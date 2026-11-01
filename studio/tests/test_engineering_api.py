import pytest

from frontier.engineering_api import calculate, solve_design, validate_request
from frontier.store import FrontierError


@pytest.mark.parametrize("data", [{"rho": 1.225}, {"mass": "nan"}, {"mass": "1e100000"},
    {"span": "-1"}, {"cl_max": "4"}, {"mass": True}, {"relax_envelopes": "true"},
    {"command": "uname"}, {"rho": "1/2"}, []])
def test_finite_design_language(data):
    with pytest.raises(FrontierError):
        validate_request(data)


def test_real_solver_process_and_context():
    data = {"rho": "1.225", "cl_max": "1", "mass": "0.05", "area": "0.01", "span": "0.25", "speed": "12"}
    got = solve_design(data)
    assert got["result"]["status"] == "feasible"
    assert got["checked_by"]["independent_witness"]["ok"] is True
    assert got["checked_by"]["lean"] == "not_run"
    assert got["parameters"]["cl_max"]["basis"] == "caller_design_assumption"
    assert len(got["code_sha256"]) == 2
    assert got["questions_persisted"] is False
    assert {q["approach"] for q in got["followup_questions"]} >= {"design_goal", "theory_fit"}
    missing = calculate({"mass": "0.05"})
    assert missing["result"]["status"] == "unknown"
    assert set(missing["result"]["missing_parameters"]) == {"CL", "rho"}
    conflict = calculate({"rho": "1.225", "cl_max": "1", "wing_loading_min": "150", "speed_max": "10"})
    assert conflict["result"]["status"] == "unsat"
    assert conflict["checked_by"]["lean"] == "not_run"


def test_worker_timeout_is_unknown(monkeypatch):
    import subprocess
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], 8)
    monkeypatch.setattr(subprocess, "run", timeout)
    assert solve_design({})["result"]["status"] == "unknown"
