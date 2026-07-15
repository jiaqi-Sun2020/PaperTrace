#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial regression tests for the transactional daily briefing pipeline."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from audit_briefing_config import audit
from briefing_contract import concept_identity, normalize_briefing_config
from briefing_to_feedback_html import render_html
from config_to_news_feedback import export_feedback
from daily_pipeline import cmd_finalize, cmd_run, verify_artifacts
from lean_html import apply_design_system
from news_delta import transform_config, upsert_index


def item(item_id: str = "N001", *, concept: str = "QSVT", url: str = "https://example.org/story") -> dict:
    return {
        "id": item_id,
        "story_id": item_id.lower(),
        "title": "Research item",
        "category": "AI product",
        "facts": "A source-grounded fact.",
        "judgment": "A separated judgment.",
        "source_title": "Official source",
        "source_url": url,
        "source_excerpt": "Evidence excerpt.",
        "evidence_level": "official source",
        "concepts": [concept],
    }


def config(items: list[dict] | None = None) -> dict:
    return {
        "briefing_title": "Test briefing",
        "date_range": "2026-07-10",
        "sections": [{"title": "Today", "items": items or [item()]}],
        "academic_delivery": {"required": False, "no_signal_reason": "non-academic unit-test fixture"},
        "analysis_language": "en",
    }


def with_fields(value: dict, **fields: object) -> dict:
    result = dict(value)
    result.update(fields)
    return result


