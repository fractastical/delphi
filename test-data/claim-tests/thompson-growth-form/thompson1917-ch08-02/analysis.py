#!/usr/bin/env python3
"""Test of thompson1917-ch08-02 (Errera's rule): a new plant cell wall has close to the least area of
any planar cut dividing the mother cell in the same volume ratio.

Data: Yates & Sablowski 2026, Zenodo 10.5281/zenodo.18711581 (CC BY 4.0), watershed-segmented 3D
confocal stacks of Arabidopsis inflorescence shoot apices. For the first 8 archives (alphabetical),
only Metadata.txt, *_seg.tif, *_new_walls.tif, *_walls_data.csv and *_cell_data.csv are read, by HTTP
range requests into the zip, each checked against its ZIP CRC-32.
Packages: requests, numpy, scipy, pandas, tifffile.
Writes derived/summary.json, derived/divisions.csv and derived/fetch_log.csv.
"""
import csv
import hashlib
import json
import os
import re
import struct
import sys
import zlib
from datetime import datetime, timezone
from multiprocessing import Pool

import numpy as np
import pandas as pd
import requests
import tifffile
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
RECORD = "18711581"
API = f"https://zenodo.org/api/records/{RECORD}"
SUFFIXES = ["Metadata.txt", "_seg.tif", "_new_walls.tif", "_walls_data.csv", "_cell_data.csv"]
OLD_WALL_CONTROL_PER_ARCHIVE = 150  # not pre-registered: walls not flagged as new, analysed identically
JOBS = int(os.environ.get("JOBS", "6"))


def utc(t=None):
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if t else datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rget(url, a, b):
    for _ in range(5):
        r = requests.get(url, headers={"Range": f"bytes={a}-{b}"}, timeout=300)
        if r.status_code == 206:
            return r.content
    raise RuntimeError(f"range {a}-{b} of {url}: {r.status_code}")


