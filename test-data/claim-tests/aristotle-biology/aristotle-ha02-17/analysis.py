#!/usr/bin/env python3
"""Dolphin viviparity and mammary-slit position, using the rules in result.json."""
import datetime as dt
import hashlib
import html
import io
import json
import re
import zipfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-ha02-17; research)"
PAGES = [
    ("adw-tursiops-truncatus", "Animal Diversity Web account of Tursiops truncatus",
     "https://animaldiversity.org/accounts/Tursiops_truncatus/", "bottlenose dolphin account"),
    ("adw-delphinus-delphis", "Animal Diversity Web account of Delphinus delphis",
     "https://animaldiversity.org/accounts/Delphinus_delphis/", "short-beaked common dolphin account"),
    ("noaa-ocean-today-dolphin-anatomy", "NOAA Ocean Today dolphin anatomy",
     "https://oceantoday.noaa.gov/dolphinanatomy/", "public anatomy page for dolphins"),
    ("mmapl-cetacean-gender", "Marine Mammal Anatomy and Pathology Library, cetacean sex identification",
     "https://mmapl.ucsc.edu/basic-response/gender-id/cetaceans", "mammary-slit position on cetaceans"),
]
ANAGE_URL = "https://genomics.senescence.info/species/dataset.zip"
TWO = re.compile(r"two mammary|pair of mammary|mammary slits|three slits", re.I)
GENITAL = re.compile(r"mammary", re.I)
SLIT_TAIL = re.compile(r"slit", re.I)
LIVE = re.compile(r"live young|gives birth|give birth|viviparous|\bcalf\b|\bcalves\b", re.I)
EGGS = re.compile(r"lay eggs|lays eggs|egg-laying", re.I)
CHEST = re.compile(r"thoracic mamm|teats? on the chest|mammary glands on the chest|chest teats", re.I)
SINGLE = re.compile(r"single mammary|one mammary", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read(), getattr(resp, "status", 200), resp.geturl()


def to_text(raw):
    page = raw.decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(page)).strip()


