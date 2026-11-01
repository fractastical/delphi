#!/usr/bin/env python3
"""Assemble routes.json from the per-scale part files.

The `sources` block is DERIVED from the evidence entries inside the routes
(plus a few meta-only citations), so a PMID can never appear in the source
list without a route that actually uses it, and read-levels cannot drift
between the two.
"""
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PARTS = HERE / "parts"

ORDER = ["molecular", "gene_a", "gene_b", "cell", "tissue", "timing", "organism", "invitro"]

# The page declares exactly these eight scale keys, in this order. A route whose
# `scale` is not one of them renders in a visible "unplaced" group, so this list
# is pinned here and checked rather than inferred from the parts.
PAGE_SCALES = ["molecular", "gene", "cell", "tissue", "pattern", "timing", "organism", "invitro"]

STUDY_IDS = {"zrs-conservation", "shh-grem1-fgf-loop", "digit-turing"}

# read-level precedence: the highest level actually attained wins
RANK = {"could-not-access": 0, "search-summary": 1, "listing": 2, "abstract": 3, "full-text": 4}

# cited in meta (welfare / judge-gene shortlist) but not inside any route's evidence
EXTRA_SOURCES = [
    {
        "pmid": "28696160",
        "cite": "Zintzsch A et al. 2017, Lab Anim 51:573-582, 'Guidelines on severity assessment and classification of genetically altered mouse and rat lines'",
        "doi": "10.1177/0023677217718863",
        "read_level": "abstract",
    },
    {
        "pmid": "21271649",
        "cite": ("Garavelli L et al. 2010, Am J Med Genet A 155A:332-6, "
                 "'Al-Awadi-Raas-Rothschild (limb/pelvis/uterus-hypoplasia/aplasia) syndrome and WNT7A mutations'"),
        "doi": "10.1002/ajmg.a.33793",
        "read_level": "listing",
    },
    {
        "pmid": "15821733",
        "cite": ("Vega H et al. 2005, Nat Genet 37:468-70, 'Roberts syndrome is caused by mutations in ESCO2, "
                 "a human homolog of yeast ECO1 that is essential for the establishment of sister chromatid cohesion'"),
        "doi": "10.1038/ng1548",
        "read_level": "abstract",
    },
]


def load(name):
    with (PARTS / f"{name}.json").open() as fh:
        return json.load(fh)


