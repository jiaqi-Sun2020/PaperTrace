"""Bounded, inspectable article-level source captures for new daily releases."""

from __future__ import annotations

import argparse
import hashlib
import html
import ipaddress
import json
import re
import socket
import ssl
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.error import HTTPError, URLError
from collection_checkpoint import atomic_json
from release_lock import release_lock
from briefing_contract import source_reference_url
from daily_revisions import atomic_bytes, contained, sha

NEWS_ROOT = Path(__file__).resolve().parents[3] / "news"
ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
MAX_CAPTURE_ATTEMPTS = 3
MAX_AUTOMATIC_RETRY_DELAY = 300
FAILURE_CODES = {"capture_validation_failed", "source_access_denied", "source_not_found", "source_rate_limited",
                 "source_server_error", "http_request_rejected", "source_rate_limit_deferred",
                 "environment_permission_denied", "tls_verification_failed", "local_write_failed", "dns_failure",
                 "connection_refused", "transport_timeout", "transport_failure", "capture_succeeded",
                 "capture_attempt_journal_invalid", "capture_attempt_journal_too_large", "candidate_changed_during_capture",
                 "capture_backup_digest_mismatch", "capture_cache_too_large", "source_quote_not_found", "source_response_limit_exceeded"}


def digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()


def normalize(value: str) -> str:
    return " ".join(html.unescape(value).split())


def public_https(url: str) -> None:
    source_reference_url(url)
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
    if item.get('ai_source_provenance'):
        from ai_social_sources import article_publication,aware
        publication=article_publication(body,final_url)
        if aware(item.get('published_at'))!=aware(publication['published_at']):
            raise ValueError('ai_original_publication_differs_from_candidate')
        record['ai_original_publication']=publication
    record["record_sha256"] = digest(record)
    return record


