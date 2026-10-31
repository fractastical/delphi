import Mathlib

/-!
# Wolfram, *A New Kind of Science* (2002), chapter 12: multiway systems as axiom systems

A multiway system rewrites substrings of a string by any of its rules; the strings derivable
from a start string `tru` ("true") are its theorems. Negation is a length-preserving involution
on strings. We prove Wolfram's counting criterion for completeness and consistency (and that
it only holds in one direction), and that an undecidable derivability question forces
incompleteness or inconsistency.
-/

namespace WolframLaws.Logic

variable {α : Type*}

/-! ## Multiway systems -/

/-- A multiway (string rewriting) system: a list of rules `lhs → rhs`. -/
structure Multiway (α : Type*) where
  rules : List (List α × List α)

/-- One step: replace one occurrence of the left side of some rule by its right side. -/
def Multiway.Step (m : Multiway α) (s t : List α) : Prop :=
  ∃ r ∈ m.rules, ∃ u v : List α, s = u ++ r.1 ++ v ∧ t = u ++ r.2 ++ v

/-- `s` is a theorem: it is reached from the string `tru` in finitely many steps. -/
def Multiway.Derives (m : Multiway α) (tru : List α) : List α → Prop :=
  Relation.ReflTransGen m.Step tru

/-- No string is derivable together with its negation. -/
def Consistent (m : Multiway α) (tru : List α) (neg : List α → List α) : Prop :=
  ∀ s, ¬ (m.Derives tru s ∧ m.Derives tru (neg s))

/-- Every string or its negation is derivable. -/
def Complete (m : Multiway α) (tru : List α) (neg : List α → List α) : Prop :=
  ∀ s, m.Derives tru s ∨ m.Derives tru (neg s)

/-- Consistency restricted to strings of length `n`. -/
def ConsistentAt (m : Multiway α) (tru : List α) (neg : List α → List α) (n : ℕ) : Prop :=
  ∀ s : List α, s.length = n → ¬ (m.Derives tru s ∧ m.Derives tru (neg s))

/-- Completeness restricted to strings of length `n`. -/
def CompleteAt (m : Multiway α) (tru : List α) (neg : List α → List α) (n : ℕ) : Prop :=
  ∀ s : List α, s.length = n → m.Derives tru s ∨ m.Derives tru (neg s)

/-- All strings of length `n`. -/
def stringsOfLength (α : Type*) (n : ℕ) : Set (List α) := {s | s.length = n}

/-- The theorems of length `n`. -/
def theoremsOfLength (m : Multiway α) (tru : List α) (n : ℕ) : Set (List α) :=
  {s | s.length = n ∧ m.Derives tru s}

theorem Consistent.at {m : Multiway α} {tru : List α} {neg : List α → List α}
    (h : Consistent m tru neg) (n : ℕ) : ConsistentAt m tru neg n := fun s _ => h s

theorem Complete.at {m : Multiway α} {tru : List α} {neg : List α → List α}
    (h : Complete m tru neg) (n : ℕ) : CompleteAt m tru neg n := fun s _ => h s

/-! ## wolfram2002-ch12-39: the half-of-all-strings criterion -/

section Counting

variable [Finite α] (m : Multiway α) (tru : List α) (neg : List α → List α)
  (hlen : ∀ s, (neg s).length = s.length)
include hlen

theorem negImage_subset (n : ℕ) :
    neg '' theoremsOfLength m tru n ⊆ stringsOfLength α n := by
  rintro _ ⟨s, ⟨hs, _⟩, rfl⟩
  simp [stringsOfLength, hlen, hs]

/-- wolfram2002-ch12-39: if the system is consistent on strings of length `n`, at most half of
those strings are theorems (negation only needs to be injective here). -/
theorem two_mul_card_le_of_consistentAt (hinj : Function.Injective neg) (n : ℕ)
    (h : ConsistentAt m tru neg n) :
    2 * (theoremsOfLength m tru n).ncard ≤ (stringsOfLength α n).ncard := by
  have hfin : (stringsOfLength α n).Finite := List.finite_length_eq α n
  have hT : theoremsOfLength m tru n ⊆ stringsOfLength α n := fun s hs => hs.1
  have hdisj : Disjoint (theoremsOfLength m tru n) (neg '' theoremsOfLength m tru n) := by
    rw [Set.disjoint_left]
    rintro _ ⟨hlen', hd⟩ ⟨s, ⟨hs, hds⟩, rfl⟩
    exact h s hs ⟨hds, hd⟩
  have hunion := Set.ncard_union_eq hdisj (hfin.subset hT)
    (hfin.subset (negImage_subset m tru neg hlen n))
  rw [Set.ncard_image_of_injective _ hinj] at hunion
  rw [two_mul, ← hunion]
  exact Set.ncard_le_ncard (Set.union_subset hT (negImage_subset m tru neg hlen n)) hfin

/-- wolfram2002-ch12-39: more than half of the strings of length `n` generated implies
inconsistency. -/
theorem not_consistentAt_of_more_than_half (hinv : Function.Involutive neg) (n : ℕ)
    (h : (stringsOfLength α n).ncard < 2 * (theoremsOfLength m tru n).ncard) :
    ¬ ConsistentAt m tru neg n := fun hc =>
  absurd (two_mul_card_le_of_consistentAt m tru neg hlen hinv.injective n hc) (not_le.2 h)

