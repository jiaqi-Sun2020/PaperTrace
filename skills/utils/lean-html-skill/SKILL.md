---
name: lean-html-skill
description: Render or post-process shared standalone HTML layers for PaperTrace skills, including compact report shells, reusable embedded CSS/JS, browser-local feedback recovery, Cosmic Sci-Fi Product Design System styling, and manual JSON export. Use when reader-skill, ai-quantum-news-briefing, adaptive-teach, or another PaperTrace skill needs HTML output, interactive annotation, copy/download feedback JSON, or shared browser UI behavior.
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
- Treat every background-selectable component as a paired foreground/surface contract. Daily story and worked-example components use `--story-surface`, `--story-panel`, `--story-subtle`, `--story-warning-surface`, `--story-border`, `--story-accent`, and `--table-surface`; define them for Light, Cosmic, and print rather than patching individual screenshots.
- Keep normal text at WCAG AA `4.5:1` or better. `audit-design` must fail when a story/table binding is missing, a palette color cannot be audited, or a foreground/surface pair falls below the threshold.
- Prefer deep-space backgrounds, quantum glass panels, restrained cyan/purple accents, command-center density, and subtle motion.
- Default page background is `light`/white for readability. Inject a background control so the reader can switch to the Cosmic deep-space background when desired; persist that preference in browser localStorage.
- Avoid game HUDs, cheap cyberpunk, excessive neon, heavy canvas particles, and visual changes that reduce readability.
- Use `--design-system classic` or `--design-system none` only for compatibility or test isolation.

## Boundary

- Do not mutate `.agents` or `knowledge_profile.json`.
- Do not infer learner status from content alone. Preserve explicit statuses from source feedback; when a saved mark has no status, use `unrated` for both news/daily reports and reader/paper reports.
- Do not own paper/news domain logic, explanations, citations, or source-map interpretation.
- Browser-local recovery may protect auto-saved marks and current form state from accidental refresh or tab closure, but it is not a portable or profile-level backup. Keep download/copy explicit and visible.
- Namespace recovery by a source fingerprint, never by an absolute local path, and fail visibly when browser storage is unavailable or full.
- Do not write browser-recovered feedback into `.agents`, generated HTML, or a learner profile automatically.

## Reader-Skill Integration Boundary

`reader-skill` should pass reader-specific body content and metadata into this utility instead of growing duplicate HTML/CSS/JS. In that integration:

- `reader-skill` owns Markdown parsing, bilingual block semantics, source anchors, concept/profile matching, and translation validation.
- `lean-html-skill` owns reusable page chrome, shared feedback forms, copy/download controls, localStorage/browser-memory behavior, and common status/question UI.
- Existing `reader-skill/scripts/markdown_reader_to_html.py` may remain as a compatibility wrapper while reusable HTML pieces are migrated here incrementally.
- New feedback export behavior for reader HTML should be implemented here first, then called from `reader-skill`.
- Shared recovery stores an internal versioned envelope containing saved items, an optional unfinished draft, timestamps, and a paper fingerprint. It must not change the exported feedback-v2 schema.
- A successful download or clipboard copy may offer to clear the browser recovery copy; clipboard fallback alone is not a successful copy and must never trigger clearing.
- Shared feedback UI owns the 250 ms debounced autosave controller, selection-adjacent quick-status toolbar, five-second undo notice, and visible saving/failure/export states. Status choices flush immediately; text/select fields debounce; page hide and unload flush pending work. Merely selecting text or opening the editor must not create an item. Collapsing or clearing the selection must dismiss the toolbar and discard its stale target, while interaction with the toolbar must retain the captured target until the chosen action completes.
- Reader detail editing uses the existing right utility pane instead of covering the article; Contents and Feedback alternate there. On narrow screens use a bounded bottom drawer. Article selection must remain available while the editor is open, and only Esc or the explicit close button dismisses it.
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

For reader HTML integration, domain skills should run the shared contract validator before reporting success. The contract rejects missing MathJax, missing feedback close handlers, missing copy fallback, source-page links polluted by generated markup, Algorithm summaries, missing knowledge-mark metadata, and reader-notes structure pollution. For full PDF readers it also rejects missing source/article/Contents pane ordering, inaccessible resize/collapse/restore controls, and annotation layouts that can permanently cover translated content.

## Resources

- `scripts/lean_html.py`: CLI utility for post-processing HTML reports with a feedback2 panel.
- `scripts/feedback_recovery.py`: shared SHA-256-namespaced browser recovery runtime for saved feedback and unfinished drafts.
- `references/cosmic-sci-fi-design-system.md`: visual-only Cosmic Sci-Fi Product Design System layer.
- `references/feedback2-contract.md`: JSON shape and integration rules for second-pass feedback.
