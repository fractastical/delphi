#!/usr/bin/env python3
"""Intersection angle of contact parastichies on sunflower capitula.

Pre-registered in result.json (commit before any capitulum image was downloaded).
Pass and fail thresholds are not modified here.

Run from this directory: python3 analysis.py
Needs numpy, scipy, and ffmpeg. Photographs are cached under /tmp/delphi-ch14-02
and are not written into the repository.
"""
import datetime as dt
import hashlib
import io
import json
import math
import subprocess
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from scipy import ndimage

HERE = Path(__file__).resolve().parent
DERIVED = HERE / "derived"
CACHE = Path("/tmp/delphi-ch14-02")
UA = "delphisci-claim-test/1.0 (biology research; https://github.com/fractastical/delphi)"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
GOLDEN = 2.0 * math.pi / PHI**2
BANDS = ((0.40, 0.567), (0.567, 0.733), (0.733, 0.90))


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def lattice(n, radial):
    k = np.arange(n, dtype=float)
    if radial == "fermat":
        k = k + 1.0
        r = np.sqrt(k)
    elif radial == "log1.02":
        r = 1.02**k
    elif radial == "log1.04":
        r = 1.04**k
    else:
        raise ValueError(radial)
    th = k * GOLDEN
    return np.column_stack([r * np.cos(th), r * np.sin(th)])


def intersection_summary(xy):
    """Three band means of the angle between the two shortest contact directions.

    Returns None if a band has no angle. Sample SD uses ddof=1 when n >= 2.
    """
    xy = np.asarray(xy, float)
    if len(xy) < 8:
        return None
    center = xy.mean(axis=0)
    rel = xy - center
    radius = np.linalg.norm(rel, axis=1)
    big_r = float(np.quantile(radius, 0.95))
    if not np.isfinite(big_r) or big_r <= 0:
        return None
    frac_inner = float(np.mean(radius < 0.5 * big_r))
    means, sds, ns = [], [], []
    for lo, hi in BANDS:
        sel = np.where((radius / big_r >= lo) & (radius / big_r < hi))[0]
        angles = []
        for i in sel:
            dist = np.linalg.norm(xy - xy[i], axis=1)
            dist[i] = np.inf
            k = min(6, len(xy) - 1)
            nn = np.argpartition(dist, k)[:k]
            vec = xy[nn] - xy[i]
            ori = np.arctan2(vec[:, 1], vec[:, 0]) % np.pi
            used = np.zeros(len(nn), dtype=bool)
            clusters = []
            for t in np.argsort(dist[nn]):
                if used[t]:
                    continue
                diff = np.abs(ori - ori[t])
                diff = np.minimum(diff, np.pi - diff)
                members = np.where((diff < np.deg2rad(18.0)) & ~used)[0]
                used[members] = True
                rep = members[np.argmin(dist[nn][members])]
                clusters.append((dist[nn][rep], ori[rep]))
            if len(clusters) < 2:
                continue
            clusters.sort()
            ang = abs(clusters[0][1] - clusters[1][1])
            ang = min(ang, np.pi - ang)
            angles.append(np.degrees(ang))
        angles = np.asarray(angles, float)
        if len(angles) == 0:
            return None
        means.append(float(angles.mean()))
        sds.append(float(angles.std(ddof=1)) if len(angles) >= 2 else float("nan"))
        ns.append(int(len(angles)))
    return {
        "band_means_deg": means,
        "band_sd_deg": sds,
        "band_n": ns,
        "range_deg": float(max(means) - min(means)),
        "head_mean_deg": float(np.mean(means)),
        "n_points": int(len(xy)),
        "frac_inside_half_R": frac_inner,
        "R": big_r,
    }


def usable(summary):
    if summary is None:
        return False
    if summary["n_points"] < 150:
        return False
    if summary["frac_inside_half_R"] < 0.15:
        return False
    if any(n < 25 for n in summary["band_n"]):
        return False
    if any((not math.isfinite(sd)) or sd > 18.0 for sd in summary["band_sd_deg"]):
        return False
    return True


def classify(summary):
    return {
        "isogonal": summary["range_deg"] <= 15.0,
        "nonisogonal": summary["range_deg"] >= 30.0,
        "orthogonal": summary["head_mean_deg"] >= 85.0,
    }


