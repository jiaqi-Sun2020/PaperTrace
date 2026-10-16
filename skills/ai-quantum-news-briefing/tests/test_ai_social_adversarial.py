"""Second adversarial audit: synthetic sources only, no live traffic."""
import copy,hashlib,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import ai_social_sources as ai
import aihot_candidates as hot
import source_worker as worker
from source_pool import SourcePool,task_spec
from source_capture import make_capture,validate_capture,digest
import test_ai_social_fixed_pool as fx

def article(*extras):
    return ('<title>Synthetic original</title><meta property="article:published_time" content="2026-10-15T12:00:00Z">'+''.join(extras)+'<p>Verified synthetic original excerpt.</p>').encode()

def item(name='a',host='example.org'):
    return {'id':name,'material_kind':'social','source_url_contract_version':2,
            'source_url':'https://'+host+'/article/'+name,'source_title':'Synthetic original',
            'source_excerpt':'Verified synthetic original excerpt.','evidence_level':'verified original report',
            'source_class':'reputable_media','evidence_fingerprint':'synthetic-only',
            'published_at':'2026-10-15T12:00:00Z','ai_source_provenance':{'version':1,'source_id':{'openai.com':'openai-news','arstechnica.com':'ars-ai'}.get(host,'synthetic-original')}}

