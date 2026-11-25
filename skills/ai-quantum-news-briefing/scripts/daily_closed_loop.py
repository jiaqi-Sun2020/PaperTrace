"""Bounded executor for one frozen edition. Disabled until a host policy is approved.

The queue is an execution journal, never a source/review/publication authority.
Workers run in fresh Codex processes. Their exit status cannot approve a release.
No scheduler, credential, publishing enablement or notification transport is changed.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import io
import json
import re
import subprocess
import time
import uuid
import copy
import tempfile
from owned_process import run_owned, OwnedProcessError
from worker_diagnostics import WorkerTrace, error_metadata

from collection_checkpoint import atomic_json
from daily_continuation import _queue, _record, begin, finish
from daily_execution_policy import execution_window, retired
from release_lock import release_lock
from source_pool import PoolConflict, checked_path, fingerprint

SHANGHAI = timezone(timedelta(hours=8))
REVIEW_ROLES = ('news_review', 'story_review', 'display_review')
AGENT_ROLES = ('discovery', 'qualification', 'author', 'repair') + REVIEW_ROLES
TERMINAL = {'completed', 'blocked', 'expired', 'budget_exhausted', 'not_scheduled'}
BROWSER_RECOVERABLE = {'browser_initialization_timeout', 'browser_runtime_unavailable',
                       'browser_connection_unavailable'}


def policy_bounds(policy, day):
    execution_window(day)
    if not isinstance(policy, dict) or type(policy.get('version')) is not int or policy.get('version') != 1 or type(policy.get('enabled')) is not bool:
        raise ValueError('closed_loop_policy_invalid')
    if not policy['enabled']:
        return None
    if policy.get('timezone') != 'Asia/Shanghai' or policy.get('start_time') != '01:00':
        raise ValueError('closed_loop_start_must_be_0100_shanghai')
    clock = policy.get('deadline_time')
    if not isinstance(clock, str) or not re.fullmatch(r'\d{2}:\d{2}', clock):
        raise ValueError('closed_loop_deadline_required')
    start = datetime.fromisoformat(day + 'T01:00:00+08:00').timestamp()
    end = datetime.fromisoformat(day + 'T' + clock + ':00+08:00').timestamp()
    if end <= start:
        raise ValueError('closed_loop_deadline_invalid')
    for key, low, high in (('max_actions', 1, 128), ('max_agent_invocations', 1, 16),
                          ('max_steps_per_invocation', 1, 32), ('no_progress_limit', 1, 3),
                          ('agent_timeout_seconds', 30, 1800)):
        if type(policy.get(key)) is not int or not low <= policy[key] <= high:
            raise ValueError('closed_loop_bound_invalid_' + key)
    if type(policy.get('allow_publish')) is not bool:
        raise ValueError('closed_loop_publish_policy_required')
    for key,default,low,high in (('driver_wait_seconds',0,0,86400),('max_tasks_per_batch',4,1,4),
                               ('browser_recovery_attempts',2,1,3),('browser_recovery_delay_seconds',300,60,1800)):
        value=policy.get(key,default)
        if type(value) is not int or not low<=value<=high:raise ValueError('closed_loop_bound_invalid_'+key)
    if type(policy.get('allow_preview',False)) is not bool:raise ValueError('closed_loop_preview_policy_invalid')
    if 'codex_model' in policy and (not isinstance(policy['codex_model'],str)
            or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9.-]{0,79}',policy['codex_model'])):
        raise ValueError('closed_loop_model_identity_invalid')
    command = policy.get('codex_argv')
    if (not isinstance(command, list) or len(command) not in (1, 2)
            or any(not isinstance(s, str) or not s or '\x00' in s for s in command)
            or any(s.startswith('-') for s in command)
            or len(command) == 2 and not command[1].lower().endswith('.js')):
        raise ValueError('closed_loop_agent_runtime_required')
    return start, end


def load_policy(path, expected_sha256, day):
    path = checked_path(path)
    data = path.read_bytes()
    if len(data) > 65536 or not re.fullmatch('[0-9a-f]{64}', expected_sha256 or ''):
        raise ValueError('closed_loop_policy_digest_required')
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError('closed_loop_policy_digest_mismatch')
    policy = json.loads(data)
    policy_bounds(policy, day)
    return policy


def _save(root, day, state, *, outcome=None):
    """Short queue transaction, preserving all other dates and owners' fields."""
    with release_lock(root):
        path, queue, records = _queue(root)
        record = _record(day, records.get(day, {}))
        record.update(version=1, date=day, closed_loop=state)
        records[day] = record
        queue['daily_continuations'] = records
        if outcome:
            outbox = queue.setdefault('notification_outbox', {})
            if not isinstance(outbox, dict):
                raise PoolConflict('notification_outbox_invalid')
            key = fingerprint({'date': day, 'status': outcome['status'], 'code': outcome.get('code'),
                               'input': state.get('last_input')})
            # Outbox creation is not notification delivery. Never send implicitly.
            outbox.setdefault(key, {'version': 1, 'id': key, 'date': day,
                                   'status': 'pending_send', 'outcome': outcome,
                                   'created_at': state['updated_at']})
        atomic_json(path, queue)


def _load(root, day):
    _, _, records = _queue(root)
    record = _record(day, records.get(day, {}))
    state = record.get('closed_loop')
    if state is None:
        return {'version': 1, 'date': day, 'coverage': execution_window(day), 'actions': [], 'no_progress': 0}
    if (not isinstance(state, dict) or state.get('version') != 1 or state.get('date') != day
            or state.get('coverage') != execution_window(day) or not isinstance(state.get('actions'), list)):
        raise PoolConflict('closed_loop_journal_invalid')
    for action in state['actions']:
        if (not isinstance(action,dict) or action.get('action') not in AGENT_ROLES+('plan','work','recover','stage','review_template','seal','finalize','online','publish')
                or action.get('status') not in {'reserved','interrupted','failed','completed','blocked','retry_wait'}
                or type(action.get('agent_slots',0)) is not int or action.get('agent_slots',0)<0
                or ('agent_slots' in action and action['agent_slots']!=(2 if action['action']=='story_review' else int(action['action'] in AGENT_ROLES)))):
            raise PoolConflict('closed_loop_action_journal_invalid')
    return state


