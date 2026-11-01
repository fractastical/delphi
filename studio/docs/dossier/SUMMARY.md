# MorphoSwarm Studio — complete summary

**One file.** Everything from the ten dossier pages, consolidated: what the system is, how
it was built, what it measured, what it used, and what it does **not** establish.

**Live site:** https://frontier.morphoswarm.ai · **Repository:** https://github.com/kganjam/delphi-frontier
**Agent endpoint:** `https://frontier.morphoswarm.ai/mcp`

Every figure was read from the site's own published data snapshot, from a receipt file
named beside it, or from a live command run at the time stated. Where a figure is unknown,
this says unknown rather than estimating it.

---

# 1. The one-paragraph version

Biological engineering spans molecules to ecosystems, and the models at each scale were
built by different communities with incompatible units, assumptions and contexts. We built
a shared workspace where a design goal — engineer toward a flying fish — forces those
models to meet, and where every junction is either checked, labelled as an assumption, or
**refused**. Underneath it is a Lean 4 proof base so the laws being reused are stated
exactly and checked mechanically. Around it is a record layer where claims carry their
conditions and review status, and an MCP endpoint so other agents can read and contribute.
The flying fish is an engineering candidate, not a viable organism; what we claim is the
method, the evidence trail, and the map of what is missing.

**What we do not claim:** no biological validation; no organism built; no wet-lab
experiment; no measured advantage for multi-agent over single-agent work; no calibrated
bridge between biological scales; total provider spend unknown.

---

# 2. Scale of the effort — measured

## 2.1 Tokens

Read by streaming **18,198 session transcripts** across the build host and seven
Orchestra-managed accounts, summing the `usage` block of every assistant message.

### Since 2026-10-30 (the event window — 687 transcript files)

| Measure | Tokens |
|---|---|
| **Cache read** | **49,642,734,476** (49.6 billion) |
| **Output generated** | **178,002,683** (178 million) |
| Cache creation | 465,394,749 |
| Fresh input | 342,598 |
| **Assistant messages** | **160,546** |

### All time across these accounts

| Measure | Tokens |
|---|---|
| Cache read | 141,749,753,482 (141.7 billion) |
| Output generated | 618,985,553 (619 million) |
| Cache creation | 2,573,117,395 |
| Fresh input | 46,577,722 |
| Assistant messages | 601,938 |

Agent loops re-send their context every turn and hit the prompt cache, so cache-read
dominates: that is why it is reported separately rather than folded into one headline
number. **Output tokens are the honest measure of generated work: 178 million in the event
window.**

### Per account (all time)

| Account | Messages | Output tokens | Cache read |
|---|---:|---:|---:|
| build host | 353,380 | 322,774,745 | 103,046,275,930 |
| max_gmail | 91,745 | 111,339,749 | 14,317,208,158 |
| max_outlook1 | 60,511 | 73,763,501 | 9,571,177,816 |
| max_outlook2 | 48,030 | 52,072,533 | 6,871,012,674 |
| max_outlook | 33,580 | 40,874,183 | 5,865,561,359 |
| max_allen | 7,189 | 10,343,718 | 1,163,483,522 |
| max_outlook3 | 4,675 | 4,846,820 | 575,346,435 |
| ent_allen | 2,828 | 2,970,304 | 339,687,588 |

**Not included:** Codex/GPT sessions (a separate 6,778 transcript files), Gemini calls
beyond the two receipts below, and any provider-side usage outside these transcripts. The
true total is therefore **higher** than the table, not lower.

## 2.2 Models actually used

Fourteen distinct models appear in the transcripts, by assistant-message count:

| Model | Messages |
|---|---:|
| Claude Opus 5.5 | 267,497 |
| Claude Opus 5 | 173,463 |
| Claude Sonnet 5.5 | 96,156 |
| Claude Haiku 5.5 | 55,040 |
| Claude Opus 4.8 | 5,866 |
| Claude Sonnet 4.6 | 2,191 |
| **MiniMax-M2.7** | 905 |
| Claude Fable 5.1 | 375 |
| **GLM-5** | 296 |
| **MiniMax-M3.1-Flash** | 79 |
| Claude Haiku 4.5 | 42 |
| **GLM-4.5** | 20 |
| Claude Fable 5 | 4 |
| Claude Opus 4.7 | 2 |

