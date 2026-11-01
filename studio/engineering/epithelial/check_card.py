"""Check that every number quoted in the science card still matches the results file.

Pins expected VALUES rather than scanning the prose for digits: a scan over a document that
discusses its own numbers cannot tell a quoted figure from a described one. Each row below is
a claim the card makes; the script reads the same quantity out of results-r2.json and compares.
Run it after any re-run, and after any edit to the card's numbers.

It caught one real slip on first use: the card said R^2 0.956 where the fit gives 0.955.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def claims(A: dict, G: dict, S: dict) -> list[tuple[str, object, object]]:
    L = G["G12"]["detail"]["ladder"]
    g9 = G["G9"]["detail"]
    rows = [
        ("A1 closed", 1.0, A["A1-baseline"]["closed_fraction"]),
        ("A1 sweeps", 240.0, A["A1-baseline"]["closure_sweeps"]),
        ("A2 motility-off closed", 0.450, round(A["A2-motility-off"]["closed_fraction"], 3)),
        ("A3 contractility-off sweeps", 180.0, A["A3-contractility-off"]["closure_sweeps"]),
        ("A4 tension-off sweeps", 290.0, A["A4-tension-off-NEGATIVE"]["closure_sweeps"]),
        ("F1 no-drive floor", 0.220, round(A["F1-no-drive-NEGATIVE"]["closed_fraction"], 3)),
        # filled and residual are pinned SEPARATELY. Pinning only 1875 could not tell which
        # quantity it was, and an earlier card called it the filled amount when it is the
        # residual. Found by independent review of edc1e10, not by this checker.
        ("floor: residual gap nodes at target", 1875, 40000 - 61 * 625),
        ("floor: filled nodes at target", 625, int(A["F1-no-drive-NEGATIVE"]["gap0"]) - (40000 - 61 * 625)),
        ("floor: filled fraction at target", 0.250,
         round((A["F1-no-drive-NEGATIVE"]["gap0"] - (40000 - 61 * 625)) / A["F1-no-drive-NEGATIVE"]["gap0"], 3)),
        ("floor: filled nodes measured", 551,
         round(A["F1-no-drive-NEGATIVE"]["gap0"] - A["F1-no-drive-NEGATIVE"]["gap_end"])),
        ("G9 measured bracket", [1, 2], g9["measured_bracket"]),
        ("G9 lambda*", 1.414, round(g9["measured_lambda_star"], 3)),
        ("G9 predicted interval", [0.6, 2.0], g9["predicted_interval"]),
        ("Phi* k=4", 2.26, round(L["4"]["phi_star"], 2)),
        ("Phi* k=7", 5.51, round(L["7"]["phi_star"], 2)),
        ("Phi* spread ratio", 2.43, round(G["G12"]["detail"]["phi_star_spread_ratio"], 2)),
        ("k=1 has no bracket", False, "1" in L),
        ("k=1 still closes at lambda_V 5000", 1.0, A["E-k1-lamV5000"]["closed_fraction"]),
        ("A1 R2 linear", 0.955, round(S["A1-baseline"]["r2_linear"], 3)),
        ("A1 R2 exponential", 0.689, round(S["A1-baseline"]["r2_exponential"], 3)),
        ("A4 R2 linear", 0.806, round(S["A4-tension-off-NEGATIVE"]["r2_linear"], 3)),
        ("A4 R2 exponential", 0.938, round(S["A4-tension-off-NEGATIVE"]["r2_exponential"], 3)),
        ("arm count", 36, len(A)),
    ]
    for p, v in ((0, 0.316), (20, 0.409), (40, 0.548), (80, 0.684), (160, 1.000)):
        nm = "B-k4-lamV1" if p == 80 else f"F2-prot{p}"
        rows.append((f"protrusion {p} closed", v, round(A[nm]["closed_fraction"], 3)))
    for gid, exp in (("G1", True), ("G1b", None), ("G2", True), ("G3", True), ("G4", False),
                     ("G5", True), ("G7", True), ("G9", True), ("G10", False), ("G11", True),
                     ("G12", False)):
        rows.append((f"{gid} passed", exp, G[gid]["passed"]))
    # The TALLY is pinned as its own claim. G6 is descriptive and G8 unevaluable; neither is a
    # pass, and summing "not failed" as "passed" is how the handoff came to say 9 pass.
    rows += [
        ("tally: gates passing", 7, sum(1 for g in G.values() if g["passed"] is True)),
        ("tally: gates failing", 3, sum(1 for g in G.values() if g["passed"] is False)),
        ("tally: no verdict (G1b incomplete, G6 descriptive, G8 unevaluable)", 3,
         sum(1 for g in G.values() if g["passed"] is None)),
        ("tally: G1b is not a pass", True, G["G1b"]["passed"] is None),
        ("tally: G6 is not a pass", True, G["G6"]["passed"] is None),
        ("tally: G8 is not a pass", True, G["G8"]["passed"] is None),
        ("G1b verdict", "INCOMPLETE", G["G1b"].get("verdict")),
        ("G1b reported history preserved", True, G["G1b"]["reported_history"]["reported_passed"] is True),
        ("tally: total gates", 13, len(G)),
    ]
    # G1b's DENOMINATOR is pinned, not just its zero. "0 disagreements" without the number of
    # frames actually compared is what let the card claim "every written frame" while the gate
    # silently skipped 720 of 1476. A zero and an empty comparison look identical otherwise.
    cov = G["G1b"]["evaluable"]
    rows += [
        ("G1b frames written", 1476, cov["frames_written"]),
        ("G1b frames comparable", 756, cov["frames_comparable"]),
        ("G1b frames NOT comparable", 720, cov["frames_not_comparable"]),
        ("G1b coverage is partial, not total", True, cov["frames_comparable"] < cov["frames_written"]),
    ]
    # the passive ceiling is 625 nodes at EVERY gap, which is a different fraction each time.
    # Pinning only k=4's 25% would let "subtract 22 points everywhere" survive this checker.
    for k, arm_name, survivors, pct in ((1, "B-k1-lamV0.1", 64, 100.0),
                                        (4, "A1-baseline", 61, 25.0),
                                        (7, "B-k7-lamV0.1", 58, 14.3)):
        g0 = A[arm_name]["gap0"]
        rows.append((f"k={k} survivors", survivors, A[arm_name]["n_cells"]))
        rows.append((f"k={k} passive ceiling nodes", 625, round(g0 - (40000 - survivors * 625))))
        rows.append((f"k={k} passive ceiling % of its gap", pct,
                     round(100 * (g0 - (40000 - survivors * 625)) / g0, 1)))
    rows += [
        ("ARRESTED arms still closing at the horizon", 5,
         sum(1 for r in A.values() if r["state"] == "ARRESTED" and r["horizon"]["trend"] == "still closing")),
        ("ARRESTED arms in total", 13, sum(1 for r in A.values() if r["state"] == "ARRESTED")),
        ("G9 arrested-side arm", "D-k4-J280-lamV2", G["G9"]["detail"]["horizon_caveat"]["arrested_side_arm"]),
        ("G9 arrested side was still closing", "still closing",
         G["G9"]["detail"]["horizon_caveat"]["trend"]["trend"]),
        ("G9 arrested side delta over last 20%", -152,
         round(G["G9"]["detail"]["horizon_caveat"]["trend"]["delta_last_20pct"])),
        ("unwounded sheet cells placed (not the nominal 64)", 65,
         A["A5-unwounded-POSITIVE"]["n_cells"]),
        ("realised mean cell area, nodes (target is 625)", 615.38,
         round(40000 / A["A5-unwounded-POSITIVE"]["n_cells"], 2)),
    ]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    a = ap.parse_args()
    d = json.loads(Path(a.results).read_text())
    rows = claims(d["arms"], {g["id"]: g for g in d["gates"]}, d["closing_curve_shape"])
    bad = [(n, c, g) for n, c, g in rows if c != g]
    for n, c, g in bad:
        print(f"  MISMATCH {n}: card says {c}, results say {g}")
    print(f"{len(rows) - len(bad)}/{len(rows)} card claims match the results")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
