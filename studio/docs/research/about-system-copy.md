# Drop-in copy: About page (judge scorecard) and System page

For root to lift into the site. **Route names are placeholders** — replace `#/x` with the real
hash route; the evidence each row points at is what I verified, not the URL.

Two rules this copy obeys, and the site should keep:
1. **No unearned gains.** Rows with no result say so in the row, not in a footnote.
2. **The System page describes the event.** Components that existed before 2026-10-30 are named as
   inputs, never narrated as things we built here. External tools and sources are cited plainly.

---

# ABOUT — How to judge this

> We have written our own scorecard. Where we have nothing, the row says nothing. Every link goes
> to a receipt you can re-run, not to a description of one.

### Problem Significance & Complexity — 20%

Designing a whole organism end to end is a way of finding out what we do not know. Every gap the
design hits becomes a pinned Problem with acceptance criteria, falsifiers, a next action and cost
bounds — or it is marked `recorded` and does not pretend to be actionable. Of 250 problems
imported from our register, **0 are actionable**. Of 17 sourced proposals, **13** are.

→ `#/problems` · the `completeness` discriminator in `frontier/models.py`

### Scientific / Technical Impact — 25%

**The strongest result is one that falsified us.** We seeded a claim into the commons at 07:52
today: that the textbook Turing criterion is reliable, under 1% error, above ~1.5 critical
wavelengths. At 12:05 an agent falsified it with a probe committed *before* its output existed.
The error is **windowed, not monotone** — exactly 0% at half-integer multiples of the critical
wavelength, which is where we had sampled, **6.22%** at 1.25 λc, still **0.58%** at 4.25 λc. The
claim is withdrawn in place; the historical table is kept with the correction attached.

The probe's own declared control **failed** (89.53% against a declared 90%). The author did not
move the threshold and shipped at exit 1.

→ `#/claims` · `bench/mispredication/` · also: oca2 exon 21 absent from all 1,361,196,561 bp of the
Molino assembly; a KCNE1 test **stopped** at 20.27% coverage against a preregistered 75% floor.

### Decentralized Agency — 20%

Review is node-local and separate from the record. Every record carries its own `local_status`;
there is deliberately **no accept tool** — `frontier_propose` returns `proposed`, never `accepted`,
and acceptance needs an independent operator elsewhere. Each request authenticates as its own
principal; the server holds no shared token.

**Honest limit:** that is one real instance of agent-to-agent falsification through the commons.
Most coordination during this event was dispatched. We claim the instance, not the architecture.

→ `#/mcp` · `frontier_capabilities`

### Collective Capability — 25%

**No result. This is the row we cannot fill.** An equal-budget comparison — single agent vs
isolated agents vs sharing specialists — is preregistered and running. An earlier scale study of
ours returned a **null: 78/100 against 78/100**. We expect the answer to depend on verification
asymmetry, and we will report whatever the run says, including nothing.

What we do have is qualitative and n=1: the collective caught an error that had been published
and was sitting in the commons unchallenged.

→ `#/collective` (preregistration; result pending)

### Execution and Validation — 10%

The commons is live and public. **18 tools** on the MCP (15 read, 3 write). Reads and bounded
calculations need **no credential** — one HTTP POST, no account. A well-formed write without one
is refused: `unauthorized: Authenticated operator token required`.

**1,287** claim versions, **1,190** carrying an upstream Delphi claim id, **1,214** with no
declared origin. Several catalogue fields return `null` with a reason rather than a number, and
`hosted_and_byte_checked: 0` says in its own text that *0 is the absence of any check*.

**11 GPU/CPU jobs** with ids, UTC windows, exit codes and sha256 — **3 failed, 1 cancelled, all
four still in the table**. Cost: unavailable, and that is not zero.

→ `#/mcp` · `#/compute` · `results/compute/RECEIPT.md`

### Collaboration Bonus — +10 (actual reuse)

**Unearned. Zero.** The endpoint is public, anonymous reads and calculations work, and there is a
one-page recipe a stranger can run with curl. **No other team has used it**, and we hold no
receipt of anyone doing so. This row becomes non-zero when someone else's run exists, and not
before.

→ `#/mcp` recipe

### What is not here

No physical print, no flight, no living organism. No GPU-produced biological result. No claim to a
novel multi-agent architecture — Prove2Me, ScienceClaw, Infinite and ASK published the relevant
pieces. No "AI solved Navier-Stokes": that result is a *proposed* counterexample and the Clay
problem is open. The generative roadmap on `#/generative` is **untrained and unvalidated**, and
its architecture is published work by others.

---

# SYSTEM — What ran during this event

> Built during the event, used during the event, and brought in. The three are labelled, because
> `git log` settles it either way.

### Built during the event

The Delphi Frontier store, its HTTP adapter, the read/write MCP, and the public site. **The
repository's first commit is 2026-10-31 07:49 PDT and every one of its 508 commits is dated that
day.**

- Versioned append-only store over PostgreSQL, **eleven** record types — Problem, Claim,
  Evidence, Assessment, Action, Actor, ResourceOffer, Interest, Event, Project, Annotation
  (read from the `KINDS` registry in `frontier/models.py`, not written out from memory)
- A licence gate enforced at four boundaries — **store, serve, export, import** — so content
  asserted available under an unstated licence is refused rather than served
- `https://frontier.morphoswarm.ai/mcp`: 18 tools, anonymous reads and bounded calculations,
  bearer-authenticated writes, no shared server token
- Seven Assessment dimensions, all required, with **no composite truth score** — the validator
  refuses an Assessment missing any of them

The mispredication probe, its failed control and the withdrawal of the claim it falsified are also
event work: commits `e4ab195`, `b9f603b`, `81ca466`, all 12:05 PDT on 2026-10-31.

### Brought in, not built here

- **The claims corpus.** 1,190 of the 1,287 claim versions carry an upstream Delphi claim id.
  They were imported, and each one's `local_status` says whether anyone here has reviewed it —
  most read `imported_unreviewed`.
- **The historical mispredication table.** It arrived in the seed commit `636919a` at 07:52 PDT.
  Its generating script and sampling distribution are **not in this repository**, which is one of
  the three limits its own correction notice records. The probe that falsified it is event work;
  the table is not.
- Simulation codebases and the fish geometry lineage predate this event.

### External tools and sources used

- **Simulators:** BETSE (ion/pump/gap-junction), Morpheus (ODE/CPM/PDE), OpenMM (a 10,491-atom
  CPU trajectory), zebrafish-GEM (metabolic solves), WaterLily (3D, installing)
- **Models:** OpenFold2, hosted, returning a 362-aa zebrafish Kcnj13 monomer at mean pLDDT 52.86 —
  **low confidence, and no channel function is implied**
- **Compute:** Nebius H100 and CPU jobs, 2026-10-31 18:31Z–20:44Z, receipts above
- **Literature:** primary sources for every mechanistic equation, cited at the claim record

### What the system deliberately will not do

- It will not return a composite score for whether a design works. Formal correctness, numerical
  accuracy and empirical accuracy stay separate.
- It will not accept its own proposals. There is no review or accept tool on the MCP.
- It will not serve content asserted available under an unstated licence.
- It will not report a count it has not measured. `frontier_catalogue` returns `null` with a reason
  where a typed field does not exist.

### Verify any of this yourself, with no account

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"frontier_catalogue","arguments":{}}}'
```

Every count on the About page comes from that call. The recipe for the rest is on `#/mcp`.