Plus, outside the Claude transcripts: **Gemini** (`gemini-embedding-001`,
`gemini-3.8-flash`, `gemini-4-argon`), **Evo 2**, **OpenFold2**, and the hosted scientific
models on the Nebius Scientific AI workbench. This is a genuinely multi-model system, not
one vendor.

## 2.3 Agents and sessions

| | Count |
|---|---:|
| tmux agent sessions on the build host | **43** |
| live agent processes | **47** |
| purpose-built simulation harnesses (`ff-*`) | **12** |
| transcript files scanned | **18,198** |
| transcript files active in the event window | **687** |

The 43 comprise 17 general `claude-NN` sessions, 4 `codex` sessions, 11 named role
sessions (`dx-corpus`, `dx-critic-r1`, `dx-submit`, `dx-guilds`, `dx-market`, `dx-gpuops`,
`dx-collab`, `dx-fable-lead`, a director and two retired), and the 12 harnesses. Not all
are active; several are spend-capped or quota-exhausted, and this count does not claim
they are working.

### The twelve harnesses

Each owns one scale or question, runs in its own git worktree on its own branch, submits
its own cloud jobs under its own name prefix, and writes its own status file.

| Harness | Owns |
|---|---|
| `ff-evo` | Evo 2 regulatory sequences, fin and scale candidates |
| `ff-mol` | molecular and cell scale; structure, signalling |
| `ff-tissue` | tissue and developmental; patterning, growth |
| `ff-organ` | organ and organism; fin mechanics, aerodynamics, glide |
| `ff-neuro` | neural; escape, CPG, glide stabilisation |
| `ff-eco` | ecological and collective; reachability, schooling |
| `ff-zf2ff` | the zebrafish-to-flying-fish project |
| `ff-xeno` | the preregistered microcarrier endpoints |
| `ff-voxgpu` | unblocking the GPU voxel engine |
| `ff-xenomodel` | actuation equations, a Lean family, PhysiCell |
| `ff-xenomorph` | cell aggregation into printable morphology |
| `ff-sitecritic` | independent Playwright critique of every route |

They hand work to one another through **files**, not conversation, so a worker can pick up
another's output without shared memory.

## 2.4 Commits

| | Count |
|---|---:|
| Commits in `kganjam/delphi-frontier` | **1,595** |
| Of those, made since 2026-10-30 | **1,595 (all of them)** |
| Repository created | **2026-10-31 14:49 UTC** |
| Branches | **158** |
| Tracked files | **6,684** |
| Commits co-authored by a named model | **703** |

The repository was **created during the event** and every commit in it was made during the
event. Co-authorship breaks down as 426 Sonnet 5.5, 150 Opus 5, 120 Opus 5.5, 7 Opus 4.8.
Branch prefixes: 131 `work/`, 10 `codex/`, 10 `claude/`.

This excludes the sibling repositories (`fractastical/delphi`,
`kavitakoolkarni-bio/morpholib-delphi-branch`, `kavitakoolkarni-bio/delphi-portal`), which
carry their own commit histories.

## 2.5 GPU, CPU and services

**Nebius H100**, project shared with other hackathon teams:

| | Jobs |
|---|---:|
| All jobs listed in the shared project | **123** |
| — completed | 87 |
| — failed | 23 |
| — cancelled | 6 |
| — running at read time | 2 |
| Carrying our name prefixes | **77** |
| Submitted by this campaign's harnesses | **28** |

Campaign jobs: 19 completed, 2 running, 2 failed, 1 error, 1 provisioning. Every job is
1 GPU. Failures are kept in the record.

**Measured GPU utilisation** — the only real evidence, sampled at 1 Hz:

| Task | Samples | Mean | Max | Power |
|---|---:|---:|---:|---:|
| `ns2d-refine-h100` | 181 | **98.6%** | 100% | — |
| `ns2d-shear-demo-h100` | 52 | **96.6%** | 100% | 454 W |
| `heldout-validation-h100` | 149 | 51.6% | 55% | 121 W |

Allocation is not utilisation. Three sampled windows do not establish continuous
saturation, and the jobs used a small fraction of each 80 GiB card.

**CPU.** Google Cloud project `scienceclaw26bos-3016`: 5 instances, 1 running (16 vCPU),
quota 32 vCPU and 0 GPU; the lab account is scheduled for deletion. A Nebius CPU request
was refused with `ResourceExhausted` (limit 24 vCPU against 28 requested); a later bounded
4-vCPU job was admitted.

