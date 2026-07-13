# Agent Context Index

- Project root: `C:\Users\SSS\Desktop\PAPER`
- Generated with: `D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill`
- Last reviewed: 2026-07-13

This directory combines project-agent context and learner memory.

Directory roles:

- `.agents/*.md`: project context for future Codex/AI-agent sessions.
- `.agents/wiki/`: persistent human-facing Obsidian knowledge layer, opened as its own vault.
- `.agents/reader-learner/knowledge_profile.json`: the user's evolving literature-reading knowledge profile. Current schema is v2: `concepts`, `events`, `sources`, and `review_queue`.
- `skills/ai-quantum-news-briefing`: AI/quantum briefing skill that can generate source-grounded briefings, render briefing feedback HTML, and normalize explicit news feedback into the same learner profile.
- `skills/utils/chat-knowledge-profile`: staged chat conversation import skill for turning local ChatGPT/GPT/Claude/Deepseek exports into bounded evidence events, conversation summaries, candidate profile signals, strict reader-learner handoffs, reviewable patches, and optional profile updates.
- `skills/utils/demo-skill`: bilingual project-demo skill that verifies README/AGENTS contracts, materializes the bundled Chinese/English three-pipeline templates, and audits the intended Git upload scope.

Recommended reading order:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `ARCHITECTURE.md`
4. `CONFIG_SPEC.md`
5. `RUNBOOK.md`
6. `DECISIONS.md`
7. `WIKI_SCHEMA.md` when the task touches `.agents/wiki/`.
8. `reader-learner/knowledge_profile.json` only when the task needs learner-profile data.

Files:

| File | Purpose |
|---|---|
| `AGENTS.md` | Stable operating rules for AI agents working in this project. |
| `PROJECT_CONTEXT.md` | Project purpose, current facts, and main workflows. |
| `ARCHITECTURE.md` | Directory map and ownership boundaries. |
| `CONFIG_SPEC.md` | Config/data surfaces and profile schema notes. |
| `RUNBOOK.md` | Verified commands and common workflows. |
| `DECISIONS.md` | Durable design choices and open questions. |
| `WIKI_SCHEMA.md` | Persistent visible-Wiki boundary, frontmatter, relation, and validation rules. |
| `reader-learner/knowledge_profile.json` | Long-term learner profile with stable concepts, raw feedback events, source index, and review queue. |

Do not treat these files as a transcript. They should summarize stable project facts, owner-confirmed rules, and current learner-state data only.

Feedback note: interactive reader HTML does not auto-write to this directory. The user must export with `Download feedback JSON` or `Copy feedback for Codex`, then import/process that feedback with `reader-learner`.

Translation note: final `reader_interactive.html` requires faithful `**中文:**` translations, useful `**注释:**` logic/knowledge guidance, strict validation, feedback UI, and learner-profile annotations when available. Do not treat `中文译意`, `非逐句精翻`, `待忠实翻译`, paragraph summaries, or reading scaffolds as valid bilingual output; do not generate preview HTML for incomplete paper readers.

Direct translation note: Codex should translate paper blocks directly by default. Do not make a local model, translation package, SDK, or network translator a prerequisite unless the user explicitly requests that tool. Missing external translation tooling must not be used as a reason to stop at an intermediate artifact when the user asked for a completed reader.

Visual/math note: final reader HTML also requires figure/table cards or semantic tables, LaTeX-readable formulas, and block-specific notes. Generic `逻辑位置` / `标注建议` scaffolds, raw formula extraction noise, and caption-only figure/table text are draft defects.

After `reader-learner` imports a feedback JSON, use `skills/read-feedback-skill` to generate `feedback_explanations.md`, `feedback_research_context.md`, and `feedback_explanations.html`. For real derivation/research work, Codex should then author `feedback_research_deep_dive.md` from the context pack and render `feedback_research_deep_dive.html`.

Credential rule: except for permitted learner-profile reads/updates, do not open, print, copy, summarize, upload, or modify any suspected key/password/token/credential file.

Daily AI/quantum briefing note: `skills/ai-quantum-news-briefing` can create source-grounded AI/quantum daily or multi-day briefings, render them as feedback HTML with concept chips and freeform annotations, and convert explicit news feedback into the same learner profile through `scripts/import_news_feedback.py`. News exposure alone should be imported as `unrated`; do not infer `known`, `unknown`, `learning`, or `mastered` without explicit user feedback. The end-to-end briefing contract finishes at the interactive HTML reader plus full feedback JSON, not at candidate/config generation; use `C:\Users\SSS\Desktop\PAPER\news\2026-07-07_to_2026-07-09` as the sample output layout. Publish through `daily_pipeline.py run`, `verify`, and `finalize`; index mutation is forbidden before final verification.

Chat conversation import note: use `skills/utils/chat-knowledge-profile` only with local `.txt`, `.md`, `.html`, or `.json` ChatGPT/GPT/Claude/Deepseek exports. The pipeline is `collect -> extract -> propose -> apply`; `collect` also writes `conversation_summaries.json`. Review `profile_patch.json` before applying, and use `--backup` when mutating `knowledge_profile.json`. Share URLs should be copied or exported locally first.

Project demo note: use `skills/utils/demo-skill` for a bilingual three-pipeline project presentation. Read repository contracts before replacing the bundled PAPER-specific text; keep Chinese and English structure equivalent, preserve static/reduced-motion fallbacks, and exclude `.design/`, screenshots, browser profiles, and QA scratch files from normal publication.
