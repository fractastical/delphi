#!/usr/bin/env python3
"""Write <slice>/species.json for fetch.py from the animal species named by claim data tests.

    python3 test-data/organisms/claim-tests/candidates.py validated --evidence supports,mixed --kind biological \
        --exclude-slice lean-tested --exclude-lean

Collects Latin binomials from each selected claim's result.json (keys and string values) plus the
species-rank taxa test-data/organisms/merged/taxa.json lists as mentioned in the claim, keeps only
names GBIF matches exactly as an accepted or synonym species in Animalia, and records which claims
use each species. Claims naming more than --max-per-claim species (genus-level and regional counts
that merely list examples) keep the --max-per-claim most frequently named ones.
"""
import argparse, collections, json, os, re, sys, urllib.parse

sys.dont_write_bytecode = True  # a __pycache__ here would be read as a slice by validate.mjs and merge.mjs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch import REPO, HERE, get_json, strings  # noqa: E402

BINOMIAL = re.compile(r"\b([A-Z][a-z]{2,})[ _]([a-z]{3,})\b")
FISH = {"Actinopterygii", "Elasmobranchii", "Holocephali", "Petromyzonti", "Myxini", "Sarcopterygii", "Chondrichthyes"}
TETRAPODS = {"Mammalia", "Aves", "Reptilia", "Amphibia", "Squamata", "Testudines", "Crocodylia"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slice")
    ap.add_argument("--evidence", default="supports,mixed")
    ap.add_argument("--kind", default="biological")
    ap.add_argument("--exclude-slice", action="append", default=[])
    ap.add_argument("--exclude-lean", action="store_true", help="skip claims that are Lean-proved theorems")
    ap.add_argument("--max-per-claim", type=int, default=40)
    a = ap.parse_args()

    claims = json.load(open(os.path.join(REPO, "docs", "claims.json")))["claims"]
    ev = set(a.evidence.split(","))
    sel = [c for c in claims if c.get("evidence") in ev and (c.get("data_test") or {}).get("data_kind") == a.kind
           and not (a.exclude_lean and c.get("theorem"))]
    taken = set()
    for s in a.exclude_slice:
        taken |= {x["name"] for x in json.load(open(os.path.join(HERE, s, "species.json")))["species"]}
    merged = json.load(open(os.path.join(REPO, "test-data", "organisms", "merged", "taxa.json")))

    names_by_claim = {}
    for c in sel:
        cnt = collections.Counter()
        path = os.path.join(REPO, c["data_test"]["path"])
        if os.path.exists(path):
            for s in strings(json.load(open(path))):
                for g, sp in BINOMIAL.findall(s):
                    cnt[f"{g} {sp}"] += 1
        for t in merged:
            if c["id"] in (t.get("mentioned_in") or []) and t.get("rank") == "species":
                cnt[t["accepted_name"]] += 1
        names_by_claim[c["id"]] = cnt

    cache, species = {}, {}
    for cid, cnt in names_by_claim.items():
        kept = 0
        for name, _ in cnt.most_common():
            if kept >= a.max_per_claim:
                break
            if name not in cache:
                r = get_json(f"https://api.gbif.org/v1/species/match?strict=true&name={urllib.parse.quote(name)}")
                cache[name] = r["json"] or {}
            m = cache[name]
            if m.get("matchType") != "EXACT" or m.get("rank") != "SPECIES" or m.get("kingdom") != "Animalia":
                continue
            acc = m.get("species") or m.get("canonicalName")
            kept += 1
            if acc in taken:
                continue
            e = species.setdefault(acc, {"name": acc, "claims": [], "class": m.get("class")})
            if cid not in e["claims"]:
                e["claims"].append(cid)
        print(f"{cid}: {kept} animal species")

    out = []
    for e in sorted(species.values(), key=lambda e: e["name"]):
        cls = e.pop("class")
        if cls in FISH:
            e["lifebase"] = "fb"
        if cls in TETRAPODS or cls == "Insecta":
            e["anage"] = True
        out.append(e)
    sdir = os.path.join(HERE, a.slice)
    os.makedirs(sdir, exist_ok=True)
    cfg = {"slice": f"claim-tests/{a.slice}",
           "description": f"Animal species named by the data tests of claims with evidence {a.evidence} on {a.kind} data"
                          + (", excluding Lean-proved claims (see lean-tested)" if a.exclude_lean else "")
                          + f". Built by candidates.py from result.json binomials and book mentions, filtered to exact GBIF species matches in Animalia.",
           "claims": sorted(names_by_claim), "species": out}
    json.dump(cfg, open(os.path.join(sdir, "species.json"), "w"), indent=2)
    print(f"{len(out)} species -> {os.path.relpath(sdir, REPO)}/species.json")


if __name__ == "__main__":
    main()
