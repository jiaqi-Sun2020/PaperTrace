"""Adversarial interruption, stale cache and partial recovery checks, offline only."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import tempfile
import time
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import academic_venue_sweep as sweep
import aihot_candidates as hot
import collection_checkpoint as checkpoints
import source_capture as capture
import orchestrate_daily as orchestration
from academic_sources import family_gate, health_table
from evidence_fixtures import evidenced_row


class CheckpointTests(unittest.TestCase):
    def test_checksum_scope_corruption_and_atomic_interruption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            checkpoints.save_checkpoint(path, {"day": "2026-10-02"}, {"rows": {"x": 1}})
            before = path.read_bytes()
            self.assertEqual(checkpoints.load_checkpoint(path, {"day": "2026-10-03"}), {})
            with patch.object(checkpoints.os, "replace", side_effect=PermissionError):
                with self.assertRaises(PermissionError):
                    checkpoints.save_checkpoint(path, {"day": "2026-10-02"}, {"rows": {"x": 2}})
            self.assertEqual(path.read_bytes(), before)
            value = json.loads(before)
            value["payload"]["rows"]["x"] = 2
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(checkpoints.load_checkpoint(path, {"day": "2026-10-02"}), {})

    def test_academic_checkpoint_survives_failed_optional_and_reuses_core(self):
        plan = sweep.build_plan_v4(["quantum"], "2026-10-01")
        plan["rows"] = [row for row in plan["rows"] if row["source_id"] in {"aps-pra", "openreview", "iop-qst"}]
        calls = []
        def fetch(row, *_args):
            calls.append(row["source_id"])
            if row["source_id"] == "iop-qst":
                raise OSError("optional failure")
            return evidenced_row({**row, "result": "checked", "retrieval_status": "success", "parse_status": "success",
                    "window_status": "matched", "matches": [{"title": "Original", "description": "Preserved"}]}, row["coverage_window"])
        with tempfile.TemporaryDirectory() as directory, patch.object(sweep, "_fetch_v4_row", side_effect=fetch):
            path = Path(directory) / "academic.json"
            first = sweep.fetch_evidence_v4(json.loads(json.dumps(plan)), checkpoint=path)
            self.assertEqual(first["family_gate"]["status"], "pass")
            calls.clear()
            second = sweep.fetch_evidence_v4(json.loads(json.dumps(plan)), checkpoint=path)
            self.assertEqual(calls, ["iop-qst"])
            self.assertEqual(first["rows"], second["rows"])
            changed = json.loads(json.dumps(plan))
            changed["date_range"] = "2026-10-02"
            calls.clear()
            sweep.fetch_evidence_v4(changed, checkpoint=path)
            self.assertEqual(len(calls), 3)

    def test_global_deadline_prevents_retry_wait_and_request_after_expiry(self):
        sweep._REQUEST_BUDGET.deadline = time.monotonic() + 0.02
        try:
            with patch.object(sweep, "_request_evidence", return_value=({"status_code": 429, "retry_after": "30"}, b"")) as request:
                sweep._request_source_with_retry("https://example.org/", 30)
                self.assertEqual(request.call_count, 1)
            sweep._REQUEST_BUDGET.deadline = time.monotonic() - 1
            with patch.object(sweep, "_request_evidence", side_effect=AssertionError("network after deadline")):
                self.assertEqual(sweep._request_source_with_retry("https://example.org/", 30)[0]["error"], "collection_deadline")
        finally:
            del sweep._REQUEST_BUDGET.deadline

    def test_health_impact_uses_aggregate_family(self):
        rows = [{"source_id": key, "result": "checked", "retrieval_status": "success",
                 "parse_status": "success", "window_status": "matched"} for key in ["aps-pra", "jmlr"]]
        rows = [evidenced_row(row) for row in rows]
        rows.append({"source_id": "openreview", "result": "error"})
        self.assertEqual(family_gate(rows)["status"], "pass")
        self.assertEqual(health_table(rows)[-1]["impact"], "isolated")

    def test_process_kill_keeps_completed_family_aggregate(self):
        # Real child termination, scaled time; transport is replaced completely.
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "collector.py"
            output = Path(directory) / "aggregate.json"
            checkpoint = Path(directory) / "checkpoint.json"
            script.write_text('''import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import academic_venue_sweep as s
plan = s.build_plan_v4(["quantum"], "2026-10-01")
plan["rows"] = [r for r in plan["rows"] if r["source_id"] in {"aps-pra", "openreview", "iop-qst"}]
def fetch(row, *_args):
    if row["source_id"] == "iop-qst": time.sleep(10)
    return dict(row, result="checked", retrieval_status="success", parse_status="success", window_status="matched", coverage_claim="discovery_only", candidate_count=0, quarantined_count=0, matches=[], evidence={"query_url": row["search_url"], "final_url": row["search_url"], "status_code": 200, "retrieved_at": "2026-10-02T01:00:00+00:00", "response_hash": "a"*64})
s._fetch_v4_row = fetch
s.fetch_evidence_v4(plan, checkpoint=Path(sys.argv[2]), progress_output=Path(sys.argv[3]))
''', encoding="utf-8")
            process = subprocess.Popen([sys.executable, "-B", str(script), str(Path(sweep.__file__).parent),
                                        str(checkpoint), str(output)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            observed = None
            try:
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    try:
                        value = json.loads(output.read_text(encoding="utf-8"))
                        if value.get("family_gate", {}).get("status") == "pass":
                            observed = value
                            break
                    except (OSError, ValueError): pass
                    time.sleep(0.02)
                self.assertIsNotNone(observed)
                self.assertFalse(observed["collection_complete"])
            finally:
                process.kill()
                process.wait(timeout=3)
            raw, _ = orchestration.read_source(output, "academic", "2026-10-02")
            self.assertEqual(raw["family_gate"]["status"], "pass")
            self.assertEqual(json.loads(checkpoint.read_text(encoding="utf-8"))["payload"]["rows"].keys(),
                             {"aps-pra", "openreview"})

    def test_jmlr_year_only_dates_remain_unhealthy(self):
        plan = sweep.build_plan_v4(["quantum"], "2026-10-01")
        row = next(row for row in plan["rows"] if row["source_id"] == "jmlr")
        source = next(source for source in sweep.load_registry()["sources"] if source["source_id"] == "jmlr")
        body = b"<rss><channel><item><title>Quantum learning</title><link>http://jmlr.org/papers/v27/x.html</link><pubDate>2026</pubDate><description>Original details</description></item></channel></rss>"
        with patch.object(sweep, "_request_source_with_retry", return_value=({"status_code": 200}, body)):
            result = sweep._fetch_v4_row(row, source, ["quantum"], {"2026-10-01"}, 1)
        self.assertEqual(result["structured_candidate_count"], 1)
        self.assertEqual(result["discovery_records"][0]["pubDate"], "2026")
        self.assertNotIn("published_at", result["discovery_records"][0])
        self.assertEqual(family_gate([result])["status"], "fail")

    def test_collector_preserves_more_than_one_hundred_matches(self):
        plan = sweep.build_plan_v4(["quantum"], "2026-10-01")
        row = next(row for row in plan["rows"] if row["source_id"] == "nature-machine-learning")
        source = next(source for source in sweep.load_registry()["sources"] if source["source_id"] == row["source_id"])
        body = ('<rss><channel>' + ''.join('<item><title>Quantum %s</title><pubDate>2026-10-01T01:00:00+00:00</pubDate><link>https://www.nature.com/articles/%s</link></item>' % (i, i) for i in range(150)) + '</channel></rss>').encode()
        with patch.object(sweep, "_request_source_with_retry", return_value=({"status_code": 200}, body)):
            result = sweep._fetch_v4_row(row, source, ["quantum"], {"2026-10-01"}, 1)
        self.assertEqual(result["candidate_count"], 150)
        self.assertEqual(len(result["matches"]), 150)

    def test_queue_keeps_pending_dates_and_does_not_cover_other_history(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(orchestration, "NEWS_ROOT", Path(directory)):
            first = orchestration.workflow_queue("2026-10-01", record=True)
            second = orchestration.workflow_queue("2026-10-03", record=True)
            self.assertEqual([state["date"] for state in second["dates"]], ["2026-10-01", "2026-10-03"])
            self.assertEqual(second["next_date"], "2026-10-01")
            self.assertFalse(second["final_response_allowed"])
            self.assertEqual(first["terminal_blocker"], None)
            saved = Path(directory) / "_automation" / "workflow_queue.json"
            before = saved.read_bytes()
            orchestration.workflow_queue("2026-10-03", record=True)
            self.assertEqual(saved.read_bytes(), before)

    def test_read_only_queue_does_not_take_a_write_lock(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(orchestration, "NEWS_ROOT", Path(directory)), \
                patch.object(orchestration, "release_lock", side_effect=AssertionError("read-only lock write")):
            state = orchestration.workflow_queue("2026-10-03")
            self.assertEqual(state["phase"], "workflow_pending")
            self.assertFalse((Path(directory) / "_index").exists())

    def test_record_preserves_previous_verification_but_does_not_call_it_current(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {"date": "2026-10-02", "phase": "remote_complete", "html_sha256": "a"*64,
                     "remote_status": "verified", "local_verified": True, "receipt_matches_local": True}
            state["remote_attempt"] = {"date": state["date"], "status": "verified", "html_sha256": "a"*64,
                                       "started_at": "2026-10-02T01:00:00Z"}
            offline = {**state, "phase": "remote_pending", "remote_status": "not_checked", "action_required": True}
            offline.pop("remote_attempt")
            with patch.object(orchestration, "inspect", side_effect=lambda *_args, **_kwargs: dict(offline)):
                orchestration._record(state, True, news_root=root)
                self.assertEqual(state["phase"], "remote_complete")
                next_state = dict(offline)
                orchestration._record(next_state, True, news_root=root)
                self.assertEqual(next_state["phase"], "remote_pending")
                self.assertEqual(next_state["last_remote_verification"]["html_sha256"], "a"*64)


class PaginationTests(unittest.TestCase):
    def args(self, path):
        day = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        return argparse.Namespace(coverage_date=day, mode="selected", take=50, category=None,
                                  since=None, query=None, checkpoint=path, budget_seconds=200)

    def response(self, url, items, cursor=None):
        body = json.dumps({"items": items, "hasNext": bool(cursor), "nextCursor": cursor})
        return body, {"query_url": url, "final_url": url, "status_code": 200,
                      "response_hash": hashlib.sha256(body.encode()).hexdigest(),
                      "retrieved_at": datetime.now(timezone.utc).isoformat()}

    def test_partial_pagination_resume_preserves_ids_and_first_page_change_restarts(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory) / "social.json")
            item1 = {"id": "one", "publishedAt": args.coverage_date + "T12:00:00+08:00"}
            item2 = {"id": "two", "publishedAt": args.coverage_date + "T13:00:00+08:00"}
            urls = []
            def partial(url):
                urls.append(url)
                if "cursor=" in url:
                    raise OSError("interrupted")
                return self.response(url, [item1], "next")
            with patch.object(hot, "fetch_response", side_effect=partial):
                items, evidence = hot.api_items(args)
            self.assertEqual(items, [item1])
            self.assertFalse(evidence["pagination_complete"])
            self.assertEqual(evidence["coverage_status"], "partial")
            urls.clear()
            def resumed(url):
                urls.append(url)
                return self.response(url, [item2]) if "cursor=" in url else self.response(url, [item1], "next")
            with patch.object(hot, "fetch_response", side_effect=resumed):
                items, evidence = hot.api_items(args)
            self.assertEqual(items, [item1, item2])
            self.assertTrue(evidence["pagination_complete"])
            self.assertEqual(len(urls), 2)
            changed = {**item1, "id": "changed"}
            with patch.object(hot, "fetch_response", side_effect=lambda url: self.response(url, [changed])):
                items, evidence = hot.api_items(args)
            self.assertEqual(items, [changed])
            self.assertEqual(evidence["retrieved_count"], 1)

    def test_malformed_record_cannot_be_filtered_into_verified_scan(self):
        args = self.args(None)
        with patch.object(hot, "fetch_response", side_effect=lambda url: self.response(url, [None])):
            _, evidence = hot.api_items(args)
        self.assertFalse(evidence["pagination_complete"])

    def test_middle_page_change_restarts_even_when_first_page_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.args(Path(directory) / "social.json")
            items = [{"id": key, "publishedAt": args.coverage_date + "T12:00:00+08:00"}
                     for key in ["one", "two", "three", "changed"]]
            def old(url):
                if "cursor=third" in url: raise OSError("interrupted")
                return self.response(url, [items[1]], "third") if "cursor=second" in url else self.response(url, [items[0]], "second")
            with patch.object(hot, "fetch_response", side_effect=old):
                _, evidence = hot.api_items(args)
            self.assertFalse(evidence["pagination_complete"])
            def changed(url):
                if "cursor=third" in url: return self.response(url, [items[2]])
                return self.response(url, [items[3]], "third") if "cursor=second" in url else self.response(url, [items[0]], "second")
            with patch.object(hot, "fetch_response", side_effect=changed):
                restored, evidence = hot.api_items(args)
            self.assertEqual([item["id"] for item in restored], ["one", "changed", "three"])
            self.assertTrue(evidence["pagination_complete"])

    def test_api_body_is_bounded_and_deadline_prevents_network(self):
        old = hot._HTTP_DEADLINE
        hot._HTTP_DEADLINE = time.monotonic() - 1
        try:
            with patch.object(hot.urllib.request, "urlopen", side_effect=AssertionError("late request")):
                with self.assertRaises(TimeoutError): hot.fetch_response("https://example.org/")
        finally:
            hot._HTTP_DEADLINE = old


class CaptureRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.config = self.root / "candidate.json"
        self.items = [{"id": key, "source_url": "https://example.org/" + key,
                       "source_excerpt": "Original claim", "source_class": "official"} for key in ["bad", "good"]]
        self.config.write_text(json.dumps({"sections": [{"items": self.items}]}), encoding="utf-8")
    def tearDown(self): self.directory.cleanup()
    def response(self, request, timeout):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *_args): pass
            def read(self, maximum): return b"<p>Original claim</p>"
            def geturl(self): return request.full_url
        return Response()
    def test_first_failure_isolated_and_good_capture_reused_without_network(self):
        def opened(request, timeout):
            if request.full_url.endswith("bad"): raise OSError("failure")
            return self.response(request, timeout)
        with patch.object(capture, "public_https"), patch.object(capture, "build_opener") as opener:
            opener.return_value.open.side_effect = opened
            report = capture.capture_report(self.config, "2026-10-01", news_root=self.root)
            self.assertEqual(report["status"], "partial")
            self.assertEqual(len(report["captured"]), 1)
        saved = Path(report["captured"][0]).read_bytes()
        with patch.object(capture, "public_https", side_effect=AssertionError("cached DNS/network")):
            report = capture.capture_report(self.config, "2026-10-01", news_root=self.root, item_id="good")
        self.assertEqual(report["status"], "complete")
        self.assertEqual(Path(report["reused"][0]).read_bytes(), saved)
    def test_candidate_mutation_during_fetch_refuses_install(self):
        def opened(request, timeout):
            self.config.write_text('{"sections":[]}', encoding="utf-8")
            return self.response(request, timeout)
        with patch.object(capture, "public_https"), patch.object(capture, "build_opener") as opener:
            opener.return_value.open.side_effect = opened
            report = capture.capture_report(self.config, "2026-10-01", news_root=self.root, item_id="good")
        self.assertEqual(report["status"], "partial")
        self.assertFalse(capture.capture_path(self.root, "2026-10-01", "good").exists())

    def test_concurrent_valid_capture_wins_without_overwrite(self):
        item = self.items[1]
        path = capture.capture_path(self.root, "2026-10-01", "good")
        other = capture.make_capture(item, item["source_url"], item["source_url"], 200,
                                     b"<p>Original claim plus concurrent content</p>", "2026-10-02T01:00:00+00:00")
        def opened(request, timeout):
            checkpoints.atomic_json(path, other)
            return self.response(request, timeout)
        with patch.object(capture, "public_https"), patch.object(capture, "build_opener") as opener:
            opener.return_value.open.side_effect = opened
            report = capture.capture_report(self.config, "2026-10-01", news_root=self.root, item_id="good")
        self.assertEqual(report["captured"], [])
        self.assertEqual(report["reused"], [str(path)])
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), other)
    def test_empty_capture_is_not_ready(self):
        day = "2026-10-02"
        candidate = self.root / "_collection" / day / ("candidate_" + day + ".json")
        candidate.parent.mkdir(parents=True)
        candidate.write_bytes(self.config.read_bytes())
        for item in self.items:
            path = capture.capture_path(self.root, "2026-10-01", item["id"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        state = orchestration.inspect(day, news_root=self.root)
        self.assertEqual(state["phase"], "candidate_waiting_capture")
        self.assertEqual(state["missing_capture_ids"], ["bad", "good"])


if __name__ == "__main__": unittest.main()
