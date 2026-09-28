#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an evidence-backed venue ledger for AI+quantum briefings.

Without ``--fetch`` this produces an unchecked plan. With ``--fetch`` it
requests official HTTPS venue endpoints and records auditable response evidence;
it never upgrades a row to checked from a search URL alone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urlencode, urlsplit


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Venue:
    key: str
    label: str
    domain: str
    evidence: str
    search_template: str


VENUES: tuple[Venue, ...] = (
    Venue("aps-prl", "APS Physical Review Letters", "journals.aps.org", "peer-reviewed venue", "https://journals.aps.org/search?q={term}"),
    Venue("aps-pra", "APS Physical Review A", "journals.aps.org", "peer-reviewed venue", "https://journals.aps.org/search?q={term}"),
    Venue("aps-prx", "APS PRX / PRX Quantum", "journals.aps.org", "peer-reviewed venue", "https://journals.aps.org/search?q={term}"),
    Venue("nature", "Nature Portfolio", "nature.com", "peer-reviewed venue", "https://www.nature.com/search?q={term}"),
    Venue("science", "Science / AAAS", "science.org", "peer-reviewed venue", "https://www.science.org/action/doSearch?AllField={term}"),
    Venue("openreview-iclr", "OpenReview / ICLR", "openreview.net", "conference review page", "https://openreview.net/search?term={term}"),
    Venue("cvf-cvpr", "CVF / CVPR / ICCV / ECCV", "openaccess.thecvf.com", "conference proceedings", "https://openaccess.thecvf.com/menu"),
    Venue("pmlr-icml", "PMLR / ICML / AISTATS / COLT", "proceedings.mlr.press", "conference proceedings", "https://proceedings.mlr.press/"),
    Venue("neurips", "NeurIPS", "neurips.cc", "conference proceedings", "https://neurips.cc/search?q={term}"),
    Venue("acl", "ACL Anthology", "aclanthology.org", "conference proceedings", "https://aclanthology.org/search/?q={term}"),
    Venue("quantum-journal", "Quantum Journal", "quantum-journal.org", "peer-reviewed venue", "https://quantum-journal.org/?s={term}"),
    Venue("arxiv", "arXiv", "arxiv.org/abs", "arXiv preprint", "https://export.arxiv.org/api/query?search_query=all:{term}"),
)


def split_terms(raw_terms: Iterable[str]) -> list[str]:
    terms: list[str] = []
    for raw in raw_terms:
        for part in raw.split(";"):
            cleaned = " ".join(part.split()).strip()
            if cleaned:
                terms.append(cleaned)
    return terms


def search_url(domain: str, term: str, date_range: str) -> str:
    return "https://" + domain + "/search?q=" + quote_plus(term)


def build_plan(terms: list[str], date_range: str, include_arxiv: bool, mark_checked_no_hit: bool) -> dict[str, object]:
    venues = [venue for venue in VENUES if include_arxiv or venue.key != "arxiv"]
    rows = []
    topics = []
    for term in terms:
        topic_rows = []
        for venue in venues:
            if mark_checked_no_hit:
                raise ValueError("--mark-checked-no-hit is disabled; fetch official venue evidence instead")
            result = "unchecked"
            row = {
                "term": term,
                "venue": venue.key,
                "label": venue.label,
                "evidence_level": venue.evidence,
                "search_url": venue.search_template.format(term=quote_plus(term)),
                "result": result,
                "url": "",
                "note": (
                    "Official query is a discovery attempt, not proof of a complete dated inventory."
                    if venue.key == "science" else ""
                ),
                "evidence": {},
            }
            rows.append(row)
            topic_rows.append(row)
        topics.append(
            {
                "term": term,
                "checked_venues": [row["venue"] for row in topic_rows if row["result"] != "unchecked"],
                "primary_hits": [
                    {"venue": row["venue"], "url": row["url"]}
                    for row in topic_rows
                    if row["url"] and row["venue"] != "arxiv"
                ],
                "status": "pending",
            }
        )
    return {
        "academic_search_version": 3,
        "date_range": date_range,
        "terms": terms,
        "venues": [venue.key for venue in venues],
        "required_venues": [
            "aps-prl",
            "aps-pra",
            "aps-prx",
            "nature",
            "science",
            "openreview-iclr",
            "cvf-cvpr",
            "pmlr-icml",
            "neurips",
            "acl",
            "quantum-journal",
            "arxiv",
        ],
        "topics": topics,
        "rows": rows,
        "venue_sweep_note_template": "Checked APS PRL/PRA/PRX, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL, and Quantum Journal; no stronger venue page found in window; treated as arXiv preprint.",
    }


