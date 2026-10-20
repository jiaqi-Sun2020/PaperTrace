"""Only synthetic source/browser evidence; no real collection or publication."""
import copy,hashlib,io,json,sys,tempfile,unittest,subprocess
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(SCRIPTS))
from source_pool import SourcePool,PoolConflict,task_spec
import source_worker as w
import source_preparation as prep
import evidence_persistence as evidence
from discovery_navigation import navigation_request
from test_source_preparation_flow import discovery_fixture
from test_dated_source import collect
DAY='2026-10-18';COVER='2026-10-17'
class FailureAndObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.pool=SourcePool(self.root/'news/_sources/pool.sqlite');self.addCleanup(self.pool.close)
    def academic(self):return self.pool.enqueue(task_spec('academic','aps-prx-dated',COVER,{}, {'code':w.code_binding()}))
    def discovery(self,max_attempts=3):
        req=navigation_request('executive_social',COVER)
        key=self.pool.enqueue(task_spec('discovery','executive_social',COVER,{'navigation':req},{'code':w.code_binding()}),max_attempts=max_attempts)
        return key,discovery_fixture(req)
    def test_worker_records_expired_window_context_without_masking(self):
        key=self.academic();row=collect('aps-prx-dated',window=COVER)
        row.update(window_status='expired',result='degraded',window_evidence={'classification_basis':'target_after_feed'})
        result=w.run_ready(self.pool,task_ids={key},coverage_date=COVER,executor=lambda s:row,clock=lambda:1000)
        failure=result['processed'][0]['failure']
        self.assertEqual(failure['code'],'source_window_not_covered')
        self.assertEqual(failure['details']['window_basis'],'target_after_feed')
        self.assertIn('academic_source_incomplete',failure['details']['validation_failures'])
        self.assertEqual(self.pool.get(key)['attempts'],1)
    def test_embedded_429_keeps_retry_after_and_academic_context(self):
        key=self.academic();row=collect('aps-prx-dated',window=COVER)
        row['evidence'].update(status_code=429,retry_after='3600');row['result']='error'
        w.run_ready(self.pool,task_ids={key},executor=lambda s:row,clock=lambda:1000)
        task=self.pool.get(key);self.assertEqual(task['state'],'retry_wait');self.assertEqual(task['retry_at'],4600)
        self.assertEqual(task['failure']['http_status'],429);self.assertTrue(task['failure']['retryable'])
        self.assertIn('validation_failures',task['failure']['details'])
    def test_failure_store_bug_is_not_recorded_as_source_failure(self):
        key=self.academic();row=collect('aps-prx-dated',window=COVER);row['result']='error'
        with patch.object(self.pool,'fail',side_effect=PoolConflict('failure_contract_invalid')) as fail:
            with self.assertRaisesRegex(PoolConflict,'failure_contract_invalid'):
                w.run_ready(self.pool,task_ids={key},executor=lambda s:row,clock=lambda:1000)
        self.assertEqual(fail.call_count,1);self.assertEqual(self.pool.get(key)['state'],'running')
    def test_flat_unknown_failure_fields_still_rejected(self):
        key=self.academic();owner=self.pool.claim(task_id=key,now=1)
        with self.assertRaisesRegex(PoolConflict,'failure_contract_invalid'):
            self.pool.fail(key,owner['lease'],{'code':'failed','retryable':False,'private_body':'DO NOT STORE'},now=2)
        self.assertEqual(self.pool.get(key)['state'],'running')
    def test_discovery_envelope_saves_exact_bytes_and_reuses(self):
        key,record=self.discovery();raw=(json.dumps(record,indent=3)+'\n').encode();source=self.root/'public-observation.json';source.write_bytes(raw)
        target=self.root/'news/_collection'/DAY/'executive-discovery.json';digest=hashlib.sha256(raw).hexdigest()
        args=['save-discovery','--news-root',str(self.root/'news'),'--date',DAY,'--input',str(source),'--output',str(target),'--expected-sha256',digest,'--expected-bytes',str(len(raw))]
        with redirect_stdout(io.StringIO()):self.assertEqual(evidence.main(args),0)
        stamp=target.stat().st_mtime_ns
        with redirect_stdout(io.StringIO()):self.assertEqual(evidence.main(args),0)
        self.assertEqual(target.read_bytes(),raw);self.assertEqual(target.stat().st_mtime_ns,stamp)
    def test_discovery_invalid_digest_and_mixed_date_rejected_before_write(self):
        key,record=self.discovery();record['observation_sha256']='0'*64
        with self.assertRaisesRegex(PoolConflict,'discovery_evidence_invalid'):
            evidence.validate_discovery_evidence(json.dumps(record).encode(),DAY)
        key,record=self.discovery()
        with self.assertRaisesRegex(PoolConflict,'discovery_evidence_invalid'):
            evidence.validate_discovery_evidence(json.dumps(record).encode(),'2026-10-19')
    def test_resume_expired_discovery_reuses_evidence_and_spent_budget(self):
        key,record=self.discovery();old=w.claim_discovery(self.pool,key,now=1)
        value=w.resume_discovery(self.pool,key,record,now=902)
        self.assertEqual(value['state'],'succeeded');self.assertFalse(value['network_executed'])
        self.assertEqual(self.pool.get(key)['attempts'],2)
        with self.assertRaisesRegex(PoolConflict,'stale_or_expired'):
            w.submit_discovery(self.pool,key,old['lease'],record,now=903)
        snapshot=self.pool.get(key)
        self.assertEqual(w.resume_discovery(self.pool,key,record,now=904)['status'],'already_committed')
        self.assertEqual(self.pool.get(key),snapshot)
    def test_resume_does_not_steal_live_owner_or_reset_exhausted(self):
        key,record=self.discovery(max_attempts=1);w.claim_discovery(self.pool,key,now=1)
        self.assertEqual(w.resume_discovery(self.pool,key,record,now=2)['state'],'running')
        self.assertEqual(self.pool.get(key)['attempts'],1)
        self.assertEqual(w.resume_discovery(self.pool,key,record,now=902)['state'],'exhausted')
        self.assertEqual(self.pool.get(key)['attempts'],1)
    def test_invalid_saved_observation_does_not_consume_lease(self):
        key,record=self.discovery();record['source_class']='reputable_media';before=self.pool.get(key)
        with self.assertRaisesRegex(PoolConflict,'saved_discovery_invalid'):
            w.resume_discovery(self.pool,key,record,now=1000)
        self.assertEqual(self.pool.get(key),before)
    def test_save_permission_error_reports_operation_without_leaking_exception_text(self):
        with patch.object(evidence,'persist_public_evidence',side_effect=PermissionError(13,'SENSITIVE SENTINEL')):
            with redirect_stdout(io.StringIO()) as stream:
                code=evidence.main(['save','--news-root',str(self.root/'news'),'--date',DAY,'--input','public.json','--output','output.json','--expected-sha256','a'*64,'--expected-bytes','4'])
        self.assertEqual(code,2);value=json.loads(stream.getvalue());self.assertEqual(value['errno'],13)
        self.assertEqual(value['operation'],'save');self.assertNotIn('SENSITIVE',stream.getvalue())
    def test_403_never_becomes_retryable_after_details_are_added(self):
        key=self.academic();row=collect('aps-prx-dated',window=COVER);row['evidence']['status_code']=403;row['result']='error'
        w.run_ready(self.pool,task_ids={key},executor=lambda s:row,clock=lambda:1000)
        task=self.pool.get(key);self.assertEqual(task['state'],'blocked');self.assertEqual(task['failure']['http_status'],403)
        self.assertFalse(task['failure']['retryable']);self.assertIn('details',task['failure'])
        with patch.object(w,'execute_existing',side_effect=AssertionError('403 must not retry')):w.run_ready(self.pool,task_ids={key},clock=lambda:9000)
        self.assertEqual(self.pool.get(key)['attempts'],1)
    def test_details_reject_unknown_fields_and_cross_source_binding(self):
        import source_recovery as recovery
        key=self.academic();owner=self.pool.claim(task_id=key,now=1);spec=owner['spec']
        context=recovery.academic_diagnostic(spec,{},['row_not_object'])
        details={'version':1,**{k:v for k,v in context.items() if k not in ('code','retryable','recovery_action')}}
        details['unknown']='DO NOT STORE'
        with self.assertRaisesRegex(PoolConflict,'details_invalid'):self.pool.fail(key,owner['lease'],{'code':'failed','retryable':False},details=details,now=2)
        details.pop('unknown');details['source_id']='another-source'
        with self.assertRaisesRegex(PoolConflict,'binding_changed'):self.pool.fail(key,owner['lease'],{'code':'failed','retryable':False},details=details,now=2)
        self.assertEqual(self.pool.get(key)['state'],'running')
    def test_resume_cli_binds_saved_bytes_and_is_idempotent(self):
        key,record=self.discovery();p=self.root/'saved-public.json';raw=json.dumps(record).encode();p.write_bytes(raw)
        args=['resume-discovery','--date',DAY,'--pool-dir',str(self.pool.path.parent),'--task-id',key,'--input',str(p),'--expected-sha256',hashlib.sha256(raw).hexdigest()]
        with redirect_stdout(io.StringIO()):self.assertEqual(prep.main(args),0)
        before=self.pool.get(key)
        with redirect_stdout(io.StringIO()):self.assertEqual(prep.main(args),0)
        self.assertEqual(self.pool.get(key),before)
        p.write_bytes(raw+b' ')
        with redirect_stdout(io.StringIO()):self.assertEqual(prep.main(args),2)
        self.assertEqual(self.pool.get(key),before)
    def test_cached_diagnosis_follows_code_alias_without_copying_cache(self):
        import source_recovery as recovery
        from collection_checkpoint import save_checkpoint
        plan=w.plan_sources(self.pool,DAY);key=next(k for k in plan['tasks'] if self.pool.get(k)['spec']['source_id']=='aps-prx-dated')
        spec=self.pool.get(key)['spec'];row=collect('aps-prx-dated',window=COVER);row.update(result='degraded',window_status='expired',window_evidence={'classification_basis':'target_after_feed'})
        owner=self.pool.claim(task_id=key,now=1);self.pool.fail(key,owner['lease'],{'code':'failure_contract_invalid','retryable':False},now=2)
        scope={'kind':'academic_v4','terms':spec['inputs']['terms'],'date_range':COVER,'source_coverage_version':2,'checkpoint_contract':2}
        source_scope=hashlib.sha256(json.dumps({'row':spec['inputs']['row'],'source':spec['config']['source']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        p=self.pool.path.parent/'checkpoints'/(key+'.json');save_checkpoint(p,scope,{'rows':{spec['source_id']:row},'source_scopes':{spec['source_id']:source_scope}});raw=p.read_bytes()
        updated=copy.deepcopy(spec);updated['config']['code']={'new':'binding'}
        alias=self.pool.enqueue_compatible(updated,lambda s,v:[])
        reports=recovery.diagnose_cached(self.pool,plan);report=next(v for v in reports if v['task_id']==alias)
        self.assertEqual(report['status'],'diagnosed');self.assertEqual(report['checkpoint_task_id'],key)
        self.assertEqual(report['diagnostic']['code'],'source_window_not_covered')
        self.assertEqual(p.read_bytes(),raw);self.assertFalse((p.parent/(alias+'.json')).exists())
        self.assertEqual(self.pool.get(alias)['attempts'],1)
    def test_saved_discovery_commit_ack_loss_is_idempotent(self):
        key,record=self.discovery();complete=self.pool.complete
        def lost(*a,**kw):complete(*a,**kw);raise OSError('synthetic lost acknowledgement')
        with patch.object(self.pool,'complete',side_effect=lost):
            with self.assertRaises(OSError):w.resume_discovery(self.pool,key,record,now=1000)
        before=self.pool.get(key);self.assertEqual(before['state'],'succeeded')
        self.assertEqual(w.resume_discovery(self.pool,key,record,now=1001)['status'],'already_committed')
        self.assertEqual(self.pool.get(key),before);self.assertEqual(before['attempts'],1)
    def test_two_actual_resume_processes_consume_only_one_lease(self):
        key,record=self.discovery();path=self.root/'saved-public.json';raw=json.dumps(record).encode();path.write_bytes(raw)
        argv=[sys.executable,'-B',str(SCRIPTS/'source_preparation.py'),'resume-discovery','--date',DAY,
              '--pool-dir',str(self.pool.path.parent),'--task-id',key,'--input',str(path),'--expected-sha256',hashlib.sha256(raw).hexdigest()]
        processes=[subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
        try:
            outputs=[child.communicate(timeout=15) for child in processes]
            self.assertEqual([p.returncode for p in processes],[0,0],outputs)
            self.assertTrue(all(json.loads(out)['network_executed'] is False for out,err in outputs))
            task=self.pool.get(key);self.assertEqual(task['state'],'succeeded');self.assertEqual(task['attempts'],1)
        finally:
            for child in processes:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
    def test_racing_different_committed_observation_is_not_acknowledged_as_ours(self):
        from daily_coverage_evidence import evidence_digest
        key,record=self.discovery();other=copy.deepcopy(record)
        other['observation']['recorded_at']='2026-10-18T01:01:00+08:00'
        other['observation_sha256']=evidence_digest(other['observation'])[7:]
        def race(pool,task_id,now=None):
            owner=pool.claim(task_id=task_id,now=1000)
            w.submit_discovery(pool,key,owner['lease'],other,now=1001)
            return {'state':'succeeded','action':None}
        with patch.object(w,'claim_discovery',side_effect=race):
            with self.assertRaisesRegex(PoolConflict,'saved_discovery_result_conflict'):
                w.resume_discovery(self.pool,key,record,now=1002)
        self.assertEqual(self.pool.get(key)['result'],other)
if __name__=='__main__':unittest.main()
