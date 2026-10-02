#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opt-in, fail-closed OSS publication for a completed daily briefing."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from release_audit import validate_bundle
from release_lock import release_lock
from publication_contracts import coverage_contract_for_manifest

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
BRIEFING_NAME = re.compile(r"briefing_reader_(20\d{2}-\d{2}-\d{2})\.html\Z")
CONFIG_KEYS = {"site_index_url", "bucket", "region", "object_prefix", "ossutil_profile"}
MAX_SITE_BYTES = 10 * 1024 * 1024


class PublishError(Exception):
    def __init__(self, message: str, *, code: str = "failure") -> None:
        super().__init__(message)
        self.code = code


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def locations(config_path: Path) -> tuple[Path, Path]:
    news_root = config_path.parent / "news"
    return news_root / "_index" / "oss_publish_state.json", news_root / "_publish"


def load_config(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise PublishError(f"Cannot read local publishing configuration: {exc.__class__.__name__}") from exc
    if not isinstance(value, dict) or set(value) != CONFIG_KEYS:
        raise PublishError("Local publishing configuration must contain only the five documented fields")
    if any(not isinstance(value[key], str) for key in CONFIG_KEYS):
        raise PublishError("Local publishing configuration fields must be strings")
    try:
        parsed = urlsplit(value["site_index_url"])
        hostname = parsed.hostname
    except ValueError as exc:
        raise PublishError("Invalid site_index_url") from exc
    if (
        parsed.scheme not in ("https", "http")
        or not hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
        or not parsed.path.endswith("/index.html")
    ):
        raise PublishError("site_index_url must be an absolute HTTP(S) URL ending in /index.html")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,61}[a-z0-9]", value["bucket"]):
        raise PublishError("Invalid OSS bucket name")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", value["region"]):
        raise PublishError("Invalid OSS region")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value["ossutil_profile"]):
        raise PublishError("Invalid ossutil profile name")
    prefix = value["object_prefix"].strip("/")
    if prefix and any(
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) or part in (".", "..")
        for part in prefix.split("/")
    ):
        raise PublishError("Invalid OSS object prefix")
    expected_path = "/" + (prefix + "/" if prefix else "") + "index.html"
    if parsed.path != expected_path:
        raise PublishError("site_index_url path must match object_prefix and end in index.html")
    value["object_prefix"] = prefix
    return value


def deployment_id(config: dict[str, str]) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"enabled": False, "reason": "Not manually enabled"}
    except (OSError, ValueError):
        return {"enabled": False, "reason": "Publishing state is unreadable"}
    if not isinstance(value, dict) or value.get("version") != 1 or not isinstance(value.get("enabled"), bool):
        return {"enabled": False, "reason": "Publishing state is invalid"}
    return value


def set_state(path: Path, *, enabled: bool, reason: str, identity: str | None = None) -> dict[str, Any]:
    value = {"version": 1, "enabled": enabled, "deployment_id": identity, "reason": reason, "updated_at": now_utc()}
    atomic_json(path, value)
    return value


def fetch_html(url: str) -> tuple[str, bytes]:
    request = Request(url, headers={"User-Agent": "PaperTrace-OSS-publisher/1"})
    try:
        with urlopen(request, timeout=10) as response:
            final_url = response.geturl()
            if response.status != 200:
                raise PublishError(f"Website returned HTTP {response.status}")
            if response.headers.get_content_type() not in ("text/html", "application/xhtml+xml"):
                raise PublishError("Website did not return HTML")
            data = response.read(MAX_SITE_BYTES + 1)
    except HTTPError as exc:
        code = "not_found" if exc.code == 404 else "transient" if exc.code >= 500 else "site_rejected"
        raise PublishError(f"Website returned HTTP {exc.code}", code=code) from exc
    except (URLError, TimeoutError, HTTPException) as exc:
        raise PublishError(f"Website check failed: {exc.__class__.__name__}", code="transient") from exc
    except PublishError:
        raise
    except Exception as exc:
        raise PublishError(f"Website check failed: {exc.__class__.__name__}", code="transient") from exc
    if len(data) > MAX_SITE_BYTES or b"<html" not in data[:4096].lower():
        raise PublishError("Website HTML is missing or exceeds the size limit")
    return final_url, data


class DailyLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.refresh_links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "a" and attributes.get("href"):
            self.links.append(html.unescape(attributes["href"] or ""))
        if tag == "meta" and (attributes.get("http-equiv") or "").lower() == "refresh":
            match = re.search(r"(?:^|;)\s*url\s*=\s*['\"]?([^;'\"]+)", attributes.get("content") or "", re.I)
            if match:
                self.refresh_links.append(html.unescape(match.group(1).strip()))


def same_origin_and_directory(index_url: str, target_url: str) -> bool:
    index = urlsplit(index_url)
    target = urlsplit(target_url)
    return (
        (index.scheme, index.netloc) == (target.scheme, target.netloc)
        and target.path.rsplit("/", 1)[0] == index.path.rsplit("/", 1)[0]
        and BRIEFING_NAME.fullmatch(target.path.rsplit("/", 1)[-1]) is not None
        and not target.query and not target.fragment
    )


def check_site(config: dict[str, str]) -> tuple[str, bytes]:
    index_url = config["site_index_url"]
    final_url, index_bytes = fetch_html(index_url)
    if final_url != index_url:
        raise PublishError("Website index redirected away from its configured URL")
    parser = DailyLinkParser()
    try:
        parser.feed(index_bytes.decode("utf-8-sig"))
    except UnicodeError as exc:
        raise PublishError("Website index is not valid UTF-8 HTML") from exc
    candidates = parser.refresh_links or parser.links
    matches = {urljoin(index_url, link) for link in candidates if same_origin_and_directory(index_url, urljoin(index_url, link))}
    if len(matches) != 1:
        raise PublishError("Website index must identify exactly one reachable daily briefing")
    linked_url = next(iter(matches))
    final_link, _ = fetch_html(linked_url)
    if final_link != linked_url:
        raise PublishError("Existing daily briefing redirected away from its link")
    return linked_url, index_bytes


def checked_site(config: dict[str, str]) -> tuple[str, bytes]:
    """Retry only transient site checks; failure still requires manual re-enable."""
    for attempt in range(3):
        try:
            return check_site(config)
        except PublishError as exc:
            if exc.code != "transient" or attempt == 2:
                raise
    raise AssertionError("unreachable")


def oss_key(config: dict[str, str], filename: str) -> str:
    return f"{config['object_prefix']}/{filename}" if config["object_prefix"] else filename


