# Evidence map against the judging criteria

For each criterion: what exists, where to verify it, and **what we cannot claim**. The
second column is the one we would most like read, because a system that cannot state its
own limits is not evidence of anything.

---

## Problem significance and complexity

**The problem.** Engineer toward a vertebrate glider reachable from a beloniform
ancestor, across eleven biological scales, and make every missing bridge between scales
visible. It is open-ended (no known answer), consequential (the same machinery applies to
any multiscale biological design), and scientifically meaningful (it produces a map of
which measurements are missing).

**Why it is hard in a way that matters.** The difficulty is not compute. It is that a
cell-scale model and an organ-scale model, both correct in their own papers, cannot be
connected without a calibration nobody has measured. Our coupling layer makes that
failure explicit instead of hiding it behind a pipeline.

**Verify:** the studio's eleven scale panels, each with its gap sentence; the coupling
manifest's 4 refusals; the frontier's open questions.

**Limit:** the goal is a design exercise. It is not a cure, a product, or a result about
a real organism.

---

## Scientific and technical impact

**What was actually achieved.**

- **A formal base.** 37 Lean definitions and theorems across 5 families, 17 of 17
  deliberately-wrong variants rejected, standard axioms only, with receipts.
- **A solver-to-proof bridge.** An `unsat` conflict certificate emitted by a constraint
  solver and then **checked by Lean**, with a one-number-corrupted version rejected.
- **31 recorded simulations across 9 of 11 scales**, each with numerical checks, hashed
  inputs and verified media.
- **A refusal layer with teeth.** 13 proposed couplings: 4 composable, 5
  assumption-level, 4 refused. Zero registered calibrations, stated as such.
- **A reusable record layer**: 21 claims with conditions, 2,444 documents embedded for
  semantic search, a bidirectional lineage from source to claim to model to action to
  evidence to project, and 21 MCP tools.
- **Negative results published**: a non-converged design variant, a stopped protocol, nine
  failed GPU jobs, a quota refusal, a reuse case that came out below threshold, and an
  attestation check where only 4 of 15 items were clean.

**Novelty we would defend.** Treating *refusal to connect two models* as a first-class,
published result; and putting mechanically checked laws underneath the design rather than
alongside it.

**Verify:** `/#/proofs`, `/#/simulations`, `/#/engineering`, `/#/evidence`.

**Limit:** no biological validation of anything. Model fidelity is not biological
validity. What is formalised so far is textbook-level physics and dimensional reasoning,
not biological mechanism.

---

## Decentralized agency

**What exists.** Capabilities and information really are distributed. Distinct agents and
harnesses held different tools and different context: GPU operations, bio-services
retrieval, corpus and citations, an independent browser critic, print and geometry,
genomics, autoformalization, site and database. The owner board records 24 deliverables
with named owners and a next acceptance each. Work was handed off through **files, not
conversation** — durable message packets in a shared directory — so an agent could pick up
another's work without shared memory. The record layer is built so review and identity are
separable from the record: nine record types, atomic leases (SPEC-003), and
fork-on-conflict bundles (SPEC-004) so independent operators could review elsewhere.

**The honest limit, in our own words on the site:** *"Many AI sessions and people worked
through it, but much of the event work was handed out by a single coordinating session.
We claim one real instance of an agent falsifying a claim the team had seeded, with no
coordinator ruling on it, and we do not claim a decentralised architecture was
exercised."* The public node, its database and the site are **one deployment**. There is
no running federated network of nodes. That is a design, not something this deployment
demonstrates.

**Verify:** `/#/faq` (the hosting question), the owner board on `/#/work`, SPEC-003 and
SPEC-004.

---

## Collective capability

**What exists.** A five-entry review-corrections ledger, with a schema and a hash. In four
of five entries, the correcting party held information the author did not: code read
rather than only run; adversarial typed inputs the author's tests had not built; failure
cases the reviewers supplied; out-of-band knowledge of which harness wrote which artifact.
Each entry records what decision changed. Outcomes include a **retracted** benefit claim,
a contributor count corrected from 4 to an 11 floor, and a cache that now returns typed
`blocked` results instead of passes.

**The honest limit, quoted from the ledger itself:** it claims neither *"that collective
work outperforms a single agent"* nor *"any agent-count based advantage"*; all reviewers
are agents of one fleet sharing one git identity, *"none is an independent lab"*; and *"for
every entry it is unknown whether one agent re-reading its own work could have found the
same issue."* It is a retrospective process trace, **not a controlled multi-agent
benchmark**.

**What a proper measurement would require, and why it is absent.** A shared-versus-isolated
arm on the same open question, preregistered, with the result published either way. We did
not run it. It is listed as planned work, and we would rather be marked down for a missing
experiment than claim an advantage our own data cannot support.

**Verify:** `artifacts/coordination/review-corrections.json` and the System page's
coordination section.

---

## Execution and validation

**It is a functioning system, publicly reachable.** Live site, separate PostgreSQL 16
instance with pgvector, public reads and credentialed writes, a public MCP endpoint with
12 of 12 recorded checks passing including anonymous-write rejection, immutable
commit-addressed releases with automatic rollback, and 2,444 documents in a live vector
index.

**Validation that could have failed, and sometimes did.** Lean mutants (17 of 17
rejected); a corrupted solver certificate (rejected); glide numerical controls (analytic
and step-halving); a lattice-refinement check that **disqualified** one of three design
variants; a control arm for the epithelial study; an attestation check that failed its own
corpus on judgement.

**Verify:** `/#/work` receipts tab, `/#/simulations` numerical checks, `/#/proofs`
receipts.

**Limit:** SPEC-005's own 11-item acceptance list is entirely unchecked; the repository
goal list is 18 of 34; a full route-by-route browser critique is incomplete; and the
deployed commit is listed among our own unknowns.

---

## Collaboration bonus

**Reusable by other teams, today:**

- A **public MCP endpoint** (21 tools) any agent can read without credentials.
- **The record contracts** (SPEC-001 to SPEC-004) and the coupling interface schema
  (`frontier.model.interface/1`), which are domain-independent.
- **The coupling checker itself**: a reusable way to decide whether one model's output may
  feed another's input, with refusal as a legitimate verdict.
- **The anti-triviality discipline for formal claims**: a theorem counts only if it names
  real parameters, rejects mutants, and has satisfiable hypotheses.
- Published artifacts with digests, and printable meshes with declared units.

**Limit:** we are not aware of another team having reused these during the event. We are
claiming availability and fitness for reuse, not demonstrated uptake.

---

## If you read only one thing

Open https://frontier.morphoswarm.ai/#/studio/flying-fish and look at how many scale
panels say *"no model exists"*. Then open `/#/engineering` and see which model connections
were refused. The project's claim is that **publishing those two lists honestly is more
useful than a polished pipeline whose joints are unsupported** — and that a mechanically
checked base of laws is what makes the refusals principled rather than merely cautious.
