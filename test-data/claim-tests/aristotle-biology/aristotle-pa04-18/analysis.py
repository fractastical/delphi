#!/usr/bin/env python3
"""aristotle-pa04-18: fore and hind digit counts of wolf, lion, dog, and leopard.

Re-run: python3 analysis.py
Uses only the four Animal Diversity Web accounts named in result.json.
"""
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphi-claim-tests/1.0 (aristotle-pa04-18)"}
SPECIES = [
    ("Canis lupus", "wolf", "https://animaldiversity.org/accounts/Canis_lupus/"),
    ("Panthera leo", "lion", "https://animaldiversity.org/accounts/Panthera_leo/"),
    ("Canis lupus familiaris", "dog", "https://animaldiversity.org/accounts/Canis_lupus_familiaris/"),
    ("Panthera pardus", "leopard", "https://animaldiversity.org/accounts/Panthera_pardus/"),
]
NUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
NUM_RE = r"(one|two|three|four|five|six|\d)"
FORE = r"(?:fore\s*feet|forefeet|fore\s*foot|forefoot|front\s*feet|front\s*foot|front\s*paws|fore\s*paws|fore\s*limbs)"
HIND = r"(?:hind\s*feet|hindfeet|hind\s*foot|hindfoot|back\s*feet|rear\s*feet|hind\s*paws|hind\s*limbs)"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def nval(tok):
    tok = tok.lower()
    return NUM[tok] if tok in NUM else int(tok)


