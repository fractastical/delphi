import Mathlib

/-!
# Scope of the parameter reading of Hamilton's rule (two-player synergy game)

Problem `hamiltons-rule-exact-scope`, approach `hamiltons-rule-exact-scope--claude-opus-5-5--2`.
Related claim: `hamilton-rule` (math-bio-claims). That claim is stated in the *regression* form
(b, c as partial regression coefficients), which this module does not formalize. Here b, c, d are
fixed game *parameters*, so the results below concern the parameter reading of the rule only.

Model. Two types, cooperator C and defector D, at frequency `p` and `1 - p`, meet in pairs.
Payoffs to a focal individual: C vs C `b - c + d`, C vs D `-c`, D vs C `b`, D vs D `0`; `d` is the
synergy term. Assortment: a cooperator's partner is a cooperator with probability
`r + (1 - r) p`, a defector's partner with probability `(1 - r) p` (these pair frequencies are
consistent: both sides give `p (1 - p) (1 - r)` mixed pairs). Fitness is `1 + δ · payoff` and the
next generation's cooperator frequency is `p w_C / w̄` (deterministic replicator update).

The approach states that `Δp` has the sign of `(r b - c) + d φ(r, p)`. That holds with
`φ(r, p) = r + (1 - r) p`, the probability that a cooperator's partner cooperates, and it holds
exactly for any `δ > 0` with positive fitnesses, not only under weak selection. No correction of
the approach's formula was needed beyond fixing `φ`.
-/

namespace ThompsonLaws.HamiltonScope

/-- Probability that a cooperator's partner is a cooperator, under assortment `r`. -/
def partnerCoopGivenC (r p : ℝ) : ℝ := r + (1 - r) * p

/-- Probability that a defector's partner is a cooperator, under assortment `r`. -/
def partnerCoopGivenD (r p : ℝ) : ℝ := (1 - r) * p

/-- Expected payoff of a cooperator: `R = b - c + d` against C, `-c` against D. -/
def payoffC (b c d r p : ℝ) : ℝ :=
  partnerCoopGivenC r p * (b - c + d) + (1 - partnerCoopGivenC r p) * (-c)

/-- Expected payoff of a defector: `b` against C, `0` against D. -/
def payoffD (b r p : ℝ) : ℝ :=
  partnerCoopGivenD r p * b + (1 - partnerCoopGivenD r p) * 0

/-- Fitness of a cooperator, `1 + δ π_C`. -/
def fitC (b c d r p δ : ℝ) : ℝ := 1 + δ * payoffC b c d r p

/-- Fitness of a defector, `1 + δ π_D`. -/
def fitD (b r p δ : ℝ) : ℝ := 1 + δ * payoffD b r p

/-- Mean fitness `w̄ = p w_C + (1 - p) w_D`. -/
def meanFitness (b c d r p δ : ℝ) : ℝ :=
  p * fitC b c d r p δ + (1 - p) * fitD b r p δ

/-- Change in cooperator frequency over one generation, `p w_C / w̄ - p`. -/
def deltaP (b c d r p δ : ℝ) : ℝ :=
  p * fitC b c d r p δ / meanFitness b c d r p δ - p

/-- The synergy-corrected inclusive-fitness quantity `r b - c + d (r + (1 - r) p)`. -/
def synergyHamilton (b c d r p : ℝ) : ℝ :=
  r * b - c + d * partnerCoopGivenC r p

/-- hamilton-rule (parameter reading, synergy game): the payoff gap between cooperators and
defectors is exactly `r b - c + d (r + (1 - r) p)`. -/
theorem payoffC_sub_payoffD (b c d r p : ℝ) :
    payoffC b c d r p - payoffD b r p = synergyHamilton b c d r p := by
  unfold payoffC payoffD synergyHamilton partnerCoopGivenC partnerCoopGivenD
  ring

