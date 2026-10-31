"""Zebrafish-GEM flux-balance slice. Steady-state LP, not time-dynamic metabolism. Generic Danio rerio model: nothing here is fin-, tissue- or stage-specific.

usage: python run.py MODEL.xml OUTDIR   (needs cobra; model fetched separately and hash-pinned)
"""
import hashlib, json, sys, csv, warnings
import numpy as np, cobra
from cobra.medium import minimal_medium
warnings.filterwarnings("ignore")
COMMIT = "846f0b7b34701801b2f5e15f549807d2e71ffa62"
MODEL_SHA = "3424f584f3f48711d79a0a5af475e0ad0413af10c93345a7bb76e53874a1e217"
BIOMASS, ATPASE = "MAR00021", "MAR03964"           # biomass objective (model's own); ATP + H2O -> ADP + H+ + Pi
GLC_UPTAKE = 10.0                                   # ASSUMED cap, mmol/gDW/h: the SBML defines no medium; not a published baseline
O2_DERIVE = 1000.0                                  # O2 unconstrained while the minimal medium is derived
TOL = 1e-6


def main(path, out):
    raw = open(path, "rb").read(); assert hashlib.sha256(raw).hexdigest() == MODEL_SHA, "model bytes changed"
    m = cobra.io.read_sbml_model(path); m.solver = "glpk"
    ex = {list(r.metabolites)[0].name: r for r in m.exchanges if len(r.metabolites) == 1}
    glc, o2 = ex["glucose"], ex["O2"]
    S = cobra.util.create_stoichiometric_matrix(m)
    rec = {"model": {"commit": COMMIT, "sha256": MODEL_SHA, "reactions": len(m.reactions), "metabolites": len(m.metabolites), "genes": len(m.genes),
                     "compartments": m.compartments, "exchanges": len(m.exchanges), "objective": BIOMASS,
                     "default_exchange_bounds": sorted({r.bounds for r in m.exchanges}), "atp_hydrolysis_bounds": m.reactions.get_by_id(ATPASE).bounds},
           "units": "flux units are not declared in the SBML; mmol/gDW/h is the Human-GEM-family convention and is ASSUMED here", "controls": {}}

    def solve(label, tag=None):
        s = m.slim_optimize(error_value=None); st = m.solver.status
        v = np.array([r.flux for r in m.reactions]) if s is not None else None
        chk = {} if v is None else {"max_abs_Sv": float(abs(S @ v).max()),
               "bounds_ok": bool(all(r.lower_bound - TOL <= r.flux <= r.upper_bound + TOL for r in m.reactions))}
        return {"status": st, "objective": s, **chk}

    # control A: source default, every exchange open +-1000. This is NOT a medium.
    rec["controls"]["A_source_default_all_exchanges_open"] = solve("A")
    # control B: all uptake closed -> no growth expected
    for r in m.exchanges: r.lower_bound = 0
    rec["controls"]["B_all_uptake_closed"] = solve("B")
    # control C: glucose only (no O2, no other nutrients): growth needs more than glucose
    glc.lower_bound = -GLC_UPTAKE
    rec["controls"]["C_glucose_only"] = solve("C")
    # control G: unrestricted minimum-uptake derivation. It exploits nucleotide/cofactor/peptide exchanges as free energy and carbon sources, so it is NOT physiological.
    for r in m.exchanges: r.lower_bound = -1000
    glc.lower_bound = -GLC_UPTAKE
    mu_rich = m.slim_optimize()
    mm = minimal_medium(m, 0.5 * mu_rich, minimize_components=False, open_exchanges=False)
    names = {list(m.reactions.get_by_id(i).metabolites)[0].name for i in mm.index}
    rec["controls"]["G_unrestricted_minimal_medium_is_degenerate"] = {"rich_biomass": mu_rich, "components": len(mm), "uses_ATP_uptake": "ATP" in names, "uses_UTP_uptake": "UTP" in names}
    # primary assumed medium: ALLOWLIST of basic nutrients by metabolite name. Names absent from the model's exchanges are recorded, not guessed.
    ALLOW = ("glucose O2 H2O H+ CO2 Pi NH3 sulfate Na+ K+ Ca2+ Mg2+ Fe2+ Fe3+ Cu2+ zinc iodide alanine arginine asparagine aspartate cysteine glutamate glutamine glycine histidine "
             "isoleucine leucine lysine methionine phenylalanine proline serine threonine tryptophan tyrosine valine linoleate linolenate arachidonate palmitate oleate choline inositol thiamin "
             "riboflavin nicotinamide pyridoxine pyridoxal folate aquacob(III)alamin biotin pantothenate ascorbate retinol alpha-tocopherol gamma-tocopherol heme").split()
    med = {}; missing = []
    for n in ALLOW:
        if n in ex: med[ex[n].id] = {"metabolite": n, "uptake_lb": -1000.0}
        else: missing.append(n)
    rec["assumed_medium"] = {"basis": "ASSUMED allowlist of basic nutrients (uptake not otherwise limited; glucose capped at %g); not a published or measured medium" % GLC_UPTAKE,
                             "components": med, "allowlist_names_without_an_exchange": missing}

    def set_medium(o2_lb):
        for r in m.exchanges: r.lower_bound = 0
        for rid, d in med.items(): m.reactions.get_by_id(rid).lower_bound = d["uptake_lb"]
        glc.lower_bound = -GLC_UPTAKE; o2.lower_bound = -o2_lb
        m.reactions.get_by_id(ATPASE).lower_bound = 0
    # derivation used free O2, so list what O2 it took
    set_medium(O2_DERIVE); base = solve("base"); rec["controls"]["D_assumed_medium_free_O2"] = base
    rec["assumed_medium"]["o2_uptake_at_free_O2"] = -o2.flux if base["objective"] is not None else None
    # oxygen sweep
    sweep = []
    for lim in [0, 1, 2, 4, 6, 8, 10, 15, 20, 30, 50]:
        set_medium(lim); r = solve("o2"); sweep.append({"o2_uptake_limit": lim, "biomass": r["objective"], "status": r["status"], "o2_flux": -o2.flux if r["objective"] is not None else None,
                                                       "glc_flux": -glc.flux if r["objective"] is not None else None, "max_abs_Sv": r.get("max_abs_Sv")})
    rec["o2_sweep"] = sweep
    # ATP maintenance vs growth (O2 at 20 and 0): force ATP hydrolysis flux
    trade = []
    for lim in (20, 0):
        for k in [0, 5, 10, 20, 40, 60, 80, 100]:
            set_medium(lim); m.reactions.get_by_id(ATPASE).lower_bound = k; r = solve("t")
            trade.append({"o2_uptake_limit": lim, "forced_atp_hydrolysis": k, "biomass": r["objective"], "status": r["status"]})
    rec["atp_tradeoff"] = trade
    # baseline flux table at O2 limit 20
    set_medium(20); b = solve("b"); rec["controls"]["E_baseline_o2_20"] = b
    with open(out + "/flux_table_baseline_o2_20.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["reaction_id", "name", "subsystem", "lower", "upper", "flux", "equation"])
        for r in m.reactions:
            if abs(r.flux) > 1e-9: w.writerow([r.id, r.name, r.subsystem, r.lower_bound, r.upper_bound, "%.9g" % r.flux, r.reaction])
    # objective validity: the objective must be the biomass reaction, and that flux equals the objective
    rec["controls"]["F_objective_validity"] = {"objective_ids": [r.id for r in m.reactions if r.objective_coefficient], "biomass_flux_equals_objective": abs(m.reactions.get_by_id(BIOMASS).flux - b["objective"]) < 1e-9}
    json.dump(rec, open(out + "/metabolism_results.json", "w"), indent=1, default=float)
    print(json.dumps({k: rec["controls"][k] for k in rec["controls"]}, default=float)[:1500]); print(len(med), "medium components"); print(sweep)

if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