def main():
    routes = []
    for name in ORDER:
        routes.extend(load(name))

    meta = load("meta")

    # the page's declared order governs the file's order, so the two cannot drift
    scale_rank = {k: i for i, k in enumerate(PAGE_SCALES)}
    routes.sort(key=lambda r: scale_rank.get(r["scale"], len(PAGE_SCALES)))

    # ---- derive sources -------------------------------------------------
    sources = {}

    def add(pmid, cite, doi, read_level):
        pmid = str(pmid)
        cur = sources.get(pmid)
        if cur is None:
            sources[pmid] = {
                "pmid": pmid,
                "cite": cite,
                "doi": doi,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "read_level": read_level,
            }
            return
        # keep the longest citation string and the best read level
        if len(cite) > len(cur["cite"]):
            cur["cite"] = cite
        if doi and not cur["doi"]:
            cur["doi"] = doi
        if RANK[read_level] > RANK[cur["read_level"]]:
            cur["read_level"] = read_level

    for r in routes:
        for ev in r["evidence"]:
            add(ev["pmid"], ev["cite"], ev.get("doi"), ev["read_level"])
    for s in EXTRA_SOURCES:
        add(s["pmid"], s["cite"], s["doi"], s["read_level"])

    source_list = sorted(sources.values(), key=lambda s: int(s["pmid"]))

    # ---- integrity checks ----------------------------------------------
    errs = []
    ids = [r["id"] for r in routes]
    if len(ids) != len(set(ids)):
        errs.append("duplicate route ids")

    declared = [s["key"] for s in meta["scales"]]
    if declared != PAGE_SCALES:
        errs.append(f"meta scales {declared} != page scales {PAGE_SCALES}")
    valid_scales = set(PAGE_SCALES)

    populated = {r["scale"] for r in routes}
    for k in PAGE_SCALES:
        if k not in populated:
            errs.append(f"scale '{k}' has no routes - its pin on the diagram would be dead")

    required = {
        "id", "scale", "title", "mechanism", "intervention", "predicted_phenotype",
        "evidence", "evidence_strength", "reversibility", "lethality_risk",
        "specificity", "difficulty", "what_we_would_run", "study", "open_questions",
    }
    valid_strength = {
        "direct_mouse_phenotype", "direct_other_species", "cis_regulatory_inference",
        "model_only", "proposed",
    }
    for r in routes:
        missing = required - set(r)
        if missing:
            errs.append(f"{r['id']}: missing {sorted(missing)}")
        if r["scale"] not in valid_scales:
            errs.append(f"{r['id']}: bad scale {r['scale']}")
        if r["evidence_strength"] not in valid_strength:
            errs.append(f"{r['id']}: bad evidence_strength {r['evidence_strength']}")
        if not r["evidence"]:
            errs.append(f"{r['id']}: no evidence entries")
        if r["study"] is not None and r["study"] not in STUDY_IDS:
            errs.append(f"{r['id']}: unknown study id {r['study']}")
        if r["study"] and r["study"] not in r["what_we_would_run"]:
            errs.append(f"{r['id']}: study {r['study']} not named in what_we_would_run")
        for ev in r["evidence"]:
            if ev["read_level"] not in RANK:
                errs.append(f"{r['id']}: bad read_level {ev['read_level']}")

    rec = meta["recommendation"]["single_best_route"]
    if rec not in set(ids):
        errs.append(f"recommendation points at unknown route {rec}")

    for c in meta["judge_gene_candidates"]:
        if str(c["key_pmid"]) not in sources:
            errs.append(f"judge candidate {c['gene']}: key_pmid {c['key_pmid']} not in sources")

    if errs:
        for e in errs:
            print("FAIL:", e, file=sys.stderr)
        return 1

    out = {
        "generated": "2026-11-01",
        "question": "How would you make a limbless mouse? A cross-scale design-route map.",
        "scales": meta["scales"],
        "routes": routes,
        "recommendation": meta["recommendation"],
        "judge_gene_candidates": meta["judge_gene_candidates"],
        "welfare": meta["welfare"],
        "sources": source_list,
        "limitations": meta["limitations"],
        "attribution": (
            "Bibliographic records and abstracts cited here were retrieved from PubMed (NCBI) "
            "on 2026-11-01; the DOI of every cited article is given in `sources`. "
            "Kvon et al. 2016 was additionally retrieved in full text from PubMed Central (PMC5484524)."
        ),
    }

    with (HERE / "routes.json").open("w") as fh:
        json.dump(out, fh, indent=2)
        fh.write("\n")

    by_scale = {}
    for r in routes:
        by_scale[r["scale"]] = by_scale.get(r["scale"], 0) + 1
    by_strength = {}
    for r in routes:
        by_strength[r["evidence_strength"]] = by_strength.get(r["evidence_strength"], 0) + 1
    by_read = {}
    for s in source_list:
        by_read[s["read_level"]] = by_read.get(s["read_level"], 0) + 1

    by_study = {}
    for r in routes:
        k = r["study"] or "(none)"
        by_study[k] = by_study.get(k, 0) + 1

    print(f"routes: {len(routes)}")
    for k in PAGE_SCALES:
        print(f"  {k:<10} {by_scale.get(k, 0)}")
    print("evidence_strength:", json.dumps(by_strength))
    print("study:", json.dumps(by_study))
    print(f"sources: {len(source_list)}  read_levels: {json.dumps(by_read)}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
