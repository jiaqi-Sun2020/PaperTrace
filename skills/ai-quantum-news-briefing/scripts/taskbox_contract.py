"""Explicit same-task self review; source evidence still controls every claim.

Validators prove binding/coverage, never scientific truth or an isolated reviewer.
"""
from datetime import datetime, timezone
import re

CONTEXT = {'mode': 'same_task_self', 'context_isolation': 'none', 'independent_review': False}


def valid_context(value):
    return (isinstance(value, dict) and value == CONTEXT
            and type(value.get('independent_review')) is bool)


def contract(day, deployment_id):
    if not re.fullmatch(r'[0-9a-f]{64}', str(deployment_id)):
        raise ValueError('taskbox_destination_identity_required')
    return {'version': 1, 'execution': 'ordinary_codex_task', 'date': day,
            'review_context': dict(CONTEXT), 'source_policy': 'selected_capture_crosscheck_v1',
            'deployment_id': deployment_id}


def validate_mode(manifest, config):
    mode = manifest.get('taskbox_contract')
    declared = config.get('taskbox_contract')
    if 'taskbox_contract' not in manifest and 'taskbox_contract' not in config:
        return []
    try:
        valid = (isinstance(mode, dict) and type(mode.get('version')) is int
                 and isinstance(declared, dict) and type(declared.get('version')) is int
                 and valid_context(mode.get('review_context'))
                 and valid_context(declared.get('review_context')) and mode == declared
                 and mode == contract(manifest['date'], mode.get('deployment_id')))
    except (ValueError, TypeError, KeyError):
        valid = False
    if not valid:
        return ['taskbox_contract_binding_invalid']
    versions = {'pipeline_version': 4, 'coverage_evidence_contract_version': 3,
                'required_story_review_protocol': 3, 'source_url_contract_version': 2}
    if any(type(manifest.get(key)) is not int or manifest[key] != expected
           for key, expected in versions.items()):
        return ['taskbox_publication_versions_required']
    if (type(config.get('source_url_contract_version')) is not int
            or config['source_url_contract_version'] != 2):
        return ['taskbox_source_url_version_required']
    return []


def validate_reviews(manifest, config, news, story, captures, *,
                     html_sha256, preview_display_pending=False):
    failures = validate_mode(manifest, config)
    if 'taskbox_contract' not in manifest and 'taskbox_contract' not in config:
        if 'taskbox_context' in news or 'taskbox_context' in story:
            failures.append('taskbox_contract_required_for_review_context')
        return failures
    if (type(news.get('version')) is not int or news['version'] != 1
            or type(story.get('review_protocol_version')) is not int
            or story['review_protocol_version'] != 3):
        failures.append('taskbox_review_versions_required')
    rows = story.get('rounds')
    display_rows = [row for row in rows if isinstance(row, dict)
                    and row.get('id') == 'cross-surface-and-display'] if isinstance(rows, list) else []
    if len(display_rows) != 1 or not isinstance(display_rows[0].get('display_review'), dict):
        failures.append('taskbox_current_html_display_required')
    else:
        display = display_rows[0]['display_review']
        if (not isinstance(html_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', html_sha256)
                or display.get('html_sha256') != html_sha256):
            failures.append('taskbox_display_html_binding_invalid')
        # The shared story validator checks all three actual display checks,
        # evidence types, completeness, verdicts and the narrow preview exemption.
        # Presence is mandatory here even though historical records allow absence.
        for check in display.get('checks', []) if isinstance(display.get('checks'), list) else []:
            evidence = check.get('evidence') if isinstance(check, dict) else None
            if evidence is None and preview_display_pending:
                continue
            try:
                observed = datetime.fromisoformat(str((evidence or {}).get('observed_at', '')).replace('Z', '+00:00'))
                if not observed.tzinfo or observed > datetime.now(timezone.utc):
                    raise ValueError('invalid time')
            except (ValueError, TypeError, AttributeError):
                failures.append('taskbox_display_observation_time_invalid')
    for value in (news, story):
        if value.get('review_method') != 'self' or not valid_context(value.get('taskbox_context')):
            failures.append('taskbox_same_task_review_context_required')
    from source_capture import validate_capture, normalize
    rows = {r.get('item_id'): r for r in news.get('items', []) if isinstance(r, dict)}
    for section in config.get('sections', []):
        for item in section.get('items', []):
            row = rows.get(item['id'], {})
            record = item.get('source_capture') or {}
            stored = captures.get(str(record.get('item_id')))
            if stored != record or validate_capture(item, record):
                failures.append('taskbox_selected_source_capture_invalid:' + item['id'])
                continue
            checked = row.get('source_crosscheck')
            keys = {'capture_record_sha256', 'response_sha256', 'quoted_excerpt', 'checked_at', 'reading_scope'}
            if (not isinstance(checked, dict) or set(checked) != keys
                    or checked.get('capture_record_sha256') != record['record_sha256']
                    or checked.get('response_sha256') != record['response_sha256']
                    or checked.get('quoted_excerpt') != record['quoted_excerpt']
                    or checked.get('reading_scope') != 'captured_primary_excerpt'):
                failures.append('taskbox_source_crosscheck_required:' + item['id'])
                continue
            try:
                checked_at = datetime.fromisoformat(checked['checked_at'].replace('Z', '+00:00'))
                captured_at = datetime.fromisoformat(record['retrieved_at'].replace('Z', '+00:00'))
                if not checked_at.tzinfo or not captured_at <= checked_at <= datetime.now(timezone.utc):
                    raise ValueError('invalid time')
            except (ValueError, TypeError, AttributeError):
                failures.append('taskbox_source_crosscheck_time_invalid:' + item['id'])
            for name in ('facts', 'judgment', 'relevance'):
                review = (row.get('claim_reviews') or {}).get(name) or {}
                anchor = normalize(str(review.get('evidence_anchor') or ''))
                if not anchor or anchor not in record['quoted_excerpt']:
                    failures.append('taskbox_claim_anchor_outside_capture:' + item['id'] + ':' + name)
    return failures
