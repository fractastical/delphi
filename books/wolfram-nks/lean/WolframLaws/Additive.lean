import Mathlib

namespace WolframLaws.Additive

/-! ### Elementary cellular automata and additive rules over `ZMod 2` -/

/-- Bi-infinite two-colour configurations, colours read as elements of `ZMod 2`. -/
abbrev Config := ℤ → ZMod 2

/-- Elementary rule `n` in Wolfram's numbering: a cell whose left, centre and right neighbours
are `l c r` gets bit `4l + 2c + r` of `n`. -/
def elementary (n : ℕ) (l c r : Bool) : Bool :=
  n.testBit (4 * l.toNat + 2 * c.toNat + r.toNat)

/-- One step of elementary rule `n` on a bi-infinite `Bool` configuration. -/
def elementaryStep (n : ℕ) (x : ℤ → Bool) : ℤ → Bool :=
  fun i => elementary n (x (i - 1)) (x i) (x (i + 1))

/-- Colour `true` (black) is `1`, `false` (white) is `0`. -/
def toZMod (b : Bool) : ZMod 2 := if b then 1 else 0

/-- A nearest-neighbour rule that is linear over `ZMod 2`. -/
def linRule (a b c : ZMod 2) (x : Config) : Config :=
  fun i => a * x (i - 1) + b * x i + c * x (i + 1)

/-- Rule 90: each cell becomes the sum mod 2 of its two neighbours. -/
def rule90 (x : Config) : Config := fun i => x (i - 1) + x (i + 1)

/-- Rule 150: each cell becomes the sum mod 2 of itself and its two neighbours. -/
def rule150 (x : Config) : Config := fun i => x (i - 1) + x i + x (i + 1)

/-- Rule 102: each cell becomes the sum mod 2 of itself and its right neighbour. -/
def rule102 (x : Config) : Config := fun i => x i + x (i + 1)

/-- Translate a configuration by `j` cells. -/
def shift (j : ℤ) (x : Config) : Config := fun i => x (i - j)

/-- A single black cell at the origin. -/
def delta : Config := fun i => if i = 0 then 1 else 0

/-- The initial condition with black cells exactly at the finite set `s`. -/
def indicator (s : Finset ℤ) : Config := fun i => if i ∈ s then 1 else 0

/-- Blow a configuration up by `2^k`: cell `j` moves to `2^k j`, all other cells are white. -/
def spread (k : ℕ) (x : Config) : Config :=
  fun i => if (2 : ℤ) ^ k ∣ i then x (i / 2 ^ k) else 0

/-- `spread` for `Bool` configurations. -/
def spreadB (k : ℕ) (x : ℤ → Bool) : ℤ → Bool :=
  fun i => if (2 : ℤ) ^ k ∣ i then x (i / 2 ^ k) else false

/-- An elementary rule is additive when its table commutes with cellwise XOR. -/
def IsAdditiveElementary (n : ℕ) : Prop :=
  ∀ l c r l' c' r' : Bool,
    elementary n (xor l l') (xor c c') (xor r r') = xor (elementary n l c r) (elementary n l' c' r')

instance : DecidablePred IsAdditiveElementary := fun n => by
  unfold IsAdditiveElementary; infer_instance

/-! ### The rule tables -/

theorem rule90_table (x : ℤ → Bool) : toZMod ∘ elementaryStep 90 x = rule90 (toZMod ∘ x) := by
  funext i
  simp only [Function.comp, elementaryStep, rule90]
  generalize x (i - 1) = l; generalize x i = c; generalize x (i + 1) = r
  revert l c r; decide

theorem rule150_table (x : ℤ → Bool) : toZMod ∘ elementaryStep 150 x = rule150 (toZMod ∘ x) := by
  funext i
  simp only [Function.comp, elementaryStep, rule150]
  generalize x (i - 1) = l; generalize x i = c; generalize x (i + 1) = r
  revert l c r; decide

theorem rule102_table (x : ℤ → Bool) : toZMod ∘ elementaryStep 102 x = rule102 (toZMod ∘ x) := by
  funext i
  simp only [Function.comp, elementaryStep, rule102]
  generalize x (i - 1) = l; generalize x i = c; generalize x (i + 1) = r
  revert l c r; decide