def validate_capture(item: dict[str, Any], record: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if type(record.get("capture_version")) is not int or record.get("capture_version") != 1 or not (
        record.get("item_id") == item.get("id") or
        (item.get("source_url_contract_version") == 2 and record.get("item_id") == item.get("source_candidate_id")) or
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
        if datetime.fromisoformat(str(record.get("retrieved_at")).replace("Z", "+00:00")).tzinfo is None:
            failures.append("capture time lacks a timezone")
    except ValueError:
        failures.append("capture time is invalid")
    try:
        if urlsplit(str(record.get("final_url") or "")).scheme != "https":
            failures.append("capture final URL is not HTTPS")
    except ValueError:
        failures.append("capture final URL is invalid")
    if item.get('ai_source_provenance'):
        from ai_social_sources import aware,public_url
        original=record.get('ai_original_publication') or {}
        try:
            if (type(original.get('extractor_version')) is not int or original['extractor_version']!=2
                    or not aware(item.get('published_at')) or aware(original.get('published_at'))!=aware(item['published_at'])
                    or public_url(original.get('canonical_url'))!=public_url(record['final_url'])
                    or original.get('response_sha256')!=record.get('response_sha256')):
                failures.append('AI original publication binding differs')
        except (ValueError,TypeError,AttributeError):failures.append('AI original publication binding missing')
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


def capture_failure(exc, stage, now):
    """Never serialize exception text, response bodies, headers or proxy URLs."""
    result = {"code": "capture_validation_failed", "stage": stage,
              "exception_class": type(exc).__name__, "retryable": False, "http_status": None}
    if isinstance(exc, HTTPError):
        status = int(exc.code)
        result.update(http_status=status, code=("source_access_denied" if status in (401, 403) else
                      "source_not_found" if status in (404, 410) else
                      "source_rate_limited" if status == 429 else
                      "source_server_error" if 500 <= status <= 599 else "http_request_rejected"),
                      retryable=status in (408, 429, 500, 502, 503, 504))
        if status == 429:
            raw = (exc.headers or {}).get("Retry-After", "")
            try:
                delay = int(raw) if str(raw).isdigit() else int((parsedate_to_datetime(raw) - now).total_seconds())
                delay = max(0, delay)
                if delay > MAX_AUTOMATIC_RETRY_DELAY:
                    result.update(code="source_rate_limit_deferred", retryable=False)
                else:
                    result["retry_after_seconds"] = delay
            except (ValueError, TypeError, OverflowError):
                pass
        try:
            exc.close()
        except (OSError, AttributeError, KeyError):
            pass  # A missing/already-closed HTTP error body cannot hide its status.
    elif isinstance(exc, PermissionError):
        result.update(code="environment_permission_denied")
    elif isinstance(exc, (OSError, URLError)):
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, ssl.SSLCertVerificationError):
            result.update(code="tls_verification_failed")
        elif stage in {"install", "checkpoint"}:
            result.update(code="local_write_failed")
        else:
            code = ("dns_failure" if isinstance(reason, socket.gaierror) else
                    "connection_refused" if isinstance(reason, ConnectionRefusedError) else
                    "transport_timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "transport_failure")
            result.update(code=code, retryable=True)
    return result


def _attempt_path(news_root, day, item):
    scope = digest({"item_id": item["id"], "story_id": item.get("story_id", ""),
                    "source_url": item.get("source_url", ""), "source_excerpt": normalize(str(item.get("source_excerpt") or "")),
                    "source_class": item.get("source_class", "")})
    return contained(news_root, news_root / "_collection" / day / "capture_attempts" / (item["id"] + "." + scope + ".json"))


def _attempt_state(path):
    scope = path.stem.split(".", 1)[1]
    if not path.exists():
        return {"version": 1, "scope_sha256": scope, "attempts": 0, "history": []}
    if path.stat().st_size > 1024 * 1024:
        raise ValueError("capture_attempt_journal_too_large")
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or type(value.get("attempts")) is not int
            or not 0 <= value["attempts"] <= MAX_CAPTURE_ATTEMPTS or type(value.get("version")) is not int or value.get("version") != 1
            or value.get("scope_sha256") != scope
            or value.get("state_sha256") != digest({k: v for k, v in value.items() if k != "state_sha256"})
            or not isinstance(value.get("history"), list) or len(value["history"]) > MAX_CAPTURE_ATTEMPTS
            or not isinstance(value.get("last_result", {}), dict)):
        raise ValueError("capture_attempt_journal_invalid")
    last = value.get("last_result")
    if last and not _valid_diagnostic(last):
        raise ValueError("capture_attempt_journal_invalid")
    attempts = set()
    for row in value["history"]:
        if (not isinstance(row, dict) or type(row.get("attempt")) is not int
                or not 1 <= row["attempt"] <= value["attempts"] or row["attempt"] in attempts
                or not _valid_diagnostic({k: v for k, v in row.items() if k not in {"attempt", "observed_at"}})):
            raise ValueError("capture_attempt_journal_invalid")
        attempts.add(row["attempt"])
        if datetime.fromisoformat(str(row.get("observed_at"))).tzinfo is None:
            raise ValueError("capture_attempt_journal_invalid")
    if value.get("next_retry_at"):
        if datetime.fromisoformat(value["next_retry_at"]).tzinfo is None:
            raise ValueError("capture_attempt_journal_invalid")
    return value


def _valid_diagnostic(value):
    keys = {"code", "stage", "exception_class", "retryable", "http_status", "retry_after_seconds",
            "item_id", "attempts", "next_retry_at", "checkpoint_status"}
    if (set(value) - keys or value.get("code") not in FAILURE_CODES
            or value.get("stage") not in {"candidate_validation", "dns_validation", "http_request", "response_parse", "install", "checkpoint"}
            or type(value.get("retryable")) is not bool):
        return False
    status = value.get("http_status")
    if status is not None and (type(status) is not int or not 100 <= status <= 599):
        return False
    if "item_id" in value and (not isinstance(value["item_id"], str) or not ITEM_ID.fullmatch(value["item_id"])):
        return False
    if "exception_class" in value and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", str(value["exception_class"])):
        return False
    if "checkpoint_status" in value and value["checkpoint_status"] != "write_failed":
        return False
    for key, ceiling in (("attempts", MAX_CAPTURE_ATTEMPTS), ("retry_after_seconds", MAX_AUTOMATIC_RETRY_DELAY)):
        if key in value and (type(value[key]) is not int or not 0 <= value[key] <= ceiling):
            return False
    if value.get("next_retry_at") and datetime.fromisoformat(str(value["next_retry_at"])).tzinfo is None:
        return False
    return True


def _save_attempt(path, value):
    value["state_sha256"] = digest({k: v for k, v in value.items() if k != "state_sha256"})
    atomic_json(path, value)


def admit_candidates(config, day, *, news_root=NEWS_ROOT, config_sha256=None):
    """Offline evidence admission before ranking; every discovery remains accounted for."""
    value = deepcopy(config)
    rows = []
    if not isinstance(value, dict) or not isinstance(value.get("sections"), list):
        raise ValueError("candidate_sections_invalid")
    seen = set()
    for section_position, section in enumerate(value["sections"]):
        if not isinstance(section, dict) or not isinstance(section.get("items"), list):
            raise ValueError("candidate_section_invalid")
        syntax_valid = []
        for item_position, item in enumerate(section["items"]):
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not ITEM_ID.fullmatch(item["id"])
                    or item["id"] in seen):
                raise ValueError("candidate_item_identity_invalid")
            seen.add(item["id"])
            if value.get("source_url_contract_version") == 2:
                item["source_candidate_id"] = item["id"]
            row = {"item_id": item.get("id"), "story_id": item.get("story_id"), "status": "pending_capture", "failures": [],
                   "section_position": section_position, "item_position": item_position}
            item.pop("source_capture", None)
            try:
                row["source_url"] = source_reference_url(item.get("source_url"))
                if not row["source_url"]:
                    raise ValueError("missing_source_url")
            except (TypeError, ValueError):
                row.update(status="excluded", failures=["invalid_source_url"])
                rows.append(row)
                continue
            path = contained(news_root, capture_path(news_root, day, str(item.get("id") or "")))
            try:
                if path.stat().st_size > 32 * 1024 * 1024:
                    raise ValueError("capture_cache_too_large")
                cache_bytes = path.read_bytes()
                record = json.loads(cache_bytes.decode("utf-8"))
                failures = validate_capture(item, record) if isinstance(record, dict) else ["capture_record_invalid"]
                row["cache_sha256"] = hashlib.sha256(cache_bytes).hexdigest()
                if failures:
                    row.update(status="retry_pending", failures=failures)
                else:
                    item["source_capture"] = record
                    row.update(status="evidence_valid", capture_sha256=record["record_sha256"])
            except FileNotFoundError:
                row["failures"] = ["capture_missing"]
            except (OSError, ValueError, TypeError, AttributeError):
                row.update(status="retry_pending", failures=["capture_cache_unreadable"])
            if row["status"] != "evidence_valid":
                try:
                    attempt = _attempt_state(_attempt_path(news_root, day, item))
                    if attempt["attempts"]:
                        row["capture_diagnostic"] = attempt.get("last_result") or {"code": "capture_attempt_interrupted", "retryable": True}
                        row["attempts"] = attempt["attempts"]
                        row["next_retry_at"] = attempt.get("next_retry_at")
                        row["status"] = "retry_pending"
                except (OSError, ValueError, TypeError):
                    row.update(status="retry_pending", capture_diagnostic={"code": "capture_attempt_journal_invalid", "retryable": False})
            item["source_capture_admission"] = {"status": row["status"], "failures": row["failures"]}
            syntax_valid.append(item)
            rows.append(row)
        section["items"] = syntax_valid
    value["candidate_admission"] = {"version": 1, "config_sha256": config_sha256, "records": rows,
                                    "counts": {status: sum(r["status"] == status for r in rows)
                                               for status in ("pending_capture", "evidence_valid", "retry_pending", "excluded")}}
    return value


