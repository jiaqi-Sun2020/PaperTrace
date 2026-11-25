"""Actual daily CLI + source adapters + strict lifecycle; synthetic reviews/OSS.

These fixtures certify transitions only. They approve no news/story or display.
"""
import base64,copy,hashlib,html,io,json,os,sys,unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from xml.sax.saxutils import escape
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(SCRIPTS))
import orchestrate_daily as o
import source_worker as w
import daily_pipeline as dp
import publish_daily_to_oss as publisher
import ai_social_sources as ai
import test_publication_v4 as v4
import test_release_protocol as reviewed
from source_pool import SourcePool
from source_preparation import bind_candidate
from source_capture import make_capture,capture_path
from paper_identity import paper_kind,host
from daily_coverage_evidence import evidence_digest
from test_source_preparation_flow import complete_synthetic_discovery
from test_dated_source import collect,doc
from academic_sources import sources_by_id

DAY='2026-10-17';COVER='2026-10-16'

class RecoveryTraceTests(unittest.TestCase):
    setUp=v4.V4PublicationTests.setUp
    prepare=v4.V4PublicationTests.prepare
    write_candidate=v4.V4PublicationTests.write_candidate
    stage=v4.V4PublicationTests.stage

    def entry(self,action,policy=False):
        argv=['daily','--date',DAY,'--action',action]
        if action not in ('status','diagnose'):argv.append('--record')
        if policy:argv+=['--recovery-policy',str(self.policy_path)]
        with redirect_stdout(io.StringIO()) as stream:
            code=o.main(argv)
        value=json.loads(stream.getvalue());self.trace.append({'action':action,'exit_code':code,'phase':value.get('phase'),
             'run_outcome':value.get('run_outcome'),'content_readiness':value.get('content_readiness'),
             'recovery':value.get('recovery'),'terminal_blocker':value.get('terminal_blocker')})
        return value

    def initial(self):
        # A fixed edition fixture must not depend on the wall-clock calendar.
        clock_patch=patch('time.time',return_value=datetime.fromisoformat(DAY+'T15:00:00+08:00').timestamp())
        clock_patch.start();self.addCleanup(clock_patch.stop)
        self.trace=[]
        self.prepare();self.release=DAY
        self.raw['date_range']=COVER;self.raw['collection_completed_at']=DAY+'T09:00:00+08:00'
        self.raw['coverage_evidence']=[reviewed.daily_evidence(COVER)]
        # Preserve the fixture's stricter 7-item / at-most-6-new policy. Move
        # its synthetic prior observations with the scenario, not the policy.
        index=self.news/'_index/story_index.jsonl'
        prior=[json.loads(line) for line in index.read_text(encoding='utf-8').splitlines() if line]
        for row in prior:row['last_seen']=COVER
        index.write_text(''.join(json.dumps(row)+'\n' for row in prior),encoding='utf-8');self.index_before=index.read_bytes()
        self.args=dp.parse_args(['run','--config',str(self.candidate),'--date',DAY,
              '--coverage-start',COVER+'T00:00:00+08:00','--coverage-end',DAY+'T00:00:00+08:00'])
        self.root_patch=patch.object(o,'NEWS_ROOT',self.news);self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.entry('plan')
        self.pool=SourcePool(self.news/'_sources/pool.sqlite');self.addCleanup(self.pool.close)
        self.plan=w.plan_sources(self.pool,DAY)
        def execute(spec):
            source=spec['source_id']
            if source=='aps-prx-dated':return collect(source,[doc(sources_by_id()[source],COVER,n) for n in range(4)],window=COVER)
            if source in ('crossref-quantum-dated','crossref-nmi-dated'):return collect(source,window=COVER)
            if spec['kind']=='aihot':return {'ai_hot_window':reviewed.daily_evidence(COVER)['social_search']['ai_hot_window'],'sections':[{'items':[]}]}
            if spec['kind']=='fixed_source':
                declared=ai.registered(source);hostname=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(declared['url']).hostname
                if 'feed' in declared['url'] or source=='openai-news':
                    body=('<rss><channel>'+''.join('<item><title>Synthetic</title><link>'+escape('https://'+hostname+'/story/'+str(n))+'</link><pubDate>Fri, 16 Oct 2026 12:00:00 GMT</pubDate></item>' for n in range(2))+'</channel></rss>').encode()
                else:body=('<html><a href="https://'+hostname+'/news/synthetic">Synthetic original</a></html>').encode()
                def fetch(url):return body,{'query_url':url,'final_url':url,'status_code':200,'retrieved_at':DAY+'T01:00:00Z','response_hash':hashlib.sha256(body).hexdigest(),'hash_scope':'decoded_representation_bytes'}
                return ai.collect(source,COVER,fetch=fetch)
            raise HTTPError('https://synthetic.invalid/',403,'SYNTHETIC',{},None)
        w.run_ready(self.pool,coverage_date=COVER,max_tasks=32,executor=execute)
        complete_synthetic_discovery(self.pool,self.plan)
        self.policy_path=self.root/'approved-fixture-policy.json'
        self.policy_path.write_text(json.dumps({'version':1,'enabled':True,'timezone':'Asia/Shanghai',
            'not_before':DAY+'T00:00:00+08:00','deadline':DAY+'T23:59:00+08:00',
            'minimum_interval_seconds':60,'max_recheck_tasks':3,'max_tasks_per_invocation':3}),encoding='utf-8')
        value=self.entry('status')
        self.assertEqual(value['phase'],'candidate_shortage',value)
        self.assertEqual(value['source_preparation']['source_preparation']['status'],'coverage_ready')
        self.assertEqual(value['content_readiness']['counts']['academic']['discovered'],4)
        self.assertEqual(value['content_readiness']['counts']['academic']['qualified'],0)

    def write_trace(self,name):
        if os.environ.get('PAPERTRACE_TEST_EVIDENCE'):
            p=Path(os.environ['PAPERTRACE_TEST_EVIDENCE']);p.mkdir(parents=True,exist_ok=True)
            (p/name).write_text(json.dumps({'simulation_only':True,'release_date':DAY,'coverage_date':COVER,
                'trace':self.trace,'no_real_network':True,'no_real_semantic_review':True,'no_real_display_review':True},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def test_thin_pool_to_recovery_qualification_strict_review_and_ack_loss_mock_publish(self):
        self.initial()
        original={t['task_id']:t for t in self.pool.tasks()}
        def late(spec):
            self.assertEqual(spec['coverage_date'],COVER)
            source=spec['source_id']
            docs=[doc(sources_by_id()[source],COVER,n) for n in range(6)] if source=='aps-prx-dated' else []
            return collect(source,docs,window=COVER)
        with patch.object(w,'execute_existing',side_effect=lambda spec,unused:late(spec)):
            value=self.entry('continue',policy=True)
        self.assertEqual(value['phase'],'article_qualification_pending',value)
        self.assertEqual(value['content_readiness']['counts']['academic']['discovered'],6)
        self.assertEqual(value['content_readiness']['counts']['academic']['qualified'],0)
        self.assertEqual(original,{k:self.pool.get(k) for k in original})
        with patch.object(w,'execute_existing',side_effect=AssertionError('no repeat')):
            self.entry('recover',policy=True)
        snapshot=w.source_snapshot(self.pool,self.plan)
        record=self.raw['coverage_evidence'][0]
        record['academic_search']=snapshot['academic'];record['academic_search_ref']=evidence_digest(snapshot['academic'])
        self.raw['academic_search']=snapshot['academic']
        social=record['social_search'];social['ai_hot_window']=snapshot['aihot']['ai_hot_window'];social['ai_fixed_pool']=snapshot['ai_fixed_pool']
        social['source_class_evidence']=[r for r in social['source_class_evidence'] if r['source_class']=='ai_hot']+snapshot['supplementary_discovery']
        record['social_search_ref']=evidence_digest(social)
        references={}
        for section in self.raw['sections']:
            for item in section['items']:
                item['published_at']=COVER;item['material_kind']='academic' if paper_kind(item) else 'social'
                body=('<title>Original source '+item['id']+'</title><p>'+html.escape(item['source_excerpt'])+'</p>').encode()
                capture=make_capture(item,item['source_url'],item['source_url'],200,body,self.raw['collection_completed_at'])
                path=capture_path(self.news,COVER,item['id']);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(capture),encoding='utf-8')
                ref=self.pool.put_material(host(item['source_url']),item,capture)
                references[item['id']]={key:ref[key] for key in ('material_id','revision')}
        self.trace.append({'action':'synthetic_agent_article_capture_and_qualification','semantic_review':'not_performed_by_program'})
        self.raw['source_pool_binding']=bind_candidate(self.pool,self.raw,DAY,references);self.write_candidate()
        self.entry('status')
        stage,manifest_path,manifest=self.stage()
        self.assertEqual(dp.verify_artifacts(stage,strict=True)['status'],'fail')
        self.trace.append({'action':'stage','strict_status_before_review':'fail'})
        reviewed.ReviewedReleaseTests._write_reviews(SimpleNamespace(stage=stage,date=DAY,manifest_path=manifest_path))
        self.assertEqual(dp.cmd_seal_review(SimpleNamespace(run_dir=str(stage))),0)
        reviews={p.name:p.read_bytes() for p in stage.glob('*review*.json')}
        self.entry('work')  # Resume after fixture review: no acquisition and no inherited new approval.
        self.assertEqual(reviews,{p.name:p.read_bytes() for p in stage.glob('*review*.json')})
        self.assertEqual(dp.verify_artifacts(stage,strict=True)['status'],'pass')
        self.trace.append({'action':'synthetic_review_fixture','warning':'NOT actual content, blind or display approval','strict_status':'pass'})
        with patch.object(publisher,'auto_publish_after_finalize',return_value={'status':'disabled'}):
            self.assertEqual(dp.cmd_finalize(SimpleNamespace(run_dir=str(stage),strict=True,require_remote=False,correction_reason=None,supersedes_hash=None)),0)
        final=self.news/DAY;self.assertEqual(dp.verify_artifacts(final,strict=True)['status'],'pass')
        config=self.root/'news_publish.local.json';config.write_text(json.dumps({'site_index_url':'https://example.org/index.html','bucket':'example-bucket','region':'cn-hongkong','object_prefix':'','ossutil_profile':'fixture'}),encoding='utf-8')
        old='briefing_reader_2026-10-16.html';objects={'index.html':publisher._index_html(old).encode(),old:b'<html>old</html>'};uploads=[]
        def fetch(url):
            name=url.rsplit('/',1)[-1]
            if name not in objects:raise publisher.PublishError('synthetic 404',code='not_found')
            return url,objects[name]
        def upload(_config,path,name):
            uploads.append(name);objects[name]=path.read_bytes()
            if len(uploads)==1:raise publisher.PublishError('synthetic lost acknowledgement',code='transport_error')
        with patch.object(publisher,'fetch_html',side_effect=fetch),patch.object(publisher,'upload_file',side_effect=upload),patch.object(publisher,'read_bucket_index',side_effect=lambda config:objects['index.html']):
            self.assertEqual(publisher.enable(config)['status'],'enabled')
            self.assertEqual(publisher.publish(final,config)['status'],'pending')
            self.assertEqual(publisher.publish(final,config)['status'],'published')
            self.assertEqual(publisher.publish(final,config)['status'],'no_change')
        self.assertEqual(uploads,[f'briefing_reader_{DAY}.html','index.html'])
        self.trace.append({'action':'mock_publish_lost_ack_reconcile_repeat','uploads':uploads,'status':'simulated_site_verified','real_upload':False})
        self.write_trace('success-trace.json')

    def test_recovery_budget_ends_with_explicit_shortage_and_no_publication(self):
        self.initial()
        def unchanged(spec,unused):
            source=spec['source_id'];docs=[doc(sources_by_id()[source],COVER,n) for n in range(4)] if source=='aps-prx-dated' else []
            return collect(source,docs,window=COVER)
        with patch.object(w,'execute_existing',side_effect=unchanged):result=self.entry('recover',policy=True)
        self.assertEqual(result['phase'],'candidate_shortage')
        self.assertEqual(result['recovery']['status'],'recovery_budget_consumed')
        with patch.object(w,'execute_existing',side_effect=AssertionError('budget must stop')):self.entry('recover',policy=True)
        self.assertFalse((self.news/DAY).exists());self.assertFalse((self.news/'_publish'/f'oss_publish_receipt_{DAY}.json').exists())
        self.write_trace('shortage-trace.json')
