#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared HTML post-processing utilities for PaperTrace skills."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_STATUSES = {"mastered", "known", "learning", "unknown", "unrated"}
DEFAULT_READER_STATUS = "unrated"
DEFAULT_NEWS_STATUS = "unrated"
MARKER_START = "<!-- lean-html-skill:feedback2:start -->"
MARKER_END = "<!-- lean-html-skill:feedback2:end -->"
DESIGN_MARKER_START = "<!-- lean-html-skill:design-system:start -->"
DESIGN_MARKER_END = "<!-- lean-html-skill:design-system:end -->"


def clean_text(value: Any, limit: int = 4000) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def js_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def is_news_feedback(feedback: dict[str, Any], feedback_path: Path) -> bool:
    source_kind = clean_text(feedback.get("source_kind"), 120)
    return (
        source_kind == "news_briefing"
        or bool(feedback.get("news_feedback_version"))
        or bool(clean_text(feedback.get("briefing_title"), 500))
        or feedback_path.name.startswith("news_feedback")
    )


def valid_status(value: Any, default: str = DEFAULT_READER_STATUS) -> str:
    status = clean_text(value, 80).lower()
    return status if status in VALID_STATUSES else default


def item_meta(index: int, item: dict[str, Any], default_status: str = DEFAULT_READER_STATUS) -> dict[str, Any]:
    concept = clean_text(item.get("concept") or item.get("selected_text") or f"feedback item {index}", 600)
    block_id = clean_text(item.get("block_id") or item.get("bilingual_block_id") or f"item-{index:02d}", 180)
    source_excerpt = clean_text(item.get("source_excerpt") or item.get("original_context") or item.get("note"), 2200)
    return {
        "index": index,
        "anchor": f"item-{index:02d}",
        "concept": concept,
        "status": valid_status(item.get("status"), default_status),
        "category": clean_text(item.get("category") or item.get("confusion_type"), 200),
        "source_title": clean_text(item.get("source_title"), 500),
        "source_url": clean_text(item.get("source_url"), 1000),
        "source_excerpt": source_excerpt,
        "selected_text": clean_text(item.get("selected_text") or concept, 1600),
        "selected_language": clean_text(item.get("selected_language") or "report_item", 80),
        "original_context": clean_text(item.get("original_context") or source_excerpt, 2200),
        "translation_context": clean_text(item.get("translation_context"), 2200),
        "block_id": block_id,
        "annotation_kind": clean_text(item.get("annotation_kind") or "report_item", 120),
        "confusion_type": clean_text(item.get("confusion_type"), 120),
        "explanation_style": clean_text(item.get("explanation_style"), 120),
        "note": clean_text(item.get("note"), 1200),
        "user_question": clean_text(item.get("user_question") or item.get("question"), 1600),
    }


def payload_from_feedback(feedback: dict[str, Any], feedback_path: Path, source: str) -> dict[str, Any]:
    items = [row for row in feedback.get("items", []) or [] if isinstance(row, dict)]
    news = is_news_feedback(feedback, feedback_path)
    default_status = DEFAULT_NEWS_STATUS if news else DEFAULT_READER_STATUS
    title = clean_text(
        feedback.get("briefing_title")
        or feedback.get("paper_title")
        or feedback.get("title")
        or feedback_path.parent.name,
        500,
    )
    return {
        "kind": "news" if news else "reader",
        "export_filename": "news_feedback2.json" if news else "reader_feedback2.json",
        "source_kind": "news_briefing" if news else clean_text(feedback.get("source_kind") or "reader_feedback", 120),
        "title": title,
        "paper_title": clean_text(feedback.get("paper_title") or title, 500),
        "briefing_title": clean_text(feedback.get("briefing_title") or title, 500),
        "date_range": clean_text(feedback.get("date_range"), 200),
        "reader_path": clean_text(feedback.get("reader_path") or str(feedback_path.parent), 1000),
        "briefing_path": clean_text(feedback.get("briefing_path") or feedback.get("reader_path") or str(feedback_path.parent), 1000),
        "feedback_path": str(feedback_path),
        "generated_from": source,
        "default_status": default_status,
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "items": [item_meta(index, item, default_status) for index, item in enumerate(items, start=1)],
    }


