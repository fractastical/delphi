"""Bounded exact-rational constraint solver for mass / wing-area / span / speed designs.

Backend: z3 (nlsat, a decision procedure for polynomial real arithmetic), with TRACKED assertions
so an unsat answer names the conflicting constraints.  Everything z3 says is then re-checked
outside z3 where that is possible:

* feasible  -> the witness must be an EXACT RATIONAL point; every constraint is re-evaluated in
               `fractions.Fraction`, independent of z3.  An algebraic (irrational) z3 model is never
               rounded into a certificate: we only accept a rational candidate that passes the exact
               check; otherwise the status is "unknown".
* unsat     -> the core is minimised by deletion and each removal is re-checked; this is z3 checking
               z3.  No independent proof object is produced and Lean did NOT verify it (see
               `lean_conflict_certificate` for the one pattern that has a separately Lean-checked
               universal reason).
* unknown   -> missing parameters (design assumptions not yet set), solver timeout, or no exact
               rational witness.

Scope: "feasible" means "satisfies exactly the constraints that were declared, in this model".  It
is not organism feasibility, and a source envelope is not a universal feasibility region.
"""
from __future__ import annotations

import itertools
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Mapping

import z3

SOLVER_TAG = "z3-nlsat-tracked v1"
SCOPE = (
    "within the declared constraints only; not organism feasibility; "
    "a source envelope is not a universal feasibility region; "
    "the lift constraint is a level-flight proxy (L = W), not a glide analysis (L = W cos(gamma))"
)
BASE_UNITS = ("kg", "m", "s")
KINDS = ("physical_law", "source_envelope", "design_assumption", "user_query", "domain")

Dim = Mapping[str, int]


def dim(**kw: int) -> dict[str, int]:
    return {u: int(kw.get(u, 0)) for u in BASE_UNITS}


def frac(x) -> Fraction:
    """Exact rational from int / str / Fraction. Floats are refused: they hide rounding."""
    if isinstance(x, float):
        raise TypeError("floats are not accepted; pass a Fraction or a decimal string")
    return Fraction(x)


@dataclass(frozen=True)
class Quantity:
    """A decision variable with a strictly positive, bounded domain (lo <= x <= hi, x > 0)."""

    name: str
    unit: str
    dim: Dim
    lo: Fraction
    hi: Fraction
    provenance: str


@dataclass(frozen=True)
class Parameter:
    """A named constant. `value=None` means UNKNOWN: constraints using it are not evaluated."""

    name: str
    unit: str
    dim: Dim
    value: Fraction | None
    kind: str  # physical_law | source_envelope | design_assumption
    provenance: str


Term = tuple[Fraction, Mapping[str, int], Dim]  # coefficient (with its own dimension) * product(symbol ** nonnegative integer)


@dataclass(frozen=True)
class Constraint:
    """`sum(terms) OP 0` with OP in <=, >=, <, >.  Symbols are Quantity or Parameter names."""

    name: str
    kind: str
    terms: tuple[Term, ...]
    op: str
    provenance: str
    correspondence: str = ""
    meta: Mapping[str, str] = field(default_factory=dict)


def poly(*terms: tuple) -> tuple[Term, ...]:
    """Each item is (coef, {symbol: power}) or (coef, {symbol: power}, coef_dim): a literal such as
    "1 kg" in a query must say so, otherwise the dimension check cannot see it."""
    return tuple((frac(t[0]), dict(t[1]), dict(t[2]) if len(t) > 2 else dim()) for t in terms)


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RESERVED_PREFIX = "domain:"  # constraint names may not collide with the solver's domain tags


