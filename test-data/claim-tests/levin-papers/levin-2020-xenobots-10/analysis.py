#!/usr/bin/env python3
"""Test of levin-2020-xenobots-10: designs evolved on simulated land with tunable actuation
bound (paper: 52.7% ground contact), while adding first-order hydrodynamics and random phase
offsets yields ground-hugging designs (93.3%) that better match living organisms
(Kriegman et al. 2020, PNAS).

The authors' repository (github.com/skriegman/reconfigurable_organisms, CC0) deposits code but no
evolved designs or contact data, so this runs the pre-registered Tier B: the simplified voxel
mass-spring re-implementation in ../levin-2020-xenobots-06/voxsim.py. Pass 1 = land, phases
evolvable; pass 2 = water (gravity x 0.1, linear face drag), random clade-fixed phases. Pass-2
champions are taken from ../levin-2020-xenobots-06/derived/pass2_champions.json when present
(same seeds and settings), otherwise re-evolved. Exploratory (not pre-registered): the two
single-change conditions, to see which change drives any difference.

Run: python3 analysis.py [--jobs N]     (needs numpy and Node 20+; about 10 minutes on 10 cores)
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import urllib.request
from multiprocessing import Pool

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM_DIR = os.path.join(os.path.dirname(HERE), "levin-2020-xenobots-06")
sys.path.insert(0, SIM_DIR)
import voxsim as vs  # noqa: E402

DERIVED = os.path.join(HERE, "derived")
COMMIT = "9a5d685c2f26259122683d304e1ac98d54bac805"
RAW = f"https://raw.githubusercontent.com/skriegman/reconfigurable_organisms/{COMMIT}/"
REPO_FILES = ["exp/Locomotion_pass1.py", "exp/Locomotion_pass2.py",
              "data_analysis/Time_in_contact_with_ground.py"]
SEEDS = list(range(1, 11))
POP, GENS = 32, 50
N_PERM = 10000
PAPER = {"pass1": 0.527, "pass2": 0.933}

CONDITIONS = {
    "pass1_land_evolved_phase": (vs.LAND, True),
    "pass2_water_random_phase": (vs.WATER, False),
    "explore_land_random_phase": (vs.LAND, False),
    "explore_water_evolved_phase": (vs.WATER, True),
}


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    return dict(download_url=url,
                retrieved_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                byte_size=len(data), sha256=hashlib.sha256(data).hexdigest())


def run(job):
    cond, seed = job
    env, evolve_phase = CONDITIONS[cond]
    c = vs.evolve(seed, env, evolve_phase=evolve_phase, pop_size=POP, gens=GENS)
    r = vs.simulate(np.array([c["mat"]]), np.array([c["phase"]]), env)
    return cond, seed, dict(disp=float(r["disp"][0]), contact=float(r["contact"][0]),
                            n_voxels=int(np.sum(np.array(c["mat"]) > 0)),
                            frac_contractile=float(np.mean(np.array(c["mat"])[np.array(c["mat"]) > 0] == 3)))


def resim_pass2(champs):
    m = np.array([c["mat"] for c in champs])
    p = np.array([c["phase"] for c in champs])
    r = vs.simulate(m, p, vs.WATER)
    return {c["seed"]: dict(disp=float(r["disp"][i]), contact=float(r["contact"][i]),
                            n_voxels=int(np.sum(m[i] > 0)), frac_contractile=float(np.mean(m[i][m[i] > 0] == 3)))
            for i, c in enumerate(champs)}


def perm_test(a, b, rng):
    a, b = np.asarray(a), np.asarray(b)
    obs = b.mean() - a.mean()
    pooled = np.concatenate([a, b])
    hits = 0
    for _ in range(N_PERM):
        rng.shuffle(pooled)
        if abs(pooled[len(a):].mean() - pooled[:len(a)].mean()) >= abs(obs) - 1e-12:
            hits += 1
    return float(obs), (hits + 1) / (N_PERM + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()
    os.makedirs(DERIVED, exist_ok=True)
    repo_files = []
    for f in REPO_FILES:
        r = fetch(RAW + f)
        r["path"] = f
        repo_files.append(r)

    cached = os.path.join(SIM_DIR, "derived", "pass2_champions.json")
    jobs = [(c, s) for c in CONDITIONS for s in SEEDS]
    results = {c: {} for c in CONDITIONS}
    if os.path.exists(cached):
        with open(cached) as f:
            champs = json.load(f)
        if sorted(c["seed"] for c in champs) == SEEDS:
            results["pass2_water_random_phase"] = resim_pass2(champs)
            jobs = [j for j in jobs if j[0] != "pass2_water_random_phase"]
    with Pool(args.jobs) as pool:
        for cond, seed, r in pool.imap_unordered(run, jobs):
            results[cond][seed] = r

    rng = np.random.default_rng(10)
    p1 = np.array([results["pass1_land_evolved_phase"][s]["contact"] for s in SEEDS])
    p2 = np.array([results["pass2_water_random_phase"][s]["contact"] for s in SEEDS])
    diff, p = perm_test(p1, p2, rng)
    m1, m2 = float(p1.mean()), float(p2.mean())

    if m2 >= 0.85 and diff >= 0.20 and p < 0.05:
        verdict = "supports"
    elif diff <= 0.05:
        verdict = "refutes"
    else:
        verdict = "mixed"

    cond_summary = {}
    for c in CONDITIONS:
        con = np.array([results[c][s]["contact"] for s in SEEDS])
        dis = np.array([results[c][s]["disp"] for s in SEEDS])
        cond_summary[c] = dict(mean_contact=round(float(con.mean()), 4), min_contact=round(float(con.min()), 4),
                               max_contact=round(float(con.max()), 4), median_disp=round(float(np.median(dis)), 4),
                               n_airborne_majority=int((con < 0.5).sum()))
    summary = dict(
        verdict_by_preregistered_rule=verdict,
        pass1_mean_contact=round(m1, 4), pass2_mean_contact=round(m2, 4),
        difference_pass2_minus_pass1=round(diff, 4), permutation_p_two_sided=round(p, 5),
        paper=PAPER, conditions=cond_summary,
        per_trial={c: {str(s): {k: round(v, 4) if isinstance(v, float) else v for k, v in results[c][s].items()}
                       for s in SEEDS} for c in CONDITIONS},
        pass2_source="cached champions from levin-2020-xenobots-06" if os.path.exists(cached) else "re-evolved",
    )
    with open(os.path.join(DERIVED, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(DERIVED, "repo_files.json"), "w") as f:
        json.dump(repo_files, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "per_trial"}, indent=1))


if __name__ == "__main__":
    main()
