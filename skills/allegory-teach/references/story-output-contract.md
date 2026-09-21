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

Then derive the narrative background from that skeleton:

```text
world state -> actor goal -> available capability and limit -> trigger ->
observable stakes -> actor choice -> mechanism consequence
```

Select one core relation from that skeleton. If the subject contains several
mechanisms, the fable may carry only the selected relation; later mechanisms
must be taught as separate bridges with a technical-language return between
them. The preflight is not shown before the story because Fable Mode preserves
the user's requested delayed reveal.

## Immersive background gate

Begin every Fable Mode story with at least two causally necessary background
paragraphs. Two or three are usually enough, but add more when an essential
goal, capability, limit, trigger, or observable cost cannot otherwise be made
explicit. After the background, give every key mechanism transition enough
space to be reconstructed; there is no total word, paragraph, or mechanism
paragraph limit. Complete the narrative and technical spines before applying
the deletion test. Brevity may remove only decoration or repetition; it may not
remove a goal, limit, rule source, choice, state change, or consequence. A
standalone fable may reveal the name in its final story paragraph; a daily
opening must keep the name out of every narrative paragraph and reveal it in
the factual debrief, as required by its existing version-3 validator.

For a daily opening, the 2000-normalized-character limit applies to each
paragraph as a transport safety boundary, not to the whole story. Split an
overlong paragraph at a natural causal or state-transition boundary. Never
truncate, summarize away, or omit a required link merely to satisfy that limit.

Every background paragraph must perform at least one causal job:

- explain why the problem matters to the actor;
- establish a rule or capability that constrains what the actor can do;
- introduce the condition that makes the old approach fail;
- make the chosen action necessary or plausible; or
- establish an observable consequence against which success or failure can be
  judged.

Use setting, motivation, and sensory detail to make the situation immersive,
but do not confuse atmosphere with background. Apply the deletion test: remove
the paragraph and ask whether the actor's goal, available choices, reason for
acting, or consequence becomes less intelligible. If none changes, the
paragraph is decorative and must be rewritten or removed.

Fable does not mean literary, historical, ancient, dramatic, or poetic. Prefer
the simplest familiar setting that makes the actor's goal, limitation, action,
and observable consequence concrete. Atmosphere is optional; mechanism clarity
is mandatory. Do not add institutions, lore, characters, or danger merely to
make the response feel more like a story.

A technical rule must appear as a real constraint in the story world before a
character relies on it. Do not introduce a tool limitation, permission, or
failure condition only when the mechanism needs it. Stakes may be physical
loss, a wrong prediction, a failed operation, or an invalid inference, but they
must be observable and must follow from the mapped mechanism. Do not invent a
disaster merely to make the story dramatic.

The background may deepen the selected relation; it may not smuggle in a
second technical mechanism. Each background paragraph may contain narrative
texture, but the story as a whole still teaches only one core relation.

## Story-value and dual-spine gate

A fable is valid only when the story action teaches the mechanism. Reject a
draft whose characters, props, meters, cards, rooms, or machines merely rename
variables, states, vectors, operators, formulas, or omitted terms. Adding a
setting to `given values -> apply rule -> calculate -> compare` creates a worked
example, not a fable.

The narrative spine must be recoverable before the technical reveal:

```text
actor goal -> real limit or missing information -> available action or tempting
shortcut -> choice or operation -> observable consequence -> reveal
```

The technical spine must be recoverable as:

```text
technical objective -> governing-rule source -> required inputs or states ->
representation or capability limit -> changed result -> error, ambiguity, or
trade-off
```

Couple the two spines explicitly. The goal maps to the technical objective, the
story limit maps to the real limit, the action maps to the technical operation,
and the consequence maps to the result or failure. The actor must do more than
read values and report arithmetic: the constraint must make a choice, shortcut,
or changed action meaningful. Do not invent drama when the mechanism supplies
only an ordinary operational consequence.

Every mechanism-bearing story element must make at least one causal contribution:
clarify the goal, expose a limit or dependency, enable or block an action, force
a choice, change a state, or make a consequence observable. Remove a noun-only
substitution. For a standalone explicit fable, first repair the draft by
narrowing it to one relation or replacing symbol stand-ins with causal actions;
if it still adds no value over the minimum technical case, disclose the mismatch
and return to Bridge Mode. A daily opening instead follows the ranked-source
fallback in `daily-briefing-interface.md` and must still produce a valid fable.

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

