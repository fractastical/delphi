"""GPU base arm vs the NCA CPU rows (solver-A field "A"), under NCA's declared tolerances (nca-to-gpuops.md, 18:35Z): pattern flag equal on every
non-diverged cell; dominant mode equal where patterned; relative amplitude difference <= 1e-6. Reported, with subsets. Do not run on the real rows
before the pilot comparison file exists (PROTOCOL.md).
  python3 -m frontier_compute.compare_nca GPU_RESULTS.jsonl NCA_ROWS.jsonl OUT.json"""
import json, sys


def main(gpu_path, rows_path, out):
    gpu = {}
    for l in open(gpu_path):
        r = json.loads(l)
        if r["arm"] == "base":
            gpu[r["id"]] = r
    rows = {json.loads(l)["id"]: json.loads(l) for l in open(rows_path)}
    res, summ = {}, {"n_gpu": len(gpu), "n_rows": len(rows), "n_compared": 0, "flag_mismatch": [], "mode_mismatch": [], "amp_over_1e-6": [],
                     "gpu_diverged_cpu_not": [], "cpu_diverged_gpu_not": [], "max_rel_amp": 0.0, "missing_in_rows": []}
    subsets = {"all": lambda i: True, "id%100==0": lambda i: i % 100 == 0, "id%10==0": lambda i: i % 10 == 0}
    for i, g in gpu.items():
        a = (rows.get(i) or {}).get("A")
        if a is None:
            summ["missing_in_rows"].append(i)
            continue
        gd, cd = bool(g.get("diverged")), bool(a.get("diverged"))
        if gd != cd:
            summ["gpu_diverged_cpu_not" if gd else "cpu_diverged_gpu_not"].append(i)
            continue
        if gd:
            continue
        summ["n_compared"] += 1
        flag = g["pattern"] == a["pattern"]
        mode = (g["mode"] == a["mode"]) if a["pattern"] and g["pattern"] else True
        rel = abs(g["amp"] - a["amp"]) / max(abs(a["amp"]), 1e-300)
        res[i] = {"flag": flag, "mode": mode, "rel_amp": rel}
        if not flag: summ["flag_mismatch"].append(i)
        if flag and not mode: summ["mode_mismatch"].append(i)
        if rel > 1e-6: summ["amp_over_1e-6"].append(i)
        summ["max_rel_amp"] = max(summ["max_rel_amp"], rel)
    summ["by_subset"] = {}
    for name, f in subsets.items():
        ids = [i for i in res if f(i)]
        summ["by_subset"][name] = {"n": len(ids), "flag_eq": sum(res[i]["flag"] for i in ids), "mode_eq": sum(res[i]["mode"] for i in ids),
                                   "amp_le_1e-6": sum(res[i]["rel_amp"] <= 1e-6 for i in ids), "max_rel_amp": max((res[i]["rel_amp"] for i in ids), default=None)}
    summ["nca_tolerance_met_all_compared"] = not (summ["flag_mismatch"] or summ["mode_mismatch"] or summ["amp_over_1e-6"])
    json.dump({"summary": summ, "cells": {str(k): v for k, v in res.items()}}, open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in summ.items() if k != "by_subset"}, indent=1))
    print(json.dumps(summ["by_subset"], indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
