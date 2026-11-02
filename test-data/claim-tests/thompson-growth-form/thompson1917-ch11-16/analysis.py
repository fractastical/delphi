#!/usr/bin/env python3
"""Test thompson1917-ch11-16: bivalve growth lines are coaxial curves through the umbo.

The photograph list, the segmentation rule and the pass/fail thresholds are the
pre-registered text in result.json. Engravings are not in the list. This script
downloads the frozen Commons files, traces commarginal ridges, and compares a
shared curve scaled from the umbo with concentric circles.
"""
import hashlib, json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

UA = "delphi-claim-test/1.0 (thompson1917-ch11-16; research)"
TITLES = [
    "File:Anomia ephippium.jpg",
    "File:Anomia ephippium 362978191.jpg",
    "File:Anomia ephippium 383519847.jpg",
    "File:Anomia ephippium 470222550.jpg",
    "File:Naturalis Biodiversity Center - ZMA.MOLL.417383 - Anomia ephippium Linnaeus, 1758 - Anomiidae - Mollusc shell.jpeg",
    "File:Tellina alternata shell.png",
    "File:Tellina iheringi.jpg",
    "File:Tellina bodegensis.jpg",
    "File:Tellina nuculoides.jpg",
    "File:Tellinella listeri.jpg",
    "File:Limatula maoria.JPG",
    "File:Naturalis Biodiversity Center - RMNH.MOL.321865 - Limatula strangei (Sowerby, 1872) - Limidae - Mollusc shell.jpeg",
    "File:Naturalis Biodiversity Center - ZMA.MOLL.414959 - Limatula leptocarya (Melvill, 1898) - Limidae - Mollusc shell.jpeg",
]
# Thompson's tabulated a/b ratios, including the circle a/b = 1.
ELLIPSE_RATIOS = (1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0)


def genus_of(title):
    if "Anomia" in title:
        return "Anomia"
    if "Limatula" in title or "Lima " in title:
        return "Lima"
    if "Tellinella" in title or "Tellina" in title:
        return "Tellinidae"
    return "other"


def slug(title):
    keep = [c.lower() if c.isalnum() else "-" for c in title.replace("File:", "")]
    s = "".join(keep).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s[:80]


def commons_urls():
    q = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "titles": "|".join(TITLES), "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "format": "json",
    })
    req = urllib.request.Request(q, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.load(r)
    found = {}
    for page in payload["query"]["pages"].values():
        if "missing" in page or "imageinfo" not in page:
            continue
        info = page["imageinfo"][0]
        extra = info.get("extmetadata") or {}
        lic = extra.get("LicenseShortName") or {}
        found[page["title"]] = {
            "url": info["url"].split("?")[0],
            "mime": info["mime"],
            "expected_size": info["size"],
            "license": lic.get("value") if isinstance(lic, dict) else None,
        }
    return found


def fetch(title, meta):
    ext = ".png" if meta["mime"] == "image/png" else ".jpg"
    path = os.path.join(DATA, slug(title) + ext)
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        blob = open(path, "rb").read()
    else:
        blob = None
        for attempt in range(6):
            try:
                time.sleep(2 + attempt)
                req = urllib.request.Request(meta["url"], headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=120) as r:
                    blob = r.read()
                break
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt < 5:
                    time.sleep(8 + 4 * attempt)
                    continue
                raise
        with open(path, "wb") as f:
            f.write(blob)
    return {
        "title": title,
        "genus": genus_of(title),
        "download_url": meta["url"],
        "mime": meta["mime"],
        "license": meta.get("license"),
        "byte_size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "retrieved_at": datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "path": path,
    }


def otsu(values):
    hist, _ = np.histogram(values, bins=256, range=(0, 255))
    total = hist.sum()
    if total == 0:
        return 128.0
    prob = hist.astype(float) / total
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * np.arange(256))
    mu_t = mu[-1]
    sigma = (mu_t * omega - mu) ** 2 / np.maximum(omega * (1 - omega), 1e-12)
    return float(np.argmax(sigma))


def largest_shell(rgb):
    """Foreground against the corner colour. Returns a bool mask or None."""
    h, w, _ = rgb.shape
    corners = np.concatenate([
        rgb[:15, :15].reshape(-1, 3),
        rgb[:15, -15:].reshape(-1, 3),
        rgb[-15:, :15].reshape(-1, 3),
        rgb[-15:, -15:].reshape(-1, 3),
    ])
    bg = np.median(corners, axis=0)
    dist = np.sqrt(np.sum((rgb.astype(float) - bg) ** 2, axis=2))
    thr = otsu(np.clip(dist, 0, 255))
    # A low threshold on a pale shell against white still needs a floor so
    # sensor noise is not the whole frame.
    mask = dist >= max(thr, 12.0)
    labeled, n = ndimage.label(mask)
    if n == 0:
        return None, "no-foreground"
    counts = np.bincount(labeled.ravel())
    counts[0] = 0
    keep = counts.argmax()
    shell = labeled == keep
    frac = float(shell.mean())
    if frac < 0.05 or frac > 0.85:
        return None, f"mask-fraction-{frac:.3f}"
    shell = ndimage.binary_fill_holes(shell)
    return shell, "ok"


