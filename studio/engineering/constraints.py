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
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Mapping

import z3

SOLVER_TAG = "z3-nlsat-tracked v1"
SCOPE = (
    "within the declared constraints only; not organism feasibility; "
    "a source envelope is not a universal feasibility region"
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


@dataclass
class Model:
    quantities: dict[str, Quantity] = field(default_factory=dict)
    parameters: dict[str, Parameter] = field(default_factory=dict)
    constraints: list[Constraint] = field(default_factory=list)

    def add(self, *items) -> "Model":
        for it in items:
            if isinstance(it, Quantity):
                self.quantities[it.name] = it
            elif isinstance(it, Parameter):
                self.parameters[it.name] = it
            else:
                self.constraints.append(it)
        return self

    def symbol_dim(self, s: str) -> Dim:
        if s in self.quantities:
            return self.quantities[s].dim
        if s in self.parameters:
            return self.parameters[s].dim
        raise KeyError(f"undeclared symbol {s!r}")

    def validate(self, extra: Iterable[Constraint] = ()) -> None:
        names = set()
        for c in itertools.chain(self.constraints, extra):
            if c.kind not in KINDS:
                raise ValueError(f"{c.name}: bad kind {c.kind!r}")
            if c.op not in ("<=", ">=", "<", ">"):
                raise ValueError(f"{c.name}: bad op {c.op!r}")
            if c.name in names:
                raise ValueError(f"duplicate constraint name {c.name!r}")
            names.add(c.name)
            dims = set()
            for coef, pw, cd in c.terms:
                d = {u: cd.get(u, 0) for u in BASE_UNITS}
                for s, e in pw.items():
                    if e < 0 or int(e) != e:
                        raise ValueError(f"{c.name}: exponents must be non-negative integers")
                    for u, k in self.symbol_dim(s).items():
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


def solve(model: Model, query: Iterable[Constraint] = (), *, relax_envelopes: bool = False,
          timeout_ms: int = 20000, minimise_core: bool = True) -> SolveResult:
    """Decide the model + query. `relax_envelopes` drops `source_envelope` constraints and reports
    which of them the witness leaves (`extrapolates_envelope`)."""
    query = list(query)
    model.validate(query)
    allc = list(model.constraints) + query
    envs = [c for c in allc if c.kind == "source_envelope"]
    active = [c for c in allc if not (relax_envelopes and c.kind == "source_envelope")]
    missing = sorted({p for c in active for p in model.missing_parameters(c)})
    usable = [c for c in active if not model.missing_parameters(c)]
    res = SolveResult(status="unknown", used_constraints=[c.name for c in usable],
                      provenance=_prov(model, usable))
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

def verify_certificate(model: Model, result: Mapping, query: Iterable[Constraint] = ()) -> dict:
    """Re-check a `to_json()` result without calling solve().

    feasible: exact Fraction evaluation of every used constraint at the witness (independent of z3).
    unsat:    z3 re-check of the named core only (NOT independent of z3); `independent` is False.
    """
    query = list(query)
    allc = {c.name: c for c in list(model.constraints) + query}
    if result["status"] == "feasible":
        pt = {k: Fraction(v) for k, v in result["witness"].items()}
        cs = [allc[n] for n in result["used_constraints"]]
        bad = check_point_exact(model, pt, cs)
        return {"status": "feasible", "ok": not bad, "violations": bad, "independent": True}
    if result["status"] == "unsat":
        core = [n for n in result["conflict"] if n in allc]
        s, _, _ = _build(model, [allc[n] for n in core], 20000, track=False,
                         domains={n for n in result["conflict"] if n.startswith("domain:")})
        r = s.check()
        return {"status": "unsat", "ok": r == z3.unsat, "z3": str(r), "independent": False}
    return {"status": result["status"], "ok": None, "independent": None}


# ---- the flying-fish model ---------------------------------------------------------------------------

FISH = ("Fish, F. E. (1990) J. Zool. Lond. 221:391-403; primary PDF re-read 2026-10-31 by dx-guilds "
        "(sha256 1efed334ed4aa48e...); ")


def flying_fish_model(*, rho=None, CL=None) -> Model:
    """Mass m [kg], wing area S [m^2], span b [m], speed V [m/s].

    `rho` (air density) and `CL` (lift coefficient) are DESIGN ASSUMPTIONS and stay unknown unless the
    caller sets them; no default is invented.  Envelope numbers are Fish 1990 values re-read from the
    primary PDF; the extra domain caps (hi) are numerical bounds for the solver, not claims.
    """
    M = Model()
    M.add(
        Quantity("m", "kg", dim(kg=1), Fraction(0), Fraction(1000), "domain cap for the solver, not a claim"),
        Quantity("S", "m^2", dim(m=2), Fraction(0), Fraction(1000), "domain cap for the solver, not a claim"),
        Quantity("b", "m", dim(m=1), Fraction(0), Fraction(100), "domain cap for the solver, not a claim"),
        Quantity("V", "m/s", dim(m=1, s=-1), Fraction(0), Fraction(300), "domain cap for the solver, not a claim"),
        Parameter("g", "m/s^2", dim(m=1, s=-2), Fraction(980665, 100000), "physical_law",
                  "standard acceleration of gravity, defined value 9.80665 m/s^2 (CGPM 1901)"),
        Parameter("rho", "kg/m^3", dim(kg=1, m=-3), None if rho is None else frac(rho), "design_assumption",
                  "caller-set air density; NOT supplied by any source in this repo"),
        Parameter("CL", "1", dim(), None if CL is None else frac(CL), "design_assumption",
                  "caller-set (maximum) lift coefficient; NOT supplied by any source in this repo"),
        # source envelopes (dimensioned constants so units are checked)
        Parameter("m_lo", "kg", dim(kg=1), Fraction(3, 1000), "source_envelope", FISH + "p.393: specimens 0.003-0.53 kg"),
        Parameter("m_hi", "kg", dim(kg=1), Fraction(53, 100), "source_envelope", FISH + "p.393: specimens 0.003-0.53 kg"),
        Parameter("WL_lo", "N/m^2", dim(kg=1, m=-1, s=-2), Fraction(117, 10), "source_envelope",
                  FISH + "p.394: 11.7 N/m^2, stated for a 0.001 kg Hirundichthys (below the stated mass range)"),
        Parameter("WL_hi", "N/m^2", dim(kg=1, m=-1, s=-2), Fraction(2089, 10), "source_envelope",
                  FISH + "p.394: 208.9 N/m^2 for a 0.53 kg Danichthys"),
        Parameter("AR_lo", "1", dim(), Fraction(30, 10), "source_envelope", FISH + "p.395: individual PECTORAL-FIN AR 3.0-16.9"),
        Parameter("AR_hi", "1", dim(), Fraction(169, 10), "source_envelope",
                  FISH + "p.395: individual PECTORAL-FIN AR 3.0-16.9 (Table III gives Exocoetus up to 19.9)"),
        Parameter("V_lo", "m/s", dim(m=1, s=-1), Fraction(10), "source_envelope",
                  FISH + "p.397: taxi raises take-off speed 'from 10 to 16-20 m/s' (cited by Fish to Shoulejkin 1929 etc.)"),
        Parameter("V_hi", "m/s", dim(m=1, s=-1), Fraction(20), "source_envelope", FISH + "p.397 as above"),
    )
    cm = "fin-level envelope applied to whole-wing quantity: a modelling choice, not stated by the source"
    M.add(
        Constraint("mass_lo", "source_envelope", poly((1, {"m": 1}), (-1, {"m_lo": 1})), ">=", FISH + "p.393"),
        Constraint("mass_hi", "source_envelope", poly((1, {"m": 1}), (-1, {"m_hi": 1})), "<=", FISH + "p.393"),
        Constraint("wl_lo", "source_envelope", poly((1, {"m": 1, "g": 1}), (-1, {"WL_lo": 1, "S": 1})), ">=",
                   FISH + "p.394", "wing area definition differs: Fish's area = pectoral+pelvic fins+body between them"),
        Constraint("wl_hi", "source_envelope", poly((1, {"m": 1, "g": 1}), (-1, {"WL_hi": 1, "S": 1})), "<=",
                   FISH + "p.394", "wing area definition differs: Fish's area = pectoral+pelvic fins+body between them"),
        Constraint("ar_lo", "source_envelope", poly((1, {"b": 2}), (-1, {"AR_lo": 1, "S": 1})), ">=", FISH + "p.395", cm),
        Constraint("ar_hi", "source_envelope", poly((1, {"b": 2}), (-1, {"AR_hi": 1, "S": 1})), "<=", FISH + "p.395", cm),
        Constraint("speed_lo", "source_envelope", poly((1, {"V": 1}), (-1, {"V_lo": 1})), ">=", FISH + "p.397"),
        Constraint("speed_hi", "source_envelope", poly((1, {"V": 1}), (-1, {"V_hi": 1})), "<=", FISH + "p.397"),
        Constraint("lift_stall", "physical_law",
                   poly((1, {"V": 2, "rho": 1, "S": 1, "CL": 1}), (-2, {"m": 1, "g": 1})), ">=",
                   "level flight: lift 0.5 rho V^2 S CL >= weight m g (CL = maximum usable lift coefficient)"),
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

def lean_conflict_certificate(model: Model, result: "SolveResult | Mapping", query: Iterable[Constraint],
                              *, name: str = "conflict_instance") -> str | None:
    """If the unsat core is exactly {q_wl_min, q_speed_max, lift_stall}, emit a Lean theorem that applies
    `FlyingFish.conflict_of_certificate`, with wlmin / vmax taken FROM THE QUERY OBJECTS and rho / CL from
    the model.  Lean then checks `rho * vmax^2 * CL < 2 * wlmin` itself and the universal lemma supplies the
    reason.  Any other core returns None (no claim).  Emitting this text is not running Lean."""
    r = result if isinstance(result, Mapping) else result.to_json()
    if r["status"] != "unsat" or set(r["conflict"]) != {"q_wl_min", "q_speed_max", "lift_stall"}:
        return None
    qs = {c.name: c for c in query}
    wl, vm = qs["q_wl_min"].meta["wlmin"], qs["q_speed_max"].meta["vmax"]
    rho, cl = model.parameters["rho"].value, model.parameters["CL"].value

    def lit(f) -> str:
        f = Fraction(f)
        return f"(({f.numerator} : ℝ) / {f.denominator})"

    return (
        f"theorem {name} {{m g S V : ℝ}} (hS : 0 < S) (hV0 : 0 ≤ V)\n"
        f"    (hwl : {lit(wl)} ≤ FlyingFish.wingLoading m g S) (hV : V ≤ {lit(vm)})\n"
        f"    (hlift : 2 * m * g ≤ V ^ 2 * {lit(rho)} * S * {lit(cl)}) : False :=\n"
        f"  FlyingFish.conflict_of_certificate hS hV0 (by norm_num) (by norm_num) hwl hV hlift (by norm_num)\n"
    )
