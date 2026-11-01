#!/usr/bin/env python3
"""Vein versus inter-vein run of thompson1917-ch07-08: are cells under directional traction (pupal
wing veins L3, L4, which undergo convergent extension) less often hexagonal than inter-vein cells?

Data: Etournay et al. 2015 pupal wings WT_1-3 as TissueMiner databases plus the authors' frame-200
ROI polygons (example_data/<wing>/Segmentation/UserFrameRoi.txt), in
../../thompson1917-ch07-09/pupal-wing-timelapse/data/ (downloaded and checksummed by that run).

Region assignment: a cell at frame 200 belongs to the ROI polygon containing its centre
(matplotlib.path). Cells in other frames are assigned through their cell id, or through the
cell id of their frame-200 descendant (cell_histories left/right daughters), so a mother cell
inherits the region of its daughters when both agree. Per wing and window (first 2 h, last 2 h):
f6, mean elongation magnitude and area CV for vein and inter-vein interior cells.

Run: python3 analysis.py
"""
import hashlib, json, os, sqlite3, sys, tarfile
import numpy as np
import pandas as pd
from matplotlib.path import Path

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "thompson1917-ch07-09", "pupal-wing-timelapse", "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
WINGS = ["WT_1", "WT_2", "WT_3"]
MARGIN = 10000
VEIN = {"distL3", "distL4"}
INTER = {"distInterL2-L3", "distInterL3-L4", "distInterL4-L5"}
ROI_FRAME = 200


def file_meta(wing):
    path = os.path.join(DATA, f"{wing}.tar.gz")
    if not os.path.exists(path):
        sys.exit(f"missing {path}: run ../../thompson1917-ch07-09/pupal-wing-timelapse/analysis.py first")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    stamp = path[:-7] + ".retrieved"
    return dict(download_url=f"http://bds.mpi-cbg.de/tissue_miner/{wing}.tar.gz",
                retrieved_at=open(stamp).read().strip() if os.path.exists(stamp) else None, byte_size=os.path.getsize(path), sha256=h.hexdigest())


def extract(wing, member):
    out = os.path.join(DATA, member)
    if not os.path.exists(out):
        with tarfile.open(os.path.join(DATA, f"{wing}.tar.gz")) as t:
            t.extract(member, DATA)
    return out


def load(wing):
    con = sqlite3.connect(extract(wing, f"example_data/{wing}/{wing}.sqlite"))
    frames = pd.read_sql("select frame, time_sec from frames", con)
    cells = pd.read_sql("select frame, cell_id, center_x, center_y, area, elong_xx, elong_xy from cells", con)
    db = pd.read_sql("select frame, cell_id, dbond_id, conj_dbond_id from directed_bonds", con)
    hist = pd.read_sql("select cell_id, left_daughter_cell_id, right_daughter_cell_id from cell_histories", con)
    con.close()
    conj = db[["frame", "dbond_id", "cell_id"]].rename(columns={"dbond_id": "conj_dbond_id", "cell_id": "nb"})
    pairs = db.merge(conj, on=["frame", "conj_dbond_id"])
    pairs = pairs[pairs.cell_id != MARGIN]
    nb = pairs.groupby(["frame", "cell_id"]).agg(n=("nb", "nunique"), touches_margin=("nb", lambda s: (s == MARGIN).any())).reset_index()
    df = cells.merge(nb, on=["frame", "cell_id"]).merge(frames, on="frame")
    df = df[~df.touches_margin].copy()
    df["time_h"] = df.time_sec / 3600
    df["elong"] = np.hypot(df.elong_xx, df.elong_xy)
    roi = pd.read_csv(extract(wing, f"example_data/{wing}/Segmentation/UserFrameRoi.txt"), sep=r"\s+")
    return df, hist, roi