@dataclass
class Model:
    quantities: dict[str, Quantity] = field(default_factory=dict)
    parameters: dict[str, Parameter] = field(default_factory=dict)
    constraints: list[Constraint] = field(default_factory=list)
    opt_ins: list[str] = field(default_factory=list)  # names of opt-in correspondence assumptions enabled

    def add(self, *items) -> "Model":
        for it in items:
            if isinstance(it, Quantity):
                if it.name in self.quantities or it.name in self.parameters:
                    raise ValueError(f"duplicate symbol name {it.name!r}")
                self.quantities[it.name] = it
            elif isinstance(it, Parameter):
                if it.name in self.parameters or it.name in self.quantities:
                    raise ValueError(f"duplicate symbol name {it.name!r}")
                self.parameters[it.name] = it
            else:
                if any(c.name == it.name for c in self.constraints):
                    raise ValueError(f"duplicate constraint name {it.name!r}")
                self.constraints.append(it)
        return self

    def symbol_dim(self, s: str) -> Dim:
        if s in self.quantities:
            return self.quantities[s].dim
        if s in self.parameters:
            return self.parameters[s].dim
        raise KeyError(f"undeclared symbol {s!r}")

    def validate(self, extra: Iterable[Constraint] = ()) -> None:
        """Re-run on every solve/verify, because dicts and lists can be mutated after `add`."""
        overlap = set(self.quantities) & set(self.parameters)
        if overlap:
            raise ValueError(f"names used as both quantity and parameter: {sorted(overlap)}")
        for n, q in self.quantities.items():
            if n != q.name or not _IDENT.match(n):
                raise ValueError(f"bad quantity name {n!r}")
            if not (0 <= q.lo < q.hi):
                raise ValueError(f"{n}: need 0 <= lo < hi")
        for n, pm in self.parameters.items():
            if n != pm.name or not _IDENT.match(n):
                raise ValueError(f"bad parameter name {n!r}")
            if pm.value is not None and not pm.value > 0:
                raise ValueError(f"parameter {n} must be strictly positive or unknown (got {pm.value})")
        names = set()
        for c in itertools.chain(self.constraints, extra):
            if c.kind not in KINDS:
                raise ValueError(f"{c.name}: bad kind {c.kind!r}")
            if c.op not in ("<=", ">=", "<", ">"):
                raise ValueError(f"{c.name}: bad op {c.op!r}")
            if c.name.startswith(RESERVED_PREFIX):
                raise ValueError(f"{c.name}: constraint names may not start with {RESERVED_PREFIX!r}")
            if c.name in names:
                raise ValueError(f"duplicate constraint name {c.name!r}")
            names.add(c.name)
            if not c.terms:
                raise ValueError(f"{c.name}: no terms")
            if all(not pw for _, pw, _ in c.terms):
                raise ValueError(f"{c.name}: constant-only constraint (a unit no-op): mentions no symbol")
            dims = set()
            for coef, pw, cd in c.terms:
                if coef == 0:
                    raise ValueError(f"{c.name}: zero-coefficient term (a unit no-op)")
                d = {u: cd.get(u, 0) for u in BASE_UNITS}
                for sym, e in pw.items():
                    if e < 0 or int(e) != e:
                        raise ValueError(f"{c.name}: exponents must be non-negative integers")
                    if e == 0:
                        raise ValueError(f"{c.name}: zero exponent on {sym!r} (a unit no-op)")
                    for u, k in self.symbol_dim(sym).items():
                        d[u] += k * e
                dims.add(tuple(sorted(d.items())))
            if len(dims) > 1:
                raise ValueError(f"{c.name}: terms have different dimensions {sorted(dims)}")

    def missing_parameters(self, c: Constraint) -> list[str]:
        out = []
        for _, pw, _cd in c.terms:
            for s in pw:
                if s in self.parameters and self.parameters[s].value is None and s not in out:
                    out.append(s)
        return out


# ---- exact evaluation outside z3 -------------------------------------------------------------

def _eval_poly(model: Model, c: Constraint, point: Mapping[str, Fraction]) -> Fraction:
    total = Fraction(0)
    for coef, pw, _cd in c.terms:
        t = coef
        for s, e in pw.items():
            v = point[s] if s in point else model.parameters[s].value
            t *= v ** e
        total += t
    return total


def _holds(op: str, v: Fraction) -> bool:
    return {"<=": v <= 0, ">=": v >= 0, "<": v < 0, ">": v > 0}[op]


def check_point_exact(model: Model, point: Mapping[str, Fraction], constraints: Iterable[Constraint]) -> list[str]:
    """Names of violated constraints / domains, evaluated in exact Fractions (no z3)."""
    bad = []
    for q in model.quantities.values():
        x = point[q.name]
        if not (0 < x and q.lo <= x <= q.hi):
            bad.append(f"domain:{q.name}")  # positivity is a standing assumption; lo/hi are numeric caps
    for c in constraints:
        if model.missing_parameters(c):
            continue
        if not _holds(c.op, _eval_poly(model, c, point)):
            bad.append(c.name)
    return bad


# ---- z3 encoding ---------------------------------------------------------------------------------

def _rv(f: Fraction):
    return z3.RealVal(f"{f.numerator}/{f.denominator}")


def _z3_poly(model: Model, c: Constraint, zvars: Mapping[str, z3.ArithRef]):
    total = z3.RealVal(0)
    for coef, pw, _cd in c.terms:
        t = _rv(coef)
        for s, e in pw.items():
            base = zvars[s] if s in zvars else _rv(model.parameters[s].value)
            for _ in range(e):
                t = t * base
        total = total + t
    return total


def _z3_cmp(op: str, lhs):
    return {"<=": lhs <= 0, ">=": lhs >= 0, "<": lhs < 0, ">": lhs > 0}[op]