theorem rule90_eq_linRule : rule90 = linRule 1 0 1 := by
  funext x i; simp [rule90, linRule]

theorem rule150_eq_linRule : rule150 = linRule 1 1 1 := by
  funext x i; simp [rule150, linRule]

/-! ### General facts about linear rules -/

theorem linRule_add (a b c : ZMod 2) (x y : Config) :
    linRule a b c (x + y) = linRule a b c x + linRule a b c y := by
  funext i; simp only [linRule, Pi.add_apply]; ring

theorem linRule_iterate_add (a b c : ZMod 2) (t : ℕ) (x y : Config) :
    (linRule a b c)^[t] (x + y) = (linRule a b c)^[t] x + (linRule a b c)^[t] y := by
  induction t generalizing x y with
  | zero => rfl
  | succ t ih => simp only [Function.iterate_succ_apply, linRule_add, ih]

theorem linRule_iterate_shift (a b c : ZMod 2) (t : ℕ) (j : ℤ) (x : Config) :
    (linRule a b c)^[t] (shift j x) = shift j ((linRule a b c)^[t] x) := by
  induction t generalizing x with
  | zero => rfl
  | succ t ih =>
    rw [Function.iterate_succ_apply, Function.iterate_succ_apply, ← ih]
    congr 1
    funext i
    simp only [linRule, shift]
    rw [show i - 1 - j = i - j - 1 by ring, show i + 1 - j = i - j + 1 by ring]

theorem linRule_iterate_sum (a b c : ZMod 2) (t : ℕ) (s : Finset ℤ) (g : ℤ → Config) :
    (linRule a b c)^[t] (∑ j ∈ s, g j) = ∑ j ∈ s, (linRule a b c)^[t] (g j) :=
  map_sum (AddMonoidHom.mk' ((linRule a b c)^[t]) (linRule_iterate_add a b c t)) g s

theorem indicator_eq_sum (s : Finset ℤ) : indicator s = ∑ j ∈ s, shift j delta := by
  funext i
  rw [Finset.sum_apply]
  simp [indicator, shift, delta, sub_eq_zero]

lemma two_pow_step_aux :
    ∀ a b c p q r s u : ZMod 2,
      a * (a * p + b * q + c * r) + b * (a * q + b * r + c * s) + c * (a * r + b * s + c * u)
        = a * p + b * r + c * u := by
  decide

/-- wolfram2002-ch06-20: the `2^k`-step law of an additive nearest-neighbour rule. -/
theorem linRule_iterate_two_pow (a b c : ZMod 2) (k : ℕ) (x : Config) (i : ℤ) :
    (linRule a b c)^[2 ^ k] x i = a * x (i - 2 ^ k) + b * x i + c * x (i + 2 ^ k) := by
  induction k generalizing x i with
  | zero => simp [linRule]
  | succ k ih =>
    rw [pow_succ, mul_two, Function.iterate_add_apply]
    simp only [ih]
    rw [show (2 : ℤ) ^ (k + 1) = 2 ^ k + 2 ^ k by ring, sub_add_cancel, add_sub_cancel_right,
      sub_sub, add_assoc]
    exact two_pow_step_aux _ _ _ _ _ _ _ _

/-- wolfram2002-ch06-20: an additive rule emulates itself; `2^k` steps on a configuration blown up
by `2^k` are one step on the original. -/
theorem linRule_selfEmulation (a b c : ZMod 2) (k : ℕ) (x : Config) :
    (linRule a b c)^[2 ^ k] (spread k x) = spread k (linRule a b c x) := by
  funext i
  rw [linRule_iterate_two_pow]
  simp only [spread, linRule]
  have hp : (2 : ℤ) ^ k ≠ 0 := pow_ne_zero _ two_ne_zero
  by_cases h : (2 : ℤ) ^ k ∣ i
  · obtain ⟨j, rfl⟩ := h
    rw [show (2 : ℤ) ^ k * j - 2 ^ k = 2 ^ k * (j - 1) by ring,
      show (2 : ℤ) ^ k * j + 2 ^ k = 2 ^ k * (j + 1) by ring]
    simp [hp]
  · simp [h, dvd_sub_self_right, dvd_add_self_right]

/-! ### Rule 90 (and 150): additivity and superposition -/

/-- wolfram2002-ch06-15: rule 90 is additive. -/
theorem rule90_add (x y : Config) : rule90 (x + y) = rule90 x + rule90 y := by
  rw [rule90_eq_linRule]; exact linRule_add _ _ _ x y

/-- wolfram2002-ch06-15: the evolution from a sum of initial conditions is the sum of the
evolutions, at every time. -/
theorem rule90_iterate_add (t : ℕ) (x y : Config) :
    rule90^[t] (x + y) = rule90^[t] x + rule90^[t] y := by
  rw [rule90_eq_linRule]; exact linRule_iterate_add _ _ _ t x y

/-- wolfram2002-ch06-15: from any finite initial condition, the pattern at time `t` is the mod-2
superposition of copies of the single-cell pattern, one shifted to each initial black cell. -/
theorem rule90_superposition (x : Config) (s : Finset ℤ) (hs : ∀ i, x i ≠ 0 ↔ i ∈ s)
    (t : ℕ) (i : ℤ) : rule90^[t] x i = ∑ j ∈ s, rule90^[t] delta (i - j) := by
  have hx : x = indicator s := by
    funext i
    simp only [indicator]
    have h := hs i
    split_ifs with hi
    · have : x i ≠ 0 := h.2 hi
      revert this; generalize x i = v; revert v; decide
    · exact not_not.mp (fun h' => hi (h.1 h'))
  rw [hx, indicator_eq_sum, rule90_eq_linRule, linRule_iterate_sum, Finset.sum_apply]
  simp only [linRule_iterate_shift, shift]

