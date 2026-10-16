"""Approved fixed discovery only. Original capture and semantic review stay separate."""
from __future__ import annotations
import base64,gzip,hashlib,ipaddress,json,re
from datetime import datetime,timezone,timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from urllib.parse import urljoin,urlsplit
from urllib.request import Request,build_opener
from source_capture import SafeRedirect
import xml.etree.ElementTree as ET

SOURCES=(
    {'id':'openai-news','url':'https://openai.com/news/rss.xml','format':'feed','source_class':'official_primary','role':'primary','discovery_only':True},
    {'id':'deepmind-news','url':'https://deepmind.google/blog/','format':'column','source_class':'official_primary','role':'primary','discovery_only':True},
    {'id':'anthropic-news','url':'https://www.anthropic.com/news','format':'column','source_class':'official_primary','role':'primary','discovery_only':True},
    {'id':'techcrunch-ai','url':'https://techcrunch.com/category/artificial-intelligence/feed/','format':'feed','source_class':'reputable_media','role':'primary','discovery_only':True},
    {'id':'ars-ai','url':'https://arstechnica.com/ai/feed/','format':'feed','source_class':'reputable_media','role':'primary','discovery_only':True},
    {'id':'verge-ai','url':'https://www.theverge.com/rss/ai-artificial-intelligence/index.xml','format':'feed','source_class':'reputable_media','role':'backup','discovery_only':True},
)
MAX_BYTES=2_000_000
LIMIT=100
ZONE=timezone(timedelta(hours=8),'Asia/Shanghai')
digest=lambda value:hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def registry():return json.loads(json.dumps(SOURCES))
def registered(source_id):
    return next(row for row in registry() if row['id']==source_id)
def aware(value):
    if not isinstance(value,str) or not value:return None
    try:stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        try:stamp=parsedate_to_datetime(value)
        except (ValueError,TypeError,IndexError):return None
    return stamp if stamp.tzinfo else None
def public_url(value):
    from briefing_contract import source_reference_url
    p=urlsplit(value)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):raise ValueError('ai_source_url_invalid')
    if p.hostname=='localhost' or p.hostname.endswith(('.local','.internal')):raise ValueError('ai_source_private_url')
    try:
        if not ipaddress.ip_address(p.hostname).is_global:raise ValueError('ai_source_private_url')
    except ValueError as exc:
        if str(exc)=='ai_source_private_url':raise
    if any(re.search(r'cookie|session|token|secret|password|credential',key,re.I) for key in __import__('urllib.parse',fromlist=['parse_qs']).parse_qs(p.query)):
        raise ValueError('ai_source_private_query')
    return source_reference_url(value)

