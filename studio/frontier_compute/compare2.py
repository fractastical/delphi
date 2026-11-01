"""Experiment 2 analysis (PROTOCOL2.md): pattern-conditioned agreement on held-out cells, with controls and checker mutations.
  python3 -m frontier_compute.compare2 CELLS.json CPU_DIR GPU_DIR TOL.json OUT.json
Gate (frozen before any held-out result exists): G1 revised agreement on all step-converged cells; G2 homogeneous control; G3 unstable control;
G4 mutation kill 100%; INCONCLUSIVE if >25% not step-converged or <8 patterned step-converged cells. The OLD rule (mode compared on every cell) is
computed and reported alongside, never used as the gate here."""
import copy, json, sys
import numpy as np
from . import VENDOR  # noqa: F401
from scopedesk.oracles import kinetics


def ust_of(c):
    return float(kinetics.steady(c["model"], kinetics.params(c["model"], c["params"]))[0])


def agree_revised(g, a, err, tol):
    """g, a: GPU / CPU-A metric dicts; err/tol floats (err None if either diverged)."""
    gd, cd = bool(g.get("diverged")), bool(a.get("diverged"))
    if gd or cd:
        return gd == cd
    if g["pattern"] != a["pattern"] or g["settled"] != a["settled"]:
        return False
    if a["pattern"] and g["mode"] != a["mode"]:
        return False
    return err is not None and err <= tol


def agree_old(g, a):
    if bool(g.get("diverged")) or bool(a.get("diverged")):
        return bool(g.get("diverged")) == bool(a.get("diverged"))
    return all(g[k] == a[k] for k in ("pattern", "mode", "settled"))


