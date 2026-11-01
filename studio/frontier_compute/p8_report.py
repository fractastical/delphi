"""Protocol 8 analysis: effect of halving dt on solver A over a whole cell grid, in NCA's own categories (B = the independent CPU BDF result, fixed), plus the control validity gate.
  python3 -m frontier_compute.p8_report GRID_NAME CELLS_FULL.json A0.jsonl A1.jsonl B.jsonl OUT.json     (jsonl rows: id, arm, pattern, mode, amp, settled, diverged)
Definitions are fixed in PROTOCOL8.md; nothing here defines a new outcome."""
import json, sys
from collections import Counter, defaultdict
from . import VENDOR  # noqa: F401
from scopedesk.oracles.nonlinear_sweep import analyze as NA
from .atlas_report import category


def load(path, arm=None):
    d = {}
    for l in open(path):
        r = json.loads(l)
        if arm is None or r.get("arm") == arm:
            d[r["id"]] = r
    return d


def grid_report(cells, A0, A1, B):
    ids = [i for i in cells if i in A0 and i in A1 and not A1[i].get("not_run") and not A0[i].get("not_run")]
    rows0, rows1, strata = [], [], defaultdict(Counter)
    flag = modef = ampf = catc = 0
    for i in ids:
        c = cells[i]; a0, a1, b = A0[i], A1[i], B[i]
        c0, w0 = category(a0, b); c1, w1 = category(a1, b)
        base = {"id": i, "model": c["model"], "draw": c["draw"], "rho": c["rho"], "x": c["x"], "eps": c["eps"], "seed": c["seed"], "linear": c["linear"], "linear_fastest_mode": c["linear_fastest_mode"]}
        rows0.append({**base, "category": c0, "why": w0, "mode": a0.get("mode") if c0 == "pattern" else None})
        rows1.append({**base, "category": c1, "why": w1, "mode": a1.get("mode") if c1 == "pattern" else None})
        both_ok = not (a0.get("diverged") or a1.get("diverged"))
        f = both_ok and a0["pattern"] != a1["pattern"]
        m = both_ok and a0["pattern"] and a1["pattern"] and a0["mode"] != a1["mode"]
        am = both_ok and a0["pattern"] and a1["pattern"] and abs(a0["amp"] - a1["amp"]) > 0.1 * a0["amp"]
        flag += bool(f); modef += bool(m); ampf += bool(am); catc += c0 != c1
        for key in (("model", c["model"]), ("rho", c["rho"]), ("x", c["x"]), ("eps", c["eps"])):
            strata[key]["n"] += 1; strata[key]["flag_flip"] += bool(f); strata[key]["mode_flip"] += bool(m); strata[key]["cat_change"] += c0 != c1
    q0, q1 = NA.quantities(rows0), NA.quantities(rows1)
    pick = lambda q: {k: q[k] for k in ("R1_linear_stable_but_nonlinear_pattern", "R2_linear_unstable_but_no_pattern", "R3_linear_unstable_pattern_with_different_dominant_mode", "unresolved_mass")}
    return {"n_cells_compared": len(ids), "flag_flips": flag, "patterned_mode_flips": modef, "patterned_amp_change_gt_10pct": ampf, "category_changes": catc,
            "R_at_dt0.02": pick(q0), "R_at_dt0.01": pick(q1), "by_stratum": {f"{k[0]}={k[1]}": dict(v) for k, v in sorted(strata.items(), key=str)}}


if __name__ == "__main__":
    name, cells_p, a0_p, a1_p, b_p, out = sys.argv[1:7]
    cells = {c["id"]: c for c in json.load(open(cells_p))["cells"]}
    rep = grid_report(cells, load(a0_p, "base"), load(a1_p, "dt2"), load(b_p))
    json.dump({"grid": name, **rep}, open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print(json.dumps({k: v for k, v in rep.items() if k != "by_stratum"}, indent=1))
