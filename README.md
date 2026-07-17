# PaperTrace

<p align="center">
  <strong>把论文、资讯与真实学习证据连接成一条可审计的个人研究工作流。</strong>
</p>

<p align="center">
  <a href="#pipelines">四条流水线</a> ·
  <a href="#paper-reader">论文 Reader</a> ·
  <a href="#daily-briefing">AI × Quantum 日报</a> ·
  <a href="#validation">验证</a> ·
  <a href="#safety">安全边界</a>
</p>

<p align="center">
  <img alt="Local first" src="https://img.shields.io/badge/Local--first-Research%20workspace-1f6feb?style=flat-square">
  <img alt="Source grounded" src="https://img.shields.io/badge/Source--grounded-Traceable-238636?style=flat-square">
  <img alt="Interactive HTML" src="https://img.shields.io/badge/Output-Interactive%20HTML-8250df?style=flat-square">
  <img alt="Feedback safe" src="https://img.shields.io/badge/Feedback-Profile--safe-dc6d1f?style=flat-square">
</p>

PaperTrace 是一个本地论文阅读、AI + 量子资讯日报与个人知识画像迭代工作区。它不把“生成摘要”当作终点，而是把来源证据、可交互阅读、显式反馈、长期画像和可验证教学连接为一条闭环。

> **核心原则：** 读过不等于掌握；曝光不等于已知；没有源证据、严格验证与真实学习表现，就不写入长期画像。

