#!/usr/bin/env python3
"""Test aristotle-ga02-31: other animals are born with teeth; humans normally are not."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = "DelphiClaimTest/1.0 (aristotle-ga02-31; public claim test)"
FILES = []
MERCK = "https://www.merckvetmanual.com/digestive-system/dental-development-and-anatomy/estimation-of-age-by-examination-of-the-teeth-in-animals"
NCBI = "https://www.ncbi.nlm.nih.gov/books/NBK573074/"
OPENSTAX = "https://openstax.org/books/anatomy-and-physiology-2e/pages/23-3-the-mouth-pharynx-and-esophagus"
PANEL = ["Horse", "Cow", "Sheep and Goat", "Pig", "Dog", "Cat"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, name, role):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if os.path.exists(path) and os.path.exists(meta):
        content = open(path, "rb").read()
        when = open(meta).read().strip()
    else:
        last = None
        for attempt in range(4):
            r = requests.get(url, headers={"User-Agent": UA}, timeout=120)
            last = r
            if r.status_code == 200 and r.content:
                break
            time.sleep(2 ** attempt)
        last.raise_for_status()
        content, when = last.content, now()
        open(path, "wb").write(content)
        open(meta, "w").write(when)
    FILES.append({
        "download_url": url,
        "retrieved_at": when,
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "role": role,
    })
    return content


def lower_bound_days(cell):
    raw = cell.strip()
    if raw in {"", "—", "–", "-"}:
        return None
    s = raw.replace("–", "-").replace("—", "-")
    s = re.sub(r"\([^)]*\)", "", s)
    s = re.sub(r"\s+[bcd]\b", "", s, flags=re.I).strip()
    low = s.lower()
    if "does not erupt" in low or low in {"", "-"}:
        return None
    if "before birth" in low:
        return -1.0
    s = s.replace("½", ".5")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*(wk|mo|yr|days|day|d)\b", s, re.I)
    if not m:
        return "UNPARSED:" + raw
    unit = {"wk": 7, "mo": 30.436875, "yr": 365.25, "day": 1, "days": 1, "d": 1}[m.group(2).lower()]
    return float(m.group(1)) * unit


def parse_table(html):
    i = html.lower().find("<table")
    j = html.lower().find("</table>", i)
    rows = re.findall(r"<tr[\s\S]*?</tr>", html[i:j])
    parsed = []
    for row in rows:
        cells = re.findall(r"<t[dh][\s\S]*?</t[dh]>", row)
        texts = []
        for c in cells:
            bits = re.findall(r'data-testid="topicText"[^>]*>(.*?)</span>', c, flags=re.S)
            bits = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", b)).strip() for b in bits]
            texts.append(" ".join(b for b in bits if b))
        if texts and re.match(r"(?:Di|Dc|Dp|[ICPM])\d*", texts[0]):
            parsed.append(texts)
    return parsed


def main():
    html = fetch(MERCK, "merck-eruption.html", "eruption table").decode("utf-8", "replace")
    rows = parse_table(html)
    header = None
    # Re-read header from the first row of the raw table.
    i = html.lower().find("<table")
    j = html.lower().find("</table>", i)
    first = re.search(r"<tr[\s\S]*?</tr>", html[i:j]).group(0)
    header_cells = re.findall(r'data-testid="topicText"[^>]*>(.*?)</span>', first, flags=re.S)
    header = [re.sub(r"<[^>]+>", "", h).strip() for h in header_cells]
    col = {name: header.index(name) for name in PANEL}

    deciduous = [r for r in rows if r[0].startswith("D")]
    species = {}
    for name in PANEL:
        bounds = []
        for r in deciduous:
            lb = lower_bound_days(r[col[name]])
            bounds.append({"tooth": r[0], "cell": r[col[name]], "lower_bound_days": lb})
        numeric = [b["lower_bound_days"] for b in bounds if isinstance(b["lower_bound_days"], (int, float))]
        born_with = any(x <= 0 for x in numeric)
        born_without = bool(numeric) and all(x > 0 for x in numeric)
        species[name] = {
            "teeth": bounds,
            "born_with": born_with,
            "born_without": born_without,
        }
    # Sheep and goat share the column.
    species["Sheep"] = dict(species["Sheep and Goat"], shared_column=True)
    species["Goat"] = dict(species["Sheep and Goat"], shared_column=True)

    ncbi = fetch(NCBI, "ncbi-primary.html", "planned human primary-dentition page")
    ncbi_text = ncbi.decode("utf-8", "replace")
    ncbi_blocked = "recaptcha" in ncbi_text.lower() or "Checking your browser" in ncbi_text
    deviations = []
    openstax = fetch(OPENSTAX, "openstax-23-3.html", "human primary dentition, used because NCBI Bookshelf blocked this client").decode("utf-8", "replace")
    text = re.sub(r"<[^>]+>", " ", openstax)
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"begin to appear at about (\d+)\s+months", text, re.I)
    if not m:
        raise RuntimeError("OpenStax did not state an eruption age in months")
    human_months = int(m.group(1))
    human_without = human_months >= 4
    if ncbi_blocked:
        deviations.append({
            "field": "datasets",
            "change": "Human eruption age was read from OpenStax Anatomy and Physiology 2e section 23.3 instead of the NCBI Bookshelf page.",
            "why": "https://www.ncbi.nlm.nih.gov/books/NBK573074/ returned a browser-check page, not the chapter. Pass and fail thresholds were not changed.",
        })

    panel_names = ["Horse", "Cow", "Sheep", "Goat", "Pig", "Dog", "Cat"]
    without = [n for n in panel_names if species[n]["born_without"]]
    with_teeth = [n for n in panel_names if species[n]["born_with"]]
    if human_without and not without:
        verdict = "supports"
    elif (not human_without) and len(without) >= 2:
        verdict = "refutes"
    elif human_without and without:
        verdict = "mixed"
    elif (not human_without) and not without:
        verdict = "mixed"
    else:
        verdict = "inconclusive"

    measured = {
        "value": len(without),
        "unit": "panel species born without erupted teeth",
        "n": len(panel_names),
        "uncertainty": None,
        "extra": {
            "human_first_eruption_months": human_months,
            "human_normally_born_without": human_without,
            "born_without": without,
            "born_with": with_teeth,
            "by_species": {n: {"born_with": species[n]["born_with"], "born_without": species[n]["born_without"], "teeth": species[n]["teeth"]} for n in panel_names},
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)
    path = os.path.join(HERE, "result.json")
    result = json.load(open(path))
    result["status"] = "complete"
    result["preregistered"] = True
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = 0.8 if verdict in {"mixed", "supports", "refutes"} else 0.4
    if verdict == "inconclusive":
        result["reason"] = "data-unavailable"
    elif "reason" in result:
        del result["reason"]
    result["deviations"] = deviations
    result["method"] = (
        "Deciduous eruption ages were parsed from the Merck Veterinary Manual table. "
        "A species is born with teeth if any deciduous tooth is 'before birth' or the stated range starts at day 0; it is born without teeth if every deciduous tooth starts later. "
        "Sheep and goats share one column. "
        f"The human age is the OpenStax statement that deciduous teeth begin to appear at about {human_months} months, which meets the pre-registered threshold of 4 months for being born without teeth. "
        "The claim supports only if humans are born without teeth and every panel species is born with them; one panel species born without teeth makes the result mixed when the human clause holds."
    )
    result["measured"] = measured
    result["caveats"] = [
        "The panel is the domestic mammals in one eruption table, not every toothed animal.",
        "A range written '0–1 wk' has lower bound 0 and counts as including birth, as pre-registered.",
        "Rare human natal teeth are not the normal age stated by the source.",
        "NCBI Bookshelf did not return chapter text to this client.",
    ]
    result["datasets"] = [
        {
            "id": "merck-eruption-of-the-teeth",
            "name": "Merck Veterinary Manual, eruption of the teeth",
            "landing_url": MERCK,
            "doi": None,
            "version": "page retrieved with this run",
            "license": "publicly readable; Merck Veterinary Manual terms",
            "files": [f for f in FILES if "merckvetmanual" in f["download_url"]],
            "role": "deciduous eruption ages for the panel",
        },
        {
            "id": "ncbi-bookshelf-primary-dentition",
            "name": "NCBI Bookshelf primary dentition page (blocked) and OpenStax section 23.3",
            "landing_url": OPENSTAX,
            "doi": None,
            "version": "2e",
            "license": "OpenStax CC BY 4.0; NCBI page was a browser check",
            "files": [f for f in FILES if "ncbi" in f["download_url"] or "openstax" in f["download_url"]],
            "role": "normal age of the first human deciduous tooth",
        },
    ]
    result["headline"] = (
        f"Humans normally erupt the first tooth at about {human_months} months, and "
        + " and ".join(n.lower() + "s" for n in without)
        + " are born without erupted teeth."
    )
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(verdict, result["headline"])


if __name__ == "__main__":
    main()
