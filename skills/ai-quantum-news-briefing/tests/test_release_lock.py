"""Cross-process fault injection for empty-file Windows lock startup."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from release_lock import release_lock


class ReleaseLockTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows byte-lock startup regression')
    def test_empty_lock_held_by_another_process_waits_instead_of_flushing_unlocked(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as temp:
            news = Path(temp) / 'news'
            path = news / '_index' / '.release.lock'
            path.parent.mkdir(parents=True)
            path.touch()
            ready = Path(temp) / 'ready'
            entered = Path(temp) / 'entered'
            code = (
                'import pathlib,sys; sys.path.insert(0,sys.argv[1]); '
                'from release_lock import release_lock; '
                'pathlib.Path(sys.argv[3]).touch(); '
                '\nwith release_lock(pathlib.Path(sys.argv[2]), timeout=3): '
                'pathlib.Path(sys.argv[4]).touch()')
            # Deliberately hold a lock on an empty file, which reproduces the
            # exact startup race without depending on scheduler luck.
            with path.open('a+b') as handle:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                worker = subprocess.Popen([sys.executable, '-B', '-c', code, str(SCRIPTS),
                    str(news), str(ready), str(entered)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 3
                    while not ready.exists() and time.monotonic() < deadline:
                        time.sleep(.01)
                    self.assertTrue(ready.exists())
                    time.sleep(.15)
                    self.assertFalse(entered.exists())
                finally:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    stdout, stderr = worker.communicate(timeout=5)
            self.assertEqual(worker.returncode, 0, stderr.decode('utf-8', errors='replace'))
            self.assertTrue(entered.exists())
            self.assertEqual(path.read_bytes(), b'0')

    def test_exception_inside_lock_does_not_poison_next_acquisition(self):
        with tempfile.TemporaryDirectory() as temp:
            news = Path(temp) / 'news'
            with self.assertRaisesRegex(OSError, 'injected write interruption'):
                with release_lock(news):
                    raise OSError('injected write interruption')
            with release_lock(news, timeout=.2):
                (news / 'reacquired').touch()
            self.assertTrue((news / 'reacquired').exists())
            self.assertEqual((news / '_index' / '.release.lock').read_bytes(), b'0')


if __name__ == '__main__':
    unittest.main()
