# Runbook

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-09-27

## Choose One Primary Pipeline

Run commands from `D:\AI\PaperTrace` and do not mix terminal gates:

1. **Paper Reader HTML:** build internal source evidence -> complete/compile -> generate `reader_interactive.html` -> publishing adversarial audit. Return the audited HTML, never the bundle.
2. **AI + Quantum Daily Briefing Release:** collect current evidence -> reviewed preflight -> strict finalize -> strict verify. Return the reviewed briefing HTML and release set, never a candidate/config/staging directory.
3. **Local Chat-to-Profile Import:** `collect -> extract -> propose -> human review -> apply --backup`. Do not generate paper/news HTML and do not apply an unreviewed patch.
4. **Adaptive Teaching Decision & Evidence Loop:** explicit request -> `analyze -> next -> lesson`; after real performance only, `build-feedback -> validate-feedback -> import-feedback`. Do not infer mastery or force feedback import from lesson exposure.

Reader/news feedback import and Visible Wiki sync are later handoffs. Teaching feedback validation/import is the guarded return phase of Pipeline 4.

## Adaptive Teaching Cycle

Run from `D:\AI\PaperTrace` only for an explicit personal teaching request:

```powershell
python .\skills\adaptive-teach\scripts\adaptive_teach.py analyze
python .\skills\adaptive-teach\scripts\adaptive_teach.py next
python .\skills\adaptive-teach\scripts\adaptive_teach.py lesson --output-dir .\.tmp\adaptive-lesson
python .\skills\adaptive-teach\scripts\adaptive_teach.py validate-feedback --feedback <teaching_feedback.json>
python .\skills\adaptive-teach\scripts\adaptive_teach.py import-feedback --feedback <teaching_feedback.json>
```

The first three commands only read the profile and create private teaching artifacts. Do not treat a generated lesson, page visit, or exposure as evidence. Import only exported actual learner performance; the final command delegates backup, atomic profile mutation, review-queue persistence, and Visible Wiki projection to `reader-learner`.

## Daily Briefing Encoding Gate

Run daily briefing commands from `D:\AI\PaperTrace`. New protocol-2 releases require timezone-aware `collection_completed_at` and content-bound `coverage_evidence` for **every** covered Asia/Shanghai calendar day, including a one-day release. The 08:00 scheduled run covers the previous complete day; `--date` is the release label, not proof of coverage. Multi-day backfills additionally need explicit midnight `--coverage-start`/`--coverage-end`. Before `run`, collect the daily academic venue ledger and social search records, then bind each daily `academic_search` and `social_search` object with its SHA-256 reference as specified in `CONFIG_SPEC.md`. The authoritative release path is:

```powershell
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run --config <candidate_config.json> --date <YYYY-MM-DD> --design-system cosmic --background-mode light
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict --structure-only
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py review-template --run-dir <news\YYYY-MM-DD\.staging\RUN_ID>
# Author the pending source and story reviews from actual evidence.
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py seal-review --run-dir <news\YYYY-MM-DD\.staging\RUN_ID>
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py finalize --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict --require-remote
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD> --strict
```

For AI HOT candidate collection, run from `D:\AI\PaperTrace` with the publication day set separately from the release label:

```powershell
python .\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <RELEASE-YYYY-MM-DD> --coverage-date <COVERED-YYYY-MM-DD> --output .\news\<RELEASE-YYYY-MM-DD>\aihot_candidates_<RELEASE-YYYY-MM-DD>.json
```

`--coverage-date` filters the Asia/Shanghai half-open day across API cursor pages; `--take` is a page size, `--since` is only a retrieval lower bound, and `--date` does not filter candidates. A partial page run, missing/ambiguous timestamp, expired API window, or RSS fallback cannot establish complete AI HOT daily coverage. Separately record the required social source classes; selected claims still need original sources. Academic-search v4 isolates source failures and requires one healthy `quantum_publisher` plus one healthy `ai_peer_review` publisher family. Science without a complete publisher-day listing is `skipped_unavailable`; this never means zero publications. HTTP 200, RSS and Crossref do not certify completeness or article claims.

The template is deliberately `unreviewed`. Check each selected news claim against its source and perform the protocol-3 story-only trace, source mapping and cross-surface review before sealing. Clear `unresolved` only after each finding is repaired. `seal-review` binds the reviews and preflight audit to the release manifest; it cannot certify semantic truth. Missing, failed or stale review blocks `finalize` and standalone OSS `publish`. Read `skills/ai-quantum-news-briefing/references/release-review-protocol.md`. Older v2 reviews stay locally readable; preserve the old sidecar before replacing and re-sealing it for a first remote upload or correction. Inspect structured coverage (old display-only `date_range` is not full-day evidence):

```powershell
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py status --from-date <YYYY-MM-DD> --through-date <YYYY-MM-DD> --compact
```

`status` is offline by default: a matching receipt is not proof that public HTML remains available, so `remote_verified: null` means **not checked**. Add `--online` for a read-only public HTML and homepage check; `unreachable` is not the same as `mismatch`. `--compact` omits verbose source evidence without weakening strict local verification.

### Optional OSS website mirror

The finalizer strictly re-verifies the reviewed local release, then invokes the OSS mirror when manually enabled. With `--require-remote`, `disabled`, `pending` or failed delivery returns exit 2 while local completion remains intact. Inspect `remote_publish` and retry standalone `publish`, not the same `finalize`. Site/link checks still latch disabled after bounded retries and require manual `enable`; upload failure stays pending. The final standalone `verify` is read-only.

From `D:\AI\PaperTrace`, install ossutil 2.x and create a user-level profile with `ossutil config credential`. Keep credentials outside this repository. Copy `news_publish.example.json` to the ignored `news_publish.local.json` and fill in `site_index_url`, `bucket`, `region`, `object_prefix`, and `ossutil_profile`. The URL path must match the prefix and end in `/index.html`.

```powershell
python .\skills\ai-quantum-news-briefing\scripts\publish_daily_to_oss.py status
python .\skills\ai-quantum-news-briefing\scripts\publish_daily_to_oss.py doctor
python .\skills\ai-quantum-news-briefing\scripts\publish_daily_to_oss.py enable
python .\skills\ai-quantum-news-briefing\scripts\publish_daily_to_oss.py publish --run-dir .\news\<YYYY-MM-DD>
```