def _to_fraction(v) -> Fraction | None:
    if z3.is_rational_value(v):
        return Fraction(v.numerator_as_long(), v.denominator_as_long())
    return None


@dataclass
class SolveResult:
    status: str  # feasible | unsat | unknown
    witness: dict[str, str] | None = None
    conflict: list[str] | None = None
    core_minimal: bool | None = None
    missing_parameters: list[str] = field(default_factory=list)
    partial_witness: dict[str, str] | None = None
    reason: str = ""
    extrapolates_envelope: list[str] = field(default_factory=list)
    used_constraints: list[str] = field(default_factory=list)
    provenance: dict[str, dict] = field(default_factory=dict)
    checks: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {
            "status": self.status,
            "witness": self.witness,
            "conflict": self.conflict,
            "core_minimal": self.core_minimal,
            "missing_parameters": self.missing_parameters,
            "partial_witness": self.partial_witness,
            "reason": self.reason,
            "scope": SCOPE,
            "extrapolates_envelope": self.extrapolates_envelope,
            "used_constraints": self.used_constraints,
            "provenance": self.provenance,
            "checks": self.checks,
            "solver": SOLVER_TAG,
            "z3_version": z3.get_version_string(),
            "lean": "not_run",  # the solver never runs Lean; Lean checks are separate artifacts
        }


def _prov(model: Model, cs: Iterable[Constraint]) -> dict[str, dict]:
    out = {}
    for c in cs:
        used = {s for _, pw, _cd in c.terms for s in pw}
        out[c.name] = {
            "kind": c.kind,
            "source": c.provenance,
            "correspondence": c.correspondence,
            "parameters": {
                p: {"value": None if model.parameters[p].value is None else str(model.parameters[p].value),
                    "kind": model.parameters[p].kind, "source": model.parameters[p].provenance}
                for p in sorted(used & set(model.parameters))
            },
        }
    return out


def _build(model: Model, cs: list[Constraint], timeout_ms: int, track: bool,
           domains: "set[str] | None" = None):
    """`domains` = subset of domain tags to assert (None = all)."""
    zvars = {n: z3.Real(n) for n in model.quantities}
    s = z3.Solver()
    s.set("timeout", timeout_ms)
    tags = {}
    for q in model.quantities.values():
        s.add(zvars[q.name] > 0)  # standing domain assumption: every quantity is strictly positive (untracked)
        caps = []
        if q.lo > 0:
            caps.append((f"domain:{q.name}:lo", zvars[q.name] >= _rv(q.lo)))
        caps.append((f"domain:{q.name}:hi", zvars[q.name] <= _rv(q.hi)))
        for tag, e in caps:
            if domains is not None and tag not in domains:
                continue
            tags[tag] = z3.Bool(tag)
            s.assert_and_track(e, tags[tag]) if track else s.add(e)
    for c in cs:
        tags[c.name] = z3.Bool(c.name)
        e = _z3_cmp(c.op, _z3_poly(model, c, zvars))
        s.assert_and_track(e, tags[c.name]) if track else s.add(e)
    return s, zvars, tags


def _rational_witness(model: Model, m: z3.ModelRef, zvars, cs) -> tuple[dict[str, Fraction] | None, str]:
    """Exact rational point from a z3 model, or None. Never trusts a rounded value unchecked."""
    exact = {}
    algebraic = []
    for n, v in zvars.items():
        val = m.eval(v, model_completion=True)
        f = _to_fraction(val)
        if f is None:
            algebraic.append(n)
        else:
            exact[n] = f
    if not algebraic:
        return exact, ""
    # algebraic z3 model: try rational candidates, accept ONLY if the independent exact check passes
    for prec in (6, 12, 24):
        cand = dict(exact)
        for n in algebraic:
            a = m.eval(zvars[n], model_completion=True)
            f = _to_fraction(a.approx(prec)) if hasattr(a, "approx") else None
            if f is None:
                break
            cand[n] = f
        else:
            if not check_point_exact(model, cand, cs):
                return cand, ""
    return None, f"z3 model is algebraic in {algebraic}; no exact rational point passed the exact check"


def active_set(model: Model, query: Iterable[Constraint], relax_envelopes: bool):
    """The ONE definition of which constraints are in force. Used by solve() and by verify_certificate();
    `relax_envelopes` is a trusted argument of the caller, never read from a result."""
    allc = list(model.constraints) + list(query)
    envs = [c for c in allc if c.kind == "source_envelope"]
    active = [c for c in allc if not (relax_envelopes and c.kind == "source_envelope")]
    missing = sorted({p for c in active for p in model.missing_parameters(c)})
    usable = [c for c in active if not model.missing_parameters(c)]
    return envs, active, missing, usable


