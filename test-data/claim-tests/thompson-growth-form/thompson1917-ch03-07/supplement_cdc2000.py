#!/usr/bin/env python3
"""Supplement, not part of the pre-registered test: the curve criteria of result.json applied to
an independent human growth reference, the CDC 2000 growth charts (Kuczmarski et al. 2002, built
from NHES/NHANES 1963-1994 and other US data, so disjoint from the NHANES 2007-2018 sample).

Monthly medians (LMS M parameter) at the month midpoint: recumbent length and weight from the
infant tables (0-23 months), stature and weight from the 2-20 yr tables (24-239 months). Applies
analysis.py's age-median-curve slope and D(p) = mean |W/W19 - (H/H19)^p| with the 19-yr reference
as the mean of months 228-239. "Pooled" averages the boys' and girls' medians month by month.

Downloads the four CSVs into data/ (sha256 recorded) and writes derived/supplement_cdc2000.json.
Standard library only.
"""
import csv, hashlib, json, math, os, urllib.request, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://www.cdc.gov/growthcharts/data/zscore/"
FILES = {"len_inf": "lenageinf.csv", "wt_inf": "wtageinf.csv", "stat": "statage.csv", "wt": "wtage.csv"}


def fetch(name):
    dest = os.path.join(HERE, "data", f"cdc2000_{name}")
    if not os.path.exists(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        req = urllib.request.Request(BASE + name, headers={"User-Agent": "curl/8.7.1", "Accept": "*/*"})
        body = urllib.request.urlopen(req, timeout=60).read()
        open(dest, "wb").write(body)
    body = open(dest, "rb").read()
    return dest, {"download_url": BASE + name, "byte_size": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                  "retrieved_at": dt.datetime.fromtimestamp(os.path.getmtime(dest), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def medians(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        if not r.get("Sex", "").strip().isdigit():
            continue  # the CDC files repeat the header row mid-file
        out[(int(r["Sex"]), float(r["Agemos"]))] = float(r["M"])
    return out


def ols(x, y):
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((a - mx) ** 2 for a in x)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    syy = sum((b - my) ** 2 for b in y)
    slope = sxy / sxx
    resid = sum((b - my - slope * (a - mx)) ** 2 for a, b in zip(x, y))
    se = math.sqrt(resid / (n - 2) / sxx)
    return {"ols_slope": slope, "ols_slope_ci95": [slope - 1.96 * se, slope + 1.96 * se], "r2": sxy ** 2 / (sxx * syy),
            "rma_slope": math.sqrt(syy / sxx), "n": n}


def analyse(H, W):
    out = {"age_median_curve": ols([math.log10(h) for h in H], [math.log10(w) for w in W])}
    h19, w19 = sum(H[228:240]) / 12, sum(W[228:240]) / 12
    Hn, Wn = [h / h19 for h in H], [w / w19 for w in W]
    D = lambda p: sum(abs(w - h ** p) for h, w in zip(Hn, Wn)) / len(Hn)
    ps = [1 + i / 100 for i in range(401)]
    best = min(ps, key=D)
    out["curve_shape"] = {"D_by_exponent": {str(p): D(p) for p in (1, 2, 3, 4)}, "D3_over_D1": D(3) / D(1),
                          "best_exponent": round(best, 2), "D_best": D(best),
                          "reference_19yr_median_height_cm": h19, "reference_19yr_median_weight_kg": w19}
    c = out["age_median_curve"]["ols_slope"]
    out["criteria"] = {"curve_slope_in_2.5_3.5": 2.5 <= c <= 3.5, "D3_over_D1_le_0.5": out["curve_shape"]["D3_over_D1"] <= 0.5}
    return out


def main():
    paths, dists = {}, []
    for k, f in FILES.items():
        paths[k], d = fetch(f)
        dists.append(d)
    m = {k: medians(p) for k, p in paths.items()}
    curves = {}
    for sex, label in ((1, "boys"), (2, "girls")):
        H, W = [], []
        for mo in range(240):
            age = mo + 0.5
            if mo < 24:
                H.append(m["len_inf"][(sex, age)]), W.append(m["wt_inf"][(sex, age)])
            else:
                H.append(m["stat"][(sex, age)]), W.append(m["wt"][(sex, age)])
        curves[label] = (H, W)
    curves["pooled"] = tuple([(a + b) / 2 for a, b in zip(curves["boys"][i], curves["girls"][i])] for i in (0, 1))
    res = {k: analyse(*v) for k, v in curves.items()}
    nh = json.load(open(os.path.join(HERE, "result.json")))["measured"]["extra"]
    comparison = {k: {"nhanes_curve_slope": nh[k]["age_median_curve"]["ols_slope"], "cdc2000_curve_slope": res[k]["age_median_curve"]["ols_slope"],
                      "nhanes_D3_over_D1": nh[k]["curve_shape"]["D3_over_D1"], "cdc2000_D3_over_D1": res[k]["curve_shape"]["D3_over_D1"],
                      "nhanes_best_exponent": nh[k]["curve_shape"]["best_exponent"], "cdc2000_best_exponent": res[k]["curve_shape"]["best_exponent"]}
                  for k in ("pooled", "boys", "girls")}
    out = {"claim_id": "thompson1917-ch03-07", "kind": "supplement", "affects_verdict": False,
           "dataset": {"id": "cdc-2000-growth-charts-lms", "name": "CDC 2000 growth charts, LMS parameters (length/stature- and weight-for-age, infants and 2-20 yr)",
                       "landing_url": "https://www.cdc.gov/growthcharts/cdc-data-files.htm", "license": "US Government public domain",
                       "citation": "Kuczmarski RJ, et al. (2002) 2000 CDC Growth Charts for the United States: methods and development. Vital Health Stat 11(246).",
                       "files": dists},
           "results": res, "comparison_with_result_json": comparison}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "derived", "supplement_cdc2000.json"), "w"), indent=1)
    print(json.dumps(comparison, indent=1))


if __name__ == "__main__":
    main()
