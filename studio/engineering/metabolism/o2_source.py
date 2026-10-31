"""Two-condition diagnostic (not a sweep): does the model make its own O2 through MAR04071 (pyridoxine oxidase, run in reverse) when O2 uptake is limited?
Same assumed allowlist medium as run.py; solves with MAR04071 free vs blocked at O2 uptake limits 0 and 20."""
import hashlib, json, sys, warnings, cobra
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from engineering.metabolism.run import MODEL_SHA, ATPASE, GLC_UPTAKE

def main(path, d):
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == MODEL_SHA
    m = cobra.io.read_sbml_model(path); m.solver = "glpk"
    med = json.load(open(d + "/metabolism_results.json"))["assumed_medium"]["components"]
    out = []
    for lim in (0, 20):
        for blocked in (False, True):
            with m:
                for r in m.exchanges: r.lower_bound = 0
                for rid, c in med.items():
                    m.reactions.get_by_id(rid).lower_bound = -GLC_UPTAKE if c["metabolite"] == "glucose" else (-float(lim) if c["metabolite"] == "O2" else c["uptake_lb"])
                if blocked: m.reactions.MAR04071.bounds = (0, 0)
                b = m.slim_optimize(error_value=None)
                row = {"o2_uptake_limit": lim, "MAR04071_blocked": blocked, "biomass": b, "status": m.solver.status}
                if b is not None: row["MAR04071_flux"] = m.reactions.MAR04071.flux; row["o2_exchange_flux"] = m.reactions.MAR09048.flux
                out.append(row)
    res = {"reaction": "MAR04071", "name": m.reactions.MAR04071.name, "equation": m.reactions.MAR04071.reaction, "bounds_in_model": list(m.reactions.MAR04071.bounds), "results": out,
           "reading": "A diagnostic of this model's structure under the ASSUMED uptake-uncapped medium, not a measurement of oxygen dependence in any fish."}
    json.dump(res, open(d + "/o2_source_diagnostic.json", "w"), indent=1, default=float); print(json.dumps(res["results"], default=float), res["equation"])
if __name__ == "__main__": main(*sys.argv[1:3])
