# 3-D flying fish at biological scale (ENGINEERED FORM)

One candidate with one hash, shared by every file. Code is in `engineering/fish3d/`; outputs are in
`artifacts/fish3d/fish3d-N1-cypselurus-baseline/`.

```
python -m engineering.fish3d.build                       # candidate, components, scales, sections (~1 min)
blender -b --factory-startup --python engineering/fish3d/blender_render.py -- \
    --glb artifacts/fish3d/<id>/fish.glb --out DIR --mode still|turntable
python -m engineering.fish3d.present --renders DIR       # captions, MP4/GIF/poster, render.json
pytest --noconftest tests/test_fish3d.py
```

Blender is the portable 4.2.3 LTS build, which matches its published sha256. It was unpacked to
`/data/tools/blender-4.2.3-linux-x64` and runs headless (Cycles, CPU, 4 threads) under
`systemd-run MemoryMax=6G MemorySwapMax=0`. The 1920×1080, 256-sample still took 2 min 42 s on this host.

## The candidate
`candidate.json` holds every shape parameter, each with a status. **`candidate_sha256` is the sha256 of those
bytes.** The following carry it, and `tests/test_fish3d.py` checks that they agree:
- `build.json`, `components.json`, `scales.json`, `surface_map.json` and `sections.json`;
- the render manifest;
- the report written inside Blender. Blender refuses to render a GLB whose sha256 differs from `build.json`.

It is the NCA corrected comparison-set **baseline**: Cypselurus fits at 0.05 kg (print form N1). Its sizes come
from three places:

| quantity | source | status |
|---|---|---|
| standard length 158.8 mm | Fish 1990 Table I length fit | derived |
| wing area, span, pectoral share | Fish 1990 fits (NCA baseline fS 1.0, fAR 1.0) | derived |
| pelvic length / SL | Daane 2021 S1A (Cheilopogon furcatus substitution) | derived |
| hypocaudal area and share | Fish 1990 Table I/IV | derived |
| fin positions along the body | read off Fish 1990 figures | figure_read |
| body width | body volume = mass / density | derived |
| body shape, fin sweep, dihedral, caudal planform | ours | aesthetic |
| fin thickness 0.5 mm (flat plates), eyes, gill covers | ours | assumed / aesthetic |
| scales: 50 along the body, overlap 0.68, tilt 7°, 0.12 mm thick | ours | **assumed** |

The Daane 2021 author PDF (sha256 `e0d4e61d…`, read in full for the main text) confirms two things: the pectoral
allometry is the same across two- and four-wing flying fishes, and the caudal fin is hypocercal with an elongated
ventral lobe. The numbers themselves come from Data S1A, read by `engineering/geometry/daane_s1.py`.

## Components (each one closed, editable and separate)
The component IDs are `body`, `operculum_L/R`, `eye_L/R`, `pectoral_L/R`, `pelvic_L/R`, `dorsal`, `anal`,
`caudal` and `scales`.
- **Formats.** STL is in metres, in the fish frame: x runs snout → tail, y is the fish's left, z is dorsal.
  `fish.glb` follows the glTF +Y-up convention: (x, z, −y).
- **Parameters.** Each component's parameters are listed in `components.json` with their status. To edit one,
  change it in `candidate.json` (`fidelity`, `shape_params`) and rebuild; the hash then changes.
- **Overlap.** Fin roots are inset into the body, so the components overlap. Union them before any volume or
  flow use.

## Scales
`scales.json` gives each scale's position (s, φ), xyz, normal, radius and tilt. The pattern is **an assumed
staggered lattice**: it is not a simulated growth pattern and not a measured scale map. Its `growth_link` points
to the S1 Erk-wave receipt (`docs/scales.md`), whose regenerating zebrafish scale could supply a growth time
course. The final radius here is set by the lattice, not by S1.

## Sections for the 2-D flow worker
`sections.json` holds polygons cut from the actual meshes with manifold3d `slice`/`project`. Nothing is redrawn.
- **`pectoral_mid`:** a 29.1 mm chord flat plate, 0.5 mm thick.
- **`body_sagittal`:** 230.7 mm long, including the caudal fin.
- **`planform`:** 0.0085 m², including the body.

**Flow on any of them is a 2-D proxy, not 3-D aerodynamics of the fish.** The contract is in
`messages/fish3d-to-nca.md`.

## The `body_profile` defect (found while building this)
`mesh.body_profile` used to normalise by the maximum of its input, so a single-point call returned roughly the
full width wherever it was evaluated. The error at the pectoral root is +3%, at the pelvic root +11%, and near
the tail up to +98%.
- **The fix.** `body_profile` is now pointwise. The old function is kept as `body_profile_v1` only so that the
  published print sets (morphology-v1, nca-comparison-v1) rebuild byte for byte. `test_geometry.py` passes, and
  every print STL, GLB, solver record and video is unchanged.
- **This candidate uses the corrected profile.** The corrected print sets are the additive v2 edition in
  `artifacts/print-v2/` (`docs/printing.md`). The v1 files are unchanged.

## Not claimed
- Aerodynamic validity of any kind, from the render or from a 2-D section.
- That this is an organism or an ancestor.
- A grown or measured scale pattern.
- Biological fin thickness, camber or ray structure.
- Anything about printing.
- That the render is a measurement. It is a picture of the mesh.
