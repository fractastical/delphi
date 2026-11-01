"""Fail-closed SBML inspection and an engine-independent evaluator for the supported subset.

Parsing uses the standard library only (no libsbml). The subset is deliberately small: anything
outside it raises `UnsupportedSBML` naming the construct, so a model is never run on the
assumption that an unread construct is harmless.

Supported: SBML Level 2/3 core; compartments; concentration-based species with constant
stoichiometry; parameters; function definitions; assignment rules; initial assignments;
reactions with kinetic laws using ci, cn, plus, minus, times, divide, power and user functions.

Refused: events, algebraic and rate rules, constraints, delays, `time`/`rateOf` symbols,
stoichiometryMath, boundary/constant species, amount-based species, packages marked required,
DOCTYPE/ENTITY declarations, and any MathML element not listed above.
"""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

MAX_NODES = 200_000


class UnsupportedSBML(ValueError):
    """The file uses a construct this connector will not run."""


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _kids(el, name):
    return [c for c in el if _local(c.tag) == name]


def _first(el, name):
    k = _kids(el, name)
    return k[0] if k else None


def _items(model, list_name, item):
    lst = _first(model, list_name)
    return _kids(lst, item) if lst is not None else []


# ---- MathML -> a small expression tree ----------------------------------------------------

_BINARY = {"plus", "times"}
_OPS = {"plus", "minus", "times", "divide", "power"}


def parse_math(math_el):
    kids = [c for c in math_el if isinstance(c.tag, str)]
    if len(kids) != 1:
        raise UnsupportedSBML("MathML block does not hold exactly one expression")
    return _expr(kids[0])


def _expr(el):
    tag = _local(el.tag)
    if tag == "cn":
        if el.get("type", "real") not in ("real", "integer") or any(_local(c.tag) == "sep" for c in el):
            raise UnsupportedSBML("cn of unsupported type (rational/e-notation)")
        return ("num", float((el.text or "").strip()))
    if tag == "ci":
        return ("sym", (el.text or "").strip())
    if tag == "apply":
        head, *args = [c for c in el if isinstance(c.tag, str)]
        h = _local(head.tag)
        if h == "ci":
            return ("call", (head.text or "").strip(), [_expr(a) for a in args])
        if h not in _OPS:
            raise UnsupportedSBML(f"MathML operator <{h}> is not supported")
        if h in ("minus",) and len(args) not in (1, 2) or h in ("divide", "power") and len(args) != 2:
            raise UnsupportedSBML(f"MathML <{h}> with {len(args)} arguments")
        return ("op", h, [_expr(a) for a in args])
    raise UnsupportedSBML(f"MathML element <{tag}> is not supported")


def evaluate(node, env, functions):
    kind = node[0]
    if kind == "num":
        return node[1]
    if kind == "sym":
        if node[1] not in env:
            raise UnsupportedSBML(f"symbol {node[1]!r} has no value in scope")
        return env[node[1]]
    if kind == "call":
        params, body = functions[node[1]]
        if len(params) != len(node[2]):
            raise UnsupportedSBML(f"function {node[1]} called with {len(node[2])} arguments")
        local = dict(zip(params, (evaluate(a, env, functions) for a in node[2])))
        return evaluate(body, local, functions)
    op, args = node[1], [evaluate(a, env, functions) for a in node[2]]
    if op == "plus":
        return math.fsum(args)
    if op == "times":
        out = 1.0
        for a in args:
            out *= a
        return out
    if op == "minus":
        return -args[0] if len(args) == 1 else args[0] - args[1]
    if op == "divide":
        return args[0] / args[1]
    return args[0] ** args[1]


def symbols(node, acc=None):
    acc = set() if acc is None else acc
    if node[0] == "sym":
        acc.add(node[1])
    elif node[0] == "call":
        acc.add(node[1])
        for a in node[2]:
            symbols(a, acc)
    elif node[0] == "op":
        for a in node[2]:
            symbols(a, acc)
    return acc


# ---- model ---------------------------------------------------------------------------------


@dataclass
class Reaction:
    id: str
    reactants: list[tuple[str, float]]
    products: list[tuple[str, float]]
    law: tuple
    local: dict[str, float]


