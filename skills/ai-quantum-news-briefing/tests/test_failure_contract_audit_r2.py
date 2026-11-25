"""Bounded adversarial regression: synthetic data and isolated SQLite only."""
import copy,hashlib,io,json,sys,tempfile,unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import source_worker as w
import source_recovery as recovery
import source_preparation as prep
from source_pool import SourcePool,PoolConflict,fingerprint
from collection_checkpoint import save_checkpoint
from test_dated_source import collect
DAY='2026-10-18';COVER='2026-10-17'
class ContractAuditR2(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.pool=SourcePool(self.root/'news/_sources/pool.sqlite');self.addCleanup(self.pool.close)
        self.plan=w.plan_sources(self.pool,DAY)
        self.key=next(k for k in self.plan['tasks'] if self.pool.get(k)['spec']['source_id']=='aps-prx-dated')
    def test_diagnostic_exception_cannot_replace_original_403(self):
        row=collect('aps-prx-dated',window=COVER);row['result']='error';row['evidence']['status_code']=403
        with patch.object(recovery,'academic_diagnostic',side_effect=RuntimeError('private diagnostic text')):
            result=w.run_ready(self.pool,task_ids={self.key},executor=lambda s:row,clock=lambda:1000)
        self.assertEqual(result['processed'][0]['failure']['http_status'],403)
        self.assertEqual(result['processed'][0]['failure']['code'],'source_access_denied')
        self.assertEqual(result['processed'][0]['diagnostic_warnings'],['academic_diagnostic_unavailable'])
        self.assertNotIn('private',json.dumps(result))
    def test_malformed_context_cannot_mask_403_or_leave_running(self):
        row=collect('aps-prx-dated',window=COVER);row['result']='error';row['evidence']['status_code']=403
        row['window_evidence']=['not an object'];row['candidate_count']={'bad':1}
        with patch.object(w,'validate_result',return_value=['academic_source_incomplete']):
            w.run_ready(self.pool,task_ids={self.key},executor=lambda s:row,clock=lambda:1000)
        task=self.pool.get(self.key);self.assertEqual(task['state'],'blocked');self.assertEqual(task['failure']['http_status'],403)
        self.assertIn('diagnostic_field_invalid',task['failure']['details']['validation_failures'])
    def test_bad_provider_diagnostic_cannot_override_http_403(self):
        row=collect('aps-prx-dated',window=COVER);row['result']='error';row['evidence']['status_code']=403
        row['task_diagnostic']={'code':'rate_limited','retryable':True,'private_body':'never persist'}
        w.run_ready(self.pool,task_ids={self.key},executor=lambda s:row,clock=lambda:1000)
        task=self.pool.get(self.key);self.assertEqual(task['state'],'blocked');self.assertEqual(task['failure']['http_status'],403)
        self.assertNotIn('private_body',json.dumps(task['failure']))
    def test_storage_exception_retains_primary_failure_in_error_context(self):
        row=collect('aps-prx-dated',window=COVER);row['result']='error';row['evidence']['status_code']=429
        with patch.object(self.pool,'fail',side_effect=PoolConflict('failure_contract_invalid')):
            with self.assertRaises(PoolConflict) as caught:
                w.run_ready(self.pool,task_ids={self.key},executor=lambda s:row,clock=lambda:1000)
        self.assertEqual(caught.exception.source_failure['http_status'],429)
        self.assertEqual(caught.exception.source_task_id,self.key);self.assertEqual(self.pool.get(self.key)['state'],'running')
    def legacy(self,healthy=True,code='failure_contract_invalid',spent=1):
        spec=copy.deepcopy(self.pool.get(self.key)['spec']);spec['config']['code']={'legacy':'r0'}
        # A separate source pool avoids creating a newer legacy identity after the current plan.
        self.pool.close();self.pool=SourcePool(self.root/'legacy/_sources/pool.sqlite');self.addCleanup(self.pool.close)
        old=self.pool.enqueue(spec)
        for n in range(spent):
            owner=self.pool.claim(task_id=old,now=1+n*100)
            diagnostic={'code':code,'retryable':False} if n==spent-1 else {'code':'temporary','retryable':True,'retry_after_seconds':0}
            self.pool.fail(old,owner['lease'],diagnostic,now=2+n*100)
        row=collect('aps-prx-dated',window=COVER)
        if not healthy:row.update(result='degraded',window_status='expired')
        scope={'kind':'academic_v4','terms':spec['inputs']['terms'],'date_range':COVER,'source_coverage_version':2,'checkpoint_contract':2}
        source_scope=hashlib.sha256(json.dumps({'row':spec['inputs']['row'],'source':spec['config']['source']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        path=self.pool.path.parent/'checkpoints'/(old+'.json')
        save_checkpoint(path,scope,{'rows':{spec['source_id']:row},'source_scopes':{spec['source_id']:source_scope}})
        self.plan=w.plan_sources(self.pool,DAY);key=next(k for k in self.plan['tasks'] if self.pool.get(k)['spec']['source_id']==spec['source_id'])
        return old,key,path,row
    def reconcile(self,key,path,**kw):
        return recovery.reconcile_cached_failure(self.pool,key,expected_failure_sha256=kw.get('failure',fingerprint(self.pool.get(key)['failure'])),
            expected_checkpoint_sha256=kw.get('checkpoint',hashlib.sha256(path.read_bytes()).hexdigest()),reason='legacy_failure_contract_repair',now=1000)
    def test_old_false_failure_can_restore_only_valid_cache_without_network_or_budget_reset(self):
        old,key,path,row=self.legacy();before=self.pool.get(old);raw=path.read_bytes();attempts=self.pool.get(key)['attempts']
        with patch.object(w,'execute_existing',side_effect=AssertionError('network forbidden')):result=self.reconcile(key,path)
        self.assertEqual(result['status'],'cached_failure_reconciled');self.assertEqual(self.pool.get(key)['result'],row)
        self.assertEqual(self.pool.get(key)['attempts'],attempts);self.assertEqual(self.pool.get(old),before);self.assertEqual(path.read_bytes(),raw)
        snapshot=self.pool.get(key);self.assertEqual(self.reconcile(key,path,failure=fingerprint(before['failure']))['status'],'already_reconciled')
        self.assertEqual(snapshot,self.pool.get(key));self.assertFalse(result['publication_approved'])
    def test_invalid_cache_does_not_unblock_or_consume_attempt(self):
        old,key,path,row=self.legacy(healthy=False);before=self.pool.get(key)
        result=self.reconcile(key,path);self.assertEqual(result['status'],'cached_failure_still_invalid');self.assertEqual(self.pool.get(key),before)
    def test_reconciliation_hash_conflicts_and_real_denial_are_preserved(self):
        old,key,path,row=self.legacy();before=self.pool.get(key)
        for kw in ({'failure':'0'*64},{'checkpoint':'0'*64}):
            with self.assertRaises(PoolConflict):self.reconcile(key,path,**kw)
            self.assertEqual(self.pool.get(key),before)
        # A real failure must not be reclassified even if a good cache happens to exist.
        self.pool.db.execute('UPDATE tasks SET failure=? WHERE task_id=?',(json.dumps({'code':'source_access_denied','http_status':403,'retryable':False}),key))
        denied=self.pool.get(key)
        with self.assertRaisesRegex(PoolConflict,'legacy_failure_required'):self.reconcile(key,path)
        self.assertEqual(self.pool.get(key),denied)
    def test_reconciliation_does_not_reset_exhaustion(self):
        old,key,path,row=self.legacy(spent=3);before=self.pool.get(key)
        self.assertEqual(before['attempts'],3)
        with self.assertRaisesRegex(PoolConflict,'unspent_budget_required'):self.reconcile(key,path)
        self.assertEqual(self.pool.get(key),before)
    def test_reconciliation_transaction_interruption_rolls_back_then_reenters(self):
        old,key,path,row=self.legacy();before=self.pool.get(key);original=self.pool._event
        with patch.object(self.pool,'_event',side_effect=OSError('injected commit boundary')):
            with self.assertRaises(OSError):self.reconcile(key,path)
        self.assertEqual(self.pool.get(key),before)
        self.assertEqual(self.reconcile(key,path)['status'],'cached_failure_reconciled')
    def test_reconciliation_cli_is_date_and_digest_bound(self):
        old,key,path,row=self.legacy();failure=fingerprint(self.pool.get(key)['failure']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
        args=['reconcile-cached-failure','--date',DAY,'--pool-dir',str(self.pool.path.parent),'--task-id',key,'--expected-failure-sha256',failure,'--expected-sha256',digest,'--reason','legacy_failure_contract_repair']
        with redirect_stdout(io.StringIO()):self.assertEqual(prep.main(args),0)
        with redirect_stdout(io.StringIO()):self.assertEqual(prep.main(args),0)
    def test_daily_error_output_keeps_source_failure_without_raw_exception(self):
        import orchestrate_daily as daily
        exc=PoolConflict('failure_contract_invalid');exc.source_failure={'code':'source_access_denied','http_status':403,'retryable':False};exc.source_task_id=self.key
        result=daily._execution_blocked(DAY,'source_pool',exc)
        self.assertEqual(result['terminal_blocker']['original_source_failure']['http_status'],403)
    def test_validating_shape_exception_preserves_http_cause(self):
        row=collect('aps-prx-dated',window=COVER);row['result']='error';row['evidence']['status_code']=429
        with patch.object(w,'validate_result',side_effect=AttributeError('do not serialize')):
            result=w.run_ready(self.pool,task_ids={self.key},executor=lambda s:row,clock=lambda:1000)
        self.assertEqual(result['processed'][0]['failure']['http_status'],429)
        self.assertEqual(self.pool.get(self.key)['state'],'retry_wait')
    def test_two_real_reconciliation_processes_commit_once(self):
        import subprocess,time
        old,key,path,row=self.legacy();before=self.pool.get(old)
        command=[sys.executable,'-B',str(Path(prep.__file__)),'reconcile-cached-failure','--date',DAY,'--pool-dir',str(self.pool.path.parent),
            '--task-id',key,'--expected-failure-sha256',fingerprint(self.pool.get(key)['failure']),'--expected-sha256',hashlib.sha256(path.read_bytes()).hexdigest(),'--reason','legacy_failure_contract_repair']
        with self.pool.transaction():
            children=[subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)) for _ in range(2)]
            time.sleep(.2)
            self.assertTrue(all(child.poll() is None for child in children),'both processes must wait behind the owned writer lock')
        outputs=[child.communicate(timeout=20) for child in children]
        self.assertEqual([child.returncode for child in children],[0,0],outputs)
        self.assertEqual(sorted(json.loads(out[0])['status'] for out in outputs),['already_reconciled','cached_failure_reconciled'])
        self.assertEqual(self.pool.get(key)['attempts'],1);self.assertEqual(self.pool.get(old),before)
        self.assertEqual(self.pool.db.execute("SELECT count(*) FROM events WHERE task_id=? AND state='succeeded'",(key,)).fetchone()[0],1)
    def test_corrupt_cached_diagnostic_is_isolated_and_retains_original_failure(self):
        old,key,path,row=self.legacy();from collection_checkpoint import fingerprint as cp
        value=json.loads(path.read_bytes());value['payload']['rows']=[];value['payload_sha256']=cp(value['payload']);path.write_text(json.dumps(value))
        reports=recovery.diagnose_cached(self.pool,self.plan)
        report=next(r for r in reports if r['task_id']==key)
        self.assertEqual(report['status'],'checkpoint_invalid');self.assertEqual(report['original_failure']['code'],'failure_contract_invalid')
    def test_cached_diagnostic_keeps_transport_denial_priority(self):
        row=collect('aps-prx-dated',window=COVER);row['result']='error';row['evidence']['status_code']=403
        diagnostic=recovery.academic_diagnostic(self.pool.get(self.key)['spec'],row,['academic_source_incomplete'])
        self.assertEqual(diagnostic['code'],'source_access_denied');self.assertFalse(diagnostic['retryable'])
if __name__=='__main__':unittest.main()
