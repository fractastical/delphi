#!/usr/bin/env python3
"""Test aristotle-ha02-21 against Gorham and Ivy 1938.

Downloads the Internet Archive OCR of the monograph, codes gall-bladder
presence from the table legend (+ present, minus absent) and from prose
sentences, and prints the measured summary as JSON.
"""

import hashlib
import json
import re
import ssl
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL = "https://archive.org/download/generalfunctiono223gorh/generalfunctiono223gorh_djvu.txt"
LANDING = "https://archive.org/details/generalfunctiono223gorh"
DOI = "10.5962/bhl.title.2727"
HERE = Path(__file__).resolve().parent

TAXA = {
    "deer": [r"\bcervus\b", r"\bcervidae\b", r"\bdeer\b"],
    "roe": [r"\bcapreolus\b", r"\broe\b"],
    "horse": [r"\bequus\s+caballus\b", r"\bhorses?\b"],
    "mule": [r"\bmules?\b"],
    "ass": [r"\bequus\s+asinus\b", r"\basses?\b", r"\bdonkeys?\b"],
    "seal": [r"\bphoca\b", r"\bseals?\b"],
}
# "guinea pig" is a cavy, not one of Aristotle's pigs.
PIG = [r"(?<!guinea\s)\bpigs?\b", r"\bhogs?\b", r"\bswine\b", r"\bsus\b", r"\bpeccar(?:y|ies)\b"]
CONTROL = [
    r"\bbox(?:en)?\b",
    r"\bcattle\b",
    r"\bsheep\b",
    r"\bgoats?\b",
    r"\bdogs?\b",
    r"\bcats?\b",
    r"\bhumans?\b",
    r"\bbos\b",
    r"\bovis\b",
    r"\bcanis\b",
    r"\bhomo\b",
    r"\bfelis\b",
    r"\bcapra\b",
]
GALL = re.compile(r"gall[\s-]*bladder|gall cyst", re.I)
# The cue has to govern the gall bladder. A bare "lack" or "presence" elsewhere
# in the sentence (lack of horns, presence of a sphincter) is not a code.
ABSENT_CUE = re.compile(
    r"(?:lacks?|lacking|without|absent).{0,80}gall[\s-]*bladder"
    r"|gall[\s-]*bladder.{0,40}(?:absent|lacking)"
    r"|\blost the organ\b",
    re.I,
)
PRESENT_CUE = re.compile(
    r"(?:possess(?:es)?|have|has|with|retains?|retained).{0,60}gall[\s-]*bladder"
    r"|gall[\s-]*bladder.{0,40}(?:present|retained)",
    re.I,
)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "DelphiClaimTest/1.0"})
    ctx = ssl.create_default_context()
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180, context=ctx) as resp:
                data = resp.read()
                retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return data, retrieved
        except Exception as exc:  # network timeouts on the archive.org redirect
            last = exc
    raise last


def compile_any(patterns):
    return re.compile("|".join(patterns), re.I)


TAXA_RE = {k: compile_any(v) for k, v in TAXA.items()}
PIG_RE = compile_any(PIG)
CONTROL_RE = compile_any(CONTROL)


def clean_line(line):
    return line.replace("\x0c", " ").rstrip()


def table_sign(line):
    s = line.strip()
    if not s:
        return None
    if s.startswith("+"):
        return "present"
    # Broken OCR of a plus, such as -\\-, is not a minus.
    if s.startswith("-\\") or s.startswith("—\\") or s.startswith("*"):
        return None
    if s[0] in "-—–−":
        return "absent"
    return None


def deer_only_musk(text):
    # Musk-deer and traguline "deer" are not Aristotle's deer. Drop those
    # phrases before deciding whether the line names a deer.
    stripped = re.sub(r"musk[\s-]*deer", "", text, flags=re.I)
    stripped = re.sub(r"traguline\s+deer", "", stripped, flags=re.I)
    stripped = re.sub(r"\bmoschus\b", "", stripped, flags=re.I)
    return TAXA_RE["deer"].search(stripped) is None


def match_groups(text):
    hits = []
    for name, cre in TAXA_RE.items():
        if name == "deer" and deer_only_musk(text):
            continue
        if name == "horse" and re.search(r"sea[\s-]*horse", text, re.I):
            # A line that is only about seahorses does not name the horse.
            if not re.search(r"\bequus caballus\b|\bhorses?\b", re.sub(r"sea[\s-]*horse", "", text, flags=re.I), re.I):
                continue
        if cre.search(text):
            hits.append(name)
    return hits


