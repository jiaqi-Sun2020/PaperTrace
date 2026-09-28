#!/usr/bin/env python3
"""Validate source and story review evidence bound to one briefing release.

This module verifies coverage and freshness of a separately authored review. It
does not claim to prove that a reviewer's semantic judgment is true.
"""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
import re
import sys
from typing import Any

ALLEGORY_SCRIPTS = Path(__file__).resolve().parents[2] / "allegory-teach" / "scripts"
if str(ALLEGORY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(ALLEGORY_SCRIPTS))

from review_evidence import story_digest, validate_review

BASE_KEYS = ("markdown", "html", "feedback", "delta_config", "index_updates")
REVIEW_NAMES = {
    "story_review": "opening_story_review_{date}.json",
    "news_review": "news_content_review_{date}.json",
    "release_audit": "release_preflight_audit_{date}.json",
}


def digest(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def content_digest(manifest: dict[str, Any]) -> str:
    hashes = manifest.get("artifact_sha256") or {}
    payload = {"date": manifest.get("date"), "run_id": manifest.get("run_id"),
               "coverage": manifest.get("coverage"),
               "index_snapshot_sha256": manifest.get("index_snapshot_sha256"),
               "artifacts": {key: hashes.get(key) for key in BASE_KEYS}}
    if "required_story_review_protocol" in manifest:
        payload["required_story_review_protocol"] = manifest["required_story_review_protocol"]
    return digest(payload)


def selected_items(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for section in config.get("sections", [])
            for item in section.get("items", []) if isinstance(item, dict)]


def claim_digest(item: dict[str, Any]) -> str:
    return digest({key: item.get(key) for key in
                   ("id", "story_id", "facts", "judgment", "relevance", "source_url",
                    "source_excerpt", "evidence_fingerprint")})


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"cannot read review artifact {path.name}: {exc.__class__.__name__}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"review artifact must be an object: {path.name}")
    return value


def validate_bundle(run_dir: Path, manifest: dict[str, Any], *, require_manifest_binding: bool) -> list[str]:
    """Check review provenance, selected-item coverage and rendered story parity."""
    failures: list[str] = []
    names = {key: template.format(date=manifest["date"])
             for key, template in REVIEW_NAMES.items()}
    try:
        config = _read_json(run_dir / manifest["artifacts"]["delta_config"])
        story_review = _read_json(run_dir / names["story_review"])
        news_review = _read_json(run_dir / names["news_review"])
        report = _read_json(run_dir / names["release_audit"])
        page = (run_dir / manifest["artifacts"]["html"]).read_text(encoding="utf-8-sig")
    except (KeyError, OSError, ValueError) as exc:
        return [str(exc)]

    story = config.get("opening_story")
    if not isinstance(story, dict):
        return ["opening story missing from release config"]
    required = manifest.get("required_story_review_protocol", 2)
    if required not in (2, 3):
        failures.append("unsupported required story review protocol")
    elif story_review.get("review_protocol_version") not in ((2, 3) if required == 2 else (3,)):
        failures.append(f"release requires story review protocol {required}")
    failures.extend(f"story review: {issue}" for issue in validate_review(story, story_review))
    narrative = re.search(r'<div class="story-narrative">(.*?)</div>', page, re.S)
    expected = "".join("<p>" + html.escape(paragraph, quote=True) + "</p>"
                       for paragraph in story.get("paragraphs", []))
    if not narrative or narrative.group(1) != expected:
        failures.append("complete ordered story is absent from visible HTML")
    if narrative and page.find('<details class="story-worked-example"') < narrative.end():
        failures.append("worked example appears before the story ends")

    release_digest = content_digest(manifest)
    if news_review.get("version") != 1 or news_review.get("content_digest") != release_digest:
        failures.append("news review is missing or stale for this release")
    if news_review.get("review_method") not in {"self", "independent"}:
        failures.append("news review method must identify self or independent review")
    rows = news_review.get("items")
    items = selected_items(config)
    if not isinstance(rows, list) or len(rows) != len(items):
        failures.append("news review must cover every selected item exactly once")
    else:
        by_id = {row.get("item_id"): row for row in rows if isinstance(row, dict)}
        if len(by_id) != len(rows):
            failures.append("news review contains duplicate or invalid item identities")
        for item in items:
            row = by_id.get(item.get("id"))
            if not isinstance(row, dict):
                failures.append(f"news review missing item {item.get('id')}")
                continue
            if row.get("claim_digest") != claim_digest(item) or row.get("source_url") != item.get("source_url"):
                failures.append(f"news review is stale for item {item.get('id')}")
            excerpt = item.get("source_excerpt")
            anchor = row.get("evidence_anchor")
            if not isinstance(excerpt, str) or not excerpt.strip():
                failures.append(f"selected item {item.get('id')} lacks source excerpt for review")
            elif not isinstance(anchor, str) or not anchor.strip() or anchor not in excerpt:
                failures.append(f"news review item {item.get('id')} lacks a source-bound evidence anchor")
            if row.get("judgment") != "pass":
                failures.append(f"news review did not approve item {item.get('id')}")
            for field in ("evidence_anchor", "reason", "limitation"):
                if not isinstance(row.get(field), str) or not row[field].strip():
                    failures.append(f"news review item {item.get('id')} lacks {field}")
            claim_reviews = row.get("claim_reviews")
            if not isinstance(claim_reviews, dict) or set(claim_reviews) != {"facts", "judgment", "relevance"}:
                failures.append(f"news review item {item.get('id')} must review facts, judgment and relevance separately")
                continue
            for claim_name, claim_review in claim_reviews.items():
                if not isinstance(claim_review, dict) or claim_review.get("verdict") != "pass":
                    failures.append(f"news review item {item.get('id')} {claim_name} is not approved")
                    continue
                claim_anchor = claim_review.get("evidence_anchor")
                if not isinstance(claim_anchor, str) or not isinstance(excerpt, str) or claim_anchor not in excerpt or not claim_anchor:
                    failures.append(f"news review item {item.get('id')} {claim_name} lacks a source-bound anchor")
                for field in ("reason", "limitation"):
                    if not isinstance(claim_review.get(field), str) or not claim_review[field].strip():
                        failures.append(f"news review item {item.get('id')} {claim_name} lacks {field}")

    if report.get("status") != "pass" or report.get("content_digest") != release_digest:
        failures.append("preflight audit is missing, failed or stale")
    if report.get("story_sha256") != story_digest(story):
        failures.append("preflight audit does not match the current story")
    if report.get("selected_items") != len(items):
        failures.append("preflight audit item count does not match")
    if report.get("story_review_sha256") != _file_hash(run_dir / names["story_review"]):
        failures.append("preflight audit story review hash mismatch")
    if report.get("news_review_sha256") != _file_hash(run_dir / names["news_review"]):
        failures.append("preflight audit news review hash mismatch")
    if require_manifest_binding:
        for key, name in names.items():
            if manifest.get("artifacts", {}).get(key) != name:
                failures.append(f"manifest is missing {key} review identity")
            if manifest.get("artifact_sha256", {}).get(key) != _file_hash(run_dir / name):
                failures.append(f"manifest is missing or mismatches {key} review hash")
    return failures


def _file_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def make_report(run_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Produce a report only after the separately authored reviews exist."""
    names = {key: template.format(date=manifest["date"]) for key, template in REVIEW_NAMES.items()}
    config = _read_json(run_dir / manifest["artifacts"]["delta_config"])
    story = config["opening_story"]
    return {
        "version": 1, "status": "pass", "content_digest": content_digest(manifest),
        "story_sha256": story_digest(story), "selected_items": len(selected_items(config)),
        "story_review_sha256": _file_hash(run_dir / names["story_review"]),
        "news_review_sha256": _file_hash(run_dir / names["news_review"]),
        "validation_scope": "review-provenance-and-freshness; semantic truth remains the reviewer's judgment",
    }
