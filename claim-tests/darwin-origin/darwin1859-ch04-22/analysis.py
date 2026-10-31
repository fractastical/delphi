#!/usr/bin/env python3
"""Test darwin1859-ch04-22: floras gain proportionally more new genera than new species by naturalisation.

Data: Kew World Checklist of Vascular Plants (WCVP) zip, names + distribution tables.
Usage: python3 analysis.py [--write-result]
Writes derived/measured.json, derived/files.json, derived/areas.csv.
"""
import hashlib
import json
import os
import sys
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

WCVP_URL = "https://sftp.kew.org/pub/data-repositories/WCVP/wcvp.zip"
MIN_NATIVE_SP = 100
MIN_INTRO_SP = 20
N_DRAWS = 200
SEED = 20261031


def fetch_wcvp():
    path = os.path.join(DATA, "wcvp.zip")
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        with requests.get(WCVP_URL, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    info = {"download_url": WCVP_URL, "retrieved_at": open(meta).read().strip(),
            "byte_size": os.path.getsize(path), "sha256": h.hexdigest()}
    with zipfile.ZipFile(path) as z:
        z.extractall(DATA)
    return info


def main():
    write_result = "--write-result" in sys.argv
    finfo = fetch_wcvp()

    names = pd.read_csv(os.path.join(DATA, "wcvp_names.csv"), sep="|", quoting=3, dtype=str,
                        usecols=["plant_name_id", "taxon_rank", "taxon_status", "family", "genus_hybrid",
                                 "genus", "species_hybrid", "species"], encoding="utf-8")
    sp = names[(names.taxon_rank == "Species") & (names.taxon_status == "Accepted")
               & names.genus_hybrid.isna() & names.species_hybrid.isna()].copy()
    sp = sp[["plant_name_id", "genus", "family"]]
    n_species_total = len(sp)

    dist = pd.read_csv(os.path.join(DATA, "wcvp_distribution.csv"), sep="|", quoting=3, dtype=str,
                       usecols=["plant_name_id", "continent", "region", "area_code_l3", "area", "introduced",
                                "extinct", "location_doubtful"], encoding="utf-8")
    dist = dist[dist.location_doubtful == "0"]
    dist = dist.merge(sp, on="plant_name_id", how="inner")
    dist["introduced"] = dist.introduced.astype(int)

    # A species that is both native and introduced to the same area counts as native there.
    nat = dist[dist.introduced == 0][["area_code_l3", "plant_name_id", "genus"]].drop_duplicates()
    intro = dist[dist.introduced == 1][["area_code_l3", "plant_name_id", "genus"]].drop_duplicates()
    nat_keys = set(zip(nat.area_code_l3, nat.plant_name_id))
    intro = intro[[(a, p) not in nat_keys for a, p in zip(intro.area_code_l3, intro.plant_name_id)]]

    area_meta = dist[["area_code_l3", "area", "region", "continent"]].drop_duplicates("area_code_l3").set_index("area_code_l3")
    genus_of = dict(zip(sp.plant_name_id, sp.genus))
    all_species = np.array(sp.plant_name_id)
    rng = np.random.default_rng(SEED)

    rows = []
    for area, g in nat.groupby("area_code_l3"):
        nat_sp = set(g.plant_name_id)
        nat_gen = set(g.genus)
        gi = intro[intro.area_code_l3 == area]
        int_sp = set(gi.plant_name_id)
        if len(nat_sp) < MIN_NATIVE_SP or len(int_sp) < MIN_INTRO_SP:
            continue
        int_gen = set(gi.genus)
        new_gen = int_gen - nat_gen
        r_sp = len(int_sp) / len(nat_sp)
        r_gen = len(new_gen) / len(nat_gen)
        # Null: draw the same number of species at random from species not native to this area.
        pool = np.array([s for s in all_species if s not in nat_sp])
        null_new = []
        for _ in range(N_DRAWS):
            draw = rng.choice(pool, size=len(int_sp), replace=False)
            null_new.append(len({genus_of[s] for s in draw} - nat_gen))
        null_new = np.array(null_new)
        rows.append({
            "area_code_l3": area, "area": area_meta.loc[area, "area"], "region": area_meta.loc[area, "region"],
            "continent": area_meta.loc[area, "continent"],
            "native_species": len(nat_sp), "native_genera": len(nat_gen),
            "introduced_species": len(int_sp), "introduced_genera": len(int_gen), "new_genera": len(new_gen),
            "r_sp": r_sp, "r_gen": r_gen, "ratio_gen_over_sp": r_gen / r_sp,
            "null_new_genera_mean": float(null_new.mean()), "null_new_genera_sd": float(null_new.std(ddof=1)),
            "null_r_gen_mean": float(null_new.mean() / len(nat_gen)),
            "obs_over_null_new_genera": len(new_gen) / null_new.mean() if null_new.mean() > 0 else None,
        })
    df = pd.DataFrame(rows).sort_values("area_code_l3")
    df.to_csv(os.path.join(DERIVED, "areas.csv"), index=False, float_format="%.5f")

    n = len(df)
    frac_gt = float((df.r_gen > df.r_sp).mean())
    med_ratio = float(df.ratio_gen_over_sp.median())
    frac_null_gt = float((df.null_r_gen_mean > df.r_sp).mean())
    frac_obs_gt_null = float((df.new_genera > df.null_new_genera_mean).mean())
    med_obs_over_null = float(df.obs_over_null_new_genera.median())

    if frac_gt >= 0.80 and med_ratio >= 1.25:
        verdict = "supports"
    elif frac_gt <= 0.50 or med_ratio <= 1.0:
        verdict = "refutes"
    else:
        verdict = "mixed"

    def pick(code):
        s = df[df.area_code_l3 == code]
        return None if s.empty else {k: (float(v) if isinstance(v, (np.floating, float)) else (int(v) if isinstance(v, (np.integer,)) else v))
                                     for k, v in s.iloc[0].to_dict().items()}

    measured = {
        "value": round(frac_gt, 4),
        "unit": "fraction of qualifying level-3 areas with r_gen > r_sp",
        "n": int(n),
        "uncertainty": f"95% Wilson CI {wilson(int((df.r_gen > df.r_sp).sum()), n)}",
        "extra": {
            "wcvp_version": "16 (extracted 2026-06-04, per README_WCVP.xlsx in the zip)",
            "accepted_non_hybrid_species_total": int(n_species_total),
            "median_r_gen_over_r_sp": round(med_ratio, 4),
            "iqr_r_gen_over_r_sp": [round(float(df.ratio_gen_over_sp.quantile(q)), 4) for q in (0.25, 0.75)],
            "median_r_sp": round(float(df.r_sp.median()), 4),
            "median_r_gen": round(float(df.r_gen.median()), 4),
            "areas_with_r_gen_gt_r_sp": int((df.r_gen > df.r_sp).sum()),
            "null_model": {
                "description": f"{N_DRAWS} random draws per area of the observed number of introduced species from all accepted species not native to the area; seed {SEED}",
                "fraction_of_areas_where_null_r_gen_gt_r_sp": round(frac_null_gt, 4),
                "fraction_of_areas_with_observed_new_genera_above_null_mean": round(frac_obs_gt_null, 4),
                "median_observed_over_null_new_genera": round(med_obs_over_null, 4),
            },
            "by_continent_fraction_r_gen_gt_r_sp": {c: round(float((s.r_gen > s.r_sp).mean()), 3) for c, s in df.groupby("continent")},
            "examples": {"Great Britain (GRB)": pick("GRB"), "Illinois (ILL)": pick("ILL"), "New York (NWY)": pick("NWY"), "Hawaii (HAW)": pick("HAW")},
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump([finfo], open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        res["datasets"][0]["files"] = [finfo]
        res["datasets"][0]["version"] = "16 (2026-06-04)"
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return f"[{(centre - half) / denom:.3f}, {(centre + half) / denom:.3f}]"


if __name__ == "__main__":
    main()