def near(text, pat, n, around):
    hits = []
    for m in re.finditer(pat, text, re.I):
        w = text[max(0, m.start() - n): m.end() + n]
        if re.search(around, w, re.I):
            hits.append(w)
    return hits


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datasets = []
    pages = []
    for pid, name, url, role in PAGES:
        try:
            raw, status, final = fetch(url)
        except Exception as exc:
            pages.append({"id": pid, "loaded": False, "error": str(exc)})
            continue
        (DATA / f"{pid}.html").write_bytes(raw)
        text = to_text(raw)
        keep = len(text) >= 2000 and re.search(r"dolphin|cetacean", text, re.I)
        rec = {
            "id": pid,
            "loaded": bool(keep),
            "http_status": status,
            "chars": len(text),
            "two_gland": bool(TWO.search(text)) if keep else False,
            "genital_near_mammary": bool(near(text, r"mammary", 120, r"genital")) if keep else False,
            "slit_near_tail": bool(near(text, r"slit", 80, r"tail")) if keep else False,
            "live_phrase": bool(LIVE.search(text)) if keep else False,
            "eggs": bool(EGGS.search(text)) if keep else False,
            "chest": bool(CHEST.search(text)) if keep else False,
            "single": bool(SINGLE.search(text)) if keep else False,
            "teat_without_slit": bool(re.search(r"teats?", text, re.I) and not re.search(r"slit", text, re.I)) if keep else False,
        }
        if keep and rec["teat_without_slit"]:
            m = re.search(r"teats?", text, re.I)
            rec["teat_snippet"] = text[max(0, m.start() - 120): m.end() + 160]
        if keep:
            m = TWO.search(text)
            rec["two_snippet"] = text[max(0, m.start() - 80): m.end() + 120] if m else ""
        pages.append(rec)
        datasets.append({
            "id": pid, "name": name, "landing_url": url, "doi": None, "version": None, "license": None,
            "files": [{"download_url": url, "retrieved_at": now, "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
            "role": role,
        })

    raw, status, final = fetch(ANAGE_URL)
    (DATA / "anage-dataset.zip").write_bytes(raw)
    gestations = []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = next(n for n in zf.namelist() if n.endswith(".txt"))
        rows = zf.read(name).decode("utf-8", "replace").splitlines()
    header = rows[0].split("\t")
    idx = {h: i for i, h in enumerate(header)}
    for line in rows[1:]:
        cols = line.split("\t")
        if len(cols) < len(header):
            continue
        if cols[idx["Family"]] != "Delphinidae":
            continue
        cell = cols[idx["Gestation/Incubation (days)"]].strip()
        if not cell:
            continue
        try:
            days = float(cell)
        except ValueError:
            continue
        gestations.append({
            "genus": cols[idx["Genus"]],
            "species": cols[idx["Species"]],
            "gestation_days": days,
        })
    long = [g for g in gestations if g["gestation_days"] >= 180]
    datasets.append({
        "id": "anage-species-dataset",
        "name": "AnAge species life-history table",
        "landing_url": "https://genomics.senescence.info/species/index.html",
        "doi": None,
        "version": None,
        "license": None,
        "files": [{"download_url": ANAGE_URL, "retrieved_at": now, "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
        "role": "gestation length for Delphinidae",
    })

    loaded_pages = [p for p in pages if p.get("loaded")]
    viv_text = any(p["live_phrase"] and not p["eggs"] for p in loaded_pages)
    viv = bool(long) or viv_text
    mammary = any(p["two_gland"] and (p["genital_near_mammary"] or p["slit_near_tail"]) for p in loaded_pages)
    contra = any(p["eggs"] or p["chest"] or p["single"] or p["teat_without_slit"] for p in loaded_pages)
    if not loaded_pages and not gestations:
        verdict, reason = "inconclusive", "data-unavailable"
    elif contra:
        verdict, reason = "refutes", None
    elif viv and mammary:
        verdict, reason = "supports", None
    elif viv and not mammary:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "data-unavailable"
    measured = {
        "value": len(long),
        "unit": "Delphinidae species in AnAge with gestation of at least 180 days",
        "n": len(gestations),
        "uncertainty": None,
        "extra": {
            "gestations": gestations,
            "viviparity_affirmed": viv,
            "mammary_affirmed": mammary,
            "contradiction": contra,
            "pages": pages,
        },
    }
    only_teat = contra and not any(p.get("eggs") or p.get("chest") or p.get("single") for p in loaded_pages) and any(p.get("two_gland") for p in loaded_pages)
    if verdict == "supports":
        confidence = 0.8
    elif verdict == "refutes" and only_teat:
        confidence = 0.46
    elif verdict == "mixed":
        confidence = 0.55
    else:
        confidence = 0.4
    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "datasets": datasets,
        "measured": measured,
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "Read AnAge gestation days for Family Delphinidae and scored the pre-registered narrative "
            "pages for a two-gland or three-slit phrase beside the genital slit or the tail. "
            "A page under 2000 characters or without the words dolphin or cetacean was dropped."
        ),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["results_summary"] = [
        f"AnAge Delphinidae with a gestation value: {len(gestations)}; of which >= 180 days: {len(long)}.",
        f"Viviparity affirmed={viv}; mammary pattern affirmed={mammary}; contradiction={contra}.",
        "Teat-without-slit pages: " + ", ".join(p["id"] for p in pages if p.get("teat_without_slit")) + ".",
        "MMAPL body was not scored when it was under 2000 characters or was a block page.",
    ] + [f"{p['id']}: loaded={p.get('loaded')} two_gland={p.get('two_gland')} genital={p.get('genital_near_mammary')} live={p.get('live_phrase')}" for p in pages]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict}, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, "long", len(long), "mammary", mammary, "viv", viv)


if __name__ == "__main__":
    main()
