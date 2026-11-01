# MorphoLib / MorphoEval import (first slice)

Worker: MorphoLib/MorphoEval integration (single reader, not Codex-reviewed, not independently reviewed). Branch `work/morpholib-import`.
Code: `frontier_adapters/morpholib.py`. Tests: `frontier_adapters/tests/test_morpholib.py`. Frozen output: `frontier_adapters/examples/morpholib_import/`.

## Current-state inventory (read 2026-10-31)

| Item | What was read | Read level |
|---|---|---|
| Upstream `fractastical/morpholib` | `origin/main` = `35d30f4cfd5397ee1ed769f96494e018603e293d`, committed 2026-10-31 14:28 -0400; 46 commits after the `6f87731` of the 2026-10-28 audit; blobless clone `/data/worktrees/reference/morpholib-20261028` fetched | `git rev-parse`, blobs read with `git cat-file` |
| Licence | `LICENSE` blob: MIT, (c) 2026 Joel Dietz. GitHub API says `NOASSERTION` for the licence field (it does not parse the file). Embedded third-party images carry their own licences (stated per specimen in each reference dataset) | full-text of `LICENSE` |
| Branches | 147 on origin, many `cursor/<species>-turing-wavelength-*`; none read | listing (count only) |
| Related repos under the same owner (GitHub API listing, none read) | `delphi` (no licence field), `project-delphi-ontology` (MIT), `project-delphi-loop`, `bioelectricity-knowledge-graph`, `probknow-nanopub-builders` (MIT), `nanopub-ts` (MIT), `fractastical.github.io` | listing |
| Upstream audit | `morphoeval/runs/science_provenance_audit.json`: 1,027 loops classified, Tier A 25, Tier B 992, Tier C 10 (upstream's statement); `lean_proof_audit.json`: 1,037 Lean files, 920 template-trivial, 117 substantive; `tier_c_deletion_manifest.json`: 8,986 loops deleted | full-text of those three JSON files |
| `models/*.py` | 1,044 files at the top level of `models/` | listing |

The 2026-10-28 research report (`docs/research/morpholib-spec-coverage.md`, at `6f87731`) is an old-state hypothesis; the Tier A numbers above agree with it, and nothing else in it was relied on.

## What was imported

The 25 loops that upstream's own audit counts as Tier A ("the paper is extracted AND the literature was actually scouted"). Tier B and C are not imported; they appear as counts in `exclusions.json` and as names in `filename_index.jsonl`.

Per model:
- **Claim** (`origin: source_statement`): the governing equations upstream's math_kg spec attributes to the paper, with upstream's own citation, code locus and Lean locus per equation. A claim about a source; Frontier did not check the paper.
- **Evidence** (`source_assessment`, relation `context_only`): upstream's MorphoEval assessment (latest version), score history across versions, nanopub flags, mechanical Lean flags. `independent_of_claim: false`: the assessor is a language model working for the script's author.
- **Problem** (`recorded`): the assessor's remediation list, quoted in full. 23 of 25 models have one; two have no remediation items in their latest assessment, so no Problem is written for them.
- **Artifacts** (store `ArtifactRef`, `urn:sha256`, availability `referenced`): model script, math_kg spec, reference dataset, Lean source, signed and unsigned assessment, specimen/reference files. The judged comparison PNG named in each assessment is `unavailable`: it is not in the pinned tree and no commit in upstream history adds it, so its digest is the one the assessment states and was not recomputed.

Side files: `models_index.json` (source-index metadata, one row per model), `equations.jsonl` (116 equations as mathematical representations with Lean text and mechanical flags), `filename_index.jsonl` (all `models/*.py`, year/author/slug parsed from the file name, a parse and not a validated mapping), `exclusions.json`.

## Counts, kept apart (`chain.json` `counts`)

25 unique models; 25 Claims = 25 Claim versions; 25 Evidence; 23 Problems; 0 Actions (nothing was executed). 116 equations as mathematical representations, all with Lean text, **0 compiled by Frontier, 0 counted as proof**. 9 of them have only trivial tactics (`decide`, `rfl`, `omega`, `trivial`) in the declared range and are flagged, not credited. 228 artifact references (203 `referenced`, 25 `unavailable`), 10,014,285 bytes hashed by the adapter (referenced only), 0 bytes available through the store. 25 nanopub assessments with a signature block present; **0 signature checks, 0 registry checks**. 17 distinct organism strings as stated in the audit file (not a taxon mapping).

## What is not claimed

- Scores describe how closely a script matches its cited source, not whether the source is right.
- `signature_block_present` is a text check. `signature_verified` and `published` are `unknown`; dx-submit owns that check.
- The scale of each model (`SCALES`) is assigned by this adapter's author, tagged `scale-assignment:adapter-curated`.
- For 9 models the reference dataset has no `metadata.sources` entry for the audit's DOI, so the citation comes from the spec's `model_spec.model`, said in the Claim. For `bailleul-allometric-cranial-sutures` the file name says 2020, the audit's DOI and the spec cite Miura et al. (2009); the Claim records the file name as upstream's own label.
- Not run: upstream model scripts, Lean, nanopub verification, SPEC-009's anti-triviality gate (parameter reference, mutated-law failure).

## Reproduce

```
systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 \
  env PYTHONPATH=. python3 -m frontier_adapters.morpholib --repo <morpholib clone> --source-commit 35d30f4cfd5397ee1ed769f96494e018603e293d --out <dir>
```
Same input gives the same bytes (checked by running twice and by a test that rebuilds the committed freeze).