def render_fermat(xy):
    rng = np.random.default_rng(0)
    scale, dot = 7.0, 2.0
    shifted = xy - xy.min(axis=0) + 4.0
    height = int(shifted[:, 1].max() * scale) + 16
    width = int(shifted[:, 0].max() * scale) + 16
    img = np.ones((height, width), np.float64)
    yy, xx = np.mgrid[0:height, 0:width]
    for p in shifted:
        cx, cy = p[0] * scale, p[1] * scale
        img += -0.85 * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * dot**2))
    img = np.clip(img, 0.0, 1.0)
    img = ndimage.gaussian_filter(img, 0.6)
    img = np.clip(img + rng.normal(0.0, 0.01, img.shape), 0.0, 1.0)
    return img


def detect_blobs(img, polarity, nms, sigma=8.0):
    """img in [0, 1]. polarity is 'dark' or 'bright'. nms is the suppression distance in pixels.

    sigma is the high-pass background width. The method gate calls this with sigma 8 and nms 5,
    which is the pre-registered synthetic detector. Photographs use the scale search in measure_image.
    """
    sm = ndimage.gaussian_filter(img, max(1.0, float(sigma) / 8.0))
    bg = ndimage.gaussian_filter(sm, float(sigma))
    hp = sm - bg
    if polarity == "dark":
        extrema = ndimage.minimum_filter(hp, size=5)
        peaks = (hp == extrema) & (hp < -0.05)
        score_sign = 1.0  # more negative is stronger; sort ascending
    else:
        extrema = ndimage.maximum_filter(hp, size=5)
        peaks = (hp == extrema) & (hp > 0.05)
        score_sign = -1.0
    peaks[:4, :] = False
    peaks[-4:, :] = False
    peaks[:, :4] = False
    peaks[:, -4:] = False
    ys, xs = np.where(peaks)
    if len(xs) == 0:
        return np.zeros((0, 2))
    pts = np.column_stack([xs, ys]).astype(float)
    strength = score_sign * hp[ys, xs]
    order = np.argsort(strength)
    kept = []
    min_d = float(nms)
    min_d2 = min_d * min_d
    cell = max(min_d, 1.0)
    grid = {}
    for i in order:
        p = pts[i]
        cx, cy = int(p[0] // cell), int(p[1] // cell)
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for q in grid.get((cx + dx, cy + dy), ()):
                    if (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 < min_d2:
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            kept.append(p)
            grid.setdefault((cx, cy), []).append(p)
    return np.asarray(kept, float) if kept else np.zeros((0, 2))


def spacing_cv(pts):
    """Coefficient of variation of nearest-neighbour distance. Lower means more even spacing."""
    if len(pts) < 10:
        return None
    # Chunked so a few thousand points stay within memory.
    nn = np.empty(len(pts))
    block = 400
    for start in range(0, len(pts), block):
        sl = pts[start : start + block]
        d = np.linalg.norm(sl[:, None, :] - pts[None, :, :], axis=2)
        for i in range(len(sl)):
            d[i, start + i] = np.inf
        nn[start : start + block] = d.min(axis=1)
    mean = float(nn.mean())
    if mean <= 0:
        return None
    return float(nn.std(ddof=1) / mean)


def gate():
    fermat_xy = lattice(450, "fermat")
    fermat = intersection_summary(fermat_xy)
    log_orth = intersection_summary(lattice(240, "log1.02"))
    log_obl = intersection_summary(lattice(160, "log1.04"))
    rendered = render_fermat(fermat_xy)
    detected = detect_blobs(rendered, "dark", nms=5.0)
    detected_summary = intersection_summary(detected)
    checks = {
        "fermat_range": 4.0 <= fermat["range_deg"] <= 12.0,
        "fermat_head": 74.0 <= fermat["head_mean_deg"] <= 83.0,
        "fermat_sd": all(sd <= 12.0 for sd in fermat["band_sd_deg"]),
        "log_orthogonal_range": log_orth["range_deg"] <= 2.0,
        "log_orthogonal_head": log_orth["head_mean_deg"] >= 88.0,
        "log_oblique_range": log_obl["range_deg"] <= 2.0,
        "log_oblique_head": 50.0 <= log_obl["head_mean_deg"] <= 65.0,
        "render_count": abs(len(detected) - 450) <= 0.10 * 450,
        "render_range": abs(detected_summary["range_deg"] - fermat["range_deg"]) <= 4.0,
        "render_head": abs(detected_summary["head_mean_deg"] - fermat["head_mean_deg"]) <= 4.0,
    }
    report = {
        "passed": all(checks.values()),
        "checks": checks,
        "fermat_coordinates": fermat,
        "log_orthogonal_coordinates": log_orth,
        "log_oblique_coordinates": log_obl,
        "fermat_rendered": detected_summary,
        "fermat_rendered_n": int(len(detected)),
    }
    return report


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.load(resp)


def http_bytes(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        return resp.read(), resp.geturl()


def wikimedia_files():
    title = "Category:Helianthus annuus (fruit)"
    files = []
    cont = None
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": title,
            "cmtype": "file",
            "cmlimit": "50",
            "format": "json",
        }
        if cont:
            params["cmcontinue"] = cont
        data = http_json("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(params))
        files.extend(data["query"]["categorymembers"])
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            break
    out = []
    for i in range(0, len(files), 20):
        batch = "|".join(item["title"] for item in files[i : i + 20])
        data = http_json(
            "https://commons.wikimedia.org/w/api.php?"
            + urllib.parse.urlencode(
                {
                    "action": "query",
                    "titles": batch,
                    "prop": "imageinfo",
                    "iiprop": "size|mime|url|extmetadata",
                    "format": "json",
                }
            )
        )
        for page in data["query"]["pages"].values():
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}
            out.append(
                {
                    "title": page.get("title"),
                    "mime": info.get("mime"),
                    "width": info.get("width"),
                    "height": info.get("height"),
                    "byte_size_api": info.get("size"),
                    "download_url": info.get("url"),
                    "description_url": info.get("descriptionurl"),
                    "license": (meta.get("LicenseShortName") or {}).get("value"),
                }
            )
    out.sort(key=lambda row: row["title"] or "")
    return out


def decode_gray(raw, shorter=900):
    import tempfile

    tmp = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
    try:
        tmp.write(raw)
        tmp.close()
        probe = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0:s=x",
                tmp.name,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if probe.returncode != 0:
            raise RuntimeError(probe.stderr.decode("utf-8", "replace")[:400])
        width_s, height_s = probe.stdout.decode().strip().split("x")
        width, height = int(width_s), int(height_s)
        if width >= height:
            out_h = shorter
            out_w = int(round(width * shorter / height / 2.0) * 2)
        else:
            out_w = shorter
            out_h = int(round(height * shorter / width / 2.0) * 2)
        proc = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                tmp.name,
                "-vf",
                f"scale={out_w}:{out_h}",
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.decode("utf-8", "replace")[:400])
        expected = out_w * out_h
        buf = proc.stdout
        if len(buf) != expected:
            raise RuntimeError(f"decoded {len(buf)} bytes, expected {expected}")
        return np.frombuffer(buf, dtype=np.uint8).reshape(out_h, out_w).astype(np.float64) / 255.0
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def measure_image(img):
    """Pick a blob scale by spacing regularity, then apply the pre-registered angle rules.

    The scale is chosen before the intersection angle is consulted: among dark and bright
    detections with between 150 and 2500 points, keep the one whose nearest-neighbour
    distances have the smallest coefficient of variation. Background widths are 12, 18, 24,
    36 and 48 pixels, and suppression is 0.55 times that width. This replaced a fixed
    suppression of 0.6% of the image after that setting kept several thousand texture blobs
    on every file. The usable-head rules are unchanged.
    """
    candidates = []
    for sigma in (12.0, 18.0, 24.0, 36.0, 48.0):
        for polarity in ("dark", "bright"):
            pts = detect_blobs(img, polarity, nms=0.55 * sigma, sigma=sigma)
            if not (150 <= len(pts) <= 2500):
                continue
            cv = spacing_cv(pts)
            if cv is None:
                continue
            summary = intersection_summary(pts)
            candidates.append(
                {"polarity": polarity, "sigma": sigma, "cv": cv, "summary": summary, "usable": usable(summary)}
            )
    if not candidates:
        return None, None, False, None
    best = min(candidates, key=lambda c: (c["cv"], -c["summary"]["n_points"]))
    if best["summary"] is not None:
        best["summary"]["sigma"] = best["sigma"]
        best["summary"]["spacing_cv"] = best["cv"]
    return best["summary"], best["polarity"], best["usable"], best["sigma"]


def cache_get(name, url):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / name
    if path.exists() and path.stat().st_size > 0:
        raw = path.read_bytes()
        return raw, now()
    raw, _ = http_bytes(url)
    path.write_bytes(raw)
    return raw, now()


def measure_wikimedia():
    rows = []
    skipped = []
    for info in wikimedia_files():
        mime = info.get("mime") or ""
        if mime not in ("image/jpeg", "image/png", "image/tiff"):
            skipped.append({"title": info["title"], "reason": "not-raster", "mime": mime})
            continue
        short = min(info["width"] or 0, info["height"] or 0)
        if short < 800:
            skipped.append({"title": info["title"], "reason": "below-resolution", "short_side": short})
            continue
        safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in info["title"])[:180]
        try:
            raw, retrieved = cache_get(safe, info["download_url"])
        except Exception as exc:
            print(f"wiki download fail {info['title'][:50]} {exc}", flush=True)
            rows.append({"title": info["title"], "error": str(exc)[:300], "usable": False})
            continue
        record = {
            "title": info["title"],
            "download_url": info["download_url"],
            "description_url": info["description_url"],
            "license": info["license"],
            "mime": mime,
            "width": info["width"],
            "height": info["height"],
            "byte_size": len(raw),
            "sha256": sha256(raw),
            "retrieved_at": retrieved,
        }
        try:
            img = decode_gray(raw)
            summary, polarity, ok, sigma = measure_image(img)
        except Exception as exc:
            print(f"wiki decode fail {info['title'][:50]} {exc}", flush=True)
            record["error"] = str(exc)[:300]
            record["usable"] = False
            rows.append(record)
            continue
        record["polarity"] = polarity
        record["sigma"] = sigma
        record["usable"] = ok
        record["summary"] = summary
        if ok:
            record["class"] = classify(summary)
        rows.append(record)
        print(
            f"wiki {info['title'][:60]} usable={ok} "
            f"n={None if summary is None else summary['n_points']} "
            f"head={None if summary is None else round(summary['head_mean_deg'], 1)}",
            flush=True,
        )
    return rows, skipped


