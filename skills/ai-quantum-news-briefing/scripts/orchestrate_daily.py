"""Artifact-derived daily orchestration checkpoint; never approves a semantic review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from daily_pipeline import NEWS_ROOT, atomic_copy, atomic_json, load_json, sha256_file, verify_artifacts
from audit_briefing_config import academic_search_venues
from daily_coverage_evidence import validate_ai_hot_window
from network_preflight import inspect_network
from release_lock import release_lock
from academic_sources import markdown_health_table, row_evidence_failures, sources_by_id, HEALTHY_RESULTS

SCRIPT_DIR = Path(__file__).resolve().parent
COLLECTION_PHASES = {"collection_pending", "collection_partial", "collection_invalid"}
PACKET_VERSION = 2
PACKET_LIMIT = 100


class CollectionError(ValueError):
    """A controlled diagnostic code; never echo source text or subprocess stderr."""
    def __init__(self, code: str, failures: list | None = None):
        super().__init__(code)
        self.failures = failures or []


def collection_paths(day: str, news_root: Path) -> dict[str, Path]:
    coverage_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    root = news_root / "_collection" / day
    return {"academic": root / f"academic_search_v4_{coverage_day}.json",
            "social": root / f"aihot_candidates_v3_{day}.json",
            "packet": root / f"authoring_packet_v4_{day}.json"}


def section_items(raw: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    sections = raw.get("sections")
    if not isinstance(sections, list):
        raise CollectionError("sections_missing_or_invalid")
    result = []
    for s, section in enumerate(sections):
        if not isinstance(section, dict) or not isinstance(section.get("items"), list):
            raise CollectionError("section_items_invalid")
        for i, item in enumerate(section["items"]):
            if not isinstance(item, dict):
                raise CollectionError("candidate_record_invalid")
            result.append((f"/sections/{s}/items/{i}", item))
    return result


def read_source(path: Path, kind: str, day: str) -> tuple[dict[str, Any], str]:
    body = path.read_bytes()
    raw = json.loads(body.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise CollectionError("source_object_invalid")
    covered = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    if kind == "academic":
        if raw.get("academic_search_version") != 4 or raw.get("date_range") != covered:
            raise CollectionError("academic_version_or_date_mismatch")
        rows = raw.get("rows")
        if not isinstance(rows, list) or not rows or not all(isinstance(row, dict) for row in rows):
            raise CollectionError("academic_rows_invalid")
        for row in rows:
            matches = row.get("matches", [])
            count = row.get("candidate_count", 0)
            if (not isinstance(matches, list) or not all(isinstance(item, dict) for item in matches)
                    or type(count) is not int or count < 0 or count != len(matches)):
                raise CollectionError("academic_candidates_inconsistent")
        if academic_search_venues({"academic_search": raw}, coverage_contract_version=3)[3]:
            declared = sources_by_id()
            raise CollectionError("academic_family_gate_invalid", [
                {"source_id": row.get("source_id") if row.get("source_id") in declared else "unregistered",
                 "codes": row_evidence_failures(row, covered)}
                for row in rows if row.get("result") in HEALTHY_RESULTS and row_evidence_failures(row, covered)])
    else:
        window = raw.get("ai_hot_window")
        if validate_ai_hot_window(window, covered):
            raise CollectionError("ai_hot_window_invalid")
        items = section_items(raw)
        if len(items) != window["inside_window_count"]:
            raise CollectionError("social_candidates_count_mismatch")
        start = datetime.fromisoformat(window["coverage_start"])
        end = datetime.fromisoformat(window["coverage_end"])
        for _, item in items:
            try:
                stamp = datetime.fromisoformat(str(item.get("published_at", "")).replace("Z", "+00:00"))
            except ValueError:
                raise CollectionError("social_candidate_timestamp_invalid") from None
            if stamp.tzinfo is None or not start <= stamp < end:
                raise CollectionError("social_candidate_outside_window")
    return raw, hashlib.sha256(body).hexdigest()


def source_snapshot(day: str, news_root: Path) -> dict[str, dict[str, Any]]:
    snapshot = {}
    for kind, path in collection_paths(day, news_root).items():
        if kind == "packet":
            continue
        try:
            raw, digest = read_source(path, kind, day)
            snapshot[kind] = {"status": "valid", "raw": raw, "sha256": digest}
        except FileNotFoundError:
            snapshot[kind] = {"status": "missing", "code": "source_missing"}
        except (OSError, ValueError, TypeError, AttributeError, OverflowError) as exc:
            snapshot[kind] = {"status": "invalid", "code": str(exc) if isinstance(exc, CollectionError)
                              else "source_" + exc.__class__.__name__}
            if isinstance(exc, CollectionError) and exc.failures:
                snapshot[kind]["evidence_failures"] = exc.failures
    return snapshot


def project_packet(day: str, news_root: Path, snapshot: dict[str, dict[str, Any]]) -> dict[str, Any]:
    paths = collection_paths(day, news_root)
    academic = snapshot["academic"]["raw"]
    social = snapshot["social"]["raw"]
    candidates: dict[str, list[dict[str, Any]]] = {"academic": [], "social": []}

    def append(kind: str, pointer: str, item: dict[str, Any], source_id: Any = None) -> None:
        if "_source_ref" in item or (source_id is not None and item.get("source_id", source_id) != source_id):
            raise CollectionError("projection_metadata_conflict")
        projected = deepcopy(item)
        projected["_source_ref"] = {"file": paths[kind].name, "json_pointer": pointer}
        if source_id is not None:
            projected["source_id"] = source_id
        candidates[kind].append(projected)

    for r, row in enumerate(academic["rows"]):
        for i, item in enumerate(row.get("matches", [])):
            append("academic", f"/rows/{r}/matches/{i}", item, row.get("source_id"))
    for pointer, item in section_items(social):
        append("social", pointer, item)
    return {"version": PACKET_VERSION, "release_date": day,
            "coverage_date": (date.fromisoformat(day) - timedelta(days=1)).isoformat(),
            "semantic_review_status": "not_reviewed", "candidate_policy": "Discovery only; source and semantic review remain required.",
            "family_gate": deepcopy(academic["family_gate"]),
            "source_health": deepcopy(academic.get("source_health", [])),
            "ai_hot_window": deepcopy(social["ai_hot_window"]),
            "source_inputs": {kind: {"file": paths[kind].name, "sha256": snapshot[kind]["sha256"]}
                              for kind in candidates},
            "candidate_counts": {kind: {"total": len(items), "emitted": min(len(items), PACKET_LIMIT),
                                        "truncated": max(0, len(items) - PACKET_LIMIT),
                                        "full_source": paths[kind].name} for kind, items in candidates.items()},
            "academic_candidates": candidates["academic"][:PACKET_LIMIT],
            "social_candidates": candidates["social"][:PACKET_LIMIT]}


def packet_status(path: Path, expected: dict[str, Any]) -> str:
    try:
        actual = load_json(path)
    except FileNotFoundError:
        return "missing"
    except (OSError, ValueError):
        return "invalid"
    version = actual.get("version")
    if type(version) is not int:
        return "invalid"
    if type(version) is int and version > PACKET_VERSION:
        return "incompatible"
    if version == 1:
        return "legacy"
    if version != PACKET_VERSION:
        return "invalid"
    if actual.get("source_inputs") != expected["source_inputs"]:
        return "stale"
    return "valid" if actual == expected else "invalid"


def inspect_collection(day: str, news_root: Path) -> dict[str, Any]:
    paths = collection_paths(day, news_root)
    snapshot = source_snapshot(day, news_root)
    state: dict[str, Any] = {"date": day, "remote_status": "not_checked", "action_required": True,
                             "packet_status": "not_checked", "source_status": {
                                 kind: {key: value for key, value in info.items() if key != "raw"}
                                 for kind, info in snapshot.items()},
                             "collection": {kind: str(paths[kind]) if info["status"] != "missing" else None
                                            for kind, info in snapshot.items()}}
    bad = {kind: info for kind, info in snapshot.items() if info["status"] != "valid"}
    try:
        version = load_json(paths["packet"]).get("version")
    except (OSError, ValueError):
        version = None
    if type(version) is int and version > PACKET_VERSION:
        state.update(phase="authoring_packet_incompatible", packet_status="incompatible",
                     failures=[{"stage": "packet", "code": "packet_incompatible"}],
                     next_action="Unknown packet version: preserve it and update the compatible reader.")
        return state
    if bad:
        state["phase"] = ("collection_invalid" if any(info["status"] == "invalid" for info in bad.values())
                          else "collection_pending" if len(bad) == 2 else "collection_partial")
        state["failures"] = [{"stage": kind, "code": info["code"]} for kind, info in bad.items()]
        state["next_action"] = "Resume only missing or invalid collectors; preserve valid cached evidence."
        return state
    try:
        expected = project_packet(day, news_root, snapshot)
    except CollectionError as exc:
        state.update(phase="collection_invalid", failures=[{"stage": "projection", "code": str(exc)}],
                     next_action="Repair projection metadata conflicts from source evidence.")
        return state
    status = packet_status(paths["packet"], expected)
    state.update(packet_status=status, authoring_packet=str(paths["packet"]),
                 source_fault_table=markdown_health_table(snapshot["academic"]["raw"]["rows"],
                    coverage_window=snapshot["academic"]["raw"]["date_range"]),
                 candidate_counts={kind: counts["total"] for kind, counts in expected["candidate_counts"].items()},
                 packet_counts=expected["candidate_counts"])
    state["phase"] = ("collection_ready" if status == "valid" else
                      "authoring_packet_incompatible" if status == "incompatible" else "authoring_packet_pending")
    state["failures"] = [] if status == "valid" else [{"stage": "packet", "code": "packet_" + status}]
    state["next_action"] = ("Expand discovery with evidence: a valid candidate pool is empty; no shortfall is approved."
                            if status == "valid" and not all(state["candidate_counts"].values()) else
                            "Author and audit article-level evidence and all four social source classes; nothing is reviewed."
                            if status == "valid" else "Unknown packet version: preserve it and update the compatible reader."
                            if status == "incompatible" else "Resume to rebuild the authoring packet from valid cached evidence without network.")
    return state


def deployment_identity(config: dict[str, Any]) -> str:
    # Public routing only; credentials/profile identity are not delivery evidence.
    return hashlib.sha256(json.dumps({key: config.get(key) for key in
        ("site_index_url", "bucket", "region", "object_prefix")}, sort_keys=True).encode()).hexdigest()


def _attempt_path(day: str, news_root: Path) -> Path:
    return news_root / "_automation" / ("remote_attempt_" + day + ".json")


def _begin_remote_attempt(day: str, news_root: Path, durable: bool) -> dict[str, Any]:
    attempt = {"started_at": datetime.now(timezone.utc).isoformat()}
    if durable:
        with release_lock(news_root):
            path = _attempt_path(day, news_root)
            previous = load_json(path) if path.exists() else {}
            sequence = previous.get("sequence", 0)
            if type(sequence) is not int or sequence < 0:
                raise CollectionError("remote_attempt_sequence_invalid")
            attempt["sequence"] = sequence + 1
            atomic_json(path, attempt)
    return attempt


def inspect(day: str, *, news_root: Path | None = None, online: bool = False,
            record_remote: bool = False) -> dict[str, Any]:
    news_root = NEWS_ROOT if news_root is None else news_root
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("release date must be ISO YYYY-MM-DD")
    output = news_root / day
    collection = news_root / "_collection" / day
    manifest = output / ("daily_pipeline_manifest_" + day + ".json")
    stage_root = output / ".staging"
    state: dict[str, Any] = {"date": day, "remote_status": "not_checked", "action_required": True,
                             "packet_status": "not_checked"}
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
            from publish_daily_to_oss import inspect_public_release, load_config, PublishError
            config = None
            try:
                config = load_config(news_root.parent / "news_publish.local.json")
                state["deployment_id"] = deployment_identity(config)
            except (OSError, ValueError, PublishError):
                state["deployment_id"] = None
            if online:
                attempt = _begin_remote_attempt(day, news_root, record_remote)
                try:
                    if config is None:
                        raise PublishError("routing unavailable")
                    remote = inspect_public_release(config, day, local_hash)
                    state["remote_status"] = remote.get("status", "unknown")
                    state["remote_verification"] = remote
                    if remote.get("status") == "verified" and state["receipt_matches_local"]:
                        state["phase"] = "remote_complete"
                        state["action_required"] = False
                except (OSError, ValueError, PublishError) as exc:
                    state["remote_status"] = "unavailable"
                    state["environment_fault"] = exc.__class__.__name__
                state["remote_attempt"] = {**attempt, "date": day, "html_sha256": local_hash,
                                           "deployment_id": state["deployment_id"],
                                           "status": state["remote_status"],
                                           "finished_at": datetime.now(timezone.utc).isoformat()}
            if state["phase"] != "remote_complete":
                state["phase"] = "remote_pending"
                if not shutil.which("ossutil"):
                    state["environment_fault"] = "ossutil_unavailable"
            state["next_action"] = ("No pending action; remote hash and homepage verified."
                                    if state["phase"] == "remote_complete" else
                                    "Remote content verified; reconcile the matching publishing receipt before completion."
                                    if state["remote_status"] == "verified" and not state["receipt_matches_local"] else
                                    "Check the public page online; if delivery is needed, run publisher doctor in an authorized environment.")
            return state
        state.update(phase="local_manifest_invalid", failures=check.get("failures", [])[:8],
                     next_action="Repair the existing release; collection recovery will not overwrite it.")
        return state
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
            config = load_json(candidate)
            items = [item for _, item in section_items(config)]
            if not items or any(not isinstance(item.get("id"), str) or not item["id"] for item in items):
                raise CollectionError("candidate_identity_missing_or_empty")
            if len({item["id"] for item in items}) != len(items):
                raise CollectionError("candidate_identity_duplicated")
        except (OSError, ValueError, TypeError):
            state.update(phase="candidate_invalid", candidate=str(candidate),
                         failures=[{"stage": "candidate", "code": "candidate_structure_invalid"}],
                         next_action="Repair the authored candidate configuration; it will not be overwritten automatically.")
            return state
        from source_capture import capture_path, validate_capture
        coverage_day = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
        missing = []
        for item in items:
            try:
                record = load_json(capture_path(news_root, coverage_day, str(item.get("id"))))
                if not isinstance(record, dict) or validate_capture(item, record):
                    missing.append(str(item.get("id")))
            except (OSError, TypeError, ValueError, AttributeError):
                missing.append(str(item.get("id")))
        state.update(phase="candidate_waiting_capture" if missing else "candidate_ready",
                     candidate=str(candidate), missing_capture_ids=missing)
        state["opening_story_status"] = ("present_not_reviewed" if config.get("opening_story")
                                         else "authoring_pending")
        state["next_action"] = ("Capture and audit each source before staging." if missing else
                                "Complete the opening story before staging; review remains a separate gate."
                                if state["opening_story_status"] == "authoring_pending" else
                                "Run the v4 pipeline with explicit --date; review remains a separate gate.")
        return state
    return inspect_collection(day, news_root)


def with_network_preflight(state: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    """Check transport before collection, without rewriting source evidence."""
    if not force and state["phase"] not in COLLECTION_PHASES | {"candidate_waiting_capture"}:
        state["network_preflight"] = {"status": "not_checked", "reason": "cached_stage_requires_no_network"}
        return state
    result = inspect_network()
    state["network_preflight"] = result
    if result["status"] != "ready":
        state["source_phase"] = state["phase"]
        state["phase"] = result["status"]
        state["action_required"] = True
        state["next_action"] = (
            "Repair or authorize this scheduled task's effective network path, then rerun "
            "the preflight. Do not classify individual sources as unavailable from this result."
        )
    return state


def _record(state: dict[str, Any], enabled: bool, *, news_root: Path | None = None) -> None:
    if not enabled:
        return
    news_root = NEWS_ROOT if news_root is None else news_root
    path = news_root / "_automation" / ("orchestration_state_" + state["date"] + ".json")
    with release_lock(news_root):
        try:
            previous = load_json(path)
        except FileNotFoundError:
            previous = {}
        # Corrupt state is not silently overwritten: it can hide a newer failure.
        incoming = state.get("remote_attempt")
        latest = previous.get("last_remote_attempt")
        reservation_path = _attempt_path(state["date"], news_root)
        reservation = load_json(reservation_path) if reservation_path.exists() else {}
        # API callers may explicitly persist a previously read-only observation.
        # Adopt it only when it started after every known attempt; otherwise a
        # late unreserved result could hide a newer negative or in-flight check.
        if incoming and "sequence" not in incoming:
            newest_start = max(reservation.get("started_at", ""),
                               latest.get("started_at", "") if latest else "")
            if incoming.get("started_at", "") > newest_start:
                incoming["sequence"] = reservation.get("sequence", 0) + 1
                reservation = {"sequence": incoming["sequence"], "started_at": incoming["started_at"]}
                atomic_json(reservation_path, reservation)
        superseded = bool(incoming and (
            incoming.get("sequence", 0) < reservation.get("sequence", 0)
            or latest and (incoming.get("sequence", 0), incoming.get("started_at", "")) <
                         (latest.get("sequence", 0), latest.get("started_at", ""))))
        # Re-inspect under the installation lock to avoid recording an obsolete phase.
        current = inspect(state["date"], news_root=news_root)
        if (state.get("html_sha256") and current.get("html_sha256") == state["html_sha256"]
                and current.get("deployment_id") == state.get("deployment_id")
                and "remote_status" in state and not superseded):
            current["remote_status"] = state["remote_status"]
            for key in ("remote_attempt", "remote_verification"):
                if key in state:
                    current[key] = state[key]
            if state["phase"] == "remote_complete":
                current.update(phase="remote_complete", action_required=False,
                               next_action="No pending action; remote hash and homepage verified.")
            elif current["remote_status"] == "verified" and not current.get("receipt_matches_local"):
                current["next_action"] = "Remote content verified; reconcile the matching publishing receipt before completion."
        if state["phase"] not in {"recovery_failed", "environment_blocked", "environment_unverified"}:
            for key in ("collection_failures", "collection_warnings", "collection_recovery", "network_preflight", "operation_failed"):
                if key in state:
                    current[key] = state[key]
            if state.get("operation_failed"):
                for key in ("failures", "next_action"):
                    if key in state:
                        current[key] = state[key]
            state.clear()
            state.update(current)
        if incoming and not superseded and state.get("remote_attempt") == incoming:
            latest = incoming
        if latest:
            state["last_remote_attempt"] = latest
        if latest and latest.get("status") == "verified" and state.get("phase") == "remote_complete":
            state["last_remote_verification"] = latest
        elif previous.get("last_remote_verification"):
            state["last_remote_verification"] = previous["last_remote_verification"]
        if superseded and state.get("local_verified"):
            state.update(phase="remote_pending", action_required=True, remote_status="superseded",
                         next_action="A newer remote check exists; reconcile its result before completion.")
        timestamp = previous.pop("observed_at", None)
        state.pop("observed_at", None)
        if previous == state and timestamp:
            state["observed_at"] = timestamp
            return
        state["observed_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(path, state)


def workflow_queue(day: str, *, record: bool = False) -> dict[str, Any]:
    """Explicit persistent date selection; status checkpoints never approve prose."""
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("release date must be ISO YYYY-MM-DD")
    path = NEWS_ROOT / "_automation" / "workflow_queue.json"
    with release_lock(NEWS_ROOT) if record else nullcontext():
        queue = load_json(path) if path.exists() else {"version": 1, "dates": []}
        if (queue.get("version") != 1 or not isinstance(queue.get("dates"), list)
                or any(not isinstance(value, str) or date.fromisoformat(value).isoformat() != value for value in queue["dates"])):
            raise ValueError("workflow queue invalid")
        dates = sorted(set(queue["dates"] + [day]))
        if record and queue["dates"] != dates:
            atomic_json(path, {"version": 1, "dates": dates})
    states = []
    for selected in dates:
        state = inspect(selected)
        try:
            previous = load_json(NEWS_ROOT / "_automation" / ("orchestration_state_" + selected + ".json"))
        except (OSError, ValueError):
            previous = {}
        proof = previous.get("last_remote_verification", {})
        latest = previous.get("last_remote_attempt", {})
        try:
            reservation_path = _attempt_path(selected, NEWS_ROOT)
            reservation = load_json(reservation_path) if reservation_path.exists() else {}
        except (OSError, ValueError):
            reservation = {"sequence": -1}
        proven = (state.get("local_verified") and state.get("receipt_matches_local")
                  and state.get("deployment_id") is not None
                  and proof == latest and latest.get("status") == "verified"
                  and latest.get("date") == selected
                  and latest.get("deployment_id") == state.get("deployment_id")
                  and latest.get("html_sha256") == state.get("html_sha256")
                  and latest.get("sequence", 0) == reservation.get("sequence", 0))
        if latest:
            state["last_remote_attempt"] = latest
        if proven:
            state.update(phase="completed_previously_verified", action_required=False,
                         next_action="No pending action; this local hash was previously verified remotely.")
        states.append(state)
    pending = [state for state in states if state.get("action_required")]
    return {"version": 1, "date": day, "phase": "workflow_pending" if pending else "workflow_complete",
            "action_required": bool(pending), "dates": states,
            "next_date": pending[0]["date"] if pending else None,
            "next_action": pending[0].get("next_action") if pending else "No pending selected date.",
            "final_response_allowed": not pending, "terminal_blocker": None}


def _repair_packet(day: str) -> dict[str, Any]:
    with release_lock(NEWS_ROOT):
        for _ in range(3):
            state = inspect(day)
            if state["phase"] != "authoring_packet_pending":
                return state
            snapshot = source_snapshot(day, NEWS_ROOT)
            if any(info["status"] != "valid" for info in snapshot.values()):
                return inspect(day)
            packet = project_packet(day, NEWS_ROOT, snapshot)
            paths = collection_paths(day, NEWS_ROOT)
            target = paths["packet"]
            if target.is_file():
                digest = sha256_file(target)
                backup = target.parent / ".packet_backups" / (target.stem + "." + digest + ".json")
                if not backup.exists():
                    atomic_copy(target, backup)
                elif sha256_file(backup) != digest:
                    raise CollectionError("packet_backup_digest_mismatch")
            # A non-cooperating writer may have changed evidence during backup.
            if any(sha256_file(paths[kind]) != info["sha256"] for kind, info in snapshot.items()):
                continue
            atomic_json(target, packet)
            result = inspect(day)
            if result["phase"] != "authoring_packet_pending":
                return result
        raise CollectionError("source_changed_during_projection")


def _collector_command(kind: str, day: str, target: Path) -> list[str]:
    covered = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    recovery = ["--budget-seconds", "200", "--checkpoint",
                str(collection_paths(day, NEWS_ROOT)[kind].parent / ".checkpoints" / (kind + ".json"))]
    if kind == "academic":
        return [sys.executable, "-B", str(SCRIPT_DIR / "academic_venue_sweep.py"),
                "--term", "quantum;machine learning", "--date-range", covered,
                "--format", "json", "--fetch"] + recovery + ["--output", str(target)]
    return [sys.executable, "-B", str(SCRIPT_DIR / "aihot_candidates.py"),
            "--source", "api", "--mode", "selected", "--take", "50", "--date", day,
            "--coverage-date", covered] + recovery + ["--output", str(target)]


def _collect(day: str) -> dict[str, Any]:
    state = inspect(day)
    if state["phase"] == "authoring_packet_pending":
        return _repair_packet(day)
    if state["phase"] not in COLLECTION_PHASES:
        return state
    if source_snapshot(day, NEWS_ROOT)["social"]["status"] != "valid":
        from aihot_candidates import api_scope, parse_args as hot_args
        from collection_checkpoint import load_checkpoint
        command = _collector_command("social", day, collection_paths(day, NEWS_ROOT)["social"])
        args = hot_args(command[3:])
        recovery = load_checkpoint(args.checkpoint, api_scope(args)).get("recovery", {})
        if recovery.get("action_required"):
            state.update(operation_failed=True, collection_recovery={"social": recovery},
                         failures=[{"stage": "social", "code": recovery.get("failure", "checkpoint_no_progress")}],
                         next_action="Pagination recovery reached its bound; diagnose transport/pool and archive the checkpoint before a deliberate fresh attempt.")
            return state
    state = with_network_preflight(state)
    if state.get("network_preflight", {}).get("status") != "ready":
        return state
    paths = collection_paths(day, NEWS_ROOT)
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    recoveries = {}
    for kind in ("academic", "social"):
        # Resume only the missing/invalid source, including after another process wins.
        if inspect(day)["phase"] not in COLLECTION_PHASES:
            break
        if source_snapshot(day, NEWS_ROOT)[kind]["status"] == "valid":
            continue
        paths[kind].parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".collect-", suffix=".json", dir=paths[kind].parent)
        os.close(fd)
        temporary = Path(name)
        try:
            interrupted = False
            try:
                command = _collector_command(kind, day, temporary)
                watchdog = 270
                if kind == "social":
                    from aihot_candidates import parse_args as hot_args, pagination_budget
                    watchdog = max(270, pagination_budget(hot_args(command[3:])) + 70)
                completed = subprocess.run(command, cwd=NEWS_ROOT.parent,
                                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                                           timeout=watchdog, check=False)
                interrupted = bool(completed.returncode)
            except subprocess.TimeoutExpired:
                interrupted = True
            if kind == "social":
                try:
                    window = load_json(temporary).get("ai_hot_window", {})
                    recoveries[kind] = window.get("recovery", {})
                except (OSError, ValueError, AttributeError):
                    pass
            # A killed academic worker can still have installed a valid atomic
            # aggregate of the completed families. Social pagination must finish.
            _, digest = read_source(temporary, kind, day)
            if interrupted:
                warnings.append({"stage": kind, "code": "interrupted_collector_valid_evidence_retained"})
            with release_lock(NEWS_ROOT):
                if inspect(day)["phase"] not in COLLECTION_PHASES:
                    continue
                if source_snapshot(day, NEWS_ROOT)[kind]["status"] == "valid":
                    continue
                if sha256_file(temporary) != digest:
                    raise CollectionError("collector_output_changed")
                atomic_copy(temporary, paths[kind])
        except subprocess.TimeoutExpired:
            failures.append({"stage": kind, "code": "collector_timeout"})
        except (OSError, ValueError, TypeError, AttributeError, TimeoutError, OverflowError) as exc:
            failures.append({"stage": kind, "code": str(exc) if isinstance(exc, CollectionError)
                             else "collector_" + exc.__class__.__name__})
        finally:
            temporary.unlink(missing_ok=True)
    state = inspect(day)
    if state["phase"] == "authoring_packet_pending":
        state = _repair_packet(day)
    if failures:
        state["collection_failures"] = failures
        state["operation_failed"] = True
    if warnings:
        state["collection_warnings"] = warnings
    if recoveries:
        state["collection_recovery"] = recoveries
    return state


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    values = list(sys.argv[1:] if argv is None else argv)
    # Compatibility for the pre-v4 scheduled prompt; new automation uses subcommands.
    if values and values[0].startswith("--"):
        values.insert(0, "status")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "preflight", "collect", "resume", "queue"):
        command = sub.add_parser(name)
        command.add_argument("--date", required=True)
        command.add_argument("--record", action="store_true")
        if name == "status":
            command.add_argument("--online", action="store_true")
            command.add_argument("--preflight-network", action="store_true")
    return parser.parse_args(values)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.command == "queue":
            state = workflow_queue(args.date, record=args.record)
        elif args.command in {"collect", "resume"}:
            state = _collect(args.date)
        else:
            state = inspect(args.date, online=getattr(args, "online", False), record_remote=args.record)
            if args.command == "preflight" or getattr(args, "preflight_network", False):
                state = with_network_preflight(state, force=True)
        if args.command != "queue":
            _record(state, args.record)
    except (OSError, ValueError, TypeError, AttributeError, TimeoutError, OverflowError) as exc:
        state = {"date": args.date, "phase": "recovery_failed", "packet_status": "not_checked",
                 "remote_status": "not_checked", "action_required": True, "operation_failed": True,
                 "failures": [{"stage": "orchestration", "code": str(exc) if isinstance(exc, CollectionError)
                               else exc.__class__.__name__}],
                 "next_action": "Repair this controlled failure and resume; existing artifacts remain authoritative."}
    print(json.dumps(state, ensure_ascii=False, indent=2))
    checked_network = args.command in {"preflight", "collect", "resume"} or getattr(args, "preflight_network", False)
    return 2 if state.get("operation_failed") or (getattr(args, "online", False) and state.get("phase") != "remote_complete") or (checked_network and state["phase"] in {
        "environment_blocked", "environment_unverified", "collection_invalid",
        "authoring_packet_incompatible", "candidate_invalid", "recovery_failed"}) else 0


if __name__ == "__main__":
    raise SystemExit(main())
