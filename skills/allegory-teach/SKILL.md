---
name: allegory-teach
description: "Explain difficult concepts through complete, source-faithful concealed-name fables followed by a precise factual return and worked example. Use for ordinary teaching, life-based analogy requests, and daily openings within this skill; never mutate learner knowledge or publish briefings."
---

# Allegory Teach

Turn one concept into a low-friction causal model without letting an analogy
replace the underlying technical claim. Technical correctness and beginner
comprehensibility are independent hard gates: failing either requires a
rewrite. Only after both gates pass, use this optimization order:

```text
explicit logic > cognitive simplicity > brevity > memorability > literary style
```

This is an explanation layer around
Pipeline 4, not a new learner-memory owner or teaching-decision system.

## Unified Fable entry

All new invocations use Fable Mode: ordinary explanation, life-based analogy,
and daily opening alike. This governs this skill, not unrelated project replies.
Bridge and Everyday references describe historical behavior only; never select
them or silently downgrade a new request. Read
[references/story-output-contract.md](references/story-output-contract.md) and
[references/narrative-language-firewall.md](references/narrative-language-firewall.md).

## Story-value repair gate

A fable is valid only when its actions teach the mechanism. Privately compare
it with the minimum technical case, then perform one repair pass: narrow the
relation and rebuild a familiar goal, real limit, choice and consequence.
If it still merely renames variables or replays formulas, disclose the specific
obstacle and stop rather than returning a weak fable or switching modes.
Daily authoring uses the ranked-source fallback below; if no eligible source
passes, stop publication and report the failed gate.

At least two causally necessary background paragraphs introduce the goal and
constraints. There is no total length/count ceiling. A localized edit preserves
the surrounding complete story instead of imposing an artificial short budget.

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

For source-grounded research, first preserve the minimum problem context that
makes the selected relation worth explaining. Apply the context-binding check in
`references/story-output-contract.md`; do not confuse a generic mechanism with
the paper's motivation or invent a baseline to make the story distinctive.

Before drafting, locate the learner's bridge and privately reduce the target to
one causal spine:

```text
known anchor -> missing bridge -> target mechanism -> consequence or application
initial state -> rule or constraint -> local action -> consequence ->
observable trade-off or failure mode
```

Before choosing story objects, prepare the minimum real case, choose one
relation, and turn it into a complete causal story. Do not add a second system
of invented rules. A caveat may be the selected relation, but it must not
masquerade as an explanation of the whole paper or protocol.

Do not build a story world first and then force each technical object into it.
Compress the mechanism to its minimum objects, one causal transition, and one
observable difference before deciding whether imagery helps.

For Fable Mode, turn that technical spine into this narrative spine before
drafting:

```text
world state -> actor goal -> available capability and limit -> trigger ->
observable stakes -> actor choice -> mechanism consequence
```

The background is part of the explanation. Each setup paragraph must make the
later choice, consequence, or need for the mechanism more intelligible. If the
paragraph can be removed without changing any of those, rewrite it instead of
keeping it as decorative lore.

Use a concept already known by the learner only as an anchor; do not pretend it
proves mastery. Every causal transition must follow from a visible rule,
constraint, or action. Do not hide a logical jump behind analogy language.

Formal derivations and evidence classifications stay in private preflight and
factual return; the story must itself explain the ordinary action and outcome.
A visible rule is not yet an explained rule. Before the first calculation,
update, transition, comparison, or replacement that depends on a rule, identify
what is being tracked, why it can change, where the rule comes from, and why
each required input contributes. A legitimate source may be a definition,
original dynamics, a chain-rule step, a conservation constraint, a measurement
operation, an experimental protocol, or a declared approximation. When a
finite version removes an input, also state what replaces it and where the
resulting error enters. A non-mathematical mechanism needs its real protocol,
constraint, or operating basis, not a decorative formula or forced derivation.

## Authorize every causal edge

