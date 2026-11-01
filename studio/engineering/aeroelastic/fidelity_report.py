"""Readable state of the returned fidelity ladder: a bounded rigid-lattice diagnostic and descriptive figures.

Posthoc and descriptive only. Nothing here changes a frozen criterion, a native status or a decision; the
classifications shown are the native summary's, which the independent audit recomputed and agreed with.

    python -m engineering.aeroelastic.fidelity_report probe --output RETURNED_OUTPUT_DIR   # pinned NumPy
    python -m engineering.aeroelastic.fidelity_report figures --output RETURNED_OUTPUT_DIR # needs matplotlib
"""

import argparse
import json
import textwrap
from hashlib import sha256
from pathlib import Path

import numpy as np

from .fidelity import FID, fixed_area_CL, fprotocol, grid
from .model import dump, setup

LADDER = ["main", "fine", "l32x8", "l36x9", "l64x16"]
SPAN_ONLY = [(16, 8), (24, 8), (32, 8), (36, 8), (48, 8), (64, 8)]
CHORD_ONLY = [(32, 4), (32, 6), (32, 9), (32, 12), (32, 16)]
EFFECTS = {
    "CL_rigid": "rigid CL",
    "dCL_one_way_minus_rigid": "ΔCL one-way − rigid",
    "dCL_two_way_minus_one_way": "ΔCL two-way − one-way",
}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def rigid_CL(fins, normals="source"):
    lattices = {}
    for name, fin in fins.items():
        lattice = dict(fin["lattice"])
        if normals == "flat":
            lattice["N"] = np.tile(fin["geometry"]["n_up"], (len(lattice["N"]), 1))
        lattices[name] = lattice
    return fixed_area_CL(fins, lattices, 20.0)[0]


def leg_clearance(fins):
    """Closest approach of any other horseshoe's +x trailing leg to each control point, per receiving span width."""
    A, B, C = (np.vstack([f["lattice"][k] for f in fins.values()]) for k in "ABC")
    nearest = np.full(len(C), np.inf)
    for start in (A, B):
        d = C[:, None, :] - start[None, :, :]
        d[..., 0] -= np.clip(d[..., 0], 0, None)
        distance = np.linalg.norm(d, axis=2)
        np.fill_diagonal(distance, np.inf)
        nearest = np.minimum(nearest, distance.min(axis=1))
    return nearest / np.linalg.norm(B - A, axis=1)


def probe(output):
    """Which part of the lattice makes rigid CL non-monotone? Rigid solves only, no coupled arm is rerun."""
    fp = fprotocol()
    ladder = {}
    for mesh in LADDER:
        fins = setup(*grid(fp, mesh))
        returned = json.loads(
            (output / "arms" / f"chi0.8-u20-{mesh}-rigid" / "result.json").read_text()
        )["iterations"][0]["CL_on_fixed_source_area"]
        area = sum(f["lattice"]["area"].sum() for f in fins.values()) / sum(
            f["source"]["area_flat_m2"] for f in fins.values()
        )
        clearance = leg_clearance(fins)
        ladder[mesh] = {
            "lattice": dict(zip(["span", "chord"], grid(fp, mesh), strict=True)),
            "CL_returned_rigid_arm": returned,
            "CL_source_normals_recomputed": rigid_CL(fins),
            "CL_flat_plane_normals": rigid_CL(fins, "flat"),
            "lattice_over_source_area": float(area),
            "min_leg_clearance_per_span_width": float(clearance.min()),
        }
    refinement = [
        {"span": ns, "chord": nc, "CL_rigid": rigid_CL(setup(ns, nc))}
        for ns, nc in SPAN_ONLY + CHORD_ONLY
    ]
    result = {
        "schema": "frontier.aeroelastic.fidelity-ladder-diagnostic/1",
        "status": "posthoc diagnostic after the return; not frozen, not a criterion, changes no decision",
        "question": "Why is rigid CL itself non-monotone across the ladder lattices?",
        "returned_output": str(output),
        "code_sha256": digest(__file__),
        "ladder": ladder,
        "separate_refinement": refinement,
        "scope": "Rigid fixed-alpha unit VLM solves of the existing solver on the existing source panels; "
        "no coupled arm, beam or glide is recomputed, and no lattice scheme is changed.",
    }
    dump(FID / "ladder-diagnostic.json", result)
    return result


