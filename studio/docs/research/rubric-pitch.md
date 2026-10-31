# Rubric pitch: 90-second story, 3-minute demo, hard questions

Written against the ScienceClaw judging rubric as the root session read it from the live page
(Problem Significance 20, Scientific/Technical Impact 25, Decentralized Agency 20, Collective
Capability 25, Execution and Validation 10, collaboration bonus +10). The weights here are
**relayed from the root session's reading, not re-fetched by me.**

Every number below is tagged `[measured here]` (I ran the command and the receipt is committed),
`[committed receipt]` (I read the committed artifact in this repository) or `[reported]` (a
worker's message, not re-run by me). Nothing untagged goes on a slide.

---

## 1. The 90-second story

> **Designing a whole organism end to end is a way of finding out what we do not know.**
>
> We built a shared scientific commons — typed claims, problems, evidence and actions, all
> versioned — and pointed a heterogeneous collective of agents at one concrete design: a flying
> fish. Every time the design needs a number nobody has, that gap becomes a pinned Problem with
> an owner and a next action. The design is the instrument; the map of gaps is the result.
>
> The commons is public and live. Anyone can read all **1,287 claim versions** and run our
> simulations **with no credential at all** — one HTTP POST, no account, no token. Writes need a
> credential; reads and calculations do not. `[measured here]`
>
> And it works on us. One of our own agents published a claim: that above about 1.5 critical
> wavelengths, the textbook Turing criterion predicts pattern formation reliably — under 1% error.
> A *different* agent attacked it with a probe committed **before** its output existed, and found
> the claim was an artifact of where we sampled. We had only tested at half-integer multiples of
> the critical wavelength, where the error is exactly zero by construction. Between those points
> it is **6.2%**, and it never goes away — still **0.58%** at 4.25 wavelengths. The claim is now
> formally **withdrawn** in the artifact itself, historical table kept, correction attached.
> `[committed receipt]`
>
> The probe's own must-fail control also failed — it demanded over 90% misprediction at a tenth
> of a wavelength and got 89.53%. The author left the threshold alone and shipped the run at
> **exit 1**. `[committed receipt]`
>
> That is the product: a commons where one agent's claim is another agent's target, where the
> checker publishes its own failed control, and where a withdrawal is a first-class result.
>
> **What we have not shown:** that the collective beats one agent at matched budget. That
> comparison is preregistered and running. It has no result yet, and we are not going to pretend
> it does.

**Timing:** ~95 seconds read aloud. Cut the probe's failed control (3rd paragraph) for 90.

**What this story claims, exactly:** a working public commons, a real scope condition found on a
classical criterion by cross-agent review, and an honest pending state on the collective question.
It claims **no** novel architecture — see §4, Q1.

---

## 2. The 3-minute demo sequence

Each step is a command or a page, with the receipt it should produce. Rehearse against the
committed receipts in `data/research/mcp-probe-2026-10-31/` so a dead network does not kill the demo.

### 0:00-0:35 — The commons is public and it refuses to invent numbers

Call `frontier_catalogue` on the live public MCP, no credential.

Show on screen: `claims.versions = 1287`, `with_upstream_claim_id = 1190`,
`origin_declared.unknown = 1214`.

Then scroll to the fields that return **null**:
- `species.mapped_species` → `null`, *"the store has no typed taxon-identifier field ... no number is invented"*
- `conditions_and_math.structured_conditions` → `null`
- `artifacts.hosted_and_byte_checked` → `0`, *"0 is the absence of any check, not a finding"*

**Say:** "A catalogue that reports its own unknowns as unknown. 1,190 of those claim versions
carry an upstream Delphi claim id; 1,214 have no declared origin. We show you both numbers."

`[measured here: data/research/mcp-probe-2026-10-31/catalogue.json]`

### 0:35-1:15 — Anyone can compute against it, with no account

Run `frontier_simulate` with `model: "bioelectric"`, no credential. One POST.

Point at four fields in the response:
- `"calibrated": false` — the result tells you itself that it is not calibrated
- `code_sha256` — every model file hashed, six files
- `effective_request_sha256` — the exact request hashed, so anyone can replay it
- `scope` — *"An ephemeral numerical scenario, not an observation or biological validation."*

**Say:** "A stranger with curl gets a Hodgkin-Huxley trajectory, the hashes of the code that
produced it, and the model's own statement that it is not calibrated biology."

`[measured here: calc_simulate_anonymous.json, elapsed 1.10 s, computed_at 2026-10-31T22:10:02Z]`

### 1:15-1:35 — The boundary is real

Same endpoint, `frontier_propose`, well-formed draft, no credential:

```
unauthorized: Authenticated operator token required
```

**Say:** "Reads and calculations are open. Writes are not. That is the must-fail control for the
previous slide — an open endpoint that cannot refuse anything has not been tested."

`[measured here: control_write_anonymous_refused.json]`

### 1:35-2:30 — The collective caught our own overclaim

Open `bench/mispredication/README.md` on the `codex/resource-utilization-20261031` branch.

Show, in this order:
1. The **correction notice** at the top — three numbered limits, the claim *"reliable (under 1%)
   above 1.5 critical wavelengths"* marked **withdrawn**.
2. The historical table, **kept**, not deleted.
3. `PROBE_DECLARATION.md` — written and committed before the output existed, with an honest
   disclosure that a scratch run motivated the priors, so the committed run is *"a replay of a
   declared design, not an independent confirmation."*
4. The numbers: at half-integer multiples of λc, exactly **0.0%** at every one. Between them,
   **6.22%** at 1.25 λc and still **0.58%** at 4.25 λc.
5. `probe_declared_prior.out`: `"x0.1_over_90pct": false` ... `CONTROL FAILED` ... `PY_EXIT=1`.

**Say:** "The reliability we claimed was a property of our grid, not of the criterion. A different
agent found it, the claim is withdrawn in place, and the probe that found it shipped with its own
control failing at 89.53% against a declared 90% — because moving the threshold would have been
the dishonest fix."

`[committed receipt: PROBE_DECLARATION.md, probe_declared_prior.out, README.md]`

### 2:30-3:00 — What is real, and what is not

One slide, two columns, read the right-hand one out loud:

| Real, with receipts | Not shown |
|---|---|
| 11 Nebius jobs, ids + UTC + rc + sha256, **3 failed and 1 cancelled, all kept in the table** | Any GPU-produced *biological* result |
| Public MCP, 18 tools, anonymous reads and calculations | Any other team using it (bonus **unearned**) |
| A withdrawn claim with its correction in place | A measured collective-vs-single advantage |
| 13-part fish model, six printer props, geometry hashes shared with renders | Any physical print, flight, or living fish |

**Say:** "The right-hand column is the honest state. The collective-versus-single comparison is
preregistered and running. If it comes back null we will report the null, the way we reported this
one."

`[compute receipts: results/compute/RECEIPT.md on codex/frontier-demo-20261031]`
`[fish model and props: reported by the print worker, not re-run by me]`

---

## 3. Which rubric line each demo beat is aimed at

| Beat | Criterion | Why it is evidence and not assertion |
|---|---|---|
| 0:00 catalogue nulls | Execution 10, Impact 25 | A running service that returns `null` where it has no typed field |
| 0:35 anonymous compute | Collaboration +10, Execution 10 | A third party can obtain a result with no account |
| 1:15 write refused | Execution 10 | The negative control for the beat before it |
| 1:35 withdrawn claim | **Decentralized Agency 20, Collective Capability 25** | Agent B falsified agent A's published claim; no coordinator ruled on it |
| 2:30 honest column | Impact 25, Significance 20 | Failed and cancelled jobs kept in the receipt table |

**The 1:35 beat is doing the heavy lifting for 45% of the score.** It is a single instance, not a
curve, and §4 Q2 says so out loud before a judge has to ask.

---

## 4. Hard questions, and the honest answers

**Q1. "Isn't this just Prove2Me / ScienceClaw / Infinite / ASK with biology instead of maths?"**

The architecture is not our novelty and we do not claim it. Prove2Me (arXiv 2608.28433v2) published
the harness-so-agents-build-on-each-other's-work thesis for formalization; ScienceClaw published
the artifact DAG and dead-ends-as-artifacts; Infinite published the publication and coordination
layer; ASK models versioned epistemic state. We claim the **workflow integration** and two
domain-specific things: that no machine-checked library of mathematical biology exists, and that
biological results are stated in limits and applied in regimes, which makes *scope conditions* the
natural unit. If Prove2Me already measured the commons effect at matched budget, we cite them and
report a replication. **We have not read their evaluation section carefully enough to say, and I
am not going to guess at this podium.**

**Q2. "Did organizing agents collectively add measurable capability?"**

**Not yet measured.** We have one qualitative instance — a cross-agent falsification that a single
agent had missed and published — and a preregistered equal-budget comparison (single vs isolated
vs sharing specialists) that is running with no result. An earlier scale study of ours returned a
**null**: shared specialists 78/100 against original 78/100. We expect the honest answer to be
"it depends on verification asymmetry", and we will report whatever the run says.

**Q3. "Your fish — does it fly?"**

No. There is a 13-part model and six downloadable printer props, with geometry hashes shared with
the renders and dimensions linked to real fish data. **Nothing has been printed, nothing has
flown, and no living organism exists.** The fin ensemble ranks candidates under *assumed* joint
draws and load cases — 20/64 baseline, 33/64 shorter, 34/64 stiffer — and biological success, mass
and growth cost are all unknown. It is a ranking, not a probability. `[reported]`

**Q4. "How much of this is GPU theatre?"**

Some of it was, and we measured that too. A bioelectric tissue model runs 882 cells in 0.718 s on
one core; GROMACS on an A100 is 2.82x a 72-core node, not 100x. We ran 11 Nebius jobs and three
failed, one was cancelled, and all four are still in the receipt table with their exit codes. We
have **no** GPU-produced biological result and we are not claiming one. `[committed receipt +
reported]`

**Q5. "What is the strongest scientific result here?"**

A scope condition on the classical Turing criterion: on a finite domain with zero-flux boundaries,
the continuum criterion's error is not monotone in domain length and does not vanish at long
lengths — it is **windowed**, exactly zero at half-integer multiples of the critical wavelength and
non-zero between them, 6.22% at 1.25 λc and 0.58% still at 4.25 λc. The honest framing is that
this is a **toy ensemble** with a declared prior; it says nothing about how often real Turing
systems mispredict, nothing about nonlinear outcomes, and nothing about any organism. Its value is
that it falsified our own published claim.

**Q6. "Did an AI solve Navier-Stokes?"**

No, and nobody on this team will say that. The OpenAI result is a **proposed** counterexample,
Wikipedia describes it as proposed, and the Clay Institute still lists the problem as open.

**Q7. "Has another team actually used your MCP?"**

**No. The collaboration bonus is unearned.** The endpoint is public, anonymous reads and
calculations work, and there is a one-page recipe (`mcp-reuse-recipe.md`). Until another team runs
it and we hold their receipt, it counts for nothing and we will say so.

**Q8. "Why should I believe your counts?"**

Do not. Run `frontier_catalogue` yourself against `https://frontier.morphoswarm.ai/mcp` with no
credential, from your laptop, right now. Every count on our slides comes from that call, and the
call reports its own unknowns as `null`.

---

## 5. What is deliberately NOT in the pitch

- No "we built a novel multi-agent architecture." Prior art is published and a judge who knows it
  catches us in two minutes.
- No swarm-gain assertion without the matched-budget run.
- No "printed forms" — no physical print has occurred; the phrase is **print-ready meshes**.
- No count of agents as a capability claim. Agent count earns nothing.
- No inferred judge preferences, and no person-targeted flattery.
- No "imported_unreviewed = 1190". The measured field is `with_upstream_claim_id = 1190`;
  `local_status: imported_unreviewed` is a per-record status we observed on sampled records, and
  we did not count it.
