"""Render the 2-D NS demo video from the returned 8-bit vorticity frames only. Caption states label, job id, frames hash, simulated, not biology.
  python3 -m frontier_compute.render_flow_video OUTDIR OUT.mp4 --job JOB --label "PARTIAL: ..." """
import hashlib, json, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FFMpegWriter


def main(outdir, out, job, label, title="2-D incompressible Navier-Stokes, double shear layer"):
    z = np.load(f"{outdir}/flow_frames_q8.npz")
    q, t, vmax, N = z["q"], z["t"], float(z["vmax"]), int(z["N"])
    sha = hashlib.sha256(open(f"{outdir}/flow_frames_q8.npz", "rb").read()).hexdigest()
    fig, ax = plt.subplots(figsize=(6.4, 7.0))
    im = ax.imshow(((q[0].astype(float) / 127.5 - 1) * vmax).T, cmap="RdBu_r", vmin=-vmax, vmax=vmax, origin="lower", extent=[0, 2 * np.pi, 0, 2 * np.pi])
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ttl = ax.set_title("", fontsize=9)
    fig.colorbar(im, ax=ax, label="vorticity (clip at 99.5th percentile)", shrink=0.8)
    import textwrap
    cap = f"{title}, N={N}^2, float64 (simulated; not biology). GPU job {job}; frames sha256 {sha[:16]}... {label}"
    fig.suptitle("\n".join(textwrap.wrap(cap, 78)), fontsize=7)
    fig.text(0.5, 0.01, "Frames: actual vorticity, spectrally low-passed to 128x128 and 8-bit quantized for return.", ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 0.90))
    w = FFMpegWriter(fps=12, codec="libx264", extra_args=["-pix_fmt", "yuv420p"])
    with w.saving(fig, out, dpi=110):
        for i in range(len(q)):
            im.set_data(((q[i].astype(float) / 127.5 - 1) * vmax).T)
            ttl.set_text(f"t = {t[i]:.2f}")
            w.grab_frame()
    print("wrote", out, len(q), "frames")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[a.index("--job") + 1], a[a.index("--label") + 1], a[a.index("--title") + 1] if "--title" in a else "2-D incompressible Navier-Stokes, double shear layer")
