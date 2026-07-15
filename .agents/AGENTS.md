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

When the user asks to read the project docs and convert all PDFs in a supplied folder into interactive HTML “一篇一篇来”, treat the wording as permission to run the entire formal reader pipeline for the whole folder. It is not a bootstrap-only request and it does not require a per-paper confirmation.

- Treat that natural-language trigger as an explicit request for persistent execution. When Codex goal tools are available, create or resume one unbudgeted active goal for the selected PDF set before the first implementation command. Keep it active while the controller says `final_response_allowed: false`; mark it complete only after every requested formal HTML and adversarial audit pass.
- The first implementation command must invoke `build_formal_reader_batch.py --agent-continuation`. Do not edit a reader bundle before observing its `agent_continuation_contract`. If no controller contract has been observed in the current turn, sending a final response is forbidden.
- Statements such as “尚未通过门禁”, “还没有可交付的 HTML”, or “当前未完成” are progress commentary only. After sending one, immediately continue tool work in the same task; never place such a statement in `final_answer` unless the controller reports one of the authorized terminal blockers.
- Determine a stable order, complete and adversarially audit one formal `reader_interactive.html`, then continue to the next PDF automatically.
- A bootstrap result of `paper_md_materialized_completion_required`, any `[translation-required]` / `[block-note-required]` marker, rotated text, missing formula reconstruction, or missing object crop is an internal current-session model work item—not a reason to stop or return a partial result.
- `complete_reader_bundle.py` only validates and writes the completion ledger. It never translates, crops figures, synthesizes table cards, or repairs Markdown. Complete these directly in `paper.md` / `assets/` first.
- Do not create a draft/preview HTML to satisfy this request. Report success only after `audit_reader_text.py`, `complete_reader_bundle.py`, `reader_wiki_compile.py`, `markdown_reader_to_html.py`, and `adversarial_html_audit.py` all pass.
- On a rerun, skip a same-source bundle only if its formal HTML and adversarial audit already pass; resume incomplete same-source bundles in place. Ask only when an existing bundle's immutable evidence belongs to a different PDF.
- After every call to `build_formal_reader_batch.py`, read the
  `agent_continuation_contract` embedded in its JSON standard output. The
  controller must not create `.reader_pipeline_runs`, `reader_batch_state.json`,
  or another batch-history/state artifact. `final_response_allowed: false` is a
  machine-readable instruction to keep working on its single `active_paper`
  and rerun its exact `next_command` in the same user task. It is never a
  reason to ask the user for “continue”.
- The controller must expose only a formal-pass prefix, at most one active
  pending/invalid paper, and untouched queued papers. A draft/progress file is
  never included in `reportable_formal_html`.
- Expected semantic completion is `action_required` with a successful default
  controller exit. Nonzero incomplete exits are reserved for `--strict-exit`
  CI use so an agent cannot confuse ordinary authorship work with a terminal
  command failure.
- For an interactive agent session, run the controller with
  `--agent-continuation` and pass its JSON through
  `reader_continuation_guard.py`. A default exit code of `0` means only that
  the checkpoint ran normally; `final_response_allowed: true` remains the sole
  permission to end the user turn.

