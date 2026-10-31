#!/usr/bin/env python3
"""Fetch the shell-coiling datasets and write the small derived tables used by analysis.py.

1. Walton & Korn 2018, ontogenetic conch parameters of 179 ammonoid species
   (Dryad doi:10.5061/dryad.c17p8; mirrored at Zenodo record 4937032, direct download).
   -> derived/ammonoid_dm_halfwhorl.csv : species, family, period, whorl, dm (mm)
2. Tajika et al. 2018, 3D morphometry of 94 Nautilus pompilius (Dryad doi:10.5061/dryad.4cb86,
   Supplementary Table_2.xlsx; conch diameter every 45 deg).
   -> derived/nautilus_dm_45deg.csv : population, specimen, step, dm, ww
3. Collins et al. 2021, helicospiral gastropods (Dryad doi:10.5061/dryad.p5hqbzknw):
   Collins_et_al_data.zip (521 MB) holds a tpsDig file with the aperture outlines of 176
   shells at 180-degree intervals plus two coiling-axis landmarks per image.
   -> derived/gastropod_aperture_radii.csv : id, species, aperture, r (px), area (px^2)

Dryad serves file downloads behind a browser proof-of-work challenge (Anubis); a plain HTTP
GET returns an HTML page instead of the file. This script tries a direct GET and otherwise
expects the files in ./data/ (download them in a browser from the Dryad landing pages).
SHA-256 of every file is checked against the values below before anything is derived.
"""
import hashlib
import io
import os
import re
import sys
import zipfile

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")

FILES = {
    "Ontogenetic_Conch_Parameter_Data.xlsx": {
        "url": "https://zenodo.org/api/records/4937032/files/Ontogenetic_Conch_Parameter_Data.xlsx/content",
        "sha256": "fbe2012f1d420ef7b292141ae0ed0ea8d046c4c15303663565dc72e0727ebe40",
        "size": 215182,
    },
    "Supplementary Table_2.xlsx": {
        "url": "https://datadryad.org/downloads/file_stream/75500",
        "sha256": "db9ee691bc10f3c03ce78340f61c5b6f2fd98f9c3b1a1f3e194b8353aee4bb9f",
        "size": 126717,
    },
    "Collins_et_al_data.zip": {
        "url": "https://datadryad.org/downloads/file_stream/547236",
        "sha256": "edab9e356820a43984bcf8130359ec29f7e6c00ca3995292fcd922ba2cb3a2a9",
        "size": 521094347,
    },
    "S_Table_1_Specimens.csv": {
        "url": "https://datadryad.org/downloads/file_stream/547239",
        "sha256": "a034e43eb95a22dffe10b1f8d0e83ab43b0e592e8e1d646513da7ab8dfbc7a39",
        "size": 20413,
    },
}


def norm_id(s):
    """tps IDs '060_3' (replicate 3 of specimen 60) and '001' match table IDs '60' and '1'."""
    base = str(s).strip().split("_")[0]
    return base.lstrip("0") or base


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def obtain(name, spec, required=True):
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, name)
    if not os.path.exists(path):
        try:
            r = requests.get(spec["url"], timeout=600, allow_redirects=True,
                             headers={"User-Agent": "delphi-claim-tests/1.0"}, stream=True)
            if r.ok and "text/html" not in r.headers.get("content-type", ""):
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
        except requests.RequestException as e:
            print(f"direct download failed for {name}: {e}", file=sys.stderr)
    if not os.path.exists(path):
        msg = f"{name} not available; download it in a browser into {DATA}/ (see docstring)"
        if required:
            sys.exit(msg)
        print(msg, file=sys.stderr)
        return None
    got = sha256(path)
    if spec["sha256"] and got != spec["sha256"]:
        sys.exit(f"checksum mismatch for {name}: {got}")
    print(f"ok {name} {os.path.getsize(path)} bytes sha256={got}")
    return path


def derive_ammonoids(path):
    d = pd.read_excel(path, sheet_name="dm")
    whorl_cols = [c for c in d.columns if str(c).startswith("Whorl")]
    rows = []
    for _, r in d.iterrows():
        for c in whorl_cols:
            if pd.notna(r[c]):
                rows.append({"species": r["Species"], "family": r["Family"], "period": r["Period"],
                             "whorl": float(str(c).split()[1]), "dm": float(r[c])})
    out = pd.DataFrame(rows).sort_values(["species", "whorl"])
    out.to_csv(os.path.join(DERIVED, "ammonoid_dm_halfwhorl.csv"), index=False, float_format="%.4f")
    print(f"ammonoids: {out.species.nunique()} species, {len(out)} half-whorl diameters")


