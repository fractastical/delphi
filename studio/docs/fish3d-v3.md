# fish3d v3: ray-fan fins and sourced meristics (ENGINEERED FORM)

The v1 fish (`fish3d-N1-cypselurus-baseline`, `docs/fish3d.md`) had flat 0.5 mm fin plates and a needle-like
lower caudal lobe. v3 rebuilds every fin as a fan of tapered rays joined by a thin membrane. Its counts, positions
and outline rules are read from a species sheet. Three candidates come out of it, and v1 is left as it was.

```
python -m engineering.fishv3.build            # ~1 min, all three candidates + v3-index.json; --no-render skips PNGs
pytest --noconftest tests/test_fishv3.py      # 13 tests
```

## Sources (read levels)
| key | what | read level | used for |
|---|---|---|---|
| `fao_wca_exocoetidae` | Parin 2002 (after Gibbs 1978), FAO WCA guide vol. 2, Exocoetidae, sha256 `f1a35c86…` | full text (pdftotext) | meristics, outline rules, pigmentation (below) |
| `daane2021` | Daane et al. 2021 Curr Biol, author PDF `e0d4e61d…` | full text | caudal "stiffened and elongated ventral lobe"; S1A pectoral and pelvic length/SL for *C. furcatus* |
| `fish1990` | Fish 1990 J Zool | as in `engineering/geometry/sources.py` | SL, wing area, span, pectoral share, hypocaudal area and share (N1) |
| `park_choi_2010` | Park & Choi 2010 J Exp Biol | **could not access** (Cloudflare on page, PDF and r.jina.ai) | nothing; camber and dihedral stay assumed |

## What is sourced, and what is not
**Sourced, from the FAO sheet for *Cheilopogon furcatus*** (the species v1 already used for the pelvic ratio):
- 15 pectoral rays (range 14–17), with only the first unbranched;
- 13 dorsal rays (12–14) and 10 anal rays (8–11);
- the anal fin originating under the 6th dorsal ray (5th–7th);
- predorsal scales 28.5 (usually 27–30). This sets the scale spacing at 2.38 mm, which gives 48 rows and 1,302
  scales;
- eye diameter = head length / 2.95 (range 2.8–3.1).

**Sourced, from the family page:**
- a deeply forked caudal with the lower lobe longer;
- pectorals high on the sides;
- dorsal and anal fins set far back, with short opposed bases;
- large cycloid scales and a low lateral line;
- a snout shorter than the eye.

**Pelvic placement rule (FAO):** the insertion must be nearer the opercle than the caudal base. The builder refuses
any candidate that breaks it.

**Derived, from Fish 1990:**
- **Pectoral fin.** The longest ray is the fin length. The fan spread is solved so that the flat fin, in its
  reference pose (lead angle 8°), has the Fish area exactly.
- **Caudal fin.** The two lobes are solved to Fish's hypocaudal area and its share (0.6263, reproduced exactly).
  The lower lobe's longest ray is 45.4 mm and the upper's 36.2 mm.

**Assumed, and exposed as parameters in `candidate.json` `anatomy`:**
- the pelvic ray count (6) and the principal caudal rays (7 + 8);
- the ray-length profiles, branch point, membrane thickness (0.10 mm) and ray radii (0.30 → 0.07 mm);
- the margin scallop, the median fins' rake and height, and the fin base lengths;
- the eye angle, the gill-cover extent, and the scale lattice, overlap and tilt.

**Not modelled:**
- separate hemitrichia, joint segments and ray bending stiffness;
- gill arches;
- the order in which scales form (not sourced for Exocoetidae).

