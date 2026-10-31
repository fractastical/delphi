# Forward-generation roadmap: synthetic data from sourced mechanism, conditional generators, solver-gated inverse screening

**Status: a roadmap and a hypothesis. Nothing here is built.** No dataset has been generated, no
model has been trained, no candidate has been screened. Every forward-looking sentence below is a
proposal. This document exists so the pitch can describe the direction without any reader
mistaking it for a result.

Read-levels, per `docs/research/README.md` convention: `full-text` | `abstract` | `search-summary`.
Each prior-art entry carries its own.

---

## 1. The pipeline, in four stages

1. **Forward — synthesise.** Take mechanistic equations and their knob ranges **from sourced claim
   records in the commons**, not from memory. Sweep the simulators we already run (BETSE ion/pump/
   gap-junction, Morpheus CPM/ODE/PDE, zebrafish-GEM metabolic, the bounded bioelectric and
   mechanobio models already exposed on the public MCP) across those ranges. Each synthetic datum
   carries the version hash of the claim that licensed its equation and the hash of the request
   that produced it.
2. **Train — conditional generator.** Fit a conditional diffusion model or a latent neural
   operator on those sweeps, conditioned on the knobs and on the regime labels.
3. **Inverse — propose.** Condition on a target morphology or behaviour; sample candidate
   parameter sets and fields.
4. **Screen — gate.** Reject candidates with the exact solver, then with real experiments.

Stage 4 is where the claim of usefulness lives, and stage 4 is the part nobody has funded.

---

## 2. Prior art: every stage is already published, and we say so first

### 2.1 Diffusion surrogates for mechanistic biological models — *the closest work to stage 1-2*

**Comlekoglu T, Toledo-Marín JQ, DeSimone DW, Peirce SM, Fox G, Glazier JA.**
*"Generative diffusion model surrogates for mechanistic agent-based biological models."*
arXiv:2505.09630 (v1 2025-05-01, v3 2025-10-23); *Machine Learning: Science and Technology*,
DOI 10.1088/2632-2153/ae11f8; PMID 41170496. Code: `github.com/tc2fh/CPM_DDPM_Surrogate`.
**Read-level: abstract** (arXiv abstract page fetched 2026-10-31; full text not read).

> **Note the exact title.** It is *"mechanistic **agent-based** biological models"*, not
> "mechanistic biological simulations". The brief that pointed us here used the looser phrase, and
> the precise one matters: this paper is about agent-based models specifically.

They train a denoising diffusion probabilistic model as a surrogate for a **Cellular-Potts Model**
of in vitro vasculogenesis, and use an image classifier to aid surrogate selection and
verification. They report roughly a **22x reduction in computational time** generating
configurations 20,000 timesteps ahead of a reference. Their stated motivation is that CPM
simulations are stochastic, so a deterministic network is ill-posed as a surrogate and a
generative one is the right class.

**What this means for us, stated bluntly: stage 1-2 of our roadmap is their published result, in
biology, on a Cellular-Potts model — and we run Morpheus CPM.** We do not get to call the forward
half novel. If we build it, we are replicating and extending their work, and the honest word is
"replicating".

### 2.2 Physics residuals inside diffusion training — *constrains stage 2*

**Bastek J-H, Sun W, Kochmann DM.** *"Physics-Informed Diffusion Models."* arXiv:2403.14404,
ICLR 2025. Code under `github.com/jhbastek`.
**Read-level: search-summary** (abstract listing and conference page; full text not read).

A physics/PDE residual term is added to the denoising objective so samples are pushed to satisfy
the governing equations. Reported: residual error reduced by up to two orders of magnitude against
prior work in a fluid-flow case study, and the extra objective acts as regularisation against
overfitting. Handles equality and inequality constraints.

**For us:** the idea of making the generator respect the mechanism rather than only the data is
published. We would be applying it, not inventing it.

### 2.3 Conditional score-based diffusion for simulator statistics — *the shape of stage 2-3*

**Molinaro R, Lanthaler S, Raonić B, et al.** *"Generative AI for fast and accurate statistical
computation of fluids"* (GenCFD). arXiv:2409.18359 (submitted 2024-09-27, revised Feb 2025).
Code: `github.com/camlab-ethz/GenCFD`.
**Read-level: search-summary** (abstract listing; full text not read).

Conditional score-based diffusion for 3D turbulent flow statistics, reporting a complex 3D
turbulent flow generated in about one second. Their motivation is directly relevant to us:
deterministic ensembles trained on mean-squared error **collapse toward the mean flow**, which
destroys exactly the variability a biological design study needs.

### 2.4 Generate-then-verify with an exact solver — *stage 4 is also not ours*

A 2025-2026 literature already does propose-filter-verify with a solver as the final gate, across
several domains: a pore-scale flow pipeline where generators propose, exact topology checks
reject, a surrogate screens and a lattice-Boltzmann solver verifies; dual-constrained diffusion
for nonlinear microstructure inverse design with direct evaluation; forward-model error
thresholding for microwave-filter coupling matrices; and adjoint-gradient guidance injected at
each denoising step for photonic inverse design.
**Read-level: search-summary only** (one extended web search, 2026-10-31; no full texts read, and
I did not verify individual claims in these papers).

