"""Static-scenario ensemble views and native regional assurance; no new physics."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .experiment import REGIONS, output_reference, sha, write_json  # noqa: E402


def render(output_directory):
    output = Path(output_directory).resolve()
    all_path = output / "all-simulations.json"
    data = json.loads(all_path.read_text())
    controls = json.loads((output / "controls.json").read_text())
    candidates = data["candidates"]
    n = len(data["draws"])
    positions = candidates[0]["runs"][0]["cases"]["uniform"]["profile"]["x_over_L"]
    fields = []
    accuracy = []
    for candidate in candidates:
        cases = candidate["runs"]
        uniform = np.array([r["cases"]["uniform"]["profile"]["w_over_L"] for r in cases])
        tip = np.array([r["cases"]["tip_same_total_force"]["profile"]["w_over_L"] for r in cases])
        grid = np.array([r["cases"]["uniform"]["profile"]["coarse_fine_abs_difference_over_L"] for r in cases])
        fields.append({"candidate_id": candidate["candidate"]["id"], "region_ids": REGIONS,
                       "x_over_L": positions, "profile_quantile_levels": [.05, .5, .95],
                       "uniform_w_over_L_quantiles": np.quantile(uniform, [.05, .5, .95], axis=0).tolist(),
                       "tip_w_over_L_quantiles": np.quantile(tip, [.05, .5, .95], axis=0).tolist(),
                       "max_grid_difference_over_L": np.max(grid, axis=0).tolist(),
                       "median_load_shape_difference_over_L": np.median(np.abs(tip-uniform), axis=0).tolist(),
                       "empirical_accuracy": "unknown at every position, including constrained zero at the clamp",
                       "biological_success_probability": None})
        case_summaries = [case["summary"] for r in cases for case in r["cases"].values()]
        uniform_tips = [r["cases"]["uniform"]["summary"]["tip_over_L"] for r in cases]
        accuracy.append({"candidate_id": candidate["candidate"]["id"],
                         "max_analytic_tip_relative_error": max(s["analytic_tip_relative_error"] for s in case_summaries),
                         "max_analytic_profile_error_over_L": max(s["analytic_profile_sup_error_over_L"] for s in case_summaries),
                         "max_grid_profile_discrepancy_over_L": max(s["grid_profile_sup_error_over_L"] for s in case_summaries),
                         "uniform_tip_over_L_q05_q50_q95": np.quantile(uniform_tips, [.05, .5, .95]).tolist(),
                         "load_shape_tip_over_L_discrepancy_q05_q50_q95": np.quantile([r["model_shape_discrepancy_tip_over_L"] for r in cases], [.05, .5, .95]).tolist()})
    write_json(output / "regional-fields.json", {"schema": "frontier.fin-assurance.fields/1", "fields": fields,
               "scope": "UI annotation to pectoral regions only; no measured anatomical coordinate mapping",
               "source_artifact": {"path": output_reference(all_path), "sha256": sha(all_path)}})
    write_json(output / "accuracy-decomposition.json", {"schema": "frontier.fin-assurance.accuracy/1",
               "numerical_accuracy": "measured against analytic solutions of the declared linear model",
               "empirical_accuracy": "unknown", "biological_success_probability": None, "candidates": accuracy,
               "parameter_scope": "variation over assumed correlated inputs, not observed biological variability",
               "model_scope": "uniform-versus-tip load discrepancy is not a calibrated physical error bound"})

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True, dpi=120)
    vmax = max(r["cases"]["tip_same_total_force"]["summary"]["tip_over_L"] for c in candidates for r in c["runs"])
    for ax, candidate in zip(axes, candidates, strict=True):
        matrix = np.array([r["cases"]["tip_same_total_force"]["profile"]["w_over_L"] for r in candidate["runs"]])
        image = ax.imshow(matrix, aspect="auto", origin="lower", extent=(0, 1, 0, n), vmin=0, vmax=vmax, cmap="magma")
        ax.contour(np.linspace(0, 1, matrix.shape[1]), np.arange(n)+.5, matrix, levels=[.1], colors="cyan", linewidths=.8)
        ax.set(xlabel="position x/L", title=candidate["candidate"]["id"])
    axes[0].set_ylabel("ensemble draw (not time)")
    fig.colorbar(image, ax=axes, label="linear-model displacement w/L", fraction=.025, pad=.03)
    fig.suptitle("SIMULATED · spatial variation, same-total tip load · cyan: w/L=.1")
    fig.text(.5, .02, "Outside-envelope values are extrapolations. Numerical fidelity is separate from UNKNOWN empirical accuracy.", ha="center", fontsize=10)
    fig.subplots_adjust(left=.06, bottom=.15, right=.88, top=.86, wspace=.15)
    fig.savefig(output / "spatial-uncertainty.png", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True, dpi=120)
    for ax, candidate in zip(axes, candidates, strict=True):
        x = [r["inputs"]["EI_Nm2"] for r in candidate["runs"]]
        y = [d["speed_m_s"] for d in data["draws"]]
        value = [r["cases"]["tip_same_total_force"]["summary"]["tip_over_L"] for r in candidate["runs"]]
        image = ax.scatter(x, y, c=value, vmin=0, vmax=vmax, cmap="magma", s=42)
        ax.set(xscale="log", xlabel="assumed EI (N m²)", title=candidate["candidate"]["id"])
    axes[0].set_ylabel("declared speed (m/s)")
    fig.colorbar(image, ax=axes, label="tip/L, same-total tip load", fraction=.025, pad=.03)
    fig.suptitle("SIMULATED · sampled parameter response · 64 common draws, no interpolation")
    fig.text(.5, .02, "Other correlated parameters vary at each point; this is not a fitted surface or biological success probability.", ha="center", fontsize=10)
    fig.subplots_adjust(left=.06, bottom=.17, right=.88, top=.84, wspace=.15)
    fig.savefig(output / "parameter-response.png", bbox_inches="tight")
    plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(12.8, 7.2), dpi=100, sharey=True)
    lines = []
    labels = []
    for ax, candidate in zip(axes, candidates, strict=True):
        uniform, = ax.plot(positions, np.zeros(len(positions)), color="#147d86", label="uniform q")
        tip, = ax.plot(positions, np.zeros(len(positions)), color="#d35932", ls="--", label="tip force qL")
        ax.axhspan(0, .1, color="#d8ece2", zorder=-1)
        ax.axhline(.1, color="#555", lw=.7)
        ax.set(xlabel="x/L", ylim=(0, 1.05*vmax), title=candidate["candidate"]["id"])
        label = ax.text(.04, .96, "", transform=ax.transAxes, va="top", fontsize=10)
        lines.append((uniform, tip))
        labels.append(label)
    axes[0].set_ylabel("linear-model displacement w/L")
    axes[0].legend(loc="center left", fontsize=9)
    fig.suptitle("SIMULATED · retain several candidates\nStatic ensemble members, not a physical-time animation", fontsize=16)
    counter = fig.text(.5, .12, "", ha="center", fontsize=12)
    fig.text(.5, .07, "Green: local displacement≤.1L; whole-candidate predicate also requires max slope≤.2rad under BOTH loads.", ha="center", fontsize=9)
    fig.text(.5, .035, "Outside-envelope curves are linear extrapolations. Empirical accuracy, biological transfer and success probability: UNKNOWN.", ha="center", fontsize=9)
    fig.subplots_adjust(left=.08, right=.98, bottom=.22, top=.79, wspace=.13)
    indices = np.rint(np.linspace(0, n-1, 180)).astype(int)
    command = ["ffmpeg", "-loglevel", "error", "-y", "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "rgb24", "-s", "1280x720",
               "-r", "15", "-i", "-", "-an", "-c:v", "libx264", "-threads", "2", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output / "candidate-variation.mp4")]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
        def set_frame(index):
            for ci, candidate in enumerate(candidates):
                record = candidate["runs"][index]
                for line, shape in zip(lines[ci], ("uniform", "tip_same_total_force"), strict=True):
                    line.set_ydata(record["cases"][shape]["profile"]["w_over_L"])
                labels[ci].set_text(f"L={record['inputs']['L_m']:.3f}m\nEI={record['inputs']['EI_Nm2']:.2g}N m²\nBoth-load envelope: {'PASS' if record['passed'] else 'FAIL'}")
            counter.set_text(f"Shared draw {index+1}/{n} · candidate costs and flight consequences remain unknown")
        for index in indices:
            set_frame(index)
            fig.canvas.draw()
            proc.stdin.write(np.ascontiguousarray(np.asarray(fig.canvas.buffer_rgba())[:, :, :3]).tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    contrast = [i for i in range(n) if not candidates[0]["runs"][i]["passed"] and any(c["runs"][i]["passed"] for c in candidates[1:])]
    set_frame(contrast[0] if contrast else 0)
    fig.savefig(output / "poster.png")
    plt.close(fig)

    evidence = {"path": output_reference(output / "controls.json"), "sha256": sha(output / "controls.json"), "selector": "$"}
    axes_vector = {
        "formal_properties": {"status": "not_attempted", "summary": "No theorem about this ensemble or biological transfer", "evidence": [], "scope": "formal proof"},
        "numerical_fidelity": {"status": "checked_in_scope", "summary": "Independent analytic/null/grid/paired-sensitivity controls executed", "evidence": [evidence, {"path": output_reference(output/"accuracy-decomposition.json"), "sha256": sha(output/"accuracy-decomposition.json"), "selector": "$.candidates"}], "scope": "linear static single-beam surrogate only"},
        "empirical_validation": {"status": "unknown", "summary": "No matched held-out measured specimen/model tuple", "evidence": [], "scope": "target fish component"},
        "parameter_coverage": {"status": "declared_ensemble", "summary": "64 correlated shared-input draws; source-context envelope kept separate", "evidence": [{"path": data["protocol"]["path"], "sha256": data["protocol"]["sha256"], "selector": "$"}], "scope": "assumed distributions, not measured population coverage"},
        "cross_scale_transfer": {"status": "unknown", "summary": "No cell/tissue/developmental transfer or pressure coupling established", "evidence": [], "scope": "biological and fluid-structure correspondence"},
        "ensemble_robustness": {"status": "computed_in_scope", "summary": "Separate fractions for all three candidates; paired cases are not extra independent trials", "evidence": [{"path": output_reference(output / "summary.json"), "sha256": sha(output / "summary.json"), "selector": "$.candidates"}], "scope": "declared scenarios only"},
    }
    write_json(output / "design-assurance.json", {"schema": "frontier.design-assurance/1", "region_ids": REGIONS,
               "scale_anchor": "flying-fish:organ", "vector": axes_vector, "dimensions": list(axes_vector), "biological_success_probability": None,
               "region_membership": "UI annotation only; no anatomical calibration"})
    names = ["regional-fields.json", "accuracy-decomposition.json", "spatial-uncertainty.png", "parameter-response.png", "candidate-variation.mp4", "poster.png", "design-assurance.json"]
    write_json(output / "render-manifest.json", {"schema": "frontier.fin-assurance.render-manifest/1",
               "input": {"path": output_reference(all_path), "sha256": sha(all_path)},
               "render_code_sha256": sha(__file__), "matplotlib": matplotlib.__version__, "n_frames": len(indices), "fps": 15,
               "controls_passed": controls["passed"],
               "outputs": {name: {"sha256": sha(output/name), "byte_size": (output/name).stat().st_size} for name in names}})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("output_directory", nargs="?", default="artifacts/assurance-experiments")
    render(parser.parse_args().output_directory)
