#!/usr/bin/env python3
"""Test of levin-2020-xenobots-06: selection for locomotion under random, clade-fixed actuation
phases evolves morphologies that derandomize the global movement (Kriegman et al. 2020, PNAS).

The authors' repository (github.com/skriegman/reconfigurable_organisms, CC0) deposits code but no
evolved designs, run logs or simulation outputs, so this runs the pre-registered Tier B: a
simplified voxel mass-spring re-implementation (voxsim.py / voxsim.mjs) of the paper's
second-pass setting (water: reduced gravity plus surface drag; random phase offsets fixed per
clade; selection on net displacement), with layout-shuffle and fresh-phase controls.

Run: python3 analysis.py [--jobs N]     (needs numpy and Node 20+; about 5 minutes on 10 cores)
"""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
import tarfile
import urllib.request
from multiprocessing import Pool

import numpy as np

import voxsim as vs

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
COMMIT = "9a5d685c2f26259122683d304e1ac98d54bac805"
TARBALL = f"https://codeload.github.com/skriegman/reconfigurable_organisms/tar.gz/{COMMIT}"
RAW = f"https://raw.githubusercontent.com/skriegman/reconfigurable_organisms/{COMMIT}/"
REPO_FILES = ["exp/Locomotion_pass1.py", "exp/Locomotion_pass2.py",
              "data_analysis/Time_in_contact_with_ground.py", "base.py"]

SEEDS = list(range(1, 11))
POP, GENS = 32, 50
N_RANDOM = 200
N_SHUFFLE = 20
N_FRESH = 20
CONTROL_SEED = 2020


def fetch(url):
    with urllib.request.urlopen(url, timeout=120) as r:
        data = r.read()
    return data, dict(download_url=url,
                      retrieved_at=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      byte_size=len(data), sha256=hashlib.sha256(data).hexdigest())


def inspect_repository():
    """Download the pinned repository and record what it deposits: no evolved designs, run
    pickles or fitness/contact outputs, only code. Returns file records and the inventory."""
    data, rec = fetch(TARBALL)
    names = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf.getmembers():
            if m.isfile():
                names.append(m.name.split("/", 1)[1])
    outputs = [n for n in names if n.endswith((".pickle", ".pkl", ".vxa", ".npy", ".csv"))
               or "/results/" in n or "fitnessFiles" in n or "bestSoFar" in n]
    files = [rec]
    for f in REPO_FILES:
        _, r = fetch(RAW + f)
        r["path"] = f
        files.append(r)
    return files, dict(n_files=len(names), candidate_output_files=outputs)


def run_trial(seed):
    return vs.evolve(seed, vs.WATER, evolve_phase=False, pop_size=POP, gens=GENS)


def sim_chunk(args):
    mats, phases, env, record = args
    out = vs.simulate(np.array(mats), np.array(phases), env, record=record)
    return {k: v.tolist() for k, v in out.items()}


