#!/usr/bin/env python3
"""Test of thompson1917-ch05-24: the biconcave red blood corpuscle is not a surface of constant
mean curvature, hence not a fluid drop in surface-tension equilibrium.

Data: Lee et al. 2022, Figshare 10.6084/m9.figshare.21378744 (Apache 2.0): ground-truth quantitative
phase maps of red blood cells and of 3 um polystyrene beads. Only the pre-registered members of the
1.1 GB zip are read, by HTTP range requests, and each is checked against its ZIP CRC-32.
Packages: requests, numpy, scipy.
Writes derived/summary.json, derived/objects.csv and derived/fetch_log.csv.
"""
import csv
import hashlib
import io
import json
import os
import struct
import zlib
from datetime import datetime, timezone

import numpy as np
import requests
import scipy.io
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
URL = "https://ndownloader.figshare.com/files/38008803"
# Pre-registered as gt_phase1..100; the archive numbers files in blocks of 50 (1-50, 501-550, ...),
# so the first 100 in numeric order are used.
RBC = [f"red_blood_cell/train/gt_phase/gt_phase{i}.mat" for i in list(range(1, 51)) + list(range(501, 551))]
BEADS = [f"polystyrene_bead/train/gt_phase/bead_gt_phase{i}.mat" for i in range(1, 51)]
SENSITIVITY_BEAD_MIN_DIAM_PX = 4  # not pre-registered; beads are ~6-7 px across
FETCH = []


def rng(a, b):
    for _ in range(5):
        r = requests.get(URL, headers={"Range": f"bytes={a}-{b}"}, timeout=120)  # re-resolves the 10 s presigned URL
        if r.status_code == 206:
            return r
    raise RuntimeError(f"range {a}-{b} failed: {r.status_code}")


def zip_index():
    size = int(rng(0, 0).headers["Content-Range"].split("/")[1])
    tail = rng(size - 65536, size - 1).content
    i = tail.rfind(b"PK\x05\x06")
    _, cd_size, cd_off = struct.unpack("<HII", tail[i + 10:i + 20])
    cd = rng(cd_off, cd_off + cd_size - 1).content
    m, p = {}, 0
    while p < len(cd) and cd[p:p + 4] == b"PK\x01\x02":
        meth = struct.unpack("<H", cd[p + 10:p + 12])[0]
        crc, csize, _ = struct.unpack("<III", cd[p + 16:p + 28])
        nl, el, cl = struct.unpack("<HHH", cd[p + 28:p + 34])
        off = struct.unpack("<I", cd[p + 42:p + 46])[0]
        m[cd[p + 46:p + 46 + nl].decode()] = (off, csize, meth, crc)
        p += 46 + nl + el + cl
    return size, hashlib.sha256(cd).hexdigest(), m


def member(index, name):
    path = os.path.join(DATA, name.replace("/", "__"))
    off, csize, meth, crc = index[name]
    if not os.path.exists(path):
        h = rng(off, off + 29).content
        nl, el = struct.unpack("<HH", h[26:30])
        s = off + 30 + nl + el
        raw = rng(s, s + csize - 1).content
        b = raw if meth == 0 else zlib.decompress(raw, -15)
        open(path, "wb").write(b)
        when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        b, when = open(path, "rb").read(), None
    assert zlib.crc32(b) == crc, f"CRC mismatch {name}"
    FETCH.append({"member": name, "zip_offset": off, "retrieved_at": when, "byte_size": len(b), "sha256": hashlib.sha256(b).hexdigest()})
    d = scipy.io.loadmat(io.BytesIO(b))
    return np.asarray(d["gt_phase"], float), FETCH[-1]["sha256"]


def objects(v, min_diam):
    bs = v - np.median(v)
    mask = bs > 0.25 * np.percentile(bs, 99)
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    out = []
    for i, sl in enumerate(ndimage.find_objects(lab), start=1):
        comp = ndimage.binary_fill_holes(lab[sl] == i)
        if sl[0].start == 0 or sl[1].start == 0 or sl[0].stop == v.shape[0] or sl[1].stop == v.shape[1]:
            continue
        area = comp.sum()
        diam = 2 * np.sqrt(area / np.pi)
        if diam < min_diam:
            continue
        yy, xx = np.nonzero(comp)
        cov = np.cov(np.vstack([yy, xx]))
        ev = np.sort(np.linalg.eigvalsh(cov))
        aspect = float(np.sqrt(ev[1] / max(ev[0], 1e-9)))
        if aspect > PRE["max_aspect_ratio"]:
            continue
        cy, cx = yy.mean(), xx.mean()
        r = np.hypot(yy - cy, xx - cx)
        t = bs[sl][comp]
        r_edge = diam / 2
        bins = np.arange(0, np.ceil(r.max()) + 1, 1.0)
        idx = np.digitize(r, bins) - 1
        prof = np.array([t[idx == k].mean() if (idx == k).any() else np.nan for k in range(len(bins) - 1)])
        centres = bins[:-1] + 0.5
        k = int(np.nanargmax(prof))
        r_crest = float(centres[k])
        sel = r <= PRE["centre_fit_max_r_over_rcrest"] * r_crest
        if sel.sum() < 4:
            out.append({"diam_px": diam, "aspect": aspect, "r_crest_over_r_edge": r_crest / r_edge, "b": np.nan, "n_fit": int(sel.sum()), "sign_change": None})
            continue
        b, a = np.polyfit(r[sel] ** 2, t[sel], 1)
        sc = bool(b > 0 and r_crest >= PRE["min_rcrest_over_redge"] * r_edge)
        out.append({"diam_px": float(diam), "aspect": aspect, "r_crest_over_r_edge": r_crest / r_edge, "b": float(b),
                    "n_fit": int(sel.sum()), "sign_change": sc, "dimple_depth_frac": float((np.nanmax(prof) - prof[0]) / np.nanmax(prof))})
    return out