def solve(model: Model, query: Iterable[Constraint] = (), *, relax_envelopes: bool = False,
          timeout_ms: int = 20000, minimise_core: bool = True) -> SolveResult:
    """Decide the model + query. `relax_envelopes` drops `source_envelope` constraints and reports
    which of them the witness leaves (`extrapolates_envelope`)."""
    query = list(query)
    model.validate(query)
    envs, active, missing, usable = active_set(model, query, relax_envelopes)
    res = SolveResult(status="unknown", used_constraints=[c.name for c in usable],
                      provenance=_prov(model, usable))
    res.checks["relax_envelopes"] = bool(relax_envelopes)
    if relax_envelopes:
        res.checks["envelopes_dropped"] = [c.name for c in envs]

    s, zvars, tags = _build(model, usable, timeout_ms, track=True)
    r = s.check()
    if r == z3.sat:
        pt, why = _rational_witness(model, s.model(), zvars, usable)
        if pt is None:
            res.reason = why
            return res
        res.checks["exact_recheck_violations"] = check_point_exact(model, pt, usable)
        if res.checks["exact_recheck_violations"]:
            res.reason = "exact recheck failed; refusing to report a witness"
            return res
        wit = {n: str(v) for n, v in pt.items()}
        if missing:
            res.partial_witness = wit
            res.missing_parameters = missing
            res.reason = ("satisfiable on the constraints whose parameters are set, but these "
                          f"parameters are unset: {missing}; the partial point is NOT a design")
            return res
        res.status, res.witness = "feasible", wit
        if relax_envelopes:
            res.extrapolates_envelope = [c.name for c in envs if check_point_exact(model, pt, [c])]
        return res
    if r == z3.unsat:
        core = [str(t) for t in s.unsat_core()]
        names = [n for n in core if not n.startswith("domain:")] + [n for n in core if n.startswith("domain:")]
        minimal = False
        if minimise_core:
            names, minimal = _minimise(model, usable, names, timeout_ms)
        res.status, res.conflict, res.core_minimal = "unsat", names, minimal
        res.missing_parameters = missing  # unsat among the set parameters is sound whatever they are
        res.provenance = _prov(model, [c for c in usable if c.name in names])
        res.reason = ("unsat on a subset of the declared constraints; z3 verdict re-checked by z3 only, "
                      "no independent proof object")
        # sound whenever it holds on a subset
        return res
    res.reason = f"z3 returned unknown ({s.reason_unknown()})"
    res.missing_parameters = missing
    return res


def _minimise(model: Model, usable: list[Constraint], core: list[str], timeout_ms: int):
    """Deletion-based core minimisation over constraint AND domain tags; each trial is a z3 check."""
    by = {c.name: c for c in usable}
    keep = list(core)
    minimal = True
    for n in list(core):
        trial = [k for k in keep if k != n]
        s, _, _ = _build(model, [by[k] for k in trial if k in by], timeout_ms, track=True,
                         domains={k for k in trial if k.startswith("domain:")})
        r = s.check()
        if r == z3.unsat:
            keep = trial
        elif r != z3.sat:
            minimal = False
    return keep, minimal


# ---- certificate verification, independent of solve() -------------------------------------------------

def verify_certificate(model: Model, result: Mapping, query: Iterable[Constraint] = (), *,
                       relax_envelopes: bool = False) -> dict:
    """Re-check a `to_json()` result against a model and query supplied BY THE CALLER.

    The set of constraints in force is rebuilt here from (model, query, relax_envelopes); nothing is read
    from `result` to decide what must hold.  `relax_envelopes` is a trusted argument: a result that was
    produced under a different policy is rejected, not obeyed.

    feasible: the claimed constraint list must EQUAL the rebuilt set (no deletions, no extras), no active
              constraint may have an unset parameter, the witness must be exactly the declared quantities,
              strictly positive, and every constraint must hold at it in exact Fractions (independent of z3).
    unsat:    every named constraint must exist in the rebuilt set; the named core is re-checked by z3
              (NOT independent of z3; `independent` is False).
    """
    query = list(query)
    out = {"status": result.get("status"), "ok": False, "violations": [], "problems": [], "independent": None}
    try:
        model.validate(query)
    except (ValueError, KeyError) as e:
        out["problems"].append(f"model/query invalid: {e}")
        return out
    if result.get("scope") != SCOPE:
        out["problems"].append("scope text missing or altered")
    if result.get("checks", {}).get("relax_envelopes") != bool(relax_envelopes):
        out["problems"].append("result was produced under a different envelope policy than the verifier's trusted argument")
    envs, active, missing, usable = active_set(model, query, relax_envelopes)
    by = {c.name: c for c in usable}
    if result.get("status") == "feasible":
        out["independent"] = True
        if missing:
            out["problems"].append(f"active constraints use unset parameters {missing}; a feasible claim is not allowed")
        if list(result.get("used_constraints", [])) != [c.name for c in usable] or result.get("conflict"):
            out["problems"].append("claimed constraint list differs from the independently rebuilt active set")
        w = result.get("witness")
        if not isinstance(w, Mapping) or set(w) != set(model.quantities):
            out["problems"].append("witness must assign exactly the declared quantities")
        else:
            try:
                pt = {k: Fraction(v) for k, v in w.items()}
            except (ValueError, TypeError, ZeroDivisionError):
                out["problems"].append("witness values are not exact rationals")
            else:
                if any(v <= 0 for v in pt.values()):
                    out["problems"].append("witness has a non-positive quantity")
                out["violations"] = check_point_exact(model, pt, usable)
        out["ok"] = not out["problems"] and not out["violations"]
        return out
    if result.get("status") == "unsat":
        out["independent"] = False
        core = list(result.get("conflict") or [])
        names = [n for n in core if not n.startswith(RESERVED_PREFIX)]
        unknown = [n for n in names if n not in by]
        if not core or unknown:
            out["problems"].append(f"conflict names not in the rebuilt active set: {unknown or 'empty core'}")
        else:
            s, _, _ = _build(model, [by[n] for n in names], 20000, track=False,
                             domains={n for n in core if n.startswith(RESERVED_PREFIX)})
            r = s.check()
            out["z3"] = str(r)
            if r != z3.unsat:
                out["problems"].append("z3 does not reproduce unsat on the named core")
        out["ok"] = not out["problems"]
        return out
    out["problems"].append("only feasible and unsat results can be verified")
    return out


