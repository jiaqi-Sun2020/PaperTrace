#!/usr/bin/env python3
"""Content-bound search evidence for each Shanghai calendar day in a new release."""

from __future__ import annotations

import hashlib
import base64
import binascii
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.parse import parse_qs, urlsplit


REQUIRED_SOCIAL_CLASSES = {"ai_hot", "reputable_media", "official_company_social", "executive_social"}

# This bounded discovery contract supports the existing three public queries.
# It cannot establish account-wide publication counts or article eligibility.
RENDERED_SEARCH_TARGETS = {
    "reputable_media": {"techcrunch.com", "channelnewsasia.com", "theguardian.com"},
    "official_company_social": {"x.com/openai", "x.com/anthropicai", "x.com/googledeepmind"},
    "executive_social": {"x.com/sama", "x.com/satyanadella", "x.com/sundarpichai"},
}
RENDERED_RECORD_KEYS = {"evidence_type", "version", "source_class", "query_url", "coverage_start",
                        "coverage_end", "source_targets", "observation", "observation_sha256", "http_receipt"}
OBSERVATION_KEYS = {"page_url", "displayed_query", "query_verified_in_UI", "recorded_at", "method", "browser",
                    "public_result_links", "result_links_observed", "no_results_message_observed",
                    "next_page_link_observed", "scope", "exhaustive_account_coverage",
                    "zero_account_publications_established", "publication_dates_verified", "personalization_possible"}
HTTP_RECEIPT_KEYS = {"query_url", "final_url", "status_code", "response_hash", "retrieved_at", "coverage_start",
                     "coverage_end", "hash_scope", "body_base64"}


def _public_url(value: Any):
    if not isinstance(value, str) or any(ord(ch) < 32 for ch in value):
        return None
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.fragment):
            return None
        if any(re.search(r"cookie|session|token|password|secret|credential", key, re.I)
               for key in parse_qs(parsed.query)):
            return None
        return parsed
    except ValueError:
        return None


