#!/usr/bin/env python3
"""Test darwin1859-ch05-06: cave animals are allied to the surface fauna of their own continent.

Data: Open Tree of Life API v3 (TNRS + induced synthetic subtree) and GBIF occurrence
counts (continent verification). Pre-registered taxa: derived/taxa.csv.

Usage: python3 analysis.py [--write-result]
Writes derived/measured.json, derived/files.json, derived/taxa_placed.csv.
"""
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from itertools import combinations

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

OTOL = "https://api.opentreeoflife.org/v3"
GBIF = "https://api.gbif.org/v1"
FILES = []


def _cached(path, fetch):
    """Return (content, retrieved_at); the retrieval time of the first download is kept in a sidecar."""
    meta = path + ".meta"
    if os.path.exists(path) and os.path.exists(meta):
        return open(path, "rb").read(), open(meta).read().strip()
    content = fetch()
    when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    open(path, "wb").write(content)
    open(meta, "w").write(when)
    return content, when


def record(url, content, when, role):
    FILES.append({
        "download_url": url,
        "retrieved_at": when,
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "role": role,
    })


def post_json(url, payload, role, cache_name):
    def fetch():
        for attempt in range(4):
            r = requests.post(url, json=payload, timeout=120)
            if r.status_code in (200, 400):
                break
            time.sleep(2 ** attempt)
        return r.content
    content, when = _cached(os.path.join(DATA, cache_name), fetch)
    record(url, content, when, role)
    return json.loads(content.decode("utf-8"))


def get_json(url, role, cache_name):
    def fetch():
        for attempt in range(5):
            r = requests.get(url, timeout=120)
            if r.status_code == 200:
                break
            time.sleep(2 ** attempt)
        r.raise_for_status()
        return r.content
    content, when = _cached(os.path.join(DATA, cache_name), fetch)
    record(url, content, when, role)
    return json.loads(content.decode("utf-8"))


# ---------------------------------------------------------------- Newick parsing
class Node:
    __slots__ = ("name", "children", "parent")

    def __init__(self, name=None):
        self.name = name
        self.children = []
        self.parent = None


def parse_newick(s):
    s = s.strip()
    if s.endswith(";"):
        s = s[:-1]
    pos = 0

    def parse_node():
        nonlocal pos
        node = Node()
        if s[pos] == "(":
            pos += 1
            while True:
                child = parse_node()
                child.parent = node
                node.children.append(child)
                if s[pos] == ",":
                    pos += 1
                    continue
                if s[pos] == ")":
                    pos += 1
                    break
        m = re.match(r"[^,():;]*", s[pos:])
        label = m.group(0)
        pos += len(label)
        if ":" in s[pos:pos + 1]:
            m2 = re.match(r":[^,()]*", s[pos:])
            pos += len(m2.group(0))
        node.name = label.strip("'\"") or None
        return node

    return parse_node()


def tips(node):
    return [node] if not node.children else [t for c in node.children for t in tips(c)]


def path_to_root(node):
    out = []
    while node is not None:
        out.append(node)
        node = node.parent
    return out


def node_distance(a, b):
    pa = path_to_root(a)
    pb = set(path_to_root(b))
    for i, n in enumerate(pa):
        if n in pb:
            j = path_to_root(b).index(n)
            return i + j
    raise RuntimeError("disconnected")


def all_clades(root):
    out = []

    def rec(n):
        if n.children:
            out.append(n)
            for c in n.children:
                rec(c)
    rec(root)
    return out