- PDF files and topic/year folders are source corpus data. Avoid bulk renames, moves, deletes, or compression without approval.
- `*_reader/` folders are internal generated reader workspaces. They may be regenerated, but preserve `paper.md`, `source_map.json`, and `translation_notes.md` unless replacing them intentionally. For Pipeline 1, the workspace itself is never the requested terminal result.
- `extract_pdf_bundle.py` writes immutable raw evidence and automatically materializes a UTF-8 working `paper.md` with stable anchors plus explicit `[translation-required]` / `[block-note-required]` markers. It never writes HTML. For legacy raw bundles missing `paper.md`, run `materialize_reader_markdown.py <reader-dir>`; the command refuses to overwrite an existing `paper.md` unless `--force` is explicitly supplied.
- Treat Windows Chinese-text emission as a reader hard gate. Never pipe Chinese literals through a default PowerShell code-page here-string into Python or another writer. Write Markdown/JSON/HTML as UTF-8 from a UTF-8-safe file or encoded payload, then reject `U+FFFD` and high-density literal `?` in visible Chinese text before `complete_reader_bundle.py` or HTML generation. If this gate fails, discard and rebuild the damaged working `paper.md`; never repair it by retaining `?` placeholders.
- Run `audit_reader_text.py <paper.md>` before completion. `complete_reader_bundle.py` enforces the same integrity audit and must fail before writing a completion ledger when reader text contains replacement characters, disallowed controls, mojibake markers, or question-mark replacement patterns.
- Formal reader HTML must be generated from the normalized llm-wiki layer under `reader_wiki/`, not directly from dirty extraction text. The required middle-layer files are `reader_manifest.json`, `concept_ledger.json`, `formula_ledger.json`, `figure_table_ledger.json`, `algorithm_ledger.json`, `claim_contribution_ledger.json`, `annotation_metadata.json`, `structure_validation_report.json`, and `normalized_reader.md`.
- If `structure_validation_report.json` fails, do not write or report `reader_interactive.html`. Fix the bundle first.
- `skills/reader-skill` owns reader-specific Markdown parsing, translation validation, source anchors, and learner-profile annotation metadata; reusable HTML shell, feedback UI, and export controls should be delegated to `skills/utils/lean-html-skill`.
- `skills/reader-learner` owns learner profile mutation.
- `skills/adaptive-teach` is an explicit-invocation teaching decision layer: it may read the profile, identify explicit weakness versus evidence gaps and due reviews, choose a single short session, and create a strict teaching-feedback handoff. It must not mutate the profile directly or duplicate profile validation, normalization, backup, atomic writes, or Visible Wiki projection.
- `skills/reader-learner` must validate feedback schema, normalize concept names/aliases/notes, fail fast on mojibake/control characters/HTML fragments, and atomically replace `knowledge_profile.json` only after validation succeeds.
- `skills/ai-quantum-news-briefing` owns AI/quantum briefings and may bridge explicit news feedback into `reader-learner`.
- `skills/utils/lean-html-skill` owns shared HTML shell/post-processing, reusable feedback UI, browser-memory/localStorage behavior, and feedback2 export controls. Prefer calling it when a domain skill needs reusable HTML/feedback UI, including future `reader-skill` HTML output work.
- `skills/utils/chat-knowledge-profile` owns reviewable initialization/extension of the learner/person profile from exported ChatGPT/GPT/Claude/Deepseek conversation files. It must use collect/extract/propose/apply stages, write `conversation_summaries.json`, generate strict `reader-learner` handoffs, and avoid direct unreviewed profile mutation.
- `skills/utils/demo-skill` owns bilingual project demo generation from verified repository contracts. It may adapt the bundled GSAP/ScrollTrigger templates, but it must not invent pipeline stages, mutate business data, or publish design/QA scratch artifacts by default.
- News explanation HTML should show the knowledge boundary as a layered map: `Source Claim -> Theme Clusters -> Mechanism / Evidence -> Profile Loop`, with category cards and status bars instead of one long horizontal node chain.
- For news briefings, never infer mastery from exposure alone. Use `unrated` for exposure-only keyword records, and use `known` / `mastered` / `learning` / `unknown` only when the user explicitly marks or states that status.
- For recurring daily briefings, use `news/_index/story_index.jsonl` and `skills/ai-quantum-news-briefing/scripts/news_delta.py` so the report is delta-first: expand only new/material-update stories, compress or skip recently seen stories, and keep category as an item tag rather than repeating full category sections.
- A daily briefing is complete only after the end-to-end artifact set exists: Markdown briefing, interactive HTML reader, full default-`unrated` feedback JSON, delta config, and updated `news/_index/story_index.jsonl`. The final reader-facing artifact is `briefing_reader_YYYY-MM-DD.html`, not the candidate pool or config alone. Use `D:\AI\PaperTrace\news\2026-07-07_to_2026-07-09` as the canonical sample layout for the daily/multi-day briefing output contract.
- The daily release boundary is `daily_pipeline.py run -> verify -> finalize -> verify`: staging and verification must finish before the story index is atomically upserted. Shared contract normalization, safe HTTPS sources, evidence-backed venue checks, HTML/feedback identity parity, and idempotent same-day index updates are mandatory.
- Daily pipeline runs default to `academic_delivery.required=true` with `minimum_items=5`. The final delta config must include a dedicated academic-research section with five formal venue/arXiv items plus audited `academic_search` evidence across PRL, PRA, PRX, Nature, Science, ICLR, CVPR, ICML, NeurIPS, ACL, Quantum Journal, and arXiv. A quantum company/platform update is context, not academic delivery. Any opt-out must set `required=false` and a concrete `no_signal_reason`.
- Daily `facts`, `judgment`, and `relevance` must be Chinese analysis by default. Keep source titles, model names, DOI, arXiv IDs, and other proper nouns in their precise original form where useful.
- A five-paper academic delivery means five distinct paper-level records with a primary article/DOI/preprint URL and individual evidence fingerprints; a venue landing page, search page, duplicate story, or company post cannot inflate the count. Papers included from a wider evidence window must retain their actual publication date and be visibly labeled as academic context rather than current-window news.
- The news HTML must derive its runtime item map from canonical `sections`, initialize every automatic feedback item as `unrated`, and make `Download JSON` work before any `Save mark`. Editing an automatic concept changes its baseline entry; deletion restores the unrated baseline rather than removing it.
- Daily briefing text has a strict UTF-8 integrity boundary: read configs/index with `utf-8-sig`, write JSON/Markdown/HTML as UTF-8 with `ensure_ascii=False`, reject `U+FFFD` and high-density literal `?` in human text, and never build Chinese configs through a default PowerShell code-page here-string. A corrupt historical summary may be omitted during delta compaction but must never leak into new HTML. Final visible HTML must pass the encoding audit before publication.
- If the encoding or Chinese-analysis audit fails, the pipeline must not stage, finalize, or update `story_index.jsonl`; rebuild the damaged UTF-8 input and rerun the complete validation chain.
- `skills/nature-reader` owns the internal full-paper evidence/Markdown stage; `skills/reader-skill` owns the formal HTML terminal stage. Together they implement Pipeline 1.
- `skills/nature-reader/scripts/complete_reader_bundle.py` is the official completion pass from extracted/draft reader bundle to completed reader bundle. Run it before `markdown_reader_to_html.py` when `paper.md` still contains placeholders, formula extraction noise, missing figure/table cards, or incomplete `source_map.json` translations. This pass must fix the bundle; it must not bypass reader-wiki validation.
- Treat `reader_interactive.html` as a completed end-to-end reader artifact: every substantive `**Original:**` block must have faithful `**中文:**` translation, useful `**注释:**` logic/knowledge/formula/figure guidance, strict validation, feedback UI, and learner-profile annotations when available.
- Treat bilingual formula components and panel boundaries as source-alignment
  evidence: each block's Original/Chinese LaTeX signatures and inline/display
  kinds must match in order, and Markdown headings must stay outside language
  fields. A one-sided formula chip/card or escaped translation panel is a hard
  compile/audit failure.