def read_bucket_index(config: dict[str, str]) -> bytes:
    source = f"oss://{config['bucket']}/{oss_key(config, 'index.html')}"
    with tempfile.TemporaryDirectory(prefix="papertrace-oss-check-") as temp:
        target = Path(temp) / "index.html"
        command = [
            "ossutil", "cp", source, str(target),
            "--profile", config["ossutil_profile"], "--region", config["region"], "--force",
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PublishError(f"Cannot inspect the configured OSS bucket: {exc.__class__.__name__}") from exc
        if result.returncode != 0 or not target.is_file():
            diagnostic = (result.stderr or "") + "\n" + (result.stdout or "")
            code = ("profile_unavailable" if "SigningContext.Credentials is null or empty" in diagnostic
                    else "bucket_unavailable")
            raise PublishError("Cannot read the configured OSS index object", code=code)
        try:
            return target.read_bytes()
        except OSError as exc:
            raise PublishError("Cannot read the downloaded OSS index object") from exc


def check_bucket_binding(config: dict[str, str], website_index: bytes) -> None:
    if read_bucket_index(config) != website_index:
        raise PublishError("Website index does not match the configured OSS bucket object",
                           code="deployment_mismatch")


def doctor(config_path: Path) -> dict[str, Any]:
    """Read-only checks in the current process; never alter the publish lock."""
    try:
        config = load_config(config_path)
    except PublishError:
        return {"status": "blocked", "code": "config_unavailable",
                "next_action": "Check the local publishing configuration without sharing it"}
    if shutil.which("ossutil") is None:
        return {"status": "blocked", "code": "ossutil_unavailable",
                "next_action": "Make ossutil available in this execution environment"}
    try:
        linked_url, index_bytes = checked_site(config)
    except PublishError as exc:
        return {"status": "blocked", "code": "network_unavailable" if exc.code == "transient" else "site_unverified",
                "next_action": "Verify the public website from this same execution environment"}
    try:
        check_bucket_binding(config, index_bytes)
    except PublishError as exc:
        code = exc.code if exc.code in {"profile_unavailable", "deployment_mismatch"} else "bucket_unavailable"
        return {"status": "blocked", "code": code,
                "next_action": "Check this environment's ossutil profile and read-only bucket access"}
    return {"status": "ready", "code": "read_only_checks_passed", "existing_briefing_url": linked_url,
            "note": "Read-only checks cannot prove PutObject permission"}


def inspect_public_release(config: dict[str, str], run_date: str, expected_hash: str) -> dict[str, Any]:
    """Check public bytes and homepage without OSS access or writes."""
    target_url = urljoin(config["site_index_url"], f"briefing_reader_{run_date}.html")
    try:
        remote_bytes = _remote_html(target_url)
        if remote_bytes is None or hashlib.sha256(remote_bytes).hexdigest() != expected_hash:
            return {"status": "mismatch", "reason": "daily_html_missing_or_different"}
        current_home_url, _ = checked_site(config)
    except PublishError as exc:
        return {"status": "unreachable" if exc.code == "transient" else "mismatch",
                "reason": "public_site_unavailable" if exc.code == "transient" else "public_site_invalid"}
    current_date = BRIEFING_NAME.fullmatch(current_home_url.rsplit("/", 1)[-1]).group(1)
    if current_date < run_date or (current_date == run_date and current_home_url != target_url):
        return {"status": "mismatch", "reason": "homepage_behind_or_wrong_target"}
    return {"status": "verified", "homepage_points_to_release": current_home_url == target_url}


def upload_file(config: dict[str, str], source: Path, filename: str) -> None:
    destination = f"oss://{config['bucket']}/{oss_key(config, filename)}"
    command = [
        "ossutil", "cp", str(source), destination,
        "--profile", config["ossutil_profile"], "--region", config["region"],
        "--content-type", "text/html; charset=utf-8", "--cache-control", "no-cache", "--force",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PublishError(f"OSS upload failed to start or timed out: {exc.__class__.__name__}") from exc
    if result.returncode != 0:
        raise PublishError(f"OSS upload failed with exit code {result.returncode}")


def verified_release(run_dir: Path, *, require_audit: bool = True) -> tuple[str, Path, str]:
    from daily_pipeline import verify_artifacts

    result = verify_artifacts(run_dir, strict=True)
    if result["status"] != "pass":
        raise PublishError("Final daily release did not pass strict verification")
    manifest = result["manifest"]
    if manifest.get("status") != "complete" or (manifest.get("index_commit") or {}).get("committed") is not True:
        raise PublishError("Only a completed, indexed daily release may be published to OSS")
    if Path(manifest.get("output_dir", "")).resolve() != run_dir.resolve():
        raise PublishError("Release manifest does not match its output directory")
    if require_audit:
        failures = validate_bundle(run_dir, manifest,
                                   require_manifest_binding=int(manifest.get("pipeline_version") or 1) >= 2)
        if failures:
            raise PublishError("Release lacks a current content review: " + "; ".join(failures[:3]),
                               code="content_ineligible")
    run_date = str(manifest.get("date") or "")
    if not BRIEFING_NAME.fullmatch(f"briefing_reader_{run_date}.html"):
        raise PublishError("Release date is invalid")
    html_path = run_dir / f"briefing_reader_{run_date}.html"
    return run_date, html_path, hashlib.sha256(html_path.read_bytes()).hexdigest()


def _receipt(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _remote_html(url: str) -> bytes | None:
    for attempt in range(3):
        try:
            final_url, data = fetch_html(url)
            if final_url != url:
                raise PublishError("Daily HTML redirected away from its configured URL", code="deployment_mismatch")
            return data
        except PublishError as exc:
            if exc.code == "not_found":
                return None
            if exc.code != "transient" or attempt == 2:
                raise
    raise AssertionError("unreachable")


def _index_html(filename: str) -> str:
    redirect = html.escape(filename, quote=True)
    return (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={redirect}">'
        '<title>Daily Briefing</title></head><body>'
        f'<a href="{redirect}">阅读最新日报</a></body></html>\n'
    )


def publish(run_dir: Path, config_path: Path, *, correction_reason: str | None = None,
            supersedes_hash: str | None = None) -> dict[str, Any]:
    with release_lock(config_path.parent / "news"):
        return _publish_locked(run_dir, config_path, correction_reason=correction_reason,
                               supersedes_hash=supersedes_hash)


def _publish_locked(run_dir: Path, config_path: Path, *, correction_reason: str | None,
                    supersedes_hash: str | None) -> dict[str, Any]:
    state_path, receipt_dir = locations(config_path)
    state = load_state(state_path)
    if not state.get("enabled"):
        return {"status": "disabled", "reason": state.get("reason", "Not manually enabled")}
    try:
        config = load_config(config_path)
        identity = deployment_id(config)
        if state.get("deployment_id") != identity:
            raise PublishError("Deployment settings changed; manual enable is required")
        current_home_url, old_index = checked_site(config)
        check_bucket_binding(config, old_index)
    except PublishError as exc:
        set_state(state_path, enabled=False, reason=str(exc))
        return {"status": "disabled", "reason": str(exc)}

    run_date, html_path, expected_hash = verified_release(run_dir, require_audit=True)
    target_url = urljoin(config["site_index_url"], html_path.name)
    current_home_date = BRIEFING_NAME.fullmatch(current_home_url.rsplit("/", 1)[-1]).group(1)
    receipt_path = receipt_dir / f"oss_publish_receipt_{run_date}.json"
    prior = _receipt(receipt_path)
    if prior and prior.get("html_sha256") not in (None, expected_hash):
        if (not correction_reason or supersedes_hash != prior.get("html_sha256")):
            raise PublishError("Published date has different content; an audited explicit correction is required",
                               code="correction_required")
    try:
        remote_bytes = _remote_html(target_url)
    except PublishError as exc:
        set_state(state_path, enabled=False, reason=str(exc))
        raise
    remote_hash = hashlib.sha256(remote_bytes).hexdigest() if remote_bytes is not None else None
    if remote_hash and remote_hash != expected_hash:
        if not correction_reason or supersedes_hash != remote_hash:
            raise PublishError("Remote date has different content; explicit correction is required",
                               code="correction_required")
    index_needed = current_home_date < run_date or (current_home_date == run_date and current_home_url != target_url)
    if current_home_date == run_date and current_home_url == target_url and remote_hash != expected_hash:
        index_needed = True
    if remote_hash != expected_hash or index_needed:
        manifest_path = run_dir / f"daily_pipeline_manifest_{run_date}.json"
        try:
            coverage_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PublishError("Remote delivery requires current daily coverage evidence",
                               code="content_ineligible") from exc
        try:
            coverage_contract_for_manifest(coverage_manifest, for_upload=True)
        except ValueError as exc:
            raise PublishError(str(exc), code="content_ineligible") from exc
        try:
            review = json.loads((run_dir / f"opening_story_review_{run_date}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise PublishError("Remote delivery requires a current story review", code="content_ineligible") from exc
        if not isinstance(review, dict) or review.get("review_protocol_version") != 3:
            raise PublishError("Remote delivery requires story review protocol 3", code="content_ineligible")
    if remote_hash == expected_hash and not index_needed:
        if prior and prior.get("html_sha256") == expected_hash and prior.get("deployment_id") == identity:
            return {"status": "no_change", "date": run_date, "html_sha256": expected_hash,
                    "site_url": target_url}
        receipt = {"version": 2, "status": "published", "date": run_date,
                   "html_sha256": expected_hash, "site_url": target_url,
                   "deployment_id": identity, "index_updated": current_home_url == target_url,
                   "published_at": now_utc(), "recovered": True}
        atomic_json(receipt_path, receipt)
        return receipt
    if remote_hash != expected_hash:
        try:
            upload_file(config, html_path, html_path.name)
        except PublishError as exc:
            return {"status": "pending", "date": run_date, "reason": str(exc), "next_action": "retry publish"}
        try:
            refreshed = _remote_html(target_url)
            if refreshed is None or hashlib.sha256(refreshed).hexdigest() != expected_hash:
                raise PublishError("Uploaded daily HTML did not match the verified local release",
                                   code="deployment_mismatch")
        except PublishError as exc:
            set_state(state_path, enabled=False, reason=str(exc))
            raise

    if index_needed:
        with tempfile.TemporaryDirectory(prefix="papertrace-oss-") as temp:
            index_path = Path(temp) / "index.html"
            index_path.write_text(_index_html(html_path.name), encoding="utf-8")
            try:
                upload_file(config, index_path, "index.html")
            except PublishError as exc:
                return {"status": "pending", "date": run_date, "reason": str(exc),
                        "next_action": "reconcile remote index, then retry publish"}
            try:
                final_link, latest_index = checked_site(config)
                if final_link != target_url:
                    raise PublishError("Published index does not point to the approved daily HTML",
                                       code="deployment_mismatch")
                check_bucket_binding(config, latest_index)
            except PublishError as exc:
                set_state(state_path, enabled=False, reason=str(exc))
                raise

    receipt = {"version": 2, "status": "published", "date": run_date,
               "html_sha256": expected_hash, "site_url": target_url,
               "deployment_id": identity, "index_updated": index_needed,
               "published_at": now_utc()}
    if correction_reason:
        receipt.update({"correction_reason": correction_reason, "supersedes_hash": supersedes_hash})
    atomic_json(receipt_path, receipt)
    return receipt


def enable(config_path: Path) -> dict[str, Any]:
    state_path, _ = locations(config_path)
    try:
        config = load_config(config_path)
        linked_url, website_index = checked_site(config)
        check_bucket_binding(config, website_index)
    except PublishError as exc:
        set_state(state_path, enabled=False, reason=str(exc))
        return {"status": "disabled", "reason": str(exc)}
    set_state(state_path, enabled=True, reason="Manually enabled after website verification", identity=deployment_id(config))
    return {"status": "enabled", "existing_briefing_url": linked_url}


def status(config_path: Path) -> dict[str, Any]:
    state_path, _ = locations(config_path)
    state = load_state(state_path)
    if not state.get("enabled"):
        return {"status": "disabled", "reason": state.get("reason", "Not manually enabled")}
    try:
        config = load_config(config_path)
        if state.get("deployment_id") != deployment_id(config):
            return {"status": "disabled", "reason": "Deployment settings changed; manual enable is required"}
    except PublishError as exc:
        return {"status": "disabled", "reason": str(exc)}
    return {"status": "enabled", "updated_at": state.get("updated_at")}


def auto_publish_after_finalize(output_root: Path, *, correction_reason: str | None = None,
                                supersedes_hash: str | None = None) -> dict[str, Any]:
    config_path = output_root.parent.parent / "news_publish.local.json"
    try:
        return publish(output_root, config_path, correction_reason=correction_reason,
                       supersedes_hash=supersedes_hash)
    except PublishError as exc:
        return {"status": "failed", "reason": str(exc)}
    except Exception as exc:
        return {"status": "failed", "reason": f"Unexpected OSS publisher error: {exc.__class__.__name__}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "doctor", "enable", "publish"))
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "news_publish.local.json")
    parser.add_argument("--run-dir", type=Path, help="Completed local daily release directory; required for publish")
    parser.add_argument("--correction-reason", help="Required to replace different content for an already published date")
    parser.add_argument("--supersedes-hash", help="SHA-256 of the old published HTML being corrected")
    args = parser.parse_args(argv)
    config_path = args.config.expanduser().resolve()
    try:
        if args.command == "status":
            result = status(config_path)
        elif args.command == "doctor":
            result = doctor(config_path)
        elif args.command == "enable":
            result = enable(config_path)
        else:
            if args.run_dir is None:
                parser.error("publish requires --run-dir")
            result = publish(args.run_dir.expanduser().resolve(), config_path,
                             correction_reason=args.correction_reason,
                             supersedes_hash=args.supersedes_hash)
    except PublishError as exc:
        result = {"status": "failed", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "doctor":
        return 0 if result["status"] == "ready" else 1
    if args.command == "enable":
        return 0 if result["status"] == "enabled" else 1
    if args.command == "publish":
        return 0 if result["status"] in {"published", "no_change"} else 1
    return 0 if result["status"] != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