class Page(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.a=None;self.canonicals=[];self.dates=[];self.scripts=[];self.script=None;self.skip=0
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and 'canonical' in a.get('rel','').lower().split():self.canonicals.append(a.get('href'))
        if tag=='meta' and a.get('property')=='article:published_time':self.dates.append(a.get('content'))
        if tag=='script':
            self.skip+=1
            if a.get('type')=='application/ld+json':self.script=[]
        if tag=='a' and not self.skip and a.get('href'):self.a=[a['href'],[]]
    def handle_data(self,data):
        if self.a and not self.skip:self.a[1].append(data)
        if self.script is not None:self.script.append(data)
    def handle_endtag(self,tag):
        if tag=='script':
            if self.script is not None:self.scripts.append(''.join(self.script));self.script=None
            self.skip=max(0,self.skip-1)
        if tag=='a' and self.a:
            self.links.append((self.a[0],re.sub(r'\s+',' ',' '.join(self.a[1])).strip()));self.a=None

def parse_candidates(source,body):
    rows=[]
    if source['format']=='feed':
        root=ET.fromstring(body)
        elements=root.findall('./channel/item')
        if not elements:elements=root.findall('{http://www.w3.org/2005/Atom}entry')
        if root.tag not in ('rss','{http://www.w3.org/2005/Atom}feed'):raise ValueError('ai_feed_shape_invalid')
        for item in elements:
            atom='{http://www.w3.org/2005/Atom}'
            link=item.findtext('link')
            if not link:
                node=next((e for e in item.findall(atom+'link') if e.get('rel','alternate')=='alternate'),None)
                link=node.get('href') if node is not None else None
            rows.append({'title':item.findtext('title') or item.findtext(atom+'title'),
                         'original_url':link,'source_record_id':item.findtext('guid') or item.findtext(atom+'id'),
                         'published_raw':item.findtext('pubDate') or item.findtext(atom+'published'),
                         'updated_raw':item.findtext(atom+'updated')})
    else:
        p=Page();p.feed(body.decode('utf-8'))
        prefix='/blog/' if source['id']=='deepmind-news' else '/news/'
        for href,title in p.links:
            url=urljoin(source['url'],href);parsed=urlsplit(url)
            if (parsed.hostname==urlsplit(source['url']).hostname and parsed.path.startswith(prefix)
                    and parsed.path.rstrip('/')!=prefix.rstrip('/') and len(title)>12):
                rows.append({'title':title,'original_url':url,'source_record_id':None,'published_raw':None,'updated_raw':None})
    result=[];seen={};invalid=[]
    for index,row in enumerate(rows):
        try:
            url=public_url(row['original_url'])
            if not row['title']:raise ValueError('ai_discovery_title_missing')
            if urlsplit(url).hostname!=urlsplit(public_url(source['url'])).hostname:raise ValueError('ai_discovery_origin_changed')
        except (ValueError,TypeError,AttributeError):invalid.append(index);continue
        if url in seen:
            previous=result[seen[url]];first=aware(previous['published_raw']);other=aware(row['published_raw'])
            if previous['date_status']=='discovery_time_conflict_original_required' or first and other and first!=other:
                previous['published_at']=None;previous['date_status']='discovery_time_conflict_original_required'
                previous.setdefault('conflicting_published_raw',[previous['published_raw']]).append(row['published_raw'])
            continue
        seen[url]=len(result);stamp=aware(row['published_raw'])
        result.append({**row,'original_url':url,'source_url_contract_version':2,'source_id':source['id'],'source_class':source['source_class'],
                       'discovery_id':digest({'source':source['id'],'url':url}),
                       'published_at':stamp.isoformat() if stamp else None,
                       'date_status':'publisher_time_unverified' if stamp else 'unknown',
                       'ai_source_provenance':{'version':1,'source_id':source['id'],'discovery_id':digest({'source':source['id'],'url':url})},
                       'semantic_review_status':'not_reviewed','publication_approved':False})
    return result,invalid

class FixedRedirect(SafeRedirect):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlsplit(newurl).hostname!=urlsplit(req.full_url).hostname:
            raise ValueError('ai_discovery_redirect_outside_pool')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_document(url):
    from source_capture import public_https
    public_https(url)
    request=Request(url,headers={'User-Agent':'PaperTrace-fixed-sources/1.0','Accept-Encoding':'gzip'})
    with build_opener(FixedRedirect()).open(request,timeout=25) as response:
        body=response.read(MAX_BYTES+1)
        if response.headers.get('Content-Encoding')=='gzip':
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:body=stream.read(MAX_BYTES+1)
        if len(body)>MAX_BYTES:raise ValueError('ai_discovery_response_limit')
        if response.status!=200:raise ValueError('ai_discovery_response_not_200')
        return body,{'query_url':url,'final_url':response.geturl(),'status_code':200,
                     'retrieved_at':datetime.now(timezone.utc).isoformat(),
                     'response_hash':hashlib.sha256(body).hexdigest(),'hash_scope':'decoded_representation_bytes'}

def project_window(candidates,day):
    observed=[];outside=0
    for candidate in candidates:
        stamp=aware(candidate['published_at'])
        if stamp and stamp.astimezone(ZONE).date().isoformat()!=day:outside+=1;continue
        observed.append(candidate)
    return observed,outside

def collect(source_id,day,*,fetch=None):
    source=registered(source_id)
    body,http=(fetch or fetch_document)(source['url'])
    candidates,invalid=parse_candidates(source,body)
    observed,outside=project_window(candidates,day)
    return {'ai_fixed_source_version':1,'source':source,'coverage_date':day,'http':http,
            'body_base64':base64.b64encode(body).decode('ascii'),
            'candidates':observed[:LIMIT],'candidate_count':len(candidates),'window_candidate_count':len(observed),
            'outside_discovery_window_count':outside,'emitted':min(LIMIT,len(observed)),
            'truncated':max(0,len(observed)-LIMIT),'invalid_positions':invalid,
            'observation_scope':'returned_feed_or_column_only','pagination_complete':False,
            'exhaustive_publisher_coverage':False,'zero_publications_established':False,
            'semantic_review_status':'not_reviewed','publication_approved':False}

def validate(value,source_id,day):
    try:
        source=registered(source_id);http=value['http'];body=base64.b64decode(value['body_base64'],validate=True)
        if len(body)>MAX_BYTES or not body:raise ValueError()
        candidates,invalid=parse_candidates(source,body)
        observed,outside=project_window(candidates,day)
        end=datetime.fromisoformat(day+'T00:00:00+08:00')+timedelta(days=1)
        stamp=aware(http['retrieved_at'])
        if not (type(value['ai_fixed_source_version']) is int and value['ai_fixed_source_version']==1 and value['source']==source and value['coverage_date']==day): raise ValueError("ai_evidence_contract_invalid")
        if not (http['query_url']==source['url'] and public_url(http['final_url'])==public_url(source['url'])): raise ValueError("ai_evidence_contract_invalid")
        if not (http['status_code']==200 and http['hash_scope']=='decoded_representation_bytes'): raise ValueError("ai_evidence_contract_invalid")
        if not (http['response_hash']==hashlib.sha256(body).hexdigest() and stamp and stamp>=end): raise ValueError("ai_evidence_contract_invalid")
        if not (value['candidates']==observed[:LIMIT] and value['invalid_positions']==invalid): raise ValueError("ai_evidence_contract_invalid")
        if not all(type(value.get(k)) is int for k in ('candidate_count','window_candidate_count','outside_discovery_window_count','emitted','truncated')): raise ValueError('ai_counts_invalid')
        if not (value['candidate_count']==len(candidates) and value['emitted']==min(LIMIT,len(observed))): raise ValueError("ai_evidence_contract_invalid")
        if not (value['window_candidate_count']==len(observed) and value['outside_discovery_window_count']==outside): raise ValueError("ai_evidence_contract_invalid")
        if not (value['truncated']==max(0,len(observed)-LIMIT)): raise ValueError("ai_evidence_contract_invalid")
        if not (value['observation_scope']=='returned_feed_or_column_only'): raise ValueError("ai_evidence_contract_invalid")
        if not (value['pagination_complete'] is False and value['exhaustive_publisher_coverage'] is False): raise ValueError("ai_evidence_contract_invalid")
        if not (value['zero_publications_established'] is False and value['publication_approved'] is False): raise ValueError("ai_evidence_contract_invalid")
        if not (value['semantic_review_status']=='not_reviewed'): raise ValueError("ai_evidence_contract_invalid")
    except (AssertionError,KeyError,ValueError,TypeError,AttributeError,StopIteration,ET.ParseError):return ['ai_fixed_source_evidence_invalid']
    return []

def article_publication(body,final_url):
    page=Page();page.feed(body.decode('utf-8'))
    canonicals={public_url(urljoin(final_url,value)) for value in page.canonicals}
    if len(canonicals)>1:raise ValueError('ai_original_canonical_conflict')
    canonical=next(iter(canonicals)) if canonicals else public_url(final_url)
    if canonical!=public_url(final_url):raise ValueError('ai_original_canonical_mismatch')
    values=list(page.dates)
    def visit(value):
        if isinstance(value,list):
            for child in value:visit(child)
        elif isinstance(value,dict):
            types=value.get('@type',[]);types=[types] if isinstance(types,str) else types
            if not isinstance(types,list):types=[]
            if any(x in ('Article','NewsArticle','BlogPosting') for x in types):
                identity=value.get('url') or value.get('mainEntityOfPage') or value.get('@id')
                if isinstance(identity,dict):identity=identity.get('@id')
                try:matches=isinstance(identity,str) and public_url(urljoin(final_url,identity))==canonical
                except (ValueError,TypeError,AttributeError):matches=False
                if matches and value.get('datePublished'):
                    values.append(value['datePublished'])
            if '@graph' in value:visit(value['@graph'])
    for raw in page.scripts:
        try:parsed=json.loads(raw)
        except (ValueError,TypeError):continue
        visit(parsed)
    stamps=[aware(value) for value in values]
    if not stamps or any(s is None for s in stamps):raise ValueError('ai_original_publication_timezone_unknown')
    if len({s.astimezone(timezone.utc).isoformat() for s in stamps})!=1:raise ValueError('ai_original_publication_conflict')
    return {'extractor_version':2,'canonical_url':canonical,'published_at':stamps[0].isoformat(),'raw_dates':values,
            'basis':'article:published_time_or_canonical_article_jsonld','response_sha256':hashlib.sha256(body).hexdigest()}

def pool_evidence(results,day):
    good=[v for v in results if not validate(v,v.get('source',{}).get('id'),day)]
    classes={v['source']['source_class'] for v in good}
    return {'version':1,'coverage_date':day,'scope':'approved_fixed_pool_observations_only',
            'registry_sha256':digest(registry()),'observations':good,
            'available_source_classes':sorted(classes),'missing_source_classes':sorted({'official_primary','reputable_media'}-classes),
            'status':'discovery_available' if {'official_primary','reputable_media'}<=classes else 'discovery_pending',
            'semantic_review_status':'not_reviewed','publication_approved':False}

def validate_pool(value,day):
    try:
        if not (value==pool_evidence(value['observations'],day)): raise ValueError("ai_evidence_contract_invalid")
        if not (value['status']=='discovery_available'): raise ValueError("ai_evidence_contract_invalid")
        ids=[v['source']['id'] for v in value['observations']]
        if not (len(ids)==len(set(ids))): raise ValueError("ai_evidence_contract_invalid")
    except (AssertionError,KeyError,ValueError,TypeError,AttributeError):return ['ai_fixed_pool_evidence_incomplete']
    return []


def discovery_packet(snapshot):
    """Deduplicate discovery URLs only; never author or promote evidence."""
    entries=[]
    for observation in (snapshot.get('ai_fixed_pool') or {}).get('observations',[]):
        entries.extend(observation['candidates'])
    for section in (snapshot.get('aihot') or {}).get('sections',[]):
        entries.extend(section.get('items',[]))
    merged={};invalid=[]
    for position,row in enumerate(entries):
        try:url=public_url(row.get('original_url') or row.get('source_url'))
        except (ValueError,TypeError,AttributeError):invalid.append(position);continue
        reference={k:row.get(k) for k in ('source_id','discovery_id','story_id','published_at','discovered_at','aggregation_url','ai_source_provenance','date_status','conflicting_published_raw')}
        if url not in merged:
            merged[url]={'original_url':url,'title':row.get('title'),'source_url_contract_version':2,
                         'published_at':row.get('published_at'),'discoveries':[],
                         'semantic_review_status':'not_reviewed','publication_approved':False,
                         'original_capture_required':True}
        merged[url]['discoveries'].append(reference)
    for candidate in merged.values():
        stamps=[aware(ref.get('published_at')) for ref in candidate['discoveries']]
        instants={s.astimezone(timezone.utc).isoformat() for s in stamps if s is not None}
        if len(instants)>1 or any(ref.get('date_status')=='discovery_time_conflict_original_required' for ref in candidate['discoveries']):
            candidate['published_at']=None
            candidate['date_status']='discovery_time_conflict_original_required'
        elif len(instants)==1:
            candidate['published_at']=next(s.isoformat() for s in stamps if s is not None)
            candidate['date_status']='publisher_time_unverified'
        else:
            candidate['published_at']=None
            candidate['date_status']='unknown'
    groups={}
    for candidate in merged.values():
        ref=candidate['discoveries'][0]
        source=ref.get('source_id') or (ref.get('ai_source_provenance') or {}).get('source_id') or 'aihot-v1'
        groups.setdefault(source,[]).append(candidate)
    candidates=[]
    while any(groups.values()):
        for rows in groups.values():
            if rows:candidates.append(rows.pop(0))
    return {'candidates':candidates[:LIMIT],'total':len(candidates),'emitted':min(LIMIT,len(candidates)),
            'truncated':max(0,len(candidates)-LIMIT),'full_evidence':'ai_fixed_pool observations and aihot sections',
            'invalid_positions':invalid,'semantic_review_status':'not_reviewed','publication_approved':False}
