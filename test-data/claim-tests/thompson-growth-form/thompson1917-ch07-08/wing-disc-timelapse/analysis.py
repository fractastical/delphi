#!/usr/bin/env python3
"""Within-tissue run of thompson1917-ch07-08: regular hexagons only where cells are uniform in size
and forces uniform, tested inside the proliferating Drosophila wing disc.

Data: Dye et al. 2026, Zenodo 10.5281/zenodo.22760592 (CC BY 4.0), five TissueMiner databases,
shared with ../../thompson1917-ch07-09/data/ (downloaded and checksummed by that test's analysis.py).

Every 10th frame, for each interior cell (no margin bond, no margin-touching neighbour):
  n      = number of distinct neighbours
  CV_nb  = CV of area over the neighbours, excluding the cell itself   (size clause)
  E_loc  = mean |elongation| over the cell and its neighbours          (force clause)
Pooled per movie, cut into deciles; f6 per decile; lowest-minus-highest gap and Spearman rho over
decile ranks. Poisson-Voronoi partition as the non-biological null.

Run: python3 analysis.py
"""
import hashlib, json, os, sqlite3, sys, zipfile
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import Voronoi

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "..", "thompson1917-ch07-09", "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
MOVIES = ["Ecd_20141010_P2", "Ecd_20150310_P2", "Ecd_20150418_P1", "Ecd_20150608_P1", "Ecd_20161213_F0"]
MARGIN = 10000
STEP = 10
RECORD = "22760592"


def file_meta(movie):
    path = os.path.join(DATA, f"{movie}.zip")
    if not os.path.exists(path):
        sys.exit(f"missing {path}: run ../../thompson1917-ch07-09/analysis.py first")
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    stamp = path[:-4] + ".retrieved"
    return dict(download_url=f"https://zenodo.org/api/records/{RECORD}/files/{movie}.zip/content",
                retrieved_at=open(stamp).read().strip() if os.path.exists(stamp) else None,
                byte_size=os.path.getsize(path), sha256=h.hexdigest())


def sqlite_path(movie):
    out_dir = os.path.join(DATA, f"db_{movie[4:12]}")
    os.makedirs(out_dir, exist_ok=True)
    with zipfile.ZipFile(os.path.join(DATA, f"{movie}.zip")) as z:
        member = [m for m in z.namelist() if m.endswith(".sqlite")][0]
        out = os.path.join(out_dir, os.path.basename(member))
        if not os.path.exists(out):
            with z.open(member) as src, open(out, "wb") as dst:
                for chunk in iter(lambda: src.read(1 << 24), b""):
                    dst.write(chunk)
    return out


def local_table(cells, db):
    """Per (frame, cell): n, CV_nb, E_loc for interior cells with interior neighbours."""
    conj = db[["frame", "dbond_id", "cell_id"]].rename(columns={"dbond_id": "conj_dbond_id", "cell_id": "nb"})
    pairs = db.merge(conj, on=["frame", "conj_dbond_id"])[["frame", "cell_id", "nb"]].drop_duplicates()
    pairs = pairs[pairs.cell_id != MARGIN]
    touches = pairs[pairs.nb == MARGIN][["frame", "cell_id"]].assign(edge=True)
    pairs = pairs[pairs.nb != MARGIN]
    cells = cells.assign(elong=np.hypot(cells.elong_xx, cells.elong_xy))
    nbinfo = cells.rename(columns={"cell_id": "nb", "area": "nb_area", "elong": "nb_elong"})[["frame", "nb", "nb_area", "nb_elong"]]
    pairs = pairs.merge(nbinfo, on=["frame", "nb"]).merge(touches.rename(columns={"cell_id": "nb"}), on=["frame", "nb"], how="left")
    g = pairs.groupby(["frame", "cell_id"])
    loc = g.agg(n=("nb", "size"), nb_mean=("nb_area", "mean"), nb_sd=("nb_area", lambda s: s.std(ddof=0)),
                nb_elong=("nb_elong", "mean"), any_edge_nb=("edge", lambda s: s.notna().any())).reset_index()
    loc = loc.merge(cells[["frame", "cell_id", "area", "elong"]], on=["frame", "cell_id"])
    loc = loc.merge(touches, on=["frame", "cell_id"], how="left")
    loc = loc[loc.edge.isna() & ~loc.any_edge_nb & (loc.n >= 3)].copy()
    loc["cv_nb"] = loc.nb_sd / loc.nb_mean
    loc["e_loc"] = (loc.nb_elong * loc.n + loc.elong) / (loc.n + 1)
    return loc[["frame", "cell_id", "n", "area", "cv_nb", "e_loc"]]


