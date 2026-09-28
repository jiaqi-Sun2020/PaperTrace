#!/usr/bin/env python3
"""Evidence-gated candidate expansion for a low-signal daily briefing.

The covered Shanghai day and its mandatory search evidence never change.
This module validates *additional discovery attempts*, not publisher inventory
completeness or the truth of a selected article's claims.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import urlsplit

from academic_venue_sweep import EXPANDED_VENUES, VENUES
from daily_coverage_evidence import evidence_digest, validate_social_search


VERSION = 1
NORMAL = "standard"
SHORTFALL = "verified_shortfall"
ACADEMIC_DAYS = 14
SOCIAL_HOURS = 72
SHANGHAI = timezone(timedelta(hours=8), "Asia/Shanghai")
OPTIONAL_DOMAINS = {venue.key: venue.domain for venue in EXPANDED_VENUES}
REQUIRED_VENUES = {venue.key for venue in VENUES}
REQUIRED_DOMAINS = {venue.key: venue.domain for venue in VENUES}
HEX_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _aware(value: Any) -> datetime | None:
    try:
        stamp = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo is not None else None


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError:
        return None


def _official_host(url: Any, domain: str) -> bool:
    try:
        parsed = urlsplit(str(url or ""))
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    base = domain.split("/", 1)[0]
    return parsed.scheme == "https" and (host == base or host.endswith("." + base))


def _http_attempt(row: Any, domain: str, after: datetime, *, success: bool) -> bool:
    if not isinstance(row, dict):
        return False
    evidence = row.get("evidence")
    if not isinstance(evidence, dict):
        return False
    stamp = _aware(evidence.get("retrieved_at"))
    if not stamp or stamp < after:
        return False
    if not _official_host(evidence.get("query_url"), domain):
        return False
    status = evidence.get("status_code")
    if not isinstance(status, int) or isinstance(status, bool):
        return False
    if status == 0:
        return not success and bool(str(evidence.get("error") or "").strip())
    if not (200 <= status < 600 and _official_host(evidence.get("final_url"), domain)
            and HEX_SHA256.fullmatch(str(evidence.get("response_hash") or ""))):
        return False
    return 200 <= status < 400 if success else True


def default_policy(coverage_date: str) -> dict[str, Any]:
    return {"version": VERSION, "mode": NORMAL, "coverage_date": coverage_date}


def publication_relation(item: dict[str, Any], kind: str, covered: date) -> str | None:
    """Use original publication time, never an aggregator's collection time."""
    raw = item.get("published_at")
    if kind == "social":
        stamp = _aware(raw)
        if stamp is None:
            return None
        local = stamp.astimezone(SHANGHAI)
        start = datetime.combine(covered, time.min, SHANGHAI)
        end = start + timedelta(days=1)
        oldest = end - timedelta(hours=SOCIAL_HOURS)
        if not oldest <= local < end:
            return None
        return "covered_day" if start <= local else "recent_context"
    stamp = _aware(raw)
    if stamp:
        published = stamp.astimezone(SHANGHAI).date()
    else:
        published = _date(raw)
    if published is None or not covered - timedelta(days=ACADEMIC_DAYS - 1) <= published <= covered:
        return None
    return "covered_day" if published == covered else "recent_context"


def validate_policy(config: dict[str, Any], *, required: bool = False) -> list[str]:
    policy = config.get("delivery_expansion")
    if policy is None and not required:
        return []  # Historical configs remain readable.
    if not isinstance(policy, dict):
        return ["delivery_expansion must be an object"]
    errors: list[str] = []
    day = _date(policy.get("coverage_date"))
    if policy.get("version") != VERSION or day is None or policy.get("mode") not in {NORMAL, SHORTFALL}:
        return ["delivery_expansion requires version 1, a coverage date and a supported mode"]
    if policy["mode"] == NORMAL:
        return errors
    end = datetime.combine(day + timedelta(days=1), time.min, SHANGHAI)
    if policy.get("academic_window_start") != (day - timedelta(days=ACADEMIC_DAYS - 1)).isoformat():
        errors.append("shortfall academic lookback must cover exactly 14 calendar days")
    if policy.get("social_window_start") != (day - timedelta(days=2)).isoformat():
        errors.append("shortfall social lookback must cover exactly 72 hours")
    if not str(policy.get("shortfall_reason") or "").strip():
        errors.append("shortfall requires a concrete reason")

    daily = config.get("academic_search") or {}
    expanded = daily.get("expanded_rows") if isinstance(daily, dict) else None
    if not isinstance(expanded, list):
        errors.append("shortfall requires the dated eight-venue expansion ledger")
    else:
        for venue, domain in OPTIONAL_DOMAINS.items():
            rows = [row for row in expanded if isinstance(row, dict) and row.get("venue") == venue]
            if not any(_http_attempt(row, domain, end, success=False) for row in rows):
                errors.append(f"shortfall optional venue attempt is missing: {venue}")

    lookback = policy.get("academic_lookback_search")
    if not isinstance(lookback, dict) or policy.get("academic_lookback_ref") != evidence_digest(lookback):
        errors.append("shortfall academic lookback ledger or digest is missing")
    else:
        expected = f"{day - timedelta(days=ACADEMIC_DAYS - 1)}..{day}"
        if lookback.get("academic_search_version") != 3 or lookback.get("date_range") != expected:
            errors.append("shortfall academic lookback has the wrong window or version")
        rows = lookback.get("rows")
        if not isinstance(rows, list):
            errors.append("shortfall academic lookback rows are missing")
        else:
            for venue, domain in REQUIRED_DOMAINS.items():
                venue_rows = [row for row in rows if isinstance(row, dict) and row.get("venue") == venue]
                required_success = venue != "science"
                if not any(_http_attempt(row, domain, end, success=required_success) for row in venue_rows):
                    errors.append(f"shortfall academic lookback source is incomplete: {venue}")

    social_rows = policy.get("social_lookback")
    previous = [(day - timedelta(days=2)).isoformat(), (day - timedelta(days=1)).isoformat()]
    if not isinstance(social_rows, list) or [row.get("date") if isinstance(row, dict) else None for row in social_rows] != previous:
        errors.append("shortfall social lookback requires both prior Shanghai days in order")
    else:
        for row in social_rows:
            social = row.get("social_search")
            if not isinstance(social, dict) or row.get("social_search_ref") != evidence_digest(social):
                errors.append(f"{row['date']}: shortfall social lookback digest is missing")
            else:
                errors.extend(validate_social_search(social, row["date"]))
    return errors


def disclosure(config: dict[str, Any]) -> str:
    policy = config.get("delivery_expansion") or {}
    if not isinstance(policy, dict) or policy.get("mode") != SHORTFALL:
        return ""
    counts = ((config.get("ranking_manifest") or {}).get("selected_counts") or {})
    same_day = ((config.get("ranking_manifest") or {}).get("shortfall_evidence") or {}).get("same_day_counts") or {}
    academic = counts.get("academic", 0)
    social = counts.get("social", 0)
    day = policy.get("coverage_date")
    return (f"{day} 指定日来源已检索；扩查期刊及近期窗口后仍只有 {academic} 篇学术、{social} 条社会内容通过审核，"
            f"其中指定日首发分别为 {same_day.get('academic', 0)} 篇和 {same_day.get('social', 0)} 条，故本期如实少发。"
            "标为‘近期回看’的条目按原发表日期展示，不代表指定日首发；"
            f"短缺原因：{str(policy.get('shortfall_reason') or '').strip()}")
