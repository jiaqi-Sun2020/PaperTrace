#!/usr/bin/env python3
"""Versioned academic-source capabilities and family-level health gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

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
        seen.add(source_id)
    return data


def sources_by_id(registry: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    registry = registry or load_registry()
    return {row["source_id"]: row for row in registry["sources"]}


def row_is_healthy(row: Any) -> bool:
    if not isinstance(row, dict) or row.get("result") not in HEALTHY_RESULTS:
        return False
    return (row.get("retrieval_status") == "success"
            and row.get("parse_status") in {"success", "not_applicable"}
            and row.get("window_status") in {"matched", "empty", "rolling_window"})


def family_gate(rows: Any, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry()
    declared = sources_by_id(registry)
    healthy: dict[str, set[str]] = {family: set() for family in REQUIRED_FAMILIES}
    for row in rows if isinstance(rows, list) else []:
        source = declared.get(str(row.get("source_id") or row.get("venue") or ""))
        if not source or source.get("family") not in healthy or not row_is_healthy(row):
            continue
        healthy[source["family"]].add(str(source["publisher"]))
    missing = [family for family in REQUIRED_FAMILIES if not healthy[family]]
    return {"status": "pass" if not missing else "fail",
            "required_families": list(REQUIRED_FAMILIES),
            "healthy_publishers": {key: sorted(value) for key, value in healthy.items()},
            "missing_families": missing}


def health_table(rows: Any, registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = registry or load_registry()
    declared = sources_by_id(registry)
    table = []
    for row in rows if isinstance(rows, list) else []:
        source_id = str(row.get("source_id") or row.get("venue") or "")
        source = declared.get(source_id, {})
        table.append({
            "source": source.get("label", row.get("label", source_id)),
            "source_id": source_id,
            "tier": source.get("tier", "unknown"),
            "family": source.get("family", "unknown"),
            "status": row.get("result", "unchecked"),
            "coverage_window": row.get("coverage_window", ""),
            "candidate_count": int(row.get("candidate_count") or 0),
            "quarantined_count": int(row.get("quarantined_count") or 0),
            "impact": ("blocks_family_gate" if source.get("tier") == "core" and not row_is_healthy(row)
                       else "isolated" if not row_is_healthy(row) else "available"),
            "next_action": row.get("next_action", "none" if row_is_healthy(row) else "retry_or_use_peer_source"),
        })
    return table


def markdown_health_table(rows: Any, registry: dict[str, Any] | None = None) -> str:
    table = health_table(rows, registry)
    if table and all(row["status"] in HEALTHY_RESULTS for row in table):
        return f"Academic sources: {len(table)} healthy; no isolated failures."
    lines = ["| 来源 | 层级 | 状态 | 覆盖窗口 | 候选/隔离 | 对本期影响 | 下一动作 |",
             "|---|---|---|---|---|---|---|"]
    for row in table:
        lines.append("| {source} | {tier} | {status} | {coverage_window} | {candidate_count}/{quarantined_count} | {impact} | {next_action} |".format(**row))
    return "\n".join(lines)
