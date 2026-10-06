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
import http.client
import json
import re
import socket
import sys
import time
import threading
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Iterable
from urllib.parse import quote_plus, urlencode, urlsplit

from academic_sources import (SEARCH_VERSION, family_gate, health_table,
                              load_registry, markdown_health_table, row_is_healthy)
from collection_checkpoint import atomic_json, load_checkpoint, save_checkpoint

_REQUEST_BUDGET = threading.local()


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
    Venue("aps-prl", "APS Physical Review Letters", "feeds.aps.org", "peer-reviewed venue", "https://feeds.aps.org/rss/recent/prl.xml"),
    Venue("aps-pra", "APS Physical Review A", "feeds.aps.org", "peer-reviewed venue", "https://feeds.aps.org/rss/recent/pra.xml"),
    Venue("aps-prx", "APS PRX Quantum", "feeds.aps.org", "peer-reviewed venue", "https://feeds.aps.org/rss/recent/prxquantum.xml"),
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

# Additional discovery targets are deliberately not required daily venues.
# Their pages can surface candidates, but a response is not a dated inventory
# or article-level evidence. Keep them outside ``rows`` and ``topics``.
EXPANDED_VENUES: tuple[Venue, ...] = (
    Venue("aps-prx-quantum", "APS PRX Quantum", "journals.aps.org", "peer-reviewed venue", "https://journals.aps.org/prxquantum/recent"),
    Venue("nature-physics", "Nature Physics", "nature.com", "peer-reviewed venue", "https://www.nature.com/nphys/articles?sort=PubDate"),
    Venue("nature-communications", "Nature Communications", "nature.com", "peer-reviewed venue", "https://www.nature.com/ncomms/articles?sort=PubDate"),
    Venue("npj-quantum-information", "npj Quantum Information", "nature.com", "peer-reviewed venue", "https://www.nature.com/npjqi/articles?sort=PubDate"),
    Venue("pmlr-aistats", "PMLR AISTATS 2026", "proceedings.mlr.press", "conference proceedings", "https://proceedings.mlr.press/v300/"),
    Venue("pmlr-colt", "PMLR COLT 2026", "proceedings.mlr.press", "conference proceedings", "https://proceedings.mlr.press/v336/"),
    Venue("cvf-iccv", "CVF ICCV 2025", "openaccess.thecvf.com", "conference proceedings", "https://openaccess.thecvf.com/ICCV2025?day=all"),
    Venue("ecva-eccv", "ECVA ECCV 2026 preliminary accepted papers", "eccv.ecva.net", "conference discovery", "https://eccv.ecva.net/Conferences/2026/AcceptedPapers"),
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


def build_plan(terms: list[str], date_range: str, include_arxiv: bool, mark_checked_no_hit: bool,
               include_expanded: bool = False) -> dict[str, object]:
    venues = [venue for venue in VENUES if include_arxiv or venue.key != "arxiv"]
    rows = []
    topics = []
    expanded_rows: list[dict[str, object]] = []
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
        if include_expanded:
            for venue in EXPANDED_VENUES:
                expanded_rows.append({
                    "term": term, "venue": venue.key, "label": venue.label,
                    "evidence_level": venue.evidence,
                    "search_url": venue.search_template.format(term=quote_plus(term)),
                    "result": "unchecked", "url": "",
                    "note": "Optional discovery only; verify the journal and article date separately.",
                    "evidence": {},
                })
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
        "expanded_rows": expanded_rows,
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
APS_RECENT_FEEDS = {
    "aps-prl": ("https://feeds.aps.org/rss/recent/prl.xml", "Physical Review Letters"),
    "aps-pra": ("https://feeds.aps.org/rss/recent/pra.xml", "Physical Review A"),
    "aps-prx": ("https://feeds.aps.org/rss/recent/prxquantum.xml", "PRX Quantum"),
}
APS_RSS_NS = {
    "rss": "http://purl.org/rss/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "prism": "http://prismstandard.org/namespaces/basic/2.0/",
}
MAX_RESPONSE_BYTES = 8_000_000


def build_plan_v4(terms: list[str], date_range: str, include_arxiv: bool = True) -> dict[str, object]:
    """Build one capability-aware row per source; topics are filters, not duplicate requests."""
    registry = load_registry()
    sources = [source for source in registry["sources"]
               if include_arxiv or source["adapter"] != "arxiv_atom"]
    rows: list[dict[str, object]] = []
    for source in sources:
        url = str(source["url"])
        rows.append({
            "source_id": source["source_id"], "venue": source["source_id"],
            "label": source["label"], "publisher": source["publisher"],
            "family": source["family"], "tier": source["tier"],
            "adapter": source["adapter"], "capabilities": source["capabilities"],
            "search_url": url, "coverage_window": date_range,
            "retrieval_status": "not_attempted", "parse_status": "not_attempted",
            "window_status": "not_checked", "coverage_claim": "none",
            "candidate_count": 0, "quarantined_count": 0,
            "result": "unchecked", "matches": [], "evidence": {},
            "note": "Retrieval, parsing and coverage claims are independent.",
        })
    return {
        "academic_search_version": SEARCH_VERSION,
        "source_coverage_version": 2,
        "source_registry_version": registry["version"],
        "date_range": date_range,
        "terms": terms,
        "sources": [source["source_id"] for source in sources],
        "rows": rows,
        "family_gate": {"status": "pending", "required_families": registry["policy"]["required_families"]},
        "source_health": [],
        "evidence_policy": ("HTTP success proves retrieval only. Candidate discovery, dated listing, "
                            "article evidence and publisher completeness are separate capabilities."),
    }


def _aps_recent_items(body: bytes, expected_journal: str) -> tuple[list[dict[str, str]], int]:
    """Extract bounded article identities; malformed items are quarantined, not dated by guesswork."""
    root = ET.fromstring(body)
    if root.tag != "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}RDF":
        raise ValueError("APS recent feed is not RSS 1.0 RDF")
    channel = root.findtext("rss:channel/rss:title", namespaces=APS_RSS_NS) or ""
    if not channel.startswith("Recent Articles in "):
        raise ValueError("APS recent feed has an unexpected channel")
    entries = root.findall("rss:item", APS_RSS_NS)
    if not entries:
        raise ValueError("APS recent feed contains no article items")
    items: list[dict[str, str]] = []
    quarantined = 0
    for entry in entries:
        title = (entry.findtext("rss:title", namespaces=APS_RSS_NS) or "").strip()
        doi = (entry.findtext("prism:doi", namespaces=APS_RSS_NS) or "").strip().lower()
        journal = (entry.findtext("prism:publicationName", namespaces=APS_RSS_NS) or "").strip()
        published = (entry.findtext("dc:date", namespaces=APS_RSS_NS) or "").strip()
        try:
            timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        except ValueError:
            timestamp = None
        if (not title or not doi.startswith("10.1103/") or journal != expected_journal
                or timestamp is None or timestamp.tzinfo is None):
            quarantined += 1
            continue
        items.append({"title": title, "doi": doi, "published_at": timestamp.isoformat(),
                      "description": (entry.findtext("rss:description", namespaces=APS_RSS_NS) or "")[:1500]})
    if not items:
        raise ValueError("APS recent feed has no valid dated article items")
    return items, quarantined


def _aps_recent_row(row: dict[str, object], body: bytes, evidence: dict[str, object],
                    target_days: set[str]) -> None:
    url, journal = APS_RECENT_FEEDS[str(row["venue"])]
    if (row.get("search_url") != url or evidence.get("query_url") != url
            or evidence.get("final_url") != url or evidence.get("status_code") != 200
            or evidence.get("response_hash") != hashlib.sha256(body).hexdigest()):
        raise ValueError("APS recent feed URL, status or body hash is not the expected official source")
    items, quarantined = _aps_recent_items(body, journal)
    shanghai = timezone(timedelta(hours=8))
    dates = [datetime.fromisoformat(item["published_at"]).astimezone(shanghai).date().isoformat()
             for item in items]
    if target_days and min(target_days) < min(dates):
        raise ValueError("target date is older than the retained APS recent feed")
    term = str(row.get("term") or "")
    matches = [item for item, day in zip(items, dates)
               if (not target_days or day in target_days)
               and _topic_matches({"title": [item["title"]], "abstract": item["description"]}, term)]
    evidence.update(source_kind="official_recent_rss", coverage_claim="discovery_only",
                    journal=journal, feed_item_count=len(items) + quarantined,
                    dated_item_count=len(items), quarantined_item_count=quarantined,
                    matched_article_count=len(matches), oldest_item_date=min(dates),
                    newest_item_date=max(dates))
    row["evidence"] = evidence
    row["matches"] = [{key: item[key] for key in ("title", "doi", "published_at")}
                      for item in matches[:20]]
    row["result"] = "checked"
    row["url"] = "https://doi.org/" + matches[0]["doi"] if matches else ""
    row["note"] = ("Journal-specific official recent feed; discovery only, not a complete dated inventory. "
                   "Malformed items are quarantined.")


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
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError("response_too_large")
            evidence.update(status_code=int(response.status), final_url=response.geturl(),
                            response_hash=hashlib.sha256(body).hexdigest(),
                            link_header=str(response.headers.get("Link", "")))
            return evidence, body
    except urllib.error.HTTPError as exc:
        body = exc.read(min(2_000_000, MAX_RESPONSE_BYTES) + 1)
        if len(body) > min(2_000_000, MAX_RESPONSE_BYTES):
            body = body[:min(2_000_000, MAX_RESPONSE_BYTES)]
        evidence.update(status_code=int(exc.code), final_url=exc.geturl(),
                        response_hash=hashlib.sha256(body).hexdigest(), error=str(exc)[:300],
                        retry_after=(exc.headers.get("Retry-After") if exc.headers else None))
        return evidence, body
    except Exception as exc:
        evidence["error"] = ("incomplete_read" if isinstance(exc, http.client.IncompleteRead)
                             else str(exc)[:300])
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


def _read_venue_with_retry(request: urllib.request.Request, timeout: int,
                           venue: str) -> tuple[int, str, bytes]:
    """Retry bounded arXiv transport timeouts around both open and body read."""
    attempts = 3 if venue == "arxiv" else 1
    for attempt in range(attempts):
        try:
            with _open_venue_with_retry(request, timeout, venue) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("response_too_large")
                return int(response.status), response.geturl(), body
        except (TimeoutError, socket.timeout, urllib.error.URLError) as exc:
            reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
            retryable = isinstance(reason, (TimeoutError, socket.timeout))
            if not retryable or attempt == attempts - 1:
                raise
            time.sleep(float(attempt + 1))
    raise AssertionError("unreachable")


def _request_source_with_retry(url: str, timeout: int, attempts: int = 3) -> tuple[dict[str, object], bytes]:
    """Retry transient source failures; 403/404 are evidence, not retry signals."""
    last: tuple[dict[str, object], bytes] = ({}, b"")
    for attempt in range(attempts):
        remaining = getattr(_REQUEST_BUDGET, "deadline", float("inf")) - time.monotonic()
        if remaining <= 0:
            return ({"query_url": url, "status_code": 0, "error": "collection_deadline"}, b"")
        last = _request_evidence(url, min(timeout, remaining))
        evidence, _ = last
        status = int(evidence.get("status_code") or 0)
        error = str(evidence.get("error") or "")
        retryable = status in {0, 429} or 500 <= status < 600
        if status in {403, 404} or not retryable or attempt == attempts - 1:
            return last
        try:
            delay = min(30.0, max(0.0, float(evidence.get("retry_after") or attempt + 1)))
        except (TypeError, ValueError):
            delay = min(3.0, float(attempt + 1))
        if "response_too_large" in error:
            return last
        if time.monotonic() + delay >= getattr(_REQUEST_BUDGET, "deadline", float("inf")):
            return last
        time.sleep(delay)
    return last


def _generic_feed_items(body: bytes) -> tuple[list[dict[str, str]], int]:
    """Parse RSS/Atom defensively; one malformed item never invalidates its peers."""
    root = ET.fromstring(body)
    nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1].lower() in {"item", "entry"}]
    if not nodes:
        raise ValueError("feed_has_no_items")
    items: list[dict[str, str]] = []
    quarantined = 0
    for node in nodes:
        fields: dict[str, str] = {}
        link = ""
        for child in node.iter():
            name = child.tag.rsplit("}", 1)[-1].lower()
            value = " ".join((child.text or "").split())
            if name in {"title", "published", "updated", "date", "pubdate", "doi", "description", "summary"} and value:
                fields.setdefault(name, value)
            if name == "link":
                link = value or str(child.attrib.get("href") or "")
        title = fields.get("title", "")
        published = next((fields[key] for key in ("published", "updated", "date", "pubdate") if fields.get(key)), "")
        timestamp = _parse_published_timestamp(published)
        if not title or timestamp is None:
            quarantined += 1
            continue
        items.append({"title": title, "published_at": timestamp.isoformat(), "url": link,
                      "description": fields.get("description", fields.get("summary", "")),
                      "doi": fields.get("doi", "")})
    if not items:
        raise ValueError("feed_has_no_valid_items")
    return items, quarantined


