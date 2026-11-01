# lamm-mit has a categorytheorydesign repo you think we might end up with some the

- **Started:** 2026-11-01 01:56 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 10:01 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 4
- **Subagents:** 0
- **Transcript ID:** `3ccac269-0cf4-4487-b0af-71736a2d473e`

## Conversation

### 2026-11-01 01:56 — Turn 1 (User)

> lamm-mit has a categorytheorydesign repo you think we might end up with some theorems or usable code fro mthere

**Assistant:**

I'll look at the repo first.

The user wants details on lamm-mit's categorytheorydesign repo, so I should fetch it from GitHub to check it out.

This ties into our plant-hygromorph-mechanics project, fitting Marom et al.'s category of stimulus-response systems. I want to check what we already have and look at the gh_scripts' core physics.


This repo contains the code for the Marom et al. paper, which our `plant-hygromorph-mechanics` project already cites for its stimulus–response systems category. I'll compare our work against the repo's code.

I'm double-checking why the files ended up in the current directory instead of /tmp/ctd — it looks like the mkdir and cd chain actually did succeed after the earlier commands ran, since the directory listing came back populated.

Also I notice the plant-hygromorph-mechanics workspace directory isn't showing up in the repo or git status, which doesn't match what AGENTS.md describes, so I should check the actual cwd and repo state to confirm what's really there.

The working directory persisted in /tmp/ctd, so I should just read files from there directly and use absolute paths when looking in the repo.

I notice the repo structure now has engine/ and site/ directories, so I should look there for the hygromorph claims.

I'm checking what else from the repo remains unformalized—candidates like the functor F from Nat to Art, its preservation of simulation under composition, the compilation functor E, and how Case III emerges from composing validated components such as the thermal twist arising from thermal stimulus composed with a twist reducer.

I'm also verifying the decoupling theorem: at 0/90° the twist mismatch vanishes, and at ±45° the thickness mismatch vanishes for matched materials, checking whether this orthogonality claim is already covered by existing lemmas like shearStrain_mismatch and axialStrain_mismatch—it seems mostly covered. On the code side, the repo's Python scripts are reference implementations but there's no measured CSV data from the printed specimens to validate against, just G-code and videos.

I should check the printed-bilayer-01 claim test to see what data it relies on, and whether the cases.png figure holds predicted-vs-measured comparisons I could extract numbers from. The spec-to-G-code compiler seems machine-specific and less relevant here. Licensing under Apache 2.0 should be fine if I vendor with attribution, and I want to check whether engine/fabrication already has related printed-bilayer work.

The pre-registered physical test has no data yet, and this repo only gives a predictions pipeline plus a fabricated test with four actuators comparing predicted vs measured values—the real data lives in paper figures, not the repo. I should also verify where the Timoshenko κ is actually computed rather than assuming, so a quick grep is warranted before I comment on it.

Yes, there's a fair amount we can use. The repo is [lamm-mit/CategoryTheoryDesign](https://github.com/lamm-mit/CategoryTheoryDesign), Apache 2.0, the code for Marom, Tibbits, Zardini and Buehler (JMPS 2026). We already depend on that paper. `plant-hygromorph-mechanics` has the claim `stimulus-response-systems-category`, whose proof is Appendix A.2, and `Hygromorphs.lean` already proves the category. It also proves bilayer curvature, antisymmetric twist and the strain mismatches, so the paper's main theorem is already covered.

I only read part of the repo. I read about a dozen of the `gh_scripts`, the READMEs and the file tree. I didn't read `viz.py` or the setup guide in full, and I haven't read the paper.

**Possible theorems:**
- **Composition of the four actuators.** Two stimuli (`stim_hygro`, `stim_thermal`) and two reducers (`beta_bend`, `beta_twist`) give four cases. The paper says Case III arises purely by composition, with no new derivation. A Lean statement could say the pipeline is a composite of independent stimulus and response components, so any stimulus–reducer pair gives a valid actuator.
- **Decoupling of bend and twist.** `beta_bend` and `beta_twist` report the other mode as "crosstalk". At θ = (0°, 90°) the shear mismatch is zero, and at (+45°, −45°) with equal layer strains the thickness mismatch is zero. We already prove the mismatch identities, so this would be a short corollary.
- **Functor F: Nat → Art.** In the code, F only substitutes parameters (`F_fib`, `alpha_1`, `alpha_3`). That is thin, but "F preserves the simulation condition" is a legitimate theorem to state and prove. I'd want to read the paper's definition of F before committing to it.

**Usable code:**
- **Reference implementation.** The `gh_scripts/` Python files are small, pure bundle-to-bundle functions. They are the pipeline from stimulus to strain to tissue projection to element geometry. We could vendor them as an independent check on our Lean laws. The check would compare numerical outputs for random inputs against our `shearStrain` and `axialStrain` definitions. This would catch transcription errors in either direction.
- **Fabrication.** The four G-code files and printer profile (Bambu X1C, PA6-GF/PA612-CF and PLA/CF-PLA) could be a starting point for the physical test `hygromorph-bilayer-curvature/printed-bilayer-01`. That test is still pre-registered. `engine/fabrication/` currently holds only `flying-zebrafish`.

**Limits:**
- **No measured data.** The repo has videos and figure PNGs but no tables, so the "predicted vs measured agree closely" result can't be re-run from it. Getting the numbers means digitizing `figures/cases.png` or asking the authors, and digitized values would be weak evidence.
- **Hard to run.** `comp.py`, `viz.py` and the other Grasshopper scripts import `Rhino.Geometry`, so they need Rhino 8. Only the strain and geometry scripts run standalone.
- **Different from our test.** The actuators are fused-filament prints, not the hydrogel strips in our pre-registered test.
- **Not an organism test.** A match with the model on printed actuators says nothing about pine cones.

I'd start with the numerical cross-check against the Lean definitions plus the decoupling corollary. That is cheap and adds a second implementation to the project. The composition theorem would come next. The prints and any measured data depend on whether we can get the authors' numbers.

I haven't changed anything in the repo. The scripts I fetched are in `/tmp/ctd`. Do you want me to do the cross-check and decoupling theorem, or contact the authors about data first?

I'm trying to recall where κ gets computed—likely in the geo or beta_crv module somewhere. That's enough digging; I'll move on to giving my assessment.

_Tools used: Shell ×10_

### 2026-11-01 08:22 — Turn 2 (User)

> "We could vendor them as an independent check on our Lean laws. The check would compare numerical outputs for random inputs against our shearStrain and axialStrain definitions. This would catch transcription errors in either direction" <-- wlet's try this

**Assistant:**

