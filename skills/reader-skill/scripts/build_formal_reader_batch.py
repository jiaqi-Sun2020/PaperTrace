#!/usr/bin/env python3
"""Build/resume formal readers for exactly the PDFs in one explicit directory.

The user-selected ``--pdf-dir`` is the input authority. The command captures
its immediate PDF children (stable sort + SHA-256) in its JSON standard output;
it never creates batch-history/state files, reads a hand-maintained batch
manifest, or infers PDFs from nested derived-reader folders.

This command is also the machine-readable controller for a user-facing agent
run.  It activates only the first non-formal paper, never starts later papers
while an earlier one needs semantic completion, and writes an explicit
continuation contract.  Expected model-authorship work is ``action_required``
rather than a process failure; use ``--strict-exit`` only in CI when a nonzero
exit for incomplete work is desirable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from completion_state import (
    PIPELINE_VERSION,
    atomic_write_json,
    clear_stale_after_audit,
    compile_canonical_markdown,
    ensure_object_inventory,
    migrate_legacy,
    read_json,
    reader_is_formal_ready,
    render_progress_html,
    seed_records,
    sha256_file,
    update_run_state,
)


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_READER_ROOT = ROOT / "2026" / "7"
TERMINAL_BLOCKER_KINDS = {
    "source_unavailable",
    "source_unreadable",
    "ambiguous_completed_bundle_overwrite",
    "irreparable_pdf_evidence_validation",
}
AGENT_CONTINUATION_EXIT = 75

NATURE_SCRIPTS = ROOT / "skills" / "nature-reader" / "scripts"
if str(NATURE_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(NATURE_SCRIPTS))
from extract_pdf_bundle import create_bundle  # noqa: E402
from preflight_reader_bundle import build_preflight_manifest, write_json as write_preflight_json  # noqa: E402


class TerminalBlocker(RuntimeError):
    """One of the narrow project-authorized reasons to stop the agent loop."""

    def __init__(self, kind: str, message: str, *, paper: dict[str, Any] | None = None, gate: str = "") -> None:
        if kind not in TERMINAL_BLOCKER_KINDS:
            raise ValueError(f"unknown terminal blocker kind: {kind}")
        super().__init__(message)
        self.kind = kind
        self.paper = paper or {}
        self.gate = gate

    def payload(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": str(self),
            "paper_id": self.paper.get("paper_id") or "",
            "filename": self.paper.get("filename") or "",
            "gate": self.gate,
        }


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def stable_paper_id(pdf_path: Path) -> str:
    stem = pdf_path.stem.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower()
    if not slug:
        slug = "paper"
    path_digest = hashlib.sha256(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:10]
    return f"{slug[:72]}--{path_digest}"


def validate_roots(pdf_dir: Path, reader_root: Path) -> tuple[Path, Path]:
    source = pdf_dir.expanduser().resolve()
    output = reader_root.expanduser().resolve()
    if not source.is_dir():
        raise TerminalBlocker("source_unavailable", f"--pdf-dir is unavailable: {source}", gate="input discovery")
    if not is_within(output, ROOT):
        raise ValueError("--reader-root must remain inside D:\\AI\\PaperTrace")
    if is_within(source, ROOT):
        raise ValueError("--pdf-dir must be outside the project write root; source corpus is read-only")
    if is_within(output, source) or is_within(source, output):
        raise ValueError("source PDF directory and D: reader output root must be disjoint")
    output.mkdir(parents=True, exist_ok=True)
    return source, output


def discover_pdfs(pdf_dir: Path) -> list[dict[str, Any]]:
    pdfs = sorted(
        (path for path in pdf_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: (str(path.relative_to(pdf_dir)).casefold(), str(path.relative_to(pdf_dir))),
    )
    if not pdfs:
        raise TerminalBlocker(
            "source_unavailable",
            f"--pdf-dir contains no immediate PDF files: {pdf_dir}",
            gate="input discovery",
        )
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for order, pdf_path in enumerate(pdfs, start=1):
        paper_id = stable_paper_id(pdf_path)
        if paper_id in seen_ids:
            raise ValueError(f"unstable duplicate PDF identity: {pdf_path.name}")
        seen_ids.add(paper_id)
        rows.append({
            "order": order,
            "paper_id": paper_id,
            "filename": pdf_path.name,
            "relative_path": pdf_path.relative_to(pdf_dir).as_posix(),
            "pdf_path": str(pdf_path.resolve()),
            "sha256": sha256_file(pdf_path),
        })
    return rows


def source_set_hash(pdf_dir: Path, rows: list[dict[str, Any]]) -> str:
    payload = {
        "pdf_dir": str(pdf_dir.resolve()),
        "papers": [{key: row[key] for key in ("order", "paper_id", "filename", "relative_path", "pdf_path", "sha256")} for row in rows],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_input_snapshot(pdf_dir: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    set_hash = source_set_hash(pdf_dir, rows)
    return {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "created_at": utc_now(),
        "input_authority": "explicit --pdf-dir immediate PDF discovery",
        "pdf_dir": str(pdf_dir),
        "source_set_sha256": set_hash,
        "expected_count": len(rows),
        "papers": rows,
    }


def reader_dir_for(paper: dict[str, Any], reader_root: Path) -> Path:
    return reader_root / f"{Path(str(paper['pdf_path'])).stem}_reader"


def external_legacy_paper(pdf_path: Path) -> Path | None:
    """Recognize a read-only legacy bundle without writing into it."""
    candidate = pdf_path.parent
    paper = candidate / "paper.md"
    source_map = candidate / "source_map.json"
    return paper if paper.is_file() and source_map.is_file() else None


def write_preflight(reader_dir: Path) -> dict[str, Any]:
    ensure_object_inventory(reader_dir)
    manifest, issues = build_preflight_manifest(reader_dir)
    write_preflight_json(reader_dir / "reader_wiki" / "preflight_manifest.json", manifest)
    return {"status": manifest["status"], "issues": issues}


def make_incomplete_status(reader_dir: Path, state: dict[str, Any], preflight: dict[str, Any]) -> None:
    status_path = reader_dir / "reader_wiki" / "formal_status.json"
    existing = read_json(status_path) if status_path.exists() else {}
    if existing.get("status") == "stale":
        return
    atomic_write_json(status_path, {
        "schema_version": 3,
        "pipeline_version": PIPELINE_VERSION,
        "status": "incomplete",
        "updated_at": utc_now(),
        "completion_status": state["status"],
        "preflight_status": preflight["status"],
        "html_path": "reader_interactive.html",
    })


def try_formal_build(reader_dir: Path) -> tuple[bool, list[str]]:
    ready, reasons = reader_is_formal_ready(reader_dir)
    if not ready:
        return False, reasons
    compile_canonical_markdown(reader_dir, materialize_paper=True)
    converter = ROOT / "skills" / "reader-skill" / "scripts" / "markdown_reader_to_html.py"
    audit = ROOT / "skills" / "reader-skill" / "tests" / "adversarial_html_audit.py"
    for command in ([sys.executable, str(converter), str(reader_dir)], [sys.executable, str(audit), str(reader_dir)]):
        result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
        if result.returncode:
            return False, [result.stderr.strip() or result.stdout.strip() or "formal build command failed"]
    clear_stale_after_audit(reader_dir)
    return True, []


def process_paper(paper: dict[str, Any], reader_root: Path, *, resume: bool) -> dict[str, Any]:
    reader_dir = reader_dir_for(paper, reader_root)
    pdf_path = Path(str(paper["pdf_path"])).resolve()
    source_map_path = reader_dir / "source_map.json"
    if not reader_dir.exists():
        create_bundle(pdf_path, reader_dir)
        external_paper = external_legacy_paper(pdf_path)
        if external_paper is not None:
            migrate_legacy(reader_dir, external_paper)
            mode = "external_legacy_migrated"
        else:
            seed_records(reader_dir)
            mode = "new_bundle_seeded_pending"
    elif not source_map_path.exists():
        raise ValueError(f"existing reader has no immutable source_map.json: {reader_dir}")
    else:
        source_map = read_json(source_map_path)
        existing_hash = str((source_map.get("paper") or {}).get("source_pdf_sha256") or "").lower()
        if existing_hash != str(paper["sha256"]).lower():
            raise TerminalBlocker(
                "ambiguous_completed_bundle_overwrite",
                f"reader source hash conflicts with selected PDF: {reader_dir.name}",
                paper=paper,
                gate="immutable source identity",
            )
        if not resume:
            raise ValueError(f"reader already exists; rerun only with --resume: {reader_dir}")
        if not (reader_dir / "reader_wiki" / "completion_run_state.json").exists():
            migrate_legacy(reader_dir)
            mode = "legacy_migrated"
        else:
            seed_records(reader_dir)
            mode = "resumed"

    state = update_run_state(reader_dir, last_failure_gate="completion records")
    if state["status"] == "pass":
        compile_canonical_markdown(reader_dir, materialize_paper=True)
    preflight = write_preflight(reader_dir)
    state = update_run_state(
        reader_dir,
        last_failure_gate="object preflight" if preflight["status"] != "pass" else "completion records",
    )
    progress = render_progress_html(reader_dir)
    if state["status"] != "pass" or preflight["status"] != "pass":
        make_incomplete_status(reader_dir, state, preflight)
        return {
            "order": paper["order"], "paper_id": paper["paper_id"], "filename": paper["filename"],
            "reader_dir": str(reader_dir), "mode": mode,
            "status": "pending", "records": f"{state['completed_records']}/{state['expected_records']}",
            "pending_records": len(state["pending_records"]), "invalid_records": len(state["invalid_records"]),
            "pending_record_ids": state["pending_records"], "invalid_record_ids": state["invalid_records"],
            "preflight": preflight["status"], "preflight_issues": preflight["issues"],
            "failure_gate": state.get("last_failure_gate") or "completion records",
            "progress_html": str(progress),
        }
    formal, reasons = try_formal_build(reader_dir)
    result = {
        "order": paper["order"], "paper_id": paper["paper_id"], "filename": paper["filename"],
        "reader_dir": str(reader_dir), "mode": mode,
        "status": "formal_pass" if formal else "invalid", "records": f"{state['completed_records']}/{state['expected_records']}",
        "pending_records": len(state["pending_records"]), "invalid_records": len(state["invalid_records"]),
        "pending_record_ids": state["pending_records"], "invalid_record_ids": state["invalid_records"],
        "preflight": preflight["status"], "preflight_issues": preflight["issues"],
        "failure_gate": "formal render/audit" if reasons else "",
        "progress_html": str(progress), "reasons": reasons,
    }
    if formal:
        result["html"] = str(reader_dir / "reader_interactive.html")
    return result


def queued_result(paper: dict[str, Any], reader_root: Path) -> dict[str, Any]:
    """Describe an untouched later paper without creating or mutating its bundle."""
    return {
        "order": paper["order"],
        "paper_id": paper["paper_id"],
        "filename": paper["filename"],
        "reader_dir": str(reader_dir_for(paper, reader_root)),
        "status": "queued",
        "reason": "an earlier paper must reach audited formal_pass first",
    }


def process_papers_sequentially(
    papers: list[dict[str, Any]],
    reader_root: Path,
    *,
    resume: bool,
    processor: Any | None = None,
) -> list[dict[str, Any]]:
    """Process a formal prefix plus at most one active non-formal paper."""
    process = processor or process_paper
    results: list[dict[str, Any]] = []
    active_seen = False
    for paper in papers:
        if active_seen:
            results.append(queued_result(paper, reader_root))
            continue
        try:
            result = process(paper, reader_root, resume=resume)
        except TerminalBlocker as exc:
            result = {
                "order": paper["order"],
                "paper_id": paper["paper_id"],
                "filename": paper["filename"],
                "reader_dir": str(reader_dir_for(paper, reader_root)),
                "status": "blocked",
                "terminal_blocker": exc.payload(),
            }
        results.append(result)
        if result.get("status") != "formal_pass":
            active_seen = True
    return results


def resume_command(
    pdf_dir: Path,
    reader_root: Path,
    *,
    strict_exit: bool = False,
    agent_continuation: bool = False,
) -> str:
    command = (
        'python .\\skills\\reader-skill\\scripts\\build_formal_reader_batch.py '
        f'--pdf-dir "{pdf_dir}" --reader-root "{reader_root}" --resume'
    )
    if strict_exit:
        return command + " --strict-exit"
    return command + (" --agent-continuation" if agent_continuation else "")


def build_agent_contract(
    *,
    pdf_dir: Path,
    reader_root: Path,
    results: list[dict[str, Any]],
    agent_continuation: bool = False,
) -> dict[str, Any]:
    """Create the fail-closed contract consumed after every controller run."""
    all_formal = bool(results) and all(row.get("status") == "formal_pass" for row in results)
    active = next((row for row in results if row.get("status") in {"pending", "invalid", "blocked"}), None)
    blocker = active.get("terminal_blocker") if active and active.get("status") == "blocked" else None
    final_allowed = all_formal or blocker is not None
    reportable = [
        {"order": row["order"], "paper_id": row["paper_id"], "filename": row["filename"], "html": row["html"]}
        for row in results
        if row.get("status") == "formal_pass" and row.get("html")
    ]
    contract: dict[str, Any] = {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "updated_at": utc_now(),
        "status": "complete" if all_formal else "blocked" if blocker else "must_continue",
        "requested_artifact_ready": all_formal,
        "final_response_allowed": final_allowed,
        "must_continue": not final_allowed,
        "persistent_goal_action": "complete" if all_formal else "report_blocker" if blocker else "keep_active",
        "final_response_prohibited_reason": (
            None
            if final_allowed
            else "The requested audited reader HTML is not ready; keep the persistent goal active and continue the same task."
        ),
        "terminal_blocker": blocker,
        "reportable_formal_html": reportable,
        "active_paper": None,
        "next_command": None if blocker else resume_command(
            pdf_dir, reader_root, agent_continuation=agent_continuation,
        ),
    }
    if active is not None:
        contract["active_paper"] = {
            "order": active["order"],
            "paper_id": active["paper_id"],
            "filename": active["filename"],
            "reader_dir": active["reader_dir"],
            "status": active["status"],
            "failure_gate": active.get("failure_gate") or "completion records",
            "pending_record_ids": active.get("pending_record_ids") or [],
            "invalid_record_ids": active.get("invalid_record_ids") or [],
            "preflight_issues": active.get("preflight_issues") or [],
            "formal_errors": active.get("reasons") or [],
        }
        if blocker:
            contract["next_required_step"] = "Report the exact terminal blocker; do not claim the requested batch is complete."
        else:
            contract["next_required_step"] = (
                "The current-session primary model must complete/repair the active paper from PDF evidence, "
                "then rerun next_command. A pending or invalid gate is normal work, not a terminal blocker."
            )
    elif not all_formal:
        contract["next_required_step"] = "Repair the controller state; no active paper was selected."
    else:
        contract["next_required_step"] = "None; every selected PDF has an audited formal HTML artifact."
    return contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-dir", required=True, type=Path, help="Exact source directory; its PDFs are the whole batch")
    parser.add_argument("--reader-root", type=Path, default=DEFAULT_READER_ROOT, help="D: derived reader root under this project")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--strict-exit", action="store_true", help="Return 1 for action_required (intended for CI only)")
    parser.add_argument(
        "--agent-continuation",
        action="store_true",
        help=f"Return {AGENT_CONTINUATION_EXIT} for must_continue; intended for an interactive agent runner",
    )
    args = parser.parse_args(argv)
    if args.strict_exit and args.agent_continuation:
        parser.error("--strict-exit and --agent-continuation are mutually exclusive")
    try:
        pdf_dir, reader_root = validate_roots(args.pdf_dir, args.reader_root)
        papers = discover_pdfs(pdf_dir)
        input_snapshot = build_input_snapshot(pdf_dir, papers)
        results = process_papers_sequentially(papers, reader_root, resume=args.resume)
    except TerminalBlocker as exc:
        print(json.dumps({
            "status": "blocked",
            "requested_artifact_ready": False,
            "final_response_allowed": True,
            "must_continue": False,
            "terminal_blocker": exc.payload(),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except Exception as exc:
        print(json.dumps({
            "status": "failed",
            "requested_artifact_ready": False,
            "final_response_allowed": False,
            "must_continue": True,
            "terminal_blocker": None,
            "error": str(exc),
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    all_formal = all(row["status"] == "formal_pass" for row in results)
    contract = build_agent_contract(
        pdf_dir=pdf_dir,
        reader_root=reader_root,
        results=results,
        agent_continuation=args.agent_continuation,
    )
    formal_manifest = None
    if all_formal:
        formal_manifest = {
            "schema_version": 1,
            "pipeline_version": PIPELINE_VERSION,
            "formal_status": "pass",
            "generated_at": utc_now(),
            "source_set_sha256": input_snapshot["source_set_sha256"],
            "readers": [
                {"paper_id": row["paper_id"], "reader_dir": row["reader_dir"], "html": "reader_interactive.html"}
                for row in results
            ],
        }
    batch_report = {
        "schema_version": 3,
        "pipeline_version": PIPELINE_VERSION,
        "updated_at": utc_now(),
        "status": "formal_pass" if all_formal else "blocked" if contract["status"] == "blocked" else "action_required",
        "final_response_allowed": contract["final_response_allowed"],
        "must_continue": contract["must_continue"],
        "terminal_blocker": contract["terminal_blocker"],
        "reader_root": str(reader_root),
        "source_set_sha256": input_snapshot["source_set_sha256"],
        "input_snapshot": input_snapshot,
        "agent_continuation_contract": contract,
        "formal_artifact_manifest": formal_manifest,
        "results": results,
    }
    print(json.dumps(batch_report, ensure_ascii=False, indent=2))
    if contract["status"] == "blocked":
        return 3
    if all_formal:
        return 0
    if args.agent_continuation:
        return AGENT_CONTINUATION_EXIT
    return 1 if args.strict_exit else 0


if __name__ == "__main__":
    raise SystemExit(main())