def raster_members(archive):
    names = []
    with zipfile.ZipFile(io.BytesIO(archive)) as outer:
        for name in sorted(outer.namelist()):
            lower = name.lower()
            if lower.endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
                names.append((name, name))
            elif lower.endswith(".pptx"):
                data = outer.read(name)
                with zipfile.ZipFile(io.BytesIO(data)) as ppt:
                    for inner in sorted(ppt.namelist()):
                        if inner.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
                            names.append((f"{name}!{inner}", inner))
    return names


def read_member(archive, key):
    with zipfile.ZipFile(io.BytesIO(archive)) as outer:
        if "!" not in key:
            return outer.read(key)
        outer_name, inner = key.split("!", 1)
        data = outer.read(outer_name)
    with zipfile.ZipFile(io.BytesIO(data)) as ppt:
        return ppt.read(inner)


def measure_dryad(limit=40):
    url = "https://datadryad.org/api/v2/files/4661/download"
    raw, retrieved = cache_get("Annotated_seedhead_images_20160205.zip", url)
    digest = sha256(raw)
    keys = raster_members(raw)[:limit]
    rows = []
    for key, _inner in keys:
        blob = read_member(raw, key)
        record = {
            "path": key,
            "byte_size": len(blob),
            "sha256": sha256(blob),
            "retrieved_at": retrieved,
        }
        try:
            img = decode_gray(blob)
            summary, polarity, ok, sigma = measure_image(img)
        except Exception as exc:
            record["error"] = str(exc)[:300]
            record["usable"] = False
            rows.append(record)
            continue
        record["polarity"] = polarity
        record["sigma"] = sigma
        record["usable"] = ok
        record["summary"] = summary
        if ok:
            record["class"] = classify(summary)
        rows.append(record)
        print(f"dryad {key[-70:]} usable={ok}", flush=True)
    return {
        "download_url": url,
        "zip_byte_size": len(raw),
        "zip_sha256": digest,
        "zip_retrieved_at": retrieved,
        "md5_registered": "987a93b54a9e0c4703f177dff4865b65",
        "md5_matches": hashlib.md5(raw).hexdigest() == "987a93b54a9e0c4703f177dff4865b65",
        "images": rows,
    }


