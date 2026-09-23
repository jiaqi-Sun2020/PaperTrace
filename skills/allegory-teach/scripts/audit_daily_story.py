"""Reproduce structural checks and validate separately authored semantic evidence."""
import argparse
import html
import json
import re
import sys
from pathlib import Path

from review_evidence import validate_review

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'skills/ai-quantum-news-briefing/scripts'))
from daily_pipeline import verify_artifacts, sha256_file, atomic_json


def audit(run_dir, review_path):
    result = verify_artifacts(run_dir, strict=True)
    manifests = list(run_dir.glob('daily_pipeline_manifest_*.json'))
    if not manifests:
        return {'status': 'fail', 'structural': result, 'semantic_review': {'status': 'unreviewed'}}
    manifest = json.loads(manifests[0].read_text(encoding='utf-8-sig'))
    config_path = run_dir / manifest['artifacts']['delta_config']
    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    story = config['opening_story']
    page = (run_dir / manifest['artifacts']['html']).read_text(encoding='utf-8-sig')
    narrative = re.search(r'<div class="story-narrative">(.*?)</div>', page, re.S)
    failures = list(result.get('failures', []))
    expected = ''.join('<p>'+html.escape(p, quote=True)+'</p>' for p in story['paragraphs'])
    if not narrative or narrative.group(1) != expected:
        failures.append('complete ordered story missing from visible narrative')
    if narrative and page.find('<details class="story-worked-example"') < narrative.end():
        failures.append('example folds before the complete narrative ends')
    review = json.loads(review_path.read_text(encoding='utf-8-sig')) if review_path.exists() else {}
    semantic_failures = validate_review(story, review)
    return {'status': 'fail' if failures or semantic_failures else 'pass',
            'release': manifest['date'], 'scope': 'opening-story-reissue-fable',
            'structural': {'status': 'fail' if failures else 'pass', 'failures': failures,
                           'paragraphs': len(story['paragraphs']),
                           'config_sha256': sha256_file(config_path)},
            'semantic_review': {'status': 'unreviewed-or-fail' if semantic_failures else 'reviewed',
                                'failures': semantic_failures, 'evidence': review,
                                'caution': 'Code verifies provenance and freshness, not semantic truth.'}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.run_dir, args.review)
    atomic_json(args.output, report)
    print(json.dumps({'status': report['status'], 'report': str(args.output)}, ensure_ascii=False))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
