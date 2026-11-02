#!/usr/bin/env python3
"""thompson1917-ch14-02: are sunflower parastichies isogonal, and rarely orthogonal?

Reads reviewer-drawn freeform strokes from the Turing's Sunflowers PowerPoint
archive (Dryad doi:10.5061/dryad.f9k77, file 4661). Thresholds are those
committed in result.json before the zip was opened.

Requires: numpy. Run from this directory: python3 analysis.py
The zip is fetched into data/ if missing. Dryad fronts downloads with an Anubis
proof-of-work page; if a direct GET does not return a zip, place the file at
data/annotated-seedheads.zip (the script checks size and md5).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import math
import re
import statistics
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import urllib.request

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
ZIP_NAME = "annotated-seedheads.zip"
ZIP_URL = "https://datadryad.org/downloads/file_stream/4661"
EXPECTED_MD5 = "987a93b54a9e0c4703f177dff4865b65"
EXPECTED_SIZE = 314590945

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

# Procedure constants stated in planned_method. Not the pass/fail thresholds.
SMOOTH_WINDOW = 5
CHORD_FRACTION = 0.05
CROSS_FRACTION = 0.03
SAMPLE_FRACTION = 0.008
MIN_LENGTH_FRACTION = 0.15
MIN_WIND_SIN = 0.15
MIN_CROSSINGS = 6
MIN_HEADS = 40


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def obtain_zip() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / ZIP_NAME
    if not path.exists() or path.stat().st_size != EXPECTED_SIZE:
        try:
            req = urllib.request.Request(ZIP_URL, headers={"User-Agent": "delphisci-claim-test"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                blob = resp.read(64)
                rest = resp.read()
            blob = blob + rest
            if blob[:2] == b"PK" and len(blob) == EXPECTED_SIZE:
                path.write_bytes(blob)
        except Exception as exc:  # noqa: BLE001
            print(f"direct download did not yield the zip: {exc}", file=sys.stderr)
    if not path.exists():
        sys.exit(
            f"{ZIP_NAME} is not in {DATA}. Dryad file 4661 is behind a browser "
            f"challenge at {ZIP_URL}."
        )
    digest_md5 = md5_file(path)
    digest = sha256_file(path)
    if digest_md5 != EXPECTED_MD5 or path.stat().st_size != EXPECTED_SIZE:
        sys.exit(
            f"checksum or size mismatch: size={path.stat().st_size} md5={digest_md5} "
            f"expected size={EXPECTED_SIZE} md5={EXPECTED_MD5}"
        )
    retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return {
        "download_url": ZIP_URL,
        "retrieved_at": retrieved,
        "byte_size": path.stat().st_size,
        "sha256": digest,
        "md5": digest_md5,
    }


def _xfrm_parts(xfrm):
    off = ext = ch_off = ch_ext = None
    for c in xfrm:
        if c.tag == A + "off":
            off = c
        elif c.tag == A + "ext":
            ext = c
        elif c.tag == A + "chOff":
            ch_off = c
        elif c.tag == A + "chExt":
            ch_ext = c
    return off, ext, ch_off, ch_ext


def _apply_group(x, y, xfrm):
    off, ext, ch_off, ch_ext = _xfrm_parts(xfrm)
    if off is None or ext is None or ch_off is None or ch_ext is None:
        return x, y
    ox, oy = float(off.get("x")), float(off.get("y"))
    cx, cy = float(ext.get("cx")), float(ext.get("cy"))
    cox, coy = float(ch_off.get("x")), float(ch_off.get("y"))
    ccx, ccy = float(ch_ext.get("cx") or 0), float(ch_ext.get("cy") or 0)
    if ccx == 0 or ccy == 0:
        return x, y
    return ox + (x - cox) * cx / ccx, oy + (y - coy) * cy / ccy


def _shape_point(px, py, ox, oy, cx, cy, w, h, flip_h, flip_v, rot):
    x = ox + px / w * cx
    y = oy + py / h * cy
    if flip_h:
        x = 2 * ox + cx - x
    if flip_v:
        y = 2 * oy + cy - y
    if rot:
        ang = math.radians(int(rot) / 60000.0)
        mx, my = ox + cx / 2.0, oy + cy / 2.0
        dx, dy = x - mx, y - my
        ca, sa = math.cos(ang), math.sin(ang)
        # DrawingML positive rotation is clockwise on the slide (y down).
        x = mx + dx * ca - dy * sa
        y = my + dx * sa + dy * ca
    return x, y


def _cubic(p0, p1, p2, p3, n=4):
    out = []
    for i in range(1, n + 1):
        t = i / n
        u = 1 - t
        x = u**3 * p0[0] + 3 * u**2 * t * p1[0] + 3 * u * t**2 * p2[0] + t**3 * p3[0]
        y = u**3 * p0[1] + 3 * u**2 * t * p1[1] + 3 * u * t**2 * p2[1] + t**3 * p3[1]
        out.append((x, y))
    return out


def parse_slide(xml: bytes):
    root = ET.fromstring(xml)
    texts = []
    for t in root.iter(A + "t"):
        if t.text and t.text.strip():
            texts.append(t.text.strip())
    title = " ".join(texts[:8])
    parent = {}
    for p in root.iter():
        for c in list(p):
            parent[c] = p

    strokes = []
    for sp in root.iter(P + "sp"):
        geom = next(sp.iter(A + "custGeom"), None)
        if geom is None:
            continue
        xfrm = next(sp.iter(A + "xfrm"), None)
        if xfrm is None:
            continue
        off, ext, _, _ = _xfrm_parts(xfrm)
        if off is None or ext is None:
            continue
        ox, oy = float(off.get("x")), float(off.get("y"))
        cx, cy = float(ext.get("cx") or 0), float(ext.get("cy") or 0)
        if cx <= 0 or cy <= 0:
            continue
        flip_h = xfrm.get("flipH") == "1"
        flip_v = xfrm.get("flipV") == "1"
        rot = xfrm.get("rot")
        groups = []
        node = parent.get(sp)
        while node is not None:
            if node.tag == P + "grpSp":
                for ch in node:
                    if ch.tag == P + "grpSpPr":
                        gxf = next((c for c in ch if c.tag == A + "xfrm"), None)
                        if gxf is not None:
                            groups.append(gxf)
            node = parent.get(node)
        for path in geom.iter(A + "path"):
            w = float(path.get("w") or 0)
            h = float(path.get("h") or 0)
            if w <= 0 or h <= 0:
                continue
            sub = []
            current = None

            def emit(pt):
                x, y = _shape_point(pt[0], pt[1], ox, oy, cx, cy, w, h, flip_h, flip_v, rot)
                for gxf in groups:
                    x, y = _apply_group(x, y, gxf)
                return (x, y)

            for child in list(path):
                tag = child.tag.split("}")[-1]
                pts = [
                    (float(c.get("x")), float(c.get("y")))
                    for c in child
                    if c.tag == A + "pt"
                ]
                if tag == "moveTo" and pts:
                    if len(sub) >= 2:
                        strokes.append(sub)
                    sub = [emit(pts[0])]
                    current = pts[0]
                elif tag == "lnTo" and pts:
                    sub.append(emit(pts[0]))
                    current = pts[0]
                elif tag == "cubicBezTo" and len(pts) == 3 and current is not None:
                    for q in _cubic(current, pts[0], pts[1], pts[2]):
                        sub.append(emit(q))
                    current = pts[2]
            if len(sub) >= 2:
                strokes.append(sub)
    return title, strokes


def arc_length(pts: np.ndarray) -> float:
    if len(pts) < 2:
        return 0.0
    d = np.diff(pts, axis=0)
    return float(np.hypot(d[:, 0], d[:, 1]).sum())


def smooth(pts: np.ndarray, window: int) -> np.ndarray:
    n = len(pts)
    if n < 3 or window < 3:
        return pts
    w = min(window, n if n % 2 == 1 else n - 1)
    if w < 3:
        return pts
    half = w // 2
    out = np.empty_like(pts)
    for i in range(n):
        a = max(0, i - half)
        b = min(n, i + half + 1)
        out[i] = pts[a:b].mean(axis=0)
    return out


def resample(pts: np.ndarray, step: float) -> np.ndarray:
    if len(pts) < 2:
        return pts
    d = np.hypot(np.diff(pts[:, 0]), np.diff(pts[:, 1]))
    cum = np.concatenate([[0.0], np.cumsum(d)])
    total = cum[-1]
    if total <= step:
        return pts[[0, -1]]
    targets = np.arange(0.0, total, step)
    if targets[-1] < total - 1e-6:
        targets = np.append(targets, total)
    out = np.empty((len(targets), 2))
    j = 0
    for i, s in enumerate(targets):
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        span = cum[j + 1] - cum[j]
        t = 0.0 if span <= 0 else (s - cum[j]) / span
        out[i] = pts[j] * (1 - t) + pts[j + 1] * t
    return out


def geometric_median(points: np.ndarray) -> np.ndarray:
    if len(points) > 4000:
        rng = np.random.default_rng(0)
        points = points[rng.choice(len(points), 4000, replace=False)]
    y = points.mean(axis=0)
    for _ in range(60):
        diff = points - y
        dist = np.hypot(diff[:, 0], diff[:, 1])
        dist = np.maximum(dist, 1e-6)
        w = 1.0 / dist
        y2 = (points * w[:, None]).sum(axis=0) / w.sum()
        if np.hypot(*(y2 - y)) <= 1e-4 * (1 + np.hypot(*y)):
            return y2
        y = y2
    return y


def wind_sign(pts: np.ndarray, center: np.ndarray):
    """Orient the stroke outward, then sign of r × dr in y-down slide coordinates.
    Positive is clockwise as the stroke radiates outward."""
    r0 = np.hypot(*(pts[0] - center))
    r1 = np.hypot(*(pts[-1] - center))
    if r1 < r0:
        pts = pts[::-1]
    rel = pts - center
    dr = np.diff(pts, axis=0)
    cross = rel[:-1, 0] * dr[:, 1] - rel[:-1, 1] * dr[:, 0]
    length = float(np.hypot(dr[:, 0], dr[:, 1]).sum())
    radius = float(np.median(np.hypot(rel[:, 0], rel[:, 1])))
    if length <= 0 or radius <= 0:
        return 0, 0.0, pts
    sin_mean = float(cross.sum() / (length * radius))
    sign = 1 if sin_mean > 0 else -1
    return sign, sin_mean, pts


def head_angles(strokes, center, radius):
    step = max(radius * SAMPLE_FRACTION, 1.0)
    prepared = []
    for raw in strokes:
        pts = np.asarray(raw, dtype=float)
        if len(pts) < 2:
            continue
        pts = smooth(pts, SMOOTH_WINDOW)
        length = arc_length(pts)
        if length < MIN_LENGTH_FRACTION * radius:
            continue
        sign, sin_mean, pts = wind_sign(pts, center)
        if abs(sin_mean) < MIN_WIND_SIN:
            continue
        samples = resample(pts, step)
        if len(samples) < 2:
            continue
        prepared.append({"sign": sign, "pts": samples, "length": length})
    cw = [s for s in prepared if s["sign"] > 0]
    ccw = [s for s in prepared if s["sign"] < 0]
    if not cw or not ccw:
        return [], len(cw), len(ccw)
    cell = CROSS_FRACTION * radius
    grid = defaultdict(list)
    for j, s in enumerate(ccw):
        for k, (x, y) in enumerate(s["pts"]):
            grid[(int(x // cell), int(y // cell))].append((j, k, x, y))
    best = {}
    for i, s in enumerate(cw):
        for k, (x, y) in enumerate(s["pts"]):
            ix, iy = int(x // cell), int(y // cell)
            for gx in (ix - 1, ix, ix + 1):
                for gy in (iy - 1, iy, iy + 1):
                    for j, kk, xb, yb in grid.get((gx, gy), ()):
                        dist = math.hypot(x - xb, y - yb)
                        if dist > cell:
                            continue
                        key = (i, j)
                        prev = best.get(key)
                        if prev is None or dist < prev[0]:
                            best[key] = (dist, k, kk)
    angles = []
    half_frac = CHORD_FRACTION / 2.0
    for (i, j), (dist, k, kk) in best.items():
        if dist > cell:
            continue
        tangents = []
        ok = True
        for stroke, idx in ((cw[i], k), (ccw[j], kk)):
            pts = stroke["pts"]
            n = len(pts)
            half = max(1, int(round(half_frac * stroke["length"] / step)))
            i0 = max(0, idx - half)
            i1 = min(n - 1, idx + half)
            if i1 == i0:
                ok = False
                break
            tangents.append(pts[i1] - pts[i0])
        if not ok:
            continue
        u, v = tangents
        nu = math.hypot(u[0], u[1])
        nv = math.hypot(v[0], v[1])
        if nu <= 0 or nv <= 0:
            continue
        cos = abs(u[0] * v[0] + u[1] * v[1]) / (nu * nv)
        cos = min(1.0, max(0.0, cos))
        angles.append(math.degrees(math.acos(cos)))
    return angles, len(cw), len(ccw)


def iqr(values):
    if len(values) < 2:
        return None
    q1, q3 = np.percentile(values, [25, 75])
    return float(q3 - q1)


def analyse_zip(path: Path):
    heads = []
    n_slides = 0
    n_with_strokes = 0
    with zipfile.ZipFile(path) as outer:
        for name in outer.namelist():
            if not name.lower().endswith(".pptx"):
                continue
            print(f"pptx {name}", flush=True)
            blob = outer.read(name)
            with zipfile.ZipFile(io.BytesIO(blob)) as deck:
                slides = [
                    n
                    for n in deck.namelist()
                    if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)
                ]
                slides.sort(key=lambda n: int(re.search(r"(\d+)", n).group(1)))
                for slide in slides:
                    n_slides += 1
                    title, strokes = parse_slide(deck.read(slide))
                    if len(strokes) < 4:
                        continue
                    n_with_strokes += 1
                    pts = np.asarray([p for s in strokes for p in s], dtype=float)
                    center = geometric_median(pts)
                    radii = np.hypot(pts[:, 0] - center[0], pts[:, 1] - center[1])
                    radius = float(np.percentile(radii, 90))
                    if radius <= 0:
                        continue
                    angles, n_cw, n_ccw = head_angles(strokes, center, radius)
                    m = re.search(r"\d+", title)
                    head_id = m.group(0) if m else f"{Path(name).stem}:{slide}"
                    heads.append(
                        {
                            "head_id": head_id,
                            "source": f"{name}#{Path(slide).stem}",
                            "title": title[:180],
                            "n_cw": n_cw,
                            "n_ccw": n_ccw,
                            "n_crossings": len(angles),
                            "median_angle": round(float(np.median(angles)), 3) if angles else None,
                            "iqr": round(iqr(angles), 3) if len(angles) >= 2 else None,
                            "angles": [round(a, 2) for a in angles],
                        }
                    )
    return {
        "n_slides": n_slides,
        "n_slides_with_strokes": n_with_strokes,
        "heads": heads,
    }


def dedupe(heads):
    chosen = {}
    order = []
    for h in heads:
        key = h["head_id"]
        prev = chosen.get(key)
        if prev is None:
            chosen[key] = h
            order.append(key)
            continue
        if h["n_crossings"] > prev["n_crossings"]:
            chosen[key] = h
    return [chosen[k] for k in order]


def decide(qualified):
    n = len(qualified)
    if n < MIN_HEADS:
        return "inconclusive", "underpowered"
    iqrs = [h["iqr"] for h in qualified]
    meds = [h["median_angle"] for h in qualified]
    med_iqr = float(np.median(iqrs))
    med_angle = float(np.median(meds))
    frac80 = float(np.mean([m >= 80.0 for m in meds]))
    if med_iqr > 35.0 or frac80 >= 0.50:
        return "refutes", None
    if med_iqr <= 20.0 and med_angle <= 75.0 and frac80 < 0.25:
        return "supports", None
    return "mixed", None


def main():
    info = obtain_zip()
    raw = analyse_zip(DATA / ZIP_NAME)
    heads = dedupe(raw["heads"])
    qualified = [h for h in heads if h["n_crossings"] >= MIN_CROSSINGS and h["iqr"] is not None]
    if raw["n_slides_with_strokes"] == 0:
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = decide(qualified)
    iqrs = [h["iqr"] for h in qualified]
    meds = [h["median_angle"] for h in qualified]
    med_iqr = float(np.median(iqrs)) if iqrs else None
    med_angle = float(np.median(meds)) if meds else None
    frac80 = float(np.mean([m >= 80.0 for m in meds])) if meds else None
    n_dup_slides = len(raw["heads"]) - len(heads)

    summary_heads = []
    for h in heads:
        summary_heads.append({k: h[k] for k in h if k != "angles"})
    measured_doc = {
        "value": None if med_iqr is None else round(med_iqr, 3),
        "unit": "degrees, median across heads of the within-head IQR of the acute crossing angle",
        "n": len(qualified),
        "uncertainty": "cross-head spread of the within-head IQRs; not a standard error",
        "extra": {
            "n_slides": raw["n_slides"],
            "n_slides_with_strokes": raw["n_slides_with_strokes"],
            "n_slide_drawings": len(raw["heads"]),
            "n_heads_after_dedupe": len(heads),
            "n_duplicate_slides_dropped": n_dup_slides,
            "n_heads_with_at_least_6_crossings": len(qualified),
            "median_within_head_iqr_deg": None if med_iqr is None else round(med_iqr, 3),
            "median_of_head_median_angle_deg": None if med_angle is None else round(med_angle, 3),
            "fraction_heads_median_at_least_80": None if frac80 is None else round(frac80, 4),
            "iqr_of_head_iqrs_deg": None if len(iqrs) < 2 else round(iqr(iqrs), 3),
            "file": info,
            "heads": summary_heads,
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured_doc, indent=2) + "\n")
    # per-head angles are the audit trail; keep them out of the summary if large
    angle_doc = {
        "heads": [
            {
                "head_id": h["head_id"],
                "source": h["source"],
                "n_crossings": h["n_crossings"],
                "median_angle": h["median_angle"],
                "iqr": h["iqr"],
                "angles": h["angles"],
            }
            for h in heads
            if h["n_crossings"]
        ]
    }
    angle_path = DERIVED / "angles.json"
    text = json.dumps(angle_doc)
    if len(text.encode()) < 180_000:
        angle_path.write_text(text)
    else:
        # keep only qualified heads
        angle_doc["heads"] = [h for h in angle_doc["heads"] if h["n_crossings"] >= MIN_CROSSINGS]
        angle_doc["note"] = "unqualified heads omitted so derived/ stays under 200 KB"
        angle_path.write_text(json.dumps(angle_doc))

    if verdict == "supports":
        conf = 0.55
    elif verdict == "refutes":
        conf = 0.62
    elif verdict == "mixed":
        conf = 0.5
    else:
        conf = 0.45

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["confidence"] = conf
    result["measured"] = {
        "value": measured_doc["value"],
        "unit": measured_doc["unit"],
        "n": measured_doc["n"],
        "uncertainty": measured_doc["uncertainty"],
        "extra": {
            "median_within_head_iqr_deg": measured_doc["extra"]["median_within_head_iqr_deg"],
            "median_of_head_median_angle_deg": measured_doc["extra"]["median_of_head_median_angle_deg"],
            "fraction_heads_median_at_least_80": measured_doc["extra"]["fraction_heads_median_at_least_80"],
            "n_heads_with_at_least_6_crossings": len(qualified),
            "n_heads_after_dedupe": len(heads),
            "n_slides_with_strokes": raw["n_slides_with_strokes"],
        },
    }
    result["datasets"] = [
        {
            "id": "swinton-ochu-2016-turings-sunflowers-dryad-f9k77",
            "name": "Turing's Sunflowers: annotated seedhead images (Swinton and Ochu)",
            "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.f9k77",
            "doi": "10.5061/dryad.f9k77",
            "version": "Dryad version id 818, file 4661, API md5 987a93b54a9e0c4703f177dff4865b65",
            "license": "CC0-1.0",
            "files": [
                {
                    "name": "Annotated seedhead images 20160205.zip",
                    "download_url": ZIP_URL,
                    "retrieved_at": info["retrieved_at"],
                    "byte_size": info["byte_size"],
                    "sha256": info["sha256"],
                    "md5": info["md5"],
                }
            ],
            "role": "reviewer freehand parastichy strokes on Helianthus annuus photographs",
        }
    ]
    result["method"] = (
        "Opened each PowerPoint slide inside Dryad file 4661 and read freeform custGeom paths "
        "(line segments and sampled cubic beziers), mapped through shape and group transforms. "
        "The disc centre is the geometric median of the stroke vertices and the disc radius is "
        "the 90th percentile of vertex distances from that centre. Strokes shorter than 15 percent "
        "of that radius are dropped. Each remaining stroke is smoothed with a 5-vertex moving average, "
        "oriented from the inner end to the outer end, and classed clockwise or anticlockwise by the "
        "sign of r cross dr. A stroke whose mean |sin| against the radius is below 0.15 is dropped. "
        "A crossing is the closest approach of one clockwise and one anticlockwise stroke when that "
        "distance is below 3 percent of the radius. The tangent is the chord spanning 5 percent of "
        "the smoothed stroke about that point. The acute angle is arccos of the absolute cosine, in "
        "(0, 90] degrees. Heads need at least 6 crossings. Slides that share a leading integer in the "
        "title are one head; the drawing with more crossings is kept."
    )
    result["deviations"] = [
        {
            "date": "2026-11-01",
            "what": (
                "Disc radius is the 90th percentile of vertex distances from the geometric median. "
                "Strokes shorter than 0.15 radii, and strokes whose tangent stays within about "
                "9 degrees of the radius (|mean sin| < 0.15), are not treated as parastichies. "
                "Slides whose title starts with the same integer are one head."
            ),
            "why": (
                "The pre-registration named the centre, the 3 percent approach, the 5-vertex smooth "
                "and the 5 percent chord, and it named heads rather than slides. It did not define "
                "the radius, a minimum stroke length, or how a repeated head number is counted. "
                "These choices do not change the 20 degree, 35 degree, 75 degree, 80 degree or 0.25 "
                "thresholds. Colours are not used: a methods slide in the same decks says colours "
                "are not significant, and the pre-registration splits families by winding."
            ),
        }
    ]
    result["caveats"] = [
        "The strokes are a reviewer's freehand lines on photographs. A smoothed line can look steadier than the seeds, which biases this test toward the claim.",
        "Clockwise is the deck's own definition: the curve goes clockwise as it radiates outward, evaluated in slide coordinates.",
        "One closest approach is kept per pair of strokes. Broken pieces of one spiral can contribute more than one approach.",
        "Parastichy counts are not turned into angles. The count workbooks in this Dryad deposit are not used.",
        "The zip md5 matches the Dryad file record 987a93b54a9e0c4703f177dff4865b65.",
    ]
    if med_iqr is None:
        result["results_summary"] = [
            f"Slides {raw['n_slides']}, with strokes {raw['n_slides_with_strokes']}, qualified heads {len(qualified)}.",
            f"Verdict {verdict}" + (f" ({reason})." if reason else "."),
        ]
    else:
        result["results_summary"] = [
            (
                f"Qualified heads {len(qualified)} of {len(heads)} after collapsing {n_dup_slides} repeat slides. "
                f"Median within-head IQR {med_iqr:.2f} degrees. "
                f"Median of head-median angles {med_angle:.2f} degrees. "
                f"Fraction of heads with median angle at least 80 degrees: {frac80:.3f}."
            ),
            f"Verdict {verdict}" + (f" ({reason})." if reason else "."),
        ]
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "verdict": verdict,
                "reason": reason,
                "n_qualified": len(qualified),
                "n_heads": len(heads),
                "med_iqr": med_iqr,
                "med_angle": med_angle,
                "frac80": frac80,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