Run `doctor` in the **same execution environment** that will publish. It checks the website, existing link, `ossutil` availability and read-only Bucket binding without uploading or changing the manual enable lock. Its results never disclose profile contents and cannot prove PutObject permission. A blocked `doctor` or `publish` exits nonzero; an earlier `enable` in another shell or sandbox does not establish this process's capability. The daily scheduled task inherits its sandbox. Grant network and user-level profile access only through a tested, narrow authorization; never broadly allow unsandboxed Python/PowerShell or full filesystem access. If narrow authorization is unavailable, keep local release automation and publish from the user's existing PowerShell environment after manual `enable`; report website delivery only after checking remote bytes and homepage.

The existing index must link to one reachable `briefing_reader_YYYY-MM-DD.html`. `enable` checks both URLs and confirms the website index matches the configured Bucket object; the ossutil profile needs GetObject and PutObject access. Every publish repeats the checks, reconciles remote HTML and the receipt, and never moves the homepage backward during historical backfill. Same-date content replacement requires `--correction-reason`, `--supersedes-hash` and fresh review. Only verified HTML and `index.html` reach OSS; receipts stay under `news/_publish/`.

Before running, ensure the candidate config is UTF-8. Do not construct Chinese JSON through a default PowerShell/code-page pipeline. If normalization reports `encoding-corrupted` or `U+FFFD`, regenerate the config from the original source record; do not delete or globally replace `?`.

The candidate config must include `story_delivery.required=true`,
`story_delivery.worked_example_required=true`, and one complete
`opening_story.worked_example`. Select the story topic for relevance and causal
value, not for equation availability. Use a mathematical/numerical derivation
only when it belongs to the mechanism; otherwise provide a complete operational,
causal, experimental, or comparative case without a formula. Read
`skills/allegory-teach/references/worked-example-contract.md` before authoring
the handoff, then read `story-output-contract.md`, `narrative-language-firewall.md`
and `daily-briefing-interface.md`. New authoring uses complete Fable version 3.
At least two causal background paragraphs precede the complete mechanism, with
no total length/count cap. Naturally split paragraphs over 2000 characters.
Keep the narrative and example consistent; legacy versions 1–4 remain readable.

For source maintenance only, run these regression tests from `D:\AI\PaperTrace`.
They use synthetic in-memory/temporary fixtures, not published reports:

```powershell
python -B -m unittest discover -s skills/allegory-teach/tests -p "test_*.py"
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p test_daily_pipeline.py
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p test_publish_daily_to_oss.py
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p test_release_protocol.py
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p test_collection_coverage.py
```

The final verify must report visible HTML `?=0`, replacement-character `=0`, Chinese UI markers, concept/feedback identity equality, all default statuses `unrated`, light default/Cosmic option, and no feedback2 panel. A failed encoding check blocks finalize and therefore blocks story-index updates.

It also verifies that the native worked-example `details` control is closed by
default and ordered between the opening-story debrief and `日报正文`;
formula-bearing examples must retain the MathJax marker. A failed worked-example
check blocks finalize and therefore blocks story-index updates.

### Recheck an opening-story repair

From `D:\AI\PaperTrace`, after structural release verification, run:

```powershell
python skills/allegory-teach/scripts/audit_daily_story.py --run-dir news/YYYY-MM-DD --review news/YYYY-MM-DD/opening_story_review_YYYY-MM-DD.json --output news/YYYY-MM-DD/adversarial_audit_YYYY-MM-DD.json
```

Replace `YYYY-MM-DD` with the release date. The separately authored review binds
the current story/example digest and records text, judgment, source or rule,
reason and limitation for three review rounds. Content edits require re-review,
not just a refreshed hash. The validator checks provenance and structure, not
semantic truth. Keep review records and reports local; they are not learner
evidence and do not change the handoff schema.

A story-only historical reissue retains the original lookback/design settings
and uses an isolated shadow index. Compare all non-story fields and preserve
feedback and canonical index bytes; do not rerank against today's live index.

## Build The Bilingual Project Demo

Run from `D:\AI\PaperTrace` after reading the root `AGENTS.md`, its canonical `.agents` documents, and `README.md`:

```powershell
python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .
```

The command writes `demo.html` and `demo-en.html` and refuses to overwrite either destination by default. Use `--force` only after reviewing the existing files. After adapting the four pipeline contracts in both languages, test `1440x1024` and `390x844`, language links, reduced motion, horizontal overflow, and console errors.

Validate the reusable skill and script:

```powershell
python -m py_compile .\skills\utils\demo-skill\scripts\create_demo.py
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" .\skills\utils\demo-skill
```

Root HTML is ignored by `/*.html`. To publish only the reviewed pages, use the exact paths rather than changing the global ignore rule:

```powershell
& 'D:\software\Git\cmd\git.exe' add -f -- demo.html demo-en.html
& 'D:\software\Git\cmd\git.exe' add -- skills/utils/demo-skill
```

Do not add `.design/`, screenshots, browser profiles, QA scratch logs, credentials, or unrelated working-tree changes.

## Generate Interactive HTML From A Reader Bundle

For a natural-language folder request, run the persistent formal controller
first from `D:\AI\PaperTrace`. Use `--max-papers N` when the request explicitly
limits the deterministic prefix:

```powershell
python .\skills\reader-skill\scripts\build_formal_reader_batch.py --pdf-dir "<PDF-folder>" --reader-root "<reader-root>" --max-papers 2 --resume --agent-continuation
```

The controller freezes the selected PDF paths/hashes in
`<reader-root>/.papertrace_jobs/<job-id>/orchestration_state.json`, records a
heartbeat and exact next command, persists the bounded active record IDs in
`reader_wiki/next_authoring_packet.json`, and invokes the continuation guard in
the production path. `action_required` exits 0 in interactive mode; it still
forbids a final response. Use `--strict-exit` only when CI requires nonzero for
incomplete work. Resume with the emitted `next_command`; do not rediscover or
expand the frozen scope manually.

Before completion records are seeded, register every figure/table/algorithm
identity and allow the controller to write `reader_wiki/source_map_lock.json`.
After that lock exists, crop/compile the registered objects without changing
`source_map.json`. A lock-hash mismatch is repair work and must not be bypassed.

The PDF bootstrap now materializes a UTF-8 working `paper.md` automatically. For a legacy raw bundle that has `source_map.json` but no `paper.md`, run from `D:\AI\PaperTrace`:

