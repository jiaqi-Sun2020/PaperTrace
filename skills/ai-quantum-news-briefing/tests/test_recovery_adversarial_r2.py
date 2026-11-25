"""Second adversarial pass: synthetic DBs and public byte fixtures only."""
import copy,hashlib,json,sys,tempfile,time,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(SCRIPTS))
from source_pool import SourcePool,task_spec,PoolConflict
import source_worker as w
import source_recovery as r
from test_dated_source import collect
from evidence_persistence import persist_public_evidence
DAY='2026-10-17';COVER='2026-10-16'
class RecoveryAdversarialR2(unittest.TestCase):
    def old(self,code):return task_spec('academic','aps-prl',COVER,{}, {'code':{'version':code}})
    def spend(self,pool,key,now=1000):
        lease=pool.claim(task_id=key,now=now)
        self.assertIsNotNone(lease)
        pool.fail(key,lease['lease'],{'code':'rate_limited','http_status':429,'retryable':True,'retry_after_seconds':60},now=now+1)
    def test_independent_legacy_bindings_count_all_real_claims(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            a=pool.enqueue(self.old('a'));self.spend(pool,a)
            b=pool.enqueue(self.old('b'));self.spend(pool,b,2000)
            c=pool.enqueue_compatible(self.old('c'),lambda s,v:[])
            self.assertEqual(pool.get(c)['attempts'],2)
            self.spend(pool,c,3000)
            self.assertEqual(pool.get(c)['state'],'exhausted')
            self.assertIsNone(pool.claim(task_id=c,now=5000))
    def test_copied_budget_is_not_counted_twice_and_old_alias_cannot_run(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            a=pool.enqueue(self.old('a'));self.spend(pool,a)
            b=pool.enqueue_compatible(self.old('b'),lambda s,v:[])
            self.assertIsNone(pool.claim(task_id=a,now=2000))
            self.spend(pool,b,2000)
            c=pool.enqueue_compatible(self.old('c'),lambda s,v:[])
            self.assertEqual(pool.get(c)['attempts'],2)
            self.spend(pool,c,3000);self.assertIsNone(pool.claim(task_id=c,now=5000))
    def test_retry_after_from_another_identity_cannot_be_shortened(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            a=pool.enqueue(self.old('a'));self.spend(pool,a)
            b=pool.enqueue(self.old('b'));self.spend(pool,b,2000)
            pool.db.execute('UPDATE tasks SET retry_at=? WHERE task_id=?',(9000,a))
            c=pool.enqueue_compatible(self.old('c'),lambda s,v:[])
            self.assertEqual(pool.get(c)['retry_at'],9000)
            self.assertIsNone(pool.claim(task_id=c,now=8999))
    def test_expired_old_owner_rebind_is_recoverable_without_restoring_attempt(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            a=pool.enqueue(self.old('a'));pool.claim(task_id=a,now=1)
            before=pool.get(a)
            b=pool.enqueue_compatible(self.old('b'),lambda s,v:[])
            self.assertEqual(pool.get(a),before)
            self.assertEqual(pool.get(b)['attempts'],1)
            self.assertIsNotNone(pool.claim(task_id=b,now=time.time()+1))
            self.assertIsNone(pool.claim(task_id=a,now=time.time()+2))
    def test_pending_recheck_survives_code_rebind_with_one_shared_reservation(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            first=w.plan_sources(pool,DAY)
            for key in first['tasks']:
                spec=pool.get(key)['spec']
                if spec['source_id'] in ('aps-prx-dated','crossref-quantum-dated'):
                    lease=pool.claim(task_id=key,now=1)
                    pool.complete(key,lease['lease'],collect(spec['source_id'],window=COVER),w.validate_result,now=2)
            now=datetime.fromisoformat(DAY+'T15:00:00+08:00').timestamp()
            policy={'version':1,'enabled':True,'timezone':'Asia/Shanghai','not_before':DAY+'T00:00:00+08:00',
                    'deadline':DAY+'T23:59:00+08:00','minimum_interval_seconds':60,'max_recheck_tasks':2,'max_tasks_per_invocation':1}
            calls=[]
            def execute(spec):calls.append(spec['source_id']);return collect(spec['source_id'],window=COVER)
            one=r.recover(pool,first,policy,now=now,executor=execute)
            self.assertEqual(len(calls),1);self.assertEqual(one['reserved_rechecks'],2)
            binding={**w.code_binding(),'r2_fixture':'changed'}
            with patch.object(w,'code_binding',return_value=binding):
                second=w.plan_sources(pool,DAY)
                two=r.recover(pool,second,policy,now=now+61,executor=execute)
                self.assertEqual(len(calls),2)
                self.assertEqual(two['status'],'recovery_budget_consumed')
                self.assertEqual(two['reserved_rechecks'],2)
                r.recover(pool,second,policy,now=now+122,executor=execute)
                self.assertEqual(len(calls),2)
                self.assertEqual(len(r.recheck_tasks(pool,second)),2)
    def test_post_read_hardlinked_unknown_destination_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'public.json';raw=json.dumps({'large':'x'*120000}).encode();source.write_bytes(raw)
            external=root/'keep.json';external.write_bytes(raw)
            dest=root/'news/_collection'/DAY/'evidence.json'
            def fault(point):
                if point=='after_read':
                    dest.parent.mkdir(parents=True);__import__('os').link(str(external),str(dest))
            with self.assertRaisesRegex(PoolConflict,'private_regular'):
                persist_public_evidence(source,dest,root/'news',DAY,hashlib.sha256(raw).hexdigest(),len(raw),fault=fault)
            self.assertEqual(external.read_bytes(),raw);self.assertEqual(dest.read_bytes(),raw)
    def test_recheck_parent_code_alias_does_not_create_another_request_budget(self):
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            a=pool.enqueue(self.old('a'));b=pool.enqueue(self.old('b'))
            def recheck(parent,code):
                inputs={'recovery':{'parent_task_id':parent,'round':1,'release_date':DAY}}
                return task_spec('academic','aps-prl',COVER,inputs,{'code':{'version':code}})
            old=pool.enqueue(recheck(a,'a'),max_attempts=1)
            lease=pool.claim(task_id=old,now=1)
            pool.fail(old,lease['lease'],{'code':'request_interrupted','retryable':True},now=2)
            new=pool.enqueue_compatible(recheck(b,'b'),lambda s,v:[])
            self.assertEqual(pool.get(new)['max_attempts'],1)
            self.assertEqual(pool.get(new)['state'],'exhausted')
            self.assertIsNone(pool.claim(task_id=new,now=5000))
    def test_large_http_receipt_exact_wire_bytes_repeat_and_truncation(self):
        import base64
        from evidence_persistence import validate_public_http_receipt
        from test_source_preparation_flow import discovery_fixture
        from discovery_navigation import navigation_request
        value=discovery_fixture(navigation_request('reputable_media',COVER))['http_receipt']
        body=('<article>原始新闻 & Unicode\n'*12000+'</article>').encode('utf-8')
        value['body_base64']=base64.b64encode(body).decode('ascii');value['response_hash']=hashlib.sha256(body).hexdigest()
        raw=(json.dumps(value,ensure_ascii=False,indent=4)+'\n').encode('utf-8')
        self.assertGreater(len(raw),120000)
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);source=root/'public-receipt.json';source.write_bytes(raw)
            output=root/'news/_collection'/DAY/'receipt.json';digest=hashlib.sha256(raw).hexdigest()
            persist_public_evidence(source,output,root/'news',DAY,digest,len(raw),validator=validate_public_http_receipt)
            stamp=output.stat().st_mtime_ns
            persist_public_evidence(source,output,root/'news',DAY,digest,len(raw),validator=validate_public_http_receipt)
            self.assertEqual(output.read_bytes(),raw);self.assertEqual(output.stat().st_mtime_ns,stamp)
            saved=json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(base64.b64decode(saved['body_base64']),body)
            source.write_bytes(raw[:-1])
            with self.assertRaisesRegex(PoolConflict,'changed_or_truncated'):
                persist_public_evidence(source,output,root/'news',DAY,digest,len(raw),validator=validate_public_http_receipt)
            self.assertEqual(output.read_bytes(),raw)
    def test_two_actual_processes_share_one_alias_budget_and_lease(self):
        code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from source_pool import SourcePool;r=Path(sys.argv[2]);\nwhile not (r/'go').exists():time.sleep(.01)\nwith SourcePool(r/'pool.sqlite') as p:\n t=p.claim(task_id=sys.argv[3],now=2000);print('owned' if t else 'none')"
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with SourcePool(root/'pool.sqlite') as pool:
                a=pool.enqueue(self.old('a'));self.spend(pool,a)
                b=pool.enqueue_compatible(self.old('b'),lambda s,v:[])
            procs=[subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS),td,b],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(2)]
            try:
                (root/'go').write_text('go')
                results=[p.communicate(timeout=15) for p in procs]
                self.assertEqual([p.returncode for p in procs],[0,0],results)
                self.assertEqual(sorted(out.decode().strip() for out,err in results),['none','owned'])
                with SourcePool(root/'pool.sqlite') as pool:
                    self.assertEqual(pool.get(b)['attempts'],2)
                    self.assertIsNone(pool.claim(task_id=a,now=2001))
            finally:
                for child in procs:
                    if child.poll() is None:child.terminate();child.wait(timeout=5)
    def setup_recheck(self,pool):
        plan=w.plan_sources(pool,DAY)
        key=next(k for k in plan['tasks'] if pool.get(k)['spec']['source_id']=='aps-prx-dated')
        lease=pool.claim(task_id=key,now=1)
        pool.complete(key,lease['lease'],collect('aps-prx-dated',window=COVER),w.validate_result,now=2)
        now=datetime.fromisoformat(DAY+'T15:00:00+08:00').timestamp()
        policy={'version':1,'enabled':True,'timezone':'Asia/Shanghai','not_before':DAY+'T00:00:00+08:00',
                'deadline':DAY+'T23:59:00+08:00','minimum_interval_seconds':60,'max_recheck_tasks':1,'max_tasks_per_invocation':1}
        return plan,policy,now
    def test_actual_terminated_recheck_claim_stays_spent_after_expiry(self):
        code="import sys,time;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from source_pool import SourcePool;r=Path(sys.argv[2]);\nwith SourcePool(r/'pool.sqlite') as p:p.claim(task_id=sys.argv[3],now=float(sys.argv[4]));(r/'claimed').write_text('owned');time.sleep(30)"
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan,policy,now=self.setup_recheck(pool)
            with patch.object(w,'run_ready',return_value={'processed':[]}):r.recover(pool,plan,policy,now=now)
            key=r.recheck_tasks(pool,plan)[0]['task_id']
            child=subprocess.Popen([sys.executable,'-B','-c',code,str(SCRIPTS),td,key,str(now)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                until=time.monotonic()+10
                while not (Path(td)/'claimed').exists() and time.monotonic()<until:time.sleep(.02)
                self.assertTrue((Path(td)/'claimed').exists())
                child.terminate();child.wait(timeout=5)
                with patch.object(w,'execute_existing',side_effect=AssertionError('spent request must not restart')):
                    value=r.recover(pool,plan,policy,now=now+901)
                self.assertEqual(value['status'],'recovery_budget_consumed')
                self.assertEqual(pool.get(key)['state'],'exhausted');self.assertEqual(pool.get(key)['attempts'],1)
            finally:
                if child.poll() is None:child.terminate();child.wait(timeout=5)
    def test_interrupt_after_reservation_reenters_same_one_request(self):
        class Interrupted(BaseException):pass
        with tempfile.TemporaryDirectory() as td,SourcePool(Path(td)/'pool.sqlite') as pool:
            plan,policy,now=self.setup_recheck(pool);enqueue=pool.enqueue
            def interrupted(*a,**kw):enqueue(*a,**kw);raise Interrupted()
            with patch.object(pool,'enqueue',side_effect=interrupted):
                with self.assertRaises(Interrupted):r.recover(pool,plan,policy,now=now)
            calls=[]
            def execute(spec):calls.append(spec['source_id']);return collect(spec['source_id'],window=COVER)
            value=r.recover(pool,plan,policy,now=now+1,executor=execute)
            r.recover(pool,plan,policy,now=now+61,executor=execute)
            self.assertEqual(calls,['aps-prx-dated']);self.assertEqual(value['reserved_rechecks'],1)

import test_daily_recovery_trace as trace
class ReboundDailyTrace(unittest.TestCase):
    setUp=trace.RecoveryTraceTests.setUp
    prepare=trace.RecoveryTraceTests.prepare
    write_candidate=trace.RecoveryTraceTests.write_candidate
    stage=trace.RecoveryTraceTests.stage
    entry=trace.RecoveryTraceTests.entry
    initial=trace.RecoveryTraceTests.initial
    def test_actual_continue_consumes_pending_rechecks_after_code_update(self):
        self.initial()
        policy=json.loads(self.policy_path.read_text(encoding='utf-8'));policy['max_tasks_per_invocation']=1
        self.policy_path.write_text(json.dumps(policy),encoding='utf-8')
        calls=[]
        def execute(spec,unused):calls.append(spec['source_id']);return collect(spec['source_id'],window=COVER)
        with patch.object(w,'execute_existing',side_effect=execute):self.entry('recover',policy=True)
        self.assertEqual(len(calls),1)
        changed={**w.code_binding(),'r2_fixture':'changed'}
        with patch.object(w,'code_binding',return_value=changed),patch.object(w,'execute_existing',side_effect=execute):
            self.entry('continue',policy=True);self.entry('continue',policy=True)
            self.assertEqual(len(calls),3,self.trace)
            self.entry('continue',policy=True);self.assertEqual(len(calls),3)
        self.assertFalse((self.news/DAY).exists())
if __name__=='__main__':unittest.main()
