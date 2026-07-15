#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Shared reader theme controls for PaperTrace HTML readers."""

from __future__ import annotations


THEME_STORAGE_KEY = "paper.reader.theme"


def reader_theme_boot_script() -> str:
    return f"""<script>
(function () {{
  try {{
    var saved = localStorage.getItem('{THEME_STORAGE_KEY}') || 'default';
    if (!/^(default|sepia|dark|contrast)$/.test(saved)) saved = 'default';
    document.documentElement.setAttribute('data-theme', saved);
  }} catch (err) {{
    document.documentElement.setAttribute('data-theme', 'default');
  }}
}}());
</script>"""


def reader_theme_css() -> str:
    return """
:root,
:root[data-theme="default"] {
  color-scheme: light;
  --reader-bg: #f5f7fb;
  --reader-card-bg: #ffffff;
  --reader-panel-bg: #fbfcff;
  --reader-note-bg: #fffdf7;
  --reader-text: #172033;
  --reader-muted: #657085;
  --reader-border: #dbe2ee;
  --reader-math-bg: #ffffff;
  --reader-link: #1f6feb;
  --reader-code-bg: #f3f6fb;
  --reader-highlight-bg: #eef2ff;
  --reader-highlight-text: #172033;
  --reader-note-border: #ead7a4;
  --reader-primary-text: #ffffff;
  --reader-status-unknown-bg: #fff1f2;
  --reader-status-unknown-border: #fecdd3;
  --reader-status-learning-bg: #fff7ed;
  --reader-status-learning-border: #fed7aa;
  --reader-status-unrated-bg: #eef2ff;
  --reader-status-unrated-border: #c7d2fe;
  --reader-status-saved-bg: #f0fdf4;
  --reader-status-saved-border: #86efac;
  --reader-status-saved-text: #166534;
  --reader-danger-bg: #fff1f2;
  --reader-danger-border: #fecdd3;
  --reader-danger-text: #9f1239;
  --reader-accent: #1f6feb;
  --reader-accent-soft: #e8f1ff;
  --reader-cn: #0f766e;
  --reader-warn: #9a3412;
}
:root[data-theme="sepia"] {
  color-scheme: light;
  --reader-bg: #f6f0df;
  --reader-card-bg: #fffaf0;
  --reader-panel-bg: #fff7e7;
  --reader-note-bg: #fff3cc;
  --reader-text: #2f261b;
  --reader-muted: #76654d;
  --reader-border: #decda9;
  --reader-math-bg: #fffdf5;
  --reader-link: #8a5a00;
  --reader-code-bg: #f4ead3;
  --reader-highlight-bg: #f3e5bd;
  --reader-highlight-text: #2f261b;
  --reader-note-border: #d8bd74;
  --reader-primary-text: #ffffff;
  --reader-status-unknown-bg: #f9dfdf;
  --reader-status-unknown-border: #d89b9b;
  --reader-status-learning-bg: #f5e7c8;
  --reader-status-learning-border: #d4b16a;
  --reader-status-unrated-bg: #ebe0bd;
  --reader-status-unrated-border: #c5ae72;
  --reader-status-saved-bg: #e0f2dc;
  --reader-status-saved-border: #93b98b;
  --reader-status-saved-text: #22551f;
  --reader-danger-bg: #f8dddd;
  --reader-danger-border: #c97f7f;
  --reader-danger-text: #781f1f;
  --reader-accent: #8a5a00;
  --reader-accent-soft: #f3e5bd;
  --reader-cn: #0f6f62;
  --reader-warn: #9a3412;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --reader-bg: #0f172a;
  --reader-card-bg: #111827;
  --reader-panel-bg: #1e293b;
  --reader-note-bg: #292524;
  --reader-text: #e5e7eb;
  --reader-muted: #cbd5e1;
  --reader-border: #334155;
  --reader-math-bg: #1e293b;
  --reader-link: #93c5fd;
  --reader-code-bg: #020617;
  --reader-highlight-bg: #312e81;
  --reader-highlight-text: #f8fafc;
  --reader-note-border: #854d0e;
  --reader-primary-text: #020617;
  --reader-status-unknown-bg: #4c0519;
  --reader-status-unknown-border: #be123c;
  --reader-status-learning-bg: #431407;
  --reader-status-learning-border: #c2410c;
  --reader-status-unrated-bg: #1e1b4b;
  --reader-status-unrated-border: #6366f1;
  --reader-status-saved-bg: #052e16;
  --reader-status-saved-border: #16a34a;
  --reader-status-saved-text: #bbf7d0;
  --reader-danger-bg: #450a0a;
  --reader-danger-border: #dc2626;
  --reader-danger-text: #fecaca;
  --reader-accent: #93c5fd;
  --reader-accent-soft: #1d3557;
  --reader-cn: #6ee7d8;
  --reader-warn: #fdba74;
}
:root[data-theme="contrast"] {
  color-scheme: light;
  --reader-bg: #ffffff;
  --reader-card-bg: #ffffff;
  --reader-panel-bg: #ffffff;
  --reader-note-bg: #fff9d6;
  --reader-text: #000000;
  --reader-muted: #202020;
  --reader-border: #000000;
  --reader-math-bg: #ffffff;
  --reader-link: #003cff;
  --reader-code-bg: #f2f2f2;
  --reader-highlight-bg: #000000;
  --reader-highlight-text: #ffffff;
  --reader-note-border: #000000;
  --reader-primary-text: #ffffff;
  --reader-status-unknown-bg: #ffffff;
  --reader-status-unknown-border: #000000;
  --reader-status-learning-bg: #ffffff;
  --reader-status-learning-border: #000000;
  --reader-status-unrated-bg: #ffffff;
  --reader-status-unrated-border: #000000;
  --reader-status-saved-bg: #ffffff;
  --reader-status-saved-border: #000000;
  --reader-status-saved-text: #000000;
  --reader-danger-bg: #ffffff;
  --reader-danger-border: #000000;
  --reader-danger-text: #8b0000;
  --reader-accent: #003cff;
  --reader-accent-soft: #e6ecff;
  --reader-cn: #005a4e;
  --reader-warn: #8b0000;
}
.reader-theme-control {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--reader-border);
  background: var(--reader-card-bg);
  color: var(--reader-text);
  border-radius: 8px;
  padding: 6px 8px;
}
.reader-theme-control label {
  color: var(--reader-muted);
  font-weight: 700;
  font-size: .9rem;
}
.reader-theme-control select {
  border: 1px solid var(--reader-border);
  border-radius: 6px;
  background: var(--reader-panel-bg);
  color: var(--reader-text);
  padding: 4px 8px;
  font: inherit;
}
"""


def reader_theme_control() -> str:
    return """<div class="reader-theme-control" role="group" aria-label="Reader theme">
        <label for="readerThemeSelect">Theme</label>
        <select id="readerThemeSelect">
          <option value="default">Default</option>
          <option value="sepia">Eye comfort</option>
          <option value="dark">Dark</option>
          <option value="contrast">High contrast</option>
        </select>
      </div>"""


def reader_theme_script() -> str:
    return f"""<script>
(function () {{
  var key = '{THEME_STORAGE_KEY}';
  var select = document.getElementById('readerThemeSelect');
  function valid(value) {{
    return /^(default|sepia|dark|contrast)$/.test(value || '') ? value : 'default';
  }}
  function applyTheme(value) {{
    var theme = valid(value);
    document.documentElement.setAttribute('data-theme', theme);
    if (select) select.value = theme;
    try {{ localStorage.setItem(key, theme); }} catch (err) {{}}
  }}
  var saved = 'default';
  try {{ saved = localStorage.getItem(key) || 'default'; }} catch (err) {{}}
  applyTheme(saved);
  if (select) {{
    select.addEventListener('change', function () {{ applyTheme(select.value); }});
  }}
}}());
</script>"""
