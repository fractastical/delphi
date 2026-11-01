#!/usr/bin/env python3
"""Pre-registered analysis for thompson1917-ch07-04, eye-bank hexagonality run.

Reads Human_Corneal_Endothelium.csv (Brookes 2017, 10.17608/k6.auckland.5701087; not vendored,
105 MB) and writes derived/summary.json, derived/images.csv and derived/figure.png.

    python3 analysis.py /path/to/Human_Corneal_Endothelium.csv
"""
import json, sys, os, hashlib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "derived")
os.makedirs(OUT, exist_ok=True)
src = sys.argv[1]

sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
df = pd.read_csv(src, encoding="utf-8-sig", na_values=["-"])
df.columns = [c.strip() for c in df.columns]
n_rows = len(df)

def pct(s):
    return pd.to_numeric(s.astype(str).str.rstrip("%"), errors="coerce") / 100.0

# Identify images. In the file, "Dataset ID" is "<image>-<cell>" and "Image Number" runs 1..2000;
# there is no cornea or donor identifier, so the pre-registered cornea-level aggregation cannot be
# computed (recorded as a deviation in result.json).
img_key = ["Image Number"]
img = df.groupby(img_key, sort=False).first().reset_index()
img["cv_area"] = pct(img["Image - Cell Area CV"])
img["total"] = pd.to_numeric(img["Image - Total Cells"], errors="coerce")
img["f6"] = pd.to_numeric(img["Image - 6-Sides Cell Count"], errors="coerce") / img["total"]
img["density"] = pd.to_numeric(img["Image - Mean Cell Density (cells/mm^2)"], errors="coerce")
img["hex_reg"] = pct(img["Image - Mean Hexagonal Cell Regularity"])
img["sides_cv"] = pd.to_numeric(img["Image - Cell Sides CV"], errors="coerce")

# Cross-check per-image totals against per-cell rows.
cell_counts = df.groupby(img_key, sort=False).size().reset_index(name="rows")
img = img.merge(cell_counts, on=img_key)
mismatch = int((img["rows"] != img["total"]).sum())

use = img[(img["total"] >= 50) & img["cv_area"].notna() & img["f6"].notna()].copy()

