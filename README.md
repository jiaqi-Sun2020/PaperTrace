# PAPER

PAPER 是一个本地论文阅读、AI + 量子资讯日报、个人知识画像迭代工作区。核心目标不是“生成摘要”，而是形成一条可追溯、可标注、可导入长期画像的阅读流水线：

1. 从论文或新闻生成 source-grounded 阅读材料。
2. 生成可交互 HTML。
3. 在 HTML 中标注会、不会、哪里卡住，或直接编辑默认反馈。
4. 下载反馈 JSON。
5. 通过 `reader-learner` 更新 `.agents/reader-learner/knowledge_profile.json`。
6. 通过反馈生成解释报告、研究推导和后续复习材料。

## Recent Updates

- `ai-quantum-news-briefing` 已接入 AI HOT 候选池，可从 AI HOT API 或 `feed.xml` 拉取每日精编候选，默认作为候选源而不是最终证据源。
- 日报学术源策略升级：不再只看 arXiv；学术项需要优先检查 APS PRL/PRA/PRX、Nature、Science、OpenReview/ICLR、CVF/CVPR、PMLR/ICML、NeurIPS、ACL Anthology、Quantum Journal，再把 arXiv 标注为 preprint。
- 日报 HTML 现在会在生成时自动写出全量 `news_feedback.json`，所有知识点默认 `unrated`；用户只需要编辑状态后点击 `Download JSON`。
- 新增低 token 的 `academic_venue_sweep.py`、`aihot_candidates.py`、`config_to_news_feedback.py` 和 `audit_briefing_config.py`，用于候选池、学术检索审计、全量反馈导出和对抗性审核。
- `lean-html-skill` 新增 Cosmic Sci-Fi Product Design System Layer：保留原功能和信息架构，只控制视觉风格；默认白色背景，可通过页面控件切换 Cosmic 深空背景。
- `reader-learner` 增加知识库重建、审计和安全测试，用来避免把噪声、乱码或未评级曝光误写成已掌握知识。
- `chat-knowledge-profile` 替代旧 `init-knowledge-profile`：借鉴 ChatInsights 和 gpt-obsidian 的聊天归档/概念跟踪/Obsidian 导航/增量导入思路，把本地 ChatGPT/GPT/Claude/Deepseek 会话提炼为可审核候选、会话摘要和严格 `reader-learner` feedback handoff。
- 新增 `demo-skill`：把 README/AGENTS 契约提炼为三条 pipeline 的中英文项目展示页，并复用本次 GSAP + ScrollTrigger 双语模板与无覆盖生成脚本。

## Directory Layout

```text
C:\Users\SSS\Desktop\PAPER
|-- 2024/                         # 按年份归档的论文
|-- 2025/
|-- 2026/
|-- news/                         # AI + 量子日报、多日报告和反馈产物
|-- readed/                       # 已读或已处理论文
|-- skills/                       # 本地 Codex skills
|   |-- nature-reader/
|   |-- reader-skill/
|   |-- reader-learner/
|   |-- read-feedback-skill/
|   |-- ai-quantum-news-briefing/
|   `-- utils/
|       |-- chat-knowledge-profile/
|       |-- demo-skill/
|       `-- lean-html-skill/
|-- .agents/                      # 项目 agent 上下文和长期学习画像
|   `-- wiki/                     # 持久的人工可见 Obsidian 知识层
`-- README.md
```

## Persistent Visible Wiki

`.agents/wiki/` is a curated Obsidian vault for stable concepts, entities, themes, questions, syntheses, claims, source summaries, and knowledge-boundary maps. It is separate from the disposable profile projection at `.agents/reader-learner/obsidian-vault`.

The full stable learner profile is projected here: each normalized stable concept has one public concept page, and each profile source has one concise source-summary page. Raw PDFs, reader bundles, feedback/events, pipeline data, and the schema-v2 learner profile remain in their existing source-layer locations. Freeform annotations and opaque candidate IDs stay retained but hidden until they are normalized and reviewed.

Run from `C:\Users\SSS\Desktop\PAPER`:

```powershell
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
python .\skills\reader-learner\scripts\lint_visible_wiki.py --profile .\.agents\reader-learner\knowledge_profile.json --wiki .\.agents\wiki --strict --require-profile-coverage
```

For one-step reader or news feedback ingestion, use `feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>` or `feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>`. Both preserve the existing importer validation and profile backup before projecting the wiki.

