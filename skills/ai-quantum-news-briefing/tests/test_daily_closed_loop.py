"""Execution protocol fault injection only; no real sources/reviews/browser/OSS."""
import copy
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import daily_closed_loop as c
import orchestrate_daily as o
import daily_pipeline as dp
import publish_daily_to_oss as publisher
import test_publication_v4 as v4
import test_release_protocol as reviewed
from types import SimpleNamespace
from source_pool import fingerprint

DAY = '2026-10-18'
NOW = datetime.fromisoformat(DAY + 'T02:00:00+08:00').timestamp()


def policy(**kw):
    return {'version': 1, 'enabled': True, 'timezone': 'Asia/Shanghai', 'start_time': '01:00',
            'deadline_time': '18:00', 'max_actions': 32, 'max_agent_invocations': 12,
            'max_steps_per_invocation': 32, 'no_progress_limit': 2, 'agent_timeout_seconds': 600,
            'allow_publish': True, 'codex_argv': [sys.executable], **kw}


class SimulatedBackend:
    def __init__(self, root, phase='source_and_authoring_pending'):
        self.root = root
        self.phase = phase
        self.actions = []
        self.reviewed = set()
        self.generation = 0
        self.uploads = 0
        self.retry_at = None
        self.shortage = False
        self.fail = None
        self.ack_loss = False
        self.stall = False
        self.review_tamper = False

    def snapshot(self, day):
        source = {'status': 'not_initialized' if self.generation == 0 else 'coverage_pending' if self.generation == 1 else 'coverage_ready',
                  'missing_tasks': [{'kind':'academic','state':'pending'}] if self.generation == 1 else []}
        return {'phase': self.phase, 'identity': str(self.generation), 'source': source,
                'independent_reviews': {'news_review','story_review'} <= self.reviewed,
                'retry_at': self.retry_at, 'recovery_exhausted': self.shortage}

    def perform(self, action, day, snapshot, policy, timeout):
        self.actions.append((action, day))
        if action == self.fail:
            return {'status': 'blocked', 'code': action + '_real_gate_failed'}
        if self.stall:
            return {'status': 'completed'}
        if action in c.REVIEW_ROLES:
            self.reviewed.add(action)
            if self.review_tamper:
                self.generation += 1
        else:
            self.generation += 1
            phases = {'plan':'source_and_authoring_pending', 'work':'article_qualification_pending',
                      'qualification':'authoring_pending', 'author':'candidate_ready', 'stage':'review_pending',
                      'seal':'ready_to_finalize', 'finalize':'remote_pending', 'publish':'remote_pending',
                      'online':'workflow_complete' if self.uploads else 'remote_pending'}
            self.phase = phases.get(action, self.phase)
        if action == 'online':
            # Online inspection does not change the local release identity.
            self.generation -= 1
            return {'status':'completed', 'remote_status':'verified' if self.uploads else 'mismatch'}
        if action == 'seal':
            self.generation -= 1  # manifest review bindings do not change content_digest
        if action == 'publish':
            self.uploads += 1
            if self.ack_loss:
                return {'status':'retry_wait', 'code':'upload_outcome_uncertain','retry_at':NOW+3600}
        return {'status': 'completed'}


class ClosedLoopTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'news'
        self.backend = SimulatedBackend(self.root)
        self.now = NOW

    def run_loop(self, **kw):
        p = policy(**kw)
        return c.execute(self.backend, DAY, p, policy_sha256=fingerprint(p), clock=lambda:self.now)

    def test_all_stage_success_requires_actual_adapter_transitions_then_repeat_is_noop(self):
        result = self.run_loop()
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual([a[0] for a in self.backend.actions], ['plan','work','qualification','author','stage',
                         'news_review','story_review','display_review','seal','finalize','online','publish','online'])
        self.assertEqual(self.backend.uploads, 1)
        actions = list(self.backend.actions)
        self.assertEqual(self.run_loop()['status'], 'completed')
        self.assertEqual(self.backend.actions, actions)
        self.assertTrue(all(d == DAY for _,d in actions))

    def test_source_coverage_and_shortage_never_become_content_or_publish(self):
        self.backend.phase = 'candidate_shortage'
        self.backend.shortage = True
        result = self.run_loop()
        self.assertEqual((result['status'],result['code']), ('blocked','shortage'))
        self.assertFalse(self.backend.actions)
        queue = json.loads((self.root/'_automation/workflow_queue.json').read_text())
        rows = list(queue['notification_outbox'].values())
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'pending_send')
        self.run_loop()
        self.assertEqual(len(json.loads((self.root/'_automation/workflow_queue.json').read_text())['notification_outbox']),1)

    def test_review_failure_never_seals_finalizes_or_publishes(self):
        self.backend.fail = 'story_review'
        result = self.run_loop()
        self.assertEqual(result['code'],'story_review_real_gate_failed')
        actions = [a[0] for a in self.backend.actions]
        self.assertNotIn('seal',actions)
        self.assertNotIn('finalize',actions)
        self.assertEqual(self.backend.uploads,0)

    def test_exit_zero_without_changed_evidence_stops_bounded(self):
        self.backend.stall = True
        result = self.run_loop()
        self.assertEqual(result['code'],'no_verified_progress')
        self.assertEqual(len(self.backend.actions),2)

    def test_review_worker_cannot_change_the_content_it_approves(self):
        self.backend.phase = 'review_pending'
        self.backend.review_tamper = True
        self.assertEqual(self.run_loop()['code'],'review_worker_changed_content')
        self.assertEqual(self.backend.uploads,0)

    def test_uncertain_upload_is_reconciled_before_any_second_write(self):
        self.backend.phase = 'remote_pending'
        self.backend.ack_loss = True
        result = self.run_loop()
        self.assertEqual(result['status'],'waiting')
        self.assertEqual(self.backend.uploads,1)
        self.now += 3601
        self.assertEqual(self.run_loop()['status'],'completed')
        self.assertEqual([a[0] for a in self.backend.actions],['online','publish','online'])
        self.assertEqual(self.backend.uploads,1)

    def test_retry_after_and_cross_midnight_keep_frozen_edition(self):
        self.backend.retry_at = NOW+3600
        result = self.run_loop()
        self.assertEqual(result['status'],'waiting')
        self.assertFalse(self.backend.actions)
        self.now = datetime.fromisoformat('2026-10-19T00:01:00+08:00').timestamp()
        result = self.run_loop()
        self.assertEqual(result['status'],'expired')
        self.assertEqual(result['coverage_date'],'2026-10-17')
        self.assertEqual(result['date'],DAY)
        self.assertFalse(self.backend.actions)

    def test_early_wakeup_cannot_start_before_0100(self):
        self.now = datetime.fromisoformat(DAY+'T00:55:05+08:00').timestamp()
        result = self.run_loop()
        self.assertEqual(result['code'],'before_0100')
        self.assertEqual(result['next_wakeup_at'],datetime.fromisoformat(DAY+'T01:00:00+08:00').timestamp())
        self.assertFalse(self.backend.actions)

    def test_crash_after_reservation_preserves_budget_and_does_not_repeat_completed_upload(self):
        self.backend.phase = 'remote_pending'
        def crash(action, day, snapshot, p, timeout):
            self.backend.uploads += 1
            raise KeyboardInterrupt()
        with patch.object(self.backend,'perform',side_effect=crash):
            with self.assertRaises(KeyboardInterrupt):self.run_loop()
        # Reservation survives, not refunded. The next call starts from fresh
        # remote truth; it cannot treat an interrupted operation as success.
        self.now += 901
        result=self.run_loop()
        self.assertEqual(result['status'],'completed')
        journal=c._load(self.root,DAY)
        self.assertEqual(journal['actions'][0]['status'],'interrupted')
        self.assertEqual(self.backend.uploads,1)

    def test_budget_and_missing_publish_authorization_are_terminal(self):
        self.assertEqual(self.run_loop(max_actions=1)['status'],'budget_exhausted')
        self.assertEqual(len(self.backend.actions),1)

    def test_publish_policy_false_does_not_call_uploader(self):
        self.backend.phase='remote_pending'
        result=self.run_loop(allow_publish=False)
        self.assertEqual(result['code'],'publish_disabled')
        self.assertEqual(self.backend.uploads,0)

    def test_changed_policy_does_not_refund_existing_journal(self):
        self.backend.retry_at=NOW+3600
        self.run_loop()
        with self.assertRaisesRegex(ValueError,'policy_changed'):
            self.run_loop(max_actions=33)

    def test_active_owner_lock_is_not_stolen(self):
        with c.release_lock(self.root/'_automation'/('attempt-'+DAY)):
            result=self.run_loop()
        self.assertEqual(result['code'],'edition_owner_active')
        self.assertFalse(self.backend.actions)

    def test_native_adapter_propagates_write_error_without_guessing_cause(self):
        with patch.object(self.backend,'perform',side_effect=PermissionError(13,'untrusted text')):
            result=self.run_loop()
        self.assertEqual(result['blocker']['operation'],'plan')
        self.assertEqual(result['blocker']['errno'],13)
        self.assertNotIn('untrusted text',json.dumps(result))

    def test_policy_digest_disabled_default_and_cli_require_record(self):
        p=Path(self.temp.name)/'runtime.json'
        p.write_text(json.dumps({'version':1,'enabled':False}))
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertFalse(c.load_policy(p,digest,DAY)['enabled'])
        with self.assertRaisesRegex(ValueError,'digest_mismatch'):c.load_policy(p,'0'*64,DAY)
        with redirect_stdout(io.StringIO()) as out:
            code=o.main(['daily','--date',DAY,'--action','close-loop','--runtime-policy',str(p),
                         '--runtime-policy-sha256',digest])
        self.assertEqual(code,2)
        self.assertIn('requires_record',out.getvalue())

    def test_pending_dispatch_is_bounded_and_has_machine_readable_wakeup(self):
        result=self.run_loop(max_steps_per_invocation=1)
        self.assertEqual(result['status'],'waiting')
        self.assertEqual(result['next_wakeup_at'],NOW+60)
        before=list(self.backend.actions)
        self.run_loop(max_steps_per_invocation=1)
        self.assertEqual(before,self.backend.actions)

    def test_execution_code_change_is_detected_before_following_action(self):
        self.backend.integrity=lambda:'initial' if not self.backend.actions else 'changed'
        self.assertEqual(self.run_loop()['code'],'worker_changed_execution_code')
        self.assertEqual(len(self.backend.actions),1)

    def test_agent_budget_counts_reserved_and_interrupted_invocations(self):
        result=self.run_loop(max_agent_invocations=1)
        self.assertEqual(result['code'],'agent_budget_exhausted')
        self.assertEqual([a[0] for a in self.backend.actions],['plan','work','qualification'])

    def test_process_bridge_is_fresh_schema_bound_and_preserves_sandbox(self):
        calls=[]
        def process(argv,**kw):
            calls.append(argv)
            packet=json.loads(next(line for line in kw['input'].decode().splitlines() if line.startswith('{')))
            receipt=Path(argv[argv.index('--output-last-message')+1])
            receipt.write_text(json.dumps({**{k:packet[k] for k in ('job_id','date','input_sha256')},
                'status':'completed','code':'mock_process_only',
                **({'review_json':'{}'} if packet['role']=='news_review' else {})}),encoding='utf-8')
            return SimpleNamespace(returncode=0)
        with patch.object(c,'run_owned',side_effect=process):
            for role in ('author','news_review'):
                result=c.run_agent(self.root,DAY,role,{'identity':'a'*64},policy(),30)
                self.assertEqual(result['status'],'completed')
        self.assertNotEqual(calls[0][calls[0].index('--output-last-message')+1],calls[1][calls[1].index('--output-last-message')+1])
        self.assertTrue(all('--ephemeral' in argv for argv in calls))
        self.assertEqual([argv[argv.index('--sandbox')+1] for argv in calls],['workspace-write','read-only'])
        self.assertFalse(any('bypass' in arg or arg.startswith('--ignore') for argv in calls for arg in argv))

    def test_process_zero_without_receipt_and_timeout_do_not_approve(self):
        with patch.object(c,'run_owned',return_value=SimpleNamespace(returncode=0)):
            self.assertEqual(c.run_agent(self.root,DAY,'author',{'identity':'a'*64},policy(),30)['code'],'agent_receipt_missing_or_large')
        with patch.object(c,'run_owned',side_effect=c.subprocess.TimeoutExpired('mock',30)):
            self.assertEqual(c.run_agent(self.root,DAY,'author',{'identity':'a'*64},policy(),30)['code'],'agent_timeout_outcome_uncertain')

    def test_policy_rejects_bypass_argv_and_noninteger_bounds(self):
        for p in (policy(codex_argv=[sys.executable,'--dangerously-bypass-approvals-and-sandbox']),
                  policy(max_agent_invocations=True),policy(deadline_time='00:30'),policy(start_time='00:55')):
            with self.subTest(p=p),self.assertRaises(ValueError):c.policy_bounds(p,DAY)

    def test_native_snapshot_waits_for_live_source_lease_then_allows_reclaim(self):
        from source_pool import SourcePool,task_spec
        pool_path=self.root/'_sources/pool.sqlite'
        with SourcePool(pool_path) as pool:
            key=pool.enqueue(task_spec('academic','synthetic-source','2026-10-17',{},{}))
            owner=pool.claim(task_id=key,now=NOW)
        source={'status':'coverage_pending','missing_tasks':[{'task_id':key,'kind':'academic','state':'running','retry_at':None}]}
        fake=SimpleNamespace(NEWS_ROOT=self.root,_daily_execution=lambda *a,**kw:{'phase':'source_and_authoring_pending','source_preparation':source},
                            inspect=lambda day:{'phase':'collection_pending'})
        with patch.object(c.time,'time',return_value=NOW):snapshot=c.Backend(fake).snapshot(DAY)
        self.assertEqual(snapshot['retry_at'],owner['lease_until'])
        with patch.object(c.time,'time',return_value=owner['lease_until']+1):snapshot=c.Backend(fake).snapshot(DAY)
        self.assertIsNone(snapshot['retry_at'])
        with SourcePool(pool_path,read_only=True) as pool:
            self.assertEqual(pool.get(key)['attempts'],1)
            self.assertEqual(pool.get(key)['state'],'running') # only actual claim reclaims


