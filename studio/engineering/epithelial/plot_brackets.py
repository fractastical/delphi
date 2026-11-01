"""Plot the measured threshold brackets from sweep-audit.json. No simulation, no movie.

The data are INTERVALS, so the marks are intervals. Drawing a point per cell would be the
same error this whole result turns on: a geometric-mean summary of a bracket is not a
measurement, and reading a refutation off summaries is what had to be withdrawn at 6366882.

Left panel  : the lambda_V bracket for every (gap, J, seed), against the proportionality the
              rule predicts, anchored on the lowest-J bracket so the prediction is not fitted.
Right panel : the same brackets as lambda*/J ratio intervals, against a band whose height is
              the frozen tolerance of 2. A passing set must fit inside one such band.

Colour is categorical by gap size and is never the only encoding: each gap also carries its
own marker shape and a direct label. Palette validated for light and dark surfaces with the
dataviz validator (all six checks pass; worst adjacent CVD dE 24.7 protan).
"""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

KEY = re.compile(r"^k(?P<k>\d+)-s(?P<s>\d+)-J(?P<J>[\d.]+)$")
THEME = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", grid="#dddcd8",
                  series={4: "#2a78d6", 7: "#eb6834"}, band="#8e8d88"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", grid="#3a3a38",
                 series={4: "#3987e5", 7: "#d95926"}, band="#9a998f"),
}
MARK = {4: "o", 7: "s"}


