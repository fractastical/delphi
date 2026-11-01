# Agent and compute usage

What was actually run, by whom, on what hardware. Every number here was read from a live
command at the time stated, not estimated. Where a figure cannot be measured, it says so.

**Read at:** 2026-11-01, late morning PDT. Sources: `tmux ls` and `ps` on the build host,
`nebius ai job list` (profile `hackathon`), `gcloud compute instances list`, the pushed
branch list on `github.com/kganjam/delphi-frontier`, and the status files each worker
writes to a shared message directory.

## Agents

### Sessions on the build host

| | Count |
|---|---|
| tmux agent sessions in total | **43** |
| live `claude` / `codex` processes | **47** |
| simulation harnesses (`ff-*`), all started for this campaign | **10** |

The 43 break down as: 17 `claude-NN` general sessions, 3 `codex-NN` plus 1 `codex-api`,
11 named role sessions (`dx-corpus`, `dx-critic-r1`, `dx-submit`, `dx-guilds`,
`dx-market`, `dx-gpuops`, `dx-collab`, `dx-fable-lead`, a rethink director and two
retired), and the 10 `ff-*` harnesses.

Not all 43 are active. Several are spend-capped, quota-exhausted or
authentication-blocked, and this count deliberately does not claim they are working.

### The ten simulation harnesses

Each owns one scale or question, runs in its own git worktree on its own branch, submits
its own cloud jobs under its own job-name prefix, and writes its own status file.

| Harness | Owns | Job prefix |
|---|---|---|
| `ff-evo` | Evo 2 regulatory-sequence work, fin and scale candidates | `claude-evo-` |
| `ff-mol` | molecular and cell scale; protein structure, signalling | `claude-mol-` |
| `ff-tissue` | tissue and developmental; patterning, growth | `claude-tissue-` |
| `ff-organ` | organ and organism; fin mechanics, aerodynamics, glide | `claude-organ-` |
| `ff-neuro` | neural scale; escape, CPG, glide stabilisation | `claude-neuro-` |
| `ff-eco` | ecological and collective; reachability, schooling | `claude-eco-` |
| `ff-zf2ff` | the zebrafish-to-flying-fish project | `claude-zf2ff-` |
| `ff-xeno` | the preregistered microcarrier endpoints | `claude-xeno-` |
| `ff-voxgpu` | unblocking the GPU voxel engine | `claude-voxgpu-` |
| `ff-xenomodel` | actuation equations, a Lean family, PhysiCell | `claude-xenomodel-` |

Two earlier background workers (GPU operations and bio-services) ran to completion before
these and are counted separately.

### What makes them distinct rather than copies

Each holds different tools and different context, and they hand work to one another
through files rather than conversation, so a worker can pick up another's output without
shared memory. **8 status files** exist in the shared message directory, each timestamped
and rewritten atomically. Cross-harness handoffs are written as named packets, for example
the Evo-to-zebrafish and voxgpu-to-xeno routes.

**The honest limit.** They were allocated by a coordinating session, they share one git
identity, and no controlled comparison against a single agent was run. Our own
review-corrections ledger refuses to claim an agent-count advantage, and so does this page.

## Branches and worktrees

| | Count |
|---|---|
| `claude/*` branches pushed to the public repository | **8** |
| git worktrees created for this campaign | **14** |

Pushed branches: `about-blog`, `bioservices`, `dossier`, `eco`, `evo2-fin-scale`,
`mol-sims`, `neuro`, `zf2ff`. More are in flight and unpushed.

## GPU jobs — Nebius H100

Project `project-e00p797qpr0049snsqvf0k`, shared with other hackathon teams.

### Everything in the shared project

| State | Jobs |
|---|---|
| COMPLETED | 87 |
| FAILED | 23 |
| CANCELLED | 6 |
| RUNNING | 2 |
| ERROR | 1 |
| **Total listed** | **123** |

### Ours

**77 jobs** carry one of our name prefixes. Of those, the **28** submitted by the ten
harnesses in this campaign stand at:

| State | Jobs |
|---|---|
| COMPLETED | 19 |
| RUNNING | 2 |
| FAILED | 2 |
| ERROR | 1 |
| PROVISIONING | 1 |

By harness: `claude-zf2ff` 7, `claude-tissue` 5, `claude-organ` 5, `claude-evo` 5,
`claude-mol` 4, `claude-neuro` 2. The remaining 49 of our 77 are the earlier
`delphi-evolve-ops-` and `bioservices-` families.

Every job is 1 GPU. Failures are kept in the record; three of this campaign's jobs did not
succeed and are counted above rather than dropped.

### Measured GPU utilisation

Allocation is not utilisation, so the only real evidence is sampled telemetry at 1 Hz:

| Task | Samples | Mean util | Max | Power |
|---|---|---|---|---|
| `ns2d-shear-demo-h100` | 52 | 96.6% | 100% | 454 W |
| `ns2d-refine-h100` | 181 | 98.6% | 100% | — |
| `heldout-validation-h100` | 149 | 51.6% | 55% | 121 W |

Three tasks, historical windows. They do not establish continuous saturation across the
campaign, and the jobs used a small fraction of each 80 GiB card.

## CPU

- **Google Cloud**, project `scienceclaw26bos-3016`: 5 instances exist, **1 RUNNING**
  (16 vCPU) and 4 terminated. Quota is 32 vCPU in all regions and **0 GPU**. The lab
  account is scheduled for deletion, so artifacts are exported ahead of it.
- **Nebius CPU**: one attempt was refused with `ResourceExhausted` on
  `compute.instance.non-gpu.vcpu` (limit 24 vCPU against 28 requested); a later bounded
  4-vCPU job was admitted.
- **Build host**: shared by every session above, running PostgreSQL, the web service, the
  Lean toolchain and the browser suite alongside the harnesses.

## Model and API usage

Two receipts exist and are **not** aggregated, because they measure different things:

| Receipt | Model | Measured |
|---|---|---|
| Discovery embedding index | `gemini-embedding-001` | 2,444 documents embedded, 49 requests, 0 failed, 768 dimensions, 45-second window |
| Bioservices ledger | Gemini | 4 calls, 7,556 input tokens, 9,700 output tokens including thinking |

Separately, a bio-service harvest logged **105 API calls, 95 succeeded and 10 failed**
across UniProt, Europe PMC, NCBI E-utilities, NCBI Datasets, Ensembl, BioModels and ZFIN,
plus 4 OpenFold2 predictions and 5 BioModels CPU simulations.

Models in use across the fleet: Claude (Opus 5 and 5.5) for the harnesses, Gemini
(`gemini-embedding-001`, `gemini-3.8-flash`, `gemini-4-argon`) for indexing and
cross-review, Evo 2 and OpenFold2 through Nebius, and hosted scientific models through the
Nebius Scientific AI workbench.

## What is not measured

- **Total token usage across all sessions: unknown.** Only the two receipts above cover
  model usage, and they are scoped to the discovery index and one bio-services ledger.
- **Total provider spend: unknown.** The billing meter was never queried. Zero worker
  creations from two failed launch attempts does not establish zero spend.
- **Continuous GPU saturation: not established.** Three sampled windows are not a campaign.
- **Which sessions were productive: not claimed.** A session existing, or reporting
  `running`, is an orchestration state, not measured work.
- **Any multi-agent advantage: not measured.** No controlled single-agent arm was run.
