"""Isolated/synthetic E2E. Review fixtures and mock uploads approve no real edition."""
import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
from source_pool import SourcePool,PoolConflict,task_spec
from source_worker import plan_sources,run_ready,source_snapshot,claim_discovery,submit_discovery,enqueue_captures,execute_existing
from source_preparation import packet,bind_candidate,check_pool_binding,orchestrate_sources
from source_capture import capture_path
from paper_identity import paper_kind,host
from daily_coverage_evidence import evidence_digest
from test_dated_source import collect as synthetic_query
from test_source_pool import material
import test_publication_v4 as v4
import test_release_protocol as reviewed
import daily_pipeline as dp
import publish_daily_to_oss as publisher


def discovery_fixture(request):
    day=date.fromisoformat(request['coverage_date']);start=day.isoformat()+'T00:00:00+08:00'
    end=(day+timedelta(days=1)).isoformat()+'T00:00:00+08:00'
    observation={'page_url':request['url'],'displayed_query':request['query'],'query_verified_in_UI':True,
      'recorded_at':end,'method':'supported_browser_dom','browser':'OFFLINE SYNTHETIC FIXTURE, not an actual browser review',
      'public_result_links':[],'result_links_observed':0,'no_results_message_observed':True,
      'next_page_link_observed':False,'scope':'observed_page_only','exhaustive_account_coverage':False,
      'zero_account_publications_established':False,'publication_dates_verified':False,'personalization_possible':True}
    raw=b'<html>OFFLINE synthetic anonymous transport fixture.</html>'
    receipt={'query_url':request['url'],'final_url':request['url'],'status_code':200,'retrieved_at':end,
      'coverage_start':start,'coverage_end':end,'hash_scope':'raw_http_bytes','body_base64':base64.b64encode(raw).decode(),
      'response_hash':hashlib.sha256(raw).hexdigest()}
    return {'evidence_type':'rendered_search_observation','version':1,'source_class':request['source_class'],
      'query_url':request['url'],'coverage_start':start,'coverage_end':end,'source_targets':request['source_targets'],
      'observation':observation,'observation_sha256':evidence_digest(observation)[7:],'http_receipt':receipt}


def collect_synthetic(pool,plan):
    hot=reviewed.daily_evidence(plan['coverage_date'])['social_search']['ai_hot_window']
    def execute(spec):
        if spec['kind']=='aihot':return {'ai_hot_window':copy.deepcopy(hot),'sections':[{'items':[]}]}
        if spec['source_id'] in ('aps-prx-dated','crossref-nmi-dated'):
            return synthetic_query(spec['source_id'],window=spec['coverage_date'])
        raise HTTPError('https://synthetic.invalid/',403,'',{},None)
    return run_ready(pool,max_tasks=32,executor=execute)


def complete_synthetic_discovery(pool,plan):
    for key in plan['tasks']:
        if pool.get(key)['spec']['kind']=='discovery':
            request=claim_discovery(pool,key)
            submit_discovery(pool,key,request['lease'],discovery_fixture(request['navigation']))


