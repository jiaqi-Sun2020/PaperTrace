#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opt-in, fail-closed OSS publication for a completed daily briefing."""

from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
BRIEFING_NAME = re.compile(r"briefing_reader_(20\d{2}-\d{2}-\d{2})\.html\Z")
CONFIG_KEYS = {"site_index_url", "bucket", "region", "object_prefix", "ossutil_profile"}
MAX_SITE_BYTES = 10 * 1024 * 1024


class PublishError(Exception):
    pass


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
    except PublishError:
        raise
    except Exception as exc:
        raise PublishError(f"Website check failed: {exc.__class__.__name__}") from exc
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
            raise PublishError("Cannot read the configured OSS index object")
        try:
            return target.read_bytes()
        except OSError as exc:
            raise PublishError("Cannot read the downloaded OSS index object") from exc


def check_bucket_binding(config: dict[str, str], website_index: bytes) -> None:
    if read_bucket_index(config) != website_index:
        raise PublishError("Website index does not match the configured OSS bucket object")


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


def verified_release(run_dir: Path) -> tuple[str, Path, str]:
    from daily_pipeline import verify_artifacts

    result = verify_artifacts(run_dir, strict=True)
    if result["status"] != "pass":
        raise PublishError("Final daily release did not pass strict verification")
    manifest = result["manifest"]
    if manifest.get("status") != "complete" or (manifest.get("index_commit") or {}).get("committed") is not True:
        raise PublishError("Only a completed, indexed daily release may be published to OSS")
    if Path(manifest.get("output_dir", "")).resolve() != run_dir.resolve():
        raise PublishError("Release manifest does not match its output directory")
    run_date = str(manifest.get("date") or "")
    if not BRIEFING_NAME.fullmatch(f"briefing_reader_{run_date}.html"):
        raise PublishError("Release date is invalid")
    html_path = run_dir / f"briefing_reader_{run_date}.html"
    return run_date, html_path, hashlib.sha256(html_path.read_bytes()).hexdigest()


def publish(run_dir: Path, config_path: Path) -> dict[str, Any]:
    state_path, receipt_dir = locations(config_path)
    state = load_state(state_path)
    if not state.get("enabled"):
        return {"status": "disabled", "reason": state.get("reason", "Not manually enabled")}
    try:
        config = load_config(config_path)
        identity = deployment_id(config)
        if state.get("deployment_id") != identity:
            raise PublishError("Deployment settings changed; manual enable is required")
        _, old_index = check_site(config)
        check_bucket_binding(config, old_index)
    except PublishError as exc:
        set_state(state_path, enabled=False, reason=str(exc))
        return {"status": "disabled", "reason": str(exc)}

    run_date, html_path, expected_hash = verified_release(run_dir)
    target_url = urljoin(config["site_index_url"], html_path.name)
    upload_file(config, html_path, html_path.name)
    try:
        remote_url, remote_bytes = fetch_html(target_url)
        if remote_url != target_url or hashlib.sha256(remote_bytes).hexdigest() != expected_hash:
            raise PublishError("Uploaded daily HTML did not match the verified local release")
    except PublishError as exc:
        set_state(state_path, enabled=False, reason=str(exc))
        raise

    redirect = html.escape(html_path.name, quote=True)
    index_text = (
        '<!doctype html>\n<html lang="zh-CN"><head><meta charset="utf-8">'
        f'<meta http-equiv="refresh" content="0; url={redirect}">'
        '<title>Daily Briefing</title></head><body>'
        f'<a href="{redirect}">阅读最新日报</a></body></html>\n'
    )
    with tempfile.TemporaryDirectory(prefix="papertrace-oss-") as temp:
        index_path = Path(temp) / "index.html"
        index_path.write_text(index_text, encoding="utf-8")
        try:
            upload_file(config, index_path, "index.html")
            try:
                final_link, _ = check_site(config)
                if final_link != target_url:
                    raise PublishError("Published index does not point to the new daily HTML")
            except PublishError as exc:
                set_state(state_path, enabled=False, reason=str(exc))
                raise
        except PublishError:
            previous_index = Path(temp) / "previous-index.html"
            previous_index.write_bytes(old_index)
            try:
                upload_file(config, previous_index, "index.html")
            except PublishError:
                raise PublishError("Index verification failed and restoring its previous content also failed")
            raise

    receipt = {"status": "published", "date": run_date, "html_sha256": expected_hash, "site_url": target_url, "published_at": now_utc()}
    atomic_json(receipt_dir / f"oss_publish_receipt_{run_date}.json", receipt)
    return receipt


def enable(config_path: Path) -> dict[str, Any]:
    state_path, _ = locations(config_path)
    try:
        config = load_config(config_path)
        linked_url, website_index = check_site(config)
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


def auto_publish_after_finalize(output_root: Path) -> dict[str, Any]:
    config_path = output_root.parent.parent / "news_publish.local.json"
    try:
        return publish(output_root, config_path)
    except PublishError as exc:
        return {"status": "failed", "reason": str(exc)}
    except Exception as exc:
        return {"status": "failed", "reason": f"Unexpected OSS publisher error: {exc.__class__.__name__}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "enable", "publish"))
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "news_publish.local.json")
    parser.add_argument("--run-dir", type=Path, help="Completed local daily release directory; required for publish")
    args = parser.parse_args(argv)
    config_path = args.config.expanduser().resolve()
    try:
        if args.command == "status":
            result = status(config_path)
        elif args.command == "enable":
            result = enable(config_path)
        else:
            if args.run_dir is None:
                parser.error("publish requires --run-dir")
            result = publish(args.run_dir.expanduser().resolve(), config_path)
    except PublishError as exc:
        result = {"status": "failed", "reason": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "failed" or (args.command == "enable" and result["status"] != "enabled") else 0


if __name__ == "__main__":
    sys.exit(main())
