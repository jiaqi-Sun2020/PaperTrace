#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Adversarial audit for formal reader_interactive.html outputs."""

from __future__ import annotations

import json
import re
import sys
from html import unescape
from pathlib import Path


REQUIRED_MARK_ATTRS = (
    "data-concept",
    "data-status",
    "data-source-anchor",
    "data-concept-type",
    "data-alias-zh",
    "title",
)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected object JSON: {path}")
    return data


def fail(message: str, issues: list[str]) -> None:
    issues.append(message)


def audit(reader_dir: Path) -> tuple[list[str], dict[str, int | str]]:
    issues: list[str] = []
    html_path = reader_dir / "reader_interactive.html"
    wiki = reader_dir / "reader_wiki"
    html = html_path.read_text(encoding="utf-8")
    report = read_json(wiki / "structure_validation_report.json")
    concepts = read_json(wiki / "concept_ledger.json")
    algorithms = json.loads((wiki / "algorithm_ledger.json").read_text(encoding="utf-8"))
    formulas = json.loads((wiki / "formula_ledger.json").read_text(encoding="utf-8"))

    if report.get("status") != "pass":
        fail("structure_validation_report.json is not pass", issues)
    if not html.lstrip().startswith("<!doctype html>"):
        fail("HTML is not a standalone doctype document", issues)
    if 'id="MathJax-script"' not in html:
        fail("MathJax script is missing", issues)
    if re.search(r"Algorithm\s+\d+\s+summary|算法\s*\d+\s*摘要", html, re.I):
        fail("Algorithm summary remains in formal HTML", issues)
    if algorithms and 'class="algorithm-card"' not in html:
        fail("algorithm_ledger exists but no algorithm-card rendered", issues)
    if algorithms:
        if "Original Algorithm" not in html or "中文算法" not in html:
            fail("algorithm-card is missing original or Chinese algorithm column", issues)
        alg_line_count = len(re.findall(r'class="alg-line-no"', html))
        expected_min = sum(int(row.get("numbered_steps") or 0) for row in algorithms)
        if alg_line_count < expected_min:
            fail(f"algorithm line count too small: html={alg_line_count}, ledger={expected_min}", issues)

    if len(concepts.get("concepts") or []) < 30:
        fail("concept ledger has fewer than 30 concepts", issues)
    marks = re.findall(r'<mark\s+class="knowledge-gap\b[^>]*>', html)
    if not marks:
        fail("no knowledge-gap marks rendered", issues)
    for idx, mark in enumerate(marks[:200]):
        for attr in REQUIRED_MARK_ATTRS:
            if f"{attr}=" not in mark:
                fail(f"knowledge mark {idx} missing {attr}", issues)
                break

    for forbidden in ("<h1", "<h2", "<section", "<script", "<style", "Source Page Index", "assets/source_pages"):
        for note in re.findall(r'<article class="lang-panel reader-notes">([\s\S]*?)</article>', html, re.I):
            if forbidden.lower() in note.lower():
                fail(f"reader-notes pollution remains: {forbidden}", issues)
                break

    if "function closePanel()" not in html:
        fail("feedback closePanel function missing", issues)
    save_match = re.search(r"function saveCurrent\([^)]*\) \{([\s\S]*?)\n  \}", html)
    if not save_match or "closePanel();" not in save_match.group(1):
        fail("Save mark does not close panel", issues)
    for required in ("downloadFeedback", "copyFeedback", "readerFeedbackSeed"):
        if required not in html:
            fail(f"feedback export capability missing: {required}", issues)

    math_inline_values = [unescape(match) for match in re.findall(r'<span class="math-inline">([\s\S]*?)</span>', html)]
    bad_math_words = [value for value in math_inline_values if re.fullmatch(r"\$[A-Za-z]{3,}\$", value)]
    if bad_math_words:
        fail(f"plain English words wrapped as math-inline: {bad_math_words[:10]}", issues)
    if formulas and 'class="math-display"' not in html:
        fail("formula ledger exists but no math-display blocks rendered", issues)
    if re.search(r"QKT|e鈭|Rn脳|RT 脳|P v鈭|cid:", html):
        fail("raw PDF formula noise remains in HTML", issues)
    if re.search(r'href="[^"]*<span class="math-inline"', html):
        fail("a link href contains math-inline markup", issues)
    for href in re.findall(r'href="([^"]*assets/source_pages/[^"]+)"', html):
        if "<" in href or ">" in href:
            fail(f"source page href contains HTML markup: {href[:120]}", issues)
            continue
        target = reader_dir / href
        if not target.exists():
            fail(f"source page href target missing: {href}", issues)

    summary = {
        "validation": str(report.get("status")),
        "algorithms": len(algorithms),
        "algorithm_lines": len(re.findall(r'class="alg-line-no"', html)),
        "concepts": int(concepts.get("concept_count") or len(concepts.get("concepts") or [])),
        "marks": len(marks),
        "math_inline": len(math_inline_values),
        "math_display": len(re.findall(r'class="math-display"', html)),
    }
    return issues, summary


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: adversarial_html_audit.py <reader-dir>", file=sys.stderr)
        return 2
    reader_dir = Path(argv[1]).expanduser().resolve()
    issues, summary = audit(reader_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if issues:
        print("Adversarial audit failed:", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
        return 1
    print("Adversarial HTML audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
