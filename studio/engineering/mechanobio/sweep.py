"""Replayable stiffness × viscosity factorial sweep and paired force-feedback intervention."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .controls import run_controls
from .model import Parameters, code_hashes, digest, environment, run_request, simulate


def _cell(item):
    stiffness, viscosity, seeds, duration, dt = item
    p = Parameters(long_term_stiffness_pN_nm=stiffness, viscosity_pN_s_nm=viscosity)
    values, mutant_values, traces = [], [], []
    for seed in seeds:
        base = simulate(p, duration_s=duration, dt_s=dt, seed=seed, frame_count=2)
        mutant = simulate(p, duration_s=duration, dt_s=dt, seed=seed, frame_count=2, force_feedback=False)
        values.append(base["summary"]["mean_traction_pN"])
        mutant_values.append(mutant["summary"]["mean_traction_pN"])
        traces.append({"seed": seed, "baseline": base["summary"], "constant_rupture_intervention": mutant["summary"]})
    sd = float(np.std(values, ddof=1))
    mean = float(np.mean(values))
    delta = np.asarray(mutant_values) - np.asarray(values)
    return {"long_term_stiffness_pN_nm": stiffness, "viscosity_pN_s_nm": viscosity,
            "replicates": traces, "n": len(seeds), "mean_traction_pN": mean, "sd_traction_pN": sd,
            "monte_carlo_mean_95_normal_interval_pN": [mean - 1.96 * sd / np.sqrt(len(seeds)), mean + 1.96 * sd / np.sqrt(len(seeds))],
            "constant_rupture_mean_traction_pN": float(np.mean(mutant_values)),
            "paired_intervention_mean_change_pN": float(np.mean(delta)),
            "paired_intervention_sd_pN": float(np.std(delta, ddof=1))}


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def artifact(path, role, media="application/json"):
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    return {"title": path.name, "uri": "urn:sha256:" + sha, "sha256": sha,
            "byte_size": len(data), "media_type": media, "role": role,
            "availability": "referenced", "license": None}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--replicates", type=int, default=12)
    parser.add_argument("--grid", type=int, default=5)
    parser.add_argument("--workers", type=int, choices=[1, 2], default=1)
    parser.add_argument("--duration", type=float, default=20)
    args = parser.parse_args()
    if os.environ.get("FRONTIER_MECHANOBIO_SWEEP_ACTIVE"):
        raise SystemExit("nested sweep refused")
    os.environ["FRONTIER_MECHANOBIO_SWEEP_ACTIVE"] = "1"
    if not 2 <= args.replicates <= 64 or not 2 <= args.grid <= 12 or not 1 <= args.duration <= 60:
        raise SystemExit("bounds: replicates2..64 grid2..12 duration1..60")
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    controls = run_controls()
    write_json(args.output / "controls.json", controls)
    if not controls["passed"]:
        raise SystemExit("numerical controls failed; sweep refused")
    request = {"schema": "frontier.mechanobio.request/1", "duration_s": args.duration}
    write_json(args.output / "request.json", request)
    result = run_request(request)
    write_json(args.output / "trajectory.json", result)
    protocol = {"stiffness_pN_nm": np.geomspace(0.01, 10, args.grid).tolist(),
                "viscosity_pN_s_nm": np.geomspace(0.01, 100, args.grid).tolist(),
                "seed_list": list(range(args.replicates)), "duration_s": args.duration, "dt_s": 0.01,
                "defaults": result["request_echo"]["parameters"],
                "intervention": "Bell force-dependent rupture versus constant unloaded rupture; paired seeds",
                "interval_scope": "Monte Carlo uncertainty only; normal approximation; not biological or parameter uncertainty"}
    write_json(args.output / "protocol.json", protocol)
    items = [(k, v, protocol["seed_list"], args.duration, 0.01) for k in protocol["stiffness_pN_nm"]
             for v in protocol["viscosity_pN_s_nm"]]
    if args.workers == 1:
        rows = list(map(_cell, items))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            rows = list(pool.map(_cell, items))
    sweep = {"schema": "frontier.mechanobio.sweep/1", "evidence_kind": "simulated",
             "protocol_sha256": digest(protocol), "rows": rows, "n_simulations": len(rows) * args.replicates * 2,
             "not_established": result["not_established"]}
    write_json(args.output / "sweep.json", sweep)
    env = environment()
    write_json(args.output / "environment.json", env)
    sources_path = Path(__file__).with_name("sources.json")
    manifest = {"schema": "frontier.mechanobio.simulation-manifest/1", "evidence_kind": "simulated",
                "source_receipt_sha256": hashlib.sha256(sources_path.read_bytes()).hexdigest(),
                "input_sha256": digest(protocol), "code_files": code_hashes(), "environment_sha256": digest(env),
                "elapsed_s": time.perf_counter() - started,
                "artifacts": [artifact(args.output / name, role) for name, role in
                              [("request.json", "input"), ("protocol.json", "protocol"), ("controls.json", "certificate"),
                               ("trajectory.json", "output"), ("sweep.json", "output"), ("environment.json", "environment")]]}
    write_json(args.output / "simulation-manifest.json", manifest)
    print(json.dumps({"output": str(args.output), "simulations": sweep["n_simulations"], "elapsed_s": manifest["elapsed_s"],
                      "controls_passed": controls["passed"], "protocol_sha256": digest(protocol)}), flush=True)


if __name__ == "__main__":
    main()