- Never generate or report HTML from extraction-only drafts, summaries, placeholders, or bypass flags. The paper pipeline has one formal HTML target: fully validated `reader_interactive.html`.
- When the user asks to regenerate, translate, or finish a formal paper reader, the active primary model in the current user-facing session must directly author every Chinese block, block-specific note, and LaTeX reconstruction. Do not delegate those fields to local/third-party translators, secondary models, or scripts; missing translation tooling is not a blocker.
- A formal reader also requires inspectable figure/table cards, LaTeX-readable formulas, and block-specific notes. Caption-only figure text, raw PDF formula noise, whole-page screenshot links, image-object lists, or generic note scaffolds are draft artifacts.
- Algorithms are first-class paper objects like figures and tables. Do not summarize them; render a full algorithm card with original numbered steps and Chinese numbered steps.
- Source Page Index links are first-class navigation aids. Keep their `href` values as plain relative file paths such as `assets/source_pages/page-01.png`; math wrapping, concept highlighting, or HTML markup inside `href` is a hard failure.
- `Copy feedback for Codex` must not depend only on clipboard permission. The HTML must populate a visible fallback textarea with the export JSON whenever copy is requested.
- Every formal reader generation must pass the adversarial HTML audit before being reported as successful.
- `reader_feedback.json` files are handoff artifacts between reader HTML and `reader-learner`; they are not the long-term profile.

