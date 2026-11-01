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


def arms_r2() -> list[dict]:
    """Revision 2. Added AFTER revision 1 ran, for two stated reasons, and frozen before it ran.

    Reason 1: revision 1's G4 was mis-specified. It assumed cell-medium interface energy is
    necessary for closure; with J=0 the gap closed anyway, because Act-model protrusion drives
    it. The true no-drive control turns BOTH off. Revision 1's G4 stays failed and is not relabelled.
    Reason 2: revision 1's G8 could not be evaluated because k=1 closed at every swept lambda_V,
    so no threshold bracket existed there. Revision 2 extends that sweep, and replaces the
    held-out test with one whose prediction is derived rather than fitted: the Phi group says
    the threshold lambda_V is proportional to J, so doubling J must double it. No revision 2
    measurement is used to fit anything.
    """
    out = [
        arm("F1-no-drive-NEGATIVE", "F",
            "true negative control: both closure drives off (no interface energy, no protrusion). MUST NOT close.",
            j_cell_medium=0, protrusion=0),
    ]
    # D. held-out J scaling at the gap whose threshold revision 1 bracketed (k=4)
    for lv in (0.3, 0.6, 1, 2, 4):
        out.append(arm(f"D-k4-J280-lamV{lv}", "D",
                       "threshold at double the interface energy; prediction derived, not fitted",
                       lambda_v=lv, j_cell_medium=280))
    # E. complete the gap ladder: k=1 never arrested below lambda_V=50
    for lv in (200, 1000, 5000):
        out.append(arm(f"E-k1-lamV{lv}", "E", "extend the k=1 sweep until it arrests",
                       lambda_v=lv, wound_r2=GAPS[1]))
    # F. protrusion dose-response on an ARRESTED gap (k=4 at lambda_V=1 arrested at 0.684)
    for p in (0, 20, 40, 160):
        out.append(arm(f"F2-prot{p}", "F", "protrusion dose-response on an arrested gap",
                       lambda_v=1, protrusion=p))
    return out


def gates_r2() -> list[dict]:
    return [
        dict(id="G9", name="held-out: threshold scales with interface energy",
             statement="Revision 1 bracketed the k=4 closure threshold at lambda_V in (0.3, 1.0) with J=140. "
                       "Phi is linear in lambda_V and inverse in J, so at J=280 the threshold must sit in "
                       "(0.6, 2.0). The measured J=280 bracket's geometric-mean threshold must fall in that "
                       "interval.",
             bound="measured lambda* at J=280 within [0.6, 2.0]",
             why="the prediction comes from the algebraic form of Phi and revision 1's J=140 bracket. No J=280 "
                 "result is used to derive it, so this is a genuine out-of-sample test of the group's "
                 "J-dependence. It tests only that dependence; revision 1 already refuted a constant Phi* "
                 "across gap size, and G9 does not re-open that."),
        dict(id="G10", name="no-drive control does not close",
             statement="F1-no-drive-NEGATIVE ends with gap >= 0.95 * its initial gap.",
             bound=">= 0.95",
             why="replaces revision 1's G4, which turned off only one of the two drives. If the gap closes with "
                 "both off, closure is an artifact of the volume constraint or the initialisation, not of either "
                 "modelled mechanism."),
        dict(id="G11", name="protrusion dose-response is monotone",
             statement="At k=4 and lambda_V=1, closed_fraction is non-decreasing in protrusion strength over "
                       "{0, 20, 40, 80, 160}; the 80 point is revision 1's B-k4-lamV1.",
             bound="non-decreasing",
             why="Bai & Zeng 2023 report that promoting lamellipodial protrusion raises the closure rate, over "
                 "an assumed 0.2-10 pN range in a finite-element model. This checks whether this CPM carries the "
                 "same ordering. Agreement is between two models and is not experimental validation; a CPM "
                 "protrusion strength is not a force in piconewtons."),
        dict(id="G12", name="gap ladder is complete",
             statement="A closure threshold bracket exists at k=1, 4 and 7, and the three fitted Phi* values "
                       "are reported together with whether they agree.",
             bound="reported; a constant Phi* is NOT asserted",
             why="revision 1 found Phi* rising as the gap shrinks. This records the full ladder so the domain of "
                 "any rule is stated from three points rather than two."),
    ]


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
    ap.add_argument("--revision", type=int, default=1)
    a = ap.parse_args()
    doc = {
        "schema": "frontier.epithelial-protocol.v1",
        "status": "FROZEN before any arm of this revision was run",
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
        "revision": a.revision,
        "arms": arms() if a.revision == 1 else arms_r2(),
        "gates": gates() if a.revision == 1 else gates_r2(),
        "supersedes": None if a.revision == 1 else
            "artifacts/epithelial/protocol.json (revision 1). Revision 1's arms and gate outcomes stand as run; "
            "no revision 1 bound is changed and no revision 1 failure is relabelled.",
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