**Service and model receipts.**

| Receipt | Measured |
|---|---|
| Discovery embedding index | 2,444 documents embedded, 49 requests, 0 failed, 768 dimensions, 45-second window |
| Bioservices Gemini ledger | 4 calls, 7,556 input / 9,700 output tokens |
| Bio-service harvest | **105 API calls, 95 succeeded, 10 failed** across UniProt, Europe PMC, NCBI E-utilities, NCBI Datasets, Ensembl, BioModels, ZFIN |
| Structure prediction | 4 OpenFold2 predictions (mean pLDDT 41–56, low confidence, labelled) |
| Systems biology | 5 BioModels CPU simulations at curated defaults |

**Cost: unknown.** The billing meter was never queried. Zero worker creations from two
failed launch attempts does not establish zero spend.

---

# 3. What the system is

Five human surfaces and two machine surfaces, one deployment.

| Surface | What it is |
|---|---|
| **Studio** | The flying-fish project across eleven scales, each panel holding sources, models, equations, media **and its gap** |
| **Frontier** | Open questions as records: field questions, project gaps, questions the design generated |
| **Knowledge** | 21 seeded claims with conditions and review status, a graph view, semantic search over 2,444 embedded documents |
| **Evidence** | Sources with read-levels, preserved disagreements, replayable results, hashed artifacts |
| **System** | The build inspecting itself: specs, owner board, receipts, resources, unknowns |
| **REST API** | records, search, events, artifacts, graph, counts, bounded calculation |
| **MCP** | 21 tools — 18 read, 3 opt-in write |

**The eleven scales:** molecular · macromolecular · subcellular · cellular · tissue ·
organ · neural · organism · developmental · collective · ecological.

**MCP tools.** Read: `frontier_search`, `frontier_get`, `frontier_neighborhood`,
`frontier_events`, `frontier_artifacts`, `frontier_capabilities`, `frontier_discover`,
`frontier_graph`, `frontier_catalogue`, `frontier_project_inspect`,
`frontier_design_context`, `frontier_artifact_inspect`, `frontier_simulate`,
`frontier_engineer`, `frontier_proofs`, `frontier_formalize`, `frontier_belief`,
`frontier_plan_experiments`. Write, opt-in: `frontier_propose`, `frontier_lease`,
`frontier_transition`.

Public reads need no login. Writes need an **individual contributor credential**; each
request authenticates as its own principal and the server holds no shared token. A
proposal enters as `proposed` and waits for review elsewhere. **Recorded check: 12 of 12
passed**, including rejection of anonymous writes, with zero scientific records written.

---

# 4. How it was built

**Store.** PostgreSQL 16 with pgvector on its own instance and port. Nine record types
with explicit field contracts. Every record carries namespace, kind, id and a
**content-addressed version**, so a reference pins exact bytes.

**Review is separate from the record.** There is deliberately **no accept tool**.
Proposing returns `proposed`, never `accepted`. An upstream label is an assertion by that
upstream, never local acceptance.

**Web application.** Vanilla JavaScript, no bundler, no npm build step. Two vendored
libraries with licence files and verified digests: KaTeX 0.16.47 and three.js 0.170.0. The
only build step is a data snapshot that hashes every input — currently **848 files** — and
copies a video or mesh into the published tree **only when its bytes match the declared
digest**.

**Snapshot or live.** The page asks `/api/health`. If the node answers, records, search
and solvers read it; if not, the page falls back to the committed snapshot **and says so
in a banner**. An interface the node does not serve raises `Unavailable` and the UI shows
no result rather than a plausible one.

**Releases.** The service runs from `app -> releases/<40-hex commit sha>`, an immutable
`git archive` of exactly that commit plus a build-info receipt. Only committed content is
archived, so a working tree cannot leak into a release. Deploys swap the symlink
atomically, restart, health-check three times in a row, and **roll back automatically on
any failure**. The predecessor stays on disk and addressable.

**Specifications.** Eighteen specs published with paths and sha256 digests: record types;
contribution and review lifecycle; actions, leases and execution; bundles, fork-on-conflict
and what a digest is not; the demo's acceptance list; action proposals and learning;
studio and discovery; holistic design assurance; the agent workspace; the launchable
glider; behaviour and ecology; genetic blueprints; adaptive experimentation; the biodesign
compiler; robust inverse design; demo videos; self-validation.

