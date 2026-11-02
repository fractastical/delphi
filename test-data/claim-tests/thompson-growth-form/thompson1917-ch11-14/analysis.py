#!/usr/bin/env python3
"""thompson1917-ch11-14: does the spiral angle change the way Thompson says
along Oekotraustes, Scaphites, Ancyloceras and Lituites?

Searches Wikimedia Commons, then iDigBio, then MorphoSource. Thresholds are
those committed in result.json. Images stay in data/ and are not committed.

Requires: numpy, scipy, pillow. Run: python3 analysis.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import ConvexHull

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (research; github.com/fractastical/delphi)"

GENERA = {
    "Oekotraustes": "narrowing",
    "Scaphites": "uncoiling",
    "Ancyloceras": "uncoiling",
    "Lituites": "uncoiling",
}
SEARCH_TERMS = {
    "Oekotraustes": ["Oekotraustes", "Oecotraustes"],
    "Scaphites": ["Scaphites"],
    "Ancyloceras": ["Ancyloceras"],
    "Lituites": ["Lituites"],
}


def get(url: str, timeout: int = 40) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp else b""
        return exc.code, body


def sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def commons_images(term: str) -> dict:
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": f"{term} filemime:image/jpeg",
        "srnamespace": "6",
        "srlimit": "8",
        "format": "json",
    })
    status, raw = get(url)
    record = {"url": url, "http_status": status, "files": []}
    if status != 200:
        return record
    hits = json.loads(raw).get("query", {}).get("search", [])
    titles = [h["title"] for h in hits if h["title"].lower().endswith((".jpg", ".jpeg"))]
    if not titles:
        return record
    info_url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query",
        "titles": "|".join(titles),
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "format": "json",
    })
    st2, raw2 = get(info_url)
    record["imageinfo_status"] = st2
    if st2 != 200:
        return record
    pages = json.loads(raw2).get("query", {}).get("pages", {})
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        if not info.get("url"):
            continue
        if info.get("size", 0) > 8_000_000:
            continue
        if info.get("mime") not in (None, "image/jpeg"):
            continue
        record["files"].append({
            "title": page.get("title"),
            "download_url": info["url"].split("?")[0],
            "byte_size_api": info.get("size"),
            "mime": info.get("mime"),
            "source": "wikimedia-commons",
        })
    return record


def idigbio_images(genus: str) -> dict:
    url = "https://search.idigbio.org/v2/search/media"
    body = json.dumps({"rq": {"genus": genus}, "limit": 5}).encode()
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA, "Content-Type": "application/json"})
    record = {"url": url, "http_status": None, "item_count": None, "files": []}
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            record["http_status"] = resp.status
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        record["http_status"] = exc.code
        return record
    except Exception as exc:  # noqa: BLE001
        record["error"] = str(exc)
        return record
    record["item_count"] = data.get("itemCount")
    for item in data.get("items", []):
        uri = (item.get("indexTerms") or {}).get("accessuri")
        if not uri or not isinstance(uri, str):
            continue
        if not uri.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
            continue
        record["files"].append({
            "title": uri.rsplit("/", 1)[-1][:80],
            "download_url": uri,
            "source": "idigbio",
        })
    return record


def morphosource_status() -> dict:
    url = "https://www.morphosource.org/search?q=Scaphites"
    status, raw = get(url)
    text = raw[:400].decode("utf-8", "replace")
    return {
        "url": url,
        "http_status": status,
        "bot_wall": "not a bot" in text.lower() or "making sure" in text.lower(),
        "used": False,
        "note": "No login was attempted and no mesh was downloaded.",
    }


def local_name(url: str) -> str:
    return urllib.parse.unquote(url.split("?")[0].rstrip("/").rsplit("/", 1)[-1])


def obtain(spec: dict) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    name = local_name(spec["download_url"])
    path = DATA / name
    status = None
    if not path.exists() or path.stat().st_size < 1000:
        time.sleep(1.2)
        status, blob = get(spec["download_url"], timeout=60)
        if status == 200 and blob[:2] == b"\xff\xd8":
            path.write_bytes(blob)
        else:
            return {**spec, "http_status": status, "obtained": False, "why": "download did not return a jpeg"}
    blob = path.read_bytes()
    retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        **spec,
        "name": name,
        "http_status": 200 if status is None else status,
        "obtained": True,
        "retrieved_at": retrieved,
        "byte_size": len(blob),
        "sha256": sha256(blob),
        "path": str(path),
    }


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


def solidity(mask: np.ndarray) -> float:
    ys, xs = np.nonzero(mask)
    if len(ys) < 10:
        return 0.0
    step = max(1, len(ys) // 2000)
    pts = np.column_stack([xs[::step], ys[::step]])
    try:
        hull = ConvexHull(pts)
    except Exception:
        return 0.0
    return float(mask.sum() / hull.volume) if hull.volume else 0.0


def trace(mask: np.ndarray):
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
    for step in range(25000):
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
            return None
        if step > 40 and (y, x) == start:
            break
    else:
        return None
    pts = np.asarray(contour, dtype=float)
    if len(pts) < 40:
        return None
    if np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    return pts


def resample(pts: np.ndarray, n: int = 360) -> np.ndarray:
    d = np.hypot(np.diff(pts[:, 0], append=pts[0, 0]), np.diff(pts[:, 1], append=pts[0, 1]))
    cum = np.concatenate([[0.0], np.cumsum(d)])
    total = cum[-1]
    targets = np.linspace(0, total, n, endpoint=False)
    out = np.empty((n, 2))
    closed = np.vstack([pts, pts[0]])
    j = 0
    for i, s in enumerate(targets):
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        span = cum[j + 1] - cum[j]
        t = 0.0 if span <= 0 else (s - cum[j]) / span
        out[i] = closed[j] * (1 - t) + closed[j + 1] * t
    return out


def candidate_mask(gray: np.ndarray):
    t = otsu(gray)
    best = None
    notes = []
    for polarity, binary in (("dark", gray <= t), ("bright", gray > t)):
        labeled, _ = ndimage.label(binary)
        counts = np.bincount(labeled.ravel())
        for i, count in enumerate(counts):
            if i == 0 or count < 0.05 * gray.size:
                continue
            mask = labeled == i
            touches = bool(mask[0].any() or mask[-1].any() or mask[:, 0].any() or mask[:, -1].any())
            if touches:
                notes.append({"polarity": polarity, "why": "touches the image border"})
                continue
            filled = ndimage.binary_fill_holes(mask)
            ys, xs = np.nonzero(filled)
            aspect = (xs.max() - xs.min() + 1) / (ys.max() - ys.min() + 1)
            frac = float(filled.mean())
            sol = solidity(filled)
            ok = 0.05 <= frac <= 0.90 and 0.4 <= aspect <= 4 and 0.4 <= sol <= 0.95
            notes.append({
                "polarity": polarity,
                "area_fraction": round(frac, 3),
                "aspect": round(float(aspect), 3),
                "solidity": round(sol, 3),
                "pass": bool(ok),
            })
            if ok and (best is None or count > best[0]):
                best = (count, polarity, filled, {
                    "area_fraction": round(frac, 3),
                    "aspect": round(float(aspect), 3),
                    "solidity": round(sol, 3),
                    "polarity": polarity,
                })
    return best, notes


def ventral_arc(contour: np.ndarray, pole: np.ndarray):
    rel = contour - pole
    rad = np.hypot(rel[:, 0], rel[:, 1])
    theta = np.arctan2(rel[:, 1], rel[:, 0])
    bins = 180
    idx = np.floor((theta + math.pi) / (2 * math.pi) * bins).astype(int) % bins
    env = []
    for b in range(bins):
        sel = np.nonzero(idx == b)[0]
        if len(sel) == 0:
            continue
        env.append(contour[sel[np.argmax(rad[sel])]])
    if len(env) < 40:
        return None
    env = np.asarray(env)
    er = np.hypot(env[:, 0] - pole[0], env[:, 1] - pole[1])
    i_min, i_max = int(np.argmin(er)), int(np.argmax(er))

    def between(a, b):
        return env[a:b + 1] if a <= b else np.vstack([env[a:], env[:b + 1]])

    arcs = [between(i_min, i_max), between(i_max, i_min)[::-1]]

    def score(arc):
        if len(arc) < 15:
            return -9.0
        r = np.hypot(arc[:, 0] - pole[0], arc[:, 1] - pole[1])
        if np.std(r) == 0:
            return -9.0
        return float(np.corrcoef(np.arange(len(r)), r)[0, 1])

    return max(arcs, key=score)


def alpha_series(arc: np.ndarray, pole: np.ndarray) -> np.ndarray:
    n = len(arc)
    half = max(1, n // 25)
    out = np.full(n, np.nan)
    for i in range(n):
        i0, i1 = max(0, i - half), min(n - 1, i + half)
        if i1 == i0:
            continue
        tangent = arc[i1] - arc[i0]
        radius = arc[i] - pole
        nt = math.hypot(tangent[0], tangent[1])
        nr = math.hypot(radius[0], radius[1])
        if nt < 1e-8 or nr < 1e-8:
            continue
        cos = abs(float(np.dot(tangent, radius))) / (nt * nr)
        out[i] = math.degrees(math.acos(min(1.0, cos)))
    return out


def measure(path: Path) -> dict:
    im = Image.open(path).convert("L")
    if max(im.size) > 700:
        scale = 700 / max(im.size)
        im = im.resize((max(1, int(im.size[0] * scale)), max(1, int(im.size[1] * scale))), Image.Resampling.LANCZOS)
    gray = np.asarray(im)
    best, notes = candidate_mask(gray)
    if best is None:
        return {"pass_gate": False, "usable": False, "why": "no component passed the gate", "components": notes}
    _, _, mask, info = best
    contour = trace(mask)
    if contour is None:
        return {"pass_gate": True, "usable": False, "why": "contour did not close", "gate": info, "components": notes}
    contour = resample(contour)
    ys, xs = np.nonzero(mask)
    winner = None
    for gx in np.linspace(xs.min(), xs.max(), 16):
        for gy in np.linspace(ys.min(), ys.max(), 16):
            yy = int(np.clip(gy, 0, mask.shape[0] - 1))
            xx = int(np.clip(gx, 0, mask.shape[1] - 1))
            if not mask[yy, xx]:
                continue
            pole = np.array([gx, gy])
            arc = ventral_arc(contour, pole)
            if arc is None or len(arc) < 20:
                continue
            ang = alpha_series(arc, pole)
            var = float(np.nanvar(ang[: len(ang) // 2]))
            if winner is None or var < winner[0]:
                winner = (var, ang)
    if winner is None:
        return {"pass_gate": True, "usable": False, "why": "no pole", "gate": info}
    var, ang = winner
    n = len(ang)
    early = float(np.nanmedian(ang[int(0.25 * n):int(0.50 * n)]))
    late = float(np.nanmedian(ang[int(0.75 * n):]))
    usable = var <= 400
    return {
        "pass_gate": True,
        "usable": bool(usable),
        "why": None if usable else "inner-half angle variance above 400 square degrees",
        "gate": info,
        "inner_half_variance_deg2": round(var, 2),
        "alpha_early_deg": round(early, 2),
        "alpha_late_deg": round(late, 2),
        "delta_deg": round(late - early, 2),
        "n_arc": n,
    }


def classify(kind: str, early: float, late: float) -> str:
    if kind == "narrowing":
        if late > early + 10:
            return "matches"
        if late < early - 10:
            return "wrong-way"
        return "no-margin"
    if late < early - 15 and late < 60:
        return "matches"
    if late > early + 15:
        return "wrong-way"
    return "no-margin"


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    searches = {}
    files = []
    for genus, terms in SEARCH_TERMS.items():
        searches[genus] = {"commons": [], "idigbio": None}
        seen = set()
        for term in terms:
            block = commons_images(term)
            searches[genus]["commons"].append({"term": term, "http_status": block["http_status"], "n": len(block["files"])})
            for spec in block["files"]:
                if spec["download_url"] in seen:
                    continue
                seen.add(spec["download_url"])
                spec = {**spec, "genus": genus}
                files.append(spec)
        searches[genus]["idigbio"] = idigbio_images(genus if genus != "Oekotraustes" else "Oecotraustes")
        # also record the historical spelling when it differs
        if genus == "Oekotraustes":
            searches[genus]["idigbio_oekotraustes"] = idigbio_images("Oekotraustes")
        for spec in searches[genus]["idigbio"].get("files", [])[:2]:
            if spec["download_url"] in seen:
                continue
            seen.add(spec["download_url"])
            files.append({**spec, "genus": genus})
    morph = morphosource_status()

    measured_files = []
    for spec in files:
        got = obtain(spec)
        if not got.get("obtained"):
            measured_files.append(got)
            continue
        metrics = measure(Path(got["path"]))
        got.pop("path", None)
        measured_files.append({**got, **metrics})
        print(got["genus"], got["name"], metrics.get("usable"), metrics.get("alpha_early_deg"), metrics.get("alpha_late_deg"), flush=True)

    by_genus = {g: [] for g in GENERA}
    for row in measured_files:
        if row.get("genus") in by_genus:
            by_genus[row["genus"]].append(row)

    selected = {}
    for genus, rows in by_genus.items():
        usable = [r for r in rows if r.get("usable")]
        if not usable:
            selected[genus] = None
            continue
        # SVG first, else largest byte size. No SVG was returned by these searches.
        svg = [r for r in usable if str(r.get("name", "")).lower().endswith(".svg")]
        pool = svg or usable
        selected[genus] = max(pool, key=lambda r: r.get("byte_size") or 0)

    calls = {}
    for genus, kind in GENERA.items():
        row = selected[genus]
        if row is None:
            calls[genus] = "unusable"
            continue
        calls[genus] = classify(kind, row["alpha_early_deg"], row["alpha_late_deg"])
        row["call"] = calls[genus]

    usable_genera = [g for g, c in calls.items() if c != "unusable"]
    n_match = sum(c == "matches" for c in calls.values())
    n_wrong = sum(c == "wrong-way" for c in calls.values())
    if len(usable_genera) < 2:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n_match == len(usable_genera):
        verdict, reason = "supports", None
    elif n_wrong >= 2:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None

    summary = []
    for genus in GENERA:
        row = selected[genus]
        if row is None:
            summary.append({"genus": genus, "call": "unusable"})
        else:
            summary.append({
                "genus": genus,
                "call": calls[genus],
                "file": row["name"],
                "byte_size": row["byte_size"],
                "alpha_early_deg": row["alpha_early_deg"],
                "alpha_late_deg": row["alpha_late_deg"],
                "delta_deg": row["delta_deg"],
                "inner_half_variance_deg2": row["inner_half_variance_deg2"],
                "sha256": row["sha256"],
            })

    doc = {
        "searches": searches,
        "morphosource": morph,
        "selected": summary,
        "files": [{k: v for k, v in row.items() if k != "components"} for row in measured_files],
    }
    (DERIVED / "measured.json").write_text(json.dumps(doc, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "none" if verdict == "inconclusive" else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["confidence"] = {"supports": 0.45, "refutes": 0.4, "mixed": 0.35, "inconclusive": 0.55}[verdict]
    deltas = [s.get("delta_deg") for s in summary if "delta_deg" in s]
    result["measured"] = {
        "value": None if not deltas else round(float(np.median(deltas)), 2),
        "unit": "degrees, late spiral angle minus early spiral angle, median across usable selected shells",
        "n": len(usable_genera),
        "uncertainty": "one outline per genus; pole grid is 16 by 16",
        "extra": {"genera": summary, "n_matching": n_match, "n_wrong_way": n_wrong},
    }
    datasets = []
    for genus in GENERA:
        got = [r for r in measured_files if r.get("genus") == genus and r.get("sha256")]
        datasets.append({
            "id": f"wikimedia-and-idigbio-{genus.lower()}",
            "name": f"Open images searched for {genus}",
            "landing_url": "https://commons.wikimedia.org/",
            "doi": None,
            "version": "Wikimedia Commons imageinfo plus iDigBio media search, retrieved with this run",
            "license": "per-file on Wikimedia Commons or the source repository; images are not redistributed",
            "files": [
                {
                    "name": r["name"],
                    "download_url": r["download_url"],
                    "retrieved_at": r.get("retrieved_at"),
                    "byte_size": r.get("byte_size"),
                    "sha256": r.get("sha256"),
                }
                for r in got
            ],
            "role": f"{genus} lateral shell candidates",
        })
    result["datasets"] = datasets
    result["method"] = (
        "Commons JPEG search and iDigBio media search were queried for each genus, and the MorphoSource "
        "search page was requested without logging in. Each obtained image was resized to a long side of "
        "at most 700 pixels. Otsu components that touch the image border were dropped as the surround. "
        "The largest remaining component was kept when its area was 5 to 90 percent, its box aspect was "
        "0.4 to 4, and its solidity was 0.4 to 0.95. The external contour was traced and the coiling pole "
        "was the grid point inside the mask that minimised the variance of the tangent-radius angle on the "
        "inner half of the outer envelope, running from the near side of the pole toward the far side. "
        "Alpha is the acute angle between that tangent and the radius. Early is arc fraction 0.25 to 0.50 "
        "and late is the last quarter. The largest usable file for each genus is the one that counts."
    )
    result["deviations"] = [{
        "date": "2026-11-01",
        "what": (
            "Components that touch the image border are discarded, and a mask with solidity above 0.95 "
            "is discarded. The pole is chosen on a 16 by 16 grid. Images are resized to 700 pixels on the long side."
        ),
        "why": (
            "The pre-registration requires one shell outline and a pole fit, and it sets a solidity floor of 0.4 "
            "so a coiled shell with an umbilicus can pass. It does not say what to do with the mounting board or "
            "the photograph's margin, which otherwise become the largest component. A filled rectangle has solidity "
            "near 1. These filters do not change the 10 degree or 15 degree margins or the 400 square-degree variance cap."
        ),
    }]
    result["caveats"] = [
        "Oekotraustes and Oecotraustes returned no JPEG on Commons and no media on iDigBio.",
        "MorphoSource answered with a bot-check page. No account was used and no mesh was measured.",
        "Lituites photographs in the Commons sample are slabs or fragments; none left an interior component inside the gate.",
        "The size rule selects Scaphites_whitfieldi.jpg. That shell is two-toned, so the dark mask covers part of the whorl and its cast shadow rather than the whole ventral outline.",
        "The largest Ancyloceras file is a display-case photograph of a worn fragment. A smaller photograph of a whole hooked shell was measured and was not selected, because the pre-registered rule keeps the largest file that passes the gate.",
        "One shell per genus is the whole sample. A near miss of the 15 degree margin is not rounded into a match.",
        "The 2025 juvenile whorl-expansion spreadsheet was not opened.",
    ]
    bits = []
    for s in summary:
        if "delta_deg" in s:
            bits.append(f"{s['genus']} {s['call']} ({s['file']}: {s['alpha_early_deg']}° to {s['alpha_late_deg']}°)")
        else:
            bits.append(f"{s['genus']} unusable")
    result["results_summary"] = [
        "; ".join(bits) + ".",
        f"Verdict {verdict}" + (f" ({reason})." if reason else "."),
    ]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "genera": summary}, indent=2))


if __name__ == "__main__":
    main()
