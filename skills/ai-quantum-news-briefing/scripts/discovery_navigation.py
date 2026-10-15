"""Construct typed public discovery navigation; never sends a request itself."""
from __future__ import annotations
import json
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode
from daily_coverage_evidence import RENDERED_SEARCH_TARGETS


def navigation_request(source_class, coverage_date):
    if not isinstance(source_class, str) or not isinstance(coverage_date, str):
        raise ValueError('unsupported_discovery_scope')
    day = date.fromisoformat(coverage_date)
    if day.isoformat() != coverage_date or source_class not in RENDERED_SEARCH_TARGETS:
        raise ValueError('unsupported_discovery_scope')
    targets = sorted(RENDERED_SEARCH_TARGETS[source_class])
    query = '(' + ' OR '.join('site:' + target for target in targets) + ')'
    if source_class == 'reputable_media':
        query = '(AI OR quantum) ' + query
    query += ' after:%s before:%s' % ((day-timedelta(days=1)).isoformat(), (day+timedelta(days=1)).isoformat())
    return {'version': 1, 'type': 'navigation_url', 'source_class': source_class,
            'coverage_date': coverage_date, 'source_targets': targets, 'query': query,
            'url': 'https://www.google.com/search?' + urlencode({'q': query})}


def validate_navigation(request):
    if (not isinstance(request, dict) or request.get('type') != 'navigation_url'
            or type(request.get('version')) is not int):
        raise ValueError('navigation_url_object_required')
    expected = navigation_request(request.get('source_class'), request.get('coverage_date'))
    if request != expected:
        raise ValueError('navigation_scope_or_url_changed')
    return request['url']


def browser_call(request, tab_expression='tab'):
    """A bounded CUA invocation; callers choose the existing, permitted tab only.

    No browser, alternate protocol or local server is created. A policy denial
    from tab.goto propagates unchanged. The agent must stop that action.
    """
    validate_navigation(request)
    if tab_expression != 'tab':
        raise ValueError('use_existing_tab_binding')
    helper = Path(__file__).with_name('discovery_navigation.mjs').read_text(encoding='utf-8')
    helper = helper.replace('export ', '')
    return '{\n' + helper + '\nawait navigateSource(tab, ' + json.dumps(request, ensure_ascii=False) + ');\n}'
