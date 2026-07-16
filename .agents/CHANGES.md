# Changes

- Project root: `D:\AI\PaperTrace`
- Last reviewed: 2026-07-16

This file records dated implementation and local-release milestones. Durable boundaries belong in `AGENTS.md`, commands in `RUNBOOK.md`, data contracts in `CONFIG_SPEC.md`, and architecture/ownership in `ARCHITECTURE.md`.

## 2026-07-16

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
