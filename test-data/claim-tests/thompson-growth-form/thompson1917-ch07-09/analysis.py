#!/usr/bin/env python3
"""Test of thompson1917-ch07-09: similar-sized cells in complete contact under a uniform force
form a pattern of hexagons (six neighbours, 120 degree junctions).

Data: Dye et al. 2026, Zenodo 10.5281/zenodo.22760592 (CC BY 4.0). Five ex vivo cultured
Drosophila wing imaginal discs (E-cadherin-GFP, 5 min intervals, ~13 h), segmented and
tracked with TissueAnalyzer (manually corrected) and stored as TissueMiner SQLite databases
(tables cells, directed_bonds, vertices, cell_histories, frames). Cell id 10000 is the
margin (background) cell of TissueMiner.

Per movie and frame: every tracked cell's number of distinct neighbours (from directed bonds and
their conjugates), its area, and whether it appeared by division within the preceding 60 min.
Interior cells = cells that do not share a bond with the margin cell. Statistics follow the
pre-registered result.json: time-averaged fraction of six-sided cells f6, mean/SD neighbour
number, Spearman rho(f6, time), CV of cell area, fraction of three-way interior vertices, and
the division-history diagnostic. A Poisson-Voronoi partition is the random baseline.

Run: python3 analysis.py   (expects the five Zenodo zips in ./data/ or downloads them, ~2.9 GB;
writes ./derived/ and prints the numbers that go into result.json)
"""
import datetime, hashlib, json, os, sqlite3, sys, zipfile
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import Voronoi

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

RECORD = "22760592"
MOVIES = ["Ecd_20141010_P2", "Ecd_20150310_P2", "Ecd_20150418_P1", "Ecd_20150608_P1", "Ecd_20161213_F0"]
MARGIN = 10000
RECENT_SEC = 3600


