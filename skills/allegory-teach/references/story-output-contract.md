# Story Output Contract

Use this contract for every `allegory-teach` response.

## Narrative gate

The story teaches a causal mechanism, not a loose mood or a vocabulary item.
It must expose a starting condition, a governing rule or constraint, an action,
and a consequence. If one of those cannot be mapped to evidence, choose a
different concept or use a direct explanation instead.

The story cannot paper over an unsupported transition: every consequence must
follow from a stated rule, constraint, or action. Retain one known learner
anchor when available, but do not present it as evidence of mastery.

Use three to five named story elements when possible. One element may represent
more than one technical detail only when the final mapping says so explicitly.
Do not state the concept name, standard acronym, or defining equation before
the last paragraph of the story.

## Required response shape

```markdown
## 寓言

<story; the reveal appears only at the end>

## 1. 概念名称与一句话定义

<canonical name>：<one scope-bounded, mechanism-level definition>。

## 3. 这个类比没有覆盖的边界

- <missing condition, scale, formal assumption, or competing mechanism>

## 4. 它可能误导你的地方

- <a plausible but false inference from the story, followed by the correction>

## 2. 故事元素与现实对应

| 故事元素 | 对应的现实对象（类型/作用） | 对应操作或约束 | 信息的保留/变化/丢弃（如适用） | 因果作用 |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

### 完整例子

<one worked example whose mathematical, numerical, operational, causal,
experimental, or comparative form matches the concept>
```

Keep the requested `1 -> 3 -> 4 -> 2` order even though the labels are not
numeric order. The final table must cover every causal element that carries the
story; decorative details need not be mapped. Keep the worked example inside
section 2 so it does not create a fifth numbered section.

## Truth conditions

- The one-sentence definition names the object, mechanism, and relevant
  condition or scope; it is not a synonym or an unsupported empirical claim.
- The mapping distinguishes an analogy from an identity. State uncertainty when
  source evidence does not support a one-to-one match.
- The boundary section names at least one formal or empirical limit of the
  analogy.
- The misleading section names at least one wrong prediction that a literal
  reading of the story would invite.
- The worked example starts from an explicit question or initial state, exposes
  the governing rules and meaningful transitions, reaches a bounded result,
  and states what that result does not establish.
- Mathematical notation is conditional, not preferred. If the concept does not
  need mathematics, use the smallest complete operational, causal,
  experimental, or comparative case without decorative formulas.
- If formulas are used, define every object and symbol before manipulation,
  name the rule at each meaningful transition, and include a relevant units,
  normalization, limiting-case, counterexample, or numerical check. Never
  invent a formula to make the response look rigorous.
- Cite supplied source anchors, paper blocks, or briefing titles when they are
  available, without copying raw feedback or long excerpts into the response.

## Logic-chain debrief inside the four sections

Keep the outer section order unchanged. Apply the following analysis within
those sections rather than adding a new numbered section:

- **1:** Give the canonical name and one scope-bounded, mechanism-level definition.
  Then state the problem or counterfactual that motivates the mechanism in one
  short sentence when it clarifies why the concept exists.
- **3:** Separate a model assumption, a formal identity, an approximation, and
  an empirical conclusion whenever the analogy might blur them.
- **4:** Preserve the reader's useful intuition, identify the first invalid
  inference, and correct it with the smallest counterexample or changed case
  that exposes the difference.
- **2:** Map each story element to the real object and its type/role, the
  corresponding operation or constraint, and what information is preserved,
  changed, or discarded. Then give the worked example and finish the section
  with a compact chain:
  `known anchor -> missing bridge -> mechanism -> consequence`.

When formulas are needed after the story, define every symbol and its object
type before manipulation. Name the rule used at each meaningful transition and
distinguish definitions, assumptions, identities, approximations, and derived
conclusions. Prefer the smallest complete case before generalizing.
