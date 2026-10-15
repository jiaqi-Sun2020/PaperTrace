"""Offline diagnostics, durable retry bounds, and evidence-only admission."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.message import Message
import io
import json
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import source_capture as capture
from collection_checkpoint import atomic_json


class CaptureDiagnosticsTests(unittest.TestCase):
    def test_http_classes_retry_after_and_redaction(self):
        now = datetime(2026, 10, 6, tzinfo=timezone.utc)
        for status, code, retry in ((401, "source_access_denied", False), (403, "source_access_denied", False),
                                    (404, "source_not_found", False), (429, "source_rate_limited", True),
                                    (500, "source_server_error", True), (502, "source_server_error", True)):
            headers = Message(); headers["Retry-After"] = "12"
            error = HTTPError("https://example.org/?token=TOPSECRET", status, "TOPSECRET", headers, io.BytesIO(b"secret response"))
            result = capture.capture_failure(error, "http_request", now)
            self.assertEqual((result["code"], result["retryable"], result["http_status"]), (code, retry, status))
            self.assertNotIn("TOPSECRET", json.dumps(result))
            if status == 429:
                self.assertEqual(result["retry_after_seconds"], 12)
        for delay in ("86400", "Wed, 07 Oct 2026 00:00:00 GMT"):
            headers = Message(); headers["Retry-After"] = delay
            result = capture.capture_failure(HTTPError("https://example.org/", 429, "limited", headers, None), "http_request", now)
            self.assertEqual((result["code"], result["retryable"]), ("source_rate_limit_deferred", False))

    def test_transport_and_local_failures_are_distinct(self):
        now = datetime.now(timezone.utc)
        cases = [(URLError(socket.gaierror("sensitive proxy info")), "dns_validation", "dns_failure", True),
                 (URLError(ConnectionRefusedError()), "http_request", "connection_refused", True),
                 (URLError(ssl.SSLCertVerificationError()), "http_request", "tls_verification_failed", False),
                 (TimeoutError(), "http_request", "transport_timeout", True),
                 (PermissionError(), "install", "environment_permission_denied", False),
                 (OSError(), "install", "local_write_failed", False)]
        for error, stage, code, retry in cases:
            result = capture.capture_failure(error, stage, now)
            self.assertEqual((result["code"], result["stage"], result["retryable"]), (code, stage, retry))
            self.assertNotIn("sensitive", json.dumps(result))


class CaptureAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "candidate.json"
        self.day = "2026-10-05"
        self.now = datetime(2026, 10, 6, tzinfo=timezone.utc)
        self.item = {"id": "N001", "story_id": "story-one", "source_url": "https://example.org/one/",
                     "source_excerpt": "Original claim", "source_class": "official_primary"}
        self.raw = {"source_url_contract_version": 2, "sections": [{"items": [self.item]}]}
        self.write()
        self.opener_patch = patch.object(capture, "build_opener")
        self.opener = self.opener_patch.start().return_value
        self.addCleanup(self.opener_patch.stop)
        self.dns_patch = patch.object(capture, "public_https")
        self.dns_patch.start(); self.addCleanup(self.dns_patch.stop)

    def write(self):
        self.config.write_text(json.dumps(self.raw), encoding="utf-8")

    def report(self, **kwargs):
        return capture.capture_report(self.config, self.day, news_root=self.root, now=kwargs.get("now", self.now))

    def response(self, request, timeout):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, maximum): return b"<title>Article</title><p>Original claim</p>"
            def geturl(self): return request.full_url
        return Response()

    def test_backoff_and_three_attempt_budget_survive_resumes(self):
        self.opener.open.side_effect = URLError(TimeoutError("private host details"))
        for attempt in range(1, 4):
            report = self.report(now=self.now + timedelta(minutes=attempt))
            self.assertEqual(report["failures"][0]["attempts"], attempt)
        calls = self.opener.open.call_count
        report = self.report(now=self.now + timedelta(minutes=5))
        self.assertEqual(report["failures"][0]["code"], "capture_retry_exhausted")
        self.assertEqual(self.opener.open.call_count, calls)
        state = capture._attempt_state(capture._attempt_path(self.root, self.day, self.item))
        self.assertEqual((state["attempts"], len(state["history"])), (3, 3))
        self.assertFalse(capture.capture_path(self.root, self.day, self.item["id"]).exists())

    def test_deferred_retry_does_not_touch_network(self):
        self.opener.open.side_effect = TimeoutError()
        self.report()
        calls = self.opener.open.call_count
        result = self.report(now=self.now + timedelta(seconds=1))
        self.assertEqual(result["failures"][0]["code"], "capture_retry_deferred")
        self.assertEqual(self.opener.open.call_count, calls)

    def test_access_denied_is_not_retried_and_health_records_status(self):
        self.opener.open.side_effect = HTTPError(self.item["source_url"], 403, "secret details", Message(), None)
        self.report()
        result = self.report(now=self.now + timedelta(days=1))
        self.assertEqual(self.opener.open.call_count, 1)
        self.assertEqual(result["failures"][0]["http_status"], 403)
        self.assertEqual(result["source_health"][0]["failures"][0]["http_status"], 403)
        self.assertEqual(result["candidate_admission"]["counts"]["retry_pending"], 1)
        self.assertNotIn("secret details", json.dumps(result))

    def test_new_reference_has_new_attempt_scope_but_old_journal_survives(self):
        self.opener.open.side_effect = HTTPError(self.item["source_url"], 404, "missing", Message(), None)
        self.report()
        old_path = capture._attempt_path(self.root, self.day, self.item)
        old_bytes = old_path.read_bytes()
        self.item["source_url"] += "?edition=2"
        self.write()
        self.opener.open.side_effect = self.response
        result = self.report(now=self.now + timedelta(minutes=1))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(old_path.read_bytes(), old_bytes)
        self.assertEqual(result["candidate_admission"]["counts"]["evidence_valid"], 1)
        record = json.loads(Path(result["captured"][0]).read_text(encoding="utf-8"))
        self.assertEqual(record["requested_url"], self.item["source_url"])

    def test_corrupt_cache_replacement_keeps_exact_backup_and_reuse_is_offline(self):
        path = capture.capture_path(self.root, self.day, self.item["id"])
        path.parent.mkdir(parents=True)
        old = b"corrupted original cache"
        path.write_bytes(old)
        self.opener.open.side_effect = self.response
        result = self.report()
        self.assertEqual(result["status"], "complete")
        backups = list(path.parent.joinpath(".capture_backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), old)
        saved = path.read_bytes()
        self.opener.open.side_effect = AssertionError("unexpected network")
        self.assertEqual(self.report()["status"], "complete")
        self.assertEqual(path.read_bytes(), saved)
        self.assertEqual(len(list(path.parent.joinpath(".capture_backups").iterdir())), 1)

    def test_every_candidate_accounted_across_multiple_sections(self):
        good = deepcopy(self.item)
        pending = {**self.item, "id": "N002", "story_id": "story-two"}
        bad = {**self.item, "id": "N003", "story_id": "story-three"}
        unsafe = {**self.item, "id": "N004", "source_url": "http://example.org/unsafe"}
        record = capture.make_capture(good, good["source_url"], good["source_url"], 200, b"<p>Original claim</p>", "2026-10-06T00:00:00Z")
        atomic_json(capture.capture_path(self.root, self.day, "N001"), record)
        atomic_json(capture.capture_path(self.root, self.day, "N003"), {"status_code": 200})
        raw = {"sections": [{"items": [good, pending]}, {"items": [bad, unsafe]}]}
        before = deepcopy(raw)
        result = capture.admit_candidates(raw, self.day, news_root=self.root)
        self.assertEqual(raw, before)
        self.assertEqual(result["candidate_admission"]["counts"], {"evidence_valid": 1, "pending_capture": 1, "retry_pending": 1, "excluded": 1})
        self.assertEqual(len(result["candidate_admission"]["records"]), 4)
        self.assertNotIn("source_capture", result["sections"][1]["items"][0])

    def test_failed_install_keeps_old_cache_and_reports_permission_boundary(self):
        path = capture.capture_path(self.root, self.day, self.item["id"])
        path.parent.mkdir(parents=True)
        path.write_bytes(b"old invalid cache")
        self.opener.open.side_effect = self.response
        original = capture.atomic_json
        def denied(target, value):
            if target == path:
                raise PermissionError("private path details")
            return original(target, value)
        with patch.object(capture, "atomic_json", side_effect=denied):
            result = self.report()
        self.assertEqual(result["failures"][0]["code"], "environment_permission_denied")
        self.assertEqual(path.read_bytes(), b"old invalid cache")
        self.assertEqual(result["candidate_admission"]["counts"]["evidence_valid"], 0)

    def test_corrupt_journal_and_duplicate_identity_fail_closed(self):
        path = capture._attempt_path(self.root, self.day, self.item)
        atomic_json(path, {"version": 1, "attempts": 0, "history": []})
        result = self.report()
        self.assertEqual(result["failures"][0]["code"], "capture_attempt_journal_invalid")
        self.opener.open.assert_not_called()
        self.raw["sections"][0]["items"].append(deepcopy(self.item))
        with self.assertRaises(ValueError):
            capture.admit_candidates(self.raw, self.day, news_root=self.root)

    def test_interrupted_reserved_attempt_cannot_retry_immediately(self):
        path = capture._attempt_path(self.root, self.day, self.item)
        state = capture._attempt_state(path)
        state.update(attempts=1, next_retry_at=(self.now + timedelta(seconds=30)).isoformat())
        capture._save_attempt(path, state)
        self.assertEqual(self.report()["failures"][0]["code"], "capture_retry_deferred")
        self.opener.open.assert_not_called()

    def test_successful_capture_then_corruption_can_be_repaired_within_budget(self):
        self.opener.open.side_effect = self.response
        self.report()
        path = capture.capture_path(self.root, self.day, self.item["id"])
        path.write_bytes(b"later corruption")
        result = self.report(now=self.now + timedelta(minutes=1))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(self.opener.open.call_count, 2)
        self.assertEqual(result["candidate_admission"]["counts"]["evidence_valid"], 1)

    def test_tampered_backup_never_allows_cache_replacement(self):
        path = capture.capture_path(self.root, self.day, self.item["id"])
        path.parent.mkdir(parents=True)
        path.write_bytes(b"original invalid cache")
        backup = path.parent / ".capture_backups" / (path.name + "." + capture.sha(path))
        backup.parent.mkdir(); backup.write_bytes(b"forged backup")
        self.opener.open.side_effect = self.response
        result = self.report()
        self.assertEqual(result["failures"][0]["code"], "capture_backup_digest_mismatch")
        self.assertEqual(path.read_bytes(), b"original invalid cache")

    def test_admission_count_digest_and_selected_binding_are_verified(self):
        self.opener.open.side_effect = self.response
        self.report()
        sha = "a" * 64
        admitted = capture.admit_candidates(self.raw, self.day, news_root=self.root, config_sha256=sha)
        self.assertEqual(capture.validate_admission(admitted, sha), [])
        wrong = deepcopy(admitted); wrong["candidate_admission"]["counts"]["evidence_valid"] = 0
        self.assertEqual(capture.validate_admission(wrong, sha), ["candidate_admission_counts_invalid"])
        wrong = deepcopy(admitted); wrong["candidate_admission"]["records"][0]["capture_sha256"] = "b" * 64
        self.assertEqual(capture.validate_admission(wrong, sha), ["selected_candidate_not_admitted"])
        self.assertEqual(capture.validate_admission(admitted, "b" * 64), ["candidate_admission_binding_invalid"])

    def test_quote_mismatch_is_a_source_evidence_failure_not_network_failure(self):
        self.item["source_excerpt"] = "Not actually in this source"
        self.write(); self.opener.open.side_effect = self.response
        result = self.report()
        self.assertEqual(result["failures"][0]["code"], "source_quote_not_found")
        self.assertFalse(result["failures"][0]["retryable"])
        self.assertFalse(capture.capture_path(self.root, self.day, self.item["id"]).exists())

    def test_unsafe_cached_reference_cannot_report_capture_complete(self):
        self.item["source_url"] = "https://example.org/one/?token=secret"
        self.write()
        record = capture.make_capture(self.item, self.item["source_url"], self.item["source_url"], 200,
            b"<p>Original claim</p>", "2026-10-06T00:00:00Z")
        path = capture.capture_path(self.root, self.day, self.item["id"])
        atomic_json(path, record)
        before = path.read_bytes()
        result = self.report()
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["candidate_admission"]["counts"]["excluded"], 1)
        self.assertEqual(path.read_bytes(), before)
        self.opener.open.assert_not_called()
        self.assertNotIn("secret", json.dumps(result))

    def test_journal_cannot_inject_sensitive_diagnostic_fields(self):
        path = capture._attempt_path(self.root, self.day, self.item)
        state = capture._attempt_state(path)
        state.update(attempts=1, last_result={"code": "transport_failure", "stage": "http_request",
                                            "retryable": True, "headers": "TOPSECRET"})
        capture._save_attempt(path, state)
        result = self.report()
        self.assertEqual(result["failures"][0]["code"], "capture_attempt_journal_invalid")
        self.assertNotIn("TOPSECRET", json.dumps(result))
        self.opener.open.assert_not_called()
