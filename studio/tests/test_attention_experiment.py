"""Forecast scoring, the matched-budget experiment and the trace gate. Hand-worked; fixtures are test-only, not data."""
import json
import subprocess

import pytest

from attention import experiment as ex, forecast as fc, traces


# ------------------------------------------------------------------ forecast scoring
NOW = "2026-10-31T20:00:00Z"
spec = lambda i, h="2026-10-31T19:00:00Z": {"id": i, "horizon": h}
f = lambda sid, who, fam, p, at="2026-10-31T10:00:00Z": {"spec_id": sid, "forecaster": who, "family": fam, "probability": p, "submitted_at": at}
r = lambda sid, o, at="2026-10-31T15:00:00Z", resolver="rev": {"spec_id": sid, "outcome": o, "resolved_at": at, "resolver": resolver}


def test_score_events_hand_example_and_selection_accounting():
    specs = [spec(f"e{i}") for i in range(1, 5)] + [spec("e5", "2026-10-31T23:00:00Z"), spec("e6")]
    res = [r("e1", 1), r("e2", 0), r("e3", 1), r("e4", "void")]                     # e5 pending, e6 expired unresolved
    A = [f("e1", "A", "x", .8), f("e2", "A", "x", .3), f("e3", "A", "x", .6)]
    B = [f(s, "B", "y", .5) for s in ("e1", "e2", "e3")]
    out = fc.score_events(specs, A + B, res, NOW)
    assert out["event_status"] == {"resolved": 3, "void": 1, "expired_unresolved": 1, "pending": 1}
    assert out["per_forecaster"]["A"]["brier"] == pytest.approx((0.04 + 0.09 + 0.16) / 3)       # (.8-1)^2,(.3-0)^2,(.6-1)^2
    assert out["per_forecaster"]["B"]["brier"] == pytest.approx(0.25) and out["reference_brier_p0.5"] == 0.25
    assert "1 void and 1 expired-unresolved" in out["selection_note"] and out["calibrated_claim_allowed"] is False
    assert out["aggregates"]["mean"]["brier"] == pytest.approx(((.65 - 1) ** 2 + (.4 - 0) ** 2 + (.55 - 1) ** 2) / 3)


def test_late_forecast_and_resolver_conflict_are_excluded():
    specs = [spec("e1"), spec("e2")]
    res = [r("e1", 1, at="2026-10-31T12:00:00Z"), r("e2", 1, resolver="A")]
    fs = [f("e1", "A", "x", .9, at="2026-10-31T13:00:00Z"), f("e1", "B", "y", .6, at="2026-10-31T09:00:00Z"), f("e2", "A", "x", .9), f("e2", "B", "y", .1)]
    out = fc.score_events(specs, fs, res, NOW)
    assert out["excluded"]["late_forecast"] == [("e1", "A")] and out["excluded"]["resolver_conflict"] == ["e2"]
    assert set(out["per_forecaster"]) == {"B"} and out["per_forecaster"]["B"]["brier"] == pytest.approx(0.16)


def test_family_first_mean_and_empty_result():
    assert fc.family_first_mean([.8, .6, .2], ["x", "x", "y"]) == pytest.approx(0.45)         # (.7 + .2)/2 ; plain mean would be .5333
    out = fc.score_events([spec("e1")], [f("e1", "A", "x", .5)], [], NOW)
    assert out["per_forecaster"] is None and out["event_status"]["expired_unresolved"] == 1


def test_spec_validation():
    s = {"id": "e1", "event": "Action X is accepted by an independent reviewer before the horizon", "resolution_criterion": "action_accepted event",
         "resolution_source": "store events", "resolver": "rev", "forecasters": ["a"], "horizon": "2026-10-31T23:00:00Z", "void_conditions": "action cancelled"}
    assert fc.validate_spec(s, now=NOW.replace("20:", "18:")) == []
    assert "resolver is also a forecaster" in fc.validate_spec({**s, "resolver": "a"})
    assert "horizon is not after creation" in fc.validate_spec(s, now="2026-11-01T00:00:00Z")
    assert any("too short" in x for x in fc.validate_spec({**s, "event": "will it work"}))