## Governing-rule origin gate

A checkable story is incomplete when a reader can reproduce its arithmetic but
cannot explain why that arithmetic is the right operation. Before the first
calculation, update, transition, comparison, or replacement, state in plain
language where its governing rule comes from. A rule may come from a definition,
the original dynamics, a chain-rule step, a conservation constraint, a
measurement operation, an experimental protocol, or a declared approximation.
The story may rename objects, but it may not turn the governing rule into an
arbitrary habit of a machine, character, or institution.

Before using the rule, make this chain recoverable from the story itself:

```text
what is being tracked -> why it can change -> source of the governing rule ->
why each required input contributes -> what the limited version removes or
replaces -> observable difference
```

For a mathematical or numerical mechanism, explain the rule origin before the
first concrete calculation. If a coefficient, sign, dependency, or missing term
comes from a definition or derivation, describe that source in ordinary
language and expose the operations needed to justify the calculation. The
delayed reveal may continue to hide the concept name, standard acronym, and
defining equation; it may not hide the causal reason for the calculation.
Formal notation and the complete derivation belong in the factual debrief.

For lifted-coordinate, truncation, projection, pruning, compression, or other
approximation stories, identify the original variable or state, what every
retained or expanded quantity records, the source of the checked quantity's
update rule, why a higher-order or removed quantity contributes before the
approximation, the explicit replacement rule after it is no longer represented,
and the resulting error or observable change. A numerical run that omits any of
these causal links is merely reproducible arithmetic and must be rewritten.

For a non-mathematical mechanism, identify the real protocol, definition,
constraint, or operating rule that licenses the transition. Do not manufacture
a formula or formal derivation when the declared procedure itself is the rule
source.

For every mathematical or numerical story, run one complete minimum case in
the story body:

```text
actual input -> explicit operation -> intermediate value -> result ->
counterfactual result -> observable difference
```

The delayed reveal hides the concept name, standard acronym, and defining
equation. It does not hide operands, arithmetic rules, intermediate values,
state labels, results, or the comparison that exposes the mechanism. For a
non-mathematical mechanism, replace the numeric chain with a named object,
explicit initial state, operation, changed state, failure case, and observable
outcome; do not add decorative formulas or invented measurements.

Each mechanism paragraph must answer five questions without relying on a later
debrief: who acts, what concrete input or state they receive, what operation
they perform, what output or state follows, and how the difference is observed.
Ban undefined mechanism-bearing placeholders such as “some payment,” “this
initial value,” “positive term,” “more influence,” “higher-page effect,” or
“immediately matches.” On first use, state what the object records, its present
value or state, and how it enters the next operation.

The story body and `worked_example` use the same bounded case. Their input
values or state labels, operation direction, signs, result, counterfactual, and
observable difference must agree. The debrief may introduce formal symbols,
the defining equation, and a general form, but it must not replace the story's
case with a different one.

As a soft cognitive budget, prefer at most three mechanism-bearing story
objects and one unfamiliar story-world rule. Count only elements that carry a
technical mapping, not ordinary background nouns. Exceeding the preference is
not an automatic failure, but it requires a new compression comparison and is
allowed only when the extra element lowers total understanding cost. Give each
important element one primary technical counterpart. If limited reuse is
unavoidable, the final mapping must list every counterpart and explain where
the analogy stops; otherwise reject the draft.
Do not state the concept name, standard acronym, or defining equation before
the last paragraph of a standalone story. For a daily opening, do not place any
of them in the narrative paragraphs; the factual debrief owns the reveal.

## Causal-fidelity gate

The analogy may rename objects but must preserve the mechanism's directed
structure. Before output, verify all of the following:

- the actor's goal maps to the real technical goal;
- the available tool and its limit map to the old method and its real limit;
- the trigger maps to the difficult term, condition, or state change;
- the stated stakes follow from failure of the selected mechanism rather than
  from unrelated drama;
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

Also remove all story nouns and verify that the remaining structure can be
restated as `problem -> limit -> operation -> state change -> result`. Failure
to recover any one of these means the background or mechanism is hiding a
logical step.

## Plain-language and cognitive-compression gate

