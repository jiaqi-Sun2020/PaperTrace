#!/usr/bin/env python3
"""Offline adversarial cases for publisher and daily candidate coverage."""

from __future__ import annotations

import json
import hashlib
import io
import socket
import sys
import unittest
import urllib.error
import urllib.request
from argparse import Namespace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import academic_venue_sweep as sweep
import aihot_candidates as hot
from audit_briefing_config import academic_search_venues, valid_science_skip_v2, valid_venue_evidence
from daily_coverage_evidence import validate_social_search


class APSRecentFeedTests(unittest.TestCase):
    @staticmethod
    def feed(journal: str = "Physical Review A") -> bytes:
        return (f'''<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"
 xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/">
 <channel><title>Recent Articles in {journal}</title></channel>
 <item><title>Quantum estimation</title><description>A quantum method</description>
  <dc:date>2026-09-28T10:00:00+00:00</dc:date>
  <prism:doi>10.1103/k7m2-vyqq</prism:doi>
  <prism:publicationName>{journal}</prism:publicationName></item>
 <item><title>Undated item</title><dc:date></dc:date>
  <prism:doi>10.1103/undated</prism:doi>
  <prism:publicationName>{journal}</prism:publicationName></item>
</rdf:RDF>''').encode()

    def test_journal_specific_urls_and_one_bad_item_does_not_discard_feed(self) -> None:
        plan = sweep.build_plan(["quantum", "method quantum"], "2026-09-28", True, False)
        urls = {row["venue"]: row["search_url"] for row in plan["rows"]}
        self.assertEqual(urls["aps-prl"], "https://feeds.aps.org/rss/recent/prl.xml")
        self.assertEqual(urls["aps-pra"], "https://feeds.aps.org/rss/recent/pra.xml")
        self.assertEqual(urls["aps-prx"], "https://feeds.aps.org/rss/recent/prxquantum.xml")
        rows = [row for row in plan["rows"] if row["venue"] == "aps-pra"]
        plan["rows"] = rows
        plan["topics"] = [{"term": term} for term in ("quantum", "method quantum")]
        def fetch(url: str, _timeout: int):
            body = self.feed()
            return ({"query_url": url, "final_url": url, "status_code": 200,
                     "retrieved_at": "2026-09-29T00:00:00Z",
                     "response_hash": hashlib.sha256(body).hexdigest()}, body)
        with patch.object(sweep, "_request_evidence", side_effect=fetch) as request:
            sweep.fetch_evidence(plan)
        self.assertEqual(request.call_count, 1)  # One fetch per journal, not per topic.
        for row in rows:
            self.assertEqual(row["result"], "checked")
            self.assertEqual(row["url"], "https://doi.org/10.1103/k7m2-vyqq")
            self.assertEqual(row["evidence"]["quarantined_item_count"], 1)
            self.assertEqual(row["evidence"]["coverage_claim"], "discovery_only")
            self.assertEqual(len(row["matches"]), 1)
            self.assertTrue(valid_venue_evidence(row))

    def test_wrong_journal_and_expired_rolling_feed_fail_closed(self) -> None:
        row = {"venue": "aps-prl", "term": "quantum",
               "search_url": "https://feeds.aps.org/rss/recent/prl.xml"}
        url = row["search_url"]
        evidence = {"query_url": url, "final_url": url, "status_code": 200,
                    "response_hash": hashlib.sha256(self.feed()).hexdigest()}
        with self.assertRaisesRegex(ValueError, "no valid dated"):
            sweep._aps_recent_row(row, self.feed(), evidence, {"2026-09-28"})
        pra = {**row, "venue": "aps-pra", "search_url": "https://feeds.aps.org/rss/recent/pra.xml"}
        pra_url = pra["search_url"]
        with self.assertRaisesRegex(ValueError, "older than"):
            sweep._aps_recent_row(pra, self.feed(),
                                  {"query_url": pra_url, "final_url": pra_url, "status_code": 200,
                                   "response_hash": hashlib.sha256(self.feed()).hexdigest()},
                                  {"2026-09-01"})
        with self.assertRaisesRegex(ValueError, "body hash"):
            sweep._aps_recent_row(pra, self.feed(),
                                  {"query_url": pra_url, "final_url": pra_url, "status_code": 200,
                                   "response_hash": "0" * 64}, {"2026-09-28"})

    def test_failed_aps_fetch_never_becomes_a_checked_venue(self) -> None:
        plan = sweep.build_plan(["quantum"], "2026-09-28", True, False)
        plan["rows"] = [row for row in plan["rows"] if row["venue"] == "aps-prl"]
        url = plan["rows"][0]["search_url"]
        with patch.object(sweep, "_request_evidence", return_value=(
                {"query_url": url, "final_url": "", "status_code": 0,
                 "response_hash": "", "error": "IncompleteRead"}, b"")):
            sweep.fetch_evidence(plan)
        row = plan["rows"][0]
        self.assertEqual(row["result"], "error")
        self.assertFalse(valid_venue_evidence(row))


