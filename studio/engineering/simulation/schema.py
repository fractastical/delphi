"""Input validation and refusals for the glide simulation. Nothing is defaulted: a missing or physically invalid input is refused with a code.

A candidate is either a guilds `SolveResult.to_json()` witness (schema frontier.glide.candidate/1) or a plain dict of the same shape.
Exact rationals (str / int / Fraction) are required for the witness and assumptions; floats are accepted ONLY inside the
declared Monte-Carlo prior ranges (they are draws, not inputs)."""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction

SCHEMA_CANDIDATE = "frontier.glide.candidate/1"
SCHEMA_RECEIPT = "frontier.glide.receipt/1"
G = 9.80665                      # m/s^2, defined standard gravity (CGPM 1901)
UNITS = {"m": "kg", "S": "m^2", "b": "m", "V": "m/s"}
ASSUMPTION_UNITS = {"rho": "kg/m^3", "CL_max": "1", "CD0": "1", "e": "1", "release_height_m": "m"}
BOUNDS = {"AR": (1.0, 30.0), "CL_max": (0.0, 3.0), "e": (0.0, 1.0), "CD0": (0.0, 1.0), "rho": (0.0, 2.0)}


class Refused(Exception):
    def __init__(self, code, detail):
        super().__init__(code)
        self.code, self.detail = code, detail


def rat(name, v):
    if isinstance(v, bool) or isinstance(v, float) or v is None:
        raise Refused("INVALID_INPUT", f"{name}: floats/bools/null refused; exact rational (str/int/Fraction) required, got {v!r}")
    try:
        return Fraction(v)
    except (ValueError, ZeroDivisionError, TypeError):
        raise Refused("INVALID_INPUT", f"{name}: not an exact rational: {v!r}")


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def parse_candidate(c: dict) -> dict:
    """-> dict of floats and provenance. Raises Refused. Checks status, units, positivity, presence, bounds."""
    if not isinstance(c, dict):
        raise Refused("INVALID_INPUT", "candidate must be a JSON object")
    if c.get("schema") not in (None, SCHEMA_CANDIDATE):
        raise Refused("SCHEMA_MISMATCH", f"expected {SCHEMA_CANDIDATE}, got {c.get('schema')}")
    sr = c.get("solver_result")
    if sr is not None:
        if sr.get("status") != "feasible":
            raise Refused("SOLVER_NOT_FEASIBLE", f"solver status {sr.get('status')!r}; only 'feasible' witnesses are simulated")
        wit = sr.get("witness")
    else:
        wit = c.get("witness")
    if not isinstance(wit, dict):
        raise Refused("MISSING_INPUT", "no witness {m,S,b,V}")
    units = c.get("units", UNITS)
    for k, u in UNITS.items():
        if units.get(k) != u:
            raise Refused("UNIT_MISMATCH", f"{k} must be in {u}, got {units.get(k)!r}")
    out = {}
    for k in UNITS:
        if k not in wit:
            raise Refused("MISSING_INPUT", f"witness lacks {k}")
        x = rat(k, wit[k])
        if x <= 0:
            raise Refused("NONPHYSICAL_INPUT", f"{k} must be > 0 (got {x})")
        out[k] = x
    fa = c.get("flight_assumptions") or {}
    prov = {}
    for k in ASSUMPTION_UNITS:
        if k not in fa:
            raise Refused("MISSING_ASSUMPTION", f"flight_assumptions.{k} ({ASSUMPTION_UNITS[k]}) is required; no default is supplied")
        ent = fa[k]
        if not isinstance(ent, dict) or "value" not in ent or "source" not in ent or ent.get("unit") != ASSUMPTION_UNITS[k]:
            raise Refused("INVALID_ASSUMPTION", f"{k} must be {{'value','unit':'{ASSUMPTION_UNITS[k]}','source'}}")
        if not (ent["source"] == "design_assumption" or str(ent["source"]).startswith("cited:")):
            raise Refused("INVALID_ASSUMPTION", f"{k}.source must be 'design_assumption' or 'cited:<reference>'")
        out[k] = rat(k, ent["value"])
        prov[k] = ent["source"]
    for k, (lo, hi) in BOUNDS.items():
        if k == "AR":
            continue
        if not (lo < out[k] <= hi):
            raise Refused("NONPHYSICAL_INPUT", f"{k}={out[k]} outside ({lo}, {hi}]")
    if out["release_height_m"] <= 0:
        raise Refused("NONPHYSICAL_INPUT", "release_height_m must be > 0")
    AR = out["b"] ** 2 / out["S"]
    if not (BOUNDS["AR"][0] <= AR <= BOUNDS["AR"][1]):
        raise Refused("NONPHYSICAL_INPUT", f"AR=b^2/S={float(AR):.3g} outside {BOUNDS['AR']}")
    res = {k: float(v) for k, v in out.items()}
    res["AR"] = float(AR)
    res["assumption_sources"] = prov
    res["required_glide_range_m"] = float(rat("required_glide_range_m", c["required_glide_range_m"])) if c.get("required_glide_range_m") is not None else None
    res["candidate_sha256"] = digest({k: c.get(k) for k in ("solver_result", "witness", "units", "flight_assumptions", "required_glide_range_m")})
    res["assumption_sha256"] = digest(fa)
    res["release_speed_from_witness"] = bool(c.get("release_speed_from_witness", False))
    return res
