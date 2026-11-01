"""levin-2015-place-05: migration then differentiation near step 8, free energy falling, fate
ambiguity resolved.  Run: python3 analysis.py"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "levin-2015-place-01"))
import morphogenesis as M  # noqa: E402

SEEDS = range(20)
INIT = {"code_randn_over_8": 1 / 8, "paper_log_precision_minus4": float(np.exp(2.0))}
# Primary runs are deterministic, as pre-registered. Sensitivity runs add the SPM generative
# process's sensory noise (precision exp(16)), omitted from the pre-registered re-implementation.
CONDITIONS = [(k, sd, False) for k, sd in INIT.items()] + \
    [(k + "+process_noise", sd, True) for k, sd in INIT.items()]


def first(traj, cond):
    return next((t["step"] for t in traj if cond(t)), None)


def main():
    records, demo, _, _ = M.load_source_info()
    tg = M.Target(demo["T"])
    rows, summary = [], {}
    for name, sd, noisy in CONDITIONS:
        for seed in SEEDS:
            v, ax, as_ = M.initial_state(tg, np.random.default_rng(seed), sd)
            nrng = np.random.default_rng(10_000 + seed) if noisy else None
            traj, _ = M.run(tg, v, ax, as_, noise_rng=nrng)
            d0 = traj[0]["mean_dist"]
            t_m = first(traj, lambda t: t["mean_dist"] < 0.5 * d0)
            t_d = first(traj, lambda t: t["correct_types"] >= 6 and t["mean_max_p"] > 0.5)
            end = traj[-1]
            resolved = end["mean_max_p"] > 0.5 and end["correct_types"] >= tg.n - 1
            f_ok = end["F"] < traj[1]["F"]
            ok = (t_m is not None and t_d is not None and t_m < t_d and 4 <= t_d <= 16
                  and f_ok and resolved)
            rows.append({"init": name, "seed": seed, "t_m": t_m, "t_d": t_d,
                         "mean_dist_0": round(d0, 4),
                         "F_1": round(traj[1]["F"], 2), "F_32": round(end["F"], 2),
                         "F_peak_step": int(np.argmax([t["F"] for t in traj[1:]]) + 1),
                         "mean_max_p_32": round(end["mean_max_p"], 4),
                         "correct_types_32": end["correct_types"],
                         "mean_max_p_by_step": [round(t["mean_max_p"], 3) for t in traj],
                         "mean_dist_by_step": [round(t["mean_dist"], 3) for t in traj],
                         "qualifies": bool(ok)})
        sub = [r for r in rows if r["init"] == name]
        tds = [r["t_d"] for r in sub if r["t_d"] is not None]
        summary[name] = {
            "init_sd": sd, "runs": len(sub),
            "qualifying_runs": sum(r["qualifies"] for r in sub),
            "median_t_m": float(np.median([r["t_m"] for r in sub if r["t_m"] is not None])),
            "median_t_d": float(np.median(tds)) if tds else None,
            "t_d_never_reached": sum(r["t_d"] is None for r in sub),
            "runs_t_d_le_t_m": sum(r["t_d"] is not None and r["t_m"] is not None
                                   and r["t_d"] <= r["t_m"] for r in sub),
            "runs_F_decreased": sum(r["F_32"] < r["F_1"] for r in sub),
            "median_F_peak_step": float(np.median([r["F_peak_step"] for r in sub])),
            "median_mean_max_p_32": float(np.median([r["mean_max_p_32"] for r in sub])),
        }
    M.dump(HERE / "derived" / "summary.json", {"sources": records, "summary": summary})
    M.dump(HERE / "derived" / "runs.json", rows)
    for k, s in summary.items():
        print(k, s)


if __name__ == "__main__":
    main()