class ScienceCoverageTests(unittest.TestCase):
    def test_official_200_without_complete_day_list_stays_pending(self) -> None:
        row = {"venue": "science", "term": "quantum", "search_url": "https://www.science.org/action/doSearch?AllField=quantum"}
        def fetch(url: str, _timeout: int):
            code = 200
            return ({"query_url": url, "final_url": url, "status_code": code,
                     "retrieved_at": "2026-09-28T00:00:00Z", "response_hash": "a" * 64}, b"<rss><item></item></rss>")
        snapshot = {"provider": "crossref", "role": "indexed_metadata_discovery",
                    "query_complete": True, "publisher_day_coverage_complete": False,
                    "items": [], "total_count": 0, "retrieved_count": 0}
        with patch.object(sweep, "_request_evidence", side_effect=fetch), patch.object(
                sweep, "_crossref_science_snapshot", return_value=snapshot):
            sweep._science_row(row, ["2026-09-27"], 1, {})
        self.assertEqual(row["retrieval_status"], "success")
        self.assertEqual(row["coverage_status"], "unavailable")
        self.assertEqual(row["result"], "skipped_unavailable")
        self.assertEqual(row["skip_reason_code"], "no_complete_dated_listing")
        self.assertFalse(valid_venue_evidence(row))
        self.assertEqual(row["provider_evidence"][1]["role"], "official_toc_discovery")
        self.assertEqual(row["provider_evidence"][2]["role"], "corroboration")

    def test_403_crossref_complete_preserves_block_and_does_not_pass(self) -> None:
        row = {"venue": "science", "term": "quantum", "search_url": "https://www.science.org/action/doSearch?AllField=quantum"}
        def fetch(url: str, _timeout: int):
            code = 200 if "showFeed" in url else 403
            return ({"query_url": url, "final_url": url, "status_code": code,
                     "retrieved_at": "2026-09-28T00:00:00Z", "response_hash": "a" * 64}, b"")
        snapshot = {"provider": "crossref", "role": "indexed_metadata_discovery",
                    "query_complete": True, "publisher_day_coverage_complete": False,
                    "items": [], "total_count": 0, "retrieved_count": 0}
        with patch.object(sweep, "_request_evidence", side_effect=fetch), patch.object(
                sweep, "_crossref_science_snapshot", return_value=snapshot):
            sweep._science_row(row, ["2026-09-27"], 1, {})
        self.assertEqual(row["retrieval_status"], "blocked")
        self.assertEqual(row["coverage_status"], "unavailable")
        self.assertEqual(row["skip_reason_code"], "access_denied")
        self.assertEqual(row["provider_evidence"][0]["status_code"], 403)
        self.assertFalse(valid_venue_evidence(row))

    def test_v2_skip_requires_both_official_attempts_and_correct_day(self) -> None:
        day = "2026-09-27"
        providers = [
            {"provider": "science", "role": role, "proves_daily_coverage": False,
             "query_url": url, "final_url": url, "retrieved_at": "2026-09-28T00:00:00Z",
             "status_code": code, "response_hash": "a" * 64}
            for role, url, code in (
                ("official_search", "https://www.science.org/action/doSearch?AllField=quantum", 403),
                ("official_toc_discovery", "https://www.science.org/toc/science/0/0", 200),
            )]
        row = {"venue": "science", "result": "skipped_unavailable", "coverage_status": "unavailable",
               "verification_method": "none", "coverage_date": day, "retrieval_status": "blocked",
               "skip_reason_code": "access_denied", "provider_evidence": providers, "evidence": providers[0]}
        self.assertTrue(valid_science_skip_v2(row, day))
        self.assertFalse(valid_science_skip_v2(row, "2026-09-26"))
        self.assertFalse(valid_science_skip_v2({**row, "provider_evidence": providers[:1]}, day))
        self.assertFalse(valid_science_skip_v2({**row, "skip_reason_code": "no_complete_dated_listing"}, day))
        self.assertFalse(valid_science_skip_v2({**row, "provider_evidence": [
            {**providers[0], "response_hash": ""}, providers[1]]}, day))
        self.assertFalse(valid_science_skip_v2({**row, "provider_evidence": [
            {**providers[0], "retrieved_at": "2026-09-27T00:00:00Z"}, providers[1]]}, day))

    def test_arxiv_rate_limit_retries_only_twice_then_remains_blocked(self) -> None:
        url = "https://export.arxiv.org/api/query?search_query=all:quantum"
        request = urllib.request.Request(url)
        def limited():
            return urllib.error.HTTPError(url, 429, "rate limited", {"Retry-After": "9"}, io.BytesIO(b""))
        with patch.object(sweep.urllib.request, "urlopen", side_effect=[limited(), limited(), limited()]) as fetch, patch.object(sweep.time, "sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError):
                sweep._open_venue_with_retry(request, 1, "arxiv")
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [3.0, 3.0])

    def test_arxiv_body_timeout_retries_the_complete_request(self) -> None:
        class Response:
            status = 200

            def __init__(self, body=None, error=None):
                self.body, self.error = body, error

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def geturl(self):
                return "https://export.arxiv.org/api/query?search_query=all:quantum"

            def read(self, _limit):
                if self.error:
                    raise self.error
                return self.body

        request = urllib.request.Request("https://export.arxiv.org/api/query?search_query=all:quantum")
        with patch.object(sweep, "_open_venue_with_retry", side_effect=[
                Response(error=socket.timeout("timed out")), Response(body=b"<feed/>")]) as opened, \
             patch.object(sweep.time, "sleep") as sleep:
            status, final_url, body = sweep._read_venue_with_retry(request, 1, "arxiv")
        self.assertEqual((status, final_url, body), (200, request.full_url, b"<feed/>"))
        self.assertEqual(opened.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_self_hashed_synthetic_listing_cannot_authorize_v2(self) -> None:
        day = "2026-09-27"
        row = {"venue": "science", "term": "quantum", "result": "checked",
               "coverage_status": "verified", "verification_method": "official_complete_listing",
               "evidence": {"query_url": "https://www.science.org/action/doSearch?AllField=quantum",
                            "final_url": "https://www.science.org/action/doSearch?AllField=quantum",
                            "retrieved_at": "2026-09-28T00:00:00Z", "status_code": 200,
                            "response_hash": "a" * 64}}
        ledger = {"date_range": day, "topics": [{"term": "quantum"}], "rows": [row]}
        venues, _, _, problems = academic_search_venues(
            {"academic_search": ledger}, coverage_contract_version=2)
        self.assertNotIn("science", venues)
        self.assertTrue(problems)

    def test_crossref_pagination_complete_vs_partial(self) -> None:
        article = {"DOI": "10.1126/science.one", "ISSN": ["0036-8075"],
                   "type": "journal-article", "title": ["Quantum walk"],
                   "published-online": {"date-parts": [[2026, 9, 27]]}}
        calls = 0
        def complete(_url: str, _timeout: int):
            nonlocal calls
            calls += 1
            items = [article] if calls == 1 else []
            body = json.dumps({"message": {"items": items, "total-results": 1,
                                           "next-cursor": "second"}}).encode()
            return ({"status_code": 200, "response_hash": "a" * 64,
                     "query_url": "https://api.crossref.org/works", "final_url": "https://api.crossref.org/works"}, body)
        with patch.object(sweep, "_request_evidence", side_effect=complete):
            result = sweep._crossref_science_snapshot("2026-09-27", 1, rows_per_page=1)
        self.assertTrue(result["query_complete"])
        self.assertEqual(result["retrieved_count"], 1)
        self.assertEqual(result["unique_science_count"], 1)
        self.assertFalse(result["publisher_day_coverage_complete"])
        self.assertTrue(sweep._topic_matches(result["items"][0], "quantum walk"))
        with patch.object(sweep, "_request_evidence", side_effect=[
            ({"status_code": 200, "response_hash": "a" * 64},
             json.dumps({"message": {"items": [article], "total-results": 2,
                                      "next-cursor": "second"}}).encode()),
            ({"status_code": 429, "response_hash": "b" * 64}, b"")]):
            partial = sweep._crossref_science_snapshot("2026-09-27", 1, rows_per_page=1)
        self.assertFalse(partial["query_complete"])
        with patch.object(sweep, "_request_evidence", return_value=(
                {"status_code": 200, "response_hash": ""},
                json.dumps({"message": {"items": [], "total-results": 0}}).encode())):
            no_hash = sweep._crossref_science_snapshot("2026-09-27", 1, rows_per_page=1)
        self.assertFalse(no_hash["query_complete"])

    def test_official_complete_record_only_passes_with_provenance_and_scope(self) -> None:
        listing_body = json.dumps({"source": "Science", "coverage_start": "2026-09-27T00:00:00+08:00",
                                   "coverage_end": "2026-09-28T00:00:00+08:00", "total_count": 2,
                                   "has_next": False,
                                   "items": [{"doi": "10.1126/science.one", "published_at": "2026-09-27T08:00:00+08:00"},
                                             {"doi": "10.1126/science.two", "published_at": "2026-09-27T09:00:00+08:00"}]})
        listing_hash = hashlib.sha256(listing_body.encode()).hexdigest()
        provider = {"provider": "science", "role": "official_search",
                    "proves_daily_coverage": True, "pagination_complete": True,
                    "total_count": 2, "retrieved_count": 2,
                    "coverage_start": "2026-09-27T00:00:00+08:00",
                    "coverage_end": "2026-09-28T00:00:00+08:00",
                    "query_url": "https://www.science.org/action/doSearch?AllField=quantum&from=2026-09-27&until=2026-09-28",
                    "final_url": "https://www.science.org/action/doSearch?AllField=quantum&from=2026-09-27&until=2026-09-28",
                    "retrieved_at": "2026-09-28T00:00:00Z", "status_code": 200,
                    "response_hash": listing_hash,
                    "listing_pages": [{"query_url": "https://www.science.org/action/doSearch?AllField=quantum&from=2026-09-27&until=2026-09-28",
                                       "response_hash": listing_hash, "response_body": listing_body}]}
        row = {"venue": "science", "result": "checked", "coverage_status": "verified",
               "verification_method": "official_complete_listing", "provider_evidence": [provider]}
        self.assertTrue(valid_venue_evidence(row))
        provider["response_hash"] = ""
        self.assertFalse(valid_venue_evidence(row))
        provider["response_hash"] = listing_hash
        provider["provider"] = "crossref"
        self.assertFalse(valid_venue_evidence(row))


class AiHotWindowTests(unittest.TestCase):
    def _args(self, day: str) -> Namespace:
        return Namespace(mode="selected", take=1, category=None, since=None,
                         query=None, coverage_date=day)

    def test_same_latest_items_are_split_by_shanghai_day_and_boundaries(self) -> None:
        yesterday = (datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()
                     - timedelta(days=1))
        prior = yesterday - timedelta(days=1)
        left = datetime.combine(yesterday, datetime.min.time(), timezone(timedelta(hours=8)))
        right = left + timedelta(days=1)
        records = [{"id": "prior", "publishedAt": (left - timedelta(seconds=1)).isoformat()},
                   {"id": "start", "publishedAt": left.isoformat()},
                   {"id": "end", "publishedAt": right.isoformat()}]
        def fetch(url: str):
            body = json.dumps({"items": records, "hasNext": False})
            return body, {"query_url": url, "final_url": url, "status_code": 200,
                          "retrieved_at": right.isoformat(), "response_hash": "a" * 64}
        with patch.object(hot, "fetch_response", side_effect=fetch):
            today_items, today_evidence = hot.api_items(self._args(yesterday.isoformat()))
            prior_items, _ = hot.api_items(self._args(prior.isoformat()))
        self.assertEqual([item["id"] for item in today_items], ["start"])
        self.assertEqual([item["id"] for item in prior_items], ["prior"])
        self.assertEqual(today_evidence["outside_window_count"], 2)
        self.assertEqual(today_evidence["coverage_status"], "verified")

    def test_missing_timestamp_or_cursor_loop_is_partial(self) -> None:
        day = (datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()
               - timedelta(days=1)).isoformat()
        def fetch(url: str):
            body = json.dumps({"items": [{"id": "untimed"}], "hasNext": True,
                               "nextCursor": "again"})
            return body, {"query_url": url, "final_url": url, "status_code": 200,
                          "retrieved_at": datetime.now(timezone.utc).isoformat(),
                          "response_hash": "a" * 64}
        with patch.object(hot, "fetch_response", side_effect=fetch):
            items, evidence = hot.api_items(self._args(day))
        self.assertEqual(items, [])
        self.assertEqual(evidence["coverage_status"], "partial")
        self.assertEqual(evidence["missing_timestamp_count"], 2)

    def test_one_undated_candidate_is_quarantined_without_disabling_dated_pool(self) -> None:
        from test_release_protocol import daily_evidence
        day = (datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=8))).date()
               - timedelta(days=1)).isoformat()
        start, end = hot.coverage_window(day)
        records = [{"id": "dated", "publishedAt": (start + timedelta(hours=1)).isoformat()},
                   {"id": "undated"}]
        def fetch(url: str):
            return (json.dumps({"items": records, "hasNext": False}),
                    {"query_url": url, "final_url": url, "status_code": 200,
                     "retrieved_at": end.isoformat(), "response_hash": "a" * 64})
        with patch.object(hot, "fetch_response", side_effect=fetch):
            items, evidence = hot.api_items(self._args(day))
        self.assertEqual([item["id"] for item in items], ["dated"])
        self.assertEqual(evidence["coverage_status"], "qualified_with_exclusion")
        self.assertEqual(evidence["coverage_claim"], "dated_candidates_only")
        social = daily_evidence(day)["social_search"]
        social["ai_hot_window"] = evidence
        self.assertEqual(validate_social_search(social, day), [])
        social["ai_hot_window"] = {**evidence, "undated_exclusions": []}
        self.assertTrue(validate_social_search(social, day))
        social["ai_hot_window"] = {**evidence, "pagination_complete": False}
        self.assertTrue(validate_social_search(social, day))

    def test_older_than_api_retention_cannot_be_verified(self) -> None:
        day = (datetime.now(timezone.utc).date() - timedelta(days=8)).isoformat()
        with patch.object(hot, "fetch_response", return_value=(
                json.dumps({"items": [], "hasNext": False}),
                {"query_url": "https://aihot.virxact.com/api/public/items", "response_hash": "a" * 64})):
            _, evidence = hot.api_items(self._args(day))
        self.assertEqual(evidence["coverage_status"], "partial")


if __name__ == "__main__":
    unittest.main()
