"""Decision-conditioned inference over exact, finite factor graphs.

Concepts reused (not code copied) from MorphoSwarm's evidence/belief engine, read 2026-10-31:
belief/graph.py (loop test by edge counting, factor-over-unknown-variable refused at
construction, do-queries refused), belief/potentials.py (every factor carries provenance, an
exact Fraction table), belief/priors.py (a prior states its method; no default prior),
belief/engines/exact.py (exact variable elimination; a loopy approximation is never returned
unlabelled), belief/sensitivity.py (leave-one-out and prior sweeps), evidence/overlap.py and
independence (shared lineage is detected, not multiplied as if independent).

What this module is NOT: a truth score, a calibrated forecaster, or a causal engine. Given a
declared scenario it returns, for a declared decision, the expected value of each action under
the declared assumptions plus the declared assumptions whose removal changes the preferred
action. Scientific calibration of any such number is UNKNOWN; nothing here measures it.

Semantics. posterior(x) is proportional to prior(x) * product of factor tables, computed with
exact Fractions. A factor table is a non-negative potential (a likelihood-ratio-like weight),
complete over its scope. A 0 is a hard zero: the combination is declared impossible.
Conditioning an action on `assumes` is conditioning, not intervention; any `do` key is an
unknown key and is refused.

Everything not computable inside the declared caps is returned as an explicit status
("refused-*", "unsupported-*", "unresolved-*", "contradiction"), never approximated and never
silently normalised. Malformed input raises BeliefError.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any

SCHEMA = "frontier-beliefs-0.1"
MAX_VARIABLES = 20          # variables in a scenario
MAX_STATES = 6              # states per variable
MAX_FACTORS = 80            # evidence factors (priors are separate and one per variable)
MAX_FACTOR_SCOPE = 4        # variables in one factor
MAX_TABLE_CELLS = 1296      # = 6**4, rows in one factor table
MAX_ELIM_CELLS = 50_000     # largest intermediate table variable elimination may build
MAX_ACTIONS = 8
PRIOR_METHODS = ("declared", "uniform-ignorance", "reference-class")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,79}$")
CALIBRATION = ("UNKNOWN: no calibration of these numbers against outcomes has been done. They are "
               "consequences of the declared assumptions, not measured accuracy.")
INTERPRETATION = ("A decision-conditioned forecast under declared assumptions. It is not a truth "
                  "score of any claim and holds only for the stated event and context.")


class BeliefError(ValueError):
    """The scenario is malformed (as opposed to well-formed but refused or unsupported)."""


class _Unsupported(Exception):
    pass


@dataclass(frozen=True)
class Caps:
    max_variables: int = MAX_VARIABLES
    max_states: int = MAX_STATES
    max_factors: int = MAX_FACTORS
    max_factor_scope: int = MAX_FACTOR_SCOPE
    max_table_cells: int = MAX_TABLE_CELLS
    max_elim_cells: int = MAX_ELIM_CELLS
    max_actions: int = MAX_ACTIONS


def canonical(value: Any) -> str:
    """Same byte format as frontier.models.canonical (tested), kept here to stay stdlib-only."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


# ---------------------------------------------------------------- parsing (strict) ----------

def _frac(x: Any, where: str, nonneg: bool = False) -> Fraction:
    if isinstance(x, bool) or not isinstance(x, (int, str)):
        raise BeliefError(f"{where}: exact numbers are ints or strings like '3/10'; got {type(x).__name__} "
                          f"(floats are refused because they are inexact)")
    try:
        f = Fraction(x)
    except (ValueError, ZeroDivisionError):
        raise BeliefError(f"{where}: not a rational number: {x!r}") from None
    if nonneg and f < 0:
        raise BeliefError(f"{where}: must be non-negative, got {f}")
    return f


