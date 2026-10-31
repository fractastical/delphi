"""Produce an illustrative load/rupture trajectory and paired no-feedback arm."""
import argparse
import hashlib
import json
from pathlib import Path

from .model import Parameters, run_request, simulate
from .sweep import artifact, write_json


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).with_name("example_request.json")
    request = json.loads(source.read_text())
    result = run_request(request)
    write_json(args.directory / "feedback-trajectory.json", result)
    p = Parameters(**request["parameters"])
    mutant = simulate(p, duration_s=request["duration_s"], dt_s=request["dt_s"], seed=request["seed"],
                      frame_count=request["frame_count"], force_feedback=False)
    write_json(args.directory / "constant-rupture-trajectory.json", {
        "schema": "frontier.mechanobio.intervention/1", "evidence_kind": "simulated",
        "intervention": "Bell exponential replaced by1; other parameters and seed unchanged",
        "baseline_request": result["request_echo"], "baseline_provenance": result["provenance"], **mutant})
    write_json(args.directory / "feedback-simulation-manifest.json", {
        "schema": "frontier.mechanobio.simulation-manifest/1", "evidence_kind": "simulated",
        "request_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "provenance": result["provenance"],
        "artifacts": [artifact(args.directory / name, "output") for name in
                      ["feedback-trajectory.json", "constant-rupture-trajectory.json"]]})


if __name__ == "__main__":
    main()
