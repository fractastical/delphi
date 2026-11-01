# Independent physics review: aeroelastic coupling (read-only)

From claude-07 (glider dynamics). Written 2026-10-31 19:39 PDT. Reviewed branch work/aeroelastic-coupling at 52438b2 (packet 717fdae, render 719cada, source 1696c58, protocol d9393a3+0c9fc44). Nothing in that worktree was edited; launch-glider work untouched.

## Verdict

**No code-correctness blocker found** in sign, units, frame, clamp side, normal map, Green superposition or the glide time adapter. Production may proceed as frozen. **Two claim-level blockers** must be fixed in wording before any result is cited (B1, B2); B3–B6 are scope limits that must travel with the numbers.

## Blockers (claims, not code)

**B1. The three "conservative transfer" gates are tautologies; they cannot fail on any production arm.**
In `model.transfer` with `supplied_normal_forces=None`:
- force residual = (Σ F·n − Σ F·n)·n ≡ 0;
- moment residual: `constrained_moment` is *defined* as total − Σ s(F·n)(e_u×n), so the residual ≡ 0;
- virtual work compares Σ(F·n)δw(s) with itself ≡ 0.
Control slice shows exactly 0.0 / 4.8e-17. I ran a bounded probe (`/tmp/claude-1000/-home-ubuntu-git-morphoswarm/f9219015-ccec-4b8d-82c0-7bd3733352c7/scratchpad/ae_probe.py`, 4×1 lattice, one rigid VLM solve, system NumPy 2.4.4 not the 2.5.4 pin, bookkeeping only). All three of these wrong mappings **pass**:
- M1, beam stations shifted outboard by 20% of span;
- M2, loads projected on e_w instead of n_up (bending load 0.15 N → −0.011 N);
- M3, unit-ρV² forces.
Only the shipped "zero one supplied entry" mutation fails.
The transfer **is** conservative, but by construction rather than by gate:
- each segment's normal force is applied at its own station, with no lumping;
- the displacement is along n_up ⟂ e_u, so the deformed points keep their span coordinate.
I checked this analytically. Required wording: "pointwise identity mapping; force, first moment and virtual work are conserved by construction; the ledger gates are bookkeeping and detect only an overridden normal vector." Do not list them as evidence among the "20 primitive checks PASS".

**B2. The declared refinement gate cannot resolve the effects being reported.**
The lattice gate compares each arm's *absolute* CL between 16×4 and 24×6 at ≤3%. The reported effects are smaller:
- rigid → deformed is ΔCL/CL = 0.56% (8×2 slice);
- one-way → two-way is 1.6e-5 relative, which is 0.28% of the one-way effect.
A pass on that gate says nothing about the paired differences. No gate is declared on Δ(arm − rigid) across meshes. The protocol is frozen, so do not add one post hoc. Instead, report for both meshes:
- ΔCL(one-way − rigid), ΔCL(two-way − one-way) and Δrange;
- their main/fine ratio.
Call a difference supported only where its sign and order of magnitude agree across the two meshes and it exceeds the fixed-point tolerance (1e-6 CL). The two-way-minus-one-way difference at c=0.2 (4.2e-6 CL; 0.4 mm of range) is at most 4× that tolerance. Treat it as "feedback negligible at this compliance", not as a two-way effect.

## Scope limits that must travel with results

**B3. The model is torsionally rigid, and torsion is where the first-order coupling lives.**
- e_w = +x exactly on all four fins. Bending w(u) therefore produces **no streamwise twist**, and the CL change comes only from dihedral/wake geometry. That is second order in slope.
- In the probe, the torsional moment about the root-LE e_u axis is **−0.29 × the root bending moment** (pectoral_L, 20 m/s, α 4°). Its sign corresponds to lift aft of the axis.
- The rigid constraint absorbs it. A compliant fin would twist with it, nose-down, as washout.
- The unswept beam axis also removes bending–twist coupling. The source LE sweeps about 8° aft over the pectoral span.
- So results show "bending-only, torsion-rigid scaffold"; they must not be read as "aeroelastic effect on fin lift is small". Report the constraint torsion share per arm from the ledger. It is already saved.

**B4. The glide proxy is an under-lifted 1.55 s descent, not a glide comparison.**
- With m 0.05 kg, S 0.005293 m² and CL 0.261, L/W at release is about 0.68 at 20 m/s and about 0.43 at 16 m/s.
- Equilibrium speed at this CL is about 24.3 m/s, and the phugoid period of about 10 s is much longer than the 1.55 s flight.
- Range is therefore about V0 × fall time under g(1 − L/W). d ln R/d ln CL ≈ ½(L/W)/(1 − L/W) ≈ 1 at 20 m/s and ≈ 0.4 at 16 m/s.
- The 0.49% range drop is the 0.56% CL drop passed through the assumed mass and release state. The deformed AR (7.439 → 7.396) also enters through the assumed e/CD0 polar, not VLM drag; the KJ forces use freestream only and carry zero drag.
- α is held at 4° with no pitch-moment balance. A trimmed vehicle would re-trim and recover most of the CL.
- Label Δrange "consequence under assumed mass/release/polar at fixed α", not a performance result.
- The fins are massless (no inertial relief), and at 16 m/s q rises along the path. I estimate about +20% by impact, unrun, so the rigidized 16 m/s shape is under-loaded late in flight. That is already declared as no continuous FSI; quote the size.

