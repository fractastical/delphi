#!/usr/bin/env python3
"""Pupal-wing run of thompson1917-ch07-09: does the hexagon pattern appear once division stops?

Data: the three wild-type Drosophila pupal wing time-lapses of Etournay et al. 2015 (eLife 4:e07090),
distributed as TissueMiner databases with Etournay et al. 2016 (eLife 5:e14334) from
http://bds.mpi-cbg.de/tissue_miner/WT_{1,2,3}.tar.gz (E-cadherin-GFP, 5 min frames, ~16-32 h APF).
Same TissueMiner schema as the Dye et al. wing-disc data used in the first run (../analysis.py).

Per frame: interior cells (no bond with margin cell 10000), neighbour number n, area; f6, mean/SD n,
CV of area, division rate (cells appearing by division in the frame, per hour per 1,000 interior
cells); every 20th frame the chord angles at interior three-way junctions. Per wing: f6 in the first
and last 2 h, Spearman rho of f6 against division rate and against CV_A across frames.

Run: python3 analysis.py  (downloads ~2.2 GB into ./data/ if absent, writes ./derived/)
"""
import datetime, hashlib, json, os, sqlite3, sys, tarfile
import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
WINGS = ["WT_1", "WT_2", "WT_3"]
MARGIN = 10000
ANGLE_STEP = 20


def fetch(wing):
    path = os.path.join(DATA, f"{wing}.tar.gz")
    url = f"http://bds.mpi-cbg.de/tissue_miner/{wing}.tar.gz"
    if not os.path.exists(path):
        import requests
        with requests.get(url, stream=True, timeout=900) as r:
            r.raise_for_status()
            with open(path, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        open(path[:-7] + ".retrieved", "w").write(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 24), b""):
            h.update(chunk)
    stamp = path[:-7] + ".retrieved"
    return dict(download_url=url, retrieved_at=open(stamp).read().strip() if os.path.exists(stamp) else None,
                byte_size=os.path.getsize(path), sha256=h.hexdigest())


def sqlite_path(wing):
    out = os.path.join(DATA, "example_data", wing, f"{wing}.sqlite")
    if not os.path.exists(out):
        with tarfile.open(os.path.join(DATA, f"{wing}.tar.gz")) as t:
            t.extract(f"example_data/{wing}/{wing}.sqlite", DATA)
    return out


def chord_angles(con, frames_sel):
    q = "select frame, dbond_id, vertex_id, left_dbond_id, cell_id from directed_bonds where frame in (%s)" % ",".join(map(str, frames_sel))
    full = pd.read_sql(q, con)
    verts = pd.read_sql("select frame, vertex_id, x_pos, y_pos from vertices where frame in (%s)" % ",".join(map(str, frames_sel)), con)
    out = {}
    for fr, g in full.groupby("frame"):
        v = verts[verts.frame == fr].set_index("vertex_id")
        end = g.set_index("dbond_id").vertex_id
        g = g.assign(end_vertex=g.left_dbond_id.map(end)).dropna(subset=["end_vertex"])
        dx = v.x_pos.reindex(g.end_vertex.astype(int)).values - v.x_pos.reindex(g.vertex_id).values
        dy = v.y_pos.reindex(g.end_vertex.astype(int)).values - v.y_pos.reindex(g.vertex_id).values
        g = g.assign(theta=np.degrees(np.arctan2(dy, dx)))
        bad = set(g[g.cell_id == MARGIN].vertex_id)
        ok = []
        for vid, grp in g.groupby("vertex_id"):
            if vid in bad or len(grp) != 3:
                continue
            th = np.sort(grp.theta.values)
            ok.append(np.diff(np.append(th, th[0] + 360)))
        a = np.array(ok)
        out[fr] = dict(n_junctions=int(len(a)), sd=float(a.std()), all_three_within_15=float((np.abs(a - 120) <= 15).all(axis=1).mean()))
    return out


