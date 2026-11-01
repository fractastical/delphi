# what bout solving something around morphogenesis

- **Started:** 2026-10-31 19:36 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 19:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `2d7c6261-70c4-44c8-b6a9-78b902226193`

## Conversation

### 2026-10-31 19:36 — Turn 1 (User)

> what bout solving something around morphogenesis

**Assistant:**

I'll start by looking for morphogenesis claims in the graph, especially ones that are testable but haven't been tested yet.

The user's question is vague, so I should look through the repo for morphogenesis-related claims to find something testable. Let me check the available tools and their schemas before searching.

I'm weighing a couple of candidates, like the active inference morphogenesis claim with strong testability or the exogenous gradient robustness simulation, and leaning toward presenting a short shortlist with a recommendation rather than just picking one outright.


I found 29 untested morphogenesis claims and narrowed it to four strong computational candidates, with `levin-2015-place-04` (testing convergence via free-energy minimization simulation) standing out as the best pick since it's a real open question with no prior tests. I'll proceed with that one.

I'll pre-register the test for `levin-2015-place-04`. First I'll read the repo's pre-registration conventions and the claim itself.

Since this is pre-registration only, I should check the README in test-data/claim-tests for guidance, review the claim details, and find an example prereg to follow.

Sibling claims from the same paper (`place-01`, `-05` and `-06`) already have tests. I'll read them so the new pre-registration is consistent with theirs and doesn't duplicate them.

Other sibling tests like place-05 and place-06 also include morphogenesis.py, so I should check place-01's result.json alongside it for alignment. Since the model code appears public and isn't quite "data" for pre-registration purposes, I can look at it carefully before checking place-01's result.

I'm drafting a pre-registration for place-04, focused on the claim that variational free energy minimization uniquely guarantees convergence to correctly inferred, uniquely located cells. I want to test this by running the re-implementation from many random and adversarial initializations—wrong identities, permutations, duplicates—to check whether descent always avoids non-target local minima.

I'm also accounting for the inherent permutation symmetry (8! equally valid cell-to-location assignments), so "unique location" means up to relabeling. My pass criterion: across 200 seeds run to steady state (~512 steps with sensitivity ramp saturated), at least 95% must converge to the target configuration (distinct positions, correct types, low spacing error), and the free energy at any non-target stationary point must exceed the target's free energy—since "guarantee" demands universality, any reproducible counterexample would fail the claim.

I'm defining tiers: full support requires 100% convergence across all initialization families with target as the unique global minimum; a refutation requires either ≥10% non-convergence among verified local minima, or discovery of a non-target stationary point with free energy at or below target (indicating a tied/non-unique minimum, like two cells swapping positions with equal energy); everything else counts as mixed evidence. I'll also run multi-start local optimization to directly probe the free-energy landscape around the target versus swapped or duplicated configurations.

I'm treating the exogenous gradient ablation as a secondary sensitivity check rather than part of the main claim, since removing it could introduce symmetric ambiguity between identical cells. I want to test both a dynamic version (long-horizon trajectories from varied initial conditions) and a static version (multi-start minimization of free energy over position and signal variables at fixed sensitivity), reusing the existing morphogenesis script from the prior experiment, and I should check how other preregistered results are formatted before writing this one's status file.


Those sibling entries confirm the format, noting the paper's model is reproducible but sensitive to initialization. I'll now check other preregistered entries' layouts and reusable code so the new test can leverage the same re-implementation.

I'll write just the result.json marking status as preregistered, skipping any analysis file. I need to carefully separate the claim into two parts: the characterization of global minimizers (unique location, correct inferred place) and the assertion that free-energy minimization guarantees convergence to that target form from any starting point—I should flag a subtlety in how these two parts relate before finalizing the wording.

I want to preregister that "unique location" holds only up to relabeling permutation symmetry, and note that the prior precision on v and the logdet term mean the true F-minimum may not land exactly at zero error — it's biased by prior shrinkage, so I'll set a tolerance where success means assess() passes (rms below half spacing, all types correctly matched). For the static test I'll run multi-start local minimization of the full free energy (including the logdet term) over the parameters using L-BFGS with finite-difference gradients, while being careful that the dynamic flow() doesn't include that logdet term — so I need to preregister that static and dynamic analyses are optimizing slightly different objectives.

Then I plan to let flow() run to a long horizon to find stationary points, compute F at convergence via free_energy(), and compare target versus non-target attractors, defining success as convergence within 1 nat of F. I'm setting up four families of fifty random seeds each: one matching the paper's literal initialization, one with near-one-hot identities, an adversarial case where every cell starts with the same identity and thus the same target position, and one with random distinct positions paired with random identities.

I'm treating F1 and F2 as the primary in-scope families since they reflect the paper's stated readings, while F3 and F4 are stress tests outside the literal claim but useful for checking universality. I'm defining the run horizon as 32 bins followed by 224 more at saturated sigma, 256 time units total, and need to pin down exactly what counts as "converged."

