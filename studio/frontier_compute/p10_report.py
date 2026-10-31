"""Protocol 10 verdict from the GPU body_results.json (+ optional CPU N=256 reference summary), gates exactly as frozen in PROTOCOL10.md.
  python3 -m frontier_compute.p10_report BODY_RESULTS.json OUT.json [CPU_REF_SUMMARY.json]  (the official CPU analytic control must already have passed: results/compute/p10/cpu/penalized_controls.json)"""
import json, sys


def verdict(R, cpu=None, control_pass=True):
    a, b, c = R["runs"].get("N1024_dt0.0015"), R["runs"].get("N512_dt0.003"), R["runs"].get("N512_dt0.0015")
    out = {"inputs_present": {"a": a is not None, "b": b is not None, "c": c is not None}}
    if not (a and b and c):
        out["label"] = "INCOMPLETE"; return out
    fin = all(r["finite"] for r in (a, b, c))
    B = {"finite": fin, "St_in_[0.15,0.21]": 0.15 <= a["St"] <= 0.21, "Cd_in_[1.1,1.9]": 1.1 <= a["Cd_mean"] <= 1.9, "Cl_rms_le_0.45": a["Cl_rms"] <= 0.45, "periods_ge_6": a["n_periods_in_window"] >= 6}
    rel = lambda x, y: abs(x - y) / abs(y)
    C = {"St_N1024_vs_N512_le_5pct": rel(b["St"], a["St"]) <= 0.05, "Cd_N1024_vs_N512_le_10pct": rel(b["Cd_mean"], a["Cd_mean"]) <= 0.10,
         "St_dt_halving_N512_le_2pct": rel(c["St"], b["St"]) <= 0.02, "Cd_dt_halving_N512_le_3pct": rel(c["Cd_mean"], b["Cd_mean"]) <= 0.03}
    out.update({"B_physics_bands_run_a": B, "C_convergence": C, "measured": {k: {m: r[m] for m in ("N", "dt", "Cd_mean", "Cl_rms", "St", "n_periods_in_window", "wall_s")} for k, r in (("a_N1024", a), ("b_N512", b), ("c_N512_dt_half", c))},
                "rel_diffs": {"St_a_vs_b": rel(b["St"], a["St"]), "Cd_a_vs_b": rel(b["Cd_mean"], a["Cd_mean"]), "St_b_vs_c": rel(c["St"], b["St"]), "Cd_b_vs_c": rel(c["Cd_mean"], b["Cd_mean"])}})
    if cpu:
        out["cpu_N256_reference_vs_a_(reported_not_gated)"] = {"St": cpu["St"], "Cd": cpu["Cd_mean"], "Cl_rms": cpu["Cl_rms"], "St_rel_diff": rel(cpu["St"], a["St"]), "Cd_rel_diff": rel(cpu["Cd_mean"], a["Cd_mean"])}
    ok = control_pass and fin and all(B.values()) and all(C.values())
    out["label"] = "PASS" if ok else ("FAIL" if not fin else "PARTIAL")
    out["failing"] = [k for d in (B, C) for k, v in d.items() if not v] + ([] if control_pass else ["official_cpu_control"])
    return out


if __name__ == "__main__":
    R = json.load(open(sys.argv[1])); cpu = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    ctl = json.load(open("results/compute/p10/cpu/penalized_controls.json"))["gate"]["ALL"]
    v = verdict(R, cpu, ctl); json.dump(v, open(sys.argv[2], "w"), indent=1, sort_keys=True, allow_nan=False); print(json.dumps(v, indent=1))
