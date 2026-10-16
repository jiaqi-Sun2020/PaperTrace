"""Artifact-derived daily orchestration checkpoint; never approves a semantic review."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
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
from academic_sources import (family_gate, health_table, markdown_health_table,
                              row_evidence_failures, sources_by_id, HEALTHY_RESULTS)
from daily_delivery_policy import policy_snapshot
from daily_revisions import active_stages, candidate_path
import daily_execution_policy as execution_policy

SCRIPT_DIR = Path(__file__).resolve().parent
COLLECTION_PHASES = {"collection_pending", "collection_partial", "collection_invalid"}
PACKET_VERSION = 2
PACKET_LIMIT = 100
EXPANDABLE_PHASES = {"collection_ready", "expansion_pending", "expansion_ready", "late_arrival_pending",
                     "candidate_ready", "candidate_waiting_capture", "candidate_invalid", "candidate_authoring_pending"}


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


def read_source(path: Path, kind: str, day: str, *, coverage_window: str | None = None) -> tuple[dict[str, Any], str]:
    body = path.read_bytes()
    raw = json.loads(body.decode("utf-8-sig"))
    if not isinstance(raw, dict):
        raise CollectionError("source_object_invalid")
    covered = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    if coverage_window is not None:
        if kind != "academic":
            raise CollectionError("coverage_override_not_academic")
        covered = coverage_window
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
    # Historical packets retain their representation. New window-proof rows
    # derive display evidence from the admitted records, never a saved summary
    # that could upgrade an indexed empty query to publisher-wide completeness.
    has_window_proof = any("window_evidence" in row for row in academic["rows"])
    covered = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    query_contract = academic.get("source_coverage_version", 1) == 2
    packet_gate = family_gate(academic["rows"], coverage_window=covered, require_query=query_contract) if has_window_proof else deepcopy(academic["family_gate"])
    packet_health = health_table(academic["rows"], coverage_window=covered, require_query=query_contract) if has_window_proof else deepcopy(academic.get("source_health", []))
    return {"version": PACKET_VERSION, "release_date": day,
            **({"source_coverage_version": 2, "delivery_policy": policy_snapshot()} if query_contract else {}),
            "coverage_date": (date.fromisoformat(day) - timedelta(days=1)).isoformat(),
            "semantic_review_status": "not_reviewed", "candidate_policy": "Discovery only; source and semantic review remain required.",
            "family_gate": packet_gate,
            "source_health": packet_health,
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
                    coverage_window=snapshot["academic"]["raw"]["date_range"],
                    require_query=snapshot["academic"]["raw"].get("source_coverage_version", 1) == 2),
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
    if status == "valid" and snapshot["academic"]["raw"].get("source_coverage_version") == 2:
        policy = policy_snapshot()
        state["delivery_policy"] = policy
        limits = {"academic": policy["policy"]["academic"]["minimum_items"],
                  "social": max(policy["policy"]["social"]["minimum_items"],
                                policy["policy"]["social"]["minimum_new_or_material_update"])}
        state["expansion_reasons"] = [kind + "_pool_below_delivery_floor" for kind in limits
                                      if state["candidate_counts"][kind] < limits[kind]]
        if state["expansion_reasons"]:
            state.update(inspect_expansion(day, news_root))
        else:
            state.update(inspect_late_arrivals(day, news_root))
    return state


def late_arrival_paths(day: str, news_root: Path) -> tuple[Path, Path, str]:
    covered = date.fromisoformat(day) - timedelta(days=1)
    root = news_root / "_collection" / day / "late_arrivals"
    return root / "academic_recheck.json", root / "authoring_annex_v1.json", (covered-timedelta(days=2)).isoformat()+".."+covered.isoformat()


def project_late_arrivals(day: str, news_root: Path) -> dict[str, Any]:
    source, _, window = late_arrival_paths(day, news_root)
    raw, digest = read_source(source, "academic", day, coverage_window=window)
    if raw.get("source_coverage_version") != 2:
        raise CollectionError("late_arrival_query_contract_required")
    items=[]
    for r,row in enumerate(raw["rows"]):
        for i,item in enumerate(row.get("matches",[])):
            if "_source_ref" in item or item.get("source_id",row["source_id"]) != row["source_id"]:
                raise CollectionError("projection_metadata_conflict")
            value=deepcopy(item);value["source_id"]=row["source_id"]
            value["_source_ref"]={"file":source.relative_to(news_root).as_posix(),"json_pointer":f"/rows/{r}/matches/{i}"}
            items.append(value)
    return dict(version=1,release_date=day,query_window=window,semantic_review_status="not_reviewed",
                delivery_policy=policy_snapshot(),source_input=dict(file=source.relative_to(news_root).as_posix(),sha256=digest),
                candidate_counts=dict(total=len(items),emitted=min(len(items),PACKET_LIMIT),truncated=max(0,len(items)-PACKET_LIMIT)),
                academic_candidates=items[:PACKET_LIMIT],candidate_policy="Preserve original dates; identity/revision review required. Published releases remain frozen.")


def inspect_late_arrivals(day: str, news_root: Path) -> dict[str, Any]:
    _,target,_=late_arrival_paths(day,news_root)
    try:
        actual=load_json(target)
        if type(actual.get("version")) is int and actual["version"]>1:
            return dict(phase="late_arrival_incompatible",next_action="Preserve unknown late-arrival annex version.")
    except (OSError,ValueError):actual=None
    try:
        expected=project_late_arrivals(day,news_root)
        if actual==expected:
            return dict(late_arrival_packet=str(target),late_arrival_packet_status="valid")
    except (OSError,ValueError,TypeError,AttributeError,OverflowError):pass
    return dict(phase="late_arrival_pending",late_arrival_packet=str(target),action_required=True,
                next_action="Resume the bounded three-calendar-day index recheck; preserve dates and frozen published releases.")


def _recheck_late_arrivals(day: str) -> dict[str, Any]:
    state=inspect(day)
    if state["phase"] not in {"collection_ready","late_arrival_pending"}:return state
    source,target,window=late_arrival_paths(day,NEWS_ROOT)
    try:project_late_arrivals(day,NEWS_ROOT);valid=True
    except (OSError,ValueError,TypeError,AttributeError,OverflowError):valid=False
    started=_begin_collection_attempt(day)
    if not valid:
        state=with_network_preflight(state,force=True)
        if state.get("network_preflight",{}).get("status")!="ready":return _finish_collection_attempt(state,started)
        from academic_venue_sweep import build_plan_v4,fetch_evidence_v4
        plan=build_plan_v4(["quantum","machine learning"],window)
        plan["rows"]=[row for row in plan["rows"] if row["adapter"] in {"aps_harvest","crossref_dated","plos_search"}]
        raw=fetch_evidence_v4(plan,checkpoint=source.parent/".checkpoint.json")
        source.parent.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix=".recheck-",suffix=".json",dir=source.parent);os.close(fd)
        temporary=Path(name)
        try:
            atomic_json(temporary,raw);_,digest=read_source(temporary,"academic",day,coverage_window=window)
            with release_lock(NEWS_ROOT):
                if inspect(day)["phase"] not in {"collection_ready","late_arrival_pending"}:return inspect(day)
                if sha256_file(temporary)!=digest:raise CollectionError("collector_output_changed")
                _backup_source(source);atomic_copy(temporary,source)
        finally:temporary.unlink(missing_ok=True)
    with release_lock(NEWS_ROOT):
        if inspect(day)["phase"] not in {"collection_ready","late_arrival_pending"}:return inspect(day)
        annex=project_late_arrivals(day,NEWS_ROOT)
        if target.exists():
            old=load_json(target)
            if type(old.get("version")) is int and old["version"]>1:raise CollectionError("late_arrival_packet_incompatible")
            if old==annex:return inspect(day)
            _backup_source(target)
        if sha256_file(source)!=annex["source_input"]["sha256"]:raise CollectionError("source_changed_during_projection")
        atomic_json(target,annex)
    return _finish_collection_attempt(inspect(day),started)


def expansion_paths(day: str, news_root: Path) -> dict[str, Path]:
    covered = date.fromisoformat(day) - timedelta(days=1)
    root = news_root / "_collection" / day / "expansion"
    paths = {"academic": root / "academic_lookback.json", "packet": root / "expansion_packet_v1.json"}
    for offset in (2, 1):
        social_day = covered - timedelta(days=offset)
        paths["social_" + social_day.isoformat()] = root / ("social_" + social_day.isoformat() + ".json")
    return paths


def expansion_snapshot(day: str, news_root: Path) -> dict[str, Any]:
    covered = date.fromisoformat(day) - timedelta(days=1)
    window = (covered - timedelta(days=13)).isoformat() + ".." + covered.isoformat()
    result = {}
    for kind, path in expansion_paths(day, news_root).items():
        if kind == "packet":
            continue
        source_day = day if kind == "academic" else (date.fromisoformat(kind[7:]) + timedelta(days=1)).isoformat()
        if kind != "academic":
            cached = collection_paths(source_day, news_root)["social"]
            try:
                read_source(cached, "social", source_day)
                path = cached
            except (OSError, ValueError, TypeError, AttributeError, OverflowError):
                pass
        try:
            raw, digest = read_source(path, "academic" if kind == "academic" else "social", source_day,
                                      coverage_window=window if kind == "academic" else None)
            if kind == "academic" and raw.get("source_coverage_version") != 2:
                raise CollectionError("expansion_query_contract_required")
            result[kind] = dict(status="valid", raw=raw, sha256=digest, path=path)
        except (OSError, ValueError, TypeError, AttributeError, OverflowError) as exc:
            result[kind] = dict(status="missing" if isinstance(exc, FileNotFoundError) else "invalid", path=path,
                                code=str(exc) if isinstance(exc, CollectionError) else "expansion_" + exc.__class__.__name__)
    return result


def project_expansion(day: str, news_root: Path, snapshot: dict[str, Any]) -> dict[str, Any]:
    paths = collection_paths(day, news_root)
    base = source_snapshot(day, news_root)
    if any(info["status"] != "valid" for info in base.values()):
        raise CollectionError("expansion_daily_evidence_invalid")
    packet = project_packet(day, news_root, base)
    pools = {"academic": [], "social": []}
    for pointer, item in section_items(base["social"]["raw"]):
        projected = deepcopy(item)
        projected["_source_ref"] = dict(file=paths["social"].relative_to(news_root).as_posix(), json_pointer=pointer)
        pools["social"].append(projected)
    for kind, info in snapshot.items():
        source_file = info["path"].relative_to(news_root).as_posix()
        records = [(f"/rows/{r}/matches/{i}", item, row.get("source_id"))
                   for r, row in enumerate(info["raw"]["rows"]) for i, item in enumerate(row.get("matches", []))] if kind == "academic" else [
                       (pointer, item, None) for pointer, item in section_items(info["raw"])]
        for pointer, item, source_id in records:
            if "_source_ref" in item or (source_id is not None and item.get("source_id", source_id) != source_id):
                raise CollectionError("projection_metadata_conflict")
            projected = deepcopy(item)
            projected["_source_ref"] = dict(file=source_file, json_pointer=pointer)
            if source_id is not None:
                projected["source_id"] = source_id
            pools["academic" if kind == "academic" else "social"].append(projected)
    return dict(version=1, release_date=day, coverage_date=packet["coverage_date"],
                semantic_review_status="not_reviewed", shortfall_status="not_approved",
                delivery_policy=policy_snapshot(), daily_source_inputs=packet["source_inputs"],
                source_inputs={kind: dict(file=info["path"].relative_to(news_root).as_posix(), sha256=info["sha256"])
                               for kind, info in snapshot.items()},
                academic_window=snapshot["academic"]["raw"]["date_range"], social_hours=72,
                candidate_counts={kind: dict(total=len(items), emitted=min(len(items), PACKET_LIMIT),
                                            truncated=max(0, len(items)-PACKET_LIMIT), full_sources=["source_inputs", "daily_source_inputs"])
                                  for kind, items in pools.items()},
                academic_candidates=pools["academic"][:PACKET_LIMIT], social_candidates=pools["social"][:PACKET_LIMIT],
                next_action="Verify original articles and all four social classes; author and review. Expansion never approves shortfall.")


def inspect_expansion(day: str, news_root: Path) -> dict[str, Any]:
    snapshot = expansion_snapshot(day, news_root)
    target = expansion_paths(day, news_root)["packet"]
    result = dict(phase="expansion_pending", action_required=True, expansion_packet=str(target),
                  expansion_source_status={kind: {k: str(v) if isinstance(v, Path) else v for k, v in info.items() if k != "raw"}
                                           for kind, info in snapshot.items()},
                  next_action="Resume bounded 14-day academic and 72-hour AI HOT expansion; preserve daily evidence. No shortfall approved.")
    try:
        saved = load_json(target)
        if type(saved.get("version")) is int and saved["version"] > 1:
            return {**result, "phase": "expansion_incompatible", "next_action": "Preserve unknown expansion packet version."}
    except (OSError, ValueError):
        saved = None
    if all(info["status"] == "valid" for info in snapshot.values()):
        expected = project_expansion(day, news_root, snapshot)
        if saved == expected:
            result.update(phase="expansion_ready", expansion_packet_status="valid", expanded_candidate_counts=expected["candidate_counts"],
                          next_action=expected["next_action"])
        else:
            result["expansion_packet_status"] = "missing" if saved is None else "stale"
    return result


def _expand(day: str) -> dict[str, Any]:
    state = inspect(day)
    if state["phase"] not in EXPANDABLE_PHASES:
        return state
    if state["phase"] == "expansion_ready":
        return state
    expansion_state = inspect_expansion(day, NEWS_ROOT)
    if expansion_state["phase"] == "expansion_incompatible":
        return {**state, **expansion_state}
    snapshot = expansion_snapshot(day, NEWS_ROOT)
    started = _begin_collection_attempt(day)
    bad = {kind: info for kind, info in snapshot.items() if info["status"] != "valid"}
    if bad:
        state = with_network_preflight(state, force=True)
        if state.get("network_preflight", {}).get("status") != "ready":
            return _finish_collection_attempt(state, started)
    failures = []
    for kind in bad:
        path = expansion_paths(day, NEWS_ROOT)[kind]
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".expand-", suffix=".json", dir=path.parent)
        os.close(fd)
        temporary = Path(name)
        try:
            covered = date.fromisoformat(day) - timedelta(days=1)
            source_day = day if kind == "academic" else (date.fromisoformat(kind[7:]) + timedelta(days=1)).isoformat()
            window = (covered - timedelta(days=13)).isoformat() + ".." + covered.isoformat()
            command = _collector_command("academic" if kind == "academic" else "social", source_day, temporary)
            command[command.index("--checkpoint")+1] = str(path.parent / ".checkpoints" / (kind + ".json"))
            if kind == "academic":
                command[command.index("--date-range")+1] = window
            watchdog = 270
            if kind != "academic":
                from aihot_candidates import parse_args as hot_args, pagination_budget
                watchdog = max(watchdog, pagination_budget(hot_args(command[3:])) + 70)
            subprocess.run(command, cwd=NEWS_ROOT.parent, capture_output=True, timeout=watchdog, check=False)
            _, digest = read_source(temporary, "academic" if kind == "academic" else "social", source_day,
                                    coverage_window=window if kind == "academic" else None)
            with release_lock(NEWS_ROOT):
                if inspect(day)["phase"] not in EXPANDABLE_PHASES:
                    return inspect(day)
                if expansion_snapshot(day, NEWS_ROOT)[kind]["status"] != "valid":
                    if sha256_file(temporary) != digest:
                        raise CollectionError("collector_output_changed")
                    _backup_source(path)
                    atomic_copy(temporary, path)
        except (OSError, ValueError, TypeError, AttributeError, TimeoutError, subprocess.TimeoutExpired, OverflowError) as exc:
            failures.append({"stage": kind, "code": str(exc) if isinstance(exc, CollectionError) else "expansion_" + exc.__class__.__name__})
        finally:
            temporary.unlink(missing_ok=True)
    with release_lock(NEWS_ROOT):
        for _ in range(3):
            snapshot = expansion_snapshot(day, NEWS_ROOT)
            if not all(info["status"] == "valid" for info in snapshot.values()):
                break
            if inspect(day)["phase"] not in EXPANDABLE_PHASES:
                return inspect(day)
            packet = project_expansion(day, NEWS_ROOT, snapshot)
            base = source_snapshot(day, NEWS_ROOT)
            if packet["daily_source_inputs"] != {kind: dict(file=collection_paths(day, NEWS_ROOT)[kind].name, sha256=info["sha256"])
                                                  for kind, info in base.items() if info["status"] == "valid"}:
                continue
            if any(sha256_file(info["path"]) != info["sha256"] for info in snapshot.values()):
                continue
            target = expansion_paths(day, NEWS_ROOT)["packet"]
            if target.exists() and load_json(target) == packet:
                break
            if target.exists():
                old = load_json(target)
                if type(old.get("version")) is int and old["version"] > 1:
                    raise CollectionError("expansion_packet_incompatible")
                backup = target.parent / ".packet_backups" / (target.stem + "." + sha256_file(target) + ".json")
                if not backup.exists():
                    atomic_copy(target, backup)
                elif sha256_file(backup) != sha256_file(target):
                    raise CollectionError("packet_backup_digest_mismatch")
            if any(sha256_file(info["path"]) != info["sha256"] for info in snapshot.values()):
                continue
            daily_now = source_snapshot(day, NEWS_ROOT)
            if any(info["status"] != "valid" for info in daily_now.values()) or packet["daily_source_inputs"] != {
                    kind: dict(file=collection_paths(day, NEWS_ROOT)[kind].name, sha256=info["sha256"]) for kind, info in daily_now.items()}:
                continue
            atomic_json(target, packet)
            break
        else:
            raise CollectionError("source_changed_during_expansion")
    result = inspect(day)
    if result["phase"] in {"collection_ready", "expansion_pending", "expansion_ready"}:
        result.update(inspect_expansion(day, NEWS_ROOT))
    if failures:
        result.update(collection_failures=failures, operation_failed=True)
    return _finish_collection_attempt(result, started)


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
    stages = sorted((path for path in active_stages(news_root, day) if path.is_dir()),
                    key=lambda path: path.stat().st_mtime, reverse=True)
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
    candidate = candidate_path(news_root, day)
    if candidate.is_file():
        try:
            config = load_json(candidate)
            if config.get("authoring_status") == "in_progress":
                section_items(config)
                state.update(phase="candidate_authoring_pending", candidate=str(candidate),
                             semantic_review_status="not_reviewed", authoring_status="in_progress",
                             next_action="Continue authored draft, source evidence and Fable; mark authoring complete before capture/staging readiness.")
                return state
            if config.get("authoring_status") not in {None, "complete"}:
                raise CollectionError("candidate_authoring_status_invalid")
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
        if config.get("source_url_contract_version") == 2:
            from source_capture import admit_candidates
            from rank_briefing_candidates import rank_briefing_config, SOURCE_ALGORITHM_VERSION
            from daily_delivery_policy import resolve_delivery_defaults
            from news_delta import load_index
            from audit_briefing_config import audit_academic_delivery, audit_social_delivery, audit_ranking_delivery
            from delivery_expansion import validate_policy
            try:
                admitted = admit_candidates(config, coverage_day, news_root=news_root)
                state["candidate_admission"] = admitted["candidate_admission"]
                admitted = resolve_delivery_defaults(admitted)
                admitted["ranking_policy"] = {**(admitted.get("ranking_policy") or {}),
                                               "enabled": True, "algorithm_version": SOURCE_ALGORITHM_VERSION}
                ranked = rank_briefing_config(admitted, load_index(news_root / "_index" / "story_index.jsonl"),
                                               date.fromisoformat(day), 30)
                selected = [item for _, item in section_items(ranked)]
                pool_failures = (audit_academic_delivery(ranked) + audit_social_delivery(ranked)
                                 + audit_ranking_delivery(ranked) + validate_policy(ranked))
                if pool_failures:
                    state["candidate_pool_failures"] = pool_failures
                    state["phase"] = "candidate_waiting_capture"
                if not pool_failures and selected and all(not validate_capture(item, item.get("source_capture") or {}) for item in selected):
                    state.update(phase="candidate_ready", selected_capture_ids=[item["id"] for item in selected])
            except (OSError, ValueError, TypeError, AttributeError):
                state["phase"] = "candidate_waiting_capture"
        state["opening_story_status"] = ("present_not_reviewed" if config.get("opening_story")
                                         else "authoring_pending")
        state["next_action"] = ("Expand or repair the candidate pool and capture viable sources; inspect candidate_pool_failures and admission diagnostics. Quotas remain unchanged." if state["phase"] == "candidate_waiting_capture" else
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
        collection_incoming = state.get("collection_attempt")
        collection_latest = previous.get("last_collection_attempt")
        for attempt in (collection_incoming, collection_latest):
            if attempt is not None:
                try:
                    for key in ("started_at", "observed_at"):
                        stamp = datetime.fromisoformat(attempt[key])
                        if stamp.tzinfo is None:
                            raise ValueError("naive attempt time")
                except (KeyError, TypeError, ValueError):
                    raise CollectionError("collection_attempt_invalid") from None
        def collection_order(attempt):
            sequence = attempt.get("sequence", 0)
            if type(sequence) is not int or sequence < 0:
                raise CollectionError("collection_attempt_sequence_invalid")
            return (sequence, datetime.fromisoformat(attempt["started_at"]), datetime.fromisoformat(attempt["observed_at"]))
        collection_superseded = bool(collection_incoming and collection_latest and
                                     collection_order(collection_incoming) < collection_order(collection_latest))
        if collection_incoming and not collection_superseded:
            collection_latest = deepcopy(collection_incoming)
        if collection_incoming:
            attempt_id = hashlib.sha256(json.dumps(collection_incoming, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            history = news_root / "_automation" / "collection_attempts" / state["date"] / (attempt_id + ".json")
            if not history.exists():
                atomic_json(history, collection_incoming)
            elif load_json(history) != collection_incoming:
                raise CollectionError("attempt_history_digest_mismatch")
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
        if (state["phase"] not in {"recovery_failed", "environment_blocked", "environment_unverified"}
                or collection_superseded):
            if not collection_superseded:
                for key in ("collection_failures", "collection_warnings", "collection_recovery",
                            "collection_diagnostics", "collection_attempt", "network_preflight", "operation_failed"):
                    if key in state:
                        current[key] = state[key]
                if state.get("operation_failed"):
                    for key in ("failures", "next_action"):
                        if key in state:
                            current[key] = state[key]
            state.clear()
            state.update(current)
        if collection_latest:
            state["last_collection_attempt"] = collection_latest
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


def workflow_queue(day: str, *, record: bool = False, withdraw_reason: str | None = None) -> dict[str, Any]:
    """Retain selection history; only the explicit release date is executable."""
    execution_policy.release_date(day)
    if withdraw_reason is not None and (not record or not isinstance(withdraw_reason,str) or not withdraw_reason.strip()):
        raise ValueError("withdrawal requires --record and a concrete reason")
    path=NEWS_ROOT/'_automation/workflow_queue.json'
    with release_lock(NEWS_ROOT) if record else nullcontext():
        queue=load_json(path) if path.exists() else {'version':1,'dates':[]}
        if (not isinstance(queue,dict) or type(queue.get('version')) is not int or queue['version']!=1
                or not isinstance(queue.get('dates'),list)):
            raise ValueError('workflow_queue_invalid')
        for selected in queue['dates']:execution_policy.release_date(selected)
        withdrawals=queue.get('withdrawals',{})
        if not isinstance(withdrawals,dict):raise ValueError('workflow_queue_withdrawal_invalid')
        for selected,value in withdrawals.items():
            execution_policy.release_date(selected)
            if (selected not in queue['dates'] or not isinstance(value,dict) or not isinstance(value.get('reason'),str)
                    or not value['reason'].strip() or not value.get('recorded_at')):
                raise ValueError('workflow_queue_withdrawal_invalid')
        history=queue.get('history_policy')
        cutoff=execution_policy.AUTOMATIC_RELEASE_NOT_BEFORE
        if history is not None:
            if (not isinstance(history,dict) or type(history.get('version')) is not int or history['version']!=1
                    or history.get('timezone')!='Asia/Shanghai' or not history.get('recorded_at')
                    or not isinstance(history.get('reason'),str) or not history['reason'].strip()):
                raise ValueError('workflow_history_policy_invalid')
            execution_policy.release_date(history.get('not_before'))
            cutoff=max(cutoff,history['not_before'])
        dates=sorted(set(queue['dates']+[day]))
        changed=queue['dates']!=dates
        if withdraw_reason is not None:
            reason=withdraw_reason.strip()
            if day in withdrawals and withdrawals[day]['reason']!=reason:
                raise ValueError('withdrawal reason conflict; preserved existing decision')
            if day not in withdrawals:
                withdrawals=dict(withdrawals)
                withdrawals[day]={'reason':reason,'recorded_at':datetime.now(timezone.utc).isoformat(),
                    'prior_queue_sha256':sha256_file(path) if path.is_file() else None}
                changed=True
        if history is None or history['not_before']!=cutoff:
            history={'version':1,'not_before':cutoff,'timezone':'Asia/Shanghai',
                'reason':'User retired automatic backfill before '+cutoff+'; preserve all original outcomes and artifacts.',
                'recorded_at':datetime.now(timezone.utc).isoformat(),
                'prior_queue_sha256':sha256_file(path) if path.is_file() else None}
            changed=True
        if record and changed:
            updated=dict(queue);updated.update(dates=dates,history_policy=history)
            if withdrawals:updated['withdrawals']=withdrawals
            atomic_json(path,updated)
    states=[]
    for selected in dates:
        if selected in withdrawals:
            states.append({'date':selected,'phase':'withdrawn','action_required':False,'withdrawal':withdrawals[selected],
                'next_action':'User cancelled this date; retain all artifacts and prior publication outcomes.'})
            continue
        if execution_policy.retired(selected,not_before=cutoff):
            states.append({**execution_policy.retired_state(selected),'publication_outcome':'preserved_not_reclassified'})
            continue
        if selected!=day:
            states.append({'date':selected,'phase':'deferred_date','action_required':False,
                'next_action':'Independent date; resume only with its explicit date, never as a dependency of this invocation.'})
            continue
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
        if state.get('action_required') and state.get('phase') not in {
                'remote_pending','local_manifest_invalid','ready_to_finalize','review_pending','staging_invalid'}:
            state['next_action']='Resume only '+day+' through daily --date '+day+' --action status; use the new source pool and controlled authoring.'
        states.append(state)
    current=next(state for state in states if state['date']==day)
    pending=bool(current.get('action_required'))
    excluded=current['phase'] in {'historical_retired','withdrawn'}
    return {'version':1,**execution_policy.execution_window(day),'automatic_release_not_before':cutoff,
            'phase':'workflow_retired' if excluded else 'workflow_pending' if pending else 'workflow_complete',
            'run_outcome':'not_scheduled' if excluded else 'pending' if pending else 'completed',
            'action_required':pending,'dates':states,'retired_dates':[value for value in dates if value<cutoff],
            'deferred_dates':[value for value in dates if value>=cutoff and value!=day and value not in withdrawals],
            'next_date':day if pending else None,'execution_order':[day] if pending else [],
            'next_action':current.get('next_action','No pending action for the requested date.'),
            'final_response_allowed':not pending,'terminal_blocker':None}


def _execution_blocked(day, stage, exc, *, scope='shared'):
    code=str(exc) if isinstance(exc,CollectionError) else exc.__class__.__name__
    return {**execution_policy.execution_window(day),'phase':'execution_blocked','run_outcome':'blocked',
            'action_required':True,'publication_approved':False,'operation_failed':True,
            'execution_order':[day],'next_date':day,'final_response_allowed':True,
            'terminal_blocker':{'stage':stage,'scope':scope,'code':code},
            'next_action':'Repair the cited '+scope+' '+stage+' failure, preserve evidence, then resume this same explicit date.'}


def daily_execution(day: str, *, action='status', record=False, max_tasks=4):
    """One pinned edition; new acquisition only, existing release authority."""
    execution_policy.release_date(day)
    if action not in {'status','plan','work','packet'}:raise ValueError('daily_action_invalid')
    try:
        queue=workflow_queue(day,record=record)
    except (OSError,ValueError,TypeError,AttributeError,TimeoutError) as exc:
        return _execution_blocked(day,'workflow_queue',exc)
    result={**queue,'daily_execution_version':1,'publication_approved':False}
    if queue['run_outcome'] in {'completed','not_scheduled'}:
        return result
    edition=next(state for state in queue['dates'] if state['date']==day)
    result['edition_state']=edition
    command=[sys.executable,'-B',str(SCRIPT_DIR/'orchestrate_daily.py')]
    if edition.get('environment_fault'):
        return {**result,**_execution_blocked(day,'release_environment',CollectionError(str(edition['environment_fault'])))}
    # Never collect again for a frozen or locally completed edition.
    if edition['phase'] in {'remote_pending','local_manifest_invalid','ready_to_finalize','review_pending','staging_invalid'}:
        result['phase']=edition['phase']
        result['next_commands']=([{'cwd':str(NEWS_ROOT.parent),'argv':command+['status','--date',day,'--online','--record']}]
                                 if edition['phase']=='remote_pending' else [])
        return result
    from source_preparation import orchestrate_sources
    try:
        acquisition=orchestrate_sources(day,NEWS_ROOT/'_sources',action=action,max_tasks=max_tasks)
    except (OSError,ValueError,TypeError,KeyError,sqlite3.Error,TimeoutError) as exc:
        return {**result,**_execution_blocked(day,'source_pool',exc)}
    source=acquisition.get('source_preparation',acquisition)
    result['source_preparation']=acquisition
    ready=source.get('status')=='coverage_ready'
    result['phase']='authoring_pending' if ready else 'source_and_authoring_pending'
    result['next_action']=('Author admitted materials, bind the candidate, then use existing controlled staging/review/strict release.'
                           if ready else 'Continue only this date: reuse validated cache, execute missing source tasks and actual discovery; author independently available materials.')
    next_action='plan' if source.get('status')=='not_initialized' else 'packet' if ready else 'work'
    if any(row.get('state')=='not_registered' for row in source.get('missing_tasks',[])):
        next_action='plan'
    result['next_commands']=[{'cwd':str(NEWS_ROOT.parent),'argv':command+['daily','--date',day,'--action',next_action,'--record']}]
    missing=source.get('missing_tasks',[])
    discovery=[row for row in missing if row.get('kind')=='discovery' and row.get('state') in {'pending','retry_wait'}]
    core_ready=(source.get('academic',{}).get('family_gate',{}).get('status')=='pass' and source.get('aihot') is not None)
    if not ready and core_ready and discovery:
        task=discovery[0]
        result['next_action']='Complete the current dated discovery observation through the permitted browser; author admitted materials independently. Do not loop ordinary source work.'
        result['next_commands']=[{'cwd':str(NEWS_ROOT.parent),'argv':[sys.executable,'-B',str(SCRIPT_DIR/'source_preparation.py'),
                    'claim-discovery','--date',day,'--pool-dir',str(NEWS_ROOT/'_sources'),'--task-id',task['task_id']]}]
        if task.get('retry_at') and task['retry_at']>datetime.now(timezone.utc).timestamp():
            result['next_commands']=[];result['retry_at']=task['retry_at']
            result['next_action']='Discovery Retry-After has not elapsed; retain this date and resume only when eligible.'
    recoverable=[row for row in missing if row.get('state') in {'pending','retry_wait','running','not_registered'}]
    if not ready and missing and not recoverable:
        result.update(phase='source_blocked',run_outcome='blocked',final_response_allowed=True,operation_failed=True,
            terminal_blocker={'stage':'required_source_coverage','scope':'current_date','tasks':missing},next_commands=[])
        result['next_action']='No recoverable current-date source task remains; diagnose the cited coverage failures without retry loops or lowering standards.'
    result['stop_conditions']=['requested date complete or retired','specific external or shared blocker recorded; never a different date pending']
    result['semantic_review_status']='not_reviewed'
    if acquisition.get('work'):
        failures=[row for row in acquisition['work']['processed'] if row['state']!='succeeded']
        result['task_failures']=failures
        result['operation_failed']=bool(failures) and not ready
    blocked=[row for row in source.get('missing_tasks',[]) if row.get('kind')=='discovery' and row.get('state') in {'blocked','exhausted'}]
    if blocked:
        result.update(phase='source_blocked',run_outcome='blocked',final_response_allowed=True,
                      operation_failed=True,terminal_blocker={'stage':'discovery','scope':'current_date','tasks':blocked})
    return result


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


def _backup_source(target: Path) -> None:
    if not target.exists():
        return
    digest = sha256_file(target)
    backup = target.parent / ".source_backups" / (target.stem + "." + digest + ".json")
    if not backup.exists():
        atomic_copy(target, backup)
    elif sha256_file(backup) != digest:
        raise CollectionError("source_backup_digest_mismatch")


def _academic_collection_diagnostics(path: Path, day: str) -> dict[str, Any]:
    """Retain bounded diagnostics before temporary evidence is removed, never approval."""
    covered = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    diagnostic: dict[str, Any] = {"diagnostic_only": True, "coverage_window": covered}
    try:
        from collection_checkpoint import MAX_CHECKPOINT_BYTES
        if path.stat().st_size > MAX_CHECKPOINT_BYTES:
            return {**diagnostic, "status": "unreadable", "code": "diagnostic_output_too_large"}
        body = path.read_bytes()
        diagnostic["output_sha256"] = hashlib.sha256(body).hexdigest()
        raw = json.loads(body.decode("utf-8-sig"))
        if not isinstance(raw, dict) or not isinstance(raw.get("rows"), list):
            return {**diagnostic, "status": "unreadable", "code": "diagnostic_rows_invalid"}
        rows = [row for row in raw["rows"] if isinstance(row, dict)]
        strict = raw.get("source_coverage_version", 1) == 2
        gate = family_gate(rows, coverage_window=covered, require_query=strict)
        table = health_table(rows, coverage_window=covered, require_query=strict)
        # Diagnostics contain controlled metadata only: never article bodies,
        # arbitrary error messages, URLs, or subprocess stdout/stderr.
        window_keys = {"observed_earliest_date", "observed_latest_date", "requested_start",
                       "requested_end", "classification_basis", "pagination_complete", "source_scope"}

        def fields(value, keys):
            if not isinstance(value, dict):
                return {}
            return {key: item[:300] if isinstance(item, str) else item
                    for key, item in value.items() if key in keys
                    and (item is None or type(item) in {str, int, float, bool})}

        health = []
        for row, item in zip(rows, table):
            detail = fields(item, {"source_id", "tier", "family", "status", "coverage_window",
                                   "candidate_count", "quarantined_count", "impact", "next_action"})
            detail["evidence_failures"] = item["evidence_failures"]
            detail.update(fields(row, {"retrieval_status", "parse_status", "window_status", "coverage_claim"}))
            detail["http_evidence"] = fields(row.get("evidence"), {"status_code", "retrieved_at", "response_hash"})
            detail["window_evidence"] = fields(row.get("window_evidence"), window_keys)
            evidence = row.get("evidence")
            if isinstance(evidence, dict):
                for old, new in (("oldest_item_date", "observed_earliest_date"),
                                 ("newest_item_date", "observed_latest_date")):
                    if isinstance(evidence.get(old), str):
                        detail["window_evidence"].setdefault(new, evidence[old][:300])
            health.append(detail)
        diagnostic.update(status="available", family_gate=gate, missing_families=gate["missing_families"],
                          source_health=health, collection_complete=raw.get("collection_complete") is True)
    except (OSError, ValueError, TypeError, AttributeError, KeyError, OverflowError) as exc:
        diagnostic.update(status="unreadable", code="diagnostic_" + exc.__class__.__name__)
    return diagnostic


def _finish_collection_attempt(state: dict[str, Any], started_at: str) -> dict[str, Any]:
    """Keep the latest real attempt separately from a later artifact-only status."""
    attempt = {"started_at": started_at, "observed_at": datetime.now(timezone.utc).isoformat(),
               "runtime": {"python": sys.version.split()[0], "entrypoint": str(Path(__file__).resolve()),
                           "code_sha256": {path.name: sha256_file(path) for path in
                                           [Path(__file__), SCRIPT_DIR / "academic_sources.py", SCRIPT_DIR / "academic_venue_sweep.py",
                                            SCRIPT_DIR / "dated_source.py", SCRIPT_DIR / "daily_delivery_policy.py"]},
                           "policy_sha256": policy_snapshot()["sha256"]}}
    identity = hashlib.sha256(started_at.encode("ascii")).hexdigest()
    started_path = NEWS_ROOT / "_automation" / "collection_attempts" / state["date"] / (identity + ".started.json")
    if started_path.exists():
        reservation = load_json(started_path)
        attempt.update(attempt_id=identity, sequence=reservation["sequence"])
    for key in ("phase", "network_preflight", "collection_diagnostics", "collection_failures",
                "collection_warnings", "collection_recovery", "operation_failed", "failures", "next_action"):
        if key in state:
            attempt[key] = deepcopy(state[key])
    state["collection_attempt"] = attempt
    return state


def _begin_collection_attempt(day: str) -> str:
    started = datetime.now(timezone.utc).isoformat()
    identity = hashlib.sha256(started.encode("ascii")).hexdigest()
    path = NEWS_ROOT / "_automation" / "collection_attempts" / day / (identity + ".started.json")
    with release_lock(NEWS_ROOT):
        counter = NEWS_ROOT / "_automation" / ("collection_reservation_" + day + ".json")
        previous = load_json(counter).get("sequence", 0) if counter.exists() else 0
        if type(previous) is not int or previous < 0:
            raise CollectionError("collection_attempt_sequence_invalid")
        sequence = previous + 1
        atomic_json(counter, {"date": day, "started_at": started, "sequence": sequence})
        atomic_json(path, {"date": day, "started_at": started, "status": "started", "sequence": sequence,
                          "policy_sha256": policy_snapshot()["sha256"], "entrypoint_sha256": sha256_file(Path(__file__))})
    return started


def _collect(day: str) -> dict[str, Any]:
    state = inspect(day)
    if state["phase"] == "authoring_packet_pending":
        return _repair_packet(day)
    if state["phase"] not in COLLECTION_PHASES:
        return state
    started_at = _begin_collection_attempt(day)
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
            return _finish_collection_attempt(state, started_at)
    state = with_network_preflight(state)
    if state.get("network_preflight", {}).get("status") != "ready":
        return _finish_collection_attempt(state, started_at)
    preflight = deepcopy(state["network_preflight"])
    paths = collection_paths(day, NEWS_ROOT)
    failures: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    recoveries = {}
    diagnostics = {}
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
                _backup_source(paths[kind])
                atomic_copy(temporary, paths[kind])
        except subprocess.TimeoutExpired:
            failures.append({"stage": kind, "code": "collector_timeout"})
        except (OSError, ValueError, TypeError, AttributeError, TimeoutError, OverflowError) as exc:
            failures.append({"stage": kind, "code": str(exc) if isinstance(exc, CollectionError)
                             else "collector_" + exc.__class__.__name__})
        finally:
            if kind == "academic":
                diagnostics[kind] = _academic_collection_diagnostics(temporary, day)
            temporary.unlink(missing_ok=True)
    state = inspect(day)
    if state["phase"] == "authoring_packet_pending":
        state = _repair_packet(day)
    state["network_preflight"] = preflight
    if failures:
        state["collection_failures"] = failures
        state["operation_failed"] = True
    if warnings:
        state["collection_warnings"] = warnings
    if recoveries:
        state["collection_recovery"] = recoveries
    if diagnostics:
        state["collection_diagnostics"] = diagnostics
    return _finish_collection_attempt(state, started_at)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    values = list(sys.argv[1:] if argv is None else argv)
    # Compatibility for the pre-v4 scheduled prompt; new automation uses subcommands.
    if values and values[0].startswith("--"):
        values.insert(0, "status")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    daily = sub.add_parser("daily", help="Pinned current-edition execution; no automatic backfill.")
    daily.add_argument("--date",required=True)
    daily.add_argument("--action",choices=("status","plan","work","packet"),default="status")
    daily.add_argument("--record",action="store_true")
    daily.add_argument("--max-tasks",type=int,default=4)
    sources = sub.add_parser("sources", help="Independent source preparation; never publication status.")
    sources.add_argument("--date", required=True)
    sources.add_argument("--pool-dir", type=Path, required=True)
    sources.add_argument("--action", choices=("plan", "status", "work", "packet"), default="plan")
    sources.add_argument("--max-tasks", type=int, default=4)
    sources.add_argument("--domain",choices=("all","ai-social"),default="all")
    for name in ("status", "preflight", "collect", "resume", "expand", "recheck", "queue"):
        command = sub.add_parser(name)
        command.add_argument("--date", required=True)
        command.add_argument("--record", action="store_true")
        if name == "queue":
            command.add_argument("--withdraw-reason", help="Record an explicit no-backfill decision without deleting history.")
        if name == "status":
            command.add_argument("--online", action="store_true")
            command.add_argument("--preflight-network", action="store_true")
    return parser.parse_args(values)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command == "sources":
        from source_preparation import main as prepare_sources
        return prepare_sources([args.action, "--date", args.date, "--pool-dir", str(args.pool_dir),
                                "--max-tasks", str(args.max_tasks), "--domain",args.domain])
    try:
        if args.command == "daily":
            state = daily_execution(args.date,action=args.action,record=args.record,max_tasks=args.max_tasks)
        elif args.command == "queue":
            state = workflow_queue(args.date, record=args.record, withdraw_reason=args.withdraw_reason)
        elif args.command in {"collect", "resume"}:
            state = _collect(args.date)
            if state["phase"] == "expansion_pending":
                state = _expand(args.date)
            elif state["phase"] == "late_arrival_pending":
                state = _recheck_late_arrivals(args.date)
        elif args.command == "expand":
            state = _expand(args.date)
        elif args.command == "recheck":
            state = _recheck_late_arrivals(args.date)
        else:
            state = inspect(args.date, online=getattr(args, "online", False), record_remote=args.record)
            if args.command == "preflight" or getattr(args, "preflight_network", False):
                state = with_network_preflight(state, force=True)
        if args.command not in {"queue","daily"}:
            _record(state, args.record)
    except (OSError, ValueError, TypeError, AttributeError, TimeoutError, OverflowError) as exc:
        state = {"date": args.date, "phase": "recovery_failed", "packet_status": "not_checked",
                 "remote_status": "not_checked", "action_required": True, "operation_failed": True,
                 "failures": [{"stage": "orchestration", "code": str(exc) if isinstance(exc, CollectionError)
                               else exc.__class__.__name__}],
                 "next_action": "Repair this controlled failure and resume; existing artifacts remain authoritative."}
    print(json.dumps(state, ensure_ascii=False, indent=2))
    checked_network = args.command in {"preflight", "collect", "resume", "expand", "recheck"} or getattr(args, "preflight_network", False)
    return 2 if state.get("operation_failed") or (getattr(args, "online", False) and state.get("phase") != "remote_complete") or (checked_network and state["phase"] in {
        "environment_blocked", "environment_unverified", "collection_invalid",
        "authoring_packet_incompatible", "expansion_incompatible", "late_arrival_incompatible", "candidate_invalid", "recovery_failed"}) else 0


if __name__ == "__main__":
    raise SystemExit(main())
