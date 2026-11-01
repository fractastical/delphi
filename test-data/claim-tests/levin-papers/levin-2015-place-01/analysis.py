"""levin-2015-place-01: do identical cells sharing one generative model self-assemble into the
8-cell head-body-tail target under free-energy minimisation?  Run: python3 analysis.py"""

from pathlib import Path

import numpy as np

import morphogenesis as M

HERE = Path(__file__).parent
SEEDS = range(20)
# Paper: "small random expectations with a log precision of minus four" (sd = e^2);
# DEM_morphogenesis.m: v = randn(n,n)/8 (log precision ~ +4.16). Both are run.
INIT = {"code_randn_over_8": 1 / 8, "paper_log_precision_minus4": float(np.exp(2.0))}
# Primary runs are deterministic, as pre-registered. Sensitivity runs add the SPM generative
# process's sensory noise (precision exp(16)), omitted from the pre-registered re-implementation.
CONDITIONS = [(k, sd, False) for k, sd in INIT.items()] + \
    [(k + "+process_noise", sd, True) for k, sd in INIT.items()]


def main():
    records, demo, demo_main, adem_t = M.load_source_info()
    tg = M.Target(demo["T"])
    rows, summary = [], {}
    for name, sd, noisy in CONDITIONS:
        passes, fdrop = 0, 0
        for seed in SEEDS:
            v, ax, as_ = M.initial_state(tg, np.random.default_rng(seed), sd)
            nrng = np.random.default_rng(10_000 + seed) if noisy else None
            traj, _ = M.run(tg, v, ax, as_, noise_rng=nrng)
            end = traj[-1]
            ok = M.assembled(tg, end)
            f_ok = bool(traj[-1]["F"] < traj[1]["F"])
            ok = bool(ok)
            passes += int(ok and f_ok)
            fdrop += int(f_ok)
            rows.append({"init": name, "seed": seed, "rms_32": round(end["rms"], 4),
                         "correct_types_32": end["correct_types"],
                         "mean_max_p_32": round(end["mean_max_p"], 4),
                         "F_1": round(traj[1]["F"], 2), "F_32": round(end["F"], 2),
                         "F_max": round(max(t["F"] for t in traj[1:]), 2),
                         "assembled": bool(ok), "pass": bool(ok and f_ok)})
        sub = [r for r in rows if r["init"] == name]
        summary[name] = {
            "init_sd": sd, "runs": len(sub), "passing_runs": passes, "F_decreased_runs": fdrop,
            "median_rms_32": float(np.median([r["rms_32"] for r in sub])),
            "median_correct_types_32": float(np.median([r["correct_types_32"] for r in sub])),
            "median_F_1": float(np.median([r["F_1"] for r in sub])),
            "median_F_32": float(np.median([r["F_32"] for r in sub])),
        }
    out = {
        "sources": records,
        "demo_defaults": {"SPLIT": demo["SPLIT"], "N": demo["N"], "L": demo["L"],
                          "cells_in_default_target": tg.n,
                          "header_comment_cell_count": demo["header_cells"],
                          "target_identical_spm12_vs_main": True,
                          "spm_ADEM_time_is_iY_over_nY": adem_t},
        "target": {"X": tg.X.tolist(), "S": tg.S.tolist(), "type": tg.type.tolist(),
                   "min_spacing": tg.min_spacing, "rms_threshold": 0.5 * tg.min_spacing},
        "summary": summary,
    }
    M.dump(HERE / "derived" / "summary.json", out)
    M.dump(HERE / "derived" / "runs.json", rows)
    for k, s in summary.items():
        print(k, s)
    print(out["demo_defaults"])


if __name__ == "__main__":
    main()
