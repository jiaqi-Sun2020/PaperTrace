"""Bounded, inspectable article-level source captures for new daily releases."""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
import socket
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from collection_checkpoint import atomic_json
from release_lock import release_lock

NEWS_ROOT = Path(__file__).resolve().parents[3] / "news"
ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return " ".join(html.unescape(value).split())


def public_https(url: str) -> None:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise ValueError("source capture requires a public HTTPS URL")
    if re.search(r"(?:^|[&;])(?:access[_-]?key|api[_-]?key|token|secret|signature|session)=", parsed.query, re.I):
        raise ValueError("source URL appears to contain a credential-bearing query parameter")
    for info in socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM):
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global:
            raise ValueError("source capture cannot access a non-public address")


class SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Request:
        public_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.title: list[str] = []
        self.skip = 0
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in {"script", "style", "noscript"}:
            self.skip += 1
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip:
            self.skip -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)
            if self.in_title:
                self.title.append(data)


def make_capture(item: dict[str, Any], requested_url: str, final_url: str, status: int,
                 body: bytes, retrieved_at: str) -> dict[str, Any]:
    if not ITEM_ID.fullmatch(str(item.get("id") or "")):
        raise ValueError("invalid source item id")
    if len(body) > 4_000_000:
        raise ValueError("source response exceeds the bounded capture limit")
    if status != 200 or not body:
        raise ValueError("source response is not a complete HTTP 200 document")
    parser = Extractor()
    parser.feed(body.decode("utf-8", errors="replace"))
    extracted = normalize(" ".join(parser.parts))
    quote = normalize(str(item.get("source_excerpt") or ""))
    if not quote or len(quote) > 500 or quote.casefold() not in extracted.casefold():
        raise ValueError("source excerpt was not found in the retrieved article text")
    record = {
        "capture_version": 1, "item_id": item["id"], "story_id": str(item.get("story_id") or ""),
        "requested_url": requested_url,
        "final_url": final_url, "retrieved_at": retrieved_at, "status_code": status,
        "response_sha256": hashlib.sha256(body).hexdigest(),
        "extracted_text_sha256": hashlib.sha256(extracted.encode("utf-8")).hexdigest(),
        "source_title": normalize(" ".join(parser.title))[:300],
        "quoted_excerpt": quote,
        "source_class": str(item.get("source_class") or "")[:120],
    }
    record["record_sha256"] = digest(record)
    return record


