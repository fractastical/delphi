# SHH–GREM1–BMP–FGF limb outgrowth loop — model provenance and limits

**This is a simulation.** Every number in `shh-loop.json` and every curve in the three PNGs is
model output. None of it is an observation of any embryo, and none of it was measured. The model
reproduces a *published signalling topology*; it is not calibrated to any published *measurement*.

Run it with `python3 shh_loop.py` in this directory. It is deterministic — no random number
generator is used anywhere in the model, so the run reproduces exactly without a seed.

---

## 1. What the model is

Six ODEs in non-dimensional time. Five signalling states plus one accumulated readout:

| symbol | meaning | compartment |
|---|---|---|
| `S` | SHH | posterior mesenchyme (ZPA) |
| `G` | GREM1 | limb bud mesenchyme |
| `B` | active (unbound) BMP | limb bud |
| `F` | FGF4/8 | apical ectodermal ridge (AER) |
| `Z` | former-ZPA descendant zone, fraction of Grem1-competent mesenchyme displaced | posterior mesenchyme |
| `L` | accumulated outgrowth (proximodistal extent proxy) | — |

```
dS/dt = s·H⁺(F; K_FS, n_FS) − d_S·S
dG/dt = g·[ a_B·H⁺(B) + a_S·H⁺(S) ]·(1−Z)·H⁻(F; K_FG, n_FG) − d_G·G
dB/dt = b·b_prod − d_B·B − k_seq·G·B
dF/dt = φ·H⁻(B; K_BF, n_BF) − d_F·F
dZ/dt = k_Z·H⁺(S; K_SZ, n_SZ)·(1−Z)
dL/dt = H⁺(F; K_FL, n_FL)
```

`H⁺` and `H⁻` are activating and repressing Hill functions. The four design knobs are
`s` (ZPA Shh transcriptional output — the ZRS knob), `φ` (AER initiation / FGF10 input),
`g` (GREM1 production) and `b` (BMP production); all are 1.0 at wild type.

**Initial condition:** `S = G = F = Z = L = 0`, with `B` at its unantagonised steady state.
BMP is present first because Bénazet et al. 2009 report that BMP4 *initiates* Grem1.

### Non-dimensionalisation — what it removed

1. **Time** is measured in SHH turnover times, i.e. `d_S ≡ 1` by definition. One time unit is one
   SHH decay time, **not** one hour. Nothing in this model fixes the conversion to real
   developmental time, so no duration it reports can be compared to a staged embryo.
2. **Each species is scaled by its own maximum**, so the unantagonised BMP steady state
   (`b_prod/d_B`) and the underepressed AER FGF steady state (`φ/d_F`) are both exactly 1.0 at
   wild type. Every Hill constant can then be read as "fraction of maximum", which is the only
   thing that makes them interpretable at all in the absence of calibration data.

