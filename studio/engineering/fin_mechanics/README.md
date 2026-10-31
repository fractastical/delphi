# fin_mechanics: scoped elastic fin-ray surrogate (SIMULATED)

A clamped-free Euler-Bernoulli cantilever that turns a declared flight load into a line load on one fin
ray and reports the resulting tip deflection across an **assumed** range of bending stiffness EI.
Evidence kind is `simulated` everywhere. It is not a fluid-structure-interaction model, not a fish
model, and makes no claim of biological feasibility.

## Method and sources actually read
- Governing equation: `d^2/dx^2 (EI d^2w/dx^2) = q`, small deflection, static. Solver: Hermite-cubic
  finite elements (numpy + scipy.sparse direct solve), checked against closed forms:
  tip load `w(L) = P L^3 / (3 EI)`, uniform load `w(L) = q L^4 / (8 EI)`.
- Textbook primary reference for the equations: Timoshenko & Gere, *Mechanics of Materials*. **Not read here.**
  What was read: the Wikipedia article "Euler-Bernoulli beam theory" (first ~100,000 of ~135,811 characters,
  through a summarising fetch tool): governing equation, tip-load deflection curve, small-slope assumptions.
  The uniform-load formula was not in the portion read; it is verified in the tests by independent numerical
  integration of M(x)/EI (`scipy.integrate.quad`), and the point-load one likewise.