Open `C:\Users\SSS\Desktop\PAPER\.agents\wiki` as the Obsidian vault. Start at `Home.md`, then use `maps/Profile Coverage.md` to verify complete profile projection. The default Graph View is restricted to rated knowledge concepts, entities, themes, questions, syntheses, and claims; source summaries and `unrated` contacts remain available through maps without becoming default graph hubs.

## Skill Boundaries

| Skill | 负责 | 不负责 |
|---|---|---|
| `skills/nature-reader` | 从 PDF/HTML/DOI/arXiv/文本生成 `paper.md`、`source_map.json`、`translation_notes.md` 和 `assets/`。 | 不更新长期画像，不把摘要冒充翻译。 |
| `skills/reader-skill` | 把 reader bundle 转成正式 `reader_interactive.html`，负责双语块、source anchors、概念标注、公式和图表结构。 | 不写 `.agents`，不直接修改画像。 |
| `skills/reader-learner` | 导入 reader/news feedback，维护 `.agents/reader-learner/knowledge_profile.json`，导出 Obsidian vault，审计知识库。 | 不生成论文 HTML，不写解释报告。 |
| `skills/read-feedback-skill` | 基于 feedback、profile、source map 生成解释报告、context pack、研究推导和 HTML。 | 不修改 profile。 |
| `skills/ai-quantum-news-briefing` | 生成 source-grounded AI + 量子日报/多日报告，接入 AI HOT 候选池，生成日报反馈 HTML/JSON，导入新闻反馈。 | 不因为新闻“出现过”就自动判定用户已经掌握。 |
| `skills/utils/lean-html-skill` | 共享 HTML shell、反馈面板、copy/download 导出控件、Cosmic Sci-Fi 视觉层和背景切换控件。 | 不做领域解释，不写 profile，不改变业务数据结构。 |
| `skills/utils/chat-knowledge-profile` | 从本地 ChatGPT/GPT/Claude/Deepseek 导出记录提炼会话摘要、概念状态候选、学习/研究/工作流偏好，并生成严格 `reader-learner` handoff。 | 不抓取分享 URL，不把助手曝光当作掌握证据，不绕过补丁审核直接覆盖 profile。 |
| `skills/utils/demo-skill` | 从经过核验的 README/AGENTS/source contract 生成结构等价的中文、英文三-pipeline 项目 demo，并负责模板物化与发布前审核。 | 不臆造 pipeline，不改业务数据，不把截图、浏览器 profile 或 QA 临时文件作为默认发布物。 |

## Paper Reader Pipeline

目标：从原始 PDF 生成正式 `reader_interactive.html`，并把 HTML 中导出的反馈安全导入长期知识画像。正式 reader 不是摘要页，也不是 draft preview；它必须经过 `reader_wiki` 规范化层和 hard gate。

### 1. PDF -> reader bundle

`nature-reader` 负责把 PDF 变成 source-grounded reader bundle。当前这一步主要由 Codex 按 skill contract 执行：读取 PDF/source pages，生成或修复同名 `*_reader/` 目录，并写出：

```text
<reader-dir>\paper.md
<reader-dir>\source_map.json
<reader-dir>\translation_notes.md
<reader-dir>\assets\
```

`paper.md` 必须是完整中英对照，不允许把“待忠实翻译”、摘要、阅读提示模板或 PDF 抽取噪声当作正式中文栏。图、表、算法和关键公式必须进入结构化 block/card：

- `Original`：只放原文和必要 LaTeX；
- `中文`：忠实翻译，并保留对应 LaTeX；
- `注释`：只解释当前 block 的逻辑、知识点、公式读法或图表读法；
- figure/table/algorithm：必须有编号、caption、中文说明、source page 和可检查内容；
- formula：必须重构为可渲染 LaTeX，交给 MathJax 渲染。

如果 reader bundle 来自 draft extraction helper，先运行 completion pass：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\nature-reader\scripts\complete_reader_bundle.py "<reader-dir>"
```

该脚本是 bundle 修复/补全步骤，不是 validation bypass。它应清理占位符、补全翻译、规范公式、补齐图表/算法卡片，然后让后续 `reader_wiki_compile.py` 决定是否允许生成正式 HTML。

### 2. reader bundle -> reader_wiki

显式编译规范化中间层：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\reader-skill\scripts\reader_wiki_compile.py "<reader-dir>" --profile ".\.agents\reader-learner\knowledge_profile.json"
```

输出目录：

