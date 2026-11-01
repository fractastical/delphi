"""Test of hamilton-senescence on COMADRE age-classified matrix population models of wild, unmanipulated animal populations.

Reads data/comadre.json (written by fetch.py). Writes derived/species_trends.csv and derived/summary.json.
Primary analysis excludes class Aves (held out); bird species are reported separately and are not part of the verdict.
"""
import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "comadre.json")
DERIVED = os.path.join(HERE, "derived")


def qualifies(m):
    U, F = np.array(m["matU"], dtype=float), np.array(m["matF"], dtype=float)
    if U.ndim != 2 or U.shape[0] != U.shape[1] or U.shape != F.shape or U.shape[0] < 5:
        return None
    if not (np.isfinite(U).all() and np.isfinite(F).all()):
        return None
    if m.get("MatrixCriteriaAge") != "Yes" or m.get("MatrixSplit") != "Divided":
        return None
    if m.get("MatrixComposite") not in ("Individual", "Mean") or m.get("MatrixTreatment") != "Unmanipulated" or m.get("MatrixCaptivity") != "W":
        return None
    return U, F


def species_trend(mats):
    """mats: list of (U, F) with the same dimension. Element-wise mean, then Spearman of mortality on age over mature classes."""
    U = np.mean([u for u, _ in mats], axis=0)
    F = np.mean([f for _, f in mats], axis=0)
    n = U.shape[0]
    surv = U.sum(axis=0)
    fert = F.sum(axis=0)
    classes = list(range(n))
    plus_group = U[n - 1, n - 1] > 0
    if plus_group:
        classes = classes[:-1]
    mature = [a for a in classes if fert[a] > 0]
    if len(mature) < 4:
        return None
    mort = 1 - surv[mature]
    if np.ptp(mort) == 0:  # constant adult mortality: no rise, correlation undefined -> recorded as 0
        rho, p = 0.0, 1.0
    else:
        rho, p = stats.spearmanr(np.array(mature, dtype=float), mort)
    return {"dim": n, "plus_group_dropped": bool(plus_group), "n_mature_classes": len(mature), "rho": float(rho), "p": float(p),
            "mortality_first_mature": float(mort[0]), "mortality_last_mature": float(mort[-1]), "n_matrices": len(mats)}


def main():
    os.makedirs(DERIVED, exist_ok=True)
    db = json.load(open(DATA, encoding="utf-8"))
    by_species = defaultdict(lambda: defaultdict(list))
    meta = {}
    for m in db["matrices"]:
        q = qualifies(m)
        if q is None:
            continue
        sp = m["SpeciesAccepted"]
        by_species[sp][q[0].shape[0]].append(q)
        meta[sp] = {"Class": m.get("Class"), "Order": m.get("Order")}
    rows = []
    for sp, dims in by_species.items():
        # Use the most common dimension for the species (ties -> larger dimension).
        dim = sorted(dims, key=lambda k: (len(dims[k]), k), reverse=True)[0]
        t = species_trend(dims[dim])
        if t is None:
            continue
        rows.append({"species": sp, **meta[sp], **t})
    df = pd.DataFrame(rows)
    df["held_out"] = df["Class"] == "Aves"
    main_df = df[~df["held_out"]]
    birds = df[df["held_out"]]
    n = len(main_df)
    frac_rising = float((main_df["rho"] > 0).mean()) if n else None
    mean_rho = float(main_df["rho"].mean()) if n else None
    if n < 15:
        verdict = "inconclusive"
    elif frac_rising >= 0.8 and mean_rho > 0.3:
        verdict = "supports"
    elif frac_rising < 0.5:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {
        "comadre_version": db["version"].get("Version"), "n_matrices_in_db": db["n"],
        "n_species_qualifying_non_aves": int(n), "fraction_species_rising_adult_mortality": frac_rising, "mean_spearman_rho": mean_rho,
        "median_spearman_rho": float(main_df["rho"].median()) if n else None,
        "n_species_rho_positive": int((main_df["rho"] > 0).sum()), "n_species_rho_negative": int((main_df["rho"] < 0).sum()), "n_species_rho_zero": int((main_df["rho"] == 0).sum()),
        "n_species_significant_rise_p05": int(((main_df["rho"] > 0) & (main_df["p"] < 0.05)).sum()),
        "n_species_significant_fall_p05": int(((main_df["rho"] < 0) & (main_df["p"] < 0.05)).sum()),
        "classes_in_main": main_df["Class"].value_counts().to_dict(),
        "holdout_aves": {"n_bird_species": int(len(birds)), "note": "class Aves excluded from the verdict at the holdout thread's request; scored only with --exam"},
        "verdict": verdict,
    }
    if "--exam" in sys.argv[1:]:
        summary["holdout_aves"]["fraction_rising"] = float((birds["rho"] > 0).mean()) if len(birds) else None
        summary["holdout_aves"]["bird_species"] = birds[["species", "rho", "p", "n_mature_classes"]].to_dict("records")
    else:
        df = df[~df["held_out"]]  # bird rows are not written to derived/ unless the exam is run
    df.sort_values(["held_out", "Class", "species"]).to_csv(os.path.join(DERIVED, "species_trends.csv"), index=False)
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
