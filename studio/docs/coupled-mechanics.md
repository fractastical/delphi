# Pressure-to-fin coupling: flow pressure → fin-ray traction → line load → deflection

Files: `engineering/coupled_mechanics/` (`contract.py`, `traction.py`, `couple.py`, `cases.py`,
`windtunnel_receipt.py`, `run.py`), `tests/test_coupled_mechanics.py`, and
`artifacts/coupled-mechanics/{result.json, poster.png, manifest.json}`.
Owner: the coupled-mechanics worker, coordinating with codex-03.

**Status: the adapter is implemented and checked. Coupling to an actual flow field is BLOCKED.**
The only completed flow field is the 2D sagittal wind tunnel. It contains no pectoral fin, and
its one in-plane strip is a single lattice cell thick. The 3D record from `cfd3d` does not exist
yet. Nothing here is a calibrated organism claim, and a passing unit or conservation check
establishes arithmetic only.

- [x] A port contract (`frontier.coupled.member-pressure/1`) with structured refusals.
- [x] Exact force and root-moment integration, and exact element-mean transfer onto the existing
  `fin_mechanics` FEM. That FEM is reused; no second beam solver was written.
- [x] Analytic checks: uniform and linear pressure, hand closed forms, grid order 2, force
  conservation exact, disabled-load control exactly 0, and EI scaling exactly 1/EI.
- [x] The actual 2D receipt: hash pins checked, read in Pa through the receipt's own mapping,
  a pressure-face force diagnostic, and the real tail strip refused through the contract.
- [x] The input contract sent to the CFD owner (`messages/coupled-mechanics-to-cfd3d.md`).
- [ ] A 3D member-pressure record with at least 2 cells across a fin ray (owner: cfd3d).
  This is reported by cfd3d (contract v0.1, `messages/cfd3d-to-coupled-mechanics.md`, 15:02 PDT,
  2026-10-31) and not re-measured here.
  - Fins are sub-grid at every planned resolution: a 0.5 mm plate needs L ≥ 923 cells to be
    2 cells thick, beyond one H100.
  - The fins enter as 3.7-cell shells, and every fin sample carries `resolved: false`.
  - So the blocker is the grid, not the schedule. Those samples will be refused
    (`MEMBER_UNRESOLVED`), and an actual fin load needs a resolved local fin-patch case or a
    validated sub-grid fin model. Neither exists.
- [ ] A measured EI(x) and a ray section (c, I) for a flying-fish ray (wet lab; no owner).
- [ ] Fluid-structure feedback. The coupling is one-way and static by design.

## Units and geometry, stated explicitly

| step | formula | unit |
|---|---|---|
| traction jump | Δp(s) = p_neg(s) − p_pos(s), acting along the member's unit normal | Pa |
| line load | q(s) = Δp(s) · w_t, with w_t the declared or geometric tributary width | Pa·m = N/m |
| resultant | F = ∫₀ᴸ q ds, computed exactly for piecewise-linear q | N |
| root moment | M₀ = ∫₀ᴸ q s ds = Σ h (q_a(2a+b) + q_b(a+2b)) / 6 | N·m |
| bending moment | M(x) = ∫ₓᴸ q(t)(t − x) dt, exact | N·m |
| deflection | (EI w'')'' = q, clamped-free, Hermite FEM (`fin_mechanics.beam`) | m |
| stress | σ = \|M\| c / I, only when a section is declared | Pa |

Refused, each with a test:
- **Wrong units:** pressure not in dimensional Pa (lattice or model units are never read as Pa),
  or a frame not in metres.
- **Wrong geometry:** a frame or member that is not the target's exactly (rational equality),
  stations not covering [0, L] exactly, or a normal that is not a unit vector perpendicular to
  the member.
- **Bad values:** floats, an undeclared tributary width, or concurrent time.
- **Wrong scope:** a 2D section offered for a `whole_fin_3d` target (`SAGITTAL_2D_NOT_3D`).
- **Unresolved member:** a simulated field with fewer than 2 cells across the member
  (`MEMBER_UNRESOLVED`, a declared minimum).
- **Missing provenance:** field or geometry hashes absent.

## What was run, and what it showed

The analytic cases reuse the fin_mechanics declared illustration (ρ 1.225, V 5 m/s, CL 1,
w_t 0.01 m, L 0.15 m), with the EI interval 1e-6 to 1e-5 N·m². That interval is Alben, Madden and
Lauder 2007, §3.4, a bluegill order-of-magnitude figure, used as context only.
- **Baseline:** uniform pressure reproduces `load_bridge` exactly (q = 49/320 N/m).
- **Load shape:** at equal total force, the tip deflection is 0.53× the uniform case for the
  root-heavy profile and 1.47× for the tip-heavy one.
- **Validity:** every case is outside the declared linear limit (tip/L ≤ 0.1). The result says
  that load and EI are incompatible under linear theory. It is not a deflection prediction, and
  it agrees with `fin_mechanics`' own EI_crit.
- **Grid study:** with element-mean transfer, the tip and root moment converge at observed
  order 2.00.

The actual 2D receipt is N1 baseline, Re 80, U 0.008 m/s in air, fields sha256 `10c2f417…`.
- **Pa mapping:** ρ(U/U_lat)²(ρ_lat − 1)/3, time-averaged over the last 20% (17 frames).
- **Force diagnostic:** the pressure-only staircase-face force is 0.97× the receipt's
  momentum-exchange lift and 0.44× its drag. That is plausible, since viscous drag is large at
  Re 80, but it is a diagnostic of the units and face bookkeeping, not a validation.
- **Tail strip:** ROI columns 52–54, row 35, one cell thick with fluid on both faces. It is
  refused `MEMBER_UNRESOLVED`. As a whole-fin-3D target it is `SAGITTAL_2D_NOT_3D`, and the
  declared pectoral ray gets `FRAME_MISMATCH`.

Poster: the left panel is the actual time-mean pressure field. The middle and right panels use
analytic pressure only, each labelled.

## Run

```
OMP_NUM_THREADS=1 systemd-run --user --scope -p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 \
  -p RuntimeMaxSec=600 -p CPUQuota=100% python3 -m engineering.coupled_mechanics.run artifacts/coupled-mechanics
python3 -m pytest tests/test_coupled_mechanics.py -q
```

`manifest.json` pins the inputs, the code and both outputs. A test fails when any of them is
stale, and a rerun is byte-identical.

## Integration

```
from engineering.coupled_mechanics import couple
result = couple.run(member_pressure_record, member_target)   # raises Refusal(code, detail)
```

Display the `scope` string with every result, and do not say "coupled" for an analytic or
refused case. When `cfd3d` publishes a 3D record, pass it through `couple.run` against a target
built from the same mesh feature. Nothing else changes.
