#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial audit for AI+quantum briefing configs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

from briefing_contract import canonical_url, normalize_briefing_config


ACADEMIC_DOMAINS = {
    "arxiv.org": "preprint",
    "journals.aps.org": "aps",
    "aps.org": "aps",
    "nature.com": "nature",
    "science.org": "science",
    "openreview.net": "openreview",
    "thecvf.com": "cvf",
    "proceedings.mlr.press": "pmlr",
    "neurips.cc": "neurips",
    "aclanthology.org": "acl",
    "quantum-journal.org": "quantum-journal",
    "npjqi.springeropen.com": "npj-qi",
}

OFFICIAL_RESEARCH_DOMAINS = {
    "openai.com",
    "anthropic.com",
    "research.google",
    "blog.google",
    "cursor.com",
    "huggingface.co",
    "ibm.com",
}

REQUIRED_ACADEMIC_VENUES = {
    "aps-prl",
    "aps-pra",
    "aps-prx",
    "nature",
    "science",
    "openreview-iclr",
    "cvf-cvpr",
    "pmlr-icml",
    "neurips",
    "acl",
    "quantum-journal",
    "arxiv",
}

VENUE_ALIASES = {
    "openreview": "openreview-iclr",
    "iclr": "openreview-iclr",
    "icla": "openreview-iclr",
    "cvf": "cvf-cvpr",
    "cvpr": "cvf-cvpr",
    "pmlr": "pmlr-icml",
    "icml": "pmlr-icml",
    "aps": "aps-prx",
    "prl": "aps-prl",
    "pra": "aps-pra",
    "prx": "aps-prx",
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def clean_text(value: Any, limit: int = 1000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return data


def iter_items(config: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for section in config.get("sections", []):
        if not isinstance(section, dict):
            continue
        title = clean_text(section.get("title"), 200)
        for item in section.get("items", []) or []:
            if isinstance(item, dict):
                yield title, item


def domain_of(url: str) -> str:
    parsed = urlsplit(clean_text(url, 1000))
    return parsed.netloc.lower().replace("www.", "")


def academic_kind(url: str) -> str:
    domain = domain_of(url)
    for known, kind in ACADEMIC_DOMAINS.items():
        if domain == known or domain.endswith("." + known):
            return kind
    if any(domain == known or domain.endswith("." + known) for known in OFFICIAL_RESEARCH_DOMAINS):
        return "official"
    return ""


def is_academic_item(section: str, item: dict[str, Any]) -> bool:
    text = " ".join(
        [
            section,
            clean_text(item.get("category"), 200),
            clean_text(item.get("evidence_level"), 200),
            clean_text(item.get("source_title"), 300),
            clean_text(item.get("title"), 300),
        ]
    ).lower()
    return any(word in text for word in ["paper", "academic", "research", "quantum", "论文", "研究", "prl", "pra", "nature", "science"])


def normalize_venue(value: Any) -> str:
    venue = clean_text(value, 120).lower()
    return VENUE_ALIASES.get(venue, venue)


def valid_http_evidence(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    required = ("query_url", "retrieved_at", "status_code", "final_url", "response_hash")
    if not all(clean_text(value.get(key), 1200) for key in required):
        return False
    try:
        return 200 <= int(value.get("status_code")) < 400
    except (TypeError, ValueError):
        return False


def academic_search_venues(config: dict[str, Any]) -> tuple[set[str], int, int, list[str]]:
    raw = config.get("academic_search") or config.get("academic_venue_sweep") or {}
    if not isinstance(raw, dict):
        return set(), 0, 0, ["academic_search ledger is missing"]
    venues: set[str] = set()
    # Declared venue lists are policy metadata, never proof that a search ran.
    topics = raw.get("topics") or []
    primary_hits = 0
    checked_topics = 0
    evidence_failures: list[str] = []
    if isinstance(topics, list):
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            checked = {normalize_venue(v) for v in topic.get("checked_venues", []) or []}
            valid_rows = []
            for row in raw.get("rows", []) or []:
                if isinstance(row, dict) and row.get("term") == topic.get("term"):
                    evidence = row.get("evidence")
                    if row.get("result") in {"checked", "hit", "checked_no_hit"} and isinstance(evidence, dict):
                        if valid_http_evidence(evidence):
                            valid_rows.append(row)
                        else:
                            evidence_failures.append(f"{topic.get('term')}/{row.get('venue')}: incomplete HTTP evidence")
                    else:
                        evidence_failures.append(f"{topic.get('term')}/{row.get('venue')}: venue result is not evidenced")
            checked.update(normalize_venue(row.get("venue")) for row in valid_rows)
            venues.update(normalize_venue(row.get("venue")) for row in valid_rows)
            if valid_rows and len(valid_rows) == len([row for row in raw.get("rows", []) or [] if isinstance(row, dict) and row.get("term") == topic.get("term")]):
                checked_topics += 1
            hits = topic.get("primary_hits") or []
            if isinstance(hits, list):
                primary_hits += sum(1 for hit in hits if isinstance(hit, dict) and clean_text(hit.get("url"), 1000))
    rows = raw.get("rows") or []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            result = clean_text(row.get("result"), 80).lower()
            venue = normalize_venue(row.get("venue"))
            evidence = row.get("evidence")
            if result and result != "unchecked" and valid_http_evidence(evidence):
                    venues.add(venue)
            if venue != "arxiv" and clean_text(row.get("url"), 1000):
                primary_hits += 1
    return venues, checked_topics, primary_hits, evidence_failures


def audit_academic_delivery(config: dict[str, Any]) -> list[str]:
    """Enforce the daily academic-delivery contract when it is enabled."""
    delivery = config.get("academic_delivery") or {}
    if not isinstance(delivery, dict):
        return ["academic_delivery must be an object"]
    if not delivery.get("required"):
        if delivery and not clean_text(delivery.get("no_signal_reason"), 500):
            return ["academic_delivery opt-out requires no_signal_reason"]
        return []
    try:
        minimum_items = max(1, int(delivery.get("minimum_items", 1)))
    except (TypeError, ValueError):
        return ["academic_delivery.minimum_items must be a positive integer"]
    formal_items = [
        item
        for _, item in iter_items(config)
        if academic_kind(clean_text(item.get("source_url"), 1000)) in ACADEMIC_DOMAINS.values()
    ]
    primary_venue_items = [
        item
        for item in formal_items
        if academic_kind(clean_text(item.get("source_url"), 1000)) != "preprint"
    ]
    academic_sections = [
        clean_text(section.get("title"), 200).lower()
        for section in config.get("sections", [])
        if isinstance(section, dict)
    ]
    failures: list[str] = []
    if len(formal_items) < minimum_items:
        failures.append(
            f"academic_delivery requires at least {minimum_items} formal venue or arXiv item; found {len(formal_items)}"
        )
    if not primary_venue_items:
        failures.append("academic_delivery requires at least one non-arXiv formal venue paper")
    if not any("academic" in title or "research" in title or "学术" in title or "论文" in title for title in academic_sections):
        failures.append("academic_delivery requires a dedicated academic research section")
    return failures


def audit_social_delivery(config: dict[str, Any]) -> list[str]:
    """Require a distinct, non-academic social-news section in daily briefings."""
    academic_delivery = config.get("academic_delivery") or {}
    if not isinstance(academic_delivery, dict) or not academic_delivery.get("required"):
        return []
    delivery = config.get("social_delivery") or {}
    if not isinstance(delivery, dict):
        return ["social_delivery must be an object"]
    candidate_pool = config.get("social_candidate_pool") or {}
    if not isinstance(candidate_pool, dict):
        return ["social_candidate_pool must be an object"]
    required_classes = {"ai_hot", "reputable_media", "official_company_social", "executive_social"}
    recorded_classes = {
        clean_text(value, 120).lower()
        for value in candidate_pool.get("required_source_classes", [])
        if clean_text(value, 120)
    }
    try:
        minimum_items = max(1, int(delivery.get("minimum_items", 1)))
    except (TypeError, ValueError):
        return ["social_delivery.minimum_items must be a positive integer"]
    social_sections = [
        section
        for section in config.get("sections", [])
        if isinstance(section, dict)
        and ("社会" in clean_text(section.get("title"), 200) or "social" in clean_text(section.get("title"), 200).lower())
    ]
    if not social_sections:
        return ["daily briefing requires a dedicated social news section"]
    social_items = [item for section in social_sections for item in section.get("items", []) if isinstance(item, dict)]
    non_academic_items = [
        item
        for item in social_items
        if academic_kind(clean_text(item.get("source_url"), 1000)) not in ACADEMIC_DOMAINS.values()
    ]
    failures: list[str] = []
    if not clean_text(candidate_pool.get("checked_at"), 120):
        failures.append("social_candidate_pool requires checked_at")
    missing_classes = sorted(required_classes - recorded_classes)
    if missing_classes:
        failures.append("social_candidate_pool is missing source classes: " + ", ".join(missing_classes))
    if len(social_items) < minimum_items:
        failures.append(f"social_delivery requires at least {minimum_items} social-news item; found {len(social_items)}")
    if len(non_academic_items) < minimum_items:
        failures.append("social news section requires non-academic source-backed items")
    for item in social_items:
        missing_fields = [
            field
            for field in ("source_title", "source_url", "published_at", "evidence_level", "evidence_fingerprint")
            if not clean_text(item.get(field), 1000)
        ]
        if missing_fields:
            failures.append("social news item is missing required evidence fields: " + ", ".join(missing_fields))
    return failures


def contains_cjk(value: Any) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in clean_text(value, 4000))


def audit(config: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    try:
        config = normalize_briefing_config(config, require_source_url=True)
    except (TypeError, ValueError) as exc:
        return {"status": "fail", "items": 0, "academic_items": 0, "failures": [str(exc)], "warnings": [], "academic_source_counts": {}}
    source_urls: Counter[str] = Counter()
    story_ids: Counter[str] = Counter()
    academic_counts: Counter[str] = Counter()
    item_count = 0
    academic_item_count = 0
    requires_chinese_analysis = clean_text(config.get("analysis_language"), 40).lower() in {"zh", "zh-cn", "chinese"}

    for section, item in iter_items(config):
        item_count += 1
        label = clean_text(item.get("id") or item.get("title"), 160)
        source_url = clean_text(item.get("source_url"), 1000)
        story_id = clean_text(item.get("story_id"), 200)
        evidence = clean_text(item.get("evidence_level"), 200).lower()
        facts = clean_text(item.get("facts"), 300)
        judgment = clean_text(item.get("judgment"), 300)
        if not clean_text(item.get("title")):
            failures.append(f"{label}: missing title")
        if not facts:
            failures.append(f"{label}: missing facts")
        if not source_url:
            failures.append(f"{label}: missing source_url")
        else:
            try:
                canonical_url(source_url)
            except ValueError as exc:
                failures.append(f"{label}: {exc}")
        if not clean_text(item.get("source_title")):
            warnings.append(f"{label}: missing source_title")
        if not evidence:
            warnings.append(f"{label}: missing evidence_level")
        if facts and not judgment:
            warnings.append(f"{label}: missing separated judgment/interpretation")
        if requires_chinese_analysis:
            for field, value in (("facts", facts), ("judgment", judgment), ("relevance", clean_text(item.get("relevance"), 300))):
                if not value:
                    failures.append(f"{label}: Chinese analysis requires {field}")
                elif not contains_cjk(value):
                    failures.append(f"{label}: {field} must include Chinese analysis text")
        if source_url:
            source_urls[source_url] += 1
        if story_id:
            story_ids[story_id] += 1
        if "candidate" in evidence and "候选" not in section and "candidate" not in section.lower():
            warnings.append(f"{label}: candidate evidence appears outside a candidate-pool section")
        if is_academic_item(section, item):
            academic_item_count += 1
            kind = academic_kind(source_url)
            academic_counts[kind or "other"] += 1
            if kind == "preprint" and not clean_text(item.get("venue_sweep_note"), 500):
                warnings.append(f"{label}: arXiv preprint lacks venue_sweep_note; record APS/Nature/Science/OpenReview/CVF/PMLR/NeurIPS/ACL/Quantum Journal check")

    for url, count in source_urls.items():
        if count > 1:
            warnings.append(f"duplicate source_url x{count}: {url}")
    for story_id, count in story_ids.items():
        if count > 1:
            warnings.append(f"duplicate story_id x{count}: {story_id}")

    total_academic = sum(count for kind, count in academic_counts.items() if kind not in {"official", "other"})
    failures.extend(audit_academic_delivery(config))
    failures.extend(audit_social_delivery(config))
    if total_academic:
        checked_venues, checked_topics, primary_hits, evidence_failures = academic_search_venues(config)
        failures.extend(evidence_failures)
        if not checked_venues:
            failures.append("academic_search ledger is missing; record PRA/PRL/Nature/Science/CVPR/ICLR and related venue checks before finalizing")
        else:
            missing = sorted(REQUIRED_ACADEMIC_VENUES - checked_venues)
            if missing:
                failures.append("academic_search ledger is incomplete; missing venue checks: " + ", ".join(missing))
            if checked_topics == 0:
                warnings.append("academic_search has no checked topics; keep a compact topic-level search record")
        arxiv_only = academic_counts.get("preprint", 0) == total_academic
        if arxiv_only and evidence_failures:
            warnings.append("academic coverage is arXiv-only; check APS/Nature/Science/OpenReview/ICLR/CVF/CVPR/PMLR/ICML/NeurIPS/ACL/Quantum Journal venue sources before finalizing")
        if academic_counts.get("preprint", 0) and primary_hits == 0 and evidence_failures:
            warnings.append("academic_search recorded no non-arXiv primary venue hits; arXiv items must remain explicitly labeled as preprints")
    status = "fail" if failures else "warn" if warnings else "pass"
    return {
        "status": status,
        "items": item_count,
        "academic_items": academic_item_count,
        "failures": failures,
        "warnings": warnings,
        "academic_source_counts": dict(academic_counts),
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Briefing config JSON.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--fail-on-warning", action="store_true", help="Treat warnings as blocking in strict finalization.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    result = audit(load_json(Path(args.config).expanduser().resolve()))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Audit status: {result['status']}")
        print(f"Items: {result['items']}")
        for failure in result["failures"]:
            print(f"FAIL: {failure}")
        for warning in result["warnings"]:
            print(f"WARN: {warning}")
        if result["academic_source_counts"]:
            print(f"Academic source counts: {result['academic_source_counts']}")
    return 1 if result["failures"] or (args.fail_on_warning and result["warnings"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
