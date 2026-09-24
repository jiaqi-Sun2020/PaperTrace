# Feedback2 Contract

Use this reference when an HTML report needs a second feedback pass.

## Model

The page automatically commits explicit status choices and edited feedback fields to browser-local state. Text/select changes use a roughly 250 ms debounce; status changes and page-hide/unload flush immediately. Merely opening Feedback or selecting then dismissing text creates no record. This is a same-browser recovery copy, not a durable or portable export. The page must still export JSON manually and must not write `.agents` directly.

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

## Interaction Rules

- Selecting article text opens a contextual status toolbar. A status click creates or updates the mark immediately; `提问 / 备注` opens the non-modal detail editor.
- Clearing or collapsing the selection, moving it outside the annotatable root, or clicking outside that root closes the toolbar and clears the cached selection. A pointer or keyboard interaction inside the toolbar temporarily protects the captured selection so focus-induced selection loss cannot apply an action to the wrong text.
- The editor must not cover the readable article on desktop. Reader Contents and Feedback share the right utility pane; narrow screens use a bounded bottom drawer.
- All explicit field changes auto-save with visible `saving`, `saved`, or `failed` state. Storage failure leaves in-memory export available and tells the user to export JSON.
- Status changes and deletion offer a five-second undo. The default list shows user-changed items, while export retains required baseline `unrated` records.

## Import Rules

- For `news_feedback2.json`, import with `skills/ai-quantum-news-briefing/scripts/import_news_feedback.py`.
- For `reader_feedback2.json`, import with `skills/reader-learner/scripts/import_reader_feedback.py`.
- Do not infer knowledge from a rendered report item alone; only explicit auto-saved user actions are imported.
