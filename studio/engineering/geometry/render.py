"""Small PNG renders drawn from the actual exported triangles (no separate illustration)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

VIEWS = (("top", 90, -90), ("side", 0, -90), ("three-quarter", 24, -58))


def _shade(tri: np.ndarray, base=(0.32, 0.55, 0.78)) -> np.ndarray:
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    light = np.array([0.35, -0.45, 0.82])
    light /= np.linalg.norm(light)
    k = 0.35 + 0.65 * np.abs(n @ light)
    return np.clip(np.outer(k, base), 0, 1)


def render(parts: list[tuple[np.ndarray, np.ndarray, tuple]], path, title: str, dpi: int = 110) -> None:
    allv = np.concatenate([p[0] for p in parts])
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    fig = plt.figure(figsize=(10.5, 3.6), dpi=dpi)
    for i, (name, elev, azim) in enumerate(VIEWS):
        ax = fig.add_subplot(1, 3, i + 1, projection="3d")
        for V, T, color in parts:
            tri = V[T]
            pc = Poly3DCollection(tri, facecolors=_shade(tri, color), edgecolors="none", linewidths=0)
            ax.add_collection3d(pc)
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(hi - lo)
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        ax.set_title(name, fontsize=8)
    size = hi - lo
    fig.suptitle(f"{title}\nrendered from the exported mesh; extent {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm",
                 fontsize=8)
    fig.tight_layout()
    fig.savefig(path, metadata={"Software": None, "Creation Time": None})
    plt.close(fig)
