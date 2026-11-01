"""Energy-generating-cycle test: with every uptake closed, any positive ATP-hydrolysis flux is ATP made from nothing (a thermodynamically impossible cycle)."""
import hashlib, json, sys, warnings, cobra
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from engineering.metabolism.run import MODEL_SHA, ATPASE

def main(path, d):
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == MODEL_SHA
    m = cobra.io.read_sbml_model(path); m.solver = "glpk"
    for r in m.exchanges: r.lower_bound = 0
    out = {}
    for tag, rid in (("cytosolic_ATP_hydrolysis_MAR03964", ATPASE), ("mito_ATP_synthase_MAR06916", "MAR06916")):
        m.objective = rid; v = m.slim_optimize(error_value=None); out[tag] = {"max_flux_all_uptake_closed": v, "status": m.solver.status}
    with m:
        m.objective = ATPASE
        m.reactions.MAR06916.upper_bound = 0
        out["cytosolic_ATP_hydrolysis_with_ATP_synthase_off"] = {"max_flux": m.slim_optimize(error_value=None)}
    egc = any((v.get("max_flux_all_uptake_closed") or 0) > 1e-9 for v in out.values() if "max_flux_all_uptake_closed" in v)
    out["energy_generating_cycle_found"] = egc
    out["reading"] = ("ATP is made with every uptake closed: an energy-generating cycle; the O2 sweep and ATP tradeoff are not energetics of this model." if egc else
                      "No energy-generating cycle with every uptake closed (tested for ATP hydrolysis and ATP synthase). Not a proof there is none under other bounds.")
    json.dump(out, open(d + "/egc_test.json", "w"), indent=1); print(out)
if __name__ == "__main__": main(*sys.argv[1:3])