def cosmic_design_css() -> str:
    return r"""
<style id="lean-html-cosmic-design-system">
:root{
  --space-bg:#050816;
  --nebula:#081B33;
  --panel:#0B1228;
  --glass:rgba(15,25,50,.65);
  --quantum:#00F5FF;
  --stellar:#8B5CFF;
  --galaxy:#FF4FD8;
  --solar:#FFD166;
  --cosmic-ink:#EAF6FF;
  --cosmic-muted:#9DB4D3;
  --cosmic-line:rgba(0,245,255,.24);
  --cosmic-shadow:0 0 30px rgba(0,245,255,.12);
  --cosmic-font-display:"Orbitron","Space Grotesk","Exo 2","Segoe UI",sans-serif;
  --cosmic-font-body:"Inter","IBM Plex Sans","Roboto","Segoe UI","Microsoft YaHei",Arial,sans-serif;
  --bg:var(--space-bg);
  --panel:rgba(10,20,40,.72);
  --ink:var(--cosmic-ink);
  --muted:var(--cosmic-muted);
  --line:rgba(0,245,255,.24);
  --accent:var(--quantum);
  --accent-2:var(--stellar);
  --warn:var(--solar);
  --bad:#FF6B8A;
  --good:#7CFFB2;
  --shadow:0 18px 44px rgba(0,0,0,.34),0 0 30px rgba(0,245,255,.12);
}
html[data-lean-design-system="cosmic"]{
  color-scheme:dark;
}
html[data-lean-design-system="cosmic"] body{
  min-height:100vh;
  color:var(--cosmic-ink);
  background:
    radial-gradient(circle at 12% 8%,rgba(139,92,255,.25),transparent 32rem),
    radial-gradient(circle at 88% 18%,rgba(0,245,255,.18),transparent 28rem),
    radial-gradient(circle at 50% 115%,rgba(255,79,216,.13),transparent 34rem),
    linear-gradient(135deg,var(--space-bg),#071126 52%,#02040d);
  font-family:var(--cosmic-font-body);
}
html[data-lean-design-system="cosmic"] header{
  background:linear-gradient(180deg,rgba(5,8,22,.94),rgba(8,27,51,.76));
  border-color:rgba(0,245,255,.18);
  box-shadow:0 10px 32px rgba(0,0,0,.28);
}
html[data-lean-design-system="cosmic"] :where(p,li,td,dd){
  color:#D6E7FF;
}
html[data-lean-design-system="cosmic"] :where(strong,b){
  color:#F5FBFF;
}
html[data-lean-design-system="cosmic"] body::before{
  content:"";
  position:fixed;
  inset:0;
  pointer-events:none;
  z-index:-1;
  background:
    linear-gradient(rgba(0,245,255,.035) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,245,255,.035) 1px,transparent 1px),
    radial-gradient(circle,rgba(255,255,255,.18) 1px,transparent 1.6px);
  background-size:64px 64px,64px 64px,150px 150px;
  mask-image:linear-gradient(to bottom,rgba(0,0,0,.9),rgba(0,0,0,.25));
}
html[data-lean-design-system="cosmic"] :where(h1,h2,h3,.report-title,.section-title){
  color:#F5FBFF;
  font-family:var(--cosmic-font-display);
  letter-spacing:.02em;
}
html[data-lean-design-system="cosmic"] :where(.date-range,.muted,.meta,.caption,small,.source-line,label){
  color:var(--cosmic-muted);
}
html[data-lean-design-system="cosmic"] :where(main,article,section,.card,.panel,.report-card,.item-card,.news-card,.lang-panel){
  border-color:var(--cosmic-line);
}
html[data-lean-design-system="cosmic"] :where(.card,.panel,.report-card,.item-card,.news-card,.lang-panel,.summary,aside.feedback-panel,.saved-item){
  background:
    linear-gradient(145deg,rgba(13,28,58,.84),rgba(7,14,34,.72)),
    radial-gradient(circle at 18% 0%,rgba(0,245,255,.08),transparent 22rem);
  border:1px solid var(--cosmic-line);
  box-shadow:var(--cosmic-shadow);
  backdrop-filter:blur(18px);
}
html[data-lean-design-system="cosmic"] :where(.summary){
  background:
    linear-gradient(135deg,rgba(0,245,255,.10),rgba(139,92,255,.08)),
    rgba(10,20,40,.72);
}
html[data-lean-design-system="cosmic"] :where(a){
  color:var(--quantum);
}
html[data-lean-design-system="cosmic"] :where(a:hover){
  color:#7EF9FF;
}
html[data-lean-design-system="cosmic"] :where(button,.button,.btn,input[type="button"],input[type="submit"]){
  border-color:rgba(0,245,255,.35);
  background:linear-gradient(135deg,rgba(0,245,255,.12),rgba(139,92,255,.12));
  color:var(--cosmic-ink);
  box-shadow:0 0 0 1px rgba(255,255,255,.03) inset;
  transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease,background .22s ease;
}
html[data-lean-design-system="cosmic"] :where(button,.button,.btn,input[type="button"],input[type="submit"]):hover{
  border-color:rgba(0,245,255,.7);
  box-shadow:0 0 22px rgba(0,245,255,.2);
  transform:translateY(-1px);
}
html[data-lean-design-system="cosmic"] :where(.primary,.action-btn.primary){
  background:linear-gradient(135deg,#00F5FF,#7EEAFF);
  border-color:rgba(126,249,255,.9);
  color:#02111f;
  font-weight:700;
}
html[data-lean-design-system="cosmic"] :where(.secondary,.action-btn.secondary){
  background:rgba(8,27,51,.72);
  border-color:rgba(0,245,255,.28);
  color:#D6E7FF;
}
html[data-lean-design-system="cosmic"] :where(.danger,.action-btn.danger){
  background:rgba(255,107,138,.10);
  border-color:rgba(255,107,138,.38);
  color:#FFB3C1;
}
html[data-lean-design-system="cosmic"] :where(input,select,textarea){
  background:rgba(5,8,22,.82);
  border-color:rgba(0,245,255,.22);
  color:var(--cosmic-ink);
}
html[data-lean-design-system="cosmic"] :where(input::placeholder,textarea::placeholder){
  color:#6F86A9;
}
html[data-lean-design-system="cosmic"] :where(input:focus,select:focus,textarea:focus,button:focus-visible){
  outline:2px solid rgba(0,245,255,.72);
  outline-offset:2px;
  border-color:rgba(0,245,255,.68);
}
html[data-lean-design-system="cosmic"] :where(table){
  background:rgba(10,20,40,.56);
  border-color:var(--cosmic-line);
}
html[data-lean-design-system="cosmic"] :where(th){
  color:var(--quantum);
}
html[data-lean-design-system="cosmic"] :where(.source-id,.category,.evidence,.saved-badge){
  background:rgba(8,27,51,.76);
  border-color:rgba(0,245,255,.22);
  color:#B8D8FF;
}
html[data-lean-design-system="cosmic"] :where(.source-id){
  color:#00131A;
  background:linear-gradient(135deg,rgba(0,245,255,.92),rgba(126,249,255,.78));
  border-color:rgba(126,249,255,.9);
  font-weight:700;
}
html[data-lean-design-system="cosmic"] :where(.category){
  color:#D9CCFF;
  background:rgba(139,92,255,.16);
  border-color:rgba(139,92,255,.38);
}
html[data-lean-design-system="cosmic"] :where(.evidence){
  color:#FFE6A3;
  background:rgba(255,209,102,.12);
  border-color:rgba(255,209,102,.42);
}
html[data-lean-design-system="cosmic"] :where(.saved-badge){
  color:#A8FFE0;
  background:rgba(124,255,178,.11);
  border-color:rgba(124,255,178,.35);
}
html[data-lean-design-system="cosmic"] :where(.concept-chip){
  background:rgba(0,245,255,.09);
  border-color:rgba(0,245,255,.28);
  color:#A9FBFF;
}
html[data-lean-design-system="cosmic"] :where(.concept-chip:hover){
  background:rgba(0,245,255,.16);
  color:#FFFFFF;
}
html[data-lean-design-system="cosmic"] :where(details.saved-list,#savedItems){
  border-color:rgba(0,245,255,.16);
}
html[data-lean-design-system="cosmic"] :where(.saved-item){
  color:#D6E7FF;
}
@media (prefers-reduced-motion:no-preference){
  html[data-lean-design-system="cosmic"] :where(.card,.panel,.report-card,.item-card,.news-card,.lang-panel,.lean-html-dock){
    animation:leanCosmicFade .45s ease both;
  }
  html[data-lean-design-system="cosmic"] :where(.report-title,h1){
    animation:leanCosmicGlow 5s ease-in-out infinite;
  }
}
@keyframes leanCosmicFade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@keyframes leanCosmicGlow{0%,100%{text-shadow:0 0 18px rgba(0,245,255,.08)}50%{text-shadow:0 0 24px rgba(0,245,255,.2)}}
@media print{
  html[data-lean-design-system="cosmic"] body{background:#fff;color:#111}
  html[data-lean-design-system="cosmic"] body::before{display:none}
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"]{
  color-scheme:light;
  --bg:#ffffff;
  --panel:#ffffff;
  --ink:#172033;
  --muted:#607086;
  --line:#d9e0ea;
  --accent:#0f766e;
  --accent-2:#5b50d6;
  --warn:#9a5a00;
  --bad:#b42318;
  --good:#166534;
  --shadow:0 12px 30px rgba(32,42,64,.10);
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] body{
  color:var(--ink);
  background:#ffffff;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] body::before{
  display:none;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] header{
  background:rgba(255,255,255,.96);
  border-color:var(--line);
  box-shadow:none;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(h1,h2,h3,.report-title,.section-title,strong,b){
  color:#172033;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(p,li,td,dd){
  color:#263244;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.date-range,.muted,.meta,.caption,small,.source-line,label){
  color:#607086;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.card,.panel,.report-card,.item-card,.news-card,.lang-panel,.summary,aside.feedback-panel,.saved-item){
  background:#ffffff;
  border:1px solid var(--line);
  box-shadow:0 1px 0 rgba(24,34,50,.03);
  backdrop-filter:none;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.summary){
  background:#eef7f6;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(a){
  color:#0b5cad;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(button,.button,.btn,input[type="button"],input[type="submit"]){
  border-color:rgba(15,118,110,.34);
  background:#f0fdfa;
  color:#0f766e;
  box-shadow:none;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.primary,.action-btn.primary){
  background:#0f766e;
  border-color:#0f766e;
  color:#ffffff;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.secondary,.action-btn.secondary){
  background:#f8fafc;
  border-color:var(--line);
  color:#172033;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.danger,.action-btn.danger){
  background:#fff5f5;
  border-color:#fecaca;
  color:#b42318;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(input,select,textarea){
  background:#ffffff;
  border-color:var(--line);
  color:#111827;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(input::placeholder,textarea::placeholder){
  color:#8794a8;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.source-id,.category,.evidence,.saved-badge){
  background:#f9fbfd;
  border-color:var(--line);
  color:#607086;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.source-id){
  color:#0f766e;
  background:#ecfdf5;
  border-color:rgba(15,118,110,.3);
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.category){
  color:#607086;
  background:#f9fbfd;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.evidence){
  color:#b45309;
  background:#fff7ed;
  border-color:#fed7aa;
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.saved-badge){
  color:#0f766e;
  background:#ecfdf5;
  border-color:rgba(15,118,110,.28);
}
html[data-lean-design-system="cosmic"][data-lean-bg="light"] :where(.concept-chip){
  background:#f0fdfa;
  border-color:rgba(15,118,110,.34);
  color:#0f766e;
}
.lean-bg-control{
  position:fixed;
  left:18px;
  bottom:18px;
  z-index:2147482999;
  display:inline-flex;
  align-items:center;
  gap:6px;
  padding:6px;
  border:1px solid rgba(96,112,134,.22);
  border-radius:999px;
  background:rgba(255,255,255,.92);
  color:#172033;
  box-shadow:0 12px 30px rgba(32,42,64,.14);
  backdrop-filter:blur(14px);
  font-family:"Inter","IBM Plex Sans","Roboto","Segoe UI","Microsoft YaHei",Arial,sans-serif;
  font-size:12px;
}
.lean-bg-control span{
  padding:0 4px 0 6px;
  color:#607086;
}
.lean-bg-control button{
  min-height:28px;
  border:1px solid transparent;
  border-radius:999px;
  padding:4px 9px;
  background:transparent;
  color:inherit;
  cursor:pointer;
}
.lean-bg-control button[aria-pressed="true"]{
  background:#172033;
  color:#ffffff;
}
html[data-lean-design-system="cosmic"][data-lean-bg="cosmic"] .lean-bg-control{
  border-color:rgba(0,245,255,.26);
  background:rgba(11,18,40,.84);
  color:#EAF6FF;
  box-shadow:0 18px 44px rgba(0,0,0,.34),0 0 24px rgba(0,245,255,.10);
}
html[data-lean-design-system="cosmic"][data-lean-bg="cosmic"] .lean-bg-control span{
  color:#9DB4D3;
}
html[data-lean-design-system="cosmic"][data-lean-bg="cosmic"] .lean-bg-control button[aria-pressed="true"]{
  background:linear-gradient(135deg,#00F5FF,#7EEAFF);
  color:#02111f;
  font-weight:700;
}
@media print{
  .lean-bg-control{display:none}
}
</style>
<script id="lean-html-background-control-script">
(function(){
  const STORAGE_KEY = 'lean-html-background-mode:' + location.pathname;
  const VALID = new Set(['light','cosmic']);
  function preferredMode(){
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (VALID.has(stored)) return stored;
    } catch (error) {}
    const attr = document.documentElement.getAttribute('data-lean-bg');
    return VALID.has(attr) ? attr : 'light';
  }
  function setBackgroundMode(mode){
    mode = VALID.has(mode) ? mode : 'light';
    document.documentElement.setAttribute('data-lean-bg', mode);
    try { localStorage.setItem(STORAGE_KEY, mode); } catch (error) {}
    document.querySelectorAll('[data-lean-bg-option]').forEach(button => {
      const active = button.getAttribute('data-lean-bg-option') === mode;
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }
  window.leanHtmlSetBackgroundMode = setBackgroundMode;
  setBackgroundMode(preferredMode());
  function install(){
    if (document.querySelector('.lean-bg-control')) return;
    const control = document.createElement('div');
    control.className = 'lean-bg-control';
    control.setAttribute('role', 'group');
    control.setAttribute('aria-label', 'Page background');
    control.innerHTML = '<span>Background</span><button type="button" data-lean-bg-option="light">Light</button><button type="button" data-lean-bg-option="cosmic">Cosmic</button>';
    control.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => setBackgroundMode(button.getAttribute('data-lean-bg-option')));
    });
    document.body.appendChild(control);
    setBackgroundMode(preferredMode());
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install);
  else install();
})();
</script>
"""


