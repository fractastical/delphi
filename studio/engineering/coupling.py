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


def tree_sha256(files: Mapping[str, str]) -> str:
    """Hash over 'path<TAB>sha256' lines sorted by path: one digest for a set of source files."""
    return hashlib.sha256("".join(f"{p}\t{files[p]}\n" for p in sorted(files)).encode()).hexdigest()


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
    caveat: str = ""   # why this quantity must not be read as the target's measured quantity (proxy, declared value, ...)

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
    reference: Mapping[str, object] | None
    ports: tuple[Port, ...]
    timescale: Timescale
    scope: str
    not_established: tuple[str, ...]
    run: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if self.status not in MODEL_STATUS:
            raise CouplingError(f"{self.model_id}: bad status")
        if self.status != "proposed":
            ref = self.reference or {}
            need = ("repo", "branch", "commit", "path", "files", "source_sha256")
            if any(k not in ref for k in need):
                raise CouplingError(f"{self.model_id}: an implemented model needs a reference with {need}")
            files = ref["files"]
            if not isinstance(files, Mapping) or not files or any(not HEX64.match(str(v)) for v in files.values()):
                raise CouplingError(f"{self.model_id}: reference.files must map paths to 64-hex sha256")
            if ref["source_sha256"] != tree_sha256(files):
                raise CouplingError(f"{self.model_id}: reference.source_sha256 does not match its files")
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
                "source": p.bounds.source, "status": p.bounds.status},
            "caveat": p.caveat}


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
                     "provenance", "bounds", "caveat"}:
            raise CouplingError(f"unknown port keys in {q.get('name')}")
        b = q.get("bounds")
        ports.append(Port(
            q["name"], q["direction"], q["quantity"], q["kind"], q["unit"],
            None if q["dim"] is None else {u: int(q["dim"][u]) for u in BASE_UNITS},
            q["scale"], q["regime"], q["context"],
            Provenance(**q["provenance"]),
            None if b is None else Bounds(_f(b["lo"]), _f(b["hi"]), b["source"], b["status"]),
            q.get("caveat", "")))
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

    if kind == "assumed":
        checks["validity"] = ("NOT established: consistent dimensions are necessary, not sufficient; this mapping "
                              "is valid only under the named assumptions")

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
        elif kind == "assumed" and not [g for g in scope_gaps if g.startswith(("scale", "context"))]:
            checks["scope"] = "scenario: " + "; ".join(scope_gaps)
            downgrade.append("regime differs (" + "; ".join(scope_gaps) + ") and is bridged only by assumption")
            missing.append(f"{c.from_ref} -> {c.to_ref}: calibration bridging " + "; ".join(scope_gaps))
        elif kind == "assumed":
            checks["scope"] = "fail: " + "; ".join(scope_gaps)
            refuse.append("an assumption cannot stand in for a transfer across biological scale or context "
                          "(that needs a calibration): " + "; ".join(scope_gaps))
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

    # ---- port caveats: a proxy or declared quantity cannot be composed by identity / unit conversion
    cav = [f"{ref}.{pt_.name}: {pt_.caveat}" for ref, pt_ in ((c.from_ref.split(".")[0], pf), (c.to_ref.split(".")[0], pt))
           if pt_.caveat]
    if cav and kind in ("identity", "unit_conversion"):
        checks["caveats"] = "scenario: " + " | ".join(cav)
        downgrade.append("port caveat (needs a calibration to be composable): " + " | ".join(cav))
    else:
        checks["caveats"] = ("noted: " + " | ".join(cav)) if cav else "none"

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


def verify_reference_sources(m: ModelSpec, git_dir) -> dict:
    """Recompute every file hash in `m.reference` from the commit in a local git object store. Reads code; runs
    nothing. {"ok": bool|None, ...}: ok is None when the commit is not in this store (not verified, not failed)."""
    import subprocess
    if m.status == "proposed":
        return {"model": m.model_id, "ok": None, "reason": "proposed: no source"}
    ref, bad, missing = m.reference, [], []
    for path, want in ref["files"].items():
        r = subprocess.run(["git", "-C", str(git_dir), "show", f"{ref['commit']}:{path}"], capture_output=True)
        if r.returncode != 0:
            missing.append(path)
        elif hashlib.sha256(r.stdout).hexdigest() != want:
            bad.append(path)
    if missing and not bad:
        return {"model": m.model_id, "ok": None, "reason": "commit or path not in this object store", "missing": missing}
    return {"model": m.model_id, "ok": not bad and not missing, "mismatched": bad, "missing": missing}


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