Technical correctness includes evidence authority, not only internal
consistency. Before an analogy renames any object or action, audit every
calculation, update, state transition, causal verb, and replacement as:

```text
real object -> technical operation -> rule or evidence source -> actual change
-> preserved content -> lost content -> conclusion not established
```

Classify the source as one of: a definition or protocol, a direct measurement,
the source author's mechanistic attribution, an inference consistent with but
not uniquely established by the evidence, or an analogy-only visualization.
Use that classification in the private preflight and factual debrief. Do not
write the classification, source voice, or reviewer language inside a sealed
Fable narrative. A story may not promote an attribution into a measurement, a
compatible inference into a uniquely proved cause, or a visual device into a
physical mechanism.

Preserve the semantic target of every operation. Restoring membership in an
allowed state space does not by itself recover the original logical content;
removing leakage is not complete error correction; reading an outcome is not
by itself evidence of passive, disturbance-free observation; discarding failed
trials is not a physical reset; smaller disturbance is not zero disturbance;
and a local fidelity or error metric is not end-to-end task success. Generalize
these distinctions beyond quantum examples: state what the operation changes,
what it preserves, what it discards, and what remains unknown.

An analogy may rename supported objects and operations, but it may not add a
new causal verb, intermediate mechanism, directionality, or guarantee. When the
source does not identify the next causal link, stop the analogy at that
evidence boundary. In Fable Mode, show only the corresponding in-world limit,
end the narrative before switching voice, and state in the factual debrief that
the available evidence does not distinguish the missing mechanism. Prefer one
fewer explained step to one invented step.

Fable Mode has a hard language boundary in addition to evidence fidelity. Its
title and every narrative paragraph form a closed story world: domain terms,
formal symbols, equations, metric labels, units, source attribution, and
reviewer commentary remain in the private preflight or factual debrief. Build a
case-specific denylist from the source and planned debrief plus a compact list
of story-world objects and actions before drafting, then audit the full
narrative. Read
[references/narrative-language-firewall.md](references/narrative-language-firewall.md)
for this narrative contract. Formal technical teaching belongs after the reveal.

One analogy explains one core relation. If the requested topic contains several
mechanisms, teach them as separate complete fables and return to technical language
after each one; never make one story carry the whole system. Use the fewest
analogy elements that preserve the selected relation. Each important element
must have one primary technical counterpart. If an element must represent more
than one object, disclose that overload explicitly or reject the analogy.

As a soft cognitive budget, prefer at most three mechanism-bearing story
objects and one unfamiliar story-world rule. Count only elements that carry a
technical mapping, not ordinary background nouns. Exceeding this preference is
not an automatic failure, but it requires another compression pass and is
allowed only when the additional element makes the selected relation easier to
understand. Literary setting, historical style, poetic wording, and dramatic
stakes are optional; familiar objects and ordinary actions are preferred.

When a mechanism concerns propagation, layers, depth, state changes, or
information flow, show the smallest concrete case before stating the general
rule: what one step changes, what two steps change, and only then what fixed
`d` steps imply. The case is prepared before drafting, run with inspectable inputs and results in
the story body, and then restated in formal language in the factual debrief.
Distinguish carriers that the real mechanism distinguishes. An observation,
measurement, compression, deletion, or projection that changes state must never
appear as cost-free inspection.

Complete the story and technical causal spines before compressing Fable Mode.
Do not impose a total word, paragraph, or mechanism-paragraph limit. Let each
necessary state transition occupy its own paragraph when that lowers the
reader's reconstruction cost. Apply the deletion test only after both spines are
complete, and never remove a goal, limit, rule source, choice, state change, or
consequence merely to make the answer shorter. A mathematical or numerical
story must expose one complete in-story run:

```text
actual input -> explicit operation -> intermediate value -> result ->
counterfactual result -> observable difference
```