def draw(audit: dict, mode: str, out_png: Path, out_svg: Path) -> None:
    T = THEME[mode]
    cells = []
    for key, v in audit["brackets"].items():
        m = KEY.match(key)
        cells.append(dict(k=int(m["k"]), s=int(m["s"]), J=float(m["J"]), **v))
    gaps = sorted({c["k"] for c in cells})

    fig, ax = plt.subplots(1, 2, figsize=(12.4, 5.4), dpi=160, facecolor=T["surface"])
    for a in ax:
        a.set_facecolor(T["surface"])
        a.set_xscale("log")
        a.set_yscale("log")
        a.grid(True, which="major", color=T["grid"], lw=0.8, alpha=0.9)
        a.grid(True, which="minor", color=T["grid"], lw=0.5, alpha=0.45)
        a.set_axisbelow(True)
        for sp in a.spines.values():
            sp.set_color(T["grid"])
        a.tick_params(colors=T["ink2"], labelsize=9)
        a.set_xlabel("cell–medium contact energy  J  (model units)", color=T["ink2"], fontsize=10)

    # ---- left: lambda_V brackets, against the predicted proportionality -------------------
    for k in gaps:
        c = T["series"][k]
        sel = [x for x in cells if x["k"] == k]
        for x in sel:
            off = 1.0 + 0.055 * (x["s"] - 2)                 # seeds nudged apart, not stacked
            ax[0].plot([x["J"] * off] * 2, [x["lo"], x["hi"]], color=c, lw=2.0,
                       solid_capstyle="butt", zorder=3)
            ax[0].plot([x["J"] * off] * 2, [x["lo"], x["hi"]], MARK[k], color=c, ms=4.5,
                       mec=T["surface"], mew=0.8, zorder=4)
        Js = sorted({x["J"] for x in sel})
        anchor = max(x["lambda_star"] for x in sel if x["J"] == Js[0])
        xs = [Js[0], Js[-1]]
        ax[0].plot(xs, [anchor, anchor * Js[-1] / Js[0]], ls=(0, (5, 3)), lw=1.8,
                   color=c, alpha=0.55, zorder=2)
        ax[0].annotate(f"gap k={k}", (Js[-1], max(x["hi"] for x in sel if x["J"] == Js[-1])),
                       textcoords="offset points", xytext=(9, -2), color=c, fontsize=10,
                       fontweight="bold", va="center")
    lo0 = min(x["lo"] for x in cells) ; hi0 = max(x["hi"] for x in cells)
    ax[0].set_ylim(lo0 / 1.6, hi0 * 9.0)          # headroom for the note, never over a mark
    ax[0].set_ylabel("closure threshold bracket in $\\lambda_V$", color=T["ink2"], fontsize=10)
    ax[0].set_title("Measured brackets vs the predicted proportionality",
                    color=T["ink"], fontsize=11, pad=9, loc="left")
    ax[0].annotate("dashed: $\\lambda^* \\propto J$, anchored on the lowest-J bracket (not fitted)",
                   (0.015, 0.965), xycoords="axes fraction", color=T["ink2"], fontsize=9,
                   va="top")

    # ---- right: ratio intervals against a band of the frozen tolerance -------------------
    for k in gaps:
        c = T["series"][k]
        sel = [x for x in cells if x["k"] == k]
        for x in sel:
            off = 1.0 + 0.055 * (x["s"] - 2)
            lo, hi = x["ratio_interval"]
            ax[1].plot([x["J"] * off] * 2, [lo, hi], color=c, lw=2.0,
                       solid_capstyle="butt", zorder=3)
            ax[1].plot([x["J"] * off] * 2, [lo, hi], MARK[k], color=c, ms=4.5,
                       mec=T["surface"], mew=0.8, zorder=4)
        g = audit["interval_audit"][str(k)]
        U = min(x["ratio_interval"][1] for x in sel)
        tol = g["frozen_tolerance"]
        ax[1].axhspan(U, U * tol, color=T["band"], alpha=0.16, zorder=1)
        ax[1].annotate(f"gap k={k}: minimum feasible spread "
                       f"{g['min_feasible_spread']:.0f}×   (tolerance {tol:.0f}×)",
                       (0.015, 0.955 - 0.062 * (gaps.index(k) + 1)), xycoords="axes fraction",
                       color=c, fontsize=9.5, fontweight="bold", va="top")
    lo1 = min(x["ratio_interval"][0] for x in cells) ; hi1 = max(x["ratio_interval"][1] for x in cells)
    ax[1].set_ylim(lo1 / 1.6, hi1 * 9.0)
    ax[1].set_ylabel("$\\lambda^*/J$  (the quantity the rule says is constant)",
                     color=T["ink2"], fontsize=10)
    ax[1].set_title("A passing set must fit inside one tolerance band",
                    color=T["ink"], fontsize=11, pad=9, loc="left")
    ax[1].annotate("shaded: a band 2× tall — the frozen tolerance, one per gap",
                   (0.015, 0.965), xycoords="axes fraction", color=T["ink2"], fontsize=9,
                   va="top")

    handles = [Line2D([], [], color=T["series"][k], marker=MARK[k], lw=2.0, ms=5.5,
                      label=f"gap k={k}  ({'2 124' if k == 4 else '3 717'} µm², 30 arms)")
               for k in gaps]
    handles.append(Line2D([], [], color=T["ink2"], ls=(0, (5, 3)), lw=1.8,
                          label="predicted $\\lambda^* \\propto J$ (drawn per gap, in that gap's colour)"))
    leg = fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False,
                     fontsize=9.5, bbox_to_anchor=(0.5, 0.005))
    for t in leg.get_texts():
        t.set_color(T["ink2"])

    fig.suptitle("Epithelial gap closure: measured threshold brackets over a ×16 range in J",
                 color=T["ink"], fontsize=13, x=0.012, ha="left", y=0.975)
    fig.text(0.012, 0.925,
             "240 frozen CPM arms, 30 bracketed cells (2 gaps × 5 J × 3 seeds). Bars are the measured "
             "brackets, not point estimates.\nClosure is defined by StopTime 1000; the long-horizon "
             "threshold is unknown. Model units throughout — no biological calibration.",
             color=T["ink2"], fontsize=9, ha="left", va="top", linespacing=1.5)
    fig.tight_layout(rect=[0, 0.055, 1, 0.855])
    for p in (out_png, out_svg):
        fig.savefig(p, facecolor=T["surface"])
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    audit = json.loads(Path(a.audit).read_text())
    d = Path(a.out_dir)
    d.mkdir(parents=True, exist_ok=True)
    for mode in ("light", "dark"):
        draw(audit, mode, d / f"threshold-brackets-{mode}.png", d / f"threshold-brackets-{mode}.svg")
        print(d / f"threshold-brackets-{mode}.png")


if __name__ == "__main__":
    main()
