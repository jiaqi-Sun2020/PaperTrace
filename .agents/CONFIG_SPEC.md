# Config Spec

- Project root: `C:\Users\SSS\Desktop\PAPER`
- Last reviewed: 2026-07-05

## Config Surfaces

There is no central package config such as `pyproject.toml`, `package.json`, or CI config at the project root. Configuration is mostly expressed through script arguments and profile JSON.

## Learner Profile

Default profile:

```text
C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

Owned by:

```text
skills/reader-learner/
```

Important fields:

- `version`: current learner schema version. v2 separates concepts, raw history, sources, and review scheduling.
- `concepts`: stable concept profile map keyed by canonical concept IDs such as `ansatz`, `tdse`, or `two-electron-unitary`.
- `events`: raw feedback and annotation history. Store selected Chinese/English text, original context, translated context, user questions, and legacy notes here.
- `sources`: deduplicated source index for papers, reader bundles, and news briefings.
- `review_queue`: learning schedule for high-frequency or recent `unknown` / `learning` items.
- `person_profile`: optional long-term non-concept user profile surface populated from reviewed GPT conversation imports, such as learning preferences, research interests, workflow preferences, project rules, and writing style.
- `status`: one of `mastered`, `known`, `learning`, `unknown`, `unrated`.
- `facet_status`: finer-grained status by issue type, such as `definition`, `paper_usage`, `math_derivation`, `terminology`, `physical_intuition`, or `visualization`.
- `learning_needs`: compact list of what kind of help the user needs for a concept.
- `event_ids` / `source_ids`: links from compact concept entries back to raw evidence.
- `reading_sessions`: processed reader sessions.

Do not use full selected text, long Chinese sentences, or paragraph excerpts as concept keys. Put those strings in `events`.

## GPT Conversation Import CLI

Script:

```text
skills/utils/init-knowledge-profile/scripts/init_knowledge_profile.py
```

Intermediate import directory:

```text
C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions
```

Important commands:

| Command | Meaning |
|---|---|
| `collect --input <file-or-folder> --output <dir>` | Read local `.txt`, `.md`, `.html`, or `.json` GPT conversation exports and write `sources.jsonl`, `events.jsonl`, and `manifest.json`. URLs are not fetched. |
| `extract --events <events.jsonl> --output <profile_candidates.json>` | Extract reviewable candidate concept statuses, learning preferences, research interests, workflow preferences, project rules, and writing style signals. |
| `propose --profile <knowledge_profile.json> --candidates <profile_candidates.json> --output <profile_patch.json>` | Build a reviewable patch and reader-feedback handoff for concept-status candidates. |
| `apply --profile <knowledge_profile.json> --patch <profile_patch.json> --backup` | Apply a reviewed patch with a timestamped backup. Concept candidates go through `reader-learner`; non-concept candidates go under `person_profile`. |

Generated files:

- `sources.jsonl`: one source conversation/file per line.
- `events.jsonl`: bounded evidence events with role, source, turn index, and text hash.
- `profile_candidates.json`: extracted but unapplied candidates.
- `profile_patch.json`: reviewable operations and concept-status handoff.

Do not import suspected credential files. Do not apply unreviewed patches.

## Reader-Skill CLI

Script:

```text
skills/reader-skill/scripts/markdown_reader_to_html.py
```

Important options:

| Option | Meaning |
|---|---|
| `--output <path>` | Write HTML to a specific file. |
| `--profile <path>` | Use an explicit learner profile. |
| `--agent-dir <path>` | Override nearest `.agents` discovery. |
| `--no-feedback-ui` | Disable click/freeform feedback controls. |
| `--no-knowledge-annotations` | Disable learner-profile highlighting. |
| `--no-embed-assets` | Keep local image links instead of embedding image data URIs. |
| `--math-renderer none` | Keep TeX source visible and do not load MathJax. |
| `--mathjax-url <path-or-url>` | Use a local or remote MathJax script. |

The formal converter has no draft-bypass option. If `paper.md` still contains placeholders, summary translations, missing figure/table cards, noisy formulas, or generic notes, fix the bundle before generating HTML.

Direct translation is the default route for completing a final reader. A missing local model backend, translation package, or API SDK is not a valid blocker; translate and update `paper.md` / `source_map.json` directly before running strict HTML generation.

Strict final generation should fail when source-map figure/table entries have no figure/table card, equation blocks lack LaTeX display math, or notes contain generic scaffolding. Fix those structural defects before generating `reader_interactive.html`.

Strict final generation should also fail when source algorithms are summarized instead of rendered as full Algorithm cards, when Source Page Index links contain generated HTML/math markup inside `href`, or when the feedback UI lacks a copy fallback textarea.

Post-generation audit:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>
```