def zip_index(url, size):
    tail = rget(url, size - 65536, size - 1)
    i = tail.rfind(b"PK\x05\x06")
    cd_size, cd_off = struct.unpack("<II", tail[i + 12:i + 20])
    cd = rget(url, cd_off, cd_off + cd_size - 1)
    m, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        meth = struct.unpack("<H", cd[p + 10:p + 12])[0]
        crc, csize, _ = struct.unpack("<III", cd[p + 16:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off = struct.unpack("<I", cd[p + 42:p + 46])[0]
        m[cd[p + 46:p + 46 + nl].decode()] = (off, csize, meth, crc)
        p += 46 + nl + el + cl
    return m


def fetch_member(url, index, name, archive):
    path = os.path.join(DATA, name.split("/")[-1])
    meta = path + ".fetched.json"
    off, csize, meth, crc = index[name]
    if not (os.path.exists(path) and zlib.crc32(open(path, "rb").read()) == crc):
        h = rget(url, off, off + 29)
        nl, el = struct.unpack("<HH", h[26:30])
        s = off + 30 + nl + el
        raw = rget(url, s, s + csize - 1)
        b = raw if meth == 0 else zlib.decompress(raw, -15)
        assert zlib.crc32(b) == crc, f"CRC mismatch {name}"
        open(path, "wb").write(b)
        json.dump({"retrieved_at": utc()}, open(meta, "w"))
    b = open(path, "rb").read()
    when = json.load(open(meta))["retrieved_at"] if os.path.exists(meta) else utc(os.path.getmtime(path))
    return {"archive": archive, "member": name, "retrieved_at": when, "byte_size": len(b), "sha256": hashlib.sha256(b).hexdigest()}, path


def archives():
    rec = requests.get(API, timeout=60).json()
    files = sorted(rec["files"], key=lambda f: f["key"])[:8]
    return rec, [{"key": f["key"], "size": f["size"], "checksum": f["checksum"],
                  "url": f"https://zenodo.org/records/{RECORD}/files/{f['key']}?download=1"} for f in files]


def fibonacci_hemisphere(n):
    i = np.arange(n) + 0.5
    z = i / n
    r = np.sqrt(1 - z ** 2)
    phi = i * np.pi * (3 - np.sqrt(5))
    return np.stack([z, r * np.sin(phi), r * np.cos(phi)], 1)  # (z, y, x) order


def voxel_size(path):
    t = open(path, errors="replace").read()
    g = lambda ax: float(re.search(rf"voxel size {ax} \(um\) : ([0-9.]+)", t).group(1))
    return g("z"), g("y"), g("x")


def analyse_archive(arg):
    root, paths = arg
    vz, vy, vx = voxel_size(paths["Metadata.txt"])
    face = np.array([vy * vx, vz * vx, vz * vy])  # face areas between neighbours along z, y, x
    vvox = vz * vy * vx
    seg = tifffile.imread(paths["_seg.tif"])
    nw = tifffile.imread(paths["_new_walls.tif"])
    gz, gy, gx = np.nonzero((nw > 0) & (seg == 0))
    gl = nw[gz, gy, gx]
    del nw
    allw = pd.read_csv(paths["_walls_data.csv"])
    new = allw[allw["New wall filter"] == 1].assign(kind="new")
    old = allw[(allw["New wall filter"] == 0) & (allw["Flanking cell 1"] > 0) & (allw["Flanking cell 2"] > 0)]
    old = old.sample(n=min(OLD_WALL_CONTROL_PER_ARCHIVE, len(old)), random_state=0).assign(kind="old_control")
    walls = pd.concat([new, old])
    slices = ndimage.find_objects(seg)
    shape = seg.shape
    N = fibonacci_hemisphere(PRE["n_orientations"]).astype(np.float32)
    rows = []
    for _, w in walls.iterrows():
        lab, a, b = int(w["Object #"]), int(w["Flanking cell 1"]), int(w["Flanking cell 2"])
        row = {"archive": root, "kind": w["kind"], "wall": lab, "cell_a": a, "cell_b": b, "status": "ok"}
        if a <= 0 or b <= 0 or a > len(slices) or b > len(slices) or slices[a - 1] is None or slices[b - 1] is None:
            rows.append({**row, "status": "missing_cell"})
            continue
        sa, sb = slices[a - 1], slices[b - 1]
        if any(s.start == 0 or s.stop == shape[k] for sl in (sa, sb) for k, s in enumerate(sl)):
            rows.append({**row, "status": "touches_border"})
            continue
        box = tuple(slice(max(min(p.start, q.start) - 1, 0), min(max(p.stop, q.stop) + 1, shape[k])) for k, (p, q) in enumerate(zip(sa, sb)))
        S = seg[box]
        L = np.zeros(S.shape, np.int8)
        L[S == a], L[S == b] = 1, 2
        gap = np.zeros(S.shape, bool)
        sel = (gl == lab) & (gz >= box[0].start) & (gz < box[0].stop) & (gy >= box[1].start) & (gy < box[1].stop) & (gx >= box[2].start) & (gx < box[2].stop)
        gap[gz[sel] - box[0].start, gy[sel] - box[1].start, gx[sel] - box[2].start] = True
        if gap.any():
            _, ind = ndimage.distance_transform_edt(L == 0, return_indices=True)
            L[gap] = L[tuple(i[gap] for i in ind)]
        n1, n2 = int((L == 1).sum()), int((L == 2).sum())
        v1, v2 = n1 * vvox, n2 * vvox
        row.update({"vol_a_um3": v1, "vol_b_um3": v2})
        if min(v1, v2) < PRE["min_sister_volume_um3"]:
            rows.append({**row, "status": "small_sister"})
            continue
        M = L > 0
        pos = -np.ones(S.shape, np.int64)
        pos[M] = np.arange(int(M.sum()))
        coords = (np.argwhere(M) * np.array([vz, vy, vx])).astype(np.float32)
        lab_flat = L[M]
        pairs, a_obs, mids = [], 0.0, []
        for ax in range(3):
            lo = [slice(None)] * 3
            hi = [slice(None)] * 3
            lo[ax], hi[ax] = slice(0, -1), slice(1, None)
            P, Q = pos[tuple(lo)].ravel(), pos[tuple(hi)].ravel()
            keep = (P >= 0) & (Q >= 0)
            P, Q = P[keep], Q[keep]
            pairs.append((P, Q))
            d = lab_flat[P] != lab_flat[Q]
            a_obs += face[ax] * d.sum()
            mids.append((coords[P[d]] + coords[Q[d]]) / 2)
        mids = np.concatenate(mids)
        if len(mids) < 3:
            rows.append({**row, "status": "no_interface"})
            continue
        ev, evec = np.linalg.eigh(np.cov(mids.T))
        n_obs = evec[:, 0]
        nvox = len(coords)
        k = min(n1, n2)
        areas = np.empty(len(N))
        for c0 in range(0, len(N), 100):
            Nc = N[c0:c0 + 100]
            Pj = coords @ Nc.T
            thr = np.partition(Pj, k - 1, axis=0)[k - 1]
            side = Pj <= thr
            A = np.zeros(len(Nc))
            for ax, (P, Q) in enumerate(pairs):
                A += face[ax] * (side[P] != side[Q]).sum(0)
            areas[c0:c0 + 100] = A
        l1 = np.abs(N).sum(1)
        areas_c = areas / l1
        a_obs_c = a_obs / np.abs(n_obs).sum()
        row.update({"n_vox": nvox, "small_fraction": k / nvox, "A_obs_um2": a_obs, "A_min_um2": float(areas.min()),
                    "q": a_obs / areas.min(), "p": float((areas < a_obs).mean()),
                    "A_median_um2": float(np.median(areas)),
                    "q_corrected": a_obs_c / areas_c.min(), "p_corrected": float((areas_c < a_obs_c).mean()),
                    "interface_planarity": float(ev[0] / ev[1])})
        rows.append(row)
    return rows


def write_tables(df):
    """Per-division rows go to data/ (too large to commit); derived/ gets q and p histograms."""
    df.round(5).to_csv(os.path.join(DATA, "divisions.csv"), index=False)
    ok = df[df.status == "ok"]
    q = ok.groupby([ok.kind, pd.cut(ok.q, [0, 0.9, 1.0, 1.05, 1.1, 1.2, 1.3, 1.5, 2.0, np.inf]).astype(str).rename("q_bin")], observed=True).size().rename("n")
    p = ok.groupby([ok.kind, pd.cut(ok.p, np.linspace(0, 1, 21), include_lowest=True).astype(str).rename("p_bin")], observed=True).size().rename("n")
    q.reset_index().to_csv(os.path.join(DERIVED, "q_histogram.csv"), index=False)
    p.reset_index().to_csv(os.path.join(DERIVED, "p_histogram.csv"), index=False)


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    rec, arcs = archives()
    fetch, jobs = [], []
    for arc in arcs:
        root = arc["key"][:-4]
        index = zip_index(arc["url"], arc["size"])
        paths = {}
        for suf in SUFFIXES:
            name = f"{root}/{suf}" if suf == "Metadata.txt" else f"{root}/{root}{suf}"
            if name not in index:
                print("missing", name, file=sys.stderr)
                continue
            info, p = fetch_member(arc["url"], index, name, arc["key"])
            fetch.append(info)
            paths[suf] = p
        if len(paths) == len(SUFFIXES):
            jobs.append((root, paths))
        print("fetched", root, file=sys.stderr, flush=True)
    with Pool(min(JOBS, len(jobs))) as pool:
        rows = [r for part in pool.map(analyse_archive, jobs) for r in part]
    df = pd.DataFrame(rows)
    ctl = df[(df.status == "ok") & (df.kind == "old_control")]
    df_new = df[df.kind == "new"]
    ok = df_new[df_new.status == "ok"]
    n = len(ok)
    med_p = float(ok.p.median()) if n else float("nan")
    f_q = float((ok.q <= PRE["q_tolerance"]).mean()) if n else float("nan")
    if n < PRE["min_divisions"]:
        verdict, reason = "inconclusive", "underpowered"
    elif med_p <= PRE["pass_median_percentile"] and f_q >= PRE["pass_fraction_within_tolerance"]:
        verdict, reason = "supports", None
    elif med_p >= PRE["fail_median_percentile"] or f_q < PRE["fail_fraction_within_tolerance"]:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    per_arc = ok.groupby("archive").agg(n=("q", "size"), median_q=("q", "median"), median_p=("p", "median"),
                                        frac_q_le_tol=("q", lambda s: float((s <= PRE["q_tolerance"]).mean()))).reset_index()
    measured = {
        "value": round(med_p, 4),
        "unit": "median over divisions of the percentile of the observed new-wall area among 500 planar cuts of the mother at the observed volume ratio (voxel-face areas)",
        "n": n,
        "uncertainty": f"{n} divisions in {ok.archive.nunique()} shoot apices; IQR of percentile {ok.p.quantile(0.25):.3f}-{ok.p.quantile(0.75):.3f}",
        "extra": {
            "fraction_q_le_1.10": round(f_q, 4),
            "median_q": round(float(ok.q.median()), 4),
            "q_quartiles": [round(float(x), 4) for x in ok.q.quantile([0.25, 0.75])],
            "median_small_sister_fraction": round(float(ok.small_fraction.median()), 4),
            "median_A_obs_over_median_random_cut": round(float((ok.A_obs_um2 / ok.A_median_um2).median()), 4),
            "excluded": df_new[df_new.status != "ok"].status.value_counts().to_dict(),
            "control_not_preregistered_old_walls": {
                "note": f"up to {OLD_WALL_CONTROL_PER_ARCHIVE} randomly sampled walls per apex not flagged as new, union of the two flanking cells analysed identically",
                "n": len(ctl), "median_p": round(float(ctl.p.median()), 4),
                "fraction_q_le_1.10": round(float((ctl.q <= PRE["q_tolerance"]).mean()), 4),
                "median_q": round(float(ctl.q.median()), 4),
                "median_p_corrected": round(float(ctl.p_corrected.median()), 4)},
            "per_archive": per_arc.round(4).to_dict(orient="records"),
            "sensitivity_not_preregistered_orientation_corrected": {
                "note": "voxel-face area divided by |n_z|+|n_y|+|n_x| of the cut normal (observed wall: normal of its interface face centres)",
                "median_p": round(float(ok.p_corrected.median()), 4),
                "fraction_q_le_1.10": round(float((ok.q_corrected <= PRE["q_tolerance"]).mean()), 4),
                "median_q": round(float(ok.q_corrected.median()), 4)},
        },
    }
    write_tables(df)
    with open(os.path.join(DERIVED, "fetch_log.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fetch[0]))
        w.writeheader()
        w.writerows(fetch)
    out = {"measured": measured, "verdict": verdict, "reason": reason,
           "record": {"doi": rec.get("doi"), "title": rec["metadata"]["title"], "license": rec["metadata"]["license"]["id"],
                      "publication_date": rec["metadata"]["publication_date"]},
           "archives": arcs}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("measured", "verdict", "reason")}, indent=1))


if __name__ == "__main__":
    main()
