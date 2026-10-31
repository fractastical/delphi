"""Collect receipts for every returned job bundle under results/compute/: ids from the controller manifests only (nothing invented, no URLs).
  python3 -m frontier_compute.receipts results/compute OUT.json"""
import glob, hashlib, json, subprocess, sys
from pathlib import Path


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(root, out):
    recs = []
    for m in sorted(glob.glob(f"{root}/*/manifest-*.json")):
        man = json.load(open(m))
        d = Path(m).parent
        for o in man["owned"]:
            res = o.get("result") or {}
            files = {str(p.relative_to(d)): sha(p) for p in sorted(d.rglob("*")) if p.is_file() and "_inject" not in p.parts and p.name != Path(m).name and f"-{o['item']}" in str(p)}
            recs.append({"job_id": o["id"], "job_name": o["name"], "item": o["item"], "run_tag": man["run_tag"], "controller_status": o["status"],
                         "job_state": res.get("job_state"), "inner_rc": res.get("rc"), "timed_out": res.get("timed_out"), "inner_wall_s": res.get("wall_s"),
                         "returned_bundle_sha256": res.get("sha256"), "returned_bundle_bytes": res.get("bytes"),
                         "controller_manifest": m, "controller_manifest_sha256": sha(m),
                         "events": [e for e in man["events"] if e.get("job") == o["id"]], "files_sha256": files})
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    json.dump({"repo_commit_at_collection": head, "n_jobs": len(recs), "jobs": recs, "price": "unavailable: the event exposes no price or usage receipt to participants (not zero)",
               "note": "ids are Nebius job ids copied from the controller manifest; no URLs recorded (none resolvable by others)."},
              open(out, "w"), indent=1, sort_keys=True, allow_nan=False)
    print(len(recs), "jobs")


main(*sys.argv[1:3])
