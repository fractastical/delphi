# Resource utilization snapshot

Observed **2026-10-31 13:54:13 PDT (20:54:13 UTC)**. The machine-readable inventory and schema are [`resource-inventory.json`](../results/resources/resource-inventory.json) and [`resource-inventory.schema.json`](../results/resources/resource-inventory.schema.json).

## Cloud compute

The latest Nebius read (20:52:14–20:52:15 UTC), filtered to this project’s `delphi-evolve-ops-` jobs, returned 17 jobs: 13 `COMPLETED`, 3 `CANCELLED`, 1 `FAILED`, 0 `RUNNING`, and 0 `PULLING`. There were no active allocations at the time of that query.

Four persisted telemetry summaries are available. Each is a historical window, not current usage:

| Workload | UTC sampling window | Samples | Mean GPU utilization | Mean GPU memory |
|---|---|---:|---:|---:|
| NS2D shear | 19:54:05–19:54:56 | 52 | 96.63% | 1,799.4 MiB |
| Held-out validation | 20:10:28–20:12:57 | 149 | 51.56% | 743.54 MiB |
| NS2D refine | 20:34:27–20:37:27 | 181 | 98.62% | 1,908.21 MiB |
| Evo2 zebrafish | 20:36:42–20:44:57 | 493 | 34.78% | 16,605.92 MiB |

Sources: [NS2D shear](../results/resources/telemetry/ns2d-shear.json), [held-out validation](../results/resources/telemetry/heldout-validation.json), [NS2D refine](../results/resources/telemetry/ns2d-refine.json), [Evo2 zebrafish](../results/resources/telemetry/evo2-zebrafish.json). These are byte-identical copies of the summaries in the compute worktree. The inventory records each file’s SHA-256, original path, and exact window.

The bounded Nebius 4-vCPU CPU worker create was rejected with `ResourceExhausted`: quota limit 24 vCPUs, aggregate requested 28. No worker was created. Google Compute remains disabled: the API enable attempt returned `FAILED_PRECONDITION` / `UREQ_TOS_NOT_ACCEPTED`; no VM was created. The copied [provider outcome receipt](../results/resources/provider-outcome.json), byte-identical to the source receipt, has SHA-256 `3343f987b531ec2609e24cc84edd62ade262af492932e08725a91f8b7cfc7b61`.

## Model calls

The discovery index receipt records **2,444 documents embedded in 49 requests**, with zero failed requests. This is the specific `gemini-embedding-001` indexing run, not total Gemini usage. [Receipt source on the discovery branch](https://github.com/kganjam/delphi-frontier/blob/4c1efea321ac32b403f64f436b8bcc74cb905a10/imports/2026-10-31-discovery-live-index-receipt.json), SHA-256 `a6f0e2256f69adc2f7bc613ca6b04d267c96e031caeaf15ba7800eb82202f27d`.

The separate [bioservices usage ledger](../results/bioservices/gemini_usage_ledger.json) records 4 Gemini LLM calls (7,556 input tokens; 9,700 output tokens including thinking). Do not add embedding requests to LLM call counts or treat these receipts as total provider usage. The discovery refresh timer receipt is [on the discovery branch](https://github.com/kganjam/delphi-frontier/blob/4c1efea321ac32b403f64f436b8bcc74cb905a10/imports/2026-10-31-discovery-refresh-timer-receipt.json), SHA-256 `12ca3902f8487b7a7e3464ef36dd4a3f9d3f953527f91ad4f65cd7f99959fa5e`; it documents schedule installation, not usage or billing.

## Workers and cost

The collaboration API reported three child agents running, with the root coordinator also running. Three selected Frontier tmux panes were sampled without reading pane contents. Each had command `python` and zero process CPU tick movement during 20:54:11–20:54:13 UTC; their activity is **unknown**, not proven idle or blocked.

Actual billing was not queried. **Spend is unknown**; zero workers created in the bounded cloud provisioning paths does not establish zero project spend. The [Gemini index](https://github.com/kganjam/delphi-frontier/blob/4c1efea321ac32b403f64f436b8bcc74cb905a10/imports/2026-10-31-discovery-live-index-receipt.json), [bioservices ledger](../results/bioservices/gemini_usage_ledger.json), four copied [Nebius telemetry summaries](../results/resources/telemetry/), and [provider outcome receipt](../results/resources/provider-outcome.json) are the evidence sources. See the inventory’s `sources` array for hashes and provenance.
