"""Animation of the ACTUAL saved reaction-diffusion fields (engineering/simulation/rd/*.npz): one saved frame per video frame, nothing interpolated.
Clock: RD MODEL time tau = gamma t (dimensionless), unrelated to glide seconds; the two animations are not coupled.
Usage: python3 -m engineering.simulation.animate_rd RDDIR OUTDIR"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.fft import dct

FPS = 25
W, H = 1280, 720


def mode_of(u):
    c = np.abs(dct(u - u.mean(), type=2, norm="ortho")); c[0] = 0
    return int(c.argmax())


def main(rd, out):
    rd, out = Path(rd), Path(out)
    rec = json.loads((rd / "receipt.json").read_text())
    data = []
    for c in rec["cells"]:
        z = np.load(rd / c["frames_file"])
        data.append((c, z["t_tau"], z["u"], z["x_m"], float(z["u_star"])))
    nfr = len(data[0][1])
    frames = out / "frames_rd"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    fig, axs = plt.subplots(3, 2, figsize=(W / 100, H / 100), dpi=100, gridspec_kw={"height_ratios": [1, 1.1, 0.8]})
    fig.subplots_adjust(left=0.07, right=0.985, top=0.87, bottom=0.13, hspace=0.55, wspace=0.22)
    lines = []
    for j, (c, t, U, x, ust) in enumerate(data):
        a0, a1, a2 = axs[0][j], axs[1][j], axs[2][j]
        lo, hi = float(U.min()), float(U.max())
        a0.set_xlim(x[0], x[-1]); a0.set_ylim(lo - 0.05 * (hi - lo), hi + 0.08 * (hi - lo)); a0.axhline(ust, color="#999", ls="--", lw=0.8)
        a0.set_xlabel("x (model length units, Du = 1)"); a0.set_ylabel("u(x, tau)")
        ln, = a0.plot([], [], color="#1f77b4", lw=2)
        a1.set_xlim(x[0], x[-1]); a1.set_ylim(t[-1], 0); a1.set_xlabel("x"); a1.set_ylabel("tau (RD model time)")
        img = a1.imshow(np.full((len(t), len(x)), np.nan), aspect="auto", extent=[x[0], x[-1], t[-1], 0], vmin=lo, vmax=hi, cmap="viridis", interpolation="nearest")
        amp = U.std(axis=1)
        a2.set_xlim(0, t[-1]); a2.set_ylim(0, float(amp.max()) * 1.1); a2.set_xlabel("tau"); a2.set_ylabel("std of u")
        la, = a2.plot([], [], color="#d62728", lw=2)
        tx = a2.text(0.02, 0.8, "", transform=a2.transAxes, fontsize=8)
        a0.set_title(c["label"][:80] + ("..." if len(c["label"]) > 80 else ""), fontsize=7)
        lines.append((ln, img, la, tx, amp))
    sup = fig.suptitle("", fontsize=10)
    fig.text(0.5, 0.012, "SIMULATED reaction-diffusion fields (declared Schnakenberg/Brusselator, zero-flux 1-D); every video frame is one SAVED state (every 2 tau), nothing interpolated.\n"
             "tau is dimensionless RD model time, NOT glide seconds; no coupling between this and the glide animation; not a tissue or fin claim.", ha="center", fontsize=7, color="#444")
    for k in range(nfr):
        for j, (c, t, U, x, ust) in enumerate(data):
            ln, img, la, tx, amp = lines[j]
            ln.set_data(x, U[k])
            arr = np.full((len(t), len(x)), np.nan); arr[:k + 1] = U[:k + 1]
            img.set_data(arr)
            la.set_data(t[:k + 1], amp[:k + 1])
            tx.set_text(f"dominant mode {mode_of(U[k])}   std {amp[k]:.3f}")
        sup.set_text(f"RD model time tau = {data[0][1][k]:6.1f} of {data[0][1][-1]:.0f} (dimensionless)   frame {k+1}/{nfr}")
        fig.savefig(frames / f"f{k:04d}.png")
    poster = out / "poster_rd.png"
    shutil.copy(frames / f"f{nfr-1:04d}.png", poster)
    mp4 = out / "rd_fields.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "30", "-preset", "slow", "-movflags", "+faststart", str(mp4)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    sha = lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()
    man = {"kind": "RD field time-series animation", "evidence_kind": "simulated", "video": mp4.name, "video_sha256": sha(mp4), "video_bytes": mp4.stat().st_size, "poster": poster.name,
           "poster_sha256": sha(poster), "fps": FPS, "frames": nfr, "duration_video_s": nfr / FPS, "resolution": [W, H], "ffmpeg_exit": p.returncode, "ffmpeg_cmd": " ".join(cmd),
           "time_units": {"axis": "tau = gamma*t, dimensionless RD model time", "saved_every_tau": rec["cells"][0]["save_every_tau"], "frames_per_saved_state": 1, "interpolation": "none",
                          "separate_from": "glide seconds; the two clocks are unrelated and not coupled"},
           "receipt_sha256": sha(rd / "receipt.json"), "cells": [{"cell_id": c["cell_id"], "label": c["label"], "frames_sha256": c["frames_sha256"], "reproduces_frozen_row": c["reproduces_frozen_row"]} for c in rec["cells"]],
           "source": rec["source"], "code": {"module": "engineering/simulation/animate_rd.py", "sha256": sha(Path(__file__))},
           "not_established": ["any biological or fin-tissue mechanism", "coupling between RD and glide models", "that the frozen sweep prior is realistic"]}
    (out / "manifest_rd.json").write_text(json.dumps(man, indent=1))
    shutil.rmtree(frames)
    print(json.dumps({k: man[k] for k in ("video", "video_bytes", "duration_video_s", "ffmpeg_exit")}))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
