#!/usr/bin/env python3
"""Check the genetic-blueprints package: manifest hashes, citation integrity, and the separations the package promises. Stdlib only.

    python3 artifacts/genetic-blueprints/check.py [--cache DIR] [--freeze]

--cache DIR  also verifies each pinned source response hash and that every quoted passage appears in it (the responses are NOT in the repository).
--freeze     rewrites manifest.json from the current files.
Exit 0 only if every check passes; a skipped cache check is reported as skipped, never as passed.
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FILES = ["blueprints.json", "sources.json"]
DOC = "docs/research/genetic-blueprints-2026-10-31.md"
LEVELS = {"full-text", "abstract", "listing", "search-summary", "could-not-access"}
REQUIRED = {"bp-1-regeneration-enhancer-reporter", "bp-2-development-versus-regeneration-contrast", "bp-3-endogenous-locus-knock-in", "bp-4-bac-carried-locus-reporter"}
APPROACHES = {"tol2-plasmid", "bac-transgenesis", "endogenous-knock-in", "transient-delivery", "autonomous-artificial-chromosome", "landing-site-integration"}
MAP_ROWS = {"basal-epithelium", "surface-epithelium", "fibroblast-mesenchyme", "osteoblast-and-joint", "hematopoietic", "pectoral-fin-field", "organism-reference"}
STALE = ["promoter-compatibility abstract", "body of the paper not read", "every enhancer evidence item here is from regenerating adult fin", "Every enhancer item read is from regenerating adult fin"]
SRC_FILE = {"tree2016": "pmc4844022.txt", "fin-multiome2025": "genomeres.txt", "fin-epigenome2020": "pmc7047409.txt", "promoter-compat2023": "pmc10211259.txt", "bac-tol2-2011": "nprot.txt", "knockin-cre2021": "sci.txt", "piglet2024": "piglet.txt", "bac-plasmids2016": "bac2016.txt", "hac2024": "hac.txt"}


def sha(b):
    return hashlib.sha256(b).hexdigest()


def norm(t):
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t).replace("_", "").replace("*", "")
    return re.sub(r"\s+", " ", t)


def load(name, base=HERE):
    return json.load(open(os.path.join(base, name)))


def check(base=HERE, cache=None, repo_root=None):
    errs, notes = [], []
    bp, sc = load("blueprints.json", base), load("sources.json", base)
    man = load("manifest.json", base) if os.path.exists(os.path.join(base, "manifest.json")) else None
    if man is None:
        errs.append("manifest.json missing")
    else:
        for f in man["files"]:
            p = os.path.join(repo_root or os.path.dirname(os.path.dirname(base)), f["path"])
            if not os.path.exists(p) or sha(open(p, "rb").read()) != f["sha256"]:
                errs.append(f"manifest hash differs or file missing: {f['path']}")
    srcs = {s["id"]: s for s in sc["sources"]}
    for s in srcs.values():
        if s["read_level"] not in LEVELS or s.get("response_in_repository") is not False or not re.fullmatch(r"[0-9a-f]{64}", s["response_sha256"]):
            errs.append(f"source {s['id']}: bad read_level, response flag or hash")
    cites = bp["citation_table"]
    for k, c in cites.items():
        s = srcs.get(c["source"])
        if s is None:
            errs.append(f"citation {k}: unknown source {c['source']}")
        elif c["read_level"] != s["read_level"]:
            errs.append(f"citation {k}: read_level {c['read_level']} differs from source {s['read_level']}")
        if not c["quote"].strip():
            errs.append(f"citation {k}: empty quote")
    if cache:
        for sid, fn in SRC_FILE.items():
            p = os.path.join(cache, fn)
            if not os.path.exists(p):
                errs.append(f"cache missing {fn}")
                continue
            raw = open(p, "rb").read()
            if sha(raw) != srcs[sid]["response_sha256"]:
                errs.append(f"cache {fn}: sha256 differs from the pinned value")
            text = norm(raw.decode("utf-8", "replace"))
            for k, c in cites.items():
                if c["source"] == sid and c["quote"] not in text:
                    errs.append(f"citation {k}: quote not found in {fn}")
    else:
        notes.append("SKIPPED: source response hashes and quote presence (no --cache)")
    ids = {d["id"] for d in bp["designs"]}
    if ids != REQUIRED:
        errs.append(f"design ids {sorted(ids)}")
    for d in bp["designs"]:
        i = d["implementation"]
        for k in ("cargo", "carrier", "delivery", "integration"):
            if not i.get(k):
                errs.append(f"{d['id']}: implementation.{k} missing")
        if len({json.dumps(i[k], sort_keys=True) for k in ("carrier", "delivery", "integration")}) < 3 and d["id"] != "bp-2-development-versus-regeneration-contrast":
            errs.append(f"{d['id']}: carrier, delivery and integration are not three distinct statements")
        cargo = json.dumps(i["cargo"])
        enh = i["cargo"].get("enhancer")
        named = isinstance(enh, dict) and enh.get("coordinates") is None and enh.get("sequence") is None and enh.get("source") in srcs
        if "UNSPECIFIED" not in cargo and not named:
            errs.append(f"{d['id']}: cargo is neither UNSPECIFIED nor a source-named element with null coordinates and sequence")
        if isinstance(enh, dict) and (enh.get("coordinates") is not None or enh.get("sequence") is not None):
            errs.append(f"{d['id']}: enhancer coordinates or sequence are set although the supplement was not read")
        for ch in i.get("provenance_of_choices", []):
            if not str(ch.get("status", "")).startswith(("sourced", "root proposal")):
                errs.append(f"{d['id']}: a choice is neither sourced nor a root proposal: {ch.get('choice')}")
        if d.get("cell_program_binding", {}).get("validation_status") != "unknown":
            errs.append(f"{d['id']}: cell_program_binding.validation_status must be unknown")
        for r in d.get("cell_program_binding", {}).get("map_rows", []):
            if r not in MAP_ROWS:
                errs.append(f"{d['id']}: unknown map row {r}")
        if d.get("expression_kinetics", {}).get("status") != "UNKNOWN":
            errs.append(f"{d['id']}: expression_kinetics must be UNKNOWN unless a source supplies it")
        if "NOT" not in d.get("off_target_coverage", ""):
            errs.append(f"{d['id']}: off_target_coverage must name what is NOT covered")
        if "source-only" not in d.get("markers_status", ""):
            errs.append(f"{d['id']}: markers must be labelled source-only")
        if not d["flying_fish_transfer"].startswith("unknown"):
            errs.append(f"{d['id']}: flying_fish_transfer is not 'unknown'")
        for need in ("target_tissues", "off_target_tissues_to_check", "proposed_readouts", "causal_gaps", "citations", "cell_context_and_stage", "cell_stage_specificity", "off_target_coverage", "markers_status"):
            if not d.get(need):
                errs.append(f"{d['id']}: {need} empty")
        for n in d["natural_regulatory_evidence"]:
            for k in n["citations"]:
                if k not in cites:
                    errs.append(f"{d['id']}: unknown citation {k}")
    if not any("developmental-fin versus regeneration" in g.lower() for d in bp["designs"] for g in d["causal_gaps"]):
        errs.append("no design states the developmental-fin versus regeneration gap")
    bac = next(d for d in bp["designs"] if d["id"] == "bp-4-bac-carried-locus-reporter")
    if "NOT an autonomous fish chromosome" not in bac["implementation"]["carrier"]:
        errs.append("BAC carrier text must say it is NOT an autonomous fish chromosome")
    for m in re.finditer(r"[^.]*autonomous[^.]*\.?", json.dumps(bp)):
        t = m.group(0).lower()
        if "bac" in t and "not" not in t and "no " not in t:
            errs.append(f"a sentence mentions BAC and autonomous without a negation: {m.group(0)[:100]}")
    rows = {r["id"]: r for r in bp["comparison"]["rows"]}
    if set(rows) != APPROACHES:
        errs.append(f"comparison rows {sorted(rows)}")
    for r in rows.values():
        if not r["citations"] and "NO source read" not in r["evidence"]:
            errs.append(f"comparison {r['id']}: no citation and no explicit 'NO source read'")
        for k in r["citations"]:
            if k not in cites:
                errs.append(f"comparison {r['id']}: unknown citation {k}")
    hac = rows["autonomous-artificial-chromosome"]
    if "NO source read describes one in fish" not in hac["evidence"] or "HUMAN" not in hac["evidence"]:
        errs.append("autonomous chromosome row must say no fish source and that the human source says nothing about fish")
    cp = bp.get("cell_program_blueprints", [])
    if len(cp) < 3 or any(x["validation_status"] != "unknown" or not (x["map_rows"] or "NO neural or muscle row" in " ".join(x["missing_links"])) for x in cp):
        errs.append("need 3 cell-program blueprints with validation_status unknown; one with no map row must say so")
    if any(r not in MAP_ROWS for x in cp for r in x["map_rows"]):
        errs.append("cell-program blueprint names an unknown map row")
    text = json.dumps(bp)
    if re.search(r"\b[ACGT]{12,}\b", text):
        errs.append("a nucleotide-like string of 12+ bases appears; sequences must stay null")
    docp = os.path.join(repo_root or os.path.dirname(os.path.dirname(base)), DOC)
    scan = text + (open(docp).read() if os.path.exists(docp) else "")
    for ph in STALE:
        if ph in scan:
            errs.append(f"stale or contradicted wording present: {ph!r}")
    for need in ("Evo2", "sequence design"):
        if need not in json.dumps(bp["not_done"]):
            errs.append(f"not_done does not mention {need}")
    return errs, notes


def freeze(base=HERE, root=None):
    root = root or os.path.dirname(os.path.dirname(base))
    files = [f"artifacts/genetic-blueprints/{f}" for f in FILES] + [DOC]
    out = {"schema": "frontier.artifact-manifest/1", "files": [{"path": f, "sha256": sha(open(os.path.join(root, f), "rb").read()), "bytes": os.path.getsize(os.path.join(root, f))} for f in files]}
    open(os.path.join(base, "manifest.json"), "w").write(json.dumps(out, indent=2) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache")
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args()
    if a.freeze:
        freeze()
    e, n = check(cache=a.cache)
    for x in n:
        print(x)
    for x in e:
        print("FAIL", x)
    print("PASS" if not e else f"{len(e)} FAILED")
    sys.exit(1 if e else 0)