def _obj(d: Any, req: tuple, opt: tuple, where: str) -> dict:
    if not isinstance(d, dict):
        raise BeliefError(f"{where}: must be an object")
    extra = sorted(set(d) - set(req) - set(opt))
    if extra:
        raise BeliefError(f"{where}: unknown keys {extra} (e.g. do-queries are not supported)")
    missing = [k for k in req if k not in d]
    if missing:
        raise BeliefError(f"{where}: missing required keys {missing}")
    return d


def _txt(d: dict, k: str, where: str) -> str:
    v = d.get(k)
    if not isinstance(v, str) or not v.strip():
        raise BeliefError(f"{where}.{k}: must be a non-empty string")
    return v


def _id(d: dict, k: str, where: str) -> str:
    v = _txt(d, k, where)
    if not _ID.match(v):
        raise BeliefError(f"{where}.{k}: {v!r} is not a valid identifier")
    return v


def _len(x: Any) -> int:
    return len(x) if isinstance(x, (list, dict)) else 0


def _cap_violations(sc: dict, caps: Caps) -> list[str]:
    """Counted on the raw input, before any table is built, so oversized input is never expanded."""
    out = []
    vs, fs, dec = sc.get("variables"), sc.get("factors"), sc.get("decision")
    for name, n, cap in (("variables", _len(vs), caps.max_variables), ("factors", _len(fs), caps.max_factors),
                         ("actions", _len(dec.get("actions")) if isinstance(dec, dict) else 0, caps.max_actions)):
        if n > cap:
            out.append(f"{name}: {n} > cap {cap}")
    for v in vs if isinstance(vs, list) else []:
        if isinstance(v, dict) and _len(v.get("states")) > caps.max_states:
            out.append(f"variable {v.get('id')}: {_len(v['states'])} states > cap {caps.max_states}")
    for f in fs if isinstance(fs, list) else []:
        if isinstance(f, dict):
            if _len(f.get("scope")) > caps.max_factor_scope:
                out.append(f"factor {f.get('id')}: scope {_len(f['scope'])} > cap {caps.max_factor_scope}")
            if _len(f.get("table")) > caps.max_table_cells:
                out.append(f"factor {f.get('id')}: {_len(f['table'])} table cells > cap {caps.max_table_cells}")
    return out