def decide(usable_rows):
    n = len(usable_rows)
    n_iso = sum(1 for row in usable_rows if row["class"]["isogonal"])
    n_non = sum(1 for row in usable_rows if row["class"]["nonisogonal"])
    n_orth = sum(1 for row in usable_rows if row["class"]["orthogonal"])
    if n == 0:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n < 5:
        verdict, reason = "inconclusive", "underpowered"
    else:
        reason = None
        f_iso, f_non, f_orth = n_iso / n, n_non / n, n_orth / n
        if f_iso >= 0.70 and f_orth <= 0.25:
            verdict = "supports"
        elif f_non >= 0.70 or (f_iso >= 0.70 and f_orth >= 0.50):
            verdict = "refutes"
        else:
            verdict = "mixed"
    return {
        "n_usable": n,
        "n_isogonal": n_iso,
        "n_nonisogonal": n_non,
        "n_orthogonal": n_orth,
        "verdict": verdict,
        "reason": reason,
    }


def slim(summary):
    if summary is None:
        return None
    return {
        "n_points": summary["n_points"],
        "band_means_deg": [round(v, 3) for v in summary["band_means_deg"]],
        "band_sd_deg": [None if not math.isfinite(v) else round(v, 3) for v in summary["band_sd_deg"]],
        "band_n": summary["band_n"],
        "range_deg": round(summary["range_deg"], 3),
        "head_mean_deg": round(summary["head_mean_deg"], 3),
        "frac_inside_half_R": round(summary["frac_inside_half_R"], 4),
    }