```powershell
python .\skills\nature-reader\scripts\materialize_reader_markdown.py "<reader-dir>"
```

For new extraction, `extract_pdf_bundle.py` prefers Poppler raw reading order. If Poppler returns Unicode replacement characters, known Windows font-map mojibake, empty pages, or a page-count mismatch, it automatically retries through pypdf and still fails closed if the fallback is incomplete or corrupt. Do not manually keep a visibly damaged Poppler result.

The materializer is no-overwrite by default and preserves `source_map.json`. It writes explicit `[translation-required]` and `[block-note-required]` markers; these are work-queue markers, not valid final content. After replacing them with source-grounded Chinese and block-specific notes, run the UTF-8 integrity gate:

```powershell
python .\skills\nature-reader\scripts\audit_reader_text.py "<reader-dir>\paper.md"
```

If the audit reports `U+FFFD`, controls, mojibake, or question-mark replacement patterns, rebuild the damaged working text from source evidence. Do not strip or globally replace the damaged characters.

The reader bundle must already contain faithful `**中文:**` translations. `reader-skill` rejects draft/paraphrase columns such as `中文译意`, `非逐句精翻`, `待忠实翻译`, or `reading scaffold` by default.

`reader_interactive.html` is reserved for the completed end-to-end reader: faithful translation, useful `**注释:**` logic/knowledge guidance, strict validation, feedback UI, and learner-profile annotations when available. There is no draft HTML route in the formal pipeline; if validation fails, fix `paper.md` / `source_map.json` first.

When the user requests a completed regenerated paper reader, the active primary model in the current user-facing session must directly author the translated `**中文:**` blocks, block-specific notes, and LaTeX reconstruction. Do not delegate these fields to Ollama, SDKs, external translators, secondary models, or scripts.

Before strict HTML generation, check that figure/table entries in `source_map.json` have actual cards or semantic tables in `paper.md`, every mathematical component in every Original/Chinese block has explicit delimiters, important equations are atomic LaTeX displays with their duplicate extraction text removed from both language fields, and `**注释:**` does not contain generic scaffolds such as `逻辑位置：本文主题是...` or `标注建议：如果这里有不懂...`. Put each independent equation in its own display. Raw `\sigma`, `A^-1`, detached PDF hats, or split indices are completion failures even when the source row is typed as a paragraph.

When any source row (formula, paragraph, caption, or object description) carries `source_math_inventory_required`, review its PDF page and author `object_metadata.source_math_inventory` before rendering. Its ordered components are the audit checklist: every item must be rendered once in Original and once in Chinese with the same LaTeX signature. A reviewed inventory may be derived only from already authored, page-checked components; it never substitutes for source review. Do not fix the row by appending a formula, and do not run any global delimiter-removal script; use a source-bound exact replacement override instead.

For every algorithm, author a complete source-language `assets/algorithms/Axxx.tex`; translate only comments that already exist, using `\Comment{...}`. Compile from `D:\AI\PaperTrace` with the detected TeX Live runtime:

```powershell
$env:PATH='D:\software\paper_software\texlive\2023\bin\windows;' + $env:PATH
python .\skills\nature-reader\scripts\compile_algorithm_latex.py "<reader-dir>\assets\algorithms\A001.tex" --output-dir "<reader-dir>\assets\algorithms"
```

Record the `.tex`, compiled `.svg`, compile manifest, hashes, engine, and source-matching numbered-step count in the algorithm completion record and `object_inventory.json`. Do not create a Chinese duplicate of the executable algorithm body.

If a PDF extraction helper produced a draft bundle, first run the completion pass. This upgrades `paper.md`, `source_map.json`, `translation_notes.md`, formula blocks, and figure/table cards before the reader-wiki hard gate runs:

```powershell
python D:\AI\PaperTrace\skills\nature-reader\scripts\complete_reader_bundle.py <reader-dir>
```

Do not use `--allow-draft-translation` for formal output. Completion must fix the bundle; validation remains the gate.

Current compatibility entry point is still `reader-skill/scripts/markdown_reader_to_html.py`, but reusable HTML shell, feedback UI, browser-memory behavior, and copy/download controls should be implemented in or delegated to `skills/utils/lean-html-skill` rather than duplicated inside `reader-skill`.

```powershell
python D:\AI\PaperTrace\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir>
```

With explicit output:

```powershell
python D:\AI\PaperTrace\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --output <reader-dir>\reader_interactive.html
```

For offline MathJax:

```powershell
python D:\AI\PaperTrace\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --mathjax-url <local-mathjax-script>
```

If this command fails, do not produce a preview HTML. Complete the missing translation, figure/table cards, LaTeX formulas, or block-specific notes, then rerun the same `reader_interactive.html` command.

After a successful generation, run the adversarial HTML audit from the project root:

```powershell
python D:\AI\PaperTrace\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>
```

Do not report Pipeline 1 as complete until this audit passes. A passing reader bundle or completion ledger is still intermediate. The audit checks compiled full-source Algorithm cards instead of summaries/translated duplicate bodies, explicit math boundaries in every visible panel, atomic MathJax formulas without plaintext duplication, declared `exact-v1` bilingual pairs, MathJax runtime status, the model-authored source-linked paper summary, hash-bound source-page viewer data, Original/source-page collapse controls, knowledge-mark metadata, concept coverage, reader-notes pollution, shared autosave and selection-toolbar behavior, stable utility-pane editing, inert blank-page clicks, and feedback-copy fallback.

Before rendering a full paper, author `reader_wiki/paper_summary.json` with detailed Chinese overview/what/how/significance/evidence-limit sections and formal source anchors. For PDF readers, preserve every `source_map.pages` image under `assets/source_pages/`; the renderer uses those existing assets for the enlarged, viewport-height left viewer and must not rerender the PDF or embed full pages as article figures. On wide screens, source pages and Contents are independently resizable around a minimum-width center article; medium widths may default Contents to a restore rail, and narrow widths stack.

After generation, verify the view-control JavaScript from `D:\AI\PaperTrace`:

```powershell
node .\skills\reader-skill\tests\test_reader_js_runtime.js <reader-dir>
```

