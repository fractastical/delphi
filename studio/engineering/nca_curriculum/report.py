"""Show all curriculum arms and preselected actual pattern states, without selection."""

import argparse
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engineering.nca_pattern.analyze import artifact_path, digest, image_rgba, load
from engineering.nca_pattern.model import ROOT, dump

ART = ROOT / "artifacts/nca-curriculum"


def render(root, out, cfg, summary):
    order = [
        f"{regime}-s{seed}" for regime in cfg["training"]["regimes"]
        for seed in cfg["training"]["model_seeds"]
    ]
    traces, refs = {}, []
    for item in summary["evaluations"]:
        if item.get("trajectory", {}).get("full_history_selected_before_training"):
            path = artifact_path(root, item["trajectory"]["path"])
            if digest(path) != item["trajectory"]["sha256"]:
                raise ValueError("Selected render input changed")
            with np.load(path, allow_pickle=False) as data:
                traces[item["model_id"]] = {name: data[name].copy() for name in data.files}
            refs.append(item["trajectory"])
    count = max((len(x["rgba"]) for x in traces.values()), default=0)
    if not count:
        return
    goal = np.moveaxis(np.load(ROOT / "artifacts/nca-seed-placement/target.npz")["rgba"], -1, 0)
    regular = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21)
    provenance = {
        "schema": "frontier.nca.curriculum.render/1",
        "summary_sha256": digest(root / "summary.json"),
        "code_sha256": digest(Path(__file__)), "source_trajectories": refs, "frames": [],
        "scope": "Eight preselected new-left-prefix-34/first-update-seed trajectories. Actual saved states; no interpolation. Display clips RGBA only. Computational updates are not biological time.",
    }
    process = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", "1280x840", "-r", "5", "-i", "-", "-an", "-c:v", "libx264",
        "-threads", "2", "-pix_fmt", "yuv420p", str(out / "curriculum-trajectories.mp4"),
    ], stdin=subprocess.PIPE)
    try:
        for frame in range(count):
            canvas = Image.new("RGB", (1280, 840), "#081c2c")
            draw = ImageDraw.Draw(canvas)
            draw.text((20, 10), "Matched damage curriculum | all eight trained candidates", fill="white", font=title)
            draw.text((20, 41), "Design target, not observed tissue. Hidden channels have no measured biochemical identity.", fill="#bdd0d9", font=regular)
            mapping = []
            for index, model in enumerate(order):
                x, y = 20 + (index % 4) * 315, 100 + (index // 4) * 345
                draw.text((x, y - 25), model, fill="white", font=small)
                trace = traces.get(model)
                if trace is None:
                    draw.text((x, y + 50), "No returned selected history", fill="#ffbb99", font=small)
                    continue
                saved = min(frame, len(trace["rgba"]) - 1)
                step, phase = int(trace["frame_update_step"][saved]), str(trace["frame_phase"][saved])
                canvas.paste(image_rgba(trace["rgba"][saved], 256), (x, y))
                draw.text((x, y + 262), f"Update {step} | {phase}", fill="#bdd0d9", font=small)
                if frame >= len(trace["rgba"]):
                    draw.text((x, y + 282), "Explicit terminal hold", fill="#ffbb99", font=small)
                mapping.append({"model_id": model, "saved_frame_index": saved, "update_step": step, "phase": phase})
            draw.text((20, 784), "Top: three circles | bottom: two circles + staged prefix | same init/update budgets per column", font=small, fill="white")
            draw.text((20, 808), f"192 declared design probes + 8 erased controls | fresh update seed {cfg['evaluation']['trace_update_seed']}", font=small, fill="#bdd0d9")
            # Target thumbnail is explicitly a goal, outside the actual-state panels.
            canvas.paste(image_rgba(goal, 64), (1196, 8))
            provenance["frames"].append({"movie_frame": frame, "actual_states": mapping})
            process.stdin.write(canvas.tobytes())
            if frame == count - 1:
                canvas.save(out / "poster.png")
    finally:
        process.stdin.close()
    if process.wait() != 0:
        raise RuntimeError("ffmpeg failed")
    provenance["outputs"] = [
        {"path": name, "sha256": digest(out / name), "bytes": (out / name).stat().st_size}
        for name in ["curriculum-trajectories.mp4", "poster.png"]
    ]
    dump(out / "render-provenance.json", provenance)


def plot(root, out, cfg, summary, audit):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.8), layout="constrained")
    for i, seed in enumerate(cfg["training"]["model_seeds"]):
        for regime, linestyle in [("damage-pool", "-"), ("curriculum-pool", "--")]:
            model = next(x for x in summary["models"] if x["id"] == f"{regime}-s{seed}")
            if "history_path" in model:
                history = load(artifact_path(root, model["history_path"]))
                axes[0].plot(
                    [x["training_step"] for x in history],
                    [x["batch_output_loss_before_parameter_update"] for x in history],
                    linestyle, color=f"C{i}", label=f"{seed} {regime}", linewidth=1.2,
                )
    axes[0].set(xlabel="Actual optimization step", ylabel="Raw batch RGBA MSE", title="Four matched training pairs")
    axes[0].legend(fontsize=7)
    kinds = ["persistence", *cfg["evaluation"]["damage"]["masks"]]
    order = [f"{regime}-s{seed}" for regime in cfg["training"]["regimes"] for seed in cfg["training"]["model_seeds"]]
    cells = np.full((8, 8), np.nan)
    for i, model in enumerate(order):
        for j, kind in enumerate(kinds):
            rows = [x for x in audit["records"] if x["model_id"] == model and x["kind"] == kind]
            if len(rows) == 3:
                cells[i, j] = sum(x["recomputed_passed"] for x in rows)
    shown = axes[1].imshow(cells, vmin=0, vmax=3, cmap="viridis", aspect="auto")
    for i, row in enumerate(cells):
        for j, value in enumerate(row):
            axes[1].text(j, i, str(int(value)) if np.isfinite(value) else "partial", ha="center", va="center", fontsize=8, color="white" if value < 2 else "black")
    axes[1].set_yticks(range(8), [x.replace("-pool", "") for x in order], fontsize=7)
    axes[1].set_xticks(range(8), [x.replace("new-", "") for x in kinds], rotation=55, ha="right", fontsize=7)
    axes[1].set(title="Passing dependent probes / 3 declared update seeds")
    fig.colorbar(shown, ax=axes[1], ticks=[0, 1, 2, 3], shrink=.65)
    fig.suptitle("Inverse computational-pattern experiment | no biological calibration")
    fig.savefig(out / "training-and-evaluation.png", dpi=120)
    plt.close(fig)


