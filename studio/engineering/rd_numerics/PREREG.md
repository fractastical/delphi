# Training-only RD discretization audit

Frozen before audit endpoints. This experiment does not train, load a network,
read held-out samples, or modify the frozen DDPM solver/configuration.

Question: how much do saved Schnakenberg fields, amplitudes and dominant modes
change under paired time and space refinement for the FIRST16 training settings
(ids0..15), each with training IC seed indices0,1,2? Actual IC seed=id*1000+index.
The exact frozen source is engineering/rd_diffusion/rd_ddpm.py at4a5394f;
config parameters/settings RNG/20-mode continuous cosine IC construction are reused.
All variables and time are model units; no fish calibration.

Design: five configurations in fixed order N64/dt.02, N64/.01, N64/.005,
N128/.005, N256/.005, float64, saves tau50,100,150,200. This separates a time
refinement axis atN64 from a grid refinement axis atdt.005; it does not estimate
space×time interaction or prove the finest result exact. Same continuous modal
coefficients are sampled on each cell-centred grid. Strang exact diffusion +RK4
reaction and homogeneous Neumann boundaries remain the source equations/method.
The original advance function is called with EXPLICIT dt; module-default mutation
is prohibited. Saved fields are retained at native resolution, without replacing
failed fields with zeros. Failure masks at each saved snapshot separately report
nonfinite, absolute value>1000, and negative values. Intermediate-state checks
are not performed and not claimed.

Comparisons: consecutive time refinements, consecutive grid refinements, and
original N64/.02 versus finest N256/.005 (the last conflates both changes).
Compare exact DCT cosine coefficients normalized bysqrt(N); project the first64
modes to the common64-point grid analytically, without spatial interpolation.
Report each channel's common-grid RMS absolute discrepancy, relativeL2 with
1e-12 denominator floor, native mean/amplitude differences, u dominant-mode
indices and changes, and finer-grid power fraction above the common-mode cutoff.
No high-resolution reference is assumed exact. Aggregate only finite paired
fields; report every omitted failed pair and exact denominators. No biological
or numerical-convergence PASS criterion is invented; this is a descriptive audit.

Controls before GPU endpoints: orthonormal DCT/cosine projection identity,
analytic single-cosine heat diffusion with error<1e-11 and wrong diffusion-sign
mutation rejected; source-wrapper short CPU equality<1e-11; same tiny actual
CPU/CUDA solver discrepancy<1e-9 with float64 and TF32 disabled. These are
software/platform controls, not whole-prior accuracy guarantees. Require CUDA,
never silently fall back toCPU.

Budget: oneH100, hard900seconds workload. Every completed configuration is saved
and hashed before the next starts; a timeout/absent configuration stays incomplete.
No runtime claim until measured. Expected48trajectories/config,4saved times,
240native-resolution trajectories total if complete. Full fields, masks,
parameters/seeds, environment/control/code/config/protocol hashes, perconfig wall
time, pairwise rows and final complete/incomplete receipt must be recoverable.
No held-out results may inform this code, protocol, thresholds or model tuning.
