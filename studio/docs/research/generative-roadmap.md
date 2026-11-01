# Generative roadmap: mechanistic simulators as training data, conditional generators, solver-gated inverse design

**Status.** One bounded pilot is frozen and awaiting GPU time. The broad organism-scale proposal is
unbuilt. The sections below separate the two, and §6 gives the counts.

Read-levels, per `docs/research/README.md`: `full-text` | `abstract` | `search-summary`. Each
prior-art entry carries its own, and every date below was read from the arXiv abstract page on
2026-10-31 rather than from a search summary.

Companion pages: `#/generative` (the public thesis, live) and `#/about`.

---

## 1. The proposal, in four stages

1. **Forward — synthesise.** Take mechanistic equations and their knob ranges from **sourced claim
   records**, not from memory. Sweep the simulators we already run across those ranges. Each
   synthetic datum carries the version of the claim that licensed its equation and the hash of the
   request that produced it.
2. **Train — conditional generator.** Fit a conditional diffusion model or latent operator on
   those sweeps, conditioned on the knobs and on regime labels.
3. **Inverse — propose.** Condition on a target morphology or behaviour; sample candidate
   parameter sets and fields.
4. **Screen — gate.** Put candidates back through the exact solver, then through real experiments.

Stage 4's second half, real measurement, is what converts any of this from model-consistency
checking into biology. That step is not part of the current pilot.

---

## 2. Where this actually stands

### 2.1 The RD-1D pilot: controls passed under explicit FP32; training started, no checkpoint

A conditional DDPM surrogate for a **1-D Schnakenberg reaction-diffusion field**.

| | |
|---|---|
| Preregistration + solver + model + controller + tests | commit **`9c56a927`**, 2026-10-31 15:32:36 PDT |
| Frozen job packet, hashes, local CPU control receipts | commit **`4a5394f3`**, 2026-10-31 15:33:03 PDT |
| Branch | `work/rd-diffusion` |
| Packet archive sha256 | `76eb4a7b273f71db51d6f8d35481dfe94a36b49414372c919d3387e67d75821c` (11,526 bytes, deterministic tar) |
| **GPU result** | **none yet** |

What is genuinely frozen before any training or held-out evaluation, per `PREREG.md`:

- **Architecture and schedule**, so nothing can be tuned on the holdouts: 1-D U-Net, 1.35 M
  parameters, replicate padding for zero-flux ends; ε-prediction DDPM, T = 200, cosine schedule,
  30,000 steps, EMA 0.999, seed 0. No physics loss and no guidance — conditioning does not
  guarantee the equations hold, so the evaluation **measures** consistency rather than assuming it.
- **Splits by whole setting or whole seed**, tested so no `(setting, seed)` pair appears in two
  splits, with a `test_param` set of 300 settings never trained on and a `test_seed` set of unseen
  initial conditions on training settings. Normalisation is fitted on training rows only.
- **A shuffled-condition null** among the baselines, alongside nearest-setting, nearest-5 and a
  deterministic conditional-mean baseline. A run in which the DDPM loses to a baseline or to the
  null is reported as such.
- **Data generated inside the job by the frozen solver.** No digitised or fabricated fields.
  Non-finite or diverging runs are flagged `failed`, excluded from training and **counted in the
  receipts**.
- **An explicit non-claims list**: no biological validity, no fin or fish model, no calibrated
  units, no equation satisfaction by the surrogate, no generality beyond the 1-D Schnakenberg
  prior box, and no speed advantage.

Controls that have run: the CPU control passes all checks; the torch solver matches the numpy
solver to 1e-9; `tests/test_rd_diffusion.py` reports 13 passed. **The CUDA control has now run on
the provider and passed under explicit IEEE FP32** — see §2.2. It was never run on this host,
which has no GPU. The end-to-end
CPU smoke output is named `smoke_evaluation_NOT_A_RESULT.json` because it is 150 steps on 30 debug
settings with an untrained model.

The 15-25 minute runtime figure in the packet is an **estimate scaled from CPU smoke timings, not
a GPU measurement**, and the packet says so.

