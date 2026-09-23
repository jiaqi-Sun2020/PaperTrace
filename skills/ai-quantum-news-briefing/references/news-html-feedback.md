# News HTML Feedback

Use this reference when turning an AI+quantum briefing into an interactive HTML reader.

## Encoding Contract

All config, Markdown, JSON, and HTML artifacts use UTF-8. Read JSON/config with `utf-8-sig` and write UTF-8 with `ensure_ascii=False`; preserve `<meta charset="utf-8">` in the reader. Do not pass Chinese content through a legacy console code page when constructing a config.

The pipeline rejects `U+FFFD` and high-density literal `?` in human-readable input. A literal `?` in a URL query string is valid; a run of `?` replacing Chinese is not. Because replacement is irreversible, regenerate the source-grounded config instead of stripping the characters.

Historical story-index summaries are untrusted. Delta compaction must omit a corrupt prior summary and record that it was omitted, so old mojibake cannot enter the new reader.

Final HTML acceptance checks include UTF-8 metadata, a successful round trip, zero visible replacement characters/corruption-pattern question marks, Chinese UI markers such as `事实`/`判断`/`来源`, and concept-chip/feedback identity equality.

## Purpose

The HTML page begins with one complete Fable (version 3 for new authoring) and then presents
the briefing body. The story is not a feedback item. The page remains the
feedback collection layer and should not write `.agents` directly. It lets the
user:

- click news concepts;
- select arbitrary text and create a free-form annotation;
- mark status as `mastered`, `known`, `learning`, `unknown`, or `unrated`;
- add an exact question, note, question type, and preferred explanation style;
- open with every configured concept already present as a saved `unrated` feedback item;
- optionally click news concepts or select arbitrary text to add extra manual annotations;
- download or copy the full feedback set from the HTML after user edits.

Then run:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
```

## Config Shape

Build HTML from a config file:

```json
{
  "news_feedback_version": 1,
  "briefing_title": "AI + Quantum News Briefing - 2026-07-04",
  "date_range": "2026-07-04",
  "summary": "One-sentence summary.",
  "story_delivery": {
    "required": true,
    "worked_example_required": true,
    "position": "before_briefing",
    "selection_basis": "highest_impact_academic",
    "override_reason": ""
  },
  "opening_story": {
    "version": 4,
    "title": "先用一个生活中的例子理解",
    "paragraphs": [
      "两个人从同一条线并排走。脚步很接近时，刚走一小段还看不出谁快；继续观察，前后的差距才慢慢显出来。",
      "如果两人的速度始终不变，而且你要看到同样明显的间距才下判断，那么速度差越小，就越需要多等一会儿。"
    ],
    "concept_name": "Canonical concept name",
    "concept_aliases": ["standard acronym"],
    "concept_definition": "一句有适用范围的机制定义。",
    "logic_chain": "已知锚点 → 缺失桥梁 → 机制 → 后果",
    "analogy_boundary": "类比没有覆盖的条件或尺度。",
    "misleading_risk": "按字面理解会得到的错误推论及修正。",
    "worked_example": {
      "kind": "operational",
      "title": "完整例子",
      "question": "这个例子要回答什么？",
      "scenario": "一个带有明确对象、初态、条件和目标的具体实例。",
      "inputs": [
        {"name": "本例输入", "value": "实际数值、标签、状态或条件", "role": "如何进入后续步骤"}
      ],
      "observable": "步骤结束后具体观察、比较或计算什么。",
      "assumptions": ["适用条件或约束。"],
      "objects": [
        {"name": "对象", "kind": "现实角色或数学类型", "role": "在机制中的作用", "units": ""}
      ],
      "steps": [
        {"action": "操作或状态变化。", "formula": "", "rule": "使用的规则。", "explanation": "为什么得到下一状态。"}
      ],
      "result": "例子的直接结果。",
      "interpretation": "结果的现实、物理或操作含义。",
      "checks": ["改变一个条件，检查结果是否按机制变化。"],
      "non_conclusion": "这个例子不能支持的更强结论。"
    },
    "grounding_kind": "briefing_items",
    "source_story_ids": ["rank-1-academic-story-id"]
  },
  "sections": [
    {
      "title": "Top Signals",
      "items": [
        {
          "id": "N001",
          "title": "Short item title",
          "category": "AI policy",
          "facts": "Source-grounded fact.",
          "judgment": "Separated interpretation.",
          "relevance": "Optional relevance to QWTA/CTQW/AI for Quantum.",
          "evidence_level": "official report|media report|paper|community",
          "source_title": "Source title",
          "source_url": "https://example.com",
          "source_excerpt": "Brief grounding context.",
          "story_id": "stable-story-id",
          "novelty": "new|material_update|continuing|duplicate",
          "delta_note": "Short explanation of why this item is expanded, compressed, or repeated.",
          "concepts": ["concept A", "concept B"]
        }
      ]
    }
  ]
}
```

## Commands

The HTML generator embeds the full-concept feedback set in the page and writes the same JSON sidecar by default. The page opens with every configured concept already present with default `unrated` status, so the user does not need to click each chip before using `Download JSON`:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --feedback-output <news_feedback.json> --default-status unrated
```

