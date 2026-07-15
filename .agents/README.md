# Agent Context Index

- Project root: `D:\AI\PaperTrace`
- Generated with: `D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill`
- Last reviewed: 2026-07-14

This directory combines project-agent context and learner memory.

Canonical four-pipeline taxonomy:

1. **Paper Reader HTML:** PDF/source paper -> internal bundle/`reader_wiki` -> adversarially audited `reader_interactive.html`.
2. **AI + Quantum Daily Briefing Release:** current sources -> evidence/config/staging -> `run -> verify -> finalize -> verify` -> briefing HTML plus required feedback/manifest/index artifacts.
3. **Local Chat-to-Profile Import:** local chat exports -> collect/extract/propose -> human review -> backed-up strict apply.
4. **Adaptive Teaching Decision & Evidence Loop:** explicit teaching request -> profile-backed analysis -> one concept/mode -> short lesson -> actual performance -> validated teaching-feedback import.

Bundles, configs, staging runs, candidates, unapplied patches, lesson exposure, and page views are not terminal evidence. Reader/news feedback import and Visible Wiki sync are shared downstream workflows; adaptive teaching is Pipeline 4 and remains explicit-invocation only.

Directory roles:

- `.agents/*.md`: project context for future Codex/AI-agent sessions.
- `.agents/wiki/`: persistent human-facing Obsidian knowledge layer, opened as its own vault.
- `.agents/reader-learner/knowledge_profile.json`: the user's evolving literature-reading knowledge profile. Current schema is v2: `concepts`, `events`, `sources`, and `review_queue`.
- `.agents/adaptive-teach/`: private teaching workspace for Mission, settings, session records, diagnostics, lessons, and derived rankings. It is not a second learner profile and is Git-ignored.
- `skills/ai-quantum-news-briefing`: AI/quantum briefing skill that can generate source-grounded briefings, render briefing feedback HTML, and normalize explicit news feedback into the same learner profile.
- `skills/utils/chat-knowledge-profile`: staged chat conversation import skill for turning local ChatGPT/GPT/Claude/Deepseek exports into bounded evidence events, conversation summaries, candidate profile signals, strict reader-learner handoffs, reviewable patches, and optional profile updates.
- `skills/adaptive-teach`: explicit-invocation, profile-backed teaching decision skill. It reads the profile, selects a diagnostic/teach/review/prerequisite/transfer session, generates short lessons, and delegates validated teaching feedback to `reader-learner`.
- `skills/utils/demo-skill`: bilingual project-demo skill that verifies README/AGENTS contracts, materializes the bundled Chinese/English four-pipeline templates, and audits the intended Git upload scope.

Recommended reading order:

1. `AGENTS.md`
2. `PROJECT_CONTEXT.md`
3. `ARCHITECTURE.md`
4. `CONFIG_SPEC.md`
5. `RUNBOOK.md`
6. `DECISIONS.md`
7. `WIKI_SCHEMA.md` when the task touches `.agents/wiki/`.
8. `reader-learner/knowledge_profile.json` only when the task needs learner-profile data.
9. `adaptive-teach/TEACHING-MISSION.md` and `adaptive-teach/teaching-settings.json` only when the task is an explicit teaching request.

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
| `adaptive-teach/` | Private derived teaching state; cannot establish concept status or replace profile evidence. |

Do not treat these files as a transcript. They should summarize stable project facts, owner-confirmed rules, and current learner-state data only.

Feedback note: interactive reader HTML does not auto-write to this directory. The user must export with `Download feedback JSON` or `Copy feedback for Codex`, then import/process that feedback with `reader-learner`.

PDF bootstrap note: `skills/nature-reader/scripts/extract_pdf_bundle.py` creates immutable raw evidence and automatically materializes a UTF-8 `paper.md` working draft. The draft keeps stable source anchors and uses explicit `[translation-required]` / `[block-note-required]` markers, so it is inspectable but cannot pass completion. For a legacy raw bundle missing `paper.md`, run `materialize_reader_markdown.py <reader-dir>`; it preserves `source_map.json` and refuses to overwrite an existing reader by default. Complete every bilingual block and structural object, run the text audit and `complete_reader_bundle.py`, and only then invoke `reader-skill`.

Reader UTF-8 note: on Windows, never send Chinese Markdown through a default PowerShell code-page pipe or here-string. Use a UTF-8-safe writer or encoded payload, then run `audit_reader_text.py <paper.md>`. The completion pass applies the same audit and rejects `U+FFFD`, disallowed control characters, mojibake markers, and high-density literal `?`. If it fails, discard and rebuild the damaged working text from immutable evidence; never convert it to HTML.

Translation note: final `reader_interactive.html` requires faithful `**中文:**` translations, useful `**注释:**` logic/knowledge guidance, strict validation, feedback UI, and learner-profile annotations when available. Do not treat `中文译意`, `非逐句精翻`, `待忠实翻译`, paragraph summaries, or reading scaffolds as valid bilingual output; do not generate preview HTML for incomplete paper readers.

Direct-authorship note: the active primary model in the current user-facing session must directly author paper-block Chinese, block-specific notes, and LaTeX reconstruction. Do not delegate those semantic fields to a local model, translation package, SDK, network translator, secondary model, or script. Missing external translation tooling must not be used as a reason to stop at an intermediate artifact when the user asked for completed HTML.

Visual/math note: final reader HTML also requires figure/table cards or semantic tables, LaTeX-readable formulas, and block-specific notes. Generic `逻辑位置` / `标注建议` scaffolds, raw formula extraction noise, and caption-only figure/table text are draft defects.

Credential rule: except for permitted learner-profile reads/updates, do not open, print, copy, summarize, upload, or modify any suspected key/password/token/credential file.

Daily AI/quantum briefing note: `skills/ai-quantum-news-briefing` can create source-grounded AI/quantum daily or multi-day briefings, render them as feedback HTML with concept chips and freeform annotations, and convert explicit news feedback into the same learner profile through `scripts/import_news_feedback.py`. News exposure alone should be imported as `unrated`; do not infer `known`, `unknown`, `learning`, or `mastered` without explicit user feedback. The end-to-end briefing contract finishes at the interactive HTML reader plus full feedback JSON, not at candidate/config generation; use `D:\AI\PaperTrace\news\2026-07-07_to_2026-07-09` as the sample output layout. Publish through `daily_pipeline.py run`, `verify`, and `finalize`; index mutation is forbidden before final verification.

Chat conversation import note: use `skills/utils/chat-knowledge-profile` only with local `.txt`, `.md`, `.html`, or `.json` ChatGPT/GPT/Claude/Deepseek exports. The pipeline is `collect -> extract -> propose -> apply`; `collect` also writes `conversation_summaries.json`. Review `profile_patch.json` before applying, and use `--backup` when mutating `knowledge_profile.json`. Share URLs should be copied or exported locally first.

Project demo note: use `skills/utils/demo-skill` for a bilingual four-pipeline project presentation. Read repository contracts before replacing the bundled PaperTrace-specific text; keep Chinese and English structure equivalent, preserve static/reduced-motion fallbacks, and exclude `.design/`, screenshots, browser profiles, and QA scratch files from normal publication.
