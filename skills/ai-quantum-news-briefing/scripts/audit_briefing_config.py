#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial audit for AI+quantum briefing configs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote_plus, urlsplit

from science_coverage_policy import science_journal_candidate, science_skipped

from briefing_contract import canonical_url, normalize_briefing_config
from rank_briefing_candidates import ALGORITHM_VERSION, SOURCE_ALGORITHM_VERSION, is_primary_official, is_reputable, score_item
from delivery_expansion import SHORTFALL, publication_relation, validate_policy
from paper_identity import academic_host_kind, host, paper_kind
from academic_sources import family_gate as academic_family_gate, row_is_healthy


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
    "eccv.ecva.net": "ecva",
    "ecva.net": "ecva",
    "jmlr.org": "jmlr",
    "iopscience.iop.org": "iop",
    "ieeexplore.ieee.org": "ieee",
    "ojs.aaai.org": "aaai",
    "api2.openreview.net": "openreview",
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


def academic_kind(url: str, item: dict[str, Any] | None = None) -> str:
    if item is not None:
        return paper_kind(item)
    if host(url) == "doi.org":
        return ""
    domain = domain_of(url)
    for known, kind in ACADEMIC_DOMAINS.items():
        if domain == known or domain.endswith("." + known):
            return kind
    if any(domain == known or domain.endswith("." + known) for known in OFFICIAL_RESEARCH_DOMAINS):
        return "official"
    return ""


