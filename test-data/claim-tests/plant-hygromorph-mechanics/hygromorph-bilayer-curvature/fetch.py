#!/usr/bin/env python3
"""Fetch the three published sources for the bilayer-curvature test and record provenance.

Downloads go to raw/ (gitignored; PDFs are 0.5-5 MB). For every file the download URL, UTC
retrieval time, byte size and SHA-256 are written to derived/fetch_manifest.json. Only the
Python standard library is needed; the optional figure measurement at the end needs pymupdf
and numpy and is skipped if they are missing (its result is already in derived/measurements.csv).

Sources
  1. Reyssat & Mahadevan 2009, J. R. Soc. Interface 6:951, doi:10.1098/rsif.2009.0184.
     Publisher PDF via PubMed Central (PMC2838359). PMC fronts PDF downloads with a small
     proof-of-work cookie (sha256(challenge+nonce) with leading zeros); solved here.
  2. Quan, Pirosa, Yang, Ritchie & Meyers 2021, Acta Biomaterialia 128:370,
     doi:10.1016/j.actbio.2021.04.049, CC BY 4.0 (openaccessUserLicense in the Elsevier
     article API). ScienceDirect and the Elsevier full-text API refuse unauthenticated
     clients, so the publisher PDF is taken from the Ritchie group's library at LBNL, and the
     supplementary material (mmc1.docx with Fig. S1) from Elsevier's CDN.
  3. Dawson, Vincent & Rocca 1997, Nature 390:668, doi:10.1038/37745. Paywalled
     (isAccessibleForFree: false, USD 39.95); only the landing page is fetched, to record that.
"""
import hashlib, json, os, re, sys, time, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
DERIVED = os.path.join(HERE, "derived")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) delphisci-claim-test/1.0 (+https://github.com/fractastical/delphi)"

# sha256 = what was obtained on 2026-11-01; a cached raw/ file with this checksum is kept and
# not re-downloaded (PMC rate-limits repeat downloads behind a reCAPTCHA page).
FILES = [
    {
        "dataset": "reyssat-mahadevan2009-hygromorphs",
        "name": "rsif20090184.pdf",
        "url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2838359/pdf/rsif20090184.pdf",
        "pmc_pow": True,
        "expect": "application/pdf",
        "sha256": "544b4b7d4ce54af02e7227c7949cdc6f1613c326c12172b65fdaf69c6b860930",
        "first_retrieved_at": "2026-11-01T12:43:17Z",
    },
    {
        "dataset": "quan2021-pine-cone-hydration",
        "name": "2021_Quan_pine_cone.pdf",
        "url": "https://www2.lbl.gov/ritchie/Library/PDF/2021_Quan_pine_cone.pdf",
        "expect": "application/pdf",
        "sha256": "87f98b1f729d0f2e9dc4b5b8721b5f3528b5d0f0a4aae79f69ba27c87188e1ba",
        "first_retrieved_at": "2026-11-01T12:46:05Z",
    },
    {
        "dataset": "quan2021-pine-cone-hydration",
        "name": "1-s2.0-S1742706121002956-mmc1.docx",
        "url": "https://ars.els-cdn.com/content/image/1-s2.0-S1742706121002956-mmc1.docx",
        "expect": "application/word",
        "sha256": "2598442e28e2cd5bfbba189f4edd6a349a75bb7b100c1d7c4493cd16c75f5090",
        "first_retrieved_at": "2026-11-01T12:46:53Z",
    },
    {
        "dataset": "dawson1997-how-pine-cones-open",
        "name": "nature-37745-landing.html",
        "url": "https://www.nature.com/articles/37745",
        "expect": "text/html",
        "sha256": None,  # dynamic page; checksum recorded per run
        "first_retrieved_at": "2026-11-01T12:46:55Z",
    },
]


def get(url, cookie=None, timeout=120):
    h = {"User-Agent": UA}
    if cookie:
        h["Cookie"] = cookie
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.headers.get("content-type", ""), r.read()


def pmc_download(url):
    st, ct, body = get(url)
    m = re.search(rb'POW_CHALLENGE = "([^"]+)"', body)
    if not m:
        return st, ct, body
    d = re.search(rb'POW_DIFFICULTY = "(\d+)"', body)
    ch, diff = m.group(1).decode(), int(d.group(1)) if d else 4
    n = 0
    while not hashlib.sha256((ch + str(n)).encode()).hexdigest().startswith("0" * diff):
        n += 1
    return get(url, cookie=f"cloudpmc-viewer-pow={ch},{n}")


def main():
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(DERIVED, exist_ok=True)
    manifest = []
    for f in FILES:
        path = os.path.join(RAW, f["name"])
        if f["sha256"] and os.path.exists(path) and hashlib.sha256(open(path, "rb").read()).hexdigest() == f["sha256"]:
            manifest.append({"dataset": f["dataset"], "name": f["name"], "download_url": f["url"],
                             "retrieved_at": f["first_retrieved_at"], "byte_size": os.path.getsize(path),
                             "sha256": f["sha256"], "cached": True})
            print(f"{f['name']}: cached copy matches sha256 {f['sha256'][:16]}...")
            continue
        t0 = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        try:
            st, ct, body = pmc_download(f["url"]) if f.get("pmc_pow") else get(f["url"])
        except Exception as e:  # record the failure, keep going
            manifest.append({"dataset": f["dataset"], "name": f["name"], "download_url": f["url"], "retrieved_at": t0, "error": str(e)})
            print("FAILED", f["name"], e)
            continue
        rec = {
            "dataset": f["dataset"], "name": f["name"], "download_url": f["url"], "retrieved_at": t0,
            "http_status": st, "content_type": ct, "byte_size": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
        if f["expect"] not in ct:
            rec["warning"] = f"expected content-type {f['expect']}; got a block/captcha page, not saved"
            if f["expect"] != "text/html":
                manifest.append(rec); print("BLOCKED", f["name"], ct); continue
        if f["sha256"] and rec["sha256"] != f["sha256"]:
            rec["warning"] = "sha256 differs from the copy used for the analysis"
        with open(path, "wb") as fh:
            fh.write(body)
        if f["name"].endswith(".html"):
            rec["access_note"] = ("paywalled: isAccessibleForFree false" if '"isAccessibleForFree":false' in body.decode("utf8", "ignore")
                                  else "landing page fetched; access flag not found")
        manifest.append(rec)
        print(f"{f['name']}: {len(body)} bytes sha256 {rec['sha256'][:16]}... ({ct})")
        time.sleep(1)

    # DOI resolution check (HEAD-like GET of the first hop only)
    dois = {"10.1098/rsif.2009.0184": None, "10.1016/j.actbio.2021.04.049": None, "10.1038/37745": None}
    for doi in dois:
        try:
            req = urllib.request.Request("https://doi.org/" + doi, headers={"User-Agent": UA}, method="HEAD")
            opener = urllib.request.build_opener(NoRedirect)
            with opener.open(req, timeout=60) as r:
                dois[doi] = {"status": r.status, "location": r.headers.get("Location")}
        except urllib.error.HTTPError as e:
            dois[doi] = {"status": e.code, "location": e.headers.get("Location")}
        except Exception as e:
            dois[doi] = {"error": str(e)}

    out = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
           "files": manifest, "doi_resolution": dois}
    with open(os.path.join(DERIVED, "fetch_manifest.json"), "w") as fh:
        json.dump(out, fh, indent=2)
    print("wrote derived/fetch_manifest.json")

    if "--measure" in sys.argv:
        measure_fig3b(os.path.join(RAW, "2021_Quan_pine_cone.pdf"))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def measure_fig3b(pdf):
    """Optional: measure the length of the micro-CT'd Torrey pine scale in Quan et al. Fig. 3b
    (page 6) against its 1 cm bar, and the length of the thin proximal stalk (thickness < 8 mm).
    Needs pymupdf + numpy. Writes derived/fig3b_measurement.json; the numbers are copied into
    derived/measurements.csv by hand (rows sourced 'Fig. 3b')."""
    try:
        import pymupdf, numpy as np
    except ImportError:
        print("pymupdf/numpy not available; skipping figure measurement")
        return
    doc = pymupdf.open(pdf)
    page = doc[5]
    r = page.rect
    clip = pymupdf.Rect(r.width * 0.19, r.height * 0.06, r.width * 0.82, r.height * 0.24)
    pix = page.get_pixmap(dpi=300, clip=clip)
    a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)
    H = a.shape[0]
    reg = a[480:, 1250:, :]
    white = reg.min(axis=2) > 240
    best = None
    for y in range(white.shape[0]):
        run = mx = 0
        for v in white[y]:
            run = run + 1 if v else 0
            mx = max(mx, run)
        if mx > 80 and (best is None or mx > best):
            best = mx
    bar_px = best
    b = a[:, 300:, :]
    sat = (b.max(axis=2) - b.min(axis=2)) > 60
    sat[480:, 1250 - 300:] = False
    cols = np.where(sat.sum(axis=0) > 3)[0]
    x0, x1 = cols.min(), cols.max()
    L_mm = (x1 - x0) / bar_px * 10
    prof = []
    for x in range(x0, x1 + 1, 10):
        ys = np.where(sat[:, x])[0]
        prof.append(((x - x0) / bar_px * 10, (ys.max() - ys.min()) / bar_px * 10 if len(ys) else 0))
    stalk = [d for d, t in prof if t < 8 and d > L_mm * 0.3]
    stalk_t = [t for d, t in prof if d >= min(stalk)]
    res = {"bar_px_per_cm": int(bar_px), "scale_length_mm": round(float(L_mm), 1),
           "stalk_length_mm": round(float(max(stalk) - min(stalk)), 1),
           "stalk_thickness_mm_median": round(float(np.median(stalk_t)), 1),
           "note": "Torrey pine scale, Quan et al. 2021 Fig. 3b lateral micro-CT view; stalk = contiguous proximal region thinner than 8 mm; thickness from colour saturation underestimates dark edges"}
    with open(os.path.join(DERIVED, "fig3b_measurement.json"), "w") as fh:
        json.dump(res, fh, indent=2)
    print(res)


if __name__ == "__main__":
    main()
