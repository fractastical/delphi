"""Render returned DDPM samples; never run a solver, model, or generate samples."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import PillowWriter
import numpy as np


def render(source: Path, output: Path):
    with np.load(source, allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    solver, generated = data["solver"], data["generated"]
    reverse = data["reverse_trajectory_normalized"]
    if solver.shape != (6, 8, 4, 2, 64) or generated.shape != (6, 4, 8, 2, 64):
        raise ValueError("Expected the complete six-condition frozen display archive")
    if reverse.shape != (20, 4, 2, 64):
        raise ValueError("Expected all twenty recorded reverse-process states")
    if not all(np.isfinite(value).all() for value in data.values()):
        raise ValueError("Nonfinite returned display data; refuse an unlabeled plot")
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.facecolor": "#fbfaf6",
                         "axes.facecolor": "#fbfaf6"})
    for channel, name in enumerate(("u", "v")):
        fig, axes = plt.subplots(2, 3, figsize=(12, 7))
        for index, ax in enumerate(axes.flat):
            x = data["x"] * data["params"][index, 3] / 64
            for fields, color, label in (
                (solver[index, :, -1, channel], "#137c83", "Direct solver"),
                (generated[index, -1, :, channel], "#b55535", "DDPM samples"),
            ):
                ax.fill_between(x, fields.min(0), fields.max(0), color=color, alpha=0.12)
                ax.plot(x, fields.mean(0), color=color, linewidth=1.8, label=label)
            ax.set_title(f"Condition {data['setting_ids'][index]}", loc="left")
            ax.set_xlabel("Position (model units)")
            ax.set_ylabel(f"{name} (model units)")
        axes[0, 0].legend(frameon=False, fontsize=9)
        fig.suptitle(f"Learned field distributions · channel {name} · τ = {data['taus'][-1]}",
                     fontsize=17, x=0.055, ha="left")
        fig.text(0.055, 0.915, "All six frozen display conditions. Lines: eight-sample means. Shading: full sample range, not a confidence interval.", fontsize=9)
        fig.text(0.055, 0.025, "SURROGATE vs SIMULATION · Independent ensembles; samples are not paired. Generic Schnakenberg model, not measured tissue.", fontsize=9)
        fig.tight_layout(rect=(0.02, 0.055, 0.99, 0.9))
        fig.savefig(output / f"solver-versus-generated-{name}.png", dpi=125)
        plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6))
    lines = []
    colors = ("#137c83", "#b55535", "#5866aa", "#947424")
    for channel, ax in enumerate(axes):
        lo, hi = reverse[:, :, channel].min(), reverse[:, :, channel].max()
        ax.set_ylim(lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo))
        ax.set_xlim(0, 63)
        ax.set_title(f"Channel {'uv'[channel]}", loc="left")
        ax.set_xlabel("Grid index")
        ax.set_ylabel("Standardized model value")
        lines.append([ax.plot(reverse[0, sample, channel], color=color, linewidth=1.3)[0]
                      for sample, color in enumerate(colors)])
    fig.suptitle("Recorded reverse diffusion · four generated samples", fontsize=15,
                 x=0.07, ha="left")
    stage = fig.text(0.07, 0.88, "", fontsize=10)
    fig.text(0.07, 0.025, "Generation steps, not physical time. Condition 1450, τ = 200. Standardized fields; not biological measurements.", fontsize=8)
    fig.tight_layout(rect=(0.02, 0.06, 0.99, 0.87))
    writer = PillowWriter(fps=4)
    with writer.saving(fig, str(output / "recorded-reverse-diffusion.gif"), dpi=95):
        for frame in range(len(reverse)):
            stage.set_text(f"Recorded state {frame + 1:02d} / 20 · reverse step {190 - frame * 10}")
            for channel in range(2):
                for sample in range(4):
                    lines[channel][sample].set_ydata(reverse[frame, sample, channel])
            writer.grab_frame()
    fig.savefig(output / "recorded-reverse-diffusion-final.png", dpi=125)
    plt.close(fig)
    manifest = {
        "schema": "frontier.rd-diffusion.visuals/1",
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_job_id": "aijob-e00fb6jhvdt12fgsje",
        "display_conditions": data["setting_ids"].tolist(), "physical_snapshot_tau": 200,
        "recorded_reverse_frames": len(reverse),
        "scope": "Returned arrays only. No generated replacements, no new simulation, no biological validation. Range shading is not a confidence interval.",
        "files": {path.name: {"bytes": path.stat().st_size,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                  for path in sorted(output.iterdir()) if path.suffix in (".gif", ".png")},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    render(args.source, args.output)
