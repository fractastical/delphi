> **ARCHIVED 2026-10-31, superseded by `docs/research/demo-narrative.md`.**
> Kept because it is the record of an earlier framing, not because it is current.
>
> **Why it was replaced.** It led with refusals, stops and withdrawals and made the limits the
> whole pitch; the constructive multiscale engineering was missing. It also used a stale 11-job
> compute figure and 18 tools, and it asserted that everything happened after the repository's
> first commit — which does not follow, because an imported artifact can predate the commit that
> brought it in. Two timestamps in it are wrong: the generative page was publicly deployed at
> 15:45 PDT, not 15:29, which was only its commit.
>
> Nothing below has been edited. Read the current narrative instead.

# Demo narrative — three minutes, event receipts only

Every artifact named here was committed or measured **on 2026-10-31**, the day of the event.
Nothing from the pre-event in-house repository appears, and the two things that were *brought in*
are labelled where they come up. Timestamps are Seattle local (PDT, UTC−7).

**The spine of the talk is a clock.** The repository's first commit is **07:49 today**. Everything
that follows happened after it, in front of you.

---

## Opening — 20 seconds

> Designing a whole organism end to end is a way of finding out what we do not know.
>
> We built a shared scientific commons this morning, pointed a collective of agents at one
> concrete design, and every time the design needed a number nobody had, that gap became a pinned
> problem with an owner. The design is the instrument. The map of gaps is the result.
>
> Everything I am about to show you was committed today. Here is the clock.

---

## Beat 1 — It is live, and you do not need an account · 45s

Run it on stage, no credential:

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"frontier_catalogue","arguments":{}}}'
```

Point at three numbers and then at three absences:

- **1,287** claim versions · **1,190** carrying an upstream Delphi claim id · **1,214** with no
  declared origin
- `species.mapped_species` → **null**, *"the store has no typed taxon-identifier field … no number
  is invented"*
- `artifacts.hosted_and_byte_checked` → **0**, *"0 is the absence of any check, not a finding"*

> "A catalogue that reports its own unknowns as unknown. We show you the 1,190 and the 1,214."

Then the calculation, still with no credential — `frontier_simulate`, `model: bioelectric`:
a Hodgkin–Huxley trajectory in **1.10 s**, carrying `calibrated: false`, the sha256 of all six
model files, and the sha256 of the request so anyone can replay it.

> "A stranger with curl gets a trajectory, the hashes of the code that made it, and the model's own
> statement that it is not calibrated biology."

Then the control — a **well-formed** write, no credential:

```
unauthorized: Authenticated operator token required
```

> "Reads and calculations are open. Writes are not. An endpoint that cannot refuse anything has not
> been tested."

**Receipts:** `data/research/mcp-probe-2026-10-31/` — six raw responses, measured 15:08–15:16 PDT.
18 tools, 15 read and 3 write. Repo first commit **07:49 PDT today**.

---

## Beat 2 — We preregister, and we stop · 35s

Two experiments, both preregistered before the result existed, both finished today:

| | preregistered | outcome | gap |
|---|---|---|---|
| oca2 exon 21 in the Molino assembly | **10:29** | **absent from all 1,361,196,561 bp**; flanking exons present once each | 97 min |
| KCNE1 binding ΔΔG | **10:48** | **STOPPED** — 20.27% coverage against a preregistered 75% floor | 20 min |

> "One closed. One we stopped ourselves, twenty minutes after writing the criterion, because the
> structure could not meet the floor we had already committed to. A pass there would have been a
> false positive."

**Receipts:** `preregistrations/2026-10-31-*.md`, `results/2026-10-31-*.md`. Commits `f497073`,
`aa29a6d`, `dcdc5f4`, `3272d3e`.

---

## Beat 3 — The collective falsified one of our own claims · 50s

**This is the centre of the talk.**

A claim entered the commons in the seed commit at **07:52** — *brought in, not produced here*:
that the textbook Turing criterion is reliable, under 1% error, above about 1.5 critical
wavelengths.

At **12:05**, four hours later, an agent falsified it. The probe was committed *before* its output
existed, with its priors, grid and controls declared in advance.

What it found: the error is **windowed, not monotone**.

| L / λc | 0.5 | 1.0 | **1.25** | 1.5 | 2.0 | **4.25** | 5.0 |
|---|---|---|---|---|---|---|---|
| mispredicted | 0.0% | 0.0% | **6.22%** | 0.0% | 0.0% | **0.58%** | 0.0% |

Every zero is a half-integer multiple of the critical wavelength — which is **exactly where we had
sampled**. Between them the criterion fails, and it never stops failing.

The claim is now **withdrawn in place**, with the historical table kept and the correction
attached.

And the probe's own declared control **failed**: it required over 90% misprediction at a tenth of
a wavelength and got **89.53%**. The author left the threshold alone and shipped at **exit 1**.

> "Say both timestamps. The table was brought in at 07:52. The falsification, the failed control
> and the withdrawal are ours, at 12:05. `git log` settles it either way, so we say it first."

**Receipts:** `bench/mispredication/PROBE_DECLARATION.md`, `probe_declared_prior.out`,
`README.md`. Commits `e4ab195`, `b9f603b`, `81ca466`, all **12:05 PDT**. Cross-check: 3,000
band-versus-eigenvalue comparisons, 0 disagreements.

---

## Beat 4 — Real compute, failures included · 25s

**11 Nebius GPU and CPU jobs**, 11:31–13:44 PDT, each with a job id, UTC window, in-container exit
code, returned bytes and sha256.

**3 failed. 1 was cancelled. All four are still in the table.**

Cost: *unavailable* — the event exposes no price receipt to participants, and that is not the same
as zero.

> "A provider state of COMPLETED means the container exited. It does not mean a scientific result
> exists. That sentence is in our own receipt file."

**Receipt:** `results/compute/RECEIPT.md`.

---

## Beat 5 — Where it goes, and what is not done · 30s

One pilot is frozen and waiting for a GPU: a conditional diffusion surrogate for a 1-D
reaction-diffusion field. Preregistration, solver, model and tests at **15:32**; job packet and
CPU control receipts at **15:33**. Splits by whole setting and whole seed, a shuffled-condition
null among the baselines, CPU controls passing, 13 tests passing.

**No GPU result yet. Nothing trained.**

> "We build on published work and we name it — Comlekoglu and colleagues trained a diffusion
> surrogate for a Cellular-Potts model of vasculogenesis; Bastek and colleagues put physics
> residuals in the training loss; GenCFD did conditional diffusion over simulator statistics. No
> first in diffusion for synthetic biology is claimed. What we add is the loop: the synthetic data
> carries the claim that licensed its equation, so a withdrawal reaches the training set — and the
> solver doing the rejecting carries scope conditions, because we just measured one that is wrong
> in windows."

**Receipts:** `9c56a927`, `4a5394f3`, both 2026-10-31. Live page: `#/generative`, published
**15:29** today.