/-- wolfram2002-ch12-39: if the system is complete on strings of length `n`, at least half of
those strings are theorems. -/
theorem card_le_two_mul_of_completeAt (hinv : Function.Involutive neg) (n : ℕ)
    (h : CompleteAt m tru neg n) :
    (stringsOfLength α n).ncard ≤ 2 * (theoremsOfLength m tru n).ncard := by
  have hfin : (stringsOfLength α n).Finite := List.finite_length_eq α n
  have hT : theoremsOfLength m tru n ⊆ stringsOfLength α n := fun s hs => hs.1
  have hcover : stringsOfLength α n ⊆
      theoremsOfLength m tru n ∪ neg '' theoremsOfLength m tru n := by
    intro s hs
    rcases h s hs with hd | hd
    · exact Or.inl ⟨hs, hd⟩
    · refine Or.inr ⟨neg s, ⟨?_, hd⟩, hinv s⟩
      rw [hlen]; exact hs
  calc (stringsOfLength α n).ncard
      ≤ (theoremsOfLength m tru n ∪ neg '' theoremsOfLength m tru n).ncard :=
        Set.ncard_le_ncard hcover ((hfin.subset hT).union
          (hfin.subset (negImage_subset m tru neg hlen n)))
    _ ≤ (theoremsOfLength m tru n).ncard + (neg '' theoremsOfLength m tru n).ncard :=
        Set.ncard_union_le _ _
    _ = 2 * (theoremsOfLength m tru n).ncard := by
        rw [Set.ncard_image_of_injective _ hinv.injective, two_mul]

/-- wolfram2002-ch12-39: fewer than half of the strings of length `n` generated implies
incompleteness. -/
theorem not_completeAt_of_less_than_half (hinv : Function.Involutive neg) (n : ℕ)
    (h : 2 * (theoremsOfLength m tru n).ncard < (stringsOfLength α n).ncard) :
    ¬ CompleteAt m tru neg n := fun hc =>
  absurd (card_le_two_mul_of_completeAt m tru neg hlen hinv n hc) (not_le.2 h)

/-- wolfram2002-ch12-39: a complete and consistent system generates exactly half of the
strings of every length. -/
theorem two_mul_card_eq_of_complete_consistent (hinv : Function.Involutive neg)
    (hc : Complete m tru neg) (hk : Consistent m tru neg) (n : ℕ) :
    2 * (theoremsOfLength m tru n).ncard = (stringsOfLength α n).ncard :=
  le_antisymm (two_mul_card_le_of_consistentAt m tru neg hlen hinv.injective n (hk.at n))
    (card_le_two_mul_of_completeAt m tru neg hlen hinv n (hc.at n))

end Counting

/-- wolfram2002-ch12-39: if negation fixes some string of length `n` (allowed for a general
length-preserving involution), no system is both complete and consistent at that length. -/
theorem not_complete_and_consistent_of_fixedPoint (m : Multiway α) (tru : List α)
    (neg : List α → List α) (n : ℕ) (s : List α) (hs : s.length = n) (hfix : neg s = s) :
    ¬ (CompleteAt m tru neg n ∧ ConsistentAt m tru neg n) := by
  rintro ⟨hc, hk⟩
  have hd : m.Derives tru s := by
    rcases hc s hs with h | h
    · exact h
    · rwa [hfix] at h
  exact hk s hs ⟨hd, hfix ▸ hd⟩

/-- Wolfram's colour-reversal negation on binary strings. -/
def flipNeg : List Bool → List Bool := List.map not

/-- The one-rule system `00 → 11` started from `00`. -/
def halfExample : Multiway Bool := ⟨[([false, false], [true, true])]⟩

theorem halfExample_derives (s : List Bool) (h : halfExample.Derives [false, false] s) :
    s = [false, false] ∨ s = [true, true] := by
  induction h with
  | refl => exact Or.inl rfl
  | tail _ hstep ih =>
    obtain ⟨r, hr, u, v, hb, hc⟩ := hstep
    simp only [halfExample, List.mem_singleton] at hr
    subst hr
    have hlen := congrArg List.length hb
    rcases ih with rfl | rfl <;>
    · simp only [List.length_append, List.length_cons, List.length_nil] at hlen
      have hu : u = [] := List.length_eq_zero_iff.1 (by omega)
      have hv : v = [] := List.length_eq_zero_iff.1 (by omega)
      subst hu hv
      simp_all

theorem stringsOfLength_bool_two :
    stringsOfLength Bool 2 =
      ↑({[false, false], [false, true], [true, false], [true, true]} : Finset (List Bool)) := by
  ext s
  simp only [stringsOfLength, Set.mem_setOf_eq, Finset.coe_insert, Finset.coe_singleton,
    Set.mem_insert_iff, Set.mem_singleton_iff]
  rcases s with _ | ⟨a, _ | ⟨b, _ | ⟨c, l⟩⟩⟩ <;> cases a <;> try cases b
  all_goals simp

