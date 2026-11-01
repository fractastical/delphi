# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "matplotlib"]
# ///
"""Is the 120-degree pull a CPSAM artefact or a Cellpose artefact?

Scores every mask under results/segmenter-compare/<segmenter>/ (written by segment_multi.py)
plus the published Nebius CPSAM masks with analyze.measure, and compares them with the
ground truth for the synthetic tilings and with each other for the tissue images. Writes
results/segmenter-compare/summary.json and segmenter-compare.png.

    uv run claim-sources/cell-geometry/compare_segmenters.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analyze import load_mask, measure, summarize  # noqa: E402

ROOT = HERE / "results" / "segmenter-compare"
SYN = HERE / "inputs" / "synthetic"
KEYS = ["cells", "junctions_measured", "angle_sd", "frac_all_within_15deg", "frac_T_like", "frac_hexagons", "mean_neighbours"]


def score(mask_path):
    try:
        return summarize(measure(load_mask(mask_path)))
    except Exception as e:  # a segmenter that found almost nothing
        return {"error": str(e)}


def main():
    manifest = json.loads((SYN / "manifest.json").read_text())
    sources = json.loads((HERE / "inputs" / "sources.json").read_text())
    segmenters = sorted(p.name for p in ROOT.iterdir() if p.is_dir())
    summary = {"method": "Same inputs segmented by several Cellpose checkpoints (segment_multi.py, GPU) and by "
                         "CPSAM v2 on Nebius (published masks); all scored with analyze.measure. For synthetic "
                         "tilings bias = segmented minus truth.",
               "segmenters": segmenters + ["nebius-cpsam-v2"], "truth": {}, "synthetic": {}, "tissue": {}}

    truths = {}
    for name in sorted({m["tiling"] for m in manifest.values()}):
        truths[name] = summarize(measure(np.array(Image.open(SYN / f"{name}.truth.png")).astype(np.int64)))
        summary["truth"][name] = {k: truths[name].get(k) for k in KEYS}

    def add(section, iid, seg, mask_path, truth=None):
        if not mask_path.exists():
            return
        s = score(mask_path)
        row = {k: s.get(k) for k in KEYS}
        if truth:
            row["bias"] = {k: round(s[k] - truth[k], 3) for k in ["angle_sd", "frac_all_within_15deg", "frac_T_like", "frac_hexagons", "mean_neighbours"]
                           if isinstance(s.get(k), (int, float)) and isinstance(truth.get(k), (int, float))}
        summary[section].setdefault(iid, {})[seg] = row

    for iid, meta in manifest.items():
        t = truths[meta["tiling"]]
        add("synthetic", iid, "nebius-cpsam-v2", HERE / "results" / "segmenter-bias" / iid / "mask.png", t)
        for seg in segmenters:
            add("synthetic", iid, seg, ROOT / seg / "synthetic" / iid / "mask.png", t)
    for iid in sources:
        add("tissue", iid, "nebius-cpsam-v2", HERE / "results" / iid / "mask.png")
        for seg in segmenters:
            add("tissue", iid, seg, ROOT / seg / iid / "mask.png")

    (ROOT / "summary.json").write_text(json.dumps(summary, indent=1))
    table(summary)
    plot(summary)


def fmt(v):
    return "-" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def table(summary):
    print("\n== synthetic tilings: T-junction fraction (truth in header) ==")
    segs = summary["segmenters"]
    print(f"{'image':30} " + " ".join(f"{s[:14]:>14}" for s in segs))
    for iid, rows in summary["synthetic"].items():
        tiling = iid.split("--")[0]
        t = summary["truth"][tiling]["frac_T_like"]
        print(f"{iid + f' (truth {fmt(t)})':30} " + " ".join(f"{fmt(rows.get(s, {}).get('frac_T_like')):>14}" for s in segs))
    print("\n== synthetic tilings: junction angle SD (deg) ==")
    for iid, rows in summary["synthetic"].items():
        tiling = iid.split("--")[0]
        t = summary["truth"][tiling]["angle_sd"]
        print(f"{iid + f' (truth {fmt(t)})':30} " + " ".join(f"{fmt(rows.get(s, {}).get('angle_sd')):>14}" for s in segs))
    print("\n== tissue images: T-junction fraction / cells ==")
    for iid, rows in summary["tissue"].items():
        print(f"{iid:30} " + " ".join(f"{fmt(rows.get(s, {}).get('frac_T_like'))}/{fmt(rows.get(s, {}).get('cells')):>8}" for s in segs))


def plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    segs = summary["segmenters"]
    tilings = list(summary["truth"])
    fig, axes = plt.subplots(1, len(tilings), figsize=(4 * len(tilings), 3.6), sharey=True)
    for ax, tiling in zip(axes, tilings):
        ax.axhline(summary["truth"][tiling]["frac_T_like"] or 0, color="k", ls=":", lw=1, label="truth")
        for seg in segs:
            pts = []
            for iid, rows in summary["synthetic"].items():
                if iid.startswith(tiling + "--") and seg in rows and rows[seg].get("frac_T_like") is not None:
                    level = iid.split("--")[1]
                    pts.append(({"clean": 12.0, "medium": 4.0, "noisy": 2.0}[level], rows[seg]["frac_T_like"]))
            pts.sort()
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=seg, ms=4)
        ax.set_xscale("log")
        ax.invert_xaxis()
        ax.set_title(tiling, fontsize=9)
        ax.set_xlabel("image SNR")
    axes[0].set_ylabel("T-junction fraction")
    axes[-1].legend(fontsize=6)
    fig.suptitle("T-junction fraction by segmenter on synthetic tilings (dotted = truth)", fontsize=10)
    fig.tight_layout()
    fig.savefig(ROOT / "segmenter-compare.png", dpi=130)


if __name__ == "__main__":
    main()
