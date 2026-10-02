#!/usr/bin/env python3
"""Content-bound search evidence for each Shanghai calendar day in a new release."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit


REQUIRED_SOCIAL_CLASSES = {"ai_hot", "reputable_media", "official_company_social", "executive_social"}


def evidence_digest(value: Any) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _http_record(value: Any, start: datetime, end: datetime) -> bool:
    if not isinstance(value, dict):
        return False
    query = urlsplit(str(value.get("query_url") or ""))
    final = urlsplit(str(value.get("final_url") or ""))
    stamp = _timestamp(value.get("retrieved_at"))
    return bool(query.scheme == final.scheme == "https" and query.hostname and final.hostname
                and isinstance(value.get("status_code"), int) and 200 <= value["status_code"] < 400
                and re.fullmatch(r"[0-9a-f]{64}", str(value.get("response_hash") or ""))
                and stamp and stamp >= end.astimezone(stamp.tzinfo)
                and value.get("coverage_start") == start.isoformat()
                and value.get("coverage_end") == end.isoformat())


def _day_bounds(day: str) -> tuple[datetime, datetime]:
    zone = timezone(timedelta(hours=8), "Asia/Shanghai")
    start = datetime.combine(date.fromisoformat(day), time.min, zone)
    return start, start + timedelta(days=1)


def _ai_hot_page(value: Any, start: datetime, end: datetime) -> bool:
    if not isinstance(value, dict):
        return False
    query = urlsplit(str(value.get("query_url") or ""))
    final = urlsplit(str(value.get("final_url") or ""))
    stamp = _timestamp(value.get("retrieved_at"))
    params = parse_qs(query.query)
    since = _timestamp(params.get("since", [None])[0])
    return bool(query.scheme == final.scheme == "https"
                and query.hostname == final.hostname == "aihot.virxact.com"
                and query.path == "/api/public/items"
                and params.get("mode") == ["selected"] and since
                and since <= start.astimezone(since.tzinfo)
                and value.get("status_code") == 200
                and re.fullmatch(r"[0-9a-f]{64}", str(value.get("response_hash") or ""))
                and stamp and stamp >= end.astimezone(stamp.tzinfo))


def validate_ai_hot_window(ai_hot: Any, day: str) -> list[str]:
    """Validate dated candidate discovery, without claiming four-class coverage."""
    start, end = _day_bounds(day)
    failures: list[str] = []
    excluded = ai_hot.get("undated_exclusions", []) if isinstance(ai_hot, dict) else []
    exclusion_valid = (isinstance(excluded, list) and len(excluded) == 1
                       and isinstance(excluded[0], dict)
                       and excluded[0].get("reason") == "missing_or_ambiguous_publishedAt"
                       and re.fullmatch(r"[0-9a-f]{64}", str(excluded[0].get("item_sha256") or "")))
    dated_scope_ok = bool(isinstance(ai_hot, dict) and (
        (ai_hot.get("coverage_status") == "verified"
         and ai_hot.get("missing_timestamp_count") == 0 and not excluded)
        or (ai_hot.get("coverage_status") == "qualified_with_exclusion"
            and ai_hot.get("coverage_claim") == "dated_candidates_only"
            and ai_hot.get("missing_timestamp_count") == 1
            and isinstance(ai_hot.get("inside_window_count"), int)
            and ai_hot["inside_window_count"] > 0 and exclusion_valid)))
    if (not isinstance(ai_hot, dict) or ai_hot.get("coverage_date") != day
            or ai_hot.get("coverage_start") != start.isoformat()
            or ai_hot.get("coverage_end") != end.isoformat()
            or not dated_scope_ok
            or ai_hot.get("pagination_complete") is not True
            or ai_hot.get("source") != "ai_hot" or ai_hot.get("pool_scope") != "ai_hot_selected"
            or ai_hot.get("timezone") != "Asia/Shanghai"
            or not all(type(ai_hot.get(name)) is int and ai_hot[name] >= 0
                       for name in ("retrieved_count", "inside_window_count", "outside_window_count", "missing_timestamp_count"))
            or ai_hot.get("retrieved_count") != (ai_hot.get("inside_window_count", -1)
                                                  + ai_hot.get("outside_window_count", -1)
                                                  + ai_hot.get("missing_timestamp_count", -1))
            or not isinstance(ai_hot.get("pages"), list) or not ai_hot["pages"]
            or not all(_ai_hot_page(page, start, end) for page in ai_hot["pages"])
            or ai_hot.get("response_hash") != hashlib.sha256(json.dumps(ai_hot["pages"], sort_keys=True).encode()).hexdigest()):
        failures.append(f"{day}: AI HOT daily candidate window is incomplete")
    return failures


def validate_social_search(social: Any, day: str) -> list[str]:
    """Validate one day of all four source classes, including AI HOT pagination."""
    start, end = _day_bounds(day)
    if not isinstance(social, dict) or (social.get("coverage_start") != start.isoformat()
                                          or social.get("coverage_end") != end.isoformat()):
        return [f"{day}: social search window mismatch"]
    failures = validate_ai_hot_window(social.get("ai_hot_window"), day)
    records = social.get("source_class_evidence")
    if not isinstance(records, list):
        failures.append(f"{day}: social source-class evidence missing")
    else:
        classes = {record.get("source_class") for record in records if isinstance(record, dict)
                   and _http_record(record, start, end)}
        if not REQUIRED_SOCIAL_CLASSES <= classes:
            failures.append(f"{day}: social source-class search evidence incomplete")
    return failures


def validate_daily_evidence(rows: Any, coverage_start: datetime, coverage_end: datetime,
                            *, contract_version: int = 1) -> list[str]:
    """Validate scope, real records and hashes; this cannot prove a source's semantics."""
    failures: list[str] = []
    shanghai = timezone(timedelta(hours=8), "Asia/Shanghai")
    start_day = coverage_start.astimezone(shanghai).date()
    end_day = coverage_end.astimezone(shanghai).date()
    expected = [(start_day + timedelta(days=index)).isoformat()
                for index in range((end_day - start_day).days)]
    if not isinstance(rows, list) or len(rows) != len(expected):
        return ["one content-bound academic/social search record is required for every covered day"]
    if [row.get("date") if isinstance(row, dict) else None for row in rows] != expected:
        return ["daily search records must be ordered and match every covered date exactly"]
    for row in rows:
        day = row["date"]
        start, end = _day_bounds(day)
        missing_digest = False
        for key in ("academic_search", "social_search"):
            value = row.get(key)
            if not isinstance(value, dict) or row.get(key + "_ref") != evidence_digest(value):
                failures.append(f"{day}: {key} missing or digest mismatch")
                missing_digest = True
        if missing_digest:
            continue
        academic = row["academic_search"]
        from audit_briefing_config import (REQUIRED_ACADEMIC_VENUES, academic_search_venues,
                                           valid_venue_evidence, valid_science_skip_v2)
        if academic.get("date_range") != day:
            failures.append(f"{day}: academic search is not date-scoped")
        if contract_version == 2 and academic.get("academic_search_version") != 3:
            failures.append(f"{day}: new academic search evidence requires version 3")
        if contract_version == 3 and academic.get("academic_search_version") != 4:
            failures.append(f"{day}: pipeline v4 requires academic search evidence version 4")
        venues, checked, _, problems = academic_search_venues(
            {"academic_search": academic}, coverage_contract_version=contract_version)
        if contract_version == 3:
            if checked != 1 or problems:
                failures.append(f"{day}: academic source family gate is incomplete")
        else:
            required = set(academic.get("required_venues") or [])
            if (not academic.get("topics") or not REQUIRED_ACADEMIC_VENUES <= required
                    or not required <= venues or checked != len(academic.get("topics") or []) or problems):
                failures.append(f"{day}: academic venue sweep is incomplete")
        science = [item for item in academic.get("rows", [])
                   if isinstance(item, dict) and item.get("venue") == "science"]
        def science_for_day(item: dict[str, Any]) -> bool:
            if contract_version == 2:
                return valid_science_skip_v2(item, day)
            return valid_venue_evidence(item) and any(
                isinstance(provider, dict) and provider.get("provider") == "science"
                and provider.get("proves_daily_coverage") is True
                and provider.get("coverage_start") == start.isoformat()
                and provider.get("coverage_end") == end.isoformat()
                for provider in item.get("provider_evidence", []))
        if contract_version != 3 and (not science or not all(science_for_day(item) for item in science)):
            failures.append(f"{day}: Science publisher-day coverage or documented skip is missing")
        failures.extend(validate_social_search(row["social_search"], day))
    return failures
