"""Test of hamilton-lmc on Cook et al. (2015) Nasonia vitripennis sex-allocation data (Dryad doi:10.5061/dryad.15nj0).

Runs only if data/DryadData.xlsx is present (see fetch.py: Dryad blocks scripted download; a browser download placed in data/
is recorded by fetch.py). Column names are matched by meaning, since the spreadsheet was not inspected before pre-registration:
foundress / cofoundress count, sons (males) and daughters (females) or a sex-ratio column, and a treatment column from which
control rows are selected. If the needed columns are absent the script reports 'not-operationalizable'.
Writes derived/summary.json (and derived/broods.csv when the data are present).
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(HERE, "data", "DryadData.xlsx")
DERIVED = os.path.join(HERE, "derived")


def find_col(cols, *patterns):
    for p in patterns:
        for c in cols:
            if re.search(p, str(c), re.I):
                return c
    return None


def main():
    os.makedirs(DERIVED, exist_ok=True)
    if not os.path.exists(XLSX):
        out = {"verdict": "inconclusive", "reason": "data-unavailable", "note": "data/DryadData.xlsx not present; Dryad blocks scripted download"}
        json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1)); return
    sheets = pd.read_excel(XLSX, sheet_name=None)
    chosen = None
    for name, df in sheets.items():
        cols = list(df.columns)
        f = find_col(cols, r"co.?foundress", r"foundress", r"n_?females", r"density")
        s = find_col(cols, r"^sons?$", r"\bmales?\b", r"n_?male")
        d = find_col(cols, r"^daughters?$", r"\bfemales?\b", r"n_?female")
        sr = find_col(cols, r"sex.?ratio", r"prop.*male")
        if f and ((s and d) or sr):
            chosen = (name, df, f, s, d, sr); break
    if chosen is None:
        out = {"verdict": "inconclusive", "reason": "not-operationalizable", "sheets": {k: list(map(str, v.columns)) for k, v in sheets.items()}}
        json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1)); return
    name, df, f, s, d, sr = chosen
    tr = find_col(list(df.columns), r"treat", r"group", r"condition")
    if tr is not None:
        ctrl = df[tr].astype(str).str.contains(r"control|untreated|vehicle|water|sham", case=False, regex=True)
        used = df[ctrl] if ctrl.any() else df
        treat_note = f"treatment column '{tr}', {int(ctrl.sum())} control rows of {len(df)}" if ctrl.any() else f"treatment column '{tr}' has no recognisable control label; all rows used"
    else:
        used = df; treat_note = "no treatment column found; all rows used"
    used = used.copy()
    used["foundresses"] = pd.to_numeric(used[f], errors="coerce")
    if s and d:
        used["sons"] = pd.to_numeric(used[s], errors="coerce"); used["daughters"] = pd.to_numeric(used[d], errors="coerce")
        used["prop_sons"] = used["sons"] / (used["sons"] + used["daughters"])
    else:
        used["prop_sons"] = pd.to_numeric(used[sr], errors="coerce")
    used = used[used["foundresses"].notna() & used["prop_sons"].notna()]
    rho, p = stats.spearmanr(used["foundresses"], used["prop_sons"])
    by_n = used.groupby("foundresses")["prop_sons"].agg(["mean", "count"]).reset_index()
    by_n["predicted"] = (by_n["foundresses"] - 1) / (2 * by_n["foundresses"])
    ge2 = by_n[by_n["foundresses"] >= 2]
    mad = float(np.mean(np.abs(ge2["mean"] - ge2["predicted"]))) if len(ge2) else None
    if rho > 0 and p < 0.05 and mad is not None and mad <= 0.10:
        verdict = "supports"
    elif rho <= 0 or p >= 0.05:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out = {"sheet": name, "columns_used": {"foundresses": f, "sons": s, "daughters": d, "sex_ratio": sr}, "selection": treat_note, "n_broods": int(len(used)),
           "spearman_rho": float(rho), "spearman_p": float(p), "mean_abs_dev_from_hamilton_n_ge_2": mad,
           "by_foundress_number": by_n.to_dict("records"), "verdict": verdict}
    used[["foundresses", "prop_sons"]].to_csv(os.path.join(DERIVED, "broods.csv"), index=False)
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1); print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
