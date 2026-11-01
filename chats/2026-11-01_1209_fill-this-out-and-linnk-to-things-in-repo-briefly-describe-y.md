# fill this out and linnk to things in repo == ### Briefly describe your project a

- **Started:** 2026-11-01 12:09 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 12:30 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 9
- **Subagents:** 0
- **Transcript ID:** `1ca0cde7-9f15-4ea6-91b2-f81b41a3aafd`

## Conversation

### 2026-11-01 12:09 — Turn 1 (User)

> fill this out and linnk to things in repo 
> ==
> ### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).
> 
> TBD
> 
> ### Provide the URL of your public, open-source GitHub repository.
> 
> TBD
> 
> ### Provide a link to your slide deck.
> 
> TBD
> 
> ### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).
> 
> TBD
> 
> ### If you would like to be considered for the Formlabs prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD
> 
> ### If you would like to be considered for the Alphaxiv prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD
> 
> ### If you would like to be considered for the Nebius prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD
> 
> ### If you would like to be considered for the NVIDIA ALCHEMI prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD
> 
> ### If you would like to be considered for the NVIDIA BioNeMo prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD
> 
> ### If you would like to be considered for the NVIDIA Platform General prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD
> 
> ### If you would like to be considered for the E14 50K Prize explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.
> 
> TBD

**Assistant:**

I'll gather the facts from the repo first so every answer links to real files and numbers.

I need to fill out a hackathon submission form linking to repo contents, so I should gather facts first: README stats, repo URL, slide deck, demo site, plugins used, and various integrations like OpenResearch, Formlabs, BioNeMo. Let me explore the repo efficiently to collect these details.

The `sponsors/` folder is exactly what I need. Reading those plus the related READMEs.

I need to figure out which deck PDF is current, find demo materials, and check whether the README mentions E14 Fund or the sponsor prize, since that's likely tied to startup commercialization. I should also look at the fittest plugin README to see if it connects to ALCHEMI's focus.

Everything below is drawn from `README.md`, `sponsors/*.md`, and the files they cite. Word counts are within limits. Two sections (ALCHEMI, BioNeMo) are honest about work that was proposed or refused rather than run; I'd suggest leaving ALCHEMI blank, but drafted it in case you want it.

---

### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).

