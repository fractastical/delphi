# Demo: spoken script, then presenter notes

**The script below is what you say.** It is word-counted for a three-minute slot. Every number
in it is one a listener can hold. **All other numbers live in the presenter notes** — use them to
answer questions, not to fill the three minutes.

Supersedes `archive/demo-narrative-2026-10-31-refusal-led.md`.

---

# PART 1 — THE SPOKEN SCRIPT (452 words)

### Open · on the viewer

Designing an organism end to end forces a decision at every scale — and shows which ones the
evidence can't yet support.

This is our flying fish, version three. The ray counts aren't artistic: fifteen pectoral, thirteen
dorsal, ten anal, read out of an FAO species sheet that we reuse as a record, not a citation. The
builder **refuses** any candidate breaking that sheet's rule for where the pelvic fins sit — the
first decision, made by the sheet.

### Drill · down through it

Zoom into one scale. A published model of Erk trigger waves driving bone growth in a regenerating
zebrafish scale — every parameter from the authors' own table.

Down again, to cells. BETSE, the real package, on a **generic** patch — not a fish fin, and we
don't claim it is. Raise potassium permeability in two cells and they drop about five millivolts;
so do their neighbours. Block the gap junctions and those two drop four times further while the
neighbours barely move. That's the coupling, shown by removing it.

Down again, to metabolism. A genome-scale zebrafish model ships with no medium, so we **assumed**
one. Growth came out zero — the biomass pool needed a vitamin E catabolite we hadn't
supplied. We added it; it solved.

Then we swept oxygen and growth barely moved. Not biology: under our assumed medium the model was
**making its own oxygen**, one reaction running backwards beside an uncapped vitamin. Block it and
growth collapses. That measured our medium, not a fish.

### The edge · where it stops

Now the interesting part. We built the adapter carrying flow pressure onto a fin ray. It checks
out exactly — force conservation exact, the disabled-load control exactly zero.

And it will not run. Fins are half a millimetre thick, and on our finest completed grid a fin
spans **four tenths of one cell**. The global grid doesn't resolve fin thickness anywhere we've
looked, so the contract refuses those samples rather than quietly loading them.

Underneath sits a second gap: we have not established a sourced stiffness profile for a real
flying-fish fin ray. That one's a wet lab.

**Two gaps with numbers on them, found by connecting a flow solver to a beam.** That's what the
design is for.

### Close · the commons

We are linking those decisions to the exact claims behind them. One is persisted today: the
diffusion pilot's governing equation carries its claim and problem references into the run.
**Most aren't curated yet** — that's the work, and it's why the graph is public: repository, site,
and nineteen tools where reads and calculations need no account.

One honest result. We preregistered a comparison of a single analyst against collaborating agents.
**Every arm scored full marks**, so **this task did not distinguish them.** That's a null about
our benchmark, not evidence that agents coordinate better.

---

**Pacing.** 452 words: **3:14 at 140 wpm, 3:01 at 150**. If the slot is hard three minutes, either
speak at 150 or **drop the oxygen paragraph** (−58 words → 2:47 at 140). Cut the whole metabolism
beat for 2:20, and the scale beat too for 1:55. **Never cut the edge section** — it is the thesis.

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
  at O₂ uptake 0 and **0.291** at 20.
- **THE OXYGEN SWEEP IS NOT OXYGEN DEPENDENCE and must never be presented as it.** Under the
  assumed, **uptake-uncapped** medium the model makes its own O₂ at +1000 through **MAR04071**,
  pyridoxine oxidase running in reverse beside uncapped vitamin B6 exchanges.
  - At **zero external O₂** it still grows at **0.265**; **block MAR04071 and it does not grow —
    3e-16**.
  - At O₂ uptake 20: **0.291 free versus 0.097 blocked**.
  - A **model-constraint diagnosis**, found by checking. Blocking MAR04071 is **not** biology.
- **Must not say:** that this measures oxygen dependence or fish oxygen use; that growth values are
  physiological (0.29 is a model objective flux); that the model is fin- or tissue-specific.
- **The glucose cap of 10 and every other uptake bound are uncalibrated assumptions**, as are the
  medium composition and the flux unit (mmol/gDW/h — assumed; the SBML does not declare it).
  Absolute growth values mean nothing physiologically.
- No flux table is stored at other O₂ conditions. **No new sweep until nutrient bounds have
  evidence.**
- `work/zebrafish-metabolism` @ `ee74e2d`; `o2_source_diagnostic.json`, `metabolism_results.json`.
- Controls: all uptake closed → 0; glucose alone → 0; max |S·v| ≤ 1e-10; no energy-generating
  cycle with uptake closed.

## The fin coupling — say the assumptions with the number

