# Architecture

- Project root: `C:\Users\SSS\Desktop\PAPER`
- Last reviewed: 2026-07-13

## Top-Level Structure

```text
PAPER/
|-- 2024/
|-- 2025/
|-- 2026/
|-- Optical/
|-- Quantum Deep Leaning/
|-- interset/
|-- news/
|-- readed/
|-- 综述文章/
|-- 王老师/
|-- skills/
`-- .agents/
```

## Corpus Directories

- `2024/`, `2025/`, `2026/`: papers organized by year and sometimes month.
- `Optical/`: optics and photonics papers.
- `Quantum Deep Leaning/`: quantum deep learning / quantum machine learning papers. The directory name is spelled as it exists on disk.
- `interset/`: interest collection.
- `news/`: generated AI/quantum daily or multi-day briefing artifacts, including Markdown briefings, feedback HTML, feedback configs, and exported feedback JSON.
- `readed/`: papers already read or previously processed.
- `综述文章/`: review papers.
- `王老师/`: small named collection.

## Skill Directories

```text
skills/
|-- nature-reader/
|-- reader-skill/
|-- reader-learner/
|-- read-feedback-skill/
|-- ai-quantum-news-briefing/
`-- utils/
    |-- chat-knowledge-profile/
    |-- demo-skill/
    `-- lean-html-skill/
