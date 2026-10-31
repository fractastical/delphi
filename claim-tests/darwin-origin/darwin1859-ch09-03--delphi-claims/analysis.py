"""Test of darwin1859-ch09-03: time since the late Chalk on the ICS timescale versus Darwin's ~300 million years.

Reads data/macrostrat_international_ages.json (run fetch.py first). Writes derived/summary.json.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "macrostrat_international_ages.json")
DERIVED = os.path.join(HERE, "derived")
DARWIN_YEARS = 306_662_400  # Darwin's own figure for the denudation of the Weald


def main():
    os.makedirs(DERIVED, exist_ok=True)
    d = json.load(open(DATA, encoding="utf-8"))
    ivs = {x["name"]: x for x in d["success"]["data"]}
    if "Maastrichtian" not in ivs or "Campanian" not in ivs:
        out = {"verdict": "inconclusive", "reason": "not-operationalizable", "names": sorted(ivs)}
    else:
        top_maas = float(ivs["Maastrichtian"]["t_age"])   # Ma, = Cretaceous-Paleogene boundary
        base_camp = float(ivs["Campanian"]["b_age"])
        base_maas = float(ivs["Maastrichtian"]["b_age"])
        verdict = "supports" if top_maas >= 225 else "refutes"
        out = {"license": d["success"].get("license"), "n_intervals": len(ivs),
               "top_of_maastrichtian_Ma": top_maas, "base_of_maastrichtian_Ma": base_maas, "base_of_campanian_Ma": base_camp,
               "darwin_years_Myr": DARWIN_YEARS / 1e6, "ratio_darwin_to_measured_top_maastrichtian": DARWIN_YEARS / 1e6 / top_maas,
               "ratio_darwin_to_measured_base_campanian": DARWIN_YEARS / 1e6 / base_camp, "threshold_Ma": 225, "verdict": verdict}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