**This pilot already instantiates part of H1** (§3): the equation is reused from registry id
`eq-rd-schnakenberg` with its claim and problem references kept attached — as **snapshot pins,
not live-store acceptance**. Whether a *withdrawal* propagates through those pins is untested.

### 2.2 What the provider run established

A paired control in the **same allocation** (job `aijob-e00qazx6sby3vav47b`, control window
23:09:31Z-23:09:38Z) settled the backend question that stopped the first attempt:

| | network CPU-vs-CUDA parity | verdict |
|---|---|---|
| first attempt, default backend | **0.001191914** | **failed** the 0.001 tolerance; stopped before training |
| same allocation, default backend | **0.001191914** | reproduced |
| same allocation, **explicit IEEE FP32** | **2.2649765e-06** | **passed**, same unchanged 0.001 tolerance |

Solver parity was **5.95e-14** in both, against a 1e-06 tolerance. The TF32 hypothesis was
**confirmed by measurement**, not assumed: the first failure was retained, the retry was declared
in advance in `inputs/diffusion-backend-policy.json`, and **nothing was relaxed** — source, config,
architecture, optimizer, dataset, splits and the tolerance itself are unchanged.

**Training began 16:09:38 PDT. No checkpoint exists yet and none is claimed.** Held-out evaluation
runs only after the checkpoint is frozen, by the preregistration's own ordering.

Receipt: `results/infra/diffusion-v2/backend-diagnosis.json`.

### 2.2 Everything above organism scale

Unbuilt. The pipeline in §1 applied to a whole organism is a proposal, and §6's table is the
honest inventory.

---

## 3. What we are proposing to add

The method class is established (§4). Our contribution is an integration, stated as two
hypotheses so that a later result can be graded against something fixed:

**H1 — provenance reaches into the training set.** Every synthetic datum carries the version of
the sourced claim whose equation and knob range produced it, so when a claim's status changes the
data generated under it is identifiable and the models trained on it are flagged. We have a live
instance to test this against: the mispredication correction withdrew a Turing-reliability claim
in place, and the commons already carries versioned records with a separate node-local review
status. The RD-1D pilot attaches claim refs today; propagation of a withdrawal is the open part.

*Scope of the negative:* one standard web search on 2026-10-31 over the ML training-data
provenance literature returned work on **detecting** whether synthetic data was used
(dataset-inference methods; TrainProVe, CVPR 2025) and nothing on retraction propagating into
derived synthetic data. That is a lead. It is not a demonstration that nobody has done it, and the
honest sentence is "we have not found prior art for this, and here is what we searched".

**H2 — the verifier carries its own validity domain.** The generate-then-verify literature treats
the exact solver as the oracle. Our own measurement argues for qualifying that: the textbook
Turing criterion's error on a finite domain is **windowed**, exactly 0% at half-integer multiples
of the critical wavelength and 6.22% at 1.25 λc, still 0.58% at 4.25 λc. A verifier that is wrong
in windows will certify candidates sitting in those windows, so the gate should carry scope
conditions — which is what the commons is built to hold.

Both are hypotheses about a combination. Neither is a result.

---

## 4. Related work, and what each contributes

Physics-informed generation and learning from mechanistic simulators are an active field with
strong published results. The roadmap builds on them directly.

### 4.1 Diffusion surrogates for mechanistic biological models — the closest precedent

**Comlekoglu T, Toledo-Marín JQ, DeSimone DW, Peirce SM, Fox G, Glazier JA.** *"Generative
diffusion model surrogates for mechanistic agent-based biological models."* arXiv:2505.09630
(v1 2025-05-01, v3 2025-10-23); *Machine Learning: Science and Technology*,
DOI 10.1088/2632-2153/ae11f8; PMID 41170496; PMC12570967.
Code: `github.com/tc2fh/CPM_DDPM_Surrogate`.
**Read-level: abstract** — arXiv abstract page fetched 2026-10-31; full text not read.

> **Cite the exact title.** It reads *"mechanistic **agent-based** biological models"*. The looser
> phrase "mechanistic biological simulations" has been used in briefs here; the precise title
> matters because the paper is specifically about agent-based models.