I need to check the Lean definitions and understand how the repo's data tests and exec manifest work before building this out. My plan is to vendor the standalone scripts under the appropriate claim-tests directory with analysis.py and a result.json following the schema, so I should first look at an existing result.json example with a "computational" data kind and review the exec manifest conventions.

I need to pre-register before running anything — writing a result.json with hypothesis and criteria first, noting the dataset is computational, sourced from the vendored Marom repo scripts with its URL, commit SHA, and sha256 recorded. For the Lean side, I'm weighing whether to transcribe the Lean definitions into Python myself, though that introduces transcription risk since the whole point is independent verification.

Lean reals are noncomputable, so I'm thinking of a different approach: write a small translator that mechanically converts the Lean definitions' source text directly into Python expressions — swapping sine/cosine calls and exponent syntax — rather than hand-transcribing, and have it fail loudly on any unrecognized tokens. I also still need to track down where Timoshenko's coefficient is implemented in Marom's code since I haven't spotted it in the scripts yet, so I'm planning to clone the repo fully and grep for relevant terms across all the files.

I'm lining up three comparison targets: their shear/axial tissue model using the same cos²/sin² angle convention, the Timoshenko element formulation, and our pipeline's end-to-end mismatch theorem relating curvature to the antisymmetric angle term. I'm also checking how their sign convention for the thickness difference term aligns with ours before comparing results directly.

I'll skip the thermal/hygro stimulus term since it's not represented in Lean. My plan is to vendor their Grasshopper scripts verbatim into a dedicated directory with proper licensing and provenance, running only the needed chain — stimulus through fiber force, alpha terms, tissue transform, bending/twisting betas, geometric alpha, and the print/element stiffness — then compare the resulting curvature against the Lean-defined bilayer curvature formula with its axial or shear strain-based mismatch. I'm also noting I need to mechanically translate the Lean definitions from the Hygromorphs file, paying attention to how units are handled in the Timoshenko thickness calculation.

I want to add property checks derived from the theorems themselves — like zero bending curvature at antisymmetric angles with matching material, the shear mismatch formula involving sin(2φ), and verifying Marom's delta_eps_12 computation matches the εL−εT difference at ±45°. I'm also planning deliberate mutation tests as negative controls: flipping a sign or swapping sin for cos in both the Lean-derived and Marom code paths to confirm the harness actually catches the resulting failures, built into the analysis script. Finally I'm considering sampling domains and unit conversions — strain ranges, angle ranges in degrees versus Lean's radians — to make sure the comparison harness handles Marom's degree-to-radian conversion correctly.

Now I'm realizing Marom's output serialization truncates values to fixed decimal places, which introduces meaningful rounding error relative to the magnitude of the quantities involved — small strain or thickness values could see relative errors of 1e-3 or more just from formatting. This means my tolerance for comparing Lean-derived results against Marom's numerical output needs to account for serialization precision, not just floating-point computation error, so I'm working out whether curvature values are computed internally before rounding or derived from already-rounded printed strips.

Tracking how rounding compounds through the strain-to-thickness pipeline, I realize it's cleaner to just enter the computation at a common point with identical rounded inputs on both sides—picking strain values as clean multiples of 1e-4 for chi_L and chi_T so both pipelines start from the same numbers.

The curvature bound should propagate as C_geom*2e-6 plus a tiny numerical floor, and I should expose the ratio of observed to bounded values for sanity-checking. I'm also double-checking that 4-decimal angle formatting is fine since angles are multiples of 0.01°.

Now I'm tracing through alpha_2 and alpha_geo, which compute h and theta from the geo_bundle, then checking that E1 and E2 pulled from the stim_hygro material dict format cleanly as floats without round-trip issues. I still need to verify the S_elem and T_stack paths, and confirm the hygro material string parsing handles chi_L, chi_T, and E correctly.

I'm realizing there are two parallel chains to test: the natural fiber chain (F_fib through alpha_1, alpha_2, T_tis, beta, alpha_geo, S_elem) and the artificial chain (F_fil, L_lay, T_stack, S_print), each using different scripts. Rather than vendor everything in gh_scripts, I want to check which files import Rhino so I can skip those, and only vendor the pure-Python modules needed for both chains to keep things minimal.

I'm deciding to vendor the non-Rhino scripts with LICENSE and PROVENANCE files under a small ~50KB directory, following the per-claim convention of organizing by project/claim-id/run, covering the three hygromorph claims like antisymmetric twist shear/axial behavior.

Since one analysis covers two claims, I'll avoid duplication by creating separate run directories for each claim that import a shared harness script rather than copying the analysis logic twice. I still need to check how the manifest builder discovers tests and whether underscore-prefixed directories cause issues, plus review the verdict schema and remaining result.json fields.

I'm trying to figure out the expected directory structure for results, since the bilayer-curvature example seems to have result.json both at the claim level and nested inside a subdirectory, which is confusing the pattern I'm trying to match against the manifest requirements.

Someone else is actively working on the bilayer-curvature claim-level test right now, so I need to be careful my crosscheck doesn't clash with that directory structure. I'm noting the convention for multiple runs uses overnight-* subdirs with their own result.json, following the pattern seen in turing-ddi's overnight-turing-n4 example.

I'm planning to place my crosscheck work in a `marom-crosscheck-01` subdir under each claim, consistent with the printed-bilayer-01 pattern, so I don't touch claim-level files directly. Since the manifest only reads claim-level results and won't pick up subdir runs, I need a shared harness approach -- putting vendor code, harness.py, and lean_defs.py in a project-level `_marom-crosscheck` directory, then having each claim's run dir contain its own analysis.py that imports the shared harness and writes its own claim-specific result.json.

I'm also thinking through whether that underscore-prefixed directory might be mistakenly scanned as a claim ID by build-claim-graph, but since it won't have a result.json at its root, it should be safe -- I'll avoid regenerating docs by running that tool and just check how load-claims actually scans directories instead. Before running anything, I'll pre-register both claims with preregistered status in their result.json files, and I won't commit without being asked.

For the harness itself, I need to parse the Lean source file for the timoshenkoCoefficient, bilayerCurvature, shearStrain, and axialStrain definitions and translate them into Python -- stripping Real. prefixes, converting ^ to **, mapping unicode identifiers to ascii names, and handling Lean's juxtaposition-style function application syntax into proper Python function calls with parentheses and commas.

Writing a small recursive-descent parser for this Lean term subset...

I need to handle application parsing carefully—bare variables with no args are fine, left-associative operator chains work out. For evaluation, I'll use Python floats against an environment of sin, cos, and user-defined functions, accepting the tiny precision gap from Lean's exact reals versus doubles since it's negligible. I could also check the theorem statements themselves, though that's somewhat outside the main scope.