@dataclass
class Model:
    id: str
    name: str
    level: int
    version: int
    compartments: dict[str, dict] = field(default_factory=dict)
    species: dict[str, dict] = field(default_factory=dict)
    parameters: dict[str, dict] = field(default_factory=dict)
    functions: dict[str, tuple] = field(default_factory=dict)
    assignment_rules: dict[str, tuple] = field(default_factory=dict)
    initial_assignments: dict[str, tuple] = field(default_factory=dict)
    reactions: list[Reaction] = field(default_factory=list)
    unit_definitions: dict[str, list[dict]] = field(default_factory=dict)
    model_units: dict[str, str | None] = field(default_factory=dict)
    annotations: list[dict] = field(default_factory=list)
    unit_notes: list[str] = field(default_factory=list)

    # -- evaluation --------------------------------------------------------------------------

    def initial_env(self, overrides: dict[str, float] | None = None) -> dict[str, float]:
        """Parameter, compartment and species values at t=0, with initial assignments applied.

        `overrides` replaces a declared value *before* initial assignments are evaluated, which is
        what a user changing `a` in the file would get; it is never applied silently.
        """
        env = {k: v["value"] for k, v in self.parameters.items() if v["value"] is not None}
        env.update({k: v["size"] for k, v in self.compartments.items()})
        env.update({k: v["initial_concentration"] for k, v in self.species.items()})
        env.update(overrides or {})
        for sym, node in self.initial_assignments.items():
            if overrides and sym in overrides:
                continue
            env[sym] = evaluate(node, env, self.functions)
        return env

    def apply_rules(self, env: dict[str, float]) -> None:
        pending = dict(self.assignment_rules)
        for _ in range(len(pending) + 1):
            if not pending:
                return
            for var, node in list(pending.items()):
                if all(s in env or s in self.functions for s in symbols(node)) and not (symbols(node) & set(pending)):
                    env[var] = evaluate(node, env, self.functions)
                    del pending[var]
        raise UnsupportedSBML(f"cyclic assignment rules: {sorted(pending)}")

    def rhs(self, state: dict[str, float], env: dict[str, float]) -> dict[str, float]:
        scope = dict(env)
        scope.update(state)
        self.apply_rules(scope)
        out = {s: 0.0 for s in self.species}
        for r in self.reactions:
            local = dict(scope)
            local.update(r.local)
            flux = evaluate(r.law, local, self.functions)
            for s, n in r.reactants:
                out[s] -= n * flux / self.compartments[self.species[s]["compartment"]]["size"]
            for s, n in r.products:
                out[s] += n * flux / self.compartments[self.species[s]["compartment"]]["size"]
        return out

    def initial_state(self, overrides=None) -> dict[str, float]:
        env = self.initial_env(overrides)
        return {s: env[s] for s in self.species}

    # -- the record --------------------------------------------------------------------------

    def inventory(self) -> dict:
        """Everything the replay preserves, with units exactly as declared (None = not declared)."""
        return {
            "model_id": self.id,
            "name": self.name,
            "sbml": f"L{self.level}V{self.version}",
            "compartments": self.compartments,
            "species": self.species,
            "parameters": self.parameters,
            "initial_assignments": sorted(self.initial_assignments),
            "assignment_rules": sorted(self.assignment_rules),
            "reactions": [r.id for r in self.reactions],
            "function_definitions": sorted(self.functions),
            "unit_definitions": self.unit_definitions,
            "model_level_units": self.model_units,
            "unit_notes": self.unit_notes,
            "annotations": self.annotations,
        }


_REQUIRED_PKG = re.compile(r"\{[^}]*\}required$")


