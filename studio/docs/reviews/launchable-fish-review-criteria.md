# Preregistered review criteria: launchable fish glider (SPEC-010)

Reviewer: an independent AI agent process (not a lab, not a human; not the 05/07/04 authors). Written from SPEC-010 and
`data/materials/formlabs-studio-2026-10-31.json` (+ `source-cell-check.json`) at origin/main `2d041fc`, **before** any prototype output was seen.
It reviews assumptions and requirements, not results. It does not duplicate physics, and it does not demand organism biology: this is a labelled
manufactured glider; biological realizability stays a separate frontier question.

Read: SPEC-010 in full; both material files (card file sha256 `44b6b07f...` matches the `material_cards_sha256` in the cell check, I computed it).
Not read: the v3 geometry, any mesh, any dynamics code, the cell-check source HTML (bytes are outside the repo).

## Blocking issues in the requirements as written (answer before building more)
1. **Range alone cannot show gliding.** A no-lift, no-drag ballistic body released level from 1.2–1.5 m lands at 1.98–2.21 m (4 m/s), 2.97–3.32 m (6),
   3.96–4.42 m (8). A 45 degree lob with no lift reaches 7.6–7.8 m at 8 m/s and 4.6–4.8 m at 6 m/s, i.e. the 5–8 m target is met at 8 m/s with no
   aerodynamics at all. At 4 m/s reaching 5 m needs 1.25 s in the air, so mean sink from 1.2 m must stay under about 0.96 m/s. Required: declare the
   launch pitch angle in the frozen protocol, and for every candidate and speed report the **same-mass, same-drag no-lift control** and the glide gain
   over it (time of flight, distance, or both). A claim of "glided across the room" without that control fails.
2. **Launch load is open-ended without a peak model.** Average acceleration V0^2/(2s) is 26.7 m/s^2 (2.7 g) at 4 m/s over 0.3 m, and 320 m/s^2 (32.6 g)
   at 8 m/s over 0.1 m. For an ideal linear elastic launcher the peak is exactly **2x** the average (work balance), a half-sine pulse of equal impulse peaks at
   pi/2 x, a rectangular pulse at 1x. Required: bracket the peak factor at least over {1, pi/2, 2}, and state why larger factors (stiction, snap-back, band
   preload) are or are not excluded. Report loads per part, not only on the body.
3. **Material allowables are not fin-level.** The cards give ultimate tensile strength, moduli and elongation from bulk ASTM coupons at 100 micrometre,
   default post-cure; no yield point, flexural strength, fatigue, impact, humidity/creep, orientation or thin-feature data (the card says so). Required:
   an explicit knock-down on the allowable stress with its rationale, and an orientation case; no pass/fail on UTS x 1.0. The Tough 1500 card is Form 4 reference-only
   with a null source hash; it may not be used as the prototype material without that stated.
4. **"Actual source-conditioned aero" needs a definition.** SPEC-010 says the failed sphere references, unresolved fins and unconverged VLM cannot supply
   validated polars, and the flying-fish sources are excerpts or abstracts. So the coefficients will be scenario assumptions. Required: each coefficient carries
   its source, read level, Reynolds range and applicability; range is a bracket, not a polar; the sensitivity of range and trim to each coefficient is reported
   separately from numerical convergence (SPEC-010 already requires the separation).
5. **Scale and mass are unstated.** 1:1 printed fins and Alpha Grey are coordinator defaults, not user answers (SPEC-010 says so). The mass and Reynolds number follow from the
   ancestor's size, which I have not seen. Required: release the chord, span, mass, Re = V c / nu (state nu) and wing loading with the first revision, and keep the
   scale and material changeable without overwriting.

## Criteria by area (each is checkable on delivered files)
**Mesh-derived mass, centre of mass, inertia.** Closed, manifold, consistently oriented mesh per part (report open edges, flipped normals, self-intersections, unit
and scale, volume sign). Mass = solid density (1220 kg/m^3 for Alpha Grey; the liquid 1110 is explicitly not for part mass) x enclosed volume. Centroid is the volume centroid (not a vertex
average); inertia by exact integration about the assembly CG with the parallel-axis step shown. Hollow parts: shell thickness, drain/vent holes removed from volume, trapped-resin case stated.
Ballast, adhesive, finish, retained process material and supports are separate lines with unknowns visible; display props excluded. I will recompute volume, CG and inertia from the delivered mesh with my own
code and compare; a discrepancy beyond numerical tolerance (declared before I compare) is a finding.

**Root / ray / membrane strength against added mass.** One load case table: launch inertial load (from the bracketed peak), aerodynamic load at the highest q in the sweep,
and landing/impact as an explicit unknown unless measured. Root bending stress sigma = M c / I with M from the actual load distribution, shear and bearing at the joint, the printed-joint
and layer-orientation limitation, and the membrane separately from rays. The mass penalty of each reinforcement is reported against a stated baseline, and a Pareto of strength or stiffness against added mass is required;
uniformly thickening is not a tradeoff (SPEC-010 item 8). Reuse the existing beam code in `engineering/fin_mechanics` for the linear model and report its validity limits; no new solver for the same equation.
Static aerodynamic deflection must stay inside the declared small-deformation limit or be labelled invalid.

**Launch load and contact offsets.** Coordinates of the pouch/contact point, load direction and the actual CG in one frame; offset e and release torque T = F x e, angular impulse and release pitch/yaw rate
with I from the mesh; local reinforcement at the contact; clearance and complete release (no retained tether). Sweep contact offset and alignment error; a contact through the CG is a control, not the design.
No statement that the glider survives launch without a measured coupon or flight.

**Trim and stability.** Pitching moment about the manufactured CG: Cm(alpha), the trim alpha at Cm = 0, dCm/dalpha at trim (negative for static pitch stability), neutral point and static margin, plus the
perturbation response over a declared alpha interval. A CG-ahead-of-aerodynamic-centre sign check alone fails (SPEC-010). Roll and yaw: stated as unanalysed or analysed, never silent. Trim speed and the lift needed for that
weight at the sweep speeds, with the stall or validity boundary of the coefficients named.

**Trajectory and controls.** Integrated equations of the selected candidate, time-step refinement, energy accounting (kinetic plus potential minus drag work), launch and airborne phases distinct, the no-lift control from issue 1,
a zero-lift/zero-drag analytic check, and at least one retained invalid or failing candidate. Range over the declared speed, pitch, release-height and stroke sweep is a scenario distribution, not a probability of success.

## Verdict structure I will use
Numerical dimensions can pass on independent recomputation. Replication, empirical relevance and flight survival stay `insufficient` until printed mass and balance are measured
and slingshot flights are recorded, as SPEC-010's last two checklist lines require. I will not mark anything `not_applicable` to reach acceptance. Review is per delivered artifact and exact version; author roles do not imply independence.
