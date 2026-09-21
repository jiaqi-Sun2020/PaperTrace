# Changes

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-09-21

This file records dated implementation and local-release milestones. Durable boundaries belong in `AGENTS.md`, commands in `RUNBOOK.md`, data contracts in `CONFIG_SPEC.md`, and architecture/ownership in `ARCHITECTURE.md`.

## 2026-09-21

### Allegory cognitive-compression gates

- Promoted technical correctness and beginner comprehensibility to independent hard gates. Bridge Mode now runs the direct concrete case first and adds a local analogy only when it lowers cognitive load; Fable Mode keeps its causal setup but prefers the simplest familiar setting instead of literary or dramatic world-building.
- Added plain-language, self-explanation, cognitive-compression, literal-reconstruction, and predicted-follow-up checks, plus explicit replacement-rule handling for removal, truncation, projection, pruning, compression, and approximation.
- Moved detailed Carleman, spectral-gap, and measurement examples out of production contracts into property-based regression coverage, and made Fable worked examples compact formalizations of the already completed story run rather than duplicate narratives.
- Migrated standalone and daily factual debriefs from `1 -> 3 -> 4 -> 2` to `1 -> 2 -> 3 -> 4` without changing `opening_story.version=3`, JSON fields, ranking, feedback identity, or learner state. HTML and Markdown retain the collapsed example before the briefing body.
- Passed six Allegory Teach contract tests, 61 daily-pipeline tests, UTF-8 Skill validation, Python compilation for all modified Python files, and `git diff --check`.

## 2026-09-20

### Checkable Fable cases and adaptive story length

- Split `allegory-teach` into bridge-first ordinary teaching and explicit/daily Fable Mode, while preserving the delayed reveal and factual `1 -> 3 -> 4 -> 2` return.
- Made Fable length follow causal completeness: at least two necessary background paragraphs, no total paragraph-count cap, and no permission to combine unrelated mechanisms merely because more space is available.
- Required mathematical/numerical narratives to expose the same concrete inputs, operations, intermediate/result values, counterfactual, and observable difference as the worked example; non-mathematical narratives use explicit states without decorative formulas.
- Kept `opening_story.version=3` and existing fields while replacing the old 2–6/900-character handling with a minimum of two paragraphs, no count maximum, a fail-closed 2000-character per-paragraph limit, full-text concept-leak checking, and complete ordered HTML/Markdown rendering without truncation or de-duplication.
- Added a reproducible Carleman truncation regression (`3/4` full rate, `1/2` zero closure, `1/4` omitted contribution), rejected the former vague mountain-city draft, and passed 61 daily-pipeline tests plus Skill validation, Python compilation, and diff checks.

## 2026-09-15

### Adaptive worked examples for opening allegories

- Extended `allegory-teach` with one complete worked example after the required `1 -> 3 -> 4 -> 2` factual return, while keeping topic selection independent of whether a concept admits equations.
- Added mathematical, numerical, operational, causal, experimental, and comparative example modes. Mathematical notation is conditional; genuine formula branches require defined objects, named rules, explicit transitions, and a falsifying check, while non-mathematical examples require no formula.
- Added `opening_story.version=2`, the structured `worked_example` contract, conditional MathJax rendering, and a native default-collapsed `details` control before `日报正文` in briefing HTML. Markdown keeps the complete example inspectable.
- Extended the daily release guard and manifest so missing/malformed examples, expanded-by-default controls, invalid placement, missing conditional MathJax, and formula-free mathematical examples fail before publication without changing ranking or feedback identities.

## 2026-08-11

### Persistent formal-reader liveness

