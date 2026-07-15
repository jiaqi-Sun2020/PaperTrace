#!/usr/bin/env python3
"""Repair obvious bibliography pages misclassified by an older extractor.

The repair is deliberately narrow and reversible: only pages containing at
least two line-leading numbered citations are changed, superseded completion
records and the prior inventory are archived, and source-bound hashes are
rebuilt atomically.  It refuses to touch a reader that already passed the
formal audit.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
READER_SCRIPTS = SCRIPT_DIR.parent.parent / "reader-skill" / "scripts"
if str(READER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(READER_SCRIPTS))

from completion_state import (  # noqa: E402
    PIPELINE_VERSION,
    SCHEMA_VERSION,
    atomic_write_json,
    evidence_hash,
    expected_records,
    read_json,
    record_path,
    sha256_file,
    utc_now,
    write_record,
)


REFERENCE_ENTRY_RE = re.compile(r"(?m)^\s*\[\d+\]\s+")


def bibliography_pages(reader_dir: Path) -> set[int]:
    pages: set[int] = set()
    for raw_page in sorted((reader_dir / "raw" / "pages").glob("page-*.txt")):
        match = re.search(r"page-(\d+)", raw_page.stem)
        text = raw_page.read_text(encoding="utf-8", errors="replace")
        if match and len(REFERENCE_ENTRY_RE.findall(text)) >= 2:
            pages.add(int(match.group(1)))
    return pages


def repair(reader_dir: Path) -> dict[str, object]:
    status_path = reader_dir / "reader_wiki" / "formal_status.json"
    if status_path.exists() and read_json(status_path).get("status") == "formal_pass":
        raise ValueError("refusing to alter an already audited formal reader")

    source_path = reader_dir / "source_map.json"
    source_map = read_json(source_path)
    pages = bibliography_pages(reader_dir)
    affected = [
        row for row in source_map.get("blocks", [])
        if isinstance(row, dict) and int(row.get("page") or 0) in pages
    ]
    if not affected:
        return {"status": "unchanged", "pages": sorted(pages), "records": 0}
    if any(str(row.get("type") or "").lower() == "reference" for row in affected):
        return {"status": "already_repaired", "pages": sorted(pages), "records": len(affected)}
    if any(len(REFERENCE_ENTRY_RE.findall(str(row.get("original_text") or ""))) == 0 for row in affected):
        raise ValueError("bibliography page contains a non-citation block; manual source review required")

    wiki = reader_dir / "reader_wiki"
    archive = wiki / "archived_misclassified_blocks"
    archive.mkdir(parents=True, exist_ok=True)
    source_archive = archive / "source_map.before_bibliography_repair.json"
    if not source_archive.exists():
        shutil.copy2(source_path, source_archive)

    old_records: list[tuple[Path, dict[str, object]]] = []
    for row in affected:
        old_anchor = str(row.get("id") or "")
        path = record_path(reader_dir, f"block:{old_anchor}")
        if not path.exists():
            raise ValueError(f"missing completion record for misclassified block {old_anchor}")
        old_records.append((path, read_json(path)))

    for index, row in enumerate(affected, start=1):
        row["id"] = f"R{index:03d}"
        row["type"] = "reference"
    atomic_write_json(source_path, source_map)

    for path, record in old_records:
        destination = archive / path.name
        if destination.exists():
            destination = archive / f"{path.stem}.{utc_now().replace(':', '-')}{path.suffix}"
        path.replace(destination)

    pdf_hash = str((source_map.get("paper") or {}).get("source_pdf_sha256") or "").lower()
    for row in affected:
        anchor = str(row["id"])
        record = {
            "schema_version": SCHEMA_VERSION,
            "pipeline_version": PIPELINE_VERSION,
            "stable_id": f"reference:{anchor}",
            "record_kind": "reference",
            "block_type": "reference",
            "source_anchor": anchor,
            "source_page": int(row.get("page") or 1),
            "source_evidence_hash": evidence_hash(row),
            "source_pdf_sha256": pdf_hash,
            "original": str(row.get("original_text") or ""),
            "zh": "",
            "notes": "",
            "object_metadata": {"source_object": False},
            "status": "pass",
            "validation_errors": [],
            "updated_at": utc_now(),
        }
        write_record(reader_dir, record)

    inventory_path = wiki / "object_inventory.json"
    inventory = read_json(inventory_path)
    inventory_archive = archive / "object_inventory.before_bibliography_repair.json"
    if not inventory_archive.exists():
        shutil.copy2(inventory_path, inventory_archive)
    planned = expected_records(source_map)
    inventory["source_map_sha256"] = sha256_file(source_path)
    inventory["source_items"] = [
        {
            "id": row["source_anchor"],
            "stable_id": row["stable_id"],
            "kind": row["record_kind"],
            "block_type": row["block_type"],
            "page": row["source_page"],
            "source_evidence_hash": row["source_evidence_hash"],
            "status": "complete",
        }
        for row in planned
    ]
    atomic_write_json(inventory_path, inventory)

    manifest_path = reader_dir / "raw_source_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        manifest["source_map"] = {"path": "source_map.json", "sha256": sha256_file(source_path)}
        atomic_write_json(manifest_path, manifest)

    return {
        "status": "repaired",
        "pages": sorted(pages),
        "records": len(affected),
        "source_map_sha256": sha256_file(source_path),
        "archive": str(archive),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir", type=Path)
    args = parser.parse_args()
    try:
        result = repair(args.reader_dir.expanduser().resolve())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
