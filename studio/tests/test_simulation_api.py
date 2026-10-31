"""Real model/subprocess runs plus explicitly labelled timeout/concurrency stubs."""
from hashlib import sha256
import json
import subprocess
import sys
import threading
import time

import pytest

from frontier import simulation_api as api
from frontier.store import FrontierError


@pytest.mark.parametrize("model", ["bioelectric", "mechanobio"])
def test_real_default_subprocess_returns_actual_typed_frames(model):
    request = {"model": model}
    started = time.monotonic()
    result = api.run_preview(request)
    assert time.monotonic() - started < 8
    assert result["status"] == "completed" and result["model"] == model
    assert result["persisted"] is False and result["calibrated"] is False
    assert result["evidence_kind"] == "SimulationResult"
    assert result["request_sha256"] == sha256(api._canonical(request).encode()).hexdigest()
    assert result["code_sha256"]["frontier/simulation_api.py"] == sha256(api.Path(api.__file__).read_bytes()).hexdigest()
    environment = result["environment"]
    assert environment["python"] == api.platform.python_version()
    assert environment["numpy"]
    assert environment["platform"] and environment["machine"]
    assert bool(environment["scipy"]) == (model == "mechanobio")
    assert environment["threads"]["OPENBLAS_NUM_THREADS"] == "1"
    assert result["environment_sha256"] == api._digest(environment)
    identity = result["execution_identity"]
    assert identity["request_sha256"] == result["request_sha256"]
    assert identity["effective_request_sha256"] == result["effective_request_sha256"]
    assert identity["environment_sha256"] == result["environment_sha256"]
    assert identity["code_sha256"] == api._digest(result["code_sha256"])
    state = result["result"]
    if model == "bioelectric":
        assert state["time_ms"][0] == 0 and state["time_ms"][-1] == 30
        assert len(state["voltage_mV"]) == len(state["time_ms"])
        assert all(len(row) == 12 for row in state["voltage_mV"])
        assert state["metrics"]["cells_crossing_0mV"] == 12
    else:
        assert len(state["frames"]) == 101 and state["frames"][-1]["t_s"] == 5
        assert state["summary"]["binding_events"] > 0
        assert state["summary"]["mean_traction_pN"] > 0
        assert state["summary"]["max_force_balance_residual_pN"] < 1e-9
    json.dumps(result, allow_nan=False)


def test_environment_captured_by_real_child_not_parent_and_excludes_unrelated_versions(monkeypatch):
    expected_python = api.platform.python_version()
    monkeypatch.setattr(api.platform, "python_version", lambda: "parent-only-sentinel")
    monkeypatch.setenv("FRONTIER_FAKE_ENV_SECRET", "do-not-export")
    result = api.run_preview({"model": "bioelectric", "parameters": {"sodium_scale": .5}})
    assert result["environment"]["python"] == expected_python
    assert result["environment"]["scipy"] is None
    assert "parent-only-sentinel" not in json.dumps(result["environment"])
    assert "do-not-export" not in json.dumps(result)
    assert "FRONTIER_FAKE_ENV_SECRET" not in json.dumps(result["environment"])
    assert result["execution_identity"]["model_input_sha256"] == result["result"]["simulationAction"]["input_sha256"]
    assert result["execution_identity"]["source_context_sha256"] == api._digest(result["result"]["source_envelope"])
    changed = dict(result["environment"], numpy="test-only-other-version")
    assert api._digest(changed) != result["execution_identity"]["environment_sha256"]


@pytest.mark.parametrize("payload", [
    {}, [], {"model": "shell"}, {"model": []}, {"model": "bioelectric", "command": "ignored"},
    {"model": "bioelectric", "parameters": {"duration_ms": 60}},
    {"model": "bioelectric", "parameters": {"dt_ms": .005}},
    {"model": "bioelectric", "parameters": {"temperature_c": float("nan")}},
    {"model": "bioelectric", "parameters": {"code": "pass"}},
    {"model": "bioelectric", "parameters": {"schema": "x"}},
    {"model": "mechanobio", "parameters": {"duration_s": 30}},
    {"model": "mechanobio", "parameters": {"frame_count": 201}},
    {"model": "mechanobio", "parameters": {"frame_count": 5.0}},
    {"model": "mechanobio", "parameters": {"parameters": {"arbitrary": 1}}},
    {"model": "mechanobio", "parameters": {"dt_s": True}},
])
def test_bad_envelope_and_preview_bounds_reject_before_spawn(payload, monkeypatch):
    monkeypatch.setattr(api, "_spawn", lambda _: pytest.fail("invalid request reached worker"))
    with pytest.raises(FrontierError) as error:
        api.run_preview(payload)
    assert error.value.http_status == 400
    assert api.error_body(error.value)["persisted"] is False


@pytest.mark.parametrize("raw", [b"[]", b"NaN", b'{"model":"bioelectric","model":"mechanobio"}',
                                b'{"model":"bioelectric","parameters":{"dt_ms":Infinity}}',
                                b"x", b"\xff", b" " * 8193])
def test_malformed_nonfinite_duplicate_and_oversized_body(raw):
    with pytest.raises(FrontierError) as error:
        api.parse_body(raw)
    assert error.value.http_status == 400


@pytest.mark.parametrize("model,parameters", [("bioelectric", {"sodium_scale": -1}),
                                            ("mechanobio", {"parameters": {"motors": 0}})])
