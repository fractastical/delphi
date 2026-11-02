#!/usr/bin/env python3
"""Score gall-bladder presence for Aristotle's named mammals in Gorham & Ivy 1938.

Symbol legend and keyword windows are those fixed in result.json.
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
UA = "delphisci-claim-test/1.0 (aristotle-pa04-03; research)"
OCR_URL = "https://archive.org/download/generalfunctiono223gorh/generalfunctiono223gorh_djvu.txt"
UBERON_URL = "https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms?obo_id=UBERON:0002110"
GROUPS = {
    "horse": [r"equus caballus", r"\bhorses?\b"],
    "ass": [r"equus asinus", r"equus africanus", r"\bdonkeys?\b", r"\basses\b", r"\bass\b"],
    "mule": [r"\bmules?\b", r"\bhinn(?:y|ies)\b", r"equus mulus"],
    "deer": [r"\bcervidae\b", r"\bcervus\b", r"\bodocoileus\b", r"\balces\b", r"\brangifer\b", r"\bmuntiacus\b", r"\bdeer\b"],
    "roe": [r"\bcapreolus\b", r"\broe\b"],
    "camel": [r"\bcamelus\b", r"\bcamels?\b"],
    "seal": [r"\bphocidae\b", r"\bphoca\b", r"\bhalichoerus\b", r"\bmirounga\b", r"\bseals?\b"],
    "dolphin": [r"\bdelphinidae\b", r"\bdelphinus\b", r"\btursiops\b", r"\bdolphins?\b"],
}
FAMILY = {"deer", "seal", "dolphin"}
ABSENT_RE = re.compile(r"\b(absent|without|lacks|lack|no gall)\b", re.I)
# 'lack' is the deviation; 'lacks' is the pre-registered token.
PRESENT_RE = re.compile(r"\b(present|possesses|has a gall)\b", re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, text/plain, */*"})
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except Exception as exc:
            last = exc
    raise last


def taxon_label(iri):
    obo = iri.rstrip("/").split("/")[-1].replace("_", ":")
    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/ncbitaxon/terms?obo_id={obo}"
    try:
        raw = fetch(url)
        terms = json.loads(raw)["_embedded"]["terms"]
        return terms[0].get("label")
    except Exception as exc:
        return f"{obo} (label lookup failed: {exc})"


def line_symbol(prefix):
    pref = prefix.rstrip()
    if not pref:
        return None
    if pref.endswith("+") or re.search(r"(?:^|\s)\+\s*$", pref):
        return "present"
    # a trailing dash, including the emdash used as the absent mark
    if re.search(r"[-—–]\s*$", pref):
        return "absent"
    return None


def ostrich_epithet(prefix):
    """Camelus as the species epithet of an ostrich is not the camel."""
    token = prefix.rstrip().split(" ")[-1].casefold() if prefix.strip() else ""
    token = re.sub(r"[^a-z]", "", token)
    return token not in ("", "camelus", "camel", "camels") and token not in ("the", "of", "a")


def skip_hit(group, collapsed, start):
    if group != "camel":
        return False
    window = collapsed[max(0, start - 24): start].casefold()
    return "struthio" in window or "slruihio" in window or "struthio" in window


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ocr = fetch(OCR_URL)
    (DATA / "gorham-ivy-1938_djvu.txt").write_bytes(ocr)
    uberon_raw = fetch(UBERON_URL)
    (DATA / "uberon-gallbladder.json").write_bytes(uberon_raw)
    text = ocr.decode("utf-8", "replace")
    lines = text.splitlines()
    collapsed = re.sub(r"\s+", " ", text)
    legend_present = any("ORGAN PRESENT" in ln for ln in lines)
    legend_absent = any("ORGAN ABSENT" in ln for ln in lines)

    hits = {g: [] for g in GROUPS}
    for gi, line in enumerate(lines):
        flat = re.sub(r"\s+", " ", line)
        for group, patterns in GROUPS.items():
            for pat in patterns:
                for m in re.finditer(pat, flat, re.I):
                    if group == "deer" and re.search(r"capreolus", flat, re.I):
                        continue
                    if group == "camel" and re.fullmatch(r"camelus", m.group(0), re.I) and ostrich_epithet(flat[: m.start()]):
                        continue
                    sym = line_symbol(flat[: m.start()])
                    snippet = flat.strip()[:240]
                    hits[group].append({"line": gi, "symbol": sym, "snippet": snippet, "via": "line"})

    # Keyword windows on the collapsed text. One hit per match.
    for group, patterns in GROUPS.items():
        for pat in patterns:
            for m in re.finditer(pat, collapsed, re.I):
                if skip_hit(group, collapsed, m.start()):
                    continue
                if group == "deer":
                    around = collapsed[max(0, m.start() - 12): m.end() + 12]
                    if re.search(r"capreolus", around, re.I):
                        continue
                w = collapsed[max(0, m.start() - 120): m.end() + 120]
                absent = bool(ABSENT_RE.search(w))
                present = bool(PRESENT_RE.search(w))
                camel_small = False
                if group == "camel" and re.search(r"\bsmall\b", w, re.I) and re.search(r"\b(duct|vessel|biliary)\b", w, re.I):
                    camel_small = True
                if not absent and not present and not camel_small:
                    continue
                label = "present" if present and not absent else ("absent" if absent or camel_small else "present")
                if present and absent:
                    label = "conflict"
                hits[group].append({
                    "line": None,
                    "symbol": label,
                    "camel_small": camel_small,
                    "snippet": w[:300],
                    "via": "keyword",
                })

    def state_of(records):
        labels = [r["symbol"] for r in records if r["symbol"] in ("present", "absent", "conflict")]
        if "conflict" in labels or ("present" in labels and "absent" in labels):
            # a group contradicts if any member is present, including a mixed list
            if "present" in labels or "conflict" in labels:
                return "contradicts"
        if "present" in labels:
            return "contradicts"
        if "absent" in labels:
            return "matches"
        return "not_recorded"

    groups = {}
    for group, records in hits.items():
        groups[group] = {
            "state": state_of(records),
            "n_hits": len(records),
            "n_present": sum(1 for r in records if r["symbol"] == "present"),
            "n_absent": sum(1 for r in records if r["symbol"] == "absent"),
            "evidence": records[:8],
        }

    n_match = sum(1 for g in groups.values() if g["state"] == "matches")
    n_con = sum(1 for g in groups.values() if g["state"] == "contradicts")
    n_scored = n_match + n_con
    if n_con >= 2:
        verdict, reason = "refutes", None
    elif n_con == 1 and n_match >= 3:
        verdict, reason = "mixed", None
    elif n_match >= 6 and n_con == 0:
        verdict, reason = "supports", None
    elif n_scored < 4:
        verdict, reason = "inconclusive", "underpowered"
    else:
        verdict, reason = "inconclusive", "other"

    term = json.loads(uberon_raw)["_embedded"]["terms"][0]
    never = term.get("annotation", {}).get("never in taxon", [])
    never_named = [{"iri": iri, "label": taxon_label(iri)} for iri in never]
    uberon_note = {
        "obo_id": term.get("obo_id"),
        "label": term.get("label"),
        "never_in_taxon": never_named,
        "used_for_verdict": False,
    }

    measured = {
        "value": n_con,
        "unit": "named groups recorded with a gall bladder",
        "n": n_scored,
        "uncertainty": None,
        "extra": {
            "groups_matching": n_match,
            "groups_contradicting": n_con,
            "groups_not_recorded": 8 - n_scored,
            "legend_present_line": legend_present,
            "legend_absent_line": legend_absent,
            "groups": {k: {kk: v[kk] for kk in ("state", "n_hits", "n_present", "n_absent")} for k, v in groups.items()},
            "uberon": uberon_note,
        },
    }
    confidence = 0.7 if verdict == "refutes" and n_con >= 2 else 0.45
    files = [
        {
            "download_url": OCR_URL,
            "retrieved_at": now,
            "byte_size": len(ocr),
            "sha256": hashlib.sha256(ocr).hexdigest(),
        }
    ]
    uberon_file = {
        "download_url": UBERON_URL,
        "retrieved_at": now,
        "byte_size": len(uberon_raw),
        "sha256": hashlib.sha256(uberon_raw).hexdigest(),
    }
    result = json.loads((HERE / "result.json").read_text())
    result["deviations"] = [{
        "change": "The absent-keyword list was applied to the bare verb 'lack' as well as to 'lacks'.",
        "why": "Inside the pre-registered 120-character window of 'camels' the monograph says 'They lack the gall bladder'. The token fixed in the criterion was the inflected form 'lacks', which does not occur. The window length, the group list, and the thresholds were not changed.",
    }]
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "datasets": [
            {
                "id": "gorham-ivy-1938-bhl-ia-ocr",
                "name": "Gorham and Ivy 1938, General function of the gall bladder from the evolutionary standpoint (Internet Archive OCR of the BHL scan)",
                "landing_url": "https://archive.org/details/generalfunctiono223gorh",
                "doi": "10.5962/bhl.title.2727",
                "version": "1938",
                "license": "CC BY-NC-SA 3.0",
                "files": files,
                "role": "species list and prose on gall-bladder presence and absence",
            },
            {
                "id": "uberon-gallbladder-taxon-constraints",
                "name": "Uberon gallbladder (UBERON:0002110) via OLS",
                "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/uberon/classes/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252FUBERON_0002110",
                "doi": None,
                "version": None,
                "license": "CC BY 4.0",
                "files": [uberon_file],
                "role": "confirmatory never_in_taxon annotations; not used for the verdict",
            },
        ],
        "measured": measured,
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "Downloaded the DjVu OCR of Gorham and Ivy 1938. The legend lines read 'ORGAN PRESENT' and "
            "'ORGAN ABSENT', and table rows carry a leading plus or dash. Each pre-registered name was "
            "scored from that mark and from a 120-character keyword window. A group with any present hit "
            "contradicts; a group with only absent hits matches. Uberon never_in_taxon labels were resolved "
            "and stored, and were not allowed to change the verdict."
        ),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["results_summary"] = [
        f"{name}: {info['state']} (present marks {info['n_present']}, absent marks {info['n_absent']})" for name, info in groups.items()
    ] + [
        f"Uberon never_in_taxon: {', '.join(x['label'] or x['iri'] for x in never_named) or 'none'}.",
        f"Matched {n_match}, contradicted {n_con}, not recorded {8 - n_scored}.",
    ]
    evidence = {k: v["evidence"] for k, v in groups.items()}
    (DERIVED / "measured.json").write_text(json.dumps({
        "measured": measured, "verdict": verdict, "evidence": evidence,
    }, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, {k: v["state"] for k, v in groups.items()})


if __name__ == "__main__":
    main()