**Work organisation.** An owner board records **24 deliverables** at P0/P1/P2, each with a
named owner and a next acceptance.

**Two levels of claim, kept apart in code, not just prose:** *author report* (what the
repository's documents say — checkboxes, status, owners, plans) and *measured* (what a
receipt records — a run with its hash and result). **A receipt covers only what it says it
covers.**

**Progress, honestly.** The goal checklist stands at **18 of 34**. **SPEC-005's own
11-item acceptance list is entirely unchecked** — several underlying capabilities exist
and are demonstrable, but the end-to-end acceptance each item demands was never recorded.
We would rather show an unchecked box than a checked one we cannot evidence.

---

# 5. Why: motivation and prior art

**Why design a whole organism.** Studying one mechanism at a time hides where mechanisms
disagree. Building one design forces the question every model skips: *does the output of
this model mean the same thing as the input of that one?* The gaps that appear are a map
of what is unknown, and **the gap list is the scientific output**.

Two directions meet. **Bottom up:** fit known biology with equations and sourced
parameters. **Top down:** start from a goal and derive what tissue, material and flow
properties it would require. Where they disagree, there is a question to work on.

**Why Lean is the foundation.** Every other capability depends on laws stated exactly with
their conditions attached. Once a law is formalised, solvers can use it, generators can be
constrained by it, and a second project can reuse it without re-deriving or misreading it.

**What we build on:** form, function and development (Darwin's own flying-fish passage is
a cited source); multiscale mechanobiology as a framing that treats forces, cell behaviour
and tissue structure as one connected problem; knowledge that carries its context (ASK);
generative models of mechanism, where forward simulation trains a model and equations and
experiments decide; computationally designed organisms as the precedent for a design loop
with the evidence trail kept; open contestable claim networks and nanopublications.

**How we differ.**

1. **Refusal is a first-class result.** We publish the junctions we will not make, and why.
2. **Mechanically checked laws under the design**, not around it.
3. **The record refuses to accept.** No accept tool; review and identity separable.
4. **Receipts for failures too** — failed jobs, a quota refusal, an unconverged variant, a
   stopped protocol.
5. **The gap map is the product.**

---

# 6. The formal core: Lean for biology

Lean 4.35.0 (commit `eb6cafb7`) with a pinned Mathlib revision `56a0058`. Recorded runs:
the site does not run Lean, and a family whose files changed since its receipt is marked
**stale** with its source withheld.

| Family | What it states | Statements | Mutants rejected |
|---|---|---:|---:|
| Geometric similarity | Scale by ratio *k*: wing loading scales as *k*, level-flight proxy speed as √*k* | 9 | 4 / 4 |
| Unit algebra | Units as dimensions; conversions and interval mappings checked | 7 | 4 / 4 |
| Cantilever guard | A small-deflection bound for a fin ray, **plus** a proof its hypotheses are satisfiable | 3 | 1 / 1 |
| Oxygen transport | Centre-content bounds for sphere and slab under steady diffusion with uptake | 8 | 4 / 4 |
| Scaled threshold intervals | Two recorded intervals shown incompatible with a factor-of-two band | 10 | 4 / 4 |

**Totals: 37 definitions and theorems, 17 of 17 mutants rejected, all five families
current.** Positive runs exit 0 using only Lean's three standard logical axioms; negative
runs exit 1, the required result.

**What makes a proof count.** A theorem can compile and be worthless. Three checks:
it must mention the model's actual parameters; it must **fail when the law is changed**
(all 17 mutated variants were rejected — a small hand-written set, showing sensitivity to
the mutations we thought of, **not** a coverage measure); and its hypotheses must be
satisfiable.

**The solver bridge.** The constraint solver reported `unsat` on a conflict between a
level-flight lift proxy, a minimum wing loading and a maximum speed, and emitted a
**conflict certificate** compiled inside the positive Lean run. The same certificate with
the speed cap changed from 10 to 20 is **rejected**.

**What Lean does not tell you,** stated on the page itself: that a statement describes a
fish; that a parameter is correct (the oxygen family supplies no cell-specific value,
boundary condition or tissue calibration); that the Lean text is faithful to a source
passage; or anything empirical.

**Honest scale check.** What is formalised so far is textbook-level — similarity scaling,
unit bookkeeping, a beam bound, steady diffusion. Not yet biological mechanism. Its value
today is as a worked pattern for how a law, its assumptions and its checks are stored.

---

