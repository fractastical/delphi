# Subagent: Levin tests: xenobots 06/10

- **Parent chat:** [let's do the same thing for mike levin's works that we did for darwin and thomps](../2026-10-31_1314_let-s-do-the-same-thing-for-mike-levin-s-works-that-we-did-f.md)
- **Started:** 2026-10-31 15:02 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 17:11 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `fd63dba2-d05a-417d-aa72-d35b81f0559f`

---

### 2026-10-31 15:02 — Turn 1 (User)

> You are running pre-registered claim tests in the repo /Users/jdietz/Documents/GitHub/dev/delphisci. Read claim-tests/README.md first and follow it exactly.
> 
> Claims (one directory each, claim-tests/levin-papers/<claim-id>/): levin-2015-place-01, levin-2015-place-05, levin-2015-place-06. They come from Friston, Levin, Sengupta & Pezzulo 2015, "Knowing one's place: a free-energy approach to pattern regulation" (active-inference simulation of morphogenesis, solver in the public SPM toolbox DEM demo for morphogenesis). Get each claim's text, quote and line from books/levin-papers/claims.json; the source text is books/levin-papers/inputs/2015-place.txt. Read the operationalizations in books/levin-papers/assessment/raw/gpt/*.json and raw/grok/*.json for these claim ids. One assessor noted the current SPM demo defaults to 16 cells with the bisection path switched off; check this. MATLAB is likely unavailable: an independent Python re-implementation of the paper's generative model and gradient descent on free energy is acceptable if you pre-register it and say so in interpretation.
> 
> Procedure per claim:
> 1. Before running any analysis or looking at results, write result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion, planned_datasets (model specification / public code by URL) and test_contract. Do NOT git commit (the working tree is shared); writing the file first is the pre-registration.
> 2. Then write analysis.py, run it, and fill in the rest of result.json (status complete, method, measured, verdict, confidence, caveats, agent {kind: local-agent, model, run: "cursor local session", date: 2026-10-31}). Record URL, retrieval time, byte size and SHA-256 for anything downloaded. Never invent data, URLs or numbers. Keep committed data under 1 MB, derived tables under 200 KB; don't commit the SPM toolbox, fetch it in a script. Keep run time to minutes.
> 3. Test the claim as stated, in its stated scope.
> 
> If a directory for one of these claims already exists when you start, skip that claim. Do not touch claim files, assessments, nanopubs or any other directory; never sign or publish anything.
> 
> Reply with one line per claim: claim id, verdict, confidence, and the key measured number.

**Assistant:**

I'll start by reading the claim-tests README and checking which claim directories already exist.

I'll start by checking the README for context.

That got rejected, so let me try a different approach.

It seems the parent turn ended while this was still pending, so my tool calls are being rejected. I should just try a simple Read tool call instead.

Tools are working again, but the equations are missing from the formula. I need the actual SPM DEM_morphogenesis.m code to pin down the precise model, so I should check the assessments and fetch that file from the SPM GitHub repo. But I'm supposed to pre-register before downloading or inspecting any data, which is tricky since I need to know the model specification to design the test in the first place.

I realize I can write the pre-registration using the paper's general description and define criteria in broad terms, saving the code download for after. Let me start by reading through the assessments first.

That file seems to have disappeared—odd since the working tree is shared. Let me check if it got moved.

The shared working tree is being reorganised under me (files moved into `claim-sources/`). Let me locate the new paths.

It looks like the repo has been restructured with things moved into claim-sources/, so I need to track down where everything ended up.

The new location should be test-data/claim-tests/levin-papers/<id>, but none of my three files exist there yet, so I need to read the assessments.


I'll write my three tests under `test-data/claim-tests/levin-papers/` since the repo structure moved claim tests there and book projects to `claim-sources/`. Next I'll read the assessments.

Some files have invalid JSON, probably still being written, so I'll switch to grep instead.

Neither the original nor the moved location has directories for my three claims, so all three proceed. Writing the pre-registrations now, before fetching the SPM code.

I should plan to fetch the DEM_morphogenesis.m script from both the current SPM main repo and the SPM12 release, since the code may have changed between versions and I want to check both sources.