/-- hamilton-rule (parameter reading, synergy game): closed form of the frequency change,
`Δp = p (1 - p) δ (r b - c + d φ) / w̄`. -/
theorem deltaP_eq (b c d r p δ : ℝ) (hw : meanFitness b c d r p δ ≠ 0) :
    deltaP b c d r p δ =
      p * (1 - p) * δ * synergyHamilton b c d r p / meanFitness b c d r p δ := by
  rw [← payoffC_sub_payoffD]
  unfold deltaP
  rw [div_sub' hw]
  congr 1
  unfold meanFitness fitC fitD
  ring

theorem meanFitness_pos (b c d r p δ : ℝ) (hp0 : 0 < p) (hp1 : p < 1)
    (hC : 0 < fitC b c d r p δ) (hD : 0 < fitD b r p δ) :
    0 < meanFitness b c d r p δ := by
  unfold meanFitness
  have : 0 < 1 - p := by linarith
  positivity

/-- hamilton-rule (parameter reading, synergy game): generalized Hamilton's rule with synergy
correction. For an interior frequency, `δ > 0` and positive fitnesses, cooperators increase
exactly when `r b - c + d (r + (1 - r) p) > 0`. -/
theorem generalizedHamilton (b c d r p δ : ℝ) (hp0 : 0 < p) (hp1 : p < 1) (hδ : 0 < δ)
    (hC : 0 < fitC b c d r p δ) (hD : 0 < fitD b r p δ) :
    0 < deltaP b c d r p δ ↔ 0 < synergyHamilton b c d r p := by
  have hw := meanFitness_pos b c d r p δ hp0 hp1 hC hD
  have hK : 0 < p * (1 - p) * δ := by
    have : 0 < 1 - p := by linarith
    positivity
  rw [deltaP_eq b c d r p δ hw.ne', div_pos_iff_of_pos_right hw, mul_pos_iff_of_pos_left hK]

/-- hamilton-rule (parameter reading, synergy game): the same rule for selection against
cooperation: `Δp < 0` exactly when `r b - c + d (r + (1 - r) p) < 0`. -/
theorem generalizedHamilton_neg (b c d r p δ : ℝ) (hp0 : 0 < p) (hp1 : p < 1) (hδ : 0 < δ)
    (hC : 0 < fitC b c d r p δ) (hD : 0 < fitD b r p δ) :
    deltaP b c d r p δ < 0 ↔ synergyHamilton b c d r p < 0 := by
  have hw := meanFitness_pos b c d r p δ hp0 hp1 hC hD
  have hK : 0 < p * (1 - p) * δ := by
    have : 0 < 1 - p := by linarith
    positivity
  rw [deltaP_eq b c d r p δ hw.ne', div_neg_iff]
  constructor
  · rintro (⟨h1, h2⟩ | ⟨h1, h2⟩)
    · exact absurd h2 (not_lt.mpr hw.le)
    · by_contra h
      exact absurd h1 (not_lt.mpr (mul_nonneg hK.le (not_lt.mp h)))
  · intro h
    exact Or.inr ⟨mul_neg_of_pos_of_neg hK h, hw⟩

/-- hamilton-rule (parameter reading): without synergy (`d = 0`, additive payoffs) the simple
rule is exact at every interior frequency: cooperators increase iff `r b > c`. -/
theorem simpleHamilton_additive (b c r p δ : ℝ) (hp0 : 0 < p) (hp1 : p < 1) (hδ : 0 < δ)
    (hC : 0 < fitC b c 0 r p δ) (hD : 0 < fitD b r p δ) :
    0 < deltaP b c 0 r p δ ↔ c < r * b := by
  rw [generalizedHamilton b c 0 r p δ hp0 hp1 hδ hC hD]
  unfold synergyHamilton
  constructor <;> intro h <;> linarith

/-- hamilton-rule, scope (iii): `r b > c` yet cooperation is selected against.
`b = 3, c = 1, r = 1/2` (so `r b - c = 1/2`), discounting synergy `d = -2`, `p = 1/2`, `δ = 1/10`:
both fitnesses are positive and `Δp = -1/41`. -/
theorem counterexample_ruleHolds_selectedAgainst :
    (1 : ℝ) < 1 / 2 * 3 ∧
      0 < fitC 3 1 (-2) (1 / 2) (1 / 2) (1 / 10) ∧ 0 < fitD 3 (1 / 2) (1 / 2) (1 / 10) ∧
      deltaP 3 1 (-2) (1 / 2) (1 / 2) (1 / 10) = -1 / 41 := by
  norm_num [deltaP, meanFitness, fitC, fitD, payoffC, payoffD, partnerCoopGivenC,
    partnerCoopGivenD]

/-- hamilton-rule, scope (iii), reverse direction: `r b < c` yet cooperation is favoured.
`b = 1, c = 1, r = 1/2` (so `r b - c = -1/2`), synergy `d = 2`, `p = 1/2`, `δ = 1/10`:
both fitnesses are positive and `Δp > 0`. -/
theorem counterexample_ruleFails_selectedFor :
    (1 / 2 : ℝ) * 1 < 1 ∧
      0 < fitC 1 1 2 (1 / 2) (1 / 2) (1 / 10) ∧ 0 < fitD 1 (1 / 2) (1 / 2) (1 / 10) ∧
      0 < deltaP 1 1 2 (1 / 2) (1 / 2) (1 / 10) := by
  norm_num [deltaP, meanFitness, fitC, fitD, payoffC, payoffD, partnerCoopGivenC,
    partnerCoopGivenD]

/-- hamilton-rule, scope (iii): with synergy allowed, `r b > c` is not sufficient for
cooperators to increase in this model, even with interior `p`, `δ > 0` and positive fitnesses. -/
theorem simpleHamilton_not_sufficient :
    ¬ ∀ b c d r p δ : ℝ, 0 < p → p < 1 → 0 < δ → 0 < fitC b c d r p δ → 0 < fitD b r p δ →
      c < r * b → 0 < deltaP b c d r p δ := by
  intro h
  obtain ⟨hrule, hC, hD, hneg⟩ := counterexample_ruleHolds_selectedAgainst
  have := h 3 1 (-2) (1 / 2) (1 / 2) (1 / 10) (by norm_num) (by norm_num) (by norm_num) hC hD hrule
  linarith

/-- hamilton-rule, scope (iii): with synergy allowed, `r b > c` is not necessary for
cooperators to increase in this model. -/
theorem simpleHamilton_not_necessary :
    ¬ ∀ b c d r p δ : ℝ, 0 < p → p < 1 → 0 < δ → 0 < fitC b c d r p δ → 0 < fitD b r p δ →
      0 < deltaP b c d r p δ → c < r * b := by
  intro h
  obtain ⟨hrule, hC, hD, hpos⟩ := counterexample_ruleFails_selectedFor
  have := h 1 1 2 (1 / 2) (1 / 2) (1 / 10) (by norm_num) (by norm_num) (by norm_num) hC hD hpos
  linarith

/-- hamilton-rule, scope (iii): frequency dependence at fixed parameters. With
`b = 2, c = 1, d = 1, r = 1/4` (`r b < c`) and `δ = 1/10`, cooperation is selected against at
`p = 1/10` and selected for at `p = 9/10`, so no fixed `(b, c, r)` comparison gives the direction
at every frequency. This is the bistable regime of the same synergy game, not a separate
threshold-game model. -/
theorem frequency_flip :
    (1 / 4 : ℝ) * 2 < 1 ∧
      0 < fitC 2 1 1 (1 / 4) (1 / 10) (1 / 10) ∧ 0 < fitD 2 (1 / 4) (1 / 10) (1 / 10) ∧
      deltaP 2 1 1 (1 / 4) (1 / 10) (1 / 10) < 0 ∧
      0 < fitC 2 1 1 (1 / 4) (9 / 10) (1 / 10) ∧ 0 < fitD 2 (1 / 4) (9 / 10) (1 / 10) ∧
      0 < deltaP 2 1 1 (1 / 4) (9 / 10) (1 / 10) := by
  norm_num [deltaP, meanFitness, fitC, fitD, payoffC, payoffD, partnerCoopGivenC,
    partnerCoopGivenD]

end ThompsonLaws.HamiltonScope

#print axioms ThompsonLaws.HamiltonScope.payoffC_sub_payoffD

#print axioms ThompsonLaws.HamiltonScope.deltaP_eq

#print axioms ThompsonLaws.HamiltonScope.meanFitness_pos

#print axioms ThompsonLaws.HamiltonScope.generalizedHamilton

#print axioms ThompsonLaws.HamiltonScope.generalizedHamilton_neg

#print axioms ThompsonLaws.HamiltonScope.simpleHamilton_additive

#print axioms ThompsonLaws.HamiltonScope.counterexample_ruleHolds_selectedAgainst

#print axioms ThompsonLaws.HamiltonScope.counterexample_ruleFails_selectedFor

#print axioms ThompsonLaws.HamiltonScope.simpleHamilton_not_sufficient

#print axioms ThompsonLaws.HamiltonScope.simpleHamilton_not_necessary

#print axioms ThompsonLaws.HamiltonScope.frequency_flip
