---
name: ai-quantum-news-briefing
description: Create concise, source-grounded AI and quantum technology briefings, turn briefings into interactive HTML pages with automatic unrated full-concept feedback JSON export plus optional concept/freeform feedback, and optionally update the user's learner profile from explicit news-reading feedback. Use for requests such as "今日资讯", "今日快报", "近三天资讯", "近4天快报", "AI+量子快报", company AI reports, research blogs, safety frameworks, model releases, policy updates, industry news, arXiv/Nature papers, quantum physics or quantum computing progress, requests to generate a briefing HTML reader, or when the user says to record daily briefing concepts as unrated/known/unknown/learning in `.agents/reader-learner/knowledge_profile.json`.
---

# AI + Quantum News Briefing

Use this skill to produce the user's recurring Chinese news briefings on AI, frontier models, agentic AI, industry/regulation, academic trends, and quantum physics/quantum computing.

## Pipeline Identity and Terminal Gate

This skill owns **Primary Pipeline 2: AI + Quantum Daily Briefing Release**. It is distinct from Pipeline 1 paper PDF-to-HTML, Pipeline 3 local chat-to-profile import, and Pipeline 4 adaptive teaching decisions/evidence return.

For a daily or multi-day briefing request, candidate pools, venue ledgers, Markdown, and `news_feedback_config.json` are internal artifacts. The pipeline completes only after `daily_pipeline.py run -> verify -> finalize -> verify` succeeds and the published directory contains the interactive briefing HTML, full default-`unrated` `news_feedback.json`, Markdown briefing, normalized delta config, release manifest, and atomically updated story index. The primary reader-facing artifact is the briefing HTML; do not report candidate/config generation as completion.

Optional news-feedback import is a downstream learner-profile handoff. It does not replace or weaken the daily publication gate.

## Core Workflow

1. Determine the time window.
   - "今日": use the user's current date and timezone; include near-24-hour rolling updates when publication times cross time zones.
   - "近三天", "近4天", "本周": state the exact date range.
   - If sources are thin for the exact day, say so and include "past 24-48 hours still relevant" items separately.

2. Search current sources before answering.
   - Use web search for all current news, company reports, model releases, regulations, prices, funding, product changes, and papers.
   - Prefer primary sources for company reports, research papers, safety frameworks, and technical releases.
   - Prefer Reuters/AP/FT/WSJ/Bloomberg/Nature/Science/Phys.org/official blogs for confirmation.
   - Treat Reddit/X/community summaries as "社区热议" only, not as confirmed facts.
   - For broad AI candidate discovery, read `references/integration-aihot.md` and fetch the latest AI HOT selected pool:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <YYYY-MM-DD> --output D:\AI\PaperTrace\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>.json
```

   - Treat AI HOT as a candidate source. Verify important final claims against original URLs, official blogs, publisher pages, paper pages, or reliable media.
   - For academic items, do not start and stop at arXiv. Generate a compact venue sweep when the topic is research-frontier material:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py --term "<topic keywords>" --date-range "<YYYY-MM-DD..YYYY-MM-DD>" --format json --fetch --output D:\AI\PaperTrace\news\<YYYY-MM-DD>\academic_search.json
```

   - Copy the resulting ledger into top-level `academic_search` in the final briefing config. A venue is checked only when the ledger contains auditable official HTTP evidence; generated search URLs or a manually asserted `checked_no_hit` are not evidence.

3. For recurring daily briefings, make the report delta-first.
   - Before drafting, read only the compact recent story context, not whole previous Markdown reports:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index D:\AI\PaperTrace\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
