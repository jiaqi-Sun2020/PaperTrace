#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a compact venue-aware academic search ledger for AI+quantum briefings.

The script does not scrape venue pages. It generates deterministic search URLs
and a JSON/Markdown ledger so a briefing can record which primary venues were
checked before falling back to arXiv.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Venue:
    key: str
    label: str
    domain: str
    evidence: str


VENUES: tuple[Venue, ...] = (
    Venue("aps-prl", "APS Physical Review Letters", "journals.aps.org/prl", "peer-reviewed venue"),
    Venue("aps-pra", "APS Physical Review A", "journals.aps.org/pra", "peer-reviewed venue"),
    Venue("aps-prx", "APS PRX / PRX Quantum", "journals.aps.org/prx journals.aps.org/prxquantum", "peer-reviewed venue"),
    Venue("nature", "Nature Portfolio", "nature.com", "peer-reviewed venue"),
    Venue("science", "Science / AAAS", "science.org", "peer-reviewed venue"),
    Venue("openreview-iclr", "OpenReview / ICLR", "openreview.net", "conference review page"),
    Venue("cvf-cvpr", "CVF / CVPR / ICCV / ECCV", "openaccess.thecvf.com", "conference proceedings"),
    Venue("pmlr-icml", "PMLR / ICML / AISTATS / COLT", "proceedings.mlr.press", "conference proceedings"),
    Venue("neurips", "NeurIPS", "neurips.cc", "conference proceedings"),
    Venue("acl", "ACL Anthology", "aclanthology.org", "conference proceedings"),
    Venue("quantum-journal", "Quantum Journal", "quantum-journal.org", "peer-reviewed venue"),
    Venue("arxiv", "arXiv", "arxiv.org/abs", "arXiv preprint"),
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
    domain_query = " OR ".join(f"site:{part}" for part in domain.split())
    query = f"({domain_query}) {term}"
    if date_range:
        query += f" {date_range}"
    return "https://www.google.com/search?q=" + quote_plus(query)


def build_plan(terms: list[str], date_range: str, include_arxiv: bool, mark_checked_no_hit: bool) -> dict[str, object]:
    venues = [venue for venue in VENUES if include_arxiv or venue.key != "arxiv"]
    rows = []
    topics = []
    for term in terms:
        topic_rows = []
        for venue in venues:
            result = "checked_no_hit" if mark_checked_no_hit and venue.key != "arxiv" else "unchecked"
            row = {
                "term": term,
                "venue": venue.key,
                "label": venue.label,
                "evidence_level": venue.evidence,
                "search_url": search_url(venue.domain, term, date_range),
                "result": result,
                "url": "",
                "note": "",
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
                "status": "checked_no_primary_hit" if mark_checked_no_hit else "pending",
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
    parser.add_argument(
        "--mark-checked-no-hit",
        action="store_true",
        help="Mark non-arXiv venue rows as checked_no_hit after the search pass has actually been performed.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    terms = split_terms(args.term)
    if not terms:
        raise SystemExit("At least one non-empty --term is required.")
    plan = build_plan(terms, args.date_range, include_arxiv=not args.no_arxiv, mark_checked_no_hit=args.mark_checked_no_hit)
    text = json.dumps(plan, ensure_ascii=False, indent=2) if args.format == "json" else to_markdown(plan)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
