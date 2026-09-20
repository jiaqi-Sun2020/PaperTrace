# Worked Example Contract

Every complete `allegory-teach` explanation includes one worked example after
the relevant technical setup. In Bridge Mode, run the minimum example before
the local analogy, then reuse its objects in the mapping and formal return. In
Fable Mode, the narrative first runs the same bounded case in story language;
section 2 then places its formal worked example after the story-to-reality
mapping. Inputs or state labels, operation direction, signs, result,
counterfactual, and observable difference must agree across both surfaces.
Topic selection and example-form selection are separate decisions: never
prefer a concept merely because it is easy to express with equations.

In Bridge Mode, the minimum case normally is the required worked example. Reuse
it through the local analogy and formal return instead of inventing a second
case that increases cognitive load without testing a different necessary link.

The example must instantiate the mechanism. A second abstract explanation,
generic workflow, or list of implications is not an example. Name one bounded
scenario, supply the actual inputs or initial states used in that scenario,
identify the observable, and carry those inputs through the steps to a concrete
result. In Fable Mode, the formal block may add symbols, types, rules, and the
general form, but it may not replace the story's case with different values or
reverse the sign, direction, or comparison.

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
formal. If the selected mechanism is genuinely mathematical, use the
mathematical branch below, calculate the smallest useful instance before the
general form, and keep every meaningful transition inspectable.

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

## Fully worked mathematical branch: spectral gap

This example demonstrates the mathematical branch only. It is not a reason to
prefer spectral or equation-heavy concepts during topic selection.

**Question.** In the simplest two-level system, why does a smaller energy gap
require a longer observation time to accumulate a distinguishable relative
phase?

**Concrete scenario.** Prepare a two-level system with
`\Delta=0.2\,\mathrm{meV}` and define “distinguishable” for this minimum case as
accumulating one radian of relative phase.

**Inputs.** `\Delta=0.2\,\mathrm{meV}` is the measured energy separation;
`\hbar=0.658\,\mathrm{meV\,ps}` converts the separation into a time scale; and
`\phi_*=1\,\mathrm{rad}` is the chosen resolution threshold.

**Observable.** Record the first time at which the relative phase reaches
`\phi_*`, then repeat the calculation after doubling `\Delta`.

**Assumptions.** Let a time-independent Hamiltonian satisfy
`H|0\rangle=E_0|0\rangle` and `H|1\rangle=E_1|1\rangle`, with
`\Delta=E_1-E_0>0`. Prepare the equal superposition
`|\psi(0)\rangle=(|0\rangle+|1\rangle)/\sqrt{2}`. This isolates phase
accumulation; it does not model every gap-dependent algorithm.

**Objects.** `H` is a Hermitian operator with energy units; `|0\rangle` and
`|1\rangle` are orthonormal eigenvectors; `E_0,E_1,\Delta` are real energies;
`t` is time; and `\hbar` has energy-times-time units.

**Step 1 — apply time evolution.** By the time-independent Schrödinger rule,

```tex
|\psi(t)\rangle=e^{-iHt/\hbar}|\psi(0)\rangle
=\frac{e^{-iE_0t/\hbar}|0\rangle+e^{-iE_1t/\hbar}|1\rangle}{\sqrt{2}}.
```

Each eigenvector keeps its direction and receives the phase associated with its
own eigenvalue.

**Step 2 — remove the unobservable common phase.** Using
`E_1=E_0+\Delta`, factor out `e^{-iE_0t/\hbar}`:

```tex
|\psi(t)\rangle
=e^{-iE_0t/\hbar}
\frac{|0\rangle+e^{-i\Delta t/\hbar}|1\rangle}{\sqrt{2}}.
```

The prefactor is a global phase and does not change measurement probabilities.
The remaining phase between the two components is observable through
interference.

**Step 3 — identify the information carrier.** The relative phase is

```tex
\phi(t)=\frac{\Delta t}{\hbar}.
```

The state accumulates phase separation at rate `\Delta/\hbar`; this is the
missing bridge between an energy separation and a time scale.

**Step 4 — impose this instance's resolution criterion.** Set
`|\phi(t_{\mathrm{resolve}})|=1`. Therefore,

