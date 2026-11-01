# Launch-prototype glider fish (`artifacts/glider/`)

**LAUNCH PROTOTYPE, UNTESTED.** Nothing here has been printed, weighed, glided or thrown. No printer or resin
compatibility is claimed. Every number not read from a mesh is a provisional default, and is labelled as one in
each `manifest.json`.

**Provenance of the defaults.** The user asked for a printable fish with strong fins that can be launched from a
sling. Root chose the rest as provisional engineering defaults; none of them is user-confirmed:
- 1:1 scale;
- printed fins;
- Form Studio 1 as the assumed printer, with a 200 × 125 × 235 mm envelope (confirmed by root);
- Alpha Grey V1 resin at 1220 kg/m³, from root's material card.

Fin and hook sections follow claude-07's print requirements R1–R4 (`glider-dynamics-to-fish-glider-print-reqs.md`).

## Revisions (lineage; a later revision never overwrites an earlier one)
| revision | parent | body shell | dry mass (measured from the meshes) | ballasted to CG x 52 mm | V_trim at C_L 0.5 (hand) |
|---|---|---|---|---|---|
| `r1-strong` | none | 0.8 mm | 19.95 g, CG x 69.3 mm | 28.9 g | 13.2 m/s |
| `r1-light` | r1-strong | 0.5 mm | 17.14 g, CG x 68.2 mm | 24.0 g | 12.1 m/s |
| `r2-light` | r1-light | 0.5 mm | 19.13 g, CG x 64.3 mm (with the nominal seat plug) | 24.9 g | 12.3 m/s |
| `r3-daane` | r2-light | 0.5 mm | 20.33 g, CG x 63.6 mm | 26.1 g | 11.1 m/s |
| `r4-daane-printfix` | r3-daane | 0.5 mm | 20.33 g, CG x 63.6 mm (r3's geometry; right-hand print files fixed) | 26.1 g | 11.1 m/s |

**r1 is immutable.** Commit `19f4546` rebuilds it byte for byte; this was checked with `cmp` in a clean worktree.
- Later builder code reproduces r1's geometry but not its bytes. The r1-strong body volume differs by
  3e-9 mm³, from floating-point operation order.
- So the r1 files come from that commit. `main()` refuses to overwrite them.

**r2-light makes the catch adjustable,** per claude-07's R3 correction (`glider-dynamics-to-fish-glider-r3-correction.md`).
- **Slots:** two transverse slots, at x 20 and 34 mm.
- **Seat heights:** −1.5, 0, +1.5 and +3.0 mm relative to the design CG height (the dry assembled CG,
  z 3.44 mm).
  - The top height is the bare slot top. Each lower seat is a `catch_plug-x<slot>-dz<offset>.stl`, pressed into
    the slot top, with 0.1 mm clearance a side (assumed). Retain it with tape or glue.
  - A raked slot moves the seat aft as it is lowered: 0.87 mm per 1.5 mm.
- **Bulkheads:** each slot's 2 mm liner is the bulkhead. The bay and the main cavity are clipped by the forward
  slot's axis plane. A flat bulkhead left a sealed 0.54 cm³ resin pocket against the raked liner, which the
  connectivity check caught as a second shell. The nominal assembly uses the x 20 mm slot at offset 0.
- **Mass:** the second liner adds mass forward. The dry CG moves 4 mm forward and the ballast needed falls, but the
  ballasted total is about the same.

**r3-daane** is r2-light built on the committed v3c candidate (`a6455a3d…`): the Daane/FAO pectoral length and
pelvics at 0.48 SL.
- Paired flat area 67.8 cm² against 52.9 cm². Each pectoral is 3.00 g against 2.40 g.
- The mass for V_trim 8 m/s at C_L 0.5 on this area is 13.5 g, against 10.5 g.
- Ballasted to CG x 52 mm it is 26.1 g. That still fails, but trim speed drops from 12.3 to 11.1 m/s.
- Hand NP bracket 55.6–58.3 mm; pectoral MAC 30.9 mm.

**r1 to r3: every `_R` print file holds the LEFT part. Do not print them.**
- **Cause.** The exporter posed each right part with a reflection (det −1). That reflection undid the mirror that
  had made the part, so `pectoral_R` and `pelvic_R-*` came out with the left part's vertices. Reviewer claude-13
  found it on r1, and root found it on r3.
- **Earlier files.** They are kept byte for byte and listed in `artifacts/glider/KNOWN_DEFECTS.json`. Their fish-frame
  mass properties, the GLB and `flight_model.json` were never affected.
- **Fix in r4.** Every print-to-fish transform is now a proper rotation (det +1). Each `_R` file is the mirror image
  of its `_L` file, and the winding stays outward. Tests check all three.

**r4-daane-printfix** is the first fit and balance test print. Root selected it, and it is not flight-ready.
- **Body.** Its `body.stl` is mesh-identical to r3's (commit `361480f`), with bytes identical after the 80-byte
  header, so an r3 body already printed is compatible. The same holds for every `_L` fin and every plug.
- **Handoff.** The six-part nominal set is in `print-set-r4-daane-printfix.zip`, written by
  `python -m engineering.glider.build --bundle r4-daane-printfix`. It holds:
  - the six STLs;
  - `manifest.json`;
  - `ASSEMBLY.md`, with fit, balance and record instructions;
  - `KNOWN_DEFECTS.json`;
  - `SHA256SUMS`.

  `download.json`, beside the ZIP and outside it, pins the ZIP's path, size and sha256. The ZIP is deterministic:
  the same files give the same bytes.

**Open finding: thin body wall at the forward catch slot (unresolved).** Reviewer claude-13 measured two
readings of 0.115 mm at about (19.4, ±5.9, 8.8) mm on the r3 body, against the 0.45 mm rule. The r4 body is the same
mesh.
- **The builder's gate missed it.** Its sampler logged an edge-limited 0.31 mm reading at (18.38, 6.39, 8.15), and
  edge-limited readings are reported but do not gate.
- **Consequence.** r4 is a fit and balance print only, with no launch clearance.
- **Record.** The finding is in `artifacts/glider/REVIEW_FINDINGS.json`, outside the frozen revisions and the ZIP.
  It will be fixed in a new revision, never by editing r4.

**All five revisions fail claude-07's preliminary mass limit.** The limit is about 10.5 g, which gives
V_trim ≤ 8 m/s at C_L 0.5. They are kept as printable launch prototypes with that failure stated.
- **Measured split** (`r1-light`): body 10.95 g, each pectoral 2.40 g, each pelvic 0.69 g.
- **Why the ballast is large.** The hollow body's CG sits at about x 69 mm, against claude-07's CG window of
  44–60 mm, so nose ballast does the rest.
- **Levers for r2,** with the mass each saves taken from these meshes:
  - a thinner shell aft;
  - a 0.4 mm membrane (R1 says this passes, with a 1.6 mm spar);
  - fewer or lower ridges;
  - a shorter tail cavity wall;
  - moving the dense parts forward.

  Scale is not a lever (claude-07 §0).

  Within the provisional 0.45 mm wall rule, these levers do not reach 10.5 g. The shell alone is about 5.9 g at
  0.5 mm, and the printed fins are 6.2 g. Reaching it needs one of these decisions, none of them mine alone:
  - the longer Daane/FAO pectoral (v3c, +28% fin area, which raises the limit to about 13.4 g);
  - thinner walls, with evidence from this printer and resin;
  - film-membrane fins (option B);
  - accepting a faster launch.

## Parts (per revision: `stl/`, mm)
- **`body.stl`**, a hollow shell in the fish frame. It has:
  - integral dorsal, anal and caudal fins (0.5 mm membrane, 0.8 × 0.9 mm centred ridges);
  - a ballast bay at x 6–23 mm, with a 5 mm ventral port to tape shut;
  - a 1 mm bulkhead;
  - the main cavity at x 24–150 mm, with two 2.5 mm ventral drains;
  - a solid peduncle;
  - a lined transverse catch slot;
  - four keyed sockets, each with a small root fairing.
- **`pectoral_{L,R}.stl`**, laid flat with the membrane in the XY plane:
  - 0.5 mm membrane;
  - root doubler, 1.2 mm out to u = 12 mm, tapering to 0.5 mm at 16 mm;
  - leading-edge spar under ray 0, 1.6 × 2.0 mm, tapering to 1.2 mm over the outer 30%;
  - 1.0 mm ridges under the other rays, with a 1 mm taper to the membrane;
  - a rounded rim bead;
  - a 2 × 10 × 6 mm root tongue;
  - incidence +2° to the body axis.
- **`pelvic_{L,R}-dec{-1..+4}.stl`**: the trim keys, with decalage = pectoral incidence − pelvic incidence. The
  nominal assembly uses `dec+2`. The spar is 1.2 × 1.2 mm and the tongue 2 × 6 × 6 mm.
- **`web/assembled.glb`** is the nominal assembly, in metres, in the glTF frame of the fish3d GLBs.
  **`img/assembled.png`** is its preview.
- **`flight_model.json`** follows claude-07's `frontier.glider.flight-model/1` interface. It holds:
  - part masses, CGs and inertias, in SI, in the fish frame;
  - the ballast rows;
  - the lifting surfaces with their ridge polylines;
  - the catch geometry and the ground-contact points.

**Frame.** v3's own frame is used throughout: x runs from the snout towards the tail, z is dorsal, and y points
towards the side v3 calls `_L`. With the snout facing −x, **+y is the fish's anatomical right**, so v3's `_L` suffix
names the anatomical right side (claude-07 flagged this). Part ids keep v3's names.

## Checks (each part, recorded in `manifest.json`)
- **Mesh validity:**
  - closed, consistently oriented, one face-connected piece, no degenerate triangles, positive volume;
  - the STL re-read and re-checked (`mesh_sha256`).
- **Envelope:** fits 200 × 125 × 235 mm less 5 mm a side, in at least one axis-aligned orientation.
- **Wall rule:** 0.45 mm. That is the 0.5 mm design membrane less 0.05 mm for float32 sampling, and it is
  provisional. The wall is sampled with validate.py's inward-ray method (3,000 samples, seed 7), with one
  addition:
  - a reading counts as a wall only when the ray's exit face opposes its entry face (normals at least 135°
    apart);
  - a shorter reading through a neighbouring face of a blunter edge measures the corner, not a wall;
  - those edge-limited readings are kept and reported, with their locations; none is dropped;
  - the raw minimum is kept beside the gated one.
