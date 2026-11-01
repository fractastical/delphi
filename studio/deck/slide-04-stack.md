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
| **474K** | lines of code written across two repositories | `git log --all --numstat` over source extensions: delphi-frontier 409,190 + delphi-evolve 65,372 |
| **2,175** | commits, both repositories created this week | `git log --all --oneline`: delphi-frontier 1,714 + delphi-evolve 461 |

## Band — swarm vs single agent (the headline comparison)

**Pre-registered, two experiments, 20 test plans.**
**Every multi-agent arm beat the single agent.**

| Arm | Verified datasets, exp 1 · exp 2 | Cost, exp 1 · exp 2 |
|---|---|---|
| single | 13 · 12 | $0.57 · $0.52 |
| isolated | 17 · 16 | $2.60 · $4.48 |
| centralized | 19 · 18 | $2.98 · $5.61 |
| decentralized | 18 (1 fabricated id) · 17 | $3.28 · $6.37 |

`claude-sonnet-5-5` via headless `claude -p` in every arm.
Source: `test-data/agent-comparison/four-arm.json`.

Every multi-agent arm beat the single agent by at least 4 of 20 verified datasets in both
experiments, with 0 fabricated identifiers in the final plans. **The three multi-agent arms
are not distinguishable from one another at n=20** under the pre-registered 2-claim margin —
centralized versus decentralized shows no difference in either experiment. Say that out loud:
the win is multi-agent over single, not one topology over another.

## Column 1 — GPU, CPU and VMs
**Nebius · Google Cloud**

- **Nebius H100 / L40S** — 140 jobs, 1 GPU each
- **Nebius Scientific AI** — 69 hosted tools available
- **Google Cloud** — 5 CPU VMs, 32 vCPU quota (project `scienceclaw26bos-3016`)
- **NVIDIA CUDA** — under every GPU run
- **Nebius CPU batch** — 4-vCPU arms, pinned image digest
- **NVIDIA Brev** — L40S instance `df-boltz2-kcnj13`, org `kganjam-c5d0a6-7kae`, serving Boltz-2
- **6 jobs** still running at slide time

> Telemetry at 1 Hz recorded **96.6%**, **98.6%** and 51.6% mean utilisation — measured, not allocated.

## Column 2 — Foundation models
**NVIDIA BioNeMo · Nebius · Google**

- **Evo 2** — genomic language model, 14 jobs (13 completed, 1 failed)
- **OpenFold2** — structure prediction, 4 predictions (mean pLDDT 41–56, low confidence, labelled)
- **Boltz-2** — served on a Brev L40S instance for KCNJ13 (instance up; no output receipt yet)
- **ESM2** — protein likelihoods, Kir2.1 variant-assay agreement pilot with passing controls
- **Gemini** — `embedding-001`, `3.8-flash`, `3.1-pro-preview`
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
**Open source · OpenResearch · every version pinned**

- **OpenMM 8.4** molecular dynamics (CUDA) · **WaterLily 1.10** 3-D Navier–Stokes
- **Morpheus 2.3.9** · **PhysiCell 1.14.2** cell-scale
- **BETSE 1.5.0** bioelectric · **Voxelyze** (pin `4287e365`) soft body
- **libRoadRunner** SBML replay · **Zebrafish-GEM** (CC-BY-4.0)
- **Neural cellular automata** · reaction–diffusion fields
- **Lattice-Boltzmann** · vortex-lattice aerodynamics
- **OpenResearch** (`orx 0.2.23`) — replay receipts, 2 exemplars

> **OpenResearch** replayed the published Collier 1996 Delta-Notch model: exit 0, **all replay
> checks passed**, and every output hash matched (`model_inventory.json`, `receipt_code_sha256`,
> three trajectory CSVs). Its own scope line is honest: OpenResearch here is a **local recorder
> of which code was run**, not a cloud dispatcher — no run used a remote backend.
>
> Plus **98 bio-database calls** (89 ok, 9 failed) — UniProt, Ensembl, NCBI E-utilities,
> NCBI Datasets, BioModels, ZFIN, Europe PMC.

## Column 4 — Design to object
**Formlabs · the agent swarm**

- **Print-ready STLs** — watertight, manifold, one body, verified not assumed
- **Wall checks** by inward ray-cast sampling (3,000 samples, 0 misses)
- **12 agent harnesses**, each with its own worktree, branch and job prefix
- **Lean 4 + Z3** — 37 statements, 17/17 mutants rejected, solver conflict certificates
- **14 cell-aggregate STLs** + 6 printable fish forms
- **Two parts physically printed** — design to object in one pipeline
- **Public MCP** — 21 tools, agents read the same record

> Design to printed part in one pipeline: **two pieces printed**. Every artifact carries a sha256,
> its inputs and the command that made it — **failures too**.

## Footer line

Counts read from provider CLIs, session transcripts and receipt files on the build host.
Brev instance `df-boltz2-kcnj13` (L40S) read from the Brev CLI. Print count attested by the
team; the STL manifests do not yet record the printer and resin used.

## What we did NOT do — keep these off the slide as claims

- **Formlabs**: two parts were printed (team-attested). The STL manifests still record printer
  and resin as `unknown`, so the *machine and material* are not yet in the record even though
  the prints happened. Worth closing before anyone audits the artifact chain.
- **Nebius Scientific AI**: 69 tools were available; only OpenFold2 and ESM2 have receipts here.
- No biological validation of anything. No wet-lab experiment. No registered cross-scale calibration.
- Total provider spend is **unknown** — the billing meter was never queried.
