"""The sha256-pinned manifest for the genomics slice, and the JSON Schema that is its contract.

A consumer checks every sha256 against the file it names, validates this file against manifest.schema.json, and applies display_rules.

  PYTHONPATH=. python3 -m connectors.genomics.manifest
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "genomics"

ROLES = {"index.json": ("index", "multi", "all"), "genes.csv": ("table", "Danio rerio", "source_assessment"), "sources.json": ("sources", "multi", "source_assessment"),
         "records/records.json": ("records", "multi", "all"), "assembly_check.json": ("check", "Danio rerio", "source_assessment"), "id_crosscheck.json": ("check", "Danio rerio", "source_assessment"), "lat4a_resolution_v2.json": ("check", "Danio rerio", "source_assessment"), "daane2021_pins.json": ("check", "multi", "all"), "daane2021_chain.json": ("check", "multi", "all"),
         "daane2021_source.json": ("sources", "multi", "source_assessment"), "daane2021_records.json": ("records", "multi", "all"), "lat4a_resolution.json": ("check", "Danio rerio", "source_assessment"), "lat4a_resolution_v3.json": ("check", "Danio rerio", "source_assessment"), "daane2021_supplement_sheets.json": ("check", "multi", "source_assessment"), "daane2021_supplement_records.json": ("records", "multi", "all"),
         "flyingfish_genome_facts.json": ("table", "Hirundichthys speculiger", "sequence_annotation"), "daniocell_correlations.csv": ("table", "Danio rerio", "expression_correlation"),
         "daniocell_tissue_group_thumbnails.csv": ("table", "Danio rerio", "expression_correlation"), "zfin_expression_selected.csv": ("table", "Danio rerio", "expression_correlation"),
         "zfin_phenotype_selected.csv": ("table", "Danio rerio", "genotype_phenotype"), "receipts.json": ("receipts", "multi", "all"), "flyingfish_receipts.json": ("receipts", "Hirundichthys speculiger", "sequence_annotation"),
         "extra_receipts.json": ("receipts", "multi", "all"), "plots/plot_manifest.json": ("plot_manifest", "multi", "all")}
DISPLAY_RULES = {
    "show_species_on_every_row": True,
    "show_evidence_class_label_on_every_row": True,
    "evidence_classes": ["expression_correlation", "genotype_phenotype", "causal_intervention", "sequence_annotation", "source_assessment"],
    "cross_species_statements": "proposed_transfer only: render as a hypothesis, never as evidence, never beside a species-specific result without the label",
    "missing_values": "show as missing (blank or 'not recorded'), never as zero; absence of a curated annotation is 'not curated', not 'not expressed'",
    "unresolved_identifiers": ["lat4a"],
    "unresolved_rule": "the paper prints no zebrafish accession for lat4a: show 'inferred: slc43a2a (supported by the supplement's naming and an Ensembl ortholog; not an author-stated zebrafish accession)' and never present slc43a2a as the paper's stated identifier; link to lat4a_resolution_v3.json",
    "show_per_plot": ["title", "limits caption inside the figure", "input hashes from plots/plot_manifest.json"],
    "must_not_say": ["causal or interaction evidence was gathered here", "Daniocell correlation means regulation", "best-hit SwissProt similarity is orthology", "any flying-fish structure is annotated beyond the mirrorwing assembly",
                     "NCBI Gene coordinates are GRCz11", "the paper's lat4a is confirmed to be slc43a2a by the authors or by a residue check (it is supported by the supplement's medaka naming and Ensembl orthology; the authors print no zebrafish accession)", "the zebrafish lat4a x kcnh2a phenocopy shows flight, or that flying fishes use these genes (the genomic data are correlational)", "genomes available is a proven mutation map"],
    "licence_rule": "a source with license null has no stated licence in the bytes read; link to it, do not host its content; CC BY items (mirrorwing paper, figshare 14600634) are redistributable with attribution",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    files = []
    for p in sorted(OUT.rglob("*")):
        rel = p.relative_to(OUT).as_posix()
        if not p.is_file() or rel in ("manifest.json", "manifest.schema.json"):
            continue
        if rel in ROLES:
            role, species, cls = ROLES[rel]
        elif rel.startswith("plots/") and rel.endswith(".svg"):
            role, species, cls = "plot", ("Hirundichthys speculiger" if "flyingfish" in rel else "Danio rerio"), ("sequence_annotation" if "flyingfish" in rel else "expression_correlation")
        elif rel.startswith("artifacts/"):
            role, species, cls = "raw_artifact", ("Hirundichthys speculiger" if ("flyingfish" in rel or "PMC8294118" in rel or "figshare" in rel or "ncbi_assembly" in rel or "bioproject" in rel) else "Danio rerio" if ("zfin" in rel or "daniocell" in rel or "ucsc" in rel or "ncbi_gene" in rel or "uniprot" in rel or "zebrahub" in rel or "slc43a2" in rel) else "multi"), "source_assessment"
        else:
            continue
        files.append({"path": f"data/genomics/{rel}", "sha256": sha(p), "bytes": p.stat().st_size, "role": role, "species": species, "evidence_class": cls})
    idx = json.loads((OUT / "index.json").read_text())
    recs = json.loads((OUT / "records" / "records.json").read_text())["records"]
    drecs = json.loads((OUT / "daane2021_records.json").read_text())["records"]
    srecs = json.loads((OUT / "daane2021_supplement_records.json").read_text())["records"]
    man = {"manifest_schema": "genomics-manifest-0.3 (connector-local)", "supersedes": "genomics-manifest-0.2: additive (supplement Data S1 read for lat4a, 5 new records, corrected sheet descriptions); the lat4a display rule and `inferred` wording change from 'probable, not confirmed' to 'supported' and say what is still not established. 0.2 and every earlier file stay as the record of the earlier state.", "retrieved": idx["retrieved"], "namespace": "node-a (corpus remaps)", "status": "proposed; nothing submitted, reviewed or accepted",
           "counts": {"genes": len(idx["genes"]), "records": {k: sum(1 for r in recs if r["kind"] == k) for k in ("Claim", "Evidence", "Problem")}, "records_daane2021": {k: sum(1 for r in drecs if r["kind"] == k) for k in ("Claim", "Evidence", "Problem")}, "records_supplement": {k: sum(1 for r in srecs if r["kind"] == k) for k in ("Claim", "Evidence", "Problem")}, "sources": len(json.loads((OUT / "sources.json").read_text())["cards"]),
                      "files": len(files), "plots": sum(1 for f in files if f["role"] == "plot")},
           "unresolved": ["lat4a zebrafish accession: neither the paper text nor Data S1 prints one (they use medaka Ensembl ids); the residue check is still inconclusive for slc43a2a (see lat4a_resolution_v3.json)"], "inferred": ["lat4a = slc43a2a (ZDB-GENE-040426-964, ENSDARG00000036848), SUPPORTED by the supplement's naming (Data S1G/H/J) and an Ensembl one-to-one ortholog; not an author-stated zebrafish accession; see lat4a_resolution_v3.json"],
           "not_fetched": ["Zebrahub gene-level data", "DANIO-CODE regulatory tracks", "Daniocell 2023 full text (not open access)", "Daane 2021 supplement: Tables S1-S3 and Figures S1-S4 (Data S1 rows naming lat4a, lat4b and slc43a2b in sheets G, H, I, J were read here; the rest of Data S1 was not; Data S1A is in the fish-controls branch)", "any causal_intervention data", "flyingfish assembly sequence (311 MB)"],
           "display_rules": DISPLAY_RULES, "files": files}
    (OUT / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema", "$id": "urn:frontier:connector:genomics:manifest-0.1", "title": "genomics-manifest-0.1 (connector-local contract; not a root schema)",
        "type": "object", "additionalProperties": False, "required": ["manifest_schema", "retrieved", "namespace", "status", "counts", "unresolved", "inferred", "not_fetched", "display_rules", "files"],
        "$defs": {"sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"}},
        "properties": {
            "manifest_schema": {"const": "genomics-manifest-0.3 (connector-local)"}, "retrieved": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"}, "namespace": {"type": "string"}, "status": {"type": "string", "pattern": "^proposed"},
            "counts": {"type": "object", "required": ["genes", "records", "sources", "files", "plots"], "properties": {"genes": {"type": "integer", "minimum": 1}, "records": {"type": "object", "required": ["Claim", "Evidence", "Problem"]},
                                                                                                               "sources": {"type": "integer"}, "files": {"type": "integer"}, "plots": {"type": "integer", "minimum": 1}}},
            "unresolved": {"type": "array", "items": {"type": "string"}, "contains": {"pattern": "^lat4a"}}, "inferred": {"type": "array", "items": {"type": "string"}, "minItems": 1, "contains": {"pattern": "SUPPORTED.*not an author-stated"}}, "supersedes": {"type": "string"}, "not_fetched": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "display_rules": {"type": "object", "required": ["show_species_on_every_row", "show_evidence_class_label_on_every_row", "cross_species_statements", "missing_values", "unresolved_identifiers", "must_not_say", "licence_rule"],
                              "properties": {"show_species_on_every_row": {"const": True}, "show_evidence_class_label_on_every_row": {"const": True}, "unresolved_identifiers": {"type": "array", "contains": {"const": "lat4a"}},
                                             "must_not_say": {"type": "array", "minItems": 5}}},
            "files": {"type": "array", "minItems": 10, "items": {"type": "object", "additionalProperties": False, "required": ["path", "sha256", "bytes", "role", "species", "evidence_class"],
                                                                 "properties": {"path": {"type": "string", "pattern": "^data/genomics/[A-Za-z0-9_./-]+$"}, "sha256": {"$ref": "#/$defs/sha256"}, "bytes": {"type": "integer", "minimum": 1},
                                                                                "role": {"enum": ["index", "table", "plot", "plot_manifest", "records", "sources", "receipts", "check", "raw_artifact"]},
                                                                                "species": {"enum": ["Danio rerio", "Hirundichthys speculiger", "multi"]},
                                                                                "evidence_class": {"enum": ["expression_correlation", "genotype_phenotype", "causal_intervention", "sequence_annotation", "source_assessment", "all"]}}}}}}
    (OUT / "manifest.schema.json").write_text(json.dumps(schema, indent=1, sort_keys=True))
    print(len(files), "files pinned;", man["counts"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