def _parse(sc: dict) -> dict:
    _obj(sc, ("schema", "label", "variables", "priors", "factors", "decision"), ("collapse",), "scenario")
    if sc["schema"] != SCHEMA:
        raise BeliefError(f"schema must be {SCHEMA!r}")
    label = _txt(sc, "label", "scenario")
    vars_: dict[str, dict] = {}
    for i, v in enumerate(sc["variables"]):
        w = f"variables[{i}]"
        _obj(v, ("id", "event", "context", "states"), (), w)
        vid = _id(v, "id", w)
        st = v["states"]
        if vid in vars_ or not isinstance(st, list) or len(st) < 2 or len(set(st)) != len(st) \
                or not all(isinstance(s, str) and s for s in st):
            raise BeliefError(f"{w}: duplicate id, or states must be >= 2 distinct non-empty strings")
        vars_[vid] = {"event": _txt(v, "event", w), "context": _txt(v, "context", w), "states": tuple(st)}
    cards = {v: len(d["states"]) for v, d in vars_.items()}
    index = {v: {s: i for i, s in enumerate(d["states"])} for v, d in vars_.items()}

    priors: dict[str, dict] = {}
    for i, p in enumerate(sc["priors"]):
        w = f"priors[{i}]"
        _obj(p, ("variable", "method"), ("table", "source", "group", "reference_class"), w)
        v = p["variable"]
        if v not in vars_ or v in priors:
            raise BeliefError(f"{w}: unknown variable {v!r} or second prior for it")
        m = p["method"]
        if m not in PRIOR_METHODS:
            raise BeliefError(f"{w}: method must be one of {PRIOR_METHODS}; a prior is never an unlabelled number")
        need = {"uniform-ignorance": (), "declared": ("table", "source"),
                "reference-class": ("table", "source", "reference_class")}[m]
        if sorted(k for k in p if k not in ("variable", "method", "group")) != sorted(need):
            raise BeliefError(f"{w}: method {m!r} takes exactly {list(need)}")
        if m == "uniform-ignorance":
            tab = [Fraction(1, cards[v])] * cards[v]
        else:
            t = p["table"]
            if not isinstance(t, dict) or set(t) != set(vars_[v]["states"]):
                raise BeliefError(f"{w}.table: must give every state of {v} exactly once")
            tab = [_frac(t[s], w, True) for s in vars_[v]["states"]]
            if sum(tab) != 1:
                raise BeliefError(f"{w}.table: must sum to exactly 1, got {sum(tab)}")
            _txt(p, "source", w)
            if m == "reference-class":
                _txt(p, "reference_class", w)
        priors[v] = {"id": "prior:" + v, "method": m, "scope": (v,), "tab": {(i,): x for i, x in enumerate(tab)},
                     "source": p.get("source"), "group": p.get("group") or "prior-group:" + v,
                     "reference_class": p.get("reference_class")}

    factors: dict[str, dict] = {}
    for i, f in enumerate(sc["factors"]):
        w = f"factors[{i}]"
        _obj(f, ("id", "scope", "table", "source", "group"), (), w)
        fid = _id(f, "id", w)
        sco = f["scope"]
        if fid in factors or fid.startswith("prior:") or not isinstance(sco, list) or not sco \
                or len(set(sco)) != len(sco) or any(v not in vars_ for v in sco):
            raise BeliefError(f"{w}: duplicate/reserved id, or scope must be distinct known variables")
        tab: dict[tuple, Fraction] = {}
        for r in f["table"]:
            if not isinstance(r, list) or len(r) != len(sco) + 1:
                raise BeliefError(f"{w}.table: each row is [state per scope variable..., weight]")
            try:
                key = tuple(index[v][s] for v, s in zip(sco, r[:-1]))
            except (KeyError, TypeError):
                raise BeliefError(f"{w}.table: unknown state in row {r}") from None
            if key in tab:
                raise BeliefError(f"{w}.table: duplicate row for {r[:-1]}")
            tab[key] = _frac(r[-1], w, True)
        if len(tab) != _prod(cards[v] for v in sco):
            raise BeliefError(f"{w}.table: must be complete over its scope (no missing assignments)")
        factors[fid] = {"id": fid, "scope": tuple(sco), "tab": tab, "source": _txt(f, "source", w),
                        "group": _txt(f, "group", w)}

    d = _obj(sc["decision"], ("id", "question", "outcome", "actions", "utility", "cost"), (), "decision")
    o = d["outcome"]
    if o not in vars_:
        raise BeliefError("decision.outcome: unknown variable")
    if not isinstance(d["actions"], dict) or not d["actions"]:
        raise BeliefError("decision.actions: object of action -> {assumes?}")
    acts, util, cost = {}, {}, {}
    for a in sorted(d["actions"]):
        spec = _obj(d["actions"][a], (), ("assumes",), f"decision.actions.{a}")
        asm = spec.get("assumes", {})
        if not isinstance(asm, dict) or any(v not in vars_ or s not in index[v] for v, s in asm.items()):
            raise BeliefError(f"decision.actions.{a}.assumes: object of known variable -> known state")
        acts[a] = sorted((v, index[v][s]) for v, s in asm.items())
        u = d["utility"].get(a) if isinstance(d["utility"], dict) else None
        if not isinstance(u, dict) or set(u) != set(vars_[o]["states"]):
            raise BeliefError(f"decision.utility.{a}: must give a value for every state of {o}")
        util[a] = [_frac(u[s], f"decision.utility.{a}.{s}") for s in vars_[o]["states"]]
        if not isinstance(d["cost"], dict) or a not in d["cost"]:
            raise BeliefError(f"decision.cost: must give a cost for {a} (0 is allowed, silence is not)")
        cost[a] = _frac(d["cost"][a], f"decision.cost.{a}")
    if set(d["utility"]) != set(acts) or set(d["cost"]) != set(acts):
        raise BeliefError("decision.utility/cost: keys must be exactly the actions")
    collapse = sc.get("collapse", {})
    if not isinstance(collapse, dict):
        raise BeliefError("collapse: object of 'group:NAME'|'source:NAME' -> kept factor id")
    return {"label": label, "vars": vars_, "cards": cards, "priors": priors, "factors": factors,
            "decision": {"id": _id(d, "id", "decision"), "question": _txt(d, "question", "decision"),
                         "outcome": o, "actions": acts, "utility": util, "cost": cost},
            "collapse": collapse}


