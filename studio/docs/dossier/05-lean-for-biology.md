# Lean for biology — the formal core

Live page: https://frontier.morphoswarm.ai/#/proofs

Toolchain: **Lean 4.35.0**, pinned Mathlib revision, recorded runs. The site does not run
Lean; it shows receipts of runs, and a family whose files changed since its receipt is
marked **stale** and its source is withheld rather than shown as compiled.

## The five families

| Family | What it states | Statements | Mutants rejected |
|---|---|---|---|
| Geometric similarity | Scale a fish by length ratio *k*: wing loading scales as *k*, level-flight proxy speed as sqrt(*k*) | 9 | 4 of 4 |
| Unit algebra | Units tracked as dimensions; conversions and interval mappings are checked | 7 | 4 of 4 |
| Cantilever guard | A small-deflection bound for a fin ray, **plus** a proof its hypotheses are satisfiable | 3 | 1 of 1 |
| Oxygen transport | Centre-content bounds for a sphere and a slab under steady diffusion with uptake | 8 | 4 of 4 |
| Scaled threshold intervals | Two recorded simulation intervals shown incompatible with a factor-of-two band over a fixed horizon | 10 | 4 of 4 |

**Totals: 37 definitions and theorems, 17 of 17 mutants rejected, all five families
`current`** (receipt matches the current files). Positive runs exit 0 using only Lean's
three standard logical axioms (`propext`, `Quot.sound`, `Classical.choice`); negative runs
exit 1, which is the required result.

## What makes a proof count here

A theorem can compile and still be worthless: its hypotheses may contradict each other, it
may never mention a model parameter, or it may reduce to arithmetic on constants. We call
that a vacuous proof and do not count it. Three checks:

1. **It must mention the model's actual parameters.** A wing-loading theorem must contain
   mass, area and speed.
2. **It must fail when the law is changed.** For each family we wrote deliberately wrong
   versions — a wrong exponent, a flipped inequality — and ran them through Lean. All 17
   were rejected. This is a small hand-written set; it shows sensitivity to the mutations
   we thought of, and it is **not** a coverage measure.
3. **Its hypotheses must be satisfiable.** The cantilever family includes a theorem
   exhibiting values that meet its conditions, so the bound cannot hold vacuously.

## The solver bridge

The constraint solver reported `unsat` on a conflict between a level-flight lift proxy, a
minimum wing loading and a maximum speed. It emitted a **conflict certificate**, which was
compiled inside the positive Lean run. The site also shows the same certificate with the
speed cap changed from 10 to 20 — Lean rejects it. This is the hand-off from numerical
search to mechanical proof, shown line by line rather than asserted.

## What Lean does not tell you — stated on the page itself

- **That a statement describes a fish.** Lean checks mathematics, not modelling choices.
- **That a parameter is correct.** The oxygen family proves a bound *given* a diffusion
  coefficient and an uptake rate; no cell-specific value, boundary condition, viability
  threshold or tissue calibration is supplied for any project.
- **That the Lean text is faithful to a source passage.** That is a separate review.
- **Anything empirical.** No organism viability, no genotype-to-fin link.
- The oxygen family's spherical limit comes from a tumour-spheroid source context; its
  fitted values are **not** transferred to this project.
- A negative continuation beyond the diffusion limit is an out-of-domain model diagnostic,
  not physical negative oxygen.

## Why this is the base, not a decoration

A proved law is a small reusable unit with its conditions attached. Two projects needing
steady oxygen transport can point at the same theorem and the same stated assumptions.
The contextual-reuse block on the page shows exact project-version links for one shared
model rule, with the parameters that remain unknown listed beside it — reuse without
pretending the parameters came along.