def _parse_published_timestamp(value: str) -> datetime | None:
    """Accept ISO/RFC timestamps only when they identify an absolute instant."""
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            stamp = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    return stamp if stamp.tzinfo is not None else None


def _fetch_v4_row(row: dict[str, object], source: dict[str, object], terms: list[str],
                  target_days: set[str], timeout: int) -> dict[str, object]:
    if source.get("adapter") in {"aps_harvest", "crossref_dated"}:
        from dated_source import fetch_dated_row
        return fetch_dated_row(row, source, target_days, timeout, _request_source_with_retry)
    if source.get("adapter") == "plos_search":
        from plos_source import fetch_plos_row
        return fetch_plos_row(row, source, target_days, timeout, _request_source_with_retry)
    result = dict(row)
    raw_url = str(source["url"])
    url = raw_url.format(term=quote_plus(terms[0] if terms else "quantum"))
    evidence, body = _request_source_with_retry(url, timeout, int(source.get("maximum_attempts") or 3))
    result["search_url"] = url
    result["evidence"] = evidence
    status = int(evidence.get("status_code") or 0)
    if not 200 <= status < 300:
        result.update(retrieval_status=("blocked" if status in {403, 404} else "error"),
                      parse_status="not_attempted", window_status="unknown",
                      coverage_claim="none", result="blocked" if status in {403, 404} else "error",
                      next_action="retry_or_use_peer_source")
        return result
    result["retrieval_status"] = "success"
    adapter = str(source.get("adapter") or "")
    if adapter == "science":
        result.update(parse_status="not_applicable", window_status="unknown",
                      coverage_claim="discovery_only", result="skipped_unavailable",
                      next_action="use_only_after_complete_publisher_listing_is_proven",
                      note="Science retrieval is discovery only; it does not prove a complete dated inventory.")
        return result
    try:
        items: list[dict[str, str]] = []
        quarantined = 0
        if adapter == "aps_rss":
            items, quarantined = _aps_recent_items(body, str(source.get("expected_journal") or ""))
        elif adapter == "jmlr_rss":
            # JMLR's live RSS currently publishes year-only pubDate fields.
            # Preserve useful structured discovery without inventing instants.
            root = ET.fromstring(body)
            discovered = []
            for node in root.iter("item"):
                record = {child.tag: " ".join((child.text or "").split()) for child in node}
                link = urlsplit(record.get("link", ""))
                if (not record.get("title") or link.hostname not in {"jmlr.org", "www.jmlr.org"}
                        or not link.path.startswith("/papers/")):
                    quarantined += 1
                    continue
                discovered.append(record)
                stamp = _parse_published_timestamp(record.get("pubDate", ""))
                if stamp is None:
                    quarantined += 1
                else:
                    items.append({"title": record["title"], "url": record["link"],
                                  "published_at": stamp.isoformat(), "description": record.get("description", "")})
            if not discovered:
                raise ValueError("jmlr_feed_has_no_article_identities")
            result["discovery_records"] = discovered
            result["structured_candidate_count"] = len(discovered)
            if not items:
                result.update(parse_status="success", window_status="unknown", coverage_claim="discovery_only",
                              candidate_count=0, quarantined_count=quarantined, matches=[], result="degraded",
                              next_action="verify_article_publication_dates",
                              note="Structured JMLR identities preserved; year-only dates cannot prove the Shanghai daily window or satisfy family health.")
                return result
        elif adapter in {"rss", "arxiv_atom"}:
            items, quarantined = _generic_feed_items(body)
        elif adapter == "openreview_api":
            payload = json.loads(body)
            notes = payload.get("notes", []) if isinstance(payload, dict) else []
            if not isinstance(notes, list):
                raise ValueError("openreview_notes_missing")
            for note in notes:
                if not isinstance(note, dict):
                    quarantined += 1
                    continue
                content = note.get("content") or {}
                title = content.get("title", "") if isinstance(content, dict) else ""
                if isinstance(title, dict):
                    title = title.get("value", "")
                published = note.get("pdate")
                if not str(title).strip() or published in {None, ""}:
                    quarantined += 1
                    continue
                try:
                    published_at = datetime.fromtimestamp(float(published) / 1000, timezone.utc).isoformat()
                except (TypeError, ValueError, OSError):
                    quarantined += 1
                    continue
                items.append({"title": str(title), "published_at": published_at,
                              "url": "https://openreview.net/forum?id=" + str(note.get("id") or "")})
        else:
            text = body.decode("utf-8", errors="replace")
            if not text.strip():
                raise ValueError("empty_response")
            result.update(parse_status="unstructured", window_status="unknown",
                          coverage_claim="discovery_only", candidate_count=0,
                          quarantined_count=0, result="degraded",
                          next_action="add_structured_adapter_or_use_peer_source")
            result["note"] = ("HTML listing retrieved, but no structured article identities were parsed; "
                              "candidate_count stays zero, the source does not satisfy a family gate, "
                              "and no completeness is claimed.")
            return result
        shanghai = timezone(timedelta(hours=8))
        item_days: list[str] = []
        for item in items:
            try:
                stamp = datetime.fromisoformat(item.get("published_at", "").replace("Z", "+00:00"))
                if stamp.tzinfo:
                    item_days.append(stamp.astimezone(shanghai).date().isoformat())
            except ValueError:
                item_days.append("")
        matches: list[dict[str, str]] = []
        for item, item_day in zip(items, item_days):
            haystack = (item.get("title", "") + " " + item.get("description", "")).lower()
            in_window = not target_days or item_day in target_days
            if in_window and any(all(token in haystack for token in re.findall(r"[\w-]+", term.lower()))
                                 for term in terms):
                matches.append(item)
        dated_days = [day for day in item_days if day]
        window = "rolling_window"
        basis = "no_requested_window"
        if target_days and dated_days:
            if max(target_days) < min(dated_days):
                window = "expired"
                basis = "target_before_feed"
            elif min(target_days) > max(dated_days):
                window = "expired"
                basis = "target_after_feed"
            else:
                window = "matched" if any(day in target_days for day in dated_days) else "unknown"
                basis = "dated_items_in_window" if window == "matched" else "gap_within_feed_span_unproven"
        elif target_days:
            window, basis = "unknown", "no_dated_items"
        result["window_evidence"] = {
            "requested_start": min(target_days) if target_days else None,
            "requested_end": max(target_days) if target_days else None,
            "observed_earliest_date": min(dated_days) if dated_days else None,
            "observed_latest_date": max(dated_days) if dated_days else None,
            "classification_basis": basis,
            "source_scope": "returned_feed_records",
            "publisher_day_coverage_complete": False,
        }
        result.update(parse_status="success", window_status=window,
                      coverage_claim="discovery_only", candidate_count=len(matches),
                      quarantined_count=quarantined, matches=matches,
                      result="checked" if window in {"matched", "empty", "rolling_window"} else "degraded",
                      next_action="article_level_review" if window in {"matched", "empty", "rolling_window"} else "use_dated_api_or_archive")
    except (ET.ParseError, ValueError, TypeError, json.JSONDecodeError) as exc:
        result.update(parse_status="error", window_status="unknown", coverage_claim="none",
                      result="degraded", next_action="retry_or_use_peer_source")
        result["evidence"] = {**evidence, "parse_error": str(exc)[:300]}
    return result