`Hide Original`, `Hide Source Pages`, and `Hide Contents` are independent view states. Pointer/keyboard separators resize the source and Contents panes, each collapsed pane leaves a restore path, and print output must restore Original even if it was collapsed on screen. On wide screens, Contents and `Annotate / 自由标注` must alternate inside the same fixed utility lane without changing the source/article grid. Blank-page clicks must not dismiss feedback or reveal Contents; only Close or Esc may dismiss it. Smaller screens use a scroll-safe bottom region rather than permanently cover translated text.

If Source Page Index links do not open, inspect the generated `href` values first. They must be plain relative paths such as `assets/source_pages/page-01.png`; generated spans such as `<span class="math-inline">` inside a link target mean the HTML renderer annotated a file path and the reader must be regenerated after fixing the renderer.

## Import Reader Feedback

Reader HTML uses browser-local recovery plus manual portable export. In the browser:

1. Click a highlighted concept or select text and click `Annotate / 自由标注`.
2. Fill status/question/context fields.
3. Choose a status or edit a detail field; status saves immediately and text/select changes save after a short debounce.
4. Confirm the saved item appears in the feedback panel's saved-annotation list and, when a source block is detected, as a badge in the page. Use the five-second undo for an accidental status or deletion.
5. Delete mistakes with `Delete current` or the row-level `Delete` button in the saved-annotation list.
6. If the tab is refreshed or closed, reopen the same reader and confirm saved marks and any unfinished form draft are restored.
7. After finishing the paper, click `Download feedback JSON` to export all saved items, then choose whether to clear the browser recovery copy.

Then import the downloaded JSON:

```powershell
python D:\AI\PaperTrace\skills\reader-learner\scripts\import_reader_feedback.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --feedback <reader_feedback.json>
```

Alternative: click `Copy feedback for Codex`, paste the payload into Codex, and let Codex apply the `reader-learner` update rules.

If browser clipboard permissions block copying, use the visible fallback textarea populated by `Copy feedback for Codex`; it contains the same JSON payload.

Important: browser recovery is local to the current browser/origin and may be unavailable under restrictive `file://` or privacy settings. Treat exported JSON as the portable backup. If the panel reports that recovery is unavailable, export before closing. The recovery copy never updates `.agents` or the learner profile.

The learner profile uses schema v2. Imports should keep stable concept IDs in `concepts`, raw selected text and questions in `events`, source paths/URLs in `sources`, and unclear or learning items in `review_queue`.

## Import AI + Quantum News Feedback

Use `skills/ai-quantum-news-briefing` for current AI/model/industry/regulation/academic/quantum news requests. State the exact date range, cite current sources, and save durable outputs under `news/<date-range>/` when producing files.

The briefing pipeline is end-to-end: candidate collection and `news_feedback_config.json` are intermediate artifacts only. A completed daily or multi-day briefing must end with an interactive HTML reader, full default-`unrated` feedback JSON, a Markdown briefing, a delta config, and an updated `news/_index/story_index.jsonl`. Use `D:\AI\PaperTrace\news\2026-07-07_to_2026-07-09` as the sample output directory structure.

Use profile import only after the user explicitly marks briefing concepts or asks to record briefing keywords. Exposure-only keywords should be `unrated`.

For recurring daily briefings, use the delta-first story index to avoid repeating prior-day items and to keep prompt context small. First get the compact lookback context:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index D:\AI\PaperTrace\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
```

After creating a source-grounded candidate `news_feedback_config.json`, rewrite it before rendering HTML:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py apply --config <candidate_news_feedback_config.json> --output <delta_news_feedback_config.json> --date <YYYY-MM-DD> --days 7 --continuing-mode one-line
```

Use `--continuing-mode skip` when the user asks for the shortest possible report. The delta output should use `今日新增`, `重大更新`, and `持续跟踪，一句话` sections; category remains an item-level tag for feedback/profile reports. Do not update the index at this stage: use `daily_pipeline.py run`, `verify`, and `finalize` so the index is committed only after all artifacts pass.

Generate an interactive briefing HTML when the user wants click/freeform feedback:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html>
```

In the HTML, click concepts or select text for the contextual toolbar; explicit changes auto-save. Finish with `Download JSON` or `Copy for Codex` for a portable handoff.

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
```

The command writes a normalized `*_reader_feedback.json` handoff file, then calls `reader-learner` to update `.agents/reader-learner/knowledge_profile.json`.

If the user explicitly says a concept is understood or unclear, map it before import:

- "我懂" -> `known`
- "我能讲清楚/会用" -> `mastered`
- "有点懂但还要例子" -> `learning`
- "不懂/解释一下" -> `unknown`
- "记录关键词/见过一次" -> `unrated`

## Inspect Or Manually Mark Learner Profile

List concepts:

```powershell
python D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json list
```

Mark one concept:

```powershell
python D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json mark --concept "ansatz" --status learning --note "Needs paper-specific explanation"
```

Review due or high-priority concepts:

```powershell
python D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json review
```

Migrate an old profile to schema v2 with a timestamped backup:

```powershell
python D:\AI\PaperTrace\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
```

## Import Chat Sessions Into Profile

Use this when the user has exported or copied ChatGPT/GPT/Claude/Deepseek conversations and wants them to contribute to the long-term learner/person profile. Prefer local `.txt`, `.md`, `.html`, or `.json` exports; do not rely on share URL fetching for reproducibility.

Collect sources, bounded evidence events, and per-conversation summaries:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions
```

Extract reviewable candidates:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py extract --events D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\events.jsonl --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
```

Propose a patch:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py propose --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --candidates D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json
```

Apply only after reviewing `profile_patch.json`:

```powershell
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py apply --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --patch D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

The skill writes concept-status candidates through strict `reader-learner` validation and writes non-concept user traits under `person_profile`. Review `profile_patch.json` before applying. Use `conversation_summaries.json` to inspect each conversation's `at_a_glance`, topic tags, explicit preferences, open questions, and action-like requests.

## Daily Academic And Feedback Release Gate

APS PRL, PRA and PRX Quantum use separate official recent-publication feeds under `https://feeds.aps.org/rss/recent/` (`prl.xml`, `pra.xml`, `prxquantum.xml`). The collector validates each feed's journal, DOI and publication date, quarantines malformed individual items, and fetches each feed once per sweep. A rolling RSS feed is a discovery source, not proof of a complete historical-day inventory or of an article's scientific claims; selected articles still require article-level capture and review.

