# SPEC-010 — Printable fish glider with slingshot launch

Status: user-directed requirement, October 31, 2026. Implementation and physical
validation are pending; no acceptance item below is claimed passed by this spec.

The user requests a launchable version of the current biologically inspired fish,
including a slingshot launch across a room. Retain the existing display props.
This is a new manufactured glider with fish-derived morphology. Its material,
mass and launch requirements are separate from living-organism feasibility.

## Requirements and provisional scenarios

1. **Slingshot launch is required.** Provide a defined pouch/contact or launch
   interface, its position relative to the actual center of mass, load path,
   local reinforcement, release clearance and a modeled launch-to-glide sequence.
   The interface must release completely; a retained launcher tether is outside
   this gliding model. A steady lift calculation alone cannot satisfy this item.
2. Use the current v3 fish as the explicit geometric ancestor: ray-supported
   pectoral fins, pelvic fins, fish body and tail. Record each changed dimension,
   incidence angle, thickness, joint and surface feature. Source-conditioned
   biological proportions are constraints; printer alterations remain labeled.
3. Provisional design target, pending the user's dimensions and material:
   5–8 m horizontal travel in still indoor air from a 1.2–1.5 m release height.
   Sweep 4, 6 and 8 m/s release speeds and pitch/release uncertainties. These are
   chosen design scenarios, not measured launcher performance or a range claim.
4. Model a 0.1–0.3 m effective acceleration stroke as a declared scenario.
   Report average acceleration `a = V0^2/(2 s)` and force `F = m a`; neither
   gives peak load. Bracket the unknown force-time profile and release torque.
   Actual launcher stroke, impulse, alignment and speed need measurement.
5. Use the exact manufactured assembly geometry for resin volume, dry mass,
   center of mass, inertia and aerodynamic inputs. Include ballast, adhesive and
   finishes separately. Never substitute biological mass or liquid resin density.
6. Include adjustable ballast/trim that can be measured after printing. Hollow
   bodies need accessible cleaning/drainage and no assumed removal of trapped
   resin. A split shell is an allowed assembly approach. No hidden support mass.
7. The actual printer/resin/tank/cure process remains pending user confirmation.
   Form Studio 1's sourced build envelope is 200 × 125 × 235 mm before support
   and orientation allowance. Multiple printed parts are allowed. A bounding-box
   check is not slicing, curing, assembly, structural or flight validation.

## Analysis contract

- Freeze a protocol before the design sweep: candidates, source versions,
  coordinate frame, units, coefficient/parameter provenance, gates, budgets and
  stop conditions. Preserve failed designs and uncertain regions.
- Calculate lift, drag and pitching moment about the manufactured center of
  mass. Report `Cm = 0` trim, `dCm/dalpha` and perturbation response over a declared
  operating interval. Include roll/yaw limitations explicitly. A center-of-mass
  sign check alone is insufficient to establish stability.
- Evaluate Reynolds number using actual chord and speed. Existing failed 3-D
  sphere references, unresolved fins and unconverged VLM candidates remain
  failures. They cannot supply validated whole-fish polars for this design.
- Thin-fin stiffness, inertial launch loads, root/assembly loads and static
  aerodynamic deflection must use sourced material properties with cure and
  printer context. Long-term fatigue, impact and thin-feature fabrication are
  unknown unless measured. Bulk coupon data are not fin-level verification.
- Report aerodynamic coefficient uncertainty separately from numerical
  convergence. A range distribution from assumed coefficients is a scenario
  distribution, not a calibrated probability of physical success.
- Run useful bounded CPU sweeps through the infrastructure dispatcher. Record
  all inputs, source/geometry hashes, actual resource use and collected outputs.

## Required outputs and acceptance checklist

- [ ] At least one distinct new printable assembly and an assembled GLB, with
  retained fish morphology, part identifiers and a source-candidate hash.
- [ ] Machine-readable material cards: resin/version, solid density, stiffness,
  test/cure conditions, printer/tank compatibility, source URL and read status.
- [ ] Computed volume, mass, center of mass and inertia for every part and the
  assembly; unknown contributions and measurement instructions remain visible.
- [ ] A concrete slingshot interface and load calculation, including release
  torque and load uncertainty. No unsupported assertion of launch survival.
- [ ] Numerical controls, mesh/time-step checks and an invalid candidate retained;
  independent review of trim/stability and the link between mesh and simulation.
- [ ] A trajectory animation generated from the actual integrated equations and
  selected candidate, with launch and airborne phases clearly distinguished.
- [ ] Download links, an assembly/ballast guide, mass/balance measurements and a
  physical glide-test record template on the Project surface.
- [ ] Actual printed-assembly mass and balance measurements before claiming
  agreement with the manufactured model; record discrepancy and update inputs.
- [ ] Recorded slingshot-launched flights reaching the stated range and remaining
  stable before describing the design as demonstrated to fly across the room.

Owners: claude-05 geometry/manufacturing; claude-07 dynamics/trim; claude-04
aerodynamic controls; root material sources and integration; infra_director
cloud admission; resource_scaling durable collection. Independent review is a
separate assignment and must not be inferred from those author roles.

## Source context

- [Form Studio 1 build envelope](https://formlabs.com/support/What-is-the-largest-part-I-can-print-on-a-Formlabs-printer/),
  manufacturer page read October 31.
- [Alpha Grey V1 material data](https://formlabs.com/materials/tds/alpha-grey-resin/),
  September 28, 2026 revision: default-post-cure density 1.22 g/cm³ and tensile
  modulus 2150 MPa, measured on Form Studio 1 coupons under the listed process.
- [Park and Choi, 2010](https://doi.org/10.1242/jeb.046052): flying-fish
  fin deployment, aerodynamics and stability. Abstract and indexed author-PDF
  excerpts available; a full PDF has not yet been retrieved by root. Do not use
  excerpted geometry as an empirically calibrated polar for this glider.
- [Saro-Cortes et al., 2022](https://doi.org/10.1093/icb/icac101): robotic
  flying-fish aerodynamic experiments; prior survey reports a lift/stability
  tradeoff. Full-text retrieval and quantitative applicability remain pending.
