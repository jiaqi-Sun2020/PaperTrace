"""Offline v4 release lifecycle and adversarial version-routing checks."""
from __future__ import annotations

from argparse import Namespace
from contextlib import redirect_stdout
from copy import deepcopy
import html
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import daily_pipeline as dp
import audit_briefing_config as config_audit
import publish_daily_to_oss as publisher
from academic_sources import family_gate
from daily_coverage_evidence import evidence_digest
from publication_contracts import coverage_contract_for_manifest, coverage_contract_for_protocol
from source_capture import capture_path, make_capture
from test_daily_pipeline import ranking_fixture
from test_delivery_expansion import shortfall_fixture
import test_release_protocol as reviewed
from evidence_fixtures import evidenced_row


def v4_ledger(day):
    rows = [{"source_id": name, "result": "checked", "retrieval_status": "success",
             "parse_status": "success", "window_status": "rolling_window",
             "candidate_count": 1, "quarantined_count": 0}
            for name in ("aps-pra", "nature-machine-learning")]
    rows = [evidenced_row(row, day) for row in rows]
    return {"academic_search_version": 4, "date_range": day,
            "rows": rows, "family_gate": family_gate(rows)}


def use_v4(raw):
    record = raw["coverage_evidence"][0]
    record["academic_search"] = v4_ledger(record["date"])
    record["academic_search_ref"] = evidence_digest(record["academic_search"])
    raw["academic_search"] = record["academic_search"]
    expansion = raw.get("delivery_expansion")
    if expansion and expansion["mode"] == "verified_shortfall":
        expansion["version"] = 2
        expansion["academic_lookback_search"] = v4_ledger(
            expansion["academic_window_start"] + ".." + expansion["coverage_date"])
        expansion["academic_lookback_ref"] = evidence_digest(expansion["academic_lookback_search"])
    return raw


class ContractRoutingTests(unittest.TestCase):
    def test_known_generation_pairs_and_unknown_versions(self):
        for protocol, expected in ((1, 1), (2, 2), (3, 2), (4, 3)):
            self.assertEqual(coverage_contract_for_protocol(protocol), expected)
        for unknown in (0, 5, -1, True, 4.0, "4", None):
            with self.subTest(version=unknown), self.assertRaises(ValueError):
                coverage_contract_for_protocol(unknown)

    def test_manifest_pair_matrix_and_upload_eligibility(self):
        for protocol in (1, 2, 3, 4):
            for contract in (None, 1, 2, 3, 4, True, "3"):
                manifest = {"pipeline_version": protocol, "status": "staged",
                            "coverage_evidence_contract_version": contract}
                valid = (type(contract) is int and contract == coverage_contract_for_protocol(protocol))
                if valid or (protocol == 1 and contract is None):
                    coverage_contract_for_manifest(manifest)
                else:
                    with self.assertRaises(ValueError):
                        coverage_contract_for_manifest(manifest)
                if valid and protocol >= 3:
                    coverage_contract_for_manifest(manifest, for_upload=True)
                else:
                    with self.assertRaises(ValueError):
                        coverage_contract_for_manifest(manifest, for_upload=True)

    def test_historical_completed_readability_cannot_grant_v4_downgrade(self):
        for protocol in (1, 2, 3):
            for contract in (None, 1):
                self.assertEqual(coverage_contract_for_manifest({"pipeline_version": protocol,
                    "status": "complete", "coverage_evidence_contract_version": contract}), 1)
        for contract in (None, 1, 2, True, 3.0):
            with self.assertRaises(ValueError):
                coverage_contract_for_manifest({"pipeline_version": 4, "status": "complete",
                                                "coverage_evidence_contract_version": contract})