AI HOT may retain a completed daily cursor scan with exactly one undated item as `qualified_with_exclusion` when at least one dated in-window item remains. The undated item is hash-identified and excluded from the selected-day pool; the record claims only `dated_candidates_only`, never complete AI HOT coverage. Interrupted pagination, retention failures, multiple undated items, or absent exclusion evidence still fail. An older `partial` file without the excluded item's identity cannot be relabeled by hand; recollect it when network access is available.

New publication-contract-v3 runs must use an explicit release date and the canonical project `news/` layout; public `run` no longer accepts `--output-dir` or `--index`. Capture viable candidates' article-level sources first; uncaptured candidates stay ineligible. The capture records request/final URL, HTTP status, timestamp, response and extracted-text hashes, plus a short quote found in the retrieved text; hashes do not prove scientific interpretation. New scoring uses `news-ranker-v2`: authored `facts`, `judgment`, `relevance` and `ranking_signals` cannot increase candidate scores. Human source/story review remains mandatory. The read-only orchestrator reports actual phase and remote-pending status; it cannot approve content or turn an offline receipt into website verification. Historical v1/v2 releases remain readable; first OSS upload or correction requires a regenerated, reviewed v3 release.

Run from `D:\AI\PaperTrace`:

```powershell
python .\skills\ai-quantum-news-briefing\scripts\source_capture.py --config .\news\_collection\<RELEASE-DATE>\candidate_<RELEASE-DATE>.json --coverage-date <COVERED-DATE>
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run --config .\news\_collection\<RELEASE-DATE>\candidate_<RELEASE-DATE>.json --date <RELEASE-DATE>
python .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py status --date <RELEASE-DATE> --record
```

For an existing date, pass `--correction-reason` and `--supersedes-hash` at both `run` and `finalize`; review the new staging before committing. Never re-upload an already verified release just to update its receipt.

For new low-signal releases, keep the covered Shanghai day fixed. Pipeline v4 requires one healthy publisher in each core family: `quantum_publisher` and `ai_peer_review`. A single optional or probationary source may fail without stopping the issue; an entire required family failure still blocks publication. Only after the normal day is collected may the pipeline expand to 14 academic calendar days and 72 social hours. Use `delivery_expansion.version=2`, `mode=verified_shortfall` only with content-bound ledgers, candidate exclusions, original publication times, at least one claim-reviewed item in each category and a concrete shortage reason.

For `daily_pipeline.py`, keep `analysis_language=zh-CN`, `academic_delivery.required=true`, and `ranking_policy.enabled=true`. In standard mode, select 6–8 academic papers and 6–12 social items. `verified_shortfall` may relax only documented lower bounds and still requires one audited academic and one audited social item. `academic_search_version=4` records retrieval, parsing, window, coverage claim, candidates and quarantines separately. HTTP 200 is never completeness or article-truth proof. Science remains optional discovery and may be `skipped_unavailable`; this never means zero publications.

