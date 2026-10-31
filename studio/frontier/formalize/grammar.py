"""Bounded declarative grammar for typed autoformalization proposals (frontier.formalize.request/1).

Nothing here executes model-supplied content.  Terms are JSON data, validated against a fixed grammar and
turned into exact-rational polynomials.  There is no eval/exec/compile, no function calls, no strings that
are interpreted other than as (a) a rational literal matched by a strict regex or (b) a declared symbol name.

Term grammar (contract director-to-codex03-formalize-contract.md):
    term := rational-literal | symbol
          | {"op": "+"|"-"|"*", "args": [term, ...]}      ("-" with one argument is negation)
          | {"op": "/", "args": [term, rational-literal]}   (division by a NONZERO constant only)
          | {"op": "pow", "base": symbol, "exp": int 0..4}
    constraint expr := {"op": "<"|"<="|">"|">="|"==", "lhs": term, "rhs": term}
Extension (not in the contract text, documented in docs/autoformalization.md): a symbol may carry
"integer": true, which restricts it to integer values (used for sequence counts).
"""
from __future__ import annotations

import hashlib
import json
import re
from fractions import Fraction

SCHEMA_REQUEST = "frontier.formalize.request/1"
SCHEMA_RESPONSE = "frontier.formalize.response/1"
SCHEMA_ERROR = "frontier.formalize.error/1"
LIMITS = {"timeout_s": 8, "max_bytes": 16384, "max_nodes": 64}
MAX_SYMBOLS, MAX_CONSTRAINTS, MAX_ASSUMPTIONS, MAX_TEXT = 16, 32, 32, 1000
COMPARISONS = ("<", "<=", ">", ">=", "==")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")
ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,32}$")
LIT_RE = re.compile(r"^[+-]?(\d{1,30}(\.\d{1,30})?([eE][+-]?\d{1,2})?|\d{1,30}/\d{1,30})$")


