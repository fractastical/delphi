# Demo narrative — the flying-fish studio, drilled to the open edge

Three minutes. Open on the fish, go down through its scales to the equations and the runs that
produced them, stop at the one coupling that does not close, then show the commons the whole thing
lives in.

**Limits are one line each, said where they belong, and then we move on.** The evidence is strong
enough that it does not need a chaperone.

Supersedes `archive/demo-narrative-2026-10-31-refusal-led.md`, which led with refusals.

**On provenance, stated once and not repeated on stage.** This project reuses sources and software
that long predate it — the FAO species guide, Daane 2021, Fish 1990, Hayden 2021, Zebrafish-GEM,
BETSE, the imported Delphi claims. What is shown below is the **work executed today**: the builds,
the solves, the checks and the integrations, each with a dated receipt. A commit date is when an
artifact entered the repository, not when its content was made, so we cite the run receipt rather
than the commit wherever the two differ.

---

## 1 · Open on the fish — 25s

**Show the v3 viewer. Rotate it. Say almost nothing for three seconds.**

> This is v3. Every fin is a fan of tapered rays joined by a thin membrane. v1 had flat half-
> millimetre plates and a needle for a lower caudal lobe — you can still load it, we kept it.
>
> The ray counts are not artistic. They are read out of a species sheet.

Then put the numbers up:

**15 pectoral rays** (range 14–17, only the first unbranched) · **13 dorsal** (12–14) · **10 anal**
(8–11) · the anal fin originating under the **6th dorsal ray** · **28.5 predorsal scales**, which
sets scale spacing at **2.38 mm** and gives **48 rows and 1,302 scales** · eye diameter = head
length / **2.95**.

> All of that is Parin 2002, after Gibbs 1978, in the FAO Western Central Atlantic guide — read as
> full text, hashed. Fish 1990 gives the areas: the caudal lobes are solved to its hypocaudal share
> of **0.6263**, reproduced exactly. Daane 2021 gives the stiffened, elongated ventral lobe.
>
> And the builder refuses candidates. The FAO sheet says the pelvic insertion sits nearer the
> opercle than the caudal base, so a candidate that breaks that rule does not get built.

**One limit:** camber and dihedral are still assumed — Park & Choi 2010 was unreachable through the
page, the PDF and the read proxy. That is a named gap with a named source, not a shrug.

**Receipts:** `docs/fish3d-v3.md`, `engineering/fishv3/`, 13 tests, three candidates plus
`v3-index.json`. FAO sheet sha256 `f1a35c86…`.

---

## 2 · Drill into a scale — 30s

> Zoom in on one scale. This one is a simulation of how it grows.

Three equations on screen — Erk, activator, inhibitor:

```
dE/dt = a1 A²/(b² + A²)(1 − E) − E(g1 I + ge)
dA/dt = a2[source] + a3 E − g2 A + D ∇²A
dI/dt = g3(a4 E − I)
```

> Erk trigger waves driving osteoblast growth in a regenerating zebrafish scale. Hayden, Poss, De
> Simone and Di Talia, *Biophysical Journal* 2021, **read in full**. Every parameter comes from
> their Table 1, and the values match the authors' own published MATLAB — read, not copied; it is
> GPL.
>
> A 520-micron disc on a five-micron grid, hundredth-of-an-hour steps.

**One limit:** the model reproduces five of the source's bands and misses the rise and the
synchrony–growth impairment. We kept it, and the miss is written next to it.

**Receipts:** `docs/scales.md`, `engineering/scales/`, `artifacts/scales/erk-wave/`, 7 tests.

---

## 3 · Go down to the cells — 35s

> Same organism, different scale. This is BETSE — the real package, version 1.5.0, wheel hashed,
> called rather than copied. A hexagonal patch, **66 cells, 364 membranes**, 80 microns across,
> at body temperature, with dynamic sodium, potassium and anion concentrations, an electrogenic
> Na/K-ATPase, and voltage-gated gap junctions.