A denoising diffusion probabilistic model is trained as a surrogate for a **Cellular-Potts Model**
of in vitro vasculogenesis, with an image classifier aiding surrogate selection and verification,
reporting roughly a **22x reduction in computational time** generating configurations 20,000
timesteps ahead. Their motivation is that CPM simulations are stochastic, so a deterministic
network is ill-posed as a surrogate and a generative one is the right class.

**This is a close biological precedent for stages 1-2, on a model class we also run (Morpheus
CPM).** The RD-1D pilot's own preregistration cites it as an existing method class and states that
it claims no new diffusion methodology. Our extension is the evidence loop around it, not the
surrogate itself.

### 4.2 Physics residuals inside diffusion training

**Bastek J-H, Sun W, Kochmann DM.** *"Physics-Informed Diffusion Models."* arXiv:2403.14404
(v1 2024-03-21, v4 2025-03-13; Comments field: *"ICLR 2025 camera ready contribution"*).
Code under `github.com/jhbastek`.
**Read-level: abstract** — arXiv abstract page fetched 2026-10-31 for title, authors and dates;
findings below are at search-summary level and the full text is not read.

A physics/PDE residual is added to the denoising objective so samples are pushed toward satisfying
the governing equations; reported residual-error reduction of up to two orders of magnitude in a
fluid-flow case study, with the extra objective acting as regularisation. Handles equality and
inequality constraints.

**Relevance:** the RD-1D pilot deliberately uses **no** physics loss, so that the evaluation can
measure consistency rather than impose it. This is the natural next arm once a baseline exists.

### 4.3 Conditional score-based diffusion over simulator statistics

**Molinaro R, Lanthaler S, Raonić B, Rohner T, Armegioiu V, Simonis S, Grund D, Ramic Y, Wan ZY,
Sha F, Mishra S, Zepeda-Núñez L.** *"Generative AI for fast and accurate statistical computation
of fluids"* (GenCFD). arXiv:2409.18359 (v1 2024-09-27, v2 2025-02-03; Comments: 120 pages, 33
figures; no journal reference on the page).
Code: `github.com/camlab-ethz/GenCFD`.
**Read-level: abstract** for title, authors and dates; findings at search-summary level.

Conditional score-based diffusion for 3D turbulent flow statistics, reporting a complex 3D
turbulent flow generated in about one second.

**Relevance, and a warning we took:** their motivation is that deterministic ensembles trained on
mean-squared error **collapse toward the mean flow**. That is a reason to use a generative model —
and equally a reason to check that a generative surrogate's apparent diversity reflects the
mechanism rather than the sampler. The RD-1D evaluation compares conditional ensembles against
32-seed solver ensembles for exactly this.

### 4.4 Physics-informed diffusion in spectral space

**Gallon D, von Wurstemberger P, Cheridito P, Jentzen A.** *"Physics-informed diffusion models in
spectral space."* arXiv:2602.09708 (v1 2026-02-10, v2 2026-06-02).
**Read-level: abstract** — arXiv abstract page fetched 2026-10-31 (title, authors, dates only).
Cited on the live `#/generative` page; verified here.

### 4.5 Generate-then-verify with a solver gate

A 2025-2026 literature already pairs a generator with a solver as the final gate: a pore-scale
flow pipeline where generators propose, exact topology checks reject and a lattice-Boltzmann
solver verifies; dual-constrained diffusion for nonlinear microstructure inverse design with
direct evaluation; forward-model error thresholding for microwave-filter coupling matrices; and
adjoint-gradient guidance injected at each denoising step for photonic inverse design.
**Read-level: search-summary only** — one extended web search, 2026-10-31; no full texts read and
individual claims not verified.

**So stage 4's structure is established too.** What we are proposing is not a new pipeline shape;
it is what the pipeline is wired into.

---

## 5. The sharpest objection, and our answer

**"You generate training data from your simulator, then verify candidates with a solver built on
the same equations. That tests consistency with your model, not with biology."**

