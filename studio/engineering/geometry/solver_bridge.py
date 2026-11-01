"""Run dx-guilds' committed z3 solver on a form's biological design point, without copying it into this tree.

The solver module is read from a pinned git blob (`git show <sha>:engineering/constraints.py`), staged in a
temporary directory OUTSIDE the repository, and imported from there.  Its blob sha256 and commit are
recorded in every result, so a candidate states exactly which solver judged it.  Nothing here edits or
re-implements the solver; when the guilds branch is merged, the same blob is what `engineering.constraints`
will contain and the hash check below still holds.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

GUILDS_COMMIT = "948c2e1d743260f25858cde89256f6d2ea786195"  # also on codex/frontier-demo-20261031
GUILDS_BRANCH = "work/guilds-engineering"
SOLVER_PATH = "engineering/constraints.py"
CANDIDATE_SCHEMA = "frontier.glide.candidate/1"  # NCA's interface, messages/glide-interface-to-guilds.md

# Flight assumptions the glide simulator requires (NCA's interface section 1).  None comes from a source read
# here; each is a labelled design assumption that the simulation owner may sweep or replace.
FLIGHT_ASSUMPTIONS = {
    "rho": {"value": "1.225", "unit": "kg/m^3", "source": "design_assumption",
            "note": "ISA sea-level air density; the solver itself never defaults rho"},
    "CL_max": {"value": "1", "unit": "1", "source": "design_assumption",
               "note": "unsourced; Park & Choi 2010 report max CL at alpha 30-35 deg but the value was not read"},
    "CD0": {"value": "0.05", "unit": "1", "source": "design_assumption", "note": "unsourced placeholder"},
    "e": {"value": "0.8", "unit": "1", "source": "design_assumption", "note": "unsourced placeholder"},
    "release_height_m": {"value": "1", "unit": "m", "source": "design_assumption", "note": "unsourced"},
    "release_speed_from_witness": True,
}


def _git_blob(repo: Path, rev: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), "show", f"{rev}:{path}"], check=True,
                          capture_output=True).stdout


def load_solver(repo: Path, rev: str = GUILDS_COMMIT):
    """Import the solver from the pinned blob.  Returns (module, provenance)."""
    blob = _git_blob(repo, rev, SOLVER_PATH)
    stage = Path(tempfile.mkdtemp(prefix="guilds-solver-stage-"))
    f = stage / "guilds_constraints.py"
    f.write_bytes(blob)
    name = "guilds_constraints_" + hashlib.sha256(blob).hexdigest()[:12]
    spec = importlib.util.spec_from_file_location(name, f)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    prov = {"repo": "kganjam/delphi-frontier", "branch": GUILDS_BRANCH, "commit": rev, "path": SOLVER_PATH,
            "blob_sha256": hashlib.sha256(blob).hexdigest(), "staged_outside_repo": True,
            "z3_version": mod.z3.get_version_string()}
    return mod, prov


def _pin(mod, sym: str, value: Fraction, unit_dim: dict) -> list:
    """sym == value, as the two inequalities the solver accepts (it has no equality operator)."""
    d = mod.dim(**unit_dim)
    return [mod.Constraint(f"q_{sym}_ge", "user_query", mod.poly((1, {sym: 1}), (-value, {}, d)), ">=",
                           "form design point (see design JSON)", meta={sym: str(value)}),
            mod.Constraint(f"q_{sym}_le", "user_query", mod.poly((1, {sym: 1}), (-value, {}, d)), "<=",
                           "form design point (see design JSON)", meta={sym: str(value)})]


def rational(x: float, sig: int = 6) -> Fraction:
    """A decimal-string rational with `sig` significant figures; the rounding is part of the design point."""
    return Fraction(f"{x:.{sig}g}")


def solve_point(mod, m: Fraction, S: Fraction, b: Fraction, V: Fraction, assumptions=FLIGHT_ASSUMPTIONS) -> dict:
    """Solve the guilds flying-fish model with the design point pinned.  Returns the default run (source
    envelopes enforced) and, when that is unsat, the relaxed run that names which envelopes the point leaves.
    Neither opt-in is taken: Fish's AR range is for individual pectoral fins (its whole-wing correspondence is
    unresolved) and the 16-20 m/s figure is a taxi speed, not a flight envelope."""
    model = mod.flying_fish_model(rho=assumptions["rho"]["value"], CL=assumptions["CL_max"]["value"])
    query = (_pin(mod, "m", m, {"kg": 1}) + _pin(mod, "S", S, {"m": 2}) + _pin(mod, "b", b, {"m": 1})
             + _pin(mod, "V", V, {"m": 1, "s": -1}))
    res = mod.solve(model, query).to_json()
    out = {"default": res, "verification": mod.verify_certificate(model, res, query)
           if res["status"] in ("feasible", "unsat") else None,
           "query": {"m": str(m), "S": str(S), "b": str(b), "V": str(V)},
           "opt_ins": list(getattr(model, "opt_ins", []))}
    if res["status"] != "feasible":
        rel = mod.solve(model, query, relax_envelopes=True).to_json()
        out["relaxed"] = rel
        out["relaxed_verification"] = (mod.verify_certificate(model, rel, query, relax_envelopes=True)
                                       if rel["status"] in ("feasible", "unsat") else None)
    return out


def glide_candidate(solver_run: dict) -> dict | None:
    """NCA's `frontier.glide.candidate/1`, only for a feasible default run (the simulator refuses others)."""
    r = solver_run["default"]
    if r["status"] != "feasible":
        return None
    return {"schema": CANDIDATE_SCHEMA, "solver_result": r,
            "units": {"m": "kg", "S": "m^2", "b": "m", "V": "m/s"},
            "flight_assumptions": FLIGHT_ASSUMPTIONS, "model_version": "glide-pointmass/1"}


def canonical_sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
