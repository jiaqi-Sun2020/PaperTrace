#!/usr/bin/env python3
"""Re-anchor a reviewed concept-candidate vocabulary to a rebuilt reader.

Names, aliases, types, and explanations come from the reviewed seed.  Only the
source anchor/evidence span are recomputed, and every emitted span is an exact
substring of the current reader's Original layer.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


ANCHOR_RE = re.compile(r'(?m)^<a id="(S\d+)"></a>\s*$')
ORIGINAL_RE = re.compile(r'(?ms)^\*\*Original:\*\*\s*(.*?)(?=\n\n^\*\*中文:\*\*)')


def blocks(markdown: str) -> list[tuple[str, str]]:
    matches = list(ANCHOR_RE.finditer(markdown))
    rows = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        body = markdown[match.end():end]
        original = ORIGINAL_RE.search(body)
        if original:
            rows.append((match.group(1), original.group(1).strip()))
    return rows


def variants(item: dict) -> list[str]:
    values = [
        str(item.get("evidence_span") or ""),
        str(item.get("canonical_name") or ""),
        *[str(value) for value in item.get("aliases_en") or []],
    ]
    cleaned = []
    for value in values:
        value = value.strip().strip("$")
        value = re.sub(r"\\(?:langle|rangle|sum|sigma|mathrm|operatorname)", " ", value)
        value = re.sub(r"[{}_^\\$]+", " ", value)
        value = re.sub(r"\s+", " ", value).strip()
        if len(value) >= 2 and value not in cleaned:
            cleaned.append(value)
    return sorted(cleaned, key=len, reverse=True)


def exact_match(item: dict, source_blocks: list[tuple[str, str]]) -> tuple[str, str] | None:
    for candidate in variants(item):
        direct = re.compile(re.escape(candidate), re.I)
        for anchor, original in source_blocks:
            match = direct.search(original)
            if match:
                return anchor, match.group(0)
        tokens = re.findall(r"[A-Za-z0-9]+", candidate)
        if len(tokens) >= 2:
            # PDF prose commonly inserts conjunctions/modifiers (for example,
            # "positive *and* trace non-increasing" or "factorial *number of*
            # terminal paths").  Permit at most three intervening words while
            # still returning the exact source substring as evidence.
            gap = r"(?:[\s\W_]+(?:[A-Za-z0-9]+[\s\W_]+){0,3})"
            flexible = re.compile(r"\b" + gap.join(map(re.escape, tokens)) + r"\b", re.I)
            for anchor, original in source_blocks:
                match = flexible.search(original)
                if match:
                    return anchor, match.group(0)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reader_dir", type=Path)
    parser.add_argument("reviewed_seed", type=Path)
    args = parser.parse_args()
    reader_dir = args.reader_dir.resolve()
    seed_payload = json.loads(args.reviewed_seed.resolve().read_text(encoding="utf-8"))
    seed_rows = seed_payload.get("concepts", []) if isinstance(seed_payload, dict) else seed_payload
    normalized_seed = []
    for item in seed_rows:
        if isinstance(item, dict):
            normalized_seed.append(item)
            continue
        if isinstance(item, list) and len(item) == 5:
            canonical_name, alias_zh, source_anchor, concept_type, explanation_note = item
            normalized_seed.append({
                "canonical_name": canonical_name,
                "aliases_en": [],
                "aliases_zh": [alias_zh] if alias_zh else [],
                "source_anchor": source_anchor,
                "concept_type": concept_type,
                "explanation_note": explanation_note,
            })
    source_blocks = blocks((reader_dir / "paper.md").read_text(encoding="utf-8"))
    emitted = []
    skipped = []
    for item in normalized_seed:
        match = exact_match(item, source_blocks)
        if not match:
            skipped.append(item.get("canonical_name"))
            continue
        anchor, evidence = match
        emitted.append({
            "canonical_name": item.get("canonical_name"),
            "aliases_en": item.get("aliases_en") or [],
            "aliases_zh": item.get("aliases_zh") or [],
            "concept_type": item.get("concept_type"),
            "source_anchor": anchor,
            "evidence_span": evidence,
            "explanation_note": item.get("explanation_note"),
        })
    output = reader_dir / "reader_wiki" / "concept_candidates.json"
    payload = {"version": 1, "concepts": emitted}
    tmp = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(output)
    print(json.dumps({"emitted": len(emitted), "skipped": skipped, "output": str(output)}, ensure_ascii=False))
    return 0 if len(emitted) >= 30 else 1


if __name__ == "__main__":
    raise SystemExit(main())