def _prod(it) -> int:
    n = 1
    for x in it:
        n *= x
    return n


# ---------------------------------------------------------------- lineage / duplicate paths --

def _duplicates(entries: list[dict]) -> list[dict]:
    """Duplicate evidence paths among prior/factor entries (id, scope, source, group).

    same-group: >= 2 entries declare the same evidence group (declared dependence).
    same-source: >= 2 entries share a source AND (transitively) a variable, i.e. one underlying
    source reaches a variable by more than one route. Routes that only meet through intermediate
    factors are NOT detected unless the author puts the entries in one group (documented limit).
    """
    out = []
    by_group = defaultdict(list)
    for e in entries:
        by_group[e["group"]].append(e["id"])
    out += [{"kind": "group", "name": g, "members": sorted(m)} for g, m in sorted(by_group.items()) if len(m) > 1]
    by_src = defaultdict(list)
    for e in entries:
        by_src[e["source"]].append(e)
    for s, es in sorted(by_src.items()):
        comp = {e["id"]: {e["id"]} for e in es}
        for a, b in itertools.combinations(es, 2):
            if set(a["scope"]) & set(b["scope"]):
                merged = comp[a["id"]] | comp[b["id"]]
                for k in merged:
                    comp[k] = merged
        seen = set()
        for m in comp.values():
            if len(m) > 1 and frozenset(m) not in seen:
                seen.add(frozenset(m))
                out.append({"kind": "source", "name": s, "members": sorted(m)})
    return out


def _is_cyclic(scopes: list[tuple]) -> bool:
    parent: dict = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i, sc in enumerate(scopes):
        for v in sc:
            a, b = find(("f", i)), find(("v", v))
            if a == b:
                return True
            parent[a] = b
    return False


# ---------------------------------------------------------------- exact solver ---------------

def _marginal(factors: list[tuple], cards: dict, query: str, caps: Caps):
    """Unnormalised marginal over `query` by exact variable elimination (min-cells greedy order).

    factors: [(scope, {state-index tuple: Fraction})]. Raises _Unsupported BEFORE building any
    intermediate table larger than caps.max_elim_cells. Returns (vector, largest_table_cells).
    """
    live = [(tuple(s), t) for s, t in factors]
    todo = {v for s, _ in live for v in s} - {query}
    biggest = 0
    while todo:
        best = None
        for v in sorted(todo):
            u = sorted({x for s, _ in live if v in s for x in s})
            cells = _prod(cards[x] for x in u)
            if best is None or cells < best[0]:
                best = (cells, v, u)
        cells, v, u = best
        if cells > caps.max_elim_cells:
            raise _Unsupported(f"eliminating {v} needs a {cells}-cell table > MAX_ELIM_CELLS={caps.max_elim_cells}")
        biggest = max(biggest, cells)
        used = [(s, t) for s, t in live if v in s]
        live = [(s, t) for s, t in live if v not in s]
        w = tuple(x for x in u if x != v)
        out = {}
        for assign in itertools.product(*(range(cards[x]) for x in w)):
            env = dict(zip(w, assign))
            tot = Fraction(0)
            for vi in range(cards[v]):
                env[v] = vi
                p = Fraction(1)
                for s, t in used:
                    p *= t[tuple(env[x] for x in s)]
                    if p == 0:
                        break
                tot += p
            out[assign] = tot
        live.append((w, out))
        todo.discard(v)
    vec = []
    for qi in range(cards[query]):
        p = Fraction(1)
        for s, t in live:
            p *= t[()] if s == () else t[(qi,)]
        vec.append(p)
    return vec, biggest