That removes two of the 23 parameters: `d_S` is fixed to 1 by the choice of time unit, and
`b_prod` is fixed by `d_B` so that maximal BMP is 1. **The other 21 remain free, and all 21 are
labelled `assumed`. Not one parameter in this model is labelled `sourced`** — no paper cited here
reports a rate constant, a Hill coefficient or an absolute concentration for this loop. What the
literature supplies is the *topology* (which arrow points where, with what sign) and the relative
*timescale ordering* (Bénazet 2009's fast BMP/GREM1 module versus the slow SHH/GREM1/FGF loop).
Everything numerical is mine.

---

## 2. Provenance, edge by edge

Every regulatory edge below is carried in `shh-loop.json` under `model.edges` with its PMID.
**Read level is `abstract` for every source in `sources`** (the JSON states the count and the
set of read levels, so neither is hand-written): the edges are taken from statements made in
the abstracts, not from figures or supplementary data. PMIDs and DOIs were each resolved through
the PubMed E-utilities MCP tools (`lookup_article_by_citation`, then `get_article_metadata` to
confirm the title and DOI). Bibliographic metadata retrieved from PubMed.

| # | edge | source | the source's own words |
|---|---|---|---|
| 1 | FGF → SHH | Zúñiga 1999, PMID 10524628 | "FGF4 signalling by the posterior AER, which in turn maintains the polarizing region (SHH/FGF4 feedback loop)" |
| 2 | SHH → GREM1 | Zúñiga 1999, PMID 10524628 | "SHH signalling is required for maintenance of Gremlin" |
| 3 | BMP → GREM1 (initiation) | Bénazet 2009, PMID 19229034 | "BMP4 first initiates and SHH then propagates e-m feedback signaling through differential transcriptional regulation of Grem1" |
| 4 | GREM1 ⊣ BMP | Zúñiga 1999, PMID 10524628; Michos 2004, PMID 15201225 | "the secreted bone-morphogenetic-protein (BMP) antagonist Gremlin"; "Gremlin-mediated BMP antagonism" |
| 5 | BMP ⊣ FGF | Zúñiga 1999, PMID 10524628 | "Formin-dependent activation of the BMP antagonist Gremlin is sufficient to induce Fgf4" |
| 6 | FGF ⊣ GREM1 | Verheyden & Sun 2008, PMID 18594511 | "FGF signalling can repress Grem1 expression… dependent on high FGF activity" |
| 7 | SHH → Z | Scherz 2004, PMID 15256670 | "Shh-expressing cells and their descendants cannot express Gremlin. The proliferation of these descendants forms a barrier… which breaks down the Shh-Fgf4 loop" |
| 8 | Z ⊣ GREM1 | Scherz 2004, PMID 15256670 | same sentence |
| 9 | FGF → outgrowth (readout) | Sekine 1999, PMID 9916808; Min 1998, PMID 9784490 | "limb bud formation was initiated but outgrowth of the limb buds did not occur… the AER and the ZPA did not form" |

**Two of these are my inference, not the authors' sentence, and the JSON marks them as such.**

- Edge 5: Zúñiga 1999 state that GREM1-mediated BMP antagonism *induces* Fgf4. That BMP therefore
  *represses* AER Fgf is my reading of their mechanism, not a sentence they wrote.
- Edge 9: Sekine 1999 report that Fgf10-null limb buds initiate but do not grow out and form no
  AER. That AER FGF is *the proximate driver of progenitor expansion* is how I use that result; it
  is a modelling choice, not their claim.

### Why each knob is the knob

| knob | what it represents | source |
|---|---|---|
| `s` | fraction of wild-type ZPA Shh output — what a ZRS allele changes | Kvon 2016, PMID 27768887: snake-ZRS knock-in mice show "severe limb reduction", and "restoration of a single transcription factor binding site… reinstated full in vivo function". Leal & Cohn 2016, PMID 27773569: in python hindlimb buds "SHH transcription is weak and transient… leading to early termination of a genetic circuit that drives limb outgrowth" |
| `φ` | AER initiation / FGF10 input; `φ = 0` is the Fgf10-null route | Sekine 1999, PMID 9916808 and Min 1998, PMID 9784490 (complete limb absence, no AER). Niemann 2004, PMID 14872406 puts human WNT3 Q83X tetra-amelia on the same upstream route |
| `g` | GREM1 production; `g = 0` is the Grem1-null route | Michos 2004, PMID 15201225: "mesenchymal Grem1 is required to establish a functional apical ectodermal ridge" |
| `b` | BMP production | Bénazet 2009, PMID 19229034 |

Sheth 2012 (PMID 23239739) is cited **only to mark what this model does not cover** — digit number
and digit pattern. No edge is taken from it.

---

## 3. The assumed parameters, and why each has the value it has

All 21 are listed with a one-line justification in `shh-loop.json` under
`model.parameters` (`status: "assumed"`). The four that actually carry the result:

- **`a_B = 0.22`** — the weight of the BMP→Grem1 *initiation* arm. Deliberately set **below** the
  value at which that arm alone sustains the loop. This was not a free choice: at `a_B = 0.40` the
  BMP–GREM1 module reaches a self-sustaining fixed point, and the model then says an
  **Shh-null limb overgrows**, which is wrong. Lowering it makes initiation a *transient* that the
  slower SHH loop must catch — which is what Bénazet 2009 describe, and which is what gives the
  `s` knob a sharp ignition threshold at all.
- **`k_seq = 80`** — GREM1's rate of removing active BMP. Must exceed `d_B = 10`, or antagonism
  cannot move BMP fast enough against its own turnover and **the loop never engages for any knob
  setting**. At the first value tried (`k_seq = 8`) AER FGF stalled at 0.067 and no limb grew
  under any parameters.
- **`K_FG = 0.75`** — set deliberately *above* the loop's operating FGF level, because Verheyden &
  Sun 2008 say the Grem1 repression is "dependent on **high** FGF activity". If it engaged at the
  operating level the loop could never be maintained.
- **`k_Z = 0.08`** — sets the *length* of the outgrowth window. It is the parameter the window
  duration is most sensitive to, and it is wholly assumed. No sensitivity analysis over the full
  parameter space was run.

### One readout parameter was changed because it manufactured a result

`n_FL` (sharpness of the outgrowth readout) is 10, not the 6 first used. At `n_FL = 6`, the
sub-threshold FGF leak in arms where **the loop never engages** integrates, over the 80-time-unit
window, into an apparent "rudiment" at `s = 0`. That looked like a result — a graded ZRS allelic
series bottoming out in a vestige — and it was an artifact of the readout integrating leak over a
long window.

Re-measured at the shipped parameters (both arms run for this note, not quoted from the tuning
session):

| `n_FL` | `L` at `s = 0` | `L_wt` | ratio |
|---|---|---|---|
| 6 | 0.5917 | 16.9890 | **3.48%** of wild type |
| 10 (shipped) | 0.0232 | 17.7055 | **0.131%** of wild type |

**It does not go to zero, it goes to 0.131%**, which is below the 5% `no-limb` cut and so no
longer changes any class. Saying "removed" would overstate it: the leak is suppressed, not
eliminated, and a longer simulated window would grow it again. The honest consequence is in §6:
the model can no longer appear to distinguish an Shh-null limb from true amelia, because it never
could.

---

## 4. The control arm

See `shh-loop-control.png` and `control_arm` in the JSON.

The control arm was built first and the sweeps were only run once it passed. The criterion was
fixed in advance: **wild-type parameters must produce a loop that initiates, is maintained for a
bounded window, and self-terminates.** `shh_loop.py` raises `SystemExit` and runs nothing else if
that fails, so a published sweep cannot exist without a control arm that passed.

| quantity | value | units |
|---|---|---|
| loop engages | t = 3.97 | SHH turnover times |
| loop self-terminates | t = 29.30 | SHH turnover times |
| outgrowth window | 25.34 | SHH turnover times |
| peak AER FGF | 0.79 | fraction of maximum |
| peak SHH | 0.94 | fraction of maximum |
| peak GREM1 | 0.54 | nondimensional |
| former-ZPA zone at t = 80 | Z = 0.900 | fraction |
| accumulated outgrowth | L_wt = 17.7055 | nondimensional (sets the 100% reference) |

The sequence is the published one. BMP starts at its unantagonised maximum and induces GREM1;
GREM1 sequesters BMP, which de-represses AER FGF; FGF turns on ZPA SHH; SHH takes over GREM1
maintenance from BMP and the loop is self-sustaining. It then switches itself off by two
mechanisms at once, both sourced: FGF rises past `K_FG` and represses Grem1 (Verheyden & Sun
2008), and the former-ZPA zone `Z` expands and removes Grem1-competent mesenchyme (Scherz 2004).

### Which mechanism actually terminates the loop — measured, not assumed

I first wrote here that `Z` makes termination irreversible while the FGF⊣Grem1 edge alone would
let the loop re-ignite. **That was an assertion, so I ran the ablation, and it was wrong in its
detail.** Knocking each mechanism out, simulated to t = 200 (`termination_ablation` in the JSON):

| arm | terminates? | window | FGF at t = 200 |
|---|---|---|---|
| both mechanisms (wild type) | **yes** | 25.34 | 0.055 |
| no descendant-zone ratchet (`k_Z = 0`, Scherz removed) | **no** | 196.06 | 0.809 |
| no FGF⊣Grem1 repression (`K_FG → ∞`, Verheyden & Sun removed) | **yes** | 26.35 | 0.054 |
| neither | **no** | 196.07 | 0.972 |

Without `Z` the loop does not oscillate or re-ignite — it simply **never switches off**, sitting
at high FGF indefinitely. And removing the FGF⊣Grem1 repression barely matters: termination
survives and the window lengthens by **+3.99%** (25.34 -> 26.35).

**So in this parameterisation the two published termination mechanisms are not equal partners,
and the model leans almost entirely on Scherz 2004.** That is a real limitation, stated here and
in `limitations` in the JSON: the self-termination in the control figure is mostly one mechanism,
and nothing here establishes which dominates in an embryo. It is also a property of this
parameter set only — `k_Z` is assumed, and no parameter scan was run.

**Three failures found and fixed while building the control arm**, recorded because each one
looked like a result:

1. `k_seq = 8`: the loop never engaged at any knob setting. AER FGF stalled at 0.067. GREM1 could
   not move BMP faster than BMP's own turnover.
2. `a_B = 0.40`: the loop engaged and **never terminated at `s = 0`** — the BMP–GREM1 module alone
   held a self-sustaining fixed point, so an Shh-null limb *overgrew*. Lowering `a_B` makes
   initiation a transient, as Bénazet 2009 describe.
3. `n_FL = 6`: a spurious 3%-of-wild-type "rudiment" appeared at `s = 0`, which was sub-threshold
   FGF leak integrated over 80 time units, not biology. See §3.

---

## 5. Thresholds, with numerical uncertainty

### The ignition thresholds

A threshold here is the **ignition bifurcation**: the knob value at which AER FGF first exceeds
`F_on = 0.35` at any time. It is located by 45-step bisection, not read off a grid.

| knob | threshold | numerical uncertainty | what is below it |
|---|---|---|---|
| `s` — ZPA Shh output (the ZRS knob) | **0.3075** | ± 0.0001 | loop never ignites |
| `φ` — AER initiation / FGF10 | **0.5862** | ± 0.0001 | loop never ignites |
| `g` — GREM1 production | **0.5549** | ± 0.0001 | loop never ignites |
| `b` — BMP production | **window [0.4421, 1.3014]** | ± 0.0001 | below: no off switch; above: never ignites |

### Phenotype bands (from `sweeps[*].phenotype_class`)

| knob | no-limb | truncated | normal | overgrowth |
|---|---|---|---|---|
| `s` | ≤ 0.31 | 0.32 – 0.48 | ≥ 0.49 | — (saturates at 1.00) |
| `φ` | ≤ 0.58 | 0.59 – 0.86 | 0.87 – 1.19 | ≥ 1.20 |
| `g` | ≤ 0.55 | 0.56 – 0.83 | 0.84 – 1.20 | ≥ 1.21 |
| `b` | ≥ 1.31 | 1.13 – 1.30 | 0.90 – 1.12 | 0.45 – 0.89 (and ≤ 0.44 fails to terminate) |

**The headline, stated as a property of the model:** the transition is nearly digital. For the ZRS
knob there is no gradual allelic series — `s` can fall to about **half** of wild type with a limb
still classed normal, the truncated band is only **s ∈ [0.32, 0.48]**, and below **s ≈ 0.31**
nothing ignites at all. Within this model that is a consequence of the double-positive-feedback
topology, which is excitable: initiation is a BMP-driven transient that the slower SHH loop either
catches or does not.

This is *qualitatively* the behaviour Kvon et al. 2016 report — restoring a single transcription
factor binding site reinstated full enhancer function — but the agreement is a resemblance between
a model's bifurcation and a published phenotype, **not a fit**, and the model was not tuned to
reproduce it.

**`s` saturates at 1.00 and the other knobs do not.** Raising ZPA Shh above wild type buys no
extra outgrowth, because `F` is already near its ceiling and SHH's only route to outgrowth is
through a saturated FGF. Raising `φ` or `g` does overgrow. That asymmetry is a prediction of this
topology, and nothing here tests it.

### Numerical honesty

| arm | result |
|---|---|
| refinement: 4 integrator/tolerance settings (LSODA 1e-6/1e-9; LSODA 1e-11/1e-13; Radau 1e-10/1e-12; DOP853 1e-11/1e-13) | threshold spread **6.4e-7** (`s`), **2.0e-8** (`φ`), **9.0e-8** (`g`) |
| control-arm outgrowth across the same four | spread 8.6e-5 absolute, **4.9e-6 relative** |
| null control (all production zero, zero initial condition) | `max|state| = 0.0` exactly — PASS |
| time-rescaling invariance (all rates × 3, window ÷ 3) | max trajectory difference **8.4e-13** — PASS |
| outgrowth: ODE state vs trapezoid re-integration of its own integrand | relative difference **4.8e-6** — PASS |
| classifier positive control (4 cases that must each return a known class) | **4/4** PASS |
| derived counts match the tables they describe | PASS, and its own positive control flags a deliberately broken copy |

**No count in the JSON is written by hand any more.** Parameter totals, the source count, the
class cuts, the bisection depth, `F_on`, `T_end` and the ablation percentage are all f-strings
over the constant or the table they describe, and `check_derived_counts` asserts that the prose
and the table agree before the file is written. This exists because the opposite happened: an
earlier copy of `limitations[2]` said "Fourteen of the eighteen parameters are assumed" while the
parameter table held 23 entries, 21 of them assumed — a sentence that both contradicted the table
on the same page and *understated* the assumption load, which is the direction that matters.

The thresholds are reported to 4 decimal places with **± 0.0001**, which is a floor, not a
measurement: the actual integrator spread is 3–4 orders of magnitude smaller. Quoting the true
spread would imply a precision an uncalibrated model does not have.

**The classifier carries a positive control because a check whose subject includes the check is
not a check.** Four settings whose class is known by construction — wild type → `normal`,
Grem1-null (`g=0`) → `no-limb`, Fgf10-null (`φ=0`) → `no-limb`, no BMP (`b=0`) → `fails-to-terminate`
— must each come back correctly, and the script exits non-zero if any does not. A classifier that
cannot flag a case it must flag would make every "no-limb" cell in the phase map meaningless.

**No symmetry check is claimed, because the model has no spatial symmetry to mirror.** The
time-rescaling invariance above is the meaningful structural check available: it tests the
implementation (that no rate is baked into a term and the initial condition scales correctly),
not the biology.

---

## 6. What this model does NOT establish

Read this section before quoting any number above on a web page.

**It is a caricature of a signalling topology, not a model of a limb bud.** It is not calibrated
to any measured mouse limb bud. No concentration, rate, diffusion length or developmental time in
it was fitted to data, and none should be read as one. 21 of the 23 parameters are assumed and
none is sourced.

**A threshold in this model is a threshold in this model.** `s = 0.3075` is not a prediction of
the ZRS allelic dose at which a mouse loses a limb. It has no units that could be compared to one,
and the model offers no way to map `s` onto a measurable quantity such as Shh transcript count or
ZPA domain size.

**The control arm's qualitative behaviour was an input to parameter choice, not an independent
result.** Parameters were chosen so the wild-type arm initiates, is maintained and self-terminates.
That the wild type does those three things is therefore not evidence for the model. What the
sweeps add is the *shape* of the response to each knob, which was not tuned for.

**The self-termination it demonstrates is mostly one of the two published mechanisms.** The
ablation in §4 shows the loop leans almost entirely on the Scherz 2004 descendant-zone ratchet;
removing the Verheyden & Sun 2008 FGF⊣Grem1 repression changes the window by +3.99%. The
control figure should not be read as evidence that both published mechanisms are doing work here.

**The model is non-spatial.** SHH, GREM1, BMP and FGF are single well-mixed levels. The real loop
is spatially organised across an epithelial–mesenchymal boundary with measured gradients, and the
Scherz 2004 mechanism it borrows is explicitly geometric — an expanding descendant zone. The
variable `Z` is a zero-dimensional stand-in for that geometry.

**It cannot distinguish an Shh-null limb from true amelia, and its "no-limb" class does not mean
amelia.** The model contains no SHH-independent proximal outgrowth. Real Shh-null mice still form
proximal skeleton; real Fgf10-null mice form none. In the model both come out as "no-limb" — at
`φ = 1`, any `s ≤ 0.31` is classed no-limb, exactly as `φ = 0` is — because the class means only
*this loop never engaged*.

**So the two routes are indistinguishable in the model and are not indistinguishable in a mouse,
and that gap is the model's, not the literature's.** A reader of the phase map must not conclude
that a sufficiently dead ZRS gives amelia. The honest reading of the grey region is "this
feedback loop contributed no outgrowth", and what skeleton remains depends on SHH-independent
proximal patterning that is nowhere in these equations.

**Digit number and digit pattern are entirely outside the model.** Sheth et al. 2012 (PMID
23239739) show digit patterning is a Turing-type mechanism whose wavelength distal Hox genes set.
None of that is represented here. The model says nothing about how many digits form, and the
"normal" class means "normal outgrowth duration", not "a normal limb".

**The knob `s` is constant in time.** The defect reported in python hindlimb buds is that SHH is
weak *and transient* (Leal & Cohn 2016, PMID 27773569). A time-varying `s` is not explored, so the
model captures only the "weak" half of a two-part phenotype.

**The class boundaries are assumed, not derived.** 5%, 85% and 115% of the wild-type control are
cuts chosen for the figure. The ignition thresholds are *not* arbitrary in this way — they are a
genuine bifurcation of the dynamics — but the `truncated`/`normal` boundary is.

**The window duration is most sensitive to `k_Z`, a wholly assumed parameter, and no sensitivity
analysis over the full parameter space was run.** The reported uncertainty is numerical only. It
is the uncertainty from the integrator, and it says nothing about uncertainty from the parameters,
which is the dominant term by far and is not quantified anywhere in this artifact.

**Every source was read at `abstract` level** — `provenance.read_levels_present` in the JSON is
the authority, and it lists exactly one level. Every regulatory edge is taken from a
sentence in an abstract, not from a figure or supplementary data. No source was read in full text.
