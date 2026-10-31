#!/usr/bin/env python3
"""Test of levin-2015-girardia-02: octanol-induced G. dorotocephala head shapes are closer by
Procrustes distance to the species they resemble than to wild-type G. dorotocephala.

Parses Table 1 (lower-triangular Procrustes distance matrix) of Emmons-Bell et al. 2015,
Int J Mol Sci 16:27865 (PMC4661923, Europe PMC full-text XML) and, for each pseudo-species
group, compares d(pseudo X, WT X) with d(pseudo X, WT GD). Thresholds are in result.json.

Needs: requests.  Run: python3 analysis.py   (downloads data/ if missing)
"""
import datetime
import hashlib
import json
import os
import re

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC4661923/fullTextXML"
XML = os.path.join(DATA, "emmonsbell2015_PMC4661923.xml")
SPECIES = {"DJ": "Dugesia japonica", "PF": "Polycelis felina", "SM": "Schmidtea mediterranea"}
WILD_TYPES = ["WT GD", "WT GD after 10 days in Water", "WT DJ", "WT PF", "WT SM"]


def fetch():
    os.makedirs(DATA, exist_ok=True)
    r = requests.get(URL, timeout=120)
    r.raise_for_status()
    with open(XML, "wb") as fh:
        fh.write(r.content)
    meta = {"download_url": URL, "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    with open(os.path.join(DATA, "manifest.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


def clean(cell):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", cell)).strip()


def main():
    if not os.path.exists(XML):
        fetch()
    raw = open(XML, encoding="utf-8").read()
    sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    table = re.search(r'<table-wrap id="ijms-16-26065-t001".*?</table-wrap>', raw, re.S).group(0)
    header = [clean(c) for c in re.findall(r"<th[^>]*>(.*?)</th>", table, re.S)][1:]
    dist, bold = {}, {}
    for tr in re.findall(r"<tr>(.*?)</tr>", table.split("<tbody>")[1], re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        row = clean(cells[0])
        for col, cell in zip(header, cells[1:]):
            v = clean(cell)
            if v:
                dist[(row, col)] = dist[(col, row)] = float(v)
                bold[(row, col)] = bold[(col, row)] = "<bold>" in cell
    caption_foot = clean(re.search(r"<caption>(.*?)</caption>", table, re.S).group(1))
    foot = re.search(r"<table-wrap-foot>(.*?)</table-wrap-foot>", table, re.S)
    foot = clean(foot.group(1)) if foot else None

    groups = {}
    for code, name in SPECIES.items():
        p, wt = f"Pseudo {code}", f"WT {code}"
        to_res, to_gd = dist[(p, wt)], dist[(p, "WT GD")]
        groups[code] = {"species": name, "d_pseudo_to_resembled_wt": to_res, "d_pseudo_to_wt_gd": to_gd,
                        "closer_to_resembled": to_res < to_gd, "margin": round(to_gd - to_res, 3),
                        "d_wt_species_to_wt_gd": dist[(wt, "WT GD")],
                        "bold_pseudo_to_wt_gd": bold[(p, "WT GD")]}
        wild = {w: dist[(p, w)] for w in WILD_TYPES}
        groups[code]["distances_to_all_wild_types"] = wild
        groups[code]["nearest_wild_type"] = sorted(k for k, v in wild.items() if v == min(wild.values()))
    n_ok = sum(g["closer_to_resembled"] for g in groups.values())
    verdict = "supports" if n_ok == 3 else ("refutes" if n_ok <= 1 else "mixed")
    out = {
        "value": n_ok,
        "unit": "of 3 octanol-induced pseudo-species groups closer (Procrustes distance) to the resembled species' wild type than to wild-type G. dorotocephala",
        "n": 3,
        "uncertainty": "published distances to two decimals; no dispersion or per-pair test reported in the table",
        "extra": {
            "source_sha256": sha,
            "groups": groups,
            "table_columns": header,
            "table_caption": caption_foot,
            "table_footnote": foot,
            "pseudo_gd_to_wt_gd": dist.get(("Pseudo GD", "WT GD")),
            "groups_whose_nearest_wild_type_is_the_resembled_species": sorted(
                c for c, g in groups.items() if g["nearest_wild_type"] == [f"WT {c}"]),
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