def validate_admission(config, input_sha256):
    """Bind selected capture evidence to the complete pre-ranking admission ledger."""
    ledger = config.get("candidate_admission")
    if (not isinstance(ledger, dict) or type(ledger.get("version")) is not int or ledger["version"] != 1
            or ledger.get("config_sha256") != input_sha256 or not isinstance(ledger.get("records"), list)):
        return ["candidate_admission_binding_invalid"]
    statuses = ("pending_capture", "evidence_valid", "retry_pending", "excluded")
    rows = ledger["records"]
    by_id = {}
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("item_id"), str)
                or not ITEM_ID.fullmatch(row["item_id"]) or row["item_id"] in by_id
                or row.get("status") not in statuses or not isinstance(row.get("failures"), list)):
            return ["candidate_admission_record_invalid"]
        by_id[row["item_id"]] = row
    if ledger.get("counts") != {status: sum(row["status"] == status for row in rows) for status in statuses}:
        return ["candidate_admission_counts_invalid"]
    failures = []
    for section in config.get("sections", []):
        for item in section.get("items", []):
            record = item.get("source_capture") or {}
            row = by_id.get(record.get("item_id"))
            if (not row or row["status"] != "evidence_valid" or row.get("capture_sha256") != record.get("record_sha256")
                    or row.get("source_url") != item.get("source_url")
                    or item.get("source_candidate_id") != row["item_id"]):
                failures.append("selected_candidate_not_admitted")
    return failures


