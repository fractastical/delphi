"""levin-2015-place-06: bisect at step 8, replicate each half, continue 32 steps; do both halves
regenerate the full target, after transient dedifferentiation?  Run: python3 analysis.py"""

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "levin-2015-place-01"))
import morphogenesis as M  # noqa: E402

SEEDS = range(20)
INIT = {"code_randn_over_8": 1 / 8, "paper_log_precision_minus4": float(np.exp(2.0))}
T_SPLIT = 8


def main():
    records, demo, _, _ = M.load_source_info()
    tg = M.Target(demo["T"])
    rows, summary = [], {}
    for name, sd in INIT.items():
        for seed in SEEDS:
            rng = np.random.default_rng(seed)
            v, ax, as_ = M.initial_state(tg, rng, sd)
            pre, states = M.run(tg, v, ax, as_, nbins=M.N_BINS)
            row = {"init": name, "seed": seed}
            both = True
            dip_any = False
            for half, upper in (("upper_tail_cells", True), ("lower_head_cells", False)):
                st = M.split_half(tg, states[T_SPLIT], upper, rng)
                a0 = M.assess(tg, st[0], st[1])
                traj, _ = M.run(tg, *st)
                end = traj[-1]
                ok = M.assembled(tg, end)
                dip = min(t["mean_max_p"] for t in traj[1:9]) < a0["mean_max_p"]
                both &= ok
                dip_any |= dip
                kept = sorted(tg.type[np.argmax(M.softmax(states[T_SPLIT][0]), 0)][
                    (np.argsort(-states[T_SPLIT][1][0]) if upper
                     else np.argsort(states[T_SPLIT][1][0]))[: tg.n // 2]].tolist())
                row[half] = {"kept_cell_types_at_split": kept,
                             "mean_max_p_at_split": round(a0["mean_max_p"], 4),
                             "min_mean_max_p_first8": round(min(t["mean_max_p"] for t in traj[1:9]), 4),
                             "rms_32": round(end["rms"], 4),
                             "correct_types_32": end["correct_types"],
                             "mean_max_p_32": round(end["mean_max_p"], 4),
                             "regenerated": bool(ok), "dedifferentiation_dip": bool(dip),
                             "F_1": round(traj[1]["F"], 2), "F_32": round(end["F"], 2)}
            row["both_regenerated"] = bool(both)
            row["dip_in_either_half"] = bool(dip_any)
            rows.append(row)
        sub = [r for r in rows if r["init"] == name]
        summary[name] = {
            "init_sd": sd, "runs": len(sub),
            "both_halves_regenerated": sum(r["both_regenerated"] for r in sub),
            "upper_regenerated": sum(r["upper_tail_cells"]["regenerated"] for r in sub),
            "lower_regenerated": sum(r["lower_head_cells"]["regenerated"] for r in sub),
            "runs_with_dedifferentiation_dip": sum(r["dip_in_either_half"] for r in sub),
            "median_rms_32_upper": float(np.median([r["upper_tail_cells"]["rms_32"] for r in sub])),
            "median_rms_32_lower": float(np.median([r["lower_head_cells"]["rms_32"] for r in sub])),
        }
    M.dump(HERE / "derived" / "summary.json", {"sources": records, "t_split": T_SPLIT,
                                                "summary": summary})
    M.dump(HERE / "derived" / "runs.json", rows)
    for k, s in summary.items():
        print(k, s)


if __name__ == "__main__":
    main()
