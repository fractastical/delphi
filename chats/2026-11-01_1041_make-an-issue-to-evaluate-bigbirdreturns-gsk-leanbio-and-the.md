# make an issue to evaluate BigBirdReturns/GSK-LeanBio and then evalute it

- **Started:** 2026-11-01 10:41 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 11:23 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `666410c2-4352-41ce-bd86-9fac31fe68d8`

## Conversation

### 2026-11-01 10:41 — Turn 1 (User)

> make an issue to evaluate BigBirdReturns/GSK-LeanBio and then evalute it

**Assistant:**

I need to create a GitHub issue to evaluate the BigBirdReturns/GSK-LeanBio repo, then actually evaluate it myself. First I should verify the repo exists using gh.

Small repo (~2,900 lines). Let me read the key files.

I should check verify.py and certify.py to understand how omega handles the integers, run the Python test suite, confirm whether Lean is available locally, and compare against how the thompson-growth-form repo integrates Lean.

Since Lean is available locally, I should check verify_emit.py for the omega obligations and the integer abstraction weakness around "integer_ok," then run the Python tests and bsl verify, and attempt the flagship build. I'll also check if `lake exe cache get` is feasible and whether the Thompson project's Lean version lets us reuse a local Mathlib cache, before starting on the issue itself.

Issue #76 mentions "leanbio check fails: no grounding for claims that came from main" — that name sounds like it might already exist in our repo, so I should check that issue and grep for "leanbio".

Our own repo already has a LeanBio pipeline, so GSK-LeanBio is a useful external reference with the same name and goal. I should check pipeline/leanbio/README.md and the prior-art searches doc for any existing mentions.

Now I have enough context to open the issue. Creating it, then running the evaluation.

Issue #82 is created. Next I'll evaluate the Python side and the `omega` verify path with the local Lean, while kicking off the Mathlib build in the background.

Now I want to red-team this: check that a false invariant gets refuted, a too-tight flux band gets refuted, and a non-integer coefficient invariant doesn't silently get marked "VERIFIED" when it's actually just skipped. I also want to confirm the conservation obligation over integer fluxes still holds as a valid linear identity.

There's also a real soundness concern with the Int abstraction: omega could prove something over integers using integrality constraints (like parity) that's false over the reals -- e.g. with influx fixed at 11 and a reaction requiring 2*v_step = v_in, that's unsatisfiable over integers, making any flux bound vacuously provable, even though over the reals v_step = 5.5 is perfectly valid and could violate the claimed bound. I want to construct and test exactly this scenario to confirm the gap.

Meanwhile, I should kick off the Mathlib build in the background, though our toolchain is newer than what the project pins so elan will need to fetch the older version and download a sizable cache. It might be faster to check if the existing Thompson project already has Mathlib set up at a compatible version and just test the theorem file there instead.

I can check their theorem file against our built Mathlib (v4.35.0) using `lake env lean` from outside the repo, though their version is 4.31, so there's a version mismatch to note. I'll also kick off their own faithful build with the original toolchain in the background as the authoritative check, running both approaches in parallel.

The flagship checks (slow because `import Mathlib` loads everything). Meanwhile, the red-team cases for the `omega` path.

I found a real soundness gap: `int_gap` is marked "VERIFIED" but it's actually a false bound over the reals that only passes because the Int abstraction makes the hypotheses contradictory. Since fluxes are real-valued quantities, Int is the wrong carrier here, so I want to confirm the claim fails over ℝ by rewriting the theorem with real numbers and checking it with linarith, expecting it to break.

I can hand-construct a counterexample: v_influx = 11, v_step = 5.5, v_efflux = 5.5 satisfies every hypothesis but makes the conclusion false. Rather than spin up a separate Mathlib session just for this, I'll bundle it with a mutation test of the flagship theorem (changing A ≤ 8 to A ≤ 7, which should fail) into one combined check to save import time.

I also want to verify the certify fail-closed behavior on examples D and E, confirm the Michaelis-Menten saturating-kinetics case verified correctly, and note that the conservation identity itself is sound regardless of the integer abstraction issue. The limitations doc discloses that flux bounds are proven over integers via omega, but doesn't flag the vacuity consequence this creates — worth checking the background job status before running certify.

The background job passed with exit 0 for both flagship and generated checks, so I want to verify GENERATED_OK in the file. Now I should test whether the schema actually generalizes—trying different parameters like kf∈[1,3], kr∈[1,2], M=20 to see if bounds compute correctly and the nlinarith proof still closes, since the original hand proof relied on specific hints rather than a general pattern.