Now I'm working out the success criteria for each run—requiring all 8 cells correctly placed and sufficiently separated—and setting the pass threshold: all primary runs succeeding plus nearly all stress runs succeeding, with a final-cost ordering check for any non-successful converged runs.

I also want to try a second validation approach: deliberately construct wrong configurations (duplicate positions, swapped identities, uniform identities), run each through the flow, and check whether any non-target outcome converges to a cost competitive with the actual target solution—if so, that would undermine the claim of uniqueness.

I should treat a lower-energy converged non-target state as a refuting competing minimum, not just unconverged runs as failures. Let me set clear tiers: full success rates near 100% for the easier cases and near 95% for harder ones supports the claim, while low success rates or any competing stationary state at or below the reference energy counts as refuting evidence.

I'll also handle reproducible non-target attractors — if 10% or more of runs in a family converge to something other than the target, that's a sign convergence isn't guaranteed, though I need to decide whether stress-test families (like different starting positions) count toward "refutes" or just "mixed" given they're still within the scope of identical cells sharing one generative model. I'll say failures confined to stress families with primary families at 100% success count as "mixed," while failures in primary families trigger the stricter "refutes" threshold.

I'll leave the exogenous gradient ablation and Hessian/second-order analysis out of scope since those belong to a separate investigation, and note that the gradient is kept on as given in the file. For seeding, I'm using numpy's default_rng with offset ranges per family (1000+ for F1, 2000+ for F2, etc.) to keep each family's randomness distinct.

For datasets, I should follow the precedent of listing only planned datasets without checksums, consistent with how an earlier boundary pre-registration handled this, and flag the "computational" data kind in my interpretation notes. For the implementation, my analysis script will import and reuse the existing morphogenesis module rather than duplicating it, citing its hash, and I need to remember the rule that the file must be committed first before anything references it.

I'm now settling on the timestamp — using 2026-10-31T23:36:00Z to match the current time, consistent with how the boundary-14 deviation was logged, and identifying myself as the agent model for the record.

I also recall having seen the sibling place-01 results (19/20 at 32 steps for F1, 14/20 for F2) and the underlying code, but I haven't run the new analysis myself — this needs honest disclosure as a preregistration note about prior knowledge, since the thresholds were chosen with that information in hand. Now I'll write the file.


I'll reuse the existing numpy SPM model from `levin-2015-place-01/morphogenesis.py`, but unlike the sibling tests' limited 32-step runs, I'll run it to steady state from many starting points to check for competing minima. I'm writing just the pre-registration now, without running any analysis.

I've pre-registered a test for `levin-2015-place-04`. It's in `test-data/claim-tests/levin-papers/levin-2015-place-04/result.json`, which parses as valid JSON with `status: "preregistered"`. I haven't written `analysis.py` or run anything.

**The claim.** In the active-inference morphogenesis model from Friston, Levin et al. (2015), free energy is minimized only when every cell sits at a unique place and has inferred its identity correctly. So free-energy minimization is said to guarantee convergence to the target form.

**What the test does.** It reuses the numpy re-implementation of the paper's model from `levin-2015-place-01` unchanged. The existing tests only ran the paper's 32-step schedule from about 20 starts. This one runs to a steady state from 200 starts in four families:

| Family | Start | Role |
|---|---|---|
| F1 | Cells co-located, identities `randn/8` (the SPM file's start) | Primary |
| F2 | Cells co-located, identities with sd = e^2 (the paper's literal "log precision −4") | Primary |
| F3 | Cells co-located, all identities set to one type | Stress |
| F4 | Random distinct positions and random identities | Stress |

A run succeeds if all 8 cells end at distinct target positions with the correct identity. That is stricter than the 7/8 used in `place-01`, because this claim says every cell. The test also looks for competing minima: a converged non-target state whose free energy is within 1 nat of the target's, or lower.

**Verdict tiers.**
- **Supports:** 50/50 successes in F1 and in F2, at least 48/50 in each of F3 and F4, and no competing minimum.
- **Refutes:**
  - fewer than 25/50 successes in F1 or F2;
  - a competing or deeper minimum in F1 or F2;
  - a reproducible non-target attractor in at least 10% of F1 or F2 runs.
- **Mixed:** everything else.

**Caveats.**
- A sampling test can refute the universal "guarantees" claim but can't prove it. "Supports" here means no counterexample in 200 runs.
- Before writing the thresholds I read the `place-01` and `place-05` results, which found 19/20 and 14/20 assembled runs. That is why the F1/F2 refutation floor is loose, and I disclosed it in `preregistration_notes`.
- The file also says the result will be `computational` data. It shows the claim as a statement about the model, not that real cells minimize free energy.

**Next steps.**
- The repo rules say to commit the pre-registration before running anything. I haven't committed it.
- If you want, I can write `analysis.py` and run it.

_Tools used: AskQuestion, GetDynamicTools ×2, Glob, Grep ×3, Read ×5, Shell, Write, delphi_claim_tests ×2, delphi_get_claim_