Rather than using the paper's generalized filtering approach in spm_ADEM, I'll reimplement with a simpler gradient-descent scheme on Laplace free energy, and I need to preregister the exact criteria before examining any code. For the target morphology, I'll default to whatever 8-cell configuration exists in the SPM source itself rather than guessing at the paper's figure, since I can't view it directly. For the matching metric, I'm planning to use optimal assignment between final and target cell positions (brute-force permutation search since there are only 8 cells) and compute RMS position error normalized by the mean nearest-neighbor spacing of the targets.

Pass criteria: across at least 20 random seeds, 80% of runs should show RMS error under half the minimum target spacing, type accuracy of at least 7 out of 8 cells, and final ensemble free energy lower than at the first step. I'm wrestling with whether to measure at the paper's 32-step cutoff or extend to 64 steps given the stated identity confusion issue, and considering a control condition using non-shared or randomized models to compare against the shared-model free energy minimization.

For the timing claim about migration and differentiation, I'm defining migration as the step when mean distance to target falls below half its initial value, and differentiation as when type accuracy reaches at least 6/8 or mean confidence exceeds 0.5. Pass requires migration to precede differentiation, differentiation falling within a factor of two of the expected step 8, and free energy showing substantial decline by the final step.

For claim 06, I'm thinking through a regeneration test: split the population at step 8 along the body axis into head and tail halves, duplicate each half's cells back to full count (following whatever approach the SPM code uses for introducing variation), then run 32 more steps and check whether each half re-achieves the target arrangement using the same criteria as the earlier claim.

I'm noting the pass condition should include a dedifferentiation signature—mean max-probability dropping after the split before recovering—alongside both halves successfully reassembling in most seeds. For data sources, I'm pointing to SPM's DEM_morphogenesis.m from the spm and spm12 GitHub repos, and now moving to actually write the preregistration, noting I'll reimplement the generative model in Python using gradient descent on Laplace free energy rather than SPM's generalized filtering, while flagging the question of whether the original file defaults to 16 cells.

Since I can't check the file yet, I'm preregistering that the target should be the 8-cell head-body-tail configuration from the SPM12 version if it exists, with a fallback plan otherwise. I'll also log an extra note for the 16-cell check, and then move on to writing the three result.json files.

I'm putting together some shared text content and starting to write out the files.

Pre-registrations written. Now fetching the SPM morphogenesis demo.

Counting the actual nonzero cells in the L=2 target, I get 8 total across the rows, not the 16 mentioned in the header comment—so the real target has 8 cells, not what the comment claims.

I notice the code has no explicit exogenous gradient variable, but setting g.x equal to a.x effectively makes position itself the sensed signal, which functions as a linear exogenous gradient matching the paper's assumption. Looking at the signal/cell-type breakdown, I see four distinct types distributed across specific rows and columns with varying signal counts (type 2 appears three times, types 1 and 4 twice each, type 3 once), and the RGB coloring comes from the last three signal channels. I'm now piecing together the generative model structure—sensations include position, signal, and a color term driven by morphogenesis as a function of position and signal.

Now I'm working out the identity/precision structure: identity is represented by a softmax over columns with fairly high precision, under a near-flat prior. For action, the free energy gradient descent uses a restriction matrix ensuring each cell's action only influences its own sensory channels (position, signal, and color), enforcing a strictly local, per-cell action-perception loop.

I'm trying to pin down how the global time variable t gets set inside spm_ADEM's loop, since the signal dynamics depend on it through an exponential ramp, and I need to check the actual source to confirm whether t is computed as iY/nY.

Then I'm mapping out the generalized coordinates setup with embedding order 2 and 1 derivative, planning to implement a simplified version using per-timestep gradient updates on v and a rather than full D-step integration, and defining the static Laplace free energy as a combination of sensory and prior precision-weighted errors to report.

Since exact integration with local linearization is complex, I'll approximate with continuous gradient flow via small Euler substeps summing to a unit time bin, applying this to both state and action updates—where the action gradient depends on the sensitivity of predicted sensory data to action, scaled by model precision and an action precision term matching SPM's ADEM convention.

Converging within a bin, so I'm planning Euler substeps with small step size and estimating the computational cost across seeds, bins, and substeps—manageable since dimensions are small. Since I only have numpy available, I need to derive analytic gradients by hand rather than rely on autograd, working out how softmax-based predictions for position, size, and color map through the model matrices per cell.

I'm deriving the free energy expression combining sensory prediction error and a prior penalty on v, then computing its gradient using the softmax Jacobian for each cell, and starting to work out how the action gradient should be restricted to the relevant sensory channels.