/-- wolfram2002-ch06-15: the state of rule 90 at time `t` is a fixed binomial combination of the
initial condition: `x_t(i) = Σ_k C(t,k) x_0(i - t + 2k) mod 2`. -/
theorem rule90_iterate_apply (t : ℕ) (x : Config) (i : ℤ) :
    rule90^[t] x i = ∑ k ∈ Finset.range (t + 1), (t.choose k : ZMod 2) * x (i - t + 2 * k) := by
  induction t generalizing i with
  | zero => simp
  | succ t ih =>
    rw [Function.iterate_succ_apply']
    simp only [rule90]
    rw [ih, ih]
    set y : ℕ → ZMod 2 := fun k => x (i - ((t + 1 : ℕ) : ℤ) + 2 * k) with hy
    have h1 : ∀ k : ℕ, x (i - 1 - t + 2 * k) = y k := fun k => by
      simp only [hy]; congr 1; push_cast; ring
    have h2 : ∀ k : ℕ, x (i + 1 - t + 2 * k) = y (k + 1) := fun k => by
      simp only [hy]; congr 1; push_cast; ring
    have h3 : ∀ k : ℕ, x (i - ((t + 1 : ℕ) : ℤ) + 2 * k) = y k := fun k => rfl
    simp only [h1, h2, h3]
    rw [Finset.sum_range_succ' _ (t + 1)]
    simp only [Nat.choose_succ_succ, Nat.cast_add, add_mul, Finset.sum_add_distrib,
      Nat.choose_zero_right]
    rw [Finset.sum_range_succ (fun k => ((t.choose (k + 1) : ℕ) : ZMod 2) * y (k + 1)),
      Nat.choose_succ_self, Finset.sum_range_succ' (fun k => ((t.choose k : ℕ) : ZMod 2) * y k),
      Nat.choose_zero_right]
    push_cast
    ring

/-! ### Rule 90: the nested (Sierpiński / Pascal mod 2) single-cell pattern -/

/-- wolfram2002-ch06-19: the single-cell pattern of rule 90 is Pascal's triangle mod 2. -/
theorem rule90_delta_pascal (t k : ℕ) (hk : k ≤ t) :
    rule90^[t] delta ((t : ℤ) - 2 * k) = (t.choose k : ZMod 2) := by
  rw [rule90_iterate_apply, Finset.sum_eq_single k]
  · have : (t : ℤ) - 2 * k - t + 2 * k = 0 := by ring
    simp [delta, this]
  · intro b _ hb
    have : (t : ℤ) - 2 * k - t + 2 * b ≠ 0 := by omega
    simp [delta, this]
  · intro hk'
    simp only [Finset.mem_range] at hk'
    omega

/-- wolfram2002-ch06-19: outside the light cone, and on cells of the wrong parity, the single-cell
pattern of rule 90 is white. -/
theorem rule90_delta_eq_zero (t : ℕ) (i : ℤ) (h : (i + t) % 2 = 1 ∨ (t : ℤ) < i ∨ i < -t) :
    rule90^[t] delta i = 0 := by
  rw [rule90_iterate_apply]
  apply Finset.sum_eq_zero
  intro k hk
  simp only [Finset.mem_range] at hk
  have : i - t + 2 * k ≠ 0 := by omega
  simp [delta, this]

/-- wolfram2002-ch06-19: nesting. Rows `2^k + t` of the single-cell pattern are two copies of row
`t`, shifted by `∓ 2^k`. -/
theorem rule90_delta_nested (k t : ℕ) (i : ℤ) :
    rule90^[2 ^ k + t] delta i = rule90^[t] delta (i - 2 ^ k) + rule90^[t] delta (i + 2 ^ k) := by
  rw [Function.iterate_add_apply, rule90_eq_linRule, linRule_iterate_two_pow]
  simp

/-- wolfram2002-ch06-19: for `t < 2^k` the two copies in `rule90_delta_nested` do not overlap, so
rows `2^k … 2^(k+1) - 1` consist of two disjoint copies of rows `0 … 2^k - 1`. -/
theorem rule90_delta_nested_disjoint (k t : ℕ) (ht : t < 2 ^ k) (i : ℤ) :
    rule90^[t] delta (i - 2 ^ k) = 0 ∨ rule90^[t] delta (i + 2 ^ k) = 0 := by
  have ht' : (t : ℤ) < 2 ^ k := by exact_mod_cast ht
  by_cases hi : 0 ≤ i
  · right; exact rule90_delta_eq_zero t _ (Or.inr (Or.inl (by linarith)))
  · left; exact rule90_delta_eq_zero t _ (Or.inr (Or.inr (by linarith)))

/-! ### Additive elementary rules: classification and self-emulation -/

/-- wolfram2002-ch06-20: the additive elementary rules are exactly these eight. -/
theorem additive_elementary_iff (n : ℕ) (hn : n < 256) :
    IsAdditiveElementary n ↔ n ∈ ({0, 60, 90, 102, 150, 170, 204, 240} : Finset ℕ) := by
  revert n; decide

/-- wolfram2002-ch06-20: an elementary rule is additive iff it is XOR of a subset of its three
inputs. -/
theorem additive_elementary_linear (n : ℕ) (hn : n < 256) :
    IsAdditiveElementary n ↔
      ∃ α β γ : Bool, ∀ l c r : Bool, elementary n l c r = xor (xor (α && l) (β && c)) (γ && r) := by
  revert n; decide

/-- wolfram2002-ch06-20: of the eight, 0 is constant, 204 the identity, 240 and 170 shifts, and 60
is the mirror image of 102. -/
theorem additive_elementary_trivial_and_mirror :
    (∀ l c r : Bool, elementary 0 l c r = false) ∧ (∀ l c r : Bool, elementary 204 l c r = c) ∧
    (∀ l c r : Bool, elementary 240 l c r = l) ∧ (∀ l c r : Bool, elementary 170 l c r = r) ∧
    (∀ l c r : Bool, elementary 60 l c r = elementary 102 r c l) := by
  decide

/-- wolfram2002-ch06-20: rule 102 is rule 90 on a skewed lattice: on every second cell, `t` steps of
rule 90 are `t` steps of rule 102, shifted by `t` cells. -/
theorem rule90_sublattice_rule102 (t : ℕ) (x : Config) (r j : ℤ) :
    rule90^[t] x (2 * j + r + t) = rule102^[t] (fun m => x (2 * m + r)) j := by
  induction t generalizing x r with
  | zero => simp
  | succ t ih =>
    rw [Function.iterate_succ_apply, Function.iterate_succ_apply,
      show 2 * j + r + ((t + 1 : ℕ) : ℤ) = 2 * j + (r + 1) + t by push_cast; ring, ih]
    congr 1
    funext m
    simp only [rule90, rule102]
    rw [show 2 * m + (r + 1) - 1 = 2 * m + r by ring,
      show 2 * m + (r + 1) + 1 = 2 * (m + 1) + r by ring]

lemma toZMod_injective : Function.Injective toZMod := by
  intro a b; cases a <;> cases b <;> decide

lemma toZMod_iterate {F : (ℤ → Bool) → (ℤ → Bool)} {G : Config → Config}
    (h : ∀ x, toZMod ∘ F x = G (toZMod ∘ x)) (t : ℕ) (x : ℤ → Bool) :
    toZMod ∘ F^[t] x = G^[t] (toZMod ∘ x) := by
  induction t generalizing x with
  | zero => rfl
  | succ t ih => rw [Function.iterate_succ_apply, ih, h, ← Function.iterate_succ_apply]

lemma toZMod_spreadB (k : ℕ) (x : ℤ → Bool) : toZMod ∘ spreadB k x = spread k (toZMod ∘ x) := by
  funext i
  simp only [Function.comp, spreadB, spread]
  split_ifs <;> simp [toZMod]

/-- wolfram2002-ch06-20: every additive elementary rule acts on colours as a linear rule over
`ZMod 2`. -/
theorem elementaryStep_linear (n : ℕ) (hn : n < 256) (hadd : IsAdditiveElementary n) :
    ∃ a b c : ZMod 2, ∀ x, toZMod ∘ elementaryStep n x = linRule a b c (toZMod ∘ x) := by
  obtain ⟨α, β, γ, h⟩ := (additive_elementary_linear n hn).1 hadd
  refine ⟨toZMod α, toZMod β, toZMod γ, fun x => funext fun i => ?_⟩
  simp only [Function.comp, elementaryStep, linRule, h]
  generalize x (i - 1) = l; generalize x i = c; generalize x (i + 1) = r
  clear h
  revert α β γ l c r; decide

/-- wolfram2002-ch06-20: every additive elementary rule emulates itself: `2^k` steps on a
configuration blown up by `2^k` equal the blown-up result of one step. -/
theorem additive_elementary_selfEmulation (n : ℕ) (hn : n < 256) (hadd : IsAdditiveElementary n)
    (k : ℕ) (x : ℤ → Bool) :
    (elementaryStep n)^[2 ^ k] (spreadB k x) = spreadB k (elementaryStep n x) := by
  obtain ⟨a, b, c, hlin⟩ := elementaryStep_linear n hn hadd
  funext i
  apply toZMod_injective
  have hL := congrFun (toZMod_iterate hlin (2 ^ k) (spreadB k x)) i
  have hR := congrFun (toZMod_spreadB k (elementaryStep n x)) i
  simp only [Function.comp] at hL hR
  rw [hL, hR, ← Function.comp_def toZMod (spreadB k x), toZMod_spreadB, linRule_selfEmulation,
    ← hlin]

/-- wolfram2002-ch06-15: rule 22, Wolfram's contrast case, is not additive. -/
theorem rule22_not_additive : ¬ IsAdditiveElementary 22 := by decide

/-! ### Rules 90 and 150 after `2^k` steps -/

/-- wolfram2002-ch11-20: after `2^k` steps rule 90 is the superposition of two copies of the
initial condition shifted by `± 2^k`. -/
theorem rule90_iterate_two_pow (k : ℕ) (x : Config) (i : ℤ) :
    rule90^[2 ^ k] x i = x (i - 2 ^ k) + x (i + 2 ^ k) := by
  rw [rule90_eq_linRule, linRule_iterate_two_pow]; simp

/-- wolfram2002-ch11-20: after `2^k` steps rule 150 is the superposition of the initial condition
and two copies shifted by `± 2^k`. -/
theorem rule150_iterate_two_pow (k : ℕ) (x : Config) (i : ℤ) :
    rule150^[2 ^ k] x i = x (i - 2 ^ k) + x i + x (i + 2 ^ k) := by
  rw [rule150_eq_linRule, linRule_iterate_two_pow]; simp

end WolframLaws.Additive
