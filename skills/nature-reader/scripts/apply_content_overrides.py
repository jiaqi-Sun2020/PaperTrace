#!/usr/bin/env python3
"""Apply reviewed per-block Chinese translations and notes to a reader draft.

This is deliberately a mechanical materialization helper.  It does not create,
translate, summarize, or validate content; the supplied JSON remains the reviewable
human/agent-authored input and the strict completion gate remains authoritative.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


BLOCK_RE = re.compile(
    r'(?ms)(<a id="(?P<id>[SE]\d{3})"></a>.*?'
    r'^\*\*中文:\*\* )(?P<zh>.*?)(?=\n\n^\*\*注释:\*\* )'
    r'(\n\n^\*\*注释:\*\* )(?P<note>.*?)(?=\n\n(?:<a id="[SE]\d{3}"></a>|## |\Z))'
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reader_dir", type=Path)
    parser.add_argument("overrides_json", type=Path)
    args = parser.parse_args()

    paper_path = args.reader_dir.resolve() / "paper.md"
    overrides_path = args.overrides_json.resolve()
    overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
    text = paper_path.read_text(encoding="utf-8")

    found = {match.group("id") for match in BLOCK_RE.finditer(text)}
    supplied = set(overrides)
    if found != supplied:
        missing = sorted(found - supplied)
        extra = sorted(supplied - found)
        raise SystemExit(f"override ID mismatch: missing={missing}, extra={extra}")

    def replace(match: re.Match[str]) -> str:
        block_id = match.group("id")
        item = overrides[block_id]
        zh = str(item.get("zh", "")).strip()
        note = str(item.get("note", "")).strip()
        if not zh or not note:
            raise SystemExit(f"empty reviewed content for {block_id}")
        return f"{match.group(1)}{zh}{match.group(4)}{note}"

    updated, count = BLOCK_RE.subn(replace, text)
    if count != len(overrides):
        raise SystemExit(f"updated {count} blocks, expected {len(overrides)}")
    paper_path.write_text(updated, encoding="utf-8")
    print(json.dumps({"paper": str(paper_path), "updated_blocks": count}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
