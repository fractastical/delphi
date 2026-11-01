# Shared oxygen rule — source and parameter gaps for project owners

Status: reusable model contract prepared in `work/oxygen-lean`; this note records
the handoff request, not an empirical result. Project proposal identifiers are
the current drafts `project-tissue-microcarrier` and `project-epithelial-repair`.

## Shared conditional rule

The same conditional center-oxygen rule is available in two ideal geometries:

- Sphere: `Ccenter = C0 - a R^2/(6 D)`; `Ccenter >= 0` iff
  `a R^2 <= 6 D C0`.
- One-sided slab: `Ccenter = C0 - a L^2/(2 D)`; `Ccenter >= 0` iff
  `a L^2 <= 2 D C0`. `L` is the no-flux-center-to-supplied-face distance;
  for a symmetric two-sided slab, total thickness is `2 L`.

Both are steady, diffusion-only, constant-consumption model statements. They
screen whether the **model** predicts nonnegative oxygen at its center. They do
not establish cell viability, repair, organism function, or a real tissue's
oxygen state. The slab is a derived one-dimensional analogue, not a Grimes
equation.

## Intended applications (same rule, no parameter transfer)

1. `project-tissue-microcarrier`: a spherical microcarrier is a candidate
   geometry for an oxygen-transport screen. The contract exposes `D`, `a`, and
   boundary `C0` as unknown until a cell/material/context-specific source or
   measurement is attached. Tumour-spheroid fitted values are not inherited.
2. `project-epithelial-repair`: an ideal slab is a candidate thickness screen
   for a repair patch under the explicitly one-sided boundary assumption. The
   rule is independent of gap closure and does not predict barrier recovery.
   Cell type/state, local demand, diffusion, boundary supply, perfusion and the
   relevant repair time are unknown here.

No project parameter values have been supplied. In both projects, exposed
controls are imposed model quantities, not claimed biological interventions.
A future spatial oxygen measurement in the same declared cell/material and
geometry could calibrate or refute the profile; no such measurement is attached
or available through this change.

## Questions for project/source owners

- Is the candidate microcarrier geometry explicitly spherical, or should that
  context remain a generic geometry screen?
- For the repair patch, what is the intended oxygen supply face and cell layer
  geometry? If it is not a slab with one-sided boundary supply, keep the bound
  as a separate counterfactual model rather than relabelling it.
- Please provide exact project version refs and any cell/material-specific
  `D`, consumption `a`, boundary `C0`/partial pressure conversion, stage,
  environment, source location, and measured/fitted/assumed status. Unknowns
  remain null until sourced; no DLD1 tumour parameter is transferred.
- If there is a candidate oxygen readout or physical/virtual instrument, attach
  its exact artifact and limitations. A simulated oxygen profile is not an
  observation.

The machine-readable contract, theorem/control receipt, numerical profile
checks, source pins and plot live under `artifacts/oxygen-diffusion-rule/`.
