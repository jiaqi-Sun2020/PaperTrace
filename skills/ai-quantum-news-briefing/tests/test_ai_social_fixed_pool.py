"""Bounded AI source adaptation; synthetic responses, no live credentials/network."""
import base64,copy,hashlib,json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from xml.sax.saxutils import escape
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import aihot_candidates as hot
import ai_social_sources as ai

DAY='2026-10-15'
def response(items,more=False,cursor=None,**changes):
    value={'schemaVersion':1,'query':{'mode':'selected','window':'7d','by':'published','category':None,'q':None},
           'items':items,'page':{'count':len(items),'hasMore':more,'nextCursor':cursor}}
    value.update(changes);return json.dumps(value)
def transport(body,url):
    return body,{'query_url':url,'final_url':url,'status_code':200,'retrieved_at':'2026-10-16T01:00:00Z',
                 'response_hash':hashlib.sha256(body.encode()).hexdigest()}
def rss(source_id,count=1,duplicate=False):
    source=ai.registered(source_id);host=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(source['url']).hostname
    rows=[]
    for i in range(count):
        url='https://'+host+'/article/'+str(0 if duplicate else i)+'?id=exact&view=full#source'
        rows.append('<item><title>Synthetic article '+str(i)+'</title><link>'+escape(url)+'</link><guid>g'+str(i)+'</guid><pubDate>Thu, 15 Oct 2026 12:00:00 GMT</pubDate></item>')
    return ('<rss><channel>'+''.join(rows)+'</channel></rss>').encode()
def observation(source_id='techcrunch-ai',body=None):
    body=rss(source_id) if body is None else body
    def fetch(url):
        return body,{'query_url':url,'final_url':url,'status_code':200,'retrieved_at':'2026-10-16T01:00:00Z',
                     'response_hash':hashlib.sha256(body).hexdigest(),'hash_scope':'decoded_representation_bytes'}
    return ai.collect(source_id,DAY,fetch=fetch)
def args(checkpoint=None):
    result=hot.parse_args(['--date','2026-10-16','--coverage-date',DAY,'--output','unused.json'])
    result.checkpoint=checkpoint;return result

