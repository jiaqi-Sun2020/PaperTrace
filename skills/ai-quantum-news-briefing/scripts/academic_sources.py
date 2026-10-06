#!/usr/bin/env python3
"""Versioned academic-source capabilities and family-level health gates."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, parse_qs

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "references" / "academic_sources.v1.json"
SEARCH_VERSION = 4
REQUIRED_FAMILIES = ("quantum_publisher", "ai_peer_review")
HEALTHY_RESULTS = {"checked", "qualified"}


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or not isinstance(data.get("sources"), list):
        raise ValueError("academic source registry must be version 1 with a sources list")
    seen: set[str] = set()
    for source in data["sources"]:
        source_id = str(source.get("source_id") or "")
        parsed = urlsplit(str(source.get("url") or "").replace("{term}", "quantum"))
        if (not source_id or source_id in seen or parsed.scheme != "https" or not parsed.hostname
                or source.get("family") not in {*REQUIRED_FAMILIES, "enhanced_discovery"}
                or source.get("tier") not in {"core", "optional", "probationary"}
                or not isinstance(source.get("capabilities"), list)):
            raise ValueError(f"invalid academic source declaration: {source_id or '<missing>'}")
        declared = str(source.get("domain") or "").lower()
        if parsed.hostname.lower() != declared:
            raise ValueError(f"source domain mismatch: {source_id}")
        if source.get("adapter") in {"aps_harvest", "crossref_dated"}:
            if not all(isinstance(source.get(key), str) and source[key].strip() for key in ("provider_id", "scope_id", "failure_domain")):
                raise ValueError(f"dated source identity missing: {source_id}")
            if source["adapter"] == "crossref_dated" and (not re.fullmatch(r"[0-9]{4}-[0-9]{3}[0-9X]", str(source.get("issn", "")))
                    or source["url"] != "https://api.crossref.org/journals/" + source["issn"] + "/works"
                    or not re.fullmatch(r"10\.[0-9]{4,9}", str(source.get("doi_prefix", "")))):
                raise ValueError(f"dated Crossref scope invalid: {source_id}")
            if source["adapter"] == "aps_harvest" and (source["url"] != "https://harvest.aps.org/v2/journals/articles"
                    or not re.fullmatch(r"[A-Z]+", str(source.get("journal_code", "")))):
                raise ValueError(f"dated APS scope invalid: {source_id}")
        seen.add(source_id)
    return data


def sources_by_id(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_registry()
    return {row["source_id"]: row for row in registry["sources"]}


def row_evidence_failures(row: Any, coverage_window: str | None = None,
                          registry: dict[str, Any] | None = None) -> list[str]:
    """Cross-check transport, registered scope and dated parsed matches, not flags."""
    if not isinstance(row, dict):
        return ["row_not_object"]
    source = sources_by_id(registry).get(str(row.get("source_id") or ""))
    if source is None:
        return ["source_unregistered"]
    failures = []
    window = row.get("coverage_window")
    try:
        days = str(window).split("..")
        first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
        canonical = first.isoformat() if len(days) == 1 else first.isoformat() + ".." + last.isoformat()
        if len(days) not in {1, 2} or first > last or window != canonical:
            raise ValueError("invalid window")
        start = datetime.combine(first, datetime.min.time(), timezone(timedelta(hours=8)))
        end = datetime.combine(last + timedelta(days=1), datetime.min.time(), start.tzinfo)
    except (ValueError, TypeError, OverflowError):
        return ["coverage_window_invalid"]
    if coverage_window is not None and window != coverage_window:
        failures.append("coverage_window_mismatch")
    evidence = row.get("evidence")
    if not isinstance(evidence, dict):
        return failures + ["http_evidence_missing"]
    status = evidence.get("status_code")
    if type(status) is not int or not 200 <= status < 300:
        failures.append("http_status_invalid")
    if not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("response_hash") or "")):
        failures.append("response_hash_invalid")
    if evidence.get("error") or evidence.get("parse_error"):
        failures.append("response_error_present")
    try:
        declared = urlsplit(str(source["url"]).replace("{term}", "quantum"))
        query = urlsplit(str(evidence.get("query_url") or ""))
        final = urlsplit(str(evidence.get("final_url") or ""))
        for parsed in (query, final):
            if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment or parsed.port not in {None, 443}:
                failures.append("response_url_invalid")
        if (query.hostname != declared.hostname or query.path != declared.path
                or any(parse_qs(query.query).get(key) != value for key, value in parse_qs(declared.query).items()
                       if "{term}" not in str(source["url"]))
                or row.get("search_url", evidence.get("query_url")) != evidence.get("query_url")):
            failures.append("query_scope_mismatch")
        if final.hostname not in {source["domain"], *source.get("allowed_final_domains", [])}:
            failures.append("final_domain_invalid")
    except (ValueError, TypeError):
        failures.append("response_url_invalid")
    try:
        stamp = datetime.fromisoformat(str(evidence.get("retrieved_at") or "").replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp < end or stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
            failures.append("retrieved_at_invalid")
    except (ValueError, TypeError, OverflowError):
        failures.append("retrieved_at_invalid")
    matches = row.get("matches")
    count = row.get("candidate_count")
    quarantined = row.get("quarantined_count", 0)
    if (not isinstance(matches, list) or type(count) is not int or count < 0 or count != len(matches)
            or type(quarantined) is not int or quarantined < 0):
        failures.append("candidate_counts_invalid")
    else:
        for item in matches:
            try:
                if not isinstance(item, dict):
                    raise ValueError("invalid match")
                if (source.get("adapter") in {"aps_harvest", "crossref_dated"}
                        and item.get("date_precision") == "day"
                        and item.get("date_semantics") == "index_publication_calendar_date"):
                    published = date.fromisoformat(item.get("published_at", ""))
                    if not first <= published <= last:
                        raise ValueError("outside calendar window")
                    continue
                stamp = datetime.fromisoformat(str(item.get("published_at") or "").replace("Z", "+00:00"))
                if stamp.tzinfo is None or not start <= stamp < end:
                    raise ValueError("outside window")
            except (ValueError, TypeError, OverflowError):
                failures.append("match_date_invalid")
                break
    if row.get("window_status") == "empty" and count != 0:
        failures.append("empty_window_has_matches")
    if row.get("coverage_claim") not in source["capabilities"]:
        failures.append("coverage_claim_unsupported")
    window_evidence = row.get("window_evidence")
    if (isinstance(window_evidence, dict) and row.get("coverage_claim") == "discovery_only"
            and window_evidence.get("publisher_day_coverage_complete") is not False):
        failures.append("discovery_window_claim_invalid")
    if source.get("adapter") == "plos_search":
        from plos_source import plos_evidence_failures
        failures.extend(plos_evidence_failures(row))
    if source.get("adapter") in {"aps_harvest", "crossref_dated"}:
        from dated_source import dated_evidence_failures
        failures.extend(dated_evidence_failures(row, source))
    return sorted(set(failures))


def row_is_healthy(row: Any, coverage_window: str | None = None,
                   registry: dict[str, Any] | None = None) -> bool:
    if not isinstance(row, dict) or row.get("result") not in HEALTHY_RESULTS:
        return False
    return (row.get("retrieval_status") == "success"
            and row.get("parse_status") == "success"
            and row.get("window_status") in {"matched", "empty", "rolling_window"}
            and not row_evidence_failures(row, coverage_window, registry))


def family_gate(rows: Any, registry: dict[str, Any] | None = None,
                coverage_window: str | None = None, *, require_query: bool = False) -> dict[str, Any]:
    registry = registry or load_registry()
    declared = sources_by_id(registry)
    healthy: dict[str, set[str]] = {family: set() for family in REQUIRED_FAMILIES}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        source = declared.get(str(row.get("source_id") or row.get("venue") or ""))
        if not source or source.get("family") not in healthy or not row_is_healthy(row, coverage_window, registry):
            continue
        if require_query and source.get("adapter") not in {"aps_harvest", "crossref_dated", "plos_search"}:
            continue
        healthy[source["family"]].add(str(source["publisher"]))
    missing = [family for family in REQUIRED_FAMILIES if not healthy[family]]
    return {"status": "pass" if not missing else "fail",
            **({"source_coverage_version": 2, "scope": "registered_complete_queries"} if require_query else {}),
            "required_families": list(REQUIRED_FAMILIES),
            "healthy_publishers": {key: sorted(value) for key, value in healthy.items()},
            "missing_families": missing}


def health_table(rows: Any, registry: dict[str, Any] | None = None,
                 coverage_window: str | None = None, *, require_query: bool = False) -> list[dict[str, Any]]:
    registry = registry or load_registry()
    declared = sources_by_id(registry)
    table = []
    missing = family_gate(rows, registry, coverage_window, require_query=require_query)["missing_families"]
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        source_id = str(row.get("source_id") or row.get("venue") or "")
        source = declared.get(source_id, {})
        healthy = row_is_healthy(row, coverage_window, registry)
        query_ready = healthy and source.get("adapter") in {"aps_harvest", "crossref_dated", "plos_search"}
        table.append({
            "source": source.get("label", row.get("label", source_id)),
            "source_id": source_id,
            "tier": source.get("tier", "unknown"),
            "family": source.get("family", "unknown"),
            "provider_id": source.get("provider_id", source.get("domain", "unknown")),
            "scope_id": source.get("scope_id", source_id),
            "query_complete": query_ready,
            "family_gate_eligible": query_ready if require_query else healthy,
            "status": ("invalid_evidence" if row.get("result") in HEALTHY_RESULTS and not healthy
                       else row.get("result", "unchecked")),
            "evidence_failures": row_evidence_failures(row, coverage_window, registry) if row.get("result") in HEALTHY_RESULTS else [],
            "coverage_window": row.get("coverage_window", ""),
            "candidate_count": row.get("candidate_count", 0),
            "quarantined_count": row.get("quarantined_count", 0),
            "impact": ("blocks_family_gate" if source.get("family") in missing and not (query_ready if require_query else healthy)
                       else "isolated" if not healthy else "available"),
            "next_action": ("repair_source_evidence" if row.get("result") in HEALTHY_RESULTS and not healthy else
                            row.get("next_action", "none" if healthy else "retry_or_use_peer_source")),
        })
        if isinstance(row.get("window_evidence"), dict):
            # Keep the scope of an indexed empty result visible to authors.
            table[-1]["window_evidence"] = {key: value for key, value in row["window_evidence"].items()
                                           if value is None or type(value) in {str, int, bool}}
    return table


def markdown_health_table(rows: Any, registry: dict[str, Any] | None = None,
                          coverage_window: str | None = None, *, require_query: bool = False) -> str:
    table = health_table(rows, registry, coverage_window, require_query=require_query)
    if table and all(row["status"] in HEALTHY_RESULTS for row in table):
        return f"Academic sources: {len(table)} healthy; no isolated failures."
    lines = ["| 来源 | 层级 | 状态 | 覆盖窗口 | 候选/隔离 | 对本期影响 | 下一动作 |",
             "|---|---|---|---|---|---|---|"]
    for row in table:
        lines.append("| {source} | {tier} | {status} | {coverage_window} | {candidate_count}/{quarantined_count} | {impact} | {next_action} |".format(**row))
    return "\n".join(lines)
