"""Deterministic baseline rankings over view rows. Every ranking is TIERED: ties are shown, never broken by an invented number.

A ranking reads only the fields named in its `basis`. No ranking reads an Assessment or any truth/acceptance field, so a claim's
truth and its priority cannot influence each other (tested). `pairs_ordered_fraction` says how much of the set the ranking actually
orders; 0.0 means it is degenerate for that set.
"""
from __future__ import annotations

from itertools import combinations
from math import comb

from . import vocab

DOES_NOT_IMPLY = ("A priority, rank or forecast says nothing about whether a design, mechanism, intervention or claim is viable or true. "
                  "Viability and truth are established only by independently reviewed computation or measurement.")


def _result(name, basis, tiers, unplaced, n, note):
    where = {i: t for t, ids in enumerate(tiers) for i in ids}
    ordered = sum(1 for a, b in combinations(sorted(where), 2) if where[a] != where[b])
    return {"name": name, "basis": basis, "tiers": [{"rank": t + 1, "ids": sorted(ids)} for t, ids in enumerate(tiers)],
            "unplaced": sorted(unplaced, key=lambda u: u[0]), "n": n, "n_placed": len(where),
            "pairs_ordered_fraction": (ordered / comb(n, 2)) if n > 1 else None, "note": note, "does_not_imply": DOES_NOT_IMPLY}


def _id(row):
    return row["key"]           # namespace/kind/id: ids alone collide across nodes


def id_order(rows):
    return _result("id_order", "identifier only", [[_id(r)] for r in sorted(rows, key=_id)], [], len(rows),
                   "a deterministic listing; orders everything and says nothing about value")


def actionable_first(rows):
    act = [_id(r) for r in rows if r["store"]["completeness"]["value"] == "actionable"]
    rec = [_id(r) for r in rows if r["store"]["completeness"]["value"] == "recorded"]
    return _result("actionable_first", "frontier-store Problem.completeness", [t for t in (act, rec) if t], [], len(rows),
                   "two tiers at most; the order inside a tier is not meaningful (listed by id for determinism)")


def register_label_layers(rows):
    """Non-dominated layers on the register's importance and tractability labels (declared direction in vocab), no weights."""
    pts, unplaced = {}, []
    for r in rows:
        imp, tra = r["register_labels"]["importance"], r["register_labels"]["tractability"]
        if imp is None or tra is None:
            unplaced.append((_id(r), "no register importance/tractability label"))
        else:
            pts[_id(r)] = (vocab.REGISTER_DIRECTION["importance"][imp["value"]], vocab.REGISTER_DIRECTION["tractability"][tra["value"]])
    dom = lambda a, b: all(x >= y for x, y in zip(a, b)) and a != b
    remaining, layers = set(pts), []
    while remaining:
        front = {i for i in remaining if not any(dom(pts[j], pts[i]) for j in remaining)}
        if not front:
            raise ValueError("dominance relation has a cycle")
        layers.append(front)
        remaining -= front
    return _result("register_label_layers", "morphoswarm-register importance x tractability (declared direction)", layers, unplaced, len(rows),
                   "orders curator LABELS, not consequence. " + vocab.REGISTER_DIRECTION_NOTE)


def typed_unlock_groups(rows):
    """Structural, no utilities: number of distinct independent groups of typed logical/empirical unlock edges, from APPLIED annotations."""
    by_n: dict[int, list] = {}
    unplaced = []
    for r in rows:
        if r["annotation"]["status"] != "applied":
            unplaced.append((_id(r), f"annotation {r['annotation']['status']}"))
            continue
        groups = {e["independent_group"] for e in r["typed_unlocks"] if e["kind"] in ("logical_necessity", "empirical_relevance")}
        by_n.setdefault(len(groups), []).append(_id(r))
    tiers = [by_n[n] for n in sorted(by_n, reverse=True)]
    return _result("typed_unlock_groups", "applied annotation: distinct independent groups of logical/empirical unlock edges", tiers, unplaced, len(rows),
                   "counts distinct downstream results, not their value; proposed_connection edges are excluded")


def declared_evpi(rows):
    """By the annotator's DECLARED EVPI. Rows with unknown utility are unplaced, never given a value."""
    vals, unplaced = {}, []
    for r in rows:
        u = r["utility"]
        if u["status"] in ("declared", "partial") and u["evpi"] is not None:
            vals[_id(r)] = u["evpi"]
        else:
            unplaced.append((_id(r), "utility " + u["status"]))
    tiers = [[i for i in vals if vals[i] == v] for v in sorted(set(vals.values()), reverse=True)]
    return _result("declared_evpi", "annotator-declared utilities and priors (not calibrated, not a probability of truth)", tiers, unplaced, len(rows),
                   "a ranking by declared numbers; it is only as good as their sources")


def derived_dependents(rows):
    """From the store's own typed `dependencies`, inverted: how many OTHER problems list this one. Factual and unannotated; says nothing
    about value. Empty everywhere when no problem declares dependencies (true of the 250 imported register problems)."""
    by_n: dict[int, list] = {}
    for r in rows:
        by_n.setdefault(len(r["dependents"]), []).append(_id(r))
    return _result("derived_dependents", "frontier-store Problem.dependencies, inverted", [by_n[n] for n in sorted(by_n, reverse=True)], [], len(rows),
                   "counts problems that declare a dependency on this one (exact id); a count of links, not of value")


BASELINES = (id_order, actionable_first, register_label_layers, derived_dependents, typed_unlock_groups, declared_evpi)


def all_baselines(rows):
    return {f.__name__: f(rows) for f in BASELINES}


def partition_by_approach(rows):
    """Group rows by the store's Problem.approach value, verbatim (None when the store does not carry one). A partition, not a ranking."""
    out: dict = {}
    for r in rows:
        key = r["store"].get("approach")
        out.setdefault(json_key(key), []).append(r)
    return out


def json_key(v):
    import json
    return "unspecified" if v is None else (v if isinstance(v, str) else json.dumps(v, sort_keys=True))
