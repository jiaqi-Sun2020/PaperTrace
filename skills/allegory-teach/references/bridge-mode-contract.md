# Bridge Mode Contract

Use Bridge Mode for a first encounter, a direct explanation, or a request to
repair confusion unless the user explicitly asks for a concealed-name fable.
Its job is to expose the missing technical relation before adding imagery.

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
5. **One local analogy:** explain only the selected relation. Introduce no extra
   characters, objects, or world rules that the bridge does not need.
6. **Map and justify:** map each important analogy element to one primary
   technical object or operation, then state why that correspondence helps.
7. **Return to technical language:** restate the same transition without story
   vocabulary before moving to another mechanism.
8. **Bound the claim:** identify analogy limits and, when applicable, separate
   exact theory, finite implementation, approximation, and error source.
9. **Reconnect the chain:** finish with
   `previous step -> current bridge -> next step -> resulting capability`.

Do not force all nine items into nine headings when the request is narrow. Do
not omit the technical position, minimum case, mapping, technical return, or
bounded conclusion merely to make the answer shorter.

## Analogy discipline

One local analogy explains one core relation. When a topic contains multiple
relations, repeat the cycle

```text
formal mechanism -> minimum case -> local analogy -> explicit mapping -> formal return
```

for each bridge that is actually needed. Do not combine representation,
truncation, solver complexity, error, readout, and end-to-end advantage into one
story.

Use one primary technical counterpart per important analogy element. If a
limited overload is unavoidable, list every counterpart and explain the limit;
otherwise replace the analogy. After mapping, answer:

- Why does this correspondence make the missing transition visible?
- Can the real mechanism be restated after deleting every analogy noun?

If either answer is no, the analogy has renamed the abstraction rather than
lowered its cost and must be rewritten.

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

## Regression case: Carleman linearization

Use this case to audit ordering and precision, not as a universal template.

Start with the disclosed technical problem:

```tex
\dot{x}=x+x^2.
```

The nonlinear term is `x^2`; the local target is to see why treating monomials
as coordinates turns one nonlinear update into linear couplings in a larger
state description. Define

```tex
z_1=x,\qquad z_2=x^2,\qquad z_3=x^3.
```

Then calculate before using an analogy:

```tex
\dot{z}_1=z_1+z_2,
```

and, by the chain rule,

```tex
\dot{z}_2=2x\dot{x}=2x^2+2x^3=2z_2+2z_3.
```

This is the useful bridge: nonlinear powers of `x` become coordinates coupled
linearly to one another. A short “additional ledger columns” analogy may now
represent the added monomial coordinates, but it must state that a ledger column
is an analysis coordinate, not a new independent physical freedom.

The audit must also preserve the boundary: the exact Carleman construction is
generally infinite-dimensional, whereas a computation that keeps terms only up
to order `K` is a finite truncation with truncation error. A claim about cost or
advantage is incomplete unless it states its dependence on relevant quantities
such as `K`, system dimension, time horizon, target error, solver conditioning,
and requested readout.

## Failure conditions

Rewrite the explanation when any of the following is true:

- the analogy appears before the real problem or minimum case;
- the learner must decode new story vocabulary before understanding the target;
- the analogy says what happened but not why the step helps;
- one analogy carries more than one unresolved technical mechanism;
- the mapping drifts or uses one object for incompatible technical roles;
- an approximation is described as an exact equivalence;
- a performance conclusion has no governing technical parameters;
- the final chain does not identify the previous step, current bridge, and next
  step.
