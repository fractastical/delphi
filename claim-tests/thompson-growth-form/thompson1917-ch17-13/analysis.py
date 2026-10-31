#!/usr/bin/env python3
"""thompson1917-ch17-13: are Perissodactyla closer to Leporidae than to other ungulates (and leporids closer
to perissodactyls than to rodents)? Tested on the Open Tree of Life synthetic tree and NCBI Taxonomy.

Saves every API response under data/ with its SHA-256 and writes derived/measured.json, derived/files.json.
"""
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

OT = "https://api.opentreeoflife.org/v3"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
UA = {"User-Agent": "delphi-claim-tests/1.0"}

GROUPS = {
    "perissodactyla": ["Equus caballus", "Ceratotherium simum", "Tapirus terrestris"],
    "artiodactyla": ["Bos taurus", "Sus scrofa", "Camelus dromedarius"],
    "other_ungulata_1917": ["Loxodonta africana", "Procavia capensis"],
    "leporidae": ["Oryctolagus cuniculus", "Lepus europaeus", "Sylvilagus floridanus"],
    "other_lagomorpha": ["Ochotona princeps"],
    "rodentia": ["Mus musculus", "Rattus norvegicus", "Sciurus carolinensis", "Cavia porcellus", "Castor canadensis"],
    "outgroups": ["Canis lupus", "Homo sapiens", "Monodelphis domestica"],
}
NCBI_TAXA = ["Perissodactyla", "Leporidae", "Artiodactyla", "Rodentia", "Lagomorpha"]


