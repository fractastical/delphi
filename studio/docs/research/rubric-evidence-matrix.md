# Rubric-to-evidence matrix: what is earned, what is missing

Rubric weights relayed from the root session's reading of the live ScienceClaw page; **not
re-fetched by me.** Receipt paths are exact. Evidence levels:

- **M** — measured by me in this session, receipt committed under `data/research/mcp-probe-2026-10-31/`
- **C** — committed artifact in this repository that I opened and read
- **R** — reported by a worker in a message; **not re-run or viewed by me**

A row at **R** may be spoken on stage only with the words "reported by" attached, or re-verified
first. Mixing levels in one table without marking them is the failure this column exists to stop.

---

## Problem Significance and Complexity — 20%

| Claim | Level | Receipt | Status |
|---|---|---|---|
| Whole-organism design maps knowledge gaps; each gap becomes a pinned Problem/Action | C | `frontier/models.py` `completeness` discriminator; `recorded` vs `actionable` with four required fields | **Earned** |
| 250 morphoswarm register problems imported, **0 actionable** | C | `scripts/import_register.py` run output | **Earned** — and the zero is the point |
| 17 sourced proposals, **13 actionable**, 17/17 resolvable URI | C | `scripts/import_sourced_problems.py` | **Earned** (corrected down from 15 after data-access verification) |
| No machine-checked library of mathematical biology exists | — | — | **MISSING**: asserted, never systematically searched. Do not claim on stage |
| Scope conditions are the natural unit because biological results are stated in limits and applied in regimes | C | the mispredication probe is one worked instance | **Partly earned** — one instance, not a survey |

**Honest weak point.** "No such library exists" is the load-bearing significance claim and it has
no negative-search receipt with a stated scope. Either say "we have not found one" or drop it.

---

## Scientific / Technical Impact — 25%

| Claim | Level | Receipt | Status |
|---|---|---|---|
| Textbook Turing criterion's finite-domain error is **windowed, not monotone**: exactly 0.0% at every half-integer multiple of λc; 6.22% at 1.25 λc; **0.58% still at 4.25 λc** (prior Dv/Du log-uniform [1,30]) | C | `bench/mispredication/probe_declared_prior.out` on `origin/codex/resource-utilization-20261031` | **Earned**, with the toy-ensemble limit stated |
| Our own claim *"reliable (under 1%) above 1.5 critical wavelengths"* is **withdrawn** | C | `bench/mispredication/README.md` correction notice, 2026-10-31 12:05 PDT | **Earned** — the strongest single artifact |
| The historical mispredication table was **imported in the seed commit**, not produced during the event; its generating script is not in the repository | C | `636919a` *"Seed Delphi Frontier with the verified artifacts"*, 07:52 PDT; README limit (1) | **Must be stated** — claiming it as event work is false and `git log` shows it |
| Probe committed **before** its output; scratch-run motivation disclosed | C | `bench/mispredication/PROBE_DECLARATION.md` | **Earned** |
| Band criterion vs direct eigenvalues: **3,000 comparisons, 0 disagreements** | C | `probe_declared_prior.json` `band_equals_direct_eigenvalues` | **Earned** (cross-check control passed) |
| Declared control **failed** (89.53% vs declared >90%), threshold not moved, run shipped at exit 1 | C | `probe_declared_prior.out` `PY_EXIT=1`; Amendment 1 in `PROBE_DECLARATION.md` | **Earned** |
| oca2 exon 21 absent from all 1,361,196,561 bp of the Molino assembly; flanking exons present once each | C | `results/2026-10-31-oca2-exon21-molino-RESULT.md` | **Earned** (positive closure) |
| KCNE1 test **stopped**, not failed: 20.27% coverage vs a 75% preregistered floor | C | `results/2026-10-31-kcne1-binding-ddg-STOPPED.md` | **Earned** (a stop is a result) |
| Scale-Erk model reproduces 5 source bands, misses the rise and synchrony-growth impairment; **retained** | R | worker message | Speak as "reported" |
| 357 initial-state perturbation checks at 1e-10, 48 repeats, 0 divergences, max repeat delta 1.32e-14 | R | codex03 message only; **I found no committed receipt** | **Do not put on a slide until a path exists** |
| OpenFold2 zebrafish Kcnj13 362 aa: mean pLDDT 52.86, pTM 0.2728, PAE 22.91 Å | R | codex03 message only; no corroborating file found | Speak as "reported"; the low confidence is the honest reading |
| OpenMM 10,491-atom CPU trajectory, 101 states + MP4 | R | codex03 message | Speak as "reported" |

