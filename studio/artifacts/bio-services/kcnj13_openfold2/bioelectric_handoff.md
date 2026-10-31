# Kcnj13 structure result for bioelectric model owner

This is a handoff for review, not an instruction to change the bioelectric
model. The only provider operation was Nebius Scientific AI OpenFold2,
`op-5ba1d104dbbcd293`, on the unmodified zebrafish sequence NCBI BAF03613.1 /
UniProt Q0KIZ7 (362 aa; exact sequence SHA-256
`8029209004a52efea91ae2c899c017ed4795a843615b4b272c7087c67ba396b2`).

The returned monomer has provider ranking confidence / mean pLDDT 52.86,
pTM 0.273, and mean PAE 22.91 Å. It was generated with a dummy single-sequence
MSA and no external template. It has no membrane, tetramer, or bound ligands.
The provider reported `upstream-source-not-nim`; it did not identify the
physical accelerator. This is a weak structural hypothesis, not a conductance
measurement or channel state.

Please assess whether the current bioelectric port should simply list Kcnj13
as an unparameterized, unverified channel candidate with conductance/gating
unknown. This structure provides no basis to set conductance, reversal
potential, gating kinetics, copy number, or a pigment-cell phenotype. Do not
transfer any numeric parameter from the structure prediction. The RefSeq
NP_001429136.1 variant 4 differs by four N-terminal residues and remains an
explicit source discrepancy in the adjacent source manifest.

Artifacts: `rank1.pdb`, `metrics.json`, and `operation_receipt.json` in this
directory. The full source sequence packet is in
`../kcnj13_source/source_manifest.json`.