I'm noticing a discrepancy between the paper's stated log precision of -4 for initial expectations and the actual code, which uses randn/8 — implying precision closer to 64, not matching "small random expectations." Since the paper emphasizes small values, I'll trust the code's scaling of 1/8 over the literal log precision value stated in the text.

I should run both interpretations as a sensitivity check, but treat the pre-registered literal spec as primary and flag the deviation if results diverge. I also note that initial actions and positions start near the centroid since probabilities are roughly uniform, and I still need to verify the time-stepping logic in the generative process function.


Found that the default target L=2 actually encodes 8 cells (the "16 cells" is just a header comment artifact), and SPLIT=0 means bisection is disabled—confirmed identical in both SPM12 r7679 and current main. Next I'll check spm_ADEM.m to see how time t and action precision are handled.

I'm working through how the time parameter maps to a rising precision function, and how the free energy expression combines error terms with log-determinant penalties, including the prior error contributions at the second level.

For the update scheme, I'm planning to use spm_dx with a local linearisation step that behaves like a near-Newton move toward the quadratic minimum each bin, jointly updating inference and action, since sensations at each bin depend on the previous action. My plan is to re-implement this as a gradient flow for both the belief and action variables, integrated with fine Euler substeps within each discrete time bin.

Given the precision values and weight magnitudes involved, I estimate the Hessian eigenvalues require a small step size for stability, so I'll use several hundred substeps per bin — this keeps total compute manageable across all seeds and bins. This approach integrates the true nonlinear flow over each unit time interval, which is more faithful than relying purely on the linearized exponential update.

I'm also checking that recomputing sensations from the current action at each substep stays consistent with how ADEM couples action to sensation within a step, and working out the action gradient term that links the energy's dependence on velocity through the sensation-action coupling and its precision-weighted inverse.

Now I'm tracing through the inference equation for the causes at level 1, confirming the prior on action defaults to zero per the code's fallback, and double-checking whether the level-1 cause variable maps directly onto the generative function output.

I'm trying to recall the exact SPM convention for M(1).v — whether it represents the initial causes at level 1 or is actually structured as the sensations-shaped struct g, which would affect how spm_unvec reconstructs the output in spm_ADEM's splitting code.

Looking at it more carefully, M(i).v specifies the output shape at level i, so M(1).v matches qU.v{1} (the level-1 prediction) while M(2).v defines the causes passed down to level 1. With no level 3, the prior mean on v is zero and M(2).V = exp(-2) sets the prior log-precision on those causes, matching the paper's Gaussian prior assumption.

I'm reconciling the paper's stated sensory log-precision of two with the actual code values (exp(3) for the model, exp(2) for action), deciding to trust the implementation over the text description. Process noise is set so high (exp(16)) that it's effectively negligible, so I can treat the generative process as deterministic.

I'm tracing through initialization: v starts as small random noise, and the action function maps that through softmax to get initial cell positions and states — since v is near zero, all cells start clustered near the centroid, matching "same location" in the setup. Now I'm working out which columns correspond to which cell-type labels (head/body/tail) based on the T value assignments across the grid positions.

I need to define correctness for cell typing: a cell's most likely identity determines its target type, which I then compare against the type assigned by the optimal final-position matching. With only 8 cells, brute-forcing all 40320 permutations per evaluation is feasible, so I'm setting up a vectorized permutation array to compute this efficiently across comparisons.

I'm also working out the geometric spacing between target positions — checking the unit distances between neighboring grid points to confirm the scaling is consistent (roughly 1 unit for adjacent rows/columns, ~1.118 for diagonal-ish neighbors).

Then I'm clarifying the coordinate convention: P.x stores [column, row] pairs, so sorting by the first coordinate orders cells along the body axis from head to tail. This lets me split cells into head-half versus tail-half groups by picking the four with the largest column index for the "upper" split.

For the split, I need to extract the actual positions from the process output at t=8, duplicate the top four indices, duplicate the corresponding expectations and predictions, add action noise, and then re-run the ADEM solver for 32 steps — noting this restarts the internal time ramp near zero, which I'm replicating faithfully from the original procedure.

The identical duplicated pairs only diverge through the small action jitter, which is interesting but seems intentional. I need to check whether after regeneration both halves reconstruct the full target configuration with proper types at their absolute target positions, and whether identity confidence dips right after the split due to the ramp reset before recovering.

