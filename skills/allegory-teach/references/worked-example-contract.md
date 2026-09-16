# Worked Example Contract

Every complete `allegory-teach` explanation includes one worked example after
the story-to-reality mapping in section 2. Topic selection and example-form
selection are separate decisions: never prefer a concept merely because it is
easy to express with equations.

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
mathematical branch below and keep every meaningful transition inspectable.

## Common structure

Represent a daily-briefing handoff as:

```json
{
  "kind": "mathematical|numerical|operational|causal|experimental|comparative",
  "title": "例子标题",
  "question": "这个例子要回答什么",
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

**Step 4 — impose a resolution criterion.** If the chosen interference
measurement needs an order-one phase separation, write
`|\phi(t_{\mathrm{resolve}})|\sim 1`. Therefore,

```tex
t_{\mathrm{resolve}}\sim\frac{\hbar}{\Delta}.
```

This is a scale relation, not a universal equality. A specified measurement
threshold would determine the constant multiplying `\hbar/\Delta`.

**Checks.** Units give `[\hbar/\Delta]=time`. If `\Delta` doubles, the same
relative phase is reached in half the time. As `\Delta\to0`, the two phase rates
become indistinguishable in this setup and the required time scale diverges.

**Interpretation.** A smaller spectral separation makes the two modes acquire
distinguishing phase more slowly, so a phase-based discrimination or adiabatic
argument can require a longer time.

**Non-conclusion.** This calculation does not prove that every algorithm runs
in exactly `\hbar/\Delta`, that a larger gap always makes every task easier, or
that the gap alone determines dynamics. Initial-state overlap, matrix elements,
the measured observable, degeneracy, the path of a time-dependent Hamiltonian,
and the chosen error criterion can all matter.
