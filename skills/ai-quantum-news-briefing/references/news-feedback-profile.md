# News Feedback Profile Bridge

Use this reference when connecting AI + quantum daily briefings to `.agents/reader-learner/knowledge_profile.json`.

## Principle

Daily news should not automatically decide what the user knows. Update the profile only when:

- the user explicitly marks a concept as `known`, `learning`, `unknown`, `mastered`, or `unrated`;
- the user asks to record briefing keywords as exposure-only daily/news items, in which case use `unrated`;
- the user asks a follow-up question about a news concept.

Do not mark a concept `unknown` merely because it appeared in a briefing.
Daily/news exposure defaults to `unrated`; literature/paper reader exposure also remains `unrated` in reader-skill.

## Native News Feedback JSON

Create a JSON file shaped like:

```json
{
  "news_feedback_version": 1,
  "briefing_title": "AI + Quantum News Briefing - 2026-07-04",
  "date_range": "2026-07-04",
  "briefing_path": "C:\\Users\\SSS\\Desktop\\PaperTrace\\news\\2026-07-04.md",
  "items": [
    {
      "concept": "quantum error correction",
      "translation": "量子纠错",
      "status": "unknown",
      "category": "quantum computing",
      "source_title": "Short source title",
      "source_url": "https://example.com/source",
      "source_excerpt": "One or two sentences of context from the briefing.",
      "user_question": "Why is decoding the bottleneck?",
      "confusion_type": "term_definition",
      "explanation_style": "first_principles",
      "needs_explanation": true
    }
  ]
}
```

Status values match `reader-learner`:

- `mastered`
- `known`
- `learning`
- `unknown`
- `unrated`

Question types may reuse reader feedback categories:

- `term_definition`
- `paper_usage`
- `math_step`
- `algorithm_step`
- `assumption`
- `evidence`
- `relation`
- `other`

## Import Command

When a briefing config already contains `concepts`, create full feedback automatically:

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\config_to_news_feedback.py --config <news_feedback_config.json> --output <news_feedback.json> --status unrated
```

```powershell
python D:\AI\PaperTrace\skills\ai-quantum-news-briefing\scripts\import_news_feedback.py --feedback <news_feedback.json> --profile D:\AI\PaperTrace\.agents\reader-learner\knowledge_profile.json
```

The script writes a normalized `*_reader_feedback.json` file next to the news feedback and delegates the actual profile mutation to:

```text
skills/reader-learner/scripts/import_reader_feedback.py
```

The normalized handoff supplies strict `concept_id`, `concept_type`, and `source_anchor` fields while keeping `source_kind: news_briefing`. News feedback is not a paper reader bundle, so it must not fabricate reader-bundle provenance.

For the profile-plus-visible-Wiki path, run from `D:\AI\PaperTrace`:

```powershell
python .\skills\reader-learner\scripts\feedback_visible_wiki_pipeline.py news-feedback --feedback <news_feedback.json>
```

Use `--no-import` when you only want to inspect the normalized handoff JSON.

## What Gets Stored

The profile entry receives:

- concept status;
- user question and note;
- source title/URL/category in evidence;
- source excerpt as context;
- `action: news_feedback`;
- `source_kind: news_briefing`.

This keeps news-derived knowledge separate from paper-reading feedback while using the same learner profile.
