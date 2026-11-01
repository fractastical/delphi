#!/usr/bin/env python3
"""Test of darwin1859-ch12-13: species on the islands of one archipelago are each other's closest
relatives (nearest-clade composition of archipelago endemics on Open Tree genus subtrees).

Requires: requests, numpy, pandas, scipy.
Data: WCVP checklist (Kew; 88 MB zip cached in /tmp, not committed) and the Open Tree of Life
v3 API (TNRS and induced subtrees; responses cached in /tmp). Every file and request with URL,
time, size and SHA-256 goes to derived/fetch_log.csv.gz; per-endemic outcomes to
derived/endemics.csv.gz; per-archipelago statistics to derived/archipelagos.csv.
"""
import gzip
import hashlib
import json
import os
import re
import sys
import time
import zipfile
from datetime import datetime, timezone
from math import comb

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
    pid_genus = names.set_index("plant_name_id").genus
    genus_size = names.groupby("genus").size()
    groups = PRE["archipelagos"]
    endemics = {}
    for gname, codes in groups.items():
        cs = frozenset(codes)
        endemics[gname] = {p for p, regs in native_regions.items() if regs <= cs}
    focal_genera = {pid_genus[p] for e in endemics.values() for p in e}
    focal_genera = {g for g in focal_genera if genus_size[g] <= PRE["max_genus_species"]}
    print("archipelago endemics:", {k: len(v) for k, v in endemics.items()}, "genera:", len(focal_genera), flush=True)
    trees, n_matched = genus_trees(names, sorted(focal_genera))
    print("genus trees:", len(trees), "species matched in Open Tree:", n_matched, flush=True)

    rng = np.random.default_rng(PRE["seed"])
    rows, arch = [], []
    for gname, codes in groups.items():
        cs = frozenset(codes)
        for g in sorted({pid_genus[p] for p in endemics[gname]} & set(trees)):
            parent, children, tip_pid = trees[g]
            tipset = set(tip_pid)
            is_in = {t: bool(native_regions.get(tip_pid[t], frozenset()) & cs) for t in tipset}
            M = len(tipset) - 1
            for t in tipset:
                if tip_pid[t] not in endemics[gname]:
                    continue
                m = sum(is_in[x] for x in tipset if x != t)
                if m < 1 or M - m < 1:
                    continue
                node = parent[t]
                while True:
                    others = [x for x in clade_tips(node, children, tipset) if x != t]
                    if others:
                        break
                    node = parent[node]
                k = len(others)
                n_in = sum(is_in[x] for x in others)
                outcome = "inside" if n_in == k else ("outside" if n_in == 0 else "tie")
                p_in = comb(m, k) / comb(M, k)
                p_out = comb(M - m, k) / comb(M, k)
                rows.append({"archipelago": gname, "genus": g, "plant_name_id": tip_pid[t], "k": k, "M": M, "m": m,
                             "outcome": outcome, "p_in": p_in, "p_out": p_out})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(DERIVED, "endemics.csv.gz"), index=False, compression="gzip", float_format="%.5g")
    for gname, s in df.groupby("archipelago"):
        n_in, n_out, n_tie = (s.outcome == "inside").sum(), (s.outcome == "outside").sum(), (s.outcome == "tie").sum()
        res = n_in + n_out
        f = n_in / res if res else np.nan
        u = rng.random((PRE["null_draws"], len(s)))
        sim_in = (u < s.p_in.values).sum(1)
        sim_out = ((u >= s.p_in.values) & (u < s.p_in.values + s.p_out.values)).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            f_null = sim_in / (sim_in + sim_out)
        f_null = f_null[~np.isnan(f_null)]
        arch.append({"archipelago": gname, "n_focal": len(s), "inside": int(n_in), "outside": int(n_out), "tie": int(n_tie),
                     "f_in": f, "f_null_mean": float(f_null.mean()), "p_sim": float((f_null >= f).mean()) if res else np.nan,
                     "genera": s.genus.nunique()})
    A = pd.DataFrame(arch)
    A.to_csv(os.path.join(DERIVED, "archipelagos.csv"), index=False, float_format="%.4f")
    use = A[(A.inside + A.outside) >= PRE["min_resolved_per_archipelago"]]
    n = len(use)
    pooled = float(use.inside.sum() / (use.inside.sum() + use.outside.sum())) if n else np.nan
    n_sig = int(((use.f_in > 0.5) & (use.p_sim < 0.05)).sum())
    n_not_above_null = int((use.f_in <= use.f_null_mean).sum())
    measured = {
        "value": round(pooled, 4),
        "unit": "pooled fraction of archipelago endemics whose nearest clade on the Open Tree genus subtree is entirely native to the same archipelago (among resolved inside/outside outcomes)",
        "n": int(n),
        "uncertainty": f"archipelagos with f_in > 0.5 and simulated p < 0.05: {n_sig}/{n}; with f_in <= null: {n_not_above_null}/{n}",
        "extra": {
            "n_endemics_scored": int(use.n_focal.sum()),
            "n_inside": int(use.inside.sum()), "n_outside": int(use.outside.sum()), "n_tie": int(use.tie.sum()),
            "tie_fraction": float(use.tie.sum() / use.n_focal.sum()) if n else None,
            "pooled_null_expectation": float((use.f_null_mean * (use.inside + use.outside)).sum() / (use.inside + use.outside).sum()) if n else None,
            "archipelagos_sig_above_half": n_sig,
            "archipelagos_not_above_null": n_not_above_null,
            "archipelagos_dropped": A[~A.archipelago.isin(use.archipelago)].archipelago.tolist()
                                    + [g for g in groups if g not in set(A.archipelago)],
            "n_genus_trees": len(trees),
            "per_archipelago": {r.archipelago: {"f_in": round(float(r.f_in), 3), "null": round(r.f_null_mean, 3), "p": round(r.p_sim, 4),
                                                "inside": r.inside, "outside": r.outside, "tie": r.tie} for r in use.itertuples()},
        },
    }
    if n < PRE["min_archipelagos"]:
        verdict = "inconclusive"
    elif pooled <= 0.5 or n_not_above_null > n / 2:
        verdict = "refutes"
    elif pooled >= 0.67 and n_sig >= 0.75 * n:
        verdict = "supports"
    else:
        verdict = "mixed"
    print(json.dumps(measured, indent=1, default=int))
    print("verdict:", verdict)
    pd.DataFrame(LOG).drop_duplicates().to_csv(os.path.join(DERIVED, "fetch_log.csv.gz"), index=False, compression="gzip")
    json.dump({"measured": measured, "verdict": verdict}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1, default=int)


if __name__ == "__main__":
    main()