# ---- the flying-fish model ---------------------------------------------------------------------------

SOURCES = {
    "fish1990": {
        "citation": "Fish, F. E. (1990). Wing design and scaling of flying fish with regard to flight performance. "
                    "J. Zool., Lond. 221: 391-403.",
        "url": "https://health-sciences.wcupa.edu/sciences-mathematics/biology/fFish/documents/1990JZWing%20design.pdf",
        "sha256": "1efed334ed4aa48ec8e23801ff0b420d1d5c21430100a6d86d0b3e569421f8ea",
        "bytes": 368219,
        "retrieved": "2026-10-31 (dx-guilds; text extracted with pdftotext -layout, pages cited below are the journal's)",
    }
}
_F = SOURCES["fish1990"]
FISH = f"{_F['citation']} {_F['url']} sha256={_F['sha256']}; "

LEVEL_PROXY_NOTE = ("level-flight proxy: lift 0.5*rho*V^2*S*CL >= m*g (gamma = 0). A glide at path angle gamma "
                    "needs only L = W*cos(gamma); this constraint is NOT a statement that flight or gliding is feasible")


def flying_fish_model(*, rho=None, CL=None, assume_pectoral_ar_applies_to_wing: bool = False,
                      assume_taxi_speed_applies_to_flight: bool = False) -> Model:
    """Mass m [kg], wing area S [m^2], span b [m], speed V [m/s].

    DEFAULT envelopes are only the two Fish 1990 specimen measurements that map directly onto m and m*g/S:
    mass 0.003-0.53 kg and wing loading 11.7-208.9 N/m^2 (with the area-definition caveat).
    `rho` (air density) and `CL` (lift coefficient) are DESIGN ASSUMPTIONS and stay unknown unless the caller
    sets them; no default is invented.  Two further ranges are OPT-IN and enter as `design_assumption`
    constraints, never as default empirical envelopes:
      assume_pectoral_ar_applies_to_wing -- Fish's 3.0-16.9 is the aspect ratio of INDIVIDUAL PECTORAL FINS;
          applying it to the whole-wing b^2/S is a correspondence the source does not make.
      assume_taxi_speed_applies_to_flight -- 10 -> 16-20 m/s is what Fish cites for the speed rise during a taxi (Cypselurus),
          not a measured flight-speed envelope for all designs.
    The solver caps on m, S, b, V are numerical bounds, not claims.
    """
    M = Model()
    cap = "domain cap for the solver, not a claim"
    M.add(
        Quantity("m", "kg", dim(kg=1), Fraction(0), Fraction(1000), cap),
        Quantity("S", "m^2", dim(m=2), Fraction(0), Fraction(1000), cap),
        Quantity("b", "m", dim(m=1), Fraction(0), Fraction(100), cap),
        Quantity("V", "m/s", dim(m=1, s=-1), Fraction(0), Fraction(300), cap),
        Parameter("g", "m/s^2", dim(m=1, s=-2), Fraction(980665, 100000), "physical_law",
                  "standard acceleration of gravity, defined value 9.80665 m/s^2 (CGPM 1901)"),
        Parameter("rho", "kg/m^3", dim(kg=1, m=-3), None if rho is None else frac(rho), "design_assumption",
                  "caller-set air density; NOT supplied by any source in this repo"),
        Parameter("CL", "1", dim(), None if CL is None else frac(CL), "design_assumption",
                  "caller-set (maximum usable) lift coefficient; NOT supplied by any source in this repo"),
        Parameter("m_lo", "kg", dim(kg=1), Fraction(3, 1000), "source_envelope", FISH + "p.393: specimens 0.003-0.53 kg"),
        Parameter("m_hi", "kg", dim(kg=1), Fraction(53, 100), "source_envelope", FISH + "p.393: specimens 0.003-0.53 kg"),
        Parameter("WL_lo", "N/m^2", dim(kg=1, m=-1, s=-2), Fraction(117, 10), "source_envelope",
                  FISH + "p.394: 11.7 N/m^2, stated for a 0.001 kg Hirundichthys (below the stated mass range)"),
        Parameter("WL_hi", "N/m^2", dim(kg=1, m=-1, s=-2), Fraction(2089, 10), "source_envelope",
                  FISH + "p.394: 208.9 N/m^2 for a 0.53 kg Danichthys"),
    )
    area_note = "Fish's wing area = pectoral + pelvic fins + body between them; the model's S is whatever the caller means"
    M.add(
        Constraint("mass_lo", "source_envelope", poly((1, {"m": 1}), (-1, {"m_lo": 1})), ">=", FISH + "p.393"),
        Constraint("mass_hi", "source_envelope", poly((1, {"m": 1}), (-1, {"m_hi": 1})), "<=", FISH + "p.393"),
        Constraint("wl_lo", "source_envelope", poly((1, {"m": 1, "g": 1}), (-1, {"WL_lo": 1, "S": 1})), ">=",
                   FISH + "p.394", area_note),
        Constraint("wl_hi", "source_envelope", poly((1, {"m": 1, "g": 1}), (-1, {"WL_hi": 1, "S": 1})), "<=",
                   FISH + "p.394", area_note),
        Constraint("level_lift_proxy", "physical_law",
                   poly((1, {"V": 2, "rho": 1, "S": 1, "CL": 1}), (-2, {"m": 1, "g": 1})), ">=",
                   "0.5*rho*V^2*S*CL >= m*g", LEVEL_PROXY_NOTE),
    )
    if assume_pectoral_ar_applies_to_wing:
        M.opt_ins.append("pectoral_ar_applies_to_wing")
        cm = ("OPT-IN correspondence assumption: Fish's 3.0-16.9 is the aspect ratio of individual pectoral fins "
              "(p.395; Table III gives Exocoetus up to 19.9); applied here to whole-wing b^2/S, which the source does not state")
        M.add(
            Parameter("AR_lo", "1", dim(), Fraction(30, 10), "design_assumption", FISH + "p.395 (pectoral-fin AR)"),
            Parameter("AR_hi", "1", dim(), Fraction(169, 10), "design_assumption", FISH + "p.395 (pectoral-fin AR)"),
            Constraint("ar_lo_assumed", "design_assumption", poly((1, {"b": 2}), (-1, {"AR_lo": 1, "S": 1})), ">=", FISH + "p.395", cm),
            Constraint("ar_hi_assumed", "design_assumption", poly((1, {"b": 2}), (-1, {"AR_hi": 1, "S": 1})), "<=", FISH + "p.395", cm),
        )
    if assume_taxi_speed_applies_to_flight:
        M.opt_ins.append("taxi_speed_range")
        cm = ("OPT-IN assumption: Fish p.397 cites 10 -> 16-20 m/s as the speed rise during a taxi (Cypselurus, via "
              "Shoulejkin 1929 et al.); it is not a measured flight-speed envelope for all designs")
        M.add(
            Parameter("V_lo", "m/s", dim(m=1, s=-1), Fraction(10), "design_assumption", FISH + "p.397"),
            Parameter("V_hi", "m/s", dim(m=1, s=-1), Fraction(20), "design_assumption", FISH + "p.397"),
            Constraint("speed_lo_assumed", "design_assumption", poly((1, {"V": 1}), (-1, {"V_lo": 1})), ">=", FISH + "p.397", cm),
            Constraint("speed_hi_assumed", "design_assumption", poly((1, {"V": 1}), (-1, {"V_hi": 1})), "<=", FISH + "p.397", cm),
        )
    return M


