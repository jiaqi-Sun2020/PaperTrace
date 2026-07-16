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

from audit_briefing_config import audit, audit_ranking_delivery
from briefing_contract import concept_identity, normalize_briefing_config
from briefing_to_feedback_html import render_html
from config_to_news_feedback import export_feedback
from daily_pipeline import cmd_finalize, cmd_run, verify_artifacts
from lean_html import apply_design_system
from news_delta import transform_config, upsert_index
from rank_briefing_candidates import DEFAULT_RANKING_POLICY, rank_briefing_config


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


def ranked_candidate(
    item_id: str,
    *,
    url: str,
    source_class: str,
    organization: str,
    topic: str,
    published_at: str = "2026-07-10",
) -> dict:
    return {
        "id": item_id,
        "story_id": item_id.lower(),
        "title": f"Ranked candidate {item_id}",
        "category": topic,
        "facts": "Verified release with 42 measured results and a concrete deployment.",
        "judgment": "The evidence is specific enough to compare with prior work.",
        "relevance": "Relevant to quantum dynamics, error correction, or agent infrastructure.",
        "source_title": f"Source {item_id}",
        "source_url": url,
        "source_excerpt": "Primary evidence excerpt with quantitative details.",
        "evidence_level": "peer-reviewed venue" if "arxiv.org" not in url else "arXiv preprint",
        "evidence_fingerprint": f"fingerprint-{item_id.lower()}",
        "published_at": published_at,
        "venue_sweep_note": "Official academic venues were checked; this item remains labeled as an arXiv preprint." if "arxiv.org" in url else "",
        "source_class": source_class,
        "organization": organization,
        "topic": topic,
        "corroborating_source_count": 2,
        "concepts": [topic, item_id],
    }


def ranking_fixture() -> tuple[dict, list[dict]]:
    academic: list[dict] = []
    for index in range(1, 11):
        if index <= 3:
            url = f"https://www.nature.com/articles/ranking-{index}"
            source_class = "formal_academic"
        else:
            url = f"https://arxiv.org/abs/2607.{14000 + index}"
            source_class = "arxiv_preprint"
        academic.append(
            ranked_candidate(
                f"A{index:03d}",
                url=url,
                source_class=source_class,
                organization="",
                topic=f"academic-topic-{index % 5}",
            )
        )
    social_classes = ["reputable_media"] * 4 + ["official_primary"] * 4 + ["official_company_social"] * 6
    social = [
        ranked_candidate(
            f"S{index:03d}",
            url=f"https://social-{index}.example.org/story",
            source_class=source_class,
            organization=f"organization-{index}",
            topic=f"social-topic-{index % 6}",
        )
        for index, source_class in enumerate(social_classes, start=1)
    ]
    raw = {
        "briefing_title": "Ranked daily briefing",
        "date_range": "2026-07-10",
        "sections": [
            {"title": "Academic research", "items": academic},
            {"title": "Social news", "items": social},
        ],
        "academic_delivery": {
            "required": True,
            "minimum_items": 7,
            "target_items": 8,
            "maximum_items": 8,
            "minimum_new_items": 4,
            "maximum_new_items": 6,
            "minimum_non_arxiv_items": 2,
            "maximum_continuing_items": 3,
        },
        "social_delivery": {
            "minimum_items": 10,
            "target_items": 12,
            "maximum_items": 14,
            "minimum_new_or_material_update": 7,
            "maximum_continuing_items": 3,
            "minimum_reputable_media_items": 3,
            "minimum_primary_official_items": 3,
            "minimum_source_classes": 3,
            "maximum_items_per_organization": 2,
            "maximum_items_per_topic": 3,
        },
        "ranking_policy": DEFAULT_RANKING_POLICY,
        "analysis_language": "en",
    }
    venues = ["aps-prl", "aps-pra", "aps-prx", "nature", "science", "openreview-iclr", "cvf-cvpr", "pmlr-icml", "neurips", "acl", "quantum-journal", "arxiv"]
    raw["academic_search"] = {
        "required_venues": venues,
        "topics": [{"term": "quantum ranking test", "checked_venues": venues, "primary_hits": [{"venue": "nature", "url": academic[0]["source_url"]}], "status": "evidenced"}],
        "rows": [
            {
                "term": "quantum ranking test",
                "venue": venue,
                "result": "checked",
                "url": academic[0]["source_url"] if venue == "nature" else "",
                "evidence": {
                    "query_url": f"https://{venue}.example.org/search",
                    "retrieved_at": "2026-07-10T00:00:00Z",
                    "status_code": 200,
                    "final_url": f"https://{venue}.example.org/search",
                    "response_hash": (venue.replace("-", "") + "0" * 64)[:64],
                },
            }
            for venue in venues
        ],
    }
    raw["social_candidate_pool"] = {
        "required_source_classes": ["ai_hot", "reputable_media", "official_company_social", "executive_social"],
        "checked_at": "2026-07-10T00:00:00Z",
        "ai_hot_artifact": "aihot_candidates_2026-07-10.json",
    }
    prior = [
        {
            "story_id": academic[index]["story_id"],
            "last_seen": "2026-07-09",
            "source_url": academic[index]["source_url"],
            "summary": academic[index]["facts"],
            "evidence_fingerprint": academic[index]["evidence_fingerprint"],
        }
        for index in (8, 9)
    ]
    return raw, prior