def main(cells_path, cpu_dir, gpu_dir, tol_path, out):
    cells = {c["id"]: c for c in json.load(open(cells_path))["cells"]}
    cpu = {json.loads(l)["id"]: json.loads(l) for l in open(f"{cpu_dir}/cpu_ref.jsonl")}
    CF = np.load(f"{cpu_dir}/cpu_ref_fields.npz")
    tol = json.load(open(tol_path))["cells"]
    arms = {}
    for l in open(f"{gpu_dir}/gpu_results.jsonl"):
        r = json.loads(l)
        arms.setdefault(r["arm"], {})[r["id"]] = r
    GF = np.load(f"{gpu_dir}/gpu_fields.npz")
    base = arms["base"]
    rows, G1_fail = {}, []
    for i, c in cells.items():
        g, a, t = base[i], cpu[i]["A_dt"], tol[str(i)]
        err = None
        if not g.get("diverged") and not a.get("diverged"):
            err = float(np.abs(GF[f"{i}_base_u_final"] - CF[f"{i}_A_dt_u"]).max() / abs(ust_of(c)))
        rows[i] = {"rho": c["rho"], "eps": c["eps"], "model": c["model"], "draw": c["draw"], "x": c["x"], "linear": c["linear"], "step_converged": t["step_converged"],
                   "cpu_pattern": a.get("pattern"), "gpu_pattern": g.get("pattern"), "cpu_mode": a.get("mode"), "gpu_mode": g.get("mode"), "err": err, "tol": t["tol"],
                   "revised_ok": agree_revised(g, a, err, t["tol"] or 0), "old_ok": agree_old(g, a)}
        if t["step_converged"] and not rows[i]["revised_ok"]:
            G1_fail.append(i)
    conv = [i for i in rows if rows[i]["step_converged"]]
    pat_conv = [i for i in conv if rows[i]["cpu_pattern"]]
    not_conv_frac = 1 - len(conv) / len(rows)
    G1 = not G1_fail
    homo = [i for i in rows if rows[i]["rho"] == 0.7 and rows[i]["eps"] == 0.01]
    G2 = bool(homo) and all(rows[i]["cpu_pattern"] is False and rows[i]["gpu_pattern"] is False for i in homo)
    uns = [i for i in rows if rows[i]["rho"] == 3.0]
    G3_sat = any(rows[i]["cpu_pattern"] for i in uns)
    G3 = G3_sat and all(rows[i]["cpu_pattern"] == rows[i]["gpu_pattern"] for i in uns)
    # ---- mutations: each applied singly to the GPU base result of an eligible step-converged cell; the revised check must reject (kill)
    mut = {"M1_mode_plus1_on_patterned": [0, 0], "M2_flip_pattern_flag": [0, 0], "M3_field_error_10x_tol": [0, 0], "M4_flip_settled": [0, 0]}
    for i in conv:
        g0, a, t = base[i], cpu[i]["A_dt"], tol[str(i)]
        if g0.get("diverged") or a.get("diverged") or not rows[i]["revised_ok"]:
            continue
        if a["pattern"]:
            g = dict(g0); g["mode"] = g0["mode"] + 1
            mut["M1_mode_plus1_on_patterned"][1] += 1; mut["M1_mode_plus1_on_patterned"][0] += (not agree_revised(g, a, rows[i]["err"], t["tol"]))
        g = dict(g0); g["pattern"] = not g0["pattern"]
        mut["M2_flip_pattern_flag"][1] += 1; mut["M2_flip_pattern_flag"][0] += (not agree_revised(g, a, rows[i]["err"], t["tol"]))
        mut["M3_field_error_10x_tol"][1] += 1; mut["M3_field_error_10x_tol"][0] += (not agree_revised(g0, a, rows[i]["err"] + 10 * t["tol"], t["tol"]))
        g = dict(g0); g["settled"] = not g0["settled"]
        mut["M4_flip_settled"][1] += 1; mut["M4_flip_settled"][0] += (not agree_revised(g, a, rows[i]["err"], t["tol"]))
    G4 = all(k == n and n > 0 for k, n in mut.values())
    # design-intent check: a mode shift on a NON-patterned cell must not matter under the revised rule (and does under the old one)
    nonpat = [i for i in conv if not cpu[i]["A_dt"].get("pattern") and not base[i].get("diverged")]
    shift_old_rej = sum(not agree_old({**base[i], "mode": base[i]["mode"] + 1}, cpu[i]["A_dt"]) for i in nonpat)
    shift_rev_rej = sum(not agree_revised({**base[i], "mode": base[i]["mode"] + 1}, cpu[i]["A_dt"], rows[i]["err"], tol[str(i)]["tol"]) for i in nonpat if rows[i]["revised_ok"])
    inconclusive = (not_conv_frac > 0.25) or (len(pat_conv) < 8)
    verdict = "INCONCLUSIVE" if inconclusive else ("PASS" if (G1 and G2 and G3 and G4) else "FAIL")
    # ---- reported controls (non-gating)
    def modeagree(ids, other):
        ids = [i for i in ids if i in other and not base[i].get("diverged") and not other[i].get("diverged")]
        return {"n": len(ids), "mode_equal": sum(base[i]["mode"] == other[i]["mode"] for i in ids)}
    cpu_pat = [i for i in rows if rows[i]["cpu_pattern"]]
    cpu_non = [i for i in rows if rows[i]["cpu_pattern"] is False]
    noise = {"old_rule_mode_vs_CPU": {"patterned": {"n": len(cpu_pat), "mode_equal": sum(rows[i]["cpu_mode"] == rows[i]["gpu_mode"] for i in cpu_pat)},
                                      "non_patterned": {"n": len(cpu_non), "mode_equal": sum(rows[i]["cpu_mode"] == rows[i]["gpu_mode"] for i in cpu_non)}},
             "max_amp_non_patterned_cpu": max([cpu[i]["A_dt"]["amp"] for i in cpu_non if not cpu[i]["A_dt"].get("diverged")], default=None)}
    stab = None
    if "perturb" in arms:
        P = arms["perturb"]
        noise["gpu_base_vs_gpu_perturb_mode"] = {"patterned": modeagree(cpu_pat, P), "non_patterned": modeagree(cpu_non, P)}
        ok = [i for i in rows if i in P and not P[i].get("diverged") and not base[i].get("diverged")]
        stab = {"n": len(ok), "flag_equal": sum(base[i]["pattern"] == P[i]["pattern"] for i in ok), "settled_equal": sum(base[i]["settled"] == P[i]["settled"] for i in ok),
                "patterned_mode_equal": sum(base[i]["mode"] == P[i]["mode"] for i in ok if base[i]["pattern"] and P[i]["pattern"]),
                "n_patterned": sum(1 for i in ok if base[i]["pattern"]), "flag_flips": [i for i in ok if base[i]["pattern"] != P[i]["pattern"]],
                "max_rel_amp_patterned": max([abs(base[i]["amp"] - P[i]["amp"]) / base[i]["amp"] for i in ok if base[i]["pattern"] and P[i]["pattern"]], default=None),
                "perturbation": "relative 1e-10 multiplicative noise on the initial state, fixed per cell id"}
    conv_ctl = {}
    for arm in ("dt2", "grid2"):
        if arm in arms:
            A2 = arms[arm]
            ids = [i for i in rows if i in A2 and not A2[i].get("diverged") and not base[i].get("diverged")]
            conv_ctl[arm] = {"n": len(ids), "flag_flips": [i for i in ids if base[i]["pattern"] != A2[i]["pattern"]],
                             "mode_flips_patterned": [i for i in ids if base[i]["pattern"] and A2[i]["pattern"] and base[i]["mode"] != A2[i]["mode"]],
                             "amp_over_10pct_patterned": [i for i in ids if base[i]["pattern"] and A2[i]["pattern"] and abs(base[i]["amp"] - A2[i]["amp"]) > 0.1 * base[i]["amp"]],
                             "diverged_or_missing": [i for i in rows if i not in A2 or A2[i].get("diverged")]}
    summary = {"verdict": verdict, "G1_revised_agreement_step_converged": G1, "G1_failing_ids": G1_fail, "G2_homogeneous": G2, "n_homogeneous": len(homo),
               "G3_unstable": G3, "G3_satisfiable": G3_sat, "n_unstable": len(uns), "G4_mutation_kill": G4, "mutations_killed_of_applied": mut,
               "not_step_converged_fraction": not_conv_frac, "n_cells": len(rows), "n_step_converged": len(conv), "n_patterned_step_converged": len(pat_conv),
               "old_rule_would_fail_on_step_converged": [i for i in conv if not rows[i]["old_ok"]],
               "design_intent_mode_shift_on_nonpatterned": {"n": len(nonpat), "rejected_by_old_rule": shift_old_rej, "rejected_by_revised_rule": shift_rev_rej},
               "noise_control": noise, "stability_control": stab, "convergence_control": conv_ctl,
               "max_err_step_converged": max([rows[i]["err"] for i in conv if rows[i]["err"] is not None], default=None)}
    json.dump({"summary": summary, "cells": {str(k): v for k, v in rows.items()}}, open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:6])
