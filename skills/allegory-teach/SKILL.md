---
name: allegory-teach
description: Teach one advanced, profile-relevant technical concept through a Chinese fable that withholds the concept name until the end, then maps the analogy back to facts and works one complete example. Use when the user asks for an allegory, intuition-first explanation, or a story selected from their PaperTrace learning boundary; do not use it to mutate learner knowledge or to create a daily briefing.
---

# Allegory Teach

Turn one concept into a memorable causal model without letting the story replace
the underlying technical claim. This is a narrative explanation layer around
Pipeline 4, not a new learner-memory owner or teaching-decision system.

## Select the subject

When the user asks for their personal knowledge boundary, read only the
schema-v2 profile facts needed to choose a subject. Reuse an existing
`adaptive-teach` selection when it is available. Otherwise, select one stable
concept that is source-backed and relevant to the user's active domain. This
is a one-off explanation subject, not a teaching priority, review proposal, or
replacement for an `adaptive-teach` decision:

- prefer an explicit `unknown` or `learning` gap, a due review with a difficult
  facet, or a concept whose prerequisite relation explains an active gap;
- treat `unrated` news or reader exposure as an exploration candidate, never as
  a diagnosed weakness;
- choose a concept whose mechanism has enough causal structure to merit a
  near-doctoral explanation, rather than choosing an obscure label for its own
  sake;
- do not prefer a concept merely because it admits a formula. Select for
  relevance, causal value, source support, and the learner's missing bridge;
- keep a user-specified domain, paper, or news item as the authority when one
  is supplied.

If the profile and supplied evidence do not identify a defensible domain or
concept, ask for the active domain instead of inventing a personal gap. Do not
read raw events, private teaching sessions, or unrelated source files merely to
make the story richer.

## Build the fable from first principles

Before drafting, locate the learner's bridge and privately reduce the target to
one causal spine:

```text
known anchor -> missing bridge -> target mechanism -> consequence or application
initial state -> rule or constraint -> local action -> consequence ->
observable trade-off or failure mode
```

Use a concept already known by the learner only as an anchor; do not pretend it
proves mastery. Every causal transition in the fable must follow from a visible
rule, constraint, or action. Do not hide a logical jump behind story language.

Use the fewest characters, rules, and events that preserve that spine. Each
important story element must have one intended technical counterpart. Do not
smuggle in a second advanced concept just to make the fable dramatic.

The story must:

- open without the concept name, its standard acronym, or an identifying
  formula;
- make the governing rule and the cost of violating or exploiting it visible
  through character choices and consequences;
- let the reader infer the mechanism before the reveal, which may occur only in
  the final paragraph or immediately after the story;
- remain a story, not a disguised lecture. Keep technical terms out until the
  requested factual return.

Read [references/story-output-contract.md](references/story-output-contract.md)
before writing the response.

For the post-story explanation, read
[references/logic-chain-explanation.md](references/logic-chain-explanation.md).
Use its smallest applicable analysis pattern; preserve a strict fable request's
required `1 -> 3 -> 4 -> 2` section order.

Read [references/worked-example-contract.md](references/worked-example-contract.md)
before constructing the required example. Match the example to the concept:
mathematical, numerical, operational, causal, experimental, or comparative.
Only use formulas when the concept and evidence genuinely require them. When a
formula is used, expose every meaningful transition and never invent a formula
to satisfy an output shape.

## Return from intuition to fact

After the story, use the four factual sections in the user's requested order:
`1 -> 3 -> 4 -> 2`. The mapping is mandatory even when the reader guesses the
concept. State what the analogy omits and how it could lead to a wrong technical
inference. In the mapping, expose the technical causal chain, the relevant
object/operation distinction, and any information that is preserved, changed,
or discarded. Complete section 2 with one worked example whose form follows the
concept rather than forcing every concept into a derivation. Do not claim that
understanding the story or example demonstrates mastery.

When the user requests an interactive explanation rather than the strict fable
format, end with one small prediction, comparison, or paraphrase check. Do not
append a fifth section to a strict story-output contract.

## Daily briefing interface

When authoring the required opening story for an AI + quantum briefing, or when
the subject comes from an already published briefing, read
[references/daily-briefing-interface.md](references/daily-briefing-interface.md)
before using it. For pre-publication authoring, consume only the source-audited,
deterministically ranked selection; for later explanation, consume finalized,
source-grounded briefing context or a user-provided feedback export. Return the
opening-story handoff to the briefing pipeline, which alone validates, renders,
and publishes it. This skill does not collect news, alter ranking, write a
feedback file, or promote exposure into a learner status.

## Ownership and completion

- `adaptive-teach` owns persistent teaching decisions, sessions, review
  proposals, and teaching-feedback construction.
- `reader-learner` is the sole profile mutator and Visible Wiki projector.
- `ai-quantum-news-briefing` owns news evidence, ranking, release, and
  news-feedback normalization.
- This skill owns only the final narrative explanation, its explicit factual
  debrief, and the concept-appropriate worked example.

Finish by reporting the story and four factual sections, including the worked
example inside section 2. If the user later supplies actual answers or an
application attempt, route that evidence through the existing `adaptive-teach`
/ `reader-learner` feedback path rather than writing the profile directly.
