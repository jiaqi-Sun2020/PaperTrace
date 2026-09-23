# Logic-Chain Explanation Guidance

Use this guide for private technical preflight and the factual return after a
complete Fable. Do not expose the formal derivation before the narrative ends.

## Diagnose the smallest missing bridge

Start with the learner's supplied wording, selected profile concept, or source
context. Identify the nearest known anchor and the single missing relation that
makes the target mechanism intelligible. Do not restart the whole subject when
one bridge is enough; do not manufacture a knowledge-state claim from exposure.

Assume the reader is encountering the target topic for the first time. When the
missing bridge involves a process, begin with the smallest numbered or named
instance and make each state transition visible. Generalize only after the
reader can answer “what changed in this particular case?”

Choose the analysis move from the actual question:

| Learner need | Smallest useful move |
|---|---|
| What is it? | Object-level definition, defining property, role, and a near non-example. |
| Why is it needed? | State the problem, test the counterfactual without the mechanism, then state what it enables. |
| How does it arise? | Start from accepted premises and expose each causal transition. |
| What does it mean physically or operationally? | Name the actors, state before, operation, state after, and observable outcome. |
| How does it differ from a nearby idea? | Contrast object type, operation, preserved information, changed information, and invalid interchange. |

Choose the worked-example form independently of topic selection. A concept is
not more suitable merely because it has equations:

| Concept structure | Worked-example form |
|---|---|
| Mathematical or theoretical | A source-backed derivation or numerical case, only when the formula carries the mechanism. |
| Algorithmic or systemic | Input, operations, intermediate states, output, and failure case. |
| Causal or statistical | Intervention or changed condition, counterfactual comparison, and bounded conclusion. |
| Experimental | Preparation, controls, measurement, observation, and what the observation rules out. |
| Engineering or product | Concrete constraint, decision, state transition, consequence, and trade-off. |
| Philosophical or methodological | Minimal case, nearby counterexample, scope, and invalid inference. |

Every worked example must identify a concrete scenario, its actual inputs or
initial states, and the observable to inspect. The steps must consume those
inputs and produce the stated result. A paragraph that only repeats the causal
chain, even accurately, remains an explanation and does not satisfy the example
contract.

Prepare the minimum case before story drafting, run it in the narrative without
leaking the concept name, then formalize it compactly after the factual debrief.
Generalize only after the minimum case has visibly run once.

## Keep technical claims inspectable

Before using notation or a formula, state what every object is, what role it
plays, and what the operation does. Explain information carriers such as value,
sign, phase, index, position, or zero pattern only when relevant. Name the
operation precisely rather than treating visual similarity as equivalence.

For a derivation, make each meaningful link auditable:

```text
accepted premise -> named rule -> resulting relation -> operational meaning
```

Say whether a step is a definition, assumption, identity, approximation, or
derived conclusion. If a claimed necessity is actually a convention or
compatibility choice, say so. Test units, normalization, a limiting case, or a
small numerical example when it can invalidate a mistaken inference.

Do not create notation for a non-mathematical concept merely to fill a formula
slot. When mathematics is intrinsic, follow the complete chain `goal ->
premises -> symbols -> derivation -> result -> interpretation -> check ->
non-conclusion`. When it is not intrinsic, use the corresponding operational or
causal chain and omit formulas without apology.

For truncation, discretization, estimation, or modelling, label every relevant
statement as an exact identity, theoretical limit, finite implementation,
approximation, or empirical conclusion. Name the approximation's error source.
Do not say a nonlinear system “became” a finite exact linear system when the
implementation discarded higher-order terms.

Only when making a performance claim, name the real governing parameters. These
may include input or state dimension, truncation order, time horizon, step size,
condition number, target error, sample count, or number of requested
observables. Do not list irrelevant symbols merely to make the answer look
complete.

## Preserve evidence authority and semantic targets

Audit each causal edge before translating it into an analogy:

```text
real object -> technical operation -> rule or evidence source -> actual change
-> preserved content -> lost content -> conclusion not established
```

Assign the strongest source class that is actually available:

1. definition or declared protocol;
2. direct measurement or observation;
3. the source author's mechanistic attribution;
4. an inference that is consistent with, but not uniquely established by, the
   evidence; or
5. analogy-only visualization.

Use claim verbs that preserve that class: distinguish “is defined as,” “the
experiment measured,” “the authors attribute,” and “is consistent with.” Do
not turn correlation into unique causation, an attribution into direct
measurement, or a visualization into a physical intermediate step. Preserve
the source's device, population, calibration, time, round, and uncertainty
scope. If an essential link is unresolved, state that the evidence does not
distinguish the mechanism instead of filling the gap with a story action.

Preserve the operation's semantic target. A transition into an allowed state
set does not establish recovery of the original information carried within that
set. Removal of one failure mode does not establish complete correction;
measurement or readout does not imply passive observation; post-selection does
not physically reset discarded systems; reduced disturbance does not mean zero
disturbance; and a component fidelity or error rate does not establish global
task success. In every domain, name what changed, what was preserved, what was
discarded, and what remains unknown.

For every empirical rate, probability, percentage, or fidelity, identify the
metric, numerator, denominator, conditioning set, experimental unit, device or
population, round or time window, and source-reported uncertainty when present.
First require a compatible sample space, target event, population, and
conditioning set. Then combine metrics only when the source provides a joint
quantity or explicit composition model, or when a stated conditional-
independence assumption is defensible for that exact population. Otherwise
report the quantities separately.

## Correct without replacing the learner's model wholesale

When a plausible interpretation is wrong, respond in this order:

1. preserve the part that is structurally correct;
2. locate the first invalid inference;
3. replace only that link with the precise condition or operation;
4. test the repair with a minimal changed case.

An analogy is an entry point, not proof. Its final mapping must identify the
model assumptions it hides and at least one conclusion that a literal story
reading would wrongly suggest.

Perform a carrier audit when the subject involves information or state:

```text
carrier before -> operation and side effect -> carrier after -> transmission
or control step -> observable consequence
```

Do not silently preserve a carrier that the operation consumes or changes. In
quantum cases, keep quantum state, measurement outcome, classical message, and
feed-forward action distinct; shared classical control is not automatically
long-range quantum correlation or entanglement.

## Close proportionally

For an interactive teaching request, invite one prediction, comparison, or
plain-language paraphrase. Use the answer to choose the next explanation move.
For the strict fable response, do not add a separate quiz or recap section: the
compact logic chain belongs at the end of section 2. The chain must identify the
previous step, the bridge just repaired, the next step, and the capability or
consequence that follows.

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
