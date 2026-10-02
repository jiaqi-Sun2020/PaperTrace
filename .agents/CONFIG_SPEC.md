# Config Spec

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-09-27

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

Formal directory controller:

```text
skills/reader-skill/scripts/build_formal_reader_batch.py
```

| Option | Meaning |
|---|---|
| `--pdf-dir <path>` | Discover immediate PDFs; the first run freezes the selected paths and hashes. |
| `--reader-root <path>` | Store reader bundles and generated `.papertrace_jobs/` workflow state under this project root. |
| `--max-papers N` | Select only the deterministic first N PDFs; required when the user limits the batch. |
| `--resume` | Resume the exact frozen selection and increment its heartbeat/attempt count. |
| `--work-packet-size N` | Bound `next_authoring_packet.json` to N source record IDs. |
| `--agent-continuation` | Persist and enforce the continuation guard with tool-safe exit 0 for ordinary incomplete work. |
| `--strict-exit` | Return 1 for ordinary incomplete work in CI; mutually exclusive with `--agent-continuation`. |

The controller stores `orchestration_state.json` and
`last_batch_report.json` under
`<reader-root>/.papertrace_jobs/<job-id>/`. The state schema contains workflow
metadata only: selected PDF identity/hash, attempts, heartbeat, active phase,
active paper, next command, last guard, and terminal blocker. It must not
contain source prose, translations, feedback, profile data, credentials, or a
second semantic ledger.

`reader_wiki/source_map_lock.json` binds the source-map and source-PDF hashes
after all figure/table/algorithm identities have been registered. After this
lock, object assets may be completed but source identities cannot change.
`reader_wiki/next_authoring_packet.json` contains a bounded ordered list of
pending/invalid stable IDs plus preflight/formal diagnostics; it never authors
semantic content.

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

Formula content uses an explicit-boundary contract in every block type: raw TeX commands, ASCII subscript/superscript syntax, and split PDF math fragments outside `\(...\)`/`$...$`/display delimiters fail in both Original and Chinese. Each `\[...\]`/`$$...$$` contains one logical formula and duplicate plaintext extraction is absent. Independent equations must be separate displays; packed `\quad`/`\qquad`, `align`/`gather`, and literal `\n` fail. `object_metadata.bilingual_math_contract: exact-v1` opts a block into identical ordered Original/Chinese components and inline/display presentation; do not impose exact parity on explanatory prose blocks that legitimately contain additional authored math.

For any immutable source row whose extraction contains layout-math residue—including paragraphs and captions, not only formula rows—bootstrap sets `object_metadata.source_math_inventory_required: true`. Formal completion then requires `object_metadata.source_math_inventory` with `contract: source-math-inventory-v1`, `status: complete`, and ordered component `{id, presentation, signature}` objects. Original and Chinese must both match every inventory signature exactly. Formula repair overrides are source-bound exact replacements; they must not globally strip delimiters or append an isolated formula to otherwise noisy prose.

Algorithms use `representation: latex_compiled_algorithm`. Each record and object-inventory row binds bundle-relative `latex_source_path`, `compiled_asset_path`, and `compile_manifest_path`; completion metadata also binds SHA-256 values, compile engine, translated-comment count, and numbered-step count. Require/Ensure and executable steps remain in the source language. Chinese is permitted only in `\Comment{...}` for an actual source comment. The compile manifest must declare `contract: latex-compiled-algorithm-v1`, a passing status, hashes for the `.tex`/`.svg`, and a numbered-state count equal to the source algorithm.

Full-paper readers require `reader_wiki/paper_summary.json` (`schema_version: 1`, `language: zh-CN`). It contains an `overview` object plus `what_it_does`, `how_it_works`, `why_it_matters`, and `evidence_and_limitations` arrays. Every object has substantive Chinese `text` and non-empty `source_anchors` that resolve to formal completion records. This file is authored during semantic completion; reader-skill validates/renders it but does not synthesize it.

