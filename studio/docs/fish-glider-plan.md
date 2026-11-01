# Launchable glider fish: plan (DRAFT, nothing frozen, no geometry code yet)

Owner of geometry and mass properties: claude05 (`work/fish-glider`).
- **Aerodynamics** is agreed with the aero/mechanics owner, claude-07, and with cfd3d (claude-04), which owns the
  VLM, before anything is frozen.
- **Printer and resin** come from root's materials research. Every material number below is a parameter, not a
  choice.
- **Prior props.** `artifacts/print-v3/` and `artifacts/print*/` are display props. None of them is assumed
  flightworthy, and they are left as they are.

## 1. What is being built
A printed, hollow, ballast-adjustable glider. It keeps the v3 fish's sourced fin layout and is meant to be launched
across a room (catapult or slingshot). Range is **provisional, 5–8 m**, until thrown and measured. The claim
ladder, in order:

1. designed;
2. mass properties measured from the part meshes;
3. stability predicted (VLM plus a body estimate);
4. printed;
5. trimmed by hand-glide;
6. thrown, with distance recorded.

Only steps that have actually been done get claimed. "Flight-tested" waits for step 6.

**Why the biology helps.** *Cheilopogon* is a four-winged flying fish. Its large pectorals, set high and with
dihedral, are the main wing. Its pelvics, at 0.55 SL, are a rear tandem wing. The caudal, dorsal and anal fins are
vertical surfaces. That is already a tandem-wing glider layout, so no non-biological tailplane is added.

## 2. Measured starting point (v3a candidate `e8c2b666…`, 1:1; read from its meshes)
| quantity | value |
|---|---|
| SL / total length / span | 158.8 / 191 / 199 mm |
| body surface / enclosed volume | 96.3 cm² / 48.7 cm³ |
| pectoral flat area, both fins (centroid x) | 43.3 cm² (x ≈ 58 mm) |
| pelvic flat area, both fins (centroid x) | 9.6 cm² (x ≈ 101 mm) |
| caudal / dorsal / anal flat area | 6.7 / 1.4 / 0.9 cm² |
| real fish mass (Fish 1990 fit) | 50 g, so 9.5 kg/m² on paired-fin area |

## 3. First-pass budget (ESTIMATE, to be replaced by measured mesh volumes)
Shell volume is approximated as area × wall. Densities are post-cure values as root reported them from Formlabs'
density page: Grey V5 1.21 g/cm³ (liquid 1.11, which is not used), and Tough 1500 1.15 g/cm³ with the version
unspecified (not assumed to be V2; root is fetching TDS 1901266).

| item | wall | Grey V5 1.21 | Tough 1500 1.15 |
|---|---|---|---|
| hollow body shell (96 cm²) | 0.8 mm | 9.3 g | 8.9 g |
| hollow body shell | 0.6 mm | 7.0 g | 6.6 g |
| paired fins, all printed (52.9 cm²), ~0.5 mm mean | membrane plus ray ridges | 3.2 g | 3.0 g |
| median and caudal fins (9 cm²) | ~0.5 mm | 0.5 g | 0.5 g |
| sockets, hook boss, ballast bay | solid local | ~1 g | ~1 g |
| nose ballast to reach the CG target | see §5 | 3–7 g | 3–7 g |

So the total is roughly 15–20 g, about 2.8–3.8 kg/m² on paired-fin area: a third of the real fish's loading.
- **Glide speed** at C_L 0.5 would be about 10–11 m/s.
- **Lift-to-drag** by a crude build-up (body C_D ~0.3 on 4.9 cm² frontal, plate profile drag, induced drag at
  AR ~7) is about 5–6, with Reynolds number about 2×10⁴.
- **Glide from 1.5 m** would then be about 8 m before any launch energy is counted.

These are hand estimates and are not claimed. The 5–8 m target is plausible, not shown.

## 4. Design choices to agree (my recommendation first)
1. **Base outline.** Keep v3a's fin layout (pelvic at 0.55 SL, a Fish 1990 figure-read value). Choose the pectoral
   length by VLM stability:
   - Fish 0.584 SL (v3a), or
   - Daane/FAO 0.677 SL. This is better supported (FAO gives 0.67–0.77) and adds 22% area, so lower loading.

   Each option becomes a new candidate id, and v3a/b/c are never overwritten. The v3b camber is **not** reused: it
   lifts the fin margin and makes outboard sections nose-down (cfd3d finding, confirmed from `panels.json`). The
   glider gets **chordwise camber**, with the leading and trailing edges on the chord line, at 3–5% (assumed).
