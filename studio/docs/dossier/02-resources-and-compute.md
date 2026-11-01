# Resources, compute and what we cannot account for

All figures below come from the published resource inventory
(`frontier.resource-inventory/1`) and the receipts it names. The inventory records an
`observed_at` time and states its own limits. Where a number is not measured, it is
reported as unknown, never as zero.

## GPU jobs (Nebius H100)

Project `project-e00p797qpr0049snsqvf0k`, shared with other hackathon teams. Our jobs are
those whose names begin `delphi-evolve-ops-` or `bioservices-`.

| | Count |
|---|---|
| Our jobs, total | **48** |
| completed | 35 |
| failed | 9 |
| cancelled | 4 |
| Our jobs non-terminal at observation | 0 |
| All jobs in the shared project | 67 completed, 21 failed, 6 cancelled |

**Allocation is not utilisation.** The inventory says so explicitly: requested capacity of
non-terminal jobs includes startup, `RUNNING` is not measured GPU utilisation, and kernel
utilisation is unknown until sampled telemetry is collected.

### Sampled GPU telemetry (the only real utilisation evidence)

Three tasks were sampled at 1 Hz with their own receipts:

| Task | Samples | GPU util mean | max | Power mean | GPU memory used |
|---|---|---|---|---|---|
| `ns2d-shear-demo-h100` | 52 | **96.6%** | 100% | 454 W | 1.8 GiB of 79.6 GiB |
| `ns2d-refine-h100` | 181 | **98.6%** | 100% | — | — |
| `heldout-validation-h100` | 149 | **51.6%** | 55% | 121 W | 0.7 GiB of 79.6 GiB |

These are **historical windows**, not current utilisation, and they cover three tasks, not
the whole campaign. Note the honest detail: the jobs used a small fraction of the 80 GiB
card, so "an H100 was busy" does not mean an H100 was needed.

## CPU

- A Nebius CPU worker attempt was **refused** by the provider: `ResourceExhausted` on
  quota `compute.instance.non-gpu.vcpu`, limit 24 vCPU against 28 requested. The failure is
  recorded with its request id rather than omitted.
- A later bounded CPU job **was** admitted: `aijob-e00bqeswtkd7dexff4`, 4 vCPU / 16 GB,
  3 arms, 1 thread per arm, with a packet sha256 and a pinned image digest.
- Google Cloud project `scienceclaw26bos-3016`: CPU VMs in `us-central1-a`, quota 32 vCPU
  in all regions and **0 GPU** quota. The lab account is scheduled for deletion.

## Model and LLM usage

Two receipts exist. **They are not aggregated**, because they measure different things.

| Receipt | Model | Measured |
|---|---|---|
| Discovery embedding index | `gemini-embedding-001` | 2,444 documents embedded, 49 embedding requests, 0 failed, 768 dimensions, 2 truncated inputs, in a 45-second window |
| Bioservices ledger | Gemini | 4 calls, 7,556 input tokens, 9,700 output tokens (thinking included) |

The inventory states plainly: **total provider LLM usage is unknown**, because other
workers are outside these receipts.

Additional bio-service work recorded separately on 2026-11-01: 105 API calls logged, 95
succeeded and 10 failed, across UniProt, Europe PMC, NCBI E-utilities, NCBI Datasets,
Ensembl, BioModels and ZFIN, plus 4 OpenFold2 structure predictions on Nebius (mean pLDDT
41–56, which is low confidence and labelled as such) and 5 BioModels CPU simulations at
the models' curated defaults.

## Cost

- **Billing meter queried: no. Actual spend: unknown.**
- The inventory adds the non-obvious caveat: zero worker creations from two recorded failed
  launch attempts does **not** establish zero total project spend.

## Agents and workers

- Native agents at observation: 1 root coordinator + 3 child agents, all reported
  `running` by the orchestration API. The inventory notes that *running* is an
  orchestration state, **not** measured CPU utilisation.
- Three sampled tmux panes were classified **unknown**: each had current command `python`
  and zero CPU-tick movement during a 2-second window. The inventory refuses to conclude
  idle or blocked from that, and says pane content was not read.

This is the level of care we tried to apply everywhere: a measurement that cannot support
a conclusion is recorded with the conclusion withheld.

## Honest summary for judges

We used real GPUs for real work and have 1 Hz telemetry proving near-saturation on two
flow-solver tasks. We also had long idle stretches, nine failed jobs, one quota refusal,
and we cannot tell you what any of it cost. The inventory is designed so that a reader can
see both.
