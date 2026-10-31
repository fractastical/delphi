"""Record Delphi snapshots (no quote text) for offline tests.
   PYTHONPATH=. python3 -m frontier_adapters.examples.snapshot_delphi"""
import json
import os

from frontier_adapters import delphi_claim as dc
from frontier_adapters.delphi_mcp import Delphi

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "delphi_snapshots")
IDS = ["turing-ddi", "darwin1859-ch02-04", "wolfram2002-ch02-08", "thompson1917-ch03-05", "fisher-ftns"]
CATALOG = ["levin-2024-anthrobots-08"]          # in delphi_graph only: no nanopub, registry null

if __name__ == "__main__":
    m = Delphi(min_interval=1.0, max_requests=80)
    for cid in IDS:
        snap, tr = dc.collect(m, cid)
        ver = dc.verify_source(snap, tr)
        assert not tr["quote"] or tr["quote"][:30] not in json.dumps(snap), "quote text leaked into snapshot"
        json.dump({"snapshot": snap, "verification": ver}, open(os.path.join(OUT, cid + ".json"), "w"), indent=2, sort_keys=True)
        print(cid, snap["kind"], snap["registry"], "verify:", {k: ver.get(k) for k in ("performed", "sha256_match", "quote_at_locator")})
    for cid in CATALOG:
        ent = next(x for x in dc.graph_entries(m, thinker="Michael Levin") if x["id"] == cid)
        snap = dc.snapshot_from_catalog(ent)
        json.dump({"snapshot": snap, "verification": {"performed": False, "reason": "catalog-only entry"}},
                  open(os.path.join(OUT, cid + ".json"), "w"), indent=2, sort_keys=True)
        print(cid, snap["kind"], snap["registry"])
    print("requests used:", m.requests, "receipts:", len(m.receipts))
