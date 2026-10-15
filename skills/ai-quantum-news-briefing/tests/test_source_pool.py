"""Synthetic/offline acquisition transactions. No production data or OSS."""
import copy
import hashlib
import json
import multiprocessing
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from source_pool import SourcePool, PoolConflict, task_spec, fingerprint
from source_worker import plan_sources, claim_discovery, run_ready, code_binding, failure_for
from discovery_navigation import navigation_request, validate_navigation, browser_call
from source_capture import make_capture
from source_preparation import bind_candidate, check_pool_binding, check_run_pool_binding
from paper_identity import paper_kind, doi_for
from audit_briefing_config import academic_kind


def claim_process(database,key,start,output):
    with SourcePool(database) as pool:
        start.wait(10)
        row=pool.claim(task_id=key,now=10)
        output.put(row['lease'] if row else None)


def cold_process(database,spec,start,output):
    start.wait(10)
    with SourcePool(database) as pool:
        key=pool.enqueue(spec);row=pool.claim(task_id=key,now=10)
        output.put(row['lease'] if row else None)


def complete_process(database,key,lease,start,output):
    with SourcePool(database) as pool:
        start.wait(10)
        output.put(pool.complete(key,lease,{'synthetic':1},lambda s,r:[],now=11)['state'])


def material_lock_process(database,attempted,acquired,output):
    from contextlib import contextmanager
    import release_lock as locking
    original=locking.release_lock
    @contextmanager
    def traced(root,**kwargs):
        attempted.set()
        with original(root,**kwargs):
            acquired.set()
            yield
    item,capture=material()
    with SourcePool(database) as pool,patch.object(locking,'release_lock',traced):
        output.put(pool.put_material('plos-ai',item,capture)['material_id'])


def material():
    item={'id':'A1','story_id':'same-story','material_kind':'academic','source_url_contract_version':2,
          'source_url':'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0312345',
          'publication_type':'journal-article','source_title':'Synthetic research',
          'source_excerpt':'Verified synthetic original excerpt.', 'evidence_level':'peer-reviewed original article',
          'evidence_fingerprint':'synthetic-fixture-only','published_at':'2026-10-14', 'source_class':'peer_reviewed'}
    raw=b'<html><title>Synthetic research</title><p>Verified synthetic original excerpt.</p></html>'
    cap=make_capture(item,item['source_url'],item['source_url'],200,raw,'2026-10-15T00:00:00Z')
    return item,cap


