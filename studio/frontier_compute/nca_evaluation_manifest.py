"""Independently commit NCA design evaluation masks before new training outcomes.

Inputs are the preregistered protocol, design target and previous mask arrays.
The generator never opens weights, training logs or model evaluation outputs.
"""

import argparse
import hashlib
import json
from pathlib import Path
import random

import numpy as np


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(protocol_path, target_path, previous_masks, output, generation_seed):
    protocol = json.loads(protocol_path.read_text())
    if digest(target_path) != protocol["target"]["sha256"]:
        raise ValueError("Target does not match frozen protocol")
    with np.load(target_path, allow_pickle=False) as archive:
        foreground = archive["silhouette"].copy()
    if (
        foreground.shape != (64, 64)
        or foreground.dtype != np.bool_
        or not foreground.any()
    ):
        raise ValueError("Invalid target foreground")
    with np.load(previous_masks, allow_pickle=False) as archive:
        old = [archive[name].copy() for name in archive.files]
    rng = random.Random(generation_seed)
    excluded = {7001, 7002, 7003}
    for seed in [20261031, 20261101, *protocol["training"]["model_seeds"]]:
        excluded.update(seed + offset for offset in [0, 11, 17, 113, 211])
    update_seeds = []
    while len(update_seeds) < 3:
        value = rng.randrange(100_000_000, 2**31)
        if value not in excluded and value not in update_seeds:
            update_seeds.append(value)
    y, x = np.mgrid[:64, :64]
    masks = {}
    rows = []
    for case in protocol["evaluation"]["mask_cases"]:
        name, family, bounds = case["id"], case["family"], case["parameters"]
        for attempt in range(1, 101):
            if family == "left-prefix":
                params = {"cutoff": bounds["cutoff"], "formula": "x<cutoff"}
                mask = x < params["cutoff"]
            elif family == "right-suffix":
                params = {
                    "cutoff": rng.randint(*bounds["cutoff_uniform_integer_inclusive"]),
                    "formula": "x>=cutoff",
                }
                mask = x >= params["cutoff"]
            elif family == "oblique-root":
                params = {
                    "slope": rng.uniform(*bounds["slope_uniform"]),
                    "offset": rng.uniform(*bounds["offset_uniform"]),
                    "formula": "x+slope*(y-32)<offset",
                }
                mask = x + params["slope"] * (y - 32) < params["offset"]
            elif family == "disk":
                params = {
                    "center_x": rng.uniform(*bounds["center_x_uniform"]),
                    "center_y": rng.uniform(*bounds["center_y_uniform"]),
                    "radius": rng.uniform(*bounds["radius_uniform"]),
                    "formula": "(x-center_x)^2+(y-center_y)^2<=radius^2",
                }
                mask = (x - params["center_x"]) ** 2 + (
                    y - params["center_y"]
                ) ** 2 <= params["radius"] ** 2
            elif family == "horizontal-slab":
                params = {
                    "y0": rng.randint(*bounds["y0_uniform_integer_inclusive"]),
                    "width": rng.randint(*bounds["width_uniform_integer_inclusive"]),
                    "formula": "y0<=y<y0+width",
                }
                mask = (y >= params["y0"]) & (y < params["y0"] + params["width"])
            else:
                raise ValueError("Unsupported preregistered family")
            removed = int(np.count_nonzero(mask & foreground))
            fraction = removed / int(foreground.sum())
            if 0.1 <= fraction <= 0.85 and not any(
                np.array_equal(mask, m) for m in [*old, *masks.values()]
            ):
                break
        else:
            raise ValueError(
                "Mask failed frozen nonvacuity/exclusion rules after100draws"
            )
        masks[name] = mask
        rows.append(
            {
                "id": name,
                "family": family,
                "parameters": params,
                "mask_array_sha256": hashlib.sha256(
                    mask.tobytes(order="C")
                ).hexdigest(),
                "erased_pixels": int(mask.sum()),
                "target_erased_pixels": removed,
                "target_erased_fraction": fraction,
                "draw_attempt": attempt,
            }
        )
    masks["all-erased-negative"] = np.ones((64, 64), dtype=bool)
    output.mkdir(parents=True, exist_ok=True)
    array_path = output / "evaluation-masks.npz"
    np.savez_compressed(array_path, **masks)
    manifest = {
        "schema": "frontier.nca.curriculum-evaluation/1",
        "protocol_sha256": digest(protocol_path),
        "target_sha256": digest(target_path),
        "coordinate_system": {
            "shape": [64, 64],
            "x": "column",
            "y": "row",
            "mask_true": "eraseall16",
        },
        "update_seeds": update_seeds,
        "mask_file_sha256": digest(array_path),
        "masks": rows,
        "producer": "infra_director independent of training implementation",
        "generation_seed": generation_seed,
        "generator_sha256": digest(Path(__file__)),
        "numpy_version": np.__version__,
        "previous_masks_sha256": digest(previous_masks),
        "negative_mask_array_sha256": hashlib.sha256(
            masks["all-erased-negative"].tobytes(order="C")
        ).hexdigest(),
        "counts": {
            "design_masks": 7,
            "all_erased_negative_masks": 1,
            "update_seeds": 3,
            "expected_models": 8,
            "expected_design_probes": 192,
            "expected_all_erased_probes": 8,
        },
        "scope": "Synthetic evaluation perturbations, not measured biology. Independent commitment and source-order read guard; not cryptographic secrecy.",
    }
    (output / "evaluation-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--previous-masks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generation-seed", type=int, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            generate(
                args.protocol,
                args.target,
                args.previous_masks,
                args.output,
                args.generation_seed,
            ),
            indent=2,
        )
    )
