"""LOAD-TO-FIN bridge: declared flight loads (glide package) -> line load on one fin ray.

Chain (all exact rational arithmetic; floats only in *_float fields):
    q_dyn  = 1/2 rho V^2                      [Pa]   dynamic pressure
    p      = q_dyn * CL                       [Pa]   lift-pressure PROXY: a MEAN aerodynamic load,
                                                     NOT a measured fin pressure
    w_t    = tributary width (DECLARED)       [m]    width of membrane / ray spacing carried by one ray
             (or w_t = b / n_rays if the request declares n_rays instead)
    q_line = p * w_t                          [N/m]  uniform line load on one ray, acting normal to it
    L_ray  = f_ray * b/2 (DECLARED fraction)  [m]    ray length taken from the candidate's span
    F_tot  = q_line * L_ray                   [N]    total load on one ray
The ray is then a clamped-free Euler-Bernoulli cantilever with uniform q_line (primary case) or the
same total force at the tip (conservative upper-bound case).

Input: a candidate in the shape of frontier.glide.candidate/1 (engineering/simulation, read-only),
with witness m,S,b,V as exact rational strings and flight_assumptions rho, CL_max.
No float is accepted for a physical input; refusals are structured, never repaired silently.
"""
from __future__ import annotations

from fractions import Fraction

G_STD = Fraction(980665, 100000)  # standard gravity 9.80665 m/s^2 (exact by definition)


