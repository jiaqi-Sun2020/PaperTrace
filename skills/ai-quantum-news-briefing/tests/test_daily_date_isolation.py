"""Date-isolated automatic execution; temporary data, no real collection/upload."""
import copy,io,json,sqlite3,sys,tempfile,unittest
from contextlib import redirect_stdout
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import orchestrate_daily as o
import source_worker as worker
from source_pool import SourcePool,task_spec

DAY='2026-10-16'
def pending(day):return {'date':day,'phase':'candidate_authoring_pending','action_required':True,'next_action':'author '+day}

class DailyDateIsolationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.news=Path(self.temp.name)/'news';self.news.mkdir()
        self.queue=self.news/'_automation/workflow_queue.json';self.queue.parent.mkdir()
        p=patch.object(o,'NEWS_ROOT',self.news);p.start();self.addCleanup(p.stop)
    def seed(self,dates):self.queue.write_text(json.dumps({'version':1,'dates':dates}),encoding='utf-8')

    def test_old_failed_day_is_not_inspected_or_selected(self):
        self.seed(['2026-10-15',DAY])
        def inspect(day):
            if day!=DAY:raise AssertionError('historical failure reached current execution')
            return pending(day)
        with patch.object(o,'inspect',side_effect=inspect):result=o.workflow_queue(DAY)
        self.assertEqual(result['execution_order'],[DAY]);self.assertEqual(result['next_date'],DAY)
        self.assertIn('daily --date '+DAY,result['next_action'])
        self.assertIn('2026-10-15',result['retired_dates'])

    def test_current_completion_ends_even_with_other_eligible_date_pending(self):
        self.seed([DAY,'2026-10-17'])
        with patch.object(o,'inspect',return_value={'date':'2026-10-17','phase':'remote_complete','action_required':False}) as inspect:
            result=o.workflow_queue('2026-10-17')
        inspect.assert_called_once_with('2026-10-17')
        self.assertEqual(result['execution_order'],[]);self.assertIsNone(result['next_date'])
        self.assertTrue(result['final_response_allowed']);self.assertIn(DAY,result['deferred_dates'])

    def test_retired_date_never_claimed_success_or_recreated(self):
        self.seed(['2026-10-15'])
        with patch.object(o,'inspect') as inspect:result=o.workflow_queue('2026-10-15',record=True)
        inspect.assert_not_called();self.assertEqual(result['run_outcome'],'not_scheduled')
        self.assertEqual(result['execution_order'],[]);self.assertNotEqual(result['phase'],'workflow_complete')
        self.assertIsNone(result['next_date'])

    def test_cutoff_record_is_idempotent_and_preserves_history_and_withdrawal_reason(self):
        self.seed(['2026-10-10','2026-10-15',DAY])
        value=json.loads(self.queue.read_text());value['withdrawals']={'2026-10-10':{'reason':'Original user decision','recorded_at':'2026-10-11T00:00:00Z'}}
        self.queue.write_text(json.dumps(value),encoding='utf-8')
        old=self.news/'2026-10-15/failed-review.json';old.parent.mkdir();old.write_bytes(b'original failed review')
        with patch.object(o,'inspect',side_effect=pending):
            o.workflow_queue(DAY,record=True);once=self.queue.read_bytes();o.workflow_queue(DAY,record=True)
        self.assertEqual(self.queue.read_bytes(),once);saved=json.loads(once)
        self.assertEqual(saved['withdrawals']['2026-10-10']['reason'],'Original user decision')
        self.assertEqual(saved['history_policy']['not_before'],DAY)
        self.assertEqual(old.read_bytes(),b'original failed review')
        self.assertEqual(saved['dates'],['2026-10-10','2026-10-15',DAY])

    def test_read_only_queue_never_writes_retirement(self):
        self.seed(['2026-10-15',DAY]);before=self.queue.read_bytes()
        with patch.object(o,'inspect',side_effect=pending),patch.object(o,'atomic_json',side_effect=AssertionError('write')):
            o.workflow_queue(DAY)
        self.assertEqual(self.queue.read_bytes(),before)

    def test_corrupt_shared_queue_is_an_explicit_blocker(self):
        self.queue.write_bytes(b'{broken')
        result=o.daily_execution(DAY,action='status')
        self.assertEqual(result['phase'],'execution_blocked');self.assertEqual(result['terminal_blocker']['scope'],'shared')
        self.assertTrue(result['final_response_allowed']);self.assertFalse(result['publication_approved'])

    def test_shared_pool_error_blocks_current_instead_of_silent_fallback(self):
        with patch.object(o,'inspect',side_effect=pending),patch('source_preparation.orchestrate_sources',side_effect=sqlite3.DatabaseError('synthetic corrupt store')):
            result=o.daily_execution(DAY,action='status')
        self.assertEqual(result['terminal_blocker']['stage'],'source_pool')
        self.assertEqual(result['terminal_blocker']['scope'],'shared')

    def test_required_discovery_failure_is_a_stopping_failure_not_completion(self):
        source={'source_preparation':{'status':'coverage_pending','missing_tasks':[{'kind':'discovery',
                'source_id':'reputable_media','state':'blocked','failure':{'code':'policy_rejected','retryable':False}}]}}
        with patch.object(o,'inspect',side_effect=pending),patch('source_preparation.orchestrate_sources',return_value=source):
            result=o.daily_execution(DAY)
        self.assertEqual(result['run_outcome'],'blocked');self.assertTrue(result['operation_failed'])
        self.assertTrue(result['final_response_allowed']);self.assertEqual(result['next_date'],DAY)
        self.assertFalse(result['publication_approved'])

    def test_discovery_gap_points_to_real_claim_not_an_ordinary_work_loop(self):
        source={'source_preparation':{'status':'coverage_pending','academic':{'family_gate':{'status':'pass'}},
                'aihot':{},'missing_tasks':[{'task_id':'synthetic-discovery','kind':'discovery','state':'pending'}]}}
        with patch.object(o,'inspect',side_effect=pending),patch('source_preparation.orchestrate_sources',return_value=source):
            result=o.daily_execution(DAY)
        command=result['next_commands'][0]['argv']
        self.assertIn('claim-discovery',command);self.assertIn(DAY,command);self.assertIn('synthetic-discovery',command)
        self.assertNotIn('work',command)

    def test_exhausted_current_source_set_does_not_suggest_an_empty_work_loop(self):
        source={'source_preparation':{'status':'coverage_pending','missing_tasks':[{'kind':'academic','state':'exhausted'}]}}
        with patch.object(o,'inspect',side_effect=pending),patch('source_preparation.orchestrate_sources',return_value=source):
            result=o.daily_execution(DAY)
        self.assertEqual(result['next_commands'],[]);self.assertEqual(result['run_outcome'],'blocked')
        self.assertTrue(result['final_response_allowed']);self.assertFalse(result['publication_approved'])

    def test_frozen_review_keeps_stage_without_new_acquisition(self):
        with patch.object(o,'inspect',return_value={'date':DAY,'phase':'review_pending','action_required':True,
                   'next_action':'review this current run'}),patch('source_preparation.orchestrate_sources') as source:
            result=o.daily_execution(DAY,action='work')
        source.assert_not_called();self.assertEqual(result['phase'],'review_pending')
        self.assertEqual(result['execution_order'],[DAY]);self.assertEqual(result['next_date'],DAY)

    def test_shared_release_permission_failure_is_not_hidden_by_date_isolation(self):
        state={'date':DAY,'phase':'remote_pending','action_required':True,'environment_fault':'ossutil_unavailable'}
        with patch.object(o,'inspect',return_value=state):result=o.daily_execution(DAY,action='work')
        self.assertEqual(result['terminal_blocker']['scope'],'shared')
        self.assertEqual(result['terminal_blocker']['stage'],'release_environment')
        self.assertEqual(result['run_outcome'],'blocked')

    def test_already_published_day_never_collects_or_uploads(self):
        with patch.object(o,'inspect',return_value={'date':DAY,'phase':'remote_complete','action_required':False}), \
                patch('source_preparation.orchestrate_sources') as sources,patch('publish_daily_to_oss.upload_file') as upload:
            result=o.daily_execution(DAY,action='work')
        sources.assert_not_called();upload.assert_not_called()
        self.assertEqual(result['run_outcome'],'completed');self.assertTrue(result['final_response_allowed'])

    def test_fixed_release_day_and_coverage_do_not_use_new_wall_clock_day(self):
        class BeforeMidnight(datetime):
            @classmethod
            def now(cls,tz=None):return datetime(2026,10,16,15,59,tzinfo=timezone.utc)
        class AfterMidnight(datetime):
            @classmethod
            def now(cls,tz=None):return datetime(2026,10,16,16,1,tzinfo=timezone.utc)
        with patch.object(o,'inspect',side_effect=pending),patch('source_preparation.orchestrate_sources',return_value={'source_preparation':{'status':'coverage_pending'}}) as sources:
            with patch.object(o,'datetime',BeforeMidnight):first=o.daily_execution(DAY,action='plan',record=True)
            with patch.object(o,'datetime',AfterMidnight):second=o.daily_execution(DAY,action='status')
        self.assertEqual(first['date'],DAY);self.assertEqual(second['coverage_date'],'2026-10-15')
        self.assertTrue(all(call.args[0]==DAY for call in sources.call_args_list))

    def test_discovery_task_from_another_date_is_rejected_before_claim(self):
        import source_preparation as preparation
        from discovery_navigation import navigation_request
        with SourcePool(self.news/'_sources/pool.sqlite') as pool:
            key=pool.enqueue(task_spec('discovery','reputable_media','2026-10-14',
                                      {'navigation':navigation_request('reputable_media','2026-10-14')},
                                      {'code':worker.code_binding()}))
            before=pool.get(key)
        with redirect_stdout(io.StringIO()):
            code=preparation.main(['claim-discovery','--date',DAY,'--pool-dir',str(self.news/'_sources'),'--task-id',key])
        self.assertEqual(code,2)
        with SourcePool(self.news/'_sources/pool.sqlite') as pool:self.assertEqual(pool.get(key),before)

    def test_cli_requires_an_explicit_date(self):
        with redirect_stdout(io.StringIO()),patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):
            o.parse_args(['daily','--action','plan'])

    def test_later_preserved_cutoff_is_not_lowered(self):
        self.seed([DAY,'2026-10-18'])
        value=json.loads(self.queue.read_text());value['history_policy']={'version':1,'not_before':'2026-10-18',
            'timezone':'Asia/Shanghai','recorded_at':'2026-10-16T00:00:00Z','reason':'Preserved stricter decision'}
        self.queue.write_text(json.dumps(value),encoding='utf-8')
        with patch.object(o,'inspect') as inspect:result=o.workflow_queue(DAY,record=True)
        inspect.assert_not_called();self.assertEqual(result['automatic_release_not_before'],'2026-10-18')
        self.assertEqual(json.loads(self.queue.read_text())['history_policy'],value['history_policy'])

    def test_worker_ignores_old_pending_and_does_not_spend_current_budget_on_it(self):
        with SourcePool(self.news/'_sources/pool.sqlite') as pool:
            for day in ('2026-10-14','2026-10-15'):
                pool.enqueue(task_spec('academic','synthetic',day,{}, {'code':worker.code_binding()}))
            calls=[]
            def blocked(spec):calls.append(spec['coverage_date']);raise HTTPError('https://synthetic.invalid/',403,'',{},None)
            result=worker.run_ready(pool,max_tasks=1,executor=blocked,coverage_date='2026-10-15')
            self.assertEqual(calls,['2026-10-15']);self.assertEqual(len(result['processed']),1)
            old=pool.tasks()[0];self.assertEqual(old['attempts'],0);self.assertEqual(old['state'],'pending')

    def test_expired_corrupt_historical_task_does_not_block_explicit_current_claim(self):
        with SourcePool(self.news/'_sources/pool.sqlite') as pool:
            old=pool.enqueue(task_spec('academic','old','2026-10-14',{},{}));pool.claim(task_id=old,now=1)
            pool.db.execute('UPDATE tasks SET result=?,result_sha=? WHERE task_id=?',(b'{}','bad',old))
            current=pool.enqueue(task_spec('academic','current','2026-10-15',{},{}))
            row=pool.claim(task_id=current,now=400)
            self.assertEqual(row['task_id'],current)

    def test_retired_sources_refuse_before_opening_or_mutating_pool(self):
        import source_preparation as preparation
        with patch.object(preparation,'SourcePool',side_effect=AssertionError('old pool was opened')):
            result=preparation.orchestrate_sources('2026-10-15',self.news/'_sources',action='work')
        self.assertEqual(result['status'],'historical_retired')
        self.assertFalse((self.news/'_sources').exists())

    def test_retirement_never_blocks_explicit_history_backup(self):
        import source_preparation as preparation
        with SourcePool(self.news/'_sources/pool.sqlite') as pool:
            pool.enqueue(task_spec('academic','old','2026-10-14',{},{}))
        before=(self.news/'_sources/pool.sqlite').read_bytes()
        with tempfile.TemporaryDirectory() as external,redirect_stdout(io.StringIO()) as stream:
            output=Path(external)/'history.sqlite'
            code=preparation.main(['backup','--date','2026-10-15','--pool-dir',str(self.news/'_sources'),'--output',str(output)])
            self.assertEqual(code,0);self.assertTrue(output.is_file())
            self.assertEqual(json.loads(stream.getvalue())['status'],'sqlite_consistent_backup_complete')
        self.assertEqual((self.news/'_sources/pool.sqlite').read_bytes(),before)

if __name__=='__main__':unittest.main()
