#!/usr/bin/env python3
"""Test of thompson1917-ch07-08: regular hexagons occur only where cells are uniform in size.

Within-tissue test on the human retinal pigment epithelium (Thompson's showcase of regular
hexagons) using the corrected RPE cell-boundary segmentations of Granger et al. 2018
(Dryad doi:10.5061/dryad.b41j15h; 10 participants, regions of interest across the macula,
in vivo adaptive-optics autofluorescence imaging).

Per ROI: cells = 4-connected components of non-boundary pixels; neighbours = cells sharing a
boundary pixel's 3x3 neighbourhood; cells touching the ROI border, oversized components
(unsegmented regions, area > 3x the median interior cell area) and cells adjacent to such
regions are excluded from the statistics. ROI metrics: CV of cell area (CV_A), fraction of
six-sided cells (f6), SD of neighbour number (SD_n). Pre-registered test: Spearman rho(f6, CV_A)
across ROIs with >= 30 counted cells, and the f6 difference between lowest- and highest-CV_A
quartiles.

Run: python3 analysis.py   (downloads ~85 MB of zips into ./data/, writes ./derived/)
"""
import datetime, hashlib, io, json, os, re, struct, sys, time, urllib.parse, zipfile
import numpy as np
import pandas as pd
import requests
from scipy import ndimage, stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

# Dryad file ids of the ten participant archives (dataset version 1, published 2018)
PARTICIPANTS = {"NOR011": 92638, "NOR025": 92640, "NOR047": 92642, "NOR053": 92644, "NOR057": 92646,
                "NOR062": 92648, "NOR063": 92650, "NOR064": 92652, "NOR065": 92654, "NOR073": 92656}
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")


# ------------------------------------------------------------------ download (Dryad + Anubis)
def _solve_anubis(random_data, difficulty):
    prefix = "0" * difficulty
    nonce = 0
    while True:
        h = hashlib.sha256((random_data + str(nonce)).encode()).hexdigest()
        if h.startswith(prefix):
            return h, nonce
        nonce += 1


def dryad_download(file_id, timeout=300):
    url = f"https://datadryad.org/downloads/file_stream/{file_id}"
    s = requests.Session()
    s.headers["User-Agent"] = UA
    r = s.get(url, timeout=timeout)
    if r.headers.get("content-type", "").startswith("text/html") and "anubis_challenge" in r.text[:8000]:
        m = re.search(r'id="anubis_challenge" type="application/json">(.*?)</script>', r.text, re.S)
        ch = json.loads(m.group(1))
        t0 = time.time()
        h, nonce = _solve_anubis(ch["challenge"]["randomData"], ch["rules"]["difficulty"])
        q = urllib.parse.urlencode({"id": ch["challenge"]["id"], "response": h, "nonce": nonce,
                                    "redir": url, "elapsedTime": int((time.time() - t0) * 1000) + 1})
        r = s.get("https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge?" + q, timeout=timeout)
    r.raise_for_status()
    return r.content, url


def fetch_all():
    meta = {}
    for pid, fid in PARTICIPANTS.items():
        path = os.path.join(DATA, f"{pid}.zip")
        if not os.path.exists(path):
            content, url = dryad_download(fid)
            open(path, "wb").write(content)
            retrieved = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            content = open(path, "rb").read()
            url = f"https://datadryad.org/downloads/file_stream/{fid}"
            retrieved = None
        meta[pid] = dict(download_url=url, byte_size=len(content), sha256=hashlib.sha256(content).hexdigest(),
                         retrieved_at=retrieved)
    return meta


# ------------------------------------------------------------------ minimal TIFF reader
TYPESZ = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
TYPEFMT = {1: "B", 3: "H", 4: "I", 6: "b", 8: "h", 9: "i"}


