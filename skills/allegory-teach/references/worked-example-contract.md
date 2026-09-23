# Worked Example Contract

Every complete `allegory-teach` explanation includes one worked example after
the factual return. The narrative first runs the same bounded case in story
language; the unnumbered example after section 4 formalizes that case compactly.
The two surfaces preserve the same underlying data identity. Their object or
population, conditions, operation direction, result, counterfactual, and
observable difference must agree. A story-native frequency may project the same datum into an exact ratio or an
explicitly approximate normalized count; it need not repeat the formal metric
notation. Topic selection and
example-form selection are separate decisions: never prefer a concept merely
because it is easy to express with equations.

The example must instantiate the mechanism. A second abstract explanation,
generic workflow, or list of implications is not an example. Name one bounded
scenario, supply the actual inputs or initial states used in that scenario,
identify the observable, and carry those inputs through the steps to a concrete
result. In Fable Mode, the formal block may add symbols, types, rules, and the
general form, but it may not replace the story's case with different values or
reverse the sign, direction, or comparison.

Professional terminology belongs to this formal surface only after factual
section 1 or 2 has introduced and mapped it. If an unavoidable term first
appears in the worked example, precede the label with one plain-language clause
that says what the object or operation does.

## Historical Everyday Mode and version 4 (read compatibility only)

Everyday Mode establishes one intuitive relation before the technical example.
The scene and example must explain that same relation, direction, scope, and
limits, but need not share a setting, sample, numbers, or data identity.
The same-case checks below apply only to Fable Mode and legacy version 3.
Keep formal calculations and statistical metadata outside the scene unless
a particular quantity genuinely helps its familiar action become clear.
Label hypothetical examples as hypothetical; never present invented scenario
values as measurements or replace a source datum with an illustrative value.
A daily version-4 handoff still requires the complete structured example below;
a localized standalone analogy need not grow into a full technical lesson.

## Do not confuse a worked example with a fable

A familiar setting, named character, or physical prop does not turn a worked
example into a Fable Mode story. If the structure is primarily
`given values -> apply rule -> calculate result -> compare result`, keep it as
the worked example and repair the missing story spine; do not switch modes. A fable must additionally make the
actor's goal, real constraint, choice or changed action, observable consequence,
and mechanism reveal carry explanatory work.

Formula density alone does not decide the mode. Keep Fable Mode only when its
narrative action lowers the cost of understanding the real dependency; otherwise
repair the story or report the failed gate. In a valid Fable response, this contract still
formalizes the already completed story case compactly and never supplies a
missing narrative spine after the fact.

Use one-example-one-job discipline:

- In Fable Mode, the story owns the intuitive run. The worked example defines
  formal objects, states the real rule, gives a compact calculation or state
  trace, and performs one useful check. It must not retell the story in equally
  long prose.
- If a second case is genuinely needed to test another relation, that relation
  requires a separate bridge rather than an expanded first example.

## Select the example form

Choose the smallest form that makes the target mechanism testable:

- `mathematical`: derive a relation from stated definitions or assumptions;
- `numerical`: calculate a concrete instance and then reconnect it to the
  general relation;
- `operational`: trace inputs, operations, intermediate states, outputs, and a
  failure case;
- `causal`: change one condition, compare the counterfactual, and state the
  bounded causal conclusion;
- `experimental`: identify preparation, controls, measurement, observation,
  and what the observation excludes;
- `comparative`: hold the shared setup fixed, change one defining condition,
  and show the resulting difference.

A non-mathematical example is complete without a formula. Never invent an
equation, coefficient, probability model, or quantitative law to make it look
formal. If the selected mechanism is genuinely mathematical, use the smallest
useful calculation before the general form and keep every meaningful transition
inspectable.

## Audit empirical metrics before calculation

An empirical number is not self-identifying. Before using a rate, probability,
percentage, fidelity, or error metric, preserve:

```text
metric name -> numerator -> denominator -> conditioning set -> experimental
unit -> device or population -> round or time window -> reported uncertainty
```

Use the existing handoff fields rather than adding schema: put the population,
device, time/round, and comparison conditions in `scenario`, `inputs`, and
`assumptions`; identify the measured quantity in `observable`; preserve the
source's uncertainty in the relevant input, result, or check; and state the
strongest unsupported extrapolation in `non_conclusion`.

