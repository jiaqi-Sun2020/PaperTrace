"""Bounded recovery fixtures are synthetic; no real edition or remote approval."""
import copy,hashlib,json,sys,tempfile,unittest,io,base64,os,subprocess,time
from datetime import datetime,timezone
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from source_pool import SourcePool,task_spec
import source_worker as w
import source_recovery as recovery
from evidence_persistence import persist_public_evidence
import orchestrate_daily as o
from test_dated_source import collect,doc
from academic_sources import sources_by_id
from source_pool import PoolConflict

DAY='2026-10-17'

class BoundedRecoveryTests(unittest.TestCase):
    def test_live_daily_process_cannot_be_stolen_after_metadata_lease_expires(self):
        code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import orchestrate_daily as o;import daily_continuation as c;r=Path(sys.argv[2]);o.NEWS_ROOT=r/'news';c.time.time=lambda:1000;\ndef blocked(*a,**k):(r/'claimed').write_text('owned');time.sleep(30)\no._daily_execution=blocked;o.daily_execution('2026-10-17',action='plan')"
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'news').mkdir()
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS),td],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+10
                while not (root/'claimed').exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue((root/'claimed').exists())
                with patch.object(o,'NEWS_ROOT',root/'news'),patch('daily_continuation.time.time',return_value=1901):
                    value=o.daily_execution(DAY,action='plan')
                self.assertEqual(value['terminal_blocker']['code'],'daily_attempt_already_running')
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)

    def test_deadline_crossed_during_request_starts_no_second_request(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan=w.plan_sources(pool,DAY)
            for key in plan['tasks']:
                spec=pool.get(key)['spec']
                if spec['source_id'] in ('aps-prx-dated','crossref-quantum-dated'):
                    t=pool.claim(task_id=key,now=1);pool.complete(key,t['lease'],collect(spec['source_id'],window='2026-10-16'),w.validate_result,now=2)
            now=datetime.fromisoformat(DAY+'T15:00:00+08:00').timestamp();elapsed=[0];calls=[]
            policy={'version':1,'enabled':True,'timezone':'Asia/Shanghai','not_before':DAY+'T00:00:00+08:00',
                    'deadline':DAY+'T15:00:01+08:00','minimum_interval_seconds':60,'max_recheck_tasks':2,'max_tasks_per_invocation':2}
            def execute(spec):
                calls.append(spec['source_id']);elapsed[0]=2
                return collect(spec['source_id'],window='2026-10-16')
            with patch('time.monotonic',side_effect=lambda:elapsed[0]):
                result=recovery.recover(pool,plan,policy,now=now,executor=execute)
            self.assertEqual(len(calls),1);self.assertEqual(result['status'],'recovery_deadline_reached')

    def test_unknown_continuation_metadata_is_not_overwritten(self):
        from daily_continuation import begin
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'news';p=root/'_automation/workflow_queue.json';p.parent.mkdir(parents=True)
            raw=json.dumps({'version':1,'dates':[DAY],'daily_continuations':{DAY:{'version':99,'date':DAY}}}).encode();p.write_bytes(raw)
            with self.assertRaisesRegex(PoolConflict,'continuation_invalid'):begin(root,DAY)
            self.assertEqual(p.read_bytes(),raw)

    def test_two_actual_cli_processes_cannot_own_same_daily_attempt(self):
        code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from daily_continuation import begin;from source_pool import PoolConflict;r=Path(sys.argv[2]);\nwhile not (r/'go').exists():time.sleep(.01)\ntry:begin(r/'news','2026-10-17',now=1000)\nexcept PoolConflict:sys.exit(3)"
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'news').mkdir()
            processes=[subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS),td],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) for _ in range(2)]
            try:
                (root/'go').write_text('go')
                self.assertEqual(sorted(p.wait(timeout=15) for p in processes),[0,3])
            finally:
                for p in processes:
                    if p.poll() is None:p.terminate();p.wait(timeout=5)

    def test_actual_owned_process_termination_preserves_recoverable_daily_lease(self):
        code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from daily_continuation import begin;r=Path(sys.argv[2]);begin(r/'news','2026-10-17',now=1000);(r/'claimed').write_text('owned test process');time.sleep(30)"
        from daily_continuation import begin,finish
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'news').mkdir()
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS),td],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                deadline=time.monotonic()+10
                while not (root/'claimed').exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue((root/'claimed').exists())
                child.terminate();child.wait(timeout=5)
                with self.assertRaisesRegex(PoolConflict,'already_running'):begin(root/'news',DAY,now=1001)
                owner=begin(root/'news',DAY,now=1901)
                self.assertEqual(finish(root/'news',DAY,owner,{'phase':'candidate_shortage'})['date'],DAY)
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)

    def test_fourteen_real_cached_failures_replay_without_network_or_promotion(self):
        records=json.loads((Path(__file__).parent/'fixtures/recovery-academic-checkpoints.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'news/_sources/pool.sqlite') as pool:
            plan=w.plan_sources(pool,DAY)
            by_source={pool.get(k)['spec']['source_id']:k for k in plan['tasks']}
            for r in records:
                key=by_source[r['source_id']];lease=pool.claim(task_id=key,now=1)
                pool.fail(key,lease['lease'],{'code':'result_validation_failed','retryable':False},now=2)
                raw=base64.b64decode(r['checkpoint_base64']);self.assertEqual(hashlib.sha256(raw).hexdigest(),r['original_sha256'])
                target=pool.path.parent/'checkpoints'/(key+'.json');target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
            before={r['source_id']:pool.get(by_source[r['source_id']]) for r in records}
            with patch.object(w,'execute_existing',side_effect=AssertionError('offline diagnosis')):
                reports=recovery.diagnose_cached(pool,plan)
            self.assertEqual(len(reports),14)
            # The IEEE registry now uses a corrected journal URL. Its immutable
            # old query snapshot must remain unmatched, not be silently rekeyed.
            invalid=[r for r in reports if r['status']!='diagnosed']
            self.assertEqual([(r['source_id'],r['status']) for r in invalid],
                             [('ieee-tqe','checkpoint_invalid')])
            diagnosed=[r for r in reports if r['status']=='diagnosed']
            counts={code:sum(r['diagnostic']['code']==code for r in diagnosed) for code in {r['diagnostic']['code'] for r in diagnosed}}
            self.assertEqual(counts,{'source_window_not_covered':8,'source_adapter_unstructured':4,'source_publication_date_unknown':1})
            self.assertEqual(before,{r['source_id']:pool.get(by_source[r['source_id']]) for r in records})

    def test_retry_after_beyond_attempt_preserves_future_eligibility(self):
        from urllib.error import HTTPError
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            spec=task_spec('academic','aps-prl','2026-10-16',{}, {'code':w.code_binding()});key=pool.enqueue(spec)
            calls=[]
            def fail(spec):calls.append(1);raise HTTPError('https://synthetic.invalid/',429,'',{'Retry-After':'3600'},None)
            w.run_ready(pool,task_ids={key},coverage_date='2026-10-16',executor=fail,clock=lambda:1000)
            first=pool.get(key);self.assertEqual(first['retry_at'],4600)
            w.run_ready(pool,task_ids={key},coverage_date='2026-10-16',executor=fail,clock=lambda:1100)
            self.assertEqual(calls,[1]);self.assertEqual(pool.get(key),first)

    def test_real_public_receipt_save_rejects_tampered_body(self):
        from evidence_persistence import validate_public_http_receipt
        from test_source_preparation_flow import discovery_fixture
        from discovery_navigation import navigation_request
        receipt=discovery_fixture(navigation_request('reputable_media','2026-10-16'))['http_receipt']
        receipt['body_base64']=base64.b64encode(b'x'*120000).decode();receipt['response_hash']=hashlib.sha256(b'x'*120000).hexdigest()
        raw=json.dumps(receipt).encode();validate_public_http_receipt(raw,DAY)
        receipt['body_base64']=base64.b64encode(b'changed').decode()
        with self.assertRaisesRegex(PoolConflict,'body_mismatch'):validate_public_http_receipt(json.dumps(receipt).encode(),DAY)

    def test_live_previous_code_owner_cannot_be_rebound(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            old=task_spec('academic','aps-prl','2026-10-16',{}, {'code':{'old':'fixture'}})
            key=pool.enqueue(old);pool.claim(task_id=key,now=time.time())
            new=copy.deepcopy(old);new['config']['code']=w.code_binding()
            with self.assertRaisesRegex(PoolConflict,'previous_binding_lease'):pool.enqueue_compatible(new,lambda s,r:[])

    def test_expired_feed_is_not_a_generic_validation_error(self):
        spec=task_spec('academic','aps-prl','2026-10-16',{}, {'code':w.code_binding()})
        row={'source_id':'aps-prl','retrieval_status':'success','parse_status':'success','result':'degraded',
             'window_status':'expired','window_evidence':{'classification_basis':'target_after_feed'}}
        diagnostic=recovery.academic_diagnostic(spec,row,['academic_source_incomplete'])
        self.assertEqual(diagnostic['code'],'source_window_not_covered')
        self.assertEqual(diagnostic['validation_failures'],['academic_source_incomplete'])
        self.assertEqual(diagnostic['window_basis'],'target_after_feed')
        self.assertFalse(diagnostic['retryable'])

    def test_code_update_preserves_exhausted_attempts(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            old=task_spec('academic','aps-prl','2026-10-16',{}, {'code':{'old':'fixture'}})
            key=pool.enqueue(old)
            for n in range(3):
                row=pool.claim(task_id=key,now=1000+n*100)
                pool.fail(key,row['lease'],{'code':'source_rate_limited','http_status':429,'retryable':True},now=1001+n*100)
            new=copy.deepcopy(old);new['config']['code']=w.code_binding()
            target=pool.enqueue_compatible(new,lambda s,r:[])
            self.assertEqual(pool.get(target)['state'],'exhausted')
            self.assertEqual(pool.get(target)['attempts'],3)
            self.assertIsNone(pool.claim(task_id=target,now=5000))

    def test_large_receipt_is_saved_byte_identically_and_repeated_without_write(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'news';source=Path(td)/'public.json'
            raw=json.dumps({'public':'x'*120000}).encode();source.write_bytes(raw)
            dest=root/'_collection'/DAY/'public.json';digest=hashlib.sha256(raw).hexdigest()
            first=persist_public_evidence(source,dest,root,DAY,digest,len(raw))
            stamp=dest.stat().st_mtime_ns
            again=persist_public_evidence(source,dest,root,DAY,digest,len(raw))
            self.assertEqual(dest.read_bytes(),raw);self.assertEqual(dest.stat().st_mtime_ns,stamp)
            self.assertEqual(first['status'],'saved');self.assertEqual(again['status'],'reused')

    def test_disabled_policy_cannot_start_recovery_network(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan=w.plan_sources(pool,DAY)
            with patch.object(w,'run_ready',side_effect=AssertionError('network')):
                result=recovery.recover(pool,plan,{'version':1,'enabled':False},now=1792195200)
            self.assertEqual(result['status'],'recovery_policy_required')

    def test_cache_rebind_does_not_change_original_success_bytes_or_denial(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            old=task_spec('academic','aps-prl','2026-10-16',{}, {'code':{'old':'fixture'}})
            key=pool.enqueue(old);lease=pool.claim(task_id=key,now=1)
            prior=pool.fail(key,lease['lease'],{'code':'source_access_denied','http_status':403,'retryable':False},now=2)
            new=copy.deepcopy(old);new['config']['code']=w.code_binding()
            rebound=pool.enqueue_compatible(new,lambda s,r:[])
            self.assertEqual(pool.get(key),prior);self.assertEqual(pool.get(rebound)['state'],'blocked')
            self.assertEqual(pool.get(rebound)['attempts'],1)

    def test_rebind_revalidates_success_and_preserves_content(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            old=task_spec('academic','aps-prl','2026-10-16',{}, {'code':{'old':'fixture'}})
            key=pool.enqueue(old);lease=pool.claim(task_id=key,now=1)
            prior=pool.complete(key,lease['lease'],{'original':'bytes'},lambda s,r:[],now=2)
            new=copy.deepcopy(old);new['config']['code']=w.code_binding()
            called=[]
            target=pool.enqueue_compatible(new,lambda s,r:called.append(r) or [])
            self.assertEqual(called,[prior['result']]);self.assertEqual(pool.get(target)['result_sha'],prior['result_sha'])
            self.assertEqual(pool.get(key),prior)

    def test_unknown_evidence_output_and_short_input_are_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'news';source=Path(td)/'public.json';source.write_bytes(b'{"x":1}')
            dest=root/'_collection'/DAY/'evidence.json';dest.parent.mkdir(parents=True);dest.write_bytes(b'USER')
            with self.assertRaisesRegex(PoolConflict,'unknown_output'):
                persist_public_evidence(source,dest,root,DAY,hashlib.sha256(source.read_bytes()).hexdigest(),7)
            self.assertEqual(dest.read_bytes(),b'USER')
            with self.assertRaisesRegex(PoolConflict,'truncated'):
                persist_public_evidence(source,dest,root,DAY,'a'*64,8)

    def test_evidence_interruption_boundaries_reenter_without_retrieval(self):
        class Interrupted(BaseException):pass
        for boundary in ('before_read','after_read','before_install','after_install'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as td:
                root=Path(td)/'news';source=Path(td)/'public.json';raw=b'{"x":1}';source.write_bytes(raw)
                dest=root/'_collection'/DAY/'evidence.json';digest=hashlib.sha256(raw).hexdigest()
                def fail(point):
                    if point==boundary:raise Interrupted()
                with self.assertRaises(Interrupted):persist_public_evidence(source,dest,root,DAY,digest,len(raw),fault=fail)
                persist_public_evidence(source,dest,root,DAY,digest,len(raw))
                self.assertEqual(dest.read_bytes(),raw)

    def test_continuation_owner_conflict_and_expired_reentry(self):
        from daily_continuation import begin,finish
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'news';root.mkdir()
            owner=begin(root,DAY,now=1000)
            with self.assertRaisesRegex(PoolConflict,'already_running'):begin(root,DAY,now=1001)
            current=begin(root,DAY,now=1901)
            with self.assertRaisesRegex(PoolConflict,'lease_lost'):finish(root,DAY,owner,{},now=1902)
            record=finish(root,DAY,current,{'phase':'candidate_shortage','next_commands':[]},now=1903)
            self.assertEqual(record['date'],DAY);self.assertEqual(record['scheduling_status'],'not_scheduled_by_code')

    def test_cross_midnight_keeps_frozen_issue_and_deadline(self):
        import daily_continuation as continuation
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'news';root.mkdir()
            owner=continuation.begin(root,DAY,now=datetime.fromisoformat('2026-10-17T23:59:00+08:00').timestamp())
            value=continuation.finish(root,DAY,owner,{'phase':'article_qualification_pending'},now=datetime.fromisoformat('2026-10-18T00:01:00+08:00').timestamp())
            self.assertEqual(value['date'],DAY)

    def test_retry_after_and_exhausted_source_cannot_consume_recheck_budget(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan=w.plan_sources(pool,DAY)
            denied=next(k for k in plan['tasks'] if pool.get(k)['spec']['source_id']=='arxiv-quant-ph')
            for n in range(3):
                t=pool.claim(task_id=denied,now=1000+n*100)
                pool.fail(denied,t['lease'],{'code':'source_rate_limited','http_status':429,'retryable':True},now=1001+n*100)
            before=pool.get(denied)
            policy={'version':1,'enabled':True,'timezone':'Asia/Shanghai','not_before':DAY+'T03:00:00+08:00',
                    'deadline':DAY+'T23:59:00+08:00','minimum_interval_seconds':60,'max_recheck_tasks':2,'max_tasks_per_invocation':2}
            with patch.object(w,'run_ready',return_value={'processed':[]}) as run:
                value=recovery.recover(pool,plan,policy,now=datetime.fromisoformat(DAY+'T15:00:00+08:00').timestamp())
            self.assertEqual(pool.get(denied),before);self.assertFalse(run.called)
            self.assertEqual(value['status'],'recovery_no_eligible_sources')

    def test_not_before_after_attempt_returns_wait_without_claim(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan=w.plan_sources(pool,DAY)
            policy={'version':1,'enabled':True,'timezone':'Asia/Shanghai','not_before':DAY+'T18:00:00+08:00',
                    'deadline':DAY+'T23:59:00+08:00','minimum_interval_seconds':60,'max_recheck_tasks':2,'max_tasks_per_invocation':2}
            with patch.object(w,'run_ready',side_effect=AssertionError('not due')):
                result=recovery.recover(pool,plan,policy,now=datetime.fromisoformat(DAY+'T17:00:00+08:00').timestamp())
            self.assertEqual(result['status'],'retry_wait');self.assertEqual(result['earliest_retry_at'],datetime.fromisoformat(policy['not_before']).timestamp())

    def test_date_scope_tampering_cannot_promote_recheck(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan=w.plan_sources(pool,DAY);key=plan['tasks'][0];parent=pool.get(key)['spec']
            spec=copy.deepcopy(parent);spec['inputs']['recovery']={'parent_task_id':key,'round':1,'release_date':'2026-10-18'}
            pool.enqueue(spec,max_attempts=1)
            with self.assertRaisesRegex(PoolConflict,'scope_changed'):recovery.recheck_tasks(pool,plan)

    def test_unknown_policy_and_widened_window_rejected(self):
        bad={'version':1,'enabled':True,'timezone':'Asia/Shanghai','not_before':DAY+'T03:00:00+08:00',
             'deadline':'2026-10-18T00:10:00+08:00','minimum_interval_seconds':60,'max_recheck_tasks':2,'max_tasks_per_invocation':2}
        with self.assertRaises(PoolConflict):recovery.validate_policy(bad,DAY)

    def test_preflight_write_failure_prevents_expensive_collection(self):
        import source_preparation as preparation
        with tempfile.TemporaryDirectory() as td,patch('evidence_persistence.probe_evidence_directory',side_effect=PermissionError('synthetic denied')),patch.object(preparation,'run_ready',side_effect=AssertionError('must not collect')):
            with self.assertRaises(PermissionError):preparation.orchestrate_sources(DAY,Path(td)/'news/_sources',action='work')

if __name__=='__main__':unittest.main()