def fetch_evidence_v4(plan: dict[str, object], timeout: int = 30, max_workers: int = 4,
                      *, budget_seconds: float = 200, checkpoint: Path | None = None,
                      progress_output: Path | None = None) -> dict[str, object]:
    """Collect independent source rows concurrently and calculate the family gate."""
    if plan.get("academic_search_version") != SEARCH_VERSION:
        raise ValueError("fetch_evidence_v4 requires an academic search v4 plan")
    registry = load_registry()
    declared = {source["source_id"]: source for source in registry["sources"]}
    require_query = plan.get("source_coverage_version", 1) == 2
    terms = [str(term) for term in plan.get("terms", [])]
    target_days = set(_science_days(str(plan.get("date_range") or "")))
    rows = [dict(row) for row in plan.get("rows", []) if isinstance(row, dict)]
    if not 0 < budget_seconds <= 200:
        raise ValueError("collection budget must be in (0, 200]")
    scope = {"kind": "academic_v4", "terms": terms, "date_range": plan.get("date_range"),
             "source_coverage_version": plan.get("source_coverage_version", 1), "checkpoint_contract": 2}
    source_scopes = {str(row["source_id"]): hashlib.sha256(json.dumps(
        {"row": row, "source": declared[str(row["source_id"])]}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                     for row in rows}
    checkpoint_payload = load_checkpoint(checkpoint, scope)
    cached = checkpoint_payload.get("rows", {})
    cached_scopes = checkpoint_payload.get("source_scopes", {})
    completed = {str(row["source_id"]): cached[str(row["source_id"])] for row in rows
                 if isinstance(cached, dict) and isinstance(cached_scopes, dict)
                 and cached_scopes.get(str(row["source_id"])) == source_scopes[str(row["source_id"])]
                 and row_is_healthy(cached.get(str(row["source_id"])), str(plan.get("date_range")), registry)
                 and cached[str(row["source_id"])].get("source_id") == row["source_id"]}
    deadline = time.monotonic() + budget_seconds

    def persist_progress():
        snapshot = dict(plan)
        snapshot["rows"] = [completed.get(str(row["source_id"]), {**row,
                            "retrieval_status": "partial", "parse_status": "not_attempted",
                            "window_status": "unknown", "coverage_claim": "none", "result": "error",
                            "next_action": "resume_collector", "evidence": {"error": "collection_pending"}}) for row in rows]
        snapshot["family_gate"] = family_gate(snapshot["rows"], registry, require_query=require_query)
        snapshot["legacy_family_gate"] = family_gate(snapshot["rows"], registry)
        snapshot["source_health"] = health_table(snapshot["rows"], registry, require_query=require_query)
        snapshot["source_health_markdown"] = markdown_health_table(snapshot["rows"], registry, require_query=require_query)
        snapshot["collection_complete"] = len(completed) == len(rows)
        if progress_output is not None:
            atomic_json(progress_output, snapshot)

    persist_progress()

    def fetch(row):
        source = declared[str(row["source_id"])]
        _REQUEST_BUDGET.deadline = deadline
        try:
            if time.monotonic() >= deadline:
                return {**row, "retrieval_status": "error", "parse_status": "not_attempted",
                        "window_status": "unknown", "coverage_claim": "none", "result": "error",
                        "evidence": {"error": "collection_deadline"}, "next_action": "resume_collector"}
            return _fetch_v4_row(row, source, terms, target_days, min(30, timeout))
        finally:
            del _REQUEST_BUDGET.deadline

    # Put one source from each core family first, then remaining core sources.
    pending = [row for row in rows if str(row["source_id"]) not in completed]
    priority = []
    for family in ("quantum_publisher", "ai_peer_review"):
        first = next((row for row in pending if declared[str(row["source_id"])]["family"] == family
                      and declared[str(row["source_id"])]["adapter"] in {"aps_harvest", "crossref_dated", "plos_search"}), None)
        if first is not None:
            priority.append(first)
            pending.remove(first)
    pending.sort(key=lambda row: (declared[str(row["source_id"])]["adapter"] not in {"aps_harvest", "crossref_dated", "plos_search"},
                                 declared[str(row["source_id"])]["tier"] != "core"))
    with ThreadPoolExecutor(max_workers=min(4, max(1, max_workers))) as pool:
        futures = {pool.submit(fetch, row): str(row["source_id"]) for row in priority + pending}
        for future in as_completed(futures):
            source_id = futures[future]
            try:
                completed[source_id] = future.result()
            except Exception as exc:
                original = next(row for row in rows if row["source_id"] == source_id)
                completed[source_id] = {**original, "retrieval_status": "error",
                                        "parse_status": "not_attempted", "window_status": "unknown",
                                        "coverage_claim": "none", "result": "error",
                                        "next_action": "retry_or_use_peer_source",
                                        "evidence": {"error": str(exc)[:300]}}
            save_checkpoint(checkpoint, scope, {"rows": completed, "source_scopes": source_scopes})
            persist_progress()
    plan["rows"] = [completed[str(row["source_id"])] for row in rows]
    plan["family_gate"] = family_gate(plan["rows"], registry, require_query=require_query)
    plan["legacy_family_gate"] = family_gate(plan["rows"], registry)
    plan["source_health"] = health_table(plan["rows"], registry, require_query=require_query)
    plan["source_health_markdown"] = markdown_health_table(plan["rows"], registry, require_query=require_query)
    plan["retrieved_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    plan["collection_complete"] = True
    return plan


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
    aps_responses: dict[str, tuple[dict[str, object], bytes]] = {}
    for row in [*rows, *(plan.get("expanded_rows") or [])]:
        if not isinstance(row, dict):
            continue
        if row.get("venue") == "science":
            _science_row(row, science_days, timeout, science_snapshots)
            continue
        if row.get("venue") in APS_RECENT_FEEDS:
            url = APS_RECENT_FEEDS[str(row["venue"])][0]
            if url not in aps_responses:
                aps_responses[url] = _request_evidence(url, timeout)
            evidence, body = aps_responses[url]
            try:
                _aps_recent_row(row, body, dict(evidence), set(science_days))
            except (ET.ParseError, ValueError) as exc:
                row["result"] = "error"
                row["evidence"] = {**evidence, "error": str(exc)[:300]}
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
            venue = str(row.get("venue") or "")
            status_code, final_url, body = _read_venue_with_retry(request, timeout, venue)
            text = body.decode("utf-8", errors="replace")
            count = extract_result_count(text)
            evidence.update(
                {
                    "status_code": status_code,
                    "final_url": final_url,
                    "result_count": count,
                    "result_count_known": count >= 0,
                    "response_hash": hashlib.sha256(body).hexdigest(),
                    "excerpt": " ".join(text[:500].split()),
                }
            )
            row["result"] = "checked" if status_code < 400 else "error"
            row["url"] = final_url if status_code < 400 and row.get("venue") != "arxiv" and count > 0 else ""
        except urllib.error.HTTPError as exc:
            body = exc.read(MAX_RESPONSE_BYTES)
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
                               "APS journal-specific recent RSS is discovery only; a malformed feed item is "
                               "quarantined, and a rolling feed cannot prove a complete historical day. "
                               "Science RSS and a complete Crossref indexed snapshot cannot alone verify "
                               "the publisher's complete daily inventory.")
    return plan


def to_markdown(plan: dict[str, object]) -> str:
    if plan.get("academic_search_version") == SEARCH_VERSION:
        return "# Academic Source Health\n\n" + str(plan.get("source_health_markdown") or markdown_health_table(plan.get("rows") or [])) + "\n"
    lines = [
        "# Academic Venue Sweep",
        "",
        f"Date range: {plan.get('date_range') or 'unspecified'}",
        "",
        "| Term | Venue | Evidence | Search | Result | URL | Note |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in [*(plan["rows"]), *(plan.get("expanded_rows") or [])]:  # type: ignore[index]
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
    parser.add_argument("--expanded", action="store_true", help="Also try eight optional journal/conference discovery targets; they do not become daily coverage requirements.")
    parser.add_argument("--legacy-v3", action="store_true", help="Generate the historical per-URL v3 ledger for read-only compatibility tests.")
    parser.add_argument("--checkpoint", type=Path, help="Query-bound resumable collection state, separate from evidence output.")
    parser.add_argument("--budget-seconds", type=float, default=200)
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
    plan = (build_plan(terms, args.date_range, include_arxiv=not args.no_arxiv,
                       mark_checked_no_hit=args.mark_checked_no_hit, include_expanded=args.expanded)
            if args.legacy_v3 else build_plan_v4(terms, args.date_range, include_arxiv=not args.no_arxiv))
    if args.fetch:
        plan = fetch_evidence(plan) if args.legacy_v3 else fetch_evidence_v4(
            plan, budget_seconds=args.budget_seconds, checkpoint=args.checkpoint,
            progress_output=Path(args.output) if args.output and args.format == "json" else None)
    text = json.dumps(plan, ensure_ascii=False, indent=2) if args.format == "json" else to_markdown(plan)
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if args.format == "json":
            atomic_json(output, plan)
        else:
            output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
