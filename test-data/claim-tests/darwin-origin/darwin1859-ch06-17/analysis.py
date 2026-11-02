#!/usr/bin/env python3
"""Test darwin1859-ch06-17: unity of type tracks descent, not habits of life.

Reads thresholds from result.json. Downloads RAG1 proteins and an Open Tree
induced subtree into ./data (gitignored) and writes derived/summary.json.

    python3 analysis.py            # compute; check result.json if it is complete
    python3 analysis.py --self-test
    python3 analysis.py --fill     # write measured, verdict, datasets into result.json
"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
RESULT_PATH = os.path.join(HERE, "result.json")
RESULT = json.load(open(RESULT_PATH))
RULE = RESULT["decision_rule"]
SPECIES = RESULT["species"]

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

S = requests.Session()
S.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"
FETCH_LOG = []


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def cache_path(key):
    return os.path.join(DATA, key)


def remember(url, body, retrieved_at=None):
    rec = {
        "download_url": url,
        "retrieved_at": retrieved_at or now(),
        "byte_size": len(body),
        "sha256": sha256(body),
    }
    FETCH_LOG.append(rec)
    return rec


def http_get(url, params=None, timeout=120):
    last = None
    for attempt in range(5):
        try:
            r = S.get(url, params=params, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                last = r.status_code
                continue
            if r.status_code >= 400:
                raise requests.HTTPError(f"{r.status_code} {r.text[:500]}", response=r)
            return r
        except requests.HTTPError:
            raise
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def http_post(url, payload, timeout=180):
    last = None
    for attempt in range(5):
        try:
            r = S.post(url, json=payload, timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 * (attempt + 1))
                last = r.status_code
                continue
            if r.status_code >= 400:
                err = requests.HTTPError(f"{r.status_code} {r.text[:800]}", response=r)
                raise err
            return r
        except requests.HTTPError:
            raise
        except requests.RequestException as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"POST failed {url}: {last}")


def cached_get(name, url, params=None):
    path = cache_path(name)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        body = open(path, "rb").read()
        meta = json.load(open(meta_path))
        if meta.get("sha256") == sha256(body) and meta.get("byte_size") == len(body):
            FETCH_LOG.append(meta)
            return body
    time.sleep(0.34)
    r = http_get(url, params=params)
    body = r.content
    meta = remember(r.url, body)
    open(path, "wb").write(body)
    json.dump(meta, open(meta_path, "w"), indent=1)
    return body


def cached_post(name, url, payload):
    path = cache_path(name)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        body = open(path, "rb").read()
        meta = json.load(open(meta_path))
        if meta.get("sha256") == sha256(body) and meta.get("byte_size") == len(body):
            FETCH_LOG.append(meta)
            return body
    time.sleep(0.2)
    r = http_post(url, payload)
    body = r.content
    meta = remember(url + " POST " + json.dumps(payload, sort_keys=True), body)
    meta["download_url"] = url
    meta["request_body"] = json.dumps(payload, sort_keys=True)
    open(path, "wb").write(body)
    json.dump(meta, open(meta_path, "w"), indent=1)
    FETCH_LOG[-1] = meta
    return body


def verify_repo_files():
    for f in RESULT.get("repo_files", []):
        raw = open(os.path.join("/workspace", f["path"]), "rb").read()
        if len(raw) != f["byte_size"] or sha256(raw) != f["sha256"]:
            raise SystemExit(f"repo file hash mismatch: {f['path']}")


def kmer_counts(seq, k):
    seq = "".join(ch for ch in seq.upper() if "A" <= ch <= "Z")
    return Counter(seq[i:i + k] for i in range(max(0, len(seq) - k + 1)))


def cosine_distance(c1, c2):
    if len(c1) > len(c2):
        c1, c2 = c2, c1
    dot = sum(v * c2.get(key, 0) for key, v in c1.items())
    n1 = sum(v * v for v in c1.values()) ** 0.5
    n2 = sum(v * v for v in c2.values()) ** 0.5
    if n1 == 0 or n2 == 0:
        return None
    sim = dot / (n1 * n2)
    if sim > 1:
        sim = 1.0
    if sim < -1:
        sim = -1.0
    return 1.0 - sim


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def crossed_stats(names, meta, dist):
    """dist is a function (a, b) -> float with a != b."""
    class_pairs, habit_pairs = [], []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            same_c = meta[a]["class"] == meta[b]["class"]
            same_h = meta[a]["habit"] == meta[b]["habit"]
            d = dist(a, b)
            if same_c and not same_h:
                class_pairs.append(d)
            elif same_h and not same_c:
                habit_pairs.append(d)
    c_num = c_den = h_num = h_den = 0
    nn_rows = []
    for a in names:
        diff_h = [b for b in names if b != a and meta[b]["habit"] != meta[a]["habit"]]
        diff_c = [b for b in names if b != a and meta[b]["class"] != meta[a]["class"]]

        def match(cands, field):
            if not cands:
                return None, []
            scored = sorted((dist(a, b), b) for b in cands)
            best = scored[0][0]
            tied = [b for d, b in scored if d <= best + 1e-12]
            ok = all(meta[b][field] == meta[a][field] for b in tied)
            return ok, tied

        c_ok, c_tied = match(diff_h, "class")
        h_ok, h_tied = match(diff_c, "habit")
        if c_ok is not None:
            c_den += 1
            c_num += int(c_ok)
        if h_ok is not None:
            h_den += 1
            h_num += int(h_ok)
        nn_rows.append({
            "species": a,
            "class": meta[a]["class"],
            "habit": meta[a]["habit"],
            "nearest_different_habit": c_tied,
            "nearest_different_habit_same_class": c_ok,
            "nearest_different_class": h_tied,
            "nearest_different_class_same_habit": h_ok,
        })
    d_class = mean(class_pairs)
    d_habit = mean(habit_pairs)
    if d_class is None or d_habit is None:
        ratio = None
    elif d_class == 0 and d_habit == 0:
        ratio = 1.0
    elif d_class == 0:
        ratio = None  # infinite; caller treats as passing the ratio
        ratio = 1e9
    else:
        ratio = d_habit / d_class
    return {
        "n": len(names),
        "n_class_pairs": len(class_pairs),
        "n_habit_pairs": len(habit_pairs),
        "D_class": d_class,
        "D_habit": d_habit,
        "ratio": ratio,
        "C_cross": (c_num / c_den) if c_den else None,
        "H_cross": (h_num / h_den) if h_den else None,
        "C_num": c_num,
        "C_den": c_den,
        "H_num": h_num,
        "H_den": h_den,
        "classes": dict(Counter(meta[n]["class"] for n in names)),
        "habits": dict(Counter(meta[n]["habit"] for n in names)),
        "nearest": nn_rows,
    }


def sample_powered(st):
    n_cls = sum(1 for v in st["classes"].values() if v >= 2)
    n_hab = sum(1 for v in st["habits"].values() if v >= 2)
    return (
        st["n"] >= RULE["min_species"]
        and n_cls >= RULE["min_classes_with_two"]
        and n_hab >= RULE["min_habits_with_two"]
        and st["n_class_pairs"] >= RULE["min_class_pairs"]
        and st["n_habit_pairs"] >= RULE["min_habit_pairs"]
        and st["D_class"] is not None
        and st["C_cross"] is not None
        and st["H_cross"] is not None
    )


def outcome(st):
    """Return pass, fail, mixed, or inconclusive plus a reason for inconclusive."""
    if st["n"] < RULE["min_proteins_else_data_unavailable"]:
        return "inconclusive", "data-unavailable"
    if not sample_powered(st):
        return "inconclusive", "underpowered"
    ratio_fail = st["D_habit"] < st["D_class"]
    nn_fail = st["C_cross"] < st["H_cross"]
    if ratio_fail or nn_fail:
        return "fail", None
    ratio_pass = st["ratio"] is not None and st["ratio"] >= RULE["min_ratio_habit_over_class"]
    if ratio_pass and st["C_cross"] >= RULE["min_c_cross"] and st["H_cross"] <= RULE["max_h_cross"]:
        return "pass", None
    return "mixed", None


def combine(seq_out, tree_out):
    seq, seq_reason = seq_out
    tree, tree_reason = tree_out
    if seq == "inconclusive":
        return "inconclusive", seq_reason
    if seq == "fail":
        return "refutes", None
    if seq == "mixed":
        return "mixed", None
    # sequence pass
    if tree == "pass":
        return "supports", None
    if tree == "inconclusive":
        return "supports", None
    return "mixed", None


def confidence_for(verdict, seq_stats, tree_out):
    rub = RESULT["confidence_rubric"]
    tree, _ = tree_out
    if verdict == "inconclusive":
        return rub["inconclusive"]
    if verdict == "mixed":
        return rub["mixed"]
    thin = (
        seq_stats.get("ratio") is not None
        and (seq_stats["ratio"] < 1.5 or (seq_stats.get("C_cross") is not None and seq_stats["C_cross"] < 0.90))
    )
    if verdict == "supports":
        if thin:
            return rub["supports_but_thin_margin"]
        if tree == "inconclusive":
            return rub["supports_tree_inconclusive"]
        return rub["supports_tree_agrees"]
    # refutes
    if tree == "fail":
        return rub["refutes_tree_also_fails"]
    return rub["refutes_otherwise"]


def self_test():
    # Four species, two classes, two habits. Classmates are close.
    # Same-habit pairs are the farthest, so H_cross is 0 and the ratio is large.
    names = ["Ma", "Mt", "Ba", "Bt"]
    meta = {
        "Ma": {"class": "M", "habit": "aerial"},
        "Mt": {"class": "M", "habit": "terrestrial"},
        "Ba": {"class": "B", "habit": "aerial"},
        "Bt": {"class": "B", "habit": "terrestrial"},
    }
    raw = {
        frozenset(("Ma", "Mt")): 0.2,
        frozenset(("Ba", "Bt")): 0.2,
        frozenset(("Ma", "Ba")): 0.9,
        frozenset(("Mt", "Bt")): 0.9,
        frozenset(("Ma", "Bt")): 0.55,
        frozenset(("Mt", "Ba")): 0.55,
    }

    def dist(a, b):
        return raw[frozenset((a, b))]

    st = crossed_stats(names, meta, dist)
    assert abs(st["D_class"] - 0.2) < 1e-9, st
    assert abs(st["D_habit"] - 0.9) < 1e-9, st
    assert abs(st["C_cross"] - 1) < 1e-9, st
    assert abs(st["H_cross"] - 0) < 1e-9, st
    # Force the sample-size gates by monkeypatching a copy of the rule check.
    saved = dict(RULE)
    RULE.update({
        "min_species": 4,
        "min_classes_with_two": 2,
        "min_habits_with_two": 2,
        "min_class_pairs": 2,
        "min_habit_pairs": 2,
        "min_proteins_else_data_unavailable": 2,
    })
    try:
        assert outcome(st)[0] == "pass", outcome(st)
        raw_fail = dict(raw)
        raw_fail[frozenset(("Ma", "Mt"))] = 0.95
        raw_fail[frozenset(("Ba", "Bt"))] = 0.95
        raw_fail[frozenset(("Ma", "Ba"))] = 0.1
        raw_fail[frozenset(("Mt", "Bt"))] = 0.1
        st_fail = crossed_stats(names, meta, lambda a, b: raw_fail[frozenset((a, b))])
        assert outcome(st_fail)[0] == "fail", outcome(st_fail)
    finally:
        RULE.clear()
        RULE.update(saved)
    print("self-test ok", flush=True)


# --- Open Tree newick (same shape as the ch06-10 test) ---------------------------------
class Node:
    __slots__ = ("label", "children", "parent")

    def __init__(self, label=""):
        self.label, self.children, self.parent = label, [], None


def parse_newick(s):
    s = s.strip().rstrip(";")
    i, root = 0, Node()
    node, stack = root, []
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
    while len(node.children) == 1 and node.children[0].children:
        child = node.children[0]
        node.label = child.label or node.label
        node.children = child.children
        for ch in node.children:
            ch.parent = node
    if len(node.children) == 1 and not node.children[0].children:
        node.label = node.children[0].label
        node.children = []
    for ch in node.children:
        collapse_unary(ch)


def tips(node):
    return [node] if not node.children else [t for c in node.children for t in tips(c)]


def ott_of(label):
    m = re.search(r"ott(\d+)$", label.replace(" ", ""))
    return int(m.group(1)) if m else None


def edge_distance(a, b):
    seen, n, d = {}, a, 0
    while n is not None:
        seen[id(n)] = d
        n = n.parent
        d += 1
    n, d = b, 0
    while n is not None:
        if id(n) in seen:
            return seen[id(n)] + d
        n = n.parent
        d += 1
    raise RuntimeError("tips are not in the same tree")


def choose_protein(summary_json):
    res = summary_json["result"]
    uids = [u for u in res.get("uids", []) if u != "uids"]
    cands = []
    for uid in uids:
        rec = res.get(uid) or {}
        try:
            slen = int(rec.get("slen"))
        except (TypeError, ValueError):
            continue
        if not (RULE["slen_min"] <= slen <= RULE["slen_max"]):
            continue
        acc = rec.get("accessionversion") or rec.get("caption") or ""
        if acc.startswith("NP_"):
            pref = 0
        elif acc.startswith("XP_"):
            pref = 1
        else:
            pref = 2
        cands.append((pref, -slen, acc, str(uid), slen, rec.get("title")))
    if not cands:
        return None
    cands.sort()
    pref, neg, acc, uid, slen, title = cands[0]
    return {"uid": uid, "accession": acc, "slen": slen, "title": title}


def fasta_seq(text):
    lines = text.splitlines()
    seq = "".join(ln.strip() for ln in lines if ln and not ln.startswith(">"))
    return seq


def fetch_proteins():
    chosen = []
    dropped = []
    for sp in SPECIES:
        name = sp["scientific_name"]
        safe = name.replace(" ", "_")
        term = RULE["protein_term"].format(binomial=name)
        body = cached_get(
            f"esearch_{safe}.json",
            ESEARCH,
            {"db": "protein", "term": term, "retmode": "json", "retmax": "20"},
        )
        ids = json.loads(body)["esearchresult"].get("idlist") or []
        if not ids:
            dropped.append({"species": name, "reason": "no RAG1 protein hit"})
            continue
        body = cached_get(
            f"esummary_{safe}.json",
            ESUMMARY,
            {"db": "protein", "id": ",".join(ids), "retmode": "json"},
        )
        pick = choose_protein(json.loads(body))
        if pick is None:
            dropped.append({"species": name, "reason": "no protein in the length window"})
            continue
        fasta = cached_get(
            f"fasta_{pick['accession']}.fa",
            EFETCH,
            {"db": "protein", "id": pick["uid"], "rettype": "fasta", "retmode": "text"},
        )
        seq = fasta_seq(fasta.decode("utf-8", "replace"))
        if len(seq) < RULE["slen_min"]:
            dropped.append({"species": name, "reason": f"fasta length {len(seq)}"})
            continue
        counts = kmer_counts(seq, RULE["kmer_k"])
        chosen.append({
            "species": name,
            "class": sp["class_label"],
            "habit": sp["habit"],
            "accession": pick["accession"],
            "uid": pick["uid"],
            "slen": pick["slen"],
            "fasta_length": len(seq),
            "title": pick["title"],
            "counts": counts,
        })
        print(f"protein {name} {pick['accession']} slen={pick['slen']}", flush=True)
    return chosen, dropped


def fetch_tree(sequenced_names):
    payload = {
        "names": sequenced_names,
        "context_name": RULE["tree_context"],
        "do_approximate_matching": False,
    }
    body = cached_post("tnrs.json", RULE["tnrs_endpoint"], payload)
    tn = json.loads(body)
    ott = {}
    for rec in tn.get("results", []):
        exact = [m for m in rec.get("matches", []) if not m.get("is_approximate_match")]
        if exact:
            ott[rec.get("name") or rec.get("matched_name")] = exact[0]["taxon"]["ott_id"]
    unmatched = [n for n in sequenced_names if n not in ott]
    pruned = []
    sub = None
    ids = sorted(set(ott.values()))
    while ids:
        try:
            body = cached_post(
                "induced_" + hashlib.sha256(",".join(map(str, ids)).encode()).hexdigest()[:12] + ".json",
                RULE["subtree_endpoint"],
                {"ott_ids": ids, "label_format": "name_and_id"},
            )
            sub = json.loads(body)
            break
        except requests.HTTPError as e:
            unknown = {}
            if e.response is not None:
                try:
                    unknown = e.response.json().get("unknown") or {}
                except Exception:
                    unknown = {}
            if not unknown:
                raise
            drop_ids = set()
            for key in unknown:
                drop_ids.add(int(str(key).replace("ott", "")))
            for nm, oid in list(ott.items()):
                if oid in drop_ids:
                    pruned.append(nm)
                    del ott[nm]
            ids = sorted(set(ott.values()))
            if not ids:
                break
    about = json.loads(cached_post("about.json", RULE["about_endpoint"], {}))
    if sub is None or "newick" not in sub:
        return {"about": about, "unmatched": unmatched, "pruned": pruned, "mapped": {}, "error": "no subtree"}
    open(os.path.join(DERIVED, "induced.nwk"), "w").write(sub["newick"] + "\n")
    root = parse_newick(sub["newick"])
    collapse_unary(root)
    tip_by_ott = {}
    tip_by_node = {}
    for t in tips(root):
        oid = ott_of(t.label)
        if oid is not None:
            tip_by_ott[oid] = t
        m = re.search(r"(mrcaott\d+ott\d+|ott\d+)$", t.label.replace(" ", ""))
        if m:
            tip_by_node[m.group(1)] = t
    broken = sub.get("broken") or {}
    mapped = {}
    for nm, oid in ott.items():
        tip = tip_by_ott.get(oid)
        if tip is None and f"ott{oid}" in broken:
            tip = tip_by_node.get(broken[f"ott{oid}"])
        if tip is not None:
            mapped.setdefault(id(tip), {"tip": tip, "species": []})
            mapped[id(tip)]["species"].append(nm)
    # one species per tip; conflicts dropped
    species_tip = {}
    conflicts = []
    for rec in mapped.values():
        if len(rec["species"]) == 1:
            species_tip[rec["species"][0]] = rec["tip"]
        else:
            conflicts.append(rec["species"])
    return {
        "about": {k: about.get(k) for k in ("synth_id", "taxonomy_version", "date_created")},
        "unmatched": unmatched,
        "pruned": pruned,
        "broken": broken,
        "conflicts": conflicts,
        "species_tip": species_tip,
        "n_requested": len(sequenced_names),
    }


def round6(x):
    if x is None:
        return None
    if isinstance(x, float):
        return round(x, 6)
    return x


def public_stats(st):
    out = {
        "n": st["n"],
        "n_class_pairs": st["n_class_pairs"],
        "n_habit_pairs": st["n_habit_pairs"],
        "D_class": round6(st["D_class"]),
        "D_habit": round6(st["D_habit"]),
        "ratio": round6(st["ratio"]) if st["ratio"] is not None and st["ratio"] < 1e8 else st["ratio"],
        "C_cross": round6(st["C_cross"]),
        "H_cross": round6(st["H_cross"]),
        "C_num": st["C_num"],
        "C_den": st["C_den"],
        "H_num": st["H_num"],
        "H_den": st["H_den"],
        "classes": st["classes"],
        "habits": st["habits"],
        "nearest": st["nearest"],
    }
    if st.get("mapped_fraction") is not None:
        out["mapped_fraction"] = round6(st["mapped_fraction"])
    return out


def run():
    verify_repo_files()
    chosen, dropped = fetch_proteins()
    meta = {c["species"]: {"class": c["class"], "habit": c["habit"]} for c in chosen}
    names = [c["species"] for c in chosen]
    counts = {c["species"]: c["counts"] for c in chosen}

    def seq_dist(a, b):
        return cosine_distance(counts[a], counts[b])

    seq_stats = crossed_stats(names, meta, seq_dist) if len(names) >= 2 else {
        "n": len(names), "n_class_pairs": 0, "n_habit_pairs": 0, "D_class": None, "D_habit": None,
        "ratio": None, "C_cross": None, "H_cross": None, "C_num": 0, "C_den": 0, "H_num": 0, "H_den": 0,
        "classes": dict(Counter(meta[n]["class"] for n in names)),
        "habits": dict(Counter(meta[n]["habit"] for n in names)),
        "nearest": [],
    }
    seq_out = outcome(seq_stats)
    tree_info = fetch_tree(names) if names else {"species_tip": {}, "n_requested": 0, "about": {}}
    tips_ok = tree_info.get("species_tip") or {}
    mapped_names = [n for n in names if n in tips_ok]
    mapped_fraction = (len(mapped_names) / len(names)) if names else 0.0
    if mapped_fraction < RULE["tree_min_mapped_fraction_of_sequenced"] or len(mapped_names) < 2:
        tree_stats = {"n": len(mapped_names), "mapped_fraction": mapped_fraction}
        tree_out = ("inconclusive", "data-unavailable" if not names else "underpowered")
    else:
        def topo(a, b):
            return float(edge_distance(tips_ok[a], tips_ok[b]))

        tree_stats = crossed_stats(mapped_names, meta, topo)
        tree_stats["mapped_fraction"] = mapped_fraction
        tree_out = outcome(tree_stats)
    verdict, reason = combine(seq_out, tree_out)
    conf = confidence_for(verdict, seq_stats, tree_out)
    proteins_public = [{k: c[k] for k in ("species", "class", "habit", "accession", "uid", "slen", "fasta_length", "title")} for c in chosen]
    return {
        "seq_stats": public_stats(seq_stats),
        "seq_outcome": seq_out[0],
        "seq_reason": seq_out[1],
        "tree_stats": public_stats(tree_stats) if "D_class" in tree_stats else tree_stats,
        "tree_outcome": tree_out[0],
        "tree_reason": tree_out[1],
        "verdict": verdict,
        "reason": reason,
        "confidence": conf,
        "dropped": dropped,
        "proteins": proteins_public,
        "tree_info": {k: v for k, v in tree_info.items() if k != "species_tip"},
        "mapped_species": mapped_names,
    }


def build_measured(out):
    st = out["seq_stats"]
    return {
        "value": st.get("C_cross"),
        "unit": "C_cross, fraction of sequenced species whose nearest different-habit neighbor is the same class (RAG1 3-mer cosine distance)",
        "n": st.get("C_den"),
        "uncertainty": (
            f"D_habit/D_class = {st.get('ratio')}; "
            f"H_cross = {st.get('H_cross')} ({st.get('H_num')}/{st.get('H_den')}); "
            f"C_cross = {st.get('C_num')}/{st.get('C_den')}"
        ),
        "extra": {
            "sequence": {k: st[k] for k in st if k != "nearest"},
            "sequence_outcome": out["seq_outcome"],
            "tree_outcome": out["tree_outcome"],
            "tree": {k: out["tree_stats"][k] for k in out["tree_stats"] if k != "nearest"} if isinstance(out["tree_stats"], dict) else out["tree_stats"],
            "tree_about": (out["tree_info"].get("about") if out.get("tree_info") else None),
            "mapped_fraction": (out["tree_stats"].get("mapped_fraction") if isinstance(out["tree_stats"], dict) else None),
            "n_proteins": len(out["proteins"]),
            "dropped": out["dropped"],
            "proteins": out["proteins"],
            "unmatched": (out.get("tree_info") or {}).get("unmatched"),
            "pruned_from_synth": (out.get("tree_info") or {}).get("pruned"),
            "tip_conflicts": (out.get("tree_info") or {}).get("conflicts"),
        },
    }


def dataset_block():
    files = []
    for rec in FETCH_LOG:
        files.append({
            "download_url": rec.get("download_url"),
            "request_body": rec.get("request_body"),
            "retrieved_at": rec.get("retrieved_at"),
            "byte_size": rec.get("byte_size"),
            "sha256": rec.get("sha256"),
        })
    return [
        {
            "id": "ncbi-protein-rag1",
            "name": "NCBI Protein RAG1 records for the frozen species list",
            "landing_url": "https://www.ncbi.nlm.nih.gov/protein/",
            "doi": None,
            "version": "live NCBI protein, accessions recorded per file",
            "license": "NCBI sequence records are freely accessible. Information created by or for the US government on the NCBI site is in the public domain (https://www.ncbi.nlm.nih.gov/home/about/policies/). Individual GenBank records may be submissions from outside the US government.",
            "files": [f for f in files if "ncbi.nlm.nih.gov" in (f.get("download_url") or "")],
            "role": "homologous RAG1 protein sequences used for the 3-mer distances",
        },
        {
            "id": "opentree-synthetic-tree-api",
            "name": "Open Tree of Life synthetic tree via the v3 API",
            "landing_url": "https://tree.opentreeoflife.org/",
            "doi": None,
            "version": "live synthesis at retrieval; synth_id recorded in measured.extra",
            "license": "CC0. Open Tree states that, except where pre-existing terms apply, its data are published with a CC0 public domain dedication (https://tree.opentreeoflife.org/about/licenses).",
            "files": [f for f in files if "opentreeoflife.org" in (f.get("download_url") or "")],
            "role": "topological distances on the synthetic tree, a replicate of the sequence test",
        },
    ]


def method_text(out):
    st = out["seq_stats"]
    return (
        f"For each frozen species, selected one NCBI protein whose Gene Name is RAG1 and whose length is "
        f"between {RULE['slen_min']} and {RULE['slen_max']} (RefSeq NP_ preferred, then XP_, then the longest; "
        f"{len(out['proteins'])} kept, {len(out['dropped'])} dropped). "
        f"Computed cosine distance of amino-acid {RULE['kmer_k']}-mer counts. "
        f"D_class is the mean distance over same-class different-habit pairs (n={st.get('n_class_pairs')}); "
        f"D_habit is the mean over same-habit different-class pairs (n={st.get('n_habit_pairs')}). "
        f"C_cross and H_cross are the nearest-neighbor fractions defined in the pass criterion. "
        f"The same statistics were computed on edge counts of the Open Tree induced subtree "
        f"(context {RULE['tree_context']}) for the species that mapped to a unique tip. "
        f"The verdict follows the pre-registered combination of the sequence outcome ({out['seq_outcome']}) "
        f"and the tree outcome ({out['tree_outcome']})."
    )


def fill_result(out):
    measured = build_measured(out)
    RESULT["status"] = "complete"
    RESULT["measured"] = measured
    RESULT["verdict"] = out["verdict"]
    RESULT["confidence"] = out["confidence"]
    RESULT["data_kind"] = "biological"
    RESULT["method"] = method_text(out)
    RESULT["datasets"] = dataset_block()
    RESULT["datasets"].append({
        "id": "darwin-origin-taxon-files",
        "name": "Vendored Darwin organism records used as name authorities",
        "landing_url": "https://github.com/fractastical/delphi",
        "doi": None,
        "version": "repo files at this commit",
        "license": "same as the repository",
        "files": [
            {"path": f["path"], "byte_size": f["byte_size"], "sha256": f["sha256"], "role": f["role"]}
            for f in RESULT["repo_files"]
        ],
        "role": "accepted names for the species and genera Darwin's inventory already resolved",
    })
    if out["reason"]:
        RESULT["reason"] = out["reason"]
    elif "reason" in RESULT:
        del RESULT["reason"]
    RESULT["results_summary"] = [
        f"Sequence outcome {out['seq_outcome']}: C_cross={out['seq_stats'].get('C_cross')} "
        f"({out['seq_stats'].get('C_num')}/{out['seq_stats'].get('C_den')}), "
        f"H_cross={out['seq_stats'].get('H_cross')}, ratio D_habit/D_class={out['seq_stats'].get('ratio')}, "
        f"n_proteins={len(out['proteins'])}.",
        f"Tree outcome {out['tree_outcome']}: mapped {len(out['mapped_species'])} species; "
        f"stats { {k: out['tree_stats'].get(k) for k in ('n','D_class','D_habit','ratio','C_cross','H_cross','mapped_fraction')} if isinstance(out['tree_stats'], dict) else out['tree_stats'] }.",
        f"Verdict {out['verdict']} with confidence {out['confidence']} from the pre-registered rubric.",
    ]
    # nearest-neighbor table is useful and small
    json.dump(out["seq_stats"].get("nearest"), open(os.path.join(DERIVED, "sequence_nearest.json"), "w"), indent=2)
    if isinstance(out["tree_stats"], dict) and out["tree_stats"].get("nearest"):
        json.dump(out["tree_stats"]["nearest"], open(os.path.join(DERIVED, "tree_nearest.json"), "w"), indent=2)
    with open(RESULT_PATH, "w") as fh:
        json.dump(RESULT, fh, indent=2)
        fh.write("\n")


def check_result(out):
    if RESULT.get("status") != "complete":
        print("result.json is not complete; pass --fill to record the verdict", flush=True)
        return
    got = build_measured(out)
    exp = RESULT["measured"]
    if exp.get("value") != got.get("value") or exp.get("n") != got.get("n"):
        raise SystemExit(f"measured mismatch\nexpected {exp.get('value')} n={exp.get('n')}\ngot {got.get('value')} n={got.get('n')}")
    if RESULT.get("verdict") != out["verdict"]:
        raise SystemExit(f"verdict mismatch {RESULT.get('verdict')} vs {out['verdict']}")
    print("recomputed measured matches result.json", flush=True)


def main():
    self_test()
    if "--self-test" in sys.argv:
        return
    out = run()
    json.dump({k: v for k, v in out.items() if k != "proteins" or True}, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)
    json.dump(FETCH_LOG, open(os.path.join(DERIVED, "fetch_log.json"), "w"), indent=1)
    print("verdict", out["verdict"], "confidence", out["confidence"], "seq", out["seq_outcome"], "tree", out["tree_outcome"], flush=True)
    print(json.dumps(build_measured(out)["extra"]["sequence"], indent=2)[:2000], flush=True)
    if "--fill" in sys.argv:
        fill_result(out)
        print("filled result.json", flush=True)
    else:
        check_result(out)


if __name__ == "__main__":
    main()
