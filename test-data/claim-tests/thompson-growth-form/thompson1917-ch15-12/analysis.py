#!/usr/bin/env python3
"""Test of thompson1917-ch15-12: the left ventricle needs six to seven times the pressure of the
right, and its wall is thicker in the same proportion.

Data:
- Westaby et al. 2022, Cardiovasc Pathol 61:107508, Table 2 (1,062 morphologically normal autopsy
  hearts): ventricular muscle wall thickness by site and sex. The PDF is fetched and checksummed;
  the table values are transcribed in derived/westaby2022_table2_wall_thickness.csv.
- NHANES 2017-2018 (CDC): BPX_J (blood pressure readings), BPQ_J (medication), DEMO_J (age).
- Europe PMC full text of PMC9487613 (Table 1): healthy-subject RV systolic pressure range.
Packages: requests, numpy, pandas, scipy (pandas reads SAS XPORT).
Writes derived/summary.json.
"""
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
UA = {"User-Agent": "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"}
FILES = {
    "westaby.pdf": ("https://openaccess.sgul.ac.uk/id/eprint/115017/3/1-s2.0-S1054880722001016-main.pdf",
                    "6e5ef590b9a8500c4a74a21558c48aa3c0ddd77b4042deb911ed1a4c0700943f"),
    "BPX_J.xpt": ("https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPX_J.xpt", None),
    "BPQ_J.xpt": ("https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPQ_J.xpt", None),
    "DEMO_J.xpt": ("https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt", None),
    "PMC9487613.xml": ("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9487613/fullTextXML", None),
}


def fetch():
    os.makedirs(DATA, exist_ok=True)
    log_path = os.path.join(DATA, "fetch_log.json")
    log = json.load(open(log_path)) if os.path.exists(log_path) else {}
    out = {}
    for name, (url, sha) in FILES.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            r = requests.get(url, headers=UA, timeout=300)
            r.raise_for_status()
            open(path, "wb").write(r.content)
            log[name] = {"download_url": url, "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()}
        b = open(path, "rb").read()
        if sha:
            assert hashlib.sha256(b).hexdigest() == sha, f"checksum mismatch for {name}"
        out[name] = b
    json.dump(log, open(log_path, "w"), indent=1)
    return out, log


def rv_systolic_range(xml):
    text = re.sub(r"<[^>]+>", " ", xml.decode("utf8"))
    text = re.sub(r"\s+", " ", text)
    m = re.search(r"RVP mmHg .{0,80}?Systolic:\s*(\d+)\s*[–-]\s*(\d+)", text)
    assert m, "RV systolic range not found in PMC9487613"
    return int(m.group(1)), int(m.group(2))


def main():
    raw, log = fetch()
    t = pd.read_csv(os.path.join(DERIVED, "westaby2022_table2_wall_thickness.csv"))
    lv_sites, rv_sites = ["anterior", "lateral", "inferior"], ["anterior", "lateral", "inferior"]

    bpx = pd.read_sas(io.BytesIO(raw["BPX_J.xpt"]), format="xport")
    bpq = pd.read_sas(io.BytesIO(raw["BPQ_J.xpt"]), format="xport")
    demo = pd.read_sas(io.BytesIO(raw["DEMO_J.xpt"]), format="xport")
    d = demo[["SEQN", "RIDAGEYR", "RIAGENDR"]].merge(bpx[["SEQN", "BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4"]], on="SEQN")
    d = d.merge(bpq[["SEQN", "BPQ050A"]], on="SEQN", how="left")
    lo, hi = PRE["nhanes_age_range"]
    d = d[(d.RIDAGEYR >= lo) & (d.RIDAGEYR <= hi) & (d.BPQ050A != 1)].copy()
    d["sbp"] = d[["BPXSY1", "BPXSY2", "BPXSY3", "BPXSY4"]].mean(axis=1)
    d = d.dropna(subset=["sbp"])
    rv_lo, rv_hi = rv_systolic_range(raw["PMC9487613.xml"])
    rv_mid = (rv_lo + rv_hi) / 2

    groups = {"female": 2, "male": 1}
    res = {}
    for g, code in groups.items():
        lv = t[(t.ventricle == "LV") & (t.group == g) & t.site.isin(lv_sites)].mean_mm.mean()
        rv = t[(t.ventricle == "RV") & (t.group == g) & t.site.isin(rv_sites)].mean_mm.mean()
        sbp = d[d.RIAGENDR == code].sbp
        R_t = lv / rv
        R_p = float(sbp.median()) / rv_mid
        res[g] = {"lv_free_wall_mm": round(float(lv), 3), "rv_free_wall_mm": round(float(rv), 3), "R_t": round(float(R_t), 3),
                  "nhanes_n": int(len(sbp)), "nhanes_median_sbp_mmHg": round(float(sbp.median()), 2),
                  "R_p": round(float(R_p), 3), "R_p_bounds_rv_range": [round(float(sbp.median()) / rv_hi, 3), round(float(sbp.median()) / rv_lo, 3)],
                  "R_t_over_R_p": round(float(R_t / R_p), 3)}
    lv_all = t[(t.ventricle == "LV") & (t.group == "all") & t.site.isin(lv_sites)].mean_mm.mean()
    rv_all = t[(t.ventricle == "RV") & (t.group == "all") & t.site.isin(rv_sites)].mean_mm.mean()
    rv_all_incl_rvot = t[(t.ventricle == "RV") & (t.group == "all")].mean_mm.mean()

    def within(x, iv):
        return iv[0] <= x <= iv[1]
    sup = all(within(r["R_t"], PRE["R_t_pass"]) and within(r["R_p"], PRE["R_p_pass"]) and within(r["R_t_over_R_p"], PRE["ratio_of_ratios_pass"]) for r in res.values())
    ref = all((not within(r["R_t"], PRE["R_t_fail_outside"])) or (not within(r["R_t_over_R_p"], PRE["ratio_of_ratios_fail_outside"])) for r in res.values())
    verdict = "supports" if sup else "refutes" if ref else "mixed"
    measured = {
        "value": round(float(np.mean([r["R_t"] for r in res.values()])), 3),
        "unit": "ratio of mean LV free-wall to mean RV free-wall muscle thickness in normal autopsy hearts (mean of female and male ratios)",
        "n": 1062,
        "uncertainty": f"female {res['female']['R_t']}, male {res['male']['R_t']}; per-site SDs 1.0 mm (RV) and 2 mm (LV)",
        "extra": {"by_sex": res, "all_hearts_R_t": round(float(lv_all / rv_all), 3),
                  "all_hearts_R_t_rv_incl_rvot": round(float(lv_all / rv_all_incl_rvot), 3),
                  "rv_systolic_range_mmHg": [rv_lo, rv_hi]},
    }
    out = {"measured": measured, "verdict": verdict, "fetch": log}
    os.makedirs(DERIVED, exist_ok=True)
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
