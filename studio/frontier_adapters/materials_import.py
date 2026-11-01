"""Manufacturer material cards -> bundle + PROPOSED Project members. Writes files only; nothing is submitted, imported or accepted.

    python3 -m frontier_adapters.materials_import --repo . --source-commit f1796ec --out frontier_adapters/examples/materials_formlabs

The launchable-glider Project subsystem is not a persisted record this adapter can see (specs/SPEC-010 describes it); members are proposed as data for the
Project owner to place, with a `scale` and `relationship` that declare applicability and never a causal bridge.
"""
from __future__ import annotations

import argparse
import json
import os

from . import engineering_manifest as em
from . import run_bundles as rb

NS = "delphi-frontier"


def members(chain) -> list[dict]:
    out = []
    for r in chain.records:
        if r["kind"] != "Evidence":
            continue
        tough = r["payload"]["relation"] == "qualifies"
        out.append({"ref": {k: r[k] for k in ("namespace", "kind", "id", "version")}, "role": "context", "subsystem": "launchable glider: print material",
                    "scale": "organism", "relationship": "informs", "causal_bridge": "none_declared",
                    "applicability": ("Declared: Form 4 coupon data for Tough 1500 V2; applicability to the user's Form Studio 1 process is NOT established." if tough else
                                      "Declared: manufacturer-reported coupon properties of a printed polymer under the stated Form Studio 1 default post-cure; not a Frontier measurement and not a fin or assembled-print result."),
                    "rationale": "Source values a mass and bending estimate for the printed glider may cite; liquid density is excluded from part mass."})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    commit = em._git_rev(a.repo, a.source_commit) if hasattr(em, "_git_rev") else __import__("subprocess").check_output(["git", "-C", a.repo, "rev-parse", a.source_commit], text=True).strip()
    c = rb.ALL_CHAINS["materials"](a.repo, commit, namespace=NS)
    bundle = em.build_bundle([c], limit=rb.AssetChain.max_records)
    prop = {"status": "PROPOSED members for the launchable-glider subsystem; not submitted, not imported, not accepted", "source_commit": commit,
            "members": members(c), "not_claimed": ["no empirical Frontier measurement", "no standalone full-HTML import", "no acceptance or review", "no survival, flight or whole-fish calibration claim"],
            "unavailable": ["The three manufacturer HTML byte sets are retained outside the repository; their recorded sha256 values could not be recomputed here.", "Tough 1500 V2 has no source sha256 at all."]}
    os.makedirs(a.out, exist_ok=True)
    for n, o in (("bundle.materials.frontier-bundle-0.1.json", bundle), ("proposed-members.json", prop)):
        t = json.dumps(o, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
        if rb.find_secretish(t):
            raise SystemExit(f"secret-like text in {n}: {rb.find_secretish(t)[:3]}")
        open(os.path.join(a.out, n), "w").write(t)
    print(json.dumps({"records": len(bundle["records"]), "members": len(prop["members"])}))


if __name__ == "__main__":
    main()
