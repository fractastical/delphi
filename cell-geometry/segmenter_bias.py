# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "matplotlib"]
# ///
"""Does Cellpose-SAM impose 120-degree, Voronoi-like packing on tissue that does not have it?

The three calibration tilings in analyze.py were label masks fed straight into the junction
code; the segmenter never saw them. This script closes that gap (raised by vina on Moltbook,
2026-10-31): it renders tilings with KNOWN packing as micrograph-like images at several noise
levels, segments them with the same CPSAM v2 checkpoint on Nebius, and compares junction
statistics measured on the segmenter's output with the same statistics on the ground-truth
labels. The difference is the segmenter's bias.

Tilings: hexagonal lattice (truth 120/120/120), brick wall (90/90/180: all T-junctions),
random Voronoi (no surface tension), and cell files (elongated rectangles with staggered
cross-walls, matched to the grass-epidermis geometry that came out at 49% T-junctions).

    uv run cell-geometry/segmenter_bias.py render     # inputs/synthetic/*.png + truth labels
    python3 cell-geometry/segmenter_bias.py segment   # Nebius -> results/segmenter-bias/<id>/
    uv run cell-geometry/segmenter_bias.py analyze    # summary.json + segmenter-bias.png
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
INPUTS = HERE / "inputs" / "synthetic"
OUT = HERE / "results" / "segmenter-bias"
SIZE = 1200
# Peak signal-to-noise of the rendered wall against background, in dB-ish terms: the
# wall/background contrast divided by the noise SD. Real micrographs here sit around 3-6.
SNR_LEVELS = {"clean": 12.0, "medium": 4.0, "noisy": 2.0}
SEED = 7


def tilings():
    from analyze import hex_lattice, brick_wall, random_voronoi, relabel
    from scipy import ndimage

    def cell_files(size=SIZE, w=38, h=150, jitter=0.35, seed=SEED):
        """Elongated cells in parallel files; cross-walls staggered at random between files,
        so new walls meet old ones at right angles (the grass-epidermis geometry)."""
        rng = np.random.default_rng(seed)
        lab = np.zeros((size, size), np.int64)
        nxt = 1
        for col in range(0, size, w):
            y = -int(rng.uniform(0, h))
            while y < size:
                hh = int(h * rng.uniform(1 - jitter, 1 + jitter))
                lab[max(y, 0):min(y + hh, size), col:col + w] = nxt
                nxt += 1
                y += hh
        # 1-px walls between distinct labels, like a segmentation mask
        edge = np.zeros_like(lab, bool)
        edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]
        edge[1:, :] |= lab[1:, :] != lab[:-1, :]
        lab[edge] = 0
        return relabel(lab)

    return {
        "hexagonal-lattice": hex_lattice(SIZE, r=40),
        "brick-wall": brick_wall(SIZE, bw=120, bh=50),
        "random-voronoi": random_voronoi(SIZE, n=500, seed=0),
        "cell-files": cell_files(),
    }


def render(labels, snr, seed, wall_px=3.0, blur_px=1.6):
    """Bright-field-like image: pale cytoplasm with slight per-cell shading, dark walls of
    finite width, defocus blur, Poisson + Gaussian noise. Returns uint8 RGB."""
    from scipy import ndimage
    rng = np.random.default_rng(seed)
    wall = labels == 0
    wall = ndimage.binary_dilation(wall, iterations=max(1, int(round(wall_px / 2))))
    img = np.full(labels.shape, 0.78)
    # per-cell shading: cytoplasm varies a little from cell to cell
    ids = np.unique(labels[labels > 0])
    shade = dict(zip(ids.tolist(), rng.normal(0, 0.05, len(ids))))
    sh = np.zeros_like(img)
    for i, s in shade.items():
        sh[labels == i] = s
    img += sh
    img[wall] = 0.28
    img = ndimage.gaussian_filter(img, blur_px)
    contrast = 0.78 - 0.28
    sigma = contrast / snr
    # Poisson-like: noise scales with brightness; plus a Gaussian floor
    img = img + rng.normal(0, 1, img.shape) * sigma * np.sqrt(np.clip(img, 0.05, 1)) + rng.normal(0, sigma * 0.3, img.shape)
    # Slow illumination gradient
    yy, xx = np.mgrid[0:img.shape[0], 0:img.shape[1]]
    img *= 1 + 0.08 * (xx / img.shape[1] - 0.5)
    img = np.clip(img, 0, 1)
    return (np.stack([img] * 3, -1) * 255).astype(np.uint8)


def cmd_render():
    INPUTS.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name, lab in tilings().items():
        assert lab.max() < 65535
        Image.fromarray(lab.astype(np.uint16)).save(INPUTS / f"{name}.truth.png")
        for level, snr in SNR_LEVELS.items():
            iid = f"{name}--{level}"
            Image.fromarray(render(lab, snr, SEED)).save(INPUTS / f"{iid}.png")
            ids, areas = np.unique(lab[lab > 0], return_counts=True)
            manifest[iid] = {"tiling": name, "snr": snr, "truth": f"{name}.truth.png",
                             "cellpose_diameter": int(round(float(np.median(2 * np.sqrt(areas / np.pi)))))}
            print(iid, manifest[iid])
    (INPUTS / "manifest.json").write_text(json.dumps(manifest, indent=1))


def cmd_segment():
    from segment import Client, MODEL, download  # noqa: F401
    manifest = json.loads((INPUTS / "manifest.json").read_text())
    wanted = sys.argv[2:] or list(manifest)
    client = Client()
    for iid in wanted:
        meta = manifest[iid]
        out = OUT / iid
        if (out / "mask.png").exists():
            print(f"{iid}: already segmented")
            continue
        out.mkdir(parents=True, exist_ok=True)
        try:
            ref = client.upload(MODEL, INPUTS / f"{iid}.png", "image/png")
            sub = client.call("segment_cells_native", {
                "image_base64": ref, "media_type": "image/png", "research_only": True,
                "diameter": meta["cellpose_diameter"],
                "idempotency_key": f"segbias-{ref['sha256'][:32]}-d{meta['cellpose_diameter']}",
                "output_prefix": f"cell-geometry/segmenter-bias/{iid}", "wait_seconds": 30,
            })
            op_id = (sub.get("operation") or {}).get("id") or sub.get("operation_id") or (sub.get("error") or {}).get("operation_id")
            if not op_id:
                raise RuntimeError(f"unexpected submit response: {json.dumps(sub)[:800]}")
            res = client.wait(op_id, every=10)
            r = res["result"]
            download(client, r["mask_artifact"]["artifact_id"], out / "mask.png")
            download(client, r["overlay_artifact"]["artifact_id"], out / "overlay.png")
            (out / "cellpose.json").write_text(json.dumps({
                "image_id": iid, "operation_id": op_id, "platform": "Nebius Scientific AI Platform",
                "tool": "segment_cells_native", "model_id": r["model_id"], "model_sha256": r["model_sha256"],
                "diameter": meta["cellpose_diameter"], "cellpose_version": r["cellpose_version"],
                "input_sha256": r["input_sha256"], "mask_sha256": r["mask_artifact"]["sha256"],
                "object_count": r["object_count"], "image_shape": r["image_shape"],
            }, indent=1))
            print(f"{iid}: {r['object_count']} cells (truth {len(np.unique(np.array(Image.open(INPUTS / meta['truth'])))) - 1})")
        except Exception as e:
            print(f"{iid}: FAILED {e}")


KEYS = ["junctions_measured", "angle_mean", "angle_sd", "frac_all_within_15deg", "frac_T_like",
        "fourfold_or_more_fraction", "mean_neighbours", "frac_hexagons", "cells"]


def cmd_analyze():
    from analyze import measure, summarize, load_mask
    manifest = json.loads((INPUTS / "manifest.json").read_text())
    summary = {"method": "Same tilings as analyze.py controls plus 'cell-files', rendered as bright-field-like "
                         "images (dark 3 px walls, Gaussian blur 1.6 px, Poisson+Gaussian noise, illumination gradient) "
                         "at three SNR levels, segmented with the same CPSAM v2 checkpoint, measured with analyze.measure. "
                         "Bias = segmented minus truth.", "snr_levels": SNR_LEVELS, "truth": {}, "segmented": {}}
    truths = {}
    for name in sorted({m["tiling"] for m in manifest.values()}):
        lab = np.array(Image.open(INPUTS / f"{name}.truth.png")).astype(np.int64)
        truths[name] = summarize(measure(lab))
        summary["truth"][name] = truths[name]
    for iid, meta in manifest.items():
        mask = OUT / iid / "mask.png"
        if not mask.exists():
            summary["segmented"][iid] = {"missing": True}
            continue
        s = summarize(measure(load_mask(mask)))
        t = truths[meta["tiling"]]
        s["bias"] = {k: (round(s[k] - t[k], 3) if isinstance(s.get(k), (int, float)) and isinstance(t.get(k), (int, float)) else None)
                     for k in ["angle_sd", "frac_all_within_15deg", "frac_T_like", "frac_hexagons", "mean_neighbours"]}
        s.update({"tiling": meta["tiling"], "snr": meta["snr"]})
        summary["segmented"][iid] = s
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=1))
    table(summary)
    plot(summary)


def table(summary):
    print(f"{'image':28} {'cells':>6} {'junc':>5} {'ang_sd':>7} {'<15deg':>7} {'T-like':>7} {'hex':>6} {'nbr':>5}")
    for name, t in summary["truth"].items():
        print(f"{name + ' (truth)':28} {t['cells']:>6} {t['junctions_measured']:>5} {t.get('angle_sd', float('nan')):>7} "
              f"{t.get('frac_all_within_15deg', float('nan')):>7} {t.get('frac_T_like', float('nan')):>7} {t.get('frac_hexagons', float('nan')):>6} {t.get('mean_neighbours', float('nan')):>5}")
        for iid, s in summary["segmented"].items():
            if s.get("tiling") != name:
                continue
            print(f"  {iid.split('--')[1]:26} {s['cells']:>6} {s['junctions_measured']:>5} {s.get('angle_sd', float('nan')):>7} "
                  f"{s.get('frac_all_within_15deg', float('nan')):>7} {s.get('frac_T_like', float('nan')):>7} {s.get('frac_hexagons', float('nan')):>6} {s.get('mean_neighbours', float('nan')):>5}")


def plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    tilings_ = list(summary["truth"])
    metrics = [("frac_T_like", "T-junction fraction (max angle >= 160)"), ("angle_sd", "junction angle SD (deg)"),
               ("frac_all_within_15deg", "junctions with all angles within 15 deg of 120")]
    fig, axes = plt.subplots(1, len(metrics), figsize=(4.2 * len(metrics), 3.8))
    colors = dict(zip(tilings_, ["tab:blue", "tab:red", "tab:gray", "tab:green"]))
    for ax, (k, label) in zip(axes, metrics):
        for name in tilings_:
            t = summary["truth"][name].get(k)
            pts = sorted([(s["snr"], s.get(k)) for s in summary["segmented"].values() if s.get("tiling") == name and s.get(k) is not None])
            if t is not None:
                ax.axhline(t, color=colors[name], ls=":", lw=1)
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", color=colors[name], label=name)
        ax.set_xscale("log")
        ax.set_xlabel("image SNR (wall contrast / noise SD)")
        ax.set_title(label, fontsize=9)
        ax.invert_xaxis()
    axes[0].legend(fontsize=7)
    fig.suptitle("Cellpose-SAM on synthetic tilings: dotted = ground truth, points = segmenter output", fontsize=10)
    fig.tight_layout()
    fig.savefig(OUT / "segmenter-bias.png", dpi=130)


if __name__ == "__main__":
    {"render": cmd_render, "segment": cmd_segment, "analyze": cmd_analyze}[sys.argv[1]]()