def _review_done(state, role, identity):
    return any(a.get('action') == role and a.get('input') == identity and a.get('status') == 'completed'
               for a in state['actions'])


def browser_failures(state):
    values=[a for a in state['actions'] if a['action']=='discovery' and a.get('code') in BROWSER_RECOVERABLE]
    if any(type(a.get('finished_at')) not in (int,float) or not __import__('math').isfinite(a['finished_at']) for a in values):
        raise PoolConflict('browser_recovery_journal_invalid')
    return values


def task_due(row, now):
    if row.get('kind')!='discovery' and row.get('work_eligible') is False:return False
    if row.get('state')=='pending':return True
    if row.get('state') not in {'running','retry_wait'}:return False
    retry=row.get('retry_at')
    # Missing lease/retry timing is not a license to spin on an unknown owner.
    return type(retry) in (int,float) and retry<=now


def choose(snapshot, state, policy, *, now=None):
    """Only named built-in actions; never execute a queue's stored argv."""
    now=time.time() if now is None else now
    phase = snapshot['phase']
    if phase == 'workflow_complete':
        return 'complete'
    if phase in {'historical_retired', 'workflow_retired'}:
        return 'retired'
    if phase in {'local_manifest_invalid', 'execution_blocked', 'source_blocked'}:
        return 'block'
    if phase == 'remote_pending':
        # Every entry and every uncertain upload first obtains a fresh online
        # observation. The publisher additionally reconciles each object itself.
        if not state.get('remote_probe') or state['remote_probe'].get('input') != snapshot['identity']:
            return 'online'
        if state['remote_probe']['status'] in {'unavailable', 'unreachable', 'unknown', 'not_checked'}:
            return 'remote_unavailable'
        return 'publish' if policy['allow_publish'] else 'publish_disabled'
    if phase in {'review_pending', 'ready_to_finalize'}:
        if snapshot.get('reviews_missing'):return 'review_template'
        for role in REVIEW_ROLES:
            if role not in snapshot.get('approved_review_roles',[]) and not _review_done(state, role, snapshot['identity']):
                return role
        if not snapshot.get('independent_reviews'):
            return 'review_not_independent'
        return 'finalize' if phase == 'ready_to_finalize' else 'seal'
    if phase == 'staging_invalid':
        return 'repair'
    if phase == 'candidate_ready':
        return 'stage' if snapshot.get('opening_story_status') != 'authoring_pending' else 'author'
    if phase in {'candidate_invalid', 'candidate_authoring_pending'}:
        return 'author'
    source = snapshot.get('source', {})
    missing = source.get('missing_tasks', [])
    if phase in {'candidate_waiting_capture', 'article_qualification_pending'}:
        if any(r.get('kind')=='capture' and task_due(r,now) for r in missing):return 'work'
        if any(r.get('kind')=='capture' and r.get('state') in {'running','retry_wait'} for r in missing):return 'source_wait'
        return 'qualification'
    if phase == 'candidate_shortage':
        # Drain already registered normal-scope peers before requesting expansion.
        if any(r.get('kind')!='discovery' and task_due(r,now) for r in missing):return 'work'
        if any(r.get('kind')!='discovery' and r.get('state') in {'running','retry_wait'} for r in missing):return 'source_wait'
        return 'shortage' if snapshot.get('recovery_exhausted') else 'recover'
    if source.get('status') == 'not_initialized' or any(r.get('state') == 'not_registered' for r in missing):
        return 'plan'
    if any(r.get('kind') != 'discovery' and task_due(r,now) for r in missing):
        return 'work'
    if any(r.get('kind') == 'discovery' and task_due(r,now) for r in missing):
        failures=browser_failures(state)
        used=sum(a.get('agent_slots',int(a['action'] in AGENT_ROLES)) for a in state['actions'])
        if used>=policy['max_agent_invocations']:
            if any(r.get('kind')!='discovery' and r.get('state') in {'running','retry_wait'} for r in missing):return 'source_wait'
            return 'browser_agent_budget_exhausted'
        if len(failures)>=policy.get('browser_recovery_attempts',2):
            if any(r.get('kind')!='discovery' and r.get('state') in {'running','retry_wait'} for r in missing):return 'source_wait'
            return 'browser_recovery_exhausted'
        if failures and now<failures[-1]['finished_at']+policy.get('browser_recovery_delay_seconds',300):return 'browser_wait'
        return 'discovery'
    if any(r.get('state') in {'running','retry_wait'} for r in missing):return 'source_wait'
    return 'author' if phase == 'authoring_pending' else 'block'