# ------------------------------------------------------------------ experiment
def frozen(values, unit="eu"):
    z = {"unit": unit, "values": values}
    z["sha256"] = ex.frozen_hash(z)
    return z


def row(arm, p, cost, accepted=True, overturned=False, dup=None, hand=False):
    return {"arm": arm, "problem_id": p, "cost": cost, "accepted": accepted, "overturned": overturned, "duplicate_of": dup, "handoff_failed": hand}


def test_mcnemar_exact_hand_values():
    assert ex.mcnemar_exact([True] * 6, [False] * 6)["p_two_sided_exact"] == pytest.approx(2 / 64)      # 2*(1/2)^6
    # b=3, c=1, n=4: 2*(C(4,0)+C(4,1))/16 = 2*5/16
    assert ex.mcnemar_exact([True, True, True, False, False], [False, False, False, True, False])["p_two_sided_exact"] == pytest.approx(0.625)
    assert ex.mcnemar_exact([True], [True])["p_two_sided_exact"] == 1.0


def test_evaluate_clean_win_and_not_clean_win():
    probs = [f"p{i}" for i in range(1, 8)]
    z = frozen({p: 1.0 for p in probs})
    rows = [row("X", p, 2) for p in probs[:6]] + [row("Y", p, 3, accepted=False) for p in probs[:4]]                                     # X 12, Y 12 (matched)
    out = ex.evaluate(rows, z, ["X", "Y"])
    c = out["comparisons"]["X vs Y"]
    assert c["x_only_right"] == 6 and c["p_two_sided_exact"] == pytest.approx(0.03125) and c["verdict"] == "X resolved more problems"
    rows2 = [row("X", p, 2, overturned=(p == "p7")) for p in probs] + [row("Y", p, 2, accepted=False) for p in probs]
    out2 = ex.evaluate(rows2, z, ["X", "Y"])
    assert out2["per_arm"]["X"]["problems_resolved"] == 6 and out2["per_arm"]["X"]["incorrect_acceptance"] == 1
    assert "not a clean win" in out2["comparisons"]["X vs Y"]["verdict"]


def test_evaluate_refuses_unmatched_tampered_and_small():
    z = frozen({f"p{i}": 1.0 for i in range(1, 7)})
    out = ex.evaluate([row("X", f"p{i}", 2) for i in range(1, 7)] + [row("Y", f"p{i}", 3, accepted=False) for i in range(1, 7)], z, ["X", "Y"])
    assert out["verdict"] == "REFUSED" and "50.0%" in out["reason"]
    with pytest.raises(ex.EvalError):
        ex.evaluate([row("X", "p1", 1), row("Y", "p1", 1)], dict(z, values={**z["values"], "p1": 9.0}), ["X", "Y"])
    small = frozen({"p1": 1.0, "p2": 1.0})
    out = ex.evaluate([row("X", "p1", 2), row("X", "p2", 2), row("Y", "p1", 4, accepted=False)], small, ["X", "Y"])
    assert "INSUFFICIENT PROBLEMS" in out["comparisons"]["X vs Y"]["verdict"]
    with pytest.raises(ex.EvalError):
        ex.evaluate([row("X", "nope", 1), row("Y", "p1", 1)], small, ["X", "Y"])


def test_evaluate_counts_duplicate_effort_and_failed_handoffs():
    z = frozen({f"p{i}": 1.0 for i in range(1, 7)})
    out = ex.evaluate([row("X", "p1", 3), row("X", "p1", 2, accepted=False, dup="x", hand=True), row("Y", "p1", 5, accepted=False)], z, ["X", "Y"])
    assert out["per_arm"]["X"]["duplicate_effort_cost"] == 2 and out["per_arm"]["X"]["failed_handoffs"] == 1


