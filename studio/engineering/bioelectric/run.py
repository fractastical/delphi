"""Replayable bundle: membrane scenarios, controls, parameter atlas and rendering."""
from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

from .model import BOUNDS, DEFAULTS, SOURCES, code_hashes, simulate


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def file_receipt(path):
    return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}


def atlas(output):
    """49 real distinct integrations. Every heatmap cell points to its own frames."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sodium = [0, .25, .5, .75, 1., 1.25, 1.5]
    gaps = [0, .125, .25, .5, 1., 1.5, 2.]
    folder = output / "atlas"
    folder.mkdir(exist_ok=True)
    rows, matrix = [], []
    for gi, gap in enumerate(gaps):
        band = []
        for si, scale in enumerate(sodium):
            result = simulate({"gap_mS_cm2": gap, "sodium_scale": scale})
            if result["status"] != "completed":
                raise RuntimeError(f"atlas cell failed: {gap}, {scale}: {result}")
            relative = f"atlas/gap{gi}-na{si}.json"
            fields = ["schema", "status", "evidence_kind", "model_id", "request", "n_cells", "time_ms", "voltage_mV", "metrics", "simulationAction"]
            saved = {field: result[field] for field in fields}
            saved["source_envelope_ref"] = "../sources.json"
            saved["scope"] = "Assumed gap coupling and channel-density scenarios; no organism or developmental calibration"
            write(output / relative, saved)
            row = {"gap_index": gi, "sodium_index": si, "gap_mS_cm2": gap, "sodium_scale": scale,
                   "artifact": relative, **file_receipt(output / relative), "metrics": result["metrics"],
                   "simulation_input_sha256": result["simulationAction"]["input_sha256"]}
            rows.append(row)
            band.append(result["metrics"]["cells_crossing_0mV"])
        matrix.append(band)
    index = {"schema": "frontier.bioelectric.atlas/1", "evidence_kind": "SimulationResult",
             "x": {"name": "sodium_scale", "unit": "1", "values": sodium, "status": "design-selected"},
             "y": {"name": "gap_mS_cm2", "unit": "mS/cm^2", "values": gaps, "status": "assumed-network-scenario"},
             "fixed": DEFAULTS | {"potassium_scale": 1},
             "color_quantity": "number of cells whose saved voltage crosses 0mV within30ms",
             "color_matrix": matrix, "rows": rows, "count": len(rows),
             "source": "sources.json", "scope": "Fixed squid-axon membrane model; no fish or fin calibration",
             "interpretation": "Simulation response atlas, not measured phenotypes or an optimization objective"}
    write(output / "atlas.json", index)
    fig, ax = plt.subplots(figsize=(10, 7), facecolor="#091820")
    ax.set_facecolor("#091820")
    image = ax.imshow(matrix, origin="lower", vmin=0, vmax=12, cmap="viridis", aspect="auto")
    ax.set_xticks(range(7), sodium, color="white")
    ax.set_yticks(range(7), gaps, color="white")
    ax.set_xlabel("Na maximal conductance / published baseline [1]", color="white")
    ax.set_ylabel("Assumed gap conductance density [mS/cm²]", color="white")
    ax.set_title("SIMULATED · electrical response atlas\n49 independently integrated parameter scenarios", color="white")
    for gi, band in enumerate(matrix):
        for si, value in enumerate(band):
            ax.text(si, gi, str(value), ha="center", va="center", color="black" if value > 8 else "white")
    bar = fig.colorbar(image, ax=ax)
    bar.set_label("cells crossing 0mV (of 12)", color="white")
    bar.ax.tick_params(colors="white")
    fig.text(.08, .025, "One pulse: 12 µA/cm², cell0, 5–6ms; 6.3°C; K scale=1. No fish calibration.\nEach cell links to actual voltage/time frames in atlas.json. DOI:10.1113/jphysiol.1952.sp004764", color="#b8c8cf", fontsize=9)
    fig.subplots_adjust(bottom=.17)
    fig.savefig(output / "atlas.png", dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    return index


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/bioelectric"))
    parser.add_argument("--skip-atlas", action="store_true")
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()
    if os.environ.get("MORPHOSWARM_BIOELECTRIC_RUN_ACTIVE"):
        raise SystemExit("refusing nested bundle run")
    os.environ["MORPHOSWARM_BIOELECTRIC_RUN_ACTIVE"] = "1"
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    write(output / "sources.json", SOURCES)
    scenarios = {"baseline": {}, "sodium_reduced": {"sodium_scale": .35}, "disconnected": {"gap_mS_cm2": 0}, "no_stimulus": {"stimulus_uA_cm2": 0}}
    for name, request in scenarios.items():
        result = simulate(request)
        if result["status"] != "completed":
            raise RuntimeError(f"{name}: {result}")
        write(output / f"{name}.json", result)
    # Actual subprocess exit statuses: the same control command must fail when
    # a physical law is changed, and pass again with the original operator.
    mutation_receipts = []
    for name, extra, expected in [("baseline", [], 0), ("gap_sign_mutant", ["--mutation", "gap-sign"], 1), ("restored", [], 0)]:
        command = [sys.executable, "-m", "engineering.bioelectric.controls", *extra]
        process = subprocess.run(command, capture_output=True, text=True, timeout=90)
        (output / f"controls_{name}.json").write_text(process.stdout)
        if process.returncode != expected:
            raise RuntimeError(f"control {name}: expected exit {expected}, got {process.returncode}: {process.stderr}")
        mutation_receipts.append({"arm": name, "command": command, "exit_status": process.returncode,
                                  "output": f"controls_{name}.json", "expected_exit_status": expected})
    write(output / "mutation_receipt.json", {"law": "gap-junction endpoint current sign", "receipts": mutation_receipts,
                                             "scope": "Physical law mutation: both endpoint currents given same sign; charge conservation must fail"})
    if not args.skip_atlas:
        atlas(output)
    if not args.skip_render:
        from .render import render
        write(output / "render_receipt.json", render(output))
    manifest = {"schema": "frontier.bioelectric.bundle/1", "status": "completed", "evidence_kind": "SimulationResult",
                "timestamp_seattle": datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d %H:%M:%S %Z"),
                "command": [sys.executable, "-m", "engineering.bioelectric.run", *sys.argv[1:]],
                "worktree_parent_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "source_identity": "Exact source files are pinned by SHA256; worktree_parent_commit is the parent at execution, not a clean-source assertion",
                "code_sha256": code_hashes(), "elapsed_s": time.perf_counter() - started, "exit_status": 0,
                "environment": {"python": platform.python_version(), "numpy": np.__version__, "platform": platform.platform(),
                                "threads": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS")}},
                "scenarios": {k: f"{k}.json" for k in scenarios}, "bounds": BOUNDS,
                "controls": "controls_baseline.json", "mutation": "mutation_receipt.json",
                "simulationActions": [f"{name}.json#/simulationAction" for name in scenarios],
                "renderAction": "render_receipt.json", "numerical_scope": "convergence checked for default HH scenario and smooth passive cable; not the entire atlas",
                "biological_validation": "not attempted; source parameters, no raw-data reproduction or fin transfer",
                "files": {str(p.relative_to(output)): file_receipt(p) for p in sorted(output.rglob("*"))
                          if p.is_file() and p.name != "manifest.json"}}
    write(output / "manifest.json", manifest)
    print(json.dumps({"status": "completed", "output": str(output), "elapsed_s": manifest["elapsed_s"], "files": len(manifest["files"])}))


if __name__ == "__main__":
    main()