Rather than parsing out theorem statements directly, I'll hardcode the key property checks (like the shear strain mismatch formula) as named checks referencing the theorem names, computed through my already-evaluated Lean definitions. For the bilayer curvature case, I realize I can do an even stronger independent check: instead of only comparing Marom's result to Lean's closed-form solution, I can solve the underlying equilibrium equations from scratch—setting up the linear system for P1 and κ with P2 = -P1—to verify everything against first principles rather than just against the derived formula.

Now I'm tracing through how Marom's script actually wires its functions together, following the chain from hygroscopic strain through the fiber and matrix properties, bending/twisting coefficients, geometric parameters, and finally into the organ-level output that produces curvature and bend angle, making sure the data (like the laminate state and geometric bundle) passes correctly between each stage.

For the Art side, I'm mapping an analogous pipeline — stimulus to filament strain, layup, stack thickness, bending/twisting coefficients, geometry, printed structure, and object-level output. Since the Lean specification doesn't include a thermal stimulus law, I'm noting that the thermal pathway falls outside its scope, but since the downstream reducers are stimulus-agnostic, the same strain-consuming logic should still apply if I route it through consistently.

Actually, I want to verify this composition claim cheaply: running the thermal chain with chi substituted for alpha and du for dT should yield the same kappa as the hygro chain, which would confirm the Case III stimulus-agnostic composition. This seems worth including since it's inexpensive. I'm now planning a comparison across random draws for each chain configuration, checking quantities like strip strain against the axial strain formula within a tight tolerance.

For the remaining checks, I'm working through tolerances: comparing shear strain and thickness-difference strain with accumulated rounding error bounds around 1e-6, then deriving a similar tolerance for curvature kappa based on the propagated error from the thickness and modulus ratio calculations.

Since kappa itself is printed with 6 decimal rounding, that adds another 5e-7 absolute error on top, so I need to combine that with the C·1e-6 term plus a tiny epsilon for the total tolerance. For typical parameter ranges (h between 0.02 and 0.5 cm, kappa around 0.15), this tolerance should stay comfortably below what mutation testing needs to detect.

I'm deciding the verdict shouldn't be framed as refuting the proof itself — a numerical cross-check can't invalidate a formal proof — but rather as checking whether the formalization faithfully matches the cited equation from the paper. So the pass criterion is: if every draw across all quantity-chain combinations falls within the rounding-aware bound, that supports consistency; if any draw exceeds it, that calls into question whether the Lean definition matches the source.

To validate the harness itself, I'm planning mutation tests: injecting deliberate faults into both the Lean-side formulas (like swapping sin(2φ) for sin(φ), flipping a sign, dropping a factor) and the Marom-side reference code (altering the angle conversion, swapping squared trig terms), then requiring the harness to flag at least 6 of these faults in nearly all draws — confirming the detection logic actually catches discrepancies rather than silently passing.

I'm checking that the strain values, derived from chi and humidity differences with decimal step sizes, stay exact enough in floating point that rounding to six decimals won't introduce spurious errors—the granularity works out to exact multiples of 1e-6 so binary representation error is negligible.

I'm also setting ranges for angles (degrees in 0.01 steps between -90 and 90), layer thicknesses (0.0001 steps between 0.01 and 0.5), and log-uniform moduli between 100 and 20000, rounding each to a reasonable precision for string formatting, plus adding an antisymmetric subset where the second angle mirrors the negative of the first with matching material.

I want to use this subset to check theorem consequences — bending curvature vanishing within rounding tolerance and twisting curvature matching the predicted expression — via property checks, pre-registering 500 samples for this test. I'm also wondering whether the four shipped example cases have their material parameters documented anywhere outside the Grasshopper panels, and plan to check the setup guide for possible chi_L values.

The setup guide actually lists real material panels like PA6-GF, so I can use the four shipped cases as deterministic checks by reproducing their predicted κ values. I want to check lines 100-135 for the geometry and material values, then build a section computing the Marom-predicted κ and b_angle for comparison against Lean, keeping an eye on rounding since alpha_L=1.0e-5 prints to six decimals.

I should set up the preregistration using the slider domain for h, noting that only PA6-GF has documented hygroscopic data while PA612-CF isn't listed. I'll skip the full four-case reproduction since PLA values are unavailable, relying on random draws instead, though I might reference the one worked example in the guide around lines 210-220.

Since the PA612 values are missing, I'll skip that worked example and move to writing the preregistration for the two claims, targeting the antisymmetric-twist and bilayer-curvature result directories. I should check whether the antisymmetric-twist directory actually exists in claim-tests, since my earlier listing only showed bilayer-curvature under plant-hygromorph.

I need to verify that creating a subdirectory under the claim directory won't confuse other tooling, like build-claim-graph scanning for result.json files, so I'll check how load-claims actually reads test directories.

Since subdirectories are supported and my run becomes the headline top-level result, the antisymmetric-twist claim will effectively be treated as tested via my computational data, which seems acceptable given the infrastructure rules. Now I should preregister, deciding where to place the vendor/harness files, likely under a crosscheck subdirectory within the plant-hygromorph-mechanics folder.

I need to figure out directory structure so both claims get valid result.json files without breaking manifest loading. I'll put the shared harness, vendor files, and analysis script inside the twist run directory, with the bilayer run directory containing a thin wrapper analysis.py that calls the shared code so both write their own results — avoiding cross-directory import complications while keeping things simple.

Now I'm defining the pass criteria: for the twist claim, checking that strain and mismatch quantities across 2000 random draws per configuration match the Lean-defined formulas within a tight rounding tolerance, with mutation testing requiring at least 90% detection across a preregistered set of eight mutants split between Lean-side and Marom-side implementations.

Continuing the mutant list: M2 removes the degrees-to-radians conversion for theta_2, M3 swaps the multiplication for division in S_elem's ratio term, and M4 flips a subtraction into an addition in beta_twist's d_12 computation. I'm noting that each mutant should trigger a rounding-bound violation in at least 90% of draws for its configuration, and I'm starting to pre-register what would count as a control failure.

I'm also working through a secondary check comparing thermal versus hygroscopic chains that should yield the same kappa when alpha equals chi and dT equals du — deciding on appropriate decimal precision and integer grids for alpha, dT, and du so the comparison stays consistent across both chains.

I'll expand the twist set to cover 8 configs (2 stimuli × 2 chains × 2 responses) with 1000 draws each, and define the verdict rule: support if all tests and controls pass, refute if any no-mutation config exceeds bounds, otherwise inconclusive. For the bilayer claim, I'm setting up a comparison against the Lean bilayer curvature function using the same draws with a composite error bound.

