#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build an interactive AI+quantum news briefing HTML with feedback export."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config_to_news_feedback import export_feedback, write_json


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def slug(value: str, fallback: str) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text, flags=re.IGNORECASE).strip("-")
    return text[:80] or fallback


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def js_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def normalize_config(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    title = clean_text(config.get("briefing_title") or config.get("title") or "AI + Quantum News Briefing")
    date_range = clean_text(config.get("date_range") or config.get("date") or "")
    sections = config.get("sections") or []
    if not isinstance(sections, list):
        raise ValueError("config.sections must be a list")

    normalized_sections: list[dict[str, Any]] = []
    all_items: list[dict[str, Any]] = []
    item_index = 1
    for section_index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        section_title = clean_text(section.get("title") or f"Section {section_index}")
        raw_items = section.get("items") or []
        if not isinstance(raw_items, list):
            continue
        normalized_items: list[dict[str, Any]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item_id = clean_text(raw_item.get("id")) or f"N{item_index:03d}"
            title_text = clean_text(raw_item.get("title") or raw_item.get("concept") or f"News item {item_index}")
            category = clean_text(raw_item.get("category") or section_title)
            concepts = raw_item.get("concepts") or []
            if not isinstance(concepts, list):
                concepts = [concepts]
            item = {
                "id": item_id,
                "story_id": clean_text(raw_item.get("story_id")),
                "novelty": clean_text(raw_item.get("novelty") or raw_item.get("delta_status")),
                "delta_note": clean_text(raw_item.get("delta_note")),
                "title": title_text,
                "category": category,
                "facts": clean_text(raw_item.get("facts") or raw_item.get("fact") or raw_item.get("summary")),
                "judgment": clean_text(raw_item.get("judgment") or raw_item.get("analysis")),
                "relevance": clean_text(raw_item.get("relevance") or raw_item.get("research_relevance")),
                "source_title": clean_text(raw_item.get("source_title") or title_text),
                "source_url": clean_text(raw_item.get("source_url")),
                "source_excerpt": clean_text(raw_item.get("source_excerpt") or raw_item.get("facts") or raw_item.get("summary")),
                "evidence_level": clean_text(raw_item.get("evidence_level")),
                "concepts": [clean_text(c) for c in concepts if clean_text(c)],
            }
            normalized_items.append(item)
            all_items.append(item)
            item_index += 1
        normalized_sections.append({"title": section_title, "items": normalized_items})

    return {
        "news_feedback_version": 1,
        "briefing_title": title,
        "date_range": date_range,
        "briefing_path": clean_text(config.get("briefing_path") or str(config_path)),
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "summary": clean_text(config.get("summary")),
        "sections": normalized_sections,
        "items": all_items,
        "profile_path": clean_text(config.get("profile_path")),
    }


def render_item(item: dict[str, Any]) -> str:
    chips = []
    for concept in item["concepts"]:
        chips.append(
            f'<button class="concept-chip" type="button" data-item-id="{esc(item["id"])}" '
            f'data-concept="{esc(concept)}">{esc(concept)}</button>'
        )
    source = ""
    if item.get("source_url"):
        source = f'<a href="{esc(item["source_url"])}" target="_blank" rel="noopener">{esc(item["source_title"])}</a>'
    elif item.get("source_title"):
        source = esc(item["source_title"])
    evidence = f'<span class="evidence">{esc(item["evidence_level"])}</span>' if item.get("evidence_level") else ""
    novelty = f'<span class="evidence">{esc(item["novelty"])}</span>' if item.get("novelty") else ""
    delta_note = f'<p class="source-line"><strong>Delta: </strong>{esc(item["delta_note"])}</p>' if item.get("delta_note") else ""
    return f"""
<article class="news-card" id="{esc(item['id'])}" data-item-id="{esc(item['id'])}">
  <div class="card-top">
    <span class="source-id">{esc(item['id'])}</span>
    <span class="category">{esc(item['category'])}</span>
    {evidence}
    {novelty}
  </div>
  <h3>{esc(item['title'])}</h3>
  <p><strong>事实：</strong>{esc(item['facts'])}</p>
  <p><strong>判断：</strong>{esc(item['judgment'])}</p>
  {f'<p><strong>对你的启发：</strong>{esc(item["relevance"])}</p>' if item.get("relevance") else ""}
  {delta_note}
  <div class="concept-row">{''.join(chips) or '<span class="muted">No concept chips</span>'}</div>
  <p class="source-line"><strong>来源：</strong>{source or "未提供"} </p>
  <div class="mark-strip" data-mark-strip="{esc(item['id'])}"></div>
</article>
"""


def render_html(config: dict[str, Any]) -> str:
    sections_html = []
    for section in config["sections"]:
        items_html = "\n".join(render_item(item) for item in section["items"])
        sections_html.append(
            f'<section class="briefing-section"><h2>{esc(section["title"])}</h2>{items_html}</section>'
        )
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(config['briefing_title'])}</title>
  <style>
    :root {{
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #1d2433;
      --muted: #607086;
      --line: #d9e0ea;
      --accent: #0f766e;
      --accent-2: #7c3aed;
      --warn: #b45309;
      --bad: #b91c1c;
      --good: #166534;
      --shadow: 0 12px 30px rgba(32, 42, 64, 0.10);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      color: var(--ink);
      background: var(--bg);
      line-height: 1.65;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      background: rgba(247, 248, 251, 0.96);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
    }}
    .header-inner {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 18px 22px;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 16px;
      align-items: center;
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      letter-spacing: 0;
    }}
    .date-range, .muted {{
      color: var(--muted);
      font-size: 13px;
    }}
    .layout {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 22px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 350px;
      gap: 20px;
      align-items: start;
    }}
    .summary {{
      padding: 14px 16px;
      border: 1px solid var(--line);
      background: #eef7f6;
      border-radius: 8px;
      margin-bottom: 18px;
    }}
    .briefing-section {{
      margin-bottom: 24px;
    }}
    h2 {{
      margin: 0 0 12px;
      font-size: 18px;
    }}
    .news-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 1px 0 rgba(24, 34, 50, 0.03);
    }}
    .news-card.marked {{
      border-color: rgba(15, 118, 110, 0.45);
    }}
    .card-top {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      margin-bottom: 8px;
    }}
    .source-id, .category, .evidence, .saved-badge {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 12px;
      border: 1px solid var(--line);
      color: var(--muted);
      background: #f9fbfd;
    }}
    .source-id {{
      color: var(--accent);
      border-color: rgba(15, 118, 110, 0.3);
      background: #ecfdf5;
    }}
    .evidence {{
      color: var(--warn);
      background: #fff7ed;
      border-color: #fed7aa;
    }}
    h3 {{
      margin: 0 0 10px;
      font-size: 17px;
      line-height: 1.45;
    }}
    p {{
      margin: 8px 0;
    }}
    a {{
      color: #0b5cad;
    }}
    .concept-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    button, select, input, textarea {{
      font: inherit;
    }}
    .concept-chip, .action-btn {{
      border: 1px solid rgba(15, 118, 110, 0.34);
      color: var(--accent);
      background: #f0fdfa;
      min-height: 30px;
      border-radius: 8px;
      padding: 4px 9px;
      cursor: pointer;
    }}
    .concept-chip:hover, .action-btn:hover {{
      background: #ccfbf1;
    }}
    .source-line {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 12px;
    }}
    .mark-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 10px;
    }}
    .saved-badge {{
      color: var(--accent);
      background: #ecfdf5;
      border-color: rgba(15, 118, 110, 0.28);
    }}
    aside.feedback-panel {{
      position: sticky;
      top: 86px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 14px;
      max-height: calc(100vh - 110px);
      overflow: auto;
    }}
    .panel-title {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .panel-title h2 {{
      margin: 0;
    }}
    .field {{
      margin-bottom: 10px;
    }}
    label {{
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: #fff;
      color: var(--ink);
    }}
    textarea {{
      min-height: 78px;
      resize: vertical;
    }}
    .button-row {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin: 10px 0;
    }}
    .primary {{
      background: var(--accent);
      color: #fff;
      border-color: var(--accent);
    }}
    .secondary {{
      background: #f8fafc;
      color: var(--ink);
      border-color: var(--line);
    }}
    .danger {{
      color: var(--bad);
      border-color: #fecaca;
      background: #fff5f5;
    }}
    details.saved-list {{
      margin-top: 12px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }}
    #savedItems {{
      max-height: 220px;
      overflow: auto;
      display: grid;
      gap: 8px;
      margin-top: 8px;
    }}
    .saved-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px;
      background: #fbfdff;
      font-size: 13px;
    }}
    .saved-item strong {{
      display: block;
      margin-bottom: 2px;
    }}
    .saved-item .tiny {{
      color: var(--muted);
      font-size: 12px;
    }}
    .floating-annotate {{
      position: fixed;
      right: 24px;
      bottom: 24px;
      z-index: 20;
      box-shadow: var(--shadow);
    }}
    @media (max-width: 920px) {{
      .header-inner, .layout {{
        grid-template-columns: 1fr;
      }}
      aside.feedback-panel {{
        position: static;
        max-height: none;
      }}
      .floating-annotate {{
        right: 14px;
        bottom: 14px;
      }}
    }}
    @media print {{
      header, aside.feedback-panel, .floating-annotate, .concept-row, .mark-strip {{
        display: none !important;
      }}
      body {{
        background: #fff;
      }}
      .layout {{
        display: block;
        max-width: none;
      }}
      .news-card {{
        box-shadow: none;
        break-inside: avoid;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div>
        <h1>{esc(config['briefing_title'])}</h1>
        <div class="date-range">日期窗口：{esc(config['date_range'] or '未指定')}</div>
      </div>
      <div class="date-range">点击概念或选中文本后标注；导出 JSON 后交给 reader-learner。</div>
    </div>
  </header>
  <main class="layout">
    <div>
      {f'<div class="summary"><strong>一句话：</strong>{esc(config["summary"])}</div>' if config.get("summary") else ""}
      {''.join(sections_html)}
    </div>
    <aside class="feedback-panel" aria-label="Feedback panel">
      <div class="panel-title">
        <h2>Feedback</h2>
        <span id="savedCount" class="source-id">0</span>
      </div>
      <div class="field">
        <label for="conceptInput">Concept / selected text</label>
        <input id="conceptInput" placeholder="点击概念或自由标注">
      </div>
      <div class="field">
        <label for="statusSelect">Status</label>
        <select id="statusSelect">
          <option value="unrated" selected>unrated / 见过但未判断</option>
          <option value="unknown">unknown / 不清楚</option>
          <option value="learning">learning / 学习中</option>
          <option value="known">known / 已理解</option>
          <option value="mastered">mastered / 能讲清楚会用</option>
        </select>
      </div>
      <div class="field">
        <label for="questionType">Question type</label>
        <select id="questionType">
          <option value="">未指定</option>
          <option value="term_definition">术语定义</option>
          <option value="paper_usage">论文/新闻用法</option>
          <option value="algorithm_step">算法步骤</option>
          <option value="math_step">数学步骤</option>
          <option value="assumption">隐含假设</option>
          <option value="evidence">证据/图表</option>
          <option value="relation">概念关系</option>
          <option value="other">其他</option>
        </select>
      </div>
      <div class="field">
        <label for="styleSelect">Explanation style</label>
        <select id="styleSelect">
          <option value="">默认</option>
          <option value="first_principles">first principles</option>
          <option value="paper_context">paper/news context</option>
          <option value="math_steps">math steps</option>
          <option value="analogy">analogy</option>
          <option value="example">example</option>
        </select>
      </div>
      <div class="field">
        <label for="questionInput">Exact question</label>
        <textarea id="questionInput" placeholder="你具体哪里不清楚？"></textarea>
      </div>
      <div class="field">
        <label for="noteInput">Note</label>
        <textarea id="noteInput" placeholder="自己的理解、卡点、想比较的对象"></textarea>
      </div>
      <div class="field">
        <label for="contextInput">Source context</label>
        <textarea id="contextInput" placeholder="来源上下文会自动填入，也可以手动改"></textarea>
      </div>
      <div class="button-row">
        <button id="saveBtn" class="action-btn primary" type="button">Save mark</button>
        <button id="deleteBtn" class="action-btn danger" type="button">Delete current</button>
        <button id="downloadBtn" class="action-btn secondary" type="button">Download JSON</button>
        <button id="copyBtn" class="action-btn secondary" type="button">Copy for Codex</button>
      </div>
      <details class="saved-list" open>
        <summary>Saved annotations</summary>
        <div id="savedItems"></div>
      </details>
    </aside>
  </main>
  <button id="annotateBtn" class="action-btn floating-annotate" type="button">Annotate selection</button>
  <script id="briefing-data" type="application/json">{js_json(config)}</script>
  <script>
    const CONFIG = JSON.parse(document.getElementById('briefing-data').textContent);
    const DEFAULT_STATUS = CONFIG.default_status || 'unrated';
    const INITIAL_FEEDBACK = Array.isArray(CONFIG.initial_feedback_items) ? CONFIG.initial_feedback_items : [];
    const itemMap = new Map(CONFIG.items.map(item => [item.id, item]));
    const storageKey = 'news-feedback::' + CONFIG.briefing_title + '::' + CONFIG.date_range;
    let saved = [];
    let active = null;

    function mergeInitialFeedback(stored, initial) {{
      const byId = new Map();
      const order = [];
      function add(entry, replace) {{
        if (!entry || !entry.feedback_id) return;
        if (!byId.has(entry.feedback_id)) order.push(entry.feedback_id);
        if (replace || !byId.has(entry.feedback_id)) byId.set(entry.feedback_id, entry);
      }}
      initial.forEach(entry => add(entry, false));
      stored.forEach(entry => add(entry, true));
      return order.map(id => byId.get(id)).filter(Boolean);
    }}

    try {{
      const stored = JSON.parse(localStorage.getItem(storageKey) || '[]');
      saved = mergeInitialFeedback(Array.isArray(stored) ? stored : [], INITIAL_FEEDBACK);
    }} catch (err) {{
      saved = mergeInitialFeedback([], INITIAL_FEEDBACK);
    }}

    const $ = id => document.getElementById(id);
    const conceptInput = $('conceptInput');
    const statusSelect = $('statusSelect');
    const questionType = $('questionType');
    const styleSelect = $('styleSelect');
    const questionInput = $('questionInput');
    const noteInput = $('noteInput');
    const contextInput = $('contextInput');

    function itemContext(item) {{
      if (!item) return '';
      const parts = [];
      if (item.category) parts.push('Category: ' + item.category);
      if (item.source_title) parts.push('Source title: ' + item.source_title);
      if (item.source_url) parts.push('Source URL: ' + item.source_url);
      if (item.source_excerpt) parts.push('Context: ' + item.source_excerpt);
      return parts.join('\\n');
    }}

    function makeFeedbackId(concept, blockId) {{
      return 'news::' + concept + '::' + (blockId || CONFIG.date_range || CONFIG.briefing_title);
    }}

    function openFeedback(payload) {{
      const item = payload.itemId ? itemMap.get(payload.itemId) : null;
      const concept = payload.concept || payload.selectedText || '';
      const blockId = payload.itemId || '';
      active = {{
        feedback_id: makeFeedbackId(concept, blockId),
        concept,
        block_id: blockId,
        annotation_kind: payload.annotationKind || 'news_concept',
        category: item ? item.category : '',
        source_title: item ? item.source_title : '',
        source_url: item ? item.source_url : '',
        source_excerpt: payload.sourceExcerpt || itemContext(item),
        selected_text: payload.selectedText || concept,
        selected_language: 'news'
      }};
      const existing = saved.find(entry => entry.feedback_id === active.feedback_id);
      conceptInput.value = concept;
      statusSelect.value = existing ? existing.status : DEFAULT_STATUS;
      questionType.value = existing ? (existing.confusion_type || '') : '';
      styleSelect.value = existing ? (existing.explanation_style || '') : '';
      questionInput.value = existing ? (existing.user_question || '') : '';
      noteInput.value = existing ? (existing.note || '') : '';
      contextInput.value = existing ? (existing.source_excerpt || active.source_excerpt || '') : (active.source_excerpt || '');
      conceptInput.focus();
    }}

    function currentPayload() {{
      const concept = conceptInput.value.trim();
      if (!concept) {{
        alert('先点击概念或选中文本。');
        return null;
      }}
      const base = active || {{}};
      const status = statusSelect.value || DEFAULT_STATUS;
      return {{
        feedback_id: base.feedback_id || makeFeedbackId(concept, base.block_id),
        concept,
        status,
        note: noteInput.value.trim(),
        user_question: questionInput.value.trim(),
        confusion_type: questionType.value,
        explanation_style: styleSelect.value,
        needs_explanation: Boolean(questionInput.value.trim() || status === 'unknown' || status === 'learning'),
        block_id: base.block_id || '',
        annotation_kind: base.annotation_kind || 'news_concept',
        source_excerpt: contextInput.value.trim(),
        selected_text: base.selected_text || concept,
        selected_language: base.selected_language || 'news',
        translation: '',
        category: base.category || '',
        source_title: base.source_title || '',
        source_url: base.source_url || '',
        action: 'news_feedback',
        source_kind: base.source_kind || 'news_briefing'
      }};
    }}

    function persist() {{
      localStorage.setItem(storageKey, JSON.stringify(saved));
      renderSaved();
      renderBadges();
    }}

    function saveCurrent() {{
      const payload = currentPayload();
      if (!payload) return;
      const index = saved.findIndex(entry => entry.feedback_id === payload.feedback_id);
      if (index >= 0) saved[index] = payload;
      else saved.push(payload);
      active = payload;
      persist();
    }}

    function deleteCurrent() {{
      const concept = conceptInput.value.trim();
      const id = active ? active.feedback_id : makeFeedbackId(concept, '');
      saved = saved.filter(entry => entry.feedback_id !== id);
      active = null;
      persist();
    }}

    function payload() {{
      return {{
        news_feedback_version: 1,
        briefing_title: CONFIG.briefing_title,
        date_range: CONFIG.date_range,
        briefing_path: CONFIG.briefing_path || location.href,
        exported_at: new Date().toISOString(),
        default_status: DEFAULT_STATUS,
        items: saved
      }};
    }}

    function downloadFeedback() {{
      const blob = new Blob([JSON.stringify(payload(), null, 2)], {{type: 'application/json;charset=utf-8'}});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'news_feedback.json';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }}

    async function copyFeedback() {{
      const text = JSON.stringify(payload(), null, 2);
      try {{
        await navigator.clipboard.writeText(text);
        alert('已复制 feedback JSON。');
      }} catch (err) {{
        prompt('复制以下 JSON：', text);
      }}
    }}

    function renderSaved() {{
      $('savedCount').textContent = String(saved.length);
      const wrap = $('savedItems');
      wrap.innerHTML = '';
      if (!saved.length) {{
        wrap.innerHTML = '<div class="muted">No saved annotations yet.</div>';
        return;
      }}
      saved.forEach((entry, index) => {{
        const div = document.createElement('div');
        div.className = 'saved-item';
        div.innerHTML = '<strong></strong><div class="tiny"></div><div class="button-row"><button type="button" class="action-btn secondary">Edit</button><button type="button" class="action-btn danger">Delete</button></div>';
        div.querySelector('strong').textContent = entry.concept;
        div.querySelector('.tiny').textContent = (entry.status || DEFAULT_STATUS) + ' · ' + (entry.category || entry.block_id || 'news');
        const buttons = div.querySelectorAll('button');
        buttons[0].addEventListener('click', () => {{
          active = entry;
          conceptInput.value = entry.concept || '';
          statusSelect.value = entry.status || DEFAULT_STATUS;
          questionType.value = entry.confusion_type || '';
          styleSelect.value = entry.explanation_style || '';
          questionInput.value = entry.user_question || '';
          noteInput.value = entry.note || '';
          contextInput.value = entry.source_excerpt || '';
        }});
        buttons[1].addEventListener('click', () => {{
          saved.splice(index, 1);
          persist();
        }});
        wrap.appendChild(div);
      }});
    }}

    function renderBadges() {{
      document.querySelectorAll('.news-card').forEach(card => {{
        const itemId = card.dataset.itemId;
        const strip = card.querySelector('[data-mark-strip]');
        const marks = saved.filter(entry => entry.block_id === itemId);
        card.classList.toggle('marked', marks.length > 0);
        strip.innerHTML = '';
        marks.forEach(entry => {{
          const span = document.createElement('span');
          span.className = 'saved-badge';
          span.textContent = '已标注: ' + entry.concept + ' / ' + entry.status;
          strip.appendChild(span);
        }});
      }});
    }}

    document.querySelectorAll('.concept-chip').forEach(button => {{
      button.addEventListener('click', () => {{
        openFeedback({{
          itemId: button.dataset.itemId,
          concept: button.dataset.concept,
          annotationKind: 'news_concept'
        }});
      }});
    }});

    $('annotateBtn').addEventListener('click', () => {{
      const selection = window.getSelection();
      const text = selection ? selection.toString().trim() : '';
      if (!text) {{
        alert('请先选中一段日报文本。');
        return;
      }}
      let node = selection.anchorNode;
      if (node && node.nodeType === Node.TEXT_NODE) node = node.parentElement;
      const card = node && node.closest ? node.closest('.news-card') : null;
      openFeedback({{
        itemId: card ? card.dataset.itemId : '',
        concept: text.slice(0, 120),
        selectedText: text,
        annotationKind: 'news_freeform'
      }});
    }});
    $('saveBtn').addEventListener('click', saveCurrent);
    $('deleteBtn').addEventListener('click', deleteCurrent);
    $('downloadBtn').addEventListener('click', downloadFeedback);
    $('copyBtn').addEventListener('click', copyFeedback);

    renderSaved();
    renderBadges();
  </script>
</body>
</html>
"""
    return html_doc


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="News briefing feedback config JSON.")
    parser.add_argument("--output", help="Output HTML path. Defaults beside config.")
    parser.add_argument("--feedback-output", help="Auto-write full-concept news_feedback.json. Defaults beside HTML.")
    parser.add_argument("--default-status", default="unrated", choices=["mastered", "known", "learning", "unknown", "unrated"], help="Default status for auto-exported concepts.")
    parser.add_argument("--no-auto-feedback", action="store_true", help="Do not write the full-concept news_feedback.json sidecar.")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()
    raw_config = load_json(config_path)
    config = normalize_config(raw_config, config_path)
    feedback = export_feedback(raw_config, config_path, args.default_status, "concept-source")
    config["default_status"] = feedback["default_status"]
    config["initial_feedback_items"] = feedback["items"]
    output_path = Path(args.output).expanduser().resolve() if args.output else config_path.with_suffix(".html")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(config), encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Items: {len(config['items'])}")
    if not args.no_auto_feedback:
        feedback_path = (
            Path(args.feedback_output).expanduser().resolve()
            if args.feedback_output
            else output_path.with_name("news_feedback.json")
        )
        write_json(feedback_path, feedback)
        print(f"Wrote auto feedback: {feedback_path}")
        print(f"Concept items: {len(feedback['items'])}")
        print(f"Default status: {feedback['default_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
