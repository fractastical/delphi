# for the sponsors (nvidia, openrearch, nebius, form labs) we need to clearly stat

- **Started:** 2026-11-01 11:15 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 11:39 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 3
- **Subagents:** 0
- **Transcript ID:** `6a61dd8d-747f-41ea-9bd9-dc476caedd28`

## Conversation

### 2026-11-01 11:15 — Turn 1 (User)

> for the sponsors (nvidia, openrearch, nebius, form labs) we need to clearly state what we used their services for, let's makes ure we have that lcaerly somwehre in a separate documetn for each one of these and then we can merge the highlights into the main readme

**Assistant:**

I'll start by finding what the repo actually records about each sponsor, so the documents state only what was used.

I need to create separate documents for each sponsor (NVIDIA, OpenResearch, Nebius, Formlabs) detailing what their services were used for, then fold highlights into the main README. First I should search the repo for actual mentions of each sponsor so I only state verified facts and flag anything uncertain.

Now the key sources: the README's existing sponsor mentions, COLLABORATIONS.md, and the main records for each sponsor.

I need more detail on each organization's contributions—Nebius's cell-geometry work and plugin integrations, NVIDIA's ESMFold/BioNeMo runs and protein backend work, and OpenResearch's prior-art documentation across research and physics domains.

I also want to check Formlabs's fabrication specs for the zebrafish and bilayer projects, plus the COLLABORATIONS.md structure and top-level README section. Let me read through these files in batch.

I should also check the Nebius Levin claim test verdicts and its related folds, look at physics/PRIOR-ART.md and open-problems/SOURCES.md for orx usage, review the generative providers like NVIDIA NIM and Nebius, and see if there are any successful NIM runs by checking the esmfold runs directory.

I also want to peek at the protein backend header file, see if the lean/nanopubs mentions NVIDIA via Kimura, check the README's top section for where a sponsors area might fit, and review COLLABORATIONS.md. I should note the Frontier summary mentioning Nebius jobs run by the morphoswarm collaborator as a quoted-but-unverified data point since it's their record, not ours.

I still need to check the verdicts and folded results from the three Levin tests, and tally up the Nebius operation counts across the cellpose.json files for both tissues and segmenter-bias cases.

Beyond that, I want to trace the NVIDIA angle: the BioNeMo NIM attempts were refused with 401 errors, the generative protein backend got wired up but never tested, and the AMBER GPU run for kcnk5b looks like it used university cluster hardware rather than an actual NVIDIA service — I should verify this against the README and the sponsor-integration chat log, plus the rejected Brev key issue in the development record.

For OpenResearch, I'm tallying usage: six headline claims, 59 prior-art discover calls, nine physics calls with six rate-limited failures, and twelve open-problems runs, and I still need to check the assess README and claim-sources directory for more context.

I also need to check the assessors.json file for an NVIDIA-hosted model mention and look at the compliance script to see if it's doing grounding checks against OpenResearch.

Finally, for Formlabs I want to verify whether anything was actually fabricated — checking the flying-zebrafish print/QA docs, the anatomy model print, and the preregistered-but-unprinted bilayer, by searching the fabrication notes and dashboard for any "printed" confirmations.

