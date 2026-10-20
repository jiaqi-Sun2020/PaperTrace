"""Bounded same-window rechecks in the existing source pool. Never publishes."""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit
from source_pool import PoolConflict,fingerprint,task_spec

ZONE=timezone(timedelta(hours=8))

def diagnostic_checkpoint(pool,task):
    """Resolve only unchanged-query code aliases; never rewrite or promote a cache."""
    from source_pool import checked_path
    seen=set();current=task
    while True:
        key=current['task_id']
        if key in seen or len(seen)>=64:raise PoolConflict('checkpoint_alias_cycle')
        seen.add(key)
        path=checked_path(pool.path.parent/'checkpoints'/(key+'.json'))
        if path.exists():return path,key
        ref=current.get('checkpoint') or {}
        if 'rebound_from' not in ref:return path,key
        if set(ref)!={'rebound_from','old_result_sha256'}:raise PoolConflict('checkpoint_alias_invalid')
        parent=pool.get(ref['rebound_from'])
        if (pool._compatible_scope(parent['spec'])!=pool._compatible_scope(task['spec'])
                or ref['old_result_sha256']!=parent['result_sha']):raise PoolConflict('checkpoint_alias_binding_changed')
        current=parent


def diagnose_cached(pool,plan):
    """Read query-bound old checkpoints; diagnoses never promote failed rows."""
    import hashlib,json
    from collection_checkpoint import load_checkpoint
    from source_pool import checked_path
    from academic_sources import row_evidence_failures
    reports=[]
    for task in pool.tasks(coverage_date=plan['coverage_date']):
        spec=task['spec']
        if spec['kind']!='academic' or not task['failure']:continue
        try:path,checkpoint_task_id=diagnostic_checkpoint(pool,task)
        except (PoolConflict,OSError):
            reports.append({'task_id':task['task_id'],'source_id':spec['source_id'],'status':'checkpoint_invalid','original_failure':task['failure']});continue
        if not path.exists():
            reports.append({'task_id':task['task_id'],'source_id':spec['source_id'],'status':'checkpoint_missing','original_failure':task['failure']});continue
        scope={'kind':'academic_v4','terms':spec['inputs']['terms'],'date_range':plan['coverage_date'],
               'source_coverage_version':2,'checkpoint_contract':2}
        value=load_checkpoint(path,scope);rows=value.get('rows',{});scopes=value.get('source_scopes',{})
        row=rows.get(spec['source_id']) if isinstance(rows,dict) else None
        source_scope=hashlib.sha256(json.dumps({'row':spec['inputs']['row'],'source':spec['config']['source']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        if (not isinstance(row,dict) or row.get('source_id')!=spec['source_id']
                or not isinstance(scopes,dict) or scopes.get(spec['source_id'])!=source_scope):
            reports.append({'task_id':task['task_id'],'source_id':spec['source_id'],'status':'checkpoint_invalid','original_failure':task['failure']});continue
        try:
            failures=row_evidence_failures(row,plan['coverage_date'])
            diagnostic=academic_diagnostic(spec,row,failures or ['academic_source_incomplete'])
        except (ValueError,TypeError,KeyError,AttributeError):
            reports.append({'task_id':task['task_id'],'source_id':spec['source_id'],'status':'checkpoint_invalid','original_failure':task['failure']});continue
        reports.append({'task_id':task['task_id'],'source_id':spec['source_id'],'status':'diagnosed',
                        'original_failure':task['failure'],'diagnostic':diagnostic,
                        'checkpoint_task_id':checkpoint_task_id,'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    return reports


def reconcile_cached_failure(pool,task_id,*,expected_failure_sha256,expected_checkpoint_sha256,reason,now=None):
    """Explicit offline correction on a new code alias; immutable old failures remain."""
    import hashlib,json,re,time
    import source_worker as w
    from source_pool import encoded,ID
    from collection_checkpoint import fingerprint as checkpoint_fingerprint
    if not isinstance(reason,str) or not ID.fullmatch(reason):raise PoolConflict('reconciliation_reason_required')
    if not all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in (expected_failure_sha256,expected_checkpoint_sha256)):
        raise PoolConflict('reconciliation_digest_required')
    legacy={'code':'failure_contract_invalid','retryable':False}
    with pool.transaction():
        task=pool.get(task_id);spec=task['spec']
        if spec['kind']!='academic' or spec['config'].get('code')!=w.code_binding():raise PoolConflict('current_academic_alias_required')
        related=pool._compatible_rows(spec)
        if related[-1]['task_id']!=task_id:raise PoolConflict('current_academic_alias_required')
        path,old_key=diagnostic_checkpoint(pool,task)
        if old_key==task_id:raise PoolConflict('immutable_legacy_checkpoint_required')
        with path.open('rb') as stream:raw=stream.read(32_000_001)
        if len(raw)>32_000_000 or hashlib.sha256(raw).hexdigest()!=expected_checkpoint_sha256:
            raise PoolConflict('reconciliation_checkpoint_changed')
        if task['state']=='succeeded':
            events=pool.db.execute("SELECT detail FROM events WHERE task_id=? AND state='succeeded' ORDER BY sequence DESC LIMIT 1",(task_id,)).fetchone()
            detail=json.loads(events[0]) if events else {}
            if detail.get('operation')=='cached_failure_reconciled' and detail.get('failure_sha256')==expected_failure_sha256 and detail.get('checkpoint_sha256')==expected_checkpoint_sha256:
                return {'status':'already_reconciled','task_id':task_id,'network_executed':False,'publication_approved':False}
            raise PoolConflict('reconciliation_already_succeeded_conflict')
        if task['state'] not in ('blocked','exhausted') or task['failure']!=legacy:raise PoolConflict('legacy_failure_required')
        if fingerprint(task['failure'])!=expected_failure_sha256:raise PoolConflict('reconciliation_failure_changed')
        old=pool.get(old_key)
        if old['failure']!=legacy or old['state']!='blocked':raise PoolConflict('legacy_failure_required')
        spent,maximum=pool._compatible_budget(related)
        if spent>=maximum:raise PoolConflict('unspent_budget_required')
        if any(t['state']=='running' or t['failure'] and t['failure']!=legacy for t in related):
            raise PoolConflict('legacy_failure_required')
        scope={'kind':'academic_v4','terms':spec['inputs']['terms'],'date_range':spec['coverage_date'],'source_coverage_version':2,'checkpoint_contract':2}
        try:
            value=json.loads(raw.decode('utf-8'));payload=value['payload']
            if value.get('version')!=1 or value.get('scope_sha256')!=checkpoint_fingerprint(scope) or not isinstance(payload,dict) or value.get('payload_sha256')!=checkpoint_fingerprint(payload):
                raise ValueError('checkpoint binding')
            source_scope=hashlib.sha256(json.dumps({'row':spec['inputs']['row'],'source':spec['config']['source']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            row=payload['rows'][spec['source_id']]
            if payload['source_scopes'][spec['source_id']]!=source_scope:raise ValueError('source binding')
            failures=w.validate_result(spec,row)
        except (ValueError,TypeError,KeyError,AttributeError):
            failures=['cached_evidence_invalid']
        if failures:
            return {'status':'cached_failure_still_invalid','task_id':task_id,'validation_failures':failures,
                    'network_executed':False,'publication_approved':False}
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected_checkpoint_sha256:raise PoolConflict('reconciliation_checkpoint_changed')
        body=encoded(row);result_sha=hashlib.sha256(body).hexdigest()
        pool.db.execute("UPDATE tasks SET state='succeeded',result=?,result_sha=?,failure=NULL,lease=NULL,lease_until=NULL,retry_at=NULL WHERE task_id=?",(body,result_sha,task_id))
        pool._event(task_id,'succeeded',time.time() if now is None else now,{'operation':'cached_failure_reconciled','reason':reason,
                    'failure_sha256':expected_failure_sha256,'checkpoint_sha256':expected_checkpoint_sha256,
                    'checkpoint_task_id':old_key,'result_sha256':result_sha,'attempts_preserved':task['attempts']})
        return {'status':'cached_failure_reconciled','task_id':task_id,'checkpoint_task_id':old_key,'checkpoint_sha256':expected_checkpoint_sha256,
                'attempts':task['attempts'],'network_executed':False,'publication_approved':False}

def academic_diagnostic(spec, row, failures):
    row=row if isinstance(row,dict) else {}
    from source_pool import ID
    import re
    invalid=[]
    def object_field(key):
        value=row.get(key)
        if value is not None and not isinstance(value,dict):invalid.append('diagnostic_field_invalid')
        return value if isinstance(value,dict) else {}
    evidence=object_field('evidence');window=object_field('window_evidence')
    def scalar(value):
        if value is None or type(value) is bool or isinstance(value,str) and ID.fullmatch(value):return value
        invalid.append('diagnostic_field_invalid');return None
    def count(value):
        if value is None or type(value) is int and 0<=value<=1000000:return value
        invalid.append('diagnostic_field_invalid');return None
    statuses={key:scalar(row.get(key)) for key in ('result','retrieval_status','parse_status','window_status','coverage_claim')}
    basis=scalar(window.get('classification_basis'));candidate=count(row.get('candidate_count'));quarantined=count(row.get('quarantined_count',0))
    digest=evidence.get('response_hash')
    if digest is not None and (not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest)):
        invalid.append('diagnostic_field_invalid');digest=None
    code='academic_evidence_invalid';retryable=False
    status=evidence.get('status_code')
    if type(status) is int and status in (401,403,404,410,408,429,500,502,503,504):
        from source_worker import failure_for
        transport=failure_for(ValueError(),http_status=status,retry_after=evidence.get('retry_after'))
        code=transport['code'];retryable=transport['retryable']
    elif row.get('parse_status')=='unstructured':code='source_adapter_unstructured'
    elif row.get('window_status')=='expired':code='source_window_not_covered'
    elif row.get('quarantined_count',0) and row.get('window_status')=='unknown':code='source_publication_date_unknown'
    safe_failures=[v for v in failures if isinstance(v,str) and ID.fullmatch(v)]
    if len(safe_failures)!=len(failures):invalid.append('diagnostic_field_invalid')
    result={'code':code,'retryable':retryable,'validation_failures':sorted(set(safe_failures+invalid))[:64],
            'source_id':spec['source_id'],'coverage_date':spec['coverage_date'],
            'row_status':statuses,'window_basis':basis,'candidate_count':candidate,
            'quarantined_count':quarantined,'raw_response_sha256':digest,
            'recovery_action':'same_window_already_approved_peer_or_recheck; never upgrade this row'}
    from source_pool import encoded
    while len(encoded({k:v for k,v in result.items() if k not in ('code','retryable','recovery_action')}))>8100:
        result['validation_failures'].pop()
    return result

def recheck_tasks(pool,plan):
    import source_worker as w
    rows=[]
    for task in pool.tasks(coverage_date=plan['coverage_date']):
        spec=task['spec'];ref=spec['inputs'].get('recovery')
        if not isinstance(ref,dict):continue
        parent=pool.get(ref.get('parent_task_id'))['spec']
        bare=dict(spec['inputs']);bare.pop('recovery')
        if (spec['kind']!='academic' or ref!={'parent_task_id':ref['parent_task_id'],'round':1,'release_date':plan['release_date']}
                or bare!=parent['inputs'] or spec['source_id']!=parent['source_id']
                or {k:v for k,v in spec['config'].items() if k!='code'}!={k:v for k,v in parent['config'].items() if k!='code'}):
            raise PoolConflict('recheck_scope_changed')
        def same_query(a,b):
            a=dict(a);b=dict(b);a['config']=dict(a['config']);b['config']=dict(b['config'])
            a['config'].pop('code',None);b['config'].pop('code',None)
            return a==b
        parents=[key for key in plan['tasks'] if same_query(pool.get(key)['spec'],parent)]
        if not parents:continue
        current={**spec,'config':{**spec['config'],'code':plan['binding']['code']}}
        if task['state']=='succeeded' and w.validate_result(current,task['result']):
            raise PoolConflict('recheck_result_invalid')
        rows.append({**task,'current_parent_task_id':parents[0]})
    # Code aliases consume one reservation; the latest identity is executable.
    current={}
    for row in rows:
        current[row['current_parent_task_id']]=row
    return list(current.values())

def readiness(pool,plan,snapshot):
    from daily_delivery_policy import policy_snapshot,resolve_delivery_defaults
    from material_admission import admit_material,publication_day
    from paper_identity import doi_for
    policy=policy_snapshot()['policy']
    if pool.news_root is not None:
        from daily_revisions import candidate_path
        from source_pool import checked_path
        import json
        candidate=checked_path(candidate_path(pool.news_root,plan['release_date']))
        if candidate.is_file():
            if candidate.stat().st_size>32_000_000:raise PoolConflict('candidate_policy_too_large')
            effective=resolve_delivery_defaults(json.loads(candidate.read_text(encoding='utf-8')))
            policy={kind:{**policy[kind],**effective[kind+'_delivery']} for kind in ('academic','social')}
    discovered={'academic':set(),'social':set()}
    for row in snapshot.get('academic',{}).get('rows',[]):
        for item in row.get('matches',[]):
            identity=doi_for(item) or item.get('source_url') or item.get('url')
            if identity:discovered['academic'].add(identity)
    hot=snapshot.get('aihot') or {}
    social=[item for section in hot.get('sections',[]) for item in section.get('items',[])]
    from ai_social_sources import discovery_packet
    social+=discovery_packet(snapshot).get('candidates',[])
    for item in social:
        try:
            if publication_day(item.get('published_at')).isoformat()==plan['coverage_date']:
                identity=item.get('original_url') or item.get('source_url') or item.get('url')
                if identity:discovered['social'].add(identity)
        except (TypeError,ValueError,AttributeError):pass
    qualified={'academic':set(),'social':set()};captured={'academic':set(),'social':set()};rejected=0
    for row in pool.db.execute('SELECT material_id FROM materials ORDER BY rowid'):
        m=pool.material(row[0]);item=m['item'];kind=item.get('material_kind')
        if kind not in qualified:continue
        try:
            if publication_day(item.get('published_at')).isoformat()!=plan['coverage_date']:continue
        except (TypeError,ValueError,AttributeError):continue
        identity=doi_for(item) or item['source_url'];captured[kind].add(identity)
        if admit_material(m['source_id'],item,m['capture']):rejected+=1
        else:qualified[kind].add(identity)
    tasks=pool.tasks(coverage_date=plan['coverage_date'])
    rejected+=sum(t['spec']['kind']=='capture' and t['state'] in ('blocked','exhausted') for t in tasks)
    counts={k:{'discovered':len(discovered[k]),'captured':len(captured[k]),'qualified':len(qualified[k]),
               'minimum':policy[k]['minimum_items'],'qualified_gap':max(0,policy[k]['minimum_items']-len(qualified[k])),
               'discovery_gap':max(0,policy[k]['minimum_items']-len(discovered[k]))} for k in qualified}
    checks=recheck_tasks(pool,plan)
    return {'counts':counts,'rejected_capture_or_material_count':rejected,
            'rechecks':{'reserved':len(checks),'all_terminal':bool(checks) and all(t['state'] in ('succeeded','blocked','exhausted') for t in checks)},
            'coverage_status':snapshot.get('status'),'qualification_means':'article evidence admission, not semantic/review approval',
            'requirements':{'date':'original frozen coverage day only','topic':'requires_rank_and_actual_review',
                            'source_diversity':'requires_rank_and_original_source_verification',
                            'effective_delivery_policy':policy,
                            'social_new_or_important_updates':{'minimum':policy['social']['minimum_new_or_material_update'],'status':'not_reviewed'},
                            'content_fable_display_strict':'not_approved'},'publication_approved':False}

def validate_policy(value,day):
    if not isinstance(value,dict) or type(value.get('version')) is not int or value['version']!=1 or type(value.get('enabled')) is not bool:
        raise PoolConflict('recovery_policy_invalid')
    if not value['enabled']:return None
    required={'version','enabled','timezone','not_before','deadline','minimum_interval_seconds','max_recheck_tasks','max_tasks_per_invocation'}
    if set(value)!=required or value['timezone']!='Asia/Shanghai':raise PoolConflict('recovery_policy_invalid')
    for key,low,high in [('minimum_interval_seconds',60,86400),('max_recheck_tasks',1,4),('max_tasks_per_invocation',1,4)]:
        if type(value[key]) is not int or not low<=value[key]<=high:raise PoolConflict('recovery_policy_budget_invalid')
    start,end=(datetime.fromisoformat(value[k]) for k in ('not_before','deadline'))
    if (start.tzinfo is None or end.tzinfo is None or start>=end
            or start.astimezone(ZONE).date().isoformat()!=day or end.astimezone(ZONE).date().isoformat()!=day):
        raise PoolConflict('recovery_policy_window_invalid')
    return start.timestamp(),end.timestamp()

def recover(pool,plan,policy,*,now,executor=None):
    import source_worker as w
    import time
    bounds=validate_policy(policy,plan['release_date'])
    if bounds is None:return {'status':'recovery_policy_required','processed':[],'network_executed':False,'publication_approved':False}
    start,end=bounds
    if now<start:return {'status':'retry_wait','earliest_retry_at':start,'processed':[],'publication_approved':False}
    if now>=end:return {'status':'recovery_deadline_reached','processed':[],'publication_approved':False}
    # The caller's per-day lock guards daily actions; this short shared lock also
    # serializes reservations made through the source interface. No network here.
    from release_lock import release_lock
    with release_lock(pool.path.parent/('recovery-'+plan['coverage_date'])):
        existing=recheck_tasks(pool,plan)
        for row in existing:
            if row['spec']['config']['code']==plan['binding']['code']:continue
            rebound={**row['spec'],'config':{**row['spec']['config'],'code':plan['binding']['code']}}
            pool.enqueue_compatible(rebound,w.validate_result)
        existing=recheck_tasks(pool,plan)
        reserved = _reserve(pool,plan,policy,now,existing)
    if isinstance(reserved,dict):return reserved
    used=reserved
    return _execute_reserved(pool,plan,policy,now,end,used,executor)


def _reserve(pool,plan,policy,now,existing):
    denied=set()
    for task in pool.tasks(coverage_date=plan['coverage_date']):
        if (task.get('failure') or {}).get('http_status') in (401,403):
            source=task['spec']['config'].get('source') or {}
            denied.add(source.get('domain'))
    eligible=[];next_times=[]
    for key in plan['tasks']:
        parent=pool.get(key);spec=parent['spec']
        if spec['kind']!='academic' or parent['state']!='succeeded':continue
        if spec['config'].get('source',{}).get('domain') in denied:continue
        stamp=(parent['result'].get('evidence') or {}).get('retrieved_at')
        try:due=datetime.fromisoformat(stamp.replace('Z','+00:00')).timestamp()+policy['minimum_interval_seconds']
        except (TypeError,ValueError,AttributeError):continue
        if due>now:next_times.append(due);continue
        inputs={**spec['inputs'],'recovery':{'parent_task_id':key,'round':1,'release_date':plan['release_date']}}
        new=task_spec('academic',spec['source_id'],plan['coverage_date'],inputs,spec['config'])
        eligible.append(new)
    used={t['task_id'] for t in existing}
    already={t['current_parent_task_id'] for t in existing}
    # One deterministic recheck per successful parent. Budget counts reservations,
    # including interrupted/failed requests, never only successful responses.
    for spec in eligible:
        if spec['inputs']['recovery']['parent_task_id'] in already:continue
        if fingerprint(spec) in used:continue
        if len(used)>=policy['max_recheck_tasks']:break
        used.add(pool.enqueue(spec,max_attempts=1))
    if not used and next_times:
        return {'status':'retry_wait','earliest_retry_at':min(next_times),'processed':[],'publication_approved':False}
    if not used:
        return {'status':'recovery_no_eligible_sources','processed':[],'publication_approved':False}
    return used


def _execute_reserved(pool,plan,policy,now,end,used,executor):
    import source_worker as w
    import time
    runnable={key for key in used if pool.get(key)['spec']['config']['code']==plan['binding']['code']}
    started=time.monotonic()
    clock=lambda:now+time.monotonic()-started
    def bounded(spec):
        if clock()>=end:raise PoolConflict('recovery_deadline_reached')
        return executor(spec) if executor else w.execute_existing(spec,pool.path.parent/'checkpoints')
    worked=w.run_ready(pool,coverage_date=plan['coverage_date'],task_ids=runnable,
                       max_tasks=policy['max_tasks_per_invocation'],executor=bounded,clock=clock)
    remaining=[pool.get(key) for key in used if pool.get(key)['state'] in ('pending','running','retry_wait')]
    due=[row.get('retry_at') or row.get('lease_until') for row in remaining if row.get('retry_at') or row.get('lease_until')]
    return {'status':'recovery_deadline_reached' if clock()>=end else 'recovery_pending' if remaining else 'recovery_budget_consumed',
            'processed':worked['processed'],'reserved_rechecks':len(used),'maximum_rechecks':policy['max_recheck_tasks'],
            'earliest_retry_at':min(due) if due else None,'deadline_at':end,
            'publication_approved':False,'semantic_review_status':'not_reviewed'}