class AISocialAdversarialTests(unittest.TestCase):
    def test_old_date_extractor_cannot_be_reused_as_new_proof(self):
        row=item();capture=make_capture(row,row['source_url'],row['source_url'],200,article(),'2026-10-16T01:00:00Z')
        self.assertFalse(validate_capture(row,capture))
        old=copy.deepcopy(capture);old['ai_original_publication'].pop('extractor_version')
        old['record_sha256']=digest({k:v for k,v in old.items() if k!='record_sha256'})
        original=json.dumps(old,sort_keys=True)
        self.assertTrue(validate_capture(row,old))
        self.assertEqual(json.dumps(old,sort_keys=True),original)

    def test_distinct_api_ids_cannot_collapse_to_one_story(self):
        rows=[hot.item_to_briefing_item({'id':key,'title':'Synthetic'},i,'api') for i,key in enumerate(('a/b','a-b'))]
        self.assertNotEqual(rows[0]['id'],rows[1]['id'])
        self.assertNotEqual(rows[0]['story_id'],rows[1]['story_id'])

    def test_api_opaque_id_is_hashed_without_html_cleaning(self):
        key='opaque<record>&id'
        a=hot.item_to_briefing_item({'id':key,'title':'Synthetic'},1,'api')
        b=hot.item_to_briefing_item({'id':key,'title':'Synthetic'},91,'api')
        self.assertEqual(a['id'],'AH'+hashlib.sha256(key.encode()).hexdigest()[:20])
        self.assertEqual(a['id'],b['id'])

    def test_relative_canonical_resolves_against_actual_original(self):
        proof=ai.article_publication(article('<link rel="canonical" href="/article/a">'),'https://example.org/article/a')
        self.assertEqual(proof['canonical_url'],'https://example.org/article/a')

    def test_disagreeing_canonical_tags_are_rejected(self):
        body=article('<link rel="canonical" href="https://example.org/other">','<link rel="canonical" href="https://example.org/article/a">')
        with self.assertRaises(ValueError):ai.article_publication(body,'https://example.org/article/a')

    def test_malformed_unrelated_jsonld_cannot_hide_conflicting_actual_date(self):
        graph={'@graph':[{'@type':'NewsArticle','url':'http://unrelated.invalid/','datePublished':'2026-10-01T00:00:00Z'},
                         {'@type':'NewsArticle','url':'https://example.org/article/a','datePublished':'2026-10-14T12:00:00Z'}]}
        body=article('<script type="application/ld+json">'+json.dumps(graph)+'</script>')
        with self.assertRaisesRegex(ValueError,'ai_original_publication_conflict'):
            ai.article_publication(body,'https://example.org/article/a')

    def test_two_original_offsets_for_same_instant_are_consistent(self):
        body=article('<script type="application/ld+json">'+json.dumps({'@type':'Article','url':'https://example.org/article/a','datePublished':'2026-10-15T20:00:00+08:00'})+'</script>')
        self.assertEqual(ai.article_publication(body,'https://example.org/article/a')['published_at'],'2026-10-15T12:00:00+00:00')

    def test_conflicting_discovery_dates_are_explicit_until_original_check(self):
        v=fx.observation();row=v['candidates'][0]
        snapshot={'ai_fixed_pool':{'observations':[v]},'aihot':{'sections':[{'items':[{'source_url':row['original_url'],'title':'Same original','published_at':'2026-10-14T12:00:00Z'}]}]}}
        candidate=ai.discovery_packet(snapshot)['candidates'][0]
        self.assertIsNone(candidate['published_at'])
        self.assertEqual(candidate['date_status'],'discovery_time_conflict_original_required')
        self.assertEqual(len(candidate['discoveries']),2)

    def test_conflicting_duplicate_dates_within_one_feed_are_not_hidden(self):
        raw=fx.rss('techcrunch-ai',2,duplicate=True)
        raw=raw.replace(b'<guid>g1</guid><pubDate>Thu, 15 Oct 2026',b'<guid>g1</guid><pubDate>Wed, 14 Oct 2026')
        observed=fx.observation(body=raw)
        self.assertEqual(len(observed['candidates']),1)
        self.assertIsNone(observed['candidates'][0]['published_at'])
        candidate=ai.discovery_packet({'ai_fixed_pool':{'observations':[observed]}})['candidates'][0]
        self.assertIsNone(candidate['published_at'])
        self.assertEqual(candidate['date_status'],'discovery_time_conflict_original_required')
        self.assertEqual(len(candidate['discoveries'][0]['conflicting_published_raw']),2)

    def test_denied_host_does_not_replace_existing_successful_capture(self):
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            rows=[item('saved'),item('denied')]
            for row in rows:pool.enqueue(task_spec('capture','fixture',fx.DAY,{'item':row},{'code':worker.code_binding()}))
            def execute(spec):
                row=spec['inputs']['item']
                if row['id']=='denied':raise HTTPError(row['source_url'],403,'',{},None)
                return {'record':make_capture(row,row['source_url'],row['source_url'],200,article(),'2026-10-16T01:00:00Z')}
            worker.run_ready(pool,coverage_date=fx.DAY,executor=execute)
            prior={t['task_id']:t['result_sha'] for t in pool.tasks() if t['state']=='succeeded'}
            self.assertEqual(len(prior),1)
            with patch.object(worker,'execute_existing') as network:
                resumed=worker.run_ready(pool,coverage_date=fx.DAY)
            network.assert_not_called()
            self.assertNotIn('saved',[r['item_id'] for r in resumed['replacement_required']])
            self.assertEqual(prior,{t['task_id']:t['result_sha'] for t in pool.tasks() if t['state']=='succeeded'})

    def test_denial_from_another_date_does_not_poison_this_date(self):
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            old=pool.enqueue(task_spec('capture','fixture','2026-10-14',{'item':item('old')},{'code':worker.code_binding()}))
            lease=pool.claim(task_id=old);pool.fail(old,lease['lease'],{'code':'source_access_denied','retryable':False,'http_status':403})
            current=pool.enqueue(task_spec('capture','fixture',fx.DAY,{'item':item('current')},{'code':worker.code_binding()}))
            calls=[]
            def execute(spec):
                calls.append(spec['inputs']['item']['id'])
                raise HTTPError(spec['inputs']['item']['source_url'],403,'',{},None)
            worker.run_ready(pool,executor=execute)
            self.assertEqual(calls,['current']);self.assertEqual(pool.get(current)['attempts'],1)

    def test_shanghai_window_is_half_open_and_not_discovery_date(self):
        start,end=hot.coverage_window(fx.DAY)
        for value,expected in [('2026-10-14T16:00:00Z',True),('2026-10-15T15:59:59Z',True),('2026-10-15T16:00:00Z',False),('2026-10-15T12:00:00',None)]:
            self.assertIs(hot.published_in_window({'publishedAt':value,'discoveredAt':'2026-10-15T12:00:00Z'},start,end),expected)

    def test_cursor_cycle_is_bounded_and_never_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=fx.args(Path(tmp)/'checkpoint.json');calls=[]
            def fetch(url):
                calls.append(url)
                row={'id':str(len(calls)),'publishedAt':'2026-10-15T12:00:00Z'}
                return fx.transport(fx.response([row],True,'same-cursor'),url)
            with patch.object(hot,'fetch_response',side_effect=fetch):
                _,proof=hot.api_items(args)
            self.assertEqual(len(calls),2);self.assertNotEqual(proof['coverage_status'],'verified')
            self.assertFalse(proof['pagination_complete'])

    def test_pool_success_reentry_has_no_new_work_or_identity_change(self):
        with tempfile.TemporaryDirectory() as tmp,SourcePool(Path(tmp)/'pool.sqlite') as pool:
            key=pool.enqueue(task_spec('fixed_source','techcrunch-ai',fx.DAY,{}, {'code':worker.code_binding()}))
            calls=[]
            def execute(spec):calls.append(spec['source_id']);return fx.observation()
            worker.run_ready(pool,coverage_date=fx.DAY,executor=execute)
            before=pool.get(key)
            again=worker.run_ready(pool,coverage_date=fx.DAY,executor=execute)
            after=pool.get(key)
            self.assertEqual(calls,['techcrunch-ai']);self.assertEqual(again['processed'],[])
            self.assertEqual((before['result_sha'],before['attempts']),(after['result_sha'],after['attempts']))

    def test_actual_capture_adapter_denial_uses_other_pool_host_and_reuses_it(self):
        import source_capture as capture
        class Response:
            status=200
            def __init__(self,url):self.url=url
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,size):return article()
            def geturl(self):return self.url
        calls=[]
        class Opener:
            def open(self,request,**kwargs):
                url=request.full_url;calls.append(url)
                if 'openai.com' in url:raise HTTPError(url,403,'',{},None)
                return Response(url)
        with tempfile.TemporaryDirectory() as tmp:
            news=Path(tmp)/'news';config=Path(tmp)/'synthetic.json'
            rows=[item('denied','openai.com'),item('unattempted','openai.com'),item('alternate','arstechnica.com')]
            config.write_text(json.dumps({'sections':[{'items':rows}]}),encoding='utf-8')
            with SourcePool(news/'_sources/pool.sqlite') as pool:
                keys=worker.enqueue_captures(pool,config,news,fx.DAY)
                with patch.object(capture,'build_opener',return_value=Opener()),patch.object(capture,'public_https'):
                    first=worker.run_ready(pool,coverage_date=fx.DAY)
                    saved=capture.capture_path(news,fx.DAY,'alternate').read_bytes()
                    second=worker.run_ready(pool,coverage_date=fx.DAY)
                self.assertEqual(calls,[rows[0]['source_url'],rows[2]['source_url']])
                self.assertEqual(pool.get(keys[0])['state'],'blocked')
                self.assertEqual(pool.get(keys[1])['attempts'],0)
                self.assertEqual(pool.get(keys[2])['state'],'succeeded')
                self.assertEqual(pool.db.execute('SELECT count(*) FROM materials').fetchone()[0],1)
                self.assertEqual(capture.capture_path(news,fx.DAY,'alternate').read_bytes(),saved)
                self.assertEqual(second['processed'],[]);self.assertFalse(first['publication_approved'])

if __name__=='__main__':unittest.main()
