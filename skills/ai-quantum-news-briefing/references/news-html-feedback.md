# News HTML Feedback

Use this reference when turning an AI+quantum briefing into an interactive HTML reader.

## Encoding Contract

All config, Markdown, JSON, and HTML artifacts use UTF-8. Read JSON/config with `utf-8-sig` and write UTF-8 with `ensure_ascii=False`; preserve `<meta charset="utf-8">` in the reader. Do not pass Chinese content through a legacy console code page when constructing a config.

The pipeline rejects `U+FFFD` and high-density literal `?` in human-readable input. A literal `?` in a URL query string is valid; a run of `?` replacing Chinese is not. Because replacement is irreversible, regenerate the source-grounded config instead of stripping the characters.

Historical story-index summaries are untrusted. Delta compaction must omit a corrupt prior summary and record that it was omitted, so old mojibake cannot enter the new reader.

Final HTML acceptance checks include UTF-8 metadata, a successful round trip, zero visible replacement characters/corruption-pattern question marks, Chinese UI markers such as `事实`/`判断`/`来源`, and concept-chip/feedback identity equality.

## Purpose

The HTML page is the feedback collection layer. It should not write `.agents` directly. It lets the user:

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

## Boundary

- Full-concept HTML export is automatic from `news_feedback_config.json`: `Download JSON` must include all default concepts plus user edits.
- The canonical config is section-based. Derive the browser item lookup table from `sections`; never require a legacy top-level `items` field.
- On load, every automatic concept is already in browser state as `unrated`. `Save mark` edits that baseline and deleting an automatic concept restores its baseline. Only a freeform annotation may be removed entirely.
- `--no-auto-feedback` disables only the sidecar file write; the HTML should still embed the initial full-concept feedback set.
- HTML `Save mark` is for corrections, questions, status changes, and free-form annotations, not for enrolling every default concept one by one.
- Daily/news exposure-only concepts should default to `unrated`.
- Literature/paper reader concepts remain `unrated`; do not reuse the news default for paper HTML.
- Do not infer `unknown` unless the user marks it or asks a question.
- Keep source title, URL, category, and excerpt so `.agents` can distinguish news-derived concepts from paper-reading feedback.