**Disagreements, kept and not reconciled** (`candidate.json` `disagreements`):
- **Pectoral length / SL.** Fish 1990 span fit 0.584; Daane S1A *C. furcatus* 0.677 (n = 12); FAO 0.67–0.77.
- **Pelvic length / SL.** Daane 0.43; FAO 0.30–0.37.
- **Head length / SL.** The *C. furcatus* sheet's head-length entry, 2.8–3.1 in SL, repeats that sheet's eye ratio.
  The *C. cyanopterus* sheet repeats its depth ratio the same way. So it is not used, and head length = SL / 4.3
  comes from the other Atlantic *Cheilopogon*.
- **Body depth.** The built body is 0.145 SL deep. FAO gives 0.164–0.208 for *C. furcatus*. Depth here comes from
  the Fish volume fit and is reported, not forced.

## The three candidates
All three share body, anatomy, sources and caudal fin, and differ only in their `knobs`. The tests check that.

| id | candidate sha256 | what differs |
|---|---|---|
| `fish3d-v3a-fan` | `e8c2b666874a…` | reference: Fish lengths and areas; pectoral lead angle 8°, dihedral 7°, flat; pelvic at 0.55 SL (Fish figure) |
| `fish3d-v3b-glide-pose` | `57874f86f499…` | **pose only, identical rays:** pectoral lead angle 16°, dihedral 12°, camber 0.06; pelvic 30°, 8°, camber 0.04 |
| `fish3d-v3c-daane-length` | `a6455a3ddfcb…` | **outline/placement:** pectoral length from Daane S1A (107.5 mm, area scaled by length², 2,909 mm²); pelvic insertion 0.48 SL |

**Flat-area misses, reported rather than re-solved:**
- **v3b:** the posed pectoral's flat area is 2,132 mm², not the 2,165 mm² target.
- **v3a and v3c:** the pelvics, at a 22° lead angle, are 481 mm² against a target of 495 mm².

The planform areas (top view, body plus paired fins) are 0.00853, 0.00836 and 0.01001 m².

## Files per candidate (`artifacts/fish3d/<id>/`)
- **`candidate.json`.** Its sha256 is carried by `build.json`, `components.json`, `rays.json`, `panels.json`,
  `sections.json`, `scales.json`, `surface_map.json` and every `appearance-*.json`.
- **`components/*.stl`.** One per component, in metres, in the fish frame: x snout→tail, y left, z dorsal. Scales
  are in the GLB only, as in v1.
- **`fish.glb`.** The exact geometry, with one node per component id (glTF +Y up).
- **`rays.json`.** Every ray as polylines in metres, with its length and tributary membrane width, for
  fin-ray load models.
- **`panels.json`.** Per fin, the membrane outline (3-D) and a ray-aligned quad lattice (6 chordwise), for panel
  or VLM codes.
- **`sections.json`.** Midsagittal and planform cuts of the actual meshes. These are a 2-D proxy, not 3-D flow.

## Appearance (pigmentation) is a separate layer
The appearance options never enter `candidate.json`, so the geometry hash is the same under every option. Each
`appearance-<option>.json` names the exact `fish.glb` it colours.
- **`adult-fao`** (default; GLB on all three). The pattern is sourced from FAO *C. furcatus* and the family page:
  - body dark above and pale below (iridescent blue in life);
  - dorsal and caudal greyish, anal transparent;
  - pectorals near-black, with an unpigmented oblique crossband reaching the upper margin and a very broad
    unpigmented rear margin;
  - pelvics pale (assumed).

  The band's position on the fin and all RGB values are ours.
- **`juvenile-bars-design`** (GLB on v3a only). This adds 6 transverse body bars. FAO describes them only in
  **juveniles of 50–100 mm SL**. This candidate is 159 mm SL, so they are a **design choice**, labelled so in the
  file and on the preview.

## Previews
`preview-<option>.png` gives top, side and three-quarter views, flat-shaded with matplotlib from the exported
triangles in about 10 s. No path tracing was done.

## Not claimed
- Aerodynamic or hydrodynamic validity, or measured fin stiffness.
- A validated pigment-pattern map.
- An organism.
- That any variant is better. They are inputs to the placement and flow studies, not results.
