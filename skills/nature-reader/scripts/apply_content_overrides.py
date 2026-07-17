#!/usr/bin/env python3
"""Apply reviewed per-block Chinese translations and notes to a reader draft.

This is deliberately a mechanical materialization helper.  It does not create,
translate, summarize, or validate content; the supplied JSON remains the reviewable
human/agent-authored input and the strict completion gate remains authoritative.
"""

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

from completion_state import load_record, write_record  # noqa: E402


BLOCK_RE = re.compile(
    r'(?ms)(<a id="(?P<id>[SEC]\d{3})"></a>.*?'
    r'^\*\*中文:\*\* )(?P<zh>.*?)(?=\n\n^\*\*注释:\*\* )'
    r'(\n\n^\*\*注释:\*\* )(?P<note>.*?)(?=\n\n(?:<a id="[SEC]\d{3}"></a>|## |\Z))'
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reader_dir", type=Path)
    parser.add_argument("overrides_json", type=Path)
    parser.add_argument("--partial", action="store_true", help="Apply a reviewed subset of block overrides.")
    args = parser.parse_args()

    paper_path = args.reader_dir.resolve() / "paper.md"
    overrides_path = args.overrides_json.resolve()
    raw_overrides = overrides_path.read_text(encoding="utf-8")
    # Directly authored LaTeX is often written with natural single
    # backslashes. Preserve those commands while retaining normal JSON escapes.
    # Treat a backslash followed by an ASCII letter as a literal LaTeX
    # command, including names that collide with JSON escapes (\beta, \tau,
    # \nabla, ...). Authored override files use physical newlines rather than
    # JSON's \n/\t escapes, so this normalization is unambiguous here.
    raw_overrides = re.sub(r'(?<!\\)\\(?!["\\])', r'\\\\', raw_overrides)
    overrides = json.loads(raw_overrides)
    text = paper_path.read_text(encoding="utf-8")

    found = {match.group("id") for match in BLOCK_RE.finditer(text)}
    supplied = set(overrides)
    # In canonical v3 Markdown an algorithm source block may be intentionally
    # replaced by its authoritative compiled algorithm card, while its source
    # completion record still needs reviewed prose metadata.  Partial mode is
    # therefore record-scoped, not limited to anchors currently materialized
    # in paper.md.
    unknown_records = sorted(
        block_id for block_id in supplied
        if load_record(args.reader_dir.resolve(), f"block:{block_id}") is None
    )
    if (not args.partial and found != supplied) or (args.partial and unknown_records):
        missing = sorted(found - supplied)
        extra = unknown_records if args.partial else sorted(supplied - found)
        raise SystemExit(f"override ID mismatch: missing={missing}, extra={extra}")

    def replace(match: re.Match[str]) -> str:
        block_id = match.group("id")
        if block_id not in overrides:
            return match.group(0)
        item = overrides[block_id]
        zh = str(item.get("zh", "")).strip()
        note = str(item.get("note", "")).strip()
        if not zh or not note:
            raise SystemExit(f"empty reviewed content for {block_id}")
        return f"{match.group(1)}{zh}{match.group(4)}{note}"

    updated, count = BLOCK_RE.subn(replace, text)
    expected = len(overrides) if args.partial else len(found)
    if count != len(found):
        raise SystemExit(f"visited {count} blocks, expected {len(found)}")
    paper_path.write_text(updated, encoding="utf-8")
    source_map = json.loads((args.reader_dir.resolve() / "source_map.json").read_text(encoding="utf-8"))
    source_rows = {str(row.get("id") or ""): row for row in source_map.get("blocks", [])}
    records_changed = 0
    for block_id, item in overrides.items():
        record = load_record(args.reader_dir.resolve(), f"block:{block_id}")
        source_row = source_rows.get(block_id)
        if record is None or source_row is None:
            continue
        # Translation/note overrides must never silently reset a reviewed
        # Original-side mathematical reconstruction to noisy PDF text.  An
        # Original mutation is explicit and reviewable.
        if item.get("original_from_source"):
            record["original"] = str(source_row.get("original_text") or source_row.get("original") or source_row.get("text") or "")
        elif "original" in item:
            record["original"] = str(item.get("original") or "").strip()
        record["zh"] = str(item.get("zh") or "").strip()
        record["notes"] = str(item.get("note") or "").strip()
        authored_payload = record["zh"] + "\n" + record["notes"]
        record["object_metadata"]["content_override_file"] = overrides_path.name
        record["object_metadata"]["content_override_sha256"] = hashlib.sha256(raw_overrides.encode("utf-8")).hexdigest()
        record["object_metadata"]["authored_content_sha256"] = hashlib.sha256(authored_payload.encode("utf-8")).hexdigest()
        record["status"] = "pass"
        record["validation_errors"] = []
        write_record(args.reader_dir.resolve(), record)
        persisted = load_record(args.reader_dir.resolve(), f"block:{block_id}")
        if not persisted or persisted.get("zh") != record["zh"] or persisted.get("notes") != record["notes"]:
            raise SystemExit(f"round-trip mismatch after writing {block_id}")
        records_changed += 1
    print(json.dumps({"paper": str(paper_path), "updated_blocks": expected, "records_changed": records_changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
