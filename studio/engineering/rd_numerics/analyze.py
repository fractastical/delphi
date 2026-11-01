"""Audit and plot returned training-only fields, including partial/failed outcomes."""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .audit import CONFIGS, PAIRS, ROOT, common_grid, comparisons, dump, rd, sha


def compare_saved_metrics(actual, saved):
    """Float64 re-evaluation across BLAS builds; identities remain exact.

    This checks recalculation of saved metrics, not PDE convergence/accuracy.
    Tolerances were fixed before reading any returned numerical endpoints.
    """
    errors = []

    def visit(a, b):
        if isinstance(a, dict):
            if not isinstance(b, dict) or a.keys() != b.keys():
                raise ValueError("Paired metric keys changed")
            for key in a:
                visit(a[key], b[key])
        elif isinstance(a, list):
            if not isinstance(b, list) or len(a) != len(b):
                raise ValueError("Paired metric dimensions changed")
            for x, y in zip(a, b):
                visit(x, y)
        elif isinstance(a, float):
            if not isinstance(b, (float, int)) or not np.isclose(
                a, b, rtol=1e-10, atol=1e-12
            ):
                raise ValueError(
                    "Recomputed floating metric differs beyond roundoff tolerance"
                )
            errors.append(abs(a - b))
        elif type(a) is not type(b) or a != b:
            raise ValueError("Paired metric identity or categorical outcome changed")

    visit(actual, saved)
    return {
        "relative_tolerance": 1e-10,
        "absolute_tolerance": 1e-12,
        "floating_values_checked": len(errors),
        "max_absolute_recalculation_difference": max(errors, default=0.0),
        "scope": "Cross-BLAS recalculation roundoff only, not numerical-convergence acceptance; all categorical outcomes exact",
    }


