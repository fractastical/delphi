# Multiscale simulation: executable evidence and next 24 hours

The first new atomistic result is an **actual OpenMM simulation of the experimental
1K6F collagen-mimetic triple helix**. Its CPU numerical controls passed; its short
CPU trajectory and movie exist. The three-seed CUDA job has been submitted by the
infra owner, not yet returned at this checkpoint. Execution state and biological
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
|1 OpenMM1K6F MD | Synthetic collagen-mimetic structure, ff14SB/TIP3P, explicit assumptions | Atom positionsnm, Cα RMSDnm, chain distancesnm; no fibril/tissue law | CPU control complete;1 H100 job submitted; setup done |
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
|Now: does the actual molecular system run consistently onCUDA? | Frozen1K6F packet; same generated System/State onCPU andCUDA;3seeds | Frozen CPU gradient/sign/NVE checks; forceL2 relative<0.002 and energy error/atom<0.01kJ/mol before production |100 ps/seed coordinates, RMSD/end distances/temperature traces; inputXML,NPZ,JSON,MP4;1 H100,1500 s workload cap,16 MB output parts; infra job receipt controls truth |
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
