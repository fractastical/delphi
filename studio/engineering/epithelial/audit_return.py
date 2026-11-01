"""Independent audit of the returned 240-arm sweep. Does NOT alter the native frozen result.

The native `j-scaling-report.json` says FAIL on a summary-ratio spread. That is the same
statistic I misused locally, where comparing geometric-mean summaries of two overlapping
intervals produced a refutation I had to withdraw (commit 6366882). So the first thing this
audit does is re-derive the verdict on INTERVALS instead, which is a test the native statistic
could fail. It also tests whether the finite horizon could be manufacturing the result.

Everything here is a separately labelled re-reading of the native raw loggers. The native
criterion, its hash and its FAIL are preserved untouched.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import math
import re
from pathlib import Path

ARM = re.compile(r"^S-k(?P<k>\d+)-J(?P<J>[\d.]+)-lamV(?P<lam>[\d.]+)-s(?P<seed>\d+)$")
TOTAL_NODES = 40000
BINARY_PIN = "3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad"


def read_arm(d: Path) -> dict:
    by = collections.defaultdict(float)
    rows = bad = 0
    for r in csv.DictReader((d / "logger.csv").open(), delimiter="\t"):
        rows += 1
        try:
            t, v = float(r["time"]), float(r["cell.volume"])
            if not (math.isfinite(t) and math.isfinite(v)):
                bad += 1
                continue
            by[t] += v
        except (KeyError, TypeError, ValueError):
            bad += 1
    ts = sorted(by)
    g = {t: TOTAL_NODES - by[t] for t in ts}
    i = int(len(ts) * 0.8)
    return dict(closed=any(g[t] <= 0 for t in ts), gap0=g[ts[0]], gap_end=g[ts[-1]],
                # positive => the gap was still shrinking when the horizon ended
                delta_last_20pct=g[ts[i]] - g[ts[-1]], rows=rows, bad=bad,
                closed_fraction=1 - g[ts[-1]] / g[ts[0]] if g[ts[0]] else None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--return-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    S = Path(a.return_dir) / "science"
    native = json.loads((S / "j-scaling-report.json").read_text())
    completeness = json.loads((S / "completeness.json").read_text())
    receipt = json.loads((S / "binary-receipt.json").read_text())

    arms, prov = {}, dict(arm_dirs=0, exit_zero=0, missing_logger=0, rows=0, nonfinite=0,
                          tiff_files=len(list(S.rglob("*.tif"))) + len(list(S.rglob("*.tiff"))))
    for d in sorted(S.iterdir()):
        if not d.is_dir() or not ARM.match(d.name):
            continue
        prov["arm_dirs"] += 1
        ex = (d / "exit.txt")
        if ex.exists() and ex.read_text().strip() == "exit=0":
            prov["exit_zero"] += 1
        if not (d / "logger.csv").exists():
            prov["missing_logger"] += 1
            continue
        r = read_arm(d)
        prov["rows"] += r["rows"]
        prov["nonfinite"] += r["bad"]
        m = ARM.match(d.name)
        arms[(int(m["k"]), float(m["J"]), float(m["lam"]), int(m["seed"]))] = r

    # brackets per (gap, seed, J)
    cells = collections.defaultdict(dict)
    for (k, J, lam, s), r in arms.items():
        cells[(k, s, J)][lam] = r["closed"]
    brackets = {}
    for (k, s, J), lam in cells.items():
        cl = [v for v, c in lam.items() if c]
        ar = [v for v, c in lam.items() if not c]
        if cl and ar and max(cl) < min(ar):
            lo, hi = max(cl), min(ar)
            brackets[(k, s, J)] = dict(lo=lo, hi=hi, lambda_star=math.sqrt(lo * hi),
                                       ratio_interval=[lo / J, hi / J],
                                       ratio_summary=math.sqrt(lo * hi) / J)

    per_gap = {}
    for k in sorted({key[0] for key in brackets}):
        sel = {key: v for key, v in brackets.items() if key[0] == k}
        LO = max(v["ratio_interval"][0] for v in sel.values())
        HI = min(v["ratio_interval"][1] for v in sel.values())
        summ = [v["ratio_summary"] for v in sel.values()]
        # how fast does lambda* actually move with J? fit log(lambda*) ~ exponent*log(J)
        pts = [(math.log(key[2]), math.log(v["lambda_star"])) for key, v in sel.items()]
        n = len(pts)
        mx = sum(p[0] for p in pts) / n
        my = sum(p[1] for p in pts) / n
        sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
        sxx = sum((p[0] - mx) ** 2 for p in pts)
        exponent = sxy / sxx if sxx else None
        Js = sorted({key[2] for key in sel})
        lam_lo = min(v["lambda_star"] for key, v in sel.items() if key[2] == min(Js))
        lam_hi = max(v["lambda_star"] for key, v in sel.items() if key[2] == max(Js))
        # Minimum FEASIBLE cross-cell spread: pick one ratio from each interval to make them as
        # close as possible. If the intervals share a point the spread can be 1; otherwise the
        # cell with the largest lower bound forces r >= LO and the cell with the smallest upper
        # bound forces r <= HI, so no choice does better than LO/HI. This tests the frozen
        # tolerance directly instead of only rejecting exact equality.
        min_feasible_spread = 1.0 if LO <= HI else LO / HI
        # Exponent bounds from the interval ENDPOINTS, not from the summaries. The fitted value
        # above is a regression of geometric bracket summaries and is not a measured exponent.
        lo_at_min = min(brackets[key]["lo"] for key in sel if key[2] == min(Js))
        hi_at_min = max(brackets[key]["hi"] for key in sel if key[2] == min(Js))
        lo_at_max = min(brackets[key]["lo"] for key in sel if key[2] == max(Js))
        hi_at_max = max(brackets[key]["hi"] for key in sel if key[2] == max(Js))
        ratio_lo, ratio_hi = lo_at_max / hi_at_min, hi_at_max / lo_at_min
        lj = math.log(max(Js) / min(Js))
        exp_bounds = [math.log(ratio_lo) / lj, math.log(ratio_hi) / lj]

        per_gap[k] = dict(
            min_feasible_spread=min_feasible_spread,
            frozen_tolerance=2.0,
            min_feasible_spread_exceeds_tolerance=min_feasible_spread > 2.0,
            lambda_star_interval_at_min_J=[lo_at_min, hi_at_min],
            lambda_star_interval_at_max_J=[lo_at_max, hi_at_max],
            lambda_star_factor_feasible_range=[ratio_lo, ratio_hi],
            exponent_feasible_bounds=exp_bounds,
            exponent_note="bounds derived from bracket ENDPOINTS. The fitted value below is a "
                          "regression of geometric bracket SUMMARIES, not a measured threshold "
                          "exponent.",
            cells=n, j_range=[min(Js), max(Js)], j_factor=max(Js) / min(Js),
            ratio_interval_intersection=([LO, HI] if LO <= HI else None),
            intervals_consistent_with_a_constant_ratio=(LO <= HI),
            summary_ratio_spread=max(summ) / min(summ),
            lambda_star_at_min_J=lam_lo, lambda_star_at_max_J=lam_hi,
            lambda_star_factor=lam_hi / lam_lo,
            fitted_exponent_lambda_star_vs_J=exponent,
            predicted_exponent=1.0)

    # Late-window endpoint delta, gap(800) - gap(1000), positive = the gap was still shrinking.
    # Reported PER ARM. An earlier version averaged the deltas across seeds at each lambda and
    # assigned "still closing" from the group mean, which let a shrinking arm vanish inside a
    # flat mean: at k=4, J=560, lambda_V=12.8 the three seeds are -3, -16, +22 and the mean is
    # +1.0, so seed s3 shrank 22 nodes while the group read as flat. Seed means are kept, but
    # only beside the per-arm values and explicitly labelled as such.
    censor = {}
    for k in sorted(per_gap):
        Jmax = per_gap[k]["j_range"][1]
        lv = collections.defaultdict(list)
        for (kk, J, lam, s), r in arms.items():
            if kk == k and J == Jmax and not r["closed"]:
                lv[lam].append((s, r["delta_last_20pct"]))
        censor[k] = {str(lam): dict(
            arms_not_closed=len(v),
            per_arm_delta={f"s{s}": d for s, d in sorted(v)},
            arms_still_shrinking=sum(1 for _, d in v if d > 1),
            seed_mean_delta=sum(d for _, d in v) / len(v),
            seed_mean_reads_as_still_closing=(sum(d for _, d in v) / len(v)) > 1,
            mean_masks_a_shrinking_arm=(any(d > 1 for _, d in v)
                                        and (sum(d for _, d in v) / len(v)) <= 1))
            for lam, v in sorted(lv.items())}
    by_J = {}
    for k in sorted(per_gap):
        by_J[k] = {}
        for J in sorted({key[1] for key in arms if key[0] == k}):
            ar = [r for (kk, JJ, lam, s), r in arms.items() if kk == k and JJ == J and not r["closed"]]
            by_J[k][str(J)] = dict(arms_not_closed=len(ar),
                                   arms_still_shrinking=sum(1 for r in ar if r["delta_last_20pct"] > 1),
                                   unit="individual arms, NOT parameter levels and NOT seed means")
        seq = [by_J[k][str(J)]["arms_still_shrinking"] for J in sorted({key[1] for key in arms if key[0] == k})]
        by_J[k]["monotone_in_J"] = (seq == sorted(seq) or seq == sorted(seq, reverse=True))

    out = dict(
        schema="frontier.epithelial-sweep-audit.v1",
        status="INDEPENDENT RE-READING. The native frozen criterion, its hash and its FAIL are "
               "preserved unchanged; nothing here edits or replaces them.",
        native=dict(verdict=native["verdict"], criterion_sha256=native["criterion"]["criterion_sha256"],
                    tolerance_ratio=native["criterion"]["tolerance_ratio"], counts=native["counts"],
                    per_gap={k: dict(spread=v["spread"], within_tolerance=v["within_tolerance"])
                             for k, v in native["per_gap"].items()},
                    completeness=dict(complete=completeness["complete"],
                                      complete_arms=completeness["complete_arms"],
                                      declared=completeness["declared_arms"])),
        provenance=dict(**prov, binary_sha256=receipt["sha256"],
                        binary_matches_pin=receipt["sha256"] == BINARY_PIN,
                        lattice_frames_present=prov["tiff_files"] > 0,
                        tissue_shape_movie_renderable=prov["tiff_files"] > 0,
                        logger_carries_cell_centres_and_volumes=True,
                        spatial_information_note="the loggers carry per-cell centre coordinates "
                                                 "and volumes. What is absent is the lattice "
                                                 "frames that define cell shapes and the wound "
                                                 "boundary, so no tissue-shape movie can be made "
                                                 "from this return."),
        interval_audit=per_gap,
        horizon_audit=dict(
            unit="per arm. Seed means appear only as an explicitly labelled companion field.",
            scope="gap(800) - gap(1000) at sampled times <= 1000 model units. A post-hoc "
                  "endpoint delta: not a trend test, not proof of permanent arrest, and not a "
                  "bound on future closure in a stochastic CPM.",
            highest_J_arms_proportionality_requires_to_close=censor,
            arrested_still_shrinking_by_J=by_J),
        brackets={f"k{k}-s{s}-J{J:g}": v for (k, s, J), v in sorted(brackets.items())},
    )
    Path(a.out).write_text(json.dumps(out, indent=1, default=float))
    print(f"native verdict {out['native']['verdict']}; provenance "
          f"{prov['exit_zero']}/{prov['arm_dirs']} exit 0, {prov['nonfinite']} non-finite of "
          f"{prov['rows']:,} rows, {prov['tiff_files']} TIFF")
    for k, v in per_gap.items():
        print(f"  k={k}: intervals {'OVERLAP' if v['intervals_consistent_with_a_constant_ratio'] else 'DISJOINT'}"
              f"; J x{v['j_factor']:.0f} -> lambda* x{v['lambda_star_factor']:.2f}"
              f"; fitted exponent {v['fitted_exponent_lambda_star_vs_J']:.3f} vs predicted 1.0")


if __name__ == "__main__":
    main()
