#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Transactional end-to-end runner for the AI + quantum daily briefing."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
LEAN_SCRIPT_DIR = SCRIPT_DIR.parents[1] / "utils" / "lean-html-skill" / "scripts"
for path in (SCRIPT_DIR, LEAN_SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from audit_briefing_config import audit as audit_config
from briefing_contract import (
    assert_config_text_integrity,
    concept_identity,
    is_lossless_text,
    normalize_briefing_config,
)
from briefing_to_feedback_html import render_html, worked_example_has_formula
from config_to_news_feedback import export_feedback
from lean_html import apply_design_system, design_audit_issues
from news_delta import (
    load_index,
    render_markdown,
    transform_config,
    upsert_index,
)
from rank_briefing_candidates import DEFAULT_RANKING_POLICY, merged_policy, rank_briefing_config
from release_audit import REVIEW_NAMES, claim_digest, content_digest, make_report, selected_items, validate_bundle
from release_lock import release_lock
from review_evidence import ROUND_MATERIALS, TASK_CARD_KEYS, story_digest


ARTIFACT_NAMES = {
    "markdown": "daily_briefing_{date}.md",
    "html": "briefing_reader_{date}.html",
    "feedback": "news_feedback_{date}.json",
    "delta_config": "news_feedback_config_delta_{date}.json",
    "manifest": "daily_pipeline_manifest_{date}.json",
    "index_updates": "daily_pipeline_index_updates_{date}.json",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def atomic_json(path: Path, data: dict[str, Any]) -> None:
    atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".new", dir=target.parent)
    os.close(fd)
    try:
        shutil.copy2(source, temp_name)
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def infer_date(config: dict[str, Any], explicit: str | None) -> date:
    if explicit:
        return date.fromisoformat(explicit)
    text = " ".join(str(config.get(key) or "") for key in ("date", "date_range", "briefing_title"))
    match = re.search(r"(20\d{2}-\d{2}-\d{2})", text)
    return date.fromisoformat(match.group(1)) if match else datetime.now().date()


def artifact_paths(root: Path, run_date: str) -> dict[str, Path]:
    return {key: root / template.format(date=run_date) for key, template in ARTIFACT_NAMES.items()}


def run_dir_from_manifest(path: Path) -> Path:
    return path.parent if path.name.startswith("daily_pipeline_manifest_") else path


def expected_concepts(config: dict[str, Any]) -> set[str]:
    canonical = normalize_briefing_config(config, require_source_url=True)
    return {
        concept_identity(item["id"], concept)
        for section in canonical["sections"]
        for item in section["items"]
        for concept in item["concepts"]
    }


def parse_chip_identities(html_text: str) -> set[str]:
    identities: set[str] = set()
    for button in re.findall(r'<button\s+class="concept-chip"[^>]*>', html_text, re.I):
        item_match = re.search(r'data-item-id="([^"]*)"', button, re.I)
        concept_match = re.search(r'data-concept="([^"]*)"', button, re.I)
        if item_match and concept_match:
            identities.add(concept_identity(html.unescape(item_match.group(1)), html.unescape(concept_match.group(1))))
    return identities


def verify_artifacts(run_root: Path, *, strict: bool = True, structure_only: bool = False) -> dict[str, Any]:
    manifest_files = list(run_root.glob("daily_pipeline_manifest_*.json"))
    if len(manifest_files) != 1:
        return {"status": "fail", "failures": [f"manifest missing in {run_root}"], "warnings": []}
    manifest_path = manifest_files[0]
    manifest = load_json(manifest_path)
    run_date = str(manifest.get("date") or "")
    paths = artifact_paths(run_root, run_date)
    failures: list[str] = []
    warnings: list[str] = []
    for key, path in paths.items():
        if key == "manifest":
            continue
        if not path.exists() or path.stat().st_size == 0:
            failures.append(f"missing or empty artifact: {path.name}")

    if not failures:
        config = load_json(paths["delta_config"])
        feedback = load_json(paths["feedback"])
        html_text = paths["html"].read_text(encoding="utf-8-sig")
        markdown_text = paths["markdown"].read_text(encoding="utf-8-sig")
        if "\ufffd" in html_text:
            failures.append("HTML contains the Unicode replacement character")
        visible_text = re.sub(r"<(script|style)\b.*?</\1>", "", html_text, flags=re.I | re.S)
        visible_text = re.sub(r"<[^>]+>", " ", visible_text)
        if not is_lossless_text(html.unescape(visible_text)):
            failures.append("visible HTML text appears encoding-corrupted")
        for marker in ('<meta charset="utf-8">', "事实：", "判断：", "来源："):
            if marker not in html_text:
                failures.append(f"HTML encoding/UI marker missing: {marker}")
        config_audit = audit_config(config)
        failures.extend(config_audit["failures"])
        warnings.extend(config_audit["warnings"])
        if strict and config_audit["warnings"]:
            failures.extend(f"strict audit warning: {warning}" for warning in config_audit["warnings"])

        expected = expected_concepts(config)
        chips = parse_chip_identities(html_text)
        feedback_ids = {
            concept_identity(str(item.get("block_id") or ""), str(item.get("concept") or ""))
            for item in feedback.get("items", [])
            if isinstance(item, dict) and item.get("annotation_kind") == "news_concept_auto"
        }
        if chips != expected:
            failures.append(f"HTML concept identity mismatch: expected={len(expected)} actual={len(chips)}")
        if feedback_ids != expected:
            failures.append(f"feedback identity mismatch: expected={len(expected)} actual={len(feedback_ids)}")
        if feedback.get("default_status") != "unrated":
            failures.append("feedback default_status is not unrated")
        statuses = [item.get("status") for item in feedback.get("items", []) if isinstance(item, dict)]
        if any(status != "unrated" for status in statuses):
            failures.append("auto feedback contains a non-unrated status")
        if "lean-html-feedback-dock" in html_text or "LEAN_HTML_FEEDBACK2" in html_text:
            failures.append("feedback2 panel is attached to the daily reader")
        required_html = (
            "Download JSON",
            "PaperTraceFeedbackUX",
            "id=\"newsSelectionToolbar\"",
            "createAutosave",
            "localStorage",
            'data-lean-bg="light"',
            'data-lean-bg-option="light"',
            'data-lean-bg-option="cosmic"',
        )
        for marker in required_html:
            if marker not in html_text:
                failures.append(f"HTML contract marker missing: {marker}")
        if "Save mark" in html_text or 'id="saveBtn"' in html_text:
            failures.append("legacy Save mark action remains in daily reader")
        story_delivery = config.get("story_delivery") or {}
        story_required = bool(story_delivery.get("required"))
        worked_example_required = bool(story_delivery.get("worked_example_required"))
        if story_required:
            story_marker = 'data-opening-story="true"'
            briefing_marker = 'data-briefing-body="true"'
            if story_marker not in html_text:
                failures.append("HTML opening story is missing")
            if briefing_marker not in html_text:
                failures.append("HTML briefing body marker is missing")
            if story_marker in html_text and briefing_marker in html_text and html_text.index(story_marker) > html_text.index(briefing_marker):
                failures.append("HTML opening story must appear before the briefing body")
            if "## 开篇故事" not in markdown_text or "## 日报正文" not in markdown_text:
                failures.append("Markdown opening story or briefing body heading is missing")
            elif markdown_text.index("## 开篇故事") > markdown_text.index("## 日报正文"):
                failures.append("Markdown opening story must appear before the briefing body")
            if manifest.get("opening_story_present") is not True:
                failures.append("manifest does not confirm the opening story")
        if worked_example_required:
            example_marker = 'data-story-example="true"'
            story_marker = 'data-opening-story="true"'
            briefing_marker = 'data-briefing-body="true"'
            if example_marker not in html_text:
                failures.append("HTML opening-story worked example is missing")
            else:
                details_match = re.search(
                    r'<details\b[^>]*data-story-example="true"[^>]*>',
                    html_text,
                    flags=re.I,
                )
                if details_match is None:
                    failures.append("HTML worked example must use a native details control")
                elif re.search(r"\sopen(?:\s|=|>)", details_match.group(0), flags=re.I):
                    failures.append("HTML worked example must be collapsed by default")
                for concrete_marker in (
                    'class="example-scenario"',
                    'class="example-input-table"',
                    'class="example-observable"',
                ):
                    if concrete_marker not in html_text:
                        failures.append(
                            f"HTML worked example concrete-instance marker missing: {concrete_marker}"
                        )
            if all(marker in html_text for marker in (story_marker, example_marker, briefing_marker)):
                if not (
                    html_text.index(story_marker)
                    < html_text.index(example_marker)
                    < html_text.index(briefing_marker)
                ):
                    failures.append(
                        "HTML worked example must appear after the opening story and before the briefing body"
                    )
            if "### 完整例子" not in markdown_text:
                failures.append("Markdown opening-story worked example is missing")
            elif "## 日报正文" in markdown_text and markdown_text.index("### 完整例子") > markdown_text.index("## 日报正文"):
                failures.append("Markdown worked example must appear before the briefing body")
            for concrete_marker in ("**具体场景：**", "**本例输入**", "**要观察什么：**"):
                if concrete_marker not in markdown_text:
                    failures.append(
                        f"Markdown worked example concrete-instance marker missing: {concrete_marker}"
                    )
            if manifest.get("opening_story_example_present") is not True:
                failures.append("manifest does not confirm the opening-story worked example")
            example = ((config.get("opening_story") or {}).get("worked_example") or {})
            if worked_example_has_formula(example) and 'id="MathJax-script"' not in html_text:
                failures.append("formula-bearing worked example requires MathJax with a TeX fallback")
        if manifest.get("design_system", "cosmic") == "cosmic":
            failures.extend(design_audit_issues(html_text))
        manifest_hashes = manifest.get("artifact_sha256") or {}
        protocol = int(manifest.get("pipeline_version") or 1)
        for key, path in paths.items():
            if key == "manifest":
                continue
            if protocol >= 2 and (manifest.get("artifacts") or {}).get(key) != path.name:
                failures.append(f"manifest artifact identity mismatch: {key}")
            recorded = manifest_hashes.get(key)
            if protocol >= 2 and (not isinstance(recorded, str) or not re.fullmatch(r"[0-9a-f]{64}", recorded)):
                failures.append(f"manifest hash missing or invalid: {key}")
            elif recorded and recorded != sha256_file(path):
                failures.append(f"manifest hash mismatch: {key}")
        if protocol >= 2:
            failures.extend(_validate_coverage_manifest(manifest))
        if protocol >= 2 and not structure_only:
            for key, template in REVIEW_NAMES.items():
                if (manifest.get("artifacts") or {}).get(key) != template.format(date=run_date):
                    failures.append(f"manifest review artifact identity mismatch: {key}")
            failures.extend(validate_bundle(run_root, manifest, require_manifest_binding=True))

    status = "fail" if failures else "pass" if not warnings else "warn"
    return {
        "status": status,
        "failures": failures,
        "warnings": warnings,
        "config_audit": config_audit if not failures or "config_audit" in locals() else {},
        "expected_concepts": len(expected) if "expected" in locals() else 0,
        "html_concepts": len(chips) if "chips" in locals() else 0,
        "feedback_concepts": len(feedback_ids) if "feedback_ids" in locals() else 0,
        "manifest": manifest,
    }


def cmd_run(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve()
    raw_config = load_json(config_path)
    raw_story_delivery = raw_config.get("story_delivery") or {}
    if not isinstance(raw_story_delivery, dict):
        raise ValueError("story_delivery must be an object")
    raw_config = dict(raw_config)
    raw_config["story_delivery"] = {
        **raw_story_delivery,
        "required": True,
        "worked_example_required": True,
        "position": "before_briefing",
    }
    if "analysis_language" not in raw_config:
        raw_config["analysis_language"] = "zh-CN"
    if "academic_delivery" not in raw_config:
        raw_config = dict(raw_config)
        raw_config["academic_delivery"] = {
            "required": True,
            "minimum_items": 7,
            "target_items": 8,
            "maximum_items": 8,
            "minimum_new_items": 4,
            "maximum_new_items": 6,
            "minimum_non_arxiv_items": 2,
            "maximum_continuing_items": 3,
            "context_days": 7,
            "policy": "Rank an academic candidate pool and publish seven or eight papers, including four to six new papers and at least two non-arXiv formal venue papers.",
        }
    if "social_delivery" not in raw_config:
        raw_config = dict(raw_config)
        raw_config["social_delivery"] = {
            "minimum_items": 10,
            "target_items": 12,
            "maximum_items": 14,
            "minimum_new_or_material_update": 7,
            "maximum_continuing_items": 3,
            "minimum_reputable_media_items": 3,
            "minimum_primary_official_items": 3,
            "minimum_source_classes": 3,
            "maximum_items_per_organization": 2,
            "maximum_items_per_topic": 3,
            "policy": "Rank a verified social-news candidate pool and publish at least ten items with source, organization, and topic diversity.",
        }
    academic_delivery = raw_config.get("academic_delivery") or {}
    if isinstance(academic_delivery, dict) and academic_delivery.get("required"):
        raw_config = dict(raw_config)
        academic_delivery = dict(academic_delivery)
        academic_delivery["minimum_items"] = max(7, int(academic_delivery.get("minimum_items", 7)))
        academic_delivery["target_items"] = max(academic_delivery["minimum_items"], int(academic_delivery.get("target_items", 8)))
        academic_delivery["maximum_items"] = max(academic_delivery["target_items"], int(academic_delivery.get("maximum_items", 8)))
        academic_delivery["minimum_new_items"] = max(4, int(academic_delivery.get("minimum_new_items", 4)))
        academic_delivery["maximum_new_items"] = max(academic_delivery["minimum_new_items"], 6, int(academic_delivery.get("maximum_new_items", 6)))
        academic_delivery["minimum_non_arxiv_items"] = max(2, int(academic_delivery.get("minimum_non_arxiv_items", 2)))
        academic_delivery["maximum_continuing_items"] = min(3, int(academic_delivery.get("maximum_continuing_items", 3)))
        raw_config["academic_delivery"] = academic_delivery

        social_delivery = dict(raw_config.get("social_delivery") or {})
        social_delivery["minimum_items"] = max(10, int(social_delivery.get("minimum_items", 10)))
        social_delivery["target_items"] = max(social_delivery["minimum_items"], int(social_delivery.get("target_items", 12)))
        social_delivery["maximum_items"] = max(social_delivery["target_items"], int(social_delivery.get("maximum_items", 14)))
        social_delivery["minimum_new_or_material_update"] = max(7, int(social_delivery.get("minimum_new_or_material_update", 7)))
        social_delivery["maximum_continuing_items"] = min(3, int(social_delivery.get("maximum_continuing_items", 3)))
        social_delivery["minimum_reputable_media_items"] = max(3, int(social_delivery.get("minimum_reputable_media_items", 3)))
        social_delivery["minimum_primary_official_items"] = max(3, int(social_delivery.get("minimum_primary_official_items", 3)))
        social_delivery["minimum_source_classes"] = max(3, int(social_delivery.get("minimum_source_classes", 3)))
        social_delivery["maximum_items_per_organization"] = min(2, int(social_delivery.get("maximum_items_per_organization", 2)))
        social_delivery["maximum_items_per_topic"] = min(3, int(social_delivery.get("maximum_items_per_topic", 3)))
        raw_config["social_delivery"] = social_delivery

        ranking_policy = merged_policy(raw_config.get("ranking_policy"))
        ranking_policy["academic"] = {**ranking_policy["academic"], **{key: academic_delivery[key] for key in DEFAULT_RANKING_POLICY["academic"] if key in academic_delivery}}
        ranking_policy["social"] = {**ranking_policy["social"], **{key: social_delivery[key] for key in DEFAULT_RANKING_POLICY["social"] if key in social_delivery}}
        raw_config["ranking_policy"] = ranking_policy
    assert_config_text_integrity(raw_config)
    normalize_briefing_config(raw_config, config_path, require_source_url=True)
    run_date = infer_date(raw_config, args.date).isoformat()
    protocol = int(getattr(args, "release_protocol", 1))
    if protocol >= 2:
        coverage_start, coverage_end = _coverage_window(args, raw_config, run_date)
    output_root = Path(args.output_dir or (config_path.parents[2] / "news" / run_date)).expanduser().resolve()
    run_id = f"{run_date}-{uuid.uuid4().hex[:12]}"
    run_root = output_root / ".staging" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    index_path = Path(args.index).expanduser().resolve() if args.index else output_root.parent / "_index" / "story_index.jsonl"

    index_records = load_index(index_path)
    index_snapshot = sha256_file(index_path) if index_path.exists() else None
    ranked_config = (
        rank_briefing_config(raw_config, index_records, date.fromisoformat(run_date), args.days)
        if isinstance(raw_config.get("academic_delivery"), dict) and raw_config["academic_delivery"].get("required")
        else raw_config
    )
    transformed, delta_manifest, index_updates = transform_config(
        ranked_config,
        index_records,
        date.fromisoformat(run_date),
        args.days,
        args.continuing_mode,
    )
    final_paths = artifact_paths(output_root, run_date)
    for record in index_updates:
        record["briefing_path"] = str(final_paths["html"])
    canonical = normalize_briefing_config(transformed, config_path, require_source_url=True)
    feedback = export_feedback(canonical, config_path, "unrated", "none")
    html_config = dict(canonical)
    html_config.update({"default_status": "unrated", "initial_feedback_items": feedback["items"]})
    rendered_html = apply_design_system(render_html(html_config), args.design_system, args.background_mode)
    names = artifact_paths(run_root, run_date)
    atomic_text(names["markdown"], render_markdown(canonical))
    atomic_json(names["delta_config"], canonical)
    atomic_json(names["feedback"], feedback)
    atomic_text(names["html"], rendered_html)
    atomic_json(names["index_updates"], {"run_id": run_id, "items": index_updates})
    manifest = {
        "pipeline_version": protocol,
        "status": "staged",
        "run_id": run_id,
        "date": run_date,
        "input_config": str(config_path),
        "input_config_sha256": sha256_file(config_path),
        "output_dir": str(output_root),
        "index_path": str(index_path),
        "index_snapshot_sha256": index_snapshot,
        "delta_counts": delta_manifest.get("counts", {}),
        "ranking": (ranked_config.get("ranking_manifest") or {}).get("selected_counts", {}),
        "expected_concepts": len(feedback["items"]),
        "default_status": "unrated",
        "design_system": args.design_system,
        "background_mode": args.background_mode,
        "opening_story_present": bool(canonical.get("opening_story")),
        "opening_story_example_present": bool(
            (canonical.get("opening_story") or {}).get("worked_example")
        ),
        "artifacts": {key: path.name for key, path in names.items()},
        "artifact_sha256": {key: sha256_file(path) for key, path in names.items() if key != "manifest"},
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    if protocol >= 2:
        manifest["coverage"] = {"start": coverage_start, "end": coverage_end,
                                "timezone": "Asia/Shanghai",
                                "collection_completed_at": raw_config["collection_completed_at"],
                                "daily_search_evidence": raw_config.get("coverage_evidence") or []}
    atomic_json(names["manifest"], manifest)
    print(json.dumps({"status": "staged", "run_id": run_id, "run_dir": str(run_root)}, ensure_ascii=False))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    run_root = Path(args.run_dir).expanduser().resolve()
    result = verify_artifacts(run_root, strict=args.strict, structure_only=getattr(args, "structure_only", False))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def _coverage_window(args: argparse.Namespace, config: dict[str, Any], run_date: str) -> tuple[str, str]:
    shanghai = timezone(timedelta(hours=8), "Asia/Shanghai")
    anchor = date.fromisoformat(run_date)
    described_dates = re.findall(r"20\d{2}-\d{2}-\d{2}", str(config.get("date_range") or ""))
    if (len(set(described_dates)) > 1
            and not (getattr(args, "coverage_start", None) and getattr(args, "coverage_end", None))):
        raise ValueError("multi-day date_range requires explicit coverage boundaries")
    default_start = datetime.combine(anchor - timedelta(days=1), datetime.min.time(), shanghai)
    default_end = datetime.combine(anchor, datetime.min.time(), shanghai)
    start_text = getattr(args, "coverage_start", None) or default_start.isoformat()
    end_text = getattr(args, "coverage_end", None) or default_end.isoformat()
    start = datetime.fromisoformat(start_text)
    end = datetime.fromisoformat(end_text)
    if start.tzinfo is None or end.tzinfo is None or start >= end:
        raise ValueError("coverage must be a nonempty timezone-aware half-open interval")
    if end.astimezone(shanghai).date() > anchor:
        raise ValueError("coverage end cannot be later than the release-date midnight")
    if (start.astimezone(shanghai).time() != datetime.min.time()
            or end.astimezone(shanghai).time() != datetime.min.time()):
        raise ValueError("coverage boundaries must be midnight in Asia/Shanghai")
    if end > datetime.now(timezone.utc):
        raise ValueError("coverage cannot include an unfinished day")
    days = (end.astimezone(shanghai).date() - start.astimezone(shanghai).date()).days
    covered_dates = {(start.astimezone(shanghai).date() + timedelta(days=offset)).isoformat()
                     for offset in range(days)}
    if described_dates and set(described_dates) != covered_dates:
        raise ValueError("date_range does not match the declared complete-day coverage")
    if days > 1:
        evidence = config.get("coverage_evidence")
        if (not isinstance(evidence, list) or len(evidence) != len(covered_dates)
                or {row.get("date") for row in evidence if isinstance(row, dict)} != covered_dates
                or any(not row.get("academic_search_ref") or not row.get("social_search_ref") for row in evidence if isinstance(row, dict))):
            raise ValueError("multi-day coverage requires per-day academic and social search evidence")
    collected = config.get("collection_completed_at")
    if not isinstance(collected, str) or not collected.strip():
        raise ValueError("new releases require collection_completed_at")
    collected_at = datetime.fromisoformat(collected)
    if collected_at.tzinfo is None or collected_at < end or collected_at > datetime.now(timezone.utc):
        raise ValueError("collection_completed_at must be timezone-aware and after coverage end")
    return start.isoformat(), end.isoformat()


def _validate_coverage_manifest(manifest: dict[str, Any]) -> list[str]:
    coverage = manifest.get("coverage")
    if not isinstance(coverage, dict) or coverage.get("timezone") != "Asia/Shanghai":
        return ["version-2 release lacks Asia/Shanghai coverage metadata"]
    try:
        shanghai = timezone(timedelta(hours=8), "Asia/Shanghai")
        start = datetime.fromisoformat(coverage["start"])
        end = datetime.fromisoformat(coverage["end"])
        collected = datetime.fromisoformat(coverage["collection_completed_at"])
        anchor = date.fromisoformat(manifest["date"])
        if any(value.tzinfo is None for value in (start, end, collected)):
            raise ValueError("naive datetime")
        if (start >= end or end.astimezone(shanghai).date() > anchor
                or any(value.astimezone(shanghai).time() != datetime.min.time()
                       for value in (start, end))
                or collected < end):
            raise ValueError("invalid coverage interval")
        days = (end.astimezone(shanghai).date() - start.astimezone(shanghai).date()).days
        if days > 1:
            evidence = coverage.get("daily_search_evidence")
            expected = {(start.astimezone(shanghai).date() + timedelta(days=offset)).isoformat()
                        for offset in range(days)}
            if (not isinstance(evidence, list) or len(evidence) != days
                    or {row.get("date") for row in evidence if isinstance(row, dict)} != expected
                    or any(not isinstance(row, dict) or not row.get("academic_search_ref")
                           or not row.get("social_search_ref") for row in evidence)):
                raise ValueError("missing per-day search evidence")
    except (KeyError, TypeError, ValueError):
        return ["version-2 coverage interval or collection time is invalid"]
    return []


def cmd_seal_review(args: argparse.Namespace) -> int:
    run_root = Path(args.run_dir).expanduser().resolve()
    base = verify_artifacts(run_root, strict=True, structure_only=True)
    if base["status"] != "pass":
        print(json.dumps(base, ensure_ascii=False, indent=2))
        return 1
    manifest = base["manifest"]
    protocol = int(manifest.get("pipeline_version") or 1)
    if not ((protocol >= 2 and manifest.get("status") == "staged")
            or (protocol == 1 and manifest.get("status") == "complete")):
        raise ValueError("seal-review requires a staged protocol-2 release or a completed legacy release")
    report_path = run_root / REVIEW_NAMES["release_audit"].format(date=manifest["date"])
    report = make_report(run_root, manifest)
    atomic_json(report_path, report)
    failures = validate_bundle(run_root, manifest, require_manifest_binding=False)
    if failures:
        report_path.unlink()
        print(json.dumps({"status": "fail", "failures": failures}, ensure_ascii=False, indent=2))
        return 1
    if protocol >= 2:
        for key, template in REVIEW_NAMES.items():
            path = run_root / template.format(date=manifest["date"])
            manifest["artifacts"][key] = path.name
            manifest["artifact_sha256"][key] = sha256_file(path)
        manifest["audit_contract_version"] = 1
        atomic_json(run_root / ARTIFACT_NAMES["manifest"].format(date=manifest["date"]), manifest)
    print(json.dumps({"status": "sealed", "run_dir": str(run_root)}, ensure_ascii=False))
    return 0


def cmd_review_template(args: argparse.Namespace) -> int:
    run_root = Path(args.run_dir).expanduser().resolve()
    result = verify_artifacts(run_root, strict=True, structure_only=True)
    if result["status"] != "pass":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    manifest = result["manifest"]
    if int(manifest.get("pipeline_version") or 1) < 2 or manifest.get("status") != "staged":
        raise ValueError("review-template requires a staged protocol-2 release")
    config = load_json(run_root / manifest["artifacts"]["delta_config"])
    story = config["opening_story"]
    story_review = {
        "review_protocol_version": 2, "review_method": "self",
        "story_sha256": story_digest(story),
        "task_card": {key: "" for key in TASK_CARD_KEYS},
        "rounds": [{"id": key, "materials_seen": sorted(materials),
                    "judgment": "unreviewed", "reviewed_text": "", "reason": "",
                    "source_or_rule": "", "limitation": ""}
                   for key, materials in ROUND_MATERIALS.items()],
    }
    news_review = {
        "version": 1, "review_method": "self", "content_digest": content_digest(manifest),
        "items": [{"item_id": item["id"], "claim_digest": claim_digest(item),
                   "source_url": item.get("source_url"), "evidence_anchor": "",
                   "judgment": "unreviewed", "reason": "", "limitation": "",
                   "claim_reviews": {name: {"verdict": "unreviewed", "evidence_anchor": "",
                                            "reason": "", "limitation": ""}
                                     for name in ("facts", "judgment", "relevance")}}
                  for item in selected_items(config)],
    }
    review_paths = {key: run_root / REVIEW_NAMES[key].format(date=manifest["date"])
                    for key in ("story_review", "news_review")}
    for path in review_paths.values():
        if path.exists():
            raise ValueError(f"refusing to overwrite existing review: {path.name}")
    for key, value in (("story_review", story_review), ("news_review", news_review)):
        path = review_paths[key]
        atomic_json(path, value)
    print(json.dumps({"status": "review_pending", "run_dir": str(run_root)}, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Report evidenced calendar-day coverage; do not infer it from old titles."""
    news_root = Path(args.news_root).expanduser().resolve()
    shanghai = timezone(timedelta(hours=8), "Asia/Shanghai")
    through = date.fromisoformat(args.through_date) if args.through_date else datetime.now(shanghai).date() - timedelta(days=1)
    start = date.fromisoformat(args.from_date)
    if start > through:
        raise ValueError("from-date must not be later than through-date")
    covered: dict[str, list[str]] = {}
    releases: list[dict[str, Any]] = []
    for run_dir in sorted(news_root.iterdir()) if news_root.exists() else []:
        if not run_dir.is_dir() or run_dir.name.startswith("_"):
            continue
        manifests = list(run_dir.glob("daily_pipeline_manifest_*.json"))
        if len(manifests) != 1:
            continue
        try:
            manifest = load_json(manifests[0])
            if manifest.get("status") != "complete":
                continue
            date_value = str(manifest.get("date") or "")
            if date.fromisoformat(date_value) < start:
                continue
            protocol = int(manifest.get("pipeline_version") or 1)
            if protocol < 2:
                releases.append({"date": date_value, "local_status": "legacy-unverified",
                                 "coverage": "legacy-unverified", "remote_verified": False})
                continue
            result = verify_artifacts(run_dir, strict=True)
            if result["status"] != "pass":
                releases.append({"date": manifest.get("date"), "local_status": "invalid",
                                 "failures": result["failures"][:3]})
                continue
            coverage = manifest.get("coverage")
            receipt_path = news_root / "_publish" / f"oss_publish_receipt_{date_value}.json"
            try:
                receipt = load_json(receipt_path)
            except (OSError, ValueError):
                receipt = {}
            receipt_matches = (receipt.get("status") == "published"
                               and receipt.get("date") == date_value
                               and receipt.get("html_sha256") == manifest.get("artifact_sha256", {}).get("html"))
            releases.append({"date": date_value, "local_status": "complete",
                             "coverage": coverage or "legacy-unverified",
                             "receipt_matches_local": receipt_matches,
                             "remote_verified": False})
            if isinstance(coverage, dict):
                left = datetime.fromisoformat(coverage["start"]).astimezone(shanghai).date()
                right = datetime.fromisoformat(coverage["end"]).astimezone(shanghai).date()
                for offset in range((right - left).days):
                    covered.setdefault((left + timedelta(days=offset)).isoformat(), []).append(date_value)
        except (OSError, ValueError, KeyError):
            releases.append({"directory": run_dir.name, "local_status": "unreadable"})
    requested = [(start + timedelta(days=offset)).isoformat() for offset in range((through - start).days + 1)]
    print(json.dumps({"status": "ok", "through_date": through.isoformat(),
                      "covered_days": {day: covered[day] for day in requested if day in covered},
                      "missing_days": [day for day in requested if day not in covered],
                      "releases": releases}, ensure_ascii=False, indent=2))
    return 0


def _recover_pending_transactions(output_root: Path, index_path: Path) -> None:
    """Roll back an interrupted local commit before another commit starts."""
    root = output_root / ".release_transactions"
    if not root.exists():
        return
    for journal_path in sorted(root.glob("*/state.json")):
        journal = load_json(journal_path)
        if journal.get("status") != "prepared":
            continue
        if journal.get("output_dir") != str(output_root) or journal.get("index_path") != str(index_path):
            raise ValueError("interrupted release journal points outside its expected targets")
        manifest_files = list(output_root.glob("daily_pipeline_manifest_*.json"))
        if len(manifest_files) == 1:
            final_manifest = load_json(manifest_files[0])
            if (final_manifest.get("run_id") == journal.get("run_id")
                    and final_manifest.get("status") == "complete"
                    and verify_artifacts(output_root, strict=True)["status"] == "pass"):
                journal["status"] = "completed"
                atomic_json(journal_path, journal)
                continue
        transaction = journal_path.parent
        partial = transaction / "partial"
        partial.mkdir(exist_ok=True)
        for name in journal.get("targets", []):
            if not isinstance(name, str) or Path(name).name != name:
                raise ValueError("interrupted release journal has an unsafe target")
            target = output_root / name
            backup = transaction / "backups" / name
            if target.exists():
                os.replace(target, partial / name)
            if backup.exists():
                atomic_copy(backup, target)
        previous_index = transaction / "index_before.jsonl"
        if previous_index.exists():
            index_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(previous_index, index_path)
        elif index_path.exists() and not journal.get("index_existed"):
            os.replace(index_path, partial / "story_index.jsonl")
        journal["status"] = "rolled_back"
        atomic_json(journal_path, journal)


def _commit_local(args: argparse.Namespace) -> dict[str, Any]:
    run_root = Path(args.run_dir).expanduser().resolve()
    result = verify_artifacts(run_root, strict=args.strict)
    if result["status"] != "pass":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return {"status": "local_verification_failed", "failures": result["failures"]}
    manifest = result["manifest"]
    run_date = str(manifest["date"])
    output_root = Path(manifest["output_dir"])
    index_path = Path(manifest["index_path"])
    _recover_pending_transactions(output_root, index_path)
    staged = {key: run_root / name for key, name in manifest["artifacts"].items()}
    final = {key: output_root / name for key, name in manifest["artifacts"].items()}
    expected_names = {key: path.name for key, path in artifact_paths(run_root, run_date).items()}
    if int(manifest.get("pipeline_version") or 1) >= 2:
        expected_names.update({key: template.format(date=run_date) for key, template in REVIEW_NAMES.items()})
    if manifest["artifacts"] != expected_names:
        raise ValueError("manifest artifact identities are invalid")
    current_index_hash = sha256_file(index_path) if index_path.exists() else None
    if int(manifest.get("pipeline_version") or 1) >= 2 and current_index_hash != manifest.get("index_snapshot_sha256"):
        raise ValueError("story index changed since ranking; rerun ranking and review")
    prior = None
    if final["manifest"].exists():
        prior = load_json(final["manifest"])
        if prior.get("status") == "complete":
            old_hash = (prior.get("artifact_sha256") or {}).get("html")
            content_keys = ("html", "markdown", "feedback", "delta_config")
            same_content = all((prior.get("artifact_sha256") or {}).get(key)
                               == (manifest.get("artifact_sha256") or {}).get(key)
                               for key in content_keys)
            if same_content and verify_artifacts(output_root, strict=True)["status"] == "pass":
                return {"status": "complete", "output_dir": str(output_root), "index_path": str(index_path),
                        "local_action": "no_change"}
            if (not getattr(args, "correction_reason", None)
                    or getattr(args, "supersedes_hash", None) != old_hash):
                raise ValueError("existing release differs; explicit audited correction is required")
    output_root.mkdir(parents=True, exist_ok=True)
    backups: dict[Path, Path] = {}
    created_targets: set[Path] = set()
    index_before = index_path.read_bytes() if index_path.exists() else None
    transaction = output_root / ".release_transactions" / f"{manifest['run_id']}-{uuid.uuid4().hex[:8]}"
    (transaction / "backups").mkdir(parents=True)
    if index_before is not None:
        (transaction / "index_before.jsonl").write_bytes(index_before)
    for target in final.values():
        if target.exists():
            backup = transaction / "backups" / target.name
            shutil.copy2(target, backup)
            backups[target] = backup
        else:
            created_targets.add(target)
    journal = {"status": "prepared", "run_id": manifest["run_id"],
               "output_dir": str(output_root), "index_path": str(index_path),
               "index_existed": index_before is not None,
               "targets": [path.name for path in final.values()]}
    atomic_json(transaction / "state.json", journal)
    try:
        index_payload = load_json(run_root / ARTIFACT_NAMES["index_updates"].format(date=run_date))
        updates = index_payload.get("items") or []
        for key, staged_path in staged.items():
            target = final[key]
            atomic_copy(staged_path, target)
        upsert_index(index_path, updates)
        final_manifest = load_json(final["manifest"])
        final_manifest.update({"status": "complete", "index_commit": {"committed": True, "records": len(updates), "index_sha256": sha256_file(index_path)}})
        final_manifest["local_finalized_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if prior is not None and getattr(args, "correction_reason", None):
            final_manifest["correction"] = {
                "reason": args.correction_reason,
                "supersedes_run_id": prior.get("run_id"),
                "supersedes_html_sha256": (prior.get("artifact_sha256") or {}).get("html"),
            }
        atomic_json(final["manifest"], final_manifest)
    except Exception:
        if index_before is None:
            if index_path.exists():
                partial = transaction / "partial"
                partial.mkdir(exist_ok=True)
                os.replace(index_path, partial / "story_index.jsonl")
        else:
            atomic_copy(transaction / "index_before.jsonl", index_path)
        for target in final.values():
            backup = backups.get(target)
            if backup and backup.exists():
                atomic_copy(backup, target)
            elif target in created_targets and target.exists():
                partial = transaction / "partial"
                partial.mkdir(exist_ok=True)
                os.replace(target, partial / target.name)
        journal["status"] = "rolled_back"
        atomic_json(transaction / "state.json", journal)
        raise
    final_check = verify_artifacts(output_root, strict=True)
    if final_check["status"] != "pass":
        _recover_pending_transactions(output_root, index_path)
        print(json.dumps({"status": "local_verification_failed", "output_dir": str(output_root), "failures": final_check["failures"]}, ensure_ascii=False))
        return {"status": "local_verification_failed", "failures": final_check["failures"]}
    journal["status"] = "completed"
    atomic_json(transaction / "state.json", journal)
    return {"status": "complete", "output_dir": str(output_root), "index_path": str(index_path),
            "local_action": "committed"}


def cmd_finalize(args: argparse.Namespace) -> int:
    run_root = Path(args.run_dir).expanduser().resolve()
    manifest_files = list(run_root.glob("daily_pipeline_manifest_*.json"))
    if len(manifest_files) != 1:
        raise ValueError("staged release manifest missing or ambiguous")
    manifest = load_json(manifest_files[0])
    index_path = Path(manifest["index_path"])
    with release_lock(Path(manifest["output_dir"]).parent):
        local = _commit_local(args)
    if local["status"] != "complete":
        return 1
    from publish_daily_to_oss import auto_publish_after_finalize

    output_root = Path(local["output_dir"])
    remote_publish = auto_publish_after_finalize(
        output_root, correction_reason=getattr(args, "correction_reason", None),
        supersedes_hash=getattr(args, "supersedes_hash", None))
    print(json.dumps({**local, "remote_publish": remote_publish}, ensure_ascii=False))
    remote_required = bool(getattr(args, "require_remote", False))
    return 2 if remote_publish["status"] in {"failed", "pending"} or (remote_required and remote_publish["status"] == "disabled") else 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Generate a staged daily briefing without touching story_index.")
    run.add_argument("--config", required=True)
    run.add_argument("--output-dir")
    run.add_argument("--index")
    run.add_argument("--date")
    run.add_argument("--days", type=int, default=7)
    run.add_argument("--continuing-mode", choices=["one-line", "skip"], default="one-line")
    run.add_argument("--design-system", choices=["cosmic", "classic", "none"], default="cosmic")
    run.add_argument("--background-mode", choices=["light", "cosmic"], default="light")
    run.add_argument("--release-protocol", type=int, choices=(2,), default=2)
    run.add_argument("--coverage-start", help="Inclusive ISO 8601 boundary with UTC offset")
    run.add_argument("--coverage-end", help="Exclusive ISO 8601 boundary with UTC offset")
    run.set_defaults(func=cmd_run)
    for name, func in (("verify", cmd_verify), ("finalize", cmd_finalize)):
        command = subparsers.add_parser(name, help=f"{name.title()} a staged or published daily briefing.")
        command.add_argument("--run-dir", required=True)
        command.add_argument("--strict", action="store_true", default=True)
        if name == "verify":
            command.add_argument("--structure-only", action="store_true")
        else:
            command.add_argument("--require-remote", action="store_true")
            command.add_argument("--correction-reason")
            command.add_argument("--supersedes-hash")
        command.set_defaults(func=func)
    seal = subparsers.add_parser("seal-review", help="Bind reviewed content to a staged protocol-2 release.")
    seal.add_argument("--run-dir", required=True)
    seal.set_defaults(func=cmd_seal_review)
    template = subparsers.add_parser("review-template", help="Create unreviewed templates without approving content.")
    template.add_argument("--run-dir", required=True)
    template.set_defaults(func=cmd_review_template)
    status = subparsers.add_parser("status", help="Inspect verified day coverage without accessing OSS.")
    status.add_argument("--news-root", default=str(SCRIPT_DIR.parents[2] / "news"))
    status.add_argument("--from-date", required=True)
    status.add_argument("--through-date")
    status.set_defaults(func=cmd_status)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
