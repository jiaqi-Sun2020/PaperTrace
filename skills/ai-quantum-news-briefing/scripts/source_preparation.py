"""Acquisition/authoring handoff. Existing daily lifecycle remains the release owner."""
from __future__ import annotations
import argparse
import copy
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from source_pool import SourcePool, PoolConflict, checked_path, fingerprint
from source_worker import plan_sources, source_snapshot, run_ready, claim_discovery, submit_discovery, code_binding, enqueue_captures
from material_admission import publication_day
from daily_execution_policy import retired,retired_state

POOL_PATH = '_sources/pool.sqlite'
SOURCE_FIELDS = ('id', 'source_url', 'source_title', 'source_excerpt', 'published_at', 'source_class', 'evidence_fingerprint', 'ai_source_provenance')


def binding_scope(config, release_date, references, source_tasks=None):
    bare = {key: value for key, value in config.items() if key != 'source_pool_binding'}
    return {'version': 1, 'release_date': release_date, 'candidate_content_sha256': fingerprint(bare),
            'code_sha256': fingerprint(code_binding()), 'references': references,
            'source_tasks': source_tasks or []}


def source_evidence_references(pool, config, release_date):
    from academic_sources import family_gate, row_is_healthy
    from daily_coverage_evidence import validate_social_search
    plan = plan_sources(pool, release_date, register=False)
    rows = config.get('coverage_evidence')
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get('date') != plan['coverage_date']:
        raise PoolConflict('pool_daily_coverage_binding_missing')
    record = rows[0]
    academic, social = record.get('academic_search') or {}, record.get('social_search') or {}
    if family_gate(academic.get('rows'), coverage_window=plan['coverage_date'], require_query=True)['status'] != 'pass':
        raise PoolConflict('pool_required_academic_queries_missing')
    if validate_social_search(social, plan['coverage_date']):
        raise PoolConflict('pool_required_social_coverage_missing')
    if release_date>='2026-10-16':
        from ai_social_sources import validate_pool
        if validate_pool(social.get('ai_fixed_pool'),plan['coverage_date']):
            raise PoolConflict('pool_ai_fixed_observations_missing')
    expected = {}
    for key in plan['tasks']:
        try:
            task = pool.get(key)
        except PoolConflict:
            continue
        expected[(task['spec']['kind'], task['spec']['source_id'])] = task
    refs = []
    def bind(kind, source_id, evidence):
        task = expected.get((kind, source_id))
        if not task or task['state'] != 'succeeded' or task['result'] != evidence:
            raise PoolConflict('pool_coverage_not_committed:' + source_id)
        refs.append({'task_id': task['task_id'], 'result_sha256': task['result_sha']})
    for row in academic.get('rows', []):
        if row_is_healthy(row, plan['coverage_date']):
            bind('academic', row['source_id'], row)
    hot = expected.get(('aihot', 'ai_hot'))
    if not hot or hot['state'] != 'succeeded' or hot['result'].get('ai_hot_window') != social.get('ai_hot_window'):
        raise PoolConflict('pool_aihot_coverage_not_committed')
    refs.append({'task_id': hot['task_id'], 'result_sha256': hot['result_sha']})
    classes = {r['source_class']: r for r in social.get('source_class_evidence', [])}
    for source_class in ('reputable_media', 'official_company_social', 'executive_social'):
        bind('discovery', source_class, classes.get(source_class))
    if release_date>='2026-10-16':
        for observation in social['ai_fixed_pool']['observations']:
            bind('fixed_source',observation['source']['id'],observation)
    return refs


def bind_candidate(pool, config, release_date, references):
    if pool.news_root is None:
        raise PoolConflict('release_pool_requires_news_sources_location')
    items = {item['id']: item for section in config['sections'] for item in section['items']}
    if not isinstance(references, dict) or set(items) != set(references):
        raise PoolConflict('candidate_material_set_differs')
    for item_id, ref in references.items():
        material = pool.material(ref['material_id'], ref['revision'])
        if not material['current'] or any(items[item_id].get(k) != material['item'].get(k) for k in SOURCE_FIELDS):
            raise PoolConflict('candidate_material_source_changed')
    scope = binding_scope(config, release_date, references, source_evidence_references(pool, config, release_date))
    key = pool.bind_preparation(scope, list(references.values()))
    return {'version': 1, 'pool_relative_path': POOL_PATH, 'binding_id': key, 'scope': scope}