I need to account for the mismatch since Δ_active in Lean uses exact axial/shear strains, so the bound should combine rounding error with print rounding. I'll also add an independent equilibrium solver check—computing curvature from the linear system in the equilibrium theorem's hypotheses and comparing it both to Marom's formula and to Lean's closed form (a redundant but cheap self-consistency check), plus verify sign conventions match between Marom and Lean.

Both conventions agree that curvature is positive when the top layer stretches, so the sign check passes. With E1=2850.0 confirmed from the bundle, I'm ready to write the preregistration JSON files, dated today with the cursor-agent kind and the model name formatted appropriately.


I'll pre-register pass/fail criteria and fault-injection controls before testing whether the published Python and our Lean definitions compute the same functions.

Pre-registration is written. Next I'll vendor the unmodified scripts, then write the term parser that reads the definitions straight out of the Lean file, and the harness.

I'm planning to vendor only the necessary scripts from gh_scripts (the chain and stim files), skipping viz, comp, and machine-specific ones, and include a LICENSE and PROVENANCE.md documenting the source commit and checksum. I'm also starting to think through the antisymmetric set analysis for layers with equal materials.

Now I'm designing a parser for the Lean source files that extracts function definitions, their arguments, and bodies using regex, handling comments and multi-argument signatures. I'm also working out a tokenizer regex that correctly matches identifiers including Greek letters and subscript characters.

For mutation testing, I'm applying string replacement on the body text and asserting the replacement actually matched something. For evaluation, I'm planning to precompile scripts and execute them per draw across configurations and mutants using plain Python floats, estimating the total exec count stays manageable performance-wise, with each script given its own namespace containing bundle inputs and importing math itself.

I'm checking the sampling domain for the thermal grid parameters, noting that even though some generated values like extreme temperature deltas push expansion terms into unrealistic percentage ranges, the absolute error bound still holds since the tolerance constant scales appropriately with those magnitudes.

Checking the other bounds with T_cur, T_ref, and dT ranges, the precision stays well within tolerance even though the overall range exceeds physical realism — I'll just flag that in the interpretation and move on. The redraw already guarantees the chi difference threshold, and the eps calculations from exact multiples hold up fine under floating-point rounding.

Checking Marom's κ computation against the rounded es bundle values, the error stays within acceptable bounds since h and other intermediate values sit on the proper grid. I'm now tracing the full computation chains for both the natural and Marom pathways, following how stimulus propagates through fiber force, lamina growth, tissue temperature, and geometric alpha functions to reach the final element response.

Then I'm mapping the parallel "Art" branch through filament force, layer growth, stacking, and print geometry alpha functions to reach S_print, checking that each stage's file signatures (like alpha_2_prime taking bundle_in and geo_bundle) and thermal/beta components all exist consistently with their natural-branch counterparts.

I'm compiling the full list of 23 variable names to fetch, then considering that mutants M1/M2 only apply to T_tis, so I need to trace which downstream natural-branch configurations are actually affected by those mutations.

For fairness I realize I should mutate T_stack in parallel with T_tis rather than leaving it untouched, since both carry equivalent code paths. I'm working out detection rates per mutant: M1 alters a sine term that flows into delta_12 comparisons across every configuration, M3 alters kappa affecting all configs similarly, and M4 only touches twist-related configs, so detection has to be defined as any compared quantity exceeding its bound in a given draw.

I'm mapping out which Marom bundle quantities (strip strains, deltas, kappa) need to be compared against the Lean-side exact evaluations, noting that the strain values use radians computed from theta, which is where mutations like M2 would show their effect.

I'm flagging the degrees-to-radians conversion as the one genuine harness-side translation, since Lean itself operates in radians while the harness converts from degrees. Then I'm working through the Lean mismatch formulas for Δthk, Δ12, and κ via bilayerCurvature, along with the tolerance bound using timoshenkoCoefficient, before setting up the equilibrium solver equations for the unknown P1 and κ.

I'm deriving the force-balance and strain-compatibility equations, substituting the eigenstrain difference Δ as ε1−ε2, solving the resulting 2x2 system numerically, and comparing the computed curvature κ_eq against κ_lean with a relative tolerance to confirm they agree.

For the numerical setup I check that the elastic modulus and thickness ratios stay well-conditioned in double precision, then move to the antisymmetric configuration (θ2=−θ1, shared modulus and chi, free thickness). There I verify that thickness-driven strain mismatch stays near zero and that the shear strain component matches the (εL−εT)·sin(2φ) formula, coded directly from the Lean theorem's statement, before running batches of randomized trials per branch.

Now I'm defining the overall verdict as the worst-case ratio of error to bound across all compared quantities, logging per-quantity errors, mutant detection rates, and draw counts, then splitting results by claim—twist-related strain and control checks versus bilayer curvature and equilibrium checks—to build the two result files.

M4 doesn't apply to bilayer configs, only twist ones, while M1, M2, L1, L2, L3 are relevant across all configurations. Checking L2's swapped sin²/cos² error in the axial direction, the detectable discrepancy scales with cos2φ and should exceed the 5e-7 threshold except near special angles where cos2φ is nearly zero—so detection should generally succeed there.

Similarly, L1's and M1's errors vanish only at φ=0 or ±60°, which is rare, and L3's error is small only near φ=0/±90° grid points, also rare. For L5's kappa mutation, detection fails only when n=1, which is unlikely given the log-uniform random sampling. I'm now estimating the computational cost: running 1000 draws across 8 configs and 4 mutants means roughly 32,000 chain runs, each requiring about 12 executions, totaling around 400,000 executions of precompiled code—likely taking 30-60 seconds.

I can optimize by noting that Marom-side mutants only need re-running for affected configs (M1/M2/M3 need all 8, M4 needs 4), while Lean-side mutants can reuse cached unmutated Marom outputs and just re-evaluate the mutated Lean expression, so I'll cache Marom outputs per config per draw in memory with a single seeded RNG for deterministic, fixed-order draws.

Now I'm planning the file structure: a vendor directory with scripts and provenance docs, a lean_eval.py, a pipeline.py for chains, and an analysis.py that writes result.json fields into both claim directories while preserving preregistered fields and setting status, method, measured, verdict, confidence, and caveats—with the bilayer directory's analysis.py acting as a thin wrapper that invokes the main Marom-crosscheck analysis script.

For updating result.json, I'll load the existing file, assert its status is preregistered or complete, then update the status, dataset hashes, method, measured, verdict, confidence, and caveats fields while keeping prereg fields intact across repeat runs. For the Lean source path, I need to work out the relative traversal from the analysis directory up through the claim-sources tree to reach the Hygromorphs.lean file—I'll compute this with Path parent traversal rather than hardcoding it.

