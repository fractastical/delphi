# Bio model services

This note records one source-pinned zebrafish Kcnj13 structure prediction and
the available hosted structure interface. It does not claim a BioNeMo runtime.

## Provider identity and capability

The live Nebius Scientific AI MCP endpoint reported server version `0.1.0`
and exposed `infer_openfold2_native`. Its OpenFold2 schema accepts one
uppercase sequence of 1–1,024 residues, one selected model, and optional
idempotency and output-prefix fields. The service description specifies a
single-sequence dummy MSA, with no external MSA, template, or relaxation. The
observed runtime identity was
`registry.serverless2.local/nebius/scientific-ai/models/openfold2@sha256:9fc70e781b18f4f547da237e2eb81387df3c38d092bb44c46145db6347e7e164`.
The service did not return evidence that this operation used NVIDIA BioNeMo.

NVIDIA's [BioNeMo NIM overview](https://docs.nvidia.com/nim/bionemo) describes
NIM as self-hosted inference microservices. The
[BioNeMo Agent Toolkit](https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit)
provides model skills and operating instructions; it is not itself the model
runtime. The hosted OpenFold2 call below is therefore attributed to Nebius
Scientific AI, not to NIM or the Agent Toolkit.

## Input provenance and sequence choice

The target is zebrafish `kcnj13`, NCBI GeneID `555691`, ZFIN
`ZDB-GENE-070129-1`. The selected input is the source-native NCBI protein
record `BAF03613.1` (362 aa). Its full unwrapped sequence exactly matches
UniProtKB `Q0KIZ7` (`Q0KIZ7_DANRE`), with sequence SHA-256
`8029209004a52efea91ae2c899c017ed4795a843615b4b272c7087c67ba396b2`.
UniProt reports protein existence evidence level 2 (predicted). The source
records and retrieval checksums are in
[`artifacts/bio-services/kcnj13_source/source_manifest.json`](../artifacts/bio-services/kcnj13_source/source_manifest.json).

The current NCBI RefSeq `NP_001429136.1` (transcript variant 4,
`NM_001442207.1`) is 358 aa and differs at the N-terminus. Its SHA-256 is
`8c8a45846e3b614a790f2b6df507be9f45d8c9878befee5a92a0de00cc71b88b`. Both
records are retained. The chosen sequence is **not labeled canonical**, and
the discrepancy is not reconciled by inference.

## Bounded prediction

The submitted operation is recorded at
[`artifacts/bio-services/kcnj13_openfold2/operation_receipt.json`](../artifacts/bio-services/kcnj13_openfold2/operation_receipt.json).
It uses `infer_openfold2_native`, model `openfold2`, one selected model,
relaxation disabled, and a stable sequence-derived idempotency key. This was a
single, unmodified native protein sequence; no sequence-generation or
mutagenesis tool was used. The receipt preserves the provider's operation ID,
states, exact sequence hash, response, and result hashes. Structure bytes are
kept in `rank1.pdb` when returned; the provider response is kept in
`result.json`.

The operation `op-5ba1d104dbbcd293` succeeded. The provider reported
`upstream-source-not-nim`, 15.54 seconds of inference, and did not report its
physical accelerator allocation. The returned rank-1 PDB was SHA-256 checked
and parsed as one chain with 362 C-alpha residues; its sequence exactly matches
the pinned input. The structure SHA-256 is
`3200f58843b77ccee331ff088376f16adabefb71adf4b9e8bd3a4aa2cbd6f5ae`.

Returned model metrics were ranking confidence / mean pLDDT 52.86, pTM 0.273,
and mean predicted aligned error 22.91 Å. These are model-internal scores, not
experimentally calibrated probabilities. Their low values limit confidence in
the predicted fold and relative placement. Full metrics, the rank-1 structure,
and provider artifact captures are recorded under
[`artifacts/bio-services/kcnj13_openfold2/`](../artifacts/bio-services/kcnj13_openfold2/).

The output is a **predicted monomeric structure hypothesis**.
The dummy MSA and absence of a membrane, tetrameric assembly, and bound ligands
limit what it can say about this integral membrane channel. Model confidence
values are not experimental uncertainty and do not establish channel
conductance, gating, pigment pattern, or any organismal phenotype. No
bioelectric simulation parameters are transferred from this structure.

## Reuse in code

`connectors/bio_services/openfold2.py` validates a canonical unwrapped input,
constructs a one-model request under an isolated `frontier/` output prefix,
and checks that a persisted receipt matches the exact sequence hash. It does
not load credentials or perform network calls; callers must use the configured
Nebius MCP client so auth stays in its existing process-only path. Its focused
tests require no network or model runtime.