For PDF inputs, `source_map.pages` is the immutable page-view manifest. Each row contains a positive `page`, a bundle-relative `assets/source_pages/...` image, and its SHA-256. Formal HTML renders an enlarged synchronized page viewer in a fluid, user-resizable left pane, a minimum-width center article, and resizable sticky Contents on the right. Source and Contents separators require pointer plus keyboard operation; every collapsed pane retains an accessible restore control; medium/narrow screens compact or stack without horizontal overflow. Opening annotation feedback must reserve wide-screen layout space or smaller-screen scroll safety so translation remains reachable. Absolute paths, traversal, missing/hash-stale pages, full-page figure cards, inaccessible controls, misplaced Contents, overlay-hidden translation, or print-hidden Original panels fail publication.

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
| `daily_pipeline.py run/verify/review-template/seal-review/finalize/status` | Stage a version-4 daily release, verify structure, author and seal source-bound release reviews, strictly verify, commit locally with a single-instance lock, and inspect evidenced coverage. Finalize may mirror to OSS only after approval. |
| `--feedback <path>` | Native `news_feedback.json` file. |
| `--profile <path>` | Explicit learner profile path. |
| `--reader-learner-importer <path>` | Override the delegated `reader-learner` importer. |
| `--normalized-output <path>` | Write the normalized reader-feedback handoff JSON to a specific path. |
| `--no-import` | Only write normalized output; do not mutate the profile. |

News feedback should use `source_kind: news_briefing` after normalization. Do not change a concept to `known`, `unknown`, `learning`, or `mastered` unless the user explicitly said so; exposure-only concepts should be `unrated`. The normalized reader-feedback handoff should preserve `briefing_title`, `date_range`, source title/URL, category, and a short source excerpt whenever available.

### Daily release protocol 4

The generated `news/_collection/<release-date>/authoring_packet_v4_<release-date>.json`
uses packet schema `version=2`, independently of pipeline protocol 4. It is a
deterministic, unreviewed projection of the preceding Shanghai day's academic
ledger and AI HOT pool. Social candidates come only from `sections[*].items`;
academic candidates retain the original `rows[*].matches` fields, source IDs and
JSON-pointer `_source_ref` anchors. `source_inputs` binds each input filename and
byte SHA-256. `candidate_counts` records `total`, `emitted`, `truncated` and
`full_source` per category. Each category emits at most 100 candidates in source
order; overflow remains in the full source, not an exclusion or a ranking result.
The packet preserves `ai_hot_window`, including qualified undated exclusions,
and `semantic_review_status=not_reviewed`; it establishes neither four-class
social coverage nor item-level truth. No generated timestamp is added.

Orchestration compares the full packet against a fresh projection. Missing,
version-1, invalid or stale packets become `authoring_packet_pending` and can be
rebuilt from valid cached evidence by `resume` without network. Unknown higher
versions are incompatible and cannot be overwritten. Input files are validated
for their actual covered day, source-family consistency and AI HOT window before
projection; existing publication validation and four social source-class gates
remain mandatory. `collection_ready` means both sources and the derived packet
are valid, with `action_required=true` for authoring/review or empty-pool
expansion. It never means the issue is published.

`academic_sources.v1.json` declares each adapter's source family, tier and capabilities. Current adapters include journal-specific APS feeds; Nature topic RSS; OpenReview/PMLR/JMLR; Quantum Journal; category arXiv; and optional/probationary Science, IOP, IEEE and AAAI discovery. Each row records retrieval, parsing, window and coverage-claim state separately. One malformed item is quarantined; a whole malformed response degrades only that source. A successful retrieval never proves a complete historical-day publication census or an article claim.

New CLI runs use `pipeline_version: 4`; historical versions 1–3 remain readable but require a current release review before first OSS upload or correction. A v4 manifest records `coverage.start` (inclusive), `coverage.end` (exclusive), `collection_completed_at`, index snapshot, required artifact paths and SHA-256 values. The scheduled 08:00 run covers the preceding complete Asia/Shanghai calendar day; `manifest.date` remains the release identifier, not proof of coverage. New manifests set `coverage_evidence_contract_version=3` and bind one ordered daily evidence record per covered calendar day. Multi-day backfills require explicit midnight boundaries.

Each candidate-config `coverage_evidence` row has `date`, `academic_search`, `academic_search_ref`, `social_search`, and `social_search_ref`. Each reference is `sha256:` plus SHA-256 of its corresponding object serialized as UTF-8 JSON with sorted keys, no ASCII escaping, and compact separators. New v4 academic objects use `academic_search_version=4`, an exact one-day `date_range`, capability-aware source rows and both core family gates. Historical v3 rows remain readable under their original per-venue contract. Science may be `skipped_unavailable`; the reader-visible notice says the journal was not covered and never claims zero publications. Science RSS HTTP success and complete Crossref pagination remain discovery evidence only. The social object carries the exact Asia/Shanghai `[00:00, next 00:00)` window and content-bound source-class evidence. AI HOT supplies candidates, not original-source support for selected news.

`run` and manifest verification enforce this content-bound record; `finalize` inherits strict verification and standalone OSS `publish` requires the release's current contract before a first upload or correction. Completed historical releases remain locally readable but cannot use legacy evidence for a new remote delivery. Hash/shape validation cannot prove scientific truth.