def sentences_of(prose):
    text = re.sub(r"\s+", " ", prose)
    parts = re.split(r"(?<=[.])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def prose_sign(sent, prev):
    organ_follows_gall = bool(re.search(r"\bthe organ\b", sent, re.I)) and bool(GALL.search(prev))
    if not GALL.search(sent) and not organ_follows_gall:
        return None
    absent = bool(ABSENT_CUE.search(sent)) or (
        organ_follows_gall and re.search(r"\blost the organ\b", sent, re.I)
    )
    present = bool(PRESENT_CUE.search(sent))
    if absent == present:
        return None
    return "absent" if absent else "present"


def prose_codes(prose):
    """Return lists of evidence dicts keyed later by taxon."""
    sents = sentences_of(prose)
    found = []
    for i, sent in enumerate(sents):
        prev = sents[i - 1] if i else ""
        sign = prose_sign(sent, prev)
        if sign is None:
            continue
        groups = match_groups(sent)
        if PIG_RE.search(sent):
            groups = groups + ["pig"]
        if CONTROL_RE.search(sent):
            groups = groups + ["control"]
        for g in groups:
            found.append({"taxon": g, "sign": sign, "source": "prose", "text": sent[:240]})
    return found


def table_codes(table_text):
    found = []
    for raw in table_text.splitlines():
        line = clean_line(raw)
        sign = table_sign(line)
        if sign is None:
            continue
        groups = match_groups(line)
        if PIG_RE.search(line):
            groups.append("pig")
        if CONTROL_RE.search(line):
            groups.append("control")
        for g in groups:
            found.append({"taxon": g, "sign": sign, "source": "table", "text": line.strip()[:240]})
    return found


def resolve(records):
    signs = {r["sign"] for r in records}
    if not records:
        return "unrecorded"
    if signs == {"absent"}:
        return "absent"
    if signs == {"present"}:
        return "present"
    return "conflict"


def main():
    data, retrieved = fetch(URL)
    text = data.decode("utf-8", errors="replace")
    # The OCR doubles spaces, so the legend is matched with flexible whitespace.
    legend = re.search(r"presence\s+of\s+the\s+gall\s+bladder\s+is\s+indicated", text, re.I)
    if not legend:
        raise SystemExit("table legend not found")
    idx = legend.start()
    prose, table = text[:idx], text[idx:]
    records = prose_codes(prose) + table_codes(table)
    by = {}
    for rec in records:
        by.setdefault(rec["taxon"], []).append(rec)
    codes = {name: resolve(by.get(name, [])) for name in list(TAXA) + ["pig", "control"]}
    six = ["deer", "roe", "horse", "mule", "ass", "seal"]
    n_absent = sum(1 for n in six if codes[n] == "absent")
    n_present = sum(1 for n in six if codes[n] == "present")
    n_mentioned = sum(1 for n in six if codes[n] != "unrecorded")
    pig_absent = codes["pig"] in ("absent", "conflict") and any(
        r["sign"] == "absent" for r in by.get("pig", [])
    )
    # Existential: at least one pig-kind record is absent.
    pig_has_absence = any(r["sign"] == "absent" for r in by.get("pig", []))
    control_present = any(r["sign"] == "present" for r in by.get("control", []))

    if n_mentioned < 4 or not control_present:
        verdict = "inconclusive"
        reason = "not-operationalizable"
    elif n_present >= 2:
        verdict = "refutes"
        reason = None
    elif n_absent >= 5 and n_present == 0 and pig_has_absence and control_present:
        verdict = "supports"
        reason = None
    elif n_present == 1 or (n_absent >= 4 and n_present == 0 and not pig_has_absence) or (
        n_absent == 4 and n_present == 0
    ):
        verdict = "mixed"
        reason = None
    else:
        verdict = "mixed"
        reason = None

    evidence = {}
    for name in list(TAXA) + ["pig", "control"]:
        evidence[name] = [
            {"sign": r["sign"], "source": r["source"], "text": r["text"]} for r in by.get(name, [])
        ]

    measured = {
        "value": n_absent,
        "unit": "named taxa coded absent out of deer, roe, horse, mule, ass and seal",
        "n": n_mentioned,
        "uncertainty": None,
        "extra": {
            "codes": codes,
            "n_absent": n_absent,
            "n_present": n_present,
            "n_conflict": sum(1 for n in six if codes[n] == "conflict"),
            "n_unrecorded": sum(1 for n in six if codes[n] == "unrecorded"),
            "pig_absence_recorded": pig_has_absence,
            "positive_control_present": control_present,
            "verdict_from_criteria": verdict,
            "reason": reason,
        },
    }
    out = {
        "retrieved_at": retrieved,
        "byte_size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "measured": measured,
        "evidence_counts": {k: len(v) for k, v in evidence.items()},
    }
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    # Keep the committed audit table small: one row per evidence hit, text clipped.
    (derived / "measured.json").write_text(json.dumps(out, indent=2) + "\n")
    (derived / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
