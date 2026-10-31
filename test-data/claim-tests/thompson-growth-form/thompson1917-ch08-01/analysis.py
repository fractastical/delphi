#!/usr/bin/env python3
"""Test of thompson1917-ch08-01 (Sachs/Thompson): a new plant cell wall cuts across the mother cell's
longest axis, and successive walls alternate at right angles.

Data: Yates & Sablowski 2026, Zenodo 10.5281/zenodo.18711581 (CC BY 4.0), the same 8 shoot-apex
archives as thompson1917-ch08-02 (first 8 alphabetically). Only Metadata.txt, *_seg.tif,
*_new_walls.tif, *_walls_data.csv and *_cell_data.csv are read, by HTTP range requests into each zip,
and checked against the ZIP CRC-32 (a CRC-matching copy already in ../thompson1917-ch08-02/data is
reused). Secondary: eLife 79224 Figure 8 source data 2 (Laruelle et al. 2022, CC BY 4.0).
Packages: requests, numpy, scipy, pandas, tifffile.
Writes derived/summary.json, derived/part1.csv, derived/part2.csv and derived/fetch_log.csv.
"""
import csv
import hashlib
import io
import json
import os
import re
import shutil
import struct
import sys
import zipfile
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
SIBLING = os.path.join(HERE, "..", "thompson1917-ch08-02", "data")
DERIVED = os.path.join(HERE, "derived")
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
RECORD = "18711581"
API = f"https://zenodo.org/api/records/{RECORD}"
SUFFIXES = ["Metadata.txt", "_seg.tif", "_new_walls.tif", "_walls_data.csv", "_cell_data.csv"]
ELIFE = "https://cdn.elifesciences.org/articles/79224/elife-79224-fig8-data2-v1.zip"
OLD_WALL_CONTROL_PER_ARCHIVE = 1000  # not pre-registered: walls not flagged as new, analysed identically
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
    base = name.split("/")[-1]
    path = os.path.join(DATA, base)
    meta = path + ".fetched.json"
    off, csize, meth, crc = index[name]
    ok = lambda p: os.path.exists(p) and zlib.crc32(open(p, "rb").read()) == crc
    if not ok(path) and ok(os.path.join(SIBLING, base)):
        shutil.copy2(os.path.join(SIBLING, base), path)
        if os.path.exists(os.path.join(SIBLING, base) + ".fetched.json"):
            shutil.copy2(os.path.join(SIBLING, base) + ".fetched.json", meta)
    if not ok(path):
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


def voxel_size(path):
    t = open(path, errors="replace").read()
    g = lambda ax: float(re.search(rf"voxel size {ax} \(um\) : ([0-9.]+)", t).group(1))
    return g("z"), g("y"), g("x")


def angle(u, v):
    return float(np.degrees(np.arccos(min(1.0, abs(float(np.dot(u, v)) / (np.linalg.norm(u) * np.linalg.norm(v)))))))


def interface_points(L, i, j, vs):
    """Midpoints (um) of voxel faces between label i and label set j in a small label array."""
    pts = []
    for ax in range(3):
        lo = [slice(None)] * 3
        hi = [slice(None)] * 3
        lo[ax], hi[ax] = slice(0, -1), slice(1, None)
        A, B = L[tuple(lo)], L[tuple(hi)]
        d = ((A == i) & np.isin(B, j)) | (np.isin(A, j) & (B == i))
        p = np.argwhere(d).astype(float)
        p[:, ax] += 0.5
        pts.append(p * vs)
    return np.concatenate(pts)


def normal(pts):
    ev, evec = np.linalg.eigh(np.cov(pts.T))
    return evec[:, 0]


