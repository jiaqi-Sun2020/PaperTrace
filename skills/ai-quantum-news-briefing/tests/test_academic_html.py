"""Actual-structure fixtures; uncertain dates and response shells stay rejected."""
from copy import deepcopy
from pathlib import Path
import hashlib,json,sys,unittest
from unittest.mock import patch
SCRIPTS=Path(__file__).resolve().parents[1]/'scripts';sys.path.insert(0,str(SCRIPTS))
from academic_html import publication_label,article_metadata,listing_records
from academic_sources import sources_by_id,row_is_healthy
from academic_venue_sweep import _fetch_v4_row
from source_capture import make_capture
from material_admission import admit_material,publication_day
from paper_identity import same_paper
FIX=Path(__file__).parent/'fixtures/academic-html'

class AcademicHTMLTests(unittest.TestCase):
    def test_year_only_does_not_invent_month_day_or_midnight(self):
        result=publication_label('2026');self.assertEqual(result['precision'],'year');self.assertIsNone(result['published_at'])

    def test_month_only_retains_unknown_day(self):
        result=publication_label('2026/10');self.assertEqual(result['precision'],'month');self.assertIsNone(result['published_at'])

    def test_day_precision_retains_calendar_label_without_timezone(self):
        result=publication_label('2026/10/24');self.assertEqual(result['published_at'],'2026-10-24');self.assertEqual(result['status'],'calendar_day_only')

    def test_naive_datetime_does_not_acquire_a_timezone(self):
        self.assertIsNone(publication_label('2026-10-24T11:00:00')['published_at'])

    def test_invalid_date_is_not_normalized_to_nearby_valid_day(self):
        self.assertEqual(publication_label('2026-02-30')['status'],'publication_date_invalid')

    def test_absolute_instant_obeys_shanghai_half_open_boundaries(self):
        self.assertEqual(publication_day(publication_label('2026-10-23T16:00:00Z')['published_at']).isoformat(),'2026-10-24')
        self.assertEqual(publication_day(publication_label('2026-10-24T16:00:00Z')['published_at']).isoformat(),'2026-10-25')

    def test_jmlr_actual_metadata_keeps_title_authors_abstract_and_year_precision(self):
        row=article_metadata((FIX/'jmlr.html').read_bytes(),'https://jmlr.org/papers/v27/26-0434.html')
        self.assertEqual(row['title'],'A Library for Learning Neural Operators');self.assertTrue(row['authors']);self.assertTrue(row['abstract'])
        self.assertEqual(row['publication']['precision'],'year');self.assertIsNone(row['publication']['published_at']);self.assertFalse(row['full_text_obtained'])

    def test_jmlr_modified_metadata_cannot_replace_absent_publication(self):
        body=(FIX/'jmlr.html').read_bytes().replace(b'citation_publication_date',b'citation_last_modified_date')
        self.assertIsNone(article_metadata(body,'https://jmlr.org/papers/v27/26-0434.html')['publication']['published_at'])

    def test_jmlr_wrong_original_identity_rejected(self):
        with self.assertRaises(ValueError):article_metadata((FIX/'jmlr.html').read_bytes(),'https://jmlr.org/papers/v27/other.html')

    def test_jmlr_incomplete_abstract_is_rejected(self):
        with self.assertRaises(ValueError):article_metadata(b'<meta name="citation_title" content="X">','https://jmlr.org/papers/v27/26-0434.html')

    def test_year_only_article_fails_native_material_admission(self):
        body=(FIX/'jmlr.html').read_bytes();metadata=article_metadata(body,'https://jmlr.org/papers/v27/26-0434.html')
        quote=metadata['abstract']
        item={'id':'TESTJMLR','material_kind':'academic','source_url':metadata['source_url'],'source_title':metadata['title'],
              'source_excerpt':quote,'published_at':'2026','source_class':'formal_academic','evidence_level':'publisher abstract',
              'evidence_fingerprint':'excerpt-sha256:'+hashlib.sha256(quote.encode()).hexdigest()}
        capture=make_capture(item,item['source_url'],item['source_url'],200,body,'2026-10-26T01:00:00+00:00')
        self.assertIn('material_url_or_date_invalid',admit_material('jmlr',item,capture))

    def test_iop_actual_anchor_structure_produces_stable_doi_discoveries(self):
        result=listing_records('iop-qst',(FIX/'iop.html').read_bytes(),'https://iopscience.iop.org/journal/2058-9565')
        self.assertEqual(len(result['records']),2);self.assertEqual(result['records'][0]['doi'],'10.1088/2058-9565/ae1e27')
        self.assertIsNone(result['records'][0]['published_at']);self.assertFalse(result['publisher_day_coverage_complete'])

    def test_iop_duplicates_merge_by_doi_not_fulltext_pdf_link(self):
        body=(FIX/'iop.html').read_bytes();result=listing_records('iop-qst',body+body,'https://iopscience.iop.org/journal/2058-9565')
        self.assertEqual(len(result['records']),2);self.assertEqual(result['collection_funnel']['duplicate_records_removed'],2)

    def test_external_injected_article_link_does_not_gain_iop_identity(self):
        body=b'<a class="art-list-item-title" href="https://evil.invalid/article/10.1088/2058-9565/ae1e27">Wrong</a>'
        self.assertFalse(listing_records('iop-qst',body,'https://iopscience.iop.org/journal/2058-9565')['records'])

    def test_ieee_actual_shell_is_not_a_zero_publication_claim(self):
        result=listing_records('ieee-tqe',(FIX/'ieee-shell.html').read_bytes(),'https://ieeexplore.ieee.org/xpl/mostRecentIssue.jsp?punumber=8924785')
        self.assertEqual(result['diagnostic'],'client_rendered_shell');self.assertFalse(result['publisher_day_coverage_complete'])

    def test_ieee_wrong_publication_number_cannot_be_accepted_as_tqe(self):
        with self.assertRaises(ValueError):listing_records('ieee-tqe',(FIX/'ieee-shell.html').read_bytes(),'https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=9140343')

    def test_one_malformed_href_does_not_discard_valid_neighbors(self):
        body=b'<a class="art-list-item-title" href="https://[malformed">Broken</a>'+(FIX/'iop.html').read_bytes()
        self.assertEqual(len(listing_records('iop-qst',body,'https://iopscience.iop.org/journal/2058-9565')['records']),2)

    def test_nonstandard_jmlr_port_cannot_gain_original_identity(self):
        with self.assertRaises(ValueError):article_metadata((FIX/'jmlr.html').read_bytes(),'https://jmlr.org:8443/papers/v27/26-0434.html')

    def test_iop_native_row_keeps_undated_discoveries_but_cannot_pass_family_gate(self):
        source=sources_by_id()['iop-qst'];body=(FIX/'iop.html').read_bytes()
        receipt={'query_url':source['url'],'final_url':source['url'],'status_code':200,'response_hash':hashlib.sha256(body).hexdigest(),'retrieved_at':'2026-10-26T01:00:00+00:00'}
        with patch('academic_venue_sweep._request_source_with_retry',return_value=(receipt,body)):
            row=_fetch_v4_row({},source,['quantum'],{'2026-10-24'},10)
        self.assertEqual(row['structured_candidate_count'],2);self.assertEqual(row['candidate_count'],0);self.assertFalse(row_is_healthy(row,'2026-10-24'))

    def test_cross_source_same_doi_deduplicates_without_mixing_publication_dates(self):
        left={'doi':'10.1038/s41467-026-78406-y','source_url':'https://www.nature.com/articles/s41467-026-78406-y','published_at':'2026-10-24'}
        right={'doi':'https://doi.org/10.1038/S41467-026-78406-Y','source_url':'https://api.crossref.org/works/example','published_at':'2026-10-25'}
        original=deepcopy([left,right]);self.assertTrue(same_paper(left,right));self.assertEqual([left,right],original)

    def test_preprint_and_formal_paper_need_explicit_same_identity_evidence(self):
        self.assertFalse(same_paper({'arxiv_id':'2610.12345','source_url':'https://arxiv.org/abs/2610.12345'},
                                    {'doi':'10.1000/fixture','source_url':'https://doi.org/10.1000/fixture'}))

if __name__=='__main__':unittest.main()
