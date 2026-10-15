"""HTTP display eligibility; all transport and cloud access are mocked."""
import io
import json
from email.message import Message
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))
import publish_daily_to_oss as publisher


class Response:
    def __init__(self, url, rows, body=b"<html>approved bytes</html>"):
        self.url, self.body, self.status = url, body, 200
        self.headers = Message()
        self.headers["Content-Type"] = "text/html; charset=utf-8"
        for name, value in rows:
            self.headers[name] = value
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        self.reads += 1
        return self.body[:limit]


class RenderHeadersTests(unittest.TestCase):
    url = "https://example.org/index.html"

    def rejected(self, rows, code):
        response = Response(self.url, rows)
        with patch.object(publisher, "urlopen", return_value=response):
            with self.assertRaises(publisher.PublishError) as caught:
                publisher.fetch_html(self.url)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(response.reads, 0)

    def test_observed_oss_response_rejected_despite_html_mime(self):
        self.rejected([("Content-Disposition", "attachment"),
                       ("x-oss-force-download", "true"),
                       ("x-oss-ec", "0048-00000001")], "html_forced_download")

    def test_inline_metadata_does_not_override_service_force_download(self):
        self.rejected([("Content-Disposition", "inline"),
                       ("X-OSS-Force-Download", " TRUE ")], "html_forced_download")

    def test_attachment_is_rejected_without_oss_force_header(self):
        self.rejected([("Content-Disposition", ' ATTACHMENT; filename="daily.html"')],
                      "html_attachment")

    def test_duplicate_disposition_cannot_hide_attachment(self):
        self.rejected([("Content-Disposition", "inline"),
                       ("Content-Disposition", "attachment")], "html_attachment")

    def test_conflicting_force_headers_cannot_hide_true(self):
        self.rejected([("x-oss-force-download", "false"),
                       ("x-oss-force-download", "true")], "html_forced_download")

    def test_ambiguous_headers_do_not_claim_inline_eligibility(self):
        for rows, code in [
            ([("Content-Disposition", "inline, attachment")], "html_disposition_invalid"),
            ([("Content-Disposition", "")], "html_disposition_invalid"),
            ([("x-oss-force-download", "false, true")], "html_force_download_invalid"),
            ([("x-oss-force-download", "")], "html_force_download_invalid"),
        ]:
            with self.subTest(rows=rows):
                self.rejected(rows, code)

    def test_plain_and_explicit_inline_keep_exact_bytes_and_interface(self):
        for rows in [[], [("Content-Disposition", 'inline; filename="daily.html"')],
                     [("x-oss-force-download", "false")]]:
            with self.subTest(rows=rows):
                response = Response(self.url, rows)
                with patch.object(publisher, "urlopen", return_value=response):
                    self.assertEqual(publisher.fetch_html(self.url), (self.url, response.body))

    def config(self, root):
        path = root / "news_publish.local.json"
        path.write_text(json.dumps({"site_index_url": self.url, "bucket": "example-bucket",
                                    "region": "cn-hongkong", "object_prefix": "",
                                    "ossutil_profile": "test-profile"}), encoding="utf-8")
        return path

    def test_doctor_explains_inline_block_without_writing_state_or_cloud_query(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            config = self.config(root)
            state, _ = publisher.locations(config)
            state.parent.mkdir(parents=True)
            state.write_bytes(b'{"version":1,"enabled":true}')
            original = state.read_bytes()
            response = Response(self.url, [("x-oss-force-download", "true")])
            with patch.object(publisher.shutil, "which", return_value="ossutil"), \
                    patch.object(publisher, "urlopen", return_value=response) as transport, \
                    patch.object(publisher, "check_bucket_binding") as bucket:
                result = publisher.doctor(config)
            self.assertEqual(result["code"], "inline_http_blocked")
            self.assertEqual(result["reason_code"], "html_forced_download")
            self.assertEqual(result["browser_display_status"], "not_tested")
            self.assertEqual(transport.call_count, 1)
            bucket.assert_not_called()
            self.assertEqual(state.read_bytes(), original)

    def test_doctor_ready_does_not_claim_actual_browser_pass(self):
        with tempfile.TemporaryDirectory() as name:
            config = self.config(Path(name))
            with patch.object(publisher.shutil, "which", return_value="ossutil"), \
                    patch.object(publisher, "checked_site", return_value=(self.url, b"<html>x</html>")), \
                    patch.object(publisher, "check_bucket_binding"):
                result = publisher.doctor(config)
            self.assertEqual(result["status"], "ready")
            self.assertEqual(result["browser_display_status"], "not_tested")
            self.assertEqual(result["inline_http_status"], "eligible")

    def test_enable_rejects_download_route_and_publish_never_uploads(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            config = self.config(root)
            response = Response(self.url, [("x-oss-force-download", "true")])
            with patch.object(publisher, "urlopen", return_value=response), \
                    patch.object(publisher, "check_bucket_binding") as bucket:
                self.assertEqual(publisher.enable(config)["status"], "disabled")
            bucket.assert_not_called()
            publisher.set_state(publisher.locations(config)[0], enabled=True, reason="fixture",
                                identity=publisher.deployment_id(publisher.load_config(config)))
            with patch.object(publisher, "urlopen", return_value=response), \
                    patch.object(publisher, "upload_file") as upload, \
                    patch.object(publisher, "verified_release") as eligibility:
                self.assertEqual(publisher.publish(root / "news/2026-10-12", config)["status"], "disabled")
            upload.assert_not_called()
            eligibility.assert_not_called()


if __name__ == "__main__":
    unittest.main()
