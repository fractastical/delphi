#!/usr/bin/env python3
"""Extract gonad, tooth and stomach counts from Ziegler et al. 2008.

The integer must sit within six tokens of a structure word, and must not be
a figure, table, file, page or year reference. That rule was committed first.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/aristotle-pa04-09 (mailto:research@example.invalid)"
ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC2500006/"
NEXUS = "https://datadryad.org/downloads/file_stream/425384"
NEXUS_PAGE = "https://datadryad.org/dataset/doi:10.5061/dryad.7h44j0zr3"

NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
STRUCTURES = {
    "gonad": {"gonad", "gonads", "ova", "ovum"},
    "tooth": {"tooth", "teeth"},
    "stomach": {"stomach", "stomachs"},
}
REF_PREV = {
    "figure", "fig", "figs", "table", "tables", "file", "files",
    "page", "pp", "additional", "resolution",
}
# Ordinary English that the first tokenizer treated as a genus.
NOT_GENUS = {
    "moving", "although", "additional", "its", "the", "this", "figure",
    "table", "selected", "magnetic", "resolution", "inside", "after",
}


def fetch(url, dest, referer=None):
    headers = {"User-Agent": UA}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    raw = urllib.request.urlopen(req, timeout=90).read()
    dest.write_bytes(raw)
    return raw


def html_to_text(raw):
    html = raw.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script\b.*?</script>", " ", html)
    html = re.sub(r"(?is)<style\b.*?</style>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def sentences(text):
    # A single capital before a period is an abbreviation (E. metularia), not a sentence end.
    protected = re.sub(r"\b([A-Z])\.\s+", lambda m: m.group(1) + "\u00b7 ", text)
    parts = re.split(r"(?<=[.!?])\s+", protected)
    return [s.replace("\u00b7", ".").strip() for s in parts if len(s.strip()) > 20]


def tokenize(sentence):
    return re.findall(r"[A-Za-z]+|\d+", sentence)


def number_at(token):
    low = token.lower()
    if low in NUM_WORDS:
        return NUM_WORDS[low]
    if token.isdigit() and 1 <= int(token) <= 10:
        return int(token)
    return None


def species_in(sentence):
    found = []
    for m in re.finditer(r"\b([A-Z][a-z]{2,})\s+([a-z]{3,})\b", sentence):
        if m.group(1).lower() in NOT_GENUS:
            continue
        found.append(m.group(0))
    for m in re.finditer(r"\b([A-Z])\.\s*([a-z]{3,})\b", sentence):
        found.append(m.group(0))
    return found or ["unspecified"]


def structure_words():
    words = set()
    for group in STRUCTURES.values():
        words |= group
    return words


def is_reference_digit(toks, i):
    """A digit is a figure, file, table or page number when a reference word
    sits in the preceding tokens and no organ word intervenes."""
    if not toks[i].isdigit():
        return False
    organs = structure_words()
    for j in range(i - 1, max(-1, i - 10), -1):
        w = toks[j].lower()
        if w in organs or w in NUM_WORDS:
            return False
        if w in REF_PREV:
            return True
    return False


def extract(text):
    found = []
    for sentence in sentences(text):
        toks = tokenize(sentence)
        species = species_in(sentence)
        for i, tok in enumerate(toks):
            n = number_at(tok)
            if n is None:
                continue
            if tok.isdigit() and len(tok) == 4:
                continue
            if is_reference_digit(toks, i):
                continue
            window_toks = toks[max(0, i - 6): i] + toks[i + 1: i + 7]
            kinds = []
            for kind, words in STRUCTURES.items():
                if any(w.lower() in words for w in window_toks):
                    kinds.append(kind)
            for kind in kinds:
                for sp in species:
                    found.append({
                        "species": sp,
                        "structure": kind,
                        "count": n,
                        "sentence": sentence[:500],
                    })
    return found


def summarize(found):
    by = {"gonad": {}, "tooth": {}, "stomach": {}}
    for row in found:
        by[row["structure"]].setdefault(row["species"], set()).add(row["count"])
    return {k: {sp: sorted(v) for sp, v in d.items()} for k, d in by.items()}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        raw = fetch(ARTICLE, DATA / "ziegler2008.html")
        err = None
    except Exception as exc:
        raw = b""
        err = str(exc)
    text = html_to_text(raw) if raw else ""
    found = extract(text) if text else []
    # Deduplicate identical extractions.
    uniq = []
    seen = set()
    for row in found:
        key = (row["species"], row["structure"], row["count"], row["sentence"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(row)
    (DERIVED / "counts.json").write_text(json.dumps(uniq, indent=2) + "\n")
    summary = summarize(uniq)

    nexus_note = "not retrieved"
    try:
        nraw = fetch(NEXUS, DATA / "morphology.nex", referer=NEXUS_PAGE)
        if nraw[:20].lower().startswith(b"#nexus") or b"#NEXUS" in nraw[:200] or b"BEGIN DATA" in nraw[:2000]:
            nexus_note = "nexus downloaded; character labels scanned"
            labels = re.findall(r"[A-Za-z][A-Za-z0-9_ ./-]{0,80}", nraw.decode("latin1", "replace")[:200000])
            hit = [lab for lab in labels if re.search(r"gonad|tooth|teeth|lantern|stomach", lab, re.I)]
            (DERIVED / "nexus_labels.json").write_text(json.dumps(hit[:80], indent=2) + "\n")
            if not hit:
                nexus_note = "nexus downloaded; no count-character labels matched"
        else:
            nexus_note = "download was not a NEXUS file (%d bytes)" % len(nraw)
    except Exception as exc:
        nexus_note = "nexus unavailable: " + str(exc)[:200]

    gonad_species = {sp: counts for sp, counts in summary["gonad"].items() if sp != "unspecified"}
    gonad_counts = [c for counts in summary["gonad"].values() for c in counts]
    tooth_counts = [c for counts in summary["tooth"].values() for c in counts]
    stomach_counts = [c for counts in summary["stomach"].values() for c in counts]
    nonfive = [c for c in gonad_counts + tooth_counts + stomach_counts if c != 5]
    n_gonad_species = len(gonad_species)

    if not text:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.3
    elif nonfive:
        verdict, reason, confidence = "refutes", None, 0.75
    elif n_gonad_species >= 3 and gonad_counts and all(c == 5 for c in gonad_counts) and tooth_counts and all(c == 5 for c in tooth_counts) and stomach_counts and all(c == 5 for c in stomach_counts):
        verdict, reason, confidence = "supports", None, 0.6
    elif n_gonad_species >= 2 and gonad_counts and all(c == 5 for c in gonad_counts) and (not tooth_counts or not stomach_counts):
        verdict, reason, confidence = "mixed", None, 0.5
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.4

    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "verdict": verdict,
        "confidence": confidence,
        "data_kind": "biological" if text else "none",
        "method": "Downloaded the open article HTML, split it into sentences, and kept integers from 1 to 10 written as digits or words within six tokens of gonad, ova, tooth, teeth, stomach, excluding tokens preceded by figure, table, file or page. The Dryad nexus was requested and used only if the body was a NEXUS file. One count other than five refutes the universal.",
        "measured": {
            "value": (nonfive[0] if nonfive else (5 if gonad_counts else None)),
            "unit": "extracted count other than 5 if any, else 5 if every extracted count was 5",
            "n": n_gonad_species,
            "uncertainty": "counts are those written in the paper, extracted by a token window; see derived/counts.json",
            "extra": {
                "by_structure": summary,
                "n_extractions": len(uniq),
                "nonfive": nonfive,
                "nexus": nexus_note,
                "fetch_error": err,
            },
        },
        "datasets": [{
            "id": "ziegler2008-pmc2500006",
            "name": "Ziegler et al. 2008, Systematic comparison and reconstruction of sea urchin internal anatomy",
            "landing_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC2500006/",
            "doi": "10.1186/1741-7007-6-33",
            "version": "PMC2500006",
            "license": "CC BY, BMC Biology",
            "files": [{
                "download_url": ARTICLE,
                "retrieved_at": now,
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest() if raw else None,
            }],
            "role": "specimen MRI descriptions of gonads, lantern and gut",
        }],
        "results_summary": [
            f"Gonad-bearing species with an extracted count: {n_gonad_species}.",
            f"Non-five counts: {nonfive}.",
            f"Nexus: {nexus_note}.",
        ] + [
            row["sentence"]
            for row in uniq
            if row["count"] != 5
        ][:4],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    note = "A search snippet of this paper was seen before registration. The verdict uses only counts the script extracted from the downloaded HTML."
    if note not in result.get("caveats", []):
        result.setdefault("caveats", []).append(note)
    deduped = []
    for item in result.get("caveats", []):
        if item not in deduped:
            deduped.append(item)
    result["caveats"] = deduped
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, "species", n_gonad_species, "nonfive", nonfive, "extractions", len(uniq))


if __name__ == "__main__":
    main()
