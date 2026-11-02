#!/usr/bin/env python3
"""Test thompson1917-ch11-20: cephalopod septa are minimal surfaces.

The curvature thresholds in result.json apply only to an anonymously
downloadable mesh of a real septum. This script checks the four planned
records and stops when none is admissible. It does not invent a curvature.
"""
import json, os, struct, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
UA = "delphi-claim-test/1.0 (thompson1917-ch11-20; research)"
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, method="GET", headers=None, timeout=60):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
            return {
                "url": url,
                "final_url": r.geturl(),
                "status": getattr(r, "status", 200),
                "content_type": r.headers.get("Content-Type"),
                "byte_size": len(body),
                "body": body,
                "retrieved_at": NOW,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4000)
        return {
            "url": url,
            "final_url": exc.geturl(),
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "byte_size": len(body),
            "body": body,
            "retrieved_at": NOW,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "url": url,
            "status": None,
            "byte_size": 0,
            "body": b"",
            "retrieved_at": NOW,
            "error": f"{type(exc).__name__}: {exc}",
        }


def public(resp):
    out = {k: v for k, v in resp.items() if k != "body"}
    return out


def zip_names_from_tail(url):
    """Read only the ZIP central directory, not the meshes."""
    head = get(url, method="GET", headers={"Range": "bytes=0-0"})
    # A range of the tail needs the length. Ask with a HEAD-like GET of 1 byte.
    # Content-Range tells us the total when the server honours Range.
    probe = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
    with urllib.request.urlopen(probe, timeout=60) as r:
        total = None
        cr = r.headers.get("Content-Range")
        if cr and "/" in cr:
            total = int(cr.split("/")[-1])
        r.read()
    if not total:
        return [], "no-content-range"
    start = max(0, total - 400000)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": f"bytes={start}-{total - 1}"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
        status = r.status
    sig = b"PK\x01\x02"
    names, idx = [], 0
    while True:
        j = data.find(sig, idx)
        if j < 0 or j + 46 > len(data):
            break
        fn_len, extra, cmt = struct.unpack_from("<HHH", data, j + 28)
        names.append(data[j + 46:j + 46 + fn_len].decode("utf-8", "replace"))
        idx = j + 46 + fn_len + extra + cmt
    return names, status


