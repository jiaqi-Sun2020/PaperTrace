---
name: lean-html-skill
description: Render or post-process shared standalone HTML layers for PAPER skills, including compact report shells, reusable embedded CSS/JS, and manual feedback export panels that produce reader_feedback2.json or news_feedback2.json. Use when reader-skill, read-feedback-skill, ai-quantum-news-briefing, or another PAPER skill needs HTML output, interactive concept/freeform annotation, copy/download feedback JSON, or wants to avoid duplicating HTML/feedback UI logic inside domain-specific skills.
---

# Lean HTML Skill

## Purpose

Keep HTML rendering concerns out of domain skills. Paper/news skills should prepare structured data and source-grounded content; this utility owns shared standalone HTML behavior, especially manual feedback export.

Use this skill when a PAPER skill needs:

- a standalone HTML artifact with embedded CSS/JS;
- a shared reader/report HTML shell for domain-specific body content;
- a reusable second-pass feedback panel for an existing HTML report;
- `news_feedback2.json` or `reader_feedback2.json` export from an HTML page;
- consistent “HTML page collects feedback, but never writes `.agents` directly” behavior.

## Boundary

- Do not mutate `.agents` or `knowledge_profile.json`.
- Do not decide learner status. Preserve statuses from source feedback; collect explicit user marks only.
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
python C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json>
```

Write to a separate file:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <feedback.json> --output <report_interactive.html>
```

The script detects news feedback and exports `news_feedback2.json`; otherwise it exports `reader_feedback2.json`.

## Integration Pattern

Domain skills should follow this split:

1. Build structured content: concepts, sections, source titles/URLs, excerpts, profile status, explanation cards.
2. Render or provide the domain-specific body. For example, `reader-skill` owns bilingual source blocks, and `read-feedback-skill` owns the layered news knowledge map.
3. Use this utility for reusable standalone HTML shell behavior and shared annotation/export controls.
4. Tell the user the HTML only collects feedback; profile updates still require `reader-learner` or `ai-quantum-news-briefing/scripts/import_news_feedback.py`.

For reader HTML integration, domain skills should run the shared contract validator before reporting success. The contract rejects missing MathJax, missing feedback close handlers, missing copy fallback, source-page links polluted by generated markup, Algorithm summaries, missing knowledge-mark metadata, and reader-notes structure pollution.

## Resources

- `scripts/lean_html.py`: CLI utility for post-processing HTML reports with a feedback2 panel.
- `references/feedback2-contract.md`: JSON shape and integration rules for second-pass feedback.
