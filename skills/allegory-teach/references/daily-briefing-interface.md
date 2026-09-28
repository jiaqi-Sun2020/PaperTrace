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

Apply the source-context binding check in `story-output-contract.md` before
handoff. Restore the real problem and relevant source constraints in the existing
`logic_chain`, alongside the action mapping; keep `concept_definition` a bounded
definition. The current renderer places the definition in section 1 and the
logic chain in section 2: use those fields without adding a background field,
changing schema, or hiding necessary context in the collapsed example. Do not
claim that authoring or structural validation demonstrates improved retention.
For new fields, leave off `1.` through `4.` prefixes: the HTML renderer adds
the headings. Keep the actual research task and story-action mapping in
`logic_chain`, not in `analogy_boundary`; the latter only states omitted scope.

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

For a newly authored review, use sidecar `review_protocol_version=3`,
`review_method="self"` or `"independent"`, and a private `task_card` with
`teaching_question`, `source_task_and_constraint`, `learner_bridge`,
`actor_goal_and_success`, `shortcut_and_limit`, `decisive_rule_and_action`, and
`counterfactual_and_boundary`. Do not put this card in `opening_story` or the
published teaching prose. Existing review sidecars remain valid without these
fields; their provenance check must not be relabelled semantic certification.
New staging manifests declare `required_story_review_protocol=3`. This is a
review-only requirement: `opening_story.version=3` and its fields do not change.
Historical v2 reviews remain locally readable. A historical release needs a
fresh v3 review before a first remote upload or correction; re-seal an existing
completed release only after deliberately preserving its old review sidecar.

Review in this order, recording `materials_seen` for each new round:

1. `story-completeness`: see only `title` and `paragraphs`, not the task card,
   author mapping, factual return or worked example. Quote the sentence that
   supplies the goal, success condition, reason for action and counterfactual;
   report any link that cannot be recovered from the story alone. In v3, record
   `literal_trace` for every decisive action. Each entry has an exact
   `story_quote`, `tracked_object`, `kind` (`physical_quantity`,
   `representation_label`, `control_event`, `knowledge_state`, or
   `other_state`), `before`, `trigger`, `operation`, `after`, and in-world
   `rule_origin`. A separate `counterfactual` records `changed_condition`,
   `predicted_result`, and `reason`. A missing event-to-update rule or a
   quantity/label switch remains in `unresolved`, never a pass.
2. `semantic-and-source`: see the full factual return and original source.
   Check task identity, object and operation types, rule origin, theorem versus
   application, alternatives and claim strength. Use primary source anchors.
   In v3, `technical_edges` maps each first-round `story_quote` exactly once to
   `technical_operation`, `source_anchor`, `claim_class` (`source_fact`,
   `derivation`, or `teaching_assumption`), and `scope_and_nonconclusion`.
   For a teaching assumption, `source_anchor` identifies the explicitly
   declared example assumption, not a fabricated paper citation.
   Capacity does not license a specific overflow policy; a necessary bound
   does not establish attainability; an observation does not uniquely prove
   a cause. Mark unsupported edges unresolved.
3. `cross-surface-and-display`: compare the revised story, debrief, worked
   example and rendered HTML. Check field responsibility, question/observable/
   steps/result, same-case quantities, visible order and collapsed example.
   In v3, `example_alignment` quotes the example's exact `question`,
   `observable`, one decisive `step_quote`, and `result`, then explains their
   relation in `consistency_reason`. If the steps do not actually compute or
   observe the promised quantity, leave the finding unresolved.

Each v3 round has an `unresolved` list; it must be empty for `judgment=pass`.
The validator checks field presence, exact story/example quotes, mapping
coverage and digest freshness. It cannot determine whether the typed objects,
source attribution or pedagogical explanation are true. Keep that semantic
judgment explicit and separate from structural validation.

An independent review requires a genuinely separate review pass with its input
and output retained; otherwise label the record `self`. The code can validate
declared materials, quotes and freshness, not whether a human learned or a
causal judgment is scientifically correct. Report these outcomes separately.

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