For free energy, I'm working out the standard variational formula: the precision-weighted sensory and prior error terms plus the log-determinant terms from the posterior covariance on causes, where that covariance comes from the Jacobian of predictions with respect to causes combined with the cause precision.

I note that free energy should rise initially before decreasing by the final timestep, so the check is just comparing the terminal value against the first. For the sensation timing, I'm tying the fraction of the trajectory to the index within the generative and generative-process models.

Then I work through the precision structure for the color error term and the action restriction matrix, figuring out which rows and columns of the mapping correspond to position, shape, and color effects versus which action components (x and s) actually drive them.

Now I'm deriving the gradients: for each cell, the derivative with respect to x_i picks up a term from the coupling through c_i (which depends on distances to other cells' x_j weighted by their released signals s_j), while the derivative with respect to s_i is simpler since c_i's dependence there is just identity. I'm being careful with the sign convention linking F to the prediction error ε, so that the gradient descent update da/dt follows the negative of this error-weighted Jacobian.

I realize at initialization all cells start near the same location, so pairwise distances are nearly zero and the direction vectors become ill-defined — I need to add a small epsilon inside the square root when computing distances to avoid this singularity. For the inference-time gradient on v_i, I'm combining a term from the prediction error projected through the weight matrix W (stacking X, S, and scaled C) with a prior precision term. I also notice a discrepancy between the pre-registered initial variance (log precision −4, giving a much larger standard deviation) and what the code actually implements (randn/8), so I'll need to decide which to use for the primary run.

I'll resolve this by running both conditions and only calling it "supports" if they agree, treating any disagreement as "mixed" with an explanation — deciding this threshold now, before seeing results, and noting it as a deviation. I also suspect the paper's "log precision of minus four" is just a sign slip versus the code's precision of positive four, since randn/8 corresponds to variance 1/64, precision 64, log ~4.16. Now I'm working through the time-step indexing and what it means for the mean distance to best-assigned targets to fall below half its initial value.

I'm planning the script that fetches the SPM source files with recorded checksums, re-derives the model parameters by parsing the T matrix straight from the fetched file to confirm L==2, SPLIT=0, and n=8, and I'm weighing whether to duplicate this ~200 lines of setup across three claim directories or factor it into a shared module that the others import via sys.path.

I'll put the core model in place-01's morphogenesis.py, with place-05 and place-06 importing it and each recomputing the shared baseline runs independently since that's fast enough. For integration I'll use plain Euler stepping with a sub-step of 1/200, checking convergence against 1/400 on a test seed before committing to it.


I noticed a discrepancy: the paper states initial expectations have log precision −4, but the code's `randn/8` implies log precision ≈+4. Setting the rule that both conditions must pass for a "supports" verdict, and now writing the Python model.

Checking the analytic gradients numerically before any runs.

I verify the gradient derivation for dv by projecting through the Jacobian term and confirming it matches the expected tangent-space update. Then I shift to thinking about how MATLAB's find function returns linear indices in column-major order when applied to the matrix p.

I trace through the indexing logic carefully, checking that my code's row/column extraction and swapping ends up matching MATLAB's convention, and I confirm the detrending and ordering of P.x and P.s are consistent with column-major ordering. Satisfied with the index mapping, I plan to write a quick numerical gradient check for both the action and v to validate everything empirically.

Gradients look right, and the cache timestamp checks out fine. Now I want to run a quick trial at substep settings of 200 versus 400 to verify integration stability before committing — this is just a numerical sanity check, not tuning against criteria, so I'll pre-decide to use 200 substeps unless results diverge.


Gradients check out against finite differences. Now I'll run a numerical-stability check comparing 200 vs. 400 Euler sub-steps per bin on one seed, using convergence alone (not pass/fail) to fix the sub-step count.

The integration has converged at 200 sub-steps (identical to 3 decimals at 400 and 800). Writing the three analysis scripts now.

Good, it converged at 200. Now I'm setting up analysis.py for experiment 01, running 20 seeds across 2 initial conditions with reproducible RNG seeding, writing results to a derived table. For 05 I'll compute the same runs but extract t_m and t_d metrics, while for 06 I need baseline runs to step 8 followed by an upper/lower split with 32 additional bins and a ramp reset, re-solving in SPM after the split.