def mark_cosmic_html(html_text: str, background_mode: str = "light") -> str:
    background_mode = background_mode if background_mode in {"light", "cosmic"} else "light"
    match = re.search(r"<html\b([^>]*)>", html_text, re.I)
    if match:
        attrs = match.group(1)
        if not re.search(r"\sdata-lean-design-system=", attrs, re.I):
            attrs += ' data-lean-design-system="cosmic"'
        if re.search(r"\sdata-lean-bg=", attrs, re.I):
            attrs = re.sub(r'\sdata-lean-bg="[^"]*"', f' data-lean-bg="{background_mode}"', attrs, count=1, flags=re.I)
        else:
            attrs += f' data-lean-bg="{background_mode}"'
        replacement = f"<html{attrs}>"
        return html_text[: match.start()] + replacement + html_text[match.end() :]
    return html_text


def unmark_cosmic_html(html_text: str) -> str:
    html_text = re.sub(r'\sdata-lean-design-system="cosmic"', "", html_text, count=1, flags=re.I)
    return re.sub(r'\sdata-lean-bg="[^"]*"', "", html_text, count=1, flags=re.I)


def strip_existing_design_layer(text: str) -> str:
    pattern = re.compile(re.escape(DESIGN_MARKER_START) + r".*?" + re.escape(DESIGN_MARKER_END), re.DOTALL)
    return pattern.sub("", text)


