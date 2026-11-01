# Multiscale simulation: executable evidence and next 24 hours

The first new atomistic result is an **actual OpenMM simulation of the experimental
1K6F collagen-mimetic triple helix**. Its CPU numerical controls passed; its short
CPU trajectory and movie exist. The three-seed CUDA job completed on an H100 after the first attempt stopped at
a numerical measurement gate; both attempts and the justified repair are retained. Execution state and biological
applicability are separate fields in the [model index](../artifacts/molecular/model-index.json).
The table below is a queue, not a claim that every simulator has been installed.

## What the molecular result establishes

[Berisio et al. 2002, 1K6F](https://pmc.ncbi.nlm.nih.gov/articles/PMC2373432/)
reports a synthetic (Pro-Pro-Gly) collagen-mimetic trimer. The selected author/PISA
assembly1 contains three modeled 29-residue chains; terminal Gly 30 is absent in all
three. We retained the modeled residues, added terminal OXT atoms and hydrogens
with [PDBFixer](https://github.com/openmm/pdbfixer) and OpenMM, removed crystal
waters, then added explicit TIP3P water and 0.1 M ions. No hydroxyproline was changed
into proline; this structure already contains standard Pro/Gly. The RCSB sequence
cross-reference to a viral protein is not the biological identity used here: the
source paper describes a synthetic collagen model, not a viral functional assay.
Coordinates are distributed under the [PDB data usage policy](https://www.rcsb.org/pages/policies).

The 10,491-atom system uses [ff14SB](https://pubmed.ncbi.nlm.nih.gov/26574453/),
PME,0.9 nm cutoff, constrained hydrogen bonds, rigid water, free charged termini,
LangevinMiddle300 K target/1 ps⁻¹ friction and1 fs integration. Conditions are declared
scenarios. [Hartmann and Zacharias2021, Materials and methods](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1009079)
provides a relevant ff14SB collagen-mimetic precedent, but used OPC, a different
peptide, special nucleus restraints and much longer trajectories. This is **not**
a reproduction of its folding kinetics. That paper's protocol motivated the
choice; it did not calibrate ours. Force-field and solvent sensitivity remain
open, consistent with the [later comparative collagen study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12414705/).

Frozen protocol0437e87 precedes outputs. The CPU controls decreased potential
energy from −50,890.3 to−144,778.1kJ/mol; a central force-gradient check had relative
error0.001663 against its predeclared0.005 bound, while a wrong-sign mutant had
error2.001663. Matched 50 fs NVE trajectories gave energy drift/initial kinetic
energy0.001334 at 1 fs and0.0002825 at 0.5 fs; the final solute-coordinate discrepancy
was0.0001157nm after rigid alignment. These are numerical checks of this system,
not estimates of empirical or fish-biological accuracy.

The delivered CPU production trajectory covers0.2 ps after0.1 ps preliminary
thermalization, with 101 actual coordinate frames. Final aligned Cα RMSD from
production start is 0.03852 nm. The actual kinetic temperature is 187–223 K
despite the 300 K thermostat target, confirming that this CPU setup run is not
thermally equilibrated. This tiny setup trajectory does not establish an
equilibrated ensemble, folding stability, kinetic rate or material stiffness.
The CUDA protocol requests three 100 ps trajectories after10 ps preliminary
thermalization, retaining the same caution. Seeds share one structure and force
field; their spread is descriptive, not independent empirical evidence or a
biological success probability.

Collagen is relevant to fin scaffolds: [Kuroda et al.2024, Results/Discussion](https://pmc.ncbi.nlm.nih.gov/articles/PMC11409509/)
tracks actinotrichia remodeling during zebrafish fin growth. Our synthetic repeat
is not a native zebrafish/flying-fish collagen sequence. Hydroxylation, fibril
assembly, crosslinks, mineralization, tissue geometry, composition and strain-rate
response are missing. The [native coupling gate](../artifacts/molecular/cross-scale-gate.json)
therefore **refuses molecular chain length→fin flexural rigidity**. Converting nm
to m does not supply the missing constitutive law. No molecular derived modulus
is fed to the existing motor-clutch or fin-beam solver.

## Prioritized model matrix

Readiness refers to this project at the checkpoint. Setup costs below are planning
estimates, not measured runtimes or provider spend. Owner reports remain attributed
until their pinned receipts are inspected. Existing models should be reused.

| Priority / model | Biological scope and actual inputs | Coupling ports; missing bridge | Compute / setup / readiness |
|---|---|---|---|
|1 OpenMM1K6F MD | Synthetic collagen-mimetic structure, ff14SB/TIP3P, explicit assumptions | Atom positionsnm, Cα RMSDnm, chain distancesnm; no fibril/tissue law | CPU and H100 CUDA runs complete; setup done |
|2 [Morpheus cell-cycle example](https://morpheus.gitlab.io/courses/multiscale-models/example/) | Source ODE→CPM division→cytokine PDE→ODE loop | CDK1/APC, cell shapes/division, local cytokine; source model units are not fish calibration | CPU; moderate setup; claude06 owns baseline/feedback knockout |
|3 [BETSE](https://github.com/betsee/betse) | Ion concentrations, channels, pumps, gap junctions,2D tissue geometry | VmV, concentrationmol/m³, junction current; channel density and fish tissue geometry missing | CPU; moderate setup; dx-market-r1 owns control/intervention |
|4 [Zebrafish-GEM](https://github.com/SysBioChalmers/Zebrafish-GEM) | Actual generic Danio SBML, exchange bounds and objective | O₂/ATP/biomass fluxmmol/gDW/h; biomass is not fish growth, flux is not ATP concentration | CPU LP; low–moderate setup; claude11 owns FBA |
|5 [WaterLily](https://github.com/WaterLily-jl/WaterLily.jl) | Actual fish-derived STL, incompressible3D fluid, declared Re | Surface pressurePa/tractionN→beam loadN/m; geometry-to-ray mapping and EI remain assumed | CPU controls then1 GPU; moderate setup; claude04 owns |
|6 Existing fin-beam+glide | FEM ray surrogate, declared load/EI envelopes, fish-derived outer dimensions | q(s)N/m→deflectionm; projected area/dynamic flight coefficients uncalibrated | CPU; ready, reuse actual controls/ensembles |
|7 Existing Shenoy-lab motor-clutch | [Gong2018 Eqs1–6](https://pmc.ncbi.nlm.nih.gov/articles/PMC5866566/), stochastic adhesion+viscoelastic feedback | TractionpN, displacementnm, relaxationtime; tissue mapping/other defaults assumed | CPU; existing600-run sweep, reuse rather than duplicate |
|8 Existing ERK-scale model | [Hayden2021 Eqs/Table1](https://pmc.ncbi.nlm.nih.gov/articles/PMC8516634/), zebrafish scale regeneration | Active Erk fraction, activator field, wave speedµm/h→growth; new cell type/fin transfer unknown | CPU/GPU PDE; existing owner work, inspect exact pins before rerun |
|9 Enzyme-cascade SBML | [Huang/Ferrell1996 MAPK, BioModels0000000009](https://www.ebi.ac.uk/biomodels/courses/20130627/Huang1996.pdf) | Kinase/phosphatase totalsµM→ppMAPKµM; Xenopus rates cannot silently set zebrafish ERK-wave rates | CPU CVODE/COPASI; reuse installed SBML engine; source retrieval gate pending403 |
|10 Physiome/HH | [CellML squid-axon model](https://models.physiomeproject.org/workspace/hodgkin_huxley_1952), existing HH implementation | VmV/spike timing→actuation is only a declared scenario; not fish neurons | CPU; existing49-run study, no generic sweep expansion |
|11 Existing behavioral CPG | Source-grounded salamander/robot oscillator with zebrafish context, not neuron reconstruction | Phaserad/frequencyHz→servo anglerad/torqueNm; no neural-to-muscle calibration | CPU; ready; small-angle CFD actuation still gated by moving-boundary solver |
|12 Native OpenFold2 service | Unmodified canonical Danio Kcnj13 sequence, sourced separately by service owner | Monomer coordinates/confidence; not tetramer assembly, membrane embedding, ion selectivity or conductance | Managed inference; resource_scaling owns one call; no BioNeMo claim |
|Fallback CompuCell3D / PhysiCell | [CC3D](https://compucell3d.org/) CPM/SBML/PDE or [PhysiCell](https://physicell.org/) off-lattice cells/substrates | Cell positions/volumes, molecular fields; cell-specific rules/units must be fitted | CPU, optional engine-specific GPU PDE; source-only; do not install alongside working Morpheus |
|Next-stage FEBio / FEniCS | [FEBio multiphasic](https://febiosoftware.github.io/febio-docs/features/modules/module_multiphasic/) mixtures/reactions or [FEniCS](https://fenicsproject.org/) specified PDE weak form | Solute concentration, chemical reactions, stress/strain/growth; kinetics/constitutive properties missing | CPU first; high setup; source-only; useful after simple coupled controls |
|Fallback IKA-FLOW | [Published OpenFOAM fish-undulation cases](https://journal.openfoam.com/index.php/ofj/article/view/89) | Prescribed body motion→flow/forces; underwater swimming is not aerial gliding | CPU CFD, large setup; source-only, fallback to WaterLily setup failure |
|Longer-term eco-evolution | [SLiM](https://messerlab.org/slim/) individual-based population genetics; measured demography/fitness needed | Allele frequencies/lineages; no genotype→fin-geometry or simulated flight→fitness map | CPU; source-only, blocked on biological fitness model; no adaptive success claims |

The existing 2D D2Q9 wind-tunnel proxy remains useful for CPU/CUDA parity and
geometry/angle sensitivity. Its low-Re sagittal extrusion is not 3D fish CFD.
The3D solver work must retain its independent grid/time/boundary checks; it does
not inherit3D validity from the 2D result. FEBio and FEniCS are numerical engines,
not ready biological parameterizations. [FEBio's coupled growth paper](https://publications.sci.utah.edu/publications/Lab2025a/bio_147_06_061004.pdf)
is a candidate to read fully; direct web retrieval timed out here, so no equation
or parameter is attributed to it at this checkpoint.

## Next 24-hour queue

Each entry needs a frozen protocol before output generation. Estimated compute
budgets are caps for useful questions, not targets for machine occupancy. The
infra owner serializes GPU use and records actual job IDs, image digests and spend.

| Order / scientific question | Inputs and paired intervention | Numerical gate | Measurable result / artifacts / resource cap |
|---|---|---|---|
|Completed: does the molecular system run consistently on CUDA? | Frozen1K6F packet; same generated System/State onCPU andCUDA;3seeds | Frozen CPU gradient/sign/NVE checks; forceL2 relative<0.002 and energy error/atom<0.01kJ/mol before production |100 ps/seed coordinates, RMSD/end distances/temperature traces; inputXML,NPZ,JSON,MP4;1 H100,1500 s workload cap,16 MB output parts; infra job receipt controls truth |
|Next: does a genuine intracellular/tissue feedback link change division dynamics? | Morpheus source example versus disabled cytokine→cell-cycle term, same initial state/seeds | ODE tolerance and timestep comparison; PDE diffusion control; cell/field bookkeeping; retain model-unit limits | Cell counts/division times and cytokine fields, paired differences; XML/CSV/frames/MP4; CPU 2 threads,600 s initial cap; claude06 |
|Next: do gap junctions transmit an imposed local ionic perturbation? | BETSE baseline versus blocked junction conductance, fixed geometry/channels/pump setup | Charge/ion balance where appropriate, no-coupling control, timestep refinement; actual simulator constraints retained | Vm spreadmV, ionic balances, propagation/relaxation time; YAML/CSV/NPZ/movie; CPU 2 threads,600 s first slice; dx-market-r1 |
|Next: how does oxygen availability constrain model ATP support? | Exact Zebrafish-GEM SBML, bounded oxygen exchanges, fixed medium; objective/treatment separated | LP optimality, Sv residual, bound satisfaction, infeasible cases retained, ATP/biomass objective distinctions | Feasible ATP/biomass flux envelopes, alternate-optimum/FVA ranges if supported; SBML hash/fluxCSV/JSON; CPU 2 threads,600 s; claude11 |
|After 3D controls: can pressure transfer conserve force and change fin deflection? | Same fish mesh pressure field→declared tributary fin strips→existing beam; uniform-pressure analytic partner | Surface-normal sign, ∫tractiondA conservation, quadrature/grid refinement, analytic cantilever control; no unstable FSI loop | ForceN, q(s)N/m, deflection/span and admissibility across existing EI candidates; mesh+field+load+FEM receipts; CPU 600 s bridge, GPU only for bounded CFD; claude04+science owner |
|After source retrieval: is enzymatic ultrasensitivity preserved when a phosphatase total changes? | Huang/Ferrell SBML exact version and rates; kinase/phosphatase paired perturbation; no activity transfer to fish | Conserved enzyme/substrate pools, positivity, CVODE tolerance check; kinase-zero negative control | ppMAPK input/output curve and transientµM, mass residuals; SBML/CSV/JSON; CPU 60 s model run cap; not yet dispatchable |
|After returnedMD assessment: is structural spread sensitive to solvent/force-field choice? | Same modeled motif/termini, one additional fully parameterized published force-field/water pair | Reparameterization audit, gradient/parity controls, independent time-step check; do not compare energies across different Hamiltonians as free energies | Matched structural observables and between-model disagreement, with sampling limits;1 GPU, predeclared small budget after benchmark; not yet dispatchable |
|Later: is a molecular mechanical parameter identifiable? | Longer equilibration, explicit strain/pulling protocol plus held-out single-molecule data; actual native/modification status required | Pull-rate sensitivity, load/unload hysteresis, timestep and force checks; force-field sensitivity | Force-extension/relaxation with units, rate dependence and uncertainty; no tissue EI until fibril/tissue calibration exists; blocked on data/protocol |

Protein structure prediction can seed a structural hypothesis. It supplies neither
an enzyme'skcat/Km nor an ion channel's conductance. Short unbiased MD cannot
supply these quantities either. A defensible enzyme-rate bridge needs kinetics
experiments or validated rare-event/free-energy methodology; a channel bridge
needs the correct assembly, membrane/lipids, ions, voltage and adequately sampled
permeation/gating, followed by functional validation. These are explicit missing
jobs, not defaults filled from a confidence score.

## Access and provenance

The lab homepage failed in the web tool but directHTTP and publicJina both returned 200;
Jina contentSHA794d06618c288b5fae978ba4f5b98735dee72a5039588624e1539a531b3d3e13.
BioModels0000000009 returned 403; publicJina also carried the 403 body, so no SBML
bytes were claimed retrieved. The source paper and BioModels training materials
establish it as a candidate, not a completed replay. PMC actinotrichia initially
showed a challenge; publicJina returned full text, SHA013602c85950fbb7be18c34db7f5f6a42cb85e4da4a8c56edffe9eaa631d352a.
Research reading and executable model checks are distinguished in the model index.

[CPU video](../artifacts/molecular/cpu-render/trajectory.mp4),
[poster](../artifacts/molecular/cpu-render/poster.png),
[render provenance](../artifacts/molecular/cpu-render/render.json),
[simulation receipt](../artifacts/molecular/cpu-trajectory-final/receipt.json),
[numerical controls](../artifacts/molecular/cpu-controls/controls.json),
[typed molecular interface](../artifacts/molecular/model-interface.json).
The first exploratory CPU receipt had a source-file hashing race and was excluded,
then rerun with import-time code hashing and an exact saved producer source.
Its excluded bytes remain outside the release evidence for audit; no result was
silently substituted. Simulation and render hashes are separate.

## First GPU attempt: preserved numerical gate failure and repair

Job `aijob-e00a3q798jsc6fdbas` stopped before CUDA production. Its CPU finite-
difference force error was 0.006232 against the frozen 0.005 limit; minimization
and both NVE checks passed. The [failed controls](../artifacts/molecular/gpu-attempt-1/controls.json)
remain failed. On the exact recovered minimized state, the diagnostic reproduced
CPU derivative error 0.006657 at the same 0.00001 nm perturbation. At smaller
perturbations the CPU error worsened, consistent with cancellation in differences
of large total energies. The high-precision Reference implementation had derivative
self-error 4.86e-8 at the original perturbation; CPU force versus that derivative
had error 6.11e-6. Full CPU/Reference force-vector discrepancy was 4.61e-5.

Protocol revision 2 was committed before repaired-control outputs. It evaluates
finite-difference energies with the double-precision Reference backend and compares
them against CPU forces at the same coordinates. The perturbation and original
0.005 gradient limit remain unchanged; a full-vector force comparison is added.
The complete repaired control run on the recovered preparation passed: gradient
error 8.52e-5, full-vector discrepancy 4.60e-5 and NVE drift ratios 0.001411 and
0.0003601. This repairs the precision of a numerical measurement, not the physical
model or its empirical validity. No acceptance was relaxed. The first failed job
is not relabeled as a pass. At that checkpoint, a subsequent CUDA run still needed its own passing
same-system CPU/CUDA gate and actual trajectory receipt; the completed result is
recorded below.

## Actual CUDA result returned

The justified retry `aijob-e00h8rra7x8ams6jyn` completed all three 100 ps production
runs on an NVIDIA H100 80GB HBM3 with CUDA mixed precision, after 10 ps preliminary
thermalization each. I independently verified all 20 returned job-file SHA256
values. The same-system CPU/CUDA comparison passed: energy difference per atom
1.394e-5 kJ/mol and relative force L2 difference 2.015e-5, against the unchanged
0.01 and 0.002 limits. Remote Reference force-gradient and paired NVE checks passed.
Production took approximately 18 seconds per seed; installation, preparation,
controls and result return are separate costs.

Each trajectory contains 101 actual heavy-atom coordinate frames. Final aligned
Cα RMSD from each run's own production start was 0.14648, 0.14659 and 0.16546 nm;
the descriptive sample SD is 0.01093 nm over these three shared-model seeds.
Last-20%-window kinetic temperature means were 300.01, 300.10 and 301.44 K.
The short trajectories do not establish an equilibrated conformational ensemble,
a molecular/tissue modulus, or native fish performance. No biological success
probability is assigned.

[CUDA actual-state video](../artifacts/molecular/cuda-render/trajectory.mp4),
[poster](../artifacts/molecular/cuda-render/poster.png),
[three-seed traces](../artifacts/molecular/cuda-analysis/ensemble.png),
[descriptive analysis](../artifacts/molecular/cuda-analysis/ensemble.json),
[full simulation receipt](../artifacts/molecular/cuda-v2/production/receipt.json),
[backend parity](../artifacts/molecular/cuda-v2/cpu-cuda-parity.json),
[regional-assurance-compatible vector](../artifacts/molecular/design-assurance.json).
The first failed attempt remains distinct. The longer conditional continuation recorded below was
proposed because the 100 ps structural traces still exhibited slow drift;
that observation is not evidence for organism function or an invitation to infer
material constants from RMSD.

## Actual conditional extensions to 1000 ps

Job `aijob-e00qxektzctnk69zwg` returned three 900 ps extensions from the exact
recorded 100 ps parent states, using newly declared thermostat seeds 11731–11733.
The original positions and velocities were preserved, with no minimization,
velocity reset or further thermalization. State XML does not preserve the
integrator RNG stream: these are conditional branches, not bitwise replays.
All 33 returned job-file SHA256 values were independently checked; all three
same-state derivative/sign, paired NVE and CPU/CUDA parity gates passed. Actual
CUDA production took 136.74, 136.45 and 137.96 seconds on an H100. Each extension
contains 101 actual heavy-atom frames. Its first frame exactly matches its parent's
final saved float32 frame; there are three parent branches, not six independent
biological samples.

The frozen diagnostic compares the 600–800 and 800–1000 ps windows, requiring both
mean original-reference Cα RMSD and geometric Cα radius-of-gyration changes to be
below 0.02 nm. Outcomes were **false, false, true**, retained without threshold
changes. RMSD changes were 0.0202865, 0.0293491 and 0.00047693 nm; radius changes were
0.00409193, 0.0169493 and 0.0153386 nm. The sampled windows contain 22 and 23 frames,
respectively (actual times 604–793 and 802–1000 ps). These are descriptive finite
windows; even the true outcome does not establish equilibrium, folding stability,
a material modulus or biological success. No success probability is assigned.

Final Cα RMSD from each original parent's production start was 0.27088, 0.17068 and
0.26715 nm; geometric Cα radii were 2.47439, 2.45820 and 2.41163 nm. These calculated
values are not measured accuracy. Empirical force-field accuracy and transfer to
native fish collagen, fibrils, tissue mechanics and fin bending stiffness remain
unknown. A further run requires a scientific question and its own frozen protocol;
the two negative window diagnostics do not justify arbitrary workload expansion.

[Actual continuation movie](../artifacts/molecular/continuation-render/trajectory.mp4),
[poster](../artifacts/molecular/continuation-render/poster.png),
[parent-plus-extension traces](../artifacts/molecular/continuation-analysis/conditional-branches.png),
[recomputed diagnostic and continuity](../artifacts/molecular/continuation-analysis/summary.json),
[frozen protocol](../artifacts/molecular/continuation-protocol.json),
[production receipt](../artifacts/molecular/cuda-v3/production/receipt.json).

## Soft-voxel mechanics: a runnable workload, and a catalog of what else exists

This section adds a second executable track beside the molecular one. It is not a
fish or a frog result. It is generic soft-body voxel mechanics, chosen because it
runs today on CPU in seconds and because its actuation law is simple enough to check
against a closed form rather than against an opinion.

### The engine that runs

[Voxelyze](https://github.com/jonhiller/Voxelyze) at pin
`4287e365e11416dd108f2f361e9ec4c5a011a16c`, library version string
`voxelyze.0.9.92`, builds with the unmodified upstream `make` in **11.45 s** on
g++ 13.3.0 under Ubuntu 24.04 and exits 0. The full recipe in
[`scripts/voxel_actuation/build.sh`](../scripts/voxel_actuation/build.sh), starting
from an empty directory, takes **17.85 s** and exits 0. It needs no CUDA, no Boost
and no CMake, and the longest simulation run in this work was **8.6 s**. Every
invocation ran under `MemoryMax=2G`, `MemorySwapMax=0` and `nice -n 19`; nothing was
installed system-wide and no package manager was invoked.

One upstream defect is worth recording because it looks like our bug: the shipped
makefile's default `FLAGS` contain `-DPARDISO_5=1`, which leaves undefined references
to `pardisoinit` and `pardiso` in the archive, so any program linking it fails unless
a commercial Pardiso 5 library is present. Overriding `FLAGS` to drop the define fixes
it; `doLinearSolve()` is unused here.

Its licence needs stating carefully. The GitHub API reports `license: null` because
**there is no LICENSE file at that commit**. Every `src/*.cpp` and `include/*.h`
header declares **LGPL-3.0-or-later**, and those headers are the licence of record.
"The API says null" is not "unlicensed". We commit our driver source and a build
recipe and redistribute no linked binary.

### What was measured, and what failed

The protocol was frozen at `7b9bd5d` before any output existed, with predeclared
expectations for every arm. Results and receipts are in
[`artifacts/voxel-actuation/`](../artifacts/voxel-actuation/); the summary with the
preregistration outcomes is
[`summary.json`](../artifacts/voxel-actuation/summary.json).

Six actuation phase patterns, matched in material, amplitude, frequency and duration,
rank travelling **0.3644** body lengths in five cycles, longitudinal **0.1532**,
lateral **0.1412**, dorsoventral **0.0031**, checker and uniform at **1e-5**. None
diverged.

The controls are what make that table worth reading. Setting the coefficient of
thermal expansion to zero and setting the temperature amplitude to zero give
numerically identical, essentially zero displacement, as they must, since both zero
the same product. Removing friction gives **exactly 0.0** horizontal displacement:
centre-of-mass x and y are constant to nine decimals across all 241 samples while z
ranges 0.009967 to 0.011017 m, so the body is demonstrably active and its horizontal
centre of mass does not move. That is the conservation prediction, not a dead run.

Two analytic positive controls reproduce their closed forms at ratio **1.0000** — free
thermal expansion against the zero-stress size law, and an end-loaded cantilever
against `F L^3 / (3 E I)`, which is the same mechanical slice SPEC-013 and SPEC-017
already name. Three must-fail mutants are rejected at ratios 1.2222, 1.1000 and
10.0000, each **while settled and not diverged**, which is the condition that stops a
crash from counting as a negative control.

Two things failed, and both are kept.

**One predeclared expectation was wrong.** The zero-gravity arm was predicted to give
at most 0.01 body lengths and gave 0.0175. The argument behind the prediction was
wrong, not the threshold: it assumed that removing gravity removes the normal force.
With the floor still enabled, actuation itself drives voxels into the floor and
generates transient normal force, so friction still acts. The frictionless arm is the
control that actually isolates friction. The threshold was not changed.

**Spatial refinement did not converge.** 0.1532 body lengths on a 5x3x3 body of 10 mm
voxels against 0.0188 on a 10x6x6 body of 5 mm voxels, an 8.2x drop. The protocol
predicted no convergence and said so in advance.

Two post-hoc diagnostics, labelled as such in the artifact, explain it. Global damping
as the cause is **refuted**: displacement rises with the damping ratio at both
resolutions, and matching total drag widens the gap to 15x rather than closing it.
Actuator-layout parity is **supported**: at fixed 10 mm resolution and fixed damping,
`nx` = 4, 5, 6, 7 give 0.0200, 0.1532, 0.0086 and 0.0796 body lengths, so an odd
voxel count moves 7.6x to 17.8x further than its adjacent even neighbours (nx5/nx4 = 7.65, nx5/nx6 = 17.81, nx7/nx6 = 9.25; non-adjacent pairs are not part of the claim). The longitudinal
pattern splits at `x < nx/2`, so the refinement arm confounded lattice resolution with
actuator-layout asymmetry. That is an artefact of our encoding, not of the engine.

With the confound removed — the travelling-wave pattern sets phase as a gradient and
so carries its own asymmetry at any `nx` — the two bodies move **14.577281 mm** and
**16.847525 mm**, a **15.57% difference relative to the coarse run**.

**An earlier version of this paragraph said 2.74%, and that figure is withdrawn.** It
divided the two runs by two *different* denominators. The stored normalisation is
`body_len = (nx-1) * voxel`, the centre-to-centre span, which is 40 mm for the coarse
body and **45 mm** for the fine one, because halving the voxel while doubling the count
adds half a lattice spacing. Dividing by two different lengths manufactured an agreement
that is not in the data. The outer envelope `nx * voxel` is 50 x 30 x 30 mm for *both*
bodies and the nominal mass is 45 g for both, so the envelope is the invariant length
here; at that common 50 mm denominator the two give 0.291546 and 0.336950, which is the
same **15.57%**. The frozen centre-span metric is preserved in the artifact beside the SI
values and both denominators. Raised by independent review of `e6f1033`; all eight of its
figures were recomputed here from the stored artifacts and all eight match.

So the travelling pattern is far less resolution-sensitive than the longitudinal split's
8.2x, and that is all. **15.6% is not agreement, and one pattern on two grids cannot
establish convergence under any denominator.** The parity diagnosis does not cure the
remaining discretisation and normalisation issues. The timestep series does converge,
0.9% of the coarsest value across a 4x range of `dt`, and that statement is about `dt` on
that one arm.

### The cross-scale interface this adds

`actuation-pattern-to-motion/1`. Inputs are a per-voxel actuation phase field in
radians, a coefficient of thermal expansion per degree C, a temperature amplitude, a
drive frequency, a Young's modulus in Pa and friction coefficients. Outputs are net
centre-of-mass displacement in m, displacement per cycle, displacement in body
lengths, path length and the full trajectory. The transfer is **mathematically defined
and numerically checked, and empirically unvalidated**: no measured organism
displacement is compared anywhere in it.

The relation it supports, stated with its conditions, is that **net displacement per
cycle is produced by spatial asymmetry of the actuation phase field, not by actuation
amplitude alone**, with a mirror-symmetric field yielding roughly an order of magnitude
less than an asymmetric one at matched everything else. Its conditions are the
specific lattice, the linear elastic parameters, Coulomb friction on a rigid floor,
global damping to a stationary absolute frame, explicit Euler at half the recommended
timestep, five cycles at 4 Hz and 10% peak linear strain. Its validation data is the
six-pattern arm, the four-point parity series, the two-resolution refinement of the
travelling pattern, four behavioural controls, a timestep series and five analytic
gates.

**It is not a biological law.** It is a property of one numerical soft-body model under
declared parameters, and no organism, tissue or cell measurement enters it. The object itself is a
**numerical soft-voxel ground-contact mechanics benchmark, not tissue**: 45 nominal 10 mm
voxels, an outer envelope of 50 x 30 x 30 mm, a 40 mm centre-to-centre span and a nominal
45 g at the assumed 1000 kg/m^3. It is not tissue-scale, not a Xenopus or microcarrier
model, and not material-calibrated. The known
If anything from this track is rendered,
`artifacts/voxel-actuation/trajectory/travelling-voxels.csv` stores voxel **centres and the
imposed temperature only** — no orientations, no deformed voxel meshes, no forces. A renderer
may draw centre points, a link graph or nominal glyphs and must label them as such; it must not
invent cellular textures, traction arrows or deformed tissue boundaries, and `temp_C` is an
imposed numerical actuation signal rather than a measured cellular state. Use SI axes, and if
body lengths are shown, say which denominator.

The known threat to its validity is that the rectifying ground reaction is part Coulomb friction
and part global damping to an absolute frame — Voxelyze's global damping is a numerical
term and not a fluid model, so no swimming interpretation is available — and the split
between those two mechanisms has not been measured.

### One measurement that would calibrate the missing biology

Three parameters in that interface are declared assumptions with no measured referent:
the coefficient of thermal expansion standing in for active contraction, the drive
amplitude and the drive frequency. A fourth, Young's modulus, is inherited from a
simulator demo file rather than from tissue.

The single measurement that would replace them is **the free contractile strain
amplitude and its frequency, together with an independent quasi-static elastic
modulus, all taken on the same specimen of the candidate contractile tissue**.
Peak-to-peak linear strain under negligible load sets the product of expansion
coefficient and amplitude directly; the beat frequency sets the drive frequency; and a
calibrated modulus on that same specimen sets `E`. Same-specimen matters more than
precision here, because the three are currently drawn from three unrelated places, and
a context-matched triple is what makes them a parameterisation rather than three
coincidences.

It would not fix everything, and the gap it leaves should be named now: it says
nothing about friction or adhesion against a real substrate, and nothing about whether
the rectifying reaction in a real construct is frictional or viscous. Those need their
own measurement, and until then the ranking above is a ranking inside a simulator.

This paragraph describes quantities and what they would license. It is not a
laboratory protocol and nothing here has been executed in a laboratory.

### The engine catalog

[`artifacts/simulator-catalog/catalog.json`](../artifacts/simulator-catalog/catalog.json)
holds twelve engines with per-entry read levels: one built and run here, three already
in use on this project, seven source-only and one blocked. Each entry carries its pin
or version, its licence with the evidence for that licence, scale and state variables,
supported couplings, compute requirements, applicability limits, parameter gaps,
public examples and available controls. The ranking in it is a ranking of **practical
readiness for this project**, not of scientific quality.

Its most load-bearing property is a vocabulary of read levels, because most of its
equation fields honestly read `not-read-here`. Nine of the twelve entries need a
reading pass before their governing equations may be cited, and the catalog says which
file or DOI to open for each. A verified Crossref record establishes a title, authors,
venue and DOI; it does not license a claim about an equation.

Three licence findings in it are worth surfacing here because each is a trap.

**The website and the repositories disagree.** `https://cdorgs.github.io/code` states
verbatim that *"The source code and build instructions are distributed under an
Attribution-NonCommercial Creative Commons license"*, linking CC BY-NC 4.0. Every
repository it links — `voxcraft/voxcraft-sim`, `voxcraft/voxcraft-viz` and
`skriegman/reconfigurable_organisms` — carries a **CC0-1.0** LICENSE file, confirmed
from the file bytes. Rely on the LICENSE file in the repository you actually clone and
record that the website says otherwise. Neither statement should be quoted alone.
Separately, `reconfigurable_organisms` declares CC0 at its root while vendoring
Voxelyze, whose per-file headers declare LGPL-3.0-or-later; a repository-level CC0 does
not obviously reach vendored third-party code.

**`license: null` from the GitHub API means two opposite things.** For Voxelyze it
hides LGPL-3.0-or-later in the source headers. For PhysiCell 1.14.2 it hides
BSD-3-Clause in `licenses/PhysiCell.txt`, alongside separate licence files for BioFVM,
MaBoSS and pugixml that a reuser must check as well. In both cases the API is reporting
the absence of a root LICENSE file, not the absence of a licence.

**The SOFA inverse plugin carries a patent grant scoped to itself.**
[SoftRobots.Inverse](https://github.com/SofaDefrost/SoftRobots.Inverse) is AGPL-3.0
with an added clause file recording an Inria patent, *"Method for controlling of a
deformable robot, associated module and computer program"*, French priority
2013-02-08, publication numbers FR3002047, WO2014122134A1, US2015360367A1,
EP2954429A1 and JP2016513021A. Its own words: AGPLv3 Clause 11 grants a royalty-free
licence to the patent *"when you use 'SoftRobots.Inverse' software or any derivative
software work (i.e., developed from the source of that software)"*, and *"Any other
exploitation of the patent, in particular by using a software solution to implement
the method other than 'SoftRobots.Inverse' ... is not covered by this license."* Inria
names `stip-lille@inria.fr` for a separate licence. The practical reading for us is
narrow and specific: reimplementing that inverse method in our own code would not be
covered by this grant, and AGPL-3.0 network use carries a source-provision obligation.
This is a statement of what the licence files say, not legal advice, and it is not a
claim about anyone's commercial position. None of it applies to the SOFA core, which is
LGPL-2.1, or to the forward SoftRobots plugin, which is LGPL-3.0.

### GPU: what is blocked, and what nobody has run

[voxcraft-sim](https://github.com/voxcraft/voxcraft-sim) at pin
`dd8668f99ff74fb2fc2ee60deb91287a3b519d8f` is the engine the computationally designed
organism results actually used, and it is the only GPU path in the voxel line. It is
**blocked here**: this host has no GPU and no CUDA toolkit — `nvidia-smi` is absent and
`/usr/local/cuda*` does not exist, checked against a positive control that
`/usr/local` does — and its `CMakeLists.txt` autodetects the target architecture by
probing a GPU at configure time, so even a configure is not meaningful here. Its README
asks for CUDA 10.1 while its Dockerfile pins `cuda:10.2-devel-ubuntu18.04`, which is a
further reason the version question has to be settled by a run.

**No claim is made here about whether it works on a modern GPU.** A two-arm probe with
definite acceptance is specified in
[`docs/handoff/xenobot-packet-to-infra.md`](handoff/xenobot-packet-to-infra.md): one
arm builds at the pin under a current CUDA toolkit with the architecture forced rather
than autodetected, and one builds in the pinned 10.2 image with an explicit PTX
`gencode` so the driver has something to JIT forward. Infra owns the dispatch; this
branch does not launch cloud jobs.

### Differentiation, stated against the actual prior art

The forward-generation roadmap in [`research/generative-roadmap.md`](research/generative-roadmap.md)
must not be pitched as novel, and the engine catalog is where that stays honest. A
diffusion-model surrogate trained on forward output from a mechanistic agent-based
biological model is **published**: Comlekoglu and colleagues, *Generative diffusion
model surrogates for mechanistic agent-based biological models*, arXiv 2505.09630, DOI
`10.1088/2632-2153/ae11f8`, on a cellular Potts model — the same model class as the
Morpheus instance already running on this project, with a reference implementation at
`tc2fh/CPM_DDPM_Surrogate`. Read at abstract level and recorded in
[`data/research/prior-art.json`](../data/research/prior-art.json). **We do not claim
that nobody has trained a diffusion model on forward biological simulator data.**
Building that is replication, and replication is a fine thing to say we are doing.

What this section adds that is not in that prior art is narrower and more boring: a
frozen protocol that precedes its outputs, an engine whose actuation law is checked
against a closed form at ratio 1.0000 with mutants that fail for the right reason, a
preregistered expectation that was recorded as missed rather than adjusted, a
refinement failure diagnosed down to a confound in our own encoding, and per-claim read
levels so that nine unread papers are visible as unread. Those are provenance and
validation properties, not a modelling advance, and they should be described that way.

Likewise, inverse control of a deformable mechanism is a solved and patented capability
in SoftRobots.Inverse. Inverse *design* of a body from a goal is a different problem,
and nothing in this section addresses it.
