#!/usr/bin/env python3
"""Adversarial source-family, isolation and bounded-fetch tests for pipeline v4."""

from __future__ import annotations

import hashlib
import http.client
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import academic_venue_sweep as sweep
from academic_sources import family_gate, load_registry, markdown_health_table
from audit_briefing_config import academic_search_venues
from daily_coverage_evidence import evidence_digest, validate_daily_evidence
from daily_pipeline import parse_args as parse_pipeline_args
from delivery_expansion import default_policy
from paper_identity import same_paper
from datetime import datetime
from evidence_fixtures import evidenced_row


def row(source_id: str, result: str = "checked", day="2026-09-27") -> dict:
    return evidenced_row({"source_id": source_id, "result": result,
            "retrieval_status": "success" if result == "checked" else "error",
            "parse_status": "success" if result == "checked" else "not_attempted",
            "window_status": "rolling_window" if result == "checked" else "unknown",
            "candidate_count": 1, "quarantined_count": 0}, day)


class AcademicSourceRegistryTests(unittest.TestCase):
    def test_new_cli_defaults_to_pipeline_four_and_expansion_two(self) -> None:
        args = parse_pipeline_args(["run", "--config", "candidate.json", "--date", "2026-09-29"])
        self.assertEqual(args.release_protocol, 4)
        self.assertEqual(default_policy("2026-09-28")["version"], 2)

    def test_registry_contains_declared_quantum_ai_and_probationary_sources(self) -> None:
        registry = load_registry()
        sources = {source["source_id"]: source for source in registry["sources"]}
        for source_id in ("aps-prx-x", "aps-prapplied", "aps-prresearch", "aps-prb", "aps-prd",
                          "aps-rmp", "nature-quantum", "nature-machine-learning", "jmlr",
                          "iop-qst", "ieee-tqe", "aaai", "arxiv-quant-ph", "arxiv-ai"):
            self.assertIn(source_id, sources)
        self.assertEqual(sources["iop-qst"]["tier"], "probationary")
        self.assertEqual(sources["jmlr"]["family"], "ai_peer_review")

    def test_one_bad_optional_source_is_isolated_but_missing_family_blocks(self) -> None:
        rows = [row("aps-pra"), row("jmlr"), row("iop-qst", "error")]
        gate = family_gate(rows)
        self.assertEqual(gate["status"], "pass")
        self.assertIn("|", markdown_health_table(rows))
        failed = family_gate([row("aps-pra"), row("iop-qst", "error")])
        self.assertEqual(failed["missing_families"], ["ai_peer_review"])

    def test_v4_audit_uses_family_gate_not_every_url(self) -> None:
        rows = [row("aps-pra"), row("jmlr"), row("science", "error")]
        ledger = {"academic_search_version": 4, "date_range": "2026-09-27", "rows": rows,
                  "family_gate": family_gate(rows)}
        venues, checked, hits, failures = academic_search_venues({"academic_search": ledger}, coverage_contract_version=3)
        self.assertEqual(failures, [])
        self.assertEqual(checked, 1)
        self.assertEqual(hits, 2)
        self.assertEqual(venues, {"aps-pra", "jmlr"})

    def test_coverage_contract_three_accepts_v4_and_rejects_missing_family(self) -> None:
        from test_release_protocol import daily_evidence
        day = "2026-09-27"
        record = daily_evidence(day)
        rows = [row("aps-pra"), row("jmlr"), row("science", "error")]
        ledger = {"academic_search_version": 4, "date_range": day, "rows": rows,
                  "family_gate": family_gate(rows)}
        record["academic_search"] = ledger
        record["academic_search_ref"] = evidence_digest(ledger)
        start = datetime.fromisoformat(day + "T00:00:00+08:00")
        end = datetime.fromisoformat("2026-09-28T00:00:00+08:00")
        self.assertEqual(validate_daily_evidence([record], start, end, contract_version=3), [])
        rows[1] = row("jmlr", "error")
        ledger["family_gate"] = family_gate(rows)
        record["academic_search_ref"] = evidence_digest(ledger)
        self.assertTrue(validate_daily_evidence([record], start, end, contract_version=3))