- Replaced ephemeral continuation-only output with atomic `.papertrace_jobs/<job-id>/orchestration_state.json` and `last_batch_report.json`, preserving the selected PDF hashes, heartbeat, phase, bounded next work, exact resume command, and production guard result across process boundaries.
- Added `--max-papers N` for user-limited deterministic prefixes and kept the frozen selection stable when the source folder later changes.
- Integrated `reader_continuation_guard.py` into the production controller and made ordinary interactive `action_required` checkpoints exit 0; strict CI retains a nonzero incomplete-work option.
- Added `source_map_lock.json` after pre-semantic object discovery plus bounded `next_authoring_packet.json` work packets; post-freeze source-object mutations fail closed.
- Added restart tests at synthetic `60/114` and `74/114` checkpoints, persistent-scope/heartbeat tests, tool-safe versus strict guard tests, and source-map mutation attacks.
- Resumed `Advantage of quantum machine learning from general computational advantages` without losing its completed records and verified 116/116 formal records, two figures, the final HTML, JavaScript runtime behavior, and the adversarial HTML audit.

## 2026-07-31

### Layout-stable annotation saves

- Separated annotation persistence from panel dismissal: `Save mark` now confirms an in-place save and retains the open feedback workspace; only Close or Esc dismisses it. Blank-page and article-content clicks are inert.
- Reserved a stable scrollbar gutter, removed the mismatched grid-padding transition, moved saved-block badges out of the article-top insertion path, and compensated the reading anchor after a marker changes local content height.
- Replaced the wide-screen feedback reflow with one permanently reserved right utility lane. Contents and feedback alternate in that lane without changing source/article columns; smaller screens retain the scroll-safe bottom workspace.
- Updated the reader/lean-HTML contracts, runbook, JavaScript regression coverage, and adversarial HTML audit to reject save handlers that close the panel, blank-click dismissal, feedback-open grid mutation, or missing stable-scrollbar handling.
- Rebuilt and adversarially audited `Active Quantum Kernel Acquisition for Gaussian Process Regression` as the verification reader.

### Robust selectable-PDF extraction

- Kept Poppler raw reading order as the preferred text source, but added a failover to pypdf when Poppler returns replacement characters, known Windows font-map mojibake, empty pages, or a page-count mismatch.
- Normalized Unicode presentation ligatures, recognized Nature-style `Fig. N |` captions and numeric bibliography entries, and stopped bibliography classification at post-reference headings.
- Generated and formally audited all 60 source records in `Experimental realization of a bidirectional`, including four figures, four formula groups, eight reference blocks, source-page navigation, and the stable annotation utility lane.

## 2026-07-17

### Whole-source math evidence contract

- Extended the source-math gate from formula/equation records to every immutable source row with layout-math evidence, including paragraphs, captions, and object descriptions.
- Added the persisted `source-math-inventory-v1` contract: ordered page-reviewed components must be present exactly once in both Original and Chinese; migration invalidates older pass records without that evidence.
- Added source-bound override support for reviewed math inventories and exact signature replacements. The override writer now preserves the independent object inventory; the completion loader defensively recovers only the unmistakable historic accidental formula-inventory shape.
- Updated reader compilation and the adversarial audit to prove source-inventory parity, then rebuilt and audited all 130 records in `Active Quantum Kernel Acquisition for Gaussian Process Regression`.

### Explicit inline-math boundary and runtime proof

- Extended the formula gate from equation records to every Original/Chinese block, rejecting raw TeX commands, ASCII script syntax, and split PDF math fragments outside explicit delimiters.
- Made strict bilingual component identity opt-in through `bilingual_math_contract: exact-v1`; this preserves exact source/translation pairs without forcing legitimate explanatory math to be deleted from other blocks.
- Prevented content overrides from silently restoring noisy extracted Original text, added authored-content/provenance hashes and round-trip verification, and allowed reviewed Original reconstructions through record overrides.
- Routed paper-summary and Concept Ledger role text through the same audited inline-math renderer, added final visible-text raw-math scanning, MathJax runtime status, and regression coverage for S004/S013-style failures.
- Rebuilt and adversarially audited `Active Quantum Kernel Acquisition for Gaussian Process Regression`, including full source-language compiled Algorithm cards.

## 2026-07-16

### Atomic formulas and compiled source algorithms

