"""Scoped environment recovery; synthetic work only, no real sources/models."""
import copy,json
from pathlib import Path
import subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_closed_loop as c
from source_pool import fingerprint,PoolConflict,SourcePool,task_spec
import source_worker as worker
import orchestrate_daily as orchestration
from test_daily_closed_loop import policy,DAY,NOW


class LaneTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'news';self.now=NOW;self.actions=[]
        self.rows=[{'task_id':'browser','kind':'discovery','state':'pending'}]
        self.failure='browser_initialization_timeout'
        self.backend=type('Backend',(),{})();self.backend.root=self.root
        self.backend.snapshot=self.snapshot;self.backend.perform=self.perform
    def snapshot(self,day):
        return {'phase':'source_and_authoring_pending','identity':fingerprint(self.rows),
                'source':{'status':'coverage_pending','missing_tasks':copy.deepcopy(self.rows)}}
    def perform(self,action,day,snapshot,p,timeout):
        self.actions.append(action)
        if action=='discovery':return {'status':'blocked','code':self.failure}
        self.rows=[r for r in self.rows if not c.task_due(r,self.now) or r['kind']=='discovery']
        return {'status':'completed'}
    def run_loop(self,**kw):
        p=policy(**kw)
        return c.execute(self.backend,DAY,p,policy_sha256=fingerprint(p),clock=lambda:self.now)
    def failed_action(self,when=NOW):
        return {'action':'discovery','code':'browser_initialization_timeout','finished_at':when}
    def test_due_deterministic_peer_precedes_browser_even_after_failure(self):
        self.rows.append({'kind':'academic','state':'pending'})
        result=self.run_loop()
        self.assertEqual(self.actions,['work','discovery']);self.assertEqual(result['status'],'waiting')
        self.assertEqual(result['next_wakeup_at'],NOW+300)
        self.assertEqual(result['scoped_blockers']['browser_discovery']['code'],self.failure)
    def test_failed_browser_is_waiting_not_global_terminal(self):
        result=self.run_loop()
        self.assertEqual((result['status'],result['code']),('waiting','browser_runtime_retry_after'))
        self.assertEqual(result['notification_status'],'not_required')
    def test_repeat_before_due_does_not_launch_or_refund(self):
        self.run_loop();first=c._load(self.root,DAY)
        self.run_loop();second=c._load(self.root,DAY)
        self.assertEqual(self.actions,['discovery']);self.assertEqual(len(first['actions']),len(second['actions']))
        self.assertEqual(sum(a['agent_slots'] for a in second['actions']),1)
    def test_recovery_due_uses_one_more_slot_and_then_stops(self):
        self.run_loop();self.now+=300;result=self.run_loop()
        self.assertEqual(result['code'],'browser_recovery_exhausted');self.assertEqual(self.actions,['discovery']*2)
        self.assertEqual(sum(a['agent_slots'] for a in c._load(self.root,DAY)['actions']),2)
        self.run_loop();self.assertEqual(len(self.actions),2)
    def test_permission_denial_is_never_classified_as_recoverable_timeout(self):
        self.failure='policy_rejected';result=self.run_loop()
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['code'],'policy_rejected')
        self.assertIsNone(result['next_wakeup_at']);self.assertEqual(self.actions,['discovery'])
    def test_unknown_agent_timeout_is_not_assumed_to_be_browser_failure(self):
        self.failure='agent_timeout_outcome_uncertain';result=self.run_loop()
        self.assertEqual(result['status'],'blocked');self.assertNotIn('browser_discovery',result['scoped_blockers'])
    def test_future_network_peer_does_not_starve_due_browser(self):
        self.rows.append({'kind':'academic','state':'retry_wait','retry_at':NOW+1000})
        self.run_loop();self.assertEqual(self.actions,['discovery'])
    def test_browser_exhaustion_waits_for_future_independent_peer(self):
        self.run_loop();self.now+=300
        self.rows.append({'kind':'academic','state':'retry_wait','retry_at':self.now+600})
        result=self.run_loop();self.assertEqual(result['status'],'waiting')
        self.assertEqual(result['next_wakeup_at'],self.now+600)
        self.now+=600;result=self.run_loop()
        self.assertEqual(self.actions,['discovery','discovery','work']);self.assertEqual(result['code'],'browser_recovery_exhausted')
    def test_exhausted_browser_does_not_permanently_block_new_due_independent_work(self):
        self.run_loop();self.now+=300;self.run_loop()
        self.rows.append({'kind':'fixed_source','state':'pending'})
        result=self.run_loop()
        self.assertEqual(self.actions,['discovery','discovery','work']);self.assertEqual(result['code'],'browser_recovery_exhausted')
    def test_agent_budget_is_not_refunded_by_environment_recovery(self):
        self.run_loop(max_agent_invocations=1);self.now+=300
        result=self.run_loop(max_agent_invocations=1)
        self.assertEqual(result['code'],'agent_budget_exhausted');self.assertEqual(self.actions,['discovery'])
    def test_exhausted_agent_budget_waits_for_future_non_model_work(self):
        self.run_loop(max_agent_invocations=1);self.now+=300
        self.rows.append({'kind':'academic','state':'retry_wait','retry_at':self.now+600})
        result=self.run_loop(max_agent_invocations=1)
        self.assertEqual(result['status'],'waiting');self.assertEqual(result['next_wakeup_at'],self.now+600)
        self.now+=600;self.run_loop(max_agent_invocations=1)
        self.assertEqual(self.actions,['discovery','work'])
        self.assertEqual(sum(a['agent_slots'] for a in c._load(self.root,DAY)['actions']),1)
    def test_new_due_work_can_resume_after_scoped_agent_budget_stop(self):
        self.run_loop(max_agent_invocations=1);self.now+=300;self.run_loop(max_agent_invocations=1)
        self.rows.append({'kind':'fixed_source','state':'pending'})
        self.run_loop(max_agent_invocations=1)
        self.assertEqual(self.actions,['discovery','work'])
    def test_retry_beyond_deadline_does_not_schedule_later_date(self):
        self.now=__import__('datetime').datetime.fromisoformat(DAY+'T17:59:00+08:00').timestamp()
        result=self.run_loop()
        self.assertEqual(result['status'],'expired');self.assertIsNone(result['next_wakeup_at'])
        self.assertEqual(result['date'],DAY)
    def test_corrupt_browser_timing_cannot_restart_budget(self):
        state={'actions':[self.failed_action('unknown')]}
        with self.assertRaisesRegex(PoolConflict,'browser_recovery_journal_invalid'):
            c.choose(self.snapshot(DAY),state,policy(),now=NOW)
    def test_invalid_recovery_policy_bounds_are_rejected(self):
        for kw in ({'browser_recovery_attempts':True},{'browser_recovery_attempts':4},
                   {'browser_recovery_delay_seconds':0},{'browser_recovery_delay_seconds':1801}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):c.policy_bounds(policy(**kw),DAY)
    def test_live_source_lease_does_not_spin_or_claim_another_date(self):
        self.rows=[{'kind':'academic','state':'running','retry_at':NOW+600}]
        result=self.run_loop()
        self.assertEqual(result['status'],'waiting');self.assertEqual(result['next_wakeup_at'],NOW+600)
        self.assertEqual(self.actions,[])
    def test_unknown_lease_timing_fails_closed(self):
        self.rows=[{'kind':'academic','state':'running'}]
        self.assertEqual(self.run_loop()['code'],'source_retry_timing_unavailable')
        self.assertEqual(self.actions,[])
    def test_pending_non_browser_is_drained_in_bounded_batches(self):
        self.rows+=[{'kind':'academic','state':'pending','task_id':str(i)} for i in range(24)]
        def batch(action,day,snapshot,p,timeout):
            if action=='discovery':return self.perform(action,day,snapshot,p,timeout)
            self.actions.append(action);remaining=4
            for r in list(self.rows):
                if r['kind']!='discovery' and remaining:self.rows.remove(r);remaining-=1
            return {'status':'completed'}
        self.backend.perform=batch;result=self.run_loop()
        self.assertEqual(self.actions,['work']*6+['discovery']);self.assertEqual(result['status'],'waiting')
        self.assertFalse(any(r['kind']!='discovery' for r in self.rows))
    def test_shortage_drains_registered_pool_before_requesting_expansion(self):
        snap={'phase':'candidate_shortage','recovery_exhausted':True,'source':{'missing_tasks':[{'kind':'academic','state':'pending'}]}}
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'work')
        snap['source']['missing_tasks'][0].update(state='retry_wait',retry_at=NOW+600)
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'source_wait')
        snap['source']['missing_tasks']=[]
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'shortage')
    def test_due_capture_uses_existing_worker_before_another_model(self):
        snap={'phase':'article_qualification_pending','source':{'missing_tasks':[{'kind':'capture','state':'pending'}]}}
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'work')
        snap['source']['missing_tasks'][0].update(state='retry_wait',retry_at=NOW+600)
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'source_wait')