```text
<reader-dir>\reader_wiki\reader_manifest.json
<reader-dir>\reader_wiki\concept_ledger.json
<reader-dir>\reader_wiki\formula_ledger.json
<reader-dir>\reader_wiki\figure_table_ledger.json
<reader-dir>\reader_wiki\algorithm_ledger.json
<reader-dir>\reader_wiki\claim_contribution_ledger.json
<reader-dir>\reader_wiki\annotation_metadata.json
<reader-dir>\reader_wiki\structure_validation_report.json
<reader-dir>\reader_wiki\normalized_reader.md
```

`structure_validation_report.json` 必须是 `status: "pass"`。如果失败，修 `paper.md`、`source_map.json`、`assets/` 或 completion pass，不要使用 `--allow-draft-translation`，不要绕过 gate，不要把 draft HTML 当正式产物。

### 3. reader_wiki -> interactive HTML

生成正式 reader HTML：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\reader-skill\scripts\markdown_reader_to_html.py "<reader-dir>" --output "<reader-dir>\reader_interactive.html" --profile ".\.agents\reader-learner\knowledge_profile.json"
```

正式 HTML 应满足：

- `reader_interactive.html` 是唯一正式 paper reader HTML；
- 30-60 个候选知识点，已有 profile 状态会合并，论文核心概念即使 mastered 也要进入 glossary；
- 每个 knowledge mark 都有 `data-concept`、`data-status`、`data-source-anchor`、`data-concept-type`、`data-alias-zh` 和 `title`；
- MathJax 存在，公式可渲染，不能出现 raw PDF formula noise；
- Source Page Index 链接保持普通相对路径，例如 `assets/source_pages/page-01.png`；
- figure/table/algorithm card 不得被整页截图冒充，不得被 CSS 裁剪；
- feedback panel、Download feedback JSON、Copy feedback for Codex fallback textarea、主题切换控件都要可用；
- Dark theme 必须通过实际对比度检查，不能只检查控件存在。

### 4. Adversarial audit

生成后必须跑对抗性 HTML 审核：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\reader-skill\tests\adversarial_html_audit.py "<reader-dir>"
```

该审核会检查：`reader_wiki` 是否 pass、MathJax、公式噪声、知识点 metadata、Save mark 后面板关闭、feedback 导出、Source Page Index href 污染、figure/table 裁剪、algorithm card 完整性、主题控件和 Dark theme contrast/readability。

### 5. HTML feedback -> reader_feedback.json

在 `reader_interactive.html` 中阅读时：

1. 点击高亮知识点，或选中文本添加 free annotation；
2. 选择 `mastered`、`known`、`learning`、`unknown` 或 `unrated`；
3. 填写问题、笔记、解释偏好或卡点；
4. 点击 `Save mark`，面板会关闭，页面保留已标注状态；
5. 点击 `Download feedback JSON` 下载 `reader_feedback.json`；
6. 如果浏览器禁止剪贴板，使用 `Copy feedback for Codex` 的 fallback textarea 取回 JSON。

HTML 只负责收集和导出 feedback；它不直接写 `.agents/reader-learner/knowledge_profile.json`。

### 6. reader_feedback.json -> knowledge profile

导入反馈到长期知识画像：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback "<reader_feedback.json>"
```

The pipeline first validates and imports feedback with a profile backup, then synchronizes the persistent visible wiki:

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
```

`reader-learner` 会做 schema validation、concept normalize、乱码/HTML 残片/整句噪声拦截、UTF-8 JSON 读写和 atomic write。validation 失败时不得覆盖 profile。

### 7. Minimal regression commands

对单篇 reader 的最小回归链路：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\nature-reader\scripts\complete_reader_bundle.py "<reader-dir>"
python .\skills\reader-skill\scripts\reader_wiki_compile.py "<reader-dir>" --profile ".\.agents\reader-learner\knowledge_profile.json"
python .\skills\reader-skill\scripts\markdown_reader_to_html.py "<reader-dir>"
python .\skills\reader-skill\tests\adversarial_html_audit.py "<reader-dir>"
```

## News Briefing Pipeline

**End-to-end target:** the daily briefing pipeline is not complete at candidate collection, Markdown, or config generation. The final reader-facing artifact must be an interactive HTML reader plus its full default-`unrated` feedback JSON. Use `C:\Users\SSS\Desktop\PAPER\news\2026-07-07_to_2026-07-09` as the canonical multi-day sample structure: Markdown briefing, HTML reader, feedback config, `news_feedback.json`, academic search ledger, and manifest live together in the same output directory.

For a daily run, the expected final files are:

```text
news\YYYY-MM-DD\daily_briefing_YYYY-MM-DD.md
news\YYYY-MM-DD\briefing_reader_YYYY-MM-DD.html
news\YYYY-MM-DD\news_feedback_YYYY-MM-DD.json
news\YYYY-MM-DD\news_feedback_config_delta_YYYY-MM-DD.json
news\YYYY-MM-DD\daily_pipeline_manifest_YYYY-MM-DD.json
news\_index\story_index.jsonl
```

日报发布入口是 `daily_pipeline.py`。`run` 只写 staging，`verify` 只验证，只有 `finalize` 在验证成功后才会发布产物并原子 upsert `story_index.jsonl`：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run --config <candidate_news_feedback_config.json> --output-dir <news\YYYY-MM-DD> --index .\news\_index\story_index.jsonl
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD\.staging\RUN_ID>
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py finalize --run-dir <news\YYYY-MM-DD\.staging\RUN_ID>
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD>
```

