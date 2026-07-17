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
            if record["record_kind"] == "block":
                if not previous:
                    raise ValueError(
                        f"{anchor}: block override requires an exact replace fragment; "
                        "appending formulae is forbidden because it can mask PDF extraction residue"
                    )
                if previous not in record["original"]:
                    if latex in record["original"] and latex in record["zh"]:
                        continue
                    raise ValueError(f"{anchor}: exact replace fragment is absent from the Original block")
                record["original"] = record["original"].replace(previous, latex, 1)
                if previous in record["zh"]:
                    record["zh"] = record["zh"].replace(previous, latex, 1)
                elif latex not in record["zh"]:
                    raise ValueError(f"{anchor}: Chinese block needs the same reviewed formula component")
                changed += 1
            if record["record_kind"] == "formula":
                if previous and previous in record["original"]:
                    record["original"] = record["original"].replace(previous, latex, 1)
                elif latex not in record["original"]:
                    record["original"] = latex
                record["zh"] = latex
                record["notes"] = str(authored.get("zh") or "")
            record["status"] = "pass"
            record["validation_errors"] = []
            write_record(reader_dir, record)
    print(json.dumps({"overrides": len(overrides), "records_changed": changed}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
