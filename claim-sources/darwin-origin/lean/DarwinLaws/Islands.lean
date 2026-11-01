import Mathlib

/-!
# Darwin, *On the Origin of Species* (1859), Ch. III, IV and XII: islands, niches and
competition

Model-dependent cores of darwin1859-ch12-04 (MacArthur–Wilson immigration–extinction
equilibrium), ch12-05 (two-state divergence/replacement chain), ch04-20 (additive
resource partition) and ch03-11 (niche overlap bounded by self-overlap).
-/

namespace DarwinLaws.Islands

/-! ### darwin1859-ch12-04: oceanic islands hold fewer species than equal continental areas -/

/-- Species richness at which immigration of absent species, `I (P − S)` from a pool of `P`
species, balances extinction `E S` (MacArthur–Wilson). -/
noncomputable def mwEquilibrium (P I E : ℝ) : ℝ := P * I / (I + E)

/-- `mwEquilibrium` is the unique balance point of immigration and extinction. -/
theorem mwEquilibrium_iff (P I E S : ℝ) (hIE : I + E ≠ 0) :
    I * (P - S) - E * S = 0 ↔ S = mwEquilibrium P I E := by
  unfold mwEquilibrium
  rw [eq_div_iff hIE]
  constructor <;> intro h <;> linarith

/-- With any extinction at all, an island holds strictly fewer species than the source pool. -/
theorem mwEquilibrium_lt_pool (P I E : ℝ) (hP : 0 < P) (hI : 0 < I) (hE : 0 < E) :
    mwEquilibrium P I E < P := by
  unfold mwEquilibrium
  rw [div_lt_iff₀ (by linarith)]
  nlinarith

/-- Richness rises strictly with the immigration rate. -/
theorem mwEquilibrium_strictMono_I (P E : ℝ) (hP : 0 < P) (hE : 0 < E) {I₁ I₂ : ℝ}
    (h0 : 0 ≤ I₁) (h : I₁ < I₂) : mwEquilibrium P I₁ E < mwEquilibrium P I₂ E := by
  unfold mwEquilibrium
  rw [div_lt_div_iff₀ (by linarith) (by linarith)]
  nlinarith [mul_pos (mul_pos hP hE) (sub_pos.mpr h)]

/-- Richness falls strictly as the extinction rate rises (smaller area, higher `E`). -/
theorem mwEquilibrium_strictAnti_E (P I : ℝ) (hP : 0 < P) (hI : 0 < I) {E₁ E₂ : ℝ}
    (h0 : 0 ≤ E₁) (h : E₁ < E₂) : mwEquilibrium P I E₂ < mwEquilibrium P I E₁ := by
  unfold mwEquilibrium
  rw [div_lt_div_iff₀ (by linarith) (by linarith)]
  nlinarith [mul_pos (mul_pos hP hI) (sub_pos.mpr h)]

/-- darwin1859-ch12-04: if immigration falls with distance from the source (`immig`
strictly antitone) then, at equal area (equal `E`), a remoter island holds strictly fewer
species; a continental area is the near limit. -/
theorem remoter_island_poorer (P E : ℝ) (hP : 0 < P) (hE : 0 < E) (immig : ℝ → ℝ)
    (hpos : ∀ d, 0 ≤ immig d) (hanti : StrictAnti immig) {d₁ d₂ : ℝ} (h : d₁ < d₂) :
    mwEquilibrium P (immig d₂) E < mwEquilibrium P (immig d₁) E :=
  mwEquilibrium_strictMono_I P E hP hE (hpos d₂) (hanti h)

/-! ### darwin1859-ch12-05: oceanic islands have a high proportion of endemic species -/

/-- Stationary fraction of endemic species when a resident non-endemic species diverges into
an endemic one at rate `σ` and an endemic is replaced or swamped by renewed immigration at
rate `m` (a two-state Markov chain on each resident lineage). -/
noncomputable def endemicFraction (σ m : ℝ) : ℝ := σ / (σ + m)

/-- `endemicFraction` is the unique balance of divergence and replacement. -/
theorem endemicFraction_iff (σ m π : ℝ) (hσm : σ + m ≠ 0) :
    σ * (1 - π) = m * π ↔ π = endemicFraction σ m := by
  unfold endemicFraction
  rw [eq_div_iff hσm]
  constructor <;> intro h <;> linarith

/-- darwin1859-ch12-05: the endemic fraction falls strictly as the replacement (immigration)
rate rises, so isolated islands, with little immigration, have a higher proportion of
endemics than connected areas. -/
theorem endemicFraction_strictAnti_m (σ : ℝ) (hσ : 0 < σ) {m₁ m₂ : ℝ} (h0 : 0 ≤ m₁)
    (h : m₁ < m₂) : endemicFraction σ m₂ < endemicFraction σ m₁ := by
  unfold endemicFraction
  rw [div_lt_div_iff₀ (by linarith) (by linarith)]
  nlinarith