class V4CollectionIsolationTests(unittest.TestCase):
    @staticmethod
    def aps_feed() -> bytes:
        return b'''<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:prism="http://prismstandard.org/namespaces/basic/2.0/"><channel><title>Recent Articles in Physical Review A</title></channel><item><title>Quantum test</title><description>quantum method</description><dc:date>2026-09-28T10:00:00+00:00</dc:date><prism:doi>10.1103/example</prism:doi><prism:publicationName>Physical Review A</prism:publicationName></item></rdf:RDF>'''

    def test_bad_probationary_source_does_not_discard_healthy_families(self) -> None:
        plan = sweep.build_plan_v4(["quantum"], "2026-09-28")
        keep = {"aps-pra", "openreview", "iop-qst"}
        plan["rows"] = [row for row in plan["rows"] if row["source_id"] in keep]

        def fetch(url: str, _timeout: int, _attempts: int = 3):
            evidence = {"query_url": url, "final_url": url, "status_code": 200,
                        "retrieved_at": "2026-09-29T00:00:00Z", "response_hash": "a" * 64}
            if "pra.xml" in url:
                body = self.aps_feed()
                evidence["response_hash"] = hashlib.sha256(body).hexdigest()
                return evidence, body
            if "openreview" in url:
                body = json.dumps({"notes": [{"id": "x", "pdate": 1790550000000,
                                               "content": {"title": {"value": "Quantum learning"}}}]}).encode()
                evidence["response_hash"] = hashlib.sha256(body).hexdigest()
                return evidence, body
            return {**evidence, "status_code": 403, "error": "forbidden"}, b""

        with patch.object(sweep, "_request_source_with_retry", side_effect=fetch):
            result = sweep.fetch_evidence_v4(plan)
        self.assertEqual(result["family_gate"]["status"], "pass")
        states = {row["source_id"]: row["result"] for row in result["rows"]}
        self.assertEqual(states["iop-qst"], "blocked")
        self.assertEqual(states["aps-pra"], "checked")
        self.assertEqual(states["openreview"], "checked")

    def test_read_cap_plus_one_rejects_truncated_payload(self) -> None:
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def geturl(self): return "https://example.test/feed"
            def read(self, _size): return b"x" * (sweep.MAX_RESPONSE_BYTES + 1)
        with patch.object(sweep.urllib.request, "urlopen", return_value=Response()):
            evidence, body = sweep._request_evidence("https://example.test/feed", 1)
        self.assertEqual(body, b"")
        self.assertIn("response_too_large", evidence["error"])

    def test_html_200_does_not_invent_candidate_count_from_page_numbers(self) -> None:
        plan = sweep.build_plan_v4(["quantum"], "2026-09-28")
        source = next(row for row in load_registry()["sources"] if row["source_id"] == "quantum-journal")
        item = next(row for row in plan["rows"] if row["source_id"] == "quantum-journal")
        body = b"<html><body>2215 articles, 100 results</body></html>"
        evidence = {"query_url": source["url"], "final_url": source["url"], "status_code": 200,
                    "retrieved_at": "2026-09-29T00:00:00Z", "response_hash": hashlib.sha256(body).hexdigest()}
        with patch.object(sweep, "_request_source_with_retry", return_value=(evidence, body)):
            result = sweep._fetch_v4_row(item, source, ["quantum"], {"2026-09-28"}, 1)
        self.assertEqual(result["result"], "degraded")
        self.assertEqual(result["parse_status"], "unstructured")
        self.assertEqual(result["candidate_count"], 0)
        self.assertIn("no structured article identities", result["note"])

    def test_incomplete_read_is_explicit_and_never_parsed(self) -> None:
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_args): return None
            def geturl(self): return "https://example.test/feed"
            def read(self, _size): raise http.client.IncompleteRead(b"partial", 100)
        with patch.object(sweep.urllib.request, "urlopen", return_value=Response()):
            evidence, body = sweep._request_evidence("https://example.test/feed", 1)
        self.assertEqual(body, b"")
        self.assertEqual(evidence["error"], "incomplete_read")

    def test_feed_item_without_date_is_quarantined_without_losing_peers(self) -> None:
        body = b'''<rss><channel>
        <item><title>Missing date</title><link>https://example.test/a</link></item>
        <item><title>Dated quantum paper</title><pubDate>2026-09-28T00:00:00Z</pubDate><link>https://example.test/b</link></item>
        </channel></rss>'''
        items, quarantined = sweep._generic_feed_items(body)
        self.assertEqual(quarantined, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Dated quantum paper")

    def test_rolling_feed_candidates_are_limited_to_target_shanghai_day(self) -> None:
        plan = sweep.build_plan_v4(["quantum"], "2026-09-28")
        source = next(row for row in load_registry()["sources"] if row["source_id"] == "nature-quantum")
        item = next(row for row in plan["rows"] if row["source_id"] == "nature-quantum")
        body = b'''<rss><channel>
        <item><title>Quantum outside</title><pubDate>2026-09-27T00:00:00Z</pubDate></item>
        <item><title>Quantum inside</title><pubDate>2026-09-28T00:00:00Z</pubDate></item>
        </channel></rss>'''
        evidence = {"query_url": source["url"], "final_url": source["url"], "status_code": 200,
                    "retrieved_at": "2026-09-29T00:00:00Z",
                    "response_hash": hashlib.sha256(body).hexdigest()}
        with patch.object(sweep, "_request_source_with_retry", return_value=(evidence, body)):
            result = sweep._fetch_v4_row(item, source, ["quantum"], {"2026-09-28"}, 1)
        self.assertEqual(result["window_status"], "matched")
        self.assertEqual(result["candidate_count"], 1)
        self.assertEqual(result["matches"][0]["title"], "Quantum inside")

    def test_openreview_id_is_a_strong_identity(self) -> None:
        left = {"source_url": "https://openreview.net/forum?id=abc_123"}
        right = {"source_url": "https://api2.openreview.net/notes", "openreview_id": "abc_123"}
        self.assertTrue(same_paper(left, right))


if __name__ == "__main__":
    unittest.main()
