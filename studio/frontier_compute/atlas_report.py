"""Protocol 6 analysis: validation gates V1-V3 (GPU solver A vs CPU solver A on control cells), NCA-schema rows (A = GPU base, B = CPU BDF), NCA analyze.py on them,
and the numerical-sensitivity report. Usage: python3 -m frontier_compute.atlas_report ATLAS.json GPU_DIR CPU_DIR OUTDIR"""
import json, sys
from collections import Counter
from pathlib import Path
import numpy as np
from . import VENDOR  # noqa: F401
from scopedesk.oracles import kinetics
from scopedesk.oracles.nonlinear_sweep import analyze as NA
from .compare2 import agree_revised, agree_old

TOL_AMP_SOLVERS = 0.15


def category(A, B):
    if A.get("diverged") or B.get("diverged"):
        return "unresolved", "diverged"
    if A["pattern"] != B["pattern"]:
        return "unresolved", "solver_disagree_flag"
    if A["pattern"] and (A["mode"] != B["mode"] or abs(A["amp"] - B["amp"]) > TOL_AMP_SOLVERS * max(A["amp"], B["amp"])):
        return "unresolved", "solver_disagree_mode_or_amp"
    if not (A["settled"] and B["settled"]):
        return "unresolved", "not_settled"
    return ("pattern" if A["pattern"] else "no_pattern"), None


