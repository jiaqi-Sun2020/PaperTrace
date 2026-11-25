"""Bounded publisher HTML discovery and citation metadata; never paper approval.

Only structures observed on the registered JMLR/IOP/IEEE samples are parsed.
Calendar labels retain their precision. No updated, indexed or fetched fallback.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, parse_qs


def publication_label(raw):
    """Represent source precision without inventing a day, clock or timezone."""
    value = str(raw or '').strip()
    result = {'raw': value, 'precision': 'unknown', 'published_at': None,
              'status': 'publication_date_unresolved'}
    try:
        if re.fullmatch(r'\d{4}', value):
            date(int(value), 1, 1)
            result.update(precision='year', status='publication_day_unresolved')
        elif re.fullmatch(r'\d{4}[-/]\d{1,2}', value):
            year, month = map(int, re.split('[-/]', value))
            date(year, month, 1)
            result.update(precision='month', status='publication_day_unresolved')
        elif re.fullmatch(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', value):
            result.update(precision='day', published_at=date(*map(int, re.split('[-/]', value))).isoformat(),
                          status='calendar_day_only')
        elif value:
            stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                result.update(precision='local_datetime', status='publication_timezone_unresolved')
            else:
                result.update(precision='instant', published_at=stamp.isoformat(), status='absolute_instant')
    except (ValueError, OverflowError):
        result['status'] = 'publication_date_invalid'
    return result


class PublisherHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.metadata = {}; self.anchors = []; self.anchor = None
        self.abstract_parts = []; self.abstract_depth = None
        self.stack = []; self.skip = 0; self.client_shell = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {'script', 'style', 'noscript'}:
            self.skip += 1
        if tag == 'xpl-root':
            self.client_shell = True
        if tag == 'meta':
            name = str(attrs.get('name') or attrs.get('property') or '').casefold()
            if name.startswith('citation_'):
                self.metadata.setdefault(name, []).append(str(attrs.get('content') or '').strip())
        if tag == 'a':
            self.anchor = {'href': attrs.get('href') or '', 'class': attrs.get('class') or '', 'text': []}
            self.anchors.append(self.anchor)
        if tag not in {'meta', 'link', 'img', 'br', 'hr', 'input', 'source', 'wbr', 'area', 'base', 'embed', 'param', 'track'}:
            self.stack.append(tag)
            if self.abstract_depth is None and 'abstract' in str(attrs.get('class') or '').split():
                self.abstract_depth = len(self.stack)

    def handle_endtag(self, tag):
        if tag == 'a':
            self.anchor = None
        if tag in {'script', 'style', 'noscript'} and self.skip:
            self.skip -= 1
        if tag in self.stack:
            depth = len(self.stack) - self.stack[::-1].index(tag)
            if self.abstract_depth is not None and depth <= self.abstract_depth:
                self.abstract_depth = None
            del self.stack[depth - 1:]

    def handle_data(self, value):
        if not self.skip:
            if self.anchor is not None:
                self.anchor['text'].append(value)
            if self.abstract_depth is not None:
                self.abstract_parts.append(value)


def parsed_html(body):
    if not isinstance(body, bytes) or not body or len(body) > 8_000_000:
        raise ValueError('publisher_html_empty_or_oversize')
    parser = PublisherHTML()
    parser.feed(body.decode('utf-8', errors='replace'))
    return parser


def listing_records(source_id, body, source_url):
    """Extract real article hrefs, retain undated discoveries, expose empty shells."""
    p = parsed_html(body)
    base = urlsplit(source_url)
    if (base.scheme != 'https' or base.username or base.password or base.fragment or base.port not in (None, 443)):
        raise ValueError('publisher_listing_scope_mismatch')
    if source_id == 'iop-qst' and (base.hostname != 'iopscience.iop.org' or base.path != '/journal/2058-9565' or base.query):
        raise ValueError('publisher_listing_scope_mismatch')
    if source_id == 'ieee-tqe' and (base.hostname != 'ieeexplore.ieee.org'
            or base.path != '/xpl/mostRecentIssue.jsp' or parse_qs(base.query) != {'punumber': ['8924785']}):
        raise ValueError('publisher_listing_scope_mismatch')
    if source_id not in {'iop-qst', 'ieee-tqe'}:
        raise ValueError('publisher_listing_not_supported')
    records = []; seen = set(); observed = 0
    for anchor in p.anchors:
        if source_id == 'iop-qst' and 'art-list-item-title' not in anchor['class'].split():
            continue
        try:
            url = urljoin(source_url, anchor['href'])
            parsed = urlsplit(url)
            valid = (parsed.scheme == 'https' and parsed.hostname == base.hostname and not parsed.username and not parsed.password
                     and parsed.port in (None, 443) and not parsed.query and not parsed.fragment)
        except ValueError:
            continue  # A malformed href cannot discard valid neighboring article records.
        if not valid:
            continue
        match = (re.fullmatch(r'/article/(10\.1088/2058-9565/[A-Za-z0-9]+)', parsed.path) if source_id == 'iop-qst'
                 else re.fullmatch(r'/document/([0-9]+)', parsed.path.rstrip('/')))
        title = ' '.join(' '.join(anchor['text']).split())
        if not match or not title:
            continue
        observed += 1
        identity = ('doi:' if source_id == 'iop-qst' else 'ieee:') + match.group(1).lower()
        if identity in seen:
            continue
        seen.add(identity)
        records.append({'title': title, 'url': url, 'stable_id': identity,
                        'doi': match.group(1).lower() if source_id == 'iop-qst' else None,
                        'published_at': None, 'date_precision': 'unknown',
                        'date_status': 'original_article_publication_required',
                        'evidence_scope': 'publisher_listing_discovery_not_article_capture'})
    return {'records': records, 'collection_funnel': {'returned_records': observed,
            'parsed_records': observed, 'parse_rejected': 0,
            'duplicate_records_removed': observed-len(records), 'deduplication_performed': True,
            'structured_discoveries': len(records), 'publication_date_confirmed': 0,
            'publication_date_unresolved': len(records), 'date_filtered': 0,
            'discovery_matches': 0, 'article_capture_not_attempted_here': True},
            'diagnostic': 'client_rendered_shell' if not records and p.client_shell else
                          'article_dates_required' if records else 'no_supported_article_structure',
            'publisher_day_coverage_complete': False}


def article_metadata(body, source_url):
    """Read observed JMLR citation/abstract fields; year-only metadata stays undated."""
    parsed = urlsplit(source_url)
    if (parsed.scheme != 'https' or parsed.hostname not in {'jmlr.org', 'www.jmlr.org'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.port not in (None, 443)
            or not re.fullmatch(r'/papers/v[0-9]+/[A-Za-z0-9_-]+\.html', parsed.path)):
        raise ValueError('publisher_article_scope_mismatch')
    p = parsed_html(body)
    def only(key):
        values = {v for v in p.metadata.get(key, []) if v}
        if len(values) > 1:
            raise ValueError('publisher_article_metadata_conflict')
        return next(iter(values), '')
    original = only('citation_public_url') or only('citation_abstract_html_url')
    if original:
        identity = urlsplit(original)
        if (identity.hostname not in {'jmlr.org', 'www.jmlr.org'} or identity.path != parsed.path
                or identity.username or identity.password or identity.query or identity.fragment):
            raise ValueError('publisher_article_identity_mismatch')
    title = only('citation_title'); authors = p.metadata.get('citation_author', [])
    abstract = ' '.join(' '.join(p.abstract_parts).split())
    if not title or not authors or not abstract:
        raise ValueError('publisher_article_metadata_incomplete')
    pub = publication_label(only('citation_publication_date'))
    return {'metadata_version': 1, 'title': title, 'authors': authors, 'abstract': abstract,
            'stable_id': 'jmlr:' + parsed.path, 'source_url': source_url,
            'publication': {**pub, 'source_field': 'citation_publication_date',
                            'semantics': 'publisher_publication_calendar_label'},
            'response_sha256': hashlib.sha256(body).hexdigest(),
            'evidence_level': 'publisher_abstract', 'full_text_obtained': False,
            'publication_approved': False}
