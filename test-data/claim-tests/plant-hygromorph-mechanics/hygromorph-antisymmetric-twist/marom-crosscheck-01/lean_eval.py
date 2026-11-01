"""Evaluate real-valued `def`s straight from a Lean source file.

Not a Lean implementation: a parser for the small term language the hygromorph definitions use
(numerals, identifiers, + - * / ^, unary minus, application by juxtaposition, parentheses, and
Real.sin / Real.cos). It reads the body of each `def NAME (args : ℝ) : ℝ := body` from
Hygromorphs.lean, so the definitions under test are the ones in the file, not a retyped copy.
Anything outside that language raises, instead of being silently skipped.
"""
import math
import re

TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([^\W\d][\w.']*)|(.))", re.UNICODE)
FUNCS1 = {"Real.sin": math.sin, "Real.cos": math.cos}


def tokenize(s):
    out, pos = [], 0
    s = s.strip()
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m:
            raise ValueError(f"cannot tokenize at {s[pos:pos+20]!r}")
        pos = m.end()
        if m.group(1) is not None:
            out.append(("num", float(m.group(1))))
        elif m.group(2) is not None:
            out.append(("id", m.group(2)))
        else:
            out.append(("op", m.group(3)))
    return out


class Parser:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, op=None):
        tok = self.peek()
        if op is not None and tok != ("op", op):
            raise ValueError(f"expected {op!r}, got {tok}")
        self.i += 1
        return tok

    def expr(self):
        node = self.mul()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.eat()[1]
            node = (op, node, self.mul())
        return node

    def mul(self):
        node = self.unary()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.eat()[1]
            node = (op, node, self.unary())
        return node

    def unary(self):
        if self.peek() == ("op", "-"):
            self.eat()
            return ("neg", self.unary())
        return self.power()

    def power(self):
        base = self.app()
        if self.peek() == ("op", "^"):
            self.eat()
            return ("^", base, self.unary())
        return base

    def app(self):
        head = self.atom()
        args = []
        while self.peek()[0] in ("num", "id") or self.peek() == ("op", "("):
            args.append(self.atom())
        if args:
            if head[0] != "var":
                raise ValueError("application of a non-identifier")
            return ("app", head[1], args)
        return head

    def atom(self):
        kind, v = self.peek()
        if kind == "num":
            self.eat()
            return ("num", v)
        if kind == "id":
            self.eat()
            return ("var", v)
        if (kind, v) == ("op", "("):
            self.eat()
            node = self.expr()
            self.eat(")")
            return node
        raise ValueError(f"unexpected token {self.peek()}")


def parse_term(s):
    p = Parser(tokenize(s))
    node = p.expr()
    if p.i != len(p.t):
        raise ValueError(f"trailing tokens in {s!r}: {p.t[p.i:]}")
    return node


DEF = re.compile(r"^def (\w+) ((?:\([^)]*:\s*ℝ\)\s*)+):\s*ℝ\s*:=\s*(.*?)(?=\n\s*\n|\n/-)", re.S | re.M)


def load_defs(path, names, mutate=None):
    """Return {name: (params, ast)} for the requested defs. `mutate` maps a def name to a list of
    (old, new) text replacements applied to its body before parsing (fault injection); each `old`
    must be present."""
    text = open(path, encoding="utf8").read()
    found = {}
    for m in DEF.finditer(text):
        name, sig, body = m.group(1), m.group(2), m.group(3)
        if name not in names:
            continue
        params = []
        for grp in re.findall(r"\(([^)]*):\s*ℝ\)", sig):
            params += grp.split()
        body = re.sub(r"--.*", "", body)
        body = " ".join(body.split())
        for old, new in (mutate or {}).get(name, []):
            if old not in body:
                raise ValueError(f"mutation target {old!r} not in {name}: {body!r}")
            body = body.replace(old, new)
        found[name] = (params, parse_term(body))
    missing = set(names) - set(found)
    if missing:
        raise ValueError(f"defs not found in {path}: {sorted(missing)}")
    return found


def evaluate(node, env, defs):
    k = node[0]
    if k == "num":
        return node[1]
    if k == "var":
        if node[1] in env:
            return env[node[1]]
        raise KeyError(node[1])
    if k == "neg":
        return -evaluate(node[1], env, defs)
    if k in "+-*/^" and len(node) == 3:
        a, b = evaluate(node[1], env, defs), evaluate(node[2], env, defs)
        if k == "/":
            return a / b if b != 0 else math.nan  # Lean: x / 0 = 0; draws never reach it
        if k == "+":
            return a + b
        if k == "-":
            return a - b
        if k == "*":
            return a * b
        return a ** b
    if k == "app":
        name, args = node[1], [evaluate(a, env, defs) for a in node[2]]
        if name in FUNCS1:
            if len(args) != 1:
                raise ValueError(f"{name} takes one argument")
            return FUNCS1[name](args[0])
        if name in defs:
            params, body = defs[name]
            if len(args) != len(params):
                raise ValueError(f"{name} expects {len(params)} arguments")
            return evaluate(body, dict(zip(params, args)), defs)
        raise KeyError(name)
    raise ValueError(f"bad node {node}")


class LeanDefs:
    def __init__(self, path, names, mutate=None):
        self.defs = load_defs(path, names, mutate)

    def __call__(self, name, *args):
        params, body = self.defs[name]
        assert len(args) == len(params), (name, params, args)
        return evaluate(body, dict(zip(params, args)), self.defs)
