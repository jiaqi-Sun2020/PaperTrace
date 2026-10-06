---
name: ai-quantum-news-briefing
description: Create source-grounded AI and quantum briefings with a complete Fable opening, reviewed release artifacts, interactive HTML and unrated feedback export. Use for daily or multi-day AI/quantum news, research, policy and model updates, briefing HTML requests, or explicit news-feedback handoffs to the learner profile.
---

# AI + Quantum News Briefing

Use this skill to produce the user's recurring Chinese news briefings on AI, frontier models, agentic AI, industry/regulation, academic trends, and quantum physics/quantum computing.

## Pipeline Identity and Terminal Gate

This skill owns **Primary Pipeline 2: AI + Quantum Daily Briefing Release**. It is distinct from Pipeline 1 paper PDF-to-HTML, Pipeline 3 local chat-to-profile import, and Pipeline 4 adaptive teaching decisions/evidence return.

For a daily or multi-day briefing request, candidate pools, venue ledgers, Markdown, and `news_feedback_config.json` are internal artifacts. New automated releases follow `run -> verify --structure-only -> review-template -> authored source/story review -> seal-review -> verify --strict -> finalize -> verify --strict`. Read [the release-review protocol](references/release-review-protocol.md) before running or recovering this sequence. The completed directory contains the interactive briefing HTML, full default-`unrated` feedback JSON, Markdown, normalized config, review evidence, manifest, and atomically updated story index. Every new run requires a validated `opening_story` and a consistent worked example; HTML keeps only the example collapsed. The primary reader-facing artifact is the briefing HTML, not a candidate, config or staging directory.

Optional news-feedback import is a downstream learner-profile handoff. It does not replace or weaken the daily publication gate.

New releases use pipeline protocol 4, academic-search version 4 and delivery-expansion version 2, while retaining story-review protocol 3 in the
review sidecar and manifest. Historical pipeline versions 1–3 remain readable. The reviewer must reconstruct decisive state
changes from the story alone, then map those actions to source-backed technical
operations and verify the same worked example. Old v2 reviews remain locally
readable; a new remote upload or correction requires a fresh v3 review.

Generation, strict verification and first OSS uploads share the version policy
in `scripts/publication_contracts.py`: pipeline 2/3 uses coverage contract 2;
pipeline 4 uses coverage contract 3. Unknown versions and mismatched pairs fail
closed. For standalone v4 config audits, pass `--coverage-contract-version 3`.
Explicit orchestrator `preflight` always checks transport, including when the
authoring packet is already ready; cached `resume` remains offline. A
capture-ready candidate may still report `opening_story_status=authoring_pending`.
Neither transport readiness nor candidate readiness approves content or release.

Daily recovery also uses `orchestrate_daily.py queue --date <release-day> --record`
to retain explicitly selected unfinished dates. Collection `resume` ends at a
source-bound authoring packet; advance authoring, article capture, actual review,
finalization and online verification according to the returned phase. Academic
rows and AI HOT pagination have separate query-bound atomic checkpoints. Academic
collection has a 200-second budget and 270-second watchdog. AI HOT starts at 200
seconds; budget exhaustion permits bounded 400/800-second resumes, with matching
parent watchdogs. Revalidation remains mandatory; repeated no-progress or an
exhausted maximum stops with an explicit diagnosis. Valid article
captures are reused; failures are isolated and retryable by item ID. A capture
file must pass validation, not merely exist. JMLR RSS identities are structured
discovery; year-only dates remain unknown and cannot satisfy a healthy daily
source gate. Read the RUNBOOK recovery section for state and permission details.

