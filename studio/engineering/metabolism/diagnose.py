"""Which biomass precursors can the allowlist medium not make? Adds a temporary sink per precursor and maximises it (steady-state LP)."""
import json, sys, warnings, cobra
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from engineering.metabolism.run import BIOMASS, MODEL_SHA, ATPASE
import hashlib

def main(path, res, out):
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == MODEL_SHA
    m = cobra.io.read_sbml_model(path); m.solver = "glpk"
    med = json.load(open(res))["assumed_medium"]["components"]
    for r in m.exchanges: r.lower_bound = 0
    for rid, d in med.items(): m.reactions.get_by_id(rid).lower_bound = d["uptake_lb"]
    m.reactions.get_by_id([k for k, d in med.items() if d["metabolite"] == "glucose"][0]).lower_bound = -10
    rows = []
    for met in m.reactions.get_by_id(BIOMASS).reactants:
        with m:
            sink = m.add_boundary(met, type="demand"); m.objective = sink
            v = m.slim_optimize(error_value=None)
        rows.append({"precursor": met.id, "name": met.name, "compartment": met.compartment, "max_sink_flux": v, "status": m.solver.status})
    # second stage: inputs of the reaction that makes any blocked pool (the pool's own sub-precursors)
    sub = []
    for b in [r for r in rows if not r["max_sink_flux"] or r["max_sink_flux"] < 1e-9]:
        pool = m.metabolites.get_by_id(b["precursor"])
        for rx in pool.reactions:
            if rx.metabolites[pool] > 0 and rx.id != BIOMASS and rx.upper_bound > 0 and len(rx.metabolites) < 40:
                for met in rx.reactants:
                    with m:
                        sink = m.add_boundary(met, type="demand"); m.objective = sink
                        v = m.slim_optimize(error_value=None)
                    sub.append({"pool": pool.name, "via_reaction": rx.id, "input": met.id, "name": met.name, "compartment": met.compartment, "max_sink_flux": v})
    rows = {"biomass_precursors": rows, "blocked_pool_inputs": sub}
    json.dump(rows, open(out, "w"), indent=1)
    rows = rows["biomass_precursors"]
    blocked = [r for r in rows if not r["max_sink_flux"] or r["max_sink_flux"] < 1e-9]
    print(len(rows), "precursors;", len(blocked), "blocked:", [(b["name"], b["compartment"]) for b in blocked])
    print("blocked inputs:", [(x["name"], x["compartment"]) for x in sub if not x["max_sink_flux"] or x["max_sink_flux"] < 1e-9])
if __name__ == "__main__": main(*sys.argv[1:4])
