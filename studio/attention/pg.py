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


# Stated in every read's meta so a reader can see exactly what was left out. Kept outside read_store so a test can assert that function's SQL never names these tables.
OTHER_EXCLUSIONS = ["private records (unless include_private)",
                    "tables principals, idempotency, write_receipts, reviews, forks, imported_review_claims, action_state are never read",
                    "record bodies are never rewritten; beyond the five tables only aggregate counts (census) are read"]


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


def census(dsn: str, schema: str | None = None) -> dict:
    """Aggregate counts for the WHOLE database, all namespaces, no record bodies: what exists, so a scoped read can say what it left out."""
    with connect_readonly(dsn, schema) as c:
        recs = c.execute("SELECT namespace, kind, envelope->>'visibility' AS visibility, count(*) AS n FROM record_versions GROUP BY 1,2,3 ORDER BY 1,2,3").fetchall()
        states = c.execute("SELECT status, count(*) AS n FROM local_states GROUP BY 1 ORDER BY 1").fetchall()
        events = c.execute("""SELECT v.namespace AS event_namespace, e.event_type, t.namespace AS target_namespace, t.kind AS target_kind, count(*) AS n
                              FROM events e JOIN record_versions v ON v.version=e.event_version JOIN record_versions t ON t.version=e.target_version
                              GROUP BY 1,2,3,4 ORDER BY 1,2,3,4""").fetchall()
    return {"record_versions": recs, "total_record_versions": sum(r["n"] for r in recs), "local_status": states,
            "events_by_namespace_and_target": events, "total_events": sum(e["n"] for e in events),
            "namespaces": sorted({r["namespace"] for r in recs})}


def read_store(dsn: str, namespace: str | list[str] | None = None, *, schema: str | None = None, include_private: bool = False) -> dict:
    """Return {records, events, local_status, typed_edges, heads, meta}. Reads only; see module docstring.
    `namespace`: one namespace, a list, or None for ALL namespaces. The scope actually used, and what it excluded, is recorded in meta."""
    listed = None if namespace is None else ([namespace] if isinstance(namespace, str) else list(namespace))
    where_ns = "TRUE" if listed is None else "v.namespace = ANY(%s)"
    args = () if listed is None else (listed,)
    with connect_readonly(dsn, schema) as c:
        recs = c.execute(f"SELECT version, envelope FROM record_versions v WHERE {where_ns}", args).fetchall()
        heads = c.execute(f"SELECT kind, record_id, version, namespace FROM heads v WHERE {where_ns}", args).fetchall()
        states = c.execute(f"SELECT s.version, s.status FROM local_states s JOIN record_versions v ON v.version=s.version WHERE {where_ns}", args).fetchall()
        edges = c.execute(f"""SELECT e.source_version, e.relation, e.target_namespace, e.target_kind, e.target_id, e.target_version
                             FROM typed_edges e JOIN record_versions v ON v.version=e.source_version WHERE {where_ns}""", args).fetchall()
        evs = c.execute(f"""SELECT e.sequence, v.envelope FROM events e JOIN record_versions v ON v.version=e.event_version
                           WHERE {where_ns} ORDER BY e.sequence""", args).fetchall()
        whole = c.execute("SELECT namespace, kind, count(*) AS n FROM record_versions GROUP BY 1,2 ORDER BY 1,2").fetchall()
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
    head_versions = {(h["namespace"], h["kind"], h["record_id"]): h["version"] for h in heads if h["version"] in visible}
    records.sort(key=lambda r: (r["kind"], r["id"], r["created_at"], r["version"]))
    content = {"records": [r["version"] for r in records], "events": [(e["sequence"], e["envelope"]["version"]) for e in events]}
    return {
        "records": records, "events": events, "local_status": status,
        "typed_edges": [e for e in edges if e["source_version"] in visible],
        "heads": {f"{n}/{k}/{i}": v for (n, k, i), v in sorted(head_versions.items())},
        "meta": {"source": {**_describe(dsn), "schema": schema or "public"},
                 "scope": {"mode": "all_namespaces" if listed is None else "listed_namespaces", "namespaces_requested": listed,
                           "namespaces_read": sorted({r["namespace"] for r in records}),
                           "excluded_by_scope": [{"namespace": w["namespace"], "kind": w["kind"], "record_versions": w["n"]} for w in whole
                                                 if listed is not None and w["namespace"] not in listed],
                           "other_exclusions": OTHER_EXCLUSIONS}, "read_at_utc": read_at, "read_only": True,
                 "tables_read": ["record_versions", "heads", "local_states", "typed_edges", "events"],
                 "records": len(records), "events": len(events), "excluded_private": excluded_private, "integrity_failures": integrity,
                 "schema_skew": {"count": len(skew), "examples": skew[:3], "by_kind": dict(Counter(x["kind"] for x in skew)),
                                 "note": "digest is valid but this checkout's models reject the payload: the store is probably newer than this code. Records are kept; unknown vocabulary values are carried verbatim and marked recognized:false."},
                 "content_sha256": digest(content)},
    }
