"""One ordinary Codex task drives explicit deterministic steps. Never runs a model."""
from __future__ import annotations
import argparse
import base64
import json
from pathlib import Path

import daily_authoring as author
import daily_pipeline as pipeline
import daily_revisions as revisions
from daily_execution_policy import execution_window, retired
from taskbox_contract import contract, validate_mode
from daily_runtime import runtime_scope, RuntimeConfigurationError


def selected_stage(day, run_dir=None):
    execution_window(day)
    root = Path(pipeline.NEWS_ROOT).resolve()
    stages = revisions.active_stages(root, day)
    if len(stages) != 1:
        raise ValueError('taskbox_requires_one_active_stage')
    stage = stages[0].resolve()
    if run_dir is not None and Path(run_dir).resolve() != stage:
        raise ValueError('taskbox_stage_identity_changed')
    manifest = pipeline.load_json(stage / ('daily_pipeline_manifest_' + day + '.json'))
    if 'taskbox_contract' not in manifest:
        raise ValueError('taskbox_contract_required')
    config = pipeline.load_json(stage / manifest['artifacts']['delta_config'])
    if validate_mode(manifest, config):
        raise ValueError('taskbox_contract_binding_invalid')
    return stage, manifest, config


def save_candidate(day, expected, payload, deployment):
    value = dict(payload)
    value['taskbox_contract'] = contract(day, deployment)
    author.validate(value, 'candidate', None)
    binding = value.get('source_pool_binding')
    if binding is not None:
        from source_pool import SourcePool
        from source_preparation import bind_candidate
        with SourcePool(Path(pipeline.NEWS_ROOT) / '_sources/pool.sqlite') as pool:
            value['source_pool_binding'] = bind_candidate(pool, value, day, binding['scope']['references'])
    return author.save(Path(pipeline.NEWS_ROOT), day, 'candidate', expected, value)


def save_review(day, kind, expected, payload, run_dir=None):
    stage, manifest, config = selected_stage(day, run_dir)
    if payload.get('review_method') != 'self':
        raise ValueError('taskbox_requires_honest_self_review')
    return author.save(Path(pipeline.NEWS_ROOT), day, kind, expected, payload, run_id=stage.name)


def review_packet(day, run_dir=None):
    stage, manifest, config = selected_stage(day, run_dir)
    captures = pipeline.load_json(stage / manifest['artifacts']['source_captures'])['items']
    return {'status': 'action_required', 'execution': 'ordinary_codex_task', 'review_method': 'self',
        'context_isolation': 'none', 'date': day, 'run_dir': str(stage),
        'content_digest': pipeline.content_digest(manifest), 'html_sha256': manifest['artifact_sha256']['html'],
        'selected_source_evidence': [{'item': item, 'capture': captures[str(item['source_capture']['item_id'])]}
                                     for section in config['sections'] for item in section['items']],
        'opening_story': config['opening_story'],
        'instruction': 'Current task: check every facts/judgment/relevance claim against captured primary evidence; leave unsupported claims failed. Inspect real display. Author self review JSON; never infer passes from this packet.',
        'model_dispatch': 'none', 'content_approved': False}


def publish(day, config_path, expected_deployment, *, allow_network=False):
    if allow_network is not True:
        return {'status': 'blocked', 'code': 'taskbox_explicit_network_scope_required'}
    from publish_daily_to_oss import load_config, deployment_id, publish as existing_publish, inspect_public_release
    config_path = Path(config_path).resolve()
    config = load_config(config_path)
    if deployment_id(config) != expected_deployment:
        return {'status': 'blocked', 'code': 'taskbox_destination_changed'}
    root = Path(pipeline.NEWS_ROOT).resolve()
    if config_path.parent / 'news' != root:
        raise ValueError('taskbox_publish_root_changed')
    final = root / day
    manifest = pipeline.load_json(final / ('daily_pipeline_manifest_' + day + '.json'))
    if (manifest.get('taskbox_contract') or {}).get('deployment_id') != expected_deployment:
        raise ValueError('taskbox_release_destination_changed')
    base = pipeline.verify_artifacts(final, strict=True)
    if base['status'] != 'pass':
        return {'status': 'blocked', 'code': 'taskbox_strict_gate_failed', 'failures': base['failures']}
    result = existing_publish(final, config_path)
    if result.get('status') not in ('published', 'no_change'):
        return result
    remote = inspect_public_release(config, day, manifest['artifact_sha256']['html'])
    if remote['status'] != 'verified':
        return {'status': 'pending', 'code': 'taskbox_remote_not_verified', 'publisher': result, 'verification': remote}
    return {'status': 'published_verified', 'publisher': result, 'verification': remote}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('next','collect','source-status','source-packet','capture','candidate','stage','templates','packet','news-review','story-review','check','seal','finalize','publish'))
    parser.add_argument('--date', required=True)
    parser.add_argument('--run-dir')
    parser.add_argument('--payload-base64')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--expected-deployment-id')
    parser.add_argument('--allow-network', action='store_true')
    parser.add_argument('--patch', action='store_true', help='Bounded JSON patch via the existing authoring owner')
    parser.add_argument('--config', type=Path, default=Path(pipeline.NEWS_ROOT).parent / 'news_publish.local.json')
    parser.add_argument('--runtime-config', type=Path, help='Non-secret process-scoped runtime settings, also supported by the direct Python entry')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        with runtime_scope(args.runtime_config):
            return execute(args)
    except RuntimeConfigurationError:
        print(json.dumps({'status': 'blocked', 'code': 'runtime_configuration_unavailable',
                          'content_approved': False}))
        return 2