最终日报必须满足共享 `sections/items` contract、HTTPS 来源、HTML/feedback identity 集合一致、默认全 `unrated`、无 feedback2、light 默认且 Cosmic 可选。学术 venue sweep 只有在官方 HTTPS endpoint 产生 HTTP 状态、最终 URL、时间戳、结果数和 response hash 后才算 evidence；搜索链接本身不算已检查。

`ai-quantum-news-briefing` 用于生成当前 AI、模型、产业、监管、学术和量子方向资讯。生成日报时必须核实当前信息并给出具体日期范围。

拉取 AI HOT 每日精编候选池：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <YYYY-MM-DD> --output C:\Users\SSS\Desktop\PAPER\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>.json
```

RSS fallback：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source feed --take 50 --date <YYYY-MM-DD> --output C:\Users\SSS\Desktop\PAPER\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>_feed.json
```

生成学术源检索台账：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py --term "quantum walk graph neural network" --date-range <YYYY-MM-DD..YYYY-MM-DD> --format markdown --output <academic_venue_sweep.md>
```

从日报配置生成 HTML，并自动写出全量 `news_feedback.json`：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --feedback-output <news_feedback.json> --default-status unrated
```

只生成 JSON，不生成 HTML：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py --config <news_feedback_config.json> --output <news_feedback.json> --status unrated
```

导入新闻反馈到画像：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>
```

关键规则：

- AI HOT 是候选源，不是最终证据源。
- 学术项优先引用期刊、会议、出版社、官方论文页；arXiv-only 必须标注 `preprint` 和 `venue_sweep_note`。
- 曝光型新闻概念默认 `unrated`，不得自动写成 `known` 或 `mastered`。
- HTML 页面只收集和下载反馈，不直接写 `.agents`。

## Lean HTML And Design Layer

`lean-html-skill` 是共享 HTML 层。它可以给现有 HTML 添加反馈面板，也可以只应用视觉设计层。

添加反馈面板：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json> --output <report_interactive.html>
```

只应用 Cosmic 视觉层，并保持白色背景为默认：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py apply-design --html <report.html> --design-system cosmic --background-mode light
```