Use `config_to_news_feedback.py` only when generating JSON without HTML:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py --config <news_feedback_config.json> --output <news_feedback.json> --status unrated
```

Import exported feedback:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
```

## Delta-First Daily Briefings

For recurring daily reports, avoid comparing against whole old Markdown files. Use the compact story index:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index D:\AI\PaperTrace\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
```

After creating a source-grounded candidate config, rewrite it into delta-first sections:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\news_delta.py apply --config <candidate_config.json> --output <delta_config.json> --date <YYYY-MM-DD> --days 7 --continuing-mode one-line
```

Only `new` and evidence-backed `material_update` items should be fully expanded. Recently seen stories without verified new facts should be compressed into `持续跟踪，一句话` or skipped with `--continuing-mode skip`. Index update is deferred to `daily_pipeline.py finalize`.

## Versioned opening presentation

For new daily authoring, follow `skills/allegory-teach/references/daily-briefing-interface.md`.
Version 4 renders scene -> one-sentence core -> real mapping -> boundaries ->
complete worked example. It has no total length/count budget and no required
two-paragraph background; existing field transport limits fail without clipping.
Scene and example share a relation, not necessarily a setting or numbers.
Explicit full fables/legacy versions keep their old presentation. Unknown
versions fail. The JSON above illustrates fields, not a publishable evidence fixture.

## Boundary

- `daily_pipeline.py run` requires exactly one valid opening story and one complete worked example, then renders both before `日报正文` in Markdown and HTML. HTML uses a native `details` control closed by default for the example.
- The HTML story/example subtree must bind its narrative, debrief, steps, formula, warning, and object/role table to the shared semantic story surfaces. Light, Cosmic, and print palettes must pass the shared `4.5:1` normal-text contrast audit; fixed light story surfaces are publication failures.
- The story's concept name and aliases must not appear in its title or narrative paragraphs; the visible debrief performs the reveal.
- Select the concept independently of whether it has equations. Use a mathematical derivation only when the mechanism genuinely requires one; otherwise use a complete numerical, operational, causal, experimental, or comparative example without fabricated formulas.
- `grounding_kind=briefing_items` requires `source_story_ids` that survive ranking and appear in the published delta config. `learner_profile` must not copy private profile evidence or status into the report.
- Opening-story concepts are excluded from automatic feedback unless they independently occur in a news item's configured `concepts` list.
- Full-concept HTML export is automatic from `news_feedback_config.json`: `Download JSON` must include all default concepts plus user edits.
- The canonical config is section-based. Derive the browser item lookup table from `sections`; never require a legacy top-level `items` field.
- On load, every automatic concept is already in browser state as `unrated`. `Save mark` edits that baseline and deleting an automatic concept restores its baseline. Only a freeform annotation may be removed entirely.
- `--no-auto-feedback` disables only the sidecar file write; the HTML should still embed the initial full-concept feedback set.
- HTML `Save mark` is for corrections, questions, status changes, and free-form annotations, not for enrolling every default concept one by one.
- Daily/news exposure-only concepts should default to `unrated`.
- Literature/paper reader concepts remain `unrated`; do not reuse the news default for paper HTML.
- Do not infer `unknown` unless the user marks it or asks a question.
- Keep source title, URL, category, and excerpt so `.agents` can distinguish news-derived concepts from paper-reading feedback.
