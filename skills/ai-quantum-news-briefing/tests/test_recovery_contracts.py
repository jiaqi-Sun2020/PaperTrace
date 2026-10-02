"""Regression contracts from the second audit; temporary artifacts, mocked transport."""
from argparse import Namespace
from contextlib import redirect_stdout, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
import hashlib
import io
import json
import sys
import tempfile
import unittest
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import academic_sources as academic
import aihot_candidates as hot
import daily_pipeline as pipeline
import orchestrate_daily as orchestration
import collection_checkpoint as checkpoints
from audit_briefing_config import academic_search_venues
from evidence_fixtures import evidenced_row
from test_orchestrate_daily import fixtures


class RecoveryContracts(unittest.TestCase):
    @contextmanager
    def remote_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            day = "2026-10-02"
            output = root / day
            output.mkdir()
            (output / ("daily_pipeline_manifest_" + day + ".json")).write_text('{"status":"complete"}', encoding="utf-8")
            (output / ("briefing_reader_" + day + ".html")).write_bytes(b"reviewed")
            receipt = root / "_publish" / ("oss_publish_receipt_" + day + ".json")
            receipt.parent.mkdir()
            receipt.write_text(json.dumps({"html_sha256": hashlib.sha256(b"reviewed").hexdigest()}), encoding="utf-8")
            config = {"site_index_url": "https://public.example/index.html", "bucket": "public", "region": "region", "object_prefix": ""}
            with patch.object(orchestration, "NEWS_ROOT", root), \
                    patch.object(orchestration, "verify_artifacts", return_value={"status": "pass"}), \
                    patch("publish_daily_to_oss.load_config", return_value=config), \
                    patch("publish_daily_to_oss.inspect_public_release", return_value={"status": "verified"}) as remote:
                yield root, day, config, remote

    def test_each_academic_evidence_attack_is_rejected(self):
        valid = evidenced_row({"source_id": "aps-pra", "result": "checked", "retrieval_status": "success",
                               "parse_status": "success", "window_status": "matched", "candidate_count": 1})
        self.assertTrue(academic.row_is_healthy(valid, "2026-10-01"))
        for key, value in [("status_code", 403), ("status_code", True), ("response_hash", "z" * 64),
                           ("response_hash", ""), ("retrieved_at", "2026-10-01T01:00:00Z"),
                           ("retrieved_at", "2026-10-02T01:00:00"),
                           ("query_url", "https://feeds.aps.org/rss/recent/prl.xml"),
                           ("final_url", "https://feeds.aps.org.invalid.example/rss"),
                           ("final_url", "https://user@feeds.aps.org/rss")]:
            with self.subTest(key=key, value=value):
                row = deepcopy(valid)
                row["evidence"][key] = value
                self.assertFalse(academic.row_is_healthy(row, "2026-10-01"))
        for key, value in [("coverage_window", "2026-09-30"), ("coverage_claim", "complete_publisher_day"),
                           ("candidate_count", True), ("candidate_count", 2), ("parse_status", "not_applicable"),
                           ("matches", [{"published_at": "2026-09-30T12:00:00+08:00"}])]:
            row = deepcopy(valid)
            row[key] = value
            self.assertFalse(academic.row_is_healthy(row, "2026-10-01"), key)

    def test_zero_candidates_and_isolated_failure_remain_valid(self):
        rows = [evidenced_row({"source_id": name, "result": "checked", "retrieval_status": "success",
                              "parse_status": "success", "window_status": "empty", "candidate_count": 0})
                for name in ["aps-pra", "nature-machine-learning"]]
        rows.append({"source_id": "openreview", "result": "blocked"})
        ledger = {"academic_search_version": 4, "date_range": "2026-10-01", "rows": rows,
                  "family_gate": academic.family_gate(rows, coverage_window="2026-10-01")}
        self.assertEqual(academic_search_venues({"academic_search": ledger}, coverage_contract_version=3)[3], [])
        rows.append(deepcopy(rows[0]))
        self.assertIn("academic source identities are duplicated",
                      academic_search_venues({"academic_search": ledger}, coverage_contract_version=3)[3])

    def test_late_old_positive_cannot_replace_new_negative(self):
        with self.remote_fixture() as (root, day, config, remote):
            old = orchestration.inspect(day, online=True, record_remote=True)
            remote.return_value = {"status": "mismatch"}
            newer = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(newer, True)
            orchestration._record(old, True)
            queue = orchestration.workflow_queue(day)
            self.assertFalse(queue["final_response_allowed"])
            self.assertEqual(queue["dates"][0]["last_remote_attempt"]["status"], "mismatch")
            remote.return_value = {"status": "verified"}
            restored = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(restored, True)
            self.assertTrue(orchestration.workflow_queue(day)["final_response_allowed"])

    def test_pending_attempt_and_deployment_change_invalidate_cached_completion(self):
        with self.remote_fixture() as (root, day, config, remote):
            state = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(state, True)
            self.assertTrue(orchestration.workflow_queue(day)["final_response_allowed"])
            config["bucket"] = "another"
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])
            config["bucket"] = "public"
            orchestration._begin_remote_attempt(day, root, True)
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])

    def test_unavailable_observation_survives_offline_record(self):
        with self.remote_fixture() as (root, day, config, remote):
            positive = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(positive, True)
            remote.side_effect = OSError
            state = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(state, True)
            offline = orchestration.inspect(day)
            orchestration._record(offline, True)
            self.assertEqual(offline["last_remote_attempt"]["status"], "unavailable")
            self.assertEqual(offline["last_remote_verification"]["status"], "verified")
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])

    def test_verified_remote_without_matching_receipt_remains_pending(self):
        with self.remote_fixture() as (root, day, config, remote):
            (root / "_publish" / ("oss_publish_receipt_" + day + ".json")).unlink()
            state = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(state, True)
            self.assertEqual(state["remote_status"], "verified")
            self.assertEqual(state["phase"], "remote_pending")
            self.assertTrue(state["action_required"])
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(orchestration.main(["status", "--date", day, "--online"]), 2)

    def test_read_only_online_does_not_write_and_network_does_not_hold_lock(self):
        with self.remote_fixture() as (root, day, config, remote):
            def check(*_args):
                with orchestration.release_lock(root, timeout=.1):
                    return {"status": "verified", "homepage_points_to_release": False}
            remote.side_effect = check
            with patch.object(orchestration, "atomic_json", side_effect=AssertionError("read-only write")):
                self.assertEqual(orchestration.inspect(day, online=True)["phase"], "remote_complete")
            self.assertFalse((root / "_automation").exists())

    def test_failed_reservation_does_not_call_network_or_overwrite_state(self):
        with self.remote_fixture() as (root, day, config, remote):
            state = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(state, True)
            path = root / "_automation" / ("orchestration_state_" + day + ".json")
            before = path.read_bytes()
            remote.reset_mock()
            with patch.object(orchestration, "atomic_json", side_effect=PermissionError), redirect_stdout(io.StringIO()):
                self.assertEqual(orchestration.main(["status", "--date", day, "--online", "--record"]), 2)
            remote.assert_not_called()
            self.assertEqual(before, path.read_bytes())

    def test_legacy_proof_requires_recheck_and_corrupt_record_is_preserved(self):
        with self.remote_fixture() as (root, day, config, remote):
            path = root / "_automation" / ("orchestration_state_" + day + ".json")
            path.parent.mkdir()
            path.write_text(json.dumps({"last_remote_verification": {"html_sha256": hashlib.sha256(b"reviewed").hexdigest()}}), encoding="utf-8")
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])
            path.write_bytes(b"{corrupt")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(orchestration.main(["status", "--date", day, "--record"]), 2)
            self.assertEqual(path.read_bytes(), b"{corrupt")

    def test_explicitly_recorded_readonly_negative_supersedes_durable_success(self):
        with self.remote_fixture() as (root, day, config, remote):
            positive = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(positive, True)
            remote.return_value = {"status": "mismatch"}
            negative = orchestration.inspect(day, online=True)
            orchestration._record(negative, True)
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])
            self.assertEqual(negative["last_remote_attempt"]["status"], "mismatch")

    def test_late_readonly_positive_cannot_clear_newer_durable_negative(self):
        with self.remote_fixture() as (root, day, config, remote):
            positive = orchestration.inspect(day, online=True)
            remote.return_value = {"status": "mismatch"}
            negative = orchestration.inspect(day, online=True, record_remote=True)
            orchestration._record(negative, True)
            orchestration._record(positive, True)
            self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])

    def test_halted_recovery_is_preserved_by_record_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(orchestration, "NEWS_ROOT", root):
                command = orchestration._collector_command("social", "2026-10-02", root / "output.json")
                args = hot.parse_args(command[3:])
                recovery = {"budget_level": 2, "failure": "pagination_budget_exhausted", "action_required": True}
                checkpoints.save_checkpoint(args.checkpoint, hot.api_scope(args), {"recovery": recovery})
                with patch.object(orchestration, "inspect_network", side_effect=AssertionError("halted network")), \
                        redirect_stdout(io.StringIO()) as captured:
                    self.assertEqual(orchestration.main(["resume", "--date", "2026-10-02", "--record"]), 2)
                state = json.loads(captured.getvalue())
                self.assertEqual(state["collection_recovery"]["social"], recovery)
                self.assertEqual(state["failures"][0]["code"], "pagination_budget_exhausted")

    def test_checkpoint_size_failure_preserves_previous_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            checkpoints.save_checkpoint(path, {}, {"ok": 1})
            before = path.read_bytes()
            with patch.object(checkpoints, "MAX_CHECKPOINT_BYTES", 200):
                with self.assertRaisesRegex(ValueError, "checkpoint_too_large"):
                    checkpoints.save_checkpoint(path, {}, {"oversize": "x" * 1000})
            self.assertEqual(path.read_bytes(), before)

    def pagination_args(self, path, budget=3):
        day = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        return Namespace(coverage_date=day, mode="selected", take=50, category=None, since=None,
                         query=None, checkpoint=path, budget_seconds=budget)

    def page_response(self, args, url, page, total):
        body = json.dumps({"items": [{"id": str(page), "publishedAt": args.coverage_date + "T12:00:00+08:00"}],
                           "hasNext": page < total, "nextCursor": str(page + 1) if page < total else None})
        return body, {"query_url": url, "final_url": url, "status_code": 200,
                      "response_hash": hashlib.sha256(body.encode()).hexdigest(),
                      "retrieved_at": datetime.now(timezone.utc).isoformat()}

    def test_budget_cap_stops_requests_and_exposes_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.pagination_args(Path(directory) / "pages.json")
            elapsed, requests = [0.0], []
            def fetch(url):
                elapsed[0] += 1
                page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("cursor", ["1"])[0])
                requests.append(page)
                return self.page_response(args, url, page, 20)
            with patch.object(hot.monotonic_clock, "monotonic", side_effect=lambda: elapsed[0]), \
                    patch.object(hot, "fetch_response", side_effect=fetch):
                runs = [hot.api_items(args)[1] for _ in range(3)]
                before = list(requests)
                stopped = hot.api_items(args)[1]
            self.assertEqual(requests, before)
            self.assertEqual([run["recovery"]["budget_seconds"] for run in runs], [3, 6, 12])
            self.assertEqual(stopped["failure"], "pagination_budget_exhausted")
            self.assertTrue(stopped["recovery"]["action_required"])

    def test_repeated_network_failure_stops_and_query_change_starts_new_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.pagination_args(Path(directory) / "pages.json")
            with patch.object(hot, "fetch_response", side_effect=OSError("transport")) as fetch:
                for _ in range(3):
                    _, state = hot.api_items(args)
                self.assertEqual(state["failure"], "checkpoint_no_progress")
                before = fetch.call_count
                hot.api_items(args)
                self.assertEqual(fetch.call_count, before)
                args.query = "different explicit query"
                hot.api_items(args)
                self.assertGreater(fetch.call_count, before)

    def test_complete_checkpoint_is_fully_revalidated_without_duplicate_scan(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.pagination_args(Path(directory) / "pages.json", 200)
            def fetch(url):
                page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("cursor", ["1"])[0])
                return self.page_response(args, url, page, 4)
            with patch.object(hot, "fetch_response", side_effect=fetch) as request:
                first, _ = hot.api_items(args)
                request.reset_mock()
                second, state = hot.api_items(args)
            self.assertEqual(first, second)
            self.assertEqual(request.call_count, 4)
            self.assertEqual(state["recovery"]["new_pages"], 0)
            self.assertEqual(state["recovery"]["revalidated_pages"], 4)
            self.assertTrue(state["pagination_complete"])

    def test_parent_watchdog_covers_escalated_social_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, s = fixtures()
            paths = orchestration.collection_paths("2026-10-02", root)
            paths["academic"].parent.mkdir(parents=True)
            paths["academic"].write_text(json.dumps(a), encoding="utf-8")
            with patch.object(orchestration, "NEWS_ROOT", root):
                command = orchestration._collector_command("social", "2026-10-02", paths["social"])
                args = hot.parse_args(command[3:])
                checkpoints.save_checkpoint(args.checkpoint, hot.api_scope(args), {"recovery": {"budget_level": 2}})
                def collect(command, **kwargs):
                    self.assertEqual(kwargs["timeout"], 870)
                    Path(command[-1]).write_text(json.dumps(s), encoding="utf-8")
                    return Namespace(returncode=0)
                with patch.object(orchestration, "inspect_network", return_value={"status": "ready"}), \
                        patch.object(orchestration.subprocess, "run", side_effect=collect):
                    self.assertEqual(orchestration._collect("2026-10-02")["phase"], "collection_ready")

    def test_contradictory_academic_evidence_never_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, s = fixtures()
            for row in a["rows"]:
                row.update(coverage_window="2010-01-01", evidence={"status_code": 403,
                           "query_url": "https://invalid.example/list", "final_url": "https://invalid.example/list",
                           "response_hash": "", "retrieved_at": "2010-01-01T00:00:00Z"})
            a["family_gate"] = academic.family_gate(a["rows"])
            paths = orchestration.collection_paths("2026-10-02", root)
            paths["academic"].parent.mkdir(parents=True)
            paths["academic"].write_text(json.dumps(a), encoding="utf-8")
            paths["social"].write_text(json.dumps(s), encoding="utf-8")
            state = orchestration.inspect("2026-10-02", news_root=root)
            self.assertEqual(state["phase"], "collection_invalid")
            self.assertNotEqual(state["packet_status"], "valid")

    def test_negative_remote_blocks_old_success_and_online_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            day = "2026-10-02"
            output = root / day
            output.mkdir()
            (output / ("daily_pipeline_manifest_" + day + ".json")).write_text('{"status":"complete"}', encoding="utf-8")
            body = b"reviewed html"
            (output / ("briefing_reader_" + day + ".html")).write_bytes(body)
            digest = hashlib.sha256(body).hexdigest()
            receipt = root / "_publish" / ("oss_publish_receipt_" + day + ".json")
            receipt.parent.mkdir()
            receipt.write_text(json.dumps({"html_sha256": digest}), encoding="utf-8")
            with patch.object(orchestration, "NEWS_ROOT", root), \
                    patch.object(orchestration, "verify_artifacts", return_value={"status": "pass"}), \
                    patch("publish_daily_to_oss.load_config", return_value={}), \
                    patch("publish_daily_to_oss.inspect_public_release", return_value={"status": "verified"}) as remote:
                state = orchestration.inspect(day, online=True)
                orchestration._record(state, True)
                self.assertTrue(orchestration.workflow_queue(day)["final_response_allowed"])
                remote.return_value = {"status": "mismatch"}
                state = orchestration.inspect(day, online=True)
                orchestration._record(state, True)
                self.assertFalse(orchestration.workflow_queue(day)["final_response_allowed"])
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(orchestration.main(["status", "--date", day, "--online"]), 2)

    def finalize(self, remote, write_failure=False, publish_status="published", required=True):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stage = root / "2026-10-02" / ".staging" / "run"
            stage.mkdir(parents=True)
            (stage / "daily_pipeline_manifest_2026-10-02.json").write_text(json.dumps({
                "date": "2026-10-02", "pipeline_version": 4}), encoding="utf-8")
            with patch.object(pipeline, "_commit_local", return_value={"status": "complete", "output_dir": str(root / "2026-10-02")}), \
                    patch.object(pipeline, "publication_layout", return_value=(root / "2026-10-02", root / "_index/story_index.jsonl")), \
                    patch("publish_daily_to_oss.auto_publish_after_finalize", return_value={"status": publish_status}), \
                    patch.object(orchestration, "inspect", return_value={"date": "2026-10-02", "phase": "remote_complete" if remote == "verified" else "remote_pending", "remote_status": remote}), \
                    patch.object(orchestration, "_record", side_effect=PermissionError if write_failure else None), \
                    redirect_stdout(io.StringIO()) as captured:
                code = pipeline.cmd_finalize(Namespace(run_dir=str(stage), require_remote=required))
            return code, json.loads(captured.getvalue())

    def test_require_remote_rejects_final_mismatch(self):
        code, output = self.finalize("mismatch")
        self.assertEqual(code, 2)
        self.assertNotEqual(output["status"], "complete")

    def test_require_remote_rejects_checkpoint_write_failure(self):
        code, output = self.finalize("verified", True)
        self.assertEqual(code, 2)
        self.assertNotEqual(output["status"], "complete")

    def test_finalize_success_and_local_only_have_explicit_outcomes(self):
        code, output = self.finalize("verified")
        self.assertEqual(code, 0)
        self.assertEqual(output["local_status"], "complete")
        self.assertEqual(output["remote_verification"]["remote_status"], "verified")
        code, output = self.finalize("not_checked", publish_status="disabled", required=False)
        self.assertEqual(code, 0)
        self.assertEqual(output["remote_publish"]["status"], "disabled")
        for status in ["disabled", "unknown", "pending", "failed"]:
            self.assertEqual(self.finalize("verified", publish_status=status)[0], 2, status)
        self.assertEqual(self.finalize("verified", publish_status="unknown", required=False)[0], 2)

    def test_optional_publish_still_rejects_attempted_remote_failure(self):
        self.assertEqual(self.finalize("unavailable", required=False)[0], 2)
        self.assertEqual(self.finalize("verified", True, required=False)[0], 2)

    def test_paginated_resume_makes_bounded_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            day = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
            args = Namespace(coverage_date=day, mode="selected", take=50, category=None, since=None,
                             query=None, checkpoint=Path(directory) / "pages.json", budget_seconds=3)
            elapsed, requests = [0.0], []
            def fetch(url):
                elapsed[0] += 1
                page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("cursor", ["1"])[0])
                requests.append(page)
                body = json.dumps({"items": [{"id": str(page), "publishedAt": day + "T12:00:00+08:00"}],
                                   "hasNext": page < 4, "nextCursor": str(page + 1) if page < 4 else None})
                return body, {"query_url": url, "final_url": url, "status_code": 200,
                              "response_hash": hashlib.sha256(body.encode()).hexdigest(),
                              "retrieved_at": datetime.now(timezone.utc).isoformat()}
            with patch.object(hot.monotonic_clock, "monotonic", side_effect=lambda: elapsed[0]), \
                    patch.object(hot, "fetch_response", side_effect=fetch):
                hot.api_items(args)
                items, evidence = hot.api_items(args)
            self.assertIn(4, requests)
            self.assertTrue(evidence["pagination_complete"])
            self.assertEqual(len(items), 4)