def q_mass_min(v) -> Constraint:
    return Constraint("q_mass_min", "user_query", poly((1, {"m": 1}), (-frac(v), {}, dim(kg=1))), ">=", "caller query",
                      meta={"mass_min": str(frac(v))})


def q_wl_min(v) -> Constraint:
    """wing loading m g / S >= v, written m*g - v*S >= 0."""
    return Constraint("q_wl_min", "user_query", poly((1, {"m": 1, "g": 1}), (-frac(v), {"S": 1}, dim(kg=1, m=-1, s=-2))), ">=",
                      "caller query", meta={"wlmin": str(frac(v))})


def q_speed_max(v) -> Constraint:
    return Constraint("q_speed_max", "user_query", poly((1, {"V": 1}), (-frac(v), {}, dim(m=1, s=-1))), "<=", "caller query",
                      meta={"vmax": str(frac(v))})


# ---- solver -> Lean certificate (one pattern) ------------------------------------------------------------------

def _terms_eq(a, b) -> bool:
    """Structural equality of two term tuples, order-insensitive, dimensions included."""
    def norm(ts):
        return sorted(((Fraction(c), tuple(sorted((k, int(v)) for k, v in pw.items())),
                        tuple(sorted((u, int(cd.get(u, 0))) for u in BASE_UNITS))) for c, pw, cd in ts),
                      key=repr)
    return norm(a) == norm(b)


