"""Distill-style learned local pattern rule; no biochemical interpretation."""

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/nca-pattern"


def protocol():
    return json.loads((ART / "protocol.json").read_text())


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def target(device="cpu"):
    p = protocol()["target"]
    path = ROOT / p["path"]
    if sha256(path.read_bytes()).hexdigest() != p["sha256"]:
        raise ValueError("frozen target bytes changed")
    with np.load(path) as data:
        rgba = torch.from_numpy(data["rgba"].copy()).permute(2, 0, 1)[None]
        seed_xy = data["seed_xy"].tolist()
        ray = torch.from_numpy(data["ray_mask"].copy())
    return rgba.to(device), seed_xy, ray.to(device)


def seed(size, xy, batch=1, device="cpu", dtype=torch.float32):
    state = torch.zeros(batch, 16, size, size, device=device, dtype=dtype)
    state[:, 3:, xy[1], xy[0]] = 1
    return state


def alive(state):
    return F.max_pool2d(state[:, 3:4], 3, stride=1, padding=1) > 0.1


class NCA(nn.Module):
    def __init__(self):
        super().__init__()
        identity = torch.zeros(3, 3)
        identity[1, 1] = 1
        dx = (
            torch.outer(torch.tensor([1.0, 2.0, 1.0]), torch.tensor([-1.0, 0.0, 1.0]))
            / 8
        )
        kernels = torch.stack([identity, dx, dx.T])[:, None].repeat(16, 1, 1, 1)
        self.register_buffer("kernels", kernels)
        self.hidden = nn.Conv2d(48, 128, 1)
        self.output = nn.Conv2d(128, 16, 1)
        nn.init.xavier_uniform_(self.hidden.weight)
        nn.init.zeros_(self.hidden.bias)
        nn.init.zeros_(self.output.weight)
        nn.init.zeros_(self.output.bias)

    def forward(self, state, generator=None, fire_mask=None):
        pre = alive(state)
        perception = F.conv2d(state, self.kernels, padding=1, groups=16)
        delta = self.output(F.relu(self.hidden(perception)))
        if fire_mask is None:
            fire_mask = (
                torch.rand(
                    (state.shape[0], 1, *state.shape[-2:]),
                    device=state.device,
                    generator=generator,
                )
                < 0.5
            )
        new = state + delta * fire_mask
        return new * (pre & alive(new))


def metrics(state, goal, ray_mask):
    visible = state[:, :4]
    foreground = goal[:, 3:4] > 0.1
    predicted = state[:, 3:4] > 0.1
    intersection = (foreground & predicted).sum().item()
    union = (foreground | predicted).sum().item()
    mse = float(torch.mean((visible.double() - goal.double()) ** 2).item())
    iou = float(intersection / union) if union else 0.0
    ray_error = float(
        ((state[:, :3].double() - goal[:, :3].double()) ** 2)[:, :, ray_mask]
        .mean()
        .item()
    )
    return {
        "rgba_MSE": mse,
        "silhouette_IoU": iou,
        "living_pixels": int(predicted.sum().item()),
        "ray_RGB_MSE": ray_error,
        "max_abs_state": float(state.abs().max().item()),
        "finite": bool(torch.isfinite(state).all().item()),
        "design_match": bool(iou >= 0.75 and mse <= 0.02),
    }


def configure():
    torch.set_num_threads(2)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.set_float32_matmul_precision("highest")


