# Runbook

- Project root: `C:\Users\SSS\Desktop\PAPER`
- Last reviewed: 2026-07-13

## Daily Briefing Encoding Gate

Run daily briefing commands from `C:\Users\SSS\Desktop\PAPER`. The authoritative path is:

```powershell
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run --config <candidate_config.json> --date <YYYY-MM-DD> --design-system cosmic --background-mode light
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py finalize --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD> --strict
```

Before running, ensure the candidate config is UTF-8. Do not construct Chinese JSON through a default PowerShell/code-page pipeline. If normalization reports `encoding-corrupted` or `U+FFFD`, regenerate the config from the original source record; do not delete or globally replace `?`.

The final verify must report visible HTML `?=0`, replacement-character `=0`, Chinese UI markers, concept/feedback identity equality, all default statuses `unrated`, light default/Cosmic option, and no feedback2 panel. A failed encoding check blocks finalize and therefore blocks story-index updates.

## Build The Bilingual Project Demo

Run from `C:\Users\SSS\Desktop\PAPER` after reading the root `AGENTS.md`, its canonical `.agents` documents, and `README.md`:

```powershell
python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .
```

The command writes `demo.html` and `demo-en.html` and refuses to overwrite either destination by default. Use `--force` only after reviewing the existing files. After adapting the three pipeline contracts in both languages, test `1440x1024` and `390x844`, language links, reduced motion, horizontal overflow, and console errors.

Validate the reusable skill and script:

```powershell
python -m py_compile .\skills\utils\demo-skill\scripts\create_demo.py
python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py .\skills\utils\demo-skill
```

Root HTML is ignored by `/*.html`. To publish only the reviewed pages, use the exact paths rather than changing the global ignore rule:

```powershell
& 'D:\software\Git\cmd\git.exe' add -f -- demo.html demo-en.html
& 'D:\software\Git\cmd\git.exe' add -- skills/utils/demo-skill
```

Do not add `.design/`, screenshots, browser profiles, QA scratch logs, credentials, or unrelated working-tree changes.

## Generate Interactive HTML From A Reader Bundle

The reader bundle must already contain faithful `**中文:**` translations. `reader-skill` rejects draft/paraphrase columns such as `中文译意`, `非逐句精翻`, `待忠实翻译`, or `reading scaffold` by default.

`reader_interactive.html` is reserved for the completed end-to-end reader: faithful translation, useful `**注释:**` logic/knowledge guidance, strict validation, feedback UI, and learner-profile annotations when available. There is no draft HTML route in the formal pipeline; if validation fails, fix `paper.md` / `source_map.json` first.

When the user requests a completed regenerated paper reader, translate directly in Codex and write the translated `**中文:**` blocks into `paper.md` and `source_map.json`. Do not first search for Ollama, OpenAI SDK, Argos Translate, DeepL, or other translation backends; those are optional aids, not prerequisites.

Before strict HTML generation, check that figure/table entries in `source_map.json` have actual cards or semantic tables in `paper.md`, important equations are LaTeX display math, and `**注释:**` does not contain generic scaffolds such as `逻辑位置：本文主题是...` or `标注建议：如果这里有不懂...`.

If a PDF extraction helper produced a draft bundle, first run the completion pass. This upgrades `paper.md`, `source_map.json`, `translation_notes.md`, formula blocks, and figure/table cards before the reader-wiki hard gate runs:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\nature-reader\scripts\complete_reader_bundle.py <reader-dir>
```

Do not use `--allow-draft-translation` for formal output. Completion must fix the bundle; validation remains the gate.

Current compatibility entry point is still `reader-skill/scripts/markdown_reader_to_html.py`, but reusable HTML shell, feedback UI, browser-memory behavior, and copy/download controls should be implemented in or delegated to `skills/utils/lean-html-skill` rather than duplicated inside `reader-skill`.

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir>
```

With explicit output:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --output <reader-dir>\reader_interactive.html
```

For offline MathJax:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --mathjax-url <local-mathjax-script>
```

If this command fails, do not produce a preview HTML. Complete the missing translation, figure/table cards, LaTeX formulas, or block-specific notes, then rerun the same `reader_interactive.html` command.

