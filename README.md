# PAPER

## Current Reader Contract (llm-wiki)

Formal paper readers are generated through a normalized `reader_wiki/` layer, not directly from PDF extraction noise.

From the project root, the supported command is:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --output <reader-dir>\reader_interactive.html --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

The command first writes and validates:

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

If validation fails, `reader_interactive.html` must not be written or reported as complete. Full papers should expose 30-60 concept candidates, LaTeX/MathJax formulas, clean Original / Chinese / Notes blocks, figure/table/algorithm cards, complete knowledge-mark metadata, and a feedback panel that closes after `Save mark`. Algorithms must preserve original numbered steps and Chinese numbered steps; summaries are invalid.

After generation, run the adversarial HTML audit before reporting success:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>
```

The audit is part of the formal pipeline. It checks the same failure modes that previously reached the browser: algorithm summaries, missing Algorithm cards, uncompiled or polluted math, broken Source Page Index links, incomplete concept metadata, insufficient concept coverage, reader-notes pollution, and feedback UI regressions.

Source Page Index links must remain plain relative links such as `assets/source_pages/page-01.png`. Inline-math or concept annotation must never run inside `href` attributes or file paths. `Copy feedback for Codex` must also expose a visible fallback textarea when clipboard access is unavailable, so feedback is never trapped in the page.

`knowledge_profile.json` is long-term learner data. It may only be updated through `reader-learner` import/update scripts, which validate feedback schema, normalize concepts and aliases, reject mojibake/HTML/PDF noise, write UTF-8 JSON with `ensure_ascii=False`, and atomically replace the profile only after validation succeeds.

本项目是本地论文阅读、AI+量子资讯、个人知识边界迭代工作区。

核心目标不是只做摘要，而是形成一条可追溯的阅读流水线：

1. 从论文或新闻生成 source-grounded 阅读材料。
2. 生成可交互 HTML。
3. 在 HTML 中标注会/不会/哪里卡住。
4. 手动导出 feedback JSON。
5. 用 `reader-learner` 更新 `.agents/reader-learner/knowledge_profile.json`。
6. 用 `read-feedback-skill` 生成针对个人知识边界的解释、推导和研究报告。

## 目录结构

```text
C:\Users\SSS\Desktop\PAPER
|-- 2024/                         # 按年份归档的论文
|-- 2025/
|-- 2026/
|-- news/                         # AI+量子日报/多日报及反馈产物
|-- readed/                       # 已读或已处理论文
|-- skills/                       # 本项目本地 Codex skills
|   |-- nature-reader/
|   |-- reader-skill/
|   |-- reader-learner/
|   |-- read-feedback-skill/
|   |-- ai-quantum-news-briefing/
|   `-- utils/
|       |-- init-knowledge-profile/
|       `-- lean-html-skill/
|-- .agents/                      # 项目 agent 上下文和长期学习画像
`-- README.md
```

## Skill 职责边界

| Skill | 职责 | 不负责 |
|---|---|---|
| `skills/nature-reader` | 从 PDF/HTML/DOI/arXiv/文本生成 `paper.md`、`source_map.json`、`translation_notes.md`、`assets/`。`中文` 栏必须是忠实翻译。 | 不生成长期画像，不把摘要冒充翻译。 |
| `skills/reader-skill` | 负责 reader bundle 的解析、翻译校验、source anchors、双语块语义和 learner-profile annotation metadata；当前 HTML 命令保留为兼容入口。 | 不翻译论文，不写 `.agents`，不新增可复用 HTML/反馈 UI。 |
| `skills/reader-learner` | 导入 reader/news feedback，维护 `.agents/reader-learner/knowledge_profile.json`，导出 Obsidian vault。 | 不生成论文 HTML，不写解释报告。 |
| `skills/read-feedback-skill` | 基于 feedback、profile、source map 生成解释报告、context pack、研究推导报告和 HTML。 | 不修改 profile。 |
| `skills/ai-quantum-news-briefing` | 生成 source-grounded AI+量子日报/多日报，生成新闻反馈 HTML，规范化新闻 feedback。 | 不根据“看过新闻”自动判断掌握状态。 |
| `skills/utils/lean-html-skill` | 负责共享 HTML shell、反馈面板、browser-memory/localStorage、copy/download 导出控件，承接后续 reader HTML 输出层复用。 | 不做领域解释，不写 profile。 |
| `skills/utils/init-knowledge-profile` | 从本地 GPT/ChatGPT 会话导出文件初始化或扩展人物/知识画像，按 `collect -> extract -> propose -> apply` 生成来源、证据事件、候选项和审阅补丁。 | 不直接抓取 share URL，不导入疑似密钥文件，不绕过补丁审阅直接覆盖 profile。 |

