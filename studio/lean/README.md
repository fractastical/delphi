# lean/Admissible.lean: what it states, and what it does not

Scope: a two-species linearisation `J = ![![a,b],![c,d]]`, diffusivities `Du, Dv > 0`, zero-flux (Neumann) modes `q_n = (n pi / L)^2`. Real arithmetic only.
It is linear stability of a declared model, not a statement that a pattern forms, and nothing here is about an organism.

| theorem | states | note |
|---|---|---|
| `unstable_of_pos_eigenvalue` | negative trace + a positive root of `lam^2 - T lam + D` implies `D < 0` | **one direction**; formerly named `unstable_iff_pos_eigenvalue` |
| `exists_pos_eigenvalue_of_unstable` | `D < 0` implies a positive root exists (no trace hypothesis) | the converse |
| `unstable_iff_exists_pos_eigenvalue` | with `T < 0`: `Unstable <-> exists positive root` | the actual iff |
| `trace_hypothesis_needed` | a witness (T=3, D=2, root 1) that the trace hypothesis cannot be dropped | |
| `finite_domain_linearly_stable` | well-mixed stable and `D > 0` at every Neumann mode implies every mode has `T < 0` and `D > 0` | replaces the earlier `not_lt` theorem (see CONTRIBUTING-VERIFICATION.md) |
| `worked_not_unstable_on_pi` | on `L = pi` no mode has `D < 0` | **weaker** than stability (allows `D = 0`); formerly named `worked_stable_on_pi` |
| `worked_modeStable_on_pi` | on `L = pi` every mode is `ModeStable` (`T < 0`, `D > 0`) | instantiates `finite_domain_linearly_stable` |
| `worked_D_two_pi_one`, `worked_unstable_on_two_pi`, `worked_not_modeStable_on_two_pi` | on `L = 2 pi`, mode `n = 1` (`q = 1/4`) has `D = -1/8 < 0`: unstable, not stable | |
| `worked_growth_on_two_pi` | on `L = 2 pi` a positive real growth eigenvalue exists for mode 1 (via the iff, `T = -19/4`) | existence only; its value is not computed |

Worked system: `J = [[1,-2],[2,-3]]`, `Du = 1`, `Dv = 10`, `D(q) = (5q-1)(2q-1)`, band `1/5 < q < 1/2`. Only `L = pi` and `L = 2 pi` are stated here; other lengths in the deck's strip are exact rational arithmetic outside Lean.

## Checks
`python -m pytest -q tests/test_admissible_lean.py` (needs Lean 4.35.0 + Mathlib at `$FRONTIER_LEAN_PROJECT`, default `/data/artifacts/mathlib-probe`; skips otherwise, never reports a pass without running).
- positive: `lean/Admissible.lean` compiles (compiler exit 0, no `error`/`sorry`), 16 `#print axioms`, all standard (`propext`, `Classical.choice`, `Quot.sound`);
- negative: `lean/AdmissibleControls.lean.part` holds four FALSE mutants (wrong determinant, pi mode 1 claimed unstable, 2 pi mode 1 claimed stable, the iff without its trace hypothesis), each paired with a true twin of the same proof script; Lean must reject each mutant and no twin; the test fails if any error lies outside a mutant block;
- a `sorry` control shows the axiom print reports `sorryAx` (the build alone exits 0 with a warning);
- name check: the one-way predicate and the `non-unstable` result must not carry `iff` / `stable` names.
A clean axiom audit is necessary and not sufficient: it passed for the earlier `not_lt` theorem. The controls and the names are what pin what each statement says.