def validate_rendered_search_observation(record: Any, day: str) -> list[str]:
    """Bind public DOM observations separately from replayable anonymous HTTP bytes.

    This checks declared provenance and integrity, not whether the observer told
    the truth. Search snippets never verify a selected article or its date.
    """
    start, end = _day_bounds(day)
    bad = [f"{day}: invalid rendered search discovery evidence"]
    if (not isinstance(record, dict) or set(record) != RENDERED_RECORD_KEYS
            or record.get("evidence_type") != "rendered_search_observation"
            or type(record.get("version")) is not int or record["version"] != 1
            or not isinstance(record.get("source_class"), str)
            or record["source_class"] not in RENDERED_SEARCH_TARGETS
            or record.get("coverage_start") != start.isoformat()
            or record.get("coverage_end") != end.isoformat()):
        return bad
    observation, receipt = record.get("observation"), record.get("http_receipt")
    if (not isinstance(observation, dict) or set(observation) != OBSERVATION_KEYS
            or not isinstance(receipt, dict) or set(receipt) != HTTP_RECEIPT_KEYS):
        return bad
    query_url, page_url = _public_url(record.get("query_url")), _public_url(observation.get("page_url"))
    if (not query_url or not page_url or query_url.hostname not in ("www.google.com", "google.com")
            or page_url.hostname != query_url.hostname or query_url.path != page_url.path or query_url.path != "/search"):
        return bad
    query_params, page_params = parse_qs(query_url.query), parse_qs(page_url.query)
    query = observation.get("displayed_query")
    if (not isinstance(query, str) or not query.strip() or len(query) > 2000
            or any(ord(ch) < 32 for ch in query)
            or query_params.get("q") != [query] or page_params.get("q") != [query]
            or not set(query_params) <= {"q", "hl", "start", "num", "filter"}
            or not set(page_params) <= {"q", "hl", "start", "num", "filter"}
            or re.findall(r"after:([^\s)]+)", query) != [(start.date() - timedelta(days=1)).isoformat()]
            or re.findall(r"before:([^\s)]+)", query) != [end.date().isoformat()]):
        return bad
    targets = record.get("source_targets")
    declared = [target.lower() for target in targets] if isinstance(targets, list) and all(
        isinstance(target, str) for target in targets) else []
    query_targets = [target.lower() for target in re.findall(r"site:([^\s)]+)", query)]
    allowed = RENDERED_SEARCH_TARGETS[record["source_class"]]
    if (not declared or len(declared) != len(set(declared)) or sorted(declared) != sorted(query_targets)
            or not set(declared) <= allowed):
        return bad
    expected_query = "(" + " OR ".join("site:" + target for target in targets) + ")"
    if record["source_class"] == "reputable_media":
        expected_query = "(AI OR quantum) " + expected_query
    expected_query += f" after:{(start.date() - timedelta(days=1)).isoformat()} before:{end.date().isoformat()}"
    if query != expected_query:
        return bad
    stamp = _timestamp(observation.get("recorded_at"))
    if (observation.get("method") != "supported_browser_dom" or not isinstance(observation.get("browser"), str)
            or not observation["browser"].strip() or not stamp or stamp < end.astimezone(stamp.tzinfo)
            or observation.get("query_verified_in_UI") is not True
            or observation.get("scope") != "observed_page_only"
            or observation.get("exhaustive_account_coverage") is not False
            or observation.get("zero_account_publications_established") is not False
            or observation.get("publication_dates_verified") is not False
            or observation.get("personalization_possible") is not True
            or type(observation.get("no_results_message_observed")) is not bool
            or (observation.get("next_page_link_observed") is not None
                and type(observation["next_page_link_observed"]) is not bool)):
        return bad
    results, count = observation.get("public_result_links"), observation.get("result_links_observed")
    if (not isinstance(results, list) or type(count) is not int or count != len(results) or count > 100
            or observation["no_results_message_observed"] != (count == 0)
            or (count == 0 and observation["next_page_link_observed"] is True)):
        return bad
    urls = []
    for result in results:
        if (not isinstance(result, dict) or set(result) != {"title", "url"}
                or not isinstance(result.get("title"), str) or not result["title"].strip()
                or len(result["title"]) > 1000):
            return bad
        url = _public_url(result.get("url"))
        if not url:
            return bad
        host = url.hostname.lower()
        if host.startswith("www."):
            host = host[4:]
        if not any(host == target.split("/")[0] and ("/" not in target
                   or url.path.lower().startswith("/" + target.split("/", 1)[1] + "/")) for target in declared):
            return bad
        urls.append(result["url"])
    if len(urls) != len(set(urls)):
        return bad
    if record.get("observation_sha256") != evidence_digest(observation)[7:]:
        return bad
    final = _public_url(receipt.get("final_url"))
    if (not final or final.hostname != query_url.hostname or final.path != "/search"
            or parse_qs(final.query).get("q") != [query]):
        return bad
    if (not _http_record(receipt, start, end) or receipt.get("query_url") != record["query_url"]
            or receipt.get("hash_scope") != "raw_http_bytes"
            or receipt.get("response_hash") == record["observation_sha256"]
            or not isinstance(receipt.get("body_base64"), str) or len(receipt["body_base64"]) > 1400000):
        return bad
    try:
        raw = base64.b64decode(receipt["body_base64"], validate=True)
    except (ValueError, binascii.Error):
        return bad
    if not raw or hashlib.sha256(raw).hexdigest() != receipt["response_hash"]:
        return bad
    return []


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
    common=bool(query.scheme == final.scheme == 'https' and query.hostname==final.hostname
                and (value.get('status_code')==200 or value.get('status_code')==304 and value.get('cache_validated') is True and value.get('etag') and value.get('representation_origin_sha256')==value.get('response_hash'))
                and re.fullmatch(r'[0-9a-f]{64}',str(value.get('response_hash') or ''))
                and stamp and stamp>=end.astimezone(stamp.tzinfo))
    if query.hostname=='aihot.news':
        return bool(common and query.path==final.path=='/api/v1/items'
                    and params.get('mode')==['selected'] and params.get('window')==['7d']
                    and params.get('by')==['published'] and len(params.get('limit',[]))==1
                    and params['limit'][0].isdigit() and 1<=int(params['limit'][0])<=100
                    and not set(params)-{'mode','window','by','limit','category','q','cursor'})
    since = _timestamp(params.get('since', [None])[0])
    return bool(common and query.hostname=='aihot.virxact.com' and query.path=='/api/public/items'
                and params.get('mode')==['selected'] and since and since<=start.astimezone(since.tzinfo))



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
    if social.get('ai_fixed_pool') is not None:
        from ai_social_sources import validate_pool
        failures.extend(validate_pool(social['ai_fixed_pool'],day))

    records = social.get("source_class_evidence")
    if not isinstance(records, list):
        failures.append(f"{day}: social source-class evidence missing")
    else:
        classes = set()
        for record in records:
            if not isinstance(record, dict):
                continue
            if {"evidence_type", "observation", "observation_sha256", "http_receipt"} & set(record):
                # Typed evidence never falls back to the older metadata contract.
                issues = validate_rendered_search_observation(record, day)
                failures.extend(issues)
                if not issues:
                    classes.add(record["source_class"])
            elif _http_record(record, start, end):
                classes.add(record.get("source_class"))
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