class SourcePoolTests(unittest.TestCase):
    def test_aihot_failure_callback_crosses_wrapper_and_legacy_failure_still_returns(self):
        import aihot_candidates as hot
        from urllib.error import HTTPError
        args=hot.parse_args(['--date','2026-10-15','--coverage-date','2026-10-14',
                             '--source','api','--mode','selected','--take','50','--output',str(self.root/'hot.json')])
        observations=[]
        with patch.object(hot,'fetch_response',side_effect=HTTPError('https://synthetic.invalid/',403,'',{},None)):
            items,evidence=hot.api_items(args,on_failure=observations.append)
            old_items,old_evidence=hot.api_items(args)
        self.assertEqual(len(observations),1)
        self.assertEqual(observations[0].code,403)
        self.assertEqual(items,old_items)
        self.assertEqual(evidence['pagination_complete'],old_evidence['pagination_complete'])
        self.assertFalse(evidence['pagination_complete'])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.path=self.root/'news/_sources/pool.sqlite'
        self.pool=SourcePool(self.path)
        self.spec=task_spec('academic','test-source','2026-10-14',{'query':'x'},{'version':1})

    def tearDown(self):
        self.pool.close();self.temp.cleanup()

    def test_idempotent_identity_and_input_date_config_drift(self):
        key=self.pool.enqueue(self.spec)
        self.assertEqual(key,self.pool.enqueue(copy.deepcopy(self.spec)))
        for field,value in [('coverage_date','2026-10-13'),('inputs',{'query':'changed'}),('config',{'version':2})]:
            changed=copy.deepcopy(self.spec);changed[field]=value
            self.assertNotEqual(key,self.pool.enqueue(changed))
        self.assertEqual(self.pool.get(key)['attempts'],0)

    def test_lost_ack_idempotent_complete_and_cursor_not_advanced_on_failure(self):
        key=self.pool.enqueue(self.spec)
        lease=self.pool.claim(task_id=key,now=10)
        self.pool.fail(key,lease['lease'],{'code':'transport_timeout','retryable':True},now=11)
        self.assertIsNone(self.pool.get(key)['checkpoint'])
        self.assertIsNone(self.pool.claim(task_id=key,now=40))
        lease=self.pool.claim(task_id=key,now=41)
        row=self.pool.complete(key,lease['lease'],{'data':1},lambda spec,result:[],now=42,checkpoint={'cursor':'verified'})
        self.assertEqual(row['checkpoint'],{'cursor':'verified'})
        self.assertEqual(self.pool.complete(key,lease['lease'],{'data':1},lambda s,r:[],now=45)['state'],'succeeded')
        self.assertIsNone(self.pool.claim(task_id=key,now=50))
        with self.assertRaises(PoolConflict):
            self.pool.complete(key,lease['lease'],{'data':2},lambda s,r:[],now=45)

    def test_interruption_reentry_stale_commit_and_attempt_bound(self):
        key=self.pool.enqueue(self.spec)
        first=self.pool.claim(task_id=key,now=0,lease_seconds=1)
        second=self.pool.claim(task_id=key,now=2,lease_seconds=1)
        with self.assertRaises(PoolConflict):
            self.pool.complete(key,first['lease'],{},lambda s,r:[],now=2)
        third=self.pool.claim(task_id=key,now=4,lease_seconds=1)
        self.assertIsNotNone(second);self.assertIsNotNone(third)
        self.assertIsNone(self.pool.claim(task_id=key,now=6))
        self.assertEqual(self.pool.get(key)['state'],'exhausted')
        self.assertIsNone(self.pool.get(key)['checkpoint'])

    def test_two_real_processes_claim_only_one_lease(self):
        key=self.pool.enqueue(self.spec)
        context=multiprocessing.get_context('spawn')
        start=context.Event();out=context.Queue()
        processes=[context.Process(target=claim_process,args=(str(self.path),key,start,out)) for _ in range(2)]
        for process in processes:process.start()
        start.set()
        results=[out.get(timeout=20) for _ in processes]
        for process in processes:
            process.join(20);self.assertEqual(process.exitcode,0)
        self.assertEqual(sum(value is not None for value in results),1)

    def test_two_real_processes_initialize_and_claim_without_schema_race(self):
        context=multiprocessing.get_context('spawn');start=context.Event();out=context.Queue()
        path=self.root/'cold/pool.sqlite'
        processes=[context.Process(target=cold_process,args=(str(path),self.spec,start,out)) for _ in range(2)]
        for process in processes:process.start()
        start.set();results=[out.get(timeout=20) for _ in processes]
        for process in processes:process.join(20);self.assertEqual(process.exitcode,0)
        self.assertEqual(sum(value is not None for value in results),1)

    def test_two_real_result_commits_are_idempotent(self):
        key=self.pool.enqueue(self.spec);lease=self.pool.claim(task_id=key,now=10)['lease']
        context=multiprocessing.get_context('spawn');start=context.Event();out=context.Queue()
        processes=[context.Process(target=complete_process,args=(str(self.path),key,lease,start,out)) for _ in range(2)]
        for process in processes:process.start()
        start.set();results=[out.get(timeout=20) for _ in processes]
        for process in processes:process.join(20);self.assertEqual(process.exitcode,0)
        self.assertEqual(results,['succeeded','succeeded'])
        self.assertEqual(self.pool.db.execute("SELECT count(*) FROM events WHERE task_id=? AND state='succeeded'",(key,)).fetchone()[0],1)

    def test_material_commit_waits_for_real_cross_process_publication_lock(self):
        from release_lock import release_lock
        context=multiprocessing.get_context('spawn');attempted=context.Event();acquired=context.Event();out=context.Queue()
        process=context.Process(target=material_lock_process,args=(str(self.path),attempted,acquired,out))
        with release_lock(self.root/'news'):
            process.start();self.assertTrue(attempted.wait(10))
            self.assertFalse(acquired.wait(0.2))
        self.assertTrue(acquired.wait(10));self.assertTrue(out.get(timeout=10))
        process.join(10);self.assertEqual(process.exitcode,0)

    def test_unknown_database_and_corrupt_state_are_preserved(self):
        unknown=self.root/'unknown.sqlite';db=sqlite3.connect(str(unknown));db.execute('CREATE TABLE user_data(value)');db.commit();db.close()
        before=unknown.read_bytes()
        with self.assertRaises(PoolConflict):SourcePool(unknown)
        self.assertEqual(unknown.read_bytes(),before)
        key=self.pool.enqueue(self.spec)
        self.pool.db.execute('UPDATE tasks SET attempts=-1 WHERE task_id=?',(key,))
        with self.assertRaises(PoolConflict):self.pool.get(key)
        self.assertEqual(self.pool.db.execute('SELECT attempts FROM tasks WHERE task_id=?',(key,)).fetchone()[0],-1)

    def test_academic_retry_after_is_never_capped_to_an_early_retry(self):
        import academic_venue_sweep as sweep
        evidence={'status_code':429,'retry_after':'120','error':'synthetic rate limit'}
        with patch.object(sweep,'_request_evidence',return_value=(evidence,b'')) as request,patch.object(sweep.time,'sleep') as sleep:
            self.assertEqual(sweep._request_source_with_retry('https://public.invalid/',1),(evidence,b''))
            self.assertEqual(request.call_count,1);sleep.assert_not_called()

    def test_denial_blocks_task_but_not_independent_work(self):
        a=self.pool.enqueue(self.spec)
        b=copy.deepcopy(self.spec);b['source_id']='independent';b=self.pool.enqueue(b)
        lease=self.pool.claim(task_id=a,now=10)
        self.pool.fail(a,lease['lease'],{'code':'policy_rejected','retryable':False},now=11)
        self.assertIsNone(self.pool.claim(task_id=a,now=10000))
        self.assertIsNotNone(self.pool.claim(task_id=b,now=11))

    def test_transaction_abort_keeps_previous_bytes_and_retryable_lease(self):
        key=self.pool.enqueue(self.spec);lease=self.pool.claim(task_id=key,now=10)
        with self.assertRaises(RuntimeError):
            with self.pool.transaction():
                self.pool.db.execute("UPDATE tasks SET state='succeeded' WHERE task_id=?",(key,))
                raise RuntimeError('injected before COMMIT')
        self.assertEqual(self.pool.get(key)['state'],'running')
        self.pool.complete(key,lease['lease'],{'ok':1},lambda s,r:[],now=11)

    def test_material_revisions_invalidate_preparation_even_after_reversion(self):
        item,cap=material();a=self.pool.put_material('plos-ai',item,cap)
        scope={'release_date':'2026-10-15','input':'synthetic material dependency test'}
        refs=[{k:a[k] for k in ('material_id','revision')}]
        binding=self.pool.bind_preparation(scope,refs)
        self.assertEqual(self.pool.validate_preparation(binding,scope),[])
        self.assertFalse(self.pool.put_material('plos-ai',item,cap)['changed'])
        changed=copy.deepcopy(item);changed['facts']='A changed authored claim.'
        b=self.pool.put_material('plos-ai',changed,cap)
        self.assertNotEqual(a['revision'],b['revision'])
        self.assertTrue(self.pool.validate_preparation(binding,scope))
        c=self.pool.put_material('plos-ai',item,cap)
        self.assertNotEqual(a['revision'],c['revision'])
        self.assertFalse(self.pool.material(a['material_id'],a['revision'])['current'])
        self.assertEqual(self.pool.material(a['material_id'],a['revision'])['item'],item)

    def test_raw_url_parameters_are_not_merged(self):
        item,cap=material();a=self.pool.put_material('plos-ai',item,cap)
        changed=copy.deepcopy(item);changed['source_url']+='&version=2'
        raw=b'<p>Verified synthetic original excerpt.</p>'
        second=make_capture(changed,changed['source_url'],changed['source_url'],200,raw,'2026-10-15T00:00:00Z')
        b=self.pool.put_material('plos-ai',changed,second)
        self.assertNotEqual(a['material_id'],b['material_id'])
        self.assertEqual(self.pool.material(b['material_id'])['item']['source_url'],changed['source_url'])

    def test_bad_date_aggregation_excerpt_and_unsupported_academic_do_not_enter_pool(self):
        item,cap=material()
        for field,value in [('published_at',None),('evidence_level','aihot candidate'),('source_excerpt','not retrieved'),
                            ('source_url','https://unregistered.invalid/article')]:
            bad=copy.deepcopy(item);bad[field]=value
            with self.subTest(field=field),self.assertRaises(PoolConflict):
                self.pool.put_material('plos-ai',bad,cap)
        self.assertEqual(self.pool.db.execute('SELECT count(*) FROM materials').fetchone()[0],0)

    def test_consistent_backup_includes_wal_and_preserves_destination(self):
        self.pool.db.execute('PRAGMA journal_mode=WAL')  # Explicit fixture; default deployment remains DELETE.
        key=self.pool.enqueue(self.spec)
        with tempfile.TemporaryDirectory() as external:
            backup=Path(external)/'pool-backup.sqlite'
            self.pool.backup(backup)
            with SourcePool(backup) as restored:self.assertEqual(restored.get(key)['state'],'pending')
            original=backup.read_bytes()
            with self.assertRaises(PoolConflict):self.pool.backup(backup)
            self.assertEqual(original,backup.read_bytes())
        with self.assertRaises(PoolConflict):self.pool.backup(self.root/'news/unsafe-backup.sqlite')

    def test_plan_is_persistent_and_discovery_claim_uses_typed_browser_call(self):
        plan=plan_sources(self.pool,'2026-10-15')
        self.assertEqual(plan,plan_sources(self.pool,'2026-10-15'))
        discovery=[key for key in plan['tasks'] if self.pool.get(key)['spec']['kind']=='discovery']
        self.assertEqual(len(discovery),3)
        lease=claim_discovery(self.pool,discovery[0],now=10)
        self.assertEqual(validate_navigation(lease['navigation']),lease['navigation']['url'])
        self.assertIn('await navigateSource(tab,',lease['browser_call'])
        self.assertNotIn('.goto(mediaQuery',lease['browser_call'])

    def test_403_404_permission_timeout_and_429_are_distinct(self):
        self.assertEqual(failure_for(ValueError(),http_status=403)['code'],'source_access_denied')
        self.assertFalse(failure_for(ValueError(),http_status=403)['retryable'])
        self.assertEqual(failure_for(ValueError(),http_status=404)['code'],'source_not_found')
        self.assertEqual(failure_for(PermissionError())['code'],'environment_permission_denied')
        self.assertEqual(failure_for(TimeoutError())['code'],'transport_timeout')
        row=failure_for(ValueError(),http_status=429,retry_after=120)
        self.assertEqual(row['retry_after_seconds'],120)
        key=self.pool.enqueue(self.spec);lease=self.pool.claim(task_id=key,now=10)
        self.pool.fail(key,lease['lease'],row,now=11)
        self.assertIsNone(self.pool.claim(task_id=key,now=130))
        self.assertIsNotNone(self.pool.claim(task_id=key,now=131))

    def test_long_retry_after_is_durable_wait_not_sleep_or_early_retry(self):
        row=failure_for(ValueError(),http_status=429,retry_after=3600)
        self.assertEqual(row['retry_after_seconds'],3600)
        key=self.pool.enqueue(self.spec);lease=self.pool.claim(task_id=key,now=10)
        self.pool.fail(key,lease['lease'],row,now=11)
        self.assertIsNone(self.pool.claim(task_id=key,now=3610))
        self.assertIsNotNone(self.pool.claim(task_id=key,now=3611))