def read_tiff(b):
    """Uncompressed 1-bit or 8-bit grayscale TIFF -> uint8 array (255 = boundary line)."""
    bo = "<" if b[:2] == b"II" else ">"
    off = struct.unpack(bo + "I", b[4:8])[0]
    n = struct.unpack(bo + "H", b[off:off + 2])[0]
    t = {}
    for i in range(n):
        e = b[off + 2 + 12 * i: off + 14 + 12 * i]
        tag, typ, cnt = struct.unpack(bo + "HHI", e[:8])
        fmt = TYPEFMT.get(typ)
        if fmt is None:
            continue
        sz = TYPESZ[typ] * cnt
        if sz <= 4:
            v = struct.unpack(bo + fmt * cnt, e[8:8 + sz])
        else:
            o = struct.unpack(bo + "I", e[8:12])[0]
            v = struct.unpack(bo + fmt * cnt, b[o:o + sz])
        t[tag] = v
    w, h = t[256][0], t[257][0]
    bps, comp, photo = t[258][0], t[259][0], t[262][0]
    if comp != 1:
        raise ValueError(f"compression {comp} unsupported")
    data = b"".join(b[o:o + c] for o, c in zip(t[273], t[279]))
    if bps == 8:
        img = np.frombuffer(data, np.uint8).reshape(h, w).copy()
        if photo == 0:
            img = 255 - img
    elif bps == 1:
        rowbytes = (w + 7) // 8
        bits = np.unpackbits(np.frombuffer(data, np.uint8).reshape(h, rowbytes), axis=1)[:, :w]
        if photo == 0:
            bits = 1 - bits
        img = (bits * 255).astype(np.uint8)
    else:
        raise ValueError(f"bits per sample {bps}")
    return img


# ------------------------------------------------------------------ cell statistics
def roi_cells(img):
    """Return per-cell (label, area, n_neighbours, touches_border) and the adjacency sets."""
    boundary = img > 127
    labels, n = ndimage.label(~boundary, structure=[[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    if n == 0:
        return None
    areas = ndimage.sum(np.ones_like(labels), labels, index=np.arange(1, n + 1))
    border = set(np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]])))
    border.discard(0)
    # adjacency through boundary pixels: labels present in each boundary pixel's 3x3 neighbourhood
    adj = {i: set() for i in range(1, n + 1)}
    ys, xs = np.nonzero(boundary)
    H, W = labels.shape
    for y, x in zip(ys, xs):
        patch = labels[max(0, y - 1):y + 2, max(0, x - 1):x + 2]
        ls = np.unique(patch)
        ls = ls[ls > 0]
        for a in ls:
            for c in ls:
                if a != c:
                    adj[int(a)].add(int(c))
    return labels, areas, border, adj


def roi_metrics(img):
    out = roi_cells(img)
    if out is None:
        return None
    labels, areas, border, adj = out
    n = len(areas)
    interior = [i for i in range(1, n + 1) if i not in border]
    if len(interior) < 5:
        return None
    med = np.median([areas[i - 1] for i in interior])
    huge = {i for i in range(1, n + 1) if areas[i - 1] > 3 * med}      # unsegmented regions
    counted = [i for i in interior if i not in huge and not (adj[i] & huge) and len(adj[i]) >= 3]
    if len(counted) == 0:
        return None
    a = np.array([areas[i - 1] for i in counted], float)
    k = np.array([len(adj[i]) for i in counted], int)
    return dict(n_cells=len(counted), n_components=n, n_border=len(border), n_huge=len(huge),
                median_area_px=float(np.median(a)), cv_area=float(a.std(ddof=1) / a.mean()) if len(a) > 1 else np.nan,
                mean_sides=float(k.mean()), sd_sides=float(k.std(ddof=1)) if len(k) > 1 else np.nan,
                f6=float((k == 6).mean()), f5=float((k == 5).mean()), f7=float((k == 7).mean()))