- Adapter: pressure jump → line load → resultant and root moment → deflection through the existing
  `fin_mechanics` FEM. **No second beam solver was written.**
- Exact checks: uniform and linear pressure against hand closed forms, **grid order 2**, force
  conservation exact, **disabled-load control exactly 0**, deflection scaling exactly **1/EI**.
- **Completed global GPU cases, and what a fin spans in each** (`summary-gpu-v1.json`). Fin plates
  are **0.5 mm**:

  | case | L | fin thickness, cells | shell, mm |
  |---|---|---|---|
  | `gpu_fish_L64_Re200` | 64 | **0.139** | 13.45 |
  | `gpu_fish_L128_Re200` | 128 | **0.277** | 6.73 |
  | `gpu_fish_L128_Re1000` | 128 | **0.277** | 6.73 |
  | `gpu_fish_L192_Re1000` | 192 | **0.416** | 4.48 |

  **A fin is under half a cell at every resolution completed, including the finest.** That is the
  statement to make: *the current global grid does not resolve fin thickness.* Do not compare
  against the older L 32 case, and **do not quote a "times finer" factor** — the global grids have
  moved and the ratio goes stale.
- **The 923-cell figure is arithmetic**, not a demonstrated hardware limit: it is what L must reach
  for a 0.5 mm plate to span 2 cells at uniform spacing. We have not run it and have not
  established that one H100 cannot. Give it only if asked, as arithmetic.
- Samples carry `resolved: false` and the contract refuses them — `MEMBER_UNRESOLVED`.
- **Say "we have not established a sourced flying-fish EI profile"** — not "nobody has measured
  it". We have not searched the literature systematically enough to claim an absence.
- **Grid-convergence pairs, stated exactly:** Re 200, L64→L128, **13.2% apart, grid rule NOT met**.
  Re 1000, L128→L192, **9.8% apart, grid rule met**. **Neither supports a physical force claim** —
  the C1 sphere reference gate **failed** and the fins are sub-grid, and the summary records
  `physical_force_claim: false` for both. Re_L 200 is 13 mm/s in air; intended glide regimes are
  assumed and unsourced, a gap factor of roughly 760-1520.
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
- **What this shows: the task did not distinguish the arms.** All three hit the rubric's maximum.
  The packet stated the source fit, the stiffness range and the measurement method, so the task was
  answer-explicit — that is the *likely* reason, and the scores alone do not prove the ceiling was
  structural. **Do not say "no room to fail"**; say the task did not separate the conditions.
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

## Receipt paths that landed late (main `8790824`)

`deploy/receipts/science-integration-20261031.json`, recorded 2026-10-31T23:20:18Z against tested
base `e8f53704`, carries **7 checks**. I read the receipt; I have **not** opened the individual
artifacts under it, so treat the per-item science as recorded-by-that-check, not inspected by me:

- Molecular returned data and controls — `pytest tests/test_molecular.py -q`, **16 passed**
- Portable packet RD software and genomics — **41 passed**; genomics alone **37 passed**
- Molecular manifest — **120 paths with matching byte counts and SHA256, root recomputed**
- **Pilot independent reconstruction — 27 distinct calls, 27 JSON/text/hash matches, all 27 scored
  16/16, 53,802 provider tokens, 18 prior-artifact references**
- Ruff on changed source — passed after 15 style fixes, scientific artifacts unchanged
- Incremental credential scan — 19 commits, 5.84 MB, **0 findings** (gitleaks 8.30.1)
- **Retained failure, kept in the receipt:** the first molecular collection stopped for missing
  OpenMM in the root venv; re-run on the isolated dependency path

`artifacts/molecular/` holds the simulation receipts (CPU controls, CPU trajectory, CUDA v2 and v3
parity, job receipts, production receipts, return verification). **The 357-perturbation-check, the
OpenFold2 confidence figures and the OpenMM 101-state trajectory now have real paths under here,
but I have not opened them.** Say "recorded at" and name the path; do not say "verified".

## If a judge interrupts

- **Does it fly?** No. Print-ready meshes exist; nothing printed, nothing flown.
- **Is the collective better?** Not established, and we ran the experiment. 16/16 in every arm, so
  the task did not distinguish them. Independently reconstructed: 27 distinct calls, 27 JSON/text/
  hash matches, all 27 scored 16/16, 53,802 provider tokens.
- **Novel architecture?** No. Prove2Me, ScienceClaw, Infinite, ASK; and Comlekoglu, Bastek and
  GenCFD for the diffusion roadmap.
- **Yours vs reused?** Sources and software are published and credited; today's work is the
  builds, solves, checks and integrations, each with a dated receipt. A commit date is when an
  artifact entered the repository, not when its content was made.
- **Believe your counts?** Don't — run the catalogue call yourself.