def apply_design_system(html_text: str, design_system: str, background_mode: str = "light") -> str:
    html_text = strip_existing_design_layer(html_text)
    if design_system != "cosmic":
        return unmark_cosmic_html(html_text)
    fragment = f"\n{DESIGN_MARKER_START}\n{cosmic_design_css()}\n{DESIGN_MARKER_END}\n"
    html_text = mark_cosmic_html(html_text, background_mode)
    if "</head>" in html_text:
        return html_text.replace("</head>", fragment + "</head>", 1)
    if "<body" in html_text:
        return html_text.replace("<body", fragment + "<body", 1)
    return fragment + html_text


def feedback_css(design_system: str = "cosmic") -> str:
    if design_system == "cosmic":
        return r"""
<style id="lean-html-feedback-style">
.lean-html-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid rgba(0,245,255,.2)}
.lean-html-mark-btn,.lean-html-btn{border:1px solid rgba(0,245,255,.38);border-radius:8px;background:linear-gradient(135deg,rgba(0,245,255,.12),rgba(139,92,255,.10));color:#D6E7FF;padding:7px 10px;font:inherit;font-size:13px;cursor:pointer;transition:transform .22s ease,border-color .22s ease,box-shadow .22s ease}
.lean-html-mark-btn:hover,.lean-html-btn:hover{border-color:rgba(0,245,255,.75);box-shadow:0 0 20px rgba(0,245,255,.18);transform:translateY(-1px)}
.lean-html-strip{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.lean-html-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(0,245,255,.24);border-radius:999px;background:rgba(8,27,51,.72);padding:3px 8px;color:#9DB4D3;font-size:12px}
.lean-html-pill button{border:0;background:transparent;color:#FFD166;cursor:pointer;font-size:12px;padding:0}
.lean-html-dock{position:fixed;right:18px;bottom:18px;z-index:2147483000;width:min(420px,calc(100vw - 36px));max-height:calc(100vh - 36px);display:grid;grid-template-rows:auto auto 1fr;border:1px solid rgba(0,245,255,.28);border-radius:8px;background:rgba(11,18,40,.88);box-shadow:0 18px 44px rgba(0,0,0,.35),0 0 30px rgba(0,245,255,.12);backdrop-filter:blur(18px);overflow:hidden;color:#EAF6FF;font-family:"Inter","IBM Plex Sans","Roboto","Segoe UI","Microsoft YaHei",Arial,sans-serif}
.lean-html-dock.collapsed{grid-template-rows:auto}
.lean-html-dock.collapsed .lean-html-body,.lean-html-dock.collapsed .lean-html-saved{display:none}
.lean-html-dock header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 12px;background:linear-gradient(90deg,rgba(0,245,255,.16),rgba(139,92,255,.18));color:#F5FBFF;border-bottom:1px solid rgba(0,245,255,.18)}
.lean-html-dock header strong{font-size:14px;font-family:"Orbitron","Space Grotesk","Exo 2","Segoe UI",sans-serif;letter-spacing:.02em}
.lean-html-dock header button{border:1px solid rgba(0,245,255,.38);border-radius:6px;background:rgba(5,8,22,.42);color:#D6E7FF;cursor:pointer;padding:3px 7px}
.lean-html-body{padding:12px;overflow:auto}
.lean-html-body label{display:block;margin:8px 0 4px;color:#9DB4D3;font-size:12px}
.lean-html-body input,.lean-html-body select,.lean-html-body textarea{width:100%;border:1px solid rgba(0,245,255,.22);border-radius:6px;padding:8px;background:rgba(5,8,22,.82);color:#EAF6FF;font:inherit;font-size:13px}
.lean-html-body textarea{min-height:70px;resize:vertical}
.lean-html-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.lean-html-toolbar{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.lean-html-saved{border-top:1px solid rgba(0,245,255,.18);padding:10px 12px;max-height:180px;overflow:auto;background:rgba(5,8,22,.45)}
.lean-html-saved h3{margin:0 0 6px;font-size:13px}
.lean-html-saved ul{margin:0;padding-left:18px}
.lean-html-saved li{margin:4px 0;font-size:12px;color:#D7E8FF}
.lean-html-saved button{margin-left:6px;border:0;background:transparent;color:#FFD166;cursor:pointer}
@media print{.lean-html-dock,.lean-html-actions{display:none}}
</style>
"""
    return r"""
<style id="lean-html-feedback-style">
.lean-html-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid #d8deea}
.lean-html-mark-btn,.lean-html-btn{border:1px solid #bfdbfe;border-radius:8px;background:#eff6ff;color:#1d4ed8;padding:7px 10px;font:inherit;font-size:13px;cursor:pointer}
.lean-html-mark-btn:hover,.lean-html-btn:hover{background:#dbeafe}
.lean-html-strip{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
.lean-html-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid #d1d5db;border-radius:999px;background:#fff;padding:3px 8px;color:#475467;font-size:12px}
.lean-html-pill button{border:0;background:transparent;color:#b42318;cursor:pointer;font-size:12px;padding:0}
.lean-html-dock{position:fixed;right:18px;bottom:18px;z-index:2147483000;width:min(420px,calc(100vw - 36px));max-height:calc(100vh - 36px);display:grid;grid-template-rows:auto auto 1fr;border:1px solid #cbd5e1;border-radius:8px;background:#fff;box-shadow:0 18px 44px rgba(15,23,42,.18);overflow:hidden;color:#172033;font-family:"Segoe UI","Microsoft YaHei",Arial,sans-serif}
.lean-html-dock.collapsed{grid-template-rows:auto}
.lean-html-dock.collapsed .lean-html-body,.lean-html-dock.collapsed .lean-html-saved{display:none}
.lean-html-dock header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:10px 12px;background:#0f172a;color:#fff}
.lean-html-dock header strong{font-size:14px}
.lean-html-dock header button{border:1px solid rgba(255,255,255,.35);border-radius:6px;background:transparent;color:#fff;cursor:pointer;padding:3px 7px}
.lean-html-body{padding:12px;overflow:auto}
.lean-html-body label{display:block;margin:8px 0 4px;color:#475467;font-size:12px}
.lean-html-body input,.lean-html-body select,.lean-html-body textarea{width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:8px;color:#111827;font:inherit;font-size:13px}
.lean-html-body textarea{min-height:70px;resize:vertical}
.lean-html-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.lean-html-toolbar{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.lean-html-saved{border-top:1px solid #e5e7eb;padding:10px 12px;max-height:180px;overflow:auto;background:#f8fafc}
.lean-html-saved h3{margin:0 0 6px;font-size:13px}
.lean-html-saved ul{margin:0;padding-left:18px}
.lean-html-saved li{margin:4px 0;font-size:12px}
.lean-html-saved button{margin-left:6px;border:0;background:transparent;color:#b42318;cursor:pointer}
@media print{.lean-html-dock,.lean-html-actions{display:none}}
</style>
"""


