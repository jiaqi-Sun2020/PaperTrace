"""Non-destructive, digest-bound revisions of failed protocol-4 staging.

The lifecycle JSON is the single atomic commit point. Old candidates and runs
remain at their original paths; no review or release is approved by revision.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from collection_checkpoint import atomic_json, fingerprint
from release_lock import release_lock

MAX_BYTES = 128 * 1024 * 1024
RUN = re.compile(r"20\d{2}-\d{2}-\d{2}-[0-9a-f]{12}\Z")


def contained(root, path):
    root, path = Path(root).absolute(), Path(path).absolute()
    path.resolve().relative_to(root.resolve())
    current = path
    while True:
        if current.is_symlink() or (current.exists() and getattr(current.lstat(), "st_file_attributes", 0) & 0x400):
            raise ValueError("revision_reparse_path_forbidden")
        if current == root:
            break
        current = current.parent
    return path


def sha(path):
    with path.open("rb") as handle:
        digest = hashlib.sha256()
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_bytes(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".revision-")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def lifecycle_path(root, day):
    from datetime import date
    if not isinstance(day, str) or not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", day) or date.fromisoformat(day).isoformat() != day:
        raise ValueError("revision_date_invalid")
    return contained(root, Path(root) / "_automation" / ("staging_revisions_" + day + ".json"))


def lifecycle(root, day):
    path = lifecycle_path(root, day)
    if not path.exists():
        return {"version": 1, "date": day, "superseded_runs": {}}
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("revision_lifecycle_too_large")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or type(value.get("version")) is not int or value.get("version") != 1 or value.get("date") != day
            or not isinstance(value.get("superseded_runs"), dict)
            or value.get("state_sha256") != fingerprint({k: v for k, v in value.items() if k != "state_sha256"})):
        raise ValueError("revision_lifecycle_invalid")
    revision = value.get("active_revision")
    active_run = value.get("active_run_id")
    if active_run is not None and (not isinstance(active_run, str) or not RUN.fullmatch(active_run) or not active_run.startswith(day + "-")):
        raise ValueError("revision_active_run_invalid")
    if active_run in value["superseded_runs"]:
        raise ValueError("revision_active_run_invalid")
    if revision is not None and (not isinstance(revision, str) or not RUN.fullmatch(revision) or not revision.startswith(day + "-")):
        raise ValueError("revision_identity_invalid")
    if bool(revision) != bool(value["superseded_runs"]):
        raise ValueError("revision_lifecycle_invalid")
    for run_id, record in value["superseded_runs"].items():
        if (not RUN.fullmatch(run_id) or not run_id.startswith(day + "-") or not isinstance(record, dict)
                or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("run_sha256")))
                or not re.fullmatch(r"[0-9a-f]{64}", str(record.get("candidate_sha256")))
                or not isinstance(record.get("revision_id"), str) or not RUN.fullmatch(record["revision_id"])
                or not record["revision_id"].startswith(day + "-")
                or not isinstance(record.get("reason"), str) or not record["reason"].strip() or len(record["reason"]) > 1000):
            raise ValueError("revision_run_record_invalid")
        peers = record.get("peer_runs", {})
        if "external_evidence_sha256" in record and not re.fullmatch(r"[0-9a-f]{64}", str(record["external_evidence_sha256"])):
            raise ValueError("revision_evidence_binding_invalid")
        if (not isinstance(peers, dict) or len(peers) > 16 or run_id in peers
                or any(not isinstance(peer, str) or not RUN.fullmatch(peer) or not peer.startswith(day + "-")
                       or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
                       or not isinstance(value["superseded_runs"].get(peer), dict)
                       or value["superseded_runs"][peer].get("run_sha256") != digest
                       or value["superseded_runs"][peer].get("revision_id") != record["revision_id"]
                       for peer, digest in peers.items())):
            raise ValueError("revision_peer_bindings_invalid")
    if revision and revision not in {record["revision_id"] for record in value["superseded_runs"].values()}:
        raise ValueError("revision_identity_invalid")
    return value


def candidate_path(root, day):
    value = lifecycle(root, day)
    folder = Path(root) / "_collection" / day
    if value.get("active_revision"):
        folder = folder / ".revisions" / value["active_revision"]
    return contained(root, folder / ("candidate_" + day + ".json"))


def run_snapshot(root, stage):
    stage = contained(root, stage)
    if not stage.is_dir():
        raise ValueError("revision_run_missing")
    records = []
    total = 0
    entries = 0
    for path in stage.rglob("*"):
        entries += 1
        if entries > 512:
            raise ValueError("revision_run_too_large")
        contained(root, path)
        if path.is_file():
            total += path.stat().st_size
            if total > MAX_BYTES or len(records) >= 256:
                raise ValueError("revision_run_too_large")
            records.append({"path": path.relative_to(stage).as_posix(), "sha256": sha(path)})
    records.sort(key=lambda row: row["path"])
    return {"files": records, "sha256": fingerprint(records)}


def active_stages(root, day):
    value = lifecycle(root, day)
    folder = contained(root, Path(root) / day / ".staging")
    for run_id, record in value["superseded_runs"].items():
        if run_snapshot(root, folder / run_id)["sha256"] != record["run_sha256"]:
            raise ValueError("superseded_run_changed")
    return [contained(root, path) for path in sorted(folder.iterdir())
            if path.name not in value["superseded_runs"]] if folder.exists() else []


def assert_active_stage(stage, manifest):
    stage = Path(stage).absolute()
    day = manifest.get("date")
    if stage.parent.name == ".staging":
        root = stage.parents[2]
    elif stage.name == day and manifest.get("pipeline_version") in (3, 4):
        root = stage.parent  # Relocation cannot revive a superseded run.
    else:
        return  # Historical releases without a lifecycle keep their semantics.
    value = lifecycle(root, day)
    if manifest.get("run_id", stage.name) in value["superseded_runs"]:
        raise ValueError("staging_revision_superseded")
    lifecycle_version = manifest.get("staging_lifecycle_version")
    if lifecycle_version is not None and (type(lifecycle_version) is not int or lifecycle_version != 1):
        raise ValueError("staging_lifecycle_version_unsupported")
    if stage.parent.name == ".staging" and ("active_run_id" in value or lifecycle_version == 1) and manifest.get("run_id") != value.get("active_run_id"):
        raise ValueError("staging_run_is_not_current")
    if value.get("active_revision") and manifest.get("revision_id") != value["active_revision"]:
        raise ValueError("staging_revision_is_not_current")


def assert_current_candidate(root, day, path):
    value = lifecycle(root, day)
    if value.get("active_revision") and Path(path).resolve() != candidate_path(root, day).resolve():
        raise ValueError("candidate_revision_is_not_current")
    return value.get("active_revision")


def register_stage(root, day, run_id, revision_id, *, correction=False):
    """Caller holds release_lock. Commit the sole active run after installation.

