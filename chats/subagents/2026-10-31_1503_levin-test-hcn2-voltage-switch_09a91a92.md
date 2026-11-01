# Subagent: Levin test: HCN2 voltage switch

- **Parent chat:** [let's do the same thing for mike levin's works that we did for darwin and thomps](../2026-10-31_1314_let-s-do-the-same-thing-for-mike-levin-s-works-that-we-did-f.md)
- **Started:** 2026-10-31 15:03 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 17:11 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `09a91a92-013c-48b9-8598-59dfa69f5477`

---

### 2026-10-31 15:03 — Turn 1 (User)

> You are running a pre-registered claim test in the repo /Users/jdietz/Documents/GitHub/dev/delphisci. Read claim-tests/README.md first and follow it exactly.
> 
> Claim (directory claim-tests/levin-papers/levin-2018-hcn2-06/): levin-2018-hcn2-06, "HCN2 modelled as a voltage-controlled switch that amplifies small Vmem gradients", from Pai, Pietak, Willocq, Ye, Shi & Levin 2018 (HCN2 rescues brain defects by enforcing endogenous voltage pre-patterns, Nature Communications). Get the claim text, quote and line from books/levin-papers/claims.json; the source text is books/levin-papers/inputs/2018-hcn2.txt. Read the operationalizations in books/levin-papers/assessment/raw/gpt/*.json and raw/grok/*.json for this claim id. The paper's modelling used BETSE (public, verify the actual repository URL and any published config files; do not guess URLs).
> 
> Procedure:
> 1. Before running any analysis or looking at results, write result.json with status "preregistered", hypothesis, pass_criterion, fail_criterion, planned_datasets and test_contract. Do NOT git commit (shared working tree); writing the file first is the pre-registration.
> 2. Then write analysis.py, run it, and fill in the rest of result.json (status complete, method, measured, verdict, confidence, caveats, agent {kind: local-agent, model, run: "cursor local session", date: 2026-10-31}). Record URL, retrieval time, byte size and SHA-256 for everything downloaded. Never invent data, URLs or numbers. Do not commit downloaded code/data over 1 MB (fetch in a script). If running full BETSE is impractical, a pre-registered minimal re-implementation of the paper's stated HCN2 channel model in a coupled-cell bioelectric circuit is acceptable; say so in interpretation. Keep run time to tens of minutes.
> 3. Test the claim as stated, in its stated scope.
> 
> If the directory already exists when you start, stop (another session owns it). Do not touch claim files, assessments, nanopubs or any other directory; never sign or publish anything.
> 
> Reply with: claim id, verdict, confidence, and the key measured number.

**Assistant:**

I'll check if the directory exists and look at the README first.

I should probably establish my working directory before diving in, maybe pre-registering my result file. But first I want to read the source claim and operationalizations — the paper's text itself is fair game since it's just the claim, even though the actual data will come from simulation.

Directory claimed. Now reading the source paper's model section to get the stated HCN2 model and parameters.

Table 1 with the initial concentrations seems to be missing from the text I have, so I should try pulling it from the paper's Europe PMC entry. I also want to double check the BETSE repo URL, since its channel library includes an HCN2 funny-current model that likely draws from ModelDB's kinetic models of HCN2 voltage sensitivity.

Fully reimplementing BETSE would need a config YAML the paper may not have published, so my plan is a minimal reimplementation using BETSE's HCN2 gating equations (fetched and hashed from source) combined with GHK flux in a coupled-cell circuit. Since pre-registration must happen before I look at any results, checking BETSE's source for model equations and verifying URLs counts as method-definition, not results-peeking, so I can proceed with that before locking in my pre-registration criteria.

I should check the BETSE repo for the HCN2 file path and any published config by searching for terms like "hcn2" or "neurula," and also look into Europe PMC's full text XML for Table 1 since those are input parameters rather than results. The Fig 3 results already appear in the text as −80/−5 mV, so that's settled.

I don't see a Nature Comms 2018 HCN2 config in the BETSE repo, just the 2016 Frontiers and 2018 PBMB versions, though those neurula embryo images might be relevant. I'll wait for the supplementary files check to confirm.

Supplementary files could be slow to fetch, so I'll skip them for now and rely on the full-text XML which already has Table 1. The Supplementary Note likely has detailed leak permeabilities per region, but I can try fetching that separately with a timeout later. Before pre-registering, I need to settle on the model structure even though parameters still depend on inputs I haven't pinned down.

I'll define my pre-registration criteria around a coupled cell-sheet model with ectoderm, neural fold, and neural tube regions, including Kir, leak conductances, gap junction coupling, and homogeneous HCN2 expression. The key measured quantities are the hyperpolarization shift in the tube versus lateral regions, channel open probability differences, and a switch-like amplification curve where HCN2 produces large shifts at hyperpolarized baselines but minimal shifts at depolarized ones. My pass criteria require the tube to hyperpolarize by at least 15 mV while lateral regions stay within 5 mV, with the voltage gradient between them widening by at least 15 mV under paper-realistic parameters.

Now I'm working through the reversal potential math for HCN2 using the GHK equation, checking whether the channel's ion selectivity (PNa:PK = 0.2) combined with the ionic concentrations in 0.1×MMR would actually produce a reversal potential below the tube's control membrane voltage—since this determines whether channel opening would hyperpolarize or depolarize the tissue. I need this reversal potential to sit below the tube's resting voltage for the hyperpolarizing mechanism to make physical sense, otherwise the fail condition triggers where HCN2 opening would depolarize rather than hyperpolarize the tube.

I'm also noting that the channel's voltage-dependence (V1/2 around -99 mV, shifting to -79 with cAMP) means open probability at -50 mV is already quite low, and essentially zero at -5 mV—so the steepness of this activation curve matters for whether the channel actually switches states as voltage changes. I should also build in a robustness check by sweeping HCN2 expression levels across a pre-registered range to test how sensitive the outcome is to permeability assumptions.

Since the exact paper value may not be fully recoverable from the tables, I'm pre-registering a fallback: if the primary parameter isn't available, I'll treat the claim as supported if there's a contiguous decade-wide range of expression levels where the pass condition holds, since the claim is about the model's capacity to produce this behavior rather than a single fixed parameter value.

Now I'm thinking through gap junction coupling between regions, since strong coupling could spread signals and undermine localized switching. I need to model voltage-sensitive gap junctions using BETSE's conductance formula (a sigmoidal function of junction voltage with threshold and gradient parameters), and I should pull BETSE's actual default values for these parameters from its source or config files to keep the reimplementation faithful.

I'm also deciding how to handle Vmem dynamics: rather than fully simulating ion concentration changes, I'll keep concentrations fixed at steady-state values and solve for Vmem via GHK current balance including gap junction currents, integrating until the net current is zero. I still need to check BETSE's Kir channel model and gap junction files to make sure my simplified specification matches their actual implementation before finalizing this as a pre-registered model.

Pre-registration written. Now fetching the model ingredients (BETSE source, paper XML, supplementary files) via a fetch script.

I should check vg_k.py for Kir channel logic, along with gap_junction.py and channelsabc.py to understand how channel currents are computed.

I'm checking whether numpy is available and considering urllib for fetching data, then verifying if the data/ directory is gitignored elsewhere.

My directory's data isn't being ignored. I wonder how tame-19 handled this—maybe there's a data/.gitignore file I should check for.

My files are small enough anyway, so I'll just set up a data/.gitignore that excludes everything except manifest.json, and switch over to urllib.

I'm noting that Table 1's extracellular sodium and potassium values reflect the intercellular space concentrations, which makes sense since BETSE models cell membranes facing both intercellular spaces and the outer environment, with the 10-µm layer representing the boundary facing the 0.1×MMR bath.

Let me try pulling the text from the Supplementary Note PDF directly to check if pdftotext works here.

I'm finding the full HCN2 model parameters in the supplementary note—the activation curve equation, permeability values for wild-type versus overexpression conditions, relative ion selectivity ratios, and the Kir channel's magnesium block parameters alongside baseline Na and K permeabilities.

Chloride and calcium permeabilities are also specified for the test simulations, though region-specific leak variations aren't numerically listed and may only appear in the figure itself—I should check Fig. 2 for those values. I also want to verify whether the supplementary note's GitLab repository link for BETSE is still valid, since the project appears to have migrated to GitHub.

Working through the Kir magnesium block formula, I'm calculating how the open probability changes with membrane voltage—at more hyperpolarized potentials the block decreases and the channel opens more, which matches expected Kir behavior. For the HCN2 overexpression scenario specifically, the relevant permeability is the elevated value representing roughly a hundredfold increase over wild-type.

I'm now reconciling a conflict between my pre-registration, which specified an "HCN2-free" control, and the paper's actual setup, which uses wild-type endogenous HCN2 as the baseline rather than zero expression. I'll treat the paper-faithful comparison (wild-type vs. overexpressed) as primary while also reporting the HCN2-free version as a disclosed deviation, checking that the verdict is consistent either way, and I'll run the sweep from 0.01x to 100x of the overexpressed permeability. Next I need to think through how the GHK flux calculation for HCN2 handles the environmental concentration term.

As a sensitivity check, I'm testing membranes facing intercellular ECM concentrations instead (Na 101.8, K 3.7). Recomputing the HCN2 reversal potential under this scenario gives roughly -36.7 mV, meaning at a tube potential of -50 mV, HCN2 opening would actually be depolarizing rather than hyperpolarizing.

But the paper specifically describes hyperpolarization under Xenopus ionic parameters with 0.1×MMR external media, and plugging those numbers gives about -97 mV for the reversal potential, matching that claim. This raises the question of whether BETSE uses fixed or dynamic concentrations, since the HCN permeability is so much larger than leak that significant potassium efflux could deplete cell potassium over time, which I want to check by accounting for cell volume and dynamic concentration changes.

Given the pump and dynamic concentration complexity, I'll go with the pre-registered fixed-concentration quasi-steady-state method as the main approach and just flag dynamics as a caveat rather than fully simulating it. Now I need the region leak values from Figure 2a, so I should look at that image directly.

I'm trying to pin down the absolute permeability scale, since the leak ratios (Na:K:Cl roughly 1:1:2 in tubes, 1:1:15 in folds/ectoderm) don't fix actual values — my test simulation gave inconsistent Na and K numbers, so I need to establish a calibration step before trusting these ratios.

Checking the chloride GHK equation with the given medium concentrations gives E_Cl around +40 mV, meaning chloride efflux depolarizes — which fits nicely with the elevated permeability ratio in folds driving the lateral region toward its more depolarized target. I'm deciding to omit the Na/K-ATPase pump term for now and disclose that simplification, and I still need to work out the gap-junction coupling conductance from the simulation config parameters.

The HCN2 shift looks consistent with the supplement. I'm now working through the gap junction permeability conversion, relating Dm and membrane thickness to permeability and then computing an effective conductance from the gap junction diffusion coefficient.

Using the electrodiffusion formula across the intercellular gap, I compute a gap junction conductance around 5.5e-3 S/m², compared to roughly 3.3e-4 S/m² for the membrane GHK conductance—so the gap junction path appears considerably more conductive per unit area.

The real uncertainty here is how strong gap junction coupling actually is between the tube and lateral regions, since the tube is only a few cells wide. If coupling is strong, the lateral folds could effectively clamp the tube's voltage, which matters a lot for interpreting the hyperpolarization result. I think I need to treat the coupling strength as a parameter to sweep rather than assume a fixed value.

Since the pre-registration never specified gap junction strength, I'll use my best derived default and sweep across a wide range to check sensitivity. For the spatial model, a simple 1D line of cells underestimates coupling compared to a 2D arrangement, so I should build something closer to a 2D grid approximating the actual tissue geometry from the figure — a circular region with an elliptical folds zone and a narrow central tube strip.

I could try segmenting the actual figure's colors to define tube, folds, and ectoderm regions faithfully, but relying on image libraries like Pillow adds a dependency I'd rather avoid, so I'll approximate with simple geometric shapes instead — a circle, teardrop-shaped folds, and a strip for the tube. For the voltage-sensitive gap junction conductance, I'm implementing a sigmoid function based on BETSE's parameters, using a half-closed threshold around 15 mV and a minimum conductance floor.

I'm working out the gap junction steady-state formula using the alpha/beta ratio plus a minimum conductance, then trying to figure out how BETSE translates open probability into an actual conductance magnitude via diffusion coefficient and junction surface area.

I'm working out the gap junction flux per membrane area, treating it like the transmembrane flux using the ion's diffusion coefficient, gap junction surface area, and open state, scaled by the cell spacing distance to get an effective per-area conductance.

I'm assuming the junction diffusion coefficients equal the free diffusion values, giving an effective diffusivity over the membrane length, then computing each ion's per-channel conductance using the standard z²F²Dc/(RTL) formula with concentration as a geometric average, starting with potassium's numeric calculation.

Summing K, Na, and Cl contributions gives a total gap junction conductance around 2 S/m² when fully open — roughly 100x stronger than overexpressed HCN2 and thousands of times stronger than membrane leak. This makes me realize that with default BETSE parameters, even with voltage-gating reducing conductance toward its minimum, the gap junctions would still dominate and effectively clamp a multi-cell-wide tube to the lateral potential, which contradicts the voltage gradient shown in the paper's control simulation — meaning the authors likely used different parameters than the defaults.

I'll treat gap junction surface area/strength as something to calibrate rather than fix at the default: the primary approach should use the BETSE default conductance if the control condition can be calibrated to match the paper's reported voltages (tube ≈ -50±10 mV, lateral ≈ -5±5 mV), and if not, fall back to the largest coupling strength on a log-spaced sweep for which that calibration target is still achievable.

For the leak permeability scale, I'll grid-search a baseline P0 against the fixed Kir and HCN2 permeabilities to minimize the combined error against the target tube and lateral voltages, using the reported Na:K:Cl permeability ratios (1:1:2 tube, 1:1:15 lateral) from the figure. I also need to settle on membrane facing conventions, like scaling apical permeability by a factor relative to the bath medium for all transmembrane fluxes.

It's ambiguous whether the simulation treats cell membranes as facing an evolving extracellular ECM grid or a fixed bath concentration directly, since the paper doesn't clarify whether extracellular space simulation was enabled — I'll have to infer from the supplementary figures that channel I-V curves were computed against the diluted bath medium directly.

I'll settle on 0.1×MMR as the primary condition and treat ECM-based concentrations as a sensitivity check that won't change the final verdict, recording this decision as a timestamped preregistration amendment before running any analysis. For ion permeabilities, I'll skip the pump, include HCN's calcium component but exclude the separate calcium leak since it's absent from Fig 2a, then move to figuring out Kir's potassium permeability.

For Kir I'm using a Mg-block formula where block strength depends on voltage through an exponential term, and I confirm the sign matches the text so that hyperpolarized voltages reduce block as expected. For HCN2 I only need the steady-state activation curve since the time constant doesn't matter at steady state, and now I'm working out how to numerically integrate the membrane voltage equation using simple explicit Euler steps, watching out for stiffness since the gap-junction conductance and capacitance give a fast ~25 ms time constant.

Given the stiffness ratio is huge, I'll instead use a damped Newton solver on the nonlinear steady-state equations across all cells, which is tractable since a dense Jacobian for ~1000 cells is fine with numpy. Since multiple steady states (bistability) are possible, I'll use pseudo-transient continuation starting from V=0 and take large implicit Euler steps solved via Newton each step, following the same trajectory approach as BETSE, with gap-junction gating treated as instantaneous steady-state.

For the membrane current I'm using the GHK flux equation for each ion, computing the Jacobian numerically via finite differences for the local membrane terms and analytically for the gap-junction (ohmic electrodiffusion) terms, while treating the gating variable as lagged and updated once per Newton step rather than fully differentiated.

Now I'm laying out the geometry as a hex lattice of radius ~18 cells, approximating the tube as a narrow vertical strip and the folds as an elliptical region around it based on the figure, with zero coupling at the outer boundary. I'm also setting up the metrics to track as mean Vmem by region (tube, folds, ectoderm) along with HCN channel gating state.

For scenarios I'm defining control (wild-type HCN2 conductance), a no-HCN control, and an overexpression case at 100x, plus a log-spaced sweep of expression levels spanning four orders of magnitude. I'm also planning single-cell sweeps varying the potassium leak multiplier alongside sodium/chloride leak ratios to establish an achievable resting potential range, and setting up a gap-junction conductance sweep across several orders of magnitude.

For each gap-junction condition, I'll calibrate the baseline leak permeability using a 40-point log grid, targeting a tube voltage near -50mV and lateral tissue voltage near -5mV by minimizing squared error against those targets, calibrating against the wild-type HCN2 control case. Then I'll write these amendments into the results file.


I've extracted the HCN2 and Kir channel specs along with regional leak ratios from Supplementary Note 1 and Fig. 2a, but absolute leak scale and gap-junction strength aren't specified—and BETSE's default gap-junction strength would be ~100× too strong relative to overexpressed HCN2. I'll document these modeling choices as an amendment to the pre-registration before running anything.

Odd, the file isn't where I expect it — maybe it got deleted. I should check the directory to confirm.

It looks like something else operating in this shared working tree staged deletions, wiping out claim-tests including my result.json, leaving only data and fetch.py behind. I should check the git branch and log to figure out whether someone ran a git rm or switched branches.

It looks like another session is mid-restructure, moving files into claim-sources via git mv. My claim-tests directory may have been relocated too, so I should check if claim-sources/claim-tests or similar now holds my result.json.

I'm noticing another session restructured the repo, moving claim-tests and books into new locations, and my earlier result.json and fetch.py ended up relocated too. There's also a stray __pycache__ directory from around 15:27, which makes me wonder if someone else actually ran fetch.py in my directory.

I need to check if my result.json is still intact, then figure out whether my later 15:52 fetch run recreated the old claim-tests path with fresh data. I should copy that newer work into the correct test-data location, delete the stray old-path directory, confirm claim-tests only contains my own files, and check the README at the new location for any updated rules.

The old-path claim-tests directory only has my files, so I'll move my fetch.py and data to the new location and clean up the stray old directory. There's a leftover __pycache__ generated from my fetch.py, but since I can't be fully certain it's mine, I'll leave it alone.


The repo got restructured mid-session (claim-tests/ → test-data/claim-tests/, books/ → claim-sources/). I'm moving my later files to the new paths and cleaning up the now-empty old directory.

Since data/ is gitignored by the parent, I'll just copy the provenance info directly into result.json rather than relying on manifest.json. I'll leave the data/.gitignore as is for simplicity, and I should also note the files I fetched to /tmp for inspecting the GJ formula as consulted sources in the provenance record.

I should check how BETSE defines its gap junction diffusion constant, particularly whether Dgj_Na is just set equal to Do_Na, around line 640 in sim.py.

Model sources are pinned. Now writing `analysis.py`, a minimal coupled-cell re-implementation of the paper's stated model.

I'm settling on free diffusion for the other ions, treating Ca as negligible, and now starting the analysis script using mM units and outward-positive current density, applying the GHK flux equation for each ion.

Current I derives as zF times flux, with Vmem defined inside-minus-outside so that dV/dt = -I_total/Cm correctly hyperpolarizes on outward K current. For gap junction coupling between hex-packed cells, I'm working out how each membrane segment contributes both a transmembrane flux and a neighbor-coupling flux, leading to a per-cell voltage equation combining the uniform membrane current with a sum of gap-junction conductance terms weighted by voltage differences to each neighbor, with boundary cells needing adjusted factors for fewer neighbors.

Now I'm estimating computational cost: a hex lattice with radius 20 gives ~1450 cells, making a dense Jacobian too expensive for many calibration runs, so I'm scaling down to radius 14 (~700 cells) to keep each Newton solve around 20ms, making a calibration sweep of roughly 200 parameter combinations feasible in about two minutes using just numpy.

I'm defining the tissue regions geometrically in cell-spacing units—ectoderm as the full circle, the fold region as a teardrop-shaped ellipse matching the figure's pink area, and the neural tube as a narrow vertical strip—then setting up the pseudo-transient update equation that advances voltage toward steady state each timestep.

The solver uses Newton's method with an analytic diagonal Jacobian plus a lagged gap-junction coupling term, ramping dt geometrically from 1ms to 1e4s and checking convergence against the rate of voltage change. I'm also noting that HCN current starts at steady state given voltage, Kir conductance depends on voltage, and starting all cells at V=0 lets the tube settle toward its hyperpolarized state through leak/Kir before HCN activates, after which I plan to test a single uncoupled cell against the mixed leak conductances.

I'm planning a two-dimensional sweep over K+ leak multiplier (log-spaced roughly 0.01 to 100) combined with two Cl leak ratios (2 and 15) to see what baseline voltage range this produces, aiming to match the preregistered -70 to 0 mV span, then I'll move to analyzing the single-cell baseline behavior with wild-type HCN conductance.

Now I'm laying out the formal evaluation criteria: the HCN reversal potential (computed via GHK with specified ion permeability ratios) must sit below the control tube voltage; the tube voltage must drop by at least 15 mV with HCN overexpression; fold and ectoderm voltage changes must stay small (within 5 mV); the lateral-minus-tube voltage gradient must increase by at least 15 mV, where lateral cells include both folds and ectoderm; and the ratio of tube to ectoderm conductance must be at least 5-fold.

I'm also defining failure conditions—reversal potential exceeding control, insufficient tube depolarization shift, lateral regions shifting nearly as much as the tube itself, or no expression level in the sweep satisfying criteria (b)-(d)—plus a secondary single-cell criterion requiring the effect to hold across at least a decade of expression levels. For the final verdict, I'm working through the logic of what counts as "supports," "refutes," or "mixed" depending on whether primary and secondary criteria are both satisfied, since the pre-registration language is ambiguous about whether the secondary condition is strictly required for a full pass.

For calibration targets, I'm setting the tube potential to roughly -50±10 mV and both lateral regions to -5±5 mV, using the average of the two lateral region means as my reference metric. For sensitivity testing, I'm planning to rerun the analysis at the primary gap-junction configuration with recalibration applied, using the same procedure and reporting results. Now I'm ready to start writing the actual code.

I should clean up the leftover code in hcn_reversal, and I'm checking that the single-cell steady state case with no adjacency works fine. I'm also worried about speed—running 25 calibration points times 8 gj values times steady-state solves, each with hundreds of Newton iterations on 700x700 matrices, could get expensive given the exponential terms in the open-channel arrays.

That's roughly 13 minutes total, which is acceptable, but I want to speed things up by computing gj only on the edge list rather than the full matrix, and assembling the dense Jacobian using np.add.at instead. Let me rewrite it that way.

Checking the single-cell edge case confirms the zero-adjacency matrix behaves correctly with no edges, and gap junction conductance set to zero still works fine since the diagonal stays nonzero. Before running the full simulation, I want to time a single steady-state computation first.

I'm double-checking the HCN reversal potential by working through the GHK flux equation for calcium permeability, plugging in the concentration gradient and exponential terms to verify the -36 mV figure.

Checking K and Na terms, I notice the computed reversal doesn't match -36 mV unless I find my error — and I spot it: I accidentally swapped the Na and K permeability values in the array, putting Na's permeability where K's should go. That's the bug causing the discrepancy, and I need to fix the ordering.

Good, -97 mV matches my hand calculation. Estimating runtime: 8 gj times 25 calibration steps at roughly 3 seconds each gives about 10 minutes, plus a few more for the rest, so I'll let it run in the background.

The simulation is slow at strong coupling, roughly 5 minutes per gap junction level, so the total runtime could stretch past 25 minutes—acceptable but pushing into tens of minutes. I'm puzzled why HCN2 overexpression would depolarize the tube from -55 to -27.6 at strong coupling given the channel's reversal potential is -97; I'm trying to work out the activation curve to understand this unexpected effect.

I'm wondering if the discrepancy comes from the system landing on a different stable branch rather than violating the single-current logic—since the Kir channel with Mg block creates a negative-slope conductance region, it could produce bistability where adding an outward HCN current shifts which stable state the cell settles into, rather than simply pulling voltage toward -97 from the same starting branch.

Let me isolate this by testing a single cell with P0=4.64e-11 to debug directly.

For cl=2 with HCN_OE, the solver returned +19mV but the residual there isn't actually zero, meaning it didn't converge properly even though the true steady state should be near -98mV. I suspect the bug is in the single-cell Newton iteration branch, possibly related to the step clipping or iteration count not checking convergence correctly.

Actually, I think the real issue is the negative-slope region between -80 and -50mV where Kir/HCN currents create negative conductance, causing the Jacobian to become negative and the Newton step to go uphill instead of downhill. The fix should clip the diagonal Jacobian term at zero (using max of the current derivative and zero, plus the capacitive term) to maintain a descent direction, even though this makes convergence slower; I should also reject steps that don't converge within the iteration budget and shrink the timestep rather than growing it blindly.

This confirms the earlier "strong gap junction" result is invalid and needs to be rerun after this fix, and I should add an explicit convergence flag to the residual tracking. HCN's activation gate indeed has a negative-slope region, which is likely what's driving this instability and the switching behavior I'm seeing.


The solver was returning a false equilibrium because Newton steps diverge where the I–V curve has negative slope (as with Kir and HCN2 activation). I'm stopping this run to make the implicit stepping robust—enforcing a positive-definite Jacobian, rejecting failed Newton steps, and cutting back dt—then rerunning.

I should also cross-check against a brute-force forward Euler implementation on a single cell, then re-run the single-cell test and time a coupled case for comparison.

Running forward Euler with 3e5 steps across 6 runs could take several minutes given numpy call overhead—that's a bad choice. I'll let it keep running and check the output file in the meantime.

The fixed solver matches brute-force forward-Euler integration exactly in single cells. Rerunning the full analysis (about 20 minutes).

Since the solver matches forward Euler, each strong GJ coupling takes about 10 seconds, so calibration across the pre-registered 25-point log grid works out to roughly 250 seconds per level, totaling maybe 15-20 minutes overall—acceptable, so I'll keep the grid at 25 and proceed.

Calibration keeps failing—the lateral cell ends up either too depolarized at +22 mV or hyperpolarized toward -19 mV, since with leaky gap junctions the chloride reversal pulls it positive while small conductance lets Kir dominate and pull it negative. This bistability suggests hitting the target of -5 mV may be essentially unreachable across junction strengths, pointing toward an inconclusive verdict.

Meanwhile the actual effect results show HCN2 strongly hyperpolarizes the tube from -55 to -87 while the lateral and ectodermal cells barely budge, and this pattern holds even at lower gap junction coupling—so the qualitative claim is robust, but since the pre-registration requires reporting "inconclusive" with reason "other" when calibration can't be achieved, I need to honor that while still presenting these results as secondary descriptive findings once the analysis finishes.


The control calibration isn't matching the paper—lateral regions show +22 mV instead of the expected −5 mV with the Fig. 2a leak ratio, though HCN2 overexpression still shifts the tube from about −57 to −95 mV while leaving lateral regions mostly unchanged. I'll wait for the rest of the sweep to finish before digging further.

The primary 0.1×MMR condition fails to calibrate, making the pre-registered verdict inconclusive. The ECM-facing sensitivity run calibrates well, but HCN2's reversal potential of −36.5 mV actually depolarizes the tube, which refutes the hypothesis in that variant — and I notice that run used gj=0 since primary was None.

So neither model variant satisfies both the control pattern and HCN2 behavior simultaneously: the 0.1×MMR model amplifies correctly but gets lateral control wrong, while the intercellular model matches control but gets HCN2 direction wrong. Given the pre-registered verdict is inconclusive, I'll add an exploratory section reporting descriptive numbers from both best-fitting uncalibrated models, clearly labeled as exploratory rather than confirmatory.

I'm planning additional exploratory runs: sweeping gap-junction values for the ECM model, running single-cell sweeps in both media, and an expression sweep at the MMR calibration point, keeping total runtime manageable. A mixed apical/basolateral medium would be more biologically realistic but isn't supported by the 2D geometry and wasn't pre-registered, so I'll just note it as a caveat rather than attempt it. Now I need to restructure the main script to compute this exploratory block with a reusable secondary-analysis function.


The pre-registered verdict comes back inconclusive: the 0.1× MMR condition specified in the paper never reproduces the control pattern, while the intercellular-space sensitivity run matches it exactly but with HCN2 now depolarizing the tube. I'll add clearly labelled exploratory runs—expression sweep, single-cell sweeps in both media, and gap-junction values for the intercellular-space variant—without altering the verdict.

The verdict already defaults to inconclusive when there's no primary result, which matches the pre-registered rule, so I'll proceed with running it again, expecting roughly 8 minutes plus another 10 for the exploratory pass.

I'm noticing that at BETSE-default gap junction settings, the MMR model passes all primary criteria with a healthy tube voltage and good lateral/medial ratio. Looking at single-cell behavior, depolarized cells stay unaffected while hyperpolarized cells shift dramatically, with one case near -29 mV swinging by -64 mV, which looks like a switching event.

Given calibration couldn't be achieved to the control standard, I'm leaning toward an inconclusive verdict with moderate confidence, reporting the tube shift under the uncalibrated best model (around -31.5 mV) as the primary measured value alongside the ECM-related depolarization as supplementary data. Now I need to finalize result.json, check the dataset manifest, and clean up the leftover __pycache__ directory from my imports since it's harmless to remove.

Runs finished. Writing the completed `result.json`.

At high expression the whole sheet flips hyperpolarized through gap junctions, pulling lateral cells down to around -97 mV, so there's no switch-selectivity there — the selective window only exists near 1x expression, spanning less than a decade between 0.32x and 3.16x. I'm also checking that the 0.01x tube conductance case matches wild-type levels as a baseline.

Now I need to fix the timestamps before writing the final result.json: the preregistration time should be corrected to 19:05Z and the amendment time to 19:56Z based on actual local run times, both occurring before the first flawed run at 19:57Z. I also confirmed the Supplementary Note's gitlab link is valid and matches the current github repo, so I'm ready to write the complete result.json file.

I'll keep the pre-registration fields exactly as they are, just fixing the timestamp, and use a script to load and append the new fields so I don't have to retype everything.

That looked like a transient error, so I'll retry the same command, but first let me check if result.json actually changed.

I'll write the script to a temp file in /tmp to avoid cluttering the repo, then execute it from there.

Looks like another session touched this directory—git shows an earlier commit, and `analysis.py` and `derived/measured.json` have later timestamps than my last edit and run. Checking what changed in them.

I realize the diff just reflects my own edits against a snapshot from the user's restructure commit, which captured things mid-run — the pre-registered result.json, the pre-exploratory analysis.py, and the flawed first run's log. I'm now trying to pin down the timing of my edits relative to when that run actually finished.

The mtime discrepancy is probably from the git checkout/stash operations around 16:38-16:39 touching file timestamps rather than anything suspicious. I verified measured.json's values match what was printed during finalize (-31.5 etc.), so the content is consistent and trustworthy.

The derived_run.log deletion makes sense — that log was from the buggy first solver run, and I correctly removed it before rerunning. I should note this to the user. The data/.gitignore is covered by the parent ignore, and since result.json is valid and analysis.py reproduces the measured values, everything checks out and I'm ready to report back.

**Claim id:** levin-2018-hcn2-06

**Verdict:** inconclusive, reason "other". This is what the pre-registered rule required.

**Confidence:** 0.60

**Key measured number:** −31.5 mV. HCN2 overexpression drives the neural tube from −55.3 to −86.8 mV, while the lateral regions (neural folds and ectoderm) move at most 4.0 mV. That model doesn't reproduce the paper's control pattern, though, which is why the verdict is inconclusive.

**Why inconclusive:** with cells facing 0.1× MMR, as the paper states, no leak scale or gap-junction strength reproduces the paper's control (tube −50, lateral −5 mV). Fig. 2a's leak ratio for the folds and ectoderm (Na:K:Cl = 1:1:15) makes chloride outflow dominate in that medium. The lateral regions then sit near +22 mV. The pre-registration said a failed calibration means inconclusive.

**What the simulations show:**
- **Closest model** (0.1× MMR, BETSE's default gap-junction strength, control −55/−19/−2 mV):
  - Every amplification criterion passes against both baselines (wild-type HCN2 and no HCN2).
  - HCN2's reversal potential is −97 mV, and it opens 87× more in the tube than in the ectoderm. Within this medium the claimed switch is reproduced.
- **Not robust in the exploratory sweeps:**
  - At 3× the paper's overexpression level or more, gap-junction coupling pulls the whole sheet down, so lateral regions also shift about 94 mV.
  - The selective range is under the one decade I pre-registered.
- **Alternative medium:** with membranes facing the Table 1 intercellular-space concentrations instead, the control matches the paper almost exactly (−49.5/−5.0/−5.0 mV). But HCN2's reversal is then −36.5 mV, and overexpression depolarizes the tube by 4.6 mV, the opposite of the claim. So the outcome depends on what the membranes face, and the paper doesn't say how BETSE handled this.

**Method:** the paper's BETSE configuration isn't published, so full BETSE wasn't run. The BETSE repository holds configs only for two other 2016–2018 papers. Instead I used a pre-registered minimal re-implementation (numpy only) of the paper's stated model. It uses Supplementary Note 1 for HCN2 and Kir, Table 1 for concentrations, Fig. 2a for the regional leak ratios and BETSE's gap-junction model, on a 711-cell sheet. Pumps and concentration changes over time aren't modelled.

**Repo notes:**
- Another session restructured the repo during this run. The test now lives in `test-data/claim-tests/levin-papers/levin-2018-hcn2-06/`.
- Its restructure commit captured an early snapshot of my files, including a log from a first run with a solver bug. I fixed the bug (checked against brute-force integration), reran everything, and deleted that stale log.
- The current files in the working tree are correct. Nothing was committed, signed or published by me.

_Tools used: AwaitShell ×6, Read ×10, Shell ×46, StrReplace ×10, UpdateCurrentStep ×4, Write ×5_