---

## Close — 20 seconds, the honest column

| Real, today, with receipts | Not shown |
|---|---|
| Public MCP, anonymous reads and calculations, writes refused | Any other team using it — bonus **unearned** |
| A claim falsified and withdrawn in place | A measured collective-vs-single advantage |
| Two preregistrations, one closed and one **stopped** | Any GPU-produced biological result |
| 11 jobs with 3 failures and 1 cancellation kept | Any physical print, flight, or living fish |
| A diffusion pilot frozen before training | Anything trained |

> "The right-hand column is the honest state. The matched-budget comparison of one agent against
> a collective is preregistered and running, and it has no result. If it comes back null we will
> report the null — the way we reported this one."

---

## If a judge interrupts

- **"Is any of this older work?"** The repository's first commit is 07:49 today and all of its
  commits are dated today. Two things were brought in and we label them: the imported claims
  corpus, where 1,190 of 1,287 versions carry an upstream Delphi id and most read
  `imported_unreviewed`, and the historical mispredication table from the 07:52 seed commit, whose
  generating script is not in the repository.
- **"Does the fish fly?"** No. Print-ready meshes exist; nothing has been printed and nothing has
  flown.
- **"Did the collective beat one agent?"** Not measured yet. An earlier scale study of ours
  returned a null, 78/100 against 78/100.
- **"Why should I believe your counts?"** Do not. Run the catalogue call yourself from your laptop.

Longer answers: `docs/research/rubric-pitch.md` §4 (Q1–Q10).

---

## Timings

| Beat | Length |
|---|---|
| Opening | 0:20 |
| 1 — live endpoint, three probes | 0:45 |
| 2 — preregister and stop | 0:35 |
| 3 — the falsification | 0:50 |
| 4 — compute with failures | 0:25 |
| 5 — roadmap and the pilot | 0:30 |
| Close | 0:20 |
| **Total** | **3:05** |

Cut beat 2 to reach 2:30. Do not cut beat 3.

**The print/viewer beat is deliberately absent** — the viewer is on v3 and moving. If a stable
build lands, it goes between beats 4 and 5 at 15 seconds, and the only sentence it may carry is
that the model geometry shares hashes with the renders. **Never "printed forms": no physical print
has occurred.**