**Honest weak point.** The headline comparisons we ran and lost are real and should stay in: an
earlier scale study returned **shared specialists 78/100 vs original 78/100** (null), and a
baseline beat us 96/100 vs 78/100. Keeping these is what makes the Turing result credible.

---

## Decentralized Agency — 20%

| Claim | Level | Receipt | Status |
|---|---|---|---|
| An agent falsified a claim the team had **seeded** into the commons; no coordinator adjudicated the verdict | C | correction notice + `PROBE_DECLARATION.md` authored by the critic. Seed `636919a` 07:52 PDT; probe/withdrawal `e4ab195`/`b9f603b`/`81ca466` 12:05 PDT, all 2026-10-31 | **Earned — one instance, event work** |
| Review status is **node-local and separate** from the record: a record carries `local_status`, acceptance needs an independent operator elsewhere | M | `read_search_anonymous.json` (`"local_status": "imported_unreviewed"`); `capabilities.json` (*"there is no review/accept tool"*) | **Earned** |
| Each MCP request authenticates as **its own principal**; the server holds no shared token | M | `capabilities.json`: `"principal": null`, *"the server holds no shared token"* | **Earned** |
| Agents coordinate through the claim graph rather than a dispatcher | — | — | **MISSING as a general claim.** Much of today's work *was* root-dispatched. The one instance above is real; the architecture-wide claim is not measured |

**Honest weak point, stated plainly.** This is the criterion where the gap between what we
designed and what we ran today is widest. The commons supports decentralized review and one real
instance went through it; most coordination today was a root session handing out work. Say the
instance, not the architecture.

---

## Collective Capability — 25%

| Claim | Level | Receipt | Status |
|---|---|---|---|
| The collective caught an error a single agent had published and shipped | C | mispredication correction notice | **Earned, qualitative, n=1** |
| Collective beats single agent at **matched budget** | C | **v3 RAN. All 27 requests valid; every answer and every condition-by-repeat aggregate scored 16/16; all three condition means identical.** `results/capability-agency/results-card.md`, commit `92c86683` | **Measured: CEILING / NULL.** No collaboration or agency advantage. The card names the cause: an answer-explicit packet left no headroom |
| The communication treatment actually executed | C | 9 pinned prior artifacts to the serial analyst, 9 peer artifacts to collaborating specialists, **none** to isolated specialists | **Earned** — the treatment ran; the ceiling left nothing to distinguish |
| v2 and v3 must not be pooled | C | v2: 27 HTTP 200, all truncated at `MAX_TOKENS`, scored zero, 49,626 tokens. v3: 53,802 tokens. Total known Google API usage **103,459 tokens over 57 requests**; USD spend unknown, no billing meter | **Stated in the card itself** |
| Three observational coordination cases (CFD packet repair, adapter refusal, viewer regressions) | C | `results/capability-agency/coordination-case-studies.md`, commit `92c86683` | **Observational only.** The document says explicitly they provide no controlled counterfactual and must not count as evidence of advantage |
| Prior scale study: shared specialists **78/100** vs original **78/100** | R | relayed in the rubric strategy document | **A measured null.** Keep it in the talk |
| Model-family diversity beats sampling diversity at equal budget | — | — | **NOT RUN.** Proposed only |

**We now have a quantitative result, and it is a null of a specific kind.** Not "the collective
tied" — the benchmark saturated. Every arm scored 16/16 on a task whose packet already stated the
source fit, the stiffness range and the measurement method, so there was no headroom for any
treatment to move. The honest sentence is that we measured our benchmark rather than our
collective, and the next pilot needs a task with room to fail. The pitch says this in its own
voice before a judge says it for us.

A null result here is still worth presenting: "we ran the experiment the rubric cares most about
and it said no" is a stronger scientific posture than an unmeasured claim, and it is consistent
with the arithmetic — averaging correlated homogeneous agents adds nothing; the gain regime is
verification asymmetry.

---

## Execution and Validation — 10%

