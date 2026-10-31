# Demo: spoken script, then presenter notes

**The script below is what you say.** It is word-counted for a three-minute slot. Every number
in it is one a listener can hold. **All other numbers live in the presenter notes** — use them to
answer questions, not to fill the three minutes.

Supersedes `archive/demo-narrative-2026-10-31-refusal-led.md`.

---

# PART 1 — THE SPOKEN SCRIPT (417 words)

### Open · on the viewer

Designing a whole organism end to end is a way of finding out what we don't know.

This is our flying fish, version three. Every fin is a fan of tapered rays. The ray counts aren't
artistic — fifteen pectoral rays, thirteen dorsal, ten anal — they're read out of an FAO species
sheet. The builder refuses any candidate that breaks the sheet's rule for where the pelvic fins
sit.

### Drill · down through it

Zoom into one scale. This is a published model of Erk trigger waves driving bone growth in a
regenerating zebrafish scale — every parameter from the authors' own table.

Down again, to cells. This is BETSE, the real package, running a **generic** tissue patch — not a
fish fin, and we don't claim it is one. Raise potassium permeability in two cells and they drop
about five millivolts, and their neighbours drop too. Block the gap junctions and the targeted
cells drop four times further while the neighbours barely move. That's the coupling, shown by
removing it.

Down again, to metabolism. We ran a published genome-scale zebrafish model. It ships with no
medium at all, so we **assumed** one. Growth came out at zero. The reason was specific: the
biomass pool needed a vitamin E catabolite our assumed medium couldn't supply. We added it and the
model solved.

### The edge · where it stops

Now the interesting part. We built the adapter that carries flow pressure onto a fin ray. It
checks out exactly — force conservation exact, the disabled-load control exactly zero.

And it will not run. Our flow grid is seven millimetres across a cell. The fins are half a
millimetre. They come through as unresolved shells, and the contract refuses them rather than
quietly loading them. Our estimate is that resolving one properly needs a grid roughly thirty
times finer than anything we've run.

Underneath that sits a second gap: we have not established a sourced stiffness profile for a real
flying-fish fin ray. That one is a wet lab.

**Two gaps, with numbers on them, found by trying to connect a flow solver to a beam.** That's
what the design is for.

### Close · the commons

All of it is public. Repository, site, and an endpoint with nineteen tools where reads and
calculations need no account — thirty-five checks passing on the current release.

One honest result. We ran a preregistered comparison of a single analyst against collaborating
agents. Every arm scored full marks, so we measured no advantage — the task had no room to fail.
That's a finding about our benchmark, and the next one needs harder questions.

---

**Pacing.** 417 words at ~140 wpm ≈ **2:59**. Cut the metabolism paragraph for 2:30. Cut the scale
paragraph too for 2:00. **Never cut the edge section** — it is the thesis.

---

# PART 2 — PRESENTER NOTES

Numbers, sources and exact limits. Reach for these in Q&A.

## Fish (v3)

- **15 pectoral rays** (range 14–17, only the first unbranched), **13 dorsal** (12–14), **10 anal**
  (8–11); anal fin originates under the **6th dorsal ray**; **28.5 predorsal scales** → 2.38 mm
  spacing → **48 rows, 1,302 scales**; eye diameter = head length / 2.95.
- Source: Parin 2002 after Gibbs 1978, FAO Western Central Atlantic guide vol. 2, read as full
  text, sha256 `f1a35c86…`. Caudal lobes solved to **Fish 1990**'s hypocaudal share **0.6263**,
  reproduced exactly. Daane 2021 gives the stiffened, elongated ventral lobe.
- Refusal rule: FAO requires the pelvic insertion nearer the opercle than the caudal base.
- **Assumed, not sourced:** camber and dihedral. Park & Choi 2010 was unreachable through the
  page, the PDF and the read proxy.
- `docs/fish3d-v3.md`, `engineering/fishv3/`, 13 tests, three candidates.

## Scale growth

- Hayden, Poss, De Simone, Di Talia, *Biophys J* 2021, **read in full**. Erk / activator /
  inhibitor system; every parameter from their Table 1, matching the authors' published MATLAB
  (read, not copied; GPL).