class SourcePreparationFlowTests(unittest.TestCase):
    setUp=v4.V4PublicationTests.setUp
    prepare=v4.V4PublicationTests.prepare
    write_candidate=v4.V4PublicationTests.write_candidate
    stage=v4.V4PublicationTests.stage
    complete=v4.V4PublicationTests.complete
    simulate_publish=v4.V4PublicationTests.simulate_publish

    def ready_candidate(self):
        self.prepare()
        self.pool=SourcePool(self.news/'_sources/pool.sqlite');self.addCleanup(self.pool.close)
        plan=plan_sources(self.pool,self.release)
        collect_synthetic(self.pool,plan);complete_synthetic_discovery(self.pool,plan)
        snapshot=source_snapshot(self.pool,plan)
        self.assertEqual(snapshot['status'],'coverage_ready')
        record=self.raw['coverage_evidence'][0]
        record['academic_search']=snapshot['academic'];record['academic_search_ref']=evidence_digest(snapshot['academic'])
        self.raw['academic_search']=snapshot['academic']
        social=record['social_search'];social['ai_hot_window']=snapshot['aihot']['ai_hot_window']
        social['source_class_evidence']=[r for r in social['source_class_evidence'] if r['source_class']=='ai_hot']+snapshot['supplementary_discovery']
        record['social_search_ref']=evidence_digest(social)
        self.references={}
        for section in self.raw['sections']:
            for item in section['items']:
                item['material_kind']='academic' if paper_kind(item) else 'social'
                capture=json.loads(capture_path(self.news,self.raw['date_range'],item['id']).read_text(encoding='utf-8'))
                ref=self.pool.put_material(host(item['source_url']),item,capture)
                self.references[item['id']]={key:ref[key] for key in ('material_id','revision')}
        self.raw['source_pool_binding']=bind_candidate(self.pool,self.raw,self.release,self.references)
        self.write_candidate()
        return plan

    def test_single_source_failure_preserves_success_and_allows_independent_authoring(self):
        self.prepare();pool=SourcePool(self.news/'_sources/pool.sqlite');self.addCleanup(pool.close)
        plan=plan_sources(pool,self.release)
        worked=collect_synthetic(pool,plan)
        self.assertTrue(any(row['state']=='blocked' for row in worked['processed']))
        succeeded={r['task_id']:r['result_sha'] for r in pool.tasks() if r['state']=='succeeded'}
        snapshot=source_snapshot(pool,plan)
        self.assertEqual(snapshot['status'],'coverage_pending')
        self.assertIn('author_admitted_materials',snapshot['allowed_actions'])
        self.assertEqual({m['source_id'] for m in snapshot['missing_tasks'] if m['kind']=='discovery'},
                         {'reputable_media','official_company_social','executive_social'})
        again=collect_synthetic(pool,plan)
        self.assertEqual(again['processed'],[])
        self.assertEqual(succeeded,{r['task_id']:r['result_sha'] for r in pool.tasks() if r['state']=='succeeded'})
        complete_synthetic_discovery(pool,plan)
        prepared=packet(pool,plan)
        self.assertEqual(prepared['status'],'coverage_ready')
        self.assertFalse(prepared['publication_approved'])
        self.assertEqual(prepared['semantic_review_status'],'not_reviewed')
        self.assertTrue(any(prepared['quantity_gaps'].values()))

    def test_full_synthetic_pool_to_generation_review_fixture_and_mock_publish_is_idempotent(self):
        self.ready_candidate();stage,_,manifest=self.stage()
        self.assertGreaterEqual(manifest['ranking']['academic'],self.raw['academic_delivery']['minimum_items'])
        self.assertGreaterEqual(manifest['ranking']['social'],self.raw['social_delivery']['minimum_items'])
        self.assertEqual(dp.verify_artifacts(stage,strict=True)['status'],'fail')
        self.simulate_publish(self.complete(stage))  # Existing mock transport; no real OSS or actual review.

    def test_material_update_invalidates_sealed_unpublished_run_without_overwriting_reviews(self):
        self.ready_candidate();stage,manifest_path,manifest=self.stage()
        reviewed.ReviewedReleaseTests._write_reviews(type('Fixture',(),{'stage':stage,'date':self.release,'manifest_path':manifest_path})())
        dp.cmd_seal_review(type('Args',(),{'run_dir':str(stage)})())
        reviews={p.name:p.read_bytes() for p in stage.glob('*review*.json')}
        config=json.loads((stage/manifest['artifacts']['delta_config']).read_text(encoding='utf-8'))
        item=config['sections'][0]['items'][0]
        source_id=item.get('source_candidate_id') or item['id'];ref=self.references[source_id]
        old=self.pool.material(ref['material_id'],ref['revision'])
        changed=copy.deepcopy(old['item']);changed['facts']='Changed synthetic claim; requires real re-review.'
        self.pool.put_material(old['source_id'],changed,old['capture'])
        result=dp.verify_artifacts(stage,strict=True)
        self.assertIn('pool_material_revision_changed',result['failures'])
        from release_audit import validate_bundle
        from daily_revisions import run_snapshot
        self.assertIn('pool_material_revision_changed',validate_bundle(stage,dp.load_json(manifest_path),require_manifest_binding=True))
        route=self.root/'news_publish.local.json'
        route.write_text(json.dumps({'site_index_url':'https://example.org/index.html','bucket':'example-bucket',
                         'region':'cn-hongkong','object_prefix':'','ossutil_profile':'fixture'}),encoding='utf-8')
        with patch.object(publisher,'upload_file') as upload, patch.object(publisher,'auto_publish_after_finalize') as remote, \
                patch.object(publisher,'upload_preview_file') as preview_upload,patch.object(publisher,'checked_site') as network:
            self.assertEqual(dp.cmd_seal_review(type('Args',(),{'run_dir':str(stage)})()),1)
            with self.assertRaises(publisher.PublishError):
                publisher.verified_release(stage)
            with self.assertRaises(publisher.PublishError):
                publisher.preview(stage,route,expected_run_sha256=run_snapshot(self.news,stage)['sha256'],
                                  expected_html_sha256=manifest['artifact_sha256']['html'])
            self.assertEqual(dp.cmd_finalize(type('Args',(),{'run_dir':str(stage),'strict':True,'require_remote':False,
                                               'correction_reason':None,'supersedes_hash':None})()),1)
            upload.assert_not_called()
            remote.assert_not_called()
            preview_upload.assert_not_called();network.assert_not_called()
        self.assertFalse((self.news/self.release/manifest_path.name).exists())
        self.assertEqual(reviews,{p.name:p.read_bytes() for p in stage.glob('*review*.json')})

    def test_unpublished_formal_upload_rejects_changed_material_but_published_history_remains_readable(self):
        self.ready_candidate();stage,_,_=self.stage();final=self.complete(stage)
        manifest=dp.load_json(final/f'daily_pipeline_manifest_{self.release}.json')
        ref=next(iter(manifest['source_pool_binding']['scope']['references'].values()))
        old=self.pool.material(ref['material_id'],ref['revision'])
        changed=copy.deepcopy(old['item']);changed['facts']='New synthetic revision.'
        self.pool.put_material(old['source_id'],changed,old['capture'])
        with self.assertRaises(publisher.PublishError):publisher.verified_release(final)
        receipt=self.news/'_publish'/f'oss_publish_receipt_{self.release}.json'
        receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps({'status':'published','date':self.release,
                          'html_sha256':manifest['artifact_sha256']['html']}),encoding='utf-8')
        self.assertEqual(dp.verify_artifacts(final,strict=True)['status'],'pass')

    def test_manifest_cannot_drop_pool_binding_while_config_retains_it(self):
        from source_preparation import check_run_pool_binding
        self.ready_candidate();stage,_,manifest=self.stage()
        config=dp.load_json(stage/manifest['artifacts']['delta_config'])
        manifest.pop('source_pool_binding')
        self.assertEqual(check_run_pool_binding(stage,manifest,config),['pool_manifest_binding_differs'])

    def test_unselected_material_update_does_not_block_unrelated_frozen_edition(self):
        self.ready_candidate();stage,_,manifest=self.stage()
        selected=manifest['source_pool_binding']['scope']['references']
        unused=next(key for key in self.references if key not in selected)
        ref=self.references[unused];old=self.pool.material(ref['material_id'],ref['revision'])
        changed=copy.deepcopy(old['item']);changed['facts']='Unselected synthetic update.'
        self.pool.put_material(old['source_id'],changed,old['capture'])
        self.assertEqual(dp.verify_artifacts(stage,strict=True,structure_only=True)['status'],'pass')

    def test_input_date_config_drift_and_uncommitted_discovery_cannot_bind(self):
        self.ready_candidate()
        binding=self.raw['source_pool_binding']
        changed=copy.deepcopy(self.raw);changed['summary']='Changed authored input'
        self.assertIn('pool_candidate_content_changed',check_pool_binding(self.news,binding,config=changed,release_date=self.release))
        self.assertIn('pool_release_date_changed',check_pool_binding(self.news,binding,release_date='2026-07-11'))
        self.raw['coverage_evidence'][0]['social_search']['source_class_evidence'].pop()
        with self.assertRaises(PoolConflict):bind_candidate(self.pool,self.raw,self.release,self.references)


