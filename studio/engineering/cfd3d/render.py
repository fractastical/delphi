"""Render a cfd3d case's actual mid-plane slices to an H.264 video (no interpolation, no synthetic frames).

Usage: python -m engineering.cfd3d.render ARTIFACT_DIR
Reads case.json, slices/*.f32 and fields/sdf.f32 written by fish.jl; writes render/flow.mp4, render/poster.png
and render/render.json (input and output sha256s).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_slice(path: Path, n1: int, n2: int, stride: int = 1, dtype: str = "float32") -> np.ndarray:
    """Slice files hold ghost-inclusive planes, optionally strided and float16 (GPU cases)."""
    m1, m2 = -(-n1 // stride), -(-n2 // stride)
    return np.fromfile(path, "<f2" if dtype == "float16" else "<f4").astype(np.float32).reshape((m1, m2, 4), order="F")


def render(art: Path) -> dict:
    case = json.loads((art / "case.json").read_text())
    g = case["grid"]
    nx, ny, nz = g["dims"]
    L, h = g["L_cells"], g["h_m"]
    zi, yi = g["slices"]["z_index"], g["slices"]["y_index"]
    st, dtype = g["slices"].get("stride", 1), g["slices"].get("dtype", "float32")
    if st == 1:
        sdf = np.fromfile(art / "fields" / "sdf.f32", "<f4").reshape((nx, ny, nz), order="F")
        # slice index k includes ghosts (k = interior index + 1); sdf holds interior only
        body_z, body_y = sdf[:, :, zi - 2], sdf[:, yi - 2, :]
    else:
        body_z = np.fromfile(art / "fields" / "sdf_z.f32", "<f4").reshape((-(-nx // st), -(-ny // st)), order="F")
        body_y = np.fromfile(art / "fields" / "sdf_y.f32", "<f4").reshape((-(-nx // st), -(-nz // st)), order="F")
    sx, sy, sz = g["snout_grid"]
    # interior cell i (1-based) has centre x_grid = i - 0.5 (WaterLily: I - 1.5 with ghost I = 1); strided
    # cells keep the same span to within one coarse cell
    ext_x = ((0.0 - sx) * h, (nx - sx) * h)
    ext_y = ((0.0 - sy) * h, (ny - sy) * h)
    ext_z = ((0.0 - sz) * h, (nz - sz) * h)
    U = case["nondim"]["U_grid"]
    frames = sorted((art / "slices").glob("z*.f32"))
    out = art / "render"
    fdir = out / "frames"
    fdir.mkdir(parents=True, exist_ok=True)
    every = g["slices"]["every_tUL"]
    cap = (f"fish3d candidate {case['candidate_sha256'][:12]} | WaterLily {case['solver']['WaterLily']} 3-D NS, "
           f"fixed rigid body, Re_L={case['nondim']['Re_L']}, L={L} cells (h={h*1e3:.2f} mm)\n"
           f"Fins are sub-grid shells ({case['resolution']['shell_simulated_thickness_mm']:.1f} mm simulated vs 0.5 mm): "
           "fin flow is not resolved. Slow water, not swimming or flight.")
    for k, fz in enumerate(frames):
        if st == 1:
            a = read_slice(fz, nx + 2, ny + 2)[1:-1, 1:-1]
            b = read_slice(art / "slices" / fz.name.replace("z", "y"), nx + 2, nz + 2)[1:-1, 1:-1]
        else:   # strided planes hold interior cells 1:st:n, aligned with the strided interior SDF planes
            a = read_slice(fz, nx, ny, st, dtype)
            b = read_slice(art / "slices" / fz.name.replace("z", "y"), nx, nz, st, dtype)
        fig, ax = plt.subplots(2, 1, figsize=(12.8, 7.2), dpi=100)
        for axk, sl, body, ext, lab in ((ax[0], a, body_z, ext_y, "y (m), plan view at fish axis z"),
                                         (ax[1], b, body_y, ext_z, "z (m), side view at y = 0")):
            speed = np.sqrt(sl[..., 0] ** 2 + sl[..., 1] ** 2 + sl[..., 2] ** 2) / U
            im = axk.imshow(speed.T, origin="lower", extent=(*ext_x, *ext), cmap="viridis", vmin=0, vmax=1.4,
                            aspect="equal")
            axk.contourf(body.T, levels=[-1e9, -1e-6], extent=(*ext_x, *ext), colors=["#f2f2f2"], origin="lower")
            axk.contour(body.T, levels=[0], extent=(*ext_x, *ext), colors=["k"], linewidths=0.6, origin="lower")
            axk.set_ylabel(lab, fontsize=8)
            axk.tick_params(labelsize=7)
        ax[1].set_xlabel("x (m), snout at 0, stream +x", fontsize=8)
        fig.colorbar(im, ax=ax, shrink=0.8, label="|u| / U")
        fig.suptitle(f"tU/L = {k * every:.2f}   " + cap, fontsize=8, x=0.02, ha="left")
        fig.savefig(fdir / f"f{k:04d}.png")
        plt.close(fig)
    mp4 = out / "flow.mp4"
    ff = shutil.which("ffmpeg")
    if ff is None:   # GPU container: static binary from the pinned imageio-ffmpeg wheel
        import imageio_ffmpeg
        ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ff, "-y", "-loglevel", "error", "-framerate", "12", "-i", str(fdir / "f%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    "-threads", "1", str(mp4)], check=True)
    poster = out / "poster.png"
    poster.write_bytes((fdir / f"f{len(frames) - 1:04d}.png").read_bytes())
    for f in fdir.glob("*.png"):
        f.unlink()
    fdir.rmdir()
    rec = {"schema": "cfd3d-render-0.1", "case_json_sha256": sha(art / "case.json"),
           "inputs": {p.name: sha(p) for p in frames} | {p.name: sha(p) for p in (art / "fields").glob("sdf*.f32")},
           "frames": len(frames), "fps": 12, "video": {"file": "flow.mp4", "sha256": sha(mp4)},
           "poster": "poster.png", "poster_sha256": sha(poster),
           "what": "actual solver mid-plane slices (|u|/U); body = SDF<=0 of the simulated union", "caption": cap}
    (out / "render.json").write_text(json.dumps(rec, indent=1))
    return rec


if __name__ == "__main__":
    r = render(Path(sys.argv[1]))
    print(json.dumps({"frames": r["frames"], "video": r["video"]}))
