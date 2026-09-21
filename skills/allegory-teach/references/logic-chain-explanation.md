# Logic-Chain Explanation Guidance

Use this shared guide for the technical layer in both modes. Bridge Mode applies
it before and around each local analogy; Fable Mode applies it after the reveal.
It adapts the project-local `logic-chain-tutor` approach to this skill's two
output contracts.

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

In Bridge Mode, the minimum case appears before any optional analogy. In Fable
Mode, it is prepared before story drafting, run in the narrative without leaking
the concept name, and then formalized compactly after the factual debrief. In
either mode, generalize only after the minimum case has visibly run once.

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
