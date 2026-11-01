# Nebius: what we used it for

Science Claw Hack @ MIT, Oct 30 – Nov 1, 2026. Everything below is read from repository files named in
each row. Issues: [#4](https://github.com/fractastical/delphi/issues/4) (Nebius integration),
[#51](https://github.com/fractastical/delphi/issues/51) (open-weights builder on Nebius).

Service used: the **Nebius Scientific AI Platform**, through its MCP server (Streamable HTTP). Our
client is `plugins/nebius/nebius_mcp.py` (list tools, read schemas, call a tool) and
`plugins/nebius/fold.py` (structure jobs with content-derived idempotency keys, so a crashed or re-run
script re-attaches to the same operation instead of starting new work). The key lives in
`NEBIUS_SCIENTIFIC_AI_API_KEY` and is never in the repo.

## What ran

### 1. Cell segmentation for three Thompson claims (the headline Nebius result)

| | |
|---|---|
| Tool on Nebius | Cellpose, CPSAM v2 checkpoint |
| Inputs | Eight openly licensed tissue micrographs from Wikimedia Commons (human corneal endothelium, *Aloe* leaf epidermis, moss leaflet, *Drosophila* compound eye, grass leaf epidermis, onion epidermis, corneal tight-junction stain, Arabidopsis section), checksum-verified and cropped by `fetch_inputs.py` |
| Operations | **19 Nebius operations**, one per `cellpose.json`: 8 tissue images + 11 synthetic tilings for the segmenter-bias null (hexagonal lattice, brick wall, random Voronoi and grass-like cell files, at three noise levels). Each record carries the Nebius `operation_id`, the model SHA-256, the Cellpose version and the SHA-256 of the exact input image, so every mask traces to its run |
| Claims tested | `thompson1917-ch07-04` (walls meet three at a time at 120°), `thompson1917-ch07-08` (hexagons regular only where cells are equal in size), `thompson1917-ch07-10` (close-packed cells hexagonal on average) |
| Verdicts | ch07-04 supported for four of five tissues, grass a clear counter-example; ch07-08 supported but a property of any space-filling partition (the random Voronoi control shows it too); ch07-10 confirmed but forced by Euler's formula. After the segmenter-bias null, ch07-04's confidence was cut from 0.60 to 0.35: Cellpose rounds corners toward Y-junctions and pulls even a brick wall toward 120° |
| Where | `claim-sources/cell-geometry/README.md` (pipeline, results tables, verdicts), `results/<tissue>/cellpose.json`, `results/segmenter-bias/`, `test-data/claim-tests/thompson-growth-form/thompson1917-ch07-{04,08,10}/result.json`; three signed evidence nanopubs in `claim-sources/cell-geometry/nanopubs/signed/` carry the Nebius operation IDs; still in `assets/nebius-snapshot.png` |

The segmenter-bias run exists because an outside agent (vina, Moltbook, Oct 31) asked for the null;
it was run on Nebius with the same checkpoint and is the reason the ch07-04 verdict was downgraded
(`COLLABORATIONS.md`).

### 2. Protein structure prediction for three pre-registered Levin tests

| | |
|---|---|
| Tool on Nebius | ESMFold2 (`submit_esmfold` in `plugins/nebius/fold.py`; the client also wraps AlphaFold3 and DiffDock, not used) |
| Tests | `levin-2015-girardia-11` (does octanol engage a planarian gap-junction channel better than hexanol; 2 operations, an innexin octamer), `levin-2018-hcn2-16` (can the GYG→AAA HCN2 construct still co-assemble with wild type; 3 operations), `levin-2019-boundary-14` (do the animal channels for touch, taste, temperature and hearing contain a bacterial channel fold; 18 operations over a panel from `panel.json`, with PIEZO2 at 2,752 aa folded as two overlapping windows because it exceeds GPU memory in one piece) |
| Status | All three are `preregistered` in their `result.json`, with pass and fail criteria committed before any structure was opened. `derived/runs.json` in each folder records the Nebius operation IDs (23 in total). The predicted structures go to the gitignored `data/` directory; **no verdict has been computed yet**, so these are submitted jobs, not results |
| Where | `test-data/claim-tests/levin-papers/levin-20{15-girardia-11,18-hcn2-16,19-boundary-14}/{nebius_run.py,derived/runs.json,result.json}` |

## Wired but not run

- `sim-engine/generative/backends/providers.mjs` has a Nebius inference backend for the design
  studio; with no key in the environment it reports `not configured` (both hosts answer 401
  unauthenticated), recorded in `sim-engine/generative/RESULTS.md` §6.
- Issue #51 proposes running the claim-test *builder* on open-weights models hosted on Nebius, with
  frontier models kept as assessors, to cut the 12-step loop cost by about 85%. It has an acceptance
  test (3 claims, blind frontier audit, cost per loop) and has not been run.

## Beside ours: the sibling project's Nebius record

The collaborating repository `kganjam/delphi-frontier` reports 48 Nebius GPU/CPU jobs (35 completed,
9 failed, 4 cancelled) and 15 scoped model runs (Evo2 7B, OpenFold2, ESM2, OpenMM, BETSE, Morpheus, a
neural CA) in its own build record, crawled into `swarm/frontier/` and summarized in
`swarm/FRONTIER-SUMMARY.md`. Those are their numbers, quoted and not re-verified by us.

## Verification

Operation counts were recounted for this document: 19 distinct `operation_id` values across the 19
`cellpose.json` files under `claim-sources/cell-geometry/results/`, and 2 + 3 + 18 entries in the three
`derived/runs.json` files. Verdicts and confidence changes are quoted from the files named above.