def main(atlas_path, gpu_dir, cpu_dir, outdir):
    At = json.load(open(atlas_path)); cells = {c["id"]: c for c in At["cells"]}
    ctrl_ids, sub_ids = At["control_ids"], set(At["refine_subset_ids"])
    G = {}
    for l in open(f"{gpu_dir}/atlas_results.jsonl"):
        r = json.loads(l); G.setdefault(r["arm"], {})[r["id"]] = r
    GF = np.load(f"{gpu_dir}/atlas_fields.npz")
    B = {json.loads(l)["id"]: json.loads(l) for l in open(f"{cpu_dir}/cpu_B.jsonl")}
    CA = {json.loads(l)["id"]: json.loads(l) for l in open(f"{cpu_dir}/cpu_A_ctrl.jsonl")}
    CF = np.load(f"{cpu_dir}/cpu_A_fields.npz")
    base = G["base"]
    complete_base = all(i in base and not base[i].get("out_of_budget") for i in cells)
    # ---- validation V1 on control cells
    ust = lambda c: float(kinetics.steady(c["model"], kinetics.params(c["model"], c["params"]))[0])
    V, fail = {}, []
    for i in ctrl_ids:
        c = cells[i]; g, a = base.get(i), CA.get(i)
        if g is None or a is None or g.get("out_of_budget"):
            V[i] = {"missing": True}; continue
        e_dt = float(np.abs(GF[f"{i}_base_u_final"] - GF[f"{i}_dt2_u_final"]).max() / abs(ust(c))) if f"{i}_dt2_u_final" in GF.files else None
        err = None if (g.get("diverged") or a.get("diverged")) else float(np.abs(GF[f"{i}_base_u_final"] - CF[f"{i}_A_u"]).max() / abs(ust(c)))
        conv = e_dt is not None and e_dt <= 0.01
        tol = max(1e-9, 2 * e_dt) if e_dt is not None else None
        ok = agree_revised(g, a, err, tol or 0)
        V[i] = {"model": c["model"], "rho": c["rho"], "eps": c["eps"], "step_converged": conv, "e_dt_gpu": e_dt, "err": err, "tol": tol, "revised_ok": ok, "old_ok": agree_old(g, a),
                "cpu_pattern": a.get("pattern"), "gpu_pattern": g.get("pattern")}
        if conv and not ok:
            fail.append(i)
    vc = [i for i in ctrl_ids if V[i].get("step_converged")]
    pat_vc = [i for i in vc if V[i]["cpu_pattern"]]
    V1 = not fail
    homo = [i for i, c in cells.items() if c["rho"] == 0.7 and c["eps"] == 0.01]
    V2 = all((i in base and base[i].get("pattern") is False) and (i in B and B[i].get("pattern") is False) for i in homo)
    mut = {"M1_mode_plus1_on_patterned": [0, 0], "M2_flip_pattern_flag": [0, 0], "M3_field_error_10x_tol": [0, 0], "M4_flip_settled": [0, 0]}
    for i in vc:
        if not V[i]["revised_ok"] or base[i].get("diverged") or CA[i].get("diverged"):
            continue
        g0, a, t, e = base[i], CA[i], V[i]["tol"], V[i]["err"]
        if a["pattern"]:
            mut["M1_mode_plus1_on_patterned"][1] += 1; mut["M1_mode_plus1_on_patterned"][0] += not agree_revised({**g0, "mode": g0["mode"] + 1}, a, e, t)
        mut["M2_flip_pattern_flag"][1] += 1; mut["M2_flip_pattern_flag"][0] += not agree_revised({**g0, "pattern": not g0["pattern"]}, a, e, t)
        mut["M3_field_error_10x_tol"][1] += 1; mut["M3_field_error_10x_tol"][0] += not agree_revised(g0, a, e + 10 * t, t)
        mut["M4_flip_settled"][1] += 1; mut["M4_flip_settled"][0] += not agree_revised({**g0, "settled": not g0["settled"]}, a, e, t)
    V3 = all(k == n and n > 0 for k, n in mut.values())
    not_conv = 1 - len(vc) / len(ctrl_ids)
    inconclusive = (not complete_base) or not_conv > 0.25 or len(pat_vc) < 8
    status = "INCONCLUSIVE" if inconclusive else ("VALIDATED" if (V1 and V2 and V3) else "NOT_VALIDATED")
    # ---- NCA-schema rows
    rows = []
    for i, c in cells.items():
        A_, B_ = base.get(i, {"diverged": True}), B.get(i, {"diverged": True})
        cat, why = category(A_, B_)
        rows.append({"id": i, "model": c["model"], "draw": c["draw"], "rho": c["rho"], "x": c["x"], "eps": c["eps"], "seed": c["seed"], "linear": c["linear"],
                     "linear_fastest_mode": c["linear_fastest_mode"], "category": cat, "why": why, "mode": A_.get("mode") if cat == "pattern" else None,
                     "A": {k: A_.get(k) for k in ("pattern", "mode", "amp", "settled", "diverged")}, "B": {k: B_.get(k) for k in ("pattern", "mode", "amp", "settled", "diverged")}})
    out = Path(outdir); out.mkdir(parents=True, exist_ok=True)
    raw = "".join(json.dumps(r, sort_keys=True, allow_nan=False) + "\n" for r in rows)
    (out / "rows.jsonl").write_text(raw)
    (out / "run_status.json").write_text(json.dumps({"cells_total": len(rows), "cells_done": len(rows), "stopped_by": "completion", "note": "A = GPU torch float64 base arm, B = CPU scipy BDF"}))
    NA.main(str(out))
    # ---- sensitivity: category changes if A is replaced by refinement arms (subset)
    sens = {}
    for arm in ("dt2", "grid2", "perturb"):
        if arm not in G:
            sens[arm] = {"status": "not_run"}; continue
        n = ch = flag = mode = miss = 0
        for i in sub_ids:
            if i not in G[arm] or G[arm][i].get("not_run") or G[arm][i].get("out_of_budget"):
                miss += 1; continue
            n += 1
            a2 = G[arm][i]; a0 = base[i]
            c2, _ = category(a2, B[i]); c0, _ = category(a0, B[i])
            ch += c2 != c0
            if not (a2.get("diverged") or a0.get("diverged")):
                flag += a2["pattern"] != a0["pattern"]
                mode += bool(a0["pattern"] and a2["pattern"] and a2["mode"] != a0["mode"])
        sens[arm] = {"n": n, "missing_or_out_of_budget": miss, "category_changes_vs_base": ch, "flag_flips": flag, "patterned_mode_flips": mode}
    rep = {"status": status, "V1_agreement_step_converged_controls": V1, "V1_failing_ids": fail, "V2_homogeneous_control": V2, "n_homogeneous": len(homo), "V3_mutation_kill": V3, "mutations": mut,
           "n_control": len(ctrl_ids), "n_control_step_converged": len(vc), "n_control_patterned_step_converged": len(pat_vc), "control_not_step_converged_fraction": not_conv,
           "base_arm_complete": complete_base, "old_rule_would_fail_on": [i for i in vc if not V[i]["old_ok"]], "sensitivity_refine_subset": sens,
           "max_err_step_converged_controls": max([V[i]["err"] for i in vc if V[i].get("err") is not None], default=None),
           "category_counts": dict(Counter(r["category"] for r in rows)), "unresolved_reasons": dict(Counter(r["why"] for r in rows if r["category"] == "unresolved"))}
    (out / "atlas_validation.json").write_text(json.dumps({"summary": rep, "controls": {str(k): v for k, v in V.items()}}, indent=1, sort_keys=True, allow_nan=False))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
