#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch AI HOT candidates and convert them into briefing config items."""

from __future__ import annotations

import gzip
import io
import argparse
import hashlib
import html
import json
import re
import sys
import time as monotonic_clock
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from collection_checkpoint import atomic_json, load_checkpoint, save_checkpoint

_HTTP_DEADLINE = float("inf")


UA = "PaperTrace-aihot-v1/1.0"
BASE_URL = "https://aihot.news"
CATEGORY_LABELS = {
    "ai-models": "Models and frontier AI",
    "ai-products": "AI products",
    "industry": "AI industry",
    "paper": "AI research papers",
    "tip": "Methods and viewpoints",
}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def clean_text(value: Any, limit: int = 4000) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def fetch_response(url: str, *, etag=None, cached_body=None) -> tuple[str, dict[str, Any]]:
    remaining = _HTTP_DEADLINE - monotonic_clock.monotonic()
    if remaining <= 0:
        raise TimeoutError("collection_deadline")
    headers={"User-Agent": UA, "Accept-Encoding": "gzip"}
    if etag and cached_body is not None: headers['If-None-Match']=etag
    request = urllib.request.Request(url, headers=headers)
    try: response=urllib.request.urlopen(request, timeout=min(30, remaining))
    except urllib.error.HTTPError as exc:
        if exc.code!=304 or not etag or cached_body is None: raise
        body=cached_body.encode('utf-8')
        if len(body)>8_000_000: raise ValueError('response_too_large')
        return cached_body, {'query_url':url,'final_url':url,'status_code':304,'etag':etag,
            'cache_validated':True,'representation_origin_sha256':hashlib.sha256(body).hexdigest(),
            'response_hash':hashlib.sha256(body).hexdigest(),'hash_scope':'decoded_representation_bytes',
            'retrieved_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat()}
    with response:
        body = response.read(8_000_001)
        if getattr(response,"headers",{}).get("Content-Encoding") == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream: body = stream.read(8_000_001)
        if len(body) > 8_000_000:
            raise ValueError("response_too_large")
        return body.decode("utf-8"), {
            "query_url": url, "final_url": response.geturl(),
            "status_code": int(response.status), "hash_scope": "decoded_representation_bytes",
            "etag": getattr(response,"headers",{}).get("ETag"),
            "cache_control": getattr(response,"headers",{}).get("Cache-Control"),
            "response_hash": hashlib.sha256(body).hexdigest(),
            "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        }


def fetch_text(url: str) -> str:
    return fetch_response(url)[0]


def coverage_window(day: str) -> tuple[datetime, datetime]:
    zone = timezone(timedelta(hours=8), "Asia/Shanghai")
    start = datetime.combine(date.fromisoformat(day), time.min, zone)
    return start, start + timedelta(days=1)


def published_in_window(raw: dict[str, Any], start: datetime, end: datetime) -> bool | None:
    value = raw.get("publishedAt")
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        return None
    return start <= stamp.astimezone(start.tzinfo) < end


def iso_from_rss_date(value: str) -> str:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return ""
    if parsed.tzinfo is None:
        return ""  # Do not invent a timezone for a daily coverage decision.
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_original_url(description: str, permalink: str) -> str:
    for match in re.findall(r"https?://[^\s<>\]\)\"']+", description or ""):
        stripped = match.rstrip(".,;，。")
        if not any(host in stripped for host in ("aihot.virxact.com","aihot.news")):
            return stripped
    return permalink


def extract_concepts(*parts: str) -> list[str]:
    joined = " ".join(parts)
    candidates = re.findall(r"\b[A-Z][A-Za-z0-9_.+-]{1,}\b|\b[A-Za-z]+(?:-[A-Za-z0-9]+)+\b", joined)
    seen: set[str] = set()
    concepts: list[str] = []
    for value in candidates:
        key = value.lower()
        if key in seen or key in {"the", "and", "for", "with", "from"}:
            continue
        seen.add(key)
        concepts.append(value[:80])
        if len(concepts) >= 8:
            break
    return concepts


def api_scope(args: argparse.Namespace) -> dict[str, Any]:
    coverage_day = getattr(args, "coverage_date", None)
    params = {"mode": args.mode, "limit": str(args.take), "window": "7d", "by": "published"}
    for field, key in (("category", "category"), ("query", "q")):
        if getattr(args, field, None): params[key] = getattr(args, field)
    return {"kind": "aihot_api_v1", "base_url": BASE_URL, "params": params,
            "coverage_date": coverage_day, "timezone": "Asia/Shanghai"}


def page_values(data,params=None):
    if (not isinstance(data,dict) or type(data.get('schemaVersion')) is not int or data['schemaVersion']!=1
            or not isinstance(data.get('query'),dict) or not isinstance(data.get('items'),list)):
        raise ValueError('aihot_v1_response_invalid')
    if params is not None:
        expected={key:params.get(key) for key in ('mode','category','q','window','by')}
        if any(data['query'].get(key)!=value for key,value in expected.items()):
            raise ValueError('aihot_query_binding_changed')
    page=data.get('page')
    if (not isinstance(page,dict) or type(page.get('count')) is not int or page['count']!=len(data['items'])
            or type(page.get('hasMore')) is not bool or not all(isinstance(x,dict) and isinstance(x.get('id'),str) and x['id'] for x in data['items'])
            or page['hasMore'] and (not isinstance(page.get('nextCursor'),str) or not page['nextCursor'])
            or not page['hasMore'] and page.get('nextCursor') is not None):
        raise ValueError('aihot_v1_page_invalid')
    return page['nextCursor'],page['hasMore']



def pagination_budget(args: argparse.Namespace) -> float:
    base = getattr(args, "budget_seconds", 200)
    if not 0 < base <= 200:
        raise ValueError("initial collection budget must be in (0, 200]")
    recovery = load_checkpoint(getattr(args, "checkpoint", None), api_scope(args)).get("recovery", {})
    level = recovery.get("budget_level", 0) if isinstance(recovery, dict) else 0
    if type(level) is not int or not 0 <= level <= 2:
        raise ValueError("checkpoint_budget_invalid")
    return min(800, base * (2 ** level))


def api_items(args: argparse.Namespace, *, on_failure=None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    global _HTTP_DEADLINE
    checkpoint=getattr(args,'checkpoint',None)
    if checkpoint is not None and Path(checkpoint).is_file():
        checkpoint=Path(checkpoint)
        if checkpoint.stat().st_size>32_000_000: raise ValueError('aihot_checkpoint_too_large_preserved')
        raw=checkpoint.read_bytes()
        try: existing=json.loads(raw.decode('utf-8'))
        except (ValueError,UnicodeError): raise ValueError('aihot_checkpoint_corrupt_preserved') from None
        from collection_checkpoint import fingerprint
        if existing.get('version')!=1 or existing.get('payload_sha256')!=fingerprint(existing.get('payload')):
            raise ValueError('aihot_checkpoint_incompatible_preserved')
        if existing.get('scope_sha256')!=fingerprint(api_scope(args)):
            backup=checkpoint.parent/'.aihot_checkpoint_backups'/(checkpoint.name+'.'+hashlib.sha256(raw).hexdigest())
            if backup.exists():
                if backup.read_bytes()!=raw: raise ValueError('aihot_checkpoint_backup_conflict')
            else:
                from daily_revisions import atomic_bytes
                atomic_bytes(backup,raw)
    budget = pagination_budget(args)
    previous = _HTTP_DEADLINE
    _HTTP_DEADLINE = monotonic_clock.monotonic() + budget
    try:
        return _api_items(args, on_failure=on_failure)
    finally:
        _HTTP_DEADLINE = previous


def _api_items(args: argparse.Namespace, *, on_failure=None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coverage_day = getattr(args, "coverage_date", None)
    start, end = coverage_window(coverage_day) if coverage_day else (None, None)
    scope = api_scope(args)
    params = scope["params"]
    pages: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    finished = False
    failure = ""
    checkpoint = getattr(args, "checkpoint", None)
    responses: list[dict[str, Any]] = []
    saved_payload = load_checkpoint(checkpoint, scope)
    saved = saved_payload.get("responses", [])
    recovery = saved_payload.get("recovery", {})
    if not isinstance(recovery, dict):
        raise ValueError("checkpoint_recovery_invalid")
    if recovery.get("action_required"):
        return [], {"coverage_status": "partial", "pagination_complete": False,
                    "failure": recovery.get("failure", "checkpoint_no_progress"),
                    "recovery": recovery, "retrieved_count": 0}
    revalidated = 0
    restarted = False
    budget = pagination_budget(args)
    started = monotonic_clock.monotonic()
    level = recovery.get("budget_level", 0)
    # Validate the whole cached prefix, not just page one: edits can occur on
    # middle pages while the first page remains unchanged.
    if isinstance(saved, list) and saved and len(saved) <= 100:
        try:
            for index, record in enumerate(saved):
                if monotonic_clock.monotonic() >= _HTTP_DEADLINE:
                    raise TimeoutError("collection_deadline")
                body, evidence = record["body"], record["evidence"]
                query = dict(params)
                if cursor:
                    query["cursor"] = cursor
                if (evidence.get("query_url") != BASE_URL + "/api/v1/items?" + urllib.parse.urlencode(query)
                        or hashlib.sha256(body.encode("utf-8")).hexdigest() != evidence.get("response_hash")
                        or evidence.get("status_code") not in (200,304)):
                    raise ValueError("checkpoint_page_invalid")
                if evidence.get('etag'):
                    _, fresh = fetch_response(evidence['query_url'],etag=evidence['etag'],cached_body=body)
                else:
                    _, fresh = fetch_response(evidence["query_url"])
                if (fresh.get("response_hash") != evidence["response_hash"]
                        or fresh.get("status_code") not in (200,304)
                        or fresh.get("query_url") != evidence["query_url"]
                        or urllib.parse.urlsplit(str(fresh.get("final_url") or "")).hostname != "aihot.news"):
                    raise ValueError("pool_changed_restart")
                revalidated += 1
                data = json.loads(body)
                next_cursor, has_more = page_values(data,params)
                terminal = not has_more
                if (not isinstance(data.get("items"), list) or not all(isinstance(item, dict) for item in data["items"])
                        or terminal and index != len(saved) - 1 or not terminal and
                        (not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors)):
                    raise ValueError("checkpoint_cursor_invalid")
                pages.append(fresh)
                items.extend(data["items"])
                responses.append({"body": body, "evidence": fresh})
                if terminal:
                    finished = True
                    break
                seen_cursors.add(next_cursor)
                cursor = next_cursor
        except urllib.error.HTTPError as exc:
            if on_failure is not None: on_failure(exc)
            failure='http_'+str(exc.code)
        except TimeoutError:
            failure = "collection_deadline"
            pages, items, responses, seen_cursors, cursor = [], [], [], set(), None
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            restarted = True
            pages, items, responses, seen_cursors, cursor = [], [], [], set(), None
    for _ in range((100 if coverage_day else 1) - len(pages)):
        if failure or finished:
            break
        if monotonic_clock.monotonic() >= _HTTP_DEADLINE:
            failure = "collection_deadline"
            break
        page_params = dict(params)
        if cursor:
            page_params["cursor"] = cursor
        url = BASE_URL + "/api/v1/items?" + urllib.parse.urlencode(page_params)
        try:
            body, evidence = fetch_response(url)
            data = json.loads(body)
            page_items = data["items"]
            if not isinstance(page_items, list) or not all(isinstance(item, dict) for item in page_items):
                raise ValueError("items is not a list")
            next_cursor, has_next = page_values(data,params)
            pages.append(evidence)
            items.extend(page_items)
            if has_next is False:
                responses.append({"body": body, "evidence": evidence})
                finished = True
                break
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
                raise ValueError("missing or repeated cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            responses.append({"body": body, "evidence": evidence})
            save_checkpoint(checkpoint, scope, {"responses": responses, "recovery": recovery})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if on_failure is not None:
                on_failure(exc)
            failure = ('http_'+str(exc.code) if isinstance(exc,urllib.error.HTTPError) else 'collection_deadline' if isinstance(exc,TimeoutError) else 'response_validation_failed' if isinstance(exc,(ValueError,KeyError,TypeError)) else 'transport_failure')
            break
    if not finished and not failure:
        failure = "pagination_page_limit"
    newly_fetched = max(0, len(pages) - (0 if restarted else revalidated))
    no_progress = 0 if finished or newly_fetched else int(recovery.get("no_progress", 0)) + 1
    restarts = 0 if finished else int(recovery.get("restarts", 0)) + int(restarted)
    action_required = bool(not finished and (failure == "pagination_page_limit" or
                           failure == "collection_deadline" and level >= 2 or
                           no_progress >= 3 or restarts >= 3))
    if action_required:
        failure = ("pagination_budget_exhausted" if failure == "collection_deadline" else
                   "pool_unstable" if restarts >= 3 else "checkpoint_no_progress" if no_progress >= 3 else failure)
    recovery = {"budget_level": min(2, level + 1) if failure == "collection_deadline" else level,
                "budget_seconds": budget, "revalidated_pages": revalidated, "new_pages": newly_fetched,
                "elapsed_seconds": max(0, monotonic_clock.monotonic() - started),
                "no_progress": no_progress, "restarts": restarts, "failure": failure,
                "action_required": action_required}
    # Keep the original prefix if validation timed out; it is still only a
    # checkpoint. A larger bounded attempt must revalidate it before admission.
    retained = saved if not responses and failure in {"collection_deadline", "pagination_budget_exhausted"} else responses
    save_checkpoint(checkpoint, scope, {"responses": retained, "recovery": recovery})
    inside: list[dict[str, Any]] = []
    outside = missing = 0
    undated_exclusions: list[dict[str, str]] = []
    if start and end:
        for item in items:
            match = published_in_window(item, start, end)
            if match is True:
                inside.append(item)
            elif match is False:
                outside += 1
            else:
                missing += 1
                undated_exclusions.append({
                    "item_sha256": hashlib.sha256(json.dumps(
                        item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                    "reason": "missing_or_ambiguous_publishedAt",
                })
    else:
        inside = items[:args.take]
    identities = [item.get('id') for item in items]
    if len(identities)!=len(set(identities)):
        failure='aihot_duplicate_identity'; finished=False
    # The API retains at most seven days. An older query is clipped server-side.
    retention_ok = bool(start and end and end <= datetime.now(timezone.utc)
                        and start.astimezone(timezone.utc) >= datetime.now(timezone.utc) - timedelta(days=7))
    since_ok = True
    if start and args.since:
        try:
            since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
            since_ok = since.tzinfo is not None and since <= start.astimezone(since.tzinfo)
        except ValueError:
            since_ok = False
    pages_valid = bool(pages and all(
        (page.get("status_code") == 200 or page.get("status_code") == 304 and page.get("cache_validated") is True and page.get("representation_origin_sha256")==page.get("response_hash"))
        and urllib.parse.urlsplit(str(page.get("final_url") or "")).hostname == "aihot.news"
        and len(str(page.get("response_hash") or "")) == 64
        for page in pages))
    complete = bool(start and finished and not failure and not missing and retention_ok and since_ok and pages_valid)
    qualified = bool(start and finished and not failure and missing == 1 and inside
                     and retention_ok and since_ok and pages_valid)
    evidence = {
        "recovery": recovery,
        "api_version": 1, "source": "ai_hot", "pool_scope": f"ai_hot_{args.mode}",
        "coverage_date": coverage_day, "coverage_start": start.isoformat() if start else None,
        "coverage_end": end.isoformat() if end else None, "timezone": "Asia/Shanghai" if start else None,
        "retrieval_status": "success" if finished else "partial",
        "coverage_status": ("verified" if complete else "qualified_with_exclusion" if qualified
                            else "partial" if start else "unscoped"),
        "coverage_claim": "dated_candidates_only" if qualified else "complete_dated_scan" if complete else "none",
        "pagination_complete": finished, "retrieved_count": len(items),
        "inside_window_count": len(inside), "outside_window_count": outside,
        "missing_timestamp_count": missing, "undated_exclusions": undated_exclusions, "pages": pages,
        "response_hash": hashlib.sha256(json.dumps(pages, sort_keys=True).encode()).hexdigest(),
        "failure": failure or ("outside API retention or invalid since" if start and not (retention_ok and since_ok) else ""),
    }
    return inside, evidence


def feed_items(args: argparse.Namespace) -> list[dict[str, Any]]:
    xml_text = fetch_text(BASE_URL + "/feed.xml")
    root = ET.fromstring(xml_text)
    items: list[dict[str, Any]] = []
    for element in root.findall("./channel/item")[: args.take]:
        title = clean_text(element.findtext("title"))
        permalink = clean_text(element.findtext("link"))
        description = clean_text(element.findtext("description"), 3000)
        category = clean_text(element.findtext("category"))
        guid = clean_text(element.findtext("guid"))
        author = clean_text(element.findtext("author"))
        published = iso_from_rss_date(clean_text(element.findtext("pubDate")))
        items.append(
            {
                "id": guid or permalink.rsplit("/", 1)[-1],
                "title": title,
                "url": extract_original_url(description, permalink),
                "permalink": permalink,
                "source": author or "AI HOT RSS",
                "publishedAt": published,
                "summary": description,
                "category": category,
                "score": None,
                "selected": True,
                "attribution": {"source": "AI HOT", "canonical": permalink},
            }
        )
    return items


def item_to_briefing_item(raw: dict[str, Any], index: int, source_kind: str) -> dict[str, Any]:
    raw = dict(raw)
    if isinstance(raw.get('links'),dict):
        raw.update(url=raw['links'].get('original'),permalink=raw['links'].get('aihot'),
                   title_en=raw.get('originalTitle'),source=(raw.get('source') or {}).get('name'))
    title = clean_text(raw.get("title") or raw.get("title_en") or f"AI HOT item {index}", 300)
    title_en = clean_text(raw.get("title_en"), 300)
    summary = clean_text(raw.get("summary"), 900)
    source = clean_text(raw.get("source") or "AI HOT", 200)
    permalink = str(raw.get("permalink") or raw.get("url") or "")
    original_url = str(raw.get("url") or (permalink if source_kind=="feed" else ""))
    category = clean_text(raw.get("category"), 120)
    category_label = CATEGORY_LABELS.get(category, category or "AI HOT")
    concepts = extract_concepts(title, title_en, summary)
    # API identity is opaque data, not HTML. Cleaning it can merge distinct IDs.
    item_id = raw.get("id") if source_kind=='api' else clean_text(raw.get("id"))
    if not isinstance(item_id,str) or not item_id:
        item_id = f"aihot-{index:03d}"
    facts = summary or title
    if original_url and original_url != permalink:
        facts = f"{facts} Original source: {original_url}"
    return {
        "id": "AH" + hashlib.sha256(item_id.encode("utf-8")).hexdigest()[:20],
        "story_id": "aihot-" + (hashlib.sha256(item_id.encode("utf-8")).hexdigest() if source_kind=='api' else re.sub(r"[^a-zA-Z0-9]+", "-", item_id).strip("-").lower()),
        "title": title,
        "category": category_label,
        "facts": facts,
        "judgment": "AI HOT candidate pool item. Use it as a discovery signal; verify against the original or primary source before promoting it into the final daily briefing.",
        "relevance": "",
        "evidence_level": f"aihot {source_kind} candidate",
        "source_title": source,
        "source_url": original_url,
        "source_url_contract_version": 2,
        "aggregation_url": permalink,
        "discovered_at": clean_text(raw.get("discoveredAt"),80),
        "ai_source_provenance": {"version":1,"source_id":"aihot-v1","record_id":item_id,"aggregation_url":permalink},
        "source_excerpt": summary or title,
        "published_at": clean_text(raw.get("publishedAt"), 80),
        "score": raw.get("score"),
        "selected": bool(raw.get("selected", True)),
        "original_url": original_url,
        "concepts": concepts,
    }


def build_config(items: list[dict[str, Any]], args: argparse.Namespace, source_kind: str,
                 window_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    today = args.date or datetime.now().date().isoformat()
    normalized = [item_to_briefing_item(item, index, source_kind) for index, item in enumerate(items, start=1)]
    daily = bool(getattr(args, "coverage_date", None))
    return {
        "news_feedback_version": 1,
        "briefing_title": f"AI HOT Candidate Pool - {today}",
        "date_range": clean_text(args.date_range or today, 240),
        "summary": (f"AI HOT {len(normalized)} candidate items in {args.coverage_date}."
                    if daily else f"AI HOT latest {len(normalized)} selected candidate items for the daily briefing pipeline."),
        "candidate_source": "AI HOT",
        "candidate_policy": "Candidate pool only: cross-check primary sources before final briefing inclusion.",
        "ai_hot_window": window_evidence or {"coverage_status": "unscoped"},
        "sections": [
            {
                "title": (f"AI HOT 逐日候选池（{args.coverage_date}，{len(normalized)} 条）"
                          if daily else f"AI HOT 精编候选池（最新 {len(normalized)} 条）"),
                "items": normalized,
            }
        ],
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["api", "feed"], default="api", help="Use AI HOT public API or feed.xml.")
    parser.add_argument("--mode", choices=["selected", "all"], default="selected", help="AI HOT items mode for API source.")
    parser.add_argument("--take", type=int, default=50, help="Number of candidates, max 100 for API.")
    parser.add_argument("--category", choices=["ai-models", "ai-products", "industry", "paper", "tip", "opinion"], help="Optional API category.")
    parser.add_argument("--since", help="Optional ISO-8601 lower bound for API items.")
    parser.add_argument("--query", help="Optional server-side keyword search.")
    parser.add_argument("--date", help="Briefing date, YYYY-MM-DD.")
    parser.add_argument("--coverage-date", help="Candidate publication day in Asia/Shanghai, YYYY-MM-DD; distinct from --date.")
    parser.add_argument("--date-range", help="Human-readable date range for the config.")
    parser.add_argument("--output", required=True, help="Output news_feedback_config JSON path.")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--budget-seconds", type=float, default=200)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    if not 1 <= args.take <= 100:
        raise SystemExit("--take must be between 1 and 100")
    if args.coverage_date:
        coverage_window(args.coverage_date)
    if args.source == "api":
        items, evidence = api_items(args)
    else:
        items = feed_items(args)
        if args.coverage_date:
            start, end = coverage_window(args.coverage_date)
            items = [item for item in items if published_in_window(item, start, end) is True]
        evidence = {"source": "ai_hot_feed", "coverage_date": args.coverage_date,
                    "coverage_status": "partial" if args.coverage_date else "unscoped",
                    "pagination_complete": False}
    config = build_config(items, args, args.source, evidence)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_json(output, config)
    print(f"Wrote AI HOT candidates: {output}")
    print(f"Items: {len(config['sections'][0]['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
