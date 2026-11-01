import Mathlib
import DarwinLaws.Struggle

/-!
# Darwin, *On the Origin of Species* (1859), Ch. X and XIV: geological succession

Mathematical cores of darwin1859-ch10-16 (with ch10-13), ch14-07 (with ch10-02), ch10-09
(with ch04-18) and the "gradual" half of ch10-06 (with ch10-07). The range-through
assumption used throughout is Darwin's own ch10-04: a lineage once extinct never reappears,
so its stratigraphic range is an interval.
-/

namespace DarwinLaws.Succession

open Filter Topology

/-! ### darwin1859-ch10-16 and ch10-13: faunal similarity decays with stratigraphic distance -/

/-- A fossil lineage (genus or species) with its first and last appearance, as stage indices. -/
structure Lineage where
  first : ℕ
  last : ℕ
  deriving DecidableEq

/-- The fauna of stage `t`: lineages whose range `[first, last]` covers `t`. The interval form
is darwin1859-ch10-04 (no reappearance after extinction). -/
def fauna (F : Finset Lineage) (t : ℕ) : Finset Lineage :=
  F.filter (fun L => L.first ≤ t ∧ t ≤ L.last)

/-- Lineages shared by the faunas of stages `i` and `k`. -/
def shared (F : Finset Lineage) (i k : ℕ) : Finset Lineage := fauna F i ∩ fauna F k

/-- darwin1859-ch10-16, intermediacy: anything common to two stages is present in every stage
between them, so the intermediate fauna is intermediate in character. -/
theorem shared_subset_fauna_between (F : Finset Lineage) {i j k : ℕ} (hij : i ≤ j) (hjk : j ≤ k) :
    shared F i k ⊆ fauna F j := by
  intro L hL
  simp only [shared, fauna, Finset.mem_inter, Finset.mem_filter] at hL ⊢
  exact ⟨hL.1.1, le_trans hL.1.2.1 hij, le_trans hjk hL.2.2.2⟩

/-- darwin1859-ch10-16, decay: a stage shares at least as many lineages with its neighbour `j`
as with the remoter stage `k` beyond it. -/
theorem shared_antitone_right (F : Finset Lineage) {i j k : ℕ} (hij : i ≤ j) (hjk : j ≤ k) :
    (shared F i k).card ≤ (shared F i j).card := by
  apply Finset.card_le_card
  intro L hL
  have hj := shared_subset_fauna_between F hij hjk hL
  simp only [shared, Finset.mem_inter] at hL ⊢
  exact ⟨hL.1, hj⟩

theorem shared_antitone_left (F : Finset Lineage) {i j k : ℕ} (hij : i ≤ j) (hjk : j ≤ k) :
    (shared F i k).card ≤ (shared F j k).card := by
  apply Finset.card_le_card
  intro L hL
  have hj := shared_subset_fauna_between F hij hjk hL
  simp only [shared, Finset.mem_inter] at hL ⊢
  exact ⟨hj, hL.2⟩

/-- darwin1859-ch10-13: taking `now` as the living fauna, the more ancient of two faunas
shares no more lineages with the living than the more recent one does. -/
theorem olderFauna_shares_fewer_with_living (F : Finset Lineage) {i j now : ℕ} (hij : i ≤ j)
    (hj : j ≤ now) : (shared F i now).card ≤ (shared F j now).card :=
  shared_antitone_left F hij hj

/-- Expected fraction of a stage's lineages still present `k` stages later when each lineage
persists across a stage boundary independently with probability `p` (a Markov turnover
model; the constant-rate idealisation behind the data test of ch10-16). -/
noncomputable def persistence (p : ℝ) (k : ℕ) : ℝ := p ^ k

/-- Under the Markov model expected similarity strictly decreases with separation. -/
theorem persistence_strictAnti (p : ℝ) (hp0 : 0 < p) (hp1 : p < 1) {m n : ℕ} (hmn : m < n) :
    persistence p n < persistence p m :=
  pow_lt_pow_right_of_lt_one₀ hp0 hp1 hmn

/-! ### darwin1859-ch14-07 (with ch10-02): organic change as a clock -/

/-- darwin1859-ch14-07: expected fraction of lineages that fail to persist across an interval
of duration `D` when each goes extinct at a constant hazard `μ` (Poisson extinction). -/
noncomputable def expectedTurnover (μ D : ℝ) : ℝ := 1 - Real.exp (-μ * D)

/-- Under a constant hazard, more elapsed time means strictly more turnover: the amount of
change is a monotone function of time. -/
theorem expectedTurnover_strictMono (μ : ℝ) (hμ : 0 < μ) {D₁ D₂ : ℝ} (h : D₁ < D₂) :
    expectedTurnover μ D₁ < expectedTurnover μ D₂ := by
  unfold expectedTurnover
  have : Real.exp (-μ * D₂) < Real.exp (-μ * D₁) := Real.exp_lt_exp.2 (by nlinarith)
  linarith

/-- The time read off from an observed turnover `T` under hazard `μ`. -/
noncomputable def elapsedTime (μ T : ℝ) : ℝ := -Real.log (1 - T) / μ

