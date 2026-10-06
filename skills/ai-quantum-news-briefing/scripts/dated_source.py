"""Bounded, replay-verified publisher/index calendar-date queries.

Calendar dates remain calendar dates. A completed registered query is not a
publisher census, article verification, or approval of a delivery shortfall.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit, parse_qs

PAGE_SIZE = 100
MAX_PAGES = 20
MAX_BYTES = 4_000_000
ADAPTERS = {"aps_harvest", "crossref_dated"}


def window_days(window):
    parts = str(window).split("..")
    if len(parts) not in (1, 2):
        raise ValueError("dated_window_invalid")
    first, last = date.fromisoformat(parts[0]), date.fromisoformat(parts[-1])
    if first > last or (last - first).days > 31 or window != (first.isoformat() if len(parts) == 1 else first.isoformat() + ".." + last.isoformat()):
        raise ValueError("dated_window_invalid")
    return first, last


def query_url(source, window, cursor="*"):
    first, last = window_days(window)
    if source["adapter"] == "aps_harvest":
        params = dict(from_=first.isoformat(), until=last.isoformat(), date="published",
                      journals=source["journal_code"], set="openaccess", per_page=PAGE_SIZE)
        params["from"] = params.pop("from_")
    else:
        params = {"filter": "from-online-pub-date:%s,until-online-pub-date:%s,type:journal-article" % (first, last),
                  "rows": PAGE_SIZE, "cursor": cursor}
    return source["url"] + "?" + urlencode(params)


def _check_url(url, source, window):
    parsed, declared = urlsplit(url), urlsplit(source["url"])
    expected = parse_qs(urlsplit(query_url(source, window)).query)
    actual = parse_qs(parsed.query)
    if (parsed.scheme != "https" or parsed.netloc != declared.netloc or parsed.path != declared.path
            or parsed.username or parsed.password or parsed.fragment):
        raise ValueError("dated_query_scope_mismatch")
    extra = {"page"} if source["adapter"] == "aps_harvest" else set()
    if set(actual) - set(expected) - extra:
        raise ValueError("dated_query_scope_mismatch")
    for key, value in expected.items():
        if key != "cursor" and actual.get(key) != value:
            raise ValueError("dated_query_scope_mismatch")
    if source["adapter"] == "aps_harvest" and "page" in actual:
        if len(actual["page"]) != 1 or not re.fullmatch(r"[1-9][0-9]*", actual["page"][0]):
            raise ValueError("dated_page_invalid")
    if source["adapter"] == "crossref_dated" and (len(actual.get("cursor", [])) != 1 or not actual["cursor"][0]):
        raise ValueError("dated_cursor_invalid")


def _stamp(value):
    stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("dated_transport_time_invalid")
    return stamp


def _page(page, source, window):
    if not isinstance(page, dict) or not isinstance(page.get("raw_response_utf8"), str):
        raise ValueError("dated_page_missing")
    raw = page["raw_response_utf8"].encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise ValueError("dated_byte_limit")
    e = page["transport"]
    _check_url(e["query_url"], source, window)
    if e.get("final_url") != e["query_url"] or type(e.get("status_code")) is not int or e["status_code"] != 200 or e.get("error"):
        raise ValueError("dated_transport_invalid")
    if e.get("response_hash") != hashlib.sha256(raw).hexdigest():
        raise ValueError("dated_response_hash_mismatch")
    _, last = window_days(window)
    stamp = _stamp(e["retrieved_at"])
    end = datetime.combine(last + timedelta(days=1), datetime.min.time(), timezone(timedelta(hours=8)))
    if stamp < end or stamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        raise ValueError("dated_transport_time_invalid")
    payload = json.loads(raw)
    if source["adapter"] == "aps_harvest":
        docs = payload["data"]
        links = str(e.get("link_header", ""))
        found = re.findall(r'<([^>]+)>\s*;\s*rel="?next"?', links)
        if len(found) > 1 or len(links) > 8192 or ("next" in links and not found):
            raise ValueError("dated_next_link_invalid")
        next_url = found[0] if found else None
        total = None
    else:
        if payload.get("status") != "ok" or payload.get("message-type") != "work-list":
            raise ValueError("dated_response_type_invalid")
        m = payload["message"]
        docs, total = m["items"], m["total-results"]
        if type(total) is not int or total < 0 or total > PAGE_SIZE * MAX_PAGES:
            raise ValueError("dated_total_invalid")
        next_url = query_url(source, window, m["next-cursor"]) if docs and m.get("next-cursor") else None
    if not isinstance(docs, list) or len(docs) > PAGE_SIZE or not all(isinstance(d, dict) for d in docs):
        raise ValueError("dated_documents_invalid")
    if next_url:
        _check_url(next_url, source, window)
    return docs, total, next_url, len(raw)


def _project(docs, source, window):
    first, last = window_days(window)
    matches, quarantined, identities = [], [], set()
    for position, doc in enumerate(docs):
        if source["adapter"] == "aps_harvest":
            doi, title = doc.get("id"), doc.get("title")
            if isinstance(title, dict):
                title = title.get("value")
            if (doc.get("type") != "article" or not isinstance(doc.get("journal"), dict)
                    or doc["journal"].get("id") != source["journal_code"] or not str(doi).startswith("10.1103/")):
                raise ValueError("dated_article_scope_invalid")
            published = doc.get("date")
        else:
            doi, titles = doc.get("DOI"), doc.get("title")
            title = titles[0] if isinstance(titles, list) and titles else None
            if (doc.get("type") != "journal-article" or source["issn"] not in doc.get("ISSN", [])
                    or not str(doi).startswith(source["doi_prefix"] + "/")):
                raise ValueError("dated_article_scope_invalid")
            if (not isinstance(doi, str) or not re.fullmatch(r"10\.[0-9]{4,9}/[^\s]+", doi)
                    or not isinstance(title, str) or not title.strip()):
                raise ValueError("dated_article_identity_invalid")
            if doi.casefold() in identities:
                raise ValueError("dated_duplicate_identity")
            parts = (doc.get("published-online") or {}).get("date-parts")
            if (not isinstance(parts, list) or len(parts) != 1 or not isinstance(parts[0], list)
                    or len(parts[0]) != 3 or any(type(p) is not int for p in parts[0])):
                quarantined.append({"record_index": position, "code": "publication_calendar_date_unresolved"})
                identities.add(doi.casefold())
                continue
            published = date(*parts[0]).isoformat()
        if (not isinstance(doi, str) or not re.fullmatch(r"10\.[0-9]{4,9}/[^\s]+", doi)
                or not isinstance(title, str) or not title.strip()):
            raise ValueError("dated_article_identity_invalid")
        key = doi.casefold()
        if key in identities:
            raise ValueError("dated_duplicate_identity")
        identities.add(key)
        day = date.fromisoformat(published)
        if not first <= day <= last:
            raise ValueError("dated_article_outside_window")
        abstract = doc.get("abstract", "")
        if isinstance(abstract, dict):
            abstract = abstract.get("value", "")
        item = copy.deepcopy(doc)
        item["source_record"] = copy.deepcopy(doc)
        item.update(title=title, doi=doi, url="https://doi.org/" + doi, published_at=published,
                    description=abstract, source_id=source["source_id"], source_record_index=position,
                    date_precision="day", date_semantics="index_publication_calendar_date")
        matches.append(item)
    return matches, quarantined


def _replay(row, source):
    ledger, window = row["dated_query_evidence"], row["coverage_window"]
    if (type(ledger.get("version")) is not int or ledger["version"] != 1
            or ledger.get("query_complete") is not True or ledger.get("scope_id") != source["scope_id"]):
        raise ValueError("dated_ledger_invalid")
    pages = ledger["pages"]
    if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_PAGES:
        raise ValueError("dated_pagination_missing")
    docs, expected, total, size, seen = [], query_url(source, window), None, 0, set()
    for pair in pages:
        a, b = pair["primary"], pair["recheck"]
        if expected is None or expected in seen or a["transport"]["query_url"] != expected or b["transport"]["query_url"] != expected:
            raise ValueError("dated_pagination_chain_invalid")
        seen.add(expected)
        da, ta, na, sa = _page(a, source, window)
        db, tb, nb, sb = _page(b, source, window)
        size += sa + sb
        if size > MAX_BYTES:
            raise ValueError("dated_byte_limit")
        if (da, ta, na) != (db, tb, nb) or _stamp(b["transport"]["retrieved_at"]) < _stamp(a["transport"]["retrieved_at"]):
            raise ValueError("dated_query_changed")
        if source["adapter"] == "crossref_dated":
            if total is not None and ta != total:
                raise ValueError("dated_total_changed")
            total = ta
        docs.extend(da)
        if total is not None:
            if len(docs) > total or (len(docs) < total and (not da or not na)):
                raise ValueError("dated_pagination_incomplete")
            expected = na if len(docs) < total else None
        else:
            expected = na
    if expected is not None or (total is not None and len(docs) != total):
        raise ValueError("dated_pagination_incomplete")
    if type(ledger.get("raw_count")) is not int or ledger["raw_count"] != len(docs) or type(ledger.get("response_bytes")) is not int or ledger["response_bytes"] != size:
        raise ValueError("dated_summary_mismatch")
    if row["evidence"] != pages[0]["primary"]["transport"] or row["search_url"] != query_url(source, window):
        raise ValueError("dated_primary_evidence_mismatch")
    return docs


def _window_evidence(source, window, docs):
    first, last = window_days(window)
    return dict(requested_start=first.isoformat(), requested_end=last.isoformat(),
                classification_basis="complete_registered_query" if docs else "complete_registered_query_zero_results",
                source_scope=source["scope_id"], provider_id=source["provider_id"],
                pagination_complete=True, publisher_day_coverage_complete=False,
                date_precision="day", date_semantics="index_publication_calendar_date")


def dated_evidence_failures(row, source):
    try:
        docs = _replay(row, source)
        matches, excluded = _project(docs, source, row["coverage_window"])
        if (row.get("matches") != matches or type(row.get("candidate_count")) is not int
                or row["candidate_count"] != len(matches) or row.get("quarantine_evidence") != excluded
                or type(row.get("quarantined_count")) is not int or row["quarantined_count"] != len(excluded)
                or row.get("window_evidence") != _window_evidence(source, row["coverage_window"], docs)
                or row.get("window_status") != ("matched" if docs else "empty") or row.get("coverage_claim") != "discovery_only"):
            raise ValueError("dated_projection_mismatch")
        return []
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError, UnicodeError) as exc:
        return [str(exc) if str(exc).startswith("dated_") else "dated_evidence_malformed"]


def fetch_dated_row(row, source, target_days, timeout, request_fn):
    result = copy.deepcopy(row)
    result.update(matches=[], candidate_count=0, quarantined_count=0, coverage_claim="none",
                  result="degraded", retrieval_status="not_attempted", parse_status="not_attempted",
                  window_status="unknown", next_action="retry_or_use_independent_query")
    ledger = dict(version=1, scope_id=source["scope_id"], query_complete=False, pages=[], raw_count=0, response_bytes=0)
    result["dated_query_evidence"] = ledger
    try:
        first, last = window_days(row["coverage_window"])
        if set(target_days) != {(first + timedelta(days=i)).isoformat() for i in range((last-first).days+1)}:
            raise ValueError("dated_target_days_mismatch")
        url = query_url(source, row["coverage_window"])
        result["search_url"] = url
        seen, docs, total = set(), [], None
        for _ in range(MAX_PAGES):
            if url in seen:
                raise ValueError("dated_cursor_loop")
            seen.add(url)
            e, body = request_fn(url, timeout, 3)
            if not ledger["pages"]:
                result["evidence"] = copy.deepcopy(e)
            result["retrieval_status"] = "success" if e.get("status_code") == 200 else "error"
            if not isinstance(body, bytes) or len(body) + ledger["response_bytes"] > MAX_BYTES:
                raise ValueError("dated_byte_limit")
            ledger["last_response"] = {"transport": copy.deepcopy(e), "response_bytes": len(body),
                                       "raw_response_utf8_prefix": body[:4096].decode("utf-8", errors="replace"),
                                       "truncated": len(body) > 4096}
            page = dict(transport=copy.deepcopy(e), raw_response_utf8=body.decode("utf-8"))
            items, count, nxt, size = _page(page, source, row["coverage_window"])
            if total is not None and count != total:
                raise ValueError("dated_total_changed")
            total = count
            ledger["pages"].append({"primary": page})
            ledger["response_bytes"] += size
            docs.extend(items)
            if total is not None and len(docs) == total:
                break
            if not nxt:
                if total is not None and len(docs) != total:
                    raise ValueError("dated_pagination_incomplete")
                break
            url = nxt
        else:
            raise ValueError("dated_page_limit")
        for pair in ledger["pages"]:
            e, body = request_fn(pair["primary"]["transport"]["query_url"], timeout, 3)
            if not isinstance(body, bytes) or len(body) + ledger["response_bytes"] > MAX_BYTES:
                raise ValueError("dated_byte_limit")
            pair["recheck"] = dict(transport=copy.deepcopy(e), raw_response_utf8=body.decode("utf-8"))
            ledger["response_bytes"] += len(body)
        ledger.update(query_complete=True, raw_count=len(docs))
        matches, excluded = _project(_replay(result, source), source, row["coverage_window"])
        result.update(matches=matches, candidate_count=len(matches), quarantined_count=len(excluded), quarantine_evidence=excluded,
                      window_evidence=_window_evidence(source, row["coverage_window"], docs),
                      retrieval_status="success", parse_status="success", window_status="matched" if docs else "empty",
                      coverage_claim="discovery_only", result="checked", next_action="article_level_review")
        failures = dated_evidence_failures(result, source)
        if failures:
            raise ValueError(failures[0])
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError, UnicodeError) as exc:
        ledger["query_complete"] = False
        result.update(result="degraded", parse_status="error" if result["retrieval_status"] == "success" else "not_attempted",
                      window_status="unknown", coverage_claim="none", matches=[], candidate_count=0)
        result["failure_code"] = str(exc) if str(exc).startswith("dated_") else "dated_evidence_malformed"
    return result
