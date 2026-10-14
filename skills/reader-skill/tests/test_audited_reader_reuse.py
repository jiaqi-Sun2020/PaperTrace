"""A passing same-source resume must preserve browser-bound HTML bytes."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('batch_reuse_test', SCRIPTS / 'build_formal_reader_batch.py')
batch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(batch)


def test_reuse_requires_both_current_and_publishing_audits(tmp_path, monkeypatch):
    html = tmp_path / 'reader_interactive.html'
    html.write_text('already browser-reviewed bytes', encoding='utf-8')
    monkeypatch.setattr(batch, 'reader_is_formal_ready', lambda _: (True, []))
    calls = []
    monkeypatch.setattr(batch.subprocess, 'run', lambda cmd, **_: calls.append(cmd) or SimpleNamespace(returncode=0))
    refreshed = []
    monkeypatch.setattr(batch, 'clear_stale_after_audit', lambda p: refreshed.append(p))
    assert batch.reuse_audited_formal_reader(tmp_path)
    assert len(calls) == 2 and '--no-write' in calls[0] and '--no-write' not in calls[1]
    assert all('adversarial_html_audit.py' in cmd[1] for cmd in calls)
    assert refreshed == [tmp_path]
    assert html.read_text(encoding='utf-8') == 'already browser-reviewed bytes'


def test_failed_or_incomplete_reuse_cannot_certify(tmp_path, monkeypatch):
    (tmp_path / 'reader_interactive.html').write_text('stale', encoding='utf-8')
    monkeypatch.setattr(batch, 'reader_is_formal_ready', lambda _: (True, []))
    monkeypatch.setattr(batch.subprocess, 'run', lambda *_, **__: SimpleNamespace(returncode=1))
    monkeypatch.setattr(batch, 'clear_stale_after_audit', lambda _: (_ for _ in ()).throw(AssertionError('must not certify')))
    assert not batch.reuse_audited_formal_reader(tmp_path)
    monkeypatch.setattr(batch, 'reader_is_formal_ready', lambda _: (False, ['incomplete']))
    assert not batch.reuse_audited_formal_reader(tmp_path)
