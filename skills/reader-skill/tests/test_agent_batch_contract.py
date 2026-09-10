#!/usr/bin/env python3
"""Regression tests for one-request, one-active-paper batch continuation."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "skills" / "reader-skill" / "scripts"
TESTS = ROOT / "skills" / "reader-skill" / "tests"
NATURE_SCRIPTS = ROOT / "skills" / "nature-reader" / "scripts"
for path in (SCRIPTS, TESTS, NATURE_SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def papers() -> list[dict]:
    return [
        {"order": index, "paper_id": f"paper-{index}", "filename": f"Paper {index}.pdf", "pdf_path": f"C:/source/Paper {index}.pdf"}
        for index in range(1, 4)
    ]


def main() -> int:
    builder = load_module("batch_builder_contract", SCRIPTS / "build_formal_reader_batch.py")
    auditor = load_module("batch_auditor_contract", TESTS / "adversarial_batch_audit.py")
    guard = load_module("batch_guard_contract", SCRIPTS / "reader_continuation_guard.py")
    with tempfile.TemporaryDirectory(prefix="agent_batch_", dir=ROOT) as temporary:
        root = Path(temporary)
        calls: list[str] = []

        def processor(paper: dict, _reader_root: Path, *, resume: bool) -> dict:
            calls.append(paper["paper_id"])
            if paper["order"] == 1:
                return {
                    "order": 1, "paper_id": "paper-1", "filename": "Paper 1.pdf",
                    "reader_dir": str(root / "Paper 1_reader"), "status": "formal_pass",
                    "html": str(root / "Paper 1_reader" / "reader_interactive.html"),
                }
            return {
                "order": 2, "paper_id": "paper-2", "filename": "Paper 2.pdf",
                "reader_dir": str(root / "Paper 2_reader"), "status": "pending",
                "pending_record_ids": ["block:S001"], "invalid_record_ids": [],
                "preflight_issues": ["F001 requires a tight crop"], "failure_gate": "completion records",
            }

        results = builder.process_papers_sequentially(papers(), root, resume=True, processor=processor)
        if calls != ["paper-1", "paper-2"]:
            raise AssertionError("controller touched a later paper after selecting the active paper")
        if [row["status"] for row in results] != ["formal_pass", "pending", "queued"]:
            raise AssertionError("controller did not produce formal-prefix / active / queued ordering")

        contract = builder.build_agent_contract(pdf_dir=Path("C:/source"), reader_root=root, results=results)
        if contract["final_response_allowed"] or not contract["must_continue"]:
            raise AssertionError("pending work did not fail closed against a final response")
        if contract.get("persistent_goal_action") != "keep_active":
            raise AssertionError("pending work did not keep the persistent goal active")
        if not contract.get("final_response_prohibited_reason"):
            raise AssertionError("pending work omitted the final-response prohibition reason")
        if contract["active_paper"]["paper_id"] != "paper-2":
            raise AssertionError("wrong active paper in continuation contract")
        if len(contract["reportable_formal_html"]) != 1:
            raise AssertionError("formal-prefix artifact was not isolated from pending/queued readers")

        complete_contract = builder.build_agent_contract(
            pdf_dir=Path("C:/source"), reader_root=root, results=[results[0]],
        )
        if complete_contract["status"] != "complete" or complete_contract.get("next_command") is not None:
            raise AssertionError("completed scope retained a misleading continuation command")

        snapshot = {"source_set_sha256": "fixture-set", "papers": papers()}
        state = {
            "schema_version": 3, "status": "action_required", "final_response_allowed": False,
            "must_continue": True, "terminal_blocker": None, "results": results,
            "reader_root": str(root), "source_set_sha256": "fixture-set",
            "input_snapshot": snapshot, "agent_continuation_contract": contract,
            "formal_artifact_manifest": None,
        }
        orchestration_path = root / ".papertrace_jobs" / "fixture" / "orchestration_state.json"
        orchestration_path.parent.mkdir(parents=True)
        orchestration_path.write_text(
            json.dumps({
                "schema_version": 1,
                "status": "active",
                "selected_papers": papers(),
                "source_set_sha256": "fixture-set",
                "next_command": contract["next_command"],
                "active_paper": {"paper_id": "paper-2"},
            }),
            encoding="utf-8",
        )
        state["orchestration_state_path"] = str(orchestration_path)
        formal_reader = root / "Paper 1_reader"
        formal_wiki = formal_reader / "reader_wiki"
        formal_wiki.mkdir(parents=True)
        formal_html = formal_reader / "reader_interactive.html"
        formal_html.write_text("<!doctype html><title>fixture</title>", encoding="utf-8")
        formal_hash = hashlib.sha256(formal_html.read_bytes()).hexdigest()
        (formal_wiki / "formal_status.json").write_text(
            json.dumps({"status": "formal_pass", "html_sha256": formal_hash}), encoding="utf-8"
        )
        issues = auditor.audit_batch_report(state, run_reader_audits=False)
        # The formal-prefix file is intentionally absent in this controller-only
        # fixture; remove only those artifact-evidence diagnostics and require
        # every sequencing/report-boundary invariant to pass.
        structural = [issue for issue in issues if "formal result HTML is missing" not in issue]
        if structural:
            raise AssertionError(f"valid continuation contract failed adversarial audit: {structural}")
        guard_code, guard_payload = guard.guard(state)
        if guard_code != 75 or guard_payload.get("status") != "must_continue":
            raise AssertionError("continuation guard did not fail closed for an active paper")
        if guard_payload.get("persistent_goal_action") != "keep_active":
            raise AssertionError("continuation guard allowed the persistent goal to end")
        if guard_payload.get("active_paper", {}).get("paper_id") != "paper-2":
            raise AssertionError("continuation guard lost the active-paper identity")
        report_fixture = root / "must_continue_report.json"
        report_fixture.write_text(json.dumps(state), encoding="utf-8")
        tool_safe = subprocess.run(
            [sys.executable, str(SCRIPTS / "reader_continuation_guard.py"), str(report_fixture)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        strict_guard = subprocess.run(
            [sys.executable, str(SCRIPTS / "reader_continuation_guard.py"), str(report_fixture), "--strict-exit"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        if tool_safe.returncode != 0 or strict_guard.returncode != guard.MUST_CONTINUE_EXIT:
            raise AssertionError("guard CLI does not separate tool-safe checkpoints from strict CI exits")

        bad = json.loads(json.dumps(contract))
        bad["final_response_allowed"] = True
        bad_report = json.loads(json.dumps(state))
        bad_report["agent_continuation_contract"] = bad
        bad_issues = auditor.audit_batch_report(bad_report, run_reader_audits=False)
        if not any("premature final response" in issue for issue in bad_issues):
            raise AssertionError("adversarial audit accepted a premature-final-response contract")

        # Attack 2: a second active paper must be rejected even if every
        # continuation flag otherwise looks plausible.
        two_active_state = json.loads(json.dumps(state))
        two_active_state["results"][2]["status"] = "pending"
        two_active_issues = auditor.audit_batch_report(two_active_state, run_reader_audits=False)
        if not any("more than one paper is active" in issue for issue in two_active_issues):
            raise AssertionError("adversarial audit accepted two simultaneously active papers")

        # Attack 3: a pending reader may have an internal progress page but
        # must never expose any HTML as a deliverable.
        draft_state = json.loads(json.dumps(state))
        draft_state["results"][1]["html"] = str(root / "Paper 2_reader" / "reader_progress.html")
        draft_issues = auditor.audit_batch_report(draft_state, run_reader_audits=False)
        if not any("non-formal result exposes an HTML deliverable" in issue for issue in draft_issues):
            raise AssertionError("adversarial audit accepted a draft HTML deliverable")

        # Authorized terminal blockers are the only incomplete state allowed
        # to end the user turn, and they still must not claim artifact success.
        blocked_results = json.loads(json.dumps(results))
        blocker = {
            "kind": "ambiguous_completed_bundle_overwrite",
            "message": "source hash conflict",
            "paper_id": "paper-2",
            "filename": "Paper 2.pdf",
            "gate": "immutable source identity",
        }
        blocked_results[1] = {
            "order": 2, "paper_id": "paper-2", "filename": "Paper 2.pdf",
            "reader_dir": str(root / "Paper 2_reader"), "status": "blocked",
            "terminal_blocker": blocker,
        }
        blocked_contract = builder.build_agent_contract(
            pdf_dir=Path("C:/source"), reader_root=root, results=blocked_results,
        )
        if blocked_contract["status"] != "blocked" or not blocked_contract["final_response_allowed"]:
            raise AssertionError("authorized terminal blocker did not produce a reportable blocked contract")
        if blocked_contract.get("persistent_goal_action") != "report_blocker":
            raise AssertionError("authorized terminal blocker has the wrong persistent-goal action")
        if blocked_contract["requested_artifact_ready"]:
            raise AssertionError("blocked contract falsely claims requested artifacts are ready")
        blocked_state = {
            "schema_version": 3, "status": "blocked", "final_response_allowed": True,
            "must_continue": False, "terminal_blocker": blocker,
            "results": blocked_results,
            "reader_root": str(root), "source_set_sha256": "fixture-set",
            "input_snapshot": snapshot, "agent_continuation_contract": blocked_contract,
            "formal_artifact_manifest": None, "orchestration_state_path": str(orchestration_path),
        }
        orchestration_path.write_text(
            json.dumps({
                "schema_version": 1,
                "status": "blocked",
                "selected_papers": papers(),
                "source_set_sha256": "fixture-set",
                "next_command": blocked_contract["next_command"],
                "active_paper": {"paper_id": "paper-2"},
            }),
            encoding="utf-8",
        )
        blocked_issues = auditor.audit_batch_report(blocked_state, run_reader_audits=False)
        blocked_structural = [issue for issue in blocked_issues if "formal result HTML is missing" not in issue]
        if blocked_structural:
            raise AssertionError(f"authorized blocked state failed adversarial audit: {blocked_structural}")
        blocked_code, blocked_payload = guard.guard(blocked_state)
        if blocked_code != 3 or blocked_payload.get("status") != "blocked":
            raise AssertionError("continuation guard did not preserve an authorized terminal blocker")

        # Liveness: the selected scope and next work packet survive process
        # boundaries. A newly inserted earlier PDF must not change a resumed
        # two-paper job.
        source_dir = root / "source"
        reader_root = root / "readers"
        source_dir.mkdir()
        reader_root.mkdir()
        for name in ("B.pdf", "C.pdf", "D.pdf"):
            (source_dir / name).write_bytes(("fixture:" + name).encode("utf-8"))
        discovered = builder.discover_pdfs(source_dir)
        selected, job, state_path, report_path = builder.load_or_create_job(
            pdf_dir=source_dir.resolve(), reader_root=reader_root.resolve(), discovered=discovered,
            max_papers=2, resume=False,
        )
        if [row["filename"] for row in selected] != ["B.pdf", "C.pdf"]:
            raise AssertionError("max-papers did not freeze the deterministic prefix")
        if not state_path.exists() or report_path.exists() or job.get("attempts") != 1:
            raise AssertionError("initial persistent orchestration state is incomplete")
        (source_dir / "A.pdf").write_bytes(b"inserted later")
        resumed, resumed_job, same_state_path, _ = builder.load_or_create_job(
            pdf_dir=source_dir.resolve(), reader_root=reader_root.resolve(),
            discovered=builder.discover_pdfs(source_dir), max_papers=2, resume=True,
        )
        if [row["filename"] for row in resumed] != ["B.pdf", "C.pdf"]:
            raise AssertionError("resume silently changed the frozen PDF scope")
        if same_state_path != state_path or resumed_job.get("attempts") != 2:
            raise AssertionError("resume did not update the same persistent heartbeat")

        packet_reader = reader_root / "B_reader"
        (packet_reader / "reader_wiki").mkdir(parents=True)
        pending = {
            "paper_id": "paper-b", "filename": "B.pdf", "reader_dir": str(packet_reader),
            "status": "pending", "failure_gate": "completion records",
            "pending_record_ids": ["block:S001", "block:S002", "block:S003"],
            "invalid_record_ids": [], "preflight_issues": [], "reasons": [],
        }
        packet = builder.write_authoring_packet(pending, packet_size=2)
        if packet is None or packet.get("record_ids") != ["block:S001", "block:S002"]:
            raise AssertionError("bounded authoring packet did not preserve the next resumable unit")
        if not (packet_reader / "reader_wiki" / "next_authoring_packet.json").is_file():
            raise AssertionError("authoring packet was not persisted")
        completed = dict(pending)
        completed["status"] = "formal_pass"
        complete_packet = builder.write_authoring_packet(completed, packet_size=2)
        if complete_packet is None or complete_packet.get("status") != "complete":
            raise AssertionError("completed reader did not close its persisted authoring packet")
        if complete_packet.get("record_ids") or complete_packet.get("remaining_record_count") != 0:
            raise AssertionError("completed authoring packet still advertises unfinished work")

        interrupted_at_60 = dict(pending)
        interrupted_at_60["pending_record_ids"] = [f"block:S{index:03d}" for index in range(61, 115)]
        packet_60 = builder.write_authoring_packet(interrupted_at_60, packet_size=12)
        if packet_60 is None or packet_60["record_ids"][0] != "block:S061" or len(packet_60["record_ids"]) != 12:
            raise AssertionError("60/114 interruption did not resume at the first unfinished record")
        interrupted_at_74 = dict(pending)
        interrupted_at_74["pending_record_ids"] = [f"block:S{index:03d}" for index in range(75, 115)]
        packet_74 = builder.write_authoring_packet(interrupted_at_74, packet_size=12)
        if packet_74 is None or packet_74["record_ids"][0] != "block:S075":
            raise AssertionError("74/114 interruption did not resume at the first unfinished record")
        _, third_job, third_state_path, _ = builder.load_or_create_job(
            pdf_dir=source_dir.resolve(), reader_root=reader_root.resolve(),
            discovered=builder.discover_pdfs(source_dir), max_papers=2, resume=True,
        )
        if third_state_path != state_path or third_job.get("attempts") != 3:
            raise AssertionError("second process restart did not retain the same job heartbeat")

        freeze_reader = reader_root / "freeze_reader"
        (freeze_reader / "reader_wiki").mkdir(parents=True)
        source_map = {
            "paper": {"source_pdf_sha256": "a" * 64}, "blocks": [],
            "figures": [], "tables": [], "algorithms": [],
        }
        (freeze_reader / "source_map.json").write_text(json.dumps(source_map), encoding="utf-8")
        frozen, reason = builder.ensure_source_map_lock(freeze_reader)
        if not frozen or reason or not (freeze_reader / "reader_wiki" / "source_map_lock.json").is_file():
            raise AssertionError("source map was not frozen before completion work")
        source_map["figures"] = [{"id": "F001", "page": 1}]
        (freeze_reader / "source_map.json").write_text(json.dumps(source_map), encoding="utf-8")
        frozen, reason = builder.ensure_source_map_lock(freeze_reader)
        if frozen or "changed after" not in reason:
            raise AssertionError("post-freeze source-map mutation was not rejected")

        controller_source = (SCRIPTS / "build_formal_reader_batch.py").read_text(encoding="utf-8")
        if "from reader_continuation_guard import guard as enforce_continuation_guard" not in controller_source:
            raise AssertionError("continuation guard is not integrated into the production controller")

    print("agent batch continuation contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