Use the single v4 orchestrator from `D:\AI\PaperTrace`:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py status --date <RELEASE-DATE>
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py preflight --date <RELEASE-DATE>
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py collect --date <RELEASE-DATE> --record
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py resume --date <RELEASE-DATE> --record
```

Explicit `preflight` and `status --preflight-network` always check transport, including cached `collection_ready`; normal cached `resume` remains offline. Transport results distinguish `ready`, `not_checked` and blocked/unverified environments. Candidate readiness covers capture availability, not completed authoring: `opening_story_status=authoring_pending` still requires a complete Fable before staging.

`collect` and `resume` run only repository-controlled collectors for missing or invalid source files, after network preflight; valid cached evidence is preserved. A valid source pair with a missing, legacy, damaged or stale authoring packet reports `authoring_packet_pending`. `resume` rebuilds that packet offline, retaining original candidate fields and identities. `collection_ready` requires a valid source pair **and** an exact, source-hash-bound packet. An empty valid pool requests evidence-backed expansion, never automatic shortfall approval.

Packet recovery uses atomic replacement and a digest-named backup under the collection day's `.packet_backups/`. Repeating recovery with unchanged sources does not fetch, rewrite the packet or duplicate its backup. Unknown higher packet versions report `authoring_packet_incompatible` and are preserved. An invalid authored candidate reports `candidate_invalid`; existing candidates, staging and release artifacts take precedence and are never overwritten by collection recovery. `status` remains read-only unless `--record` is supplied; unchanged recorded state is not rewritten. Normal actionable checkpoints exit 0; collector, validation, filesystem and environment failures during recovery exit 2. Inspect `phase`, `packet_status`, `action_required` and structured failure codes instead of interpreting exit 0 as publication success.

Source failures are shown as a compact health table without credential paths, raw subprocess diagnostics or stack traces. Recovery never approves semantic review, enables OSS, publishes, or imports feedback. Run this regression suite from the project root when changing orchestration:

```powershell
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p test_orchestrate_daily.py
```

For a v4 release, inspect the `ranking_manifest` and `candidate_ledger` in the staged delta config after `run`; the standalone ranker CLI without captured-source enrichment is a historical v1 preview, not an exact v3 replay. Run from `D:\AI\PaperTrace`:

```powershell
python .\skills\ai-quantum-news-briefing\scripts\audit_briefing_config.py --config .\news\<RELEASE-DATE>\.staging\<RUN-ID>\news_feedback_config_delta_<RELEASE-DATE>.json --coverage-contract-version 3 --fail-on-warning
```

The normal `daily_pipeline.py run` command performs captured-source v2 ranking internally before Delta compaction. Candidate-only evidence, invalid dates, unsafe URLs, duplicates, and missing fact/judgment/relevance fields remain in the ranking ledger with exclusion reasons but cannot enter the publication.

Before `finalize`, run the strict config audit. It blocks English-only `facts`/`judgment`/`relevance`, encoding-corrupted Chinese (`U+FFFD` or corruption-pattern `?`), and insufficient academic delivery. On failure, rebuild the UTF-8 input from source records; never repair strings with global replacements or publish a visually rendered but semantically corrupted HTML file.

The interactive briefing must initialize browser state from embedded `initial_feedback_items`. Before any click, `Download JSON` must export exactly the complete automatic concept set with `default_status: "unrated"`; after edits, it exports the same identities with user changes overlaid. Removing an automatic item restores the baseline; freeform annotations remain removable.

After the final strict verification, inspect the published manifest from `D:\AI\PaperTrace`:

```powershell
$manifest = Get-Content -LiteralPath '.\news\<YYYY-MM-DD>\daily_pipeline_manifest_<YYYY-MM-DD>.json' -Raw -Encoding UTF8 | ConvertFrom-Json
$manifest | Select-Object status, ranking, delta_counts, expected_concepts, index_commit
```

`status` must be `complete`. In `standard` mode, `ranking.academic` must be 6–8 and `ranking.social` must be 6–12. In `verified_shortfall`, inspect the bound expansion evidence and actual counts instead; both categories still require at least one source-reviewed item and a shortage explanation consistent with the manifest. The item-level ranking ledger in `news_feedback_config_delta_<YYYY-MM-DD>.json` must agree with the manifest.

## Validate Scripts

```powershell
python -m py_compile D:\AI\PaperTrace\skills\reader-skill\scripts\markdown_reader_to_html.py
python -m py_compile D:\AI\PaperTrace\skills\nature-reader\scripts\complete_reader_bundle.py
python -m py_compile D:\AI\PaperTrace\skills\reader-learner\scripts\profile_v2.py
python -m py_compile D:\AI\PaperTrace\skills\reader-learner\scripts\import_reader_feedback.py
python -m py_compile D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py
python -m py_compile D:\AI\PaperTrace\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\rank_briefing_candidates.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\audit_briefing_config.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py
python -m py_compile D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py
python -m py_compile D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python -m py_compile D:\AI\PaperTrace\skills\utils\demo-skill\scripts\create_demo.py
python D:\AI\PaperTrace\skills\reader-skill\tests\test_reader_e2e.py
```

## Validate Skills

```powershell
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\reader-skill
python "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\reader-learner
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\adaptive-teach
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\allegory-teach
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\ai-quantum-news-briefing
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\utils\chat-knowledge-profile
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\utils\demo-skill
```

## Sync And Validate The Persistent Visible Wiki

Run these commands from `D:\AI\PaperTrace`. The sync pipeline never mutates the learner profile. It creates the missing concise public projections for every stable profile concept and every profile source, then validates coverage.

```powershell
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
python .\skills\reader-learner\scripts\lint_visible_wiki.py --profile .\.agents\reader-learner\knowledge_profile.json --wiki .\.agents\wiki --strict --require-profile-coverage
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>
```

The reader/news commands first invoke the existing strict importer (which backs up the profile) and only sync the visible wiki after a successful import. Open `D:\AI\PaperTrace\.agents\wiki` as its own Obsidian vault. Use `maps/Profile Coverage.md` to confirm the projection and `maps/Evidence Map.md` for claim-to-source navigation.

## Risky Operations

Ask the user before:

- moving/deleting corpus PDFs;
- overwriting generated reader bundles;
- rewriting `.agents/reader-learner/knowledge_profile.json`;
- running large OCR jobs or network-heavy downloads;
- converting many PDFs in batch.

Do not open, print, copy, summarize, upload, or modify any suspected key/password/token/credential file. The learner profile is user learning data, not credential material, and should still be handled only through the documented reader-learner workflow.

### Publication version-routing regression

Generation, local strict verification and first upload use `publication_contracts.py`: pipeline 2/3 uses coverage contract 2; pipeline 4 uses contract 3. First uploads require pipeline 3/4 with its exact coverage pair and a current story review protocol 3. Unknown versions and v4 downgrades are rejected. Historical completed evidence keeps its original local validation semantics.

The shared release lock initializes its byte only while holding the OS lock.
Windows supports locking past EOF; writing an empty lock file before taking its
lock races with concurrent startup. `test_release_lock.py` holds an empty file
locked from another process to reproduce that race deterministically and checks
that interruption does not poison the next acquisition.

Run from `D:\AI\PaperTrace` using the runtime interpreter:

```powershell
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p 'test_*.py'
git diff --check
```

`test_publication_v4.py` exercises the default CLI, normal/shortfall staging, source/story reviews, sealing, strict verification, finalization and in-memory OSS. Tests use temporary data and mocked transport, never real keys or OSS. When making evidence copies, retain original JSON timestamp strings and compute digests with `daily_coverage_evidence.evidence_digest`; do not round-trip dates through PowerShell date objects or relabel academic-search versions.


## Daily collection and workflow recovery

Run from `D:\AI\PaperTrace` with the actual runtime interpreter:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py queue --date <RELEASE-DATE> --record
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py preflight --date <RELEASE-DATE> --record
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py resume --date <RELEASE-DATE> --record
```

Use the last two commands only after the prior Shanghai day has ended and collection needs work. `queue` persists explicitly selected release dates under `news/_automation/workflow_queue.json`; it does not discover or authorize arbitrary historical backfills. Its next date/action keeps unfinished selected dates visible. `final_response_allowed=false` means normal workflow work remains, not an approved review. Ordinary pending work exits 0; actual collection/validation/write failures exit 2.

Academic collection has a 200-second cooperative budget and a 270-second parent watchdog. Requests and retry sleeps respect the remaining budget, core families start first, and every finished row gets an atomic query/registry-bound checkpoint. The temporary evidence aggregate is also updated after each completion. Even after worker termination it can be installed only if independently validated family evidence passes; unfinished rows remain explicit errors. Healthy cached rows are reused; failed rows are retried. No per-source candidate truncation is permitted; only the authoring packet's documented total cap applies.

AI HOT starts with the same budget and an 8 MB response cap; bounded resume escalation is defined below. Partial pagination keeps query/date-bound page bodies, response hashes and cursors under `.checkpoints`, separate from authoritative evidence. Resume validates the chain and rechecks every cached page against its current response; a changed pool restarts the scan. Missing/repeated cursors, malformed records and unfinished pagination never become ready. This is a bounded recovery checkpoint, not a claim that the external API offers immutable snapshots.

`source_capture.py` isolates item failures, reports captured/reused/failed IDs, reuses only validated captures, and exits 2 on partial failure. Before atomic installation it checks the candidate bytes and takes the shared release lock; network requests do not hold it. A concurrent valid capture wins. Retry with the same config or `--item-id`; do not regenerate or promote candidate prose automatically. The status inspector validates captures rather than checking existence.