def feedback_html(payload: dict[str, Any], design_system: str = "cosmic") -> str:
    payload_json = js_json(payload)
    filename = html.escape(payload["export_filename"], quote=True)
    return f"""
{MARKER_START}
{feedback_css(design_system)}
<aside class="lean-html-dock collapsed" id="lean-html-feedback-dock" aria-label="Second-pass feedback export">
  <header>
    <strong>Second-pass feedback · {filename}</strong>
    <button type="button" id="lean-html-toggle">Open</button>
  </header>
  <div class="lean-html-body">
    <div class="lean-html-toolbar">
      <button class="lean-html-btn" type="button" id="lean-html-annotate-selection">Annotate selection</button>
      <button class="lean-html-btn" type="button" id="lean-html-download">Download JSON</button>
      <button class="lean-html-btn" type="button" id="lean-html-copy">Copy for Codex</button>
    </div>
    <label for="lean-html-concept">Concept / selected text</label>
    <input id="lean-html-concept" type="text" placeholder="Click Mark this item or select report text">
    <div class="lean-html-row">
      <div>
        <label for="lean-html-status">Status</label>
        <select id="lean-html-status">
          <option value="unknown">unknown</option>
          <option value="learning">learning</option>
          <option value="known">known</option>
          <option value="mastered">mastered</option>
          <option value="unrated">unrated</option>
        </select>
      </div>
      <div>
        <label for="lean-html-confusion">Question type</label>
        <select id="lean-html-confusion">
          <option value="term_definition">term definition</option>
          <option value="paper_usage">paper/news usage</option>
          <option value="math_step">math step</option>
          <option value="algorithm_step">algorithm step</option>
          <option value="assumption">assumption</option>
          <option value="evidence">evidence</option>
          <option value="relation">relation</option>
          <option value="physical_intuition">physical intuition</option>
          <option value="other">other</option>
        </select>
      </div>
    </div>
    <label for="lean-html-style">Preferred explanation style</label>
    <select id="lean-html-style">
      <option value="paper_context">paper/news context</option>
      <option value="math_derivation">math derivation</option>
      <option value="physical_intuition">physical intuition</option>
      <option value="algorithm_trace">algorithm trace</option>
      <option value="examples">examples</option>
    </select>
    <label for="lean-html-question">Exact question</label>
    <textarea id="lean-html-question" placeholder="Write the exact thing still unclear after reading this report"></textarea>
    <label for="lean-html-note">Note</label>
    <textarea id="lean-html-note" placeholder="Optional: what you understood, what still feels vague"></textarea>
    <div class="lean-html-toolbar">
      <button class="lean-html-btn" type="button" id="lean-html-save">Save mark</button>
      <button class="lean-html-btn" type="button" id="lean-html-clear">Clear</button>
    </div>
    <label for="lean-html-export-fallback">Copy fallback (always populated)</label>
    <textarea id="lean-html-export-fallback" readonly aria-label="Feedback JSON fallback"></textarea>
    <p id="lean-html-active-source">No active report item.</p>
  </div>
  <div class="lean-html-saved">
    <h3>Saved marks</h3>
    <ul id="lean-html-saved-list"></ul>
  </div>
</aside>
<script>
(function(){{
  const PAYLOAD = {payload_json};
  const DEFAULT_STATUS = PAYLOAD.default_status || 'unrated';
  const storageKey = 'lean-html-skill:v2:' + PAYLOAD.feedback_path + ':' + PAYLOAD.export_filename;
  const byAnchor = new Map((PAYLOAD.items || []).map(item => [item.anchor, item]));
  let marks = [];
  let activeBase = null;
  const dock = document.getElementById('lean-html-feedback-dock');
  const toggle = document.getElementById('lean-html-toggle');
  const conceptEl = document.getElementById('lean-html-concept');
  const statusEl = document.getElementById('lean-html-status');
  const confusionEl = document.getElementById('lean-html-confusion');
  const styleEl = document.getElementById('lean-html-style');
  const questionEl = document.getElementById('lean-html-question');
  const noteEl = document.getElementById('lean-html-note');
  const activeSourceEl = document.getElementById('lean-html-active-source');
  const savedList = document.getElementById('lean-html-saved-list');
  const exportFallbackEl = document.getElementById('lean-html-export-fallback');
  function shortText(text, limit) {{
    text = String(text || '').trim();
    return text.length > limit ? text.slice(0, limit - 1) + '...' : text;
  }}
  function loadMarks() {{
    try {{
      const raw = localStorage.getItem(storageKey);
      marks = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(marks)) marks = [];
    }} catch (error) {{ marks = []; }}
  }}
  function persistMarks() {{ localStorage.setItem(storageKey, JSON.stringify(marks)); }}
  function openDock() {{ dock.classList.remove('collapsed'); toggle.textContent = 'Close'; }}
  function toggleDock() {{
    dock.classList.toggle('collapsed');
    toggle.textContent = dock.classList.contains('collapsed') ? 'Open' : 'Close';
  }}
  function baseFromItem(item) {{
    return {{
      concept: item.concept || '',
      category: item.category || '',
      source_title: item.source_title || '',
      source_url: item.source_url || '',
      source_excerpt: item.source_excerpt || '',
      selected_text: item.selected_text || item.concept || '',
      selected_language: item.selected_language || 'report_item',
      original_context: item.original_context || item.source_excerpt || '',
      translation_context: item.translation_context || '',
      block_id: item.block_id || item.anchor || '',
      status: item.status || DEFAULT_STATUS,
      annotation_kind: 'report_item',
      source_kind: PAYLOAD.source_kind || '',
      report_item_index: item.index,
      report_anchor: item.anchor
    }};
  }}
  function setActive(base) {{
    activeBase = base || {{}};
    conceptEl.value = activeBase.concept || activeBase.selected_text || '';
    statusEl.value = activeBase.status || DEFAULT_STATUS;
    activeSourceEl.textContent = activeBase.report_anchor
      ? ('Active: ' + activeBase.report_anchor + ' · ' + shortText(activeBase.source_title || activeBase.category || activeBase.block_id, 90))
      : 'Active: freeform report selection';
    openDock();
  }}
  function installItemButtons() {{
    document.querySelectorAll('.item-card[id]').forEach(card => {{
      const item = byAnchor.get(card.id);
      if (!item || card.querySelector('.lean-html-actions')) return;
      const actions = document.createElement('div');
      actions.className = 'lean-html-actions';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'lean-html-mark-btn';
      button.textContent = 'Mark this item';
      button.addEventListener('click', () => setActive(baseFromItem(item)));
      const strip = document.createElement('div');
      strip.className = 'lean-html-strip';
      strip.setAttribute('data-lean-anchor', item.anchor);
      actions.appendChild(button);
      actions.appendChild(strip);
      card.appendChild(actions);
    }});
  }}
  function selectionBase() {{
    const selection = window.getSelection();
    const text = selection ? String(selection.toString()).trim() : '';
    if (!text) {{ alert('请先选中报告中的一段文本。'); return null; }}
    let node = selection.anchorNode;
    if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
    const card = node && node.closest ? node.closest('.item-card[id]') : null;
    const item = card ? byAnchor.get(card.id) : null;
    const base = item ? baseFromItem(item) : {{}};
    base.concept = shortText(text, 140);
    base.selected_text = text;
    base.selected_language = 'report_selection';
    base.original_context = text;
    base.annotation_kind = 'report_freeform';
    base.report_anchor = item ? item.anchor : '';
    return base;
  }}
  function currentMark() {{
    const concept = conceptEl.value.trim();
    if (!concept) {{ alert('请先选择一个概念或选中文本。'); return null; }}
    const question = questionEl.value.trim();
    const status = statusEl.value || DEFAULT_STATUS;
    return Object.assign({{}}, activeBase || {{}}, {{
      feedback_id: 'feedback2::' + Date.now().toString(36) + '::' + Math.random().toString(36).slice(2, 8),
      concept,
      status,
      user_question: question,
      note: noteEl.value.trim(),
      confusion_type: confusionEl.value,
      question_type: confusionEl.value,
      explanation_style: styleEl.value,
      needs_explanation: status === 'unknown' || status === 'learning' || Boolean(question),
      action: 'lean_html_feedback2_mark',
      source_kind: PAYLOAD.source_kind || (activeBase && activeBase.source_kind) || '',
      created_at: new Date().toISOString()
    }});
  }}
  function exportPayload() {{
    const base = {{
      exported_at: new Date().toISOString(),
      generated_from: PAYLOAD.generated_from || 'lean-html-skill',
      source_feedback_path: PAYLOAD.feedback_path,
      items: marks
    }};
    if (PAYLOAD.kind === 'news') {{
      return Object.assign({{
        news_feedback_version: 2,
        briefing_title: PAYLOAD.briefing_title || PAYLOAD.title,
        date_range: PAYLOAD.date_range || '',
        briefing_path: PAYLOAD.briefing_path || PAYLOAD.reader_path || PAYLOAD.feedback_path
      }}, base);
    }}
    return Object.assign({{
      reader_feedback_version: 2,
      paper_title: PAYLOAD.paper_title || PAYLOAD.title,
      reader_path: PAYLOAD.reader_path || PAYLOAD.feedback_path,
      source_kind: PAYLOAD.source_kind || 'reader_feedback'
    }}, base);
  }}
  function renderMarks() {{
    persistMarks();
    savedList.innerHTML = '';
    const grouped = new Map();
    for (const mark of marks) {{
      const anchor = mark.report_anchor || '';
      if (!grouped.has(anchor)) grouped.set(anchor, []);
      grouped.get(anchor).push(mark);
    }}
    document.querySelectorAll('[data-lean-anchor]').forEach(strip => {{
      const anchor = strip.getAttribute('data-lean-anchor') || '';
      const local = grouped.get(anchor) || [];
      strip.innerHTML = local.map(mark => '<span class="lean-html-pill">' + shortText(mark.concept, 36) + ' · ' + mark.status + '</span>').join('');
    }});
    if (!marks.length) {{ savedList.innerHTML = '<li>No saved marks yet.</li>'; return; }}
    marks.forEach((mark, index) => {{
      const li = document.createElement('li');
      li.textContent = shortText(mark.concept, 52) + ' · ' + mark.status;
      const del = document.createElement('button');
      del.type = 'button';
      del.textContent = 'Delete';
      del.addEventListener('click', () => {{ marks.splice(index, 1); renderMarks(); }});
      li.appendChild(del);
      savedList.appendChild(li);
    }});
  }}
  function download() {{
    const data = JSON.stringify(exportPayload(), null, 2);
    exportFallbackEl.value = data;
    const blob = new Blob([data], {{type: 'application/json;charset=utf-8'}});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = PAYLOAD.export_filename || 'feedback2.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }}
  async function copy() {{
    const data = JSON.stringify(exportPayload(), null, 2);
    exportFallbackEl.value = data;
    try {{ await navigator.clipboard.writeText(data); }} catch (error) {{ exportFallbackEl.focus(); exportFallbackEl.select(); }}
    alert('已复制 feedback2 JSON，可直接粘给 Codex。');
  }}
  document.getElementById('lean-html-annotate-selection').addEventListener('click', () => {{
    const base = selectionBase();
    if (base) setActive(base);
  }});
  document.getElementById('lean-html-save').addEventListener('click', () => {{
    const mark = currentMark();
    if (!mark) return;
    marks.push(mark);
    questionEl.value = '';
    noteEl.value = '';
    renderMarks();
  }});
  document.getElementById('lean-html-clear').addEventListener('click', () => {{
    activeBase = null;
    conceptEl.value = '';
    statusEl.value = DEFAULT_STATUS;
    questionEl.value = '';
    noteEl.value = '';
    activeSourceEl.textContent = 'No active report item.';
  }});
  document.getElementById('lean-html-download').addEventListener('click', download);
  document.getElementById('lean-html-copy').addEventListener('click', copy);
  toggle.addEventListener('click', toggleDock);
  installItemButtons();
  loadMarks();
  statusEl.value = DEFAULT_STATUS;
  renderMarks();
  exportFallbackEl.value = JSON.stringify(exportPayload(), null, 2);
}})();
</script>
{MARKER_END}
"""


