"""Cross-module admission, cached replay and authoring boundaries for the AI fallback."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import academic_venue_sweep as sweep
from academic_sources import family_gate, health_table, row_evidence_failures, sources_by_id
from audit_briefing_config import academic_search_venues
from collection_checkpoint import fingerprint
import orchestrate_daily as o
from plos_source import fetch_plos_row
from test_plos_source import MockRequests, document
from test_orchestrate_daily import fixtures, DAY, COVERED


def plos_row(docs=None):
    return fetch_plos_row({"source_id": "plos-ai", "coverage_window": COVERED},
                          sources_by_id()["plos-ai"], {COVERED}, 1, MockRequests(docs or []))


class SourceRepairIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.news = Path(temporary.name) / "news"
        self.paths = o.collection_paths(DAY, self.news)
        self.paths["academic"].parent.mkdir(parents=True)
        self.academic, self.social = fixtures(academic_count=2, social_count=15)
        self.academic["rows"][1] = plos_row()
        self.refresh_ledger()

    def refresh_ledger(self):
        self.academic["family_gate"] = family_gate(self.academic["rows"], coverage_window=COVERED)
        self.academic["source_health"] = health_table(self.academic["rows"], coverage_window=COVERED)

    def write(self):
        self.paths["academic"].write_text(json.dumps(self.academic), encoding="utf-8")
        self.paths["social"].write_text(json.dumps(self.social), encoding="utf-8")

    def test_proven_empty_fallback_restores_packet_but_never_approves_shortfall(self):
        self.assertEqual(self.academic["family_gate"]["status"], "pass")
        self.write()
        original = {key: self.paths[key].read_bytes() for key in ("academic", "social")}
        with patch.object(o, "NEWS_ROOT", self.news), patch.object(o, "inspect_network", side_effect=AssertionError("offline")):
            state = o._collect(DAY)
            self.assertEqual(state["phase"], "collection_ready")
            packet_bytes = self.paths["packet"].read_bytes()
            again = o._collect(DAY)
            self.assertEqual(again["phase"], "collection_ready")
            self.assertEqual(self.paths["packet"].read_bytes(), packet_bytes)
        packet = json.loads(packet_bytes)
        self.assertEqual(packet["semantic_review_status"], "not_reviewed")
        self.assertEqual(packet["candidate_counts"]["academic"]["total"], 2)
        health = next(row for row in packet["source_health"] if row["source_id"] == "plos-ai")
        self.assertFalse(health["window_evidence"]["publisher_day_coverage_complete"])
        self.assertEqual(health["window_evidence"]["source_scope"], "plos_indexed_ai_research_query")
        self.assertNotIn("verified_shortfall", packet_bytes.decode())
        self.assertFalse((self.news / DAY).exists())
        for key, body in original.items():
            self.assertEqual(self.paths[key].read_bytes(), body)

    def test_forged_plos_evidence_is_rejected_by_every_admission_layer(self):
        for attack in ("missing_pages", "invented_candidate", "narrow_query", "wrong_day"):
            with self.subTest(attack=attack):
                row = plos_row()
                if attack == "missing_pages":
                    row["plos_query_evidence"]["pages"] = []
                elif attack == "invented_candidate":
                    row["matches"] = [{"title": "fabricated", "published_at": COVERED + "T01:00:00Z"}]
                    row["candidate_count"] = 1
                elif attack == "narrow_query":
                    row["plos_query_evidence"]["pages"][0]["primary"]["transport"]["query_url"] += "&q=nothing"
                else:
                    row["coverage_window"] = "2026-09-30"
                self.assertTrue(row_evidence_failures(row, COVERED))
                self.academic["rows"][1] = row
                self.academic["family_gate"] = {"status": "pass"}
                self.assertEqual(family_gate(self.academic["rows"], coverage_window=COVERED)["status"], "fail")
                self.assertTrue(academic_search_venues({"academic_search": self.academic}, coverage_contract_version=3)[3])
                self.write()
                with self.assertRaises(o.CollectionError):
                    o.read_source(self.paths["academic"], "academic", DAY)

    def test_cached_plos_rows_are_replayed_before_reuse(self):
        checkpoint = self.news / "academic-checkpoint.json"

        def plan():
            value = sweep.build_plan_v4(["machine learning"], COVERED)
            value["rows"] = [r for r in value["rows"] if r["source_id"] == "plos-ai"]
            return value

        request = MockRequests([document()])
        with patch.object(sweep, "_request_source_with_retry", side_effect=request):
            first = sweep.fetch_evidence_v4(plan(), checkpoint=checkpoint)
        self.assertEqual(first["rows"][0]["candidate_count"], 1)
        with patch.object(sweep, "_request_source_with_retry", side_effect=AssertionError("cached must stay offline")):
            second = sweep.fetch_evidence_v4(plan(), checkpoint=checkpoint)
        self.assertEqual(second["rows"], first["rows"])
        damaged = json.loads(checkpoint.read_text())
        damaged["payload"]["rows"]["plos-ai"]["matches"][0]["title"] = "forged title"
        damaged["payload_sha256"] = fingerprint(damaged["payload"])
        checkpoint.write_text(json.dumps(damaged))
        retry = MockRequests([document()])
        with patch.object(sweep, "_request_source_with_retry", side_effect=retry):
            repaired = sweep.fetch_evidence_v4(plan(), checkpoint=checkpoint)
        self.assertEqual(len(retry.calls), 2)
        self.assertEqual(repaired["rows"][0]["matches"][0]["title"], document()["title"])

    def test_saved_health_table_cannot_upgrade_empty_index_evidence(self):
        self.academic["source_health"][1]["window_evidence"]["publisher_day_coverage_complete"] = True
        self.write()
        snapshot = o.source_snapshot(DAY, self.news)
        self.assertEqual(snapshot["academic"]["status"], "valid")
        packet = o.project_packet(DAY, self.news, snapshot)
        self.assertEqual(packet["family_gate"]["healthy_publishers"]["ai_peer_review"], ["PLOS"])
        health = next(row for row in packet["source_health"] if row["source_id"] == "plos-ai")
        self.assertFalse(health["window_evidence"]["publisher_day_coverage_complete"])


if __name__ == "__main__":
    unittest.main()