PLOS provides an independent, fixed AI / machine-learning Research Article
index query. Its healthy result requires exact Shanghai-window query parameters,
bounded complete pagination, locally validated records, and a matching second
read of every page. Preserve the publisher's raw `publication_date` and label it
`publisher_index_publication_date`; it is not proof of the actual online instant.
A complete empty query proves only zero current indexed matches in that scope,
never zero publications by the publisher or the whole AI field. It remains
`discovery_only`; article review, expansion, quotas and publishing gates apply.
Feed diagnostics distinguish a target before the returned range from one after
it; neither can be promoted to a covered empty day. Collection diagnostics retain
the missing family, per-source failures, observed date span and current preflight.

Healthy academic rows require registered query scope, valid transport/digest,
aware collection time, matching coverage window, and consistent dated matches;
success flags alone cannot pass. Remote checks for completion use
`status --online --record`: a durable attempt is reserved before network and the
latest observation binds release date, HTML hash and public deployment identity.
A later negative/unavailable check or an unfinished newer attempt blocks queue
completion. Missing/mismatched publishing receipts remain pending even when
public content verifies. Legacy hash-only proofs require rechecking. Read-only `--online`
does not update the queue. Online failures and checkpoint write failures exit 2.
`finalize --require-remote` succeeds only after final online verification and
durable checkpoint recording; local commits survive delivery/reconciliation failure.

An opt-in OSS website mirror runs only after the reviewed local release passes strict verification. Direct `publish` applies the same content gate. Read the OSS section in `.agents/RUNBOOK.md` when operating it. The local `news_publish.local.json` contains only site routing; `ossutil` owns credentials. Website mirroring starts disabled, requires manual `enable`, and latches disabled when the site or link cannot be verified after bounded retries. A failed mirror does not erase the completed local briefing; report the separate remote status.

## Core Workflow

Current source optimization uses academic-search v4 with `source_coverage_version=2`.
Each family requires a replay-verified complete registered query: APS PRX Quantum
open-access publication-calendar API / Crossref Quantum, and PLOS AI / Crossref
Nature Machine Intelligence. Scope and provider are explicit; an indexed empty
query is not a publisher census. RSS remains discovery and its date span cannot
prove an empty target day. Historical coverage version 1 keeps its local meaning.

`resume` now prepares bounded expansion when raw pools are below the unchanged
delivery floors. `expansion_pending` -> `expansion_ready` covers 14 academic
calendar days and 72 hours of AI HOT candidates. The separate packet remains
`not_reviewed`, with `shortfall_status=not_approved`; all four social search
classes, source verification and actual content/story reviews still apply.
When the daily pool is large enough, `late_arrival_pending` triggers a three-day
index recheck and a source-bound authoring annex. Original publication dates are
preserved; frozen releases are not rewritten. Explicit `expand` and `recheck`
use the same sole orchestrator and must preserve authored/staged content.

Read quotas from `scripts/daily_delivery_policy.py` / packet `delivery_policy`.
Current defaults preserve formal publication bounds: academic 6–8, social 6–12,
with at least 4 social new/material-update items under standard delivery.
Explicit conflicting non-default ranking/delivery fields raise `policy_conflict`;
a copied default ranking template remains a fallback. Do not lower quotas to recover a run. Queue
`execution_order` puts the requested current date first while retaining backlog.
Run records bind code/runtime/policy and retain independent attempt histories.

Before authoring, test this task's scoped write capability with
`daily_authoring.py probe --date <release-day>`. Save authored candidate JSON and
existing staged review templates through `daily_authoring.py save/patch`, using
the exact current SHA-256 (or `absent` for initial creation) and bounded UTF-8
JSON encoded as base64. The CLI only writes the day's candidate or its existing
protocol-4 staging news/story review; it cannot write releases, index, credentials
or profile. It does not grant sandbox permission: if denied, request host
approval for the complete command only, and obey a denial. Do not reinterpret a
failed editor call as proof that every authorized command is read-only.
Read the RUNBOOK authoring command contract before use. Drafts stay
`authoring_status=in_progress` / `candidate_authoring_pending` until actually
finished. Marking authoring complete or saving a review never approves content;
source capture, actual reviews, sealing and strict publishing gates still apply.

