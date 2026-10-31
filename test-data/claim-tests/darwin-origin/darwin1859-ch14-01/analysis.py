#!/usr/bin/env python3
"""Test of darwin1859-ch14-01: descent with modification embraces all members of each class
(as the classes were circumscribed in 1859).

Data: Open Tree of Life v3 API (tnrs/match_names, tree_of_life/induced_subtree). The induced
subtree (newick), per-class results and response checksums are written to derived/.
"""
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
RESULT = json.load(open(os.path.join(HERE, "result.json")))
PRE = RESULT["preregistration"]
FETCH_LOG = []
S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"


def post(url, payload):
    r = S.post(url, json=payload, timeout=180)
    r.raise_for_status()
    FETCH_LOG.append({"download_url": url, "request_body": json.dumps(payload, sort_keys=True),
                      "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "byte_size": len(r.content), "sha256": hashlib.sha256(r.content).hexdigest()})
    return r.json()


# --- minimal newick parser -------------------------------------------------------------
class Node:
    __slots__ = ("label", "children", "parent")

    def __init__(self, label=""):
        self.label, self.children, self.parent = label, [], None


def parse_newick(s):
    s = s.strip().rstrip(";")
    i = 0
    root = Node()
    node = root
    stack = []
    while i < len(s):
        c = s[i]
        if c == "(":
            child = Node()
            child.parent = node
            node.children.append(child)
            stack.append(node)
            node = child
            i += 1
        elif c == ",":
            node = stack[-1]
            child = Node()
            child.parent = node
            node.children.append(child)
            node = child
            i += 1
        elif c == ")":
            node = stack.pop()
            i += 1
        elif c == "'":
            j = s.index("'", i + 1)
            node.label = s[i + 1:j]
            i = j + 1
        else:
            m = re.match(r"[^,():;]+", s[i:])
            node.label += m.group(0)
            i += len(m.group(0))
    return root


def collapse_unary(node):
    """Remove single-child chains (Open Tree includes them) so that polytomy structure is explicit."""
    while len(node.children) == 1 and node.children[0].children:
        child = node.children[0]
        node.label = child.label or node.label
        node.children = child.children
        for ch in node.children:
            ch.parent = node
    if len(node.children) == 1 and not node.children[0].children:
        # a labelled tip hanging below a labelled taxon node: keep the deeper (tip) label
        node.label = node.children[0].label
        node.children = []
    for ch in node.children:
        collapse_unary(ch)


def tips(node):
    return [node] if not node.children else [t for c in node.children for t in tips(c)]


def ott_of(label):
    m = re.search(r"ott(\d+)$", label)
    return int(m.group(1)) if m else None


def dollo_origins(root, state):
    """Maximal clades whose tips all have state 1 (gains only, no losses); their number is the
    Dollo minimum number of independent origins."""
    clades = []

    def rec(n):
        if not n.children:
            return state[n]
        res = [(c, rec(c)) for c in n.children]
        if all(a for _, a in res):
            return True
        for c, a in res:
            if a:
                clades.append(c)
        return False
    if rec(root):
        clades.append(root)
    return clades



def sankoff_origins(root, state, gain_cost, loss_cost):
    """Weighted parsimony for a binary character. Returns the number of origins (gains, plus
    one if the root is reconstructed in state 1) in the cheapest reconstruction, breaking ties
    toward fewer gains. Costs are (weighted cost, gains) tuples compared lexicographically."""
    INF = (10 ** 9, 10 ** 9)

    def add(a, b):
        return (a[0] + b[0], a[1] + b[1])

    def rec(n):
        if not n.children:
            return {0: (0, 0) if not state[n] else INF, 1: (0, 0) if state[n] else INF}
        child_costs = [rec(c) for c in n.children]
        out = {}
        for s in (0, 1):
            total = (0, 0)
            for cc in child_costs:
                stay = cc[s]
                if s == 0:
                    change = add(cc[1], (gain_cost, 1))
                else:
                    change = add(cc[0], (loss_cost, 0))
                total = add(total, min(stay, change))
            out[s] = total
        return out
    costs = rec(root)
    root0 = costs[0]
    root1 = add(costs[1], (0, 1))  # a root in state 1 is itself one origin
    best = min(root0, root1)
    return best[1], best[0]


def main():
    about = post("https://api.opentreeoflife.org/v3/tree_of_life/about", {})
    classes = PRE["classes_1859"]
    names = sorted({t for reps in classes.values() for t in reps})
    tn = post(PRE["tnrs_endpoint"], {"names": names, "context_name": PRE["context"], "do_approximate_matching": False})
    ott = {}
    for r in tn["results"]:
        exact = [m for m in r["matches"] if not m["is_approximate_match"]]
        if exact:
            ott[r["name"]] = exact[0]["taxon"]["ott_id"]
    print("matched", len(ott), "of", len(names), "unmatched:", [n for n in names if n not in ott], flush=True)
    pruned = []
    while True:
        try:
            sub = post(PRE["synthetic_tree_endpoint"], {"ott_ids": sorted(ott.values()), "label_format": "name_and_id"})
            break
        except requests.HTTPError as e:
            unknown = e.response.json().get("unknown", {}) if e.response is not None else {}
            if not unknown:
                raise
            for k in unknown:
                oid = int(k.replace("ott", ""))
                for nm, v in list(ott.items()):
                    if v == oid:
                        pruned.append(nm)
                        del ott[nm]
            print("pruned from synth tree:", pruned, flush=True)
    broken = sub.get("broken", {})
    open(os.path.join(DERIVED, "classes.newick"), "w").write(sub["newick"] + "\n")
    root = parse_newick(sub["newick"])
    collapse_unary(root)
    tip_by_ott = {ott_of(t.label): t for t in tips(root)}
    tip_by_nodeid = {}
    for t in tips(root):
        m = re.search(r"(mrcaott\d+ott\d+|ott\d+)$", t.label)
        if m:
            tip_by_nodeid[m.group(1)] = t
    assigned, unmapped = {}, []
    for nm, oid in ott.items():
        t = tip_by_ott.get(oid)
        if t is None and f"ott{oid}" in broken:
            t = tip_by_nodeid.get(broken[f"ott{oid}"])
        if t is None:
            unmapped.append(nm)
        else:
            assigned.setdefault(t, []).append(nm)
    unmapped += [n for n in names if n not in ott]
    mapped_frac = (len(names) - len(unmapped)) / len(names)
    print("mapped fraction", mapped_frac, "unmapped", unmapped, flush=True)

    rows = []
    for cls, reps in classes.items():
        members = set(reps)
        state = {t: any(n in members for n in assigned.get(t, [])) for t in tips(root)}
        n_tips = sum(state.values())
        origins, cost = sankoff_origins(root, state, PRE["gain_cost"], PRE["loss_cost"])
        dollo = len(dollo_origins(root, state))
        rows.append({"class_1859": cls, "n_representatives": len(reps), "n_placed": n_tips,
                     "representatives_missing": [r for r in reps if r in unmapped],
                     "origins_weighted_parsimony": origins, "parsimony_cost": cost, "dollo_pure_clades": dollo,
                     "single_descent": origins == 1})
        print(cls, "origins", origins, "dollo", dollo, flush=True)
    import pandas as pd
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "classes.csv"), index=False)
    n = len(df)
    k = int(df.single_descent.sum())
    frac = k / n
    measured = {
        "value": k,
        "unit": f"of {n} classes as circumscribed in 1859 that have a single origin under weighted parsimony (gain 2, loss 1) on the Open Tree synthetic tree",
        "n": n,
        "uncertainty": f"fraction {frac:.3f}; mapped fraction of representative taxa {mapped_frac:.3f}",
        "extra": {"synth_id": about.get("synth_id"), "taxonomy_version": about.get("taxonomy_version"),
                  "fraction_single_descent": frac, "mapped_fraction": mapped_frac, "unmapped": unmapped, "pruned_from_synth": pruned,
                  "classes": {r["class_1859"]: {"origins": int(r["origins_weighted_parsimony"]), "dollo_pure_clades": int(r["dollo_pure_clades"]), "n_placed": int(r["n_placed"])} for r in rows},
                  "single_descent_classes": sorted(df[df.single_descent].class_1859.tolist()),
                  "multiple_origin_classes": sorted(df[~df.single_descent].class_1859.tolist())},
    }
    if mapped_frac < PRE["min_mapped_fraction"]:
        verdict, reason = "inconclusive", "data-unavailable"
    elif frac >= PRE["support_threshold"]:
        verdict, reason = "supports", None
    elif frac <= PRE["refute_threshold"]:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "mixed", None
    print(json.dumps(measured, indent=1))
    print("verdict:", verdict)
    json.dump(FETCH_LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=1)
    json.dump({"measured": measured, "verdict": verdict, "reason": reason}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