## 论文阅读流水线

正式 end-to-end 论文阅读器必须同时满足：

1. `paper.md` 覆盖论文的实质内容，并保留稳定 source anchor。
2. 每个实质性 `**Original:**` 块都有忠实 `**中文:**` 翻译。
3. `**注释:**` 提供逻辑结构、知识点、公式、图表或阅读提示，而不是替代翻译。
4. 严格校验通过，没有 `待忠实翻译`、`中文译意`、`非逐句精翻`、`reading scaffold` 等草稿标记。
5. 图和表必须以可检查的 figure/table card 或语义表格进入正文，不能只有 caption 文本、图片对象列表或整页截图链接。
6. 关键公式必须重构为 LaTeX display math，不能把 PDF 抽取噪声当作最终公式。
7. `**注释:**` 必须针对具体段落、公式、图表或论证功能；不能保留 `逻辑位置：本文主题是...`、`标注建议：如果这里有不懂...` 这类模板句。
8. 最终交互文件命名为 `reader_interactive.html`，并包含反馈 UI / 画像标注能力。

只有文本抽取、摘要、占位翻译或阅读脚手架的结果不是完成 pipeline，也不能生成替代性的预览 HTML；必须继续完成翻译、图表、公式和注释后再生成 `reader_interactive.html`。

默认翻译责任在 Codex：当目标是正式 `reader_interactive.html` 时，应直接逐块翻译并回写 `paper.md` / `source_map.json`。不要先寻找本地翻译模型、SDK 或第三方包；缺少 Ollama、OpenAI SDK、Argos Translate、DeepL 等工具不能作为停止翻译或只生成中间产物的理由。

### 1. 生成 reader bundle

使用 `nature-reader` 从论文生成：

```text
<paper>_reader/
|-- paper.md
|-- source_map.json
|-- translation_notes.md
`-- assets/
```

`paper.md` 的基本块必须是：

```markdown
<a id="S001"></a>
**Source:** p.1 S001

**Original:** English source paragraph.

**中文:** 对 Original 的忠实中文翻译。

**注释:** 针对本块的具体逻辑提示、知识点、公式核对、图表读法或论证功能说明。
```

注意：`中文` 栏不能写 `中文译意`、`非逐句精翻`、段落概括、知识点列表或阅读提示。

### 2. 生成交互式 HTML

在任意目录运行：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --output <reader-dir>\reader_interactive.html --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

默认会严格校验 `中文` 栏。如果 `paper.md` 仍是草稿翻译或意译提示，命令会失败，避免生成假的中英对照 HTML。

`reader_interactive.html` 只表示已经翻译好、有逻辑与知识点提示、图表/公式结构完整、可正式阅读的交互 HTML。若严格校验失败，先修 `paper.md` / `source_map.json`，不要生成草稿 HTML。

### 3. 在 HTML 中标注

在 `reader_interactive.html` 中：

1. 点击高亮概念，或选中文本后用自由标注。
2. 标记 `mastered`、`known`、`learning`、`unknown` 或 `unrated`。
3. 写下具体问题、问题类型、解释偏好和补充说明。
4. 点击 `Save mark`。
5. 读完后点击 `Download feedback JSON` 或 `Copy feedback for Codex`。

HTML 不会自动写入 `.agents`。刷新或关闭前必须导出。

### 4. 导入个人知识画像

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --feedback <reader_feedback.json>
```