| Claim | Level | Receipt | Status |
|---|---|---|---|
| Public MCP live, **19 tools** (manifest: 15 `read`, 3 `write`), protocol 2025-06-18, server `Delphi Frontier MCP` 1.27.0 | M | `tools_list.json`, HTTP 200 at 2026-10-31T22:08:18Z | **Earned** |
| **Anonymous reads work**: `frontier_search` returns records with no credential | M | `read_search_anonymous.json` | **Earned** |
| **Anonymous calculations work**: `frontier_simulate` returns an HH trajectory in 1.10 s, `calibrated: false`, six model-file sha256s, request sha256, full environment | M | `calc_simulate_anonymous.json`, `computed_at` 2026-10-31T22:10:02Z | **Earned** |
| **Writes are refused**: well-formed `frontier_propose` with no credential → `unauthorized: Authenticated operator token required` | M | `control_write_anonymous_refused.json` | **Earned — this is the must-fail control** |
| Catalogue: **1,287** claim versions, **1,190** with upstream claim id, **1,214** origin unknown, 451 artifact declarations | M | `catalogue.json` | **Earned** |
| Catalogue reports its own unknowns as `null` and `0`-means-unchecked | M | `catalogue.json`: `mapped_species: null`, `structured_conditions: null`, `hosted_and_byte_checked: 0` with *"0 is the absence of any check"* | **Earned** |
| Live release `c1ad527`: **13 public web checks and 35 MCP checks, 0 failures** | C | `deploy/receipts/rayfan-public-live-check.json`, `rayfan-mcp-live-check.json`, both at 2026-10-31T23:14:54Z | **Earned** |
| Nebius tally **at 16:13 PDT**: 52 team jobs (37 current queue + 15 prior team/setup), 30 unattributed, 2 ours running + 1 pulling | R | relayed from root's correction; **not re-derived by me**; infra still reconciling source receipts | Speak **with the snapshot time**, never as a timeless total |
| Earlier job receipts with ids, UTC windows, rc, bytes, sha256 — **failures and cancellations kept** | C | `results/compute/RECEIPT.md` | **Earned** |
| Cost of those jobs | C | RECEIPT.md: *"unavailable ... this is not zero"* | Honest unknown, keep the wording |
| 13-part fish model + six print-ready props, geometry hashes shared with renders | R | print worker message | Speak as "reported". **Never "printed forms"** |
| 26 assurance tests passed, integrated | R | native worker | Speak as "reported" |
| Public Studio with interactive HH + mechanobio | R | native worker; **not viewed by me** | Speak as "reported" |

---

## Collaboration Bonus — +10

| Claim | Level | Status |
|---|---|---|
| Endpoint publicly reachable, anonymous reads and calculations, one-page recipe exists | M | **Ready** |
| **Another team actually used it and got a result** | — | **UNEARNED.** No external contact has been made or authorized. Zero until we hold their receipt |

The recipe is `docs/research/mcp-reuse-recipe.md`. It is written to be executable by a stranger
with curl and nothing else. **It has not been given to anyone**, because outreach is not
authorized.

---

## Generative roadmap — NOT BUILT

Full document with read-levels: `docs/research/generative-roadmap.md`. Page copy: `#/generative`.

