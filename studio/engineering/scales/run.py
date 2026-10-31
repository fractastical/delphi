"""Run the scale layer: standard simulation, controls, saved states, video, receipt.  SIMULATED.

    python -m engineering.scales.run [--out artifacts/scales] [--hours 120] [--no-controls]

Writes artifacts/scales/erk-wave/{states.npz, erk_growth.mp4, erk_growth.gif, poster.png, receipt.json}.  The receipt maps sources + parameters + code sha256 -> every output's sha256, and records each
control against the band declared in BANDS (written before the controls were first run, from the paper's own
numbers; a band is a tolerance on "order of"/"about" wording, not a fit).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np

from engineering.scales import erk_wave as M

ROOT = Path(__file__).resolve().parents[2]

# Measured values the standard run is compared against (De Simone 2021 text, Hayden 2021 text), and the band
# accepted for each.  "order of 10 um/h" -> 5..20; "about 2 days" -> 24..72 h; "50-100 um wide" -> 50..100;
# "activated in ~3 h" -> 1.5..6 h; "deactivated in ~5 h" -> 2.5..10 h; "~1 wave per day" at onset -> 12..48 h.
BANDS = {
    "wave_speed_um_per_h": (5.0, 20.0, "De Simone 2021: 'Erk waves travel at a speed in the order of 10 um/h'"),
    "first_crossing_h": (24.0, 72.0, "De Simone 2021: 'one wave traverses the entire scale in about 2 days'"),
    "front_fwhm_um": (50.0, 100.0, "De Simone 2021: 'a traveling front 50-100 um wide'"),
    "rise_10_90_h": (1.5, 6.0, "De Simone 2021: 'activation time of ~3 hours' (single-cell tracks)"),
    "fall_peak_10_h": (2.5, 10.0, "De Simone 2021: 'inactivation time of ~5 hours'"),
    "source_period_h": (12.0, 48.0, "Hayden 2021: wave generation starts at ~1 wave per day"),
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def code_hash() -> str:
    h = hashlib.sha256()
    for f in ("erk_wave.py", "run.py", "render.py"):
        h.update((Path(__file__).parent / f).read_bytes())
    return h.hexdigest()


def inband(x, key):
    lo, hi, _ = BANDS[key]
    return x is not None and lo <= x <= hi


def standard_checks(s: dict) -> dict:
    sp = s["source_peak_times_h"]
    period = float(np.median(np.diff(sp))) if len(sp) > 1 else None
    first_cross = (s["rim_arrival_times_h"][0] - sp[0]) if s["rim_arrival_times_h"] and sp else None
    ps = s["pulse_shape"] or {}
    got = {"wave_speed_um_per_h": s["wave_speed"]["speed_um_per_h"], "first_crossing_h": first_cross,
           "front_fwhm_um": s["front_fwhm_um_median"], "rise_10_90_h": ps.get("rise_10_90_h"),
           "fall_peak_10_h": ps.get("fall_peak_10_h"), "source_period_h": period}
    return {k: {"simulated": v, "band": list(BANDS[k][:2]), "measured_source": BANDS[k][2], "in_band": inband(v, k)}
            for k, v in got.items()}


def controls(hours: float, std: dict, std_summary: dict) -> dict:
    out = {}
    ns = M.summary(M.simulate(M.Run(hours=hours, mode="no_source")))
    out["no_source"] = {"expect": "no Erk anywhere, no growth",
                        "max_E": ns["max_E_outside_source"], "area_ratio": ns["area_ratio"],
                        "pass": ns["max_E_outside_source"] < 1e-9 and abs(ns["area_ratio"] - 1) < 1e-12}
    pf = M.summary(M.simulate(M.Run(hours=hours, mode="pf_sign_mutant")))
    out["pf_sign_mutant"] = {"expect": "alpha3 -> -alpha3 (Erk suppresses its activator): no propagating wave",
                             "max_E_outside_source": pf["max_E_outside_source"],
                             "cells_reached_fraction": pf["cells_reached_fraction"],
                             "rim_arrivals": pf["rim_arrival_times_h"],
                             "pass": pf["cells_reached_fraction"] < 0.05 and not pf["rim_arrival_times_h"]}
    dq = M.summary(M.simulate(M.Run(hours=hours, params=replace(M.Params(), D=M.Params().D / 4))))
    v0 = std_summary["wave_speed"]["speed_um_per_h"]; v1 = dq["wave_speed"]["speed_um_per_h"]
    ratio = (v1 / v0) if (v0 and v1) else None
    out["D_quarter"] = {"expect": "trigger-wave scaling v ~ (D/tau)^(1/2) (Hayden 2021): D/4 -> speed x0.5; band 0.4-0.6",
                        "speed_um_per_h": v1, "speed_ratio": ratio,
                        "pass": ratio is not None and 0.4 <= ratio <= 0.6}
    sy = M.summary(M.simulate(M.Run(hours=hours, mode="synchronous")))
    out["synchronous"] = {
        "expect": ("De Simone 2021 MEASURED that daily tissue-wide synchronous Erk activation (fgf20a, fgf3) "
                   "impairs scale growth. Here: activator set to 1 over the whole disc every 24 h, source off."),
        "area_ratio": sy["area_ratio"], "standard_area_ratio": std_summary["area_ratio"],
        "peaks_per_cell_max": sy["peaks_per_cell_max"],
        "reproduces_measured_impairment": sy["area_ratio"] < std_summary["area_ratio"],
        "pass": None,
        "note": ("Reported, not gated. The growth law grows each cell for a fixed window after each of its own "
                 "Erk peaks, so it cannot tell a wave from a synchronous pulse at equal pulse count; the measured "
                 "impairment is outside what this layer models."),
    }
    fine = M.summary(M.simulate(M.Run(hours=hours, geometry=replace(M.Geometry(), dt_h=0.005))))
    vf = fine["wave_speed"]["speed_um_per_h"]
    pf_ = float(np.median(np.diff(fine["source_peak_times_h"]))); p0 = float(np.median(np.diff(std_summary["source_peak_times_h"])))
    out["step_halved"] = {"expect": "dt 0.01 -> 0.005 h changes speed and source period by < 5%",
                          "speed_rel": abs(vf - v0) / v0, "period_rel": abs(pf_ - p0) / p0,
                          "pass": abs(vf - v0) / v0 < 0.05 and abs(pf_ - p0) / p0 < 0.05}
    return out


def save_states(res: dict, path: Path) -> None:
    buf = io.BytesIO()
    np.savez_compressed(buf, t_h=res["t_h"].astype(np.float32), E=res["E"].astype(np.float16),
                        loga=res["loga"].astype(np.float16), area_um2=res["area_um2"].astype(np.float64),
                        scale=res["scale"], source=res["source"], probe_um=np.array(res["probe_um"]),
                        probe_E=res["probe_E"][::10].astype(np.float16))
    path.write_bytes(buf.getvalue())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "scales"))
    ap.add_argument("--hours", type=float, default=120.0)
    ap.add_argument("--no-controls", action="store_true")
    a = ap.parse_args(argv)
    from engineering.scales import render as R
    out = Path(a.out) / "erk-wave"; out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    run = M.Run(hours=a.hours)
    res = M.simulate(run)
    s = M.summary(res)
    checks = standard_checks(s)
    ctl = controls(a.hours, res, s) if not a.no_controls else {}
    save_states(res, out / "states.npz")
    media = R.render(res, s, out)
    files = {p.name: {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
             for p in sorted(out.iterdir()) if p.name != "receipt.json"}
    src = json.loads((Path(__file__).parent / "sources.json").read_text())
    receipt = {
        "schema": "frontier.scales.receipt/1",
        "evidence_kind": "SimulationResult (not an observation; not a microscope image)",
        "model": "Hayden 2021 Erk trigger-wave reaction-diffusion + wave-gated hypertrophic growth (one scale)",
        "sources": src["sources"], "parameters": src["parameters"],
        "run": M.run_dict(run), "code_sha256": code_hash(), "summary": s,
        "measured_comparison": checks, "controls": ctl, "media": media, "files": files,
        # Two different things, kept apart: controls test the implementation (exit code); the measured
        # comparison tests the model against the papers' measurements, and a miss there is a finding to report.
        "controls_pass": all(c["pass"] for c in ctl.values() if c["pass"] is not None) and media["checks"]["frames_match"]
        and media["checks"]["within_size_limits"],
        "measured_comparison_all_in_band": all(c["in_band"] for c in checks.values()),
        "measured_comparison_misses": [k for k, c in checks.items() if not c["in_band"]],
        "not_claimed": src["not_claimed"],
        "wall_s": round(time.time() - t0, 1),
    }
    (out / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True, default=float) + "\n")
    print(json.dumps({"checks": {k: v["in_band"] for k, v in checks.items()},
                      "controls": {k: v["pass"] for k, v in ctl.items()},
                      "controls_pass": receipt["controls_pass"],
                      "measured_comparison_misses": receipt["measured_comparison_misses"]}, indent=1))
    return 0 if receipt["controls_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