def bind_selected_materials(news_root, binding, selected_config):
    """A frozen edition depends on selected material, not unrelated pool updates."""
    scope = copy.deepcopy(binding['scope'])
    ids = [item.get('source_candidate_id') or item['id'] for section in selected_config['sections'] for item in section['items']]
    if not ids or not set(ids) <= set(scope['references']):
        raise PoolConflict('selected_material_dependency_missing')
    scope['references'] = {key: scope['references'][key] for key in ids}
    with SourcePool(Path(news_root)/POOL_PATH) as pool:
        key = pool.bind_preparation(scope, list(scope['references'].values()))
    return {'version': 1, 'pool_relative_path': POOL_PATH, 'binding_id': key, 'scope': scope}


def check_pool_binding(news_root, binding, *, config=None, release_date=None, historical=False):
    """Read-only dependency check, usable at every existing release entry point.

    A completed historical receipt retains its reviewed revision, while an
    unpublished run must still point to current material revisions.
    """
    if (not isinstance(binding, dict) or set(binding) != {'version', 'pool_relative_path', 'binding_id', 'scope'}
            or type(binding.get('version')) is not int or binding.get('version') != 1 or binding.get('pool_relative_path') != POOL_PATH):
        return ['pool_binding_contract_invalid']
    scope = binding['scope']
    if not isinstance(scope, dict) or (release_date and scope.get('release_date') != release_date):
        return ['pool_release_date_changed']
    if scope.get('code_sha256') != fingerprint(code_binding()) and not historical:
        return ['pool_preparation_code_changed']
    if config is not None and scope != binding_scope(config, release_date, scope.get('references'), scope.get('source_tasks')):
        return ['pool_candidate_content_changed']
    try:
        path = checked_path(Path(news_root)/POOL_PATH)
        db = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            if db.execute('PRAGMA user_version').fetchone()[0] != 1:
                return ['pool_schema_incompatible']
            row = db.execute('SELECT scope,dependencies FROM preparation_bindings WHERE binding_id=?', (binding['binding_id'],)).fetchone()
            if not row or json.loads(row['scope']) != scope:
                return ['pool_preparation_binding_missing']
            refs = json.loads(row['dependencies'])
            if fingerprint({'scope': scope, 'dependencies': refs}) != binding['binding_id']:
                return ['pool_preparation_binding_corrupt']
            if {tuple(sorted(v.items())) for v in scope.get('references', {}).values()} != {tuple(sorted(v.items())) for v in refs}:
                return ['pool_material_references_changed']
            failures = []
            if not isinstance(scope.get('source_tasks'), list) or len(scope['source_tasks']) < 6:
                return ['pool_source_dependencies_missing']
            for ref in scope['source_tasks']:
                source = db.execute('SELECT state,result,result_sha FROM tasks WHERE task_id=?', (ref['task_id'],)).fetchone()
                if (not source or source['state'] != 'succeeded' or source['result_sha'] != ref['result_sha256']
                        or fingerprint(json.loads(source['result'])) != source['result_sha']):
                    failures.append('pool_source_result_changed')
            for ref in refs:
                material = db.execute('SELECT current_revision FROM materials WHERE material_id=?', (ref['material_id'],)).fetchone()
                saved = db.execute('SELECT payload FROM material_revisions WHERE material_id=? AND revision=?',
                                   (ref['material_id'], ref['revision'])).fetchone()
                if not saved or fingerprint(json.loads(saved[0])) != ref['revision']:
                    failures.append('pool_material_revision_missing')
                if not material or not historical and material[0] != ref['revision']:
                    failures.append('pool_material_revision_changed')
            return failures
        finally:
            db.close()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error):
        return ['pool_dependency_unavailable']


