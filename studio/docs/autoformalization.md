# Claim-to-constraints autoformalization (bounded, proposal-only)

Market worker, **single-reader, not Codex-reviewed, not independently reviewed**. Branch `work/autoformalization-recovery`. Nothing here is a claim of
"Lean for biology", of faithful translation from English, or of any functional organism design. API contract: `messages/market-to-root-formalize-contract.md`
(based on the director's v0). Salvage note: the stopped director subagent left an UNCOMMITTED, UNTESTED `frontier/formalize/*` and `engineering/formalize/cases.py`
and `sources/`; they were copied (the original worktree is untouched), tested, and fixed here. Three real bugs were found and fixed by those tests (below).

## Workflow
`pinned public passage` -> **model or human writes a typed PROPOSAL** (symbols with units and domains, assumptions, constraints, source quotes, unresolved choices; JSON
data only) -> `frontier.formalize.propose` -> **grammar** (bounded declarative terms) -> **refusal gates** -> **dimension check** (exact integer exponents of the SI base)
-> **satisfiability** with an independent exact re-check -> **named controls and probes** -> response. A Lean theorem, if any, is a separate hand-authored file compiled by an
explicit local job (`engineering/formalize/lean_run.py`), never by the endpoint.

## What the checker establishes, and what it does not
* Grammar: rational literals (exact), declared symbols, `+ - *`, division by a rational LITERAL only, `pow` with exponent 0..4, comparisons; at most 64 nodes and 16 KB.
  No functions, no strings evaluated, no code. Everything the model writes is parsed as JSON data; the package contains no `eval`, `exec`, `compile`, network or shell (tested by AST scan).
* `status: checked` means: **as written**, the constraints are dimensionally consistent and have a verdict under the declared symbols, units and domains. It does NOT mean the
  constraints encode the source faithfully. `unresolved_translation` and `next_questions` carry what the proposer was unsure of.
* `sat` only with an exact rational witness re-evaluated in `fractions.Fraction` against every constraint and domain by code independent of the search. `unsat` only from (a) exact
  interval refutation of a single constraint over the declared box (sound; tested at the boundary), (b) exhaustive enumeration of a finite integer box, or (c) z3 when importable,
  labelled `independent_check: none` (no proof object). Anything else is `unknown`: an open question, not a guess.
* Controls have a pre-declared expectation and are measured, never tuned: unit mutants, exponent mutants, witness re-check, perturbed witness, strict negation of each constraint.
  **Probes** (`kind: probe`) are measurements without an expectation, e.g. which constraints bind (`g <= n` is redundant given `5g <= 3n`) or which are in a conflict core. Mutation controls are
  skipped when the base law already fails the dimension check, since their premise would not hold.
* Refusals: a causal genotype-to-phenotype claim with no mechanism in the grammar is `refused` (`CAUSAL_GENOTYPE_PHENOTYPE_NO_MECHANISM`) with what would be needed; claims of biological
  function or viability are refused. The gate is lexical and can miss a paraphrase; a miss is not a licence. Checkable sequence facts are reported apart (`separated_checkable_facts`) and
  say nothing about function.

## Demonstrations (all offline-reproducible from committed files)
| # | what | result |
|---|---|---|
| 1 | sourced biomechanics (Euler-Bernoulli end-load law with the Alben et al. range, public passage `sources/cantilever_passage.txt`, hashes in `sources/MANIFEST.json`), hand-authored proposal | `checked`, `sat`, exact witness; 7/7 controls as expected; dims C1 `kg m^4 s^-2`, C2 `m` |
| 2 | corrupt laws: exponent `L^2`, wrong unit | `invalid` by the dimension check before any satisfiability claim; no controls run against a faulty base |
| 3 | dropped guard / over-constrained GC window `7n <= 10g <= 3n` | dropped guard is still `checked` (satisfiability does not show a guard was encoded); the GC window is `unsat` by exhaustive enumeration; probes show C1, C2 in the conflict core and C3 redundant |
| 4 | genotype-phenotype claim (oca2 exon 21 and albinism, Warren et al. 2021 passage) | `refused`; only the counting facts are checkable and they are kept apart |
| 5 | **parameterized theorem, Lean 4.35.0 + Mathlib**: for all real P, L, E, I, d > 0 (as hypotheses) with `3EId = PL^3` and `10PL^2 <= 3EI`, then `d <= L/10` | compiled, standard axioms only; companions prove the hypotheses are satisfiable (not vacuous) and that the stiffness hypothesis is needed; the corrupt law (`L^2`) is rejected by the kernel. See `engineering/formalize/lean/RECEIPT.json` |

## The actual model runs (Google Generative Language, `gemini-3-flash-preview`, reported usage; `engineering/formalize/runs/*`)
Six calls, 32,237 provider-reported tokens in total. No dollar figure is stated: the price of this exact model was not verified. The credential was read in process from the configured
source, sent only in a request header and never logged, printed or written (tested).
| run | settings | outcome |
|---|---|---|
| `cantilever-gemini-1` | maxOutputTokens 4000 | `MAX_TOKENS`: 3,836 of the budget went to hidden thinking, 148 to the answer, JSON cut off. Recorded as rejected |
| `cantilever-gemini-2` | maxOutputTokens 12000 | `MAX_TOKENS` again: 11,516 thinking tokens. Raising the cap was the wrong lever |
| `cantilever-gemini-3` | thinkingLevel low, 8000 | complete proposal; **the model dropped `E*I` from the law (`w_C = P L^3 / 3`)**; the dimension check rejected it: `lhs has dimension [m] but rhs has [kg m^4 s^-2]` |
| `cantilever-gemini-3-repair` | checker finding fed back | the model divided by a symbol, outside the grammar: `unsupported_expression` |
| `cantilever-gemini-3-repair2` | grammar error fed back | grammar-valid, multiplied-out law; the solver then said `unknown`, kept as recorded |
| `oca2-gemini-1` | thinkingLevel low | the model encoded only a counting relation and listed the missing mechanism as unresolved; the gate `refused` the causal claim |
After round 2 the CHECKER was changed, not the proposal: the witness search resolved eliminated variables in listed order (a bug, fixed to dependency order) and its candidate grid
gained fine points near a low bound. The same request was re-checked: `checked`, `sat`, witness verified by hand (`3 * 1e8 * 1e-14 * (1/30) = 1e-7 = 100 * (1/1000)^3`). The original
`unknown` is kept; the re-check is `recheck_after_solver_change.json`. **The repaired law is dimensionally consistent and satisfiable as written; the model omitted the small-deflection guard, and
fidelity of the translation to the source remains unverified.**

## Bugs found by the tests in the salvaged code (fixed)
1. a literal `"1/0"` raised `ZeroDivisionError` out of `propose()`; 2. a 100,000-deep nested list raised `RecursionError` out of `propose()`; 3. the witness search could not solve equalities that depend on
another equality's variable. Also corrected: controls whose premise was false (strict negation instead of `<=`/`>=` flip; redundancy checks relabelled probes).

## Run
`python3 -m pytest tests/test_autoformalization.py` (50 tests, hand-worked expectations, recorded runs verified offline). `FRONTIER_RUN_LEAN=1` also recompiles the Lean files (about 2 minutes, 12G cap).
New model runs: `python3 -m engineering.formalize.extract --case cantilever|oca2 --out <dir> --thinking level:low --max-output-tokens 8000` (needs a configured credential; `--repair-of <dir>` for a bounded repair round).

## Limits and open problems
Translation fidelity is never proven. The grammar has no vocabulary for biological mechanism, so unsupported biology is an explicit open translation problem. The Lean text is hand-authored and corresponds
to the hand-authored fixture; the service's generated `lean_statement` (unit-rescaling invariance) is text only and was not compiled. z3 was not importable in the worker, so `unsat` rests on intervals and enumeration.
The refusal gate is lexical. The checker is proposal-only: no persistence or Lean job.
The website exposes `POST /api/formalize/propose` through its existing session,
Origin and CSRF checks, with a16KiB request limit and two concurrent slots.
Public readers can create an anonymous calculation session; it grants no record
write permission. Each solver child has an8second wall limit,10CPU-second limit
and384MiB address-space limit. Model calls remain separate offline actions.
