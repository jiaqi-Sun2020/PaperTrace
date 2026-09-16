#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical contract shared by the daily briefing pipeline and its exports."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit


VALID_STATUSES = {"mastered", "known", "learning", "unknown", "unrated"}
VALID_NOVELTY = {"new", "material_update", "continuing", "duplicate"}
VALID_STORY_GROUNDING = {"learner_profile", "briefing_items"}
VALID_WORKED_EXAMPLE_KINDS = {
    "mathematical",
    "numerical",
    "operational",
    "causal",
    "experimental",
    "comparative",
}
OPENING_STORY_FIELDS = (
    "title",
    "concept_name",
    "concept_definition",
    "logic_chain",
    "analogy_boundary",
    "misleading_risk",
    "grounding_kind",
)
TEXT_FIELDS = (
    "briefing_title",
    "date_range",
    "summary",
    "title",
    "category",
    "facts",
    "new_facts",
    "judgment",
    "relevance",
    "source_title",
    "source_excerpt",
    "evidence_level",
    "venue_sweep_note",
)


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def assert_lossless_text(value: Any, field: str) -> None:
    """Reject text that already lost Unicode before the UTF-8 writer saw it."""
    if value is None:
        return
    text = str(value)
    if "\ufffd" in text:
        raise ValueError(f"{field} contains the Unicode replacement character; preserve the original UTF-8 text")
    question_marks = text.count("?")
    if question_marks < 3:
        return
    density = question_marks / max(len(text), 1)
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in text)
    if density >= 0.20 or (not has_cjk and density >= 0.08):
        sample = text[:120].replace("\n", " ")
        raise ValueError(
            f"{field} appears encoding-corrupted: {question_marks} literal '?' characters in {len(text)} chars; "
            f"repair the UTF-8 input before rendering ({sample!r})"
        )


def is_lossless_text(value: Any) -> bool:
    try:
        assert_lossless_text(value, "text")
    except ValueError:
        return False
    return True


def assert_config_text_integrity(config: dict[str, Any]) -> None:
    assert_lossless_text(config.get("briefing_title"), "briefing_title")
    assert_lossless_text(config.get("date_range"), "date_range")
    assert_lossless_text(config.get("summary"), "summary")
    opening_story = config.get("opening_story")
    if opening_story is not None:
        if not isinstance(opening_story, dict):
            raise ValueError("opening_story must be an object")
        for field in OPENING_STORY_FIELDS:
            assert_lossless_text(opening_story.get(field), f"opening_story.{field}")
        for field in ("paragraphs", "concept_aliases", "source_story_ids"):
            values = opening_story.get(field) or []
            if not isinstance(values, list):
                raise ValueError(f"opening_story.{field} must be a list")
            for index, value in enumerate(values, start=1):
                assert_lossless_text(value, f"opening_story.{field}[{index}]")
        worked_example = opening_story.get("worked_example")
        if worked_example is not None:
            if not isinstance(worked_example, dict):
                raise ValueError("opening_story.worked_example must be an object")
            for field in ("kind", "title", "question", "result", "interpretation", "non_conclusion"):
                assert_lossless_text(
                    worked_example.get(field),
                    f"opening_story.worked_example.{field}",
                )
            for field in ("assumptions", "checks"):
                values = worked_example.get(field) or []
                if not isinstance(values, list):
                    raise ValueError(f"opening_story.worked_example.{field} must be a list")
                for index, value in enumerate(values, start=1):
                    assert_lossless_text(
                        value,
                        f"opening_story.worked_example.{field}[{index}]",
                    )
            for field, record_fields in (
                ("objects", ("name", "kind", "role", "units")),
                ("steps", ("action", "formula", "rule", "explanation")),
            ):
                values = worked_example.get(field) or []
                if not isinstance(values, list):
                    raise ValueError(f"opening_story.worked_example.{field} must be a list")
                for index, value in enumerate(values, start=1):
                    if not isinstance(value, dict):
                        raise ValueError(
                            f"opening_story.worked_example.{field}[{index}] must be an object"
                        )
                    for record_field in record_fields:
                        assert_lossless_text(
                            value.get(record_field),
                            f"opening_story.worked_example.{field}[{index}].{record_field}",
                        )
    sections = config.get("sections") or []
    if not isinstance(sections, list):
        return
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        assert_lossless_text(section.get("title"), f"sections[{section_index}].title")
        items = section.get("items") or []
        if not isinstance(items, list):
            continue
        for item_index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue
            for field in TEXT_FIELDS[3:]:
                assert_lossless_text(item.get(field), f"sections[{section_index}].items[{item_index}].{field}")
            concepts = item.get("concepts") or []
            if isinstance(concepts, list):
                for concept_index, concept in enumerate(concepts, start=1):
                    assert_lossless_text(
                        concept,
                        f"sections[{section_index}].items[{item_index}].concepts[{concept_index}]",
                    )


