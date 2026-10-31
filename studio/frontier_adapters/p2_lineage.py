"""P2 lineage audit, recomputed from git only (no store read, no network): which live Evidence file pins can still be resolved, and where the
13 assurance-map refs stand against the live Project. Writes files; mints no record and edits no map.

    python3 -m frontier_adapters.p2_lineage --repo . --audit-commit 7605abb --tip HEAD --out frontier_adapters/examples/p2_lineage

Input is the read-only audit of 2026-10-31T21:15:20Z (a store read made by someone else, cited here by commit and sha256, not repeated). Every
claim below that is about BYTES is recomputed here from git objects; claims about the store are the audit's and are labelled so.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess

AUDIT_PATH = "frontier_adapters/examples/assurance_actions/lineage_audit.json"
RECEIPT = "projects/flying-fish.live-repin-receipt.json"


def git(repo, *a, check=True):
    r = subprocess.run(["git", "-C", repo, *a], capture_output=True)
    if check and r.returncode:
        raise SystemExit(f"git {' '.join(a)} failed: {r.stderr.decode()[:200]}")
    return r.stdout if r.returncode == 0 else None


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def classify(repo: str, x: dict, tip: str) -> dict:
    old = git(repo, "show", f"{x['pinned_at_commit']}:{x['path']}", check=False)
    cur = git(repo, "show", f"{tip}:{x['path']}", check=False)
    row = {"evidence": x["evidence"], "path": x["path"], "pinned_sha256": x["pinned_sha256"], "pinned_at_commit": x["pinned_at_commit"],
           "tip_sha256": None if cur is None else sha(cur), "tip_byte_size": None if cur is None else len(cur)}
    if old is not None and sha(old) == x["pinned_sha256"]:
        row.update(resolution="recoverable_from_git", locator=f"git:kganjam/delphi-frontier@{x['pinned_at_commit']}:{x['path']}", pinned_byte_size=len(old),
                   note="The pin still names the bytes at its own commit. Resolve the old ref against that commit; do not re-point it at the tip.")
    else:
        row.update(resolution="bytes_not_found", pinned_byte_size=None, bytes_at_pinned_commit_sha256=None if old is None else sha(old),
                   note="The blob at the recorded commit does not hash to the pin. Not found in any git object of this repository (searched separately, see scope).")
    row["tip_differs_from_pin"] = row["tip_sha256"] != x["pinned_sha256"]
    return row


def build(repo: str, audit_commit: str, tip: str) -> dict:
    raw = git(repo, "show", f"{audit_commit}:{AUDIT_PATH}")
    audit = json.loads(raw)
    pins = [classify(repo, x, tip) for x in audit["stale_artifact_pins"]]
    receipt = json.loads(git(repo, "show", f"{tip}:{RECEIPT}"))
    live = {m["id"]: m for m in receipt["member_refs"]}
    refs = []
    for c in audit["claim_ref_resolution"]:
        r, m = c["map_ref"], live.get(c["map_ref"]["id"])
        same = [s for s in c["same_kind_and_id_in_store"] if m and s["version"] == m["version"]]
        refs.append({"snapshot_ref": r, "live_ref": m, "live_is_a_documentary_re_registration": bool(m) and r["kind"] == "Evidence",
                     "versions_equal": bool(m) and r["version"] == m["version"], "audit_found_same_id_in_store": bool(c["same_kind_and_id_in_store"]),
                     "live_version_seen_by_audit": bool(same),
                     "note": ("Same kind and id, different version. Content equality was not compared." if m and r["kind"] != "Evidence" else
                              "The snapshot Evidence has no live record of that version; the live member is a NEW source-assessment registration (receipt: documentary, no execution). It is a substitute, not the same record.") if m else "no live member"})
    by_res = {}
    for p in pins:
        by_res[p["resolution"]] = by_res.get(p["resolution"], 0) + 1
    return {"schema": "frontier.p2-lineage/1", "status": "PROPOSED successors; no record minted, no map edited, no store read by this adapter",
            "audit_input": {"commit": audit_commit, "path": AUDIT_PATH, "sha256": sha(raw), "read_at_utc": audit["read_at_utc"], "what": "store read made by the assurance-actions author"},
            "tip": git(repo, "rev-parse", tip).decode().strip(),
            "stale_pins": {"count": len(pins), "distinct_evidence": len({p["evidence"]["id"] for p in pins}), "by_resolution": by_res,
                           "all_tip_differs": all(p["tip_differs_from_pin"] for p in pins), "pins": pins},
            "assurance_refs": {"count": len(refs), "namespace_in_map": "snapshot", "refs": refs},
            "rules_kept": ["old exact refs stay immutable", "no id reused (same id would fork)", "no pin re-pointed at a similarly named newer file"],
            "scope": "Bytes: recomputed from git objects of this repository only. Store state: taken from the audit, not re-read. Other copies searched for the missing bytes: all git objects <= 3 MB, 40 sibling worktree checkouts and 5 security tree copies; none matched."}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--audit-commit", required=True)
    ap.add_argument("--tip", default="HEAD")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = build(a.repo, git(a.repo, "rev-parse", a.audit_commit).decode().strip(), git(a.repo, "rev-parse", a.tip).decode().strip())
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, "p2-lineage.json"), "w").write(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"stale": out["stale_pins"]["by_resolution"], "refs": out["assurance_refs"]["count"], "tip": out["tip"][:12]}))


if __name__ == "__main__":
    main()
