"""Compact human receipt: every job id of ours under results/compute with the provider's own state and timestamps (read live with `nebius ai job get`),
the controller's verdict, and the hash of what came back. Does not infer scientific success from job completion.
  python3 -m frontier_compute.receipt_md results/compute OUT.md"""
import glob, json, subprocess, sys
from pathlib import Path


def prov(jid):
    r = subprocess.run(["nebius", "--profile", "hackathon", "ai", "job", "get", jid, "--format", "json"], capture_output=True, text=True)
    try:
        st = json.loads(r.stdout)["status"]
        return st.get("state"), (st.get("state_details") or {}).get("message"), st.get("started_at"), st.get("finished_at")
    except Exception:
        return "unreadable", None, None, None


def main(root, out):
    rows = []
    for m in sorted(glob.glob(f"{root}/*/manifest-*.json")):
        man = json.load(open(m))
        for o in man["owned"]:
            ev = [e for e in man["events"] if e.get("job") == o["id"] and e["msg"] == "created"]
            res = o.get("result") or {}
            ps, pm, a, b = prov(o["id"])
            tele = list(Path(m).parent.glob(f"results/*/out/telemetry_summary.json"))
            rows.append((o["name"], o["id"], ev[0]["t"] if ev else "-", ps, a, b, o["status"], res.get("rc"), res.get("bytes"), res.get("sha256"), res.get("truncated"), pm, [str(t) for t in tele if o["item"] in str(t) or True][:0]))
    L = ["# Compute receipt (ids and hashes from the controller manifests; provider states read live)", "",
         "Cost: **unavailable** (the event exposes no price or usage receipt to participants; this is not zero). No URLs are recorded.", "",
         "| job name | job id | created (UTC) | provider state | provider start - finish (UTC) | controller status | in-container rc | returned bytes | returned sha256 | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n, i, c, ps, a, b, st, rc, by, sh, tr, pm, _ in rows:
        L.append(f"| `{n}` | `{i}` | {c} | {ps} | {a} - {b} | {st} | {rc} | {by} | `{sh}` | {('truncated; ' if tr else '')}{pm or ''} |")
    L += ["", "A provider state of COMPLETED means the container exited; it does not mean a scientific result exists or passed. See PROTOCOL*.md for the frozen labels."]
    Path(out).write_text("\n".join(L) + "\n")
    print(len(rows), "jobs")


if __name__ == "__main__":
    main(*sys.argv[1:3])