- **Fit:** the nominal assembly has zero fin–body overlap volume.
- **Outline:** the fins' ray lengths and roots match the committed v3a `rays.json`.
- **Mass properties:** exact for each mesh, by the divergence theorem (`engineering/glider/mass.py`). Its
  analytic controls are an offset box, a 64-gon prism and a hollow box, each exact to 1e-14.

Not checked: slicing, supports, cupping, peel (PreForm), fin strength or stiffness (claude-07's beam check reads
these bytes), the tongue's fit, printed mass, impact, and any flight.

## Hand numbers (not claimed)
- **NP bracket:** x 54.5–58.9 mm. It comes from Helmbold lift slopes, a downwash of 0.2–0.6 and a Munk body
  couple, and independently matches claude-07's R4 (54.5–59.0). The VLM replaces both.
- **Catch:**
  - the seat is at x 28 mm, 1.5 mm below the dry CG;
  - the slot is 3.5 mm wide, raked 30° with its mouth aft and below the seat, and lined with 2 mm walls across the
    full body width;
  - a forward band pull drives the loop up the slot's aft face into the seat. Once the model outruns the band, the
    loop slides out of the mouth.

  This is the recessed form of a rear-raked hook. claude-07's D1 should check it.

## Rebuild
```
systemd-run --user --scope -p TasksMax=64 -p MemoryMax=4G -p MemorySwapMax=0 \
  --setenv=OMP_NUM_THREADS=1 --setenv=MPLBACKEND=Agg --setenv=PYTHONPATH=. \
  nice -n 19 python -m engineering.glider.build          # one core, a few minutes
pytest --noconftest tests/test_glider.py
```
The builder refuses to overwrite a published revision that was built by other code. Add a revision instead.
