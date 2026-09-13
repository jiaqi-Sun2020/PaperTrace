#!/usr/bin/env python3
"""Build/resume formal readers for exactly the PDFs in one explicit directory.

The user-selected ``--pdf-dir`` is the input authority. The command captures
its immediate PDF children (stable sort + SHA-256), freezes the selected scope
in ``<reader-root>/.papertrace_jobs/``, and resumes that exact scope even when
the source directory later gains unrelated PDFs. It never infers inputs from
nested derived-reader folders.

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
JOB_SCHEMA_VERSION = 1
JOB_DIR_NAME = ".papertrace_jobs"
DEFAULT_WORK_PACKET_SIZE = 12

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


def job_scope_id(pdf_dir: Path, reader_root: Path, max_papers: int | None) -> str:
    payload = {
        "pdf_dir": str(pdf_dir.resolve()),
        "reader_root": str(reader_root.resolve()),
        "max_papers": max_papers,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def job_paths(pdf_dir: Path, reader_root: Path, max_papers: int | None) -> tuple[Path, Path]:
    job_dir = reader_root / JOB_DIR_NAME / job_scope_id(pdf_dir, reader_root, max_papers)
    return job_dir / "orchestration_state.json", job_dir / "last_batch_report.json"


def validate_selected_papers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated: list[dict[str, Any]] = []
    for row in rows:
        paper = dict(row)
        path = Path(str(paper.get("pdf_path") or "")).expanduser().resolve()
        if not path.is_file():
            raise TerminalBlocker(
                "source_unavailable",
                f"selected PDF is no longer available: {path}",
                paper=paper,
                gate="persisted input snapshot",
            )
        actual_hash = sha256_file(path)
        if actual_hash != str(paper.get("sha256") or "").lower():
            raise TerminalBlocker(
                "source_unreadable",
                f"selected PDF changed after the persisted input snapshot: {path.name}",
                paper=paper,
                gate="persisted input snapshot",
            )
        paper["pdf_path"] = str(path)
        validated.append(paper)
    return validated


def load_or_create_job(
    *,
    pdf_dir: Path,
    reader_root: Path,
    discovered: list[dict[str, Any]],
    max_papers: int | None,
    resume: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], Path, Path]:
    state_path, report_path = job_paths(pdf_dir, reader_root, max_papers)
    if state_path.exists():
        if not resume:
            raise ValueError(f"persisted reader job already exists; rerun with --resume: {state_path}")
        state = read_json(state_path)
        if state.get("schema_version") != JOB_SCHEMA_VERSION:
            raise ValueError(f"unsupported reader orchestration schema: {state_path}")
        if str(state.get("pdf_dir") or "") != str(pdf_dir) or str(state.get("reader_root") or "") != str(reader_root):
            raise ValueError("persisted reader job scope does not match the requested roots")
        if state.get("max_papers") != max_papers:
            raise ValueError("persisted reader job max_papers does not match the request")
        selected = validate_selected_papers(list(state.get("selected_papers") or []))
        if not selected:
            raise ValueError("persisted reader job has no selected papers")
        state["attempts"] = int(state.get("attempts") or 0) + 1
        state["heartbeat_at"] = utc_now()
        state["updated_at"] = state["heartbeat_at"]
        atomic_write_json(state_path, state)
        return selected, state, state_path, report_path

    if max_papers is not None and max_papers < 1:
        raise ValueError("--max-papers must be a positive integer")
    selected = discovered[:max_papers] if max_papers is not None else discovered
    if not selected:
        raise TerminalBlocker("source_unavailable", "the selected PDF scope is empty", gate="input selection")
    now = utc_now()
    state = {
        "schema_version": JOB_SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "job_id": job_scope_id(pdf_dir, reader_root, max_papers),
        "status": "active",
        "created_at": now,
        "updated_at": now,
        "heartbeat_at": now,
        "attempts": 1,
        "pdf_dir": str(pdf_dir),
        "reader_root": str(reader_root),
        "max_papers": max_papers,
        "discovered_count_at_start": len(discovered),
        "selected_papers": selected,
        "active_phase": "input_snapshot",
        "active_paper": None,
        "next_command": None,
        "last_guard": None,
    }
    atomic_write_json(state_path, state)
    return selected, state, state_path, report_path


def source_map_lock_path(reader_dir: Path) -> Path:
    return reader_dir / "reader_wiki" / "source_map_lock.json"


def unregistered_object_issues(preflight: dict[str, Any]) -> list[str]:
    return [
        str(issue)
        for issue in preflight.get("issues", [])
        if re.search(r"\bunregistered\s+(?:figure|table|algorithm|pseudocode)\b", str(issue), re.I)
    ]


def ensure_source_map_lock(reader_dir: Path) -> tuple[bool, str]:
    source_map_path = reader_dir / "source_map.json"
    current_hash = sha256_file(source_map_path)
    lock_path = source_map_lock_path(reader_dir)
    if lock_path.exists():
        lock = read_json(lock_path)
        locked_hash = str(lock.get("source_map_sha256") or "")
        if locked_hash != current_hash:
            return False, (
                "source_map.json changed after object discovery was frozen; review and explicitly rebuild "
                "the completion state from the immutable PDF evidence"
            )
        return True, ""
    atomic_write_json(lock_path, {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "status": "frozen",
        "frozen_at": utc_now(),
        "source_map_path": "source_map.json",
        "source_map_sha256": current_hash,
        "source_pdf_sha256": str((read_json(source_map_path).get("paper") or {}).get("source_pdf_sha256") or "").lower(),
        "rule": "object identities must be registered before completion records are seeded",
    })
    return True, ""


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
    legacy_source: Path | None = None
    needs_initialization = False
    if not reader_dir.exists():
        create_bundle(pdf_path, reader_dir)
        legacy_source = external_legacy_paper(pdf_path)
        needs_initialization = True
        mode = "external_legacy_discovered" if legacy_source is not None else "new_bundle_object_discovery"
    elif not source_map_path.exists():
        if not resume:
            raise ValueError(f"existing reader has no immutable source_map.json: {reader_dir}")
        create_bundle(pdf_path, reader_dir, resume_incomplete=True)
        legacy_source = external_legacy_paper(pdf_path)
        needs_initialization = True
        mode = "resumed_incomplete_extraction"
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
            needs_initialization = True
            legacy_source = reader_dir / "paper.md" if (reader_dir / "paper.md").exists() else None
            mode = "legacy_object_discovery"
        else:
            mode = "resumed"

    # Object identity is part of immutable evidence. Discover/register every
    # figure, table, and algorithm before freezing the source map and seeding
    # semantic completion records. Asset crops may be completed later without
    # changing those identities.
    discovery_preflight = write_preflight(reader_dir)
    discovery_issues = unregistered_object_issues(discovery_preflight)
    if discovery_issues:
        state = update_run_state(reader_dir, last_failure_gate="object discovery before source-map freeze")
        progress = render_progress_html(reader_dir)
        make_incomplete_status(reader_dir, state, discovery_preflight)
        return {
            "order": paper["order"], "paper_id": paper["paper_id"], "filename": paper["filename"],
            "reader_dir": str(reader_dir), "mode": mode, "status": "pending",
            "records": f"{state['completed_records']}/{state['expected_records']}",
            "pending_records": len(state["pending_records"]), "invalid_records": len(state["invalid_records"]),
            "pending_record_ids": state["pending_records"], "invalid_record_ids": state["invalid_records"],
            "preflight": discovery_preflight["status"], "preflight_issues": discovery_preflight["issues"],
            "failure_gate": "object discovery before source-map freeze",
            "progress_html": str(progress),
        }

    frozen, freeze_reason = ensure_source_map_lock(reader_dir)
    if not frozen:
        state = update_run_state(reader_dir, last_failure_gate="source-map freeze")
        progress = render_progress_html(reader_dir)
        return {
            "order": paper["order"], "paper_id": paper["paper_id"], "filename": paper["filename"],
            "reader_dir": str(reader_dir), "mode": mode, "status": "invalid",
            "records": f"{state['completed_records']}/{state['expected_records']}",
            "pending_records": len(state["pending_records"]), "invalid_records": len(state["invalid_records"]),
            "pending_record_ids": state["pending_records"], "invalid_record_ids": state["invalid_records"],
            "preflight": discovery_preflight["status"], "preflight_issues": discovery_preflight["issues"],
            "failure_gate": "source-map freeze", "progress_html": str(progress),
            "reasons": [freeze_reason],
        }

    if needs_initialization and legacy_source is not None:
        migrate_legacy(reader_dir, legacy_source)
        mode = "external_legacy_migrated" if legacy_source.resolve().parent != reader_dir.resolve() else "legacy_migrated"
    else:
        seed_records(reader_dir)
        if needs_initialization:
            mode = "new_bundle_seeded_pending"

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


def result_phase(result: dict[str, Any]) -> str:
    if result.get("status") == "formal_pass":
        return "formal_pass"
    gate = str(result.get("failure_gate") or "").lower()
    if "object discovery" in gate:
        return "object_discovery"
    if "source-map freeze" in gate:
        return "source_map_review"
    if result.get("pending_record_ids") or result.get("invalid_record_ids"):
        return "semantic_completion"
    if "preflight" in gate:
        return "object_preflight"
    if result.get("status") == "invalid":
        return "formal_render_audit"
    return "controller_repair"


def write_authoring_packet(result: dict[str, Any], *, packet_size: int) -> dict[str, Any] | None:
    reader_dir = Path(str(result["reader_dir"])).resolve()
    path = reader_dir / "reader_wiki" / "next_authoring_packet.json"
    if result.get("status") == "formal_pass":
        if not path.exists():
            return None
        payload = {
            "schema_version": 1,
            "pipeline_version": PIPELINE_VERSION,
            "generated_at": utc_now(),
            "status": "complete",
            "phase": "formal_pass",
            "paper_id": result.get("paper_id"),
            "filename": result.get("filename"),
            "reader_dir": str(reader_dir),
            "packet_size": packet_size,
            "record_ids": [],
            "remaining_record_count": 0,
            "preflight_issues": [],
            "formal_errors": [],
            "instruction": "No authoring work remains; the audited formal reader is complete.",
        }
        atomic_write_json(path, payload)
        result["phase"] = "formal_pass"
        result["authoring_packet"] = str(path)
        result["authoring_packet_record_ids"] = []
        return payload
    if result.get("status") not in {"pending", "invalid"}:
        return None
    pending = [str(item) for item in result.get("invalid_record_ids") or []]
    pending.extend(str(item) for item in result.get("pending_record_ids") or [] if str(item) not in pending)
    selected = pending[:packet_size]
    phase = result_phase(result)
    payload = {
        "schema_version": 1,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": utc_now(),
        "status": "action_required",
        "phase": phase,
        "paper_id": result.get("paper_id"),
        "filename": result.get("filename"),
        "reader_dir": str(reader_dir),
        "packet_size": packet_size,
        "record_ids": selected,
        "remaining_record_count": len(pending),
        "preflight_issues": list(result.get("preflight_issues") or []),
        "formal_errors": list(result.get("reasons") or []),
        "instruction": (
            "The current-session primary model must complete only these source-bound records or repair the named gate, "
            "persist each result atomically, then rerun the controller. This packet is workflow state, not paper content."
        ),
    }
    atomic_write_json(path, payload)
    result["phase"] = phase
    result["authoring_packet"] = str(path)
    result["authoring_packet_record_ids"] = selected
    return payload


def resume_command(
    pdf_dir: Path,
    reader_root: Path,
    *,
    strict_exit: bool = False,
    agent_continuation: bool = False,
    max_papers: int | None = None,
    work_packet_size: int = DEFAULT_WORK_PACKET_SIZE,
) -> str:
    command = (
        'python .\\skills\\reader-skill\\scripts\\build_formal_reader_batch.py '
        f'--pdf-dir "{pdf_dir}" --reader-root "{reader_root}" --resume'
    )
    if max_papers is not None:
        command += f" --max-papers {max_papers}"
    command += f" --work-packet-size {work_packet_size}"
    if strict_exit:
        return command + " --strict-exit"
    return command + (" --agent-continuation" if agent_continuation else "")


def build_agent_contract(
    *,
    pdf_dir: Path,
    reader_root: Path,
    results: list[dict[str, Any]],
    agent_continuation: bool = False,
    max_papers: int | None = None,
    work_packet_size: int = DEFAULT_WORK_PACKET_SIZE,
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
        "next_command": None if blocker or all_formal else resume_command(
            pdf_dir, reader_root, agent_continuation=agent_continuation,
            max_papers=max_papers, work_packet_size=work_packet_size,
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
    parser.add_argument("--pdf-dir", required=True, type=Path, help="Exact source directory; selection is frozen in the job state")
    parser.add_argument("--reader-root", type=Path, default=DEFAULT_READER_ROOT, help="D: derived reader root under this project")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-papers", type=int, help="Freeze only the first N deterministically sorted PDFs into this job")
    parser.add_argument("--work-packet-size", type=int, default=DEFAULT_WORK_PACKET_SIZE, help="Maximum source-bound record IDs in the next authoring packet")
    parser.add_argument("--strict-exit", action="store_true", help="Return 1 for action_required (intended for CI only)")
    parser.add_argument(
        "--agent-continuation",
        action="store_true",
        help="Emit and persist an enforced must_continue contract while keeping the shell exit tool-safe",
    )
    args = parser.parse_args(argv)
    if args.strict_exit and args.agent_continuation:
        parser.error("--strict-exit and --agent-continuation are mutually exclusive")
    if args.work_packet_size < 1:
        parser.error("--work-packet-size must be a positive integer")
    job_state: dict[str, Any] | None = None
    job_state_path: Path | None = None
    report_path: Path | None = None
    try:
        pdf_dir, reader_root = validate_roots(args.pdf_dir, args.reader_root)
        discovered = discover_pdfs(pdf_dir)
        papers, job_state, job_state_path, report_path = load_or_create_job(
            pdf_dir=pdf_dir,
            reader_root=reader_root,
            discovered=discovered,
            max_papers=args.max_papers,
            resume=args.resume,
        )
        input_snapshot = build_input_snapshot(pdf_dir, papers)
        input_snapshot["selection_policy"] = {
            "kind": "deterministic-prefix" if args.max_papers is not None else "frozen-all-at-start",
            "max_papers": args.max_papers,
            "discovered_count_at_start": job_state.get("discovered_count_at_start"),
            "persisted_job_state": str(job_state_path),
        }
        results = process_papers_sequentially(papers, reader_root, resume=args.resume)
        for result in results:
            write_authoring_packet(result, packet_size=args.work_packet_size)
    except TerminalBlocker as exc:
        payload = {
            "status": "blocked",
            "requested_artifact_ready": False,
            "final_response_allowed": True,
            "must_continue": False,
            "terminal_blocker": exc.payload(),
        }
        if job_state is not None and job_state_path is not None:
            job_state.update({"status": "blocked", "updated_at": utc_now(), "heartbeat_at": utc_now(), "terminal_blocker": exc.payload()})
            atomic_write_json(job_state_path, job_state)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3
    except Exception as exc:
        payload = {
            "status": "failed",
            "requested_artifact_ready": False,
            "final_response_allowed": False,
            "must_continue": True,
            "terminal_blocker": None,
            "error": str(exc),
        }
        if job_state is not None and job_state_path is not None:
            job_state.update({"status": "active", "updated_at": utc_now(), "heartbeat_at": utc_now(), "last_error": str(exc)})
            atomic_write_json(job_state_path, job_state)
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    all_formal = all(row["status"] == "formal_pass" for row in results)
    contract = build_agent_contract(
        pdf_dir=pdf_dir,
        reader_root=reader_root,
        results=results,
        agent_continuation=args.agent_continuation,
        max_papers=args.max_papers,
        work_packet_size=args.work_packet_size,
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
        "orchestration_state_path": str(job_state_path),
        "source_set_sha256": input_snapshot["source_set_sha256"],
        "input_snapshot": input_snapshot,
        "agent_continuation_contract": contract,
        "formal_artifact_manifest": formal_manifest,
        "results": results,
    }
    # The guard is part of the production controller, not merely a unit-test
    # helper. Its must_continue code is embedded as state; interactive tool
    # execution remains exit-0 so a normal checkpoint is not mislabeled as a
    # process failure.
    from reader_continuation_guard import guard as enforce_continuation_guard
    guard_code, guard_payload = enforce_continuation_guard(batch_report)
    batch_report["enforced_guard"] = guard_payload
    if job_state is not None and job_state_path is not None and report_path is not None:
        active = next((row for row in results if row.get("status") in {"pending", "invalid", "blocked"}), None)
        now = utc_now()
        job_state.update({
            "status": "complete" if all_formal else "blocked" if contract["status"] == "blocked" else "active",
            "updated_at": now,
            "heartbeat_at": now,
            "source_set_sha256": input_snapshot["source_set_sha256"],
            "active_phase": result_phase(active) if active else "complete",
            "active_paper": ({
                "paper_id": active.get("paper_id"),
                "filename": active.get("filename"),
                "reader_dir": active.get("reader_dir"),
                "phase": result_phase(active),
                "authoring_packet": active.get("authoring_packet"),
            } if active else None),
            "next_command": contract.get("next_command"),
            "last_guard": guard_payload,
            "last_batch_report": str(report_path),
            "terminal_blocker": contract.get("terminal_blocker"),
        })
        job_state.pop("last_error", None)
        atomic_write_json(report_path, batch_report)
        atomic_write_json(job_state_path, job_state)
    print(json.dumps(batch_report, ensure_ascii=False, indent=2))
    if guard_code == 2:
        return 2
    if contract["status"] == "blocked":
        return 3
    if all_formal:
        return 0
    return 1 if args.strict_exit else 0


if __name__ == "__main__":
    raise SystemExit(main())
