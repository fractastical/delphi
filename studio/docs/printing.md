# Printable flying-fish form studies

Six solid props in two versioned sets, each built from a design JSON by `engineering/geometry`, each with its own
display stand. Every prop is an **engineered illustrative form**. It is not an ancestor, a viable organism, a
demonstrated evolutionary path, or a flight-tested design. The fins are thickened so they can be printed.
**Printer and resin are unknown.** Nothing here has been sliced, loaded into PreForm or printed.

## Install and run

The geometry stack is the `geometry` extra in `pyproject.toml`. Its pins are the versions every committed file
in `artifacts/print/` was built with:

| package | version | used for |
|---|---|---|
| manifold3d | 3.5.4 | every boolean, extrusion and offset; ray casts for wall sampling |
| numpy | 2.4.4 | arrays (same pin as the `simulation` extra) |
| trimesh | 5.2.0 | GLB export only |
| matplotlib | 3.11.2 | PNG renders and the species graph |
| z3-solver | 5.3.3.0 | dx-guilds' solver (same pin as the `engineering` extra) |
| openpyxl | 3.1.5 | `engineering.geometry.daane_s1` only (summarising the S1A spreadsheet) |

From the repository root, on Python 3.13 (the version used here):

```
uv venv --python 3.13 .venv && uv pip install -e '.[geometry,test]'     # or: pip install -e '.[geometry,test]'
python -m engineering.geometry.build --solver-repo .     # writes artifacts/print/** ; exits 1 if any check fails
pytest --noconftest tests/test_geometry.py               # 41 tests; skips if manifold3d is absent
```

