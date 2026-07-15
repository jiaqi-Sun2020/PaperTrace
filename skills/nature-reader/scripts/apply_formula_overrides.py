#!/usr/bin/env python3
"""Apply directly authored formula overrides to source-bound completion records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

READER_SCRIPTS = Path(__file__).resolve().parent.parent.parent / "reader-skill" / "scripts"
if str(READER_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(READER_SCRIPTS))

from completion_state import load_record, write_record  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reader_dir", type=Path)
    args = parser.parse_args()
    reader_dir = args.reader_dir.expanduser().resolve()
    overrides = json.loads((reader_dir / "reader_wiki" / "formula_overrides.json").read_text(encoding="utf-8"))
    changed = 0
    for anchor, authored in overrides.items():
        latex = str(authored.get("latex") or "").strip()
        if not latex:
            raise ValueError(f"{anchor}: empty authored LaTeX override")
        for stable_id in (f"block:{anchor}", f"formula:{anchor}:01"):
            record = load_record(reader_dir, stable_id)
            if record is None:
                continue
            previous = str(authored.get("replace") or "").strip()
            if previous and previous in record["original"]:
                record["original"] = record["original"].replace(previous, latex)
                changed += 1
            if latex not in record["original"]:
                record["original"] = record["original"].rstrip() + "\n\n" + latex
                changed += 1
            if record["record_kind"] == "formula":
                record["zh"] = str(authored.get("zh") or "")
                record["notes"] = str(authored.get("zh") or "")
            record["status"] = "pass"
            record["validation_errors"] = []
            write_record(reader_dir, record)
    print(json.dumps({"overrides": len(overrides), "records_changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