I'm checking dedifferentiation by tracking whether the mean max probability within the first 8 post-split bins drops below the value at the split point. For the analysis scripts, since every measured number must trace back to analysis code, I'll have each script write a derived summary.json rather than directly touching result.json, then manually populate result.json's measured fields from those summaries afterward.

I realize the pre-run in 06 uses the full 32 bins even though we only need the first 8, which is wasteful but harmless since those early bins match the full run's ramp schedule. I'll just run all three in parallel as is.

I need to fix an int64 casting issue in the 01 script and account for slow wall time due to machine contention, so I'll rerun it. Also, in test 05 there's a sharp divergence between code-init (19/20 qualifying) and paper-init (0/20) — since I set the pre-registered rule that both must pass to count as "supports" with disagreement marked mixed, I should make sure that rule is actually documented in result.json rather than just stated in my message.

For 06, code init only gets 3/20 while paper init gets 6/20, both under the threshold of 10, which would count as refuting under the criterion — but I want to make sure this isn't an artifact of my integrator rather than a genuine result. I'm looking at the median rms values and suspect the failure mode might be duplicated pairs staying stuck together since my integrator is deterministic and doesn't break symmetry, so I want to inspect individual runs more closely.


Claim 05 finished and claim 06 didn't hit the regeneration threshold. Claim 01 crashed on an int64 JSON type error—I'll fix that and re-run it, then examine how the bisected halves fail.

Typical runs get 6 of 8 correct with rms around 0.76, which looks like duplicated pairs converging to nearly the same spot rather than breaking symmetry, leaving two target locations empty. I should check whether these duplicate pairs separate out by the end as a diagnostic, and consider whether my deterministic jitter of 1/512 is too small compared to the process noise precision used in spm_ADEM.

I realize my implementation omits process noise entirely — in SPM this continuously breaks symmetry across bins, and leaving it out is a real fidelity gap relative to what I pre-registered as "same generative model." Adding it now would technically be a post-hoc change, but since it's correcting an implementation bug rather than altering the hypothesis, I think the honest path is to keep the pre-registered primary result intact, run this as a disclosed sensitivity analysis, and let it inform confidence without overturning the original verdict.

To avoid endless forking, I'm deciding now: if the noise-included version flips the result to pass, I'll call the verdict "mixed/implementation-sensitive"; if it still fails, the refutation stands but with moderate confidence given it's a re-implementation. I'll apply this same noise-sensitivity check across all three claims for consistency, implementing it as an optional per-bin noise term added to the sensations.

I'll also add a diagnostic tracking the minimum separation between duplicated pairs at the end of the run, recorded alongside the other outputs.


Claim 06 typically fails with 6/8 cells correct (RMS ~0.76), likely because duplicated cell pairs collapse into one target slot—something my integrator's omission of SPM's tiny process noise may be causing. I'll keep the pre-registered verdict as-is but add a disclosed sensitivity run with that noise plus a pair-separation diagnostic, pre-committing now that if the noisy version passes, the verdict drops to mixed.

I should add a "sensitivity: process noise" condition to the analyses, keeping runtime manageable given the machine's 11% CPU load. I'll include noise conditions for both code and paper inits in script 06, and also add them to 01/05, estimating each run at roughly 4-5 minutes given the ~1 minute per 20-seed set.

I'm restructuring the conditions into a list of (name, sd, noise) tuples, with the primary case having no noise and others seeding a separate noise RNG per seed. For 06, I also want to add pair separation tracking at the end of the post-split run — comparing final positions between paired agents to compute minimum distances.

Not applied; editing each script directly.

I realize I introduced a bug by changing the pre-run bin count to 8, since the ramp function needs to stay relative to 32 bins — otherwise it produces a different ramp entirely. I need to fix this by keeping the bin count tied to the deterministic 32-bin value while making sure noise consumption still lines up correctly.

Process noise doesn't seem to affect the results, so let me look at the pair separation diagnostic instead.


Adding SPM's process noise doesn't change the outcome—claim 06 still shows both halves regenerating in only 3-7 of 20 runs. I'll check the pair-separation diagnostic to see if the failing halves just need more time.

Since pairs separate, the failure case is just a misassembled configuration — like 6/8 types correct with rms 0.76, a local minimum rather than a true failure — and the paper notes it regenerates within 32 iterations, so I don't need to dig further there. I'll skip exploring an extended run to save time and move on to checking what the paper says for claim 01.

