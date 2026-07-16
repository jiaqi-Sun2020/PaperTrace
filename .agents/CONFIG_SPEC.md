# Config Spec

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-07-16

## Primary Pipeline Selection

The project exposes four distinct primary pipelines with different terminal contracts:

| Pipeline | Terminal contract |
|---|---|
| Paper Reader HTML | audited `<reader-dir>/reader_interactive.html`; bundle/ledger success is intermediate |
| AI + Quantum Daily Briefing Release | final strict verify of published briefing HTML plus full feedback/Markdown/config/manifest/story-index release set |
| Local Chat-to-Profile Import | human-reviewed `profile_patch.json` applied with backup through strict `reader-learner` validation |
| Adaptive Teaching Decision & Evidence Loop | a validated one-topic lesson completes a lesson request; full evidence return additionally requires actual performance, validated `teaching_feedback.json`, and delegated backed-up atomic import |

Do not reuse one pipeline's terminal status for another. In particular, `complete_reader_bundle.py` cannot certify HTML delivery, `briefing_to_feedback_html.py` alone cannot certify daily publication, chat candidate extraction cannot certify profile mutation, and lesson generation cannot certify mastery or teaching-feedback import.

## Config Surfaces

There is no central package config such as `pyproject.toml`, `package.json`, or CI config at the project root. Configuration is mostly expressed through script arguments and profile JSON.

## Learner Profile

Default profile:

