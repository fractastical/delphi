# Two bounded airborne ecology experiments

Canonical data: `run-refined/`; movies/posters: `render-refined/`; viewer contract:
`interface.json` and `geometry-manifest.json`. These are computed engineering
scenarios, not measured flying-fish performance or a biologically calibrated
nervous system. Both scenarios start airborne; no swimming, taxiing, takeoff or
water-entry dynamics are invented.

## Physics and provenance

MuJoCo **3.17.0** integrates one free torso and four finite-mass fin hinges per
fish. The original v3a biological geometry supplies fin areas, area-weighted
centers, lever arms, body dimensions and visualization. Its per-fin computed VLM
polar at0/4/8° is reused by exact candidate/panel/result hashes. Positive CL is
interpolated within that domain; negative symmetry is assumed. Out-of-domain
states stop integration and have null force predictions, never extrapolation.

For each fin, with point velocity v and projected unit normal n_perp:

`L = rho |v|² S CL(alpha) n_perp /2`

`D = -rho |v|² S [CD0 + CL²/(pi e AR)] vhat /2`

`moment = r × (L+D)`; MuJoCo applies these forces at the actual panel centroid.
Lift is perpendicular to point velocity and drag dissipates energy. The declared
air density is1.204kg/m³; CD0=.04 and e=.8 are assumptions. There is no prescribed
air-thrust force. Initial kinetic energy comes from the assumed20m/s release.