I'm double-checking operator precedence and parsing order for the trig expression involving cosine squared and sine of double angle, making sure multiplication and exponentiation are grouped correctly.

The parser is working, so now I'm moving to the pipeline and analysis script. I'm cataloging the specific mutation text replacements needed across the vendor source files, like swapping sine function arguments and modifying radian conversion lines for theta parameters.

I'm also tracking the M3 and M4 mutations - a division-versus-multiplication swap in element strain calculations, and a sign flip in the d_12 twist angle formula. I notice something important: since S_elem recomputes d_12 independently rather than relying on the beta-stage value, the final kappa result doesn't actually depend on beta_twist's mismatch calculations, meaning I need to capture intermediate bundle states separately to properly detect the M4 mutation since the pipeline isn't strictly compositional in how data flows through stages.

Now I'm working through the pipeline's draw generation and data formatting logic, covering material string formatting, environmental and thermal parameters, and how strain values get derived from displacement deltas for the Lean calculation step.

I check that computing eps using the exact du versus parsing it from printed six-decimal values matches within floating-point tolerance, since the chi grid spacing and RH increments both land on exact multiples that avoid rounding mismatches.

I'm now setting constraints requiring the chi_L and chi_T difference to exceed 0.005 per layer on the integer grid, and designing antisymmetric hygroscopic draws where both layers share material properties but theta2 is the negative of theta1. I'm starting to define a comparison function that checks error/bound ratios across quantities like strip epsilon values.

Now I'm mapping out the remaining comparisons: shear terms, the beta-bundle delta_eps checks against axial and shear differences, and the kappa curvature comparison with its tolerance bound. I'm also noting that the printed kappa value is actually the active one, so I want to double-check κ_bend and κ_twist derived from the C coefficient against their own bundle quantities as additional validation.

For the mutation testing strategy, I'm planning to perturb the Lean-side definitions and rerun comparisons against unmutated Marom outputs, flagging detection whenever the max ratio across a claim's quantities exceeds 1, then doing the reverse by mutating the Marom scripts while keeping Lean fixed. I'm also defining the scope of quantities tied to each claim—twist-related terms like the strip strains and their differences plus antisymmetry, and bilayer-related terms like kappa and its bend/twist components.

I'm mapping which specific mutants (L4, L5, M3, M4) are relevant to which claim scopes, restricting detection-fraction calculations to configs where the fault actually matters, and separately verifying the equilibrium solver against each unmutated draw using the active delta from Lean, plus checking Marom's antisymmetric outputs stand on their own.

For property checks I'm computing ratios of strain mismatches against tolerance bounds using the shear strain formula with the mismatch angle, applied across both antisymmetric beta sets. I'm also estimating the total runtime budget — roughly 100k executions across configs, antisymmetric sets, and the Marom mutant variants — to make sure the test suite stays feasible.

Now I'm mapping out the natural vs artificial chain naming conventions for each stage (stimulus, fiber, lamina, tissue, bending, geometry, element), and double-checking the alpha_2_prime and L_lay branches to confirm they're wired correctly.

I'm planning the test inputs — material/humidity or temperature pairs for the stimulus functions, and geometric parameters feeding through geo.py to produce the geometry bundle. For results, I'm structuring the output as a measured dict capturing the headline max-ratio value, its unit as a rounding-bound comparison, the draw count, and a note that uncertainty is deterministic rather than statistical, with per-claim breakdowns for twist and bilayer quantities.

The verdict logic should support the claim if all ratios stay at or below 1, antisymmetry properties pass, and equilibrium relations hold to a tight tolerance for the bilayer case, with controls passing at least 90% of the time — I'll set confidence around 0.9-0.95 given this is deterministic computation. I also need to record SHA256 hashes and metadata for the vendored files, using the GitHub raw URL, retrieval date, byte size, and hash, settling on a fixed retrieval timestamp, and I should cross-check the vendor file hashes against the published SHA256SUMS file.

I'm verifying the anti-symmetric term formula matches the expected (εL−εT)sin2φ expression, and checking that the Lean proof's whitespace-normalized body for the L3 case correctly aligns with the mutated definition.

Checking the axial strain body text and the scope detection tally both look correct, with the M3 fault not applying to the twist scope anyway. I'll do a quick smoke test of the chain before running the full timed execution.

I'm suspecting the dict eagerly computes every branch including a**b, which could blow up if one operand is a huge exponent, so I'm tracing through which node might have a large base and exponent causing a "Result too large" error.

I'm checking the ratios against the rounding bound—most stay below 1, with a few samples near 0.98, which seems close given the worst-case nature of the bound. With thousands of draws, I'm wondering whether the max ratio could actually tip past 1, so I'm examining the strip error terms more carefully.

For the thermal case specifically, I'm tracing through the error propagation in computing κ and eps: float noise from squaring cosines, relative errors in the distance term, and whether both sides use consistently rounded values. Since the bound margins look tight but still sufficient in each scenario I check, I'll just run the code to confirm.

I notice the ratio saturates exactly at 1.0 for these strips because errors approach the 5e-7 half-grid bound, which is expected behavior with the small slack factor added, so that confirms things check out.