审核视觉层：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py audit-design --html <report.html>
```

Design System Layer 只负责色彩、字体、组件风格、布局语言、轻量动效和视觉氛围；不改变页面功能、数据结构、用户需求解析、页面结构生成或代码输出流程。

## Bilingual Project Demo

`demo-skill` 保存了本次 PAPER 三-pipeline 项目展示页的中文、英文成品模板。它要求先读取仓库 `AGENTS.md`、其指向的 canonical `.agents` 文档和根 `README.md`，再核验 pipeline 名称、阶段、handoff、输出和 hard gate；模板只提供表现层，不能替代项目事实。

从 `C:\Users\SSS\Desktop\PAPER` 运行：

```powershell
python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .
```

默认生成 `demo.html` 与 `demo-en.html`，已有任一目标文件时会拒绝覆盖；只有明确需要替换时才使用 `--force`。页面以静态语义 HTML 为基线，GSAP + ScrollTrigger/Lenis 为渐进增强，并提供 reduced-motion 与脚本加载失败时的可读回退。

发布时只提交两份目标 HTML 与 `skills/utils/demo-skill/` 的必要文件。根目录 `/*.html` 被 `.gitignore` 默认忽略，因此确认范围后需要对 `demo.html` 和 `demo-en.html` 使用精确的 `git add -f --`；不要提交 `.design/`、截图、浏览器 profile、QA 临时日志或其他脏工作区改动。

## Knowledge Profile

`knowledge_profile.json` 是长期学习数据，只能通过导入/更新脚本修改。不要手动编辑该文件来绕过校验。

导入 reader feedback：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>
```

从本地 GPT/ChatGPT/Claude/Deepseek 导出记录生成画像补丁：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py extract --events C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\events.jsonl --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py propose --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --candidates C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py apply --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --patch C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

该流程会额外生成 `conversation_summaries.json`，用于快速查看每个会话的 `at_a_glance`、topic tags、显式偏好、开放问题和动作型请求。正式写入画像前应先人工检查 `profile_patch.json`；概念状态候选会通过 `reader-learner` 严格 schema 导入。

## Validation

常用静态校验：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\nature-reader\scripts\complete_reader_bundle.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\profile_v2.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\render_research_deep_dive_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\audit_briefing_config.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python C:\Users\SSS\Desktop\PAPER\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\demo-skill\scripts\create_demo.py
python -X utf8 C:\Users\SSS\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\SSS\Desktop\PAPER\skills\utils\demo-skill
```

Reader end-to-end 测试：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\test_reader_e2e.py
```

## Safety Rules

### Daily Briefing UTF-8 Gate

Daily briefing configs and published Markdown/JSON/HTML must use UTF-8. The normalizer rejects `U+FFFD` and high-density literal `?` in human-readable fields; do not build Chinese JSON through a default PowerShell code-page here-string, and do not “repair” lost text by deleting question marks. Regenerate from the original source record instead. Corrupt historical story-index summaries are omitted during delta compaction and must never leak into new HTML. `daily_pipeline.py verify --strict` audits visible HTML text before the story index can be updated.

- 除个人画像的明确读取、导入、同步任务外，不要打开、打印、复制、总结、上传或修改疑似密钥、密码、令牌或凭据文件。
- 不要手动编辑 `knowledge_profile.json` 绕过 `reader-learner`。
- 不要把整页 PDF source page 当作正文 figure 插入；正文只放可靠裁剪图、结构化图表或可审计描述。
- 不要把意译、摘要、阅读提示伪装成中英对照翻译。
- 不要因为某个概念出现在日报里就把用户状态写成 `known`；默认应保持 `unrated`。

## Acknowledgements And Inspirations

本项目的 reader、知识画像、日报候选池、HTML 设计层和 agent 上下文工作流借鉴了以下项目、资料和本地 skill 设计：

- [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)：`nature-reader` 思路，尤其是 source-grounded 全文阅读、图表位置保留、术语表和 Markdown bundle 输出结构。
- [AI HOT skill](https://aihot.virxact.com/aihot-skill/) 和 [AI HOT feed.xml](https://aihot.virxact.com/feed.xml)：作为 AI 日报候选池与中文精选资讯发现机制的参考。当前项目只把它作为候选源，最终日报仍需要核实原始来源。
- [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)：作为 HTML/product taste、控件协调性、可读性优先和设计审计思路的参考。
- OpenAI Product Design workflow：用于明确“Design System Layer 只改变视觉，不改变核心功能和信息架构”的产品设计约束。
- [greg-asher/codex-obsidian](https://github.com/greg-asher/codex-obsidian)：用于理解 Codex 与 Obsidian、本地仓库之间的衔接方式，启发 `.agents/reader-learner/obsidian-vault` 的同步和诊断脚本设计。
- [ar9av/obsidian-wiki](https://github.com/ar9av/obsidian-wiki)：用于借鉴 wiki 式知识组织、MOC、知识点页面和图谱表达方式。
- [Eden-Eldith/ChatInsights](https://github.com/Eden-Eldith/ChatInsights)：用于借鉴多平台聊天导出解析、概念跟踪、Obsidian-ready 会话组织和训练对抽取思路；本项目仅吸收架构原则，不复用其 GPL 代码。
- [ygivenx/gpt-obsidian](https://github.com/ygivenx/gpt-obsidian)：用于借鉴增量导入、每会话笔记、topic tags/backlinks、月度索引和导入报告思路，并适配为 `chat-knowledge-profile` 的可审核画像候选流程。
- `D:\AI\skill\S_paper_skills\util_skills\research-html-report`：作为 HTML 研究报告视觉与结构参考，影响 `read-feedback-skill` 的报告布局、公式渲染、证据矩阵和打印友好样式。
- `D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill`：用于生成和维护 `.agents` 项目上下文，帮助后续 Codex 会话快速理解项目边界、命令、数据位置和安全规则。

上述来源提供的是架构、交互、候选池和设计参考；本仓库中的个人画像、反馈导入、论文 reader 生成、日报学术检索策略和知识边界迭代逻辑均按本地需求重新组织实现。