def is_academic_item(section: str, item: dict[str, Any]) -> bool:
    source_kind = academic_kind(clean_text(item.get("source_url"), 1000))
    if source_kind in ACADEMIC_DOMAINS.values():
        return True
    section_text = clean_text(section, 300).lower()
    if any(word in section_text for word in ["社会", "social", "news", "新闻"]):
        return False
    if any(word in section_text for word in ["academic", "学术", "papers", "论文"]):
        return True
    text = " ".join(
        [
            section_text,
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


def valid_venue_evidence(row: dict[str, Any]) -> bool:
    """Validate adapter-produced listing data; the current sweep does not emit such a proof.

    A Science retrieval or Crossref snapshot cannot assert publisher-day coverage.
    The source review must independently inspect the captured publisher response.
    """
    evidence = row.get("evidence")
    if normalize_venue(row.get("venue")) != "science":
        return valid_http_evidence(evidence)
    if row.get("coverage_status") != "verified" or row.get("verification_method") != "official_complete_listing":
        return False
    providers = row.get("provider_evidence")
    if not isinstance(providers, list):
        return False
    for provider in providers:
        if not isinstance(provider, dict) or provider.get("provider") != "science":
            continue
        if provider.get("role") not in {"official_search", "official_first_release"}:
            continue
        if provider.get("proves_daily_coverage") is not True or provider.get("pagination_complete") is not True:
            continue
        if not valid_http_evidence(provider):
            continue
        try:
            query = urlsplit(provider["query_url"])
            final = urlsplit(provider["final_url"])
            total = int(provider["total_count"])
            retrieved = int(provider["retrieved_count"])
            start = datetime.fromisoformat(provider["coverage_start"])
            end = datetime.fromisoformat(provider["coverage_end"])
        except (KeyError, TypeError, ValueError):
            continue
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            continue
        try:
            retrieved_at = datetime.fromisoformat(str(provider["retrieved_at"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if retrieved_at.tzinfo is None or retrieved_at < end:
            continue
        pages = provider.get("listing_pages")
        if not isinstance(pages, list) or not pages:
            continue
        publication_ids: list[str] = []
        page_ok = True
        for index, page in enumerate(pages):
            if not isinstance(page, dict) or not isinstance(page.get("response_body"), str):
                page_ok = False
                break
            page_url = urlsplit(str(page.get("query_url") or ""))
            if (page_url.scheme != "https" or page_url.hostname not in {"science.org", "www.science.org"}
                    or page.get("response_hash") != hashlib.sha256(page["response_body"].encode("utf-8")).hexdigest()):
                page_ok = False
                break
            try:
                payload = json.loads(page["response_body"])
            except ValueError:
                page_ok = False
                break
            if (not isinstance(payload, dict) or payload.get("source") != "Science"
                    or payload.get("coverage_start") != start.isoformat()
                    or payload.get("coverage_end") != end.isoformat()
                    or payload.get("total_count") != total
                    or payload.get("has_next") is not (index < len(pages) - 1)
                    or not isinstance(payload.get("items"), list)):
                page_ok = False
                break
            for item in payload["items"]:
                if not isinstance(item, dict) or not str(item.get("doi") or "").lower().startswith("10.1126/"):
                    page_ok = False
                    break
                try:
                    published = datetime.fromisoformat(str(item["published_at"]).replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    page_ok = False
                    break
                if published.tzinfo is None or not start <= published.astimezone(start.tzinfo) < end:
                    page_ok = False
                    break
                publication_ids.append(str(item["doi"]).lower())
            if not page_ok:
                break
        query_text = unquote_plus(query.query)
        if (page_ok and provider.get("response_hash") == pages[0].get("response_hash")
                and provider.get("query_url") == pages[0].get("query_url")
                and len(publication_ids) == len(set(publication_ids)) == total
                and start.date().isoformat() in query_text
                and end.date().isoformat() in query_text
                and query.scheme == final.scheme == "https"
                and query.hostname in {"science.org", "www.science.org"}
                and final.hostname in {"science.org", "www.science.org"}
                and total >= 0 and retrieved == total
                and re.fullmatch(r"[0-9a-f]{64}", str(provider["response_hash"]))):
            return True
    return False


def valid_science_skip_v2(row: dict[str, Any], day: str) -> bool:
    """Validate a bounded unavailable claim, never a zero-publication claim."""
    if (row.get("venue") != "science" or row.get("result") != "skipped_unavailable"
            or row.get("coverage_status") != "unavailable"
            or row.get("verification_method") != "none"
            or row.get("coverage_date") != day
            or row.get("skip_reason_code") not in {"access_denied", "no_complete_dated_listing"}):
        return False
    try:
        end = datetime.fromisoformat(day + "T00:00:00+08:00") + timedelta(days=1)
    except ValueError:
        return False
    providers = row.get("provider_evidence")
    if not isinstance(providers, list):
        return False
    official: dict[str, dict[str, Any]] = {}
    for provider in providers:
        if not isinstance(provider, dict) or provider.get("provider") != "science":
            continue
        role = provider.get("role")
        if role not in {"official_search", "official_toc_discovery"}:
            continue
        query = urlsplit(str(provider.get("query_url") or ""))
        final = urlsplit(str(provider.get("final_url") or ""))
        try:
            stamp = datetime.fromisoformat(str(provider.get("retrieved_at") or "").replace("Z", "+00:00"))
            status = int(provider.get("status_code"))
        except (TypeError, ValueError):
            return False
        if (query.scheme != final.scheme or query.scheme != "https"
                or query.hostname not in {"science.org", "www.science.org"}
                or final.hostname not in {"science.org", "www.science.org"}
                or not 200 <= status < 600 or stamp.tzinfo is None or stamp < end
                or not re.fullmatch(r"[0-9a-f]{64}", str(provider.get("response_hash") or ""))
                or provider.get("proves_daily_coverage") is not False):
            return False
        if role == "official_search" and query.path != "/action/doSearch":
            return False
        if role == "official_toc_discovery" and query.path != "/toc/science/0/0":
            return False
        official[role] = provider
    if set(official) != {"official_search", "official_toc_discovery"}:
        return False
    blocked = any(int(provider["status_code"]) == 403 for provider in official.values())
    if row.get("retrieval_status") != ("blocked" if blocked else "success"):
        return False
    return row["skip_reason_code"] == ("access_denied" if blocked else "no_complete_dated_listing")


def academic_search_venues(config: dict[str, Any], *, legacy_science: bool = False,
                           coverage_contract_version: int = 1) -> tuple[set[str], int, int, list[str]]:
    raw = config.get("academic_search") or config.get("academic_venue_sweep") or {}
    if not isinstance(raw, dict):
        return set(), 0, 0, ["academic_search ledger is missing"]
    if raw.get("academic_search_version") == 4:
        rows = raw.get("rows")
        if not isinstance(rows, list) or not rows:
            return set(), 0, 0, ["academic search v4 source rows are missing"]
        gate = academic_family_gate(rows)
        failures = [] if gate["status"] == "pass" else [
            "academic source family gate failed: " + ", ".join(gate["missing_families"])]
        if raw.get("family_gate") != gate:
            failures.append("academic source family gate is stale or inconsistent")
        venues = {normalize_venue(row.get("source_id") or row.get("venue"))
                  for row in rows if isinstance(row, dict) and row_is_healthy(row)}
        hits = sum(int(row.get("candidate_count") or 0) for row in rows
                   if isinstance(row, dict) and row_is_healthy(row))
        return venues, 1 if gate["status"] == "pass" else 0, hits, failures
    venues: set[str] = set()
    # Declared venue lists are policy metadata, never proof that a search ran.
    topics = raw.get("topics") or []
    primary_hits = 0
    checked_topics = 0
    evidence_failures: list[str] = []
    def evidenced(row: dict[str, Any]) -> bool:
        if coverage_contract_version == 2 and normalize_venue(row.get("venue")) == "science":
            # No publisher-complete Science parser exists yet.  In particular,
            # the old hand-authored JSON body cannot authorize a v2 release.
            return valid_science_skip_v2(row, str(row.get("coverage_date") or raw.get("date_range") or ""))
        return (valid_http_evidence(row.get("evidence")) if legacy_science
                and normalize_venue(row.get("venue")) == "science" else valid_venue_evidence(row))
    if isinstance(topics, list):
        for topic in topics:
            if not isinstance(topic, dict):
                continue
            checked = {normalize_venue(v) for v in topic.get("checked_venues", []) or []}
            valid_rows = []
            for row in raw.get("rows", []) or []:
                if isinstance(row, dict) and row.get("term") == topic.get("term"):
                    evidence = row.get("evidence")
                    allowed = {"checked", "hit", "checked_no_hit"}
                    if coverage_contract_version == 2 and normalize_venue(row.get("venue")) == "science":
                        allowed = {"skipped_unavailable"}
                    if row.get("result") in allowed and isinstance(evidence, dict):
                        if evidenced(row):
                            valid_rows.append(row)
                        else:
                            evidence_failures.append(f"{topic.get('term')}/{row.get('venue')}: incomplete venue coverage evidence")
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
            allowed = {"checked", "hit", "checked_no_hit"}
            if coverage_contract_version == 2 and venue == "science":
                allowed = {"skipped_unavailable"}
            if result in allowed and evidenced(row):
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
    failures: list[str] = []
    shortfall = (config.get("delivery_expansion") or {}).get("mode") == SHORTFALL
    try:
        configured_minimum_items = int(delivery.get("minimum_items", 6))
        minimum_items = max(6, configured_minimum_items)
    except (TypeError, ValueError):
        return ["academic_delivery.minimum_items must be a positive integer"]
    if configured_minimum_items < 6:
        failures.append("academic_delivery.minimum_items must be at least 6")
    formal_items = [
        item
        for _, item in iter_items(config)
        if academic_kind(clean_text(item.get("source_url"), 1000), item) in ACADEMIC_DOMAINS.values()
    ]
    primary_venue_items = [
        item
        for item in formal_items
        if academic_kind(clean_text(item.get("source_url"), 1000), item) != "preprint"
    ]
    academic_sections = [
        clean_text(section.get("title"), 200).lower()
        for section in config.get("sections", [])
        if isinstance(section, dict)
    ]
    if len(formal_items) < minimum_items and not shortfall:
        failures.append(
            f"academic_delivery requires at least {minimum_items} formal venue or arXiv item; found {len(formal_items)}"
        )
    try:
        configured_maximum_items = int(delivery.get("maximum_items", 8))
        configured_minimum_non_arxiv = int(delivery.get("minimum_non_arxiv_items", 2))
        configured_maximum_continuing = int(delivery.get("maximum_continuing_items", 3))
    except (TypeError, ValueError):
        return failures + ["academic_delivery item limits must be integers"]
    if configured_maximum_items > 8 or configured_maximum_items < minimum_items:
        failures.append("academic_delivery publication range must stay within 6-8 items")
    if configured_minimum_non_arxiv < 2:
        failures.append("academic_delivery.minimum_non_arxiv_items must be at least 2")
    if configured_maximum_continuing > 3:
        failures.append("academic_delivery.maximum_continuing_items must be at most 3")
    maximum_items = min(8, max(minimum_items, configured_maximum_items))
    minimum_non_arxiv = max(2, configured_minimum_non_arxiv)
    maximum_continuing = max(0, min(3, configured_maximum_continuing))
    if len(formal_items) > maximum_items:
        failures.append(f"academic_delivery permits at most {maximum_items} paper items; found {len(formal_items)}")
    if len(primary_venue_items) < minimum_non_arxiv and not shortfall:
        failures.append(
            f"academic_delivery requires at least {minimum_non_arxiv} non-arXiv formal venue papers; found {len(primary_venue_items)}"
        )
    continuing_items = [item for item in formal_items if clean_text(item.get("novelty"), 80).lower() == "continuing"]
    if len(continuing_items) > maximum_continuing:
        failures.append(
            f"academic_delivery permits at most {maximum_continuing} continuing paper items; found {len(continuing_items)}"
        )
    if not any("academic" in title or "research" in title or "学术" in title or "论文" in title for title in academic_sections):
        failures.append("academic_delivery requires a dedicated academic research section")
    delta_policy = config.get("delta_policy") or {}
    if isinstance(delta_policy, dict) and delta_policy.get("mode") == "delta_first":
        try:
            configured_minimum_new = int(delivery.get("minimum_new_items", 4))
            configured_maximum_new = int(delivery.get("maximum_new_items", 8))
        except (TypeError, ValueError):
            return failures + ["academic_delivery.minimum_new_items and maximum_new_items must be positive integers"]
        if configured_minimum_new < 4:
            failures.append("academic_delivery.minimum_new_items must be at least 4")
        if configured_maximum_new > 8 or configured_maximum_new < max(4, configured_minimum_new):
            failures.append("academic_delivery new-item range must stay within 4-8 items")
        minimum_new_items = max(4, configured_minimum_new)
        maximum_new_items = min(8, max(minimum_new_items, configured_maximum_new))
        new_items = [
            item for item in formal_items
            if clean_text(item.get("novelty"), 80).lower() == "new"
        ]
        if len(new_items) < minimum_new_items and not shortfall:
            failures.append(
                f"academic_delivery final delta requires {minimum_new_items}-{maximum_new_items} new academic paper items; found {len(new_items)}"
            )
        if len(new_items) > maximum_new_items:
            failures.append(
                f"academic_delivery final delta permits at most {maximum_new_items} new academic paper items; found {len(new_items)}"
            )
    if shortfall and not formal_items:
        failures.append("verified_shortfall still requires at least one audited academic paper")
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
    failures: list[str] = []
    shortfall = (config.get("delivery_expansion") or {}).get("mode") == SHORTFALL
    legacy_shortfall = shortfall and (config.get("delivery_expansion") or {}).get("version") == 1
    try:
        configured_minimum_items = int(delivery.get("minimum_items", 6))
        minimum_items = max(6, configured_minimum_items)
    except (TypeError, ValueError):
        return ["social_delivery.minimum_items must be a positive integer"]
    if configured_minimum_items < 6:
        failures.append("social_delivery.minimum_items must be at least 6")
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
        if not academic_host_kind(item.get("source_url")) and host(item.get("source_url")) != "doi.org"
    ]
    if not clean_text(candidate_pool.get("checked_at"), 120):
        failures.append("social_candidate_pool requires checked_at")
    missing_classes = sorted(required_classes - recorded_classes)
    if missing_classes:
        failures.append("social_candidate_pool is missing source classes: " + ", ".join(missing_classes))
    if len(social_items) < minimum_items and not shortfall:
        failures.append(f"social_delivery requires at least {minimum_items} social-news item; found {len(social_items)}")
    if len(non_academic_items) < minimum_items and not shortfall:
        failures.append("social news section requires non-academic source-backed items")
    try:
        configured_maximum_items = int(delivery.get("maximum_items", 12))
        configured_minimum_active = int(delivery.get("minimum_new_or_material_update", 4))
        configured_maximum_continuing = int(delivery.get("maximum_continuing_items", 3))
        configured_minimum_reputable = int(delivery.get("minimum_reputable_media_items", 3))
        configured_minimum_official = int(delivery.get("minimum_primary_official_items", 3))
        configured_minimum_classes = int(delivery.get("minimum_source_classes", 3))
        configured_maximum_organization = int(delivery.get("maximum_items_per_organization", 2))
        configured_maximum_topic = int(delivery.get("maximum_items_per_topic", 3))
    except (TypeError, ValueError):
        return failures + ["social_delivery limits must be integers"]
    maximum_ceiling = 14 if legacy_shortfall else 12
    if configured_maximum_items > maximum_ceiling or configured_maximum_items < minimum_items:
        failures.append("social_delivery publication range must stay within 6-12 items")
    if configured_minimum_active < 4:
        failures.append("social_delivery.minimum_new_or_material_update must be at least 4")
    if configured_maximum_continuing > 3:
        failures.append("social_delivery.maximum_continuing_items must be at most 3")
    if configured_minimum_reputable < 3:
        failures.append("social_delivery.minimum_reputable_media_items must be at least 3")
    if configured_minimum_official < 3:
        failures.append("social_delivery.minimum_primary_official_items must be at least 3")
    if configured_minimum_classes < 3:
        failures.append("social_delivery.minimum_source_classes must be at least 3")
    if configured_maximum_organization > 2:
        failures.append("social_delivery.maximum_items_per_organization must be at most 2")
    if configured_maximum_topic > 3:
        failures.append("social_delivery.maximum_items_per_topic must be at most 3")
    maximum_items = min(maximum_ceiling, max(minimum_items, configured_maximum_items))
    minimum_active = max(4, configured_minimum_active)
    maximum_continuing = max(0, min(3, configured_maximum_continuing))
    minimum_reputable = max(3, configured_minimum_reputable)
    minimum_official = max(3, configured_minimum_official)
    minimum_classes = max(3, configured_minimum_classes)
    maximum_organization = max(1, min(2, configured_maximum_organization))
    maximum_topic = max(1, min(3, configured_maximum_topic))
    if len(social_items) > maximum_items:
        failures.append(f"social_delivery permits at most {maximum_items} items; found {len(social_items)}")
    active_items = [item for item in social_items if clean_text(item.get("novelty"), 80).lower() in {"new", "material_update"}]
    continuing_items = [item for item in social_items if clean_text(item.get("novelty"), 80).lower() == "continuing"]
    source_classes = [clean_text((item.get("ranking") or {}).get("source_class") or item.get("source_class"), 120).lower() for item in social_items]
    if len(active_items) < minimum_active and not shortfall:
        failures.append(f"social_delivery requires at least {minimum_active} new or material-update items; found {len(active_items)}")
    if len(continuing_items) > maximum_continuing:
        failures.append(f"social_delivery permits at most {maximum_continuing} continuing items; found {len(continuing_items)}")
    if sum(is_reputable(value) for value in source_classes) < minimum_reputable and not shortfall:
        failures.append(f"social_delivery requires at least {minimum_reputable} reputable-media items")
    if sum(is_primary_official(value) for value in source_classes) < minimum_official and not shortfall:
        failures.append(f"social_delivery requires at least {minimum_official} primary-official items")
    if len({value for value in source_classes if value}) < minimum_classes and not shortfall:
        failures.append(f"social_delivery requires at least {minimum_classes} source classes")
    organizations = Counter(clean_text((item.get("ranking") or {}).get("organization") or item.get("organization"), 200).lower() for item in social_items)
    topics = Counter(clean_text((item.get("ranking") or {}).get("topic") or item.get("topic"), 200).lower() for item in social_items)
    for organization, count in organizations.items():
        if organization and count > maximum_organization:
            failures.append(f"social_delivery organization cap exceeded: {organization} x{count} > {maximum_organization}")
    for topic, count in topics.items():
        if topic and count > maximum_topic:
            failures.append(f"social_delivery topic cap exceeded: {topic} x{count} > {maximum_topic}")
    for item in social_items:
        missing_fields = [
            field
            for field in ("source_title", "source_url", "published_at", "evidence_level", "evidence_fingerprint")
            if not clean_text(item.get(field), 1000)
        ]
        if missing_fields:
            failures.append("social news item is missing required evidence fields: " + ", ".join(missing_fields))
    if shortfall and not non_academic_items:
        failures.append("verified_shortfall still requires at least one audited social item")
    return failures


def audit_ranking_delivery(config: dict[str, Any]) -> list[str]:
    """Require a transparent, internally consistent ranking record for daily releases."""
    delivery = config.get("academic_delivery") or {}
    if not isinstance(delivery, dict) or not delivery.get("required"):
        return []
    policy = config.get("ranking_policy") or {}
    manifest = config.get("ranking_manifest") or {}
    failures: list[str] = []
    recorded_minimums = ((manifest.get("shortfall_evidence") or {}).get("normal_minimums")
                         if isinstance(manifest, dict) else None)
    legacy_policy = recorded_minimums == {"academic": 7, "social": 10}
    if not isinstance(policy, dict) or not policy.get("enabled"):
        return ["daily briefing requires ranking_policy.enabled=true"]
    algorithm = clean_text(policy.get("algorithm_version"), 120)
    if algorithm not in {ALGORITHM_VERSION, SOURCE_ALGORITHM_VERSION}:
        failures.append("ranking_policy.algorithm_version is unsupported")
    if not isinstance(manifest, dict) or clean_text(manifest.get("algorithm_version"), 120) != algorithm:
        failures.append("ranking_manifest.algorithm_version differs from policy")
        return failures
    academic_policy = policy.get("academic") or {}
    social_policy = policy.get("social") or {}
    try:
        academic_floor = 7 if legacy_policy else 6
        social_floor = 10 if legacy_policy else 6
        social_ceiling = 14 if legacy_policy else 12
        if int(academic_policy.get("minimum_items", 0)) < academic_floor or int(academic_policy.get("maximum_items", 99)) > 8:
            failures.append(f"ranking_policy academic publication range must be {academic_floor}-8 items")
        if clean_text(academic_policy.get("ordering"), 120) != "base_score_desc":
            failures.append("ranking_policy academic ordering must be base_score_desc")
        if (int(social_policy.get("minimum_items", 0)) < social_floor
                or int(social_policy.get("maximum_items", 99)) > social_ceiling):
            failures.append(f"ranking_policy social publication range must be {social_floor}-{social_ceiling} items")
    except (TypeError, ValueError):
        failures.append("ranking_policy item limits must be integers")

    ranked_items: dict[str, list[dict[str, Any]]] = {"academic": [], "social": []}
    for section, item in iter_items(config):
        kind = "academic" if academic_kind(clean_text(item.get("source_url"), 1000), item) in ACADEMIC_DOMAINS.values() else "social"
        ranking = item.get("ranking") or {}
        label = clean_text(item.get("story_id") or item.get("id"), 240)
        if not isinstance(ranking, dict) or not ranking:
            failures.append(f"{label}: selected item is missing ranking evidence")
            continue
        if clean_text(ranking.get("algorithm_version"), 120) != algorithm:
            failures.append(f"{label}: ranking algorithm version mismatch")
        if algorithm == SOURCE_ALGORITHM_VERSION:
            try:
                ranking_day = date.fromisoformat(str(manifest.get("generated_for_date")))
                recomputed = score_item(item, kind, ranking_day,
                                        clean_text(ranking.get("novelty"), 80), SOURCE_ALGORITHM_VERSION)
                if ranking.get("components") != recomputed["components"] or ranking.get("penalties") != recomputed["penalties"]:
                    failures.append(f"{label}: source-only ranking signals differ from the captured source")
            except (ValueError, TypeError):
                failures.append(f"{label}: cannot reproduce source-only ranking")
        if ranking.get("eligible") is not True or ranking.get("selected") is not True:
            failures.append(f"{label}: published item must be eligible and selected")
        components = ranking.get("components") or {}
        penalties = ranking.get("penalties") or {}
        try:
            computed = max(0.0, min(100.0, sum(float(value) for value in components.values()) + sum(float(value) for value in penalties.values())))
            if abs(computed - float(ranking.get("base_score"))) > 0.02:
                failures.append(f"{label}: ranking base_score is not reproducible from components and penalties")
            rank = int(ranking.get("rank"))
            if rank < 1:
                raise ValueError
        except (TypeError, ValueError):
            failures.append(f"{label}: ranking score or rank is invalid")
        ranked_items[kind].append(item)

    for kind, items in ranked_items.items():
        try:
            ranks = sorted(int((item.get("ranking") or {}).get("rank", 0)) for item in items)
        except (TypeError, ValueError):
            ranks = []
        if ranks != list(range(1, len(items) + 1)):
            failures.append(f"{kind} ranking must use contiguous ranks starting at 1")
    try:
        academic_rank_sequence = [
            int((item.get("ranking") or {}).get("rank", 0)) for item in ranked_items["academic"]
        ]
    except (TypeError, ValueError):
        academic_rank_sequence = []
    if academic_rank_sequence != list(range(1, len(academic_rank_sequence) + 1)):
        failures.append("academic section must be displayed in rank order")
    academic_scores: list[float] = []
    for item in ranked_items["academic"]:
        try:
            academic_scores.append(float((item.get("ranking") or {}).get("base_score")))
        except (TypeError, ValueError):
            academic_scores = []
            break
    if academic_scores and academic_scores != sorted(academic_scores, reverse=True):
        failures.append("academic section must be ordered by descending impact score")
    selected_counts = manifest.get("selected_counts") or {}
    for kind in ("academic", "social"):
        try:
            if int(selected_counts.get(kind, -1)) != len(ranked_items[kind]):
                failures.append(f"ranking_manifest selected count mismatch for {kind}")
        except (TypeError, ValueError):
            failures.append(f"ranking_manifest selected count is invalid for {kind}")
    ledger = manifest.get("candidate_ledger") or []
    if not isinstance(ledger, list) or not ledger:
        failures.append("ranking_manifest requires a non-empty candidate_ledger")
    else:
        selected_ledger = {clean_text(row.get("story_id"), 240) for row in ledger if isinstance(row, dict) and row.get("selected")}
        published_ids = {clean_text(item.get("story_id"), 240) for items in ranked_items.values() for item in items}
        if selected_ledger != published_ids:
            failures.append("ranking_manifest selected ledger does not match published story IDs")
        for row in ledger:
            if isinstance(row, dict) and not row.get("selected") and not row.get("exclusion_reasons"):
                failures.append("ranking candidate exclusion requires an explicit reason")
    if (config.get("delivery_expansion") or {}).get("mode") == SHORTFALL:
        short = manifest.get("shortfall_evidence") or {}
        if not isinstance(short, dict):
            short = {}
        if (not isinstance(short, dict) or short.get("coverage_date") != config["delivery_expansion"].get("coverage_date")
                or short.get("selected_counts") != selected_counts
                or short.get("eligible_counts") != manifest.get("eligible_counts")
                or not isinstance(short.get("exclusions"), dict)):
            failures.append("shortfall ranking evidence is missing or does not match the candidate ledger")
        if isinstance(ledger, list):
            actual_eligible = {kind: sum(isinstance(row, dict) and row.get("kind") == kind
                                         and row.get("eligible") is True for row in ledger)
                               for kind in ("academic", "social")}
            actual_exclusions = dict(Counter(reason for row in ledger if isinstance(row, dict)
                                             for reason in row.get("exclusion_reasons", [])))
            if manifest.get("eligible_counts") != actual_eligible or short.get("exclusions") != actual_exclusions:
                failures.append("shortfall candidate counts or exclusions do not match the ledger")
        shortfall_minimums = (7, 10) if legacy_policy else (6, 6)
        if (len(ranked_items["academic"]) >= shortfall_minimums[0]
                and len(ranked_items["social"]) >= shortfall_minimums[1]):
            failures.append("verified_shortfall cannot be used when both normal item minimums are met")
        try:
            covered = date.fromisoformat(str(config["delivery_expansion"]["coverage_date"]))
        except (KeyError, TypeError, ValueError):
            failures.append("shortfall coverage date is invalid")
            return failures
        for kind, items in ranked_items.items():
            for item in items:
                if item.get("time_relation") != publication_relation(item, kind, covered):
                    failures.append(f"{item.get('id')}: time relation disagrees with original publication time")
            same_day = sum(item.get("time_relation") == "covered_day" for item in items)
            recent = sum(item.get("time_relation") == "recent_context" for item in items)
            if same_day + recent != len(items):
                failures.append(f"{kind}: published shortfall item has no verified time relation")
            if isinstance(short, dict) and (short.get("same_day_counts", {}).get(kind) != same_day
                                            or short.get("recent_context_counts", {}).get(kind) != recent):
                failures.append(f"{kind}: shortfall temporal counts do not match published items")
    return failures


def contains_cjk(value: Any) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in clean_text(value, 4000))


def audit(config: dict[str, Any], *, legacy_science: bool = False,
          coverage_contract_version: int = 1) -> dict[str, Any]:
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
    failures.extend(validate_policy(config))

    opening_story = config.get("opening_story") or {}
    if opening_story and requires_chinese_analysis:
        story_text = " ".join(str(value) for value in opening_story.get("paragraphs", []))
        if not contains_cjk(story_text):
            failures.append("opening_story.paragraphs must include Chinese narrative text")
        for field in ("concept_definition", "logic_chain", "analogy_boundary", "misleading_risk"):
            if not contains_cjk(opening_story.get(field)):
                failures.append(f"opening_story.{field} must include Chinese analysis text")
        worked_example = opening_story.get("worked_example") or {}
        if worked_example:
            for field in (
                "title",
                "question",
                "scenario",
                "observable",
                "result",
                "interpretation",
                "non_conclusion",
            ):
                if not contains_cjk(worked_example.get(field)):
                    failures.append(
                        f"opening_story.worked_example.{field} must include Chinese analysis text"
                    )
            for field in ("assumptions", "checks"):
                for index, value in enumerate(worked_example.get(field, []), start=1):
                    if not contains_cjk(value):
                        failures.append(
                            f"opening_story.worked_example.{field}[{index}] must include Chinese analysis text"
                        )
            for index, value in enumerate(worked_example.get("objects", []), start=1):
                object_explanation = f"{value.get('kind', '')} {value.get('role', '')}"
                if not contains_cjk(object_explanation):
                    failures.append(
                        f"opening_story.worked_example.objects[{index}] must explain type and role in Chinese"
                    )
            for index, value in enumerate(worked_example.get("inputs", []), start=1):
                input_explanation = f"{value.get('name', '')} {value.get('role', '')}"
                if not contains_cjk(input_explanation):
                    failures.append(
                        f"opening_story.worked_example.inputs[{index}] must name and explain the concrete input in Chinese"
                    )
            for index, value in enumerate(worked_example.get("steps", []), start=1):
                step_explanation = " ".join(
                    str(value.get(field) or "")
                    for field in ("action", "rule", "explanation")
                )
                if not contains_cjk(step_explanation):
                    failures.append(
                        f"opening_story.worked_example.steps[{index}] must explain the transition in Chinese"
                    )

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
            if urlsplit(source_url).hostname in {"api.crossref.org", "search.crossref.org"}:
                failures.append(f"{label}: Crossref metadata is discovery/coverage evidence, not article-level content evidence")
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
            kind = academic_kind(source_url, item)
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
    if coverage_contract_version == 2 and science_skipped(config.get("academic_search")):
        for section, item in iter_items(config):
            if is_academic_item(section, item) and science_journal_candidate(item):
                failures.append(f"{item.get('id') or item.get('title')}: Science candidate cannot be published while its daily inventory is skipped")
    failures.extend(audit_academic_delivery(config))
    failures.extend(audit_social_delivery(config))
    failures.extend(audit_ranking_delivery(config))
    if total_academic:
        checked_venues, checked_topics, primary_hits, evidence_failures = academic_search_venues(
            config, legacy_science=legacy_science, coverage_contract_version=coverage_contract_version)
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
