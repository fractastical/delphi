"""Figure from the committed sweep artifacts only (no new simulation). Evidence kind: simulated; coefficients are design assumptions."""
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main(d):
    d = Path(d)
    rows = list(csv.DictReader(open(d / "designs.csv")))
    ts = json.loads((d / "timeseries.json").read_text())
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
    for ar in sorted({float(r["AR"]) for r in rows}):
        sub = [r for r in rows if float(r["AR"]) == ar]
        ax[0].scatter([float(r["WL"]) for r in sub], [float(r["range_q50"]) for r in sub], s=6, label=f"AR {ar:g}")
    ax[0].set_xscale("log"); ax[0].set_yscale("log"); ax[0].set_xlabel("wing loading m g/S (N/m^2)"); ax[0].set_ylabel("median glide range from 1 m (m), MC")
    ax[0].legend(fontsize=7); ax[0].set_title("range vs wing loading (mass does not enter)", fontsize=9)
    par = [r for r in rows if r["pareto"] == "True"]
    sc = ax[1].scatter([float(r["sink_eq_ms"]) for r in par], [float(r["range_q10"]) for r in par], c=[float(r["m"]) for r in par], s=18)
    ax[1].set_xlabel("equilibrium sink rate (m/s)"); ax[1].set_ylabel("q10 glide range (m)"); fig.colorbar(sc, ax=ax[1], label="mass (kg)")
    ax[1].set_title(f"Pareto set ({len(par)} of {len(rows)} designs)", fontsize=9)
    for name, s in ts.items():
        ax[2].plot(s["x_m"], s["h_m"], label=f"{name}: m={s['design']['m']:.3g} kg, AR={s['design']['AR']:g}")
    ax[2].set_xlabel("distance x (m)"); ax[2].set_ylabel("height above water (m)"); ax[2].legend(fontsize=6); ax[2].set_title("nominal trajectories", fontsize=9)
    fig.suptitle("SIMULATED point-mass glide; coefficients are design assumptions; no biological feasibility, no tissue coupling", fontsize=9)
    fig.tight_layout(); fig.savefig(d / "figure.png", dpi=130)


if __name__ == "__main__":
    main(sys.argv[1])
