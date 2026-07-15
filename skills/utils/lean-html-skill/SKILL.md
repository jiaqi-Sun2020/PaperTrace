---
name: lean-html-skill
description: Render or post-process shared standalone HTML layers for PaperTrace skills, including compact report shells, reusable embedded CSS/JS, Cosmic Sci-Fi Product Design System styling, and manual feedback export panels that produce reader_feedback2.json or news_feedback2.json. Use when reader-skill, ai-quantum-news-briefing, adaptive-teach, or another PaperTrace skill needs HTML output, interactive concept/freeform annotation, copy/download feedback JSON, professional futuristic web styling, or wants to avoid duplicating HTML/feedback UI logic inside domain-specific skills.
---

# Lean HTML Skill

## Purpose

Keep HTML rendering concerns out of domain skills. Paper/news skills should prepare structured data and source-grounded content; this utility owns shared standalone HTML behavior, especially manual feedback export.

Use this skill when a PaperTrace skill needs:

- a standalone HTML artifact with embedded CSS/JS;
- a shared reader/report HTML shell for domain-specific body content;
- a reusable second-pass feedback panel for an existing HTML report;
- `news_feedback2.json` or `reader_feedback2.json` export from an HTML page;
- a reusable visual design layer that turns ordinary report/web UI into a Cosmic Sci-Fi product interface;
- consistent “HTML page collects feedback, but never writes `.agents` directly” behavior.

## Cosmic Sci-Fi Design Layer

Default HTML styling uses the Cosmic Sci-Fi Product Design System. This layer is visual only: it maps existing structure into a professional "NASA x SpaceX x Quantum Computing x Future Operating System" interface while preserving functionality, data, user requirements, and interactions.

Apply this flow for generated or post-processed HTML:

User Request -> Requirement Analysis -> Information Architecture -> Cosmic Sci-Fi Design Mapping -> HTML/CSS/JS Generation -> Output

Read `references/cosmic-sci-fi-design-system.md` before changing the visual style or adding new reusable HTML components.

Design layer rules:

- Keep functionality, information architecture, data schema, source links, annotation behavior, copy/download JSON controls, and import boundaries unchanged.
- Use design tokens, semantic HTML, responsive CSS, accessible labels, and readable contrast. When post-processing existing pages, override legacy tokens such as `--bg`, `--panel`, `--ink`, `--muted`, `--line`, `--accent`, and `--shadow` so white surfaces cannot leak through.
- Prefer deep-space backgrounds, quantum glass panels, restrained cyan/purple accents, command-center density, and subtle motion.
- Default page background is `light`/white for readability. Inject a background control so the reader can switch to the Cosmic deep-space background when desired; persist that preference in browser localStorage.
- Avoid game HUDs, cheap cyberpunk, excessive neon, heavy canvas particles, and visual changes that reduce readability.
- Use `--design-system classic` or `--design-system none` only for compatibility or test isolation.

## Boundary

- Do not mutate `.agents` or `knowledge_profile.json`.
- Do not infer learner status from content alone. Preserve explicit statuses from source feedback; when a saved mark has no status, use `unrated` for both news/daily reports and reader/paper reports.
- Do not own paper/news domain logic, explanations, citations, or source-map interpretation.
- Do not hide feedback in browser memory as if it were persisted. The user must click download/copy.

## Reader-Skill Integration Boundary

`reader-skill` should pass reader-specific body content and metadata into this utility instead of growing duplicate HTML/CSS/JS. In that integration:

- `reader-skill` owns Markdown parsing, bilingual block semantics, source anchors, concept/profile matching, and translation validation.
- `lean-html-skill` owns reusable page chrome, shared feedback forms, copy/download controls, localStorage/browser-memory behavior, and common status/question UI.
- Existing `reader-skill/scripts/markdown_reader_to_html.py` may remain as a compatibility wrapper while reusable HTML pieces are migrated here incrementally.
- New feedback export behavior for reader HTML should be implemented here first, then called from `reader-skill`.
- Shared reader feedback UI must keep `Download feedback JSON` and `Copy feedback for Codex` working, close the annotate panel after `Save mark`, and close on Esc, blank-page click, or the close button.
- `Copy feedback for Codex` must populate a visible fallback textarea with the export JSON even when clipboard access is unavailable; feedback must never be trapped behind a browser permission failure.
- Shared knowledge marks must preserve reader-specific metadata from `reader-skill`: `data-concept`, `data-status`, `data-source-anchor`, `data-concept-type`, `data-alias-zh`, and `title`.
- Shared inline rendering must not annotate or math-wrap inside `href`, `src`, file paths, source-page labels, code spans, or HTML attributes. Source Page Index links must remain plain clickable paths.

## Quick Start

Attach a feedback2 panel to an existing report HTML:

```powershell
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json>
```

Write to a separate file:

```powershell
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <feedback.json> --output <report_interactive.html>
```

Use the legacy visual layer only when needed:

```powershell
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <feedback.json> --design-system classic
```

Apply only the Cosmic visual layer without adding a feedback2 panel:

```powershell
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py apply-design --html <report.html> --design-system cosmic
```

Default to the white background and keep Cosmic as a user-selectable option:

```powershell
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py apply-design --html <report.html> --design-system cosmic --background-mode light
```

Audit the applied visual layer:

```powershell
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py audit-design --html <report.html>
```

The script detects news feedback and exports `news_feedback2.json`; otherwise it exports `reader_feedback2.json`.
All feedback controls default new marks to `unrated` unless the source feedback explicitly provides a status.

## Integration Pattern

Domain skills should follow this split:

1. Build structured content: concepts, sections, source titles/URLs, excerpts, profile status, explanation cards.
2. Render or provide the domain-specific body. For example, `reader-skill` owns bilingual source blocks, `ai-quantum-news-briefing` owns daily briefing content, and `adaptive-teach` owns lesson content.
3. Use this utility for reusable standalone HTML shell behavior and shared annotation/export controls.
4. Tell the user the HTML only collects feedback; profile updates still require `reader-learner` or `ai-quantum-news-briefing/scripts/import_news_feedback.py`.

For reader HTML integration, domain skills should run the shared contract validator before reporting success. The contract rejects missing MathJax, missing feedback close handlers, missing copy fallback, source-page links polluted by generated markup, Algorithm summaries, missing knowledge-mark metadata, and reader-notes structure pollution.

## Resources

- `scripts/lean_html.py`: CLI utility for post-processing HTML reports with a feedback2 panel.
- `references/cosmic-sci-fi-design-system.md`: visual-only Cosmic Sci-Fi Product Design System layer.
- `references/feedback2-contract.md`: JSON shape and integration rules for second-pass feedback.
