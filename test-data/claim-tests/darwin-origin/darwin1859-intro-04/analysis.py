#!/usr/bin/env python3
"""darwin1859-intro-04: congeners form one clade, and an extinct species is at least as old.

Re-run from this directory: python3 analysis.py
API responses are cached under data/ and are not committed.
The genus list, thresholds and verdict table are read from result.json and are not revised here.
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
RESULT_PATH = os.path.join(HERE, "result.json")
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

UA = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = UA
FILES = []
BINOM = re.compile(r"^[A-Z][A-Za-z-]+ [a-z][a-z-]+$")
EXTANT_OK = {"extant", "1", "true", "True", "yes"}
EXTINCT_OK = {"extinct", "0", "false", "False", "no"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(url, raw, request_body=None):
    meta = {
        "download_url": url,
        "retrieved_at": now(),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    if request_body is not None:
        meta["request_body"] = request_body
    FILES.append(meta)
    return meta


def cache_path(kind, key):
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(key))[:120]
    return os.path.join(DATA, f"{kind}_{safe}.json")


def http_get(url, params=None, cache=None):
    if cache and os.path.exists(cache):
        meta = json.load(open(cache + ".meta.json"))
        FILES.append(meta)
        return json.load(open(cache))
    last = None
    for attempt in range(5):
        try:
            r = SESSION.get(url, params=params, timeout=180)
            if r.status_code == 200 and r.content:
                raw = r.content
                try:
                    text = raw.decode("utf-8")
                except UnicodeDecodeError:
                    text = raw.decode("latin-1")
                data = json.loads(text)
                meta = record(r.url, raw)
                if cache:
                    open(cache, "w").write(json.dumps(data))
                    json.dump(meta, open(cache + ".meta.json", "w"))
                return data
            last = f"HTTP {r.status_code} {r.text[:240]}"
        except (requests.RequestException, json.JSONDecodeError, UnicodeError) as exc:
            last = str(exc)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} {params}: {last}")


def http_post(url, payload, cache=None):
    body = json.dumps(payload, sort_keys=True)
    if cache and os.path.exists(cache):
        meta = json.load(open(cache + ".meta.json"))
        FILES.append(meta)
        return json.load(open(cache))
    last = None
    for attempt in range(5):
        try:
            r = SESSION.post(url, json=payload, timeout=180)
            raw = r.content
            if r.status_code == 200 and raw:
                data = json.loads(raw.decode("utf-8"))
                meta = record(url, raw, request_body=body)
                if cache:
                    open(cache, "w").write(json.dumps(data))
                    json.dump(meta, open(cache + ".meta.json", "w"))
                return data
            last = f"HTTP {r.status_code} {r.text[:400]}"
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last = str(exc)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(last)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [value]
    return []


NULL_CHILDREN = 0


def itis_down(pre, tsn):
    """Immediate ITIS children. JSON nulls in hierarchyList are not taxa.

    The live service returns hierarchyList: [null] for some genera that have
    no children (seen for Bulinus, TSN 655935). Those entries are skipped.
    """
    global NULL_CHILDREN
    url = pre["itis_down"]
    cache = cache_path("itis_down", tsn)
    cached = os.path.exists(cache)
    data = http_get(url, {"tsn": tsn}, cache=cache)
    if not cached:
        time.sleep(0.12)
    items = as_list(data.get("hierarchyList"))
    NULL_CHILDREN += sum(1 for child in items if not isinstance(child, dict))
    return [child for child in items if isinstance(child, dict)]


def itis_up(pre, tsn):
    cache = cache_path("itis_up", tsn)
    cached = os.path.exists(cache)
    data = http_get(pre["itis_up"], {"tsn": tsn}, cache=cache)
    if not cached:
        time.sleep(0.12)
    return data


def itis_rank(pre, tsn):
    cache = cache_path("itis_rank", tsn)
    cached = os.path.exists(cache)
    data = http_get(pre["itis_rank"], {"tsn": tsn}, cache=cache)
    if not cached:
        time.sleep(0.12)
    return data.get("rankName")


def resolve_tsn(pre, genus):
    if genus.get("itis_tsn"):
        return str(genus["itis_tsn"]), None
    cache = cache_path("itis_search", genus["name"])
    cached = os.path.exists(cache)
    data = http_get(pre["itis_search"], {"srchKey": genus["name"]}, cache=cache)
    if not cached:
        time.sleep(0.12)
    hits = []
    for rec in as_list(data.get("scientificNames")):
        if rec.get("unitName1") != genus["name"]:
            continue
        if rec.get("unitName2") not in (None, ""):
            continue
        if rec.get("kingdom") not in (None, "", "Animalia"):
            continue
        tsn = str(rec.get("tsn"))
        try:
            rank = itis_rank(pre, tsn)
        except RuntimeError as exc:
            return None, f"rank lookup failed: {exc}"
        if rank == "Genus" and rec.get("kingdom") in (None, "", "Animalia"):
            if rec.get("kingdom") == "Animalia" or rec.get("kingdom") in (None, ""):
                hits.append(tsn)
    # keep Animalia-confirmed hits if any rank call said Animalia; hits already filtered
    hits = sorted(set(hits))
    if len(hits) == 1:
        return hits[0], None
    if len(hits) == 0:
        return None, "no ITIS genus hit"
    return None, f"{len(hits)} ITIS genus hits"


def species_under(pre, genus_name, tsn, depth=0):
    try:
        children = itis_down(pre, tsn)
    except RuntimeError as exc:
        raise
    found = []
    for ch in children:
        rank = ch.get("rankName")
        name = ch.get("taxonName") or ""
        if rank == "Species" and BINOM.match(name) and name.split()[0] == genus_name:
            found.append(name)
        elif rank in ("Subgenus", "Section") and depth < 2:
            found.extend(species_under(pre, genus_name, ch["tsn"], depth + 1))
    return found


def even_sample(names, k):
    names = sorted(set(names), key=lambda s: (s.split()[1], s))
    n = len(names)
    if n <= k:
        return names
    picked = []
    seen = set()
    for i in range(k):
        j = (i * (n - 1)) // (k - 1)
        if j not in seen:
            seen.add(j)
            picked.append(names[j])
    return picked


def pick_two(names, k):
    names = sorted(set(names), key=lambda s: (s.split()[1], s))
    if len(names) <= k:
        return names
    return [names[0], names[-1]]


def family_of(pre, genus_tsn):
    node = str(genus_tsn)
    for _ in range(8):
        up = itis_up(pre, node)
        parent = up.get("parentTsn")
        if not parent:
            return None
        rank = itis_rank(pre, parent)
        if rank == "Family":
            return str(parent)
        node = str(parent)
    return None


def genera_in_family(pre, family_tsn):
    cache = cache_path("family_genera", family_tsn)
    if os.path.exists(cache):
        return json.load(open(cache))
    found = []

    def walk(tsn, depth):
        for ch in itis_down(pre, tsn):
            rank = ch.get("rankName")
            if rank == "Genus":
                found.append({"name": ch.get("taxonName"), "tsn": str(ch.get("tsn"))})
            elif rank in ("Subfamily", "Tribe", "Subtribe") and depth < 2:
                walk(ch["tsn"], depth + 1)

    walk(family_tsn, 0)
    # unique by name
    by = {}
    for g in found:
        if g["name"] and g["name"] not in by:
            by[g["name"]] = g
    genera = [by[k] for k in sorted(by)]
    json.dump(genera, open(cache, "w"))
    return genera


def outgroup_species(pre, genus_name, family_tsn, k_genera, k_species):
    genera = [g for g in genera_in_family(pre, family_tsn) if g["name"] != genus_name]
    genera = genera[:k_genera]
    chosen = []
    for g in genera:
        spp = species_under(pre, g["name"], g["tsn"])
        chosen.extend(pick_two(spp, k_species))
    return chosen


class Node:
    __slots__ = ("label", "children", "parent")

    def __init__(self, label=""):
        self.label = label
        self.children = []
        self.parent = None


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
            m = re.match(r"[-+0-9.eE]+", s[i + 1:])
            i += 1 + (len(m.group(0)) if m else 0)
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
        node.label = node.children[0].label or node.label
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
    m = re.search(r"ott(\d+)", label.replace(" ", "_"))
    return int(m.group(1)) if m else None


def ancestors(node):
    chain = []
    seen = set()
    while node is not None and id(node) not in seen:
        seen.add(id(node))
        chain.append(node)
        node = node.parent
    return chain


def mrca_of(nodes):
    common = set(ancestors(nodes[0]))
    for n in nodes[1:]:
        common &= set(ancestors(n))
    return max(common, key=lambda n: len(ancestors(n)))


def clade_status(newick, ingroup_ids, outgroup_ids):
    root = parse_newick(newick)
    collapse_unary(root)
    by = {}
    for tip in tips_of(root):
        ott = ott_of(tip.label)
        if ott is not None:
            by[ott] = tip
    if set(ingroup_ids) & set(outgroup_ids):
        return "conflict", sorted(set(ingroup_ids) & set(by)), sorted(set(outgroup_ids) & set(by))
    ing = [by[i] for i in ingroup_ids if i in by]
    out = [i for i in outgroup_ids if i in by]
    if len(ing) < 3 or len(out) < 1:
        return "untested", sorted(set(ingroup_ids) & set(by)), sorted(out)
    mrca = mrca_of(ing)
    desc = {ott_of(t.label) for t in tips_of(mrca)}
    extra = [i for i in desc if i is not None and i not in set(ingroup_ids)]
    return (len(extra) == 0), sorted(set(ingroup_ids) & set(by)), sorted(out)


def norm_family(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper().startswith("NO_"):
        return None
    return re.sub(r"\s+", " ", text).casefold()


def pbdb_genus(pre, genus):
    params = {
        "base_name": genus["name"],
        "rank": "species",
        "taxon_status": "valid",
        "show": "attr,app,class",
        "vocab": "pbdb",
    }
    cache = cache_path("pbdb", genus["name"])
    cached = os.path.exists(cache)
    data = http_get(pre["pbdb_taxa_list"], params, cache=cache)
    if not cached:
        time.sleep(0.15)
    records = data.get("records")
    if records is None:
        raise RuntimeError(f"PBDB response keys {list(data)[:8]}")
    wanted = norm_family(genus.get("family"))
    rows = []
    seen = set()
    family_mismatch = 0
    for rec in records:
        if rec.get("accepted_rank") != "species":
            continue
        accepted = rec.get("accepted_name") or ""
        if not accepted or accepted.split()[0] != genus["name"]:
            continue
        fam = norm_family(rec.get("family"))
        if wanted and fam and fam != wanted:
            family_mismatch += 1
            continue
        key = rec.get("accepted_no") or accepted
        if key in seen:
            continue
        seen.add(key)
        rows.append(rec)
    if wanted and family_mismatch and not rows:
        return {"status": "untested", "why": "family filter removed every species", "n_mismatch": family_mismatch}
    extinct_ages = []
    extant_ages = []
    for rec in rows:
        flag = rec.get("is_extant")
        flag_s = str(flag).strip() if flag is not None else ""
        age = rec.get("firstapp_max_ma")
        try:
            age_f = float(age)
        except (TypeError, ValueError):
            continue
        if flag_s in EXTINCT_OK:
            extinct_ages.append(age_f)
        elif flag_s in EXTANT_OK:
            extant_ages.append(age_f)
    if not extinct_ages or not extant_ages:
        return {
            "status": "untested",
            "why": "need at least one extinct and one extant species with firstapp_max_ma",
            "n_extinct_aged": len(extinct_ages),
            "n_extant_aged": len(extant_ages),
            "n_rows": len(rows),
        }
    max_ex = max(extinct_ages)
    max_et = max(extant_ages)
    return {
        "status": "tested",
        "match": max_ex >= max_et,
        "max_extinct_ma": max_ex,
        "max_extant_ma": max_et,
        "n_extinct_aged": len(extinct_ages),
        "n_extant_aged": len(extant_ages),
        "n_rows": len(rows),
    }


def part_status(fraction, n, n_min, support, refute):
    if n < n_min:
        return "underpowered"
    if fraction + 1e-12 >= support:
        return "support"
    if fraction <= refute + 1e-12:
        return "refute"
    return "mixed"


def hash_sources(genera):
    files = []
    seen = set()
    for g in genera:
        for rel in g.get("source_paths") or []:
            if rel in seen:
                continue
            seen.add(rel)
            path = os.path.join(REPO, rel)
            if not os.path.exists(path):
                files.append({"path": rel, "missing": True})
                continue
            raw = open(path, "rb").read()
            files.append({
                "path": rel,
                "byte_size": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            })
    return files


def main():
    res = json.load(open(RESULT_PATH))
    pre = res["preregistration"]
    genera = pre["genera"]
    about = http_post(pre["about_endpoint"], {}, cache=cache_path("ot_about", "about"))

    plans = []
    mono_errors = 0
    for g in genera:
        entry = {"name": g["name"], "class": g.get("class"), "family": g.get("family")}
        try:
            tsn, why = resolve_tsn(pre, g)
        except RuntimeError as exc:
            entry["mono"] = "error"
            entry["mono_why"] = str(exc)
            mono_errors += 1
            plans.append(entry)
            continue
        if not tsn:
            entry["mono"] = "untested"
            entry["mono_why"] = why
            plans.append(entry)
            continue
        entry["itis_tsn"] = tsn
        try:
            spp = species_under(pre, g["name"], tsn)
            sampled = even_sample(spp, pre["max_ingroup_sample"])
            fam = family_of(pre, tsn)
            out = outgroup_species(pre, g["name"], fam, pre["max_outgroup_genera"], pre["outgroup_species_per_genus"]) if fam else []
        except RuntimeError as exc:
            entry["mono"] = "error"
            entry["mono_why"] = str(exc)
            mono_errors += 1
            plans.append(entry)
            continue
        entry["n_itis_species"] = len(spp)
        entry["ingroup"] = sampled
        entry["outgroup"] = out
        entry["family_tsn"] = fam
        if len(sampled) < pre["min_ingroup_tips"] or not out:
            entry["mono"] = "untested"
            entry["mono_why"] = "fewer than 3 ITIS species" if len(sampled) < pre["min_ingroup_tips"] else "no outgroup species"
        else:
            entry["mono"] = "pending"
        plans.append(entry)
        print(f"ITIS {g['name']}: species {len(spp)} sampled {len(sampled)} out {len(out)}", flush=True)

    # fossil half
    fossil_errors = 0
    for g, entry in zip(genera, plans):
        try:
            entry["fossil"] = pbdb_genus(pre, g)
        except RuntimeError as exc:
            entry["fossil"] = {"status": "error", "why": str(exc)}
            fossil_errors += 1
        print(f"PBDB {g['name']}: {entry['fossil'].get('status')} {entry['fossil'].get('why','')}", flush=True)

    # TNRS for every pending name
    names = []
    for entry in plans:
        if entry.get("mono") == "pending":
            names.extend(entry["ingroup"])
            names.extend(entry["outgroup"])
    names = sorted(set(names))
    tnrs_hits = {}
    chunk = 150
    for i in range(0, len(names), chunk):
        part = names[i:i + chunk]
        payload = {"names": part, "context_name": pre["tnrs_context"], "do_approximate_matching": False}
        try:
            data = http_post(pre["tnrs_endpoint"], payload, cache=cache_path("tnrs", i))
        except RuntimeError as exc:
            for name in part:
                tnrs_hits[name] = {"error": str(exc)}
            continue
        results = data.get("results") or []
        for name, result in zip(part, results):
            hit = None
            for m in result.get("matches") or []:
                if m.get("is_approximate_match"):
                    continue
                taxon = m.get("taxon") or {}
                if taxon.get("ott_id"):
                    hit = taxon
                    break
            tnrs_hits[name] = hit
        print(f"TNRS {i}..{i+len(part)}", flush=True)

    def ott_for(name):
        hit = tnrs_hits.get(name)
        if not hit or "error" in (hit or {}):
            return None, "error" if isinstance(hit, dict) and hit.get("error") else "unmatched"
        flags = [str(f).lower() for f in (hit.get("flags") or [])]
        if "extinct" in flags:
            return None, "extinct"
        return int(hit["ott_id"]), None

    for entry in plans:
        if entry.get("mono") != "pending":
            continue
        ing, out = {}, {}
        role_error = False
        for name in entry["ingroup"]:
            ott, why = ott_for(name)
            if why == "error":
                role_error = True
            if ott is not None:
                if ott in out:
                    entry["mono"] = "untested"
                    entry["mono_why"] = "ingroup and outgroup collapsed to one ott id"
                    break
                ing[name] = ott
        if entry.get("mono") != "pending":
            continue
        for name in entry["outgroup"]:
            ott, why = ott_for(name)
            if why == "error":
                role_error = True
            if ott is not None:
                if ott in set(ing.values()):
                    entry["mono"] = "untested"
                    entry["mono_why"] = "ingroup and outgroup collapsed to one ott id"
                    break
                out[name] = ott
        if entry.get("mono") != "pending":
            continue
        if role_error and (len(ing) < pre["min_ingroup_tips"] or len(set(out.values())) < 1):
            entry["mono"] = "error"
            entry["mono_why"] = "Open Tree TNRS failed"
            mono_errors += 1
            continue
        ing_ids = sorted(set(ing.values()))
        out_ids = sorted(set(out.values()))
        entry["n_ingroup_matched"] = len(ing_ids)
        entry["n_outgroup_matched"] = len(out_ids)
        if len(ing_ids) < pre["min_ingroup_tips"] or len(out_ids) < 1:
            entry["mono"] = "untested"
            entry["mono_why"] = "fewer than 3 ingroup tips or no outgroup tip after name matching"
            continue
        payload = {"ott_ids": ing_ids + out_ids, "label_format": "name_and_id"}
        subtree = None
        dropped = []
        err = None
        ids = list(payload["ott_ids"])
        for _try in range(6):
            try:
                subtree = http_post(
                    pre["induced_subtree_endpoint"],
                    {"ott_ids": ids, "label_format": "name_and_id"},
                    cache=cache_path("subtree", entry["name"] + "_" + str(len(ids))),
                )
                if subtree.get("newick"):
                    break
                err = json.dumps(subtree)[:300]
                subtree = None
            except RuntimeError as exc:
                err = str(exc)
                subtree = None
            mentioned = [int(x) for x in re.findall(r"ott_?id[^\d]*(\d+)", err or "")]
            mentioned += [int(x) for x in re.findall(r"\bott(\d+)\b", err or "")]
            if not mentioned:
                break
            ids = [i for i in ids if i not in set(mentioned)]
            dropped.extend(mentioned)
        if not subtree or not subtree.get("newick"):
            entry["mono"] = "error"
            entry["mono_why"] = f"induced subtree failed: {err}"
            mono_errors += 1
            continue
        newick = subtree["newick"]
        open(os.path.join(DERIVED, f"{entry['name']}.newick"), "w").write(newick if newick.endswith("\n") else newick + "\n")
        status, got_in, got_out = clade_status(newick, ing_ids, out_ids)
        entry["dropped_ott_ids"] = sorted(set(dropped))
        entry["n_ingroup_tips"] = len(got_in)
        entry["n_outgroup_tips"] = len(got_out)
        if status == "conflict":
            entry["mono"] = "untested"
            entry["mono_why"] = "ingroup and outgroup on the same tip"
        elif status == "untested":
            entry["mono"] = "untested"
            entry["mono_why"] = "fewer than 3 ingroup tips or no outgroup tip on the induced tree"
        else:
            entry["mono"] = "monophyletic" if status else "not-monophyletic"

    # verdict
    mono_rows = [e for e in plans if e.get("mono") in ("monophyletic", "not-monophyletic")]
    n_m = len(mono_rows)
    n_mono_true = sum(1 for e in mono_rows if e["mono"] == "monophyletic")
    M = (n_mono_true / n_m) if n_m else None
    fossil_rows = [e for e in plans if e.get("fossil", {}).get("status") == "tested"]
    n_e = len(fossil_rows)
    n_match = sum(1 for e in fossil_rows if e["fossil"]["match"])
    E = (n_match / n_e) if n_e else None
    mono_definitive = n_m
    fossil_definitive = n_e
    mono_state = part_status(M or 0, n_m, pre["min_monophyly_n"], pre["support_fraction"], pre["refute_fraction"]) if M is not None else "underpowered"
    foss_state = part_status(E or 0, n_e, pre["min_fossil_n"], pre["support_fraction"], pre["refute_fraction"]) if E is not None else "underpowered"
    if mono_errors > mono_definitive and n_m < pre["min_monophyly_n"]:
        mono_state = "unavailable"
    if fossil_errors > fossil_definitive and n_e < pre["min_fossil_n"]:
        foss_state = "unavailable"
    reason = None
    if mono_state == "refute" or foss_state == "refute":
        verdict = "refutes"
    elif mono_state == "unavailable" or foss_state == "unavailable":
        verdict, reason = "inconclusive", "data-unavailable"
    elif mono_state == "support" and foss_state == "support":
        verdict = "supports"
    elif mono_state in ("support", "mixed") and foss_state in ("support", "mixed"):
        verdict = "mixed"
    else:
        verdict, reason = "inconclusive", "underpowered"

    if verdict == "supports":
        confidence = 0.57
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "mixed":
        # A monophyly fraction within one genus of the frozen 0.80 line is a mixed call,
        # but it sits next to support. Confidence stays lower in that case.
        confidence = 0.6
        if M is not None and n_m and M < pre["support_fraction"]:
            genera_short = (pre["support_fraction"] - M) * n_m
            if genera_short <= 1.0 + 1e-9:
                confidence = 0.55
    else:
        confidence = 0.4

    # per-class descriptive fractions, not used for the verdict
    by_class = {}
    for e in mono_rows:
        by_class.setdefault(e.get("class") or "unknown", {"n": 0, "monophyletic": 0})
        by_class[e["class"] or "unknown"]["n"] += 1
        if e["mono"] == "monophyletic":
            by_class[e["class"] or "unknown"]["monophyletic"] += 1

    table = []
    for e in plans:
        fossil = e.get("fossil") or {}
        table.append({
            "genus": e["name"],
            "class": e.get("class"),
            "family": e.get("family"),
            "mono": e.get("mono"),
            "mono_why": e.get("mono_why"),
            "n_itis_species": e.get("n_itis_species"),
            "n_ingroup_tips": e.get("n_ingroup_tips"),
            "n_outgroup_tips": e.get("n_outgroup_tips"),
            "fossil_status": fossil.get("status"),
            "fossil_match": fossil.get("match"),
            "max_extinct_ma": fossil.get("max_extinct_ma"),
            "max_extant_ma": fossil.get("max_extant_ma"),
            "n_extinct_aged": fossil.get("n_extinct_aged"),
            "n_extant_aged": fossil.get("n_extant_aged"),
            "fossil_why": fossil.get("why"),
        })
    # csv without pandas to keep the dependency optional if pandas is present; write manually
    cols = list(table[0].keys())
    with open(os.path.join(DERIVED, "genera.csv"), "w") as fh:
        fh.write(",".join(cols) + "\n")
        for row in table:
            cells = []
            for c in cols:
                val = row.get(c)
                text = "" if val is None else str(val)
                if any(ch in text for ch in ",\"\n"):
                    text = '"' + text.replace('"', "'") + '"'
                cells.append(text)
            fh.write(",".join(cells) + "\n")
    json.dump(plans, open(os.path.join(DERIVED, "plans.json"), "w"), indent=2)

    value = None
    unit = "minimum of monophyly fraction M and extinct-ancestor fraction E"
    if M is not None and E is not None:
        value = min(M, E)
    elif M is not None:
        value = M
        unit = "monophyly fraction M; fossil fraction was not measured"
    elif E is not None:
        value = E
        unit = "extinct-ancestor fraction E; monophyly fraction was not measured"

    synth = about.get("synth_id") or about.get("source_id")
    taxonomy = about.get("taxonomy_version") or about.get("taxonomy")
    measured = {
        "value": value,
        "unit": unit,
        "n": n_m,
        "uncertainty": f"M = {None if M is None else round(M, 4)} on {n_m} genera; E = {None if E is None else round(E, 4)} on {n_e} genera",
        "extra": {
            "monophyly_fraction": M,
            "n_monophyly_tested": n_m,
            "n_monophyletic": n_mono_true,
            "extinct_ancestor_fraction": E,
            "n_fossil_tested": n_e,
            "n_fossil_match": n_match,
            "mono_state": mono_state,
            "fossil_state": foss_state,
            "mono_http_errors": mono_errors,
            "fossil_http_errors": fossil_errors,
            "n_genera": len(genera),
            "monophyly_by_class_not_used_for_verdict": by_class,
            "synth_id": synth,
            "taxonomy_version": taxonomy,
        },
    }
    method = (
        f"The frozen list of {len(genera)} genera was read from the pre-registered result file. "
        f"Species membership and family outgroups came from ITIS; names were matched exactly on the Open Tree "
        f"synthetic tree ({synth}); monophyly is whether the ingroup tips form a clade. "
        f"{n_m} genera were monophyly-testable and {n_mono_true} of them were monophyletic (M = {M}). "
        f"Paleobiology Database accepted species with is_extant and firstapp_max_ma gave a fossil test for "
        f"{n_e} genera, of which {n_match} have an extinct species at least as old as every dated living species (E = {E}). "
        f"The verdict table in the pre-registration was applied unchanged "
        f"(monophyly half {mono_state}, fossil half {foss_state})."
    )
    source_files = hash_sources(genera)
    datasets = [
        {
            "id": "darwin-origin-vendored-genus-inventory",
            "name": "Genus-rank taxon records vendored under test-data/organisms/darwin-origin",
            "landing_url": "https://github.com/fractastical/delphi",
            "doi": None,
            "version": "repository files hashed at run time",
            "license": "same as the repository",
            "files": source_files,
            "role": "frozen list of genus names, ITIS TSNs where present, and the family used to reject homonyms",
        },
        {
            "id": "itis-web-service",
            "name": "ITIS web service JSON API",
            "landing_url": "https://www.itis.gov/",
            "doi": None,
            "version": "live service, responses cached with SHA-256",
            "license": "US public domain (federal work of the USGS and the Smithsonian)",
            "files": [f for f in FILES if "itis.gov" in f["download_url"]],
            "role": "species membership of each genus and outgroup species from the same family",
        },
        {
            "id": "opentree-synthetic-tree-api",
            "name": "Open Tree of Life synthetic tree via the v3 API",
            "landing_url": "https://tree.opentreeoflife.org/",
            "doi": None,
            "version": f"{synth} / {taxonomy}",
            "license": "CC0 for Open Tree synthesis products, as stated by the project; the licence deed was not re-fetched in this run",
            "files": [f for f in FILES if "opentreeoflife.org" in f["download_url"]],
            "role": "exact name matches and induced subtrees on which monophyly was scored",
        },
        {
            "id": "pbdb-taxa-list",
            "name": "Paleobiology Database taxa/list, accepted species with appearance ages",
            "landing_url": "https://paleobiodb.org/data1.2/taxa/list_doc.html",
            "doi": None,
            "version": "live API data1.2",
            "license": "CC BY 4.0",
            "files": [f for f in FILES if "paleobiodb.org" in f["download_url"]],
            "role": "extinct and extant congeners and firstapp_max_ma",
        },
    ]
    res["status"] = "complete"
    res["data_kind"] = "biological"
    res["verdict"] = verdict
    res["confidence"] = confidence
    if reason:
        res["reason"] = reason
    elif "reason" in res:
        del res["reason"]
    res["method"] = method
    res["measured"] = measured
    res["datasets"] = datasets
    note = (
        f"M = {M} ({n_mono_true}/{n_m} monophyletic), E = {E} ({n_match}/{n_e} genera whose oldest dated species is extinct). "
        f"Monophyly half is {mono_state}; fossil half is {foss_state}."
    )
    caveats = list(res.get("caveats") or [])
    if not caveats or not caveats[0].startswith("M ="):
        caveats.insert(0, note)
    if M is not None and n_m and M < pre["support_fraction"] and (pre["support_fraction"] - M) * n_m <= 1.0 + 1e-9:
        short = (
            f"Monophyly is {n_mono_true}/{n_m}. One more monophyletic genus would meet the "
            f"pre-registered support fraction of {pre['support_fraction']}; the fossil half already does."
        )
        if short not in caveats:
            caveats.append(short)
    res["caveats"] = caveats
    deviations = list(res.get("deviations") or [])
    if NULL_CHILDREN and not any("hierarchyList" in str(d.get("what", "")) for d in deviations):
        deviations.append({
            "what": "ITIS hierarchyList entries that are JSON null were skipped and not treated as taxa.",
            "why": (
                f"The live service returned {NULL_CHILDREN} null child record(s), including "
                "hierarchyList: [null] for genera with no children. A null is not a species or a genus. "
                "Pass and fail thresholds were not changed."
            ),
        })
    if deviations:
        res["deviations"] = deviations
    json.dump(res, open(RESULT_PATH, "w"), indent=2)
    open(RESULT_PATH, "a").write("\n")
    summary = {"verdict": verdict, "confidence": confidence, "reason": reason, "M": M, "E": E, "n_m": n_m, "n_e": n_e,
               "mono_state": mono_state, "foss_state": foss_state, "mono_errors": mono_errors, "fossil_errors": fossil_errors}
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
