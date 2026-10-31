#!/usr/bin/env python3
"""Test of darwin1859-ch14-02: animals descend from at most four or five progenitors, plants
from as many or fewer.

Data: Open Tree of Life v3 API (tnrs/match_names, tree_of_life/induced_subtree). The induced
subtree (newick) and response checksums are written to derived/.
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


def fitch_changes(root, state):
    def rec(n):
        if not n.children:
            return ({state[n]}, 0)
        sets, changes = zip(*[rec(c) for c in n.children])
        inter = set.intersection(*sets)
        if inter:
            return (inter, sum(changes))
        # for polytomies, use the majority-state generalisation: pick states present in most children
        from collections import Counter
        cnt = Counter(st for s_ in sets for st in s_)
        best = max(cnt.values())
        return ({st for st, c in cnt.items() if c == best}, sum(changes) + len(sets) - best)
    return rec(root)[1]



def main():
    about = post("https://api.opentreeoflife.org/v3/tree_of_life/about", {})
    lineages = PRE["lineages"]
    names = list(lineages)
    tn = post(PRE["tnrs_endpoint"], {"names": names, "context_name": PRE["context"], "do_approximate_matching": False})
    ott = {}
    for r in tn["results"]:
        exact = [m for m in r["matches"] if not m["is_approximate_match"]]
        if exact:
            ott[r["name"]] = exact[0]["taxon"]["ott_id"]
    print("matched", len(ott), "of", len(names), flush=True)
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
    open(os.path.join(DERIVED, "lineages.newick"), "w").write(sub["newick"] + "\n")
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

    def count(reading, kingdom):
        state = {}
        for t in tips(root):
            ks = {lineages[n][reading] for n in assigned.get(t, [])}
            state[t] = (kingdom in ks)
        clades = dollo_origins(root, state)
        return len(clades), sorted([" + ".join(", ".join(assigned.get(t, [t.label])) for t in tips(c)) for c in clades])

    results = {}
    for reading in ("modern", "k1859"):
        a_n, a_cl = count(reading, "animal")
        p_n, p_cl = count(reading, "plant")
        results[reading] = {"animal_progenitors": a_n, "animal_clades": a_cl, "plant_progenitors": p_n, "plant_clades": p_cl,
                            "bound_satisfied": a_n <= PRE["max_animal_progenitors"] and p_n <= a_n}
    print(json.dumps(results, indent=1), flush=True)
    measured = {
        "value": results["k1859"]["animal_progenitors"],
        "unit": "independent clades (Dollo progenitors) required for the animals of 1859 (Metazoa + Protozoa) on the Open Tree synthetic tree",
        "n": len(tips(root)),
        "uncertainty": f"modern reading: animals {results['modern']['animal_progenitors']}, plants {results['modern']['plant_progenitors']}; 1859 reading: animals {results['k1859']['animal_progenitors']}, plants {results['k1859']['plant_progenitors']}",
        "extra": {"synth_id": about.get("synth_id"), "taxonomy_version": about.get("taxonomy_version"), "readings": results,
                  "unmapped": unmapped, "pruned_from_synth": pruned, "broken_taxa": broken, "mapped_fraction": mapped_frac,
                  "tips": {t.label: assigned.get(t, []) for t in tips(root)}},
    }
    if mapped_frac < PRE["min_mapped_fraction"]:
        verdict, reason = "inconclusive", "data-unavailable"
    elif not results["modern"]["bound_satisfied"]:
        verdict, reason = "refutes", None
    elif results["k1859"]["bound_satisfied"]:
        verdict, reason = "supports", None
    else:
        verdict, reason = "mixed", None
    print("verdict:", verdict)
    json.dump(FETCH_LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=1)
    json.dump({"measured": measured, "verdict": verdict, "reason": reason}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