## Persistent Visible Wiki

- `.agents/wiki/` is a separate, persistent human-facing Obsidian vault. It may contain only curated knowledge-layer pages and generated navigation/maps.
- Do not move PDFs, raw source text, reader bundles, feedback/events, logs, pipeline data, or `knowledge_profile.json` into `.agents/wiki/`.
- `knowledge_status` in a public concept must be projected from the profile exactly; exposure never implies `known` or `mastered`.
- Keep `source_refs` pointed at public source-summary pages and reserve `profile_source_refs` for internal `src-*` matching. Never put absolute local paths or raw feedback payloads into a public page.
- Use `feedback_visible_wiki_pipeline.py sync` to project every stable profile concept and every profile source into `.agents/wiki/`; use `maps/Profile Coverage.md` to account for raw records that intentionally stay hidden.
- For reader/news/teaching feedback, use `feedback_visible_wiki_pipeline.py reader-feedback`, `news-feedback`, or `teaching-feedback`. Each command must finish the strict importer and its profile backup before an applied visible-Wiki sync.
- Before reporting a visible-Wiki change, run `lint_visible_wiki.py --strict --require-profile-coverage` from the project root.

## Commands Worth Knowing

| Purpose | Command |
|---|---|
| Materialize `paper.md` for a legacy raw bundle | `python D:\AI\PaperTrace\skills\nature-reader\scripts\materialize_reader_markdown.py <reader-dir>` |
| Audit reader UTF-8/text integrity | `python D:\AI\PaperTrace\skills\nature-reader\scripts\audit_reader_text.py <reader-dir>\paper.md` |
| Complete draft reader bundle before HTML | `python D:\AI\PaperTrace\skills\nature-reader\scripts\complete_reader_bundle.py <reader-dir>` |
| Convert reader bundle to HTML | `python D:\AI\PaperTrace\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir>` |
| Test reader end-to-end contract | `python D:\AI\PaperTrace\skills\reader-skill\tests\test_reader_e2e.py` |
| Audit generated reader HTML | `python D:\AI\PaperTrace\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>` |
| Convert news briefing to feedback HTML | `python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html>` |
| Build delta-first news config | `python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py apply --config <candidate_news_feedback_config.json> --output <delta_news_feedback_config.json> --date <YYYY-MM-DD> --days 7 --continuing-mode one-line` |
| Publish verified daily briefing | `python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run/verify/finalize` |
| Import HTML feedback | `python D:\AI\PaperTrace\skills\reader-learner\scripts\import_reader_feedback.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --feedback <reader_feedback.json>` |
| Import news feedback | `python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json` |
| Import feedback and sync visible Wiki | `python D:\AI\PaperTrace\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>` |
| Import news and sync visible Wiki | `python D:\AI\PaperTrace\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>` |
| Sync complete visible Wiki | `python D:\AI\PaperTrace\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync` |
| Attach feedback2 HTML panel | `python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json>` |
| Materialize bilingual project demo | `python D:\AI\PaperTrace\skills\utils\demo-skill\scripts\create_demo.py --output-dir D:\AI\PaperTrace` |
| Initialize profile from chat sessions | `python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions` |
| List learner profile | `python D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json list` |
| Review learner queue | `python D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json review` |
| Analyze adaptive teaching candidates | `python D:\AI\PaperTrace\skills\adaptive-teach\scripts\adaptive_teach.py analyze` |
| Select next adaptive topic | `python D:\AI\PaperTrace\skills\adaptive-teach\scripts\adaptive_teach.py next` |
| Create a short teaching lesson | `python D:\AI\PaperTrace\skills\adaptive-teach\scripts\adaptive_teach.py lesson --output-dir <empty-session-dir>` |
| Import validated teaching feedback | `python D:\AI\PaperTrace\skills\adaptive-teach\scripts\adaptive_teach.py import-feedback --feedback <teaching_feedback.json>` |
| Migrate learner profile to v2 | `python D:\AI\PaperTrace\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json` |
| Validate reader-skill | `python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\reader-skill` |
| Validate reader-learner | `python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\reader-learner` |
| Validate ai-quantum-news-briefing | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\ai-quantum-news-briefing` |
| Validate lean-html-skill | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\utils\lean-html-skill` |
| Validate chat-knowledge-profile | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\utils\chat-knowledge-profile` |
| Validate demo-skill | `python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py D:\AI\PaperTrace\skills\utils\demo-skill` |

## Verification Expectations

- For Python script changes, run `python -m py_compile <script>`.
- For PDF bootstrap/materialization changes, run `python -X utf8 D:\AI\PaperTrace\skills\nature-reader\tests\test_materialize_reader_markdown.py`; it must prove automatic UTF-8 materialization, source-map immutability, no-overwrite behavior, explicit incomplete-state failure, and corruption rejection.
- For reader pipeline changes, compile `skills\nature-reader\scripts\complete_reader_bundle.py`, then run it on at least one draft bundle before strict HTML generation.
- For learner-profile schema changes, compile `profile_v2.py`, `import_reader_feedback.py`, `update_learner_profile.py`, and `migrate_knowledge_profile_v2.py`.
- For skill metadata/instruction changes, run `quick_validate.py` on the changed skill folder.
- For project demos, compare all four pipeline contracts across both languages, test desktop `1440x1024` and mobile `390x844`, and verify no horizontal overflow, language-switch failure, reduced-motion regression, or console error.
- For reader HTML changes, regenerate at least one reader bundle and check for:
  - `Original` and `中文` block counts;
  - image rendering or missing-image warnings;
  - feedback controls;
  - MathJax script when formula rendering is enabled;
  - learner profile annotations when a profile exists.
- For formal `reader_interactive.html`, also run `adversarial_html_audit.py <reader-dir>`. It must check Algorithm cards, Source Page Index link integrity, MathJax/formula rendering, concept mark metadata, feedback export fallback, and Save-mark panel closing.
- For reader pipeline changes, run `python D:\AI\PaperTrace\skills\reader-skill\tests\test_reader_e2e.py`; it must prove valid readers build and incomplete translation/structure fails.
- For reader-learner safety changes, run `python D:\AI\PaperTrace\skills\reader-learner\tests\test_profile_safety.py`; it must prove UTF-8 JSON writes, schema validation, concept normalization, and fail-fast behavior.
- For adaptive teaching changes, run `python D:\AI\PaperTrace\skills\adaptive-teach\tests\test_teaching_cycle.py`; it must prove deterministic selection, evidence separation, no profile write from lesson generation, and safe handoff import.

## Approval Rules

Ask before:

- deleting or moving PDF corpus directories;
- overwriting `.agents/reader-learner/knowledge_profile.json` wholesale;
- running long OCR, large PDF extraction, model downloads, or network-heavy tasks;
- changing the semantics of learner status values.

Never open, print, copy, summarize, upload, or modify suspected credential material. This includes files or paths containing names such as `.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, cookies, or session stores.

## GitHub 发布安全

只发布可复现的代码、公开文档、测试和明确允许的示例资产。绝不上传 `.agents/reader-learner/`、`.agents/adaptive-teach/`、`.agents/wiki/`、原始论文/reader bundle、浏览器与 IDE 状态、Cookie/会话、机器本地配置、数据库或本地生成音视频。提交前必须查看 `git status --short` 和暂存区 diff，并按文件路径显式暂存；混合工作区中禁止使用 `git add -A`。`.gitignore` 只防止新的误提交，不能撤销已跟踪的敏感内容；发现已跟踪的个人或凭据数据时，停止发布并先取得用户确认。
