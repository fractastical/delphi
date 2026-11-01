# Lean for biology: what a proof here does and does not say
Date: 2026-11-01
Summary: Five small families of Lean 4 mathematics sit under the flying-fish design. Here is why we wrote them, what makes a proof count, and the three things Lean cannot tell you.

A biology paper states a law in prose and fits a few numbers. A design then reuses that law in a setting the authors never tested: another organism, another size, another unit system. Most of the failures we worry about are not arithmetic mistakes. They are a quantity read in the wrong unit, a hypothesis nobody wrote down, or a bound that is quietly false outside the range it was fitted on.

Lean is a proof assistant. It accepts a theorem only if every step is checked by a small trusted kernel. We use it as the foundation of the project because it forces three things that prose does not: **every symbol has a type, every assumption is written as a hypothesis, and the claim is true for all values that satisfy those hypotheses**, not just the ones we plotted.

## What is on the Lean proofs page

Five families, compiled with Lean 4.35.0 and a pinned Mathlib revision. Each one is a few dozen lines, readable in a sitting.

| Family | The idea in one line |
|---|---|
| Geometric similarity | Scale a fish by a length ratio *k*: wing loading scales as *k*, level-flight speed as the square root of *k*. |
| Unit algebra | Units are tracked as dimensions, so conversions and interval mappings are checked rather than assumed. |
| Cantilever guard | A small-deflection bound for a fin ray, together with a proof that its hypotheses can be satisfied at all. |
| Oxygen transport | Center-content bounds for a sphere and a slab with steady diffusion and uptake. |
| Scaled threshold intervals | Recorded intervals from a scaled simulation are shown incompatible with a factor-of-two band over a fixed horizon. |

Across the five there are 37 definitions and theorems. The positive runs that compile them exit 0, and use only Lean's standard axioms (`propext`, `Quot.sound`, `Classical.choice`) where we recorded them.

## What makes a proof count

An easy way to look rigorous is to prove something empty. A theorem can compile because its hypotheses contradict each other, because it never mentions a model parameter, or because it reduces to a calculation on constants. We call that a vacuous proof and we do not count it. Three checks apply:

1. **The theorem must mention the model's actual parameters.** A statement about wing loading has to contain mass, area and speed.
2. **It must fail when the law is changed.** For each family we wrote mutated copies, for example a wrong exponent or a flipped inequality, and ran them through Lean. All 17 mutated blocks across the five families were rejected. If a mutant had compiled, the original statement would not have been pinning down the law.
3. **The hypotheses must be satisfiable.** The cantilever guard includes a theorem exhibiting values that meet its conditions, so the bound cannot hold only because nothing satisfies it.

Each family also carries a receipt: the exit codes, the axioms used and a hash of every input file. If a file changes after the receipt was written, the site marks the family as stale and withholds the source rather than showing a result that no longer matches.

## What Lean cannot tell you

This is the part we most want a reader to take away.

- **That the statement describes a fish.** Lean checks the mathematics of the statement. Whether wing loading is the right quantity for a flying fish is a biological and engineering judgement.
- **That a parameter is correct.** The oxygen family proves a bound given a diffusion coefficient and an uptake rate. It does not supply measured values for any cell type, and says so.
- **That the Lean text matches its source.** Fidelity between a paper's sentence and the formal statement is a separate review, and we label it as one.

## Why it is the foundation

A proved law is a small reusable unit with its conditions attached. Two projects that both need steady oxygen transport can point at the same theorem and the same stated assumptions, and a constraint solver can use the same inequalities. When the solver reports a conflict, for example that no design satisfies a lift condition together with a wing-loading ceiling and a speed cap, the conflict certificate is itself checked by Lean, and a certificate with one number changed is rejected.

That is the sense in which "Lean for biology" is more than formalising a handful of equations. The goal is a shared, growing base of laws whose scope is explicit, so that generation, design and experiment planning can build on statements that have been checked rather than recalled.

[Open the Lean proofs page](#/proofs) to read the source, the receipts and each rejected mutant.
