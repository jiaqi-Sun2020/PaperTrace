#!/usr/bin/env python3
"""Fail closed on a formal-reader batch report before an agent replies.

This guard is content-free: it never edits reader bundles or supplies
translations. It only converts the controller contract into an explicit
reply/continue boundary for the calling agent.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = ROOT / "skills" / "reader-skill" / "tests" / "adversarial_batch_audit.py"
MUST_CONTINUE_EXIT = 75
BLOCKED_EXIT = 3


def load_auditor() -> Any:
    spec = importlib.util.spec_from_file_location("reader_batch_guard_audit", AUDIT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load batch auditor: {AUDIT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_report(value: str) -> dict[str, Any]:
    payload = json.load(sys.stdin) if value == "-" else json.loads(Path(value).expanduser().resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("batch report must be a JSON object")
    return payload


def guard(report: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    issues = load_auditor().audit_batch_report(report, run_reader_audits=False)
    if issues:
        return 2, {"status": "invalid_report", "final_response_allowed": False, "issues": issues}
    contract = report["agent_continuation_contract"]
    if contract.get("must_continue"):
        return MUST_CONTINUE_EXIT, {
            "status": "must_continue",
            "final_response_allowed": False,
            "persistent_goal_action": "keep_active",
            "instruction": "DO NOT SEND final_answer and do not complete the active goal: complete active_paper from PDF evidence, then rerun next_command.",
            "final_response_prohibited_reason": contract.get("final_response_prohibited_reason"),
            "active_paper": contract.get("active_paper") or {},
            "next_command": contract.get("next_command"),
        }
    if report.get("terminal_blocker") is not None:
        return BLOCKED_EXIT, {"status": "blocked", "final_response_allowed": True, "persistent_goal_action": "report_blocker", "terminal_blocker": report.get("terminal_blocker")}
    return 0, {"status": "complete", "final_response_allowed": True, "persistent_goal_action": "complete", "reportable_formal_html": contract.get("reportable_formal_html") or []}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", nargs="?", default="-", help="controller JSON file, or - for standard input")
    args = parser.parse_args()
    try:
        code, payload = guard(read_report(args.report))
    except Exception as exc:
        code, payload = 2, {"status": "invalid_report", "final_response_allowed": False, "issues": [str(exc)]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
