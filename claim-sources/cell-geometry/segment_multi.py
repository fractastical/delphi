"""Segment the tissue images and the synthetic tilings with several Cellpose checkpoints on a GPU.

The published masks come from a single checkpoint (CPSAM v2 on Nebius), and
segmenter_bias.py showed that checkpoint pulls junctions toward 120 degrees. This script
asks whether that is a property of CPSAM or of Cellpose in general: it runs the same inputs
through CPSAM and the older flow-based models (cyto3, cyto2) at a few flow thresholds, and
writes label masks in the same format as results/<id>/mask.png so analyze.measure can score
them all identically (see compare_segmenters.py).

Runs anywhere with a CUDA GPU and `pip install cellpose`; it was run on an NVIDIA Brev L40S.

    python3 segment_multi.py --inputs inputs --out results/segmenter-compare [--models cpsam,cyto3,cyto2]
"""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
from PIL import Image

FLOW_THRESHOLDS = [0.4, 0.8]  # Cellpose default and a permissive setting


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jobs(inputs):
    """(image_id, image_path, diameter) for the tissue images and the synthetic tilings."""
    out = []
    sources = json.loads((inputs / "sources.json").read_text())
    for iid, meta in sources.items():
        out.append((iid, inputs / meta["image"], meta.get("cellpose_diameter")))
    synth = inputs / "synthetic" / "manifest.json"
    if synth.exists():
        for iid, meta in json.loads(synth.read_text()).items():
            out.append((f"synthetic/{iid}", inputs / "synthetic" / f"{iid}.png", meta.get("cellpose_diameter")))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, default=Path("inputs"))
    ap.add_argument("--out", type=Path, default=Path("results/segmenter-compare"))
    ap.add_argument("--models", default="cpsam,cyto3,cyto2")
    args = ap.parse_args()

    import torch
    from cellpose import models, version as cp_version

    gpu = torch.cuda.is_available()
    device = torch.cuda.get_device_name(0) if gpu else platform.processor()
    print(f"cellpose {cp_version} torch {torch.__version__} gpu={gpu} ({device})")

    todo = jobs(args.inputs)
    for name in args.models.split(","):
        try:
            model = models.CellposeModel(gpu=gpu, pretrained_model=name)
        except Exception as e:
            print(f"{name}: cannot load ({e})")
            continue
        thresholds = [0.4] if name == "cpsam" else FLOW_THRESHOLDS
        for ft in thresholds:
            tag = f"{name}-ft{ft}"
            for iid, path, diam in todo:
                out = args.out / tag / iid
                if (out / "mask.png").exists():
                    continue
                out.mkdir(parents=True, exist_ok=True)
                img = np.array(Image.open(path).convert("RGB"))
                t0 = time.time()
                try:
                    kw = {"flow_threshold": ft}
                    if name != "cpsam":  # cpsam ignores diameter; flow models need it
                        kw["diameter"] = diam
                        kw["channels"] = [0, 0]
                    masks = model.eval(img, **kw)[0]
                except Exception as e:
                    print(f"{tag} {iid}: FAILED {e}")
                    (out / "error.txt").write_text(str(e))
                    continue
                dt = time.time() - t0
                n = int(masks.max())
                assert n < 65535
                Image.fromarray(masks.astype(np.uint16)).save(out / "mask.png")
                (out / "cellpose.json").write_text(json.dumps({
                    "image_id": iid, "model": name, "flow_threshold": ft, "diameter": diam,
                    "cellpose_version": cp_version, "torch_version": torch.__version__,
                    "device": device, "platform": "NVIDIA Brev (massedcompute L40S)" if gpu else "cpu",
                    "input_sha256": sha256(path), "mask_sha256": sha256(out / "mask.png"),
                    "object_count": n, "image_shape": list(masks.shape), "seconds": round(dt, 2),
                }, indent=1))
                print(f"{tag} {iid}: {n} cells in {dt:.1f}s")


if __name__ == "__main__":
    main()