class Backend:
    """Production adapter, using the installed validators and lifecycle owners."""
    def __init__(self, orchestrator, recovery_policy=None, recovery_path=None):
        self.o = orchestrator
        self.root = orchestrator.NEWS_ROOT
        self.recovery_policy = recovery_policy
        self.recovery_path = recovery_path

    def integrity(self):
        code = {}
        project=Path(self.o.__file__).resolve().parents[3]
        for folder in ('skills/ai-quantum-news-briefing/scripts','skills/ai-quantum-news-briefing/references',
                       'skills/allegory-teach/scripts','skills/allegory-teach/references','skills/utils/lean-html-skill/scripts'):
            for path in sorted((project / folder).glob('*')):
                if path.suffix not in {'.py','.mjs','.js','.json','.md','.html','.css'}:continue
                checked_path(path)
                code[path.relative_to(project).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return fingerprint(code)

    def snapshot(self, day):
        daily = self.o._daily_execution(day, action='status')
        edition = self.o.inspect(day)
        phase = daily.get('phase') or (daily.get('edition_state') or {}).get('phase')
        if daily.get('run_outcome') == 'completed':
            phase = 'workflow_complete'
        elif edition.get('phase') in {'remote_pending', 'local_manifest_invalid', 'ready_to_finalize',
                                     'review_pending', 'staging_invalid', 'candidate_ready',
                                     'candidate_invalid', 'candidate_authoring_pending', 'candidate_waiting_capture'}:
            phase = edition['phase']
        acquisition = daily.get('source_preparation') or {}
        source = acquisition.get('source_preparation', acquisition)
        content = daily.get('content_readiness', {})
        source = {**source, 'missing_tasks': [dict(r) for r in source.get('missing_tasks', [])]}
        pool_path = self.root / '_sources' / 'pool.sqlite'
        if pool_path.exists() and any(r.get('state') in {'running','retry_wait'} for r in source['missing_tasks']):
            from source_pool import SourcePool
            with SourcePool(pool_path, read_only=True) as pool:
                for row in source['missing_tasks']:
                    if row.get('state') in {'running','retry_wait'}:
                        task=pool.get(row['task_id'])
                        row['retry_at'] = task['lease_until'] if row['state']=='running' else task['retry_at']
        recoverable = [r for r in source['missing_tasks'] if r.get('state') in {'pending','retry_wait','running','not_registered'}]
        retries = [r['retry_at'] for r in recoverable if r.get('retry_at') and r['retry_at'] > time.time()]
        # One rate-limited peer must not hold back an independently due peer.
        all_waiting = recoverable and len(retries) == len(recoverable)
        # Running source leases are reclaimed only by the source pool on its
        # own task claim. No task state/attempt counter is edited here.
        identity = None
        independent = False
        reviews={};approved=[];templates_missing=False
        if edition.get('stage'):
            from release_audit import content_digest, REVIEW_NAMES, BASE_KEYS
            stage = checked_stage(self.root, day, edition['stage'])
            manifest = self.o.load_json(stage / ('daily_pipeline_manifest_' + day + '.json'))
            actual = {}
            for key in BASE_KEYS:
                path = checked_path(stage / manifest['artifacts'][key])
                if path.parent != stage:
                    raise ValueError('closed_loop_artifact_path_invalid')
                actual[key] = hashlib.sha256(path.read_bytes()).hexdigest()
            identity = fingerprint({'manifest_content': content_digest(manifest), 'actual': actual})
            methods = []
            for role in ('news_review', 'story_review'):
                p = stage / REVIEW_NAMES[role].format(date=day)
                reviews[role]=self.o.load_json(p) if p.exists() else None
                methods.append((reviews[role] or {}).get('review_method'))
            independent = methods == ['independent', 'independent']
            templates_missing=all(v is None for v in reviews.values())
            if any(v is None for v in reviews.values()) and not templates_missing:
                raise ValueError('closed_loop_partial_review_templates')
            if independent:
                from release_audit import validate_bundle
                story=reviews['story_review'];third=next((r for r in story.get('rounds',[]) if r.get('id')=='cross-surface-and-display'),{})
                if isinstance(third.get('display_review'),dict) and not validate_bundle(stage,manifest,require_manifest_binding=False,require_audit_report=False):
                    approved=list(REVIEW_ROLES)
        candidate = edition.get('candidate')
        candidate_hash = hashlib.sha256(Path(candidate).read_bytes()).hexdigest() if candidate else None
        identity = identity or fingerprint({'phase': phase, 'candidate': candidate_hash,
                                            'html': edition.get('html_sha256'),
                                            'deployment': edition.get('deployment_id'),
                                            'content': content, 'source': source})
        return {'phase': phase or 'execution_blocked', 'identity': identity, 'source': source,
                'content': content, 'stage': edition.get('stage'), 'candidate': candidate,
                'opening_story_status': edition.get('opening_story_status'),
                'independent_reviews': independent,
                'reviews':reviews,'reviews_missing':templates_missing,'approved_review_roles':approved,
                'recovery_exhausted': bool(content.get('rechecks', {}).get('all_terminal')),
                'retry_at': min(retries) if all_waiting else None,
                'blocker': daily.get('terminal_blocker'), 'edition': edition}

    def perform(self, action, day, snapshot, policy, timeout):
        if action in REVIEW_ROLES:return self.review(action,day,snapshot,policy,timeout)
        if action in AGENT_ROLES:return run_agent(self.root, day, action, snapshot, policy, timeout)
        if action in {'plan', 'work', 'recover'}:
            if action == 'recover' and not self.recovery_policy:
                return {'status': 'blocked', 'code': 'approved_recovery_policy_required'}
            result = self.o._daily_execution(day, action=action, record=True, max_tasks=policy.get('max_tasks_per_batch',4),
                        recovery_policy=self.recovery_policy, recovery_policy_path=self.recovery_path)
            recovery = result.get('recovery') or {}
            if recovery.get('status') == 'retry_wait':
                retry=self.snapshot(day).get('retry_at') if action=='work' else recovery.get('earliest_retry_at')
                if retry:return {'status':'retry_wait','code':'source_retry_after','retry_at':retry}
            if recovery.get('status') in {'recovery_deadline_reached','recovery_no_eligible_sources','recovery_policy_required'}:
                return {'status': 'blocked', 'code': recovery['status']}
            if result.get('phase') in {'execution_blocked', 'source_blocked'}:
                return {'status': 'blocked', 'code': 'source_stage_blocked', 'blocker': result.get('terminal_blocker')}
            return {'status': 'completed'}
        import daily_pipeline as dp
        if action in {'stage', 'review_template', 'seal', 'finalize'}:
            if action == 'stage':
                cover = execution_window(day)['coverage_date']
                args = ['run', '--config', snapshot['candidate'], '--date', day,
                        '--coverage-start', cover + 'T00:00:00+08:00', '--coverage-end', day + 'T00:00:00+08:00']
            else:
                stage = str(checked_stage(self.root, day, snapshot['stage']))
                args = [{'seal':'seal-review','review_template':'review-template','finalize':'finalize'}[action], '--run-dir', stage]
                if action == 'finalize':
                    args.append('--local-only')
            # Avoid mixing child CLI stdout with the sole orchestration JSON.
            with redirect_stdout(io.StringIO()):
                code = dp.main(args)
            return {'status': 'completed' if code == 0 else 'blocked',
                    'code': action + '_gate_failed' if code else None}
        if action == 'online':
            result = self.o.inspect(day, online=True, record_remote=True)
            self.o._record(result, True)
            return {'status': 'completed', 'remote_status': result.get('remote_status', 'unknown')}
        if action == 'publish':
            from publish_daily_to_oss import publish
            # Existing publisher checks enabled/site/Bucket/content and exact
            # objects before writing. A timeout never means "upload again".
            result = publish(self.root / day, self.root.parent / 'news_publish.local.json')
            if result.get('status') in {'published', 'no_change'}:
                return {'status': 'completed'}
            if result.get('status') == 'pending':
                return {'status': 'retry_wait', 'code': 'upload_outcome_uncertain', 'retry_at': time.time() + 3600}
            return {'status': 'blocked', 'code': 'publisher_' + str(result.get('status', 'unknown'))}
        raise ValueError('closed_loop_action_invalid')

    def review(self,role,day,snapshot,policy,timeout):
        from release_audit import REVIEW_NAMES
        from daily_authoring import save
        stage=checked_stage(self.root,day,snapshot['stage'])
        kind='news_review' if role=='news_review' else 'story_review'
        path=checked_path(stage/REVIEW_NAMES[kind].format(date=day))
        raw=path.read_bytes();old=json.loads(raw);expected=hashlib.sha256(raw).hexdigest()
        packet={**snapshot,'review_template':old}
        manifest=self.o.load_json(stage/('daily_pipeline_manifest_'+day+'.json'))
        if role=='display_review':
            from release_audit import validate_bundle
            failures=validate_bundle(stage,manifest,require_manifest_binding=False,
                                     require_audit_report=False,preview_display_pending=True)
            if failures:return {'status':'blocked','code':'pre_display_content_gate_failed'}
            if not policy.get('allow_preview',False):return {'status':'blocked','code':'approved_preview_policy_required'}
            from publish_daily_to_oss import preview,PublishError
            from daily_revisions import run_snapshot
            try:
                packet['preview']=preview(stage,self.root.parent/'news_publish.local.json',
                    expected_run_sha256=run_snapshot(self.root,stage)['sha256'],
                    expected_html_sha256=manifest['artifact_sha256']['html'])
            except PublishError as exc:
                return {'status':'blocked','code':exc.code}
        if role=='story_review':
            story=self.o.load_json(stage/manifest['artifacts']['delta_config'])['opening_story']
            blind=run_agent(self.root,day,'story_blind',{'identity':snapshot['identity'],
                'blind_story':{k:story[k] for k in ('title','paragraphs')}},policy,max(1,timeout/2))
            if blind.get('status')!='completed':return blind
            first=blind.get('review')
            validate_blind(story,first)
            packet['blind_round']=first
        result=run_agent(self.root,day,role,packet,policy,max(1,timeout/2) if role=='story_review' else timeout)
        if result.get('status')!='completed':return result
        value=result.get('review')
        if not isinstance(value,dict):return {'status':'blocked','code':'review_proposal_required'}
        if role=='story_review':
            first=next((r for r in value.get('rounds',[]) if r.get('id')=='story-completeness'),None)
            if first!=packet['blind_round']:return {'status':'blocked','code':'blind_round_changed_after_mapping'}
            from review_evidence import validate_review_for_preview
            third=next((r for r in value.get('rounds',[]) if r.get('id')=='cross-surface-and-display'),{})
            if third.get('judgment')!='pending' or validate_review_for_preview(story,value,html_sha256=manifest['artifact_sha256']['html']):
                return {'status':'blocked','code':'story_semantics_or_pending_display_invalid'}
        if role=='display_review' and display_protected(value)!=display_protected(old):
            return {'status':'blocked','code':'display_worker_changed_semantic_review'}
        save(self.root,day,'news-review' if kind=='news_review' else 'story-review',expected,value,run_id=stage.name)
        return result


def display_protected(value):
    value=copy.deepcopy(value)
    for row in value.get('rounds',[]):
        if row.get('id')=='cross-surface-and-display':
            for key in ('display_review','judgment','unresolved'):row.pop(key,None)
    return value


def validate_blind(story,row):
    from daily_pipeline import TASK_CARD_KEYS
    from review_evidence import validate_review,story_digest
    if (not isinstance(row,dict) or row.get('id')!='story-completeness' or row.get('materials_seen')!=['title','paragraphs']
            and row.get('materials_seen')!=['paragraphs','title']):raise ValueError('blind_round_invalid')
    review={'review_protocol_version':3,'review_method':'independent','story_sha256':story_digest(story),
            'task_card':{k:'not part of blind input' for k in TASK_CARD_KEYS},'rounds':[row,
            {'id':'semantic-and-source','technical_edges':[],'unresolved':[]},{'id':'cross-surface-and-display','unresolved':[]}]}
    failures=[v for v in validate_review(story,review) if v.startswith('story-completeness:')]
    if failures:raise ValueError('blind_round_validation_failed')


def checked_stage(root, day, value):
    stage = Path(value).absolute()
    expected = (root / day / '.staging').absolute()
    if stage.parent != expected or stage.is_symlink() or not stage.is_dir():
        raise ValueError('closed_loop_stage_identity_invalid')
    checked_path(stage / ('daily_pipeline_manifest_' + day + '.json'))
    return stage


def run_agent(root, day, role, snapshot, policy, timeout):
    """Real subprocess bridge. Tests replace the process, never mark real review PASS."""
    command = policy['codex_argv']
    if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
        return {'status': 'blocked', 'code': 'agent_executable_unavailable'}
    job = uuid.uuid4().hex
    reviewing=role in REVIEW_ROLES+('story_blind',)
    work = root / '_automation' / 'closed-loop' / day / job
    trace=None;diagnostic_error=None;process=None
    try:trace=WorkerTrace(work,job=job,date=day,role=role,input_sha256=snapshot['identity'])
    except Exception as exc:diagnostic_error=error_metadata(exc)
    def phase(name,**kw):
        nonlocal diagnostic_error
        if trace:
            try:trace.observe(name,**kw)
            except Exception as exc:diagnostic_error=error_metadata(exc)
    def done(value,owner=None,*,timed_out=False):
        nonlocal diagnostic_error
        owner=owner if owner is not None else process
        output=getattr(owner,'output_metadata',None)
        cleanup=getattr(owner,'cleanup_confirmed',None)
        # A worker-provided code is not evidence that the host timed out.
        outcome='timeout' if timed_out else value['status']
        diagnostic=None
        if trace:
            try:diagnostic=trace.finish(outcome=outcome,output=output,cleanup_confirmed=cleanup)
            except Exception as exc:diagnostic_error=error_metadata(exc)
        if diagnostic_error:
            diagnostic={'status':'incomplete','errors':[diagnostic_error],'raw_text_retained':False}
        value['diagnostic']=diagnostic or {'status':'incomplete','raw_text_retained':False}
        if owner is not None:
            value['cleanup_confirmed']=cleanup
            value['cleanup_failure_codes']=getattr(owner,'cleanup_failure_codes',[])
        return value
    try:
        receipt = checked_path(work / 'worker-result.json')
        schema = checked_path(work / 'worker-result.schema.json')
        schema.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(schema, {'type': 'object', 'additionalProperties': False,
        'required': ['job_id', 'date', 'input_sha256', 'status', 'code']+(['review_json'] if reviewing else []),
        'properties': {'job_id': {'type': 'string'}, 'date': {'type': 'string'},
            'input_sha256': {'type': 'string'}, 'status': {'enum': ['completed', 'blocked']},
            'code': {'type': 'string', 'pattern': '^[a-z0-9_]{1,80}$'},
            **({'review_json':{'type':'string'}} if reviewing else {})}})
    except (OSError,ValueError) as exc:
        phase('input_write_failed')
        return done({'status':'blocked','code':'agent_input_write_failed','io_error':error_metadata(exc)})
    packet = {'version': 1, 'job_id': job, 'date': day, 'coverage': execution_window(day),
              'role': role, 'input_sha256': snapshot['identity'], 'stage': snapshot.get('stage'),
              'candidate': snapshot.get('candidate')}
    if role=='story_blind':
        packet={k:packet[k] for k in ('version','job_id','date','role','input_sha256')}
        packet['story']=snapshot['blind_story']
        # Contract, not a completed review: no technical mapping or answer key.
        packet['blind_review_contract']={
            'id':'story-completeness','judgment':'pending','materials_seen':['title','paragraphs'],
            'reviewed_text':'','reason':'','source_or_rule':'','limitation':'',
            'literal_trace':[{'story_quote':'','tracked_object':'','kind':'other_state',
                'before':'','trigger':'','operation':'','after':'','rule_origin':''}],
            'counterfactual':{'changed_condition':'','predicted_result':'','reason':''},'unresolved':[]}
    elif reviewing:
        packet['review_template']=copy.deepcopy(snapshot.get('review_template'))
        if role=='story_review':
            packet['blind_round']=snapshot['blind_round']
            # One canonical accepted blind record, never duplicate it in template.
            if isinstance(packet['review_template'],dict) and isinstance(packet['review_template'].get('rounds'),list):
                packet['review_template']['rounds']=[r for r in packet['review_template']['rounds']
                    if not isinstance(r,dict) or r.get('id')!='story-completeness']
        if role=='display_review':packet['preview']=snapshot['preview']
    try:atomic_json(checked_path(work / 'task.json'), packet)
    except (OSError,ValueError) as exc:
        phase('input_write_failed')
        return done({'status':'blocked','code':'agent_input_write_failed','io_error':error_metadata(exc)})
    prompt = worker_prompt(packet)
    phase('prepared')
    # No shell, bypass flags, alternate transport, credentials or config changes.
    # Output can include untrusted source text; retain only bounded receipt and
    # output digests, not raw terminal logs in the workflow queue.
    try:
        with tempfile.TemporaryDirectory(prefix='papertrace-review-input-') as neutral:
            cwd=neutral if role=='story_blind' else str(root.parent)
            argv=command+['exec','--ephemeral','--sandbox','read-only' if reviewing else 'workspace-write','--cd',cwd,
                         '--skip-git-repo-check','--json','--output-schema',str(schema),'--output-last-message',str(receipt),'-']
            if policy.get('codex_model'):
                model=policy['codex_model']
                if not isinstance(model,str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9.-]{0,79}',model):
                    return done({'status':'blocked','code':'closed_loop_model_identity_invalid'})
                position=len(command)+1
                argv[position:position]=['--model',model]
            process=run_owned(argv,input=prompt.encode('utf-8'),timeout=timeout,check=False,
                              capture_metadata=True,observer=trace)
        if process.returncode != 0:
            return done({'status': 'blocked', 'code': 'agent_process_failed'})
    except subprocess.TimeoutExpired as exc:
        phase('timeout')
        return done({'status': 'blocked', 'code': 'agent_timeout_outcome_uncertain'},exc,timed_out=True)
    except OwnedProcessError as exc:
        code=str(exc) if re.fullmatch('owned_[a-z_]{1,80}',str(exc)) else 'owned_process_failed'
        return done({'status':'blocked','code':code},exc)
    except OSError as exc:
        return done({'status':'blocked','code':'agent_process_io_failed','io_error':error_metadata(exc)},exc)
    try:
        checked_path(receipt)  # validate again after the external process wrote it
        if not receipt.exists() or receipt.stat().st_size > 32_000_000:
            phase('receipt_missing')
            return done({'status': 'blocked', 'code': 'agent_receipt_missing_or_large'})
        phase('receipt_read')
        raw=receipt.read_bytes()
    except (OSError,ValueError) as exc:
        phase('receipt_read_failed')
        return done({'status':'blocked','code':'agent_receipt_read_failed','io_error':error_metadata(exc)})
    if len(raw)>32_000_000:return done({'status':'blocked','code':'agent_receipt_missing_or_large'})
    try:result = json.loads(raw.decode('utf-8'))
    except (ValueError,UnicodeError,RecursionError):
        phase('receipt_invalid')
        return done({'status':'blocked','code':'agent_receipt_invalid_json'})
    if (not isinstance(result,dict) or set(result) != {'job_id', 'date', 'input_sha256', 'status', 'code'}|({'review_json'} if reviewing else set())
            or result['job_id'] != job or result['date'] != day or result['input_sha256'] != snapshot['identity']
            or not isinstance(result['status'],str) or result['status'] not in {'completed', 'blocked'}
            or not isinstance(result['code'],str) or not re.fullmatch('[a-z0-9_]{1,80}', result['code'])):
        phase('receipt_invalid')
        return done({'status': 'blocked', 'code': 'agent_receipt_identity_invalid'})
    if reviewing:
        try:result['review']=json.loads(result.pop('review_json'))
        except (TypeError,ValueError,RecursionError):return done({'status':'blocked','code':'review_proposal_invalid_json'})
    phase('receipt_valid')
    return done({**result, 'receipt_sha256': hashlib.sha256(raw).hexdigest()})


def worker_prompt(packet):
    if packet['role']=='story_blind':
        return ('You are an independent story-only reviewer in a fresh ephemeral context.\n'+json.dumps(packet,ensure_ascii=False)+'\n'
                'Read only the supplied title and paragraphs. Do not seek project files, technical mapping or answers. '
                'review_json must encode ONE object with the exact keys and types of blind_review_contract. '
                'id is exactly story-completeness. materials_seen is the two-string array, never an object. '
                'judgment is the string pass, fail or pending, never an object. The template pending and empty '
                'fields are unreviewed placeholders, not evidence: replace them with your actual findings. '
                'reviewed_text must be ONE contiguous verbatim excerpt from the title or ONE paragraph: '
                'no heading, quote marks added by you, explanation, concatenated excerpts or newlines. '
                'Put explanations in reason and separate exact story_quote excerpts in literal_trace. '
                'A completed worker response means the review was performed, not that it passed. Keep failures '
                'and unresolved findings explicit. Do not manufacture pass to satisfy a validator. '
                'Return review_json containing only the complete protocol-3 story-completeness round: materials_seen title/paragraphs, '
                'a literal state trace, changed-condition counterfactual, quoted narrative, reasons, limitations, judgment and unresolved findings. '
                'Do not invent a pass when the story alone is insufficient. Do not edit files or invoke publication. '
                'The other required receipt fields must match the supplied identity.')
    duties = {
        'discovery': 'Complete missing typed browser discovery with real permitted browser observations and separate original HTTP receipts. Use evidence_persistence probe/save-discovery and source_preparation resume-discovery. Never reconstruct bytes from prose. Reuse valid saved observations; reclaim only expired own task leases through the supported claim interface. If the supported browser initialization times out before any page is selected, return blocked with code browser_initialization_timeout; for an unavailable runtime use browser_runtime_unavailable. Do not mislabel these as source 403 or save failures. Stop this worker after one failed initialization; the host owns bounded recovery. A policy rejection or source denial must retain its actual code, never one of these retryable environment codes.',
        'qualification': 'Prepare same-covered-day article inputs, capture actual originals, qualify/import materials and bind the candidate through supported interfaces. Reuse valid captures. Discovery/coverage never certifies article admission. Stop at the existing supply floor if unavailable.',
        'author': 'Directly author the complete Chinese candidate, full version-3 Fable and consistent worked example from qualified sources. Use daily_authoring probe/save/patch and source_preparation binding. Do not stage, review, seal, finalize or publish.',
        'repair': 'Repair only the cited current staging failure through the controlled digest-bound revision interfaces. Preserve original stages and invalidate changed reviews. Never modify validators or invent a passing review.',
        'news_review': 'Perform a fresh independent factual/source review of every selected item and each facts/judgment/relevance claim. Read actual source evidence. Use existing blank review templates or preserve existing reviews; set review_method independent only after actually reviewing. Do not edit content or other review roles.',
        'story_review': 'Perform a fresh independent Fable review following the three protocol-3 rounds and required isolated story-only procedure. Preserve the literal trace, counterfactual, source mapping and example alignment. Do not claim story-only blindness after seeing technical answers; stop if the permitted runtime cannot supply isolation. Do not edit content or display judgments.',
        'display_review': 'Use a permitted real browser on the current exact HTML/approved preview. Actually test desktop, narrow screen, formulas, links, printing and required reading behavior; bind evidence to its HTML hash. Feedback-only checks may be N/A only when disabled. Complete only display evidence in the existing review. A program/HTTP check cannot be display approval.'}
    return ('PaperTrace closed-loop job. Read AGENTS.md, .agents/AGENTS.md, .agents/PROJECT_CONTEXT.md, .agents/README.md, '
            'the ai-quantum-news-briefing SKILL and referenced current runbook before work.\n'
            + json.dumps(packet, ensure_ascii=False) + '\n' + duties[packet['role']] + '\n'
            'Use the fixed release date and preceding Shanghai natural day throughout. Never expand the date window, '
            'lower academic >=6/social >=6/new-important >=4 or stricter configured floors, reset budgets, bypass '
            '403/401/Retry-After or tool denials, modify scheduling/access/credentials/publishing settings, send messages, '
            'upload or finalize. Evidence and original response bytes are separate from observations and judgments. '
            'Do not run another closed-loop controller or ordinary daily work in parallel. Do not read agent task/output '
            'directories of other roles. Review templates are unreviewed and never auto-PASS. '
            'If blocked, return a precise snake_case code and preserve all data. '+
            ('Review mode is read-only. Return your review proposal encoded in review_json, not a file write. '
             'For story_review preserve the supplied blind_round verbatim as story-completeness and leave actual display pending with typed evidence. '
             'The review_template intentionally omits that accepted first round to avoid duplicate input. '
             'For display_review change only actual-display evidence/judgment in the existing story review after actual checks. '
             if packet['role'] in REVIEW_ROLES else '')+
            'A completed response is only a worker acknowledgment; existing validators retain release authority. '
            'Return only the schema JSON with the supplied job/date/input identity.')


def execute(backend, day, policy, *, policy_sha256, clock=time.time):
    """One bounded invocation; a host wakeup must consume returned retry times."""
    bounds = policy_bounds(policy, day)
    base = {**execution_window(day), 'closed_loop_version': 1, 'publication_approved': False,
            'scheduling_status': 'not_scheduled_by_code'}
    if retired(day) or not bounds:
        return {**base, 'status': 'not_scheduled', 'code': 'retired_or_policy_disabled'}
    root = backend.root
    try:
        with release_lock(root / '_automation' / ('attempt-' + day), timeout=0):
            state = _load(root, day)
            if state.get('policy_sha256') not in {None, policy_sha256}:
                raise ValueError('closed_loop_policy_changed_preserve_journal')
            state['policy_sha256'] = policy_sha256
            now = clock()
            if now < bounds[0]:
                return {**base, 'status': 'waiting', 'code': 'before_0100', 'next_wakeup_at': bounds[0]}
            identity = begin(root, day, now=now, policy=policy)
            try:
                return _owned(backend, day, policy, base, state, bounds, clock)
            finally:
                finish(root, day, identity, {'phase': state.get('phase'), 'run_outcome': state.get('status'),
                       'terminal_blocker': state.get('outcome'),
                       'recovery': {'earliest_retry_at': state.get('next_wakeup_at')}}, now=clock())
    except TimeoutError:
        return {**base, 'status': 'waiting', 'code': 'edition_owner_active'}


def drive(backend,day,policy,*,policy_sha256,clock=time.time,monotonic=time.monotonic,sleep=time.sleep):
    """Consume wakeups in this host process only. Never create a scheduler.

    Zero is the safe default. At the approved host bound return the exact pending
    wakeup; another normal invocation resumes the same durable ledger and date.
    """
    policy_bounds(policy,day)
    until=monotonic()+policy.get('driver_wait_seconds',0)
    while True:
        result=execute(backend,day,policy,policy_sha256=policy_sha256,clock=clock)
        due=result.get('next_wakeup_at')
        if result['status']!='waiting' or not isinstance(due,(int,float)):return result
        while clock()<due:
            remaining=until-monotonic()
            if remaining<=0:return result
            sleep(min(30,remaining,due-clock()))
        if monotonic()>=until:return result


def _owned(backend, day, policy, base, state, bounds, clock):
    root = backend.root
    # A prior process may have died between reserving and acknowledging an
    # action. Keep consumption; re-inspect before doing anything else.
    for action in state['actions']:
        if action['status'] == 'reserved':
            action.update(status='interrupted', code='process_interrupted_outcome_uncertain')
    state.pop('remote_probe', None)  # no stale online proof across invocations

    def stop(status, code, *, retry_at=None, blocker=None):
        state.update(status=status, updated_at=clock(), next_wakeup_at=retry_at,
                     outcome={'status': status, 'code': code, 'blocker': blocker})
        _save(root, day, state, outcome=state['outcome'] if status in TERMINAL else None)
        return {**base, 'status': status, 'code': code, 'phase': state.get('phase'),
                'next_wakeup_at': retry_at, 'notification_status': 'pending_send' if status in TERMINAL else 'not_required',
                'actions_used': len(state['actions']), 'blocker': blocker,
                'scoped_blockers':state.get('scoped_blockers',{})}

    if state.get('status') in TERMINAL:
        # Explicit policy changes/recovery need a new reviewed migration, never
        # deleting a journal or silently refunding interrupted reservations.
        observed=backend.snapshot(day)
        if observed['phase']=='workflow_complete':
            state.update(phase=observed['phase'],last_input=observed['identity'])
            return stop('completed','complete')
        if state['status']=='completed':return stop('blocked','completion_no_longer_verified')
        # Browser exhaustion is scoped. New independently due source work can
        # drain later, without reopening the exhausted browser budget.
        resume_action=choose(observed,state,policy,now=clock())
        independent_wait=(resume_action=='source_wait' and any(r.get('kind')!='discovery'
            and r.get('state') in {'running','retry_wait'} for r in observed.get('source',{}).get('missing_tasks',[])))
        if not ((state['outcome'].get('code')=='browser_recovery_exhausted'
                or state['outcome'].get('code')=='agent_budget_exhausted' and (state['outcome'].get('blocker') or {}).get('scope')=='browser_discovery')
                and (resume_action=='work' or independent_wait)):
            return stop(state['status'], state['outcome']['code'], blocker=state['outcome'].get('blocker'))
    if hasattr(backend, 'integrity'):
        integrity = backend.integrity()
        if state.get('code_sha256') not in {None, integrity}:
            return stop('blocked', 'execution_code_changed_preserve_journal')
        state['code_sha256'] = integrity
    # A timeout/wait is never stronger than current verified publication truth.
    if state.get('next_wakeup_at') and clock()>=bounds[1]:
        observed=backend.snapshot(day)
        if observed['phase']=='workflow_complete':
            state.update(phase=observed['phase'],last_input=observed['identity'])
            return stop('completed','complete')
    if state.get('next_wakeup_at') and clock() < state['next_wakeup_at']:
        if clock() >= bounds[1]:
            return stop('expired', 'same_day_deadline_reached')
        return stop('waiting', 'retry_not_due', retry_at=state['next_wakeup_at'])
    for _ in range(policy['max_steps_per_invocation']):
        snapshot = backend.snapshot(day)
        state.update(phase=snapshot['phase'], last_input=snapshot['identity'], updated_at=clock())
        action = choose(snapshot, state, policy,now=clock())
        if action in {'complete', 'retired'}:
            return stop('completed' if action == 'complete' else 'not_scheduled', action)
        if clock() >= bounds[1]:
            return stop('expired', 'same_day_deadline_reached')
        if action=='browser_wait':
            due=browser_failures(state)[-1]['finished_at']+policy.get('browser_recovery_delay_seconds',300)
            return stop('waiting' if due<bounds[1] else 'expired','browser_runtime_retry_after',retry_at=due if due<bounds[1] else None)
        if action=='source_wait':
            times=[r['retry_at'] for r in snapshot.get('source',{}).get('missing_tasks',[])
                   if r.get('state') in {'running','retry_wait'} and type(r.get('retry_at')) in (int,float) and r['retry_at']>clock()]
            retry=min(times) if times else snapshot.get('retry_at')
            if type(retry) not in (int,float) or not clock()<retry<bounds[1]:
                return stop('blocked','source_retry_timing_unavailable')
            return stop('waiting','source_retry_after',retry_at=retry)
        if action=='browser_recovery_exhausted':
            return stop('blocked',action,blocker={'scope':'browser_discovery','independent_due_work_drained':True})
        if action=='browser_agent_budget_exhausted':
            return stop('budget_exhausted','agent_budget_exhausted',blocker={'scope':'browser_discovery','independent_due_work_drained':True})
        if action in {'block', 'shortage', 'remote_unavailable', 'publish_disabled', 'review_not_independent'}:
            return stop('blocked', action, blocker=snapshot.get('blocker'))
        retry = snapshot.get('retry_at')
        if retry and retry > clock():
            return stop('waiting' if retry < bounds[1] else 'expired', 'source_retry_after',
                        retry_at=retry if retry < bounds[1] else None)
        if len(state['actions']) >= policy['max_actions']:
            return stop('budget_exhausted', 'action_budget_exhausted')
        agent_slots=2 if action=='story_review' else int(action in AGENT_ROLES)
        used=sum(a.get('agent_slots',2 if a['action']=='story_review' else int(a['action'] in AGENT_ROLES)) for a in state['actions'])
        if used+agent_slots>policy['max_agent_invocations']:
            return stop('budget_exhausted', 'agent_budget_exhausted')
        attempt = {'id': uuid.uuid4().hex, 'action': action, 'input': snapshot['identity'],
                   'status': 'reserved', 'agent_slots':agent_slots,'started_at': clock()}
        state['actions'].append(attempt)
        _save(root, day, state)  # reserve before side effects; interruption consumes
        try:
            result = backend.perform(action, day, snapshot, policy,
                                     min(policy['agent_timeout_seconds'], max(1, bounds[1] - clock())))
        except (OSError, ValueError, TypeError, TimeoutError) as exc:
            attempt.update(status='failed', code=exc.__class__.__name__)
            cause=str(exc) if isinstance(exc,ValueError) and re.fullmatch('[a-z0-9_]{1,100}',str(exc)) else None
            return stop('blocked', 'action_failed_' + exc.__class__.__name__,
                        blocker={'operation': action, 'type': exc.__class__.__name__,
                                 'cause_code':cause,'errno': getattr(exc, 'errno', None), 'winerror': getattr(exc, 'winerror', None)})
        if result.get('status') not in {'completed', 'blocked', 'retry_wait'}:
            return stop('blocked', 'action_result_invalid')
        attempt.update(status=result['status'], finished_at=clock(), code=result.get('code'),
                       receipt_sha256=result.get('receipt_sha256'))
        if result['status'] == 'blocked':
            if action=='discovery' and result.get('code') in BROWSER_RECOVERABLE:
                attempt['status']='retry_wait'
                state.setdefault('scoped_blockers',{})['browser_discovery']={
                    'code':result['code'],'failures':len(browser_failures(state)),
                    'next_retry_at':clock()+policy.get('browser_recovery_delay_seconds',300),
                    'authority':'worker_reported_environment_failure_not_a_source_verdict'}
                _save(root,day,state)
                continue # Re-inspect; independently due deterministic peers may proceed.
            return stop('blocked', result.get('code') or 'action_blocked', blocker=result.get('blocker'))
        if result['status'] == 'retry_wait':
            retry = result.get('retry_at')
            if not isinstance(retry, (int, float)) or not clock() < retry < bounds[1]:
                return stop('expired', 'retry_outside_same_day_window')
            return stop('waiting', result.get('code') or 'retry_wait', retry_at=retry)
        if hasattr(backend, 'integrity') and backend.integrity() != state['code_sha256']:
            return stop('blocked', 'worker_changed_execution_code')
        after = backend.snapshot(day)  # success text/exit 0 alone never advances
        if action in REVIEW_ROLES and after['identity'] != snapshot['identity']:
            return stop('blocked', 'review_worker_changed_content')
        if action == 'online':
            state['remote_probe'] = {'input': snapshot['identity'], 'status': result.get('remote_status', 'unknown')}
        if action == 'publish':
            state.pop('remote_probe', None)
        progressed = after['identity'] != snapshot['identity'] or after['phase'] != snapshot['phase'] or action in REVIEW_ROLES + ('online','review_template')
        state['no_progress'] = 0 if progressed else state['no_progress'] + 1
        _save(root, day, state)
        if state['no_progress'] >= policy['no_progress_limit']:
            return stop('blocked', 'no_verified_progress')
    retry = clock() + 60
    return stop('waiting' if retry < bounds[1] else 'expired', 'invocation_step_bound',
                retry_at=retry if retry < bounds[1] else None)
