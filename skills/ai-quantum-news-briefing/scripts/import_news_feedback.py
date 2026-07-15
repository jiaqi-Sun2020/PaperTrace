#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Import AI+quantum news feedback into the shared learner profile.

This script normalizes news-briefing feedback into the reader-learner feedback
shape, then delegates profile mutation to skills/reader-learner.
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
from typing import Any, Iterable


VALID_STATUSES = {"mastered", "known", "learning", "unknown", "unrated"}
DEFAULT_NEWS_STATUS = "unrated"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def valid_status(value: Any, default: str = DEFAULT_NEWS_STATUS) -> str:
    status = clean_text(value, 80).lower()
    return status if status in VALID_STATUSES else default


def find_project_root(start: Path) -> Path:
    resolved = start.resolve()
    for parent in [resolved, *resolved.parents]:
        if (parent / ".agents").exists() and (parent / "skills").exists():
            return parent
    # scripts/import_news_feedback.py -> scripts -> skill -> skills -> project
    return Path(__file__).resolve().parents[3]


def find_profile(project_root: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidate = project_root / ".agents" / "reader-learner" / "knowledge_profile.json"
    if not candidate.exists():
        raise FileNotFoundError(f"Could not find learner profile: {candidate}")
    return candidate


def find_importer(project_root: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidate = project_root / "skills" / "reader-learner" / "scripts" / "import_reader_feedback.py"
    if not candidate.exists():
        raise FileNotFoundError(f"Could not find reader-learner importer: {candidate}")
    return candidate


def source_excerpt(item: dict[str, Any]) -> str:
    parts: list[str] = []
    title = clean_text(item.get("source_title"), 500)
    url = clean_text(item.get("source_url"), 1000)
    category = clean_text(item.get("category"), 200)
    excerpt = clean_text(item.get("source_excerpt") or item.get("excerpt") or item.get("note"), 2400)
    if category:
        parts.append(f"Category: {category}")
    if title:
        parts.append(f"Source title: {title}")
    if url:
        parts.append(f"Source URL: {url}")
    if excerpt:
        parts.append(f"Context: {excerpt}")
    return "\n".join(parts)


def handoff_concept_id(concept: str) -> str:
    """Provide the strict handoff field without pretending news has reader-bundle IDs."""
    slug = re.sub(r"[^a-z0-9]+", "-", concept.casefold()).strip("-")
    if re.search(r"[a-z]", slug):
        return slug[:120]
    return "news-" + hashlib.sha1(concept.encode("utf-8")).hexdigest()[:12]


def normalize_item(item: dict[str, Any], index: int, source_label: str, date_range: str) -> dict[str, Any]:
    concept = clean_text(item.get("concept") or item.get("term") or item.get("topic"), 600)
    if not concept:
        raise ValueError(f"Item {index} is missing concept/term/topic")
    category = clean_text(item.get("category"), 200)
    block_id = clean_text(item.get("block_id") or category or f"news-{index:03d}", 180)
    feedback_id = clean_text(item.get("feedback_id"), 500)
    if not feedback_id:
        feedback_id = f"news::{concept}::{date_range or source_label or index}"
    excerpt = source_excerpt(item)
    question = clean_text(item.get("user_question") or item.get("question"), 1600)
    status = valid_status(item.get("status"))
    needs_explanation = bool(item.get("needs_explanation") or question or status in {"unknown", "learning"})
    annotation_kind = clean_text(item.get("annotation_kind") or "concept", 120)
    if annotation_kind == "news_concept":
        annotation_kind = "concept"
    return {
        "feedback_id": feedback_id,
        "concept": concept,
        "concept_id": handoff_concept_id(concept),
        "concept_type": clean_text(item.get("concept_type") or "term", 80),
        "status": status,
        "note": clean_text(item.get("note"), 1600),
        "user_question": question,
        "confusion_type": clean_text(item.get("confusion_type") or item.get("question_type"), 200),
        "explanation_style": clean_text(item.get("explanation_style"), 200),
        "needs_explanation": needs_explanation,
        "block_id": block_id,
        "source_anchor": f"news-{index:03d}",
        "annotation_kind": annotation_kind,
        "source_excerpt": excerpt,
        "selected_text": clean_text(item.get("selected_text") or concept, 1600),
        "selected_language": clean_text(item.get("selected_language") or "news", 80),
        "bilingual_block_id": "",
        "original_context": clean_text(item.get("original_context") or excerpt, 2200),
        "translation_context": clean_text(item.get("translation_context"), 2200),
        "translation": clean_text(item.get("translation"), 300),
        "action": clean_text(item.get("action") or "news_feedback", 120),
        "source_kind": "news_briefing",
        "source_title": clean_text(item.get("source_title"), 500),
        "source_url": clean_text(item.get("source_url"), 1000),
        "category": category,
    }


def normalize_feedback(news_feedback: dict[str, Any], feedback_path: Path) -> dict[str, Any]:
    items = news_feedback.get("items", [])
    if not isinstance(items, list):
        raise ValueError("news_feedback.items must be a list")
    title = clean_text(
        news_feedback.get("briefing_title")
        or news_feedback.get("title")
        or news_feedback.get("paper_title")
        or "AI + Quantum News Briefing",
        500,
    )
    date_range = clean_text(news_feedback.get("date_range") or news_feedback.get("date") or "", 120)
    briefing_path = clean_text(news_feedback.get("briefing_path") or news_feedback.get("reader_path") or str(feedback_path), 1000)
    normalized_items = [
        normalize_item(item, index, title, date_range)
        for index, item in enumerate(items, start=1)
        if isinstance(item, dict)
    ]
    return {
        "reader_feedback_version": 2,
        "source_kind": "news_briefing",
        "paper_title": title,
        "reader_path": briefing_path,
        "briefing_title": title,
        "date_range": date_range,
        "created_at": utc_now(),
        "items": normalized_items,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feedback", required=True, help="Path to news_feedback.json.")
    parser.add_argument("--profile", help="Path to .agents/reader-learner/knowledge_profile.json.")
    parser.add_argument("--reader-learner-importer", help="Path to reader-learner import_reader_feedback.py.")
    parser.add_argument("--normalized-output", help="Where to write the normalized reader-feedback JSON.")
    parser.add_argument("--no-import", action="store_true", help="Only write normalized output; do not update the profile.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    feedback_path = Path(args.feedback).expanduser().resolve()
    project_root = find_project_root(feedback_path.parent)
    profile_path = find_profile(project_root, args.profile)
    importer_path = find_importer(project_root, args.reader_learner_importer)
    news_feedback = load_json(feedback_path)
    normalized = normalize_feedback(news_feedback, feedback_path)
    output_path = (
        Path(args.normalized_output).expanduser().resolve()
        if args.normalized_output
        else feedback_path.with_name(feedback_path.stem + "_reader_feedback.json")
    )
    write_json(output_path, normalized)
    print(f"Wrote normalized feedback: {output_path}", flush=True)
    print(f"Items: {len(normalized['items'])}", flush=True)
    if args.no_import:
        print("Profile import skipped (--no-import).")
        return 0
    command = [
        sys.executable,
        str(importer_path),
        "--profile",
        str(profile_path),
        "--feedback",
        str(output_path),
    ]
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode
    print(f"Profile updated: {profile_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