| 你想完成什么 | 从哪里开始 | 最终交付 |
|---|---|---|
| 把一篇论文变成可读、可标注的中文交互页面 | [论文 Reader](#paper-reader) | 经过对抗审计的 `reader_interactive.html` |
| 追踪 AI 与量子领域的当日重要变化 | [日报流水线](#daily-briefing) | HTML 日报、反馈 JSON、manifest 与索引 |
| 将本地聊天记录转成可审核的画像候选 | [知识画像](#knowledge-profile) | 经人工审核、带备份的 profile patch |
| 用已有证据选择下一次短课与复习 | [Adaptive Teach](#adaptive-teach) | 单主题课程与受控 feedback handoff |

<a id="pipelines"></a>

## 四条核心流水线

| 流水线 | 它解决的问题 | 完成边界 |
|---|---|---|
| **Paper Reader HTML** | 从 PDF/source paper 生成中英对照、公式可读、可反馈的正式 reader。 | 对抗审计通过的 `reader_interactive.html`；bundle 和 ledger 只是中间层。 |
| **AI + Quantum Daily Briefing Release** | 将当前信号转成有来源、可反馈的 AI + 量子日报。 | `run → verify → finalize → verify` 后的 HTML、feedback、manifest 与 index。 |
| **Local Chat-to-Profile Import** | 从本地聊天导出中提炼可复核的学习/研究候选。 | 人工审核后执行 `apply --backup`；候选和未应用 patch 都不是终态。 |
| **Adaptive Teaching Decision & Evidence Loop** | 以明确弱项、证据缺口和到期复习选择下一主题。 | 真实表现生成的 teaching feedback 经验证后安全导入；课程生成或浏览不等于掌握。 |

Reader/news feedback import 与 Visible Wiki 是共享下游工作流。Adaptive teaching 是 Pipeline 4，但仍只能显式调用，且没有真实表现时不得进入画像回写阶段。

## 设计取向

- **Local-first：** 论文、反馈与画像保持在本地工作区；发布时只提交可复现的公开代码与文档。
- **Evidence-first：** 每项关键结论都必须可回溯到论文、来源页面或明确的用户反馈。
- **Human-in-the-loop：** 候选、曝光和自动抽取不能直接等同于知识状态。
- **Deliverable-first：** Reader、日报、导入和教学各有明确终态，草稿与中间产物不冒充交付。

## Current Capabilities

- `ai-quantum-news-briefing` 可从 AI HOT API 或 `feed.xml` 拉取每日精编候选；AI HOT 只作为候选源，不作为最终证据源。
- 日报学术源覆盖 APS PRL/PRA/PRX、Nature、Science、OpenReview/ICLR、CVF/CVPR、PMLR/ICML、NeurIPS、ACL Anthology、Quantum Journal 和 arXiv；arXiv 条目标注为 preprint。
- 日报 HTML 生成时写出全量 `news_feedback.json`，所有知识点默认 `unrated`，用户编辑状态后可直接下载反馈 JSON。
- `academic_venue_sweep.py`、`aihot_candidates.py`、`config_to_news_feedback.py` 和 `audit_briefing_config.py` 分别支持候选池、学术检索审计、全量反馈导出和对抗性审核。
- `lean-html-skill` 的 Cosmic Sci-Fi Product Design System Layer 只控制视觉风格，不改变功能和信息架构；默认白色背景，可切换 Cosmic 深空背景。
- `reader-learner` 通过知识库重建、审计和安全测试，阻止噪声、乱码或未评级曝光被误写为已掌握知识。
- `chat-knowledge-profile` 把本地 ChatGPT/GPT/Claude/Deepseek 会话提炼为可审核候选、会话摘要和严格的 `reader-learner` feedback handoff。
- `demo-skill` 把 README/AGENTS 契约提炼为四条 pipeline 的中英文项目展示页，并复用 GSAP + ScrollTrigger 双语模板与无覆盖生成脚本。
- 日报加入可审计的 `news-ranker-v1`：先做证据准入，再按学术/社会两套分数和 MMR 多样性约束筛选；正式发布包含 7–8 篇学术论文和至少 10 条社会新闻，并保留分项得分、配额、选择轨迹与淘汰原因。

## Directory Layout

```text
D:\AI\PaperTrace
|-- 2026/                         # 当前按年份/月组织的论文与 reader
|-- news/                         # AI + 量子日报、多日报告和反馈产物
|-- readed/                       # 已读或已处理论文
|-- video/                        # 本地生成的视频与演示媒体
|-- skills/                       # 本地 Codex skills
|   |-- nature-reader/
|   |-- reader-skill/
|   |-- reader-learner/
|   |-- adaptive-teach/
|   |-- ai-quantum-news-briefing/
|   `-- utils/
|       |-- chat-knowledge-profile/
|       |-- demo-skill/
|       |-- lean-html-skill/
|       `-- neat-freak/           # 文档、规则和记忆层的同步审计
|-- .agents/                      # 项目 agent 上下文和长期学习画像
|   `-- wiki/                     # 持久的人工可见 Obsidian 知识层
`-- README.md
```

<a id="adaptive-teach"></a>

## Adaptive Teach

`skills/adaptive-teach` is the explicit-invocation teaching decision layer. It analyzes the sole schema-v2 profile source of truth, identifies explicit weakness versus evidence gaps versus due reviews, selects one small next target, and writes private Mission/session/lesson artifacts under `.agents/adaptive-teach/` (ignored by Git). It does not own profile schema, normalization, atomic mutation, reader generation, news collection, Visible Wiki projection, or the shared HTML shell.

`reader-learner` retains schema-v2 concepts/events/sources/review queue, strict validation, backup, atomic writes, imports, and wiki projection. The legacy `update_learner_profile.py review` command is a read-only compatibility delegate to adaptive-teach; teaching ranking and review pedagogy have one implementation.

Run from `D:\AI\PaperTrace`:

```powershell
python .\skills\adaptive-teach\scripts\adaptive_teach.py analyze
python .\skills\adaptive-teach\scripts\adaptive_teach.py next
python .\skills\adaptive-teach\scripts\adaptive_teach.py lesson --output-dir .\.tmp\adaptive-lesson
python .\skills\adaptive-teach\scripts\adaptive_teach.py validate-feedback --feedback <teaching_feedback.json>
python .\skills\adaptive-teach\scripts\adaptive_teach.py import-feedback --feedback <teaching_feedback.json>
```

Generating/viewing a lesson never changes the profile or queue. Only actual performance becomes a validated teaching handoff, imported through `feedback_visible_wiki_pipeline.py teaching-feedback`; that path performs backup, atomic update, and optional Visible Wiki sync.

## Persistent Visible Wiki

`.agents/wiki/` is a curated Obsidian vault for stable concepts, entities, themes, questions, syntheses, claims, source summaries, and knowledge-boundary maps. It is separate from the disposable profile projection at `.agents/reader-learner/obsidian-vault`.

The full stable learner profile is projected here: each normalized stable concept has one public concept page, and each profile source has one concise source-summary page. Raw PDFs, reader bundles, feedback/events, pipeline data, and the schema-v2 learner profile remain in their existing source-layer locations. Freeform annotations and opaque candidate IDs stay retained but hidden until they are normalized and reviewed.

Run from `D:\AI\PaperTrace`:

```powershell
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
python .\skills\reader-learner\scripts\lint_visible_wiki.py --profile .\.agents\reader-learner\knowledge_profile.json --wiki .\.agents\wiki --strict --require-profile-coverage
```

For one-step reader or news feedback ingestion, use `feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>` or `feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>`. Both preserve the existing importer validation and profile backup before projecting the wiki.

Open `D:\AI\PaperTrace\.agents\wiki` as the Obsidian vault. Start at `Home.md`, then use `maps/Profile Coverage.md` to verify complete profile projection. The default Graph View is restricted to rated knowledge concepts, entities, themes, questions, syntheses, and claims; source summaries and `unrated` contacts remain available through maps without becoming default graph hubs.

## Skill Boundaries

| Skill | 负责 | 不负责 |
|---|---|---|
| `skills/nature-reader` | 从 PDF/HTML/DOI/arXiv/文本生成 `paper.md`、`source_map.json`、`translation_notes.md` 和 `assets/`。 | 不更新长期画像，不把摘要冒充翻译。 |
| `skills/reader-skill` | 把 reader bundle 转成正式 `reader_interactive.html`，负责双语块、source anchors、概念标注、公式和图表结构。 | 不写 `.agents`，不直接修改画像。 |
| `skills/reader-learner` | 导入 reader/news feedback，维护 `.agents/reader-learner/knowledge_profile.json`，导出 Obsidian vault，审计知识库。 | 不生成论文 HTML，不生成教学课程。 |
| `skills/adaptive-teach` | 读取唯一 learner profile，区分薄弱/证据不足/到期复习，选择单一下一主题，生成诊断、短课、复习策略和 teaching-feedback handoff。 | 不维护 profile schema、normalization、atomic write、PDF/news、Visible Wiki 或通用 HTML shell。 |
| `skills/ai-quantum-news-briefing` | 生成 source-grounded AI + 量子日报/多日报告，接入 AI HOT 候选池，生成日报反馈 HTML/JSON，导入新闻反馈。 | 不因为新闻“出现过”就自动判定用户已经掌握。 |
| `skills/utils/lean-html-skill` | 共享 HTML shell、反馈面板、copy/download 导出控件、Cosmic Sci-Fi 视觉层和背景切换控件。 | 不做领域解释，不写 profile，不改变业务数据结构。 |
| `skills/utils/chat-knowledge-profile` | 从本地 ChatGPT/GPT/Claude/Deepseek 导出记录提炼会话摘要、概念状态候选、学习/研究/工作流偏好，并生成严格 `reader-learner` handoff。 | 不抓取分享 URL，不把助手曝光当作掌握证据，不绕过补丁审核直接覆盖 profile。 |
| `skills/utils/demo-skill` | 从经过核验的 README/AGENTS/source contract 生成结构等价的中文、英文四-pipeline 项目 demo，并负责模板物化与发布前审核。 | 不臆造 pipeline，不改业务数据，不把截图、浏览器 profile 或 QA 临时文件作为默认发布物。 |
| `skills/utils/neat-freak` | 对照代码、规则和发布产物同步 README、`.agents/` 与项目说明，清理重复、死引用和过期事实。 | 不把变更流水账塞进规则文件，不手改机器生成的 Codex memory，不新建业务 skill。 |

<a id="paper-reader"></a>

## Paper Reader Pipeline

目标：从原始 PDF 生成并正式审计 `reader_interactive.html`。这份 HTML 是 Pipeline 1 的终态；HTML 反馈导入长期画像是可选的下游 handoff，不是 PDF-to-HTML 完成条件。正式 reader 不是摘要页、draft preview 或 reader bundle；它必须经过 `reader_wiki` 规范化层和 hard gate。

### 1. PDF -> internal reader evidence (not deliverable)

The selectable-PDF bootstrap now writes immutable source evidence and automatically materializes a UTF-8 working `paper.md` with stable anchors and explicit completion markers. For an older raw bundle that contains `source_map.json` but lacks `paper.md`, run from `D:\AI\PaperTrace`:

```powershell
python .\skills\nature-reader\scripts\materialize_reader_markdown.py "<reader-dir>"
python .\skills\nature-reader\scripts\audit_reader_text.py "<reader-dir>\paper.md"
```

The materializer never overwrites an existing `paper.md` by default. Its markers must be replaced with faithful Chinese and block-specific notes before completion; the text audit and completion gate reject encoding corruption and incomplete markers.

### Formal Reader v3 (resumable and directory-selected)

`paper.md` and legacy `completion_ledger.json` are no longer formal source of
truth. The formal reader state is one atomic JSON record per source block,
formula, figure, table, algorithm, and reference under
`reader_wiki/completion_blocks/`, with a hash-bound
`completion_run_state.json`. The derived `canonical_reader.md` is the only
input that may be compiled into formal HTML.

Run from `D:\AI\PaperTrace`:

```powershell
python .\skills\reader-skill\scripts\build_formal_reader_batch.py --pdf-dir "<PDF-folder>" --reader-root "D:\AI\PaperTrace\2026\7" --agent-continuation
```

The specified directory is the complete input set. The command sorts only its
immediate PDFs and emits their exact paths and SHA-256 values in its JSON
standard output. It creates no batch-history or root-level state file. It validates any
formal-pass prefix and activates only the first incomplete paper; every later
paper remains `queued` and untouched. While any record or preflight check is
pending/invalid, it writes only `reader_progress.html` with an `INCOMPLETE / NOT
FORMAL` banner for that active paper. It must not write or report
`reader_interactive.html` as formal.

Every checkpoint embeds `agent_continuation_contract` in the same JSON standard
output. The default command exits successfully with `status: action_required` for expected
current-session model work; `--strict-exit` is available for CI callers that
need exit code 1 on incompleteness. An agent must continue while the contract
says `final_response_allowed: false`, directly complete the named
`active_paper`, and rerun its exact `next_command` without asking the user for
another message. Only `status: complete` makes the complete batch reportable.
A legacy HTML artifact is explicitly marked stale until a full v3 completion,
render, and adversarial audit pass.

Audit the batch response boundary from `D:\AI\PaperTrace` with:

```powershell
python .\skills\reader-skill\scripts\build_formal_reader_batch.py --pdf-dir "<PDF-folder>" --reader-root "D:\AI\PaperTrace\2026\7" --agent-continuation | python .\skills\reader-skill\tests\adversarial_batch_audit.py -
```

`nature-reader` 负责把 PDF 变成内部 source-grounded evidence/bundle。当前会话的主大模型按 skill contract 直接完成中文、块级注释与 LaTeX 重建；相关脚本只负责抽取、校验、编译与渲染。该阶段生成或修复同名 `*_reader/` 工作目录，并写出：

```text
<reader-dir>\paper.md
<reader-dir>\source_map.json
<reader-dir>\translation_notes.md
<reader-dir>\assets\
```

`paper.md` 必须是完整中英对照，不允许把“待忠实翻译”、摘要、阅读提示模板或 PDF 抽取噪声当作正式中文栏。图、表、算法和关键公式必须进入结构化 block/card：

- `Original`：放 source-faithful 正文和重建后的 LaTeX；所有段落中的数学内容都必须有显式定界符，重建公式后删除同一公式的 PDF 断行/纯文字副本；
- `中文`：忠实翻译，数学内容同样必须使用显式 LaTeX；需要逐组件严格对应的块以 `bilingual_math_contract: exact-v1` 声明，避免为了全局数量相等而删除合理的解释性公式；
- `source math inventory`：凡 bootstrap 标记为 `source_math_inventory_required` 的原文行（包括段落、图注和对象描述，而非仅公式行），必须在页级复核后保存完整、有序的 `source-math-inventory-v1` 组件清单；清单中的每个签名都须在 Original 与中文各渲染一次，不能用追加一个代表公式或全局删除定界符来“修复”；
- `注释`：只解释当前 block 的逻辑、知识点、公式读法或图表读法；
- figure/table：必须有编号、caption、中文说明、source page 和可检查内容；
- algorithm：完整正文保留源语言，仅实际注释可译为中文；以 `.tex` 经 XeLaTeX 编译为 `.svg`，并用 manifest/hash/编号步骤数约束完整性；
- formula：必须重构为可渲染 LaTeX，且一个展示块只承载一个逻辑公式；独立公式逐个展示，不能用 `\quad`/`\qquad` 或 `align`/`gather` 挤在一起。

如果 reader bundle 来自 draft extraction helper，先运行 completion pass：

```powershell
cd D:\AI\PaperTrace
python .\skills\nature-reader\scripts\complete_reader_bundle.py "<reader-dir>"
```

该脚本是内部 bundle 的严格验证与 ledger 写入步骤，不是 validation bypass、pipeline 终态或用户交付物，也不会自行清理占位符、补全翻译、规范公式或补齐图表/算法卡片。这些内容必须由当前会话主大模型直接完成后，再由该脚本验证；随后继续运行 `reader_wiki_compile.py`、HTML converter 与 publishing adversarial audit。

### Folder-level end-to-end trigger

当用户请求“阅读当前项目下的 readme 和 .agents，根据 PAPER 的 pipeline 将 `<PDF-folder>` 下的 PDF 生成对应的可交互 HTML，一篇一篇来”时，该请求本身授权完整处理整个文件夹。当前会话主模型必须按稳定顺序完成一篇的翻译、图表/公式重建、正式 HTML 生成与对抗性审计，再自动开始下一篇；“一篇一篇来”不是只做第一篇 bundle/草稿后等待确认。只有当源文件不可读、已有完成产物的覆盖意图不明确，或无法从 PDF 证据修复的严格验证失败时，才可暂停并报告具体阻断点。

### 2. reader bundle -> reader_wiki

显式编译规范化中间层：

```powershell
cd D:\AI\PaperTrace
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
<reader-dir>\reader_wiki\paper_summary.json
<reader-dir>\reader_wiki\structure_validation_report.json
<reader-dir>\reader_wiki\normalized_reader.md
```

`structure_validation_report.json` 必须是 `status: "pass"`。如果失败，修 `paper.md`、`source_map.json`、`assets/` 或 completion pass，不要使用 `--allow-draft-translation`，不要绕过 gate，不要把 draft HTML 当正式产物。

### 3. reader_wiki -> interactive HTML

生成正式 reader HTML：

```powershell
cd D:\AI\PaperTrace
python .\skills\reader-skill\scripts\markdown_reader_to_html.py "<reader-dir>" --output "<reader-dir>\reader_interactive.html" --profile ".\.agents\reader-learner\knowledge_profile.json"
```

正式 HTML 应满足：

- `reader_interactive.html` 是唯一正式 paper reader HTML；
- 顶部包含当前主模型撰写的详细中文论文总结，分别回答“做了什么、怎么做、有什么意义、证据与局限”，且每项链接到正式 source anchor；
- 阅读器按可用空间自适应：宽屏采用“左侧约 42% 起步的可拖拽大幅原始页—最低可读宽度正文—可拖拽 Contents”三栏布局，中等宽度默认把 Contents 收成可恢复窄条，窄屏自动纵向重排；Original、原始页图和 Contents 均可独立折叠，`Annotate / 自由标注` 展开时会让出布局空间或增加滚动安全区，不覆盖译文；
- 30-60 个候选知识点，已有 profile 状态会合并，论文核心概念即使 mastered 也要进入 glossary；
- 每个 knowledge mark 都有 `data-concept`、`data-concept-id`、`data-status`、`data-source-anchor`、`data-concept-type`、`data-alias-zh` 和 `title`；
- MathJax 存在且运行时状态为 pass；任何 Original、中文、论文总结或概念账本可见文本都不能出现裸 `\sigma`、`A^-1`、PDF 断裂公式、展示公式的文字重复副本或多公式挤在同一展示块；
- Source Page Index 链接保持普通相对路径，例如 `assets/source_pages/page-01.png`；
- figure/table card 不得被整页截图冒充，不得被 CSS 裁剪；algorithm card 必须展示构建期编译的完整 SVG，不得显示翻译后的重复算法正文；
- feedback panel、Download feedback JSON、Copy feedback for Codex fallback textarea、主题切换控件都要可用；
- Dark theme 必须通过实际对比度检查，不能只检查控件存在。

### 4. Adversarial audit

生成后必须跑对抗性 HTML 审核：

```powershell
cd D:\AI\PaperTrace
python .\skills\reader-skill\tests\adversarial_html_audit.py "<reader-dir>"
```

该审核会检查：`reader_wiki` 是否 pass、MathJax 加载/排版状态、所有可见面板的裸公式泄漏、声明为 `exact-v1` 的原文/中文公式组件对齐、一个展示块一个逻辑公式、重复纯文字公式清理、知识点 metadata、Save mark 后面板关闭、feedback 导出、Source Page Index href 污染、figure/table 裁剪、完整源码 Algorithm 的 XeLaTeX/SVG/manifest/hash/步骤数契约、主题控件和 Dark theme contrast/readability。

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
cd D:\AI\PaperTrace
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback "<reader_feedback.json>"
```

The pipeline first validates and imports feedback with a profile backup, then synchronizes the persistent visible wiki:

```powershell
cd D:\AI\PaperTrace
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync --dry-run
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py sync
```

`reader-learner` 会做 schema validation、concept normalize、乱码/HTML 残片/整句噪声拦截、UTF-8 JSON 读写和 atomic write。validation 失败时不得覆盖 profile。

### 7. Minimal regression commands

对单篇 reader 的最小回归链路：

```powershell
cd D:\AI\PaperTrace
python .\skills\nature-reader\scripts\complete_reader_bundle.py "<reader-dir>"
python .\skills\reader-skill\scripts\reader_wiki_compile.py "<reader-dir>" --profile ".\.agents\reader-learner\knowledge_profile.json"
python .\skills\reader-skill\scripts\markdown_reader_to_html.py "<reader-dir>"
python .\skills\reader-skill\tests\adversarial_html_audit.py "<reader-dir>"
```

<a id="daily-briefing"></a>

## News Briefing Pipeline

**End-to-end target:** the daily briefing pipeline is not complete at candidate collection, Markdown, or config generation. The final reader-facing artifact must be an interactive HTML reader plus its full default-`unrated` feedback JSON. Use `D:\AI\PaperTrace\news\2026-07-07_to_2026-07-09` as the canonical multi-day sample structure: Markdown briefing, HTML reader, feedback config, `news_feedback.json`, academic search ledger, and manifest live together in the same output directory.

For a daily run, the expected final files are:

```text
news\YYYY-MM-DD\daily_briefing_YYYY-MM-DD.md
news\YYYY-MM-DD\briefing_reader_YYYY-MM-DD.html
news\YYYY-MM-DD\news_feedback_YYYY-MM-DD.json
news\YYYY-MM-DD\news_feedback_config_delta_YYYY-MM-DD.json
news\YYYY-MM-DD\daily_pipeline_manifest_YYYY-MM-DD.json
news\YYYY-MM-DD\daily_pipeline_index_updates_YYYY-MM-DD.json
news\_index\story_index.jsonl
```

日报发布入口是 `daily_pipeline.py`。`run` 只写 staging，`verify` 只验证，只有 `finalize` 在验证成功后才会发布产物并原子 upsert `story_index.jsonl`：

```powershell
cd D:\AI\PaperTrace
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py run --config <candidate_news_feedback_config.json> --output-dir <news\YYYY-MM-DD> --index .\news\_index\story_index.jsonl
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py finalize --run-dir <news\YYYY-MM-DD\.staging\RUN_ID> --strict
python .\skills\ai-quantum-news-briefing\scripts\daily_pipeline.py verify --run-dir <news\YYYY-MM-DD> --strict
```

`daily_pipeline.py run` 会先执行 `news-ranker-v1`，再做 Delta 压缩。排名器先拒绝缺失/不安全证据、候选页、无效日期和重复身份，再分别计算学术与社会新闻分数，并用来源、主题和机构多样性约束选择最终条目。正式日报必须包含 7–8 篇学术论文和 10–14 条社会新闻（目标 12），同时把 `ranking_policy`、逐条 `ranking`、选择轨迹和淘汰原因保留到最终 delta config。

最终日报还必须满足共享 `sections/items` contract、HTTPS 来源、HTML/feedback identity 集合一致、默认全 `unrated`、无 feedback2、light 默认且 Cosmic 可选。学术 venue sweep 只有在官方 HTTPS endpoint 产生 HTTP 状态、最终 URL、时间戳、结果数和 response hash 后才算 evidence；搜索链接本身不算已检查。

2026-07-16 的本地发布是当前通过严格验证的参考实例：20 条内容（8 篇学术研究 + 12 条社会新闻）、60 个默认 `unrated` 概念，发布状态为 `complete`。产物位于 `news\2026-07-16\`（该目录按隐私/发布边界被 Git 忽略）；完整核验读数记录在 [`.agents/CHANGES.md`](.agents/CHANGES.md)。

`ai-quantum-news-briefing` 用于生成当前 AI、模型、产业、监管、学术和量子方向资讯。生成日报时必须核实当前信息并给出具体日期范围。

拉取 AI HOT 每日精编候选池：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source api --mode selected --take 50 --date <YYYY-MM-DD> --output D:\AI\PaperTrace\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>.json
```

RSS fallback：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py --source feed --take 50 --date <YYYY-MM-DD> --output D:\AI\PaperTrace\news\<YYYY-MM-DD>\aihot_candidates_<YYYY-MM-DD>_feed.json
```

生成学术源检索台账：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py --term "quantum walk graph neural network" --date-range <YYYY-MM-DD..YYYY-MM-DD> --format markdown --output <academic_venue_sweep.md>
```

从日报配置生成 HTML，并自动写出全量 `news_feedback.json`：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --feedback-output <news_feedback.json> --default-status unrated
```

只生成 JSON，不生成 HTML：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py --config <news_feedback_config.json> --output <news_feedback.json> --status unrated
```

导入新闻反馈到画像：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>
```

关键规则：

- AI HOT 是候选源，不是最终证据源。
- `news-ranker-v1` 必须在 Delta 之前运行；AI HOT 自带分数不能代替最终排名分数。
- 学术交付为 7–8 篇，其中 4–6 篇为 `new`、至少 2 篇来自非 arXiv 正式来源、最多 3 篇为 `continuing`。
- 社会新闻至少 10 条、目标 12 条；至少 7 条为 `new`/`material_update`，并满足来源类别、机构与主题多样性约束。
- 学术项优先引用期刊、会议、出版社、官方论文页；arXiv-only 必须标注 `preprint` 和 `venue_sweep_note`。
- 曝光型新闻概念默认 `unrated`，不得自动写成 `known` 或 `mastered`。
- HTML 页面只收集和下载反馈，不直接写 `.agents`。

## Lean HTML And Design Layer

`lean-html-skill` 是共享 HTML 层。它可以给现有 HTML 添加反馈面板，也可以只应用视觉设计层。

添加反馈面板：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py attach-feedback --html <report.html> --feedback <reader_or_news_feedback.json> --output <report_interactive.html>
```

只应用 Cosmic 视觉层，并保持白色背景为默认：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py apply-design --html <report.html> --design-system cosmic --background-mode light
```

审核视觉层：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py audit-design --html <report.html>
```

Design System Layer 只负责色彩、字体、组件风格、布局语言、轻量动效和视觉氛围；不改变页面功能、数据结构、用户需求解析、页面结构生成或代码输出流程。

## Bilingual Project Demo

`demo-skill` 保存了本次 PaperTrace 四-pipeline 项目展示页的中文、英文成品模板。它要求先读取仓库 `AGENTS.md`、其指向的 canonical `.agents` 文档和根 `README.md`，再核验 pipeline 名称、阶段、handoff、输出和 hard gate；模板只提供表现层，不能替代项目事实。

从 `D:\AI\PaperTrace` 运行：

```powershell
python .\skills\utils\demo-skill\scripts\create_demo.py --output-dir .
```

默认生成 `demo.html` 与 `demo-en.html`，已有任一目标文件时会拒绝覆盖；只有明确需要替换时才使用 `--force`。页面以静态语义 HTML 为基线，GSAP + ScrollTrigger/Lenis 为渐进增强，并提供 reduced-motion 与脚本加载失败时的可读回退。

发布时只提交两份目标 HTML 与 `skills/utils/demo-skill/` 的必要文件。根目录 `/*.html` 被 `.gitignore` 默认忽略，因此确认范围后需要对 `demo.html` 和 `demo-en.html` 使用精确的 `git add -f --`；不要提交 `.design/`、截图、浏览器 profile、QA 临时日志或其他脏工作区改动。

<a id="knowledge-profile"></a>

## Knowledge Profile

`knowledge_profile.json` 是长期学习数据，只能通过导入/更新脚本修改。不要手动编辑该文件来绕过校验。

导入 reader feedback：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py reader-feedback --feedback <reader_feedback.json>
```

### Local Chat-to-Profile Import Pipeline

从本地 GPT/ChatGPT/Claude/Deepseek 导出记录生成画像补丁：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py extract --events D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\events.jsonl --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py propose --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --candidates D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py apply --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json --patch D:\AI\PaperTrace\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

该流程会额外生成 `conversation_summaries.json`，用于快速查看每个会话的 `at_a_glance`、topic tags、显式偏好、开放问题和动作型请求。正式写入画像前应先人工检查 `profile_patch.json`；概念状态候选会通过 `reader-learner` 严格 schema 导入。

<a id="validation"></a>

## Validation

常用静态校验：

```powershell
cd D:\AI\PaperTrace
python -m py_compile D:\AI\PaperTrace\skills\reader-skill\scripts\markdown_reader_to_html.py
python -m py_compile D:\AI\PaperTrace\skills\nature-reader\scripts\complete_reader_bundle.py
python -m py_compile D:\AI\PaperTrace\skills\reader-learner\scripts\profile_v2.py
python -m py_compile D:\AI\PaperTrace\skills\reader-learner\scripts\import_reader_feedback.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\aihot_candidates.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\academic_venue_sweep.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py
python -m py_compile D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\audit_briefing_config.py
python -m py_compile D:\AI\PaperTrace\skills\utils\lean-html-skill\scripts\lean_html.py
python -m py_compile D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\init_knowledge_profile.py
python -m py_compile D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python D:\AI\PaperTrace\skills\utils\chat-knowledge-profile\scripts\audit_chat_knowledge_profile.py
python -m py_compile D:\AI\PaperTrace\skills\utils\demo-skill\scripts\create_demo.py
python -X utf8 "$env:USERPROFILE\.codex\skills\.system\skill-creator\scripts\quick_validate.py" D:\AI\PaperTrace\skills\utils\demo-skill
```

Reader end-to-end 测试：

```powershell
cd D:\AI\PaperTrace
python D:\AI\PaperTrace\skills\reader-skill\tests\test_reader_e2e.py
```

<a id="safety"></a>

## Safety Rules

### Daily Briefing UTF-8 Gate

Daily briefing configs and published Markdown/JSON/HTML must use UTF-8. The normalizer rejects `U+FFFD` and high-density literal `?` in human-readable fields; do not build Chinese JSON through a default PowerShell code-page here-string, and do not “repair” lost text by deleting question marks. Regenerate from the original source record instead. Corrupt historical story-index summaries are omitted during delta compaction and must never leak into new HTML. `daily_pipeline.py verify --strict` audits visible HTML text before the story index can be updated.

## GitHub 发布与隐私边界

GitHub 发布只包含可复现的代码、公开文档、测试与有意维护的示例资产；不得上传个人学习画像、教学会话、可见 Wiki 投影、论文语料与 reader bundle、浏览器/IDE 状态、Cookie/会话、密钥、机器配置或本地生成的音视频。发布前必须执行 `git status --short` 与暂存区审查，使用显式路径暂存，绝不以 `git add -A` 把混合工作区整体提交。`.gitignore` 是防误提交的第二道防线，不能替代提交前检查；已经被 Git 跟踪的敏感文件必须先停止跟踪并确认其历史处置方案。

- 除个人画像的明确读取、导入、同步任务外，不要打开、打印、复制、总结、上传或修改疑似密钥、密码、令牌或凭据文件。
- 不要手动编辑 `knowledge_profile.json` 绕过 `reader-learner`。
- 不要把整页 PDF source page 当作正文 figure 插入；正文只放可靠裁剪图、结构化图表或可审计描述。
- 不要把意译、摘要、阅读提示伪装成中英对照翻译。
- 不要因为某个概念出现在日报里就把用户状态写成 `known`；默认应保持 `unrated`。

## Acknowledgements And Inspirations

本项目的 reader、知识画像、日报候选池、HTML 设计层和 agent 上下文工作流借鉴了以下项目、资料和本地 skill 设计：

- [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills)：`nature-reader` 思路，尤其是 source-grounded 全文阅读、图表位置保留、术语表和 Markdown bundle 输出结构。
- [AI HOT skill](https://aihot.virxact.com/aihot-skill/) 和 [AI HOT feed.xml](https://aihot.virxact.com/feed.xml)：作为 AI 日报候选池与中文精选资讯发现机制的参考。当前项目只把它作为候选源，最终日报仍需要核实原始来源。
- [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills/tree/main)：感谢其公开的 `aihot` 候选发现与 `neat-freak` 文档治理思路；本项目将前者限制在发现层，并将后者用于 README、`.agents/`、技能契约和双语说明的同步维护。
- [Leonxlnx/taste-skill](https://github.com/Leonxlnx/taste-skill)：作为 HTML/product taste、控件协调性、可读性优先和设计审计思路的参考。
- OpenAI Product Design workflow：用于明确“Design System Layer 只改变视觉，不改变核心功能和信息架构”的产品设计约束。
- [greg-asher/codex-obsidian](https://github.com/greg-asher/codex-obsidian)：用于理解 Codex 与 Obsidian、本地仓库之间的衔接方式，启发 `.agents/reader-learner/obsidian-vault` 的同步和诊断脚本设计。
- [ar9av/obsidian-wiki](https://github.com/ar9av/obsidian-wiki)：用于借鉴 wiki 式知识组织、MOC、知识点页面和图谱表达方式。
- [Eden-Eldith/ChatInsights](https://github.com/Eden-Eldith/ChatInsights)：用于借鉴多平台聊天导出解析、概念跟踪、Obsidian-ready 会话组织和训练对抽取思路；本项目仅吸收架构原则，不复用其 GPL 代码。
- [ygivenx/gpt-obsidian](https://github.com/ygivenx/gpt-obsidian)：用于借鉴增量导入、每会话笔记、topic tags/backlinks、月度索引和导入报告思路，并适配为 `chat-knowledge-profile` 的可审核画像候选流程。
- `D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill`：用于生成和维护 `.agents` 项目上下文，帮助后续 Codex 会话快速理解项目边界、命令、数据位置和安全规则。

上述来源提供的是架构、交互、候选池和设计参考；本仓库中的个人画像、反馈导入、论文 reader 生成、日报学术检索策略和知识边界迭代逻辑均按本地需求重新组织实现。
