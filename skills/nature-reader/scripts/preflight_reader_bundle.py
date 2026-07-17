#!/usr/bin/env python3
"""Inventory a reader bundle before translation or HTML generation.

The preflight report is intentionally source-first.  It exposes every
registered and caption-discovered figure, table, and algorithm/pseudocode
object; identifies bibliography blocks; and verifies that formula-source
blocks have Original-side LaTeX once a paper.md exists.  It never translates,
crops, or mutates immutable source evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
READER_SCRIPTS = ROOT / "skills" / "reader-skill" / "scripts"
if str(READER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(READER_SCRIPTS))
from formula_contract import atomic_formula_issues  # noqa: E402


ANCHOR_RE = re.compile(r'(?m)^<a\s+id=["\']([^"\']+)["\']\s*>\s*</a>\s*$')
FIGURE_CAPTION_RE = re.compile(r'(?im)^\s*(?:fig(?:ure)?\.?\s*\d+\b)')
TABLE_CAPTION_RE = re.compile(r'(?im)^\s*(?:table\s+[ivxlcdm\d]+\b)')
REFERENCE_ENTRY_RE = re.compile(r'(?m)^\s*\[\d+\]\s+')
REFERENCE_HEADING_RE = re.compile(r'(?im)^\s*(?:references|bibliography)\s*$')
PSEUDOCODE_RE = re.compile(r'\b(?:algorithm|procedure|pseudocode)\b', re.I)
MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)')


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def source_text(row: dict[str, Any]) -> str:
    return str(row.get("original_text") or row.get("original") or row.get("text") or "")


def split_segments(markdown: str) -> dict[str, str]:
    matches = list(ANCHOR_RE.finditer(markdown))
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result[match.group(1)] = markdown[match.end():end]
    return result


def caption_candidates(reader_dir: Path) -> dict[str, list[dict[str, Any]]]:
    figures: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    for raw_page in sorted((reader_dir / "raw" / "pages").glob("page-*.txt")):
        page_match = re.search(r"page-(\d+)", raw_page.stem)
        page = int(page_match.group(1)) if page_match else 0
        for raw_line in raw_page.read_text(encoding="utf-8", errors="replace").splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if FIGURE_CAPTION_RE.match(line):
                figures.append({"page": page, "caption_candidate": line})
            elif TABLE_CAPTION_RE.match(line):
                tables.append({"page": page, "caption_candidate": line})
    return {"figures": figures, "tables": tables}


def registered_caption_tokens(rows: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        text = str(row.get("caption_original") or row.get("caption") or "")
        match = re.search(r"(?i)(fig(?:ure)?\.?\s*(\d+)|table\s+([ivxlcdm\d]+))", text)
        if match:
            values.add(f"figure:{match.group(2)}" if match.group(2) else f"table:{match.group(3).lower()}")
    return values


def build_preflight_manifest(reader_dir: Path) -> tuple[dict[str, Any], list[str]]:
    source_map_path = reader_dir / "source_map.json"
    source_map = read_json(source_map_path)
    paper_path = reader_dir / "paper.md"
    markdown = paper_path.read_text(encoding="utf-8") if paper_path.exists() else ""
    segments = split_segments(markdown)
    source_blocks = [row for row in source_map.get("blocks", []) if isinstance(row, dict)]
    figures = [row for row in source_map.get("figures", []) if isinstance(row, dict)]
    tables = [row for row in source_map.get("tables", []) if isinstance(row, dict)]
    algorithms = [row for row in source_map.get("algorithms", []) if isinstance(row, dict)]
    inventory_path = reader_dir / "reader_wiki" / "object_inventory.json"
    inventory = read_json(inventory_path) if inventory_path.exists() else {}
    inventory_hash = sha256_file(inventory_path) if inventory_path.exists() else ""
    inventory_source_hash = str(inventory.get("source_map_sha256") or "")
    if not inventory_path.exists():
        issues = ["missing reader_wiki/object_inventory.json"]
    elif inventory_source_hash != sha256_file(source_map_path):
        issues = ["object_inventory.json is not bound to the current immutable source_map.json"]
    else:
        issues = []
    inventory_rows = {
        str(row.get("id") or ""): row
        for row in inventory.get("objects", []) or []
        if isinstance(row, dict)
    }
    inventory_source_items = {
        str(row.get("stable_id") or "")
        for row in inventory.get("source_items", []) or []
        if isinstance(row, dict)
    }
    expected_source_items: set[str] = set()
    for row in source_blocks:
        source_id = str(row.get("id") or row.get("block_id") or "")
        block_type = str(row.get("type") or "paragraph").lower()
        if source_id:
            expected_source_items.add(f"{'reference' if block_type == 'reference' else 'block'}:{source_id}")
            if block_type in {"formula", "equation_or_formula"}:
                expected_source_items.add(f"formula:{source_id}:01")
    for collection, kind in ((figures, "figure"), (tables, "table"), (algorithms, "algorithm")):
        expected_source_items.update(f"{kind}:{str(row.get('id') or '')}" for row in collection if str(row.get("id") or ""))
    if not inventory_source_items:
        issues.append("object_inventory.json lacks the v3 source-wide inventory")
    else:
        missing_inventory_items = sorted(expected_source_items - inventory_source_items)
        if missing_inventory_items:
            issues.append("object_inventory.json misses source items: " + ", ".join(missing_inventory_items[:12]))
    candidates = caption_candidates(reader_dir)

    figure_tokens = registered_caption_tokens(figures)
    table_tokens = registered_caption_tokens(tables)
    unresolved_caption_candidates: list[dict[str, Any]] = []
    for kind, token_set in (("figure", figure_tokens), ("table", table_tokens)):
        for candidate in candidates[f"{kind}s"]:
            match = re.search(r"(?i)(fig(?:ure)?\.?\s*(\d+)|table\s+([ivxlcdm\d]+))", candidate["caption_candidate"])
            token = (f"figure:{match.group(2)}" if match and match.group(2) else
                     f"table:{match.group(3).lower()}" if match and match.group(3) else "")
            if token and token not in token_set:
                unresolved_caption_candidates.append({"kind": kind, **candidate})
                issues.append(f"p.{candidate['page']}: unregistered {kind} caption candidate {token}")

    object_rows = {str(row.get("id") or ""): row for row in [*figures, *tables, *algorithms]}
    object_checks: list[dict[str, Any]] = []
    for object_id, row in object_rows.items():
        kind = "algorithm" if object_id.startswith("A") else "figure" if object_id.startswith("F") else "table"
        segment = segments.get(object_id, "")
        inventory_row = inventory_rows.get(object_id, {})
        if not inventory_row:
            issues.append(f"{object_id}: missing derived-object inventory row")
        elif str(inventory_row.get("kind") or "") != kind:
            issues.append(f"{object_id}: derived-object inventory kind does not match source object")
        asset_path = str(inventory_row.get("asset_path") or "").replace("\\", "/")
        card_present = bool(segment)
        asset_exists = bool(asset_path) and (reader_dir / asset_path).is_file()
        uses_source_page = "assets/source_pages/" in asset_path
        if kind == "figure":
            if not card_present:
                issues.append(f"{object_id}: registered figure lacks a Markdown card")
            if not asset_path or not asset_exists or uses_source_page:
                issues.append(f"{object_id}: figure requires a tight local crop recorded as asset_path")
            if not inventory_row.get("bbox"):
                issues.append(f"{object_id}: figure crop lacks source-page bbox provenance")
        elif kind == "table":
            if not card_present:
                issues.append(f"{object_id}: registered table lacks a Markdown card")
            if str(inventory_row.get("representation") or "") not in {"semantic_table", "tight_crop"}:
                issues.append(f"{object_id}: table inventory must declare semantic_table or tight_crop")
        else:
            if not card_present:
                issues.append(f"{object_id}: registered algorithm/pseudocode lacks a Markdown card")
            if str(inventory_row.get("representation") or "") != "latex_compiled_algorithm":
                issues.append(f"{object_id}: algorithm inventory must declare latex_compiled_algorithm")
            tex_path = str(inventory_row.get("latex_source_path") or "").replace("\\", "/")
            compiled_path = str(inventory_row.get("compiled_asset_path") or "").replace("\\", "/")
            manifest_path = str(inventory_row.get("compile_manifest_path") or "").replace("\\", "/")
            if not tex_path or not (reader_dir / tex_path).is_file():
                issues.append(f"{object_id}: algorithm LaTeX source is absent")
            if not compiled_path or not (reader_dir / compiled_path).is_file():
                issues.append(f"{object_id}: compiled Algorithm asset is absent")
            if not manifest_path or not (reader_dir / manifest_path).is_file():
                issues.append(f"{object_id}: Algorithm compile manifest is absent")
        object_checks.append({
            "id": object_id,
            "kind": kind,
            "card_present": card_present,
            "asset_path": asset_path,
            "asset_exists": asset_exists,
            "bbox_present": bool(inventory_row.get("bbox")),
            "representation": str(inventory_row.get("representation") or ""),
        })

    formula_rows = [
        row for row in source_blocks
        if str(row.get("type") or "").lower() in {"formula", "equation_or_formula"}
    ]
    formula_checks: list[dict[str, Any]] = []
    for row in formula_rows:
        block_id = str(row.get("id") or "")
        segment = segments.get(block_id, "")
        original_match = re.search(r"(?ms)^\*\*Original:\*\*\s*(.*?)(?=^\*\*(?:中文|Notes|注释):\*\*|\Z)", segment)
        original = original_match.group(1).strip() if original_match else ""
        has_latex = bool(MATH_RE.search(original))
        if paper_path.exists() and not has_latex:
            issues.append(f"{block_id}: formula source block lacks Original-side LaTeX before HTML generation")
        formula_checks.append({"id": block_id, "original_latex": has_latex})

    zh_label = "\u4e2d\u6587"
    notes_label = "\u6ce8\u91ca"
    for row in source_blocks:
        block_id = str(row.get("id") or "")
        if not block_id or str(row.get("type") or "").lower() == "reference":
            continue
        segment = segments.get(block_id, "")
        original_match = re.search(
            rf"(?ms)^\*\*Original:\*\*\s*(.*?)(?=^\*\*(?:{zh_label}|Notes|{notes_label}):\*\*|\Z)",
            segment,
        )
        zh_match = re.search(
            rf"(?ms)^\*\*{zh_label}:\*\*\s*(.*?)(?=^\*\*(?:Notes|{notes_label}):\*\*|\Z)",
            segment,
        )
        for field, match in (("Original", original_match), ("Chinese", zh_match)):
            value = match.group(1).strip() if match else ""
            for message in atomic_formula_issues(value, field=field):
                issues.append(f"{block_id}: {message}")

    reference_blocks = [row for row in source_blocks if str(row.get("type") or "").lower() == "reference"]
    raw_reference_detected = False
    for raw_page in sorted((reader_dir / "raw" / "pages").glob("page-*.txt")):
        raw = raw_page.read_text(encoding="utf-8", errors="replace")
        if REFERENCE_HEADING_RE.search(raw) or len(REFERENCE_ENTRY_RE.findall(raw)) >= 2:
            raw_reference_detected = True
            break
    if raw_reference_detected and not reference_blocks:
        issues.append("bibliography evidence exists but source_map has no reference-only blocks")
    for row in reference_blocks:
        block_id = str(row.get("id") or "")
        if "**Reference list (original only):**" not in segments.get(block_id, ""):
            issues.append(f"{block_id}: reference block must use original-only Markdown shape")

    kinds = Counter(str(row.get("type") or "paragraph") for row in source_blocks)
    manifest = {
        "version": 2,
        "generated_at": utc_now(),
        "status": "pass" if not issues else "fail",
        "source_map": {"path": "source_map.json", "sha256": sha256_file(source_map_path)},
        "object_inventory": {
            "path": "reader_wiki/object_inventory.json",
            "sha256": inventory_hash,
            "source_map_sha256": inventory_source_hash,
        },
        "paper_md": {"path": "paper.md", "sha256": sha256_file(paper_path) if paper_path.exists() else ""},
        "inventory": {
            "source_blocks_by_type": dict(sorted(kinds.items())),
            "figures": len(figures),
            "tables": len(tables),
            "algorithms": len(algorithms),
            "formula_blocks": len(formula_rows),
            "reference_blocks": len(reference_blocks),
            "source_items": len(expected_source_items),
        },
        "object_checks": object_checks,
        "formula_checks": formula_checks,
        "unresolved_caption_candidates": unresolved_caption_candidates,
        "issues": issues,
    }
    return manifest, issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir", type=Path)
    args = parser.parse_args()
    reader_dir = args.reader_dir.expanduser().resolve()
    try:
        manifest, _issues = build_preflight_manifest(reader_dir)
        path = reader_dir / "reader_wiki" / "preflight_manifest.json"
        write_json(path, manifest)
    except Exception as exc:
        print(f"reader preflight failed: {exc}")
        return 2
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
