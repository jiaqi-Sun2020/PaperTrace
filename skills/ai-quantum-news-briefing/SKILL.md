---
name: ai-quantum-news-briefing
description: Create concise, source-grounded AI and quantum technology briefings, turn briefings into interactive HTML pages with concept/freeform feedback export, and optionally update the user's learner profile from explicit news-reading feedback. Use for requests such as "今日资讯", "今日快报", "近三天资讯", "近4天快报", "AI+量子快报", company AI reports, research blogs, safety frameworks, model releases, policy updates, industry news, arXiv/Nature papers, quantum physics or quantum computing progress, requests to generate a briefing HTML reader, or when the user says to record daily briefing concepts as known/unknown/learning in `.agents/reader-learner/knowledge_profile.json`.
---

# AI + Quantum News Briefing

Use this skill to produce the user's recurring Chinese news briefings on AI, frontier models, agentic AI, industry/regulation, academic trends, and quantum physics/quantum computing.

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

3. For recurring daily briefings, make the report delta-first.
   - Before drafting, read only the compact recent story context, not whole previous Markdown reports:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index C:\Users\SSS\Desktop\PAPER\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
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

5. Distinguish fact from interpretation.
   - Use "事实:" for source-supported events when useful.
   - Use "判断:" or "对你的启发:" for analysis.
   - Do not present rumors, model leaderboard claims, or company self-statements as verified unless independent sources support them.

6. Cite sources.
   - Cite every factual news item, report, paper, or company claim.
   - Do not include raw URLs unless explicitly asked.
   - Keep quotations short; paraphrase by default.

## HTML Feedback Workflow

Use this when the user wants to read a briefing like a lightweight reader page and collect feedback before updating `.agents`. For shared HTML shell behavior or second-pass report feedback, use `skills/utils/lean-html-skill`; keep this skill focused on news sourcing, briefing structure, and news-feedback normalization.

Read `references/news-html-feedback.md` before changing the HTML config or feedback export format.

Workflow:
1. Create a source-grounded `news_feedback_config.json` with briefing sections, items, concepts, source title/URL, source excerpt, and date range.
2. Generate the interactive HTML:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html>
```

3. In the HTML, click concept chips or select arbitrary text and click `Annotate selection`.
4. Mark status, exact question, question type, explanation style, and note.
5. Click `Save mark`.
6. Export with `Download JSON` or `Copy for Codex`.
7. Import the exported `news_feedback.json` with `scripts/import_news_feedback.py`.

The HTML page is a collection layer only. It must not write `.agents` directly.

If a generated explanation/report HTML needs another feedback round after import, call `lean-html-skill` to attach `news_feedback2.json` export controls instead of duplicating the feedback panel here.

Downstream `read-feedback-skill` reports use `category`, `status`, `source_title`, `source_url`, and `source_excerpt` to render the layered news knowledge map. Preserve those fields in `news_feedback.json` and normalized reader-feedback handoffs.

## Learner Profile Update Workflow

Use this only when the user explicitly asks to update the personal knowledge profile from a briefing, asks a follow-up question about a briefing concept, or marks a news concept as known/unknown/learning/mastered/unrated.

Read `references/news-feedback-profile.md` before changing the profile bridge format.

Rules:
- Do not infer that the user knows or does not know a concept just because it appeared in the briefing.
- If the user only says "记录今天日报关键词", mark extracted concepts as `unrated`.
- If the user says "X 我懂", use `known`; if "X 我能讲清楚/会用", use `mastered`; if "X 有点懂但还要例子", use `learning`; if "X 不懂/解释一下", use `unknown`.
- Preserve news source title, URL, category, and source excerpt when available.
- Delegate profile mutation to `reader-learner`; this skill should normalize news feedback, not maintain a separate memory file.

Workflow:
1. Create a small `news_feedback.json` file from the user's explicit feedback, requested exposure-only concepts, or the exported HTML feedback.
2. Run:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

3. Report how many concepts were imported and where the normalized `*_reader_feedback.json` handoff file was written.

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
- Include a short "给你的科研观察" section.