def _decide(model: dict, factors: list[tuple], caps: Caps) -> dict:
    dec, cards = model["decision"], model["cards"]
    o, rows = dec["outcome"], {}
    for a, assumes in dec["actions"].items():
        cond = [((v,), {(i,): Fraction(int(i == si)) for i in range(cards[v])}) for v, si in assumes]
        m, _ = _marginal(factors + cond, cards, o, caps)
        z = sum(m)
        if z == 0:
            rows[a] = None
            continue
        p = [x / z for x in m]
        rows[a] = (p, sum(pi * ui for pi, ui in zip(p, dec["utility"][a])) - dec["cost"][a])
    ev = {a: r[1] for a, r in rows.items() if r}
    top = max(ev.values()) if ev else None
    return {"rows": rows, "ev": ev, "preferred": tuple(sorted(a for a, e in ev.items() if e == top))}


def _breakeven(model: dict, base: dict) -> list[dict]:
    """Exact crossing points in P(first outcome state) for a binary outcome. Only valid when no
    action conditions on extra assumptions (then every action shares one forecast)."""
    dec, o = model["decision"], model["decision"]["outcome"]
    if model["cards"][o] != 2 or any(dec["actions"].values()) or len(base["preferred"]) != 1:
        return []
    b, s0, out = base["preferred"][0], model["vars"][o]["states"][0], []
    p = base["rows"][b][0][0]
    ub = dec["utility"][b]
    for a in dec["actions"]:
        if a == b:
            continue
        ua = dec["utility"][a]
        d = (ub[0] - ub[1]) - (ua[0] - ua[1])
        e = (ub[1] - dec["cost"][b]) - (ua[1] - dec["cost"][a])
        if d != 0 and 0 <= -e / d <= 1:
            star = -e / d
            out.append({"versus": a, "state": s0, "p_threshold": _s(star), "current_p": _s(p),
                        "preferred_changes_to_" + a + "_when_p_is": "below" if d > 0 else "above"})
    return out


def _s(x: Fraction) -> str:
    return str(x)


# ---------------------------------------------------------------- public entry ---------------