- 520 µm disc, 5 µm grid, 0.01 h step. 7 tests.
- **Limit:** reproduces 5 of the source's bands; **misses** the rise and the synchrony–growth
  impairment. Retained with the miss recorded.

## Cells — BETSE

- **Label it a generic patch.** BETSE 1.5.0 (wheel sha256 `17a11601…`), called not copied. 80 µm
  square, hexagonal, **66 cells, 364 membranes**, BETSE default parameters throughout. **It is not
  fish tissue and fin applicability is an explicit unknown.**
- K⁺ permeability ×5 in 2 cells: targeted **−4.67 mV**, untargeted **−2.62 mV**.
- With gap junctions blocked: targeted **−19.8 mV**, others **−0.16 mV**.
- Block-only control: mean open fraction **0.967 → ~1e-11**, Vm moves ≤0.16 mV, because a
  homogeneous patch has almost no voltage differences to equalise.
- **Limit:** resting Vm ≈ −23.5 mV is a property of BETSE's defaults. A leak-only GHK reference
  gives +0.7 mV and the 24 mV difference is **not decomposed**.

## Metabolism

- Zebrafish-GEM (Wang 2021 PNAS, CC-BY-4.0), commit `846f0b7b3…`. **Measured from the file:**
  12,833 reactions, 8,435 metabolites, 2,709 genes, 1,658 exchanges.
- The SBML defines **no medium**; all exchanges open at ±1000 gives biomass 4.26, which is not a
  medium.
- **Call it an ASSUMED nutrient medium.** An allowlist of 58 basic nutrients → **biomass 0**. The
  cause: the biomass pool's cofactor-and-vitamin term needs vitamin E catabolites reachable only
  from **gamma-tocopherol**; the allowlist supplied alpha. Adding gamma-tocopherol gives **0.265**
  (O₂ 0), **0.291** (O₂ 20), **0.329** (O₂ 50).
- **The glucose cap of 10 and every other uptake bound are uncalibrated assumptions**, as are the
  medium composition and the flux unit. Absolute growth values mean nothing physiologically.
- Controls: all uptake closed → 0; glucose alone → 0; max |S·v| ≤ 1e-10; no energy-generating
  cycle with uptake closed.

## The fin coupling — say the assumptions with the number

- Adapter: pressure jump → line load → resultant and root moment → deflection through the existing
  `fin_mechanics` FEM. **No second beam solver was written.**
- Exact checks: uniform and linear pressure against hand closed forms, **grid order 2**, force
  conservation exact, **disabled-load control exactly 0**, deflection scaling exactly **1/EI**.
- **Measured grid limits:** h = **7.2 mm at L 32**, **0.9 mm at L 256**. Fin plates are **0.5 mm**.
  The simulated shell is **3.7 cells thick (26.9 mm at L 32)**.
- **The 923-cell figure is an arithmetic extrapolation**, not a demonstrated hardware limit: it is
  what L must reach for a 0.5 mm plate to span 2 cells at uniform spacing. **We have not run it
  and have not established that one H100 cannot.** Say "roughly thirty times finer than anything
  we have run", and give 923 as the arithmetic if asked.
- Samples carry `resolved: false` and the contract refuses them — `MEMBER_UNRESOLVED`.
- **Say "we have not established a sourced flying-fish EI profile"** — not "nobody has measured
  it". We have not searched the literature systematically enough to claim an absence.
- Related CFD limit: Cd_total 0.175 at L 24 vs 0.137 at L 32 — **27.8% apart, not grid-independent,
  so no force claim**. Re_L 200 is 13 mm/s in air; intended glide regimes are ~1.5–3×10⁵ and
  assumed.
- `docs/coupled-mechanics.md`, `docs/cfd3d.md`, `artifacts/coupled-mechanics/result.json`.

## The commons

- **Repository public** as of 2026-10-31: `github.com/kganjam/delphi-frontier`. Verified
  anonymously — API returns `"private": false`; raw `README.md` is HTTP 200 while a nonexistent
  path 404s.
- Live release **`c1ad527`**: **13 public web checks and 35 MCP checks, 0 failures**, receipts
  `deploy/receipts/rayfan-public-live-check.json` and `rayfan-mcp-live-check.json`, both stamped
  2026-10-31T23:14:54Z. The MCP suite's own scope: *"public client connectivity, search, schema
  discovery and anonymous write denial; not scientific acceptance."*