Run both under the repo's caps (`systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0
-p RuntimeMaxSec=600`).

- **What was measured.** A build took 51.9 s here. Two consecutive builds wrote byte-identical files: all 52
  in the manifest.
- **Install check, 2026-10-31.** I ran this install recipe on the integration branch's `pyproject.toml` with
  this extra added, in a fresh venv:
  - `uv` resolved exactly the versions above;
  - a build from that venv reproduced all 51 build outputs byte for byte;
  - the tests passed: 39 passed, with 2 git-dependent skips in an exported tree that has no git history.
- **Run from a checkout, not an installed wheel.** The build reads `artifacts/print/sources/` and two pinned
  git commits:
  - dx-guilds' solver blob, from `--solver-repo`;
  - dx-nca's comparison CSV, from `--nca-repo`, which defaults to the solver repo.

  Both must be present in the clone.
- **A pre-existing packaging gap on `origin/main`.** Its `pyproject.toml` has no `[tool.setuptools.packages.find]`,
  so `pip install .` fails package discovery there. The integration branch has that table, and the install
  above works on it.

## The two sets

Sets are versioned, and a new dimension set never overwrites an earlier one. It gets new form ids, its own display
scale and its own candidate files. `test_morphology_set_files_are_preserved` pins the v1 meshes, solver runs and
candidates byte for byte to merged commit `3c97a38`.

### `morphology-v1`: three body plans at 0.1 kg (scale 7:20, 1 m = 350 mm)

| form | role | solver (guilds 948c2e1) | prop L × span × H (mm) | volume (mm³) |
|---|---|---|---|---|
| A, precursor-inspired short fin | Form B's body with the fin lengths of non-gliding halfbeaks | **unsat**: `wl_hi` (1891 N/m² against 208.9) | 110.9 × 25.3 × 20.9 | 4714 |
| B, two-wing glider | *Exocoetus*-type proportions | feasible, verified independently | 94.9 × 111.3 × 20.9 | 6046 |
| C, four-wing glider | *Cypselurus*-type proportions | feasible, verified independently | 91.3 × 94.4 × 20.0 | 6108 |

### `nca-comparison-v1`: wing-geometry comparison at 0.05 kg (scale 9:20, 1 m = 450 mm)

dx-nca's corrected request is in `messages/nca-to-print.md` and `nca-to-claude05.md` (2026-10-31T19:21Z), from
`work/nca-glide` @ `87e72f9`. N1–N3 hold one *Cypselurus* body (Form C's shape parameters, at 0.05 kg) and vary
only wing area S and whole-wing aspect ratio b²/S. The variation is applied to the Fish 1990 Table I fits.

| form | S (m²) | b (m) | b²/S | m·g/S (N/m²) | prop L × span × H (mm) | volume (mm³) |
|---|---|---|---|---|---|---|
| N1 baseline | 0.005699 | 0.2117 | 7.86 | 86.0 | 92.5 × 93.6 × 20.6 | 6473 |
| N2 area ×1.3 | 0.007409 | 0.2414 | 7.86 | 66.2 | 92.5 × 106.8 × 20.6 | 7005 |
| N3 area ×1.3, AR ×1.2 | 0.007409 | 0.2644 | 9.44 | 66.2 | 92.5 × 117.0 × 20.8 | 7015 |

- **Match with NCA.** These S and b values are computed here from the Fish fit and NCA's factors.
  `test_comparison_set_is_ncas_geometry` checks them against NCA's table, written out independently. They also
  match NCA's committed CSV to within the 6-significant-figure rounding of the solver point.
- **Solver.** All three are feasible in guilds' model, and each has a `frontier.glide.candidate/1` file.
- **Simulation rows.** Each design JSON carries the six matching rows of NCA's controlled run under
  `simulation_comparison`: 3 release speeds × 2 assumed polars. The rows come from the CSV, read with
  `git show` at `87e72f9`, and its sha256 `6c434c4a…343d` is checked.
- **These rows are simulated.** They come from a point-mass model with assumed polars, calibrate nothing, and
  include no pitch or stability. NCA reports **0 robust winners**, and range ordering flips with release speed.
  The one robust effect is that equilibrium sink falls with S and AR: 1.24 > 1.09 > 0.95 m/s under P1. **The
  set is a comparison for a geometry-effect test, not an optimum.**
- **Not used.** NCA's first 720-design sweep is diagnostic only, so nothing is meshed from it. Their solver
  witness (S = 0.25 m², 13.9× the species fit) is not a mesh candidate.

### Common to both sets

The tables are copied from `artifacts/print/manifest.json`. That file and the per-form `design/*.json` are the
authority, and they also carry the mesh and file hashes.

- **"Feasible"** means that one exact point (m, S, b, V) satisfies the constraints declared in guilds' model:
  the mass and wing-loading envelopes from Fish 1990, and a level-lift proxy at ρ = 1.225, CL = 1 and V = 16 m/s.
  It does not mean the organism is feasible. The props make no aerodynamic claim.
- **Form A** is kept as a rejected candidate. With every source envelope relaxed it is still unsat, on
  `level_lift_proxy`, and that relaxed result was also verified.
- **Opt-in constraints.** The model has two opt-in constraints, and neither is taken. The first applies Fish's
  aspect-ratio range to the whole wing. Fish's 3.0–16.9 is for individual pectoral fins, and how it maps onto
  b²/S is unresolved. The second treats the 16–20 m/s taxi speed as a flight-speed envelope, which it is not.
- **Glide receipts.** A–C have no glide simulation. The build attaches a `frontier.glide.receipt/1` from
  `artifacts/print/glide/<id>.receipt.json` only if it names the candidate's sha256.

## Downloads for the site

`artifacts/print/downloads.json` (`frontier.print.downloads/1`) is the file list a site may offer. All paths
are relative to `artifacts/print/`. For each form it gives:

- the set and display scale;
- the solver status, and the glide or simulation status;
- the prop size;
- every file (prop STL, stand STL, GLB, two PNGs, design JSON), each with its kind, path, bytes, sha256 and,
  for meshes, units (mm);
- the prop and stand check results: closed 2-manifold, oriented, one component, no degenerate triangles,
  positive volume, genus, fits the box, min wall required and sampled, and self-intersection "not checked".

The same limitations travel with the list, starting with "Printer and resin are unknown".
`test_download_manifest_matches_the_files` re-hashes every listed file.

## Where the numbers come from

Every parameter in a design JSON has a `kind`:

| kind | meaning |
|---|---|
| `functional` | enters the solver point or a sourced proportion |
| `figure_read` | read off a published figure by eye |
| `design_assumption` | our choice, with a physical meaning |
| `aesthetic` | a shape choice with no biological authority |
| `derived` | computed from the kinds above |
| `print` | a prop-only choice |

The test `test_every_parameter_is_kind_labelled` enforces this.

| quantity | source | read level |
|---|---|---|
| comparison mass 0.1 kg (A–C) | Fish 1990 p.399 ("a 0.1 kg bird … Cypselurus and Exocoetus of equivalent mass") | full-text |
| mass 0.05 kg and the S ×1.3, AR ×1.2 factors (N1–N3) | dx-nca's controlled comparison protocol, `work/nca-glide` @ `87e72f9` | its committed CSV is read by the build (sha256 checked); the protocol file was not read by me |
| standard length, wing span, wing area, hypocaudal area | Fish 1990 Table I r.m.a. fits at the form's mass (0.1 or 0.05 kg) | full-text (pdftotext; decimal points restored, cross-checked against Table II: *Cypselurus* 2.8 %, *Exocoetus* 10.4 % apart) |
| pectoral share of wing area (91.83 %, 75.99 %), hypocaudal share | Fish 1990 Table IV | full-text |
| fin positions along the body | Fish 1990 Fig. 4 and Fig. 1 | figure read, ± 0.05 SL |
| pectoral / SL and pelvic / SL (A: halfbeak medians 0.140 and 0.076; B: *Exocoetus volitans* pelvic 0.121; C: *Cheilopogon furcatus* pelvic 0.43) | Daane et al. 2021 Data S1A, 109 museum specimens; ratios recomputed from raw lengths | supplement downloaded and parsed (`daane_s1`); article full-text via r.jina.ai of PMC |
| body density 1025 kg/m³ | ours; Fish 1990 p.399 says only "close to that of water" | design assumption |
| body profile, fin taper, sweep, dihedral, lobe angle, jaw length | ours | aesthetic |

Notes on these sources:

- **Fish 1990** (J. Zool. 221:391–403). Its sha256 `1efed334…f8ea` is the same file guilds' solver cites.
- **Daane et al. 2021 Data S1A** (Curr. Biol. 31:5052, doi:10.1016/j.cub.2021.08.054).
  - The sheet is `mmc2.xlsx` from the Elsevier CDN, sha256 `1ac98650…2279`. It is not redistributed.
    `artifacts/print/sources/daane2021-S1A-summary.json` is the derived summary.
  - The sheet's own ratio column has a corrupt cell: specimen 1 shows pelvic/SL 2.4e-16 where 6.9/23 = 0.30.
  - *Cypselurus* is not in S1A, so Form C's pelvic ratio comes from *Cheilopogon furcatus*. That is a
    cross-genus substitution, and it is stated in the design JSON.
  - The zebrafish `lat4a` × `kcnh2a` experiments in the same paper inform **no** geometry. They are a
    mechanism hypothesis for larger paired fins, shown in zebrafish only.
- **Pectoral length / SL** is 0.709 for B and 0.593 for C. Davenport 1992 (abstract only, relayed by
  fable-lead) reports swimming impaired beyond about 78–79 %. Both forms are inside that reported envelope,
  which is not a demonstrated ceiling.

### Aspect ratio: three conventions, none settled

Fish 1990 Table III gives "aspect ratio" for the pectoral fin. Which span and area enter it is not settled
here. Each design JSON records three conventions under `aspect_ratio_conventions`:

| form | single fin L²/A | b² / (2 pectoral areas) | whole wing b²/S | Table III fit at 0.1 kg |
|---|---|---|---|---|
| B (*Exocoetus*) | 5.66 | 13.57 | 12.47 | 14.94 |
| C (*Cypselurus*) | 4.30 | 11.15 | 8.47 | 8.74 |

No single convention matches both genera. The solver uses none of them, because the opt-in is off. The
fins' area/length² is fixed by the Table I span and area fits once pectoral share is set, so the fin shape is
not a free aesthetic choice for B and C.

## Biology, prop and resin stay separate

- **Biological values** are in SI under `biological_design_SI`. A–C are 0.1 kg and N1–N3 are 0.05 kg.
- **Prop values** are in mm under `prop_mm`. Each set has one display scale, so sizes compare within a set:
  - 7:20 for `morphology-v1`;
  - 9:20 for `nca-comparison-v1`.

  The two sets have different masses, so do not compare sizes across them.
- **How the scale is chosen.** For each candidate round ratio, largest first, coarse trial builds are made
  **at that scale**. The first ratio that keeps every length and span ≤ 118 mm with every form ≥ 90 mm long
  is used.
  - **Measured at the candidate scale.** The 1 mm tip rounding does not scale, and a trial at 1/3 had
    predicted 88.5 mm for N1 where the build gives 92.5 mm.
  - **If no ratio met both limits,** the shortfall would be written into the manifest's `length_aim` and
    reported. Both sets meet the aim.
- **Fins** are 1.6 mm resin plates. That is 4.6 mm of "biological" fin at 7:20 and 3.6 mm at 9:20, i.e.
  **not** biological thickness. Planforms are opened by a 1 mm radius, so no in-plane sliver is under 2 mm.
- **Fin areas are solved after the opening and thickening**, so the built exposed area matches the
  biological target. The pectoral and pelvic print-area exaggeration is 1.000 for every form.
- **Built span against the target.** The flat built span is within 2 % of the target for B and C. Form
  A's tiny fins lose span to tip rounding: 0.0844 m flat and 0.0724 m bounding box, against a 0.0862 m target.
- **Resin mass and print time** are not computed. They come only from the slicer for the chosen printer and
  resin. The prop volume in mm³ is in the manifest.
- **The stand** is a separate part. Its saddle is cut by the prop itself, swept upward, so the prop drops
  in. The post sits near the solid prop's volume centroid, which is not a biological centre of gravity.
  Whether the prop balances on it is not tested.

## Checks run on every mesh (`engineering/geometry/validate.py`)

These are computed from the triangle arrays, not trusted from the mesh library:

- finite vertices;
- no degenerate triangles: area < 1e-10 mm² or a repeated index;
- every undirected edge used by exactly two faces, and every directed edge used once, i.e. a closed,
  consistently oriented 2-manifold;
- one face-connected component;
- no unreferenced vertices;
- positive signed volume;
- Euler characteristic and genus (all props are genus 0);
- bounds within a 120 mm box;
- a canonical mesh sha256.

Each of these has a negative control in the tests: a missing face, a flipped face, an inside-out mesh, two
pieces, a NaN, a degenerate face and an oversized box. The thickness sampler has two: a 1 mm slab must measure
1.0 mm, and a 0.5 mm slab must fail the 1 mm gate.

Further checks:

- **STL weld.** STL is float32, so vertices that coincide at float32 are welded before writing. Form A had
  2 such vertices and 4 collapsing faces. The welded mesh is what was checked and written.
- **STL round trip.** The written STL is re-read and re-checked.
- **Rebuild from JSON.** Rebuilding each prop from its design JSON reproduces the committed mesh hash
  (`test_prop_rebuilds_from_its_design_json`).
- **Resolution convergence.** Each prop is built at three resolutions. The default against the fine
  build differs by at most 0.25 % in volume and 0.22 % in extent across all six props, against a 1 % tolerance.
- **Minimum wall (gated).** 3,000 area-weighted face centroids per mesh, each with an inward ray to the next
  surface. A mesh fails (`ok: false`, and the build exits 1) unless every sampled ray hits a wall at
  ≥ 1.0 mm. That 1.0 mm is our provisional prop choice, not a certified setting for any printer or resin.

  | | A | B | C | N1 | N2 | N3 |
  |---|---|---|---|---|---|---|
  | prop minimum (mm) | 1.26 | 1.60 | 1.60 | 1.60 | 1.60 | 1.60 |
  | stand minimum (mm) | 3.21 | 2.15 | 4.00 | 4.00 | 1.35 | 2.03 |

  A 0.5 mm slab is the test's negative control. This is a sample, so a thinner region between samples can be
  missed.

**Not checked:**

- global self-intersection (manifold3d's booleans produce none by construction, but nothing here
  re-verifies that);
- slicing, supports, cups, minima and island detection, all of which depend on orientation;
- resin-specific thin-wall limits;
- the aerodynamics of the prop;
- any physical print.

## Formlabs: what was read, and what was not available

Read on 2026-10-31:

- **Design Specs** (support.formlabs.com/s/article/Design-Specs, read via r.jina.ai because the page is
  client-rendered).
  - Minimums: supported and unsupported wall 0.4 mm, hole 0.8 mm, drain hole 3.5 mm, clearance 0.5 mm.
  - The **stated basis is Clear resin at 100 µm on a Form 2**. No Form 4 or Form 4L figure was found, so
    these minimums are not assumed to hold for the user's printer.
  - Our 1.6 mm fins and ≥ 1 mm walls are a provisional choice for a handled prop, not a certified setting.
- **Design Models for Printability** (formlabs.com/support/Design-Models-for-Printability/). It gives build
  volumes for Form 1+, 2, 3, 3B, 3L, 3BL and Fuse 1 only. The smallest listed is 125 × 125 × 165 mm.
  The props are solid, with no enclosed voids, so they need no drain holes.
- **PreForm Local API** (developer.formlabs.com core-concepts/validate and examples/printability-report).
  It lists `validate_manifoldness`, `validate_thin_features` (example threshold 0.5 mm), `validate_cups`,
  `validate_minima`, `validate_supportedness`, `validate_in_bounds` and `validate_interferences`.

**PreForm on this host: not available.**

- Nothing listens on the API's default port 44388.
- There is no PreForm config directory and no PreForm environment variable.
- No credentials were looked for or copied.

None of the PreForm checks above has been run.

### Operator checklist (do this in PreForm before printing)

1. **Choose the actual printer and resin.** They are unknown to this repository, and every design JSON says
   `printer_resin: unknown`. Record both, then read that printer's build volume and that resin's minimum wall
   from current Formlabs documentation. Do not use the Form 2 figures above. If the resin's minimum wall is
   above 1.0 mm, rebuild with a thicker plate before slicing.
2. **Import** `artifacts/print/stl/<form>.stl`. Units are millimetres.
   - Check the sha256 against `manifest.json` before importing.
   - Import each stand (`<form>-stand.stl`) as a **separate** job or a separate part. Do not merge it with
     the prop.
3. **Orient and support.** Fins away from the build plate, the body at an angle, and supports on the
   ventral side so marks fall on the underside. Never print the fins flat against the plate.
4. **Run PreForm's printability checks** and record each result:
   - manifold / repair: expect no change; if PreForm repairs anything, stop and report it;
   - thin features, at the chosen resin's minimum wall;
   - cups and minima, at the chosen orientation;
   - supportedness;
   - in bounds;
   - interferences, if several parts share one job.
5. **Read resin volume and print time from the slicer only.** Record them with the printer, resin, layer
   height and PreForm version.
6. **Save the .form file** and record its hash next to this checklist's results.
7. **Do not start the print from an agent.** A person starts it.

## Prior art

Saro-Cortes, Cui, Dufficy, Boctor, Flammang & Wissa (2022), *An Adaptable Flying Fish Robotic Model for
Aero- and Hydrodynamic Experimentation*, Integr. Comp. Biol., doi:10.1093/icb/icac101, PMID 35771996.

- **Read level: abstract, via Crossref.** OUP's PDF returned 403, r.jina.ai hit a security-check page, and
  Europe PMC has no full text.
- **What the abstract reports.** A modular, flying-fish-inspired robotic model was validated against
  earlier work on preserved fish. In a wind tunnel at Re 30,000, efficiency was highest with the pelvic fins
  directly behind the pectorals, and pitching stability was not achieved at positive pelvic pitch or with the
  pelvic fins directly below the pectorals.
- **Whether its geometry is published as data is unknown.** Nothing here uses it, and nothing here is
  claimed to be novel relative to it.
- **It is relevant to Form C,** whose pelvic placement is a figure read from Fish 1990, not an optimised
  position.

## Species graph

`artifacts/print/species-graph.json` and `img/species-graph.png` separate the kinds of node:

- **Sourced analogues:**
  - extant: halfbeaks, *Oxyporhamphus*, *Exocoetus*, *Cypselurus*, and the Daane S1A specimens;
  - experimental: zebrafish, with no edge into any form;
  - fossil: *Potanichthys*, a convergent four-wing configuration and not an ancestor.
- **Engineered forms:** A, B and C, and one node for the N1–N3 comparison set, which takes the *Cypselurus*
  fits at 0.05 kg with NCA's S and AR factors.

Each node and edge carries its read level. The only phylogenetic edges are the sourced ones: flyingfishes
are nested within the halfbeaks (Lovejoy et al. 2004, abstract). The A→B and A→C edges are
`conjectured_route`, drawn dashed red and labelled "not demonstrated, not claimed reachable". The test
`test_graph_keeps_conjecture_apart` enforces that no conjectured edge touches a sourced node.
