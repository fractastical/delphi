#!/usr/bin/env python3
"""Code extension publications for egg laying without a male, hens and geese."""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

DOCS = [
    {"id": "msu-extension-backyard-flock", "group": "hen", "kind": "html",
     "url": "https://extension.msstate.edu/publications/choosing-the-right-breed-for-your-backyard-flock"},
    {"id": "ncsu-extension-garden-chickens", "group": "hen", "kind": "html",
     "url": "https://content.ces.ncsu.edu/keeping-garden-chickens-in-north-carolina"},
    {"id": "uf-ifas-an239", "group": "hen", "kind": "pdf",
     "url": "https://ask.ifas.ufl.edu/publication/AN239/pdf"},
    {"id": "psu-extension-these-eggs", "group": "hen", "kind": "html",
     "url": "https://extension.psu.edu/what-do-i-do-with-all-these-eggs"},
    {"id": "umd-extension-eb409", "group": "hen", "kind": "pdf",
     "url": "https://extension.umd.edu/sites/extension.umd.edu/files/publications/EB-409%202013%20Raising%20Your%20Home%20Chicken%20Flock.pdf"},
    {"id": "nsw-dpi-goose-egg-production", "group": "goose", "kind": "html",
     "url": "https://www.dpi.nsw.gov.au/animals-and-livestock/poultry-and-birds/species/geese-raising/egg-production"},
    {"id": "unl-extension-g84-711-goose-breeder", "group": "goose", "kind": "pdf",
     "url": "https://digitalcommons.unl.edu/cgi/viewcontent.cgi?article=2279&context=extensionhist"},
]

HEN_PASS = re.compile(
    r"(without (a |any )?(rooster|male)|no rooster|absence of a rooster|"
    r"rooster is not (needed|necessary|required)|"
    r"roosters? are not (needed|necessary|required)|"
    r"not required in order for .{0,40}lay|"
    r"do not need a rooster|don't need a rooster|"
    r"not necessary .{0,40}eggs|not necessary for hens to (begin |start )?lay|"
    r"not required for (the )?hen|even if you do not .{0,20}have a rooster)",
    re.I,
)
HEN_LAY = re.compile(r"\b(lay|lays|laying|laid|produce eggs|egg production)\b", re.I)
GOOSE_PASS = re.compile(
    r"(without (a |any )?(gander|male)|no gander|gander is not (needed|necessary|required)|"
    r"do not need a gander|not required for (the )?(goose|geese)|without a male)",
    re.I,
)
GOOSE_WORD = re.compile(r"\b(goose|geese|gander)\b", re.I)
# An assertion that laying itself requires a male. Questions and "not required" stay out.
FAIL_HEN = re.compile(
    r"\b(do not|don't|cannot|will not|only)\s+lay\b.{0,80}\b(rooster|gander|male)\b|"
    r"\b(must have|only when|only if)\b.{0,40}\b(rooster|gander)\b.{0,40}\blay",
    re.I,
)
FAIL_NEG = re.compile(r"\b(not required|not necessary|not needed|not the case|without)\b", re.I)


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
    return re.sub(r"\s+", " ", html)