Do not multiply, divide, or otherwise compose values from different
experiments, populations, denominators, or conditioning sets merely because
their units look compatible. First require a compatible sample space, target
event, population, and conditioning set. Then allow composition only when the
source reports the joint quantity or supplies a model, or when the explanation
states and defends the exact conditional-independence assumption required. Keep
leakage removal, readout fidelity, state fidelity, logical error, and end-to-end
task success as distinct metrics unless an explicit composition model connects
them.

The worked example must also preserve evidence level. A measured result, an
author's mechanistic attribution, an inference compatible with the data, and an
analogy-only visualization are not interchangeable inputs. Do not use arithmetic
to convert a local observation into a unique causal explanation or universal
claim.

For a Fable response, compare this formal metric record with the narrative
projection. An exact story ratio must represent the same value. A rounded count
must be marked approximate, use the same population and conditioning, and be
described as normalization rather than raw trial count. The narrative contains
neither the formal metric label nor percent sign, unit, error bar, or statistical
qualifier; this block restores all of them without changing the datum.
In particular, it restores the exact source value rather than treating the
story's normalized or rounded expression as the formal measurement.

## Common structure

Represent a daily-briefing handoff as:

```json
{
  "kind": "mathematical|numerical|operational|causal|experimental|comparative",
  "title": "例子标题",
  "question": "这个例子要回答什么",
  "scenario": "一个有明确对象、初态、条件和目标的具体场景",
  "inputs": [
    {
      "name": "本例输入或初态",
      "value": "本例实际使用的数值、标签、状态或条件",
      "role": "这个输入如何进入后续步骤"
    }
  ],
  "observable": "完成步骤后具体观察、比较或计算什么",
  "assumptions": ["适用条件或约束"],
  "objects": [
    {
      "name": "对象或符号",
      "kind": "数学类型或现实角色",
      "role": "它在例子中的作用",
      "units": "仅在适用时填写"
    }
  ],
  "steps": [
    {
      "action": "操作或状态变化；有公式时也要说明它做了什么",
      "formula": "仅在真实需要时填写，不包含显示分隔符",
      "rule": "定义、假设、恒等式、近似、定理或操作规则",
      "explanation": "为什么能够从上一步得到这一步"
    }
  ],
  "result": "例子的直接结果",
  "interpretation": "结果的现实、物理或操作含义",
  "checks": ["反例、极限、量纲、归一化或条件变化检查"],
  "non_conclusion": "这个例子不能支持的更强结论"
}
```

The number of objects and steps follows the mechanism. Do not pad a short proof
or truncate a long causal chain to meet an arbitrary count. Every step needs a
named rule and an explanation, and it needs at least one of `action` or
`formula`.

`scenario`, `inputs`, and `observable` are mandatory. Each input requires a
name, a value/state/condition used by this instance, and a role. Values need not
be numeric: an operational example may use queue states, an experiment may use
treatment/control assignments, and a comparison may use two named cases. But
the steps must visibly consume these inputs. If the same text would still work
after deleting every value, state, and entity name, it is probably only a logic
explanation and must be rewritten.

If any step contains `formula`, define the formula's symbols in `objects`, keep
notation stable, and add a check that could expose a wrong derivation. For a
mathematical example, at least one step must contain a genuine formula. Formula
strings contain TeX bodies without `\(...\)` or `\[...\]`; the renderer owns
the display boundaries.

## Final consistency check

Before returning the example, verify:

- in Fable Mode, the story and formal block preserve the same underlying data
  identity and bounded case; in Everyday Mode, they explain the same relation
  without claiming that a hypothetical scene is a source experiment;
- any narrative frequency preserves the same population, conditioning,
  direction, and conclusion, and marks rounding rather than implying a new raw
  sample;
- each formal step consumes a named input or an explicitly derived state;
- the operation direction, sign, result, counterfactual, and observable agree;
- every empirical metric retains its numerator, denominator, conditions,
  experimental unit, scope, and available uncertainty;
- any metric composition is licensed by a source-backed joint model or an
  explicit, defensible conditional-independence assumption after confirming a
  compatible sample space, target event, population, and conditioning set;
- the block adds formal precision or a falsifying check rather than repeating
  the story's prose; and
- every professional term in the block was introduced in factual section 1 or
  2, or receives a plain-language clause before its formal label; and
- the `non_conclusion` prevents the most tempting unsupported generalization.

Concrete domain cases belong in `tests/regression_cases.json`, not in this
production contract.

## Cross-surface revision gate

Read the semantic, timing and cross-surface review in
`logic-chain-explanation.md`. Recheck every story-linked assertion after any
narrative change; an unchanged example is never a consistency certificate.
