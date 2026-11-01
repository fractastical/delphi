# SPEC-011 — Fish control and collective escape

Status: user-directed implementation target, October 31, 2026. Simulations are
being built; neither physical flight nor engineered animal behavior is established.

## Two concrete comparisons

1. A fish-derived rigid body with articulated fins: passive glide versus bounded
   feedback control. Vary declared mass, center of mass, incidence and controller
   delay. Biological mass is a separate input from manufactured resin mass.
2. Eight fish with local visual-threat/neighbor sensing: collective escape versus
   a matched no-neighbor control. Preserve identical initial states and disturbance
   draws. Measure separation, collisions, response propagation, trajectory and
   actuation work. Report worse and null outcomes as well as improvements.

Begin with airborne release and explicit termination at water contact. Swimming,
taxiing, takeoff and regrouping are separate model interfaces; do not animate a
transition that the equations do not integrate. A future hybrid model needs
buoyancy, drag, propulsion, surface-crossing conditions and energy accounting.

## Physics and evidence contract

- Use an actual pinned rigid-body engine and actual saved integration states.
  MuJoCo integration with reduced aerodynamic forces is not Navier–Stokes CFD.
  If the source v3a VLM polar supplies lift, pin its geometry and result hashes,
  declare its angle-of-attack domain, and stop or flag exits. Assumed negative-angle
  symmetry, drag and controller gains remain assumptions. Avoid double-counting
  forces with an enabled engine fluid model.
- State SI units, right-handed world/body frames, mesh-to-body transform,
  quaternion ordering, forces, torques, time step and fin hinge conventions.
  Biological geometry reuse does not validate its mass, inertia or flight polar.
- Bound actuator torque, angle, speed and positive work. Lift must be orthogonal
  to relative flow in the reduced model; drag must dissipate energy. Account for
  moving surfaces and hinges consistently in body and hinge dynamics.
- Freeze comparisons, source/parameter versions, numerical controls and budgets
  before a sweep. Required controls: ballistic analytic solution, drag energy,
  lift orthogonality, actuation limits, frame transforms, time-step halving and
  deterministic replay. Report scenario sensitivity separately from model error.
- Local sensing and response delays are controller hypotheses. Do not present a
  behavioral controller as a validated neural circuit or a genetic implementation.
  Flying-fish schooling observations, zebrafish evidence and Danionella neural
  evidence retain distinct species and experimental contexts.

## Artifact and interface acceptance

- [ ] Frozen protocol, source/parameter cards and passed numerical controls.
- [ ] Both comparisons run, including failed/domain-exit trajectories.
- [ ] Trajectory JSON/NPZ with actual times, identities, position, quaternion,
  velocity, fin angles, forces/torques, energy/work and termination reason.
- [ ] Video/poster generated from those states with exact input/output hashes.
- [ ] Play/pause/scrub, individual selection, equations, sources and comparison
  metrics on the Project surface. Interpolated display frames are not new states.
- [ ] Source Claim → model/equation → Action → Evidence/Artifact → Project links;
  unmeasured cell/neural-to-controller interfaces become explicit open Problems.
- [ ] Resource caps and actual run receipts, including failed runs and export.

Owners: native mechanobio_sim physics; claude-10 trajectory viewer; claude-02
Project integration; infra_director admission; resource_scaling collection.

## Sources and applicability

- [MuJoCo fluid documentation](https://mujoco.readthedocs.io/en/stable/computation/fluid.html):
  phenomenological fluid forces; read by coordinator. Engine capability does not
  establish flying-fish aerodynamic accuracy.
- [Yu et al., 2026](https://pubmed.ncbi.nlm.nih.gov/42778611/): abstract read;
  visually evoked collective escape and neural responses in Danionella. Numerical
  controller calibration and transfer to flying fish remain unestablished.
- [NOAA expert interview](https://www.noaa.gov/office-education/celc/podcast/episode4):
  descriptive flying-fish schooling/escape context, not quantitative calibration.