- **19 tools** — the manifest splits them **16 `read`, 3 `write`**; `frontier_design_context` is
  the newest and is a read. Anonymous reads and bounded calculations work; a well-formed anonymous
  write returns `unauthorized: Authenticated operator token required`.
- Measured 16:15 PDT: **1,315 claim versions**, 1,190 with an upstream Delphi id, **543 artifact
  declarations**. **Re-run the catalogue call before the room** — these move.
- Compute, **snapshot at 16:13 PDT, not a total**: 52 team jobs (37 current queue + 15 prior team
  and setup), 30 unattributed, 2 of ours running + 1 pulling. Relayed from root's correction, not
  re-derived here; infra is still reconciling receipts. **Quote the snapshot time or don't quote
  it.** Spend unknown — no billing meter.

## The collective result

- v3 completed: **27 requests valid**; every answer and every condition-by-repeat aggregate
  **16/16**; all three condition means identical. Conditions: one serial analyst, isolated
  specialists, specialists sharing pinned artifacts.
- **A ceiling, not a tie.** The packet stated the source fit, the stiffness range and the
  measurement method, so the task was answer-explicit.
- Communication treatment **did execute**: 9 pinned artifacts to the serial analyst, 9 peer
  artifacts to collaborators, none to the isolated arm.
- **Do not pool v2 with v3.** v2: 27 HTTP 200, all truncated at `MAX_TOKENS`, scored zero, 49,626
  tokens. v3: 53,802. Total known Google API usage **103,459 tokens over 57 requests**.
- Three **observational** coordination cases exist. The source document states they provide **no
  controlled counterfactual** and must not count as evidence of advantage. We don't count them.
- `results/capability-agency/results-card.md`, commit `92c86683`.

## The diffusion pilot — current status

- The first CUDA control **failed** and stopped before training: network CPU/GPU parity
  **0.001191914** against a **0.001** tolerance.
- A paired diagnosis in the **same allocation** confirmed the TF32 hypothesis: default backend
  reproduces **0.001191914** (fails); **explicit IEEE FP32 gives 2.265e-06 (passes)** — the same
  unchanged 0.001 tolerance. Solver parity 5.95e-14 in both.
- **Training began 16:09:38 PDT. There is no completed checkpoint and none is claimed.**
- Nothing was relaxed: source, config, architecture, optimizer, dataset, splits and tolerance all
  unchanged; the first failure is retained.
- `results/infra/diffusion-v2/backend-diagnosis.json`, job `aijob-e00qazx6sby3vav47b`.

## Agents checking each other

- A claim that the textbook Turing criterion is reliable above ~1.5 critical wavelengths was
  falsified by a probe committed **before** its output existed. Error is **windowed**: 0% at
  half-integer multiples of λc, **6.22%** at 1.25 λc, **0.58%** at 4.25 λc. Withdrawn in place,
  historical table kept. The probe's own control failed (89.53% vs a declared 90%) and shipped at
  exit 1 with the threshold untouched.
- A frozen CFD packet failed its gate — 12 STL hashes matched, the float64 candidate hash did not.
  An unchanged retry was refused; CPU-only diagnosis isolated **NumPy AVX-512 dispatch drifting 3
  fields by 1–2 ULP** while float32 STLs stayed identical. A declared geometry-only dispatch
  setting restored byte-identical output.

## If a judge interrupts

- **Does it fly?** No. Print-ready meshes exist; nothing printed, nothing flown.
- **Is the collective better?** Not established, and we ran the experiment. 16/16 everywhere — a
  ceiling on an answer-explicit task.
- **Novel architecture?** No. Prove2Me, ScienceClaw, Infinite, ASK; and Comlekoglu, Bastek and
  GenCFD for the diffusion roadmap.
- **Yours vs reused?** Sources and software are published and credited; today's work is the
  builds, solves, checks and integrations, each with a dated receipt. A commit date is when an
  artifact entered the repository, not when its content was made.
- **Believe your counts?** Don't — run the catalogue call yourself.
