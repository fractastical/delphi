# Slide 04 — The stack we ran on

> Feed this file to the deck. Every figure is read from a provider CLI, a session
> transcript or a receipt file on the build host. Nothing is estimated.

**Eyebrow:** 04 · The stack we ran on
**Headline:** A trillion tokens of reasoning, turned into *checkable biology*.
**Sub:** Sponsor infrastructure, foundation models and mechanistic simulators, driven end to end by an agent swarm — every run leaving a receipt.

## Hero numbers

| Figure | Caption | Source |
|---|---|---|
| **1.07T** | tokens across 14 models and 24,976 sessions | Codex 922,177,496,289 + Claude 144,988,434,152, summed from the `usage` block of every assistant message |
| **140** | H100 GPU jobs on Nebius · 109 completed | `nebius ai job list`, names `claude-*`, `delphi-evolve-ops-*`, `bioservices-*`. 109 completed, 12 failed, 11 cancelled, 6 running, 1 error |
| **31** | recorded simulations across 9 biological scales | `site/data/snapshot.json` → `simulation_manifests` |
| **98.6%** | peak mean GPU utilisation, sampled at 1 Hz | `results/resources/telemetry/ns2d-refine.json`, 181 samples |
| **2,444** | documents embedded for live semantic search | `gemini-embedding-001`, 49 requests, 0 failed |

## Column 1 — GPU, CPU and VMs
**Nebius · Google Cloud**

- **Nebius H100 / L40S** — 140 jobs, 1 GPU each
- **Nebius Scientific AI** — 69 hosted tools available
- **Google Cloud** — 5 CPU VMs, 32 vCPU quota (project `scienceclaw26bos-3016`)
- **NVIDIA CUDA** — under every GPU run
- **Nebius CPU batch** — 4-vCPU arms, pinned image digest
- **6 jobs** still running at slide time

> Telemetry at 1 Hz recorded **96.6%**, **98.6%** and 51.6% mean utilisation — measured, not allocated.

## Column 2 — Foundation models
**NVIDIA BioNeMo · Nebius · Google**

- **Evo 2** — genomic language model, 14 jobs (13 completed, 1 failed)
- **OpenFold2** — structure prediction, 4 predictions (mean pLDDT 41–56, low confidence, labelled)
- **ESM2** — protein likelihoods, Kir2.1 variant-assay agreement pilot with passing controls
- **Gemini** — `embedding-001`, `3.8-flash`, `4-argon`
- **Claude** — Opus 5.5 / Opus 5 / Sonnet 5.5 / Haiku 5.5
- **MiniMax** M2.7 · **GLM** 5 · **GPT-5.6**

> **Evo 2 result.** Real fin/ray/scale regulatory windows beat **their own** dinucleotide-preserving
> shuffles, paired by window so composition, GC and gene identity are held fixed:
> **+0.1444 log-prob/base, 95% CI [0.0980, 0.1908], t = 6.53, p = 3.9×10⁻⁶, n = 19.**
> It holds in the flying fish alone (+0.0993, CI [0.0453, 0.1533], n = 9) — and
> `GCA_018398805.1` is almost certainly **not** in Evo 2's training corpus, so that
> figure cannot be verbatim recall. The uniform-random self-check lands at −1.3997
> against the required −ln 4 = −1.3863, so the control works.
> *This is a sequence likelihood, not a functional enhancer and not a validated design.*

## Column 3 — Mechanistic simulators
**Open source, every version pinned**

- **OpenMM 8.4** molecular dynamics (CUDA) · **WaterLily 1.10** 3-D Navier–Stokes
- **Morpheus 2.3.9** · **PhysiCell 1.14.2** cell-scale
- **BETSE 1.5.0** bioelectric · **Voxelyze** (pin `4287e365`) soft body
- **libRoadRunner** SBML replay · **Zebrafish-GEM** (CC-BY-4.0)
- **Neural cellular automata** · reaction–diffusion fields
- **Lattice-Boltzmann** · vortex-lattice aerodynamics

> Plus **105 bio-database calls** (95 ok, 10 failed) — UniProt, Ensembl, NCBI E-utilities,
> NCBI Datasets, BioModels, ZFIN, Europe PMC.

## Column 4 — Design to object
**Formlabs · the agent swarm**

- **Print-ready STLs** — watertight, manifold, one body, verified not assumed
- **Wall checks** by inward ray-cast sampling (3,000 samples, 0 misses)
- **12 agent harnesses**, each with its own worktree, branch and job prefix
- **Lean 4 + Z3** — 37 statements, 17/17 mutants rejected, solver conflict certificates
- **14 cell-aggregate STLs** + 6 printable fish forms
- **Public MCP** — 21 tools, agents read the same record

> Every artifact carries a sha256, its inputs and the command that made it. **Failures are published too.**

## Footer line

Counts read from provider CLIs, session transcripts and receipt files on the build host.
Printer and resin not yet selected; nothing physically printed. NVIDIA Brev: account not activated.

## What we did NOT do — keep these off the slide as claims

- **NVIDIA Brev**: the CLI is installed but the account was never activated. No Brev run exists.
- **Formlabs**: STLs pass their print gates, but printer and resin are recorded as `unknown`
  and **nothing was physically printed**.
- **Nebius Scientific AI**: 69 tools were available; only OpenFold2 and ESM2 have receipts here.
- No biological validation of anything. No wet-lab experiment. No registered cross-scale calibration.
- Total provider spend is **unknown** — the billing meter was never queried.