def packet(pool, plan):
    from daily_delivery_policy import policy_snapshot
    from material_admission import admit_material
    from paper_identity import doi_for, paper_kind
    result = source_snapshot(pool, plan)
    refs, materials, excluded = [], [], []
    for row in pool.db.execute('SELECT material_id FROM materials ORDER BY rowid'):
        material = pool.material(row[0])
        if admit_material(material['source_id'], material['item'], material['capture']):
            excluded.append({'material_id': row[0], 'reason': 'current_admission_requires_recheck'})
            continue
        if publication_day(material['item']['published_at']).isoformat() != plan['coverage_date']:
            excluded.append({'material_id': row[0], 'reason': 'outside_requested_day'})
            continue
        refs.append({key: material[key] for key in ('material_id', 'revision')})
        materials.append(material)
    counts = {kind: len({('doi:'+doi_for(m['item']) if paper_kind({**m['item'], 'source_capture':m['capture']}) and doi_for(m['item'])
                         else 'url:'+m['item']['source_url']) for m in materials if m['item']['material_kind'] == kind})
              for kind in ('academic', 'social')}
    emitted = [m for kind in ('academic', 'social') for m in
               [v for v in materials if v['item']['material_kind'] == kind][:100]]
    policy = policy_snapshot()['policy']
    from ai_social_sources import discovery_packet
    result['ai_candidate_discovery']=discovery_packet(result)
    result.update(materials=emitted, excluded_materials=excluded, authoring_counts=counts,
                  material_output={'total':len(materials),'emitted':len(emitted),'truncated':len(materials)-len(emitted),
                                   'full_pool':str(pool.path),'truncated_is_not_excluded':True},
                  quantity_gaps={kind: max(0, policy[kind]['minimum_items']-counts[kind]) for kind in counts},
                  preparation_binding=pool.bind_preparation({'release_date': plan['release_date'], 'plan': fingerprint(plan)}, refs) if refs else None,
                  next_actions=['author_available_original_evidence', 'complete_missing_coverage',
                                'rank_authored_candidates_with_existing_policy', 'perform_actual_news_fable_and_display_reviews'],
                  release_readiness='not_evaluated', publication_approved=False)
    return result


def read_input(path):
    path = checked_path(path)
    if path.stat().st_size > 32_000_000:
        raise PoolConflict('public_input_too_large')
    return json.loads(path.read_text(encoding='utf-8'))


def check_run_pool_binding(run_dir, manifest, config):
    binding = manifest.get('source_pool_binding')
    if binding is None and config.get('source_pool_binding') is None:
        return []
    if (type(manifest.get('source_preparation_version')) is not int or manifest.get('source_preparation_version') != 1
            or binding != config.get('source_pool_binding')):
        return ['pool_manifest_binding_differs']
    run_dir = Path(run_dir).resolve()
    news_root = run_dir.parents[2] if run_dir.parent.name in ('.staging', '.staging-preparation') else run_dir.parent
    historical = False
    receipt = news_root/'_publish'/('oss_publish_receipt_'+manifest['date']+'.json')
    if manifest.get('status') == 'complete' and receipt.is_file():
        try:
            published = json.loads(receipt.read_text(encoding='utf-8'))
            historical = bool(published.get('status') == 'published' and published.get('date') == manifest['date']
                              and published.get('html_sha256') == manifest['artifact_sha256']['html'])
        except (OSError, ValueError, KeyError):
            return ['pool_release_receipt_invalid']
    return check_pool_binding(news_root, binding, release_date=manifest['date'], historical=historical)