class MappingPacketTests(unittest.TestCase):
    def test_node_launcher_keeps_model_flag_after_exec(self):
        seen=[];p=policy(codex_model='gpt-6-astra');p['codex_argv']=[sys.executable,'launcher.js']
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'run_owned',side_effect=lambda argv,**kw:(seen.append(argv) or subprocess.CompletedProcess(argv,1))):
            c.run_agent(Path(temp)/'news',DAY,'author',{'identity':'a'*64},p,120)
        self.assertEqual(seen[0][2:5],['exec','--model','gpt-6-astra'])
    def test_model_identity_is_bound_without_shell_or_sandbox_changes(self):
        seen=[]
        def process(argv,**kw):seen.append(argv);return subprocess.CompletedProcess(argv,1)
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'run_owned',side_effect=process):
            c.run_agent(Path(temp)/'news',DAY,'author',{'identity':'a'*64},policy(codex_model='gpt-6-astra'),120)
        self.assertEqual(seen[0][seen[0].index('--model')+1],'gpt-6-astra')
        self.assertEqual(seen[0][seen[0].index('--sandbox')+1],'workspace-write')
    def test_unsafe_model_identity_is_rejected_before_process(self):
        with self.assertRaises(ValueError):c.policy_bounds(policy(codex_model='gpt; command'),DAY)
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'run_owned',side_effect=AssertionError('no process')):
            value=c.run_agent(Path(temp)/'news',DAY,'author',{'identity':'a'*64},policy(codex_model='bad --flag'),120)
        self.assertEqual(value['code'],'closed_loop_model_identity_invalid')
    def test_absent_model_identity_preserves_existing_default(self):
        seen=[]
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'run_owned',side_effect=lambda argv,**kw:(seen.append(argv) or subprocess.CompletedProcess(argv,1))):
            c.run_agent(Path(temp)/'news',DAY,'author',{'identity':'a'*64},policy(),120)
        self.assertNotIn('--model',seen[0])
    def test_accepted_blind_round_is_single_copy_and_inputs_are_not_mutated(self):
        first={'id':'story-completeness','reviewed_text':'exact original quote'}
        template={'rounds':[first,{'id':'semantic-and-source','unresolved':[]}]};before=copy.deepcopy(template)
        captured=[]
        def process(argv,**kw):
            packet=json.loads(next(l for l in kw['input'].decode().splitlines() if l.startswith('{')));captured.append(packet)
            return subprocess.CompletedProcess(argv,1)
        with tempfile.TemporaryDirectory() as temp,patch.object(c,'run_owned',side_effect=process):
            c.run_agent(Path(temp)/'news',DAY,'story_review',{'identity':'a'*64,'review_template':template,'blind_round':first},policy(),120)
        self.assertEqual(template,before);self.assertEqual(captured[0]['blind_round'],first)
        self.assertNotIn('story-completeness',[r['id'] for r in captured[0]['review_template']['rounds']])
        self.assertNotIn('Read AGENTS.md, .agents/AGENTS.md, PROJECT_CONTEXT.md',c.worker_prompt(captured[0]))


class WorkerViewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.pool=SourcePool(Path(self.temp.name)/'pool.sqlite');self.addCleanup(self.pool.close)
        self.coverage='2026-10-17'
    def fixed(self,source):
        return self.pool.enqueue(task_spec('fixed_source',source,self.coverage,{}, {'code':worker.code_binding()}))
    def complete(self,key,count=0):
        lease=self.pool.claim(task_id=key,now=NOW)
        value={'candidates':[{'published_at':self.coverage+'T12:00:00+08:00'} for _ in range(count)]}
        self.pool.complete(key,lease['lease'],value,lambda *a:[],now=NOW)
    def reason(self,key):
        return worker.work_eligibility(self.pool,self.pool.get(key),self.pool.tasks(),now=NOW)
    def test_backup_waits_for_primary_and_real_worker_uses_same_rule(self):
        self.fixed('techcrunch-ai');self.fixed('ars-ai');backup=self.fixed('verge-ai')
        self.assertEqual(self.reason(backup),'backup_waits_for_primary')
        with patch.object(worker,'execute_existing',side_effect=AssertionError('no backup request')):
            result=worker.run_ready(self.pool,coverage_date=self.coverage,task_ids={backup},clock=lambda:NOW)
        self.assertEqual(result['processed'],[]);self.assertEqual(self.pool.get(backup)['attempts'],0)
    def test_unneeded_backup_does_not_stall_authoring_or_browser(self):
        a=self.fixed('techcrunch-ai');b=self.fixed('ars-ai');backup=self.fixed('verge-ai')
        self.complete(a,3);self.complete(b,3)
        self.assertEqual(self.reason(backup),'backup_not_required')
        row={'kind':'fixed_source','state':'pending','work_eligible':False,'work_eligibility_reason':self.reason(backup)}
        snap={'phase':'authoring_pending','source':{'missing_tasks':[row]}}
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'author')
        snap['source']['missing_tasks'].append({'kind':'discovery','state':'pending'})
        self.assertEqual(c.choose(snap,{'actions':[]},policy(),now=NOW),'discovery')
    def test_backup_can_run_when_primary_is_rate_limited(self):
        a=self.fixed('techcrunch-ai');b=self.fixed('ars-ai');backup=self.fixed('verge-ai')
        lease=self.pool.claim(task_id=a,now=NOW)
        self.pool.fail(a,lease['lease'],{'code':'rate_limited','retryable':True,'http_status':429,'retry_after_seconds':600},now=lambda:NOW)
        self.complete(b)
        self.assertIsNone(self.reason(backup));self.assertEqual(self.reason(a),'retry_after')
    def test_old_pending_code_binding_cannot_block_current_successful_primary(self):
        old=self.pool.enqueue(task_spec('fixed_source','techcrunch-ai',self.coverage,{}, {'code':{'old':'binding'}}))
        a=self.fixed('techcrunch-ai');b=self.fixed('ars-ai');backup=self.fixed('verge-ai')
        self.complete(a,3);self.complete(b,3)
        self.assertEqual(self.reason(backup),'backup_not_required')
        self.assertEqual(self.pool.get(old)['state'],'pending');self.assertEqual(self.pool.get(old)['attempts'],0)
    def test_denied_original_host_remains_excluded_but_peer_is_eligible(self):
        def capture(host,identity):
            return self.pool.enqueue(task_spec('capture',host,self.coverage,{'item':{'id':identity,'source_url':'https://'+host+'/original','ai_source_provenance':{'fixture':True}}},{'code':worker.code_binding()}))
        old=capture('example.org','old');lease=self.pool.claim(task_id=old,now=NOW)
        self.pool.fail(old,lease['lease'],{'code':'http_denied','retryable':False,'http_status':403},now=lambda:NOW)
        same=capture('example.org','new');peer=capture('example.net','peer')
        self.assertEqual(self.reason(same),'same_ai_original_host_access_denied')
        self.assertIsNone(self.reason(peer));self.assertEqual(self.pool.get(same)['attempts'],0)
    def test_capture_view_is_current_date_and_code_bound(self):
        plan=worker.plan_sources(self.pool,DAY)
        config=plan['binding']
        current=self.pool.enqueue(task_spec('capture','fixture',self.coverage,{'item':{'id':'current'}},config))
        self.pool.enqueue(task_spec('capture','fixture','2026-10-16',{'item':{'id':'old-day'}},config))
        stale=self.pool.enqueue(task_spec('capture','fixture',self.coverage,{'item':{'id':'old-code'}},{**config,'code':{'old':'binding'}}))
        snapshot=worker.source_snapshot(self.pool,plan)
        captures=[r for r in snapshot['missing_tasks'] if r.get('kind')=='capture']
        self.assertEqual([r['task_id'] for r in captures],[current]);self.assertTrue(captures[0]['work_eligible'])
        self.assertEqual(self.pool.get(stale)['attempts'],0)


