"""Preregistered robustness probes, loaded only after the checkpoint SHA barrier."""

from hashlib import sha256
import json
from pathlib import Path
import time

import numpy as np
import torch

from .model import ART, NCA, dump, metrics, protocol, seed, target


def one(model, goal, xy, ray, kind, update_seed, mask, out, record_trace):
    cfg = protocol()["evaluation"]
    device = "cuda"
    generator = torch.Generator(device=device).manual_seed(update_seed)
    state = seed(64, xy, device=device)
    history = []
    rgba = []
    frame_steps = []
    frame_phase = []
    full = []
    full_steps = []
    full_phase = []
    damage_step = cfg["damage"]["before_damage_updates"]
    end = (
        cfg["persistence"]["updates"]
        if kind == "persistence"
        else damage_step + cfg["damage"]["recovery_updates"]
    )
    predamage = None
    status = "complete"

    def save(step, phase, force=False):
        nonlocal predamage
        values = metrics(state, goal, ray)
        history.append({"update_step": step, "phase": phase, **values})
        if phase == "before-damage":
            predamage = values
        if record_trace and (step % cfg["save_rgba_every_updates"] == 0 or force):
            rgba.append(state[0, :4].detach().cpu().numpy().copy())
            frame_steps.append(step)
            frame_phase.append(phase)
        if record_trace and (step in cfg["full_state_snapshot_updates"] or force):
            full.append(state[0].detach().cpu().numpy().copy())
            full_steps.append(step)
            full_phase.append(phase)
        return values

    save(0, "seed", True)
    with torch.no_grad():
        for step in range(1, end + 1):
            state = model(state, generator=generator)
            if not bool(torch.isfinite(state).all()) or float(state.abs().max()) > 100:
                status = "failed: nonfinite or state magnitude guard"
                break
            if kind != "persistence" and step == damage_step:
                save(step, "before-damage", True)
                state *= torch.as_tensor(~mask, device=device)[None, None]
                save(step, "after-damage", True)
            elif (
                step % 16 == 0
                or step == end
                or (record_trace and step in cfg["full_state_snapshot_updates"])
            ):
                save(
                    step,
                    "persistence"
                    if kind == "persistence"
                    else ("growth" if step < damage_step else "recovery"),
                )
    final = (
        metrics(state, goal, ray)
        if bool(torch.isfinite(state).all())
        else {"finite": False, "design_match": False}
    )
    path = out.with_suffix(".npz")
    data = {
        "final_rgba": state[0, :4].detach().cpu().numpy(),
        "recorded_trace": np.array(record_trace),
    }
    if record_trace:
        data.update(
            rgba=np.asarray(rgba),
            frame_update_step=np.asarray(frame_steps),
            frame_phase=np.asarray(frame_phase),
            full_state=np.asarray(full),
            full_state_update_step=np.asarray(full_steps),
            full_state_phase=np.asarray(full_phase),
        )
    np.savez_compressed(path, **data)
    if kind == "persistence":
        considered = [x for x in history if x["update_step"] >= 256]
        passed = (
            status == "complete"
            and bool(considered)
            and all(x["design_match"] for x in considered)
        )
    elif kind == "all-erased-negative":
        passed = bool(torch.count_nonzero(state) == 0)
    else:
        passed = (
            status == "complete"
            and predamage is not None
            and predamage["design_match"]
            and final["design_match"]
        )
    result = {
        "kind": kind,
        "update_seed": update_seed,
        "status": status,
        "updates_completed": step,
        "criterion_passed": bool(passed),
        "criterion_scope": "all-zero absorbing negative control"
        if kind == "all-erased-negative"
        else (
            f"design match at every saved checkpoint256..{cfg['persistence']['updates']}"
            if kind == "persistence"
            else "design match before and512updates after damage"
        ),
        "predamage": predamage,
        "final": final,
        "metrics": history,
        "trajectory": {
            "path": str(path),
            "sha256": sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
            "full_history_selected_before_training": record_trace,
        },
        "scope": "Computational design target; no biological success probability.",
    }
    dump(out.with_suffix(".json"), result)
    return result


def evaluate(training, out, barrier_path, deadline):
    cfg = protocol()["evaluation"]
    manifest = json.loads(barrier_path.read_text())
    goal, xy, ray = target("cuda")
    maskpath = ART / "heldout-masks.npz"
    if (
        sha256(maskpath.read_bytes()).hexdigest()
        != protocol()["target"]["heldout_masks_sha256"]
    ):
        raise ValueError("Frozen heldout masks changed")
    masks = np.load(maskpath)
    results = []
    for record in training:
        if record["status"] != "complete":
            continue
        checkpoint = record["final_checkpoint"]
        path = Path(checkpoint["path"])
        if sha256(path.read_bytes()).hexdigest() != checkpoint["sha256"]:
            raise ValueError("Checkpoint changed before holdout")
        assert any(
            x["sha256"] == checkpoint["sha256"]
            for x in manifest["completed_checkpoints"]
        )
        model = NCA().cuda()
        model.load_state_dict(
            torch.load(path, map_location="cuda", weights_only=True)["model"]
        )
        model.eval()
        modelout = out / record["id"]
        modelout.mkdir(parents=True)
        for update_seed in cfg["update_seeds"]:
            tasks = [("persistence", None)] + [
                (name, masks[name]) for name in cfg["damage"]["masks"]
            ]
            if update_seed == cfg["negative_all_erased"]["update_seed"]:
                tasks.append(("all-erased-negative", masks["all-erased-negative"]))
            for kind, mask in tasks:
                if time.monotonic() > deadline:
                    results.append(
                        {
                            "model_id": record["id"],
                            "kind": kind,
                            "update_seed": update_seed,
                            "status": "not-started: evaluation deadline",
                            "criterion_passed": False,
                        }
                    )
                    continue
                trace = update_seed == cfg["trace_update_seed"] and kind == cfg["trace_damage_kind"]
                item = one(
                    model,
                    goal,
                    xy,
                    ray,
                    kind,
                    update_seed,
                    mask,
                    modelout / f"{kind}-s{update_seed}",
                    trace,
                )
                item.update(
                    model_id=record["id"],
                    regime=record["regime"],
                    initialization_seed=record["initialization_seed"],
                    checkpoint_sha256=checkpoint["sha256"],
                    checkpoint_barrier_sha256=sha256(
                        barrier_path.read_bytes()
                    ).hexdigest(),
                )
                results.append(item)
                dump(
                    out / "progress.json",
                    {
                        "expected": cfg["total_expected_evaluation_runs"],
                        "returned": len(results),
                        "results": results,
                    },
                )
                print(
                    {
                        "stage": "evaluation",
                        "model": record["id"],
                        "kind": kind,
                        "seed": update_seed,
                        "status": item["status"],
                        "criterion": item["criterion_passed"],
                    },
                    flush=True,
                )
    return results