def figures(output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    summary = json.loads((output / "summary.json").read_text())
    diagnostic = json.loads((FID / "ladder-diagnostic.json").read_text())
    fp = fprotocol()
    panels = {m: 4 * np.prod(grid(fp, m)) for m in LADDER}
    paths = {
        "T2 (r = 2)": ["main", "l32x8", "l64x16"],
        "T1.5 (r = 1.5)": ["main", "fine", "l36x9"],
    }
    colours = dict(zip(paths, ["#2a78d6", "#eb6834"], strict=True))
    ink, muted = "#0b0b0b", "#52514e"

    fig, axes = plt.subplots(3, 3, figsize=(14, 11.5), constrained_layout=True)
    for row, context in zip(axes, summary["contexts"], strict=True):
        label = f"χ {context['compliance']}, {context['speed_m_s']:g} m/s"
        for ax, (key, title) in zip(row, EFFECTS.items(), strict=True):
            effect = context["effects"][key]
            series = effect["series"]
            for name, members in paths.items():
                ax.plot(
                    [panels[m] for m in members],
                    [series[m] for m in members],
                    "-o",
                    lw=2,
                    ms=8,
                    color=colours[name],
                    label=name,
                    mec="white",
                    mew=1.5,
                )
            ax.set_xscale("log")
            ax.set_xticks(
                list(panels.values()),
                [f"{m} ({v})" for m, v in panels.items()],
                fontsize=7.5,
                rotation=35,
                ha="right",
                rotation_mode="anchor",
            )
            ax.minorticks_off()
            ax.margins(x=0.08, y=0.18)
            ax.yaxis.set_major_formatter(
                matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.4g}")
            )
            ax.grid(alpha=0.25)
            ax.tick_params(labelsize=8, colors=muted)
            reasons = "\n".join(textwrap.wrap("; ".join(effect["reasons"]), 48))
            ax.set_title(
                f"{label}: {title}\nnative status {effect['status']}\n{reasons}",
                fontsize=8.5,
                color=ink,
                loc="left",
            )
        row[0].set_ylabel("value on fixed source area", color=ink)
    for ax in axes[-1]:
        ax.set_xlabel("total VLM panels, four fins (lattice)", color=ink)
    axes[0][0].legend(fontsize=8, frameon=False, loc="lower left")
    decisions = sorted(
        {
            (
                c["decision"]["bending"]["decision"],
                c["decision"]["feedback"]["decision"],
            )
            for c in summary["contexts"]
        }
    )
    verdict = "; ".join(f"bending {b}, feedback {f}" for b, f in decisions)
    fig.suptitle(
        f"Returned fidelity ladder: {summary['valid_arms']} of {summary['declared_arms']} arms valid, "
        "actual values per lattice, frozen criteria unchanged\n"
        f"Native decisions in all {len(summary['contexts'])} contexts: {verdict}",
        fontsize=11,
        color=ink,
    )
    ladder_png = FID / "fidelity-ladder.png"
    fig.savefig(ladder_png, dpi=120, facecolor="white")
    plt.close(fig)

    fig, (span, chord) = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    rows = diagnostic["separate_refinement"]
    for ax, pick, varied, title in [
        (span, rows[: len(SPAN_ONLY)], "span", "span strips refined, 8 chordwise"),
        (
            chord,
            rows[len(SPAN_ONLY) :],
            "chord",
            "chordwise panels refined, 32 span strips",
        ),
    ]:
        ax.plot(
            [r[varied] for r in pick],
            [r["CL_rigid"] for r in pick],
            "-o",
            lw=2,
            ms=8,
            color=colours["T2 (r = 2)"],
            mec="white",
            mew=1.5,
        )
        ax.set_xlabel(f"{varied} count", color=ink)
        ax.set_title(f"Rigid CL, {title}", fontsize=10, color=ink, loc="left")
        ax.grid(alpha=0.25)
        ax.tick_params(labelsize=8, colors=muted)
    span.set_ylabel("rigid CL on fixed source area", color=ink)
    fig.suptitle(
        "Posthoc diagnostic: rigid CL is non-monotone under span refinement and drifts with growing steps "
        "under chord refinement\n(flat-plane normals change CL by < 4e-6; planform area and trailing-leg "
        "clearance do not explain it; mechanism not identified)",
        fontsize=9.5,
        color=ink,
    )
    diagnostic_png = FID / "ladder-diagnostic.png"
    fig.savefig(diagnostic_png, dpi=120, facecolor="white")
    plt.close(fig)

    dump(
        FID / "fidelity-figures.provenance.json",
        {
            "schema": "frontier.aeroelastic.fidelity-figures/1",
            "scope": "Posthoc descriptive plots of actual returned values; statuses and decisions are the native "
            "summary's, recomputed and agreed by the independent audit; no new threshold",
            "inputs": [
                {"path": str(p), "sha256": digest(p)}
                for p in [output / "summary.json", FID / "ladder-diagnostic.json"]
            ],
            "code_sha256": digest(__file__),
            "outputs": [
                {"path": str(p), "sha256": digest(p), "bytes": p.stat().st_size}
                for p in [ladder_png, diagnostic_png]
            ],
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["probe", "figures"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    probe(args.output) if args.action == "probe" else figures(args.output)


if __name__ == "__main__":
    main()