1. Determine the time window.
   - "今日" in an interactive request follows the user's current date and timezone. The scheduled 08:00 Asia/Shanghai release instead covers the prior complete local calendar day; do not claim that its release-date label means the current day is fully covered.
   - "近三天", "近4天", "本周": state the exact date range.
   - If the exact day is thin, finish its required source checks first. Then try the optional venue expansion; only afterward widen candidate discovery to 14 academic calendar days and 72 social-news hours. Label older items `近期回看` with their original dates.

2. Search current sources before answering.
   - Use web search for all current news, company reports, model releases, regulations, prices, funding, product changes, and papers.
   - Prefer primary sources for company reports, research papers, safety frameworks, and technical releases.
   - Prefer Reuters/AP/FT/WSJ/Bloomberg/Nature/Science/Phys.org/official blogs for confirmation.
   - Treat Reddit/X/community summaries as "社区热议" only, not as confirmed facts.
   - For daily collection, use the sole routine orchestrator from `D:\AI\PaperTrace`:

```powershell
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py status --date <RELEASE-YYYY-MM-DD>
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py preflight --date <RELEASE-YYYY-MM-DD>
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py collect --date <RELEASE-YYYY-MM-DD> --record
python -B .\skills\ai-quantum-news-briefing\scripts\orchestrate_daily.py resume --date <RELEASE-YYYY-MM-DD> --record
```

   - `authoring_packet_pending` means valid cached discovery needs a packet rebuild,
     not another collection. `resume` rebuilds it offline, preserving original
     candidates, source hashes and `not_reviewed`. It recollects only a missing or
     invalid source after network preflight. `collection_ready` requires the
     source-bound packet too; an empty valid pool needs expansion. Unknown higher
     packet versions and invalid authored candidates are preserved and reported.
     Existing staging/releases take precedence. Exit 0 is an actionable checkpoint,
     not semantic approval or publication. See the RUNBOOK for failure codes,
     atomic recovery, backups and packet schema 2.

   - Treat AI HOT as a candidate source. Verify important final claims against original URLs, official blogs, publisher pages, paper pages, or reliable media.
   - For academic items, do not start and stop at arXiv. Generate a compact venue sweep when the topic is research-frontier material:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py --term "<topic keywords>" --date-range "<YYYY-MM-DD..YYYY-MM-DD>" --format json --fetch --output D:\AI\PaperTrace\news\<YYYY-MM-DD>\academic_search.json
```

   - Use an explicit one-day `--date-range` per dated sweep. Pipeline v4 reads `references/academic_sources.v1.json` and records retrieval, parsing, date-window and coverage claims separately. Publication needs one healthy publisher in both `quantum_publisher` and `ai_peer_review`; a single optional/probationary failure or malformed record is isolated. Science, arXiv and other enhancement sources improve discovery but do not individually gate publication. Science RSS and Crossref remain discovery only; `skipped_unavailable` never means zero publications.

3. For recurring daily briefings, make the report delta-first.
   - Before drafting, read only the compact recent story context, not whole previous Markdown reports:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index D:\AI\PaperTrace\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
```

   - Treat the daily value as new information per reading cost.
   - Expand only `new` and `material_update` stories.
   - Compress stories already seen within the configured lookback window and carrying no new facts into `持续跟踪，一句话`, or skip them when brevity matters.
   - Use stable `story_id` when known; otherwise the helper derives one from source URL/title/concepts.

4. Build the briefing in this order unless the user asks otherwise:
   - 开篇故事：生活画面 → 一句话核心 → 真实概念对应 → 边界纠正 → 默认折叠的完整例子
   - 今日新增
   - 重大更新
   - 持续跟踪，一句话
   - Top signals
   - AI regulation / policy
   - Models and products
   - Company reports and research updates
   - Industry / infrastructure / funding
   - Academic frontier
   - Community discussion, clearly labeled
   - Quantum physics / quantum computing
   - Personalized research observation for QWTA / CTQW / Quantum Walk GNN / AI for Quantum
   - One-sentence summary