# 7. Simulations, and the layer that refuses to connect them

**31 recorded runs across 9 of 11 scales**, each with a manifest, scope, numerical checks,
hashed inputs and verified media, all labelled **simulated, not observed**.

| Scale | Runs | Examples |
|---|---:|---|
| molecular | 4 | OpenMM MD (CPU and CUDA, plus a continuation), OpenFold2 for KCNJ13 |
| subcellular | 1 | Zebrafish-GEM genome-scale metabolic model |
| cellular | 10 | Delta-Notch replay from published SBML, BETSE bioelectric, motor-clutch mechanobiology, Morpheus multicell |
| tissue | 12 | reaction-diffusion fields, fin-ray bilaminar mechanics, ERK wave, epithelial closes-vs-arrests **with a control arm** |
| developmental | 4 | neural cellular automata: pattern, seed placement, curriculum |
| organ | 7 | fin mechanics, 2D wind tunnel, aeroelastic coupling and a fidelity arm |
| neural | 1 | central pattern generator |
| organism | 10 | fixed-launch glide, WaterLily 3D CFD at L128 and L192 (Re 1000), fish3d render, Voxelyze travelling wave |
| **collective, macromolecular** | **0** | **empty — published as gaps** |

**The coupling layer.** Each model declares a typed interface
(`frontier.model.interface/1`): ports with quantity, unit, dimension, **scale**,
**context**, regime, provenance status and bounds. Three verdicts:

| Verdict | Meaning | May it run? |
|---|---|---|
| `composable` | Typed identity, exact unit conversion, or a registered calibration | yes |
| `scenario` | Only under named assumptions, unknown bounds or uncertainty | yes, labelled, never evidence about an organism |
| `refused` | A bridge is missing or inconsistent | **no** |

**Current manifest: 4 composable, 5 scenario, 4 refused.**

**The refusal that matters most.** Delta-Notch asymmetry (cellular) feeding fin flexural
rigidity (organ) is **refused**: no mapping declared; scale changes cell → organ; context
changes from the SBML's annotated species to the flying-fish design envelope; and the
Delta-Notch model is non-dimensional as stored. An assumption may differ in *regime* only
— **an assumption can never stand in for a transfer across biological scale or context.**

**Registered calibrations today: NONE.** That is the most important number on the page,
and why every cross-scale bridge is refused or assumption-level. The manifest carries an
explicit `must_not_say` list: *"the models are coupled"*, *"validated multiscale model"*,
*"the fin pattern is explained"*, *"Lean proves the biological correspondence"*.

---

# 8. Evidence, validation, and corrections

## What was measured

| What | Result | Covers — and does not |
|---|---|---|
| Lean check of the constraint certificate | all recorded checks passed | three constraints and four mutants; **not biology** |
| Glide numerical controls | all pass | analytic and step-halving controls of a point-mass model; **not a fish** |
| Attestation quote check, 15 items | 15 of 15 quotes found; **judgment 4 of 15 clean** | a hand-picked sample; **not a population rate** |

The attestation check went against us: all 15 quotes existed, but only 4 were clean — 3
`stance_overstated`, 4 `scope_narrower_than_question`, 2 with the question's core only
partly answered, 3 dated, 1 not biology. **A quote can be present and still not state what
the stance claims.** A hash or a matched string establishes neither.

## A check that disqualified our own design

Three printable variants under matched conditions (4° angle of attack, horseshoe vortex
lattice, isolated paired fins). On lattice refinement:

| Variant | Lift-coefficient change | Usable? |
|---|---:|---|
| v3a | 0.5% | yes |
| v3c | 2.9% | yes |
| **v3b** | **26%** | **no — not converged** |

v3b is published with a warning and **no feasibility score**, its non-convergence recorded
as undiagnosed rather than guessed.

## Claim reuse with a null result

One versioned claim, pinned by content hash, used by two distinct scoped actions with
causal order checked, including a **below-threshold** case. Exact rationals carried
through rather than floats. A reuse demonstration that only ever succeeds demonstrates
nothing.

## The review-corrections ledger

Five corrections, with a schema and a hash:

