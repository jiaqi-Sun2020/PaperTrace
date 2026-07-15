#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial smoke audit for chat-knowledge-profile."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[4]
SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "init_knowledge_profile.py"
PROFILE_V2_DIR = PROJECT_ROOT / "skills" / "reader-learner" / "scripts"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fail(message: str, details: str = "") -> int:
    print(json.dumps({"status": "fail", "message": message, "details": details}, ensure_ascii=False, indent=2))
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="chat-profile-audit-") as tmp_raw:
        tmp = Path(tmp_raw)
        export = tmp / "chatgpt_export.json"
        export.write_text(json.dumps([
            {
                "title": "Quantum Walk Reader Preferences",
                "mapping": {
                    "1": {
                        "message": {
                            "author": {"role": "user"},
                            "create_time": 1,
                            "metadata": {"model_slug": "gpt-4o"},
                            "content": {
                                "parts": [
                                    "请以后默认从第一性原理解释。QSVT 我不懂，quantum walk 我懂了。"
                                ]
                            },
                        }
                    },
                    "2": {
                        "message": {
                            "author": {"role": "assistant"},
                            "create_time": 2,
                            "content": {"parts": ["好的，我会用公式推导和物理直觉解释。"]},
                        }
                    },
                    "3": {
                        "message": {
                            "author": {"role": "user"},
                            "create_time": 3,
                            "content": {"parts": ["temporary api_key=sk-THIS_SHOULD_NOT_BE_STORED_1234567890"]},
                        }
                    },
                },
            }
        ], ensure_ascii=False), encoding="utf-8")

        out = tmp / "out"
        collect = run([sys.executable, str(SCRIPT), "collect", "--input", str(export), "--output", str(out)], PROJECT_ROOT)
        if collect.returncode != 0:
            return fail("collect failed", collect.stderr)
        events = load_jsonl(out / "events.jsonl")
        manifest = load_json(out / "manifest.json")
        summaries = load_json(out / "conversation_summaries.json")
        if manifest.get("sensitive_events_skipped") != 1:
            return fail("sensitive event was not skipped")
        if any("sk-THIS_SHOULD_NOT_BE_STORED" in row.get("text", "") for row in events):
            return fail("sensitive value leaked into events.jsonl")
        if not summaries.get("items") or not summaries["items"][0].get("topic_tags"):
            return fail("conversation summary or topic tags missing")

        candidates_path = out / "profile_candidates.json"
        extract = run([sys.executable, str(SCRIPT), "extract", "--events", str(out / "events.jsonl"), "--output", str(candidates_path)], PROJECT_ROOT)
        if extract.returncode != 0:
            return fail("extract failed", extract.stderr)
        candidates = load_json(candidates_path)
        if not candidates.get("items"):
            return fail("no candidates extracted")

        profile = tmp / "profile.json"
        profile.write_text(json.dumps({
            "version": 2,
            "updated_at": "2026-01-01T00:00:00+00:00",
            "description": "audit profile",
            "status_scale": {},
            "concepts": {},
            "events": [],
            "sources": {},
            "review_queue": [],
            "reading_sessions": [],
            "migrations": [],
        }, ensure_ascii=False), encoding="utf-8")
        patch_path = out / "profile_patch.json"
        propose = run([
            sys.executable,
            str(SCRIPT),
            "propose",
            "--profile",
            str(profile),
            "--candidates",
            str(candidates_path),
            "--output",
            str(patch_path),
        ], PROJECT_ROOT)
        if propose.returncode != 0:
            return fail("propose failed", propose.stderr)
        patch = load_json(patch_path)
        handoff = patch.get("reader_feedback_handoff", {})
        if handoff.get("source_kind") != "chat_session":
            return fail("chat handoff source_kind is invalid")
        if "reader_feedback_version" in handoff or "reader_path" in handoff or "bundle_provenance" in handoff:
            return fail("chat handoff must not masquerade as a reader bundle")
        for idx, item in enumerate(handoff.get("items", [])):
            for field in ("concept", "concept_id", "concept_type", "status", "annotation_kind", "source_anchor", "block_id"):
                if not item.get(field):
                    return fail(f"handoff item {idx} missing {field}")
            if not item.get("source") or not item.get("source_title"):
                return fail(f"handoff item {idx} is missing local chat provenance")

        sys.path.insert(0, str(PROFILE_V2_DIR))
        from profile_v2 import empty_profile_v2, import_feedback  # type: ignore

        try:
            import_feedback(empty_profile_v2(), handoff)
        except Exception as exc:  # noqa: BLE001 - audit reports validation details.
            return fail("reader-learner strict validation rejected handoff", str(exc))

    print(json.dumps({"status": "pass", "checks": ["collect", "sensitive-skip", "summaries", "extract", "propose", "reader-learner-validation"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
