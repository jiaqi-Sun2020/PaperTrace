# News HTML Feedback

Use this reference when turning an AI+quantum briefing into an interactive HTML reader.

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
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
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
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\briefing_to_feedback_html.py --config <news_feedback_config.json> --output <briefing_reader.html> --feedback-output <news_feedback.json> --default-status unrated
```

Use `config_to_news_feedback.py` only when generating JSON without HTML:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py --config <news_feedback_config.json> --output <news_feedback.json> --status unrated
```

Import exported feedback:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile C:\Users\SSS\Desktop\PAPER\.agents\reader-learner\knowledge_profile.json
```

## Delta-First Daily Briefings

For recurring daily reports, avoid comparing against whole old Markdown files. Use the compact story index:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py context --index C:\Users\SSS\Desktop\PAPER\news\_index\story_index.jsonl --date <YYYY-MM-DD> --days 7
```

After creating a source-grounded candidate config, rewrite it into delta-first sections:

```powershell
python C:\Users\SSS\Desktop\PAPER\skills\ai-quantum-news-briefing\scripts\news_delta.py apply --config <candidate_config.json> --output <delta_config.json> --date <YYYY-MM-DD> --days 7 --continuing-mode one-line --update-index
```

Only `new` and `material_update` items should be fully expanded. Recently seen stories without new facts should be compressed into `持续跟踪，一句话` or skipped with `--continuing-mode skip`.

## Boundary

- Full-concept HTML export is automatic from `news_feedback_config.json`: `Download JSON` must include all default concepts plus user edits.
- `--no-auto-feedback` disables only the sidecar file write; the HTML should still embed the initial full-concept feedback set.
- HTML `Save mark` is for corrections, questions, status changes, and free-form annotations, not for enrolling every default concept one by one.
- Daily/news exposure-only concepts should default to `unrated`.
- Literature/paper reader concepts remain `unrated`; do not reuse the news default for paper HTML.
- Do not infer `unknown` unless the user marks it or asks a question.
- Keep source title, URL, category, and excerpt so `.agents` can distinguish news-derived concepts from paper-reading feedback.
