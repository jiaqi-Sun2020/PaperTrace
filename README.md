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
|       |-- init-knowledge-profile/
|       `-- lean-html-skill/
|-- .agents/                      # 项目 agent 上下文和长期学习画像
`-- README.md
```

## Skill Boundaries

| Skill | 负责 | 不负责 |
|---|---|---|
| `skills/nature-reader` | 从 PDF/HTML/DOI/arXiv/文本生成 `paper.md`、`source_map.json`、`translation_notes.md` 和 `assets/`。 | 不更新长期画像，不把摘要冒充翻译。 |
| `skills/reader-skill` | 把 reader bundle 转成正式 `reader_interactive.html`，负责双语块、source anchors、概念标注、公式和图表结构。 | 不写 `.agents`，不直接修改画像。 |
| `skills/reader-learner` | 导入 reader/news feedback，维护 `.agents/reader-learner/knowledge_profile.json`，导出 Obsidian vault，审计知识库。 | 不生成论文 HTML，不写解释报告。 |
| `skills/read-feedback-skill` | 基于 feedback、profile、source map 生成解释报告、context pack、研究推导和 HTML。 | 不修改 profile。 |
| `skills/ai-quantum-news-briefing` | 生成 source-grounded AI + 量子日报/多日报告，接入 AI HOT 候选池，生成日报反馈 HTML/JSON，导入新闻反馈。 | 不因为新闻“出现过”就自动判定用户已经掌握。 |
| `skills/utils/lean-html-skill` | 共享 HTML shell、反馈面板、copy/download 导出控件、Cosmic Sci-Fi 视觉层和背景切换控件。 | 不做领域解释，不写 profile，不改变业务数据结构。 |
| `skills/utils/init-knowledge-profile` | 从本地 GPT/ChatGPT 导出记录初始化或扩展画像，按 `collect -> extract -> propose -> apply` 生成可审计补丁。 | 不绕过补丁审核直接覆盖 profile。 |

## Paper Reader Pipeline

生成 reader HTML：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py <reader-dir> --output <reader-dir>\reader_interactive.html --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

该命令会先写入并校验 `reader_wiki/`：

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

如果校验失败，不应写出或报告 `reader_interactive.html`。正式 reader 需要包含 30-60 个概念候选、LaTeX/MathJax 公式、清晰的 Original / Chinese / Notes 块、图表/算法卡片、完整 knowledge-mark metadata，以及保存后可关闭的反馈面板。

对抗性 HTML 审核：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\adversarial_html_audit.py <reader-dir>
```

## News Briefing Pipeline

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
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
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

## Knowledge Profile

`knowledge_profile.json` 是长期学习数据，只能通过导入/更新脚本修改。不要手动编辑该文件来绕过校验。

导入 reader feedback：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-learner\scripts\import_reader_feedback.py --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --feedback <reader_feedback.json>
```

从本地 GPT/ChatGPT 导出记录生成画像补丁：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py collect --input <chat_export_or_folder> --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py extract --events C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\events.jsonl --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py propose --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --candidates C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_candidates.json --output C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json
python C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py apply --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json --patch C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\imports\chat_sessions\profile_patch.json --backup
```

## Validation

常用静态校验：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\reader-skill\scripts\markdown_reader_to_html.py
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
python -m py_compile C:\Users\SSS\Desktop\PAPER\skills\utils\init-knowledge-profile\scripts\init_knowledge_profile.py
```

Reader end-to-end 测试：

```powershell
cd C:\Users\SSS\Desktop\PAPER
python C:\Users\SSS\Desktop\PAPER\skills\reader-skill\tests\test_reader_e2e.py
```

## Safety Rules

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
- `D:\AI\skill\S_paper_skills\util_skills\research-html-report`：作为 HTML 研究报告视觉与结构参考，影响 `read-feedback-skill` 的报告布局、公式渲染、证据矩阵和打印友好样式。
- `D:\AI\skill\S_paper_skills\util_skills\project-agent-generator-skill`：用于生成和维护 `.agents` 项目上下文，帮助后续 Codex 会话快速理解项目边界、命令、数据位置和安全规则。

上述来源提供的是架构、交互、候选池和设计参考；本仓库中的个人画像、反馈导入、论文 reader 生成、日报学术检索策略和知识边界迭代逻辑均按本地需求重新组织实现。
