#!/usr/bin/env python3
"""Score elephant trunk-snorkel pages against the rules in result.json.

The pass and fail criteria were committed before these pages were downloaded.
This script fetches them, applies those rules, and writes measured.
"""
import datetime as dt
import hashlib
import html
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-pa02-37; research)"
PAGES = [
    {
        "id": "elephantvoices-ethogram-snorkel",
        "name": "ElephantVoices Elephant Ethogram, behavior Snorkel",
        "landing_url": "https://www.elephantvoices.org/the-elephant-ethogram/snorkel",
        "download_url": "https://www.elephantvoices.org/the-elephant-ethogram/snorkel",
        "role": "catalogued behavior of Loxodonta africana while swimming or in deep water",
    },
    {
        "id": "adw-loxodonta-africana",
        "name": "Animal Diversity Web account of Loxodonta africana",
        "landing_url": "https://animaldiversity.org/accounts/Loxodonta_africana/",
        "download_url": "https://animaldiversity.org/accounts/Loxodonta_africana/",
        "role": "species account for the African elephant",
    },
    {
        "id": "adw-elephas-maximus",
        "name": "Animal Diversity Web account of Elephas maximus",
        "landing_url": "https://animaldiversity.org/accounts/Elephas_maximus/",
        "download_url": "https://animaldiversity.org/accounts/Elephas_maximus/",
        "role": "species account for the Asian elephant",
    },
]
BREATH = r"breath(?:e|ing)?|respire|respiration"
WATER = r"water|swim(?:ming)?|surface"
NEG = r"do not|does not|don't|never"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as resp:
        body = resp.read()
        return body, resp.geturl(), getattr(resp, "status", 200)


def to_text(raw):
    page = raw.decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    page = html.unescape(page)
    return re.sub(r"\s+", " ", page).strip()


def windows(text, anchor, n):
    hits = []
    for m in re.finditer(anchor, text, re.I):
        hits.append(text[max(0, m.start() - n): m.end() + n])
    return hits


def score(text):
    snorkel = list(re.finditer(r"snorkel\w*", text, re.I))
    # One trunk occurrence must sit within 80 characters of both a breath word and a water word.
    trunk_both = []
    trunk_breath = 0
    trunk_water = 0
    for m in re.finditer(r"trunk", text, re.I):
        w = text[max(0, m.start() - 80): m.end() + 80]
        breath = re.search(BREATH, w, re.I)
        water = re.search(WATER, w, re.I)
        trunk_breath += bool(breath)
        trunk_water += bool(water)
        if breath and water:
            trunk_both.append(w)
    affirm = bool(snorkel) or bool(trunk_both)
    deny_snorkel = [w for w in windows(text, r"snorkel", 80) if re.search(NEG, w, re.I)]
    deny_without = any(
        re.search(r"without", text[max(0, m.start() - 40): m.end() + 40], re.I)
        and re.search(BREATH, text[max(0, m.start() - 80): m.end() + 80], re.I)
        for m in re.finditer(r"trunk", text, re.I)
    )
    deny = bool(deny_snorkel) or deny_without
    if deny:
        label = "deny"
    elif affirm:
        label = "affirm"
    else:
        label = "silent"
    snippet = ""
    for m in snorkel:
        w = text[max(0, m.start() - 40): m.end() + 180]
        if re.search(r"breathe|breath", w, re.I):
            snippet = w
            break
    if not snippet and trunk_both:
        snippet = trunk_both[0]
    return {
        "label": label,
        "snorkel_matches": len(snorkel),
        "trunk_breath_and_water_windows": len(trunk_both),
        "trunk_breath_windows": trunk_breath,
        "trunk_water_windows": trunk_water,
        "deny_snorkel_windows": len(deny_snorkel),
        "snippet": snippet,
    }


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datasets = []
    scores = []
    for page in PAGES:
        raw, final, status = fetch(page["download_url"])
        path = DATA / f"{page['id']}.html"
        path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        text = to_text(raw)
        sc = score(text)
        sc["id"] = page["id"]
        sc["http_status"] = status
        sc["final_url"] = final
        sc["chars"] = len(text)
        scores.append(sc)
        datasets.append({
            "id": page["id"],
            "name": page["name"],
            "landing_url": page["landing_url"],
            "doi": None,
            "version": None,
            "license": None,
            "files": [{
                "download_url": page["download_url"],
                "retrieved_at": now,
                "byte_size": len(raw),
                "sha256": digest,
            }],
            "role": page["role"],
        })
    by = {s["id"]: s["label"] for s in scores}
    eth, afr, asia = (by["elephantvoices-ethogram-snorkel"], by["adw-loxodonta-africana"], by["adw-elephas-maximus"])
    loaded = all(s["http_status"] == 200 and s["chars"] > 500 for s in scores)
    if not loaded or eth == "silent" and afr == "silent" and asia == "silent":
        # silent-all is inconclusive; a failed fetch of the ethogram page is too
        if not any(s["id"] == "elephantvoices-ethogram-snorkel" and s["http_status"] == 200 for s in scores) or (
            eth == "silent" and afr == "silent" and asia == "silent"
        ):
            verdict, reason = "inconclusive", "data-unavailable"
        else:
            verdict, reason = "inconclusive", "data-unavailable"
    elif eth == "deny" or (afr == "deny" and asia == "deny"):
        verdict, reason = "refutes", None
    elif eth == "affirm" and (afr == "affirm" or asia == "affirm") and "deny" not in (eth, afr, asia):
        verdict, reason = "supports", None
    else:
        verdict, reason = "mixed", None
    n_affirm = sum(1 for s in scores if s["label"] == "affirm")
    measured = {
        "value": n_affirm,
        "unit": "pages scored affirm for trunk-snorkel breathing",
        "n": len(scores),
        "uncertainty": None,
        "extra": {"pages": scores, "labels": by},
    }
    if verdict == "supports":
        confidence = 0.8
    elif verdict == "refutes":
        confidence = 0.75
    elif verdict == "mixed" and eth == "affirm":
        confidence = 0.7
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
            "Fetched the three pre-registered pages, stripped HTML, and scored each as affirm, "
            "deny, or silent with the character windows fixed in pass_criterion. "
            f"Labels: Snorkel={eth}, Loxodonta={afr}, Elephas={asia}."
        ),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["results_summary"] = [
        f"{s['id']}: {s['label']} (snorkel matches {s['snorkel_matches']}, trunk windows with both breath and water {s['trunk_breath_and_water_windows']})."
        for s in scores
    ]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict, "reason": reason}, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, reason, by)


if __name__ == "__main__":
    main()