def lean_conflict_certificate(model: Model, result: "SolveResult | Mapping", query: Iterable[Constraint],
                              *, name: str = "conflict_instance") -> str | None:
    """Emit a Lean theorem applying `FlyingFish.conflict_of_certificate`, or None.

    Nothing is trusted from `result` or from `Constraint.meta`/names alone:
      * the three constraints are looked up by name in (model.constraints + query) and must match their
        EXPECTED CONSTRUCTOR structurally (terms, powers, coefficient dimensions, operator):
          level_lift_proxy : V^2*rho*S*CL - 2*m*g >= 0           (exactly the model's lift law)
          q_wl_min         : m*g - wlmin*S >= 0                  (wlmin READ FROM the S coefficient)
          q_speed_max      : V - vmax <= 0                       (vmax READ FROM the constant term)
      * rho and CL come from the model's parameters (must be set, strictly positive);
      * the Lean side condition  rho*vmax^2*CL < 2*wlmin  is checked here in exact Fractions and the
        text is refused if it is false (Lean would reject it anyway; we do not emit a known-bad proof);
      * the result is only required to claim `unsat` with exactly this core, as a sanity gate -- the
        emitted theorem's truth does not depend on it.
    Emitting this text is not running Lean."""
    r = result if isinstance(result, Mapping) else result.to_json()
    if r.get("status") != "unsat" or set(r.get("conflict") or []) != {"q_wl_min", "q_speed_max", "level_lift_proxy"}:
        return None
    by = {c.name: c for c in list(model.constraints) + list(query)}
    if len(by) != len(model.constraints) + len(list(query)) or any(n not in by for n in
                                                                  ("q_wl_min", "q_speed_max", "level_lift_proxy")):
        return None
    lift, wl, sp = by["level_lift_proxy"], by["q_wl_min"], by["q_speed_max"]
    d_wl, d_v = dim(kg=1, m=-1, s=-2), dim(m=1, s=-1)
    if not (lift.op == ">=" and _terms_eq(lift.terms, poly((1, {"V": 2, "rho": 1, "S": 1, "CL": 1}),
                                                           (-2, {"m": 1, "g": 1})))):
        return None
    # q_wl_min: exactly two terms, [1*m*g] and [-wlmin * S] with the coefficient carrying N/m^2
    if wl.op != ">=" or len(wl.terms) != 2:
        return None
    mg = [t for t in wl.terms if dict(t[1]) == {"m": 1, "g": 1}]
    sc = [t for t in wl.terms if dict(t[1]) == {"S": 1}]
    if len(mg) != 1 or len(sc) != 1 or not _terms_eq([mg[0]], poly((1, {"m": 1, "g": 1}))) \
            or sc[0][0] >= 0 or any(sc[0][2].get(u, 0) != d_wl[u] for u in BASE_UNITS):
        return None
    wlmin = -Fraction(sc[0][0])
    # q_speed_max: V - vmax <= 0
    if sp.op != "<=" or len(sp.terms) != 2:
        return None
    vt = [t for t in sp.terms if dict(t[1]) == {"V": 1}]
    ct = [t for t in sp.terms if not t[1]]
    if len(vt) != 1 or len(ct) != 1 or not _terms_eq([vt[0]], poly((1, {"V": 1}))) or ct[0][0] >= 0 \
            or any(ct[0][2].get(u, 0) != d_v[u] for u in BASE_UNITS):
        return None
    vmax = -Fraction(ct[0][0])
    rho, cl = model.parameters["rho"].value, model.parameters["CL"].value
    if rho is None or cl is None or not (rho > 0 and cl > 0 and wlmin > 0 and vmax > 0):
        return None
    if not (rho * vmax ** 2 * cl < 2 * wlmin):  # the Lean side condition, in exact arithmetic
        return None

    def lit(f) -> str:
        f = Fraction(f)
        return f"(({f.numerator} : ℝ) / {f.denominator})"

    return (
        f"theorem {name} {{m g S V : ℝ}} (hS : 0 < S) (hV0 : 0 ≤ V)\n"
        f"    (hwl : {lit(wlmin)} ≤ FlyingFish.wingLoading m g S) (hV : V ≤ {lit(vmax)})\n"
        f"    (hlift : 2 * m * g ≤ V ^ 2 * {lit(rho)} * S * {lit(cl)}) : False :=\n"
        f"  FlyingFish.conflict_of_certificate hS hV0 (by norm_num) (by norm_num) hwl hV hlift (by norm_num)\n"
    )


