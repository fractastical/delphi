"""Held-out cell set for Experiment 2 (PROTOCOL2.md). Rule fixed BEFORE any held-out result exists.
New initial-state seed (not 101/102), draws disjoint from the pilot's (0,1), ids offset by 100000 so no id collides with the frozen grid."""
import hashlib, json, random, sys
from . import cells as C

SEED_NEW = int(hashlib.sha256(b"delphi-frontier-heldout-v1").hexdigest()[:8], 16) % 900000 + 1000          # 518331
SEED_RESERVED = int(hashlib.sha256(b"delphi-frontier-heldout-v1").hexdigest()[8:16], 16) % 900000 + 1000   # 478778 (unused)
RULE = {"seed": SEED_NEW, "draws_pool": [2, 3, 4, 5, 6, 7, 8, 9], "n_draws": 3, "draw_pick_rng_seed": SEED_RESERVED, "x": [2, 4],
        "rho": [0.7, 0.9, 1.5, 3.0], "eps": [0.01, 0.3], "models": ["schnakenberg", "brusselator"], "id_offset": 100000, "nframes": 100}


def build():
    tab = C.full_table(10)
    draws = sorted(random.Random(RULE["draw_pick_rng_seed"]).sample(RULE["draws_pool"], RULE["n_draws"]))
    out = []
    for c in tab:
        if c["seed"] == 101 and c["model"] in RULE["models"] and c["draw"] in draws and c["x"] in RULE["x"] and c["rho"] in RULE["rho"] and c["eps"] in RULE["eps"]:
            d = dict(c)
            d["id"] = c["id"] + RULE["id_offset"]
            d["seed"] = SEED_NEW
            d["source_id_seed101"] = c["id"]
            out.append(d)
    # video cells: per model, first chosen draw, x=4: (rho 3.0, eps 0.01), (rho 1.5, eps 0.3), (rho 0.7, eps 0.3)
    vids = []
    for m in RULE["models"]:
        for rho, eps in ((3.0, 0.01), (1.5, 0.3), (0.7, 0.3)):
            vids += [c["id"] for c in out if c["model"] == m and c["draw"] == draws[0] and c["x"] == 4 and c["rho"] == rho and c["eps"] == eps]
    return {"rule": RULE, "draws_chosen": draws, "table_sha256": C.table_sha(tab), "video_ids": vids, "cells": out}


if __name__ == "__main__":
    d = build()
    json.dump(d, open(sys.argv[1], "w"), sort_keys=True, indent=0, allow_nan=False)
    print(len(d["cells"]), "cells; draws", d["draws_chosen"], "video ids", d["video_ids"])
