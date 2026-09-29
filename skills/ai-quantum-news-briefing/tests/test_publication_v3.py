"""Adversarial checks for v3 destinations, paper identity and source-only rank signals."""

from argparse import Namespace
from datetime import date
import html
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import daily_pipeline
import orchestrate_daily
from paper_identity import paper_kind, same_paper
from news_delta import prior_for, replace_release_index, load_index
from rank_briefing_candidates import ALGORITHM_VERSION, SOURCE_ALGORITHM_VERSION, score_item, eligibility_failures, rank_briefing_config
from source_capture import capture_path, make_capture, public_https, validate_capture
from test_daily_pipeline import ranking_fixture
from test_release_protocol import daily_evidence


class PublicationV3Tests(unittest.TestCase):
    def test_historical_release_is_readable_but_not_mutable_from_cli(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp)
            (run_dir / "daily_pipeline_manifest_2026-07-10.json").write_text(
                json.dumps({"pipeline_version": 2, "date": "2026-07-10"}), encoding="utf-8")
            for command in ("review-template", "seal-review", "finalize"):
                with self.subTest(command=command), self.assertRaisesRegex(ValueError, "read-only"):
                    daily_pipeline.main([command, "--run-dir", str(run_dir)])

    def test_manifest_destination_and_components_are_assertions_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            news = Path(temp) / "news"
            day = "2026-07-10"
            run_id = day + "-abcdef123456"
            stage = news / day / ".staging" / run_id
            stage.mkdir(parents=True)
            manifest = {"pipeline_version": 3, "date": day, "run_id": run_id,
                        "output_dir": str(news / day),
                        "index_path": str(news / "_index" / "story_index.jsonl"),
                        "artifacts": {key: value.format(date=day) for key, value in daily_pipeline.ARTIFACT_NAMES.items()}}
            self.assertEqual(daily_pipeline.publication_layout(manifest, stage, news_root=news)[0], news / day)
            for key, bad in (("date", "../2026-07-10"), ("run_id", day + "-../escape"),
                             ("output_dir", str(Path(temp) / "outside")),
                             ("index_path", str(Path(temp) / "outside.jsonl"))):
                changed = dict(manifest, **{key: bad})
                with self.assertRaises(ValueError, msg=key):
                    daily_pipeline.publication_layout(changed, stage, news_root=news)
            changed = dict(manifest, artifacts={**manifest["artifacts"], "html": "../escape.html"})
            with self.assertRaises(ValueError):
                daily_pipeline.publication_layout(changed, stage, news_root=news)

    def test_doi_dataset_rejected_but_article_level_doi_can_be_classified(self) -> None:
        dataset = {"source_url": "https://doi.org/10.1234/data.1", "publication_type": "dataset"}
        article = {"source_url": "https://doi.org/10.1234/paper.1",
                   "publication_type": "journal-article",
                   "article_source_url": "https://www.nature.com/articles/example",
                   "source_capture": {"status_code": 200, "quoted_excerpt": "A paper claim",
                                      "final_url": "https://www.nature.com/articles/example"}}
        self.assertEqual(paper_kind(dataset), "")
        self.assertEqual(paper_kind(article), "nature")
        self.assertEqual(paper_kind({"source_url": "https://www.science.org/toc/science/0/0"}), "")
        self.assertEqual(paper_kind({"source_url": "https://www.nature.com/articles/example",
                                     "source_capture": {"status_code": 200,
                                                        "final_url": "https://www.nature.com/login"}}), "")
        self.assertIn("academic_source_in_social_pool", eligibility_failures(
            {"source_url": "https://www.science.org/toc/science/0/0"}, "social"))
        self.assertIn("not_a_paper_level_academic_source", eligibility_failures(dataset, "academic"))
        self.assertIn("academic_source_in_social_pool", eligibility_failures(dataset, "social"))
        self.assertTrue(same_paper(article, {"source_url": "https://www.nature.com/articles/example", "doi": "10.1234/paper.1"}))
        self.assertFalse(same_paper(article, {"title": "The same title", "doi": "10.1234/other"}))
        self.assertIsNone(prior_for(article, [{"title": "The same title", "source_url": "https://www.nature.com/articles/other",
                                               "doi": "10.1234/other"}]))
        self.assertTrue(same_paper({"source_url": "https://arxiv.org/abs/2607.01234"},
                                   {"source_url": "https://www.nature.com/articles/journal-version",
                                    "related_identifiers": {"arxiv_id": "2607.01234"},
                                    "source_capture": {"quoted_excerpt": "This article extends arXiv 2607.01234."}}))
        self.assertFalse(same_paper({"source_url": "https://arxiv.org/abs/2607.01234"},
                                    {"source_url": "https://www.nature.com/articles/unsupported",
                                     "related_identifiers": {"arxiv_id": "2607.01234"}}))

    def test_correction_replaces_only_old_release_index_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / "story_index.jsonl"
            old = {"story_id": "old", "last_seen": "2026-07-10", "briefing_path": "release-a"}
            neighbor = {"story_id": "neighbor", "last_seen": "2026-07-11", "briefing_path": "release-b"}
            index.write_text(json.dumps(old) + "\n" + json.dumps(neighbor) + "\n", encoding="utf-8")
            new = {"story_id": "new", "last_seen": "2026-07-10", "briefing_path": "release-a"}
            replace_release_index(index, Path("release-a"), [new], {("old", "2026-07-10")})
            self.assertEqual({row["story_id"] for row in load_index(index)}, {"new", "neighbor"})

    def test_capture_quote_and_source_only_score_resist_authored_prose(self) -> None:
        with self.assertRaises(ValueError):
            public_https("https://127.0.0.1/private")
        with self.assertRaises(ValueError):
            public_https("https://example.org/article?api_key=secret")
        item = {"id": "A001", "source_url": "https://www.nature.com/articles/example",
                "source_excerpt": "An observed effect supports the result", "published_at": "2026-07-10",
                "source_title": "A paper", "evidence_level": "formal journal"}
        body = b"<html><title>Source title</title><p>An observed effect supports the result</p></html>"
        capture = make_capture(item, item["source_url"], item["source_url"], 200, body,
                               "2026-07-10T08:00:00+00:00")
        self.assertEqual(validate_capture(item, capture), [])
        copied = dict(item, source_capture=capture)
        first = score_item(copied, "academic", date(2026, 7, 10), "new", SOURCE_ALGORITHM_VERSION)
        copied.update(facts="Revolutionary quantum algorithm 100%", judgment="proof data benchmark",
                      relevance="quantum error correction", ranking_signals={"relevance": 1})
        second = score_item(copied, "academic", date(2026, 7, 10), "new", SOURCE_ALGORITHM_VERSION)
        self.assertEqual(first["base_score"], second["base_score"])
        self.assertNotEqual(score_item(item, "academic", date(2026, 7, 10), "new", ALGORITHM_VERSION)["base_score"],
                            score_item(copied, "academic", date(2026, 7, 10), "new", ALGORITHM_VERSION)["base_score"])
        tampered = dict(capture, quoted_excerpt="A made-up source quote")
        self.assertTrue(validate_capture(item, tampered))

    def test_source_only_selection_does_not_change_when_draft_prose_changes(self) -> None:
        raw, prior = ranking_fixture()
        raw["ranking_policy"] = {**raw["ranking_policy"], "algorithm_version": SOURCE_ALGORITHM_VERSION}
        for section in raw["sections"]:
            for item in section["items"]:
                body = ("<title>Source " + item["id"] + "</title><p>"
                        + html.escape(item["source_excerpt"]) + "</p>").encode("utf-8")
                item["source_capture"] = make_capture(item, item["source_url"], item["source_url"],
                                                       200, body, "2026-07-10T08:00:00+08:00")
        first = rank_briefing_config(raw, prior, date(2026, 7, 10), 7)
        altered = json.loads(json.dumps(raw))
        for section in altered["sections"]:
            for item in section["items"]:
                item.update(facts="Quantum breakthrough 1000%", judgment="proof benchmark",
                            relevance="quantum error correction", ranking_signals={"relevance": 1})
        second = rank_briefing_config(altered, prior, date(2026, 7, 10), 7)
        self.assertEqual(first["ranking_manifest"]["selection_trace"],
                         second["ranking_manifest"]["selection_trace"])

    def test_v3_run_uses_isolated_news_root_and_requires_capture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            news = root / "news"
            raw, prior = ranking_fixture()
            raw["date_range"] = "2026-07-09"
            raw["collection_completed_at"] = "2026-07-10T08:00:00+08:00"
            raw["coverage_evidence"] = [daily_evidence("2026-07-09")]
            raw["academic_search"] = raw["coverage_evidence"][0]["academic_search"]
            raw["story_delivery"]["selection_basis"] = "explicit_override"
            raw["story_delivery"]["override_reason"] = "Fixture isolates publication paths from rank-1 pedagogy."
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            args = Namespace(config=str(candidate), date="2026-07-10", days=7,
                             continuing_mode="one-line", design_system="cosmic", background_mode="light",
                             release_protocol=3, coverage_start=None, coverage_end=None,
                             correction_reason=None, supersedes_hash=None)
            with patch.object(daily_pipeline, "NEWS_ROOT", news):
                disabled_academic = dict(raw, academic_delivery={"required": False})
                candidate.write_text(json.dumps(disabled_academic, ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "academic_delivery.required"):
                    daily_pipeline.cmd_run(args)
                disabled_ranking = dict(raw, ranking_policy={"enabled": False})
                candidate.write_text(json.dumps(disabled_ranking, ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "ranking cannot be disabled"):
                    daily_pipeline.cmd_run(args)
                candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                index = news / "_index" / "story_index.jsonl"
                index.parent.mkdir(parents=True, exist_ok=True)
                index.write_text("".join(json.dumps(row) + "\n" for row in prior), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "source captures"):
                    daily_pipeline.cmd_run(args)
                for section in raw["sections"]:
                    for item in section["items"]:
                        quote = str(item["source_excerpt"])
                        body = ("<title>Original source " + str(item["id"]) + "</title><p>"
                                + html.escape(quote) + "</p>").encode("utf-8")
                        record = make_capture(item, item["source_url"], item["source_url"], 200, body,
                                              "2026-07-10T08:00:00+08:00")
                        path = capture_path(news, "2026-07-09", str(item["id"]))
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(json.dumps(record), encoding="utf-8")
                self.assertEqual(daily_pipeline.cmd_run(args), 0)
                stage = next((news / "2026-07-10" / ".staging").iterdir())
                manifest = daily_pipeline.load_json(stage / "daily_pipeline_manifest_2026-07-10.json")
                self.assertEqual(manifest["pipeline_version"], 3)
                self.assertEqual(manifest["index_path"], str(news / "_index" / "story_index.jsonl"))
                self.assertEqual(manifest["artifacts"]["source_captures"], "source_captures_2026-07-10.json")
                manifest_path = stage / "daily_pipeline_manifest_2026-07-10.json"
                for key, bad in (("output_dir", str(root / "outside")),
                                 ("index_path", str(root / "outside.jsonl"))):
                    altered = dict(manifest, **{key: bad})
                    manifest_path.write_text(json.dumps(altered), encoding="utf-8")
                    self.assertEqual(daily_pipeline.verify_artifacts(stage, strict=True)["status"], "fail")
                    with self.assertRaises(ValueError):
                        daily_pipeline.cmd_finalize(Namespace(run_dir=str(stage), strict=True,
                                                             correction_reason=None, supersedes_hash=None,
                                                             require_remote=False))
                    self.assertFalse((root / "outside").exists())
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                result = daily_pipeline.verify_artifacts(stage, strict=False, structure_only=True)
                self.assertEqual(result["status"], "pass", result["failures"])
                self.assertEqual(daily_pipeline.verify_artifacts(stage, strict=True)["status"], "fail")
                from test_release_protocol import ReviewedReleaseTests
                ReviewedReleaseTests._write_reviews(SimpleNamespace(
                    stage=stage, date="2026-07-10",
                    manifest_path=stage / "daily_pipeline_manifest_2026-07-10.json"))
                self.assertEqual(daily_pipeline.cmd_seal_review(Namespace(run_dir=str(stage))), 0)
                self.assertEqual(daily_pipeline.verify_artifacts(stage, strict=True)["status"], "pass")
                with patch("publish_daily_to_oss.auto_publish_after_finalize", return_value={"status": "disabled"}):
                    result_code = daily_pipeline.cmd_finalize(Namespace(
                        run_dir=str(stage), strict=True, require_remote=True,
                        correction_reason=None, supersedes_hash=None))
                self.assertEqual(result_code, 2)
                self.assertEqual(daily_pipeline.verify_artifacts(news / "2026-07-10", strict=True)["status"], "pass")
                final_html = news / "2026-07-10" / "briefing_reader_2026-07-10.html"
                original_html_hash = daily_pipeline.sha256_file(final_html)
                original_index_hash = daily_pipeline.sha256_file(index)
                selected = daily_pipeline.load_json(
                    news / "2026-07-10" / "news_feedback_config_delta_2026-07-10.json")["sections"][0]["items"][0]
                for section in raw["sections"]:
                    for item in section["items"]:
                        if item["story_id"] == selected["story_id"]:
                            item["facts"] = item["facts"] + " A revised, reviewed detail."
                candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                args.correction_reason = "Correct a source-reviewed item while preserving other releases."
                args.supersedes_hash = original_html_hash
                self.assertEqual(daily_pipeline.cmd_run(args), 0)
                corrected_stage = next(path for path in (news / "2026-07-10" / ".staging").iterdir()
                                       if path != stage)
                ReviewedReleaseTests._write_reviews(SimpleNamespace(
                    stage=corrected_stage, date="2026-07-10",
                    manifest_path=corrected_stage / "daily_pipeline_manifest_2026-07-10.json"))
                self.assertEqual(daily_pipeline.cmd_seal_review(Namespace(run_dir=str(corrected_stage))), 0)
                self.assertEqual(daily_pipeline.verify_artifacts(corrected_stage, strict=True)["status"], "pass")
                with patch("news_delta.atomic_write_text", side_effect=OSError("injected index write failure")):
                    with self.assertRaises(OSError):
                        daily_pipeline.cmd_finalize(Namespace(
                            run_dir=str(corrected_stage), strict=True, require_remote=False,
                            correction_reason=args.correction_reason, supersedes_hash=args.supersedes_hash))
                self.assertEqual(daily_pipeline.sha256_file(final_html), original_html_hash)
                self.assertEqual(daily_pipeline.sha256_file(index), original_index_hash)
                self.assertEqual(daily_pipeline.verify_artifacts(news / "2026-07-10", strict=True)["status"], "pass")
                with patch("publish_daily_to_oss.auto_publish_after_finalize", return_value={"status": "disabled"}):
                    self.assertEqual(daily_pipeline.cmd_finalize(Namespace(
                        run_dir=str(corrected_stage), strict=True, require_remote=False,
                        correction_reason=args.correction_reason, supersedes_hash=args.supersedes_hash)), 0)
                self.assertNotEqual(daily_pipeline.sha256_file(final_html), original_html_hash)
                self.assertEqual(daily_pipeline.verify_artifacts(news / "2026-07-10", strict=True)["status"], "pass")
                final_config_path = news / "2026-07-10" / "news_feedback_config_delta_2026-07-10.json"
                final_manifest_path = news / "2026-07-10" / "daily_pipeline_manifest_2026-07-10.json"
                final_config = daily_pipeline.load_json(final_config_path)
                final_config["academic_delivery"]["required"] = False
                final_config_path.write_text(json.dumps(final_config, ensure_ascii=False), encoding="utf-8")
                final_manifest = daily_pipeline.load_json(final_manifest_path)
                final_manifest["artifact_sha256"]["delta_config"] = daily_pipeline.sha256_file(final_config_path)
                final_manifest_path.write_text(json.dumps(final_manifest), encoding="utf-8")
                failures = daily_pipeline.verify_artifacts(news / "2026-07-10", strict=True)["failures"]
                self.assertTrue(any("academic_delivery.required=true" in issue for issue in failures))

    def test_orchestrator_reports_artifacts_without_approving_review_or_claiming_remote(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            news = Path(temp) / "news"
            self.assertEqual(orchestrate_daily.inspect("2026-07-10", news_root=news)["phase"], "collection_pending")
            candidate = news / "_collection" / "2026-07-10" / "candidate_2026-07-10.json"
            candidate.parent.mkdir(parents=True)
            candidate.write_text(json.dumps({"sections": [{"items": [{"id": "A001"}]}]}), encoding="utf-8")
            state = orchestrate_daily.inspect("2026-07-10", news_root=news)
            self.assertEqual(state["phase"], "candidate_waiting_capture")
            self.assertEqual(state["remote_status"], "not_checked")
            stage = news / "2026-07-10" / ".staging" / "2026-07-10-abcdef123456"
            stage.mkdir(parents=True)
            with patch.object(orchestrate_daily, "verify_artifacts", side_effect=[
                {"status": "pass", "failures": []}, {"status": "fail", "failures": ["review pending"]}]):
                state = orchestrate_daily.inspect("2026-07-10", news_root=news)
            self.assertEqual(state["phase"], "review_pending")
            self.assertIn("semantic approval is never automatic", state["next_action"])