| Item | Level | Status |
|---|---|---|
| **RD-1D conditional DDPM pilot**: preregistration, solver, model, controller and tests frozen | C | **`9c56a927`**, 2026-10-31 15:32:36 PDT, committed before any training or held-out evaluation |
| **RD-1D job packet**, hashes, local CPU control receipts | C | **`4a5394f3`**, 15:33:03 PDT; archive sha256 `76eb4a7b…`, 11,526 bytes |
| RD-1D local controls | C | CPU control all checks ok; torch solver = numpy to 1e-9; `tests/test_rd_diffusion.py` **13 passed**. CUDA control **not run here** (no GPU on this host) |
| **RD-1D GPU result** | — | **NONE YET.** The 15-25 min runtime in the packet is an estimate scaled from CPU smoke timings, not a GPU measurement |
| Organism-scale pipeline: datasets, models, candidates, solver-screened, real experiments, GPU hours | — | **0 / 0 / 0 / 0 / 0 / 0 — unbuilt** |
| Diffusion surrogate for a mechanistic **agent-based** biological model (CPM, in vitro vasculogenesis, ~22x) | — | **Published by Comlekoglu et al.**, arXiv:2505.09630 (v1 2025-05-01, v3 2025-10-23), DOI 10.1088/2632-2153/ae11f8, PMC12570967. A close precedent for stages 1-2. Read-level: abstract |
| Physics residuals inside diffusion training | — | **Published by Bastek, Sun, Kochmann**, arXiv:2403.14404 — **v1 2024-03-21**, v4 2025-03-13, ICLR 2025 per the Comments field. Read-level: abstract for metadata |
| Conditional score-based diffusion over simulator statistics | — | **GenCFD**, arXiv:2409.18359, v1 2024-09-27, v2 2025-02-03, 12 authors, **no journal reference on the page**. Read-level: abstract for metadata |
| Physics-informed diffusion in spectral space | — | Gallon, von Wurstemberger, Cheridito, Jentzen, arXiv:2602.09708 (v1 2026-02-10, v2 2026-06-02). Cited on the live `#/generative` page; **verified correct here** |
| Generate → filter → exact-solver gate | — | **Published across several domains, 2025-26.** Read-level: search-summary, no full texts read |
| H1: a withdrawn claim identifies its own derived synthetic data | — | **Hypothesis.** One web search found no prior art; that is a lead, **not** a demonstration of absence |
| H2: the exact solver carries its own scope conditions | — | **Hypothesis**, motivated by our own windowed-error measurement |

**Forbidden:** "first diffusion model for synthetic biology", and any IP claim. The method class is
published; what we propose is the evidence loop around it.

**Removed as unsupported, 2026-10-31:** the roadmap previously called stage 4 "the part nobody has
funded". We have no information about funding, and the sentence is gone.

---

## Event work vs brought in — the System page constraint

| Component | Verdict | Evidence |
|---|---|---|
| Frontier store, HTTP adapter, MCP, public site | **Built during the event** | repo's first commit `c508a423` 2026-10-31 07:49:44 PDT; **all 508 commits dated 2026-10-31** |
| Root About + `#/generative` pages | **Built during the event** | `df98621` 2026-10-31 15:29:05 PDT (`site/js/about.js`, `site/js/generative.js`, `site/css/about.css`) |
| RD-1D diffusion pilot (prereg, code, packet) | **Built during the event** | `9c56a927` 15:32:36 PDT, `4a5394f3` 15:33:03 PDT. **No GPU result yet** |
| Mispredication probe, its failed control, the withdrawal | **Event work** | `e4ab195`, `b9f603b`, `81ca466`, all 12:05 PDT 2026-10-31 |
| The historical mispredication table | **IMPORTED, not event work** | arrived in seed commit `636919a` 07:52 PDT, *"Seed Delphi Frontier with the verified artifacts"*; its generating script is **not in the repository** |
| The claims corpus (1,190 with upstream ids) | **Imported** | `frontier_catalogue`; records read `local_status: imported_unreviewed` |
| morphoswarm repository | **PRE-EVENT** | first commit 2026-10-20, eleven days earlier. **Must not be narrated on the System page as event work** |

**Store facts re-read from source, not from memory:** `KINDS` holds **eleven** record types
(Problem, Claim, Evidence, Assessment, Action, Actor, ResourceOffer, Interest, Event, Project,
Annotation) — I had written "nine" from memory and it was stale. The licence gate has **four**
call sites (`store`, `serve`, `export`, `import`). The Assessment validator requires **all seven**
named dimensions.

---

## The four things most likely to sink us, in order

1. **Collective Capability (25%) has no quantitative result.** Mitigation: say it first, show the
   n=1 instance, commit to reporting the null.
2. **Decentralized Agency (20%) is asserted more broadly than it was practised today.** Mitigation:
   claim the one instance that genuinely went through the commons, not the architecture.
3. **Three Impact numbers sit at level R with no committed path** (the 357 perturbation checks, the
   OpenFold2 confidence figures, the OpenMM trajectory). Mitigation: either land a receipt path
   before the cut or drop them from the slides.
4. **The significance claim "no machine-checked library of mathematical biology exists" has no
   search receipt.** Mitigation: downgrade to "we have not found one" with the scope of what we
   looked at, or cut it.