def boot_rho(x, y, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    x = np.asarray(x); y = np.asarray(y); N = len(x)
    r0 = spearmanr(x, y).correlation
    rs = np.empty(n)
    for i in range(n):
        idx = rng.integers(0, N, N)
        rs[i] = spearmanr(x[idx], y[idx]).correlation
    lo, hi = np.percentile(rs, [2.5, 97.5])
    return float(r0), float(lo), float(hi)

res = {}
r, lo, hi = boot_rho(use["cv_area"], use["f6"])
res["image_level"] = {"n_images": int(len(use)), "rho_cv_f6": r, "ci95": [lo, hi]}

res["cornea_level"] = {"status": "not-computable", "reason": "the CSV carries no cornea or donor identifier; Dataset ID is image-cell"}

# Secondary: density vs f6 (clinical reading)
r, lo, hi = boot_rho(use["density"], use["f6"])
res["secondary_density_f6_image"] = {"rho": r, "ci95": [lo, hi]}
r, lo, hi = boot_rho(use["density"], use["cv_area"])
res["secondary_density_cv_image"] = {"rho": r, "ci95": [lo, hi]}

# Secondary: within-image Lewis's law, per-cell area vs sides
cells = df.copy()
cells["area"] = pd.to_numeric(cells["Cell - Cell Area (µm^2)"], errors="coerce")
cells["sides"] = pd.to_numeric(cells["Cell - Number of Sides"], errors="coerce")
lewis = []
for k, g in cells.groupby(img_key, sort=False):
    g = g.dropna(subset=["area", "sides"])
    if len(g) >= 50 and g["sides"].nunique() > 1:
        lewis.append(spearmanr(g["area"], g["sides"]).correlation)
lewis = np.array(lewis)
res["secondary_lewis_within_image"] = {"n_images": int(len(lewis)), "median_rho_area_sides": float(np.median(lewis)),
                                        "iqr": [float(np.percentile(lewis, 25)), float(np.percentile(lewis, 75))],
                                        "frac_positive": float((lewis > 0).mean())}

# Sensitivity: density >= 2000
hq = use[use["density"] >= 2000]
r, lo, hi = boot_rho(hq["cv_area"], hq["f6"])
res["sensitivity_density_ge_2000"] = {"n_images": int(len(hq)), "rho_cv_f6": r, "ci95": [lo, hi]}

# Descriptives
res["descriptives"] = {
    "rows": int(n_rows), "images_total": int(len(img)), "images_used": int(len(use)),
    "images_excluded_lt_50_cells": int((img["total"] < 50).sum()),
    "images_where_row_count_differs_from_stated_total": mismatch,
    "corneas": "678 per the dataset record; not identifiable in the file",
    "mean_cell_sides_overall": float(pd.to_numeric(img["Image - Mean Cell Sides"], errors="coerce").mean()),
    "f6": {"median": float(use["f6"].median()), "p10": float(use["f6"].quantile(.1)), "p90": float(use["f6"].quantile(.9))},
    "cv_area": {"median": float(use["cv_area"].median()), "p10": float(use["cv_area"].quantile(.1)), "p90": float(use["cv_area"].quantile(.9))},
    "density": {"median": float(use["density"].median()), "p10": float(use["density"].quantile(.1)), "p90": float(use["density"].quantile(.9))},
}
# f6 by CV quintile, for the figure and the text
use["cv_q"] = pd.qcut(use["cv_area"], 5, labels=False)
res["f6_by_cv_quintile"] = [{"quintile": int(q), "cv_range": [float(g["cv_area"].min()), float(g["cv_area"].max())],
                             "f6_median": float(g["f6"].median()), "n": int(len(g))} for q, g in use.groupby("cv_q")]

# Pre-registered decision
# Image level only (cornea level not computable, see deviation).
il = res["image_level"]
if abs(il["rho_cv_f6"]) < .15 and all(-.30 < v < .30 for v in il["ci95"]):
    verdict = "supports"
elif il["rho_cv_f6"] <= -.30 and il["ci95"][1] < -.15:
    verdict = "refutes"
else:
    verdict = "mixed"
res["preregistered_verdict_irrespective_of_size"] = verdict
res["source_file"] = {"name": os.path.basename(src), "sha256": sha, "bytes": os.path.getsize(src)}

use.drop(columns=[c for c in use.columns if c.startswith("Image - ")]).to_csv(os.path.join(OUT, "images.csv"), index=False)
json.dump(res, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
print(json.dumps(res, indent=1))

# Figure
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(11, 4.4))
ax[0].scatter(use["cv_area"] * 100, use["f6"] * 100, s=6, alpha=.35, color="#2457D6", lw=0)
ax[0].set_xlabel("cell-area coefficient of variation per image (%)")
ax[0].set_ylabel("hexagonal cells per image (%)")
ax[0].set_title(f"{len(use):,} specular images of 678 donor corneas\nSpearman rho = {il['rho_cv_f6']:.2f} [{il['ci95'][0]:.2f}, {il['ci95'][1]:.2f}]", fontsize=10)
ax[1].scatter(use["density"], use["f6"] * 100, s=6, alpha=.35, color="#B23A5A", lw=0)
ax[1].set_xlabel("endothelial cell density per image (cells/mm²)")
ax[1].set_ylabel("hexagonal cells per image (%)")
r2 = res["secondary_density_f6_image"]
ax[1].set_title(f"secondary: cell loss and hexagons\nSpearman rho = {r2['rho']:.2f} [{r2['ci95'][0]:.2f}, {r2['ci95'][1]:.2f}]", fontsize=10)
for a in ax:
    a.spines[["top", "right"]].set_visible(False)
fig.suptitle("Human corneal endothelium (NZ National Eye Bank, Brookes 2017, CC BY 4.0): does packing regularity depend on cell-size variation?", fontsize=10)
fig.tight_layout()
fig.savefig(os.path.join(OUT, "figure.png"), dpi=160)
print("wrote", OUT)