def record(path, url, note):
    h = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return {"download_url": url, "retrieved_at": datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": os.path.getsize(path), "sha256": h, "request": note}


def post_json(url, body, dest):
    if not os.path.exists(dest):
        r = requests.post(url, json=body, timeout=120, headers=UA)
        r.raise_for_status()
        open(dest, "w").write(r.text)
    return json.load(open(dest))


def get_text(url, dest):
    if not os.path.exists(dest):
        r = requests.get(url, timeout=120, headers=UA)
        r.raise_for_status()
        open(dest, "w").write(r.text)
    return open(dest).read()


# ---------- minimal Newick parsing ----------
def parse_newick(s):
    """Return nested tuples: leaf = label string, internal = (label, [children])."""
    s = s.strip().rstrip(";")
    pos = 0

    def read_label():
        nonlocal pos
        if pos < len(s) and s[pos] == "'":  # quoted label, may contain spaces and parentheses
            end = s.index("'", pos + 1)
            label = s[pos + 1:end]
            pos = end + 1
        else:
            start = pos
            while pos < len(s) and s[pos] not in ",();:":
                pos += 1
            label = s[start:pos]
        if pos < len(s) and s[pos] == ":":  # skip branch length
            pos += 1
            while pos < len(s) and s[pos] not in ",();":
                pos += 1
        return label

    def read_node():
        nonlocal pos
        if s[pos] == "(":
            pos += 1
            children = [read_node()]
            while s[pos] == ",":
                pos += 1
                children.append(read_node())
            assert s[pos] == ")"
            pos += 1
            return (read_label(), children)
        return read_label()

    return read_node()


def leaves(node):
    if isinstance(node, str):
        return [node]
    return [l for c in node[1] for l in leaves(c)]


def smallest_clade_containing(node, targets):
    """Smallest subtree whose leaf set contains all targets."""
    if isinstance(node, str):
        return node if targets <= {node} else None
    for c in node[1]:
        if targets <= set(leaves(c)):
            return smallest_clade_containing(c, targets)
    return node


def ott_label_to_name(label):
    # induced_subtree labels look like "Equus_caballus_ott541953" or "mrcaott..."
    m = re.match(r"(.+)_ott\d+$", label)
    return m.group(1).replace("_", " ") if m else label


def main():
    files = []
    names = [n for g in GROUPS.values() for n in g]
    tnrs = post_json(f"{OT}/tnrs/match_names", {"names": names, "context_name": "Animals", "do_approximate_matching": False},
                     os.path.join(DATA, "tnrs.json"))
    files.append(record(os.path.join(DATA, "tnrs.json"), f"{OT}/tnrs/match_names", {"names": names, "context_name": "Animals"}))
    ott = {}
    for res in tnrs["results"]:
        matches = [m for m in res["matches"] if not m.get("is_synonym")] or res["matches"]
        ott[res["name"]] = matches[0]["taxon"]["ott_id"]
    missing = [n for n in names if n not in ott]
    if missing:
        raise SystemExit(f"TNRS failed for {missing}")

    about = post_json(f"{OT}/tree_of_life/about", {}, os.path.join(DATA, "about.json"))
    files.append(record(os.path.join(DATA, "about.json"), f"{OT}/tree_of_life/about", {}))
    sub = post_json(f"{OT}/tree_of_life/induced_subtree", {"ott_ids": list(ott.values()), "label_format": "name_and_id"},
                    os.path.join(DATA, "induced_subtree.json"))
    files.append(record(os.path.join(DATA, "induced_subtree.json"), f"{OT}/tree_of_life/induced_subtree",
                        {"ott_ids": list(ott.values()), "label_format": "name_and_id"}))
    newick = sub["newick"]
    tree = parse_newick(newick)
    tip_names = {ott_label_to_name(l) for l in leaves(tree)}
    name_to_group = {n: g for g, ns in GROUPS.items() for n in ns}

    def tips_of(group):
        return {l for l in leaves(tree) if name_to_group.get(ott_label_to_name(l)) == group}

    targets = tips_of("perissodactyla") | tips_of("leporidae")
    clade = smallest_clade_containing(tree, targets)
    clade_tips = {ott_label_to_name(l) for l in leaves(clade)}
    groups_in_clade = {g: sorted(n for n in ns if n in clade_tips) for g, ns in GROUPS.items()}
    sub1 = len(groups_in_clade["artiodactyla"]) == 0
    sub2 = len(groups_in_clade["rodentia"]) == 0
    # Where do perissodactyls actually sit? Smallest clade with perissodactyls + artiodactyls, and leporids + rodents.
    clade_pa = smallest_clade_containing(tree, tips_of("perissodactyla") | tips_of("artiodactyla"))
    clade_lr = smallest_clade_containing(tree, tips_of("leporidae") | tips_of("rodentia"))
    pa_tips = {ott_label_to_name(l) for l in leaves(clade_pa)}
    lr_tips = {ott_label_to_name(l) for l in leaves(clade_lr)}

    # NCBI Taxonomy lineages.
    ncbi = {}
    for taxon in NCBI_TAXA:
        es = get_text(f"{EUTILS}/esearch.fcgi?db=taxonomy&term={taxon}[Scientific Name]&retmode=json", os.path.join(DATA, f"esearch_{taxon}.json"))
        files.append(record(os.path.join(DATA, f"esearch_{taxon}.json"), f"{EUTILS}/esearch.fcgi?db=taxonomy&term={taxon}[Scientific Name]&retmode=json", None))
        taxid = json.loads(es)["esearchresult"]["idlist"][0]
        xml = get_text(f"{EUTILS}/efetch.fcgi?db=taxonomy&id={taxid}&retmode=xml", os.path.join(DATA, f"efetch_{taxon}.xml"))
        files.append(record(os.path.join(DATA, f"efetch_{taxon}.xml"), f"{EUTILS}/efetch.fcgi?db=taxonomy&id={taxid}&retmode=xml", None))
        root = ET.fromstring(xml)
        lineage = [t.find("ScientificName").text for t in root.find("Taxon").find("LineageEx").findall("Taxon")]
        ncbi[taxon] = {"taxid": taxid, "lineage": lineage}
    lin = {k: set(v["lineage"]) for k, v in ncbi.items()}
    shared_pl = lin["Perissodactyla"] & lin["Leporidae"]
    shared_pl_excl = shared_pl - lin["Artiodactyla"] - lin["Rodentia"]
    boreo_and_below = [x for x in ncbi["Perissodactyla"]["lineage"][ncbi["Perissodactyla"]["lineage"].index("Boreoeutheria") + 1:]] if "Boreoeutheria" in lin["Perissodactyla"] else []
    ncbi_check = {
        "shared_named_clades_perisso_leporidae": sorted(shared_pl),
        "shared_clades_excluding_artiodactyla_and_rodentia": sorted(shared_pl_excl),
        "perissodactyla_in_laurasiatheria": "Laurasiatheria" in lin["Perissodactyla"],
        "artiodactyla_in_laurasiatheria": "Laurasiatheria" in lin["Artiodactyla"],
        "leporidae_in_glires": "Glires" in lin["Leporidae"],
        "rodentia_in_glires": "Glires" in lin["Rodentia"],
        "perissodactyla_lineage_below_boreoeutheria": boreo_and_below,
        "leporidae_lineage": ncbi["Leporidae"]["lineage"],
    }

    out = {
        "opentree_synth_version": about.get("synth_id"),
        "opentree_taxonomy_version": about.get("taxonomy_version"),
        "n_tips_requested": len(names),
        "n_tips_in_tree": len(tip_names),
        "ott_ids": ott,
        "newick": newick,
        "smallest_clade_with_perissodactyla_and_leporidae": {"n_tips": len(clade_tips), "tips": sorted(clade_tips), "groups_present": groups_in_clade},
        "subclaim1_perisso_closer_to_leporids_than_artiodactyls": sub1,
        "subclaim2_leporids_closer_to_perisso_than_rodents": sub2,
        "smallest_clade_perisso_plus_artiodactyla": {"n_tips": len(pa_tips), "contains_leporidae": bool(pa_tips & set(GROUPS["leporidae"])), "contains_rodentia": bool(pa_tips & set(GROUPS["rodentia"]))},
        "smallest_clade_leporidae_plus_rodentia": {"n_tips": len(lr_tips), "contains_perissodactyla": bool(lr_tips & set(GROUPS["perissodactyla"])), "contains_artiodactyla": bool(lr_tips & set(GROUPS["artiodactyla"]))},
        "ncbi_taxonomy": ncbi_check,
    }
    if sub1 and sub2:
        verdict = "supports"
    elif (not sub1) and (not sub2):
        verdict = "refutes"
    else:
        verdict = "mixed"
    out["verdict_by_prereg_rule"] = verdict
    json.dump(out, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(files, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
