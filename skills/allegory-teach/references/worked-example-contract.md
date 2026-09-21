# Worked Example Contract

Every complete `allegory-teach` explanation includes one worked example after
the relevant technical setup. In Bridge Mode, run the minimum example before
any optional local analogy, then reuse its objects in the mapping and formal
return. In Fable Mode, the narrative first runs the same bounded case in story
language; the unnumbered example after section 4 formalizes that case compactly.
Inputs or state labels, operation direction, signs, result, counterfactual, and
observable difference must agree across both surfaces. Topic selection and
example-form selection are separate decisions: never prefer a concept merely
because it is easy to express with equations.

In Bridge Mode, the minimum case normally is the required worked example. Reuse
it through any optional local analogy and formal return instead of inventing a
second case that increases cognitive load without testing a different necessary
link. Do not print the same calculation or state trace a second time.

The example must instantiate the mechanism. A second abstract explanation,
generic workflow, or list of implications is not an example. Name one bounded
scenario, supply the actual inputs or initial states used in that scenario,
identify the observable, and carry those inputs through the steps to a concrete
result. In Fable Mode, the formal block may add symbols, types, rules, and the
general form, but it may not replace the story's case with different values or
reverse the sign, direction, or comparison.

Use one-example-one-job discipline:

- In Bridge Mode, the concrete case is the worked example; later prose refers
  back to it rather than replaying it.
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

- the story and formal block use the same inputs or state labels;
- each formal step consumes a named input or an explicitly derived state;
- the operation direction, sign, result, counterfactual, and observable agree;
- the block adds formal precision or a falsifying check rather than repeating
  the story's prose; and
- the `non_conclusion` prevents the most tempting unsupported generalization.

Concrete domain cases belong in `tests/regression_cases.json`, not in this
production contract.
