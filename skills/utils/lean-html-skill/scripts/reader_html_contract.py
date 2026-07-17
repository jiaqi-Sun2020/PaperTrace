#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared validation contract for generated PaperTrace reader HTML."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


class _VisibleTextCollector(HTMLParser):
    """Collect user-visible text while excluding explicit math/code regions."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_stack: list[bool] = []
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            return
        values = {key.lower(): (value or "") for key, value in attrs}
        classes = set(values.get("class", "").split())
        inherited = bool(self._skip_stack and self._skip_stack[-1])
        own = tag.lower() in {"script", "style", "pre", "code", "textarea", "svg"} or bool(
            classes & {"math-inline", "math-display"}
        )
        self._skip_stack.append(inherited or own)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        return

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack:
            self._skip_stack.pop()

    def handle_data(self, data: str) -> None:
        if not (self._skip_stack and self._skip_stack[-1]):
            self.parts.append(data)


def _visible_raw_math_issues(html_text: str) -> list[str]:
    collector = _VisibleTextCollector()
    collector.feed(html_text)
    visible = " ".join(collector.parts)
    issues: list[str] = []
    command = re.search(r"\\(?:[A-Za-z]{2,}|[A-Za-z](?=[_^{]))", visible)
    if command:
        preview = re.sub(r"\s+", " ", visible[max(0, command.start() - 28):command.end() + 56]).strip()
        issues.append(f"visible prose contains raw TeX outside a math node: {preview[:120]}")
    script = re.search(
        r"(?<![\w\\])(?:[A-Za-z][A-Za-z0-9]*)(?:_\{[A-Za-z0-9,+\-]+\}|\^\{?[-+A-Za-z0-9]+\}?)+",
        visible,
    )
    if script:
        issues.append(f"visible prose contains uncompiled subscript/superscript syntax: {script.group(0)[:80]}")
    return issues


def _css_block(html_text: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", html_text, re.I)
    return match.group(1) if match else ""


def _all_css(html_text: str) -> str:
    return "\n".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", html_text, re.I))


def _css_rule(css_text: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", css_text, re.I)
    return match.group(1) if match else ""


def _parse_css_vars(block: str) -> dict[str, str]:
    return {
        name: value.lower()
        for name, value in re.findall(r"(--[a-z0-9-]+)\s*:\s*(#[0-9a-f]{3,6})\s*;", block, re.I)
    }


def _hex_to_rgb(value: str) -> tuple[float, float, float] | None:
    value = value.strip().lower()
    if not re.fullmatch(r"#[0-9a-f]{3}|#[0-9a-f]{6}", value):
        return None
    if len(value) == 4:
        value = "#" + "".join(ch * 2 for ch in value[1:])
    return tuple(int(value[idx : idx + 2], 16) / 255 for idx in (1, 3, 5))


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _contrast_ratio(foreground: str, background: str) -> float:
    fg = _hex_to_rgb(foreground)
    bg = _hex_to_rgb(background)
    if fg is None or bg is None:
        return 0.0
    lum_fg = _relative_luminance(fg)
    lum_bg = _relative_luminance(bg)
    lighter = max(lum_fg, lum_bg)
    darker = min(lum_fg, lum_bg)
    return (lighter + 0.05) / (darker + 0.05)


def _strip_print_css(css_text: str) -> str:
    output: list[str] = []
    idx = 0
    while idx < len(css_text):
        match = re.search(r"@media\s+print\s*\{", css_text[idx:], re.I)
        if not match:
            output.append(css_text[idx:])
            break
        start = idx + match.start()
        open_brace = idx + match.end() - 1
        output.append(css_text[idx:start])
        depth = 0
        pos = open_brace
        while pos < len(css_text):
            if css_text[pos] == "{":
                depth += 1
            elif css_text[pos] == "}":
                depth -= 1
                if depth == 0:
                    pos += 1
                    break
            pos += 1
        idx = pos
    return "".join(output)


def _validate_dark_theme_readability(html_text: str) -> list[str]:
    issues: list[str] = []
    css_text = _all_css(html_text)
    dark_block = _css_rule(css_text, ':root[data-theme="dark"]')
    if not dark_block:
        return ['dark theme CSS block :root[data-theme="dark"] is missing']
    vars_by_name = _parse_css_vars(dark_block)
    required_vars = (
        "--reader-bg",
        "--reader-card-bg",
        "--reader-text",
        "--reader-muted",
        "--reader-border",
        "--reader-math-bg",
    )
    for var_name in required_vars:
        if var_name not in vars_by_name:
            issues.append(f"dark theme variable missing: {var_name}")
    contrast_pairs = {
        "dark body text": ("--reader-text", "--reader-bg", 4.5),
        "dark card text": ("--reader-text", "--reader-card-bg", 4.5),
        "dark panel text": ("--reader-text", "--reader-panel-bg", 4.5),
        "dark math text": ("--reader-text", "--reader-math-bg", 4.5),
        "dark muted card text": ("--reader-muted", "--reader-card-bg", 4.5),
        "dark link text": ("--reader-link", "--reader-bg", 4.5),
        "dark highlight text": ("--reader-highlight-text", "--reader-highlight-bg", 4.5),
        "dark primary button text": ("--reader-primary-text", "--reader-accent", 4.5),
    }
    for label, (fg_var, bg_var, minimum) in contrast_pairs.items():
        if fg_var not in vars_by_name or bg_var not in vars_by_name:
            continue
        fg = vars_by_name[fg_var]
        bg = vars_by_name[bg_var]
        if fg == bg:
            issues.append(f"{label}: {fg_var} and {bg_var} are identical ({fg})")
            continue
        ratio = _contrast_ratio(fg, bg)
        if ratio < minimum:
            issues.append(f"{label}: contrast {ratio:.2f}:1 is below {minimum}:1 ({fg_var}={fg}, {bg_var}={bg})")

    css_without_print = _strip_print_css(css_text)
    dangerous_backgrounds = re.findall(
        r"([^{@]+)\{[^}]*background(?:-color)?\s*:\s*(?:white|#fff(?:fff)?)\b[^}]*\}",
        css_without_print,
        re.I,
    )
    dangerous_white_text = re.findall(
        r"([^{@]+)\{[^}]*color\s*:\s*(?:white|#fff(?:fff)?)\b[^}]*\}",
        css_without_print,
        re.I,
    )
    if dangerous_backgrounds:
        selectors = ", ".join(selector.strip().splitlines()[-1] for selector in dangerous_backgrounds[:5])
        issues.append(f"hardcoded white background remains outside print CSS: {selectors}")
    if dangerous_white_text:
        selectors = ", ".join(selector.strip().splitlines()[-1] for selector in dangerous_white_text[:5])
        issues.append(f"hardcoded white text remains outside print CSS: {selectors}")
    return issues


def validate_generated_reader_html(html_text: str, concepts: list[dict[str, Any]], math_renderer: str) -> list[str]:
    issues: list[str] = []
    if math_renderer == "mathjax" and 'id="MathJax-script"' not in html_text:
        issues.append("MathJax script is missing")
    if math_renderer == "mathjax" and "data-math-status" not in html_text:
        issues.append("MathJax runtime status contract is missing")
    issues.extend(_visible_raw_math_issues(html_text))
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
    algorithm_cards = re.findall(r'<section class="algorithm-card"[\s\S]*?</section>', html_text, re.I)
    for index, card in enumerate(algorithm_cards, start=1):
        if 'data-algorithm-contract="latex-compiled-algorithm-v1"' not in card:
            issues.append(f"algorithm-card {index} lacks the compiled-LaTeX contract marker")
        if not re.search(
            r'<img\b[^>]+class="algorithm-render"[^>]+src="(?:[^"]+\.svg|data:image/svg\+xml[^"]*)"',
            card,
            re.I,
        ):
            issues.append(f"algorithm-card {index} lacks a compiled SVG algorithm")
        if 'class="lang-panel translation"' in card or re.search(r'\*\*中文算法', card):
            issues.append(f"algorithm-card {index} contains a translated algorithm body")
    if 'class="alg-line-no"' in html_text:
        issues.append("legacy line-list algorithm rendering remains; use compiled LaTeX")
    for index, body in enumerate(
        re.findall(r'<div class="math-display">([\s\S]*?)</div>', html_text, re.I),
        start=1,
    ):
        math = re.sub(r"<[^>]+>", "", body)
        if re.search(r'\\q(?:uad|quad)|\\begin\{(?:align\*?|aligned|gather\*?|gathered)\}', math):
            issues.append(f"math-display {index} contains multiple logical formulas")
    if 'id="readerThemeSelect"' not in html_text:
        issues.append("reader theme control is missing")
    if "localStorage" not in html_text or "paper.reader.theme" not in html_text:
        issues.append("reader theme localStorage persistence is missing")
    if "data-theme" not in html_text:
        issues.append("reader theme data-theme switching is missing")
    issues.extend(_validate_dark_theme_readability(html_text))
    figure_img_css = _css_block(html_text, ".figure-card img")
    figure_card_css = _css_block(html_text, ".figure-card")
    if re.search(r"object-fit\s*:\s*cover", figure_img_css, re.I):
        issues.append("figure-card images use object-fit: cover")
    if re.search(r"height\s*:\s*(?!\s*auto\b)[^;]+", figure_img_css, re.I):
        issues.append("figure-card images have a fixed height")
    if re.search(r"overflow\s*:\s*hidden", figure_card_css, re.I):
        issues.append("figure-card clips image content with overflow hidden")
    for figure in re.findall(r'<figure\s+class="figure-card"[\s\S]*?</figure>', html_text, re.I):
        if re.search(r'<img\b[^>]+src="[^"]*assets/source_pages/', figure, re.I):
            issues.append("figure-card uses a full source-page image as figure content")
            break
    required_attrs = (
        "data-concept=",
        "data-concept-id=",
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
    for token in ('id="toggleOriginal"', 'aria-controls="readerDocument"', "original-collapsed"):
        if token not in html_text:
            issues.append(f"reader Original-collapse contract is missing: {token}")
    if not re.search(r'id="toggleOriginal"[^>]*aria-pressed="false"[^>]*aria-expanded="true"', html_text):
        issues.append("reader Original-collapse control lacks initial ARIA state")
    for token in (
        'id="toggleContents"',
        'id="contentsPaneToggle"',
        'id="contentsPaneResizer"',
        "toc-collapsed",
        "document.body.classList.add('feedback-open')",
        "document.body.classList.remove('feedback-open')",
    ):
        if token not in html_text:
            issues.append(f"reader adaptive-pane contract is missing: {token}")
    source_pages_match = re.search(
        r'<script id="readerSourcePages" type="application/json">([\s\S]*?)</script>',
        html_text,
        re.I,
    )
    if source_pages_match and source_pages_match.group(1).strip() not in ("", "[]"):
        for token in (
            'id="sourcePageViewer"',
            'id="toggleSourcePages"',
            'aria-controls="sourcePageViewer"',
            'id="sourcePaneToggle"',
            'id="sourcePaneResizer"',
            'role="separator"',
        ):
            if token not in html_text:
                issues.append(f"reader source-page viewer contract is missing: {token}")
        if not re.search(r'id="toggleSourcePages"[^>]*aria-pressed="false"[^>]*aria-expanded="true"', html_text):
            issues.append("reader source-page collapse control lacks initial ARIA state")
        if not re.search(
            r'<div class="layout has-source-pages">\s*'
            r'<aside class="reader-sidebar"[^>]*>[\s\S]*?id="sourcePageViewer"[\s\S]*?</aside>\s*'
            r'<main>[\s\S]*?</main>\s*<nav class="toc"',
            html_text,
            re.I,
        ):
            issues.append("reader layout must place source pages left, article center, and Contents right")
    return issues
