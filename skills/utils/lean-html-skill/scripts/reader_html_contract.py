#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared validation contract for generated PAPER reader HTML."""

from __future__ import annotations

import re
from typing import Any


def validate_generated_reader_html(html_text: str, concepts: list[dict[str, Any]], math_renderer: str) -> list[str]:
    issues: list[str] = []
    if math_renderer == "mathjax" and 'id="MathJax-script"' not in html_text:
        issues.append("MathJax script is missing")
    if "feedbackDock" in html_text:
        if "function closePanel()" not in html_text:
            issues.append("feedback UI closePanel handler is missing")
        save_match = re.search(r"function saveCurrent\([^)]*\) \{([\s\S]*?)\n  \}", html_text)
        if not save_match or "closePanel();" not in save_match.group(1):
            issues.append("Save mark does not close the annotate panel")
        if "feedbackExportFallback" not in html_text:
            issues.append("feedback copy fallback textarea is missing")
    if re.search(r'href="[^"]*<span\s+class="math-inline"', html_text, re.I):
        issues.append("link href contains math-inline markup")
    for href in re.findall(r'href="([^"]*assets/source_pages/[^"]+)"', html_text, re.I):
        if "<" in href or ">" in href:
            issues.append(f"source page link href contains HTML markup: {href[:160]}")
    if re.search(r'Algorithm\s+\d+\s+summary|算法\s*\d+\s*摘要', html_text, re.I):
        issues.append("Algorithm content is summarized; use a full algorithm-card")
    if re.search(r'Algorithm\s+\d+', html_text, re.I) and 'class="algorithm-card"' not in html_text:
        issues.append("Algorithm content exists but no algorithm-card is rendered")
    required_attrs = (
        "data-concept=",
        "data-status=",
        "data-source-anchor=",
        "data-concept-type=",
        "data-alias-zh=",
        "title=",
    )
    mark_count = len(re.findall(r'<mark\s+class="knowledge-gap\b', html_text))
    if concepts and mark_count == 0:
        issues.append("concept ledger exists but HTML contains no knowledge marks")
    for mark in re.findall(r'<mark\s+class="knowledge-gap\b[^>]*>', html_text):
        for attr in required_attrs:
            if attr not in mark:
                issues.append(f"knowledge mark missing {attr.rstrip('=')}: {mark[:160]}")
                break
    for note in re.findall(r'<article class="lang-panel reader-notes">([\s\S]*?)</article>', html_text, re.I):
        if re.search(r"<\s*/?\s*(h1|h2|section|script|style)\b", note, re.I):
            issues.append("reader-notes contains structural HTML pollution")
        if re.search(r"Source Page Index|source page index|assets/source_pages", note, re.I):
            issues.append("reader-notes contains source page/index pollution")
    return issues
