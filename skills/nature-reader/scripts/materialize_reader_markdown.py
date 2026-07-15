#!/usr/bin/env python3
"""Materialize a UTF-8-safe working paper.md from immutable PDF evidence.

The generated Markdown is deliberately incomplete: it preserves source anchors
and original text while marking Chinese translations and notes as required.
Formal completion and HTML generation must still reject these placeholders.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from audit_reader_text import audit_text


TRANSLATION_PLACEHOLDER = "[translation-required]"
NOTE_PLACEHOLDER = "[block-note-required]"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.read_text(encoding="utf-8")
    temporary.replace(path)


def atomic_write_json(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, payload)
    json.loads(path.read_text(encoding="utf-8"))


def build_object_inventory(source_map: dict[str, Any], source_map_sha256: str) -> dict[str, Any]:
    """Seed mutable object-completion work without ever altering raw evidence."""
    objects: list[dict[str, Any]] = []
    for collection, kind in (("figures", "figure"), ("tables", "table"), ("algorithms", "algorithm")):
        for source_object in source_map.get(collection, []) or []:
            if not isinstance(source_object, dict):
                continue
            source_id = str(source_object.get("id") or "")
            objects.append({
                "id": source_id,
                "kind": kind,
                "page": source_object.get("page"),
                "source_object_id": source_id,
                "source_block_id": str(source_object.get("caption_id") or source_object.get("source_block_id") or ""),
                "asset_path": "",
                "bbox": [],
                "representation": "",
                "status": "completion-required",
            })
    return {
        "version": 2,
        "role": "derived_object_completion_inventory",
        "source_map_sha256": source_map_sha256,
        "objects": objects,
    }


def visible_source_text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    result: list[str] = []
    for char in text:
        if unicodedata.category(char) == "Cc" and char not in "\n\t":
            result.append(f"[U+{ord(char):04X}]")
        else:
            result.append(char)
    return "".join(result)


def build_markdown(source_map: dict[str, Any]) -> str:
    paper = source_map.get("paper") or {}
    title = visible_source_text(paper.get("title")) or "Untitled Paper"
    lines = [
        f"# {title}",
        "",
        "> Draft materialized from immutable source evidence. Complete every translation, note, formula, figure/table card, and algorithm/pseudocode card before formal HTML generation. Bibliography blocks remain original-only.",
        "",
        "## Source Page Index",
        "",
    ]
    for page in source_map.get("pages", []) or []:
        if not isinstance(page, dict):
            continue
        page_no = page.get("page")
        source_page = str(page.get("source_page_image") or "").replace("\\", "/")
        if source_page:
            lines.append(f"- p.{page_no}: [{source_page}]({source_page})")
    lines.extend(["", "## Bilingual Reader", ""])

    for block in source_map.get("blocks", []) or []:
        if not isinstance(block, dict):
            continue
        block_id = str(block.get("id") or "").strip()
        if not block_id:
            continue
        page_no = block.get("page")
        original = visible_source_text(
            block.get("original_text") or block.get("original") or block.get("text")
        )
        if str(block.get("type") or "").lower() == "reference":
            lines.extend([
                f'<a id="{block_id}"></a>',
                f"**Source:** p.{page_no} {block_id}",
                "",
                f"**Reference list (original only):** {original}",
                "",
            ])
            continue
        lines.extend([
            f'<a id="{block_id}"></a>',
            f"**Source:** p.{page_no} {block_id}",
            "",
            f"**Original:** {original}",
            "",
            f"**中文:** {TRANSLATION_PLACEHOLDER}",
            "",
            f"**注释:** {NOTE_PLACEHOLDER}",
            "",
        ])

    objects: list[tuple[str, dict[str, Any]]] = []
    for key in ("figures", "tables", "algorithms"):
        for item in source_map.get(key, []) or []:
            if isinstance(item, dict):
                objects.append((key[:-1], item))
    if objects:
        lines.extend(["## Source Object Completion Queue", ""])
        for kind, item in objects:
            object_id = item.get("id") or "unknown"
            page_no = item.get("page")
            status = item.get("status") or "completion-required"
            lines.append(f"- {kind} `{object_id}` on p.{page_no}: {status}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def materialize_reader_markdown(reader_dir: Path, *, force: bool = False) -> dict[str, Any]:
    source_map_path = reader_dir / "source_map.json"
    paper_md_path = reader_dir / "paper.md"
    report_path = reader_dir / "paper_materialization.json"
    object_inventory_path = reader_dir / "reader_wiki" / "object_inventory.json"
    if not source_map_path.is_file():
        raise FileNotFoundError(f"missing source_map.json: {source_map_path}")
    if paper_md_path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing paper.md: {paper_md_path}")

    source_hash_before = sha256_file(source_map_path)
    source_map = read_json(source_map_path)
    markdown = build_markdown(source_map)
    issues = audit_text(markdown)
    if issues:
        raise ValueError("materialized paper.md failed text integrity: " + "; ".join(issues))
    atomic_write_text(paper_md_path, markdown)
    if not object_inventory_path.exists() or force:
        atomic_write_json(object_inventory_path, build_object_inventory(source_map, source_hash_before))
    source_hash_after = sha256_file(source_map_path)
    if source_hash_after != source_hash_before:
        raise RuntimeError("source_map.json changed during paper.md materialization")

    report = {
        "version": 2,
        "generated_at": utc_now(),
        "status": "paper_md_materialized_completion_required",
        "paper_md": {"path": "paper.md", "sha256": sha256_file(paper_md_path)},
        "source_map": {
            "path": "source_map.json",
            "sha256_before": source_hash_before,
            "sha256_after": source_hash_after,
            "immutable": source_hash_before == source_hash_after,
        },
        "object_inventory": {
            "path": "reader_wiki/object_inventory.json",
            "sha256": sha256_file(object_inventory_path),
        },
        "counts": {
            "blocks": sum(1 for row in source_map.get("blocks", []) or [] if isinstance(row, dict) and row.get("id")),
            "figures": len(source_map.get("figures", []) or []),
            "tables": len(source_map.get("tables", []) or []),
            "algorithms": len(source_map.get("algorithms", []) or []),
        },
        "next_action": "Complete bilingual blocks; keep bibliography original-only; fill reader_wiki/object_inventory.json with figure/table/algorithm provenance; reconstruct LaTeX; then run preflight_reader_bundle.py and complete_reader_bundle.py.",
    }
    atomic_write_json(report_path, report)
    return report


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir", type=Path)
    parser.add_argument("--force", action="store_true", help="Replace an existing derived paper.md intentionally.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    reader_dir = args.reader_dir.expanduser().resolve()
    try:
        report = materialize_reader_markdown(reader_dir, force=args.force)
    except Exception as exc:
        print(f"paper.md materialization failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
