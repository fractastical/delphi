import Mathlib

namespace WolframLaws.Digits

/-! ## Neighbour-independent substitution systems -/

/-- wolfram2002-ch03-10: one step of a neighbour-independent substitution system: every element
`a` is replaced by the block `σ a`, chosen from its own colour alone. -/
def subst {α : Type*} (σ : α → List α) (w : List α) : List α := w.flatMap σ

/-- `n` steps of the substitution system `σ` started from the word `w`. -/
def substIter {α : Type*} (σ : α → List α) (n : ℕ) (w : List α) : List α := (subst σ)^[n] w

theorem substIter_append {α : Type*} (σ : α → List α) (n : ℕ) (u v : List α) :
    substIter σ n (u ++ v) = substIter σ n u ++ substIter σ n v := by
  induction n generalizing u v with
  | zero => rfl
  | succ n ih =>
    simp only [substIter, Function.iterate_succ_apply] at ih ⊢
    rw [show subst σ (u ++ v) = subst σ u ++ subst σ v by simp [subst], ih]

/-- wolfram2002-ch03-10: nesting. After `n` steps every element of the current word has grown,
independently of its neighbours, into the same block `σⁿ(a)` that a lone `a` grows into, so the
word at step `m + n` is the concatenation of copies of the step-`n` blocks, one per element of
the word at step `m`. -/
theorem substIter_nested {α : Type*} (σ : α → List α) (m n : ℕ) (w : List α) :
    substIter σ (m + n) w = (substIter σ m w).flatMap (fun a => substIter σ n [a]) := by
  have key : ∀ u : List α, substIter σ n u = u.flatMap (fun a => substIter σ n [a]) := by
    intro u
    induction u with
    | nil => induction n with
      | zero => rfl
      | succ n ih =>
        simp only [substIter, Function.iterate_succ_apply] at ih ⊢
        simpa [subst] using ih
    | cons a u ih =>
      rw [show a :: u = [a] ++ u from rfl, substIter_append, ih]
      simp
  rw [← key, substIter, substIter, Nat.add_comm, Function.iterate_add_apply]

theorem getElem?_flatMap_uniform {α : Type*} (σ : α → List α) (k : ℕ)
    (hσ : ∀ a, (σ a).length = k) (w : List α) (i j : ℕ) (hj : j < k) :
    (w.flatMap σ)[k * i + j]? = w[i]?.bind (fun b => (σ b)[j]?) := by
  induction w generalizing i with
  | nil => simp
  | cons a w ih =>
    cases i with
    | zero =>
      simp only [List.flatMap_cons, Nat.mul_zero, Nat.zero_add, List.getElem?_cons_zero,
        Option.bind_some]
      exact List.getElem?_append_left (by rw [hσ]; exact hj)
    | succ i =>
      simp only [List.flatMap_cons, List.getElem?_cons_succ]
      rw [List.getElem?_append_right (by rw [hσ]; nlinarith), hσ, ← ih i]
      congr 1
      ring_nf
      omega

