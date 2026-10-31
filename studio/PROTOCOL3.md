# PROTOCOL 3: Evo 2 (7B) setup-and-score capability test on one H100

Author `dx-gpuops-r1` (Claude Sonnet 5.5). Time from `date`: 2026-10-31 12:31:23 PDT. Frozen before the job is submitted. Review status: single-reader, not Codex-reviewed. Priority set by the user (Evo2 with the bioservices worker, one H100, at most 60 minutes). Evidence kind: `simulated`/`predicted` model output on a public sequence; nothing observed.

## Question
Can Evo 2 7B be installed, loaded and run for sequence scoring on one Nebius H100 within 60 minutes, and does its scoring pass basic sanity controls? This is a **capability and setup test**. It makes no claim about any organism, gene, variant or biological question, and no fitness or variant-effect claim. A biological use needs its own protocol (data, acceptance, baseline) from the worker that owns the question (bioservices, claude-12); this test only establishes whether such a run would be feasible here.

## Sources (read by me before freezing)
* HuggingFace model `arcinstitute/evo2_7b`: not gated, license Apache-2.0 (model card), revision `bda0089f92582d5baabf0f22d9fc85f3588f6b58`, file `evo2_7b.pt` 13,766,621,200 bytes, LFS sha256 `c66645929dc1b9c631f5be656da8726f38946315dc9167000a615dd626fcecf4` (public API, fetched 2026-10-31 12:31:23 PDT).
* GitHub `ArcInstitute/evo2`: Apache-2.0, `pyproject` version 0.6.0, requires Python >= 3.11 and < 3.13, dependencies biopython, huggingface_hub, torch, vtx >= 1.1.0; README states the 7B models run in bfloat16 without Transformer Engine or FP8.
* Input sequence: NCBI nuccore NC_000913.3 (E. coli K-12 MG1655), complement strand 364500..362455, 2,046 nt, file `inputs/evo2_ecoli_NC_000913.3_c364500-362455.fa` sha256 `c5f29ad94881f471f7a4f7d5ea55c836e391e152807e6d71af4126cb98b938e1` (NCBI efetch). It is chosen only as a public natural sequence; E. coli genomes are likely within the training data of Evo 2, so the result must not be read as generalization.

## Procedure (script `evo2_smoke/evo2_smoke.py`, sha256 `c588b584a6a04d0329bc3273c7a73308184c9e1917e5a3c65de94c948dfe495e`)
Stages, each timed and recorded, failures recorded not hidden, global inner budget 3000 s inside a 60-minute server timeout: (1) environment report (GPU, driver, torch, packages already in the container image `nvcr.io/nvidia/pytorch:25.12-py3`); (2) network reachability check; (3) `pip install --no-deps evo2 vtx` plus biopython and huggingface_hub, resolving missing pure-python imports one by one (torch is never reinstalled); (4) download `evo2_7b.pt` at the pinned revision and compute its sha256; (5) load `Evo2('evo2_7b')`; (6) score the natural sequence and controls.

## Controls and acceptance (fixed now)
Score = mean negative log-likelihood per nucleotide (nats) from the model's next-token logits over the full vocabulary.
* **A1** install and import succeed, weights sha256 equals the pinned LFS oid, model loads.
* **A2** logits finite, shape (1, L, V).
* **A3** determinism: scoring the same input twice gives maximum absolute log-probability difference <= 1e-3.
* **A4 baselines:** natural-sequence NLL is below the uniform baseline ln 4 = 1.3863 and below the order-0 entropy of its own base composition.
* **A5 must-fail controls:** natural NLL is below that of two mononucleotide shuffles of the same sequence (seeds 1 and 2) and of a uniform iid random sequence of equal length (seed 3).
Result labels: PASS if A1 to A5 hold; PARTIAL if loading works but any of A2 to A5 fails (reported as it is, with the failing control named); SETUP-FAILED if A1 fails (the error text of the failing stage is the result). Timing of the first 8,184-nt forward is reported with its first-call overhead.

## Bounds and conduct
One 1-GPU H100 job, server timeout 60 min, pool and our active jobs re-read by the controller before launch; ten team H100s is a ceiling, not a target; no job that is not mine is touched. No credential is used or passed (public weights, no token). Cost: the event exposes no price or usage receipt to participants: unavailable (not zero).