In Fable Mode, hide all professional representation until the story has ended: the concept
name and aliases, adjacent domain vocabulary, standard acronyms, variables,
formal notation, equations, units, and metric labels. Do not hide the causal
operation, intermediate quantity, result, or comparison; express them through
ordinary story-world actions and numbers rather than source notation. Reveal
the canonical name only in factual section 1. A non-mathematical story uses
named story objects, explicit in-world states, an operation, and an observable
failure or transition instead of decorative numbers. Reject
undefined mechanism-bearing shorthand such as “some contribution,” “this initial
value,” “higher-page effect,” or “now they match.” Each first occurrence must say
what the object records, its current value or state, and how it enters the next
step.

## Beginner-comprehension gates

An analogy succeeds only when it lowers vocabulary and working-memory load.
Before returning one, run all five checks below. Failure of any check means
simplify or replace the analogy, then apply the Story-value repair gate.

1. **Plain-Language Gate:** every mechanism-bearing phrase is understandable
   without learning a second metaphor vocabulary. An invented term is invalid
   when it merely renames the abstraction.
2. **Self-Explanation Test:** a first-time learner can say what physically or
   operationally happens. Prefer actions such as take away, keep, connect,
   disconnect, copy, pass, replace, set to zero, add, and compare. Words such as
   seal, freeze, hide, awaken, or suppress must immediately define their exact
   operation or be replaced.
3. **Cognitive Compression Test:** compare only mechanism-bearing objects,
   independent rules, state labels, and causal transitions. If the analogy
   creates a second symbolic system that is harder than the minimum technical
   case, abandon it.
4. **Literal Reconstruction Test:** remove decorative story nouns and restate
   the remainder as `input/object -> operation -> state change -> output ->
   observable difference`. No essential step may disappear.
5. **Predicted Follow-up Test:** the likely next question should concern the
   real variable, operation, condition, or approximation. If it is instead
   “what does that story word mean?”, regenerate.

The preflight must also answer both questions:

1. Why does this correspondence make the real mechanism easier to understand?
2. After removing every story word, can the real objects, operations, states,
   prerequisites, and consequences be reconstructed without guessing?

Reject or narrow the analogy when either answer is missing.

For the technical explanation in every mode, read
[references/logic-chain-explanation.md](references/logic-chain-explanation.md).
Use its smallest applicable analysis pattern after the reveal while preserving the
required `1 -> 2 -> 3 -> 4` section order.

Read [references/worked-example-contract.md](references/worked-example-contract.md)
before constructing the required example. Match the example to the concept:
mathematical, numerical, operational, causal, experimental, or comparative.
Only use formulas when the concept and evidence genuinely require them. When a
formula is used, expose every meaningful transition and never invent a formula
to satisfy an output shape. A worked example is not another explanation of the
general mechanism: it must instantiate one bounded scenario with named inputs
or initial states, trace those particular values/states through the rules, and
state a concrete observable result. Hypothetical examples are not source measurements. In Fable Mode, the story body and
`worked_example` must retain the same underlying case and data identity,
operation direction, conditions, comparison, and conclusion. The story may use
an exact in-world frequency or an explicitly approximate normalized count while
the debrief restores the source value and metric identity; it may not silently
change the sample, denominator, or result. The debrief may reveal formal
notation and the general rule but may not substitute a cleaner case. Because
the story has already run the case, the worked example formalizes it compactly
instead of repeating the same narrative at equal length.

## Semantic, timing and cross-surface review

Before writing, lock one selected teaching relation. The title, bounded
definition, narrative, action mapping and worked example must explain that
relation, not alternate between a caveat and the whole system.

Preserve object types: a basis is not its linear span, a set of labels is not
a state space, and a population is not an individual state or its information.
"Not established" is not "impossible" and does not license a story-invented
cause of loss. Preserve parallel, serial, conditional and feedback dependencies;
never add detection or a decision as the prerequisite of an unconditional act.
Verify unfamiliar terms against the original source; retain the original term
rather than inventing a translation when uncertain.