def inspect_sbml(data: bytes) -> Model:
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise UnsupportedSBML("DOCTYPE/ENTITY declarations are refused")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise UnsupportedSBML(f"not well-formed XML: {exc}") from exc
    if _local(root.tag) != "sbml":
        raise UnsupportedSBML("root element is not <sbml>")
    if sum(1 for _ in root.iter()) > MAX_NODES:
        raise UnsupportedSBML("document exceeds the node bound")
    level, version = int(root.get("level", "0")), int(root.get("version", "0"))
    if level not in (2, 3):
        raise UnsupportedSBML(f"SBML Level {level} is not supported")
    for key, value in root.attrib.items():
        if _REQUIRED_PKG.match(key) and value == "true":
            raise UnsupportedSBML(f"package {key} is marked required")
    model_el = _first(root, "model")
    if model_el is None:
        raise UnsupportedSBML("no <model>")
    for tag in ("event", "constraint"):
        if any(_local(e.tag) == tag for e in model_el.iter()):
            raise UnsupportedSBML(f"<{tag}> is not supported")
    for e in model_el.iter():
        t = _local(e.tag)
        if t == "csymbol":
            raise UnsupportedSBML(f"MathML csymbol {e.get('definitionURL')!r} (time/delay/rateOf) is not supported")
        if t in ("stoichiometryMath", "algebraicRule", "rateRule"):
            raise UnsupportedSBML(f"<{t}> is not supported")

    m = Model(model_el.get("id", ""), model_el.get("name", ""), level, version)
    m.model_units = {u: model_el.get(f"{u}Units") for u in ("substance", "time", "volume", "area", "length", "extent")}

    for ud in _items(model_el, "listOfUnitDefinitions", "unitDefinition"):
        m.unit_definitions[ud.get("id")] = [
            {k: u.get(k) for k in ("kind", "exponent", "scale", "multiplier")}
            for u in _kids(_first(ud, "listOfUnits"), "unit")
        ]
    for c in _items(model_el, "listOfCompartments", "compartment"):
        m.compartments[c.get("id")] = {
            "name": c.get("name"), "size": float(c.get("size", "nan")),
            "units": c.get("units"), "spatial_dimensions": c.get("spatialDimensions"),
        }
        if math.isnan(m.compartments[c.get("id")]["size"]) or not c.get("constant", "true") == "true":
            raise UnsupportedSBML(f"compartment {c.get('id')} has no size or is not constant")
    for s in _items(model_el, "listOfSpecies", "species"):
        sid = s.get("id")
        if s.get("initialConcentration") is None or s.get("initialAmount") is not None:
            raise UnsupportedSBML(f"species {sid}: only initialConcentration is supported")
        if s.get("hasOnlySubstanceUnits", "false") == "true" or s.get("boundaryCondition", "false") == "true" or s.get("constant", "false") == "true":
            raise UnsupportedSBML(f"species {sid}: substance-only, boundary or constant species are not supported")
        m.species[sid] = {
            "name": s.get("name"), "compartment": s.get("compartment"),
            "initial_concentration": float(s.get("initialConcentration")),
            "substance_units": s.get("substanceUnits"), "boundary": False,
        }
    for p in _items(model_el, "listOfParameters", "parameter"):
        m.parameters[p.get("id")] = {
            "name": p.get("name"), "value": float(p.get("value")) if p.get("value") is not None else None,
            "units": p.get("units"), "constant": p.get("constant", "true") == "true", "sbo": p.get("sboTerm"),
        }
    for fd in _items(model_el, "listOfFunctionDefinitions", "functionDefinition"):
        lam = _first(_first(fd, "math"), "lambda")
        if lam is None:
            raise UnsupportedSBML(f"function {fd.get('id')} is not a lambda")
        parts = [c for c in lam if isinstance(c.tag, str)]
        params = [(_first(b, "ci").text or "").strip() for b in parts if _local(b.tag) == "bvar"]
        body = [c for c in parts if _local(c.tag) != "bvar"]
        if len(body) != 1:
            raise UnsupportedSBML(f"function {fd.get('id')} has no single body")
        m.functions[fd.get("id")] = (params, _expr(body[0]))
    for r in _items(model_el, "listOfRules", "assignmentRule"):
        m.assignment_rules[r.get("variable")] = parse_math(_first(r, "math"))
    for ia in _items(model_el, "listOfInitialAssignments", "initialAssignment"):
        m.initial_assignments[ia.get("symbol")] = parse_math(_first(ia, "math"))
    for rx in _items(model_el, "listOfReactions", "reaction"):
        law = _first(rx, "kineticLaw")
        if law is None:
            raise UnsupportedSBML(f"reaction {rx.get('id')} has no kinetic law")
        local = {
            p.get("id"): float(p.get("value"))
            for lst, item in (("listOfParameters", "parameter"), ("listOfLocalParameters", "localParameter"))
            for p in _items(law, lst, item)
        }
        refs = {}
        for side, tag in (("reactants", "listOfReactants"), ("products", "listOfProducts")):
            refs[side] = []
            for sr in _items(rx, tag, "speciesReference"):
                if sr.get("species") not in m.species:
                    raise UnsupportedSBML(f"reaction {rx.get('id')} references unknown or unsupported species {sr.get('species')}")
                refs[side].append((sr.get("species"), float(sr.get("stoichiometry", "1"))))
        m.reactions.append(Reaction(rx.get("id"), refs["reactants"], refs["products"], parse_math(_first(law, "math")), local))

    known = set(m.parameters) | set(m.compartments) | set(m.species)
    for r in m.reactions:
        for s in symbols(r.law) - known - set(r.local) - set(m.functions):
            raise UnsupportedSBML(f"reaction {r.id}: symbol {s!r} is undefined")
    if not m.reactions:
        raise UnsupportedSBML("model has no reactions")

    rdf = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
    for desc in model_el.iter():
        if _local(desc.tag) != "Description":
            continue
        for q in desc:
            for li in q.iter():
                if _local(li.tag) == "li" and li.get(rdf + "resource"):
                    m.annotations.append({"about": desc.get(rdf + "about"), "qualifier": _local(q.tag), "resource": li.get(rdf + "resource")})
    referenced = {x for coll in (m.compartments, m.species, m.parameters) for v in coll.values() for x in (v.get("units"), v.get("substance_units")) if x}
    if not referenced and not any(m.model_units.values()):
        m.unit_notes.append(
            "No compartment, species or parameter references a unit and no model-level unit is set. "
            "The file declares unitDefinitions for the SBML Level 2 defaults (second, mole, litre, "
            "metre) that apply by omission; they are not a statement that these quantities are in "
            "those units. No SI quantity is asserted."
        )
    return m
