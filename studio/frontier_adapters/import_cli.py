"""Bounded, deterministic import of FROZEN records into a Frontier store, only through `Store.import_bundle`.

  python -m frontier_adapters.import_cli build     --records R.json [--drafts D.jsonl ...] --out DIR [--exclude-id ID ...]
  python -m frontier_adapters.import_cli preflight --plan DIR/plan.json --dsn ... --namespace NS --token-file F
  python -m frontier_adapters.import_cli import    --plan DIR/plan.json --dsn ... --namespace NS --token-file F --receipt R.jsonl [--execute]
  python -m frontier_adapters.import_cli verify    --plan DIR/plan.json --dsn ... --namespace NS --receipt-out R.json
  python -m frontier_adapters.import_cli submit-local --input DRAFTS --dsn ... --namespace NS --token-file F --expect-actor A --expect-operator O --receipt-out R.json [--execute]

Properties (each has a test against a scratch PostgreSQL):
  * No network, no model call. Inputs are frozen files; outputs are bundles of <=100 records built exactly as
    `Store.export_bundle` builds them (same body, same digest rule), so `import_bundle` accepts them unchanged.
  * Records keep their own namespace/kind/id/version/issuer: nothing is rewritten, aliased or re-issued. Imports land as
    `imported_unreviewed`; an imported Action stays `proposed` (an import never shows an action ran).
  * Deterministic: records are ordered and chunked by a stable rule; the idempotency key is derived from the bundle digest,
    so re-running returns the stored response and writes nothing. `import` is a DRY RUN unless `--execute` is given.
  * No duplicate heads: `build` refuses a repeated (namespace, kind, id); `preflight` reports any record whose id already has
    a different head (which `import_bundle` would record as a FORK, leaving the head unchanged) so it is chosen, not stumbled into.
  * The credential is read inside the process from a file that must be mode 0600/0400, owned by the caller and outside any git
    work tree. It is never printed, logged, put in a receipt or included in an error message.
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone

from .common import sha_obj

KIND_ORDER = {"Claim": 0, "Problem": 0, "Action": 1, "Evidence": 2}
TRUST = "Digest proves integrity only; reviews require receiving-node policy."


class ImportRefused(RuntimeError):
    pass


# ---------------------------------------------------------------- inputs
def _jsonl(path):
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _created_at(draft: dict) -> str:
    try:
        return draft["payload"]["prior_review"]["adapter"]["retrieved_at"]
    except KeyError as e:
        raise ImportRefused(f"draft {draft.get('id')!r} has no payload.prior_review.adapter.retrieved_at to pin created_at: {e}") from e


def records_from_drafts(paths, *, exclude_ids=()) -> list[dict]:
    """Frozen Draft dicts -> full Records. `created_at` is pinned to each draft's own retrieval time, so the same input
    always yields the same version digests."""
    from frontier.models import Draft, make_record
    out, skipped = [], set()
    for p in paths:
        for d in _jsonl(p):
            if d["id"] in exclude_ids:
                skipped.add(d["id"])
                continue
            out.append(make_record(Draft.model_validate(d), created_at=_created_at(d)))
    return out


def records_from_file(path) -> list[dict]:
    """Already-made Records (e.g. examples/nca_chain/records.json). Validated, never rebuilt: versions stay exact."""
    from frontier.models import Record
    with open(path) as fh:
        data = json.load(fh)
    if isinstance(data, dict) and isinstance(data.get("records"), list):      # e.g. a connector mapping file {"records": [...], ...}
        data = data["records"]
    if not isinstance(data, list):
        raise ImportRefused(f"{path}: expected a JSON list of Records or an object with a 'records' list")
    return [Record.model_validate(r).model_dump() for r in data]


# ---------------------------------------------------------------- bundles
def order(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda r: (KIND_ORDER.get(r["kind"], 9), r["namespace"], r["id"]))


def check_unique(records: list[dict]):
    seen = {}
    for r in records:
        k = (r["namespace"], r["kind"], r["id"])
        if k in seen and seen[k] != r["version"]:
            raise ImportRefused(f"two different versions for head {k}: would fork or shadow; choose one deliberately")
        seen[k] = r["version"]


def make_bundles(records: list[dict], exporting_node: str, *, max_records: int = 100, keep_input_order: bool = False) -> list[dict]:
    from frontier.models import MAX_BUNDLE_BYTES, MAX_BUNDLE_RECORDS, POLICY, canonical, digest
    if not 1 <= max_records <= MAX_BUNDLE_RECORDS:
        raise ImportRefused(f"max_records must be 1..{MAX_BUNDLE_RECORDS}")
    recs = list(records) if keep_input_order else order(records)
    check_unique(recs)
    unique = list({r["version"]: r for r in recs}.values())
    bundles = []
    for i in range(0, len(unique), max_records):
        body = {"schema_version": "frontier-bundle-0.1", "exporting_node": exporting_node, "records": unique[i:i + max_records],
                "review_claims": [], "policy_version": POLICY, "trust": TRUST}
        b = {**body, "bundle_sha256": digest(body)}
        if len(canonical(b).encode()) > MAX_BUNDLE_BYTES:
            raise ImportRefused(f"bundle {i // max_records} exceeds the byte limit; lower max_records")
        bundles.append(b)
    return bundles


def key_for(bundle: dict) -> str:
    """Deterministic idempotency key: one key per exact bundle."""
    return "corpus-import-" + bundle["bundle_sha256"][:40]


def ref_of(r: dict) -> dict:
    return {k: r[k] for k in ("namespace", "kind", "id", "version")}


def write_plan(bundles: list[dict], out_dir: str, *, source: dict) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for n, b in enumerate(bundles, 1):
        name = f"bundle-{n:03d}-{b['bundle_sha256'][:12]}.json"
        with open(os.path.join(out_dir, name), "w") as fh:
            json.dump(b, fh, sort_keys=True)
        files.append({"file": name, "bundle_sha256": b["bundle_sha256"], "idempotency_key": key_for(b), "records": len(b["records"]),
                      "refs": [ref_of(r) for r in b["records"]]})
    plan = {"schema": "frontier-import-plan-0.1", "source": source, "bundles": files,
            "total_records": sum(f["records"] for f in files),
            "by_namespace_kind": _count([r for b in bundles for r in b["records"]])}
    plan["plan_sha256"] = sha_obj({k: v for k, v in plan.items() if k != "plan_sha256"})
    with open(os.path.join(out_dir, "plan.json"), "w") as fh:
        json.dump(plan, fh, indent=1, sort_keys=True)
    return plan


def _count(records) -> dict:
    out = {}
    for r in records:
        k = f"{r['namespace']}/{r['kind']}"
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def load_bundles(plan_path: str) -> tuple[dict, list[dict]]:
    with open(plan_path) as fh:
        plan = json.load(fh)
    base = os.path.dirname(os.path.abspath(plan_path))
    bundles = []
    for f in plan["bundles"]:
        with open(os.path.join(base, f["file"])) as fh:
            b = json.load(fh)
        if b["bundle_sha256"] != f["bundle_sha256"]:
            raise ImportRefused(f"{f['file']}: bundle changed since the plan was written")
        bundles.append(b)
    return plan, bundles


# ---------------------------------------------------------------- credential
def read_token(path: str) -> str:
    """Read a credential inside the process. Never echoed; error messages carry the path and the reason only."""
    ap = os.path.abspath(path)
    st = os.stat(ap)
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
        raise ImportRefused(f"credential file {ap} must be owned by you with mode 0600 or 0400")
    top = subprocess.run(["git", "-C", os.path.dirname(ap), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode == 0:
        raise ImportRefused(f"credential file {ap} is inside a git work tree ({top.stdout.strip()}); refusing to read it from there")
    with open(ap) as fh:
        tok = fh.read().strip()
    if not 24 <= len(tok) <= 512:
        raise ImportRefused("credential file does not hold a token of the expected size")
    return tok


# ---------------------------------------------------------------- store-side operations
def _store(dsn, namespace, schema="public"):
    from frontier.store import Store
    return Store(dsn, namespace, schema)


def counts(store) -> dict:
    with store.connection() as c:
        heads = {f"{r['namespace']}/{r['kind']}": r["n"] for r in c.execute("SELECT namespace,kind,count(*) n FROM heads GROUP BY 1,2 ORDER BY 1,2").fetchall()}
        status = {r["status"]: r["n"] for r in c.execute("SELECT status,count(*) n FROM local_states GROUP BY 1 ORDER BY 1").fetchall()}
        forks = c.execute("SELECT count(*) n FROM forks").fetchone()["n"]
        events = c.execute("SELECT count(*) n FROM events").fetchone()["n"]
        wr = c.execute("SELECT count(*) n FROM write_receipts WHERE witnessed_at > CURRENT_TIMESTAMP - INTERVAL '1 day'").fetchone()["n"]
        versions = c.execute("SELECT count(*) n FROM record_versions").fetchone()["n"]
    return {"heads": heads, "versions": versions, "status": status, "forks": forks, "events": events, "write_receipts_24h": wr}



# ---------------------------------------------------------------- graph gates (import_bundle validates NO references; these do)
def _present(c, r) -> bool:
    return bool(c.execute("SELECT 1 FROM record_versions WHERE namespace=%s AND kind=%s AND record_id=%s AND version=%s",
                          (r["namespace"], r["kind"], r["id"], r["version"])).fetchone())


def graph_gates(records: list[dict], store=None, *, allow_dangling_predecessor=()) -> dict:
    """Closure and lineage checks over a set of records about to be imported.

    `Store.import_bundle` checks digests but no references, so an inconsistent graph would be stored as written. These checks
    refuse that (refused), flag what needs a human (warnings) and tabulate typed lineage per Evidence (lineage). A reference is
    satisfied by the set itself or, with a store, by the exact version already in the store.
    Nothing here reviews anything: an imported Assessment that claims a decision is REFUSED, because an import must not
    manufacture independent review.
    """
    by_v = {r["version"]: r for r in records}
    refused, warnings, lineage = [], [], []
    c_ctx = store.connection() if store is not None else None
    c = c_ctx.__enter__() if c_ctx else None
    try:
        def exists(ref):
            r = by_v.get(ref["version"])
            if r is not None and (r["namespace"], r["kind"], r["id"]) == (ref["namespace"], ref["kind"], ref["id"]):
                return r
            if c is not None and _present(c, ref):
                row = c.execute("SELECT envelope FROM record_versions WHERE version=%s", (ref["version"],)).fetchone()
                return row["envelope"]
            return None

        for r in records:
            tag = f"{r['namespace']}/{r['kind']}/{r['id']}"
            p = r["payload"]
            if r["kind"] == "Assessment" and (p.get("decision") != "unreviewed" or any(d.get("status") in ("passed", "failed") for d in p.get("dimensions", {}).values())):
                refused.append({"record": tag, "why": "an imported Assessment claims a decision or a dimension result; imports must not manufacture review"})
            if r["predecessor"] and exists({"namespace": r["namespace"], "kind": r["kind"], "id": r["id"], "version": r["predecessor"]}) is None \
                    and r["id"] not in allow_dangling_predecessor:
                refused.append({"record": tag, "why": "predecessor version is in neither the set nor the store (dangling); allow it explicitly with --allow-dangling-predecessor ID",
                                "predecessor": r["predecessor"]})
            elif r["predecessor"] and r["id"] in allow_dangling_predecessor and exists({"namespace": r["namespace"], "kind": r["kind"], "id": r["id"], "version": r["predecessor"]}) is None:
                warnings.append({"record": tag, "why": "dangling predecessor allowed explicitly; the earlier version is not in the store", "predecessor": r["predecessor"]})
            if r["kind"] == "Evidence":
                tgt = exists(p["target"])
                if tgt is None:
                    refused.append({"record": tag, "why": "Evidence target is in neither the set nor the store", "target": p["target"]["id"]})
                act = None
                if p.get("produced_by"):
                    act = exists(p["produced_by"])
                    if act is None:
                        refused.append({"record": tag, "why": "produced_by Action is in neither the set nor the store", "action": p["produced_by"]["id"]})
                    elif act["payload"].get("target") != p["target"]:
                        refused.append({"record": tag, "why": "produced_by Action and Evidence do not pin the same target (the store enforces this on submit)"})
                    if not any(a["role"] == "output" for a in p.get("artifacts", [])):
                        warnings.append({"record": tag, "why": "Evidence has produced_by but no typed artifact with role 'output'"})
                if p["evidence_kind"] == "observed":
                    warnings.append({"record": tag, "why": "evidence_kind 'observed': a human must confirm something was actually observed"})
                lineage.append({"evidence": tag, "kind": p["evidence_kind"], "relation": p.get("relation", "unspecified"),
                                "target": f"{p['target']['namespace']}/{p['target']['kind']}/{p['target']['id']}",
                                "produced_by": None if not p.get("produced_by") else p["produced_by"]["id"],
                                "action_inputs": [i["id"] for i in (act or {}).get("payload", {}).get("inputs", [])],
                                "artifact_roles": sorted({a["role"] for a in p.get("artifacts", [])}), "artifacts": len(p.get("artifacts", []))})
            if r["kind"] == "Action":
                if exists(p["target"]) is None:
                    refused.append({"record": tag, "why": "Action target is in neither the set nor the store"})
                for i in p.get("inputs", []):
                    if exists(i) is None:
                        refused.append({"record": tag, "why": "Action input is in neither the set nor the store", "input": i["id"]})
    finally:
        if c_ctx:
            c_ctx.__exit__(None, None, None)
    per_action = {}
    for l in lineage:
        if l["produced_by"]:
            per_action.setdefault(l["produced_by"], []).append(l["evidence"])
    shared = {a: e for a, e in per_action.items() if len(e) > 1}
    if shared:
        warnings.append({"why": "several Evidence records share one producing Action: one execution, not several", "actions": shared})
    return {"refused": refused, "warnings": warnings, "lineage": lineage, "ok": not refused}


def preflight(store, token, bundles, *, allow_dangling_predecessor=()) -> dict:
    p = store.principal(token)
    recs = [r for b in bundles for r in b["records"]]
    existing_versions, would_fork, new = [], [], 0
    with store.connection() as c:
        for r in recs:
            if c.execute("SELECT 1 FROM record_versions WHERE version=%s", (r["version"],)).fetchone():
                existing_versions.append(ref_of(r))
                continue
            head = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s", (r["namespace"], r["kind"], r["id"])).fetchone()
            if head:
                would_fork.append({"ref": ref_of(r), "current_head": head["version"]})
            else:
                new += 1
        other_ns = {}
        for r in recs:
            for row in c.execute("SELECT namespace FROM heads WHERE kind=%s AND record_id=%s AND namespace<>%s", (r["kind"], r["id"], r["namespace"])).fetchall():
                other_ns.setdefault(f"{r['kind']}/{r['id']}", set()).add(row["namespace"])
    quota_left = p["daily_write_limit"] - counts(store)["write_receipts_24h"]
    gates = graph_gates(recs, store, allow_dangling_predecessor=tuple(allow_dangling_predecessor))
    return {"gates": gates, "principal": {k: p[k] for k in ("actor", "operator", "roles", "namespaces", "daily_write_limit")},
            "can_import": "coordinator" in p["roles"] and store.namespace in p["namespaces"] and gates["ok"],
            "records": len(recs), "new_heads": new, "already_present_versions": len(existing_versions),
            "would_fork": would_fork, "same_id_in_other_namespaces": {k: sorted(v) for k, v in sorted(other_ns.items())},
            "writes_needed": len(bundles), "quota_left": quota_left, "counts_before": counts(store)}


def run_import(store, token, bundles, *, execute: bool, receipt_path: str | None, stop_on_fork: bool = True) -> list[dict]:
    out = []
    for b in bundles:
        entry = {"bundle_sha256": b["bundle_sha256"], "idempotency_key": key_for(b), "records": len(b["records"]), "executed": execute,
                 "at": datetime.now(timezone.utc).isoformat()}
        if execute:
            try:
                resp = store.import_bundle(token, key_for(b), b)
            except Exception as exc:                                # record the stop, never retry with a different key
                entry.update(error=f"{type(exc).__name__}: {str(exc)[:300]}")
                out.append(entry)
                _append(receipt_path, entry)
                break
            entry.update(inserted=len(resp["inserted"]), forks=resp["forks"], imported_reviews_are_local_authority=resp["imported_reviews_are_local_authority"])
            if resp["forks"] and stop_on_fork:
                entry["stopped"] = "fork recorded; stopping so it can be examined"
                out.append(entry)
                _append(receipt_path, entry)
                break
        out.append(entry)
        _append(receipt_path, entry)
    return out


def _append(path, obj):
    if path:
        with open(path, "a") as fh:
            fh.write(json.dumps(obj, sort_keys=True) + "\n")


def verify(store, bundles, *, expect_status="imported_unreviewed", token=None) -> dict:
    """Read every record back by its exact ref (public read, no credential unless given) and check status/head."""
    bad, ok, statuses = [], 0, {}
    for b in bundles:
        for r in b["records"]:
            try:
                got = store.get(ref_of(r), token)
            except Exception as exc:
                bad.append({"ref": ref_of(r), "problem": f"{type(exc).__name__}: {str(exc)[:120]}"})
                continue
            st = (got["local_review"] or {}).get("status")
            statuses[st] = statuses.get(st, 0) + 1
            problems = []
            if got["record"]["version"] != r["version"]: problems.append("version differs")
            if st != expect_status: problems.append(f"status {st!r}")
            if not got["is_head"]: problems.append("not the head")
            if r["kind"] == "Action" and (got["action"] or {}).get("state") != "proposed": problems.append("action not in 'proposed'")
            if problems:
                bad.append({"ref": ref_of(r), "problem": "; ".join(problems)})
            else:
                ok += 1
    return {"verified_ok": ok, "problems": bad, "status_counts": statuses, "counts_now": counts(store)}



# ---------------------------------------------------------------- local proposals (re-issue into the store's namespace as the caller)
import functools


@functools.lru_cache(maxsize=1)
def _root_submit():
    """Root's `scripts/submit_drafts.py`, loaded by RELATIVE path so its planning, quota, head/predecessor and read-back logic is reused unchanged.
    Cached: every call would otherwise create a new `Stop` class and `except mod.Stop` would stop matching."""
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "scripts" / "submit_drafts.py"
    spec = importlib.util.spec_from_file_location("frontier_root_submit_drafts", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _refs_in(o, found=None):
    found = [] if found is None else found
    if isinstance(o, dict):
        if {"namespace", "kind", "id", "version"} <= set(o):
            found.append(o)
        for v in o.values():
            _refs_in(v, found)
    elif isinstance(o, list):
        for v in o:
            _refs_in(v, found)
    return found


def load_local_drafts(path: str, namespace: str, actor: str, submission: dict, *, allow_content_available=()) -> tuple[list[dict], str, dict]:
    """Draft dicts (JSONL, or a JSON object with a `drafts` list) -> local PROPOSALS under `namespace`, issued by `actor`.

    This is the intentional exception to 'never rewrite a namespace': the records are NEW local proposals, not imports. What is
    rewritten (namespace, issuer, predecessor) is recorded, with the original draft's content digest, in the payload field the kind has:
    `original.submission` where the kind has `original` (Problem), else `prior_review.submission` (Claim). Both are provenance, not review.
    """
    import copy
    from hashlib import sha256
    from pathlib import Path
    from frontier.models import Draft, digest
    from .artifacts import find_abs_paths
    mod = _root_submit()
    raw = Path(path).read_bytes()
    file_sha = sha256(raw).hexdigest()
    text = raw.decode()
    items = json.loads(text)["drafts"] if text.lstrip().startswith("{") and '"drafts"' in text[:400] else [json.loads(l) for l in text.splitlines() if l.strip()]
    out, seen, report = [], set(), {"content_available_ids": [], "origins": {}, "reissued_from": {}}
    for n, d0 in enumerate(items, 1):
        d = copy.deepcopy(d0)
        tag = f"{d.get('kind')}/{d.get('id')}"
        if d["kind"] == "Assessment":
            raise mod.Stop(f"{tag}: reviews cannot be submitted through this tool; an Assessment needs an independent reviewer principal")
        if (d["kind"], d["id"]) in seen:
            raise mod.Stop(f"item {n}: duplicate {tag} in the input")
        seen.add((d["kind"], d["id"]))
        foreign = [r for r in _refs_in(d["payload"]) if r["namespace"] != namespace]
        if foreign:
            raise mod.Stop(f"{tag}: payload pins {len(foreign)} record(s) outside {namespace!r}; re-issuing would break those pins, so remap them deliberately first")
        if find_abs_paths(d["payload"]):
            raise mod.Stop(f"{tag}: payload contains an absolute local path")
        src = d["payload"].get("source") or {}
        if src.get("content_available"):
            report["content_available_ids"].append(d["id"])
            if d["id"] not in allow_content_available:
                raise mod.Stop(f"{tag}: marks source content as AVAILABLE (licence {src.get('license')!r}); allow it explicitly with --allow-content-available {d['id']}")
        report["origins"][d["payload"].get("origin", "unset")] = report["origins"].get(d["payload"].get("origin", "unset"), 0) + 1
        prov = {"label": "provenance of this LOCAL PROPOSAL; not a review and not an acceptance", "tool": "frontier_adapters.import_cli submit-local",
                "original_namespace": d0["namespace"], "original_issuer": d0["issuer"], "input_file_sha256": file_sha,
                "draft_content_sha256": digest(mod.content_of(d0)), **submission}
        report["reissued_from"][d["id"]] = [d0["namespace"], d0["issuer"]]
        d["namespace"], d["issuer"], d["predecessor"] = namespace, actor, None
        payload = json.loads(json.dumps(d["payload"]))
        from frontier.models import PAYLOADS
        fields = PAYLOADS[d["kind"]].model_fields
        if "original" in fields:
            payload.setdefault("original", {})["submission"] = prov
        elif "prior_review" in fields:
            payload.setdefault("prior_review", {})["submission"] = prov
        else:
            raise mod.Stop(f"{tag}: kind {d['kind']} has no field that can carry submission provenance")
        d["payload"] = payload
        Draft.model_validate(d)
        out.append(d)
    return out, file_sha, report


def submit_local(args) -> int:
    mod = _root_submit()
    try:
        token = read_token(args.token_file)
        store = _store(args.dsn, args.namespace, args.schema)
        who = store.principal(token)
        submission = {"submitted_by_actor": who["actor"], "submitted_by_operator": who["operator"], "role": "proposer; not an independent reviewer"}
        drafts, file_sha, rep = load_local_drafts(args.input, args.namespace, who["actor"], submission, allow_content_available=set(args.allow_content_available))
        receipt = mod.run(store, token, drafts, args.expect_actor, args.expect_operator, args.execute, args.receipt_out, file_sha,
                          {"tool": "frontier_adapters.import_cli submit-local", "gates": rep})
    except mod.Stop as e:
        print(json.dumps({"ok": False, "stopped": str(e), "written": 0 if not args.execute else "see receipt if any"}))
        return 3
    except Exception as e:                                                  # never a traceback: it could carry a connection string
        code = getattr(e, "code", type(e).__name__)
        print(json.dumps({"ok": False, "error": code, "message": str(e)[:200] if code != "ValidationError" else "draft failed validation"}))
        return 2
    print(json.dumps({"mode": receipt["mode"], "planned": receipt["planned"], "quota_left_before": receipt["quota_left_before"],
                      "written": sum(1 for r in receipt["records"] if r["action"] in ("create", "revise")) if args.execute else 0,
                      "read_back": receipt.get("read_back"), "stopped": receipt.get("stopped"), "content_available_ids": rep["content_available_ids"]}))
    return 0 if not receipt.get("stopped") and not (receipt.get("read_back") or {}).get("not_head_or_not_proposed") else 2


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bounded deterministic import of frozen records into a Frontier store (credentials never printed)")
    ap.add_argument("command", choices=["build", "preflight", "import", "verify", "submit-local"])
    ap.add_argument("--records", action="append", default=[], help="JSON file of full Records (kept exact)")
    ap.add_argument("--drafts", action="append", default=[], help="JSONL of Draft dicts (created_at pinned to each draft's retrieval time)")
    ap.add_argument("--exclude-id", action="append", default=[], help="draft ids to leave out (e.g. ones already represented by --records)")
    ap.add_argument("--exporting-node", default="node-a")
    ap.add_argument("--max-records", type=int, default=100)
    ap.add_argument("--out"); ap.add_argument("--plan")
    ap.add_argument("--dsn"); ap.add_argument("--namespace"); ap.add_argument("--schema", default="public"); ap.add_argument("--token-file")
    ap.add_argument("--receipt"); ap.add_argument("--receipt-out")
    ap.add_argument("--only-bundles", type=int, default=None, help="import only the first N bundles")
    ap.add_argument("--allow-dangling-predecessor", action="append", default=[], help="record id whose predecessor is deliberately not in the store")
    ap.add_argument("--execute", action="store_true", help="actually write; without it `import` and `submit-local` are dry runs")
    ap.add_argument("--input", help="submit-local: JSONL of Drafts, or a JSON object with a `drafts` list")
    ap.add_argument("--expect-actor"); ap.add_argument("--expect-operator")
    ap.add_argument("--allow-content-available", action="append", default=[], help="submit-local: draft id whose source content_available=true is accepted")
    a = ap.parse_args(argv)
    if a.command == "submit-local":
        return submit_local(a)
    if a.command == "build":
        recs = []
        for r in a.records: recs += records_from_file(r)
        recs += records_from_drafts(a.drafts, exclude_ids=set(a.exclude_id))
        bundles = make_bundles(recs, a.exporting_node, max_records=a.max_records, keep_input_order=bool(a.drafts) and not a.records)
        plan = write_plan(bundles, a.out, source={"records_files": [os.path.basename(x) for x in a.records], "draft_files": [os.path.basename(x) for x in a.drafts],
                                                   "excluded_ids": sorted(a.exclude_id), "exporting_node": a.exporting_node})
        print(json.dumps({"bundles": len(bundles), "records": plan["total_records"], "by_namespace_kind": plan["by_namespace_kind"], "plan_sha256": plan["plan_sha256"]}, indent=1))
        return 0
    plan, bundles = load_bundles(a.plan)
    if a.only_bundles is not None:
        bundles = bundles[:a.only_bundles]
    store = _store(a.dsn, a.namespace, a.schema)
    if a.command == "verify":
        rep = verify(store, bundles)
        rep.update(plan_sha256=plan["plan_sha256"], bundles=len(bundles), verified_at=datetime.now(timezone.utc).isoformat())
        if a.receipt_out:
            tmp = a.receipt_out + ".tmp"
            with open(tmp, "w") as fh: json.dump(rep, fh, indent=1, sort_keys=True, default=str)
            os.replace(tmp, a.receipt_out)
        print(json.dumps({k: rep[k] for k in ("verified_ok", "status_counts")} | {"problems": len(rep["problems"])}, indent=1))
        return 0 if not rep["problems"] else 1
    token = read_token(a.token_file)
    if a.command == "preflight":
        rep = preflight(store, token, bundles, allow_dangling_predecessor=a.allow_dangling_predecessor)
        print(json.dumps(rep, indent=1, sort_keys=True, default=str))
        return 0 if rep["can_import"] and not rep["would_fork"] else 1
    pre = preflight(store, token, bundles, allow_dangling_predecessor=a.allow_dangling_predecessor)
    if pre["gates"]["refused"]:
        raise ImportRefused(f"graph gates refused {len(pre['gates']['refused'])} problem(s): {[g['why'][:70] for g in pre['gates']['refused'][:3]]}")
    if pre["would_fork"]:
        raise ImportRefused(f"{len(pre['would_fork'])} record(s) would fork an existing head; resolve deliberately first")
    if not pre["can_import"] or pre["quota_left"] < len(bundles):
        raise ImportRefused("principal cannot import, or the daily quota is insufficient")
    res = run_import(store, token, bundles, execute=a.execute, receipt_path=a.receipt)
    print(json.dumps({"executed": a.execute, "bundles": len(res), "inserted": sum(r.get("inserted", 0) for r in res), "errors": [r for r in res if r.get("error")]}, indent=1))
    return 0 if not any(r.get("error") for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())


# ---------------------------------------------------------------- receipt and site ids (pure functions over stored artifacts)
def make_receipt(*, plans: dict, import_receipts: list, verifies: dict, counts_before: dict, counts_before_note: str, code: dict,
                 principal: dict, store: dict, excluded: dict, cross_namespace: dict, notes: list) -> dict:
    """The final machine-readable receipt. Built only from artifacts of the run; contains no credential."""
    entries = [e for r in import_receipts for e in r]
    inserted = sum(e.get("inserted", 0) for e in entries)
    last = list(verifies.values())[-1]["counts_now"] if verifies else None
    rep = {
        "schema": "frontier-live-import-receipt-0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "imported_unreviewed. No record was accepted, reviewed or independently verified by this import. "
                  "single-reader, not Codex-reviewed.",
        "code": code, "principal": principal, "store": store,
        "plans": {k: {"plan_sha256": v["plan_sha256"], "bundles": [{"bundle_sha256": b["bundle_sha256"], "idempotency_key": b["idempotency_key"],
                                                                      "records": b["records"]} for b in v["bundles"]],
                      "total_records": v["total_records"], "by_namespace_kind": v["by_namespace_kind"]} for k, v in plans.items()},
        "import_responses": [{k: e.get(k) for k in ("bundle_sha256", "idempotency_key", "records", "inserted", "forks", "at", "error")} for e in entries],
        "inserted_total": inserted,
        "forks_recorded": sum(len(e.get("forks") or []) for e in entries),
        "verification": {k: {"verified_ok": v["verified_ok"], "problems": v["problems"], "status_counts": v["status_counts"], "verified_at": v.get("verified_at")}
                         for k, v in verifies.items()},
        "counts_before": counts_before, "counts_before_note": counts_before_note, "counts_after": last,
        "excluded": excluded, "same_id_in_other_namespaces": cross_namespace,
        "action_semantics": "Imported Action records remain in state 'proposed'. An import does not show any action executed locally; "
                            "the executed-run claim rests on the Evidence's run receipt, hashed artifacts and link checks, not on this import.",
        "issuer_note": "Import does not authenticate the issuer named in a record ('importer'); issuer_authenticated is false for every imported record.",
        "notes": notes,
    }
    rep["receipt_sha256"] = sha_obj({k: v for k, v in rep.items() if k != "receipt_sha256"})
    return rep


def site_ids(records: list[dict], chain: dict) -> dict:
    """Exact ids and edges for the site to render the claim -> action -> evidence -> artifact chain."""
    by_v = {r["version"]: r for r in records}
    rows = []
    for e in (r for r in records if r["kind"] == "Evidence"):
        t, pb = e["payload"]["target"], e["payload"]["produced_by"]
        claim, act = by_v[t["version"]], by_v[pb["version"]]
        rows.append({
            "claim": ref_of(claim), "delphi_claim_iri": claim["source_uri"], "delphi_nanopub": claim["payload"]["source_record_version"],
            "action": ref_of(act), "action_inputs": act["payload"]["inputs"], "evidence": ref_of(e),
            "relation": e["payload"]["relation"], "evidence_kind": e["payload"]["evidence_kind"],
            "artifacts": [{"role": a["role"], "sha256": a["sha256"], "byte_size": a["byte_size"], "uri": a["uri"], "availability": a["availability"],
                           "title": a["title"]} for a in e["payload"]["artifacts"]],
            "link_checks": [{"name": c["name"], "passed": c["passed"]} for c in e["payload"]["provenance"]["link_checks"]],
            "run_id": e["payload"]["provenance"]["run_id"], "backend": "local (not hosted compute, no GPU)",
        })
    return {"schema": "frontier-site-chain-ids-0.1", "namespace": records[0]["namespace"], "status": "imported_unreviewed; Actions 'proposed'",
            "chains": rows, "reuse_counts": chain.get("reuse_counts"),
            "not_yet_hosted": "artifact manifest (no served URL); artifacts are urn:sha256 pointers, availability 'referenced', no licence stated",
            "cross_namespace_note": "The same Delphi claim ids also exist as local proposals in namespace delphi-frontier; Evidence here pins the node-a versions."}
