# r4-daane-printfix: fit and balance test print

**LAUNCH PROTOTYPE, UNTESTED, OVERWEIGHT.** This set is for a first fit and balance test. It is not flight-ready.
- Nothing in it has been printed, weighed, glided or thrown.
- No printer or resin compatibility is claimed. Slicing, orientation, supports and post-cure are not checked.
- Dry mass from the meshes is 20.33 g, against claude-07's preliminary 10.5 g budget (13.5 g on this fin area).

r4 is r3-daane with one export fix: the right-hand fin files. Every other file has r3's geometry.

## What changed from r3 (why the `_R` files are new)
- **Up to r3, every `_R` print file holds the LEFT part.** Do not print `pectoral_R.stl` or `pelvic_R-*.stl` from
  r1-strong, r1-light, r2-light or r3-daane. Those files are kept unchanged, and the defect is recorded in
  `KNOWN_DEFECTS.json`.
- In r4, each `_R` file is the mirror image of its `_L` file.
- The print-to-fish transform of every part is a proper rotation (determinant +1), so face winding stays outward.
- Tests: `tests/test_glider.py` checks that each `_R` vertex set equals the `_L` vertex set with z negated and differs
  from the `_L` set. It also checks det +1 and that each print STL, moved into place, reproduces the assembled part's
  CG on the correct side.

## Body compatibility with the frozen r3 body
The r4 `body.stl` is **mesh-identical** to the frozen r3 body at commit `361480f`
(`artifacts/glider/r3-daane/stl/body.stl`). An r3 body already printed is compatible with this set.
- **Bytes 81 onward are identical.** Only the 80-byte STL text header differs, because it names the revision.
- sha256 of the r3 body: `91fa0d8501c473aa424e5c2e2b85e4fabf3fdb9e1af8801085654fd9b637101a`.
- sha256 of the r4 body: `11499468c57f10a65aa5a1bcf8a9814a145be09073e0c70bcec67d92389d0204`.
- The same holds for every `_L` fin and every catch plug. Only the `_R` files differ from r3.

## The set (6 parts)
| file | part | mass from mesh |
|---|---|---|
| `stl/body.stl` | hollow body, with integral dorsal, anal and caudal fins | 12.53 g |
| `stl/pectoral_L.stl` | pectoral, goes on the fish's anatomical RIGHT (+y) | 3.00 g |
| `stl/pectoral_R.stl` | pectoral, goes on the fish's anatomical LEFT (−y) | 3.00 g |
| `stl/pelvic_L-dec+2.stl` | pelvic trim key, decalage +2°, anatomical RIGHT | 0.69 g |
| `stl/pelvic_R-dec+2.stl` | pelvic trim key, decalage +2°, anatomical LEFT | 0.69 g |
| `stl/catch_plug-x20-dz+0.0.stl` | launch-catch seat plug, forward slot | 0.43 g |

Masses are mesh volume × 1220 kg/m³ (Alpha Grey V1, root's card). The other trim keys (dec −1 to +4) and plugs are
in this revision's `stl/` folder in the repository.

**Which side is which.** The suffixes are v3's names, and v3's `_L` is the fish's anatomical right. Hold the fish
dorsal side up with the snout pointing away from you: the `_L` parts go on your right and the `_R` parts on your
left.

## Assembly (fit test)
1. **Before assembly.** Wash out uncured resin through the two 2.5 mm ventral drains (x 60 and 140 mm) and the
   5 mm ventral ballast port (x 11 mm). Drain size is assumed, not validated.
2. **Pectorals.** Push each root tongue (2 × 10 × 6 mm) into its socket. The spar and ridges go on the underside.
   - The socket is designed with 0.10 mm clearance a side. That is assumed, and printer tolerance is unknown, so
     the tongue may need light sanding.
   - A rectangular tongue can enter either way up. Check the spar is underneath before gluing.
   - Glue is optional for a fit test. Record the adhesive if you use one.
3. **Pelvics.** Fit the `dec+2` keys (tongue 2 × 6 × 6 mm) the same way. Play in this socket changes the decalage,
   so note any looseness.
4. **Catch plug.** Press `catch_plug-x20-dz+0.0` into the top of the forward slot (x 20 mm).
   - The STL is already in its installed orientation: its print pose is the fish frame. Keep its +z dorsal, towards the
     top of the fish. Its lower face is the seat the band bears on.
   - Clearance is 0.1 mm a side (assumed). Retain it with tape or a drop of glue.

## Balance test
1. Start with **no ballast**. The mesh prediction for the dry assembly (all six parts) is CG x 63.6 mm from the
   snout tip, on the centreline, z 4.1 mm. Weigh it and record the mass.
2. Balance the fish across a thin edge and measure the CG position from the snout tip.
3. claude-07's CG window is x 44–60 mm, so the dry fish is tail-heavy. Ballast goes into the bay through the
   ventral port, which you then close with tape or putty.

   Ballast for each target CG, assuming steel shot set in glue at 4.7 g/cm³ packed from the front of the bay:

   | target CG x | ballast | total |
   |---|---|---|
   | 60 mm | 1.4 g | 21.7 g |
   | 56 mm | 3.3 g | 23.6 g |
   | 52 mm | 5.7 g | 26.1 g |

   If the measured dry CG differs from 63.6 mm, these figures move with it. Report the measured value.
4. **Record:**
   - the printer, resin, layer height, orientation and supports;
   - each part's printed mass;
   - the tongue fit, and any sanding;
   - the dry CG;
   - the ballast and the final CG;
   - the slot, plug and pelvic key used.

Do not throw it on the strength of this test. A hand-glide trim is a later step. Launch loads, fin strength and
impact survival are not verified.

## Files in the ZIP
`manifest.json` has every parameter, check and hash for this revision. `SHA256SUMS` lists each file in the ZIP.