class StartBoundaryTests(unittest.TestCase):
    def test_original_recovery_policy_arguments_are_not_dropped_or_rebound(self):
        start=__import__('datetime').datetime.fromisoformat(DAY+'T01:00:00+08:00').timestamp()
        with patch.object(orchestration,'_daily_start_now',return_value=start-1):
            result=orchestration._owned_daily_attempt(DAY,action='recover',record=True,max_tasks=4,
                recovery_policy={'version':1,'enabled':True},recovery_policy_path='approved-policy.json')
        self.assertEqual(result['next_commands'],[]);self.assertTrue(result['resume_requires_original_approved_arguments'])
    def test_exact_0100_can_enter_existing_owner_protocol(self):
        start=__import__('datetime').datetime.fromisoformat(DAY+'T01:00:00+08:00').timestamp()
        with patch.object(orchestration,'_daily_start_now',return_value=start),patch.object(orchestration,'workflow_queue',return_value={'run_outcome':'pending'}),\
             patch.object(orchestration,'_daily_execution',return_value={'phase':'fixture','run_outcome':'pending'}) as execute,\
             patch('daily_continuation.begin',return_value='a'*32),patch('daily_continuation.finish',return_value={}):
            result=orchestration._owned_daily_attempt(DAY,action='work',record=True,max_tasks=4,recovery_policy=None,recovery_policy_path=None)
        self.assertEqual(result['phase'],'fixture');self.assertEqual(execute.call_count,1)
    def test_ordinary_entry_waits_without_collection_or_queue_mutation_before_0100(self):
        start=__import__('datetime').datetime.fromisoformat(DAY+'T01:00:00+08:00').timestamp()
        with patch.object(orchestration,'_daily_start_now',return_value=start-147),patch.object(orchestration,'_daily_execution',side_effect=AssertionError('no collection')),\
             patch('daily_continuation.begin',side_effect=AssertionError('no lease mutation')):
            result=orchestration._owned_daily_attempt(DAY,action='work',record=True,max_tasks=4,recovery_policy=None,recovery_policy_path=None)
        self.assertEqual(result['code'],'before_0100');self.assertEqual(result['next_wakeup_at'],start)
        self.assertEqual(result['date'],DAY);self.assertFalse(result['publication_approved'])


if __name__=='__main__':unittest.main()
