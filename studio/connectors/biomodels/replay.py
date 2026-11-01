"""Replay a pinned SBML model with libroadrunner and check it against independent computations.

Evidence kind of everything produced here: *simulation of a published model under its own
parameters*. It is not an observation, and it says nothing about whether the source paper is
right (a reproduction matches its source; it does not validate it).

The controls are what separate a replay from a plot:

* tolerance convergence of the engine against its own finest setting;
* an independent integrator (scipy LSODA, plus a fixed-step RK4 with step halving) driven by
  right-hand sides evaluated from the parsed SBML, not from roadrunner;
* a derivative cross-check of that evaluator against roadrunner's own rates, and a mutated
  evaluator that the same check must reject (otherwise the check proves nothing);
* an unperturbed baseline and a no-feedback counterfactual run through the same engine.

Transcription caveat: the independent evaluator reads the same file, so it checks the engine and
the evaluation of the file's mathematics, not the file's fidelity to the paper.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
import sysconfig
import time
from datetime import datetime, timezone
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import scipy  # noqa: E402

from .client import sha256_bytes  # noqa: E402
from .sbml import Model, UnsupportedSBML, inspect_sbml  # noqa: E402

T_END = 60.0
POINTS = 601
RTOLS = (1e-6, 1e-8, 1e-10, 1e-12)
ENGINE_RTOL, ENGINE_ATOL = 1e-10, 1e-14
PACKAGE_DIR = Path(__file__).resolve().parent


class EngineUnavailable(RuntimeError):
    """libroadrunner could not be imported; reported as not run, never substituted."""


def load_engine():
    try:
        import roadrunner
        return roadrunner
    except ImportError as exc:
        if "libpython" not in str(exc):
            raise EngineUnavailable(str(exc)) from exc
        libdir = sysconfig.get_config_var("LIBDIR") or ""
        name = f"libpython{sys.version_info.major}.{sys.version_info.minor}.so.1.0"
        try:
            ctypes.CDLL(str(Path(libdir) / name), mode=ctypes.RTLD_GLOBAL)
            import roadrunner
        except (OSError, ImportError) as exc2:
            raise EngineUnavailable(f"{exc}; preload of {libdir}/{name} failed: {exc2}") from exc2
        return roadrunner


# ---- engine runs ---------------------------------------------------------------------------


def engine_run(rr_mod, sbml_text: str, overrides: dict[str, float], rtol: float, atol: float = ENGINE_ATOL):
    r = rr_mod.RoadRunner(sbml_text)
    integ = r.getIntegrator()
    integ.setValue("relative_tolerance", rtol)
    integ.setValue("absolute_tolerance", atol)
    integ.setValue("maximum_num_steps", 200_000)
    for key, val in overrides.items():
        r.setValue(f"init({key})" if key in r.model.getGlobalParameterIds() else f"init([{key}])", val)
    r.reset()
    ids = list(r.model.getFloatingSpeciesIds())
    r.timeCourseSelections = ["time"] + [f"[{i}]" for i in ids]
    out = np.asarray(r.simulate(0.0, T_END, POINTS))
    return ids, out, r


def reference_run(model: Model, overrides: dict[str, float], method: str):
    from scipy.integrate import solve_ivp

    env = model.initial_env(overrides)
    ids = list(model.species)
    consts = {k: v for k, v in env.items() if k not in ids}

    def f(_t, y):
        d = model.rhs(dict(zip(ids, y)), consts)
        return [d[i] for i in ids]

    y0 = [env[i] for i in ids]
    ts = np.linspace(0.0, T_END, POINTS)
    if method == "LSODA":
        sol = solve_ivp(f, (0, T_END), y0, method="LSODA", t_eval=ts, rtol=1e-11, atol=1e-14)
        if not sol.success:
            raise RuntimeError(sol.message)
        return ids, np.column_stack([ts, sol.y.T])
    n = int(method.removeprefix("RK4:"))
    h = T_END / n
    y, traj = np.array(y0), [(0.0, *y0)]
    for k in range(n):
        k1 = np.array(f(0, y)); k2 = np.array(f(0, y + h / 2 * k1)); k3 = np.array(f(0, y + h / 2 * k2)); k4 = np.array(f(0, y + h * k3))
        y = y + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        traj.append(((k + 1) * h, *y))
    return ids, np.array(traj)


def _at(grid: np.ndarray, t: np.ndarray) -> np.ndarray:
    return np.column_stack([np.interp(t, grid[:, 0], grid[:, j]) for j in range(1, grid.shape[1])])


# ---- controls ------------------------------------------------------------------------------


def derivative_check(rr_mod, sbml_text: str, model: Model, mutate: dict[str, float] | None = None) -> dict:
    """Max |roadrunner rate - evaluator rate| over deterministic states. `mutate` perturbs the evaluator."""
    r = rr_mod.RoadRunner(sbml_text)
    ids = list(r.model.getFloatingSpeciesIds())
    env = model.initial_env(mutate)
    consts = {k: v for k, v in env.items() if k not in ids}
    states = [[model.species[i]["initial_concentration"] for i in ids]]
    rng = np.random.default_rng(20261031)
    states += [list(rng.uniform(0.0, 1.5, len(ids))) for _ in range(6)]
    worst = 0.0
    for y in states:
        for i, v in zip(ids, y):
            r.setValue(f"[{i}]", v)
        got = np.asarray(r.model.getFloatingSpeciesConcentrationRates())
        want = model.rhs(dict(zip(ids, y)), consts)
        worst = max(worst, float(np.max(np.abs(got - np.array([want[i] for i in ids])))))
    return {"states_checked": len(states), "max_abs_diff": worst, "seed": 20261031}


def _asym(traj: np.ndarray, ids: list[str]) -> float:
    d1, d2 = ids.index("delta1") + 1, ids.index("delta2") + 1
    return float(np.max(np.abs(traj[:, d1] - traj[:, d2])))


def _final(traj, ids):
    return {i: float(traj[-1, j + 1]) for j, i in enumerate(ids)}


# The modules whose bytes decide a replay's result and its records. Explicit, so that adding an unrelated module
# (for example the video renderer) does not silently change the hash a committed receipt carries.
REPLAY_MODULES = ("__init__.py", "__main__.py", "client.py", "frontier_mapping.py", "replay.py", "sbml.py")


def _code_hash() -> str:
    h = hashlib.sha256()
    for name in REPLAY_MODULES:
        h.update(name.encode() + b"\0" + (PACKAGE_DIR / name).read_bytes())
    return h.hexdigest()


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", "-C", str(PACKAGE_DIR), *args], capture_output=True, text=True, timeout=20, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def replay_collier1996(sbml_bytes: bytes, expected_sha256: str, out_dir: Path, *, source: dict | None = None, argv: list[str] | None = None) -> dict:
    """Replay BIOMD0000001047 (Collier 1996 two-cell Delta-Notch) and write the receipt into `out_dir`.

    Specific to this model: the scenarios name its species (`delta1`, `notch2`, ...) and its
    parameter `b`. Raises `UnsupportedSBML` before any engine work if the file is outside the
    supported subset or lacks those names, and `ValueError` if the bytes are not the pinned file.
    """
    started = time.monotonic()
    digest = sha256_bytes(sbml_bytes)
    if digest != expected_sha256:
        raise ValueError(f"input sha256 {digest} != pinned {expected_sha256}")
    model = inspect_sbml(sbml_bytes)
    needed = {"delta1", "delta2", "notch1", "notch2"}
    if not needed <= set(model.species) or "b" not in model.parameters:
        raise UnsupportedSBML(f"replay_collier1996 needs species {sorted(needed)} and parameter b")
    rr_mod = load_engine()
    text = sbml_bytes.decode("utf-8")
    out_dir.mkdir(parents=True, exist_ok=True)

    sym = {"delta2": model.species["delta1"]["initial_concentration"], "notch2": model.species["notch1"]["initial_concentration"]}
    scenarios = {
        "as_published": ({}, "initial conditions exactly as stored in the file (cell 2 starts 1% below cell 1)"),
        "symmetric_baseline": (sym, "cell 2 initial conditions set equal to cell 1 (no perturbation); reference for symmetry breaking"),
        "no_notch_feedback_b0": ({"b": 0.0}, "counterfactual, not in the source: b=0 removes inhibition of Delta by Notch"),
    }
    runs, files = {}, {}
    for name, (ov, desc) in scenarios.items():
        ids, traj, _ = engine_run(rr_mod, text, ov, ENGINE_RTOL)
        csv = out_dir / f"trajectory_{name}.csv"
        np.savetxt(csv, traj, delimiter=",", header=",".join(["time"] + ids), comments="", fmt="%.12e")
        files[csv.name] = hashlib.sha256(csv.read_bytes()).hexdigest()
        runs[name] = {"description": desc, "overrides": ov, "final_state": _final(traj, ids), "max_abs_delta1_minus_delta2": _asym(traj, ids),
                      "min_concentration": float(traj[:, 1:].min()), "trajectory_file": csv.name}
        runs[name]["_traj"] = traj
    ids = list(model.species)
    pub = runs["as_published"]["_traj"]

    # convergence of the engine against its own finest tolerance
    finest = engine_run(rr_mod, text, {}, RTOLS[-1], 1e-16)[1]
    conv = [{"rtol": rt, "max_abs_diff_vs_finest": float(np.max(np.abs(engine_run(rr_mod, text, {}, rt, 1e-16)[1][:, 1:] - finest[:, 1:])))} for rt in RTOLS[:-1]]

    # independent integrators on evaluator RHS
    lsoda = reference_run(model, {}, "LSODA")[1]
    rk4 = []
    for n in (600, 1200, 2400):
        tr = reference_run(model, {}, f"RK4:{n}")[1]
        rk4.append({"steps": n, "h": T_END / n, "max_abs_diff_vs_lsoda": float(np.max(np.abs(_at(tr, lsoda[:, 0]) - lsoda[:, 1:])))})
    orders = [float(np.log2(rk4[i]["max_abs_diff_vs_lsoda"] / rk4[i + 1]["max_abs_diff_vs_lsoda"])) for i in range(2)]
    ref_diff = {}
    for name in scenarios:
        ov = scenarios[name][0]
        ref = reference_run(model, ov, "LSODA")[1]
        ref_diff[name] = float(np.max(np.abs(runs[name]["_traj"][:, 1:] - ref[:, 1:])))

    deriv = derivative_check(rr_mod, text, model)
    deriv_mut = derivative_check(rr_mod, text, model, mutate={"h": 3.0})

    # fixed points: patterned end state, and the symmetric state's linear stability
    from scipy.optimize import fsolve

    env = model.initial_env()
    consts = {k: v for k, v in env.items() if k not in ids}
    f = lambda y: [model.rhs(dict(zip(ids, y)), consts)[i] for i in ids]  # noqa: E731
    final = pub[-1, 1:]
    residual = float(np.max(np.abs(f(final))))
    x0 = fsolve(lambda z: f([z[0], z[0], z[1], z[1]])[::2], [1.0, 1.0], xtol=1e-14)
    sym_fp = [x0[0], x0[0], x0[1], x0[1]]
    J = np.zeros((4, 4))
    for j in range(4):
        e = 1e-7 * np.eye(4)[j]
        J[:, j] = (np.array(f(np.array(sym_fp) + e)) - np.array(f(np.array(sym_fp) - e))) / 2e-7
    eig = np.sort(np.linalg.eigvals(J).real)

    base_asym = runs["symmetric_baseline"]["max_abs_delta1_minus_delta2"]
    checks = {k: bool(v) for k, v in {
        "engine_converges_with_tolerance": conv[-1]["max_abs_diff_vs_finest"] < 1e-6,
        "engine_matches_independent_lsoda": max(ref_diff.values()) < 1e-6,
        "rk4_order_near_4": all(3.0 < o < 5.0 for o in orders),
        "evaluator_matches_engine_rates": deriv["max_abs_diff"] < 1e-12,
        "mutated_evaluator_is_rejected": deriv_mut["max_abs_diff"] > 1e-3,
        "patterned_state_is_fixed_point": residual < 1e-8,
        "symmetric_fixed_point_unstable": bool(eig[-1] > 1e-3),
        "baseline_stays_symmetric": base_asym < 1e-9,
        "published_run_breaks_symmetry": runs["as_published"]["max_abs_delta1_minus_delta2"] > 0.5 and abs(pub[-1, 1] - pub[-1, 2]) > 0.5,
        "concentrations_non_negative": all(r["min_concentration"] > -1e-12 for r in runs.values()),
    }.items()}
    for r in runs.values():
        r.pop("_traj")

    (out_dir / "model_inventory.json").write_text(json.dumps(model.inventory(), indent=1, sort_keys=True))
    files["model_inventory.json"] = hashlib.sha256((out_dir / "model_inventory.json").read_bytes()).hexdigest()
    receipt = {
        "evidence_kind": "simulation of a published model under its own parameters (not an observation; not a validation of the paper)",
        "model": {"sha256": digest, "bytes": len(sbml_bytes), "sbml": f"L{model.level}V{model.version}", "id": model.id},
        "source": source,
        "supported_subset_check": "passed",
        "engine": {"name": "libroadrunner", "version": rr_mod.__version__, "integrator": "cvode", "rtol": ENGINE_RTOL, "atol": ENGINE_ATOL},
        "numpy": np.__version__, "scipy": scipy.__version__, "python": platform.python_version(),
        "time_horizon": {"t_end": T_END, "points": POINTS, "note": "chosen for this replay; the SBML file declares no simulation settings and no time unit"},
        "scenarios": runs,
        "controls": {
            "tolerance_convergence": conv,
            "rk4_step_halving": rk4, "rk4_observed_orders": orders,
            "engine_vs_lsoda_max_abs_diff": ref_diff,
            "derivative_check": deriv, "derivative_check_mutated_h3": deriv_mut,
            "patterned_state_max_abs_rate": residual,
            "symmetric_fixed_point": sym_fp, "symmetric_jacobian_real_eigenvalues": [float(x) for x in eig],
            "baseline_max_asymmetry": base_asym,
        },
        "checks": checks, "all_checks_passed": all(checks.values()),
        "limits": [
            "The independent evaluator reads the same SBML file: it checks the engine and the evaluation, not fidelity to the paper.",
            "The paper's full text was not read; parameter provenance (measured/fitted/assumed) is unknown from the file.",
            "Units: none are referenced by any quantity; the model is non-dimensional as stored.",
            "The b=0 run is an added counterfactual, not a result from the source.",
            "receipt.json cannot hash itself, so it is absent from output_sha256; run.git_head names the code commit, and the receipt is committed after it.",
            "Versions recorded here (engine, numpy, scipy, python) are those of the producing environment; the SBML bytes were fetched from BioModels and are not stored in this repository.",
        ],
        "run": {
            "command": " ".join("<abs-path-withheld>" if a.startswith("/") else a for a in (argv or sys.argv)), "code_sha256": _code_hash(), "git_head": _git("rev-parse", "HEAD"),
            "git_dirty": bool(_git("status", "--porcelain", "--", ".", ":(exclude)receipts")),
            "hardware": {"machine": platform.machine(), "cpu_count": os.cpu_count(), "threads_requested": 1, "gpu": None},
            "elapsed_s": round(time.monotonic() - started, 3), "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
        "output_sha256": files,
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1, sort_keys=True))
    return receipt
