#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Initialize or extend PAPER knowledge profiles from exported chat sessions."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_STATUSES = {"mastered", "known", "learning", "unknown", "unrated"}
STATUS_ORDER = {"unrated": 0, "unknown": 1, "learning": 2, "known": 3, "mastered": 4}
TEXT_EXTS = {".txt", ".md", ".markdown", ".html", ".htm", ".json"}
SENSITIVE_RE = re.compile(
    r"(\.env|secret|secrets|credential|credentials|token|password|passwd|apikey|api_key|private_key|id_rsa|\.pem|\.p12|\.pfx|cookie|session)",
    re.I,
)

CONCEPT_HINTS = [
    "continuous-time quantum walk",
    "coined quantum walk",
    "quantum walk",
    "MHV scattering amplitudes",
    "Parke-Taylor amplitudes",
    "permutation tree",
    "Kraus operators",
    "quantum channel",
    "QAOA",
    "QUBO",
    "quantum error correction",
    "neutral-atom quantum computing",
    "structure-aware compilation",
    "reader-skill",
    "lean-html-skill",
    "knowledge_profile",
    "reader-learner",
    "nature-reader",
    "first principles",
]

RESEARCH_HINTS = [
    "quantum walk",
    "量子行走",
    "quantum machine learning",
    "QML",
    "量子机器学习",
    "quantum neural",
    "photonic",
    "photonics",
    "光学",
    "holography",
    "全息",
    "agent",
    "智能体",
    "AI",
    "LLM",
    "scattering amplitudes",
    "MHV",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def short_hash(text: str, length: int = 12) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:length]


def slugify(text: str, fallback: str = "item") -> str:
    ascii_text = text.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    if slug:
        return slug[:80]
    return f"{fallback}-{short_hash(text, 10)}"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def is_sensitive_path(path: Path) -> bool:
    return bool(SENSITIVE_RE.search(str(path)))