### Mandatory Academic Delivery

`daily_pipeline.py run` normally targets 6–8 distinct paper-level records in a dedicated `Academic research and venue evidence` section, including at least two non-arXiv formal papers and at most three `continuing`. Approved discovery includes the declared APS, Nature, OpenReview/PMLR, JMLR, Quantum Journal, arXiv and probationary IOP/IEEE/AAAI adapters. Only a fully evidenced `verified_shortfall` release may relax unattainable count/source-category minima; it still needs at least one claim-reviewed academic paper, and preprints remain labeled as such.

The ledger must show both source-family gates and preserve every source-specific failure. HTTP 200, a landing page or a search result proves neither daily completeness nor an article claim. Selected papers must be traceable to the current sweep and pass article-level source review.

If no defensible academic item survives, stop the daily release; an opt-out cannot manufacture a rank-1 paper for its source-grounded Fable.

Count six to eight distinct paper records with a primary article/DOI/preprint URL and a source-specific evidence fingerprint. At least two records in standard mode must have non-arXiv primary URLs and formal evidence. DOI, unversioned arXiv ID and OpenReview ID are strong identities; title similarity only requests manual review. If the requested window lacks enough formal items, widen only to the configured academic context window, label the context, and retain every paper's actual publication date.

### Mandatory Social News Delivery

Every daily briefing also needs a separate `Social news` / `社会新闻` section. Normal delivery targets 6–12 verified non-academic items, with at least four `new`/`material_update`, at most three `continuing`, and source/organization/topic diversity. `verified_shortfall` may relax only unattainable lower bounds after complete search evidence; it still requires at least one reviewed social item and never admits a candidate-only or duplicate record.

### Evidence-gated low-signal release

Read [the release-review protocol](references/release-review-protocol.md) before using this branch. Keep the covered Shanghai day fixed. First pass both academic source-family gates and all social evidence gates. If normal targets remain unattainable, use the declared optional/probationary sources, collect separate records for the 14-day academic and 72-hour social lookback, and set `delivery_expansion.version=2`, `mode=verified_shortfall`. This is additional discovery, not proof that every publisher published nothing else.

For shortfall, `academic_window_start` is covered day minus 13 days and `social_window_start` is minus two days. Attach the full lookback academic sweep plus its canonical digest, both earlier social daily search records plus their digests, and a concrete `shortfall_reason`. The ranker records all eligible, selected and excluded candidates. Original publication time—not an aggregator's resurfacing date—determines `covered_day` versus `recent_context`; social times must be timezone-aware. Older unseen items may count toward total output but must show `近期回看` and their original dates. If either final category is empty, or a required source or claim review fails, do not publish. `--days` remains an index deduplication lookback, not this candidate retrieval window.

### Deterministic Candidate Ranking

Daily releases use `scripts/rank_briefing_candidates.py` and `news-ranker-v1` before delta compaction. The ranker first rejects missing/unsafe evidence, candidate-only AI HOT items, invalid dates, and duplicate story identities. It then computes separate academic and social component scores and selects with deterministic MMR-style source/topic/organization diversity constraints. `ranking`, `ranking_policy`, and `ranking_manifest` must survive normalization and publication. AI HOT scores are discovery priors only and never bypass primary-source verification.

After quota/diversity selection, display the academic section in descending
`ranking.base_score`. This is the pipeline's auditable impact/importance proxy
across evidence strength, novelty, technical contribution, specificity,
learner relevance, and reproducibility; do not present it as citation impact or
an objective universal measure of scientific importance.

