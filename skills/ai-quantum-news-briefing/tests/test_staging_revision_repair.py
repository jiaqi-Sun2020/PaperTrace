"""Digest-bound revisions preserve failed evidence and reset every review gate."""
from argparse import Namespace
from copy import deepcopy
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_revisions as revisions
import daily_authoring as authoring
import daily_pipeline as pipeline
import test_publication_v4 as fixtures
from collection_checkpoint import atomic_json


class RevisionUnitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.day = "2026-10-05"
        self.run = self.day + "-0123456789ab"
        self.stage = self.root / self.day / ".staging" / self.run
        self.stage.mkdir(parents=True)
        atomic_json(self.stage / ("daily_pipeline_manifest_" + self.day + ".json"),
                    {"pipeline_version": 4, "status": "staged", "date": self.day, "run_id": self.run})
        (self.stage / "failed_review.json").write_text('{"judgment":"unreviewed"}', encoding="utf-8")
        self.candidate = revisions.candidate_path(self.root, self.day)
        atomic_json(self.candidate, {"news_feedback_version": 1, "sections": [], "authoring_status": "complete"})
        self.before = self.candidate.read_bytes()
        self.run_hash = revisions.run_snapshot(self.root, self.stage)["sha256"]
        self.candidate_hash = revisions.sha(self.candidate)

    def revise(self, **extra):
        return revisions.revise(self.root, self.day, self.run, self.run_hash, self.candidate_hash,
                                "Repair source reference mismatch", verify=extra.get("verify", lambda *a, **k: {"status": "fail"}))

    def test_revision_preserves_all_original_bytes_and_is_idempotent(self):
        first = self.revise()
        self.assertEqual(first["status"], "revision_created")
        self.assertFalse(first["content_approved"])
        self.assertEqual(self.candidate.read_bytes(), self.before)
        self.assertEqual(revisions.run_snapshot(self.root, self.stage)["sha256"], self.run_hash)
        new_path = Path(first["candidate"])
        new_value = json.loads(new_path.read_text(encoding="utf-8"))
        self.assertEqual(new_value["authoring_status"], "in_progress")
        self.assertEqual(new_value["semantic_review_status"], "not_reviewed")
        self.assertEqual(new_value["source_url_contract_version"], 2)
        self.assertEqual(new_path.parent.joinpath("candidate_before.json").read_bytes(), self.before)
        checkpoint_before = revisions.lifecycle_path(self.root, self.day).read_bytes()
        files_before = sorted(str(p) for p in self.root.rglob("*"))
        self.assertEqual(self.revise()["status"], "revision_unchanged")
        self.assertEqual(revisions.lifecycle_path(self.root, self.day).read_bytes(), checkpoint_before)
        self.assertEqual(sorted(str(p) for p in self.root.rglob("*")), files_before)
        self.assertEqual(revisions.active_stages(self.root, self.day), [])
        self.assertEqual(authoring.target_path(self.root, self.day, "candidate"), new_path)

    def test_digest_conflict_does_not_create_revision(self):
        self.candidate.write_bytes(self.before + b" ")
        with self.assertRaisesRegex(ValueError, "revision_candidate_conflict"):
            self.revise()
        self.assertFalse(revisions.lifecycle_path(self.root, self.day).exists())
        self.assertFalse(self.candidate.parent.joinpath(".revisions").exists())

    def test_run_conflict_does_not_create_revision(self):
        (self.stage / "failed_review.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "revision_run_conflict"):
            self.revise()
        self.assertEqual(self.candidate.read_bytes(), self.before)

    def test_interrupted_commit_keeps_old_stage_active_and_can_resume(self):
        with patch.object(revisions, "atomic_json", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.revise()
        self.assertEqual(revisions.candidate_path(self.root, self.day), self.candidate)
        self.assertEqual(revisions.active_stages(self.root, self.day), [self.stage])
        self.assertEqual(self.candidate.read_bytes(), self.before)
        self.assertEqual(self.revise()["status"], "revision_created")

    def test_reviewed_or_published_run_cannot_be_revised(self):
        with self.assertRaisesRegex(ValueError, "reviewed_staging_frozen"):
            self.revise(verify=lambda *a, **k: {"status": "pass"})
        (self.root / self.day / ("daily_pipeline_manifest_" + self.day + ".json")).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "published_release_frozen"):
            self.revise()

    def test_superseded_review_and_evidence_tampering_rejected(self):
        self.revise()
        with self.assertRaisesRegex(ValueError, "staging_revision_superseded"):
            authoring.target_path(self.root, self.day, "news-review", self.run)
        (self.stage / "failed_review.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "superseded_run_changed"):
            revisions.active_stages(self.root, self.day)

    def test_new_candidate_revision_binding_cannot_be_removed(self):
        self.revise()
        path = revisions.candidate_path(self.root, self.day)
        value = json.loads(path.read_text(encoding="utf-8"))
        value.pop("revision_id")
        with self.assertRaisesRegex(authoring.AuthoringError, "candidate_revision_binding_changed"):
            authoring.save(self.root, self.day, "candidate", revisions.sha(path), value)

    def test_malformed_lifecycle_fails_closed(self):
        path = revisions.lifecycle_path(self.root, self.day)
        atomic_json(path, [])
        with self.assertRaisesRegex(ValueError, "revision_lifecycle_invalid"):
            revisions.candidate_path(self.root, self.day)

    def test_relocation_cannot_revive_superseded_run(self):
        self.revise()
        manifest = {"date": self.day, "run_id": self.run, "pipeline_version": 4, "status": "complete"}
        with self.assertRaisesRegex(ValueError, "staging_revision_superseded"):
            revisions.assert_active_stage(self.root / self.day, manifest)

    def test_path_traversal_and_unknown_generation_rejected(self):
        with self.assertRaises(ValueError):
            revisions.revise(self.root, self.day, "../escape", self.run_hash, self.candidate_hash, "reason", verify=lambda *a, **k: {})
        manifest = self.stage / ("daily_pipeline_manifest_" + self.day + ".json")
        data = json.loads(manifest.read_text(encoding="utf-8")); data["pipeline_version"] = 5
        atomic_json(manifest, data)
        self.run_hash = revisions.run_snapshot(self.root, self.stage)["sha256"]
        with self.assertRaisesRegex(ValueError, "revision_requires_protocol4_staging"):
            self.revise()

    def test_concurrent_identical_revisions_commit_once(self):
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: self.revise(), range(2)))
        self.assertEqual(sorted(r["status"] for r in results), ["revision_created", "revision_unchanged"])
        self.assertEqual(len(list(self.candidate.parent.joinpath(".revisions").iterdir())), 1)
        self.assertEqual(self.candidate.read_bytes(), self.before)