/-- With immigration falling with distance, remoter islands have a higher endemic fraction. -/
theorem remoter_island_more_endemic (σ : ℝ) (hσ : 0 < σ) (immig : ℝ → ℝ)
    (hpos : ∀ d, 0 ≤ immig d) (hanti : StrictAnti immig) {d₁ d₂ : ℝ} (h : d₁ < d₂) :
    endemicFraction σ (immig d₁) < endemicFraction σ (immig d₂) :=
  endemicFraction_strictAnti_m σ hσ (hpos d₂) (hanti h)

/-! ### darwin1859-ch04-20 (with ch04-21): divergence of character maximises the life supported -/

variable {ι : Type*} [DecidableEq ι] [Fintype ι]

/-- Life supported by an assemblage whose species together use the resources (places in the
economy of nature) in `used`, when resource `i` alone can support `K i`. -/
def supportedLife (K : ι → ℝ) (used : Finset ι) : ℝ := ∑ i ∈ used, K i

/-- Resources used by a set of species with niches `niche`. -/
def resourcesUsed {σ : Type*} (niche : σ → Finset ι) (species : Finset σ) : Finset ι :=
  species.biUnion niche

/-- Using more resources never supports less life. -/
theorem supportedLife_mono (K : ι → ℝ) (hK : ∀ i, 0 ≤ K i) {A B : Finset ι} (h : A ⊆ B) :
    supportedLife K A ≤ supportedLife K B :=
  Finset.sum_le_sum_of_subset_of_nonneg h (fun i _ _ => hK i)

/-- darwin1859-ch04-20: an assemblage that leaves some resource unused supports strictly less
life than one that diversifies to use every resource; the maximum is reached exactly by full
diversification of structure. -/
theorem supportedLife_lt_of_unused (K : ι → ℝ) (hK : ∀ i, 0 < K i) (used : Finset ι)
    (hne : used ≠ Finset.univ) : supportedLife K used < supportedLife K Finset.univ := by
  obtain ⟨i, hi⟩ : ∃ i, i ∉ used := by
    by_contra hall
    exact hne (Finset.eq_univ_iff_forall.2 fun i => of_not_not fun h => hall ⟨i, h⟩)
  exact Finset.sum_lt_sum_of_subset (Finset.subset_univ used) (Finset.mem_univ i) hi (hK i)
    (fun j _ _ => (hK j).le)

/-- Adding a species whose niche includes an unused resource strictly increases the life
supported (ch04-20 as Darwin states it: diversification lets more live). -/
theorem supportedLife_increases_with_new_niche {σ : Type*} [DecidableEq σ] (K : ι → ℝ)
    (hK : ∀ i, 0 < K i) (niche : σ → Finset ι) (species : Finset σ) (s : σ) (i : ι)
    (hi : i ∈ niche s) (hnew : i ∉ resourcesUsed niche species) :
    supportedLife K (resourcesUsed niche species) <
      supportedLife K (resourcesUsed niche (insert s species)) := by
  unfold supportedLife
  apply Finset.sum_lt_sum_of_subset
    (Finset.biUnion_subset_biUnion_of_subset_left niche (Finset.subset_insert s species))
    (i := i)
  · exact Finset.mem_biUnion.2 ⟨s, Finset.mem_insert_self s species, hi⟩
  · exact hnew
  · exact hK i
  · exact fun j _ _ => (hK j).le

/-! ### darwin1859-ch03-11 (with ch03-12, ch04-21): the struggle is most severe between
members of the same species -/

/-- Normalised niche overlap (MacArthur–Levins competition coefficient) between two
utilisation vectors over the resource classes `ι`. -/
noncomputable def nicheOverlap (u v : ι → ℝ) : ℝ :=
  (∑ i, u i * v i) / (Real.sqrt (∑ i, u i ^ 2) * Real.sqrt (∑ i, v i ^ 2))

/-- A form's overlap with itself is one. -/
theorem nicheOverlap_self (u : ι → ℝ) (hu : 0 < ∑ i, u i ^ 2) : nicheOverlap u u = 1 := by
  unfold nicheOverlap
  rw [← Real.sqrt_mul hu.le, Real.sqrt_mul_self hu.le]
  have : ∑ i, u i * u i = ∑ i, u i ^ 2 := by
    apply Finset.sum_congr rfl; intro i _; ring
  rw [this, div_self hu.ne']

/-- darwin1859-ch03-11: by the Cauchy–Schwarz inequality no other form competes with a given
form as intensely as its own kind does; overlap with a different form never exceeds the
self-overlap. -/
theorem nicheOverlap_le_self (u v : ι → ℝ) (hu : 0 < ∑ i, u i ^ 2) (hv : 0 < ∑ i, v i ^ 2) :
    nicheOverlap u v ≤ nicheOverlap u u := by
  rw [nicheOverlap_self u hu]
  unfold nicheOverlap
  have hden : 0 < Real.sqrt (∑ i, u i ^ 2) * Real.sqrt (∑ i, v i ^ 2) :=
    mul_pos (Real.sqrt_pos.2 hu) (Real.sqrt_pos.2 hv)
  rw [div_le_one hden, ← Real.sqrt_mul hu.le]
  have hcs := Finset.sum_mul_sq_le_sq_mul_sq Finset.univ u v
  exact le_trans (le_abs_self _) (Real.abs_le_sqrt hcs)

end DarwinLaws.Islands