- Added a fail-closed formula contract: Original/Chinese formula components remain aligned, each display owns one logical formula, and plaintext PDF-extraction duplicates, literal `\n`, packed `\quad`/`\qquad`, and `align`/`gather` packing are rejected.
- Replaced translated Algorithm step lists with `latex_compiled_algorithm`: complete source-language `.tex`, verified XeLaTeX `.svg`, compile manifest, hashes, engine, translated-comment count, and source/compiled numbered-step parity.
- Updated reader-wiki compilation, completion/preflight gates, the shared HTML contract, formal HTML rendering, adversarial audit, regression fixtures, README, and agent/skill contracts.
- Rebuilt the two algorithms and affected formula blocks in the `Active Quantum Kernel Acquisition for Gaussian Process Regression` reader as the end-to-end test case.

### Source-grounded adaptive reader workspace

- Added a completion-authored `paper_summary.json` contract for detailed Chinese overview, method, significance, and evidence/limitation explanations with formal source anchors.
- Reworked the reader into synchronized source/article/Contents regions: a substantially larger viewport-height source pane, a protected-width article, and sticky Contents. Wide layouts are pointer/keyboard resizable, medium layouts compact Contents to a restore rail, and narrow layouts stack without horizontal overflow.
- Added independent, accessible Original/source-page/Contents collapse controls, persistent restore paths, namespaced local view state, and print restoration of Original content.
- Changed annotation feedback from a translation-covering overlay to a layout-reserving desktop dock or scroll-safe bottom workspace.
- Extended formal compilation, shared contract validation, JavaScript regression coverage, and adversarial publication audit for summary provenance, pane ordering and sizing, folding, responsiveness, and annotation non-overlap.

### Auditable daily-news ranking

- Added `skills/ai-quantum-news-briefing/scripts/rank_briefing_candidates.py` with algorithm version `news-ranker-v1`.
- Ranking now runs before Delta compaction. It applies a fail-closed evidence gate, separate 100-point academic/social component scores, deterministic quota bonuses, MMR-style similarity control, and organization/topic concentration caps.
- Normalization, Delta compaction, staged publication, and strict audit preserve item-level `ranking` plus top-level `ranking_policy` and `ranking_manifest`.
- The independent strict auditor enforces hard quota floors and caps even when an input config attempts to weaken them; regression coverage exercises academic/social quota bypass attempts.
- The daily contract is now 7–8 academic papers and 10–14 social-news items (target 12), with explicit new/continuing, formal-source, source-class, organization, and topic quotas.

### Verified 2026-07-16 local briefing

- Candidate pool: 10 academic and 15 social items; all 25 passed the metadata evidence gate before quota selection.
- Published selection: 20 items — 8 academic and 12 social.
- Academic mix: 5 `new`, 3 `continuing`, and 2 non-arXiv formal papers.
- Social mix: 9 `new`/`material_update`, 3 `continuing`, 4 reputable-media items, and 8 primary-official/government items.
- Interactive feedback baseline: 60 concepts, all initialized as `unrated`.
- Transaction status: `complete`; strict post-publication verification returned zero failures and zero warnings; 20 story-index records were committed idempotently.
- Relevant local outputs: `news/2026-07-16/briefing_reader_2026-07-16.html`, `daily_briefing_2026-07-16.md`, `news_feedback_config_delta_2026-07-16.json`, and `daily_pipeline_manifest_2026-07-16.json`. The `news/` tree is intentionally Git-ignored.
- Automated coverage after the ranking and audit changes: `31 passed` for `skills/ai-quantum-news-briefing/tests`.

### Documentation reconciliation

- Added the ranking stage and 8+12 verified release to README, project context, architecture, config, runbook, decisions, and bilingual demo contracts.
- Removed confirmed dead corpus/example paths and replaced the stale reader example with an existing local reader.
- Reduced `.agents/AGENTS.md` by moving duplicated trigger state to the root `AGENTS.md` and command/test detail to `RUNBOOK.md`.
