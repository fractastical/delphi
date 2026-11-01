# Fidelity ladder v1: returned state and independent audit

**Status.** All 45 declared arms came back valid, and the independent audit passed with 0 findings. **No effect magnitude is resolved.** In all three contexts the bending and feedback decisions are `undetermined`, the frozen outcome that does not promote a context. Nothing was rerun, and no criterion, status or decision was changed. Every value below is a returned value or a recomputation of one. The diagnostic section is the only posthoc analysis.

## What returned
- **Run:** VM04 (`frontier-cpu-20261031-04`), task `aeroelastic-fidelity-v1`, admitted packet `dacec9a5…a457` (source 34d400f). It finished at 05:52:45 UTC (22:52:45 PDT, 2026-10-31) with scientific exit 0.
- **Raw return:** `/data/artifacts/delphi-evolve-rethink/gcp/aeroelastic-fidelity-v1/frontier-cpu-20261031-04/final-678c747967c7472ebb9460a5a8a3cffb`, collected by infra's collector.
  - Collection receipt sha256 `d8dde7f6…db79`, final manifest sha256 `c1a5c6ee…53a5`.
  - Rehashed here: 210 of 210 files, 41,826,885 bytes, 0 size or sha256 mismatches. The only unlisted file is the receipt itself.
- **Resources, measured against my runtime control:**
  - native wall time 466.7 s (critical-path estimate ≈ 283 s; cap 1200 s);
  - CPU time 28 min 49 s (estimate 1012 CPU-s, so 1.7× over);
  - memory peak 3.6 GB of 12 GiB, swap 0;
  - output 41.8 MB of 50 MB.
  - The cost of the over-run CPU estimate was nothing: the run stayed inside the cap.

## Independent audit
Ran `python -m engineering.aeroelastic.audit_fidelity` as frozen in `return-audit-protocol.json` (sha256 `dbee169c…f736a7`, code `fac619ca…22cf2`, commit b579d41), read-only on the returned tree, with Python 3.12.3 / NumPy 2.5.4 / SciPy 1.17.1. The report is `return-audit-report.json`.
- **Result:** `audit_passed: true`, 0 findings of any kind.
- **Comparisons:** 5,901, all within roundoff; 3,650 exact; worst 1.07e-14 (a reference range).
- **Identity:** the collection manifest, receipt files, executed protocol and source hashes, and pins all match the admitted packet.
- **Completeness:** all 45 identities have a `result.json`. There is no `failure.json`, no progress-only row and no crashed task.
- **Per arm:** loads, CL and the closed-form beam shape all reproduce. There are 45 fresh final-pose VLM solves.
- **Domain exits:** none. Every arm is `valid_for_declared_transfer`. Over all 1,200 saved fin-frames, the largest tip/span is 0.09934, on both pectorals of the χ0.8, 20 m/s, l36x9 one-way frozen-load arm. The maximum slope there is 0.130 rad against a 0.2 limit. That is 0.7 % inside the 0.1 tip gate. The two-way arms of that context reach 0.0965–0.0977, because their relieved load is lower. This margin belongs to the model domain, not to feasibility.
- **Other checks:** the 5 lattice-control groups pass, the 18 a54f478 references reproduce within roundoff (3 exact), and a separate three-grid implementation reproduces every native effect status and decision.

**So there are no numerical failures or domain exits to preserve in this return.** The thing to preserve is the failure to resolve, and it is kept as returned.

## Why every decision is undetermined
The frozen protocol classifies 9 quantities in each of 3 contexts: rigid CL, the three paired ΔCL effects, the three Δrange effects, and the two tip/span values. All 27 are `sign_resolved`: the same sign on all five lattices, at least 10× the numerical floor, and the 64×16 value at least 3× its step from 32×8. None is `resolved`, because the r = 2 triple (main, l32x8, l64x16) is **divergent** in all 27. The T1.5 triple is divergent, oscillatory or monotone depending on the effect.
- **Bending** (`dCL_one_way_minus_rigid`) needs a resolved effect, and it is not resolved.
- **Feedback** is not blocked by its own status. The frozen `one_way_sufficient` rule accepts a sign-resolved feedback effect, but it compares that effect with the *extrapolated* one-way effect, which does not exist. So the native reason is "one-way effect not resolved". The audit agrees.

The frozen remedy is "a finer or separated (span/chord) ladder, never a looser rule".

## Returned values (descriptive, not decisions)
The ratios below are computed lattice by lattice from `summary.json` `descriptive_series`. They show how far apart the lattices are. They are **not** extrapolated values, and they do not satisfy the frozen rules.

