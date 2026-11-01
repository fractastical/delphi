"""Matched pool training with explicit partial checkpoints and no heldout reads."""

from datetime import datetime, timezone
from hashlib import sha256
import time

import numpy as np
import torch

from .model import NCA, dump, protocol, seed, target
from .curriculum_policy import damage_masks


def tensor_hash(model):
    digest = sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def checkpoint(path, model, optimizer, step, fire_generator, pool_rng, damage_rng):
    temp = path.with_suffix(".tmp")
    torch.save(
        {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "step": step,
            "torch_rng": torch.get_rng_state(),
            "fire_rng": fire_generator.get_state(),
            "pool_rng": pool_rng.bit_generator.state,
            "damage_rng": damage_rng.bit_generator.state,
            "pool_state_saved": False,
        },
        temp,
    )
    temp.replace(path)
    return {
        "path": str(path),
        "sha256": sha256(path.read_bytes()).hexdigest(),
        "step": step,
        "model_tensor_sha256": tensor_hash(model),
        "resume_scope": "Pool not saved; not an exact resumable training state",
    }


def circles(rng, n, size, device):
    yy, xx = torch.meshgrid(
        torch.linspace(-1, 1, size, device=device),
        torch.linspace(-1, 1, size, device=device),
        indexing="ij",
    )
    centers = rng.uniform(-0.5, 0.5, (n, 2))
    radii = rng.uniform(0.1, 0.4, n)
    return torch.stack(
        [
            ((xx - cx) ** 2 + (yy - cy) ** 2) >= radius**2
            for (cx, cy), radius in zip(centers, radii, strict=True)
        ]
    )[:, None]


def train_one(regime, initialization_seed, out, deadline):
    cfg = protocol()["training"]
    device = "cuda"
    name = f"{regime}-s{initialization_seed}"
    directory = out / name
    directory.mkdir(parents=True)
    torch.manual_seed(initialization_seed)
    model = NCA().to(device)
    initial_hash = tensor_hash(model)
    goal, xy, _ = target(device)
    original = seed(64, xy, device=device)
    pool = original.repeat(cfg["pool_size"], 1, 1, 1)
    optimizer = torch.optim.Adam(
        model.parameters(), lr=0.002, betas=(0.9, 0.999), eps=1e-7
    )
    pool_rng = np.random.default_rng(initialization_seed + 11)
    damage_rng = np.random.default_rng(initialization_seed + 113)
    prefix_rng = np.random.default_rng(initialization_seed + 211)
    fire = torch.Generator(device=device).manual_seed(initialization_seed + 17)
    history = []
    steps = 0
    updates = 0
    status = "complete"
    error = None
    started = time.monotonic()
    latest = checkpoint(
        directory / "latest.pt", model, optimizer, 0, fire, pool_rng, damage_rng
    )
    for iteration in range(cfg["steps_per_model"]):
        if time.monotonic() > deadline:
            status = "partial: training deadline reached"
            break
        indexes = pool_rng.choice(cfg["pool_size"], cfg["batch_size"], replace=False)
        ids = torch.as_tensor(indexes, device=device)
        state = pool[ids].clone()
        rank = ((state[:, :4] - goal) ** 2).mean(dim=(1, 2, 3)).argsort(descending=True)
        state = state[rank]
        ids = ids[rank]
        state[0] = original[0]
        if regime in ["damage-pool", "curriculum-pool"]:
            masks, prefix_cutoff = damage_masks(regime, iteration, circles(damage_rng, 3, 64, device), prefix_rng, cfg["prefix_schedule"])
            state[-3:] *= masks
        count = int(pool_rng.integers(64, 96))
        optimizer.zero_grad(set_to_none=True)
        for _ in range(count):
            state = model(state, generator=fire)
        loss = ((state[:, :4] - goal) ** 2).mean()
        if (
            not bool(torch.isfinite(state).all())
            or not bool(torch.isfinite(loss))
            or float(state.detach().abs().max()) > 100
        ):
            status = "failed: nonfinite or state magnitude guard"
            error = {"iteration": iteration, "reason": status}
            break
        loss.backward()
        finite = all(
            parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
            for parameter in model.parameters()
        )
        if not finite:
            status = "failed: nonfinite gradient"
            error = {"iteration": iteration, "reason": status}
            break
        for parameter in model.parameters():
            parameter.grad.div_(torch.linalg.vector_norm(parameter.grad) + 1e-8)
        optimizer.step()
        with torch.no_grad():
            pool[ids] = state.detach()
        steps = iteration + 1
        updates += count
        if steps == 1 or steps % 25 == 0:
            history.append(
                {
                    "training_step": steps,
                    "batch_output_loss_before_parameter_update": float(loss.detach()),
                    "CA_updates_this_step": count,
                    "CA_updates_total": updates,
                    "max_abs_batch_state": float(state.detach().abs().max()),
                    "prefix_cutoff_draw": prefix_cutoff,
                    "prefix_applied": regime == "curriculum-pool",
                    "elapsed_wall_s": time.monotonic() - started,
                }
            )
        if steps % 100 == 0:
            print({"stage": "training", "id": name, **history[-1]}, flush=True)
        if steps % cfg["checkpoints_every_steps"] == 0:
            latest = checkpoint(
                directory / "latest.pt",
                model,
                optimizer,
                steps,
                fire,
                pool_rng,
                damage_rng,
            )
            dump(directory / "history.json", history)
    torch.cuda.synchronize()
    if steps < cfg["steps_per_model"] and status == "complete":
        status = "partial: training did not reach frozen step count"
    final = checkpoint(
        directory / ("final.pt" if status == "complete" else "partial.pt"),
        model,
        optimizer,
        steps,
        fire,
        pool_rng,
        damage_rng,
    )
    result = {
        "id": name,
        "regime": regime,
        "initialization_seed": initialization_seed,
        "status": status,
        "training_steps": steps,
        "CA_updates_total": updates,
        "initial_model_tensor_sha256": initial_hash,
        "final_checkpoint": final,
        "latest_periodic_checkpoint": latest,
        "history_path": str(directory / "history.json"),
        "training_wall_s": time.monotonic() - started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "failure": error,
        "heldout_data_read": False,
        "scope": "Actual local-rule image optimization; no biological calibration.",
    }
    dump(directory / "history.json", history)
    dump(directory / "training.json", result)
    return result
