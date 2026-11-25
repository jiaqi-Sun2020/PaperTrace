"""Synthetic source, semantic and browser fixtures; real local gates and publisher logic."""
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime
import copy
import html
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import taskbox_daily as task
import taskbox_contract as contract
import daily_pipeline as pipeline
import daily_authoring as author
import daily_revisions as revisions
import orchestrate_daily as orchestrator
import publish_daily_to_oss as publisher
import release_audit as audit
from source_capture import make_capture, capture_path
from review_evidence import DISPLAY_CHECKS
import test_publication_v4 as fixtures
import test_release_protocol as review_fixtures

RECORDS = []
DAY = '2026-10-18'
DEPLOY_CONFIG = {'site_index_url':'https://example.org/index.html', 'bucket':'example-bucket',
                 'region':'cn-hongkong', 'object_prefix':'', 'ossutil_profile':'fixture'}
DEPLOY = publisher.deployment_id(DEPLOY_CONFIG)


class TaskboxTests(unittest.TestCase):
    prepare = fixtures.V4PublicationTests.prepare
    write_candidate = fixtures.V4PublicationTests.write_candidate

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='case-'))
        self.news = self.root / 'news'
        for module in (pipeline, orchestrator):
            scope = patch.object(module, 'NEWS_ROOT', self.news)
            scope.start(); self.addCleanup(scope.stop)
        output = redirect_stdout(io.StringIO()); output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)

    def record(self, **extra):
        value = {'case':self.id(), 'status':'pass', 'fixture_root':str(self.root), **extra}
        RECORDS.append(value)
        (self.root/'CASE.json').write_text(json.dumps(value, indent=2), encoding='utf-8')

    def staged(self, taskbox=True):
        self.prepare()
        self.release = DAY
        self.raw.update(date_range='2026-10-17', collection_completed_at=DAY+'T01:30:00+08:00',
                        coverage_evidence=[review_fixtures.daily_evidence('2026-10-17')],
                        news_feedback_version=1, authoring_status='complete')
        fixtures.use_v4(self.raw)
        for section in self.raw['sections']:
            for item in section['items']:
                item['published_at'] = '2026-10-17'
                body = ('<title>OFFLINE synthetic article</title><p>'+html.escape(item['source_excerpt'])+'</p>').encode('utf-8')
                pipeline.atomic_json(capture_path(self.news,'2026-10-17',item['id']),
                    make_capture(item,item['source_url'],item['source_url'],200,body,self.raw['collection_completed_at']))
        index = self.news/'_index/story_index.jsonl'
        prior = [json.loads(line) for line in index.read_text().splitlines() if line]
        for row in prior: row['last_seen']='2026-10-17'
        index.write_text(''.join(json.dumps(row)+'\n' for row in prior), encoding='utf-8')
        self.index_before = index.read_bytes()
        if taskbox:
            task.save_candidate(DAY,'absent',self.raw,DEPLOY)
            self.assertEqual(task.main(['stage','--date',DAY]),0)
        else:
            saved=author.save(self.news,DAY,'candidate','absent',self.raw)
            self.assertEqual(pipeline.main(['run','--config',saved['path'],'--date',DAY,
                '--coverage-start','2026-10-17T00:00:00+08:00',
                '--coverage-end','2026-10-18T00:00:00+08:00']),0)
        stage = revisions.active_stages(self.news,DAY)[0]
        if taskbox:
            self.assertEqual(task.main(['templates','--date',DAY,'--run-dir',str(stage)]),0)
        else:
            self.assertEqual(pipeline.main(['review-template','--run-dir',str(stage)]),0)
        manifest = pipeline.load_json(stage/f'daily_pipeline_manifest_{DAY}.json')
        return stage, manifest

    def fixture_reviews(self, stage, manifest):
        # Existing review helper is solely a synthetic fixture builder; it never
        # stands in for actual source/semantic/browser checking in a real run.
        review_fixtures.ReviewedReleaseTests._write_reviews(SimpleNamespace(stage=stage,date=DAY,
            manifest_path=stage/f'daily_pipeline_manifest_{DAY}.json'))
        values = {kind:pipeline.load_json(stage/audit.REVIEW_NAMES[kind].format(date=DAY))
                  for kind in ('news_review','story_review')}
        config = pipeline.load_json(stage/manifest['artifacts']['delta_config'])
        by_id = {i['id']:i for s in config['sections'] for i in s['items']}
        if 'taskbox_contract' in manifest:
            for value in values.values(): value['taskbox_context']=dict(contract.CONTEXT)
        for row in values['news_review']['items']:
            capture = by_id[row['item_id']]['source_capture']
            row['source_crosscheck'] = {'capture_record_sha256':capture['record_sha256'],
                'response_sha256':capture['response_sha256'], 'quoted_excerpt':capture['quoted_excerpt'],
                'checked_at':DAY+'T03:00:00+08:00', 'reading_scope':'captured_primary_excerpt'}
        third = values['story_review']['rounds'][2]
        third.update(unresolved=[], cross_surface_checks={'judgment':'pass','reason':'Synthetic surface fixture only'},
            display_review={'version':1,'status':'pass','html_sha256':manifest['artifact_sha256']['html'],
                'checks':[{'id':key,'status':'pass','evidence':{'type':'actual_browser',
                    'reference':'OFFLINE SYNTHETIC FIXTURE ONLY','environment':'OFFLINE SYNTHETIC FIXTURE ONLY',
                    'observed_at':DAY+'T03:00:00+08:00'}} for key in sorted(DISPLAY_CHECKS)]})
        # Restore genuine blank templates before testing the real owner writes.
        for kind in ('news_review','story_review'):
            (stage/audit.REVIEW_NAMES[kind].format(date=DAY)).unlink()
        if 'taskbox_contract' in manifest:
            self.assertEqual(task.main(['templates','--date',DAY]),0)
        else:
            self.assertEqual(pipeline.main(['review-template','--run-dir',str(stage)]),0)
        return values

    def save_values(self, stage, values):
        for kind, value in values.items():
            name = kind.replace('_','-')
            path = stage/audit.REVIEW_NAMES[kind].format(date=DAY)
            task.save_review(DAY,name,author.digest(path),value,stage)

    def test_templates_do_not_approve_sources_or_display(self):
        stage, manifest = self.staged()
        news = pipeline.load_json(stage/audit.REVIEW_NAMES['news_review'].format(date=DAY))
        self.assertEqual(news['review_method'],'self')
        self.assertEqual(news['taskbox_context'],contract.CONTEXT)
        self.assertTrue(all(r['judgment']=='unreviewed' and not r['source_crosscheck']['checked_at'] for r in news['items']))
        self.assertEqual(task.main(['seal','--date',DAY]),1)
        self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'fail')
        with patch.object(publisher,'upload_file') as upload:
            with self.assertRaises(publisher.PublishError): publisher.verified_release(stage)
        upload.assert_not_called()
        self.record(blank_templates_not_approval=True, review_context='same_task_self', strict='fail')

    def test_same_task_source_display_seal_finalize_and_existing_publish_idempotent(self):
        stage, manifest = self.staged()
        values = self.fixture_reviews(stage,manifest); self.save_values(stage,values)
        self.assertEqual(task.main(['seal','--date',DAY]),0)
        self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'pass')
        with patch.object(publisher,'auto_publish_after_finalize',side_effect=AssertionError('implicit upload forbidden')):
            self.assertEqual(task.main(['finalize','--date',DAY]),0)
        final = self.news/DAY
        self.assertEqual(pipeline.verify_artifacts(final,strict=True)['status'],'pass')
        route = self.root/'news_publish.local.json'
        route.write_text(json.dumps(DEPLOY_CONFIG),encoding='utf-8')
        old = 'briefing_reader_2026-10-17.html'
        objects = {'index.html':publisher._index_html(old).encode(),old:b'<html>old synthetic edition</html>'}
        uploads=[]
        def fetch(url):
            name=url.rsplit('/',1)[-1]
            if name not in objects: raise publisher.PublishError('fixture missing',code='not_found')
            return url,objects[name]
        def upload(config,path,name): objects[name]=path.read_bytes(); uploads.append(name)
        with patch.object(publisher,'fetch_html',side_effect=fetch),patch.object(publisher,'upload_file',side_effect=upload),\
             patch.object(publisher,'read_bucket_index',side_effect=lambda c:objects['index.html']):
            self.assertEqual(publisher.enable(route)['status'],'enabled')
            first=task.publish(DAY,route,DEPLOY,allow_network=True)
            second=task.publish(DAY,route,DEPLOY,allow_network=True)
        self.assertEqual(first['status'],'published_verified',first)
        self.assertEqual(second['publisher']['status'],'no_change',second)
        self.assertEqual(uploads,[f'briefing_reader_{DAY}.html','index.html'])
        self.record(strict='pass',local_finalized=True,mock_publication='published_verified',repeat='no_change',
                    mock_uploads=uploads,substitutes='All source/semantic/display evidence and remote transport are synthetic. No real edition approved.')

    def test_claim_source_and_display_failures_block_seal(self):
        stage,manifest=self.staged(); baseline=self.fixture_reviews(stage,manifest)
        attacks = ('unchecked_claim','missing_source_crosscheck','stale_capture_hash',
            'missing_display','false_independence','story_false_independence',
            'missing_context','numeric_review_context','stale_html','null_display','empty_display',
            'missing_display_check','duplicate_display_check','pending_display',
            'failed_display','synthetic_evidence_type','missing_display_reference',
            'future_display_observation','naive_display_observation',
            'outside_capture_anchor','stale_claim_digest','stale_story_digest',
            'news_version_bool','story_version_downgrade','display_version_bool',
            'missing_news_item','duplicate_story_round','missing_rounds')
        passed=[]
        for attack in attacks:
            with self.subTest(attack=attack):
                values=copy.deepcopy(baseline)
                news=values['news_review']; story=values['story_review']
                row=news['items'][0]; third=story['rounds'][2]
                display=third['display_review']; check=display['checks'][0]
                if attack=='unchecked_claim': row['claim_reviews']['facts']['verdict']='unreviewed'
                elif attack=='missing_source_crosscheck': row.pop('source_crosscheck')
                elif attack=='stale_capture_hash': row['source_crosscheck']['response_sha256']='0'*64
                elif attack=='missing_display': third.pop('display_review')
                elif attack=='false_independence': news['review_method']='independent'
                elif attack=='story_false_independence': story['review_method']='independent'
                elif attack=='missing_context': story.pop('taskbox_context')
                elif attack=='numeric_review_context': news['taskbox_context']['independent_review']=0
                elif attack=='stale_html': display['html_sha256']='0'*64
                elif attack=='null_display': third['display_review']=None
                elif attack=='empty_display': third['display_review']={}
                elif attack=='missing_display_check': display['checks'].pop()
                elif attack=='duplicate_display_check': display['checks'][1]=copy.deepcopy(check)
                elif attack=='pending_display': display['status']='pending'
                elif attack=='failed_display': check['status']='fail'
                elif attack=='synthetic_evidence_type': check['evidence']['type']='static_html'
                elif attack=='missing_display_reference': check['evidence']['reference']=''
                elif attack=='future_display_observation': check['evidence']['observed_at']='2999-01-01T00:00:00+08:00'
                elif attack=='naive_display_observation': check['evidence']['observed_at']='2026-10-18T03:00:00'
                elif attack=='outside_capture_anchor': row['claim_reviews']['facts']['evidence_anchor']='unrelated unsupported statement'
                elif attack=='stale_claim_digest': row['claim_digest']='0'*64
                elif attack=='stale_story_digest': story['story_sha256']='0'*64
                elif attack=='news_version_bool': news['version']=True
                elif attack=='story_version_downgrade': story['review_protocol_version']=2
                elif attack=='display_version_bool': display['version']=True
                elif attack=='missing_news_item': news['items'].pop()
                elif attack=='duplicate_story_round': story['rounds'].append(copy.deepcopy(third))
                elif attack=='missing_rounds': story['rounds']=None
                for kind,value in values.items():
                    path=stage/audit.REVIEW_NAMES[kind].format(date=DAY)
                    # Simulate a bypass of taskbox's writer to exercise the real
                    # downstream gates, including malformed version attacks.
                    pipeline.atomic_json(path,value)
                before_manifest=(stage/f'daily_pipeline_manifest_{DAY}.json').read_bytes()
                with patch.object(publisher,'upload_file') as upload:
                    self.assertNotEqual(task.main(['seal','--date',DAY]),0,attack)
                    self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'fail',attack)
                    self.assertNotEqual(task.main(['finalize','--date',DAY]),0,attack)
                    with self.assertRaises(publisher.PublishError): publisher.verified_release(stage)
                upload.assert_not_called()
                self.assertEqual((stage/f'daily_pipeline_manifest_{DAY}.json').read_bytes(),before_manifest)
                self.assertFalse((self.news/DAY/f'daily_pipeline_manifest_{DAY}.json').exists())
                passed.append(attack)
        self.record(attacks=len(passed),attack_branches=passed,all_rejected=len(passed)==len(attacks),no_publish=True)

    def test_taskbox_versions_cannot_downgrade_to_historical_routes(self):
        stage,manifest=self.staged()
        config_path=stage/manifest['artifacts']['delta_config']
        config=pipeline.load_json(config_path)
        changes=[('pipeline_version',v) for v in (1,2,3,5,True,4.0,None)]
        changes += [('coverage_evidence_contract_version',v) for v in (1,2,True,None)]
        changes += [('required_story_review_protocol',v) for v in (2,True,None)]
        changes += [('source_url_contract_version',v) for v in (1,True,None)]
        passed=[]
        for key,value in changes:
            with self.subTest(key=key,value=value):
                altered=copy.deepcopy(manifest);altered[key]=value
                # Unit-level classification is checked before invoking the real
                # common verifier; rejection must not be just an artifact hash.
                self.assertIn('taskbox_publication_versions_required',contract.validate_mode(altered,config))
                path=stage/f'daily_pipeline_manifest_{DAY}.json'
                pipeline.atomic_json(path,altered)
                self.assertEqual(pipeline.verify_artifacts(stage,strict=True,structure_only=True)['status'],'fail')
                passed.append([key,value])
        pipeline.atomic_json(stage/f'daily_pipeline_manifest_{DAY}.json',manifest)
        for version in (1,True,None):
            altered=copy.deepcopy(config);altered['source_url_contract_version']=version
            self.assertIn('taskbox_source_url_version_required',contract.validate_mode(manifest,altered))
        self.record(manifest_attacks=passed,source_url_config_attacks=3)

    def test_null_or_coerced_mode_declarations_cannot_become_historical(self):
        stage,manifest=self.staged(); config=pipeline.load_json(stage/manifest['artifacts']['delta_config'])
        attacks=('both_null','manifest_null','config_null','config_version_bool',
                 'numeric_manifest_context','numeric_config_context','unknown_mode_version','changed_source_policy')
        passed=[]
        for attack in attacks:
            with self.subTest(attack=attack):
                m=copy.deepcopy(manifest);c=copy.deepcopy(config)
                if attack=='both_null': m['taskbox_contract']=c['taskbox_contract']=None
                elif attack=='manifest_null': m['taskbox_contract']=None
                elif attack=='config_null': c['taskbox_contract']=None
                elif attack=='config_version_bool': c['taskbox_contract']['version']=True
                elif attack=='numeric_manifest_context': m['taskbox_contract']['review_context']['independent_review']=0
                elif attack=='numeric_config_context': c['taskbox_contract']['review_context']['independent_review']=0
                elif attack=='unknown_mode_version': m['taskbox_contract']['version']=c['taskbox_contract']['version']=2
                elif attack=='changed_source_policy': m['taskbox_contract']['source_policy']=c['taskbox_contract']['source_policy']='unchecked'
                self.assertIn('taskbox_contract_binding_invalid',contract.validate_mode(m,c))
                pipeline.atomic_json(stage/f'daily_pipeline_manifest_{DAY}.json',m)
                pipeline.atomic_json(stage/manifest['artifacts']['delta_config'],c)
                self.assertNotEqual(pipeline.main(['seal-review','--run-dir',str(stage)]),0)
                self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'fail')
                passed.append(attack)
        self.record(mode_attacks=passed)

    def test_capture_versions_and_bundle_consistency_remain_mandatory(self):
        stage,manifest=self.staged();values=self.fixture_reviews(stage,manifest);self.save_values(stage,values)
        config_path=stage/manifest['artifacts']['delta_config'];config=pipeline.load_json(config_path)
        bundle_path=stage/manifest['artifacts']['source_captures'];bundle=pipeline.load_json(bundle_path)
        from source_capture import digest
        passed=[]
        for version in (True,0,2,None):
            with self.subTest(version=version):
                c=copy.deepcopy(config);b=copy.deepcopy(bundle);n=copy.deepcopy(values['news_review'])
                item=c['sections'][0]['items'][0];capture=item['source_capture']
                capture['capture_version']=version
                capture['record_sha256']=digest({k:v for k,v in capture.items() if k!='record_sha256'})
                b['items'][capture['item_id']]=copy.deepcopy(capture)
                next(row for row in n['items'] if row['item_id']==item['id'])['source_crosscheck']['capture_record_sha256']=capture['record_sha256']
                # Rebind container hashes so rejection exercises source version
                # validation, not just the outer artifact SHA check.
                pipeline.atomic_json(config_path,c);pipeline.atomic_json(bundle_path,b)
                m=copy.deepcopy(manifest)
                for key,path in (('delta_config',config_path),('source_captures',bundle_path)):
                    m['artifact_sha256'][key]=author.digest(path)
                n['content_digest']=pipeline.content_digest(m)
                pipeline.atomic_json(stage/audit.REVIEW_NAMES['news_review'].format(date=DAY),n)
                pipeline.atomic_json(stage/f'daily_pipeline_manifest_{DAY}.json',m)
                issues=audit.validate_bundle(stage,m,require_manifest_binding=False,require_audit_report=False)
                self.assertTrue(any(code.startswith('taskbox_selected_source_capture_invalid:') for code in issues))
                self.assertNotEqual(pipeline.main(['seal-review','--run-dir',str(stage)]),0)
                self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'fail')
                passed.append(version)
        self.record(capture_version_attacks=passed,rehashed_bad_versions_rejected=True)

    def test_display_binds_actual_html_bytes_and_failed_reseal_keeps_prior_seal(self):
        stage,manifest=self.staged();values=self.fixture_reviews(stage,manifest);self.save_values(stage,values)
        self.assertEqual(task.main(['seal','--date',DAY]),0)
        manifest_path=stage/f'daily_pipeline_manifest_{DAY}.json'
        before_manifest=manifest_path.read_bytes()
        report_path=stage/audit.REVIEW_NAMES['release_audit'].format(date=DAY)
        before_report=report_path.read_bytes()
        story_path=stage/audit.REVIEW_NAMES['story_review'].format(date=DAY)
        bad=copy.deepcopy(values['story_review']);bad['rounds'][2].pop('display_review')
        author.save(self.news,DAY,'story-review',author.digest(story_path),bad,run_id=stage.name)
        self.assertNotEqual(task.main(['seal','--date',DAY]),0)
        self.assertEqual(manifest_path.read_bytes(),before_manifest)
        self.assertEqual(report_path.read_bytes(),before_report)
        pipeline.atomic_json(story_path,values['story_review'])
        page=stage/manifest['artifacts']['html']
        page.write_bytes(page.read_bytes()+b'<!-- new rendered bytes -->')
        issues=audit.validate_bundle(stage,pipeline.load_json(manifest_path),
            require_manifest_binding=False,require_audit_report=False)
        self.assertIn('taskbox_display_html_binding_invalid',issues)
        self.record(actual_bytes_bound=True,failed_reseal_preserved_previous_manifest_and_report=True)

    def test_new_review_context_cannot_erase_both_mode_markers(self):
        stage,manifest=self.staged();values=self.fixture_reviews(stage,manifest);self.save_values(stage,values)
        config_path=stage/manifest['artifacts']['delta_config']; config=pipeline.load_json(config_path)
        manifest.pop('taskbox_contract');config.pop('taskbox_contract')
        pipeline.atomic_json(config_path,config)
        issues=audit.validate_bundle(stage,manifest,require_manifest_binding=False,require_audit_report=False)
        self.assertIn('taskbox_contract_required_for_review_context',issues)
        self.record(stripped_mode_markers_rejected=True)

    def test_historical_missing_typed_display_retains_original_validation(self):
        # Created by the existing non-taskbox owner from the start, not a new
        # taskbox run stripped of its creation identity.
        stage,manifest=self.staged(taskbox=False);values=self.fixture_reviews(stage,manifest)
        values['story_review']['rounds'][2].pop('display_review')
        for kind,value in values.items(): pipeline.atomic_json(stage/audit.REVIEW_NAMES[kind].format(date=DAY),value)
        issues=audit.validate_bundle(stage,manifest,require_manifest_binding=False,require_audit_report=False)
        self.assertEqual(issues,[])
        self.assertEqual(pipeline.main(['seal-review','--run-dir',str(stage)]),0)
        self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'pass')
        self.record(historical_compatibility=True,created_without_taskbox=True)

    def test_full_mode_stripping_is_rejected_by_shared_owners(self):
        stage,manifest=self.staged();values=self.fixture_reviews(stage,manifest)
        config_path=stage/manifest['artifacts']['delta_config'];config=pipeline.load_json(config_path)
        manifest.pop('taskbox_contract');config.pop('taskbox_contract')
        pipeline.atomic_json(config_path,config)
        manifest['artifact_sha256']['delta_config']=author.digest(config_path)
        for value in values.values(): value.pop('taskbox_context')
        values['story_review']['rounds'][2].pop('display_review')
        values['news_review']['content_digest']=pipeline.content_digest(manifest)
        for kind,value in values.items(): pipeline.atomic_json(stage/audit.REVIEW_NAMES[kind].format(date=DAY),value)
        pipeline.atomic_json(stage/f'daily_pipeline_manifest_{DAY}.json',manifest)
        manifest_before=(stage/f'daily_pipeline_manifest_{DAY}.json').read_bytes()
        taskbox_codes={action:task.main([action,'--date',DAY,'--run-dir',str(stage)])
                       for action in ('seal','check','finalize')}
        shared_seal=pipeline.main(['seal-review','--run-dir',str(stage)])
        strict=pipeline.verify_artifacts(stage,strict=True)
        with patch.object(publisher,'auto_publish_after_finalize',side_effect=AssertionError('implicit upload forbidden')):
            shared_finalize=pipeline.main(['finalize','--run-dir',str(stage),'--strict','--local-only'])
        # Exercise the publisher's real content gate against a completed-layout
        # fixture even when finalize correctly refused. No transport is invoked.
        final=self.news/DAY
        if shared_finalize:
            import shutil
            for entry in stage.iterdir():
                if entry.is_file(): shutil.copy2(entry,final/entry.name)
            complete=pipeline.load_json(final/f'daily_pipeline_manifest_{DAY}.json')
            complete['status']='complete'
            pipeline.atomic_json(final/f'daily_pipeline_manifest_{DAY}.json',complete)
        route=self.root/'news_publish.local.json'
        route.write_text(json.dumps(DEPLOY_CONFIG),encoding='utf-8')
        with patch.object(publisher,'upload_file') as upload,patch.object(publisher,'checked_site') as site:
            taskbox_codes['publish']=task.main(['publish','--date',DAY,'--config',str(route),
                '--expected-deployment-id',DEPLOY,'--allow-network'])
            try:
                publisher.verified_release(final)
                publisher_gate='accepted'
            except publisher.PublishError:
                publisher_gate='rejected'
        upload.assert_not_called();site.assert_not_called()
        self.record(attack='full_mode_stripping_rebound_config_and_news_digest',
            status='pass' if shared_seal and shared_finalize and strict['status']=='fail' and publisher_gate=='rejected' else 'fail',
            taskbox_codes=taskbox_codes,shared_seal=shared_seal,strict_status=strict['status'],
            strict_failures=strict['failures'],shared_finalize=shared_finalize,publisher_gate=publisher_gate)
        self.assertTrue(all(code!=0 for code in taskbox_codes.values()))
        self.assertNotEqual(shared_seal,0)
        self.assertEqual(strict['status'],'fail')
        self.assertIn('taskbox_creation_contract_changed',strict['failures'])
        self.assertNotEqual(shared_finalize,0)
        self.assertEqual(publisher_gate,'rejected')
        self.assertEqual((stage/f'daily_pipeline_manifest_{DAY}.json').read_bytes(),manifest_before)

    def test_only_typed_actual_display_pending_is_preview_eligible(self):
        stage,manifest=self.staged();values=self.fixture_reviews(stage,manifest)
        third=values['story_review']['rounds'][2]
        third['judgment']='pending'
        third['unresolved']=[{'kind':'actual_display_pending','reason':'Synthetic browser pending'}]
        third['display_review']['status']='pending'
        third['display_review']['checks']=[{'id':key,'status':'pending'} for key in sorted(DISPLAY_CHECKS)]
        self.save_values(stage,values)
        self.assertEqual(audit.validate_bundle(stage,manifest,require_manifest_binding=False,
            require_audit_report=False,preview_display_pending=True),[])
        self.assertNotEqual(task.main(['seal','--date',DAY]),0)
        self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['status'],'fail')
        third.pop('display_review')
        pipeline.atomic_json(stage/audit.REVIEW_NAMES['story_review'].format(date=DAY),values['story_review'])
        self.assertTrue(audit.validate_bundle(stage,manifest,require_manifest_binding=False,
            require_audit_report=False,preview_display_pending=True))
        self.record(typed_preview_pending_only=True,pending_never_seals=True)

    def test_revision_invalidates_old_review_and_preserves_old_run(self):
        stage,manifest=self.staged(); values=self.fixture_reviews(stage,manifest); self.save_values(stage,values)
        candidate=revisions.candidate_path(self.news,DAY)
        original=candidate.read_bytes(); snapshot=revisions.run_snapshot(self.news,stage)
        result=revisions.revise(self.news,DAY,stage.name,snapshot['sha256'],author.digest(candidate),
                                'Synthetic taskbox revision',verify=pipeline.verify_artifacts)
        new=Path(result['candidate']); draft=pipeline.load_json(new)
        draft.update(authoring_status='complete',summary='Synthetic revised taskbox content')
        task.save_candidate(DAY,author.digest(new),draft,DEPLOY)
        self.assertEqual(task.main(['stage','--date',DAY]),0)
        self.assertEqual(task.main(['templates','--date',DAY]),0)
        new_stage=revisions.active_stages(self.news,DAY)[0]
        path=new_stage/audit.REVIEW_NAMES['news_review'].format(date=DAY)
        with self.assertRaisesRegex(author.AuthoringError,'review_binding_changed'):
            task.save_review(DAY,'news-review',author.digest(path),values['news_review'],new_stage)
        self.assertEqual(candidate.read_bytes(),original)
        self.assertEqual(revisions.run_snapshot(self.news,stage),snapshot)
        self.assertEqual(pipeline.verify_artifacts(stage,strict=True)['failures'],['staging_revision_superseded'])
        with self.assertRaises(ValueError): task.selected_stage('2026-10-19',new_stage)
        self.record(old_review_rejected=True,old_run_preserved=True,date_isolation=True,new_revision=result['revision_id'])

    def test_network_flags_and_destination_binding_prevent_wrong_publish(self):
        for action in ('collect','capture','publish'):
            self.assertEqual(task.main([action,'--date',DAY]),2)
        config=self.root/'news_publish.local.json'; config.write_text(json.dumps(DEPLOY_CONFIG),encoding='utf-8')
        with patch.object(publisher,'publish') as send,patch.object(publisher,'checked_site') as network:
            result=task.publish(DAY,config,'0'*64,allow_network=True)
        self.assertEqual(result['code'],'taskbox_destination_changed')
        send.assert_not_called(); network.assert_not_called()
        self.record(no_default_network=True,destination_mismatch_rejected=True)

    def test_contract_cannot_be_removed_from_manifest_or_change_destination(self):
        stage,manifest=self.staged()
        path=stage/f'daily_pipeline_manifest_{DAY}.json'
        manifest.pop('taskbox_contract'); pipeline.atomic_json(path,manifest)
        result=pipeline.verify_artifacts(stage,strict=True,structure_only=True)
        self.assertIn('taskbox_creation_contract_changed',result['failures'])
        self.record(contract_removal_rejected=True)