def strip_existing_fragment(text: str) -> str:
    pattern = re.compile(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL)
    return pattern.sub("", text)


def attach_feedback(html_text: str, fragment: str) -> str:
    html_text = strip_existing_fragment(html_text)
    if "</body>" in html_text:
        return html_text.replace("</body>", fragment + "\n</body>", 1)
    return html_text + "\n" + fragment


def cmd_attach_feedback(args: argparse.Namespace) -> int:
    html_path = Path(args.html).expanduser().resolve()
    feedback_path = Path(args.feedback).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else html_path
    feedback = load_json(feedback_path)
    payload = payload_from_feedback(feedback, feedback_path, args.source)
    html_text = html_path.read_text(encoding="utf-8-sig")
    html_text = apply_design_system(html_text, args.design_system, args.background_mode)
    feedback_design = "classic" if args.design_system == "none" else args.design_system
    output = attach_feedback(html_text, feedback_html(payload, feedback_design))
    write_text(output_path, output)
    print(f"Wrote {output_path}")
    print(f"Design system: {args.design_system}")
    print(f"Feedback export: {payload['export_filename']}")
    print(f"Items available: {len(payload['items'])}")
    return 0


def cmd_apply_design(args: argparse.Namespace) -> int:
    html_path = Path(args.html).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else html_path
    html_text = html_path.read_text(encoding="utf-8-sig")
    output = apply_design_system(html_text, args.design_system, args.background_mode)
    write_text(output_path, output)
    print(f"Wrote {output_path}")
    print(f"Design system: {args.design_system}")
    return 0