```tex
t_{\mathrm{resolve}}
=\frac{\hbar}{\Delta}
=\frac{0.658\,\mathrm{meV\,ps}}{0.2\,\mathrm{meV}}
=3.29\,\mathrm{ps}.
```

The equality here belongs to the explicitly chosen one-radian threshold. It is
not a universal measurement threshold.

**Result.** The one-radian threshold is reached after `3.29 ps`. If `\Delta`
doubles to `0.4 meV`, it is reached after about `1.65 ps`.

**Checks.** Units give `[\hbar/\Delta]=time`. Doubling `\Delta` halves the
computed time. As `\Delta\to0`, the two phase rates become indistinguishable in
this setup and the required time scale diverges.

**Interpretation.** A smaller spectral separation makes the two modes acquire
distinguishing phase more slowly, so a phase-based discrimination or adiabatic
argument can require a longer time.

**Non-conclusion.** This calculation does not prove that every algorithm runs
in exactly `\hbar/\Delta`, that a larger gap always makes every task easier, or
that the gap alone determines dynamics. Initial-state overlap, matrix elements,
the measured observable, degeneracy, the path of a time-dependent Hamiltonian,
and the chosen error criterion can all matter.

## Fully worked operational branch: measurement and feed-forward

This branch demonstrates a concrete example without decorative mathematics and
preserves the information-carrier distinctions highlighted by measurement.

**Question.** In a four-site chain `A-B-C-D`, what changes when the two middle
sites `B-C` are jointly measured and the result is sent to `D` for a
conditional operation?

**Concrete scenario.** Sites `A-B` and `C-D` each start with a prepared
short-range entangled pair. At the scheduled middle step, `B-C` undergo a joint
Bell-state measurement, producing the classical outcome `m_BC=1`. A classical
message carrying that outcome reaches `D`, which applies the pre-agreed
correction for outcome `1`.

**Inputs.** The initial short-range resources specify what quantum correlations
exist before measurement; the chosen measurement basis determines the possible
outcomes and back-action; the actual outcome is the classical label `m_BC=1`; and
the correction table maps outcome `1` to one operation at `D`.

**Observable.** Compare the post-protocol `A-D` correlations obtained when `D`
receives and uses `m_BC=1` with the unconditioned `A-D` state before the
classical message arrives.

**Objects.** The joint state is the quantum carrier before measurement; the
joint measurement on `B-C` is a state-changing operation; `m_BC` is a classical
outcome, not the original quantum state; the message is classical
communication; and the correction at `D` is a measurement-conditioned quantum
operation.

**Step 1 — prepare local resources.** Establish the stated short-range quantum
resources on `A-B` and `C-D`. This is a prerequisite: classical communication
alone cannot supply the missing quantum resource.

**Step 2 — jointly measure `B-C`.** Perform the specified Bell-state measurement
and record `m_BC=1`. The measurement consumes the two measured subsystems and
changes the relevant joint state; it is not a passive copy of a state that then
continues unchanged toward `D`.

**Step 3 — send the outcome.** Transmit the classical bit `1` to `D`. Before
that message arrives, `D` cannot condition a controllable action on the actual
outcome merely from its local reduced state.

**Step 4 — apply feed-forward.** `D` looks up outcome `1` in the correction
table and applies the corresponding operation. The protocol is now “local
quantum preparation → measurement with back-action → classical outcome →
classical communication → conditional quantum operation,” not the original
nearest-neighbour evolution plus a harmless side channel.

**Result.** With the stated initial resource, measurement, received outcome,
and correction, the final correlations can be reorganized across more distant
sites. Omitting the classical outcome leaves `D` with the unconditioned mixture;
omitting the initial quantum resource leaves only classically coordinated
actions.

**Checks.** Remove the initial short-range resource: broadcasting `m_BC` no
longer creates entanglement. Withhold the message: `D` cannot choose the
outcome-dependent correction. Treat the measurement as passive: the predicted
state disagrees with the actual post-measurement branch.

**Non-conclusion.** This instance does not show that measurement alone creates
long-range entanglement, that the pre-measurement quantum state survives
unchanged, or that classical outcomes enable faster-than-light controllable
communication.