**So the architecture — forward sweeps, conditional generator, inverse proposal, solver gate — is
prior art end to end.** Anyone claiming it as new at this hackathon is wrong, and we will not.

---

## 3. What we would actually be claiming, and how small it is

Two things, and we state them as **hypotheses about a combination**, not as results:

**H1 — Provenance reaches into the training set.** Every synthetic datum carries the version hash
of the sourced claim whose equation and knob range produced it. When a claim is **withdrawn**, the
data generated under it is identifiable and the models trained on it are flagged. We have a live
instance of a withdrawal to test this against: the mispredication correction withdrew our own
Turing-reliability claim in place (`bench/mispredication/README.md`), and the commons already
carries versioned records with a separate node-local review status.

*Scope of the negative:* one standard web search on 2026-10-31 over the ML training-data
provenance literature returned work on **detecting** whether synthetic data was used
(dataset-inference methods; TrainProVe, CVPR 2025) and **nothing** on retraction propagating into
derived synthetic data. That is a lead, **not** a demonstration that nobody has done it. The
honest sentence is "we have not found prior art for this, and here is what we searched" — not
"this is new".

**H2 — The exact solver carries its own validity domain.** The generate-then-verify literature
treats the solver as the oracle. Our own measured result says that is unsafe: the textbook Turing
criterion's error on a finite domain is **windowed**, exactly 0% at half-integer multiples of the
critical wavelength and 6.22% at 1.25 λc, still 0.58% at 4.25 λc. A verifier that is wrong in
windows will certify candidates that sit in those windows. So the gate must carry scope conditions,
and those scope conditions are the thing our commons is already built to hold.

That is the whole claim. It is modest. It is not "first diffusion model in synthetic biology",
it is not an IP position, and nobody should put either phrase on a slide.

---

## 4. The objection that will be put to us, and the honest answer

**"You generate training data from your simulator, then verify candidates with a solver built on
the same equations. You have proved consistency with your own model, not with biology."**

That objection is correct, it is already live in the literature — a reviewer note on a
diffusion-based electromagnetic inverse-design paper raises exactly it, and the authors' reply is
that one forward solver for both is standard practice — and we should concede it immediately
rather than defend it.

**Our answer, in full:** the circularity is real and it is not removed by any amount of solver
rigour. It is broken only at stage 4's second half, **real experiments**, which we have not done
and are not funded to do. Everything upstream of a wet-lab measurement is model-consistency
checking, and we will label it that way. What the commons adds is that the circularity is
*declared*: the claim that licensed the equation, its review status, and its scope conditions are
all attached to the generated data, so a reader can see which model's consistency was checked.

A second honest concession: §2.3's finding that MSE-trained deterministic surrogates collapse to
the mean is a reason to use a generative model, **and** a warning that a generative surrogate's
apparent diversity can be an artifact of the sampler rather than of the mechanism. We have not
measured that distinction and would need to before reporting any sweep.

---

## 5. What would have to be true, stated before any run

Preregistration-shaped, so a later result cannot be graded against a moved target:

- **Falsifier for the surrogate.** If the generator's samples do not reproduce held-out simulator
  statistics at a stated tolerance on parameter sets withheld from training, the surrogate is
  rejected. A surrogate that only interpolates within its sweep is reported as such.
- **Must-fail control.** A deliberately wrong knob range must produce samples the classifier or
  the solver rejects. A screen that cannot reject anything has not been tested.
- **Positive control.** A parameter set with a known simulator outcome must pass end to end.
- **Stop rule.** If the solver gate accepts candidates at a rate indistinguishable from random
  draws over the same knob ranges, the pipeline adds nothing and we report that null.
- **INCONCLUSIVE band declared in advance**, not after seeing the numbers.
- **No composite score.** Formal correctness, numerical accuracy and empirical accuracy stay
  separate, as everywhere else in this project. There is no single number for whether a generated
  organism works.

---

## 6. Current state, for the avoidance of doubt

| | |
|---|---|
| Synthetic datasets generated | **0** |
| Models trained | **0** |
| Inverse candidates proposed | **0** |
| Candidates screened by an exact solver | **0** |
| Real experiments | **0** |
| GPU hours spent on this | **0** |

The simulators in stage 1 **do** exist and run — several are live on the public MCP and anyone can
call them with no credential. That is the only part of this document with a receipt.

---

## 7. Revisions

- **2026-10-31** — created. Prior art verified against primary sources on the same day: arXiv
  abstract page for 2505.09630 (exact title, authors, dates, 22x figure, DOI); web search for
  2403.14404 and 2409.18359 (abstract-level only). The brief that commissioned this document gave
  the third paper's title as "...for mechanistic biological simulations"; the exact title is
  "...for mechanistic **agent-based** biological models", corrected here.
