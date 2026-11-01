"""Deterministically project an existing v3a fin into a declared design target."""

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/nca-pattern"
SOURCE = ROOT / "artifacts/fish3d/fish3d-v3a-fan"


def build():
    fin = json.loads((SOURCE / "panels.json").read_text())["fins"]["pectoral_L"]
    rays = json.loads((SOURCE / "rays.json").read_text())["fins"]["pectoral_L"]["rays"]
    origin = np.asarray(fin["fin_plane"]["origin_m"])
    span = np.asarray(fin["fin_plane"]["e_u"])
    chord = np.asarray(fin["fin_plane"]["e_w"])

    def project(points):
        points = np.asarray(points) - origin
        return np.stack([points @ span, points @ chord], axis=-1)

    outline = project(fin["outline_m"])
    lower = outline.min(axis=0)
    upper = outline.max(axis=0)
    pitch = float(max(upper - lower) / 48)
    center = (lower + upper) / 2

    def pixels(points):
        q = (project(points) - center) / pitch + 31.5
        q[:, 1] = 63 - q[:, 1]
        return [tuple(x) for x in q]

    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.polygon(pixels(fin["outline_m"]), fill=(42, 143, 173, 255))
    rayimage = Image.new("L", (64, 64))
    rd = ImageDraw.Draw(rayimage)
    for ray in rays:
        for line in ray["polylines_m"]:
            pts = pixels(line)
            draw.line(pts, fill=(190, 232, 222, 255), width=1)
            rd.line(pts, fill=255, width=1)
    rgba = np.asarray(image, dtype=np.float32) / 255
    # Keep ray endpoints inside the declared fin silhouette by intersecting alpha.
    silhouette = Image.new("L", (64, 64))
    ImageDraw.Draw(silhouette).polygon(pixels(fin["outline_m"]), fill=255)
    inside = np.asarray(silhouette) > 0
    rgba[~inside] = 0
    root = np.asarray(pixels([origin]))[0]
    seed_xy = [int(round(root[0])), int(round(root[1]))]
    rgba_image = Image.fromarray(np.round(rgba * 255).astype(np.uint8))
    ART.mkdir(parents=True, exist_ok=True)
    rgba_image.save(ART / "target-design.png")
    np.savez_compressed(
        ART / "target.npz",
        rgba=rgba,
        ray_mask=(np.asarray(rayimage) > 0) & inside,
        silhouette=inside,
        seed_xy=np.asarray(seed_xy, dtype=np.int64),
    )
    yy, xx = np.mgrid[:64, :64]
    masks = {
        "left-half": xx < 32,
        "central-square": (abs(xx - 32) < 10) & (abs(yy - 32) < 10),
        "diagonal-slit": abs(yy - 0.6 * xx - 12) < 4,
        "all-erased-negative": np.ones((64, 64), dtype=bool),
    }
    np.savez_compressed(ART / "heldout-masks.npz", **masks)
    meta = {
        "schema": "frontier.nca.design-target/1",
        "status": "design goal, not observed biological image or fabricated tissue measurement",
        "source_geometry": "fish3d-v3a-fan, pectoral_L",
        "source_files": [
            {
                "path": str((SOURCE / name).relative_to(ROOT)),
                "sha256": sha256((SOURCE / name).read_bytes()).hexdigest(),
            }
            for name in ["candidate.json", "panels.json", "rays.json"]
        ],
        "projection": {
            "x": "fin-plane span basis e_u",
            "y": "negative fin-plane chord basis e_w (image row axis)",
            "nominal_m_per_pixel": pitch,
            "pixel_grid": [64, 64],
            "seed_xy": seed_xy,
            "scale_note": "Computational raster pixels are NOT biological cells; no biological time step or cell size is assigned",
        },
        "target_sha256": sha256((ART / "target.npz").read_bytes()).hexdigest(),
        "target_png_sha256": sha256(
            (ART / "target-design.png").read_bytes()
        ).hexdigest(),
        "heldout_masks_sha256": sha256(
            (ART / "heldout-masks.npz").read_bytes()
        ).hexdigest(),
        "source_generation_code_sha256": sha256(
            Path(__file__).read_bytes()
        ).hexdigest(),
        "foreground_pixels": int(inside.sum()),
        "ray_pixels": int(((np.asarray(rayimage) > 0) & inside).sum()),
        "palette": "Declared blue membrane/pale rays, not measured pigmentation",
        "all_zero_baseline_MSE": float(np.mean(rgba**2)),
    }
    (ART / "target-manifest.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta))


if __name__ == "__main__":
    build()