Build the social-news candidate pool from AI HOT; reliable news media (for example Reuters, AP, FT, WSJ, Bloomberg, and relevant local outlets); official X and Instagram accounts of leading AI companies; and official posts by their named executives. Prioritize original company, government, regulator, or publisher pages for final evidence. X/Instagram may surface candidates and may be the primary source only for an attributable announcement from the verified official organization or executive account; label it as an official social post and never turn reposts, rumors, or engagement metrics into facts.

Before curation, persist a `social_candidate_pool` object in the source config. It must record all four required source classes (`ai_hot`, `reputable_media`, `official_company_social`, `executive_social`), the collection timestamp, and the saved AI HOT candidate artifact when available. This records the breadth of discovery; it does not require a final item from every class. Every promoted social item must retain `source_title`, a direct `source_url`, `published_at`, `evidence_level`, and an `evidence_fingerprint`. The config audit treats a missing class, timestamp, dedicated section, or source-backed final item as a blocking delivery failure.

The final delta config must retain both required sections: the academic research section and the social-news section. Delta compaction may shorten continuing social stories to one line, but must not remove the final social-news section or reduce it below one independently source-grounded item.

### Chinese Analysis Contract

For daily and multi-day briefings, set `analysis_language` to `zh-CN` unless the user explicitly requests another language. Every published item must contain Chinese prose in `facts`, `judgment`, and `relevance`; retain paper titles, source titles, model names, DOI, arXiv IDs, and other proper nouns in their precise original form where translation would lose meaning. Treat missing or English-only analysis fields as a configuration-audit failure, not a presentation preference.

### Mandatory Opening Story

After deterministic ranking has identified the publishable concepts, but before
`daily_pipeline.py run`, author exactly one complete Fable opening (version 3). Read
`skills/allegory-teach/SKILL.md`, its story-output contract, narrative-language
firewall and daily briefing interface. Prefer a near-doctoral concept at the intersection of the
learner's read-only knowledge boundary and the final briefing. If no supported
intersection exists, use one source-grounded final briefing concept and retain
its neutral `unrated` status.
Before drafting the scene, make the private task-and-reasoning card required by
`allegory-teach`; keep it in review evidence, never in `opening_story`.

For a daily briefing, default to the rank-1 academic item after the academic
section is ordered by descending impact score. Set
`story_delivery.selection_basis="highest_impact_academic"`, use
`grounding_kind="briefing_items"`, and place that paper's `story_id` first in
`source_story_ids`. Depart from this only with
`selection_basis="explicit_override"` plus a concrete `override_reason` such as
an explicitly user-selected paper; the override must remain auditable.

Use `rank_briefing_candidates.py` output as a read-only authoring preview. Add
the resulting `opening_story` to the original full candidate config, then pass
that full config to `daily_pipeline.py run`; the deterministic rerun should pick
the same referenced `story_id` while preserving rejected candidates and their
exclusion reasons in the ranking ledger.

The candidate config must contain `story_delivery.required=true`,
`story_delivery.worked_example_required=true`, and
`story_delivery.position="before_briefing"`.
New authoring uses `opening_story.version=3` with at least two causally necessary
background paragraphs, a complete mechanism and observable consequence.
No total character, sentence, or paragraph-count cap applies. Split at natural
causal boundaries when a paragraph exceeds 2000 characters; never truncate.
Read `narrative-language-firewall.md`; professional terminology returns only
after the entire story, in factual sections 1 -> 2 -> 3 -> 4.
The full story stays visible; only the formal example is collapsed.
Legacy versions 1–4 retain their runtime contracts; unknown versions are rejected.
If rank 1 fails after narrowing and repair, inspect academic sources in ranking
order and record an explicit override. If none passes, stop publication.

