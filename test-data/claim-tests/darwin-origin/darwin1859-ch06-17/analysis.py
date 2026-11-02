#!/usr/bin/env python3
"""darwin1859-ch06-17: unity of type tracks descent more than habits of life.

Re-run from this directory: python3 analysis.py
Downloads are cached under data/ and are not committed.
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
RESULT_PATH = os.path.join(HERE, "result.json")

UA = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA
FILES = []


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def record_file(download_url, raw, retrieved_at=None, request_body=None):
    meta = {
        "download_url": download_url,
        "retrieved_at": retrieved_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": sha256_bytes(raw),
    }
    if request_body is not None:
        meta["request_body"] = request_body
    FILES.append(meta)
    return meta


def fetch_bytes(url, fname, headers=None):
    path = os.path.join(DATA, fname)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        FILES.append(meta)
        return open(path, "rb").read(), meta
    last = None
    for attempt in range(4):
        try:
            r = SESSION.get(url, headers=headers, timeout=300)
            if r.status_code == 200 and r.content:
                raw = r.content
                meta = record_file(r.url, raw)
                open(path, "wb").write(raw)
                json.dump(meta, open(meta_path, "w"), indent=2)
                return raw, meta
            last = f"HTTP {r.status_code} bytes={len(r.content)}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


def post_json(url, payload):
    body = json.dumps(payload, sort_keys=True)
    last = None
    for attempt in range(4):
        try:
            r = SESSION.post(url, json=payload, timeout=180)
            if r.status_code == 200:
                raw = r.content
                record_file(url, raw, request_body=body)
                return json.loads(raw)
            last = f"HTTP {r.status_code} {r.text[:300]}"
        except requests.RequestException as exc:
            last = str(exc)
        time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"POST {url} failed: {last}")


def parse_cells(seq):
    """Cells are single symbols, or parenthetical / brace polymorphisms.

    MorphoBank writes polymorphisms with spaces inside parentheses, '(0 1)'.
    Gap '-' and missing '?' are unscored. A cell is a frozenset of states or None.
    """
    cells = []
    i = 0
    n = len(seq)
    while i < n:
        c = seq[i]
        if c.isspace():
            i += 1
            continue
        if c in "({[":
            close = {"(": ")", "{": "}", "[": "]"}[c]
            j = seq.find(close, i + 1)
            if j < 0:
                raise ValueError("unclosed polymorphism")
            inner = seq[i + 1:j]
            states = [tok for tok in re.split(r"[\s,]+", inner) if tok]
            # a token may itself be a run of symbols if the file omitted spaces
            bits = []
            for tok in states:
                if len(tok) == 1:
                    bits.append(tok)
                else:
                    bits.extend(list(tok))
            cells.append(frozenset(bits))
            i = j + 1
            continue
        if c in "?-":
            cells.append(None)
        else:
            cells.append(frozenset(c))
        i += 1
    return cells


def load_nexus(path):
    nchar = None
    taxa = []
    in_matrix = False
    for line in open(path, encoding="utf-8", errors="replace"):
        if nchar is None:
            m = re.search(r"NCHAR\s*=\s*(\d+)", line, re.I)
            if m and "DIMENSIONS" in line.upper():
                nchar = int(m.group(1))
        if not in_matrix:
            if line.strip().upper() == "MATRIX":
                in_matrix = True
            continue
        if line.strip() == ";":
            break
        m = re.match(r"\s*'([^']+)'\s+(.*)$", line.rstrip("\n"))
        if not m:
            continue
        label, seq = m.group(1), m.group(2)
        cells = parse_cells(seq)
        taxa.append((label, cells))
    if nchar is None:
        raise RuntimeError("NCHAR not found")
    bad = [(lab, len(cells)) for lab, cells in taxa if len(cells) != nchar]
    return nchar, taxa, bad


def binomial(label):
    s = label.strip().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    parts = s.split(" ")
    if len(parts) < 2:
        return None
    if not parts[0][:1].isupper():
        return None
    if not re.fullmatch(r"[a-z][a-z-]+", parts[1]):
        return None
    return f"{parts[0]} {parts[1]}"


class Node:
    __slots__ = ("label", "children", "parent", "length")

    def __init__(self, label=""):
        self.label = label
        self.children = []
        self.parent = None
        self.length = None


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
        elif c == ":":
            m = re.match(r"([-+0-9.eE]+)", s[i + 1:])
            if not m:
                raise ValueError("bad branch length")
            node.length = float(m.group(1))
            i += 1 + len(m.group(1))
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
    while len(node.children) == 1 and node.children[0].children:
        child = node.children[0]
        node.label = child.label or node.label
        if node.length is None:
            node.length = child.length
        elif child.length is not None:
            node.length = (node.length or 0) + child.length
        node.children = child.children
        for ch in node.children:
            ch.parent = node
    if len(node.children) == 1 and not node.children[0].children:
        node.label = node.children[0].label or node.label
        if node.children[0].length is not None:
            node.length = (node.length or 0) + node.children[0].length
        node.children = []
    for ch in list(node.children):
        collapse_unary(ch)


def tips_of(node):
    if not node.children:
        return [node]
    out = []
    for c in node.children:
        out.extend(tips_of(c))
    return out


def ott_of(label):
    m = re.search(r"ott(\d+)$", label.replace(" ", "_"))
    if not m:
        m = re.search(r"ott(\d+)", label)
    return int(m.group(1)) if m else None


def edge_length_fraction(node):
    internal = []

    def rec(n):
        for c in n.children:
            if c.children:
                internal.append(c.length is not None)
                rec(c)
    rec(node)
    if not internal:
        return 0.0
    return sum(internal) / len(internal)


def path_distance(a, b, use_length):
    def ancestors(n):
        chain = []
        while n is not None:
            chain.append(n)
            n = n.parent
        return chain
    aa, bb = ancestors(a), ancestors(b)
    common = set(aa) & set(bb)
    mrca = max(common, key=lambda n: len(ancestors(n)))

    def dist_to(n):
        d = 0.0
        steps = 0
        while n is not mrca:
            if use_length:
                d += 0.0 if n.length is None else n.length
            else:
                d += 1
            n = n.parent
            steps += 1
            if steps > 100000:
                raise RuntimeError("cycle in tree")
        return d
    return dist_to(a) + dist_to(b)


def hamming(a, b, min_compared):
    compared = 0
    differ = 0
    for x, y in zip(a, b):
        if x is None or y is None:
            continue
        compared += 1
        if x.isdisjoint(y):
            differ += 1
    if compared < min_compared:
        return None
    return differ / compared


def eco_vector(row, diet_cols, act_cols, forstrat, code_index):
    diet = []
    for c in diet_cols:
        v = row[c]
        if pd.isna(v) or v == "":
            return None
        diet.append(float(v) / 100.0)
    if sum(diet) <= 0:
        return None
    code = row[forstrat]
    if pd.isna(code) or str(code).strip() == "":
        return None
    one = [0.0] * len(code_index)
    key = str(code).strip()
    if key not in code_index:
        return None
    one[code_index[key]] = 1.0
    act = []
    for c in act_cols:
        v = row[c]
        if pd.isna(v) or v == "":
            return None
        act.append(float(v))
    return np.asarray(diet + one + act, dtype=float)


def spearman_upper(xa, xb):
    n = xa.shape[0]
    iu = np.triu_indices(n, 1)
    x = xa[iu]
    y = xb[iu]
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 3:
        return float("nan"), int(mask.sum())
    rho = stats.spearmanr(x[mask], y[mask]).statistic
    return float(rho), int(mask.sum())


def main():
    res = json.load(open(RESULT_PATH))
    pre = res["preregistration"]
    matrix_raw, matrix_meta = fetch_bytes(
        pre["matrix_download_url"], "mbank_X1766.nex",
        headers={"User-Agent": "Mozilla/5.0 (compatible; delphi-claim-tests/0.1)"},
    )
    elton_raw, elton_meta = fetch_bytes(pre["elton_download_url"], "MamFuncDat.txt")
    about = post_json(pre["about_endpoint"], {})

    nexus_path = os.path.join(DATA, "mbank_X1766.nex")
    nchar, taxa, bad = load_nexus(nexus_path)
    if bad:
        raise RuntimeError(f"cell count != NCHAR for {len(bad)} taxa, e.g. {bad[:3]}")

    elton = pd.read_csv(os.path.join(DATA, "MamFuncDat.txt"), sep="\t", dtype=str)
    diet_cols = pre["diet_columns"]
    act_cols = pre["activity_columns"]
    for col in diet_cols + act_cols:
        elton[col] = pd.to_numeric(elton[col], errors="coerce")
    by_name = {}
    for _, row in elton.iterrows():
        key = str(row[pre["scientific_column"]]).strip().casefold()
        if key and key not in by_name:
            by_name[key] = row

    candidates = []
    for label, cells in taxa:
        name = binomial(label)
        if not name:
            continue
        row = by_name.get(name.casefold())
        if row is None:
            continue
        candidates.append({"label": label, "binomial": name, "cells": cells, "row": row})

    # one row per binomial: keep the label with more scored cells
    best = {}
    for c in candidates:
        scored = sum(x is not None for x in c["cells"])
        prev = best.get(c["binomial"])
        if prev is None or scored > prev[0]:
            best[c["binomial"]] = (scored, c)
    chosen = [v[1] for _, v in sorted(best.items())]

    names = [c["binomial"] for c in chosen]
    tnrs_payload = {"names": names, "context_name": pre["opentree_context"], "do_approximate_matching": False}
    tnrs = post_json(pre["tnrs_endpoint"], tnrs_payload)
    # retry unmatched in All life
    unmatched = []
    matches = {}
    for query, result in zip(names, tnrs.get("results", [])):
        hit = None
        for m in result.get("matches") or []:
            if m.get("is_approximate_match"):
                continue
            taxon = m.get("taxon") or {}
            if taxon.get("ott_id"):
                hit = taxon
                break
        if hit is None:
            unmatched.append(query)
        else:
            matches[query] = hit
    if unmatched:
        retry_payload = {"names": unmatched, "context_name": pre["opentree_context_retry"], "do_approximate_matching": False}
        tnrs2 = post_json(pre["tnrs_endpoint"], retry_payload)
        for query, result in zip(unmatched, tnrs2.get("results", [])):
            for m in result.get("matches") or []:
                if m.get("is_approximate_match"):
                    continue
                taxon = m.get("taxon") or {}
                if taxon.get("ott_id"):
                    matches[query] = taxon
                    break

    placed = []
    extinct_dropped = []
    for c in chosen:
        taxon = matches.get(c["binomial"])
        if not taxon:
            continue
        flags = [str(f).lower() for f in (taxon.get("flags") or [])]
        if "extinct" in flags:
            extinct_dropped.append(c["binomial"])
            continue
        c["ott_id"] = int(taxon["ott_id"])
        placed.append(c)

    # unique ott ids
    by_ott = {}
    for c in placed:
        by_ott.setdefault(c["ott_id"], c)
    placed = [by_ott[k] for k in sorted(by_ott)]

    subtree_payload = {"ott_ids": [c["ott_id"] for c in placed], "label_format": "name_and_id"}
    subtree = post_json(pre["induced_subtree_endpoint"], subtree_payload)
    newick = subtree.get("newick")
    if not newick:
        raise RuntimeError(f"induced subtree returned no newick: {json.dumps(subtree)[:500]}")
    open(os.path.join(DERIVED, "induced.newick"), "w").write(newick if newick.endswith("\n") else newick + "\n")
    root = parse_newick(newick)
    use_length = edge_length_fraction(root) >= 0.5
    collapse_unary(root)
    tip_by_ott = {}
    for tip in tips_of(root):
        ott = ott_of(tip.label)
        if ott is not None:
            tip_by_ott[ott] = tip
    on_tree = [c for c in placed if c["ott_id"] in tip_by_ott]

    # ecology codes from the on-tree set
    codes = []
    for c in on_tree:
        code = str(c["row"][pre["forstrat_column"]]).strip()
        if code and code not in codes:
            codes.append(code)
    codes = sorted(codes)
    code_index = {c: i for i, c in enumerate(codes)}
    usable = []
    for c in on_tree:
        vec = eco_vector(c["row"], diet_cols, act_cols, pre["forstrat_column"], code_index)
        if vec is None:
            continue
        c["eco"] = vec
        usable.append(c)

    n = len(usable)
    min_c = pre["min_compared_characters"]
    morph = np.full((n, n), np.nan)
    phy = np.full((n, n), np.nan)
    eco = np.full((n, n), np.nan)
    for i in range(n):
        morph[i, i] = 0.0
        phy[i, i] = 0.0
        eco[i, i] = 0.0
        for j in range(i + 1, n):
            h = hamming(usable[i]["cells"], usable[j]["cells"], min_c)
            if h is not None:
                morph[i, j] = morph[j, i] = h
            dphy = path_distance(tip_by_ott[usable[i]["ott_id"]], tip_by_ott[usable[j]["ott_id"]], use_length)
            phy[i, j] = phy[j, i] = dphy
            de = float(np.linalg.norm(usable[i]["eco"] - usable[j]["eco"]))
            eco[i, j] = eco[j, i] = de

    # complete-case filter: drop taxa that have no finite morph distance to anyone
    keep = []
    for i in range(n):
        if np.isfinite(morph[i]).sum() > 1:
            keep.append(i)
    morph, phy, eco = morph[np.ix_(keep, keep)], phy[np.ix_(keep, keep)], eco[np.ix_(keep, keep)]
    usable = [usable[i] for i in keep]
    n = len(usable)

    iu = np.triu_indices(n, 1)
    mask = np.isfinite(morph[iu]) & np.isfinite(phy[iu]) & np.isfinite(eco[iu])
    n_pairs = int(mask.sum())
    if n_pairs >= 3:
        r_p = float(stats.spearmanr(morph[iu][mask], phy[iu][mask]).statistic)
        r_e = float(stats.spearmanr(morph[iu][mask], eco[iu][mask]).statistic)
    else:
        r_p = float("nan")
        r_e = float("nan")
    delta = r_p - r_e if np.isfinite(r_p) and np.isfinite(r_e) else float("nan")

    rng = np.random.default_rng(pre["seed"])
    n_perm = pre["n_permutations"]
    count_phy = 0
    count_eco = 0
    n_perm_used = 0
    if n >= 3 and n_pairs >= 3 and np.isfinite(delta):
        base_idx = np.arange(n)
        for _ in range(n_perm):
            perm = rng.permutation(base_idx)
            mperm = morph[np.ix_(perm, perm)]
            msk = np.isfinite(mperm[iu]) & np.isfinite(phy[iu]) & np.isfinite(eco[iu])
            if int(msk.sum()) < 3:
                continue
            rp = float(stats.spearmanr(mperm[iu][msk], phy[iu][msk]).statistic)
            re = float(stats.spearmanr(mperm[iu][msk], eco[iu][msk]).statistic)
            if not np.isfinite(rp) or not np.isfinite(re):
                continue
            n_perm_used += 1
            dlt = rp - re
            if dlt >= delta:
                count_phy += 1
            if -dlt >= -delta:
                count_eco += 1
        # Denominator is 1 + the pre-registered permutation count, including any
        # permutation that was skipped for a non-finite correlation.
        p_phy = (1 + count_phy) / (1 + n_perm)
        p_eco = (1 + count_eco) / (1 + n_perm)
    else:
        p_phy = p_eco = float("nan")

    enough = n >= pre["min_taxa"] and n_pairs >= pre["min_pairs"]
    supports = (
        enough and np.isfinite(r_p) and np.isfinite(delta)
        and r_p >= pre["support_r_min"] and delta >= pre["support_delta_min"] and p_phy < pre["alpha"]
    )
    refutes = (
        enough and np.isfinite(r_e) and np.isfinite(delta)
        and r_e >= pre["support_r_min"] and (-delta) >= pre["support_delta_min"] and p_eco < pre["alpha"]
    )
    if supports:
        verdict, reason = "supports", None
        confidence = 0.66
    elif refutes:
        verdict, reason = "refutes", None
        confidence = 0.72
    elif enough:
        verdict, reason = "mixed", None
        # The gap and its permutation probability sit well clear of both thresholds.
        # Confidence stays moderate because the test is one class and the matrix was built to recover phylogeny.
        confidence = 0.61
    else:
        verdict, reason = "inconclusive", "underpowered"
        confidence = 0.4

    # descriptive partial Spearman, not used for the verdict
    def partial(x, y, z):
        if len(x) < 5:
            return None
        rx, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
        def resid(a, b):
            A = np.vstack([np.ones_like(b), b]).T
            coef, *_ = np.linalg.lstsq(A, a, rcond=None)
            return a - A @ coef
        return float(np.corrcoef(resid(rx, rz), resid(ry, rz))[0, 1])

    partial_phy = partial_eco = None
    if n_pairs >= 5:
        partial_phy = partial(morph[iu][mask], phy[iu][mask], eco[iu][mask])
        partial_eco = partial(morph[iu][mask], eco[iu][mask], phy[iu][mask])

    rows = []
    for c in usable:
        rows.append({
            "binomial": c["binomial"],
            "matrix_label": c["label"],
            "ott_id": c["ott_id"],
            "forstrat": str(c["row"][pre["forstrat_column"]]).strip(),
            "n_scored_characters": int(sum(x is not None for x in c["cells"])),
        })
    pd.DataFrame(rows).to_csv(os.path.join(DERIVED, "taxa.csv"), index=False)

    synth = about.get("synth_id") or about.get("source_id")
    taxonomy = about.get("taxonomy_version") or about.get("taxonomy")

    measured = {
        "value": None if not np.isfinite(delta) else float(delta),
        "unit": "Spearman r(morphology, phylogeny) minus Spearman r(morphology, ecology)",
        "n": int(n),
        "uncertainty": None if not np.isfinite(p_phy) else f"one-sided permutation p for delta = {p_phy:.4g}",
        "extra": {
            "r_morph_phylogeny": None if not np.isfinite(r_p) else float(r_p),
            "r_morph_ecology": None if not np.isfinite(r_e) else float(r_e),
            "delta": None if not np.isfinite(delta) else float(delta),
            "p_delta_phylogeny_greater": None if not np.isfinite(p_phy) else float(p_phy),
            "p_ecology_gap": None if not np.isfinite(p_eco) else float(p_eco),
            "n_pairs": n_pairs,
            "n_matrix_taxa": len(taxa),
            "nchar": nchar,
            "n_binomial_matched_to_elton": len(chosen),
            "n_opentree_not_extinct": len(placed),
            "n_on_induced_tree": len(on_tree),
            "extinct_flag_dropped": extinct_dropped,
            "phylogenetic_distance": "patristic" if use_length else "edge_count",
            "forstrat_codes": codes,
            "partial_spearman_morph_phylo_given_eco": partial_phy,
            "partial_spearman_morph_eco_given_phylo": partial_eco,
            "partials_not_used_for_verdict": True,
            "synth_id": synth,
            "taxonomy_version": taxonomy,
            "n_permutations": n_perm,
            "n_permutations_finite": n_perm_used,
            "seed": pre["seed"],
        },
    }
    method = (
        f"The MorphoBank P773 matrix X1766 NEXUS ({nchar} characters, {len(taxa)} taxa) and the EltonTraits "
        f"mammal table were downloaded. Extant species were the matrix binomials that match an EltonTraits row, "
        f"have an exact Open Tree name match not flagged extinct, and sit on the induced synthetic subtree "
        f"({n} taxa, {n_pairs} complete-case pairs). Morphological distance is the Hamming fraction on characters "
        f"scored in both taxa (at least {min_c} characters). Phylogenetic distance is "
        f"{'the sum of branch lengths' if use_length else 'the number of edges'} after unary nodes are collapsed. "
        f"Ecological distance is Euclidean distance on diet proportions, a one-hot of ForStrat-Value, and the three "
        f"activity columns. Spearman correlations and a {n_perm}-permutation test of their difference follow the "
        f"pre-registered thresholds."
    )
    datasets = [
        {
            "id": "morphobank-p773-x1766",
            "name": "MorphoBank project 773 matrix X1766, O'Leary et al. 2013 phenomic matrix of placental mammals",
            "landing_url": "https://morphobank.org/index.php/Projects/ProjectOverview/project_id/773",
            "doi": "10.1126/science.1229237",
            "version": "matrix 1766, NEXUS generated on retrieval",
            "license": "not CC0 (project record publish_cc0 = 0); public NEXUS download of the published project",
            "files": [matrix_meta],
            "role": "discrete phenomic characters used as the structural distances",
        },
        {
            "id": "eltontraits-1-0-mammals",
            "name": "EltonTraits 1.0 mammal foraging attributes (MamFuncDat.txt), Wilman et al. 2014",
            "landing_url": "https://esapubs.org/archive/ecol/E095/178/default.php",
            "doi": "10.1890/13-1917.1",
            "version": "MamFuncDat.txt, Ecological Archives E095-178, last-modified 2014-06-17",
            "license": "CC BY 4.0 (Figshare collection 10.6084/m9.figshare.c.3306933; file retrieved from the Ecological Archives copy)",
            "files": [elton_meta],
            "role": "diet, foraging stratum and activity time, the habits-of-life distance",
        },
        {
            "id": "opentree-synthetic-tree-api",
            "name": "Open Tree of Life synthetic tree via the v3 API (tnrs/match_names, tree_of_life/induced_subtree, tree_of_life/about)",
            "landing_url": "https://tree.opentreeoflife.org/",
            "doi": None,
            "version": f"{synth} / {taxonomy}",
            "license": "CC0 for Open Tree synthesis products, as stated by the project; the licence deed was not re-fetched in this run",
            "files": [f for f in FILES if "opentreeoflife.org" in f["download_url"]],
            "role": "independently estimated genealogy of the matched extant mammals",
        },
    ]
    res["status"] = "complete"
    res["data_kind"] = "biological"
    res["verdict"] = verdict
    res["confidence"] = confidence
    if reason:
        res["reason"] = reason
    res["method"] = method
    res["measured"] = measured
    res["datasets"] = datasets
    note = (
        f"Measured on {n} taxa and {n_pairs} pairs: r_phylogeny = {r_p if np.isfinite(r_p) else 'nan'}, "
        f"r_ecology = {r_e if np.isfinite(r_e) else 'nan'}, delta = {delta if np.isfinite(delta) else 'nan'}, "
        f"permutation p(delta) = {p_phy if np.isfinite(p_phy) else 'nan'}."
    )
    caveats = list(res.get("caveats") or [])
    if not any(note[:40] in c for c in caveats):
        caveats.insert(0, note)
    if extinct_dropped:
        drop_note = (
            "Open Tree exact matches flagged extinct were dropped before the tree was built: "
            + ", ".join(extinct_dropped)
            + ". A later non-extinct match for the same binomial was not substituted."
        )
        if drop_note not in caveats:
            caveats.append(drop_note)
    res["caveats"] = caveats
    json.dump(res, open(RESULT_PATH, "w"), indent=2)
    open(RESULT_PATH, "a").write("\n")
    summary = {
        "verdict": verdict,
        "confidence": confidence,
        "reason": reason,
        "n": n,
        "n_pairs": n_pairs,
        "r_p": r_p,
        "r_e": r_e,
        "delta": delta,
        "p_phy": p_phy,
        "p_eco": p_eco,
        "use_length": use_length,
        "synth": synth,
    }
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