A crash before this commit leaves an unregistered run unable to pass verification;
it can be explicitly revised with its snapshot. Finalized releases stay readable.
"""
    value = lifecycle(root, day)
    if not isinstance(run_id, str) or not RUN.fullmatch(run_id) or not run_id.startswith(day + "-"):
        raise ValueError("revision_run_identity_invalid")
    if value.get("active_revision") != revision_id:
        raise ValueError("candidate_revision_changed_during_staging")
    stages = active_stages(root, day)
    if not correction and any(path.name != run_id for path in stages):
        raise ValueError("active_staging_exists_use_controlled_revision")
    value["active_run_id"] = run_id
    value["state_sha256"] = fingerprint({k: v for k, v in value.items() if k != "state_sha256"})
    atomic_json(lifecycle_path(root, day), value)


def normalize_evidence_binding(day, binding):
    """Bound raw-capture bytes and index; no arbitrary filesystem read contract."""
    if binding is None:
        return None  # Historical callers keep their contract; migration supplies it.
    from datetime import date, timedelta
    coverage = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
    if (not isinstance(binding, dict) or set(binding) != {"version", "date", "files", "index_sha256"}
            or type(binding.get("version")) is not int or binding["version"] != 1 or binding["date"] != day
            or not isinstance(binding["files"], list) or not 1 <= len(binding["files"]) <= 128
            or not isinstance(binding["index_sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", binding["index_sha256"])):
        raise ValueError("revision_evidence_binding_invalid")
    files = []
    for row in binding["files"]:
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
                or not isinstance(row["path"], str)
                or not re.fullmatch(re.escape("_collection/" + coverage + "/source_captures/") + r"[A-Za-z0-9_-]{1,128}\.json", row["path"])
                or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("revision_evidence_binding_invalid")
        files.append(dict(row))
    if len({row["path"] for row in files}) != len(files):
        raise ValueError("revision_evidence_binding_invalid")
    return {"version": 1, "date": day, "files": sorted(files, key=lambda row: row["path"]), "index_sha256": binding["index_sha256"]}


def assert_external_evidence(root, binding):
    if binding is None:
        return
    for row in binding["files"]:
        path = contained(root, Path(root) / row["path"])
        if not path.is_file() or sha(path) != row["sha256"]:
            raise ValueError("revision_capture_evidence_conflict")
    index = contained(root, Path(root) / "_index" / "story_index.jsonl")
    if not index.is_file() or sha(index) != binding["index_sha256"]:
        raise ValueError("revision_index_evidence_conflict")


def revise(root, day, run_id, expected_run, expected_candidate, reason, *, verify, expected_peers=None, expected_evidence=None):
    root = Path(root).absolute()
    lifecycle_path(root, day)
    evidence = normalize_evidence_binding(day, expected_evidence)
    if not isinstance(run_id, str) or not RUN.fullmatch(run_id) or not run_id.startswith(day + "-"):
        raise ValueError("revision_run_identity_invalid")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000 or any(ord(c) < 32 for c in reason):
        raise ValueError("revision_reason_required")
    peers = {} if expected_peers is None else expected_peers
    if (not isinstance(peers, dict) or len(peers) > 16 or run_id in peers
            or any(not isinstance(key, str) or not RUN.fullmatch(key) or not key.startswith(day + "-")
                   or not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                   for key, value in peers.items())):
        raise ValueError("revision_peer_bindings_invalid")
    peers = dict(peers)
    contained(root, root / "_index" / ".release.lock")
    with release_lock(root):
        # Capture installation and index commits use the same OS lock. Verify
        # preflight bindings inside the transaction and again before commit.
        assert_external_evidence(root, evidence)
        final = contained(root, root / day)
        if any(final.glob("daily_pipeline_manifest_*.json")):
            raise ValueError("published_release_frozen")
        value = lifecycle(root, day)
        stage = contained(root, final / ".staging" / run_id)
        snapshot = run_snapshot(root, stage)
        if snapshot["sha256"] != expected_run:
            raise ValueError("revision_run_conflict")
        previous = value["superseded_runs"].get(run_id)
        if previous:
            if previous["candidate_sha256"] != expected_candidate or previous["reason"] != reason:
                raise ValueError("revision_repeat_conflict")
            if previous.get("peer_runs", {}) != peers:
                raise ValueError("revision_repeat_conflict")
            if previous.get("external_evidence_sha256") != (fingerprint(evidence) if evidence else None):
                raise ValueError("revision_repeat_conflict")
            return {"status": "revision_unchanged", "candidate": str(candidate_path(root, day)),
                    "revision_id": value["active_revision"], "content_approved": False}
        if value.get("active_run_id") not in (None, run_id, *peers):
            raise ValueError("revision_run_is_not_current")
        other_ids = {path.name for path in active_stages(root, day) if path.name != run_id}
        if other_ids != set(peers):
            raise ValueError("revision_multiple_active_runs")
        peer_snapshots = {}
        for peer, expected_hash in peers.items():
            peer_stage = contained(root, final / ".staging" / peer)
            peer_snapshot = run_snapshot(root, peer_stage)
            if peer_snapshot["sha256"] != expected_hash:
                raise ValueError("revision_peer_run_conflict")
            peer_manifest = json.loads((peer_stage / ("daily_pipeline_manifest_" + day + ".json")).read_text(encoding="utf-8"))
            if (not isinstance(peer_manifest, dict) or type(peer_manifest.get("pipeline_version")) is not int
                    or peer_manifest.get("pipeline_version") != 4 or peer_manifest.get("status") != "staged"
                    or peer_manifest.get("date") != day or peer_manifest.get("run_id") != peer):
                raise ValueError("revision_requires_protocol4_staging")
            if verify(peer_stage, strict=True)["status"] == "pass":
                raise ValueError("reviewed_staging_frozen")
            peer_snapshots[peer] = peer_snapshot
        manifest = json.loads((stage / ("daily_pipeline_manifest_" + day + ".json")).read_text(encoding="utf-8"))
        if (not isinstance(manifest, dict) or type(manifest.get("pipeline_version")) is not int or manifest.get("pipeline_version") != 4 or manifest.get("status") != "staged"
                or manifest.get("date") != day or manifest.get("run_id") != run_id):
            raise ValueError("revision_requires_protocol4_staging")
        if verify(stage, strict=True)["status"] == "pass":
            raise ValueError("reviewed_staging_frozen")
        current = candidate_path(root, day)
        if not current.is_file() or sha(current) != expected_candidate:
            raise ValueError("revision_candidate_conflict")
        if current.stat().st_size > 32 * 1024 * 1024:
            raise ValueError("revision_candidate_too_large")
        before = current.read_bytes()
        if hashlib.sha256(before).hexdigest() != expected_candidate:
            raise ValueError("revision_candidate_conflict")
        draft = json.loads(before.decode("utf-8"))
        if isinstance(draft, dict):
            draft.setdefault("news_feedback_version", 1)
        if (not isinstance(draft, dict) or type(draft.get("news_feedback_version")) is not int or draft["news_feedback_version"] != 1
                or not isinstance(draft.get("sections"), list)):
            raise ValueError("revision_candidate_invalid")
        identity = {"run": run_id, "run_hash": expected_run, "candidate": expected_candidate, "reason": reason}
        if peers:
            identity["peer_runs"] = peers
        if evidence:
            identity["external_evidence_sha256"] = fingerprint(evidence)
        revision_id = day + "-" + fingerprint(identity)[:12]
        folder = contained(root, root / "_collection" / day / ".revisions" / revision_id)
        draft = deepcopy(draft)
        draft.update(authoring_status="in_progress", semantic_review_status="not_reviewed",
                     source_url_contract_version=2, revision_id=revision_id, supersedes_run_id=run_id)
        draft.pop("ranking_manifest", None)
        material = {"candidate_before.json": before,
                    "run_snapshot.json": json.dumps(snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
                    "candidate_" + day + ".json": json.dumps(draft, ensure_ascii=False, indent=2).encode("utf-8")}
        for peer, peer_snapshot in peer_snapshots.items():
            material["run_snapshot_" + peer + ".json"] = json.dumps(peer_snapshot, ensure_ascii=False, indent=2).encode("utf-8")
        if evidence:
            material["external_evidence_binding.json"] = json.dumps(evidence, ensure_ascii=False, indent=2).encode("utf-8")
        for name, body in material.items():
            target = contained(root, folder / name)
            if target.exists() and target.read_bytes() != body:
                raise ValueError("revision_orphan_content_conflict")
            if not target.exists():
                atomic_bytes(target, body)
        # Check again immediately before the lifecycle commit.
        if sha(current) != expected_candidate or run_snapshot(root, stage)["sha256"] != expected_run:
            raise ValueError("revision_inputs_changed")
        for peer, expected_hash in peers.items():
            if run_snapshot(root, final / ".staging" / peer)["sha256"] != expected_hash:
                raise ValueError("revision_inputs_changed")
        if {path.name for path in active_stages(root, day)} != {run_id, *peers}:
            raise ValueError("revision_multiple_active_runs")
        assert_external_evidence(root, evidence)
        value["superseded_runs"][run_id] = {"run_sha256": expected_run, "candidate_sha256": expected_candidate,
                                            "revision_id": revision_id, "reason": reason}
        if peers:
            value["superseded_runs"][run_id]["peer_runs"] = peers
        for peer, expected_hash in peers.items():
            value["superseded_runs"][peer] = {"run_sha256": expected_hash, "candidate_sha256": expected_candidate,
                                              "revision_id": revision_id, "reason": reason}
        if evidence:
            for old_id in (run_id, *peers):
                value["superseded_runs"][old_id]["external_evidence_sha256"] = fingerprint(evidence)
        value["active_revision"] = revision_id
        value["active_run_id"] = None
        value["state_sha256"] = fingerprint({k: v for k, v in value.items() if k != "state_sha256"})
        atomic_json(lifecycle_path(root, day), value)
        target = candidate_path(root, day)
        return {"status": "revision_created", "revision_id": revision_id, "candidate": str(target),
                "sha256": sha(target), "supersedes_run_id": run_id, "content_approved": False}
