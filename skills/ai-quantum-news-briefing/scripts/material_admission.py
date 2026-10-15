"""Evidence admission into authoring inputs, not semantic review approval."""
from __future__ import annotations
from datetime import date, datetime, timezone, timedelta
from urllib.parse import urlsplit
from briefing_contract import source_reference_url
from paper_identity import paper_kind
from source_capture import validate_capture


def publication_day(value):
    if not isinstance(value, str):
        raise ValueError('publication_date_missing')
    if len(value) == 10:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError('publication_date_invalid')
        return parsed
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('publication_timezone_missing')
    return parsed.astimezone(timezone(timedelta(hours=8))).date()


def admit_material(source_id, item, capture):
    failures = []
    if not isinstance(source_id, str) or not source_id or not isinstance(item, dict) or not isinstance(capture, dict):
        return ['material_shape_invalid']
    if item.get('material_kind') not in {'academic', 'social'}:
        failures.append('material_kind_missing')
    try:
        url = source_reference_url(item.get('source_url'))
        publication_day(item.get('published_at'))
        host = urlsplit(url).hostname or ''
        if host in {'aihot.virxact.com', 'google.com', 'www.google.com', 'api.plos.org'}:
            failures.append('discovery_is_not_original_article')
    except (ValueError, TypeError, AttributeError):
        failures.append('material_url_or_date_invalid')
    level = str(item.get('evidence_level') or '').lower()
    if not level or any(word in level for word in ('candidate', 'unverified', 'rumor')):
        failures.append('unverified_material')
    if not item.get('source_title') or not item.get('source_excerpt') or not item.get('evidence_fingerprint'):
        failures.append('article_evidence_missing')
    failures.extend(validate_capture(item, capture))
    if item.get('material_kind') == 'academic' and not paper_kind({**item, 'source_capture': capture}):
        failures.append('unsupported_academic_identity')
    return failures