| id | What changed |
|---|---|
| `doe-centered-margin` | Retracted a claim that measurement halves a 0.50 misclassification rate. Root read the code and the arithmetic; the author had only run it. |
| `sequence-compiler-typed-inputs` | A reader built adversarial typed inputs the author's tests had not, and compared snapshots to git objects. |
| `compiler-cache-and-pins` | Reviewers supplied failure cases; stale pins now produce typed **blocked** results instead of passes. |
| `contributor-count-labels` | A headline contributor number moved from **4 to an 11 floor**; 31 stopped being described as active. |
| `doe-mutant-control` | An analytic screen's agreement with 192 recorded flags became meaningful **only after the control could fail**. |

**What the ledger refuses to claim,** quoted: *"that collective work outperforms a single
agent"*, *"any agent-count based advantage"*, *"any scientific breakthrough count"*. On
independence: *"All reviewers are agents or sessions of one fleet sharing one git
identity; none is an independent lab."* And: *"For every entry it is unknown whether one
agent re-reading its own work could have found the same issue."*

Four of five involved information one party had and another did not. That is a real
pattern. It is not a controlled experiment and is not presented as one.

## What was not tested

No wet-lab experiment. No registered calibration between scales. No controlled
multi-agent versus single-agent arm. SPEC-005's 11 acceptance items all unchecked. Total
spend and total model usage unknown. Which commit is deployed is listed among our own
unknowns.

---

# 9. Evidence map against the judging criteria

**Problem significance.** Eleven scales, open-ended, consequential, and the difficulty is
not compute — it is that two models each correct in their own paper cannot be connected
without a calibration nobody has measured. *Limit:* a design exercise, not a result about
a real organism.

**Scientific and technical impact.** A formal base (37 statements, 17/17 mutants); a
solver-to-proof bridge; 31 simulations across 9 scales; a refusal layer with 4 refusals and
zero registered calibrations stated plainly; a reusable record layer with 2,444 embedded
documents and 21 MCP tools; and negative results published. **Novelty we would defend:**
treating refusal to connect two models as a first-class published result, and putting
mechanically checked laws underneath the design. *Limit:* no biological validation;
textbook-level formalisation so far.

**Decentralized agency.** Capabilities genuinely distributed: 12 purpose-built harnesses
with distinct tools and context, handing work through files rather than conversation; 24
board deliverables with named owners; atomic leases and fork-on-conflict bundles so
independent operators could review elsewhere. *Limit, in our own words on the site:* much
of the event work was handed out by a single coordinating session; the node, database and
site are **one deployment**; there is no running federated network, and we do not claim a
decentralised architecture was exercised.

**Collective capability.** The corrections ledger, where in four of five entries the
correcting party held information the author did not, producing a retracted benefit claim,
a corrected contributor count, and a cache that now returns typed `blocked` results.
*Limit:* a retrospective process trace, not a controlled benchmark. A proper measurement
needs a preregistered shared-versus-isolated arm, published either way. **We did not run
it**, and would rather be marked down for a missing experiment than claim an advantage our
data cannot support.

**Execution and validation.** Publicly reachable; separate PostgreSQL with pgvector;
public MCP with 12/12 checks including anonymous-write rejection; immutable
commit-addressed releases with automatic rollback. Validation that could fail and sometimes
did: 17/17 mutants, a rejected corrupted certificate, step-halving controls, a refinement
check that disqualified a variant, a control arm, and an attestation check that failed its
own corpus. *Limit:* SPEC-005 acceptance 0 of 11; goal list 18 of 34.

**Collaboration bonus.** Reusable today: a public MCP endpoint readable without
credentials; domain-independent record contracts and the coupling interface schema; the
coupling checker itself with refusal as a legitimate verdict; the anti-triviality
discipline for formal claims; hashed artifacts and printable meshes with declared units.
*Limit:* we are not aware of another team having reused these during the event. We claim
availability and fitness for reuse, not demonstrated uptake.

---

# 10. Resources we are thankful for

**People and partners.** The team — Kris Ganjam (Allen Institute) and collaborators, with
Kavita Koolkarni's Delphi portal and Joel Dietz's Delphi claim work as sibling efforts.
**Nebius** (H100s and the Scientific AI workbench, 69 hosted tools). **Google** (Gemini
models and Google Cloud). **NVIDIA** (BioNeMo, Brev, CUDA). Upstream communities: the
nanopublication network, BioModels, UniProt, Ensembl, NCBI, ZFIN, Europe PMC, FishBase.

