import Mathlib

/-!
# Darwin, *On the Origin of Species* (1859), Ch. II, IV and XIII: the tree of life

Mathematical cores of darwin1859-ch13-01 (with ch13-06, ch13-02), ch02-15 (with ch02-08,
ch02-09) and ch04-24.
-/

namespace DarwinLaws.Tree

/-! ### darwin1859-ch13-01: descent produces groups subordinate to groups -/

variable {α : Type*} [PartialOrder α]

/-- Descent as a partial order: `u ≤ w` means `u` is an ancestor of `w` (or `w` itself).
Descent is tree-like when the ancestors of any form are totally ordered — each form has a
single line of ancestry (no hybrid origin between distinct lineages). -/
def TreeLike (α : Type*) [PartialOrder α] : Prop :=
  ∀ w u v : α, u ≤ w → v ≤ w → u ≤ v ∨ v ≤ u

/-- The group (clade) founded by an ancestral form `v`: all its descendants, itself included. -/
def clade (v : α) : Set α := {w | v ≤ w}

/-- darwin1859-ch13-01: under tree-like descent any two groups are either disjoint or one is
subordinate to the other; groups are "subordinate to groups". -/
theorem clade_laminar (h : TreeLike α) (u v : α) :
    Disjoint (clade u) (clade v) ∨ clade u ⊆ clade v ∨ clade v ⊆ clade u := by
  by_cases hd : Disjoint (clade u) (clade v)
  · exact Or.inl hd
  · rw [Set.not_disjoint_iff] at hd
    obtain ⟨w, hu, hv⟩ := hd
    rcases h w u v hu hv with huv | hvu
    · exact Or.inr (Or.inr fun x hx => le_trans huv hx)
    · exact Or.inr (Or.inl fun x hx => le_trans hvu hx)

/-- The groups containing a given form are totally ordered by inclusion: species within
genera within families, and so on. -/
theorem clades_containing_chain (h : TreeLike α) (w u v : α) (hu : w ∈ clade u)
    (hv : w ∈ clade v) : clade u ⊆ clade v ∨ clade v ⊆ clade u := by
  rcases h w u v hu hv with huv | hvu
  · exact Or.inr fun x hx => le_trans huv hx
  · exact Or.inl fun x hx => le_trans hvu hx

/-- Conversely, laminarity forces tree-likeness: if the groups were nested or disjoint for
every pair, every form would have a single line of ancestry. -/
theorem treeLike_of_laminar
    (h : ∀ u v : α, Disjoint (clade u) (clade v) ∨ clade u ⊆ clade v ∨ clade v ⊆ clade u) :
    TreeLike α := by
  intro w u v hu hv
  rcases h u v with hd | huv | hvu
  · exact absurd hd (Set.not_disjoint_iff.2 ⟨w, hu, hv⟩)
  · exact Or.inr (huv (le_refl u))
  · exact Or.inl (hvu (le_refl v))

/-! ### darwin1859-ch04-24: ancestral forms lie between their descendants -/

/-- A tree metric on forms: the distance between `x` and `y` equals the sum of the distances
to their last common ancestor `a` (path-additivity on a tree). -/
def PathAdditive (d : α → α → ℝ) (lca : α → α → α) : Prop :=
  ∀ x y, d x y = d x (lca x y) + d (lca x y) y

/-- darwin1859-ch04-24: in a path-additive (tree) metric, the common ancestor of two living
groups is metrically between them — no farther from either than they are from each other —
which is what "intermediate in character" means for an extinct ancestral form. -/
theorem ancestor_between (d : α → α → ℝ) (lca : α → α → α) (hd : PathAdditive d lca)
    (hnonneg : ∀ x y, 0 ≤ d x y) (x y : α) :
    d x (lca x y) ≤ d x y ∧ d (lca x y) y ≤ d x y := by
  have h := hd x y
  constructor
  · have := hnonneg (lca x y) y
    linarith
  · have := hnonneg x (lca x y)
    linarith

/-! ### darwin1859-ch02-15 (with ch02-08, ch02-09): larger genera tend to grow larger -/

/-- Expected number of species in a genus of initial size `n₀` after time `t`, when every
species gives rise to new species at the same rate `lam` (Yule's pure-birth model, built for
exactly this claim): `n₀ e^{lam t}`. -/
noncomputable def expectedGenusSize (n₀ lam t : ℝ) : ℝ := n₀ * Real.exp (lam * t)

/-- The expected gain over a period is proportional to the current size: the species of a
large genus, being more numerous, produce more new species (Darwin's "varieties" becoming
species) than those of a small genus. -/
theorem expectedGain_proportional (n₀ lam t : ℝ) :
    expectedGenusSize n₀ lam t - n₀ = n₀ * (Real.exp (lam * t) - 1) := by
  unfold expectedGenusSize; ring

/-- Two genera with the same speciation rate keep a constant ratio of expected sizes ... -/
theorem expectedGenusSize_ratio (n₁ n₂ lam t : ℝ) (h₂ : n₂ ≠ 0) :
    expectedGenusSize n₁ lam t / expectedGenusSize n₂ lam t = n₁ / n₂ := by
  unfold expectedGenusSize
  have : Real.exp (lam * t) ≠ 0 := (Real.exp_pos _).ne'
  field_simp

/-- ... so the absolute lead of the larger genus grows strictly with time: the dominant become
more dominant. -/
theorem expectedGenusSize_gap_strictMono (n₁ n₂ lam : ℝ) (h : n₂ < n₁) (hl : 0 < lam)
    {t₁ t₂ : ℝ} (ht : t₁ < t₂) :
    expectedGenusSize n₁ lam t₁ - expectedGenusSize n₂ lam t₁ <
      expectedGenusSize n₁ lam t₂ - expectedGenusSize n₂ lam t₂ := by
  unfold expectedGenusSize
  have hexp : Real.exp (lam * t₁) < Real.exp (lam * t₂) :=
    Real.exp_lt_exp.2 (mul_lt_mul_of_pos_left ht hl)
  nlinarith [sub_pos.2 h]

end DarwinLaws.Tree
