"""Parsimonious FBA at the baseline condition (O2 limit 20): removes unconstrained futile cycles that plain FBA leaves at the bounds."""
import csv, hashlib, json, sys, warnings, cobra
from cobra.flux_analysis import pfba
warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from engineering.metabolism.run import MODEL_SHA, ATPASE, GLC_UPTAKE

def main(path, d):
    assert hashlib.sha256(open(path, "rb").read()).hexdigest() == MODEL_SHA
    m = cobra.io.read_sbml_model(path); m.solver = "glpk"
    med = json.load(open(d + "/metabolism_results.json"))["assumed_medium"]["components"]
    for r in m.exchanges: r.lower_bound = 0
    for rid, c in med.items():
        m.reactions.get_by_id(rid).lower_bound = -GLC_UPTAKE if c["metabolite"] == "glucose" else (-20.0 if c["metabolite"] == "O2" else c["uptake_lb"])
    m.reactions.get_by_id(ATPASE).lower_bound = 0
    s = pfba(m); fl = s.fluxes
    S = cobra.util.create_stoichiometric_matrix(m)
    out = {"biomass": float(fl["MAR00021"]), "max_abs_Sv": float(abs(S @ fl.values).max()), "total_abs_flux": float(fl.abs().sum()),
           "MAR06916_flux": float(fl["MAR06916"]), "MAR03964_flux": float(fl[ATPASE]), "n_nonzero": int((fl.abs() > 1e-9).sum())}
    json.dump(out, open(d + "/pfba_summary.json", "w"), indent=1); print(out)
    with open(d + "/flux_table_pfba_o2_20.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["reaction_id", "name", "subsystem", "flux", "equation"])
        for r in m.reactions:
            if abs(fl[r.id]) > 1e-9: w.writerow([r.id, r.name, r.subsystem, "%.9g" % fl[r.id], r.reaction])
if __name__ == "__main__": main(*sys.argv[1:3])
