"""Publisher subject labels fix a lexical false negative, not evidence gates."""
from copy import deepcopy
from pathlib import Path
import sys,unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(SCRIPTS))
from academic_sources import sources_by_id
import academic_venue_sweep as sweep

class RegisteredSubjectFeedTests(unittest.TestCase):
    def run_row(self,source=None,terms=None,date='2026-10-24T00:00:00Z'):
        source=source or sources_by_id()['nature-machine-learning']
        body=('<rss><item><title>Predicting protein electrostatics with protein language models</title>'
              '<link>https://www.nature.com/articles/synthetic-fixture</link>'
              '<pubDate>'+date+'</pubDate><description>Sequence-based protein models.</description></item></rss>').encode()
        evidence={'query_url':source['url'],'final_url':source['url'],'status_code':200}
        with patch.object(sweep,'_request_source_with_retry',return_value=(evidence,body)):
            return sweep._fetch_v4_row({},source,terms if terms is not None else ['machine learning'],{'2026-10-24'},1)

    def test_registered_subject_scope_keeps_relevant_paper_without_literal_phrase(self):
        row=self.run_row()
        self.assertEqual(row['candidate_count'],1)
        self.assertEqual(row['collection_funnel']['subject_scope_matches'],1)
        self.assertEqual(row['matches'][0]['topic_match_basis'],'registered_publisher_subject_feed')
        self.assertFalse(row['topic_filter_evidence']['article_qualification'])

    def test_spoofed_url_cannot_inherit_registered_subject(self):
        source=deepcopy(sources_by_id()['nature-machine-learning']);source['url']='https://unregistered.invalid/feed'
        self.assertEqual(self.run_row(source)['candidate_count'],0)

    def test_unrelated_requested_topic_does_not_match(self):
        self.assertEqual(self.run_row(terms=['quantum'])['candidate_count'],0)

    def test_subject_scope_does_not_bypass_original_date(self):
        row=self.run_row(date='2026-10-23T00:00:00Z')
        self.assertEqual(row['candidate_count'],0)
        self.assertEqual(row['collection_funnel']['date_filtered'],1)

if __name__=='__main__':unittest.main()
