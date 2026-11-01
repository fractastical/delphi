#!/usr/bin/env python3
"""Test of levin-2024-collective-04: in an electric field whole keratocytes migrate to the
cathode and keratocyte fragments to the anode.

Published measurements: Sun et al. 2013 Curr Biol 23:569-574 (doi:10.1016/j.cub.2013.02.026),
Supplemental Table S1 (directedness = mean cos(angle to field), + = cathode, mean +/- SE, n).
The table is transcribed below; the script downloads the supplement PDF, checks its SHA-256 and
confirms that every transcribed "mean +/- SE" string occurs in the PDF's text streams. Then a
one-sample z test (mean / SE) per group and the pre-registered thresholds in result.json.

Needs: requests, scipy.  Run: python3 analysis.py   (downloads data/ if missing)
"""
import datetime
import hashlib
import json
import os
import re
import zlib

import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
URL = "https://ars.els-cdn.com/content/image/1-s2.0-S0960982213001978-mmc1.pdf"
PDF = os.path.join(DATA, "sun2013_mmc1.pdf")
SHA256 = "86efb46b6a50bcb821cc45b49688e9c2b467c3e52d5b5c86c33de384807af3e1"

# Table S1, field-strength series (V/cm): (n, directedness mean, SE) for keratocytes and fragments
TABLE_S1 = {
    0.0: ((53, 0.06, 0.05), (40, -0.13, 0.05)),
    0.1: ((47, -0.01, 0.11), (47, -0.04, 0.11)),
    0.2: ((47, 0.18, 0.10), (60, 0.12, 0.10)),
    0.5: ((53, 0.06, 0.09), (61, -0.28, 0.08)),
    1.0: ((32, 0.14, 0.08), (53, -0.22, 0.11)),
    2.0: ((51, 0.20, 0.08), (50, -0.47, 0.08)),
    4.0: ((24, 0.81, 0.07), (30, -0.65, 0.12)),
    6.0: ((39, 0.77, 0.05), (151, -0.59, 0.05)),
}
# Same table, 4 V/cm control rows: DMSO vehicle and pH 7.4 series
CONTROLS_4V = {
    "DMSO": ((52, 0.65, 0.06), (54, -0.66, 0.08)),
    "pH 7.4": ((27, 0.74, 0.09), (44, -0.83, 0.04)),
}


def fetch():
    os.makedirs(DATA, exist_ok=True)
    r = requests.get(URL, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    with open(PDF, "wb") as fh:
        fh.write(r.content)
    meta = {"download_url": URL, "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
    with open(os.path.join(DATA, "manifest.json"), "w") as fh:
        json.dump(meta, fh, indent=1)


def pdf_text(path):
    d = open(path, "rb").read()
    chunks = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", d, re.S):
        try:
            s = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        chunks += re.findall(rb"\((.*?)(?<!\\)\)", s, re.S)
    t = b"".join(chunks).decode("latin-1").replace("\\261", "±")
    return re.sub(r"\s+", "", t)


def z_test(mean, se):
    z = mean / se
    return z, 2 * stats.norm.sf(abs(z))


def main():
    if not os.path.exists(PDF):
        fetch()
    sha = hashlib.sha256(open(PDF, "rb").read()).hexdigest()
    text = pdf_text(PDF)
    rows = list(TABLE_S1.values()) + list(CONTROLS_4V.values())
    missing = [f"{m:.2f}±{s:.2f}" for row in rows for _, m, s in row if f"{m:.2f}±{s:.2f}" not in text]

    series = {}
    for field, (cell, frag) in TABLE_S1.items():
        zc, pc = z_test(cell[1], cell[2])
        zf, pf = z_test(frag[1], frag[2])
        series[f"{field:g}"] = {
            "cells_n": cell[0], "cells_directedness": cell[1], "cells_se": cell[2], "cells_z": round(zc, 2), "cells_p": float(f"{pc:.3g}"),
            "fragments_n": frag[0], "fragments_directedness": frag[1], "fragments_se": frag[2], "fragments_z": round(zf, 2), "fragments_p": float(f"{pf:.3g}"),
            "meets_pass": bool(cell[1] >= 0.5 and frag[1] <= -0.3 and pc < 0.01 and pf < 0.01),
            "meets_fail": bool(frag[1] >= 0 or cell[1] <= 0),
        }
    applied = {k: v for k, v in series.items() if k != "0"}
    pass_fields = [k for k, v in applied.items() if v["meets_pass"]]
    fail_main = any(series[k]["meets_fail"] for k in ("4", "6"))
    verdict = "supports" if pass_fields and not fail_main else ("refutes" if fail_main else "mixed")
    s6 = series["6"]
    out = {
        "value": [s6["cells_directedness"], s6["fragments_directedness"]],
        "unit": "mean directedness (cos angle to field, + = cathode) of keratocytes and fragments at 6 V/cm (Figure 1 conditions)",
        "n": s6["cells_n"] + s6["fragments_n"],
        "uncertainty": f"SE 0.05 each; z = {s6['cells_z']} (cells), {s6['fragments_z']} (fragments)",
        "extra": {
            "pdf_sha256": sha,
            "pdf_sha256_matches_recorded": sha == SHA256,
            "transcribed_values_not_found_in_pdf": missing,
            "field_series": series,
            "fields_meeting_pass": pass_fields,
            "fields_with_opposite_signs_cells_pos_fragments_neg": [k for k, v in applied.items() if v["cells_directedness"] > 0 > v["fragments_directedness"]],
            "controls_4V": {k: {"cells": list(v[0]), "fragments": list(v[1])} for k, v in CONTROLS_4V.items()},
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
