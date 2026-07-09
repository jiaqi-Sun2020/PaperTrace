# Feedback2 Contract

Use this reference when an HTML report needs a second feedback pass.

## Model

The page stores marks in browser memory/localStorage and exports JSON manually. It must not write `.agents` directly.

News report export:

```json
{
  "news_feedback_version": 2,
  "briefing_title": "...",
  "date_range": "...",
  "briefing_path": "...",
  "source_feedback_path": "...",
  "generated_from": "lean-html-skill",
  "items": []
}
```

Reader/paper report export:

```json
{
  "reader_feedback_version": 2,
  "paper_title": "...",
  "reader_path": "...",
  "source_feedback_path": "...",
  "generated_from": "lean-html-skill",
  "items": []
}
```

Each item should preserve:

- `concept`
- `status`
- `user_question`
- `note`
- `confusion_type`
- `explanation_style`
- `selected_text`
- `selected_language`
- `source_excerpt`
- `source_title`
- `source_url`
- `category`
- `block_id`
- `annotation_kind`
- `report_anchor`

## Status Rules

- Default form status is domain-aware: `known` for news/daily report feedback, `unrated` for reader/paper feedback.
- Explicit user choices always override the domain default.
- Export status must be exactly one of `mastered`, `known`, `learning`, `unknown`, or `unrated`.
- `needs_explanation` should be true for `unknown`, `learning`, or any item with a user question.

## Import Rules

- For `news_feedback2.json`, import with `skills/ai-quantum-news-briefing/scripts/import_news_feedback.py`.
- For `reader_feedback2.json`, import with `skills/reader-learner/scripts/import_reader_feedback.py`.
- Do not infer knowledge from a rendered report item alone; only saved marks are imported.
