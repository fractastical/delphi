"""Read-only adapter: Frontier PostgreSQL store -> plain records/events for the attention view.

* The connection is opened with default_transaction_read_only=on and verified; a write on it fails (tested).
* Only these tables and columns are read: record_versions(version, envelope), heads(kind, record_id, version), local_states(version, status),
  typed_edges(source_version, relation, target_*), events(sequence, event_version). It never touches principals, idempotency, write_receipts
  or any credential-bearing table, and it needs no token: it does not use the Store class, so no principal is created or consumed.
* Private records are excluded by default (a snapshot may be published). Every envelope is re-verified (digest and schema); failures are reported.
* The DSN is used as given and is never written into the output (only host path, port, dbname and namespace are recorded).
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from frontier.models import Record, canonical, digest


class ReadOnlyError(RuntimeError):
    pass


def connect_readonly(dsn: str, schema: str | None = None, timeout: int = 5):
    opts = "-c default_transaction_read_only=on" + (f" -c search_path={schema}" if schema else "")
    c = psycopg.connect(dsn, options=opts, connect_timeout=timeout, row_factory=dict_row, autocommit=False)
    c.read_only = True
    if c.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] != "on":
        c.close()
        raise ReadOnlyError("could not establish a read-only transaction; refusing to read")
    return c


def check_envelope(env: dict) -> tuple[str, str]:
    """('ok'|'digest'|'schema', detail). `digest`: the stored bytes do not hash to the version (tampering or corruption). `schema`: the digest is
    fine but THIS checkout's models reject the payload (a running store may be newer than this code); the record is kept and flagged, not dropped."""
    try:
        if digest({k: v for k, v in env.items() if k != "version"}) != env.get("version"):
            return "digest", "recomputed digest differs from the stored version"
    except Exception as exc:
        return "digest", f"cannot hash: {exc}"[:200]
    try:
        Record.model_validate(env)
    except Exception as exc:
        return "schema", str(exc).replace("\n", " ")[:200]
    return "ok", ""


def _describe(dsn: str) -> dict:
    kv = dict(p.split("=", 1) for p in dsn.split() if "=" in p and not p.lower().startswith(("password", "passfile", "sslkey", "sslpassword")))
    return {k: kv[k] for k in ("host", "port", "dbname") if k in kv}


def read_store(dsn: str, namespace: str, *, schema: str | None = None, include_private: bool = False) -> dict:
    """Return {records, events, local_status, typed_edges, heads, meta}. Reads only; see module docstring."""
    with connect_readonly(dsn, schema) as c:
        recs = c.execute("SELECT version, envelope FROM record_versions WHERE namespace=%s", (namespace,)).fetchall()
        heads = c.execute("SELECT kind, record_id, version FROM heads WHERE namespace=%s", (namespace,)).fetchall()
        states = c.execute("SELECT s.version, s.status FROM local_states s JOIN record_versions v ON v.version=s.version WHERE v.namespace=%s", (namespace,)).fetchall()
        edges = c.execute("""SELECT e.source_version, e.relation, e.target_namespace, e.target_kind, e.target_id, e.target_version
                             FROM typed_edges e JOIN record_versions v ON v.version=e.source_version WHERE v.namespace=%s""", (namespace,)).fetchall()
        evs = c.execute("""SELECT e.sequence, v.envelope FROM events e JOIN record_versions v ON v.version=e.event_version
                           WHERE v.namespace=%s ORDER BY e.sequence""", (namespace,)).fetchall()
        read_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records, excluded_private, integrity, skew = [], 0, [], []
    for r in recs:
        env = r["envelope"]
        if env.get("visibility") != "public" and not include_private:
            excluded_private += 1
            continue
        verdict, detail = check_envelope(env)
        if verdict == "digest":
            integrity.append({"version": r["version"], "error": detail})
        elif verdict == "schema":
            skew.append({"version": r["version"], "kind": env.get("kind"), "error": detail})
        records.append(env)
    visible = {r["version"] for r in records}
    events = [{"sequence": e["sequence"], "envelope": e["envelope"]} for e in evs if e["envelope"]["version"] in visible]
    status = {s["version"]: s["status"] for s in states if s["version"] in visible}
    head_versions = {(h["kind"], h["record_id"]): h["version"] for h in heads if h["version"] in visible}
    records.sort(key=lambda r: (r["kind"], r["id"], r["created_at"], r["version"]))
    content = {"records": [r["version"] for r in records], "events": [(e["sequence"], e["envelope"]["version"]) for e in events]}
    return {
        "records": records, "events": events, "local_status": status,
        "typed_edges": [e for e in edges if e["source_version"] in visible],
        "heads": {f"{k}/{i}": v for (k, i), v in sorted(head_versions.items())},
        "meta": {"source": {**_describe(dsn), "namespace": namespace, "schema": schema or "public"}, "read_at_utc": read_at, "read_only": True,
                 "tables_read": ["record_versions", "heads", "local_states", "typed_edges", "events"],
                 "records": len(records), "events": len(events), "excluded_private": excluded_private, "integrity_failures": integrity,
                 "schema_skew": {"count": len(skew), "examples": skew[:3], "by_kind": dict(Counter(x["kind"] for x in skew)),
                                 "note": "digest is valid but this checkout's models reject the payload: the store is probably newer than this code. Records are kept; unknown vocabulary values are carried verbatim and marked recognized:false."},
                 "content_sha256": digest(content)},
    }
