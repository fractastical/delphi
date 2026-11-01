#!/usr/bin/env python3
"""Supplement, not part of the pre-registered test: per-species length-weight exponents from
FishBase for the fish measured in result.json.

Reads the FishBase v25.04 rows vendored in
test-data/organisms/claim-tests/lean-tested/files/lifebase/<slug>.json (built by
test-data/organisms/claim-tests/fetch.py) and, for each species, compares
  - b from the DATRAS individual fits in result.json (measured.extra.per_taxon),
  - every published population fit W = aL^b in FishBase's poplw table,
  - FishBase's hierarchical Bayesian estimate of b (Froese, Thorson & Reyes 2014, estimate table).
W = kL^3 with constant k means b = 3; Thompson's claim is that k drifts as form changes.

Writes derived/supplement_fishbase_lw.json. Standard library only.
"""
import json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LIFEBASE = os.path.join(REPO, "test-data", "organisms", "claim-tests", "lean-tested", "files", "lifebase")
ISO_BAND = 0.1  # |b - 3| above this counts as allometric, the same threshold result.json reports


def main():
    res = json.load(open(os.path.join(HERE, "result.json")))
    per_taxon = res["measured"]["extra"]["per_taxon"]
    out, rows = {}, []
    for name, t in per_taxon.items():
        if "(" in name:
            continue  # genus-level and jellyfish entries; SeaLifeBase has no LW fits for the jellyfish
        slug = name.lower().replace(" ", "-")
        path = os.path.join(LIFEBASE, f"{slug}.json")
        if not os.path.exists(path):
            continue
        fb = json.load(open(path))["tables"]
        fits = [r for r in fb.get("poplw", []) if r.get("b")]
        bs = sorted(float(r["b"]) for r in fits)
        est = (fb.get("estimate") or [{}])[0]
        bb, sd = est.get("b"), est.get("sd_b")
        ci = [round(bb - 1.96 * sd, 3), round(bb + 1.96 * sd, 3)] if bb and sd else None
        q = statistics.quantiles(bs, n=4) if len(bs) >= 4 else None
        out[name] = {
            "datras_b": t["b"], "datras_b_ci95": t["b_ci95"], "datras_variable_k": t["variable_k"], "datras_n": t["n"],
            "fishbase_n_fits": len(bs),
            "fishbase_b_median": round(statistics.median(bs), 3) if bs else None,
            "fishbase_b_iqr": [round(q[0], 3), round(q[2], 3)] if q else None,
            "fishbase_b_range": [bs[0], bs[-1]] if bs else None,
            "fishbase_frac_fits_allometric": round(sum(abs(b - 3) > ISO_BAND for b in bs) / len(bs), 3) if bs else None,
            "fishbase_frac_fits_above_3": round(sum(b > 3 for b in bs) / len(bs), 3) if bs else None,
            "bayes_b": round(bb, 3) if bb else None, "bayes_b_ci95": ci,
            "bayes_excludes_3": (ci[0] > 3 or ci[1] < 3) if ci else None,
            "datras_within_fishbase_iqr": (q[0] <= t["b"] <= q[2]) if q else None,
            "fits": [{k: r.get(k) for k in ("a", "b", "LengthMin", "LengthMax", "Number", "Type", "Sex", "Locality", "C_Code", "CoeffDetermination", "PopLWRef")} for r in fits],
        }
        rows.append(out[name])
    with_ci = [r for r in rows if r["bayes_excludes_3"] is not None]
    summary = {
        "species": len(rows),
        "fishbase_fits": sum(r["fishbase_n_fits"] for r in rows),
        "species_bayes_ci_excludes_3": sum(r["bayes_excludes_3"] for r in with_ci),
        "species_with_bayes_ci": len(with_ci),
        "species_datras_variable_k": sum(r["datras_variable_k"] for r in rows),
        "species_datras_b_within_fishbase_iqr": sum(bool(r["datras_within_fishbase_iqr"]) for r in rows),
        "pooled_frac_fits_allometric": round(sum(r["fishbase_frac_fits_allometric"] * r["fishbase_n_fits"] for r in rows) / max(1, sum(r["fishbase_n_fits"] for r in rows)), 3),
        "note": "b is a single exponent per fit; a drifting k within one fit (what result.json measures) is not visible in published (a, b) pairs, so this supplement checks only whether populations depart from b = 3.",
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    json.dump({"claim_id": res["claim_id"], "kind": "supplement", "affects_verdict": False,
               "source": "FishBase v25.04 (rfishbase parquet snapshot), poplw and estimate tables; see test-data/organisms/claim-tests/lean-tested/datasets/fishbase-v25-04-lean-tested.json",
               "summary": summary, "per_species": out},
              open(os.path.join(HERE, "derived", "supplement_fishbase_lw.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    print(f"{'species':28} {'DATRAS b':>9} {'FB n':>5} {'FB median':>9} {'FB IQR':>15} {'Bayes b [95%]':>22}")
    for n, r in out.items():
        print(f"{n:28} {r['datras_b']:9.3f} {r['fishbase_n_fits']:5d} {str(r['fishbase_b_median']):>9} {str(r['fishbase_b_iqr']):>15} {str(r['bayes_b'])+' '+str(r['bayes_b_ci95']):>22}")


if __name__ == "__main__":
    main()
