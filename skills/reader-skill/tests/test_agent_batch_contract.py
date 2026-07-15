#!/usr/bin/env python3
"""Regression tests for one-request, one-active-paper batch continuation."""

from __future__ import annotations

import importlib.util
import hashlib
import json
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

        snapshot = {"source_set_sha256": "fixture-set", "papers": papers()}
        state = {
            "schema_version": 3, "status": "action_required", "final_response_allowed": False,
            "must_continue": True, "terminal_blocker": None, "results": results,
            "reader_root": str(root), "source_set_sha256": "fixture-set",
            "input_snapshot": snapshot, "agent_continuation_contract": contract,
            "formal_artifact_manifest": None,
        }
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
            "formal_artifact_manifest": None,
        }
        blocked_issues = auditor.audit_batch_report(blocked_state, run_reader_audits=False)
        blocked_structural = [issue for issue in blocked_issues if "formal result HTML is missing" not in issue]
        if blocked_structural:
            raise AssertionError(f"authorized blocked state failed adversarial audit: {blocked_structural}")
        blocked_code, blocked_payload = guard.guard(blocked_state)
        if blocked_code != 3 or blocked_payload.get("status") != "blocked":
            raise AssertionError("continuation guard did not preserve an authorized terminal blocker")

        if (root / ".reader_pipeline_runs").exists() or (root / "reader_batch_state.json").exists():
            raise AssertionError("controller contract tests created forbidden batch state artifacts")

    print("agent batch continuation contract tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