```

- `nature-reader`: source-paper to bilingual Markdown bundle with faithful `中文` translations plus logic, knowledge-point, formula, figure, and reading guidance in `注释`. Codex performs the translation pass directly by default; external translation tools are optional aids, not prerequisites.
- `reader-skill`: reader-specific Markdown parsing, translation validation, source anchors, bilingual body semantics, and learner-profile annotation metadata. It may keep compatibility HTML wrappers, but reusable HTML shell, feedback UI, and export controls should move to `lean-html-skill`. `reader_interactive.html` is only for completed translated readers; incomplete bundles must be fixed before HTML generation.
- `reader-learner`: learner profile import/update commands plus `feedback_visible_wiki_pipeline.py`, which invokes the strict reader/news importer and then projects all stable profile concepts and concise source summaries into `.agents/wiki/`.
- `read-feedback-skill`: post-reading context packs, baseline Markdown/HTML explanations, and research deep-dive reports from feedback JSON, learner profile, and source map.
- `ai-quantum-news-briefing`: source-grounded AI/quantum briefings, lightweight briefing-reader HTML, concept/freeform news feedback export, and explicit news-feedback bridge into the learner profile.
- `utils/lean-html-skill`: shared standalone HTML shell, reusable HTML components, feedback UI, browser-memory/localStorage behavior, and feedback2 export layer for domain skills, including future reader HTML output work.
- `utils/chat-knowledge-profile`: reviewable chat-session import layer for initializing or extending `knowledge_profile.json` from exported ChatGPT/GPT/Claude/Deepseek conversations through sources, bounded evidence events, `conversation_summaries.json`, candidates, strict `reader-learner` handoffs, and patches.
- `utils/demo-skill`: source-traceable bilingual project-demo layer. It stores the current PAPER Chinese/English three-pipeline HTML templates and a deterministic no-overwrite materializer; copied pages must be reconciled with the target repository's README/AGENTS contracts before publication.
- News report visualization: `read-feedback-skill` owns the layered news knowledge map; `ai-quantum-news-briefing` supplies category/source/status fields, `reader-learner` supplies profile status, and `lean-html-skill` only appends feedback2 controls.

## Agent Data

- `.agents/*.md`: project documentation for future AI agents.
- `.agents/reader-learner/knowledge_profile.json`: long-term learner profile. Schema v2 splits stable `concepts`, raw `events`, deduplicated `sources`, and `review_queue`.
- `.agents/wiki/`: persistent human-facing Obsidian knowledge layer. It projects every stable profile concept and each profile source as curated concepts/source summaries plus maps; it must not become a storage location for raw source or learner-event records.
- `.agents/reader-learner/obsidian-vault/`: generated profile projection retained for compatibility and audit work. It is not the persistent curated vault.

## Generated Reader Bundle Shape

```text
<paper-name>_reader/
|-- paper.md
|-- source_map.json
|-- translation_notes.md
|-- reader_wiki/
|   |-- reader_manifest.json
|   |-- concept_ledger.json
|   |-- formula_ledger.json
|   |-- figure_table_ledger.json
|   |-- algorithm_ledger.json
|   |-- claim_contribution_ledger.json
|   |-- annotation_metadata.json
|   |-- structure_validation_report.json
|   `-- normalized_reader.md
|-- reader_interactive.html
|-- feedback_explanations.md
|-- feedback_explanations.html
|-- feedback_research_context.md
|-- feedback_research_deep_dive.md
|-- feedback_research_deep_dive.html
|-- assets/
|   |-- fig*.png
|   |-- table*.png
|   `-- source_pages/
```

## Module Boundaries

- `nature-reader` produces `paper.md` and source-grounded assets; do not make it responsible for learner profile mutation or HTML feedback UI.
- `reader-skill` reads learner profile and prepares reader-specific annotation metadata; do not make it write `.agents`, translate paper text, or grow reusable HTML/feedback UI that belongs in `lean-html-skill`. It must not turn extraction-only drafts or placeholder translations into `reader_interactive.html`.
- `reader-learner` writes `.agents/reader-learner/knowledge_profile.json`; keep this as the single owner of learner profile mutation.
- `read-feedback-skill` reads feedback/profile/source context and writes report artifacts in the reader directory; do not make it mutate `.agents`.
- `ai-quantum-news-briefing` may normalize explicit news feedback, but it delegates profile mutation to `reader-learner`.
- `lean-html-skill` owns reusable HTML shell/post-processing, shared feedback UI, browser-memory/localStorage behavior, and feedback2 export controls; domain skills should call it instead of embedding new shared HTML UI logic.
- `chat-knowledge-profile` owns chat conversation import staging. It generates strict concept-status handoff feedback for `reader-learner`, including `source_anchor`, `concept_type`, and bounded evidence; it should not silently overwrite the learner/person profile without a reviewable patch and backup.
- `demo-skill` owns project-presentation templates and their content/interaction audit. It does not own reader generation, profile mutation, news publication, or shared application data contracts.
- Keep news knowledge-map layout out of `knowledge_profile.json`; store evidence/status in the profile, and render layout only in HTML reports.
- News feedback and paper reader feedback share `.agents/reader-learner/knowledge_profile.json`; do not create a separate long-term news memory file unless the user changes the architecture.
- Project-level README and `.agents/*.md` document workflows; they should not duplicate full paper contents.
- Translation and explanation are separate layers: faithful translation belongs in `中文`; logic, knowledge summaries, formula checks, and annotation guidance belong in `注释`.
- Figure/table extraction and formula reconstruction are structural reader layers, not optional decoration. A final reader needs inspectable figure/table cards, semantic tables where appropriate, and LaTeX-readable formulas.
- Algorithm extraction is also a structural reader layer. A final reader needs full Algorithm cards with original and Chinese numbered steps; Algorithm summaries are invalid.
- Source Page Index links are navigation metadata, not prose. Renderers must protect them from inline math conversion and concept annotation so `href` values stay plain local paths.
- Generated reader HTML must pass both the compile-time `structure_validation_report.json` gate and the post-generation adversarial HTML audit before it is considered complete.
- Shared feedback UI belongs in `lean-html-skill` and must include a clipboard fallback textarea for exported JSON.

## Generated Or Sensitive Areas

- Treat `*_reader/` folders as generated-but-important reading artifacts.
- Treat `.agents/reader-learner/knowledge_profile.json` as user data; do not collapse raw questions or selected text back into concept keys.
- Treat PDFs as source corpus.
- Do not open, print, copy, summarize, upload, or modify suspected credential files. The learner profile is allowed only through the documented workflow.
- Treat `.design/`, screenshots, browser profiles, and demo QA scratch logs as local evidence, not default repository artifacts. Root `demo.html` and `demo-en.html` are intentional publishable exceptions to the root HTML ignore rule only when explicitly force-added by exact path.
