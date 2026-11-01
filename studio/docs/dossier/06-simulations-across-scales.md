# Simulations across scales, and the layer that refuses to connect them

Live page: https://frontier.morphoswarm.ai/#/simulations

## 31 recorded runs across 9 of 11 scales

Every run has a manifest: its model, its scope, its numerical checks, its inputs with
hashes, and a verified video or figure. Each is labelled **simulated, not observed**.

| Scale | Runs | Examples |
|---|---|---|
| molecular | 4 | molecular dynamics (CPU and CUDA, plus a continuation), OpenFold2 structure for KCNJ13 |
| subcellular | 1 | genome-scale metabolic model |
| cellular | 10 | Delta-Notch replay from published SBML, bioelectric cells, motor-clutch mechanobiology, BETSE tissue and a K-sensitivity arm, Morpheus multicell |
| tissue | 12 | reaction-diffusion fields, fin-ray bilaminar mechanics, ERK wave, Morpheus full-horizon, epithelial closes-vs-arrests **with a control arm** |
| developmental | 4 | neural cellular automata: pattern, seed placement, curriculum; scale ERK wave |
| organ | 7 | fin mechanics, 2D wind tunnel, aeroelastic coupling and a fidelity arm |
| neural | 1 | central pattern generator for behaviour |
| organism | 10 | fixed-launch glide, 3D GPU CFD at L128 and L192 (Re 1000), fish3d render, voxelyze travelling wave, observed allometry |
| collective, macromolecular | 0 | **empty — published as gaps** |

Two scales have no simulation at all, and the studio page says so rather than borrowing a
neighbouring result.

## The coupling layer

Each model declares a typed interface (`frontier.model.interface/1`): named ports with a
quantity, unit, dimension, **scale**, **context** (organism or design envelope), regime,
provenance status (measured / fitted / assumed / simulated / unknown) and bounds. A
proposed connection gets one of three verdicts:

| Verdict | Meaning | May it run? |
|---|---|---|
| `composable` | Typed identity, exact unit conversion, or a registered calibration; dimension, scope, time and uncertainty all pass | yes |
| `scenario` | Runnable only under named assumptions, with unknown bounds, time scale or uncertainty | yes, labelled; never evidence about an organism |
| `refused` | A bridge is missing or inconsistent | **no** |

**Current manifest: 4 composable, 5 scenario, 4 refused.**

The composable ones are deliberately boring — a wing area or a span passed between two
models as the same quantity in the same unit. The interesting ones are the refusals.

### The refusal that matters most

Delta-Notch asymmetry (cellular) feeding fin flexural rigidity (organ) is **refused**, for
stated reasons: no mapping is declared; the scale changes cell to organ; the context
changes from the species annotated in the SBML to the flying-fish design envelope; and the
Delta-Notch model is non-dimensional as stored, so it cannot be identity-mapped to an SI
quantity. An assumption may differ in *regime* only. **An assumption can never stand in
for a transfer across biological scale or context** — that needs a calibration.

A calibration is a structural record: measured or fitted-to-measured, source read at
full-text or data level, a 64-hex data hash, a closed domain, a positive factor with its
dimension, a relative uncertainty, at least two points, and the scale/context it bridges.

**Registered calibrations today: NONE.** That one line is the most important number on the
page, and it is why every cross-scale bridge is refused or assumption-level.

The manifest also carries an explicit `must_not_say` list: *"the models are coupled"*,
*"validated multiscale model"*, *"the fin pattern is explained"*, *"Lean proves the
biological correspondence"*.

## A worked example of a check doing its job

Three printable fin-and-body variants were compared under matched conditions (4 degrees
angle of attack, horseshoe vortex lattice, isolated paired fins). On lattice refinement:

| Variant | Lift-coefficient change | Usable? |
|---|---|---|
| v3a | 0.5% | yes |
| v3c | 2.9% | yes |
| **v3b** | **26%** | **no — not converged** |

v3b's lift is published with a warning and **no feasibility score**, and the cause of its
non-convergence is recorded as undiagnosed rather than guessed. A rank order built on that
number would have been wrong.

## The generative pilot

A diffusion model was trained on an abstract reaction-diffusion pattern problem. The
figures come from arrays returned by a recorded GPU job; the first attempt timed out
before evaluation and the recovery job was an evaluation-only rerun of the frozen
checkpoint, recorded as such. Scope line: no generated replacements, no new simulation,
no biological validation, and range shading is **not** a confidence interval.