def solve(scenario: dict, caps: Caps = Caps()) -> dict:
    """Solve a declared scenario. Always returns an envelope with `status`; see module docs."""
    if not isinstance(scenario, dict):
        raise BeliefError("scenario must be an object")
    h = digest(scenario)
    res: dict[str, Any] = {
        "schema": SCHEMA, "input_hash": h, "status": "ok", "reasons": [],
        "metadata": {"calibration": CALIBRATION, "interpretation": INTERPRETATION,
                     "caps": asdict(caps), "solver": "exact variable elimination over Fractions; no approximation",
                     "engine_concepts_from": "morphoswarm/src/morphoswarm/evidence/belief (read, not copied)"},
        "duplicate_paths": [], "collapsed": []}

    def finish(status: str, *reasons: str) -> dict:
        res["status"], res["reasons"] = status, list(reasons)
        res["output_hash"] = digest({k: v for k, v in res.items() if k != "output_hash"})
        return res

    res["label"] = scenario.get("label")
    over = _cap_violations(scenario, caps)
    if over:
        return finish("refused-cap-exceeded", *over)
    model = _parse(scenario)
    cards, vars_ = model["cards"], model["vars"]
    missing = sorted(set(vars_) - set(model["priors"]))
    if missing:
        return finish("unresolved-no-prior", "no prior with a stated method for: " + ", ".join(missing)
                      + " (no default prior is supplied; use method 'uniform-ignorance' to state ignorance)")

    # lineage: duplicate evidence paths are reported, then collapsed by a DECLARED rule or refused
    pool = {**{p["id"]: p for p in model["priors"].values() if p["method"] != "uniform-ignorance"},
            **model["factors"]}
    first = _duplicates(list(pool.values()))
    res["duplicate_paths"] = first
    rules = model["collapse"]
    for key in sorted(rules):
        hit = [d for d in first if f"{d['kind']}:{d['name']}" == key]
        if not hit or rules[key] not in hit[0]["members"]:
            raise BeliefError(f"collapse rule {key!r} -> {rules[key]!r} matches no detected duplicate set/member")
    for d in first:
        key = f"{d['kind']}:{d['name']}"
        if key in rules:
            dropped = [m for m in d["members"] if m != rules[key]]
            for m in dropped:
                pool.pop(m, None)
            res["collapsed"].append({"rule": "keep-one", "key": key, "kept": rules[key], "dropped": dropped})
    left = _duplicates(list(pool.values()))
    if left:
        return finish("refused-duplicate-evidence", *[
            f"{d['kind']} {d['name']!r}: {d['members']} reach the same variable(s) via a shared "
            f"{d['kind']}; declare collapse {{'{d['kind']}:{d['name']}': <id to keep>}} or split the lineage"
            for d in left])
    dropped_ids = {m for c in res["collapsed"] for m in c["dropped"]}
    # a dropped prior is dropped evidence, not a licence to invent one: variable becomes unresolved
    missing = sorted(p["scope"][0] for p in model["priors"].values() if p["id"] in dropped_ids)
    if missing:
        return finish("unresolved-no-prior", "collapse dropped the prior of: " + ", ".join(missing))

    fl = {f["id"]: (f["scope"], f["tab"]) for f in model["factors"].values() if f["id"] not in dropped_ids}
    pl = {p["scope"][0]: (p["scope"], p["tab"]) for p in model["priors"].values()}
    allf = list(fl.values()) + list(pl.values())
    cyc = _is_cyclic([s for s, _ in allf])
    res["structure"] = {"variables": len(vars_), "factors": len(fl), "priors": len(pl), "cyclic": cyc,
                        "solver": "exact-variable-elimination"}
    try:
        post, biggest = {}, 0
        for v in sorted(vars_):
            vec, big = _marginal(allf, cards, v, caps)
            biggest = max(biggest, big)
            z = sum(vec)
            if z == 0:
                break
            post[v] = [x / z for x in vec]
        res["structure"]["largest_intermediate_cells"] = biggest
        if len(post) < len(vars_):
            labelled = {**fl, **{"prior:" + v: x for v, x in pl.items()}}
            q = sorted(vars_)[0]
            culprits = sorted(i for i in labelled if sum(
                _marginal([x for j, x in labelled.items() if j != i], cards, q, caps)[0]) > 0)
            zero = sorted(i for i, (_, t) in fl.items() if 0 in t.values())
            res["contradiction"] = {"factors_with_hard_zeros": zero, "support_restored_if_dropped": culprits}
            return finish("contradiction", "the declared factors/priors jointly assign probability 0 to "
                          "every joint state (hard-zero conflict); no posterior or decision is produced")
        base = _decide(model, allf, caps)
        if not base["ev"]:
            return finish("contradiction", "every action's declared assumptions contradict the evidence")
        sens = []
        for fid in sorted(fl):
            sens.append(("drop factor " + fid, [g for k, g in fl.items() if k != fid] + list(pl.values())))
        for v, (sco, t) in sorted(pl.items()):
            uni = {k: Fraction(1, cards[v]) for k in t}
            if t != uni:
                sens.append((f"replace prior of {v} by uniform-ignorance", list(fl.values())
                             + [g for k, g in pl.items() if k != v] + [(sco, uni)]))
        variations = []
        for name, fs in sens:
            r = _decide(model, fs, caps)
            variations.append({"assumption_changed": name, "preferred": list(r["preferred"]) or None,
                               "changes_preferred_action": r["preferred"] != base["preferred"],
                               "status": "ok" if r["ev"] else "contradiction"})
    except _Unsupported as e:
        return finish("unsupported-cyclic-beyond-exact-cap" if cyc else "unsupported-beyond-exact-cap",
                      str(e) + "; no approximate posterior is returned")

    dec = model["decision"]
    ranked = sorted(base["ev"].values(), reverse=True)
    res["variables"] = {v: {"event": vars_[v]["event"], "context": vars_[v]["context"],
                            "prior_method": model["priors"][v]["method"],
                            "prior_reference_class": model["priors"][v]["reference_class"],
                            "posterior": {s: _s(p) for s, p in zip(vars_[v]["states"], post[v])},
                            "prior_only": not any(v in s for s, _ in fl.values()),
                            "ruled_out_states": [s for s, p, q in zip(vars_[v]["states"], post[v], pl[v][1].values())
                                                 if p == 0 and q > 0]} for v in sorted(vars_)}
    res["decision"] = {
        "id": dec["id"], "question": dec["question"], "outcome_variable": dec["outcome"],
        "actions": {a: ({"forecast": {s: _s(p) for s, p in zip(vars_[dec["outcome"]]["states"], r[0])},
                         "expected_value": _s(r[1]), "assumes": [list(x) for x in dec["actions"][a]]} if r else
                        {"status": "impossible-under-its-assumptions"}) for a, r in base["rows"].items()},
        "preferred": base["preferred"][0] if len(base["preferred"]) == 1 else None,
        "tied": list(base["preferred"]) if len(base["preferred"]) > 1 else [],
        "ev_margin_over_runner_up": _s(ranked[0] - ranked[1]) if len(ranked) > 1 else None,
        "preferred_changes_when": {
            "breakeven": _breakeven(model, base),
            "variations": variations,
            "flipping_assumptions": [v["assumption_changed"] for v in variations if v["changes_preferred_action"]],
            "scope": "only the declared priors and factors are varied (drop-one, prior-to-uniform); "
                     "values are not perturbed beyond the exact breakeven. Unlisted assumptions are untested."}}
    return finish("ok")