def capture_report(config_path: Path, day: str, *, news_root: Path = NEWS_ROOT,
                   item_id: str | None = None, now=None) -> dict[str, Any]:
    fixed_clock = now is not None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("capture_clock_requires_timezone")
    if config_path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("candidate_config_too_large")
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
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str) or not ITEM_ID.fullmatch(item["id"])
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
        stage = "candidate_validation"
        attempt_path = None
        reservation = None
        try:
            url = str(item.get("source_url") or "")
            source_reference_url(url)
            path = contained(news_root, capture_path(news_root, day, str(item["id"])))
            if path.exists() and path.stat().st_size > 32 * 1024 * 1024:
                raise ValueError("capture_cache_too_large")
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                valid = isinstance(cached, dict) and not validate_capture(item, cached)
            except (OSError, ValueError, TypeError, AttributeError):
                valid = False
            if valid:
                report["reused"].append(str(path))
                continue
            attempt_path = _attempt_path(news_root, day, item)
            stage = "checkpoint"
            with release_lock(news_root):
                state = _attempt_state(attempt_path)
                latest = state.get("last_result") or {}
                if state["attempts"] >= MAX_CAPTURE_ATTEMPTS:
                    report["failures"].append({"item_id": item["id"], "code": "capture_retry_exhausted",
                                               "stage": "checkpoint", "attempts": state["attempts"], "retryable": False})
                    continue
                if latest and latest.get("code") != "capture_succeeded" and not latest.get("retryable"):
                    report["failures"].append({"item_id": item["id"], **latest, "attempts": state["attempts"]})
                    continue
                deadline = state.get("next_retry_at")
                if deadline and datetime.fromisoformat(deadline) > now:
                    report["failures"].append({"item_id": item["id"], "code": "capture_retry_deferred",
                                               "stage": "checkpoint", "attempts": state["attempts"],
                                               "next_retry_at": deadline, "retryable": True})
                    continue
                # Durable reservation bounds retries across interruptions/resumes.
                state["attempts"] += 1
                reservation = state["attempts"]
                state["next_retry_at"] = (now + timedelta(seconds=30)).isoformat()
                _save_attempt(attempt_path, state)
            stage = "dns_validation"
            public_https(url)
            stage = "http_request"
            request = Request(url, headers={"User-Agent": "PaperTrace-source-capture/1.0"})
            with opener.open(request, timeout=20) as response:
                body = response.read(4_000_001)
                stage = "response_parse"
                record = make_capture(item, url, response.geturl(), response.status, body,
                                      datetime.now(timezone.utc).isoformat())
            if validate_capture(item, record):
                raise ValueError("retrieved capture invalid")
            stage = "install"
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
                    if path.exists():
                        before_bytes = path.read_bytes()
                        before_sha = hashlib.sha256(before_bytes).hexdigest()
                        backup = contained(news_root, path.parent / ".capture_backups" / (path.name + "." + before_sha))
                        if not backup.exists():
                            atomic_bytes(backup, before_bytes)
                        elif sha(backup) != before_sha:
                            raise ValueError("capture_backup_digest_mismatch")
                        if sha(path) != before_sha:
                            raise ValueError("capture_backup_digest_mismatch")
                    atomic_json(path, record)
                    report["captured"].append(str(path))
                state = _attempt_state(attempt_path)
                if state["attempts"] == reservation:
                    state.update(last_result={"code": "capture_succeeded", "stage": "install", "http_status": 200,
                                              "retryable": False}, next_retry_at=None)
                    state["history"].append({"attempt": reservation, "observed_at": now.isoformat(), **state["last_result"]})
                    _save_attempt(attempt_path, state)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            observed = now if fixed_clock else datetime.now(timezone.utc)
            failure = capture_failure(exc, stage, observed)
            known = {"candidate changed during capture": "candidate_changed_during_capture",
                     "capture_backup_digest_mismatch": "capture_backup_digest_mismatch",
                     "capture_cache_too_large": "capture_cache_too_large",
                     "source excerpt was not found in the retrieved article text": "source_quote_not_found",
                     "source response exceeds the bounded capture limit": "source_response_limit_exceeded"}
            if str(exc) in known:
                failure["code"] = known[str(exc)]
            if stage == "checkpoint" and str(exc) in {"capture_attempt_journal_invalid", "capture_attempt_journal_too_large"}:
                failure["code"] = str(exc)
            failure.update(item_id=item["id"], attempts=reservation or 0)
            if attempt_path is not None and reservation is not None:
                try:
                    with release_lock(news_root):
                        state = _attempt_state(attempt_path)
                        if state["attempts"] == reservation:
                            delay = max(2 ** reservation, failure.get("retry_after_seconds", 0))
                            deadline = (observed + timedelta(seconds=delay)).isoformat() if failure["retryable"] else None
                            state.update(last_result=failure, next_retry_at=deadline)
                            state["history"].append({"attempt": reservation, "observed_at": observed.isoformat(), **failure})
                            _save_attempt(attempt_path, state)
                            failure["next_retry_at"] = deadline
                except (OSError, ValueError, TypeError):
                    failure["checkpoint_status"] = "write_failed"
            report["failures"].append(failure)
    report["status"] = "partial" if report["failures"] else "complete"
    admitted = admit_candidates(raw, day, news_root=news_root, config_sha256=report["config_sha256"])
    report["candidate_admission"] = admitted["candidate_admission"]
    report["requested_item_ids"] = [item["id"] for item in selected]
    report["observed_at"] = now.isoformat()
    health = {}
    for row in admitted["candidate_admission"]["records"]:
        host = urlsplit(row.get("source_url", "")).hostname or "invalid_source"
        group = health.setdefault(host, {"host": host, "evidence_valid": 0, "pending": 0, "failures": []})
        group["evidence_valid" if row["status"] == "evidence_valid" else "pending"] += 1
        group["failures"].extend({key: failure[key] for key in ("item_id", "code", "stage", "http_status", "retryable", "next_retry_at") if key in failure}
                                 for failure in report["failures"] if failure.get("item_id") == row["item_id"])
    report["source_health"] = [health[host] for host in sorted(health)]
    with release_lock(news_root):
        if config_path.read_bytes() != original:
            report["status"] = "partial"
            report["failures"].append({"code": "candidate_changed", "stage": "checkpoint", "retryable": False})
        else:
            report_path = contained(news_root, news_root / "_collection" / day / "capture_attempts" /
                                    ("admission_" + report["config_sha256"] + ".json"))
            atomic_json(report_path, report)
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
        report = {"status": "failed", "failures": [capture_failure(exc, "checkpoint", datetime.now(timezone.utc))]}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
