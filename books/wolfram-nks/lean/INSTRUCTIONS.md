# Lean 4 formalization instructions: Wolfram's mathematical claims (A New Kind of Science, 2002)

Read `BEST_PRACTICES.md` (repo root), especially "Stub proofs" in section 2 and "Formulas and
Lean live on a law concept" in section 9. The ontology convention is upstream in
`ONTOLOGY.md`, "Formal-verification convention (v1.3)". The Thompson project
(`books/thompson-growth-form/lean/`) follows the same rules and is a worked example.

Lake project: `books/wolfram-nks/lean/` (Lean `v4.35.0`, Mathlib `v4.35.0`, already
downloaded). Check a module with:

```bash
cd books/wolfram-nks/lean && lake env lean WolframLaws/<Module>.lean
```

(The first check takes about 90 s while Mathlib loads.)

## Inputs

`books/wolfram-nks/claims.json`. Your task names the claim ids you own. For each, use its
`claim`, `quote`, `scope` and `claim_kind`. The book text for page N is in
`books/wolfram-nks/inputs/cache/pages/pN.txt` (`pageStart`–`pageEnd`); read it if you need
Wolfram's argument.

## What to write

One module, `books/wolfram-nks/lean/WolframLaws/<Module>.lean`, starting with `import Mathlib`
and wrapped in `namespace WolframLaws.<Module>`. For each claim you can formalize, one block,
preceded by a doc comment naming the claim id:

```lean
/-- wolfram2002-ch06-12: a deterministic system with finitely many states eventually repeats. -/
def orbit {S : Type*} (f : S → S) (s : S) (n : ℕ) : S := f^[n] s

theorem orbit_eventually_periodic {S : Type*} [Fintype S] (f : S → S) (s : S) :
    ∃ m p, 0 < p ∧ p ≤ Fintype.card S ∧ ∀ n ≥ m, orbit f s (n + p) = orbit f s n := by
  -- pigeonhole on orbit f s restricted to Fin (card S + 1)
```

(The proof is elided above; yours must be complete.)

Rules:

- **Encode the stated claim, not a generic fact.** The `def` names the system Wolfram talks
  about (a cellular automaton rule, a substitution or tag system, a digit expansion, an axiom
  system). The `theorem` states the consequence he draws, with his assumptions (finite size,
  additivity, neighbor-independence, an involutive negation, …) as explicit hypotheses or as the
  definition itself. The conclusion must not simply restate a hypothesis, must not be `True`, and
  must involve the claim's objects. A theorem about a concrete rule (rule 90, rule 150) should use
  that rule's actual update table.
- **Only what mathematics can establish.** Empirical or heuristic parts ("almost all", "seems
  random", "should be widespread in nature", "is likely", "probably") cannot be proved. Formalize
  the mathematical core when there is one, and say in `scope_note` what is left over. If a claim
  has no core that Lean can state faithfully, or its core is a deep result out of reach here
  (universality of rule 110, P ≠ NP, Gödel's theorems for arithmetic), do not force one: mark it
  `not-formalized` with the reason. If the claim is mathematically false as stated, say so in the
  reason, and formalize the true part only if that part is still the substance of the claim.
- **Finite enumerations** (counts over 256 elementary rules, explicit witnesses) may use `decide`
  when the kernel can check them in reasonable time. Never `native_decide`.
- **No `sorry`, `admit`, `axiom`, `native_decide`, `unsafe`, or `opaque` constants.** The only
  axioms allowed are Lean's standard `propext`, `Classical.choice`, `Quot.sound`.
- Names are `lowerCamelCase`, unique within the module. One `def` and one or more `theorem`s per
  claim; reuse a `def` from earlier in the module if two claims share it.
- Keep it readable: `ℤ → Bool` or `ℤ → ZMod 2` for bi-infinite configurations, `Fin n → _` or
  `ZMod n → _` for cyclic ones, `List` for words of substitution and tag systems.

The module must check with no errors and no `sorry` warnings. Then add at the end of the file,
outside the namespace, one `#print axioms WolframLaws.<Module>.<theorem>` per theorem, check
again, and confirm the output lists only the three standard axioms. Remove those `#print` lines
again before finishing.

## Report file

Write `books/wolfram-nks/lean/reports/<Module>.json`: a JSON array, one object per claim you
were given, in claims.json order:

```json
{
  "claim_id": "wolfram2002-ch06-12",
  "status": "formalized",
  "label": "Finite deterministic systems eventually repeat, with period at most the number of states",
  "notation": "\\exists m,\\, p \\le |S| : f^{n+p}(s) = f^{n}(s) \\ \\forall n \\ge m",
  "lean_declaration": "WolframLaws.Finite.orbit",
  "lean_theorems": ["WolframLaws.Finite.orbit_eventually_periodic"],
  "assumptions": "A deterministic update map f on a finite state set S.",
  "scope_note": "Proves eventual periodicity with period ≤ |S| by pigeonhole; nothing is left to data."
}
```

- `status`: `formalized` or `not-formalized` (then omit the `lean_*` fields and give
  `reason` instead of `scope_note`).
- `label`: ≤ 90 characters, names the law.
- `notation`: Wolfram's claims have no LaTeX in claims.json; write the LaTeX of what you proved
  (omit the field for `not-formalized`).
- The first entry of the array must be a `formalized` one if the module has any, because the
  site reads the module path from the first entry's `lean_declaration`.

Report back: the module path, how many claims were formalized and not formalized, the theorem
names, and confirmation that the module checks with only the standard axioms.
