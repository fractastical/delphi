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
        per_gap[k] = dict(
            cells=n, j_range=[min(Js), max(Js)], j_factor=max(Js) / min(Js),
            ratio_interval_intersection=([LO, HI] if LO <= HI else None),
            intervals_consistent_with_a_constant_ratio=(LO <= HI),
            summary_ratio_spread=max(summ) / min(summ),
            lambda_star_at_min_J=lam_lo, lambda_star_at_max_J=lam_hi,
            lambda_star_factor=lam_hi / lam_lo,
            fitted_exponent_lambda_star_vs_J=exponent,
            predicted_exponent=1.0)

    # could the finite horizon be manufacturing the result? Proportionality requires the
    # highest-J arms above the observed bracket to be censored rather than genuinely arrested.
    censor = {}
    for k in sorted(per_gap):
        Jmax = per_gap[k]["j_range"][1]
        need = {}
        for (kk, J, lam, s), r in arms.items():
            if kk == k and J == Jmax and not r["closed"]:
                need.setdefault(lam, []).append(r["delta_last_20pct"])
        censor[k] = {str(lam): dict(mean_delta_last_20pct=sum(v) / len(v),
                                    still_closing=(sum(v) / len(v)) > 1)
                     for lam, v in sorted(need.items())}
    by_J = {}
    for k in sorted(per_gap):
        by_J[k] = {}
        for J in sorted({key[1] for key in arms if key[0] == k}):
            ar = [r for (kk, JJ, lam, s), r in arms.items() if kk == k and JJ == J and not r["closed"]]
            by_J[k][str(J)] = dict(arrested=len(ar),
                                   still_closing=sum(1 for r in ar if r["delta_last_20pct"] > 1))

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
                        spatial_states_present=prov["tiff_files"] > 0,
                        movie_renderable=prov["tiff_files"] > 0),
        interval_audit=per_gap,
        horizon_audit=dict(highest_J_arms_proportionality_requires_to_close=censor,
                           arrested_still_closing_by_J=by_J),
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