def iter_input_files(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in inputs:
        if re.match(r"^https?://", raw, re.I):
            continue
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in TEXT_EXTS and not is_sensitive_path(candidate):
                    files.append(candidate)
        elif path.is_file() and path.suffix.lower() in TEXT_EXTS and not is_sensitive_path(path):
            files.append(path)
    return sorted(set(files), key=lambda p: str(p).lower())


def html_to_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    raw = re.sub(r"(?s)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?s)</p\s*>", "\n\n", raw)
    raw = re.sub(r"(?s)<[^>]+>", " ", raw)
    return html.unescape(raw)


def read_text_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() in {".html", ".htm"}:
        return html_to_text(text)
    return text


def content_parts_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(content_parts_to_text(row) for row in content)
    if isinstance(content, dict):
        if isinstance(content.get("parts"), list):
            return "\n".join(content_parts_to_text(row) for row in content["parts"])
        if content.get("text"):
            return content_parts_to_text(content["text"])
    return ""


def messages_from_mapping(data: dict[str, Any], title: str, source_path: Path) -> list[dict[str, Any]]:
    mapping = data.get("mapping")
    if not isinstance(mapping, dict):
        return []
    rows: list[dict[str, Any]] = []
    for node in mapping.values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not isinstance(message, dict):
            continue
        role = clean_text(((message.get("author") or {}).get("role") if isinstance(message.get("author"), dict) else ""), 80) or "unknown"
        text = clean_text(content_parts_to_text(message.get("content")), 12000)
        if not text:
            continue
        create_time = message.get("create_time") or node.get("create_time") or ""
        rows.append({
            "title": title,
            "role": role,
            "timestamp": str(create_time) if create_time else "",
            "text": text,
            "source_path": str(source_path),
        })
    rows.sort(key=lambda row: (row.get("timestamp") or "", row.get("role") or ""))
    return rows


def messages_from_json(data: Any, source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if isinstance(data, list):
        for index, item in enumerate(data):
            if isinstance(item, dict):
                title = clean_text(item.get("title") or source_path.stem or f"conversation {index + 1}", 500)
                rows.extend(messages_from_mapping(item, title, source_path))
        if rows:
            return rows
    if isinstance(data, dict):
        title = clean_text(data.get("title") or data.get("name") or source_path.stem, 500)
        rows.extend(messages_from_mapping(data, title, source_path))
        if rows:
            return rows
        conversations = data.get("conversations")
        if isinstance(conversations, list):
            for index, item in enumerate(conversations):
                if isinstance(item, dict):
                    sub_title = clean_text(item.get("title") or f"{title} {index + 1}", 500)
                    rows.extend(messages_from_mapping(item, sub_title, source_path))
            if rows:
                return rows
    fallback = clean_text(json.dumps(data, ensure_ascii=False), 12000)
    return [{"title": source_path.stem, "role": "unknown", "timestamp": "", "text": fallback, "source_path": str(source_path)}] if fallback else []


def split_text_messages(text: str, source_path: Path) -> list[dict[str, Any]]:
    lines = text.splitlines()
    role_re = re.compile(r"^\s*(user|assistant|system|用户|助手|模型|chatgpt)\s*[:：]\s*(.*)$", re.I)
    messages: list[dict[str, Any]] = []
    current_role = "unknown"
    current: list[str] = []

    def flush() -> None:
        nonlocal current
        body = clean_text("\n".join(current), 12000)
        if body:
            messages.append({"title": source_path.stem, "role": current_role, "timestamp": "", "text": body, "source_path": str(source_path)})
        current = []

    for line in lines:
        match = role_re.match(line)
        if match:
            flush()
            role = match.group(1).lower()
            current_role = "user" if role in {"user", "用户"} else "assistant" if role in {"assistant", "助手", "模型", "chatgpt"} else "system"
            if match.group(2):
                current.append(match.group(2))
        else:
            current.append(line)
    flush()
    if messages:
        return messages

    compact = clean_text(text, 50000)
    chunks = [compact[i:i + 1800] for i in range(0, len(compact), 1800)]
    return [{"title": source_path.stem, "role": "unknown", "timestamp": "", "text": chunk, "source_path": str(source_path)} for chunk in chunks if chunk.strip()]


def load_messages(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        return messages_from_json(read_json(path), path)
    return split_text_messages(read_text_file(path), path)


def cmd_collect(args: argparse.Namespace) -> int:
    output_dir = Path(args.output).expanduser().resolve()
    files = iter_input_files(args.input)
    sources: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    skipped = [raw for raw in args.input if re.match(r"^https?://", raw, re.I)]
    for path in files:
        messages = load_messages(path)
        title = messages[0]["title"] if messages else path.stem
        source_id = "chat-src-" + short_hash(str(path) + title)
        source = {
            "source_id": source_id,
            "source_kind": "chat_session",
            "title": title,
            "path": str(path),
            "url": "",
            "created_at": "",
            "collected_at": utc_now(),
            "event_ids": [],
        }
        for turn_index, message in enumerate(messages, start=1):
            text = clean_text(message.get("text"), args.max_event_chars)
            if not text:
                continue
            event_id = "chat-evt-" + short_hash(source_id + str(turn_index) + text, 16)
            source["event_ids"].append(event_id)
            events.append({
                "event_id": event_id,
                "source_id": source_id,
                "source_title": title,
                "source_path": str(path),
                "role": clean_text(message.get("role") or "unknown", 80),
                "turn_index": turn_index,
                "timestamp": clean_text(message.get("timestamp"), 80),
                "text": text,
                "text_sha1": hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest(),
                "contains_sensitive_skip": False,
            })
        sources.append(source)
    write_jsonl(output_dir / "sources.jsonl", sources)
    write_jsonl(output_dir / "events.jsonl", events)
    manifest = {
        "generated_from": "init-knowledge-profile",
        "generated_at": utc_now(),
        "input_count": len(args.input),
        "files_collected": len(files),
        "sources": len(sources),
        "events": len(events),
        "skipped_url_inputs": skipped,
        "note": "ChatGPT share URLs are recorded only if saved locally first; this collector does not fetch web pages.",
    }
    write_json(output_dir / "manifest.json", manifest)
    print(f"Wrote {output_dir / 'sources.jsonl'}")
    print(f"Wrote {output_dir / 'events.jsonl'}")
    print(f"Sources: {len(sources)}")
    print(f"Events: {len(events)}")
    if skipped:
        print(f"Skipped URL inputs: {len(skipped)}")
    return 0


def candidate_id(kind: str, label: str, event_id: str) -> str:
    return "cand-" + short_hash("|".join([kind, label, event_id]), 16)


def add_candidate(bucket: dict[tuple[str, str], dict[str, Any]], item: dict[str, Any]) -> None:
    key = (item["type"], item["label"].casefold())
    existing = bucket.get(key)
    if existing is None:
        bucket[key] = item
        return
    existing["confidence"] = max(float(existing.get("confidence", 0)), float(item.get("confidence", 0)))
    if STATUS_ORDER.get(item.get("status", "unrated"), 0) > STATUS_ORDER.get(existing.get("status", "unrated"), 0):
        existing["status"] = item.get("status")
    for field in ("evidence_event_ids", "source_ids"):
        values = existing.setdefault(field, [])
        for value in item.get(field, []):
            if value not in values:
                values.append(value)
    if item.get("note") and item["note"] not in existing.setdefault("notes", []):
        existing["notes"].append(item["note"])


def base_candidate(kind: str, label: str, event: dict[str, Any], confidence: float, note: str, status: str = "unrated") -> dict[str, Any]:
    return {
        "candidate_id": candidate_id(kind, label, event["event_id"]),
        "type": kind,
        "label": clean_text(label, 180),
        "status": status if status in VALID_STATUSES else "unrated",
        "confidence": round(confidence, 2),
        "evidence_event_ids": [event["event_id"]],
        "source_ids": [event["source_id"]],
        "note": clean_text(note, 500),
        "notes": [clean_text(note, 500)] if note else [],
    }


def detect_status(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"(不懂|不理解|看不懂|没懂|卡住|confused|do not understand|don't understand|unclear)", text, re.I):
        return "unknown"
    if re.search(r"(有点懂|部分理解|还需要|还要例子|learning|partly understand)", text, re.I):
        return "learning"
    if re.search(r"(我懂了|理解了|明白了|i understand|makes sense)", text, re.I):
        return "known"
    if re.search(r"(掌握|会用|能讲清楚|can apply|can explain)", text, re.I):
        return "mastered"
    if "?" in text or "？" in text or re.search(r"(是什么|为什么|解释|讲一下|how|what|why)", lowered):
        return "unknown"
    return None


def extract_terms(text: str) -> list[str]:
    terms: list[str] = []
    lowered = text.lower()
    for hint in CONCEPT_HINTS:
        if hint.lower() in lowered and hint not in terms:
            terms.append(hint)
    for raw in re.findall(r"`([^`]{2,80})`", text):
        if raw not in terms:
            terms.append(raw)
    for raw in re.findall(r"\b[A-Z][A-Z0-9-]{2,20}\b", text):
        if raw not in terms:
            terms.append(raw)
    return terms[:8]


def preference_candidates(event: dict[str, Any]) -> list[dict[str, Any]]:
    text = event["text"]
    items: list[dict[str, Any]] = []
    if re.search(r"(第一性原理|first principles)", text, re.I):
        items.append(base_candidate("learning_preference", "first-principles explanations", event, 0.9, "User asked to reason from first principles."))
    if re.search(r"(公式推导|math derivation|推导)", text, re.I):
        items.append(base_candidate("learning_preference", "math-derivation explanations", event, 0.75, "User values derivation-level explanations."))
    if re.search(r"(物理直觉|physical intuition)", text, re.I):
        items.append(base_candidate("learning_preference", "physical-intuition explanations", event, 0.75, "User values physical intuition."))
    if re.search(r"(例子|example|举例)", text, re.I):
        items.append(base_candidate("learning_preference", "example-driven explanations", event, 0.65, "User asks for examples."))
    if re.search(r"(直接|具体|可执行|actionable|complete commands|完整命令)", text, re.I):
        items.append(base_candidate("writing_style", "direct specific actionable answers", event, 0.85, "User prefers direct, specific, actionable outputs."))
    return items


def workflow_candidates(event: dict[str, Any]) -> list[dict[str, Any]]:
    text = event["text"]
    items: list[dict[str, Any]] = []
    if re.search(r"(pipeline|工作流|流程)", text, re.I):
        items.append(base_candidate("workflow_preference", "explicit pipeline documentation", event, 0.7, "User asks to clarify or maintain project pipeline."))
    if re.search(r"(reader-skill|lean-html-skill|nature-reader|reader-learner|knowledge_profile|画像)", text, re.I):
        items.append(base_candidate("workflow_preference", "modular PAPER skill chain", event, 0.8, "User works through modular PAPER skills and learner profile."))
    if re.search(r"(交给|归 .*负责|减少冗余|不要重复|delegate)", text, re.I):
        items.append(base_candidate("project_rule", "delegate reusable behavior to owner skill", event, 0.85, "User confirmed durable ownership boundaries."))
    return items


def research_candidates(event: dict[str, Any]) -> list[dict[str, Any]]:
    text = event["text"]
    items: list[dict[str, Any]] = []
    for hint in RESEARCH_HINTS:
        if hint.lower() in text.lower():
            label = hint if re.search(r"[A-Za-z]", hint) else f"topic: {hint}"
            items.append(base_candidate("research_interest", label, event, 0.55, "Topic appears in user conversation."))
    return items[:8]


def concept_candidates(event: dict[str, Any]) -> list[dict[str, Any]]:
    status = detect_status(event["text"])
    if not status:
        return []
    terms = extract_terms(event["text"])
    if not terms:
        return []
    confidence = 0.8 if event.get("role") == "user" else 0.45
    return [base_candidate("concept_status", term, event, confidence, f"Conversation signal suggests concept status: {status}.", status=status) for term in terms]


def cmd_extract(args: argparse.Namespace) -> int:
    events = read_jsonl(Path(args.events).expanduser().resolve())
    bucket: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        role = clean_text(event.get("role"), 80).lower()
        text = clean_text(event.get("text"), 8000)
        if not text:
            continue
        event["text"] = text
        candidates: list[dict[str, Any]] = []
        if role in {"user", "unknown"}:
            candidates.extend(preference_candidates(event))
            candidates.extend(workflow_candidates(event))
            candidates.extend(concept_candidates(event))
            candidates.extend(research_candidates(event))
        else:
            # Assistant content is useful for topic exposure only, not mastery.
            candidates.extend(research_candidates(event))
        for item in candidates:
            if item["confidence"] >= args.min_confidence:
                add_candidate(bucket, item)
    output = {
        "candidate_version": 1,
        "generated_from": "init-knowledge-profile",
        "generated_at": utc_now(),
        "events_scanned": len(events),
        "items": sorted(bucket.values(), key=lambda row: (row["type"], row["label"].lower())),
    }
    write_json(Path(args.output).expanduser().resolve(), output)
    print(f"Wrote {Path(args.output).expanduser().resolve()}")
    print(f"Candidates: {len(output['items'])}")
    return 0


def load_profile(path: Path) -> dict[str, Any]:
    return read_json(path)


def load_source_lookup(events_path: Path | None, candidates: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    if events_path and events_path.exists():
        for event in read_jsonl(events_path):
            lookup[event["event_id"]] = event
    return lookup


def candidate_to_feedback_item(candidate: dict[str, Any], event_lookup: dict[str, dict[str, Any]]) -> dict[str, Any]:
    event_id = (candidate.get("evidence_event_ids") or [""])[0]
    event = event_lookup.get(event_id, {})
    return {
        "feedback_id": candidate.get("candidate_id", ""),
        "concept": candidate.get("label", ""),
        "status": candidate.get("status", "unrated"),
        "annotation_kind": "chat_profile_candidate",
        "confusion_type": "term_definition" if candidate.get("status") in {"unknown", "learning"} else "",
        "explanation_style": "paper_context",
        "user_question": "" if candidate.get("status") not in {"unknown", "learning"} else candidate.get("note", ""),
        "note": "; ".join(candidate.get("notes") or [candidate.get("note", "")]),
        "selected_text": "",
        "selected_language": "chat_session",
        "source_excerpt": clean_text(event.get("text"), 2200),
        "original_context": clean_text(event.get("text"), 2200),
        "translation_context": "",
        "block_id": event_id,
        "source_title": event.get("source_title", ""),
        "source_url": "",
        "category": "chat_session",
        "source_kind": "chat_session",
        "needs_explanation": candidate.get("status") in {"unknown", "learning"},
        "action": "init_knowledge_profile_candidate",
    }


def cmd_propose(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile).expanduser().resolve()
    profile = load_profile(profile_path)
    candidates = read_json(Path(args.candidates).expanduser().resolve())
    events_path = Path(args.events).expanduser().resolve() if args.events else Path(args.candidates).expanduser().resolve().parent / "events.jsonl"
    event_lookup = load_source_lookup(events_path, candidates)
    operations: list[dict[str, Any]] = []
    feedback_items: list[dict[str, Any]] = []

    person_profile = profile.get("person_profile", {}) if isinstance(profile.get("person_profile"), dict) else {}
    for item in candidates.get("items", []):
        kind = item.get("type")
        if kind == "concept_status":
            feedback_items.append(candidate_to_feedback_item(item, event_lookup))
            continue
        section = {
            "learning_preference": "learning_preferences",
            "research_interest": "research_interests",
            "workflow_preference": "workflow_preferences",
            "project_rule": "project_rules",
            "writing_style": "writing_style",
        }.get(kind)
        if not section:
            continue
        key = slugify(item.get("label", ""), "signal")
        exists = key in (person_profile.get(section, {}) if isinstance(person_profile.get(section), dict) else {})
        operations.append({
            "op": "upsert_person_profile_signal",
            "section": section,
            "key": key,
            "exists": exists,
            "value": {
                "label": item.get("label", ""),
                "confidence": item.get("confidence", 0),
                "evidence_event_ids": item.get("evidence_event_ids", []),
                "source_ids": item.get("source_ids", []),
                "notes": item.get("notes") or [item.get("note", "")],
            },
        })

    patch = {
        "patch_version": 1,
        "generated_from": "init-knowledge-profile",
        "generated_at": utc_now(),
        "profile_path": str(profile_path),
        "review_required": True,
        "operations": operations,
        "reader_feedback_handoff": {
            "reader_feedback_version": 2,
            "paper_title": "Imported GPT conversation profile signals",
            "reader_path": str(events_path.parent),
            "source_kind": "chat_session",
            "generated_from": "init-knowledge-profile",
            "items": feedback_items,
        },
    }
    write_json(Path(args.output).expanduser().resolve(), patch)
    print(f"Wrote {Path(args.output).expanduser().resolve()}")
    print(f"Person-profile operations: {len(operations)}")
    print(f"Concept feedback handoff items: {len(feedback_items)}")
    return 0


def import_concept_feedback(profile: dict[str, Any], feedback: dict[str, Any], project_root: Path) -> tuple[dict[str, Any], int]:
    scripts_dir = project_root / "skills" / "reader-learner" / "scripts"
    sys.path.insert(0, str(scripts_dir))
    from profile_v2 import import_feedback  # type: ignore

    return import_feedback(profile, feedback)


def apply_person_operation(profile: dict[str, Any], operation: dict[str, Any]) -> None:
    person = profile.setdefault("person_profile", {})
    section = clean_text(operation.get("section"), 80)
    key = clean_text(operation.get("key"), 120)
    value = operation.get("value") if isinstance(operation.get("value"), dict) else {}
    if not section or not key:
        return
    bucket = person.setdefault(section, {})
    now = utc_now()
    entry = bucket.setdefault(key, {
        "label": value.get("label", key),
        "confidence": 0.0,
        "evidence_event_ids": [],
        "source_ids": [],
        "first_seen_at": now,
        "last_seen_at": now,
        "notes": [],
    })
    entry["label"] = entry.get("label") or value.get("label", key)
    entry["confidence"] = max(float(entry.get("confidence") or 0), float(value.get("confidence") or 0))
    for field in ("evidence_event_ids", "source_ids", "notes"):
        values = entry.setdefault(field, [])
        for row in value.get(field, []) or []:
            if row and row not in values:
                values.append(row)
    entry["last_seen_at"] = now


def cmd_apply(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile).expanduser().resolve()
    patch_path = Path(args.patch).expanduser().resolve()
    project_root = Path(args.project_root).expanduser().resolve() if args.project_root else profile_path.parents[2]
    profile = load_profile(profile_path)
    patch = read_json(patch_path)
    if args.backup:
        backup = profile_path.with_name(profile_path.stem + "." + datetime.now().strftime("%Y%m%d-%H%M%S") + profile_path.suffix + ".bak")
        shutil.copy2(profile_path, backup)
        print(f"Backup: {backup}")

    feedback = patch.get("reader_feedback_handoff") if isinstance(patch.get("reader_feedback_handoff"), dict) else {}
    changed = 0
    if feedback.get("items"):
        profile, changed = import_concept_feedback(profile, feedback, project_root)

    applied_person = 0
    for operation in patch.get("operations", []) or []:
        if isinstance(operation, dict) and operation.get("op") == "upsert_person_profile_signal":
            apply_person_operation(profile, operation)
            applied_person += 1
    profile["updated_at"] = utc_now()
    write_json(profile_path, profile)
    print(f"Profile: {profile_path}")
    print(f"Concept feedback items imported: {changed}")
    print(f"Person-profile operations applied: {applied_person}")
    return 0


def default_import_dir(project_root: Path) -> Path:
    return project_root / ".agents" / "reader-learner" / "imports" / "chat_sessions"


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    collect = sub.add_parser("collect", help="Collect local chat exports into sources.jsonl and events.jsonl.")
    collect.add_argument("--input", action="append", required=True, help="Local chat export file or folder. Repeat for multiple inputs.")
    collect.add_argument("--output", required=True, help="Output import directory.")
    collect.add_argument("--max-event-chars", type=int, default=3000, help="Maximum stored text per evidence event.")
    collect.set_defaults(func=cmd_collect)

    extract = sub.add_parser("extract", help="Extract reviewable profile candidates from events.jsonl.")
    extract.add_argument("--events", required=True, help="Path to events.jsonl.")
    extract.add_argument("--output", required=True, help="Output profile_candidates.json.")
    extract.add_argument("--min-confidence", type=float, default=0.5, help="Minimum candidate confidence to keep.")
    extract.set_defaults(func=cmd_extract)

    propose = sub.add_parser("propose", help="Build a reviewable profile patch.")
    propose.add_argument("--profile", required=True, help="Existing knowledge_profile.json.")
    propose.add_argument("--candidates", required=True, help="profile_candidates.json.")
    propose.add_argument("--events", help="events.jsonl. Defaults to the candidates directory.")
    propose.add_argument("--output", required=True, help="Output profile_patch.json.")
    propose.set_defaults(func=cmd_propose)

    apply = sub.add_parser("apply", help="Apply a reviewed profile patch.")
    apply.add_argument("--profile", required=True, help="Existing knowledge_profile.json.")
    apply.add_argument("--patch", required=True, help="Reviewed profile_patch.json.")
    apply.add_argument("--project-root", help="Project root. Defaults to the PAPER root inferred from profile path.")
    apply.add_argument("--backup", action="store_true", help="Write a timestamped backup before mutating profile.")
    apply.set_defaults(func=cmd_apply)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
