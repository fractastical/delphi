# The mispredication map

**Among parameter sets that pass the textbook (continuum) Turing test, what fraction admit no
unstable mode at all on a finite domain of length L with zero-flux boundaries?**

Ensemble of **30,000** two-species systems, every one of which satisfies all four continuum
conditions. Band edges from the exact quadratic; Neumann modes `q_n = (nπ/L)²`; a system is
unstable on `[0,L]` iff some integer `n ≥ 1` lies strictly inside `(L√q₋/π, L√q₊/π)`. Lengths are
reported against each system's own critical wavelength `λ_c = 2π/k_c`.

> **Correction notice (independent review, 2026-10-31).** The table below is kept as the historical result. Three limits apply to it.
> (1) It comes from a **toy ensemble**: its sampling distribution, seed and generating script are not in this repository, so the percentages describe an undeclared
> prior and say nothing about real Turing systems. (2) The earlier `mispredication_map.json` records `n_systems` 20000 and the table's `mispredication_fine.json` records 30000; the
> two files are different runs. (3) The rows from 1.50 up were tested only at 1.5, 2, 3 and 5, which are half-integer multiples of λ_c, where a mode sits exactly at the critical
> wavenumber and the rate is 0 by construction; the former claim that the criterion is "reliable (under 1%) above 1.5 critical wavelengths" is **withdrawn**. A declared-prior probe
> (`PROBE_DECLARATION.md`, `probe_declared_prior.py`, committed output) finds non-zero rates between the half-integers, see "Declared-prior probe" below.

| L / λ_c | mispredicted |
|---:|---:|
| 0.05 | 99.9% |
| 0.10 | 98.2% |
| 0.20 | 79.3% |
| 0.30 | 41.7% |
| 0.40 | 10.0% |
| 0.50 | 0.0% |
| 0.60 | 6.9% |
| **0.70** | **21.6%** |
| 0.80 | 10.0% |
| 0.90 | 2.5% |
| 1.00 | 0.0% |
| 1.25 | 6.9% |
| 1.5, 2, 3, 5 (half-integers only; 0 by construction) | 0.0% |

**Two things to read off it.**

1. **Short domains.** Below half a wavelength the textbook criterion is wrong for most systems in this toy ensemble.
   *(The former second sentence, a universal "<1% above about 1.5 critical wavelengths", is withdrawn: see the correction notice and the probe below.)*
2. **It is not monotone.** The rate falls to zero at `0.5 λ_c`, rises again to **21.6% at
   0.7 λ_c**, and reappears at 1.25. These are *windows* between admissible modes — the same
   re-stabilisation that makes the worked example stable at `π`, unstable at `3π/2` and `2π`, and
   **stable again at `5π/2`**.

## Scope, stated plainly

- Two species, linear stability, zero-flux boundaries, one dimension.
- It says nothing about nonlinear outcomes. **Subcritical patterns can form where linear theory
  says stable**, and that is not measured here.
- **Practical reach is small domains.** Most tissues are many critical wavelengths across, where
  the textbook criterion is fine. This matters for early development, engineered constructs and
  small compartments — not as a general warning about Turing's analysis.
- The underlying mathematics is **classical**: mode quantisation on a bounded domain is textbook,
  and the per-mode critical lengths are tabulated in the literature (e.g. Janovský, Appl. Math.
  67:705, 2022). The algorithm is `n ≤ ⌊L·k₊/π⌋` and is exact for rational `L/π`.
  **What is new here is the map, not the mathematics.**

## Citations — what we actually verified, and a correction to our own correction

**We do not cite a primary source for the finite-domain caveat, because we could not verify one.**

The history is worth recording, since it is the third citation error in this file's lineage:

1. We first cited **PMC9884266** for it. That is Villar-Sepúlveda & Champneys, *J Math Biol*
   86:39 (2023). It contains only a passing remark that the dispersion relation becomes
   discretised, with no minimum-size result. **Not a source for the claim.**
2. A reviewer proposed **arXiv:1407.7114** and **arXiv:2509.15829** instead, and we relayed those
   without reading them. We have now fetched both abstracts. 1407.7114 is Kurics, Menshykau & Iber
   on ligand-receptor Turing spaces; its "Turing space" is a *parameter* space, and the abstract
   says nothing about domain size, boundary conditions or mode quantisation. 2509.15829 is
   Ouchdiri et al. on a Nodal-Lefty model with weakly nonlinear analysis; its abstract likewise
   says nothing about domain size. **Neither abstract supports the claim either.**
3. **Arcuri & Murray 1986** is about boundary and initial-condition sensitivity and is also not a
   source for it.

What we can say without a citation: mode quantisation on a bounded domain is **textbook**, and
follows in two lines from the Neumann eigenvalues. Per-mode critical lengths are tabulated in the
literature — a reviewer reports Janovský, *Appl. Math.* 67:705 (2022), Def. 3.2 for Schnakenberg,
**which we have not read**. The map below is ours; the mathematics under it is not, and we decline
to attach a reference we have not checked supports it.

## Declared-prior probe (replaces the withdrawn "<1% beyond 1.5" statement)

Design committed before the output: `PROBE_DECLARATION.md`. Run: `python3 -I probe_declared_prior.py probe_declared_prior.json` (numpy only, about 20 s, seed 12345,
20,000 accepted continuum-Turing systems per prior; Jacobian entries uniform on [-2, 2], Du = 1, Dv/Du log-uniform on [1, R]). Percent mispredicted:

| L / λ_c | R = 30 | R = 100 | R = 1000 |
|---:|---:|---:|---:|
| 0.1 | 98.51 | 97.11 | 89.53 |
| 1.25 | 6.22 | 4.90 | 2.69 |
| 1.75 | 3.41 | 2.69 | 1.46 |
| 2.25 | 2.15 | 1.69 | 0.86 |
| 2.75 | 1.54 | 1.13 | 0.63 |
| 4.25 | 0.58 | 0.48 | 0.23 |
| 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0 | 0 | 0 | 0 |

- The rate is exactly 0 at every half-integer multiple and non-zero between them; it exceeds 1% at 1.75 λ_c under all three priors, and at 2.25 and 2.75 under two of three. The size of the rate depends on the prior. No threshold above which the textbook criterion is "reliable" is claimed.
- Controls: half-integers exactly 0 (pass); band-criterion vs direct eigenvalues of `J - q_n D` over 3,000 comparisons, 0 disagreements (pass); the must-fail control (at 0.1 more than 90% mispredicted for every prior) **failed on R = 1000 (89.53%)**; the committed run therefore exited 1, and the declared threshold was not edited (Amendment 1).
- This is a statement about a toy sampling distribution and a linear one-dimensional criterion, not about any organism.
