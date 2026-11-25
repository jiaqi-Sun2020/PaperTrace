"""Offline diagnostic boundaries; no Codex/model/browser/cloud calls."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_closed_loop as c
import owned_process as owned
import worker_diagnostics as d
from test_daily_closed_loop import policy, DAY

CANARY='PRIVATE_CANARY_not_for_metadata'


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.trace=d.WorkerTrace(self.root,job='a'*32,date=DAY,role='story_review',input_sha256='b'*64)
    def persisted(self):
        return '\n'.join(p.read_text() for p in self.root.rglob('*.json'))
    def test_event_hints_store_only_categories_not_arguments_or_body(self):
        for event in ({'type':'thread.started','thread_id':CANARY},
                      {'type':'item.started','item':{'id':CANARY,'type':'command_execution','command':CANARY}},
                      {'type':'item.completed','item':{'id':CANARY,'type':'command_execution','output':CANARY}},
                      {'type':'item.completed','item':{'type':'reasoning','text':CANARY}},
                      {'type':'error','message':CANARY}):
            self.trace.feed((json.dumps(event)+'\n').encode())
        self.trace.checkpoint();result=self.trace.finish(outcome='blocked')
        self.assertEqual(result['status'],'saved')
        self.assertNotIn(CANARY,self.persisted())
        data=json.loads((self.root/'worker-diagnostics.json').read_text())
        self.assertEqual(data['authority'],'diagnostic_hints_only')
        self.assertIn('command',[v.get('category') for v in data['events']])
        self.assertIn('duration_ms',data['events'][2])
    def test_oversized_lines_and_split_json_remain_bounded(self):
        self.trace.feed(b'x'*200000+b'\n'+b'{"type":"turn.')
        self.trace.feed(b'started"}\n')
        self.assertLessEqual(len(self.trace.buffer),self.trace.MAX_LINE)
        self.assertEqual(self.trace.lines['oversized'],1)
        self.assertEqual(self.trace.counts['inference_started'],1)
    def test_malformed_and_unknown_events_cannot_crash_or_echo(self):
        self.trace.feed(b'\xff\n[1]\n{"type":{}}\n{"type":"item.completed","item":{"type":[]}}\n')
        self.trace.observe([],category=[CANARY],text=CANARY)
        self.trace.finish(outcome='blocked',output={'sha256':CANARY,'secret':CANARY})
        self.assertNotIn(CANARY,self.persisted())
        self.assertEqual(self.trace.lines['invalid'],1)
    def test_event_and_checkpoint_caps_are_enforced(self):
        self.trace.MAX_CHECKPOINTS=2
        for _ in range(200):self.trace.observe('progress');self.trace.checkpoint()
        self.trace.finish(outcome='completed')
        self.assertEqual(len(self.trace.events),96)
        self.assertEqual(self.trace.dropped,105) # includes final outcome
        self.assertEqual(len(list((self.root/'worker-diagnostics').glob('*.json'))),2)
    def test_repeat_finish_is_idempotent(self):
        first=self.trace.finish(outcome='blocked');raw=(self.root/'worker-diagnostics.json').read_bytes()
        second=self.trace.finish(outcome='completed')
        self.assertEqual(first,second);self.assertEqual(raw,(self.root/'worker-diagnostics.json').read_bytes())
    def test_unknown_metadata_file_is_not_overwritten(self):
        path=self.root/'worker-diagnostics.json';path.write_text(CANARY)
        result=self.trace.finish(outcome='blocked')
        self.assertEqual(result['status'],'incomplete');self.assertEqual(path.read_text(),CANARY)
    def test_persistence_denial_is_diagnostic_and_sanitized(self):
        with patch.object(d,'install_new_json',side_effect=PermissionError(13,CANARY)):
            self.trace.checkpoint();result=self.trace.finish(outcome='blocked')
        self.assertEqual(result['status'],'incomplete')
        self.assertNotIn(CANARY,json.dumps(result));self.assertEqual(result['errors'][0]['errno'],13)
    def test_output_summary_has_no_untrusted_fields(self):
        self.trace.finish(outcome='completed',output={'observed_bytes':123,'sha256':'c'*64,
                         'complete':True,'command':CANARY},cleanup_confirmed=True)
        data=json.loads((self.root/'worker-diagnostics.json').read_text())
        self.assertEqual(data['process_output']['sha256'],'c'*64)
        self.assertNotIn(CANARY,self.persisted())
    def test_command_exit_code_is_retained_without_its_error_output(self):
        self.trace.feed((json.dumps({'type':'item.completed','item':{'type':'command_execution','exit_code':5,'aggregated_output':CANARY}})+'\n').encode())
        self.trace.finish(outcome='blocked')
        self.assertEqual(self.trace.events[0]['returncode'],5)
        self.assertNotIn(CANARY,self.persisted())


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'news'
    def invoke(self,worker,role='author'):
        with patch.object(c,'run_owned',side_effect=worker):
            return c.run_agent(self.root,DAY,role,{'identity':'a'*64},policy(),120)
    def worker(self,value='valid'):
        def run(argv,**kw):
            self.assertIn('--json',argv);self.assertTrue(kw['capture_metadata'])
            packet=json.loads(next(x for x in kw['input'].decode().splitlines() if x.startswith('{')))
            receipt=Path(argv[argv.index('--output-last-message')+1])
            result={k:packet[k] for k in ('job_id','date','input_sha256')}
            result.update(status='completed',code='fixture_only')
            if value=='spoof-timeout':result['code']='agent_timeout_outcome_uncertain'
            if value=='identity':result['input_sha256']='b'*64
            if value=='bad-type':result['status']=[];result['code']={}
            if value!='absent':
                receipt.write_bytes(b'{bad' if value=='json' else b'\xff' if value=='utf8' else json.dumps(result).encode())
            process=subprocess.CompletedProcess(argv,0)
            process.cleanup_confirmed=True;process.cleanup_failure_codes=[]
            process.output_metadata={'observed_bytes':0,'sha256':hashlib.sha256(b'').hexdigest(),'complete':True}
            return process
        return run
    def test_normal_receipt_binds_digest_and_diagnostic(self):
        result=self.invoke(self.worker())
        self.assertEqual(result['status'],'completed');self.assertTrue(result['cleanup_confirmed'])
        self.assertEqual(result['diagnostic']['status'],'saved')
        saved=next(self.root.rglob('worker-result.json'))
        self.assertEqual(result['receipt_sha256'],hashlib.sha256(saved.read_bytes()).hexdigest())
    def test_missing_receipt_remains_blocked(self):
        self.assertEqual(self.invoke(self.worker('absent'))['code'],'agent_receipt_missing_or_large')
    def test_worker_claim_cannot_forge_host_timeout_diagnostic(self):
        self.invoke(self.worker('spoof-timeout'))
        data=json.loads(next(self.root.rglob('worker-diagnostics.json')).read_text())
        self.assertEqual(data['outcome'],'completed')
        self.assertNotIn('timeout',data['phase_counts'])
    def test_wrong_receipt_identity_and_types_remain_blocked(self):
        for case in ('identity','bad-type'):
            with self.subTest(case=case):
                self.assertEqual(self.invoke(self.worker(case))['code'],'agent_receipt_identity_invalid')
    def test_invalid_json_and_encoding_remain_blocked(self):
        for case in ('json','utf8'):
            with self.subTest(case=case):
                self.assertEqual(self.invoke(self.worker(case))['code'],'agent_receipt_invalid_json')
    def test_input_write_error_reports_operation_and_errno_only(self):
        with patch.object(c,'atomic_json',side_effect=PermissionError(13,CANARY)):
            result=self.invoke(Mock(side_effect=AssertionError('must not start')))
        self.assertEqual(result['code'],'agent_input_write_failed');self.assertEqual(result['io_error']['errno'],13)
        self.assertNotIn(CANARY,json.dumps(result))
    def test_receipt_read_error_is_not_a_missing_receipt(self):
        original=Path.read_bytes
        def read(path):
            if path.name=='worker-result.json':raise PermissionError(13,CANARY)
            return original(path)
        with patch.object(Path,'read_bytes',read):result=self.invoke(self.worker())
        self.assertEqual(result['code'],'agent_receipt_read_failed')
        self.assertNotIn(CANARY,json.dumps(result))
    def test_diagnostic_constructor_failure_does_not_replace_primary_timeout(self):
        with patch.object(c,'WorkerTrace',side_effect=PermissionError(13,CANARY)):
            result=self.invoke(Mock(side_effect=subprocess.TimeoutExpired('fake',120)))
        self.assertEqual(result['code'],'agent_timeout_outcome_uncertain')
        self.assertEqual(result['diagnostic']['status'],'incomplete')
        self.assertNotIn(CANARY,json.dumps(result))
    def test_diagnostic_finalize_failure_does_not_replace_receipt_error(self):
        with patch.object(d.WorkerTrace,'finish',side_effect=OSError(5,CANARY)):
            result=self.invoke(self.worker('identity'))
        self.assertEqual(result['code'],'agent_receipt_identity_invalid')
        self.assertNotIn(CANARY,json.dumps(result))
    def test_timeout_keeps_cleanup_uncertainty_as_secondary(self):
        failure=subprocess.TimeoutExpired('fake',120)
        failure.cleanup_confirmed=False;failure.cleanup_failure_codes=['owned_job_member_exit_unconfirmed']
        result=self.invoke(Mock(side_effect=failure))
        self.assertEqual(result['code'],'agent_timeout_outcome_uncertain')
        self.assertFalse(result['cleanup_confirmed'])
        self.assertEqual(result['cleanup_failure_codes'],['owned_job_member_exit_unconfirmed'])
    def test_spawn_io_error_does_not_leak_path_or_exception(self):
        result=self.invoke(Mock(side_effect=PermissionError(13,CANARY)))
        self.assertEqual(result['code'],'agent_process_io_failed');self.assertNotIn(CANARY,json.dumps(result))


class FakeProcess:
    def __init__(self,data=b'',running=False):
        self.stdout=io.BytesIO(data);self.returncode=None if running else 0;self.pid=1
    def poll(self):return self.returncode
    def kill(self):self.returncode=-9
    def wait(self,timeout=None):
        if self.returncode is None:self.returncode=-9
        return self.returncode


class OwnedMetadataTests(unittest.TestCase):
    def run_fake(self,process,job=None,observer=None):
        self.assertEqual(owned.os.name,'nt','fake Job tests require Windows; not process queries')
        self.job=job or Mock()
        with patch.object(owned,'WindowsJob',return_value=self.job),patch.object(owned.subprocess,'Popen',return_value=process):
            return owned.run_owned(['fake-no-model'],input=b'',timeout=120,capture_metadata=True,
                                   observer=observer,output_limit=1024)
    def test_normal_output_count_and_digest_without_raw_capture(self):
        raw=(json.dumps({'type':'turn.started','text':CANARY})+'\n').encode()
        result=self.run_fake(FakeProcess(raw))
        self.assertEqual(result.output_metadata['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(result.output_metadata['observed_bytes'],len(raw))
        self.assertTrue(result.output_metadata['complete']);self.assertTrue(result.cleanup_confirmed)
        self.assertNotIn(CANARY,json.dumps(result.output_metadata))
    def test_120_second_timeout_is_injected_not_waited(self):
        clock=iter(range(1000))
        with patch.object(owned.time,'monotonic',side_effect=lambda:next(clock)),patch.object(owned.time,'sleep'):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:self.run_fake(FakeProcess(running=True))
        self.assertEqual(caught.exception.timeout,120);self.assertTrue(caught.exception.cleanup_confirmed)
    def test_cleanup_failure_cannot_mask_primary_timeout(self):
        job=Mock();job.close.side_effect=owned.OwnedProcessError('owned_job_member_exit_unconfirmed')
        clock=iter(range(1000))
        with patch.object(owned.time,'monotonic',side_effect=lambda:next(clock)),patch.object(owned.time,'sleep'):
            with self.assertRaises(subprocess.TimeoutExpired) as caught:self.run_fake(FakeProcess(running=True),job)
        self.assertFalse(caught.exception.cleanup_confirmed)
        self.assertEqual(caught.exception.cleanup_failure_codes,['owned_job_member_exit_unconfirmed'])
    def test_success_with_unconfirmed_owned_children_is_blocked(self):
        job=Mock();job.close.side_effect=owned.OwnedProcessError('owned_job_member_exit_unconfirmed')
        with self.assertRaisesRegex(owned.OwnedProcessError,'owned_job_member_exit_unconfirmed'):
            self.run_fake(FakeProcess(),job)
    def test_output_limit_survives_observer_failure(self):
        observer=Mock();observer.feed.side_effect=OSError(CANARY)
        with self.assertRaisesRegex(owned.OwnedProcessError,'owned_output_limit') as caught:
            self.run_fake(FakeProcess(b'x'*3000),observer=observer)
        self.assertTrue(caught.exception.output_metadata['observer_failed'])
        self.assertFalse(caught.exception.output_metadata['complete'])
    def test_output_read_error_is_an_independent_blocker(self):
        proc=FakeProcess();proc.stdout=Mock();proc.stdout.read1.side_effect=OSError(CANARY)
        with self.assertRaisesRegex(owned.OwnedProcessError,'owned_output_read_failed') as caught:
            self.run_fake(proc)
        self.assertTrue(caught.exception.output_metadata['read_failed'])
        self.assertNotIn(CANARY,json.dumps(caught.exception.output_metadata))
    def test_arbitrary_cleanup_message_is_not_exported(self):
        job=Mock();job.close.side_effect=PermissionError(13,CANARY)
        with self.assertRaises(owned.OwnedProcessError) as caught:self.run_fake(FakeProcess(),job)
        self.assertEqual(str(caught.exception),'owned_cleanup_failed')
        self.assertNotIn(CANARY,str(caught.exception.cleanup_failure_codes))


class RealPythonPipeTests(unittest.TestCase):
    """Real owned Python helpers, not models; no network, no global process query."""
    def test_real_pipe_event_count_and_cleanup(self):
        with tempfile.TemporaryDirectory() as base:
            trace=d.WorkerTrace(base,job='a'*32,date=DAY,role='author',input_sha256='b'*64)
            raw=b'{"type":"turn.started"}\n'
            result=owned.run_owned([sys.executable,'-B','-c','import sys;sys.stdout.buffer.write('+repr(raw)+')'],
                                   input=b'',timeout=10,capture_metadata=True,observer=trace)
            self.assertEqual(result.output_metadata['observed_bytes'],len(raw))
            self.assertEqual(result.output_metadata['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertTrue(result.cleanup_confirmed);self.assertTrue(result.output_metadata['complete'])
            self.assertEqual(trace.counts['inference_started'],1)
    def test_real_pipe_timeout_kills_owned_child_only(self):
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            owned.run_owned([sys.executable,'-B','-c','import time;print("started",flush=True);time.sleep(20)'],
                            input=b'',timeout=.5,capture_metadata=True)
        self.assertTrue(caught.exception.cleanup_confirmed)
        self.assertGreater(caught.exception.output_metadata['observed_bytes'],0)
    def test_real_pipe_large_output_is_rejected(self):
        with self.assertRaisesRegex(owned.OwnedProcessError,'owned_output_limit') as caught:
            owned.run_owned([sys.executable,'-B','-c','import sys;sys.stdout.write("x"*100000)'],
                            input=b'',timeout=10,capture_metadata=True,output_limit=1024)
        self.assertTrue(caught.exception.cleanup_confirmed)
        self.assertFalse(caught.exception.output_metadata['complete'])


if __name__=='__main__':unittest.main()
