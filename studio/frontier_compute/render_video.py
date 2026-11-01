"""Render a video from the ACTUAL u(x,t) frames returned by a GPU job. Nothing is drawn beyond the frames.
  python3 -m frontier_compute.render_video CELLS.json GPU_DIR OUT.mp4 --job JOBID [--ids a,b,c,...]
Layout: per cell a profile panel (u(x) at the frame time, fixed y-range from the cell's full trajectory) over a space-time map (all frames, time cursor)."""
import hashlib, json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter


def main(cells_path, gpu_dir, out, job, ids=None, label=""):
    cells = {c["id"]: c for c in json.load(open(cells_path))["cells"]}
    F = np.load(f"{gpu_dir}/gpu_fields.npz")
    have = sorted({int(k.split("_")[0]) for k in F.files if k.endswith("_frames_u")})
    ids = ids or have
    fr_sha = hashlib.sha256(open(f"{gpu_dir}/gpu_fields.npz", "rb").read()).hexdigest()
    n = len(ids)
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(2 * rows, cols, figsize=(5.2 * cols, 5.4 * rows), squeeze=False, gridspec_kw={"height_ratios": [1, 1] * rows})
    data = {}
    for k, i in enumerate(ids):
        U, t = F[f"{i}_base_frames_u"], F[f"{i}_base_frame_t"]
        c = cells[i]
        L = c["L"]
        x = (np.arange(U.shape[1]) + 0.5) * L / U.shape[1]
        r, cc = divmod(k, cols)
        ap, ak = axes[2 * r, cc], axes[2 * r + 1, cc]
        lo, hi = float(U.min()), float(U.max())
        pad = 0.05 * (hi - lo + 1e-12)
        ap.set_ylim(lo - pad, hi + pad); ap.set_xlim(0, L)
        (line,) = ap.plot(x, U[0], lw=1.6)
        ap.set_title(f"{c['model']} draw {c['draw']} x={c['x']} rho={c['rho']} eps={c['eps']} (id {i})", fontsize=8)
        ap.set_ylabel("u"); ap.tick_params(labelsize=7)
        ak.imshow(U.T, aspect="auto", origin="lower", extent=[t[0], t[-1], 0, L], cmap="viridis")
        cur = ak.axvline(t[0], color="w", lw=1)
        ak.set_xlabel("time (tau)", fontsize=8); ak.set_ylabel("x", fontsize=8); ak.tick_params(labelsize=7)
        data[i] = (U, t, line, cur)
    import textwrap
    cap = f"Simulated reaction-diffusion trajectories (declared model, 1-D Neumann, float64, GPU job {job}); not tissue. Frames file sha256 {fr_sha[:16]}...; evidence kind: simulated. {label}"
    fig.suptitle("\n".join(textwrap.wrap(cap, 150)), fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    nf = min(d[0].shape[0] for d in data.values())
    w = FFMpegWriter(fps=8, codec="libx264", extra_args=["-pix_fmt", "yuv420p"])
    with w.saving(fig, out, dpi=110):
        for f in range(nf):
            for U, t, line, cur in data.values():
                line.set_ydata(U[f]); cur.set_xdata([t[f], t[f]])
            w.grab_frame()
    print("wrote", out, nf, "frames,", n, "cells")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2], a[a.index("--job") + 1], [int(x) for x in a[a.index("--ids") + 1].split(",")] if "--ids" in a else None, a[a.index("--label") + 1] if "--label" in a else "")