class V4PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.news = self.root / "news"
        root_patch = patch.object(dp, "NEWS_ROOT", self.news)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        # Keep routine lifecycle JSON out of the test runner's output.
        output_patch = redirect_stdout(io.StringIO())
        output_patch.__enter__()
        self.addCleanup(output_patch.__exit__, None, None, None)

    def prepare(self, shortfall=False):
        if shortfall:
            raw, prior = shortfall_fixture()
            release = "2026-09-28"
        else:
            from test_release_protocol import daily_evidence
            raw, prior = ranking_fixture()
            raw["date_range"] = "2026-07-09"
            raw["collection_completed_at"] = "2026-07-10T08:00:00+08:00"
            raw["coverage_evidence"] = [daily_evidence("2026-07-09")]
            release = "2026-07-10"
        use_v4(raw)
        raw["story_delivery"].update(selection_basis="explicit_override",
            override_reason="Fixture isolates version routing from rank-1 pedagogy.")
        self.candidate = self.root / "candidate.json"
        self.raw = raw
        self.release = release
        self.write_candidate()
        self.args = dp.parse_args(["run", "--config", str(self.candidate), "--date", release])
        index = self.news / "_index" / "story_index.jsonl"
        index.parent.mkdir(parents=True)
        index.write_text("".join(json.dumps(row) + "\n" for row in prior), encoding="utf-8")
        self.index_before = index.read_bytes()
        for section in raw["sections"]:
            for item in section["items"]:
                body = ("<title>Original source " + item["id"] + "</title><p>"
                        + html.escape(item["source_excerpt"]) + "</p>").encode("utf-8")
                record = make_capture(item, item["source_url"], item["source_url"], 200, body,
                                      raw["collection_completed_at"])
                path = capture_path(self.news, raw["date_range"], item["id"])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(record), encoding="utf-8")
        return raw

    def write_candidate(self):
        self.candidate.write_text(json.dumps(self.raw, ensure_ascii=False), encoding="utf-8")

    def stage(self):
        self.assertEqual(dp.cmd_run(self.args), 0)
        stage = next((self.news / self.release / ".staging").iterdir())
        manifest_path = stage / f"daily_pipeline_manifest_{self.release}.json"
        manifest = dp.load_json(manifest_path)
        self.assertEqual((manifest["pipeline_version"], manifest["coverage_evidence_contract_version"]), (4, 3))
        self.assertEqual(manifest["required_story_review_protocol"], 3)
        result = dp.verify_artifacts(stage, strict=True, structure_only=True)
        self.assertEqual(result["status"], "pass", result["failures"])
        self.assertEqual(config_audit.main(["--config", str(stage / manifest["artifacts"]["delta_config"]),
                                          "--coverage-contract-version", "3", "--json"]), 0)
        self.assertEqual((self.news / "_index" / "story_index.jsonl").read_bytes(), self.index_before)
        return stage, manifest_path, manifest

    def complete(self, stage):
        self.assertEqual(dp.verify_artifacts(stage, strict=True)["status"], "fail")
        reviewed.ReviewedReleaseTests._write_reviews(SimpleNamespace(stage=stage, date=self.release,
            manifest_path=stage / f"daily_pipeline_manifest_{self.release}.json"))
        self.assertEqual(dp.cmd_seal_review(Namespace(run_dir=str(stage))), 0)
        result = dp.verify_artifacts(stage, strict=True)
        self.assertEqual(result["status"], "pass", result["failures"])
        with patch.object(publisher, "auto_publish_after_finalize", return_value={"status": "disabled"}):
            self.assertEqual(dp.cmd_finalize(Namespace(run_dir=str(stage), strict=True,
                require_remote=False, correction_reason=None, supersedes_hash=None)), 0)
        final = self.news / self.release
        result = dp.verify_artifacts(final, strict=True)
        self.assertEqual(result["status"], "pass", result["failures"])
        return final

    def simulate_publish(self, final):
        # All transport operations use this in-memory site; no real OSS or keys.
        config_path = self.root / "news_publish.local.json"
        config = {"site_index_url": "https://example.org/index.html", "bucket": "example-bucket",
                  "region": "cn-hongkong", "object_prefix": "", "ossutil_profile": "fixture"}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        old = "briefing_reader_2026-07-08.html"
        objects = {"index.html": publisher._index_html(old).encode(), old: b"<html>old</html>"}
        uploaded = []
        def fetch(url):
            name = url.rsplit("/", 1)[-1]
            if name not in objects:
                raise publisher.PublishError("fixture 404", code="not_found")
            return url, objects[name]
        def upload(_config, path, name):
            objects[name] = path.read_bytes()
            uploaded.append(name)
        with patch.object(publisher, "fetch_html", side_effect=fetch), \
                patch.object(publisher, "upload_file", side_effect=upload), \
                patch.object(publisher, "read_bucket_index", side_effect=lambda _config: objects["index.html"]):
            self.assertEqual(publisher.enable(config_path)["status"], "enabled")
            result = publisher.publish(final, config_path)
            self.assertEqual(result["status"], "published")
            self.assertEqual(uploaded, [f"briefing_reader_{self.release}.html", "index.html"])
            self.assertEqual(result["html_sha256"], dp.sha256_file(final / uploaded[0]))
            before = list(uploaded)
            self.assertEqual(publisher.publish(final, config_path)["status"], "no_change")
            self.assertEqual(uploaded, before)

    def test_default_cli_v4_full_review_finalize_and_mock_first_upload(self):
        self.prepare()
        stage, _, _ = self.stage()
        self.simulate_publish(self.complete(stage))

    def test_v4_shortfall_full_lifecycle_uses_contract_three(self):
        self.prepare(shortfall=True)
        stage, _, _ = self.stage()
        self.simulate_publish(self.complete(stage))

    def test_reject_v3_evidence_missing_family_forged_gate_and_stale_digest_before_staging(self):
        from test_release_protocol import daily_evidence
        for attack in ("v3_evidence", "missing_family", "stale_digest", "wrong_day"):
            with self.subTest(attack=attack):
                if not hasattr(self, "raw"):
                    self.prepare()
                original = deepcopy(self.raw)
                record = self.raw["coverage_evidence"][0]
                if attack == "v3_evidence":
                    record["academic_search"] = daily_evidence(record["date"])["academic_search"]
                elif attack == "missing_family":
                    record["academic_search"]["rows"].pop()  # Saved family_gate still claims pass.
                elif attack == "wrong_day":
                    record["academic_search"]["date_range"] = "2026-07-08"
                if attack != "stale_digest":
                    record["academic_search_ref"] = evidence_digest(record["academic_search"])
                else:
                    record["academic_search"]["rows"][0]["candidate_count"] += 1
                self.raw["academic_search"] = record["academic_search"]
                self.write_candidate()
                with self.assertRaises(ValueError):
                    dp.cmd_run(self.args)
                self.assertFalse((self.news / self.release / ".staging").exists())
                self.raw = original

    def test_missing_opening_story_remains_a_real_gate(self):
        self.prepare()
        self.raw.pop("opening_story")
        self.write_candidate()
        with self.assertRaisesRegex(ValueError, "opening_story"):
            dp.cmd_run(self.args)
        self.assertFalse((self.news / self.release).exists())

    def test_v4_manifest_downgrade_unknown_protocol_and_removed_contract_rejected(self):
        self.prepare()
        stage, manifest_path, manifest = self.stage()
        for update in ({"coverage_evidence_contract_version": 2},
                       {"coverage_evidence_contract_version": None}, {"pipeline_version": 5},
                       {"pipeline_version": True}, {"pipeline_version": "4"},
                       {"required_story_review_protocol": 2}, {"required_story_review_protocol": None}):
            with self.subTest(update=update):
                manifest_path.write_text(json.dumps({**manifest, **update}), encoding="utf-8")
                self.assertEqual(dp.verify_artifacts(stage, strict=True, structure_only=True)["status"], "fail")
                self.assertNotEqual(dp.cmd_seal_review(Namespace(run_dir=str(stage))), 0)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_missing_capture_never_stages(self):
        self.prepare()
        for section in self.raw["sections"]:
            for item in section["items"]:
                path = capture_path(self.news, self.raw["date_range"], item["id"])
                path.unlink()
        with self.assertRaisesRegex(ValueError, "source captures"):
            dp.cmd_run(self.args)
        self.assertFalse((self.news / self.release).exists())

    def test_tampered_capture_never_stages(self):
        self.prepare()
        item = self.raw["sections"][0]["items"][0]
        path = capture_path(self.news, self.raw["date_range"], item["id"])
        record = dp.load_json(path)
        record["quoted_excerpt"] = "A forged source quote."
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "source capture"):
            dp.cmd_run(self.args)
        self.assertFalse((self.news / self.release).exists())

    def test_stale_content_review_cannot_finalize_or_upload(self):
        self.prepare()
        stage, manifest_path, _ = self.stage()
        reviewed.ReviewedReleaseTests._write_reviews(SimpleNamespace(stage=stage, date=self.release,
            manifest_path=manifest_path))
        self.assertEqual(dp.cmd_seal_review(Namespace(run_dir=str(stage))), 0)
        path = stage / f"news_content_review_{self.release}.json"
        data = dp.load_json(path)
        data["content_digest"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        self.assertEqual(dp.verify_artifacts(stage, strict=True)["status"], "fail")
        with patch.object(publisher, "auto_publish_after_finalize") as remote:
            self.assertNotEqual(dp.cmd_finalize(Namespace(run_dir=str(stage), strict=True, require_remote=False,
                                     correction_reason=None, supersedes_hash=None)), 0)
        remote.assert_not_called()
        with patch.object(publisher, "upload_file") as upload:
            with self.assertRaises(publisher.PublishError):
                publisher.verified_release(stage)
            upload.assert_not_called()
        self.assertEqual((self.news / "_index" / "story_index.jsonl").read_bytes(), self.index_before)


if __name__ == "__main__":
    unittest.main()
