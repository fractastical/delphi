#!/usr/bin/env python3
"""Test darwin1859-ch14-03: all living things share chemical composition and machinery of growth/reproduction.

Data: KEGG REST (link/genes/ko, list/genome) and KEGG BRITE br08601 (organism taxonomy).
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

KEGG = "https://rest.kegg.jp"
MARKERS = {
    "TyrRS": ["K01866"], "TrpRS": ["K01867"], "ThrRS": ["K01868"], "LeuRS": ["K01869"], "IleRS": ["K01870"],
    "AlaRS": ["K01872"], "ValRS": ["K01873"], "MetRS": ["K01874"], "SerRS": ["K01875"], "AspRS": ["K01876"],
    "ProRS": ["K01881"], "CysRS": ["K01883"], "ArgRS": ["K01887"], "PheRS_alpha": ["K01889"], "HisRS": ["K01892"],
    "EF-Tu/EF-1alpha": ["K02358", "K03231"], "EF-G/EF-2": ["K02355", "K03234"],
    "uS12": ["K02950", "K02973"], "uL2": ["K02886", "K02938"], "uS7": ["K02992", "K02993"],
}
MIN_MARKERS = 18
FILES = []


def get_text(url, cache_name, role):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=300)
                if r.status_code == 200 and r.content:
                    break
            except requests.RequestException:
                pass
            time.sleep(2 ** attempt)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    FILES.append({"download_url": url, "retrieved_at": open(meta).read().strip(), "byte_size": len(content),
                  "sha256": hashlib.sha256(content).hexdigest(), "role": role})
    return content.decode("utf-8", errors="replace")


def main():
    write_result = "--write-result" in sys.argv
    # Organisms and domains from BRITE br08601
    br = get_text(f"{KEGG}/get/br:br08601", "br08601.txt", "KEGG organism hierarchy")
    domain = {}
    cur_b = None
    for line in br.splitlines():
        if line.startswith("B"):
            cur_b = line[1:].strip().split(" (")[0]
        elif line.startswith("E") and cur_b:
            m = re.match(r"E\s+(\S+)\s+(.*)", line)
            if m:
                code = m.group(1)
                dom = {"Bacteria": "Bacteria", "Archaea": "Archaea"}.get(cur_b, "Eukaryotes")
                domain[code] = (dom, cur_b, m.group(2).strip())
    genomes = get_text(f"{KEGG}/list/genome", "list_genome.txt", "KEGG genome list")
    org_codes = set()
    for line in genomes.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            m = re.match(r"([a-z]{2,5});", parts[1])
            if m:
                org_codes.add(m.group(1))
    orgs = sorted(c for c in org_codes if c in domain)

    presence = pd.DataFrame(False, index=orgs, columns=list(MARKERS))
    for marker, kos in MARKERS.items():
        for ko in kos:
            txt = get_text(f"{KEGG}/link/genes/ko:{ko}", f"link_genes_{ko}.txt", f"genes assigned to {ko} ({marker})")
            codes = {line.split("\t")[1].split(":")[0] for line in txt.splitlines() if "\t" in line}
            hit = [c for c in orgs if c in codes]
            presence.loc[hit, marker] = True
    presence["n_markers"] = presence[list(MARKERS)].sum(axis=1)
    presence["domain"] = [domain[c][0] for c in presence.index]
    presence["group"] = [domain[c][1] for c in presence.index]
    presence["organism"] = [domain[c][2] for c in presence.index]
    presence.to_csv(os.path.join(DERIVED, "marker_presence.csv.gz"), compression="gzip")

    by_dom = {}
    all_ok = True
    any_fail = False
    for dom, sub in presence.groupby("domain"):
        frac_core = float((sub.n_markers >= MIN_MARKERS).mean())
        prev = {m: float(sub[m].mean()) for m in MARKERS}
        by_dom[dom] = {"n_genomes": int(len(sub)), "fraction_with_ge_18_of_20": round(frac_core, 4),
                       "fraction_with_all_20": round(float((sub.n_markers == 20).mean()), 4),
                       "median_markers": float(sub.n_markers.median()), "min_markers": int(sub.n_markers.min()),
                       "marker_prevalence": {m: round(v, 4) for m, v in prev.items()},
                       "least_prevalent_marker": min(prev, key=prev.get)}
        if frac_core < 0.95 or min(prev.values()) < 0.90:
            all_ok = False
        if frac_core < 0.50 or min(prev.values()) < 0.50:
            any_fail = True
    worst = presence.sort_values("n_markers").head(15)[["organism", "group", "n_markers"]]
    worst_rows = [{"code": i, "organism": r.organism, "group": r.group, "n_markers": int(r.n_markers)} for i, r in worst.iterrows()]
    worst.to_csv(os.path.join(DERIVED, "genomes_with_fewest_markers.csv"))

    verdict = "supports" if all_ok else ("refutes" if any_fail else "mixed")
    overall = float((presence.n_markers >= MIN_MARKERS).mean())

    # POST-HOC sensitivity analysis (not pre-registered): KEGG files the archaeal / many bacterial
    # non-discriminating aspartyl-tRNA synthetase under K09759 rather than K01876, so the pre-registered
    # AspRS marker misses the same enzyme family in most Archaea. Pool K09759 into AspRS and recompute.
    txt = get_text(f"{KEGG}/link/genes/ko:K09759", "link_genes_K09759.txt", "genes assigned to K09759 (ND-AspRS; post-hoc)")
    codes = {line.split("\t")[1].split(":")[0] for line in txt.splitlines() if "\t" in line}
    sens = presence.copy()
    sens.loc[[c for c in orgs if c in codes], "AspRS"] = True
    sens["n_markers"] = sens[list(MARKERS)].sum(axis=1)
    sens_dom = {}
    s_all_ok, s_any_fail = True, False
    for dom, sub in sens.groupby("domain"):
        frac_core = float((sub.n_markers >= MIN_MARKERS).mean())
        prev = {m: float(sub[m].mean()) for m in MARKERS}
        sens_dom[dom] = {"n_genomes": int(len(sub)), "fraction_with_ge_18_of_20": round(frac_core, 4),
                         "fraction_with_all_20": round(float((sub.n_markers == 20).mean()), 4),
                         "markers_below_0.90": {m: round(v, 4) for m, v in prev.items() if v < 0.90},
                         "least_prevalent_marker": min(prev, key=prev.get), "least_prevalence": round(min(prev.values()), 4)}
        if frac_core < 0.95 or min(prev.values()) < 0.90:
            s_all_ok = False
        if frac_core < 0.50 or min(prev.values()) < 0.50:
            s_any_fail = True
    sens_verdict = "supports" if s_all_ok else ("refutes" if s_any_fail else "mixed")
    zero = presence[presence.n_markers == 0]
    measured = {
        "value": round(overall, 4),
        "unit": "fraction of KEGG organism genomes carrying >= 18 of 20 pre-registered universal translation-machinery marker families",
        "n": int(len(presence)),
        "uncertainty": "per-domain fractions in extra; exact census of KEGG genomes, no sampling error",
        "extra": {"by_domain": by_dom, "genomes_with_fewest_markers": worst_rows,
                  "fraction_with_all_20_overall": round(float((presence.n_markers == 20).mean()), 4),
                  "genomes_with_zero_markers": int(len(zero)),
                  "n_markers": len(MARKERS), "markers": MARKERS, "rule_based_verdict": verdict,
                  "post_hoc_sensitivity_pooling_K09759_into_AspRS": {
                      "overall_fraction_with_ge_18_of_20": round(float((sens.n_markers >= MIN_MARKERS).mean()), 4),
                      "overall_fraction_with_all_20": round(float((sens.n_markers == 20).mean()), 4),
                      "by_domain": sens_dom, "rule_based_verdict": sens_verdict}},
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        for ds in res["datasets"]:
            if ds["id"] == "kegg-brite-br08601":
                fl = [f for f in FILES if "br08601" in f["download_url"]]
            else:
                fl = [f for f in FILES if "br08601" not in f["download_url"]]
            ds["files"] = [{k: v for k, v in f.items() if k != "role"} | {"note": f["role"]} for f in fl]
            ds["version"] = f"KEGG release as served on {fl[0]['retrieved_at'][:10]}"
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