def fetch(movie):
    path = os.path.join(DATA, f"{movie}.zip")
    url = f"https://zenodo.org/api/records/{RECORD}/files/{movie}.zip/content"
    if not os.path.exists(path):
        import requests
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        open(path + ".retrieved", "w").write(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    stamp = os.path.join(DATA, f"{movie}.retrieved")
    retrieved = open(stamp).read().strip() if os.path.exists(stamp) else None
    return dict(download_url=url, retrieved_at=retrieved, byte_size=os.path.getsize(path), sha256=h.hexdigest())


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


def analyse_movie(movie):
    con = sqlite3.connect(sqlite_path(movie))
    frames = pd.read_sql("select frame, time_sec from frames", con)
    cells = pd.read_sql("select frame, cell_id, area from cells", con)
    db = pd.read_sql("select frame, cell_id, dbond_id, conj_dbond_id, vertex_id from directed_bonds", con)
    hist = pd.read_sql("select cell_id, first_occ, appears_by from cell_histories", con)
    con.close()

    # neighbour of each directed bond = owner of its conjugate bond
    conj = db[["frame", "dbond_id", "cell_id"]].rename(columns={"dbond_id": "conj_dbond_id", "cell_id": "nb"})
    pairs = db.merge(conj, on=["frame", "conj_dbond_id"], how="inner")
    pairs = pairs[pairs.cell_id != MARGIN]
    nb = pairs.groupby(["frame", "cell_id"]).agg(n=("nb", "nunique"), touches_margin=("nb", lambda s: (s == MARGIN).any())).reset_index()
    df = cells.merge(nb, on=["frame", "cell_id"]).merge(frames, on="frame").merge(hist, on="cell_id", how="left")
    df = df[~df.touches_margin].copy()
    t0 = frames.set_index("frame").time_sec
    df["born_sec"] = df.first_occ.map(t0)
    df["recent_division"] = (df.appears_by == "Division") & (df.time_sec - df.born_sec <= RECENT_SEC)
    df["rel_area"] = df.area / df.groupby("frame").area.transform("median")

    # vertex degree among vertices not touched by a margin bond
    margin_vertices = set(db[db.cell_id == MARGIN][["frame", "vertex_id"]].itertuples(index=False, name=None))
    deg = db.groupby(["frame", "vertex_id"]).size().reset_index(name="deg")
    deg = deg[[(f, v) not in margin_vertices for f, v in zip(deg.frame, deg.vertex_id)]]
    three_way = float((deg.deg == 3).mean())

    per_frame = df.groupby("frame").apply(lambda g: pd.Series(dict(
        time_h=g.time_sec.iloc[0] / 3600, n_cells=len(g), f6=(g.n == 6).mean(), mean_n=g.n.mean(),
        sd_n=g.n.std(ddof=0), cv_area=g.area.std(ddof=0) / g.area.mean(),
        frac_recent=g.recent_division.mean()))).reset_index()
    rho_t, p_t = stats.spearmanr(per_frame.time_h, per_frame.f6)

    poly = df.n.clip(upper=9).value_counts(normalize=True).sort_index()
    poly = {str(k) if k < 9 else "9+": round(float(v), 4) for k, v in poly.items()}

    recent, other = df[df.recent_division], df[~df.recent_division]
    rho_a, p_a = stats.spearmanr(other.rel_area, other.n)
    rho_a_all, _ = stats.spearmanr(df.rel_area, df.n)

    # Not pre-registered, sensitivity: division effect at matched relative area (quintiles of rel_area)
    df["area_bin"] = pd.qcut(df.rel_area, 5, labels=False, duplicates="drop")
    binned = df.groupby(["area_bin", "recent_division"]).n.mean().unstack()
    gap_matched = float((binned[True] - binned[False]).mean()) if True in binned.columns else float("nan")

    # Not pre-registered: junction angles at interior three-way vertices, every 20th frame.
    # Each directed bond runs from its vertex to the vertex of its left_dbond (next bond around the cell).
    angles = []
    full = pd.read_sql("select frame, dbond_id, vertex_id, left_dbond_id, cell_id from directed_bonds where frame % 20 = 0", sqlite3.connect(sqlite_path(movie)))
    verts = pd.read_sql("select frame, vertex_id, x_pos, y_pos from vertices where frame % 20 = 0", sqlite3.connect(sqlite_path(movie)))
    for fr, g in full.groupby("frame"):
        v = verts[verts.frame == fr].set_index("vertex_id")
        end = g.set_index("dbond_id").vertex_id
        g = g.assign(end_vertex=g.left_dbond_id.map(end))
        g = g.dropna(subset=["end_vertex"])
        g["dx"] = v.x_pos.reindex(g.end_vertex.astype(int)).values - v.x_pos.reindex(g.vertex_id).values
        g["dy"] = v.y_pos.reindex(g.end_vertex.astype(int)).values - v.y_pos.reindex(g.vertex_id).values
        g["theta"] = np.degrees(np.arctan2(g.dy, g.dx))
        bad = set(g[g.cell_id == MARGIN].vertex_id)
        for vid, grp in g.groupby("vertex_id"):
            if vid in bad or len(grp) != 3:
                continue
            th = np.sort(grp.theta.values)
            d = np.diff(np.append(th, th[0] + 360))
            angles.extend(d.tolist())
    angles = np.array(angles)
    angle_stats = dict(n_angles=int(len(angles)), mean=round(float(angles.mean()), 2), sd=round(float(angles.std()), 2),
                       within_15_of_120=round(float((np.abs(angles - 120) <= 15).mean()), 4),
                       junctions_all_three_within_15=round(float((np.abs(angles.reshape(-1, 3) - 120) <= 15).all(axis=1).mean()), 4))

    summary = dict(
        movie=movie, frames=int(len(frames)), duration_h=round(float(frames.time_sec.max() / 3600), 2),
        cell_frames=int(len(df)), cells_per_frame=round(float(per_frame.n_cells.mean()), 1),
        f6=round(float(per_frame.f6.mean()), 4), f6_first_hour=round(float(per_frame[per_frame.time_h <= 1].f6.mean()), 4),
        f6_last_hour=round(float(per_frame[per_frame.time_h >= per_frame.time_h.max() - 1].f6.mean()), 4),
        mean_n=round(float(df.n.mean()), 4), sd_n=round(float(df.n.std(ddof=0)), 4),
        rho_f6_time=round(float(rho_t), 3), p_f6_time=float(f"{p_t:.2e}"),
        cv_area=round(float(per_frame.cv_area.mean()), 3), three_way_vertex_fraction=round(three_way, 4),
        polygon_distribution=poly,
        divisions=int((hist.appears_by == "Division").sum()),
        recent_division_cell_frames=int(len(recent)), mean_n_recent_division=round(float(recent.n.mean()), 3),
        mean_n_other=round(float(other.n.mean()), 3), f6_recent_division=round(float((recent.n == 6).mean()), 4),
        f6_other=round(float((other.n == 6).mean()), 4),
        rho_n_relarea_other=round(float(rho_a), 3), rho_n_relarea_all=round(float(rho_a_all), 3),
        sensitivity_gap_recent_minus_other_at_matched_area=round(gap_matched, 3),
        sensitivity_junction_angles=angle_stats,
    )
    per_frame.round(4).to_csv(os.path.join(DERIVED, f"{movie}_per_frame.csv"), index=False)
    return summary


def poisson_voronoi(n=20000, seed=0):
    rng = np.random.default_rng(seed)
    pts = rng.random((n, 2))
    vor = Voronoi(pts)
    interior = (pts[:, 0] > 0.1) & (pts[:, 0] < 0.9) & (pts[:, 1] > 0.1) & (pts[:, 1] < 0.9)
    nbs = np.zeros(n, int)
    for a, b in vor.ridge_points:
        nbs[a] += 1
        nbs[b] += 1
    areas = []
    for i in np.where(interior)[0]:
        reg = vor.regions[vor.point_region[i]]
        poly = vor.vertices[reg]
        x, y = poly[:, 0], poly[:, 1]
        areas.append(0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1))))
    areas = np.array(areas)
    k = nbs[interior]
    return dict(f6=round(float((k == 6).mean()), 4), mean_n=round(float(k.mean()), 4), sd_n=round(float(k.std()), 4),
                cv_area=round(float(areas.std() / areas.mean()), 3), n=int(interior.sum()))


