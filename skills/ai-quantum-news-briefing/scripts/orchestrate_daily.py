"""Artifact-derived daily orchestration checkpoint; never approves a semantic review."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from daily_pipeline import NEWS_ROOT, load_json, sha256_file, verify_artifacts
from network_preflight import inspect_network

SCRIPT_DIR = Path(__file__).resolve().parent


def inspect(day: str, *, news_root: Path = NEWS_ROOT, online: bool = False) -> dict[str, Any]:
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("release date must be ISO YYYY-MM-DD")
    output = news_root / day
    collection = news_root / "_collection" / day
    manifest = output / ("daily_pipeline_manifest_" + day + ".json")
    stage_root = output / ".staging"
    state: dict[str, Any] = {"date": day, "remote_status": "not_checked"}
    if manifest.is_file():
        try:
            published = load_json(manifest)
            check = verify_artifacts(output, strict=True)
        except (OSError, ValueError) as exc:
            check = {"status": "fail", "failures": [exc.__class__.__name__]}
            published = {}
        if published.get("status") == "complete" and check.get("status") == "pass":
            state.update(phase="local_complete", local_verified=True)
            local_hash = hashlib.sha256((output / ("briefing_reader_" + day + ".html")).read_bytes()).hexdigest()
            state["html_sha256"] = local_hash
            receipt_path = news_root / "_publish" / ("oss_publish_receipt_" + day + ".json")
            try:
                receipt = load_json(receipt_path) if receipt_path.is_file() else {}
            except (OSError, ValueError):
                receipt = {}
            state["receipt_matches_local"] = receipt.get("html_sha256") == local_hash
            if online:
                from publish_daily_to_oss import inspect_public_release, load_config, PublishError
                try:
                    config = load_config(news_root.parent / "news_publish.local.json")
                    remote = inspect_public_release(config, day, local_hash)
                    state["remote_status"] = remote.get("status", "unknown")
                    if remote.get("status") == "verified":
                        state["phase"] = "remote_complete"
                except (OSError, ValueError, PublishError) as exc:
                    state["remote_status"] = "unavailable"
                    state["environment_fault"] = exc.__class__.__name__
            if state["phase"] != "remote_complete":
                state["phase"] = "remote_pending"
                if not shutil.which("ossutil"):
                    state["environment_fault"] = "ossutil_unavailable"
                state["next_action"] = "Check the public page online; if delivery is needed, run publisher doctor in an authorized environment."
            return state
        state["local_manifest_failures"] = check.get("failures", [])[:8]
    stages = sorted((path for path in stage_root.iterdir() if path.is_dir()),
                    key=lambda path: path.stat().st_mtime, reverse=True) if stage_root.exists() else []
    if stages:
        reviewed = None
        pending = None
        invalid = None
        for stage in stages:
            structure = verify_artifacts(stage, strict=True, structure_only=True)
            strict = verify_artifacts(stage, strict=True) if structure["status"] == "pass" else structure
            choice = (stage, strict)
            if strict["status"] == "pass":
                manifest_data = strict["manifest"]
                index_path = news_root / "_index" / "story_index.jsonl"
                current_hash = sha256_file(index_path) if index_path.is_file() else None
                if current_hash == manifest_data.get("index_snapshot_sha256"):
                    reviewed = choice
                    break
                strict = {"status": "fail", "failures": ["story index changed since ranking"]}
                choice = (stage, strict)
            if structure["status"] == "pass" and pending is None:
                pending = choice
            elif invalid is None:
                invalid = choice
        stage, result = reviewed or pending or invalid
        state["stage"] = str(stage)
        state["phase"] = ("ready_to_finalize" if reviewed else
                          "review_pending" if pending else "staging_invalid")
        state["failures"] = result.get("failures", [])[:8]
        state["next_action"] = ("Strict review passed; finalize is eligible, but this inspector will not publish."
                                if state["phase"] == "ready_to_finalize" else
                                "Repair or complete the cited staged evidence; semantic approval is never automatic.")
        return state
    candidate = collection / ("candidate_" + day + ".json")
    if candidate.is_file():
        try:
            raw = load_json(candidate)
            items = [item for section in raw.get("sections", []) for item in section.get("items", [])]
        except (OSError, ValueError, TypeError):
            items = []
        from source_capture import capture_path
        coverage_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        missing = []
        for item in items:
            try:
                if not capture_path(news_root, coverage_day, str(item.get("id"))).is_file():
                    missing.append(str(item.get("id")))
            except (TypeError, ValueError):
                missing.append("invalid_item_identity")
        state.update(phase="candidate_waiting_capture" if missing else "candidate_ready",
                     candidate=str(candidate), missing_capture_ids=missing)
        state["next_action"] = ("Capture and audit each source before staging." if missing else
                                "Run the v3 pipeline with explicit --date; review remains a separate gate.")
        return state
    coverage_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    academic = collection / ("academic_search_v4_" + coverage_day + ".json")
    social = collection / ("aihot_candidates_v3_" + day + ".json")
    if academic.is_file() or social.is_file():
        state.update(phase="collection_partial", collection={"academic": str(academic) if academic.is_file() else None,
                                                              "social": str(social) if social.is_file() else None})
        if academic.is_file() and social.is_file():
            try:
                ledger = load_json(academic)
                pool = load_json(social)
                gate = ledger.get("family_gate") or {}
                if ledger.get("academic_search_version") == 4 and gate.get("status") == "pass":
                    state["phase"] = "collection_ready"
                    state["source_fault_table"] = ledger.get("source_health_markdown", "")
                    state["candidate_counts"] = {"academic": sum(int(row.get("candidate_count") or 0)
                                                                  for row in ledger.get("rows", []) if isinstance(row, dict)),
                                                 "social": len(pool.get("items", []))}
            except (OSError, ValueError, TypeError):
                state["phase"] = "collection_invalid"
        state["next_action"] = ("Build the bounded authoring packet and audit article-level evidence."
                                if state["phase"] == "collection_ready" else
                                "Resume only the missing or invalid collection stage.")
        return state
    state.update(phase="collection_pending", next_action="Complete dated source discovery and candidate review.")
    return state


def with_network_preflight(state: dict[str, Any]) -> dict[str, Any]:
    """Check transport before collection, without rewriting source evidence."""
    if state["phase"] not in {"collection_pending", "candidate_waiting_capture"}:
        return state
    result = inspect_network()
    state["network_preflight"] = result
    if result["status"] != "ready":
        state["phase"] = result["status"]
        state["next_action"] = (
            "Repair or authorize this scheduled task's effective network path, then rerun "
            "the preflight. Do not classify individual sources as unavailable from this result."
        )
    return state


def _record(state: dict[str, Any], enabled: bool) -> None:
    if not enabled:
        return
    path = NEWS_ROOT / "_automation" / ("orchestration_state_" + state["date"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    state["observed_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _collect(day: str) -> dict[str, Any]:
    preflight = with_network_preflight(inspect(day))
    if preflight.get("network_preflight", {}).get("status") != "ready":
        return preflight
    coverage_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    collection = NEWS_ROOT / "_collection" / day
    collection.mkdir(parents=True, exist_ok=True)
    academic = collection / ("academic_search_v4_" + coverage_day + ".json")
    social = collection / ("aihot_candidates_v3_" + day + ".json")
    commands = [
        [sys.executable, "-B", str(SCRIPT_DIR / "academic_venue_sweep.py"),
         "--term", "quantum;machine learning", "--date-range", coverage_day,
         "--format", "json", "--fetch", "--output", str(academic)],
        [sys.executable, "-B", str(SCRIPT_DIR / "aihot_candidates.py"),
         "--source", "api", "--mode", "selected", "--take", "50", "--date", day,
         "--coverage-date", coverage_day, "--output", str(social)],
    ]
    failures: list[dict[str, Any]] = []
    for command in commands:
        try:
            completed = subprocess.run(command, cwd=NEWS_ROOT.parent, capture_output=True, text=True,
                                       encoding="utf-8", errors="replace", timeout=240, check=False)
        except subprocess.TimeoutExpired:
            failures.append({"stage": Path(command[2]).stem, "reason": "overall_timeout"})
            continue
        if completed.returncode:
            failures.append({"stage": Path(command[2]).stem, "reason": "command_failed",
                             "detail": completed.stderr.strip()[-500:]})
    state = inspect(day)
    if state.get("phase") == "collection_ready":
        ledger = load_json(academic)
        pool = load_json(social)
        academic_items = []
        for row in ledger.get("rows", []):
            if not isinstance(row, dict):
                continue
            for item in row.get("matches", [])[:20]:
                if isinstance(item, dict):
                    academic_items.append({"source_id": row.get("source_id"),
                                           "title": item.get("title"), "doi": item.get("doi"),
                                           "url": item.get("url"), "published_at": item.get("published_at")})
        packet = {"version": 1, "release_date": day, "coverage_date": coverage_day,
                  "semantic_review_status": "not_reviewed",
                  "family_gate": ledger.get("family_gate"),
                  "source_health": ledger.get("source_health", []),
                  "academic_candidates": academic_items[:100],
                  "social_candidates": (pool.get("items") or [])[:100]}
        packet_path = collection / ("authoring_packet_v4_" + day + ".json")
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        state["authoring_packet"] = str(packet_path)
    if failures:
        state["collection_failures"] = failures
    return state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    values = list(sys.argv[1:] if argv is None else argv)
    # Compatibility for the pre-v4 scheduled prompt; new automation uses subcommands.
    if values and values[0].startswith("--"):
        values.insert(0, "status")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "preflight", "collect", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--date", required=True)
        command.add_argument("--record", action="store_true")
        if name == "status":
            command.add_argument("--online", action="store_true")
            command.add_argument("--preflight-network", action="store_true")
    return parser.parse_args(values)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "collect":
        state = _collect(args.date)
    elif args.command == "resume":
        state = inspect(args.date)
        if state["phase"] in {"collection_pending", "collection_partial", "collection_invalid"}:
            state = _collect(args.date)
    else:
        state = inspect(args.date, online=getattr(args, "online", False))
        if args.command == "preflight" or getattr(args, "preflight_network", False):
            state = with_network_preflight(state)
    _record(state, args.record)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    checked_network = args.command in {"preflight", "collect", "resume"} or getattr(args, "preflight_network", False)
    return 2 if checked_network and state["phase"] in {
        "environment_blocked", "environment_unverified"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
