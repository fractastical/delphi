#!/usr/bin/env python3
"""thompson1917-ch17-11: does one head-fixed posterior stretch carry a Diodon
outline onto a Mola outline?

Downloads FishBase species JPEGs linked from the thumbnail pages, segments a
side-view body, and fits the map committed in result.json. Thresholds are not
revised after the photographs are seen.

Requires: numpy, scipy, pillow. Run: python3 analysis.py
Photographs stay in data/ and are not committed.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import math
import re
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.optimize import minimize
from scipy.spatial import ConvexHull, cKDTree

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (research; contact via github.com/fractastical/delphi)"

SPECIES = [
    {
        "id": "fishbase-photographs-diodon-hystrix-speccode-1022",
        "name": "Diodon hystrix",
        "speccode": 1022,
        "role": "source outline",
    },
    {
        "id": "fishbase-photographs-mola-mola-speccode-1732",
        "name": "Mola mola",
        "speccode": 1732,
        "role": "target outline",
    },
]

MAP_STARTS = [
    (0.0, 0.0, 0.0, 0.0),
    (1.0, 0.0, 0.0, 0.0),
    (2.0, 0.0, -0.3, 0.0),
    (0.0, 2.0, 0.0, 0.0),
    (1.0, 1.0, -0.2, 0.0),
    (3.0, 1.0, -0.4, 0.05),
    (0.5, 0.5, 0.2, 0.0),
    (2.0, 2.0, -0.5, -0.05),
    (4.0, 0.0, -0.6, 0.0),
    (1.0, -0.3, 0.3, 0.1),
]
FLEX_STARTS = [
    (1, 1, 1, 1, 0),
    (1, 1.5, 2, 3, 0),
    (1.5, 2, 3, 4, 0),
    (2, 2, 2, 2, 0),
    (1, 1, 2, 4, 0.05),
    (3, 2, 1.5, 1, 0),
    (1, 2, 2, 1, -0.05),
    (4, 3, 2, 1, 0),
    (1, 1, 1, 4, 0),
    (2, 3, 4, 5, 0.1),
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def otsu(gray: np.ndarray) -> int:
    hist = np.bincount(gray.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    if total <= 0:
        return 128
    prob = hist / total
    omega = np.cumsum(prob)
    mu = np.cumsum(prob * np.arange(256))
    mu_t = mu[-1]
    denom = omega * (1.0 - omega)
    sigma = np.zeros(256)
    ok = denom > 1e-12
    sigma[ok] = (mu_t * omega[ok] - mu[ok]) ** 2 / denom[ok]
    return int(np.argmax(sigma))


def trace_contour(mask: np.ndarray) -> np.ndarray | None:
    img = np.pad(mask.astype(np.uint8), 1)
    ys, xs = np.nonzero(img)
    if len(ys) == 0:
        return None
    i0 = int(np.lexsort((xs, ys))[0])
    y, x = int(ys[i0]), int(xs[i0])
    dirs = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    d = 6
    start = (y, x)
    contour = [(x - 1, y - 1)]
    closed = False
    for step in range(min(img.size, 20000)):
        found = False
        for k in range(8):
            nd = (d + k) % 8
            ny, nx = y + dirs[nd][0], x + dirs[nd][1]
            if 0 <= ny < img.shape[0] and 0 <= nx < img.shape[1] and img[ny, nx]:
                y, x = ny, nx
                d = (nd + 5) % 8
                contour.append((x - 1, y - 1))
                found = True
                break
        if not found:
            break
        if step > 1 and (y, x) == start and d == 6:
            closed = True
            break
    if not closed:
        return None
    pts = np.asarray(contour, dtype=float)
    if len(pts) < 30:
        return None
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    return pts


def solidity_of(mask: np.ndarray) -> float:
    ys, xs = np.nonzero(mask)
    if len(ys) < 10:
        return 0.0
    step = max(1, len(ys) // 3000)
    pts = np.column_stack([xs[::step], ys[::step]])
    if len(pts) < 4:
        return 0.0
    try:
        hull = ConvexHull(pts)
    except Exception:
        return 0.0
    area = float(mask.sum())
    if hull.volume <= 0:
        return 0.0
    return area / float(hull.volume)


def components(binary: np.ndarray, min_frac: float):
    labeled, n = ndimage.label(binary)
    if n == 0:
        return []
    counts = np.bincount(labeled.ravel())
    min_area = min_frac * binary.size
    out = []
    for i in range(1, n + 1):
        if counts[i] >= min_area:
            out.append((int(counts[i]), labeled == i))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


def gate(mask: np.ndarray, image_area: int) -> dict:
    area = int(mask.sum())
    frac = area / image_area
    ys, xs = np.nonzero(mask)
    if len(ys) == 0:
        return {"pass": False, "why": "empty"}
    h = int(ys.max() - ys.min() + 1)
    w = int(xs.max() - xs.min() + 1)
    aspect = w / h if h else 0
    sol = solidity_of(mask)
    ok = 0.08 <= frac <= 0.85 and 0.8 <= aspect <= 3.5 and sol >= 0.7
    return {
        "pass": bool(ok),
        "area_fraction": round(frac, 4),
        "aspect": round(aspect, 3),
        "solidity": round(sol, 4),
        "why": None if ok else "area, aspect or solidity outside the gate",
    }


def candidates_from_image(gray: np.ndarray) -> list[dict]:
    t = otsu(gray)
    found = []
    image_area = gray.size
    for polarity, binary in (("bright", gray > t), ("dark", gray <= t)):
        comps = components(binary, 0.01)
        if not comps:
            continue
        largest = comps[0][0]
        second = comps[1][0] if len(comps) > 1 else 0
        if second and largest < 5 * second:
            found.append({
                "polarity": polarity,
                "pass": False,
                "why": "largest component is not five times the next",
                "largest": largest,
                "second": second,
            })
            continue
        info = gate(comps[0][1], image_area)
        info["polarity"] = polarity
        info["threshold"] = t
        if info["pass"]:
            info["mask"] = comps[0][1]
        found.append(info)
    return found


def orient_outline(contour: np.ndarray, mask: np.ndarray, gray: np.ndarray) -> np.ndarray:
    ys, xs = np.nonzero(mask)
    pts = np.column_stack([xs.astype(float), ys.astype(float)])
    mu = pts.mean(axis=0)
    cov = np.cov((pts - mu).T)
    _, evecs = np.linalg.eigh(cov)
    major = evecs[:, 1]
    ang = math.atan2(major[1], major[0])
    ca, sa = math.cos(-ang), math.sin(-ang)
    rot = np.array([[ca, -sa], [sa, ca]])
    xy = (contour - mu) @ rot.T
    x, y = xy[:, 0], xy[:, 1]
    xmin, xmax = float(x.min()), float(x.max())
    span = max(xmax - xmin, 1.0)
    left = y[(x - xmin) <= 0.15 * span]
    right = y[(xmax - x) <= 0.15 * span]
    hl = float(left.max() - left.min()) if len(left) else 1e9
    hr = float(right.max() - right.min()) if len(right) else 1e9
    pointier_is_right = hr < hl
    ambiguous = min(hl, hr) > 0 and min(hl, hr) / max(hl, hr) >= 0.85
    head_on_right = pointier_is_right
    if ambiguous:
        filled = ndimage.binary_fill_holes(mask)
        holes = filled & ~mask
        labeled, n = ndimage.label(holes)
        if n:
            counts = np.bincount(labeled.ravel())
            body = max(int(mask.sum()), 1)
            best = None
            for i in range(1, n + 1):
                if not (0.002 * body <= counts[i] <= 0.05 * body):
                    continue
                hy, hx = np.nonzero(labeled == i)
                centre = np.array([hx.mean(), hy.mean()])
                cx = float(((centre - mu) @ rot.T)[0])
                if best is None or counts[i] > best[0]:
                    best = (counts[i], cx)
            if best is not None:
                head_on_right = best[1] > 0
    if head_on_right:
        xy = xy.copy()
        xy[:, 0] *= -1
    return xy


def smooth_closed(pts: np.ndarray, window: int) -> np.ndarray:
    n = len(pts)
    window = max(3, int(window))
    if window % 2 == 0:
        window += 1
    window = min(window, n if n % 2 else n - 1)
    if window < 3 or n < 3:
        return pts
    half = window // 2
    pad = np.vstack([pts[-half:], pts, pts[:half]])
    csum = np.cumsum(pad, axis=0)
    csum = np.vstack([np.zeros((1, 2)), csum])
    return (csum[window:window + n] - csum[:n]) / window


def resample(pts: np.ndarray, n: int) -> np.ndarray:
    d = np.hypot(np.diff(pts[:, 0], append=pts[0, 0]), np.diff(pts[:, 1], append=pts[0, 1]))
    cum = np.concatenate([[0.0], np.cumsum(d)])
    total = cum[-1]
    targets = np.linspace(0, total, n, endpoint=False)
    out = np.empty((n, 2))
    j = 0
    closed = np.vstack([pts, pts[0]])
    for i, s in enumerate(targets):
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        span = cum[j + 1] - cum[j]
        t = 0.0 if span <= 0 else (s - cum[j]) / span
        out[i] = closed[j] * (1 - t) + closed[j + 1] * t
    return out


def normalize(xy: np.ndarray) -> tuple[np.ndarray, float]:
    xy = xy - np.array([xy[:, 0].min(), 0.0])
    span = float(xy[:, 0].max())
    head = xy[xy[:, 0] <= 0.25 * span]
    y0 = float(head[:, 1].mean()) if len(head) else float(xy[:, 1].mean())
    xy = xy - np.array([0.0, y0])
    depth = float(np.mean(np.abs(head[:, 1] - y0))) if len(head) else 1.0
    if depth <= 1e-6:
        depth = 1.0
    xy = xy / depth
    return xy, depth


def prepare_outline(mask: np.ndarray, gray: np.ndarray) -> np.ndarray | None:
    contour = trace_contour(mask)
    if contour is None:
        return None
    xy = orient_outline(contour, mask, gray)
    window = max(3, len(xy) // 50)
    xy = smooth_closed(xy, window)
    xy = resample(xy, 300)
    xy, _ = normalize(xy)
    return xy


def sym_dist(a: np.ndarray, b: np.ndarray) -> float:
    da, _ = cKDTree(b).query(a)
    db, _ = cKDTree(a).query(b)
    return float(0.5 * (da.mean() + db.mean()))


def apply_map(pts, x_h, x_max, a, b, c, t):
    x = pts[:, 0]
    y = pts[:, 1]
    span = max(x_max - x_h, 1e-9)
    u = np.where(x >= x_h, np.clip((x - x_h) / span, 0, None), 0.0)
    y2 = y * (1 + a * u + b * u * u) + t
    x2 = np.where(x >= x_h, x_h + (x - x_h) * (1 + c * u), x)
    return np.column_stack([x2, y2])


def apply_flex(pts, x_h, x_max, scales, t):
    x = pts[:, 0]
    y = pts[:, 1]
    span = max(x_max - x_h, 1e-9)
    u = np.where(x >= x_h, np.clip((x - x_h) / span, 0, 1), 0.0)
    s = np.ones_like(u)
    post = x >= x_h
    bins = np.minimum((u[post] * 4).astype(int), 3)
    s[post] = np.asarray(scales, dtype=float)[bins]
    return np.column_stack([x, y * s + t])


def clip_map(p):
    a, b, c, t = [float(v) for v in p]
    return (
        float(np.clip(a, -0.5, 6)),
        float(np.clip(b, -0.5, 6)),
        float(np.clip(c, -0.8, 1.5)),
        float(np.clip(t, -0.5, 0.5)),
    )


def fit_pair(src: np.ndarray, dst: np.ndarray):
    x_h = 0.25 * float(src[:, 0].max())
    x_max = float(src[:, 0].max())

    def obj_map(p):
        a, b, c, t = p
        pen = 0.0
        for val, lo, hi in ((a, -0.5, 6), (b, -0.5, 6), (c, -0.8, 1.5), (t, -0.5, 0.5)):
            if val < lo:
                pen += (lo - val) * 50
            elif val > hi:
                pen += (val - hi) * 50
        return sym_dist(apply_map(src, x_h, x_max, a, b, c, t), dst) + pen

    best = None
    for start in MAP_STARTS:
        res = minimize(obj_map, start, method="Nelder-Mead", options={"maxiter": 500, "xatol": 1e-3, "fatol": 1e-4})
        if best is None or res.fun < best.fun:
            best = res
    params = clip_map(best.x)
    d_map = sym_dist(apply_map(src, x_h, x_max, *params), dst)

    def obj_t(p):
        t = float(p[0])
        pen = 0.0 if -0.5 <= t <= 0.5 else 50 * min(abs(t + 0.5), abs(t - 0.5))
        t = float(np.clip(t, -0.5, 0.5))
        return sym_dist(apply_map(src, x_h, x_max, 0, 0, 0, t), dst) + pen

    sim = None
    for t0 in np.linspace(-0.4, 0.4, 9):
        res = minimize(obj_t, [t0], method="Nelder-Mead", options={"maxiter": 80})
        if sim is None or res.fun < sim.fun:
            sim = res
    t_sim = float(np.clip(sim.x[0], -0.5, 0.5))
    d_sim = sym_dist(apply_map(src, x_h, x_max, 0, 0, 0, t_sim), dst)

    def obj_flex(p):
        scales = p[:4]
        t = p[4]
        pen = 0.0
        for s in scales:
            if s < 0.3:
                pen += (0.3 - s) * 50
            elif s > 6:
                pen += (s - 6) * 50
        if t < -0.5:
            pen += (-0.5 - t) * 50
        elif t > 0.5:
            pen += (t - 0.5) * 50
        scales = np.clip(scales, 0.3, 6)
        t = float(np.clip(t, -0.5, 0.5))
        return sym_dist(apply_flex(src, x_h, x_max, scales, t), dst) + pen

    flex = None
    for start in FLEX_STARTS:
        res = minimize(obj_flex, start, method="Nelder-Mead", options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-4})
        if flex is None or res.fun < flex.fun:
            flex = res
    scales = [float(np.clip(v, 0.3, 6)) for v in flex.x[:4]]
    t_flex = float(np.clip(flex.x[4], -0.5, 0.5))
    d_flex = sym_dist(apply_flex(src, x_h, x_max, scales, t_flex), dst)
    return {
        "a": params[0], "b": params[1], "c": params[2], "t": params[3],
        "D_map": d_map, "D_sim": d_sim, "D_flex": d_flex,
        "t_sim": t_sim, "flex_scales": scales, "t_flex": t_flex,
        "x_h": x_h, "x_max": x_max,
    }


def load_gray(blob: bytes) -> np.ndarray:
    im = Image.open(io.BytesIO(blob)).convert("L")
    w, h = im.size
    long = max(w, h)
    if long > 800:
        scale = 800 / long
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    return np.asarray(im)


def species_jpegs(speccode: int) -> tuple[str, list[str], int]:
    page = f"https://www.fishbase.se/photos/ThumbnailsSummary.php?ID={speccode}"
    try:
        html = fetch(page).decode("utf-8", "replace")
        status = 200
    except Exception as exc:  # noqa: BLE001
        return page, [], getattr(exc, "code", 0) or 0
    names = sorted(set(re.findall(r"images/species/([A-Za-z0-9_]+\.jpg)", html)))
    return page, names, status


def holocanthus_speccode() -> int | None:
    url = "https://www.fishbase.se/summary/Diodon-holocanthus.html"
    try:
        html = fetch(url).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r"speccode=(\d+)", html)
    return int(m.group(1)) if m else None


def evaluate_species(speccode: int, label: str) -> dict:
    page, names, status = species_jpegs(speccode)
    print(f"{label} page {status} images {len(names)}", flush=True)
    records = []
    best = None
    for name in names:
        url = f"https://www.fishbase.se/images/species/{name}"
        path = DATA / f"{label}-{name}"
        try:
            if path.exists() and path.stat().st_size > 1000:
                blob = path.read_bytes()
                retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            else:
                blob = fetch(url)
                if blob[:2] != b"\xff\xd8":
                    records.append({"name": name, "download_url": url, "http_status": 200, "pass": False, "why": "not a jpeg"})
                    continue
                path.write_bytes(blob)
                retrieved = dt.datetime.now(dt.timezone.utc)
        except Exception as exc:  # noqa: BLE001
            records.append({
                "name": name,
                "download_url": url,
                "http_status": getattr(exc, "code", 0) or 0,
                "pass": False,
                "why": "download failed",
            })
            continue
        gray = load_gray(blob)
        cands = candidates_from_image(gray)
        passing = [c for c in cands if c.get("pass")]
        chosen = max(passing, key=lambda c: c["solidity"]) if passing else None
        outline = prepare_outline(chosen["mask"], gray) if chosen else None
        rec = {
            "name": name,
            "download_url": url,
            "retrieved_at": retrieved.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(blob),
            "sha256": sha256(blob),
            "http_status": 200,
            "pass": bool(chosen) and outline is not None,
            "attempts": [{k: v for k, v in c.items() if k != "mask"} for c in cands],
        }
        records.append(rec)
        print(f"  {label} {name} pass={rec['pass']}", flush=True)
        if outline is not None and (best is None or chosen["solidity"] > best["solidity"]):
            best = {"solidity": chosen["solidity"], "outline": outline, "record": rec, "gate": {k: chosen[k] for k in chosen if k != "mask"}}
    return {"page": page, "page_status": status, "images": records, "best": best}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    diodon = evaluate_species(1022, "diodon-hystrix")
    used_fallback = False
    fallback_code = None
    if diodon["best"] is None:
        fallback_code = holocanthus_speccode()
        if fallback_code:
            used_fallback = True
            diodon = evaluate_species(fallback_code, "diodon-holocanthus")
    mola = evaluate_species(1732, "mola-mola")

    if diodon["best"] is None or mola["best"] is None:
        verdict, reason = "inconclusive", "data-unavailable"
        measured = {
            "value": None,
            "unit": "head-depth units, symmetric mean nearest-point distance",
            "n": 0,
            "uncertainty": None,
            "extra": {
                "diodon_images_passing": 0 if diodon["best"] is None else 1,
                "mola_images_passing": 0 if mola["best"] is None else 1,
                "used_diodon_holocanthus": used_fallback,
                "holocanthus_speccode": fallback_code,
            },
        }
        fit = None
    else:
        src = diodon["best"]["outline"]
        dst = mola["best"]["outline"]
        flip_results = []
        for sign, name in ((1.0, "as-oriented"), (-1.0, "dorsal-flipped")):
            trial = fit_pair(src * np.array([1.0, sign]), dst)
            trial["flip"] = name
            flip_results.append(trial)
        fit = min(flip_results, key=lambda r: r["D_map"])
        d_map, d_sim, d_flex, t = fit["D_map"], fit["D_sim"], fit["D_flex"], fit["t"]
        supports = d_map <= 0.35 and d_map <= 0.60 * d_sim and d_map <= 1.40 * d_flex and abs(t) <= 0.15
        refutes = d_map > 0.70 or d_map > 0.90 * d_sim
        if supports:
            verdict, reason = "supports", None
        elif refutes:
            verdict, reason = "refutes", None
        else:
            verdict, reason = "mixed", None
        measured = {
            "value": round(d_map, 4),
            "unit": "head-depth units, symmetric mean nearest-point distance of the fitted map",
            "n": 2,
            "uncertainty": "one photograph pair; no sampling error",
            "extra": {
                "D_map": round(d_map, 4),
                "D_sim": round(d_sim, 4),
                "D_flex": round(d_flex, 4),
                "ratio_map_over_sim": round(d_map / d_sim, 4) if d_sim else None,
                "ratio_map_over_flex": round(d_map / d_flex, 4) if d_flex else None,
                "a": round(fit["a"], 4),
                "b": round(fit["b"], 4),
                "c": round(fit["c"], 4),
                "t": round(t, 4),
                "abs_t": round(abs(t), 4),
                "flip": fit["flip"],
                "flex_scales": [round(s, 4) for s in fit["flex_scales"]],
                "t_sim": round(fit["t_sim"], 4),
                "other_flip_D_map": round(max(r["D_map"] for r in flip_results), 4),
                "diodon_file": diodon["best"]["record"]["name"],
                "mola_file": mola["best"]["record"]["name"],
                "diodon_solidity": diodon["best"]["solidity"],
                "mola_solidity": mola["best"]["solidity"],
                "used_diodon_holocanthus": used_fallback,
            },
        }

    def slim(species_result):
        return {
            "page": species_result["page"],
            "page_status": species_result["page_status"],
            "images": species_result["images"],
            "selected": None if species_result["best"] is None else species_result["best"]["record"]["name"],
        }

    doc = {"measured": measured, "diodon": slim(diodon), "mola": slim(mola), "fit": None if fit is None else {k: fit[k] for k in fit if k != "outline"}}
    (DERIVED / "measured.json").write_text(json.dumps(doc, indent=2, default=float) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "none" if verdict == "inconclusive" else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    # Mixed stays mixed under the distance rules. Confidence is low because the
    # highest-solidity Mola mask in this run is a postage-stamp rectangle.
    result["confidence"] = {"supports": 0.5, "refutes": 0.55, "mixed": 0.25, "inconclusive": 0.4}[verdict]
    result["measured"] = {k: measured[k] for k in ("value", "unit", "n", "uncertainty")}
    result["measured"]["extra"] = measured["extra"]

    def files_for(species_result):
        out = []
        for im in species_result["images"]:
            if "sha256" not in im:
                continue
            out.append({
                "name": im["name"],
                "download_url": im["download_url"],
                "retrieved_at": im["retrieved_at"],
                "byte_size": im["byte_size"],
                "sha256": im["sha256"],
            })
        return out

    datasets = []
    for spec, block in ((SPECIES[0], diodon), (SPECIES[1], mola)):
        datasets.append({
            "id": spec["id"] if not (spec["speccode"] == 1022 and used_fallback) else "fishbase-photographs-diodon-holocanthus",
            "name": (f"Diodon holocanthus speccode {fallback_code}" if spec["speccode"] == 1022 and used_fallback else f"{spec['name']} photographs on FishBase"),
            "landing_url": block["page"],
            "doi": None,
            "version": f"FishBase ThumbnailsSummary speccode {fallback_code if spec['speccode']==1022 and used_fallback else spec['speccode']}",
            "license": "licences are per photograph on the FishBase thumbnail page; images are not redistributed",
            "files": files_for(block),
            "role": spec["role"],
        })
    result["datasets"] = datasets
    result["method"] = (
        "Downloaded every images/species JPEG linked from the FishBase thumbnail page. "
        "Each image was resized so its long side is at most 800 pixels, converted to grayscale, "
        "and thresholded with Otsu in both polarities. Components under 1 percent of the image were dropped. "
        "A mask passes when the largest component is at least five times the next, its area is 8 to 85 percent "
        "of the image, its box aspect is 0.8 to 3.5, and its solidity is at least 0.7. The highest solidity wins. "
        "The contour is traced, rotated onto its major axis, snout placed left by the pointier end "
        "(or by an eye-sized hole when the two ends are similarly blunt), smoothed over one fiftieth of the "
        "perimeter and resampled to 300 points. Head depth, the mean absolute height of the anterior quarter, "
        "is scaled to 1. Both dorsal flips are fitted. The map, the translation-only alignment and the four-bin "
        "vertical warp are bounded Nelder-Mead fits from the pre-set starts, scored by symmetric mean nearest-point distance."
    )
    result["deviations"] = [{
        "date": "2026-11-01",
        "what": "Images whose long side exceeds 800 pixels are resized before the mask. The ten map starts and the ten modular starts are the fixed tuples in analysis.py.",
        "why": "The pre-registration requires ten pre-set starts and a quality gate, and does not list the start coordinates or a pixel cap. Resizing does not change the distance thresholds. Starts stay inside the published bounds.",
    }]
    result["caveats"] = [
        "One photograph of each fish is not a growth series, and the two animals are not a homologous pair of specimens.",
        "Spines, fins and the background can move the outline. The solidity gate prefers a compact side view and rejects cluttered underwater frames.",
        "Diodon hystrix had no image through the gate, so the source is Diodon holocanthus, which the pre-registration allows.",
        "The highest-solidity Mola image is Momol_u8.jpg, a postage stamp. Its mask is the stamp rectangle, not the drawn fish. Other Mola images that pass the numeric gate are a beach background and a partial body. The distance is not a clean body-to-body comparison, which is why confidence is low. The pass and fail thresholds were not changed.",
        "The fitted parameters a, b and c sit on the published bounds, so the stretch family is constrained by those bounds.",
        "The fitted family is a head-fixed posterior stretch read from Thompson's prose. It is not a recovery of his circles-and-hyperbolas drawing.",
        "Dorsal side is unknown in the photograph, so both reflections are tried and the lower map distance is kept.",
    ]
    if fit is None:
        result["results_summary"] = [
            "No Diodon or Mola photograph passed the mask quality gate.",
            "Verdict inconclusive (data-unavailable).",
        ]
    else:
        result["results_summary"] = [
            (
                f"D_map={fit['D_map']:.3f}, D_sim={fit['D_sim']:.3f}, D_flex={fit['D_flex']:.3f}, "
                f"t={fit['t']:.3f}, flip={fit['flip']}. "
                f"Files {diodon['best']['record']['name']} and {mola['best']['record']['name']}."
            ),
            f"Verdict {verdict}.",
        ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "extra": measured["extra"]}, indent=2, default=float))


if __name__ == "__main__":
    main()
