"""Adapters between persistent acquisition tasks and the existing collectors.

Only explicit work executes network collectors. Discovery actions are returned
as typed browser calls and completed from real observations, never simulated.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import time
from datetime import date, timedelta, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from source_pool import SourcePool, PoolConflict, task_spec, fingerprint
from discovery_navigation import navigation_request, validate_navigation, browser_call

SCRIPTS = Path(__file__).resolve().parent


def code_binding():
    names = ('source_pool.py', 'source_worker.py', 'discovery_navigation.py', 'discovery_navigation.mjs',
             'material_admission.py', 'academic_sources.py', 'academic_venue_sweep.py', 'dated_source.py',
             'plos_source.py', 'aihot_candidates.py', 'source_capture.py', 'daily_coverage_evidence.py', 'paper_identity.py',
             'source_preparation.py', 'ai_social_sources.py', 'daily_execution_policy.py', 'daily_pipeline.py', 'briefing_contract.py', 'release_audit.py')
    values = {name: hashlib.sha256((SCRIPTS/name).read_bytes()).hexdigest() for name in names}
    values['source_registry'] = hashlib.sha256((SCRIPTS.parent/'references/academic_sources.v1.json').read_bytes()).hexdigest()
    return values


def plan_sources(pool, release_date, *, register=True):
    from academic_venue_sweep import build_plan_v4
    from academic_sources import sources_by_id
    from daily_delivery_policy import policy_snapshot
    from daily_coverage_evidence import RENDERED_SEARCH_TARGETS
    release = date.fromisoformat(release_date)
    if release.isoformat() != release_date:
        raise PoolConflict('release_date_invalid')
    coverage = (release-timedelta(days=1)).isoformat()
    binding = {'code': code_binding(), 'policy': policy_snapshot()}
    plan = build_plan_v4(['quantum', 'machine learning'], coverage)
    registered = sources_by_id()
    tasks = []
    register_spec = pool.enqueue if register else fingerprint
    for row in plan['rows']:
        spec = task_spec('academic', row['source_id'], coverage,
                         {'row': row, 'terms': plan['terms']}, {**binding, 'source': registered[row['source_id']]})
        tasks.append(register_spec(spec))
    tasks.append(register_spec(task_spec('aihot', 'ai_hot', coverage,
                                       {'release_date': release_date, 'source': 'api', 'mode': 'selected', 'take': 50}, binding)))
    for source_class in sorted(RENDERED_SEARCH_TARGETS):
        tasks.append(register_spec(task_spec('discovery', source_class, coverage,
                                           {'navigation': navigation_request(source_class, coverage)}, binding)))
    if release_date >= '2026-10-16':
        from ai_social_sources import registry
        for source in registry():
            tasks.append(register_spec(task_spec('fixed_source',source['id'],coverage,{},binding)))
    return {'version': 1, 'release_date': release_date, 'coverage_date': coverage,
            'binding': binding, 'tasks': tasks, 'semantic_review_status': 'not_reviewed', 'publication_approved': False}


def validate_result(spec, value):
    if spec['config'].get('code') != code_binding():
        return ['task_code_changed']
    if not isinstance(value, dict):
        return ['result_shape_invalid']
    if spec['kind'] == 'academic':
        from academic_sources import row_evidence_failures, row_is_healthy
        if value.get('source_id') != spec['source_id'] or not row_is_healthy(value, spec['coverage_date']):
            return ['academic_source_incomplete']
        return row_evidence_failures(value, spec['coverage_date'])
    if spec['kind'] == 'aihot':
        from daily_coverage_evidence import validate_ai_hot_window
        return validate_ai_hot_window(value.get('ai_hot_window'), spec['coverage_date'])
    if spec['kind'] == 'discovery':
        from daily_coverage_evidence import validate_rendered_search_observation
        request = spec['inputs']['navigation']
        validate_navigation(request)
        if value.get('source_class') != spec['source_id'] or value.get('query_url') != request['url']:
            return ['discovery_task_binding_changed']
        return validate_rendered_search_observation(value, spec['coverage_date'])
    if spec['kind'] == 'fixed_source':
        from ai_social_sources import validate
        return validate(value,spec['source_id'],spec['coverage_date'])
    if spec['kind'] == 'capture':
        from source_capture import validate_capture
        return validate_capture(spec['inputs']['item'], value.get('record', {}))
    return ['unsupported_task_kind']


def enqueue_captures(pool, config_path, news_root, coverage_date):
    """Reuse the existing excerpt/capture recovery before daily prose or a Fable exists."""
    from daily_delivery_policy import policy_snapshot
    from source_pool import checked_path
    config_path = checked_path(config_path)
    raw = config_path.read_bytes()
    if len(raw) > 32_000_000:
        raise PoolConflict('capture_input_too_large')
    config = json.loads(raw.decode('utf-8'))
    if not isinstance(config, dict) or not isinstance(config.get('sections'), list):
        raise PoolConflict('capture_input_sections_invalid')
    sha = hashlib.sha256(raw).hexdigest()
    keys = []
    for section in config['sections']:
        if not isinstance(section, dict) or not isinstance(section.get('items'), list):
            raise PoolConflict('capture_input_section_invalid')
        for item in section['items']:
            if not isinstance(item, dict) or item.get('material_kind') not in {'academic', 'social'}:
                raise PoolConflict('capture_material_kind_required')
            source = item.get('source_id') or urlsplit(item.get('source_url', '')).hostname
            spec = task_spec('capture', source or '', coverage_date,
                             {'item': item, 'config_path': str(config_path), 'config_sha256': sha,
                              'news_root': str(Path(news_root).resolve())},
                             {'code': code_binding(), 'policy': policy_snapshot()})
            keys.append(pool.enqueue(spec))
    return keys


def failure_for(exc, *, http_status=None, retry_after=None):
    """Use existing bounded/sanitized capture taxonomy; never persist exception text."""
    from source_capture import capture_failure
    if http_status is not None:
        exc = HTTPError('https://public.invalid/', http_status, '',
                        {'Retry-After': str(retry_after)} if retry_after is not None else {}, None)
    status = exc.code if isinstance(exc, HTTPError) else http_status
    header = (exc.headers or {}).get('Retry-After') if isinstance(exc, HTTPError) else retry_after
    now = datetime.now(timezone.utc)
    raw = capture_failure(exc, 'http_request', now)
    if status in (429,503) and header:
        try:
            seconds = int(header) if str(header).isdigit() else math.ceil((parsedate_to_datetime(header)-now).total_seconds())
            if 0 <= seconds <= 86400:
                raw.update(code='source_rate_limited' if status==429 else 'source_server_error', retryable=True, retry_after_seconds=seconds)
            elif seconds > 86400:
                raw.update(code='source_rate_limit_deferred', retryable=False)
                raw.pop('retry_after_seconds', None)
        except (ValueError, TypeError, OverflowError):
            pass
    return {k: raw[k] for k in ('code', 'retryable', 'http_status', 'retry_after_seconds') if k in raw}


def execute_existing(spec, checkpoint_dir):
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    key = fingerprint(spec)
    checkpoint = checkpoint_dir/(key+'.json')
    if spec['kind'] == 'academic':
        from academic_venue_sweep import build_plan_v4, fetch_evidence_v4
        plan = build_plan_v4(spec['inputs']['terms'], spec['coverage_date'])
        plan['rows'] = [copy.deepcopy(spec['inputs']['row'])]
        plan['sources'] = [spec['source_id']]
        value = fetch_evidence_v4(plan, max_workers=1, checkpoint=checkpoint,
                                  progress_output=checkpoint_dir/(key+'.partial.json'))
        return value['rows'][0]
    if spec['kind'] == 'aihot':
        from aihot_candidates import parse_args, api_items, build_config
        args = parse_args(['--source', 'api', '--mode', 'selected', '--take', '50',
                           '--date', spec['inputs']['release_date'], '--coverage-date', spec['coverage_date'],
                           '--checkpoint', str(checkpoint), '--output', str(checkpoint_dir/(key+'.partial.json'))])
        diagnostics = []
        items, evidence = api_items(args, on_failure=lambda exc: diagnostics.append(failure_for(exc)))
        value = build_config(items, args, 'api', evidence)
        if diagnostics:
            value['task_diagnostic'] = diagnostics[-1]
        from collection_checkpoint import atomic_json
        atomic_json(Path(args.output), value)
        return value
    if spec['kind'] == 'fixed_source':
        from ai_social_sources import collect
        return collect(spec['source_id'],spec['coverage_date'])
    if spec['kind'] == 'capture':
        from source_capture import capture_report, capture_path
        path = Path(spec['inputs']['config_path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec['inputs']['config_sha256']:
            raise PoolConflict('capture_input_changed')
        root = Path(spec['inputs']['news_root'])
        report = capture_report(path, spec['coverage_date'], news_root=root, item_id=spec['inputs']['item']['id'])
        if report['failures']:
            return {'capture_failures': report['failures']}
        artifact = capture_path(root, spec['coverage_date'], spec['inputs']['item']['id'])
        raw = artifact.read_bytes()
        return {'record': json.loads(raw.decode('utf-8')),
                'artifact_sha256': hashlib.sha256(raw).hexdigest()}
    raise PoolConflict('browser_task_requires_actual_observation')


def run_ready(pool, *, max_tasks=4, executor=None, clock=time.time, coverage_date=None, task_ids=None):
    if type(max_tasks) is not int or not 1 <= max_tasks <= 32:
        raise PoolConflict('work_budget_invalid')
    results = []
    replacement_required=[]
    tasks=pool.tasks(coverage_date=coverage_date)
    blocked_hosts=set()
    for task in tasks:
        if task['spec']['kind']=='capture' and task['spec']['inputs'].get('item',{}).get('ai_source_provenance') and (task['failure'] or {}).get('http_status') in (401,403):
            blocked_hosts.add((task['spec']['coverage_date'],urlsplit(task['spec']['inputs']['item']['source_url']).hostname))
    for pending in tasks:
        if task_ids is not None and pending['task_id'] not in task_ids: continue
        item=pending['spec']['inputs'].get('item',{})
        if pending['state']=='succeeded' and pending['spec']['kind']=='capture' and item.get('ai_source_provenance'): continue
        if pending['spec']['kind']=='capture' and item.get('ai_source_provenance') and (pending['spec']['coverage_date'],urlsplit(item['source_url']).hostname) in blocked_hosts:
            replacement_required.append({'task_id':pending['task_id'],'item_id':item['id'],
                                         'reason':'same_ai_original_host_access_denied','action':'choose_another_approved_pool_candidate'})
            continue
        if pending['spec']['kind']=='fixed_source':
            from ai_social_sources import registered,aware
            source=registered(pending['spec']['source_id'])
            if source['role']=='backup':
                primary=[pool.get(t['task_id']) for t in tasks if t['spec']['coverage_date']==pending['spec']['coverage_date'] and t['spec']['kind']=='fixed_source' and registered(t['spec']['source_id'])['source_class']==source['source_class'] and registered(t['spec']['source_id'])['role']=='primary']
                if any(t['state'] in ('pending','running') for t in primary): continue
                count=sum(1 for t in primary if t['state']=='succeeded' for c in t['result']['candidates'] if aware(c.get('published_at')) and aware(c['published_at']).astimezone(__import__('ai_social_sources').ZONE).date().isoformat()==pending['spec']['coverage_date'])
                original_denied=any((pending['spec']['coverage_date'],urlsplit(registered(t['spec']['source_id'])['url']).hostname) in blocked_hosts for t in primary)
                if all(t['state']=='succeeded' for t in primary) and count>=3 and not original_denied: continue
        if len(results) >= max_tasks:
            break
        if pending['spec']['kind'] == 'discovery':
            continue  # These need an explicit existing-tab observation, not an HTTP substitute.
        lease = pool.claim(task_id=pending['task_id'], now=clock(), lease_seconds=900)
        if lease is None:
            continue
        key, token, spec = lease['task_id'], lease['lease'], lease['spec']
        try:
            if spec['config'].get('code') != code_binding():
                raise PoolConflict('task_code_changed')
            value = executor(spec) if executor is not None else execute_existing(spec, pool.path.parent/'checkpoints')
            failures = validate_result(spec, value)
            if failures:
                evidence = value.get('evidence') or {}
                status = evidence.get('status_code')
                if value.get('task_diagnostic'):
                    diagnostic = value['task_diagnostic']
                elif status in (401, 403, 404, 410, 429, 500, 502, 503, 504, 408):
                    diagnostic = failure_for(ValueError(), http_status=status, retry_after=evidence.get('retry_after'))
                elif evidence.get('failure_diagnostic'):
                    diagnostic = {k: evidence['failure_diagnostic'][k] for k in
                                  ('code', 'retryable', 'http_status', 'retry_after_seconds') if k in evidence['failure_diagnostic']}
                elif value.get('capture_failures'):
                    diagnostic = {k: value['capture_failures'][0][k] for k in
                                  ('code', 'retryable', 'http_status', 'retry_after_seconds') if k in value['capture_failures'][0]}
                elif spec['kind'] == 'aihot' and not value.get('ai_hot_window', {}).get('recovery', {}).get('action_required'):
                    diagnostic = {'code': 'pagination_incomplete', 'retryable': True}
                else:
                    diagnostic = {'code': 'result_validation_failed', 'retryable': False}
                state = pool.fail(key, token, diagnostic, now=clock)
            else:
                state = pool.complete(key, token, value, validate_result, now=clock)
        except Exception as exc:
            diagnostic = ({'code': str(exc), 'retryable': False} if isinstance(exc, PoolConflict)
                          else failure_for(exc) if isinstance(exc, (OSError, ValueError, TypeError))
                          else {'code': 'collector_'+type(exc).__name__, 'retryable': False})
            try:
                state = pool.fail(key, token, diagnostic, now=clock)
            except PoolConflict as conflict:
                if str(conflict) != 'stale_or_expired_lease':
                    raise
                # Another worker owns recovery after expiry. Do not overwrite
                # its state or abort unrelated ready tasks with a stale token.
                results.append({'task_id': key, 'state': 'lease_lost',
                                'failure': {'code': 'stale_or_expired_lease', 'retryable': False}})
                continue
        if spec['kind']=='capture' and spec['inputs']['item'].get('ai_source_provenance') and (state['failure'] or {}).get('http_status') in (401,403):
            blocked_hosts.add((spec['coverage_date'],urlsplit(spec['inputs']['item']['source_url']).hostname))
        results.append({'task_id': key, 'state': state['state'], 'failure': state['failure']})
    return {'processed': results, 'replacement_required':replacement_required, 'execution_mode': 'existing_adapters' if executor is None else 'injected_test_adapter',
            'semantic_review_status': 'not_reviewed', 'publication_approved': False}


def claim_discovery(pool, task_id, *, now=None):
    task = pool.get(task_id)
    if task['spec']['kind'] != 'discovery':
        raise PoolConflict('not_a_discovery_task')
    if task['spec']['config'].get('code') != code_binding():
        raise PoolConflict('task_code_changed')
    lease = pool.claim(task_id=task_id, now=now, lease_seconds=900)
    if lease is None:
        return {'state': pool.get(task_id)['state'], 'action': None}
    request = lease['spec']['inputs']['navigation']
    return {'task_id': task_id, 'lease': lease['lease'], 'navigation': request,
            'browser_call': browser_call(request), 'policy_denial_action': 'stop_and_record_blocked'}


def submit_discovery(pool, task_id, lease, observation, *, now=None):
    if pool.get(task_id)['spec']['kind'] != 'discovery':
        raise PoolConflict('not_a_discovery_task')
    return pool.complete(task_id, lease, observation, validate_result, now=now)


def source_snapshot(pool, plan):
    """A derived handoff, not a competing daily lifecycle or a release receipt."""
    if plan != plan_sources(pool, plan['release_date'], register=False):
        raise PoolConflict('plan_input_date_or_config_changed')
    from academic_venue_sweep import build_plan_v4
    from academic_sources import family_gate, health_table
    rows, hot, discovery, missing, fixed = [], None, [], [], []
    for key in plan['tasks']:
        try:
            task = pool.get(key)
        except PoolConflict as exc:
            if str(exc) != 'unknown_task':
                raise
            missing.append({'task_id': key, 'state': 'not_registered', 'failure': None, 'retry_at': None})
            continue
        spec = task['spec']
        if (spec['coverage_date'] != plan['coverage_date'] or spec['config']['policy'] != plan['binding']['policy']
                or spec['config']['code'] != plan['binding']['code']):
            raise PoolConflict('plan_task_binding_changed')
        if task['state'] != 'succeeded':
            missing.append({'task_id': key, 'kind': spec['kind'], 'source_id': spec['source_id'],
                            'state': task['state'], 'failure': task['failure'], 'retry_at': task['retry_at']})
        if spec['kind'] == 'academic':
            rows.append(task['result'] if task['state'] == 'succeeded' else
                        {**spec['inputs']['row'], 'result': 'error', 'retrieval_status': 'error',
                         'evidence': {'error': (task['failure'] or {}).get('code', 'pending')}})
        elif spec['kind'] == 'aihot' and task['state'] == 'succeeded':
            hot = task['result']
        elif spec['kind']=='fixed_source' and task['state']=='succeeded':
            fixed.append(task['result'])
        elif spec['kind'] == 'discovery' and task['state'] == 'succeeded':
            discovery.append(task['result'])
    academic = build_plan_v4(['quantum', 'machine learning'], plan['coverage_date'])
    academic.update(rows=rows, family_gate=family_gate(rows, require_query=True), source_health=health_table(rows, require_query=True))
    from ai_social_sources import pool_evidence
    ai=pool_evidence(fixed,plan['coverage_date']) if plan['release_date']>='2026-10-16' else None
    complete = academic['family_gate']['status'] == 'pass' and hot is not None and len(discovery) == 3
    if ai is not None: complete=complete and ai['status']=='discovery_available'
    return {'source_preparation_version': 1, 'release_date': plan['release_date'], 'coverage_date': plan['coverage_date'],
            'status': 'coverage_ready' if complete else 'coverage_pending', 'academic': academic, 'aihot': hot,
            'supplementary_discovery': discovery, 'missing_tasks': missing, 'ai_fixed_pool':ai,
            'allowed_actions': ['continue_independent_tasks', 'author_admitted_materials'],
            'semantic_review_status': 'not_reviewed', 'publication_approved': False}
