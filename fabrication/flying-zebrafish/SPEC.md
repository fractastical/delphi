# Flying zebrafish: build spec (shared contract)

Goal: one watertight, Formlabs-printable model of a **flying fish built on a zebrafish (*Danio rerio*)
body plan**, with **flying-fish (Exocoetidae) wings** stitched on. Gliding pose, wings spread.

**HARD DEADLINE: wall clock 20:28 (Oct 31, 2026) the printable file must exist. Parts due 20:00,
assembly 20:15, QA/print pack 20:25.** Run `date` often. A rough part on time beats a perfect part late.
If you are short on time, ship the simple version, write what you skipped in your notes, and stop.

## Toolchain
- Python venv: `fabrication/flying-zebrafish/.venv/bin/python` (trimesh, numpy, scipy, manifold3d, shapely,
  matplotlib, mapbox-earcut, networkx). No Blender/OpenSCAD. Do not install anything big.
- PreForm 3.64 is installed at `/Applications/PreForm.app` (GUI only, no usable CLI). Deliver STL/3MF for import.
- All work under `fabrication/flying-zebrafish/`. Each agent writes ONLY its own files (listed per role).

## Coordinate frame and units (everything agrees on this)
- Millimetres. Right-handed. **+X = toward the nose. Z = up (dorsal). Y = fish's left.**
- The nose tip is the origin of x and the tail is at NEGATIVE x: nose tip `x = 0`, caudal peduncle end
  `x = -80`, tail fin tip `x = -102`. Every "x = -0.38*SL" in this spec means 0.38 SL behind the nose.
- Standard length SL = 80 mm (nose tip to end of caudal peduncle). Body centreline at `z = 0, y = 0`.
- Mirror symmetric about the plane y = 0. Parts that come in pairs are built left (y > 0) and mirrored.
- Whole assembly bounding box must be <= 120 (X) x 120 (Y) x 60 (Z) mm (fits Form 3/3+/4 builds).

## Anatomy targets (zebrafish base, flying-fish modifications)
Zebrafish proportions (as fractions of SL): max body depth 0.24 at x = -0.38*SL; max body width 0.13*SL
(a little compressed laterally, ellipse cross-sections); head length 0.25*SL; eye diameter 0.07*SL at about
x = -0.07*SL, set laterally; caudal peduncle depth 0.10*SL; mouth upturned and terminal; dorsal fin base
from x = -0.50*SL to -0.64*SL; anal fin base from x = -0.57*SL to -0.76*SL; pelvic fin insertion at x = -0.42*SL.
Zebrafish surface detail: five horizontal stripes along the flank (embossed 0.15 mm, optional but nice).

Flying-fish modifications (Exocoetidae, e.g. *Cheilopogon*, four-winged type):
- Flattened belly (ventral cross-section flatter than dorsal) and straighter back; slightly deeper at the shoulder.
- **Pectoral wings**: length 0.70*SL = 56 mm each, insertion HIGH on the flank just behind the operculum at
  x = -0.25*SL, z = +0.04*SL, root chord ~16 mm tapering to tip chord ~8 mm, swept back ~25-35 deg,
  with a rigid leading edge, a slight dorsal camber (airfoil-ish, 2-4 mm camber) and ray texture
  (fine radial grooves/ridges, <= 0.2 mm). Spread laterally about 80 deg from the body axis, a little
  raised (dihedral ~5-10 deg) in gliding pose. Minimum thickness: **1.2 mm at the tip, 2.0 mm at the root**.
- **Pelvic wings** (second, smaller pair): length 0.40*SL = 32 mm, insertion at x = -0.50*SL, z = -0.10*SL,
  spread laterally ~60 deg, min thickness 1.0 mm.
- **Tail**: hypocercal, lower lobe about 1.3x the upper lobe (the flying-fish "taxi" tail). Total tail fin
  length ~22 mm beyond the peduncle, min thickness 1.0 mm, ray texture optional. Fork depth ~60% of lobe length.
- Dorsal and anal fins: zebrafish-like, small, set back, 0.8-1.0 mm thick, root embedded 1 mm into body.

## Corrections from the research agent (refs/REFERENCES.md, 19:37)
- Dorsal fin base is shorter in real zebrafish: x = -0.53..-0.62 SL (-42..-50 mm), ~0.09 SL long. The assembler
  tolerates the longer base already built; trim only if time allows.
- Span budget: 56 mm wing at 80 deg spread reaches y of about 60, i.e. 120 mm across, exactly the Y limit.
  The assembler will check the bbox and, if over 120, rotate the wings back a few degrees rather than rebuild.

## Part interface (so the assembler can union everything)
Every part module lives in `parts/<name>/` and exposes `build() -> trimesh.Trimesh` (a single watertight
mesh in the shared frame above, units mm) and, when run as a script, writes `parts/<name>/<name>.stl`
and a PNG preview `parts/<name>/<name>_preview.png` (top, side, front, matplotlib). Appendages must
**embed 1.5-3 mm into the body volume at their root** so a boolean union fuses them (no gaps, no tangent faces).
Use `manifold3d` via `trimesh.boolean` (engine="manifold") for unions. Prefer lofted cross-sections,
`trimesh.creation.extrude_polygon`, and displaced grids; keep faces < 400k per part.

Part names and owners:
1. `body`     - zebrafish head+trunk+peduncle, eyes, mouth, gill cover line, stripes, root sockets. (Body agent)
2. `tail`     - caudal fin + dorsal fin + anal fin. (Fins agent)
3. `pectoral` - left pectoral wing (build left, y > 0) plus helper to mirror. (Wing agent)
4. `pelvic`   - left pelvic wing. (Wing agent)
5. assembler  - `assemble.py`: union all, mirror pairs, check, export. (Assembler agent)
6. printpack  - orientation, supports, stand, material, PreForm instructions. (Print agent)
7. refs       - `refs/REFERENCES.md` with sourced numbers (Research agent). Feeds back corrections early.

## Printability rules (Formlabs SLA, Form 3/3+/4; Clear/Grey/Standard resins at 50-100 um layers)
- Watertight, manifold, outward normals, single shell after union (ignore tiny floating debris, delete it).
- Min wall/feature 0.6 mm everywhere; fins/wings >= 1.0 mm tip thickness as above (the thin edges are the risk).
- Embossed/engraved detail >= 0.15 mm deep and >= 0.3 mm wide, or leave it out.
- No internal voids unless drained (we are NOT hollowing; solid is fine at this size).
- Output units mm, STL binary and 3MF.
- Overhangs are handled by PreForm auto-support; Print agent chooses orientation and adds a **display stand**
  (a slim rod from the belly to a round 30 mm base, or a clear rod to the underside of the body) as a separate
  or fused option. The fish is "in flight" so a stand is how it will actually be displayed.

## Shared outputs
- `out/flying-zebrafish.stl`, `out/flying-zebrafish.3mf` (fish only) and `out/flying-zebrafish_with-stand.stl`.
- `out/QA.md` (watertight, volume, bbox, min thickness check, renders) and `out/PRINT.md` (PreForm steps).
- Notes: each agent appends 5-10 lines to `notes/<role>.md` (what it did, assumptions, what is unfinished).
