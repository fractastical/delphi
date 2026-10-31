# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy", "scikit-image", "pillow", "matplotlib"]
# ///
"""Measure cell-packing geometry from Cellpose label masks.

For each segmented image (results/<id>/mask.png) and for three synthetic
calibration tilings, this measures:
  - junction angles where three cells meet (Thompson: ~120 deg, any cell size)
  - how often four or more cells meet at one point (Thompson: never)
  - number of neighbours per interior cell (Thompson: hexagonal on average)
  - size heterogeneity vs. departure from hexagons (Thompson: hexagons are
    regular only where cells are equal in size)

    uv run claim-sources/cell-geometry/analyze.py
"""
import json
from itertools import combinations
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage, stats
from skimage.segmentation import expand_labels

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
EXCLUDED = {"arabidopsis-shoot-section": "crop missed the intended panel; segmentation unusable"}

# Annulus around a junction used to estimate each wall's direction, as a
# fraction of the median cell diameter.
R_IN, R_OUT = 0.08, 0.25
SHIFTS = [(0, 1), (1, 0), (1, 1), (1, -1)]
# Images with fewer measurable three-cell junctions are reported but not used as evidence.
MIN_JUNCTIONS = 30


def load_mask(path):
    m = np.array(Image.open(path))
    if m.ndim == 3:  # RGB-encoded labels
        m = m[..., 0].astype(np.int64) + 256 * m[..., 1].astype(np.int64) + 65536 * m[..., 2].astype(np.int64)
    return m.astype(np.int64)


def shifted(a, dy, dx, fill=0):
    out = np.full_like(a, fill)
    h, w = a.shape
    ys, yd = (slice(dy, h), slice(0, h - dy)) if dy >= 0 else (slice(0, h + dy), slice(-dy, h))
    xs, xd = (slice(dx, w), slice(0, w - dx)) if dx >= 0 else (slice(0, w + dx), slice(-dx, w))
    out[yd, xd] = a[ys, xs]
    return out