class NativeLifecycleTests(unittest.TestCase):
    setUp = v4.V4PublicationTests.setUp
    prepare = v4.V4PublicationTests.prepare
    write_candidate = v4.V4PublicationTests.write_candidate
    stage = v4.V4PublicationTests.stage

    def prepared_stage(self):
        self.prepare()
        # Keep all synthetic source/story fixtures and genuine local validators,
        # move only the fixture's edition so automatic eligibility applies.
        from source_capture import capture_path, make_capture
        import html
        self.release=DAY
        self.raw['date_range']='2026-10-17'
        self.raw['collection_completed_at']=DAY+'T01:30:00+08:00'
        self.raw['coverage_evidence']=[reviewed.daily_evidence('2026-10-17')]
        v4.use_v4(self.raw)
        for section in self.raw['sections']:
            for item in section['items']:
                item['published_at']='2026-10-17'
                body=('<title>Original source '+item['id']+'</title><p>'+html.escape(item['source_excerpt'])+'</p>').encode()
                record=make_capture(item,item['source_url'],item['source_url'],200,body,self.raw['collection_completed_at'])
                p=capture_path(self.news,'2026-10-17',item['id']);p.parent.mkdir(parents=True,exist_ok=True)
                p.write_text(json.dumps(record),encoding='utf-8')
        index=self.news/'_index/story_index.jsonl'
        prior=[json.loads(line) for line in index.read_text().splitlines() if line]
        for row in prior:row['last_seen']='2026-10-17'
        index.write_text(''.join(json.dumps(row)+'\n' for row in prior));self.index_before=index.read_bytes()
        self.write_candidate()
        self.args=dp.parse_args(['run','--config',str(self.candidate),'--date',DAY,
             '--coverage-start','2026-10-17T00:00:00+08:00','--coverage-end',DAY+'T00:00:00+08:00'])
        stage,manifest_path,manifest=self.stage()
        root=patch.object(o,'NEWS_ROOT',self.news);root.start();self.addCleanup(root.stop)
        return stage,manifest_path

    def synthetic_reviews(self,stage,manifest_path):
        """Synthetic protocol fixtures, never actual semantic/display evidence."""
        from review_evidence import DISPLAY_CHECKS
        reviewed.ReviewedReleaseTests._write_reviews(SimpleNamespace(stage=stage,date=DAY,manifest_path=manifest_path))
        result={}
        for role,name in [('news_review','news_content_review'),('story_review','opening_story_review')]:
            path=stage/(name+'_'+DAY+'.json')
            result[role]=json.loads(path.read_text(encoding='utf-8'));result[role]['review_method']='independent'
            path.unlink()  # only this test's newly created temporary fixture
        story=result['story_review'];third=story['rounds'][2]
        digest=json.loads(manifest_path.read_text())['artifact_sha256']['html']
        third.update(judgment='pending',unresolved=[{'kind':'actual_display_pending','reason':'synthetic pending'}],
            cross_surface_checks={'judgment':'pass','reason':'synthetic protocol fixture'},
            display_review={'version':1,'status':'pending','html_sha256':digest,
                'checks':[{'id':key,'status':'pending'} for key in sorted(DISPLAY_CHECKS)]})
        display=copy.deepcopy(story);third=display['rounds'][2];third.update(judgment='pass',unresolved=[])
        third['display_review']['status']='pass'
        for check in third['display_review']['checks']:
            check.update(status='pass',evidence={'type':'actual_browser','reference':'synthetic-test-only',
                'environment':'synthetic-test-only','observed_at':DAY+'T02:00:00+08:00'})
        result['display_review']=display;result['story_blind']=copy.deepcopy(story['rounds'][0])
        return result

    def test_real_strict_lifecycle_and_local_only_cannot_implicitly_upload(self):
        stage,manifest_path=self.prepared_stage()
        backend=c.Backend(o)
        calls=[]
        proposals=self.synthetic_reviews(stage,manifest_path)
        def worker(root,day,role,snapshot,p,timeout):
            calls.append(role)
            # Deliberately synthetic semantic/display judgments; these certify
            # invocation/binding only, never actual reviewer quality or display.
            return {'status':'completed','code':'synthetic_fixture_only','review':copy.deepcopy(proposals[role])}
        p=policy(allow_publish=False,allow_preview=True)
        with patch.object(c,'run_agent',side_effect=worker),patch.object(publisher,'preview',return_value={'status':'previewed','site_url':'https://example.invalid/synthetic'}),patch.object(publisher,'auto_publish_after_finalize',side_effect=AssertionError('implicit upload forbidden')):
            # Stop after finalize, before a real online operation can run.
            result=c.execute(backend,DAY,{**p,'max_steps_per_invocation':6},
                policy_sha256='1'*64,clock=lambda:NOW)
        self.assertEqual(calls,['news_review','story_blind','story_review','display_review'],result)
        final=self.news/DAY
        self.assertEqual(dp.verify_artifacts(final,strict=True)['status'],'pass')
        self.assertEqual(result['status'],'waiting')
        self.assertFalse((self.news/'_publish'/('oss_publish_receipt_'+DAY+'.json')).exists())
        actions=c._load(self.news,DAY)['actions']
        self.assertEqual([a['action'] for a in actions],['review_template','news_review','story_review','display_review','seal','finalize'])

    def test_worker_acknowledgments_cannot_pass_unreviewed_native_gate(self):
        stage,_=self.prepared_stage()
        with patch.object(c,'run_agent',return_value={'status':'completed','code':'ack_only'}), \
             patch.object(publisher,'publish',side_effect=AssertionError('must not publish')):
            p=policy()
            result=c.execute(c.Backend(o),DAY,p,policy_sha256='2'*64,clock=lambda:NOW)
        self.assertEqual(result['status'],'blocked')
        self.assertEqual(result['code'],'review_proposal_required')
        self.assertEqual(dp.verify_artifacts(stage,strict=True)['status'],'fail')

    def test_native_reviewer_claim_without_approved_items_still_fails_seal(self):
        stage,manifest_path=self.prepared_stage()
        dp.cmd_review_template(SimpleNamespace(run_dir=str(stage)))
        for name in ('news_content_review','opening_story_review'):
            q=stage/(name+'_'+DAY+'.json');value=json.loads(q.read_text(encoding='utf-8'));value['review_method']='independent'
            q.write_text(json.dumps(value),encoding='utf-8')
        with patch.object(c,'run_agent',return_value={'status':'completed','code':'ack_only'}), \
             patch.object(publisher,'publish',side_effect=AssertionError('must not publish')):
            p=policy()
            result=c.execute(c.Backend(o),DAY,p,policy_sha256='3'*64,clock=lambda:NOW)
        self.assertEqual(result['code'],'review_proposal_required')
        self.assertFalse((self.news/DAY/('daily_pipeline_manifest_'+DAY+'.json')).exists())


if __name__ == '__main__':
    unittest.main()