Publication review uses `opening_story_review_<date>.json`, `news_content_review_<date>.json`, and `release_preflight_audit_<date>.json`, all named and hashed in the manifest. New manifests retain `required_story_review_protocol=3`; this review protocol is separate from `opening_story.version=3`. The news review judges every selected item's facts, judgment and relevance against source excerpts. Automatic review records establish coverage and traceability, not scientific truth.

The local commit and OSS publisher share a cross-process release lock. A local release may be complete while remote delivery is pending or disabled; `finalize --require-remote` returns nonzero unless the OSS acceptance check succeeds. Publisher recovery compares the reviewed local HTML, remote HTML, homepage date/link and receipt; it skips unchanged objects, repairs a missing receipt or homepage, and never moves the homepage backward for a historical backfill. Same-date content replacement requires an explicit correction reason, old-content reference and fresh review. Site/link verification failure latches remote publishing disabled until a manual `enable`. The read-only `doctor` checks current-process website, ossutil and Bucket-read capability without changing that lock or proving upload permission; standalone `publish` exits nonzero for disabled/pending/failed delivery. Offline daily `status` uses `remote_verified: null` and `remote_status: not_checked`, even if the local receipt matches; opt-in `--online` checks public bytes and homepage and distinguishes unreachable from mismatch. OSS credentials remain only in the user's ossutil profile; the ignored local route config, feedback and learner data are not release artifacts.

## Reader Feedback JSON

Generated manually from interactive HTML with `Download feedback JSON`, or copied with `Copy feedback for Codex`.

Persistence rules:

- The HTML page stores explicit auto-saved marks and current form state in a browser-local recovery envelope keyed as `paper.reader.feedback-draft.v1:<source-map-sha256>`.
- The recovery envelope is internal, contains no absolute path in its storage key, and does not change the exported feedback-v2 schema.
- Only explicit status or field edits are included in export/copy output; merely opening Feedback or dismissing a selection creates no item.
- Reopening the same reader restores valid same-paper marks and drafts; invalid, oversized, mismatched, unavailable, or quota-failed storage is ignored with a visible warning rather than blocking JSON export.
- A successful download or clipboard copy asks whether to clear the browser recovery copy. Clipboard fallback without a successful write never clears it.
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

## Daily Opening Story And Worked Example

Every new `daily_pipeline.py run` forces:

```json
"story_delivery": {
  "required": true,
  "worked_example_required": true,
  "position": "before_briefing"
}
```

New authoring uses `opening_story.version=3` (complete Fable). At least two
causally necessary background paragraphs precede a complete story. No total
character, sentence or paragraph ceiling applies; each normalized paragraph
retains the 2000-character transport boundary, rejecting overflow without
truncation. The entire story is visible before factual sections 1 -> 2 -> 3 -> 4;
only the complete worked example is collapsed in HTML.

Versions 1–4 retain their existing runtime normalization, validation and display;
v4 stays v4 with one or more paragraphs and its existing same-relation example
contract. Unknown versions fail. This authoring change is not a schema migration.
New Fable stories and examples retain the same bounded case and data identity;
examples require scenario, actual inputs, observable, justified steps, result,
check and non-conclusion. No formula is required for nonmathematical mechanisms.
Ranking, source binding, feedback identity and learner state do not change.
Structural checks do not certify semantic correctness or comprehension.

## Academic Delivery Contract

Publication contract v3 requires explicit `--date`, `academic_delivery.required=true`, and `ranking_policy.enabled=true`. Normal destinations are fixed to project `news/<date>/` and `news/_index/story_index.jsonl`; manifest paths are assertions, never write targets. Dates, run IDs, artifact names and symlinked publication components are checked before commit. An audited correction binds its reason, superseded HTML hash and old index-update identities, replacing only that release's index records.

For every selected new item, require article-level source evidence under `news/_collection/<covered-date>/source_captures/`. The staged `source_captures_<release-date>.json` artifact binds requested/final URLs, capture time, HTTP status, response/extracted-text digests, title and a short quote found in retrieved text. This is retrieval provenance, not semantic proof. A DOI resolver URL requires separate article-level venue evidence and a paper publication type; a dataset DOI cannot be a paper or social-news filler. New index entries retain DOI/arXiv IDs; similar titles alone do not establish identity. New `news-ranker-v2` scores source metadata rather than drafted prose. Legacy v1/v2 artifacts remain readable; first remote upload or correction requires regeneration and review under v3.

