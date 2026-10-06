#!/usr/bin/env python3
"""Bounded, replay-verifiable PLOS indexed AI research discovery.

The completed query is evidence of this index query only. It never establishes
publisher-wide daily completeness, article-level verification or a shortfall.
All I/O is supplied by the caller so its collection deadline remains in force.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import parse_qs, urlencode, urlsplit

ENDPOINT = "https://api.plos.org/search"
PAGE_SIZE = 100
MAX_PAGES = 20
MAX_TOTAL_BYTES = 4_000_000
SOURCE_SCOPE = "plos_indexed_ai_research_query"
FIELDS = "id,title,publication_date,article_type,journal,abstract,subject,doc_type"
SHANGHAI = timezone(timedelta(hours=8))


def _window(value):
    parts = str(value).split("..")
    if len(parts) not in (1, 2):
        raise ValueError("plos_window_invalid")
    first, last = date.fromisoformat(parts[0]), date.fromisoformat(parts[-1])
    canonical = first.isoformat() if len(parts) == 1 else first.isoformat() + ".." + last.isoformat()
    if first > last or value != canonical:
        raise ValueError("plos_window_invalid")
    start = datetime.combine(first, datetime.min.time(), SHANGHAI)
    end = datetime.combine(last + timedelta(days=1), datetime.min.time(), SHANGHAI)
    return start, end


def _timestamp(value):
    if not isinstance(value, str):
        raise ValueError("plos_timestamp_invalid")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("plos_timestamp_timezone_missing")
    return stamp


def build_query_url(coverage_window, start=0):
    """A fixed scope, stable sort and exact half-open Shanghai date window."""
    lower, upper = _window(coverage_window)
    utc = lambda stamp: stamp.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = ('(subject:"Artificial intelligence" OR subject:"Machine learning") '
             'AND publication_date:[%s TO %s}' % (utc(lower), utc(upper)))
    return ENDPOINT + "?" + urlencode([
        ("q", query), ("fq", "doc_type:full"), ("fq", 'article_type:"Research Article"'),
        ("fl", FIELDS), ("wt", "json"), ("start", str(start)),
        ("rows", str(PAGE_SIZE)), ("sort", "publication_date asc,id asc"),
    ])


def _business_hash(response):
    business = {key: response[key] for key in ("numFound", "start", "docs")}
    return hashlib.sha256(json.dumps(business, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_response_params(header, expected_url):
    """An optional server query echo must prove the same complete request scope."""
    if not isinstance(header, dict) or "params" not in header:
        return
    params = header["params"]
    expected = parse_qs(urlsplit(expected_url).query, keep_blank_values=True)
    # An extra parser, grouping or filtering option could alter even a zero
    # result. Only the exact query parameters declared by this adapter qualify.
    if not isinstance(params, dict) or set(params) != set(expected):
        raise ValueError("plos_response_params_scope_mismatch")
    for key, wanted in expected.items():
        value = params[key]
        values = [value] if isinstance(value, str) else value
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise ValueError("plos_response_params_type_invalid")
        # fq is an AND of repeated filter expressions, so their order is inert.
        if (sorted(values) if key == "fq" else values) != (sorted(wanted) if key == "fq" else wanted):
            raise ValueError("plos_response_params_scope_mismatch")


def _parse_page(page, coverage_window, offset):
    if not isinstance(page, dict) or not isinstance(page.get("transport"), dict):
        raise ValueError("plos_page_evidence_missing")
    raw = page.get("raw_response_utf8")
    if not isinstance(raw, str):
        raise ValueError("plos_raw_response_missing")
    encoded = raw.encode("utf-8")
    if len(encoded) > MAX_TOTAL_BYTES:
        raise ValueError("plos_response_byte_limit")
    evidence = page["transport"]
    expected = build_query_url(coverage_window, offset)
    if evidence.get("query_url") != expected or evidence.get("final_url") != expected:
        raise ValueError("plos_query_scope_mismatch")
    if type(evidence.get("status_code")) is not int or evidence["status_code"] != 200:
        raise ValueError("plos_http_status_invalid")
    if evidence.get("error") or evidence.get("parse_error"):
        raise ValueError("plos_transport_error")
    if evidence.get("response_hash") != hashlib.sha256(encoded).hexdigest():
        raise ValueError("plos_response_hash_mismatch")
    lower, upper = _window(coverage_window)
    stamp = _timestamp(evidence.get("retrieved_at"))
    if stamp < upper or stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("plos_retrieved_at_invalid")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("plos_payload_invalid")
    header = payload.get("responseHeader")
    if header is not None and (not isinstance(header, dict)
            or type(header.get("status")) is not int or header["status"] != 0
            or ("partialResults" in header and header["partialResults"] is not False)):
        raise ValueError("plos_partial_response")
    _validate_response_params(header, expected)
    response = payload.get("response")
    if not isinstance(response, dict):
        raise ValueError("plos_response_missing")
    if (("numFoundExact" in response and response["numFoundExact"] is not True)
            or ("partialResults" in payload and payload["partialResults"] is not False)):
        raise ValueError("plos_partial_response")
    total = response.get("numFound")
    if type(total) is not int or total < 0 or total > PAGE_SIZE * MAX_PAGES:
        raise ValueError("plos_total_invalid_or_limit")
    if type(response.get("start")) is not int or response["start"] != offset:
        raise ValueError("plos_page_offset_invalid")
    docs = response.get("docs")
    if not isinstance(docs, list) or len(docs) != min(PAGE_SIZE, max(0, total - offset)):
        raise ValueError("plos_page_count_mismatch")
    if page.get("business_hash") != _business_hash(response):
        raise ValueError("plos_business_hash_mismatch")
    for doc in docs:
        if not isinstance(doc, dict):
            raise ValueError("plos_document_invalid")
        if not isinstance(doc.get("id"), str) or not re.fullmatch(r"10\.1371/[A-Za-z0-9._-]+", doc["id"]):
            raise ValueError("plos_doi_invalid")
        if not all(isinstance(doc.get(key), str) and doc[key].strip() for key in ("title", "journal")):
            raise ValueError("plos_document_identity_missing")
        if doc.get("doc_type") != "full" or doc.get("article_type") != "Research Article":
            raise ValueError("plos_article_scope_invalid")
        for key in ("abstract", "subject"):
            if not isinstance(doc.get(key), list) or not doc[key] or not all(isinstance(text, str) for text in doc[key]):
                raise ValueError("plos_document_%s_invalid" % key)
        if not any(part.casefold() in {"artificial intelligence", "machine learning"}
                   for subject in doc["subject"] for part in subject.split("/")):
            raise ValueError("plos_subject_scope_invalid")
        published = _timestamp(doc.get("publication_date"))
        if not lower <= published < upper:
            raise ValueError("plos_document_date_outside_window")
    return response, len(encoded)


def _project(docs):
    matches = []
    for position, doc in enumerate(docs):
        item = copy.deepcopy(doc)
        item.update(doi=doc["id"], url="https://doi.org/" + doc["id"],
                    published_at=doc["publication_date"], description="\n".join(doc["abstract"]),
                    date_semantics="publisher_index_publication_date",
                    date_precision="publisher_supplied",
                    source_id="plos-ai", source_record_index=position)
        matches.append(item)
    return matches


def _replay(row):
    ledger = row.get("plos_query_evidence")
    if not isinstance(ledger, dict) or type(ledger.get("version")) is not int or ledger["version"] != 1:
        raise ValueError("plos_query_evidence_missing")
    if ledger.get("query_complete") is not True or ledger.get("source_scope") != SOURCE_SCOPE:
        raise ValueError("plos_query_incomplete")
    window = row.get("coverage_window")
    _window(window)
    pages = ledger.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
        raise ValueError("plos_pages_missing_or_limit")
    docs, total, byte_count = [], None, 0
    for index, pair in enumerate(pages):
        if not isinstance(pair, dict):
            raise ValueError("plos_page_pair_invalid")
        primary, size = _parse_page(pair.get("primary"), window, index * PAGE_SIZE)
        check, check_size = _parse_page(pair.get("recheck"), window, index * PAGE_SIZE)
        byte_count += size + check_size
        if byte_count > MAX_TOTAL_BYTES:
            raise ValueError("plos_response_byte_limit")
        if pair["primary"]["business_hash"] != pair["recheck"]["business_hash"]:
            raise ValueError("plos_query_changed_during_recheck")
        if _timestamp(pair["recheck"]["transport"]["retrieved_at"]) < _timestamp(pair["primary"]["transport"]["retrieved_at"]):
            raise ValueError("plos_recheck_time_invalid")
        if total is None:
            total = primary["numFound"]
        if primary["numFound"] != total or check["numFound"] != total:
            raise ValueError("plos_total_changed")
        docs.extend(primary["docs"])
    if len(pages) != max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) or len(docs) != total:
        raise ValueError("plos_pagination_incomplete")
    keys = [(_timestamp(doc["publication_date"]), doc["id"]) for doc in docs]
    if keys != sorted(keys):
        raise ValueError("plos_sort_order_invalid")
    if len({doc["id"].casefold() for doc in docs}) != len(docs):
        raise ValueError("plos_duplicate_identity")
    if (type(ledger.get("num_found")) is not int or ledger["num_found"] != total
            or type(ledger.get("response_bytes")) is not int or ledger["response_bytes"] != byte_count):
        raise ValueError("plos_query_summary_mismatch")
    if row.get("evidence") != pages[0]["primary"]["transport"]:
        raise ValueError("plos_primary_evidence_mismatch")
    if row.get("search_url") != build_query_url(window):
        raise ValueError("plos_query_scope_mismatch")
    return docs


def _window_evidence(window, docs):
    lower, upper = _window(window)
    days = [_timestamp(doc["publication_date"]).astimezone(SHANGHAI).date().isoformat() for doc in docs]
    return {"requested_start": lower.date().isoformat(),
            "requested_end": (upper.date() - timedelta(days=1)).isoformat(),
            "observed_earliest_date": min(days) if days else None,
            "observed_latest_date": max(days) if days else None,
            "classification_basis": "complete_indexed_query" if docs else "complete_indexed_query_zero_results",
            "source_scope": SOURCE_SCOPE, "publisher_day_coverage_complete": False,
            "pagination_complete": True,
            "date_precision": "publisher_supplied",
            "date_semantics": "publisher_index_publication_date"}


def plos_evidence_failures(row):
    """Independently replay retained responses; never trust healthy/empty flags."""
    try:
        if not isinstance(row, dict):
            raise ValueError("plos_row_invalid")
        docs = _replay(row)
        if (json.dumps(row.get("matches"), sort_keys=True, ensure_ascii=False)
                != json.dumps(_project(docs), sort_keys=True, ensure_ascii=False)
                or type(row.get("candidate_count")) is not int or row["candidate_count"] != len(docs)):
            raise ValueError("plos_candidates_mismatch")
        if row.get("window_status") != ("matched" if docs else "empty"):
            raise ValueError("plos_window_status_mismatch")
        if (json.dumps(row.get("window_evidence"), sort_keys=True, ensure_ascii=False)
                != json.dumps(_window_evidence(row["coverage_window"], docs), sort_keys=True, ensure_ascii=False)):
            raise ValueError("plos_window_evidence_mismatch")
        if (row.get("coverage_claim") != "discovery_only"
                or type(row.get("quarantined_count")) is not int or row["quarantined_count"] != 0):
            raise ValueError("plos_coverage_claim_invalid")
        return []
    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError) as exc:
        return [str(exc) if str(exc).startswith("plos_") else "plos_evidence_malformed"]


def fetch_plos_row(row, source, target_days, timeout, request_fn):
    """Fetch two consistent bounded passes, preserving evidence on any failure."""
    result = copy.deepcopy(row)
    result.update(matches=[], candidate_count=0, quarantined_count=0,
                  coverage_claim="none", result="degraded", retrieval_status="not_attempted",
                  parse_status="not_attempted", window_status="unknown",
                  next_action="retry_or_use_peer_source")
    ledger = {"version": 1, "source_scope": SOURCE_SCOPE, "query_complete": False,
              "pages": [], "response_bytes": 0}
    result["plos_query_evidence"] = ledger
    try:
        if source.get("source_id") != "plos-ai" or source.get("url") != ENDPOINT:
            raise ValueError("plos_source_declaration_invalid")
        window = result.get("coverage_window")
        lower, upper = _window(window)
        expected_days = {(lower.date() + timedelta(days=index)).isoformat()
                         for index in range((upper - lower).days)}
        if set(target_days) != expected_days:
            raise ValueError("plos_target_days_mismatch")
        result["search_url"] = build_query_url(window)

        def fetch_page(offset):
            result["retrieval_status"] = "error"
            evidence, body = request_fn(build_query_url(window, offset), timeout,
                                        int(source.get("maximum_attempts") or 3))
            if offset == 0 and not ledger["pages"]:
                result["evidence"] = evidence
            if not isinstance(body, bytes):
                raise ValueError("plos_response_bytes_required")
            ledger["failed_response"] = {
                "offset": offset, "transport": copy.deepcopy(evidence),
                "raw_response_utf8_prefix": body[:4096].decode("utf-8", errors="replace"),
                "response_bytes": len(body), "truncated": len(body) > 4096,
            }
            status = evidence.get("status_code")
            result["retrieval_status"] = ("success" if type(status) is int and status == 200
                                          else "blocked" if status in (403, 404) else "error")
            if result["retrieval_status"] != "success":
                raise ValueError("plos_http_status_invalid")
            ledger["response_bytes"] += len(body)
            if ledger["response_bytes"] > MAX_TOTAL_BYTES:
                raise ValueError("plos_response_byte_limit")
            page = {"transport": copy.deepcopy(evidence), "raw_response_utf8": body.decode("utf-8")}
            # Malformed JSON still returns a retained page before the validator rejects it.
            try:
                payload = json.loads(page["raw_response_utf8"])
            except (ValueError, TypeError):
                payload = None
            response = payload.get("response") if isinstance(payload, dict) else None
            if isinstance(response, dict) and all(key in response for key in ("numFound", "start", "docs")):
                page["business_hash"] = _business_hash(response)
            return page

        total = None
        for index in range(MAX_PAGES):
            pair = {"primary": fetch_page(index * PAGE_SIZE)}
            ledger["pages"].append(pair)
            parsed, _ = _parse_page(pair["primary"], window, index * PAGE_SIZE)
            ledger.pop("failed_response", None)
            if total is None:
                total = parsed["numFound"]
                ledger["num_found"] = total
            elif parsed["numFound"] != total:
                raise ValueError("plos_total_changed")
            if (index + 1) * PAGE_SIZE >= total:
                break
        for index, pair in enumerate(ledger["pages"]):
            pair["recheck"] = fetch_page(index * PAGE_SIZE)
            _parse_page(pair["recheck"], window, index * PAGE_SIZE)
            if pair["primary"]["business_hash"] != pair["recheck"]["business_hash"]:
                raise ValueError("plos_query_changed_during_recheck")
            ledger.pop("failed_response", None)
        ledger["query_complete"] = True
        docs = _replay(result)
        result.update(matches=_project(docs), candidate_count=len(docs), retrieval_status="success",
                      parse_status="success", coverage_claim="discovery_only", result="checked",
                      window_status="matched" if docs else "empty", next_action="article_level_review",
                      window_evidence=_window_evidence(window, docs),
                      note="Completed indexed AI Research Article query; publication_date is publisher index metadata. "
                           "This does not prove publisher-wide daily completeness or verified shortfall.")
        failures = plos_evidence_failures(result)
        if failures:
            raise ValueError(failures[0])
    except Exception as exc:
        ledger["query_complete"] = False
        error = str(exc)[:300] or type(exc).__name__
        ledger["failure_reason"] = error
        result.update(result="degraded", parse_status=("error" if result["retrieval_status"] == "success" else "not_attempted"), window_status="unknown",
                      coverage_claim="none", matches=[], candidate_count=0,
                      next_action="retry_or_use_peer_source")
        result["evidence"] = {**result.get("evidence", {}), "parse_error": error}
    return result