Then the experiment, which is the good part:

| run | targeted cells | everyone else |
|---|---|---|
| raise K⁺ permeability in 2 cells | **−4.67 mV** | **−2.62 mV** |
| same, with gap junctions blocked | **−19.8 mV** | **−0.16 mV** |

> Block the junctions and the effect stops spreading and gets four times bigger where you put it.
> That is the coupling doing the work, shown by removing it.
>
> And the control that proves the block: with junctions blocked and nothing else changed, the open
> fraction goes from 0.967 to about 1e-11, and the voltage barely moves — because a uniform patch
> has almost no differences for junctions to equalise.

**One limit:** resting Vm here is about −23.5 mV, which is a property of BETSE's defaults, not a
calibrated epithelium. A leak-only reference gives +0.7 mV and we have **not** decomposed the
24 mV difference. This is not a fin.

**Receipts:** `docs/bioelectric-tissue.md`, `artifacts/bioelectric-tissue/summary.json`,
betse 1.5.0 wheel sha256 `17a11601…`.

---

## 4 · And down to metabolism — 25s

> Zebrafish-GEM, the published genome-scale model. We measured the file rather than quoting its
> README: **12,833 reactions, 8,435 metabolites, 2,709 genes, 1,658 exchanges.**
>
> It ships with **no medium** — every exchange wide open. Run it that way and biomass is 4.26,
> which means nothing.

Then the actual finding:

> So we built a real medium from an allowlist of basic nutrients. **Biomass came out zero.**
>
> The reason is specific: the biomass pool's cofactor-and-vitamin term needs vitamin E catabolites
> that only come from **gamma-tocopherol**, and we had supplied alpha. Add gamma-tocopherol and it
> solves — **0.265 with no oxygen, 0.291 at O₂ 20, 0.329 at O₂ 50.**
>
> That is what this kind of work is for. A zero that turns out to be a missing nutrient is a
> result.

**Controls:** all uptake closed → zero. Glucose alone → zero. Mass balance ≤ 1e-10. No
energy-generating cycle with every uptake closed.

**One limit:** the medium, the glucose cap and the flux units are assumptions. Absolute growth
values mean nothing physiologically.

**Receipts:** `docs/metabolism.md`, `artifacts/metabolism/`, Zebrafish-GEM commit `846f0b7b3…`.

---

## 5 · The edge: the fin coupling that does not close — 35s

**This is the most interesting slide. Do not rush it.**

> We built the adapter that takes flow pressure onto a fin ray: pressure jump, to line load, to
> resultant and root moment, to deflection through the FEM we already had. We did not write a
> second beam solver; we reused the one that exists.
>
> It checks out exactly. Uniform and linear pressure against hand-derived closed forms. **Grid
> order 2. Force conservation exact. Disabled-load control exactly zero. Deflection scaling
> exactly 1/EI.**
>
> And it will not run, for a reason worth hearing.

Put the number up:

> **A half-millimetre fin plate needs a grid of at least 923 cells to be two cells thick. That is
> beyond one H100.** Our actual case runs at 32 cells — **7.2 mm of grid spacing for a 0.5 mm
> fin**. Every one of those samples is tagged `resolved: false`, and the contract **refuses**
> them — `MEMBER_UNRESOLVED`.
>
> So the blocker is the grid, not the schedule. More hours would not fix it. What fixes it is a
> resolved local fin-patch case or a validated sub-grid fin model, and neither exists yet.
>
> There is a second gap under it: nobody has measured EI along a flying-fish ray. That one is a
> wet lab, and it has no owner.

> **That is what designing an organism end to end buys you.** Two gaps with numbers on them,
> found by trying to connect a flow solver to a beam, and now pinned as problems anyone can pick
> up.