def orchestrate_sources(release_date, pool_dir, *, action='plan', max_tasks=4, domain='all'):
    if domain not in ('all','ai-social'): raise PoolConflict('source_domain_invalid')
    if retired(release_date):
        return retired_state(release_date)
    path = Path(pool_dir)/'pool.sqlite'
    if action == 'status' and not path.exists():
        return {'source_preparation_version': 1, 'status': 'not_initialized', 'publication_approved': False}
    with SourcePool(path, read_only=action == 'status') as pool:
        plan = plan_sources(pool, release_date, register=action != 'status')
        if action == 'work':
            selected=None
            if domain=='ai-social':
                selected={task['task_id'] for task in pool.tasks(coverage_date=plan['coverage_date']) if task['spec']['kind'] in ('aihot','fixed_source') or task['spec']['kind']=='capture' and task['spec']['inputs'].get('item',{}).get('ai_source_provenance')}
            worked = run_ready(pool, max_tasks=max_tasks, coverage_date=plan['coverage_date'],task_ids=selected)
            return {'plan': plan, 'work': worked, 'source_preparation': source_snapshot(pool, plan)}
        if action == 'packet':
            return packet(pool, plan)
        return {'plan': plan, 'source_preparation': source_snapshot(pool, plan),
                'pending_discovery': [{'task_id': task['task_id'], 'navigation': task['spec']['inputs']['navigation']}
                                      for task in pool.tasks(coverage_date=plan['coverage_date']) if task['task_id'] in plan['tasks']
                                      and task['spec']['kind'] == 'discovery'
                                      and task['state'] in ('pending', 'retry_wait')]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('plan', 'status', 'work', 'packet', 'claim-discovery', 'submit-discovery',
                                          'record-denial', 'import-materials', 'enqueue-captures', 'bind-candidate', 'backup'))
    parser.add_argument('--date', required=True)
    parser.add_argument('--pool-dir', type=Path, required=True)
    parser.add_argument('--task-id')
    parser.add_argument('--lease')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--references', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--news-root', type=Path)
    parser.add_argument('--max-tasks', type=int, default=4)
    parser.add_argument('--domain',choices=('all','ai-social'),default='all')
    args = parser.parse_args(argv)
    try:
        if date.fromisoformat(args.date).isoformat() != args.date:
            raise PoolConflict('release_date_invalid')
        if retired(args.date) and args.action!='backup':
            print(json.dumps(retired_state(args.date),ensure_ascii=False))
            return 0
        if args.action in ('plan', 'status', 'work', 'packet'):
            result = orchestrate_sources(args.date, args.pool_dir, action=args.action, max_tasks=args.max_tasks,domain=args.domain)
        else:
            with SourcePool(args.pool_dir/'pool.sqlite') as pool:
                if args.action in ('claim-discovery','submit-discovery','record-denial'):
                    task=pool.get(args.task_id)
                    if task['spec']['coverage_date']!=(date.fromisoformat(args.date)-timedelta(days=1)).isoformat():
                        raise PoolConflict('task_release_date_mismatch')
                if args.action == 'claim-discovery':
                    result = claim_discovery(pool, args.task_id)
                elif args.action == 'submit-discovery':
                    result = submit_discovery(pool, args.task_id, args.lease, read_input(args.input))
                elif args.action == 'record-denial':
                    result = pool.fail(args.task_id, args.lease, {'code': 'policy_rejected', 'retryable': False})
                elif args.action == 'import-materials':
                    rows = read_input(args.input)
                    if not isinstance(rows, list):
                        raise PoolConflict('material_input_list_required')
                    result = {'admitted': [], 'invalid': [], 'publication_approved': False}
                    for position, row in enumerate(rows):
                        try:
                            result['admitted'].append(pool.put_material(row['source_id'], row['item'], row['capture']))
                        except (ValueError, KeyError, TypeError) as exc:
                            result['invalid'].append({'position': position, 'code': str(exc) if isinstance(exc, PoolConflict) else 'material_shape_invalid'})
                elif args.action == 'enqueue-captures':
                    if args.news_root is None:
                        raise PoolConflict('explicit_news_root_required')
                    result = {'task_ids': enqueue_captures(pool, args.input, args.news_root,
                              (date.fromisoformat(args.date)-timedelta(days=1)).isoformat()),
                              'publication_approved': False}
                elif args.action == 'bind-candidate':
                    result = bind_candidate(pool, read_input(args.input), args.date, read_input(args.references))
                else:
                    pool.backup(args.output)
                    result = {'status': 'sqlite_consistent_backup_complete'}
        print(json.dumps(result, ensure_ascii=False))
        if args.action == 'work' and any(row['state'] != 'succeeded' for row in result.get('work', {}).get('processed', [])):
            return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(json.dumps({'status': 'source_preparation_failed', 'code': str(exc) if isinstance(exc, PoolConflict) else type(exc).__name__,
                          'publication_approved': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