def analyse_wing(wing):
    con = sqlite3.connect(sqlite_path(wing))
    frames = pd.read_sql("select frame, time_sec from frames", con)
    cells = pd.read_sql("select frame, cell_id, area from cells", con)
    db = pd.read_sql("select frame, cell_id, dbond_id, conj_dbond_id, vertex_id from directed_bonds", con)
    hist = pd.read_sql("select cell_id, first_occ, appears_by from cell_histories", con)
    conj = db[["frame", "dbond_id", "cell_id"]].rename(columns={"dbond_id": "conj_dbond_id", "cell_id": "nb"})
    pairs = db.merge(conj, on=["frame", "conj_dbond_id"])
    pairs = pairs[pairs.cell_id != MARGIN]
    nb = pairs.groupby(["frame", "cell_id"]).agg(n=("nb", "nunique"), touches_margin=("nb", lambda s: (s == MARGIN).any())).reset_index()
    df = cells.merge(nb, on=["frame", "cell_id"]).merge(frames, on="frame").merge(hist, on="cell_id", how="left")
    df = df[~df.touches_margin].copy()
    df["time_h"] = df.time_sec / 3600
    df["rel_area"] = df.area / df.groupby("frame").area.transform("median")
    df["born_here"] = (df.appears_by == "Division") & (df.first_occ == df.frame)

    margin_vertices = set(db[db.cell_id == MARGIN][["frame", "vertex_id"]].itertuples(index=False, name=None))
    deg = db.groupby(["frame", "vertex_id"]).size().reset_index(name="deg")
    deg = deg[[(f, v) not in margin_vertices for f, v in zip(deg.frame, deg.vertex_id)]]
    three_way = float((deg.deg == 3).mean())

    dt_h = frames.time_sec.diff().median() / 3600
    pf = df.groupby("frame").apply(lambda g: pd.Series(dict(
        time_h=g.time_h.iloc[0], n_cells=len(g), f6=(g.n == 6).mean(), mean_n=g.n.mean(), sd_n=g.n.std(ddof=0),
        cv_area=g.area.std(ddof=0) / g.area.mean(), births=int(g.born_here.sum())))).reset_index()
    pf["division_rate"] = pf.births / dt_h / pf.n_cells * 1000  # divisions per hour per 1,000 cells
    pf["div_rate_smooth"] = pf.division_rate.rolling(12, center=True, min_periods=6).mean()
    T = pf.time_h.max()
    first, last = pf[pf.time_h <= 2], pf[pf.time_h >= T - 2]
    rho_div, p_div = stats.spearmanr(pf.f6, pf.div_rate_smooth, nan_policy="omit")
    rho_cv, p_cv = stats.spearmanr(pf.f6, pf.cv_area)
    rho_t, p_t = stats.spearmanr(pf.time_h, pf.f6)

    sel = sorted(set(range(0, int(frames.frame.max()) + 1, ANGLE_STEP)) | {int(frames.frame.max())})
    ang = chord_angles(con, sel)
    con.close()
    sel = [f for f in sel if f in ang]  # frames with no bonds in the database are skipped
    early = [ang[f] for f in sel if frames.time_sec[frames.frame == f].iloc[0] <= 2 * 3600]
    late = [ang[f] for f in sel if frames.time_sec[frames.frame == f].iloc[0] >= (T - 2) * 3600]
    wmean = lambda L, k: float(np.average([d[k] for d in L], weights=[d["n_junctions"] for d in L])) if L else float("nan")

    poly = df.n.clip(upper=9).value_counts(normalize=True).sort_index()
    poly_last = last.frame.pipe(lambda fr: df[df.frame.isin(fr)].n.clip(upper=9).value_counts(normalize=True).sort_index())
    fmt = lambda s: {str(k) if k < 9 else "9+": round(float(v), 4) for k, v in s.items()}
    rho_a, _ = stats.spearmanr(df.rel_area, df.n)

    pf.round(4).to_csv(os.path.join(DERIVED, f"{wing}_per_frame.csv"), index=False)
    pd.DataFrame([dict(frame=f, time_h=float(frames.time_sec[frames.frame == f].iloc[0]) / 3600, **ang[f]) for f in sel]).round(4).to_csv(os.path.join(DERIVED, f"{wing}_angles.csv"), index=False)
    return dict(
        wing=wing, frames=int(len(frames)), duration_h=round(float(T), 2), cell_frames=int(len(df)),
        cells_first_2h=round(float(first.n_cells.mean()), 1), cells_last_2h=round(float(last.n_cells.mean()), 1),
        f6_first_2h=round(float(first.f6.mean()), 4), f6_last_2h=round(float(last.f6.mean()), 4), f6_change=round(float(last.f6.mean() - first.f6.mean()), 4),
        f6_max_frame=round(float(pf.f6.max()), 4), f6_all=round(float((df.n == 6).mean()), 4),
        mean_n_last_2h=round(float(last.mean_n.mean()), 4), sd_n_first_2h=round(float(first.sd_n.mean()), 4), sd_n_last_2h=round(float(last.sd_n.mean()), 4),
        cv_area_first_2h=round(float(first.cv_area.mean()), 3), cv_area_last_2h=round(float(last.cv_area.mean()), 3),
        division_rate_first_2h=round(float(first.division_rate.mean()), 2), division_rate_last_2h=round(float(last.division_rate.mean()), 2),
        divisions_total=int((hist.appears_by == "Division").sum()),
        three_way_vertex_fraction=round(three_way, 4),
        rho_f6_time=round(float(rho_t), 3), p_f6_time=float(f"{p_t:.2e}"),
        rho_f6_division_rate=round(float(rho_div), 3), p_f6_division_rate=float(f"{p_div:.2e}"),
        rho_f6_cv_area=round(float(rho_cv), 3), p_f6_cv_area=float(f"{p_cv:.2e}"),
        rho_n_relarea_all=round(float(rho_a), 3),
        junction_all_three_within_15_first_2h=round(wmean(early, "all_three_within_15"), 4),
        junction_all_three_within_15_last_2h=round(wmean(late, "all_three_within_15"), 4),
        junction_angle_sd_first_2h=round(wmean(early, "sd"), 2), junction_angle_sd_last_2h=round(wmean(late, "sd"), 2),
        polygon_distribution_all=fmt(poly), polygon_distribution_last_2h=fmt(poly_last))


def main():
    files = [fetch(w) for w in WINGS]
    wings = []
    for w in WINGS:
        r = analyse_wing(w)
        wings.append(r)
        print(json.dumps(r), file=sys.stderr)
    last = np.array([w["f6_last_2h"] for w in wings]); chg = np.array([w["f6_change"] for w in wings])
    counts = dict(
        wings_supports=int(((last >= 0.60) & (chg >= 0.10) & (np.array([w["three_way_vertex_fraction"] for w in wings]) >= 0.95)).sum()),
        wings_f6_last_lt_0_50=int((last < 0.50).sum()), wings_f6_fell_ge_0_05=int((chg <= -0.05).sum()),
        wings_rho_div_le_minus_0_3=int(sum(w["rho_f6_division_rate"] <= -0.3 for w in wings)),
        wings_rho_cv_le_minus_0_3=int(sum(w["rho_f6_cv_area"] <= -0.3 for w in wings)),
        wings_junctions_more_regular_late=int(sum(w["junction_all_three_within_15_last_2h"] > w["junction_all_three_within_15_first_2h"] for w in wings)))
    out = dict(files=files, wings=wings, verdict_counts=counts, median_f6_last_2h=round(float(np.median(last)), 4), median_f6_change=round(float(np.median(chg)), 4))
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
