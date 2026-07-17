# PaperTrace

<p align="center">
  <strong>A local, auditable research workspace that connects papers, current AI/quantum signals, and real learning evidence.</strong>
</p>

<p align="center">
  <strong>English</strong> ·
  <a href="README.zh-CN.md">中文</a> ·
  <a href="#pipelines">Pipelines</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#paper-reader">Paper Reader</a> ·
  <a href="#daily-briefing">AI × Quantum Briefing</a> ·
  <a href="#validation">Validation</a> ·
  <a href="#safety">Safety</a>
</p>

<p align="center">
  <img alt="Local first" src="https://img.shields.io/badge/Local--first-Research%20workspace-1f6feb?style=flat-square">
  <img alt="Source grounded" src="https://img.shields.io/badge/Source--grounded-Traceable-238636?style=flat-square">
  <img alt="Interactive HTML" src="https://img.shields.io/badge/Output-Interactive%20HTML-8250df?style=flat-square">
  <img alt="Feedback safe" src="https://img.shields.io/badge/Feedback-Profile--safe-dc6d1f?style=flat-square">
</p>

PaperTrace is a local workspace for paper reading, AI + quantum briefings, and an evolving personal knowledge profile. It does not stop at generated summaries: source evidence, interactive reading, explicit feedback, long-term profile updates, and verifiable teaching form one closed loop.

> **Core principle:** reading is not mastery; exposure is not knowledge. No source evidence, strict validation, and real learning performance means no long-term profile update.

