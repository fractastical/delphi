# Geometry-linked 2D low-Re wind tunnel

This runs actual fluid flow around the sagittal projection of an existing fish
candidate STL. It is an infinite-span 2D extrusion of a **print-modified candidate**,
not a specimen, full3D fish, flight polar, flexible fin or genetic mechanism.

- [x] Inspect and salvage NCA's existing mask/bounce-back solver and original controls.
- [x] Compare GPUops periodic spectral Protocol5; retain its distinct no-body scope.
- [x] Freeze geometry, physical bounds and numerical checks before fish-flow runs.
- [x] Rerun original channel/Taylor-Green/mass controls and no-body control on CPU.
- [x] Generate actual STL-derived masks with source and raster hashes.
- [x] Run paired body-grid/time checks and preserve the grid runtime failure.
- [x] Inspect velocity/pressure/force video and publish exact byte receipts.
- [ ] Establish 3D, flight-Re, moving-wall, flexible-fin or measured-polar accuracy.

## Physics and source

The reused `engineering/flow/lbm.py` from work/nca-flow37a7559 is a D2Q9 BGK
lattice-Boltzmann implementation. Its original source hashes are in protocol.json.
The only changes to the copied solver/control bodies are whitespace formatting and
an unused import removal; an AST comparison against the original source was run.
Original CPU controls passed before those cosmetic changes. This establishes
numerical behavior in named analytic cases, not physical validation of fish flow.

Macroscopic target equations, in the low-Mach limit:
`div(u)=0`, `du/dt+(u·grad)u=-grad(p)/rho+nu laplacian(u)`.
The actual discrete update is BGK collision plus streaming with
`f_eq=w_i rho [1+3 c_i·u+4.5(c_i·u)^2-1.5|u|²]`;
`nu_lattice=(tau-.5)/3`, `p_lattice=rho_lattice/3`.
Rigid halfway bounce-back sets incoming fluid populations from opposite outgoing
ones; summing reflected boundary-link momentum yields drag/lift on the body.

Primary method source read: Ladd, *Numerical Simulations of Particulate Suspensions
via a Discretized Boltzmann Equation, PartI*,
[arXiv:comp-gas/9306004](https://arxiv.org/pdf/comp-gas/9306004), SectionII Eq2.35
(macroscopic NS limit), SectionIII Eq3.12 and its following boundary-force sum.
PDF text and pages12/19 were inspected. It uses a different discrete-velocity model;
it does not validate this implementation or geometry. Zou/He
[comp-gas/9611001](https://arxiv.org/abs/comp-gas/9611001) abstract was read for
halfway-boundary context; this engine's simple equilibrium outer boundary is
explicitly **not** an implementation of the paper's pressure/velocity reconstruction.
Qian1992 D2Q9 and Guo2002 forcing references in the older protocol were not reread;
no body-force forcing is used for fish runs. Guo forcing is exercised by the channel control.

Left/top/bottom boundaries reset to uniform equilibrium; right outflow copies the
neighboring population. The domain is12×6 reference body lengths, with body center
(3.5,3). No wall-distance convergence is claimed. Initial uniform flow starts
impulsively around a static no-slip mask; transients are retained and stationarity
is checked separately. Low-Re and weak-compressibility assumptions remain visible.

## Geometry, units and knobs

Supported mesh IDs: N1-cypselurus-baseline, N2-area-x1.3, N3-area-x1.3-ar-x1.2.
Binary STL triangles are projected onto x-z and union-rasterized at lattice cell
centers. Source x runs snout-to-tail; positive AoA puts the snout up. The reference
length is the total unpitched STL x extent, rescaled to the declared body_length_m,
not a measured standard length. thickness_scale rescales the sagittal height.
Print-thickened fins and rounded features remain in the source shape. A mask may
fail to resolve features; no dilation or fabricated reconstruction repairs them.

`request_parameters` bounds speed.002–.02m/s, reference length.08–.25m,
thickness.6–1.5, AoA±15degrees, viscosity1e-5–1e-3m²/s and Reynolds10–120.
The limits are coupled: an otherwise in-range request is refused if Re is outside
the domain. These deliberately slow low-Re flows **cannot be used as flight
Reynolds numbers**. Density/viscosity and all body rescalings are declared inputs.

Physical mapping: `dx=L/length_cells`, `dt=U_lattice*dx/U_physical`,
`Re=U_physical*L/nu_physical`. Force per unit infinite span is
`F'=0.5*rho_physical*U_physical²*L*C`, in N/m. Pressure above freestream is
`rho_physical*(U_physical/U_lattice)²*(rho_lattice-1)/3`. It is not a measured
pressure or total force on a finite-span fish.

## Execution and provenance

`run_request(request,outdir,device='cpu',analytic_receipt=...)` is a trusted bounded
runner; physical request keys cannot inject paths, commands, credentials or masks.
The server/operator supplies the passing frozen analytic receipt. Stability checks
stop a configuration for nonfinite state, Mach>.3 or density deviation>.1.
No video is emitted for that failing configuration. Grid/time/flux failures remain
PARTIAL. Force observations use matched physical times in refinement partners,
following the equal-end-time lesson from GPUops Protocol5.

```
python -m engineering.windtunnel.run --analytic-controls CONTROLS.json --output artifacts/windtunnel
python -m engineering.windtunnel.render artifacts/windtunnel
```

Use the bounded4G/no-swap/TasksMax128/RuntimeMaxSec600 systemd scope and at most2
threads. `fields.npz` contains actual sampled central-ROI nodes exported float32
from float64 states, with full-field hashes at each snapshot. No spatial or temporal
interpolation fabricates data. Rendering may repeat saved states for playback and
labels color saturation. Simulation and render manifests are separate.

Proposed pitch/heave ports are recorded, but only static pitch is implemented.
A neural/CPG controller cannot yet drive moving fluid boundaries or infer force
calibration. Moving-wall bounce-back and oscillating-body controls are prerequisites.
Reported Mach is the lattice/artificial-compressibility Mach, not a calibrated
real-gas acoustic Mach number.

## Recorded first slice

Original analytic suite passed in163.3s on CPU. Baseline24-cell/body run completed
in30.3s, Re80, positive final-window Cd≈.632, max Mach≈.110 and flux imbalance≈.138%.
Physical values remain low-Re proxy calculations, not fish measurements.
The48-cell CPU run hit the immutable500s cap at an incomplete end time; its result
stays FAIL and grid accuracy UNKNOWN. Its near-end coefficient is **not** substituted
for the missing equal-time grid check. No video is made from that failed case.
The successful baseline video displays the failed suite/refinement status.

Independent24-cell time partners completed at exactly tU/L=2, including matched
force observation times: final-window Cd difference.352%, inside the frozen10%
criterion. Source-style formatting changes were checked against the original AST;
an actual force-sign mutant is tested and cannot be rendered as a successful run.
The portable CUDA protocol proposes a same-grid CPU/CUDA repeat, completion of48
at tU/L=4, and96 through tU/L=8 (its midpoint reuses tU/L=4 for grid comparison).
It does not revise the CPU FAIL or imply that a GPU has run. GPUops alone dispatches.