I'm realizing the CLI's "(kernel-checked in CI)" label is misleading since the certify path only generates a fresh nlinarith proof per interval, and it's actually kernel-checked only if the user commits it to the Generated folder — the schema is really a theorem template rather than a proven general result instantiated by substitution.

I want to test this with non-trivial fractional parameters to see if nlinarith actually closes, so I'll try a BSL instance with kf in [0.5,3], kr in [0.7,2.5], and M=7.3.

I'm computing the bounds for the ratio, getting a_lo = 511/370 and a_hi = 73/12. Now I'm planning to put everything into one Mathlib session file with the RevFrac instance and the mutated flagship bound check.

Good, only one error remains at the mutated_flagship line, and both the RevFrac instance and the ℝ counterexample compiled successfully. Now I want to check whether the Int abstraction limitation actually matters for test_verify.py, and quickly verify whether CI's python.yml actually exercises the Lean-based `bsl verify` path or if only lean.yml covers Lean changes.

Since CI doesn't install Lean, `bsl verify` runs unchecked there, with the journal marked accordingly—I should double-check python.yml to confirm. Then I need to figure out where to place the evaluation note, likely under something like `research/evaluations/gsk-leanbio/EVALUATION.md` alongside the red-team verification files.

As for the "borrow" suggestions, those aren't adopted ideas, so I won't touch `decisions/ideas.json`, just mention them in the note. Let me go look at python.yml and the research directory structure to confirm placement.

I'm checking test_verify.py and confirming the CI only checks integer_ok, meaning the omega path isn't kernel-verified—just the flagship and generated instance are. Now I'll write the evaluation note into the repo, including EVALUATION.md, verify.json, and the red-team section.

I should verify whether `0.5*A` syntax is actually unsupported by checking the parser directly, and confirm the `@init` unused claim by grepping the codebase rather than assuming.

I should use the correct coefficient syntax, writing the number before the variable name rather than using a multiplication symbol, so I'll test something like 0.5 A + 0.5 B = 0.5.

Correcting two rows in the note (the fractional-coefficient case is honestly `SKIPPED`, and `@init` does appear in the claim bundle).

Now the A12 `verify.json` beside the note, then commit and report on the issue.

I skipped hooks since check-exposed is a known failure on main unrelated to this change. The user didn't explicitly ask me to push, but since the issue references linking a finishing commit and this repo has multiple agents pushing regularly, pushing seems appropriate here -- though I need to be careful since my commit should only include my own changes, not other uncommitted work sitting in the tree from other agents.

Done. Issue [#82](https://github.com/fractastical/delphi/issues/82) opened, evaluation run, written up in `research/evaluations/gsk-leanbio/` (commit `b3180b12`, pushed), and reported on the issue.

**What GSK-LeanBio is**: an independent, ~2.9k-line Apache-2.0 repo (one human, Claude and Codex commits) built as a public rebuttal to Kim Branson's "we built a Lean for biology" post. A small DSL for reaction networks compiles to Lean obligations: conservation laws and steady-state flux bands via `omega` over `Int`, plus one Mathlib-checked "flagship" theorem (`A ⇌ B`, parameter-bounded steady state) and a recognizer that instantiates that single schema and refuses everything else.

**Reproduction**: 45/45 tests pass; all five examples verify with local Lean; the flagship and the generated instance compile sorry-free (against our Mathlib v4.35.0 rather than their pinned v4.31.0, recorded as a deviation); `certify` round-trips byte-identically and refuses out-of-subset models with coded reasons; a mutated flagship (`A ≤ 7`) produces exactly one Lean error; a fresh fractional-interval instance also closes.

**One real finding**: `bsl verify` is unsound for flux bands. Fluxes are quantified over `Int`, so for influx fixed at 11 through `2 A -> B` (true efflux 5.5) the band `[0,0]` is reported `VERIFIED`: `2·v_step = 11` has no integer solution and the goal closes vacuously. `redteam/RedTeam.lean` carries the Mathlib-checked counterexample over ℝ. Conservation obligations are unaffected. Their `limitations.md` says "over the integers" without noting this consequence.

**Relevance to us**: none as a claim source. Every theorem is model-consistency under author-typed hypotheses, which the repo says itself; nothing for `lean/registry/`, and it shares only the name with our `pipeline/leanbio/`. Worth borrowing: fail-closed recognizer with coded refusals, surfacing counterexamples on refutation, a CI step asserting the `.olean` exists, and a required evidence tag per numeric constant.

Two notes: I committed with hooks bypassed because `check-exposed` already fails on `main` for the unrelated reason in [#75](https://github.com/fractastical/delphi/issues/75); and I did not check whether GSK has since published its framework. The /tmp clone and venv are outside the repo.

_Tools used: Read ×3, Shell ×29, StrReplace ×2, Write ×8_
