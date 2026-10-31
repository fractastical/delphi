# Lean 4 formalization instructions: Thompson's laws (On Growth and Form, 1917)

Read `BEST_PRACTICES.md` (repo root), especially "Stub proofs" in section 2 and "Formulas and
Lean live on a law concept" in section 9. The ontology convention is upstream in
`ONTOLOGY.md`, "Formal-verification convention (v1.3)".

Lake project: `books/thompson-growth-form/lean/` (Lean `v4.35.0`, Mathlib `v4.35.0`, already
downloaded). Check a module with:

```bash
cd books/thompson-growth-form/lean && lake env lean ThompsonLaws/<Module>.lean
```

(The first check takes about 90 s while Mathlib loads.)

## Inputs

`books/thompson-growth-form/claims.json`. Your task names the claim ids you own. For each, use its
`claim`, `quote`, `notation` (the LaTeX), `scope` and `claim_kind`. Read the surrounding
source text in `books/thompson-growth-form/inputs/pg55264.txt` (`lineStart`–`lineEnd`) if you
need Thompson's argument.

## What to write

One module, `books/thompson-growth-form/lean/ThompsonLaws/<Module>.lean`, starting with
`import Mathlib` and wrapped in `namespace ThompsonLaws.<Module>`. For each claim you can
formalize, one block, preceded by a doc comment naming the claim id:

```lean
/-- thompson1917-ch02-03: strength ∝ L², weight ∝ L³ ⇒ strength/weight ∝ 1/L. -/
def strengthToWeight (a b L : ℝ) : ℝ := (a * L ^ 2) / (b * L ^ 3)

theorem strengthToWeight_eq (a b L : ℝ) (hb : b ≠ 0) (hL : L ≠ 0) :
    strengthToWeight a b L = (a / b) * L⁻¹ := by
  unfold strengthToWeight; field_simp; ring
```

Rules:

- **Encode the stated law, not generic arithmetic.** The `def` names the quantity Thompson
  talks about. The `theorem` states the consequence he draws (the relation in `notation`,
  or the inference in `claim`), with his physical assumptions (proportionalities,
  constant ratios, equilibrium conditions, geometry) as explicit hypotheses or as the
  definition itself. The conclusion must not simply restate a hypothesis, must not be
  `True`, and must involve the law's quantities.
- **Only what mathematics can establish.** Empirical parts (measured values, "about 300
  ft", "in most shells", which species do what) cannot be proved. Formalize the
  mathematical core when there is one, and say in `scope_note` what is left to data. If a
  claim has no mathematical core that Lean can state faithfully, do not force one: mark it
  `not-formalized` with the reason.
- **No `sorry`, `admit`, `axiom`, `native_decide`, `unsafe`, or `opaque` constants.** The
  only axioms allowed are Lean's standard `propext`, `Classical.choice`, `Quot.sound`.
- Names are `lowerCamelCase`, unique within the module. One `def` and one or more
  `theorem`s per claim; reuse a `def` from earlier in the module if two claims share it.
- Keep it readable: `ℝ` for physical quantities, positivity hypotheses (`0 < L`) where the
  physics needs them.

The module must check with no errors and no `sorry` warnings. Then add at the end of the
file, outside the namespace, one `#print axioms ThompsonLaws.<Module>.<theorem>` per theorem,
check again, and confirm the output lists only the three standard axioms. Remove those
`#print` lines again before finishing.

## Report file

Write `books/thompson-growth-form/lean/reports/<Module>.json`: a JSON array, one object per claim
you were given, in claims.json order:

```json
{
  "claim_id": "thompson1917-ch02-03",
  "status": "formalized",
  "label": "Strength-to-weight ratio falls as 1/L under square–cube scaling",
  "notation": "\\frac{\\text{strength}}{W} \\propto L^{-1}",
  "lean_declaration": "ThompsonLaws.Magnitude.strengthToWeight",
  "lean_theorems": ["ThompsonLaws.Magnitude.strengthToWeight_eq"],
  "assumptions": "Strength proportional to cross-sectional area (a L²), weight to volume (b L³), with fixed shape.",
  "scope_note": "Proves the ratio falls as 1/L; whether real muscle strength scales as L² is an empirical question."
}
```

- `status`: `formalized` or `not-formalized` (then omit the `lean_*` fields and give
  `reason` instead of `scope_note`).
- `label`: ≤ 90 characters, names the law.
- `notation`: the claim's LaTeX from claims.json, corrected only if it is mathematically
  wrong or does not match what you proved (then explain in `scope_note`).

Report back: the module path, how many claims were formalized and not formalized, the
theorem names, and confirmation that the module checks with only the standard axioms.
