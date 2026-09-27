#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Behavioral checks for opt-in OSS publishing without cloud credentials."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import publish_daily_to_oss as publisher


class OssPublisherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config_path = self.root / "news_publish.local.json"
        self.config = {
            "site_index_url": "https://example.org/index.html",
            "bucket": "example-bucket",
            "region": "cn-hongkong",
            "object_prefix": "",
            "ossutil_profile": "papertrace-publisher",
        }
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.run_dir = self.root / "news" / "2026-09-27"
        self.run_dir.mkdir(parents=True)
        self.html_path = self.run_dir / "briefing_reader_2026-09-27.html"
        self.new_html = b"<!doctype html><html><body>new daily</body></html>"
        self.old_html = b"<!doctype html><html><body>old daily</body></html>"
        self.html_path.write_bytes(self.new_html)
        self.old_index = b'<html><meta http-equiv="refresh" content="0; url=briefing_reader_2026-09-26.html"><a href="briefing_reader_2026-09-26.html">old</a></html>'
        self.new_index = b'<html><meta http-equiv="refresh" content="0; url=briefing_reader_2026-09-27.html"><a href="briefing_reader_2026-09-27.html">new</a></html>'
        bucket_patch = patch.object(publisher, "read_bucket_index", side_effect=lambda _config: self.old_index)
        bucket_patch.start()
        self.addCleanup(bucket_patch.stop)

    def site_fetch(self, url: str) -> tuple[str, bytes]:
        if url == self.config["site_index_url"]:
            return url, self.old_index
        if url.endswith("briefing_reader_2026-09-26.html"):
            return url, self.old_html
        if url.endswith("briefing_reader_2026-09-27.html"):
            return url, self.new_html
        raise AssertionError(url)

    def test_disabled_until_explicit_enable_and_missing_config_fails_closed(self) -> None:
        with patch.object(publisher, "upload_file") as upload:
            self.assertEqual(publisher.publish(self.run_dir, self.config_path)["status"], "disabled")
            upload.assert_not_called()
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            self.assertEqual(publisher.enable(self.config_path)["status"], "enabled")
        self.assertEqual(publisher.status(self.config_path)["status"], "enabled")
        self.config_path.unlink()
        self.assertEqual(publisher.publish(self.run_dir, self.config_path)["status"], "disabled")
        self.assertEqual(publisher.status(self.config_path)["status"], "disabled")

    def test_website_failure_latches_disabled_even_after_recovery(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            publisher.enable(self.config_path)
        with patch.object(publisher, "fetch_html", side_effect=publisher.PublishError("HTTP 403")), patch.object(publisher, "upload_file") as upload:
            result = publisher.publish(self.run_dir, self.config_path)
            self.assertEqual(result["status"], "disabled")
            upload.assert_not_called()
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch), patch.object(publisher, "upload_file") as upload:
            self.assertEqual(publisher.publish(self.run_dir, self.config_path)["status"], "disabled")
            upload.assert_not_called()
            self.assertEqual(publisher.enable(self.config_path)["status"], "enabled")

    def test_wrong_bucket_binding_blocks_enable_and_upload(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch), patch.object(publisher, "read_bucket_index", return_value=b"<html>other site</html>"), patch.object(publisher, "upload_file") as upload:
            result = publisher.enable(self.config_path)
            self.assertEqual(result["status"], "disabled")
            self.assertIn("does not match", result["reason"])
            self.assertEqual(publisher.publish(self.run_dir, self.config_path)["status"], "disabled")
            upload.assert_not_called()

    def test_config_change_requires_manual_reenable(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            publisher.enable(self.config_path)
        self.config["bucket"] = "another-bucket"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.assertEqual(publisher.publish(self.run_dir, self.config_path)["status"], "disabled")

    def test_uploads_html_before_index_and_checks_remote_bytes(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            publisher.enable(self.config_path)
        uploaded: list[str] = []
        def upload(_config: dict[str, str], source: Path, filename: str) -> None:
            uploaded.append(filename)
            if filename == "index.html":
                self.new_index = source.read_bytes()
        def fetch(url: str) -> tuple[str, bytes]:
            if url == self.config["site_index_url"] and uploaded and uploaded[-1] == "index.html":
                return url, self.new_index
            return self.site_fetch(url)
        expected_hash = hashlib.sha256(self.new_html).hexdigest()
        with patch.object(publisher, "verified_release", return_value=("2026-09-27", self.html_path, expected_hash)), patch.object(publisher, "fetch_html", side_effect=fetch), patch.object(publisher, "upload_file", side_effect=upload):
            result = publisher.publish(self.run_dir, self.config_path)
        self.assertEqual(result["status"], "published")
        self.assertEqual(uploaded, [self.html_path.name, "index.html"])
        receipt = self.root / "news" / "_publish" / "oss_publish_receipt_2026-09-27.json"
        self.assertEqual(json.loads(receipt.read_text(encoding="utf-8"))["html_sha256"], expected_hash)

    def test_failed_html_upload_never_updates_index(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            publisher.enable(self.config_path)
        expected_hash = hashlib.sha256(self.new_html).hexdigest()
        with patch.object(publisher, "verified_release", return_value=("2026-09-27", self.html_path, expected_hash)), patch.object(publisher, "fetch_html", side_effect=self.site_fetch), patch.object(publisher, "upload_file", side_effect=publisher.PublishError("upload failed")) as upload:
            with self.assertRaises(publisher.PublishError):
                publisher.publish(self.run_dir, self.config_path)
        self.assertEqual(upload.call_count, 1)

    def test_remote_html_mismatch_latches_disabled_before_index_upload(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            publisher.enable(self.config_path)
        def stale_fetch(url: str) -> tuple[str, bytes]:
            if url.endswith("briefing_reader_2026-09-27.html"):
                return url, self.old_html
            return self.site_fetch(url)
        expected_hash = hashlib.sha256(self.new_html).hexdigest()
        with patch.object(publisher, "verified_release", return_value=("2026-09-27", self.html_path, expected_hash)), patch.object(publisher, "fetch_html", side_effect=stale_fetch), patch.object(publisher, "upload_file") as upload:
            with self.assertRaisesRegex(publisher.PublishError, "did not match"):
                publisher.publish(self.run_dir, self.config_path)
        self.assertEqual(upload.call_count, 1)
        self.assertEqual(publisher.status(self.config_path)["status"], "disabled")

    def test_index_upload_failure_restores_previous_index(self) -> None:
        with patch.object(publisher, "fetch_html", side_effect=self.site_fetch):
            publisher.enable(self.config_path)
        attempts: list[tuple[str, bytes]] = []
        def upload(_config: dict[str, str], source: Path, filename: str) -> None:
            attempts.append((filename, source.read_bytes()))
            if filename == "index.html" and len(attempts) == 2:
                raise publisher.PublishError("index upload failed")
        expected_hash = hashlib.sha256(self.new_html).hexdigest()
        with patch.object(publisher, "verified_release", return_value=("2026-09-27", self.html_path, expected_hash)), patch.object(publisher, "fetch_html", side_effect=self.site_fetch), patch.object(publisher, "upload_file", side_effect=upload):
            with self.assertRaisesRegex(publisher.PublishError, "index upload failed"):
                publisher.publish(self.run_dir, self.config_path)
        self.assertEqual([name for name, _ in attempts], [self.html_path.name, "index.html", "index.html"])
        self.assertEqual(attempts[-1][1], self.old_index)

    def test_site_link_and_config_validation(self) -> None:
        with patch.object(publisher, "fetch_html", return_value=(self.config["site_index_url"], b"<html>no daily link</html>")):
            self.assertEqual(publisher.enable(self.config_path)["status"], "disabled")
        invalid = dict(self.config, access_key="do-not-accept-this-field")
        self.config_path.write_text(json.dumps(invalid), encoding="utf-8")
        with self.assertRaises(publisher.PublishError):
            publisher.load_config(self.config_path)

    def test_generic_object_prefix_matches_site_path(self) -> None:
        self.config["site_index_url"] = "https://example.org/reports/index.html"
        self.config["object_prefix"] = "reports"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        config = publisher.load_config(self.config_path)
        self.assertEqual(publisher.oss_key(config, "index.html"), "reports/index.html")
        self.assertEqual(publisher.oss_key(config, "briefing_reader_2026-09-27.html"), "reports/briefing_reader_2026-09-27.html")

    def test_bucket_check_reads_only_the_configured_index_object(self) -> None:
        config = publisher.load_config(self.config_path)
        def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
            self.assertEqual(command[:3], ["ossutil", "cp", "oss://example-bucket/index.html"])
            self.assertIn("papertrace-publisher", command)
            Path(command[3]).write_bytes(self.old_index)
            return SimpleNamespace(returncode=0)
        with patch.object(publisher.subprocess, "run", side_effect=fake_run):
            self.assertEqual(publisher.read_bucket_index(config), self.old_index)


if __name__ == "__main__":
    unittest.main()