def report(root, out, inputs=ART):
    cfg, summary, audit = load(inputs / "runtime-protocol.json"), load(root / "summary.json"), load(out / "audit.json")
    counts = audit["counts"]
    rows = []
    for pair in audit["per_pair_effects"]:
        if pair["group"] not in ["all_design", "persistence", "damage"]:
            continue
        a, b = (pair["regimes"][x] for x in ["damage-pool", "curriculum-pool"])
        rows.append(f"| {pair['initialization_seed']} | {pair['group']} | {a['passed']}/{a['declared']} ({a['executed']} executed) | {b['passed']}/{b['declared']} ({b['executed']} executed) | {pair['curriculum_minus_baseline_fraction']} |")
    text = f"""# Matched damage curriculum: actual returned computation

Native status: **{summary['status']}**. Fixed design predicates passed **{counts['design_passed']}/192 declared**, {counts['design_executed']} executed. Erased-state absorbing controls passed **{counts['negative_passed']}/8 declared**, {counts['negative_executed']} executed; these are outside the design denominator. Completed final checkpoints: {audit['complete_checkpoint_count']}/8. Missing evaluation identities: {len(audit['missing_identities'])}. All eight candidates and incomplete/failed arms are retained.

| Paired initialization | Endpoint family | Three-circle baseline | Prefix curriculum | Curriculum minus baseline fraction |
| --- | --- | --- | --- | --- |
""" + "\n".join(rows) + f"""

The four training initialization pairs are the replicate units. Three update seeds and eight endpoint families probe the same learned weights and are dependent. These fractions and differences are descriptive of the declared computational scenarios, not independent biological replicates, biological-success probabilities or evidence of a general curriculum benefit. Inspect persistence separately from damage to expose a possible tradeoff. Partial evaluations have no substituted denominator or invented outcome.

The intervention replaces exactly one of three circular erasures with a staged left-prefix erasure. The remaining circles, initialization, optimizer, raw RGBA loss, stochastic-update budget and target are matched within each pair. All eight final 2000-step weights were prescribed before evaluation; there is no best-model selection. New independently committed masks and update seeds are used here; the original zero-pattern failure and prior seed-placement result remain unchanged.

Target: one synthetic-colored 64×64 raster of the biological-v3a fin design, not an observed cell/tissue image. The shared local rule is adapted from [Growing Neural Cellular Automata, Model and Experiments 2–3](https://distill.pub/2020/growing-ca/). Its 12 hidden channels have no measured biochemical meaning. Pixels and updates have no measured cell-size or biological-time mapping. A computational pattern is not DNA, neural control, tissue regeneration or a feasible organism.

Criteria were fixed before training: raw RGBA MSE≤.02 AND alpha>.1 silhouette IoU≥.75. Persistence requires all saved checkpoints256–2048; recovery requires a valid pattern before erasure at256 and after512 recovery updates. Failure to establish the pre-damage pattern fails recovery. Negative all-erased state tests are separate.

Returned-byte audit checked {audit['files_checked']} files/{audit['bytes_checked']} bytes against the native receipt, pinned execution snapshots, source hashes and protocols. Checkpoint barrier and read-guard events are checked. Independent commitment plus a source-order guard is not cryptographic secrecy when plaintext files ship with the job. Guard coverage is the configured mask path in the cooperative frozen program, not protection against an adversarial reader.

Final visible-state metrics are recomputed from every returned raw final RGBA. Selected trajectory visible metrics and the all-channel before/after damage operator are also checked. Persistence at checkpoints without saved whole states and all-erased hidden-state zero rely on source-pinned saved metrics; this is not a training/trajectory replication. Bit-for-bit metric reproduction: {audit['exact_metric_reproduction']}; {audit['nonexact_metric_count']} nonexact comparisons, maximum absolute discrepancy {audit['max_metric_absolute_difference']:.17g}. Separately named fixed-roundoff diagnostic (rtol1e-10,atol1e-12): {audit['fixed_roundoff_metric_reproduction']}. Neither replaces the original exact outcome or changes a criterion.

Actual device: {audit['device']}. Environment: {audit['environment']}. Science wall time: {audit['wall_seconds']:.3f}s. Dollar cost unknown. Protocol SHA256 {audit['protocol_sha256']}; receipt SHA256 {audit['job_receipt_sha256']}. Checkpoints omit the training pool and do not provide exact resume. Full provenance and per-case values are in audit.json and the native files.

Movie panels show only the eight preselected new-left-prefix-34/first-update-seed histories. There is no interpolation or replacement by a more successful case. RGBA clipping is display-only; reported metrics use raw values. All-channel snapshots and raw failure records remain available. Empirical biological validation remains unknown.
"""
    (out / "RESULTS.md").write_text(text)
    plot(root, out, cfg, summary, audit)
    render(root, out, cfg, summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, default=ART)
    args = parser.parse_args()
    report(args.root, args.out, args.inputs)
