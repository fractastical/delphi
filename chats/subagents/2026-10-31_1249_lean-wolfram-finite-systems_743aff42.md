# Subagent: Lean: Wolfram finite systems

- **Parent chat:** [none of the wolfram ones got verified](../2026-10-31_1244_none-of-the-wolfram-ones-got-verified.md)
- **Started:** 2026-10-31 12:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 13:07 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** aborted
- **Transcript ID:** `743aff42-f3d3-4212-8e1b-5b343ab3e268`

---

### 2026-10-31 12:49 — Turn 1 (User)

> Repo: /Users/jdietz/Documents/GitHub/dev/delphisci. Follow books/wolfram-nks/lean/INSTRUCTIONS.md exactly (read it first, plus the BEST_PRACTICES.md sections it names). Your module is `Finite`: write books/wolfram-nks/lean/WolframLaws/Finite.lean and books/wolfram-nks/lean/reports/Finite.json. Do not touch any other module or report (other agents are writing Additive, Digits, Logic in parallel).
> 
> Your claim ids, in claims.json order (look them up in books/wolfram-nks/claims.json): wolfram2002-ch05-09, wolfram2002-ch05-15, wolfram2002-ch05-16, wolfram2002-ch05-18, wolfram2002-ch05-20, wolfram2002-ch06-12, wolfram2002-ch06-17, wolfram2002-ch09-02, wolfram2002-ch09-15, wolfram2002-ch09-17, wolfram2002-ch09-24, wolfram2002-ch09-25, wolfram2002-ch11-08, wolfram2002-ch11-19.
> 
> Suggested targets (use your judgement; faithfulness beats count):
> - ch06-12: any deterministic map on a finite state set has an eventually periodic orbit with period ≤ card of states (pigeonhole).
> - ch06-17: an elementary (nearest-neighbour, 2-colour) CA started from a configuration with spatial period n is eventually periodic in time with period ≤ 2^n; derive from ch06-12 via the cyclic system on Fin n → Bool / ZMod n → Bool and show the bi-infinite evolution equals the lifted cyclic one.
> - ch05-15: 1D local constraints (an allowed set of length-k windows over a finite alphabet) that admit a bi-infinite (ℤ-indexed) satisfying configuration also admit a periodic one (pigeonhole on windows / de Bruijn cycle).
> - ch09-02: define elementary rule number r : Fin 256 acting on ℤ → Bool; prove the six rules 15, 51, 85, 170, 204, 240 are injective (bijective) on configurations, and that every other rule is not injective, e.g. via explicit colliding pairs of periodic configurations checked by decide on a cyclic ring plus a lifting lemma. The 3-colour count (1800 of 3^27) is out of reach: say so in scope_note. If the full 250-rule non-injectivity is too costly, formalize what you can and be explicit; only mark formalized if the theorem captures the 6-of-256 statement or a clearly stated core of it.
> - ch11-08: light cone: for a radius-1 CA with quiescent state (f 0 0 0 = 0), the support after t steps lies within the initial support widened by t on each side, while a uniform substitution of factor k ≥ 2 has length k^t·|w|; conclude a CA cannot emulate it one step per step (state this precisely).
> - ch05-16/18/20 are huge computer searches, ch09-15/24/25 are physics/differential-geometry heuristics, ch09-17 causal invariance, ch05-09, ch11-19 (vague class definitions): decline unless you find a faithful, tractable core.
> 
> Check with `cd books/wolfram-nks/lean && lake env lean WolframLaws/Finite.lean` (≈90 s per check; keep iterating until clean). Return: module path, counts formalized / not-formalized, theorem names, and confirmation of the #print axioms check.

**Assistant:**

I'm starting by reviewing the instructions provided.

_Tools used: Grep, Read ×3, Shell, UpdateCurrentStep_

_Turn ended: aborted_
