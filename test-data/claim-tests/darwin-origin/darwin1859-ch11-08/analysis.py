#!/usr/bin/env python3
"""Test darwin1859-ch11-08: separate continents and oceanic islands were not joined by land during
the period of existing species.

Data: NOAA NCEI ETOPO 2022 (60 arc-second surface elevation) fetched from the NCEI THREDDS NetCDF
Subset Service in six 60-degree longitude bands with horizStride=6, giving a 0.1-degree global grid
(1800 x 3600, nearest-sample subsampling). Cells with elevation >= -130 m are labelled into connected
components (4-connectivity, longitude wrap). Oceanic islands and continental gaps are tested for
connection to continent seed cells listed in derived/sites.csv.
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import ndimage
from scipy.io import netcdf_file

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

NCSS = ("https://www.ngdc.noaa.gov/thredds/ncss/grid/global/ETOPO2022/60s/60s_surface_elev_netcdf/"
        "ETOPO_2022_v1_60s_N90W180_surface.nc")
BANDS = [(-179.99, -120.0), (-119.99, -60.0), (-59.99, 0.0), (0.01, 60.0), (60.01, 120.0), (120.01, 179.99)]
LOWSTAND = -130.0
STEP = 0.1
R_EARTH_KM = 6371.0
FILES = []


def get_cached(url, cache_name, role):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=900)
                if r.status_code == 200 and r.content[:3] == b"CDF":
                    break
            except requests.RequestException:
                pass
            time.sleep(3 * 2 ** attempt)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    FILES.append({"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
                  "sha256": hashlib.sha256(content).hexdigest(), "role": role})
    return path


def load_grid():
    lats = None
    cols = {}
    for west, east in BANDS:
        url = (f"{NCSS}?var=z&north=89.99&south=-89.99&west={west}&east={east}&horizStride=6&accept=netcdf3")
        path = get_cached(url, f"etopo2022_60s_stride6_{west}_{east}.nc", f"ETOPO 2022 60s surface, 0.1-degree subsample, lon {west} to {east}")
        f = netcdf_file(path, "r", mmap=False)
        z = np.array(f.variables["z"][:], dtype=np.float32)
        lat = np.array(f.variables["lat"][:], dtype=float)
        lon = np.array(f.variables["lon"][:], dtype=float)
        f.close()
        if lats is None:
            lats = lat
        assert np.allclose(lats, lat)
        for j, lo in enumerate(lon):
            k = int(round((lo + 180.0 - STEP / 2) / STEP)) % 3600
            cols[k] = z[:, j]
    assert len(cols) == 3600, len(cols)
    Z = np.stack([cols[k] for k in range(3600)], axis=1)
    lons = -180.0 + STEP / 2 + STEP * np.arange(3600)
    return lats, lons, Z


def label_wrap(mask):
    lab, n = ndimage.label(mask)
    parent = np.arange(n + 1)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    l0, l1 = lab[:, 0], lab[:, -1]
    sel = (l0 > 0) & (l1 > 0)
    for a, b in set(zip(l0[sel].tolist(), l1[sel].tolist())):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra
    roots = np.array([find(i) for i in range(n + 1)])
    return roots[lab]


def cell_of(lat, lon, lats, lons):
    return int(np.argmin(np.abs(lats - lat))), int(np.argmin(np.abs(lons - lon)))


def nearest_land_cell(i, j, land, radius):
    """Nearest present-day land cell (z >= 0) to (i, j) within +-radius cells, or None."""
    best = None
    ni, nj = land.shape
    for di in range(-radius, radius + 1):
        for dj in range(-radius, radius + 1):
            ii, jj = i + di, (j + dj) % nj
            if 0 <= ii < ni and land[ii, jj]:
                d = di * di + dj * dj
                if best is None or d < best[0]:
                    best = (d, ii, jj)
    return None if best is None else (best[1], best[2], best[0] ** 0.5)


def cell_area_km2(lats):
    return (np.deg2rad(STEP) * R_EARTH_KM) ** 2 * np.cos(np.deg2rad(lats))


def connected(Z, thr, a, b, region=None):
    """True if cell a shares an emergent component (Z >= thr, within region) with cell b or any cell in list b."""
    mask = Z >= thr
    if region is not None:
        mask &= region
    lab = label_wrap(mask)
    la = lab[a]
    targets = b if isinstance(b, list) else [b]
    return la > 0 and any(lab[t] == la for t in targets)


def sill_depth(Z, a, b, region=None, lo=-6000.0, hi=0.0):
    """Shallowest threshold (m, <= 0) at which a and b are in one emergent component; None if not even at lo."""
    if not connected(Z, lo, a, b, region):
        return None
    if connected(Z, hi, a, b, region):
        return hi
    for _ in range(14):
        mid = (lo + hi) / 2
        if connected(Z, mid, a, b, region):
            lo = mid
        else:
            hi = mid
    return round(lo, 1)


def main():
    write_result = "--write-result" in sys.argv
    sites = pd.read_csv(os.path.join(HERE, "derived", "sites.csv"))
    lats, lons, Z = load_grid()
    LAT = np.broadcast_to(lats[:, None], Z.shape)
    LON = np.broadcast_to(lons[None, :], Z.shape)
    area = np.broadcast_to(cell_area_km2(lats)[:, None], Z.shape)

    land0 = Z >= 0
    low = Z >= LOWSTAND
    lab0 = label_wrap(land0)
    lab130 = label_wrap(low)
    comp_area130 = np.bincount(lab130.ravel(), weights=area.ravel())

    seeds = {}
    for _, s in sites[sites["class"] == "continent"].iterrows():
        i, j = cell_of(s.lat, s.lon, lats, lons)
        assert land0[i, j], f"seed {s.site_id} not on land"
        seeds[s.site_id] = (i, j)
    seed_comp130 = {k: int(lab130[v]) for k, v in seeds.items()}
    continental_labels = set(seed_comp130.values())

    rows = []
    for _, s in sites[sites["class"] != "continent"].iterrows():
        i, j = cell_of(s.lat, s.lon, lats, lons)
        hit = nearest_land_cell(i, j, land0, radius=5)
        resolved = hit is not None
        if not resolved:
            # island too small to be sampled as land on the 0.1-degree grid: fall back to the nearest cell that is
            # emergent at -130 m (the island's bank), so that connectivity is still checked rather than assumed
            hit = nearest_land_cell(i, j, low, radius=5)
        if hit is None:
            rows.append({"site_id": s.site_id, "name": s["name"], "class": s["class"], "resolved": False, "bank_found": False,
                         "connected_130": False, "connected_to": "", "land_area_0_km2": 0.0, "area_130_km2": 0.0,
                         "offset_cells": None, "z_at_point": float(Z[i, j]), "cell": None})
            continue
        ii, jj, off = hit
        l130 = int(lab130[ii, jj])
        con = [k for k, v in seed_comp130.items() if v == l130]
        rows.append({"site_id": s.site_id, "name": s["name"], "class": s["class"], "resolved": resolved, "bank_found": True,
                     "connected_130": bool(con), "connected_to": "+".join(con),
                     "land_area_0_km2": round(float(np.bincount(lab0.ravel(), weights=area.ravel())[lab0[ii, jj]]), 1) if resolved else 0.0,
                     "area_130_km2": round(float(comp_area130[l130]), 1), "offset_cells": round(off, 2),
                     "z_at_point": float(Z[i, j]), "cell": (ii, jj)})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "island_connectivity.csv"), index=False)

    oce = df[df["class"] == "oceanic"]
    ctl = df[df["class"] == "continental-island"]
    n_oce = len(oce)
    n_oce_res = int(oce["resolved"].sum())
    n_oce_con = int(oce["connected_130"].sum())
    frac_oce_uncon = (n_oce - n_oce_con) / n_oce

    # Continental gap tests. Region masks restrict the connectivity search so that each test is about the
    # named ocean gap rather than about any route around the world.
    bering = (LAT > 55) & ((LON >= 160) | (LON <= -160))
    gaps = {
        "T1_eurasia_namerica_atlantic": ("EURASIA", "NAMERICA", (LAT > 20) & ~bering),
        "T2_africa_samerica_atlantic": ("AFRICA", "SAMERICA", LAT < 30),
        "T3_australia_asia": ("EURASIA", "AUSTRALIA", None),
        "T4_antarctica_samerica": ("ANTARCTICA", "SAMERICA", None),
        "T5_antarctica_australia": ("ANTARCTICA", "AUSTRALIA", None),
    }
    gap_res = {}
    for name, (a, b, region) in gaps.items():
        c = connected(Z, LOWSTAND, seeds[a], seeds[b], region)
        gap_res[name] = {"connected_at_-130m": bool(c), "sill_depth_m": sill_depth(Z, seeds[a], seeds[b], region)}
    bering_sill = sill_depth(Z, seeds["EURASIA"], seeds["NAMERICA"], None)
    bering_130 = connected(Z, LOWSTAND, seeds["EURASIA"], seeds["NAMERICA"], None)
    n_gaps_con = sum(v["connected_at_-130m"] for v in gap_res.values())

    # Sill depth (shallowest sea level at which the island joins any continent, searched down to -1000 m) for every
    # island; informative for oceanic islands, the validity check for the continental-island positive controls.
    sills = {}
    for _, r in df.iterrows():
        if r.cell is None:
            continue
        d = sill_depth(Z, tuple(r.cell), list(seeds.values()), None, lo=-1000.0)
        sills[r.site_id] = d
    df["sill_depth_m"] = df["site_id"].map(sills)
    df.drop(columns=["cell"]).to_csv(os.path.join(DERIVED, "island_connectivity.csv"), index=False)
    oce = df[df["class"] == "oceanic"]
    ctl = df[df["class"] == "continental-island"]
    ctl_sills = {s: {"sill_depth_to_any_continent_m": sills.get(s), "note": None if sills.get(s) is not None else "not connected even at -1000 m"}
                 for s in ctl.site_id}
    oce_sills = {s: sills.get(s) for s in oce.site_id}
    n_oce_deep = sum(1 for v in oce_sills.values() if v is None)

    if n_gaps_con == 0 and frac_oce_uncon >= 0.90:
        verdict = "supports"
    elif n_gaps_con >= 2 or (1 - frac_oce_uncon) >= 0.25:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": round(frac_oce_uncon, 4),
        "unit": "fraction of pre-registered oceanic islands whose emergent component at -130 m contains no continent seed",
        "n": n_oce,
        "uncertainty": f"{n_oce_res} of {n_oce} islands resolved as present-day land on the 0.1-degree grid (the rest located by their -130 m bank); {n_gaps_con} of 5 continental gaps connected at -130 m; {n_oce_deep} of {n_oce} oceanic islands not joined to any continent even at -1000 m",
        "extra": {
            "oceanic_islands_connected_at_-130m": oce[oce.connected_130]["site_id"].tolist(),
            "oceanic_islands_unresolved_on_grid": oce[~oce.resolved]["site_id"].tolist(),
            "oceanic_islands_bank_not_found": oce[~oce.bank_found]["site_id"].tolist(),
            "oceanic_island_sill_depths_m": oce_sills,
            "n_oceanic_islands_isolated_to_-1000m": n_oce_deep,
            "continental_gaps": gap_res,
            "bering_eurasia_namerica": {"connected_at_-130m": bool(bering_130), "sill_depth_m": bering_sill},
            "positive_controls": {
                "n": int(len(ctl)), "n_connected_at_-130m": int(ctl.connected_130.sum()),
                "connected": ctl[ctl.connected_130]["site_id"].tolist(),
                "unconnected": ctl[~ctl.connected_130]["site_id"].tolist(),
                "sill_depths_m": ctl_sills,
            },
            "grid": {"step_deg": STEP, "shape": list(Z.shape), "land_fraction_0m": round(float(area[land0].sum() / area.sum()), 4),
                     "emergent_fraction_-130m": round(float(area[low].sum() / area.sum()), 4)},
            "continent_seed_components_-130m": seed_comp130,
            "n_distinct_continental_components_-130m": len(continental_labels),
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        res["datasets"][0]["files"] = [{k: v for k, v in f.items() if k != "role"} | {"note": f["role"]} for f in FILES]
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