| What you want to do | Start here | Final deliverable |
|---|---|---|
| Turn a paper into an annotatable Chinese interactive reader | [Paper Reader](#paper-reader) | An adversarially audited <code>reader_interactive.html</code> |
| Track meaningful current AI and quantum developments | [Briefing pipeline](#daily-briefing) | Briefing HTML, feedback JSON, manifest, and index |
| Turn local chat exports into reviewable profile candidates | [Knowledge Profile](#knowledge-profile) | A human-reviewed, backed-up profile patch |
| Choose a focused next lesson or review from existing evidence | [Adaptive Teach](#adaptive-teach) | A one-topic lesson and controlled feedback handoff |

<a id="pipelines"></a>

## The four primary pipelines

| Pipeline | What it solves | Completion boundary |
|---|---|---|
| **Paper Reader HTML** | Produces a bilingual, formula-readable, feedback-enabled reader from a PDF or source paper. | <code>reader_interactive.html</code> exists and passes the publishing adversarial HTML audit. Bundles and ledgers are intermediate state. |
| **AI + Quantum Daily Briefing Release** | Turns current signals into a sourced and feedback-enabled AI + quantum briefing. | HTML, feedback, manifest, and index are published only after <code>run → verify → finalize → verify</code>. |
| **Local Chat-to-Profile Import** | Extracts reviewable learning and research candidates from local chat exports. | A human reviews the patch and runs <code>apply --backup</code>. Candidates and unapplied patches are not final. |
| **Adaptive Teaching Decision & Evidence Loop** | Selects the next topic from confirmed weaknesses, evidence gaps, and due reviews. | A lesson request ends with a validated session; profile return requires actual performance imported as validated teaching feedback. |

Reader/news feedback import and Visible Wiki projection are shared downstream workflows. Adaptive teaching is Pipeline 4 and is always explicit-invocation: opening or reading a lesson never proves mastery.

<a id="quick-start"></a>

## Quick start: ask Codex directly

Choose one of the four paths below and send its request to Codex.

### 1. Turn PDFs into formal interactive readers

To turn every PDF in a folder into a formal interactive Chinese reader, you do not need to run scripts first. Place the PDFs in a local folder and send Codex this request:

> Read the README and <code>.agents</code> in the current project. Following the PAPER pipeline, generate the corresponding interactive HTML for the PDFs under <code>&lt;PDF-folder&gt;</code>, one paper at a time.

For example:

> Read the README and <code>.agents</code> in the current project. Following the PAPER pipeline, generate the corresponding interactive HTML for the PDFs under <code>D:\Papers\2026\7</code>, one paper at a time.

Codex processes the PDFs in order, continues automatically after each pass, and delivers only an audited <code>&lt;paper-name&gt;_reader\reader_interactive.html</code>. If source evidence cannot satisfy a hard gate, it reports the concrete blocker instead of presenting a draft as final.

### 2. Release a sourced AI + Quantum briefing

> Read the README and <code>.agents</code> in the current project. Using current, source-verifiable information for <code>&lt;date or date-range&gt;</code>, produce the AI + Quantum Daily Briefing Release. Build the evidence-backed candidate config, then complete <code>run → verify → finalize → verify</code>. Deliver the interactive briefing HTML, feedback JSON, manifest, and index; do not treat a candidate list or staging output as final.

Codex verifies sources and dates, applies the ranking and Delta rules, then publishes only after the strict release sequence succeeds. Concepts in the exported feedback start as <code>unrated</code>.

### 3. Prepare a reviewable profile patch from local chat exports

> Read the README and <code>.agents</code> in the current project. Import the local chat export at <code>&lt;chat-export-or-folder&gt;</code> through the Chat-to-Profile pipeline: collect, extract, and propose a profile patch. Show me the resulting <code>profile_patch.json</code> for review and do not apply it yet.

After you review the patch, explicitly ask Codex to run the backed-up apply step. A candidate or a proposed patch must never silently change the profile.

### 4. Generate one evidence-based lesson or review

> Read the README and <code>.agents</code> in the current project. Use the Adaptive Teaching pipeline to analyze my current knowledge profile, select one evidence-backed next topic, and generate a short lesson with a transparent review proposal. Do not update my knowledge profile unless I later provide actual learning performance as teaching feedback.

The lesson is a controlled teaching artifact, not evidence of mastery. Only validated feedback from actual performance may return to the profile.

Use the script interface below only when you need recovery, diagnostics, or CI integration.

## Design principles

- **Local-first:** papers, feedback, and profile data remain in the local workspace. Publish only reproducible public code and documentation.
- **Evidence-first:** every important claim must trace to a paper, source page, or explicit feedback.
- **Human-in-the-loop:** a candidate, exposure, or automatic extraction is not a knowledge state.
- **Deliverable-first:** each pipeline has a hard terminal state; drafts and intermediate artifacts never impersonate delivery.

## Current capabilities

- <code>ai-quantum-news-briefing</code> gathers daily candidate signals from AI HOT API or <code>feed.xml</code>; AI HOT is discovery only, never final evidence.
- Briefing research sources cover APS journals, Nature, Science, OpenReview/ICLR, CVF/CVPR, PMLR/ICML, NeurIPS, ACL Anthology, Quantum Journal, and arXiv. arXiv-only records are labeled as preprints.
- Reader and briefing HTML export full feedback JSON. Concepts default to <code>unrated</code> until the user explicitly provides a learning judgment.
- <code>news-ranker-v1</code> first applies an evidence gate, then uses separate academic/social scoring and diversity constraints. The published config retains item scores, quotas, selection trace, and exclusions.
- <code>lean-html-skill</code> controls only visual presentation. It keeps the light theme as default and can add a Cosmic visual layer without changing behavior or data structure.
- <code>reader-learner</code> validates, normalizes, and atomically updates the profile while blocking encoding corruption, HTML remnants, and exposure-only overclaims.

## Directory layout

    D:\AI\PaperTrace
    |-- 2026/                         # local paper corpus and reader workspaces
    |-- news/                         # generated briefings and feedback artifacts
    |-- readed/                       # papers already processed
    |-- video/                        # local generated media
    |-- skills/
    |   |-- nature-reader/
    |   |-- reader-skill/
    |   |-- reader-learner/
    |   |-- adaptive-teach/
    |   |-- ai-quantum-news-briefing/
    |   +-- utils/
    |       |-- chat-knowledge-profile/
    |       |-- demo-skill/
    |       |-- lean-html-skill/
    |       +-- neat-freak/
    |-- .agents/                      # project context and local learner state
    +-- README.md                     # English default
    +-- README.zh-CN.md               # Chinese edition

<a id="adaptive-teach"></a>

## Adaptive Teach

<code>skills/adaptive-teach</code> is the explicit-invocation teaching decision layer. It analyzes the schema-v2 profile, distinguishes a confirmed weakness from an evidence gap or due review, selects one small next target, and creates short lessons and a transparent review proposal. It does not directly mutate the profile.

Run from <code>D:\AI\PaperTrace</code>:

    python .\skills\adaptive-teach\scripts\adaptive_teach.py analyze
    python .\skills\adaptive-teach\scripts\adaptive_teach.py next
    python .\skills\adaptive-teach\scripts\adaptive_teach.py lesson --output-dir .\.tmp\adaptive-lesson
    python .\skills\adaptive-teach\scripts\adaptive_teach.py validate-feedback --feedback <teaching_feedback.json>
    python .\skills\adaptive-teach\scripts\adaptive_teach.py import-feedback --feedback <teaching_feedback.json>

Generating or viewing a lesson never changes the profile or review queue. Only actual learner performance can become a validated handoff, imported through the guarded <code>reader-learner</code> pipeline.

## Persistent Visible Wiki

<code>.agents/wiki/</code> is an Obsidian layer for stable concepts, entities, themes, questions, syntheses, claims, source summaries, and knowledge-boundary maps. It is separate from raw PDFs, reader bundles, feedback events, and the schema-v2 profile.

Run from <code>D:\AI\PaperTrace</code>:

    python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
    python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
    python .\skills\reader-learner\scripts\lint_visible_wiki.py --profile .\.agents\reader-learner\knowledge_profile.json --wiki .\.agents\wiki --strict --require-profile-coverage

For one-step imports, use <code>reader-feedback</code> or <code>news-feedback</code> with the exported feedback JSON. Both preserve validation, backup, atomic profile updates, and wiki projection.

## Skill boundaries

| Skill | Owns | Does not own |
|---|---|---|
| <code>nature-reader</code> | Source evidence, working bilingual Markdown, source-grounded assets, formula reconstruction, and compiled Algorithm assets. | Learner-profile mutation or browser feedback UI. |
| <code>reader-skill</code> | Formal reader normalization, source anchors, HTML generation, concept marks, and structural/audit gates. | Direct profile mutation. |
| <code>reader-learner</code> | Feedback import, schema-v2 profile validation, backup/atomic mutation, and Visible Wiki projection. | PDF reader generation or teaching decisions. |
| <code>adaptive-teach</code> | Profile-backed teaching decisions, sessions, lessons, and teaching-feedback handoff. | Profile schema, direct profile writes, PDFs/news collection, or shared HTML shell. |
| <code>ai-quantum-news-briefing</code> | Sourced AI/quantum briefings, candidate ranking, briefing feedback artifacts, and news-feedback normalization. | Treating mere exposure as knowledge. |
| <code>lean-html-skill</code> | Shared HTML shell, feedback UI, export controls, and visual design layer. | Domain interpretation or profile mutation. |
| <code>chat-knowledge-profile</code> | Staged local conversation extraction and reviewable profile handoffs. | Share-URL scraping or direct profile overwrite. |
| <code>neat-freak</code> | Reconciles documentation, rules, and durable release facts. | Adding business skills or turning agent rules into a changelog. |

<a id="paper-reader"></a>

## Paper Reader pipeline

The target is an audited <code>reader_interactive.html</code>, not an extraction preview, raw bundle, or summary. The natural-language Quick Start is the preferred end-to-end entry point; the commands below are the advanced, resumable interface.

### 1. PDF to internal evidence

The PDF bootstrap creates immutable source evidence and a UTF-8 working <code>paper.md</code> with stable anchors and completion markers. For a legacy raw bundle that has <code>source_map.json</code> but no <code>paper.md</code>:

    python .\skills\nature-reader\scripts\materialize_reader_markdown.py "<reader-dir>"
    python .\skills\nature-reader\scripts\audit_reader_text.py "<reader-dir>\paper.md"

The materializer does not overwrite an existing <code>paper.md</code> by default. The active primary model must replace every marker with faithful Chinese, block-specific notes, and source-grounded LaTeX before formal completion.

### Formal Reader v3: resumable directory batches

Formal state is stored as atomic records under <code>reader_wiki/completion_blocks/</code>; derived <code>canonical_reader.md</code> is the only input allowed to formal HTML compilation. Start or resume the controller from <code>D:\AI\PaperTrace</code>:

    python .\skills\reader-skill\scripts\build_formal_reader_batch.py --pdf-dir "<PDF-folder>" --reader-root "D:\AI\PaperTrace\2026\7" --agent-continuation

The command considers only the immediate PDFs in the requested folder, records their stable order and hashes, completes one paper at a time, and leaves later papers untouched until earlier ones are formal. Its JSON contains an <code>agent_continuation_contract</code>. A pending/invalid record is repair work, not a successful result.

A completed reader must include:

- faithful Original and Chinese fields for every substantive source row;
- explicit LaTeX boundaries in both fields; raw TeX, ASCII scripts, and broken PDF math are invalid;
- one logical formula per display, with duplicate plaintext extraction removed;
- a page-reviewed <code>source-math-inventory-v1</code> for every source row with layout-math evidence, including paragraphs and captions;
- inspectable figure/table cards and complete source-language Algorithm cards compiled from LaTeX;
- a source-anchored Chinese paper summary, controlled concept aliases, and block-specific notes.

### 2. Completion records to reader wiki

For a targeted repair or locally completed legacy bundle:

    cd D:\AI\PaperTrace
    python .\skills\nature-reader\scripts\complete_reader_bundle.py "<reader-dir>"
    python .\skills\reader-skill\scripts\reader_wiki_compile.py "<reader-dir>" --profile ".\.agents\reader-learner\knowledge_profile.json"

The strict completion gate validates and writes the ledger; it does not translate, crop figures, repair Markdown, or bypass source evidence.

### 3. Reader wiki to interactive HTML

    cd D:\AI\PaperTrace
    python .\skills\reader-skill\scripts\markdown_reader_to_html.py "<reader-dir>"

The final reader includes the original paper-page pane, translated article, resizable or collapsible Contents, detailed Chinese summary, concept ledger, MathJax, and an annotation workspace that does not cover translation.

### 4. Adversarial audit

    cd D:\AI\PaperTrace
    python .\skills\reader-skill\tests\adversarial_html_audit.py "<reader-dir>"

The audit checks source coverage, algorithms, source-page links, formula rendering, concept metadata, pane behavior, feedback export, and dark-theme readability. Do not report a reader as formal until it passes.

### 5. Reader feedback to the knowledge profile

While reading, select concept marks or add annotations, choose a status, and click **Save mark**. Export the result through **Download feedback JSON** or **Copy feedback for Codex**. The browser page does not write profile data itself.

    cd D:\AI\PaperTrace
    python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback "<reader_feedback.json>"

The importer validates feedback, backs up and atomically updates the profile, then synchronizes the Visible Wiki.

### Minimal reader regression chain

    cd D:\AI\PaperTrace
    python .\skills\nature-reader\scripts\complete_reader_bundle.py "<reader-dir>"
    python .\skills\reader-skill\scripts\reader_wiki_compile.py "<reader-dir>" --profile ".\.agents\reader-learner\knowledge_profile.json"
    python .\skills\reader-skill\scripts\markdown_reader_to_html.py "<reader-dir>"
    python .\skills\reader-skill\tests\adversarial_html_audit.py "<reader-dir>"

<a id="daily-briefing"></a>

## AI + Quantum News Briefing pipeline

The briefing is not complete at candidate collection, Markdown, or config generation. The terminal deliverable is an interactive HTML briefing with default-<code>unrated</code> feedback JSON, manifest, and updated story index.

Expected daily artifacts:

    news\YYYY-MM-DD\daily_briefing_YYYY-MM-DD.md
    news\YYYY-MM-DD\briefing_reader_YYYY-MM-DD.html
    news\YYYY-MM-DD\news_feedback_YYYY-MM-DD.json
    news\YYYY-MM-DD\news_feedback_config_delta_YYYY-MM-DD.json
    news\YYYY-MM-DD\daily_pipeline_manifest_YYYY-MM-DD.json
    news\YYYY-MM-DD\daily_pipeline_index_updates_YYYY-MM-DD.json
    news\_index\story_index.jsonl

The release entry point is <code>daily_pipeline.py</code>. <code>run</code> writes staging only; only a successful <code>finalize</code> publishes artifacts and atomically updates the index:

    cd D:\AI\PaperTrace
    python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run --config <candidate_news_feedback_config.json> --output-dir <news\YYYY-MM-DD> --index .\news\_index\story_index.jsonl
    python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
    python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py finalize --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
    python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD> --strict

Optional discovery and evidence tools:

    python .\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <YYYY-MM-DD> --output .\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>.json
    python .\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py --term "quantum walk graph neural network" --date-range <YYYY-MM-DD..YYYY-MM-DD> --format markdown --output <academic_venue_sweep.md>
    python .\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --feedback-output <news_feedback.json> --default-status unrated
    python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>

Key rules:

- AI HOT is a candidate source, never final evidence.
- <code>news-ranker-v1</code> runs before Delta compaction; AI HOT scores cannot replace it.
- Publish 7–8 academic records and 10–14 social-news records (target 12), preserving source, topic, and organization diversity.
- arXiv-only academic entries must say <code>preprint</code> and include a venue-sweep note.
- Exposure-only news concepts remain <code>unrated</code>. HTML only gathers and exports feedback; it never writes <code>.agents</code> directly.

## Lean HTML and design layer

<code>lean-html-skill</code> is the shared presentation layer. It can attach feedback controls or apply the optional Cosmic design system without changing functional behavior or data contracts.

    python .\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json> --output <report_interactive.html>
    python .\skills\utils\lean-html-skill\scripts\lean_html.py apply-design --html <report.html> --design-system cosmic --background-mode light
    python .\skills\utils\lean-html-skill\scripts\lean_html.py audit-design --html <report.html>

## Bilingual project demo

<code>demo-skill</code> renders the verified four-pipeline project presentation in Chinese and English. It validates repository contracts before generation and refuses accidental overwrite.

    cd D:\AI\PaperTrace
    python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .

It creates <code>demo.html</code> and <code>demo-en.html</code>. Use <code>--force</code> only after explicitly approving replacement. Publish only intentional demo assets; exclude design scratch files, screenshots, browser profiles, QA data, and unrelated worktree changes.

<a id="knowledge-profile"></a>

## Knowledge profile and local chat import

<code>.agents/reader-learner/knowledge_profile.json</code> is long-term learning data. Never hand-edit it to bypass validation.

Reader-feedback import:

    cd D:\AI\PaperTrace
    python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>

### Local Chat-to-Profile Import pipeline

Use local ChatGPT/GPT/Claude/Deepseek exports only. The workflow is deliberately staged:

    cd D:\AI\PaperTrace
    python .\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions
    python .\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py extract --events D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\events.jsonl --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
    python .\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py propose --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --candidates D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json

Review <code>profile_patch.json</code> before the only mutating step:

    python .\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py apply --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --patch D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup

The workflow also creates <code>conversation_summaries.json</code> for at-a-glance topics, explicit preferences, open questions, and action requests. Share URLs must first be copied or exported locally for reproducibility.

<a id="validation"></a>

## Validation

Useful static checks:

    cd D:\AI\PaperTrace
    python -m py_compile .\skills\reader-skill\scripts\markdown_reader_to_html.py
    python -m py_compile .\skills\nature-reader\scripts\complete_reader_bundle.py
    python -m py_compile .\skills\reader-learner\scripts\profile_v2.py
    python -m py_compile .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py
    python -m py_compile .\skills\utils\lean-html-skill\scripts\lean_html.py
    python -m py_compile .\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py
    python .\skills\reader-skill\tests\test_reader_e2e.py

<a id="safety"></a>

## Safety and GitHub privacy boundary

Briefing configs and published Markdown/JSON/HTML must be UTF-8. The normalizer rejects replacement characters and suspicious high-density question marks. Rebuild corrupted text from its source record instead of deleting damaged characters.

GitHub publication may contain reproducible code, public documentation, tests, and intentionally maintained examples only. Do **not** upload learner profiles, teaching sessions, visible-wiki projections, paper corpus, reader bundles, browser/IDE state, cookies/sessions, credentials, machine-specific configuration, or generated audio/video.

Before committing:

1. run <code>git status --short</code> and inspect the staged diff;
2. stage explicit paths only; never use <code>git add -A</code> in a mixed worktree;
3. treat <code>.gitignore</code> as a second defense, not a substitute for review;
4. stop tracking a sensitive file before deciding how its Git history should be handled.

- Never open, print, copy, summarize, upload, or modify suspected key/password/token/credential files except for explicitly authorized profile work.
- Do not hand-edit <code>knowledge_profile.json</code>.
- Do not use a whole source-PDF page as an in-article figure; use tight crops, structured tables, or auditable descriptions.
- Do not present paraphrase, summary, or reading guidance as faithful bilingual translation.
- Do not infer <code>known</code> or <code>mastered</code> simply because a concept appears in a briefing.

## Acknowledgements and inspirations

PaperTrace draws on the following projects and design references for architecture, evidence flow, candidate discovery, documentation governance, visual design, and local knowledge organization:

- [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)
- [AI HOT skill](https://aihot.virxact.com/aihot-skill/) and [AI HOT feed.xml](https://aihot.virxact.com/feed.xml)
- [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills/tree/main)
- [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)
- OpenAI Product Design workflow
- [greg-asher/codex-obsidian](https://github.com/greg-asher/codex-obsidian)
- [ar9av/obsidian-wiki](https://github.com/ar9av/obsidian-wiki)
- [Eden-Eldith/ChatInsights](https://github.com/Eden-Eldith/ChatInsights)
- [ygivenx/gpt-obsidian](https://github.com/ygivenx/gpt-obsidian)

These sources are inspiration only. PaperTrace independently implements its local profile, feedback import, paper-reader, briefing research, and knowledge-boundary workflows.