class NavigationAndPLOSTests(unittest.TestCase):
    def test_python_query_is_not_navigation_and_drift_is_rejected(self):
        request=navigation_request('reputable_media','2026-10-14')
        for value in (request['query'],{'type':'query','query':request['query']},
                      {**request,'url':request['query']},{**request,'coverage_date':'2026-10-13'}):
            with self.assertRaises((TypeError,ValueError)):validate_navigation(value)

    def test_actual_js_adapter_rejects_query_before_goto_and_propagates_policy_denial(self):
        import shutil
        if not shutil.which('node'):self.skipTest('Node unavailable: actual JS call adapter untested')
        request=navigation_request('reputable_media','2026-10-14')
        module=(SCRIPTS/'discovery_navigation.mjs').as_uri()
        js='''import {navigateSource} from %s;
let count=0;const tab={goto:async(url)=>{count++;throw new Error('policy_rejected')}};
for(const bad of [%s,{type:'query',query:%s}]) {try{await navigateSource(tab,bad);throw Error('accepted bad input')}catch(e){if(e.message==='accepted bad input')throw e;}}
if(count!==0)throw Error('bad query left process');
try{await navigateSource(tab,%s)}catch(e){if(e.message!=='policy_rejected')throw e;}
if(count!==1)throw Error('policy rejection retried');
console.log(JSON.stringify({invalid_query_network_calls:0,policy_denial_calls:count}));'''%(json.dumps(module),json.dumps(request['query']),json.dumps(request['query']),json.dumps(request))
        result=subprocess.run(['node','--input-type=module','-e',js],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_plos_article_admission_matches_capture_and_doi(self):
        item,cap=material();item['source_capture']=cap
        self.assertEqual(paper_kind(item),'plos')
        self.assertEqual(academic_kind(item['source_url'],item),'plos')
        self.assertEqual(doi_for(item),'10.1371/journal.pone.0312345')
        for url in ('https://api.plos.org/search?q=ai','https://journals.plos.org/plosone/',
                    'https://evil.journals.plos.org/plosone/article?id=10.1371/journal.pone.0312345',
                    'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0312345&id=10.1371/journal.pone.0999999'):
            with self.subTest(url=url):self.assertEqual(paper_kind({**item,'source_url':url}),'')
        resolver={**item,'source_url':'https://doi.org/10.1371/journal.pone.0999999'}
        self.assertEqual(paper_kind(resolver),'')

    def test_plos_collector_research_type_survives_normalization_without_changing_old_projection(self):
        from briefing_contract import normalize_briefing_config
        from test_daily_pipeline import config
        item,cap=material();doi='10.1371/journal.pone.0312345'
        item.update(source_url='https://doi.org/'+doi,article_type='Research Article',title='Synthetic PLOS paper',
                    facts='Synthetic fact.',judgment='Synthetic limitation.',relevance='Synthetic learning.')
        item.pop('publication_type')
        cap.update(requested_url=item['source_url'])
        from source_capture import digest
        cap['record_sha256']=digest({k:v for k,v in cap.items() if k!='record_sha256'})
        item['source_capture']=cap
        self.assertEqual(paper_kind(item),'plos')
        raw=config([item]);raw['source_url_contract_version']=2
        canonical=normalize_briefing_config(raw)
        projected=canonical['sections'][0]['items'][0]
        self.assertEqual(projected['article_type'],'Research Article')
        self.assertEqual(paper_kind(projected),'plos')


if __name__=='__main__':unittest.main()