def main():
    meta = fetch_all()
    rows = []
    for pid in PARTICIPANTS:
        z = zipfile.ZipFile(os.path.join(DATA, f"{pid}.zip"))
        for name in z.namelist():
            if "Corrected Segmentation" in name and name.lower().endswith(".tif"):
                try:
                    img = read_tiff(z.read(name))
                except ValueError as e:
                    print(f"skip {name}: {e}", file=sys.stderr)
                    continue
                m = roi_metrics(img)
                if m is None:
                    continue
                roi = os.path.basename(name).replace("_RPE.tif", "")
                rows.append(dict(participant=pid, roi=roi, **m))
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "rpe_roi_metrics.csv"), index=False)

    d = df[df.n_cells >= 30].copy()
    rho, p = stats.spearmanr(d.f6, d.cv_area)
    rho_sd, p_sd = stats.spearmanr(d.sd_sides, d.cv_area)
    q = d.cv_area.quantile([0.25, 0.75])
    low = d[d.cv_area <= q[0.25]]; high = d[d.cv_area >= q[0.75]]
    within = []
    for pid, g in d.groupby("participant"):
        if len(g) >= 6:
            within.append(stats.spearmanr(g.f6, g.cv_area)[0])
    slope, intercept, r, p_lin, se = stats.linregress(d.cv_area, d.f6)
    res = dict(
        n_rois_total=int(len(df)), n_rois_ge30_cells=int(len(d)), n_participants=int(d.participant.nunique()),
        n_cells_counted=int(d.n_cells.sum()),
        spearman_rho_f6_vs_cv_area=round(float(rho), 3), p_value=float(p),
        spearman_rho_sdsides_vs_cv_area=round(float(rho_sd), 3), p_value_sd=float(p_sd),
        f6_lowest_cv_quartile=round(float(low.f6.mean()), 3), f6_highest_cv_quartile=round(float(high.f6.mean()), 3),
        f6_quartile_difference=round(float(low.f6.mean() - high.f6.mean()), 3),
        cv_area_quartile_means=[round(float(low.cv_area.mean()), 3), round(float(high.cv_area.mean()), 3)],
        within_participant_rho_mean=round(float(np.mean(within)), 3) if within else None,
        within_participant_rho_values=[round(float(x), 3) for x in within],
        ols_f6_on_cv_area_slope=round(float(slope), 3), ols_r2=round(float(r ** 2), 3),
        overall_mean_f6=round(float(d.f6.mean()), 3), overall_mean_cv_area=round(float(d.cv_area.mean()), 3),
        overall_mean_sides=round(float(d.mean_sides.mean()), 3),
        f6_range=[round(float(d.f6.min()), 3), round(float(d.f6.max()), 3)],
        cv_area_range=[round(float(d.cv_area.min()), 3), round(float(d.cv_area.max()), 3)],
    )
    # sensitivity (not pre-registered): looser cell-count thresholds, and within-participant correlations
    sens = {}
    for thr in (15, 20):
        s = df[df.n_cells >= thr]
        r_, p_ = stats.spearmanr(s.f6, s.cv_area)
        w = [stats.spearmanr(g.f6, g.cv_area)[0] for _, g in s.groupby("participant") if len(g) >= 6]
        sens[f"min_{thr}_cells"] = dict(n_rois=int(len(s)), rho=round(float(r_), 3), p=float(p_),
                                        within_participant_rho_mean=round(float(np.mean(w)), 3) if w else None,
                                        n_participants_with_ge6_rois=len(w))
    res["sensitivity_not_preregistered"] = sens
    res["decision"] = dict(
        pass_rho_le_minus_0_3_and_p_lt_0_01=bool(rho <= -0.3 and p < 0.01),
        pass_quartile_diff_ge_0_10=bool(res["f6_quartile_difference"] >= 0.10),
        fail_rho_ge_0=bool(rho >= 0),
        fail_nonsignificant_and_small=bool(p >= 0.05 and res["f6_quartile_difference"] < 0.05),
        underpowered=bool(len(d) < 20),
    )
    print(json.dumps(dict(result=res, files=meta), indent=2, default=str))


if __name__ == "__main__":
    main()
