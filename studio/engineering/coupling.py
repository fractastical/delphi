"""Typed model ports and explicit coupling contracts. Refuses a missing bridge instead of inventing one.

This layer does NOT solve anything and does NOT duplicate engineering/constraints.py: it only reasons about
whether the OUTPUT port of one model may feed the INPUT port of another, and says so in three words:

  composable -- a typed, dimension-checked, scope-checked mapping that needs no biological assumption
                (identity, exact unit conversion, or a structurally complete CALIBRATION record);
  scenario   -- may be RUN, but only as an assumption-level scenario: every assumption is named and the result
                must carry that label; it is never evidence about an organism;
  refused    -- a bridge is missing (no mapping, non-dimensional model fed to an SI model, cross-scale or
                cross-context transfer without calibration, endpoint model not implemented, dimension
                mismatch, concurrent coupling). Nothing is invented to fill the gap; a Problem proposal is
                produced instead.

A calibration record is checked for STRUCTURE only (source with a read level, data hash, domain, uncertainty);
this module cannot verify that the data say what the record claims, and no real calibration is registered.
Lean may check the arithmetic of unit conversion (engineering/formal/UnitAlgebra.lean); it says nothing about
biological correspondence.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Iterable, Mapping

BASE_UNITS = ("kg", "m", "s")  # same base units as engineering/constraints.py (a test pins the equality)


def dim(**kw: int) -> dict[str, int]:
    return {u: int(kw.get(u, 0)) for u in BASE_UNITS}


def frac(x) -> Fraction:
    """Exact rational from int / str / Fraction. Floats are refused: they hide rounding."""
    if isinstance(x, float):
        raise TypeError("floats are not accepted; pass a Fraction or a decimal string")
    return Fraction(x)

INTERFACE_SCHEMA = "frontier.model.interface/1"
COUPLING_SCHEMA = "frontier.coupling.contract/1"
MANIFEST_SCHEMA = "frontier.coupling.manifest/1"
PROBLEM_SCHEMA = "frontier.problem.proposal/1"

SCALES = ("molecular", "cell", "tissue", "organ", "organism", "environment")
KINDS = ("dimensional", "dimensionless", "model_units")
PROV_STATUS = ("measured", "fitted", "assumed", "simulated", "unknown")
READ_LEVELS = ("full-text", "data", "abstract", "file", "none")
MODEL_STATUS = ("implemented_replayed", "implemented", "proposed")
MAPPING_KINDS = ("identity", "unit_conversion", "calibrated", "assumed", "none")
TIME_RELATIONS = ("static_input", "quasi_static", "concurrent", "unknown")
UNCERTAINTY_KINDS = ("exact", "calibration_relative_bound", "declared_interval", "unknown")
TIMESCALE_SEPARATION = Fraction(10)  # declared design parameter: 'quasi_static' needs source >= 10x slower
HEX64 = re.compile(r"^[0-9a-f]{64}$")

SCOPE_NOTE = ("A coupling verdict is about typed interfaces, not biology. 'composable' means the declared mapping is "
              "dimensionally and scope-consistent; it does not mean the models describe the same organism. "
              "'scenario' results are assumption-level. No Lean theorem here proves biological correspondence.")


class CouplingError(ValueError):
    """Malformed port/model/contract (a programming or data error, not a refusal verdict)."""


def _f(x) -> Fraction | None:
    return None if x is None else frac(x)


@dataclass(frozen=True)
class Provenance:
    source: str
    status: str          # measured | fitted | assumed | simulated | unknown
    read_level: str = "none"

    def __post_init__(self):
        if self.status not in PROV_STATUS:
            raise CouplingError(f"bad provenance status {self.status!r}")
        if self.read_level not in READ_LEVELS:
            raise CouplingError(f"bad read level {self.read_level!r}")


@dataclass(frozen=True)
class Bounds:
    lo: Fraction | None
    hi: Fraction | None
    source: str
    status: str  # measured | fitted | assumed | simulated | unknown

    def __post_init__(self):
        if self.status not in PROV_STATUS:
            raise CouplingError(f"bad bounds status {self.status!r}")
        if self.lo is not None and self.hi is not None and not self.lo <= self.hi:
            raise CouplingError("bounds need lo <= hi")

    @property
    def closed(self) -> bool:
        return self.lo is not None and self.hi is not None


@dataclass(frozen=True)
class Port:
    name: str
    direction: str                 # in | out
    quantity: str
    kind: str                      # dimensional | dimensionless | model_units
    unit: str
    dim: Mapping[str, int] | None  # None only for model_units (no SI meaning)
    scale: str
    regime: str
    context: str
    provenance: Provenance
    bounds: Bounds | None = None

    def __post_init__(self):
        if self.direction not in ("in", "out"):
            raise CouplingError(f"{self.name}: direction must be in|out")
        if self.kind not in KINDS:
            raise CouplingError(f"{self.name}: bad kind {self.kind!r}")
        if self.scale not in SCALES:
            raise CouplingError(f"{self.name}: bad scale {self.scale!r}")
        if self.kind == "dimensional":
            if self.dim is None or set(self.dim) != set(BASE_UNITS) or all(v == 0 for v in self.dim.values()):
                raise CouplingError(f"{self.name}: a dimensional port needs a non-zero (kg,m,s) dimension")
        elif self.kind == "dimensionless":
            if self.dim is None or any(v != 0 for v in self.dim.values()):
                raise CouplingError(f"{self.name}: a dimensionless port must have an all-zero dimension")
        elif self.dim is not None:
            raise CouplingError(f"{self.name}: model_units ports have no SI dimension (dim must be None)")
        if not self.quantity or not self.context or not self.regime:
            raise CouplingError(f"{self.name}: quantity, regime and context are required")


@dataclass(frozen=True)
class Timescale:
    kind: str                       # static | seconds | unknown
    seconds: Fraction | None = None
    source: str = ""

    def __post_init__(self):
        if self.kind not in ("static", "seconds", "unknown"):
            raise CouplingError("timescale kind must be static|seconds|unknown")
        if (self.kind == "seconds") != (self.seconds is not None) or (self.seconds is not None and self.seconds <= 0):
            raise CouplingError("timescale 'seconds' needs a positive value, and only then")


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    name: str
    engine: str
    status: str                     # implemented_replayed | implemented | proposed
    reference: Mapping[str, str] | None
    ports: tuple[Port, ...]
    timescale: Timescale
    scope: str
    not_established: tuple[str, ...]
    run: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in MODEL_STATUS:
            raise CouplingError(f"{self.model_id}: bad status")
        if self.status != "proposed" and not self.reference:
            raise CouplingError(f"{self.model_id}: an implemented model needs a reference (repo/branch/commit/path)")
        names = [p.name for p in self.ports]
        if len(names) != len(set(names)):
            raise CouplingError(f"{self.model_id}: duplicate port names")

    def port(self, name: str) -> Port:
        for p in self.ports:
            if p.name == name:
                return p
        raise KeyError(name)


@dataclass(frozen=True)
class Assumption:
    id: str
    text: str
    level: str = "assumption"       # always assumption-level; calibrated knowledge lives in Calibration
    owner: str = "unassigned"


@dataclass(frozen=True)
class Calibration:
    """A STRUCTURAL record of a measured/fitted mapping y = factor * x. Not verified against the data."""
    id: str
    from_port: str                  # "model.port"
    to_port: str
    evidence_kind: str              # measured | fitted_to_measured
    source: str
    read_level: str                 # full-text | data
    data_sha256: str
    domain: Bounds                  # from-port values the calibration covers
    factor: Fraction
    factor_dim: Mapping[str, int]   # dimension of the factor (to = factor * from)
    uncertainty_rel: Fraction       # relative bound on the factor
    n_points: int
    bridges: Mapping[str, tuple[str, str]]  # {"scale": (from,to), "context": (from,to)} it is calibrated across

    def structural_problems(self) -> list[str]:
        out = []
        if self.evidence_kind not in ("measured", "fitted_to_measured"):
            out.append("evidence_kind must be measured|fitted_to_measured")
        if self.read_level not in ("full-text", "data"):
            out.append("source must have been read at full-text or data level")
        if not HEX64.match(self.data_sha256 or ""):
            out.append("data_sha256 must be a 64-hex digest")
        if not self.domain.closed:
            out.append("domain must be a closed interval")
        if self.factor <= 0 or self.uncertainty_rel < 0 or self.n_points < 2:
            out.append("factor>0, uncertainty_rel>=0 and n_points>=2 are required")
        return out


@dataclass(frozen=True)
class Coupling:
    id: str
    from_ref: str                   # "model.port" (an output port)
    to_ref: str                     # "model.port" (an input port)
    mapping_kind: str               # identity | unit_conversion | calibrated | assumed | none
    factor: Fraction | None = None  # unit_conversion / assumed
    factor_dim: Mapping[str, int] | None = None
    calibration_id: str | None = None
    assumption_ids: tuple[str, ...] = ()
    time_relation: str = "unknown"
    uncertainty_kind: str = "unknown"
    uncertainty_rel: Fraction | None = None
    note: str = ""

    def __post_init__(self):
        if self.mapping_kind not in MAPPING_KINDS:
            raise CouplingError(f"{self.id}: bad mapping kind")
        if self.time_relation not in TIME_RELATIONS:
            raise CouplingError(f"{self.id}: bad time relation")
        if self.uncertainty_kind not in UNCERTAINTY_KINDS:
            raise CouplingError(f"{self.id}: bad uncertainty kind")
        if self.factor is not None and isinstance(self.factor, float):
            raise CouplingError("floats are not accepted")


@dataclass
class Registry:
    models: dict[str, ModelSpec] = field(default_factory=dict)
    calibrations: dict[str, Calibration] = field(default_factory=dict)
    assumptions: dict[str, Assumption] = field(default_factory=dict)

    def add_model(self, m: ModelSpec) -> "Registry":
        if m.model_id in self.models:
            raise CouplingError(f"duplicate model {m.model_id}")
        self.models[m.model_id] = m
        return self

    def add_calibration(self, c: Calibration) -> "Registry":
        if c.id in self.calibrations:
            raise CouplingError(f"duplicate calibration {c.id}")
        self.calibrations[c.id] = c
        return self

    def add_assumption(self, a: Assumption) -> "Registry":
        if a.id in self.assumptions:
            raise CouplingError(f"duplicate assumption {a.id}")
        self.assumptions[a.id] = a
        return self

    def resolve(self, ref: str) -> tuple[ModelSpec, Port]:
        mid, _, pname = ref.partition(".")
        if mid not in self.models:
            raise KeyError(f"unknown model {mid!r}")
        return self.models[mid], self.models[mid].port(pname)


# ---- model interface JSON ------------------------------------------------------------------------------------

def _port_json(p: Port) -> dict:
    return {"name": p.name, "direction": p.direction, "quantity": p.quantity, "kind": p.kind, "unit": p.unit,
            "dim": None if p.dim is None else {u: int(p.dim[u]) for u in BASE_UNITS},
            "scale": p.scale, "regime": p.regime, "context": p.context,
            "provenance": {"source": p.provenance.source, "status": p.provenance.status,
                           "read_level": p.provenance.read_level},
            "bounds": None if p.bounds is None else {
                "lo": None if p.bounds.lo is None else str(p.bounds.lo),
                "hi": None if p.bounds.hi is None else str(p.bounds.hi),
                "source": p.bounds.source, "status": p.bounds.status}}


def model_to_json(m: ModelSpec) -> dict:
    return {"schema": INTERFACE_SCHEMA, "model_id": m.model_id, "name": m.name, "engine": m.engine,
            "status": m.status, "reference": dict(m.reference) if m.reference else None,
            "ports": [_port_json(p) for p in m.ports],
            "timescale": {"kind": m.timescale.kind,
                          "seconds": None if m.timescale.seconds is None else str(m.timescale.seconds),
                          "source": m.timescale.source},
            "run": dict(m.run), "scope": m.scope, "not_established": list(m.not_established)}


def model_from_json(o: Mapping) -> ModelSpec:
    """Strict parser for `frontier.model.interface/1`; unknown keys and wrong schema are errors."""
    if o.get("schema") != INTERFACE_SCHEMA:
        raise CouplingError("wrong or missing schema")
    allowed = {"schema", "model_id", "name", "engine", "status", "reference", "ports", "timescale", "run", "scope",
               "not_established"}
    if set(o) - allowed:
        raise CouplingError(f"unknown interface keys {sorted(set(o) - allowed)}")
    ports = []
    for q in o["ports"]:
        if set(q) - {"name", "direction", "quantity", "kind", "unit", "dim", "scale", "regime", "context",
                     "provenance", "bounds"}:
            raise CouplingError(f"unknown port keys in {q.get('name')}")
        b = q.get("bounds")
        ports.append(Port(
            q["name"], q["direction"], q["quantity"], q["kind"], q["unit"],
            None if q["dim"] is None else {u: int(q["dim"][u]) for u in BASE_UNITS},
            q["scale"], q["regime"], q["context"],
            Provenance(**q["provenance"]),
            None if b is None else Bounds(_f(b["lo"]), _f(b["hi"]), b["source"], b["status"])))
    t = o["timescale"]
    return ModelSpec(o["model_id"], o["name"], o["engine"], o["status"], o.get("reference"), tuple(ports),
                     Timescale(t["kind"], _f(t.get("seconds")), t.get("source", "")), o["scope"],
                     tuple(o["not_established"]), o.get("run", {}))


# ---- validation ---------------------------------------------------------------------------------------------------

@dataclass
class Verdict:
    coupling_id: str
    status: str                       # composable | scenario | refused
    label: str
    reasons: list[str]
    checks: dict[str, str]
    missing_calibrations: list[str]
    assumption_ids: list[str]

    def to_json(self) -> dict:
        return {"coupling_id": self.coupling_id, "status": self.status, "label": self.label,
                "reasons": self.reasons, "checks": self.checks, "missing_calibrations": self.missing_calibrations,
                "assumption_ids": self.assumption_ids}


def _interval_map(b: Bounds, k: Fraction) -> Bounds:
    return Bounds(b.lo * k, b.hi * k, b.source, b.status)


def _subset(inner: Bounds, outer: Bounds) -> bool:
    return outer.lo <= inner.lo and inner.hi <= outer.hi


def validate_coupling(reg: Registry, c: Coupling) -> Verdict:
    refuse: list[str] = []      # hard failures -> refused
    downgrade: list[str] = []   # composable-eligible but only scenario-grade
    checks: dict[str, str] = {}
    missing: list[str] = []

    try:
        mf, pf = reg.resolve(c.from_ref)
        mt, pt = reg.resolve(c.to_ref)
    except KeyError as e:
        return Verdict(c.id, "refused", "refused: unknown model or port", [f"unknown reference {e}"],
                       {"endpoints": "fail"}, [], [])
    checks["endpoints"] = "pass"
    if pf.direction != "out" or pt.direction != "in":
        refuse.append("a coupling must run from an OUTPUT port to an INPUT port")
        checks["endpoints"] = "fail"
    if c.from_ref.split(".")[0] == c.to_ref.split(".")[0]:
        refuse.append("self-coupling inside one model is not a coupling contract")
        checks["endpoints"] = "fail"
    for m in (mf, mt):
        if m.status == "proposed":
            refuse.append(f"model {m.model_id!r} is only PROPOSED: nothing exists to run")
            checks["endpoints"] = "fail"

    asm_ids = list(c.assumption_ids)
    unknown_asm = [a for a in asm_ids if a not in reg.assumptions]
    if unknown_asm:
        refuse.append(f"unknown assumption ids {unknown_asm}")

    kind = c.mapping_kind
    cal = reg.calibrations.get(c.calibration_id) if c.calibration_id else None
    factor = c.factor
    factor_dim = c.factor_dim

    # ---- mapping presence
    if kind == "none":
        refuse.append("no mapping declared: the bridge is missing and is not invented here")
        checks["mapping"] = "fail"
    elif kind == "calibrated":
        if cal is None:
            refuse.append(f"calibration {c.calibration_id!r} is not registered")
            checks["mapping"] = "fail"
            missing.append(c.calibration_id or "unnamed calibration")
        else:
            probs = cal.structural_problems()
            if (cal.from_port, cal.to_port) != (c.from_ref, c.to_ref):
                probs.append("calibration is for a different port pair")
            if probs:
                refuse.append("calibration record is structurally invalid: " + "; ".join(probs))
                checks["mapping"] = "fail"
            else:
                checks["mapping"] = "pass"
                factor, factor_dim = cal.factor, cal.factor_dim
    elif kind == "assumed":
        if not asm_ids:
            refuse.append("an assumed mapping must name at least one assumption")
        if factor is None and pf.unit != pt.unit:
            refuse.append("an assumed mapping between different units must state its factor explicitly")
        checks["mapping"] = "scenario"
    elif kind in ("identity", "unit_conversion"):
        checks["mapping"] = "pass"
        if pf.quantity != pt.quantity:
            refuse.append(f"{kind} requires the SAME quantity ({pf.quantity!r} != {pt.quantity!r}); equal "
                          "dimensions do not make two quantities the same")
            checks["mapping"] = "fail"
        if kind == "identity" and factor is not None:
            refuse.append("identity mapping takes no factor")
        if kind == "unit_conversion" and (factor is None or factor <= 0 or factor_dim is None):
            refuse.append("unit_conversion needs a positive exact factor and its dimension")

    # ---- dimension
    if checks.get("mapping") != "fail" and kind != "none":
        if pf.kind == "model_units" or pt.kind == "model_units":
            both_mu = pf.kind == pt.kind == "model_units"
            if kind in ("identity", "unit_conversion"):
                if both_mu and kind == "identity" and pf.unit == pt.unit and pf.quantity == pt.quantity:
                    checks["dimension"] = "pass"
                else:
                    refuse.append("a non-dimensional (model_units) port cannot be mapped to a different quantity/unit "
                                  "without a calibration or a named assumption")
                    checks["dimension"] = "fail"
                    missing.append(f"{c.from_ref} -> {c.to_ref}: calibration of model units to {pt.unit}")
            elif kind == "calibrated":
                checks["dimension"] = "n/a (calibrated across model units)" if checks.get("mapping") == "pass" else "n/a"
            elif kind == "assumed":
                checks["dimension"] = "scenario: no SI meaning on one side, assumption-level only"
                missing.append(f"{c.from_ref} -> {c.to_ref}: calibration of model units to {pt.unit}")
            else:
                checks["dimension"] = "fail"
        else:
            fd = {u: pf.dim[u] for u in BASE_UNITS}
            td = {u: pt.dim[u] for u in BASE_UNITS}
            if kind == "identity":
                ok = fd == td
            elif kind in ("unit_conversion", "calibrated", "assumed") and factor is not None and factor_dim is not None:
                ok = all(fd[u] + factor_dim.get(u, 0) == td[u] for u in BASE_UNITS)
            elif kind == "assumed" and factor is None:
                ok = fd == td
            else:
                ok = False
            if kind == "unit_conversion" and ok and any(factor_dim.get(u, 0) for u in BASE_UNITS):
                ok = False  # a unit conversion between equal dimensions has a dimensionless factor
            checks["dimension"] = "pass" if ok else "fail"
            if not ok and kind != "none":
                refuse.append(f"dimension mismatch: {pf.unit} -> {pt.unit} not consistent with the mapping")
    checks.setdefault("dimension", "n/a (no valid mapping)")

    # ---- scope: scale, context, regime
    scope_gaps = []
    if pf.scale != pt.scale:
        scope_gaps.append(f"scale {pf.scale} -> {pt.scale}")
    if pf.context != pt.context:
        scope_gaps.append(f"context {pf.context!r} -> {pt.context!r}")
    if pf.regime != pt.regime:
        scope_gaps.append(f"regime {pf.regime!r} -> {pt.regime!r}")
    if scope_gaps:
        bridged = cal is not None and checks.get("mapping") == "pass" and all(
            (cal.bridges.get(k) == (a, b)) for k, (a, b) in
            {"scale": (pf.scale, pt.scale), "context": (pf.context, pt.context)}.items()
            if a != b) and pf.regime == pt.regime
        if bridged:
            checks["scope"] = "pass (calibration declares the bridge)"
        elif kind == "assumed":
            checks["scope"] = "scenario: " + "; ".join(scope_gaps)
            downgrade.append("scope differs (" + "; ".join(scope_gaps) + ") and is bridged only by assumption")
            missing.append(f"{c.from_ref} -> {c.to_ref}: calibration bridging " + "; ".join(scope_gaps))
        else:
            checks["scope"] = "fail: " + "; ".join(scope_gaps)
            refuse.append("scope mismatch without a calibration that bridges it: " + "; ".join(scope_gaps))
            missing.append(f"{c.from_ref} -> {c.to_ref}: calibration bridging " + "; ".join(scope_gaps))
    else:
        checks["scope"] = "pass"

    # ---- bounds
    fb, tb = pf.bounds, pt.bounds
    if fb is not None and tb is not None and fb.closed and tb.closed and factor is not None or \
            (fb is not None and tb is not None and fb.closed and tb.closed and kind in ("identity", "unit_conversion")):
        k = factor if factor is not None else Fraction(1)
        if cal is not None and checks.get("mapping") == "pass" and not _subset(fb, cal.domain):
            checks["bounds"] = "extrapolation: from-port range leaves the calibration domain"
            downgrade.append("source range leaves the calibration domain")
        elif _subset(_interval_map(fb, k), tb):
            checks["bounds"] = "pass"
        else:
            checks["bounds"] = "extrapolation: mapped range leaves the target port's declared bounds"
            downgrade.append("mapped range leaves the target port's declared bounds")
    elif kind in ("identity", "unit_conversion"):
        checks["bounds"] = ("not checked (a bound is open or unknown); an exact identity/unit conversion of the "
                            "same quantity adds no new extrapolation")
    else:
        checks["bounds"] = "unknown (bounds open or undeclared)"
        downgrade.append("parameter bounds are unknown on at least one side of a value-transforming mapping")

    # ---- time scale
    rel = c.time_relation
    tf, tt = mf.timescale, mt.timescale
    if rel == "concurrent":
        refuse.append("concurrent (two-way, same-clock) coupling is not supported by this layer")
        checks["time"] = "fail"
    elif rel == "static_input":
        if tf.kind == "static":
            checks["time"] = "pass"
        else:
            checks["time"] = "fail: source model is not static"
            refuse.append("static_input declared but the source model has dynamics")
    elif rel == "quasi_static":
        if tf.kind == tt.kind == "seconds":
            if tf.seconds >= TIMESCALE_SEPARATION * tt.seconds:
                checks["time"] = "pass"
            else:
                checks["time"] = f"fail: source {tf.seconds} s is not >= {TIMESCALE_SEPARATION}x target {tt.seconds} s"
                refuse.append("time scales are not separated enough for quasi-static coupling")
        else:
            checks["time"] = "unknown (a time scale is undeclared)"
            downgrade.append("a characteristic time scale is undeclared")
    else:
        if tf.kind == "static":
            checks["time"] = "pass (static source)"
        else:
            checks["time"] = "unknown"
            downgrade.append("time relation or time scale unknown")

    # ---- uncertainty
    uk = c.uncertainty_kind
    if uk == "unknown":
        checks["uncertainty"] = "unknown"
        downgrade.append("no uncertainty edge declared")
    elif uk == "exact" and kind in ("identity", "unit_conversion"):
        checks["uncertainty"] = "pass (exact arithmetic)"
    elif uk == "calibration_relative_bound" and cal is not None and checks.get("mapping") == "pass":
        checks["uncertainty"] = f"pass (calibration relative bound {cal.uncertainty_rel})"
    elif uk == "declared_interval" and c.uncertainty_rel is not None and c.uncertainty_rel >= 0:
        checks["uncertainty"] = f"declared relative interval {c.uncertainty_rel} (not checked against data)"
        downgrade.append("uncertainty is declared, not calibrated")
    else:
        checks["uncertainty"] = "fail: uncertainty kind does not match the mapping"
        refuse.append("uncertainty edge is inconsistent with the mapping kind")

    # ---- assumptions
    if asm_ids:
        checks["assumptions"] = "assumption-level: " + ", ".join(asm_ids)
        downgrade.append("assumption-level edges: " + ", ".join(asm_ids))
    else:
        checks["assumptions"] = "none"

    missing = sorted(set(missing))
    if refuse:
        return Verdict(c.id, "refused", "refused: missing or inconsistent bridge; nothing was composed",
                       refuse, checks, missing, asm_ids)
    if kind == "assumed" or downgrade:
        return Verdict(c.id, "scenario", "SCENARIO (assumption-level): may run, never evidence about an organism",
                       downgrade or ["assumed mapping"], checks, missing, asm_ids)
    return Verdict(c.id, "composable",
                   "composable: typed, dimension- and scope-checked mapping; no biological correspondence is claimed",
                   [], checks, missing, asm_ids)


# ---- Problem proposals for missing calibrations -------------------------------------------------------------

FORBIDDEN_ACTIONS = ("paid model calls", "GPU submission", "contacting other teams", "publishing a nanopub",
                     "presenting a result as an observation")


def problem_proposal(reg: Registry, c: Coupling, v: Verdict) -> dict | None:
    """A Problem for a coupling that is not composable. Thresholds are NOT invented: each is a slot that must
    be frozen (committed) before any run; success/falsifier are procedural."""
    if v.status == "composable":
        return None
    mf, pf = reg.resolve(c.from_ref)
    mt, pt = reg.resolve(c.to_ref)
    pid = f"problem-calibration-{c.id}"
    return {
        "schema": PROBLEM_SCHEMA, "id": pid, "kind": "missing_calibration", "status": "proposed",
        "not_a_claim": True, "source_coupling": c.id, "coupling_status": v.status,
        "title": f"Calibrate {pf.quantity} ({mf.model_id}.{pf.name}) -> {pt.quantity} ({mt.model_id}.{pt.name})",
        "missing": v.missing_calibrations or v.reasons,
        "success": ("A calibration record with a measured or fitted mapping, a data file with a recorded sha256, a "
                    "declared domain, an uncertainty bound and the scale/context it bridges, read at full-text or data "
                    "level, that passes validate_coupling as 'calibrated' (structure) AND whose held-out points fall "
                    "inside the stated bound. The held-out fraction and the bound are frozen BEFORE the fit."),
        "falsifier": ("Held-out measurements outside the frozen bound, a calibration domain that does not contain the "
                      "source model's declared parameter range, or no dataset pairing both quantities in the target "
                      "context after the bounded search. Any of these closes the Problem as 'no calibration "
                      "available', which keeps the coupling refused."),
        "action_bounds": {
            "allowed_actions": ["bounded literature/data search by named repository (no whole-filesystem search)",
                                "read the primary paper or dataset and record the read level",
                                "CPU-only exact or numerical fit under systemd caps (MemoryMax=4G, <=2 threads)"],
            "max_cpu_hours": "2 (declared cap, not an estimate)", "gpu": False, "paid_calls": False,
            "stop_rule": "stop and report on the first of: no dataset found, domain mismatch, cap reached",
            "forbidden": list(FORBIDDEN_ACTIONS)},
        "prerequisites": [f"{m.model_id} is implemented" for m in (mf, mt) if m.status == "proposed"],
    }


# ---- manifest -------------------------------------------------------------------------------------------------------

def build_manifest(reg: Registry, couplings: Iterable[Coupling]) -> dict:
    couplings = list(couplings)
    ids = [c.id for c in couplings]
    if len(ids) != len(set(ids)):
        raise CouplingError("duplicate coupling ids")
    rows, problems = [], []
    for c in couplings:
        v = validate_coupling(reg, c)
        rows.append({"coupling": {"id": c.id, "from": c.from_ref, "to": c.to_ref, "mapping_kind": c.mapping_kind,
                                  "factor": None if c.factor is None else str(c.factor),
                                  "calibration_id": c.calibration_id, "assumption_ids": list(c.assumption_ids),
                                  "time_relation": c.time_relation, "uncertainty_kind": c.uncertainty_kind,
                                  "note": c.note},
                     "verdict": v.to_json()})
        p = problem_proposal(reg, c, v)
        if p:
            problems.append(p)
    counts = {s: sum(r["verdict"]["status"] == s for r in rows) for s in ("composable", "scenario", "refused")}
    body = {
        "schema": MANIFEST_SCHEMA,
        "scope": SCOPE_NOTE,
        "timescale_separation": str(TIMESCALE_SEPARATION),
        "counts": counts,
        "models": [model_to_json(m) for m in sorted(reg.models.values(), key=lambda m: m.model_id)],
        "calibrations_registered": sorted(reg.calibrations),
        "assumptions": [{"id": a.id, "text": a.text, "level": a.level, "owner": a.owner}
                        for a in sorted(reg.assumptions.values(), key=lambda a: a.id)],
        "couplings": rows,
        "problem_proposals": problems,
        "must_display": [SCOPE_NOTE,
                         "Scenario results carry the label 'assumption-level'.",
                         "Registered calibrations: " + (", ".join(sorted(reg.calibrations)) or "NONE")],
        "must_not_say": ["the models are coupled", "validated multiscale model", "the fin pattern is explained",
                         "Lean proves the biological correspondence"],
    }
    body["manifest_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return body


# ---- the registry of models that exist today (read from the hand-off notes; code NOT re-read here) -----------------

def _ref(repo, branch, commit, path, read_by="dx-guilds, from the owner's hand-off note; code not re-read"):
    return {"repo": repo, "branch": branch, "commit": commit, "path": path, "read_by": read_by}


def default_registry() -> Registry:
    """Four models + the one assumption-level edge. Every port detail comes from the owners' hand-off notes in
    messages/ (biomodels-to-codex03*.md, nca-to-codex03.md, glide-interface-to-guilds.md, nca-to-gpuops.md)."""
    FISH_CTX = "Exocoetidae design envelope (Fish 1990 m / wing-loading range)"
    FISH_RG = "point-mass vertical-plane flight; Reynolds/scale validity of the polar not established"
    note = "owner hand-off note"
    reg = Registry()
    reg.add_model(ModelSpec(
        "flying_fish_constraints", "Exact-rational constraint solver (mass, wing area, span, speed)", "z3 5.3.3.0",
        "implemented", _ref("kganjam/delphi-frontier", "work/guilds-engineering", "948c2e1", "engineering/constraints.py",
                            "dx-guilds (author)"),
        (Port("m", "out", "body mass", "dimensional", "kg", dim(kg=1), "organism", FISH_RG, FISH_CTX,
              Provenance("solver witness; envelope Fish 1990 p.393", "assumed", "full-text"),
              Bounds(Fraction(3, 1000), Fraction(53, 100), "Fish 1990 p.393 specimen range", "measured")),
         Port("S", "out", "wing area", "dimensional", "m^2", dim(m=2), "organism", FISH_RG, FISH_CTX,
              Provenance("solver witness", "assumed", "none"), None),
         Port("b", "out", "wing span", "dimensional", "m", dim(m=1), "organism", FISH_RG, FISH_CTX,
              Provenance("solver witness", "assumed", "none"), None),
         Port("V", "out", "speed at the level-flight proxy", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
              FISH_CTX, Provenance("solver witness; level-flight proxy L=W", "assumed", "none"), None)),
        Timescale("static", None, "a design point: the solver has no dynamics"),
        "exact-rational feasibility of declared constraints; a level-flight proxy, not a glide analysis",
        ("organism feasibility", "glide performance", "that any witness is a viable fish"),
        {"entrypoint": "engineering.constraints.solve", "deterministic": True}))
    reg.add_model(ModelSpec(
        "glide_pointmass", "Point-mass glide simulation (RK4)", "numpy RK4", "implemented",
        _ref("kganjam/delphi-frontier", "work/nca-glide", "4dee158", "engineering/simulation/{schema,glide,evaluate}.py"),
        (Port("m", "in", "body mass", "dimensional", "kg", dim(kg=1), "organism", FISH_RG, FISH_CTX,
              Provenance("candidate from the constraint solver", "assumed", "none"),
              Bounds(Fraction(3, 1000), Fraction(53, 100), "sweep range in nca-to-codex03.md", "assumed")),
         Port("S", "in", "wing area", "dimensional", "m^2", dim(m=2), "organism", FISH_RG, FISH_CTX,
              Provenance("candidate", "assumed", "none"), None),
         Port("b", "in", "wing span", "dimensional", "m", dim(m=1), "organism", FISH_RG, FISH_CTX,
              Provenance("candidate", "assumed", "none"), None),
         Port("release_speed", "in", "release speed", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
              FISH_CTX, Provenance("glide default is 1.5 x stall speed; witness V only if the caller opts in",
                                   "assumed", "none"), None),
         Port("glide_range", "out", "horizontal glide range", "dimensional", "m", dim(m=1), "organism", FISH_RG,
              FISH_CTX, Provenance("simulated, CD0/e/CL_max are declared priors", "simulated", "none"), None),
         Port("sink_rate", "out", "equilibrium sink rate", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
              FISH_CTX, Provenance("simulated", "simulated", "none"), None)),
        Timescale("unknown", None, "glide duration is an output; no characteristic time is declared"),
        "point-mass flight with declared drag/lift priors (CL_max 0.8-1.6, CD0 0.03-0.12, e 0.6-0.95: priors, not measurements)",
        ("biological feasibility", "fin-tissue coupling", "calibrated lift/drag for any fish"),
        {"entrypoint": "engineering.simulation.evaluate", "deterministic": True, "schema": "frontier.glide.candidate/1"}))
    REG_RD = "1-D zero-flux (Neumann) field; domain length in units of the model's own critical wavelength"
    reg.add_model(ModelSpec(
        "rdfield_nonlinear_sweep", "Reaction-diffusion field (Schnakenberg, Brusselator) nonlinear sweep",
        "spectral Strang + scipy BDF", "implemented",
        _ref("kganjam/delphi-evolve", "work/rethink-nca", "02346812b93a6ee8c9e67c89b02ae6e2a69e51a7",
             "scopedesk/oracles/nonlinear_sweep"),
        (Port("L_over_lambda_c", "in", "domain length / critical wavelength", "dimensionless", "1", dim(), "tissue",
              REG_RD, "abstract kinetics; no organism", Provenance("sweep design", "assumed", "none"), None),
         Port("kinetic_parameters", "in", "kinetic parameters", "model_units", "model units", None, "tissue", REG_RD,
              "abstract kinetics; no organism", Provenance("published ranges or a stated prior", "assumed", "none"), None),
         Port("dominant_mode", "out", "dominant mode number", "dimensionless", "1", dim(), "tissue", REG_RD,
              "abstract kinetics; no organism", Provenance("simulated", "simulated", "none"), None),
         Port("pattern_flag", "out", "pattern / no pattern / not settled", "dimensionless", "1", dim(), "tissue",
              REG_RD, "abstract kinetics; no organism", Provenance("simulated", "simulated", "none"), None)),
        Timescale("unknown", None, "non-dimensional time; no SI time scale"),
        "numerical sweep of two textbook kinetics; linear verdict vs nonlinear outcome",
        ("any fin or fish tissue", "SI length or time scales", "that a real tissue obeys these kinetics"),
        {"entrypoint": "scopedesk.oracles.nonlinear_sweep", "deterministic": True}))
    reg.add_model(ModelSpec(
        "collier1996_two_cell", "Collier 1996 two-cell Delta-Notch lateral inhibition (BIOMD0000001047)",
        "libroadrunner 2.10.0 (CVODE)", "implemented_replayed",
        _ref("kganjam/delphi-frontier", "work/biomodels", "c41188dd2b47", "connectors/biomodels"),
        (Port("parameters_a_b_h_k", "in", "feedback parameters", "model_units", "model units", None, "cell",
              "two coupled cells; non-dimensional as stored; no time scale",
              "NCBI taxon 7215 as annotated in the SBML (name unresolved by the connector owner)",
              Provenance("values stored in the SBML (a 0.01, b 100, h 2, k 2, mu 1, rho 1); paper not read",
                         "unknown", "file"), None),
         Port("delta_asymmetry", "out", "Delta level difference between the two cells", "model_units", "model units",
              None, "cell", "two coupled cells; non-dimensional as stored; no time scale",
              "NCBI taxon 7215 as annotated in the SBML (name unresolved by the connector owner)",
              Provenance("simulated; horizon 0-60 chosen by the connector, not the file", "simulated", "file"), None)),
        Timescale("unknown", None, "the file declares none; horizon 0-60 is the connector's"),
        "a published model replayed as written; the replay checks the engine, not the file's fidelity to the paper",
        ("any flying-fish or fin role for Notch/Delta", "SI units", "parameter provenance"),
        {"entrypoint": "connectors.biomodels replay", "deterministic": True}))
    reg.add_model(ModelSpec(
        "finbeam_euler_bernoulli", "Fin as an Euler-Bernoulli beam (PROPOSED)", "none", "proposed", None,
        (Port("flexural_rigidity", "in", "fin flexural rigidity EI", "dimensional", "N m^2", dim(kg=1, m=3, s=-2),
              "organ", "small deflection, linear elastic (proposed)", FISH_CTX,
              Provenance("proposed slot: no source has been read", "unknown", "none"), None),
         Port("tip_deflection", "out", "tip deflection under load", "dimensional", "m", dim(m=1), "organ",
              "small deflection, linear elastic (proposed)", FISH_CTX,
              Provenance("proposed slot", "unknown", "none"), None)),
        Timescale("unknown", None, "none"),
        "a slot for a future scoped model; no implementation or source exists",
        ("everything: it does not exist yet",), {"entrypoint": None, "deterministic": None}))
    reg.add_assumption(Assumption(
        "A1", "glide release speed equals the constraint solver's witness V (the glide model's own default is 1.5 x stall speed)",
        "assumption", "dx-guilds"))
    reg.add_assumption(Assumption(
        "A2", "Notch/Delta lateral-inhibition spacing from a two-cell non-dimensional model sets fin-ray stiffness scale (NO source supports this)",
        "assumption", "dx-guilds"))
    return reg


def default_couplings() -> list[Coupling]:
    ident = dict(mapping_kind="identity", time_relation="static_input", uncertainty_kind="exact")
    return [
        Coupling("c01_mass", "flying_fish_constraints.m", "glide_pointmass.m", note="same quantity, same unit", **ident),
        Coupling("c02_area", "flying_fish_constraints.S", "glide_pointmass.S", note="same quantity, same unit", **ident),
        Coupling("c03_span", "flying_fish_constraints.b", "glide_pointmass.b", note="same quantity, same unit", **ident),
        Coupling("c04_speed", "flying_fish_constraints.V", "glide_pointmass.release_speed", mapping_kind="assumed",
                 assumption_ids=("A1",), time_relation="static_input", uncertainty_kind="unknown",
                 note="the glide model defaults to 1.5 x stall speed; identity V -> release speed is an assumption"),
        Coupling("c05_notch_to_fin_stiffness", "collier1996_two_cell.delta_asymmetry",
                 "finbeam_euler_bernoulli.flexural_rigidity", mapping_kind="none",
                 note="no mapping exists; this is the bridge a reader may be tempted to draw"),
        Coupling("c06_notch_to_fin_stiffness_assumed", "collier1996_two_cell.delta_asymmetry",
                 "finbeam_euler_bernoulli.flexural_rigidity", mapping_kind="assumed", assumption_ids=("A2",),
                 factor=Fraction(1), factor_dim=dim(kg=1, m=3, s=-2), time_relation="unknown",
                 uncertainty_kind="unknown"),
        Coupling("c07_rd_wavelength_to_wing_span", "rdfield_nonlinear_sweep.dominant_mode", "glide_pointmass.b",
                 mapping_kind="none", note="a mode number is dimensionless; the span is in metres; no length scale"),
        Coupling("c08_fin_deflection_to_glide_speed", "finbeam_euler_bernoulli.tip_deflection",
                 "glide_pointmass.release_speed", mapping_kind="none",
                 note="needs camber -> CL/CD (Park & Choi 2010 tables, PDF not yet read by anyone)"),
    ]


# ---- CLI: write the manifest and the per-model interface JSON -------------------------------------------------------

def write_outputs(outdir) -> dict:
    """Write engineering/COUPLING_MANIFEST.json and engineering/model_interfaces/<id>.json (deterministic)."""
    from pathlib import Path
    out = Path(outdir)
    (out / "model_interfaces").mkdir(parents=True, exist_ok=True)
    reg = default_registry()
    manifest = build_manifest(reg, default_couplings())
    (out / "COUPLING_MANIFEST.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    for mid, m in reg.models.items():
        (out / "model_interfaces" / f"{mid}.json").write_text(
            json.dumps(model_to_json(m), indent=1, ensure_ascii=False, sort_keys=True) + "\n")
    return manifest["counts"]


if __name__ == "__main__":
    import sys
    print(json.dumps(write_outputs(sys.argv[1] if len(sys.argv) > 1 else "engineering"), indent=1))