The objection is correct and we put it on the page ourselves. The same question is live in the
field — a reviewer note on a diffusion-based electromagnetic inverse-design paper raises it, and
the usual reply is that one forward solver for both is standard practice, which describes the
convention rather than settling it.

Our answer has three parts.

1. **Concede the scope.** Everything upstream of a real measurement is model-consistency checking.
   No amount of solver rigour changes that, and the RD-1D preregistration's non-claims list says so
   for the pilot specifically.
2. **Make the circularity legible.** The claim that licensed the equation, its review status and
   its scope conditions travel with the generated data, so a reader can see *which* model's
   consistency was checked. That is a real improvement over a surrogate whose training distribution
   is undocumented.
3. **Put the break where it belongs.** Calibration against real measurement is a milestone in its
   own right, and until it happens the surrogate's accuracy claims are bounded by the simulator.

A second honest limit: §4.3's mean-collapse finding cuts both ways, and we have not yet measured
whether generated diversity tracks the mechanism or the sampler. The RD-1D evaluation is designed
to answer that for one system.

---

## 6. Inventory

**Current as of 2026-10-31 16:09:38 PDT.** This table is the one that goes stale; check it against
§2.2 before quoting it.

| | Organism-scale proposal | RD-1D pilot |
|---|---|---|
| Preregistration | — | **frozen, `9c56a927`** |
| Code and job packet | — | **frozen, `4a5394f3`** |
| Local CPU controls | — | **pass; 13 tests; solver = numpy to 1e-9** |
| **CUDA control** | — | **RAN on the provider and PASSED under explicit IEEE FP32** (2.265e-06 against an unchanged 0.001). The default backend failed at 0.001191914; both outputs retained |
| **Synthetic datasets** | 0 | **generated inside the running job** — the dataset stage began with training |
| **Training** | 0 | **STARTED 16:09:38 PDT** |
| **Checkpoint** | 0 | **none yet, and none claimed** |
| Held-out evaluation | 0 | **not yet — it runs after the checkpoint is frozen** |
| Inverse candidates proposed | 0 | 0 — out of scope for the pilot |
| Candidates screened by an exact solver | 0 | 0 |
| Real experiments | 0 | 0 |
| **GPU hours spent** | **unknown until a receipt exists** | **unknown until a receipt exists** |

> **GPU hours are `unknown`, not `0`.** The job is running on a provider that has not yet returned
> a usage receipt, so zero would be a claim we cannot support. An earlier version of this table
> said 0; that was wrong in the same direction the rest of this document warns about.

The simulators in stage 1 do exist and run; several are live on the public MCP and anyone can call
them with no credential.

---

## 7. Revisions

- **2026-10-31, created.** Prior art verified against primary sources the same day.
- **2026-10-31, revised.** (a) Removed the sentence calling stage 4 "the part nobody has funded" —
  **we have no information about funding** and the claim was unsupported. (b) Added §2 with the
  RD-1D pilot's frozen commits and the explicit "no GPU result yet". (c) Upgraded every date to a
  direct reading of the arXiv abstract page: Bastek v1 is **2024-03-21** (the 2403 identifier is
  March 2024, not 2025) with v4 2025-03-13 and the ICLR 2025 reference taken from the Comments
  field; GenCFD v1 2024-09-27, v2 2025-02-03, with all twelve authors named and **no journal
  reference on the page**, so it should not be described as journal-published. (d) Added §4.4 for
  the Gallon et al. paper cited on the live `#/generative` page, verified here. (e) Rewrote §4 and
  §5 as a forward proposal that credits the prior work, replacing phrasing that read as scolding.
- **2026-10-31, revised again (root's second read).** §6's inventory still said the CUDA control
  had not run, that no datasets had been generated and that GPU hours were **0**, which
  contradicted the §2 that had just been rewritten. Every contradictory paragraph and table is
  updated, §2.2 records the paired-control measurement, and **GPU hours now read "unknown until a
  receipt exists" rather than 0** — a running provider job has returned no usage receipt, so zero
  would be a claim we cannot support. The §2.1 heading no longer says "no GPU result".
