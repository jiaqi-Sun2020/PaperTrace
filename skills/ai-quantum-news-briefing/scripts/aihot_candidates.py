#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch AI HOT candidates and convert them into briefing config items."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
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


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def iso_from_rss_date(value: str) -> str:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
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


def api_items(args: argparse.Namespace) -> list[dict[str, Any]]:
    params = {
        "mode": args.mode,
        "take": str(args.take),
    }
    if args.category:
        params["category"] = args.category
    if args.since:
        params["since"] = args.since
    if args.query:
        params["q"] = args.query
    url = BASE_URL + "/api/public/items?" + urllib.parse.urlencode(params)
    data = json.loads(fetch_text(url))
    items = data.get("items", [])
    return items if isinstance(items, list) else []


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


def build_config(items: list[dict[str, Any]], args: argparse.Namespace, source_kind: str) -> dict[str, Any]:
    today = args.date or datetime.now().date().isoformat()
    normalized = [item_to_briefing_item(item, index, source_kind) for index, item in enumerate(items, start=1)]
    return {
        "news_feedback_version": 1,
        "briefing_title": f"AI HOT Candidate Pool - {today}",
        "date_range": clean_text(args.date_range or today, 240),
        "summary": f"AI HOT latest {len(normalized)} selected candidate items for the daily briefing pipeline.",
        "candidate_source": "AI HOT",
        "candidate_policy": "Candidate pool only: cross-check primary sources before final briefing inclusion.",
        "sections": [
            {
                "title": f"AI HOT 精编候选池（最新 {len(normalized)} 条）",
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
    parser.add_argument("--date-range", help="Human-readable date range for the config.")
    parser.add_argument("--output", required=True, help="Output news_feedback_config JSON path.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    items = api_items(args) if args.source == "api" else feed_items(args)
    config = build_config(items[: args.take], args, args.source)
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote AI HOT candidates: {output}")
    print(f"Items: {len(config['sections'][0]['items'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
