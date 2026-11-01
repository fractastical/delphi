"""Score the frozen protocol's arms against its frozen gates. Computes nothing it cannot derive.

Energy terms use Morpheus' own formulas, read from v2.3.9 source:
  VolumeConstraint.hamiltonian   = strength * (target - V)^2                    [shape/volume_constraint.cpp:26]
  SurfaceConstraint.hamiltonian  = strength * (target*2*sqrt(pi*V) - S)^2       [shape/surface_constraint.cpp:65,89]
with V = cell.volume and S = cell.surface as logged, so these reproduce the engine exactly.
The cell-medium adhesion term is NOT computed: it needs the per-cell interface with medium,
which is not logged, and Morpheus' hexagonal normalized surface is not recoverable from the
written lattice image by a plain neighbour count. Gap perimeter below is a descriptive
4-neighbour measure on the TIFF, explicitly not that Hamiltonian term.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

TOTAL_NODES = 40000
NODES_PER_CELL = 625
NODE_AREA_UM2 = 0.8494869358669834


def load_arm(d: Path) -> dict | None:
    log = d / "logger.csv"
    if not log.exists():
        return None
    arm = json.loads((d / "build.json").read_text())["arm"]
    by = defaultdict(list)
    with log.open() as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            by[float(r["time"])].append((float(r["cell.volume"]), float(r["cell.surface"]),
                                         float(r["cell.center.x"]), float(r["cell.center.y"]),
                                         int(float(r["cell.id"]))))
    ts = sorted(by)
    series = []
    for t in ts:
        rows = by[t]
        vol = sum(v for v, _, _, _, _ in rows)
        e_v = arm["lambda_v"] * sum((NODES_PER_CELL - v) ** 2 for v, _, _, _, _ in rows)
        e_s = arm["lambda_s"] * sum((2 * math.sqrt(math.pi * v) - s) ** 2 for v, s, _, _, _ in rows)
        series.append(dict(t=t, n=len(rows), gap=TOTAL_NODES - vol, e_volume=e_v, e_surface=e_s))
    return dict(arm=arm, series=series, by_time=by, times=ts)


def tiff_gap(d: Path, frame_step: float) -> list[tuple[float, int, int]]:
    """(model_time, medium_node_count, gap_perimeter_4n) per written frame. Independent of the logger."""
    tifs = sorted(d.glob("*.tif*"))
    if not tifs:
        return []
    im = Image.open(tifs[0])
    out = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        a = np.array(im)
        med = a == 0
        # 4-neighbour boundary between medium and any cell; descriptive, not the CPM surface term
        per = int((med[:, :-1] != med[:, 1:]).sum() + (med[:-1, :] != med[1:, :]).sum())
        out.append((i * frame_step, int(med.sum()), per))
    return out


def closure(series: list[dict], mcs: float) -> dict:
    g0, gend = series[0]["gap"], series[-1]["gap"]
    hit = next((s["t"] for s in series if s["gap"] <= 0), None)
    # CPM dynamics advance per Monte-Carlo sweep, not per model time unit, so closure is
    # reported in sweeps as well. MCSDuration is model time per sweep.
    return dict(gap0=g0, gap_end=gend, gap0_um2=g0 * NODE_AREA_UM2,
                closed_fraction=(1 - gend / g0) if g0 > 0 else None,
                state=("UNWOUNDED" if g0 <= 0 else ("CLOSED" if hit is not None else "ARRESTED")),
                closure_time=hit, closure_sweeps=(hit / mcs) if hit is not None and g0 > 0 else None)


def coef(gap_nodes: float, n_cells: int, j: float) -> float:
    """A^2 / (N * J * P) with P = 2*sqrt(pi*A); lambda_V * coef = Phi."""
    return gap_nodes ** 2 / (n_cells * j * 2.0 * math.sqrt(math.pi * gap_nodes))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    proto = json.loads(Path(a.protocol).read_text())
    runs = Path(a.runs)

    arms, missing = {}, []
    for spec in proto["arms"]:
        got = load_arm(runs / spec["name"])
        (arms.__setitem__(spec["name"], got) if got else missing.append(spec["name"]))

    res, gates = {}, []
    for name, A in arms.items():
        c = closure(A["series"], A["arm"]["mcs"])
        tif = tiff_gap(runs / name, A["arm"]["frame_step"])
        res[name] = dict(arm=A["arm"], **c,
                         n_cells=A["series"][0]["n"], t_end=A["series"][-1]["t"],
                         e_volume_end=A["series"][-1]["e_volume"], e_surface_end=A["series"][-1]["e_surface"],
                         e_volume_start=A["series"][0]["e_volume"], e_surface_start=A["series"][0]["e_surface"],
                         tiff_frames=len(tif),
                         phi=(A["arm"]["lambda_v"] * coef(c["gap0"], A["series"][0]["n"], A["arm"]["j_cell_medium"]))
                         if c["gap0"] > 0 and A["arm"]["j_cell_medium"] > 0 else None)

    # G1 area conservation: gap is defined as TOTAL - sum(volume), so check the sum is an exact integer split
    bad = [(n, s["t"]) for n, A in arms.items() for s in A["series"]
           if abs(s["gap"] + (TOTAL_NODES - s["gap"]) - TOTAL_NODES) > 1e-9 or s["gap"] < -1e-9 or s["gap"] % 1 != 0]
    gates.append(dict(id="G1", passed=not bad, detail=f"{len(bad)} non-integer or negative gap samples"))

    # G1b independent TIFF channel
    mism = []
    for n, A in arms.items():
        lg = {s["t"]: s["gap"] for s in A["series"]}
        for t, med, _ in tiff_gap(runs / n, A["arm"]["frame_step"]):
            if t in lg and abs(lg[t] - med) > 0:
                mism.append((n, t, lg[t], med))
    gates.append(dict(id="G1b", passed=not mism, detail=f"{len(mism)} frames disagree between logger and TIFF",
                      examples=mism[:5]))

    # G2 cell count constant
    g2 = [n for n, A in arms.items() if len({s["n"] for s in A["series"]}) != 1]
    gates.append(dict(id="G2", passed=not g2, detail=f"arms with a changing cell count: {g2}"))

    # G3 initial gap exactly 625*k
    g3 = []
    for n, A in arms.items():
        k = {100: 0, 200: 1, 400: 4, 1300: 7}[A["arm"]["wound_r2"]]
        if A["series"][0]["gap"] != NODES_PER_CELL * k:
            g3.append((n, k, A["series"][0]["gap"]))
    gates.append(dict(id="G3", passed=not g3, detail=f"arms whose initial gap is not 625*k: {g3}"))

    neg = res.get("A4-tension-off-NEGATIVE")
    gates.append(dict(id="G4", passed=bool(neg) and neg["gap_end"] >= 0.95 * neg["gap0"],
                      detail=f"gap_end/gap0 = {neg['gap_end'] / neg['gap0']:.4f} (needs >= 0.95)" if neg else "arm missing"))

    pos = arms.get("A5-unwounded-POSITIVE")
    nz = [s["t"] for s in pos["series"] if s["gap"] != 0] if pos else None
    gates.append(dict(id="G5", passed=bool(pos) and not nz,
                      detail=f"{len(nz)} logged times with a non-zero gap" if pos else "arm missing"))

    seeds = [res[n]["closed_fraction"] for n in ("A1-baseline", "C1-seed2", "C2-seed3") if n in res]
    sd = float(np.std(seeds, ddof=1)) if len(seeds) > 2 else None
    gates.append(dict(id="G6", passed=None, detail=f"closed fractions {seeds}, sample SD {sd}",
                      note="3 seeds of one model; descriptive spread, not an empirical uncertainty"))

    g7 = None
    if "A1-baseline" in res and "C3-halfstep" in res:
        g7 = abs(res["C3-halfstep"]["closed_fraction"] - res["A1-baseline"]["closed_fraction"])
    sw = {n: res[n]["closure_sweeps"] for n in ("A1-baseline", "C3-halfstep") if n in res}
    gates.append(dict(id="G7", passed=(g7 is not None and g7 <= 0.10),
                      detail=f"|closed(mcs=0.5) - closed(mcs=1)| = {g7}" if g7 is not None else "arm missing",
                      sweep_invariant=dict(
                          closure_sweeps=sw,
                          equal=(len(sw) == 2 and sw["A1-baseline"] == sw["C3-halfstep"]),
                          note="not a declared gate bound. Model time to closure halves when MCSDuration halves, "
                               "while closure measured in Monte-Carlo sweeps is unchanged. Closure TIME in model "
                               "units is therefore a statement about the sampler; closure in sweeps is not.")))

    # G8 held-out threshold prediction
    brackets = {}
    for k in (1, 4, 7):
        rows = sorted((res[n] for n in res if n.startswith(f"B-k{k}-")), key=lambda r: r["arm"]["lambda_v"])
        cl = [r["arm"]["lambda_v"] for r in rows if r["state"] == "CLOSED"]
        ar = [r["arm"]["lambda_v"] for r in rows if r["state"] == "ARRESTED"]
        if cl and ar and max(cl) < min(ar):
            lo, hi = max(cl), min(ar)
            brackets[k] = dict(lo=lo, hi=hi, lambda_star=math.sqrt(lo * hi),
                               n_cells=rows[0]["n_cells"], gap0=rows[0]["gap0"],
                               coef=coef(rows[0]["gap0"], rows[0]["n_cells"], rows[0]["arm"]["j_cell_medium"]),
                               closed=cl, arrested=ar)
    g8 = dict(brackets=brackets)
    if {1, 7} <= brackets.keys() and 4 in brackets:
        phis = [brackets[k]["lambda_star"] * brackets[k]["coef"] for k in (1, 7)]
        phi_star = math.sqrt(phis[0] * phis[1])
        pred = phi_star / brackets[4]["coef"]
        inside = brackets[4]["lo"] <= pred <= brackets[4]["hi"]
        g8.update(phi_star_from_k1_k7=phi_star, phi_k1=phis[0], phi_k7=phis[1],
                  predicted_lambda_star_k4=pred,
                  measured_bracket_k4=[brackets[4]["lo"], brackets[4]["hi"]], inside=inside)
    gates.append(dict(id="G8", passed=g8.get("inside"), detail=g8))

    out = dict(schema="frontier.epithelial-results.v1",
               protocol_sha256=__import__("hashlib").sha256(Path(a.protocol).read_bytes()).hexdigest(),
               arms_missing=missing, arms=res, gates=gates)
    Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    print(f"arms scored {len(res)}, missing {len(missing)}")
    for g in gates:
        print(f"  {g['id']:4s} {str(g['passed']):5s} {str(g['detail'])[:150]}")


if __name__ == "__main__":
    main()