/-- wolfram2002-ch03-10: for a uniform substitution (every block of length `k`), the element at
position `i` of `σⁿ(a)` is computed by reading the base-`k` digits `ds` of `i` (least significant
first) one at a time: the pattern is `k`-automatic, the formal notion of a nested sequence. -/
theorem substIter_uniform_automatic {α : Type*} (σ : α → List α) (k : ℕ)
    (hσ : ∀ a, (σ a).length = k) (a : α) (ds : List ℕ) (hds : ∀ d ∈ ds, d < k) :
    (substIter σ ds.length [a])[Nat.ofDigits k ds]? =
      ds.foldr (fun j ob => ob.bind (fun b => (σ b)[j]?)) (some a) := by
  induction ds with
  | nil => simp [substIter]
  | cons j ds ih =>
    have hj : j < k := hds j (by simp)
    have ih' := ih (fun d hd => hds d (by simp [hd]))
    simp only [List.length_cons, substIter, Function.iterate_succ_apply', Nat.ofDigits_cons,
      List.foldr_cons] at ih' ⊢
    rw [subst, Nat.add_comm, getElem?_flatMap_uniform σ k hσ _ _ _ hj, ih']

/-! ## Tag systems that delete one element per step -/

/-- wolfram2002-ch03-13: one step of a tag system that removes one element from the front of the
sequence and appends the block `σ a` determined by the removed element `a`. -/
def tagStep {α : Type*} (σ : α → List α) : List α → List α
  | [] => []
  | a :: w => w ++ σ a

theorem tagStep_iterate_append {α : Type*} (σ : α → List α) (u v : List α) :
    (tagStep σ)^[u.length] (u ++ v) = v ++ subst σ u := by
  induction u generalizing v with
  | nil => simp [subst]
  | cons a u ih =>
    rw [List.length_cons, Function.iterate_succ_apply, List.cons_append, tagStep,
      List.append_assoc, ih]
    simp [subst]

/-- wolfram2002-ch03-13: after `|w|` steps the one-deletion tag system has replaced every
element of `w`, in order, by its block: it has performed one step of the neighbour-independent
substitution `σ`. -/
theorem tagStep_cycle_eq_subst {α : Type*} (σ : α → List α) (w : List α) :
    (tagStep σ)^[w.length] w = subst σ w := by
  simpa using tagStep_iterate_append σ w []

/-- wolfram2002-ch03-13: the tag system is a slow version of the substitution system: at the
cumulative step counts `|w| + |σ(w)| + ⋯ + |σⁿ⁻¹(w)|` its sequence is exactly `σⁿ(w)`. -/
theorem tagStep_slow_subst {α : Type*} (σ : α → List α) (w : List α) (n : ℕ) :
    (tagStep σ)^[∑ i ∈ Finset.range n, (substIter σ i w).length] w = substIter σ n w := by
  induction n with
  | zero => rfl
  | succ n ih =>
    rw [Finset.sum_range_succ, Nat.add_comm, Function.iterate_add_apply, ih,
      tagStep_cycle_eq_subst, substIter, substIter, Function.iterate_succ_apply']

/-! ## Digit sequences of real numbers -/

/-- wolfram2002-ch04-14: digit `n` (counting from 0 after the point) of the base-`b` expansion
of `x`, namely `⌊bⁿ⁺¹ x⌋ mod b`. -/
def digit (b : ℕ) (x : ℝ) (n : ℕ) : ℤ := ⌊(b : ℝ) ^ (n + 1) * x⌋ % b

/-- A sequence is eventually periodic (repetitive) if from some point on it repeats with some
positive period. -/
def EventuallyPeriodic (d : ℕ → ℤ) : Prop :=
  ∃ m per, 0 < per ∧ ∀ n ≥ m, d (n + per) = d n

/-- The remainder recursion `r₀ = p`, `rₙ₊₁ = b·rₙ mod q` of long division of `p` by `q`. -/
def remainder (b p q : ℕ) : ℕ → ℕ
  | 0 => p % q
  | n + 1 => b * remainder b p q n % q

theorem remainder_eq (b p q n : ℕ) : remainder b p q n = b ^ n * p % q := by
  induction n with
  | zero => simp [remainder]
  | succ n ih => rw [remainder, ih, pow_succ, Nat.mul_mod, Nat.mod_mod, ← Nat.mul_mod,
      Nat.mul_comm (b ^ n) b, Nat.mul_assoc]

/-- Long division: digit `n` of `p/q` is `⌊b·rₙ / q⌋`, so it depends only on the remainder. -/
theorem digit_rat_eq (b p q n : ℕ) (hb : 0 < b) (hq : 0 < q) :
    digit b ((p : ℝ) / q) n = ((b * remainder b p q n / q : ℕ) : ℤ) := by
  have hfl : ⌊(b : ℝ) ^ (n + 1) * ((p : ℝ) / q)⌋ = ((b ^ (n + 1) * p / q : ℕ) : ℤ) := by
    rw [← mul_div_assoc, show ((b : ℝ) ^ (n + 1) * p) = ((b ^ (n + 1) * p : ℕ) : ℝ) by
      push_cast; ring, ← Int.natCast_floor_eq_floor (by positivity), Nat.floor_div_eq_div]
  rw [digit, hfl, remainder_eq]
  set r := b ^ n * p % q
  have hdiv : b ^ n * p = q * (b ^ n * p / q) + r := (Nat.div_add_mod _ _).symm
  have hr : r < q := Nat.mod_lt _ hq
  have hlt : b * r / q < b := by
    rw [Nat.div_lt_iff_lt_mul hq]; exact Nat.mul_lt_mul_of_pos_left hr hb
  have : b ^ (n + 1) * p / q = b * (b ^ n * p / q) + b * r / q := by
    rw [pow_succ, Nat.mul_comm (b ^ n) b, Nat.mul_assoc, hdiv, Nat.mul_add,
      ← Nat.mul_assoc, Nat.mul_comm b q, Nat.mul_assoc, Nat.add_comm,
      Nat.add_mul_div_left _ _ hq, Nat.add_comm]
  rw [this]
  push_cast
  rw [Int.add_mul_emod_self_left, Int.emod_eq_of_lt (by positivity) (by exact_mod_cast hlt)]

/-- Pigeonhole for a deterministic sequence whose values from step `n₀` on lie in a finite set. -/
theorem eventually_periodic_of_maps_to (s : ℕ → ℕ) (g : ℕ → ℕ) (hs : ∀ n, s (n + 1) = g (s n))
    (S : Finset ℕ) (n₀ : ℕ) (hS : ∀ n ≥ n₀, s n ∈ S) :
    ∃ m per, 0 < per ∧ per ≤ S.card ∧ ∀ n ≥ m, s (n + per) = s n := by
  obtain ⟨i, hi, j, hj, hij, heq⟩ := Finset.exists_ne_map_eq_of_card_lt_of_maps_to
    (s := Finset.range (S.card + 1)) (t := S) (f := fun i => s (n₀ + i)) (by simp)
    (fun i _ => hS _ (by omega))
  simp only [Finset.coe_range, Set.mem_Iio] at hi hj
  have step : ∀ a c, s (n₀ + a) = s (n₀ + c) → ∀ t, s (n₀ + a + t) = s (n₀ + c + t) := by
    intro a c h t
    induction t with
    | zero => simpa using h
    | succ t ih => rw [← Nat.add_assoc, hs, ih, ← hs, Nat.add_assoc]
  rcases Nat.lt_or_gt_of_ne hij with h | h
  · refine ⟨n₀ + i, j - i, by omega, by omega, fun n hn => ?_⟩
    have := step j i heq.symm (n - (n₀ + i))
    rw [show n₀ + j + (n - (n₀ + i)) = n + (j - i) by omega,
      show n₀ + i + (n - (n₀ + i)) = n by omega] at this
    exact this
  · refine ⟨n₀ + j, i - j, by omega, by omega, fun n hn => ?_⟩
    have := step i j heq (n - (n₀ + j))
    rw [show n₀ + i + (n - (n₀ + j)) = n + (i - j) by omega,
      show n₀ + j + (n - (n₀ + j)) = n by omega] at this
    exact this

/-- wolfram2002-ch04-14: the base-`b` digits of a rational `p/q` in `[0, 1)` are eventually
periodic with period at most `q - 1`. -/
theorem digit_rat_eventually_periodic (b p q : ℕ) (hb : 2 ≤ b) (hq : 1 < q) :
    ∃ m per, 0 < per ∧ per ≤ q - 1 ∧
      ∀ n ≥ m, digit b ((p : ℝ) / q) (n + per) = digit b ((p : ℝ) / q) n := by
  have hrec : ∀ n, remainder b p q (n + 1) = b * remainder b p q n % q := fun n => rfl
  have hlt : ∀ n, remainder b p q n < q := fun n => by
    cases n <;> exact Nat.mod_lt _ (by omega)
  have periodic_of : ∀ m per, (∀ n ≥ m, remainder b p q (n + per) = remainder b p q n) →
      ∀ n ≥ m, digit b ((p : ℝ) / q) (n + per) = digit b ((p : ℝ) / q) n := by
    intro m per h n hn
    rw [digit_rat_eq _ _ _ _ (by omega) (by omega), digit_rat_eq _ _ _ _ (by omega) (by omega),
      h n hn]
  by_cases hz : ∃ n₀, remainder b p q n₀ = 0
  · obtain ⟨n₀, hn₀⟩ := hz
    have hzero : ∀ n ≥ n₀, remainder b p q n = 0 := by
      intro n hn
      induction n, hn using Nat.le_induction with
      | base => exact hn₀
      | succ n _ ih => rw [hrec, ih]; simp
    refine ⟨n₀, 1, by omega, by omega, periodic_of n₀ 1 fun n hn => ?_⟩
    rw [hzero n hn, hzero (n + 1) (by omega)]
  · push Not at hz
    obtain ⟨m, per, hper, hle, h⟩ := eventually_periodic_of_maps_to (remainder b p q)
      (fun r => b * r % q) hrec (Finset.Ioo 0 q) 0
      (fun n _ => Finset.mem_Ioo.mpr ⟨Nat.pos_of_ne_zero (hz n), hlt n⟩)
    exact ⟨m, per, hper, by simpa using hle, periodic_of m per h⟩

theorem digit_eq_floor_fract (b : ℕ) (hb : 0 < b) (x : ℝ) (n : ℕ) :
    digit b x n = ⌊(b : ℝ) * Int.fract ((b : ℝ) ^ n * x)⌋ := by
  have hf0 := Int.fract_nonneg ((b : ℝ) ^ n * x)
  have hf1 := Int.fract_lt_one ((b : ℝ) ^ n * x)
  have hsplit : (b : ℝ) ^ (n + 1) * x =
      (b : ℝ) * Int.fract ((b : ℝ) ^ n * x) + ((b * ⌊(b : ℝ) ^ n * x⌋ : ℤ) : ℝ) := by
    push_cast
    rw [pow_succ, ← Int.self_sub_floor]; ring
  rw [digit, hsplit, Int.floor_add_intCast, Int.add_mul_emod_self_left]
  apply Int.emod_eq_of_lt (Int.floor_nonneg.mpr (by positivity))
  rw [Int.floor_lt]
  push_cast
  have : (0 : ℝ) < b := by exact_mod_cast hb
  nlinarith

theorem fract_succ (b : ℕ) (x : ℝ) (n : ℕ) :
    Int.fract ((b : ℝ) ^ (n + 1) * x) = Int.fract ((b : ℝ) * Int.fract ((b : ℝ) ^ n * x)) := by
  rw [pow_succ, show (b : ℝ) ^ n * b * x = (b : ℝ) * Int.fract ((b : ℝ) ^ n * x) +
    ((b * ⌊(b : ℝ) ^ n * x⌋ : ℤ) : ℝ) by push_cast; rw [← Int.self_sub_floor]; ring,
    Int.fract_add_intCast]

/-- wolfram2002-ch04-14 (converse): a real number whose base-`b` digit sequence is eventually
periodic is rational. -/
theorem rational_of_digit_eventually_periodic (b : ℕ) (hb : 2 ≤ b) (x : ℝ)
    (h : EventuallyPeriodic (digit b x)) : ∃ r : ℚ, x = r := by
  obtain ⟨m, per, hper, hd⟩ := h
  have hb0 : (0 : ℝ) < b := by exact_mod_cast (show 0 < b by omega)
  have hb1 : (1 : ℝ) < b := by exact_mod_cast (show 1 < b by omega)
  set y : ℕ → ℝ := fun n => Int.fract ((b : ℝ) ^ n * x)
  have hy : ∀ n, y (n + 1) = b * y n - digit b x n := by
    intro n
    simp only [y]
    rw [fract_succ, digit_eq_floor_fract b (by omega), Int.fract]
  have hgrow : ∀ t, y (m + t) - y (m + per + t) = (b : ℝ) ^ t * (y m - y (m + per)) := by
    intro t
    induction t with
    | zero => simp
    | succ t ih =>
      rw [← Nat.add_assoc, ← Nat.add_assoc, hy, hy,
        show m + per + t = (m + t) + per by omega, hd (m + t) (by omega), pow_succ]
      rw [show m + t + per = m + per + t by omega] at *
      linear_combination (b : ℝ) * ih
  have hsame : y m = y (m + per) := by
    by_contra hne
    have hpos : 0 < |y m - y (m + per)| := abs_pos.mpr (sub_ne_zero.mpr hne)
    obtain ⟨t, ht⟩ := pow_unbounded_of_one_lt (1 / |y m - y (m + per)|) hb1
    have hbound : |y (m + t) - y (m + per + t)| < 1 := by
      have := Int.fract_nonneg ((b : ℝ) ^ (m + t) * x)
      have := Int.fract_lt_one ((b : ℝ) ^ (m + t) * x)
      have := Int.fract_nonneg ((b : ℝ) ^ (m + per + t) * x)
      have := Int.fract_lt_one ((b : ℝ) ^ (m + per + t) * x)
      rw [abs_lt]; constructor <;> simp only [y] <;> linarith
    rw [hgrow, abs_mul, abs_of_pos (by positivity)] at hbound
    rw [div_lt_iff₀ hpos] at ht
    linarith
  simp only [y, Int.fract] at hsame
  have hden : (b : ℝ) ^ (m + per) - (b : ℝ) ^ m ≠ 0 := by
    have : (b : ℝ) ^ m < (b : ℝ) ^ (m + per) := pow_lt_pow_right₀ hb1 (by omega)
    linarith
  refine ⟨(⌊(b : ℝ) ^ (m + per) * x⌋ - ⌊(b : ℝ) ^ m * x⌋ : ℤ) / ((b : ℚ) ^ (m + per) - b ^ m), ?_⟩
  push_cast
  rw [eq_div_iff hden]
  linarith

/-- wolfram2002-ch04-14: for `x ∈ [0, 1)`, the base-`b` digit sequence is repetitive exactly when
`x` is rational. -/
theorem digit_eventually_periodic_iff_rational (b : ℕ) (hb : 2 ≤ b) (x : ℝ)
    (hx0 : 0 ≤ x) (hx1 : x < 1) : EventuallyPeriodic (digit b x) ↔ ∃ r : ℚ, x = r := by
  refine ⟨rational_of_digit_eventually_periodic b hb x, ?_⟩
  rintro ⟨r, rfl⟩
  have hr0 : (0 : ℚ) ≤ r := by exact_mod_cast hx0
  have hr1 : r < 1 := by exact_mod_cast hx1
  have hnum : 0 ≤ r.num := Rat.num_nonneg.mpr hr0
  have hden : 0 < r.den := r.den_pos
  have hrx : (r : ℝ) = ((r.num.toNat : ℕ) : ℝ) / ((r.den : ℕ) : ℝ) := by
    rw [Int.toNat_of_nonneg hnum |>.symm ▸ (rfl : ((r.num.toNat : ℕ) : ℝ) = _)]
    have : ((r.num.toNat : ℕ) : ℤ) = r.num := Int.toNat_of_nonneg hnum
    rw [show ((r.num.toNat : ℕ) : ℝ) = ((r.num : ℤ) : ℝ) by exact_mod_cast this]
    exact_mod_cast (Rat.num_div_den r).symm
  by_cases hq : 1 < r.den
  · obtain ⟨m, per, hper, -, h⟩ := digit_rat_eventually_periodic b r.num.toNat r.den hb hq
    exact ⟨m, per, hper, by rw [hrx]; exact h⟩
  · have hr : r = 0 := by
      have h1 : r.den = 1 := by omega
      have : (r.num : ℚ) = r := by exact_mod_cast (Rat.den_eq_one_iff r).mp h1
      have hn : r.num < 1 := by exact_mod_cast (this ▸ hr1 : (r.num : ℚ) < 1)
      have : r.num = 0 := by omega
      rw [← (Rat.den_eq_one_iff r).mp h1, this]; simp
    refine ⟨0, 1, by omega, fun n _ => ?_⟩
    simp [digit, hr]

/-! ## The shift map -/

/-- wolfram2002-ch04-19: the shift map `x ↦ 2x mod 1`. -/
noncomputable def shiftMap (x : ℝ) : ℝ := Int.fract (2 * x)

/-- wolfram2002-ch04-19: the shift map moves every binary digit one place to the left. -/
theorem digit_shiftMap (x : ℝ) (n : ℕ) : digit 2 (shiftMap x) n = digit 2 x (n + 1) := by
  rw [digit, digit, shiftMap, Int.fract,
    show ((2 : ℕ) : ℝ) ^ (n + 1) * (2 * x - ⌊2 * x⌋) =
      ((2 : ℕ) : ℝ) ^ (n + 1 + 1) * x - ((2 * (2 ^ n * ⌊2 * x⌋) : ℤ) : ℝ) by push_cast; ring,
    Int.floor_sub_intCast]
  push_cast
  omega

/-- wolfram2002-ch04-19: after `k` steps, digit `n` of the state is digit `n + k` of the initial
condition: the orbit only reads off the initial digits. -/
theorem digit_shiftMap_iterate (x : ℝ) (k n : ℕ) :
    digit 2 (shiftMap^[k] x) n = digit 2 x (n + k) := by
  induction k generalizing x with
  | zero => rfl
  | succ k ih => rw [Function.iterate_succ_apply, ih, digit_shiftMap, Nat.add_right_comm,
      Nat.add_assoc]

/-- wolfram2002-ch04-19: the shift map adds no information: two initial conditions whose binary
digits agree from position `k` on give states at step `k` with identical digit sequences. -/
theorem shiftMap_iterate_digits_determined (x x' : ℝ) (k : ℕ)
    (h : ∀ n ≥ k, digit 2 x n = digit 2 x' n) (n : ℕ) :
    digit 2 (shiftMap^[k] x) n = digit 2 (shiftMap^[k] x') n := by
  rw [digit_shiftMap_iterate, digit_shiftMap_iterate, h _ (by omega)]

/-! ## Geometric replacement rules -/

/-- wolfram2002-ch05-07: one step of a geometric replacement rule. An element is a placement
`h : P → P` of the base shape, and each element is replaced, independently of all others, by the
placements `h ∘ f` for `f` in the rule's finite or infinite set `fs` of maps (given in the
element's own frame). -/
def geomStep {P : Type*} (fs : Set (P → P)) (A : Set (P → P)) : Set (P → P) :=
  {g | ∃ h ∈ A, ∃ f ∈ fs, g = h ∘ f}

/-- The elements after `n` steps, starting from the base shape itself. -/
def geomLevel {P : Type*} (fs : Set (P → P)) (n : ℕ) : Set (P → P) := (geomStep fs)^[n] {id}

/-- The pattern after `n` steps: the union of all placed copies of the base shape `X₀`. -/
def geomPattern {P : Type*} (fs : Set (P → P)) (X₀ : Set P) (n : ℕ) : Set P :=
  ⋃ h ∈ geomLevel fs n, h '' X₀

theorem geomLevel_succ {P : Type*} (fs : Set (P → P)) (n : ℕ) :
    geomLevel fs (n + 1) = {g | ∃ f ∈ fs, ∃ h ∈ geomLevel fs n, g = f ∘ h} := by
  induction n with
  | zero =>
    ext g
    simp [geomLevel, geomStep, Function.comp_id, Function.id_comp]
  | succ n ih =>
    ext g
    rw [geomLevel, Function.iterate_succ_apply', ← geomLevel, ih]
    simp only [geomStep, geomLevel, Set.mem_setOf_eq]
    constructor
    · rintro ⟨_, ⟨f, hf, h, hh, rfl⟩, f', hf', rfl⟩
      rw [geomLevel, Function.iterate_succ_apply']
      exact ⟨f, hf, h ∘ f', ⟨h, hh, f', hf', rfl⟩, rfl⟩
    · rintro ⟨f, hf, _, hh, rfl⟩
      rw [geomLevel, Function.iterate_succ_apply'] at hh
      obtain ⟨h, hh, f', hf', rfl⟩ := hh
      exact ⟨f ∘ h, ⟨f, hf, h, hh, rfl⟩, f', hf', rfl⟩

/-- wolfram2002-ch05-07: nesting. The pattern after `n + 1` steps is the union of copies of the
pattern after `n` steps, one transformed by each map of the rule: the step-`n` patterns are the
approximants of a self-similar set, `Kₙ₊₁ = ⋃_{f ∈ fs} f(Kₙ)`. -/
theorem geomPattern_succ {P : Type*} (fs : Set (P → P)) (X₀ : Set P) (n : ℕ) :
    geomPattern fs X₀ (n + 1) = ⋃ f ∈ fs, f '' geomPattern fs X₀ n := by
  ext p
  simp only [geomPattern, geomLevel_succ, Set.mem_iUnion, Set.mem_setOf_eq, Set.mem_image,
    Set.image_iUnion]
  constructor
  · rintro ⟨_, ⟨f, hf, h, hh, rfl⟩, y, hy, rfl⟩
    exact ⟨f, hf, h, hh, h y, ⟨y, hy, rfl⟩, rfl⟩
  · rintro ⟨f, hf, h, hh, _, ⟨y, hy, rfl⟩, rfl⟩
    exact ⟨f ∘ h, ⟨f, hf, h, hh, rfl⟩, y, hy, rfl⟩

end WolframLaws.Digits
