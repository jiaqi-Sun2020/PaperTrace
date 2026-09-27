"""Fault-injection checks for the reviewed daily release protocol."""

from argparse import Namespace
from datetime import datetime
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
ALLEGORY = Path(__file__).resolve().parents[2] / "allegory-teach" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ALLEGORY))

from daily_pipeline import cmd_finalize, cmd_review_template, cmd_run, cmd_seal_review, cmd_status, sha256_file, verify_artifacts
from release_audit import REVIEW_NAMES, claim_digest, content_digest, selected_items
from release_lock import release_lock
from review_evidence import ROUND_MATERIALS, TASK_CARD_KEYS, story_digest
from test_daily_pipeline import config


class ReviewedReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.date = "2026-07-10"
        raw = config()
        raw["date_range"] = "2026-07-09"
        raw["collection_completed_at"] = "2026-07-10T08:00:00+08:00"
        candidate = self.root / "candidate.json"
        candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        self.output = self.root / "news" / self.date
        self.index = self.root / "news" / "_index" / "story_index.jsonl"
        args = Namespace(config=str(candidate), output_dir=str(self.output), index=str(self.index),
                         date=self.date, days=7, continuing_mode="one-line", design_system="cosmic",
                         background_mode="light", release_protocol=2, coverage_start=None, coverage_end=None)
        self.assertEqual(cmd_run(args), 0)
        self.stage = next((self.output / ".staging").iterdir())
        self.manifest_path = self.stage / f"daily_pipeline_manifest_{self.date}.json"

    def _write_reviews(self) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        config_data = json.loads((self.stage / manifest["artifacts"]["delta_config"]).read_text(encoding="utf-8"))
        story = config_data["opening_story"]
        quote = story["paragraphs"][0]
        story_review = {
            "story_sha256": story_digest(story), "review_protocol_version": 2,
            "review_method": "self",
            "task_card": {key: "Source-grounded task and causal constraint." for key in TASK_CARD_KEYS},
            "rounds": [
                {"id": key, "judgment": "pass", "reviewed_text": quote,
                 "reason": "The stated action and result agree in this case.",
                 "source_or_rule": "The configured source and rule were checked.",
                 "limitation": "This review does not prove the source beyond its recorded evidence.",
                 "materials_seen": sorted(materials)}
                for key, materials in ROUND_MATERIALS.items()
            ],
        }
        news_review = {
            "version": 1, "content_digest": content_digest(manifest), "review_method": "self",
            "items": [
                {"item_id": item["id"], "claim_digest": claim_digest(item),
                 "source_url": item["source_url"],
                 "evidence_anchor": item.get("source_excerpt") or item["source_url"],
                 "judgment": "pass", "reason": "The claim is bounded to this source.",
                 "limitation": "No broader causal conclusion is claimed.",
                 "claim_reviews": {name: {"verdict": "pass",
                                          "evidence_anchor": item.get("source_excerpt") or item["source_url"],
                                          "reason": f"The {name} claim was checked against the excerpt.",
                                          "limitation": "The excerpt does not prove broader claims."}
                                   for name in ("facts", "judgment", "relevance")}}
                for item in selected_items(config_data)
            ],
        }
        for key, value in (("story_review", story_review), ("news_review", news_review)):
            name = REVIEW_NAMES[key].format(date=self.date)
            (self.stage / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def _seal(self) -> None:
        self._write_reviews()
        self.assertEqual(cmd_seal_review(Namespace(run_dir=str(self.stage))), 0)

    def test_structure_then_review_then_strict_finalize(self) -> None:
        self.assertEqual(verify_artifacts(self.stage, strict=True, structure_only=True)["status"], "pass")
        self.assertEqual(verify_artifacts(self.stage, strict=True)["status"], "fail")
        self._seal()
        self.assertEqual(verify_artifacts(self.stage, strict=True)["status"], "pass")
        with patch("publish_daily_to_oss.auto_publish_after_finalize", return_value={"status": "disabled"}):
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(self.stage), strict=True, require_remote=True)), 2)
        self.assertEqual(verify_artifacts(self.output, strict=True)["status"], "pass")
        manifest = json.loads((self.output / f"daily_pipeline_manifest_{self.date}.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["coverage"]["start"], "2026-07-09T00:00:00+08:00")
        self.assertEqual(manifest["coverage"]["end"], "2026-07-10T00:00:00+08:00")

    def test_missing_hash_and_stale_review_fail_closed(self) -> None:
        self._seal()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        del manifest["artifact_sha256"]["html"]
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertIn("manifest hash missing or invalid: html",
                      verify_artifacts(self.stage, strict=True)["failures"])
        manifest["artifact_sha256"]["html"] = sha256_file(self.stage / manifest["artifacts"]["html"])
        manifest["artifact_sha256"]["delta_config"] = "0" * 64
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertEqual(verify_artifacts(self.stage, strict=True)["status"], "fail")

    def test_coverage_or_artifact_identity_tampering_invalidates_release(self) -> None:
        self._seal()
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        manifest["coverage"]["start"] = "2026-07-08T00:00:00+08:00"
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertIn("news review is missing or stale for this release",
                      verify_artifacts(self.stage, strict=True)["failures"])
        manifest["coverage"]["start"] = "2026-07-09T00:00:00+08:00"
        manifest["artifacts"]["story_review"] = "../unreviewed.json"
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.assertIn("manifest review artifact identity mismatch: story_review",
                      verify_artifacts(self.stage, strict=True)["failures"])

    def test_display_date_cannot_claim_another_coverage_day(self) -> None:
        raw = config()
        raw["collection_completed_at"] = "2026-07-10T08:00:00+08:00"
        candidate = self.root / "wrong-day.json"
        candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "date_range does not match"):
            cmd_run(Namespace(config=str(candidate), output_dir=str(self.root / "wrong-output"),
                              index=str(self.index), date=self.date, days=7,
                              continuing_mode="one-line", design_system="cosmic",
                              background_mode="light", release_protocol=2,
                              coverage_start=None, coverage_end=None))

    def test_multiday_search_evidence_survives_normalization_in_manifest(self) -> None:
        raw = config()
        raw["date_range"] = "2026-07-08 to 2026-07-09"
        raw["collection_completed_at"] = "2026-07-10T08:00:00+08:00"
        raw["coverage_evidence"] = [
            {"date": day, "academic_search_ref": f"academic-{day}",
             "social_search_ref": f"social-{day}"}
            for day in ("2026-07-08", "2026-07-09")]
        candidate = self.root / "backfill.json"
        candidate.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        output = self.root / "news" / "backfill"
        self.assertEqual(cmd_run(Namespace(config=str(candidate), output_dir=str(output),
                                           index=str(self.index), date=self.date, days=7,
                                           continuing_mode="one-line", design_system="cosmic",
                                           background_mode="light", release_protocol=2,
                                           coverage_start="2026-07-08T00:00:00+08:00",
                                           coverage_end="2026-07-10T00:00:00+08:00")), 0)
        staged = next((output / ".staging").iterdir())
        manifest = json.loads((staged / f"daily_pipeline_manifest_{self.date}.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["coverage"]["daily_search_evidence"], raw["coverage_evidence"])
        self.assertEqual(verify_artifacts(staged, strict=True, structure_only=True)["status"], "pass")
        manifest["coverage"]["daily_search_evidence"] = []
        (staged / f"daily_pipeline_manifest_{self.date}.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.assertIn("version-2 coverage interval or collection time is invalid",
                      verify_artifacts(staged, strict=True, structure_only=True)["failures"])

    def test_failed_review_cannot_be_sealed(self) -> None:
        self._write_reviews()
        name = REVIEW_NAMES["news_review"].format(date=self.date)
        path = self.stage / name
        review = json.loads(path.read_text(encoding="utf-8"))
        review["items"][0]["judgment"] = "unknown"
        path.write_text(json.dumps(review), encoding="utf-8")
        self.assertEqual(cmd_seal_review(Namespace(run_dir=str(self.stage))), 1)
        self.assertEqual(verify_artifacts(self.stage, strict=True)["status"], "fail")

    def test_one_unreviewed_claim_blocks_sealing_even_if_item_is_approved(self) -> None:
        self._write_reviews()
        path = self.stage / REVIEW_NAMES["news_review"].format(date=self.date)
        review = json.loads(path.read_text(encoding="utf-8"))
        review["items"][0]["claim_reviews"]["judgment"]["verdict"] = "unreviewed"
        path.write_text(json.dumps(review), encoding="utf-8")
        self.assertEqual(cmd_seal_review(Namespace(run_dir=str(self.stage))), 1)

    def test_template_does_not_auto_approve_and_refuses_overwrite(self) -> None:
        self.assertEqual(cmd_review_template(Namespace(run_dir=str(self.stage))), 0)
        with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
            cmd_review_template(Namespace(run_dir=str(self.stage)))
        self.assertEqual(cmd_seal_review(Namespace(run_dir=str(self.stage))), 1)

    def test_changed_index_blocks_stale_ranking_before_commit(self) -> None:
        self._seal()
        self.index.parent.mkdir(parents=True, exist_ok=True)
        self.index.write_text('{"story_id":"newer"}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "story index changed"):
            cmd_finalize(Namespace(run_dir=str(self.stage), strict=True))
        self.assertFalse((self.output / f"daily_pipeline_manifest_{self.date}.json").exists())

    def test_interrupted_commit_recovers_from_journal_then_completes(self) -> None:
        self._seal()
        original = shutil.copy2
        crashed = False

        def interrupt_after_first_copy(source, target, *args, **kwargs):
            nonlocal crashed
            result = original(source, target, *args, **kwargs)
            if not crashed and str(source).startswith(str(self.stage)):
                crashed = True
                raise SystemExit("simulated process termination")
            return result

        with patch("daily_pipeline.shutil.copy2", side_effect=interrupt_after_first_copy):
            with self.assertRaises(SystemExit):
                cmd_finalize(Namespace(run_dir=str(self.stage), strict=True))
        self.assertTrue(crashed)
        with patch("publish_daily_to_oss.auto_publish_after_finalize", return_value={"status": "disabled"}):
            self.assertEqual(cmd_finalize(Namespace(run_dir=str(self.stage), strict=True)), 0)
        self.assertEqual(verify_artifacts(self.output, strict=True)["status"], "pass")
        journals = list((self.output / ".release_transactions").glob("*/state.json"))
        self.assertTrue(any(json.loads(path.read_text(encoding="utf-8"))["status"] == "rolled_back" for path in journals))

    def test_status_counts_only_versioned_verified_coverage(self) -> None:
        self._seal()
        with patch("publish_daily_to_oss.auto_publish_after_finalize", return_value={"status": "disabled"}):
            cmd_finalize(Namespace(run_dir=str(self.stage), strict=True))
        output = io.StringIO()
        with redirect_stdout(output):
            cmd_status(Namespace(news_root=str(self.root / "news"), from_date="2026-07-09",
                                 through_date="2026-07-10"))
        status = json.loads(output.getvalue())
        self.assertEqual(status["missing_days"], ["2026-07-10"])
        self.assertEqual(status["covered_days"]["2026-07-09"], [self.date])
        self.assertFalse(status["releases"][0]["remote_verified"])

    def test_status_reads_legacy_release_without_claiming_day_coverage(self) -> None:
        legacy = self.root / "news" / "2026-07-11"
        legacy.mkdir(parents=True)
        (legacy / "daily_pipeline_manifest_2026-07-11.json").write_text(
            json.dumps({"pipeline_version": 1, "date": "2026-07-11", "status": "complete"}),
            encoding="utf-8")
        output = io.StringIO()
        with redirect_stdout(output):
            cmd_status(Namespace(news_root=str(self.root / "news"), from_date="2026-07-09",
                                 through_date="2026-07-11"))
        status = json.loads(output.getvalue())
        self.assertEqual(status["releases"][0]["local_status"], "legacy-unverified")
        self.assertIn("2026-07-11", status["missing_days"])

    def test_lock_rejects_concurrent_writer(self) -> None:
        news_root = self.root / "news"
        with release_lock(news_root):
            with self.assertRaises(TimeoutError):
                with release_lock(news_root, timeout=0.01):
                    pass


if __name__ == "__main__":
    unittest.main()
