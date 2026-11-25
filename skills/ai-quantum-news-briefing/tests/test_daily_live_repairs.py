"""Offline regression for the Oct-25 observed adapter/selection failures.

Fixtures are synthetic discovery bytes, not evidence for a real edition.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0, str(SCRIPTS))
import academic_venue_sweep as sweep
import daily_coverage_evidence as coverage
import source_preparation as preparation
from daily_delivery_policy import policy_snapshot
from discovery_navigation import navigation_request
from material_admission import admit_material, publication_day
from rank_briefing_candidates import rank_briefing_config, parse_iso_date, constraint_reasons
from source_pool import SourcePool, task_spec
from source_worker import code_binding, resume_discovery
from test_rendered_search_evidence import fixture, rehash, DAY
from test_source_preparation_flow import discovery_fixture
from test_source_pool import material


def observed(record=None):
    value = deepcopy(record or fixture())
    observation = value['observation']
    observation['page_url'] += '&sei=PublicOpaqueRouting_123'
    observation.update(public_result_links=[{'title':'Users who reposted this post / X',
        'url':'https://www.google.com/goto?url=opaque-public-routing'}],
        result_links_observed=1, no_results_message_observed=False)
    rehash(value)
    return value


class DiscoveryAdapterRepairTests(unittest.TestCase):
    def test_real_format_is_retained_and_opaque_redirect_is_not_a_lead(self):
        old = observed(); before = deepcopy(old)
        value = coverage.adapt_rendered_search_observation(old, DAY)
        self.assertEqual(old, before)
        self.assertEqual(value['version'], 2)
        self.assertEqual(coverage.validate_rendered_search_observation(value, DAY), [])
        for key, raw in old['observation'].items():
            self.assertEqual(value['observation'][key], raw)
        self.assertEqual(value['http_receipt'], old['http_receipt'])
        row = value['observation']['result_classifications'][0]
        self.assertEqual(row['classification'], 'unresolved_google_redirect')
        self.assertIsNone(row['candidate_url'])
        self.assertFalse(value['observation']['no_results_message_observed'])
        self.assertFalse(value['observation']['publication_dates_verified'])

    def test_v1_behavior_stays_strict(self):
        self.assertEqual(coverage.validate_rendered_search_observation(fixture(), DAY), [])
        self.assertTrue(coverage.validate_rendered_search_observation(observed(), DAY))

    def test_adapter_is_idempotent(self):
        value = coverage.adapt_rendered_search_observation(observed(), DAY)
        self.assertEqual(coverage.adapt_rendered_search_observation(value, DAY), value)

    def test_forged_classification_rejected_even_after_rehash(self):
        value = coverage.adapt_rendered_search_observation(observed(), DAY)
        value['observation']['result_classifications'][0].update(
            classification='target_discovery_lead', candidate_url='https://x.com/sama/status/123')
        rehash(value)
        self.assertTrue(coverage.validate_rendered_search_observation(value, DAY))

    def test_boolean_result_index_is_not_an_integer_identity(self):
        value = coverage.adapt_rendered_search_observation(observed(), DAY)
        value['observation']['result_classifications'][0]['result_index'] = False
        rehash(value)
        self.assertTrue(coverage.validate_rendered_search_observation(value, DAY))

    def test_no_results_cannot_hide_off_scope_visible_results(self):
        value = coverage.adapt_rendered_search_observation(observed(), DAY)
        value['observation']['no_results_message_observed'] = True
        rehash(value)
        self.assertTrue(coverage.validate_rendered_search_observation(value, DAY))

    def test_missing_http_or_changed_raw_observation_never_adapts(self):
        for mutate in (lambda r:r.pop('http_receipt'),
                       lambda r:r['observation'].update(result_links_observed=10),
                       lambda r:r['http_receipt'].update(status_code=403)):
            value = observed(); mutate(value)
            with self.assertRaises(ValueError):coverage.adapt_rendered_search_observation(value, DAY)

    def test_unknown_tracking_private_duplicate_or_changed_query_rejected(self):
        for suffix in ('&unknown=1','&session=private','&sei=second','&q=other','&sei='):
            value = observed(); value['observation']['page_url'] += suffix; rehash(value)
            with self.assertRaises(ValueError):coverage.adapt_rendered_search_observation(value, DAY)

    def test_direct_lead_and_off_scope_result_remain_distinct(self):
        value = fixture()
        value['observation']['public_result_links'].append({'title':'Other account','url':'https://x.com/other/status/123'})
        value['observation']['result_links_observed'] = 2
        rehash(value)
        new = coverage.adapt_rendered_search_observation(value, DAY)
        rows = new['observation']['result_classifications']
        self.assertEqual([r['classification'] for r in rows],['target_discovery_lead','off_scope'])
        self.assertIsNone(rows[1]['candidate_url'])

    def test_target_retweet_endpoint_is_not_an_original_post_lead(self):
        value = fixture(); value['observation']['public_result_links'][0]['url'] += '/retweets'
        rehash(value)
        new = coverage.adapt_rendered_search_observation(value, DAY)
        self.assertEqual(new['observation']['result_classifications'][0]['classification'],'target_non_post')

    def test_native_conversion_does_not_claim_or_commit_a_blocked_task(self):
        (SCRIPTS.parents[2]/'.tmp').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='live-repair-test-', dir=str(SCRIPTS.parents[2]/'.tmp')) as folder:
            root=Path(folder); db=root/'_sources/pool.sqlite'
            native_day='2026-10-24'
            request=navigation_request('executive_social',native_day)
            record=observed(discovery_fixture(request))
            source=root/'synthetic-observation.json'
            source.write_text(json.dumps(record),encoding='utf-8')
            spec=task_spec('discovery','executive_social',native_day,{'navigation':request},
                           {'code':code_binding(),'policy':policy_snapshot()})
            with SourcePool(db) as pool:
                key=pool.enqueue(spec); owner=pool.claim(task_id=key)
                pool.fail(key,owner['lease'],{'code':'rendered_search_evidence_invalid','retryable':False})
                before=pool.get(key)
            output=io.StringIO()
            with redirect_stdout(output):
                exit_code=preparation.main(['adapt-discovery','--date','2026-10-25','--pool-dir',str(db.parent),
                    '--task-id',key,'--input',str(source),'--expected-sha256',hashlib.sha256(source.read_bytes()).hexdigest()])
            self.assertEqual(exit_code,0)
            converted=json.loads(output.getvalue())
            with SourcePool(db) as pool:
                result=resume_discovery(pool,key,converted)
                self.assertEqual(result['state'],'blocked')
                self.assertEqual(pool.get(key),before)


class PublicationAndFeedDateRepairTests(unittest.TestCase):
    def test_shanghai_window_utc_boundaries(self):
        for timestamp,expected in [('2026-10-23T15:59:59Z','2026-10-23'),
            ('2026-10-23T16:00:00Z','2026-10-24'),('2026-10-24T15:59:59Z','2026-10-24'),
            ('2026-10-24T16:00:00Z','2026-10-25')]:
            self.assertEqual(publication_day(timestamp).isoformat(),expected)
            self.assertEqual(parse_iso_date(timestamp).isoformat(),expected)

    def test_naive_material_date_cannot_be_treated_as_an_instant(self):
        with self.assertRaises(ValueError):publication_day('2026-10-24T12:00:00')

    def test_modified_only_entry_is_quarantined_not_published(self):
        body=b'<feed><entry><title>Updated old quantum item</title><updated>2026-10-24T01:00:00Z</updated></entry></feed>'
        stats={}
        with self.assertRaisesRegex(ValueError,'feed_has_no_valid_items'):
            sweep._generic_feed_items(body,funnel=stats)
        self.assertEqual(stats['updated_only_rejected'],1)
        self.assertEqual(stats['parsed_records'],0)

    def test_pubdate_beats_updated_and_raw_semantics_retained(self):
        body=b'<rss><item><title>quantum item</title><updated>2026-10-25T12:00:00Z</updated><pubDate>2026-10-23T16:00:00Z</pubDate></item></rss>'
        rows,bad=sweep._generic_feed_items(body)
        self.assertEqual(bad,0)
        self.assertEqual(rows[0]['published_at'],'2026-10-23T16:00:00+00:00')
        self.assertEqual(rows[0]['publication_date_raw'],'2026-10-23T16:00:00Z')
        self.assertEqual(rows[0]['date_semantics'],'feed_pubdate_publication_timestamp')

    def test_offline_feed_funnel_separates_date_topic_and_parse_failures(self):
        body=b'<rss><item><title>quantum valid</title><pubDate>2026-10-23T16:00:00Z</pubDate></item><item><title>quantum old</title><pubDate>2026-10-23T15:59:59Z</pubDate></item><item><title>other topic</title><pubDate>2026-10-24T01:00:00Z</pubDate></item><item><title>quantum updated</title><updated>2026-10-24T01:00:00Z</updated></item></rss>'
        source={'url':'https://fixture.invalid/feed','adapter':'rss','maximum_attempts':1}
        evidence={'query_url':source['url'],'final_url':source['url'],'status_code':200,'response_hash':hashlib.sha256(body).hexdigest()}
        with patch.object(sweep,'_request_source_with_retry',return_value=(evidence,body)):
            row=sweep._fetch_v4_row({},source,['quantum'],{'2026-10-24'},1)
        stats=row['collection_funnel']
        self.assertEqual([stats[k] for k in ('returned_records','parsed_records','parse_rejected','date_filtered','term_filtered','discovery_matches')],[4,3,1,1,1,1])
        self.assertFalse(stats['deduplication_performed'])

    def test_changed_original_source_or_missing_capture_is_rejected(self):
        item,capture=material()
        self.assertEqual(admit_material('plos-ai',item,capture),[])
        changed=deepcopy(item);changed['source_url']='https://www.google.com/goto?url=opaque'
        self.assertTrue(admit_material('plos-ai',changed,capture))
        self.assertTrue(admit_material('plos-ai',item,{}))


def social(number,organization='fixture.invalid',topic='shared'):
    return {'id':'S'+str(number),'source_url':'https://'+organization+'/story-'+str(number),
        'published_at':'2026-10-24T01:00:00Z','title':'Test story '+str(number),
        'facts':'已验证的合成测试事实','judgment':'合成判断','relevance':'合成关联',
        'source_title':'Test original '+str(number),'source_excerpt':'Synthetic original evidence '+str(number),
        'evidence_level':'reputable media original','evidence_fingerprint':'synthetic-'+str(number),
        'source_class':'reputable_media','organization':organization,'topic':topic}


class SelectionReasonRepairTests(unittest.TestCase):
    def rank(self,items):
        return rank_briefing_config({'sections':[{'title':'社会新闻','items':items}]},[],date(2026,10,25),7)['ranking_manifest']

    def test_organization_cap_remains_two_and_exclusion_is_exact(self):
        manifest=self.rank([social(i,topic='topic-'+str(i)) for i in range(4)])
        self.assertEqual(manifest['selected_counts']['social'],2)
        reasons=[r['exclusion_reasons'] for r in manifest['candidate_ledger'] if not r['selected']]
        self.assertEqual(reasons,[['maximum_items_per_organization']]*2)

    def test_topic_cap_remains_three_and_is_not_a_duplicate(self):
        manifest=self.rank([social(i,organization='source'+str(i)+'.invalid') for i in range(4)])
        self.assertEqual(manifest['selected_counts']['social'],3)
        rejected=[r for r in manifest['candidate_ledger'] if not r['selected']]
        self.assertEqual(rejected[0]['exclusion_reasons'],['maximum_items_per_topic'])

    def test_duplicate_reason_remains_distinct_from_quota_exclusion(self):
        item=social(1)
        duplicate=deepcopy(item);duplicate['id']='S2'
        manifest=self.rank([item,duplicate])
        self.assertEqual(manifest['selected_counts']['social'],1)
        self.assertIn('duplicate_candidate',next(r for r in manifest['candidate_ledger'] if not r['selected'])['exclusion_reasons'])

    def test_all_binding_caps_are_reported_without_changing_selection(self):
        candidate={'score':{'novelty':'new','topic':'shared','organization':'one'}}
        selected=[candidate,candidate,{'score':{'novelty':'new','topic':'shared','organization':'two'}}]
        reasons=constraint_reasons(candidate,selected,'social',policy_snapshot()['policy']['social'])
        self.assertEqual(reasons,['maximum_items_per_organization','maximum_items_per_topic'])


if __name__=='__main__':unittest.main()
