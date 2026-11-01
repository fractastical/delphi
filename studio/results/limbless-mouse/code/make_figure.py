#!/usr/bin/env python3
"""zrs-conservation.png / .svg - conservation track + per-species alignment strip."""
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

sys.path.insert(0, "/tmp/claude-1000/-home-ubuntu-git-morphoswarm/507442cb-0fa9-4ade-b46c-d7b940105d10/scratchpad/limbless/zrs")
from core_trim import read_fasta, smooth  # noqa: E402

BG, INK, TEAL, WARN, RED, GREEN = "#fffdf8", "#0f2238", "#0e7c86", "#9a6700", "#b3261e", "#1d7a46"
GREY = "#8b94a0"

LABEL = {
    "mouse": "mouse (reference)", "human": "human", "chicken": "chicken",
    "lizard": "green anole", "coelacanth": "coelacanth", "elephant_shark": "elephant shark",
    "eryx": "dwarf sand boa", "python": "Burmese python", "king_cobra": "king cobra",
    "rattlesnake": "tiger rattlesnake", "garter_snake": "garter snake",
}
# colour by Kvon 2016 knock-in outcome; grey = not knocked in
PHENO = {
    "mouse": GREEN, "human": GREEN, "coelacanth": GREEN,
    "python": RED, "king_cobra": RED,
    "chicken": GREY, "lizard": GREY, "elephant_shark": GREY,
    "eryx": GREY, "rattlesnake": GREY, "garter_snake": GREY,
}
ORDER = ["mouse", "human", "coelacanth", "chicken", "lizard", "elephant_shark",
         "eryx", "python", "king_cobra", "rattlesnake", "garter_snake"]


def main():
    A = json.load(open("zrs-analysis.json"))
    aln = read_fasta("alignment.fasta")
    cons = A["alignment"]["per_column_conservation"]
    mp = A["alignment"]["per_column_mouse_position"]
    ets = A["ets_sites"]
    e1s, e1e = A["e1_deletion"]["aln_columns"]
    L = len(cons)
    sc = smooth(cons, 21)

    fig = plt.figure(figsize=(14, 7), dpi=100, facecolor=BG)
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 2.5], hspace=0.30,
                          left=0.155, right=0.985, top=0.885, bottom=0.095)

    # ---------------- panel A: conservation ----------------
    ax = fig.add_subplot(gs[0], facecolor=BG)
    ax.fill_between(range(L), sc, color=TEAL, alpha=0.30, linewidth=0)
    ax.plot(range(L), sc, color=TEAL, lw=1.6)
    ax.axvspan(e1s, e1e, color=RED, alpha=0.16, lw=0)
    ax.set_ylim(0.3, 1.02)
    ax.set_xlim(0, L)
    ax.set_ylabel("conservation\n(21-col mean)", color=INK, fontsize=11)
    ax.tick_params(colors=INK, labelsize=10)
    ax.set_xticks([])
    for sp in ("top", "right", "bottom"):
        ax.spines[sp].set_visible(False)
    ax.spines["left"].set_color(GREY)
    ax.annotate("17 bp deletion in every snake\ncarries the ETS1 site",
                xy=((e1s + e1e) / 2, 0.97), xytext=((e1s + e1e) / 2 + 150, 0.62),
                color=RED, fontsize=11, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="->", color=RED, lw=1.6))
    ax.set_title("ZRS limb enhancer: conservation across 11 vertebrates, and the one deletion "
                 "that tracks limblessness",
                 color=INK, fontsize=14.5, fontweight="bold", pad=12, loc="left")

    # ---------------- panel B: alignment strip ----------------
    ax2 = fig.add_subplot(gs[1], facecolor=BG)
    mouse = aln["mouse"]
    n = len(ORDER)
    for r, k in enumerate(ORDER):
        y = n - 1 - r
        row = aln[k]
        # identity strip: dark = matches mouse, pale = mismatch, blank = gap
        xs_m, xs_x = [], []
        for i in range(L):
            if row[i] == "-":
                continue
            (xs_m if row[i] == mouse[i] else xs_x).append(i)
        ax2.bar(xs_x, 0.52, bottom=y - 0.26, width=1.0, color=GREY, alpha=0.40, linewidth=0)
        ax2.bar(xs_m, 0.52, bottom=y - 0.26, width=1.0, color=PHENO[k], alpha=0.80, linewidth=0)
        # ETS1 motif boxes
        for h in ets[k]:
            ax2.add_patch(Rectangle((h["aln_start"], y - 0.34), h["aln_end"] - h["aln_start"] + 1,
                                    0.68, facecolor="none", edgecolor=WARN, lw=1.5, zorder=5))
        ax2.text(-14, y, LABEL[k], ha="right", va="center", color=INK, fontsize=11.5,
                 fontweight="bold" if k == "mouse" else "normal")
        ax2.text(L + 10, y, str(len(ets[k])), ha="left", va="center",
                 color=WARN, fontsize=11, fontweight="bold")

    ax2.axvspan(e1s, e1e, color=RED, alpha=0.16, lw=0, zorder=0)
    ax2.set_ylim(-0.75, n - 0.25)
    ax2.set_xlim(0, L)
    ax2.set_yticks([])
    ax2.text(L + 10, n - 0.30, "ETS1\nsites", ha="left", va="center", color=WARN,
             fontsize=10, fontweight="bold")
    for sp in ("top", "right", "left"):
        ax2.spines[sp].set_visible(False)
    ax2.spines["bottom"].set_color(GREY)

    # x axis in mouse ZRS coordinates
    ticks, labels = [], []
    for i in range(0, L, 100):
        if mp[i] is not None:
            ticks.append(i)
            labels.append(str(mp[i]))
    ax2.set_xticks(ticks)
    ax2.set_xticklabels(labels, color=INK, fontsize=10)
    ax2.set_xlabel("position in the mouse ZRS  (mm10 chr5:29,314,894-29,315,539, the alignable core)",
                   color=INK, fontsize=11)
    ax2.tick_params(colors=INK)

    handles = [
        Line2D([], [], marker="s", ls="", ms=11, color=GREEN,
               label="knock-in into mouse gave NORMAL limbs (Kvon 2016)"),
        Line2D([], [], marker="s", ls="", ms=11, color=RED,
               label="knock-in gave TRUNCATED limbs (Kvon 2016)"),
        Line2D([], [], marker="s", ls="", ms=11, color=GREY, label="not knocked in"),
        Line2D([], [], marker="s", ls="", ms=11, color=GREY, alpha=0.40,
               label="differs from mouse at that column"),
        Line2D([], [], marker="s", ls="", ms=11, mfc="none", mec=WARN, mew=1.6,
               label="ETS1 motif, JASPAR MA0098.3, p<0.0032 (inferred)"),
    ]
    leg = fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.155, -0.004),
                     ncol=3, frameon=False, fontsize=10.5, labelcolor=INK,
                     handletextpad=0.5, columnspacing=1.4)
    for t in leg.get_texts():
        t.set_color(INK)

    fig.text(0.155, 0.925,
             "Correlational, post-hoc, n=4 knock-ins: this is not a predictor. "
             "Sequences re-derived from reference genomes, not the authors' constructs.",
             color=WARN, fontsize=10, style="italic")

    for ext in ("png", "svg"):
        fig.savefig(f"zrs-conservation.{ext}", facecolor=BG, bbox_inches="tight")
    print("wrote zrs-conservation.png and zrs-conservation.svg")


if __name__ == "__main__":
    main()