def extract_result_count(text: str) -> int:
    if "<rss" in text[:500].lower() or "<rdf:rdf" in text[:500].lower():
        return len(re.findall(r"<item(?:\s|>)", text, re.I))
    patterns = (
        r"(?:about|total|resultCount|resultsCount|totalResults)[^0-9]{0,30}([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s+(?:results|papers|articles)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1).replace(",", ""))
    return -1


SCIENCE_RSS = "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science"
SCIENCE_TOC = "https://www.science.org/toc/science/0/0"
SCIENCE_ISSN = "0036-8075"


def _request_evidence(url: str, timeout: int) -> tuple[dict[str, object], bytes]:
    """Keep failed requests as evidence; a successful response is not a coverage proof."""
    evidence: dict[str, object] = {
        "query_url": url,
        "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status_code": 0,
        "final_url": "",
        "response_hash": "",
    }
    try:
        if urlsplit(url).scheme != "https":
            raise ValueError("source URL must be https")
        request = urllib.request.Request(url, headers={"User-Agent": "PaperTrace-academic-venue-sweep/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(2_000_000)
            evidence.update(status_code=int(response.status), final_url=response.geturl(),
                            response_hash=hashlib.sha256(body).hexdigest())
            return evidence, body
    except urllib.error.HTTPError as exc:
        body = exc.read(2_000_000)
        evidence.update(status_code=int(exc.code), final_url=exc.geturl(),
                        response_hash=hashlib.sha256(body).hexdigest(), error=str(exc)[:300])
        return evidence, body
    except Exception as exc:
        evidence["error"] = str(exc)[:300]
        return evidence, b""


def _open_venue_with_retry(request: urllib.request.Request, timeout: int, venue: str):
    """Retry only a bounded arXiv rate-limit response; never infer a hit from it."""
    for attempt in range(3):
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if venue != "arxiv" or exc.code != 429 or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = min(3.0, max(0.0, float(retry_after))) if retry_after else float(attempt + 1)
            except ValueError:
                delay = float(attempt + 1)
            exc.close()
            time.sleep(delay)
    raise AssertionError("unreachable")


def _science_days(date_range: str) -> list[str]:
    values = re.findall(r"20\d{2}-\d{2}-\d{2}", date_range)
    if not values:
        return []
    start, end = date.fromisoformat(values[0]), date.fromisoformat(values[-1])
    if end < start or (end - start).days > 31:
        raise ValueError("Science sweep needs an ordered window of at most 32 days")
    return [(start + timedelta(days=index)).isoformat() for index in range((end - start).days + 1)]


def _crossref_science_snapshot(day: str, timeout: int, rows_per_page: int = 100) -> dict[str, object]:
    """Complete an indexed-metadata query, never a publisher-publication census."""
    endpoint = f"https://api.crossref.org/journals/{SCIENCE_ISSN}/works"
    cursor = "*"
    seen_cursors: set[str] = set()
    records: dict[str, dict[str, object]] = {}
    pages: list[dict[str, object]] = []
    total: int | None = None
    raw_count = 0
    complete = False
    for _ in range(100):
        if cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        # Crossref date filters are inclusive. Recheck the actual date locally.
        params = {"filter": f"from-online-pub-date:{day},until-online-pub-date:{day}",
                  "rows": rows_per_page, "cursor": cursor,
                  "select": "DOI,title,abstract,subject,ISSN,prefix,published-online,type"}
        url = endpoint + "?" + urlencode(params)
        evidence, body = _request_evidence(url, timeout)
        pages.append(evidence)
        if (not 200 <= int(evidence["status_code"]) < 300
                or not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("response_hash") or ""))):
            break
        try:
            message = json.loads(body)["message"]
            items = message["items"]
            count = message["total-results"]
            if not isinstance(items, list) or not isinstance(count, int) or count < 0:
                break
            if total is None:
                total = count
            elif total != count:
                break  # The index changed during pagination.
            raw_count += len(items)
            for item in items:
                if not isinstance(item, dict):
                    continue
                doi = str(item.get("DOI") or "").lower()
                if (doi.startswith("10.1126/") and SCIENCE_ISSN in item.get("ISSN", [])
                        and item.get("type") == "journal-article"):
                    records[doi] = item
            if len(items) < rows_per_page:
                complete = raw_count == total
                break
            next_cursor = message.get("next-cursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                break
            cursor = next_cursor
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            break
    return {
        "provider": "crossref", "role": "indexed_metadata_discovery",
        "journal": "Science", "issn": SCIENCE_ISSN, "doi_prefix": "10.1126",
        "publication_date_field": "published-online", "coverage_date": day,
        "query_complete": complete, "publisher_day_coverage_complete": False,
        "total_count": total, "retrieved_count": raw_count,
        "unique_science_count": len(records), "pages": pages,
        "response_hash": hashlib.sha256(json.dumps(pages, sort_keys=True).encode()).hexdigest(),
        "items": [{"doi": doi, "title": item.get("title", []), "abstract": item.get("abstract", ""),
                   "subject": item.get("subject", []), "published_online": item.get("published-online", {})}
                  for doi, item in sorted(records.items())],
    }


def _topic_matches(item: dict[str, object], term: str) -> bool:
    tokens = re.findall(r"[\w-]+", term.lower(), re.UNICODE)
    if not tokens:
        return False
    haystack = " ".join((" ".join(str(part) for part in item.get("title", [])),
                         re.sub(r"<[^>]+>", " ", str(item.get("abstract") or "")),
                         " ".join(str(part) for part in item.get("subject", [])))).lower()
    words = set(re.findall(r"[\w-]+", haystack, re.UNICODE))
    return all(token in words for token in tokens)


def _science_row(row: dict[str, object], days: list[str], timeout: int,
                 snapshots: dict[str, dict[str, object]]) -> None:
    providers = []
    for url, role in ((str(row["search_url"]), "official_search"),
                      (SCIENCE_TOC, "official_toc_discovery"),
                      (SCIENCE_RSS, "corroboration")):
        evidence, body = _request_evidence(url, timeout)
        evidence["provider"] = "science"
        evidence["role"] = role
        evidence["result_count"] = extract_result_count(body.decode("utf-8", errors="replace"))
        evidence["proves_daily_coverage"] = False
        evidence["response_bytes"] = len(body)
        providers.append(evidence)
    for day in days:
        if day not in snapshots:
            snapshots[day] = _crossref_science_snapshot(day, timeout)
    providers.extend(snapshots[day] for day in days)
    term = str(row.get("term") or "")
    row["crossref_topic_matches"] = {
        day: [item["doi"] for item in snapshots[day]["items"] if _topic_matches(item, term)]
        for day in days
    }
    row["provider_evidence"] = providers
    row["retrieval_status"] = ("blocked" if any(
        provider["role"] != "corroboration" and provider["status_code"] == 403
        for provider in providers if provider.get("provider") == "science") else
        "success" if any(200 <= int(provider["status_code"]) < 300
                         for provider in providers if provider.get("provider") == "science") else "error")
    row["coverage_status"] = "unavailable"
    row["verification_method"] = "none"
    row["result"] = "skipped_unavailable"
    row["skip_reason_code"] = ("access_denied" if row["retrieval_status"] == "blocked"
                               else "no_complete_dated_listing")
    row["coverage_date"] = days[0] if len(days) == 1 else ""
    row["evidence"] = providers[0]
    row["note"] = "Science was not included: official pages did not prove a complete dated inventory; RSS and Crossref are discovery only."


def fetch_evidence(plan: dict[str, object], timeout: int = 20) -> dict[str, object]:
    rows = plan.get("rows") or []
    science_days = _science_days(str(plan.get("date_range") or ""))
    science_snapshots: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("venue") == "science":
            _science_row(row, science_days, timeout, science_snapshots)
            continue
        url = str(row.get("search_url") or "")
        evidence: dict[str, object] = {
            "query_url": url,
            "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "status_code": 0,
            "final_url": "",
            "result_count": -1,
            "result_count_known": False,
            "response_hash": "",
            "excerpt": "",
        }
        try:
            parsed = urlsplit(url)
            if parsed.scheme != "https" or not parsed.netloc:
                raise ValueError("official search URL must be https")
            request = urllib.request.Request(url, headers={"User-Agent": "PaperTrace-academic-venue-sweep/1.0"})
            with _open_venue_with_retry(request, timeout, str(row.get("venue") or "")) as response:
                body = response.read(2_000_000)
                text = body.decode("utf-8", errors="replace")
                count = extract_result_count(text)
                evidence.update(
                    {
                        "status_code": int(response.status),
                        "final_url": response.geturl(),
                        "result_count": count,
                        "result_count_known": count >= 0,
                        "response_hash": hashlib.sha256(body).hexdigest(),
                        "excerpt": " ".join(text[:500].split()),
                    }
                )
                row["result"] = "checked" if response.status < 400 else "error"
                row["url"] = response.geturl() if response.status < 400 and row.get("venue") != "arxiv" and count > 0 else ""
        except urllib.error.HTTPError as exc:
            body = exc.read(2_000_000)
            evidence.update(
                {
                    "status_code": int(exc.code),
                    "final_url": exc.geturl(),
                    "response_hash": hashlib.sha256(body).hexdigest(),
                    "excerpt": " ".join(body.decode("utf-8", errors="replace")[:500].split()),
                    "error": str(exc)[:300],
                }
            )
            row["result"] = "blocked"
            row["evidence"] = evidence
        except Exception as exc:
            evidence["error"] = str(exc)[:300]
            row["result"] = "error"
        row["evidence"] = evidence

    topics = plan.get("topics") or []
    for topic in topics:
        if not isinstance(topic, dict):
            continue
        term = topic.get("term")
        topic_rows = [row for row in rows if isinstance(row, dict) and row.get("term") == term]
        checked = [row for row in topic_rows if row.get("result") == "checked"
                   and isinstance(row.get("evidence"), dict)]
        skipped = [row for row in topic_rows if row.get("result") == "skipped_unavailable"
                   and isinstance(row.get("evidence"), dict)]
        topic["checked_venues"] = [row.get("venue") for row in checked]
        topic["skipped_venues"] = [row.get("venue") for row in skipped]
        topic["primary_hits"] = [{"venue": row.get("venue"), "url": row.get("url")} for row in checked if row.get("url") and row.get("venue") != "arxiv"]
        topic["status"] = ("evidenced_with_science_gap" if skipped else "evidenced") if len(checked) + len(skipped) == len(topic_rows) else "pending"
    plan["retrieved_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    plan["evidence_policy"] = ("A successful HTTP response is retrieval evidence, not daily coverage. "
                               "Science RSS and a complete Crossref indexed snapshot cannot alone verify "
                               "the publisher's complete daily inventory.")
    return plan


def to_markdown(plan: dict[str, object]) -> str:
    lines = [
        "# Academic Venue Sweep",
        "",
        f"Date range: {plan.get('date_range') or 'unspecified'}",
        "",
        "| Term | Venue | Evidence | Search | Result | URL | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in plan["rows"]:  # type: ignore[index]
        assert isinstance(row, dict)
        lines.append(
            "| {term} | {label} | {evidence_level} | [search]({search_url}) | {result} | {url} | {note} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "Use `venue_sweep_note` on any final arXiv-only item.",
            f"Template: {plan.get('venue_sweep_note_template')}",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--term", action="append", required=True, help="Search term. Repeat or separate related terms with semicolons.")
    parser.add_argument("--date-range", default="", help="Compact date/window hint, e.g. 2026-07-07..2026-07-09.")
    parser.add_argument("--output", help="Output path. Defaults to stdout.")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--no-arxiv", action="store_true", help="Exclude arXiv from generated search rows.")
    parser.add_argument("--fetch", action="store_true", help="Fetch official HTTPS venue endpoints and attach auditable evidence.")
    parser.add_argument(
        "--mark-checked-no-hit",
        action="store_true",
        help="Deprecated and rejected; use --fetch instead.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    terms = split_terms(args.term)
    if not terms:
        raise SystemExit("At least one non-empty --term is required.")
    plan = build_plan(terms, args.date_range, include_arxiv=not args.no_arxiv, mark_checked_no_hit=args.mark_checked_no_hit)
    if args.fetch:
        plan = fetch_evidence(plan)
    text = json.dumps(plan, ensure_ascii=False, indent=2) if args.format == "json" else to_markdown(plan)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