def decile_stats(loc, col):
    loc = loc.assign(dec=pd.qcut(loc[col].rank(method="first"), 10, labels=False))
    d = loc.groupby("dec").agg(f6=("n", lambda s: (s == 6).mean()), sd_n=("n", lambda s: s.std(ddof=0)),
                               lo=(col, "min"), hi=(col, "max"), count=("n", "size")).reset_index()
    rho, p = stats.spearmanr(d.dec, d.f6)
    return dict(gap=round(float(d.f6.iloc[0] - d.f6.iloc[-1]), 4), rho=round(float(rho), 3), p=float(f"{p:.2e}"),
                f6_lowest=round(float(d.f6.iloc[0]), 4), f6_highest=round(float(d.f6.iloc[-1]), 4),
                deciles=d.round(4).to_dict(orient="records"))


def analyse_movie(movie):
    con = sqlite3.connect(sqlite_path(movie))
    cells = pd.read_sql(f"select frame, cell_id, area, elong_xx, elong_xy from cells where frame % {STEP} = 0", con)
    db = pd.read_sql(f"select frame, cell_id, dbond_id, conj_dbond_id from directed_bonds where frame % {STEP} = 0", con)
    con.close()
    loc = local_table(cells, db)
    size = decile_stats(loc, "cv_nb")
    force = decile_stats(loc, "e_loc")
    rho_cell, _ = stats.spearmanr(loc.cv_nb, (loc.n - 6).abs())
    rho_cell_e, _ = stats.spearmanr(loc.e_loc, (loc.n - 6).abs())
    pd.DataFrame(size["deciles"]).assign(movie=movie, clause="size").to_csv(os.path.join(DERIVED, f"{movie}_cv_deciles.csv"), index=False)
    pd.DataFrame(force["deciles"]).assign(movie=movie, clause="force").to_csv(os.path.join(DERIVED, f"{movie}_elong_deciles.csv"), index=False)
    return dict(movie=movie, frames_used=int(loc.frame.nunique()), cell_frames=int(len(loc)), f6_all=round(float((loc.n == 6).mean()), 4),
                size_clause={k: v for k, v in size.items() if k != "deciles"},
                force_clause={k: v for k, v in force.items() if k != "deciles"},
                rho_cv_nb_vs_abs_n_minus_6=round(float(rho_cell), 3), rho_e_loc_vs_abs_n_minus_6=round(float(rho_cell_e), 3),
                cv_nb_decile_bounds=[round(float(x), 3) for x in pd.DataFrame(size["deciles"]).hi],
                e_loc_decile_bounds=[round(float(x), 3) for x in pd.DataFrame(force["deciles"]).hi])


def poisson_voronoi(n=40000, seed=1):
    rng = np.random.default_rng(seed)
    pts = rng.random((n, 2))
    vor = Voronoi(pts)
    nb = [[] for _ in range(n)]
    for a, b in vor.ridge_points:
        nb[a].append(b); nb[b].append(a)
    areas = np.full(n, np.nan)
    for i in range(n):
        reg = vor.regions[vor.point_region[i]]
        if -1 in reg or not reg:
            continue
        poly = vor.vertices[reg]
        areas[i] = 0.5 * abs(np.dot(poly[:, 0], np.roll(poly[:, 1], 1)) - np.dot(poly[:, 1], np.roll(poly[:, 0], 1)))
    inside = (pts[:, 0] > 0.1) & (pts[:, 0] < 0.9) & (pts[:, 1] > 0.1) & (pts[:, 1] < 0.9)
    rows = []
    for i in np.where(inside)[0]:
        a = areas[nb[i]]
        if np.isnan(a).any():
            continue
        rows.append((len(nb[i]), a.std() / a.mean()))
    loc = pd.DataFrame(rows, columns=["n", "cv_nb"])
    s = decile_stats(loc, "cv_nb")
    return dict(cells=int(len(loc)), f6_all=round(float((loc.n == 6).mean()), 4), **{k: v for k, v in s.items() if k != "deciles"})


def main():
    files = [file_meta(m) for m in MOVIES]
    movies = []
    for m in MOVIES:
        r = analyse_movie(m)
        movies.append(r)
        print(json.dumps(r), file=sys.stderr)
    null = poisson_voronoi()
    gaps = np.array([m["size_clause"]["gap"] for m in movies])
    rhos = np.array([m["size_clause"]["rho"] for m in movies])
    fgaps = np.array([m["force_clause"]["gap"] for m in movies])
    counts = dict(movies_size_supports=int(((gaps >= 0.10) & (rhos <= -0.3)).sum()),
                  movies_size_refutes=int((gaps < 0.05).sum()),
                  movies_force_gap_ge_0_05=int((fgaps >= 0.05).sum()), movies_force_reversed=int((fgaps < 0).sum()))
    out = dict(files=files, movies=movies, poisson_voronoi_null=null, verdict_counts=counts,
               median_size_gap=round(float(np.median(gaps)), 4), median_force_gap=round(float(np.median(fgaps)), 4),
               median_f6_most_uniform_decile=round(float(np.median([m["size_clause"]["f6_lowest"] for m in movies])), 4))
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