def parallel_sim(pool, mats, phases, env, record=False, chunk=10):
    jobs = [(mats[i:i + chunk], phases[i:i + chunk], env, record) for i in range(0, len(mats), chunk)]
    res = pool.map(sim_chunk, jobs)
    return {k: np.concatenate([np.array(r[k]) for r in res]) for k in res[0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=os.cpu_count())
    args = ap.parse_args()
    os.makedirs(DERIVED, exist_ok=True)

    repo_files, inventory = inspect_repository()

    with Pool(args.jobs) as pool:
        champs = pool.map(run_trial, SEEDS)

        rng = np.random.default_rng(CONTROL_SEED)
        rand_m = np.array([vs.random_body(rng) for _ in range(N_RANDOM)])
        rand_p = np.array([vs.random_phase(rng) for _ in range(N_RANDOM)])
        rand = parallel_sim(pool, rand_m, rand_p, vs.WATER, record=True)

        c_m = np.array([c["mat"] for c in champs])
        c_p = np.array([c["phase"] for c in champs])
        champ = parallel_sim(pool, c_m, c_p, vs.WATER, record=True)

        sh_m, sh_p, fr_m, fr_p = [], [], [], []
        for m, p in zip(c_m, c_p):
            pres = np.nonzero(m > 0)[0]
            for _ in range(N_SHUFFLE):
                mm = m.copy()
                mm[pres] = rng.permutation(m[pres])
                sh_m.append(mm)
                sh_p.append(p)
            for _ in range(N_FRESH):
                fr_m.append(m)
                fr_p.append(vs.random_phase(rng))
        shuf = parallel_sim(pool, np.array(sh_m), np.array(sh_p), vs.WATER)
        fresh = parallel_sim(pool, np.array(fr_m), np.array(fr_p), vs.WATER)

    rd = rand["disp"]
    r_mean, r_med, r_p95 = float(rd.mean()), float(np.median(rd)), float(np.percentile(rd, 95))
    cd = champ["disp"]
    ratio = cd / r_mean
    above95 = cd > r_p95
    shuf_med = np.median(shuf["disp"].reshape(len(SEEDS), N_SHUFFLE), axis=1)
    shuf_ratio = shuf_med / cd
    fresh_med = np.median(fresh["disp"].reshape(len(SEEDS), N_FRESH), axis=1)
    fresh_ratio = fresh_med / cd

    a_pass = np.median(ratio) >= 2 and above95.mean() >= 0.8
    b_pass = np.median(shuf_ratio) <= 0.7
    c_pass = (fresh_med > r_p95).mean() >= 0.7
    a_fail = np.median(ratio) <= 1.2 or above95.mean() < 0.5
    b_none = np.median(shuf_ratio) >= 0.95
    c_fail = (fresh_med <= r_med).mean() >= 0.5
    if a_pass and b_pass and c_pass:
        verdict = "supports"
    elif a_fail or (b_none and c_fail):
        verdict = "refutes"
    else:
        verdict = "mixed"

    straight_c = champ["disp"] / np.maximum(champ["path_len"], 1e-9)
    straight_r = rand["disp"] / np.maximum(rand["path_len"], 1e-9)
    n_vox = (c_m > 0).sum(1)
    frac_act = (c_m == 3).sum(1) / n_vox
    rn_vox = (rand_m > 0).sum(1)
    rfrac_act = (rand_m == 3).sum(1) / rn_vox

    per_trial = [dict(seed=s, champion_disp=round(float(cd[i]), 4), gen0_best=round(champs[i]["best_hist"][0], 4),
                      ratio_to_random_mean=round(float(ratio[i]), 3),
                      above_random_p95=bool(above95[i]),
                      layout_shuffle_median_disp=round(float(shuf_med[i]), 4),
                      layout_shuffle_ratio=round(float(shuf_ratio[i]), 3),
                      fresh_phase_median_disp=round(float(fresh_med[i]), 4),
                      fresh_phase_ratio=round(float(fresh_ratio[i]), 3),
                      fresh_phase_above_random_p95=bool(fresh_med[i] > r_p95),
                      straightness=round(float(straight_c[i]), 3),
                      n_voxels=int(n_vox[i]), frac_contractile=round(float(frac_act[i]), 3),
                      contact_fraction=round(float(champ["contact"][i]), 4))
                 for i, s in enumerate(SEEDS)]

    summary = dict(
        verdict_by_preregistered_rule=verdict,
        criteria=dict(a_pass=bool(a_pass), b_pass=bool(b_pass), c_pass=bool(c_pass),
                      a_fail=bool(a_fail), b_no_dependence=bool(b_none), c_fail=bool(c_fail)),
        random_designs=dict(n=N_RANDOM, mean_disp=round(r_mean, 4), median_disp=round(r_med, 4),
                            p95_disp=round(r_p95, 4), median_straightness=round(float(np.median(straight_r)), 3),
                            mean_frac_contractile=round(float(rfrac_act.mean()), 3),
                            mean_n_voxels=round(float(rn_vox.mean()), 1)),
        champions=dict(n=len(SEEDS), median_disp=round(float(np.median(cd)), 4),
                       median_ratio_to_random_mean=round(float(np.median(ratio)), 3),
                       frac_above_random_p95=float(above95.mean()),
                       median_layout_shuffle_ratio=round(float(np.median(shuf_ratio)), 3),
                       median_fresh_phase_ratio=round(float(np.median(fresh_ratio)), 3),
                       frac_fresh_phase_above_random_p95=float((fresh_med > r_p95).mean()),
                       frac_fresh_phase_at_or_below_random_median=float((fresh_med <= r_med).mean()),
                       median_straightness=round(float(np.median(straight_c)), 3),
                       mean_frac_contractile=round(float(frac_act.mean()), 3),
                       mean_n_voxels=round(float(n_vox.mean()), 1)),
        per_trial=per_trial,
        repository_inventory=inventory,
    )
    with open(os.path.join(DERIVED, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    with open(os.path.join(DERIVED, "pass2_champions.json"), "w") as f:
        json.dump([dict(seed=c["seed"], mat=c["mat"], phase=[round(x, 6) for x in c["phase"]],
                        fitness=c["fitness"], best_hist=[round(x, 4) for x in c["best_hist"]])
                   for c in champs], f)
    with open(os.path.join(DERIVED, "repo_files.json"), "w") as f:
        json.dump(repo_files, f, indent=1)
    print(json.dumps({k: summary[k] for k in ("verdict_by_preregistered_rule", "criteria",
                                              "random_designs", "champions")}, indent=1))


if __name__ == "__main__":
    main()
