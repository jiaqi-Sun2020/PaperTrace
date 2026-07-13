# Project Context

- Project root: `C:\Users\SSS\Desktop\PAPER`
- Last reviewed: 2026-07-13

## Summary

`PAPER` is a local academic-paper workspace. It stores PDF/HTML literature by year, topic, and reading state, and it includes a local Codex skill chain for full-paper Chinese-English reading:

1. `nature-reader` creates source-grounded bilingual Markdown reader bundles from papers. The `**中文:**` field must be faithful translation, not paraphrase, summary, or reading scaffold, and `**注释:**` should carry logic, knowledge-point, formula, figure, and reading guidance.
2. `reader-skill` converts completed bundles into `reader_interactive.html` and rejects draft/paraphrase Chinese columns by default. Incomplete bundles must be fixed before HTML generation.
3. `reader-learner` imports user feedback from HTML or natural language, updates `.agents/reader-learner/knowledge_profile.json`, and projects every stable profile record into the persistent `.agents/wiki/` Obsidian vault.
4. `read-feedback-skill` generates source-grounded context packs, baseline Markdown/HTML explanations, and final research deep-dive reports from exported feedback, the updated learner profile, and the reader bundle source map.
5. `ai-quantum-news-briefing` creates source-grounded AI/quantum daily or multi-day briefings, can render them as lightweight feedback HTML, and can import explicit news-reading feedback into the same learner profile.
6. `chat-knowledge-profile` imports local ChatGPT/GPT/Claude/Deepseek conversation exports through a staged `collect -> extract -> propose -> apply` workflow. It writes bounded evidence events, `conversation_summaries.json`, profile candidates, and strict `reader-learner` handoff patches so prior conversations can initialize or extend the learner/person profile without unreviewed mutation.
7. `demo-skill` turns verified README/AGENTS contracts into structurally equivalent Chinese and English project pages centered on three pipelines. The bundled PAPER pages use static semantic HTML with GSAP + ScrollTrigger/Lenis progressive enhancement and reduced-motion fallback.

The current learner profile exists and contains concepts from the paper `Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm`. It uses learner schema v2, which separates stable concept profiles from raw feedback events, source metadata, and the review queue.

## Detected Stack

- Python scripts for reader conversion, AI/quantum briefing feedback HTML, news-feedback normalization, and learner profile updates.
- Python scripts for chat conversation import staging, conversation summaries, strict handoff generation, and profile patch application.
- Markdown skills and documentation.
- PDF/HTML corpus data.

## Important Entry Points

- `README.md`
- `.agents/README.md`
- `skills/nature-reader/SKILL.md`
- `skills/reader-skill/SKILL.md`
- `skills/reader-learner/SKILL.md`
- `skills/read-feedback-skill/SKILL.md`
- `skills/ai-quantum-news-briefing/SKILL.md`
- `skills/utils/chat-knowledge-profile/SKILL.md`
- `skills/utils/chat-knowledge-profile/scripts/init_knowledge_profile.py`
- `skills/utils/demo-skill/SKILL.md`
- `skills/utils/demo-skill/scripts/create_demo.py`
- `demo.html`
- `demo-en.html`
- `.agents/reader-learner/knowledge_profile.json`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/paper.md`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/reader_interactive.html`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/feedback_explanations.md`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/feedback_explanations.html`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/feedback_research_context.md`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/feedback_research_deep_dive.md`
- `2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/feedback_research_deep_dive.html`

## Main User Workflow

1. Start with a PDF.
2. Use `nature-reader` to generate `paper.md`, `source_map.json`, `translation_notes.md`, and `assets/`.
3. Complete faithful Chinese translations and useful logic/knowledge notes directly as Codex; extraction-only placeholders do not complete the pipeline, and missing external translation tools are not blockers.
4. Reconstruct figures/tables as cards or semantic tables, reconstruct key formulas as LaTeX, and replace generic notes with block-specific reading guidance.
5. Use `reader-skill` to generate `reader_interactive.html` only after faithful translation and structural validation pass. If the bundle is incomplete, finish translation/structure first.
6. Read the HTML, click highlighted concepts or use free annotation, and click `Save mark` for each feedback item. Saved annotations appear as badges near the source block and in a deletable list inside the feedback panel.
7. At the end of the reading session, manually export all saved feedback with `Download feedback JSON` or `Copy feedback for Codex`.
8. Use `feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>` to import the JSON into `.agents/reader-learner/knowledge_profile.json` and synchronize the persistent visible wiki.
9. Use `read-feedback-skill` to generate a context pack and baseline explanations; for derivation/research tasks, author `feedback_research_deep_dive.md/html` from the context pack rather than stopping at the baseline report.
10. Regenerate HTML so future readings highlight concepts based on the updated profile.