def design_audit_issues(html_text: str) -> list[str]:
    issues: list[str] = []
    if 'data-lean-design-system="cosmic"' not in html_text:
        issues.append("missing cosmic html attribute")
    if 'data-lean-bg="light"' not in html_text:
        issues.append("default background is not light")
    if DESIGN_MARKER_START not in html_text or DESIGN_MARKER_END not in html_text:
        issues.append("missing cosmic design marker")
    marker_match = re.search(
        re.escape(DESIGN_MARKER_START) + r"(?P<css>.*?)" + re.escape(DESIGN_MARKER_END),
        html_text,
        re.DOTALL,
    )
    css = marker_match.group("css") if marker_match else ""
    required_fragments = {
        "legacy background token override": "--bg:var(--space-bg)",
        "legacy panel token override": "--panel:rgba(10,20,40,.72)",
        "legacy ink token override": "--ink:var(--cosmic-ink)",
        "dark color scheme": "color-scheme:dark",
        "light mode token override": '[data-lean-bg="light"]',
        "cosmic mode option": '[data-lean-bg="cosmic"]',
        "background control": ".lean-bg-control",
        "background control script": "lean-html-background-control-script",
        "background setter": "leanHtmlSetBackgroundMode",
        "news card surface": ".news-card",
        "summary surface": ".summary",
        "feedback panel surface": "aside.feedback-panel",
        "primary button contrast": "#02111f",
        "category badge differentiation": ".category",
        "evidence badge differentiation": ".evidence",
        "form focus state": "focus-visible",
    }
    for label, fragment in required_fragments.items():
        target = html_text if label in {"background control script"} else css
        if fragment not in target:
            issues.append(f"missing {label}: {fragment}")
    screen_css = re.sub(r"@media\s+print\s*\{.*?\}\s*", "", css, flags=re.I | re.DOTALL)
    scoped_light_css = re.sub(
        r"html\[data-lean-design-system=\"cosmic\"\]\[data-lean-bg=\"light\"\][^{]*\{.*?\}",
        "",
        screen_css,
        flags=re.I | re.DOTALL,
    )
    for forbidden in ("color:#fff;cursor", "color:#ffffff;cursor"):
        if scoped_light_css.lower().find(forbidden) >= 0:
            issues.append(f"cosmic layer contains uncoordinated white control token: {forbidden}")
    for forbidden in ("background:#fff", "background:#ffffff"):
        if forbidden in screen_css.lower():
            if '[data-lean-bg="light"]' not in screen_css:
                issues.append(f"unscoped white background token without light mode: {forbidden}")
    if "Download JSON" in html_text and "download" not in html_text:
        issues.append("download control text exists but download implementation marker is missing")
    return issues