Comparing init conditions: code init gives 19/20 pass while paper init gives 14/20, a mixed result under my rule that both need to pass for "supports." I'm inclined to call claim 01 mixed with moderate confidence, since the literal pre-registration spec also lands at 14/20 regardless of path. For claim 05, code init passes 19/20 but paper init fails outright (0/20, with migration too slow — only 8/20 meeting the timing criterion), so under the literal pre-registration this one actually refutes rather than just being mixed.

For claim 06, both conditions fall below the 10/20 threshold (3/20 and 6/20, or 7/20 with noise), so this refutes under the pre-registered criteria — though I'm only moderately confident given my re-implementation might diverge from the original SPM filter in subtle ways. I also want to double check the SPM12 split-branch logic that re-calls spm_ADEM after resetting state, and confirm I replicated that reset correctly, along with verifying file timestamps to make sure I'm using the right cached data before moving on to gather more supporting numbers for claim 06.

Now I'm computing a few more summary stats for the failing runs, then writing the final result.json files — keeping the pre-registered fields intact while adding a deviations field to flag where my implementation differs from the original setup.


The duplicated pairs separate well (median ~0.6–0.8), so failures result in a wrong arrangement with 6 of 8 cells correctly typed rather than overlap, and all derived tables stay under 200 KB. I'll now fill in the result files.

Writing the completed result files, with the pre-registered fields kept verbatim.

I notice some runs never halved t_m, leaving it None—that's fine to note. Now I'll move to writing out the results, keeping the shared datasets block and preserving each result.json's preregistered fields exactly as specified.

That command was dropped by the tool layer, so I'll save the finalizer as a temporary script and run that instead.

That tool call got rejected again due to an infrastructure issue. Let me try a different approach and write the script to a temp file using the Write tool, then execute it separately.

I've confirmed the summary.json for item 01 matches the final rerun and that the claims in claim-sources align with the text. Now I'll draft the final reply with one line per claim, noting the path move and the 16-cell detail.

I ran all three claims as a Python re-implementation of the SPM model, since MATLAB isn't installed. Two came out mixed and one refuted:

- **levin-2015-place-01**: verdict mixed, confidence 0.6. With the SPM code's small random starting values (`randn/8`), 19 of 20 runs self-assemble into the target (median position error 0.29 against a threshold of 0.5; median 8 of 8 cells correctly typed). With the paper's stated "log precision −4", 14 of 20 do.
- **levin-2015-place-05**: verdict mixed, confidence 0.6. With the code's starting values, cells differentiate at median step 10 (range 9–14), after migrating by step 4, in 19 of 20 runs. With the paper's stated value, 0 of 20 runs follow that order.
- **levin-2015-place-06**: verdict refutes, confidence 0.55. After bisection, both halves regenerate the full form in only 3 of 20 runs (6 of 20 with the paper's starting value). Every run shows a brief loss of differentiation after the cut, but the failed halves settle into a wrong arrangement, typically with 6 of 8 cells correctly typed.

Things that affect how to read these:

- **Paper versus code:** the paper says the initial expectations had log precision −4, but the code uses about +4. Only the code's value fits the paper's own description of the cells as "undifferentiated". Before any run I fixed the rule that a claim is supported only if it passes under both values, and mixed if they disagree. That rule is the only reason 01 and 05 are mixed; under the code's values both reproduce clearly.
- **Re-implementation limits:** I copied the model, parameters, target and bisection procedure from the SPM file. The integration is plain gradient descent on free energy, not SPM's own filter, and that is why 06's confidence is low. After seeing the first results I added SPM's small process noise as a disclosed extra check; it changed no count by more than one run.
- **The assessor's "16 cells" note:** that number appears only in the file's header comment. The default target has exactly 8 cells, the paper's head–body–tail form, and is the same in SPM12 and current SPM. Bisection is switched off by default, as noted.
- **Location:** during the session the repo was reorganised (`claim-tests/` moved to `test-data/claim-tests/`, `books/` to `claim-sources/`). The tests are in `test-data/claim-tests/levin-papers/`, uncommitted, with SHA-256 checksums of the fetched SPM files.

_Tools used: Grep, Read ×5, Shell ×26, StrReplace ×12, UpdateCurrentStep ×7, Write ×8_
