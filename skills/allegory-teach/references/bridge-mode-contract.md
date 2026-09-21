# Bridge Mode Contract

Use Bridge Mode for a first encounter, a direct explanation, or a request to
repair confusion unless the user explicitly asks for a concealed-name fable.
Its job is to expose the missing technical relation before adding imagery.

## Prefer Bridge Mode when it is clearer

A good Bridge Mode explanation is preferable to a weak fable. If a proposed
story only renames variables or wraps `given values -> apply rule -> calculate
-> compare` in scenery, keep the technical skeleton visible and use Bridge Mode.
Formula-heavy material does not automatically require Bridge Mode; route by
whether a goal, real limit, meaningful action, or observable consequence makes
the mechanism easier to reconstruct.

For an explicit fable request, first narrow the target to one story-worthy
relation and replace noun substitutions with causal actions. If that repair
still adds decoding cost without teaching value, say so and use this contract
instead. Daily opening stories do not use this fallback; their source selection
follows `daily-briefing-interface.md` so the required opening remains a valid
Fable Mode story.

## Required sequence

For a substantial explanation, keep this causal order. Headings may be
compressed for a short-form request, but the mechanism may not be reordered:

1. **Technical position:** name the real object or problem, the term or operation
   causing difficulty, and the immediate goal.
2. **Known -> gap -> target:** identify the nearest supported anchor, the one
   missing bridge, and what the learner should be able to explain afterward.
3. **Minimum concrete case:** use actual values, states, labels, or conditions.
   For an intrinsically mathematical mechanism, calculate the smallest useful
   case before displaying the general form. For a non-mathematical mechanism,
   trace concrete input, state change, output, and one failure case.
4. **Run the real mechanism:** show each meaningful transition and say why it
   follows. Distinguish definitions, assumptions, identities, approximations,
   and conclusions.
5. **Need-an-analogy decision:** ask whether the concrete case already makes the
   missing relation visible. If yes, continue in technical language without an
   analogy. If no, use one local analogy for only that relation and introduce no
   extra characters, objects, or world rules that the bridge does not need.
6. **Map and justify when an analogy is used:** map each important analogy
   element to one primary technical object or operation, then state why that
   correspondence lowers the learner's cognitive cost.
7. **Return to technical language after an analogy:** restate the same
   transition without story vocabulary before moving to another mechanism.
8. **Bound the claim:** identify analogy limits and, when applicable, separate
   exact theory, finite implementation, approximation, and error source.
9. **Reconnect the chain:** finish with
   `previous step -> current bridge -> next step -> resulting capability`.

Do not force all nine items into nine headings when the request is narrow. Do
not omit the technical position, minimum case, or bounded conclusion merely to
make the answer shorter. Mapping and analogy return are mandatory only when an
analogy is actually used.

## Analogy discipline

Do not build a full analogy when the direct concrete case already repairs the
bridge. When an analogy is needed, one local analogy explains one core relation.
For a topic with multiple unresolved relations, repeat the cycle

```text
formal mechanism -> minimum case -> need decision -> optional local analogy ->
explicit mapping -> formal return
```

for each bridge that is actually needed. Do not combine representation,
truncation, solver complexity, error, readout, and end-to-end advantage into one
story.

Prefer no more than three mechanism-bearing analogy objects and one unfamiliar
story rule. This is a soft cognitive budget rather than a numeric validity
rule: count only elements that participate in the mapping, then keep an excess
element only if another compression pass shows that it lowers total effort.

Use one primary technical counterpart per important analogy element. If a
limited overload is unavoidable, list every counterpart and explain the limit;
otherwise replace the analogy. After mapping, answer:

- Why does this correspondence make the missing transition visible?
- Can the real mechanism be restated after deleting every analogy noun?

If either answer is no, the analogy has renamed the abstraction rather than
lowered its cost and must be rewritten.

Apply the five beginner-comprehension checks from `SKILL.md`: plain language,
self-explanation, cognitive compression, literal reconstruction, and predicted
follow-up. Prefer familiar operational actions such as remove, retain, connect,
replace, set to zero, add, and compare. An invented mechanism word is not an
explanation unless its physical operation is stated immediately.

## Precision gates

- Mathematical notation is required only when mathematics carries the
  mechanism. Never invent a formula, coefficient, or quantitative law.
- For truncation, discretization, estimation, or modelling, distinguish an exact
  identity or infinite theoretical construction from a finite approximation and
  name the associated error source.
- A claim of faster, slower, cheaper, harder, scalable, or advantageous must name
  the relevant real parameters, such as state dimension `N`, truncation order
  `K`, step size `\Delta t`, condition number `\kappa`, target error `\epsilon`,
  or number of requested observables `M`. Mention only parameters that actually
  govern the claim.
- Do not turn a coordinate introduced for analysis into an independent physical
  degree of freedom unless the domain evidence establishes that interpretation.
- For removal, truncation, projection, pruning, compression, or approximation,
  explicitly identify the original contributors, the removed or unrepresented
  part, the rule used in place of its contribution, and the resulting error
  path. A metaphorical action cannot substitute for the replacement rule.

## Failure conditions

Rewrite the explanation when any of the following is true:

- an optional analogy appears before the real problem or minimum case;
- an analogy is added even though the concrete case already repairs the bridge;
- the learner must decode new story vocabulary before understanding the target;
- the analogy says what happened but not why the step helps;
- one analogy carries more than one unresolved technical mechanism;
- the mapping drifts or uses one object for incompatible technical roles;
- an approximation is described as an exact equivalence;
- a performance conclusion has no governing technical parameters;
- the final chain does not identify the previous step, current bridge, and next
  step.