**Open-source code.** Lean 4.35.0 + Mathlib · Z3 5.3.3 · PostgreSQL 16 + pgvector · MCP
SDK 1.27 · libRoadRunner 2.10 · BETSE 1.5.0 · Morpheus 2.3.9 · OpenMM 8.4 · OpenFold2 ·
Evo 2 · WaterLily.jl 1.10 · Voxelyze · manifold3d 3.5.4 · trimesh 5.2 · NumPy 2.4 · SciPy
1.17 · RDFLib 7.6 · KaTeX 0.16.47 (MIT) · three.js 0.170.0 (MIT) · pytest 9 · Playwright.

**Mathematics and source texts,** each with a read-level: Darwin 1859 *Origin of Species*
ch. VI (full text) · Fish 1990 wing design and scaling (full text) · Park & Choi 2010
gliding aerodynamics (full text) · Davenport 1992 wing-loading (abstract) and 2003
allometric limits (listing) · Lovejoy et al. 2004 beloniform phylogeny (abstract) · Xu et
al. 2013 stem neopterygian (search summary) · Daane et al. 2021 the *lat4a* × *kcnh2a*
interaction phenocopying flying-fish fin proportion (full text) · Collier et al. 1996
Delta-Notch · Alben et al. 2007 fin-ray mechanics · Hayden et al. 2021 ERK trigger waves ·
Wang et al. 2021 Zebrafish-GEM (CC-BY-4.0). *Listing a source is not reading it, and a
search summary is a lead rather than evidence.*

**Data.** BioModels, UniProt, Ensembl, NCBI Datasets and E-utilities, ZFIN, Europe PMC,
FishBase, Delphi claims and nanopublications imported with provenance preserved. NCBI
lists exactly one Exocoetidae genome: *Hirundichthys speculiger* **GCA_018398805.1**;
Ensembl has none, so medaka is the nearest annotated proxy.

**Licences.** All vendored web libraries are MIT with licence files and verified digests.
Imported records keep upstream licences. Darwin's text is public domain.

---

# 11. The Xenobot / computationally designed organism line

A **12-engine catalogue** ranked by value to this project: Voxelyze, Morpheus, BETSE and
OpenMM already running; PhysiCell, CompuCell3D, SOFA SoftRobots (+Inverse),
reconfigurable-organisms, voxcraft-viz and a CPM-DDPM surrogate source-only; voxcraft-sim
**blocked**.

**Real licence findings.** The cdorgs website's licence statement disagrees with the
LICENSE files in the repos it links. `reconfigurable_organisms` declares CC0 at root while
vendoring Voxelyze, whose headers say LGPL-3.0-or-later. `license: null` from the GitHub
API means opposite things in different repos — hiding LGPL for Voxelyze and BSD-3 for
PhysiCell. It reports a missing root LICENSE file, not a missing licence.

**voxcraft-sim, the GPU engine the published work used, does not compile on modern CUDA.**
The probe ran and failed honestly: source fetch verified (1,247,489 bytes, sha256 matched,
14/14 files match the pin); CMake configured against CUDA 13.1 with arch forced to
`sm_90`; the build failed on **`cudaDeviceSynchronize` called from device code** at ten
sites, an API removed from device code in CUDA 12, plus a Boost 1.83 header failure under
nvcc 13.1. Receipt status `COMPILE_FAIL`, first error preserved verbatim, no retry.

**The audit that corrected us.** An independent Voxelyze review **withdrew an agreement
claim**: an earlier "~2.74%" used changing denominators; recomputed, raw SI displacement
differs by **15.5739%**. One frozen check still **fails** its bound (0.017479 against
0.01). A spread claimed as "about five orders" is **4.2277**. The artifact is a **45 g
soft-voxel ground-contact benchmark, not tissue, not a microcarrier**, and its prescribed
thermal expansion is **not** measured cellular contractility.

**The microcarrier project** holds three **preregistered endpoints with falsifiers** —
`passive-control`, `pattern-dependence`, `mirror-symmetry` — and `runner: null`. The
experiment was fully specified and never run; harnesses are now executing it. Its sources
are read at **abstract level only**, and the record keeps visible that the published
constructs move by **cilia** while contraction is this project's own modelling choice.

---

# 12. If you read only one thing

Open https://frontier.morphoswarm.ai/#/studio/flying-fish and count how many scale panels
say *"no model exists"*. Then open `/#/engineering` and see which model connections were
refused. The claim is that **publishing those two lists honestly is more useful than a
polished pipeline whose joints are unsupported** — and that a mechanically checked base of
laws is what makes the refusals principled rather than merely cautious.
