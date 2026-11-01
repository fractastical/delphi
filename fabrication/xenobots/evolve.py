"""Evolve a new xenobot design with the repo's voxel soft-body simulator and save its genome.

Reuses, unchanged, the simulator and evolutionary loop of the pre-registered claim test
test-data/claim-tests/levin-papers/levin-2020-xenobots-06 (voxsim.py + voxsim.mjs): a 5x5x4
workspace, cells empty / passive / contractile, 2 Hz sinusoidal actuation with a per-cell phase,
truncation selection on net displacement of the centre of mass. This is a stand-in for the
Voxelyze/VoxCad pipeline of Kriegman et al. 2020 (PNAS, 10.1073/pnas.1910837117), not a port of it.

    python3 evolve.py --seed 101 --env water --gens 20 --out designs/

Writes designs/evolved-<env>-s<seed>.json with the genome (mat, phase), the fitness, the run
parameters and the files it came from. Fitness is in simulator units (voxel edges of net
displacement over a 10 s evaluation), is a prediction of the simulator, and says nothing about
any physical print. Plain python3 + numpy + node, like the original test.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEST = os.path.join(ROOT, "test-data", "claim-tests", "levin-papers", "levin-2020-xenobots-06")
sys.path.insert(0, TEST)
import voxsim  # noqa: E402


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--env", choices=["water", "land"], default="water",
                    help="water: 0.1 g plus drag (the paper's second pass); land: full g, no drag")
    ap.add_argument("--gens", type=int, default=20)
    ap.add_argument("--pop", type=int, default=32)
    ap.add_argument("--fixed-phase", action="store_true",
                    help="phases fixed per clade (the claim-test setting); default lets phase evolve")
    ap.add_argument("--out", default=os.path.join(HERE, "designs"))
    a = ap.parse_args()

    env = voxsim.WATER if a.env == "water" else voxsim.LAND
    t0 = time.time()
    res = voxsim.evolve(a.seed, env, evolve_phase=not a.fixed_phase, pop_size=a.pop, gens=a.gens,
                        log=lambda s: print(s, file=sys.stderr))
    elapsed = time.time() - t0

    import numpy as np
    mat = np.array(res["mat"])
    out = {
        "name": f"evolved-{a.env}-s{a.seed}",
        "mat": res["mat"],
        "phase": [round(p, 6) for p in res["phase"]],
        "shape": [voxsim.NX, voxsim.NY, voxsim.NZ],
        "fitness_sim_units": round(res["fitness"], 4),
        "gen0_best_sim_units": round(max(res["gen0_fitness"]), 4),
        "best_by_generation": [round(b, 4) for b in res["best_hist"]],
        "n_voxels": int((mat > 0).sum()),
        "n_contractile": int((mat == 3).sum()),
        "params": {"seed": a.seed, "env": a.env, "env_values": env, "generations": a.gens,
                   "population": a.pop, "evolve_phase": not a.fixed_phase,
                   "eval_seconds": voxsim.EVAL, "actuation_hz": voxsim.FREQ},
        "simulator": {
            "kind": "simulated",
            "files": {os.path.relpath(os.path.join(TEST, f), ROOT): sha256(os.path.join(TEST, f))
                      for f in ("voxsim.py", "voxsim.mjs")},
            "stand_in_for": "github.com/skriegman/reconfigurable_organisms (Voxelyze/VoxCad), doi:10.1073/pnas.1910837117",
        },
        "wall_seconds": round(elapsed, 1),
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, out["name"] + ".json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"{path}: {out['n_voxels']} voxels ({out['n_contractile']} contractile), "
          f"fitness {out['fitness_sim_units']} (gen0 best {out['gen0_best_sim_units']}), {elapsed:.0f}s")


if __name__ == "__main__":
    main()