/-- wolfram2002-ch12-39: exactly half is not sufficient. For binary strings of length 2 with
colour-reversal negation, `00 → 11` from `00` generates exactly half of the strings
(`00`, `11`) yet is both inconsistent (`00` and its negation `11`) and incomplete (neither `01`
nor `10`). -/
theorem exactly_half_not_sufficient :
    2 * (theoremsOfLength halfExample [false, false] 2).ncard = (stringsOfLength Bool 2).ncard ∧
      ¬ ConsistentAt halfExample [false, false] flipNeg 2 ∧
      ¬ CompleteAt halfExample [false, false] flipNeg 2 := by
  have hT : theoremsOfLength halfExample [false, false] 2 =
      ↑({[false, false], [true, true]} : Finset (List Bool)) := by
    ext s
    simp only [theoremsOfLength, Set.mem_setOf_eq, Finset.coe_insert, Finset.coe_singleton,
      Set.mem_insert_iff, Set.mem_singleton_iff]
    constructor
    · exact fun h => halfExample_derives s h.2
    · rintro (rfl | rfl)
      · exact ⟨rfl, Relation.ReflTransGen.refl⟩
      · exact ⟨rfl, Relation.ReflTransGen.single ⟨_, List.mem_singleton_self _, [], [], rfl, rfl⟩⟩
  have h11 : halfExample.Derives [false, false] [true, true] :=
    Relation.ReflTransGen.single ⟨_, List.mem_singleton_self _, [], [], rfl, rfl⟩
  refine ⟨?_, ?_, ?_⟩
  · rw [hT, stringsOfLength_bool_two, Set.ncard_coe_finset, Set.ncard_coe_finset]
    decide
  · exact fun hk => hk [false, false] rfl ⟨Relation.ReflTransGen.refl, h11⟩
  · intro hc
    rcases hc [false, true] rfl with h | h
    · rcases halfExample_derives _ h with h | h <;> simp at h
    · rcases halfExample_derives _ h with h | h <;> simp [flipNeg] at h

/-! ## wolfram2002-ch12-31: undecidability forces incompleteness or inconsistency -/

section Decidability

variable [Primcodable α] (m : Multiway α) (tru : List α) (neg : List α → List α)

/-- wolfram2002-ch12-31: if the theorems can be enumerated (running the multiway system) and
negation is computable, a complete and consistent system has decidable derivability: run it
until `s` or its negation appears. -/
theorem derives_computable_of_complete_consistent (hre : REPred (m.Derives tru))
    (hneg : Computable neg) (hc : Complete m tru neg) (hk : Consistent m tru neg) :
    ComputablePred (m.Derives tru) := by
  have hre' : REPred fun s => m.Derives tru (neg s) := Partrec.comp hre hneg
  refine ComputablePred.computable_iff_re_compl_re'.2 ⟨hre, hre'.of_eq fun s => ?_⟩
  exact ⟨fun h hs => hk s ⟨hs, h⟩, fun h => (hc s).resolve_left h⟩

/-- wolfram2002-ch12-31: if whether a string is ever reached is undecidable, the system cannot
be both complete and consistent. -/
theorem not_complete_and_consistent_of_undecidable (hre : REPred (m.Derives tru))
    (hneg : Computable neg) (hund : ¬ ComputablePred (m.Derives tru)) :
    ¬ (Complete m tru neg ∧ Consistent m tru neg) := fun ⟨hc, hk⟩ =>
  hund (derives_computable_of_complete_consistent m tru neg hre hneg hc hk)

/-- wolfram2002-ch12-31: assuming consistency, undecidability yields a string such that
neither it nor its negation is derivable. -/
theorem exists_undecided_of_undecidable_consistent (hre : REPred (m.Derives tru))
    (hneg : Computable neg) (hund : ¬ ComputablePred (m.Derives tru))
    (hk : Consistent m tru neg) :
    ∃ s, ¬ m.Derives tru s ∧ ¬ m.Derives tru (neg s) := by
  by_contra h
  push_neg at h
  refine not_complete_and_consistent_of_undecidable m tru neg hre hneg hund ⟨fun s => ?_, hk⟩
  by_cases hs : m.Derives tru s
  · exact Or.inl hs
  · exact Or.inr (h s hs)

end Decidability

end WolframLaws.Logic

#print axioms WolframLaws.Logic.two_mul_card_le_of_consistentAt
#print axioms WolframLaws.Logic.not_consistentAt_of_more_than_half
#print axioms WolframLaws.Logic.card_le_two_mul_of_completeAt
#print axioms WolframLaws.Logic.not_completeAt_of_less_than_half
#print axioms WolframLaws.Logic.two_mul_card_eq_of_complete_consistent
#print axioms WolframLaws.Logic.not_complete_and_consistent_of_fixedPoint
#print axioms WolframLaws.Logic.exactly_half_not_sufficient
#print axioms WolframLaws.Logic.derives_computable_of_complete_consistent
#print axioms WolframLaws.Logic.not_complete_and_consistent_of_undecidable
#print axioms WolframLaws.Logic.exists_undecided_of_undecidable_consistent
