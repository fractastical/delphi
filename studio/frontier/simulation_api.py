"""Anonymous, bounded CPU previews of two fixed trusted simulation models.

Request: {"model": "bioelectric"|"mechanobio", "parameters": <model request>}.
Mechanobio's existing request itself has a nested ``parameters`` object.
No persistence, rendering, supplied code, equations, commands or cloud calls.

Checklist: finite 8KiB input; allowlisted fields/models; two slots; isolated child;
8s wall deadline; stripped environment; inherited service cgroup bounds; explicit
unknown on timeout; full typed state frames plus exact request/source hashes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

from .worker_limits import Slots

ROOT = Path(__file__).resolve().parents[1]
API_SCHEMA = "frontier.simulation.preview/1"
MAX_REQUEST_BYTES = 8192
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
TIMEOUT_S = 8
SLOTS = Slots(2)                 # also draws on the process-wide worker budget in worker_limits
WORKER_ARGV = [sys.executable, "-m", "frontier.simulation_api", "--worker"]
MODEL_FIELDS = {
    "bioelectric": {"schema", "sodium_scale", "potassium_scale", "gap_mS_cm2", "stimulus_uA_cm2", "temperature_c", "duration_ms", "dt_ms"},
    "mechanobio": {"schema", "parameters", "duration_s", "dt_s", "seed", "frame_count"},
}
MECH_PARAMETER_FIELDS = {
    "long_term_stiffness_pN_nm", "additional_stiffness_pN_nm", "viscosity_pN_s_nm", "motors", "clutches",
    "on_rate_s", "off_rate_s", "rupture_force_pN", "motor_stall_pN", "unloaded_speed_nm_s", "clutch_stiffness_pN_nm",
}
PREVIEW_LIMITS = {
    "bioelectric": {"duration_ms": [10, 30], "dt_ms": [.0125, .025]},
    "mechanobio": {"duration_s": [1, 10], "dt_s": [.005, .02], "frame_count": [2, 101]},
}
SCOPE = ("An ephemeral numerical scenario, not an observation or biological validation. "
         "Published source equations with explicitly assumed network/contact parameters; "
         "no calibrated cell-to-tissue-to-fin bridge. Full sweeps and convergence challenges are separate offline actions.")


class _Invalid(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(value):
    return sha256(_canonical(value).encode()).hexdigest()


def _envelope(status, **extra):
    return {"schema": API_SCHEMA, "status": status, "persisted": False, "calibrated": False,
            "evidence_kind": "SimulationResult", "scope": SCOPE, **extra}


def _error(message, code="invalid_request", http_status=400):
    from .store import FrontierError  # Lazy: trusted numerical child does not import store/db packages.
    error = FrontierError(message)
    error.code, error.http_status = code, http_status
    error.body = _envelope("error", error={"code": code, "message": message})
    return error


def error_body(error):
    return getattr(error, "body", None) or _envelope("error", error={"code": "preview_failed", "message": "Preview request failed"})


def _reject_constant(_):
    raise _Invalid("Request must contain finite JSON values")


def _no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _Invalid("Duplicate JSON keys are not supported")
        result[key] = value
    return result


def _loads(raw):
    return json.loads(raw, parse_constant=_reject_constant, object_pairs_hook=_no_duplicates)


def _normalize(data):
    if not isinstance(data, dict) or set(data) - {"model", "parameters"}:
        raise _Invalid("Expected model and parameters fields only")
    try:
        if len(_canonical(data).encode()) > MAX_REQUEST_BYTES:
            raise _Invalid("Preview request exceeds 8192 bytes")
    except (TypeError, ValueError, RecursionError):
        raise _Invalid("Preview request must be finite JSON no larger than 8192 bytes") from None
    model = data.get("model")
    if not isinstance(model, str) or model not in MODEL_FIELDS:
        raise _Invalid("Model must be bioelectric or mechanobio")
    request = data.get("parameters", {})
    if not isinstance(request, dict) or set(request) - MODEL_FIELDS[model]:
        raise _Invalid("Unknown or malformed model request fields")
    request = dict(request)
    schema = f"frontier.{model}.request/1"
    if request.get("schema", schema) != schema:
        raise _Invalid("Unsupported model request schema")
    if model == "mechanobio":
        parameters = request.get("parameters", {})
        if not isinstance(parameters, dict) or set(parameters) - MECH_PARAMETER_FIELDS:
            raise _Invalid("Unknown or malformed mechanobio parameters")
        request = {"duration_s": 5.0, "dt_s": .01, "frame_count": 101, **request}
    else:
        request = {"duration_ms": 30.0, "dt_ms": .025, **request}
    for name, (lower, upper) in PREVIEW_LIMITS[model].items():
        value = request[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not lower <= value <= upper:
            raise _Invalid(f"Preview {name} must be finite in [{lower}, {upper}]")
        if name == "frame_count" and type(value) is not int:
            raise _Invalid("Preview frame_count must be an integer")
    return {"model": model, "parameters": request}


def validate_request(data):
    try:
        _normalize(data)
    except _Invalid as exc:
        raise _error(str(exc)) from None
    # Return a JSON snapshot so caller-side mutation cannot alter a running job.
    return _loads(_canonical(data))


def parse_body(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_REQUEST_BYTES:
        raise _error("Preview request exceeds 8192 bytes or has invalid body type")
    try:
        data = _loads(raw)
    except (ValueError, TypeError, UnicodeDecodeError, RecursionError):
        raise _error("Preview request is not valid finite JSON") from None
    return validate_request(data)


def _spawn(data):
    # No HOME, credential, proxy, PYTHONPATH, cloud or operator configuration is
    # inherited. Fixed cwd/module/argv; data travels exclusively on stdin.
    env = {"PATH": os.defpath, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
           "NUMEXPR_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.Popen(WORKER_ARGV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, cwd=ROOT, env=env, close_fds=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(_canonical(data), timeout=TIMEOUT_S)
    except BaseException:
        # A dedicated process group scopes cleanup to this request. Whole service
        # MemoryMax/MemorySwapMax/TasksMax remain inherited and are never relaxed.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.communicate()
        raise
    return subprocess.CompletedProcess(WORKER_ARGV, process.returncode, stdout, stderr)


def _calculate(data):
    effective = _normalize(data)
    model, request = effective["model"], effective["parameters"]
    started = time.perf_counter()
    if model == "bioelectric":
        from engineering.bioelectric import simulate
        result = simulate(request)
        if result["status"] == "invalid_request":
            raise _Invalid("Bioelectric parameters are outside the model envelope")
        if result["status"] != "completed":
            raise RuntimeError("Numerical model did not finish")
        source_files = result["simulationAction"]["code_sha256"]
    else:
        from engineering.mechanobio.model import run_request
        try:
            result = run_request(request)
        except (ValueError, TypeError):
            raise _Invalid("Mechanobio parameters are outside the model envelope") from None
        source_files = result["provenance"]["code_files"]
    # Capture only explicit runtime facts inside this actual numerical child.
    # Never export os.environ, credentials, parent-only metadata or packages the
    # selected model did not use. This identity is not a validation/calibration.
    import numpy
    scipy_version = None
    if model == "mechanobio":
        import scipy
        scipy_version = scipy.__version__
    environment = {"python": platform.python_version(), "python_implementation": platform.python_implementation(),
                   "numpy": numpy.__version__, "scipy": scipy_version, "platform": platform.platform(), "machine": platform.machine(),
                   "threads": {key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")},
                   "capture_scope": "actual isolated simulation worker after model imports; scipy null means not used by this model"}
    code = {"frontier/simulation_api.py": sha256(Path(__file__).read_bytes()).hexdigest(), "model_files": source_files}
    model_input = result["simulationAction"]["input_sha256"] if model == "bioelectric" else result["provenance"]["input_sha256"]
    source_context = result["source_envelope"] if model == "bioelectric" else {"model": result["model"], "source_receipt_sha256": result["provenance"].get("source_receipt_sha256")}
    identity = {"request_sha256": _digest(data), "effective_request_sha256": _digest(effective),
                "model_input_sha256": model_input, "code_sha256": _digest(code),
                "source_context_sha256": _digest(source_context), "environment_sha256": _digest(environment),
                "scope_sha256": _digest(SCOPE)}
    return _envelope("completed", model=model, result=result, request_sha256=_digest(data),
                     effective_request_sha256=_digest(effective), effective_request=effective,
                     code_sha256=code, environment=environment, environment_sha256=identity["environment_sha256"],
                     execution_identity=identity,
                     preview_limits=PREVIEW_LIMITS[model], elapsed_s=time.perf_counter() - started,
                     computed_at=datetime.now(timezone.utc).isoformat())


def run_preview(data):
    data = validate_request(data)
    if not SLOTS.acquire(blocking=False):
        raise _error("Two simulation previews are already running; retry shortly", "simulation_busy", 429)
    try:
        try:
            done = _spawn(data)
        except subprocess.TimeoutExpired:
            return _envelope("unknown", model=data["model"], request_sha256=_digest(data),
                             reason="compute_budget_exhausted", timeout_s=TIMEOUT_S,
                             message="Eight-second preview budget exhausted; no simulation outcome established")
        except OSError:
            raise _error("Simulation preview dependencies are unavailable", "simulation_unavailable", 503) from None
        if done.returncode == 3:
            raise _error("Model parameters are outside the supported preview envelope")
        try:
            if done.returncode != 0 or len(done.stdout.encode()) > MAX_RESPONSE_BYTES:
                raise ValueError
            result = _loads(done.stdout)
            if result.get("schema") != API_SCHEMA or result.get("status") != "completed" or result.get("model") != data["model"]:
                raise ValueError
        except (ValueError, TypeError, AttributeError, RecursionError):
            raise _error("Simulation preview is unavailable or failed its numerical check", "simulation_unavailable", 503) from None
        return result
    finally:
        SLOTS.release()


def _worker():
    # Service cgroup bounds the whole tree; these additional per-child limits
    # bound memory/CPU even when this adapter is called outside that service.
    from .worker_limits import cap_worker
    cap_worker()
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
    if len(raw) > MAX_REQUEST_BYTES:
        raise _Invalid("Request too large")
    print(_canonical(_calculate(_loads(raw))))


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use run_preview, or the fixed --worker protocol")
    try:
        _worker()
    except (_Invalid, json.JSONDecodeError):
        raise SystemExit(3) from None
    except Exception:
        # A fixed exit status prevents traces, runtime details and request leaks.
        raise SystemExit(2) from None