- Fish-fin source: Alben, Madden & Lauder (2007), *The mechanics of active fin-shape control in ray-finned
  fishes*, J R Soc Interface 4(13):243-256, doi:10.1098/rsif.2006.0181 (PMC2359861). **Full text read** as the
  publisher HTML hosted on PMC, downloaded with curl (`curl -sSL https://pmc.ncbi.nlm.nih.gov/articles/PMC2359861/`,
  exit 0, HTTP 200, 213,488 bytes, sha256 `3ee6a0ea...b7854`) and text-extracted with `python -I` (70,538
  characters). The PDF could not be obtained (PMC served a proof-of-work page; royalsocietypublishing.org and
  Europe PMC returned 403; not bypassed), so the HTML has no page numbers and citations are by section/figure.
  An earlier version of this package relied on a summarising fetch tool; the numbers below were then re-checked
  against the primary text and **confirmed**:
  - Section 3.4 "Physical scalings" (after eq. 3.19): "using three-point bending tests ... the 'composite'
    Young's modulus ... E ~ 1e8-1e9 N m^-2, with the average area moment of inertia I ~ 1e-6 cm^4. Hence, the
    measured B = EI ~ 1e-6-1e-5 J m." J m = N m^2, and 1e-6 cm^4 = 1e-14 m^4, so E*I = 1e-6 to 1e-5 N m^2
    (consistent). This is the gray band. Species bluegill sunfish (*Lepomis macrochirus*); 24 rays from six fish
    (maximum ray length 40.3 +/- 0.8 mm), tested in water within 48 h; the scaling estimate uses L = 4 cm for a
    typical ray. It is an **order-of-magnitude product of a composite E and an average I** (area moments from
    one fin's microCT scan, Section 2); it is not a per-ray or per-position measurement and is not in any table
    or figure. The paper's own scaling argument (eq. 3.19) gave B ~ 1e-6 J m, lower than measured.
  - Section 5.2 and Figure 7 caption: base-clamped ray, vertical point force at about two-thirds of the way along
    the ray; slope 1.98 N m^-1 with both hemitrich bases clamped, "about 12 times the value when one hemitrich is
    free". That is a stiffness (N/m) at a point load, not an EI.
  - The paper's model is a *bilaminar* elastica with intraray shear (Section 3), not a single beam, and it gives
    no closed-form tip-deflection formula. The band is **not** used to calibrate or validate anything here and
    is drawn in gray hatching as context only.
- Other fin-ray papers (Lauder lab, Fernandez-Gutierrez et al.) appeared in search results and were NOT read.

## Inputs: `frontier.finmech.request/1`
See `example_request.json` (a **declared illustration**, not a design from the guilds solver).
| field | meaning |
|---|---|
| `candidate` | shape of `frontier.glide.candidate/1` (read-only): `solver_result.status == "feasible"`, `witness{m,S,b,V}` exact rational strings, `units`, `flight_assumptions.rho`, `.CL_max` each `{value, unit, source}` |
| `fin.ray_length_fraction_of_semispan` | declared; `L_ray = f * b/2` (ray length from the candidate span) |
| `fin.tributary_width_m` *or* `fin.n_rays` | declared width of membrane/ray spacing carried by one ray; or `w_t = b / n_rays` (exactly one) |
| `fin.CL` | optional override of `CL_max` |
| `elastic.EI_status` | must be exactly `ASSUMED_RANGE_NOT_MEASURED` |
| `elastic.EI_min_Nm2`, `EI_max_Nm2`, `n_points` | assumed log-spaced EI range (N m^2) |
| `validity.tip_over_L_max`, `slope_max_rad` | declared small-deformation limits (default 1/10, 1/5) |
| `numerics.n_elements` | FE elements |
Physical numbers are exact decimal/rational strings; JSON floats are refused. Refusals are structured
(`{"verdict":"refused","code":...}`), never repaired.

## Load-to-fin bridge (`load_bridge.py`)
`q_dyn = 0.5 rho V^2` [Pa]; `p = q_dyn CL` [Pa] is a **mean aerodynamic lift-pressure proxy**, not a measured
fin pressure; `q_line = p w_t` [N/m] with the declared tributary width; `L_ray = f b/2` [m];
`F = q_line L_ray` [N]. The ray then carries a uniform `q_line` (primary) or the same total force at the tip
(upper bound). The informational ratio `p S / (m g)` is reported, not enforced. Example: `rho=1.225, V=5,
CL=1 -> p = 245/16 Pa`, `w_t = 10 mm -> q_line = 0.153125 N/m`.

## Outputs: `frontier.finmech.result/1`
`inputs_sha256` (canonical JSON), `code_sha256` (+ per-file), `evidence_kind: "simulated"`, `assumptions`,
`not_established`, `load_bridge` (exact strings and floats), `critical_stiffness` (exact `EI_crit`, the stiffness
below which the declared load violates the linear limits), `sweep.rows` (each row has `valid`/`flag`; invalid
rows are reported, never hidden), `convergence`, `controls`, `measurement_question`, `sources_read`.
`beam.solve_checked(..., strict=True)` raises `SmallDeformationViolation` instead of returning the flag.

## Convergence
Static problem: no time step. Grid refinement (see `result.json`): constant-EI nodal values exact to round-off;
interpolated profile error observed order 4.00 (expected 4); tapered-EI (midpoint rule) tip error observed
order 2.00 (expected 2), reference by independent quadrature.

## Measurement question that would resolve the unknown EI
What is the effective flexural rigidity EI(x) of an excised ray of the target fin, under the clamping
condition matching its in-fin boundary condition, and is it above or below `EI_crit`? Apparatus: clamp the ray
base (state whether both hemitrichs; Alben et al. Fig. 7 report ~12x stiffness difference, point force at 2/3 of the ray), load the tip with a calibrated
micro-force transducer (<= 1 microN) or calibrated cantilever probe, track tip displacement optically
(<= 1 micrometre), keep hydrated, work at tip/L < 0.1, repeat with the clamp moved along the ray, and cross-check
with micro-CT second moment of area. `EI = P L^3 / (3 delta)` from the linear slope. Decision: `EI >= EI_crit`
keeps the declared load inside the small-deformation limit; otherwise a large-deformation model or lower load is
needed.

## Reproduce
```
OMP_NUM_THREADS=1 python -m engineering.fin_mechanics.sweep engineering/fin_mechanics/example_request.json result.json
OMP_NUM_THREADS=1 python -m engineering.fin_mechanics.render engineering/fin_mechanics/example_request.json engineering/fin_mechanics/artifacts
python -m pytest tests/test_fin_mechanics.py
```
Artifacts (`artifacts/`): `fin_mechanics.mp4` (H.264, 1280x720, 15 s, every frame an FEM solve),
`poster.png`, `result.json`, `manifest.json` (sha256 of request, code files, outputs, and of the computed
frame data; mp4 bytes can differ across ffmpeg builds, the frame-data hash is the reproducible quantity).
Re-render after any code change: a test compares the manifest's code hashes with the current files.

## Limitations (all remain open)
Euler-Bernoulli (no shear), single constant-EI beam, no bilaminar/intraray shear, no membrane, no taper in
the product model, load fixed and uncoupled to deformation, small-deformation results only. The default sweep
puts 29 of 61 assumed-EI points (the soft end, EI < EI_crit = 6.46e-4 N m^2) outside the declared limit for the
illustrative load; that is a statement about this declared load and geometry, nothing about any real fish. The scoped
EI range, ray length and tributary width are declared, not measured.