```text
D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
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
- `person_profile`: optional long-term non-concept user profile surface populated from reviewed chat conversation imports, such as learning preferences, research interests, workflow preferences, project rules, and writing style.
- `status`: one of `mastered`, `known`, `learning`, `unknown`, `unrated`.
- `facet_status`: finer-grained status by issue type, such as `definition`, `paper_usage`, `math_derivation`, `terminology`, `physical_intuition`, or `visualization`.
- `learning_needs`: compact list of what kind of help the user needs for a concept.
- `event_ids` / `source_ids`: links from compact concept entries back to raw evidence.
- `reading_sessions`: processed reader sessions.

Do not use full selected text, long Chinese sentences, or paragraph excerpts as concept keys. Put those strings in `events`.

## Adaptive Teaching Workspace

Private workspace:

```text
D:\AI\PaperTrace\.agents\adaptive-teach
```

Owned by `skills/adaptive-teach/`, with `TEACHING-MISSION.md`, `teaching-settings.json`, session artifacts, and only regenerated `derived/` reports. It may contain Mission relevance, explicit prerequisite maps, lesson duration, language, and review preferences; it must not duplicate profile concepts, statuses, events, sources, or `review_queue`.

`teaching_feedback.json` is a handoff, not learner memory. It requires a stable existing concept ID, existing profile source refs, actual evidence with prompt-use information, a status proposal, a transparent proposed review schedule, and `provenance: adaptive-teach`. `reader-learner` validates it and owns the backup/atomic write.

## Chat Conversation Import CLI

Script:

```text
skills/utils/chat-knowledge-profile/scripts/init_knowledge_profile.py
```

Intermediate import directory:

```text
D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions
```

Important commands:

| Command | Meaning |
|---|---|
| `collect --input <file-or-folder> --output <dir>` | Read local `.txt`, `.md`, `.html`, or `.json` chat conversation exports and write `sources.jsonl`, `events.jsonl`, `conversation_summaries.json`, and `manifest.json`. URLs are not fetched; share pages must be saved locally first. |
| `extract --events <events.jsonl> --output <profile_candidates.json>` | Extract reviewable candidate concept statuses, learning preferences, research interests, workflow preferences, project rules, and writing style signals. |
| `propose --profile <knowledge_profile.json> --candidates <profile_candidates.json> --output <profile_patch.json>` | Build a reviewable patch and reader-feedback handoff for concept-status candidates. |
| `apply --profile <knowledge_profile.json> --patch <profile_patch.json> --backup` | Apply a reviewed patch with a timestamped backup. Concept candidates go through strict `reader-learner` handoff validation; non-concept candidates go under `person_profile`. |

Generated files:

- `sources.jsonl`: one source conversation/file per line.
- `events.jsonl`: bounded evidence events with role, source, turn index, and text hash.
- `conversation_summaries.json`: per-conversation `at_a_glance`, topic tags, explicit preferences, open questions, action-like requests, and model metadata for review/navigation.
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

The active primary model in the current user-facing session must directly author Chinese translation, block-specific notes, and LaTeX reconstruction. A missing local model backend, translation package, or API SDK is not a valid blocker, and those tools must not be substituted as the formal content author.

Strict final generation should fail when source-map figure/table entries have no figure/table card, equation blocks lack LaTeX display math, or notes contain generic scaffolding. Fix those structural defects before generating `reader_interactive.html`.

Strict final generation should also fail when source algorithms are summarized instead of rendered as full Algorithm cards, when Source Page Index links contain generated HTML/math markup inside `href`, or when the feedback UI lacks a copy fallback textarea.

Full-paper readers require `reader_wiki/paper_summary.json` (`schema_version: 1`, `language: zh-CN`). It contains an `overview` object plus `what_it_does`, `how_it_works`, `why_it_matters`, and `evidence_and_limitations` arrays. Every object has substantive Chinese `text` and non-empty `source_anchors` that resolve to formal completion records. This file is authored during semantic completion; reader-skill validates/renders it but does not synthesize it.

For PDF inputs, `source_map.pages` is the immutable page-view manifest. Each row contains a positive `page`, a bundle-relative `assets/source_pages/...` image, and its SHA-256. Formal HTML renders one synchronized left-side page viewer, adds `data-source-page` to source blocks, and supplies independent Original/source-page collapse controls. Absolute paths, traversal, missing/hash-stale pages, full-page figure cards, inaccessible controls, or print-hidden Original panels fail publication.

Post-generation audit:

```powershell
python D:\AI\PaperTrace\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>
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
python D:\AI\PaperTrace\skills\reader-learner\scripts\migrate_knowledge_profile_v2.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
python D:\AI\PaperTrace\skills\reader-learner\scripts\update_learner_profile.py --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json review
```

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
| `news_delta.py apply --config <candidate.json> --output <delta.json>` | Rewrite a candidate config into delta-first sections without mutating the story index. |
| `rank_briefing_candidates.py --config <candidate.json> --output <ranked.json>` | Apply the evidence gate, deterministic academic/social scores, quotas, and diversity selection without publishing. |
| `daily_pipeline.py run/verify/finalize` | Stage, verify including UTF-8/visible-text integrity, publish the Markdown/interactive HTML/full feedback bundle, and atomically upsert the story index only after final verification. |
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

- `news_feedback_version`: `1`.
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
- `items[].source_class`: normalized evidence/source class used by ranking, such as `formal_academic`, `arxiv_preprint`, `official_primary`, `government_or_regulator`, or `reputable_media`.
- `items[].organization`: normalized organization identity used by social-news concentration caps.
- `items[].topic`: normalized topic identity used by diversity caps.
- `items[].corroborating_source_count`: optional count of independently checked corroborating sources.
- `items[].ranking_signals`: optional bounded `0..1` evidence-backed overrides for named score components; absent values use deterministic text/metadata fallbacks.
- `items[].ranking`: pipeline-written publication evidence containing algorithm version, eligibility/selection state, component scores, penalties, base score, final rank, novelty, source class, organization, and topic.
- `items[].user_question`: user's exact question when available.

## News Briefing Encoding And Text Integrity

News briefing configs are UTF-8 data contracts. Human-readable fields must survive a UTF-8 round trip without replacement. Producers must use UTF-8-aware file I/O (`utf-8-sig` input compatibility, UTF-8 output, `ensure_ascii=False`) and must not send Chinese source text through a legacy PowerShell/code-page here-string.

The shared normalizer blocks `U+FFFD` and high-density literal `?` in titles, facts, judgments, relevance, source excerpts, section titles, and concepts. URL query delimiters are not human-text corruption. If the check fails, regenerate from the original candidate/source; never strip `?` or rewrite a damaged string heuristically.

`story_index.jsonl` is historical input, not trusted prose. Delta compaction must omit a corrupt prior summary and mark the omission rather than copying mojibake into current Markdown/HTML. Final `daily_pipeline.py verify --strict` audits visible HTML text as well as the config.

## Academic Delivery Contract

Daily configs accept:

```json
"analysis_language": "zh-CN",
"academic_delivery": {"required": true, "minimum_items": 7, "target_items": 8, "maximum_items": 8, "minimum_new_items": 4, "maximum_new_items": 6, "minimum_non_arxiv_items": 2, "maximum_continuing_items": 3, "context_days": 7},
"social_delivery": {"minimum_items": 10, "target_items": 12, "maximum_items": 14, "minimum_new_or_material_update": 7, "maximum_continuing_items": 3, "minimum_reputable_media_items": 3, "minimum_primary_official_items": 3, "minimum_source_classes": 3, "maximum_items_per_organization": 2, "maximum_items_per_topic": 3},
"ranking_policy": {"enabled": true, "algorithm_version": "news-ranker-v1"}
```

`analysis_language` defaults to `zh-CN` for daily pipeline runs. In that mode every item needs Chinese `facts`, `judgment`, and `relevance`; titles and technical proper nouns may retain their source language.

`daily_pipeline.py run` supplies and enforces the ranked daily defaults. Academic delivery publishes 7–8 distinct paper records, including 4–6 `new`, at least two non-arXiv formal papers, and no more than three `continuing` items. Social delivery publishes at least 10 items (target 12, maximum 14), at least seven `new`/`material_update`, at most three `continuing`, and enforced source/organization/topic diversity. Every candidate must have a direct HTTPS source, publication date, evidence level, evidence fingerprint, and complete fact/judgment/relevance fields before it is eligible. A venue landing page, candidate-only AI HOT record, duplicate story, or company platform update cannot masquerade as a paper.

`news-ranker-v1` writes item-level `ranking` evidence plus top-level `ranking_policy` and `ranking_manifest`. The manifest records candidate, eligible, and selected counts; quota metrics; a deterministic selection trace; and explicit exclusion reasons. The normalizer, delta pass, HTML config, manifest verification, and adversarial audit must preserve and validate these fields. AI HOT `score` is not a final ranking score.

The academic score totals 100 points: evidence 25, novelty 15, technical contribution 20, specificity 15, relevance 15, and reproducibility 10. The social score totals 100 points: evidence 25, public impact 20, materiality 15, novelty 15, relevance 10, corroboration 10, and specificity 5. Selection uses the base score plus quota/source/topic bonuses minus text similarity and repeated organization/topic penalties. Deterministic tie-breaking uses the score, publication date, and evidence fingerprint; the same config and story index must produce the same manifest.

## News HTML Feedback Contract

The canonical briefing is section-based. HTML derives its flat runtime item map from `sections`, embeds the complete automatic feedback set, and initializes every automatic concept as `unrated`. `Download JSON` must work before individual saves and export the exact initial identity set plus edits. Deleting an automatic item restores it; only freeform annotations are removable.

## News Story Index

Default index:

```text
D:\AI\PaperTrace\news\_index\story_index.jsonl
```

Each JSONL record is intentionally small: `story_id`, `last_seen`, `status`, one-line `summary`, `source_url`, `category`, concepts, and briefing path/date. This file is for recurring-news deduplication only; it is not learner memory and should not store user understanding status.

## Visible Wiki Contract

The persistent human-facing vault is `D:\AI\PaperTrace\.agents\wiki`. Its public pages use stable IDs, `visibility: public-wiki`, and one of `concept`, `entity`, `theme`, `question`, `synthesis`, `claim`, or `source` as `type`.

- `source_refs` lists public `source.*` page IDs for visible evidence navigation.
- `profile_source_refs` lists internal learner-profile `src-*` IDs only for source-summary projection.
- `knowledge_status` is allowed only on concept pages and must exactly match the profile's explicit status.
- Public pages must not contain absolute drive paths, raw feedback/event payloads, or unresolved `freeform-annotation-*` / `concept-*` profile candidates.
- Public relation types are `prerequisite`, `supports`, `contradicts`, `extends`, `example-of`, `evidence-for`, and `about`.

`skills/reader-learner/scripts/compile_visible_wiki.py` is read-only with respect to the profile. It updates only page-managed projection blocks, generated navigation/maps, and `.agents/wiki/_internal/projection_manifest.json`.

## Environment Variables

No required environment variables were detected in the project files.

## Secrets

No secret files were detected. Do not add API keys or credentials to `.agents`, README files, exported feedback JSON, or generated reports.

Except for permitted learner-profile reads/updates, agents must not open, print, copy, summarize, upload, or modify suspected credential files, including files or paths named like `.env`, `secret`, `secrets`, `credential`, `credentials`, `token`, `password`, `passwd`, `apikey`, `api_key`, `private_key`, `id_rsa`, `.pem`, `.p12`, `.pfx`, cookies, or session stores.
