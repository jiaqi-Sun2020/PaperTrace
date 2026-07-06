#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared HTML post-processing utilities for PAPER skills."""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


VALID_STATUSES = {"mastered", "known", "learning", "unknown", "unrated"}
MARKER_START = "<!-- lean-html-skill:feedback2:start -->"
MARKER_END = "<!-- lean-html-skill:feedback2:end -->"


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


def valid_status(value: Any) -> str:
    status = clean_text(value, 80).lower()
    return status if status in VALID_STATUSES else "unrated"


def item_meta(index: int, item: dict[str, Any]) -> dict[str, Any]:
    concept = clean_text(item.get("concept") or item.get("selected_text") or f"feedback item {index}", 600)
    block_id = clean_text(item.get("block_id") or item.get("bilingual_block_id") or f"item-{index:02d}", 180)
    source_excerpt = clean_text(item.get("source_excerpt") or item.get("original_context") or item.get("note"), 2200)
    return {
        "index": index,
        "anchor": f"item-{index:02d}",
        "concept": concept,
        "status": valid_status(item.get("status")),
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
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "items": [item_meta(index, item) for index, item in enumerate(items, start=1)],
    }


def feedback_css() -> str:
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


def feedback_html(payload: dict[str, Any]) -> str:
    payload_json = js_json(payload)
    filename = html.escape(payload["export_filename"], quote=True)
    return f"""
{MARKER_START}
{feedback_css()}
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
      annotation_kind: 'report_item',
      source_kind: PAYLOAD.source_kind || '',
      report_item_index: item.index,
      report_anchor: item.anchor
    }};
  }}
  function setActive(base) {{
    activeBase = base || {{}};
    conceptEl.value = activeBase.concept || activeBase.selected_text || '';
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
    const status = statusEl.value;
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
    await navigator.clipboard.writeText(data);
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
    questionEl.value = '';
    noteEl.value = '';
    activeSourceEl.textContent = 'No active report item.';
  }});
  document.getElementById('lean-html-download').addEventListener('click', download);
  document.getElementById('lean-html-copy').addEventListener('click', copy);
  toggle.addEventListener('click', toggleDock);
  installItemButtons();
  loadMarks();
  renderMarks();
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
    output = attach_feedback(html_text, feedback_html(payload))
    write_text(output_path, output)
    print(f"Wrote {output_path}")
    print(f"Feedback export: {payload['export_filename']}")
    print(f"Items available: {len(payload['items'])}")
    return 0


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    attach = subparsers.add_parser("attach-feedback", help="Attach a reusable feedback2 export panel to an HTML file.")
    attach.add_argument("--html", required=True, help="Input HTML report path.")
    attach.add_argument("--feedback", required=True, help="Source reader/news feedback JSON used to seed report item metadata.")
    attach.add_argument("--output", help="Output HTML path. Defaults to overwriting --html.")
    attach.add_argument("--source", default="lean-html-skill", help="Name recorded in generated_from.")
    attach.set_defaults(func=cmd_attach_feedback)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
