"""Produce artifacts/coupled-mechanics: result.json, poster.png, manifest.json.

    python -m engineering.coupled_mechanics.run artifacts/coupled-mechanics

Run inside a bounded scope with one thread. Everything recorded is computed in this run from the
committed inputs whose hashes the manifest pins.
"""
from __future__ import annotations

import hashlib
import json
import platform
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np
import scipy

from engineering.fin_mechanics.load_bridge import Refusal

from . import MODEL_VERSION, SCHEMA_RESULT, cases, couple
from . import windtunnel_receipt as wt

PKG = Path(__file__).resolve().parent


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _refusal(fn):
    try:
        fn()
    except Refusal as e:
        return {"verdict": "refused", "code": e.code, "detail": e.detail}
    return {"verdict": "accepted"}


def _slim(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k != "deflection"}
    out["deflection"] = {k: {kk: vv for kk, vv in v.items() if kk not in ("x_m", "w_m")}
                         for k, v in r["deflection"].items()}
    return out


def build() -> tuple[dict, dict]:
    tgt = cases.target()
    profiles = {}
    curves = {}
    for prof in ("uniform", "root_heavy", "tip_heavy"):
        r = couple.run(cases.analytic_record(prof), tgt)
        profiles[prof] = _slim(r)
        curves[prof] = r
    disabled = couple.run(couple.disabled_load(cases.analytic_record("uniform")), tgt)
    bridge = cases.illustration_bridge()
    base = profiles["uniform"]
    comparison = {
        "baseline": "fin_mechanics load_bridge mean lift-pressure proxy (uniform q), the existing one-way chain",
        "baseline_q_line_N_per_m": bridge["exact"]["q_line_N_per_m"],
        "adapter_uniform_q_N_per_m": base["stations"]["q_N_per_m"][0],
        "adapter_equals_baseline_exactly": base["stations"]["q_N_per_m"][0] == bridge["exact"]["q_line_N_per_m"],
        "tip_ratio_vs_uniform_at_EI_hi": {
            p: profiles[p]["deflection"]["EI_hi"]["tip_m"] / base["deflection"]["EI_hi"]["tip_m"]
            for p in profiles},
        "disabled_load_tip_m": {k: v["tip_m"] for k, v in disabled["deflection"].items()},
        "meaning": "same total force, different analytic distribution: load shape alone changes the tip; "
                   "no flow model produced these pressures",
    }

    r = wt.load()
    rec, tail_tgt = wt.tail_record_and_target(r)
    tail_whole = dict(tail_tgt, claim="whole_fin_3d")
    pect = cases.target(claim="whole_fin_3d")
    actual = {
        "receipt": {"result_sha256": r["sha256"]["result"], "fields_sha256": r["sha256"]["fields"],
                    "geometry_sha256": r["result"]["geometry"]["sha256"], "status": r["result"]["status"],
                    "Re": r["result"]["Re"], "request": r["request"],
                    "pins_checked": "fields.npz vs receipt fields_sha256; result.json and fields.npz vs "
                                    "artifacts/windtunnel/simulation-manifest.json outputs"},
        "pressure_mapping": {"Pa_per_unit_lattice_density_excess": r["pa_per_lattice_density"],
                             "formula": r["result"]["units"]["pressure"],
                             "time_mean_frames": int(r["window"].sum()),
                             "time_mean_window_s": [float(r["t_s"][r["window"]][0]),
                                                    float(r["t_s"][r["window"]][-1])]},
        "surface_pressure_force_diagnostic": {k: float(v) if isinstance(v, (float, np.floating)) else v
                                              for k, v in wt.surface_pressure_force(r).items()},
        "tail_strip": wt.tail_strip(r),
        "tail_strip_record_stations": rec["stations"],
        "attempts": {
            "tail_strip_as_2d_section_member": _refusal(lambda: couple.run(rec, tail_tgt)),
            "tail_strip_as_whole_fin_3d": _refusal(lambda: couple.run(rec, tail_whole)),
            "declared_pectoral_ray_from_this_field": _refusal(lambda: couple.run(rec, pect)),
        },
        "verdict": "ACTUAL COUPLING BLOCKED: the only completed flow field is a 2D sagittal extrusion whose "
                   "one in-plane strip is 1 cell thick, and it contains no pectoral fin; the 3D member-pressure "
                   "record from cfd3d does not exist yet",
    }

    result = {
        "schema": SCHEMA_RESULT + "#run", "model_version": MODEL_VERSION, "evidence_kind": "analytic+simulated",
        "analytic_cases": profiles, "disabled_load_control": _slim(disabled),
        "grid_study_tip_heavy": couple.grid_study(cases.analytic_record("tip_heavy"), tgt),
        "one_way_comparison": comparison,
        "actual_flow_receipt": actual,
        "blocked": [
            {"what": "3D pressure on a resolved fin ray", "owner": "cfd3d (claude-04)",
             "needs": "frontier.coupled.member-pressure/1 with dimensionality 3d and >= 2 cells across the ray",
             "contract": "engineering/coupled_mechanics/contract.py; messages/coupled-mechanics-to-cfd3d.md"},
            {"what": "measured EI(x) of a flying-fish ray", "owner": "none (wet lab)",
             "needs": "fin_mechanics MEASUREMENT_QUESTION; the interval used is bluegill context only"},
            {"what": "ray section c and I for stress", "owner": "none",
             "needs": "micro-CT section of the target ray; stress is refused without it"},
        ],
        "not_established": ["any calibrated organism claim", "fluid-structure feedback",
                            "that unit or conservation checks say anything about biological transfer"],
    }
    return result, curves


