"""Protocol 8 control validity: GPU solver A at dt=0.01 vs CPU solver A at dt=0.01 on the 48 atlas control cells, revised agreement criterion with a FLAT whole-field tolerance (1e-8)
on ALL controls (same algorithm, same dt: only roundoff differs). Usage: python3 -m frontier_compute.p8_validity ATLAS_DT2_RESULTS.jsonl ATLAS_DT2_FIELDS.npz CPU_DIR OUT.json"""
import json, sys
import numpy as np
from . import VENDOR  # noqa: F401
from scopedesk.oracles import kinetics
from . import cols
from .compare2 import agree_revised

TOL = 1e-8


def main(res_p, fld_p, cpu_dir, out):
    cells, extra = cols.decode("inputs/atlas_cols.xz"); C = {c["id"]: c for c in cells}
    G = {json.loads(l)["id"]: json.loads(l) for l in open(res_p) if json.loads(l).get("arm") == "dt2"}
    GF = np.load(fld_p); CF = np.load(f"{cpu_dir}/cpu_A_dt2_fields.npz")
    CA = {json.loads(l)["id"]: json.loads(l) for l in open(f"{cpu_dir}/cpu_A_dt2_ctrl.jsonl")}
    rows, fail = {}, []
    for i in extra["control_ids"]:
        g, a, c = G[i], CA[i], C[i]
        ust = abs(float(kinetics.steady(c["model"], kinetics.params(c["model"], c["params"]))[0]))
        err = None if (g.get("diverged") or a.get("diverged")) else float(np.abs(GF[f"{i}_dt2_u_final"] - CF[f"{i}_A_dt2_u"]).max() / ust)
        ok = agree_revised(g, a, err, TOL)
        rows[i] = {"err": err, "ok": ok, "cpu_pattern": a.get("pattern"), "gpu_pattern": g.get("pattern")}
        if not ok:
            fail.append(i)
    s = {"validity": "VALIDATED" if not fail else "NOT_VALIDATED", "n": len(rows), "failing_ids": fail, "max_err": max(r["err"] for r in rows.values() if r["err"] is not None), "tol": TOL}
    json.dump({"summary": s, "controls": {str(k): v for k, v in rows.items()}}, open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print(json.dumps(s, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:5])
