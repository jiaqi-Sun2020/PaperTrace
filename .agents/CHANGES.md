# Changes

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-07-17

This file records dated implementation and local-release milestones. Durable boundaries belong in `AGENTS.md`, commands in `RUNBOOK.md`, data contracts in `CONFIG_SPEC.md`, and architecture/ownership in `ARCHITECTURE.md`.

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
