"""Submit Problem (or any) drafts from a JSONL file to a Frontier node as PROPOSED records. Reusable; dry-run unless --execute.

    FRONTIER_DSN='host=... port=... dbname=... user=...' python3 scripts/submit_drafts.py drafts.jsonl \\
        --namespace NS --credential-file PATH --expect-actor ACTOR --expect-operator OPERATOR --receipt receipt.json [--execute]

The credential is read from the file inside this process, passed only to Store.submit, and never printed, logged, written to the
receipt, put in an argument or an environment variable. Records are submitted as `proposed`; nothing here reviews or accepts.
The submitting principal is checked against --expect-actor / --expect-operator before anything is planned.

Idempotency. The idempotency key is derived from a hash of the draft content, so a retry of the same content replays the stored
response. Before writing, the existing head of each (namespace, kind, id) is read:
  * no head                              -> submit with no predecessor
  * head's payload equals this content   -> skip (a re-run makes NO new version)
  * head differs and every version of the id was written by this actor from this source_uri, in one linear chain whose head is still
    `proposed`                           -> submit with predecessor = the head's exact version (a revision)
  * anything else (another author, another source_uri, a fork, a branch, a reviewed head, a private/public flip) -> STOP, plan
    nothing, write nothing. Exit code 3.
The plan is made for all records before the first write, and the daily write quota is checked against the number of writes planned.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from hashlib import sha256
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from frontier.models import Draft, canonical, digest, ref  # noqa: E402
from frontier.store import FrontierError, Store  # noqa: E402

EXIT_STOP = 3


class Stop(Exception):
    """Unexpected state: nothing is written."""


def read_credential(path: str) -> str:
    p = Path(path)
    st = p.stat()
    if st.st_mode & 0o077:
        raise Stop(f"credential file {p.name} is readable by group or others; refusing to use it")
    token = p.read_text().strip()
    if not token or "\n" in token:
        raise Stop(f"credential file {p.name} is empty or malformed")
    return token


def content_of(draft: dict) -> dict:
    return {"kind": draft["kind"], "id": draft["id"], "source_uri": draft["source_uri"], "visibility": draft.get("visibility", "public"),
            "payload": draft["payload"]}


def load_drafts(path: str, namespace: str, actor: str, submission: dict) -> list[dict]:
    out, seen = [], set()
    raw = Path(path).read_bytes()
    file_sha = sha256(raw).hexdigest()
    for n, line in enumerate(raw.decode().splitlines(), 1):
        if not line.strip():
            continue
        d = json.loads(line)
        d["namespace"], d["issuer"], d["predecessor"] = namespace, actor, None
        payload = json.loads(canonical(d["payload"]))
        payload.setdefault("original", {})["submission"] = {**submission, "draft_content_sha256": digest(content_of({**d, "payload": d["payload"]}))}
        d["payload"] = payload
        Draft.model_validate(d)
        if (d["kind"], d["id"]) in seen:
            raise Stop(f"line {n}: duplicate {d['kind']}/{d['id']} in the input")
        seen.add((d["kind"], d["id"]))
        out.append(d)
    return out, file_sha


def existing(store: Store, draft: dict) -> dict:
    """Read-only: every version of this id, its head, and its local status."""
    with store.connection() as c:
        versions = c.execute("""SELECT v.version, v.issuer, v.source_uri, v.predecessor, v.visibility, v.envelope, s.status
            FROM record_versions v JOIN local_states s USING(version)
            WHERE v.namespace=%s AND v.kind=%s AND v.record_id=%s ORDER BY v.created_at, v.version""",
                              (draft["namespace"], draft["kind"], draft["id"])).fetchall()
        head = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s",
                         (draft["namespace"], draft["kind"], draft["id"])).fetchone()
        forks = c.execute("SELECT count(*) AS n FROM forks f JOIN record_versions v ON v.version=f.local_version "
                          "WHERE v.namespace=%s AND v.kind=%s AND v.record_id=%s", (draft["namespace"], draft["kind"], draft["id"])).fetchone()["n"]
    return {"versions": versions, "head": head["version"] if head else None, "forks": forks}


def plan_one(draft: dict, state: dict, actor: str) -> dict:
    cid = f"{draft['kind']}/{draft['id']}"
    content_hash = digest(content_of(draft))
    base = {"id": draft["id"], "kind": draft["kind"], "content_sha256": content_hash}
    versions = state["versions"]
    if not versions:
        return {**base, "action": "create", "predecessor": None, "key": f"reg-import:{content_hash[:48]}"}
    if state["forks"]:
        raise Stop(f"{cid}: a fork exists")
    if state["head"] is None:
        raise Stop(f"{cid}: versions exist but there is no head")
    for v in versions:
        if v["issuer"] != actor or v["source_uri"] != draft["source_uri"]:
            raise Stop(f"{cid}: version {v['version'][:12]} was written by {v['issuer']!r} from {v['source_uri']!r}, not this actor and source")
        if v["visibility"] != draft.get("visibility", "public"):
            raise Stop(f"{cid}: visibility differs from an existing version")
    by_pred = {}
    for v in versions:
        by_pred.setdefault(v["predecessor"], []).append(v["version"])
    roots = by_pred.get(None, [])
    if len(roots) != 1 or any(len(x) != 1 for x in by_pred.values()):
        raise Stop(f"{cid}: existing versions do not form one linear chain")
    chain, cur = [roots[0]], roots[0]
    while cur in by_pred:
        cur = by_pred[cur][0]
        chain.append(cur)
    if len(chain) != len(versions) or chain[-1] != state["head"]:
        raise Stop(f"{cid}: the head is not the end of the chain")
    head = next(v for v in versions if v["version"] == state["head"])
    if canonical(head["envelope"]["payload"]) == canonical(draft["payload"]):
        return {**base, "action": "unchanged", "version": head["version"], "predecessor": head["predecessor"]}
    if head["status"] != "proposed":
        raise Stop(f"{cid}: the head is {head['status']!r}, not proposed; refusing to revise a reviewed record")
    return {**base, "action": "revise", "predecessor": head["version"], "key": f"reg-import:{content_hash[:40]}:p{head['version'][:16]}"}


def quota_left(store: Store, operator: str, limit: int) -> int:
    with store.connection() as c:
        n = c.execute("SELECT count(*) AS n FROM write_receipts WHERE operator=%s AND witnessed_at > CURRENT_TIMESTAMP - INTERVAL '1 day'",
                      (operator,)).fetchone()["n"]
    return limit - n


def run(store: Store, token: str, drafts: list[dict], expect_actor: str, expect_operator: str, execute: bool, receipt_path: str | None,
        file_sha: str, extra: dict) -> dict:
    who = store.principal(token)
    if who["actor"] != expect_actor or who["operator"] != expect_operator:
        raise Stop(f"credential belongs to {who['actor']!r}/{who['operator']!r}, expected {expect_actor!r}/{expect_operator!r}")
    if "contributor" not in who["roles"] or store.namespace not in who["namespaces"]:
        raise Stop("principal cannot write this namespace as a contributor")
    plans = []
    for d in drafts:
        d["issuer"] = who["actor"]
        plans.append(plan_one(d, existing(store, d), who["actor"]))
    writes = [p for p in plans if p["action"] in ("create", "revise")]
    left = quota_left(store, who["operator"], who["daily_write_limit"])
    if len(writes) > left:
        raise Stop(f"{len(writes)} writes planned but only {left} remain in the operator's daily quota")
    counts = {a: sum(1 for p in plans if p["action"] == a) for a in ("create", "revise", "unchanged")}
    receipt = {"mode": "execute" if execute else "dry_run", "namespace": store.namespace, "actor": who["actor"], "operator": who["operator"],
               "roles": who["roles"], "independent_reviewer": False, "records_are": "proposed, not accepted", "input_sha256": file_sha,
               "planned": counts, "quota_left_before": left, "daily_write_limit": who["daily_write_limit"], **extra, "records": []}
    if execute:
        for p, d in zip(plans, drafts):
            if p["action"] == "unchanged":
                receipt["records"].append({k: p[k] for k in ("kind", "id", "action", "version", "content_sha256")})
                continue
            try:
                out = store.submit(token, p["key"], {**d, "predecessor": p["predecessor"]})
            except FrontierError as e:  # stop at the first refusal; the partial receipt says exactly what was written
                receipt["stopped"] = {"at": f"{p['kind']}/{p['id']}", "error": getattr(e, "code", type(e).__name__), "message": str(e)[:300]}
                break
            rec = out["record"]
            receipt["records"].append({"kind": rec["kind"], "id": rec["id"], "action": p["action"], "version": rec["version"], "predecessor": rec["predecessor"],
                                       "created_at": rec["created_at"], "content_sha256": p["content_sha256"], "idempotency_key": p["key"],
                                       "local_status": out["local_status"]})
        # Read-back through the public path: no credential, exactly what a reader sees.
        bad = []
        for r in receipt["records"]:
            got = store.get({"namespace": store.namespace, "kind": r["kind"], "id": r["id"], "version": r["version"]})
            if not got["is_head"] or got["local_review"]["status"] != "proposed":
                bad.append(r["id"])
        receipt["read_back"] = {"checked": len(receipt["records"]), "not_head_or_not_proposed": bad}
    else:
        receipt["records"] = [{k: p.get(k) for k in ("kind", "id", "action", "content_sha256", "predecessor", "version")} for p in plans]
    if receipt_path:
        tmp = Path(receipt_path + ".tmp")
        tmp.write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
        os.replace(tmp, receipt_path)
    return receipt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("drafts")
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--schema", default="public")
    ap.add_argument("--credential-file", required=True, help="file holding the bearer token (mode 600); the token is never printed")
    ap.add_argument("--expect-actor", required=True)
    ap.add_argument("--expect-operator", required=True)
    ap.add_argument("--receipt", help="write the JSON receipt here (atomic)")
    ap.add_argument("--register-sha256", help="sha256 of the source register, recorded in each record and the receipt")
    ap.add_argument("--importer", default="scripts/import_register.py")
    ap.add_argument("--execute", action="store_true", help="write; without it nothing is written")
    a = ap.parse_args(argv)
    try:
        token = read_credential(a.credential_file)
        store = Store(os.environ["FRONTIER_DSN"], a.namespace, a.schema)
        who = store.principal(token)
        submission = {"actor": who["actor"], "operator": who["operator"], "role": "proposer; not an independent reviewer",
                      "importer": a.importer, "register_sha256": a.register_sha256}
        drafts, file_sha = load_drafts(a.drafts, a.namespace, who["actor"], submission)
        receipt = run(store, token, drafts, a.expect_actor, a.expect_operator, a.execute, a.receipt, file_sha,
                      {"register_sha256": a.register_sha256, "importer": a.importer})
    except Stop as e:
        print(json.dumps({"ok": False, "stopped": str(e), "written": 0 if not a.execute else "see receipt if any"}))
        return EXIT_STOP
    except FrontierError as e:
        print(json.dumps({"ok": False, "error": getattr(e, "code", type(e).__name__), "message": str(e)[:300]}))
        return 2
    except Exception as e:  # noqa: BLE001 - never print a traceback or a message that could carry a connection string or credential
        print(json.dumps({"ok": False, "error": type(e).__name__}))
        return 2
    summary = {k: receipt[k] for k in ("mode", "namespace", "actor", "operator", "planned", "quota_left_before", "input_sha256")}
    summary.update(written=sum(1 for r in receipt["records"] if r["action"] in ("create", "revise")) if a.execute else 0,
                   read_back=receipt.get("read_back"), stopped=receipt.get("stopped"))
    print(json.dumps(summary))
    return 0 if not receipt.get("stopped") and not (receipt.get("read_back") or {}).get("not_head_or_not_proposed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