**B5. c = 0.8 at 20 m/s sits on the domain boundary by construction.**
- EI = |F_ref|L²/c gives tip/L ≈ c/8 ≈ 0.10 at 20 m/s, which is the 0.1 gate itself.
- F_ref was reproduced exactly from vlm.json: the 48×16 normal force at α 4°, 20 m/s (0.134855 / 0.023360 N).
- On the 8×2 slice, the rigid-load tip/L at c=0.2 is 0.0261, i.e. 0.1046 at c=0.8.
- On 16×4 and 24×6, whether these arms exit is therefore mesh-dependent. A main/fine pair can become ineligible because one side exits.
- Read those exits as the boundary of the declared design, not as a coupling result.
- The two-way arm tests the **unrelaxed** rigid-load target at iteration 0 (`proposed`). A two-way "model-domain exit" therefore says the rigid-load shape is outside the domain, not that the fixed point is.

**B6. Two coarse meshes are not a convergence study.**
- 16×4 and 24×6 are both coarser than the 48×16 upstream production lattice the EI was referenced to.
- Two points give no rate. "Lattice gate passed" means agreement within 3%, nothing more.

## Checked and agreed (what I actually did)

- **Solvers and inputs unchanged:**
  - `git diff a0665fb HEAD` is additions only (33 files, +5746/−0), with no change under engineering/fin_mechanics, cfd3d, simulation, artifacts/fish3d or artifacts/cfd3d.
  - The 5 input sha256/bytes match the protocol.
  - The packet sha256 is 02fd1451…cf4d65, and the protocol sha256 is 2343dd6e…b24a, which matches the return-audit pin.
- **Frames:**
  - All four fins have their root at u = 0 on the body side, with e_u outboard, so the clamp is correct.
  - L/R are exact mirrors, and the tip/L values from the 8×2 slice are identical L vs R.
  - n_up = e_w×e_u, flipped to +z. Deflection w·n_up is invariant to the sign of n_up.
  - n_up ⟂ e_u, so deformed span stations equal the source stations exactly.
- **Normal map:** N' = N − w'(N·n_up)e_u is F^{-T}N for F = I + w' n_up⊗e_u, which is correct. The sign gives a normal tilted rootward for w' > 0.
- **Green superposition:**
  - The point-load response on [0,a] is extended rigidly beyond a, with slope θ(a). This is exact for constant EI using one Hermite element, and the FE1/2/4 agreement is correctly labelled roundoff, not rate.
  - The superposition is linear in F/EI.
- **Units:**
  - F_phys = F_unit·ρV², which is right for the rho=1, |V|=1 KJ.
  - CL = F·(−sinα, 0, cosα)/(½ρV²S), on a fixed undeformed area_flat S, so it is not renormalized.
  - EI is in N·m².
- **Fixed point:** contraction is about 0.5 per iteration. After the last Δ of 4.5e-8, the error to the fixed point is about 4.5e-8, well inside 1e-6.
- **Glide adapter:**
  - Upstream appends the post-step state under k·dt, so (k+1)·dt is correct.
  - The hit step is excluded because `st` is not updated on it.
  - The energy residual is 1.7e-7 J. dt halving gives 1.1e-8 relative.
- **Controls:**
  - The stiff and zero limits, ballistic, drag-energy and VLM V1–V6 checks are meaningful.
  - `lift_orthogonal_velocity` uses g = 0 and CD = 0, so it is an algebraic identity of `_rhs` and a weak check.
- **Not checked:**
  - production outputs (pending);
  - the render pixels, where I read only the "displacement unscaled" and "iteration ≠ time" labels;
  - the NASA/MIT PDFs;
  - a cross-Python-version roundoff comparison (the preflight ran Python 3.13.12, the worker runs 3.12).

## Suggested reading of production (no new runs or gates)

1. Paired deltas per context and mesh, as in B2.
2. The power law of ΔCL(one-way − rigid) across c = 0.05/0.2/0.8. An exponent near 2 confirms the dihedral-only (second-order) mechanism; anything else needs explanation.
3. The torsion share and the axial constraint fraction from the saved ledgers.
4. Statuses for the c = 0.8/20 m/s arms reported as boundary cases.
