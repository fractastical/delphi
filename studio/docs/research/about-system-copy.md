# Page copy for root: a judge scorecard for About, and the System page

**Root's About and `#/generative` are already implemented** (`df98621`, 2026-10-31 15:29 PDT:
`site/js/about.js`, `site/js/generative.js`, `site/css/about.css`). This file does **not** replace
them. It supplies the two things they do not yet contain:

1. **§A — a rubric scorecard section** to add to the existing About, in root's register.
2. **§B — the System page**, which has no implementation yet.

Route names in §A match root's existing `DF.href` paths where I could read them from `about.js`
(`/studio`, `/work`, `/frontier`, `/knowledge`, `/engineering`, `/simulations`, `/about/docs`,
`/generative`). Two are guesses and are marked.

Two rules the copy keeps:
- **No unearned gains.** A criterion with no result says so in its own card, not in a footnote.
- **The System page describes this event.** Work that predates 2026-10-30 is named as an input,
  never narrated as something built here, because `git log` settles it either way.

---

# §A — About: "How to judge this"

> Suggested placement: after the *Follow the evidence* section, before *A research direction*.
> Root's `about-cards` grid and `about-step` eyebrow style fit it as-is.

**Eyebrow:** How to judge this
**Heading:** Our own scorecard, with the receipts attached.
**Lede:** The event scores six things. Here is where we stand on each, including the one we cannot
fill. Every link goes to something you can re-run.

---

**20% / Problem significance.** **Designing an organism end to end finds the gaps.**
Each gap the design hits becomes a pinned problem with acceptance criteria, falsifiers, a next
action and cost bounds — or it is marked `recorded` and does not pretend to be actionable. Of 250
problems imported from our register, **0** are actionable. Of 17 sourced proposals, **13** are.
→ `/frontier`

**25% / Scientific and technical impact.** **The strongest result falsified us.**
A claim entered the commons at 07:52: that the textbook Turing criterion is reliable, under 1%
error, above about 1.5 critical wavelengths. By 12:05 an agent had falsified it with a probe
committed before its output existed. The error is windowed rather than monotone — exactly 0% at
half-integer multiples of the critical wavelength, which is where we had sampled, **6.22%** at
1.25 λc, still **0.58%** at 4.25 λc. The claim is withdrawn in place; the historical table stays
with the correction attached. The probe's own declared control failed at 89.53% against a declared
90%, and shipped at exit 1 with the threshold unchanged.
→ `/knowledge`

**20% / Decentralized agency.** **Review is separate from the record.**
Every record carries its own node-local status. There is deliberately no accept tool:
`frontier_propose` returns `proposed`, never `accepted`, and acceptance needs an independent
operator elsewhere. Each request authenticates as its own principal and the server holds no shared
token. *One instance of agent-to-agent falsification went through this path. Most coordination
during the event was dispatched, so we claim the instance rather than the architecture.*
→ `/about/docs`

**25% / Collective capability.** **No result yet. This is the row we cannot fill.**
An equal-budget comparison — single agent, isolated agents, sharing specialists — is preregistered
and running. An earlier scale study of ours returned a null: 78/100 against 78/100. What we have
is qualitative and singular: the collective caught an error that had been sitting in the commons
unchallenged. We will report the outcome either way.
→ `/work`

**10% / Execution and validation.** **It is live, and you do not need an account.**
18 tools on the MCP, 15 read and 3 write. Reads and bounded calculations need no credential — one
HTTP POST. A well-formed write without one is refused. 1,287 claim versions, 1,190 carrying an
upstream Delphi claim id, 1,214 with no declared origin. Several catalogue fields return `null`
with a reason instead of a number. 11 GPU and CPU jobs with ids, UTC windows, exit codes and
sha256 — **3 failed, 1 cancelled, all four still in the table**. Cost is unavailable, which is not
the same as zero.
→ `/work`

**+10% / Collaboration bonus — actual reuse.** **Unearned. Zero.**
The endpoint is public, anonymous reads and calculations work, and a one-page recipe runs with
curl alone. No other team has used it and we hold no receipt that anyone has. This becomes
non-zero when someone else's run exists.
→ `/about/docs`

