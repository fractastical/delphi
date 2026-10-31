#!/usr/bin/env python3
"""Test darwin1859-ch11-06: many genera are confined to one region; the most natural
genera (species most closely related) are local.

Clause 1: GBIF occurrence facets per continent, per class -> share of genera/families
confined to one region (>= 95% of records). Clause 2: mammal genus crown age from the
Upham et al. 2019 DNA-only MCC tree vs number of regions occupied.

Re-run:  python3 analysis.py        (downloads ~5 MB into ./data, writes derived/ and result.json)
"""
import csv
import hashlib
import json
import math
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import numpy as np
import requests
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

GBIF = "https://api.gbif.org/v1"
CLASSES = {  # GBIF backbone class keys
    "Mammalia": 359,
    "Aves": 212,
    "Amphibia": 131,
    # "Squamata" (key 358) is a pro-parte synonym with no occurrences in the current backbone;
    # Squamata is the class-rank taxon that holds ~95% of reptile genera.
    "Squamata": 11592253,
    "Magnoliopsida": 220,
    "Liliopsida": 196,
    "Pinopsida": 194,
}
CONTINENTS = ["AFRICA", "ANTARCTICA", "ASIA", "EUROPE", "NORTH_AMERICA", "OCEANIA", "SOUTH_AMERICA"]
REGION_OF = {c: ("EURASIA" if c in ("ASIA", "EUROPE") else c) for c in CONTINENTS}
BASIS = ["PRESERVED_SPECIMEN", "HUMAN_OBSERVATION", "MATERIAL_SAMPLE", "OBSERVATION",
         "MACHINE_OBSERVATION", "OCCURRENCE", "MATERIAL_CITATION"]  # excludes FOSSIL_SPECIMEN, LIVING_SPECIMEN
SPECIES_FACET_CLASSES = {"Mammalia", "Aves", "Amphibia", "Squamata", "Pinopsida"}
MIN_RECORDS = 20
CONFINED_SHARE = 0.95
REGION_PRESENCE_SHARE = 0.05

TREE_URL = ("https://raw.githubusercontent.com/n8upham/MamPhy_v1/master/_DATA/"
            "MamPhy_fullPosterior_BDvr_DNAonly_4098sp_topoFree_NDexp_MCC_v2_target.tre")

FILES = []  # provenance records for every file fetched
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "delphi-claim-tests/0.1 (https://github.com/fractastical/delphi)"


def fetch(url, fname, params=None):
    """GET url (with params) once, cache under data/, record provenance, return bytes."""
    path = os.path.join(DATA, fname)
    meta_path = path + ".meta.json"
    if os.path.exists(path) and os.path.exists(meta_path):
        with open(meta_path) as fh:
            FILES.append(json.load(fh))
        with open(path, "rb") as fh:
            return fh.read()
    for attempt in range(5):
        try:
            r = SESSION.get(url, params=params, timeout=300)
            if r.status_code == 200:
                break
            print(f"  HTTP {r.status_code} for {r.url}", file=sys.stderr)
        except requests.RequestException as e:
            print(f"  retry {attempt}: {e}", file=sys.stderr)
        time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {url}")
    body = r.content
    meta = {
        "download_url": r.url,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
    }
    with open(path, "wb") as fh:
        fh.write(body)
    with open(meta_path, "w") as fh:
        json.dump(meta, fh)
    FILES.append(meta)
    return body


# ----------------------------------------------------------------------------- clause 1
def gbif_facets(class_name, class_key, continent):
    facets = ["genusKey", "familyKey"] + (["speciesKey"] if class_name in SPECIES_FACET_CLASSES else [])
    params = [("classKey", class_key), ("continent", continent), ("hasCoordinate", "true"),
              ("hasGeospatialIssue", "false"), ("limit", 0), ("facetLimit", 100000)]
    params += [("basisOfRecord", b) for b in BASIS]
    params += [("facet", f) for f in facets]
    body = fetch(f"{GBIF}/occurrence/search", f"gbif_{class_name}_{continent}.json", params=params)
    d = json.loads(body)
    out = {}
    for fac in d.get("facets", []):
        out[fac["field"]] = {int(c["name"]): int(c["count"]) for c in fac["counts"]}
    return out


