#!/usr/bin/env python3
"""Test of levin-2018-hcn2-01: embryonic nicotine (0.1 mg/mL, st. 10-35) causes major brain
defects in ~55% of Xenopus tadpoles vs ~6% of controls.

Primary: Pai et al. 2018 Nat Commun 9:998 (PMC5843655). Only approximate percentages and
"n = 3 experiments with N > 50 embryos per treatment group" are published, so counts are
reconstructed as round(pct x N) with the smallest N consistent with the legend (3 x 51 = 153),
which is conservative for the Fisher test. The script checks the quoted phrases in the Europe PMC
full text. Context: Tung et al. 2024 Nat Commun (doi:10.1038/s41467-023-44522-2) Source Data,
nicotine-induced defect percentages by rearing group size (Fig. 2d) and at group size 100 (Fig. 3d).

Needs: requests, numpy, scipy.  Run: python3 analysis.py   (downloads data/ if missing)
"""
import datetime
import hashlib
import json
import os
import re

import numpy as np
import requests
from scipy import stats

from xlsx import read_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = {
    "pai2018_PMC5843655.xml": "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5843655/fullTextXML",
    "tung2024_source_data.xlsx": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-023-44522-2/MediaObjects/41467_2023_44522_MOESM9_ESM.xlsx",
}
N_MIN = 3 * 51
# (label, nicotine %, control %, phrase that must occur in the full text)
PAI_REPORTS = [
    ("Fig. 1d", 55, 6, "major brain morphology defects (~55%) in comparison to controls (~6%)"),
    ("Fig. 5f", 60, 7, "major brain morphology defects (~60%) in comparison to controls (~7%)"),
]
LEGEND = "Three independent experiments ( n = 3) were conducted with N > 50 embryos per treatment group"


def fetch():
    os.makedirs(DATA, exist_ok=True)
    manifest = []
    for name, url in FILES.items():
        r = requests.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        with open(os.path.join(DATA, name), "wb") as fh:
            fh.write(r.content)
        manifest.append({"name": name, "download_url": url,
                         "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
    with open(os.path.join(DATA, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)


def text_of(xml):
    t = re.sub(r"<[^>]+>", " ", xml).replace("&gt;", ">").replace("&lt;", "<")
    return re.sub(r"\s+", " ", t)


def main():
    if not all(os.path.exists(os.path.join(DATA, f)) for f in FILES):
        fetch()
    sha = {f: hashlib.sha256(open(os.path.join(DATA, f), "rb").read()).hexdigest() for f in FILES}
    text = text_of(open(os.path.join(DATA, "pai2018_PMC5843655.xml"), encoding="utf-8").read())
    phrases_found = {p: p in text for _, _, _, p in PAI_REPORTS}
    phrases_found[LEGEND] = text.count(LEGEND)

    results = {}
    for label, nic, ctl, _ in PAI_REPORTS:
        a, c = round(nic / 100 * N_MIN), round(ctl / 100 * N_MIN)
        odds, p = stats.fisher_exact([[a, N_MIN - a], [c, N_MIN - c]])
        # smallest per-group N at which Fisher p < 0.001 still holds with these percentages
        n_needed = next(n for n in range(5, 400) if stats.fisher_exact(
            [[round(nic / 100 * n), n - round(nic / 100 * n)], [round(ctl / 100 * n), n - round(ctl / 100 * n)]])[1] < 1e-3)
        results[label] = {"nicotine_pct": nic, "control_pct": ctl, "n_per_group_lower_bound": N_MIN,
                          "reconstructed_counts_nicotine_control": [a, c], "fisher_p_two_sided": float(f"{p:.3g}"),
                          "odds_ratio": round(float(odds), 2), "min_n_per_group_for_p_lt_0.001": n_needed,
                          "meets_a": nic >= 40 and ctl <= 15, "meets_b": bool(p < 1e-3),
                          "meets_fail": bool(nic - ctl < 10 or p >= 0.05)}
    primary = results["Fig. 1d"]
    if not all(v is True for k, v in phrases_found.items() if k != LEGEND) or phrases_found[LEGEND] < 1:
        verdict = "inconclusive"
    elif primary["meets_a"] and primary["meets_b"]:
        verdict = "supports"
    elif primary["meets_fail"]:
        verdict = "refutes"
    else:
        verdict = "mixed"

    wb = read_workbook(os.path.join(DATA, "tung2024_source_data.xlsx"))
    density = {}
    for row in wb["Figure2d"][1:]:
        vals = [float(x) for x in row[1:] if x not in (None, "")]
        if row and row[0]:
            density[row[0]] = {"replicates": vals, "mean": round(float(np.mean(vals)), 1)}
    g100 = [float(x) for x in wb["Figure3d"][1][1:4]]

    out = {
        "value": [primary["nicotine_pct"], primary["control_pct"]],
        "unit": "percent of stage-45 tadpoles with major brain defects, nicotine vs control (Pai et al. 2018 Fig. 1d, as reported)",
        "n": 2 * N_MIN,
        "uncertainty": f"counts reconstructed at the legend's lower bound N = {N_MIN} per group; Fisher p = {primary['fisher_p_two_sided']:.3g}",
        "extra": {
            "file_sha256": sha,
            "quoted_phrases_found_in_full_text": phrases_found,
            "pai2018": results,
            "tung2024_fig2d_nicotine_induced_defect_pct_by_group_size": density,
            "tung2024_fig3d_nicotine_brain_defect_pct_group_size_100": {"replicates": g100, "mean": round(float(np.mean(g100)), 1)},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
