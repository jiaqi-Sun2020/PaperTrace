# Agent Instructions

- Project root: `D:\AI\PaperTrace`
- Agent context directory: `.agents/`
- Learner memory directory: `.agents/reader-learner/`
- Private teaching workspace: `.agents/adaptive-teach/`

## Operating Rules

- Treat this project as a local research-paper library plus an AI-agent skill chain for bilingual reading, AI/quantum news briefings, and learner-profile iteration.
- Treat AI/quantum daily briefings as a second entry point into the same learner-profile system, not as a separate memory store.
- Prefer verified repository files over chat history.
- Do not fabricate paper metadata, commands, skill behavior, or learner-profile facts.
- Preserve original PDFs and source reader bundles unless the user explicitly asks to reorganize or overwrite them.
- Keep the roles inside `.agents/` clear:
  - root Markdown files are project-agent documentation;
  - `reader-learner/knowledge_profile.json` is user learning data.
- Treat `reader-learner/knowledge_profile.json` as schema v2 learner memory: stable concept IDs belong in `concepts`, raw feedback belongs in `events`, source metadata belongs in `sources`, and scheduling belongs in `review_queue`.
- Do not store full selected text, long sentence excerpts, or user questions as concept keys.
- Use `reader-learner` scripts or explicit user direction before mutating `.agents/reader-learner/knowledge_profile.json`.
- Except for permitted personal learner-profile reads/updates, do not open, print, copy, summarize, upload, or modify any file that appears to contain keys, passwords, tokens, credentials, API secrets, certificates, private keys, cookies, or session data.
- Remember that interactive HTML feedback is not auto-persisted. It exists in page memory until the user clicks `Download feedback JSON` or `Copy feedback for Codex`.
- For document/code edits, keep changes tightly scoped and verify with the smallest relevant command.
- For generated reader outputs, report exact output paths and warnings.

## Four Primary Pipelines — Never Merge Them

PaperTrace has exactly four primary end-to-end pipelines in its project/demo taxonomy:

| Pipeline | Input and owner | Internal states | Terminal completion boundary |
|---|---|---|---|
| 1. Paper Reader HTML | PDF/DOI/source paper; `nature-reader` + `reader-skill` | raw evidence, `paper.md`, `source_map.json`, assets, completion ledger, `reader_wiki/` | `reader_interactive.html` exists and the publishing adversarial HTML audit passes |
| 2. AI + Quantum Daily Briefing Release | current signals/sources; `ai-quantum-news-briefing` | candidate pool, academic/social evidence, Markdown draft, config, staging run | `daily_pipeline.py run -> verify -> finalize -> verify` passes and publishes briefing HTML plus the required feedback/manifest/index release set |
| 3. Local Chat-to-Profile Import | local ChatGPT/GPT/Claude/Deepseek exports; `chat-knowledge-profile` + `reader-learner` | collected events/summaries, candidates, unapplied patch | a human-reviewed `profile_patch.json` is applied with backup through strict profile validation |
| 4. Adaptive Teaching Decision & Evidence Loop | explicit teaching request plus schema-v2 profile/Mission; `adaptive-teach` + `reader-learner` | analysis, one-topic decision, diagnostics, private session, Markdown/HTML lesson, unimported feedback | lesson requests end at a validated single-topic session; the full evidence-return loop ends only after actual performance becomes validated `teaching_feedback.json` and is imported through backed-up atomic `reader-learner` mutation |

Do not call a reader bundle the result of Pipeline 1, a candidate/config the result of Pipeline 2, extracted candidates the result of Pipeline 3, or lesson exposure/page views the evidence completion of Pipeline 4. Reader/news feedback imports and Visible Wiki projection remain shared downstream workflows; teaching feedback import is the guarded return stage of Pipeline 4.

## Project-Specific Boundaries

### End-to-End PDF Trigger

The root `AGENTS.md` is the single source of truth for the natural-language PDF batch trigger, persistent goal, controller continuation contract, and allowed terminal blockers. Do not duplicate that state machine here. Operational commands and repair/verification sequences live in `RUNBOOK.md`; data and artifact contracts live in `CONFIG_SPEC.md`.

- PDF files and topic/year folders are source corpus data. Avoid bulk renames, moves, deletes, or compression without approval.
- `*_reader/` folders are internal generated reader workspaces. They may be regenerated, but preserve `paper.md`, `source_map.json`, and `translation_notes.md` unless replacing them intentionally. For Pipeline 1, the workspace itself is never the requested terminal result.

### Ownership

