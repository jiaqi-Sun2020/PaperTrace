"""Controlled preview with real isolated v4 artifacts and mocked cloud transport."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import publish_daily_to_oss as publisher
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_publication_v4 as v4fixtures
reviewed, dp = v4fixtures.reviewed, v4fixtures.dp
import daily_revisions as revisions


class PreviewTests(unittest.TestCase):
    def setUp(self):
        fixture = v4fixtures.V4PublicationTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.prepare()
        self.stage, self.manifest_path, self.manifest = fixture.stage()
        self.root, self.news, self.day = fixture.root, fixture.news, fixture.release
        reviewed.ReviewedReleaseTests._write_reviews(SimpleNamespace(
            stage=self.stage, date=self.day, manifest_path=self.manifest_path))
        self.report_path = self.stage / f"release_preflight_audit_{self.day}.json"
        dp.atomic_json(self.report_path, dp.make_report(self.stage, self.manifest))
        self.config = {"site_index_url": "https://example.org/index.html", "bucket": "example-bucket",
                       "region": "cn-hongkong", "object_prefix": "", "ossutil_profile": "fixture"}
        self.config_path = self.root / "news_publish.local.json"
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
        self.html = self.stage / f"briefing_reader_{self.day}.html"
        self.sha = hashlib.sha256(self.html.read_bytes()).hexdigest()
        self.expected = revisions.run_snapshot(self.news, self.stage)["sha256"]
        self.key = f"_preview/{self.day}/{self.stage.name}/{self.sha}.html"
        self.url = "https://example.org/" + self.key
        self.objects = {}
        self.index_before = (self.news / "_index/story_index.jsonl").read_bytes()
        for name, options in [
            ("checked_site", {"return_value": ("https://example.org/briefing_reader_2026-07-09.html", b"<html>old</html>")}),
            ("check_bucket_binding", {}),
            ("_remote_html", {"side_effect": lambda url: self.objects.get(url)}),
        ]:
            guard = patch.object(publisher, name, **options)
            guard.start()
            self.addCleanup(guard.stop)

    def put(self, config, path, key):
        self.assertEqual(key, self.key)
        self.assertNotIn(self.url, self.objects)
        self.objects[self.url] = path.read_bytes()

    def call(self):
        return publisher.preview(self.stage, self.config_path,
                                 expected_run_sha256=self.expected, expected_html_sha256=self.sha)

    def rebind_fixture(self):
        self.expected = revisions.run_snapshot(self.news, self.stage)["sha256"]

    def test_preseal_cli_uses_real_reviews_without_creating_a_sealed_report(self):
        self.report_path.unlink()
        self.rebind_fixture()
        args=["preview", "--run-dir", str(self.stage), "--config", str(self.config_path),
              "--expected-run-sha256", self.expected, "--expected-html-sha256", self.sha]
        manifest_before=self.manifest_path.read_bytes()
        with patch.object(publisher, "upload_preview_file", side_effect=self.put) as upload, \
                patch.object(dp, "cmd_seal_review") as seal, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(publisher.main(args), 0, output.getvalue())
            self.assertEqual(json.loads(output.getvalue())["status"], "preview_available")
            seal.assert_not_called();upload.assert_called_once()
        self.assertFalse(self.report_path.exists())
        self.assertEqual(self.manifest_path.read_bytes(), manifest_before)
        # Missing authored review remains a real transport gate, even after an
        # exact HTML key already exists remotely. Never manufacture a review.
        (self.stage / f"news_content_review_{self.day}.json").unlink()
        self.rebind_fixture()
        with patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError):self.call()
            upload.assert_not_called()

    def test_formal_bundle_still_requires_report_and_cannot_disable_bound_audit(self):
        self.report_path.unlink()
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False))
        self.assertEqual(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=False,
                                                  require_audit_report=False), [])
        self.assertTrue(publisher.validate_bundle(self.stage, self.manifest, require_manifest_binding=True,
                                                 require_audit_report=False))

    def test_success_repeat_preserves_run_index_reviews_and_publication_state(self):
        with patch.object(publisher, "upload_preview_file", side_effect=self.put) as upload, \
                patch.object(publisher, "upload_file") as formal, \
                patch.object(dp, "cmd_seal_review") as seal, patch.object(dp, "cmd_finalize") as finalize:
            receipt = self.call()
            path = self.news / "_automation" / f"preview_{self.stage.name}_{self.sha}.json"
            before = path.read_bytes(), path.stat().st_mtime_ns
            self.assertEqual(self.call(), receipt)
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)
            self.assertEqual(upload.call_count, 1)
            formal.assert_not_called()
            seal.assert_not_called()
            finalize.assert_not_called()
        self.assertEqual(receipt["status"], "preview_available")
        self.assertIs(receipt["formal_publish"], False)
        self.assertEqual(receipt["browser_display_status"], "not_tested")
        self.assertEqual(revisions.run_snapshot(self.news, self.stage)["sha256"], self.expected)
        self.assertEqual((self.news / "_index/story_index.jsonl").read_bytes(), self.index_before)
        self.assertFalse(publisher.locations(self.config_path)[0].exists())
        self.assertFalse((self.news / "_publish").exists())

    def test_unreviewed_and_failed_claims_cannot_upload(self):
        review = self.stage / f"news_content_review_{self.day}.json"
        data = dp.load_json(review)
        data["items"][0]["claim_reviews"]["facts"]["verdict"] = "fail"
        dp.atomic_json(review, data)
        dp.atomic_json(self.report_path, dp.make_report(self.stage, self.manifest))
        self.rebind_fixture()
        with patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "content_ineligible")
            upload.assert_not_called()

    def test_snapshot_conflict_cannot_upload(self):
        self.html.write_bytes(self.html.read_bytes() + b"external edit")
        with patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "preview_input_conflict")
            upload.assert_not_called()

    def test_preflight_to_commit_change_rejected_without_upload(self):
        def change(config):
            self.html.write_bytes(self.html.read_bytes() + b"new edit")
            return "https://example.org/briefing_reader_2026-07-09.html", b"<html>old</html>"
        with patch.object(publisher, "checked_site", side_effect=change), \
                patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "preview_input_conflict")
            upload.assert_not_called()

    def test_candidate_change_between_preflight_and_commit_rejected(self):
        path = Path(self.manifest["input_config"])
        def change(config):
            path.write_bytes(path.read_bytes() + b" ")
            return "https://example.org/briefing_reader_2026-07-09.html", b"<html>old</html>"
        with patch.object(publisher, "checked_site", side_effect=change), \
                patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "preview_input_conflict")
            upload.assert_not_called()

    def test_unknown_remote_bytes_never_overwritten(self):
        self.objects[self.url] = b"unknown user object"
        with patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "preview_remote_conflict")
            upload.assert_not_called()
        self.assertEqual(self.objects[self.url], b"unknown user object")

    def test_accepted_upload_lost_response_reconciles_before_any_reupload(self):
        def lost(config, path, key):
            self.put(config, path, key)
            raise publisher.PublishError("lost response", code="preview_upload_pending")
        with patch.object(publisher, "upload_preview_file", side_effect=lost) as upload:
            self.assertEqual(self.call()["status"], "preview_available")
            self.assertEqual(self.call()["status"], "preview_available")
            self.assertEqual(upload.call_count, 1)

    def test_unknown_or_corrupt_local_receipt_is_preserved_before_upload(self):
        path = self.news / "_automation" / f"preview_{self.stage.name}_{self.sha}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        for body in [b"corrupt user note", b'{"version":9}']:
            path.write_bytes(body)
            with patch.object(publisher, "upload_preview_file") as upload:
                with self.assertRaises(publisher.PublishError) as caught:
                    self.call()
                self.assertEqual(caught.exception.code, "preview_receipt_conflict")
                upload.assert_not_called()
            self.assertEqual(path.read_bytes(), body)

    def test_changed_run_after_upload_cannot_receive_current_receipt(self):
        def changed(config, path, key):
            self.put(config, path, key)
            self.html.write_bytes(self.html.read_bytes() + b"changed")
        with patch.object(publisher, "upload_preview_file", side_effect=changed):
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "preview_input_conflict")
        self.assertEqual(self.objects[self.url], self.html.read_bytes()[:-7])
        self.assertFalse(list((self.news / "_automation").glob("preview_*.json")))

    def test_duplicate_active_stage_cannot_upload(self):
        (self.stage.parent / f"{self.day}-aaaaaaaaaaaa").mkdir()
        with patch.object(publisher, "upload_preview_file") as upload:
            with self.assertRaises(publisher.PublishError) as caught:
                self.call()
            self.assertEqual(caught.exception.code, "preview_input_conflict")
            upload.assert_not_called()

    def test_default_endpoint_and_http_route_rejected_without_network(self):
        for url in ["http://example.org/index.html",
                    "https://example-bucket.oss-cn-hongkong.aliyuncs.com/index.html"]:
            self.config["site_index_url"] = url
            self.config_path.write_text(json.dumps(self.config), encoding="utf-8")
            with patch.object(publisher, "checked_site") as transport:
                with self.assertRaises(publisher.PublishError) as caught:
                    self.call()
                self.assertEqual(caught.exception.code, "preview_domain_required")
                transport.assert_not_called()

    def test_upload_command_is_scoped_server_nonoverwrite_without_acl_or_secret_flags(self):
        with patch.object(publisher.subprocess, "run", side_effect=[
            SimpleNamespace(returncode=0, stdout="<VersioningConfiguration/>"),
            SimpleNamespace(returncode=0)]) as call:
            publisher.upload_preview_file(self.config, self.html, self.key)
        command = call.call_args.args[0]
        self.assertIn("--forbid-overwrite=true", command)
        self.assertEqual(call.call_count, 2)
        self.assertIn("get-bucket-versioning", call.call_args_list[0].args[0])
        self.assertEqual(command[command.index("--key") + 1], self.key)
        self.assertEqual(command[command.index("--retry-times") + 1], "0")
        self.assertEqual(call.call_args.kwargs["timeout"], 45)
        for forbidden in ("--access-key-id", "--access-key-secret", "--object-acl", "--skip-verify-cert"):
            self.assertNotIn(forbidden, command)
        with self.assertRaises(publisher.PublishError):
            publisher.upload_preview_file(self.config, self.html, "index.html")

    def test_versioning_enabled_suspended_and_unknown_cannot_put(self):
        for body in ["<VersioningConfiguration><Status>Enabled</Status></VersioningConfiguration>",
                     "<VersioningConfiguration><Status>Suspended</Status></VersioningConfiguration>",
                     "<VersioningConfiguration><Status>unknown</Status></VersioningConfiguration>",
                     "<Unknown/>", "{}"]:
            with self.subTest(body=body), patch.object(publisher.subprocess, "run",
                    return_value=SimpleNamespace(returncode=0, stdout=body)) as call:
                with self.assertRaises(publisher.PublishError) as caught:
                    publisher.upload_preview_file(self.config, self.html, self.key)
                self.assertEqual(caught.exception.code, "preview_storage_unverified")
                self.assertEqual(call.call_count, 1)

    def test_versioning_permission_denial_stops_without_put_or_leaking_raw_error(self):
        with patch.object(publisher.subprocess, "run", return_value=SimpleNamespace(
                returncode=2, stdout="private diagnostic", stderr="AccessDenied")) as call:
            with self.assertRaises(publisher.PublishError) as caught:
                publisher.upload_preview_file(self.config, self.html, self.key)
        self.assertEqual(caught.exception.code, "preview_storage_unverified")
        self.assertNotIn("private diagnostic", str(caught.exception))
        self.assertEqual(call.call_count, 1)

    def test_real_cli_elapsed_framing_requires_quiet_versioning_query(self):
        # XML comes from the actual read-only 2.4.0 response. The timing value is
        # synthetic; its framing/length was observed in the real command.
        xml = '<VersioningConfiguration xmlns="http://doc.oss-cn-hangzhou.aliyuncs.com"/>'
        def command_result(command, **kwargs):
            if 'get-bucket-versioning' in command:
                body = xml if '--quiet' in command else xml + '\n\n0.000000(s) elapsed\n'
                return SimpleNamespace(returncode=0, stdout=body)
            return SimpleNamespace(returncode=0)
        with patch.object(publisher.subprocess, 'run', side_effect=command_result) as transport:
            publisher.upload_preview_file(self.config, self.html, self.key)
        self.assertEqual(transport.call_count, 2)
        self.assertIn('--quiet', transport.call_args_list[0].args[0])
        self.assertIn('--forbid-overwrite=true', transport.call_args_list[1].args[0])

    def test_quiet_does_not_accept_unexpected_xml_framing_or_oversized_output(self):
        xml = '<VersioningConfiguration/>'
        for body in [xml + '\n\n0.000000(s) elapsed\n',
                     'unknown banner\n' + xml, xml + xml,
                     '<VersioningConfiguration>' + (' ' * 4097) + '</VersioningConfiguration>']:
            with self.subTest(body_length=len(body)), patch.object(publisher.subprocess, 'run',
                    return_value=SimpleNamespace(returncode=0, stdout=body)) as transport:
                with self.assertRaises(publisher.PublishError) as caught:
                    publisher.upload_preview_file(self.config, self.html, self.key)
                self.assertEqual(caught.exception.code, 'preview_storage_unverified')
                self.assertEqual(transport.call_count, 1)


if __name__ == "__main__":
    unittest.main()
