"""Scoped, atomic saving of human/agent-authored daily drafts and reviews.

This entry point never grants filesystem permission or approves content. In a
restricted task its complete invocation still needs host approval. Small JSON
patches avoid Windows command-length and PowerShell Chinese-encoding problems.
"""
from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

from daily_pipeline import NEWS_ROOT, atomic_copy, atomic_json
from release_audit import REVIEW_NAMES
from release_lock import release_lock

MAX_BYTES = 32 * 1024 * 1024
MAX_PAYLOAD = 20000


class AuthoringError(ValueError):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"


def contained(root, path):
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise AuthoringError("path_outside_news") from None
    # Reject reparse points within news, including junctions and symlinks.
    current = path
    while True:
        if current.is_symlink() or (current.exists() and
                getattr(current.lstat(), "st_file_attributes", 0) & 0x400):
            raise AuthoringError("reparse_path_forbidden")
        if current == root:
            break
        current = current.parent
    return path


def decode_json(raw):
    if len(raw) > MAX_BYTES:
        raise AuthoringError("json_too_large")
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise AuthoringError("duplicate_json_key")
            result[key] = value
        return result
    def invalid_constant(value):
        raise AuthoringError("nonfinite_json_number")
    text = raw.decode("utf-8")
    if "\ufffd" in text:
        raise AuthoringError("corrupted_utf8_text")
    result = json.loads(text, object_pairs_hook=pairs, parse_constant=invalid_constant)
    if "\ufffd" in json.dumps(result, ensure_ascii=False, allow_nan=False):
        raise AuthoringError("corrupted_utf8_text")
    return result


def target_path(root, day, kind, run_id=None):
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", day) or date.fromisoformat(day).isoformat() != day:
        raise AuthoringError("invalid_release_date")
    final = contained(root, root / day)
    if any(final.glob("daily_pipeline_manifest_*.json")):
        raise AuthoringError("published_release_frozen")
    stages = contained(root, final / ".staging")
    if kind == "candidate":
        if run_id:
            raise AuthoringError("candidate_run_id_forbidden")
        if stages.exists() and any(stages.iterdir()):
            raise AuthoringError("staged_candidate_frozen")
        return contained(root, root / "_collection" / day / ("candidate_" + day + ".json"))
    if kind not in {"news-review", "story-review"}:
        raise AuthoringError("unknown_artifact_kind")
    if not run_id or not re.fullmatch(re.escape(day) + r"-[0-9a-f]{12}", run_id):
        raise AuthoringError("invalid_staging_run_id")
    stage = contained(root, stages / run_id)
    manifest = decode_json((stage / ("daily_pipeline_manifest_" + day + ".json")).read_bytes())
    if (manifest.get("date") != day or manifest.get("run_id") != run_id
            or manifest.get("status") != "staged" or manifest.get("pipeline_version") != 4):
        raise AuthoringError("staging_manifest_mismatch")
    key = kind.replace("-", "_")
    path = contained(root, stage / REVIEW_NAMES[key].format(date=day))
    if not path.is_file():
        raise AuthoringError("review_template_required")
    return path


def tokens(pointer):
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise AuthoringError("invalid_json_pointer")
    parts = pointer[1:].split("/")
    if any(re.search(r"~(?![01])", part) for part in parts):
        raise AuthoringError("invalid_json_pointer_escape")
    return [part.replace("~1", "/").replace("~0", "~") for part in parts]


def lookup(value, parts):
    for part in parts:
        if isinstance(value, list):
            if not re.fullmatch(r"0|[1-9]\d*", part):
                raise AuthoringError("invalid_array_index")
            value = value[int(part)]
        else:
            value = value[part]
    return value


def patched(current, operations, root, source_root):
    result = deepcopy(current)
    if not isinstance(operations, list) or not 1 <= len(operations) <= 100:
        raise AuthoringError("invalid_patch_operations")
    for op in operations:
        if not isinstance(op, dict) or op.get("op") not in {"add", "replace", "remove", "copy-file"}:
            raise AuthoringError("unsupported_patch_operation")
        parts = tokens(op.get("path"))
        parent = lookup(result, parts[:-1])
        key = parts[-1]
        value = op.get("value")
        if op["op"] == "copy-file":
            relative = op.get("source")
            if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise AuthoringError("invalid_source_path")
            source = contained(root, root / relative)
            try:
                source.resolve().relative_to(source_root.resolve())
            except ValueError:
                raise AuthoringError("source_outside_release_collection") from None
            if any(part.startswith(".") for part in source.relative_to(source_root).parts):
                raise AuthoringError("hidden_source_path_forbidden")
            if source.name.startswith("candidate_"):
                raise AuthoringError("authored_candidate_is_not_source_evidence")
            if source.suffix != ".json" or source.stat().st_size > MAX_BYTES:
                raise AuthoringError("invalid_source_json")
            value = decode_json(source.read_bytes())
            if op.get("source_pointer"):
                value = lookup(value, tokens(op["source_pointer"]))
        elif op["op"] != "remove" and "value" not in op:
            raise AuthoringError("patch_value_required")
        if isinstance(parent, list):
            if key == "-" and op["op"] in {"add", "copy-file"}:
                parent.append(value)
                continue
            if not re.fullmatch(r"0|[1-9]\d*", key):
                raise AuthoringError("invalid_array_index")
            index = int(key)
            if op["op"] == "add":
                if index > len(parent):
                    raise AuthoringError("array_index_out_of_range")
                parent.insert(index, value)
            elif op["op"] == "remove":
                del parent[index]
            else:
                parent[index] = value
        elif isinstance(parent, dict):
            if op["op"] in {"replace", "remove"} and key not in parent:
                raise AuthoringError("patch_key_missing")
            if op["op"] == "remove":
                del parent[key]
            else:
                parent[key] = value
        else:
            raise AuthoringError("patch_parent_invalid")
    return result


