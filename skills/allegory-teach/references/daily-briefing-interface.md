# Daily Briefing Interface

`allegory-teach` has two read-only relationships with an AI + quantum briefing:
it may author the opening-story handoff after deterministic ranking and source
audit, or explain a concept from an already published briefing. It never owns
collection, ranking, feedback, or publication.

Daily opening stories always use Fable Mode because this product contract asks
for a concealed-name narrative before the briefing. The routing decision is not
serialized into the handoff: keep `opening_story.version=3`, the existing
`1 -> 3 -> 4 -> 2` factual return, and the current worked-example schema. Do not
add an `explanation_mode` field. Bridge Mode remains the default only for
ordinary direct teaching outside this opening-story contract.

## Accepted upstream context

For an opening story before publication, use only a deterministically ranked
selection whose underlying items already passed the news evidence gate. Do not
use unranked candidates, search-result pages, a staging directory, or a compact
story-index summary as primary evidence. If the story instead comes from the
learner boundary, read only the stable concept facts needed to choose it; do not
copy status, raw events, private notes, or profile paths into the report.

The academic section is displayed by descending `ranking.base_score`, the
pipeline's evidence-backed impact/importance proxy. The default story source is
the rank-1 academic item, and its `story_id` must be the first entry in
`source_story_ids`. Use a different briefing item or learner-profile concept
only when `story_delivery.selection_basis="explicit_override"` and
`story_delivery.override_reason` states the concrete reason. The override is an
exception, not an alternative default.

For a later explanation, use one of the following only after its source
pipeline has passed its release gate:

1. a finalized `news_feedback.json` exported by the briefing reader;
2. a finalized news-feedback config or briefing item with title, category,
   source title/URL, source excerpt, and concept list; or
3. a stable profile concept whose `sources` record identifies a news briefing.

Retain item title, category, source title/URL, and date range as provenance for
the factual debrief.

## Opening-story handoff

Return this object to `ai-quantum-news-briefing`; do not write the config or
published files directly:

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

Use 2-6 narrative paragraphs totaling at least 120 characters. The title and
paragraphs must not contain the canonical concept name or its aliases. When
`grounding_kind` is `briefing_items`, reference at least one `story_id` that
survives into the published selection. Under the default daily selection policy,
the first ID is the rank-1 academic item. The pipeline renders the story first,
then its compact factual debrief, then a collapsed worked example, then
`日报正文`.

The worked example is required for a new daily run, but its form follows the
concept. Do not prefer mathematical concepts during selection. Use `formula`
only when the selected concept and evidence genuinely require mathematics; a
complete operational, causal, experimental, or comparative example may contain
no formula. Every kind still requires a bounded `scenario`, named `inputs`, and
an `observable`; a generic explanation of the logic chain is rejected. When
any formula is present, define its objects, expose every
meaningful transition, and include a check that can reveal an invalid
derivation. Read [worked-example-contract.md](worked-example-contract.md) for
the full contract and mathematical branch example.

## Post-release explanation handoff

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
