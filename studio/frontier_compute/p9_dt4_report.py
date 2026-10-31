"""Protocol 9 dt/4 follow-up: for the frozen-grid cells that changed between dt 0.02 and 0.01 (plus 48 random unchanged controls), does dt = 0.005 agree with dt = 0.01?
  python3 -m frontier_compute.p9_dt4_report FULL_CELLS.json P8_RESULTS.jsonl DT4_RESULTS.jsonl NCA_B.jsonl DT4_SUBSET.xz OUT.json
Reports counts only; NCA categories with B fixed. Not a gate."""
import json, sys
from collections import Counter
from . import cols
from .p8_report import load
from .atlas_report import category


def main(cells_p, p8_p, dt4_p, b_p, sub_p, out):
    C = {c["id"]: c for c in json.load(open(cells_p))["cells"]}
    A1, A2, B = load(p8_p, "dt2"), load(dt4_p, "dt4"), load(b_p)
    _, extra = cols.decode(sub_p); changed, ctrl = set(extra["changed_ids"]), set(extra["control_ids"])
    res = {}
    for name, ids in (("changed_between_dt0.02_and_0.01", changed), ("unchanged_controls", ctrl)):
        n = fl = md = am = cc = nr = 0
        for i in ids:
            a1, a2 = A1[i], A2.get(i)
            if a2 is None or a2.get("not_run") or a2.get("out_of_budget"):
                nr += 1; continue
            n += 1
            ok = not (a1.get("diverged") or a2.get("diverged"))
            fl += bool(ok and a1["pattern"] != a2["pattern"])
            md += bool(ok and a1["pattern"] and a2["pattern"] and a1["mode"] != a2["mode"])
            am += bool(ok and a1["pattern"] and a2["pattern"] and abs(a1["amp"] - a2["amp"]) > 0.1 * a1["amp"])
            cc += category(a1, B[i])[0] != category(a2, B[i])[0]
        res[name] = {"n_compared": n, "not_run": nr, "flag_flips_dt0.01_to_0.005": fl, "patterned_mode_flips": md, "amp_change_gt_10pct": am, "category_changes": cc}
    json.dump(res, open(out, "w"), indent=1, sort_keys=True, allow_nan=False); print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:7])
