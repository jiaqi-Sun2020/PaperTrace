"""Offline, adversarial checks for dated expansion and verified shortfall."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from argparse import Namespace
from datetime import date
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from academic_venue_sweep import EXPANDED_VENUES, VENUES, build_plan
from audit_briefing_config import audit
from daily_coverage_evidence import evidence_digest
from daily_pipeline import cmd_run, sha256_file, verify_artifacts
from delivery_expansion import publication_relation, validate_policy
from rank_briefing_candidates import eligibility_failures, rank_briefing_config
from publish_daily_to_oss import PublishError, verified_release
from test_daily_pipeline import ranking_fixture
from test_release_protocol import daily_evidence


DAY = "2026-09-27"
STAMP = "2026-09-28T02:00:00+08:00"


def _row(venue: str, domain: str, *, status: int = 200) -> dict:
    url = f"https://{domain.split('/')[0]}/search?q=quantum"
    return {"venue": venue, "term": "quantum", "result": "checked" if status == 200 else "blocked",
            "evidence": {"query_url": url, "final_url": url, "status_code": status,
                         "response_hash": "a" * 64, "retrieved_at": STAMP}}


def shortfall_fixture() -> tuple[dict, list[dict]]:
    raw, prior = ranking_fixture()
    raw["date_range"] = DAY
    raw["sections"][0]["items"] = raw["sections"][0]["items"][:2]
    raw["sections"][1]["items"] = raw["sections"][1]["items"][:3]
    raw["sections"][0]["items"][0]["published_at"] = DAY
    raw["sections"][0]["items"][1]["published_at"] = "2026-09-20"
    for row, stamp in zip(raw["sections"][1]["items"],
                          ("2026-09-27T10:00:00+08:00", "2026-09-26T09:00:00+08:00",
                           "2026-09-25T01:00:00+08:00")):
        row["published_at"] = stamp
    raw["social_candidate_pool"]["checked_at"] = STAMP
    daily = daily_evidence(DAY)
    daily["academic_search"]["expanded_rows"] = [_row(venue.key, venue.domain)
                                                    for venue in EXPANDED_VENUES]
    daily["academic_search_ref"] = evidence_digest(daily["academic_search"])
    raw["academic_search"] = daily["academic_search"]
    raw["coverage_evidence"] = [daily]
    raw["collection_completed_at"] = STAMP
    lookback = {"academic_search_version": 3, "date_range": "2026-09-14..2026-09-27",
                "rows": [_row(venue.key, venue.domain, status=403 if venue.key == "science" else 200)
                         for venue in VENUES]}
    social = []
    for past_day in ("2026-09-25", "2026-09-26"):
        record = daily_evidence(past_day)["social_search"]
        social.append({"date": past_day, "social_search": record,
                       "social_search_ref": evidence_digest(record)})
    raw["delivery_expansion"] = {
        "version": 1, "mode": "verified_shortfall", "coverage_date": DAY,
        "academic_window_start": "2026-09-14", "social_window_start": "2026-09-25",
        "academic_lookback_search": lookback, "academic_lookback_ref": evidence_digest(lookback),
        "social_lookback": social,
        "shortfall_reason": "逐日及扩展窗口检索后，合格且未在历史日报出现的候选不足正常篇数。",
    }
    return raw, prior


class DeliveryExpansionTests(unittest.TestCase):
    def test_expanded_venues_remain_optional_to_daily_coverage(self) -> None:
        plan = build_plan(["quantum"], DAY, include_arxiv=True,
                          mark_checked_no_hit=False, include_expanded=True)
        self.assertEqual(len(plan["expanded_rows"]), 8)
        self.assertEqual(len(plan["rows"]), 12)
        self.assertEqual(len(plan["required_venues"]), 12)
        self.assertFalse(set(row["venue"] for row in plan["expanded_rows"]) & set(plan["required_venues"]))

    def test_window_uses_original_time_and_shanghai_half_open_boundary(self) -> None:
        covered = date.fromisoformat(DAY)
        self.assertEqual(publication_relation({"published_at": "2026-09-28T00:00:00+08:00"}, "social", covered), None)
        self.assertEqual(publication_relation({"published_at": "2026-09-25T00:00:00+08:00"}, "social", covered), "recent_context")
        self.assertEqual(publication_relation({"published_at": "2026-09-27T16:00:00Z"}, "social", covered), None)
        self.assertIsNone(publication_relation({"published_at": "2026-09-27"}, "social", covered))
        self.assertEqual(publication_relation({"published_at": "2026-09-14"}, "academic", covered), "recent_context")
        self.assertIsNone(publication_relation({"published_at": "2026-09-13"}, "academic", covered))

    def test_shortfall_requires_both_expansion_stages_and_hashes(self) -> None:
        raw, _ = shortfall_fixture()
        self.assertEqual(validate_policy(raw), [])
        missing = copy.deepcopy(raw)
        missing["academic_search"]["expanded_rows"].pop()
        self.assertIn("optional venue attempt", " ".join(validate_policy(missing)))
        wrong_hash = copy.deepcopy(raw)
        wrong_hash["delivery_expansion"]["social_lookback"][0]["social_search_ref"] = "sha256:" + "0" * 64
        self.assertIn("digest", " ".join(validate_policy(wrong_hash)))
        rate_limited = copy.deepcopy(raw)
        rate_limited["delivery_expansion"]["academic_lookback_search"]["rows"][-1]["evidence"]["status_code"] = 429
        rate_limited["delivery_expansion"]["academic_lookback_ref"] = evidence_digest(
            rate_limited["delivery_expansion"]["academic_lookback_search"])
        self.assertIn("arxiv", " ".join(validate_policy(rate_limited)))
        missing_social = copy.deepcopy(raw)
        prior_day = missing_social["delivery_expansion"]["social_lookback"][0]
        prior_day["social_search"]["source_class_evidence"] = []
        prior_day["social_search_ref"] = evidence_digest(prior_day["social_search"])
        self.assertIn("social source-class", " ".join(validate_policy(missing_social)))

    def test_ranked_shortfall_keeps_dates_and_rejects_prior_publications(self) -> None:
        raw, prior = shortfall_fixture()
        ranked = rank_briefing_config(raw, prior, date(2026, 9, 28), 7)
        self.assertEqual(ranked["ranking_manifest"]["selected_counts"], {"academic": 2, "social": 3})
        self.assertEqual(ranked["ranking_manifest"]["shortfall_evidence"]["recent_context_counts"],
                         {"academic": 1, "social": 2})
        self.assertEqual(audit(ranked, coverage_contract_version=2)["failures"], [])
        self.assertIn("如实少发", ranked["coverage_notice"])
        self.assertIn("指定日首发分别为 1 篇和 1 条", ranked["coverage_notice"])
        prior.append({"story_id": "s001", "source_url": raw["sections"][1]["items"][0]["source_url"]})
        reranked = rank_briefing_config(raw, prior, date(2026, 9, 28), 7)
        rejected = next(row for row in reranked["ranking_manifest"]["candidate_ledger"]
                        if row["story_id"] == "s001")
        self.assertIn("previously_published", rejected["exclusion_reasons"])

    def test_listing_page_and_bad_url_cannot_pad_shortfall(self) -> None:
        raw, _ = shortfall_fixture()
        listing = raw["sections"][0]["items"][0]
        listing["source_url"] = "https://eccv.ecva.net/Conferences/2026/AcceptedPapers"
        self.assertIn("academic_listing_is_not_a_paper", eligibility_failures(listing, "academic"))
        listing["source_url"] = "https://[invalid"
        with self.assertRaisesRegex(ValueError, "IPv6"):
            rank_briefing_config(raw, [], date(2026, 9, 28), 7)

    def test_resurfaced_old_social_item_cannot_enter_shortfall(self) -> None:
        raw, _ = shortfall_fixture()
        resurfaced = raw["sections"][1]["items"][0]
        resurfaced["published_at"] = "2026-09-21T12:00:00+08:00"
        ranked = rank_briefing_config(raw, [], date(2026, 9, 28), 7)
        rejected = next(row for row in ranked["ranking_manifest"]["candidate_ledger"]
                        if row["story_id"] == resurfaced["story_id"])
        self.assertIn("outside_verified_lookback_or_ambiguous_publication_time", rejected["exclusion_reasons"])

    def test_prior_doi_with_different_url_cannot_pad_academic_count(self) -> None:
        raw, _ = shortfall_fixture()
        paper = raw["sections"][0]["items"][0]
        paper["doi"] = "10.1234/same-paper"
        prior = [{"story_id": "different-id", "source_url": "https://doi.org/10.1234/same-paper",
                  "doi": "10.1234/same-paper"}]
        ranked = rank_briefing_config(raw, prior, date(2026, 9, 28), 7)
        rejected = next(row for row in ranked["ranking_manifest"]["candidate_ledger"]
                        if row["story_id"] == paper["story_id"])
        self.assertIn("previously_published", rejected["exclusion_reasons"])

    def test_selected_item_cannot_relabel_old_date_as_same_day(self) -> None:
        raw, prior = shortfall_fixture()
        ranked = rank_briefing_config(raw, prior, date(2026, 9, 28), 7)
        recent = next(item for section in ranked["sections"] for item in section["items"]
                      if item.get("time_relation") == "recent_context")
        recent["time_relation"] = "covered_day"
        self.assertIn("time relation disagrees", " ".join(
            audit(ranked, coverage_contract_version=2)["failures"]))

    def test_run_fails_before_staging_if_shortfall_has_no_source_attempt(self) -> None:
        raw, _ = shortfall_fixture()
        raw["academic_search"]["expanded_rows"] = []
        raw["coverage_evidence"][0]["academic_search_ref"] = evidence_digest(raw["academic_search"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            output = root / "news" / "2026-09-28"
            args = Namespace(config=str(candidate), output_dir=str(output), index=str(root / "story_index.jsonl"),
                             date="2026-09-28", days=7, continuing_mode="one-line",
                             design_system="cosmic", background_mode="light", release_protocol=2,
                             coverage_start=None, coverage_end=None)
            with self.assertRaisesRegex(ValueError, "optional venue attempt"):
                cmd_run(args)
            self.assertFalse((output / ".staging").exists())

    def test_shortfall_stage_disclosure_and_manifest_binding(self) -> None:
        raw, _ = shortfall_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            output = root / "news" / "2026-09-28"
            args = Namespace(config=str(candidate), output_dir=str(output), index=str(root / "story_index.jsonl"),
                             date="2026-09-28", days=7, continuing_mode="one-line",
                             design_system="cosmic", background_mode="light", release_protocol=2,
                             coverage_start=None, coverage_end=None)
            self.assertEqual(cmd_run(args), 0)
            stage = next((output / ".staging").iterdir())
            self.assertEqual(verify_artifacts(stage, strict=True, structure_only=True)["failures"], [])
            html = (stage / "briefing_reader_2026-09-28.html").read_text(encoding="utf-8")
            markdown = (stage / "daily_briefing_2026-09-28.md").read_text(encoding="utf-8")
            self.assertIn("近期回看", html)
            self.assertIn("近期回看", markdown)
            self.assertIn("2 篇学术、3 条社会内容", html)
            self.assertIn("2 篇学术、3 条社会内容", markdown)
            manifest_path = stage / "daily_pipeline_manifest_2026-09-28.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            html_path = stage / "briefing_reader_2026-09-28.html"
            html_path.write_text(html.replace("近期回看", "当日新发"), encoding="utf-8")
            manifest["artifact_sha256"]["html"] = sha256_file(html_path)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertIn("coverage notice differs", " ".join(
                verify_artifacts(stage, strict=True, structure_only=True)["failures"]))
            html_path.write_text(html, encoding="utf-8")
            manifest["artifact_sha256"]["html"] = sha256_file(html_path)
            manifest["delivery_expansion_ref"] = "sha256:" + "0" * 64
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            self.assertIn("delivery expansion differs", " ".join(
                verify_artifacts(stage, strict=True, structure_only=True)["failures"]))
            with self.assertRaisesRegex(PublishError, "strict verification"):
                verified_release(stage)


if __name__ == "__main__":
    unittest.main()