## AI + Quantum News Workflow

1. Use `skills/ai-quantum-news-briefing` for current AI/model/industry/regulation/academic/quantum news requests.
2. Browse and cite current sources; state the exact date range for "today", "near three days", or other relative windows.
3. Save durable briefing artifacts under `news/<date-range>/` when producing files.
4. If the user wants interaction, create `news_feedback_config.json` and render feedback HTML with `briefing_to_feedback_html.py`.
5. The user clicks concept chips or freeform annotations, clicks `Save mark`, then exports with `Download JSON` or `Copy for Codex`.
6. Import exported `news_feedback.json` with `skills/reader-learner/scripts/feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>`; it retains the news normalizer and strict profile import before synchronizing the visible wiki.

## Chat Conversation Import Workflow

1. Save or export ChatGPT/GPT/Claude/Deepseek conversations as local `.txt`, `.md`, `.html`, or `.json` files. Do not depend on share URL fetching for reproducibility.
2. Run `skills/utils/chat-knowledge-profile/scripts/init_knowledge_profile.py collect` to write `sources.jsonl`, `events.jsonl`, `conversation_summaries.json`, and `manifest.json` under `.agents/reader-learner/imports/chat_sessions/`.
3. Run `extract` to generate `profile_candidates.json` with concept-status, learning-preference, research-interest, workflow-preference, project-rule, and writing-style candidates.
4. Run `propose` against `.agents/reader-learner/knowledge_profile.json` to create `profile_patch.json`.
5. Review the patch. Only then run `apply --backup`, which sends concept-status candidates through strict `reader-learner` validation and writes non-concept user traits under `person_profile`.

## Bilingual Project Demo Workflow

1. Read the root `AGENTS.md`, each canonical `.agents` document it requires, the root `README.md`, and the source files that own the three selected pipelines.
2. From the project root, run `python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .`; use `--force` only after explicitly approving replacement.
3. Reconcile both pages with the verified pipeline stages, handoffs, outputs, and hard gates. Keep the Chinese and English information architecture equivalent.
4. Test desktop `1440x1024`, mobile `390x844`, language switching, reduced motion, horizontal overflow, and console output.
5. Publish only `demo.html`, `demo-en.html`, and intentional `skills/utils/demo-skill/` files. Exclude `.design/`, screenshots, browser profiles, QA scratch data, credentials, and unrelated dirty-worktree changes.

## Feedback Persistence Model

Interactive reader HTML does not automatically write to `.agents`. It collects feedback in browser memory during the current page session. The user must manually export/copy feedback before refreshing or closing the page, then import it with `reader-learner` or ask Codex to process the copied payload.

AI/quantum news briefings update the learner profile only from explicit user feedback or an explicit request to record exposure-only keywords. News exposure alone should become `unrated`, not `known`, `unknown`, `learning`, or `mastered`.

Chat conversation imports update the learner/person profile only through a reviewed `profile_patch.json`. Concept exposure from chat alone should remain `unrated` unless the user explicitly expressed understanding or confusion.

## Credential Safety

The learner profile is the only long-term personal data file that this workflow intentionally reads or updates. Do not open, print, copy, summarize, upload, or modify suspected key/password/token/credential files.

## Translation Safety

Do not present `中文译意`, `非逐句精翻`, paragraph summaries, terminology hints, or `待忠实翻译` placeholders as final Chinese-English reader output. If a reader bundle is incomplete, regenerate faithful translations and structural cards first; do not produce preview HTML.

## Current Known Reader Bundle

```text
2026/7/Many-Body Time Evolution from a Correlation-Efficient Quantum Algorithm_reader/
|-- paper.md
|-- source_map.json
|-- translation_notes.md
|-- reader_interactive.html
`-- assets/
```

## Open Context Questions

- Confirm whether future generated reader bundles should always use `_reader` suffix.
- Confirm whether generated HTML should default to CDN MathJax or a local MathJax file for offline reading.
