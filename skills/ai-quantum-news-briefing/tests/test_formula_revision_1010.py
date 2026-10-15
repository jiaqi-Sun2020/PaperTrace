"""Formula transport and one-current-staging regression, using only temporary data."""
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from formula_contract import validate_formula
from briefing_contract import normalize_worked_example
from briefing_to_feedback_html import render_worked_example, worked_example_has_formula
from news_delta import render_worked_example_markdown
import daily_revisions as dr
import daily_pipeline as dp
import daily_authoring as authoring
import test_staging_revision_repair as fixture
import test_publication_v4 as v4


class FormulaContractTests(unittest.TestCase):
    def example(self, value, format=None):
        step = {"formula": value}
        if format is not None:
            step["formula_format"] = format
        return {"steps": [step]}

    def test_bare_percent_is_rejected_at_normalization_and_html(self):
        value = self.example("40/50=80%; 50/100=50%")
        with self.assertRaisesRegex(ValueError, "tex_formula_unescaped_percent"):
            normalize_worked_example(value)
        with self.assertRaisesRegex(ValueError, "tex_formula_unescaped_percent"):
            render_worked_example({"worked_example": value})

    def test_already_escaped_percent_is_not_double_escaped(self):
        value = self.example(r"40/50=80\%;\quad 50/100=50\%")
        normalized = normalize_worked_example(value)
        normalized_again = normalize_worked_example(normalized)
        self.assertEqual(normalized, normalized_again)
        self.assertEqual(normalized["steps"][0]["formula"], value["steps"][0]["formula"])
        html = render_worked_example({"worked_example": normalized})
        self.assertIn(value["steps"][0]["formula"], html)
        self.assertNotIn(r"80\\%", html)
        self.assertEqual(html, render_worked_example({"worked_example": normalized}))

    def test_backslash_parity_and_valid_linebreaks(self):
        for value in (r"80\%", r"a\\b=50\%", r"80\\\%", r"\frac{40}{50}=80\%"):
            self.assertEqual(validate_formula({"formula": value}), "tex")
        for value in ("80%", r"80\\%", r"80\\\\%"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_formula({"formula": value})

    def test_plain_text_percent_chinese_backslashes_do_not_enter_math_block(self):
        formula = r"覆盖率80%; 比例50%; \alpha 与 \(x\)；<边界> &"
        value = self.example(formula, "text")
        normalized = normalize_worked_example(value)
        before = deepcopy(normalized)
        html = render_worked_example({"worked_example": normalized})
        self.assertIn("tex2jax_ignore", html)
        self.assertNotIn(r"\[", html)
        self.assertIn("覆盖率80%; 比例50%;", html)
        self.assertIn("&lt;边界&gt; &amp;", html)
        self.assertFalse(worked_example_has_formula(normalized))
        markdown = "\n".join(render_worked_example_markdown(normalized))
        self.assertIn("公式（普通文本）：", markdown)
        self.assertNotIn(r"\[", markdown)
        self.assertEqual(normalized, before)
        self.assertEqual(html, render_worked_example({"worked_example": normalized}))

    def test_tex_chinese_and_macros_are_preserved(self):
        formula = r"\text{覆盖率}=\frac{40}{50}=80\%;\quad \alpha=1"
        normalized = normalize_worked_example(self.example(formula, "tex"))
        self.assertEqual(normalized["steps"][0]["formula"], formula)
        self.assertTrue(worked_example_has_formula(normalized))
        self.assertIn(formula, render_worked_example({"worked_example": normalized}))

    def test_unknown_format_and_non_string_formula_rejected(self):
        for format in ("latex", "plain", 1, True):
            with self.subTest(format=format), self.assertRaises(ValueError):
                normalize_worked_example(self.example("50%", format))
        with self.assertRaises(ValueError):
            validate_formula({"formula": 0})

    def test_implicit_tex_has_no_new_digest_fields(self):
        implicit = normalize_worked_example(self.example(r"x=50\%"))
        self.assertNotIn("formula_format", implicit["steps"][0])
        self.assertEqual(implicit, normalize_worked_example(implicit))


class SingleActiveRunUnitTests(unittest.TestCase):
    setUp = fixture.RevisionUnitTests.setUp
    revise = fixture.RevisionUnitTests.revise

    def peer(self):
        other_id = self.day + "-abcdef012345"
        other = self.stage.parent / other_id
        other.mkdir()
        dp.atomic_json(other / ("daily_pipeline_manifest_" + self.day + ".json"),
                       {"pipeline_version": 4, "status": "staged", "date": self.day, "run_id": other_id})
        return other, {other_id: dr.run_snapshot(self.root, other)["sha256"]}

    def batch_revise(self, peers, verify=None):
        return dr.revise(self.root, self.day, self.run, self.run_hash, self.candidate_hash,
                         "Repair both failed render attempts", verify=verify or (lambda *a, **k: {"status": "fail"}),
                         expected_peers=peers)

    def test_explicit_peer_bindings_retire_both_runs_without_overwriting(self):
        other, peers = self.peer()
        before = dr.run_snapshot(self.root, other)
        first = self.batch_revise(peers)
        self.assertEqual(dr.active_stages(self.root, self.day), [])
        self.assertEqual(dr.run_snapshot(self.root, other), before)
        self.assertEqual(self.candidate.read_bytes(), self.before)
        self.assertEqual(len(dr.lifecycle(self.root, self.day)["superseded_runs"]), 2)
        self.assertEqual(self.batch_revise(peers)["status"], "revision_unchanged")
        self.assertEqual(first["revision_id"], self.batch_revise(peers)["revision_id"])
        with self.assertRaisesRegex(ValueError, "revision_repeat_conflict"):
            self.batch_revise({})

    def test_peer_conflict_and_passed_review_do_not_retire_any_run(self):
        other, peers = self.peer()
        with self.assertRaisesRegex(ValueError, "revision_peer_run_conflict"):
            self.batch_revise({other.name: "0" * 64})
        with self.assertRaisesRegex(ValueError, "reviewed_staging_frozen"):
            self.batch_revise(peers, verify=lambda stage, **k: {"status": "pass" if stage == other else "fail"})
        self.assertFalse(dr.lifecycle_path(self.root, self.day).exists())
        self.assertEqual(self.candidate.read_bytes(), self.before)

    def test_peer_lifecycle_corruption_is_not_accepted_as_completed_revision(self):
        other, peers = self.peer()
        self.batch_revise(peers)
        value = dr.lifecycle(self.root, self.day)
        value["superseded_runs"][self.run]["peer_runs"][other.name] = "0" * 64
        from collection_checkpoint import fingerprint
        value["state_sha256"] = fingerprint({key: row for key, row in value.items() if key != "state_sha256"})
        dp.atomic_json(dr.lifecycle_path(self.root, self.day), value)
        with self.assertRaisesRegex(ValueError, "revision_peer_bindings_invalid"):
            dr.lifecycle(self.root, self.day)

    def test_peer_commit_interrupt_and_concurrent_reentry_commit_one_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        other, peers = self.peer()
        with patch.object(dr, "atomic_json", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                self.batch_revise(peers)
        self.assertEqual(len(dr.active_stages(self.root, self.day)), 2)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.batch_revise(peers), range(2)))
        self.assertEqual(sorted(r["status"] for r in results), ["revision_created", "revision_unchanged"])
        self.assertEqual(len({r["revision_id"] for r in results}), 1)

    def test_cli_exposes_active_run_hashes_and_requires_explicit_peer_payload(self):
        import base64, io
        from contextlib import redirect_stdout
        other, peers = self.peer()
        args = ["revise", "--date", self.day, "--run-id", self.run,
                "--expected-run-sha256", self.run_hash, "--expected-sha256", self.candidate_hash,
                "--reason", "Repair both failed render attempts"]
        with patch.object(authoring, "NEWS_ROOT", self.root), patch.object(dp, "verify_artifacts", return_value={"status": "fail"}):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(authoring.main(["revision-info", "--date", self.day, "--run-id", self.run]), 0)
            observed = json.loads(output.getvalue())
            self.assertEqual(observed["active_runs"], {self.run: self.run_hash, **peers})
            with redirect_stdout(io.StringIO()):
                self.assertEqual(authoring.main(args), 2)
                payload = base64.b64encode(json.dumps(peers).encode("utf-8")).decode("ascii")
                self.assertEqual(authoring.main(args + ["--expected-peer-runs-base64", payload]), 0)
        self.assertEqual(len(dr.lifecycle(self.root, self.day)["superseded_runs"]), 2)

    def test_multiple_legacy_stages_require_resolution_without_mutating_them(self):
        other = self.stage.parent / (self.day + "-abcdef012345")
        other.mkdir(); (other / "keep.txt").write_text("unchanged", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "revision_multiple_active_runs"):
            self.revise()
        self.assertEqual(self.candidate.read_bytes(), self.before)
        self.assertFalse(dr.lifecycle_path(self.root, self.day).exists())

    def test_unregistered_run_cannot_be_reviewed_but_can_be_revised(self):
        first = self.revise()
        orphan_id = self.day + "-abcdef012345"
        orphan = self.stage.parent / orphan_id
        orphan.mkdir()
        manifest = {"pipeline_version": 4, "status": "staged", "date": self.day, "run_id": orphan_id,
                    "revision_id": first["revision_id"]}
        from collection_checkpoint import atomic_json
        atomic_json(orphan / ("daily_pipeline_manifest_" + self.day + ".json"), manifest)
        with self.assertRaisesRegex(ValueError, "staging_run_is_not_current"):
            dr.assert_active_stage(orphan, manifest)
        with self.assertRaisesRegex(ValueError, "staging_run_is_not_current"):
            authoring.target_path(self.root, self.day, "story-review", orphan_id)
        current = dr.candidate_path(self.root, self.day)
        result = dr.revise(self.root, self.day, orphan_id, dr.run_snapshot(self.root, orphan)["sha256"], dr.sha(current),
                           "Recover interrupted staging registration", verify=lambda *a, **k: {"status": "fail"})
        self.assertEqual(result["status"], "revision_created")
        self.assertIsNone(dr.lifecycle(self.root, self.day)["active_run_id"])