class GrammarError(Exception):
    """Structural violation; `code` is a frontier.formalize.error/1 code."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_obj(obj) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def parse_literal(x, where="literal") -> Fraction:
    if isinstance(x, bool) or isinstance(x, float):
        raise GrammarError("unsupported_expression", f"{where}: JSON booleans/floats are refused; use an integer or a decimal/'p/q' string")
    if isinstance(x, int):
        if abs(x) > 10**30:
            raise GrammarError("unsupported_expression", f"{where}: integer too large")
        return Fraction(x)
    if isinstance(x, str) and LIT_RE.match(x.strip()):
        try:
            return Fraction(x.strip())
        except (ZeroDivisionError, ValueError):                   # "1/0" matches the literal shape but is not a number
            raise GrammarError("unsupported_expression", f"{where}: not an exact rational literal (zero denominator)") from None
    raise GrammarError("unsupported_expression", f"{where}: not an exact rational literal")


def is_literal(x) -> bool:
    return (isinstance(x, int) and not isinstance(x, bool)) or (isinstance(x, str) and bool(LIT_RE.match(x.strip())))


def _only(obj: dict, allowed: set, where: str):
    extra = set(obj) - allowed
    if extra:
        raise GrammarError("unknown_field", f"{where}: unknown field(s) {sorted(extra)}")


# ---------------------------------------------------------------- polynomial arithmetic (exact)
class Poly:
    """Sparse multivariate polynomial over Q: {exponent-tuple (ordered by symbol list): Fraction}."""

    def __init__(self, n: int, terms: dict | None = None):
        self.n, self.t = n, {k: v for k, v in (terms or {}).items() if v != 0}

    @staticmethod
    def const(n, c):
        return Poly(n, {(0,) * n: Fraction(c)})

    @staticmethod
    def var(n, i):
        e = [0] * n
        e[i] = 1
        return Poly(n, {tuple(e): Fraction(1)})

    def __add__(self, o):
        r = dict(self.t)
        for k, v in o.t.items():
            r[k] = r.get(k, 0) + v
        return Poly(self.n, r)

    def __neg__(self):
        return Poly(self.n, {k: -v for k, v in self.t.items()})

    def __sub__(self, o):
        return self + (-o)

    def __mul__(self, o):
        r = {}
        for k1, v1 in self.t.items():
            for k2, v2 in o.t.items():
                k = tuple(a + b for a, b in zip(k1, k2))
                r[k] = r.get(k, 0) + v1 * v2
        return Poly(self.n, r)

    def scale(self, c):
        return Poly(self.n, {k: v * c for k, v in self.t.items()})

    def pow(self, e: int):
        r = Poly.const(self.n, 1)
        for _ in range(e):
            r = r * self
        return r

    def degree_in(self, i):
        return max((k[i] for k in self.t), default=0)

    def total_degree(self):
        return max((sum(k) for k in self.t), default=0)

    def eval(self, pt: list) -> Fraction:
        s = Fraction(0)
        for k, v in self.t.items():
            m = v
            for x, e in zip(pt, k):
                if e:
                    m *= x ** e
            s += m
        return s

    def is_zero(self):
        return not self.t


# ---------------------------------------------------------------- term validation
def check_term(term, names: set, budget: list, where: str):
    """Validate one term; raises GrammarError.  `budget` is a one-element list counting nodes left."""
    budget[0] -= 1
    if budget[0] < 0:
        raise GrammarError("unsupported_expression", f"{where}: more than {LIMITS['max_nodes']} nodes")
    if isinstance(term, dict):
        op = term.get("op")
        if op in ("+", "-", "*"):
            _only(term, {"op", "args"}, where)
            args = term.get("args")
            if not isinstance(args, list) or not (1 <= len(args) <= LIMITS["max_nodes"]) or (op != "-" and len(args) < 2):
                raise GrammarError("unsupported_expression", f"{where}: op {op} needs a list of args ('-' may take one)")
            for a in args:
                check_term(a, names, budget, where)
        elif op == "/":
            _only(term, {"op", "args"}, where)
            args = term.get("args")
            if not isinstance(args, list) or len(args) != 2 or not is_literal(args[1]) or parse_literal(args[1], where) == 0:
                raise GrammarError("unsupported_expression", f"{where}: '/' takes [term, nonzero rational literal]")
            check_term(args[0], names, budget, where)
            budget[0] -= 1
        elif op == "pow":
            _only(term, {"op", "base", "exp"}, where)
            b, e = term.get("base"), term.get("exp")
            if not (isinstance(b, str) and b in names):
                raise GrammarError("unsupported_expression", f"{where}: pow base must be a declared symbol")
            if isinstance(e, bool) or not isinstance(e, int) or not 0 <= e <= 4:
                raise GrammarError("unsupported_expression", f"{where}: pow exp must be an integer 0..4")
            budget[0] -= 1
        else:
            raise GrammarError("unsupported_expression", f"{where}: operator {str(op)[:20]!r} is not in the grammar (no functions)")
        return
    if is_literal(term):
        parse_literal(term, where)
        return
    if isinstance(term, str) and term in names:
        return
    raise GrammarError("unsupported_expression", f"{where}: {str(term)[:30]!r} is neither a rational literal nor a declared symbol")


def to_poly(term, index: dict) -> Poly:
    n = len(index)
    if isinstance(term, dict):
        op = term["op"]
        if op == "+":
            r = Poly(n)
            for a in term["args"]:
                r = r + to_poly(a, index)
            return r
        if op == "-":
            a = [to_poly(x, index) for x in term["args"]]
            if len(a) == 1:
                return -a[0]
            r = a[0]
            for x in a[1:]:
                r = r - x
            return r
        if op == "*":
            r = Poly.const(n, 1)
            for a in term["args"]:
                r = r * to_poly(a, index)
            return r
        if op == "/":
            return to_poly(term["args"][0], index).scale(1 / parse_literal(term["args"][1]))
        if op == "pow":
            return Poly.var(n, index[term["base"]]).pow(term["exp"])
    if is_literal(term):
        return Poly.const(n, parse_literal(term))
    return Poly.var(n, index[term])


def term_to_text(term) -> str:
    """Human-readable infix rendering (display only; never parsed back)."""
    if isinstance(term, dict):
        op = term["op"]
        if op == "pow":
            return f"{term['base']}^{term['exp']}"
        if op == "/":
            return f"({term_to_text(term['args'][0])}/{term['args'][1]})"
        if op == "-" and len(term["args"]) == 1:
            return f"-{term_to_text(term['args'][0])}"
        return "(" + f" {op} ".join(term_to_text(a) for a in term["args"]) + ")"
    return str(term)


# ---------------------------------------------------------------- request validation
def validate_request(req) -> dict:
    """Structural validation. Returns a normalised context dict or raises GrammarError."""
    if not isinstance(req, dict):
        raise GrammarError("unsupported_expression", "request must be a JSON object")
    size = len(canonical(req))
    if size > LIMITS["max_bytes"]:
        raise GrammarError("request_too_large", f"{size} bytes > {LIMITS['max_bytes']}")
    _only(req, {"schema", "claim", "proposal", "options"}, "request")
    if req.get("schema") != SCHEMA_REQUEST:
        raise GrammarError("unsupported_expression", f"schema must be {SCHEMA_REQUEST}")
    claim, prop = req.get("claim"), req.get("proposal")
    if not isinstance(claim, dict) or not isinstance(prop, dict):
        raise GrammarError("unsupported_expression", "claim and proposal must be objects")
    _only(claim, {"id", "text", "source"}, "claim")
    if not isinstance(claim.get("id"), str) or not ID_RE.match(claim["id"]):
        raise GrammarError("unsupported_expression", "claim.id must be a short id")
    if not isinstance(claim.get("text"), str) or len(claim["text"]) > MAX_TEXT:
        raise GrammarError("request_too_large", f"claim.text must be a string of <= {MAX_TEXT} chars")
    src = claim.get("source", {})
    if not isinstance(src, dict):
        raise GrammarError("unsupported_expression", "claim.source must be an object")
    _only(src, {"ref", "locator", "text_sha256"}, "claim.source")
    for k in ("ref", "locator", "text_sha256"):
        if k in src and (not isinstance(src[k], str) or len(src[k]) > 300):
            raise GrammarError("unsupported_expression", f"claim.source.{k} must be a short string")
    _only(prop, {"symbols", "assumptions", "constraints", "source_mapping", "unresolved"}, "proposal")
    opts = req.get("options", {})
    if not isinstance(opts, dict):
        raise GrammarError("unsupported_expression", "options must be an object")
    _only(opts, {"controls", "lean_statement"}, "options")

    symbols = prop.get("symbols", [])
    if not isinstance(symbols, list) or len(symbols) > MAX_SYMBOLS:
        raise GrammarError("request_too_large", f"at most {MAX_SYMBOLS} symbols")
    names, syms = [], {}
    for i, s in enumerate(symbols):
        if not isinstance(s, dict):
            raise GrammarError("unsupported_expression", "symbol must be an object")
        _only(s, {"name", "unit", "domain", "status", "source_ref", "integer"}, f"symbols[{i}]")
        n = s.get("name")
        if not isinstance(n, str) or not NAME_RE.match(n) or n in syms:
            raise GrammarError("unsupported_expression", f"symbols[{i}].name must be a unique identifier [A-Za-z][A-Za-z0-9_]{{0,15}}")
        if s.get("status", "declared") not in ("given", "declared", "unknown"):
            raise GrammarError("unsupported_expression", f"symbols[{i}].status must be given|declared|unknown")
        if not isinstance(s.get("unit", "1"), str) or len(s.get("unit", "1")) > 40:
            raise GrammarError("unsupported_expression", f"symbols[{i}].unit must be a short unit string")
        if "source_ref" in s and (not isinstance(s["source_ref"], str) or len(s["source_ref"]) > 300):
            raise GrammarError("unsupported_expression", f"symbols[{i}].source_ref must be a short string")
        if s.get("integer", False) not in (True, False):
            raise GrammarError("unsupported_expression", f"symbols[{i}].integer must be boolean")
        dom = s.get("domain", {})
        if not isinstance(dom, dict):
            raise GrammarError("unsupported_expression", f"symbols[{i}].domain must be an object")
        _only(dom, {"lo", "hi", "lo_open", "hi_open"}, f"symbols[{i}].domain")
        lo = parse_literal(dom["lo"], f"{n}.lo") if "lo" in dom and dom["lo"] is not None else None
        hi = parse_literal(dom["hi"], f"{n}.hi") if "hi" in dom and dom["hi"] is not None else None
        if lo is not None and hi is not None and lo > hi:
            raise GrammarError("unsupported_expression", f"symbol {n}: domain lo > hi")
        syms[n] = {"name": n, "unit": s.get("unit", "1"), "lo": lo, "hi": hi,
                   "lo_open": bool(dom.get("lo_open", False)), "hi_open": bool(dom.get("hi_open", False)),
                   "status": s.get("status", "declared"), "integer": bool(s.get("integer", False)),
                   "source_ref": s.get("source_ref", "")}
        names.append(n)
    nameset = set(names)

    for key, fields in (("assumptions", {"id", "text", "kind"}), ("unresolved", {"id", "question"}),
                        ("source_mapping", {"element", "quote", "locator"})):
        lst = prop.get(key, [])
        if not isinstance(lst, list) or len(lst) > MAX_ASSUMPTIONS:
            raise GrammarError("request_too_large", f"proposal.{key} must be a list of <= {MAX_ASSUMPTIONS}")
        for j, e in enumerate(lst):
            if not isinstance(e, dict):
                raise GrammarError("unsupported_expression", f"proposal.{key}[{j}] must be an object")
            _only(e, fields, f"{key}[{j}]")
            for k, v in e.items():
                if not isinstance(v, str) or len(v) > (1000 if k in ("text", "question") else 300):
                    raise GrammarError("unsupported_expression", f"{key}[{j}].{k} must be a short string")
        if key == "assumptions":
            for e in lst:
                if e.get("kind", "modelling") not in ("modelling", "scope", "numerical"):
                    raise GrammarError("unsupported_expression", "assumption.kind must be modelling|scope|numerical")

    cons = prop.get("constraints", [])
    if not isinstance(cons, list) or len(cons) > MAX_CONSTRAINTS:
        raise GrammarError("request_too_large", f"at most {MAX_CONSTRAINTS} constraints")
    ids = set()
    for i, c in enumerate(cons):
        w = f"constraints[{i}]"
        if not isinstance(c, dict):
            raise GrammarError("unsupported_expression", f"{w} must be an object")
        _only(c, {"id", "kind", "expr", "source_ref", "dimension_check"}, w)
        if not isinstance(c.get("id"), str) or not ID_RE.match(c["id"]) or c["id"] in ids:
            raise GrammarError("unsupported_expression", f"{w}.id must be a unique short id")
        ids.add(c["id"])
        if c.get("kind") not in ("inequality", "equality", "domain_guard"):
            raise GrammarError("unsupported_expression", f"{w}.kind must be inequality|equality|domain_guard")
        e = c.get("expr")
        if not isinstance(e, dict):
            raise GrammarError("unsupported_expression", f"{w}.expr must be an object")
        _only(e, {"op", "lhs", "rhs"}, w + ".expr")
        if e.get("op") not in COMPARISONS:
            raise GrammarError("unsupported_expression", f"{w}.expr.op must be one of {COMPARISONS}")
        if c["kind"] == "equality" and e["op"] != "==" or c["kind"] == "inequality" and e["op"] == "==":
            raise GrammarError("unsupported_expression", f"{w}: kind {c['kind']} does not match op {e['op']}")
        if "lhs" not in e or "rhs" not in e:
            raise GrammarError("unsupported_expression", f"{w}.expr needs lhs and rhs")
        total = [LIMITS["max_nodes"]]
        for side in ("lhs", "rhs"):
            check_term(e[side], nameset, total, f"{c['id']}")
        if "dimension_check" in c and not isinstance(c["dimension_check"], bool):
            raise GrammarError("unsupported_expression", f"{w}.dimension_check must be boolean")
    return {"claim": claim, "source": src, "proposal": prop, "options": opts, "names": names, "symbols": syms,
            "constraints": cons}