def confinement_table(counts_by_region):
    """counts_by_region: {taxonKey: {region: n}} -> rows with shares."""
    rows = []
    for key, regs in counts_by_region.items():
        total = sum(regs.values())
        if total < MIN_RECORDS:
            continue
        top_region, top_n = max(regs.items(), key=lambda kv: kv[1])
        share = top_n / total
        n_regions = sum(1 for n in regs.values() if n / total >= REGION_PRESENCE_SHARE)
        rows.append({"key": key, "total": total, "top_region": top_region, "top_share": share,
                     "n_regions_5pct": n_regions, "confined95": share >= CONFINED_SHARE,
                     "confined99": share >= 0.99, "confined90": share >= 0.90})
    return rows


def clause1():
    per_class = {}
    mammal_genus_rows = None
    for cname, ckey in CLASSES.items():
        print(f"GBIF facets for {cname}", file=sys.stderr)
        acc = {"GENUS_KEY": {}, "FAMILY_KEY": {}, "SPECIES_KEY": {}}
        for cont in CONTINENTS:
            fac = gbif_facets(cname, ckey, cont)
            region = REGION_OF[cont]
            for field, counts in fac.items():
                for key, n in counts.items():
                    acc[field].setdefault(key, {})
                    acc[field][key][region] = acc[field][key].get(region, 0) + n
        summary = {}
        for field, label in (("FAMILY_KEY", "family"), ("GENUS_KEY", "genus"), ("SPECIES_KEY", "species")):
            rows = confinement_table(acc[field])
            if not rows:
                continue
            n = len(rows)
            summary[label] = {
                "n_assessed": n,
                "n_with_records": len(acc[field]),
                "confined95": sum(r["confined95"] for r in rows) / n,
                "confined99": sum(r["confined99"] for r in rows) / n,
                "confined90": sum(r["confined90"] for r in rows) / n,
                "mean_regions_5pct": float(np.mean([r["n_regions_5pct"] for r in rows])),
            }
            if cname == "Mammalia" and label == "genus":
                mammal_genus_rows = rows
        per_class[cname] = summary
        # per-taxon table; genus rows are dropped for the very large plant classes to keep derived/ < 200 KB per file
        ranks = (("FAMILY_KEY", "family"), ("GENUS_KEY", "genus"))
        if sum(len(acc[f]) for f, _ in ranks) > 4000:
            ranks = ranks[:1]
        with open(os.path.join(DERIVED, f"confinement_{cname}.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["rank", "gbif_key", "total_records", "top_region", "top_share", "n_regions_5pct"])
            for field, label in ranks:
                for r in confinement_table(acc[field]):
                    w.writerow([label, r["key"], r["total"], r["top_region"], f"{r['top_share']:.4f}", r["n_regions_5pct"]])
    return per_class, mammal_genus_rows


# ----------------------------------------------------------------------------- clause 2
def genus_names(keys):
    def one(k):
        body = fetch(f"{GBIF}/species/{k}", f"gbif_species_{k}.json")
        d = json.loads(body)
        return k, d.get("canonicalName"), d.get("rank")
    with ThreadPoolExecutor(max_workers=6) as ex:
        return list(ex.map(one, keys))


def parse_newick(s):
    """Minimal Newick parser -> (children, parent, label, brlen) arrays. Node 0 is root."""
    children, parent, label, brlen = [[]], [-1], [None], [0.0]
    cur = 0
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "(":
            children.append([]); parent.append(cur); label.append(None); brlen.append(0.0)
            children[cur].append(len(children) - 1)
            cur = len(children) - 1
            i += 1
        elif ch == ",":
            cur = parent[cur]
            children.append([]); parent.append(cur); label.append(None); brlen.append(0.0)
            children[cur].append(len(children) - 1)
            cur = len(children) - 1
            i += 1
        elif ch == ")":
            cur = parent[cur]
            i += 1
        elif ch == ":":
            j = i + 1
            while j < n and s[j] not in ",();":
                j += 1
            brlen[cur] = float(s[i + 1:j])
            i = j
        elif ch == ";":
            break
        else:
            j = i
            while j < n and s[j] not in ",():;":
                j += 1
            label[cur] = s[i:j].strip().strip("'")
            i = j
    return children, parent, label, brlen


def load_tree():
    raw = fetch(TREE_URL, "upham2019_mamphy_dnaonly_mcc.tre").decode("utf-8", "replace")
    txt = re.sub(r"\[[^\]]*\]", "", raw)  # strip NEXUS/BEAST annotations
    translate = {}
    m = re.search(r"translate\s+(.*?);", txt, re.S | re.I)
    if m:
        for line in m.group(1).split(","):
            parts = line.strip().split(None, 1)
            if len(parts) == 2:
                translate[parts[0]] = parts[1].strip().strip("'")
    m = re.search(r"tree\s+\S+\s*=\s*(\(.*?;)", txt, re.S | re.I)
    newick = m.group(1) if m else txt[txt.index("("):txt.rindex(";") + 1]
    children, parent, label, brlen = parse_newick(newick)
    if translate:
        label = [translate.get(l, l) if l else l for l in label]
    # node ages: height above the tips, assuming an ultrametric dated tree
    depth = [0.0] * len(children)
    order = [0]
    for node in order:
        for c in children[node]:
            depth[c] = depth[node] + brlen[c]
            order.append(c)
    tips = [i for i in range(len(children)) if not children[i]]
    root_height = float(np.median([depth[t] for t in tips]))
    age = [root_height - d for d in depth]
    return children, parent, label, age, tips


def clause2(mammal_genus_rows):
    children, parent, label, age, tips = load_tree()
    genus_tips = {}
    for t in tips:
        genus = label[t].split("_")[0]
        genus_tips.setdefault(genus, []).append(t)

    def ancestors(node):
        path = []
        while node != -1:
            path.append(node)
            node = parent[node]
        return path

    crown = {}
    for g, ts in genus_tips.items():
        if len(ts) < 2:
            continue
        common = set(ancestors(ts[0]))
        for t in ts[1:]:
            common &= set(ancestors(t))
        mrca = min(common, key=lambda n: age[n])
        crown[g] = (age[mrca], len(ts))

    keys = [r["key"] for r in mammal_genus_rows]
    names = genus_names(keys)
    by_key = {r["key"]: r for r in mammal_genus_rows}
    merged = []
    for k, name, rank in names:
        if rank != "GENUS" or name not in crown:
            continue
        r = by_key[k]
        merged.append({"genus": name, "gbif_key": k, "crown_age_myr": crown[name][0],
                       "n_species_tree": crown[name][1], "records": r["total"],
                       "n_regions_5pct": r["n_regions_5pct"], "confined95": int(r["confined95"])})
    with open(os.path.join(DERIVED, "mammal_genus_crown_age_regions.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(merged[0].keys()))
        w.writeheader()
        w.writerows(merged)

    x = np.array([m["crown_age_myr"] for m in merged])
    y = np.array([m["n_regions_5pct"] for m in merged], dtype=float)
    z = np.log(np.array([m["n_species_tree"] for m in merged], dtype=float))
    rho, p = stats.spearmanr(x, y)
    # partial Spearman: Pearson correlation of rank residuals after regressing on rank(z)
    rx, ry, rz = stats.rankdata(x), stats.rankdata(y), stats.rankdata(z)
    def resid(a, b):
        A = np.vstack([np.ones_like(b), b]).T
        coef, *_ = np.linalg.lstsq(A, a, rcond=None)
        return a - A @ coef
    ex, ey = resid(rx, rz), resid(ry, rz)
    prho = float(np.corrcoef(ex, ey)[0, 1])
    n = len(x)
    t = prho * math.sqrt((n - 3) / max(1e-12, 1 - prho ** 2))
    pp = float(2 * stats.t.sf(abs(t), n - 3))
    q1, q2 = np.quantile(x, [1 / 3, 2 / 3])
    young = [m for m in merged if m["crown_age_myr"] <= q1]
    old = [m for m in merged if m["crown_age_myr"] > q2]
    fy = sum(m["confined95"] for m in young) / len(young)
    fo = sum(m["confined95"] for m in old) / len(old)
    rho_rich, p_rich = stats.spearmanr(z, y)
    return {
        "n_genera": n,
        "spearman_rho_crownage_vs_nregions": float(rho), "p": float(p),
        "partial_spearman_rho_controlling_log_richness": prho, "partial_p": pp,
        "spearman_rho_log_richness_vs_nregions": float(rho_rich), "p_richness": float(p_rich),
        "tercile_cut_myr": [float(q1), float(q2)],
        "youngest_tercile_confined95": fy, "n_young": len(young),
        "oldest_tercile_confined95": fo, "n_old": len(old),
        "median_crown_age_myr": float(np.median(x)),
    }


# ----------------------------------------------------------------------------- verdict
def main():
    per_class, mammal_rows = clause1()
    c2 = clause2(mammal_rows)

    genus_frac = {c: s["genus"]["confined95"] for c, s in per_class.items()}
    fam_frac = {c: s["family"]["confined95"] for c, s in per_class.items()}
    n_majority = sum(1 for v in genus_frac.values() if v > 0.5)
    n_gradient = sum(1 for c in per_class if genus_frac[c] > fam_frac[c])
    clause1_pass = n_majority >= 5 and n_gradient >= 5
    clause1_fail = n_majority <= 4 or n_gradient <= 4
    clause2_pass = (c2["partial_spearman_rho_controlling_log_richness"] > 0 and c2["partial_p"] < 0.05
                    and c2["youngest_tercile_confined95"] > c2["oldest_tercile_confined95"])
    if clause1_pass and clause2_pass:
        verdict = "supports"
    elif clause1_pass or clause2_pass:
        verdict = "mixed"
    else:
        verdict = "refutes"

    measured = {
        "value": float(np.mean(list(genus_frac.values()))),
        "unit": "mean across classes of the fraction of assessable genera with >= 95% of records in one region",
        "n": int(sum(s["genus"]["n_assessed"] for s in per_class.values())),
        "uncertainty": None,
        "extra": {
            "per_class": per_class,
            "classes_with_majority_of_genera_confined": n_majority,
            "classes_with_genera_more_confined_than_families": n_gradient,
            "clause1_pass": clause1_pass,
            "clause2_mammals": c2,
            "clause2_pass": clause2_pass,
        },
    }
    with open(os.path.join(HERE, "result.json")) as fh:
        res = json.load(fh)
    gbif_files = [f for f in FILES if "api.gbif.org/v1/occurrence" in f["download_url"]]
    name_files = [f for f in FILES if "api.gbif.org/v1/species/" in f["download_url"]]
    tree_files = [f for f in FILES if "MamPhy" in f["download_url"]]
    res["datasets"] = [
        {
            "id": "gbif-occurrence-search-facets",
            "name": "GBIF occurrence search API, faceted counts by genus/family/species key per continent",
            "landing_url": "https://www.gbif.org/occurrence/search",
            "doi": None,
            "version": "live index, retrieved " + gbif_files[0]["retrieved_at"][:10],
            "license": "mixed per publishing dataset (CC0, CC BY, CC BY-NC)",
            "files": gbif_files,
            "role": "occurrence counts per taxon per continent (clause 1 and regions for clause 2)",
        },
        {
            "id": "gbif-species-api-genus-names",
            "name": "GBIF Backbone Taxonomy species API (genus names for mammal genus keys)",
            "landing_url": "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",
            "doi": "10.15468/39omei",
            "version": "live, retrieved " + name_files[0]["retrieved_at"][:10],
            "license": "CC BY 4.0",
            "files": [{"download_url": GBIF + "/species/{genusKey}", "retrieved_at": name_files[0]["retrieved_at"],
                       "byte_size": sum(f["byte_size"] for f in name_files),
                       "sha256": hashlib.sha256("".join(sorted(f["sha256"] for f in name_files)).encode()).hexdigest(),
                       "note": f"{len(name_files)} per-key JSON responses; sha256 is of the sorted concatenation of their individual sha256 digests"}],
            "role": "map GBIF mammal genus keys to canonical genus names",
        },
        {
            "id": "upham2019-mamphy-dnaonly-mcc-tree",
            "name": "Upham, Esselstyn & Jetz (2019) mammal phylogeny, DNA-only 4098-species node-dated MCC tree (NDexp, topoFree)",
            "landing_url": "https://github.com/n8upham/MamPhy_v1",
            "doi": "10.1371/journal.pbio.3000494",
            "version": "MamPhy_v1 repository, master branch",
            "license": "CC BY 4.0",
            "files": tree_files,
            "role": "genus crown ages (MRCA age of sampled congeners) for clause 2",
        },
    ]
    res["method"] = (
        "For seven GBIF backbone classes and each of seven GBIF continents, one faceted occurrence search "
        "(coordinates present, no geospatial issue, fossil and living specimens excluded) returned record counts per "
        "genus, family (and species for the smaller classes). Europe and Asia were merged into Eurasia. Taxa with >= 20 "
        "records were scored as confined if >= 95% of records fell in one region, and the fraction of confined taxa was "
        "compared between genera and families within each class. For mammals, genus crown ages were computed as the MRCA "
        "age of sampled congeners in the Upham et al. 2019 DNA-only MCC tree, genus names were matched to GBIF genus keys, "
        "and crown age was correlated (Spearman, and partial Spearman controlling log sampled richness) with the number of "
        "regions holding >= 5% of the genus's records; single-region fractions were compared between youngest and oldest "
        "crown-age terciles."
    )
    res["measured"] = measured
    res["verdict"] = verdict
    res["confidence"] = 0.7
    res["caveats"] = [
        "GBIF 'Reptilia' (classKey 358) is a pro-parte synonym with no occurrences in the current backbone, so the pre-registered reptile class was run as Squamata (classKey 11592253), which holds most reptile genera.",
        "GBIF continents are a coarse proxy for Darwin's biogeographic regions; merging Europe and Asia follows the Palaearctic but leaves Wallace's line and the Nearctic/Neotropical boundary at the continental edge.",
        "Genus-level 'assessable' counts include extinct genera that have non-fossil basis-of-record entries and genera whose records are introductions or captives not flagged as LIVING_SPECIMEN; both bias against confinement, so clause 1 is conservative.",
        "Recording effort is very uneven (Europe and North America dominate); the >= 20 record floor reduces but does not remove under-recording of tropical taxa, which could make some truly widespread genera look confined.",
        "Clause 2 is a modern reinterpretation: 'most natural genera' was read as young crown age in a dated molecular tree. Crown age depends on which species were sampled (DNA-only tree) and on taxonomic lumping/splitting, and only 577 of 1890 assessable mammal genera had >= 2 sampled species. The negative partial correlation (older genera occupy fewer regions, controlling for richness) is significant but small.",
        "Sub-families and sections of genera, which Darwin names explicitly, are not represented in the GBIF backbone and were not tested; the family-to-genus-to-species gradient is consistent with his rank ordering.",
    ]
    res["status"] = "complete"
    res["agent"]["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with open(os.path.join(HERE, "result.json"), "w") as fh:
        json.dump(res, fh, indent=2)
        fh.write("\n")
    print(json.dumps({"verdict": verdict, "genus_confined_by_class": genus_frac,
                      "family_confined_by_class": fam_frac, "clause2": c2}, indent=2))


if __name__ == "__main__":
    main()
