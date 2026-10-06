"""Persist failed collection evidence without promoting it to a ready source."""
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import orchestrate_daily as o
from test_orchestrate_daily import DAY, COVERED, fixtures


class CollectionDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.news = Path(temporary.name) / "news"
        self.paths = o.collection_paths(DAY, self.news)
        self.paths["social"].parent.mkdir(parents=True)
        self.academic, social = fixtures()
        self.paths["social"].write_text(json.dumps(social), encoding="utf-8")
        self.social_bytes = self.paths["social"].read_bytes()
        root = patch.object(o, "NEWS_ROOT", self.news)
        root.start()
        self.addCleanup(root.stop)
        self.preflight = {"status": "ready", "reason": "at_least_one_allowed_source_replied",
                          "probes": [{"name": "aps", "result": "http_response", "http_status": 200}]}
        self.outputs = []

    def run_resume(self, payload, interrupted=False):
        def collect(command, **kwargs):
            self.assertIn("academic_venue_sweep.py", command[2])
            target = Path(command[command.index("--output") + 1])
            self.outputs.append(target)
            target.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
            if interrupted:
                raise subprocess.TimeoutExpired(command, kwargs["timeout"])
            return SimpleNamespace(returncode=0)
        output = io.StringIO()
        with patch.object(o, "inspect_network", return_value=deepcopy(self.preflight)), \
                patch.object(o.subprocess, "run", side_effect=collect), redirect_stdout(output):
            code = o.main(["resume", "--date", DAY, "--record"])
        state = json.loads(output.getvalue())
        saved = json.loads((self.news / "_automation" / ("orchestration_state_" + DAY + ".json")).read_text())
        self.assertEqual(saved, state)
        self.assertEqual(self.paths["social"].read_bytes(), self.social_bytes)
        self.assertTrue(all(not path.exists() for path in self.outputs))
        return code, state

    def test_failed_family_preserves_current_preflight_and_window_diagnostics(self):
        failed = deepcopy(self.academic)
        row = failed["rows"][1]
        row.update(result="degraded", window_status="expired")
        row["window_evidence"] = {
            "observed_earliest_date": "2026-09-01", "observed_latest_date": "2026-09-30",
            "requested_start": COVERED, "requested_end": COVERED,
            "classification_basis": "target_after_feed", "pagination_complete": False,
            "source_scope": "rolling_feed", "response_body": "must not be copied"}
        row["evidence"]["error"] = "must not be copied"
        # A forged saved gate must not turn the diagnostic into an accepted source.
        failed["family_gate"]["status"] = "pass"
        code, state = self.run_resume(failed)
        self.assertEqual(code, 2)
        self.assertEqual(state["phase"], "collection_partial")
        self.assertEqual(state["network_preflight"], self.preflight)
        self.assertEqual(state["collection_failures"], [{"stage": "academic", "code": "academic_family_gate_invalid"}])
        diagnostic = state["collection_diagnostics"]["academic"]
        self.assertTrue(diagnostic["diagnostic_only"])
        self.assertEqual(diagnostic["missing_families"], ["ai_peer_review"])
        self.assertEqual(diagnostic["family_gate"]["status"], "fail")
        health = next(item for item in diagnostic["source_health"] if item["source_id"] == "nature-machine-learning")
        self.assertEqual(health["window_status"], "expired")
        self.assertEqual(health["window_evidence"]["observed_latest_date"], "2026-09-30")
        self.assertEqual(health["window_evidence"]["classification_basis"], "target_after_feed")
        self.assertEqual(health["http_evidence"]["status_code"], 200)
        self.assertNotIn("must not be copied", json.dumps(diagnostic))
        self.assertFalse(self.paths["academic"].exists())
        self.assertFalse(self.paths["packet"].exists())

    def test_interrupted_failed_collector_keeps_diagnostics_after_temp_cleanup(self):
        failed = deepcopy(self.academic)
        failed["rows"][1].update(result="blocked", retrieval_status="blocked", window_status="unknown")
        failed["rows"][1]["evidence"]["status_code"] = 403
        code, state = self.run_resume(failed, interrupted=True)
        self.assertEqual(code, 2)
        self.assertEqual(state["collection_diagnostics"]["academic"]["missing_families"], ["ai_peer_review"])
        self.assertEqual(state["network_preflight"], self.preflight)
        self.assertFalse(self.paths["academic"].exists())

    def test_corrupt_collector_json_does_not_mask_original_failure(self):
        code, state = self.run_resume("{broken")
        self.assertEqual(code, 2)
        self.assertEqual(state["collection_failures"][0]["code"], "collector_JSONDecodeError")
        self.assertEqual(state["collection_diagnostics"]["academic"]["status"], "unreadable")
        self.assertEqual(state["network_preflight"], self.preflight)

    def test_success_keeps_preflight_and_uses_recomputed_gate(self):
        code, state = self.run_resume(self.academic)
        self.assertEqual(code, 0)
        self.assertEqual(state["phase"], "collection_ready")
        self.assertEqual(state["network_preflight"], self.preflight)
        self.assertEqual(state["collection_diagnostics"]["academic"]["missing_families"], [])
        self.assertEqual(json.loads(self.paths["packet"].read_text())["semantic_review_status"], "not_reviewed")

    def test_plain_status_record_retains_failure_only_in_attempt_history(self):
        failed = deepcopy(self.academic)
        failed["rows"][1].update(result="degraded", window_status="expired")
        _, failure = self.run_resume(failed)
        history = failure["last_collection_attempt"]
        self.assertEqual(history["collection_diagnostics"]["academic"]["missing_families"], ["ai_peer_review"])
        output = io.StringIO()
        with patch.object(o, "inspect_network", side_effect=AssertionError("offline status used network")), \
                patch.object(o.subprocess, "run", side_effect=AssertionError("offline status collected")), redirect_stdout(output):
            code = o.main(["status", "--date", DAY, "--record"])
        status = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(status["last_collection_attempt"], history)
        self.assertNotIn("operation_failed", status)
        self.assertNotIn("collection_failures", status)
        self.assertEqual(status["phase"], "collection_partial")

    def test_success_replaces_failed_history_and_late_old_failure_cannot_restore_it(self):
        failed = deepcopy(self.academic)
        failed["rows"][1].update(result="degraded", window_status="expired")
        _, failure = self.run_resume(failed)
        old = deepcopy(failure)
        code, success = self.run_resume(self.academic)
        self.assertEqual(code, 0)
        self.assertNotIn("operation_failed", success)
        self.assertNotIn("collection_failures", success)
        history = success["last_collection_attempt"]
        self.assertNotIn("collection_failures", history)
        self.assertEqual(history["collection_diagnostics"]["academic"]["missing_families"], [])
        self.assertGreater(history["started_at"], old["last_collection_attempt"]["started_at"])
        o._record(old, True)
        self.assertEqual(old["last_collection_attempt"], history)
        self.assertNotIn("operation_failed", old)
        self.assertEqual(old["phase"], "collection_ready")

    def test_network_blocked_attempt_is_recorded_without_collector(self):
        output = io.StringIO()
        with patch.object(o, "inspect_network", return_value={"status": "environment_blocked", "reason": "local_https_proxy_refused"}), \
                patch.object(o.subprocess, "run", side_effect=AssertionError("blocked attempt collected")), redirect_stdout(output):
            code = o.main(["resume", "--date", DAY, "--record"])
        state = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        history = state["last_collection_attempt"]
        self.assertEqual(history["phase"], "environment_blocked")
        self.assertEqual(history["network_preflight"]["status"], "environment_blocked")
        self.assertIn("observed_at", history)


if __name__ == "__main__":
    unittest.main()