# ------------------------------------------------------------------ trace gate
def trow(arm, p, cost, acc, run=None, hashed=True):
    d = {"arm": arm, "run": run or arm, "problem_id": p, "cost": cost, "accepted": acc}
    if hashed:
        d.update(source_path="trace.jsonl", source_sha256="a" * 64)
    return d


def test_trace_gate_usable_only_when_every_condition_holds():
    # test-only fixture: 6 problems; X attempts p1..p6, Y attempts p1..p5 (different sets), resolution differs on p6; costs 12 vs 12
    rows = [trow("X", f"p{i}", 2, True) for i in range(1, 7)] + [trow("Y", f"p{i}", 12 / 5, i != 3) for i in range(1, 6)]
    g = ex.trace_gate(rows)
    assert g["usable"] is True and g["blocked_reasons"] == [] and g["facts"]["problems_where_arms_differ_in_resolution_rate"] >= 1


def test_trace_gate_blocks_with_exact_reasons():
    same = [trow(a, f"p{i}", 2, True) for a in "XY" for i in range(1, 7)]
    g = ex.trace_gate(same)
    assert g["usable"] is False
    assert any("identical set of problems" in x for x in g["blocked_reasons"]) and any("ceiling/floor" in x for x in g["blocked_reasons"])
    few = ex.trace_gate([trow("X", "p1", 1, True), trow("Y", "p2", 1, False)])
    assert any("1 problems" in x or "2 problems" in x for x in few["blocked_reasons"])
    unmatched = ex.trace_gate([trow("X", f"p{i}", 2, True) for i in range(1, 7)] + [trow("Y", f"p{i}", 3, i > 2) for i in range(2, 7)])
    assert any("budgets differ" in x for x in unmatched["blocked_reasons"])
    nohash = ex.trace_gate([trow("X", "p1", 1, True, hashed=False), trow("Y", "p1", 1, True)])
    assert nohash["facts"]["rows_without_source_hash"] == 1 and any("sha256" in x for x in nohash["blocked_reasons"])
    assert ex.trace_gate([])["usable"] is False


# ------------------------------------------------------------------ the real Lean-commons traces (skipped if the source commit is absent)
SHA = "ebe024241a5d5bc8fe50c26c745d9ae55058dbd3"
EVOLVE = "/data/worktrees/delphi-evolve/market"


def _extract(tmp_path):
    try:
        subprocess.run(f"git -C {EVOLVE} archive {SHA} artifacts/commons/runs | tar -x -C {tmp_path}", shell=True, check=True, capture_output=True)
        return tmp_path / "artifacts/commons/runs"
    except Exception:
        return None


def test_real_commons_traces_are_blocked_for_an_allocation_experiment(tmp_path):
    runs = _extract(tmp_path)
    if runs is None or not runs.exists():
        pytest.skip("delphi-evolve source commit not available")
    rows = traces.commons_rows(str(runs))
    g = ex.trace_gate(rows)
    assert len(rows) == 228 and g["usable"] is False                                         # 12 arm-runs x 19 targets
    assert g["facts"]["cost_by_arm"] == {"N": 66, "P": 66, "Q": 60, "S": 64}                 # model calls; matches TABLE.json per-run calls_used
    assert g["facts"]["problems_attempted_by_arm"] == {"N": 19, "P": 19, "Q": 19, "S": 19}
    assert g["facts"]["problems_where_arms_differ_in_resolution_rate"] == 0 and g["facts"]["rows_without_source_hash"] == 0
    assert len(g["blocked_reasons"]) == 3


def test_forecast_and_experiment_outputs_do_not_imply_viability():
    out = fc.score_events([spec("e1")], [], [], NOW)
    assert "viable or true" in out["does_not_imply"]
    z = frozen({f"p{i}": 1.0 for i in range(1, 7)})
    assert "viable or true" in ex.evaluate([row("X", "p1", 2), row("Y", "p1", 2, accepted=False)], z, ["X", "Y"])["does_not_imply"]