def validate_capture(item: dict[str, Any], record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if type(record.get("capture_version")) is not int or record.get("capture_version") != 1 or not (
        record.get("item_id") == item.get("id") or
        (record.get("story_id") and record.get("story_id") == item.get("story_id"))
    ):
        failures.append("capture identity or version differs")
    if record.get("requested_url") != item.get("source_url"):
        failures.append("capture requested URL differs from the selected source")
    if record.get("status_code") != 200:
        failures.append("capture has no successful article response")
    quote = normalize(str(item.get("source_excerpt") or ""))
    if not quote or len(quote) > 500 or quote != record.get("quoted_excerpt"):
        failures.append("source excerpt differs from the retrieved quote")
    try:
        requested = urlsplit(str(record.get("requested_url") or ""))
        if (requested.scheme != "https" or not requested.hostname or requested.username or requested.password
                or requested.port not in (None, 443)):
            failures.append("capture requested URL is not public HTTPS syntax")
    except ValueError:
        failures.append("capture requested URL is invalid")
    if str(item.get("source_class") or "")[:120] != record.get("source_class"):
        failures.append("source classification differs from the reviewed capture")
    for field in ("response_sha256", "extracted_text_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(record.get(field) or "")):
            failures.append(field + " is missing or invalid")
    try:
        if datetime.fromisoformat(str(record.get("retrieved_at"))).tzinfo is None:
            failures.append("capture time lacks a timezone")
    except ValueError:
        failures.append("capture time is invalid")
    try:
        if urlsplit(str(record.get("final_url") or "")).scheme != "https":
            failures.append("capture final URL is not HTTPS")
    except ValueError:
        failures.append("capture final URL is invalid")
    bare = {key: value for key, value in record.items() if key != "record_sha256"}
    if record.get("record_sha256") != digest(bare):
        failures.append("capture record hash differs")
    return failures


def capture_path(news_root: Path, day: str, item_id: str) -> Path:
    if not ITEM_ID.fullmatch(item_id):
        raise ValueError("invalid source item id")
    from datetime import date
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError("invalid coverage date")
    return news_root / "_collection" / day / "source_captures" / (item_id + ".json")


def capture_report(config_path: Path, day: str, *, news_root: Path = NEWS_ROOT,
                   item_id: str | None = None) -> dict[str, Any]:
    original = config_path.read_bytes()
    raw = json.loads(original.decode("utf-8-sig"))
    if not isinstance(raw, dict) or not isinstance(raw.get("sections"), list):
        raise ValueError("candidate sections invalid")
    selected = []
    seen = set()
    for section in raw["sections"]:
        if not isinstance(section, dict) or not isinstance(section.get("items"), list):
            raise ValueError("candidate section invalid")
        for item in section["items"]:
            if (not isinstance(item, dict) or not ITEM_ID.fullmatch(str(item.get("id") or ""))
                    or item["id"] in seen):
                raise ValueError("candidate item identity invalid")
            seen.add(item["id"])
            if item_id is None or item["id"] == item_id:
                selected.append(item)
    if not selected:
        raise ValueError("no selected candidate item")
    report: dict[str, Any] = {"captured": [], "reused": [], "failures": [],
                              "config_sha256": hashlib.sha256(original).hexdigest()}
    opener = build_opener(SafeRedirect())
    for item in selected:
        try:
            path = capture_path(news_root, day, str(item["id"]))
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                valid = isinstance(cached, dict) and not validate_capture(item, cached)
            except (OSError, ValueError, TypeError, AttributeError):
                valid = False
            if valid:
                report["reused"].append(str(path))
                continue
            url = str(item.get("source_url") or "")
            public_https(url)
            request = Request(url, headers={"User-Agent": "PaperTrace-source-capture/1.0"})
            with opener.open(request, timeout=20) as response:
                body = response.read(4_000_001)
                record = make_capture(item, url, response.geturl(), response.status, body,
                                      datetime.now(timezone.utc).isoformat())
            if validate_capture(item, record):
                raise ValueError("retrieved capture invalid")
            with release_lock(news_root):
                if config_path.read_bytes() != original:
                    raise ValueError("candidate changed during capture")
                # A concurrent successful capture wins; never replace its evidence.
                try:
                    other = json.loads(path.read_text(encoding="utf-8"))
                    valid = isinstance(other, dict) and not validate_capture(item, other)
                except (OSError, ValueError, TypeError, AttributeError):
                    valid = False
                if valid:
                    report["reused"].append(str(path))
                else:
                    atomic_json(path, record)
                    report["captured"].append(str(path))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            report["failures"].append({"item_id": item["id"], "code": exc.__class__.__name__})
    report["status"] = "partial" if report["failures"] else "complete"
    return report


def capture_config(config_path: Path, day: str, *, news_root: Path = NEWS_ROOT,
                   item_id: str | None = None) -> list[Path]:
    report = capture_report(config_path, day, news_root=news_root, item_id=item_id)
    if report["failures"]:
        raise ValueError("source capture partial; successful captures retained; retry failed item ids")
    return [Path(path) for path in report["captured"] + report["reused"]]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--coverage-date", required=True)
    parser.add_argument("--item-id", help="Capture one viable candidate instead of the whole pool")
    args = parser.parse_args()
    try:
        report = capture_report(args.config, args.coverage_date, item_id=args.item_id)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        report = {"status": "failed", "failures": [{"code": exc.__class__.__name__}]}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
