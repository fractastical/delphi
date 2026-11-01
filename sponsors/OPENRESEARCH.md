# OpenResearch (alphaXiv): what we used it for

Science Claw Hack @ MIT, Oct 30 – Nov 1, 2026. OpenResearch is NVIDIA's research-agent tool, reached
through alphaXiv's official `orx` CLI (version 0.2.23, installed 2026-10-31 from openresearch.sh).
Everything below is read from repository files named in each row. Issues:
[#16](https://github.com/fractastical/delphi/issues/16) (orx as the research-agent harness),
[#10](https://github.com/fractastical/delphi/issues/10) (alphaXiv).

## The role it plays in the pipeline

`AGENTS.md`, role **A2 Source attestor**, makes an OpenResearch literature run a **release
requirement**: before a claim is formalized or tested, it must carry a logged `orx` run recording what
the modern literature says about it and whether prior work already answers it. The reason is stated
there: the biggest credibility risk in this project is restating a historical claim as though nobody
had studied it since. A claim the literature already answers gets a citation, not an experiment.
`dashboard/compliance.mjs` counts the OpenResearch records per role on the dashboard.

## What ran

All runs use `orx discover <source> "<query>"` against OpenAlex, PubMed and the alphaXiv corpus.
`orx discover` is a stateless retrieval primitive and issues **no run or experiment identifier**; every
record therefore carries `run_identifier: null` rather than an invented one, and the exact command, UTC
time, exit code and returned records are the reproducible log. Every call was made with
`--no-telemetry`, and `NCBI_EMAIL` was unset after a research agent once sent the project lead's email
as an etiquette parameter (now prohibited, `AGENTS.md`).

| Use | Runs | Finding | Where |
|---|---:|---|---|
| Literature grounding of six headline claim tests (Kimura heterozygosity, Maynard Smith hitchhiking, Thompson ch03-07 and ch04-13, Darwin ch09-03 and ch11-13) | 6 claims, OpenAlex + PubMed per claim | **5 of 6 were already answered by prior work**; the sixth (Thompson weight-for-height) partly. The tests are therefore reproductions and the open question is recorded per claim | `test-data/claim-tests/openresearch/README.md`, `run.mjs`, `assessments.mjs`; per claim `test-data/claim-tests/<project>/<claim>--delphi-claims/openresearch.json` |
| Prior art for the organism-design idea ("a layered, ontology-based, formally checked organism") | 59 `orx discover` calls, plus Europe PMC, DOI checks | Each part has been done (Uberon, Phenoscape, Human Reference Atlas, whole-cell models, Lean on the genetic code); the combination has not. Phenoscape is the closest prior work and must be cited. "First formal verification of biology" is **not** a supportable claim | `research/prior-art/REPORT.md`, `SEARCHES.md`, `works.json` |
| Physics thread: flying-fish gliding, take-off, fin allometry | 9 `orx discover` calls | OpenAlex rate-limited 6 of 7 calls (HTTP 429) because the prior-art run had used the same route minutes earlier; discovery moved to Europe PMC, with every call logged | `physics/PRIOR-ART.md`, `physics/SEARCHES.md` |
| Building the open-problems catalogue | 12 `orx discover` runs (OpenAlex and PubMed, six queries each) | 20 problems from screened abstracts, 12 via Pelabon et al. 2025 and 9 via Solé et al. 2024, both found through orx; coverage is weighted toward evolution and organism design because the queries were | `open-problems/SOURCES.md` §3 |

Rule applied throughout (`AGENTS.md`, standing order on ideas): citations come only from searches that
returned them. `assessments.mjs` refuses to write any identifier its runs did not return.

## What it changed

- Six headline tests are presented as reproductions of settled results, with the open part named,
  instead of as discoveries.
- The pitch cites Phenoscape, Uberon, the Cell Ontology, the Human Reference Atlas and Daane 2021, and
  claims only "we did not find prior use of a proof assistant on an ontology-derived anatomy hierarchy".
- The sister project `kganjam/delphi-evolve` reported the same effect from its own OpenResearch-style
  pass (ALDE, LazySP, Bayesian Active Edge Evaluation already covered parts of its method); quoted from
  issue #16, not re-verified here.

## What we did not do

- No `orx` experiment or compute run (the auto-research side of OpenResearch): only `orx discover`.
- alphaXiv GPU credits (#10) were not used.
- Grounding covers the six headline tests, the organism-design idea, the physics thread and the
  open-problems catalogue, not every one of the 174 tested claims.
