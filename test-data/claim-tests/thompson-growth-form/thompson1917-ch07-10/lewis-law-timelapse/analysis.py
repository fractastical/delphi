#!/usr/bin/env python3
"""Lewis's-law run of thompson1917-ch07-10: close-packed cells of varying size are hexagonal on
average, the larger having more and the smaller fewer than six sides.

Data: the five Dye et al. wing-disc movies (../../thompson1917-ch07-09/data/, Zenodo 22760592) and
the three Etournay et al. 2015 pupal wings (../../thompson1917-ch07-09/pupal-wing-timelapse/data/),
TissueMiner databases, every 10th frame, interior cells (no bond with margin cell 10000).

Per tissue: mean neighbour number, Spearman rho(area, n) (area relative to the frame median),
mean relative area per polygon class 4-8 (classes with >= 50 cells), monotonicity of those means,
least-squares slope and R^2 of class mean area on n, and the fit of area on (n - 2) through the origin.

Run: python3 analysis.py
"""
import hashlib, json, os, sqlite3, sys, tarfile, zipfile
import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
D1 = os.path.join(HERE, "..", "..", "thompson1917-ch07-09", "data")
D2 = os.path.join(HERE, "..", "..", "thompson1917-ch07-09", "pupal-wing-timelapse", "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
MARGIN = 10000
STEP = 10
TISSUES = [("disc", m, os.path.join(D1, f"{m}.zip")) for m in ["Ecd_20141010_P2", "Ecd_20150310_P2", "Ecd_20150418_P1", "Ecd_20150608_P1", "Ecd_20161213_F0"]] + \
          [("pupal", w, os.path.join(D2, f"{w}.tar.gz")) for w in ["WT_1", "WT_2", "WT_3"]]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def sqlite_path(kind, name, archive):
    if not os.path.exists(archive):
        sys.exit(f"missing {archive}: run the ch07-09 analyses first")
    if kind == "disc":
        out_dir = os.path.join(D1, f"db_{name[4:12]}")
        os.makedirs(out_dir, exist_ok=True)
        with zipfile.ZipFile(archive) as z:
            member = [m for m in z.namelist() if m.endswith(".sqlite")][0]
            out = os.path.join(out_dir, os.path.basename(member))
            if not os.path.exists(out):
                with z.open(member) as src, open(out, "wb") as dst:
                    for chunk in iter(lambda: src.read(1 << 24), b""):
                        dst.write(chunk)
        return out
    out = os.path.join(D2, "example_data", name, f"{name}.sqlite")
    if not os.path.exists(out):
        with tarfile.open(archive) as t:
            t.extract(f"example_data/{name}/{name}.sqlite", D2)
    return out


def analyse(kind, name, archive):
    con = sqlite3.connect(sqlite_path(kind, name, archive))
    cells = pd.read_sql(f"select frame, cell_id, area from cells where frame % {STEP} = 0", con)
    db = pd.read_sql(f"select frame, cell_id, dbond_id, conj_dbond_id from directed_bonds where frame % {STEP} = 0", con)
    con.close()
    conj = db[["frame", "dbond_id", "cell_id"]].rename(columns={"dbond_id": "conj_dbond_id", "cell_id": "nb"})
    pairs = db.merge(conj, on=["frame", "conj_dbond_id"])
    pairs = pairs[pairs.cell_id != MARGIN]
    nb = pairs.groupby(["frame", "cell_id"]).agg(n=("nb", "nunique"), touches_margin=("nb", lambda s: (s == MARGIN).any())).reset_index()
    df = cells.merge(nb, on=["frame", "cell_id"])
    df = df[~df.touches_margin].copy()
    df["rel_area"] = df.area / df.groupby("frame").area.transform("median")
    rho, p = stats.spearmanr(df.rel_area, df.n)
    cls = df[df.n.between(4, 8)].groupby("n").rel_area.agg(["mean", "size"]).reset_index()
    cls = cls[cls["size"] >= 50]
    means = cls["mean"].values
    monotone = bool(len(cls) == 5 and np.all(np.diff(means) > 0))
    slope, intercept, r, _, _ = stats.linregress(cls.n, cls["mean"])
    k = float(np.sum(cls["mean"] * (cls.n - 2)) / np.sum((cls.n - 2) ** 2))  # area = k (n - 2), through the origin
    r2_lewis = float(1 - np.sum((cls["mean"] - k * (cls.n - 2)) ** 2) / np.sum((cls["mean"] - cls["mean"].mean()) ** 2))
    cls.round(4).to_csv(os.path.join(DERIVED, f"{name}_class_means.csv"), index=False)
    return dict(tissue=name, stage=kind, frames_used=int(df.frame.nunique()), cell_frames=int(len(df)),
                mean_n=round(float(df.n.mean()), 4), sd_n=round(float(df.n.std(ddof=0)), 4), f6=round(float((df.n == 6).mean()), 4),
                rho_area_n=round(float(rho), 3), p_area_n=float(f"{p:.1e}"),
                class_mean_rel_area={int(a): round(float(b), 4) for a, b in zip(cls.n, cls["mean"])}, class_counts={int(a): int(b) for a, b in zip(cls.n, cls["size"])},
                monotone_4_to_8=monotone, slope_per_side=round(float(slope), 4), intercept=round(float(intercept), 4), r2_linear=round(float(r ** 2), 4),
                lewis_k=round(k, 4), r2_lewis_n_minus_2=round(r2_lewis, 4), file_sha256=sha(archive), file_byte_size=os.path.getsize(archive))


def main():
    rows = []
    for t in TISSUES:
        r = analyse(*t)
        rows.append(r)
        print(json.dumps(r), file=sys.stderr)
    ok = [5.85 <= r["mean_n"] <= 6.15 and r["rho_area_n"] >= 0.3 and r["monotone_4_to_8"] for r in rows]
    bad = [r["rho_area_n"] < 0.1 or not r["monotone_4_to_8"] for r in rows]
    outside = [not (5.7 <= r["mean_n"] <= 6.3) for r in rows]
    out = dict(tissues=rows, verdict_counts=dict(tissues_all_conditions=int(sum(ok)), tissues_rho_lt_0_1_or_nonmonotone=int(sum(bad)), tissues_mean_n_outside_5_7_6_3=int(sum(outside))),
               median_rho_area_n=round(float(np.median([r["rho_area_n"] for r in rows])), 3), median_mean_n=round(float(np.median([r["mean_n"] for r in rows])), 4),
               median_r2_linear=round(float(np.median([r["r2_linear"] for r in rows])), 4), median_r2_lewis=round(float(np.median([r["r2_lewis_n_minus_2"] for r in rows])), 4))
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