Run every Fable Mode draft through the five checks defined in `SKILL.md`:

1. **Plain-Language Gate:** reject a mechanism-bearing word that itself needs a
   definition before the action can be understood.
2. **Self-Explanation Test:** a first-time learner can describe what is moved,
   retained, connected, disconnected, copied, passed, replaced, set to zero,
   added, or compared. A metaphor-only verb such as “seal,” “freeze,” “hide,”
   or “awaken” must state its exact operation immediately or be replaced.
3. **Cognitive Compression Test:** the story must not require more independent
   objects, rules, labels, or causal transitions than its explanatory value
   earns. Arbitrary page numbers, colors, rooms, ranks, or characters may not
   duplicate an existing technical index without making the relation clearer.
4. **Literal Reconstruction Test:** after replacing story nouns with neutral
   words such as input, object, operation, removed part, replacement rule, and
   output, the complete mechanism still remains.
5. **Predicted Follow-up Test:** the likely immediate question concerns the real
   mechanism or its conditions, not the meaning of the story vocabulary.

If any test fails, use a simpler familiar action, narrow the story to one
relation, or rebuild the fable around the already prepared concrete case. Do
not try to rescue a failed analogy by adding more prose.

Whenever the mechanism removes, truncates, projects, prunes, compresses, or
approximates part of a system, state what originally contributed, what is no
longer represented, what explicit rule replaces the missing contribution, and
where the error enters. A phrase such as “close the page” or “hide the layer”
does not satisfy this requirement unless it immediately states the operation,
such as setting a named input to zero.

For quantum explanations involving measurement, explicitly separate the
pre-measurement quantum state, measurement back-action, the classical outcome,
classical communication, and any conditional quantum operation. Classical
broadcast can coordinate distant actions; it does not by itself create
entanglement or enable controllable faster-than-light signalling.

## Required response shape

```markdown
## 寓言

<story; a standalone reveal appears in the final paragraph, while a daily
opening defers the reveal to section 1>

## 1. 概念名称与一句话定义

<canonical name>：<one scope-bounded, mechanism-level definition>。

<真实问题 -> 困难项或操作 -> 目标 -> 机制主链>

## 2. 故事元素与现实对应

| 故事元素 | 对应的现实对象（类型/作用） | 对应操作或约束 | 信息的保留/变化/丢弃（如适用） | 因果作用 |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

<移除故事词后的真实机制，以及为什么这个对应关系让缺失步骤变得可见>

## 3. 这个类比没有覆盖的边界

- <missing condition, scale, formal assumption, or competing mechanism>

## 4. 它可能误导你的地方

- <a plausible but false inference from the story, followed by the correction>

## 最小检查例

<one worked example whose mathematical, numerical, operational, causal,
experimental, or comparative form matches the concept>
```

Keep the factual return in the learner's decoding order `1 -> 2 -> 3 -> 4`.
The final table must cover every causal element that carries the story;
decorative details need not be mapped. Keep the worked example unnumbered after
section 4 so it does not create a fifth factual section.

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
- In Fable Mode the story has already run that case, so the worked example adds
  formal names, symbols, rules, a compact calculation or state trace, and one
  check. It does not repeat the story in equally long prose.
- The story body already runs that same bounded case. For mathematical or
  numerical cases, a reader can reproduce its input, intermediate value,
  result, counterfactual, and difference without opening the debrief. For
  non-mathematical cases, the reader can reproduce the exact state transition
  and failure outcome without inventing missing labels.
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
- **2:** Map each story element to the real object and its type/role, the
  corresponding operation or constraint, and what information is preserved,
  changed, or discarded. For each important mapping, trace `story action ->
  technical operation -> why it is required -> preserved, changed, discarded,
  or replaced information -> observable consequence`; noun correspondences
  alone are insufficient. Then remove the story vocabulary, restate the real
  mechanism, and explain why the correspondence makes the missing bridge
  visible. Finish with `previous step -> current bridge -> next step ->
  resulting capability`.
- **3:** Separate a model assumption, a formal identity, an approximation, and
  an empirical conclusion whenever the analogy might blur them.
- **4:** Preserve the reader's useful intuition, identify the first invalid
  inference, and correct it with the smallest counterexample or changed case
  that exposes the difference.

After section 4, give the unnumbered worked example using the same bounded case.

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