def main():
    checks = []

    ms_page = get("https://www.morphosource.org/concern/media/000101204")
    page_text = ms_page["body"][:8000].decode("utf-8", "replace").lower()
    ms_dl = get("https://api.morphosource.org/api/download/000101204")
    ms_media = get("https://api.morphosource.org/api/media/000101204")
    morpho_admissible = False
    morpho_reason = (
        "The media page is a bot wall or an error, and the download API did not return a mesh "
        "without credentials. MorphoSource's documented download call requires an API key from an account."
    )
    if ms_dl["status"] == 200 and ms_dl["byte_size"] > 100000 and "html" not in (ms_dl["content_type"] or ""):
        morpho_admissible = True
        morpho_reason = "Anonymous download returned a file."
    checks.append({
        "id": "morphosource-media-000101204-spirula-ct",
        "admissible": morpho_admissible,
        "reason": morpho_reason,
        "page": public(ms_page) | {"mentions_bot_wall": "bot" in page_text or "making sure" in page_text},
        "download": public(ms_dl),
        "api_media": public(ms_media),
    })

    zen = get("https://zenodo.org/api/records/4308813")
    zen_meta = {}
    description = ""
    if zen["status"] == 200:
        zen_meta = json.loads(zen["body"].decode())
        description = (zen_meta.get("metadata") or {}).get("description") or ""
    # Admissible only if the record is not a constructed virtual model.
    peterman_admissible = False
    peterman_reason = (
        "Zenodo 10.5281/zenodo.4308813 describes virtual STL models made for 3D printing, "
        "including smoothed versions. Peterman, Ritterbush, Hoffmann and others built the "
        "ammonoid septa by wrapping a suture and smoothing toward a minimum-curvature surface, "
        "and built the nautiloid septum as a hemisphere (Scientific Reports 2021, "
        "s41598-021-87379-5, methods). A surface constructed to be minimal cannot test the claim."
    )
    checks.append({
        "id": "zenodo-4308813-peterman-septa-camerae-stl",
        "admissible": peterman_admissible,
        "reason": peterman_reason,
        "record": {
            "status": zen["status"],
            "retrieved_at": zen["retrieved_at"],
            "title": (zen_meta.get("metadata") or {}).get("title"),
            "doi": zen_meta.get("doi"),
            "license": (zen_meta.get("metadata") or {}).get("license"),
            "description_excerpt": description[:500],
            "files": [
                {"key": f.get("key"), "size": f.get("size")}
                for f in zen_meta.get("files") or []
            ],
        },
    })

    cherns_rec = get("https://zenodo.org/api/records/5539406")
    cherns_meta = json.loads(cherns_rec["body"].decode()) if cherns_rec["status"] == 200 else {}
    stl_url = "https://zenodo.org/api/records/5539406/files/stl_model_meshes.zip/content"
    try:
        names, range_status = zip_names_from_tail(stl_url)
        zip_error = None
    except Exception as exc:
        names, range_status, zip_error = [], None, f"{type(exc).__name__}: {exc}"
    septal = [n for n in names if "sept" in n.lower()]
    cherns_admissible = bool(septal)
    checks.append({
        "id": "zenodo-5539406-cherns-sigaloceras-stl-filenames",
        "admissible": cherns_admissible,
        "reason": (
            "The ZIP central directory lists septal surfaces."
            if septal else
            "The 49 mesh names are shell fragments, sediment, bivalves, gastropods and "
            "soft-tissue labels. None is a septal surface, and the whole-ammonite mesh is one "
            "smoothed fossil rather than an isolated septum."
        ),
        "range_status": range_status,
        "error": zip_error,
        "record": {
            "status": cherns_rec["status"],
            "retrieved_at": cherns_rec["retrieved_at"],
            "title": (cherns_meta.get("metadata") or {}).get("title"),
            "doi": cherns_meta.get("doi"),
            "license": (cherns_meta.get("metadata") or {}).get("license"),
            "files": [
                {"key": f.get("key"), "size": f.get("size")}
                for f in cherns_meta.get("files") or []
            ],
        },
        "n_names": len(names),
        "names": names,
        "septal_names": septal,
    })

    fig = get("https://api.figshare.com/v2/articles/3475058")
    fig_meta = json.loads(fig["body"].decode()) if fig["status"] == 200 else {}
    desc = fig_meta.get("description") or ""
    stress_only = "stress" in desc.lower() or "displacement" in desc.lower()
    checks.append({
        "id": "figshare-3475058-lemanis-fea-nodal-stress",
        "admissible": bool(fig["status"] == 200 and not stress_only),
        "reason": (
            "The article describes nodal displacement and principal stress, not septal coordinates."
            if stress_only else
            "File list did not establish a stress-only table."
        ),
        "record": {
            "status": fig["status"],
            "retrieved_at": fig["retrieved_at"],
            "title": fig_meta.get("title"),
            "doi": fig_meta.get("doi"),
            "description_excerpt": desc[:400],
            "files": [
                {"name": f.get("name"), "size": f.get("size")}
                for f in fig_meta.get("files") or []
            ],
        },
    })

    admissible = [c["id"] for c in checks if c["admissible"]]
    if admissible:
        verdict, reason = "inconclusive", "other"
        note = "An admissible mesh was found but this script does not yet measure it: " + ", ".join(admissible)
    else:
        verdict, reason = "inconclusive", "data-unavailable"
        note = "No anonymously downloadable mesh of a real septum was found."
    measured = {
        "verdict": verdict,
        "reason": reason,
        "note": note,
        "n_admissible": len(admissible),
        "checks": checks,
    }
    with open(os.path.join(DERIVED, "measured.json"), "w", encoding="utf-8") as f:
        json.dump(measured, f, indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "n_admissible": len(admissible),
                      "morpho_status": ms_dl["status"], "morpho_error": ms_dl.get("error"),
                      "peterman_files": checks[1]["record"].get("files"),
                      "cherns_n": len(names), "septal": septal,
                      "figshare_stress_only": stress_only}, indent=2))


if __name__ == "__main__":
    main()