After a successful generation, run the adversarial HTML audit from the project root:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>
```

Do not report the reader as complete until this audit passes. It checks Algorithm cards instead of summaries, MathJax/formula integrity, Source Page Index links, knowledge-mark metadata, concept coverage, reader-notes pollution, `Save mark` panel closing, and feedback-copy fallback.

If Source Page Index links do not open, inspect the generated `href` values first. They must be plain relative paths such as `assets/source_pages/page-01.png`; generated spans such as `<span class="math-inline">` inside a link target mean the HTML renderer annotated a file path and the reader must be regenerated after fixing the renderer.

## Import Reader Feedback

Reader HTML feedback is manual-export only. In the browser:

1. Click a highlighted concept or select text and click `Annotate / 自由标注`.
2. Fill status/question/context fields.
3. Click `Save mark`.
4. Confirm the saved item appears in the feedback panel's saved-annotation list and, when a source block is detected, as a badge in the page.
5. Delete mistakes with `Delete current` or the row-level `Delete` button in the saved-annotation list.
6. After finishing the paper, click `Download feedback JSON` to export all saved items.

Then import the downloaded JSON:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --feedback <reader_feedback.json>
```

Alternative: click `Copy feedback for Codex`, paste the payload into Codex, and let Codex apply the `reader-learner` update rules.

If browser clipboard permissions block copying, use the visible fallback textarea populated by `Copy feedback for Codex`; it contains the same JSON payload.

Important: feedback saved in the HTML page is in-memory. Refreshing or closing the page before export may lose unsaved/unexported feedback.

The learner profile uses schema v2. Imports should keep stable concept IDs in `concepts`, raw selected text and questions in `events`, source paths/URLs in `sources`, and unclear or learning items in `review_queue`.

## Generate Feedback Explanation Report

Run this after importing feedback with `reader-learner`, so the report can use the updated personal knowledge boundary:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py --feedback <reader_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

Default outputs are `feedback_explanations.md` and `feedback_explanations.html` next to the feedback JSON's reader bundle. The reports keep concept-click feedback, free-form annotations, selected Chinese/English text, source block IDs, and profile status.

Explicit HTML output:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py --feedback <reader_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --output <reader-dir>\feedback_explanations.md --html-output <reader-dir>\feedback_explanations.html
```

For a real derivation/research report, use the generated `feedback_research_context.md` as the evidence pack, author `feedback_research_deep_dive.md`, then render:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\render_research_deep_dive_html.py --input <reader-dir>\feedback_research_deep_dive.md --output <reader-dir>\feedback_research_deep_dive.html
```

## Import AI + Quantum News Feedback

Use `skills/ai-quantum-news-briefing` for current AI/model/industry/regulation/academic/quantum news requests. State the exact date range, cite current sources, and save durable outputs under `news/<date-range>/` when producing files.

The briefing pipeline is end-to-end: candidate collection and `news_feedback_config.json` are intermediate artifacts only. A completed daily or multi-day briefing must end with an interactive HTML reader, full default-`unrated` feedback JSON, a Markdown briefing, a delta config, and an updated `news/_index/story_index.jsonl`. Use `C:\Users\SSS\Desktop\PAPER\news\2026-07-07_to_2026-07-09` as the sample output directory structure.

Use profile import only after the user explicitly marks briefing concepts or asks to record briefing keywords. Exposure-only keywords should be `unrated`.

For recurring daily briefings, use the delta-first story index to avoid repeating yesterday's items and to keep prompt context small. First get the compact recent-story context:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index C:\Users\SSS\Desktop\PAPER\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
```

After creating a source-grounded candidate `news_feedback_config.json`, rewrite it before rendering HTML:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py apply --config <candidate_news_feedback_config.json> --output <delta_news_feedback_config.json> --date <YYYY-MM-DD> --days 7 --continuing-mode one-line
```

Use `--continuing-mode skip` when the user asks for the shortest possible report. The delta output should use `今日新增`, `重大更新`, and `持续跟踪，一句话` sections; category remains an item-level tag for feedback/profile reports. Do not update the index at this stage: use `daily_pipeline.py run`, `verify`, and `finalize` so the index is committed only after all artifacts pass.

Generate an interactive briefing HTML when the user wants click/freeform feedback:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html>
```

In the HTML, click concepts or use `Annotate selection`, then `Save mark`, then `Download JSON` or `Copy for Codex`.

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
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
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json list
```

