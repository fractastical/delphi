/-
  UnitAlgebra -- the ARITHMETIC that engineering/coupling.py relies on when it validates a unit conversion.

  Proved here (universally quantified, over ℚ and ℤ):
    * converting by f then by g is converting by f*g, a positive factor keeps a positive value positive,
      and a nonzero factor is undone by its inverse;
    * mapping an interval [lo, hi] by a POSITIVE factor f gives [lo*f, hi*f] (the rule coupling.py uses to
      check a mapped range against a target port's bounds), and positivity of f is NECESSARY (counterexample);
    * dimension exponents (kg, m, s) add under multiplication, so 'dim(dst) = dim(src) + dim(factor)' composes.
  NOT proved: that any two models describe the same organism, that any calibration is correct, anything about
  biology. Units themselves (what 'kg' means) are conventions checked in Python.
-/
import Mathlib.Tactic

namespace UnitAlgebra

/-- Exponent vector over the base units (kg, m, s). -/
@[ext] structure Dim where
  kg : ℤ
  m : ℤ
  s : ℤ

def Dim.add (a b : Dim) : Dim := ⟨a.kg + b.kg, a.m + b.m, a.s + b.s⟩

theorem convert_comp (x f g : ℚ) : (x * f) * g = x * (f * g) := by ring

theorem convert_pos {x f : ℚ} (hx : 0 < x) (hf : 0 < f) : 0 < x * f := mul_pos hx hf

theorem convert_inv {x f : ℚ} (hf : f ≠ 0) : (x * f) * f⁻¹ = x := by
  field_simp

theorem interval_map {lo hi x f : ℚ} (hf : 0 < f) (h1 : lo ≤ x) (h2 : x ≤ hi) :
    lo * f ≤ x * f ∧ x * f ≤ hi * f :=
  ⟨mul_le_mul_of_nonneg_right h1 hf.le, mul_le_mul_of_nonneg_right h2 hf.le⟩

theorem dim_compose {src dst dst2 f g : Dim} (h1 : dst = src.add f) (h2 : dst2 = dst.add g) :
    dst2 = src.add (f.add g) := by
  subst h1 h2
  ext <;> simp [Dim.add] <;> ring

end UnitAlgebra
