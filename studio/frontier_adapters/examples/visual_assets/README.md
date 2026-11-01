# Visual-asset chains (glide video, RD video, six printable forms): 47 PROPOSED records, NOT imported

Built by `python -m frontier_adapters.visual_assets --repo . --source-commit d06c24ce6128 --replay-glide --also-records <market + BioModels records>` from git blobs at the
integrated root tip. Namespace `node-a` (rebuild with `--namespace` to change; every version changes). Single-reader (corpus, Claude Sonnet 5.5), not Codex-reviewed, not independently reviewed.

| chain | Claims | compute Action -> Evidence | render/build Action -> Evidence |
|---|---|---|---|
| glide fixed launch | 1 (derived ranges, assumed polar) | sim (reported) + **replay (really run here: 39 numbers identical, exit 0, numpy only)** | render (reported), `context_only` |
| reaction-diffusion cells 1306 and 240 | 2 (model outcomes) | sim rerun (reported), one per cell | render per cell, `context_only`; one video shows both cells |
| six printable forms (A,B,C,N1,N2,N3) | 6 (z3 verdict on declared constraints; A is **unsat**) | solve (reported, evidence_kind `formal`, z3 only) | geometry build, `context_only`: STL, stand STL, GLB, two PNGs |

Rules held: no media Evidence has `supports`; render Actions take the compute Evidence as input; output videos/meshes/images sit only under the render/build Action; every stated hash was recomputed from a blob
(all 52 print-manifest files, mp4/poster/frames/receipt/code); pointers are `urn:sha256`, availability `referenced`, no licence, no URL; printer, resin and slicing stay unknown; glide PNG frames are not in the commit so their three stated hashes are recorded as unverifiable.

`coverage.json`: 75 media files at root tip 42cbd81, 66 tied by sha256, 9 untied (3 more are the newly merged bioelectric/mechanobio media; see sim_bundles), 0 tied as `supports`. Untied: `species-graph.png`, `engineering/simulation/results/figure.png`, and the fin-mechanics MP4/poster (see below).

**Finding.** The fin-mechanics MP4 and poster were re-rendered after market's bundle was imported (commit b33b1d9): the imported render Evidence pins mp4 `f4080da6…` and poster `df0e4804…`, the root tip holds `dbdedba50…` and `becbc217…`.
The imported records are correct for their pinned commit a48399f; they no longer describe the bytes the tip serves. A new render Action/Evidence pinned to the new bytes needs new ids (same ids would fork).
`preflight-dryrun.json`: can_import true, 47 new heads, 0 forks, gates ok (one warning: the replay Evidence has `produced_by` but its artifact is a `log`).
Open design choice for root: z3 results use evidence_kind `formal` (an SMT verdict re-checked by z3 only); `simulated` is the alternative.
