"""Tests for frontier.beliefs_api. Stubs are labelled; the real worker runs in one test."""
import copy
import json
import os
import subprocess
import sys
import threading
from fractions import Fraction as F

import pytest

from frontier import beliefs as B
from frontier import beliefs_api as A
from frontier.store import FrontierError


def codes(exc):
    return exc.value.code, exc.value.http_status


def test_real_worker_roundtrips_exact_rationals_and_labels_every_response():
    r = A.solve_scenario(copy.deepcopy(B.EXAMPLE_SCENARIO))      # real fixed subprocess
    assert r["status"] == "ok" and r["calibrated"] is False and r["assumed_scope"] == A.ASSUMED_SCOPE
    assert r["result"] == json.loads(json.dumps(B.solve(B.EXAMPLE_SCENARIO)))      # identical to in-process
    assert F(r["result"]["variables"]["H"]["posterior"]["yes"]) == F(3, 5)
    assert F(r["result"]["decision"]["actions"]["advance"]["expected_value"]) == F(17, 5)
    assert "unknown" in A.ASSUMED_SCOPE and "truth score" in A.ASSUMED_SCOPE      # states non-calibration


def test_refusal_is_wrapped_with_calibrated_false_and_no_decision():
    sc = copy.deepcopy(B.EXAMPLE_SCENARIO)
    sc["priors"] = []
    r = A.solve_scenario(sc)
    assert r["status"] == "unresolved-no-prior" and r["calibrated"] is False
    assert "decision" not in r["result"] and r["assumed_scope"]


def test_oversize_request_rejected_before_any_subprocess(monkeypatch):
    monkeypatch.setattr(A, "_spawn", lambda d: pytest.fail("worker must not run"))
    sc = copy.deepcopy(B.EXAMPLE_SCENARIO)
    sc["label"] = "x" * (A.MAX_REQUEST_BYTES + 1)
    with pytest.raises(FrontierError) as e:
        A.solve_scenario(sc)
    assert codes(e) == ("request_too_large", 413) and e.value.body["calibrated"] is False
    with pytest.raises(FrontierError) as e:
        A.parse_body(b" " * (A.MAX_REQUEST_BYTES + 1))
    assert codes(e) == ("request_too_large", 413)


@pytest.mark.parametrize("bad", [b"NaN", b'{"label": Infinity}', b"[]", b"not json"])
def test_non_finite_or_malformed_json_rejected(bad):
    with pytest.raises(FrontierError) as e:
        A.parse_body(bad)
    assert e.value.http_status in (400,) and A.error_body(e.value)["calibrated"] is False


def test_unknown_field_rejected_including_code_like_fields(monkeypatch):
    monkeypatch.setattr(A, "_spawn", lambda d: pytest.fail("worker must not run"))
    for extra in ("code", "equation", "command", "do"):
        sc = copy.deepcopy(B.EXAMPLE_SCENARIO)
        sc[extra] = "anything"
        with pytest.raises(FrontierError) as e:
            A.solve_scenario(sc)
        assert codes(e) == ("invalid_request", 400)


def test_nested_unknown_field_rejected_by_the_worker_validation():
    sc = copy.deepcopy(B.EXAMPLE_SCENARIO)
    sc["decision"]["actions"]["advance"]["do"] = {"H": "yes"}
    with pytest.raises(FrontierError) as e:
        A.solve_scenario(sc)
    assert codes(e) == ("invalid_request", 400) and e.value.body["calibrated"] is False


def test_timeout_returns_unknown_never_a_posterior(monkeypatch):
    # STUB: a worker that sleeps far longer than a monkeypatched tiny timeout.
    monkeypatch.setattr(A, "WORKER_ARGV", [sys.executable, "-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(A, "TIMEOUT_S", 0.3)
    r = A.solve_scenario(copy.deepcopy(B.EXAMPLE_SCENARIO))
    assert r["status"] == "unknown" and r["calibrated"] is False and r["assumed_scope"]
    assert not {"result", "variables", "decision", "structure"} & set(r)


def test_worker_failure_is_a_fixed_error_without_leaks(monkeypatch):
    # STUB: a worker that fails and prints a trace plus the request-ish text to stderr/stdout.
    monkeypatch.setattr(A, "WORKER_ARGV", [sys.executable, "-c",
                        "import sys; print('TRACE secret-looking-sentinel'); sys.stderr.write('TRACE'); sys.exit(1)"])
    with pytest.raises(FrontierError) as e:
        A.solve_scenario(copy.deepcopy(B.EXAMPLE_SCENARIO))
    assert codes(e) == ("solver_unavailable", 503)
    assert "sentinel" not in json.dumps(A.error_body(e.value)) and "TRACE" not in str(e.value)


def test_third_concurrent_call_gets_solver_busy(monkeypatch):
    # STUB: _spawn blocks until released, holding both slots.
    started, release = threading.Semaphore(0), threading.Event()
    calls = []

    def slow(data):
        calls.append(1)
        started.release()
        release.wait(10)
        return subprocess.CompletedProcess([], 0, canonical_ok(), "")
    monkeypatch.setattr(A, "_spawn", slow)
    out = []
    ts = [threading.Thread(target=lambda: out.append(A.solve_scenario(copy.deepcopy(B.EXAMPLE_SCENARIO)))) for _ in range(2)]
    for t in ts:
        t.start()
    assert started.acquire(timeout=5) and started.acquire(timeout=5)
    try:
        with pytest.raises(FrontierError) as e:
            A.solve_scenario(copy.deepcopy(B.EXAMPLE_SCENARIO))
        assert codes(e) == ("solver_busy", 429) and e.value.body["calibrated"] is False
    finally:
        release.set()
        for t in ts:
            t.join(10)
    assert len(out) == 2 and len(calls) == 2
    assert A.SLOTS.acquire(blocking=False) and A.SLOTS.acquire(blocking=False)     # both slots were released
    A.SLOTS.release()
    A.SLOTS.release()


def canonical_ok():
    return B.canonical(B.solve(B.EXAMPLE_SCENARIO))


def test_worker_env_is_stripped_to_the_five_allowed_variables(monkeypatch):
    # Harmless sentinel (not a secret) injected into the parent; STUB worker reports its own environment.
    monkeypatch.setenv("BELIEFS_TEST_SENTINEL", "visible-if-leaked")
    monkeypatch.setenv("FRONTIER_FAKE_TOKEN_FOR_TEST", "visible-if-leaked")
    monkeypatch.setattr(A, "WORKER_ARGV", [sys.executable, "-c", "import os,json;print(json.dumps(dict(os.environ)))"])
    env = json.loads(A._spawn({}).stdout)
    assert "BELIEFS_TEST_SENTINEL" not in env and "FRONTIER_FAKE_TOKEN_FOR_TEST" not in env
    assert "visible-if-leaked" not in json.dumps(env)
    assert {k: env[k] for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                "PYTHONDONTWRITEBYTECODE")} == {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                                                                "MKL_NUM_THREADS": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    assert set(env) <= {"PATH", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                        "PYTHONDONTWRITEBYTECODE", "LC_CTYPE"}      # LC_CTYPE: set by CPython itself, not by us


def test_worker_direct_invocation_requires_flag():
    p = subprocess.run([sys.executable, "-m", "frontier.beliefs_api"], cwd=A.ROOT, capture_output=True, text=True, timeout=20)
    assert p.returncode != 0
