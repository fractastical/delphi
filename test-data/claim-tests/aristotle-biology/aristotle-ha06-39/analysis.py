#!/usr/bin/env python3
"""Test aristotle-ha06-39: bear cubs are the smallest newborns relative to the mother."""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

URL = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
MARSUPIAL_ORDERS = {
    "Diprotodontia", "Dasyuromorphia", "Peramelemorphia", "Didelphimorphia",
    "Microbiotheria", "Notoryctemorphia", "Paucituberculata",
}


def fetch():
    path = os.path.join(DATA, "PanTHERIA_1-0_WR05_Aug2008.txt")
    meta = path + ".retrieved"
    if not (os.path.exists(path) and os.path.exists(meta)):
        r = requests.get(URL, timeout=180)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    return path, {
        "download_url": URL,
        "retrieved_at": open(meta).read().strip(),
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def pos(series):
    s = pd.to_numeric(series, errors="coerce")
    s = s.where(s > 0)
    return s


def main():
    path, file_meta = fetch()
    df = pd.read_csv(path, sep="\t", low_memory=False)
    adult = pos(df["5-1_AdultBodyMass_g"])
    neonate = pos(df["5-3_NeonateBodyMass_g"])
    eye = pos(df["2-1_AgeatEyeOpening_d"])
    use = df.loc[adult.notna() & neonate.notna()].copy()
    use["adult_g"] = adult.loc[use.index]
    use["neonate_g"] = neonate.loc[use.index]
    use["ratio"] = use["neonate_g"] / use["adult_g"]
    use["eye_d"] = eye.reindex(use.index)
    n_species = int(len(use))

    def one(binomial):
        rows = use[use["MSW05_Binomial"] == binomial]
        if rows.empty:
            return None
        return rows.iloc[0]

    bear = one("Ursus arctos")
    mouse = one("Mus musculus")
    weasel = one("Mustela nivalis")
    # Adult masses are needed even when neonate mass is missing, so look up adults on the full table.
    def adult_of(binomial):
        rows = df[df["MSW05_Binomial"] == binomial]
        if rows.empty:
            return None
        val = pos(rows["5-1_AdultBodyMass_g"]).iloc[0]
        return None if pd.isna(val) else float(val)

    mouse_adult = adult_of("Mus musculus")
    weasel_adult = adult_of("Mustela nivalis")

    reason = None
    if n_species < 30 or bear is None:
        verdict = "inconclusive"
        reason = "underpowered"
        confidence = 0.4
        a_holds = b_holds = c_holds = None
    else:
        others = use[use["MSW05_Binomial"] != "Ursus arctos"]
        smaller = others[others["ratio"] < float(bear["ratio"])]
        a_holds = bool(len(smaller) == 0)
        b_holds = None
        if mouse_adult is None or weasel_adult is None:
            b_holds = None
        else:
            b_holds = bool(float(bear["neonate_g"]) > mouse_adult and float(bear["neonate_g"]) < weasel_adult)
        if pd.isna(bear["eye_d"]):
            c_holds = None
        else:
            c_holds = bool(float(bear["eye_d"]) > 0)
        if not a_holds:
            verdict = "refutes"
        elif b_holds is False or c_holds is False:
            verdict = "mixed"
        elif b_holds is True and (c_holds is True or c_holds is None):
            verdict = "supports"
        else:
            verdict = "inconclusive"
            reason = "underpowered"
        n_smaller = int(len(smaller))
        confidence = 0.86 if verdict == "refutes" and n_smaller >= 5 else 0.7 if verdict == "mixed" else 0.55 if verdict == "supports" else 0.4
    else_block_n_smaller = int((use["ratio"] < float(bear["ratio"])).sum()) if bear is not None else None

    plac = use[~use["MSW05_Order"].isin(MARSUPIAL_ORDERS)]
    plac_bear = plac[plac["MSW05_Binomial"] == "Ursus arctos"]
    plac_extra = None
    if bear is not None and len(plac_bear):
        plac_others = plac[plac["MSW05_Binomial"] != "Ursus arctos"]
        plac_smaller = plac_others[plac_others["ratio"] < float(bear["ratio"])]
        plac_extra = {
            "n_after_dropping_listed_marsupial_orders": int(len(plac)),
            "n_remaining_with_smaller_ratio": int(len(plac_smaller)),
            "ursus_arctos_is_minimum_after_that_drop": bool(len(plac_smaller) == 0),
            "remaining_species_with_smaller_ratio": plac_smaller.sort_values("ratio")["MSW05_Binomial"].head(15).tolist(),
        }

    smallest = use.nsmallest(15, "ratio")[
        ["MSW05_Order", "MSW05_Binomial", "neonate_g", "adult_g", "ratio"]
    ]
    smallest.to_csv(os.path.join(DERIVED, "smallest-ratios.csv"), index=False)

    bear_ratio = None if bear is None else round(float(bear["ratio"]), 6)
    measured = {
        "value": bear_ratio,
        "unit": "Ursus arctos neonate mass / adult mass",
        "n": n_species,
        "uncertainty": "adult mass is not female-only; ratios use the table's adult body mass",
        "extra": {
            "ursus_arctos_neonate_g": None if bear is None else float(bear["neonate_g"]),
            "ursus_arctos_adult_g": None if bear is None else float(bear["adult_g"]),
            "ursus_arctos_eye_opening_d": None if bear is None or pd.isna(bear["eye_d"]) else float(bear["eye_d"]),
            "mus_musculus_adult_g": mouse_adult,
            "mustela_nivalis_adult_g": weasel_adult,
            "clause_A_minimum_ratio": a_holds if bear is not None else None,
            "clause_B_between_mouse_and_weasel": b_holds if bear is not None else None,
            "clause_C_eyes_open_after_birth": c_holds if bear is not None else None,
            "n_mammals_with_strictly_smaller_ratio": else_block_n_smaller,
            "minimum_ratio": None if use.empty else round(float(use["ratio"].min()), 6),
            "minimum_ratio_species": None if use.empty else str(use.loc[use["ratio"].idxmin(), "MSW05_Binomial"]),
            "placental_sensitivity": plac_extra,
        },
    }
    summary = {"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "file": file_meta}
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)

    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = "biological"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [{
            "id": "pantheria-1.0-wr05",
            "name": "PanTHERIA 1.0 WR05 mammal life-history table",
            "landing_url": "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt",
            "doi": "10.1890/08-1494.1",
            "version": "1.0_WR05_Aug2008",
            "license": None,
            "role": "neonate mass, adult mass, and age at eye opening",
            "files": [file_meta],
        }]
        result["method"] = (
            "analysis.py reads the PanTHERIA WR05 table, drops masses that are missing (-999) or not positive, "
            f"and divides neonate mass by adult mass for {n_species} species. "
            "Clause A asks whether Ursus arctos has the minimum ratio. "
            "Clause B compares that neonate mass with the adult masses of Mus musculus and Mustela nivalis. "
            "Clause C asks whether age at eye opening is after day 0. "
            "A recount that drops only the pre-registered marsupial orders is stored and does not set the verdict."
        )
        result["caveats"] = [
            "Adult body mass is not the mother's mass. Where males are heavier, the ratio is smaller than neonate/mother.",
            "The table covers mammals, not every animal. A smaller mammal refutes 'of all animals'; a minimum among mammals would not speak for birds or insects.",
            "Hairless skin and unformed limbs are not columns in PanTHERIA.",
            "The extra recount drops only the marsupial orders named before the data were opened. The short-beaked echidna is still in that recount, and it is a monotreme.",
            "The file is served by Ecological Archives. The archive landing page returned HTTP 403 to a header request from this environment; the text file itself returned HTTP 200.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n": n_species, "bear_ratio": bear_ratio, "confidence": confidence,
                      "A": measured["extra"]["clause_A_minimum_ratio"],
                      "B": measured["extra"]["clause_B_between_mouse_and_weasel"],
                      "C": measured["extra"]["clause_C_eyes_open_after_birth"],
                      "smaller": else_block_n_smaller,
                      "min_species": measured["extra"]["minimum_ratio_species"]}))


if __name__ == "__main__":
    main()