class Refusal(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code, self.detail = code, detail

    def to_json(self) -> dict:
        return {"verdict": "refused", "code": self.code, "detail": self.detail}


def exact(value, name: str) -> Fraction:
    """Parse an exact rational/decimal string ('1/4', '0.125', '1e-3') or int. Floats are refused."""
    if isinstance(value, bool) or isinstance(value, float):
        raise Refusal("FLOAT_INPUT", f"{name} must be an exact decimal/rational string, got {type(value).__name__}")
    try:
        return Fraction(value) if not isinstance(value, str) else Fraction(value.strip())
    except (ValueError, ZeroDivisionError):
        raise Refusal("UNPARSEABLE_NUMBER", f"{name}={value!r}")


def _pos(value, name):
    v = exact(value, name)
    if v <= 0:
        raise Refusal("NON_POSITIVE", f"{name} must be > 0, got {v}")
    return v


def _quantity(entry, name, expect_unit):
    if not isinstance(entry, dict) or "value" not in entry or "unit" not in entry or "source" not in entry:
        raise Refusal("MISSING_ASSUMPTION", f"flight_assumptions.{name} must be {{value, unit, source}}")
    if entry["unit"] != expect_unit:
        raise Refusal("UNIT_MISMATCH", f"{name} unit {entry['unit']!r} != {expect_unit!r}")
    return _pos(entry["value"], name), entry["source"]


def _s(fr: Fraction) -> str:
    return str(fr)


def bridge(request: dict) -> dict:
    """Return the load bridge as an ordered, auditable derivation. Raises Refusal on bad input."""
    cand = request.get("candidate")
    if not isinstance(cand, dict):
        raise Refusal("MISSING_CANDIDATE", "request.candidate is required")
    sr = cand.get("solver_result", {})
    if sr.get("status") != "feasible":
        raise Refusal("NOT_FEASIBLE", f"solver_result.status={sr.get('status')!r}, need 'feasible'")
    wit = sr.get("witness") or {}
    units = cand.get("units", {})
    for k, u in (("m", "kg"), ("S", "m^2"), ("b", "m"), ("V", "m/s")):
        if units.get(k) != u:
            raise Refusal("UNIT_MISMATCH", f"units.{k}={units.get(k)!r}, expected {u!r}")
    m, S, b, V = (_pos(wit.get(k), f"witness.{k}") for k in ("m", "S", "b", "V"))
    fa = cand.get("flight_assumptions", {})
    rho, rho_src = _quantity(fa.get("rho"), "rho", "kg/m^3")
    CLm, cl_src = _quantity(fa.get("CL_max"), "CL_max", "1")
    fin = request.get("fin", {})
    CL = _pos(fin["CL"], "fin.CL") if "CL" in fin else CLm
    CL_src = "fin.CL (declared override)" if "CL" in fin else "flight_assumptions.CL_max"
    if not (0 < CL <= 3):
        raise Refusal("CL_OUT_OF_RANGE", f"CL={CL} outside (0, 3]")
    f_ray = _pos(fin.get("ray_length_fraction_of_semispan"), "fin.ray_length_fraction_of_semispan")
    if f_ray > 1:
        raise Refusal("RAY_LONGER_THAN_SEMISPAN", f"fraction {f_ray} > 1")
    if ("tributary_width_m" in fin) == ("n_rays" in fin):
        raise Refusal("TRIBUTARY_WIDTH", "declare exactly one of fin.tributary_width_m or fin.n_rays")
    if "tributary_width_m" in fin:
        wt = _pos(fin["tributary_width_m"], "fin.tributary_width_m")
        wt_rule = "declared tributary_width_m"
    else:
        n_rays = _pos(fin["n_rays"], "fin.n_rays")
        wt = b / n_rays
        wt_rule = f"w_t = b / n_rays, n_rays={n_rays} (declared)"

    q_dyn = rho * V * V / 2
    p = q_dyn * CL
    q_line = p * wt
    L = f_ray * b / 2
    F_tot = q_line * L
    W = m * G_STD
    lift_proxy_total = p * S
    geometry_flags = []
    if L / wt < 5:
        geometry_flags.append("RAY_NOT_SLENDER: L / w_t < 5; beam theory is a weak description")

    def step(name, formula, val, unit):
        return {"name": name, "formula": formula, "exact": _s(val), "float": float(val), "unit": unit}

    return {
        "evidence_kind": "simulated",
        "load_proxy_statement": (
            "p = q_dyn*CL is a MEAN aerodynamic lift-pressure proxy built from DECLARED rho, V, CL; "
            "it is not a measured fin pressure, and nothing here is fluid-structure interaction."),
        "inputs": {
            "m_kg": _s(m), "S_m2": _s(S), "b_m": _s(b), "V_ms": _s(V),
            "rho_kg_m3": _s(rho), "rho_source": rho_src,
            "CL": _s(CL), "CL_source": CL_src, "CL_max_source": cl_src,
            "ray_length_fraction_of_semispan": _s(f_ray),
            "tributary_width_rule": wt_rule,
        },
        "steps": [
            step("q_dyn", "0.5*rho*V^2", q_dyn, "Pa"),
            step("p_lift_proxy", "q_dyn*CL", p, "Pa"),
            step("tributary_width", wt_rule, wt, "m"),
            step("q_line", "p*w_t", q_line, "N/m"),
            step("L_ray", "f_ray*b/2", L, "m"),
            step("F_total_on_ray", "q_line*L_ray", F_tot, "N"),
        ],
        "q_dyn_Pa": float(q_dyn), "p_Pa": float(p), "w_t_m": float(wt), "q_line_N_per_m": float(q_line),
        "L_ray_m": float(L), "F_total_N": float(F_tot),
        "exact": {"q_line_N_per_m": _s(q_line), "L_ray_m": _s(L), "F_total_N": _s(F_tot),
                  "p_Pa": _s(p), "w_t_m": _s(wt)},
        "consistency_diagnostic": {
            "weight_N_exact": _s(W), "weight_N_float": float(W), "g_m_s2": _s(G_STD),
            "p_times_S_N_float": float(lift_proxy_total),
            "ratio_pS_over_weight": float(lift_proxy_total / W),
            "note": ("Informational only: ratio p*S/(m g) is NOT repaired or enforced; it shows how "
                     "far the declared CL/V is from level lift balance (the glide package's own "
                     "receipt owns that analysis)."),
        },
        "geometry_flags": geometry_flags,
    }
