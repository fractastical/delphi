# Force-feedback motor clutches on a relaxing ECM contact

This executes molecular-clutch and cell-edge mechanics using Gong et al. (2018),
PNAS, [doi:10.1073/pnas.1716620115](https://www.pnas.org/doi/10.1073/pnas.1716620115),
coauthored by Vivek B. Shenoy. The lab homepage was read via Jina; the full article
was read from PMC HTML after browser and Jina CAPTCHA failures. Retrieval receipts
and exact byte hashes are in `sources.json`. Supplementary PDFs remained challenge
HTML. This is an implementation of the stated slip-bond equations, not the authors'
software, a quantitative reproduction, or calibrated fish biology.

- [x] Read source equations and existing fin-beam/coupling code.
- [x] Implement dynamic force–velocity and force–rupture feedback.
- [x] Bound requests and expose actual trajectory states.
- [x] Run independent elastic analytic, null, equilibrium and force-law controls.
- [x] Screen timestep sensitivity of default ensemble mean traction.
- [ ] Validate all sweep cells numerically and fit measured cell-specific data.
- [ ] Establish a cell–tissue–fin developmental bridge.

## Equations and implementation

Source Model Description Eqs.1–6: a clutch binds with constant rate `r_on`, breaks
with `r_off0 exp(F_i/F_b)`, and carries `F_i=kc(x_i-xs)` when bound. Net traction
slows actin according to `v=vu(1-F/(Nm Fm))`. The contact obeys the source SLS
constitutive relation. Its equivalent internal coordinate is
`F=kl xs+ka(xs-z)`, `z'=ka(xs-z)/eta`.

Force balance eliminates `xs` at each topology change. Between events the coupled
actin/Maxwell equations are linear; `scipy.linalg.expm` advances them exactly.
Seeded Bernoulli frozen-rate binding/rupture steps use `1-exp(-rate dt)` and split
from mechanics at first order. New clutches start at zero extension. An unbound
clutch carries zero force. Compressive forces use the unloaded rupture rate,
an explicit assumption outside the tensile Bell law. Reported equilibrium residuals
check force balance, not biological validity. High event probabilities warn that
a setting may need a smaller timestep; uniform convergence has not been established.

Internal units are pN, nm and s (`1 pN/nm = 1e-3 N/m`). Contact stiffness cannot
be converted into a tissue modulus without a geometry model. The source Fig.1C/D
example supplies `ka=1`, `kl=.1` pN/nm and `eta=1` pN s/nm. Other cell parameters
are operator assumptions because supplementary TableS1 was not retrieved. The
displayed spreading proxy assumes polymerization speed equals unloaded flow and
is not cell area, migration distance, or fin growth. Reinforcement is omitted.

## Interactive contract

`from engineering.mechanobio import run_request; result=run_request({})`

Request schema `frontier.mechanobio.request/1`; optional `parameters` use names,
units and hard bounds in `model.LIMITS`. `duration_s` 1–60, `dt_s` .001–.02,
`seed` unsigned32bit, `frame_count` 2–301. Invalid/unknown inputs raise ValueError.
Example request is `example_request.json`; it uses fewer clutches to display
load-and-rupture cycles clearly. This is declared scenario selection, not fitting.

Result schema `frontier.mechanobio.result/1`, status/evidence kind `simulated`,
contains `request_echo`, per-parameter provenance, `model`, `frames`, `summary`,
`not_established`, open measurement questions, and input/code/environment/trajectory
hashes. Every frame exposes time, traction, substrate and actin displacement,
Maxwell coordinate, attached count, retrograde velocity and per-clutch forces.
Results remain simulations when plotted or embedded in a project.

## Replay

Dependencies: Python >=3.11, numpy2.4.4, scipy1.17.1. Rendering additionally needs
matplotlib (recorded exact version in rendering receipt) and ffmpeg with libx264.
Run process-spawning commands inside a systemd scope with TasksMax128, MemoryMax4G,
MemorySwapMax0 and RuntimeMaxSec600; limit BLAS/OpenMP threads to2.

```
python -m pytest tests/test_mechanobio.py -q
python -m engineering.mechanobio.sweep --output artifacts/mechanobio --grid 5 --replicates 12
python -m engineering.mechanobio.demo artifacts/mechanobio
python -m engineering.mechanobio.render artifacts/mechanobio
```

Sweep protocol fixes the grid, default parameters and seeds before execution.
Each cell retains individual replicate summaries, variance, normal Monte Carlo
mean intervals and a paired constant-rupture intervention. These intervals quantify
simulation sampling, not biological or parameter uncertainty. Simulation and render
manifests are separate. Video bars are actual computed spring forces; curves are
saved computed states. ArtifactRef-compatible content-addressed pointers establish
byte identity; availability is `referenced` until a serving layer supplies downloads.
