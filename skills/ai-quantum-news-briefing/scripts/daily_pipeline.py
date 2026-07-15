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
from datetime import date, datetime
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
from briefing_to_feedback_html import render_html
from config_to_news_feedback import export_feedback
from lean_html import apply_design_system, design_audit_issues
from news_delta import (
    load_index,
    render_markdown,
    transform_config,
    upsert_index,
)


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


def verify_artifacts(run_root: Path, *, strict: bool = True) -> dict[str, Any]:
    manifest_files = list(run_root.glob("daily_pipeline_manifest_*.json"))
    if not manifest_files:
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
            "id=\"saveBtn\"",
            "localStorage",
            'data-lean-bg="light"',
            'data-lean-bg-option="light"',
            'data-lean-bg-option="cosmic"',
        )
        for marker in required_html:
            if marker not in html_text:
                failures.append(f"HTML contract marker missing: {marker}")
        if manifest.get("design_system", "cosmic") == "cosmic":
            failures.extend(design_audit_issues(html_text))
        manifest_hashes = manifest.get("artifact_sha256") or {}
        for key, path in paths.items():
            if key != "manifest" and manifest_hashes.get(key) and manifest_hashes[key] != sha256_file(path):
                failures.append(f"manifest hash mismatch: {key}")

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
    if "analysis_language" not in raw_config:
        raw_config = dict(raw_config)
        raw_config["analysis_language"] = "zh-CN"
    if "academic_delivery" not in raw_config:
        raw_config = dict(raw_config)
        raw_config["academic_delivery"] = {
            "required": True,
            "minimum_items": 5,
            "context_days": 7,
            "policy": "Include at least five academic paper records, including one non-arXiv formal venue paper, in a dedicated academic section.",
        }
    if "social_delivery" not in raw_config:
        raw_config = dict(raw_config)
        raw_config["social_delivery"] = {
            "minimum_items": 1,
            "policy": "Include at least one source-grounded, non-academic item in a dedicated social news section.",
        }
    assert_config_text_integrity(raw_config)
    run_date = infer_date(raw_config, args.date).isoformat()
    output_root = Path(args.output_dir or (config_path.parents[2] / "news" / run_date)).expanduser().resolve()
    run_id = f"{run_date}-{uuid.uuid4().hex[:12]}"
    run_root = output_root / ".staging" / run_id
    run_root.mkdir(parents=True, exist_ok=False)
    index_path = Path(args.index).expanduser().resolve() if args.index else output_root.parent / "_index" / "story_index.jsonl"

    transformed, delta_manifest, index_updates = transform_config(
        raw_config,
        load_index(index_path),
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
        "pipeline_version": 1,
        "status": "staged",
        "run_id": run_id,
        "date": run_date,
        "input_config": str(config_path),
        "input_config_sha256": sha256_file(config_path),
        "output_dir": str(output_root),
        "index_path": str(index_path),
        "delta_counts": delta_manifest.get("counts", {}),
        "expected_concepts": len(feedback["items"]),
        "default_status": "unrated",
        "design_system": args.design_system,
        "background_mode": args.background_mode,
        "artifacts": {key: path.name for key, path in names.items()},
        "artifact_sha256": {key: sha256_file(path) for key, path in names.items() if key != "manifest"},
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    atomic_json(names["manifest"], manifest)
    print(json.dumps({"status": "staged", "run_id": run_id, "run_dir": str(run_root)}, ensure_ascii=False))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    run_root = Path(args.run_dir).expanduser().resolve()
    result = verify_artifacts(run_root, strict=args.strict)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 1


def cmd_finalize(args: argparse.Namespace) -> int:
    run_root = Path(args.run_dir).expanduser().resolve()
    result = verify_artifacts(run_root, strict=args.strict)
    if result["status"] != "pass":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1
    manifest = result["manifest"]
    run_date = str(manifest["date"])
    output_root = Path(manifest["output_dir"])
    index_path = Path(manifest["index_path"])
    staged = artifact_paths(run_root, run_date)
    final = artifact_paths(output_root, run_date)
    output_root.mkdir(parents=True, exist_ok=True)
    backups: dict[Path, Path] = {}
    created_targets: set[Path] = set()
    index_before = index_path.read_bytes() if index_path.exists() else None
    try:
        index_payload = load_json(run_root / ARTIFACT_NAMES["index_updates"].format(date=run_date))
        updates = index_payload.get("items") or []
        for key, staged_path in staged.items():
            target = final[key]
            if target.exists():
                backup = target.with_name(target.name + f".{manifest['run_id']}.bak")
                shutil.copy2(target, backup)
                backups[target] = backup
            else:
                created_targets.add(target)
            os.replace(staged_path, target)
        upsert_index(index_path, updates)
        final_manifest = load_json(final["manifest"])
        final_manifest.update({"status": "complete", "index_commit": {"committed": True, "records": len(updates), "index_sha256": sha256_file(index_path)}})
        atomic_json(final["manifest"], final_manifest)
    except Exception:
        if index_before is None:
            if index_path.exists():
                index_path.unlink()
        else:
            atomic_text(index_path, index_before.decode("utf-8"))
        for target in final.values():
            backup = backups.get(target)
            if backup and backup.exists():
                os.replace(backup, target)
            elif target in created_targets and target.exists():
                target.unlink()
        raise
    finally:
        for backup in backups.values():
            if backup.exists():
                backup.unlink()
    print(json.dumps({"status": "complete", "output_dir": str(output_root), "index_path": str(index_path)}, ensure_ascii=False))
    return 0


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
    run.set_defaults(func=cmd_run)
    for name, func in (("verify", cmd_verify), ("finalize", cmd_finalize)):
        command = subparsers.add_parser(name, help=f"{name.title()} a staged or published daily briefing.")
        command.add_argument("--run-dir", required=True)
        command.add_argument("--strict", action="store_true", default=True)
        command.set_defaults(func=func)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
