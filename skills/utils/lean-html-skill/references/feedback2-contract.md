# Feedback2 Contract

Use this reference when an HTML report needs a second feedback pass.

## Model

The page may automatically keep saved marks and an unfinished form draft in browser `localStorage` so an accidental refresh or tab closure can be recovered. This is a same-browser recovery copy, not a durable or portable export. The page must still export JSON manually and must not write `.agents` directly.

For paper readers, namespace the internal recovery envelope as
`paper.reader.feedback-draft.v1:<source-map-sha256>`. The envelope is not part
of the feedback-v2 export schema and must never use an absolute filesystem path
as its key. Storage failure must be visible, while JSON download/copy remains
available. Only a successful download or clipboard write may offer to clear
the local recovery copy.

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