def assign_regions(df, hist, roi):
    at = df[df.frame == ROI_FRAME]
    if at.empty:
        at = df[df.frame == df.frame.max()]
    region = {}
    for name, g in roi[roi.frame == ROI_FRAME].groupby("ROIname"):
        cls = "vein" if name in VEIN else "inter" if name in INTER else None
        if cls is None:
            continue
        inside = Path(g[["x", "y"]].values).contains_points(at[["center_x", "center_y"]].values)
        for cid in at.cell_id[inside]:
            region[int(cid)] = cls if region.get(int(cid), cls) == cls else "conflict"
    # propagate to ancestors: a mother takes its daughters' region when they agree
    parent = {}
    for r in hist.itertuples(index=False):
        for d in (r.left_daughter_cell_id, r.right_daughter_cell_id):
            if d is not None and not (isinstance(d, float) and np.isnan(d)) and int(d) != 0:
                parent[int(d)] = int(r.cell_id)
    changed = True
    while changed:
        changed = False
        kids = {}
        for cid, reg in region.items():
            if cid in parent and parent[cid] not in region:
                kids.setdefault(parent[cid], set()).add(reg)
        for p, regs in kids.items():
            region[p] = regs.pop() if len(regs) == 1 else "conflict"
            changed = True
    return region


def window_stats(g):
    return dict(cells=int(len(g)), cell_frames_per_frame=round(float(len(g) / max(g.frame.nunique(), 1)), 1),
                f6=round(float((g.n == 6).mean()), 4), mean_n=round(float(g.n.mean()), 3), sd_n=round(float(g.n.std(ddof=0)), 3),
                mean_elong=round(float(g.elong.mean()), 4), area_cv=round(float(g.area.std(ddof=0) / g.area.mean()), 3))


def analyse(wing):
    df, hist, roi = load(wing)
    region = assign_regions(df, hist, roi)
    df["region"] = df.cell_id.map(region)
    T = df.time_h.max()
    out = dict(wing=wing, roi_frame=ROI_FRAME, cells_assigned_at_roi_frame=int(sum(1 for v in region.values() if v != "conflict")), conflicts=int(sum(1 for v in region.values() if v == "conflict")))
    for label, sel in (("last_2h", df.time_h >= T - 2), ("first_2h", df.time_h <= 2)):
        w = df[sel & df.region.isin(["vein", "inter"])]
        v, i = w[w.region == "vein"], w[w.region == "inter"]
        out[label] = dict(vein=window_stats(v), inter=window_stats(i),
                          f6_inter_minus_vein=round(float((i.n == 6).mean() - (v.n == 6).mean()), 4),
                          vein_more_elongated=bool(v.elong.mean() > i.elong.mean()),
                          elong_ratio_vein_over_inter=round(float(v.elong.mean() / i.elong.mean()), 3))
    # per-frame trace for the derived table
    tr = df[df.region.isin(["vein", "inter"])].groupby(["frame", "region"]).apply(lambda g: pd.Series(dict(time_h=g.time_h.iloc[0], n_cells=len(g), f6=(g.n == 6).mean(), mean_elong=g.elong.mean()))).reset_index()
    tr.round(4).to_csv(os.path.join(DERIVED, f"{wing}_vein_intervein_per_frame.csv"), index=False)
    return out


def main():
    files = [file_meta(w) for w in WINGS]
    wings = [analyse(w) for w in WINGS]
    for w in wings:
        print(json.dumps(w), file=sys.stderr)
    L = [w["last_2h"] for w in wings]
    counts = dict(
        wings_supports=int(sum(x["vein_more_elongated"] and x["f6_inter_minus_vein"] >= 0.05 for x in L)),
        wings_refutes=int(sum(x["vein_more_elongated"] and x["f6_inter_minus_vein"] <= 0 for x in L)),
        wings_premise_fails=int(sum(not x["vein_more_elongated"] for x in L)),
        wings_vein_cells_per_frame_lt_100=int(sum(x["vein"]["cell_frames_per_frame"] < 100 for x in L)))
    out = dict(files=files, wings=wings, verdict_counts=counts,
               median_f6_inter_minus_vein_last_2h=round(float(np.median([x["f6_inter_minus_vein"] for x in L])), 4),
               median_f6_inter_minus_vein_first_2h=round(float(np.median([w["first_2h"]["f6_inter_minus_vein"] for w in wings])), 4))
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