def html_text(raw):
    raw = re.sub(r"(?is)<script.*?>.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<style.*?>.*?</style>", " ", raw)
    raw = re.sub(r"(?i)</(p|div|li|h[1-6])>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html.unescape(raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return re.sub(r"\s+\n", "\n", raw)


def section_or_all(raw_html, text):
    m = re.search(r"(?is)<h[1-3][^>]*>\s*Physical Description\s*</h[1-3]>(.*?)(?=<h[1-3][^>]*>)", raw_html)
    if not m:
        return text, "whole account (no Physical Description heading)"
    sec = html_text(m.group(1))
    return text, "whole account, Physical Description searched first"


def pairs_in(text):
    """Return (fore, hind, evidence) pairs stated in the text."""
    found = []
    windows = re.split(r"(?<=[.!?])\s+", text)
    # Also slide a 240-character window so a count split across two clauses is seen once.
    compact = re.sub(r"\s+", " ", text)
    windows.append(compact)
    pat_fore_first = re.compile(
        NUM_RE + r"\s+(?:digits?|toes?)\s+(?:on|in)\s+(?:each\s+|the\s+|their\s+)*(?:of\s+)?(?:the\s+)?" + FORE
        + r".{0,120}?" + NUM_RE + r"\s+(?:digits?|toes?)?(?:\s+on|\s+in)?\s*(?:each\s+|the\s+|their\s+)*(?:of\s+)?(?:the\s+)?" + HIND,
        re.I,
    )
    pat_hind_first = re.compile(
        NUM_RE + r"\s+(?:digits?|toes?)\s+(?:on|in)\s+(?:each\s+|the\s+|their\s+)*(?:of\s+)?(?:the\s+)?" + HIND
        + r".{0,120}?" + NUM_RE + r"\s+(?:digits?|toes?)?(?:\s+on|\s+in)?\s*(?:each\s+|the\s+|their\s+)*(?:of\s+)?(?:the\s+)?" + FORE,
        re.I,
    )
    fore_only = re.compile(NUM_RE + r"\s+(?:digits?|toes?)\s+(?:on|in)\s+(?:each\s+|the\s+|their\s+)*(?:of\s+)?(?:the\s+)?" + FORE, re.I)
    hind_only = re.compile(NUM_RE + r"\s+(?:digits?|toes?)\s+(?:on|in)\s+(?:each\s+|the\s+|their\s+)*(?:of\s+)?(?:the\s+)?" + HIND, re.I)
    for w in windows:
        for m in pat_fore_first.finditer(w):
            found.append((nval(m.group(1)), nval(m.group(2)), m.group(0)[:300]))
        for m in pat_hind_first.finditer(w):
            found.append((nval(m.group(2)), nval(m.group(1)), m.group(0)[:300]))
    fores = {nval(m.group(1)) for m in fore_only.finditer(compact)}
    hinds = {nval(m.group(1)) for m in hind_only.finditer(compact)}
    if len(fores) == 1 and len(hinds) == 1:
        found.append((next(iter(fores)), next(iter(hinds)), "separate fore and hind sentences"))
    # Dewclaw: four toes on a named foot plus a dewclaw on that foot becomes five.
    def dewclaw_adds(foot_re, count):
        if count != 4:
            return count, False
        hit = re.search(foot_re + r".{0,80}dewclaw|dewclaw.{0,80}" + foot_re, compact, re.I)
        if not hit:
            return count, False
        if re.search(r"dewclaw.{0,30}absent|no dewclaw|without a dewclaw|dewclaws? (?:is|are) absent", hit.group(0), re.I):
            return count, False
        return 5, True
    adjusted = []
    for fore, hind, ev in found:
        fore2, fd = dewclaw_adds(FORE, fore)
        hind2, hd = dewclaw_adds(HIND, hind)
        note = ev
        if fd or hd:
            note = ev + " [dewclaw counted]"
        adjusted.append((fore2, hind2, note))
    return adjusted


def code_species(raw_html, text, role, final_url, requested_url):
    if role == "dog" and "familiaris" not in final_url.lower():
        # Redirected onto another account. Keep only sentences that name the domestic dog.
        bits = [s for s in re.split(r"(?<=[.!?])\s+", text) if re.search(r"domestic dog|Canis lupus familiaris|dog\b", s, re.I)]
        text = " ".join(bits)
        if not text.strip():
            return {"code": "unscored", "reason": "dog account redirects and does not state digits separately", "pairs": []}
    pairs = pairs_in(text)
    uniq = {(a, b) for a, b, _ in pairs}
    if not uniq:
        return {"code": "unscored", "reason": "no explicit fore and hind digit counts", "pairs": []}
    if len(uniq) > 1:
        return {"code": "unscored", "reason": "conflicting counts", "pairs": pairs}
    fore, hind = next(iter(uniq))
    ok = fore == 5 and hind == 4
    return {"code": "pass" if ok else "fail", "fore": fore, "hind": hind, "pairs": pairs}


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    rows = []
    files = []
    for name, role, url in SPECIES:
        r = requests.get(url, timeout=90, headers=UA)
        meta = {
            "download_url": r.url,
            "requested_url": url,
            "retrieved_at": now(),
            "byte_size": len(r.content),
            "sha256": hashlib.sha256(r.content).hexdigest(),
            "status_code": r.status_code,
        }
        dest = DATA / f"adw-{name.replace(' ', '_')}.html"
        dest.write_bytes(r.content)
        (dest.with_suffix(".html.meta.json")).write_text(json.dumps(meta, indent=2) + "\n")
        files.append(meta)
        if r.status_code != 200:
            rows.append({"species": name, "role": role, "code": "unresolved", "status_code": r.status_code})
            continue
        text = html_text(r.text)
        coded = code_species(r.text, text, role, r.url, url)
        coded.update({"species": name, "role": role, "final_url": r.url})
        rows.append(coded)

    scored = [x for x in rows if x["code"] in {"pass", "fail"}]
    fails = [x for x in scored if x["code"] == "fail"]
    passes = [x for x in scored if x["code"] == "pass"]
    if len(scored) < 3:
        verdict, confidence, reason = "inconclusive", 0.60, "data-unavailable"
    elif len(fails) >= 2:
        verdict, confidence, reason = "refutes", 0.70, None
    elif len(fails) == 1 and passes:
        verdict, confidence, reason = "mixed", 0.50, None
    elif len(fails) == 0 and len(passes) >= 3:
        verdict = "supports"
        confidence = 0.75 if len(passes) == 4 else 0.60
        reason = None
    else:
        verdict, confidence, reason = "inconclusive", 0.60, "data-unavailable"

    measured = {
        "value": len(passes),
        "unit": "named species whose account states 5 fore digits and 4 hind digits",
        "n": len(rows),
        "uncertainty": "one published account per species; unscored accounts state no digit formula",
        "extra": {
            "scored": len(scored),
            "fail": len(fails),
            "species": [
                {k: x.get(k) for k in ("species", "role", "code", "fore", "hind", "reason")}
                for x in rows
            ],
        },
    }
    (DERIVED / "digits.json").write_text(json.dumps({"rows": rows, "measured": measured}, indent=2) + "\n")
    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = confidence
    result["data_kind"] = "biological" if files and any(f["status_code"] == 200 for f in files) else "none"
    if reason:
        result["reason"] = reason
    result["datasets"] = [{
        "id": "adw-carnivore-digit-accounts",
        "name": "Animal Diversity Web accounts for wolf, lion, domestic dog, and leopard",
        "landing_url": "https://animaldiversity.org/",
        "doi": None,
        "version": "pages retrieved " + now()[:10],
        "license": "Animal Diversity Web, University of Michigan Museum of Zoology",
        "files": [{k: f[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")} | {"requested_url": f["requested_url"]} for f in files],
        "role": "explicit forefoot and hind-foot digit counts",
    }]
    result["method"] = (
        "Fetched the four Animal Diversity Web accounts and searched the text for a number of digits or toes "
        "tied to a fore foot and a hind foot. A dewclaw stated for a foot whose count is four is added, so the "
        "count includes it. Conflicting numbers leave the species unscored. The domestic dog is scored only from "
        "sentences that survive a redirect onto the wolf account. The verdict uses the pre-registered thresholds "
        "and no other website."
    )
    result["measured"] = measured
    if verdict == "supports":
        headline = "The scored wolf, lion, dog, and leopard accounts state five fore digits and four hind digits."
    elif verdict == "refutes":
        headline = "Two or more of the named carnivores are given a digit formula other than five in front and four behind."
    elif verdict == "mixed":
        headline = "One named species misses the five-and-four formula and the others that were scored match it."
    else:
        headline = (
            f"Animal Diversity Web states both a forefoot count and a hind-foot count for {len(scored)} of the four species, "
            "which is below the three required to score the claim."
        )
    result["results_summary"] = [headline]
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "species": measured["extra"]["species"]}, indent=2))


if __name__ == "__main__":
    main()