Finalization refreshes the artifact-derived orchestration checkpoint after local/remote processing. After remote success, it performs online status inspection; the queue retains earlier verification only under the latest observation and deployment identity rules defined below. For explicit reconciliation run:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py status --date <RELEASE-DATE> --online --record
```

JMLR now has a genuine RSS article parser. Its live feed currently supplies year-only dates: preserve structured identities/descriptions and raw dates, report degraded/unknown, and require article-date verification. It cannot satisfy a dated family gate by pretending that a year is a timestamp. Independent healthy fallback remains unproven; Nature/OpenReview availability is an external dependency. Family impact labels use the aggregate gate rather than treating every failed core row as blocking.

The existing daily automation keeps its schedule and target, uses the date queue, and advances by actual phase. Collection `resume` does not perform authoring, reviews or publishing. Permission scope also covers controlled source capture, OSS doctor/publish, finalization and online status commands. Never grant generic interpreter/shell permission, change proxies/global policy, read credentials or automatically enable OSS. Interactive elevated transport success does not prove unattended permissions; the next background preflight must validate its own network/write context. The desktop app and computer must remain available for local automation.


## Daily evidence and delivery recovery contracts

Academic v4 healthy rows share one validator (`academic_sources.row_evidence_failures`): registered source/query path and parameters; explicit allowed final domains; successful HTTP and SHA-256 shape; aware retrieval time after the covered window and not in the future; matching canonical row/ledger window; supported coverage claim; consistent counts and timezone-aware match dates. `not_applicable` parsing cannot prove healthy structured discovery. Invalid healthy declarations fail audit; blocked/degraded peer sources remain isolated. Empty valid matches do not approve verified shortfall. This checks evidence consistency, not article semantics or completeness of a publisher's inventory. Original valid historical collection bytes are not rewritten.

AI HOT starts with 200 seconds and can resume after budget exhaustion with 400, then 800 seconds. Scaled test budgets use the same multipliers. The parent watchdog is at least the effective budget plus 70 seconds. Every cached page is still revalidated in the current attempt; a changed prefix restarts. No immutable snapshot contract is assumed. Checkpoints expose budget level, revalidated/new pages, elapsed time, no-progress count, restart count and failure. At the maximum budget, after three no-progress attempts, after three unfinished restart attempts or at the page bound, automatic recovery stops with `action_required`. The orchestrator exposes this diagnosis without another network preflight. Diagnose transport/pool first, preserve the checkpoint, then deliberately archive it before starting a fresh attempt; do not repeatedly resume a halted checkpoint. Checkpoint reads/writes share the 32 MB cap and atomic replacement. Partial evidence is never installed as an authoritative social source.

Remote completion is bound to release date, HTML SHA-256 and a digest of public routing (site, bucket, region, prefix). Credential/profile data is excluded. `status --online --record` reserves a monotonic attempt sequence under the short shared lock before network; no network request holds that lock. The latest completed observation, its start/end timestamps and historical successful proof are recorded separately. A later mismatch/unavailable result, an unfinished newer attempt, a changed deployment or changed HTML blocks queue completion. Older late-returning checks cannot overwrite newer observations. Offline recording preserves known failures. Missing/mismatched publishing receipts remain pending even when public content verifies. Legacy hash-only success is audit history and requires one fresh check for completion; it does not require republishing. Read-only `status --online` performs no metadata write and does not update the queue. Older releases may legitimately have a homepage pointing to a newer date; preserve the publisher's existing no-downgrade policy.

`finalize` returns separate local, publisher, final verification and checkpoint outcomes. `--require-remote` exits 0 only after the strict local commit, successful publisher outcome, final online verification and durable checkpoint all succeed. Requested online/publish/checkpoint failure exits 2 with `recovery_required`; preserve the local commit and reconcile verification/state before considering another upload. Explicit local-only completion with remote disabled may exit 0 and reports `remote_publish.status=disabled`. Unknown publisher results fail closed. Normal offline actionable status/queue checkpoints still exit 0.

Run from `D:\AI\PaperTrace` to reconcile the already published release without uploading:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py status --date <RELEASE-DATE> --online --record
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py queue --date <RELEASE-DATE>
```

Run the full offline regression from the worktree or production project root:

```powershell
python -B -m unittest discover -s skills/ai-quantum-news-briefing/tests -p 'test_*.py'
git diff --check
```

Actual semantic/Fable review, all social search classes and strict publication gates are unchanged. Recovery must preserve original source hashes and `not_reviewed` packet semantics. It must not create a release, backfill history, toggle OSS, mutate a profile or change a schedule. Unattended transport/write permission and an independent healthy AI publisher fallback still require actual environment evidence; interactive success does not establish those conditions.


## Independent AI source and collection diagnostics

The `plos-ai` source queries the official PLOS index for AI / machine-learning
Research Articles with `doc_type:full`. The requested Shanghai half-open interval
is converted to UTC in the fixed query. Preserve each original `publication_date`
and label its meaning `publisher_index_publication_date`; the index's timestamp
does not prove the actual first-online instant. This is `discovery_only`, never
a publisher-wide census or approval of article claims.

Healthy PLOS evidence requires a complete bounded query, exact request scope,
HTTP/digest evidence for every page, unique consistently ordered article IDs,
matching counts, valid article types/subjects/dates, and an unchanged second read
of all pages. The shared row validator reconstructs these checks from saved raw
responses before family admission or cached reuse. A healthy empty result means
only zero currently indexed matches for that exact query. It does not approve
verified shortfall: normal expansion, article review and release quotas remain.

RSS `window_evidence` records the observed date range and distinguishes
`target_before_feed` from `target_after_feed`. Neither is evidence of a covered
empty day. A response with no dated entries is unknown, not a healthy rolling
window. `collection_diagnostics` retains the recomputed missing family and
per-source transport/parse/window failures before temporary aggregate cleanup.
The current preflight survives collection; `last_collection_attempt` preserves
the most recent completed attempt for later status inspections and is explicitly
historical, not a current readiness or publishing result.