Select the concept for relevance, causal value, source support, and the
learner's missing bridge—not for whether it admits equations. Choose the worked
example independently as mathematical, numerical, operational, causal,
experimental, or comparative. A non-mathematical example needs no formula. If
the mechanism genuinely uses mathematics, define the objects and symbols,
expose every meaningful transition, and add a check that can falsify a bad
derivation; never invent a formula to satisfy the format. Read
`skills/allegory-teach/references/worked-example-contract.md` before authoring
the handoff. Every example kind must still provide one bounded `scenario`, a
non-empty list of named `inputs` with actual values/states/conditions, and an
`observable`. The steps must consume those inputs and reach a concrete result;
repeating the general logic chain does not satisfy the example contract.
Story and example share the same bounded case, direction, conditions and data
identity. Re-review every cross-reference after editing either surface.
Keep `concept_definition` to a bounded definition, put the research-task and
story-action mapping in `logic_chain`, and leave section numbering to the
renderer. The example's question, observable, steps and result must agree.
Hypothetical examples must not impersonate source measurements. Review causal
fidelity and comprehension separately from structural schema validation.

The opening story and worked example are presentation artifacts, not news items
or learning events. They cannot satisfy academic/social quotas, enter candidate
ranking, create concept feedback, or update the learner profile.
`daily_pipeline.py run` fails before staging when either is missing or malformed.

5. Distinguish fact from interpretation.
   - Use "事实:" for source-supported events when useful.
   - Use "判断:" or "对你的启发:" for analysis.
   - Do not present rumors, model leaderboard claims, or company self-statements as verified unless independent sources support them.

6. Cite sources.
   - Cite every factual news item, report, paper, or company claim.
   - Do not include raw URLs unless explicitly asked.
   - Keep quotations short; paraphrase by default.

## HTML Feedback Workflow

## Encoding And Text Integrity Contract

Unicode correctness is a data contract, not a browser styling option. Candidate config, delta config, Markdown, feedback JSON, and HTML must be read as UTF-8 (`utf-8-sig` input compatibility) and written as UTF-8 with `ensure_ascii=False`. A file being technically UTF-8 cannot repair text that was already replaced by literal `?` characters upstream.

Before normalization or rendering:

- Generate multilingual config from a UTF-8 file or a UTF-8-aware Python process. Do not pipe Chinese source text through a default PowerShell/code-page here-string.
- Treat `?` as ordinary data only when it is a real question mark or URL query delimiter. High-density `?` in human-readable fields and `U+FFFD` are blocking corruption signals.
- Never repair corrupted text by deleting or globally replacing `?`; regenerate the fact from the candidate/source record.
- Treat historical `story_index` summaries as untrusted input. A corrupt prior summary may be omitted from a continuing item, but must never be copied into new Markdown/HTML.

If the encoding audit fails, stop before staging/finalizing. Recreate the affected input from a UTF-8 file, rerun the config audit, and only then regenerate Markdown, HTML, and feedback JSON. Do not use a visually plausible HTML page as evidence that the source data survived intact.

The shared normalizer enforces this contract before `daily_pipeline.py run`. Final `verify` additionally checks visible HTML text, UTF-8 metadata, Chinese UI markers, and replacement-character absence. A report with encoding validation failure is not publishable.

Use this when the user wants to read a briefing like a lightweight reader page and collect feedback before updating `.agents`. For shared HTML shell behavior or second-pass report feedback, use `skills/utils/lean-html-skill`; keep this skill focused on news sourcing, briefing structure, and news-feedback normalization.

Read `references/news-html-feedback.md` before changing the HTML config or feedback export format.