# ---- the registry of models that exist today: ports read from the CODE at the exact commits below ------------------

FRONTIER = "kganjam/delphi-frontier"


def _ref(branch, commit, files, extra=None, repo=FRONTIER, read_by="dx-guilds, read from the source at this commit"):
    ref = {"repo": repo, "branch": branch, "commit": commit, "path": ", ".join(sorted(files)),
           "files": dict(files), "source_sha256": tree_sha256(files), "read_by": read_by}
    ref.update(extra or {})
    return ref


FILES = {
    "constraints": {
    "engineering/constraints.py":
        "de0acf47ffc7ffbebe5a44d775e007e87b7f4a996256b6c94fc0e188a0fcead1",
},
    "glide": {
    "engineering/simulation/schema.py":
        "94b4f003be514ac5055ed184b0e2695a68bf0de8689e387238e9583c8e62b944",
    "engineering/simulation/glide.py":
        "1f6a04baaf5a7cda589f80907ba00ac93f5b20fd458211a2340f3ec44de79fa7",
    "engineering/simulation/evaluate.py":
        "0a793951b8812a9093a637c61d79f3f4fea5e93f07a92825e46601c8e84357fc",
},
    "rd": {
    "engineering/simulation/rd_frames.py":
        "ee4ed03de805265bfbd1f7673a10b8b2d6eff2a71e0609d86a3e036796a85d12",
    "engineering/simulation/rd/receipt.json":
        "a3af348c151336721c4f844028b0f7f585e02c34684bc8cdcc085bd0dc4048dc",
    "engineering/simulation/rd/cells.json":
        "f74184cb56ba36e4face9978c96c2c00ae728a471183294c3f9d866eb066d6b6",
},
    "collier": {
    "connectors/biomodels/replay.py":
        "c9c017e6fd76aedcce2822de39c77a22349bea560dabc8ca432954f9d1938a8f",
    "connectors/biomodels/sbml.py":
        "eda0dcf677cd6d7786e84c0180bec075bc6dbefaa04e7cdcaa0d48c2604d40a8",
    "connectors/biomodels/client.py":
        "36e7bbcc93fb7102458fa43ecab9aa07bf775787577ef9f820ffb64b0691eea6",
    "connectors/biomodels/receipts/BIOMD0000001047/receipt.json":
        "731a85a6fe893bd10f86196b5fd7101a64810d0d68ae03ebfa4eee3d2e04bc6e",
},
    "fin_bridge": {
    "engineering/fin_mechanics/load_bridge.py":
        "743d85121d2804fbed690a310d31f7ac7eec7fab9c8b06e776eee30fb4a97a11",
},
    "fin_beam": {
    "engineering/fin_mechanics/beam.py":
        "4dfceb004a2eddef9cad27f09b744710de2a8b9b7f9f9e232b756e3cb4683b5d",
    "engineering/fin_mechanics/sweep.py":
        "17e2e1835d9f67c47b68e8285ae118b1b585c4d2b9a955bd13c598fbc498fa6e",
},
}

FISH_CTX = "Exocoetidae design envelope (Fish 1990 m / wing-loading range)"
FISH_RG = "point-mass vertical-plane flight; Reynolds/scale validity of the polar not established"
FIN_RG = ("static clamped-free Euler-Bernoulli ray, small deflection; the load is a mean lift-pressure PROXY, "
          "not a measured fin pressure")
RD_RG = "1-D zero-flux (Neumann) field; domain length in units of the model's own critical wavelength"
RD_CTX = "abstract kinetics; no organism"
CELL_RG = "two coupled cells; non-dimensional as stored; no time scale"
CELL_CTX = "NCBI taxon 7215 as annotated in the SBML (name unresolved by the connector owner)"
SIM = Provenance("simulated", "simulated", "none")
PA = dim(kg=1, m=-1, s=-2)        # Pa
NPM = dim(kg=1, s=-2)             # N/m
NM2 = dim(kg=1, m=3, s=-2)        # N m^2