class DailyPipelineTests(unittest.TestCase):
    def test_lossy_question_mark_text_is_blocking(self) -> None:
        broken = config([with_fields(item(), facts="中文事实???????")])
        with self.assertRaisesRegex(ValueError, "encoding-corrupted"):
            normalize_briefing_config(broken, require_source_url=True)

    def test_unicode_survives_html_render(self) -> None:
        raw = config([with_fields(item(), title="今日量子日报", facts="中文事实", judgment="中文判断", concepts=["量子纠错"])])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]})
        self.assertIn("今日量子日报", html)
        self.assertIn("中文事实", html)
        self.assertIn("charset=\"utf-8\"", html)
        self.assertNotIn("\ufffd", html)

    def test_unsafe_url_is_blocking(self) -> None:
        bad = config([item(url="javascript:alert(1)")])
        result = audit(bad)
        self.assertEqual(result["status"], "fail")

    def test_duplicate_concept_is_normalized_once_for_html_and_feedback(self) -> None:
        raw = config([with_fields(item(concept="QSVT"), concepts=["QSVT", "qsvt", "LUCI"])])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = apply_design_system(render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]}), "cosmic", "light")
        self.assertEqual(html.count('class="concept-chip"'), len(feedback["items"]))
        self.assertEqual({concept_identity(x["block_id"], x["concept"]) for x in feedback["items"]}, {"N001::qsvt", "N001::luci"})

    def test_html_initializes_all_unrated_feedback_without_legacy_top_level_items(self) -> None:
        canonical = normalize_briefing_config(config([with_fields(item(), concepts=["QSVT", "LUCI"])]), require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]})
        self.assertIn('"items":[{', html)
        self.assertIn("const BRIEFING_ITEMS", html)
        self.assertNotIn("const itemMap = new Map(CONFIG.items.map", html)
        self.assertIn("const INITIAL_BY_ID", html)
        self.assertIn("...(initial || {})", html)

    def test_required_academic_delivery_needs_formal_item_and_section(self) -> None:
        raw = config([item()])
        raw["academic_delivery"] = {"required": True, "minimum_items": 5}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("academic_delivery requires" in message for message in result["failures"]))

    def test_chinese_analysis_contract_blocks_english_facts_judgment_and_relevance(self) -> None:
        raw = config([with_fields(item(), relevance="English-only relevance")])
        raw["analysis_language"] = "zh-CN"
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("must include Chinese analysis text" in message for message in result["failures"]))

    def test_academic_item_is_preserved_in_dedicated_delta_section(self) -> None:
        raw = config([with_fields(item(url="https://journals.aps.org/prxquantum/abstract/10.1103/example"), category="Quantum research")])
        raw["academic_delivery"] = {"required": False, "no_signal_reason": "section routing test"}
        transformed, _, _ = transform_config(raw, [], __import__("datetime").date(2026, 7, 10), 7, "one-line")
        self.assertEqual(transformed["sections"][0]["title"], "Academic research and venue evidence")

    def test_existing_story_cannot_be_forced_new(self) -> None:
        raw = config([with_fields(item(), novelty="new")])
        prior = [{"story_id": "n001", "last_seen": "2026-07-09", "source_url": "https://example.org/story", "summary": "old"}]
        _, manifest, _ = transform_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7, "one-line")
        self.assertEqual(manifest["counts"]["new"], 0)
        self.assertEqual(manifest["counts"]["continuing"], 1)

    def test_corrupt_prior_summary_does_not_leak_into_html(self) -> None:
        raw = config([item()])
        prior = [{"story_id": "n001", "last_seen": "2026-07-09", "source_url": "https://example.org/story", "summary": "??? permutation tree?coined quantum walks ? color-ordered amplitudes ???????"}]
        transformed, _, _ = transform_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7, "one-line")
        facts = transformed["sections"][0]["items"][0]["facts"]
        self.assertIn("历史编码损坏", facts)
        self.assertNotIn("????????", facts)

    def test_index_upsert_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "story_index.jsonl"
            record = {"story_id": "same", "last_seen": "2026-07-10", "status": "new"}
            upsert_index(path, [record])
            upsert_index(path, [record])
            self.assertEqual(len(path.read_text(encoding="utf-8").splitlines()), 1)

    def test_staging_failure_does_not_touch_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(config(), ensure_ascii=False), encoding="utf-8")
            index_path = root / "story_index.jsonl"
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(index_path), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((root / "news" / "2026-07-10" / ".staging").iterdir())
            html_path = run_dir / "briefing_reader_2026-07-10.html"
            html_path.write_text("broken", encoding="utf-8")
            result = verify_artifacts(run_dir, strict=True)
            self.assertEqual(result["status"], "fail")
            self.assertFalse(index_path.exists())

    def test_run_verify_finalize_verify_is_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(config(), ensure_ascii=False), encoding="utf-8")
            index_path = root / "story_index.jsonl"
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(index_path), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((root / "news" / "2026-07-10" / ".staging").iterdir())
            self.assertEqual(verify_artifacts(run_dir, strict=True)["status"], "pass")
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(run_dir), strict=True)), 0)
            final_root = root / "news" / "2026-07-10"
            self.assertEqual(verify_artifacts(final_root, strict=True)["status"], "pass")
            self.assertEqual(len(index_path.read_text(encoding="utf-8").splitlines()), 1)

    def test_local_storage_contract_is_versioned_and_stale_entries_are_filtered(self) -> None:
        canonical = normalize_briefing_config(config(), require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = apply_design_system(render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]}), "cosmic", "light")
        self.assertIn("CONFIG.config_fingerprint", html)
        self.assertIn("const initialIds = new Set", html)
        self.assertIn("entry.annotation_kind === 'news_freeform'", html)

    def test_run_does_not_mutate_learner_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            profile = root / "knowledge_profile.json"
            profile.write_text('{"sentinel": true}', encoding="utf-8")
            raw = config()
            raw["profile_path"] = str(profile)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            before = profile.read_bytes()
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(root / "story_index.jsonl"), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            self.assertEqual(profile.read_bytes(), before)

    def test_venue_ledger_without_http_evidence_fails(self) -> None:
        academic = config([with_fields(item(url="https://arxiv.org/abs/2607.00001"), category="Quantum research", evidence_level="arXiv preprint")])
        academic["academic_search"] = {"required_venues": ["aps-prl"], "rows": [{"venue": "aps-prl", "result": "checked_no_hit"}]}
        result = audit(academic)
        self.assertEqual(result["status"], "fail")

    def test_evidenced_arxiv_only_coverage_is_blocked(self) -> None:
        venues = ["aps-prl", "aps-pra", "aps-prx", "nature", "science", "openreview-iclr", "cvf-cvpr", "pmlr-icml", "neurips", "acl", "quantum-journal", "arxiv"]
        rows = []
        for venue in venues:
            rows.append({
                "term": "quantum error suppression", "venue": venue, "result": "checked", "url": "",
                "evidence": {
                    "query_url": f"https://{venue}.example/search", "retrieved_at": "2026-07-10T00:00:00Z",
                    "status_code": 200, "final_url": f"https://{venue}.example/search", "response_hash": "a" * 64,
                    "result_count": 0,
                },
            })
        academic = config([with_fields(item(url="https://arxiv.org/abs/2607.00001"), category="Quantum research", evidence_level="arXiv preprint", venue_sweep_note="Official venue endpoints checked; no stronger venue page found.")])
        academic["academic_delivery"] = {"required": True, "minimum_items": 1}
        academic["academic_search"] = {"required_venues": venues, "topics": [{"term": "quantum error suppression", "checked_venues": venues, "primary_hits": [], "status": "evidenced"}], "rows": rows}
        result = audit(academic)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("non-arXiv formal venue paper" in message for message in result["failures"]))

    def test_required_daily_delivery_needs_distinct_social_section(self) -> None:
        raw = config([with_fields(item(url="https://journals.aps.org/prl/abstract/10.1103/example"), category="Quantum research")])
        raw["academic_delivery"] = {"required": True, "minimum_items": 1}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertIn("daily briefing requires a dedicated social news section", result["failures"])

    def test_required_daily_delivery_needs_social_candidate_pool_coverage(self) -> None:
        social = with_fields(item("S001", url="https://example.org/social"), published_at="2026-07-10", evidence_fingerprint="social-v1")
        raw = config([social])
        raw["sections"] = [
            {"title": "Academic research", "items": [with_fields(item(url="https://journals.aps.org/prl/abstract/10.1103/example"), category="Quantum research")]},
            {"title": "Social news", "items": [social]},
        ]
        raw["academic_delivery"] = {"required": True, "minimum_items": 1}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("social_candidate_pool" in message for message in result["failures"]))

    def test_normalizer_preserves_social_candidate_pool(self) -> None:
        raw = config()
        raw["social_candidate_pool"] = {"required_source_classes": ["ai_hot"], "checked_at": "2026-07-10T00:00:00Z"}
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(canonical["social_candidate_pool"], raw["social_candidate_pool"])

    def test_social_section_is_preserved_by_delta(self) -> None:
        raw = config([item()])
        raw["sections"] = [{"title": "Social news", "items": [item()]}]
        transformed, _, _ = transform_config(raw, [], __import__("datetime").date(2026, 7, 10), 7, "one-line")
        self.assertEqual(transformed["sections"][0]["title"], "社会新闻")

    def test_68_concepts_remain_unrated_and_interactive(self) -> None:
        concepts = [f"concept-{index:02d}" for index in range(68)]
        raw = config([with_fields(item(concept=concepts[0]), concepts=concepts)])
        canonical = normalize_briefing_config(raw, require_source_url=True)
        feedback = export_feedback(canonical, Path("config.json"), "unrated", "none")
        html = apply_design_system(render_html({**canonical, "default_status": "unrated", "initial_feedback_items": feedback["items"]}), "cosmic", "light")
        self.assertEqual(len(feedback["items"]), 68)
        self.assertTrue(all(entry["status"] == "unrated" for entry in feedback["items"]))
        self.assertEqual(html.count('class="concept-chip"'), 68)
        self.assertIn("Download JSON", html)
        self.assertIn('data-lean-bg-option="cosmic"', html)
        self.assertNotIn("lean-html-feedback-dock", html)


if __name__ == "__main__":
    unittest.main()
