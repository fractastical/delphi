# 90-second pitch — MorphoSwarm Frontier

**CHECKPOINT, ready to present.** Pitched release: `12eb390` on
`codex/frontier-demo-20261031`, live at `https://frontier.morphoswarm.ai/` (HTTP 200), API
healthy. **Not `origin/main`.**

**Live counts, with receipt.** `POST /v1/read/search`, cursor-paginated at limit 50: **912
Claims (19 pages), 261 Problems (6 pages), 6 Evidence, 5 Actions.** Re-run before the room.

---

## The thesis

**Designing a whole organism end to end is a way of mapping what we do not know.** You cannot
finish the design without hitting every place the science runs out — and each of those places is
a research problem, located rather than guessed.

MorphoSwarm Frontier is **a design studio on a shared scientific frontier**. **Delphi** is the
claims and evidence foundation. **Flying Fish is the featured project**, not the scope.

## The script

> **MorphoSwarm Frontier is a design studio sitting on a shared scientific frontier**, built on
> **Delphi** — a claims and evidence layer holding **912 claims and 261 open problems** as typed
> records with their sources and scope.
>
> Our featured project asks something a search engine cannot: **design a flying fish that is
> evolutionarily possible, not merely aerodynamic.**
>
> You cannot finish that design. Every attempt runs into a place where the science stops — and
> that is the point. **Designing a whole organism end to end maps the gaps.**
>
> So we borrowed the idea that made protein structure prediction trustworthy. AlphaFold does not
> tell you a protein is eighty-seven percent correct. It gives you **confidence per region**, and
> **separately, uncertainty at the interfaces between regions**. We do the same for a design:
> **a regional assurance map, plus interface uncertainty where two regions must agree.**
>
> And we keep three things apart that are usually blended: **is it formally correct, is it
> numerically accurate, is it empirically supported.** There is no single number for the whole
> fish, because there is no honest way to compute one.
>
> Every low-assurance region becomes a **pinned Problem with an Action** — what would settle it,
> what would refute it, when to stop. When new evidence lands, **the candidate changes and so does
> the map.**
>
> One study. A frontier built to hold many.

**~215 words ≈ 87 s.**

## What is on screen, and what it rests on

| beat | artifact | status |
|---|---|---|
| live store | `frontier.morphoswarm.ai`, API `mode: live` | **verified**, HTTP 200 |
| 912 claims / 261 problems | `POST /v1/read/search`, paginated | **verified with receipt**; re-run |
| regional assurance + interface uncertainty | assurance suite | **26 tests passed, integrated** — reported by native workers, **not re-run by me** |
| MCP, public | 12 official-SDK checks | **live and public** — reported, not re-run by me |
| Studio, public | interactive Hodgkin–Huxley + mechanobio | **live and public** — reported, not viewed by me |
| three candidates | `A-precursor-short-fin`, `B-two-wing-glider`, `C-four-wing-glider` design + glide JSON | **present on the release** |
| fin robustness ensemble | baseline **20/64**, shorter **33/64**, stiffer **34/64** | **a ranking under ASSUMED joint draws and load cases.** Biological success, mass and area costs are **unknown**. See the rule below |
| root SPEC-008 | — | **not on any delphi-frontier branch** when I checked all remotes. Morphoswarm's SPEC-008 is the Postgres schema, unrelated |
| constraints | `exocoetid_check.py`, 8 constraints, each carrying its derivation population | **verified**: 71 tests, exit 0, re-run from the durable copy |
| gap → Problem | `CANNOT-EVALUATE` already returned per constraint | **verified**; the wiring to pinned Problems is the new work |
| simulations | 8 `.mp4` incl. `glide_fixed_launch`, `rd_fields`, `fin_mechanics` | **present**; I have not viewed them |
| geometry | **12 STL mesh files** | **files exist. NOTHING HAS BEEN PRINTED.** Say "print-ready meshes" |

## Rules this pitch must not break

- **No whole-fish probability.** Not a percentage, not a score, not a traffic light for the
  organism. The whole point is that the composite is the dishonest part. Our store already
  refuses this: Assessment carries seven named dimensions and **no composite truth score**, which
  is the same principle the assurance map applies to a design.
- **Formal / numerical / empirical stay separate**, and a region may be strong in one and absent
  in another. Saying which is the product.
- **Nothing has been printed.** Print-ready meshes.
- **No test-function count as passing tests.** Cite a run and its exit code.
- **No swarm or collective gain assertion.** Follow the organisers' own regime map: where one
  channel dominates, coordination buys provenance and auditability, not better discrimination.
- **The fish is the featured project, not the scope.** A listener who leaves thinking we built a
  fish simulator heard the wrong pitch.
- **Darwin, Thompson and Wolfram are optional secondary lenses.** They do not open the pitch.
- **Do not pitch the refutation ledger as the product.**

## Honest framing of the pLDDT/PAE borrowing

It is an **analogy, and we say so**. pLDDT and PAE are calibrated against a structural ground
truth that a novel organism design does not have. So ours is **an assurance map over declared
constraints and their evidence**, not a calibrated predictor — and no number from it is
comparable to a pLDDT value. Stating that difference out loud is stronger than hoping nobody asks,
and it is the same discipline that made the borrowing worth doing.

## The ensemble result, stated so it cannot be overread

**20/64 baseline, 33/64 shorter, 34/64 stiffer.** Two things must travel with those numbers or
they mislead:

1. **The draws and load cases are assumed, not measured.** This ranks three candidates under a
   stated model. It is not a probability that any of them works.
2. **The costs are unknown.** Biological success, mass and area are not in this score. "Stiffer
   survives more load cases" is not "stiffer is better" — a stiffer fin may be heavier, costlier
   to grow, or developmentally unreachable, and none of that is measured here.

So the honest sentence is: *under our assumed joint draws and load cases, shorter and stiffer
variants survive roughly a third of cases against the baseline's fifth, and we do not know what
they cost.* **That gap is itself a pinned Problem** — which is the thesis working, not a caveat
bolted on.

## The Erk model: a retained partial reproduction

A scale-Erk model **reproduces five source bands** and **misses the rise and the
synchrony-growth-impairment**. It is **retained**, not discarded, and shown as a partial
reproduction with the misses named.

This is the assurance map in miniature: the model is strong in one region and absent in another,
and saying which is the product. A single "the model reproduces the paper" claim would be false;
a single "the model fails" claim would throw away five reproduced bands. **Neither is a number
for the whole model, and there isn't one.**

## Positioning against prior art — integration, not a unique graph

**What we claim: the workflow integration.** Goal → sourced constraints → models and simulations
→ artifacts → regional assurance with interface uncertainty → pinned Problems and Actions →
evidence reusable by the next project, end to end on one platform.

**What we do NOT claim: a unique graph, typed objects, artifact lineage, independent review, or
dead-ends-as-artifacts.** ScienceClaw and Infinite implement those and publish them. ASK models
versioned epistemic state. Those are cited, not competed with. The category-theoretic work from
the same group is substantially more formal than ours on model coupling.

**The feature-level difference remains narrow and is the one to say:** the decision rule is
attached to the question before the result exists, and a low-assurance region becomes a pinned
Problem automatically. We are claiming a **loop that closes**, not a novel data structure.
