"""Render a video, poster and manifest from ACTUAL computed frames (FEM solves), never from hand-drawn curves.

CLI:  python -m engineering.fin_mechanics.render REQUEST.json OUT_DIR
Writes OUT_DIR/{result.json, fin_mechanics.mp4, poster.png, manifest.json}.
Every frame carries the words 'SIMULATED' and 'ASSUMED EI range'.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import beam, sweep  # noqa: E402

FPS = 24
SECONDS = 15
W_PX, H_PX, DPI = 1280, 720, 100
BLUE, RED, GREY = "#0072B2", "#D55E00", "#555555"
BANNER = ("SIMULATED  |  Euler-Bernoulli cantilever, linear, static  |  EI range is ASSUMED, not measured  |  "
          "mean pressure proxy, no fluid-structure interaction, no biological claim")


def frame_plan(res: dict) -> list[dict]:
    """Phase 1: load ramp (V from 5% to 100% of declared, q ~ V^2) at EI_demo = EI_crit/3.
    Phase 2: EI sweep from the top to the bottom of the ASSUMED range at full declared load."""
    n = FPS * SECONDS
    n1, n2, n_hold = int(5.5 * FPS), int(8.5 * FPS), FPS
    assert n1 + n2 + n_hold == n
    ei_crit = res["critical_stiffness"]["EI_crit_Nm2_float"]
    ei_demo = ei_crit / 3.0
    lo, hi = eval_frac(res["EI_assumed_range"]["min_Nm2"]), eval_frac(res["EI_assumed_range"]["max_Nm2"])
    plan = []
    for i in range(n1):
        vf = 0.05 + 0.95 * i / (n1 - 1)
        plan.append({"phase": 1, "EI": ei_demo, "load_factor": vf**2, "v_fraction": vf})
    ei_path = np.logspace(np.log10(hi), np.log10(lo), n2)
    for e in ei_path:
        plan.append({"phase": 2, "EI": float(e), "load_factor": 1.0, "v_fraction": 1.0})
    plan += [dict(plan[-1], phase=2) for _ in range(n_hold)]
    return plan


def compute_frames(res: dict, plan: list[dict]) -> list[dict]:
    q0, L = res["load_bridge"]["q_line_N_per_m"], res["load_bridge"]["L_ray_m"]
    vl = res["request_echo"]["validity_limits"]
    lim_t, lim_s = eval_frac(vl["tip_over_L_max"]), eval_frac(vl["slope_max_rad"])
    n_el = res["request_echo"]["n_elements"]
    xs = np.linspace(0, L, 101)
    out = []
    for p in plan:
        q = q0 * p["load_factor"]
        sol, chk = beam.solve_checked(L, p["EI"], q, n_el, 0.0, lim_t, lim_s)
        w, _ = sol.evaluate(xs)
        out.append({**p, "q": q, "x": xs, "w": w, "tip_over_L": chk["tip_over_L"], "valid": chk["valid"],
                    "analytic_w": beam.w_uniform(xs, q, L, p["EI"]), "slope": chk["max_slope_rad"]})
    return out


def eval_frac(s: str) -> float:
    from fractions import Fraction
    return float(Fraction(s))


def frames_sha256(frames: list[dict]) -> str:
    h = hashlib.sha256()
    for f in frames:
        h.update(np.ascontiguousarray(f["w"], dtype=np.float64).tobytes())
        h.update(np.float64(f["EI"]).tobytes())
        h.update(np.float64(f["q"]).tobytes())
    return h.hexdigest()


def _scalar_axes(ax, res):
    rows = res["sweep"]["rows"]
    ei = np.array([r["EI_Nm2"] for r in rows])
    ax.loglog(ei, [r["uniform"]["tip_over_L"] for r in rows], color=BLUE, lw=2,
              label="uniform line load q_line (primary)")
    ax.loglog(ei, [r["tip_equivalent"]["tip_over_L"] for r in rows], color=BLUE, lw=1.5, ls="--",
              label="same total force F at tip (upper bound)")
    lim = float(eval_frac(res["request_echo"]["validity_limits"]["tip_over_L_max"]))
    ax.axhline(lim, color=RED, lw=1.5)
    ax.text(ei[0] * 1.2, lim * 1.15, f"validity limit tip/L = {lim:g} (declared)", color=RED, fontsize=8)
    crit = res["critical_stiffness"]["EI_crit_Nm2_float"]
    ax.axvspan(ei[0], crit, color=RED, alpha=0.10)
    ax.axvline(crit, color=RED, lw=1, ls=":")
    ax.text(crit * 1.1, 2e-4, f"EI_crit = {crit:.3g} N m^2", color=RED,
            fontsize=8, rotation=90, va="bottom")
    ax.text(crit * 0.8, 800, "linear model INVALID\n(flagged, left of EI_crit)", color=RED, fontsize=8, va="top", ha="right")
    b0, b1 = res["EI_context_only"]["bluegill_sunfish_B_range_Nm2"]
    ax.axvspan(b0, b1, facecolor="none", edgecolor=GREY, hatch="///", alpha=0.6, lw=0)
    ax.text(np.sqrt(b0 * b1), 2e-4, "context only: bluegill B~1e-6..1e-5\n(Alben+ 2007 Sec. 3.4: composite E x\naverage I; not a calibration)",
            fontsize=7, color=GREY, ha="center", va="bottom")
    ax.set_xlabel("bending stiffness EI  [N m^2]   (ASSUMED log-spaced range, not measured)", fontsize=9)
    ax.set_ylabel("tip deflection / L  [1]\n(simulated)", fontsize=9)
    ax.set_ylim(1e-4, 2e3)
    ax.set_xlim(ei[0], ei[-1])
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(True, which="major", alpha=0.3)
    ax.tick_params(labelsize=8)


def make_video(res: dict, out_mp4: Path) -> dict:
    plan = frame_plan(res)
    frames = compute_frames(res, plan)
    L = res["load_bridge"]["L_ray_m"]
    q_full = res["load_bridge"]["q_line_N_per_m"]
    fig = plt.figure(figsize=(W_PX / DPI, H_PX / DPI), dpi=DPI)
    gs = fig.add_gridspec(2, 2, left=0.07, right=0.97, top=0.88, bottom=0.10, hspace=0.5, wspace=0.22, height_ratios=[1.2, 1])
    axp, axq, axs = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
    fig.text(0.5, 0.965, BANNER, ha="center", va="center", fontsize=8, color=RED, weight="bold")
    title = fig.text(0.5, 0.925, "", ha="center", va="center", fontsize=11)
    fig.text(0.5, 0.012, "Declared illustration candidate; rho, V, CL, tributary width, ray length declared; "
             "EI unknown (assumed range).  Not a measurement.", ha="center", fontsize=7, color=GREY)
    # profile panel
    axp.set_xlim(0, L * 1e3); axp.set_ylim(-2, 0.4 * L * 1e3)
    axq.set_title("applied load (declared proxy)", fontsize=10)
    axp.set_xlabel("distance from clamped base x  [mm]", fontsize=9)
    axp.set_ylabel("deflection w  [mm] (simulated)", fontsize=9)
    axp.grid(alpha=0.3); axp.tick_params(labelsize=8)
    (lnw,) = axp.plot([], [], lw=2.5, color=BLUE)
    (lna,) = axp.plot([], [], lw=1, color="k", ls=":", label="closed form q x^2(6L^2-4Lx+x^2)/(24EI)")
    axp.axhline(0.1 * L * 1e3, color=RED, lw=1, ls="--")
    axp.text(L * 1e3 * 0.02, 0.1 * L * 1e3 + 0.8, "tip/L = 0.1 limit", color=RED, fontsize=7)
    axp.legend(fontsize=7, loc="upper left")
    
    # load panel
    axq.set_xlim(0, L * 1e3); axq.set_ylim(0, 1.15 * q_full)
    axq.set_xlabel("distance from clamped base x  [mm]", fontsize=9)
    axq.set_ylabel("line load q  [N/m] (declared proxy)", fontsize=9)
    axq.grid(alpha=0.3); axq.tick_params(labelsize=8)
    xq = np.linspace(0, L * 1e3, 2)
    fill = axq.fill_between(xq, 0, 0, color=BLUE, alpha=0.35)
    br = res["load_bridge"]
    axq.text(0.02, 0.97, f"p = 0.5 rho V^2 CL = {br['p_Pa']:.3g} Pa (mean proxy)\n"
             f"x tributary width {br['w_t_m']*1e3:.3g} mm  ->  q_line = {br['q_line_N_per_m']:.3g} N/m (full load)",
             transform=axq.transAxes, va="top", fontsize=7.5)
    qtxt = axq.text(0.98, 0.04, "", transform=axq.transAxes, ha="right", fontsize=9)
    _scalar_axes(axs, res)
    (mk,) = axs.plot([], [], "o", ms=9, mfc="white", mew=2.5)
    raw = []
    for f in frames:
        valid = f["valid"]
        col = BLUE if valid else RED
        lnw.set_data(f["x"] * 1e3, f["w"] * 1e3); lnw.set_color(col)
        lna.set_data(f["x"] * 1e3, f["analytic_w"] * 1e3)
        axp.set_title(f"tip/L = {f['tip_over_L']:.3g}  " + ("(inside declared linear limit)" if valid else
                      "INVALID: small-deformation limit exceeded (flagged)"), fontsize=10, color=col, weight="bold")
        fill.remove()
        fill = axq.fill_between(xq, 0, f["q"], color=col, alpha=0.35)
        qtxt.set_text(f"q = {f['q']:.3g} N/m  (V = {f['v_fraction']*100:.0f}% of declared)")
        ph = ("PHASE 1: load ramp at fixed EI = EI_crit/3 (illustrative choice)" if f["phase"] == 1 else
              "PHASE 2: EI sweep across the ASSUMED range at the full declared load")
        title.set_text(f"{ph}   |   EI = {f['EI']:.3g} N m^2")
        mk.set_data([f["EI"]], [max(f["tip_over_L"], 1e-4)]); mk.set_markeredgecolor(col)
        fig.canvas.draw()
        raw.append(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy())
    plt.close(fig)
    cmd = ["/usr/bin/ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{raw[0].shape[1]}x{raw[0].shape[0]}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-crf", "28", "-preset", "medium", "-threads", "1", "-movflags", "+faststart",
           str(out_mp4)]
    subprocess.run(cmd, input=b"".join(a.tobytes() for a in raw), check=True)
    return {"n_frames": len(frames), "fps": FPS, "duration_s": len(frames) / FPS,
            "frames_data_sha256": frames_sha256(frames), "size_px": [raw[0].shape[1], raw[0].shape[0]],
            "frames_from": "beam.solve_checked (Hermite FEM) per frame; closed form overlaid for comparison",
            "n_frames_invalid": int(sum(not f["valid"] for f in frames))}


def make_poster(res: dict, out_png: Path):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.text(0.5, 0.975, "Elastic fin-ray surrogate: how a declared flight load maps to ray deflection",
             ha="center", fontsize=20, weight="bold")
    fig.text(0.5, 0.945, BANNER, ha="center", fontsize=10.5, color=RED, weight="bold")
    axs = fig.add_axes([0.05, 0.14, 0.42, 0.74])
    _scalar_axes(axs, res)
    axs.set_title("Tip deflection / L across the ASSUMED EI range (simulated)", fontsize=12)
    # profiles at 4 EI
    axp = fig.add_axes([0.55, 0.50, 0.42, 0.38])
    L = res["load_bridge"]["L_ray_m"]; q = res["load_bridge"]["q_line_N_per_m"]
    xs = np.linspace(0, L, 101)
    crit = res["critical_stiffness"]["EI_crit_Nm2_float"]
    for k, c in zip([0.5, 1.0, 3.0, 30.0], ["#D55E00", "#CC79A7", "#009E73", "#0072B2"]):
        sol = beam.solve_cantilever(L, crit * k, q, res["request_echo"]["n_elements"])
        w, _ = sol.evaluate(xs)
        axp.plot(xs * 1e3, w * 1e3, color=c, lw=2, label=f"EI = {k:g} x EI_crit = {crit*k:.3g} N m^2")
    axp.axhline(0.1 * L * 1e3, color=RED, ls="--", lw=1)
    axp.set_xlabel("distance from clamped base x [mm]"); axp.set_ylabel("deflection w [mm] (simulated)")
    axp.set_title("Computed FEM profiles under the full declared load (uniform line load)", fontsize=12)
    axp.legend(fontsize=9); axp.grid(alpha=0.3)
    # text
    br = res["load_bridge"]
    steps = "\n".join(f"{s['name']:<16s} = {s['formula']:<28s} -> {s['float']:.6g} {s['unit']}" for s in br["steps"])
    mq = res["measurement_question"]
    body = ("LOAD-TO-FIN BRIDGE (declared, exact arithmetic)\n" + steps +
            f"\n\nEI_crit (uniform load, declared limits) = {crit:.4g} N m^2 [{res['critical_stiffness']['binding_limit']} binds]\n"
            f"assumed EI range: {eval_frac(res['EI_assumed_range']['min_Nm2']):g} .. {eval_frac(res['EI_assumed_range']['max_Nm2']):g} N m^2; "
            f"{res['sweep']['n_valid_uniform']}/{res['sweep']['n_points']} sweep points inside the linear limit\n\n"
            "MEASUREMENT QUESTION\n" + textwrap.fill(mq["question"], 105) + "\n" +
            textwrap.fill("Apparatus: " + mq["apparatus"], 105) + "\n" + textwrap.fill(mq["decision_rule"], 105))
    fig.text(0.55, 0.455, body, fontsize=8.6, family="monospace", va="top")
    fig.text(0.05, 0.062, textwrap.fill("NOT ESTABLISHED: " + "; ".join(res["not_established"][:5]) + ".", 230),
             fontsize=8.5, color=GREY, va="center")
    fig.text(0.05, 0.012, f"inputs sha256 {res['inputs_sha256'][:16]}...  code sha256 {res['code_sha256'][:16]}...  "
             "evidence_kind: simulated.  Gray hatched band = bluegill B=EI ~1e-6-1e-5 N m^2, Alben, Madden & Lauder 2007 Sec. 3.4 (order of magnitude, other species), not a calibration.",
             fontsize=8, color=GREY)
    fig.savefig(out_png, dpi=100)
    plt.close(fig)


def sha_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__); return 2
    req_path, out = Path(argv[0]), Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    req = json.loads(req_path.read_text())
    res = sweep.run(req)
    if res.get("verdict") != "ok":
        print(json.dumps(res)[:500]); return 1
    (out / "result.json").write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    vinfo = make_video(res, out / "fin_mechanics.mp4")
    make_poster(res, out / "poster.png")
    man = {
        "schema": "frontier.finmech.manifest/1", "evidence_kind": "simulated",
        "request_file": {"path": str(req_path.name), "sha256": sha_file(req_path), "canonical_sha256": res["inputs_sha256"]},
        "code_files_sha256": sweep.code_hashes(), "code_sha256": sweep.code_sha256(),
        "outputs": {n: {"sha256": sha_file(out / n), "bytes": (out / n).stat().st_size}
                    for n in ("result.json", "fin_mechanics.mp4", "poster.png")},
        "video": vinfo,
        "note": ("mp4 bytes can differ across ffmpeg builds; frames_data_sha256 hashes the computed numeric "
                 "frames and is the reproducible quantity"),
    }
    (out / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