def main():
    files, movies = [], []
    for m in MOVIES:
        files.append(fetch(m))
        s = analyse_movie(m)
        movies.append(s)
        print(json.dumps(s), file=sys.stderr)
    base = poisson_voronoi()
    f6s = np.array([m["f6"] for m in movies])
    rhos = np.array([m["rho_f6_time"] for m in movies])
    ps = np.array([m["p_f6_time"] for m in movies])
    verdict_counts = dict(
        movies_f6_ge_0_60=int((f6s >= 0.60).sum()), movies_f6_lt_0_50=int((f6s < 0.50).sum()),
        movies_rho_ge_0=int((rhos >= 0).sum()), movies_rho_lt_minus_0_3_sig=int(((rhos < -0.3) & (ps < 0.05)).sum()),
        movies_cv_area_ge_0_6=int(sum(m["cv_area"] >= 0.6 for m in movies)),
        movies_mean_n_in_5_8_6_2=int(sum(5.8 <= m["mean_n"] <= 6.2 for m in movies)),
        movies_three_way_ge_0_95=int(sum(m["three_way_vertex_fraction"] >= 0.95 for m in movies)))
    out = dict(files=files, movies=movies, poisson_voronoi_baseline=base, verdict_counts=verdict_counts,
               median_f6=round(float(np.median(f6s)), 4),
               pooled_mean_n_recent_minus_other=round(float(np.mean([m["mean_n_recent_division"] - m["mean_n_other"] for m in movies])), 3))
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
