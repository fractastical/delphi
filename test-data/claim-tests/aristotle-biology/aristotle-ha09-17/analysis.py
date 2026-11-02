#!/usr/bin/env python3
"""FishBase accounts of Mediterranean Lophius against the fishing-frog lure claim.

Pre-registered in result.json. Keyword windows are applied to the species summary
plus linked morphology pages. The fisheries phrases 'used as bait' and
'used as baitfish' are removed before the search.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from html import unescape
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "Mozilla/5.0 (compatible; delphisci-claim-test/1.0; research)"
SPECIES = {
    "Lophius piscatorius": "https://www.fishbase.se/summary/Lophius-piscatorius.html",
    "Lophius budegassa": "https://www.fishbase.se/summary/Lophius-budegassa.html",
}
STRUCT_RE = re.compile(r"illicium|esca|\bfilaments?\b", re.I)
USE_RE = re.compile(r"\blure\b|\bbait\b|\battract", re.I)
CONCEAL_RE = re.compile(r"\bsand\b|\bmud\b|\bbur(?:y|ies|ied|rowing)\b|\bconceal", re.I)
DENIAL_RE = re.compile(r"\b(?:no|without|lacks|lack of)\s+(?:an?\s+)?(?:illicium|esca|lure)\b", re.I)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.read(), r.geturl()


def visible(html):
    html = re.sub(r"(?is)<script\b.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?>.*?</style>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def absolutize(href):
    href = href.replace("&amp;", "&")
    if href.startswith("http"):
        return href
    if href.startswith("../"):
        return "https://www.fishbase.se/" + href[3:]
    if href.startswith("/"):
        return "https://www.fishbase.se" + href
    return "https://www.fishbase.se/" + href


def score(text):
    text = re.sub(r"used as baitfish|used as bait", " ", text, flags=re.I)
    denial = DENIAL_RE.search(text)
    structs = list(STRUCT_RE.finditer(text))
    uses = list(USE_RE.finditer(text))
    conceals = list(CONCEAL_RE.finditer(text))
    hit = None
    for s in structs:
        u = next((m for m in uses if abs(m.start() - s.start()) <= 500), None)
        c = next((m for m in conceals if abs(m.start() - s.start()) <= 800), None)
        if u and c:
            a = min(s.start(), u.start(), c.start())
            b = max(s.end(), u.end(), c.end())
            hit = {
                "structure": s.group(0),
                "use": u.group(0),
                "conceal": c.group(0),
                "excerpt": text[max(0, a - 80): b + 80],
            }
            break
    return {"support_triple": hit is not None, "denial": bool(denial),
            "denial_text": denial.group(0) if denial else None, "hit": hit,
            "n_structure": len(structs), "n_use": len(uses), "n_conceal": len(conceals)}


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    per = {}
    files_by_species = {name: [] for name in SPECIES}
    any_page = False
    for name, url in SPECIES.items():
        try:
            status, body, _ = fetch(url)
        except Exception as exc:  # noqa: BLE001
            per[name] = {"error": str(exc), "support_triple": False, "denial": False}
            continue
        any_page = True
        fname = name.replace(" ", "-") + ".html"
        (DATA / fname).write_bytes(body)
        files_by_species[name].append({
            "name": fname, "download_url": url, "retrieved_at": now(),
            "byte_size": len(body), "sha256": sha256(body), "http_status": status,
        })
        html = body.decode("utf-8", "replace")
        pages = [visible(html)]
        hrefs = re.findall(r"""href=['"]([^'"]+)['"]""", html, flags=re.I)
        extra = []
        for href in hrefs:
            low = href.lower()
            if "morphdatalist.php" in low or "fishreprosummary.php" in low:
                extra.append(absolutize(href))
        for i, link in enumerate(dict.fromkeys(extra)):
            try:
                st, b, _ = fetch(link)
            except Exception as exc:  # noqa: BLE001
                pages.append("")
                continue
            fn = f"{name.replace(' ', '-')}-extra-{i}.html"
            (DATA / fn).write_bytes(b)
            files_by_species[name].append({
                "name": fn, "download_url": link, "retrieved_at": now(),
                "byte_size": len(b), "sha256": sha256(b), "http_status": st,
            })
            pages.append(visible(b.decode("utf-8", "replace")))
        per[name] = score("\n".join(pages))

    supports = [n for n, s in per.items() if s.get("support_triple") and not s.get("denial")]
    denials = [n for n, s in per.items() if s.get("denial")]
    if denials:
        verdict, reason = "refutes", None
    elif supports:
        verdict, reason = "supports", None
    elif not any_page:
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = "inconclusive", "other"
    confidence = 0.7 if verdict == "supports" else (0.6 if verdict == "refutes" else 0.35)
    measured = {
        "value": len(supports),
        "unit": "Mediterranean Lophius species whose FishBase text meets the lure triple",
        "n": len(SPECIES),
        "uncertainty": None,
        "extra": {
            name: {k: v for k, v in info.items() if k != "hit"} | (
                {"excerpt": info["hit"]["excerpt"], "structure": info["hit"]["structure"],
                 "use": info["hit"]["use"], "conceal": info["hit"]["conceal"]} if info.get("hit") else {}
            )
            for name, info in per.items()
        },
    }
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["verdict"] = verdict
    if reason:
        doc["reason"] = reason
    elif "reason" in doc:
        del doc["reason"]
    doc["confidence"] = confidence
    doc["data_kind"] = "biological"
    for ds in doc["datasets"]:
        if "piscatorius" in ds["id"]:
            ds["files"] = files_by_species["Lophius piscatorius"]
        if "budegassa" in ds["id"]:
            ds["files"] = files_by_species["Lophius budegassa"]
    doc["measured"] = measured
    doc["method"] = (
        "Fetched each FishBase species summary and any morphology or reproduction pages it links. "
        "After deleting the fisheries phrases 'used as bait' and 'used as baitfish', the visible text "
        "was searched for a structure word (illicium, esca, filament) with a lure word within 500 "
        "characters and a burial word within 800 characters. A denial pattern refutes; silence is inconclusive."
    )
    doc["results_summary"] = [
        f"{name}: triple={info.get('support_triple')} denial={info.get('denial')} "
        f"structure_hits={info.get('n_structure')}"
        for name, info in per.items()
    ] + [f"Verdict {verdict}." + (f" Reason {reason}." if reason else "")]
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    DERIVED.joinpath("measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict, "reason": reason}, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "supports": supports, "denials": denials}, indent=2))


if __name__ == "__main__":
    main()
