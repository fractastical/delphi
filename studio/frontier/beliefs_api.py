"""Bounded web adapter for frontier.beliefs: a finite scenario in, a labelled result out.

No supplied code, equations or commands: the request is only the scenario schema that
frontier.beliefs already validates. Each solve runs in a fresh child of the same interpreter
(`python -m frontier.beliefs_api --worker`), request on stdin, canonical JSON on stdout, with a
stripped environment, an 8 s timeout and at most two concurrent slots. Every response, including
errors, refusals and timeouts, carries `calibrated: false` and the declared-assumption scope text.
Wiring into frontier/web.py is not done here. Pattern: engineering_api.py (read, not copied).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from threading import BoundedSemaphore

from .beliefs import BeliefError, canonical, digest, solve

ROOT = Path(__file__).resolve().parents[1]
API_SCHEMA = "frontier.beliefs.api/1"
MAX_REQUEST_BYTES = 32 * 1024
TIMEOUT_S = 8
SLOTS = BoundedSemaphore(2)
SCENARIO_KEYS = {"schema", "label", "variables", "priors", "factors", "decision", "collapse"}
WORKER_ARGV = [sys.executable, "-m", "frontier.beliefs_api", "--worker"]
ASSUMED_SCOPE = ("Consequences of the declared assumptions in the submitted scenario only (priors, factors, "
                 "utilities, costs as written). Not calibrated against outcomes: calibration of this method "
                 "is unknown. Not a truth score and not a measurement.")


def _envelope(status: str, **extra) -> dict:
    return {"schema": API_SCHEMA, "status": status, "calibrated": False, "assumed_scope": ASSUMED_SCOPE, **extra}


def _error(message: str, code: str, http_status: int):
    from .store import FrontierError           # lazy: the worker child never imports the store
    err = FrontierError(message)
    err.code, err.http_status = code, http_status
    err.body = _envelope("error", error={"code": code, "message": message})
    return err


def error_body(exc: Exception) -> dict:
    """Response body for any adapter error; always labelled uncalibrated."""
    return getattr(exc, "body", None) or _envelope("error", error={"code": getattr(exc, "code", "error"),
                                                                    "message": "Request failed"})


def _reject_constant(name):
    raise ValueError("non-finite number " + name)


def parse_body(raw: bytes) -> dict:
    if len(raw) > MAX_REQUEST_BYTES:
        raise _error("Request exceeds 32 KB", "request_too_large", 413)
    try:
        return validate_request(json.loads(raw, parse_constant=_reject_constant))
    except ValueError as exc:
        if hasattr(exc, "body"):
            raise
        raise _error("Request is not finite JSON", "invalid_request", 400) from None


def validate_request(data) -> dict:
    if not isinstance(data, dict) or set(data) - SCENARIO_KEYS:
        raise _error("Unknown or malformed scenario fields", "invalid_request", 400)
    try:
        size = len(canonical(data).encode())
    except (ValueError, TypeError):
        raise _error("Request is not finite JSON", "invalid_request", 400) from None
    if size > MAX_REQUEST_BYTES:
        raise _error("Request exceeds 32 KB", "request_too_large", 413)
    return data


def _spawn(data: dict) -> subprocess.CompletedProcess:
    # Explicit environment: the child never sees the site's or operator's credentials.
    env = {"PATH": os.environ.get("PATH", ""), "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
           "MKL_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(WORKER_ARGV, input=canonical(data), capture_output=True, text=True,
                          cwd=ROOT, env=env, timeout=TIMEOUT_S)


def solve_scenario(data) -> dict:
    data = validate_request(data)
    if not SLOTS.acquire(blocking=False):
        raise _error("Two belief solves are already running; retry shortly", "solver_busy", 429)
    try:
        try:
            done = _spawn(data)
        except subprocess.TimeoutExpired:
            return _envelope("unknown", reason="Compute budget exhausted; no posterior or decision established",
                             input_hash=digest(data))
        if done.returncode == 3:
            try:
                msg = str(json.loads(done.stdout)["error"])[:300]
            except Exception:
                msg = "Scenario rejected"
            raise _error("Scenario rejected: " + msg, "invalid_request", 400)
        try:
            if done.returncode != 0:
                raise ValueError
            result = json.loads(done.stdout)
            status = result["status"]
        except Exception:
            raise _error("Belief solver is unavailable or failed", "solver_unavailable", 503) from None
        return _envelope(status, result=result)
    finally:
        SLOTS.release()


if __name__ == "__main__":
    if sys.argv[1:] != ["--worker"]:
        raise SystemExit("Use the bounded adapter, or --worker with a finite JSON scenario on stdin")
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if len(raw) > MAX_REQUEST_BYTES:
            raise ValueError
        req = json.loads(raw, parse_constant=_reject_constant)
        if not isinstance(req, dict) or set(req) - SCENARIO_KEYS:
            raise ValueError
        print(canonical(solve(req)))
    except BeliefError as exc:
        print(canonical({"error": str(exc)[:300]}))
        raise SystemExit(3) from None
    except Exception:
        # Fixed failure: no trace, environment or request is exported.
        raise SystemExit(2) from None
