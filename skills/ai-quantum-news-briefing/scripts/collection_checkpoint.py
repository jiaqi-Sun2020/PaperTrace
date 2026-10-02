"""Atomic, query-bound collection checkpoints; never publication evidence."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

MAX_CHECKPOINT_BYTES = 32_000_000


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".checkpoint-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_checkpoint(path: Path | None, scope: Any) -> dict:
    if path is None or not path.is_file():
        return {}
    try:
        if path.stat().st_size > MAX_CHECKPOINT_BYTES:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        payload = value["payload"]
        if (value.get("version") != 1 or value.get("scope_sha256") != fingerprint(scope)
                or not isinstance(payload, dict) or value.get("payload_sha256") != fingerprint(payload)):
            return {}
        return payload
    except (OSError, ValueError, TypeError, KeyError):
        return {}


def save_checkpoint(path: Path | None, scope: Any, payload: dict) -> None:
    if path is not None:
        value = {"version": 1, "scope_sha256": fingerprint(scope),
                 "payload_sha256": fingerprint(payload), "payload": payload}
        if len((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")) > MAX_CHECKPOINT_BYTES:
            raise ValueError("checkpoint_too_large")
        atomic_json(path, value)