class SourceProcessRecoveryTests(unittest.TestCase):
    def test_expired_worker_cannot_record_failure_or_stop_independent_task(self):
        from source_worker import code_binding
        with tempfile.TemporaryDirectory() as temporary,SourcePool(Path(temporary)/'pool.sqlite') as pool:
            for name in ('source-one','source-two'):
                pool.enqueue(task_spec('academic',name,'2026-10-14',{}, {'code':code_binding()}))
            clock=iter((1,902,903,904,905))
            def denied(spec):raise HTTPError('https://synthetic.invalid/',403,'',{},None)
            result=run_ready(pool,executor=denied,clock=lambda:next(clock))
            self.assertEqual([row['state'] for row in result['processed']],['lease_lost','blocked'])
            # Claiming an independent task no longer mutates other expired
            # leases; recovery happens when that exact task is reclaimed.
            self.assertEqual(pool.tasks()[0]['state'],'running')
            self.assertIsNone(pool.tasks()[0]['result'])
            self.assertEqual(pool.claim(task_id=pool.tasks()[0]['task_id'],now=906)['attempts'],2)

    def test_discovery_code_drift_between_claim_and_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary,SourcePool(Path(temporary)/'pool.sqlite') as pool:
            plan=plan_sources(pool,'2026-10-15')
            key=next(k for k in plan['tasks'] if pool.get(k)['spec']['kind']=='discovery')
            lease=claim_discovery(pool,key)
            with patch('source_worker.code_binding',return_value={'changed':'code'}):
                with self.assertRaises(PoolConflict):
                    submit_discovery(pool,key,lease['lease'],discovery_fixture(lease['navigation']))
            self.assertEqual(pool.get(key)['state'],'running')
            self.assertIsNone(pool.get(key)['result'])

    def test_status_is_read_only_even_when_current_code_has_no_registered_tasks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);database=root/'pool.sqlite'
            self.assertEqual(orchestrate_sources('2026-10-16',root,action='status')['status'],'not_initialized')
            self.assertFalse(database.exists())
            with SourcePool(database) as pool:plan_sources(pool,'2026-10-16')
            before=database.read_bytes();modified=database.stat().st_mtime_ns
            with patch('source_worker.code_binding',return_value={'new':'code'}):
                result=orchestrate_sources('2026-10-16',root,action='status')
            self.assertTrue(result['source_preparation']['missing_tasks'])
            self.assertEqual(database.read_bytes(),before)
            self.assertEqual(database.stat().st_mtime_ns,modified)

    def test_existing_capture_adapter_is_reused_offline_and_success_bytes_survive_repeat(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);news=root/'news';input_path=root/'capture-input.json'
            item,_=material();item['source_id']='plos-ai'
            input_path.write_text(json.dumps({'sections':[{'items':[item]}]}),encoding='utf-8')
            calls=[]
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def geturl(self):return item['source_url']
                def read(self,n):return b'<title>Synthetic research</title><p>Verified synthetic original excerpt.</p>'
            class Opener:
                def open(self,*args,**kwargs):calls.append(1);return Response()
            with SourcePool(news/'_sources/pool.sqlite') as pool, \
                    patch('source_capture.public_https'),patch('source_capture.build_opener',return_value=Opener()):
                keys=enqueue_captures(pool,input_path,news,'2026-10-14')
                result=run_ready(pool)
                self.assertEqual(result['processed'][0]['state'],'succeeded')
                artifact=capture_path(news,'2026-10-14','A1');before=artifact.read_bytes()
                self.assertEqual(len(calls),1)
                self.assertEqual(pool.db.execute('SELECT count(*) FROM materials').fetchone()[0],1)
                self.assertEqual(run_ready(pool)['processed'],[])
                self.assertEqual(len(calls),1);self.assertEqual(artifact.read_bytes(),before)
                self.assertEqual(enqueue_captures(pool,input_path,news,'2026-10-14'),keys)

    def test_capture_input_drift_is_detected_before_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);news=root/'news';input_path=root/'input.json';item,_=material()
            input_path.write_text(json.dumps({'sections':[{'items':[item]}]}),encoding='utf-8')
            with SourcePool(news/'_sources/pool.sqlite') as pool:
                key=enqueue_captures(pool,input_path,news,'2026-10-14')[0]
                input_path.write_text('{"sections":[]}',encoding='utf-8')
                with patch('source_capture.build_opener') as transport:
                    result=run_ready(pool)
                    transport.assert_not_called()
                self.assertEqual(result['processed'][0]['failure']['code'],'capture_input_changed')
                self.assertEqual(pool.get(key)['state'],'blocked')

    def test_actual_process_exit_before_and_after_commit_reenters_only_missing_work(self):
        for boundary in ('before_commit','after_commit'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as temporary:
                path=Path(temporary)/'pool.sqlite'
                with SourcePool(path) as pool:
                    spec=task_spec('academic','synthetic','2026-10-14',{},{});key=pool.enqueue(spec)
                    script="""import sys,os
sys.path.insert(0,%r)
from source_pool import SourcePool
pool=SourcePool(%r);row=pool.claim(task_id=%r,now=1)
if %r=='before_commit':
    with pool.transaction():
        pool.db.execute("UPDATE tasks SET state='succeeded' WHERE task_id=?",(%r,))
        os._exit(91)
else:
    pool.complete(%r,row['lease'],{'fixture':1},lambda s,r:[],now=2)
    os._exit(92)
"""%(str(SCRIPTS),str(path),key,boundary,key,key)
                    child=subprocess.run([sys.executable,'-B','-c',script],capture_output=True,text=True,timeout=15)
                    self.assertEqual(child.returncode,91 if boundary=='before_commit' else 92,child.stderr)
                    row=pool.get(key)
                    if boundary=='before_commit':
                        self.assertEqual(row['state'],'running');lease=pool.claim(task_id=key,now=400)
                        self.assertEqual(lease['attempts'],2)
                        pool.complete(key,lease['lease'],{'fixture':1},lambda s,r:[],now=401)
                    else:
                        self.assertEqual(row['state'],'succeeded');self.assertIsNone(pool.claim(task_id=key,now=400))
                        pool.complete(key,row['lease'],{'fixture':1},lambda s,r:[],now=401)
                    self.assertEqual(pool.get(key)['state'],'succeeded')

    def test_capture_result_and_material_commit_are_one_transaction(self):
        with tempfile.TemporaryDirectory() as temporary,SourcePool(Path(temporary)/'news/_sources/pool.sqlite') as pool:
            item,capture=material()
            spec=task_spec('capture','plos-ai','2026-10-14',{'item':item},{})
            key=pool.enqueue(spec);lease=pool.claim(task_id=key,now=1)
            with patch.object(pool,'_event',side_effect=RuntimeError('injected commit boundary')):
                with self.assertRaises(RuntimeError):pool.complete(key,lease['lease'],{'record':capture},lambda s,r:[],now=2)
            self.assertEqual(pool.get(key)['state'],'running')
            self.assertEqual(pool.db.execute('SELECT count(*) FROM materials').fetchone()[0],0)
            pool.complete(key,lease['lease'],{'record':capture},lambda s,r:[],now=3)
            self.assertEqual(pool.db.execute('SELECT count(*) FROM materials').fetchone()[0],1)


if __name__=='__main__':unittest.main()
