#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render an authored feedback research deep-dive Markdown file to standalone HTML."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path
from typing import Any


def clean(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def inline_md(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    return escaped


def heading_id(text: str, index: int) -> str:
    ascii_slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return f"h-{index}-{ascii_slug[:48]}" if ascii_slug else f"h-{index}"


def mathjax_src(value: str) -> str:
    src = clean(value)
    if not src or src.lower() == "none":
        return ""
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", src):
        return src
    path = Path(src)
    try:
        if path.exists():
            return path.resolve().as_uri()
    except OSError:
        return src
    return src


def render_markdown(markdown: str) -> tuple[str, str]:
    body: list[str] = []
    toc: list[tuple[int, str, str]] = []
    list_mode: str | None = None
    in_code = False
    code_lines: list[str] = []
    heading_index = 0

    def close_list() -> None:
        nonlocal list_mode
        if list_mode:
            body.append(f"</{list_mode}>")
            list_mode = None

    def close_code() -> None:
        nonlocal in_code, code_lines
        if in_code:
            body.append(f"<pre><code>{html.escape(chr(10).join(code_lines))}</code></pre>")
            in_code = False
            code_lines = []

    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                close_code()
            else:
                close_list()
                in_code = True
                code_lines = []
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line:
            close_list()
            body.append("")
            continue
        heading_match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if heading_match:
            close_list()
            level = len(heading_match.group(1))
            text = heading_match.group(2)
            heading_index += 1
            hid = heading_id(text, heading_index)
            toc.append((level, hid, text))
            body.append(f'<h{level} id="{hid}">{inline_md(text)}</h{level}>')
            continue
        if line.startswith("- "):
            if list_mode != "ul":
                close_list()
                body.append("<ul>")
                list_mode = "ul"
            body.append(f"<li>{inline_md(line[2:])}</li>")
            continue
        ordered = re.match(r"^\d+\.\s+(.+)$", line)
        if ordered:
            if list_mode != "ol":
                close_list()
                body.append("<ol>")
                list_mode = "ol"
            body.append(f"<li>{inline_md(ordered.group(1))}</li>")
            continue
        close_list()
        if line.startswith(">"):
            body.append(f"<blockquote>{inline_md(line.lstrip('> '))}</blockquote>")
        else:
            body.append(f"<p>{inline_md(line)}</p>")
    close_list()
    close_code()
    toc_html = "\n".join(
        f'<a class="toc-l{level}" href="#{html.escape(hid)}">{inline_md(text)}</a>'
        for level, hid, text in toc
        if level <= 3
    )
    return "\n".join(body), toc_html


def build_html(markdown: str, title: str, mathjax_url: str) -> str:
    body, toc = render_markdown(markdown)
    src = mathjax_src(mathjax_url)
    mathjax = ""
    if src:
        mathjax = f"""
<script>
window.MathJax = {{
  tex: {{ inlineMath: [['$', '$'], ['\\\\(', '\\\\)']], displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']] }},
  options: {{ skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'] }}
}};
</script>
<script async src="{html.escape(src)}"></script>
"""
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: light; --bg:#f6f7fb; --paper:#fff; --ink:#172033; --muted:#667085; --line:#d8deea; --accent:#2454d6; --soft:#eef4ff; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font-family:"Segoe UI","Microsoft YaHei",Arial,sans-serif; line-height:1.68; }}
header {{ background:#111827; color:white; padding:32px 22px; }}
header .inner, .layout {{ max-width:1240px; margin:0 auto; }}
h1 {{ margin:0; font-size:32px; line-height:1.2; letter-spacing:0; }}
.subtitle {{ margin:10px 0 0; color:#cbd5e1; }}
.layout {{ display:grid; grid-template-columns:260px minmax(0,1fr); gap:22px; padding:24px 18px 48px; }}
nav {{ position:sticky; top:16px; align-self:start; max-height:calc(100vh - 32px); overflow:auto; border:1px solid var(--line); border-radius:8px; background:#fff; padding:14px; }}
nav h2 {{ margin:0 0 8px; font-size:14px; color:var(--muted); }}
nav a {{ display:block; padding:5px 7px; border-left:2px solid transparent; color:#334155; text-decoration:none; font-size:13px; }}
nav a:hover {{ border-color:var(--accent); background:var(--soft); color:var(--accent); }}
.toc-l1 {{ font-weight:700; }}
.toc-l2 {{ margin-left:8px; }}
.toc-l3 {{ margin-left:18px; color:var(--muted); }}
main {{ min-width:0; border:1px solid var(--line); border-radius:8px; background:var(--paper); padding:30px; }}
h1,h2,h3,h4 {{ line-height:1.28; letter-spacing:0; }}
h2 {{ margin:34px 0 12px; padding-top:14px; border-top:1px solid var(--line); font-size:24px; }}
h3 {{ margin:24px 0 10px; font-size:20px; }}
h4 {{ margin:18px 0 8px; font-size:17px; color:#0f172a; }}
p {{ margin:10px 0; }}
ul,ol {{ padding-left:24px; margin:8px 0 16px; }}
li {{ margin:5px 0; }}
blockquote {{ border-left:4px solid var(--accent); margin:12px 0; padding:8px 12px; background:#f8faff; color:#344054; }}
pre {{ overflow:auto; background:#111827; color:#e5e7eb; border-radius:8px; padding:14px; }}
code {{ padding:1px 5px; border-radius:4px; background:#eef2f7; font-family:Consolas,"Cascadia Mono",monospace; font-size:.92em; }}
pre code {{ padding:0; background:transparent; }}
table {{ width:100%; border-collapse:collapse; margin:14px 0; }}
th,td {{ border-bottom:1px solid #e5eaf2; padding:10px; text-align:left; vertical-align:top; letter-spacing:0; }}
th {{ background:#f8fafc; }}
@page {{ size:A4; margin:18mm 16mm; }}
@media (max-width:900px) {{ .layout {{ display:block; padding:12px; }} nav {{ position:static; max-height:none; margin-bottom:12px; }} main {{ padding:20px; }} h1 {{ font-size:24px; }} }}
@media print {{ body {{ background:#fff; }} header {{ background:#fff; color:#111827; border-bottom:1px solid var(--line); }} .subtitle {{ color:var(--muted); }} .layout {{ display:block; padding:0; }} nav {{ display:none; }} main {{ border:0; padding:0; }} }}
</style>
{mathjax}
</head>
<body>
<header><div class="inner"><h1>{html.escape(title)}</h1><p class="subtitle">Research deep-dive report generated from reader feedback context.</p></div></header>
<div class="layout"><nav><h2>目录</h2>{toc}</nav><main>{body}</main></div>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Authored research deep-dive Markdown path.")
    parser.add_argument("--output", help="Output HTML path. Defaults to input path with .html suffix.")
    parser.add_argument("--title", help="HTML title. Defaults to the first Markdown heading or file stem.")
    parser.add_argument(
        "--mathjax-url",
        default="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js",
        help="MathJax script URL/path. Use 'none' to disable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    markdown = input_path.read_text(encoding="utf-8-sig")
    first_heading = next((line.lstrip("# ").strip() for line in markdown.splitlines() if line.startswith("# ")), "")
    title = args.title or first_heading or input_path.stem.replace("_", " ")
    output_path = Path(args.output).resolve() if args.output else input_path.with_suffix(".html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html(markdown, title, args.mathjax_url), encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
