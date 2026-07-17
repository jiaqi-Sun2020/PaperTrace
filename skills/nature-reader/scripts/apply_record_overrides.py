#!/usr/bin/env python3
"""Mechanically apply reviewed, source-bound v3 completion record overrides."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

READER_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "reader-skill" / "scripts"
if str(READER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(READER_SCRIPTS))

from completion_state import atomic_write_json, load_record, read_json, record_path, write_record  # noqa: E402
from formula_contract import bilingual_math_issues, canonical_math_signature, math_components  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir", type=Path)
    parser.add_argument("overrides_json", type=Path)
    args = parser.parse_args()
    reader_dir = args.reader_dir.resolve()
    raw_overrides = args.overrides_json.read_text(encoding="utf-8")
    # Review files may use natural single-backslash LaTeX.  They use physical
    # line structure rather than JSON control escapes, so preserve every
    # command/delimiter before parsing.
    # Preserve valid JSON escapes (notably ``\\n``).  Only a natural,
    # single-backslash LaTeX command such as ``\frac`` needs escaping before
    # JSON parsing; rewriting every backslash turns paragraph breaks into the
    # visible two-character sequence ``\\n``.
    raw_overrides = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', raw_overrides)
    overrides = json.loads(raw_overrides)
    override_sha256 = hashlib.sha256(args.overrides_json.read_bytes()).hexdigest()
    source_map = json.loads((reader_dir / "source_map.json").read_text(encoding="utf-8"))
    source_rows = {str(row.get("id") or ""): row for row in source_map.get("blocks", [])}
    changed = 0
    inventory_path = reader_dir / "reader_wiki" / "object_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory_rows = {str(row.get("id") or ""): row for row in inventory.get("objects", [])}
    for stable_id, authored in overrides.items():
        completion_path = record_path(reader_dir, stable_id)
        if not completion_path.exists():
            raise ValueError(f"unknown completion record: {stable_id}")
        # Repair overrides must be able to open a record that the newest
        # fail-closed validator has just invalidated.  Validation still runs
        # on write, so an override cannot persist a malformed replacement.
        record = read_json(completion_path)
        if authored.get("original_from_source"):
            row = source_rows.get(record["source_anchor"], {})
            record["original"] = str(row.get("original_text") or row.get("original") or row.get("text") or "")
        for key in ("original", "zh", "notes"):
            if key in authored:
                record[key] = authored[key]
        field_replacements = dict(authored.get("field_replacements") or {})
        if authored.get("original_replacements"):
            field_replacements.setdefault("original", []).extend(authored["original_replacements"])
        for field, replacements in field_replacements.items():
            if field not in {"original", "zh", "notes"}:
                raise ValueError(f"{stable_id}: unsupported replacement field: {field}")
            for replacement in replacements or []:
                if not isinstance(replacement, list) or len(replacement) != 2:
                    raise ValueError(f"{stable_id}: {field} replacements must be [old, new]")
                old = str(replacement[0]).replace(r"\n", "\n")
                new = str(replacement[1]).replace(r"\n", "\n")
                value = str(record.get(field) or "")
                if old not in value:
                    if new in value:
                        continue
                    raise ValueError(f"{stable_id}: replacement source not found in {field}: {old!r}")
                record[field] = value.replace(old, new)
        reviewed_math = authored.get("reviewed_source_math")
        if reviewed_math:
            if record.get("record_kind") != "block":
                raise ValueError(f"{stable_id}: reviewed_source_math is only valid for source blocks")
            if not isinstance(reviewed_math, dict):
                raise ValueError(f"{stable_id}: reviewed_source_math must be an object")
            reviewed_page = int(reviewed_math.get("page") or 0)
            if reviewed_page != int(record.get("source_page") or 0):
                raise ValueError(
                    f"{stable_id}: reviewed_source_math page {reviewed_page} does not match source page "
                    f"{record.get('source_page')}"
                )
            alignment = bilingual_math_issues(
                str(record.get("original") or ""),
                str(record.get("zh") or ""),
                block_id=stable_id,
            )
            if alignment:
                raise ValueError(f"{stable_id}: cannot derive a reviewed inventory: {'; '.join(alignment)}")
            original_components = math_components(str(record.get("original") or ""))
            if not original_components:
                raise ValueError(f"{stable_id}: reviewed source math has no reconstructed LaTeX components")
            inventory_components = [
                {
                    "id": f"source-{index:02d}",
                    "presentation": "display" if value.lstrip().startswith((r"\[", "$$")) else "inline",
                    "signature": canonical_math_signature(value),
                }
                for index, value in enumerate(original_components, start=1)
            ]
            record["object_metadata"].update(
                {
                    "source_math_inventory_required": True,
                    "source_math_evidence_contract": "source-math-evidence-v2",
                    "source_math_reviewed_page": reviewed_page,
                    "source_math_reviewed_by": "direct-source-page-audit",
                    "source_math_inventory": {
                        "contract": "source-math-inventory-v1",
                        "status": "complete",
                        "source_equation_labels": list(reviewed_math.get("source_equation_labels") or []),
                        "components": inventory_components,
                    },
                }
            )
        if "object_metadata" in authored:
            record["object_metadata"].update(authored["object_metadata"])
        for replacement in authored.get("inventory_signature_replacements") or []:
            if not isinstance(replacement, list) or len(replacement) != 2:
                raise ValueError(f"{stable_id}: inventory_signature_replacements must be [old, new]")
            source_inventory = record["object_metadata"].get("source_math_inventory") or {}
            components = source_inventory.get("components") if isinstance(source_inventory, dict) else None
            if not isinstance(components, list):
                raise ValueError(f"{stable_id}: source_math_inventory is unavailable for signature replacement")
            old, new = (str(value) for value in replacement)
            matches = [item for item in components if isinstance(item, dict) and str(item.get("signature") or "") == old]
            if len(matches) != 1:
                if any(isinstance(item, dict) and str(item.get("signature") or "") == new for item in components):
                    continue
                raise ValueError(f"{stable_id}: inventory signature replacement expected one match for {old!r}, found {len(matches)}")
            matches[0]["signature"] = new
        record["object_metadata"]["record_override_file"] = args.overrides_json.name
        record["object_metadata"]["record_override_sha256"] = override_sha256
        record["status"] = "pass"
        record["validation_errors"] = []
        write_record(reader_dir, record)
        persisted = load_record(reader_dir, stable_id)
        for key in ("original", "zh", "notes"):
            if key in authored and (not persisted or persisted.get(key) != record.get(key)):
                raise ValueError(f"{stable_id}: round-trip mismatch for {key}")
        if record["record_kind"] in {"figure", "table", "algorithm"}:
            row = inventory_rows.get(record["source_anchor"])
            if row is None:
                raise ValueError(f"missing inventory row: {record['source_anchor']}")
            row.update(record["object_metadata"])
            row["status"] = "pass"
        changed += 1
    atomic_write_json(inventory_path, inventory)
    print(json.dumps({"updated_records": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