# ---------------------------------------------------------------- declared illustration ------

EXAMPLE_SCENARIO: dict = {
    "schema": SCHEMA,
    "label": "declared illustration: every number below is a declared assumption, not a measurement",
    "variables": [{"id": "H", "event": "Hypothetical variant V exceeds activity threshold T in assay A",
                   "context": "declared illustration only; no variant, assay or data is referenced",
                   "states": ["yes", "no"]}],
    "priors": [{"variable": "H", "method": "declared", "table": {"yes": "1/5", "no": "4/5"},
                "source": "declared:illustration-author"}],
    "factors": [
        {"id": "e1", "scope": ["H"], "source": "declared:predictor-A", "group": "predictor-family",
         "table": [["yes", "3"], ["no", "1"]]},
        {"id": "e2", "scope": ["H"], "source": "declared:heuristic-B", "group": "structure-heuristic",
         "table": [["yes", "2"], ["no", "1"]]}],
    "decision": {"id": "advance-V", "question": "Spend the declared cost to advance V, or hold?",
                 "outcome": "H", "actions": {"advance": {}, "hold": {}},
                 "utility": {"advance": {"yes": "10", "no": "-4"}, "hold": {"yes": "0", "no": "0"}},
                 "cost": {"advance": "1", "hold": "0"}}}


def replay(scenario: dict) -> dict:
    return solve(scenario)


if __name__ == "__main__":
    import sys
    sc = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else EXAMPLE_SCENARIO
    print(json.dumps(solve(sc), indent=2, sort_keys=True))