```

   - Treat the daily value as new information per reading cost.
   - Expand only `new` and `material_update` stories.
   - Compress recently seen stories with no new facts into `持续跟踪，一句话`, or skip them when brevity matters.
   - Use stable `story_id` when known; otherwise the helper derives one from source URL/title/concepts.

4. Build the briefing in this order unless the user asks otherwise:
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

`daily_pipeline.py run` defaults to `academic_delivery.required=true` with `minimum_items=5`. Include five distinct paper-level records in a dedicated `Academic research and venue evidence` section. The section must include at least one formal primary academic source from an approved venue or publisher (for example PRL/PRA/PRX/PRX Quantum, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL Anthology, or Quantum Journal). arXiv is required in the search coverage and may supply timely preprint context, but an all-arXiv academic delivery is invalid.

Search PRL, PRA, PRX/PRX Quantum, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL Anthology, Quantum Journal, and arXiv; the `academic_search` evidence ledger must cover each venue with auditable official HTTPS evidence. A company quantum blog, venue landing page, search page, or a venue check without an individual formal paper record does not satisfy the required non-arXiv item.

If neither the requested window nor clearly labeled recent academic context has a defensible formal academic item, use an explicit opt-out with a concrete `no_signal_reason`; do not silently omit the academic section or invent a publication.

Count five distinct, paper-level records with a primary article/DOI/preprint URL and a source-specific evidence fingerprint. At least one record must have a non-arXiv primary URL and a formal `evidence_level` such as `peer-reviewed venue` or `conference proceedings`. A journal landing page, one search result, a company platform update, or five paraphrases of one paper never satisfies the five-paper delivery. If the requested window has only new arXiv papers, widen the academic context window to find a defensible recent formal paper, label it as `near 7-day academic context`, and retain its actual publication date; never present it as same-day publication.

### Mandatory Social News Delivery

Every daily briefing must also contain a separate `Social news` / `社会新闻` section with at least one verified, non-academic source-backed item. This is a second required page section, not a subsection of academic research and not an optional add-on. Suitable coverage includes policy and regulation, public-sector deployment, labor and education, social impact, infrastructure, industry, funding, or market developments. A paper, preprint, venue ledger, company research blog, or an empty “no signal” placeholder cannot satisfy this section.

Build the social-news candidate pool from AI HOT; reliable news media (for example Reuters, AP, FT, WSJ, Bloomberg, and relevant local outlets); official X and Instagram accounts of leading AI companies; and official posts by their named executives. Prioritize original company, government, regulator, or publisher pages for final evidence. X/Instagram may surface candidates and may be the primary source only for an attributable announcement from the verified official organization or executive account; label it as an official social post and never turn reposts, rumors, or engagement metrics into facts.

Before curation, persist a `social_candidate_pool` object in the source config. It must record all four required source classes (`ai_hot`, `reputable_media`, `official_company_social`, `executive_social`), the collection timestamp, and the saved AI HOT candidate artifact when available. This records the breadth of discovery; it does not require a final item from every class. Every promoted social item must retain `source_title`, a direct `source_url`, `published_at`, `evidence_level`, and an `evidence_fingerprint`. The config audit treats a missing class, timestamp, dedicated section, or source-backed final item as a blocking delivery failure.

The final delta config must retain both required sections: the academic research section and the social-news section. Delta compaction may shorten continuing social stories to one line, but must not remove the final social-news section or reduce it below one independently source-grounded item.

### Chinese Analysis Contract

For daily and multi-day briefings, set `analysis_language` to `zh-CN` unless the user explicitly requests another language. Every published item must contain Chinese prose in `facts`, `judgment`, and `relevance`; retain paper titles, source titles, model names, DOI, arXiv IDs, and other proper nouns in their precise original form where translation would lose meaning. Treat missing or English-only analysis fields as a configuration-audit failure, not a presentation preference.

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
1. Create a source-grounded `news_feedback_config.json` with briefing sections, items, concepts, source title/URL, source excerpt, and date range.
2. Generate the interactive HTML. The page embeds every extracted concept as a saved feedback item with default `unrated`, and also writes the same full-concept `news_feedback.json` beside the HTML:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --default-status unrated
```

3. In the HTML, click concept chips or select arbitrary text only for corrections, explicit ratings, or extra questions.
4. Mark status, exact question, question type, explanation style, and note when a specific item needs editing.
5. Click `Save mark` only for changed items or new free-form annotations; do not require users to save every concept.
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

For academic or quantum configs, include top-level `academic_search`. The adversarial audit fails if this ledger is missing, lacks real HTTP evidence, or does not cover PRL, PRA, PRX, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL, Quantum Journal, and arXiv. If the user says "ICLA", treat it as ICLR unless context proves otherwise.

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
- For "今日资讯": 6-10 main items.
- For "近三天/近4天": 8-14 main items.
- For "只要重点": 3-5 items.

Use clear section headings. Avoid padding. If there is no reliable news in a section, say "今天没有可核验的强信号", then move on.

## Reliability Checklist

Before finalizing:
- Verify the exact date range.
- Remove stale items outside the requested window unless labeled as context.
- Remove unsourced claims.
- Separate company self-promotion from independently verified results.
- Ensure quantum items are not old papers unless the user asked for background.
- Ensure academic configs include top-level `academic_search`; if missing or incomplete, run `scripts/academic_venue_sweep.py`, search primary venues, and record the compact ledger before finalizing.
- When academic delivery is required, verify the final delta config contains its dedicated academic section, the configured number of formal venue/arXiv items, and at least one individual non-arXiv formal paper record. A complete venue-search ledger does not excuse an all-arXiv delivery.
- Verify the final delta config also contains a distinct `社会新闻` / `Social news` section with at least one verified non-academic item; do not let academic backfill or delta compaction erase this second required section.
- Default daily `facts`, `judgment`, and `relevance` to Chinese analysis. Preserve source titles, paper titles, model names, acronyms, and other proper nouns when translation would reduce precision.
- Ensure arXiv items include `venue_sweep_note` and remain labeled as preprints. Do not finalize a daily briefing whose academic delivery is all arXiv, even if every preprint is correctly labeled.
- Include a short "给你的科研观察" section.
- Run the adversarial config audit before rendering final HTML:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\audit_briefing_config.py --config <news_feedback_config.json>
```
