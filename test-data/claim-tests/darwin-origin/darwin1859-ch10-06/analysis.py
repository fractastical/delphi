#!/usr/bin/env python3
"""Test of darwin1859-ch10-06: genus richness of (extinct) families rises gradually to a
maximum and then declines gradually to extinction.

Data: Paleobiology Database data service 1.2 (taxa/list for the family sampling frame,
occs/diversity for range-through genus counts per stage). Raw responses are not committed;
their sizes and SHA-256 go to derived/fetch_log.csv.gz (one row per request, query string
truncated; the two URL templates are in result.json), and the per-family shape table
to derived/family_trajectories.csv.
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
RESULT = json.load(open(os.path.join(HERE, "result.json")))
PRE = RESULT["preregistration"]
API = "https://paleobiodb.org/data1.2"
FETCH_LOG = []
S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"


def get(path, params, tries=5):
    for attempt in range(tries):
        try:
            r = S.get(API + path, params=params, timeout=180)
            if r.status_code == 200:
                FETCH_LOG.append({"request": path + "?" + r.url.split("?", 1)[1][:60],
                                  "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
                return r.json()
            print("HTTP", r.status_code, r.url, file=sys.stderr)
        except requests.RequestException as e:
            print("retry", attempt, e, file=sys.stderr)
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("PBDB request failed: " + path)


def trajectory(taxon_id):
    d = get("/occs/diversity.json", {"base_id": taxon_id, "count": PRE["count_unit"],
                                      "time_reso": PRE["time_resolution"]})
    recs = d.get("records", [])
    if not recs:
        return None
    df = pd.DataFrame(recs)
    for c in ("xft", "xbl", "xfl", "xbt", "dsb", "noc"):
        if c not in df:
            df[c] = 0
        df[c] = df[c].fillna(0).astype(int)
    df["R"] = df.xft + df.xbl + df.xfl + df.xbt
    df = df.sort_values("eag", ascending=False).reset_index(drop=True)
    nz = df.index[df.R > 0]
    if len(nz) == 0:
        return None
    df = df.loc[nz[0]:nz[-1]].reset_index(drop=True)
    n_genera = int((df.xft + df.xfl).sum())
    return df, n_genera


def score(df):
    R = df.R.values
    M = R.max()
    thr = PRE["edge_threshold_fraction_of_max"] * M
    above = R > thr
    idx = [i for i, a in enumerate(above) if a]
    contiguous = (idx[-1] - idx[0] + 1) == len(idx)
    peak_first = int(R.argmax())
    peak_last = int(len(R) - 1 - R[::-1].argmax())
    return {
        "n_bins": int(len(R)), "max_richness": int(M),
        "first_frac": float(R[0] / M), "last_frac": float(R[-1] / M),
        "low_start": bool(R[0] <= thr), "low_end": bool(R[-1] <= thr), "single_peak": bool(contiguous),
        "peak_position_frac": float((peak_first + peak_last) / 2 / max(len(R) - 1, 1)),
        "bins_rise": peak_first, "bins_fall": int(len(R) - 1 - peak_last),
        "first_bin": df.nam.iloc[0], "last_bin": df.nam.iloc[-1],
        "first_age_ma": float(df.eag.iloc[0]), "last_age_ma": float(df.lag.iloc[-1]),
        "series": ",".join(str(int(x)) for x in R),
    }


def main():
    rows = []
    for ht in PRE["higher_taxa"]:
        d = get("/taxa/list.json", {"base_name": ht, "rank": PRE["rank"], "extant": "no" if PRE["extinct_only"] else "all",
                                     "taxon_status": "accepted", "show": "app,size"})
        fams = [r for r in d.get("records", []) if r.get("noc", 0) > 0 and r.get("rnk") == "family"]
        print(ht, "extinct families with occurrences:", len(fams), flush=True)
        for f in fams:
            # cheap pre-filter on recorded duration: need at least ~6 stages (~30 Myr is too strict,
            # so only skip families whose whole recorded span is < 5 Myr)
            if f.get("fea") is None or f.get("lla") is None or (f["fea"] - f["lla"]) < 5:
                continue
            t = trajectory(f["oid"])
            if t is None:
                continue
            df, n_genera = t
            if n_genera < PRE["min_genera"] or len(df) < PRE["min_bins"]:
                continue
            s = score(df)
            # bins in which no genus of the family is recorded or ranges through (Lazarus gap)
            s["interior_zero_bins"] = int((df.R == 0).sum())
            s.update({"higher_taxon": ht, "family": f["nam"], "pbdb_id": f["oid"], "n_genera": n_genera,
                      "n_occurrences": int(df.noc.sum())})
            s["darwinian"] = s["low_start"] and s["low_end"] and s["single_peak"]
            rows.append(s)
            print(f"  {f['nam']}: bins={s['n_bins']} genera={n_genera} max={s['max_richness']} darwinian={s['darwinian']}", flush=True)
    fam = pd.DataFrame(rows).drop_duplicates("pbdb_id")
    fam.to_csv(os.path.join(DERIVED, "family_trajectories.csv"), index=False)
    n = len(fam)
    frac = float(fam.darwinian.mean()) if n else float("nan")
    # exact binomial 95% CI (Clopper-Pearson)
    from scipy.stats import beta
    k = int(fam.darwinian.sum())
    lo = float(beta.ppf(0.025, k, n - k + 1)) if k > 0 else 0.0
    hi = float(beta.ppf(0.975, k + 1, n - k)) if k < n else 1.0
    measured = {
        "value": round(frac, 4),
        "unit": "fraction of qualifying extinct families with low start, low end and a single peak",
        "n": n,
        "uncertainty": f"95% Clopper-Pearson CI [{lo:.3f}, {hi:.3f}]",
        "extra": {
            "n_darwinian": k,
            "frac_low_start": float(fam.low_start.mean()),
            "frac_low_end": float(fam.low_end.mean()),
            "frac_single_peak": float(fam.single_peak.mean()),
            "frac_peak_in_first_bin": float((fam.bins_rise == 0).mean()),
            "frac_peak_in_last_bin": float((fam.bins_fall == 0).mean()),
            "median_bins_rise": float(fam.bins_rise.median()),
            "median_bins_fall": float(fam.bins_fall.median()),
            "median_peak_position_frac": float(fam.peak_position_frac.median()),
            "median_n_bins": float(fam.n_bins.median()),
            "median_n_genera": float(fam.n_genera.median()),
            "n_families_with_interior_gap": int((fam.interior_zero_bins > 0).sum()),
            "per_higher_taxon": {ht: {"n": int((fam.higher_taxon == ht).sum()),
                                      "frac_darwinian": float(fam[fam.higher_taxon == ht].darwinian.mean())}
                                 for ht in PRE["higher_taxa"] if (fam.higher_taxon == ht).any()},
        },
    }
    if n < PRE["min_families"]:
        verdict = "inconclusive"
    elif frac >= PRE["support_threshold"]:
        verdict = "supports"
    elif frac < PRE["refute_threshold"]:
        verdict = "refutes"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    pd.DataFrame(FETCH_LOG).to_csv(os.path.join(DERIVED, "fetch_log.csv.gz"), index=False, compression="gzip")
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