def measure(labels, gap_px=None):
    labels = labels.copy()
    ids, areas = np.unique(labels[labels > 0], return_counts=True)
    area = dict(zip(ids.tolist(), areas.tolist()))
    diam = float(np.median(2 * np.sqrt(areas / np.pi)))
    # Close the gaps Cellpose leaves between touching cells (wider for thick walls).
    E = expand_labels(labels, distance=gap_px or max(3, round(0.08 * diam)))
    h, w = E.shape

    # Cells touching unsegmented space or the image border lack a full neighbour ring.
    padded = np.pad(E, 1, constant_values=0)
    edge_cells = set()
    for dy, dx in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
        nb = padded[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx]
        edge_cells.update(np.unique(E[(E > 0) & (nb == 0)]).tolist())

    # Neighbour pairs and the wall pixels between each pair.
    walls = {}
    for dy, dx in SHIFTS:
        nb = shifted(E, dy, dx)
        sel = (E > 0) & (nb > 0) & (E != nb)
        ys, xs = np.nonzero(sel)
        a, b = E[sel], nb[sel]
        for y, x, p, q in zip(ys, xs, a, b):
            key = (min(p, q), max(p, q))
            walls.setdefault(key, []).append((y + dy / 2, x + dx / 2))
    neighbours = {}
    for p, q in walls:
        neighbours.setdefault(p, set()).add(q)
        neighbours.setdefault(q, set()).add(p)

    # Junctions: pixels whose 3x3 window holds >=3 cells and no unsegmented space.
    stack = np.stack([shifted(E, dy, dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
    srt = np.sort(stack, axis=0)
    distinct = 1 + (np.diff(srt, axis=0) != 0).sum(axis=0)
    has_zero = (stack == 0).any(axis=0)
    cand = (distinct >= 3) & ~has_zero
    clusters, n = ndimage.label(ndimage.binary_dilation(cand, iterations=1))
    junctions = []
    for j, sl in enumerate(ndimage.find_objects(clusters), start=1):
        ys, xs = np.nonzero((clusters[sl] == j) & cand[sl])
        if len(ys) == 0:
            continue
        ys, xs = ys + sl[0].start, xs + sl[1].start
        cells = set(np.unique(stack[:, ys, xs]).tolist()) - {0}
        cy, cx = ys.mean(), xs.mean()
        if cy < 2 or cx < 2 or cy > h - 3 or cx > w - 3:
            continue
        junctions.append({"y": float(cy), "x": float(cx), "cells": sorted(cells)})

    r_in, r_out = R_IN * diam, R_OUT * diam
    rows = []
    for jn in junctions:
        cells = jn["cells"]
        row = {"y": round(jn["y"], 1), "x": round(jn["x"], 1), "n_cells": len(cells),
               "rel_size": float(np.mean([area[c] for c in cells]) / np.median(areas))}
        if len(cells) == 3:
            dirs = []
            for p, q in combinations(cells, 2):
                pts = np.array(walls.get((min(p, q), max(p, q)), []), dtype=float)
                if len(pts) == 0:
                    break
                d = np.hypot(pts[:, 0] - jn["y"], pts[:, 1] - jn["x"])
                near = pts[(d >= r_in) & (d <= r_out)]
                if len(near) < 3:
                    break
                v = near.mean(axis=0) - (jn["y"], jn["x"])
                dirs.append(np.degrees(np.arctan2(v[0], v[1])) % 360)
            if len(dirs) == 3:
                s = sorted(dirs)
                angles = sorted([s[1] - s[0], s[2] - s[1], 360 - s[2] + s[0]])
                row.update({"angles": [round(a, 1) for a in angles],
                            "max_dev": round(max(abs(a - 120) for a in angles), 1)})
        rows.append(row)

    interior = [c for c in ids.tolist() if c not in edge_cells and c in neighbours]
    nsides = {c: len(neighbours[c]) for c in interior}
    return {"diam_px": diam, "area": area, "neighbours": neighbours, "interior": interior,
            "nsides": nsides, "junctions": rows}


def summarize(m):
    tri = [j for j in m["junctions"] if "angles" in j]
    allj = m["junctions"]
    angles = np.array([a for j in tri for a in j["angles"]]) if tri else np.array([])
    dev = np.array([j["max_dev"] for j in tri])
    out = {
        "cells": len(m["area"]),
        "interior_cells": len(m["interior"]),
        "junctions": len(allj),
        "junctions_measured": len(tri),
        "fourfold_or_more_fraction": round(sum(j["n_cells"] >= 4 for j in allj) / len(allj), 3) if allj else None,
        "sufficient": len(tri) >= MIN_JUNCTIONS,
    }
    if len(tri):
        out.update({
            "angle_mean": round(float(angles.mean()), 1),
            "angle_sd": round(float(angles.std()), 1),
            "median_max_dev": round(float(np.median(dev)), 1),
            "frac_all_within_15deg": round(float((dev <= 15).mean()), 3),
            "frac_T_like": round(float(np.mean([max(j["angles"]) >= 160 for j in tri])), 3),
        })
        rel = np.array([j["rel_size"] for j in tri])
        if len(tri) >= 10:
            rho, p = stats.spearmanr(rel, dev)
            out["size_vs_dev_spearman"] = corr(rho, p)
    if m["interior"]:
        n = np.array(list(m["nsides"].values()))
        a = np.array([m["area"][c] for c in m["nsides"]], dtype=float)
        out.update({
            "mean_neighbours": round(float(n.mean()), 2),
            "neighbour_variance_mu2": round(float(n.var()), 2),
            "frac_hexagons": round(float((n == 6).mean()), 3),
            "area_cv": round(float(a.std() / a.mean()), 3),
        })
        if len(n) >= 10:
            rho, p = stats.spearmanr(a, n)
            out["lewis_area_vs_sides_spearman"] = corr(rho, p)
            # Local size heterogeneity vs departure from six sides, per cell.
            het, irr = [], []
            for c in m["nsides"]:
                ring = [m["area"][c]] + [m["area"][k] for k in m["neighbours"][c]]
                het.append(np.std(ring) / np.mean(ring))
                irr.append(abs(m["nsides"][c] - 6))
            rho, p = stats.spearmanr(het, irr)
            out["local_size_het_vs_nonhex_spearman"] = corr(rho, p)
    return out


def corr(rho, p):
    """Spearman result for JSON; a constant input (e.g. a perfect lattice) has no defined rho."""
    if np.isnan(rho):
        return {"rho": None, "p": None}
    return {"rho": round(float(rho), 3), "p": float(f"{p:.3g}")}


# --- synthetic calibration tilings --------------------------------------------

def hex_lattice(size=1200, r=40):
    yy, xx = np.mgrid[0:size, 0:size]
    pts = [(y, x + (r * np.sqrt(3) / 2 if (i % 2) else 0))
           for i, y in enumerate(np.arange(0, size + r, 1.5 * r))
           for x in np.arange(0, size + 2 * r, r * np.sqrt(3))]
    return voronoi_raster(np.array(pts), size)


def brick_wall(size=1200, bw=120, bh=50):
    yy, xx = np.mgrid[0:size, 0:size]
    row = yy // bh
    col = (xx + (row % 2) * (bw // 2)) // bw
    lab = row * 1000 + col + 1
    lab[(yy % bh == 0) | ((xx + (row % 2) * (bw // 2)) % bw == 0)] = 0  # thin walls
    return relabel(lab)


def random_voronoi(size=1200, n=500, seed=0):
    rng = np.random.default_rng(seed)
    return voronoi_raster(rng.uniform(0, size, (n, 2)), size)


def voronoi_raster(pts, size):
    from scipy.spatial import cKDTree
    yy, xx = np.mgrid[0:size, 0:size]
    _, idx = cKDTree(pts).query(np.c_[yy.ravel(), xx.ravel()])
    lab = idx.reshape(size, size) + 1
    edge = np.zeros_like(lab, bool)
    edge[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    edge[1:, :] |= lab[1:, :] != lab[:-1, :]
    lab[edge] = 0  # 1-px walls, like a segmentation mask
    return relabel(lab)


def relabel(lab):
    out, _ = ndimage.label(lab > 0)
    return out


def main():
    sources = json.loads((HERE / "inputs" / "sources.json").read_text())
    summary = {"method": {
        "segmentation": "Cellpose CPSAM v2 on the Nebius Scientific AI Platform (segment_cells_native)",
        "wall_direction_annulus_fraction_of_median_diameter": [R_IN, R_OUT],
        "gap_closing": "skimage expand_labels, distance = max(3 px, 0.08 x median cell diameter)",
        "interior_cell": "cell whose expanded outline touches no unsegmented pixel and not the image border",
        "fourfold": "junction cluster (pixels within 1 px) whose windows contain >= 4 distinct cells",
    }, "controls": {}, "images": {}}

    for name, fn in [("hexagonal-lattice", hex_lattice), ("brick-wall", brick_wall), ("random-voronoi", random_voronoi)]:
        summary["controls"][name] = summarize(measure(fn()))
        print(name, summary["controls"][name])

    for image_id, meta in sources.items():
        if image_id in EXCLUDED:
            summary["images"][image_id] = {"excluded": EXCLUDED[image_id]}
            continue
        mask = RESULTS / image_id / "mask.png"
        if not mask.exists():
            continue
        m = measure(load_mask(mask), meta.get("gap_closing_px"))
        s = summarize(m)
        s.update({"species": meta["species"], "tissue": meta["tissue"], "kingdom": meta["kingdom"],
                  "gap_closing_px": meta.get("gap_closing_px", "default")})
        summary["images"][image_id] = s
        (RESULTS / image_id / "junctions.json").write_text(json.dumps(m["junctions"]))
        print(image_id, s)

    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=1))
    plot(summary)


def plot(summary):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = [(k, None) for k in summary["controls"]] + [(k, v) for k, v in summary["images"].items() if "excluded" not in v]
    fig, axes = plt.subplots(2, (len(panels) + 1) // 2, figsize=(3.2 * ((len(panels) + 1) // 2), 6.2), sharex=True)
    for ax, (k, v) in zip(axes.ravel(), panels):
        if v is None:
            m = measure({"hexagonal-lattice": hex_lattice, "brick-wall": brick_wall, "random-voronoi": random_voronoi}[k]())
            rows, title, color = m["junctions"], f"control: {k}", "0.5"
        else:
            rows = json.loads((RESULTS / k / "junctions.json").read_text())
            title, color = f"{v['species'] or 'species n/s'}\n{v['tissue'][:34]}", "tab:green" if v["kingdom"] == "Plantae" else "tab:purple"
        ang = [a for r in rows if "angles" in r for a in r["angles"]]
        ax.hist(ang, bins=np.arange(0, 241, 10), color=color)
        ax.axvline(120, color="k", ls="--", lw=1)
        ax.set_title(title, fontsize=8)
        ax.set_yticks([])
    for ax in axes.ravel()[len(panels):]:
        ax.axis("off")
    fig.supxlabel("angle between cell walls at three-cell junctions (degrees)")
    fig.suptitle("Thompson (1917): cell walls meet three at a time at 120°", fontsize=11)
    fig.tight_layout()
    fig.savefig(RESULTS / "junction-angles.png", dpi=130)


if __name__ == "__main__":
    main()