**Closing paragraph — "What is not here."**
No physical print, no flight, no living organism, and no GPU-produced biological result. No claim
to a novel multi-agent architecture: Prove2Me, ScienceClaw, Infinite and ASK published the relevant
pieces. Nobody here will say an AI solved Navier-Stokes — that result is a proposed counterexample
and the Clay problem is open. The generative roadmap has one frozen pilot awaiting GPU time and
nothing trained.

---

# §B — System: "What ran during this event"

> No implementation exists yet. Route guess: `/system`. Root's `about-cards` and `about-docs`
> styles cover the whole page.

**Eyebrow:** System
**Heading:** Built here, brought in, borrowed.
**Lede:** Three categories, labelled, because the repository history settles each one.

### Built during the event

The Frontier store, its HTTP adapter, the read/write MCP and this site. The repository's first
commit is **2026-10-31 07:49:44 PDT** and **all 508 of its commits are dated that day**.

- A versioned append-only store over PostgreSQL with **eleven** record types — Problem, Claim,
  Evidence, Assessment, Action, Actor, ResourceOffer, Interest, Event, Project, Annotation (read
  from the `KINDS` registry, not written from memory)
- A licence gate at **four** boundaries — store, serve, export, import — so content asserted
  available under an unstated licence is refused rather than served
- `https://frontier.morphoswarm.ai/mcp`: 18 tools, anonymous reads and bounded calculations,
  bearer-authenticated writes, no shared server token
- Seven assessment dimensions, all required, with **no composite truth score**
- The mispredication probe, its failed control and the withdrawal it produced: commits `e4ab195`,
  `b9f603b`, `81ca466`, all 12:05 PDT
- The RD-1D diffusion pilot: preregistration and code `9c56a927`, frozen job packet `4a5394f3`,
  both 15:32-15:33 PDT. **No GPU result yet.**

### Brought in, not built here

- **The claims corpus.** 1,190 of 1,287 claim versions carry an upstream Delphi claim id. They
  were imported, and each record's status says whether anyone here has reviewed it — most read
  `imported_unreviewed`.
- **The historical mispredication table.** It arrived in the seed commit `636919a` at 07:52 PDT.
  Its generating script and sampling distribution are **not in this repository**, which is one of
  the three limits its own correction notice records. The probe that falsified it is event work;
  the table is not.
- Simulation codebases and the fish geometry lineage predate this event.

### External tools and sources

- **Simulators:** BETSE (ion, pump and gap-junction), Morpheus (ODE, CPM, PDE), OpenMM, zebrafish-GEM, WaterLily
- **Models:** OpenFold2, hosted, returning a 362-residue zebrafish Kcnj13 monomer at mean pLDDT
  52.86 — low confidence, and no channel function is implied
- **Compute:** Nebius H100 and CPU jobs, 2026-10-31 18:31Z to 20:44Z
- **Literature:** primary sources for every mechanistic equation, cited at the claim record

### What the system will not do

- Return a composite score for whether a design works. Formal correctness, numerical accuracy and
  empirical accuracy stay separate.
- Accept its own proposals. There is no review or accept tool on the MCP.
- Serve content asserted available under an unstated licence.
- Report a count it has not measured. The catalogue returns `null` with a reason where a typed
  field does not exist.

### Check any of it yourself, with no account

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"frontier_catalogue","arguments":{}}}'
```

Every count on the About scorecard comes from that call.

---

## Note for root on the live `#/generative` page

Two precision upgrades available, both verified here on 2026-10-31:

1. The pilot status card reads *"implementation in progress"*. It is now stronger than that:
   **preregistration and code frozen at `9c56a927`, job packet at `4a5394f3`, local CPU controls
   and 13 tests passing, no GPU result yet.** "Frozen and awaiting GPU time" is both more accurate
   and more impressive than "in progress".
2. The four related-work citations were checked against their arXiv abstract pages and all four
   are correct, including Gallon et al. 2026 (arXiv:2602.09708, v1 2026-02-10). One refinement:
   Bastek et al. is **v1 2024-03-21**, v4 2025-03-13, with ICLR 2025 from the Comments field — the
   2403 identifier is March 2024. GenCFD carries **no journal reference** on its arXiv page, so it
   should not be described as journal-published.