def cpu_controls():
    configure()
    torch.manual_seed(9901)
    goal, xy, ray = target()
    model = NCA().double()
    tinygoal = F.interpolate(goal.double(), size=(12, 12), mode="area")
    tinyxy = [max(0, min(11, round(x * 12 / 64))) for x in xy]
    initial = seed(12, tinyxy, dtype=torch.float64)
    fire = torch.ones(1, 1, 12, 12, dtype=torch.bool)

    def loss():
        state = model(model(initial, fire_mask=fire), fire_mask=fire)
        return ((state[:, :4] - tinygoal) ** 2).mean()

    value = loss()
    value.backward()
    name, parameter = max(
        model.named_parameters(), key=lambda item: float(item[1].grad.abs().max())
    )
    flat_index = int(parameter.grad.abs().argmax())
    analytic = float(parameter.grad.flatten()[flat_index])
    epsilon = protocol()["controls"]["cpu_finite_difference_eps"]
    with torch.no_grad():
        old = float(parameter.flatten()[flat_index])
        parameter.flatten()[flat_index] = old + epsilon
        plus = float(loss())
        parameter.flatten()[flat_index] = old - epsilon
        minus = float(loss())
        parameter.flatten()[flat_index] = old
    difference = (plus - minus) / (2 * epsilon)
    relative = abs(difference - analytic) / max(abs(difference), abs(analytic), 1e-8)
    wrong = abs(difference + analytic) / max(abs(difference), abs(analytic), 1e-8)
    before = [p.detach().clone() for p in model.parameters()]
    optimizer = torch.optim.Adam(model.parameters(), lr=0.002, eps=1e-7)
    optimizer.step()
    changed = max(
        float((p - b).abs().max())
        for p, b in zip(model.parameters(), before, strict=True)
    )
    fresh = NCA()
    original = seed(64, xy)
    untrained = fresh(original, fire_mask=torch.ones(1, 1, 64, 64, dtype=torch.bool))
    biased = NCA()
    with torch.no_grad():
        biased.output.bias.fill_(0.2)
    zero = biased(
        torch.zeros_like(original), fire_mask=torch.ones(1, 1, 64, 64, dtype=torch.bool)
    )
    # Nonzero rule makes the local-dependency test nonvacuous.
    torch.manual_seed(19)
    rule = NCA()
    nn.init.normal_(rule.output.weight, std=0.01)
    state = torch.randn(1, 16, 12, 12) * 0.01
    state[:, 3] = 0.5
    mask = torch.ones(1, 1, 12, 12, dtype=torch.bool)
    baseline = rule(state, fire_mask=mask)
    far = state.clone()
    far[:, :, 0, 0] += 0.2
    near = state.clone()
    near[:, :, 6, 7] += 0.02
    far_delta = float(
        (rule(far, fire_mask=mask)[:, :, 6, 6] - baseline[:, :, 6, 6]).abs().max()
    )
    near_delta = float(
        (rule(near, fire_mask=mask)[:, :, 6, 6] - baseline[:, :, 6, 6]).abs().max()
    )
    checks = {
        "finite_nonzero_gradient": bool(np.isfinite(analytic) and abs(analytic) > 1e-8),
        "finite_difference": relative <= 0.0001,
        "wrong_sign_gradient_rejected": wrong >= 1.0,
        "optimizer_changed_weights": changed > 1e-8,
        "optimizer_loss_finite": bool(torch.isfinite(loss())),
        "empty_state_absorbing": bool(torch.count_nonzero(zero) == 0),
        "zero_updater_seed_only": bool(torch.equal(untrained, original)),
        "zero_updater_fails_target": not metrics(untrained, goal, ray)["design_match"],
        "bounded_local_dependency": far_delta == 0 and near_delta > 1e-8,
        "parameter_count": sum(p.numel() for p in fresh.parameters()) == 8336,
    }
    return {
        "schema": "frontier.nca.cpu-controls/1",
        "checks": checks,
        "passed": all(checks.values()),
        "analytic_gradient": analytic,
        "finite_difference": difference,
        "relative_error": relative,
        "wrong_sign_relative_error": wrong,
        "selected_parameter": name,
        "selected_flat_index": flat_index,
        "optimizer_parameter_change_max": changed,
        "far_perturbation_delta": far_delta,
        "near_perturbation_delta": near_delta,
        "untrained_metrics": metrics(untrained, goal, ray),
        "scope": "Finite/local rule and actual gradient checks only; no training or biological validation.",
    }


def cuda_controls():
    configure()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required; no CPU training fallback")
    torch.manual_seed(771)
    cpu = NCA()
    nn.init.normal_(cpu.output.weight, std=0.01)
    gpu = NCA().cuda()
    gpu.load_state_dict(cpu.state_dict())
    state = torch.randn(1, 16, 12, 12) * 0.01
    state[:, 3] = 0.5
    mask = torch.rand(1, 1, 12, 12) < 0.5
    c = cpu(state, fire_mask=mask)
    g = gpu(state.cuda(), fire_mask=mask.cuda())
    c.square().mean().backward()
    g.square().mean().backward()
    cg = torch.cat([p.grad.flatten() for p in cpu.parameters()])
    gg = torch.cat([p.grad.detach().cpu().flatten() for p in gpu.parameters()])
    forward = float((c - g.detach().cpu()).abs().max())
    gradient = float(
        torch.linalg.vector_norm(cg - gg)
        / torch.linalg.vector_norm(cg).clamp_min(1e-12)
    )
    return {
        "schema": "frontier.nca.cuda-controls/1",
        "forward_max_abs": forward,
        "gradient_relative_L2": gradient,
        "passed": forward <= 0.00001 and gradient <= 0.0001,
        "actual_device": torch.cuda.get_device_name(),
        "tf32": False,
        "dtype": "float32",
        "scope": "Same-job CPU/CUDA nonzero-rule forward and gradient comparison",
    }
