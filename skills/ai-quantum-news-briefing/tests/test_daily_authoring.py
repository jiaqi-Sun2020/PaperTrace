import base64
from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import daily_authoring as author

DAY = "2026-10-05"
DRAFT = {"news_feedback_version": 1, "sections": [{"title": "学术", "items": []}]}


class DailyAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "news"
        self.target = self.root / "_collection" / DAY / ("candidate_" + DAY + ".json")

    def save(self, value=DRAFT, expected="absent", **kwargs):
        return author.save(self.root, DAY, "candidate", expected, value, **kwargs)

    def test_probe_creates_no_candidate_or_leftover(self):
        self.assertEqual(author.probe(self.root, DAY)["status"], "authoring_write_probe_pass")
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.target.parent.iterdir()), [])

    def test_utf8_save_is_unreviewed_and_repeat_has_no_backup(self):
        first = self.save({**DRAFT, "briefing_title": "量子日报", "semantic_review_status": "approved"})
        self.assertFalse(first["content_approved"])
        data = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(data["semantic_review_status"], "not_reviewed")
        self.assertEqual(data["briefing_title"], "量子日报")
        original = self.target.read_bytes()
        self.assertEqual(self.save(data, first["sha256"])["status"], "unchanged")
        self.assertEqual(original, self.target.read_bytes())
        self.assertFalse((self.target.parent / ".authoring_backups").exists())

    def test_patch_keeps_fields_and_exact_original_backup(self):
        first = self.save()
        original = self.target.read_bytes()
        second = self.save([{"op": "add", "path": "/sections/0/items/-", "value": {"id": "A1", "facts": "原始证据"}}],
                           first["sha256"], patch=True)
        self.assertNotEqual(second["sha256"], first["sha256"])
        backup = next((self.target.parent / ".authoring_backups").iterdir())
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(author.digest(backup), first["sha256"])

    def test_conflict_preserves_target(self):
        self.save()
        original = self.target.read_bytes()
        with self.assertRaisesRegex(author.AuthoringError, "authoring_conflict"):
            self.save({**DRAFT, "title": "stale"})
        self.assertEqual(original, self.target.read_bytes())

    def test_concurrent_first_writers_only_one_wins(self):
        def attempt(title):
            try:
                self.save({**DRAFT, "title": title})
                return "saved"
            except author.AuthoringError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(attempt, ["one", "two"]))
        self.assertCountEqual(results, ["saved", "authoring_conflict"])

    def test_interrupted_install_preserves_previous(self):
        first = self.save()
        original = self.target.read_bytes()
        with patch.object(author, "atomic_json", side_effect=PermissionError("test")):
            with self.assertRaises(PermissionError):
                self.save({**DRAFT, "title": "new"}, first["sha256"])
        self.assertEqual(original, self.target.read_bytes())

    def test_bad_drafts_do_not_create_target(self):
        for value in [[], {}, {"news_feedback_version": True, "sections": []},
                      {"news_feedback_version": 2, "sections": []},
                      {"news_feedback_version": 1, "sections": [{"items": [None]}]},
                      {**DRAFT, "title": "bad\ufffd"}]:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                self.save(value)
            self.assertFalse(self.target.exists())

    def test_invalid_dates_and_kinds_fail_closed(self):
        for day in ["../2026-10-05", "2026-02-30", "2026-1-05", "C:\\other"]:
            with self.subTest(day=day), self.assertRaises(ValueError):
                author.target_path(self.root, day, "candidate")
        with self.assertRaises(author.AuthoringError):
            author.target_path(self.root, DAY, "manifest")

    def test_published_and_staged_candidates_are_frozen(self):
        final = self.root / DAY
        final.mkdir(parents=True)
        manifest = final / ("daily_pipeline_manifest_" + DAY + ".json")
        manifest.write_text("{}")
        with self.assertRaisesRegex(author.AuthoringError, "published_release_frozen"):
            self.save()
        manifest.unlink()
        (final / ".staging" / (DAY + "-" + "a" * 12)).mkdir(parents=True)
        with self.assertRaisesRegex(author.AuthoringError, "staged_candidate_frozen"):
            self.save()

    def test_copy_file_preserves_evidence_and_cannot_read_outside_news(self):
        first = self.save()
        source = self.target.parent / "academic.json"
        source.write_text('{"raw": "日期和证据"}', encoding="utf-8")
        op = {"op": "copy-file", "path": "/academic_search", "source": "_collection/" + DAY + "/academic.json"}
        result = self.save([op], first["sha256"], patch=True)
        data = json.loads(self.target.read_text(encoding="utf-8"))
        self.assertEqual(data["academic_search"], {"raw": "日期和证据"})
        for path in ["../secret.json", str(source.absolute()), "_collection/../../secret.json"]:
            with self.assertRaises(author.AuthoringError):
                self.save([{**op, "source": path}], result["sha256"], patch=True)

    def test_copy_file_cannot_import_feedback_other_days_or_authored_candidates(self):
        first = self.save()
        feedback = self.root / DAY / "news_feedback.json"
        feedback.parent.mkdir(parents=True, exist_ok=True)
        feedback.write_text('{"private":"annotation"}', encoding="utf-8")
        other_day = self.root / "_collection" / "2026-10-04" / "academic.json"
        other_day.parent.mkdir(parents=True)
        other_day.write_text('{"source":"other day"}', encoding="utf-8")
        candidate = self.target.parent / "candidate_source.json"
        candidate.write_text('{"source":"authored"}', encoding="utf-8")
        op = {"op": "copy-file", "path": "/evidence", "source": ""}
        for path in [f"{DAY}/news_feedback.json", "_collection/2026-10-04/academic.json",
                     f"_collection/{DAY}/candidate_source.json"]:
            with self.subTest(path=path), self.assertRaises(author.AuthoringError):
                self.save([{**op, "source": path}], first["sha256"], patch=True)

    def test_symlink_escape_is_rejected(self):
        self.root.mkdir()
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        try:
            (self.root / "_collection").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(author.AuthoringError):
            self.save()
        self.assertEqual(list(outside.iterdir()), [])

    def test_windows_reparse_root_is_rejected_before_lock_write(self):
        self.root.mkdir()
        original = Path.lstat
        def lstat(path):
            return SimpleNamespace(st_file_attributes=0x400, st_mode=original(path).st_mode) if path == self.root else original(path)
        with patch.object(Path, "lstat", lstat):
            with self.assertRaisesRegex(author.AuthoringError, "reparse_path_forbidden"):
                author.probe(self.root, DAY)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_explicit_replacement_repairs_corrupt_candidate_with_exact_backup(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b'{"sections":broken')
        original = self.target.read_bytes()
        expected = author.digest(self.target)
        result = self.save(DRAFT, expected)
        self.assertEqual(result["status"], "draft_saved")
        self.assertEqual(next((self.target.parent / ".authoring_backups").iterdir()).read_bytes(), original)

    def test_future_candidate_version_is_preserved(self):
        self.target.parent.mkdir(parents=True)
        self.target.write_text('{"news_feedback_version":2,"sections":[]}')
        with self.assertRaisesRegex(author.AuthoringError, "candidate_version_incompatible"):
            self.save(DRAFT, author.digest(self.target))
        self.assertEqual(json.loads(self.target.read_text())["news_feedback_version"], 2)

    def test_partial_draft_never_reports_capture_or_staging_readiness(self):
        import orchestrate_daily
        self.save()
        state = orchestrate_daily.inspect(DAY, news_root=self.root)
        self.assertEqual(state["phase"], "candidate_authoring_pending")
        self.assertEqual(state["semantic_review_status"], "not_reviewed")

    def test_malformed_patch_is_transactional(self):
        first = self.save()
        original = self.target.read_bytes()
        for op in [{"op": "exec", "path": "/x"}, {"op": "add", "path": "/bad~3"},
                   {"op": "add", "path": "/sections/-1", "value": 1},
                   {"op": "add", "path": "/sections/100", "value": {}},
                   {"op": "replace", "path": "/missing", "value": "x"}]:
            with self.assertRaises((ValueError, KeyError, IndexError)):
                self.save([op], first["sha256"], patch=True)
            self.assertEqual(original, self.target.read_bytes())

    def test_decoder_rejects_duplicate_keys_nonfinite_and_encoding_corruption(self):
        for raw in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}', b'{"x":"\\ufffd"}', b'\xff']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                author.decode_json(raw)

    def review_template(self, kind="news-review"):
        run_id = DAY + "-" + "a" * 12
        stage = self.root / DAY / ".staging" / run_id
        stage.mkdir(parents=True)
        (stage / ("daily_pipeline_manifest_" + DAY + ".json")).write_text(json.dumps(
            {"date": DAY, "run_id": run_id, "status": "staged", "pipeline_version": 4}))
        data = ({"version": 1, "content_digest": "source-bound", "items": [
            {"item_id": "A1", "claim_digest": "claim-bound", "source_url": "https://example.org", "judgment": "unreviewed"}]}
            if kind == "news-review" else {"review_protocol_version": 3, "story_sha256": "story-bound", "rounds": []})
        target = stage / author.REVIEW_NAMES[kind.replace("-", "_")].format(date=DAY)
        target.write_text(json.dumps(data))
        return run_id, target, data

    def test_review_authoring_cannot_change_source_bindings_or_approve_release(self):
        run_id, target, data = self.review_template()
        expected = author.digest(target)
        with self.assertRaisesRegex(author.AuthoringError, "review_binding_changed"):
            author.save(self.root, DAY, "news-review", expected, {**data, "content_digest": "fake"}, run_id=run_id)
        changed = json.loads(json.dumps(data))
        changed["items"][0]["item_id"] = "different"
        with self.assertRaisesRegex(author.AuthoringError, "review_item_binding_changed"):
            author.save(self.root, DAY, "news-review", expected, changed, run_id=run_id)
        result = author.save(self.root, DAY, "news-review", expected, [
            {"op": "add", "path": "/items/0/reason", "value": "Actual reviewer prose"}], patch=True, run_id=run_id)
        self.assertFalse(result["content_approved"])
        manifest = json.loads((target.parent / ("daily_pipeline_manifest_" + DAY + ".json")).read_text())
        self.assertEqual(manifest["status"], "staged")

    def test_story_review_keeps_digest_and_requires_existing_template(self):
        run_id, target, data = self.review_template("story-review")
        with self.assertRaisesRegex(author.AuthoringError, "review_binding_changed"):
            author.save(self.root, DAY, "story-review", author.digest(target), {**data, "story_sha256": "fake"}, run_id=run_id)
        target.unlink()
        with self.assertRaisesRegex(author.AuthoringError, "review_template_required"):
            author.save(self.root, DAY, "story-review", "absent", data, run_id=run_id)

    def test_cli_reports_write_failure_and_bounds_payload(self):
        payload = base64.b64encode(json.dumps(DRAFT).encode("utf-8")).decode("ascii")
        with contextlib.redirect_stdout(io.StringIO()) as output, patch.object(author, "NEWS_ROOT", self.root), \
                patch.object(author, "probe", side_effect=PermissionError("private system detail")):
            self.assertEqual(author.main(["probe", "--date", DAY]), 2)
        self.assertNotIn("private system detail", output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()), patch.object(author, "NEWS_ROOT", self.root):
            self.assertEqual(author.main(["save", "--date", DAY, "--expected-sha256", "absent", "--payload-base64", payload]), 0)
            self.assertEqual(author.main(["save", "--date", DAY, "--expected-sha256", "absent", "--payload-base64", "A" * 20001]), 2)


if __name__ == "__main__":
    unittest.main()
