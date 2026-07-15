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
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urlsplit


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
                "note": "",
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
        "academic_search_version": 2,
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
    patterns = (
        r"(?:about|total|resultCount|resultsCount|totalResults)[^0-9]{0,30}([0-9][0-9,]*)",
        r"([0-9][0-9,]*)\s+(?:results|papers|articles)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return int(match.group(1).replace(",", ""))
    return -1


def fetch_evidence(plan: dict[str, object], timeout: int = 20) -> dict[str, object]:
    rows = plan.get("rows") or []
    for row in rows:
        if not isinstance(row, dict):
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
            with urllib.request.urlopen(request, timeout=timeout) as response:
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
        valid = [row for row in topic_rows if row.get("result") == "checked" and isinstance(row.get("evidence"), dict)]
        topic["checked_venues"] = [row.get("venue") for row in valid]
        topic["primary_hits"] = [{"venue": row.get("venue"), "url": row.get("url")} for row in valid if row.get("url") and row.get("venue") != "arxiv"]
        topic["status"] = "evidenced" if len(valid) == len(topic_rows) else "pending"
    plan["retrieved_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    plan["evidence_policy"] = "A venue is checked only when an official HTTPS endpoint returned auditable HTTP evidence."
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
