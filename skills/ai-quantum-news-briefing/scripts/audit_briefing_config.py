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


def academic_search_venues(config: dict[str, Any]) -> tuple[set[str], int, int]:
    raw = config.get("academic_search") or config.get("academic_venue_sweep") or {}
    if not isinstance(raw, dict):
        return set(), 0, 0
    venues: set[str] = set()
    for venue in raw.get("required_venues", []) or raw.get("venues", []) or []:
        venues.add(normalize_venue(venue))
    topics = raw.get("topics") or []
    primary_hits = 0
    checked_topics = 0
    if isinstance(topics, list):
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            checked = {normalize_venue(v) for v in topic.get("checked_venues", []) or []}
            venues.update(checked)
            if checked:
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
            if result and result != "unchecked":
                venues.add(venue)
            if venue != "arxiv" and clean_text(row.get("url"), 1000):
                primary_hits += 1
    return venues, checked_topics, primary_hits


def audit(config: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    warnings: list[str] = []
    source_urls: Counter[str] = Counter()
    story_ids: Counter[str] = Counter()
    academic_counts: Counter[str] = Counter()
    item_count = 0
    academic_item_count = 0

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
        if not clean_text(item.get("source_title")):
            warnings.append(f"{label}: missing source_title")
        if not evidence:
            warnings.append(f"{label}: missing evidence_level")
        if facts and not judgment:
            warnings.append(f"{label}: missing separated judgment/interpretation")
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

    total_academic = sum(academic_counts.values())
    if total_academic:
        checked_venues, checked_topics, primary_hits = academic_search_venues(config)
        if not checked_venues:
            failures.append("academic_search ledger is missing; record PRA/PRL/Nature/Science/CVPR/ICLR and related venue checks before finalizing")
        else:
            missing = sorted(REQUIRED_ACADEMIC_VENUES - checked_venues)
            if missing:
                failures.append("academic_search ledger is incomplete; missing venue checks: " + ", ".join(missing))
            if checked_topics == 0:
                warnings.append("academic_search has no checked topics; keep a compact topic-level search record")
        arxiv_only = academic_counts.get("preprint", 0) == total_academic
        if arxiv_only:
            warnings.append("academic coverage is arXiv-only; check APS/Nature/Science/OpenReview/ICLR/CVF/CVPR/PMLR/ICML/NeurIPS/ACL/Quantum Journal venue sources before finalizing")
        if academic_counts.get("preprint", 0) and primary_hits == 0:
            warnings.append("academic_search recorded no non-arXiv primary venue hits; arXiv items must remain explicitly labeled as preprints")
        if academic_counts.get("other", 0):
            warnings.append("some academic-looking items are from non-whitelisted domains; verify they are primary or reputable sources")

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
    return 1 if result["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