/-- The clock inverts exactly: turnover is a fair measure of time if the hazard is known. -/
theorem elapsedTime_expectedTurnover (μ D : ℝ) (hμ : μ ≠ 0) :
    elapsedTime μ (expectedTurnover μ D) = D := by
  unfold elapsedTime expectedTurnover
  rw [sub_sub_cancel, Real.log_exp]
  field_simp

/-- darwin1859-ch10-02 makes the clock imperfect: at the same elapsed time, a group with a
higher hazard shows strictly more turnover, so change measures time only within a group of
constant rate. -/
theorem expectedTurnover_strictMono_in_hazard (D : ℝ) (hD : 0 < D) {μ₁ μ₂ : ℝ}
    (h : μ₁ < μ₂) : expectedTurnover μ₁ D < expectedTurnover μ₂ D := by
  unfold expectedTurnover
  have : Real.exp (-μ₂ * D) < Real.exp (-μ₁ * D) := Real.exp_lt_exp.2 (by nlinarith)
  linarith

/-! ### darwin1859-ch10-09, ch04-18, ch10-06, ch10-07: gradual change passes through every
intermediate number -/

/-- Numbers change one at a time: a discrete trajectory `N` (individuals of a species, or
species of a group, per period) never falls by more than one per step. -/
def UnitStepsDown (N : ℕ → ℕ) : Prop := ∀ t, N t ≤ N (t + 1) + 1

/-- ... and never rises by more than one per step. -/
def UnitStepsUp (N : ℕ → ℕ) : Prop := ∀ t, N (t + 1) ≤ N t + 1

/-- Discrete intermediate-value property for a declining count: every number between the
later and the earlier value is attained at some intermediate period. -/
theorem exists_eq_of_unitStepsDown (N : ℕ → ℕ) (h : UnitStepsDown N) (a d m : ℕ)
    (hlo : N (a + d) ≤ m) (hhi : m ≤ N a) : ∃ t, a ≤ t ∧ t ≤ a + d ∧ N t = m := by
  induction d with
  | zero =>
    refine ⟨a, le_rfl, le_rfl, ?_⟩
    simp only [Nat.add_zero] at hlo
    omega
  | succ d ih =>
    by_cases hc : N (a + d) ≤ m
    · obtain ⟨t, h1, h2, h3⟩ := ih hc
      exact ⟨t, h1, by omega, h3⟩
    · have hstep := h (a + d)
      have hlo' : N (a + d + 1) ≤ m := hlo
      refine ⟨a + d + 1, by omega, by omega, ?_⟩
      omega

/-- Discrete intermediate-value property for a rising count. -/
theorem exists_eq_of_unitStepsUp (N : ℕ → ℕ) (h : UnitStepsUp N) (a d m : ℕ)
    (hlo : N a ≤ m) (hhi : m ≤ N (a + d)) : ∃ t, a ≤ t ∧ t ≤ a + d ∧ N t = m := by
  induction d with
  | zero =>
    refine ⟨a, le_rfl, le_rfl, ?_⟩
    simp only [Nat.add_zero] at hhi
    omega
  | succ d ih =>
    by_cases hc : m ≤ N (a + d)
    · obtain ⟨t, h1, h2, h3⟩ := ih hc
      exact ⟨t, h1, by omega, h3⟩
    · have hstep := h (a + d)
      have hhi' : m ≤ N (a + d + 1) := hhi
      refine ⟨a + d + 1, by omega, by omega, ?_⟩
      omega

/-- darwin1859-ch10-09 (and ch04-18): if a species present with `N a ≥ 1` individuals is
extinct `d` periods later and numbers fall at most one per period, then it was rare, in fact
reduced to a single individual, at some period before its extinction: rarity precedes
extinction. -/
theorem rarity_precedes_extinction (N : ℕ → ℕ) (h : UnitStepsDown N) (a d : ℕ)
    (hpresent : 1 ≤ N a) (hextinct : N (a + d) = 0) :
    ∃ t, a ≤ t ∧ t ≤ a + d ∧ N t = 1 :=
  exists_eq_of_unitStepsDown N h a d 1 (by omega) hpresent

/-- darwin1859-ch10-06 / ch10-07, the gradual half: a group that appears with one species,
reaches a maximum of `M` species, and is later extinct, passes through every species number
from `1` to `M` on the way up and from `M` down to `1` on the way down. (Unimodality of the
curve is *not* a consequence and is left to data.) -/
theorem gradual_rise_and_fall (N : ℕ → ℕ) (hup : UnitStepsUp N) (hdown : UnitStepsDown N)
    (a p e M : ℕ) (hap : a ≤ p) (hpe : p ≤ e) (hstart : N a = 1) (hpeak : N p = M)
    (hend : N e = 0) (m : ℕ) (hm1 : 1 ≤ m) (hmM : m ≤ M) :
    (∃ t, a ≤ t ∧ t ≤ p ∧ N t = m) ∧ (∃ t, p ≤ t ∧ t ≤ e ∧ N t = m) := by
  obtain ⟨d₁, rfl⟩ := Nat.exists_eq_add_of_le hap
  obtain ⟨d₂, rfl⟩ := Nat.exists_eq_add_of_le hpe
  constructor
  · exact exists_eq_of_unitStepsUp N hup a d₁ m (by omega) (by omega)
  · exact exists_eq_of_unitStepsDown N hdown (a + d₁) d₂ m (by omega) (by omega)

end DarwinLaws.Succession