Mark one concept:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json mark --concept "ansatz" --status learning --note "Needs paper-specific explanation"
```

Review due or high-priority concepts:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json review
```

Migrate an old profile to schema v2 with a timestamped backup:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

## Import Chat Sessions Into Profile

Use this when the user has exported or copied ChatGPT/GPT/Claude/Deepseek conversations and wants them to contribute to the long-term learner/person profile. Prefer local `.txt`, `.md`, `.html`, or `.json` exports; do not rely on share URL fetching for reproducibility.

Collect sources, bounded evidence events, and per-conversation summaries:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions
```

Extract reviewable candidates:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py extract --events C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\events.jsonl --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
```

Propose a patch:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py propose --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --candidates C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json
```

Apply only after reviewing `profile_patch.json`:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py apply --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --patch C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

The skill writes concept-status candidates through strict `reader-learner` validation and writes non-concept user traits under `person_profile`. Review `profile_patch.json` before applying. Use `conversation_summaries.json` to inspect each conversation's `at_a_glance`, topic tags, explicit preferences, open questions, and action-like requests.

## Validate Scripts

## Daily Academic And Feedback Release Gate

For `daily_pipeline.py`, keep `analysis_language=zh-CN` and `academic_delivery.required` enabled with `minimum_items=5`. The normalized delta config must contain a dedicated academic section with five distinct formal paper records, each with a primary article/DOI/preprint URL and individual evidence fingerprint, plus an `academic_search` HTTP-evidence ledger spanning PRL, PRA, PRX, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL, Quantum Journal, and arXiv. Label any paper from the wider context window with its actual date; do not describe it as a current-window publication.

Before `finalize`, run the strict config audit. It blocks English-only `facts`/`judgment`/`relevance`, encoding-corrupted Chinese (`U+FFFD` or corruption-pattern `?`), and insufficient academic delivery. On failure, rebuild the UTF-8 input from source records; never repair strings with global replacements or publish a visually rendered but semantically corrupted HTML file.

The interactive briefing must initialize browser state from embedded `initial_feedback_items`. Before any click, `Download JSON` must export exactly the complete automatic concept set with `default_status: "unrated"`; after edits, it exports the same identities with user changes overlaid. Removing an automatic item restores the baseline; freeform annotations remain removable.

```powershell
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\nature-reader\scripts\complete_reader_bundle.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\profile_v2.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\render_research_deep_dive_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\demo-skill\scripts\create_demo.py
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\test_reader_e2e.py
```

## Validate Skills

```powershell
python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\reader-skill
python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\reader-learner
python C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill
python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing
python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile
python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\utils\demo-skill
```

## Sync And Validate The Persistent Visible Wiki

Run these commands from `C:\Users\SSS\Desktop\PAPER`. The sync pipeline never mutates the learner profile. It creates the missing concise public projections for every stable profile concept and every profile source, then validates coverage.

```powershell
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
python .\skills\reader-learner\scripts\lint_visible_wiki.py --profile .\.agents\reader-learner\knowledge_profile.json --wiki .\.agents\wiki --strict --require-profile-coverage
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>
```

The reader/news commands first invoke the existing strict importer (which backs up the profile) and only sync the visible wiki after a successful import. Open `C:\Users\SSS\Desktop\PAPER\.agents\wiki` as its own Obsidian vault. Use `maps/Profile Coverage.md` to confirm the projection and `maps/Evidence Map.md` for claim-to-source navigation.

## Regenerate Project Agent Context

Use this only when project structure or workflow changes:

```powershell
python D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill\scripts\generate_project_agents.py C:\Users\SSS\Desktop\PAPER --out-dir .agents --force
```

After running the generator, manually revise `.agents/*.md`; the generator's first pass is intentionally conservative. It should not overwrite `.agents/reader-learner/`, but verify outputs before and after running it.

## Risky Operations

Ask the user before:

- moving/deleting corpus PDFs;
- overwriting generated reader bundles;
- rewriting `.agents/reader-learner/knowledge_profile.json`;
- running large OCR jobs or network-heavy downloads;
- converting many PDFs in batch.

Do not open, print, copy, summarize, upload, or modify any suspected key/password/token/credential file. The learner profile is user learning data, not credential material, and should still be handled only through the documented reader-learner workflow.
