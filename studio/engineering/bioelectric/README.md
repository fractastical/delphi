# Bioelectric membrane and cell-network sandbox

A running, independently implemented Hodgkin–Huxley membrane model (1952,
DOI [10.1113/jphysiol.1952.sp004764](https://pmc.ncbi.nlm.nih.gov/articles/PMC1392413/))
plus a deliberately assumed equal-area electrical cell network. **SimulationResult,
not observation, fin-development model, or biological validation.**

## Delivery checklist

- [x] Read SPEC-005/007 and existing model/coupling contracts before implementation.
- [x] Retrieve and read primary equations, units, temperature and Table 3 values.
- [x] Implement Na activation/inactivation, K activation, leak, membrane capacitance
  and conservative sealed-chain gap currents.
- [x] Bounded, side-effect-free parameter API with voltage/time/channel/current output.
- [x] Analytic membrane and voltage-clamp controls; current conservation; step/grid checks.
- [x] Physical-law sign mutant fails the conservation control; unmutated control passes.
- [x] Baseline, Na reduction, disconnection and no-stimulus scenario exports.
- [x] Automated 7×7 parameter atlas and video rendering from saved state frames.
- [ ] Independently review the implementation and source correspondence.
- [ ] Obtain species/stage-matched data and calibrate a fin-development bridge.

## Model and applicability

For cell i, capacitance times dV_i/dt equals inward applied current, minus outward
Na/K/leak currents, plus the sum of g_gap(V_neighbor−V_i). Na conductance is
120 m³h, K conductance is 36 n⁴, and leak conductance is 0.3 mS/cm². Capacitance
is 1 µF/cm². Reversal potentials are +50, −77, −54.387 mV in the modern
intracellular-minus-extracellular voltage convention. Each gate obeys
dq/dt=α(V)(1−q)−β(V)q using the published rates and Q10=3 at 6.3°C.
These fitted phenomenological channel equations describe source membrane
electrophysiology; they do not resolve molecular channel structure.

The 12 identical-area cells, chain topology and gap conductance are **assumptions**,
not squid measurements. Gap conductance density is an absolute junction
conductance divided by the common cell membrane area; each edge contributes
equal opposite currents, so it conserves charge internally. No external current
crosses the chain ends. No measured cell geometry or length is assigned. An ideal
buffered bath keeps reversal potentials fixed. Ion depletion, pumps, gene regulation,
growth, morphology and ion mass balance are outside this model. The default
stimulus is +12 µA/cm² into cell0 from 5 to 6ms. Every cell begins at −65mV
with gates at the corresponding steady state. Conductance perturbations may
change the resting state; their initial transient is retained rather than hidden.

`sources.json` pins downloaded primary PDF and official NEURON mechanism bytes,
exact page/section locators and the sign conversion. NEURON's mechanism was read
as a rate-law cross-check; NEURON and BETSE were not executed. BETSE's official
workflow was assessed; installing its full multiphysics workflow was deferred.
This implementation is not a BETSE substitute and does not claim electrodiffusion
or source-data reproduction. Published fitted parameters are real source grounding;
no raw voltage traces were digitized or compared in this delivery.

## API

```python
from engineering.bioelectric import simulate
result = simulate({"sodium_scale": 0.35, "gap_mS_cm2": 0.5})
```

Optional schema: `frontier.bioelectric.request/1`. Unsupported fields and
non-finite/out-of-envelope values produce `status=invalid_request`. No files,
network requests or subprocesses are created by `simulate`.

| Parameter | Default | Bounds | Unit / provenance |
| --- | ---: | --- | --- |
| sodium_scale | 1 | 0–1.5 | unitless design change to published maximum |
| potassium_scale | 1 | 0.25–2 | unitless design change to published maximum |
| gap_mS_cm2 | 0.5 | 0–2 | mS/cm²; assumed coupling |
| stimulus_uA_cm2 | 12 | 0–30 | µA/cm²; chosen current pulse |
| temperature_c | 6.3 | 6.3–18 | °C; published Q10 scaling |
| duration_ms | 30 | 10–60 | ms; chosen horizon |
| dt_ms | 0.025 | 0.005–0.025 | ms; chosen maximum integration step |

The envelope is a **resource/experiment bound**, not an empirically validated
parameter range. `voltage_mV[time][cell]` contains actual integration states sampled
at approximately 0.1ms, with exact pulse endpoints; no invented interpolation.
`gates_m_h_n[time][gate][cell]` and `ionic_current_uA_cm2[time][ion][cell]`
(Na,K,leak) retain the mechanism. A completed status means a bounded integration
finished with finite voltages and bounded gates. It is separate from control
receipts and biological validity. Crossings are 0mV crossings of sampled states,
not experimentally detected spikes; first crossing times have sampling resolution.

## Reproduce

Python3.11+, exact tested dependencies in `requirements.txt`, system `ffmpeg` and
`ffprobe`. The tested environment version is recorded in the bundle manifest.
From the repository root:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 systemd-run --user --scope \
  -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
  python -m engineering.bioelectric.run --output artifacts/bioelectric
```

The CLI refuses nested bundle runs. `python -m engineering.bioelectric.controls`
must exit 0; adding `--mutation gap-sign` must exit 1 because one gap-current
endpoint sign is reversed. `mutation_receipt.json` contains actual subprocess
commands and measured exits 0/1/0, including the restored baseline. The test
command is `python -m pytest tests/test_bioelectric.py -q`, under the same scope.

Controls compare the actual membrane-current code against a frozen-gate analytic
exponential, and gate integration against a voltage-clamp exponential. HH step
refinement checks dt=.025,.0125,.00625ms on the default scenario. A separate
smooth passive cable checks the same conservative gap operator against a cosine
Neumann solution on 16/32/64 grid cells; it is a mathematical control, not a
claim that subdividing a real cell preserves biology. The **entire atlas has not
received per-cell convergence controls**. No biological validation is implied.

## Artifacts and rendering

`artifacts/bioelectric/manifest.json` pins source/input/output hashes, runtime,
environment and scenarios. `baseline.json`, `sodium_reduced.json`,
`disconnected.json`, `no_stimulus.json` carry simulationActions. `atlas.json`
maps its 49 heatmap entries to hashed per-run voltage/time artifacts. K scale=1;
the axes vary Na maximal conductance and assumed gap coupling. These are distinct
integrations even when the displayed crossing count is equal.

`python -m engineering.bioelectric.render --output artifacts/bioelectric` reads
those saved results to produce `bioelectric.mp4` and `poster.png`; it does not
integrate. Its renderAction records input artifact hashes and the selected actual
frame indices. Cell positions in the movie are index glyphs, not specimen geometry.
The movie slows 30ms of model time into 7.5s for inspection. `atlas.png` is a
simulation response heatmap, not a biological phenotype map.

The source and run hashes establish artifact identity. Independent source-code
review, experimentally measured fin-cell voltage/channel/coupling data and a
causally tested voltage→tissue-pattern→fin-geometry map remain open work.