def run(index, names, kind, min_diam, seen):
    rows = []
    for name in names:
        v, sha = member(index, name)
        if (kind, sha) in seen:
            continue
        seen.add((kind, sha))
        for o in objects(v, min_diam):
            o.update({"kind": kind, "file": name.rsplit("/", 1)[1]})
            rows.append(o)
    return rows


def frac(rows):
    a = [r for r in rows if r["sign_change"] is not None]
    return (sum(r["sign_change"] for r in a) / len(a) if a else float("nan")), len(a)


def main():
    os.makedirs(DATA, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    zip_size, cd_sha, index = zip_index()
    seen = set()
    rbc = run(index, RBC, "rbc", PRE["min_diameter_px"], seen)
    beads = run(index, BEADS, "bead", PRE["min_diameter_px"], set())
    beads_sens = run(index, BEADS, "bead", SENSITIVITY_BEAD_MIN_DIAM_PX, set())
    n_unique_rbc = len({s for k, s in seen if k == "rbc"})
    f_rbc, n_rbc = frac(rbc)
    f_bead, n_bead = frac(beads)
    f_bead_s, n_bead_s = frac(beads_sens)

    def verdict(fr, nr, fb, nb):
        if nr < PRE["min_rbc"] or nb < PRE["min_beads"]:
            return "inconclusive", "underpowered"
        if fb > PRE["max_bead_fraction"]:
            return "inconclusive", "other"
        if fr >= PRE["pass_rbc_fraction"]:
            return "supports", None
        if fr <= PRE["fail_rbc_fraction"]:
            return "refutes", None
        return "mixed", None
    v, reason = verdict(f_rbc, n_rbc, f_bead, n_bead)
    v_s, reason_s = verdict(f_rbc, n_rbc, f_bead_s, n_bead_s)
    diam = np.array([r["diam_px"] for r in rbc])
    bdiam = np.array([r["diam_px"] for r in beads_sens])
    measured = {
        "value": round(float(f_rbc), 4),
        "unit": "fraction of analysable red cells whose upper-surface mean curvature changes sign between the central dimple and the rim crest",
        "n": n_rbc,
        "uncertainty": f"{n_rbc} RBC profiles from {n_unique_rbc} unique phase maps; pre-registered bead control: {n_bead} analysable beads",
        "extra": {
            "n_rbc_files_requested": len(RBC), "n_rbc_files_unique": n_unique_rbc,
            "rbc_median_diameter_px": float(np.median(diam)) if len(diam) else None,
            "rbc_median_dimple_depth_frac": float(np.nanmedian([r.get("dimple_depth_frac", np.nan) for r in rbc])) if rbc else None,
            "beads_analysable_preregistered": n_bead, "bead_sign_change_fraction_preregistered": None if n_bead == 0 else float(f_bead),
            "verdict_preregistered": v, "reason_preregistered": reason,
            "sensitivity_not_preregistered": {"bead_min_diameter_px": SENSITIVITY_BEAD_MIN_DIAM_PX, "beads_analysable": n_bead_s,
                                               "bead_sign_change_fraction": float(f_bead_s), "bead_median_diameter_px": float(np.median(bdiam)) if len(bdiam) else None,
                                               "verdict_if_applied": v_s, "reason_if_applied": reason_s},
        },
    }
    with open(os.path.join(DERIVED, "objects.csv"), "w", newline="") as fh:
        keys = ["kind", "file", "diam_px", "aspect", "r_crest_over_r_edge", "b", "n_fit", "sign_change", "dimple_depth_frac"]
        w = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        for r in rbc + beads_sens:
            w.writerow({k: (round(r[k], 5) if isinstance(r.get(k), float) else r.get(k)) for k in keys})
    with open(os.path.join(DERIVED, "fetch_log.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["member", "zip_offset", "retrieved_at", "byte_size", "sha256"])
        w.writeheader()
        uniq = {}
        for r in FETCH:
            uniq.setdefault(r["member"], r)
        w.writerows(uniq.values())
    out = {"measured": measured, "verdict": v, "reason": reason, "zip": {"url": URL, "byte_size": zip_size, "central_directory_sha256": cd_sha}}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