画像 schema v2 分为：

- `concepts`: 稳定概念画像；
- `events`: 原始反馈历史；
- `sources`: 来源索引；
- `review_queue`: 复习队列。

### 5. 生成反馈解释报告

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py --feedback <reader_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

默认输出：

- `feedback_explanations.md`
- `feedback_research_context.md`
- `feedback_explanations.html`

真正的推导/研究报告应基于 `feedback_research_context.md` 再写 `feedback_research_deep_dive.md`，然后渲染 HTML。

## AI + 量子日报流水线

`ai-quantum-news-briefing` 用于生成当前 AI、模型、产业、监管、学术和量子方向资讯。生成日报时必须联网核实当前信息并给出具体日期范围。

如果要像读论文一样标注日报：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html>
```

导入新闻反馈：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

新闻只出现不代表会或不会。曝光型概念默认 `unrated`，只有用户明确反馈时才写入 `known`、`mastered`、`learning` 或 `unknown`。

## GPT 会话导入画像流水线

`skills/utils/init-knowledge-profile` 用于把本地 GPT/ChatGPT 会话导出文件变成可审阅的人物/知识画像补丁。推荐先把 share 链接或聊天记录保存为 `.txt`、`.md`、`.html` 或 `.json`，再导入；不要依赖自动抓取 share URL。

从项目根目录运行：

```powershell
cd C:\Users\SSS\Desktop\PAPER
```

1. 收集来源和证据事件：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions
```

2. 提取候选画像：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py extract --events C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\events.jsonl --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
```

3. 生成审阅补丁：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py propose --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --candidates C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json
```

4. 审阅 `profile_patch.json` 后再应用：

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py apply --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --patch C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

概念状态候选会通过 `reader-learner` 的 v2 导入逻辑进入 `concepts/events/review_queue`；非概念类偏好会进入 `person_profile`。

## 常用校验

```powershell
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\profile_v2.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\build_feedback_explanation_report.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\read-feedback-skill\scripts\render_research_deep_dive_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\lean-html-skill\scripts\lean_html.py
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\test_reader_e2e.py
```

## 安全规则

- 除个人画像的明确读取/导入/同步任务外，不要打开、打印、复制、总结、上传或修改任何疑似密钥、密码、令牌或凭据文件。
- 不要手动编辑 `knowledge_profile.json` 来绕过 `reader-learner`。
- 不要把整页 PDF source page 当作正文 figure 插入；正文只放可靠裁剪图或提取图。
- 不要把意译、摘要、阅读提示伪装成中英对照翻译。

## 致谢与借鉴

本项目的 reader、知识库和 agent 上下文工作流借鉴了以下开源项目和本地 skill 设计：

- [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills) 的 `nature-reader` 思路：作为论文翻译 reader 的基础参考，尤其是 source-grounded 全文阅读、图表位置保留、术语表和 Markdown bundle 输出结构。
- [greg-asher/codex-obsidian](https://github.com/greg-asher/codex-obsidian)：用于理解 Codex 与 Obsidian 桌面端/仓库之间的衔接方式，启发了 `.agents/reader-learner/obsidian-vault` 的打开、诊断和同步脚本设计。
- [ar9av/obsidian-wiki](https://github.com/ar9av/obsidian-wiki)：用于借鉴 wiki 式知识组织、MOC、知识点页面和图谱表达方式，帮助把 reader-learner 的长期画像整理成更像知识库而不是事件流水账。
- `D:\AI\skill\S_paper_skills\util_skills\research-html-report`：作为 HTML 研究报告视觉与结构参考，影响了 `read-feedback-skill` 的报告布局、公式渲染、证据矩阵和打印友好样式。
- `D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill`：用于生成和维护 `.agents` 项目上下文，帮助后续 Codex 会话快速理解项目边界、命令、数据位置和安全规则。

上述项目提供的是架构与交互设计参考；本仓库中的个人画像、反馈导入、论文 reader 生成和知识边界迭代逻辑按本地需求重新组织实现。