def derive_nautilus(path):
    rows = []
    for sheet in ("Philippines_WER_WWI", "Malaysia_WER_WWI", "Indonesia_WER_WWI"):
        n = pd.read_excel(path, sheet_name=sheet, header=None)
        pop = sheet.split("_")[0]
        # blocks: a row of specimen numbers, a 'DM WW WER WWI' header row, then one row per
        # 45-degree station (a block may start with an empty station row for one specimen)
        starts = [i for i in range(len(n) - 1) if str(n.iloc[i + 1, 0]).strip() == "DM"]
        for b, i in enumerate(starts):
            end = starts[b + 1] if b + 1 < len(starts) else len(n)
            for col0 in (0, 5):
                spec = n.iloc[i, col0]
                if pd.isna(spec):
                    continue
                stations = []
                for j in range(i + 2, end):
                    dm = n.iloc[j, col0]
                    if isinstance(dm, (int, float, np.integer, np.floating)) and pd.notna(dm):
                        stations.append((float(dm), float(n.iloc[j, col0 + 1])))
                # some Indonesian specimens are listed from the aperture inwards; use ontogenetic order
                if len(stations) > 1 and stations[0][0] > stations[-1][0]:
                    stations.reverse()
                for step, (dm, ww) in enumerate(stations):
                    rows.append({"population": pop, "specimen": f"{pop}-{int(spec)}", "step": step,
                                 "dm": dm, "ww": ww})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DERIVED, "nautilus_dm_45deg.csv"), index=False, float_format="%.4f")
    print(f"nautilus: {out.specimen.nunique()} specimens, {len(out)} 45-degree stations")


def _polygon_centroid_area(xy):
    x, y = xy[:, 0], xy[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cross = x * y1 - x1 * y
    a = cross.sum() / 2.0
    if abs(a) < 1e-12:
        return xy.mean(axis=0), 0.0
    cx = ((x + x1) * cross).sum() / (6 * a)
    cy = ((y + y1) * cross).sum() / (6 * a)
    return np.array([cx, cy]), abs(a)


def derive_gastropods(path):
    """Parse the tpsDig file: per specimen two LM points (coiling axis) and N CURVE outlines
    (apertures at 180-degree steps, oldest first). r = distance of the aperture centroid from
    the axis line, in image pixels (scale cancels in ratios)."""
    with zipfile.ZipFile(path) as z:
        tps_names = [n for n in z.namelist() if n.lower().endswith(".tps")]
        if len(tps_names) != 1:
            sys.exit(f"expected one .tps file in the zip, found {tps_names}")
        text = z.read(tps_names[0]).decode("utf-8", errors="replace")
    blocks = re.split(r"(?m)^(?=LM=)", text)
    rows = []
    for bi, b in enumerate(blocks):
        if not b.startswith("LM="):
            continue
        lines = b.strip().splitlines()
        lm_n = int(lines[0].split("=")[1])
        lm = np.array([[float(v) for v in lines[1 + k].split()] for k in range(lm_n)])
        if lm_n != 2:
            continue
        sid = next((l.split("=", 1)[1].strip() for l in lines if l.startswith("ID=")), None)
        image = next((l.split("=", 1)[1].strip() for l in lines if l.startswith("IMAGE=")), None)
        curves = []
        k = 1 + lm_n
        while k < len(lines):
            if lines[k].startswith("POINTS="):
                npts = int(lines[k].split("=")[1])
                pts = np.array([[float(v) for v in lines[k + 1 + m].split()] for m in range(npts)])
                curves.append(pts)
                k += 1 + npts
            else:
                k += 1
        a, bpt = lm[0], lm[1]
        axis = (bpt - a) / np.linalg.norm(bpt - a)
        for ap, pts in enumerate(curves, start=1):
            c, area = _polygon_centroid_area(pts)
            v = c - a
            r = abs(v[0] * axis[1] - v[1] * axis[0])
            y = float(v @ axis)
            rows.append({"id": norm_id(sid), "tps_id": sid, "block": bi, "image": image, "aperture": ap,
                         "r_px": r, "y_px": y, "area_px2": area})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(DERIVED, "gastropod_aperture_radii.csv"), index=False, float_format="%.3f")
    print(f"gastropods: {out.id.nunique()} specimens, {len(out)} apertures")


def main():
    os.makedirs(DERIVED, exist_ok=True)
    derive_ammonoids(obtain("Ontogenetic_Conch_Parameter_Data.xlsx", FILES["Ontogenetic_Conch_Parameter_Data.xlsx"]))
    derive_nautilus(obtain("Supplementary Table_2.xlsx", FILES["Supplementary Table_2.xlsx"]))
    p = obtain("Collins_et_al_data.zip", FILES["Collins_et_al_data.zip"], required=False)
    if p:
        derive_gastropods(p)
    t = obtain("S_Table_1_Specimens.csv", FILES["S_Table_1_Specimens.csv"], required=False)
    if t:
        meta = pd.read_csv(t, encoding="latin-1")
        meta["ID"] = meta["ID"].map(norm_id)
        meta[["ID", "Genus", "species", "Age", "Number of apertures"]].drop_duplicates("ID").to_csv(
            os.path.join(DERIVED, "gastropod_specimens.csv"), index=False)


if __name__ == "__main__":
    main()
