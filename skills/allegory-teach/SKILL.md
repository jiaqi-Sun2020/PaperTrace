---
name: allegory-teach
description: Explain one complex, abstract, professional, or difficult concept so a first-time learner can follow its causal logic. Default to a bridge-first technical explanation with a minimum concrete case and a local mapped analogy; use a concealed-name Chinese fable only when explicitly requested or for a daily-briefing opening story. Do not use it to mutate learner knowledge or publish a daily briefing.
---

# Allegory Teach

Turn one concept into a low-friction causal model without letting an analogy
replace the underlying technical claim. The first success criterion is that a
reader meeting the topic for the first time can reconstruct what happens and
why; literary elegance is secondary. Use this priority order:

```text
mechanism accuracy > explicit logic > beginner comprehension > memorability > literary style
```

This is an explanation layer around
Pipeline 4, not a new learner-memory owner or teaching-decision system.

## Choose the explanation mode

Select one mode before drafting. Do not blend both output structures.

- **Bridge Mode is the default** for requests to explain, analyze, teach, repair
  confusion, or introduce an unfamiliar topic. State the real technical problem
  and run a minimum concrete case before adding one local analogy. Read
  [references/bridge-mode-contract.md](references/bridge-mode-contract.md).
- **Fable Mode is opt-in** when the user explicitly asks for an allegory, story,
  delayed reveal, or says not to name the concept at first. It is also mandatory
  for the daily-briefing opening story. Read
  [references/story-output-contract.md](references/story-output-contract.md).
- An explicit requested format wins over the default. If a first-time learner
  explicitly requests a concealed-name fable, preserve the delayed reveal but
  make the post-story technical reconstruction complete.
- A strict short form, prompt-only request, or localized rewrite may compress
  Bridge Mode, but it does not relax mechanism accuracy or epistemic limits.

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
make the explanation richer.

## Build one causal spine from first principles

Before drafting, locate the learner's bridge and privately reduce the target to
one causal spine:

```text
known anchor -> missing bridge -> target mechanism -> consequence or application
initial state -> rule or constraint -> local action -> consequence ->
observable trade-off or failure mode
```

Use a concept already known by the learner only as an anchor; do not pretend it
proves mastery. Every causal transition must follow from a visible rule,
constraint, or action. Do not hide a logical jump behind analogy language.

One analogy explains one core relation. If the requested topic contains several
mechanisms, teach them as separate bridges and return to technical language
after each one; never make one story carry the whole system. Use the fewest
analogy elements that preserve the selected relation. Each important element
must have one primary technical counterpart. If an element must represent more
than one object, disclose that overload explicitly or reject the analogy.

When a mechanism concerns propagation, layers, depth, state changes, or
information flow, show the smallest concrete case before stating the general
rule: what one step changes, what two steps change, and only then what fixed
`d` steps imply. In Bridge Mode this case appears before the analogy. In Fable
Mode it is prepared before drafting and shown in the factual debrief. Distinguish
carriers that the real mechanism distinguishes. An observation, measurement,
compression, deletion, or projection that changes state must never appear as
cost-free inspection.

Before returning any analogy, answer both questions:

1. Why does this correspondence make the real mechanism easier to understand?
2. After removing every story word, can the real objects, operations, states,
   prerequisites, and consequences be reconstructed without guessing?

Reject or narrow the analogy when either answer is missing.

For the technical explanation in either mode, read
[references/logic-chain-explanation.md](references/logic-chain-explanation.md).
Use its smallest applicable analysis pattern. Bridge Mode follows its technical
sequence directly; Fable Mode applies it after the reveal while preserving the
required `1 -> 3 -> 4 -> 2` section order.

Read [references/worked-example-contract.md](references/worked-example-contract.md)
before constructing the required example. Match the example to the concept:
mathematical, numerical, operational, causal, experimental, or comparative.
Only use formulas when the concept and evidence genuinely require them. When a
formula is used, expose every meaningful transition and never invent a formula
to satisfy an output shape. A worked example is not another explanation of the
general mechanism: it must instantiate one bounded scenario with named inputs
or initial states, trace those particular values/states through the rules, and
state a concrete observable result.

## Return every analogy to fact

In Bridge Mode, return to formal language immediately after each local analogy.
In Fable Mode, use the four factual sections in the user's requested order:
`1 -> 3 -> 4 -> 2`. In both modes, state what the analogy omits and how it could
lead to a wrong technical inference. Expose the technical causal chain, the
relevant object/operation distinction, and any information that is preserved,
changed, or discarded. Include one worked example whose form follows the
concept rather than forcing every concept into a derivation. Do not claim that
understanding the analogy or example demonstrates mastery.

When a claim uses words such as faster, cheaper, harder, scalable, or advantage,
name the real parameters on which it depends. When the mechanism involves
truncation, discretization, estimation, or modelling, distinguish exact
identities, theoretical limits, finite implementations, approximations, and
their error sources instead of compressing them into an equivalence claim.

When the user requests an interactive explanation, end with one small
prediction, comparison, or paraphrase check. Do not append a fifth numbered
section to a strict Fable Mode response.

## Daily briefing interface

When authoring the required opening story for an AI + quantum briefing, or when
the subject comes from an already published briefing, read
[references/daily-briefing-interface.md](references/daily-briefing-interface.md)
before using it. Daily authoring always uses Fable Mode; it does not add an
`explanation_mode` field or change the existing story schema. For
pre-publication authoring, consume only the source-audited,
deterministically ranked selection. By default, ground the story in the
rank-1 academic item after the academic section has been ordered by descending
impact score; use another source only through an explicit, documented override.
For later explanation, consume finalized,
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
- This skill owns only the bridge-first or fable-first explanation, its explicit
  factual return, and the concept-appropriate worked example.

Finish in the selected mode's contract. If the user later supplies actual
answers or an application attempt, route that evidence through the existing
`adaptive-teach` / `reader-learner` feedback path rather than writing the
profile directly.