Workflow:
1. Create a source-grounded `news_feedback_config.json` with the required opening story, briefing sections, items, concepts, source title/URL, source excerpt, and date range.
2. Generate the interactive HTML. The page embeds every extracted concept as a saved feedback item with default `unrated`, and also writes the same full-concept `news_feedback.json` beside the HTML:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --default-status unrated
```

3. In the HTML, click concept chips or select arbitrary text only for corrections, explicit ratings, or extra questions.
4. Mark status, exact question, question type, explanation style, and note when a specific item needs editing.
5. Status choices save immediately; questions, notes, explanation style and context auto-save after a short debounce. Selecting text opens the shared quick-status toolbar, and merely opening/dismissing it creates no record.
6. Export with `Download JSON` or `Copy for Codex`; the export must include the full default `unrated` concept set plus the user's edits.
7. Import the exported `news_feedback.json` with `scripts/import_news_feedback.py` only when the user asks to update the learner profile.

The HTML page is a collection layer only. It must not write `.agents` directly.

Reader encoding acceptance requires `<meta charset="utf-8">`, a successful UTF-8 round trip, no `U+FFFD` or corruption-pattern question marks in visible text, and Chinese UI markers such as `事实`, `判断`, and `来源`. The concept-chip and feedback identity sets must remain equal.

If a generated explanation/report HTML needs another feedback round after import, call `lean-html-skill` to attach `news_feedback2.json` export controls instead of duplicating the feedback panel here.

Preserve `category`, `status`, `source_title`, `source_url`, and `source_excerpt` in `news_feedback.json` and normalized reader-feedback handoffs for source-grounded profile evidence and future pipeline-owned views.

## Learner Profile Update Workflow

Use this only when the user explicitly asks to update the personal knowledge profile from a briefing, asks a follow-up question about a briefing concept, or marks a news concept as known/unknown/learning/mastered/unrated.

Read `references/news-feedback-profile.md` before changing the profile bridge format.

Rules:
- Do not infer that the user knows or does not know a concept just because it appeared in the briefing.
- For daily/news briefing generation and exposure-only daily keywords, default extracted concepts to `unrated`.
- Keep literature/paper reader concepts as `unrated`; news and paper exposure share the same neutral default.
- If the user says "X 我懂", use `known`; if "X 我能讲清楚/会用", use `mastered`; if "X 有点懂但还要例子", use `learning`; if "X 不懂/解释一下", use `unknown`.
- Preserve news source title, URL, category, and source excerpt when available.
- Delegate profile mutation to `reader-learner`; this skill should normalize news feedback, not maintain a separate memory file.

Workflow:
1. Create `news_feedback.json` from `news_feedback_config.json` with `scripts/config_to_news_feedback.py`; use `unrated` unless the user explicitly marks a different status.
2. Run:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
```

3. Report how many concepts were imported and where the normalized `*_reader_feedback.json` handoff file was written.

For the normal user-facing path, import and synchronize the persistent visible Wiki in one command:

```powershell
python D:\AI\PaperTrace\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>
```

This preserves the news normalizer and strict profile-import backup, then projects all stable profile records into `.agents/wiki/`.

## Company Report Tracking

When the user asks for company reports or "各公司对 AI 的报告", read `references/company-report-sources.md`.

Track at least:
- OpenAI: model/system cards, Preparedness Framework, safety updates, research posts, product/API announcements, policy posts.
- Anthropic: Responsible Scaling Policy, system cards, safety/research posts, model release notes, policy posts.
- Google DeepMind / Google Research: Gemini reports, technical blogs, publications, safety/responsibility posts, AI for Science reports.
- Microsoft: AI infrastructure, Copilot, Azure AI, enterprise AI adoption, responsible AI reports.
- Meta AI: Llama/model reports, FAIR research, agent/product roadmap, open model releases.
- NVIDIA: AI factory, robotics/physical AI, World Foundation Models, GPU/datacenter reports.
- Apple: Apple Intelligence, on-device/private cloud AI, ML research notes.

For company reports, summarize:
- What was released or claimed
- Evidence level: official report, peer-reviewed paper, media report, or community claim
- Technical relevance
- Safety/regulatory implications
- Relevance to the user's quantum walk / continuous dynamics research, if any

## Quantum Section Rules

Always include a quantum section when the user previously asked for AI + quantum briefings or when the request says "资讯/快报" in this ongoing context.

Read `references/academic-source-policy.md` before academic-frontier searches. Do not rely only on arXiv when the topic plausibly appears in APS PRL/PRA/PRX, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL Anthology, Quantum journal, or other primary venue pages.

