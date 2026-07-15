#!/usr/bin/env python3
"""Adversarially audit a directory batch controller JSON report.

This audit is intentionally independent from the controller.  It rejects
non-prefix execution, more than one active paper, reportable draft HTML,
contradictory continuation flags, and a batch-level formal manifest that
claims success while any selected paper is pending or queued.  Formal-prefix
readers are re-audited with the normal reader adversarial audit by default.
The report is ephemeral (normally piped on standard input); the audit also
rejects legacy batch-history/state artifacts under the reader root.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
READER_AUDIT = ROOT / "skills" / "reader-skill" / "tests" / "adversarial_html_audit.py"
TERMINAL_BLOCKER_KINDS = {
    "source_unavailable",
    "source_unreadable",
    "ambiguous_completed_bundle_overwrite",
    "irreparable_pdf_evidence_validation",
}


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_batch_report(report: dict[str, Any], *, run_reader_audits: bool = True) -> list[str]:
    issues: list[str] = []
    snapshot = report.get("input_snapshot") or {}
    state = report
    contract = report.get("agent_continuation_contract") or {}
    if not isinstance(snapshot, dict) or not isinstance(contract, dict):
        return ["input_snapshot and agent_continuation_contract must be embedded JSON objects"]
    reader_root_value = str(report.get("reader_root") or "").strip()
    if not reader_root_value:
        issues.append("batch report lacks reader_root")
    else:
        reader_root = Path(reader_root_value)
        if (reader_root / ".reader_pipeline_runs").exists():
            issues.append("forbidden legacy .reader_pipeline_runs directory exists")
        if (reader_root / "reader_batch_state.json").exists():
            issues.append("forbidden persisted reader_batch_state.json exists")
    if report.get("source_set_sha256") != snapshot.get("source_set_sha256"):
        issues.append("report source-set hash differs from the embedded input snapshot")
    papers = snapshot.get("papers") or []
    results = state.get("results") or []
    if not isinstance(papers, list) or not isinstance(results, list):
        return issues + ["snapshot papers and batch-report results must be lists"]
    if len(papers) != len(results):
        issues.append("batch-report result count differs from the current input snapshot")
        return issues
    if [row.get("paper_id") for row in papers] != [row.get("paper_id") for row in results]:
        issues.append("batch-report order/identity differs from the current input snapshot")

    statuses = [str(row.get("status") or "") for row in results]
    active_indexes = [index for index, status in enumerate(statuses) if status in {"pending", "invalid", "blocked"}]
    if len(active_indexes) > 1:
        issues.append("more than one paper is active; sequential one-paper execution was violated")
    active_index = active_indexes[0] if active_indexes else None
    for index, status in enumerate(statuses):
        if active_index is None:
            if status != "formal_pass":
                issues.append("a complete batch contains a non-formal result")
                break
        elif index < active_index and status != "formal_pass":
            issues.append("a paper before the active paper is not formal_pass")
        elif index == active_index and status not in {"pending", "invalid", "blocked"}:
            issues.append("active paper has an invalid status")
        elif index > active_index and status != "queued":
            issues.append("a later paper was touched before the active paper reached formal_pass")

    all_formal = bool(results) and all(status == "formal_pass" for status in statuses)
    blocked = active_index is not None and statuses[active_index] == "blocked"
    expected_state = "formal_pass" if all_formal else "blocked" if blocked else "action_required"
    if state.get("status") != expected_state:
        issues.append(f"batch-report status must be {expected_state!r}")
    if bool(state.get("final_response_allowed")) != (all_formal or blocked):
        issues.append("batch-report final_response_allowed contradicts batch completion")
    if bool(state.get("must_continue")) != (not all_formal and not blocked):
        issues.append("batch-report must_continue contradicts batch completion")
    state_blocker = state.get("terminal_blocker")
    if blocked:
        if not isinstance(state_blocker, dict) or state_blocker.get("kind") not in TERMINAL_BLOCKER_KINDS:
            issues.append("blocked batch report lacks an authorized terminal blocker")
    elif state_blocker is not None:
        issues.append("ordinary pending/invalid work was mislabeled as a terminal blocker")

    if contract.get("status") != ("complete" if all_formal else "blocked" if blocked else "must_continue"):
        issues.append("continuation-contract status contradicts batch completion")
    if bool(contract.get("requested_artifact_ready")) != all_formal:
        issues.append("requested_artifact_ready contradicts batch completion")
    if bool(contract.get("final_response_allowed")) != (all_formal or blocked):
        issues.append("continuation contract permits a premature final response")
    if bool(contract.get("must_continue")) != (not all_formal and not blocked):
        issues.append("continuation contract has an inverted must_continue flag")
    contract_blocker = contract.get("terminal_blocker")
    if blocked:
        if not isinstance(contract_blocker, dict) or contract_blocker.get("kind") not in TERMINAL_BLOCKER_KINDS:
            issues.append("blocked continuation contract lacks an authorized terminal blocker")
    elif contract_blocker is not None:
        issues.append("continuation contract invents a terminal blocker")

    active_contract = contract.get("active_paper")
    if all_formal and active_contract is not None:
        issues.append("complete continuation contract still names an active paper")
    if not all_formal:
        if not isinstance(active_contract, dict):
            issues.append("incomplete continuation contract lacks the active paper")
        elif active_index is not None and active_contract.get("paper_id") != results[active_index].get("paper_id"):
            issues.append("continuation contract points at the wrong active paper")
        if not blocked and not str(contract.get("next_command") or "").strip():
            issues.append("incomplete continuation contract lacks the exact resume command")

    expected_reportable = [
        str(row.get("html")) for row in results
        if row.get("status") == "formal_pass" and row.get("html")
    ]
    reportable_rows = contract.get("reportable_formal_html") or []
    reportable = [str(row.get("html")) for row in reportable_rows if isinstance(row, dict)]
    if reportable != expected_reportable:
        issues.append("reportable HTML set contains a draft, omits a formal prefix item, or is out of order")

    manifest = report.get("formal_artifact_manifest")
    if all_formal:
        if not isinstance(manifest, dict) or manifest.get("formal_status") != "pass":
            issues.append("complete batch report lacks an embedded passing formal artifact manifest")
        elif manifest.get("source_set_sha256") != snapshot.get("source_set_sha256"):
            issues.append("embedded formal artifact manifest has the wrong source-set hash")
    elif isinstance(manifest, dict) and manifest.get("formal_status") == "pass":
        issues.append("incomplete batch report contains a passing formal artifact manifest")

    for row in results:
        if row.get("status") != "formal_pass":
            if row.get("html"):
                issues.append(f"{row.get('filename')}: non-formal result exposes an HTML deliverable")
            continue
        reader_dir = Path(str(row.get("reader_dir") or ""))
        html_path = Path(str(row.get("html") or ""))
        if not html_path.is_file() or html_path.name != "reader_interactive.html":
            issues.append(f"{row.get('filename')}: formal result HTML is missing or misnamed")
            continue
        formal_status_path = reader_dir / "reader_wiki" / "formal_status.json"
        if not formal_status_path.is_file():
            issues.append(f"{row.get('filename')}: missing reader formal_status.json")
            continue
        formal_status = read_json(formal_status_path)
        if formal_status.get("status") != "formal_pass":
            issues.append(f"{row.get('filename')}: reader formal status is not formal_pass")
        if formal_status.get("html_sha256") != sha256_file(html_path):
            issues.append(f"{row.get('filename')}: reader HTML hash differs from formal status")
        if run_reader_audits:
            audited = subprocess.run(
                [sys.executable, str(READER_AUDIT), str(reader_dir)],
                cwd=ROOT,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
            )
            if audited.returncode:
                detail = audited.stderr.strip() or audited.stdout.strip() or "reader audit failed"
                issues.append(f"{row.get('filename')}: {detail}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", default="-", help="JSON report file, or - for standard input")
    parser.add_argument("--skip-reader-audits", action="store_true", help="Only for controller unit-test fixtures")
    args = parser.parse_args()
    if args.report == "-":
        report = json.load(sys.stdin)
        report_source = "stdin"
    else:
        report_path = Path(args.report).expanduser().resolve()
        report = read_json(report_path)
        report_source = str(report_path)
    if not isinstance(report, dict):
        raise ValueError("batch report must be a JSON object")
    issues = audit_batch_report(report, run_reader_audits=not args.skip_reader_audits)
    payload = {"status": "pass" if not issues else "fail", "report_source": report_source, "issues": issues}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