DELPHI (Distributed Epistemic Layer for Probabilistic Hypothesis Inference) searches for fundamental laws of biology: statements general enough to hold across organisms and scales, stated precisely enough to test. Biology has thousands of candidate "laws" scattered across books and papers, with no shared record of which are mathematical consequences of their assumptions, which are empirical regularities, and which have been refuted. We extract candidate laws as claims traced to their sources (Darwin, D'Arcy Thompson, Wolfram, Levin, Aristotle, mathematical biologists), formalize them where possible as Lean 4 theorems, test them against organism data under pre-registered pass/fail criteria, gate each test through an independent faithfulness assessor from a different model provider, and publish every claim, test and assessment as a citable nanopublication. Current state ([README](https://github.com/fractastical/delphi#current-numbers)): 1,763 claims, 880 live nanopubs, 91 theorems (73 Lean-checked), 174 claims tested against data (93 supported, 30 refuted, 37 mixed, 14 inconclusive). Agents query all of it over a hosted MCP server.

### Provide the URL of your public, open-source GitHub repository.

https://github.com/fractastical/delphi

### Provide a link to your slide deck.

- PDF: https://github.com/fractastical/delphi/blob/main/assets/hackathon-deck-4.pdf
- Live, data-driven deck (unevidenced slides greyed out): https://delphi-mission-control.ashenoy000.workers.dev/deck/

### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

- Site: https://delphibio.org (team page tour: https://delphibio.org/team.html)
- MCP server for agents, no auth: `https://mcp.delphibio.org/mcp` (`claude mcp add --transport http delphisci https://mcp.delphibio.org/mcp`)
- Mission control dashboard: https://delphi-mission-control.ashenoy000.workers.dev/start/ — knowledge graph, Claim Book, design studio ([Perturb & optimise](https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb))
- Agent forum: https://forum.delphibio.org
- Animated walkthroughs: [`assets/delphi-summary.gif`](https://github.com/fractastical/delphi/blob/main/assets/delphi-summary.gif), [`assets/overnight-nov1.gif`](https://github.com/fractastical/delphi/blob/main/assets/overnight-nov1.gif)

(No recorded video exists in the repo; if you record one, add the link here.)

### Formlabs prize (maximum 250 words)

We used Formlabs SLA to put a mathematical model next to the real thing. Two 140 mm hindwings of the dragonfly *Arigomphus villosipes* were printed on the hackathon's printers (0.6 mm membrane, 1.5 mm main veins): one carries the vein network segmented from a photograph of the real wing (442 closed cells); the other regenerates the cross veins with the Hoffmann et al. 2018 (*PNAS* 115:9905) inhibitory-centre/Voronoi rule (480 cells). Hoffmann's claim is that the model looks like the real wing; the prints put that claim in a judge's hand. Record: [issue #58](https://github.com/fractastical/delphi/issues/58), photo [`assets/arigomphus-wing.jpg`](https://github.com/fractastical/delphi/blob/main/assets/arigomphus-wing.jpg), README section [The wings](https://github.com/fractastical/delphi#the-wings-a-model-next-to-the-real-thing), where each wing design decision is tagged as a Lean-proved claim (hollow spar `thompson1917-ch16-03`, wall thickness `ch16-04`), a data-tested one, or open.

Several copies of a flying zebrafish ([`fabrication/flying-zebrafish/`](https://github.com/fractastical/delphi/tree/main/fabrication/flying-zebrafish)) were also printed, designed by a six-agent swarm to a shared Form 3/4 spec (0.6 mm minimum feature, STL+3MF, mesh verified watertight).

Designed to Formlabs specifications but not yet printed: a 71-file winged-zebrafish anatomy kit in Tough 2000 (0.5 mm walls, D-keyed press-fit pegs, Blender-verified; [`anatomy-model/print/`](https://github.com/fractastical/delphi/tree/main/anatomy-model/print), viewer at `/print/`), and a [pre-registered printed test](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-bilayer-curvature/printed-bilayer-01) of a Lean-proved bilayer-curvature law, whose curvature is predicted before the strip is built.

What we did not do: no measured print-vs-design agreement yet; the PreForm API path was documented, not exercised. Full record: [`sponsors/FORMLABS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/FORMLABS.md).

### Alphaxiv prize (maximum 250 words)

OpenResearch via the official `orx` CLI is a release requirement in our pipeline, not an enrichment. [`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md) role A2 (Source attestor) says no claim may be formalized or tested until it carries a logged `orx discover` run recording what the modern literature says and whether prior work already answers it. The reason: the biggest credibility risk in a project restating Darwin and Thompson is pretending nobody has studied the question since.

What it changed, all logged with command, UTC time, exit code and returned records:

- Six headline claim tests (Kimura, Maynard Smith hitchhiking, two Thompson, two Darwin): **5 of 6 were already answered by prior work**, so they are reported as reproductions with the open part named ([`test-data/claim-tests/openresearch/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/openresearch)).
- A 59-search prior-art report on "a layered, ontology-based, formally checked organism" found Phenoscape, Uberon, the Human Reference Atlas and whole-cell models; it ruled out "first formal verification of biology" as a claim we may make ([`research/prior-art/REPORT.md`](https://github.com/fractastical/delphi/blob/main/research/prior-art/REPORT.md), `SEARCHES.md`).
- The flying-fish physics thread ([`physics/PRIOR-ART.md`](https://github.com/fractastical/delphi/blob/main/physics/PRIOR-ART.md)) and the 20-problem open-problems catalogue ([`open-problems/SOURCES.md`](https://github.com/fractastical/delphi/blob/main/open-problems/SOURCES.md)).

Rule applied throughout: citations come only from searches that returned them; `assessments.mjs` refuses to write an identifier its runs did not return, and `orx discover` issues no run ID so we record `run_identifier: null` rather than inventing one. The dashboard counts OpenResearch records per role (`dashboard/compliance.mjs`).

Not done: no `orx` experiment/compute runs, only `orx discover`. Record: [`sponsors/OPENRESEARCH.md`](https://github.com/fractastical/delphi/blob/main/sponsors/OPENRESEARCH.md).

### Nebius prize (maximum 250 words)

The Nebius Scientific AI Platform, reached through its MCP server, produced our most instructive data verdicts. Client: [`plugins/nebius/`](https://github.com/fractastical/delphi/tree/main/plugins/nebius) (`nebius_mcp.py`, `fold.py` with content-derived idempotency keys so re-runs re-attach to the same operation).

**Cell segmentation, 19 operations (Cellpose CPSAM v2).** Eight openly licensed tissue micrographs plus eleven synthetic tilings were segmented to test three of D'Arcy Thompson's cell-packing claims: walls meet three at a time at 120° (`thompson1917-ch07-04`), hexagons regular only where cells are equal in size (`ch07-08`), close-packed cells hexagonal on average (`ch07-10`). Every mask carries its Nebius `operation_id`, model SHA-256 and input hash. Verdicts: ch07-04 supported in four of five tissues with grass as a clear counter-example; ch07-08 supported but true of any space-filling partition (the random-Voronoi control shows it); ch07-10 confirmed but forced by Euler's formula. The synthetic null, requested by an outside agent on Moltbook, showed Cellpose pulls even a brick wall toward 120°, and cut ch07-04's confidence from 0.60 to 0.35. Record: [`claim-sources/cell-geometry/README.md`](https://github.com/fractastical/delphi/blob/main/claim-sources/cell-geometry/README.md); three signed evidence nanopubs carry the operation IDs.

**Protein structure, 23 ESMFold2 operations** for three pre-registered Levin tests (planarian innexin octamer, HCN2 GYG→AAA co-assembly, an 18-protein channel panel with PIEZO2 folded in two windows). Criteria were committed before any structure was opened; verdicts are not yet computed, so these are submitted jobs, not results ([`test-data/claim-tests/levin-papers/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/levin-papers)).

Record: [`sponsors/NEBIUS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NEBIUS.md).

### NVIDIA ALCHEMI prize (maximum 250 words)

*Recommendation: leave blank. ALCHEMI was proposed, not run. Draft if you want to submit anyway:*

We did not run ALCHEMI during the hackathon and say so. [Issue #13](https://github.com/fractastical/delphi/issues/13) proposes the pairing we think ALCHEMI is for in this project: screen a candidate structure with the Batched Geometry Relaxation NIM, print it with Formlabs through the PreForm API, and publish both steps as linked nanopublications so the simulated and fabricated object share one provenance chain. That design exists; the run does not.

The nearest work that did run is in the same domain of trust in ML interatomic potentials: [`plugins/fittest/`](https://github.com/fractastical/delphi/tree/main/plugins/fittest) sends PubChem conformers of alanine, lactic acid and glyceraldehyde (with mirror images, rotations and stretched bonds) through a router over MACE-MPA-0, AIMNet2 and Orb-v3, and found that Orb-v3 is not exactly equivariant (1–6 meV mirror asymmetry) and that stretched bonds stay "trusted" on a handful of DFT labels. We then applied the same trust-or-escalate rule to our own assessor truth scores (`route.py`). This is context for claim `thompson1917-ch09-03` on molecular asymmetry, and it is not an ALCHEMI result. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md), "What we did not use".

### NVIDIA BioNeMo prize (maximum 250 words)

Our BioNeMo record is a documented refusal plus wired-but-unexercised integrations, and we present it as that. On Oct 30 all 27 NVIDIA-BioNeMo repositories were reviewed for fit ([issue #14](https://github.com/fractastical/delphi/issues/14)); `bionemo-agent-toolkit` was the best match, and the proposal to make BioNeMo an agent harness was rejected in architecture review ([#17](https://github.com/fractastical/delphi/issues/17)) as backwards: BioNeMo is a model service, not where an agent lives.

The hosted ESMFold NIM was called on bovine albumin (UniProt P02769, checksummed input) and returned HTTP 401, because the key available to the session was a Brev key, not an `nvapi-` NIM key. Rather than discard this, we recorded it as a run with `status: "refused"` ([`organism-design/esmfold/runs/P02769/result.json`](https://github.com/fractastical/delphi/blob/main/organism-design/esmfold/runs/P02769/result.json)) and as two unsigned nanopub drafts, following our rule that a documented refusal is a micro-discovery another team can cite. The fallback ESM Atlas runs for cytochrome c are labelled as not NVIDIA runs.

ProteinMPNN, RFdiffusion, Evo2 and ESMFold NIMs are wired into the organism design studio ([`sim-engine/generative/backends/protein.mjs`](https://github.com/fractastical/delphi/blob/main/sim-engine/generative/backends/protein.mjs)); without a key the protein level reports `not configured` and zero candidates, and tests confirm a bogus key reads as `auth failed` with no key leak (`sim-engine/generative/RESULTS.md` §6). No NIM payload has run against a live key.

Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### NVIDIA Platform General prize (maximum 250 words)

An NVIDIA Brev instance (`delphi-gpu`, L40S 46 GB) served Qwen3-32B (AWQ 4-bit) with vLLM 0.32 as a self-hosted claim assessor, scoring all **566 claims** of the Aristotle biology project for dataset resolvability, one JSON-schema-constrained request per claim at about one claim per second (concurrency 24). This matters structurally, not just as compute: our pipeline rule is *assessor ≠ builder* with at least two assessor providers, and an open-weights model on our own GPU is a provider no frontier-API builder shares, at zero per-token cost. Setup, serve and tunnel commands: [`scripts/assess/README.md`](https://github.com/fractastical/delphi/blob/main/scripts/assess/README.md); runner `run-assessor.mjs`; assessor record in [`claim-sources/aristotle-biology/assessment/assessors.json`](https://github.com/fractastical/delphi/blob/main/claim-sources/aristotle-biology/assessment/assessors.json); outputs merged into `assessments.json`. The 566 count is the number of entries carrying the `qwen` assessor in that file.

Around it: the BioNeMo ESMFold NIM call recorded as a refusal, four NIM protein-design backends wired into the design studio behind `NVIDIA_API_KEY`, and the OpenResearch (NVIDIA research agent via alphaXiv `orx`) literature grounding made a release requirement (see the Alphaxiv answer). Together these cover the three legs of the platform we touched: GPU serving, model NIMs and the research agent.

Not used: DGX Spark, ALCHEMI. The all-atom MD of kcnk5b (`md/kcnk5b/`) ran on a university cluster and is explicitly not counted as an NVIDIA contribution. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### E14 50K Prize (maximum 250 words)

DELPHI is infrastructure, and infrastructure is what outlives a hackathon. The problem is that biology's candidate laws have no shared, machine-readable ledger of what is proved, tested, refuted or merely restated; every lab and every AI agent rediscovers the same questions. Our answer is a public, open, citable layer that agents and people both read: 1,763 claims, 880 signed nanopublications on the production registry, 91 theorems (73 Lean-checked), 174 pre-registered data tests with verdicts, all served through a hosted MCP endpoint (`mcp.delphibio.org/mcp`) that any Claude, Cursor or ChatGPT user can add in one line.

Adoption already happened during the event: two sibling repositories by an outside team ([delphi-evolve](https://github.com/kganjam/delphi-evolve), [delphi-frontier](https://github.com/kganjam/delphi-frontier)) imported 1,326 claim versions through our MCP server, visible as 30 sessions in our log ([`COLLABORATIONS.md`](https://github.com/fractastical/delphi/blob/main/COLLABORATIONS.md)); an outside agent on Moltbook requested a control that changed one of our verdicts.

We measured rather than asserted the multi-agent story: on 20 pre-registered test plans, every multi-agent arm beat a single agent by at least 4 of 20 verified datasets, the arms were indistinguishable from each other, and the single agent cost a fifth to a tenth as much ([`test-data/agent-comparison/SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/test-data/agent-comparison/SUMMARY.md)). We report nulls in the headline.

The path forward: the claim–test–assess–publish harness ([`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md), thirteen roles with contracts) generalizes to any field with a literature and data, and the design studio ([`sim-engine/`](https://github.com/fractastical/delphi/tree/main/sim-engine)) shows the same ledger constraining engineering. What is not established: no wet-lab work, and no claim promoted to a law of biology.

---

Two things to check before submitting: whether `assets/hackathon-deck-4.pdf` is the deck you want judges to see (it is the most recent; `hackathon-deck.pdf` is older), and whether to include the ALCHEMI section at all, since nothing ran.

Since the E14 Fund focuses on venture potential, I should frame this honestly around the platform itself—the MCP server and nanopub infrastructure as reusable research infrastructure. I'll reference the latest hackathon deck and the live demo sites for support.

For ALCHEMI, nothing's actually been run yet—the closest real result is the fittest work on interatomic potentials plus the proposal outlined in #13, so I'll draft honest text noting it's proposed-but-not-run while flagging that leaving it blank might be the safer choice. I'll keep each section under the word limits and present everything as markdown directly in chat with GitHub links pointing to the actual repo paths.

_Tools used: Read ×6, Shell ×3_

### 2026-11-01 12:11 — Turn 2 (User)

> i need the markdown

### 2026-11-01 12:11 — Turn 3 (User)

> i need the markdown

**Assistant:**

````markdown
### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).

DELPHI (Distributed Epistemic Layer for Probabilistic Hypothesis Inference) searches for fundamental laws of biology: statements general enough to hold across organisms and scales, stated precisely enough to test. Biology has thousands of candidate "laws" scattered across books and papers, with no shared record of which are mathematical consequences of their assumptions, which are empirical regularities, and which have been refuted. We extract candidate laws as claims traced to their sources (Darwin, D'Arcy Thompson, Wolfram, Levin, Aristotle, mathematical biologists), formalize them where possible as Lean 4 theorems, test them against organism data under pre-registered pass/fail criteria, gate each test through an independent faithfulness assessor from a different model provider, and publish every claim, test and assessment as a citable nanopublication. Current state ([README](https://github.com/fractastical/delphi#current-numbers)): 1,763 claims, 880 live nanopubs, 91 theorems (73 Lean-checked), 174 claims tested against data (93 supported, 30 refuted, 37 mixed, 14 inconclusive). Agents query all of it over a hosted MCP server.

### Provide the URL of your public, open-source GitHub repository.

https://github.com/fractastical/delphi

### Provide a link to your slide deck.

- PDF: https://github.com/fractastical/delphi/blob/main/assets/hackathon-deck-4.pdf
- Live, data-driven deck (unevidenced slides greyed out): https://delphi-mission-control.ashenoy000.workers.dev/deck/

### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

- Site: https://delphibio.org (team page tour: https://delphibio.org/team.html)
- MCP server for agents, no auth: `https://mcp.delphibio.org/mcp` (`claude mcp add --transport http delphisci https://mcp.delphibio.org/mcp`)
- Mission control dashboard: https://delphi-mission-control.ashenoy000.workers.dev/start/ — knowledge graph, Claim Book, design studio ([Perturb & optimise](https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb))
- Agent forum: https://forum.delphibio.org
- Animated walkthroughs: [`assets/delphi-summary.gif`](https://github.com/fractastical/delphi/blob/main/assets/delphi-summary.gif), [`assets/overnight-nov1.gif`](https://github.com/fractastical/delphi/blob/main/assets/overnight-nov1.gif)

### If you would like to be considered for the Formlabs prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We used Formlabs SLA to put a mathematical model next to the real thing. Two 140 mm hindwings of the dragonfly *Arigomphus villosipes* were printed on the hackathon's printers (0.6 mm membrane, 1.5 mm main veins): one carries the vein network segmented from a photograph of the real wing (442 closed cells); the other regenerates the cross veins with the Hoffmann et al. 2018 (*PNAS* 115:9905) inhibitory-centre/Voronoi rule (480 cells). Hoffmann's claim is that the model looks like the real wing; the prints put that claim in a judge's hand. Record: [issue #58](https://github.com/fractastical/delphi/issues/58), photo [`assets/arigomphus-wing.jpg`](https://github.com/fractastical/delphi/blob/main/assets/arigomphus-wing.jpg), README section [The wings](https://github.com/fractastical/delphi#the-wings-a-model-next-to-the-real-thing), where each wing design decision is tagged as a Lean-proved claim (hollow spar `thompson1917-ch16-03`, wall thickness `ch16-04`), a data-tested one, or open.

Several copies of a flying zebrafish ([`fabrication/flying-zebrafish/`](https://github.com/fractastical/delphi/tree/main/fabrication/flying-zebrafish)) were also printed, designed by a six-agent swarm to a shared Form 3/4 spec (0.6 mm minimum feature, STL+3MF, mesh verified watertight).

Designed to Formlabs specifications but not yet printed: a 71-file winged-zebrafish anatomy kit in Tough 2000 (0.5 mm walls, D-keyed press-fit pegs, Blender-verified; [`anatomy-model/print/`](https://github.com/fractastical/delphi/tree/main/anatomy-model/print), viewer at `/print/`), and a [pre-registered printed test](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-bilayer-curvature/printed-bilayer-01) of a Lean-proved bilayer-curvature law, whose curvature is predicted before the strip is built.

What we did not do: no measured print-vs-design agreement yet; the PreForm API path was documented, not exercised. Full record: [`sponsors/FORMLABS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/FORMLABS.md).

### If you would like to be considered for the Alphaxiv prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

OpenResearch via the official `orx` CLI is a release requirement in our pipeline, not an enrichment. [`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md) role A2 (Source attestor) says no claim may be formalized or tested until it carries a logged `orx discover` run recording what the modern literature says and whether prior work already answers it. The reason: the biggest credibility risk in a project restating Darwin and Thompson is pretending nobody has studied the question since.

What it changed, all logged with command, UTC time, exit code and returned records:

- Six headline claim tests (Kimura, Maynard Smith hitchhiking, two Thompson, two Darwin): **5 of 6 were already answered by prior work**, so they are reported as reproductions with the open part named ([`test-data/claim-tests/openresearch/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/openresearch)).
- A 59-search prior-art report on "a layered, ontology-based, formally checked organism" found Phenoscape, Uberon, the Human Reference Atlas and whole-cell models; it ruled out "first formal verification of biology" as a claim we may make ([`research/prior-art/REPORT.md`](https://github.com/fractastical/delphi/blob/main/research/prior-art/REPORT.md), `SEARCHES.md`).
- The flying-fish physics thread ([`physics/PRIOR-ART.md`](https://github.com/fractastical/delphi/blob/main/physics/PRIOR-ART.md)) and the 20-problem open-problems catalogue ([`open-problems/SOURCES.md`](https://github.com/fractastical/delphi/blob/main/open-problems/SOURCES.md)).

Rule applied throughout: citations come only from searches that returned them; `assessments.mjs` refuses to write an identifier its runs did not return, and `orx discover` issues no run ID so we record `run_identifier: null` rather than inventing one. The dashboard counts OpenResearch records per role (`dashboard/compliance.mjs`).

Not done: no `orx` experiment/compute runs, only `orx discover`. Record: [`sponsors/OPENRESEARCH.md`](https://github.com/fractastical/delphi/blob/main/sponsors/OPENRESEARCH.md).

### If you would like to be considered for the Nebius prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

The Nebius Scientific AI Platform, reached through its MCP server, produced our most instructive data verdicts. Client: [`plugins/nebius/`](https://github.com/fractastical/delphi/tree/main/plugins/nebius) (`nebius_mcp.py`, `fold.py` with content-derived idempotency keys so re-runs re-attach to the same operation).

**Cell segmentation, 19 operations (Cellpose CPSAM v2).** Eight openly licensed tissue micrographs plus eleven synthetic tilings were segmented to test three of D'Arcy Thompson's cell-packing claims: walls meet three at a time at 120° (`thompson1917-ch07-04`), hexagons regular only where cells are equal in size (`ch07-08`), close-packed cells hexagonal on average (`ch07-10`). Every mask carries its Nebius `operation_id`, model SHA-256 and input hash. Verdicts: ch07-04 supported in four of five tissues with grass as a clear counter-example; ch07-08 supported but true of any space-filling partition (the random-Voronoi control shows it); ch07-10 confirmed but forced by Euler's formula. The synthetic null, requested by an outside agent on Moltbook, showed Cellpose pulls even a brick wall toward 120°, and cut ch07-04's confidence from 0.60 to 0.35. Record: [`claim-sources/cell-geometry/README.md`](https://github.com/fractastical/delphi/blob/main/claim-sources/cell-geometry/README.md); three signed evidence nanopubs carry the operation IDs.

**Protein structure, 23 ESMFold2 operations** for three pre-registered Levin tests (planarian innexin octamer, HCN2 GYG→AAA co-assembly, an 18-protein channel panel with PIEZO2 folded in two windows). Criteria were committed before any structure was opened; verdicts are not yet computed, so these are submitted jobs, not results ([`test-data/claim-tests/levin-papers/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/levin-papers)).

Record: [`sponsors/NEBIUS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NEBIUS.md).

### If you would like to be considered for the NVIDIA ALCHEMI prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We did not run ALCHEMI during the hackathon and say so. [Issue #13](https://github.com/fractastical/delphi/issues/13) proposes the pairing we think ALCHEMI is for in this project: screen a candidate structure with the Batched Geometry Relaxation NIM, print it with Formlabs through the PreForm API, and publish both steps as linked nanopublications so the simulated and fabricated object share one provenance chain. That design exists; the run does not.

The nearest work that did run is in the same domain of trust in ML interatomic potentials: [`plugins/fittest/`](https://github.com/fractastical/delphi/tree/main/plugins/fittest) sends PubChem conformers of alanine, lactic acid and glyceraldehyde (with mirror images, rotations and stretched bonds) through a router over MACE-MPA-0, AIMNet2 and Orb-v3, and found that Orb-v3 is not exactly equivariant (1–6 meV mirror asymmetry) and that stretched bonds stay "trusted" on a handful of DFT labels. We then applied the same trust-or-escalate rule to our own assessor truth scores (`route.py`). This is context for claim `thompson1917-ch09-03` on molecular asymmetry, and it is not an ALCHEMI result. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md), "What we did not use".

### If you would like to be considered for the NVIDIA BioNeMo prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

Our BioNeMo record is a documented refusal plus wired-but-unexercised integrations, and we present it as that. On Oct 30 all 27 NVIDIA-BioNeMo repositories were reviewed for fit ([issue #14](https://github.com/fractastical/delphi/issues/14)); `bionemo-agent-toolkit` was the best match, and the proposal to make BioNeMo an agent harness was rejected in architecture review ([#17](https://github.com/fractastical/delphi/issues/17)) as backwards: BioNeMo is a model service, not where an agent lives.

The hosted ESMFold NIM was called on bovine albumin (UniProt P02769, checksummed input) and returned HTTP 401, because the key available to the session was a Brev key, not an `nvapi-` NIM key. Rather than discard this, we recorded it as a run with `status: "refused"` ([`organism-design/esmfold/runs/P02769/result.json`](https://github.com/fractastical/delphi/blob/main/organism-design/esmfold/runs/P02769/result.json)) and as two unsigned nanopub drafts, following our rule that a documented refusal is a micro-discovery another team can cite. The fallback ESM Atlas runs for cytochrome c are labelled as not NVIDIA runs.

ProteinMPNN, RFdiffusion, Evo2 and ESMFold NIMs are wired into the organism design studio ([`sim-engine/generative/backends/protein.mjs`](https://github.com/fractastical/delphi/blob/main/sim-engine/generative/backends/protein.mjs)); without a key the protein level reports `not configured` and zero candidates, and tests confirm a bogus key reads as `auth failed` with no key leak (`sim-engine/generative/RESULTS.md` §6). No NIM payload has run against a live key.

Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### If you would like to be considered for the NVIDIA Platform General prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

An NVIDIA Brev instance (`delphi-gpu`, L40S 46 GB) served Qwen3-32B (AWQ 4-bit) with vLLM 0.32 as a self-hosted claim assessor, scoring all **566 claims** of the Aristotle biology project for dataset resolvability, one JSON-schema-constrained request per claim at about one claim per second (concurrency 24). This matters structurally, not just as compute: our pipeline rule is *assessor ≠ builder* with at least two assessor providers, and an open-weights model on our own GPU is a provider no frontier-API builder shares, at zero per-token cost. Setup, serve and tunnel commands: [`scripts/assess/README.md`](https://github.com/fractastical/delphi/blob/main/scripts/assess/README.md); runner `run-assessor.mjs`; assessor record in [`claim-sources/aristotle-biology/assessment/assessors.json`](https://github.com/fractastical/delphi/blob/main/claim-sources/aristotle-biology/assessment/assessors.json); outputs merged into `assessments.json`. The 566 count is the number of entries carrying the `qwen` assessor in that file.

Around it: the BioNeMo ESMFold NIM call recorded as a refusal, four NIM protein-design backends wired into the design studio behind `NVIDIA_API_KEY`, and the OpenResearch (NVIDIA research agent via alphaXiv `orx`) literature grounding made a release requirement (see the Alphaxiv answer). Together these cover the three legs of the platform we touched: GPU serving, model NIMs and the research agent.

Not used: DGX Spark, ALCHEMI. The all-atom MD of kcnk5b (`md/kcnk5b/`) ran on a university cluster and is explicitly not counted as an NVIDIA contribution. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### If you would like to be considered for the E14 50K Prize explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

DELPHI is infrastructure, and infrastructure is what outlives a hackathon. The problem is that biology's candidate laws have no shared, machine-readable ledger of what is proved, tested, refuted or merely restated; every lab and every AI agent rediscovers the same questions. Our answer is a public, open, citable layer that agents and people both read: 1,763 claims, 880 signed nanopublications on the production registry, 91 theorems (73 Lean-checked), 174 pre-registered data tests with verdicts, all served through a hosted MCP endpoint (`mcp.delphibio.org/mcp`) that any Claude, Cursor or ChatGPT user can add in one line.

Adoption already happened during the event: two sibling repositories by an outside team ([delphi-evolve](https://github.com/kganjam/delphi-evolve), [delphi-frontier](https://github.com/kganjam/delphi-frontier)) imported 1,326 claim versions through our MCP server, visible as 30 sessions in our log ([`COLLABORATIONS.md`](https://github.com/fractastical/delphi/blob/main/COLLABORATIONS.md)); an outside agent on Moltbook requested a control that changed one of our verdicts.

We measured rather than asserted the multi-agent story: on 20 pre-registered test plans, every multi-agent arm beat a single agent by at least 4 of 20 verified datasets, the arms were indistinguishable from each other, and the single agent cost a fifth to a tenth as much ([`test-data/agent-comparison/SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/test-data/agent-comparison/SUMMARY.md)). We report nulls in the headline.

The path forward: the claim–test–assess–publish harness ([`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md), thirteen roles with contracts) generalizes to any field with a literature and data, and the design studio ([`sim-engine/`](https://github.com/fractastical/delphi/tree/main/sim-engine)) shows the same ledger constraining engineering. What is not established: no wet-lab work, and no claim promoted to a law of biology.
````

The ALCHEMI section is included for completeness; delete it if you'd rather leave that prize blank, since nothing ran.

They want the raw markdown text, so I should just give it in a fenced code block for easy copying, keeping the content as-is without extra commentary inside it.

### 2026-11-01 12:12 — Turn 4 (User)

> we should be doing a studio

**Assistant:**

"Studio" is ambiguous here — it could mean featuring the Design Studio more prominently in the demo, or referencing the actual `studio/` folder in the repo. I'll peek at that folder to clarify, then lead the demo section with the studio.

Agreed: the studio is the thing a judge can actually *do* something with, and the current demo answer buries it under a list of links. Here is the demo section rewritten to lead with it, plus a matching tweak to the project description's last sentence so the two agree.

````markdown
### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

**Try the Design Studio:** https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb

Type what an organism must do in plain text ("glides 5 m, survives 10–30 °C as an adult"). The studio turns it into criteria, lets you edit the fish at body, organ-system, organ, tissue, cell or gene level, runs it through eleven perturbation scenarios (temperature, current, pressure, altitude, wind, glide, predator, grip, sleep, day/night, digestion) at every developmental stage, and marks in red any design that breaks an accepted physical or biological law. The laws are versioned data in [`lean/registry/`](https://github.com/fractastical/delphi/tree/main/lean/registry), backed by the Lean proofs; the optimizer rejects any candidate with a new binding violation and says "no design meets the spec" when nothing qualifies. The same engine is exposed to agents as an MCP server ([`sim-engine/AGENT-GUIDE.md`](https://github.com/fractastical/delphi/blob/main/sim-engine/AGENT-GUIDE.md)) and the printable output is the Formlabs kit at `/print/`.

What it does not establish: a passing design is a shape that violates no registered law, not a viable animal; in-band wild-type numbers are scored *circular* by the independent harness ([`sim-engine/validation/STUDIO-RESULTS.md`](https://github.com/fractastical/delphi/blob/main/sim-engine/validation/STUDIO-RESULTS.md)) because the modules were calibrated on the papers they are scored against.

**The knowledge layer underneath it:**
- Site: https://delphibio.org (team page tour: https://delphibio.org/team.html)
- MCP server, no auth: `claude mcp add --transport http delphisci https://mcp.delphibio.org/mcp`
- Mission control: https://delphi-mission-control.ashenoy000.workers.dev/start/ (knowledge graph, Claim Book, deck)
- Agent forum: https://forum.delphibio.org
- Sibling studio by the collaborating team, importing our claims live: https://frontier.morphoswarm.ai/
````

And the last sentence of the 150-word description, swapped for:

````markdown
Agents query all of it over a hosted MCP server, and a design studio uses the same law registry to reject organism designs that break a proved or tested law.
````

(That keeps it at 150 words if you drop "Current state" down to "Now:".)

If by "doing a studio" you meant something else, say which: recording a studio walkthrough video for the optional field, or something about the `studio/` folder (which is the Frontier team's GOAL/PROTOCOL record, not our site).

_Tools used: Shell_

### 2026-11-01 12:13 — Turn 5 (User)

> i mean including the studio that we made that is now included

**Assistant:**

The user's referring to the studio/ folder now merged into the repo (MorphoSwarm Frontier studio). I should check studio/README.md to understand what it is before drafting markdown that mentions it.

Got it: `studio/` is the MorphoSwarm Frontier studio, now vendored into this repo with its database snapshot (`studio/data/db`). The earlier answers treated it as a sibling repo only. Here are the sections that change, with the studio presented as part of the submission.

````markdown
### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).

DELPHI (Distributed Epistemic Layer for Probabilistic Hypothesis Inference) searches for fundamental laws of biology: statements general enough to hold across organisms and scales, stated precisely enough to test. Biology's candidate "laws" are scattered across books and papers with no shared record of which are proved, which are empirical, and which are refuted. We extract them as claims traced to their sources (Darwin, Thompson, Wolfram, Levin, Aristotle, mathematical biologists), formalize them as Lean 4 theorems where possible, test them against organism data under pre-registered criteria, gate each test through an independent assessor from a different model provider, and publish every step as a citable nanopublication. Now: 1,763 claims, 880 live nanopubs, 91 theorems (73 Lean-checked), 174 data tests. On top of that ledger sits a biological design studio ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)): engineer toward a flying fish, with every claim, simulation and missing bridge visible and contestable.

### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

**Two things to try:**

1. **The Frontier design studio** — https://frontier.morphoswarm.ai/ (source: [`studio/`](https://github.com/fractastical/delphi/tree/main/studio), database snapshot in `studio/data/db`). Start from a desired capability, explore the flying fish at molecular, cellular, tissue, organ, organism and evolutionary scales, inspect the [simulations](https://frontier.morphoswarm.ai/#/simulations) (molecular dynamics, reaction–diffusion, scale growth, fluid), compare candidate geometries in 3D, download the printable form, and see the [build and resource evidence](https://frontier.morphoswarm.ai/#/work). Agents connect over MCP at `https://frontier.morphoswarm.ai/mcp` (public reads, credentialed writes that cannot grant scientific acceptance). The fish is an engineering candidate, not a validated organism, and the site says so.

2. **The claim ledger it is built on** — https://delphibio.org, queryable by any agent with one line: `claude mcp add --transport http delphisci https://mcp.delphibio.org/mcp`. Mission control at https://delphi-mission-control.ashenoy000.workers.dev/start/ shows the knowledge graph, Claim Book (each Lean proof end to end), and the in-browser [perturb & optimise](https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb) mode, which marks any design that breaks a registered law in red.

Agent forum: https://forum.delphibio.org. Animated walkthroughs: [`assets/delphi-summary.gif`](https://github.com/fractastical/delphi/blob/main/assets/delphi-summary.gif).

### If you would like to be considered for the E14 50K Prize explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

DELPHI is two layers that outlive a hackathon. The first is a public, citable ledger of biology's candidate laws: 1,763 claims, 880 signed nanopublications, 91 theorems (73 Lean-checked), 174 pre-registered data tests with verdicts, served over a hosted MCP endpoint (`mcp.delphibio.org/mcp`) any Claude, Cursor or ChatGPT user adds in one line. The second is the design studio built on it ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio), live at [frontier.morphoswarm.ai](https://frontier.morphoswarm.ai/)): versioned claims, problems, evidence and projects in PostgreSQL, real computational artifacts with source hashes and applicability limits, an interactive 3D flying-fish candidate with printable output, and challenges anchored to exact design versions. It imported 1,326 claim versions from the ledger through the MCP server during the event ([`COLLABORATIONS.md`](https://github.com/fractastical/delphi/blob/main/COLLABORATIONS.md)) and now ships in the same repository with its database snapshot.

We measured the multi-agent story rather than asserting it: on 20 pre-registered test plans, every multi-agent arm beat a single agent by at least 4 of 20 verified datasets, the arms were indistinguishable from each other, and the single agent cost a fifth to a tenth as much ([`test-data/agent-comparison/SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/test-data/agent-comparison/SUMMARY.md)). Nulls go in the headline.

The path forward: the claim–test–assess–publish harness ([`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md), thirteen roles with contracts) generalizes to any field with a literature and data, and the studio shows the same ledger constraining engineering. Not established: no wet-lab work, no claim promoted to a law of biology, and the fish is a design, not a species.
````

For the Nebius answer, add one sentence after the ESMFold paragraph, since the studio's compute record is now in-repo:

````markdown
The studio ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)) adds its own Nebius record: 48 GPU/CPU jobs (35 completed, 9 failed, 4 cancelled) and 15 scoped model runs (Evo2 7B, OpenFold2, ESM2, OpenMM, BETSE, Morpheus, a neural CA), with provider state and scientific state kept as separate fields and the failed diffusion-training run retained ([`swarm/FRONTIER-SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/swarm/FRONTIER-SUMMARY.md)).
````

The Formlabs, Alphaxiv and NVIDIA answers stand as written. One caveat: the README's "Sibling repositories" section still describes Frontier as a separate repo, so a judge who reads both will see a mismatch; worth a one-line update there saying it now lives in `studio/`.

_Tools used: Shell_

### 2026-11-01 12:19 — Turn 6 (User)

> update teh whole thing including to the new deck link

**Assistant:**

I need to find the new deck link, so I'll check the assets folder for a newer deck and look at git status for recently added files.

The newest deck in the repo is `assets/hackathon-deck-4.pdf` (11:35 today); I've used that. If "new deck link" means a Google Slides or Canva URL that isn't in the repo, swap it into the one line marked below.

````markdown
### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).

DELPHI (Distributed Epistemic Layer for Probabilistic Hypothesis Inference) searches for fundamental laws of biology: statements general enough to hold across organisms and scales, stated precisely enough to test. Biology's candidate "laws" are scattered across books and papers with no shared record of which are proved, which are empirical, and which are refuted. We extract them as claims traced to their sources (Darwin, Thompson, Wolfram, Levin, Aristotle, mathematical biologists), formalize them as Lean 4 theorems where possible, test them against organism data under pre-registered criteria, gate each test through an independent assessor from a different model provider, and publish every step as a citable nanopublication. Now: 1,763 claims, 880 live nanopubs, 91 theorems (73 Lean-checked), 174 data tests. On top of that ledger sits a biological design studio ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)): engineer toward a flying fish, with every claim, simulation and missing bridge visible and contestable.

### Provide the URL of your public, open-source GitHub repository.

https://github.com/fractastical/delphi

### Provide a link to your slide deck.

https://github.com/fractastical/delphi/blob/main/assets/hackathon-deck-4.pdf

Live, data-driven version (unevidenced slides greyed out): https://delphi-mission-control.ashenoy000.workers.dev/deck/

### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

**Two things to try:**

1. **The Frontier design studio** — https://frontier.morphoswarm.ai/ (source: [`studio/`](https://github.com/fractastical/delphi/tree/main/studio), database snapshot in `studio/data/db`). Start from a desired capability, explore the flying fish at molecular, cellular, tissue, organ, organism and evolutionary scales, inspect the [simulations](https://frontier.morphoswarm.ai/#/simulations) (molecular dynamics, reaction–diffusion, scale growth, fluid), compare candidate geometries in 3D, download the printable form, and see the [build and resource evidence](https://frontier.morphoswarm.ai/#/work). Agents connect over MCP at `https://frontier.morphoswarm.ai/mcp` (public reads, credentialed writes that cannot grant scientific acceptance). The fish is an engineering candidate, not a validated organism, and the site says so.

2. **The claim ledger it is built on** — https://delphibio.org, queryable by any agent with one line: `claude mcp add --transport http delphisci https://mcp.delphibio.org/mcp`. Mission control at https://delphi-mission-control.ashenoy000.workers.dev/start/ shows the knowledge graph, Claim Book (each Lean proof end to end), and the in-browser [perturb & optimise](https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb) mode, which marks any design that breaks a registered law in red.

Agent forum: https://forum.delphibio.org. Animated walkthroughs: [`assets/delphi-summary.gif`](https://github.com/fractastical/delphi/blob/main/assets/delphi-summary.gif), [`assets/overnight-nov1.gif`](https://github.com/fractastical/delphi/blob/main/assets/overnight-nov1.gif).

### If you would like to be considered for the Formlabs prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We used Formlabs SLA to put a mathematical model next to the real thing. Two 140 mm hindwings of the dragonfly *Arigomphus villosipes* were printed on the hackathon's printers (0.6 mm membrane, 1.5 mm main veins): one carries the vein network segmented from a photograph of the real wing (442 closed cells); the other regenerates the cross veins with the Hoffmann et al. 2018 (*PNAS* 115:9905) inhibitory-centre/Voronoi rule (480 cells). Hoffmann's claim is that the model looks like the real wing; the prints put that claim in a judge's hand. Record: [issue #58](https://github.com/fractastical/delphi/issues/58), photo [`assets/arigomphus-wing.jpg`](https://github.com/fractastical/delphi/blob/main/assets/arigomphus-wing.jpg), README section [The wings](https://github.com/fractastical/delphi#the-wings-a-model-next-to-the-real-thing), where each wing design decision is tagged as a Lean-proved claim (hollow spar `thompson1917-ch16-03`, wall thickness `ch16-04`), a data-tested one, or open.

Several copies of a flying zebrafish ([`fabrication/flying-zebrafish/`](https://github.com/fractastical/delphi/tree/main/fabrication/flying-zebrafish)) were also printed, designed by a six-agent swarm to a shared Form 3/4 spec (0.6 mm minimum feature, STL+3MF, mesh verified watertight). The studio's flying-fish candidates export printable meshes with download provenance ([`studio/docs/printing.md`](https://github.com/fractastical/delphi/blob/main/studio/docs/printing.md)), labelled as physical props.

Designed to Formlabs specifications but not yet printed: a 71-file winged-zebrafish anatomy kit in Tough 2000 (0.5 mm walls, D-keyed press-fit pegs, Blender-verified; [`anatomy-model/print/`](https://github.com/fractastical/delphi/tree/main/anatomy-model/print)), and a [pre-registered printed test](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-bilayer-curvature/printed-bilayer-01) of a Lean-proved bilayer-curvature law, whose curvature is predicted before the strip is built.

What we did not do: no measured print-vs-design agreement yet; the PreForm API path was documented, not exercised. Full record: [`sponsors/FORMLABS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/FORMLABS.md).

### If you would like to be considered for the Alphaxiv prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

OpenResearch via the official `orx` CLI is a release requirement in our pipeline, not an enrichment. [`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md) role A2 (Source attestor) says no claim may be formalized or tested until it carries a logged `orx discover` run recording what the modern literature says and whether prior work already answers it. The reason: the biggest credibility risk in a project restating Darwin and Thompson is pretending nobody has studied the question since.

What it changed, all logged with command, UTC time, exit code and returned records:

- Six headline claim tests (Kimura, Maynard Smith hitchhiking, two Thompson, two Darwin): **5 of 6 were already answered by prior work**, so they are reported as reproductions with the open part named ([`test-data/claim-tests/openresearch/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/openresearch)).
- A 59-search prior-art report on "a layered, ontology-based, formally checked organism" found Phenoscape, Uberon, the Human Reference Atlas and whole-cell models; it ruled out "first formal verification of biology" as a claim we may make ([`research/prior-art/REPORT.md`](https://github.com/fractastical/delphi/blob/main/research/prior-art/REPORT.md), `SEARCHES.md`).
- The flying-fish physics thread ([`physics/PRIOR-ART.md`](https://github.com/fractastical/delphi/blob/main/physics/PRIOR-ART.md)) and the 20-problem open-problems catalogue ([`open-problems/SOURCES.md`](https://github.com/fractastical/delphi/blob/main/open-problems/SOURCES.md)).

Rule applied throughout: citations come only from searches that returned them; `assessments.mjs` refuses to write an identifier its runs did not return, and `orx discover` issues no run ID so we record `run_identifier: null` rather than inventing one. The dashboard counts OpenResearch records per role (`dashboard/compliance.mjs`).

Not done: no `orx` experiment/compute runs, only `orx discover`. Record: [`sponsors/OPENRESEARCH.md`](https://github.com/fractastical/delphi/blob/main/sponsors/OPENRESEARCH.md).

### If you would like to be considered for the Nebius prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

The Nebius Scientific AI Platform, reached through its MCP server, produced our most instructive data verdicts. Client: [`plugins/nebius/`](https://github.com/fractastical/delphi/tree/main/plugins/nebius) (`fold.py` uses content-derived idempotency keys so re-runs re-attach to the same operation).

**Cell segmentation, 19 operations (Cellpose CPSAM v2).** Eight openly licensed tissue micrographs plus eleven synthetic tilings were segmented to test three of D'Arcy Thompson's cell-packing claims: walls meet three at a time at 120° (`thompson1917-ch07-04`), hexagons regular only where cells are equal in size (`ch07-08`), close-packed cells hexagonal on average (`ch07-10`). Every mask carries its Nebius `operation_id`, model SHA-256 and input hash. Verdicts: ch07-04 supported in four of five tissues with grass as a counter-example; ch07-08 true of any space-filling partition (the random-Voronoi control shows it); ch07-10 forced by Euler's formula. The synthetic null showed Cellpose pulls even a brick wall toward 120°, cutting ch07-04's confidence from 0.60 to 0.35. Record: [`claim-sources/cell-geometry/README.md`](https://github.com/fractastical/delphi/blob/main/claim-sources/cell-geometry/README.md); three signed evidence nanopubs carry the operation IDs.

**Protein structure, 23 ESMFold2 operations** for three pre-registered Levin tests (planarian innexin octamer, HCN2 GYG→AAA co-assembly, an 18-protein channel panel). Criteria were committed before any structure was opened; verdicts are not yet computed ([`test-data/claim-tests/levin-papers/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/levin-papers)).

**The studio** ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)) adds its own record: 48 Nebius GPU/CPU jobs (35 completed, 9 failed, 4 cancelled) and 15 scoped model runs (Evo2 7B, OpenFold2, ESM2, OpenMM, BETSE, Morpheus, a neural CA), provider state and scientific state kept as separate fields, the failed diffusion-training run retained ([`swarm/FRONTIER-SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/swarm/FRONTIER-SUMMARY.md)).

Record: [`sponsors/NEBIUS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NEBIUS.md).

### If you would like to be considered for the NVIDIA ALCHEMI prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We did not run ALCHEMI during the hackathon and say so. [Issue #13](https://github.com/fractastical/delphi/issues/13) proposes the pairing we think ALCHEMI is for in this project: screen a candidate structure with the Batched Geometry Relaxation NIM, print it with Formlabs through the PreForm API, and publish both steps as linked nanopublications so the simulated and fabricated object share one provenance chain. That design exists; the run does not.

The nearest work that did run is in the same domain of trust in ML interatomic potentials: [`plugins/fittest/`](https://github.com/fractastical/delphi/tree/main/plugins/fittest) sends PubChem conformers of alanine, lactic acid and glyceraldehyde (with mirror images, rotations and stretched bonds) through a router over MACE-MPA-0, AIMNet2 and Orb-v3, and found that Orb-v3 is not exactly equivariant (1–6 meV mirror asymmetry) and that stretched bonds stay "trusted" on a handful of DFT labels. We then applied the same trust-or-escalate rule to our own assessor truth scores (`route.py`). This is context for claim `thompson1917-ch09-03` on molecular asymmetry, and it is not an ALCHEMI result. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md), "What we did not use".

### If you would like to be considered for the NVIDIA BioNeMo prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

Our BioNeMo record is a documented refusal, wired-but-unexercised integrations, and the studio's model runs, presented as exactly that. On Oct 30 all 27 NVIDIA-BioNeMo repositories were reviewed for fit ([issue #14](https://github.com/fractastical/delphi/issues/14)); `bionemo-agent-toolkit` was the best match, and the proposal to make BioNeMo an agent harness was rejected in architecture review ([#17](https://github.com/fractastical/delphi/issues/17)) as backwards: BioNeMo is a model service, not where an agent lives.

The hosted ESMFold NIM was called on bovine albumin (UniProt P02769, checksummed input) and returned HTTP 401, because the key available was a Brev key, not an `nvapi-` NIM key. We recorded it as a run with `status: "refused"` ([`organism-design/esmfold/runs/P02769/result.json`](https://github.com/fractastical/delphi/blob/main/organism-design/esmfold/runs/P02769/result.json)) and as two unsigned nanopub drafts, following our rule that a documented refusal is a finding another team can cite.

ProteinMPNN, RFdiffusion, Evo2 and ESMFold NIMs are wired into the organism design studio ([`sim-engine/generative/backends/protein.mjs`](https://github.com/fractastical/delphi/blob/main/sim-engine/generative/backends/protein.mjs)); without a key the protein level reports `not configured` and zero candidates, and tests confirm a bogus key reads as `auth failed` with no key leak. No NIM payload has run against a live key.

The Frontier studio ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)) ran Evo2 7B on zebrafish sequence (`studio/evo2_zebrafish/`, smoke test in `studio/evo2_smoke/`) and OpenFold2 and ESM2 among its 15 scoped model runs, on Nebius rather than NIM, with inputs and source hashes beside each artifact.

Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### If you would like to be considered for the NVIDIA Platform General prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

An NVIDIA Brev instance (`delphi-gpu`, L40S 46 GB) served Qwen3-32B (AWQ 4-bit) with vLLM 0.32 as a self-hosted claim assessor, scoring all **566 claims** of the Aristotle biology project for dataset resolvability, one JSON-schema-constrained request per claim at about one claim per second (concurrency 24). This matters structurally, not just as compute: our pipeline rule is *assessor ≠ builder* with at least two assessor providers, and an open-weights model on our own GPU is a provider no frontier-API builder shares, at zero per-token cost. Setup, serve and tunnel commands: [`scripts/assess/README.md`](https://github.com/fractastical/delphi/blob/main/scripts/assess/README.md); assessor record in [`claim-sources/aristotle-biology/assessment/assessors.json`](https://github.com/fractastical/delphi/blob/main/claim-sources/aristotle-biology/assessment/assessors.json). The 566 count is the number of entries carrying the `qwen` assessor in `assessments.json`.

Around it: the BioNeMo ESMFold NIM call recorded as a refusal, four NIM protein-design backends wired into the design studio behind `NVIDIA_API_KEY`, the OpenResearch (NVIDIA research agent via alphaXiv `orx`) literature grounding made a release requirement (see the Alphaxiv answer), and the Frontier studio's Evo2 7B runs ([`studio/evo2_zebrafish/`](https://github.com/fractastical/delphi/tree/main/studio/evo2_zebrafish)). Together these cover GPU serving, model NIMs, open NVIDIA models and the research agent.

Not used: DGX Spark, ALCHEMI. The all-atom MD of kcnk5b (`md/kcnk5b/`) ran on a university cluster and is explicitly not counted as an NVIDIA contribution. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### If you would like to be considered for the E14 50K Prize explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

DELPHI is two layers that outlive a hackathon. The first is a public, citable ledger of biology's candidate laws: 1,763 claims, 880 signed nanopublications, 91 theorems (73 Lean-checked), 174 pre-registered data tests with verdicts, served over a hosted MCP endpoint (`mcp.delphibio.org/mcp`) any Claude, Cursor or ChatGPT user adds in one line. The second is the design studio built on it ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio), live at [frontier.morphoswarm.ai](https://frontier.morphoswarm.ai/)): versioned claims, problems, evidence and projects in PostgreSQL, real computational artifacts with source hashes and applicability limits, an interactive 3D flying-fish candidate with printable output, and challenges anchored to exact design versions. It imported 1,326 claim versions from the ledger through the MCP server during the event ([`COLLABORATIONS.md`](https://github.com/fractastical/delphi/blob/main/COLLABORATIONS.md)) and now ships in the same repository with its database snapshot.

We measured the multi-agent story rather than asserting it: on 20 pre-registered test plans, every multi-agent arm beat a single agent by at least 4 of 20 verified datasets, the arms were indistinguishable from each other, and the single agent cost a fifth to a tenth as much ([`test-data/agent-comparison/SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/test-data/agent-comparison/SUMMARY.md)). Nulls go in the headline.

The path forward: the claim–test–assess–publish harness ([`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md), thirteen roles with contracts) generalizes to any field with a literature and data, and the studio shows the same ledger constraining engineering. Not established: no wet-lab work, no claim promoted to a law of biology, and the fish is a design, not a species.
````

Two notes. The Evo2 sentences in the BioNeMo and Platform answers cite `studio/evo2_zebrafish/` and the 15-run count from `swarm/FRONTIER-SUMMARY.md`; I did not re-run those, so they are quoted from the Frontier team's own record. And the ALCHEMI block is still there for you to delete if you'd rather not apply.

I don't see another deck link beyond hackathon-deck-4.pdf, so I'll assume that's what they mean and note they can swap it if there's an external link. I'll proceed to produce the full markdown with that file.

_Tools used: Shell_

### 2026-11-01 12:22 — Turn 7 (User)

> [Image attached] ?

**Assistant:**

A CNAME can only point to a hostname, not an IP address. `34.223.78.181` is an IP, so the registrar rejects it.

Change the type to **A**:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | studio | 34.223.78.181 | 1/2 Hour |

Use CNAME only if you want `studio.delphibio.org` to alias a hostname, e.g. `frontier.morphoswarm.ai` — but then the server at that host also has to be configured (nginx `server_name` and a TLS cert) to answer for `studio.delphibio.org`, otherwise you'll get a certificate error. The repo's `studio/deploy/nginx/` is where that would go; the recent commit "record the requested certificates and the DNS records still needed" in `forum/` and `mcp/` suggests the same step was just done for those two subdomains.

### 2026-11-01 12:23 — Turn 8 (User)

> ok update with this for the studio and give me full markdown, remove the sections for things we don't cqaulify for, just put "we dont't qualify for this prize:

**Assistant:**

````markdown
### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).

DELPHI (Distributed Epistemic Layer for Probabilistic Hypothesis Inference) searches for fundamental laws of biology: statements general enough to hold across organisms and scales, stated precisely enough to test. Biology's candidate "laws" are scattered across books and papers with no shared record of which are proved, which are empirical, and which are refuted. We extract them as claims traced to their sources (Darwin, Thompson, Wolfram, Levin, Aristotle, mathematical biologists), formalize them as Lean 4 theorems where possible, test them against organism data under pre-registered criteria, gate each test through an independent assessor from a different model provider, and publish every step as a citable nanopublication. Now: 1,763 claims, 880 live nanopubs, 91 theorems (73 Lean-checked), 174 data tests. On top of that ledger sits a biological design studio ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)): engineer toward a flying fish, with every claim, simulation and missing bridge visible and contestable.

### Provide the URL of your public, open-source GitHub repository.

https://github.com/fractastical/delphi

### Provide a link to your slide deck.

https://github.com/fractastical/delphi/blob/main/assets/hackathon-deck-4.pdf

Live, data-driven version (unevidenced slides greyed out): https://delphi-mission-control.ashenoy000.workers.dev/deck/

### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

**Two things to try:**

1. **The design studio** — https://studio.delphibio.org (source: [`studio/`](https://github.com/fractastical/delphi/tree/main/studio), database snapshot in `studio/data/db`; mirror at https://frontier.morphoswarm.ai/). Start from a desired capability, explore the flying fish at molecular, cellular, tissue, organ, organism and evolutionary scales, inspect the [simulations](https://studio.delphibio.org/#/simulations) (molecular dynamics, reaction–diffusion, scale growth, fluid), compare candidate geometries in 3D, download the printable form, and see the [build and resource evidence](https://studio.delphibio.org/#/work). Agents connect over MCP at `https://studio.delphibio.org/mcp` (public reads, credentialed writes that cannot grant scientific acceptance). The fish is an engineering candidate, not a validated organism, and the site says so.

2. **The claim ledger it is built on** — https://delphibio.org, queryable by any agent with one line: `claude mcp add --transport http delphisci https://mcp.delphibio.org/mcp`. Mission control at https://delphi-mission-control.ashenoy000.workers.dev/start/ shows the knowledge graph, Claim Book (each Lean proof end to end), and the in-browser [perturb & optimise](https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb) mode, which marks any design that breaks a registered law in red.

Agent forum: https://forum.delphibio.org. Animated walkthroughs: [`assets/delphi-summary.gif`](https://github.com/fractastical/delphi/blob/main/assets/delphi-summary.gif), [`assets/overnight-nov1.gif`](https://github.com/fractastical/delphi/blob/main/assets/overnight-nov1.gif).

### If you would like to be considered for the Formlabs prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We used Formlabs SLA to put a mathematical model next to the real thing. Two 140 mm hindwings of the dragonfly *Arigomphus villosipes* were printed on the hackathon's printers (0.6 mm membrane, 1.5 mm main veins): one carries the vein network segmented from a photograph of the real wing (442 closed cells); the other regenerates the cross veins with the Hoffmann et al. 2018 (*PNAS* 115:9905) inhibitory-centre/Voronoi rule (480 cells). Hoffmann's claim is that the model looks like the real wing; the prints put that claim in a judge's hand. Record: [issue #58](https://github.com/fractastical/delphi/issues/58), photo [`assets/arigomphus-wing.jpg`](https://github.com/fractastical/delphi/blob/main/assets/arigomphus-wing.jpg), README section [The wings](https://github.com/fractastical/delphi#the-wings-a-model-next-to-the-real-thing), where each wing design decision is tagged as a Lean-proved claim (hollow spar `thompson1917-ch16-03`, wall thickness `ch16-04`), a data-tested one, or open.

Several copies of a flying zebrafish ([`fabrication/flying-zebrafish/`](https://github.com/fractastical/delphi/tree/main/fabrication/flying-zebrafish)) were also printed, designed by a six-agent swarm to a shared Form 3/4 spec (0.6 mm minimum feature, STL+3MF, mesh verified watertight). The studio's flying-fish candidates export printable meshes with download provenance ([`studio/docs/printing.md`](https://github.com/fractastical/delphi/blob/main/studio/docs/printing.md)), labelled as physical props.

Designed to Formlabs specifications but not yet printed: a 71-file winged-zebrafish anatomy kit in Tough 2000 (0.5 mm walls, D-keyed press-fit pegs, Blender-verified; [`anatomy-model/print/`](https://github.com/fractastical/delphi/tree/main/anatomy-model/print)), and a [pre-registered printed test](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-bilayer-curvature/printed-bilayer-01) of a Lean-proved bilayer-curvature law, whose curvature is predicted before the strip is built.

What we did not do: no measured print-vs-design agreement yet; the PreForm API path was documented, not exercised. Full record: [`sponsors/FORMLABS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/FORMLABS.md).

### If you would like to be considered for the Alphaxiv prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

OpenResearch via the official `orx` CLI is a release requirement in our pipeline, not an enrichment. [`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md) role A2 (Source attestor) says no claim may be formalized or tested until it carries a logged `orx discover` run recording what the modern literature says and whether prior work already answers it. The reason: the biggest credibility risk in a project restating Darwin and Thompson is pretending nobody has studied the question since.

What it changed, all logged with command, UTC time, exit code and returned records:

- Six headline claim tests (Kimura, Maynard Smith hitchhiking, two Thompson, two Darwin): **5 of 6 were already answered by prior work**, so they are reported as reproductions with the open part named ([`test-data/claim-tests/openresearch/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/openresearch)).
- A 59-search prior-art report on "a layered, ontology-based, formally checked organism" found Phenoscape, Uberon, the Human Reference Atlas and whole-cell models; it ruled out "first formal verification of biology" as a claim we may make ([`research/prior-art/REPORT.md`](https://github.com/fractastical/delphi/blob/main/research/prior-art/REPORT.md), `SEARCHES.md`).
- The flying-fish physics thread ([`physics/PRIOR-ART.md`](https://github.com/fractastical/delphi/blob/main/physics/PRIOR-ART.md)) and the 20-problem open-problems catalogue ([`open-problems/SOURCES.md`](https://github.com/fractastical/delphi/blob/main/open-problems/SOURCES.md)).

Rule applied throughout: citations come only from searches that returned them; `assessments.mjs` refuses to write an identifier its runs did not return, and `orx discover` issues no run ID so we record `run_identifier: null` rather than inventing one. The dashboard counts OpenResearch records per role (`dashboard/compliance.mjs`).

Not done: no `orx` experiment/compute runs, only `orx discover`. Record: [`sponsors/OPENRESEARCH.md`](https://github.com/fractastical/delphi/blob/main/sponsors/OPENRESEARCH.md).

### If you would like to be considered for the Nebius prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

The Nebius Scientific AI Platform, reached through its MCP server, produced our most instructive data verdicts. Client: [`plugins/nebius/`](https://github.com/fractastical/delphi/tree/main/plugins/nebius) (`fold.py` uses content-derived idempotency keys so re-runs re-attach to the same operation).

**Cell segmentation, 19 operations (Cellpose CPSAM v2).** Eight openly licensed tissue micrographs plus eleven synthetic tilings were segmented to test three of D'Arcy Thompson's cell-packing claims: walls meet three at a time at 120° (`thompson1917-ch07-04`), hexagons regular only where cells are equal in size (`ch07-08`), close-packed cells hexagonal on average (`ch07-10`). Every mask carries its Nebius `operation_id`, model SHA-256 and input hash. Verdicts: ch07-04 supported in four of five tissues with grass as a counter-example; ch07-08 true of any space-filling partition (the random-Voronoi control shows it); ch07-10 forced by Euler's formula. The synthetic null showed Cellpose pulls even a brick wall toward 120°, cutting ch07-04's confidence from 0.60 to 0.35. Record: [`claim-sources/cell-geometry/README.md`](https://github.com/fractastical/delphi/blob/main/claim-sources/cell-geometry/README.md); three signed evidence nanopubs carry the operation IDs.

**Protein structure, 23 ESMFold2 operations** for three pre-registered Levin tests (planarian innexin octamer, HCN2 GYG→AAA co-assembly, an 18-protein channel panel). Criteria were committed before any structure was opened; verdicts are not yet computed ([`test-data/claim-tests/levin-papers/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/levin-papers)).

**The studio** ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio), https://studio.delphibio.org) adds its own record: 48 Nebius GPU/CPU jobs (35 completed, 9 failed, 4 cancelled) and 15 scoped model runs (Evo2 7B, OpenFold2, ESM2, OpenMM, BETSE, Morpheus, a neural CA), provider state and scientific state kept as separate fields, the failed diffusion-training run retained ([`swarm/FRONTIER-SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/swarm/FRONTIER-SUMMARY.md)).

Record: [`sponsors/NEBIUS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NEBIUS.md).

### If you would like to be considered for the NVIDIA ALCHEMI prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We don't qualify for this prize.

### If you would like to be considered for the NVIDIA BioNeMo prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We don't qualify for this prize.

### If you would like to be considered for the NVIDIA Platform General prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

An NVIDIA Brev instance (`delphi-gpu`, L40S 46 GB) served Qwen3-32B (AWQ 4-bit) with vLLM 0.32 as a self-hosted claim assessor, scoring all **566 claims** of the Aristotle biology project for dataset resolvability, one JSON-schema-constrained request per claim at about one claim per second (concurrency 24). This matters structurally, not just as compute: our pipeline rule is *assessor ≠ builder* with at least two assessor providers, and an open-weights model on our own GPU is a provider no frontier-API builder shares, at zero per-token cost. Setup, serve and tunnel commands: [`scripts/assess/README.md`](https://github.com/fractastical/delphi/blob/main/scripts/assess/README.md); assessor record in [`claim-sources/aristotle-biology/assessment/assessors.json`](https://github.com/fractastical/delphi/blob/main/claim-sources/aristotle-biology/assessment/assessors.json). The 566 count is the number of entries carrying the `qwen` assessor in `assessments.json`.

Around it: the BioNeMo ESMFold NIM call on bovine albumin, refused with HTTP 401 and recorded as a run with `status: "refused"` plus two unsigned nanopub drafts rather than discarded ([`organism-design/esmfold/runs/P02769/`](https://github.com/fractastical/delphi/tree/main/organism-design/esmfold/runs/P02769)); four NIM protein-design backends (ProteinMPNN, RFdiffusion, Evo2, ESMFold) wired into the design studio behind `NVIDIA_API_KEY` and tested to fail closed, never run against a live key; the OpenResearch (NVIDIA research agent via alphaXiv `orx`) literature grounding made a release requirement (see the Alphaxiv answer); and the studio's Evo2 7B runs on zebrafish sequence ([`studio/evo2_zebrafish/`](https://github.com/fractastical/delphi/tree/main/studio/evo2_zebrafish)). Together these cover GPU serving, open NVIDIA models and the research agent.

Not used: DGX Spark, ALCHEMI. The all-atom MD of kcnk5b (`md/kcnk5b/`) ran on a university cluster and is explicitly not counted as an NVIDIA contribution. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### If you would like to be considered for the E14 50K Prize explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

DELPHI is two layers that outlive a hackathon. The first is a public, citable ledger of biology's candidate laws: 1,763 claims, 880 signed nanopublications, 91 theorems (73 Lean-checked), 174 pre-registered data tests with verdicts, served over a hosted MCP endpoint (`mcp.delphibio.org/mcp`) any Claude, Cursor or ChatGPT user adds in one line. The second is the design studio built on it ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio), live at [studio.delphibio.org](https://studio.delphibio.org)): versioned claims, problems, evidence and projects in PostgreSQL, real computational artifacts with source hashes and applicability limits, an interactive 3D flying-fish candidate with printable output, and challenges anchored to exact design versions. It imported 1,326 claim versions from the ledger through the MCP server during the event ([`COLLABORATIONS.md`](https://github.com/fractastical/delphi/blob/main/COLLABORATIONS.md)) and now ships in the same repository with its database snapshot.

We measured the multi-agent story rather than asserting it: on 20 pre-registered test plans, every multi-agent arm beat a single agent by at least 4 of 20 verified datasets, the arms were indistinguishable from each other, and the single agent cost a fifth to a tenth as much ([`test-data/agent-comparison/SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/test-data/agent-comparison/SUMMARY.md)). Nulls go in the headline.

The path forward: the claim–test–assess–publish harness ([`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md), thirteen roles with contracts) generalizes to any field with a literature and data, and the studio shows the same ledger constraining engineering. Not established: no wet-lab work, no claim promoted to a law of biology, and the fish is a design, not a species.
````

I marked both ALCHEMI and BioNeMo as not qualifying: nothing ran through ALCHEMI, and the only BioNeMo call was the 401 refusal (the studio's Evo2/ESM2 runs went through Nebius, not BioNeMo). If you'd rather keep the BioNeMo pitch on the strength of the refusal record and the wired NIMs, the earlier text is still valid.

One caution on the studio link: the A record was just created, so `studio.delphibio.org` won't serve until DNS propagates and nginx on 34.223.78.181 has a `server_name` and TLS cert for it. I kept `frontier.morphoswarm.ai` as the mirror in the demo answer so judges have a working URL either way.

I should update the studio URL to studio.delphibio.org. Thinking through which prizes we actually qualify for — ALCHEMI clearly doesn't since nothing used it, and honestly BioNeMo doesn't either since the NIM was refused and the studio ran Evo2/OpenFold2/ESM2 on Nebius instead. I'll mark both ALCHEMI and BioNeMo as not qualifying to be accurate.

Since DNS was just set, studio.delphibio.org might not resolve or have TLS ready yet, so I'll mention frontier.morphoswarm.ai briefly as a fallback in case judges hit certificate errors before nginx is configured — but keep it concise.

### 2026-11-01 12:26 — Turn 9 (User)

> we need to puldate the links, also i guess we need to point to platform subdirectory

**Assistant:**

The latest commit now serves the portal from /platform/, so I should check what's at the delphibio.org root, look at the docs structure, and verify all the links are actually live.

All the delphibio.org subdomains are failing to connect, so I should run a dig command to check DNS resolution directly.

I checked every link live. All 33 GitHub and dashboard links return 200. Every `delphibio.org` link is currently broken, for four separate reasons, so I've put working URLs in the submission and listed the DNS fixes.

**What's wrong right now**

| Host | State | Fix |
|---|---|---|
| `delphibio.org` | DNS → GitHub Pages, but Pages' certificate doesn't cover the apex yet (`no alternative certificate subject name matches`). HTTP works, HTTPS fails. | In repo Settings → Pages, re-save custom domain and tick "Enforce HTTPS" once the cert issues; may take up to an hour. |
| `mcp.delphibio.org` | No DNS record at all | Add `A 66.241.125.161` and `AAAA 2a09:8280:1::1d9:ca99:0` (from `mcp/README.md`) |
| `forum.delphibio.org` | No DNS record at all | Add `A 66.241.124.120` and `AAAA 2a09:8280:1::1db:4b52:0` (from `forum/README.md`) |
| `studio.delphibio.org` | A record resolves to 34.223.78.181, but nginx there returns **403** and has no cert for the name | Add a `server_name studio.delphibio.org` block + cert on the Frontier box (`studio/deploy/nginx/`) |

The portal is live at `https://fractastical.github.io/delphi/platform/` (200), so the submission points there with the `/platform/` path, and the studio points at the mirror that works. Swap the `delphibio.org` URLs back in once the table above is green.

````markdown
### Briefly describe your project and the scientific or technical problem it addresses (maximum 150 words).

DELPHI (Distributed Epistemic Layer for Probabilistic Hypothesis Inference) searches for fundamental laws of biology: statements general enough to hold across organisms and scales, stated precisely enough to test. Biology's candidate "laws" are scattered across books and papers with no shared record of which are proved, which are empirical, and which are refuted. We extract them as claims traced to their sources (Darwin, Thompson, Wolfram, Levin, Aristotle, mathematical biologists), formalize them as Lean 4 theorems where possible, test them against organism data under pre-registered criteria, gate each test through an independent assessor from a different model provider, and publish every step as a citable nanopublication. Now: 1,763 claims, 880 live nanopubs, 91 theorems (73 Lean-checked), 174 data tests. On top of that ledger sits a biological design studio ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio)): engineer toward a flying fish, with every claim, simulation and missing bridge visible and contestable.

### Provide the URL of your public, open-source GitHub repository.

https://github.com/fractastical/delphi

### Provide a link to your slide deck.

https://github.com/fractastical/delphi/blob/main/assets/hackathon-deck-4.pdf

Live, data-driven version (unevidenced slides greyed out): https://delphi-mission-control.ashenoy000.workers.dev/deck/

### Provide a link to a demo video or a live, working website where judges can try your project, if available (optional).

**Two things to try:**

1. **The design studio** — https://frontier.morphoswarm.ai/ (source: [`studio/`](https://github.com/fractastical/delphi/tree/main/studio), database snapshot in `studio/data/db`). Start from a desired capability, explore the flying fish at molecular, cellular, tissue, organ, organism and evolutionary scales, inspect the [simulations](https://frontier.morphoswarm.ai/#/simulations) (molecular dynamics, reaction–diffusion, scale growth, fluid), compare candidate geometries in 3D, download the printable form, and see the [build and resource evidence](https://frontier.morphoswarm.ai/#/work). Agents connect over MCP at `https://frontier.morphoswarm.ai/mcp` (public reads, credentialed writes that cannot grant scientific acceptance). The fish is an engineering candidate, not a validated organism, and the site says so.

2. **The claim ledger it is built on** — portal at https://fractastical.github.io/delphi/platform/, with the [team page tour](https://fractastical.github.io/delphi/team.html), [claim graph](https://fractastical.github.io/delphi/claim-graph.html) and [theorems](https://fractastical.github.io/delphi/theorems.html). Mission control at https://delphi-mission-control.ashenoy000.workers.dev/start/ shows the knowledge graph, Claim Book (each Lean proof end to end), and the in-browser [perturb & optimise](https://delphi-mission-control.ashenoy000.workers.dev/blueprint3d/explode.html?mode=perturb) mode, which marks any design that breaks a registered law in red. Any agent can query the ledger over MCP: `npx -y github:fractastical/delphi` (stdio), or the hosted Streamable HTTP endpoint at `https://delphisci-mcp.fly.dev/mcp`.

Animated walkthroughs: [`assets/delphi-summary.gif`](https://github.com/fractastical/delphi/blob/main/assets/delphi-summary.gif), [`assets/overnight-nov1.gif`](https://github.com/fractastical/delphi/blob/main/assets/overnight-nov1.gif).

### If you would like to be considered for the Formlabs prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We used Formlabs SLA to put a mathematical model next to the real thing. Two 140 mm hindwings of the dragonfly *Arigomphus villosipes* were printed on the hackathon's printers (0.6 mm membrane, 1.5 mm main veins): one carries the vein network segmented from a photograph of the real wing (442 closed cells); the other regenerates the cross veins with the Hoffmann et al. 2018 (*PNAS* 115:9905) inhibitory-centre/Voronoi rule (480 cells). Hoffmann's claim is that the model looks like the real wing; the prints put that claim in a judge's hand. Record: [issue #58](https://github.com/fractastical/delphi/issues/58), photo [`assets/arigomphus-wing.jpg`](https://github.com/fractastical/delphi/blob/main/assets/arigomphus-wing.jpg), README section [The wings](https://github.com/fractastical/delphi#the-wings-a-model-next-to-the-real-thing), where each wing design decision is tagged as a Lean-proved claim (hollow spar `thompson1917-ch16-03`, wall thickness `ch16-04`), a data-tested one, or open.

Several copies of a flying zebrafish ([`fabrication/flying-zebrafish/`](https://github.com/fractastical/delphi/tree/main/fabrication/flying-zebrafish)) were also printed, designed by a six-agent swarm to a shared Form 3/4 spec (0.6 mm minimum feature, STL+3MF, mesh verified watertight). The studio's flying-fish candidates export printable meshes with download provenance ([`studio/docs/printing.md`](https://github.com/fractastical/delphi/blob/main/studio/docs/printing.md)), labelled as physical props.

Designed to Formlabs specifications but not yet printed: a 71-file winged-zebrafish anatomy kit in Tough 2000 (0.5 mm walls, D-keyed press-fit pegs, Blender-verified; [`anatomy-model/print/`](https://github.com/fractastical/delphi/tree/main/anatomy-model/print)), and a [pre-registered printed test](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/plant-hygromorph-mechanics/hygromorph-bilayer-curvature/printed-bilayer-01) of a Lean-proved bilayer-curvature law, whose curvature is predicted before the strip is built.

What we did not do: no measured print-vs-design agreement yet; the PreForm API path was documented, not exercised. Full record: [`sponsors/FORMLABS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/FORMLABS.md).

### If you would like to be considered for the Alphaxiv prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

OpenResearch via the official `orx` CLI is a release requirement in our pipeline, not an enrichment. [`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md) role A2 (Source attestor) says no claim may be formalized or tested until it carries a logged `orx discover` run recording what the modern literature says and whether prior work already answers it. The reason: the biggest credibility risk in a project restating Darwin and Thompson is pretending nobody has studied the question since.

What it changed, all logged with command, UTC time, exit code and returned records:

- Six headline claim tests (Kimura, Maynard Smith hitchhiking, two Thompson, two Darwin): **5 of 6 were already answered by prior work**, so they are reported as reproductions with the open part named ([`test-data/claim-tests/openresearch/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/openresearch)).
- A 59-search prior-art report on "a layered, ontology-based, formally checked organism" found Phenoscape, Uberon, the Human Reference Atlas and whole-cell models; it ruled out "first formal verification of biology" as a claim we may make ([`research/prior-art/REPORT.md`](https://github.com/fractastical/delphi/blob/main/research/prior-art/REPORT.md), `SEARCHES.md`).
- The flying-fish physics thread ([`physics/PRIOR-ART.md`](https://github.com/fractastical/delphi/blob/main/physics/PRIOR-ART.md)) and the 20-problem open-problems catalogue ([`open-problems/SOURCES.md`](https://github.com/fractastical/delphi/blob/main/open-problems/SOURCES.md)).

Rule applied throughout: citations come only from searches that returned them; `assessments.mjs` refuses to write an identifier its runs did not return, and `orx discover` issues no run ID so we record `run_identifier: null` rather than inventing one. The dashboard counts OpenResearch records per role (`dashboard/compliance.mjs`).

Not done: no `orx` experiment/compute runs, only `orx discover`. Record: [`sponsors/OPENRESEARCH.md`](https://github.com/fractastical/delphi/blob/main/sponsors/OPENRESEARCH.md).

### If you would like to be considered for the Nebius prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

The Nebius Scientific AI Platform, reached through its MCP server, produced our most instructive data verdicts. Client: [`plugins/nebius/`](https://github.com/fractastical/delphi/tree/main/plugins/nebius) (`fold.py` uses content-derived idempotency keys so re-runs re-attach to the same operation).

**Cell segmentation, 19 operations (Cellpose CPSAM v2).** Eight openly licensed tissue micrographs plus eleven synthetic tilings were segmented to test three of D'Arcy Thompson's cell-packing claims: walls meet three at a time at 120° (`thompson1917-ch07-04`), hexagons regular only where cells are equal in size (`ch07-08`), close-packed cells hexagonal on average (`ch07-10`). Every mask carries its Nebius `operation_id`, model SHA-256 and input hash. Verdicts: ch07-04 supported in four of five tissues with grass as a counter-example; ch07-08 true of any space-filling partition (the random-Voronoi control shows it); ch07-10 forced by Euler's formula. The synthetic null showed Cellpose pulls even a brick wall toward 120°, cutting ch07-04's confidence from 0.60 to 0.35. Record: [`claim-sources/cell-geometry/README.md`](https://github.com/fractastical/delphi/blob/main/claim-sources/cell-geometry/README.md); three signed evidence nanopubs carry the operation IDs.

**Protein structure, 23 ESMFold2 operations** for three pre-registered Levin tests (planarian innexin octamer, HCN2 GYG→AAA co-assembly, an 18-protein channel panel). Criteria were committed before any structure was opened; verdicts are not yet computed ([`test-data/claim-tests/levin-papers/`](https://github.com/fractastical/delphi/tree/main/test-data/claim-tests/levin-papers)).

**The studio** ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio), https://frontier.morphoswarm.ai/) adds its own record: 48 Nebius GPU/CPU jobs (35 completed, 9 failed, 4 cancelled) and 15 scoped model runs (Evo2 7B, OpenFold2, ESM2, OpenMM, BETSE, Morpheus, a neural CA), provider state and scientific state kept as separate fields, the failed diffusion-training run retained ([`swarm/FRONTIER-SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/swarm/FRONTIER-SUMMARY.md)).

Record: [`sponsors/NEBIUS.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NEBIUS.md).

### If you would like to be considered for the NVIDIA ALCHEMI prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We don't qualify for this prize.

### If you would like to be considered for the NVIDIA BioNeMo prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

We don't qualify for this prize.

### If you would like to be considered for the NVIDIA Platform General prize, explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

An NVIDIA Brev instance (`delphi-gpu`, L40S 46 GB) served Qwen3-32B (AWQ 4-bit) with vLLM 0.32 as a self-hosted claim assessor, scoring all **566 claims** of the Aristotle biology project for dataset resolvability, one JSON-schema-constrained request per claim at about one claim per second (concurrency 24). This matters structurally, not just as compute: our pipeline rule is *assessor ≠ builder* with at least two assessor providers, and an open-weights model on our own GPU is a provider no frontier-API builder shares, at zero per-token cost. Setup, serve and tunnel commands: [`scripts/assess/README.md`](https://github.com/fractastical/delphi/blob/main/scripts/assess/README.md); assessor record in [`claim-sources/aristotle-biology/assessment/assessors.json`](https://github.com/fractastical/delphi/blob/main/claim-sources/aristotle-biology/assessment/assessors.json). The 566 count is the number of entries carrying the `qwen` assessor in `assessments.json`.

Around it: the BioNeMo ESMFold NIM call on bovine albumin, refused with HTTP 401 and recorded as a run with `status: "refused"` plus two unsigned nanopub drafts rather than discarded ([`organism-design/esmfold/runs/P02769/`](https://github.com/fractastical/delphi/tree/main/organism-design/esmfold/runs/P02769)); four NIM protein-design backends (ProteinMPNN, RFdiffusion, Evo2, ESMFold) wired into the design studio behind `NVIDIA_API_KEY` and tested to fail closed, never run against a live key; the OpenResearch (NVIDIA research agent via alphaXiv `orx`) literature grounding made a release requirement (see the Alphaxiv answer); and the studio's Evo2 7B runs on zebrafish sequence ([`studio/evo2_zebrafish/`](https://github.com/fractastical/delphi/tree/main/studio/evo2_zebrafish)). Together these cover GPU serving, open NVIDIA models and the research agent.

Not used: DGX Spark, ALCHEMI. The all-atom MD of kcnk5b (`md/kcnk5b/`) ran on a university cluster and is explicitly not counted as an NVIDIA contribution. Record: [`sponsors/NVIDIA.md`](https://github.com/fractastical/delphi/blob/main/sponsors/NVIDIA.md).

### If you would like to be considered for the E14 50K Prize explain how your project is relevant (maximum 250 words). Leave blank if you are not applying.

DELPHI is two layers that outlive a hackathon. The first is a public, citable ledger of biology's candidate laws: 1,763 claims, 880 signed nanopublications, 91 theorems (73 Lean-checked), 174 pre-registered data tests with verdicts, served over a hosted MCP endpoint any Claude, Cursor or ChatGPT user adds in one line. The second is the design studio built on it ([`studio/`](https://github.com/fractastical/delphi/tree/main/studio), live at [frontier.morphoswarm.ai](https://frontier.morphoswarm.ai/)): versioned claims, problems, evidence and projects in PostgreSQL, real computational artifacts with source hashes and applicability limits, an interactive 3D flying-fish candidate with printable output, and challenges anchored to exact design versions. It imported 1,326 claim versions from the ledger through the MCP server during the event ([`COLLABORATIONS.md`](https://github.com/fractastical/delphi/blob/main/COLLABORATIONS.md)) and now ships in the same repository with its database snapshot.

We measured the multi-agent story rather than asserting it: on 20 pre-registered test plans, every multi-agent arm beat a single agent by at least 4 of 20 verified datasets, the arms were indistinguishable from each other, and the single agent cost a fifth to a tenth as much ([`test-data/agent-comparison/SUMMARY.md`](https://github.com/fractastical/delphi/blob/main/test-data/agent-comparison/SUMMARY.md)). Nulls go in the headline.

The path forward: the claim–test–assess–publish harness ([`AGENTS.md`](https://github.com/fractastical/delphi/blob/main/AGENTS.md), thirteen roles with contracts) generalizes to any field with a literature and data, and the studio shows the same ledger constraining engineering. Not established: no wet-lab work, no claim promoted to a law of biology, and the fish is a design, not a species.
````

One thing I could not verify: the hosted MCP fallback `https://delphisci-mcp.fly.dev/mcp` is inferred from the Fly app name in `mcp/README.md` (`delphisci-mcp`); I did not get a 200 from it in this pass, so confirm it or drop that clause before submitting. Also the README links I checked under "The wings" anchor are to the repo README, which still says `delphibio.org` throughout; worth a sed once DNS is live.

_Tools used: Shell ×8_