Daily configs accept:

```json
"analysis_language": "zh-CN",
"academic_delivery": {"required": true, "minimum_items": 6, "target_items": 8, "maximum_items": 8, "minimum_new_items": 4, "maximum_new_items": 8, "minimum_non_arxiv_items": 2, "maximum_continuing_items": 3, "context_days": 7},
"social_delivery": {"minimum_items": 6, "target_items": 12, "maximum_items": 12, "minimum_new_or_material_update": 4, "maximum_continuing_items": 3, "minimum_reputable_media_items": 3, "minimum_primary_official_items": 3, "minimum_source_classes": 3, "maximum_items_per_organization": 2, "maximum_items_per_topic": 3},
"ranking_policy": {"enabled": true, "algorithm_version": "news-ranker-v2"}
```

`analysis_language` defaults to `zh-CN` for daily pipeline runs. In that mode every item needs Chinese `facts`, `judgment`, and `relevance`; titles and technical proper nouns may retain their source language.

`daily_pipeline.py run` supplies and enforces the ranked daily defaults. Pipeline v4 publishes 6–8 distinct paper records, at least two non-arXiv formal papers, and no more than three `continuing` items. Social delivery publishes 6–12 items, at least four `new`/`material_update`, at most three `continuing`, and enforced source/organization/topic diversity. Every candidate must have a direct HTTPS source, publication date, evidence level, evidence fingerprint, and complete fact/judgment/relevance fields before it is eligible. A venue landing page, candidate-only AI HOT record, duplicate story, or company platform update cannot masquerade as a paper.

Historical `news-ranker-v1` and new `news-ranker-v2` write item-level `ranking` evidence plus top-level `ranking_policy` and `ranking_manifest`. The manifest records candidate, eligible, and selected counts; quota metrics; a deterministic selection trace; and explicit exclusion reasons. The normalizer, delta pass, HTML config, manifest verification, and adversarial audit must preserve and validate these fields. AI HOT `score` is not a final ranking score.

The academic score totals 100 points: evidence 25, novelty 15, technical contribution 20, specificity 15, relevance 15, and reproducibility 10. The social score totals 100 points: evidence 25, public impact 20, materiality 15, novelty 15, relevance 10, corroboration 10, and specificity 5. Selection uses the base score plus quota/source/topic bonuses minus text similarity and repeated organization/topic penalties. Deterministic tie-breaking uses the score, publication date, and evidence fingerprint; the same config and story index must produce the same manifest.

Historical v3 releases may contain `delivery_expansion.version=1`. New single-day pipeline-v4 releases use version 2, a separate 14-calendar-day academic lookback ledger, the 72-hour social window, content digests, source-family health, exclusions and original publication times. Only unattainable count and source-class lower bounds may be relaxed; one reviewed academic and one reviewed social item, upper bounds, article evidence, deduplication, content review and strict publication remain mandatory.

## Academic Source Capability Contract

### Academic search v4

New pipeline-v4 releases use `academic_search_version=4`, the public `academic_sources.v1.json` registry, `coverage_evidence_contract_version=3`, and `delivery_expansion.version=2`. Each source row records retrieval, parsing, date-window and coverage-claim state independently, plus candidate and quarantine counts. The release gate requires a healthy `quantum_publisher` family and a healthy `ai_peer_review` family; optional and probationary sources never become hard gates merely by returning HTTP 200. Historical v1–v3 evidence remains readable but is not silently upgraded.

Publication version routing is centralized in `publication_contracts.py`. New pipeline 2/3 releases require coverage contract 2; pipeline 4 requires contract 3 and `required_story_review_protocol=3`. Generation audits, manifest writing, local verification and first remote delivery enforce the same pair; unknown versions and mismatched pairs fail closed. Historical completed v1-v3 releases retain their declared legacy local evidence meaning; that compatibility does not permit a first upload or correction. Standalone config audits select the contract explicitly with `--coverage-contract-version` (3 for v4).

The registry is public and contains no proxy, credential or OSS profile. Machine-local allowlists may add `www.jmlr.org`, `iopscience.iop.org`, `ieeexplore.ieee.org`, `ojs.aaai.org`, and `api2.openreview.net`; local network configuration remains ignored by Git.

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

Actual semantic/Fable review, all social search classes and strict publication gates are unchanged. A recovery must preserve original source hashes and `not_reviewed` packet semantics. It must not create a release, backfill history, toggle OSS, mutate a profile or change a schedule. Unattended transport/write permission and an independent healthy AI publisher fallback still require actual environment evidence; interactive success does not establish those conditions.
