# Evaluation: BigBirdReturns/GSK-LeanBio

Issue: [#82](https://github.com/fractastical/delphi/issues/82). Date: 2026-11-01.
Evaluated commit: `2d35f9fe64f01fa64be70af95bdf89a1bdd877d0` (2026-07-23), cloned from
<https://github.com/BigBirdReturns/GSK-LeanBio>. Apache-2.0. ~2,900 lines (Python + Lean). Authors per
`git log`: 1 human account, 6 commits by Claude, 5 by Codex; the README says so.

Role: A12 red team. Everything below was run on this machine; "not checked" means not checked.

## 1. What it is

A public response to Kim Branson's (GSK) post "we need a 'Lean for biology' ... we built it". The repo's
thesis (`docs/THESIS.md`) is that a claim borrowing the word *Lean* is undischarged until the checker is
published, and it builds the "smallest honest version" to show what that would look like:

- **BSL**, a DSL for biochemical models: species, reactions (mass-action, Michaelis–Menten, Hill),
  interval-bounded parameters with an evidence grade (`@experiment` / `@literature` / `@assumed`),
  conservation invariants, optional `steady_state` + `property flux(r) in [lo, hi]`.
- **`bsl verify`**: emits each invariant or flux band as a Lean theorem over opaque `Int` fluxes and runs
  `omega` (Lean core, no Mathlib). Refutations print omega's counterexample.
- **`bsl certify`**: a recognizer that accepts exactly one network class (two species, `A ⇌ B`, unit
  stoichiometry, mass-action, declared `A + B = M`, positive rate lower bounds), computes tight steady-state
  intervals and emits an ℝ-valued Lean theorem with an `nlinarith` proof. Anything else is refused with a
  reason and no Lean is emitted.
- **Flagship** (`lean/BslLean/ReversibleTwoSpecies.lean`): for `k1 ∈ [1,2]`, `k2 ∈ [3,4]`, any steady state
  of `A ⇌ B` with `A + B = 10` has `A ∈ [6,8]`, `B ∈ [2,4]`. Mathlib, CI-checked.

Its own `docs/limitations.md` states the ceiling plainly: proofs are about model consistency under stated
hypotheses, not about biology, and the confidence floats are placeholders.

## 2. Reproduction

| step | result |
|---|---|
| `pytest` (venv, Python 3.14, Lean 4.35 on PATH) | 45 passed |
| `bsl verify` on all 5 shipped examples | all `VERIFIED` by local `lean` (4.35.0) via `omega` |
| Flagship `ReversibleTwoSpecies.lean` | compiles, no `sorry`, against our Thompson project's Mathlib (`lake env lean`) |
| Committed generated instance `Generated/ReversibleAB.lean` | compiles; `bsl certify examples/E-reversible` regenerates it byte-identical |
| `bsl certify` on examples A and D | refused (`expected 2 species, found 4`; `expected 2 reactions, found 3`) |
| GitHub Actions `lean-flagship` | last run on `main` success (run 27971146551, 2026-06-22) |

Deviation: the repo pins `leanprover/lean4:v4.31.0` + Mathlib `v4.31.0`; I checked the Lean files against
Lean/Mathlib **v4.35.0** (already built locally) instead of downloading their pinned Mathlib. Their own CI is
the authority for the pinned version; the proof also holds four Mathlib releases later.

## 3. Red team (`redteam/`)

| test | input | expected | observed |
|---|---|---|---|
| false invariant | `false_inv.bsl` (`A = 1` with `A -> B`) | refuted | `FAILED`, counterexample `v_f ≥ 1` |
| too-tight flux band | `tight_band.bsl` (`[12,18]` for influx `[10,20]`) | refuted | `FAILED`, counterexample `10 ≤ v_efflux ≤ 11` |
| mutated flagship | `RedTeam.lean` `mutated_flagship` (`A ≤ 7`) | Lean error | one `linarith failed` error, at that theorem only |
| non-flagship certify instance | `rev_frac.bsl` (fractional intervals, `M = 7.3`) | emitted proof closes | closes; bounds `X ∈ [511/370, 73/12]` match `M·kr/(kf+kr)` at the box corners |
| **integer-abstraction gap** | `int_gap.bsl` | should be refuted | **`VERIFIED`** (see below) |
| fractional invariant coefficient | `halfcoef.bsl` (`0.5 A + 0.5 B = 0.5`) | skipped, not verified | `SKIPPED`, journal `result: "skipped"`; honest, but a true conservation law goes unchecked because the Int path cannot scale it |

### The one real finding: `bsl verify` is unsound for flux bands

`verify_emit.py` quantifies fluxes over `Int`. Fluxes are real-valued. For `int_gap.bsl` (influx fixed at
11, reaction `2 A -> B`, efflux) the true steady-state efflux is 5.5, so `flux(efflux) in [0, 0]` is false.
Over the integers `2·v_step = 11` has no solution, the hypotheses are contradictory, `omega` closes the goal
and the tool prints `VERIFIED`. `RedTeam.lean` `int_gap_false_over_reals` is the Mathlib-checked witness
`(11, 11/2, 11/2)` that the same statement is false over ℝ.

The conservation obligations are unaffected: `d/dt(c·x) = (c·N)v = 0` is a linear identity, true over `Int`
iff true over ℝ. The steady-state **band** obligations are affected whenever stoichiometry is non-unit or
the influx interval is narrow enough to leave no integer solution. `limitations.md` discloses "over the
integers" but not that this can discharge a false bound. Fix is small: emit over `ℚ`/`ℝ` and close with
`linarith` (needs Mathlib, which they already require for the flagship), or add a satisfiability check
(the hypotheses must admit a model) before reporting `VERIFIED`.

### Smaller points

- `bsl certify` prints `(kernel-checked in CI)` for every emitted instance. Only instances committed under
  `lean/BslLean/Generated/` and imported from `BslLean.lean` are checked in CI; a fresh instance is unchecked
  until then. The general schema (∀ intervals, ∀ M) is not itself a Lean theorem; each instance re-runs
  `nlinarith`, which happened to close for my fractional case but is not guaranteed to.
- `python.yml` never installs Lean, so the `omega` path is exercised in CI only as "emit a file"; the
  `needs_lean` tests skip there.
- `@init` values and evidence grades go into the claim bundle (`candidates.py`) and play no role in any
  proof; no theorem mentions an initial condition or a grade.

## 4. Is any of it a claim about biology?

No. Every theorem is of the form "these equations with these parameter boxes imply these bounds", where the
equations and boxes are hypotheses typed by the author. No organism, no dataset, no measured constant: the
flagship's `k1 ∈ [1,2]`, `k2 ∈ [3,4]` are illustrative. Nothing here is a candidate for `lean/registry/`
(no empirical constraint to map) and nothing changes a verdict in `test-data/claim-tests/`. The repo says
this itself and is right to.

Relation to our LeanBio (`pipeline/leanbio/`, `lean/registry/`): the two share a name and the word
"Lean" and nothing else. Theirs formalizes the *model* of a reaction network; ours formalizes candidate
*laws* distilled from literature, grounded to ontology ids and ordered by a belief score, and keeps the
data test (`test-data/claim-tests/`) as the thing that touches organisms. The useful prior-art point for us
is their framing: "a 'Lean for biology' certifies the model, not the biology". That is the distinction
`AGENTS.md` already draws ("a proof shows a statement follows from its assumptions, not that organisms
satisfy them").

## 5. Worth borrowing

1. **Fail-closed recognizer.** `certify` refuses with a coded reason (`UnsupportedKineticLaw`,
   `MissingConservationLaw`, `CannotProvePositiveDenominator`) rather than emitting Lean it cannot prove.
   `lean/registry/propose.mjs` could reject with equally specific codes.
2. **Counterexample on refutation.** omega's model is surfaced to the user. Our `lean_check` reports
   compile failure; printing the counterexample where a decision procedure gives one is cheap.
3. **CI asserts the artifact**: `test -f .olean` plus `grep -E '\b(sorry|admit)\b'`. Our reports record
   "no sorry"; asserting the `.olean` exists is one more line.
4. **Evidence grade on every parameter**, syntactically required. Our constraints carry a source; a
   required `assumed | literature | measured` tag per numeric constant in `lean/constraints.json` would
   make the "model vs data" boundary visible in the registry.

Not worth borrowing: the DSL (we have no reaction-network claims), the Int/omega path (unsound as shipped).

## 6. Not checked

- Their pinned Mathlib v4.31.0 build (used our v4.35.0; their CI covers the pin).
- `bsl compile` bundle output and the `GenesisEmitter` / "AXM" stub, which are explicitly placeholders.
- Whether the "Lean for biology" GSK framework referred to has since been published. That is a
  literature/news question outside this evaluation and I did not search for it.