# ---------------------------------------------------------------- main
def main():
    write_result = "--write-result" in sys.argv
    taxa = list(csv.DictReader(open(os.path.join(DERIVED, "taxa.csv"))))
    names = [t["name"] for t in taxa]

    about = post_json(f"{OTOL}/tree_of_life/about", {}, "synthetic tree version", "otol_about.json")
    synth_id = about.get("synth_id")

    tnrs = post_json(f"{OTOL}/tnrs/match_names",
                     {"names": names, "context_name": "Animals", "do_approximate_matching": False},
                     "TNRS name matching", "otol_tnrs.json")
    ott = {}
    for res in tnrs["results"]:
        matches = [m for m in res["matches"] if not m.get("is_synonym")] or res["matches"]
        if matches:
            ott[res["name"]] = matches[0]["taxon"]["ott_id"]
    unmatched = [n for n in names if n not in ott]

    # GBIF continent verification
    continent_rows = []
    for t in taxa:
        name = t["name"]
        key = name.replace(" ", "_")
        m = get_json(f"{GBIF}/species/match?name={requests.utils.quote(name)}&kingdom=Animalia",
                     "GBIF backbone match", f"gbif_match_{key}.json")
        usage = m.get("usageKey") if m.get("matchType") in ("EXACT", "FUZZY") and m.get("rank") == "SPECIES" else None
        counts = {}
        if usage:
            for cont in ("NORTH_AMERICA", "EUROPE"):
                d = get_json(f"{GBIF}/occurrence/search?limit=0&taxonKey={usage}&continent={cont}",
                             "GBIF occurrence counts by continent", f"gbif_count_{key}_{cont}.json")
                counts[cont] = d["count"]
        na, eu = counts.get("NORTH_AMERICA", 0), counts.get("EUROPE", 0)
        tot = na + eu
        frac_pre = None
        if tot > 0:
            frac_pre = (na if t["continent"] == "NA" else eu) / tot
        keep = frac_pre is not None and frac_pre >= 0.90
        continent_rows.append({**t, "gbif_usageKey": usage, "gbif_NA": na, "gbif_EU": eu,
                               "frac_on_preregistered_continent": None if frac_pre is None else round(frac_pre, 4),
                               "ott_id": ott.get(name), "continent_verified": keep})

    # Induced subtree. Remove ids not in the synthetic tree (API reports them).
    candidate = [r for r in continent_rows if r["continent_verified"] and r["ott_id"]]
    ids = [r["ott_id"] for r in candidate]
    resp = post_json(f"{OTOL}/tree_of_life/induced_subtree", {"ott_ids": ids, "label_format": "name_and_id"},
                     "induced synthetic subtree", "otol_induced_1.json")
    if "newick" not in resp:
        # The API lists ott ids that are not in the synthetic tree; drop them and retry once.
        msg = json.dumps(resp)
        unknown = set(int(x) for x in re.findall(r"ott(\d+)", msg)) | set(
            int(x) for x in re.findall(r'"(\d+)"', msg) if int(x) in ids)
        ids2 = [i for i in ids if i not in unknown]
        resp = post_json(f"{OTOL}/tree_of_life/induced_subtree", {"ott_ids": ids2, "label_format": "name_and_id"},
                         "induced synthetic subtree (after dropping taxa absent from synth)", "otol_induced_2.json")
    newick = resp["newick"]
    broken = resp.get("broken", {})
    open(os.path.join(DERIVED, "induced_tree.nwk"), "w").write(newick + "\n")

    root = parse_newick(newick)
    tipnodes = tips(root)
    by_ott = {}
    for tn in tipnodes:
        m = re.search(r"ott(\d+)$", tn.name or "")
        if m:
            by_ott[int(m.group(1))] = tn
    placed = []
    for r in candidate:
        tn = by_ott.get(r["ott_id"])
        r["placed"] = tn is not None
        if tn is not None:
            placed.append((r, tn))

    # Per cave taxon: nearest same-continent vs nearest other-continent cave
    rows = []
    for r, tn in placed:
        if r["habitat"] != "cave":
            continue
        d_same = min((node_distance(tn, tn2) for r2, tn2 in placed if tn2 is not tn and r2["continent"] == r["continent"]),
                     default=None)
        d_oc = min((node_distance(tn, tn2) for r2, tn2 in placed
                    if r2["continent"] != r["continent"] and r2["habitat"] == "cave"), default=None)
        ok = None if (d_same is None or d_oc is None) else d_same <= d_oc
        rows.append({"group": r["group"], "name": r["name"], "continent": r["continent"],
                     "d_same_continent": d_same, "d_other_continent_cave": d_oc, "same_le_othercave": ok})

    # Exclusive transcontinental cave clades (minimal ones)
    tipinfo = {tn: r for r, tn in placed}
    excl = []
    for cl in all_clades(root):
        ts = [t for t in tips(cl) if t in tipinfo]
        if len(ts) < 2:
            continue
        habitats = {tipinfo[t]["habitat"] for t in ts}
        conts = {tipinfo[t]["continent"] for t in ts}
        if habitats == {"cave"} and conts == {"NA", "EU"}:
            excl.append(sorted(tipinfo[t]["name"] for t in ts))
    # keep only minimal clades (not supersets of another)
    minimal = [c for c in excl if not any(set(o) < set(c) for o in excl)]
    groups_with_excl = sorted({tipinfo[t]["group"] for c in minimal for t in tipinfo if tipinfo[t]["name"] in c})

    evaluable = [x for x in rows if x["same_le_othercave"] is not None]
    n_ok = sum(1 for x in evaluable if x["same_le_othercave"])
    frac = n_ok / len(evaluable) if evaluable else None
    groups_placed = sorted({x["group"] for x in rows})

    with open(os.path.join(DERIVED, "taxa_placed.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(continent_rows[0].keys()) + ["placed"])
        w.writeheader()
        for r in continent_rows:
            w.writerow({**r, "placed": r.get("placed", False)})
    with open(os.path.join(DERIVED, "cave_taxa_distances.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    if frac is None or len(evaluable) < 10 or len(groups_placed) < 3:
        verdict = "inconclusive"
    elif frac >= 0.70 and len(minimal) == 0:
        verdict = "supports"
    elif frac < 0.50 or len(groups_with_excl) >= 2:
        verdict = "refutes"
    else:
        verdict = "mixed"

    measured = {
        "value": None if frac is None else round(frac, 4),
        "unit": "fraction of cave taxa with nearest same-continent taxon at least as close as nearest other-continent cave taxon",
        "n": len(evaluable),
        "uncertainty": None if frac is None else f"95% Wilson CI {wilson(n_ok, len(evaluable))}",
        "extra": {
            "synth_id": synth_id,
            "taxa_preregistered": len(taxa),
            "taxa_unmatched_by_tnrs": unmatched,
            "taxa_failed_continent_check": [r["name"] for r in continent_rows if not r["continent_verified"]],
            "taxa_absent_from_synth_tree": [r["name"] for r in candidate if not r.get("placed")],
            "broken_taxa_reported_by_api": list(broken.keys()) if isinstance(broken, dict) else broken,
            "tips_in_induced_tree": len(placed),
            "cave_taxa_evaluated": len(evaluable),
            "cave_taxa_satisfying": n_ok,
            "cave_taxa_by_continent": {c: sum(1 for x in evaluable if x["continent"] == c) for c in ("NA", "EU")},
            "fraction_by_continent": {c: (sum(1 for x in evaluable if x["continent"] == c and x["same_le_othercave"]) /
                                          max(1, sum(1 for x in evaluable if x["continent"] == c))) for c in ("NA", "EU")},
            "groups_placed": groups_placed,
            "exclusive_transcontinental_cave_clades": minimal,
            "groups_with_exclusive_transcontinental_cave_clades": groups_with_excl,
            "rule_based_verdict": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(FILES, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    print(json.dumps(measured, indent=2))
    for x in rows:
        print(x)

    if write_result:
        rp = os.path.join(HERE, "result.json")
        res = json.load(open(rp))
        res["measured"] = measured
        by_role = {"open-tree-of-life-synth-v15": [], "gbif-occurrence-api": []}
        for fobj in FILES:
            k = "gbif-occurrence-api" if "gbif.org" in fobj["download_url"] else "open-tree-of-life-synth-v15"
            by_role[k].append(fobj)
        for ds in res["datasets"]:
            fl = by_role.get(ds["id"], [])
            if ds["id"] == "gbif-occurrence-api":
                # summarise the many small GBIF calls: keep one aggregate record plus the list in derived/files.json
                ds["files"] = [{
                    "download_url": f"{GBIF}/species/match and {GBIF}/occurrence/search?limit=0&taxonKey=<k>&continent=<c> (per-call list in derived/files.json)",
                    "retrieved_at": fl[0]["retrieved_at"] if fl else None,
                    "byte_size": sum(f["byte_size"] for f in fl),
                    "sha256": hashlib.sha256("".join(f["sha256"] for f in fl).encode()).hexdigest(),
                    "note": f"{len(fl)} API responses; sha256 here is the SHA-256 of the concatenated per-response SHA-256 hex digests",
                }]
            else:
                ds["files"] = [{k: v for k, v in f.items() if k != "role"} | {"note": f["role"]} for f in fl]
                ds["version"] = synth_id
        json.dump(res, open(rp, "w"), indent=2, ensure_ascii=False)
        open(rp, "a").write("\n")


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return f"[{(centre - half) / denom:.3f}, {(centre + half) / denom:.3f}]"


if __name__ == "__main__":
    main()
