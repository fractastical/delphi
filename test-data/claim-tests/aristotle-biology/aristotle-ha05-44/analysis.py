#!/usr/bin/env python3
"""Code CDC DPDx life-cycle pages, via the Wayback snapshots named in result.json."""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "Mozilla/5.0 (compatible; delphisci-claim-test/aristotle-ha05-44)"

PAGES = [
    {
        "id": "cdc-dpdx-pediculosis-wayback-20261017015646",
        "name": "CDC DPDx pediculosis (lice), Wayback snapshot",
        "download_url": "https://web.archive.org/web/20261017015646/https://www.cdc.gov/dpdx/pediculosis/index.html",
        "landing_url": "https://www.cdc.gov/dpdx/pediculosis/index.html",
        "must_match": r"louse|lice|Pediculus",
    },
    {
        "id": "cdc-dpdx-fleas-wayback-20260725193531",
        "name": "CDC DPDx fleas, Wayback snapshot",
        "download_url": "https://web.archive.org/web/20260725193531/https://www.cdc.gov/dpdx/fleas/index.html",
        "landing_url": "https://www.cdc.gov/dpdx/fleas/index.html",
        "must_match": r"flea|Siphonaptera",
    },
    {
        "id": "cdc-dpdx-bedbugs-wayback-20260903215024",
        "name": "CDC DPDx bed bugs, Wayback snapshot",
        "download_url": "https://web.archive.org/web/20260903215024/https://www.cdc.gov/dpdx/bedbugs/index.html",
        "landing_url": "https://www.cdc.gov/dpdx/bedbugs/index.html",
        "must_match": r"bed\s*bug|Cimex",
    },
]
EGG = re.compile(r"\b(eggs?|nits?)\b", re.I)
HATCH = re.compile(r"\b(hatch(?:es|ed|ing)?|nymphs?|larvae|larva)\b", re.I)
NEG = re.compile(r"\b(do not|does not|don't|never|cannot|can't|not)\b", re.I)
NOTHING = re.compile(
    r"(do not|does not|don't|never|cannot).{0,40}(hatch|develop)|produce nothing|generate nothing|nothing further",
    re.I,
)


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=90).read()
    dest.write_bytes(raw)
    return raw


def html_to_text(raw):
    html = raw.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def code_page(text):
    sents = sentences(text)
    egg_sents = [s for s in sents if EGG.search(s)]
    hatch_sents = [s for s in egg_sents if HATCH.search(s) and not NEG.search(s)]
    # A negation anywhere in a long sentence can hide a real hatch clause.
    # The registration says negation in the same sentence beats a hatch word,
    # so hatch_sents above is the strict reading. Also keep the raw matches.
    raw_hatch = [s for s in egg_sents if HATCH.search(s)]
    nothing_sents = [s for s in egg_sents if NOTHING.search(s)]
    return {
        "hatch_sentences": hatch_sents[:12],
        "raw_hatch_sentences": raw_hatch[:12],
        "nothing_sentences": nothing_sents[:8],
        "n_egg_sentences": len(egg_sents),
        "codes_hatch": bool(hatch_sents),
        "codes_nothing": bool(nothing_sents) and not hatch_sents,
    }


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datasets = []
    coded = []
    for page in PAGES:
        dest = DATA / (page["id"] + ".html")
        try:
            raw = fetch(page["download_url"], dest)
            err = None
        except Exception as exc:
            raw = b""
            err = str(exc)
        text = html_to_text(raw) if raw else ""
        about = bool(re.search(page["must_match"], text, re.I)) if text else False
        coding = code_page(text) if about else {"codes_hatch": False, "codes_nothing": False, "error": err, "about": False}
        coding["about"] = about
        coding["id"] = page["id"]
        if err:
            coding["error"] = err
        coded.append(coding)
        meta = {
            "download_url": page["download_url"],
            "retrieved_at": now,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
        }
        datasets.append({
            "id": page["id"],
            "name": page["name"],
            "landing_url": page["landing_url"],
            "doi": None,
            "version": page["download_url"].split("/web/")[1].split("/")[0],
            "license": "CDC DPDx public page, retrieved from the Internet Archive",
            "files": [meta],
            "role": "life-cycle account of eggs or nits",
        })
    (DERIVED / "coding.json").write_text(json.dumps(coded, indent=2) + "\n")

    clear_hatch = [c for c in coded if c.get("codes_hatch")]
    clear_nothing = [c for c in coded if c.get("codes_nothing")]
    fetched_about = [c for c in coded if c.get("about")]
    if clear_hatch:
        verdict, reason, confidence = "refutes", None, 0.8 if len(clear_hatch) >= 2 else 0.7
    elif len(clear_nothing) == 3:
        verdict, reason, confidence = "supports", None, 0.65
    elif not fetched_about:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
    else:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.4

    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if verdict != "inconclusive" else "none",
        "method": "Fetched the three Wayback snapshots named in the registration, reduced each HTML page to text, and coded sentences that mention eggs or nits. A sentence that also says hatch, nymph, or larva, without a negation in that sentence, codes as hatching. The universal claim fails if any page codes as hatching.",
        "measured": {
            "value": len(clear_hatch),
            "unit": "number of the three accounts that state eggs or nits hatch into a later stage",
            "n": len(fetched_about),
            "uncertainty": "sentence coding of one official account per parasite, not a hatch-rate count",
            "extra": {
                "pages_about_the_parasite": len(fetched_about),
                "pages_coding_hatch": [c["id"] for c in clear_hatch],
                "pages_coding_nothing_further": [c["id"] for c in clear_nothing],
            },
        },
        "datasets": datasets,
        "results_summary": [
            f"{c['id']}: about={c.get('about')} hatch={c.get('codes_hatch')} nothing={c.get('codes_nothing')}"
            for c in coded
        ],
    })
    if reason:
        result["reason"] = reason
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, reason)


if __name__ == "__main__":
    main()
