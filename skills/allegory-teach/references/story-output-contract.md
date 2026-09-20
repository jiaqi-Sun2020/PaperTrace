# Fable Mode Output Contract

Use this contract only when the user explicitly asks for an allegory, story, or
delayed reveal, or when authoring a daily-briefing opening story. Ordinary
first-contact explanations use
[bridge-mode-contract.md](bridge-mode-contract.md) instead.

## Private technical preflight

Before drafting the story, privately write the real skeleton:

```text
technical problem -> difficult term or operation -> immediate goal
known anchor -> missing bridge -> target mechanism
```

Select one core relation from that skeleton. If the subject contains several
mechanisms, the fable may carry only the selected relation; later mechanisms
must be taught as separate bridges with a technical-language return between
them. The preflight is not shown before the story because Fable Mode preserves
the user's requested delayed reveal.

## Narrative gate

The story teaches a causal mechanism, not a loose mood or a vocabulary item.
It must expose a starting condition, a governing rule or constraint, an action,
and a consequence. If one of those cannot be mapped to evidence, choose a
different concept or use a direct explanation instead.

The story cannot paper over an unsupported transition: every consequence must
follow from a stated rule, constraint, or action. Retain one known learner
anchor when available, but do not present it as evidence of mastery.

Optimize for a first encounter with the topic. Prefer an explicit small case
over a polished abstraction: show the initial state, the first operation, the
changed state, and the observable consequence before compressing them into a
general rule. A reader should not need prior field vocabulary to decode what
the characters actually did.

Use three to five named story elements when possible. Give each important
element one primary technical counterpart. If limited reuse is unavoidable,
the final mapping must list every counterpart and explain where the analogy
stops; otherwise reject the draft.
Do not state the concept name, standard acronym, or defining equation before
the last paragraph of the story.

## Causal-fidelity gate

The analogy may rename objects but must preserve the mechanism's directed
structure. Before output, verify all of the following:

- the order of events and the actor for each operation are recoverable;
- every important consequence has a visible rule or prerequisite;
- destructive or state-changing operations are not portrayed as passive,
  lossless observation;
- different carriers are not collapsed into the vague word “information”;
- the mapping states what is preserved, changed, and discarded;
- correlation, coordinated action, and stronger domain-specific relations are
  not treated as synonyms;
- after removing the story vocabulary, the real mechanism can be reconstructed
  without adding a hidden step.

The preflight must also answer two hard questions:

1. Why does this correspondence make the selected technical transition easier
   to understand?
2. After removing the story vocabulary, can the real sequence be stated with
   its actual objects, operations, state changes, prerequisites, and result?

Reject or narrow the story when either answer is missing.

For quantum explanations involving measurement, explicitly separate the
pre-measurement quantum state, measurement back-action, the classical outcome,
classical communication, and any conditional quantum operation. Classical
broadcast can coordinate distant actions; it does not by itself create
entanglement or enable controllable faster-than-light signalling.

## Required response shape

```markdown
## 寓言

<story; the reveal appears only at the end>

## 1. 概念名称与一句话定义

<canonical name>：<one scope-bounded, mechanism-level definition>。

<真实问题 -> 困难项或操作 -> 目标 -> 机制主链>

## 3. 这个类比没有覆盖的边界

- <missing condition, scale, formal assumption, or competing mechanism>

## 4. 它可能误导你的地方

- <a plausible but false inference from the story, followed by the correction>

## 2. 故事元素与现实对应

| 故事元素 | 对应的现实对象（类型/作用） | 对应操作或约束 | 信息的保留/变化/丢弃（如适用） | 因果作用 |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

<为什么这个对应关系让缺失的技术步骤变得可见>

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
  one bounded concrete scenario, named input values or states, and an observable.
  It traces those particular inputs through the governing rules and meaningful
  transitions, reaches a bounded result, and states what that result does not
  establish. Restating the general logic chain is not an example.
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
  Immediately expose the technical skeleton prepared before the story:
  `problem -> difficult term/operation -> goal -> mechanism spine`. The story
  cannot remain the only explanation.
- **3:** Separate a model assumption, a formal identity, an approximation, and
  an empirical conclusion whenever the analogy might blur them.
- **4:** Preserve the reader's useful intuition, identify the first invalid
  inference, and correct it with the smallest counterexample or changed case
  that exposes the difference.
- **2:** Map each story element to the real object and its type/role, the
  corresponding operation or constraint, and what information is preserved,
  changed, or discarded. State why the correspondence makes the missing bridge
  visible, then give the worked example and finish with:
  `previous step -> current bridge -> next step -> resulting capability`.

When formulas are needed after the story, define every symbol and its object
type before manipulation. Name the rule used at each meaningful transition and
distinguish definitions, assumptions, identities, approximations, and derived
conclusions. Prefer the smallest complete case before generalizing.

When the subject involves truncation, discretization, estimation, or modelling,
state which relation is exact, which construction is only theoretical or
infinite, what the finite implementation approximates, and where error enters.
When the response claims that something is faster, cheaper, harder, scalable,
or advantageous, name the real parameters that govern that claim rather than
letting the story carry the performance conclusion.