def pdf_to_text(path):
    reader = PdfReader(str(path))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return re.sub(r"\s+", " ", text)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def code_doc(text, group):
    sents = sentences(text)
    if group == "hen":
        passed = [s for s in sents if HEN_LAY.search(s) and HEN_PASS.search(s)]
        failed = [s for s in sents if FAIL_HEN.search(s) and not FAIL_NEG.search(s)]
    else:
        passed = [s for s in sents if GOOSE_WORD.search(s) and HEN_LAY.search(s) and GOOSE_PASS.search(s)]
        failed = [s for s in sents if GOOSE_WORD.search(s) and FAIL_HEN.search(s) and not FAIL_NEG.search(s)]
    return {"pass_sentences": passed[:6], "fail_sentences": failed[:4], "pass": bool(passed) and not failed, "fail": bool(failed)}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    coded = []
    datasets = []
    for doc in DOCS:
        suffix = ".pdf" if doc["kind"] == "pdf" else ".html"
        dest = DATA / (doc["id"] + suffix)
        try:
            raw = fetch(doc["url"], dest)
            err = None
            text = pdf_to_text(dest) if doc["kind"] == "pdf" else html_to_text(raw)
        except Exception as exc:
            raw = b""
            err = str(exc)
            text = ""
        coding = code_doc(text, doc["group"]) if text else {"pass": False, "fail": False, "pass_sentences": [], "fail_sentences": []}
        coding.update({"id": doc["id"], "group": doc["group"], "error": err, "fetched": bool(text), "chars": len(text)})
        coded.append(coding)
        datasets.append({
            "id": doc["id"],
            "name": doc["id"],
            "landing_url": doc["url"],
            "doi": None,
            "version": now[:10],
            "license": "public university or government extension publication",
            "files": [{
                "download_url": doc["url"],
                "retrieved_at": now,
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
            }],
            "role": doc["group"] + " egg-laying statement",
        })
    (DERIVED / "coding.json").write_text(json.dumps(coded, indent=2) + "\n")

    hens = [c for c in coded if c["group"] == "hen"]
    geese = [c for c in coded if c["group"] == "goose"]
    hens_fetched = [c for c in hens if c["fetched"]]
    hen_pass = [c for c in hens_fetched if c["pass"]]
    hen_fail = [c for c in hens_fetched if c["fail"]]
    goose_pass = [c for c in geese if c["fetched"] and c["pass"]]
    goose_fail = [c for c in geese if c["fetched"] and c["fail"]]
    goose_fetched = [c for c in geese if c["fetched"]]

    if len(hens_fetched) < 3:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
    elif len(hen_fail) > len(hens_fetched) / 2 or goose_fail:
        verdict, reason, confidence = "refutes", None, 0.6
    elif len(hen_pass) >= 3 and goose_pass:
        verdict, reason, confidence = "supports", None, 0.6
    elif len(hen_pass) >= 3 and goose_fetched and not goose_pass:
        verdict, reason, confidence = "mixed", None, 0.55
    elif len(hen_pass) >= 3 and not goose_fetched:
        # Goose URLs failed. The joint claim needs both species. Missing goose
        # files are data-unavailable, not a refutation and not a pass.
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.45
    else:
        verdict, reason, confidence = "inconclusive", "not-operationalizable", 0.4

    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if hens_fetched else "none",
        "method": "Downloaded the seven pre-registered extension documents, extracted text (HTML stripped, PDFs via pypdf), and coded sentences. A hen pass sentence states laying together with the absence of a rooster. A goose pass sentence does the same for a gander or male. The hen component needs three passing documents. The goose component needs one. Both are required for support.",
        "measured": {
            "value": len(hen_pass),
            "unit": "hen documents, of those fetched, stating that hens lay without a rooster",
            "n": len(hens_fetched),
            "uncertainty": "extension statements, not a counted flock; sperm storage is not measured",
            "extra": {
                "hen_pass": [c["id"] for c in hen_pass],
                "hen_fail": [c["id"] for c in hen_fail],
                "goose_pass": [c["id"] for c in goose_pass],
                "goose_fail": [c["id"] for c in goose_fail],
                "goose_fetched": [c["id"] for c in goose_fetched],
            },
        },
        "datasets": datasets,
        "results_summary": [
            f"Hen documents passing: {len(hen_pass)} of {len(hens_fetched)} fetched.",
            f"Goose documents passing: {len(goose_pass)} of {len(goose_fetched)} fetched.",
        ] + [
            f"{c['id']}: {c['pass_sentences'][0]}"
            for c in hen_pass
            if c.get("pass_sentences")
        ] + [
            f"{c['id']}: {c['error']}"
            for c in coded
            if c["group"] == "goose" and c.get("error")
        ],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    note = "These are extension statements, not a log of eggs from identified unmated birds. They do not measure how long any sperm could have been stored."
    if note not in result.get("caveats", []):
        result.setdefault("caveats", []).append(note)
    deduped = []
    for item in result.get("caveats", []):
        if item not in deduped:
            deduped.append(item)
    result["caveats"] = deduped
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, "hens", len(hen_pass), "/", len(hens_fetched), "geese", len(goose_pass), "/", len(goose_fetched))


if __name__ == "__main__":
    main()