I found that NVIDIA Brev L40S was used to serve a Qwen assessor, so I want to check that README, verify whether the Nebius levin folds completed, figure out where the kcnk5b cluster actually ran (likely Northeastern's Discovery cluster rather than Nebius), and look into how many Aristotle claims were assessed by Qwen on Brev.

I should also look at the Nebius Scientific AI Platform MCP to see what tools it exposes, and check whether those ESMFold2 runs actually completed—the runs.json entries only show operation_id, suggesting results weren't collected since data/ is gitignored. I'll inspect one entry fully to confirm.

So the folds were submitted but results aren't recorded in the repo—I should state that plainly. Similarly, there's no QA.md or PRINT.md in out/, only stl/3mf/assembly.json, and SWARM_COORDINATION notes print outputs haven't been checked yet, so nothing's actually been printed according to the repo. I'm also noting that the kcnk5b GPU work ran on a university cluster, not a sponsor service, so I shouldn't attribute it to NVIDIA. Let me also grep issues.cache.json for sponsor-integration labels to match up hackathon issue numbers (NVIDIA, Formlabs, Nebius, alphaXiv).

I need to grab the issue numbers, so I'll check via gh quickly.

Issue #58 "actually print wings" is closed; let me check what it says before I write the Formlabs document, and confirm the Levin Nebius folds' completion status.

I want to check the last comment on issue #58 to confirm whether the print actually happened, and also look at the dashboard's print view and parts.json for any photo evidence of the printed object.

Good: an actual print happened. Let me read the full print comment and find where the wing files live in the repo.

I have enough now, but let me also check the Nebius issue #4 for what was done, like credits sign-up or the Nebius platform/MCP mention, plus issues #1/#14 for NVIDIA Brev, and glance at the latest comments on #1, #4, #10/#16, and #3.

I want to check whether claim #51's open-weights builder actually ran on Nebius, so I'm searching the repo for "nebius" mentions in compare/token-factory files and docs/claims.json to see if any assessor actually used Nebius inference for evidence.

I'll go with the REPORT's figure of 59 orx discover calls, even though cmdlog shows 76 lines (likely including retries). For issue #51, the open-weights builder on Nebius, I'll mark it as proposed rather than actually run since nothing in the repo confirms execution, and I note the sim-engine's Nebius backend is wired but left unconfigured.

The collaborator's morphoswarm Frontier repo reportedly ran 48 Nebius jobs — I'll cite that as their claim without re-verifying it myself.

Now I'm planning the sponsor documentation: a new `sponsors/` folder at root with individual files for NVIDIA, OpenResearch (alphaXiv), Nebius, and Formlabs, plus an index README, each covering what was used, where in the repo, results, gaps, open issues, and verification status. Time to draft these.


I've confirmed how each sponsor's tools and data appear in the repo—NVIDIA, OpenResearch, Nebius, and Formlabs—covering model runs, searches, segmentation, and 3D prints. Now writing the four sponsor documents based on these findings.

I'm checking that the 566 count corresponds to qwen entries by searching for "qwen" occurrences in assessments.json, which likely map one per claim — I'll trust this for now but verify alongside other checks later.

I'm double-checking the PreForm version claim against SPEC.md, confirming the dragonfly wings printing note is properly hedged, and now verifying the qwen count and hygromorph Lean module reports before moving on to the signed evidence claims.

The math checks out: 566 claims times three assessors equals 1698 entries. Now I'm figuring out where to place the sponsor services section in the README, deciding to add it right before the repository layout section, and I'll also need to reference the sponsors directory in the file listing.

Actually, wait—Anthropic, OpenAI, and Google services are used elsewhere (Claude as agents, GPT/Gemini as assessors), so saying nothing runs on those services is inaccurate. I need to correct that: these providers are used as model backends throughout, and this particular folder just covers the four tools the user asked about.

Now the README: a highlights section placed before "Repository layout", plus a layout entry.

I realize the wing photo is actually referenced earlier in "The wings" section, so I should correct "photo below" to "photo above" here, and also add `sponsors/` to the layout list.

I'm confirming the README builder only regenerates numbers within the designated markers, so my section outside them is safe, and no script rewrites the whole file. I also decide not to mention the new sponsors folder in AGENTS.md since it's not required, and I'm doing a quick check that referenced links and files actually exist.

All cited paths exist. Done.

## What I added

**`sponsors/`** (new folder, five files), each stating what the service was used for, where the record is in the repo, what it produced, and what was not done. Every number is read from a named file or issue; I recounted the ones that were cheap to recount (Nebius operation IDs, the 566 Qwen assessments) and said so.

- `sponsors/NVIDIA.md`: Brev L40S served a self-hosted Qwen3-32B assessor over all 566 Aristotle claims (`scripts/assess/`); BioNeMo ESMFold NIM called and refused with 401 (no `nvapi-` key), recorded as a run and as unsigned nanopub drafts; ProteinMPNN/RFdiffusion/Evo2/ESMFold NIMs wired into `sim-engine` but never exercised. ALCHEMI and DGX Spark not used.
- `sponsors/OPENRESEARCH.md`: `orx discover` grounding made a release requirement (A2): six headline tests (5 of 6 already answered by prior work), the 59-search prior-art report (Phenoscape as closest prior work; "first formal verification of biology" ruled out), the physics thread (OpenAlex rate-limited, logged), the open-problems catalogue. Only `orx discover`, no experiment runs; no run identifier because the tool issues none.
- `sponsors/NEBIUS.md`: 19 Cellpose operations testing three Thompson cell-packing claims, including the segmenter-bias null that cut `ch07-04` confidence 0.60 → 0.35; 23 ESMFold2 operations for three pre-registered Levin tests, verdicts not yet computed. The sibling project's 48 Nebius jobs quoted as not re-verified.
- `sponsors/FORMLABS.md`: two 140 mm SLA dragonfly hindwings actually printed ([#58](https://github.com/fractastical/delphi/issues/58)); the 71-STL winged-zebrafish kit, the flying-zebrafish STL/3MF and the pre-registered hygromorph bilayer test designed to Formlabs specs but not printed; PreForm API documented, not exercised.
- `sponsors/README.md`: index table.

**`README.md`**: a new "Sponsor services: what we used" section (four-row highlights table linking to each file) before "Repository layout", plus a `sponsors/` entry in the layout list.

## Two things worth knowing

- The repo has no print log or `.form` file for the dragonfly wings; the print is attested only by the issue comments and `assets/arigomphus-wing.jpg`. The Formlabs file says so.
- The three Levin Nebius tests are submitted jobs with pre-registration, not results. I described them that way rather than counting them as Nebius-backed verdicts.

_Tools used: Grep ×10, Read ×15, Shell ×13, StrReplace ×4, Write ×5_

### 2026-11-01 11:29 — Turn 2 (User)

> we did print seeral of the flyigh zebra fish i have them ehre

**Assistant:**

Since the repo itself has no record of the print, I should update the Formlabs doc and README to note that several flying zebrafish (from fabrication/flying-zebrafish/out/flying-zebrafish.stl) were printed per the operator's statement on Nov 1, 2026, while flagging that no photo or log exists yet and suggesting one be added.

Updated. `sponsors/FORMLABS.md`, `sponsors/README.md` and the README table now record that several flying zebrafish (`fabrication/flying-zebrafish/out/flying-zebrafish.stl`/`.3mf`) were printed, attributed to your report on Nov 1, alongside the two dragonfly wings.

One gap remains on the evidence side: the repo has no photo or print record of the zebrafish prints, so the row says so explicitly. If you drop a photo into `assets/` (e.g. `assets/flying-zebrafish-prints.jpg`), tell me and I'll cite it in both files and the README, the same way the dragonfly wings cite `assets/arigomphus-wing.jpg`. Knowing which printer and resin were used would also let me replace "the hackathon's Formlabs printers" with the specifics.

_Tools used: StrReplace ×6_

### 2026-11-01 11:34 — Turn 3 (User)

> let's post to frontier isseu with an issue for this too for him to add to thse with a pull request

**Assistant:**

I want to open an issue on kganjam's delphi-frontier repo asking him to add their sponsor usage via pull request, referencing the sponsor files on fractastical/delphi and their sibling's Nebius record with 48 jobs plus possibly NVIDIA usage. Let me verify the repo exists before opening the issue.

The sponsor files haven't been pushed yet, so the issue link won't resolve until I do that. I want to commit and push the sponsors directory, but I need to be careful since README.md shows uncommitted changes that might belong to other agents—I should verify the README diff only touches my section before including it.

The README has another session's uncommitted edits mixed in, so I'll commit and push only `sponsors/` so the issue's links resolve, and leave the README commit to you.

The README has uncommitted changes from another session, so I'll only commit and push the sponsors directory to keep links resolving, leaving the README alone, then go open the issue on kganjam/delphi-frontier.

Opened [kganjam/delphi-frontier#9](https://github.com/kganjam/delphi-frontier/issues/9): it links the five `sponsors/` files, quotes the Frontier Nebius numbers we currently carry as "not re-verified", and asks for a PR against `fractastical/delphi` adding a Frontier section per service in the same shape (what it was used for, where the record/receipt is, what it produced or failed, what was not used).

To make those links resolve I committed and pushed `sponsors/` on its own (`8989af75`). I did not commit `README.md`: it has another session's day-by-day edits mixed in with my sponsor section, so that commit is yours to make when that work is ready.

_Tools used: Shell ×4_
