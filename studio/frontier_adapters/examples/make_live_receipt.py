"""Assemble the machine-readable receipt and the site chain ids from the artifacts of a live import run.
   PYTHONPATH=. python3 -m frontier_adapters.examples.make_live_receipt <import dir> <out dir> <dsn> <namespace>
Reads only: the plans, the import responses, the verification reads and the recorded pre-import counts. No credential is read."""
import json
import os
import sys

from frontier_adapters import import_cli as ic

imp, out, dsn, ns = sys.argv[1:5]
load = lambda p: json.load(open(os.path.join(imp, p)))
plans = {"chain": load("chain/plan.json"), "claims": load("claims/plan.json")}
responses = [[json.loads(l) for l in open(os.path.join(imp, "receipt-import.jsonl"))]]
verifies = {"chain": load("verify-chain.json"), "claims": load("verify-claims.json")}
store = ic._store(dsn, ns)
with store.connection() as c:
    cross = {}
    for r in c.execute("SELECT DISTINCT a.record_id, a.namespace other FROM heads a JOIN heads b ON a.kind=b.kind AND a.record_id=b.record_id AND a.namespace<>b.namespace "
                       "WHERE a.kind='Claim' AND b.namespace='node-a' AND a.namespace<>'node-a' ORDER BY 1").fetchall():
        cross.setdefault(r["record_id"], []).append(r["other"])
recs = ic.records_from_file(os.path.join(os.path.dirname(__file__), "nca_chain", "records.json"))
chain = json.load(open(os.path.join(os.path.dirname(__file__), "nca_chain", "chain.json")))
rep = ic.make_receipt(
    plans=plans, import_receipts=responses, verifies=verifies,
    counts_before={"heads": {"delphi-frontier/Claim": 21, "delphi-frontier/Event": 28, "delphi-frontier/Problem": 7}, "versions": 56,
                   "status": {"proposed": 56}, "forks": 0, "events": 28, "write_receipts_24h": 28},
    counts_before_note="copied from the preflight output printed immediately before the first write (19:0xZ); not re-read from the store afterwards",
    code={"repo": "kganjam/delphi-frontier", "branch": "work/corpus-adapters", "commit": os.environ.get("IMPORT_CODE_COMMIT"),
          "root_branch_merged": "origin/codex/frontier-demo-20261031 @ a3e0fd8", "cli": "python -m frontier_adapters.import_cli"},
    principal={"actor": "corpus-importer", "operator": "local-fleet", "roles": ["contributor", "coordinator"], "namespaces": ["delphi-frontier"], "daily_write_limit": 1000},
    store={"namespace": ns, "connection": "local unix socket, port 5471 (path omitted)", "database": "frontier"},
    excluded={"left_to_the_chain_exact_versions": ["turing-ddi", "turing-wavelength"],
              "catalog_only_unpublished_not_imported_yet": 310,
              "meaning": "node-a/Claim has 880 heads = 878 from the bulk plan + the chain's 2 exact claims"},
    cross_namespace=cross,
    notes=["Source namespace 'node-a' and every record's own pins were preserved; nothing was aliased or rewritten.",
           "The 21 math Delphi claims also exist as local proposals in namespace delphi-frontier (issuer codex-03). Heads are keyed by namespace, so nothing is "
           "shadowed and no fork was recorded, but the same Delphi claim appears twice. The Evidence pins the node-a versions only.",
           "10 writes used (one per bundle) of 1000/day; the identical re-run of the 9 claim bundles changed no count (idempotent).",
           "No record carries origin; Delphi's own verification labels remain upstream assertions inside prior_review."])
os.makedirs(out, exist_ok=True)
for name, obj in (("import-receipt.json", rep), ("site-chain-ids.json", ic.site_ids(recs, chain))):
    tmp = os.path.join(out, name + ".tmp")
    with open(tmp, "w") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, default=str)
    os.replace(tmp, os.path.join(out, name))
print(json.dumps({"inserted_total": rep["inserted_total"], "forks": rep["forks_recorded"], "after_heads": rep["counts_after"]["heads"],
                  "cross_namespace_ids": len(cross), "receipt_sha256": rep["receipt_sha256"][:16]}, indent=1))
