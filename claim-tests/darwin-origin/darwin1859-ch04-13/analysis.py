#!/usr/bin/env python3
"""Test darwin1859-ch04-13: trees have separate sexes more often than other (non-woody) plants.

Data: GIFT public API (traits 3.4.1 sexual system, 1.2.1 growth form; species; taxonomy).
Usage: python3 analysis.py [--write-result]
"""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

API = "https://gift.uni-goettingen.de/api/extended/index.php"
PAGE = 10000
FILES = []


def get_json(url, cache_name, role):
    path = os.path.join(DATA, cache_name)
    meta = path + ".meta"
    if not (os.path.exists(path) and os.path.exists(meta)):
        for attempt in range(6):
            try:
                r = requests.get(url, timeout=600)
                if r.status_code == 200 and r.content.strip().startswith(b"["):
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
    return json.loads(content.decode("utf-8"))


def trait(trait_id, label):
    rows, start = [], 0
    while True:
        d = get_json(f"{API}?query=traits&traitid={trait_id}&biasref=1&biasderiv=1&startat={start}",
                     f"trait_{trait_id}_{start}.json", f"GIFT trait {trait_id} ({label}), rows from {start}")
        rows += d
        if len(d) < PAGE:
            break
        start += PAGE
    return pd.DataFrame(rows)


def main():
    write_result = "--write-result" in sys.argv
    sex = trait("3.4.1", "sexual system")
    gf = trait("1.2.1", "growth form")
    species = pd.DataFrame(get_json(f"{API}?query=species", "species.json", "GIFT species list"))
    tax = pd.DataFrame(get_json(f"{API}?query=taxonomy", "taxonomy.json", "GIFT taxonomy"))

    # Nested-set taxonomy: an ancestor has lft < lft_genus and rgt > rgt_genus.
    gen = tax[tax.taxon_lvl == "genus"].set_index("taxon_ID")
    orders = tax[tax.taxon_lvl == "order"]
    angio = tax[tax.taxon_name == "Angiospermae"].iloc[0]
    order_of = {}
    for gid, g in gen.iterrows():
        o = orders[(orders.lft < g.lft) & (orders.rgt > g.rgt)]
        order_of[gid] = o.taxon_name.iloc[0] if len(o) else None
    is_angio = {gid: (g.lft > angio.lft and g.rgt < angio.rgt) for gid, g in gen.iterrows()}

    species["order"] = species.genus_ID.map(order_of)
    species["angiosperm"] = species.genus_ID.map(is_angio)
    df = sex[["work_ID", "trait_value", "agreement"]].rename(columns={"trait_value": "sexual_system", "agreement": "agreement_sex"})
    df = df.merge(gf[["work_ID", "trait_value"]].rename(columns={"trait_value": "growth_form"}), on="work_ID", how="inner")
    df = df.merge(species[["work_ID", "work_species", "work_genus", "order", "angiosperm"]], on="work_ID", how="left")
    n_joined_all = len(df)
    df = df[(df.angiosperm == True) & df.growth_form.isin(["tree", "shrub", "herb"]) & df.sexual_system.isin(["dioecious", "monoecious", "bisexual"])]
    df["separate_sexes"] = df.sexual_system.isin(["dioecious", "monoecious"])
    df["dioecious"] = df.sexual_system == "dioecious"
    df.to_csv(os.path.join(DERIVED, "species_traits.csv"), index=False)

    def table(a, b, col="separate_sexes"):
        A, B = df[df.growth_form == a], df[df.growth_form == b]
        t = [[int(A[col].sum()), int((~A[col]).sum())], [int(B[col].sum()), int((~B[col]).sum())]]
        odds, p = stats.fisher_exact(t)
        return {"table_[[a_yes,a_no],[b_yes,b_no]]": t, "odds_ratio": float(odds), "fisher_p": float(p),
                f"prop_{a}": t[0][0] / sum(t[0]), f"prop_{b}": t[1][0] / sum(t[1]), "n": int(sum(t[0]) + sum(t[1]))}

    tree_herb = table("tree", "herb")
    tree_shrub = table("tree", "shrub")
    tree_herb_dioecy = table("tree", "herb", "dioecious")
    props = df.groupby("growth_form").agg(n=("separate_sexes", "size"), prop_separate=("separate_sexes", "mean"), prop_dioecious=("dioecious", "mean")).round(4)

    rows = []
    for o, sub in df.groupby("order"):
        t, h = sub[sub.growth_form == "tree"], sub[sub.growth_form == "herb"]
        if len(t) >= 10 and len(h) >= 10:
            rows.append({"order": o, "n_trees": len(t), "n_herbs": len(h), "prop_separate_trees": round(t.separate_sexes.mean(), 4),
                         "prop_separate_herbs": round(h.separate_sexes.mean(), 4), "trees_higher": bool(t.separate_sexes.mean() > h.separate_sexes.mean())})
    orders_df = pd.DataFrame(rows)
    orders_df.to_csv(os.path.join(DERIVED, "orders.csv"), index=False)
    frac_orders = float(orders_df.trees_higher.mean()) if len(orders_df) else float("nan")
    sign_p = float(stats.binomtest(int(orders_df.trees_higher.sum()), len(orders_df), 0.5, alternative="greater").pvalue) if len(orders_df) else None

    cond1 = tree_herb["odds_ratio"] >= 1.5 and tree_herb["fisher_p"] < 0.01
    cond2 = len(orders_df) > 0 and frac_orders >= 2 / 3
    if cond1 and cond2:
        verdict = "supports"
    elif tree_herb["odds_ratio"] <= 1.0 or tree_herb["fisher_p"] >= 0.05 or (len(orders_df) > 0 and frac_orders < 0.5):
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": round(tree_herb["odds_ratio"], 3),
        "unit": "odds ratio of separate sexes (dioecious or monoecious) in trees versus herbs, angiosperms in GIFT",
        "n": tree_herb["n"],
        "uncertainty": f"Fisher exact p = {tree_herb['fisher_p']:.2e}",
        "extra": {
            "n_species_with_sexual_system": int(len(sex)), "n_species_with_growth_form": int(len(gf)), "n_joined_before_filters": n_joined_all,
            "n_angiosperms_analysed": int(len(df)),
            "proportions_by_growth_form": props.to_dict(orient="index"),
            "tree_vs_herb": tree_herb, "tree_vs_shrub": tree_shrub, "tree_vs_herb_dioecy_only": tree_herb_dioecy,
            "orders_with_ge_10_trees_and_herbs": int(len(orders_df)), "fraction_of_orders_trees_higher": round(frac_orders, 4),
            "sign_test_p_orders": sign_p, "orders": rows,
            "conditions": {"OR_ge_1.5_p_lt_0.01": bool(cond1), "trees_higher_in_ge_two_thirds_of_orders": bool(cond2)},
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, default=float)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2, default=float))

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = json.loads(json.dumps(measured, default=float))
        for ds in res["datasets"]:
            fl = [f for f in FILES if ("taxonomy" in f["download_url"]) == (ds["id"] == "gift-api-taxonomy")]
            ds["files"] = [{k: v for k, v in f.items() if k != "role"} | {"note": f["role"]} for f in fl]
            ds["version"] = f"GIFT public API, retrieved {fl[0]['retrieved_at'][:10]}"
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


if __name__ == "__main__":
    main()
