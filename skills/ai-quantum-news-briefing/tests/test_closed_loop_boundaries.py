"""Adversarial execution tests; semantic/browser/network results are synthetic."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import daily_closed_loop as c
import owned_process as owned
import daily_pipeline as dp
import test_daily_closed_loop as fixtures
policy,DAY,NOW=fixtures.policy,fixtures.DAY,fixtures.NOW


class DriverTests(fixtures.ClosedLoopTests):
    # Inherit helpers only; inherited test identities excluded below.
    def test_driver_consumes_retry_without_refunding_or_changing_day(self):
        self.backend.retry_at=NOW+2
        def sleep(seconds):
            self.now+=seconds
            if self.now>=NOW+2:self.backend.retry_at=None
        p=policy(driver_wait_seconds=20)
        result=c.drive(self.backend,DAY,p,policy_sha256='a'*64,clock=lambda:self.now,
                       monotonic=lambda:self.now,sleep=sleep)
        self.assertEqual(result['status'],'completed',result)
        self.assertEqual(self.backend.uploads,1)
        self.assertTrue(all(day==DAY for _,day in self.backend.actions))

    def test_driver_stops_at_host_bound_without_busy_loop_or_reset(self):
        self.backend.retry_at=NOW+3600
        sleeps=[]
        def sleep(seconds):sleeps.append(seconds);self.now+=seconds
        result=c.drive(self.backend,DAY,policy(driver_wait_seconds=65),policy_sha256='b'*64,
                       clock=lambda:self.now,monotonic=lambda:self.now,sleep=sleep)
        self.assertEqual(result['status'],'waiting')
        self.assertEqual(result['next_wakeup_at'],NOW+3600)
        self.assertEqual(sleeps,[30,30,5])
        self.assertFalse(self.backend.actions)

    def test_two_story_processes_are_reserved_before_any_blind_call(self):
        self.backend.phase='review_pending';self.backend.reviewed={'news_review'}
        # Journal approval for the existing news review; story needs two slots.
        self.backend.snapshot=lambda day:{'phase':'review_pending','identity':'x',
            'approved_review_roles':['news_review'],'independent_reviews':True}
        result=self.run_loop(max_agent_invocations=1)
        self.assertEqual(result['code'],'agent_budget_exhausted')
        self.assertFalse(self.backend.actions)

    def test_completed_remote_truth_is_visible_after_deadline_without_upload(self):
        self.backend.phase='workflow_complete';self.now=NOW+86400
        result=self.run_loop()
        self.assertEqual(result['status'],'completed')
        self.assertFalse(self.backend.actions)

    def test_policy_optional_bounds_reject_boolean_and_oversize(self):
        for kw in ({'driver_wait_seconds':True},{'driver_wait_seconds':86401},
                   {'max_tasks_per_batch':0},{'allow_preview':'yes'}):
            with self.subTest(kw=kw),self.assertRaises(ValueError):c.policy_bounds(policy(**kw),DAY)

    def test_existing_wait_does_not_hide_later_verified_release_after_deadline(self):
        self.backend.retry_at=NOW+3600;self.run_loop()
        self.backend.phase='workflow_complete';self.now=NOW+86400
        self.assertEqual(self.run_loop()['status'],'completed')
        self.assertFalse(self.backend.actions)

    def test_machine_error_code_is_retained_without_copying_arbitrary_exception(self):
        with patch.object(self.backend,'perform',side_effect=ValueError('blind_round_validation_failed')):
            result=self.run_loop()
        self.assertEqual(result['blocker']['cause_code'],'blind_round_validation_failed')

    def test_execution_journal_alone_cannot_certify_publication(self):
        self.assertEqual(self.run_loop()['status'],'completed')
        self.backend.phase='remote_pending';self.backend.uploads=0
        self.assertEqual(self.run_loop()['code'],'completion_no_longer_verified')
        self.assertEqual(self.backend.uploads,0)

    def test_corrupt_reservation_cannot_refund_agent_budget(self):
        self.run_loop(max_steps_per_invocation=1)
        path=self.root/'_automation/workflow_queue.json';queue=json.loads(path.read_text())
        queue['daily_continuations'][DAY]['closed_loop']['actions'][0]['agent_slots']=-10
        path.write_text(json.dumps(queue))
        with self.assertRaisesRegex(ValueError,'action_journal_invalid'):self.run_loop(max_steps_per_invocation=1)

    def test_reserved_story_pair_is_not_refunded_on_process_interruption(self):
        self.backend.phase='review_pending'
        self.backend.snapshot=lambda day:{'phase':'review_pending','identity':'x',
            'approved_review_roles':['news_review'],'independent_reviews':True}
        with patch.object(self.backend,'perform',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):self.run_loop(max_agent_invocations=2)
        self.assertEqual(c._load(self.root,DAY)['actions'][0]['agent_slots'],2)
        self.now+=901
        self.assertEqual(self.run_loop(max_agent_invocations=2)['code'],'agent_budget_exhausted')

    def test_two_real_controller_processes_compete_for_same_edition_lock(self):
        script='''import sys,time,json
from pathlib import Path
sys.path[:0]=[sys.argv[1],sys.argv[2]]
from test_daily_closed_loop import SimulatedBackend,policy,DAY,NOW
import daily_closed_loop as c
root=Path(sys.argv[3]);backend=SimulatedBackend(root)
original=backend.perform
def perform(*a,**k):
 (root.parent/'owner-ready').write_text('ready')
 time.sleep(.6)
 return original(*a,**k)
backend.perform=perform
result=c.execute(backend,DAY,policy(max_steps_per_invocation=1),policy_sha256='c'*64,clock=lambda:NOW)
print(json.dumps(result))
'''
        args=[sys.executable,'-B','-c',script,str(Path(c.__file__).parent),str(Path(__file__).parent),str(self.root)]
        first=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            end=time.monotonic()+5
            while not (self.root.parent/'owner-ready').exists() and time.monotonic()<end:time.sleep(.02)
            self.assertTrue((self.root.parent/'owner-ready').exists())
            second=subprocess.run(args,capture_output=True,timeout=5,check=True)
            # The second worker cannot enter perform or reserve an action.
            self.assertEqual(json.loads(second.stdout)['code'],'edition_owner_active')
            output,errors=first.communicate(timeout=5)
            self.assertEqual(first.returncode,0,errors)
            self.assertEqual(json.loads(output)['actions_used'],1)
            self.assertEqual(len(c._load(self.root,DAY)['actions']),1)
        finally:
            if first.poll() is None:first.terminate();first.wait(timeout=5)


# unittest inheritance is only for setup/helpers, not duplicate coverage counts.
for _name in tuple(vars(fixtures.ClosedLoopTests)):
    if _name.startswith('test_') and _name not in DriverTests.__dict__:setattr(DriverTests,_name,None)


class ReviewBoundaryTests(fixtures.NativeLifecycleTests):
    def test_display_cannot_clear_semantic_failure_before_browser_or_preview(self):
        stage,manifest=self.prepared_stage();proposals=self.synthetic_reviews(stage,manifest)
        dp.cmd_review_template(type('A',(),{'run_dir':str(stage)})())
        for role,name in [('news_review','news_content_review'),('story_review','opening_story_review')]:
            value=proposals[role]
            if role=='story_review':value['rounds'][1]['unresolved']=['unsupported mapping']
            (stage/(name+'_'+DAY+'.json')).write_text(json.dumps(value),encoding='utf-8')
        backend=c.Backend(__import__('orchestrate_daily'))
        before=(stage/('opening_story_review_'+DAY+'.json')).read_bytes()
        with patch.object(c,'run_agent',side_effect=AssertionError('no browser before semantics')),\
             patch('publish_daily_to_oss.preview',side_effect=AssertionError('no upload')):
            result=backend.review('display_review',DAY,backend.snapshot(DAY),policy(),30)
        self.assertEqual(result['code'],'pre_display_content_gate_failed')
        self.assertEqual(before,(stage/('opening_story_review_'+DAY+'.json')).read_bytes())

    def test_blind_packet_contains_only_story_and_fresh_neutral_cwd(self):
        packets=[];commands=[]
        def process(argv,**kw):
            packet=json.loads(next(line for line in kw['input'].decode().splitlines() if line.startswith('{')))
            packets.append(packet);commands.append(argv)
            Path(argv[argv.index('--output-last-message')+1]).write_text(json.dumps({
                **{k:packet[k] for k in ('job_id','date','input_sha256')},'status':'blocked','code':'test_only','review_json':'{}'}))
            return subprocess.CompletedProcess(argv,0)
        with tempfile.TemporaryDirectory() as base,patch.object(c,'run_owned',side_effect=process):
            root=Path(base)/'news'
            c.run_agent(root,DAY,'story_blind',{'identity':'a'*64,'stage':'secret-path','candidate':'secret',
                'blind_story':{'title':'story','paragraphs':['literal narrative']}},policy(),30)
        self.assertEqual(set(packets[0]),{'version','job_id','date','role','input_sha256','story','blind_review_contract'})
        contract=packets[0]['blind_review_contract']
        self.assertEqual(contract['id'],'story-completeness')
        self.assertEqual(contract['judgment'],'pending')
        self.assertEqual(contract['materials_seen'],['title','paragraphs'])
        self.assertNotIn('task_card',contract)
        self.assertNotIn('technical_edges',contract)
        self.assertEqual(set(packets[0]['story']),{'title','paragraphs'})
        self.assertNotEqual(Path(commands[0][commands[0].index('--cd')+1]),root.parent)
        self.assertEqual(commands[0][commands[0].index('--sandbox')+1],'read-only')

    def test_local_only_and_require_remote_conflict_precedes_commit(self):
        with patch.object(dp,'_commit_local',side_effect=AssertionError('no commit')):
            with self.assertRaisesRegex(ValueError,'incompatible'):
                dp.cmd_finalize(type('A',(),{'local_only':True,'require_remote':True})())

    def test_real_observed_wrong_blind_json_types_fail_closed(self):
        wrong={'materials_seen':{'title':'story','paragraphs':['text']},
               'judgment':{'overall_pass':False},'literal_state_trace':[]}
        with self.assertRaisesRegex(ValueError,'blind_round_invalid'):
            c.validate_blind({'title':'story','paragraphs':['text']},wrong)

    def test_real_negative_blind_review_is_not_converted_to_pass(self):
        stage,manifest=self.prepared_stage();proposal=self.synthetic_reviews(stage,manifest)['story_blind']
        proposal['judgment']='fail';proposal['unresolved']=['unclosed causal outcome']
        raw=json.loads((stage/json.loads(manifest.read_text(encoding='utf-8'))['artifacts']['delta_config']).read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'blind_round_validation_failed'):
            c.validate_blind(raw['opening_story'],proposal)
        self.assertEqual(proposal['judgment'],'fail')
        self.assertEqual(proposal['unresolved'],['unclosed causal outcome'])

    def test_real_observed_composite_quote_is_rejected_without_rewriting(self):
        stage,manifest=self.prepared_stage();proposal=self.synthetic_reviews(stage,manifest)['story_blind']
        raw=json.loads((stage/json.loads(manifest.read_text(encoding='utf-8'))['artifacts']['delta_config']).read_text(encoding='utf-8'))
        proposal['reviewed_text']='Key narrative:\n'+proposal['reviewed_text']+'\nAdditional quoted fragment'
        before=copy.deepcopy(proposal)
        with self.assertRaisesRegex(ValueError,'blind_round_validation_failed'):
            c.validate_blind(raw['opening_story'],proposal)
        self.assertEqual(proposal,before)
        self.assertIn('ONE contiguous verbatim excerpt',c.worker_prompt({'role':'story_blind'}))

    def test_existing_fully_bound_independent_typed_reviews_are_reused(self):
        stage,manifest=self.prepared_stage();proposals=self.synthetic_reviews(stage,manifest)
        for role,name in [('news_review','news_content_review'),('display_review','opening_story_review')]:
            (stage/(name+'_'+DAY+'.json')).write_text(json.dumps(proposals[role]),encoding='utf-8')
        backend=c.Backend(__import__('orchestrate_daily'));snapshot=backend.snapshot(DAY)
        self.assertEqual(snapshot['approved_review_roles'],list(c.REVIEW_ROLES))
        self.assertEqual(c.choose(snapshot,{'actions':[]},policy()),'seal')

    def test_review_proposal_conflict_preserves_external_edit(self):
        stage,manifest=self.prepared_stage();proposals=self.synthetic_reviews(stage,manifest)
        dp.cmd_review_template(type('A',(),{'run_dir':str(stage)})())
        path=stage/('news_content_review_'+DAY+'.json')
        def concurrent(*args):
            value=json.loads(path.read_text());value['review_method']='self';value['external_note']='user edit'
            path.write_text(json.dumps(value));return {'status':'completed','review':proposals['news_review']}
        backend=c.Backend(__import__('orchestrate_daily'))
        with patch.object(c,'run_agent',side_effect=concurrent),self.assertRaisesRegex(ValueError,'authoring_conflict'):
            backend.review('news_review',DAY,backend.snapshot(DAY),policy(),30)
        self.assertEqual(json.loads(path.read_text())['external_note'],'user edit')

for _name in tuple(vars(fixtures.NativeLifecycleTests)):
    if _name.startswith('test_') and _name not in ReviewBoundaryTests.__dict__:setattr(ReviewBoundaryTests,_name,None)


class OwnedProcessTests(unittest.TestCase):
    @unittest.skipUnless(os.name=='nt','Windows Job accounting')
    def test_unknown_job_quiescence_cannot_be_reported_as_clean(self):
        job=owned.WindowsJob()
        query=job.k.QueryInformationJobObject
        def fail_accounting(*args):return False if args[1]==1 else query(*args)
        with patch.object(job.k,'QueryInformationJobObject',side_effect=fail_accounting):
            with self.assertRaisesRegex(owned.OwnedProcessError,'quiescence_unconfirmed'):job.close()
        self.assertIsNone(job.handle)

    def test_quick_exit_output_is_bounded(self):
        with tempfile.TemporaryFile() as output:
            with self.assertRaisesRegex(owned.OwnedProcessError,'output_limit'):
                owned.run_owned([sys.executable,'-B','-c','print("x"*50000)'],input=b'',stdout=output,
                    stderr=output,timeout=5,output_limit=100)

    def test_timeout_terminates_real_owned_parent_and_grandchild(self):
        # Real processes, not a simulated timeout. Not a power-loss test.
        with tempfile.TemporaryDirectory() as base,tempfile.TemporaryFile() as output:
            marker=Path(base)/'grandchild-alive.txt'
            child='import pathlib,time; p=pathlib.Path('+repr(str(marker))+');\nwhile True: p.write_text(str(time.time()));time.sleep(.03)'
            parent='import subprocess,sys,time; subprocess.Popen([sys.executable,"-B","-c",'+repr(child)+']);time.sleep(20)'
            with self.assertRaises(subprocess.TimeoutExpired):
                owned.run_owned([sys.executable,'-B','-c',parent],input=b'',stdout=output,stderr=output,timeout=1)
            self.assertTrue(marker.exists(),'grandchild must actually have run')
            before=marker.read_bytes();time.sleep(.2)
            self.assertEqual(before,marker.read_bytes(),'owned grandchild must no longer write')

    @unittest.skipUnless(os.name=='nt','Windows Job guard')
    def test_job_assignment_denial_does_not_run_suspended_child(self):
        with tempfile.TemporaryDirectory() as base,tempfile.TemporaryFile() as output:
            marker=Path(base)/'must-not-exist'
            with patch.object(owned.WindowsJob,'start',side_effect=owned.OwnedProcessError('owned_job_assignment_denied')):
                with self.assertRaisesRegex(owned.OwnedProcessError,'assignment_denied'):
                    owned.run_owned([sys.executable,'-B','-c','from pathlib import Path;Path('+repr(str(marker))+').write_text("ran")'],
                        input=b'',stdout=output,stderr=output,timeout=1)
            self.assertFalse(marker.exists())

if __name__=='__main__':unittest.main()