def cmd_audit_design(args: argparse.Namespace) -> int:
    html_path = Path(args.html).expanduser().resolve()
    html_text = html_path.read_text(encoding="utf-8-sig")
    issues = design_audit_issues(html_text)
    if issues:
        print("Design audit status: fail")
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print("Design audit status: pass")
    print("Cosmic layer preserves structure, defaults to light background, and exposes the optional cosmic background.")
    return 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    attach = subparsers.add_parser("attach-feedback", help="Attach a reusable feedback2 export panel to an HTML file.")
    attach.add_argument("--html", required=True, help="Input HTML report path.")
    attach.add_argument("--feedback", required=True, help="Source reader/news feedback JSON used to seed report item metadata.")
    attach.add_argument("--output", help="Output HTML path. Defaults to overwriting --html.")
    attach.add_argument("--source", default="lean-html-skill", help="Name recorded in generated_from.")
    attach.add_argument(
        "--design-system",
        default="cosmic",
        choices=["cosmic", "classic", "none"],
        help="Visual design layer to inject. Default: cosmic. Use classic/none for compatibility.",
    )
    attach.add_argument(
        "--background-mode",
        default="light",
        choices=["light", "cosmic"],
        help="Default background mode for the Cosmic layer. Default: light.",
    )
    attach.set_defaults(func=cmd_attach_feedback)
    design = subparsers.add_parser("apply-design", help="Apply only the reusable visual design layer to an HTML file.")
    design.add_argument("--html", required=True, help="Input HTML path.")
    design.add_argument("--output", help="Output HTML path. Defaults to overwriting --html.")
    design.add_argument(
        "--design-system",
        default="cosmic",
        choices=["cosmic", "classic", "none"],
        help="Visual design layer to inject. Default: cosmic. Use classic/none for compatibility.",
    )
    design.add_argument(
        "--background-mode",
        default="light",
        choices=["light", "cosmic"],
        help="Default background mode for the Cosmic layer. Default: light.",
    )
    design.set_defaults(func=cmd_apply_design)
    audit = subparsers.add_parser("audit-design", help="Adversarially audit the Cosmic visual layer in an HTML file.")
    audit.add_argument("--html", required=True, help="HTML path to audit.")
    audit.set_defaults(func=cmd_audit_design)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
