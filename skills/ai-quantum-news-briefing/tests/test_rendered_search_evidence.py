# -*- coding: utf-8 -*-
"""Discovery provenance tests; these fixtures approve no news or story content."""
import base64
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import daily_coverage_evidence as coverage
from test_release_protocol import daily_evidence

DAY = '2026-07-09'
TARGETS = {
    'reputable_media': ['techcrunch.com', 'channelnewsasia.com', 'theguardian.com'],
    'official_company_social': ['x.com/OpenAI', 'x.com/AnthropicAI', 'x.com/GoogleDeepMind'],
    'executive_social': ['x.com/sama', 'x.com/satyanadella', 'x.com/sundarpichai'],
}


def fixture(kind='executive_social', empty=False):
    targets = TARGETS[kind]
    query = ('(AI OR quantum) ' if kind == 'reputable_media' else '') + '(' + ' OR '.join('site:' + target for target in targets) + ') after:2026-07-08 before:2026-07-10'
    url = 'https://www.google.com/search?q=' + quote(query, safe='')
    results = [] if empty else [{'title': 'One public indexed result',
                                'url': 'https://' + targets[0] + ('/story' if kind == 'reputable_media' else '/status/123')}]
    observation = {'page_url': url, 'displayed_query': query, 'query_verified_in_UI': True,
                   'recorded_at': '2026-07-10T08:00:00+08:00',
                   'method': 'supported_browser_dom', 'browser': 'existing Edge test fixture',
                   'public_result_links': results, 'result_links_observed': len(results),
                   'no_results_message_observed': empty, 'next_page_link_observed': False,
                   'scope': 'observed_page_only', 'exhaustive_account_coverage': False,
                   'zero_account_publications_established': False,
                   'publication_dates_verified': False, 'personalization_possible': True}
    body = b'<html>Anonymous HTTP JavaScript bootstrap, not browser result bytes.</html>'
    receipt = {'query_url': url, 'final_url': url, 'status_code': 200,
               'retrieved_at': '2026-07-10T07:59:00+08:00',
               'coverage_start': DAY + 'T00:00:00+08:00', 'coverage_end': '2026-07-10T00:00:00+08:00',
               'response_hash': hashlib.sha256(body).hexdigest(),
               'hash_scope': 'raw_http_bytes', 'body_base64': base64.b64encode(body).decode('ascii')}
    return {'evidence_type': 'rendered_search_observation', 'version': 1, 'source_class': kind,
            'query_url': url, 'coverage_start': receipt['coverage_start'],
            'coverage_end': receipt['coverage_end'], 'source_targets': targets,
            'observation': observation, 'observation_sha256': coverage.evidence_digest(observation)[7:],
            'http_receipt': receipt}


def rehash(record):
    record['observation_sha256'] = coverage.evidence_digest(record['observation'])[7:]


