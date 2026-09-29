#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch AI HOT candidates and convert them into briefing config items."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable


UA = "aihot-skill/0.3.4 (+https://aihot.virxact.com/aihot-skill/; integrated-ai-quantum-news-briefing)"
BASE_URL = "https://aihot.virxact.com"
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


def fetch_response(url: str) -> tuple[str, dict[str, Any]]:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        return body.decode("utf-8", errors="replace"), {
            "query_url": url, "final_url": response.geturl(),
            "status_code": int(response.status),
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
        if "aihot.virxact.com" not in stripped:
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


def api_items(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    coverage_day = getattr(args, "coverage_date", None)
    start, end = coverage_window(coverage_day) if coverage_day else (None, None)
    params = {
        "mode": args.mode,
        "take": str(args.take),
    }
    if args.category:
        params["category"] = args.category
    if args.since:
        params["since"] = args.since
    elif start:
        params["since"] = start.astimezone(timezone.utc).isoformat()
    if args.query:
        params["q"] = args.query
    pages: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    finished = False
    failure = ""
    for _ in range(100 if coverage_day else 1):
        page_params = dict(params)
        if cursor:
            page_params["cursor"] = cursor
        url = BASE_URL + "/api/public/items?" + urllib.parse.urlencode(page_params)
        try:
            body, evidence = fetch_response(url)
            data = json.loads(body)
            page_items = data["items"]
            if not isinstance(page_items, list):
                raise ValueError("items is not a list")
            pages.append(evidence)
            items.extend(item for item in page_items if isinstance(item, dict))
            next_cursor = data.get("nextCursor")
            has_next = data.get("hasNext")
            if has_next is False or (has_next is None and not next_cursor):
                finished = True
                break
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor in seen_cursors:
                raise ValueError("missing or repeated cursor")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
        except (OSError, ValueError, KeyError, TypeError) as exc:
            failure = str(exc)[:300]
            break
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
        page.get("status_code") == 200
        and urllib.parse.urlsplit(str(page.get("final_url") or "")).hostname == "aihot.virxact.com"
        and len(str(page.get("response_hash") or "")) == 64
        for page in pages))
    complete = bool(start and finished and not failure and not missing and retention_ok and since_ok and pages_valid)
    qualified = bool(start and finished and not failure and missing == 1 and inside
                     and retention_ok and since_ok and pages_valid)
    evidence = {
        "source": "ai_hot", "pool_scope": f"ai_hot_{args.mode}",
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
    title = clean_text(raw.get("title") or raw.get("title_en") or f"AI HOT item {index}", 300)
    title_en = clean_text(raw.get("title_en"), 300)
    summary = clean_text(raw.get("summary"), 900)
    source = clean_text(raw.get("source") or "AI HOT", 200)
    permalink = clean_text(raw.get("permalink") or raw.get("url"), 800)
    original_url = clean_text(raw.get("url") or permalink, 800)
    category = clean_text(raw.get("category"), 120)
    category_label = CATEGORY_LABELS.get(category, category or "AI HOT")
    concepts = extract_concepts(title, title_en, summary)
    item_id = clean_text(raw.get("id")) or f"aihot-{index:03d}"
    facts = summary or title
    if original_url and original_url != permalink:
        facts = f"{facts} Original source: {original_url}"
    return {
        "id": f"AH{index:03d}",
        "story_id": "aihot-" + re.sub(r"[^a-zA-Z0-9]+", "-", item_id).strip("-").lower(),
        "title": title,
        "category": category_label,
        "facts": facts,
        "judgment": "AI HOT candidate pool item. Use it as a discovery signal; verify against the original or primary source before promoting it into the final daily briefing.",
        "relevance": "",
        "evidence_level": f"aihot {source_kind} candidate",
        "source_title": source,
        "source_url": permalink,
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
    parser.add_argument("--category", choices=["ai-models", "ai-products", "industry", "paper", "tip"], help="Optional API category.")
    parser.add_argument("--since", help="Optional ISO-8601 lower bound for API items.")
    parser.add_argument("--query", help="Optional server-side keyword search.")
    parser.add_argument("--date", help="Briefing date, YYYY-MM-DD.")
    parser.add_argument("--coverage-date", help="Candidate publication day in Asia/Shanghai, YYYY-MM-DD; distinct from --date.")
    parser.add_argument("--date-range", help="Human-readable date range for the config.")
    parser.add_argument("--output", required=True, help="Output news_feedback_config JSON path.")
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
    output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote AI HOT candidates: {output}")
    print(f"Items: {len(config['sections'][0]['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