- `nature-reader` owns immutable paper evidence and working Markdown; `reader-skill` owns normalized reader structure and the formal HTML terminal stage.
- `reader-learner` is the sole profile mutator. It validates and normalizes feedback before a backed-up atomic replacement; reader/news/teaching feedback files are handoffs, not long-term memory.
- `adaptive-teach` may read the profile and create one-topic teaching decisions and feedback handoffs, but cannot mutate the profile or duplicate projection logic.
- `ai-quantum-news-briefing` owns briefing collection, ranking, Delta compaction, release, and news-feedback handoff.
- `lean-html-skill` owns the reusable HTML shell and feedback UI; `chat-knowledge-profile` owns reviewable collect/extract/propose/apply imports; `demo-skill` owns the verified bilingual project demo.

### Reader Completion Contract

- Treat UTF-8 Chinese integrity, source anchors, bilingual LaTeX alignment, figures/tables/algorithms, and block-specific notes as hard evidence gates. Exact schemas, middle-layer files, commands, and repair sequences live in `CONFIG_SPEC.md` and `RUNBOOK.md`.
- Generate formal HTML only from a passing normalized `reader_wiki/` layer. Extraction drafts, placeholders, caption-only cards, raw formula noise, and failed structure reports are never publishable results.
- The active primary model must directly author every Chinese block, block-specific note, and LaTeX reconstruction for a requested formal reader; do not delegate those fields to local translators, secondary models, or scripts.
- `reader_interactive.html` is complete only when content, navigation, feedback fallback, learner annotations when available, and the adversarial HTML audit all pass.

### Daily Briefing Completion Contract

- Never infer mastery from exposure. Automatic concepts start as `unrated`; only explicit user evidence can set `known`, `mastered`, `learning`, or `unknown`.
- Run `news-ranker-v1` after evidence admission and before Delta compaction. Select 7–8 academic papers and 10–14 social items (target 12) under the quota/diversity contract in `CONFIG_SPEC.md`; preserve score components, selection trace, and exclusions.
- Academic records must be distinct paper-level evidence with primary URLs and fingerprints. Social selection must retain source-class, organization, topic, and corroboration evidence. Search pages, duplicates, candidate-only records, and venue landing pages cannot inflate delivery.
- The release boundary remains `daily_pipeline.py run -> verify -> finalize -> verify`; staging cannot update the story index. Publication requires the complete Markdown/HTML/feedback/config/manifest/index-update set, identity parity, safe sources, UTF-8 and Chinese-analysis audits, and an idempotent index upsert.
- Keep `facts`, `judgment`, and `relevance` in Chinese by default while preserving precise proper nouns. The HTML must derive runtime items from canonical `sections`, support feedback export before marking, and preserve the default-unrated baseline.

## Persistent Visible Wiki

- `.agents/wiki/` is a separate, persistent human-facing Obsidian vault. It may contain only curated knowledge-layer pages and generated navigation/maps.
- Do not move PDFs, raw source text, reader bundles, feedback/events, logs, pipeline data, or `knowledge_profile.json` into `.agents/wiki/`.
- `knowledge_status` in a public concept must be projected from the profile exactly; exposure never implies `known` or `mastered`.
- Keep `source_refs` pointed at public source-summary pages and reserve `profile_source_refs` for internal `src-*` matching. Never put absolute local paths or raw feedback payloads into a public page.
- Use `feedback_visible_wiki_pipeline.py sync` to project every stable profile concept and every profile source into `.agents/wiki/`; use `maps/Profile Coverage.md` to account for raw records that intentionally stay hidden.
- For reader/news/teaching feedback, use `feedback_visible_wiki_pipeline.py reader-feedback`, `news-feedback`, or `teaching-feedback`. Each command must finish the strict importer and its profile backup before an applied visible-Wiki sync.
- Before reporting a visible-Wiki change, run `lint_visible_wiki.py --strict --require-profile-coverage` from the project root.

## Commands And Verification

Use `RUNBOOK.md` as the single command and verification reference. Update that file when an entry point, option, or required check changes; keep this file limited to durable ownership, safety, and completion boundaries.

## Approval Rules

Ask before:

- deleting or moving PDF corpus directories;
- overwriting `.agents/reader-learner/knowledge_profile.json` wholesale;
- running long OCR, large PDF extraction, model downloads, or network-heavy tasks;
- changing the semantics of learner status values.

Never open, print, copy, summarize, upload, or modify suspected credential material. This includes files or paths containing names such as `.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, cookies, or session stores.

## GitHub 发布安全

只发布可复现的代码、公开文档、测试和明确允许的示例资产。绝不上传 `.agents/reader-learner/`、`.agents/adaptive-teach/`、`.agents/wiki/`、原始论文/reader bundle、浏览器与 IDE 状态、Cookie/会话、机器本地配置、数据库或本地生成音视频。提交前必须查看 `git status --short` 和暂存区 diff，并按文件路径显式暂存；混合工作区中禁止使用 `git add -A`。`.gitignore` 只防止新的误提交，不能撤销已跟踪的敏感内容；发现已跟踪的个人或凭据数据时，停止发布并先取得用户确认。