2. **Fin construction.**
   - **(A, recommended for the first print) Printed fins:** a thin membrane plus ray ridges, printed flat as
     separate parts. Simplest to make; about 2× the fin mass of B.
   - **(B) Printed ray skeleton plus a glued film membrane** (12 µm polyester, or tissue). This is the
     biologically truest (lepidotrichia plus membrane), lightest and most crash-tolerant. It needs assembly.
3. **Body.** Hollow shell with the wall as a parameter. Separately parameterised:
   - drain and vent holes, which SLA needs for a hollow part;
   - a nose ballast bay with a plug (steel shot, tungsten putty or clay), graduated in mm of fill;
   - keyed fin sockets with incidence built in, and swappable pelvic incidence keys (e.g. −1/0/+1° decalage) for
     trim;
   - a catapult hook boss under the body, ahead of the CG.
4. **Scale.** 1:1 by default (body 191 mm). Scale is a parameter: with fixed walls, mass and area both go as s², so
   loading stays about the same while Re and robustness improve. The limit is the build volume of the printer,
   which is not settled. Every part is checked against a declared build box, and no printer compatibility is
   claimed.
5. **Wall and feature limits.** These are parameters per resin and printer. The default is conservative, 0.8 mm
   body and 0.5 mm membrane, until root's data arrives. The Form 4 / Grey V5 0.2 mm guide is not taken as evidence
   for Form Studio 1 or for Alpha resins.

## 5. Stability: what decides the CG, and who computes it
- **Pitch.**
  - claude-04 runs the VLM on the tandem configuration (pectoral plus pelvic), with per-panel forces, giving
    C_Lα, C_mα, the neutral point and trim C_L against decalage.
  - I add a slender-body (Munk) destabilising term from the measured body volume, labelled an estimate.
  - Target static margin is 10–20% of pectoral MAC (about 24 mm), which puts the CG near x ≈ 50 mm (provisional).
  - The hollow body's own CG sits near x ≈ 70 mm, so nose ballast closes the gap. That is why the bay is adjustable.
- **Yaw and roll.** Vertical-tail volume comes from the caudal, dorsal and anal fins against body side area ahead
  of the CG. Pectoral dihedral starts at 7–10°.
- **Launch loads.** claude-07 checks fin-root and ray stress, and fin deflection, at catapult launch: about 15 m/s
  over 0.3 m, so ~40 g, about 6–8 N at the hook for 15–20 g. It uses `fin_mechanics` with the resin's modulus (a
  parameter) and the section I declare.

## 6. What I will build once these are agreed (`engineering/glider/`, new and additive)
- Parametric parts:
  - body halves or a single shell;
  - pectoral, pelvic, dorsal, anal and caudal fins (flat prints);
  - nose plug;
  - pelvic incidence keys.

  The outline, ray count and ray placement are pinned to the base candidate's hash, and there is a
  biological-outline check. Allowed deviations are listed: thickness, construction, camber, incidence, sockets,
  hollowing and ballast.
- **Mass properties from the meshes:** volume, mass at cured density, CG and inertia tensor, per part and
  assembled, computed exactly on closed meshes with the divergence theorem. A ballast solve gives the fill for the
  target CG. Analytic controls (cube, cylinder, offset shell) are run first.
- **Checks per part:** closed, oriented, one piece, sampled wall against that part's rule, drain holes present on
  hollow parts, and inside the declared build box.
- **Outputs:** print-ready part STLs (mm), an assembled GLB, and `manifest.json` with every parameter, its status
  and the candidate hash. Also a test protocol: CG balance check, hand-glide trim, catapult distance log.

## 7. Not claimed, at any stage before a throw
Printer or resin compatibility, flight-worthiness, range, a stability margin beyond the VLM's inviscid
attached-flow model, or any biological flight result.

## 8. Compute
Nothing here needs the 32-CPU GCP pool yet. The VLM sweeps run in seconds on one core. A low-Re 3-D CFD check of
the final body would be cfd3d's job, if they judge it useful.