class RenderedSearchEvidenceTests(unittest.TestCase):
    def errors(self, record):
        return coverage.validate_rendered_search_observation(record, DAY)

    def test_public_observation_and_separate_raw_http_are_accepted(self):
        for kind in TARGETS:
            with self.subTest(source_class=kind):
                record = fixture(kind)
                before = deepcopy(record)
                self.assertEqual(self.errors(record), [])
                self.assertEqual(record, before)
                self.assertNotEqual(record['observation_sha256'], record['http_receipt']['response_hash'])

    def test_no_results_means_no_index_matches_not_no_account_publications(self):
        record = fixture('official_company_social', empty=True)
        self.assertEqual(self.errors(record), [])
        record['observation']['zero_account_publications_established'] = True
        rehash(record)
        self.assertTrue(self.errors(record))

    def test_changed_or_missing_observation_cannot_use_old_digest(self):
        for mutate in (lambda r: r.pop('observation'),
                       lambda r: r['observation']['public_result_links'][0].update(title='external edit'),
                       lambda r: r.update(observation_sha256='a' * 64)):
            record = fixture(); mutate(record)
            self.assertTrue(self.errors(record))

    def test_query_page_targets_source_class_and_date_window_are_bound(self):
        mutations = (
            lambda r: r.update(source_class='official_company_social'),
            lambda r: r.update(source_targets=['x.com/unregistered']),
            lambda r: r.update(coverage_start='2026-07-08T00:00:00+08:00'),
            lambda r: r['observation'].update(displayed_query='different query'),
            lambda r: r['observation'].update(page_url='https://www.google.com/search?q=other'),
            lambda r: r['http_receipt'].update(query_url='https://www.google.com/search?q=other'),
            lambda r: r['observation'].update(recorded_at='2026-07-09T23:59:00+08:00'),
        )
        for mutate in mutations:
            record = fixture(); mutate(record); rehash(record)
            self.assertTrue(self.errors(record))

    def test_result_count_zero_conflicts_duplicates_and_off_target_results_rejected(self):
        for mutate in (
            lambda o: o.update(result_links_observed=2),
            lambda o: o.update(no_results_message_observed=True),
            lambda o: o['public_result_links'].append(deepcopy(o['public_result_links'][0])),
            lambda o: o['public_result_links'][0].update(url='https://x.com/OpenAI/status/123'),
            lambda o: o.update(result_links_observed=True),
        ):
            record = fixture(); mutate(record['observation']); rehash(record)
            self.assertTrue(self.errors(record))

    def test_private_fields_unknown_versions_and_unbounded_claims_rejected(self):
        for mutate in (
            lambda r: r.update(version=2), lambda r: r.update(version=True),
            lambda r: r.update(account_email='private@example.org'),
            lambda r: r['observation'].update(cookie='private'),
            lambda r: r['observation'].update(exhaustive_account_coverage=True),
            lambda r: r['observation'].update(publication_dates_verified=True),
            lambda r: r['observation'].update(method='invented_browser'),
        ):
            record = fixture(); mutate(record); rehash(record)
            self.assertTrue(self.errors(record))

    def test_http_bytes_and_dom_digest_cannot_be_interchanged(self):
        for mutate in (
            lambda r: r['http_receipt'].update(response_hash=r['observation_sha256']),
            lambda r: r['http_receipt'].update(body_base64='not valid base64'),
            lambda r: r['http_receipt'].pop('body_base64'),
            lambda r: r['http_receipt'].update(hash_scope='rendered_dom'),
            lambda r: r['http_receipt'].update(response_hash='0' * 64),
        ):
            record = fixture(); mutate(record)
            self.assertTrue(self.errors(record))

    def test_four_classes_require_ai_hot_and_reject_unknown_typed_fallback(self):
        social = daily_evidence(DAY)['social_search']
        social['source_class_evidence'] = [social['source_class_evidence'][0]] + [fixture(k) for k in TARGETS]
        self.assertEqual(coverage.validate_social_search(social, DAY), [])
        invalid = deepcopy(social)
        invalid['ai_hot_window']['pagination_complete'] = False
        self.assertTrue(coverage.validate_social_search(invalid, DAY))
        invalid = deepcopy(social)
        invalid['source_class_evidence'][1]['version'] = 99
        # Deliberately attach legacy HTTP keys: typed unknowns must not fall back.
        invalid['source_class_evidence'][1].update(social['source_class_evidence'][0])
        invalid['source_class_evidence'][1]['source_class'] = 'reputable_media'
        self.assertTrue(coverage.validate_social_search(invalid, DAY))

    def test_malformed_records_return_failures_instead_of_crashing(self):
        for record in (None, [], 'bad', {}, {'observation': None}):
            self.assertTrue(self.errors(record))
        record = fixture(); record['observation']['public_result_links'] = [None]
        rehash(record)
        self.assertTrue(self.errors(record))

    def test_removed_type_cannot_fall_back_to_http_metadata(self):
        social = daily_evidence(DAY)['social_search']
        record = fixture(); record.pop('evidence_type')
        record.update(social['source_class_evidence'][-1])
        social['source_class_evidence'][-1] = record
        self.assertTrue(coverage.validate_social_search(social, DAY))

    def test_negative_site_terms_and_malformed_url_rejected(self):
        record = fixture()
        query = record['observation']['displayed_query'].replace('site:x.com/sama', '-site:x.com/sama')
        url = 'https://www.google.com/search?q=' + quote(query, safe='')
        record['query_url'] = record['observation']['page_url'] = record['http_receipt']['query_url'] = url
        record['http_receipt']['final_url'] = url
        record['observation']['displayed_query'] = query
        rehash(record)
        self.assertTrue(self.errors(record))
        record = fixture(); record['http_receipt']['final_url'] = 'https://[bad'
        self.assertTrue(self.errors(record))

    def test_unknown_next_page_observation_is_retained_as_unknown(self):
        record = fixture()
        record['observation']['next_page_link_observed'] = None
        rehash(record)
        self.assertEqual(self.errors(record), [])
        record['observation']['next_page_link_observed'] = 'completed'
        rehash(record)
        self.assertTrue(self.errors(record))


if __name__ == '__main__':
    unittest.main()