This command is part of the formal reader pipeline for completed `reader_interactive.html` outputs.

## Reader-Learner CLI

Scripts:

```text
skills/reader-learner/scripts/profile_v2.py
skills/reader-learner/scripts/import_reader_feedback.py
skills/reader-learner/scripts/update_learner_profile.py
skills/reader-learner/scripts/migrate_knowledge_profile_v2.py
```

Status values:

| Status | Meaning |
|---|---|
| `mastered` | User can explain and apply the concept without help. |
| `known` | User understands it in this paper context. |
| `learning` | User partly understands and benefits from reminders. |
| `unknown` | User needs explanation before reading fluently. |
| `unrated` | Seen in a paper but not judged yet. |

Useful commands:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\update_learner_profile.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json review
```

## Read-Feedback CLI

Script:

```text
skills/read-feedback-skill/scripts/build_feedback_explanation_report.py
skills/read-feedback-skill/scripts/render_research_deep_dive_html.py
```

Important options:

| Option | Meaning |
|---|---|
| `--feedback <path>` | Feedback JSON exported from reader HTML. |
| `--profile <path>` | Explicit learner profile; defaults to nearest `.agents/reader-learner/knowledge_profile.json`. |
| `--reader-dir <path>` | Explicit reader bundle directory. |
| `--source-map <path>` | Explicit source map; defaults to `<reader-dir>/source_map.json`. |
| `--output <path>` | Output Markdown report; defaults to `<reader-dir>/feedback_explanations.md`. |
| `--html-output <path>` | Output HTML report; defaults to the Markdown output path with `.html` suffix. |
| `--no-html` | Write Markdown only. |
| `--context-output <path>` | Output research context-pack Markdown path; defaults to `<reader-dir>/feedback_research_context.md`. |
| `--no-context` | Do not write the research context pack. |
| `--mathjax-url <path-or-url>` | MathJax script for HTML formula rendering; use `none` to disable. |

The report generator reads profile data but does not mutate `.agents`.

Deep-dive HTML renderer:

| Option | Meaning |
|---|---|
| `--input <path>` | Authored `feedback_research_deep_dive.md`. |
| `--output <path>` | Output HTML; defaults to the input path with `.html` suffix. |
| `--mathjax-url <path-or-url>` | MathJax script for formula rendering; use `none` to disable. |

## AI + Quantum News Feedback CLI

Scripts:

```text
skills/ai-quantum-news-briefing/scripts/briefing_to_feedback_html.py
skills/ai-quantum-news-briefing/scripts/news_delta.py
skills/ai-quantum-news-briefing/scripts/import_news_feedback.py
```

Important options:

| Option | Meaning |
|---|---|
| `briefing_to_feedback_html.py --config <path>` | Read a source-grounded briefing feedback config. |
| `briefing_to_feedback_html.py --output <path>` | Write interactive HTML with click/freeform feedback export. |
| `news_delta.py context --index <path> --date <YYYY-MM-DD> --days 7` | Print compact recent-story context for the next daily briefing prompt. |
| `news_delta.py apply --config <candidate.json> --output <delta.json> --update-index` | Rewrite a candidate config into delta-first sections and optionally append emitted stories to `news/_index/story_index.jsonl`. |
| `--feedback <path>` | Native `news_feedback.json` file. |
| `--profile <path>` | Explicit learner profile path. |
| `--reader-learner-importer <path>` | Override the delegated `reader-learner` importer. |
| `--normalized-output <path>` | Write the normalized reader-feedback handoff JSON to a specific path. |
| `--no-import` | Only write normalized output; do not mutate the profile. |

News feedback should use `source_kind: news_briefing` after normalization. Do not change a concept to `known`, `unknown`, `learning`, or `mastered` unless the user explicitly said so; exposure-only concepts should be `unrated`. The normalized reader-feedback handoff should preserve `briefing_title`, `date_range`, source title/URL, category, and a short source excerpt whenever available.

## Reader Feedback JSON

Generated manually from interactive HTML with `Download feedback JSON`, or copied with `Copy feedback for Codex`.

Persistence rules:

- The HTML page stores feedback in browser memory for the current page session.
- Only items saved with `Save mark` are included in export/copy output.
- Refreshing or closing the page before export may lose current-session feedback.
- `reader_feedback.json` is an intermediate handoff artifact; the long-term source of truth is `.agents/reader-learner/knowledge_profile.json` after import.

Important fields:

- `reader_feedback_version`: feedback payload version.
- `paper_title`: paper associated with the reading session.
- `reader_path`: reader bundle path.
- `items`: saved feedback entries.
- `items[].concept`: concept, phrase, or selected text label.
- `items[].status`: `mastered`, `known`, `learning`, `unknown`, or `unrated`.
- `items[].user_question`: user's exact free-form question.
- `items[].confusion_type`: question category such as term definition, paper usage, math step, or algorithm step.
- `items[].source_excerpt`: selected or nearby source context.
- `items[].selected_language`: `original` or `translation` when the selected text came from a bilingual panel.
- `items[].original_context`: English/source side of the bilingual block when available.
- `items[].translation_context`: Chinese translation side of the bilingual block when available.
- `items[].block_id`: source anchor when detected.

## News Feedback JSON

Generated by Codex from explicit user feedback about an AI+quantum briefing, not by passive news exposure.

Important fields:

- `news_feedback_version`: currently `1`.
- `briefing_title`: title/date of the briefing.
- `date_range`: exact date range covered.
- `briefing_path`: optional saved briefing path.
- `items[].concept`: concept/topic to update.
- `items[].status`: `mastered`, `known`, `learning`, `unknown`, or `unrated`.
- `items[].category`: AI/quantum/news category.
- `items[].source_title`: source headline/title.
- `items[].source_url`: source URL.
- `items[].source_excerpt`: short grounding excerpt from the briefing/source.
- `items[].story_id`: stable identifier for recurring story deduplication. If omitted, `news_delta.py` derives it from source URL/title/concepts.
- `items[].novelty`: `new`, `material_update`, `continuing`, or `duplicate`.
- `items[].delta_note`: short reason for expanding or compressing this story.
- `items[].user_question`: user's exact question when available.

## News Story Index

Default index:

```text
C:\Users\SSS\Desktop\PAPER\news\_index\story_index.jsonl
```

Each JSONL record is intentionally small: `story_id`, `last_seen`, `status`, one-line `summary`, `source_url`, `category`, concepts, and briefing path/date. This file is for recurring-news deduplication only; it is not learner memory and should not store user understanding status.

## Environment Variables

No required environment variables were detected in the project files.

## Secrets

No secret files were detected. Do not add API keys or credentials to `.agents`, README files, exported feedback JSON, or generated reports.

Except for permitted learner-profile reads/updates, agents must not open, print, copy, summarize, upload, or modify suspected credential files, including files or paths named like `.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, cookies, or session stores.
