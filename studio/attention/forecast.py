"""Forecast scoring for frontier events (pure Python port of delphi-evolve frontier_attention.forecasting).

A forecast is of a DEFINED EVENT (an action is accepted by a horizon; a run finishes within a stop bound), never of a claim's truth.
Void and expired-unresolved events are counted and reported; late forecasts and resolver conflicts are excluded and listed.
Nothing is invented: with no resolved events the result says so. Calibration is shown as a table and never asserted.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime

LOG_EPS = 1e-6
DOES_NOT_IMPLY = ("A forecast here is of a defined process event. It says nothing about whether a design, mechanism or claim is viable or true; "
                  "viability is established only by independently reviewed computation or measurement.")


def _t(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        raise ValueError("timestamp requires a zone")
    return d


def brier(p: float, o: int) -> float:
    return (p - o) ** 2


def log_loss(p: float, o: int) -> float:
    q = min(max(p, LOG_EPS), 1 - LOG_EPS)
    return -(o * math.log(q) + (1 - o) * math.log(1 - q))


def logit(p):
    p = min(max(p, LOG_EPS), 1 - LOG_EPS)
    return math.log(p / (1 - p))


def log_pool(ps):
    return 1 / (1 + math.exp(-statistics.fmean(logit(p) for p in ps)))


def validate_spec(s: dict, now: str | None = None) -> list[str]:
    """Issues with a prediction spec; [] = scoreable. Written BEFORE anyone forecasts."""
    out = []
    for k in ("id", "event", "resolution_criterion", "resolution_source", "resolver", "void_conditions"):
        if not (isinstance(s.get(k), str) and s[k].strip()):
            out.append(f"{k} missing")
    if isinstance(s.get("event"), str) and 0 < len(s["event"].strip()) < 15:
        out.append("event too short to define a yes/no resolution")
    if isinstance(s.get("forecasters"), list) and s.get("resolver") in s["forecasters"]:
        out.append("resolver is also a forecaster")
    try:
        h = _t(s["horizon"])
        if now is not None and h <= _t(now):
            out.append("horizon is not after creation")
    except Exception:
        out.append("horizon missing or invalid")
    return out


def family_first_mean(ps: list[float], families: list[str]) -> float:
    """Mean within each family, then across families: a dependence-aware HEURISTIC, not a correction."""
    return statistics.fmean(statistics.fmean(p for p, f in zip(ps, families) if f == g) for g in sorted(set(families)))


def calibration_table(pairs: list[tuple[float, int]], bins: int = 10) -> dict:
    rows = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        sel = [(p, o) for p, o in pairs if (lo <= p < hi) or (b == bins - 1 and p == 1.0)]
        rows.append({"lo": lo, "hi": hi, "n": len(sel), "mean_forecast": statistics.fmean(p for p, _ in sel) if sel else None,
                     "observed_frequency": statistics.fmean(o for _, o in sel) if sel else None})
    return {"bins": rows, "n": len(pairs), "note": "equal-width bins; empty bins keep n=0"}


def score_events(specs: list[dict], forecasts: list[dict], resolutions: list[dict], now: str) -> dict:
    """forecasts: {spec_id, forecaster, family, probability, submitted_at}; resolutions: {spec_id, outcome in {0,1,'void'}, resolved_at, resolver}"""
    res = {r["spec_id"]: r for r in resolutions}
    t_now = _t(now)
    status = {"resolved": [], "void": [], "expired_unresolved": [], "pending": []}
    for s in specs:
        r = res.get(s["id"])
        if r is not None and r["outcome"] == "void":
            status["void"].append(s["id"])
        elif r is not None and r["outcome"] in (0, 1) and not isinstance(r["outcome"], bool):
            status["resolved"].append(s["id"])
        elif _t(s["horizon"]) <= t_now:
            status["expired_unresolved"].append(s["id"])
        else:
            status["pending"].append(s["id"])
    spec = {s["id"]: s for s in specs}
    who: dict[str, set] = {}
    for f in forecasts:
        who.setdefault(f["spec_id"], set()).add(f["forecaster"])
    excluded = {"resolver_conflict": [], "late_forecast": [], "after_horizon": []}
    keep: dict[str, dict[str, dict]] = {}
    for f in forecasts:
        sid = f["spec_id"]
        if sid not in status["resolved"]:
            continue
        r = res[sid]
        if r["resolver"] in who[sid]:
            if sid not in excluded["resolver_conflict"]:
                excluded["resolver_conflict"].append(sid)
            continue
        if _t(f["submitted_at"]) >= _t(r["resolved_at"]):
            excluded["late_forecast"].append((sid, f["forecaster"])); continue
        if _t(f["submitted_at"]) > _t(spec[sid]["horizon"]):
            excluded["after_horizon"].append((sid, f["forecaster"])); continue
        keep.setdefault(sid, {})[f["forecaster"]] = f
    scored = sorted(sid for sid in keep if sid not in excluded["resolver_conflict"])
    report = {"event_status": {k: len(v) for k, v in status.items()}, "excluded": excluded, "n_scored_events": len(scored),
              "selection_note": "scores cover RESOLVED events only; %d void and %d expired-unresolved events are not scored and may differ systematically from the scored ones"
                                % (len(status["void"]), len(status["expired_unresolved"])),
              "calibrated_claim_allowed": False, "does_not_imply": DOES_NOT_IMPLY}
    if not scored:
        return {**report, "per_forecaster": None, "reason": "no resolved events with admissible forecasts"}
    names = sorted({n for sid in scored for n in keep[sid]})
    per = {}
    for n in names:
        ids = [sid for sid in scored if n in keep[sid]]
        per[n] = {"family": keep[ids[0]][n]["family"], "n": len(ids),
                  "brier": statistics.fmean(brier(keep[sid][n]["probability"], res[sid]["outcome"]) for sid in ids),
                  "log_loss": statistics.fmean(log_loss(keep[sid][n]["probability"], res[sid]["outcome"]) for sid in ids)}
    report["per_forecaster"] = per
    report["reference_brier_p0.5"] = statistics.fmean(0.25 for _ in scored)
    report["calibration_pooled"] = calibration_table([(keep[sid][n]["probability"], res[sid]["outcome"]) for sid in scored for n in keep[sid]])
    complete = [sid for sid in scored if all(n in keep[sid] for n in names)]
    if len(names) >= 2 and complete:
        fam = [per[n]["family"] for n in names]
        agg = {"mean": [], "median": [], "log_pool": [], "family_first_mean": []}
        for sid in complete:
            ps = [keep[sid][n]["probability"] for n in names]
            agg["mean"].append(statistics.fmean(ps)); agg["median"].append(statistics.median(ps))
            agg["log_pool"].append(log_pool(ps)); agg["family_first_mean"].append(family_first_mean(ps, fam))
        report["aggregates"] = {k: {"brier": statistics.fmean(brier(p, res[sid]["outcome"]) for p, sid in zip(v, complete)),
                                    "log_loss": statistics.fmean(log_loss(p, res[sid]["outcome"]) for p, sid in zip(v, complete))} for k, v in agg.items()}
        report["distinct_families"] = len(set(fam))
        report["dependence_note"] = "forecasters sharing a model family or operator are not independent; distinct_families is an upper bound on independent voices"
    else:
        report["aggregates"] = None
    return report