def contour_of(mask):
    er = ndimage.binary_erosion(mask)
    edge = mask & ~er
    ys, xs = np.nonzero(edge)
    if len(xs) < 50:
        return None
    # Order the outline by angle about its centroid so curvature is along the boundary.
    cx, cy = xs.mean(), ys.mean()
    ang = np.arctan2(ys - cy, xs - cx)
    order = np.argsort(ang)
    return np.column_stack([xs[order], ys[order]])


def umbo_of(contour):
    """Point of maximum curvature on a contour resampled every ~2 pixels."""
    if len(contour) < 30:
        return None
    # Resample to roughly uniform spacing by taking every k-th point.
    step = max(1, len(contour) // 400)
    p = contour[::step].astype(float)
    if len(p) < 25:
        return None
    # Smooth with a 5-point moving average along the closed curve.
    pad = np.vstack([p[-2:], p, p[:2]])
    kernel = np.array([1, 2, 3, 2, 1], float)
    kernel /= kernel.sum()
    sm = np.column_stack([np.convolve(pad[:, 0], kernel, mode="valid"),
                          np.convolve(pad[:, 1], kernel, mode="valid")])
    sm = sm[2:-2]
    if len(sm) < 15:
        return None
    v1 = sm - np.roll(sm, 1, axis=0)
    v2 = np.roll(sm, -1, axis=0) - sm
    n1 = np.maximum(np.linalg.norm(v1, axis=1), 1e-6)
    n2 = np.maximum(np.linalg.norm(v2, axis=1), 1e-6)
    cosang = np.sum((v1 / n1[:, None]) * (v2 / n2[:, None]), axis=1)
    curvature = 1 - np.clip(cosang, -1, 1)
    i = int(np.argmax(curvature))
    return float(sm[i, 0]), float(sm[i, 1])


def growth_lines(rgb, mask, umbo):
    """Commarginal ridges: strong edges whose normal is nearly radial about the umbo."""
    gray = rgb.mean(axis=2)
    gy, gx = np.gradient(gray)
    mag = np.hypot(gx, gy)
    ux, uy = umbo
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    rx, ry = xx - ux, yy - uy
    rad = np.hypot(rx, ry)
    # Erode away the outline, which is not an internal growth line.
    band = max(2, int(0.02 * min(mask.shape)))
    inner = ndimage.binary_erosion(mask, iterations=band)
    unit_r = np.maximum(rad, 1e-6)
    # Gradient parallel to the radius means the edge itself is commarginal.
    align = np.abs(gx * rx + gy * ry) / (mag * unit_r + 1e-6)
    score = mag * align
    score = np.where(inner, score, 0)
    if score.max() <= 0:
        return []
    cutoff = np.percentile(score[inner], 92)
    edge = score >= cutoff
    theta = np.arctan2(ry, rx)
    rmax = float(np.percentile(rad[mask], 99))
    if rmax <= 1:
        return []
    n_th, n_r = 180, 60
    th_bin = np.clip(((theta + np.pi) / (2 * np.pi) * n_th).astype(int), 0, n_th - 1)
    r_bin = np.clip((rad / rmax * (n_r - 1)).astype(int), 0, n_r - 1)
    hist = np.zeros((n_th, n_r), float)
    flat_th = th_bin[edge]
    flat_r = r_bin[edge]
    np.add.at(hist, (flat_th, flat_r), 1)
    hist = ndimage.gaussian_filter(hist, sigma=(1.0, 0.6))
    if hist.max() <= 0:
        return []
    ridges = hist >= max(np.percentile(hist[hist > 0], 75), 1.0)
    labeled, nlab = ndimage.label(ridges)
    lines = []
    for lab in range(1, nlab + 1):
        ys, xs = np.nonzero(labeled == lab)
        if len(ys) < 8:
            continue
        span_bins = len(np.unique(ys))
        span_deg = span_bins * (360.0 / n_th)
        if span_deg < 100 or span_bins < 30:
            continue
        # One radius per angle bin: the bin centre, in pixels.
        pts = []
        for b in np.unique(ys):
            rb = np.median(xs[ys == b])
            ang = (b + 0.5) / n_th * 2 * np.pi - np.pi
            radius = (rb + 0.5) / (n_r - 1) * rmax
            pts.append((ang, radius))
        pts = np.array(pts, float)
        if len(pts) >= 30:
            lines.append(pts)
    # The outline itself is the last growth line.
    outline = mask & ~ndimage.binary_erosion(mask)
    if outline.sum() > 30:
        o_th = theta[outline]
        o_r = rad[outline]
        bins = np.linspace(-np.pi, np.pi, n_th + 1)
        pts = []
        for i in range(n_th):
            sel = (o_th >= bins[i]) & (o_th < bins[i + 1])
            if sel.sum() < 2:
                continue
            pts.append(((bins[i] + bins[i + 1]) / 2, float(np.median(o_r[sel]))))
        if len(pts) >= 30:
            lines.append(np.array(pts, float))
    return lines


def coaxial_template_rmse(lines):
    """r = t_i f(theta), f the median shape, two iterations."""
    # Common grid.
    grid = np.linspace(-np.pi, np.pi, 72, endpoint=False)
    samples = []
    for pts in lines:
        th, r = pts[:, 0], pts[:, 1]
        # Map each grid node to the nearest sample within 8 degrees.
        sampled = []
        for g in grid:
            d = np.abs((th - g + np.pi) % (2 * np.pi) - np.pi)
            if d.min() > np.radians(8):
                sampled.append(np.nan)
            else:
                sampled.append(r[d.argmin()])
        samples.append(np.array(sampled, float))
    samples = np.array(samples)
    t = np.nanmedian(samples, axis=1)
    t = np.where(t > 0, t, np.nan)
    shape = samples / t[:, None]
    f = np.nanmedian(shape, axis=0)
    if np.sum(np.isfinite(f)) < 10:
        return None
    # Refresh scales.
    pred = t[:, None] * f[None, :]
    ratio = samples / pred
    t = np.nanmedian(ratio, axis=1) * t
    pred = t[:, None] * f[None, :]
    err = np.abs(samples - pred) / np.nanmedian(samples, axis=1)[:, None]
    if not np.isfinite(err).any():
        return None
    return float(np.nanmean(err))


def lines_to_xy(lines, umbo):
    ux, uy = umbo
    out = []
    for pts in lines:
        x = ux + pts[:, 1] * np.cos(pts[:, 0])
        y = uy + pts[:, 1] * np.sin(pts[:, 0])
        out.append(np.column_stack([x, y, pts[:, 0], pts[:, 1]]))
    return out


def concentric_from_xy(xylines, outline_xy):
    xmin, ymin = outline_xy.min(axis=0)
    xmax, ymax = outline_xy.max(axis=0)
    step_x = 0.04 * max(xmax - xmin, 1)
    step_y = 0.04 * max(ymax - ymin, 1)
    best = np.inf
    best_c = None
    for cx in np.arange(xmin, xmax + step_x, step_x):
        for cy in np.arange(ymin, ymax + step_y, step_y):
            errs = []
            for pts in xylines:
                d = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
                radius = np.median(d)
                if radius <= 1:
                    continue
                errs.append(np.abs(d - radius) / radius)
            if not errs:
                continue
            val = float(np.mean(np.concatenate(errs)))
            if val < best:
                best = val
                best_c = (float(cx), float(cy))
    if best_c is None:
        return None
    return best


def circle_through_umbo_rmse(lines):
    """r = t_i cos(theta - theta0), theta0 shared, searched every 2 degrees."""
    best = np.inf
    best_th = None
    for theta0 in np.radians(np.arange(0, 360, 2)):
        errs = []
        ok = True
        for pts in lines:
            c = np.cos(pts[:, 0] - theta0)
            use = c > 0.15
            if use.sum() < 15:
                ok = False
                break
            f = c[use]
            r = pts[use, 1]
            t = float(np.dot(r, f) / np.dot(f, f))
            if t <= 0:
                ok = False
                break
            errs.append(np.abs(r - t * f) / np.median(r))
        if not ok or not errs:
            continue
        val = float(np.mean(np.concatenate(errs)))
        if val < best:
            best = val
            best_th = float(theta0)
    if best_th is None:
        return None
    return best


def thompson_ellipse_rmse(lines):
    """Thompson's coaxial ellipse, best a/b on his table and axis every 5 degrees."""
    best = np.inf
    best_ratio = None
    for ratio in ELLIPSE_RATIOS:
        a, b = ratio, 1.0
        for phi in np.radians(np.arange(0, 180, 5)):
            errs = []
            ok = True
            for pts in lines:
                c = np.cos(pts[:, 0] - phi)
                denom = (b * b - a * a) * c * c + a * a
                f = (2 * a * b * b * c) / denom
                use = f > 0.05
                if use.sum() < 15:
                    ok = False
                    break
                ff, rr = f[use], pts[use, 1]
                # Normalise f so the scale t is a length.
                t = float(np.dot(rr, ff) / np.dot(ff, ff))
                if t <= 0:
                    ok = False
                    break
                errs.append(np.abs(rr - t * ff) / np.median(rr))
            if not ok or not errs:
                continue
            val = float(np.mean(np.concatenate(errs)))
            if val < best:
                best = val
                best_ratio = float(ratio)
    if best_ratio is None:
        return None, None
    return best, best_ratio


def analyse_image(record):
    im = Image.open(record["path"]).convert("RGB")
    im.thumbnail((700, 700))
    rgb = np.asarray(im).astype(float)
    mask, status = largest_shell(rgb)
    result = {
        "title": record["title"],
        "genus": record["genus"],
        "sha256": record["sha256"],
        "byte_size": record["byte_size"],
        "status": status,
        "qualifying": False,
    }
    if mask is None:
        return result
    contour = contour_of(mask)
    if contour is None:
        result["status"] = "no-contour"
        return result
    umbo = umbo_of(contour)
    if umbo is None:
        result["status"] = "no-umbo"
        return result
    lines = growth_lines(rgb, mask, umbo)
    result["n_lines"] = len(lines)
    if len(lines) < 4:
        result["status"] = "fewer-than-4-lines"
        return result
    co = coaxial_template_rmse(lines)
    xy = lines_to_xy(lines, umbo)
    outline_xy = contour.astype(float)
    conc = concentric_from_xy(xy, outline_xy)
    circ = circle_through_umbo_rmse(lines)
    elli, ratio = thompson_ellipse_rmse(lines)
    if co is None or conc is None:
        result["status"] = "fit-failed"
        return result
    result.update({
        "qualifying": True,
        "status": "ok",
        "rmse_coaxial": round(co, 5),
        "rmse_concentric": round(conc, 5),
        "ratio_coaxial_over_concentric": round(co / conc, 5) if conc else None,
        "rmse_circle": None if circ is None else round(circ, 5),
        "rmse_ellipse": None if elli is None else round(elli, 5),
        "ellipse_a_over_b": ratio,
        "circle_over_ellipse": None if (circ is None or elli is None or elli == 0) else round(circ / elli, 5),
    })
    return result


def main():
    meta = commons_urls()
    records = []
    missing = []
    for title in TITLES:
        if title not in meta:
            missing.append(title)
            continue
        records.append(fetch(title, meta[title]))
    per_image = [analyse_image(rec) for rec in records]
    qualifying = [r for r in per_image if r.get("qualifying")]
    anomia = [r for r in qualifying if r["genus"] == "Anomia"]
    n_q, n_a = len(qualifying), len(anomia)
    if n_q == 0:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n_q < 6 or n_a < 2:
        verdict, reason = "inconclusive", "underpowered"
    else:
        ratios = np.array([r["ratio_coaxial_over_concentric"] for r in qualifying], float)
        frac_better = float(np.mean(ratios < 1))
        med = float(np.median(ratios))
        anomia_ratio = np.array([r["circle_over_ellipse"] for r in anomia if r["circle_over_ellipse"] is not None], float)
        med_anomia = float(np.median(anomia_ratio)) if len(anomia_ratio) else None
        coaxial_wins = frac_better >= 0.75 and med <= 0.80
        anomia_circle = med_anomia is not None and med_anomia <= 1.25
        coaxial_loses = frac_better <= 0.25 or med >= 1.25
        # fail_criterion: coaxial higher on >= 75% (that is frac of coaxial-better <= 0.25) OR median ratio >= 1.25
        # OR Anomia circle/ellipse >= 2
        anomia_fails = med_anomia is not None and med_anomia >= 2.0
        if coaxial_loses or anomia_fails:
            verdict, reason = "refutes", None
        elif coaxial_wins and anomia_circle:
            verdict, reason = "supports", None
        else:
            verdict, reason = "mixed", None
        summary_stats = {
            "n_qualifying": n_q,
            "n_anomia": n_a,
            "fraction_coaxial_rmse_lower": round(frac_better, 4),
            "median_ratio_coaxial_over_concentric": round(med, 4),
            "median_anomia_circle_over_ellipse": None if med_anomia is None else round(med_anomia, 4),
        }
    else_summary = {
        "n_qualifying": n_q,
        "n_anomia": n_a,
    }
    if n_q >= 6 and n_a >= 2:
        else_summary = summary_stats
    measured = {
        "verdict": verdict,
        "reason": reason,
        "summary": else_summary,
        "images": [{k: v for k, v in r.items() if k != "path"} for r in per_image],
        "missing_titles": missing,
        "files": [{k: v for k, v in rec.items() if k != "path"} for rec in records],
    }
    with open(os.path.join(DERIVED, "measured.json"), "w", encoding="utf-8") as f:
        json.dump(measured, f, indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "summary": else_summary,
                      "per_image": [(r["genus"], r["status"], r.get("n_lines"), r.get("ratio_coaxial_over_concentric")) for r in per_image]}, indent=2))


if __name__ == "__main__":
    main()
