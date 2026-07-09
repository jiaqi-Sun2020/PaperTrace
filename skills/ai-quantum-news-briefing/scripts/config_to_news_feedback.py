#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Export all concepts from a news briefing config to news_feedback.json."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_STATUSES = {"mastered", "known", "learning", "unknown", "unrated"}
DEFAULT_STATUS = "unrated"


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def status_or_default(value: str) -> str:
    normalized = clean_text(value, 80).lower()
    return normalized if normalized in VALID_STATUSES else DEFAULT_STATUS


def iter_config_items(config: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    sections = config.get("sections") or []
    if not isinstance(sections, list):
        raise ValueError("config.sections must be a list")
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_title = clean_text(section.get("title"), 300)
        items = section.get("items") or []
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict):
                yield section_title, item


def concept_list(item: dict[str, Any]) -> list[str]:
    concepts = item.get("concepts") or []
    if isinstance(concepts, str):
        concepts = [concepts]
    if not isinstance(concepts, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for concept in concepts:
        text = clean_text(concept, 600)
        key = text.casefold()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
    return cleaned


def source_excerpt(section_title: str, item: dict[str, Any]) -> str:
    parts: list[str] = []
    category = clean_text(item.get("category") or section_title, 300)
    item_title = clean_text(item.get("title"), 600)
    facts = clean_text(item.get("facts") or item.get("summary"), 1800)
    judgment = clean_text(item.get("judgment") or item.get("analysis"), 1200)
    source_excerpt_text = clean_text(item.get("source_excerpt"), 1800)
    evidence = clean_text(item.get("evidence_level"), 200)
    if category:
        parts.append(f"Category: {category}")
    if item_title:
        parts.append(f"Item: {item_title}")
    if evidence:
        parts.append(f"Evidence: {evidence}")
    if facts:
        parts.append(f"Facts: {facts}")
    if judgment:
        parts.append(f"Judgment: {judgment}")
    if source_excerpt_text and source_excerpt_text not in facts:
        parts.append(f"Source excerpt: {source_excerpt_text}")
    return "\n".join(parts)


def dedupe_key(mode: str, concept: str, item: dict[str, Any], section_title: str) -> str:
    concept_key = concept.casefold()
    if mode == "none":
        item_id = clean_text(item.get("id") or item.get("story_id") or item.get("source_url") or section_title, 500)
        return f"{concept_key}::{item_id}"
    if mode == "concept":
        return concept_key
    source_key = clean_text(item.get("source_url") or item.get("story_id") or item.get("id") or section_title, 1000)
    return f"{concept_key}::{source_key.casefold()}"


def export_feedback(config: dict[str, Any], config_path: Path, status: str, dedupe: str) -> dict[str, Any]:
    title = clean_text(config.get("briefing_title") or config.get("title") or "AI + Quantum News Briefing", 500)
    date_range = clean_text(config.get("date_range") or config.get("date"), 200)
    briefing_path = clean_text(config.get("briefing_path") or str(config_path), 1000)
    profile_path = clean_text(config.get("profile_path"), 1000)
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    default_status = status_or_default(status)

    for section_title, item in iter_config_items(config):
        category = clean_text(item.get("category") or section_title, 300)
        item_id = clean_text(item.get("id") or item.get("story_id"), 300)
        source_title = clean_text(item.get("source_title") or item.get("title"), 600)
        source_url = clean_text(item.get("source_url"), 1000)
        excerpt = source_excerpt(section_title, item)
        for concept in concept_list(item):
            key = dedupe_key(dedupe, concept, item, section_title)
            if key in seen:
                continue
            seen.add(key)
            feedback_id = f"news::{concept}::{item_id or source_url or date_range or title}"
            items.append(
                {
                    "feedback_id": feedback_id,
                    "concept": concept,
                    "status": default_status,
                    "category": category,
                    "source_title": source_title,
                    "source_url": source_url,
                    "source_excerpt": excerpt,
                    "selected_text": concept,
                    "selected_language": "news",
                    "annotation_kind": "news_concept_auto",
                    "block_id": item_id,
                    "user_question": "",
                    "confusion_type": "",
                    "explanation_style": "",
                    "note": "auto-exported from briefing config; user has not rated this concept",
                    "needs_explanation": False,
                    "action": "news_feedback",
                    "source_kind": "news_briefing",
                }
            )

    return {
        "news_feedback_version": 1,
        "briefing_title": title,
        "date_range": date_range,
        "briefing_path": briefing_path,
        "profile_path": profile_path,
        "exported_at": utc_now(),
        "default_status": default_status,
        "dedupe": dedupe,
        "items": items,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Path to news_feedback_config.json.")
    parser.add_argument("--output", help="Output news_feedback.json. Defaults beside config.")
    parser.add_argument("--status", default=DEFAULT_STATUS, choices=sorted(VALID_STATUSES), help="Default status for exported concepts.")
    parser.add_argument("--dedupe", default="concept-source", choices=["concept", "concept-source", "none"], help="How to deduplicate exported concepts.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else config_path.with_name("news_feedback.json")
    )
    feedback = export_feedback(load_json(config_path), config_path, args.status, args.dedupe)
    write_json(output_path, feedback)
    print(f"Wrote news feedback: {output_path}")
    print(f"Concept items: {len(feedback['items'])}")
    print(f"Default status: {feedback['default_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
