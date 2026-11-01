# hamiltons-rule-exact-scope--claude-opus-5-5--2: synergy-game counterexamples

Artifact: `claim-sources/thompson-growth-form/lean/ThompsonLaws/HamiltonScope.lean`
(imported from `ThompsonLaws.lean`). Checked with `lake env lean`: no errors, no `sorry`; every
theorem depends only on `propext`, `Classical.choice`, `Quot.sound` (checked with `#print axioms`,
then removed).

## Model
Two-player game with payoffs C/C `b - c + d`, C/D `-c`, D/C `b`, D/D `0` (`d` = synergy). The
partner of a cooperator is a cooperator with probability `r + (1-r)p`, of a defector `(1-r)p`.
Fitness `1 + δ·payoff`; next frequency `p w_C / w̄` (deterministic replicator update).

## What the theorems say
- `payoffC_sub_payoffD`, `deltaP_eq`: `Δp = p(1-p) δ (r b - c + d(r + (1-r)p)) / w̄`, exactly.
- `generalizedHamilton`, `generalizedHamilton_neg`: for `0 < p < 1`, `δ > 0` and positive
  fitnesses, `Δp > 0` iff `r b - c + d φ > 0` and `Δp < 0` iff it is `< 0`, with
  `φ = r + (1-r)p`. This holds exactly for any `δ > 0`, not only under weak selection.
- `simpleHamilton_additive`: with `d = 0`, `Δp > 0` iff `r b > c` at every interior `p`.
- `counterexample_ruleHolds_selectedAgainst`: `b=3, c=1, r=1/2, d=-2, p=1/2, δ=1/10` gives
  `r b > c` but `Δp = -1/41`.
- `counterexample_ruleFails_selectedFor`: `b=1, c=1, r=1/2, d=2, p=1/2, δ=1/10` gives
  `r b < c` but `Δp > 0`.
- `simpleHamilton_not_sufficient` / `_not_necessary`: in this model class, `r b > c` is neither
  sufficient nor necessary for cooperators to increase.
- `frequency_flip`: `b=2, c=1, d=1, r=1/4, δ=1/10` gives `Δp < 0` at `p=1/10` and `Δp > 0` at
  `p=9/10`, so no fixed `(b, c, r)` comparison gives the direction at every frequency.

## Corrections to the approach
- The approach's form "sign = (r b - c) + d φ(r, p)" is right, with `φ = r + (1-r)p` (degree 1).
  The approach called the result "Queller's form". By hand, Queller's synergy coefficient
  `Cov(g, g g')/Var(g)` equals `φ` for this pairing model, but that identity is not proved in Lean.
- The "frequency-dependent threshold game" is the bistable regime of the same synergy game,
  not a separate threshold-game model.
- The models of van Veelen et al. 2017 and Lehmann and Keller 2006 are not used.

## What it settles, and what is left
This settles only the *parameter* reading of the rule in one standard model. With fixed game
parameters `b, c` and assortment `r`, the simple rule is exact under additivity (`d = 0`) and
fails in both directions once synergy is allowed. The synergy-corrected rule restores exactness.
This does not refute the *regression* reading (Gardner et al. 2011) and does not touch the
problem's falsifier. That needs approach 1: the Price identity and regression coefficients over a
finite population. The problem's mapping of disputed sentences to theorems is also not done.
No Lean report JSON was written: `hamilton-rule` is stated in regression form, and a
`formalized` entry would mark it `proved` from a theorem that only models its parameter reading.
`hamilton-haplodiploidy` and `hamilton-lmc` are not addressed.