Source-registry upgrades invalidate the registry-bound academic checkpoint;
back it up before recovery. Existing valid social collection and completed
release files are preserved. In `D:\AI\PaperTrace`, recover with:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py queue --date <RELEASE-DATE> --record
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py resume --date <RELEASE-DATE> --record
```

`collection_ready` still means only valid not-reviewed authoring inputs. Continue
source review, expansion where needed, Fable, strict local review and publication
through their existing gates. Do not toggle OSS or modify learner state to fix a
collection failure. Tests use temporary directories and mocked transport.

## Daily source and recovery contract

New collection retains academic search v4 and publication protocol v4, and adds
source_coverage_version=2. Families admit replay-verified complete registered
queries; rolling feed date spans cannot prove query completeness. APS PRX
Quantum open-access publication-calendar queries and Crossref Quantum metadata
are independent provider/publisher paths. PLOS AI and Crossref Nature Machine
Intelligence provide AI query paths. Query zero results never claim publisher-
wide zero publications. Preserve raw responses, scope, provider, dates, precision,
pagination and bounded consistent rechecks. Calendar labels remain date-only;
they do not identify actual Shanghai first-online instants. Historical coverage
version 1 keeps its meaning; dated evidence cannot downgrade to that contract.

The sole quota owner is scripts/daily_delivery_policy.py. Defaults are unchanged:
academic minimum/target/maximum 6/8/8, social 6/12/12, social new/material update
minimum 4. Formal publication bounds remain unchanged. Conflicting explicit
non-default ranking/delivery values raise policy_conflict; copied defaults remain
fallbacks for configured delivery. Packets
and attempts bind the policy SHA-256. Configuration overrides retain their
existing meaning; semantic review and verified-shortfall gates remain unchanged.

resume advances thin source-valid pools through expansion_pending to
expansion_ready: 14 academic calendar days plus the current and two preceding
AI HOT days. expansion_packet_v1.json remains not_reviewed / not_approved and
points back to full evidence when capped at 100 per category. Four social source
classes still need actual search/verification before shortfall can be approved.
For sufficiently large daily pools, late_arrival_pending performs a three-day
registered-index query and emits an unreviewed authoring annex. Frozen releases
are never changed. Source and packet replacement is atomic, backed up by content
digest, and rechecked under the installation lock. Network runs outside locks.
Academic caches are scoped per source; unrelated registry edits preserve valid
peer rows. A new checkpoint contract requires one initial revalidation.

Run from D:\AI\PaperTrace:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py resume --date <RELEASE-DATE> --record
```

Explicit expand/recheck subcommands use the same --date and --record arguments.
Unknown packet versions are preserved. Actionable input checkpoints exit 0;
real transport/validation/write failures exit 2. Queue execution_order puts the
requested current date first and retains every selected backlog date. Attempt
reservations precede network, are sequence ordered and retain independent history
with runtime/code/policy identity. A source-valid packet, expansion packet or
annex never approves facts, story, shortfall, local release or remote delivery.

Validation: offline regression and live positive/empty qualification precede
deployment. New aggregates retain legacy_family_gate alongside the actual gate
for a 14-natural-day observation including weekends; this observation is ongoing,
not an already-passed acceptance result. Installation records exact target/payload
hashes and backups. Rollback code as a bundle; retain all newly collected evidence
and completed releases. Notification is separate from publishing; no new channel
or automatic OSS enable is introduced.


## Scoped daily authoring save contract

Run commands from `D:\AI\PaperTrace`. A failed file-editor call does not prove
all project writes are denied. Test the current task's actual controlled writer:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\daily_authoring.py probe --date <RELEASE-DATE>
```

The probe creates and removes a temporary file inside that day's collection
directory; it never creates a candidate, review, release or approval. It does not
grant sandbox permissions. If a command is denied, request host approval for
that exact full command, with no generic interpreter/shell prefix. If approval
is unavailable or denied, stop the dependent write and report the actual tool
failure. OS `PermissionError`, editor denial and unavailable host escalation
must be distinguished. Do not switch tools to bypass a denial.

The sole scoped authoring CLI supports `save` (whole JSON object) and `patch`
(JSON-pointer operations). Set `--date`, `--kind candidate|news-review|story-review`,
`--expected-sha256 <current 64-hex digest|absent>`, and `--payload-base64 <ASCII>`.
Review writes additionally require `--run-id <date>-<12 lowercase hex>` and an
existing protocol-4 staged manifest and template from `review-template`.
Encode the actual authored UTF-8 JSON directly as base64; do not pass Chinese
through a default Windows shell encoding. Each payload is limited to 20,000
ASCII characters. Split large authored documents into small patch commands,
using each returned SHA-256 for the next command. Never approve a generic Python
or PowerShell prefix. For example, after constructing an actual draft payload:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\daily_authoring.py save --date <RELEASE-DATE> --kind candidate --expected-sha256 absent --payload-base64 <BASE64_OF_AUTHORED_JSON>
```

Patch operations are `add`, `replace`, `remove`, or `copy-file`; JSON pointers
follow `/sections/0/items/-` syntax. `copy-file` imports unchanged evidence only
from a non-hidden `.json` in the same release's `_collection` directory, with
optional `source_pointer`. Feedback, another date's collection and authored
candidate files are rejected:
`{"op":"copy-file","path":"/coverage_evidence/0/academic_search",`
`"source":"_collection/<RELEASE-DATE>/academic_search_v4_<COVERAGE-DATE>.json"}`.
This copies evidence; it cannot make a discovery candidate or missing source
class approved. Paths outside `news`, reparse points, unknown artifact kinds,
changed review bindings and obsolete expected digests fail closed.

Candidate drafts default to `authoring_status=in_progress` and are inspected as
`candidate_authoring_pending`, even with zero items. Continue actual authoring;
only when the draft is finished explicitly patch `/authoring_status` to
`complete`. All saves retain `semantic_review_status=not_reviewed`.
This marker is not a content approval. Capture validity, required coverage,
quotas, Fable and all actual reviews are still enforced by existing gates.
Staged/published candidates cannot be rewritten by this CLI. Review binding
digests and item identities cannot be changed, and saving a review cannot seal
or publish it. Repair a staged content defect through the existing controlled
regeneration path rather than editing published HTML or index.

Writes hold the shared release lock briefly, require optimistic SHA-256 matching,
make exact-byte backups under `.authoring_backups` before replacements, and use
atomic installation. Repeating identical content with the current digest makes
no backup or byte change. A corrupt candidate can be explicitly replaced with
its exact digest and raw backup; a future candidate version remains untouched.
Failures exit 2, unchanged/saved drafts and successful probes exit 0. No global
permission, credential, proxy, OSS-enable or learner-profile change is needed.
