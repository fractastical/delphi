# Reduced CPG and mechanical feedback controller

This slice executes eight amplitude-controlled phase oscillators driving eight
independent inertial/damped/elastic joint proxies. It is a source-form engineering
controller with a zebrafish locomotor context, **not a zebrafish neural-circuit
reproduction, observed swimming, whole brain or genotype-to-behavior model**.

The oscillator form comes from Ijspeert et al.2007
([DOI10.1126/science.1138353](https://doi.org/10.1126/science.1138353)), p1416;
its Fig1 describes oscillator setpoints and mechanical PD feedback. That study
concerns salamanders and a robot. Roussel et al.2021
([DOI10.7554/eLife.67453](https://elifesciences.org/articles/67453)) provides
primary zebrafish computational context: rostrocaudal alternating swimming
patterns and a simplified damped angle model. Its neural cells, synapses,
muscle voltages, published figures and datasets are not reproduced here.
The source's discussed20–65Hz swimming context motivates a chosen35Hz scenario;
it does not calibrate this oscillator's parameters or make it a zebrafish CPG.

`engineering/behavior/sources.json` pins retrieved primary-source bytes and exact
sections. Roussel's public dataset DOI10.20383/102.0498 was discovered but not
replayed. A separate PMC page challenged the direct browser fetch; command-line
Jina retrieved it, but its model was not used. The Masino2005 publisher returned
403 and Jina returned its Cloudflare challenge, so no measured parameter was
adopted from that unread paper.

The normalized oscillator amplitude follows the published critically damped
second-order law. A directed phase-coupled chain converges toward a chosen lag.
Right/left outputs are imposed in exact anti-phase; this is an assumption, not a
demonstration of biological reciprocal inhibition. Their difference defines an
angle setpoint. A bounded actuator applies nominal inverse dynamics plus PD
feedback. Inertia, damping, stiffness, gain, torque and geometry are all designed
assumptions with units, listed in `interface.json`. The mechanical equations are
dimensionally consistent; no biological tissue force calibration is claimed.

The acceptance protocol was committed and pushed before any comparison output,
at `6d1a507`. Baseline35Hz, changed25Hz, feedback removal, phase-coupling removal
and a sign-reversed feedback law all share the same phase kick and torque pulse.
The frozen criteria test controller tracking, phase-wave recovery, discriminating
negative controls, time-step refinement and a closed-form amplitude solution.
The wrong-sign controller must fail the baseline tracking predicate. An extra
direct test checks passive mechanical energy dissipation. No endpoint scores
swimming speed, thrust, energy economy or biological success.

To replay, from the repo root with NumPy2.4.4, Matplotlib3.10.8 and system ffmpeg:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 systemd-run --user --scope \
  -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
  python -m engineering.behavior.run --output artifacts/behavior
```

Run `python -m pytest tests/test_behavior_control.py -q` under the same scope.
The output bundle records actual state/time arrays, input/code hashes, protocol
identity, controls and separate simulation/render receipts. Its MP4 shows selected
saved states in a0.65–1.45s model-time window, slowed for inspection. The pictured
hinge chain has normalized unit length and no translation; it is a kinematic
glyph, not a measured fish body or fluid simulation. A movie is not a new
simulation and does not improve the model's empirical validity.

The interface exports phase (rad), frequency (Hz), angle (rad), angular velocity
(rad/s) and actuator torque (N*m). The current wind tunnel supports rigid static
angles only. Its ±0.262rad angle domain is retained as a **proposed interface
bound**, not a dynamic coupling or anatomical fit. The no-feedback and wrong-sign
negative controls can leave this envelope; those excursions stay flagged and
are not evidence of physically valid fish configurations. Frequency-dependent
fluid forces need a moving-wall solver and oscillating-body controls first.

`problems.json` records proposed, unpersisted Problems for target-circuit
calibration, neuromuscular transfer, moving-fluid coupling and genotype-to-circuit
causality. Those bridges remain open. No source association is promoted into a
causal gene-to-behavior equation.