def validate(value, kind, previous):
    if not isinstance(value, dict):
        raise AuthoringError("artifact_object_required")
    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    decode_json(serialized)
    if kind == "candidate":
        if (type(value.get("news_feedback_version")) is not int or value["news_feedback_version"] != 1
                or not isinstance(value.get("sections"), list)):
            raise AuthoringError("candidate_draft_structure_invalid")
        for section in value["sections"]:
            if (not isinstance(section, dict) or not isinstance(section.get("items"), list)
                    or any(not isinstance(item, dict) for item in section["items"])):
                raise AuthoringError("candidate_draft_structure_invalid")
        value["semantic_review_status"] = "not_reviewed"
        value.setdefault("authoring_status", "in_progress")
        if value["authoring_status"] not in {"in_progress", "complete"}:
            raise AuthoringError("invalid_authoring_status")
    else:
        # Authoring cannot rebind a template to different sources/content.
        keys = ("version", "content_digest") if kind == "news-review" else ("review_protocol_version", "story_sha256")
        if any(value.get(key) != previous.get(key) or type(value.get(key)) is not type(previous.get(key)) for key in keys):
            raise AuthoringError("review_binding_changed")
        if kind == "news-review":
            identity = lambda data: [(row["item_id"], row["claim_digest"], row["source_url"]) for row in data["items"]]
            if identity(value) != identity(previous):
                raise AuthoringError("review_item_binding_changed")


def save(root, day, kind, expected, payload, *, patch=False, run_id=None):
    root = Path(root).absolute()
    contained(root, root / "_index" / ".release.lock")
    with release_lock(root):
        path = target_path(root, day, kind, run_id)
        actual = digest(path)
        if actual != expected:
            raise AuthoringError("authoring_conflict")
        try:
            previous = decode_json(path.read_bytes()) if actual != "absent" else {}
        except ValueError:
            if kind != "candidate" or patch:
                raise
            previous = None  # Explicit digest-bound replacement, retaining raw backup.
        if (kind == "candidate" and isinstance(previous, dict)
                and type(previous.get("news_feedback_version")) is int
                and previous["news_feedback_version"] > 1):
            raise AuthoringError("candidate_version_incompatible")
        source_root = contained(root, root / "_collection" / day)
        value = patched(previous, payload, root, source_root) if patch else deepcopy(payload)
        validate(value, kind, previous)
        if value == previous:
            return {"status": "unchanged", "path": str(path), "sha256": actual, "content_approved": False}
        if actual != "absent":
            backup = contained(root, path.parent / ".authoring_backups" / (path.name + "." + actual + ".json"))
            if not backup.exists():
                atomic_copy(path, backup)
            elif digest(backup) != actual:
                raise AuthoringError("backup_digest_mismatch")
        atomic_json(path, value)
        return {"status": "draft_saved", "path": str(path), "sha256": digest(path), "content_approved": False}


def probe(root, day):
    root = Path(root).absolute()
    contained(root, root / "_index" / ".release.lock")
    with release_lock(root):
        target = target_path(root, day, "candidate")
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".authoring-write-probe.", dir=target.parent) as handle:
            handle.write(b"permission probe only")
            handle.flush()
        return {"status": "authoring_write_probe_pass", "content_approved": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["probe", "save", "patch"])
    parser.add_argument("--date", required=True)
    parser.add_argument("--kind", choices=["candidate", "news-review", "story-review"], default="candidate")
    parser.add_argument("--run-id")
    parser.add_argument("--expected-sha256", help="Current target digest, or absent for first creation")
    parser.add_argument("--payload-base64", help="UTF-8 JSON or JSON patch operations; max 20000 ASCII characters")
    args = parser.parse_args(argv)
    try:
        if args.command == "probe":
            if args.payload_base64 or args.expected_sha256 or args.run_id or args.kind != "candidate":
                raise AuthoringError("invalid_probe_arguments")
            result = probe(NEWS_ROOT, args.date)
        else:
            if not args.expected_sha256 or not re.fullmatch(r"absent|[0-9a-f]{64}", args.expected_sha256):
                raise AuthoringError("expected_digest_required")
            if not args.payload_base64 or len(args.payload_base64) > MAX_PAYLOAD:
                raise AuthoringError("bounded_payload_required")
            payload = decode_json(base64.b64decode(args.payload_base64, validate=True))
            result = save(NEWS_ROOT, args.date, args.kind, args.expected_sha256, payload,
                          patch=args.command == "patch", run_id=args.run_id)
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, IndexError, TimeoutError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, AuthoringError) else exc.__class__.__name__
        print(json.dumps({"status": "authoring_failed", "reason": code,
                          "content_approved": False, "action_required": True}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