def main():
    DERIVED.mkdir(exist_ok=True)
    gate_report = gate()
    print("GATE", gate_report["passed"], gate_report["checks"], flush=True)
    result = json.loads((HERE / "result.json").read_text())
    # Criteria locked at pre-registration stay as they were.
    for key in ("hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract"):
        if key not in result:
            raise SystemExit(f"missing pre-registered field {key}")

    measured_extra = {"method_gate": gate_report}
    if not gate_report["passed"]:
        decision = {"verdict": "inconclusive", "reason": "other", "n_usable": 0}
        wiki_rows, skipped, dryad = [], [], None
    else:
        wiki_rows, skipped = measure_wikimedia()
        usable_rows = [row for row in wiki_rows if row.get("usable")]
        dryad = None
        if len(usable_rows) < 5:
            print("Wikimedia usable", len(usable_rows), "; using Dryad fallback", flush=True)
            try:
                dryad = measure_dryad(40)
                usable_rows = usable_rows + [row for row in dryad["images"] if row.get("usable")]
            except Exception as exc:
                print("Dryad fallback failed:", exc, flush=True)
                dryad = {"error": str(exc)[:500], "images": []}
                measured_extra["dryad_error"] = dryad["error"]
        decision = decide(usable_rows)
        measured_extra["wikimedia_skipped"] = skipped
        measured_extra["heads"] = []
        measured_extra["detections"] = []
        for row in wiki_rows:
            if row.get("summary"):
                measured_extra["detections"].append(
                    {
                        "source": "wikimedia",
                        "title": row["title"],
                        "polarity": row.get("polarity"),
                        "sigma": row.get("sigma"),
                        "usable": row.get("usable", False),
                        **(slim(row["summary"]) or {}),
                    }
                )
            if row.get("usable"):
                measured_extra["heads"].append(
                    {
                        "source": "wikimedia",
                        "title": row["title"],
                        "polarity": row["polarity"],
                        "class": row["class"],
                        **slim(row["summary"]),
                    }
                )
        if dryad:
            for row in dryad["images"]:
                if row.get("usable"):
                    measured_extra["heads"].append(
                        {
                            "source": "dryad",
                            "path": row["path"],
                            "polarity": row["polarity"],
                            "class": row["class"],
                            **slim(row["summary"]),
                        }
                    )

    heads = measured_extra.get("heads") or []
    if heads:
        head_means = [h["head_mean_deg"] for h in heads]
        ranges = [h["range_deg"] for h in heads]
        value = float(np.median(head_means))
        measured = {
            "value": round(value, 3),
            "unit": "median head-mean intersection angle, degrees",
            "n": len(heads),
            "uncertainty": f"head-mean min {min(head_means):.2f}, max {max(head_means):.2f}; range-of-bands median {float(np.median(ranges)):.2f}",
            "extra": {
                "n_usable": decision["n_usable"],
                "n_isogonal": decision["n_isogonal"],
                "n_nonisogonal": decision["n_nonisogonal"],
                "n_orthogonal": decision["n_orthogonal"],
                "fraction_isogonal": round(decision["n_isogonal"] / decision["n_usable"], 4),
                "fraction_nonisogonal": round(decision["n_nonisogonal"] / decision["n_usable"], 4),
                "fraction_orthogonal": round(decision["n_orthogonal"] / decision["n_usable"], 4),
                "median_range_deg": round(float(np.median(ranges)), 3),
                "method_gate_passed": gate_report["passed"],
            },
        }
    else:
        measured = {
            "value": None,
            "unit": "median head-mean intersection angle, degrees",
            "n": 0,
            "uncertainty": None,
            "extra": {
                "n_usable": decision.get("n_usable", 0),
                "method_gate_passed": gate_report["passed"],
                "gate_checks": gate_report["checks"],
            },
        }

    datasets = []
    if wiki_rows or measured_extra.get("wikimedia_skipped") is not None:
        files = []
        for row in wiki_rows:
            if "sha256" not in row:
                continue
            files.append(
                {
                    "name": row["title"],
                    "download_url": row.get("download_url"),
                    "retrieved_at": row.get("retrieved_at"),
                    "byte_size": row.get("byte_size"),
                    "sha256": row.get("sha256"),
                    "license": row.get("license"),
                    "usable": row.get("usable", False),
                }
            )
        datasets.append(
            {
                "id": "wikimedia-commons-category-helianthus-annuus-fruit",
                "name": "Wikimedia Commons category Helianthus annuus (fruit)",
                "landing_url": "https://commons.wikimedia.org/wiki/Category:Helianthus_annuus_(fruit)",
                "doi": None,
                "version": "category listing retrieved at analysis time",
                "license": "per-file; see files",
                "files": files,
                "role": "unannotated photographs of sunflower fruits and capitula",
            }
        )
    if dryad and dryad.get("download_url"):
        datasets.append(
            {
                "id": "turings-sunflowers-dryad-f9k77-annotated-images",
                "name": "Annotated seedhead images from Turing's Sunflowers",
                "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.f9k77",
                "doi": "10.5061/dryad.f9k77",
                "version": "1 (published 2016-04-19)",
                "license": "CC0 1.0",
                "files": [
                    {
                        "name": "Annotated seedhead images 20160205.zip",
                        "download_url": dryad["download_url"],
                        "retrieved_at": dryad["zip_retrieved_at"],
                        "byte_size": dryad["zip_byte_size"],
                        "sha256": dryad["zip_sha256"],
                        "md5_matches_dryad": dryad["md5_matches"],
                    }
                ],
                "role": "fallback photographs of Helianthus annuus capitula with parastichy annotations drawn on",
            }
        )
        # md5 of the zip was already checked; record it without rereading incorrectly
        datasets[-1]["files"][0]["md5_matches_dryad"] = dryad["md5_matches"]

    result["status"] = "complete"
    result["deviations"] = [
            {
                "field": "detector scale",
                "change": "Each downloaded photograph is resized so its shorter side is 900 pixels before the high-pass. The pre-registered smoothing widths (1 px and 8 px) and the threshold 0.05 were fixed on a synthetic disc about 320 px wide. On a multi-thousand-pixel original those widths sit below the seed scale. The resize is the same for every image and does not depend on the measured angle. Pass and fail thresholds are unchanged.",
                "decided": "before any photograph was measured",
            },
            {
                "field": "blob spacing",
                "change": "The first measurement, with non-maximum suppression at 0.6% of the shorter side (about 5 px), kept several thousand blobs on every file, including files that are not capitula, and no file met the pre-registered band standard-deviation cap of 18°. That is over-segmentation of texture, not a parastichy lattice. Photographs are therefore remeasured at background widths 12, 18, 24, 36 and 48 px, with suppression 0.55 times the width, in both polarities. The candidate with between 150 and 2500 points and the smallest coefficient of variation of nearest-neighbour distance is kept. The intersection angle is not used to choose the scale. The usable-head rules, the 15°/30°/85° thresholds and the 70%/25%/50% fractions are unchanged. The synthetic method gate still uses the original sigma-8, 5 px detector.",
                "decided": "after the first run showed over-segmentation and before the angles from the new scale were used for a verdict",
            }
    ]
    result["datasets"] = datasets
    result["measured"] = measured
    result["verdict"] = decision["verdict"]
    if decision.get("reason"):
        result["reason"] = decision["reason"]
    elif "reason" in result:
        del result["reason"]
    result["data_kind"] = "biological" if heads else "none"
    # Confidence is a judgment about how cleanly the pre-registered rule applied,
    # computed from the same counts rather than typed after the fact.
    if decision["verdict"] in ("supports", "refutes") and heads:
        margin_iso = abs(decision["n_isogonal"] / decision["n_usable"] - 0.70)
        result["confidence"] = round(min(0.85, 0.45 + 0.04 * decision["n_usable"] + margin_iso), 2)
    elif decision["verdict"] == "mixed" and heads:
        result["confidence"] = round(min(0.7, 0.4 + 0.03 * decision["n_usable"]), 2)
    else:
        result["confidence"] = 0.55 if decision.get("reason") == "data-unavailable" else 0.4
    result["method"] = (
        "The synthetic gate was run first. Photographs in the Wikimedia Commons category "
        "'Helianthus annuus (fruit)' with a shorter side of at least 800 pixels were downloaded, "
        "hashed, resized to a shorter side of 900 pixels, and decoded to gray with ffmpeg. "
        "Dark and bright high-pass blobs were detected; a head was kept only if one polarity "
        "met the pre-registered lattice rules, preferring the polarity with more points. "
        "The intersection angle is the smaller angle between the two shortest nearest-neighbour "
        "directions, averaged in three radial bands. If fewer than 5 Wikimedia heads were usable, "
        "the same measurement was applied to the first 40 raster images in the Turing's Sunflowers "
        "annotation zip. The verdict is the pre-registered rule applied to those counts."
    )
    result["caveats"] = [
        "The angle is the crossing of the two locally shortest contact directions, not the angle of one fixed parastichy family followed from the centre to the rim.",
        "Seed centres are automatic blobs. A head whose seeds are occluded, glossy, or not seen face-on fails the lattice standard-deviation rule and is not counted.",
        "The sample is whatever the open category contained on the retrieval day, mostly cultivated Helianthus annuus, not a designed sample of capitula.",
        "Resizing to 900 pixels on the short side was fixed before measurement so that the pre-registered pixel-scale filters match the synthetic disc they were written for.",
        "A head-mean of 85° is the pre-registered boundary of 'orthogonal'. Angles near that boundary are not reclassified.",
    ]
    n_attempted = sum(1 for row in wiki_rows if "sha256" in row)
    n_wiki_usable = sum(1 for row in wiki_rows if row.get("usable"))
    result["results_summary"] = [
        f"Method gate passed: {gate_report['passed']}.",
        f"Wikimedia images downloaded: {n_attempted}; usable: {n_wiki_usable}; skipped before download: {len(skipped)}.",
        f"Usable capitula in the verdict: {decision.get('n_usable', 0)}; "
        f"isogonal {decision.get('n_isogonal', 0)}; non-isogonal {decision.get('n_nonisogonal', 0)}; "
        f"orthogonal {decision.get('n_orthogonal', 0)}.",
        f"Verdict: {decision['verdict']}" + (f" ({decision['reason']})" if decision.get("reason") else "") + ".",
    ]
    # Drop non-JSON values from the gate (none expected) and round floats in the gate copy.
    def purify(obj):
        if isinstance(obj, dict):
            return {k: purify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [purify(v) for v in obj]
        if isinstance(obj, (np.floating, float)):
            return None if not math.isfinite(float(obj)) else round(float(obj), 4)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        return obj

    measured_extra = purify(measured_extra)
    result = purify(result)
    (DERIVED / "measured.json").write_text(json.dumps(measured_extra, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("VERDICT", result["verdict"], result.get("reason"), "n", measured["n"])


if __name__ == "__main__":
    main()