def render(result, curves, out: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    r = wt.load()
    fig, ax = plt.subplots(1, 3, figsize=(16, 5.2), dpi=110)
    x, y = r["x_over_L"], r["y_over_L"]
    p = np.ma.masked_where(r["solid"], r["p_mean_Pa"])
    lim = float(np.abs(p).max())
    im = ax[0].pcolormesh(x, y, p.T, cmap="RdBu_r", vmin=-lim, vmax=lim, shading="nearest")
    ax[0].contour(x, y, r["solid"].T.astype(float), levels=[0.5], colors="k", linewidths=0.8)
    for i in wt.TAIL_COLUMNS:
        ax[0].plot(x[i], y[wt.TAIL_ROW], "s", ms=5, mfc="none", mec="#d4a000")
    ax[0].set_xlim(x[30], x[66])
    ax[0].set_ylim(y[26], y[46])
    ax[0].set_aspect("equal")
    fig.colorbar(im, ax=ax[0], label="time-mean gauge pressure [Pa]")
    code = result["actual_flow_receipt"]["attempts"]["tail_strip_as_2d_section_member"]["code"]
    ax[0].set_title(f"ACTUAL 2D receipt (Re 80, fields {r['sha256']['fields'][:12]})\n"
                    f"tail strip (gold) -> REFUSED {code}: 1 cell thick", fontsize=9)
    ax[0].set_xlabel("x / L")
    ax[0].set_ylabel("z / L")

    colors = {"uniform": "#333333", "root_heavy": "#1f77b4", "tip_heavy": "#d62728"}
    for prof, rr in curves.items():
        s = [float(Fraction(t)) for t in rr["stations"]["s_m"]]
        q = [float(Fraction(t)) for t in rr["stations"]["q_N_per_m"]]
        ax[1].plot(s, q, "-o", ms=3, color=colors[prof], label=prof)
        lo, hi = rr["deflection"]["EI_lo"], rr["deflection"]["EI_hi"]
        Lr = float(Fraction(rr["L_m"]))

        def tag(e):
            return "valid" if e["validity"]["valid"] else "INVALID linear"
        xr = np.array(hi["x_m"]) / Lr
        ax[2].fill_between(xr, np.array(hi["w_m"]) / Lr, np.array(lo["w_m"]) / Lr, color=colors[prof], alpha=0.18)
        ax[2].plot(xr, np.array(hi["w_m"]) / Lr, color=colors[prof], label=f"{prof}, EI 1e-5: {tag(hi)}")
        ax[2].plot(xr, np.array(lo["w_m"]) / Lr, color=colors[prof], ls="--", label=f"{prof}, EI 1e-6: {tag(lo)}")
    ax[2].axhline(0.1, color="k", lw=0.8, ls=":")
    ax[2].text(0.02, 0.12, "declared linear limit tip/L = 0.1", fontsize=7)
    ax[2].set_yscale("log")
    ax[2].set_ylim(1e-3, 2e2)
    ax[1].set_title("ANALYTIC pressure only: line load q = dp x w_t [N/m]\nsame total force, three shapes",
                    fontsize=9)
    ax[1].set_xlabel("s along declared ray [m]")
    ax[1].set_ylabel("q [N/m]")
    ax[1].legend(fontsize=8)
    ax[2].set_title("EB cantilever w/L at both EI ends (bluegill context, not calibrated)\n"
                    "every case exceeds the linear limit: the declared load is too large for this EI", fontsize=9)
    ax[2].set_xlabel("s / L")
    ax[2].set_ylabel("w / L (log)")
    ax[2].legend(fontsize=6.5, loc="lower right")
    fig.suptitle("Pressure -> fin-ray traction -> line load -> deflection.  Actual 3D coupling BLOCKED "
                 "(awaiting cfd3d member-pressure record)", fontsize=11)
    fig.tight_layout()
    fig.savefig(out / "poster.png")
    plt.close(fig)


def main(argv):
    out = Path(argv[1] if len(argv) > 1 else "artifacts/coupled-mechanics")
    out.mkdir(parents=True, exist_ok=True)
    result, curves = build()
    code = {f"engineering/coupled_mechanics/{p.name}": _sha(p) for p in sorted(PKG.glob("*.py"))}
    fin = PKG.parent / "fin_mechanics"
    code.update({f"engineering/fin_mechanics/{n}": _sha(fin / n) for n in ("beam.py", "load_bridge.py", "sweep.py")})
    result["provenance"] = {
        "code_files": code,
        "inputs": {"engineering/fin_mechanics/example_request.json": _sha(cases.FIN_REQUEST),
                   "artifacts/windtunnel/baseline/result.json": _sha(wt.RECEIPT_DIR / "result.json"),
                   "artifacts/windtunnel/baseline/fields.npz": _sha(wt.RECEIPT_DIR / "fields.npz"),
                   "artifacts/windtunnel/simulation-manifest.json": _sha(wt.MANIFEST)},
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "scipy": scipy.__version__},
    }
    (out / "result.json").write_text(json.dumps(result, indent=1, sort_keys=True, default=str) + "\n")
    render(result, curves, out)
    manifest = {"schema": "frontier.coupled.manifest/1",
                "outputs": {n: {"sha256": _sha(out / n), "byte_size": (out / n).stat().st_size}
                            for n in ("result.json", "poster.png")},
                "code_files": code, "inputs": result["provenance"]["inputs"],
                "note": "simulation (result.json) and rendering (poster.png) are pinned separately"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"verdict": result["actual_flow_receipt"]["verdict"],
                      "outputs": manifest["outputs"]}, indent=1))


if __name__ == "__main__":
    main(sys.argv)
