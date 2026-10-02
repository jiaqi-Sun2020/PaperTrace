"""Fault injection for cached evidence, packet recovery and collection installation."""
from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import hashlib
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
from academic_sources import family_gate
from daily_coverage_evidence import validate_social_search
from test_release_protocol import daily_evidence
from evidence_fixtures import evidenced_row

DAY = "2026-10-02"
COVERED = "2026-10-01"


def fixtures(academic_count=11, social_count=23):
    matches = [{"title": f"Paper {i}", "doi": f"10.1000/{i}", "description": "Source description",
                "published_at": COVERED + "T12:00:00+08:00"} for i in range(academic_count)]
    rows = [{"source_id": name, "result": "checked", "retrieval_status": "success",
             "parse_status": "success", "window_status": "rolling_window",
             "candidate_count": len(items), "matches": items}
            for name, items in [("aps-pra", matches), ("nature-machine-learning", [])]]
    rows = [evidenced_row(row, COVERED) for row in rows]
    academic = {"academic_search_version": 4, "date_range": COVERED,
                "rows": rows, "family_gate": family_gate(rows)}
    window = daily_evidence(COVERED)["social_search"]["ai_hot_window"]
    window.update(inside_window_count=social_count, retrieved_count=social_count)
    items = [{"id": f"S{i}", "story_id": f"original-{i}", "title": f"Item {i}",
              "published_at": COVERED + "T12:00:00+08:00", "evidence_level": "candidate",
              "facts": "Original candidate text", "score": i} for i in range(social_count)]
    social = {"ai_hot_window": window, "sections": [{"items": items[:7]}, {"items": items[7:]}]}
    return academic, social


class OrchestrationRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.news = Path(self.temp.name) / "news"
        self.paths = o.collection_paths(DAY, self.news)
        self.paths["packet"].parent.mkdir(parents=True)
        self.academic, self.social = fixtures()
        self.write("academic", self.academic)
        self.write("social", self.social)
        self.root_patch = patch.object(o, "NEWS_ROOT", self.news)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write(self, kind, data):
        self.paths[kind].write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def inspect(self):
        return o.inspect(DAY)

    def cli(self, command="resume", record=False):
        output = io.StringIO()
        with redirect_stdout(output):
            code = o.main([command, "--date", DAY] + (["--record"] if record else []))
        return code, json.loads(output.getvalue())

    def offline(self, record=False):
        with patch.object(o, "inspect_network", side_effect=AssertionError("network called")), \
                patch.object(o.subprocess, "run", side_effect=AssertionError("collector called")):
            return self.cli(record=record)

    def test_nested_items_conservation_and_original_fields(self):
        for academic_count, social_count in [(4, 35), (11, 23)]:
            with self.subTest(social_count=social_count):
                a, s = fixtures(academic_count, social_count)
                self.write("academic", a)
                self.write("social", s)
                before = {k: p.read_bytes() for k, p in self.paths.items() if k != "packet"}
                code, state = self.offline()
                self.assertEqual(code, 0)
                self.assertEqual(state["phase"], "collection_ready")
                self.assertEqual(state["candidate_counts"], {"academic": academic_count, "social": social_count})
                packet = json.loads(self.paths["packet"].read_text(encoding="utf-8"))
                self.assertEqual(packet["semantic_review_status"], "not_reviewed")
                self.assertEqual(len(packet["social_candidates"]), social_count)
                self.assertEqual(packet["academic_candidates"][0]["description"], a["rows"][0]["matches"][0]["description"])
                for source, projected in zip([item for section in s["sections"] for item in section["items"]],
                                             packet["social_candidates"]):
                    self.assertEqual(source, {k: v for k, v in projected.items() if k != "_source_ref"})
                self.assertEqual(before, {k: self.paths[k].read_bytes() for k in before})

    def test_packet_missing_legacy_corrupt_stale_and_tampered_are_rebuilt(self):
        self.assertEqual(self.inspect()["packet_status"], "missing")
        self.offline()
        expected = json.loads(self.paths["packet"].read_text(encoding="utf-8"))
        cases = [("legacy", {"version": 1}), ("stale", {**expected, "source_inputs": {}}),
                 ("invalid", {**expected, "semantic_review_status": "approved"}), ("invalid", None)]
        for status, value in cases:
            with self.subTest(status=status):
                if value is None:
                    self.paths["packet"].write_text("{broken", encoding="utf-8")
                else:
                    self.write("packet", value)
                previous = self.paths["packet"].read_bytes()
                digest = hashlib.sha256(previous).hexdigest()
                self.assertEqual(self.inspect()["packet_status"], status)
                self.assertEqual(self.offline()[1]["packet_status"], "valid")
                backup = next((self.paths["packet"].parent / ".packet_backups").glob(f"*.{digest}.json"))
                self.assertEqual(backup.read_bytes(), previous)

    def test_idempotence_no_network_no_writes_or_duplicate_backups(self):
        self.write("packet", {"version": 1})
        self.offline(record=True)
        packet_bytes = self.paths["packet"].read_bytes()
        record = self.news / "_automation" / f"orchestration_state_{DAY}.json"
        record_bytes = record.read_bytes()
        backups = list((self.paths["packet"].parent / ".packet_backups").iterdir())
        with patch.object(o, "atomic_json", side_effect=AssertionError("unexpected write")), \
                patch.object(o, "atomic_copy", side_effect=AssertionError("unexpected backup")):
            self.offline(record=True)
        self.assertEqual(packet_bytes, self.paths["packet"].read_bytes())
        self.assertEqual(record_bytes, record.read_bytes())
        self.assertEqual(backups, list((self.paths["packet"].parent / ".packet_backups").iterdir()))

    def test_high_packet_version_preserved_and_not_collected(self):
        self.write("packet", {"version": 99, "opaque": "preserve"})
        before = self.paths["packet"].read_bytes()
        code, state = self.offline()
        self.assertEqual(code, 2)
        self.assertEqual(state["phase"], "authoring_packet_incompatible")
        self.assertEqual(before, self.paths["packet"].read_bytes())
        self.paths["social"].unlink()
        self.assertEqual(self.offline()[1]["phase"], "authoring_packet_incompatible")

    def test_empty_pool_is_valid_and_requests_expansion_not_shortfall(self):
        a, s = fixtures(0, 0)
        self.write("academic", a)
        self.write("social", s)
        state = self.offline()[1]
        self.assertEqual(state["phase"], "collection_ready")
        self.assertTrue(state["action_required"])
        self.assertIn("Expand discovery", state["next_action"])
        self.assertNotIn("delivery_expansion", json.loads(self.paths["packet"].read_text()))

    def test_limit_is_per_category_and_does_not_drop_at_twenty(self):
        a, s = fixtures(101, 101)
        self.write("academic", a)
        self.write("social", s)
        self.offline()
        p = json.loads(self.paths["packet"].read_text())
        for kind in ("academic", "social"):
            self.assertEqual(len(p[kind + "_candidates"]), 100)
            self.assertEqual(p["candidate_counts"][kind]["total"], 101)
            self.assertEqual(p["candidate_counts"][kind]["truncated"], 1)
            self.assertEqual(p["candidate_counts"][kind]["full_source"], self.paths[kind].name)

    def test_boundary_one_hundred_is_not_truncated(self):
        a, s = fixtures(100, 100)
        self.write("academic", a)
        self.write("social", s)
        state = self.offline()[1]
        self.assertEqual(state["packet_counts"]["social"]["truncated"], 0)

    def test_partial_wrong_day_pagination_hash_and_counts_never_ready(self):
        changes = [{"coverage_status": "partial"}, {"coverage_date": "2026-09-20"},
                   {"pagination_complete": False}, {"response_hash": "0" * 64},
                   {"inside_window_count": 0}, {"retrieved_count": True}]
        for change in changes:
            with self.subTest(change=change):
                bad = deepcopy(self.social)
                bad["ai_hot_window"].update(change)
                self.write("social", bad)
                self.assertEqual(self.inspect()["phase"], "collection_invalid")

    def test_candidate_date_and_structural_damage_rejected(self):
        for change in ("timestamp", "record", "sections", "top_level"):
            bad = deepcopy(self.social)
            if change == "timestamp":
                bad["sections"][0]["items"][0]["published_at"] = "2026-10-02T00:00:00+08:00"
            elif change == "record":
                bad["sections"][0]["items"][0] = "not an object"
            elif change == "sections":
                bad["sections"] = {}
            else:
                bad["items"] = [item for section in bad.pop("sections") for item in section["items"]]
            self.write("social", bad)
            self.assertEqual(self.inspect()["phase"], "collection_invalid")

    def test_qualified_exclusion_preserved_but_invalid_exclusion_rejected(self):
        window = self.social["ai_hot_window"]
        window.update(coverage_status="qualified_with_exclusion", coverage_claim="dated_candidates_only",
                      missing_timestamp_count=1, retrieved_count=24,
                      undated_exclusions=[{"reason": "missing_or_ambiguous_publishedAt", "item_sha256": "e" * 64}])
        self.write("social", self.social)
        self.offline()
        self.assertEqual(json.loads(self.paths["packet"].read_text())["ai_hot_window"], window)
        window["undated_exclusions"][0]["item_sha256"] = "invalid"
        self.write("social", self.social)
        self.assertEqual(self.inspect()["phase"], "collection_invalid")

    def test_packet_does_not_weaken_four_class_publication_gate(self):
        self.offline()
        social_search = daily_evidence(COVERED)["social_search"]
        social_search.pop("source_class_evidence")
        self.assertTrue(any("source-class" in failure for failure in validate_social_search(social_search, COVERED)))

    def test_forged_family_gate_bad_rows_or_academic_day_rejected(self):
        for case in ("gate", "rows", "count", "date"):
            bad = deepcopy(self.academic)
            if case == "gate":
                bad["rows"][1]["result"] = "blocked"
            elif case == "rows":
                bad["rows"][0] = None
            elif case == "count":
                bad["rows"][0]["candidate_count"] += 1
            else:
                bad["date_range"] = DAY
            self.write("academic", bad)
            self.assertEqual(self.inspect()["phase"], "collection_invalid")

    def test_corrupt_authored_candidate_is_not_empty_ready_or_overwritten(self):
        candidate = self.paths["packet"].parent / f"candidate_{DAY}.json"
        for data in ("{broken", "[]", '{"sections":[]}', '{"sections":[{"items":[null]}]}'):
            candidate.write_text(data, encoding="utf-8")
            code, state = self.offline()
            self.assertEqual(code, 2)
            self.assertEqual(state["phase"], "candidate_invalid")
            self.assertEqual(candidate.read_text(), data)
            self.assertFalse(self.paths["packet"].exists())

    def test_source_change_during_backup_reprojects_latest_snapshot(self):
        self.write("packet", {"version": 1})
        copy = o.atomic_copy
        changed = False

        def change(source, destination):
            nonlocal changed
            copy(source, destination)
            if not changed:
                changed = True
                self.academic["rows"][0]["matches"][0]["description"] = "New source description"
                self.write("academic", self.academic)

        with patch.object(o, "atomic_copy", side_effect=change):
            self.offline()
        p = json.loads(self.paths["packet"].read_text())
        self.assertEqual(p["academic_candidates"][0]["description"], "New source description")
        self.assertEqual(p["source_inputs"]["academic"]["sha256"], o.sha256_file(self.paths["academic"]))

    def test_interrupted_atomic_write_preserves_old_input_and_backup(self):
        self.write("packet", {"version": 1})
        before = self.paths["packet"].read_bytes()
        with patch.object(o, "atomic_json", side_effect=OSError("injected interruption")):
            code, state = self.offline()
        self.assertEqual(code, 2)
        self.assertEqual(state["phase"], "recovery_failed")
        self.assertEqual(before, self.paths["packet"].read_bytes())
        self.assertEqual(len(list((self.paths["packet"].parent / ".packet_backups").iterdir())), 1)

    def test_readonly_install_reports_controlled_failure(self):
        with patch.object(o, "atomic_json", side_effect=PermissionError("do not echo private path")):
            code, state = self.offline()
        self.assertEqual(code, 2)
        self.assertEqual(state["failures"][0]["code"], "PermissionError")
        self.assertNotIn("private path", str(state))

    def test_concurrent_recovery_installs_one_packet_and_one_backup(self):
        self.write("packet", {"version": 1})
        with patch.object(o, "inspect_network", side_effect=AssertionError("network called")), \
                ThreadPoolExecutor(max_workers=2) as executor:
            states = list(executor.map(lambda _: o._repair_packet(DAY), range(2)))
        self.assertTrue(all(state["packet_status"] == "valid" for state in states))
        self.assertEqual(len(list((self.paths["packet"].parent / ".packet_backups").iterdir())), 1)

    def test_partial_collection_only_runs_missing_source_and_preserves_valid_source(self):
        before = self.paths["academic"].read_bytes()
        self.paths["social"].unlink()

        def collect(command, **kwargs):
            self.assertIn("aihot_candidates.py", command[2])
            Path(command[-1]).write_text(json.dumps(self.social), encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch.object(o, "inspect_network", return_value={"status": "ready"}) as network, \
                patch.object(o.subprocess, "run", side_effect=collect) as run:
            code, state = self.cli()
        network.assert_called_once()
        run.assert_called_once()
        self.assertEqual(code, 0)
        self.assertEqual(state["phase"], "collection_ready")
        self.assertEqual(before, self.paths["academic"].read_bytes())
        self.assertEqual(list(self.paths["packet"].parent.glob(".collect-*")), [])

    def test_invalid_source_is_retried_and_valid_peer_preserved(self):
        self.paths["academic"].write_text("{broken", encoding="utf-8")
        before = self.paths["social"].read_bytes()

        def collect(command, **kwargs):
            self.assertIn("academic_venue_sweep.py", command[2])
            Path(command[-1]).write_text(json.dumps(self.academic), encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch.object(o, "inspect_network", return_value={"status": "ready"}), \
                patch.object(o.subprocess, "run", side_effect=collect) as run:
            self.assertEqual(self.cli()[0], 0)
        run.assert_called_once()
        self.assertEqual(before, self.paths["social"].read_bytes())

    def test_network_block_does_not_modify_cached_evidence(self):
        self.paths["social"].unlink()
        before = self.paths["academic"].read_bytes()
        with patch.object(o, "inspect_network", return_value={"status": "environment_blocked"}), \
                patch.object(o.subprocess, "run") as run:
            code, state = self.cli()
        self.assertEqual(code, 2)
        self.assertEqual(state["phase"], "environment_blocked")
        run.assert_not_called()
        self.assertEqual(before, self.paths["academic"].read_bytes())

    def test_failed_or_invalid_collector_preserves_previous_bytes_and_hides_stderr(self):
        self.paths["social"].write_text("{old broken source", encoding="utf-8")
        before = self.paths["social"].read_bytes()
        for result in ("returncode", "timeout", "invalid"):
            def collect(command, **kwargs):
                if result == "timeout":
                    raise subprocess.TimeoutExpired(command, 240)
                if result == "invalid":
                    Path(command[-1]).write_text("{}", encoding="utf-8")
                return SimpleNamespace(returncode=1 if result == "returncode" else 0,
                                       stderr="sensitive runtime diagnostic")
            with patch.object(o, "inspect_network", return_value={"status": "ready"}), \
                    patch.object(o.subprocess, "run", side_effect=collect):
                code, state = self.cli()
            self.assertEqual(code, 2)
            self.assertTrue(state["operation_failed"])
            self.assertNotIn("sensitive", str(state))
            self.assertEqual(before, self.paths["social"].read_bytes())

    def test_later_stage_appearing_during_collection_is_not_regressed(self):
        self.paths["social"].unlink()

        def collect(command, **kwargs):
            candidate = self.paths["packet"].parent / f"candidate_{DAY}.json"
            candidate.write_text('{"sections":[{"items":[{"id":"A001"}]}]}', encoding="utf-8")
            Path(command[-1]).write_text(json.dumps(self.social), encoding="utf-8")
            return SimpleNamespace(returncode=0)

        with patch.object(o, "inspect_network", return_value={"status": "ready"}), \
                patch.object(o.subprocess, "run", side_effect=collect):
            state = self.cli()[1]
        self.assertEqual(state["phase"], "candidate_waiting_capture")
        self.assertFalse(self.paths["social"].exists())
        self.assertFalse(self.paths["packet"].exists())

    def test_existing_release_failure_never_falls_through_to_collection(self):
        output = self.news / DAY
        output.mkdir()
        (output / f"daily_pipeline_manifest_{DAY}.json").write_text("{}", encoding="utf-8")
        with patch.object(o, "verify_artifacts", return_value={"status": "fail", "failures": ["bad release"]}):
            state = self.offline()[1]
        self.assertEqual(state["phase"], "local_manifest_invalid")
        self.assertFalse(self.paths["packet"].exists())

    def test_process_lock_prevents_duplicate_packet_installations(self):
        self.write("packet", {"version": 1})
        code = ("import pathlib,sys; sys.path.insert(0,sys.argv[1]); import orchestrate_daily as o; "
                "o.NEWS_ROOT=pathlib.Path(sys.argv[2]); "
                "o.inspect_network=lambda: (_ for _ in ()).throw(AssertionError('unexpected network')); "
                f"assert o._repair_packet('{DAY}')['packet_status']=='valid'")
        commands = [sys.executable, "-B", "-c", code, str(o.SCRIPT_DIR), str(self.news)]
        workers = [subprocess.Popen(commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        try:
            for worker in workers:
                stdout, stderr = worker.communicate(timeout=15)
                self.assertEqual(worker.returncode, 0, stderr.decode("utf-8", errors="replace"))
        finally:
            for worker in workers:
                if worker.poll() is None:
                    worker.kill()
                    worker.communicate()
        self.assertEqual(self.inspect()["packet_status"], "valid")
        self.assertEqual(len(list((self.paths["packet"].parent / ".packet_backups").iterdir())), 1)

    def test_corrupt_existing_backup_is_not_overwritten(self):
        self.write("packet", {"version": 1})
        before = self.paths["packet"].read_bytes()
        backup = self.paths["packet"].parent / ".packet_backups" / (
            self.paths["packet"].stem + "." + hashlib.sha256(before).hexdigest() + ".json")
        backup.parent.mkdir()
        backup.write_bytes(b"corrupt backup")
        code, state = self.offline()
        self.assertEqual(code, 2)
        self.assertEqual(state["failures"][0]["code"], "packet_backup_digest_mismatch")
        self.assertEqual(before, self.paths["packet"].read_bytes())
        self.assertEqual(backup.read_bytes(), b"corrupt backup")

    def test_record_keeps_fresh_online_verification_for_same_html(self):
        online = {"date": DAY, "phase": "remote_complete", "remote_status": "verified",
                  "action_required": False, "packet_status": "not_checked", "html_sha256": "a" * 64}
        offline = {**online, "phase": "remote_pending", "remote_status": "not_checked", "action_required": True}
        with patch.object(o, "inspect", return_value=offline):
            o._record(online, True)
        record = json.loads((self.news / "_automation" / f"orchestration_state_{DAY}.json").read_text())
        self.assertEqual(record["phase"], "remote_complete")
        self.assertEqual(record["remote_status"], "verified")

    def test_explicit_preflight_checks_network_after_cached_collection_ready(self):
        self.offline()
        with patch.object(o, "inspect_network", return_value={"status": "ready"}) as network:
            code, state = self.cli("preflight", record=True)
        network.assert_called_once()
        self.assertEqual(code, 0)
        self.assertEqual(state["phase"], "collection_ready")
        self.assertEqual(state["network_preflight"]["status"], "ready")

    def test_explicit_preflight_blocked_reports_transport_and_retains_cached_input(self):
        self.offline()
        before = {key: path.read_bytes() for key, path in self.paths.items()}
        with patch.object(o, "inspect_network", return_value={"status": "environment_blocked"}):
            code, state = self.cli("preflight", record=True)
        self.assertEqual(code, 2)
        self.assertEqual(state["source_phase"], "collection_ready")
        self.assertTrue(state["action_required"])
        self.assertEqual(before, {key: path.read_bytes() for key, path in self.paths.items()})
        self.assertEqual(self.offline()[1]["phase"], "collection_ready")

    def test_opt_in_status_checks_transport_but_plain_status_is_offline(self):
        self.offline()
        with patch.object(o, "inspect_network", side_effect=AssertionError("unexpected network")):
            self.assertEqual(self.cli("status")[0], 0)
            state = o.with_network_preflight(self.inspect())
            self.assertEqual(state["network_preflight"]["status"], "not_checked")
        with patch.object(o, "inspect_network", return_value={"status": "ready"}) as network, \
                redirect_stdout(io.StringIO()):
            self.assertEqual(o.main(["status", "--date", DAY, "--preflight-network"]), 0)
        network.assert_called_once()

    def test_capture_ready_candidate_reports_missing_story_without_claiming_release_ready(self):
        from source_capture import capture_path, make_capture
        candidate = self.paths["packet"].parent / f"candidate_{DAY}.json"
        item = {"id": "A001", "source_url": "https://example.org/article", "source_excerpt": "Test claim"}
        candidate.write_text(json.dumps({"sections": [{"items": [item]}]}), encoding="utf-8")
        path = capture_path(self.news, COVERED, "A001")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(make_capture(item, item["source_url"], item["source_url"], 200,
                                              b"<p>Test claim</p>", "2026-10-02T01:00:00+00:00")), encoding="utf-8")
        state = self.inspect()
        self.assertEqual(state["phase"], "candidate_ready")
        self.assertEqual(state["opening_story_status"], "authoring_pending")
        self.assertIn("Complete the opening story", state["next_action"])


if __name__ == "__main__":
    unittest.main()
