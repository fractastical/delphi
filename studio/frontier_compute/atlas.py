"""Atlas cell set for Protocol 6: a HELD-OUT replication of the frozen NCA sweep design on NEW parameter draws (ensemble master seed 20261101, 20 draws per model,
same stated prior, same factors) with a NEW initial-state seed (518331). Rules fixed before any atlas result exists."""
import hashlib, json, random, sys
from . import cells as C
from scopedesk.oracles.nonlinear_sweep import ensemble as E

SEED_ENS = 20261101
SEED_IC = 518331
ID_OFFSET = 200000
CTRL_STRATA = {"rho": [0.7, 0.97, 1.5, 3.0], "eps": [0.01, 0.3], "per_stratum": 3, "rng": 20261102, "draws": [0, 1, 2, 3, 4]}


def build():
    raw = E.build(20, seed=SEED_ENS)
    out = []
    for c in raw:
        if c["seed"] != E.PAIRED_SEEDS[0]:
            continue                          # one IC seed per cell: take the seed-101 copies and overwrite the seed
        d = C.derive(c)
        d["source_id"] = c["id"]
        d["id"] = c["id"] + ID_OFFSET
        d["seed"] = SEED_IC
        out.append(d)
    sub_ids = [d["id"] for d in out if d["draw"] in CTRL_STRATA["draws"]]
    rng = random.Random(CTRL_STRATA["rng"])
    ctrl = []
    for m in ("schnakenberg", "brusselator"):
        for rho in CTRL_STRATA["rho"]:
            for eps in CTRL_STRATA["eps"]:
                pool = sorted(d["id"] for d in out if d["model"] == m and d["rho"] == rho and d["eps"] == eps and d["draw"] in CTRL_STRATA["draws"])
                ctrl += sorted(rng.sample(pool, CTRL_STRATA["per_stratum"]))
    return {"rule": {"ensemble_seed": SEED_ENS, "ic_seed": SEED_IC, "n_draws_per_model": 20, "id_offset": ID_OFFSET, "ctrl": CTRL_STRATA}, "cells": out,
            "refine_subset_ids": sub_ids, "control_ids": sorted(ctrl)}


if __name__ == "__main__":
    d = build()
    json.dump(d, open(sys.argv[1], "w"), sort_keys=True, indent=0, allow_nan=False)
    frozen = {(c["model"], json.dumps(c["params"], sort_keys=True)) for c in C.full_table(10)}
    new = {(c["model"], json.dumps(c["params"], sort_keys=True)) for c in d["cells"]}
    print(len(d["cells"]), "cells;", len(new), "parameter sets; overlap with frozen draws:", len(frozen & new), "; refine subset", len(d["refine_subset_ids"]), "; control", len(d["control_ids"]))