**Receipts:** `docs/coupled-mechanics.md`, `engineering/coupled_mechanics/`,
`artifacts/coupled-mechanics/result.json`, `tests/test_coupled_mechanics.py`. Sub-grid finding
reported by `cfd3d` at 15:02 PDT, contract v0.1.

---

## 6 · The commons it all lives in — 30s

> Everything you just saw is addressable, and you do not need an account.

Run it live, no credential:

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"frontier_catalogue","arguments":{}}}'
```

> **19 tools.** Reads and bounded calculations are open — search, graph, design context, and
> solvers you can run from a laptop. Writes need a credential and are refused without one.
> **1,315 claim versions**, 1,190 carrying an upstream Delphi claim id.
>
> Ask it to simulate and you get a trajectory back in about a second, carrying the hash of every
> model file, the hash of your request, and the model's own statement that it is not calibrated.

**The release is live and checked.** The current release `c1ad527` passed **13 public web checks
and 35 MCP checks, zero failures**, both receipts stamped **2026-10-31 16:14:54 PDT**. The MCP
suite's own scope line is worth reading aloud: *"public client connectivity, search, schema
discovery and anonymous write denial; not scientific acceptance."*

**Compute, as a snapshot and not a total.** At **16:13 PDT**: **52 team jobs** — 37 in the current
queue plus 15 from prior team and setup work — with **30 unattributed** in the shared project, and
**2 of ours running plus 1 pulling** right then. One sampled window shows **96.6% mean GPU
utilisation** across 52 samples at 454 watts. Kernel-execution seconds are reported as
**unknown**, because wall time was sampled and not kernels. Spend is unknown; no dollar figure is
inferred from credits.

> **Say the clock, not a bare number.** This is a shared 16-H100 pool and the tally moves. The
> figures above are root's corrected count at 16:13 and infra is still reconciling source
> receipts; quote the snapshot time with them or do not quote them.

**Receipts:** `deploy/receipts/rayfan-public-live-check.json` (13 checks) and
`rayfan-mcp-live-check.json` (35 checks), both 0 failed at 2026-10-31T23:14:54Z.
`results/resources/hackathon-usage.json` for the job records. Compute tally relayed from root's
16:13 correction, not re-derived by me. MCP measured here at 16:15 PDT: 19 tools, 1,315 claim
versions, 543 artifact declarations.

> **Re-run the catalogue call shortly before the room.** The store is live and the counts move —
> versions went 1,287 → 1,315 and artifact declarations 451 → 543 inside an hour, then held
> steady across the release. Quote what the call returns on the day.

---

## 7 · Agents checking each other — 25s

> One claim in the commons said the textbook Turing criterion is reliable above about 1.5 critical
> wavelengths — under 1% error. An agent went after it with a probe committed **before** its
> output existed.
>
> The reliability was an artifact of where we had sampled. Every zero sits at a half-integer
> multiple of the critical wavelength. **Between them it is 6.22%, and at 4.25 wavelengths it is
> still 0.58%** — it never goes away.
>
> The claim is withdrawn in place, historical table kept, correction attached. And the probe's own
> declared control failed — it demanded over 90% and got 89.53% — so it shipped at exit 1 with the
> threshold untouched.

**Receipts:** `bench/mispredication/`, probe and withdrawal at 12:05 PDT. The table it falsified
was imported earlier in the day; the falsification is ours.

**And one repair worth thirty seconds if you have them.** A frozen CFD packet failed its own gate:
all twelve STL hashes matched, but the float64 candidate hash did not, so no solver ran. The
reviewer refused an unchanged retry and required a CPU-only exact-image diagnosis. It found
**NumPy AVX-512 dispatch drifting three candidate fields by one to two units in the last place**,
while the float32 STLs stayed identical. A declared geometry-only dispatch setting restored
byte-identical output, and the gates stayed exact.

> "A one-ULP difference is invisible unless something is checking bytes. Ours was."

**Receipt:** job `aijob-e00m8v3m77z86n5ads`, rc 0, 6.2 s, sha256 `53b39302…`;
`results/capability-agency/coordination-case-studies.md`.

---

## 8 · Honest close — 25s

> Two things are running and neither has a result yet, so here they are.

**The diffusion pilot did not train.** Its CUDA gate caught a CPU-versus-GPU network mismatch of
**0.001191914 against a tolerance of 0.001** and stopped before training. The solver's own
mismatch, 5.95e-14, passed. A precision-only diagnostic retry is preregistered with the **original
tolerance untouched** and the failed output preserved.

**The collective comparison ran, and measured nothing — for a reason we can name.** v3 completed:
all **27 requests valid**, three conditions — one serial analyst, isolated specialists, specialists
sharing pinned artifacts. **Every answer and every condition-by-repeat aggregate scored 16 out of
16.** All three means identical.

> That is a **ceiling**, not a tie. The packet handed each arm the source fit, the stiffness range
> and the measurement method, so the task was answer-explicit and there was no headroom left to
> measure a difference. The communication treatment demonstrably ran — nine pinned artifacts to
> the serial analyst, nine peer artifacts to the collaborators, none to the isolated arm — and the
> ceiling left nothing for it to move.
>
> So we have **no measured collaboration advantage**, and the honest reading is that we measured
> our benchmark rather than our collective. The next pilot needs a task with room to fail.

**Do not pool v2 with v3.** v2's 27 requests all returned HTTP 200 and all truncated at the token
ceiling with invalid JSON, scoring zero. Different failure, separate receipt, kept separate.
Known Google API usage across everything: **103,459 tokens over 57 requests.** Spend unknown — no
billing meter was available.

> What we do have is an organism you can take apart: geometry traced to a species sheet, growth to
> a published model, cells to a real simulator, metabolism to a genome-scale solve — and two gaps
> with numbers on them where it stops. That is the product. The gaps are the point.

---

## Timing

| § | beat | length |
|---|---|---|
| 1 | v3 fish and its sourced meristics | 0:25 |
| 2 | scale growth, Erk waves | 0:30 |
| 3 | BETSE cells, gap-junction experiment | 0:35 |
| 4 | metabolism, the gamma-tocopherol find | 0:25 |
| 5 | **the fin coupling that does not close** | 0:35 |
| 6 | the commons, live, 19 tools, 35 jobs | 0:30 |
| 7 | agents checking each other | 0:25 |
| 8 | honest close | 0:25 |
| | **total** | **3:30** |

**For a hard 3:00:** cut §4 to a single sentence about the zero and the missing vitamin, and cut
§7 to the 6.22% figure and the word "withdrawn". **Never cut §5** — it is the thesis.
**For 90 seconds:** §1, §5, §6, §8.

---

## If a judge interrupts

- **"Does it fly?"** No. Print-ready meshes exist; nothing has been printed and nothing has flown.
  The fin loads are a ranking under assumed load cases, not a probability.
- **"Is the collective better?"** **Not established, and we ran the experiment.** v3 scored 16/16
  in every arm — a ceiling on an answer-explicit task, so the instrument had no headroom. We have
  three observational coordination cases where review caught things a single pass did not, but
  they have **no controlled counterfactual** and we do not count them as evidence of advantage.
- **"Is this a novel architecture?"** No, and we name the prior work — Prove2Me, ScienceClaw,
  Infinite, ASK; and for the diffusion roadmap, Comlekoglu, Bastek and GenCFD.
- **"What is yours, versus what you reused?"** The sources and the software are published and
  credited. Today's work is the builds, the solves, the checks and the integrations, each with a
  dated receipt. The imported claims corpus is labelled as imported, and most records read
  `imported_unreviewed`.
- **"Why should I believe the counts?"** Run the catalogue call yourself.

Longer answers: `docs/research/rubric-pitch.md` §4.