def canonical_url(value: Any) -> str:
    url = clean_text(value, 1600)
    if not url:
        return ""
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError(f"source_url must be an absolute https URL: {url[:160]}")
    if parsed.username or parsed.password:
        raise ValueError("source_url must not contain credentials")
    if any(ord(ch) < 32 for ch in url):
        raise ValueError("source_url contains control characters")
    path = re.sub(r"/+", "/", parsed.path).rstrip("/") or "/"
    return urlunsplit(("https", parsed.netloc.lower(), path, "", ""))


def normalize_concepts(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        concept = clean_text(value, 240)
        key = concept.casefold()
        if concept and key not in seen:
            result.append(concept)
            seen.add(key)
    return result


def normalize_text_list(values: Any, *, limit: int, field: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{field} must be a list")
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_text(value, limit)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def normalize_worked_example(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("opening_story.worked_example must be an object")
    if not value:
        return {}

    raw_objects = value.get("objects") or []
    if not isinstance(raw_objects, list):
        raise ValueError("opening_story.worked_example.objects must be a list")
    objects: list[dict[str, str]] = []
    for index, item in enumerate(raw_objects, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"opening_story.worked_example.objects[{index}] must be an object")
        objects.append(
            {
                "name": clean_text(item.get("name"), 240),
                "kind": clean_text(item.get("kind"), 240),
                "role": clean_text(item.get("role"), 800),
                "units": clean_text(item.get("units"), 160),
            }
        )

    raw_steps = value.get("steps") or []
    if not isinstance(raw_steps, list):
        raise ValueError("opening_story.worked_example.steps must be a list")
    steps: list[dict[str, str]] = []
    for index, item in enumerate(raw_steps, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"opening_story.worked_example.steps[{index}] must be an object")
        steps.append(
            {
                "action": clean_text(item.get("action"), 1200),
                "formula": clean_text(item.get("formula"), 1600),
                "rule": clean_text(item.get("rule"), 600),
                "explanation": clean_text(item.get("explanation"), 1600),
            }
        )

    return {
        "kind": clean_text(value.get("kind"), 80),
        "title": clean_text(value.get("title") or "完整例子", 200),
        "question": clean_text(value.get("question"), 1200),
        "assumptions": normalize_text_list(
            value.get("assumptions"),
            limit=1000,
            field="opening_story.worked_example.assumptions",
        ),
        "objects": objects,
        "steps": steps,
        "result": clean_text(value.get("result"), 1600),
        "interpretation": clean_text(value.get("interpretation"), 1600),
        "checks": normalize_text_list(
            value.get("checks"),
            limit=1200,
            field="opening_story.worked_example.checks",
        ),
        "non_conclusion": clean_text(value.get("non_conclusion"), 1600),
    }


def assert_worked_example_contract(example: dict[str, Any], *, required: bool) -> None:
    if not example:
        if required:
            raise ValueError("daily briefing opening_story requires worked_example")
        return

    kind = clean_text(example.get("kind"), 80)
    if kind not in VALID_WORKED_EXAMPLE_KINDS:
        raise ValueError(
            "opening_story.worked_example.kind must be mathematical, numerical, "
            "operational, causal, experimental, or comparative"
        )
    required_fields = ("title", "question", "result", "interpretation", "non_conclusion")
    missing = [field for field in required_fields if not clean_text(example.get(field))]
    if missing:
        raise ValueError(
            "opening_story.worked_example missing required fields: " + ", ".join(missing)
        )
    for field in ("assumptions", "objects", "steps", "checks"):
        values = example.get(field)
        if not isinstance(values, list) or not values:
            raise ValueError(f"opening_story.worked_example.{field} must be a non-empty list")

    for index, item in enumerate(example["objects"], start=1):
        missing_object_fields = [
            field for field in ("name", "kind", "role") if not clean_text(item.get(field))
        ]
        if missing_object_fields:
            raise ValueError(
                f"opening_story.worked_example.objects[{index}] missing required fields: "
                + ", ".join(missing_object_fields)
            )

    has_formula = False
    for index, item in enumerate(example["steps"], start=1):
        action = clean_text(item.get("action"))
        formula = clean_text(item.get("formula"))
        if not action and not formula:
            raise ValueError(
                f"opening_story.worked_example.steps[{index}] requires action or formula"
            )
        for field in ("rule", "explanation"):
            if not clean_text(item.get(field)):
                raise ValueError(
                    f"opening_story.worked_example.steps[{index}] missing required field: {field}"
                )
        has_formula = has_formula or bool(formula)

    if kind == "mathematical" and not has_formula:
        raise ValueError(
            "opening_story.worked_example.kind mathematical requires at least one formula step; "
            "the authoring contract forbids fabricated formulas"
        )


def normalize_opening_story(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("opening_story must be an object")
    if not value:
        return {}
    worked_example = normalize_worked_example(value.get("worked_example"))
    return {
        "version": 2 if worked_example else 1,
        "title": clean_text(value.get("title") or "开篇寓言", 160),
        "paragraphs": normalize_text_list(
            value.get("paragraphs"), limit=900, field="opening_story.paragraphs"
        ),
        "concept_name": clean_text(value.get("concept_name"), 240),
        "concept_aliases": normalize_text_list(
            value.get("concept_aliases"), limit=120, field="opening_story.concept_aliases"
        ),
        "concept_definition": clean_text(value.get("concept_definition"), 800),
        "logic_chain": clean_text(value.get("logic_chain"), 800),
        "analogy_boundary": clean_text(value.get("analogy_boundary"), 800),
        "misleading_risk": clean_text(value.get("misleading_risk"), 800),
        "worked_example": worked_example,
        "grounding_kind": clean_text(value.get("grounding_kind"), 80),
        "source_story_ids": normalize_text_list(
            value.get("source_story_ids"), limit=180, field="opening_story.source_story_ids"
        ),
    }


def assert_opening_story_contract(
    story: dict[str, Any],
    *,
    required: bool,
    worked_example_required: bool = False,
    available_story_ids: set[str] | None = None,
) -> None:
    if not story:
        if required:
            raise ValueError("daily briefing requires opening_story before the briefing body")
        return
    required_fields = (
        "title",
        "concept_name",
        "concept_definition",
        "logic_chain",
        "analogy_boundary",
        "misleading_risk",
        "grounding_kind",
    )
    missing = [field for field in required_fields if not clean_text(story.get(field))]
    if missing:
        raise ValueError("opening_story missing required fields: " + ", ".join(missing))
    paragraphs = story.get("paragraphs") or []
    if not isinstance(paragraphs, list) or not (2 <= len(paragraphs) <= 6):
        raise ValueError("opening_story.paragraphs must contain 2-6 story paragraphs")
    story_text = " ".join(clean_text(paragraph, 900) for paragraph in paragraphs)
    if len(story_text) < 120:
        raise ValueError("opening_story must contain at least 120 characters of narrative")
    hidden_terms = [story.get("concept_name"), *(story.get("concept_aliases") or [])]
    concealed_text = f"{clean_text(story.get('title'))} {story_text}".casefold()
    leaked = [
        clean_text(term, 240)
        for term in hidden_terms
        if len(clean_text(term, 240)) >= 2
        and clean_text(term, 240).casefold() in concealed_text
    ]
    if leaked:
        raise ValueError("opening_story reveals the concept before the factual debrief: " + ", ".join(leaked))
    assert_worked_example_contract(
        story.get("worked_example") or {},
        required=worked_example_required,
    )
    grounding_kind = clean_text(story.get("grounding_kind"), 80)
    if grounding_kind not in VALID_STORY_GROUNDING:
        raise ValueError("opening_story.grounding_kind must be learner_profile or briefing_items")
    source_story_ids = set(story.get("source_story_ids") or [])
    if grounding_kind == "briefing_items" and not source_story_ids:
        raise ValueError("opening_story grounded in briefing_items requires source_story_ids")
    if available_story_ids is not None:
        missing_ids = sorted(source_story_ids - available_story_ids)
        if missing_ids:
            raise ValueError("opening_story references unpublished story IDs: " + ", ".join(missing_ids))


def story_id_for_item(item: dict[str, Any]) -> str:
    explicit = clean_text(item.get("story_id"), 180)
    if explicit:
        basis = explicit
    else:
        url = canonical_url(item.get("source_url")) if item.get("source_url") else ""
        if url:
            parsed = urlsplit(url)
            basis = f"{parsed.netloc.lower()} {parsed.path.strip('/')}"
        else:
            basis = " ".join(
                part
                for part in (
                    clean_text(item.get("source_title"), 300),
                    clean_text(item.get("title"), 300),
                    clean_text(item.get("category"), 120),
                    " ".join(normalize_concepts(item.get("concepts"))[:4]),
                )
                if part
            )
    slug = re.sub(r"[^a-z0-9]+", "-", basis.lower()).strip("-")
    if len(slug) >= 3:
        return slug[:100]
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]
    return f"story-{digest}"


def concept_identity(block_id: str, concept: str) -> str:
    return f"{clean_text(block_id, 300)}::{clean_text(concept, 240).casefold()}"


def feedback_id(block_id: str, concept: str) -> str:
    return f"news::{clean_text(concept, 240)}::{clean_text(block_id, 300)}"


def iter_sections(config: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    sections = config.get("sections")
    if not isinstance(sections, list):
        raise ValueError("config.sections must be a list")
    if config.get("items"):
        raise ValueError("config must not contain top-level items together with sections")
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            raise ValueError(f"section {section_index} must be an object")
        title = clean_text(section.get("title") or f"Section {section_index}", 200)
        items = section.get("items") or []
        if not isinstance(items, list):
            raise ValueError(f"section {title} items must be a list")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"section {title} contains a non-object item")
            yield title, item


def normalize_briefing_config(
    config: dict[str, Any],
    config_path: Path | None = None,
    *,
    require_source_url: bool = True,
) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("briefing config must be an object")
    if "sections" not in config:
        top_items = config.get("items")
        if isinstance(top_items, list):
            config = dict(config)
            config["sections"] = [{"title": "Briefing", "items": top_items}]
            config.pop("items", None)
        else:
            raise ValueError("briefing config requires sections")
    assert_config_text_integrity(config)
    title = clean_text(config.get("briefing_title") or config.get("title") or "AI + Quantum News Briefing", 500)
    date_range = clean_text(config.get("date_range") or config.get("date"), 240)
    raw_story_delivery = config.get("story_delivery") or {}
    if not isinstance(raw_story_delivery, dict):
        raise ValueError("story_delivery must be an object")
    if "required" in raw_story_delivery and not isinstance(raw_story_delivery.get("required"), bool):
        raise ValueError("story_delivery.required must be a boolean")
    if "worked_example_required" in raw_story_delivery and not isinstance(
        raw_story_delivery.get("worked_example_required"), bool
    ):
        raise ValueError("story_delivery.worked_example_required must be a boolean")
    story_delivery = {
        "required": raw_story_delivery.get("required") is True,
        "worked_example_required": raw_story_delivery.get("worked_example_required") is True,
        "position": clean_text(raw_story_delivery.get("position") or "before_briefing", 80),
    }
    if story_delivery["position"] != "before_briefing":
        raise ValueError("story_delivery.position must be before_briefing")
    opening_story = normalize_opening_story(config.get("opening_story"))
    normalized_sections: list[dict[str, Any]] = []
    all_ids: set[str] = set()
    for section_title, raw_item in iter_sections(config):
        if not normalized_sections or normalized_sections[-1]["title"] != section_title:
            normalized_sections.append({"title": section_title, "items": []})
        item_id = clean_text(raw_item.get("id"), 300)
        if not item_id:
            item_id = f"N{sum(len(section['items']) for section in normalized_sections) + 1:03d}"
        if item_id in all_ids:
            raise ValueError(f"duplicate item id: {item_id}")
        source_url = clean_text(raw_item.get("source_url"), 1600)
        if require_source_url:
            source_url = canonical_url(source_url)
        elif source_url:
            source_url = canonical_url(source_url)
        concepts = normalize_concepts(raw_item.get("concepts"))
        item = {
            "id": item_id,
            "story_id": story_id_for_item({**raw_item, "source_url": source_url}),
            "novelty": clean_text(raw_item.get("novelty") or raw_item.get("delta_status"), 80),
            "novelty_claim": clean_text(raw_item.get("novelty_claim") or raw_item.get("novelty"), 80),
            "delta_note": clean_text(raw_item.get("delta_note"), 600),
            "title": clean_text(raw_item.get("title") or raw_item.get("concept") or f"News item {item_id}", 500),
            "category": clean_text(raw_item.get("category") or section_title, 300),
            "facts": clean_text(raw_item.get("facts") or raw_item.get("fact") or raw_item.get("summary"), 4000),
            "new_facts": clean_text(raw_item.get("new_facts") or raw_item.get("update_summary"), 2000),
            "judgment": clean_text(raw_item.get("judgment") or raw_item.get("analysis"), 3000),
            "relevance": clean_text(raw_item.get("relevance") or raw_item.get("research_relevance"), 1800),
            "source_title": clean_text(raw_item.get("source_title") or raw_item.get("title"), 600),
            "source_url": source_url,
            "source_excerpt": clean_text(raw_item.get("source_excerpt") or raw_item.get("facts") or raw_item.get("summary"), 2000),
            "evidence_level": clean_text(raw_item.get("evidence_level"), 200),
            "evidence_fingerprint": clean_text(raw_item.get("evidence_fingerprint") or raw_item.get("source_fingerprint"), 200),
            "published_at": clean_text(raw_item.get("published_at") or raw_item.get("publishedAt"), 100),
            "verified_at": clean_text(raw_item.get("verified_at"), 100),
            "venue_sweep_note": clean_text(raw_item.get("venue_sweep_note"), 1000),
            "source_class": clean_text(raw_item.get("source_class"), 120),
            "organization": clean_text(raw_item.get("organization"), 200),
            "topic": clean_text(raw_item.get("topic"), 200),
            "corroborating_source_count": raw_item.get("corroborating_source_count", 0),
            "ranking_signals": raw_item.get("ranking_signals") if isinstance(raw_item.get("ranking_signals"), dict) else {},
            "ranking": raw_item.get("ranking") if isinstance(raw_item.get("ranking"), dict) else {},
            "concepts": concepts,
        }
        all_ids.add(item_id)
        normalized_sections[-1]["items"].append(item)
    normalized = {
        "news_feedback_version": 1,
        "briefing_title": title,
        "date_range": date_range,
        "briefing_path": clean_text(config.get("briefing_path") or str(config_path or ""), 1200),
        "summary": clean_text(config.get("summary"), 1600),
        "story_delivery": story_delivery,
        "opening_story": opening_story,
        "sections": normalized_sections,
        "academic_search": config.get("academic_search") or config.get("academic_venue_sweep") or {},
        "academic_delivery": config.get("academic_delivery") or {},
        "delta_policy": config.get("delta_policy") or {},
        "social_delivery": config.get("social_delivery") or {},
        "social_candidate_pool": config.get("social_candidate_pool") or {},
        "ranking_policy": config.get("ranking_policy") or {},
        "ranking_manifest": config.get("ranking_manifest") or {},
        "analysis_language": clean_text(config.get("analysis_language"), 40),
        "profile_path": clean_text(config.get("profile_path"), 1200),
    }
    published_story_ids = {
        item["story_id"]
        for section in normalized_sections
        for item in section["items"]
        if item.get("story_id")
    }
    assert_opening_story_contract(
        opening_story,
        required=story_delivery["required"],
        worked_example_required=story_delivery["worked_example_required"],
        available_story_ids=published_story_ids,
    )
    normalized["config_fingerprint"] = config_fingerprint(normalized)
    return normalized


def config_fingerprint(config: dict[str, Any]) -> str:
    payload = {key: value for key, value in config.items() if key not in {"generated_at", "config_fingerprint", "run_fingerprint"}}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def contract_concept_set(config: dict[str, Any]) -> set[str]:
    canonical = normalize_briefing_config(config, require_source_url=False)
    return {
        concept_identity(item["id"], concept)
        for section in canonical["sections"]
        for item in section["items"]
        for concept in item["concepts"]
    }
