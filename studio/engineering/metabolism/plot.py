"""Plot the O2 sweep and ATP-maintenance tradeoff from metabolism_results.json, and extract named energy-flow reactions from the flux table."""
import csv, json, sys, re
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

def main(d):
    r = json.load(open(d + "/metabolism_results.json"))
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot([s["o2_uptake_limit"] for s in r["o2_sweep"]], [s["biomass"] for s in r["o2_sweep"]], "o-")
    ax[0].set(xlabel="O2 uptake limit (assumed units mmol/gDW/h)", ylabel="biomass objective flux (model units)", title="Oxygen sweep, glucose capped at 10 (assumed)")
    for lim in (20, 0):
        t = [x for x in r["atp_tradeoff"] if x["o2_uptake_limit"] == lim]
        ax[1].plot([x["forced_atp_hydrolysis"] for x in t], [x["biomass"] for x in t], "o-", label="O2 limit %d" % lim)
    ax[1].set(xlabel="forced ATP hydrolysis, MAR03964 lower bound", ylabel="biomass objective flux", title="ATP maintenance vs growth"); ax[1].legend()
    fig.suptitle("Zebrafish-GEM FBA (steady-state LP; generic Danio rerio; assumed allowlist medium)", fontsize=9); fig.tight_layout()
    fig.savefig(d + "/o2_atp_biomass.png", dpi=110)
    pat = re.compile(r"cytochrome c oxidase|ATP synthase|complex I\b|NADH:ubiquinone|hexokinase|pyruvate dehydrogenase|lactate dehydrogenase|ATP phosphohydrolase|^$", re.I)
    ids = {"MAR09034": "glucose exchange", "MAR09048": "O2 exchange", "MAR03964": "ATP hydrolysis", "MAR00021": "biomass"}
    rows = [x for x in csv.DictReader(open(d + "/flux_table_baseline_o2_20.csv")) if x["reaction_id"] in ids or (x["name"] and pat.search(x["name"]) and not x["name"] == "")]
    json.dump([{k: x[k] for k in ("reaction_id", "name", "flux", "equation")} for x in rows], open(d + "/selected_energy_flow.json", "w"), indent=1)
    print(len(rows)); [print(x["reaction_id"], x["name"][:50], x["flux"]) for x in rows[:25]]
main(sys.argv[1])
