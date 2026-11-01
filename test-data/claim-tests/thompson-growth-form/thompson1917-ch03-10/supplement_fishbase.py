#!/usr/bin/env python3
"""Supplement, not part of the pre-registered test: published von Bertalanffy growth parameters
from FishBase for the species in derived/species_model_comparison.csv.

For each qualifying DATRAS species, compares the fitted Linf and K with every FishBase popgrowth
fit (all length types, and total-length fits only, since DATRAS measures total length), and the
DATRAS mean length at the oldest age with FishBase's maximum recorded length. Reads the FishBase
v25.04 rows vendored under test-data/organisms/claim-tests/*/files/lifebase/ by
test-data/organisms/claim-tests/fetch.py. Writes derived/supplement_fishbase_growth.json.
Standard library only.
"""
import csv, glob, json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LIFEBASE = glob.glob(os.path.join(REPO, "test-data", "organisms", "claim-tests", "*", "files", "lifebase", "*.json"))


def q(xs):
    if len(xs) < 4:
        return None
    a = statistics.quantiles(xs, n=4)
    return [round(a[0], 3), round(a[2], 3)]


def main():
    fb = {}
    for p in LIFEBASE:
        d = json.load(open(p))
        fb.setdefault(d["accepted_name"], d)
    out = {}
    for r in csv.DictReader(open(os.path.join(HERE, "derived", "species_model_comparison.csv"))):
        name = r["Species"]
        d = fb.get(name)
        if not d:
            out[name] = {"fishbase": None}
            continue
        g = [x for x in d["tables"].get("popgrowth", []) if x.get("Loo") and x.get("K")]
        tl = [x for x in g if (x.get("Type") or "").upper() == "TL"]
        loo, loo_tl, k = sorted(float(x["Loo"]) for x in g), sorted(float(x["Loo"]) for x in tl), sorted(float(x["K"]) for x in g)
        sp = (d["tables"].get("species") or [{}])[0]
        linf, kk, lold = float(r["vb_Linf"]), float(r["vb_K"]), float(r["L_at_oldest_cm"])
        out[name] = {
            "datras_vb_Linf_cm": linf, "datras_vb_K": kk, "datras_L_oldest_cm": lold, "datras_dAIC_plateau_minus_vb": float(r["dAIC_plateau_minus_vb"]),
            "fishbase_n_growth_fits": len(g), "fishbase_n_growth_fits_TL": len(tl),
            "fishbase_Loo_median_cm": round(statistics.median(loo), 2) if loo else None, "fishbase_Loo_iqr_cm": q(loo),
            "fishbase_Loo_TL_median_cm": round(statistics.median(loo_tl), 2) if loo_tl else None,
            "fishbase_K_median": round(statistics.median(k), 3) if k else None, "fishbase_K_iqr": q(k),
            "datras_Linf_percentile_in_fishbase": round(sum(x <= linf for x in loo) / len(loo), 3) if loo else None,
            "fishbase_max_length_cm": sp.get("Length"), "fishbase_max_length_type": sp.get("LTypeMaxM"),
            "max_length_over_fishbase_Loo_median": round(sp["Length"] / statistics.median(loo), 3) if sp.get("Length") and loo else None,
        }
    rows = [v for v in out.values() if v.get("fishbase_n_growth_fits")]
    summary = {
        "species": len(out), "species_with_fishbase_growth": len(rows),
        "fishbase_growth_fits": sum(v["fishbase_n_growth_fits"] for v in rows),
        "species_datras_Linf_within_fishbase_iqr": sum(1 for v in rows if v["fishbase_Loo_iqr_cm"] and v["fishbase_Loo_iqr_cm"][0] <= v["datras_vb_Linf_cm"] <= v["fishbase_Loo_iqr_cm"][1]),
        "species_max_length_exceeds_median_Loo": sum(1 for v in rows if (v["max_length_over_fishbase_Loo_median"] or 0) > 1),
        "note": "Published (Linf, K) pairs presuppose the von Bertalanffy form, so they cannot discriminate it from a plateau model; they show whether the DATRAS fits sit inside the range of independent estimates and how far record sizes exceed the typical asymptote.",
    }
    json.dump({"claim_id": "thompson1917-ch03-10", "kind": "supplement", "affects_verdict": False,
               "source": "FishBase v25.04 (rfishbase parquet snapshot) popgrowth and species tables; see test-data/organisms/claim-tests/*/datasets/fishbase-v25-04-*.json",
               "summary": summary, "per_species": out},
              open(os.path.join(HERE, "derived", "supplement_fishbase_growth.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    print(f"{'species':28} {'DATRAS Linf':>11} {'FB n':>5} {'FB Loo median [IQR]':>26} {'pctile':>7} {'Lmax/Loo':>9}")
    for n, v in out.items():
        if v.get("fishbase_n_growth_fits"):
            print(f"{n:28} {v['datras_vb_Linf_cm']:11.1f} {v['fishbase_n_growth_fits']:5d} {str(v['fishbase_Loo_median_cm'])+' '+str(v['fishbase_Loo_iqr_cm']):>26} {str(v['datras_Linf_percentile_in_fishbase']):>7} {str(v['max_length_over_fishbase_Loo_median']):>9}")
        else:
            print(f"{n:28} no FishBase growth fits")


if __name__ == "__main__":
    main()