def analyse_archive(arg):
    root, paths = arg
    vs = np.array(voxel_size(paths["Metadata.txt"]))
    vvox = float(np.prod(vs))
    seg = tifffile.imread(paths["_seg.tif"])
    allw = pd.read_csv(paths["_walls_data.csv"])
    allw = allw[(allw["Flanking cell 1"] > 0) & (allw["Flanking cell 2"] > 0)]
    walls = allw[allw["New wall filter"] == 1]
    old = allw[allw["New wall filter"] == 0]
    old = old.sample(n=min(OLD_WALL_CONTROL_PER_ARCHIVE, len(old)), random_state=0)
    slices = ndimage.find_objects(seg)
    shape = seg.shape
    vol = {i + 1: None for i in range(len(slices))}

    def good(c):
        if c <= 0 or c > len(slices) or slices[c - 1] is None:
            return False
        if any(s.start == 0 or s.stop == shape[k] for k, s in enumerate(slices[c - 1])):
            return False
        if vol[c] is None:
            vol[c] = float((seg[slices[c - 1]] == c).sum() * vvox)
        return vol[c] >= PRE["min_sister_volume_um3"]

    def crop(cells):
        sl = [slices[c - 1] for c in cells]
        box = tuple(slice(max(min(s[k].start for s in sl) - 1, 0), min(max(s[k].stop for s in sl) + 1, shape[k])) for k in range(3))
        return seg[box]

    pairs = [(int(w["Object #"]), int(w["Flanking cell 1"]), int(w["Flanking cell 2"])) for _, w in walls.iterrows()]
    old_pairs = [(int(w["Object #"]), int(w["Flanking cell 1"]), int(w["Flanking cell 2"])) for _, w in old.iterrows()]
    part1 = []
    for kind, (lab, a, b) in [("new", p) for p in pairs] + [("old_control", p) for p in old_pairs]:
        if not (good(a) and good(b)):
            continue
        S = crop([a, b])
        pts = interface_points(S, a, [b], vs)
        if len(pts) < 3:
            continue
        n = normal(pts)
        mc = np.argwhere((S == a) | (S == b)) * vs
        ev, evec = np.linalg.eigh(np.cov(mc.T))
        elong = float(np.sqrt(ev[2] / ev[1]))
        part1.append({"archive": root, "kind": kind, "wall": lab, "cell_a": a, "cell_b": b, "theta_deg": angle(n, evec[:, 2]),
                      "elongation": elong, "mother_vol_um3": vol[a] + vol[b]})
    nbr = {}
    for lab, a, b in pairs:
        nbr.setdefault(a, set()).add(b)
        nbr.setdefault(b, set()).add(a)
    part2 = []
    for lab, y1, y2 in pairs:
        for x in sorted(nbr.get(y1, set()) & nbr.get(y2, set())):
            if not (good(x) and good(y1) and good(y2)):
                continue
            S = crop([x, y1, y2])
            p_y = interface_points(S, y1, [y2], vs)
            p_x = interface_points(S, x, [y1, y2], vs)
            if len(p_y) < 3 or len(p_x) < 3:
                continue
            part2.append({"archive": root, "wall_y1y2": lab, "x": x, "y1": y1, "y2": y2, "phi_deg": angle(normal(p_y), normal(p_x))})
    return part1, part2, sum(len(v) > 1 for v in nbr.values())


