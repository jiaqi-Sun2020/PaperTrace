# Decisions

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-07-14

## Current Decisions

| Decision | Status | Rationale |
|---|---|---|
| Use `.agents/` as the combined agent context and learner-memory directory. | active | User confirmed `.agent` and `.agents` can be merged. |
| Keep `.agents/reader-learner/knowledge_profile.json` for learner data. | active | Existing reader workflow and scripts use this path for long-term knowledge profile. |
| Split rendering and learning into separate skills. | active | `reader-skill` renders HTML and exports feedback; `reader-learner` mutates profile data. |
| Delegate reusable reader HTML output behavior to `lean-html-skill`. | active | User requested that `skills/reader-skill` hand HTML output work to `lean-html-skill` to reduce duplicate HTML/CSS/JS and feedback export logic. `reader-skill` keeps reader parsing, validation, source anchors, and annotation metadata; `lean-html-skill` owns reusable page shell, feedback UI, browser-memory behavior, and copy/download controls. |
| Reserve `reader_interactive.html` for completed translated readers. | active | User clarified that the target artifact is a translated paper with logic and knowledge-point guidance plus interactivity. Extraction-only bundles, placeholders, summaries, or reading scaffolds are incomplete intermediate states and must not produce HTML. |
| Treat the current-session primary model as the paper content author. | active | The rule is product-neutral: the active primary model directly authors Chinese blocks, block-specific notes, and LaTeX reconstruction. Offline translators, APIs, local/secondary models, and scripts are not formal content authors; missing external tooling is not a blocker. |
| Keep exactly four primary pipelines with distinct terminal gates. | active | Paper Reader HTML ends at audited `reader_interactive.html`; AI + Quantum Daily Briefing Release ends after `run -> verify -> finalize -> verify`; Local Chat-to-Profile Import ends after reviewed backed-up apply; Adaptive Teaching Decision & Evidence Loop ends a lesson request at a validated single-topic session and completes profile return only from actual performance through strict teaching-feedback import. |
| Treat figures, tables, formulas, and block-specific notes as required final-reader structure. | active | User identified that missing figure/table cards, non-LaTeX formula noise, and generic `逻辑位置` / `标注建议` scaffolds make a reader invalid even when text is translated. |
| Add `chat-knowledge-profile` for chat conversation imports. | active | User wants many chat conversation sessions to contribute to the long-term learner/person profile. The durable design is staged and reviewable: collect local exports, create `conversation_summaries.json`, extract candidates, propose a strict `reader-learner` handoff patch, then apply with backup. The design borrows ideas from ChatInsights and gpt-obsidian, but does not copy their code. |
| Keep bilingual project demos in `skills/utils/demo-skill`. | active | The user requested the current Chinese/English four-pipeline PaperTrace demo as a reusable skill. The bundled templates remain editable visual references; verified README/AGENTS contracts own the facts, generation refuses accidental overwrite, and QA/design scratch artifacts stay out of normal publication. |
| Maintain a separate curated `.agents/wiki/` knowledge layer. | active | The learner profile and generated legacy vault remain source/projection layers. `.agents/wiki/` holds stable, source-traceable concepts, entities, themes, questions, syntheses, claims, and source summaries without copying raw feedback, events, paths, or bundles. |
| Remove `read-feedback-skill` from the active architecture. | active | The four primary pipelines do not call it. Historical generated explanation artifacts may remain, but no active skill, command, ownership rule, or pipeline terminal depends on it. |
| Let AI/quantum briefing feedback share the learner profile. | active | The user wants daily briefing concepts to update the same knowledge boundary; `ai-quantum-news-briefing` generates source-grounded briefings, can render feedback HTML, normalizes explicit feedback, and delegates mutation to `reader-learner`. |
| Treat news exposure-only concepts as `unrated`. | active | Seeing a concept in a briefing is evidence of exposure, not evidence that the user understands or does not understand it. |
| Generate recurring daily briefings as delta-first reports. | active | User confirmed that repeated categories/stories across consecutive daily reports should be avoided. `news_delta.py` keeps a compact `news/_index/story_index.jsonl`, expands only new/material-update stories, and compresses or skips recently seen stories to reduce token use. |
| Use learner profile schema v2 with `concepts`, `events`, `sources`, and `review_queue`. | active | The user identified unstable concept keys, bloated notes, mixed evidence, coarse status, and missing learning scheduling; the split schema fixes those boundaries. |
| Use `nature-reader` as the internal source-grounded paper evidence stage. | active | It preserves source anchors and builds the bilingual bundle, but Pipeline 1 is not complete until `reader-skill` emits and formally audits `reader_interactive.html`. |
| Preserve PDFs as source corpus. | active | The project is a paper library; reader outputs should reference PDFs, not replace them. |
| Use feedback JSON/copy payloads rather than direct browser writes to `.agents`. | active | Static browser pages cannot safely write local project files. |
| Export reader feedback manually at the end of a reading session. | active | The HTML keeps feedback in page memory and only persists it through `Download feedback JSON` or `Copy feedback for Codex`. |
| Use MathJax for formula rendering in generated HTML. | active | Browsers do not render TeX natively; `reader-skill` can point to CDN or local MathJax. |
| Treat Algorithms as first-class reader objects. | active | Algorithm sections must be rendered like figures/tables with original numbered steps and Chinese numbered steps; Algorithm summaries are invalid formal-reader output. |
| Protect Source Page Index links from annotation and math wrapping. | active | A prior renderer regression inserted inline-math HTML into source-page `href` values, making links impossible to open. File paths and HTML attributes are now protected rendering zones. |
| Require adversarial HTML audit before reporting formal reader success. | active | Static validation plus browser-facing failure checks catch Algorithm summaries, broken source links, formula/MathJax pollution, missing concept metadata, weak concept coverage, reader-notes pollution, and feedback UI regressions. |
| Provide feedback-copy fallback text in generated readers. | active | Clipboard permissions can fail in local/browser contexts; `Copy feedback for Codex` must always expose a visible fallback textarea containing the same JSON payload. |
| Treat suspected credential files as off-limits. | active | Except for permitted learner-profile reads/updates, agents must not open, print, copy, summarize, upload, or modify key/password/token/credential material. |

## Open Questions

- Should future reader HTML default to local MathJax for offline reading?
- Should completed reader bundles use local MathJax by default when generating `reader_interactive.html`?
- Which corpus folders should be treated as immutable archives?

## Decision Update Rule

Add a new row only when the user confirms a durable project rule or when a repository change makes the decision visible from files. Do not turn one-off chat preferences into permanent project decisions without confirmation.