def test_real_model_validation_failure_maps_to_400(model, parameters):
    with pytest.raises(FrontierError) as error:
        api.run_preview({"model": model, "parameters": parameters})
    assert error.value.http_status == 400


def test_actual_child_timeout_is_unknown_and_releases_slot(monkeypatch):
    # Test-only fixed sleeping child; public requests cannot choose this command.
    monkeypatch.setattr(api, "WORKER_ARGV", [sys.executable, "-c", "import time;time.sleep(30)"])
    monkeypatch.setattr(api, "TIMEOUT_S", .15)
    started = time.monotonic()
    result = api.run_preview({"model": "bioelectric"})
    assert time.monotonic() - started < 2
    assert result["status"] == "unknown" and result["reason"] == "compute_budget_exhausted"
    assert result["persisted"] is False and "result" not in result
    assert api.SLOTS.acquire(blocking=False) and api.SLOTS.acquire(blocking=False)
    api.SLOTS.release()
    api.SLOTS.release()


def test_two_slots_and_third_request_busy_with_actual_children(monkeypatch):
    # Synchronization stub holds slots; each accepted call then executes the real worker.
    original = api._spawn
    entered, release = threading.Semaphore(0), threading.Event()
    results, errors = [], []

    def delayed(data):
        entered.release()
        assert release.wait(5)
        return original(data)

    def call():
        try:
            results.append(api.run_preview({"model": "mechanobio"}))
        except Exception as exc:
            errors.append(exc)

    monkeypatch.setattr(api, "_spawn", delayed)
    threads = [threading.Thread(target=call) for _ in range(2)]
    for thread in threads:
        thread.start()
    try:
        assert entered.acquire(timeout=5) and entered.acquire(timeout=5)
        with pytest.raises(FrontierError) as error:
            api.run_preview({"model": "bioelectric"})
        assert error.value.http_status == 429 and error.value.code == "simulation_busy"
    finally:
        release.set()
        for thread in threads:
            thread.join(10)
    assert not errors and len(results) == 2
    assert all(r["status"] == "completed" for r in results)


def test_stripped_environment_no_credentials_proxy_home_or_pythonpath(monkeypatch):
    monkeypatch.setenv("SIMULATION_TEST_SENTINEL", "must-not-leak")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "test-only-not-a-credential")
    monkeypatch.setenv("HTTP_PROXY", "test-only-not-a-proxy")
    monkeypatch.setattr(api, "WORKER_ARGV", [sys.executable, "-c", "import os,json;print(json.dumps(dict(os.environ)))"])
    env = json.loads(api._spawn({}).stdout)
    assert set(env) <= {"PATH", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS",
                        "VECLIB_MAXIMUM_THREADS", "PYTHONDONTWRITEBYTECODE", "LC_CTYPE"}
    assert "must-not-leak" not in json.dumps(env)
    assert env["OPENBLAS_NUM_THREADS"] == "1" and env["OMP_NUM_THREADS"] == "1"
    assert env["PATH"] == api.os.defpath


@pytest.mark.parametrize("output,code", [("TRACE test-secret", 1), ("not json", 0), ("[]", 0)])
def test_worker_failure_or_corrupt_output_is_safe_503(output, code, monkeypatch):
    # Stub malformed/failing worker. Neither stdout nor stderr may reach an error body.
    monkeypatch.setattr(api, "_spawn", lambda _: subprocess.CompletedProcess([], code, output, "TRACE test-secret"))
    with pytest.raises(FrontierError) as error:
        api.run_preview({"model": "bioelectric"})
    assert error.value.http_status == 503
    assert "TRACE" not in json.dumps(api.error_body(error.value))
    assert "test-secret" not in str(error.value)


def test_dependency_or_spawn_failure_is_503(monkeypatch):
    def unavailable(_):
        raise FileNotFoundError("test-only-secret-runtime-location")
    monkeypatch.setattr(api, "_spawn", unavailable)
    with pytest.raises(FrontierError) as error:
        api.run_preview({"model": "mechanobio"})
    assert error.value.http_status == 503
    assert "runtime-location" not in json.dumps(api.error_body(error.value))


def test_worker_does_not_relax_inherited_memory_limits():
    # Test-only child inspects resource limits without importing/running a model.
    from frontier.worker_limits import DEFAULT_ADDRESS_SPACE
    program = """
import io,json,resource,sys
import frontier.simulation_api as api
resource.setrlimit(resource.RLIMIT_AS,({inherited},{inherited}))
api._calculate=lambda data: {{'limits':resource.getrlimit(resource.RLIMIT_AS)}}
sys.stdin=io.TextIOWrapper(io.BytesIO(b'{{}}'))
api._worker()
"""
    def limits(inherited):
        process = subprocess.run([sys.executable, "-c", program.format(inherited=inherited)], capture_output=True, text=True, cwd=api.ROOT, timeout=5)
        assert process.returncode == 0
        return json.loads(process.stdout)["limits"]
    lower = DEFAULT_ADDRESS_SPACE // 2
    assert limits(lower) == [lower, lower]                                  # a lower inherited limit is never raised
    assert limits(1024**3) == [DEFAULT_ADDRESS_SPACE] * 2                   # a higher one is lowered to the worker cap
