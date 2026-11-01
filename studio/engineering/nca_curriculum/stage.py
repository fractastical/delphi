"""Named exact-count source adaptations; original published execution files stay unchanged."""

import argparse
import copy
from hashlib import sha256
import json
from pathlib import Path

from engineering.nca_pattern.model import ROOT

ART = ROOT / "artifacts/nca-curriculum"
BASE = ROOT / "artifacts/nca-seed-placement"


def replace(source, old, new):
    if source.count(old) != 1:
        raise ValueError("Source adaptation identity/count changed: " + old[:60])
    return source.replace(old, new)


def build():
    plan = json.loads((ART / "protocol.json").read_text())
    manifest = json.loads((BASE / "packet.json").read_text())
    dest = ART / "execution-source"
    files = {}
    for item in manifest["files"]:
        name = item["path"]
        if name.startswith("engineering/"):
            raw = (ROOT / name).read_bytes()
            if sha256(raw).hexdigest() != item["sha256"]:
                raise ValueError("Original source pin changed")
            files[name] = raw.decode()
    train = files["engineering/nca_pattern/train.py"]
    train = replace(
        train,
        "from .model import NCA, dump, protocol, seed, target",
        "from .model import NCA, dump, protocol, seed, target\nfrom .curriculum_policy import damage_masks",
    )
    train = replace(
        train,
        "    damage_rng = np.random.default_rng(initialization_seed + 113)",
        "    damage_rng = np.random.default_rng(initialization_seed + 113)\n    prefix_rng = np.random.default_rng(initialization_seed + 211)",
    )
    train = replace(
        train,
        '        if regime == "damage-pool":\n            state[-3:] *= circles(damage_rng, 3, 64, device)',
        '        if regime in ["damage-pool", "curriculum-pool"]:\n            masks, prefix_cutoff = damage_masks(regime, iteration, circles(damage_rng, 3, 64, device), prefix_rng, cfg["prefix_schedule"])\n            state[-3:] *= masks',
    )
    train = replace(
        train,
        '                    "max_abs_batch_state": float(state.detach().abs().max()),',
        '                    "max_abs_batch_state": float(state.detach().abs().max()),\n                    "prefix_cutoff_draw": prefix_cutoff,\n                    "prefix_applied": regime == "curriculum-pool",',
    )
    files["engineering/nca_pattern/train.py"] = train
    evaluate = files["engineering/nca_pattern/evaluate.py"]
    evaluate = replace(
        evaluate,
        '        1024\n        if kind == "persistence"',
        '        cfg["persistence"]["updates"]\n        if kind == "persistence"',
    )
    evaluate = replace(
        evaluate,
        '"design match at every saved checkpoint256..1024"',
        "f\"design match at every saved checkpoint256..{cfg['persistence']['updates']}\"",
    )
    evaluate = replace(
        evaluate,
        '                trace = update_seed == 7001 and kind in [\n                    "persistence",\n                    "central-square",\n                ]',
        '                trace = update_seed == cfg["trace_update_seed"] and kind == cfg["trace_damage_kind"]',
    )
    files["engineering/nca_pattern/evaluate.py"] = evaluate
    job = files["engineering/nca_pattern/job.py"]
    job = replace(
        job,
        "from .train import train_one",
        "from .train import train_one\nfrom .curriculum_policy import install_read_guard, validate_manifest",
    )
    job = replace(
        job,
        "    cfg = protocol()",
        '    cfg = protocol()\n    read_guard = install_read_guard(ART / "heldout-masks.npz")\n    try:\n        with open(ART / "heldout-masks.npz", "rb"):\n            pass\n    except RuntimeError:\n        pass\n    else:\n        raise RuntimeError("Evaluation read guard failed its negative control")',
    )
    job = replace(
        job,
        '{"expected": 4, "models": training}',
        '{"expected": 8, "models": training}',
    )
    job = replace(
        job,
        "        dump(barrier_path, barrier)",
        '        dump(barrier_path, barrier)\n        read_guard["released_after_checkpoint_barrier"] = True\n        read_guard["checkpoint_barrier_sha256"] = sha256(barrier_path.read_bytes()).hexdigest()\n        dump(out / "evaluation-read-guard.json", read_guard)',
    )
    job = replace(
        job,
        '        positive = [x for x in evaluation if x["kind"] != "all-erased-negative"]',
        '        positive = [x for x in evaluation if x["kind"] != "all-erased-negative" and not x["status"].startswith("not-started")]',
    )
    job = replace(
        job,
        '        negatives = [x for x in evaluation if x["kind"] == "all-erased-negative"]',
        '        negatives = [x for x in evaluation if x["kind"] == "all-erased-negative" and not x["status"].startswith("not-started")]',
    )
    job = replace(job, "len(training) == 4", "len(training) == 8")
    job = replace(job, '"training_models_expected": 4', '"training_models_expected": 8')
    job = replace(job, '"declared_expected": 48', '"declared_expected": 192')
    job = replace(job, '"declared_expected": 4', '"declared_expected": 8')
    job = replace(
        job,
        '        dump(out / "summary.json", summary)',
        '        dump(out / "summary.json", summary)\n        dump(out / "evaluation-read-guard.json", read_guard)',
    )
    job = replace(
        job,
        '        status = "holdout evaluation"',
        '        validate_manifest(ART / "evaluation-manifest.json", cfg)\n        status = "holdout evaluation"',
    )
    job = replace(
        job,
        "        receipt.update(\n            status=status,",
        "        receipt.update(\n            evaluation_read_guard=read_guard,\n            status=status,",
    )
    files["engineering/nca_pattern/job.py"] = job
    files["engineering/nca_pattern/curriculum_policy.py"] = (
        ROOT / "engineering/nca_curriculum/policy.py"
    ).read_text()
    refs = []
    for name, source in files.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        compile(source, name, "exec")
        refs.append(
            {
                "path": name,
                "sha256": sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
            }
        )
    runtime = copy.deepcopy(json.loads((BASE / "protocol.json").read_text()))
    runtime.pop("seed_placement_follow_up", None)
    runtime["training"].update(
        regimes=plan["training"]["regimes"],
        model_seeds=plan["training"]["model_seeds"],
        models_expected=8,
        prefix_schedule=plan["training"]["prefix_schedule"],
    )
    runtime["evaluation"]["persistence"] = {"updates": 2048}
    runtime["evaluation"]["undamaged_persistence"].update(
        grow_updates=2048, expected_runs=24
    )
    runtime["evaluation"]["damage"]["expected_runs"] = 168
    runtime["evaluation"]["negative_all_erased"]["expected_runs"] = 8
    runtime["evaluation"]["persistence_predicate"] = (
        "design_match at every saved checkpoint256..2048"
    )
    runtime["training"]["damage_training"] = plan["training"]["curriculum"]
    runtime["training"]["comparison"] = (
        "circle-only versus mixed prefix curriculum, matched initialweights/updates, fourfreshpairs"
    )
    runtime["training"]["rng_policy"] = plan["training"]["rng"]
    runtime["evaluation"]["damage"]["masks"] = [
        x["id"] for x in plan["evaluation"]["mask_cases"]
    ]
    runtime["evaluation"]["total_expected_evaluation_runs"] = 200
    runtime["evaluation"]["full_state_snapshot_updates"] = [0, 256, 257, 768]
    runtime["evaluation"]["trace_damage_kind"] = "new-left-prefix-34"
    runtime["curriculum_plan_sha256"] = sha256(
        (ART / "protocol.json").read_bytes()
    ).hexdigest()
    runtime["evaluation"]["update_seeds"] = []
    runtime["evaluation"]["negative_all_erased"]["update_seed"] = None
    runtime["evaluation"]["trace_update_seed"] = None
    runtime["target"]["heldout_masks_sha256"] = None
    runtime["evaluation"]["trace_sampling_scope"] = (
        "8preselected new-left-prefix-34 histories, first independently committed update seed; all200retainfinalRGBA+metrics, fullsnapshots at0,256before/after,257,768"
    )
    runtime["resources"].update(
        training_soft_deadline_s=1800,
        total_soft_deadline_s=2100,
        outer_hard_runtime_s=2400,
    )
    (ART / "runtime-protocol-template.json").write_text(
        json.dumps(runtime, indent=2) + "\n"
    )
    (ART / "execution-source-manifest.json").write_text(
        json.dumps(
            {
                "schema": "frontier.nca.execution-source/1",
                "origin": "Named exact-count adaptations of original pinned execution; model/rule/optimizer unchanged, curriculum/evaluation/guard adaptations explicit",
                "files": refs,
                "builder_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            },
            indent=2,
        )
        + "\n"
    )
    print("built", len(refs), "syntax-checked execution files")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    build()