After any story edit, re-review every example reference to a story object,
number, action, condition, comparison and conclusion. An unchanged example is
not evidence of consistency. Reject phantom story quantities and stale case
references. Hypothetical case data must be labeled, never passed off as a
paper's sample. A semantic error in the core mapping cannot be repaired by
adding disclaimers.

Keep audit records separate from teaching prose. The visible story must be
understandable before expanding the example; the debrief carries the real
mechanism and only consequential boundaries. Detailed derivations and metric
identities belong in the example without repeatedly printing internal checks.

Report structural validation separately from semantic review. A semantic
review needs the reviewed text, judgment, source or rule basis, and limitation.
Missing evidence means unreviewed, not pass. Length and keyword checks cannot
certify comprehension, truth or action correspondence.

## Return every analogy to fact

Use the four factual sections in order:
`1 -> 2 -> 3 -> 4`, then place the unnumbered worked example after section 4.
State what the analogy omits and how it could
lead to a wrong technical inference. Expose the technical causal chain, the
relevant object/operation distinction, and any information that is preserved,
changed, discarded, or not established. For each important analogy action,
return `story action -> technical operation -> evidence level -> why required
-> changed/preserved/lost content -> observable consequence -> unsupported
stronger conclusion`. Include one worked example whose form follows the
concept rather than forcing every concept into a derivation. Do not claim that
understanding the analogy or example demonstrates mastery.

When a claim uses words such as faster, cheaper, harder, scalable, or advantage,
name the real parameters on which it depends. When the mechanism involves
truncation, discretization, estimation, or modelling, distinguish exact
identities, theoretical limits, finite implementations, approximations, and
their error sources instead of compressing them into an equivalence claim. For
any removal, truncation, projection, pruning, compression, or approximation,
state what originally contributed, what is no longer represented, which rule
replaces the missing contribution, and where the resulting error enters.
For empirical percentages or rates, retain the metric identity, numerator,
denominator, conditioning set, device or population, round or time window, and
source-reported uncertainty in the factual debrief or worked example. In a
sealed Fable narrative, include a number only when it aids causal understanding
and express it as a story-native frequency without a formal metric label,
percent sign, unit, or implied raw sample size. Do not multiply results from different experiments
unless they share a compatible sample space, target event, population, and
conditioning set and a source-backed joint model or a stated, defensible
conditional-independence assumption licenses the composition. Never promote a
component metric into end-to-end success without an explicit composition model.

When the user requests an interactive explanation, end with one small
prediction, comparison, or paraphrase check. Do not append a fifth numbered
section to a strict Fable Mode response.

## Daily briefing interface

When authoring the required opening story for an AI + quantum briefing, or when
the subject comes from an already published briefing, read
[references/daily-briefing-interface.md](references/daily-briefing-interface.md)
before using it. All new daily authoring uses Fable and
`opening_story.version=3`. Keep existing versions 1–4 readable without changing
their runtime meaning. Do not add an `explanation_mode` field. For
pre-publication authoring, consume only the source-audited,
deterministically ranked selection. By default, ground the story in the
rank-1 academic item after the academic section has been ordered by descending
impact score and first try to narrow that item to one relation that passes the
story-value gate. If no relation survives one repair pass, inspect the remaining
academic items in rank order and use the first one that passes, recording
`story_delivery.selection_basis="explicit_override"` and a concrete
`override_reason`. A stable learner-profile concept requires explicit user
selection. If no eligible source passes, stop publication and report the failed
gate. Never weaken ranking or publish a noun-renaming story to avoid the override.
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
- This skill owns only the complete fable explanation, its explicit
  factual return, and the concept-appropriate worked example.

Finish in the Fable contract. If the user later supplies actual
answers or an application attempt, route that evidence through the existing
`adaptive-teach` / `reader-learner` feedback path rather than writing the
profile directly.
