# Bending-only, torsion-rigid scaffold: checked model comparison

All36 declared static arms returned; no failed, unconverged or model-domain-exit arms. The18 frozen absolute-CL lattice comparisons and all72 separate descent dt checks pass. This means agreement within the declared bounds, not a convergence rate, biological validity or validated fin/glide performance. Both16×4 and24×6 meshes are coarser than the48×16 reference used to define assumed EI. The original8×2 control slice remains separately available.

Independent saved-state audit checked161 returned files/18,268,194bytes,36 exact identities,222staticframes and72,544actual RK4states. Recomputed geometry, beam-validity metrics, ledgers,CL,descent energies/powers and36 final-pose VLMforce samples match EXACTLY. This is same-model reproduction, not independent biological evidence. Native compute41.243s on4CPU;Python3.12.3/NumPy2.5.4/SciPy1.17.1. Dollar costunknown.

## Paired differences: descriptive posthoc diagnostics

At declaredcompliance0.2,20m/s,alpha4°, the24×6 model gives rigidCL0.25036032, frozenloadCL0.24901258 and feedbackCL0.24901642. The separate assumed-release descent ranges are29.16950m,29.04643m and29.04678m.

| Difference |16×4 ΔCL|24×6 ΔCL|main/fine ratio|16×4 Δrange|24×6 Δrange|
|---|---:|---:|---:|---:|---:|
|one-way minus rigid|−0.00134033|−0.00134774|0.99450|−0.122901m|−0.123068m|
|two-way minus one-way|+0.000003804|+0.000003840|0.99067|+0.3474mm|+0.3492mm|

The nominal feedback increment is negligible at this compliance: only about3.8× the declared1e-6CL iteration tolerance. The frozen3% absolute mesh gate cannot establish these smaller paired effects. Both-mesh signed deltas, ratios and tolerance multiples for ALL contexts are retained in `production-diagnostics.json`; the plot is explicitly posthoc descriptive and introduces no acceptance criterion. Two meshes do not establish a convergence rate or continuum accuracy.

The three-point absolute deformation-effect versus compliance descriptors are≈1.03–1.04, rather than quadratic. The independent review suggested a second-order dihedral mechanism. The actual source fins already have7° pectoral/4° pelvic dihedral; increments around nonzero dihedral can have a linear term. This is an untested explanation for the observed descriptor, not a new material law or a zero-dihedral ablation. The review and this disagreement remain available.

## What the checks establish

As claude-07's independent review notes, normal forces are pointwise at their own span stations: force,firstmoment andvirtualwork are conserved BYCONSTRUCTION. Production ledger residuals are bookkeeping identities, not independent transfer validation. The omitted-normal-entry mutation detects that override only; it does not test wrong station/frame/scaling. The algebraic lift-orthogonality check is also weak. These are NOT additional independent proofs among the20 recorded booleans. Meaningful controls include independent cantilever quadrature, FE1/2/4 roundoff exactness (not a rate), zero/stiff limits, degeneracy/refusal, ballistic and drag-energy behavior, and the original VLM analytic/refinement/mutation controls. No frozen source, protocol or acceptance gate was changed after review.

## Mechanical and biological scope

The equivalent fin scaffold bends but is torsionally rigid. At nominal fine feedback conditions, constraint torsion is≈29% of root bending moment in pectorals and≈48% in pelvics. These substantial reactions do not produce finite twist; the model cannot establish that total fin aeroelastic effects are small. All per-fin constraint torsion/axial fractions are saved. No ecologyhingeK or molecular/ECM modulus is substituted for EI. No anatomical ray network, finite torsional stiffness, membrane stretching law or tissue calibration is supplied.

The point-mass calculation is an under-lifted, fixed-alpha assumed-release DESCENT, not a trimmed/glide-performance validation. Nominal L/W is0.647 at20m/s and0.415 at16m/s. The16m/s frozen shape sees actual saved dynamic pressure grow≈16.9% before contact, while it remains rigidized; at20m/s growth is≈0.24%. There is no continuous FSI, pitch-moment balance, fin inertia/self-weight or actuator/metabolic calibration. Changes in projected span enter an assumedCD0/e drag polar, not VLM viscous drag. Mass0.05kg, releaseheight4m and drag parameters are engineering assumptions, not resin mass or specimen measurements.

The aerodynamic solver is inviscid attached-flow thin-surface VLM with fixed straight horseshoe trailing legs; no body,separation or free/unsteady wake dynamics. The largest sampled tip/span is0.09896, close to the frozen0.1 boundary; that is a model-domain margin, not a biological feasibility margin.

The production movie shows the actual nominal24×6 static iterations, unscaled geometry and separately integrated fixed-alpha descent paths. It assigns no physicalseconds to static iterations; all interpolated event endpoints remain scalar results rather than physics frames.

Method context: [NASA Ting/Nguyen/Trinh2014](https://ntrs.nasa.gov/api/citations/20140008648/downloads/20140008648.pdf),HermiteEq63–66,staticEq74–75 andSectionVIII; [MIT1.050beamnotes](https://ocw.mit.edu/courses/1-050-solid-mechanics-fall-2004/f9a4d5764b9b0f51ffaacbdf69f7aed8_emech10_04.pdf),p268cantilever table. We implement a bounded bending-only/scalar-flight subset and do not inherit those aircraft validations.
