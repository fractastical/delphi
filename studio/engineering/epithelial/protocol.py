"""The frozen protocol for the epithelial gap-closure testbed.

This file declares every arm, every control and every acceptance gate with its bound,
BEFORE any result is produced. `--emit` writes artifacts/epithelial/protocol.json, which
is committed ahead of the outputs. Changing a bound after a result exists is a material
change: record it as a revision, do not edit it away.

Mechanism under test (model-level, not a claim about tissue):
  a confluent CPM monolayer with a central hole closes when the cell-medium interface
  energy it can shed outweighs the volume-constraint cost of the stretching required to
  fill the hole. The predicted control group is

      Phi = lambda_V * A_gap^2 / (N_cells * J_cell_medium * P_gap)

  with P_gap = 2*sqrt(pi*A_gap) for a disc. Phi below a threshold Phi* => closure.
  Phi is derived from the CPM energy, not fitted to data, and Phi* is the one number fitted.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# wound radius^2 -> cells removed, measured on this model 2026-10-31 (preflight, not a result):
#   r2=100 -> 0 cells, 200 -> 1, 400 -> 4, 1300 -> 7, 1800 -> 12.
# Every removed cell is exactly 625 nodes, so the initial gap area is exact.
GAPS = {0: 100, 1: 200, 4: 400, 7: 1300}
NODE_AREA_UM2 = 0.8494869358669834

BASE = dict(stop=1000, seed=1, lambda_v=0.3, lambda_s=5, protrusion=80, j_cell_medium=140,
            mcs=1, wound_r2=GAPS[4], log_step=10, frame_step=25)


def arm(name, group, purpose, **over):
    a = dict(BASE, name=name, group=group, purpose=purpose)
    a.update(over)
    return a


def arms() -> list[dict]:
    out = [
        # A. mechanism decomposition at one gap (4 cells removed, 2500 nodes = 2124 um^2)
        arm("A1-baseline", "A", "reference arm; all mechanisms on"),
        arm("A2-motility-off", "A", "ablate lamellipodial protrusion (Act model) only", protrusion=0),
        arm("A3-contractility-off", "A", "ablate the perimeter/cortical-tension constraint only", lambda_s=0),
        arm("A4-tension-off-NEGATIVE", "A",
            "negative control: no cell-medium interface energy, so no closure drive. MUST NOT close.",
            j_cell_medium=0),
        arm("A5-unwounded-POSITIVE", "A",
            "positive control: identical code path with no cell removed. Gap MUST read 0 throughout.",
            wound_r2=GAPS[0]),
    ]
    # B. control surface: volume-constraint strength x gap geometry
    for k in (1, 4, 7):
        for lv in (0.1, 0.3, 1, 5, 50):
            out.append(arm(f"B-k{k}-lamV{lv}", "B",
                           f"closure threshold sweep, {k} cell(s) removed", lambda_v=lv, wound_r2=GAPS[k]))
    # C. numerical controls
    out.append(arm("C1-seed2", "C", "seed replicate of A1", seed=2))
    out.append(arm("C2-seed3", "C", "seed replicate of A1", seed=3))
    out.append(arm("C3-halfstep", "C", "Monte-Carlo step refinement of A1", mcs=0.5))
    return out


def gates() -> list[dict]:
    return [
        dict(id="G1", name="area conservation",
             statement="At every logged time and in every arm, sum(cell.volume) + gap_nodes == 40000 exactly.",
             bound="exact integer identity",
             why="the gap measure is defined as 40000 - sum(cell.volume); if this fails the measure is wrong, "
                 "not the model. This gate checks the instrument, not the result."),
        dict(id="G1b", name="independent gap channel agrees",
             statement="For every arm and every TIFF frame, the count of medium nodes in the CPM lattice image "
                       "equals the logger-derived gap_nodes at the same model time.",
             bound="exact",
             why="the logger route (40000 - sum of a logged per-cell property) and the TIFF route (counting "
                 "medium pixels in the written lattice) share no code. If they agree the gap measure is not an "
                 "artifact of either; if they disagree, neither number is usable."),
        dict(id="G2", name="cell-count conservation",
             statement="Cell count is constant from the first logged time after wounding to the last, in every arm.",
             bound="exact", why="the model has no division and no death after the wounding step."),
        dict(id="G3", name="initial gap is as designed",
             statement="gap_nodes(t=0) == 625 * k for the k cells the arm removes.",
             bound="exact", why="confirms the wound geometry actually applied."),
        dict(id="G4", name="negative control does not close",
             statement="A4-tension-off-NEGATIVE ends with gap >= 0.95 * its initial gap.",
             bound=">= 0.95", why="with no cell-medium interface energy there is no closure drive. "
                                  "If this arm closes, closure in the other arms is not driven by what is claimed."),
        dict(id="G5", name="positive control reads zero",
             statement="A5-unwounded-POSITIVE has gap_nodes == 0 at every logged time.",
             bound="exact", why="a gap measure that cannot report 0 on an unwounded sheet cannot report closure."),
        dict(id="G6", name="seed spread (descriptive)",
             statement="Report the closed-fraction spread of A1/C1/C2 as a sample SD over 3 shared-model seeds.",
             bound="reported, no threshold",
             why="three seeds of one model are not independent biological samples; no pass/fail is assigned."),
        dict(id="G7", name="Monte-Carlo step refinement",
             statement="|closed_fraction(C3, mcs=0.5) - closed_fraction(A1, mcs=1)| <= 0.10.",
             bound="<= 0.10 absolute",
             why="halving the MCS duration doubles the Monte-Carlo sweeps per unit model time. A result that "
                 "moves more than this is a statement about the sampler, not about gap closure."),
        dict(id="G8", name="held-out threshold prediction",
             statement="Fit Phi* from the measured closure thresholds at k=1 and k=7 ONLY (geometric mean of the "
                       "bracketing lambda_V values at each k). Predict lambda_V* at the held-out k=4 as "
                       "Phi*/coef(k=4). The prediction must fall inside the lambda_V interval that brackets the "
                       "measured k=4 transition.",
             bound="prediction inside the measured bracketing interval at k=4",
             why="k=4 is never used to fit. This is the only predictive claim made, and its domain is this CPM, "
                 "this parameter set and gaps of 1-7 cells."),
    ]


def phi(lambda_v: float, gap_nodes: float, n_cells: int, j: float) -> float:
    """Dimensionless closure number. Undefined when there is no gap or no interface energy."""
    if gap_nodes <= 0 or j <= 0 or n_cells <= 0:
        return float("nan")
    perimeter = 2.0 * math.sqrt(math.pi * gap_nodes)
    return lambda_v * gap_nodes ** 2 / (n_cells * j * perimeter)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", required=True)
    a = ap.parse_args()
    doc = {
        "schema": "frontier.epithelial-protocol.v1",
        "status": "FROZEN before any arm was run",
        "engine": {"name": "Morpheus", "tag": "v2.3.9",
                   "binary_sha256": "3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad",
                   "base_example": "Examples/CPM/Protrusion_2D.xml",
                   "base_sha256": "da2a27c8e552041ee4a51d7ff1e7332466f5180762642c997594731c92737db2"},
        "measurement": {
            "gap_nodes": "40000 - sum(cell.volume) over all living cells at that logged time",
            "gap_um2": f"gap_nodes * {NODE_AREA_UM2}",
            "closed_fraction": "1 - gap_nodes(t_end) / gap_nodes(t=0)",
            "closure_call": "an arm is CLOSED when gap_nodes reaches 0 before t_end, otherwise ARRESTED",
            "trajectories": "cell.center.x, cell.center.y per cell per logged time",
            "mechanical_cost": "interface energy J*sum(cell.surface touching medium) is NOT separable from the "
                               "logged total surface, so the reported cost is the volume-constraint term "
                               "lambda_V * sum((cell.volume - 625)^2) plus lambda_S * the logged aspherity term; "
                               "both are CPM energy in model units and neither is a force or a stress."},
        "caps": {"cpu_quota_pct": 200, "memory_max": "2G", "memory_swap_max": 0,
                 "tasks_max": 256, "runtime_max_s": 600, "threads": 1},
        "arms": arms(),
        "gates": gates(),
        "not_claimed": [
            "This is not a reproduction of Bai & Zeng 2023. Their mechanics is 3D continuum finite element with "
            "cohesive-zone traction-separation laws; a Cellular Potts Model implements none of those equations. "
            "Only the geometric construction is shared: Voronoi monolayer, wound by removing central cells, "
            "no proliferation.",
            "No parameter here is calibrated to any cell line, species or measured tissue. CPM energies are in "
            "model units inherited from the upstream Act-model example.",
            "Closure times in model time units are not minutes, hours or any measured closure rate.",
            "No purse-string actomyosin cable is modelled. Closure here is interface energy plus Act-model "
            "protrusion only.",
            "Agreement between this model's behaviour and a published trend is model-level agreement. It is not "
            "experimental validation and does not raise the evidence level of either.",
        ],
    }
    Path(a.emit).parent.mkdir(parents=True, exist_ok=True)
    Path(a.emit).write_text(json.dumps(doc, indent=1))
    print(f"arms={len(doc['arms'])} gates={len(doc['gates'])} -> {a.emit}")


if __name__ == "__main__":
    main()