CAV_LEVEL = "speed from the level-flight proxy (L = W); not a measured or glide-derived flight speed"
CAV_PROXY = "derived from a mean lift-pressure PROXY (0.5*rho*V^2*CL) and a declared width; not a measured ray load"
CAV_DECL = "a DECLARED fraction/length, not a measurement"
CAV_EI = "ASSUMED stiffness range; no calibrated fin stiffness exists"


def _p(name, direction, quantity, kind, unit, d, scale, regime, context, prov, bounds=None, caveat=""):
    return Port(name, direction, quantity, kind, unit, d, scale, regime, context, prov, bounds, caveat)


def default_registry() -> Registry:
    """Six models and five assumptions. Ports are read from the SOURCE at the commits in each reference (file hashes
    are recomputed by verify_reference_sources); the owners' hand-off notes were used only to locate the code."""
    reg = Registry()
    mass_bounds = Bounds(Fraction(3, 1000), Fraction(53, 100), "Fish 1990 p.393 specimen range", "measured")
    reg.add_model(ModelSpec(
        "flying_fish_constraints", "Exact-rational constraint solver (mass, wing area, span, speed)", "z3 5.3.3.0",
        "implemented", _ref("work/guilds-engineering", "948c2e1", FILES["constraints"], read_by="dx-guilds (author)"),
        (_p("m", "out", "body mass", "dimensional", "kg", dim(kg=1), "organism", FISH_RG, FISH_CTX,
            Provenance("solver witness; envelope Fish 1990 p.393", "assumed", "full-text"), mass_bounds),
         _p("S", "out", "wing area", "dimensional", "m^2", dim(m=2), "organism", FISH_RG, FISH_CTX,
            Provenance("solver witness", "assumed", "none")),
         _p("b", "out", "wing span", "dimensional", "m", dim(m=1), "organism", FISH_RG, FISH_CTX,
            Provenance("solver witness", "assumed", "none")),
         _p("V", "out", "speed at the level-flight proxy", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
            FISH_CTX, Provenance("solver witness; level-flight proxy L=W", "assumed", "none"), caveat=CAV_LEVEL)),
        Timescale("static", None, "a design point: the solver has no dynamics"),
        "exact-rational feasibility of declared constraints; a level-flight proxy, not a glide analysis",
        ("organism feasibility", "glide performance", "that any witness is a viable fish"),
        {"entrypoint": "engineering.constraints.solve", "deterministic": True}))
    reg.add_model(ModelSpec(
        "glide_pointmass", "Point-mass glide simulation (RK4)", "numpy RK4", "implemented",
        _ref("work/nca-glide", "87e72f9", FILES["glide"]),
        (_p("m", "in", "body mass", "dimensional", "kg", dim(kg=1), "organism", FISH_RG, FISH_CTX,
            Provenance("candidate from the constraint solver (schema.parse_candidate)", "assumed", "file"), mass_bounds),
         _p("S", "in", "wing area", "dimensional", "m^2", dim(m=2), "organism", FISH_RG, FISH_CTX,
            Provenance("candidate", "assumed", "file")),
         _p("b", "in", "wing span", "dimensional", "m", dim(m=1), "organism", FISH_RG, FISH_CTX,
            Provenance("candidate", "assumed", "file")),
         _p("release_speed", "in", "release speed", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
            FISH_CTX, Provenance("evaluate.py: default 1.5 x stall speed; the witness V is used only when "
                                 "release_speed_from_witness is set", "assumed", "file")),
         _p("rho", "in", "air density", "dimensional", "kg/m^3", dim(kg=1, m=-3), "organism", FISH_RG, FISH_CTX,
            Provenance("flight_assumptions.rho: design assumption, schema bound (0, 2)", "assumed", "file")),
         _p("CL_max", "in", "maximum usable lift coefficient", "dimensionless", "1", dim(), "organism", FISH_RG,
            FISH_CTX, Provenance("flight_assumptions.CL_max: design assumption, schema bound (0, 3)", "assumed", "file")),
         _p("glide_range", "out", "horizontal glide range", "dimensional", "m", dim(m=1), "organism", FISH_RG,
            FISH_CTX, Provenance("simulated; CD0/e/CL_max are declared priors, not measurements", "simulated", "file")),
         _p("sink_rate", "out", "equilibrium sink rate", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
            FISH_CTX, SIM)),
        Timescale("unknown", None, "glide duration is an output; no characteristic time is declared"),
        "point-mass flight with declared drag/lift priors (priors, not measurements); controlled-launch comparison exists",
        ("biological feasibility", "fin-tissue coupling", "calibrated lift/drag for any fish (Park & Choi 2010 unread)"),
        {"entrypoint": "engineering.simulation.evaluate.evaluate", "deterministic": True,
         "schema": "frontier.glide.candidate/1"}))
    reg.add_model(ModelSpec(
        "fin_load_bridge", "Load bridge: declared flight load -> line load on one fin ray (exact rational)",
        "python Fraction", "implemented", _ref("work/fin-mechanics", "72df07c", FILES["fin_bridge"]),
        (_p("b", "in", "wing span", "dimensional", "m", dim(m=1), "organism", FISH_RG, FISH_CTX,
            Provenance("candidate witness.b (load_bridge.bridge)", "assumed", "file")),
         _p("V", "in", "speed at the level-flight proxy", "dimensional", "m/s", dim(m=1, s=-1), "organism", FISH_RG,
            FISH_CTX, Provenance("candidate witness.V used as the flight speed", "assumed", "file"), caveat=CAV_LEVEL),
         _p("rho", "in", "air density", "dimensional", "kg/m^3", dim(kg=1, m=-3), "organism", FISH_RG, FISH_CTX,
            Provenance("flight_assumptions.rho: design assumption", "assumed", "file")),
         _p("CL", "in", "lift coefficient", "dimensionless", "1", dim(), "organism", FISH_RG, FISH_CTX,
            Provenance("CL_max or fin.CL override: design assumption", "assumed", "file"),
            Bounds(None, Fraction(3), "load_bridge refuses CL outside (0, 3]", "assumed")),
         _p("ray_length_fraction", "in", "ray length / semispan", "dimensionless", "1", dim(), "organ", FIN_RG,
            FISH_CTX, Provenance("fin.ray_length_fraction_of_semispan: DECLARED", "assumed", "file"),
            Bounds(None, Fraction(1), "load_bridge refuses a fraction > 1", "assumed")),
         _p("tributary_width", "in", "tributary width per ray", "dimensional", "m", dim(m=1), "organ", FIN_RG,
            FISH_CTX, Provenance("fin.tributary_width_m or b/n_rays: DECLARED", "assumed", "file")),
         _p("p_lift_proxy", "out", "mean lift-pressure proxy", "dimensional", "Pa", PA, "organ", FIN_RG, FISH_CTX,
            Provenance("0.5*rho*V^2*CL: a proxy, not a measured fin pressure", "assumed", "file"), caveat=CAV_PROXY),
         _p("q_line", "out", "line load on one fin ray", "dimensional", "N/m", NPM, "organ", FIN_RG, FISH_CTX,
            Provenance("p_lift_proxy * tributary_width (declared width)", "assumed", "file"), caveat=CAV_PROXY),
         _p("L_ray", "out", "fin ray length", "dimensional", "m", dim(m=1), "organ", FIN_RG, FISH_CTX,
            Provenance("ray_length_fraction * b / 2 (declared fraction)", "assumed", "file"), caveat=CAV_DECL)),
        Timescale("static", None, "algebra: no time dependence"),
        "exact derivation of a line load from DECLARED rho, V, CL, ray fraction and tributary width",
        ("a measured fin pressure", "fluid-structure interaction", "that the tributary width or ray length is real",
         "that p*S balances weight (reported, not enforced)"),
        {"entrypoint": "engineering.fin_mechanics.load_bridge.bridge", "deterministic": True,
         "schema": "frontier.finmech.request/1"}))
    reg.add_model(ModelSpec(
        "finbeam_euler_bernoulli", "Elastic fin-ray surrogate: clamped-free Euler-Bernoulli cantilever (SIMULATED)",
        "numpy + scipy.sparse Hermite-cubic FEM", "implemented", _ref("work/fin-mechanics", "72df07c", FILES["fin_beam"]),
        (_p("q_line", "in", "line load on one fin ray", "dimensional", "N/m", NPM, "organ", FIN_RG, FISH_CTX,
            Provenance("uniform line load from the load bridge (or the same force at the tip)", "assumed", "file"), caveat=CAV_PROXY),
         _p("L_ray", "in", "fin ray length", "dimensional", "m", dim(m=1), "organ", FIN_RG, FISH_CTX,
            Provenance("from the load bridge", "assumed", "file"), caveat=CAV_DECL),
         _p("flexural_rigidity", "in", "fin ray flexural rigidity EI", "dimensional", "N m^2", NM2, "organ", FIN_RG,
            FISH_CTX, Provenance("elastic.EI_status = ASSUMED_RANGE_NOT_MEASURED; bluegill 1e-6..1e-5 J m (Alben et "
                                 "al. 2007) is context only, read through a summarising tool", "assumed", "none"),
            Bounds(Fraction(1, 10**6), Fraction(1), "example_request.json assumed sweep range", "assumed"), caveat=CAV_EI),
         _p("tip_deflection", "out", "tip deflection under load", "dimensional", "m", dim(m=1), "organ", FIN_RG,
            FISH_CTX, SIM),
         _p("critical_stiffness", "out", "EI below which the declared load breaks the small-deformation limits",
            "dimensional", "N m^2", NM2, "organ", FIN_RG, FISH_CTX, SIM)),
        Timescale("static", None, "static problem: no time step"),
        "linear static beam with an ASSUMED stiffness range; no shear, no bilaminar structure, load uncoupled to deformation",
        ("a calibrated fin stiffness", "that any real ray lies in the assumed EI range", "fluid-structure interaction",
         "biological feasibility"),
        {"entrypoint": "engineering.fin_mechanics.sweep", "deterministic": True,
         "schema": "frontier.finmech.request/1"}))
    reg.add_model(ModelSpec(
        "rdfield_nonlinear_sweep", "Reaction-diffusion field (Schnakenberg, Brusselator): saved-state rerun",
        "numpy Strang splitting + DCT-II diffusion + RK4", "implemented",
        _ref("work/nca-glide", "87e72f9", FILES["rd"], extra={
            "upstream_repo": "kganjam/delphi-evolve", "upstream_branch": "work/rethink-nca",
            "upstream_prereg_commit": "cb27cf24521b7eb77f784bc266d2f3f584f049ff", "upstream_results_commit": "1067cdb",
            "upstream_rows_sha256": "a32c2bf7dd3c10162317974ae6a0ecbefa06c1c180a6886dea1bcb8ea4d4c882",
            "note": "rd_frames.py is pinned-source reuse of solver A; rd/receipt.json compares two reruns with frozen rows"}),
        (_p("L_over_lambda_c", "in", "domain length / critical wavelength", "dimensionless", "1", dim(), "tissue",
            RD_RG, RD_CTX, Provenance("sweep design", "assumed", "file")),
         _p("kinetic_parameters", "in", "kinetic parameters", "model_units", "model units", None, "tissue", RD_RG,
            RD_CTX, Provenance("published ranges or a stated prior", "assumed", "file")),
         _p("dominant_mode", "out", "dominant mode number", "dimensionless", "1", dim(), "tissue", RD_RG, RD_CTX, SIM),
         _p("pattern_flag", "out", "pattern / no pattern / not settled", "dimensionless", "1", dim(), "tissue", RD_RG,
            RD_CTX, SIM)),
        Timescale("unknown", None, "tau = gamma*t is dimensionless model time, unrelated to glide seconds"),
        "numerical rerun of two frozen sweep cells with every saved state kept; textbook kinetics only",
        ("any fin or fish tissue", "SI length or time scales", "that a real tissue obeys these kinetics"),
        {"entrypoint": "engineering.simulation.rd_frames", "deterministic": True}))
    reg.add_model(ModelSpec(
        "collier1996_two_cell", "Collier 1996 two-cell Delta-Notch lateral inhibition (BIOMD0000001047)",
        "libroadrunner 2.10.0 (CVODE)", "implemented_replayed",
        _ref("work/biomodels", "abf1838", FILES["collier"], extra={
            "sbml_sha256": "da21ab52edba14b61e41ee87df7a8bb2f367a1206e6e822602f1e75271fae8e2",
            "note": "the SBML bytes are not committed; the receipt pins this digest"}),
        (_p("parameters_a_b_h_k", "in", "feedback parameters", "model_units", "model units", None, "cell", CELL_RG,
            CELL_CTX, Provenance("values stored in the SBML (a 0.01, b 100, h 2, k 2, mu 1, rho 1); paper not read",
                                 "unknown", "file")),
         _p("delta_asymmetry", "out", "Delta level difference between the two cells", "model_units", "model units",
            None, "cell", CELL_RG, CELL_CTX,
            Provenance("simulated (replay._asym over delta1, delta2); horizon 0-60 chosen by the connector", "simulated", "file"))),
        Timescale("unknown", None, "the file declares none; horizon 0-60 is the connector's"),
        "a published model replayed as written; the replay checks the engine, not the file's fidelity to the paper",
        ("any flying-fish or fin role for Notch/Delta", "SI units", "parameter provenance"),
        {"entrypoint": "connectors.biomodels.replay.replay_collier1996", "deterministic": True}))
    reg.add_assumption(Assumption(
        "A1", "glide release speed equals the constraint solver's witness V (the glide model's own default is 1.5 x stall speed)",
        "assumption", "dx-guilds"))
    reg.add_assumption(Assumption(
        "A2", "Notch/Delta lateral-inhibition spacing from a two-cell non-dimensional model sets fin-ray stiffness scale (NO source supports this)",
        "assumption", "dx-guilds"))
    reg.add_assumption(Assumption(
        "A3", "the mean lift-pressure proxy p = 0.5*rho*V^2*CL, built from declared rho, V and CL, is the pressure carried by one fin ray "
              "(it is not a measured fin pressure; V is the solver's level-flight-proxy speed)", "assumption", "dx-guilds"))
    reg.add_assumption(Assumption(
        "A4", "ray length fraction and tributary width are declared values, not measurements (fin_mechanics example: 1/5 of the semispan, 1/100 m)",
        "assumption", "dx-guilds"))
    reg.add_assumption(Assumption(
        "A5", "the flexural-rigidity range is ASSUMED, not measured or calibrated: no calibrated fin stiffness exists in this repository",
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
                 factor=Fraction(1), factor_dim=NM2, time_relation="unknown", uncertainty_kind="unknown",
                 note="an assumption cannot stand in for a cross-scale, cross-taxon transfer"),
        Coupling("c07_rd_wavelength_to_wing_span", "rdfield_nonlinear_sweep.dominant_mode", "glide_pointmass.b",
                 mapping_kind="none", note="a mode number is dimensionless; the span is in metres; no length scale"),
        Coupling("c08_fin_deflection_to_glide_speed", "finbeam_euler_bernoulli.tip_deflection",
                 "glide_pointmass.release_speed", mapping_kind="none",
                 note="needs camber -> CL/CD (Park & Choi 2010 tables, PDF not yet read by anyone)"),
        Coupling("c09_span_to_fin_bridge", "flying_fish_constraints.b", "fin_load_bridge.b",
                 note="the bridge reads witness.b as the span", **ident),
        Coupling("c10_speed_to_fin_bridge", "flying_fish_constraints.V", "fin_load_bridge.V",
                 mapping_kind="identity", assumption_ids=("A3",), time_relation="static_input", uncertainty_kind="exact",
                 note="SCENARIO: the bridge reads witness.V as the flight speed, but it is a level-flight-proxy speed"),
        Coupling("c11_load_proxy_to_beam", "fin_load_bridge.q_line", "finbeam_euler_bernoulli.q_line",
                 mapping_kind="identity", assumption_ids=("A3", "A4"), time_relation="static_input",
                 uncertainty_kind="unknown",
                 note="SCENARIO: same quantity and unit, but the load is a mean lift-pressure proxy times a declared "
                      "width; there is no calibrated fin stiffness and no measured ray pressure"),
        Coupling("c12_ray_length_to_beam", "fin_load_bridge.L_ray", "finbeam_euler_bernoulli.L_ray",
                 mapping_kind="identity", assumption_ids=("A4",), time_relation="static_input",
                 uncertainty_kind="unknown", note="SCENARIO: ray length is a declared fraction of the semispan"),
        Coupling("c13_pressure_to_line_load_dimension_only", "fin_load_bridge.p_lift_proxy",
                 "finbeam_euler_bernoulli.q_line", mapping_kind="assumed", assumption_ids=("A3", "A4"),
                 factor=Fraction(1, 100), factor_dim=dim(m=1), time_relation="static_input", uncertainty_kind="unknown",
                 note="Pa x m = N/m matches in dimension; that is necessary, NOT evidence that a ray carries the mean "
                      "pressure over this width. Scenario only."),
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