| Context | ΔCL one-way − rigid, five lattices | as % of rigid CL | ΔCL two-way − one-way | as % of one-way effect | Δrange one-way − rigid |
|---|---|---|---|---|---|
| χ0.8, 20 m/s | −0.005900 … −0.005756 | −2.36 … −2.32 | 8.49e-5 … 9.05e-5 | −1.54 … −1.47 | −0.530 … −0.506 m |
| χ0.8, 16 m/s | −0.003621 … −0.003537 | −1.45 … −1.43 | 2.92e-5 … 3.11e-5 | −0.86 … −0.82 | −0.0987 … −0.0954 m |
| χ0.2, 20 m/s | −0.001348 … −0.001318 | −0.54 … −0.53 | 3.62e-6 … 3.84e-6 | −0.29 … −0.27 | −0.124 … −0.118 m |

- **Spread across lattices** (max − min over mean):
  - bending effect: 2.2–2.5 %
  - feedback effect: 5.8–6.4 %
  - rigid CL: 1.25 % (0.24791 … 0.25103)
- **Cancellation:** rigid CL is the same in every context, as expected, since the rigid solve does not depend on compliance or speed. Its lattice error largely cancels in the paired differences, but not completely.

**What this does and does not say.**
- **Bending:** on every lattice the χ0.8 bending effect is above the 1 % convention and the χ0.2 effect below it.
- **Feedback:** on every lattice the feedback is one to two orders of magnitude below the 10 % convention.
- **Not decisions:** neither statement is a protocol decision. The frozen rules require resolution, and the ladder did not provide it.

## Posthoc diagnostic: the lattice family itself does not converge monotonically
This ran after the return and was not frozen; it is labelled that way in `ladder-diagnostic.json`. It is bounded: 21 rigid fixed-α unit VLM solves with the existing solver, about 1 min on one thread, and no coupled arm rerun. Code: `engineering/aeroelastic/fidelity_report.py probe`.

- **Control.** Rigid CL recomputed for each of the five lattices reproduces the returned rigid arms within 1.3e-15.
- **Refuted: faceted source normals.** Replacing the sampled source-surface normals with the flat fin-plane normal changes CL by at most 3.7e-6, which is 2–3 orders of magnitude below the lattice-to-lattice spread.
- **Refuted: planform area.** Lattice area / source area is 0.99851 … 0.99992. Normalising by lattice area leaves the same zigzag.
- **Refuted: near-singular trailing legs.** The fin chord axes lie along +x (0°). No other horseshoe's +x trailing leg comes within 0.16 panel span-widths of any collocation point; the minimum by lattice is 0.239, 0.222, 0.229, 0.178 and 0.160.
- **Separated refinement of rigid CL:**
  - **Span strips** (8 chordwise): 0.24219, 0.24943, 0.24987, 0.25087, 0.24853, 0.24796 at 16, 24, 32, 36, 48, 64. Non-monotone, peaking at 36.
  - **Chordwise panels** (32 strips): 0.25016, 0.25005, 0.24975, 0.24929, 0.24832 at 4, 6, 9, 12, 16. Monotone, but each step is larger than the last (−1.1e-4, −3.0e-4, −4.6e-4, −9.7e-4), which is not asymptotic convergence.
- **Mechanism: not identified.** Under the current lattice scheme (cosine spanwise spacing with clipped ends, uniform chordwise panels, the polygon chord sampler, and fixed +x horseshoe legs), a finer ladder is therefore **not expected** to give monotone triples. That expectation is an inference from these 21 rigid solves, not a tested prediction for coupled arms.

**Decision relevance.** Before any v2 ladder, the lattice convergence of `vlm.lattice` itself should be examined. Doing that belongs to the VLM owner, cfd04. A useful start would be an analytic planform under the same separated span and chord refinements. I recommend no automatic rerun, and no relaxation of the resolution rule.

## Visuals (actual returned states)
- `fidelity-ladder.png`: the actual value of each quantity on all five lattices, with the two frozen triples drawn as lines, in 3 contexts × 3 effects. Panel titles carry the native statuses and reasons.
- `ladder-diagnostic.png`: the posthoc separated span and chord refinement of rigid CL.
- `render-l64x16-chi0.8-u20/`: `poster.png` and `coupled-states.mp4`. This is the existing `render.render` run unchanged on the returned finest-lattice χ0.8, 20 m/s arms: 18 actual static iterations, unscaled deflection, and the separately integrated fixed-α descent. Static iterations are not physical time.
- **Provenance:**
  - `fidelity-figures.provenance.json` and `render-l64x16-chi0.8-u20/provenance.json` carry the input, code and output sha256s.
  - Figures were made with matplotlib 3.11.2, mujoco 3.17.0 and trimesh 5.2.0 in a scratch venv. That venv is not part of the scientific environment.

## Scope
This is the bending-only, torsion-rigid, fixed-α scaffold with assumed constant EI.
- The aerodynamics are inviscid thin-surface VLM with a fixed straight wake.
- The flight model is a separate rigidized-shape point-mass descent.
- Nothing here is a tissue measurement, a trimmed glide, a continuous FSI result, or evidence about real fish. Model fidelity is not biological validity. `biological_success_probability` is null.