# ---- scoped UI manifest ------------------------------------------------------------------------------------------

UI_SCHEMA = "frontier.constraints.ui/1"
UI_BADGE = {
    "feasible": "satisfies the declared constraints (exact point)",
    "unsat": "declared constraints conflict (named below)",
    "unknown": "not decided",
}
UI_MUST_NOT_SAY = ("feasible design", "flight is feasible", "the organism can fly", "viable organism", "proved",
                   "Lean verified the solver", "universal limit")
UI_LEAN_COVERS = ("scaling of wing loading and level-flight speed under the stated geometric-similarity hypotheses",
                  "the wing-loading ceiling lemma behind the {level_lift_proxy, q_wl_min, q_speed_max} conflict")
UI_LEAN_DOES_NOT_COVER = ("any z3 verdict except via the emitted certificate for that one core",
                          "organism feasibility", "Fish's measured allometry", "unit correctness (checked in Python)")


def ui_manifest(model: Model, result: "SolveResult | Mapping", query: Iterable[Constraint] = (), *,
                relax_envelopes: bool = False) -> dict:
    """What a UI may render for a result, with the wording constraints it must keep.  The manifest embeds an
    independent `verify_certificate` run and never upgrades a status: if verification fails it says so and
    withholds the witness."""
    query = list(query)
    r = result if isinstance(result, Mapping) else result.to_json()
    ver = verify_certificate(model, r, query, relax_envelopes=relax_envelopes) if r["status"] in ("feasible", "unsat") \
        else {"status": r["status"], "ok": None}
    shown = r["status"] if ver["ok"] is not False else "unknown"
    conflict = set(r.get("conflict") or [])
    used = set(r.get("used_constraints") or [])
    allc = {c.name: c for c in list(model.constraints) + query}
    rows = []
    for n, c in allc.items():
        rows.append({
            "name": n, "kind": c.kind, "in_force": n in used, "in_conflict": n in conflict,
            "source": c.provenance, "correspondence": c.correspondence or None,
            "opt_in_assumption": c.kind == "design_assumption" and n.endswith("_assumed"),
            "parameters_missing": model.missing_parameters(c),
        })
    witness = None
    if shown == "feasible":
        witness = [{"symbol": q.name, "unit": q.unit, "exact": r["witness"][q.name],
                    "display_decimal": f"{float(Fraction(r['witness'][q.name])):.6g}"}
                   for q in model.quantities.values()]
    must = [SCOPE, LEVEL_PROXY_NOTE]
    if shown == "unsat":
        must.append("The conflict is a z3 verdict re-checked by z3; Lean did not verify it.")
    if model.opt_ins:
        must.append("Opt-in assumptions enabled (not default empirical envelopes): " + ", ".join(model.opt_ins))
    if relax_envelopes:
        must.append("Source envelopes were DROPPED for this run; any point may lie outside what the source observed: "
                    + ", ".join(r.get("extrapolates_envelope") or []))
    if r.get("missing_parameters"):
        must.append("Unset design assumptions: " + ", ".join(r["missing_parameters"]))
    return {
        "schema": UI_SCHEMA,
        "status": shown,
        "badge": UI_BADGE[shown],
        "headline": {
            "feasible": "An exact rational point satisfies every declared constraint listed below.",
            "unsat": "No point satisfies these named constraints together: " + ", ".join(sorted(conflict)) + ".",
            "unknown": "Not decided. " + (r.get("reason") or ""),
        }[shown],
        "must_display": must,
        "must_not_say": list(UI_MUST_NOT_SAY),
        "witness": witness,
        "rows": rows,
        "verification": ver,
        "lean": {"run_by_this_solver": False, "receipt": "engineering/formal/RECEIPT.json",
                 "covers": list(UI_LEAN_COVERS), "does_not_cover": list(UI_LEAN_DOES_NOT_COVER)},
        "solver": r.get("solver"), "z3_version": r.get("z3_version"),
    }