class AISocialTests(unittest.TestCase):
    def test_aihot_v1_scope(self):
        a=hot.parse_args(['--date','2026-10-16','--coverage-date','2026-10-15','--output','unused.json'])
        s=hot.api_scope(a)
        self.assertEqual(s['base_url'],'https://aihot.news')
        self.assertEqual(s['params'],{'mode':'selected','limit':'50','window':'7d','by':'published'})

    def test_aihot_uses_original_link_and_preserves_two_times(self):
        row={'id':'item-a','title':'Synthetic news','source':{'name':'Synthetic'},
             'links':{'original':'https://example.org/news/a','aihot':'https://aihot.news/items/a'},
             'publishedAt':'2026-10-15T12:00:00Z','discoveredAt':'2026-10-16T00:00:00Z'}
        value=hot.item_to_briefing_item(row,1,'api')
        self.assertEqual(value['source_url'],row['links']['original'])
        self.assertEqual(value['discovered_at'],row['discoveredAt'])
        self.assertEqual(value['aggregation_url'],row['links']['aihot'])

    def test_fixed_sources_require_verified_registry(self):
        import ai_social_sources as ai
        self.assertEqual({r['id'] for r in ai.registry()},
                         {'openai-news','deepmind-news','anthropic-news','techcrunch-ai','ars-ai','verge-ai'})
        self.assertTrue(next(r for r in ai.registry() if r['id']=='openai-news')['discovery_only'])
        self.assertNotIn('help.openai.com',' '.join(r['url'] for r in ai.registry()))

    def test_api_identity_is_stable_when_display_order_changes(self):
        row={'id':'stable','title':'Synthetic','links':{'original':'https://example.org/a?x=1#part','aihot':'https://aihot.news/items/a'}}
        self.assertEqual(hot.item_to_briefing_item(row,1,'api')['id'],hot.item_to_briefing_item(row,99,'api')['id'])
        self.assertEqual(hot.item_to_briefing_item(row,1,'api')['source_url'],row['links']['original'])

    def test_discovery_time_cannot_replace_unknown_publication(self):
        body=response([{'id':'unknown','publishedAt':None,'discoveredAt':'2026-10-15T12:00:00Z'}])
        with patch.object(hot,'fetch_response',side_effect=lambda url:transport(body,url)):
            rows,evidence=hot.api_items(args())
        self.assertEqual(rows,[]);self.assertEqual(evidence['missing_timestamp_count'],1)
        self.assertEqual(evidence['coverage_status'],'partial')

    def test_api_count_mismatch_is_not_ready(self):
        value=json.loads(response([{'id':'a'}]));value['page']['count']=9
        with patch.object(hot,'fetch_response',side_effect=lambda url:transport(json.dumps(value),url)) as request:
            _,e=hot.api_items(args())
        self.assertEqual(request.call_count,1);self.assertEqual(e['coverage_status'],'partial')

    def test_api_query_mismatch_is_rejected(self):
        value=json.loads(response([]));value['query']['by']='timeline'
        with patch.object(hot,'fetch_response',side_effect=lambda url:transport(json.dumps(value),url)):
            _,e=hot.api_items(args())
        self.assertFalse(e['pagination_complete'])

    def test_duplicate_ids_across_pages_cannot_inflate_pool(self):
        bodies=[response([{'id':'a','publishedAt':'2026-10-15T12:00:00Z'}],True,'next'),response([{'id':'a','publishedAt':'2026-10-15T12:00:00Z'}])]
        with patch.object(hot,'fetch_response',side_effect=lambda url:transport(bodies.pop(0),url)):
            _,e=hot.api_items(args())
        self.assertFalse(e['pagination_complete']);self.assertEqual(e['failure'],'aihot_duplicate_identity')

    def test_api_400_stops_without_query_widening_or_fallback(self):
        with patch.object(hot,'fetch_response',side_effect=HTTPError('https://aihot.news/api/v1/items',400,'',{},None)) as request:
            _,e=hot.api_items(args())
        self.assertEqual(request.call_count,1);self.assertFalse(e['pagination_complete'])

    def test_cached_prefix_403_is_not_retried_from_page_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=args(Path(tmp)/'cache.json');body=response([])
            with patch.object(hot,'fetch_response',side_effect=lambda url:transport(body,url)):hot.api_items(a)
            with patch.object(hot,'fetch_response',side_effect=HTTPError('https://aihot.news/api/v1/items',403,'',{},None)) as request:
                _,e=hot.api_items(a)
            self.assertEqual(request.call_count,1);self.assertFalse(e['pagination_complete'])

    def test_etag_304_is_bound_to_cached_representation(self):
        body=response([])
        with patch.object(hot.urllib.request,'urlopen',side_effect=HTTPError('https://aihot.news/api/v1/items',304,'',{},None)) as request:
            restored,e=hot.fetch_response('https://aihot.news/api/v1/items',etag='"sample"',cached_body=body)
        self.assertEqual(restored,body);self.assertEqual(e['status_code'],304)
        self.assertEqual(e['response_hash'],hashlib.sha256(body.encode()).hexdigest())
        self.assertEqual(request.call_args.args[0].get_header('If-none-match'),'"sample"')

    def test_feed_is_discovery_not_full_publisher_coverage(self):
        v=observation();self.assertEqual(ai.validate(v,'techcrunch-ai',DAY),[])
        self.assertFalse(v['pagination_complete']);self.assertFalse(v['zero_publications_established'])
        self.assertEqual(v['candidates'][0]['published_at'],'2026-10-15T12:00:00+00:00')

    def test_malformed_feed_does_not_become_empty_success(self):
        with self.assertRaises(Exception):observation(body=b'<rss>broken')

    def test_valid_and_private_links_are_accounted_individually(self):
        body=rss('techcrunch-ai',2).replace(b'https://techcrunch.com/article/0',b'https://127.0.0.1/article/0')
        v=observation(body=body)
        self.assertEqual(v['candidate_count'],1);self.assertEqual(v['invalid_positions'],[0])

    def test_query_and_fragment_are_preserved(self):
        url=observation()['candidates'][0]['original_url']
        self.assertTrue(url.endswith('?id=exact&view=full#source'))

    def test_response_and_candidate_tampering_fail_replay(self):
        v=observation();changed=copy.deepcopy(v);changed['http']['response_hash']='a'*64
        self.assertTrue(ai.validate(changed,'techcrunch-ai',DAY))
        changed=copy.deepcopy(v);changed['candidates'][0]['title']='Changed claim'
        self.assertTrue(ai.validate(changed,'techcrunch-ai',DAY))

    def test_output_limit_preserves_full_response_and_count(self):
        v=observation(body=rss('techcrunch-ai',101))
        self.assertEqual((v['candidate_count'],v['emitted'],v['truncated']),(101,100,1))
        self.assertEqual(ai.validate(v,'techcrunch-ai',DAY),[])

    def test_duplicate_links_merge_discoveries_without_becoming_reviewed(self):
        v=observation();row=v['candidates'][0]
        snapshot={'ai_fixed_pool':{'observations':[v]},'aihot':{'sections':[{'items':[{'source_url':row['original_url'],'title':'Same report'}]}]}}
        p=ai.discovery_packet(snapshot)
        self.assertEqual(p['total'],1);self.assertEqual(len(p['candidates'][0]['discoveries']),2)
        self.assertFalse(p['publication_approved'])

    def test_column_dates_remain_unknown_until_original_read(self):
        v=observation('deepmind-news',b'<main><a href="/blog/a-real-report/">Synthetic official report</a></main>')
        self.assertIsNone(v['candidates'][0]['published_at'])

    def test_original_date_is_canonical_bound_and_ignores_related_articles(self):
        body=b'<link rel="canonical" href="https://example.org/main"><meta property="article:published_time" content="2026-10-15T12:00:00Z"><script type="application/ld+json">{"@type":"NewsArticle","url":"https://example.org/related","datePublished":"2020-01-01T00:00:00Z"}</script>'
        self.assertEqual(ai.article_publication(body,'https://example.org/main')['published_at'],'2026-10-15T12:00:00+00:00')

    def test_unknown_timezone_and_conflicting_original_dates_fail(self):
        for value in ('2026-10-15','2026-10-15T12:00:00'):
            with self.assertRaises(ValueError):ai.article_publication(('<meta property="article:published_time" content="'+value+'">').encode(),'https://example.org/main')
        body=b'<meta property="article:published_time" content="2026-10-15T12:00:00Z"><meta property="article:published_time" content="2026-10-15T13:00:00Z">'
        with self.assertRaisesRegex(ValueError,'conflict'):ai.article_publication(body,'https://example.org/main')

    def test_ai_capture_requires_original_date_not_discovery_time(self):
        from source_capture import make_capture,validate_capture
        item={'id':'AI-a','source_url':'https://example.org/main','source_excerpt':'A factual original sentence.',
              'source_class':'official_primary','published_at':'2026-10-15T12:00:00Z','ai_source_provenance':{'version':1}}
        body=b'<title>Report</title><meta property="article:published_time" content="2026-10-15T12:00:00Z"><p>A factual original sentence.</p>'
        capture=make_capture(item,item['source_url'],item['source_url'],200,body,'2026-10-16T01:00:00Z')
        self.assertEqual(validate_capture(item,capture),[])
        item['published_at']='2026-10-16T01:00:00Z'
        self.assertTrue(validate_capture(item,capture))
        with self.assertRaises(ValueError):make_capture(item,item['source_url'],item['source_url'],200,body,'2026-10-16T01:00:00Z')

    def test_pool_cannot_count_aggregation_as_a_third_article_class(self):
        p=ai.pool_evidence([observation()],DAY)
        self.assertEqual(p['missing_source_classes'],['official_primary']);self.assertTrue(ai.validate_pool(p,DAY))

    def test_ai_domain_work_uses_real_entry_without_claiming_quantum(self):
        import source_preparation as prep,source_worker as worker
        from source_pool import SourcePool
        body=response([{'id':'a','publishedAt':'2026-10-15T12:00:00Z','discoveredAt':'2026-10-16T00:00:00Z','links':{'original':'https://example.org/a','aihot':'https://aihot.news/items/a'}}])
        def fixed(url):
            source=next(s for s in ai.registry() if s['url']==url);source_id=source['id']
            raw=rss(source_id,4) if source['format']=='feed' else ('<a href="'+('/blog/article/' if source_id=='deepmind-news' else '/news/article/')+'">Synthetic original report</a>').encode()
            return raw,{'query_url':url,'final_url':url,'status_code':200,'retrieved_at':'2026-10-16T01:00:00Z',
                        'response_hash':hashlib.sha256(raw).hexdigest(),'hash_scope':'decoded_representation_bytes'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'news/_sources'
            with patch.object(hot,'fetch_response',side_effect=lambda url:transport(body,url)),patch.object(ai,'fetch_document',side_effect=fixed):
                result=prep.orchestrate_sources('2026-10-16',root,action='work',max_tasks=12,domain='ai-social')
                second=prep.orchestrate_sources('2026-10-16',root,action='work',max_tasks=12,domain='ai-social')
            with SourcePool(root/'pool.sqlite') as pool:
                untouched=[t for t in pool.tasks() if t['spec']['kind'] in ('academic','discovery')]
                self.assertTrue(untouched);self.assertTrue(all(t['attempts']==0 for t in untouched))
            self.assertEqual(result['source_preparation']['ai_fixed_pool']['status'],'discovery_available')
            self.assertEqual(result['source_preparation']['status'],'coverage_pending')
            self.assertEqual(second['work']['processed'],[])

    def test_original_403_stops_same_ai_host_and_continues_other_pool_candidate(self):
        from source_pool import SourcePool,task_spec
        import source_worker as worker
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            keys=[]
            for i,host in enumerate(('openai.com','openai.com','arstechnica.com')):
                item={'id':'x'+str(i),'source_url':'https://'+host+'/article','ai_source_provenance':{'version':1}}
                keys.append(pool.enqueue(task_spec('capture','source-'+str(i),DAY,{'item':item},{'code':worker.code_binding()})))
            calls=[]
            def denied(spec):calls.append(spec['source_id']);return {'capture_failures':[{'code':'source_access_denied','retryable':False,'http_status':403}]}
            worker.run_ready(pool,executor=denied,coverage_date=DAY)
            self.assertEqual(calls,['source-0','source-2']);self.assertEqual(pool.get(keys[1])['attempts'],0)
            worker.run_ready(pool,executor=denied,coverage_date=DAY)
            self.assertEqual(calls,['source-0','source-2'])

    def test_retry_after_is_honored_and_never_serializes_cookie_headers(self):
        import source_worker as worker
        for status in (429,503):
            d=worker.failure_for(HTTPError('https://synthetic.invalid/',status,'',{'Retry-After':'120','Set-Cookie':'DO-NOT-STORE'},None))
            self.assertEqual(d['retry_after_seconds'],120)
            self.assertNotIn('DO-NOT-STORE',json.dumps(d))

    def test_retry_after_beyond_scheduler_bound_stops_instead_of_retrying_early(self):
        import source_worker as worker
        for status in (429,503):
            d=worker.failure_for(HTTPError('https://synthetic.invalid/',status,'',{'Retry-After':'172800'},None))
            self.assertFalse(d['retryable'])
            self.assertEqual(d['code'],'source_rate_limit_deferred')

    def test_fixed_source_redirect_outside_registered_host_stops_before_follow(self):
        from urllib.request import Request
        redirect=ai.FixedRedirect()
        with self.assertRaisesRegex(ValueError,'ai_discovery_redirect_outside_pool'):
            redirect.redirect_request(Request('https://openai.com/news/rss.xml'),None,302,'',{},'https://other.invalid/feed')

    def test_fixed_403_stops_that_task_and_preserves_other_sources(self):
        from source_pool import SourcePool,task_spec
        import source_worker as worker
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            keys=[pool.enqueue(task_spec('fixed_source',name,DAY,{}, {'code':worker.code_binding()})) for name in ('openai-news','techcrunch-ai')]
            calls=[]
            def fetch(spec):
                calls.append(spec['source_id'])
                if spec['source_id']=='openai-news':raise HTTPError('https://openai.com/news/rss.xml',403,'',{},None)
                return observation()
            worker.run_ready(pool,coverage_date=DAY,executor=fetch)
            first=pool.get(keys[1])['result_sha']
            worker.run_ready(pool,coverage_date=DAY,executor=fetch)
            self.assertEqual(calls,['openai-news','techcrunch-ai'])
            self.assertEqual(pool.get(keys[0])['state'],'blocked');self.assertEqual(pool.get(keys[1])['result_sha'],first)

    def test_backup_is_not_claimed_when_primary_media_have_candidates(self):
        from source_pool import SourcePool,task_spec
        import source_worker as worker
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            for name in ('techcrunch-ai','ars-ai','verge-ai'):pool.enqueue(task_spec('fixed_source',name,DAY,{}, {'code':worker.code_binding()}))
            calls=[]
            def fetch(spec):calls.append(spec['source_id']);return observation(spec['source_id'],rss(spec['source_id'],4))
            worker.run_ready(pool,coverage_date=DAY,executor=fetch)
            self.assertEqual(calls,['techcrunch-ai','ars-ai'])

    def test_backup_uses_only_registered_entry_after_primary_failure(self):
        from source_pool import SourcePool,task_spec
        import source_worker as worker
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            for name in ('techcrunch-ai','ars-ai','verge-ai'):pool.enqueue(task_spec('fixed_source',name,DAY,{}, {'code':worker.code_binding()}))
            calls=[]
            def fetch(spec):
                calls.append(spec['source_id'])
                if spec['source_id']=='techcrunch-ai':raise HTTPError('https://techcrunch.com/',403,'',{},None)
                return observation(spec['source_id'],rss(spec['source_id'],4))
            worker.run_ready(pool,coverage_date=DAY,executor=fetch)
            self.assertEqual(calls,['techcrunch-ai','ars-ai','verge-ai'])

    def test_backup_becomes_eligible_after_original_access_denial(self):
        from source_pool import SourcePool,task_spec
        import source_worker as worker
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            for name in ('techcrunch-ai','ars-ai','verge-ai'):
                pool.enqueue(task_spec('fixed_source',name,DAY,{}, {'code':worker.code_binding()}))
            worker.run_ready(pool,coverage_date=DAY,executor=lambda spec:observation(spec['source_id'],rss(spec['source_id'],4)))
            item={'id':'blocked-original','source_url':'https://techcrunch.com/article/blocked','ai_source_provenance':{'version':1}}
            pool.enqueue(task_spec('capture','techcrunch-ai',DAY,{'item':item},{'code':worker.code_binding()}))
            worker.run_ready(pool,coverage_date=DAY,executor=lambda spec:{'capture_failures':[{'code':'source_access_denied','retryable':False,'http_status':403}]})
            calls=[]
            def fetch(spec):calls.append(spec['source_id']);return observation(spec['source_id'],rss(spec['source_id'],4))
            worker.run_ready(pool,coverage_date=DAY,executor=fetch)
            self.assertEqual(calls,['verge-ai'])

    def test_fixed_pool_cannot_waive_unchanged_quantum_search_gate(self):
        from daily_coverage_evidence import validate_social_search
        from test_release_protocol import daily_evidence
        social=daily_evidence(DAY)['social_search']
        social['ai_fixed_pool']=ai.pool_evidence([observation(),observation('openai-news')],DAY)
        self.assertEqual(validate_social_search(social,DAY),[])
        social['source_class_evidence']=[]
        self.assertTrue(validate_social_search(social,DAY))

    def test_new_date_binding_requires_exact_committed_fixed_observations(self):
        from source_pool import SourcePool,PoolConflict
        from source_worker import plan_sources,run_ready,source_snapshot
        from source_preparation import source_evidence_references
        from test_source_preparation_flow import complete_synthetic_discovery
        from test_dated_source import collect as synthetic_query
        from test_release_protocol import daily_evidence
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'news/_sources/pool.sqlite') as pool:
            plan=plan_sources(pool,'2026-10-16')
            def execute(spec):
                if spec['kind']=='fixed_source':return observation(spec['source_id'])
                if spec['kind']=='aihot':return {'ai_hot_window':daily_evidence(DAY)['social_search']['ai_hot_window'],'sections':[{'items':[]}]}
                if spec['source_id'] in ('aps-prx-dated','crossref-nmi-dated'):return synthetic_query(spec['source_id'],window=DAY)
                raise HTTPError('https://synthetic.invalid/',403,'',{},None)
            run_ready(pool,max_tasks=32,executor=execute,coverage_date=DAY)
            complete_synthetic_discovery(pool,plan)
            snapshot=source_snapshot(pool,plan)
            self.assertEqual(snapshot['status'],'coverage_ready')
            social=daily_evidence(DAY)['social_search']
            social['ai_hot_window']=snapshot['aihot']['ai_hot_window']
            social['source_class_evidence']=[r for r in social['source_class_evidence'] if r['source_class']=='ai_hot']+snapshot['supplementary_discovery']
            config={'coverage_evidence':[{'date':DAY,'academic_search':snapshot['academic'],'social_search':social}]}
            with self.assertRaisesRegex(PoolConflict,'pool_ai_fixed_observations_missing'):
                source_evidence_references(pool,config,'2026-10-16')
            social['ai_fixed_pool']=snapshot['ai_fixed_pool']
            refs=source_evidence_references(pool,config,'2026-10-16')
            self.assertTrue(any(pool.get(r['task_id'])['spec']['kind']=='fixed_source' for r in refs))
            social['ai_fixed_pool']['observations'][0]['candidates'][0]['title']='Changed after commit'
            with self.assertRaises(PoolConflict):source_evidence_references(pool,config,'2026-10-16')

    def test_fixed_record_date_and_source_scope_changes_are_rejected(self):
        value=observation()
        self.assertTrue(ai.validate(value,'ars-ai',DAY));self.assertTrue(ai.validate(value,'techcrunch-ai','2026-10-14'))
        value['exhaustive_publisher_coverage']=True
        self.assertTrue(ai.validate(value,'techcrunch-ai',DAY))

    def test_current_ai_worker_does_not_claim_other_days(self):
        from source_pool import SourcePool,task_spec
        import source_worker as worker
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            old=pool.enqueue(task_spec('fixed_source','techcrunch-ai','2026-10-14',{}, {'code':worker.code_binding()}))
            current=pool.enqueue(task_spec('fixed_source','techcrunch-ai',DAY,{}, {'code':worker.code_binding()}))
            worker.run_ready(pool,coverage_date=DAY,executor=lambda spec:observation())
            self.assertEqual(pool.get(old)['attempts'],0);self.assertEqual(pool.get(current)['state'],'succeeded')

    def test_old_checkpoint_is_backed_up_without_cursor_reuse(self):
        from collection_checkpoint import save_checkpoint
        with tempfile.TemporaryDirectory() as tmp:
            a=args(Path(tmp)/'old.json');save_checkpoint(a.checkpoint,{'kind':'old_public_api'}, {'responses':[{'old':'unchanged'}]})
            original=a.checkpoint.read_bytes();urls=[]
            def fetch(url):urls.append(url);return transport(response([]),url)
            with patch.object(hot,'fetch_response',side_effect=fetch):hot.api_items(a)
            self.assertEqual(len(urls),1);self.assertNotIn('cursor=',urls[0])
            self.assertEqual(next((Path(tmp)/'.aihot_checkpoint_backups').iterdir()).read_bytes(),original)

    def test_unknown_future_checkpoint_stops_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=args(Path(tmp)/'future.json');a.checkpoint.write_bytes(b'{"version":99}')
            with patch.object(hot,'fetch_response') as request,self.assertRaises(ValueError):hot.api_items(a)
            request.assert_not_called();self.assertEqual(a.checkpoint.read_bytes(),b'{"version":99}')

    def test_orchestrator_forwards_ai_domain_in_actual_cli_contract(self):
        import orchestrate_daily as o
        with patch('source_preparation.main',return_value=0) as prepare:
            self.assertEqual(o.main(['sources','--date','2026-10-16','--pool-dir','temporary-only','--domain','ai-social','--action','work']),0)
        command=prepare.call_args.args[0]
        self.assertEqual(command[command.index('--domain')+1],'ai-social')

    def test_old_feed_records_do_not_crowd_out_current_window(self):
        raw=rss('openai-news',100).replace(b'Thu, 15 Oct 2026 12:00:00 GMT',b'Thu, 15 Oct 2020 12:00:00 GMT')
        v=observation('openai-news',raw)
        self.assertEqual(v['candidate_count'],100);self.assertEqual(v['emitted'],0)
        self.assertEqual(v['outside_discovery_window_count'],100)
        self.assertFalse(v['zero_publications_established'])

    def test_large_source_cannot_hide_alternate_pool_sources(self):
        first=observation('openai-news',rss('openai-news',101));second=observation('ars-ai')
        p=ai.discovery_packet({'ai_fixed_pool':{'observations':[first,second]}})
        self.assertTrue(any('arstechnica.com' in c['original_url'] for c in p['candidates']))
        self.assertEqual(p['truncated'],1)

if __name__=='__main__':unittest.main()
