"""Finite design queries for the website; no supplied code, equations or commands.

Each solve has a fresh Python/Z3 process, preventing concurrent Z3 context use.
The web service's systemd unit bounds the entire process tree. The child does not
spawn processes and is killed after eight seconds. This computes a response;
persisting an Evidence or Action remains a separate authenticated operation.
"""
from fractions import Fraction
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from .models import canonical, now
from .store import FrontierError
from .worker_limits import Slots

ROOT = Path(__file__).resolve().parents[1]
SLOTS = Slots(2)                 # also draws on the process-wide worker budget in worker_limits
NUMERIC = {"rho": ("kg/m^3", 10), "cl_max": ("1", 3), "mass": ("kg", 50),
           "area": ("m^2", 10), "span": ("m", 10), "speed": ("m/s", 100),
           "mass_min": ("kg", 50), "wing_loading_min": ("N/m^2", 1000), "speed_max": ("m/s", 100)}
FLAGS = {"relax_envelopes", "assume_pectoral_ar_applies_to_wing", "assume_taxi_speed_applies_to_flight"}
DECIMAL = re.compile(r"^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,12})?$")


def validate_request(data):
    if not isinstance(data, dict) or set(data) - (set(NUMERIC) | FLAGS):
        raise FrontierError("Unknown design-query fields")
    if len(canonical(data).encode()) > 1024:
        raise FrontierError("Design query exceeds 1024 bytes")
    for key, value in data.items():
        if key in FLAGS:
            if type(value) is not bool:
                raise FrontierError("Design options must be booleans")
        elif value is not None:
            if not isinstance(value, str) or not DECIMAL.fullmatch(value) or not 0 < Fraction(value) <= NUMERIC[key][1]:
                raise FrontierError(f"{key} needs a positive decimal string no greater than {NUMERIC[key][1]}")
    return dict(data)


def calculate(data):
    """Trusted finite request translated to the shared model, inside the worker."""
    from engineering.constraints import (Constraint, flying_fish_model, poly, q_mass_min,
                                         q_speed_max, q_wl_min, solve, verify_certificate)
    data = validate_request(data)
    model = flying_fish_model(rho=data.get("rho"), CL=data.get("cl_max"),
        assume_pectoral_ar_applies_to_wing=data.get("assume_pectoral_ar_applies_to_wing", False),
        assume_taxi_speed_applies_to_flight=data.get("assume_taxi_speed_applies_to_flight", False))
    queries = []
    for key, symbol in (("mass", "m"), ("area", "S"), ("span", "b"), ("speed", "V")):
        if data.get(key) is None:
            continue
        value = Fraction(data[key])
        terms = poly((1, {symbol: 1}), (-value, {}, model.quantities[symbol].dim))
        for suffix, op in (("lo", ">="), ("hi", "<=")):
            queries.append(Constraint(f"query_{symbol}_{suffix}", "user_query", terms, op,
                                      "Caller-specified design value; not a measured biological parameter"))
    for key, constructor in (("mass_min", q_mass_min), ("wing_loading_min", q_wl_min), ("speed_max", q_speed_max)):
        if data.get(key) is not None:
            queries.append(constructor(data[key]))
    relaxed = data.get("relax_envelopes", False)
    result = solve(model, queries, relax_envelopes=relaxed, timeout_ms=1500, minimise_core=False).to_json()
    checked_by = {"solver": result["solver"], "independent_witness": None, "lean": "not_run"}
    if result["status"] == "feasible":
        checked_by["independent_witness"] = verify_certificate(model, result, queries, relax_envelopes=relaxed)
        if checked_by["independent_witness"]["ok"] is not True:
            raise RuntimeError("Independent witness check failed")
    questions = []
    if not data.get("rho") or not data.get("cl_max"):
        questions.append({"approach": "measurement", "scales": ["organ", "organism"],
            "question": "Which measured air density and usable lift coefficient apply to this geometry, Reynolds number and flight regime?"})
    questions.append({"approach": "theory_fit", "scales": ["organ", "organism"],
        "question": "Does a sourced aerodynamic polar predict held-out glide trajectories for this fin geometry?"})
    questions.append({"approach": "design_goal", "scales": ["molecular", "developmental", "organ"],
        "question": "Which published genotype-to-fin proportion evidence applies to this candidate, and which developmental and mechanical couplings remain unmeasured?"})
    if result["status"] == "unsat":
        questions.append({"approach": "challenge", "scales": ["organism"],
            "question": "Which named conflicting requirement or empirical-envelope assumption should be revised, and what evidence would justify it?"})
    parameters = {key: {"value": data.get(key), "unit": unit,
                  "basis": "caller_design_assumption" if key in {"rho", "cl_max"} else "caller_design_requirement"}
                  for key, (unit, _) in NUMERIC.items()}
    hashes = {str(p.relative_to(ROOT)): sha256(p.read_bytes()).hexdigest()
              for p in (Path(__file__).resolve(), ROOT / "engineering/constraints.py")}
    return {"schema": "frontier.engineering.solve/1", "result": result, "parameters": parameters,
            "request_sha256": sha256(canonical(data).encode()).hexdigest(), "computed_at": now(),
            "code_sha256": hashes, "checked_by": checked_by, "followup_questions": questions,
            "questions_persisted": False, "evidence_kind": "simulated",
            "scope": "Exact declared-constraint calculation with a level-flight lift proxy; no biological, developmental, glide or manufacturing validation."}


def solve_design(data):
    data = validate_request(data)
    if not SLOTS.acquire(blocking=False):
        err = FrontierError("Two design queries are already running; retry shortly")
        err.code, err.http_status = "solver_busy", 429
        raise err
    try:
        # Explicit environment avoids handing the website or operator credentials to the solver.
        env = {"PATH": os.environ.get("PATH", ""), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        try:
            done = subprocess.run([sys.executable, "-m", "frontier.engineering_api", "--worker"],
                input=canonical(data), capture_output=True, text=True, cwd=ROOT, env=env, timeout=8)
        except subprocess.TimeoutExpired:
            return {"schema": "frontier.engineering.solve/1", "result": {"status": "unknown", "reason": "Eight-second compute budget exhausted"},
                    "request_sha256": sha256(canonical(data).encode()).hexdigest(), "computed_at": now(),
                    "checked_by": {"lean": "not_run", "independent_witness": None}, "questions_persisted": False,
                    "followup_questions": [], "scope": "No candidate or infeasibility conclusion established"}
        if done.returncode != 0:
            err = FrontierError("Engineering solver is unavailable or failed its check")
            err.code, err.http_status = "solver_unavailable", 503
            raise err
        return json.loads(done.stdout)
    finally:
        SLOTS.release()


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use the bounded website adapter, or --worker with a finite JSON request on stdin")
    from .worker_limits import cap_worker
    cap_worker()
    try:
        raw = sys.stdin.buffer.read(1025)
        if len(raw) > 1024:
            raise ValueError("request too large")
        print(canonical(calculate(json.loads(raw))))
    except Exception:
        # The caller sees a fixed error; no trace, environment or request is exported.
        raise SystemExit(2) from None
