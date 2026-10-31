#!/usr/bin/env python3
"""Test of darwin1859-ch12-12: island endemics are related to species of the nearest continent
(native regions of the nearest outside relatives of island endemics on Open Tree genus subtrees).

Requires: requests, numpy, pandas, scipy.
Data: WCVP checklist (Kew; 88 MB zip cached in /tmp, not committed) and the Open Tree of Life
v3 API (TNRS and induced subtrees; responses cached in /tmp). Every file and request with URL,
time, size and SHA-256 goes to derived/fetch_log.csv.gz; per-endemic outcomes to
derived/endemics.csv.gz; per-island-group statistics to derived/groups.csv.
"""
import hashlib
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)
PRE = json.load(open(os.path.join(HERE, "result.json")))["preregistration"]
CACHE = os.environ.get("DELPHI_CACHE", "/tmp/delphi-data")
OT_CACHE = os.path.join(CACHE, "opentree")
os.makedirs(OT_CACHE, exist_ok=True)
LOG = []
S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_file(url, name):
    path = os.path.join(CACHE, name)
    when = None
    if not os.path.exists(path):
        with S.get(url, stream=True, timeout=1800) as r:
            r.raise_for_status()
            with open(path + ".part", "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        os.rename(path + ".part", path)
        when = now()
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    LOG.append({"download_url": url, "request_body_sha256": "", "retrieved_at": when or datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "byte_size": os.path.getsize(path), "sha256": h.hexdigest()})
    return path


def ot_post(url, body):
    """POST to the Open Tree API with an on-disk cache; returns (status, json)."""
    raw_body = json.dumps(body, sort_keys=True)
    key = hashlib.sha256((url + raw_body).encode()).hexdigest()
    path = os.path.join(OT_CACHE, key + ".json")
    if os.path.exists(path):
        rec = json.load(open(path))
    else:
        for attempt in range(6):
            try:
                r = S.post(url, data=raw_body, headers={"content-type": "application/json"}, timeout=300)
                if r.status_code in (200, 400):
                    break
                print("HTTP", r.status_code, url, file=sys.stderr)
            except requests.RequestException as e:
                print("retry", attempt, e, file=sys.stderr)
            time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError("Open Tree request failed")
        rec = {"status": r.status_code, "retrieved_at": now(), "byte_size": len(r.content),
               "sha256": hashlib.sha256(r.content).hexdigest(), "text": r.text}
        json.dump(rec, open(path, "w"))
    LOG.append({"download_url": url, "request_body_sha256": hashlib.sha256(raw_body.encode()).hexdigest(),
                "retrieved_at": rec["retrieved_at"], "byte_size": rec["byte_size"], "sha256": rec["sha256"]})
    return rec["status"], json.loads(rec["text"])


def load_wcvp():
    z = zipfile.ZipFile(fetch_file(PRE["wcvp_url"], "wcvp.zip"))
    names = pd.read_csv(z.open("wcvp_names.csv"), sep="|", dtype=str, keep_default_na=False,
                        usecols=["plant_name_id", "taxon_rank", "taxon_status", "genus_hybrid", "genus", "species_hybrid", "species"])
    names = names[(names.taxon_rank == "Species") & (names.taxon_status == "Accepted")
                  & (names.genus_hybrid == "") & (names.species_hybrid == "")].copy()
    names["binomial"] = names.genus + " " + names.species
    names = names.drop_duplicates("binomial", keep=False)
    dist = pd.read_csv(z.open("wcvp_distribution.csv"), sep="|", dtype=str, keep_default_na=False,
                       usecols=["plant_name_id", "continent_code_l1", "region_code_l2", "area_code_l3", "introduced", "location_doubtful"])
    dist = dist[dist.plant_name_id.isin(names.plant_name_id) & (dist.location_doubtful == "0") & (dist.introduced == "0")]
    return names, dist


def tnrs(binomials):
    out = {}
    names = sorted(set(binomials))
    for i in range(0, len(names), 1000):
        chunk = names[i:i + 1000]
        st, d = ot_post("https://api.opentreeoflife.org/v3/tnrs/match_names",
                        {"names": chunk, "context_name": PRE["tnrs_context"], "do_approximate_matching": False})
        if st != 200:
            raise RuntimeError(f"TNRS error: {d}")
        for res in d["results"]:
            nm = res["name"]
            exact = [m for m in res["matches"] if not m.get("is_approximate_match") and m["taxon"].get("name") == nm
                     and m["taxon"].get("rank") == "species"]
            accepted = [m for m in exact if not m.get("is_synonym")]
            pick = (accepted or exact)
            if len(pick) == 1 or (pick and len({m["taxon"]["ott_id"] for m in pick}) == 1):
                out[nm] = pick[0]["taxon"]["ott_id"]
    return out


def induced_subtree(ott_ids):
    ids = sorted(set(ott_ids))
    for _ in range(5):
        if len(ids) < 2:
            return None
        st, d = ot_post("https://api.opentreeoflife.org/v3/tree_of_life/induced_subtree",
                        {"ott_ids": ids, "label_format": "id"})
        if st == 200:
            return d["newick"]
        bad = set()
        for k in ("unknown", "broken"):
            if isinstance(d.get(k), dict):
                bad |= {int(re.sub(r"\D", "", x)) for x in d[k] if re.sub(r"\D", "", x)}
        if not bad:
            msg = json.dumps(d)
            bad = {int(x) for x in re.findall(r"ott(\d+)", msg)}
        if not bad:
            return None
        ids = [i for i in ids if i not in bad]
    return None


def parse_newick(nwk):
    """Return (parent list, tip label dict node->label)."""
    parent, labels, stack = [-1], {}, [0]
    cur, i, n = 0, 0, len(nwk)
    while i < n:
        c = nwk[i]
        if c == "(":
            parent.append(cur)
            cur = len(parent) - 1
            stack.append(cur)
            i += 1
        elif c == ",":
            p = parent[cur]
            parent.append(p)
            cur = len(parent) - 1
            i += 1
        elif c == ")":
            cur = parent[cur]
            i += 1
        elif c == ";":
            break
        else:
            j = i
            while j < n and nwk[j] not in "(),;":
                j += 1
            labels[cur] = nwk[i:j].split(":")[0].strip("'")
            i = j
    children = {}
    for k, p in enumerate(parent):
        if p >= 0:
            children.setdefault(p, []).append(k)
    tips = {k: v for k, v in labels.items() if k not in children}
    return parent, children, tips


def clade_tips(node, children, tipset):
    out, st = [], [node]
    while st:
        x = st.pop()
        if x in tipset:
            out.append(x)
        st.extend(children.get(x, []))
    return out


def genus_trees(names, genera):
    sub = names[names.genus.isin(genera)]
    ott = tnrs(sub.binomial)
    sub = sub.assign(ott=sub.binomial.map(ott)).dropna(subset=["ott"])
    trees = {}
    for g, s in sub.groupby("genus"):
        nwk = induced_subtree(s.ott.astype(int).tolist())
        if not nwk:
            continue
        parent, children, tips = parse_newick(nwk)
        id2pid = dict(zip(s.ott.astype(int), s.plant_name_id))
        tip_pid = {}
        for node, lab in tips.items():
            m = re.fullmatch(r"ott(\d+)", lab)
            if m and int(m.group(1)) in id2pid:
                tip_pid[node] = id2pid[int(m.group(1))]
        trees[g] = (parent, children, tip_pid)
    return trees, len(sub)


def main():
    names, dist = load_wcvp()
    native_regions = dist.groupby("plant_name_id").area_code_l3.apply(frozenset)
    geo = dist[(dist.area_code_l3 != "") & (dist.continent_code_l1 != "") & (dist.region_code_l2 != "")]
    geo = geo.drop_duplicates("area_code_l3").set_index("area_code_l3")
    l3_l1 = geo.continent_code_l1.astype(int)
    l3_l2 = geo.region_code_l2.astype(int)
    pid_genus = names.set_index("plant_name_id").genus
    genus_size = names.groupby("genus").size()
    groups = PRE["island_groups"]
    endemics, near_l3 = {}, {}
    for gname, spec in groups.items():
        cs = frozenset(spec["l3"])
        endemics[gname] = {p for p, regs in native_regions.items() if regs <= cs}
        own_l2 = {int(l3_l2[c]) for c in spec["l3"] if c in l3_l2.index}
        near_l3[gname] = frozenset(c for c in l3_l1.index
                                   if l3_l1[c] in spec["near_l1"] or (PRE["near_also_own_l2"] and l3_l2[c] in own_l2)) - cs
    focal_genera = {pid_genus[p] for e in endemics.values() for p in e}
    focal_genera = {g for g in focal_genera if genus_size[g] <= PRE["max_genus_species"]}
    print("island endemics:", {k: len(v) for k, v in endemics.items()}, "genera:", len(focal_genera), flush=True)
    trees, n_matched = genus_trees(names, sorted(focal_genera))
    print("genus trees:", len(trees), "species matched in Open Tree:", n_matched, flush=True)

    rows, ctrl = [], []
    for gname, spec in groups.items():
        cs, near = frozenset(spec["l3"]), near_l3[gname]
        for g in sorted({pid_genus[p] for p in endemics[gname]} & set(trees)):
            parent, children, tip_pid = trees[g]
            tipset = set(tip_pid)
            outside = {t for t in tipset if not (native_regions.get(tip_pid[t], frozenset()) & cs)}
            if not outside:
                continue
            ctrl.extend({"group": gname, "genus": g, "near": bool(native_regions.get(tip_pid[t], frozenset()) & near)} for t in outside)
            for t in tipset:
                if tip_pid[t] not in endemics[gname]:
                    continue
                node = parent[t]
                while True:
                    rel = [x for x in clade_tips(node, children, tipset) if x in outside]
                    if rel:
                        break
                    node = parent[node]
                n_near = sum(bool(native_regions.get(tip_pid[x], frozenset()) & near) for x in rel)
                rows.append({"group": gname, "genus": g, "plant_name_id": tip_pid[t], "n_outside_relatives": len(rel),
                             "n_near": n_near, "near_related": n_near / len(rel) > 0.5})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "endemics.csv.gz"), index=False, compression="gzip")
    C = pd.DataFrame(ctrl)
    G = []
    for gname, s in df.groupby("group"):
        c = C[C.group == gname]
        G.append({"group": gname, "n_focal": len(s), "s_near": float(s.near_related.mean()),
                  "single_relative_share": float((s.n_outside_relatives == 1).mean()),
                  "control_congeners_near": float(c.near.mean()) if len(c) else np.nan,
                  "genera": s.genus.nunique(), "n_near_l3": len(near_l3[gname])})
    G = pd.DataFrame(G)
    G.to_csv(os.path.join(DERIVED, "groups.csv"), index=False, float_format="%.4f")
    use = G[G.n_focal >= PRE["min_focal_per_group"]]
    n = len(use)
    sub = df[df.group.isin(use.group)]
    pooled = float(sub.near_related.mean()) if n else np.nan
    n_ge06 = int((use.s_near >= 0.6).sum())
    n_lt05 = int((use.s_near < 0.5).sum())
    measured = {
        "value": round(pooled, 4),
        "unit": "pooled fraction of island endemics whose nearest outside relatives (smallest clade on the Open Tree genus subtree) are mostly native to the nearest continent or the island group's own region",
        "n": int(n),
        "uncertainty": f"island groups with s >= 0.6: {n_ge06}/{n}; with s < 0.5: {n_lt05}/{n}; endemics scored: {len(sub)}",
        "extra": {
            "n_endemics_scored": int(len(sub)),
            "groups_s_ge_0.6": n_ge06,
            "groups_s_lt_0.5": n_lt05,
            "share_endemics_with_single_outside_relative": float((sub.n_outside_relatives == 1).mean()) if n else None,
            "median_outside_relatives": float(sub.n_outside_relatives.median()) if n else None,
            "post_hoc_single_outside_relative": {
                "note": "not pre-registered; endemics whose nearest outside clade is a single species",
                "n": int((sub.n_outside_relatives == 1).sum()),
                "pooled_s_near": float(sub[sub.n_outside_relatives == 1].near_related.mean()),
                "per_group": {k: {"n": int(v.size), "s_near": round(float(v.mean()), 3)}
                              for k, v in sub[sub.n_outside_relatives == 1].groupby("group").near_related},
            },
            "groups_dropped": G[~G.group.isin(use.group)].group.tolist() + [g for g in groups if g not in set(G.group)],
            "n_genus_trees": len(trees),
            "per_group": {r.group: {"s_near": round(r.s_near, 3), "control_congeners_near": round(r.control_congeners_near, 3),
                                    "n": int(r.n_focal), "single_relative_share": round(r.single_relative_share, 3)} for r in use.itertuples()},
        },
    }
    if n < PRE["min_groups"]:
        verdict = "inconclusive"
    elif pooled < 0.5 or n_lt05 > n / 2:
        verdict = "refutes"
    elif pooled >= 0.75 and n_ge06 >= 0.75 * n:
        verdict = "supports"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1, default=int))
    print("verdict:", verdict)
    pd.DataFrame(LOG).drop_duplicates().to_csv(os.path.join(DERIVED, "fetch_log.csv.gz"), index=False, compression="gzip")
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1, default=int)


if __name__ == "__main__":
    main()