class StagingRepairIntegrationTests(unittest.TestCase):
    setUp = fixtures.V4PublicationTests.setUp
    prepare = fixtures.V4PublicationTests.prepare
    write_candidate = fixtures.V4PublicationTests.write_candidate
    stage = fixtures.V4PublicationTests.stage

    def test_old_run_rejected_by_verify_seal_finalize_and_publisher(self):
        self.prepare()
        stage, _, manifest = self.stage()
        current = revisions.candidate_path(self.news, self.release)
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_bytes(self.candidate.read_bytes())
        before = revisions.run_snapshot(self.news, stage)
        result = revisions.revise(self.news, self.release, manifest["run_id"], before["sha256"], revisions.sha(current),
                                  "Repair failed staging", verify=pipeline.verify_artifacts)
        self.assertEqual(pipeline.verify_artifacts(stage, strict=True)["failures"], ["staging_revision_superseded"])
        self.assertEqual(pipeline.cmd_seal_review(Namespace(run_dir=str(stage))), 1)
        self.assertEqual(pipeline._commit_local(Namespace(run_dir=str(stage), strict=True))["status"], "local_verification_failed")
        import publish_daily_to_oss as publisher
        with self.assertRaises(publisher.PublishError):
            publisher.verified_release(stage)
        self.assertEqual(revisions.run_snapshot(self.news, stage), before)
        new_path = Path(result["candidate"])
        draft = json.loads(new_path.read_text(encoding="utf-8"))
        draft["authoring_status"] = "complete"
        authoring.save(self.news, self.release, "candidate", revisions.sha(new_path), draft)
        self.args.config = str(new_path)
        self.assertEqual(pipeline.cmd_run(self.args), 0)
        new_stage = [p for p in (self.news / self.release / ".staging").iterdir() if p != stage][0]
        new_manifest = pipeline.load_json(next(new_stage.glob("daily_pipeline_manifest_*.json")))
        self.assertEqual(new_manifest["revision_id"], result["revision_id"])
        self.assertEqual(pipeline.verify_artifacts(new_stage, strict=True, structure_only=True)["status"], "pass")
        self.assertEqual(pipeline.verify_artifacts(new_stage, strict=True)["status"], "fail")
        self.assertEqual((self.news / "_index" / "story_index.jsonl").read_bytes(), self.index_before)

    def test_lossless_urls_stage_with_unmodified_source_records(self):
        import html
        from source_capture import capture_path, make_capture
        self.prepare()
        before = {}
        for section in self.raw["sections"]:
            for item in section["items"]:
                item["source_url"] += "/?edition=1#claim"
                record = make_capture(item, item["source_url"], item["source_url"].split("#")[0], 200,
                    ("<p>" + html.escape(item["source_excerpt"]) + "</p>").encode("utf-8"), "2026-07-10T01:00:00Z")
                path = capture_path(self.news, self.raw["date_range"], item["id"])
                atomic_json(path, record); before[item["story_id"]] = (item["source_url"], record, path.read_bytes())
        self.write_candidate()
        stage, _, _ = self.stage()
        config = pipeline.load_json(pipeline.artifact_paths(stage, self.release)["delta_config"])
        for section in config["sections"]:
            for item in section["items"]:
                self.assertEqual((item["source_url"], item["source_capture"]), before[item["story_id"]][:2])
                path = capture_path(self.news, self.raw["date_range"], item["source_capture"]["item_id"])
                self.assertEqual(path.read_bytes(), before[item["story_id"]][2])

    def test_derived_story_ids_keep_original_capture_identity_after_delta_renumbering(self):
        import html
        from source_capture import capture_path, make_capture
        self.prepare()
        for item in self.raw["sections"][1]["items"]:
            item.pop("story_id", None)
            record = make_capture(item, item["source_url"], item["source_url"], 200,
                ("<p>" + html.escape(item["source_excerpt"]) + "</p>").encode("utf-8"), "2026-07-10T01:00:00Z")
            atomic_json(capture_path(self.news, self.raw["date_range"], item["id"]), record)
        self.write_candidate()
        stage, _, _ = self.stage()
        config = pipeline.load_json(pipeline.artifact_paths(stage, self.release)["delta_config"])
        social = [item for section in config["sections"] for item in section["items"] if item["source_candidate_id"].startswith("S")]
        self.assertTrue(social)
        for item in social:
            self.assertEqual(item["source_capture"]["item_id"], item["source_candidate_id"])
            self.assertEqual(item["source_capture"]["story_id"], "")
            self.assertTrue(item["story_id"].startswith("story-url-"))

    def test_bad_unselected_cache_is_accounted_and_does_not_abort_valid_pool(self):
        from source_capture import capture_path
        self.prepare()
        bad = deepcopy(self.raw["sections"][1]["items"][-1])
        bad.update(id="BAD001", story_id="bad-extra", source_url="https://example.org/bad-extra")
        self.raw["sections"][1]["items"].append(bad)
        path = capture_path(self.news, self.raw["date_range"], bad["id"])
        path.write_text("broken cache", encoding="utf-8")
        self.write_candidate()
        stage, _, _ = self.stage()
        config = pipeline.load_json(pipeline.artifact_paths(stage, self.release)["delta_config"])
        ledger = config["candidate_admission"]
        self.assertEqual(len(ledger["records"]), 25)
        self.assertEqual(ledger["counts"]["retry_pending"], 1)
        self.assertEqual(ledger["counts"]["evidence_valid"], 24)
        selected = [i for s in config["sections"] for i in s["items"]]
        self.assertFalse(any(i.get("story_id") == "bad-extra" for i in selected))
        self.assertEqual(path.read_text(encoding="utf-8"), "broken cache")

    def test_interrupted_staging_never_freezes_candidate(self):
        self.prepare()
        current = revisions.candidate_path(self.news, self.release)
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_bytes(self.candidate.read_bytes())
        with patch.object(pipeline, "atomic_text", side_effect=PermissionError("write interrupted")):
            with self.assertRaises(PermissionError):
                pipeline.cmd_run(self.args)
        self.assertEqual(revisions.active_stages(self.news, self.release), [])
        self.assertEqual(authoring.target_path(self.news, self.release, "candidate"), current)
        self.assertFalse(pipeline.artifact_paths(self.news / self.release, self.release)["manifest"].exists())
        self.assertEqual((self.news / "_index" / "story_index.jsonl").read_bytes(), self.index_before)

    def test_candidate_change_before_commit_does_not_install_staging(self):
        self.prepare()
        original = pipeline.render_html
        def changed(config):
            self.candidate.write_bytes(self.candidate.read_bytes() + b" ")
            return original(config)
        with patch.object(pipeline, "render_html", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "candidate_changed_during_staging"):
                pipeline.cmd_run(self.args)
        self.assertEqual(revisions.active_stages(self.news, self.release), [])

    def test_url_contract_downgrade_cannot_verify(self):
        self.prepare()
        stage, path, manifest = self.stage()
        manifest.pop("source_url_contract_version")
        pipeline.atomic_json(path, manifest)
        result = pipeline.verify_artifacts(stage, strict=True, structure_only=True)
        self.assertIn("source_url_contract_binding_differs", result["failures"])

    def test_pool_readiness_ignores_only_bad_unselected_extra(self):
        import orchestrate_daily as orchestrator
        self.prepare()
        self.raw.update(authoring_status="complete", source_url_contract_version=2, news_feedback_version=1)
        bad = {**self.raw["sections"][1]["items"][-1], "id": "BAD001", "story_id": "bad-extra",
               "source_url": "https://example.org/bad-extra"}
        self.raw["sections"][1]["items"].append(bad)
        current = revisions.candidate_path(self.news, self.release)
        atomic_json(current, self.raw)
        with patch.object(orchestrator, "NEWS_ROOT", self.news):
            state = orchestrator.inspect(self.release, news_root=self.news)
        self.assertEqual(state["phase"], "candidate_ready")
        self.assertEqual(state["missing_capture_ids"], ["BAD001"])
        self.assertEqual(state["candidate_admission"]["counts"]["pending_capture"], 1)
        self.assertEqual(state["opening_story_status"], "present_not_reviewed")

    def test_valid_captures_below_quota_do_not_make_pool_ready(self):
        import orchestrate_daily as orchestrator
        self.prepare()
        self.raw.update(authoring_status="complete", source_url_contract_version=2, news_feedback_version=1)
        for section in self.raw["sections"]:
            section["items"] = section["items"][:1]
        current = revisions.candidate_path(self.news, self.release)
        atomic_json(current, self.raw)
        state = orchestrator.inspect(self.release, news_root=self.news)
        self.assertEqual(state["phase"], "candidate_waiting_capture")
        self.assertTrue(state["candidate_pool_failures"])
        self.assertEqual(state["missing_capture_ids"], [])