class DailyPipelineTests(unittest.TestCase):
    def test_ranker_selects_eight_academic_and_twelve_social_items_deterministically(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        repeated = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        self.assertEqual(ranked["ranking_manifest"], repeated["ranking_manifest"])
        self.assertEqual(ranked["ranking_manifest"]["selected_counts"], {"academic": 8, "social": 12})
        self.assertEqual([len(section["items"]) for section in ranked["sections"]], [8, 12])
        self.assertEqual(audit_ranking_delivery(ranked), [])

    def test_strict_audit_rejects_attempts_to_weaken_delivery_quotas(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ranked["delta_policy"] = {"mode": "delta_first"}
        ranked["academic_delivery"].update({
            "minimum_items": 1,
            "minimum_new_items": 1,
            "minimum_non_arxiv_items": 1,
            "maximum_continuing_items": 9,
        })
        ranked["social_delivery"].update({
            "minimum_items": 1,
            "maximum_items": 99,
            "minimum_new_or_material_update": 1,
            "maximum_items_per_organization": 99,
        })
        result = audit(ranked)
        self.assertEqual(result["status"], "fail")
        for expected in (
            "academic_delivery.minimum_items must be at least 7",
            "academic_delivery.minimum_new_items must be at least 4",
            "academic_delivery.minimum_non_arxiv_items must be at least 2",
            "academic_delivery.maximum_continuing_items must be at most 3",
            "social_delivery.minimum_items must be at least 10",
            "social_delivery publication range must stay within 10-14 items",
            "social_delivery.minimum_new_or_material_update must be at least 7",
            "social_delivery.maximum_items_per_organization must be at most 2",
        ):
            self.assertIn(expected, result["failures"])

    def test_ranker_rejects_candidate_only_evidence_before_scoring_selection(self) -> None:
        raw, prior = ranking_fixture()
        raw["sections"][1]["items"][0]["evidence_level"] = "AI HOT API candidate"
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        ledger = ranked["ranking_manifest"]["candidate_ledger"]
        rejected = next(row for row in ledger if row["story_id"] == "s001")
        self.assertFalse(rejected["eligible"])
        self.assertFalse(rejected["selected"])
        self.assertIn("candidate_or_unverified_evidence", rejected["exclusion_reasons"])

    def test_ranker_deduplicates_story_identity_before_selection(self) -> None:
        raw, prior = ranking_fixture()
        duplicate = dict(raw["sections"][1]["items"][0])
        duplicate["id"] = "S999"
        duplicate["evidence_fingerprint"] = "duplicate-fingerprint"
        raw["sections"][1]["items"].append(duplicate)
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        duplicates = [
            row for row in ranked["ranking_manifest"]["candidate_ledger"]
            if row["story_id"] == duplicate["story_id"]
        ]
        self.assertEqual(sum(row["selected"] for row in duplicates), 1)
        self.assertTrue(any("duplicate_candidate" in row["exclusion_reasons"] for row in duplicates))

    def test_ranked_daily_pipeline_passes_run_verify_finalize_verify(self) -> None:
        raw, prior = ranking_fixture()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "candidate.json"
            input_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            index_path = root / "story_index.jsonl"
            index_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in prior), encoding="utf-8")
            args = Namespace(
                config=str(input_path), output_dir=str(root / "news" / "2026-07-10"), index=str(index_path), date="2026-07-10",
                days=7, continuing_mode="one-line", design_system="cosmic", background_mode="light",
            )
            self.assertEqual(cmd_run(args), 0)
            run_dir = next((root / "news" / "2026-07-10" / ".staging").iterdir())
            staged_verification = verify_artifacts(run_dir, strict=True)
            self.assertEqual(staged_verification["status"], "pass", json.dumps(staged_verification, ensure_ascii=False, indent=2))
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(run_dir), strict=True)), 0)
            self.assertEqual(verify_artifacts(root / "news" / "2026-07-10", strict=True)["status"], "pass")

    def test_normalizer_preserves_ranking_evidence(self) -> None:
        raw, prior = ranking_fixture()
        ranked = rank_briefing_config(raw, prior, __import__("datetime").date(2026, 7, 10), 7)
        canonical = normalize_briefing_config(ranked, require_source_url=True)
        self.assertEqual(canonical["ranking_policy"]["algorithm_version"], "news-ranker-v1")
        self.assertEqual(canonical["ranking_manifest"]["selected_counts"]["academic"], 8)
        self.assertEqual(canonical["sections"][0]["items"][0]["ranking"]["rank"], 1)

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

    def test_final_delta_cannot_weaken_four_to_six_new_academic_floor(self) -> None:
        raw = config([
            with_fields(item(f"A{index:03d}", url=f"https://arxiv.org/abs/2607.00{index:03d}"), category="Quantum research", novelty="continuing")
            for index in range(1, 6)
        ])
        raw["sections"] = [{"title": "Academic research and venue evidence", "items": raw["sections"][0]["items"]}]
        raw["academic_delivery"] = {"required": True, "minimum_items": 5, "minimum_new_items": 3, "maximum_new_items": 4}
        raw["delta_policy"] = {"mode": "delta_first"}
        result = audit(raw)
        self.assertEqual(result["status"], "fail")
        self.assertIn("academic_delivery.minimum_items must be at least 7", result["failures"])
        self.assertIn("academic_delivery.minimum_new_items must be at least 4", result["failures"])
        self.assertTrue(any("4-4 new academic paper items; found 0" in message for message in result["failures"]))

    def test_normalizer_preserves_delta_policy(self) -> None:
        raw = config()
        raw["delta_policy"] = {"mode": "delta_first", "continuing_mode": "one-line"}
        canonical = normalize_briefing_config(raw, require_source_url=True)
        self.assertEqual(canonical["delta_policy"], raw["delta_policy"])

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

    def test_social_research_announcement_is_not_counted_as_academic_paper(self) -> None:
        social = with_fields(
            item("S001", url="https://alignment.anthropic.com/2026/example"),
            title="Anthropic 发布智能体安全研究",
            category="AI 安全研究与社会影响",
            evidence_level="official research publication",
            source_title="Anthropic Alignment Science Blog - Research update",
        )
        raw = config([social])
        raw["sections"] = [{"title": "社会新闻", "items": [social]}]
        result = audit(raw)
        self.assertEqual(result["academic_items"], 0)

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
