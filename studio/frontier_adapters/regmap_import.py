"""Fish regulatory research map -> bundle + PROPOSED Project members. Writes files only; nothing is submitted, imported or accepted.

    python3 -m frontier_adapters.regmap_import --repo . --source-commit bff3828 --out frontier_adapters/examples/regmap_zebrafish

Every record is Danio rerio and source-only. Members are declared at cellular/developmental scale (the store has no genomic scale) with no causal bridge:
the map's own four coupling ports are all unknown, and nothing here maps DNA to fin shape or to a flying fish.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess

from . import engineering_manifest as em
from . import run_bundles as rb

NS = "delphi-frontier"
SCALE = {"pectoral-fin-field": "developmental", "organism-reference": "developmental"}


def members(chain) -> list[dict]:
    out = []
    for r in chain.records:
        ref = {k: r[k] for k in ("namespace", "kind", "id", "version")}
        if r["kind"] == "Evidence" and r["id"].startswith("run-regmap-evidence-") and "dataset-" not in r["id"]:
            row = r["id"].removeprefix("run-regmap-evidence-")
            out.append({"ref": ref, "role": "context", "subsystem": f"zebrafish regulatory program: {row}", "scale": SCALE.get(row, "cellular"), "relationship": "informs", "causal_bridge": "none_declared",
                        "applicability": "Declared: a source-only statement about Danio rerio and the stated assay and tissue; no flying-fish transfer, no DNA-to-fin bridge.",
                        "rationale": "States what the cited source reports and what is only inferred; the row's missing bridge is recorded in the Evidence."})
        elif r["kind"] == "Problem":
            out.append({"ref": ref, "role": "gap", "subsystem": "zebrafish regulatory data coverage", "scale": "cellular", "relationship": "depends_on", "causal_bridge": "none_declared",
                        "applicability": "Declared: an unexecuted proposal from the research map; it is a question, not a result.",
                        "rationale": "Marks what measured coverage must be established before any association is used."})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    commit = subprocess.check_output(["git", "-C", a.repo, "rev-parse", a.source_commit], text=True).strip()
    c = rb.ALL_CHAINS["regmap"](a.repo, commit, namespace=NS)
    bundle = em.build_bundle([c], limit=rb.AssetChain.max_records)
    prop = {"status": "PROPOSED members for the flying-fish Project; not submitted, not imported, not accepted", "source_commit": commit, "members": members(c),
            "not_claimed": ["no DNA-to-fin bridge", "no flying-fish transfer", "no new sequence design or model inference", "no causal control from markers or inferred GRNs", "no production write"],
            "species_and_assay_limits": "All rows and datasets are Danio rerio (zebrafish). Assays: snRNA-seq and snATAC-seq (GSE261907, adult caudal fin, 0/1/2/4/6 dpa); bulk and sp7-sorted ATAC/RNA/bisulfite (GSE126700-03); enriched fin scRNA (GSE251828); whole embryo/larva scRNA (GSE223922). The pectoral-fin-field row has no accession in the map.",
            "unavailable": ["Source response bytes are held outside the repository; only their sha256 values are carried, not recomputed.", "Coverage 'checked' is recorded for one dataset only (fin-multiome); the native metadata coverage audit has not reported."]}
    os.makedirs(a.out, exist_ok=True)
    for n, o in (("bundle.regmap.frontier-bundle-0.1.json", bundle), ("proposed-members.json", prop)):
        t = json.dumps(o, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        bad = rb.find_secretish(t)
        if bad:
            raise SystemExit(f"secret-like text in {n}: {bad[:3]}")
        open(os.path.join(a.out, n), "w").write(t)
    k = [r["kind"] for r in bundle["records"]]
    print(json.dumps({"records": len(k), "kinds": {x: k.count(x) for x in sorted(set(k))}, "members": len(prop["members"])}))


if __name__ == "__main__":
    main()
