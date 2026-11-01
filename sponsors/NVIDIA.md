# NVIDIA: what we used it for

Science Claw Hack @ MIT, Oct 30 – Nov 1, 2026. Everything below is read from repository files or
GitHub issues named in each row; nothing is from memory. Issues:
[#1](https://github.com/fractastical/delphi/issues/1) (general access),
[#14](https://github.com/fractastical/delphi/issues/14) (BioNeMo),
[#13](https://github.com/fractastical/delphi/issues/13) (ALCHEMI).

## What ran

### 1. A self-hosted claim assessor on an NVIDIA Brev GPU instance

| | |
|---|---|
| Service | NVIDIA Brev instance `delphi-gpu` (massedcompute L40S, 46 GB) |
| What ran on it | Qwen3-32B (AWQ 4-bit) served by vLLM 0.32, as a dataset-resolvability assessor |
| Used for | Assessing all **566 claims** of the Aristotle biology project (`claim-sources/aristotle-biology/`), one claim per request, JSON-schema constrained, about one claim per second at concurrency 24 |
| Why it matters | The pipeline rule is *assessor ≠ builder* and at least two assessor providers. An open-weights model on our own GPU is a provider that no frontier-API builder shares, at zero per-token cost |
| Where | `scripts/assess/README.md` (setup, serve and tunnel commands), `scripts/assess/run-assessor.mjs`, assessor record in `claim-sources/aristotle-biology/assessment/assessors.json` (`provider: "Alibaba Qwen weights, served with vLLM on an NVIDIA Brev L40S"`), outputs merged into `claim-sources/aristotle-biology/assessment/assessments.json` |

Not compared: Qwen's thinking mode (off in all runs, `scripts/assess/README.md`).

### 2. BioNeMo ESMFold NIM: called, refused, recorded

| | |
|---|---|
| Service | NVIDIA NIM, hosted ESMFold (`https://health.api.nvidia.com/v1/biology/nvidia/esmfold`) |
| What we did | `organism-design/esmfold/smoke-test.mjs --host nvidia` on bovine albumin (UniProt P02769, residues 25–607, checksummed input) |
| Result | HTTP 401 ("Invalid JWT serialization"): the hackathon key available to the session was a Brev key, not an `nvapi-` NIM key. The refusal is recorded as a run with `status: "refused"` in `organism-design/esmfold/runs/P02769/result.json`, and as two unsigned nanopub drafts (`organism-design/nanopubs/unsigned/claim-esmfold-P02769-refused.trig`, `evidence-esmfold-P02769-refusal.trig`) |
| Fallback | The same script was run against Meta's public ESM Atlas for cytochrome c from cattle, tuna and yeast (`runs/P00044-esmatlas`, `P62894-esmatlas`, `P81459-esmatlas`), attached to the `kimura-substitution-rate` claim. Those are not NVIDIA runs; the attachment file says so |

### 3. NIM protein-design backends wired into the design studio, not exercised

`sim-engine/generative/backends/protein.mjs` wires ProteinMPNN (inverse folding), RFdiffusion
(backbone design), Evo2 (DNA generation) and ESMFold (re-folding) NIMs behind `NVIDIA_API_KEY`.
Without a working key the protein level returns `not configured (NVIDIA NIM: ...)` and zero
candidates, and the public-structure fallback is labelled as prediction, not design. The test suite
checks that the endpoint answers 401 unauthenticated and that a bogus key reads as `auth failed`
(`sim-engine/generative/RESULTS.md` §6, tests `auth-failed`, `no-key-leak`). **NIM payloads have
not been run against a live key.**

### 4. BioNeMo review

All 27 NVIDIA-BioNeMo repositories were reviewed for fit on Oct 30 (issue
[#14](https://github.com/fractastical/delphi/issues/14), comment of 23:45 UTC): `bionemo-agent-toolkit`
was identified as the best fit. The harness proposal that would have made BioNeMo an agent harness was
judged "mostly backwards" in the architecture review (issue [#17](https://github.com/fractastical/delphi/issues/17);
`DEVELOPMENT-RECORD.md`): BioNeMo is a model service, not a place for an agent to live.

## What we did not use

- ALCHEMI (Batched Geometry Relaxation NIM): proposed in #13 as a simulate-then-print pairing with
  Formlabs; not run.
- DGX Spark: not used.
- The all-atom MD of the kcnk5b channel (`md/kcnk5b/`) was built for a university GPU cluster
  (`module load AMBER/24`), not on NVIDIA's hackathon resources, and its production stage was blocked
  by that cluster's GPU cap. It is not an NVIDIA sponsor contribution and is listed here only so it is
  not mistaken for one.

## Verification

Every number above comes from the named file. The 566-claim count is the number of entries in
`claim-sources/aristotle-biology/assessment/assessments.json` carrying the `qwen` assessor; the 401 is
quoted from `organism-design/esmfold/runs/P02769/result.json`. Nothing was re-run for this document.