class SingleActiveRunIntegrationTests(unittest.TestCase):
    setUp = v4.V4PublicationTests.setUp
    prepare = v4.V4PublicationTests.prepare
    write_candidate = v4.V4PublicationTests.write_candidate
    stage = v4.V4PublicationTests.stage

    def test_plain_formula_projection_passes_cross_surface_structure_check(self):
        self.prepare()
        step = self.raw["opening_story"]["worked_example"]["steps"][0]
        step.update(formula=r"覆盖率80%; \alpha 与 \(x\)", formula_format="text")
        self.write_candidate()
        stage, _, _ = self.stage()
        result = dp.verify_artifacts(stage, strict=True, structure_only=True)
        self.assertEqual(result["status"], "pass", result["failures"])

    def test_bad_formula_is_a_failed_audit_that_can_be_revised(self):
        self.prepare(); stage, _, manifest = self.stage()
        config_path = dp.artifact_paths(stage, self.release)["delta_config"]
        config = dp.load_json(config_path)
        config["opening_story"]["worked_example"]["steps"][0]["formula"] = "80%"
        dp.atomic_json(config_path, config)
        failed = dp.verify_artifacts(stage, strict=True)
        self.assertEqual(failed["status"], "fail")
        self.assertTrue(any("tex_formula_unescaped_percent" in f for f in failed["failures"]))
        current = dr.candidate_path(self.news, self.release)
        current.parent.mkdir(parents=True, exist_ok=True); current.write_bytes(self.candidate.read_bytes())
        result = dr.revise(self.news, self.release, manifest["run_id"], dr.run_snapshot(self.news, stage)["sha256"],
                           dr.sha(current), "Repair failed formula transport", verify=dp.verify_artifacts)
        self.assertEqual(result["status"], "revision_created")

    def test_second_run_of_same_candidate_is_blocked(self):
        self.prepare(); stage, _, manifest = self.stage()
        before = dr.run_snapshot(self.news, stage)
        with self.assertRaisesRegex(ValueError, "active_staging_exists"):
            dp.cmd_run(self.args)
        self.assertEqual(dr.lifecycle(self.news, self.release)["active_run_id"], manifest["run_id"])
        self.assertEqual(dr.run_snapshot(self.news, stage), before)
        self.assertEqual(len(dr.active_stages(self.news, self.release)), 1)

    def test_registration_write_failure_preserves_preparation_not_publishable(self):
        self.prepare()
        with patch.object(dr, "atomic_json", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                dp.cmd_run(self.args)
        self.assertEqual(dr.active_stages(self.news, self.release), [])
        preparations = list((self.news / self.release / ".staging-preparation").iterdir())
        self.assertEqual(len(preparations), 1)
        self.assertTrue(next(preparations[0].glob("daily_pipeline_manifest_*.json")))
        self.assertEqual((self.news / "_index/story_index.jsonl").read_bytes(), self.index_before)

    def test_crash_before_first_lifecycle_commit_leaves_unpublishable_orphan(self):
        self.prepare()
        with patch.object(dp, "register_stage", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                dp.cmd_run(self.args)
        stage = dr.active_stages(self.news, self.release)[0]
        manifest = dp.load_json(stage / ("daily_pipeline_manifest_" + self.release + ".json"))
        self.assertEqual(manifest["staging_lifecycle_version"], 1)
        self.assertFalse(dr.lifecycle_path(self.news, self.release).exists())
        self.assertIn("staging_run_is_not_current", dp.verify_artifacts(stage, strict=True)["failures"])
        with self.assertRaisesRegex(ValueError, "staging_run_is_not_current"):
            authoring.target_path(self.news, self.release, "news-review", manifest["run_id"])

    def test_concurrent_generation_installs_one_active_run(self):
        from concurrent.futures import ThreadPoolExecutor
        self.prepare()
        def run(_):
            try:
                return dp.cmd_run(self.args)
            except ValueError as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(results.count(0), 1)
        self.assertEqual(sum("active_staging_exists" in str(result) for result in results), 1)
        self.assertEqual(len(dr.active_stages(self.news, self.release)), 1)
