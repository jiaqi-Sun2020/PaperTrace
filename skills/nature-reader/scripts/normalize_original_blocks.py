#!/usr/bin/env python3
"""Mechanically normalize Original blocks before semantic completion.

The raw source map is never changed.  This helper may repair layout, but it
never copies LaTeX from the Chinese column and never runs after a completion
ledger exists.  Original-side LaTeX is a direct semantic completion task, not
a late mechanical rewrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


ANCHOR_RE = re.compile(r'(?m)^<a id="(S\d+)"></a>\s*$')
MATH_RE = re.compile(r'(\\\[[\s\S]*?\\\]|\\\([\s\S]*?\\\)|\$\$[\s\S]*?\$\$|(?<!\\)\$(?!\s)(?:\\.|[^$]){1,800}?(?<!\\)\$)')
EQUATION_LABEL_RE = re.compile(r"\(([A-M]?\d+)\)\s*$")
ORIGINAL_RE = re.compile(r'(?ms)(^\*\*Original:\*\*\s*)(.*?)(?=\n\n^\*\*中文:\*\*)')
ZH_RE = re.compile(r'(?ms)^\*\*中文:\*\*\s*(.*?)(?=\n\n^\*\*(?:注释|Notes):\*\*)')


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def formulaish_source_line(line: str) -> bool:
    """Identify extraction lines that belong to a displayed equation run."""
    value = re.sub(r"\s+", " ", line).strip()
    if not value:
        return False
    if EQUATION_LABEL_RE.search(value):
        return True
    long_words = re.findall(r"[A-Za-z]{3,}", value)
    if len(long_words) >= 3:
        return False
    if re.search(r"[=<>≤≥±†⟨⟩∑∏√σρψαβγΛ]|\.\s*\.\s*\.", value):
        return True
    if len(value) <= 12 and not long_words:
        return True
    symbols = sum(not char.isalnum() and not char.isspace() for char in value)
    return symbols / max(1, len(value)) >= 0.28 and len(long_words) <= 2


def add_equation_tag(formula: str, label: str) -> str:
    if formula.startswith("$$") and formula.endswith("$$"):
        return f"$${formula[2:-2].strip()}\\tag{{{label}}}$$"
    if formula.startswith("\\[") and formula.endswith("\\]"):
        return f"\\[{formula[2:-2].strip()}\\tag{{{label}}}\\]"
    return formula


LATEX_TO_PLAIN = {
    r"\kappa": "κ",
    r"\sigma": "σ",
    r"\alpha": "α",
    r"\beta": "β",
    r"\gamma": "γ",
    r"\rho": "ρ",
    r"\psi": "ψ",
    r"\phi": "φ",
    r"\Lambda": "Λ",
    r"\langle": "⟨",
    r"\rangle": "⟩",
    r"\dagger": "†",
    r"\ne": "≠",
    r"\le": "≤",
    r"\ge": "≥",
    r"\sum": "∑",
    r"\prod": "∏",
}


def inline_plain_pattern(formula: str) -> re.Pattern[str] | None:
    body = formula.strip().strip("$")
    has_notation_structure = "\\" in body or "_" in body or "^" in body
    for latex, plain in LATEX_TO_PLAIN.items():
        body = body.replace(latex, plain)
    body = re.sub(r"\\(?:left|right|,|!|;|:)", "", body)
    body = re.sub(r"\\(?:mathrm|text|operatorname)\{([^{}]+)\}", r"\1", body)
    body = re.sub(r"[{}_^]", "", body)
    body = re.sub(r"\s+", "", body)
    if len(body) < 3 and not has_notation_structure:
        return None
    pieces: list[str] = []
    for char in body:
        if char == "≠":
            pieces.append(r"(?:≠|̸\s*=)")
        elif char == "φ":
            pieces.append(r"[φϕ]")
        else:
            pieces.append(re.escape(char))
    return re.compile(r"\s*".join(pieces))


def replace_inline_formula_occurrences(raw: str, formulas: list[str]) -> tuple[str, list[str], int]:
    value = raw
    remaining: list[str] = []
    replaced = 0
    for formula in formulas:
        pattern = inline_plain_pattern(formula)
        if pattern is None:
            remaining.append(formula)
            continue
        value, count = pattern.subn(lambda _match, latex=formula: latex, value, count=1)
        if count:
            replaced += 1
        else:
            remaining.append(formula)
    return value, remaining, replaced


def replace_extracted_formula_runs(raw: str, formulas: list[str]) -> tuple[str, int]:
    """Replace labelled PDF equation-line runs with reviewed LaTeX in place."""
    if not formulas:
        return raw, 0
    lines = raw.splitlines()
    groups: list[tuple[int, int, str]] = []
    occupied: set[int] = set()
    for end, line in enumerate(lines):
        label_match = EQUATION_LABEL_RE.search(line.strip())
        if not label_match:
            continue
        start = end
        while start > 0 and formulaish_source_line(lines[start - 1]):
            start -= 1
        if start == end and not formulaish_source_line(line):
            continue
        if any(index in occupied for index in range(start, end + 1)):
            continue
        occupied.update(range(start, end + 1))
        groups.append((start, end, label_match.group(1)))
    if not groups:
        return raw, 0
    replacements = {
        start: (end, add_equation_tag(formulas[index], label))
        for index, (start, end, label) in enumerate(groups[: len(formulas)])
    }
    rebuilt: list[str] = []
    index = 0
    while index < len(lines):
        if index in replacements:
            end, formula = replacements[index]
            rebuilt.extend(["", formula, ""])
            index = end + 1
        else:
            rebuilt.append(lines[index])
            index += 1
    return "\n".join(rebuilt), len(replacements)


def normalize_layout(raw: str, page: int) -> tuple[str, list[str]]:
    operations = ["unicode-control-removal", "pdf-line-unwrap", "whitespace-collapse"]
    text = raw.replace("[U+0001]", " ")
    text = "".join(char if ord(char) >= 32 or char in "\n\t" else " " for char in text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if lines and lines[0] == str(page):
        lines.pop(0)
        operations.append("orphan-page-number-removal")
    rebuilt: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.endswith("-") and index + 1 < len(lines) and re.match(r"^[a-z]", lines[index + 1]):
            rebuilt.append(line[:-1] + lines[index + 1])
            index += 2
            operations.append("line-break-dehyphenation")
            continue
        rebuilt.append(line)
        index += 1
    text = " ".join(rebuilt)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(
        r"\s*(\$\$[\s\S]*?\$\$|\\\[[\s\S]*?\\\])\s*",
        lambda match: f"\n\n{match.group(1).strip()}\n\n",
        text,
    )
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    # Restore semantic visual boundaries without changing words or order.
    text = re.sub(r"\s+(?=((?:I|II|III|IV|V|VI|VII)\.\s+[A-Z]))", "\n\n", text)
    text = re.sub(r"\s+(?=(?:Appendix\s+[A-M]:|SUPPLEMENTARY MATERIAL))", "\n\n", text)
    text = re.sub(r"\s+(?=(?:FIG\.|TABLE)\s+[IVX0-9]+:)", "\n\n", text)
    operations.extend(["display-math-boundary-repair", "section-caption-boundary-repair"])
    return text, sorted(set(operations))


def split_segments(markdown: str) -> list[tuple[str, str, int, int]]:
    matches = list(ANCHOR_RE.finditer(markdown))
    result = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        result.append((match.group(1), markdown[match.end():end], match.end(), end))
    return result


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reader_dir", type=Path)
    args = parser.parse_args()
    reader_dir = args.reader_dir.resolve()
    paper_path = reader_dir / "paper.md"
    completion_path = reader_dir / "reader_wiki" / "completion_ledger.json"
    if completion_path.exists():
        raise RuntimeError(
            "refusing to mutate paper.md after completion_ledger.json exists; "
            "normalize Original layout before semantic completion and rerun the full gate"
        )
    source_map = json.loads((reader_dir / "source_map.json").read_text(encoding="utf-8"))
    rows = {str(row.get("id") or ""): row for row in source_map.get("blocks", []) if isinstance(row, dict)}
    markdown = paper_path.read_text(encoding="utf-8")
    replacements: list[tuple[int, int, str]] = []
    ledger_rows = []

    for anchor, segment, start, end in split_segments(markdown):
        row = rows.get(anchor)
        if not row:
            continue
        original_match = ORIGINAL_RE.search(segment)
        if not original_match:
            continue
        raw = str(row.get("original_text") or row.get("original") or row.get("text") or "")
        page = int(row.get("page") or 0)
        source_type = str(row.get("type") or "").lower()
        authored_original = original_match.group(2)
        original_formulas = [match.group(0).strip() for match in MATH_RE.finditer(authored_original)]
        reader_source = authored_original if authored_original.strip() else raw
        normalized, operations = normalize_layout(reader_source, page)
        if original_formulas:
            operations.append("preserved-existing-original-side-latex")
        new_segment = segment[:original_match.start(2)] + normalized + segment[original_match.end(2):]
        replacements.append((start, end, new_segment))
        ledger_rows.append({
            "block_id": anchor,
            "source_page": page,
            "source_type": source_type,
            "raw_sha256": sha256_text(raw),
            "normalized_original_sha256": sha256_text(normalized),
            "operations": sorted(set(operations)),
            "original_formula_count": len(original_formulas),
        })

    for start, end, replacement in reversed(replacements):
        markdown = markdown[:start] + replacement + markdown[end:]
    atomic_write(paper_path, markdown)
    ledger = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_map_path": "source_map.json",
        "paper_path": "paper.md",
        "blocks": ledger_rows,
    }
    ledger_path = reader_dir / "reader_wiki" / "original_normalization_ledger.json"
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2))
    print(json.dumps({"normalized_blocks": len(ledger_rows), "ledger": str(ledger_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
