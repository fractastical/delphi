"""Render the ideal-geometry oxygen bound and its model-only size response."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, Rectangle


def main() -> None:
    out = Path("artifacts/oxygen-diffusion-rule/geometry-control.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(2, 2, figsize=(14, 8.5), gridspec_kw={"height_ratios": [0.9, 1.2]})
    fig.patch.set_facecolor("#f6f8fb")
    for ax in axes.flat:
        ax.set_facecolor("#f6f8fb")

    # Idealized sphere cross-section; the curve below is the center prediction.
    ax = axes[0, 0]
    ax.set_aspect("equal")
    ax.add_patch(Circle((0.0, 0.0), 1.0, fill=False, lw=3, color="#167c80"))
    ax.plot([0.0, 1.0], [0.0, 0.0], color="#174e66", lw=2, marker="o", markevery=[0, 1])
    ax.text(-0.32, -0.28, "center C(0)", ha="center", va="top", fontsize=10)
    ax.text(0.57, -0.16, "R", color="#174e66", fontsize=13, weight="bold")
    ax.text(0.72, 0.62, "supplied boundary\nC(R) = C₀", ha="center", fontsize=10)
    ax.set_title("Sphere · supplied outer boundary", loc="left", weight="bold", fontsize=13)
    ax.set_xlim(-1.25, 1.35); ax.set_ylim(-1.2, 1.2); ax.axis("off")

    # Half of a symmetric slab, from the no-flux center plane to the supplied face.
    ax = axes[0, 1]
    ax.add_patch(Rectangle((0, 0.15), 1.0, 0.55, facecolor="#d8eeee", edgecolor="#167c80", lw=2))
    ax.plot([0, 0], [0.08, 0.78], color="#174e66", lw=2, ls="--")
    ax.annotate("L", xy=(0.5, 0.04), ha="center", va="top", fontsize=13, weight="bold")
    ax.annotate("no-flux center", xy=(0.0, 0.72), xytext=(0.02, 1.0),
                arrowprops={"arrowstyle": "->", "color": "#174e66"}, fontsize=10)
    ax.annotate("supplied face\nC(L) = C₀", xy=(1.0, 0.68), xytext=(0.72, 1.0),
                arrowprops={"arrowstyle": "->", "color": "#174e66"}, fontsize=10)
    ax.text(0.5, 0.42, "slab half-domain", ha="center", va="center", fontsize=10)
    ax.set_title("Slab half-thickness · one-sided supply", loc="left", weight="bold", fontsize=13)
    ax.set_xlim(-0.18, 1.22); ax.set_ylim(-0.12, 1.3); ax.axis("off")

    # Same exact center-oxygen response, expressed against each geometry's own threshold.
    x = np.linspace(0, 1.35, 300)
    for ax, geometry, equation in [
        (axes[1, 0], "sphere", "Ccenter / C₀ = 1 − aR²/(6DC₀)"),
        (axes[1, 1], "slab", "Ccenter / C₀ = 1 − aL²/(2DC₀)"),
    ]:
        ax.axvspan(1.0, x.max(), color="#f4c8c3", alpha=0.45, label="outside nonnegative model domain")
        ax.plot(x, 1 - x, color="#174e66", lw=3)
        ax.axhline(0, color="#444", lw=1)
        ax.axvline(1, color="#bf4438", ls="--", lw=1.5)
        ax.scatter([0, 1], [1, 0], color=["#167c80", "#bf4438"], zorder=4)
        ax.set_title(f"{geometry.capitalize()} center response", loc="left", weight="bold", fontsize=13)
        ax.set_xlabel("squared size / squared diffusion-limit size")
        ax.set_ylabel("predicted center oxygen / boundary oxygen")
        ax.set_xlim(0, x.max()); ax.set_ylim(-0.38, 1.08); ax.grid(alpha=0.22)
        ax.text(0.04, 0.09, equation, transform=ax.transAxes, fontsize=10,
                bbox={"boxstyle": "round,pad=.3", "facecolor": "white", "alpha": 0.88, "edgecolor": "#aab6c2"})
        ax.text(1.015, 0.87, "limit", color="#9b2e25", fontsize=10)

    fig.suptitle("A conditional oxygen-transport bound—not a viability result", fontsize=19, weight="bold", x=0.05, ha="left")
    fig.text(0.05, 0.015,
             "Steady diffusion · constant consumption · no perfusion · parameters unknown in both reuse projects. "
             "Negative continuation flags an out-of-domain size; it is not physical negative oxygen. "
             "Slab is a derived 1-D analogue. No repair, cell-survival, or organism claim.",
             fontsize=9.5, color="#293947", ha="left")
    fig.tight_layout(rect=(0.03, 0.055, 0.99, 0.92), h_pad=1.5, w_pad=1.4)
    fig.savefig(out, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    print(out)


if __name__ == "__main__":
    main()
