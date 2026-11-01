"""Deterministic cell table for the frozen 2,520-cell NCA ensemble, plus the per-cell derived inputs (T, grid, K).

Everything is computed with the vendored NCA code (cb27cf2). Selection rules for subsets are fixed here, BEFORE any result is read."""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction as F

from . import VENDOR  # noqa: F401  (puts vendor on sys.path)
from scopedesk.oracles import kinetics, linear
from scopedesk.oracles.nonlinear_sweep import ensemble as E
from scopedesk.oracles.nonlinear_sweep import run as R


def derive(c):
    """Add T, L, NA, NB, K, linear verdict to a raw ensemble cell (same formulas as nonlinear_sweep.run.run_cell)."""
    lin = linear.check(E.linear_structured(c))
    fast = (lin.get("witness") or {}).get("fastest_growing_mode")
    sig = (fast or {}).get("max_eigenvalue_float", 0.0) or 0.0
    T = min(1500.0, max(800.0, 40.0 / sig)) if sig > 0 else 800.0
    L, NA, NB, K = R.grid_for(c)
    d = dict(c)
    d.update({"T": T, "L": L, "NA": NA, "NB": NB, "K": K, "sigma_fast": sig, "linear": lin["scope_verdict"],
              "linear_fastest_mode": fast["index"][0] if fast else None})
    return d


def full_table(draws=10):
    return [derive(c) for c in E.build(draws)]


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def table_sha(cells):
    return hashlib.sha256(canon(cells).encode()).hexdigest()


# ---- subset rules (frozen) ----
PILOT_RULE = {"models": ["schnakenberg", "brusselator"], "draw": [0, 1], "x": [2, 4], "rho": [0.7, 3.0], "eps": [0.01, 0.3], "seed": [101]}


def select(cells, rule):
    return [c for c in cells if c["model"] in rule["models"] and c["draw"] in rule["draw"] and c["x"] in rule["x"]
            and c["rho"] in rule["rho"] and c["eps"] in rule["eps"] and c["seed"] in rule["seed"]]