For academic or quantum configs, include top-level `academic_search`. For new releases the adversarial audit fails when academic-search v4 is missing, evidence digests are stale, or either core source family has no healthy publisher. Optional source failure is reported and isolated; it is not silently upgraded to a family-wide failure.

For each arXiv academic item, set `evidence_level` to `arXiv preprint` and add `venue_sweep_note` explaining which primary venues were checked. Such items may supplement the academic section, but cannot make the entire daily academic delivery arXiv-only. Prefer PRL/PRA/PRX/PRX Quantum, Nature Portfolio, Science/AAAS, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL Anthology, and Quantum Journal URLs whenever available.

Prioritize:
- quantum computing hardware
- quantum error correction / decoding
- Hamiltonian simulation
- quantum walks
- quantum machine learning
- tensor networks
- quantum sensing / metrology
- quantum communication
- quantum optics
- AI for quantum / quantum for AI

For each quantum item, state whether it is:
- hardware progress
- algorithm/theory progress
- quantum simulation
- physics discovery
- industry/commercial development

## Personalization

The user is working on QWTA, CTQW, complex graph neural networks, Hamiltonian propagation, quantum walk GNNs, and AI for Quantum. When relevant, map news to:
- continuous-time evolution
- spectral propagation
- Hamiltonian simulation
- graph diffusion / interference
- complex-valued representation learning
- quantum hardware feasibility
- agent/world-model continuous dynamics

Avoid overclaiming direct relevance. Use "可借鉴", "方向相关", or "概念上接近" when the link is indirect.

## Output Style

Write in Chinese by default.

Keep the briefing compact but complete:
- Place the opening story, compact factual debrief, and default-collapsed worked
  example before `日报正文`.
- For "今日资讯": target 6–8 academic papers plus 6–12 social-news items; an evidenced low-signal release may be shorter and must disclose its actual counts.
- For "近三天/近4天": 8-14 main items.
- For "只要重点": 3-5 items.

Use clear section headings. Avoid padding. If there is no reliable news in a section, say "截至 <YYYY-MM-DD>，本节没有可核验的强信号", then move on.

## Reliability Checklist

Before finalizing:
- Verify the exact date range.
- Verify one opening story appears before the briefing in both Markdown and HTML, conceals its concept until the debrief, and is followed by one complete worked example. In HTML the example must use a native `details` control that is closed by default; neither story nor example creates learner feedback by exposure.
- Verify academic items appear in descending `ranking.base_score`, and verify the default story's first `source_story_id` is the rank-1 academic paper unless an explicit override reason is present.
- Reject a worked example that lacks a bounded concrete scenario, named actual inputs or states, or a specific observable, even when its general logic explanation is correct.
- Remove stale items outside the requested window unless labeled as context.
- Remove unsourced claims.
- Separate company self-promotion from independently verified results.
- Ensure quantum items are not old papers unless the user asked for background.
- Ensure academic configs include top-level academic-search v4; if missing or incomplete, run the orchestrator collector and record the compact source-family ledger before finalizing. Optional sources never cure a missing core family.
- Verify both final sections, ranking ledger, item-level source reviews and the normal quotas. If a category is below its normal minimum, require the bound `verified_shortfall` expansion evidence and visible disclosure; a complete search ledger alone is not an item-level content review.
- Default daily `facts`, `judgment`, and `relevance` to Chinese analysis. Preserve source titles, paper titles, model names, acronyms, and other proper nouns when translation would reduce precision.
- Ensure arXiv items include `venue_sweep_note` and remain labeled as preprints. Do not finalize a daily briefing whose academic delivery is all arXiv, even if every preprint is correctly labeled.
- Include a short "给你的科研观察" section.
- Run the adversarial config audit before rendering final HTML:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\audit_briefing_config.py --config <news_feedback_config.json>
```