def execute(args):
    try:
        execution_window(args.date)
        if retired(args.date):
            raise ValueError('taskbox_historical_date_requires_separate_correction_scope')
        if args.action == 'next':
            import orchestrate_daily as orchestrator
            result = {'status': 'action_required', 'date': args.date, 'edition': orchestrator.inspect(args.date),
                      'continue_in_current_task': True, 'model_dispatch': 'none',
                      'instruction': 'Follow taskbox-execution.md in this same task through collection, authored content, source/display self-checks, strict local finalize and authorized existing-site delivery. Pause on a real permission/evidence blocker.'}
        elif args.action == 'collect':
            if not args.allow_network:
                raise ValueError('taskbox_explicit_network_scope_required')
            import orchestrate_daily as orchestrator
            code = orchestrator.main(['daily', '--date', args.date, '--action', 'plan', '--record'])
            if code == 0:
                code = orchestrator.main(['daily', '--date', args.date, '--action', 'work', '--record', '--max-tasks', '4'])
            return code
        elif args.action in ('source-status','source-packet'):
            import orchestrate_daily as orchestrator
            return orchestrator.main(['daily','--date',args.date,'--action',args.action.split('-')[1]])
        elif args.action == 'capture':
            if not args.allow_network:
                raise ValueError('taskbox_explicit_network_scope_required')
            from source_capture import capture_report
            result = capture_report(revisions.candidate_path(Path(pipeline.NEWS_ROOT), args.date),
                execution_window(args.date)['coverage_date'], news_root=Path(pipeline.NEWS_ROOT))
            if result['status'] != 'complete':
                print(json.dumps(result, ensure_ascii=True))
                return 2
        elif args.action in ('candidate','news-review','story-review'):
            if not args.payload_base64 or len(args.payload_base64) > author.MAX_PAYLOAD or not args.expected_sha256:
                raise ValueError('taskbox_bounded_payload_and_expected_sha_required')
            value = author.decode_json(base64.b64decode(args.payload_base64, validate=True))
            if args.patch:
                root = Path(pipeline.NEWS_ROOT)
                run_id = None if args.action == 'candidate' else selected_stage(args.date, args.run_dir)[0].name
                target = author.target_path(root, args.date, args.action, run_id)
                current = author.decode_json(target.read_bytes())
                value = author.patched(current, value, root, root / '_collection' / args.date)
            result = (save_candidate(args.date, args.expected_sha256, value, args.expected_deployment_id)
                      if args.action == 'candidate' else save_review(args.date, args.action, args.expected_sha256, value, args.run_dir))
        elif args.action == 'stage':
            path = revisions.candidate_path(Path(pipeline.NEWS_ROOT), args.date)
            value = pipeline.load_json(path)
            if 'taskbox_contract' not in value:
                raise ValueError('taskbox_contract_required')
            window = execution_window(args.date)
            values = ['run','--config',str(path),'--date',args.date,'--coverage-start',window['coverage_date']+'T00:00:00+08:00',
                      '--coverage-end',args.date+'T00:00:00+08:00']
            return pipeline.main(values)
        elif args.action == 'publish':
            result = publish(args.date, args.config, args.expected_deployment_id, allow_network=args.allow_network)
        else:
            stage, manifest, config = selected_stage(args.date, args.run_dir)
            if args.action == 'packet': result = review_packet(args.date, stage)
            elif args.action == 'check': result = pipeline.verify_artifacts(stage, strict=True)
            else:
                command = {'templates':'review-template','seal':'seal-review','finalize':'finalize'}[args.action]
                values = [command, '--run-dir', str(stage)]
                if args.action == 'finalize': values.extend(['--strict','--local-only'])
                return pipeline.main(values)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        return 2 if result.get('status') in ('blocked','pending','fail','disabled','failed') else 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status':'blocked','code':str(exc) if isinstance(exc, ValueError) else type(exc).__name__, 'content_approved':False}, ensure_ascii=True))
        return 2


if __name__ == '__main__': raise SystemExit(main())