def analyze(folder, output, retain_failed_recalculation=False):
    folder, out = Path(folder), Path(output)
    out.mkdir(parents=True, exist_ok=True)
    receipt = json.loads((folder / "receipt.json").read_text())
    required_sources = {
        "engineering/rd_numerics/audit.py",
        "engineering/rd_numerics/PREREG.md",
        "engineering/rd_diffusion/rd_ddpm.py",
        "engineering/rd_diffusion/config.json",
    }
    if set(receipt["source_pins"]) != required_sources:
        raise ValueError("Missing or unexpected executed source identities")
    for name, digest in receipt["source_pins"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(
                "Executed source differs from frozen local source: " + name
            )
    for name, digest in receipt["files"].items():
        if sha(folder / name) != digest:
            raise ValueError("Returned file hash mismatch: " + name)
    inputs = np.load(folder / "declared-inputs.npz")
    ids, seeds, taus = (
        inputs["setting_ids"],
        inputs["seed_indices"],
        inputs["save_tau"].tolist(),
    )
    if not (
        np.array_equal(ids, np.repeat(np.arange(16), 3))
        and np.array_equal(seeds, np.tile(np.arange(3), 16))
        and np.array_equal(inputs["ic_seeds"], ids * 1000 + seeds)
        and taus == [50, 100, 150, 200]
    ):
        raise ValueError("Declared training-only input identity changed")
    if not np.array_equal(inputs["params"], rd.settings_table()[ids]):
        raise ValueError("Actual input parameters differ from frozen training settings")
    complete = receipt["completed_configs"]
    if complete != list(range(len(complete))) or not set(complete) <= set(range(5)):
        raise ValueError("Unexpected/repeated configuration identities")
    if receipt["complete"] != (complete == list(range(5))):
        raise ValueError("Completeness claim contradicts actual configuration count")
    fields_summary = []
    for index in complete:
        data = np.load(folder / f"config-{index}.npz")
        f = data["fields"]
        if f.shape != (48, 4, 2, CONFIGS[index][0]) or f.dtype != np.float64:
            raise ValueError("Native field dimensions changed")
        finite = np.isfinite(f).all((2, 3))
        exceeded = np.nan_to_num(abs(f), nan=np.inf).max((2, 3)) > 1000
        negative = (f < 0).any((2, 3))
        if not all(
            np.array_equal(data[k], value)
            for k, value in (
                ("finite", finite),
                ("exceeded", exceeded),
                ("negative", negative),
            )
        ):
            raise ValueError("Saved failure mask does not match native fields")
        fields_summary.append(
            {
                "index": index,
                "N": CONFIGS[index][0],
                "dt_tau": CONFIGS[index][1],
                "native_snapshots": 192,
                "nonfinite_snapshots": int((~finite).sum()),
                "over1000_snapshots": int(exceeded.sum()),
                "negative_snapshots": int(negative.sum()),
            }
        )
    rows = comparisons(folder, complete, ids, seeds, taus)
    saved = json.loads((folder / "paired-discrepancies.json").read_text())
    original_exact_check = rows == saved
    recalculation_failed = False
    try:
        metric_check = compare_saved_metrics(rows, saved)
    except ValueError as error:
        if not retain_failed_recalculation:
            raise
        recalculation_failed = True
        metric_check = {
            "status": "FAILED",
            "error": str(error),
            "relative_tolerance": 1e-10,
            "absolute_tolerance": 1e-12,
            "scope": "Failure retained; original cloud metrics below are not relabeled as independently reproduced",
        }
        rows = saved
    if len(rows) != receipt["paired_rows"]:
        raise ValueError("Saved paired counts do not match recomputation")
    n_pairs = sum(a in complete and b in complete for a, b in PAIRS)
    if len(rows) != n_pairs * 48 * 4:
        raise ValueError("Missing paired conditions")
    summaries = []
    fig, axes = plt.subplots(1, 3, figsize=(13, 5), dpi=120)
    images = [np.full((5, 4), np.nan) for _ in axes]
    for pi, pair in enumerate(PAIRS):
        all_rows = [r for r in rows if r["configs"] == list(pair)]
        if not all_rows:
            continue
        for ti, tau in enumerate(taus):
            subset = [r for r in all_rows if r["tau"] == tau]
            valid = [r for r in subset if r["valid_native_pair"]]
            record = {
                "configs": list(pair),
                "tau": tau,
                "declared_pairs": len(subset),
                "valid_pairs": len(valid),
                "excluded_pairs": len(subset) - len(valid),
                "mode_changed_count": sum(r["mode_changed"] for r in valid),
                "channels": None,
            }
            if valid:
                record["channels"] = [
                    {
                        "median_common_grid_relative_L2": float(
                            np.median(
                                [
                                    r["channels"][c]["common_grid_relative_L2"]
                                    for r in valid
                                ]
                            )
                        ),
                        "max_common_grid_relative_L2": float(
                            max(
                                r["channels"][c]["common_grid_relative_L2"]
                                for r in valid
                            )
                        ),
                        "median_common_grid_RMS_abs": float(
                            np.median(
                                [r["channels"][c]["common_grid_RMS_abs"] for r in valid]
                            )
                        ),
                        "max_finer_highmode_power_fraction": float(
                            max(
                                r["channels"][c][
                                    "finer_power_fraction_above_common_cutoff"
                                ]
                                for r in valid
                            )
                        ),
                    }
                    for c in range(2)
                ]
                images[0][pi, ti] = record["channels"][0][
                    "median_common_grid_relative_L2"
                ]
                images[1][pi, ti] = record["channels"][1][
                    "median_common_grid_relative_L2"
                ]
                images[2][pi, ti] = record["mode_changed_count"] / len(valid)
            summaries.append(record)
    labels = [
        "time:64/.02→64/.01",
        "time:64/.01→64/.005",
        "grid:64/.005→128/.005",
        "grid:128/.005→256/.005",
        "combined:64/.02→256/.005",
    ]
    for ax, image, title in zip(
        axes,
        images,
        [
            "u median relative L2 discrepancy",
            "v median relative L2 discrepancy",
            "u dominant-mode change fraction",
        ],
    ):
        palette = plt.colormaps["magma"].copy()
        palette.set_bad("#dddddd")
        shown = ax.imshow(image, aspect="auto", cmap=palette, interpolation="nearest")
        ax.set_xticks(range(4), taus)
        ax.set_yticks(range(5), labels, fontsize=8)
        ax.set_xlabel("Dimensionless model time τ")
        ax.set_title(title, fontsize=10)
        fig.colorbar(shown, ax=ax, shrink=0.7)
    fig.suptitle("Training-only paired discretization audit · no grid is assumed exact")
    fig.text(
        0.02,
        0.015,
        "Medians across declared 16 settings × 3 shared IC seeds. Gray/missing cells indicate unavailable or invalid comparisons; no convergence PASS threshold.",
        fontsize=8,
    )
    if recalculation_failed:
        fig.text(
            0.02,
            0.045,
            "Independent auxiliary-metric reproduction FAILED; original cloud metrics shown, failure retained.",
            color="#a32125",
            fontsize=9,
        )
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(out / "paired-discrepancies.png")
    plt.close(fig)
    if 0 in complete and 4 in complete:
        # Scenario rows are not a 2-D tissue: these are 48 paired 1-D fields.
        coarse = np.load(folder / "config-0.npz")["fields"][:, -1]
        fine, _ = common_grid(np.load(folder / "config-4.npz")["fields"][:, -1])
        fig, axes = plt.subplots(2, 3, figsize=(13, 7), dpi=120)
        for channel, name in enumerate(("u", "v")):
            a, b = coarse[:, channel], fine[:, channel]
            extent = (0, 1, 48, 0)
            low, high = min(a.min(), b.min()), max(a.max(), b.max())
            for axis, field, title in zip(
                axes[channel, :2],
                (a, b),
                ("N64 / dt .02", "N256 / dt .005 projected to64cosine modes"),
            ):
                img = axis.imshow(
                    field, aspect="auto", extent=extent, vmin=low, vmax=high
                )
                axis.set_title(name + ": " + title, fontsize=9)
                fig.colorbar(img, ax=axis, shrink=0.75)
            delta = a - b
            limit = max(float(abs(delta).max()), 1e-15)
            img = axes[channel, 2].imshow(
                delta,
                aspect="auto",
                extent=extent,
                cmap="coolwarm",
                vmin=-limit,
                vmax=limit,
            )
            axes[channel, 2].set_title(name + ": coarse − projected finer", fontsize=9)
            fig.colorbar(img, ax=axes[channel, 2], shrink=0.75)
            for axis in axes[channel]:
                axis.set_xlabel("Normalized spatial coordinate x/L")
                axis.set_ylabel("Training scenario row (16settings ×3ICs)")
        fig.suptitle(
            "Actual paired1-D solver fields at τ200 · concentrations in model units"
        )
        fig.text(
            0.02,
            0.015,
            "Rows are simulated scenarios, not a spatial tissue image. Finest solution is not assumed exact; auxiliary-power recalculation failure retained separately.",
            fontsize=8,
        )
        fig.tight_layout(rect=(0, 0.04, 1, 0.95))
        fig.savefig(out / "actual-fields.png")
        plt.close(fig)
    report = {
        "schema": "frontier.rd-numerics.analysis/1",
        "complete": complete == list(range(5)),
        "completed_configs": complete,
        "expected_configurations": 5,
        "expected_runs_per_configuration": 48,
        "paired_rows": len(rows),
        "expected_pairs_if_complete": 960,
        "field_checks": fields_summary,
        "paired_summaries": summaries,
        "scope": "Descriptive differences between numerical approximations on training settings only. No exact reference, grid-time interaction estimate, neural-surrogate result or biological validation. Paired IC seeds share settings; not independent biological samples.",
        "convergence_pass": None,
        "empirical_accuracy": "unknown",
        "source_receipt_sha256": sha(folder / "receipt.json"),
        "original_bit_for_bit_metric_comparison_equal": original_exact_check,
        "saved_metric_recalculation": metric_check,
        "independent_metric_reproduction_status": "FAILED"
        if recalculation_failed
        else "passed_in_scope",
        "metric_basis": "Original saved cloud metrics; failed independent recalculation retained"
        if recalculation_failed
        else "Independently recomputed from pinned arrays",
    }
    dump(out / "summary.json", report)
    dump(
        out / "provenance.json",
        {
            "analysis_source_sha256": sha(__file__),
            "comparison_source_sha256": sha(Path(__file__).with_name("audit.py")),
            "input_receipt_sha256": sha(folder / "receipt.json"),
            "outputs": {
                p.name: sha(p)
                for p in out.iterdir()
                if p.is_file() and p.name != "provenance.json"
            },
        },
    )
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    return not recalculation_failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--retain-failed-recalculation",
        action="store_true",
        help="Write labeled original-metric figures while retaining FAILED status and exit1; does not change any tolerance",
    )
    args = parser.parse_args()
    success = analyze(args.folder, args.output, args.retain_failed_recalculation)
    if not success:
        raise SystemExit(1)
