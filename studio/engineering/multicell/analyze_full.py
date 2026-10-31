"""Full-horizon comparison of three recovered Morpheus arms (logger.csv only; no spatial frames exist)."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze  # noqa: E402

ARMS = ("baseline", "nofeedback", "seed2")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    parts, out = Path(a.parts), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    res, series = {}, {}
    for n in ARMS:
        d = analyze.load(parts / n)
        t = sorted(d["cell_count"])
        series[n] = [(x, d["cell_count"][x]) for x in t]
        vols = [r["cell.volume"] for r in d["recs"][d["reached_t"]]]
        res[n] = {"exit": (parts / n / "exit.txt").read_text().strip(), "reached_t": d["reached_t"],
                  "rows": sum(len(v) for v in d["recs"].values()), "final_cells": d["n_final"],
                  "n_division_event_times": len(d["division_event_times"]),
                  "first_division_events": d["division_event_times"][:8],
                  "final_total_volume": sum(vols), "max_g_l": d["max_g_l"], "max_cdk1": d["max_cdk1"],
                  "cells_at": {str(h): analyze.count_at(d, h) for h in (0.456, 0.5, 1.0, 1.5, 2.0)},
                  "logger_sha256": hashlib.sha256((parts / n / "logger.csv").read_bytes()).hexdigest()}
    (out / "full_summary.json").write_text(json.dumps(res, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6, 3.6))
    for n, s in series.items():
        ax.step([x for x, _ in s], [c for _, c in s], where="post", label=n)
    ax.set_yscale("log")
    ax.set_xlabel("t (example units)")
    ax.set_ylabel("cells")
    ax.set_title("Morpheus cell-cycle/CPM/PDE example, full horizon (generic, uncalibrated)", fontsize=8)
    ax.legend()
    fig.tight_layout()
    fig.savefig(out / "cell_count.png", dpi=130)
    print(json.dumps({n: (r["final_cells"], r["reached_t"], r["cells_at"]) for n, r in res.items()}))


if __name__ == "__main__":
    main()
