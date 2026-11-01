"""Display actual paired uncertainty outcomes without an invented fitness score."""

from hashlib import sha256
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .model import ART, dump


def render(source, out):
    summary = json.loads(source.read_text())
    protocol = json.loads((ART / "uncertainty-protocol.json").read_text())
    settings = [x["id"] for x in protocol["settings"]]
    seeds = protocol["seeds"]
    shape = (len(settings), len(seeds))
    values = [np.full(shape, np.nan) for _ in range(3)]
    for item in summary["paired_comparisons"]:
        if item["eligible"]:
            i, j = settings.index(item["setting"]), seeds.index(item["seed"])
            values[0][i, j] = item["response_count_difference"]
            values[1][i, j] = item["positive_work_difference_J"] * 1000
            values[2][i, j] = item["lateral_displacement_difference_m"] * 1000
    fig, axes = plt.subplots(
        1, 3, figsize=(12.8, 5.8), facecolor="#081c2c", layout="constrained"
    )
    fig.get_layout_engine().set(rect=(0, 0.055, 1, 0.945))
    titles = [
        "Extra response flags by 0.6 s",
        "Extra positive actuator work (mJ)",
        "Extra lateral displacement (mm)",
    ]
    cmap = plt.get_cmap("viridis").copy()
    cmap.set_bad("#52616b")
    for ax, value, title in zip(axes, values, titles, strict=True):
        ax.imshow(value, cmap=cmap, aspect="auto")
        ax.set_xticks(range(2), [str(x) for x in seeds], color="white", fontsize=9)
        ax.set_yticks(range(len(settings)), settings, color="white", fontsize=9)
        ax.set_title(title, color="white", fontsize=11)
        for i in range(len(settings)):
            for j in range(2):
                ax.text(
                    j,
                    i,
                    "not run" if np.isnan(value[i, j]) else f"{value[i, j]:.3g}",
                    ha="center",
                    va="center",
                    color="white",
                    fontsize=10,
                )
        ax.set_xlabel("Assigned reaction-delay RNG seed", color="white", fontsize=9)
    fig.suptitle(
        f"Paired neighbor-minus-ablation outcomes • {summary['computed_count']}/{summary['scenario_count']} scenarios computed",
        color="white",
        fontsize=14,
    )
    fig.text(
        0.5,
        0.018,
        "Seven-point axial design: no interaction estimate | assumed parameter envelopes and shared source/seeds | model-domain stops retained | no biological probability",
        ha="center",
        color="#a4b4c8",
        fontsize=8,
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    dump(
        out.with_suffix(".provenance.json"),
        {
            "schema": "frontier.ecology.sensitivity-render/1",
            "source_path": str(source),
            "source_sha256": sha256(source.read_bytes()).hexdigest(),
            "code_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "values": [
                [[None if np.isnan(x) else float(x) for x in row] for row in value]
                for value in values
            ],
            "scope": "Actual paired endpoints; grey not-run cells are missing, not zero. Display colors are not a fitness score.",
        },
    )


if __name__ == "__main__":
    render(
        ART / "uncertainty-initial/summary.json",
        ART / "uncertainty-initial/paired-sensitivity.png",
    )