The solver integrates `M(q) vdot+c = tau+Jᵀf`, as documented in the
[official general framework](https://mujoco.readthedocs.io/en/stable/computation/index.html#general-framework).
The [fluid documentation](https://mujoco.readthedocs.io/en/stable/computation/fluid.html)
describes phenomenological alternatives, not CFD; those built-in fluid forces
are disabled here to avoid double counting external forces. Fin servos use a
bounded PD torque with finite spring/damping, rate-limited commands, torque and
positive-power caps and a positive mechanical-work budget. Mechanical work is not
metabolic energy or an identified muscle model.

The0.05kg mass, torso CG reference at0.4 standard length, ellipsoid-envelope
inertia, fin mass fractions, hinge stiffness and controller gains are scenario
assumptions. They are **not resin mass** or measurements of this geometry.
Biological component STL coordinates are already **metres**; `bbox_mm` is metadata
in a different unit. The separate manifest records the corrected rigid transform
and articulated-system COM is saved independently of the torso reference.

## Actual paired results

| Experiment | Computed behavior | Numerical scope |
| --- | --- | --- |
| Passive release | Water-stop at1.064875s; torso x20.4979m, height0.04983m; actuator work0J. | dt-halving max position0.248mm, orientation0.0000195rad. No water phase follows. |
| Fin feedback | Reaches1.2s; torso x23.0084m, height1.7616m; positive actuator work0.0001869J. | dt-halving max position4.174mm, orientation0.000565rad; deterministic position replay exact. This does not compare both candidates at equal landing time. |
| Eight-fish local social cue | Seven response flags by0.6s, eight by0.62s. Assigned delay and observed nearby bank motion drive finite fin torques. | Paired no-neighbor ablation has one response flag; identical physics/initial state/seed. dt-halving max position1.518mm versus1.602mm for ablation. |

School episodes stop around0.851s when a fin exceeds the reused ±8° VLM domain;
they do not complete the1.2s horizon. The response-count difference tests our
encoded interaction hypothesis, not a measured survival advantage. There are no
fish–fish contact or wake forces; saved center distances cannot prove collision
clearance. Color denotes a software response flag, not measured pigmentation.

All four refined cases pass the **unchanged**0.01m/0.03rad discrepancy bounds at
common actual saved times and all torque, sampled power, command/actual-rate and
work-budget gates. Maximum quaternion norm error is about1.1e-15. Analytic controls
include gravity-only ballistic motion, drag-energy decrease, orthogonal lift,
right-handed frames, world-force/body-torque mapping and a rejected reversed-drag
mutation. These checks establish numerical/model consistency, not empirical
accuracy.

Feedback mechanical energy falls from11.96207 to9.85014J; integrated fluid work
is−2.11188J, damping loss0.0000240J, signed actuator work is retained, and the
discrete energy-balance residual is−0.0001758J. The residual is reported, not
silently normalized away. School energy balances and all force/actuator peaks
are in `run-refined/summary.json`.

## Neural/ecological applicability and missing bridges

[Park and Choi2010](https://doi.org/10.1242/jeb.046052) measured static forces and
moments on flying-fish models; this experiment did not fit its coefficients to
those measurements. [Herbert-Read et al.2015](https://doi.org/10.1098/rsos.140355)
reports swimming-school escape waves. [Yu et al.2026](https://pubmed.ncbi.nlm.nih.gov/42778611/),
abstract read, reports visual social escape and neuronal responses in Danionella.
Neither supplies this airborne flying-fish controller's radius, bank threshold,
delay, gain or energetic parameters. Species, modality and airborne transfer
remain unknown. A threshold/delay/PD loop is not an implemented biological neural
circuit.

Regulatory DNA→cell state→neural response, tissue/ECM→hinge stiffness, and
muscle activation→torque/metabolic cost are open ports in `interface.json`.
Existing molecular/fin-beam results do not silently fill them. The actual
implemented loop is geometry/polar→forces→rigid-body motion→local sensing→bounded
fin actuation. No whole-organism genetic feasibility is asserted.

## Failures, checks and runtime

The original protocol/run and all failures remain available. A serialization
failure preceded production. Original0.0005/0.00025s feedback discrepancy was
**0.445m**, failing the frozen bound. A separately committed protocol reduced
steps to0.000125/0.0000625s without changing physical parameters or acceptance
limits. An initial body-render unit error and an original receipt-finalization
path error are separately preserved; no trajectory was edited to repair them.

Refined receipt:405.745s wall,276.713s process CPU,555,892KiB process-reported
maximum RSS; Python3.13.12/NumPy2.5.4, CPU MuJoCo. Local trees were bounded under
systemd; concurrent render/numeric jobs each had1 CPU/2GiB/64tasks, totaling at
most2CPU/4GiB/128tasks. Dollar cost remains unknown/null. Three focused tests and
Ruff passed;26 simulation-output hashes and all numerical/actuator gates were
checked independently from the saved receipt. Simulation and render provenance
are separate; movies select actual saved states and label terminal holds.

The separately frozen uncertainty protocol proposes seven axial settings,
two seeds and paired neighbor ablations, with a fixed0.6s endpoint, no interaction
estimate and no biological probability. Cloud dispatch/results are separate
evidence; a proposed packet is not a completed batch.

## Returned axial uncertainty batch (initial partial)

The actual Ubuntu24.04/Python3.12.3/MuJoCo3.17.0 CPU batch completed26 of28
declared scenarios (52 main/half-step simulations). The final two hinge-stiff
seed20261101 neighbor/ablation arms were never started at the original soft
deadline. They remain missing in the initial heatmap; a separately frozen
missing-only continuation does not replace this partial receipt.

All167 returned file hashes (15,535,827bytes), all52 trajectory/context hashes,
4,548 saved frames, and234 endpoint/discrepancy metrics were checked. The metrics
reproduced exactly. Reevaluating force, torque and mechanical energy at528
selected saved poses gave zero difference using the same model; this is a
saved-state integrity check, not an independent physical solver or experiment.
All26 original dt-halving bounds and130 actuator bounds passed. Every computed
scenario supplies the declared0.6s endpoint, then later stops at the reused
VLM angle-domain boundary near0.85s.

At0.6s the encoded neighbor cue produces7/8 response flags for the two baseline
seeds versus1/1 without neighbors. Fast assigned reaction delays produce8/8;
slow delays4/5. The paired figure also shows the actual actuator-work and lateral
displacement costs, without collapsing them into a fitness score. These are
conditional software responses under assumed engineering parameter envelopes,
not measured nervous-system parameters or survival probabilities. Two seeds
share geometry, model and source assumptions; the seven axial settings do not
estimate interactions. Center separation is sampled over the whole episode,
not continuous mesh clearance.

The native batch wall time is979.988s. Dollar cost and aggregate CPU utilization
are unknown. Raw scientific outputs and exact-byte manifests are retained under
`uncertainty-initial/raw-science/`; the original outer collection manifest is
retained separately.