The pass criteria all line up—headline ratio stays under 1, detection rate is near-complete with just one missed draw near the angle origin, and the run completed quickly despite the large number of chains. I should verify the preregistration fields match (fault detection list, M4's twist-only scope), then write the analysis wrapper and rerun to confirm determinism by diffing the result.json output.

Wait, the working directory doesn't exist? Something must have removed it—I should check what happened.

It looks like the repo structure has changed — the engine/ directory may no longer exist, with files reverted to root. I should check if engine is still there with an ls.

Someone ran a hard reset outside my control, undoing the engine/ restructure commits, so the repo is back to the pre-restructure layout. I need to check whether my files under engine/ survived as untracked since that directory was already committed before the reset.

It looks like the repo got reset to its pre-engine layout, likely intentionally by the user, and my untracked files only partially survived — the marom-crosscheck-01 analysis files are there but vendor/ and .gitignore seem to be missing.

I'm checking whether my analysis script's relative path logic for the engine directory still resolves correctly under the new root layout, and it looks like it does for both old and new structures. I still need to verify the Lean file is unchanged, recreate the missing vendor directory and files, confirm whether the twist dir's result.json is the completed run or just a prereg stub, and make sure the reset didn't corrupt the preregistered files too.


The repo layout shifted unexpectedly — main was reset to 1605b923, undoing the engine/ move and wiping my vendor/ directory and wrapper. I'll check what's left in the repo now.

The files survived and only the rejected command never ran. I'll redo the wrapper and `.gitignore`, then rerun on the new layout to confirm it still passes and gives the same output.

Most files survived and vendor exists with 28 entries — it was just the wrapper and .gitignore that never got created since that rejected command didn't run, and the directory vanishing was actually just a shell cwd reset. I'll redo that rejected command from the correct working directory, and also recheck the Lean file at the root layout to confirm it matches the engine path version before rerunning analysis.

The check passes: the Lean definitions and the code published with the paper compute the same functions. I ran both claims, `hygromorph-antisymmetric-twist` and `hygromorph-bilayer-curvature`, and both came out `supports`.

**What it does**
- **Published code:** it runs 23 components from the paper's `gh_scripts` unmodified. They are pinned to commit `fa8100b` with Apache licence and hashes, and the script refuses to run if any were edited. They are wired as in the repo README: stimulus, fibre, lamina, tissue, bend or twist reducer, element. Both the natural and engineered branches run, for hygro and thermal stimuli.
- **Lean side:** a small parser, `lean_eval.py`, reads the definitions straight out of `Hygromorphs.lean` (`shearStrain`, `axialStrain`, `timoshenkoCoefficient`, `bilayerCurvature`). Nothing is retyped, so a later edit to the Lean file is checked automatically.
- **Extra check:** for the curvature claim it also solves the force, moment and compatibility equations that `bilayerCurvature_ofEquilibrium` assumes, as a linear system.

**Results**
- **Pre-registration:** the criteria were written before the first run. The result files keep them unchanged.
- **Draws:** 8,000 random draws across 8 configurations, plus 2,000 antisymmetric ones.
- **Agreement:** every shared quantity matches within the pre-registered rounding bound. That bound exists because the published scripts print six decimals.
- **Rounding limit:** the largest error is 0.999998 of the bound. That is what pure output rounding looks like, and it doesn't exceed it.
- **Equilibrium solve:** it matches the closed form to a relative difference of 9e-16.
- **Antisymmetric angles:** the axial mismatch is exactly 0, and the shear mismatch equals (εL − εT) sin 2φ to within rounding.
- **Fault injection:** I injected nine faults one at a time. Examples are `sin(2φ)` becoming `sin(φ)`, the factor 6 becoming 3, `m*n` becoming `m/n`, and radians dropped from one angle. Each was caught in at least 99.8% of draws, so a transcription error on either side would have shown up.
- **Reruns:** the script is deterministic, and a second run gave byte-identical output.

**Caveats**
- **Weak evidence:** this shows the formalization matches the authors' code. It doesn't show either matches pine cones, and the data is purely computational.
- **Angle conversion:** the degrees-to-radians conversion is done by my harness, because the code takes degrees and Lean takes radians. A wrong conversion there would make every draw fail, so it is visible.
- **Duplicated mismatch:** `S_elem.py` and `S_print.py` recompute both mismatches themselves. The final curvature therefore doesn't depend on the bend or twist reducer's output. I flagged this in the caveats, because it matters if we state a composition theorem.
- **Unphysical ranges:** I sampled thermal strains far beyond physical ones, because the identities are algebraic. The paper's measured-vs-predicted results are not reproduced, since the repo has no measurement tables.

**Repo state:** partway through, `main` was reset to `1605b923`, which undoes the `engine/` restructure. My untracked files survived and the script works under both layouts. If the reset wasn't you, check before the next commit. Nothing is committed, and the pre-registration should be committed first as the rules require. These runs sit in subfolders, so the `claims:exec` manifest won't pick them up, and `hygromorph-antisymmetric-twist` now has this run as its only test.

The code is in `test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-antisymmetric-twist/marom-crosscheck-01/`, and the second claim has a thin wrapper next to its own `result.json`. Do you want me to move on to the bend/twist decoupling theorem next?

The max ratios of 0.999998 confirm errors are saturating the rounding bound, as expected. I shouldn't commit anything—I'll wrap up with a concise summary, flagging the odd repo reset where HEAD was changed by something else, and noting the headline twist value rounds to 1.0 from 0.999998.

_Tools used: Shell ×24, StrReplace ×2, Write ×2_

### 2026-11-01 09:06 — Turn 3 (User)

> please go through teh whole paper first and anythign else you missed in the ifrst pass

**Assistant:**

I'll find the full paper text first, then go back to the repo for what I skipped (`viz.py`, `comp.py`, `spec.py`, the machine profile, the setup guide, CITATION.cff, G-code).

I should try to fetch the actual Marom et al. 2026 JMPS paper by its DOI, checking for an open-access version or arXiv preprint, and also double-check the repo state on the merge-origin branch before diving in.

The journal version is closed, but there's an arXiv preprint (2604.26367v2). I'll pull it and read it in full.

The LaTeX source is better than PDF text anyway. Reading it in full.

Important: the paper does have the measurement table (Table 4), which I said last time it didn't. Continuing with the appendix.

I still need to look at the files I skipped over: viz.py, comp.py, spec.py in full, the machine profile, CITATION.cff, g-code headers, the complete setup guide with material panels, the rest of the gh_scripts README, and figures like cases.png. I also want to compare the arXiv v1 vs v2 differences and check the 00README and export.bib references for citations like Timoshenko1925 and Armon2011.

I should cross-check the repo's git log, then verify the claim's reference to "Marom et al. 2026, eq. 28" against the actual equation numbering in the paper, and confirm the Appendix A.2 category-theoretic framing matches the Dyn subsection structure.


I've finished reading the paper in full. Next I'll go through the remaining repo items I skipped: spec.py, comp.py, viz.py, the machine profile, full setup guide, CITATION.cff, G-code headers, git history, and the cited bib entries.

I notice the G-code header lists kappa=0.0763 1/cm for hygro_bend but swaps the material order compared to the paper's table — mat1 PA6-GF at theta=90 instead of 0°. I want to cross-check all four G-code headers' kappa values against the paper's predicted angle, starting with the baseline case where 36.4° over L=100mm implies kappa ≈ 0.0636/cm.

That doesn't match the 0.0763/cm in the header, which works out closer to 43.7° — so I'll need to dig into the geometry fields in each G-code file, try to reconstruct the "Predicted" column using the material panel parameters in the guide, and flag that PA612-CF15 and PLA panels seem to be missing from that guide. I should also check viz.py, the bibliography entries for Timoshenko1925, Armon2011, and Reyssat2009, the 00README, and compare the two arXiv versions to see what changed between revisions, keeping in mind the 2604 submission date points to April 2026.

The paper and repo disagree in a few places. Before writing up, I'll check our own Lean category definition and `CLAIMS.md` against the paper's Appendix, since that's what our claim rests on.

I'm checking the panel data against the paper's predicted curvature values—comparing the baseline PA6-GF and PA612-CF parameters against the hygro_bend header's kappa of 0.0763 1/cm versus the paper's predicted 0.0635 1/cm at a 100mm length, trying to see where the discrepancy comes from.

Then I notice a potential conflict: the g-code header assigns PA6-GF a 90° raster angle while the paper's table lists 0°, and since strip strain depends heavily on whether the longitudinal or transverse swelling coefficient dominates at that angle, this swap could explain part of the mismatch—though I can't fully resolve it without the PA612-CF15 material data. I also notice the thermal g-code header reports a kappa of zero, which seems worth investigating further.

Looking into the zero-kappa thermal case, it seems likely this g-code was generated from a configuration lacking proper thermal expansion coefficients at the time, meaning both predicted and specified curvature would trivially match at zero—verification passing for the wrong reason. I also want to check the twist case: with raster angles at 45° and -45°, the shear strain mismatch combines the longitudinal-minus-transverse strain differences from both layers.

I'm checking whether the magnitudes for bend versus twist could match by coincidence—working through whether material 2 would need an effective isotropic strain equal to the average of material 1's longitudinal and transverse strains, which seems like a stretch unless the composite happens to land near that value. It's probably not worth pursuing further analytically, but I'll flag it as a loose end worth noting rather than resolving.

The paper's predicted twist angle (41.3° at L=10cm, giving kappa≈0.0721) versus bend angle (36.4°, kappa≈0.0635) gives a ratio of about 1.135, not 1—yet the G-code shows equal magnitudes for bend and twist curvature. That mismatch suggests the G-code was generated using different parameters than the paper's final reported predictions, which I should flag as a discrepancy.

Checking the material orientations: the paper's Case I describes CF-PLA as passive (0°) and PLA as active (90°), which matches the G-code's raster angle assignments. But for the baseline case, the paper specifies PA6-GF at 0° and PA612-CF at 90°, while the G-code has these swapped—PA6-GF at 90° and PA612-CF15 at 0°. That's an inconsistency worth noting.

I also want to verify the citation "Marom et al. 2026, eq. 28" referenced for the twist equation against Appendix A.2, but without an easy way to count equation numbers in the paper, I'll set that aside for now and just note the appendix subsection numbering as something to double-check.

Confirming the appendix A.2 ordering follows A.1 as expected, and that our claim about stimulus-response dynamical systems forming a category matches the paper's framing. I'm also cross-referencing the v1/v2 revision history—adding the natural transformation section, presheaf remark, and Table 4—to make sure our claim file's October date aligns, and now I want to check whether our Lean formalization of StimulusResponseSystem uses finite-dimensional manifolds consistent with the paper's definition.

I should look at lines 260-351 of Hygromorphs.lean, and also verify that CLAIMS.md's statements about Marom (like the eq. 28 reference) are still accurate given the final paper.

I wanted to check if the paper's 36.4° baseline angle could be reproduced from the setup guide's panel data, but only two of the four materials are listed, so it's not verifiable. I did notice a discrepancy though: the G-code header's kappa value (0.0763) doesn't match the paper's implied value of 0.0635 1/cm from 36.4°/10cm, worth flagging.

I also need to verify the "eq. 28" reference in CLAIMS.md against the arXiv v2 numbering — I'll count the numbered equation environments in the main text leading up to Case II to see which one corresponds to Δε12.


I'll verify the equation 28 citation in CLAIMS.md against the preprint, then try reproducing the predicted angles using the repo's material panels.

Equation 28 checks out, so I'm moving to the write-up. I want to double-check my caveat about the repository lacking measurement tables — it's accurate that the repo itself ships only videos and figures, no tables, even though the paper's Table 4 contains the measured values being referenced.

I should correct my earlier claim that there's no measured data at all, since Table 4 does exist in the paper. I'll edit the caveat string in analysis.py to mention Table 4 for clarity, keeping the real blocker (missing PA612-CF and PLA panel data) intact, then re-run so result.json regenerates with the updated caveat.


The "eq. 28" citation checks out, but I noticed the paper's Table 4 actually has measured data, contradicting a caveat I wrote yesterday saying none existed—I'll fix that and regenerate the analysis.

I read the full paper (arXiv 2604.26367v2, LaTeX source, 1,395 lines, including the appendix; the JMPS version is paywalled) and the parts of the repo I skipped: `spec.py`, `comp.py`, `viz.py`, the Bambu machine profile, the full setup guide, `CITATION.cff`, and all four G-code files. The repo has a single commit (2026-08-02). The preprint v1 is from April 2026, v2 from August; the highlighted v2 additions are the natural-transformation section, the presheaf remark, the "verification is about composition, not models" caveat, and the measurement table.

**Correction to what I told you yesterday.** I said the paper's measured-vs-predicted results couldn't be reproduced because there's no measured data. Wrong: the paper's Table 4 has them.

| Case | n | Predicted | Measured | 
|---|---|---|---|
| hygro / bend | 3 | 36.4° | 35.3 ± 3.1° |
| thermal / bend | 3 | 52.0° | 55.7 ± 4.2° |
| hygro / twist | 4 | 41.3° | 41.3 ± 2.2° |
| thermal / twist | 3 | 23.0° | 23.3 ± 2.5° |

All at L = 100 mm, h₁ = h₂ = 0.6 mm. The repo still doesn't let us recompute the predictions, though: only two of four material panels are shipped (PA6-GF and PLA-CF; PA612-CF15 and PLA are missing). I've updated the caveat in the result files and regenerated them; verdicts unchanged.

**Discrepancies between paper and repo** (found by reading the G-code headers):
- Baseline raster angles are swapped: paper Table 2 has PA6-GF at 0°, PA612-CF at 90°; the shipped `hygro_bend.gcode` header has PA6-GF at 90°, PA612-CF15 at 0°.
- The G-code header records κ = 0.0763 1/cm for the baseline; the paper's predicted 36.4° over 10 cm is 0.0635 1/cm. The twist header has −0.0763, equal magnitude to the bend, where the paper's two predictions differ (36.4° vs 41.3°). So the shipped G-code was generated with different inputs than the paper's final predictions.
- Both thermal G-code headers record κ = 0.0000. `spec.py` compares κ_spec against κ_art with a relative tolerance, so when both are zero the check passes trivially and `verified=True`. The thermal files were compiled from a specification whose predicted curvature was zero, most likely because the thermal coefficients weren't in the panels at generation time.

None of this affects our cross-check, which tests the functions, not the paper's numbers. It does mean the repo isn't a route to independently reproducing Table 4.

**The theory, as the appendix actually states it** (relevant to what we can formalize):
- `Dyn`: objects (X, E, f) with X, E smooth finite-dimensional manifolds and f : X × E → TX; morphisms are pairs of smooth maps with the simulation condition; the proof is the chain rule. Our Lean version uses normed spaces and `fderiv`, which is a faithful special case. The claim and `CLAIMS.md` describe it correctly, and "eq. 28" for the twist mismatch is the right equation number in v2.
- Reductions β are only morphisms when "compatible with the dynamics" (closed observables); strain components, curvature and the mean angle are explicitly called terminal observables, not morphisms. Our claim text doesn't say otherwise, but it's worth knowing: the repo's `beta_bend`/`beta_twist` are terminal readouts, not scale transitions.
- α_geom and α₃ become morphisms only after adjoining the fixed geometry (h₁, h₂, E₁, E₂, L, w) to the *state* with zero dynamics. That's a neat trick and short to formalize.
- F : Nat → Art is defined as conjugation by diffeomorphisms ι, ȷ; the paper admits these are identities in every case here, so F is parameter substitution. The functor proof is three lines of chain rule.
- The implementation natural transformation η (v2 addition) is the thing that justifies "implement then assemble = assemble then implement". Its proof is deferred to the F proof.
- π : Spec → Art sends every morphism to an identity (Spec morphisms are defined as behavior-preserving, so this is circular by construction); E : Spec → Comp is asserted a functor without a real definition of Comp morphisms. Neither has mathematical content worth formalizing.
- The per-scale ODEs (first-order relaxation with τ_m, τ_L, τ_T, τ_Δ) are in the paper but not in the code; the code evaluates equilibrium only (`F_fib` multiplies coefficient by Δu). The dynamics are never run anywhere.

**What's genuinely formalizable beyond what we have:**
- The F-functor proof (conjugation preserves the simulation condition) and the η naturality squares. Both are chain-rule lemmas on top of our `StimulusResponseHom`.
- The augmented-state construction: adjoining constants with zero dynamics makes α_geom a morphism. Short.
- The reductions proposition: a compatible observable induces unique dynamics. Needs quotient reasoning; medium.
- The bend/twist decoupling corollary at (0°, 90°) and (±φ) I proposed before, now with the paper's own statement of Case III (eq. 29) as the target.

**One fact from the paper worth recording against our claim `stimulus-response-systems-category`**: the paper itself says (v2) that composition is "verified by construction" while "the fidelity of the models themselves … remains empirical". Our claim context already says this. Also, the sources the paper leans on for the mechanics are exactly ours: Timoshenko 1925, Reyssat & Mahadevan 2009, Armon et al. 2011, Quan et al. 2021.

Files touched this turn: only the caveat string in `marom-crosscheck-01/analysis.py` and the two regenerated `result.json`. Nothing committed; still on `merge-origin`.

_Tools used: Read ×4, Shell ×14, StrReplace_

### 2026-11-01 09:49 — Turn 4 (User)

> so is there something we cna print with bambu as well that would relate to our biomaterials claims?

**Assistant:**

I'm trying to figure out if something tied to our biomaterials claims could actually be printed on a Bambu printer — checking the fabrication folder, the printed-bilayer-01 hydrogel strip test, and the hygromorph-bilayer-scaling problem for anything concrete to suggest.

Let me check the problem statements quickly since the fields differ, then put together an answer as an assessment with options.

Yes. The best fit is the hygromorph bilayer itself, because the Marom repo gives us a Bambu-specific recipe that our Formlabs plan lacks, and three other claims have printable tests too.

**1. FFF hygromorph bilayer (strongest fit).** Our `printed-bilayer-01` plan is pre-registered for a Formlabs resin printer, and its README says the risk is fabrication: one resin at a time, laminate or tank-swap. A Bambu X1C with AMS sidesteps that: two filaments, one print, the layer interface is a normal tool change. The Marom repo hands us the machine profile (`machine_bambu_x1c.py`), the toolpath generator (`comp.py`, which needs Rhino, but its G-code is plain enough to reimplement without it), a conditioning protocol (dry at 60 °C for 4 h, then room-temperature water), and the material pair PA6-GF / PA612-CF with their process windows (Table 1 of the paper: 275/290 °C nozzle, 90 °C bed). The claims it tests are `hygromorph-bilayer-curvature`, `hygromorph-response-time` (three thicknesses give the \(h^2\) scaling), and `hygromorph-antisymmetric-twist` (±45° rasters, which is exactly the paper's Case II and the thing Formlabs can't do at all, since raster angle is an FFF concept). Also the thermal variants, with PLA / PLA-CF, in near-boiling water: same law, a stimulus we control far more precisely than humidity.

Caveats: it's `data_kind: physical`, so it shows the law predicts a thing we made, not that pine cones obey it. The paper's own predictions can't be reproduced from the repo (two material panels missing), so we'd measure our own inputs: single-layer strips for modulus and free swelling strain, as our README already requires. Hygroscopic swelling of PA6-GF is slow (hours to days to equilibrate) and small (~0.5 % strain over RH 30→80 by their panel); the thermal pair is faster and larger. The Bambu's 0.4 mm nozzle sets a 0.2–0.3 mm layer floor, so the thinnest total thickness is ~0.6 mm, which matches the paper and our sweep's lower bound. And the pre-registration would need a new run directory (`printed-bilayer-02-fff` or similar), not an edit of the Formlabs one, since the materials, process and stimulus differ.

**2. Hollow-tube stiffness per mass** (`thompson1917-ch16-03`, problem `hollow-tube-mass-optimality`). Print tubes at fixed mass with varying radius-to-wall ratio, three-point bend them, find the stiffness peak and the local-buckling cliff. Cheap, single material, needs a bending fixture and a load measurement (a kitchen scale and dial gauge are enough for a first pass). Tests the engineering half of the claim, not the biological one.

**3. Stress-aligned vs uniform lattice** (`thompson1917-ch16-05`, problem `printed-stress-aligned-lattice-beats-uniform`). The problem is written for SLA, but FFF works for a compression block. Harder: it needs lattice generation, FEA for the trajectories, and a real testing machine for ten replicates per arm.

**4. Phyllotaxis / log-spiral geometry** (`thompson1917-ch13-01`, ch. 14 claims). Printable, but a print of a spiral only illustrates the math; it doesn't test anything.

Whichever you pick, the repo rules apply as they do for data tests: the prediction from independently measured inputs is committed before anything is measured, and the swarm designs while an operator prints.

Do you want me to draft the FFF bilayer pre-registration (a `result.json` plus a specimen table and a Rhino-free toolpath script, modelled on the Marom G-code), and if so, do you have PA6-GF/PA612-CF on hand or should I plan around PLA / PLA-CF with the thermal stimulus?

_Tools used: Shell ×4_