def elife():
    r = requests.get(ELIFE, timeout=60)
    r.raise_for_status()
    info = {"download_url": ELIFE, "retrieved_at": utc(), "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    z = zipfile.ZipFile(io.BytesIO(r.content))
    d = pd.read_csv(z.open(z.namelist()[0]), sep="\t")
    tr = d[d["type"] == "transversal"]
    lo = d[d["type"].str.startswith("longitudinal")]
    return info, {"file": z.namelist()[0],
                  "n_transversal": len(tr), "transversal_frac_longitudinal_gt_radial": float((tr.ratio > 1).mean()),
                  "n_longitudinal": len(lo), "longitudinal_frac_longitudinal_lt_radial": float((lo.ratio < 1).mean()),
                  "median_ratio_transversal": float(tr.ratio.median()), "median_ratio_longitudinal": float(lo.ratio.median())}


def part_outcome(med, frac, pass_med, pass_frac, fail_med, low_is_good):
    if low_is_good:
        return "pass" if med <= pass_med and frac >= pass_frac else ("fail" if med >= fail_med else "neither")
    return "pass" if med >= pass_med and frac >= pass_frac else ("fail" if med <= fail_med else "neither")


def write_tables(p1_all, p2):
    """Per-wall rows go to data/ (too large to commit); derived/ gets theta histograms."""
    p1_all.round(4).to_csv(os.path.join(DATA, "part1.csv"), index=False)
    if len(p2):
        p2.round(4).to_csv(os.path.join(DERIVED, "part2.csv"), index=False)
    eb = pd.cut(p1_all.elongation, [1.0, 1.2, 1.5, 2.0, np.inf], right=False)
    tb = pd.cut(p1_all.theta_deg, np.arange(0, 95, 5), include_lowest=True)
    h = p1_all.groupby([p1_all.kind, eb.astype(str).rename("elongation_bin"), tb.astype(str).rename("theta_bin_deg")], observed=True).size().rename("n")
    h.reset_index().to_csv(os.path.join(DERIVED, "part1_theta_histogram.csv"), index=False)


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
        res = pool.map(analyse_archive, jobs)
    p1_all = pd.DataFrame([r for a, _, _ in res for r in a])
    p1, ctl = p1_all[p1_all.kind == "new"], p1_all[p1_all.kind == "old_control"]
    ctl_el = ctl[ctl.elongation >= PRE["elongation_min"]]
    p2 = pd.DataFrame([r for _, b, _ in res for r in b])
    el = p1[p1.elongation >= PRE["elongation_min"]]
    n1, n2 = len(el), len(p2)
    med1 = float(el.theta_deg.median()) if n1 else float("nan")
    f1 = float((el.theta_deg <= 30).mean()) if n1 else float("nan")
    med2 = float(p2.phi_deg.median()) if n2 else float("nan")
    f2 = float((p2.phi_deg >= 70).mean()) if n2 else float("nan")
    o1 = part_outcome(med1, f1, PRE["part1_pass_median_deg"], PRE["part1_pass_fraction_le30"], PRE["part1_fail_median_deg"], True)
    o2 = part_outcome(med2, f2, PRE["part2_pass_median_deg"], PRE["part2_pass_fraction_ge70"], PRE["part2_fail_median_deg"], False) if n2 else "none"
    cap = None
    if n1 < PRE["min_part1"]:
        verdict, reason = "inconclusive", "underpowered"
    elif n2 < PRE["min_part2"]:
        verdict, reason, cap = {"pass": "supports", "fail": "refutes"}.get(o1, "mixed"), None, 0.6
    elif o1 == "pass" and o2 == "pass":
        verdict, reason = "supports", None
    elif o1 == "fail" and o2 == "fail":
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    einfo, esum = elife()
    rng = np.random.default_rng(0)
    u = rng.normal(size=(200000, 3))
    null_med = float(np.median(np.degrees(np.arccos(np.abs(u[:, 0]) / np.linalg.norm(u, axis=1)))))
    measured = {
        "value": round(med1, 2),
        "unit": "median angle (deg) between the new wall's normal and the mother cell's longest principal axis, elongated mothers (axis ratio >= 1.2)",
        "n": n1,
        "uncertainty": f"IQR {el.theta_deg.quantile(0.25):.1f}-{el.theta_deg.quantile(0.75):.1f} deg; random-orientation median {null_med:.1f} deg",
        "extra": {
            "part1_fraction_theta_le_30": round(f1, 4),
            "part1_outcome": o1,
            "part1_all_mothers": {"n": len(p1), "median_theta_deg": round(float(p1.theta_deg.median()), 2),
                                  "fraction_le_30": round(float((p1.theta_deg <= 30).mean()), 4)},
            "part1_by_elongation": {f"{lo}-{hi}": {"n": int(((p1.elongation >= lo) & (p1.elongation < hi)).sum()),
                                                  "median_theta_deg": round(float(p1[(p1.elongation >= lo) & (p1.elongation < hi)].theta_deg.median()), 2)}
                                    for lo, hi in [(1.0, 1.2), (1.2, 1.5), (1.5, 2.0), (2.0, 99)]},
            "control_not_preregistered_old_walls": {
                "note": f"up to {OLD_WALL_CONTROL_PER_ARCHIVE} randomly sampled walls per apex not flagged as new; union of the two flanking cells analysed identically",
                "n_elongated": len(ctl_el), "median_theta_deg": round(float(ctl_el.theta_deg.median()), 2),
                "fraction_le_30": round(float((ctl_el.theta_deg <= 30).mean()), 4)},
            "cells_in_more_than_one_new_wall": int(sum(c for _, _, c in res)),
            "part2_n_triples": n2,
            "part2_median_phi_deg": None if not n2 else round(med2, 2),
            "part2_fraction_phi_ge_70": None if not n2 else round(f2, 4),
            "part2_outcome": o2,
            "confidence_cap": cap,
            "per_archive": p1[p1.elongation >= PRE["elongation_min"]].groupby("archive").theta_deg.agg(["size", "median"]).round(2).reset_index().to_dict(orient="records"),
            "secondary_elife79224_fig8_data2": esum,
        },
    }
    write_tables(p1_all, p2)
    with open(os.path.join(DERIVED, "fetch_log.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fetch[0]))
        w.writeheader()
        w.writerows(fetch)
    out = {"measured": measured, "verdict": verdict, "reason": reason, "elife_file": einfo,
           "record": {"doi": rec.get("doi"), "title": rec["metadata"]["title"], "license": rec["metadata"]["license"]["id"],
                      "publication_date": rec["metadata"]["publication_date"]},
           "archives": arcs}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("measured", "verdict", "reason")}, indent=1))


if __name__ == "__main__":
    main()
