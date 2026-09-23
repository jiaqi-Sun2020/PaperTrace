# Daily Briefing Interface

`allegory-teach` authors a source-grounded opening handoff or explains a
released briefing. It never owns collection, ranking, feedback, or publication.
All new daily openings use Fable Mode, `opening_story.version=3`.
Read `story-output-contract.md` and `narrative-language-firewall.md`.
Historical versions 1–4 remain readable; do not add an explanation_mode field.

## Accepted upstream context

Use only source-audited, deterministically ranked publishable items, not search
results, staging records, or story-index summaries as primary evidence.
The academic display order remains descending `ranking.base_score`.
The default source is rank 1; its `story_id` is first in `source_story_ids`.
Try one narrower relation and one repair within that item before changing source.
If no faithful, comprehensible analogy survives, inspect remaining academic
items in rank order. Record `story_delivery.selection_basis="explicit_override"`
and a concrete `override_reason`. Use a stable learner-profile concept only
when the user explicitly selects it. If no eligible source supports a valid
fable, stop publication and disclose the failed gate.
This changes neither ranking nor display order. Never trade evidence quality
for a more entertaining scene.

For later explanation, use finalized briefing/feedback context with source
title/URL, excerpt, category, and date range, or a stable concept whose sources
identify a briefing. Profile reads are limited to relevant stable facts.
Do not copy status, raw events, private notes, or profile paths into a report.

Every important analogy action must preserve the source's operation target,
direction, evidence class, and claim boundary. Stop at unresolved mechanisms.
A visualization is not evidence and may not imply extra information recovery,
perfect observation, or universal success.

## Opening-story handoff

Return this object to `ai-quantum-news-briefing`; do not publish or write
the config yourself. The existing fields carry the four reading layers:
`paragraphs` = complete narrative, `concept_definition` = bounded definition,
`concept_name` plus `logic_chain` = real concept and mapping,
`analogy_boundary` plus `misleading_risk` = boundary corrections.

```json
{
  "version": 3,
  "title": "开篇寓言",
  "paragraphs": ["...", "..."],
  "concept_name": "...",
  "concept_aliases": ["..."],
  "concept_definition": "...",
  "logic_chain": "已知锚点 → 缺失桥梁 → 机制 → 后果",
  "analogy_boundary": "...",
  "misleading_risk": "...",
  "worked_example": {
    "kind": "mathematical|numerical|operational|causal|experimental|comparative",
    "title": "...",
    "question": "...",
    "scenario": "一个具体对象、初态、条件与目标组成的本例场景",
    "inputs": [
      {"name": "...", "value": "本例实际值或状态", "role": "如何进入步骤"}
    ],
    "observable": "本例结束后具体观察、比较或计算什么",
    "assumptions": ["..."],
    "objects": [
      {"name": "...", "kind": "...", "role": "...", "units": "..."}
    ],
    "steps": [
      {"action": "...", "formula": "", "rule": "...", "explanation": "..."}
    ],
    "result": "...",
    "interpretation": "...",
    "checks": ["..."],
    "non_conclusion": "..."
  },
  "grounding_kind": "learner_profile|briefing_items",
  "source_story_ids": []
}
```


## Versioned validation and presentation

- New version-3 authoring begins with at least two causally necessary background
  paragraphs and then completes the story. No total character, sentence, or
  paragraph-count ceiling applies; suggested lengths are never pass/fail thresholds.
- Each paragraph has a 2000-normalized-character transport boundary. Split
  naturally; never truncate. Preserve all paragraphs in their input order.
- Conceal the concept and professional representation throughout the title and
  story. Reveal only in factual section 1, then return in order 1 -> 2 -> 3 -> 4.
- Keep a complete structured worked example after section 4 and before the
  briefing. HTML shows the entire story and debrief, with only the example
  inside a native details control closed by default.
- Narrative and example preserve the same bounded case and underlying data
  identity. Natural-language projection is allowed; fabricated measurements,
  mismatched conditions and phantom references are not. Read
  `worked-example-contract.md` and the shared semantic review.
- Versions 1, 2, 3 and 4 retain their runtime meaning and existing normalization,
  validation and rendering. Version 4 stays 4 and may retain one paragraph.
  Unknown or malformed versions are rejected. Do not bulk rewrite history.
- The first source ID defaults to rank 1. Source override uses the existing
  audited reason; ranking, publication, feedback identity and learner ownership
  remain unchanged. Schema success never certifies semantic correctness.

## Post-release explanation handoff

For a story-only repair, keep ranking, item identity, feedback and index records
unchanged. Reproduce the existing staged release using its original lookback
and design settings; compare non-story config fields before publication.
Never rerank against today's index and assume historical output stays identical.

Keep authored review evidence outside the opening-story schema. Record the
current story/example digest and three rounds: story-completeness,
semantic-and-source, cross-surface-and-display. Each records reviewed text,
judgment, reason, source_or_rule and limitation. Re-author the judgment after an
edit, not just its hash. The validator checks provenance, not truth.

From `D:\AI\PaperTrace`, reproduce the review and structural audit with:

```powershell
python skills/allegory-teach/scripts/audit_daily_story.py --run-dir news/YYYY-MM-DD --review news/YYYY-MM-DD/opening_story_review_YYYY-MM-DD.json --output news/YYYY-MM-DD/adversarial_audit_YYYY-MM-DD.json
```

Missing, stale or unsupported review records cannot certify a release as
teaching-approved, even when the structural pipeline passes.

The optional in-chat handoff is:

```json
{
  "interface": "allegory-teach-news-context-v1",
  "source_kind": "news_briefing",
  "briefing_title": "...",
  "date_range": "YYYY-MM-DD",
  "concept": "...",
  "concept_status": "unrated|unknown|learning|known|mastered",
  "source_refs": [
    {"title": "...", "url": "https://...", "category": "..."}
  ],
  "profile_mutation": false
}
```

`concept_status` is copied only from explicit user feedback or the existing
profile. A new briefing concept remains `unrated`; neither inclusion in the
story nor reader engagement changes that status.

## Downstream boundary

If the reader responds with an actual explanation, solution, or transfer
attempt, preserve it as user-provided evidence and hand it to
`adaptive-teach` / `reader-learner` through their validated teaching-feedback
workflow. An opening story is never learner evidence and its concept does not
enter automatic news feedback unless the same concept independently belongs to
a configured news item. Do not write `news_feedback.json`, alter the daily
manifest, or directly modify `knowledge_profile.json`.
