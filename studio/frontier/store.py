"""Transactional domain service. All interfaces call this same authorization boundary.

Writes serialize on one node row in this first slice. This favors inspectable
correctness over throughput; no scalability result is implied.
"""
from contextlib import contextmanager
from hashlib import sha256
from pathlib import Path
import re
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import (Assessment, Draft, Record, Ref, KINDS, POLICY, MAX_BUNDLE_BYTES,
                     MAX_BUNDLE_RECORDS, canonical, digest, make_record, now, ref, references)


class FrontierError(ValueError):
    code = "invalid_request"
    http_status = 400


class Unauthorized(FrontierError):
    code = "unauthorized"
    http_status = 401


class Forbidden(FrontierError):
    code = "forbidden"
    http_status = 403


class Conflict(FrontierError):
    code = "conflict"
    http_status = 409


class Missing(FrontierError):
    code = "not_found"
    http_status = 404


class Store:
    def __init__(self, dsn: str, namespace: str, schema: str = "public"):
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("Invalid SQL schema name")
        Ref(namespace=namespace, kind="Problem", id="validation", version="0" * 64)
        self.dsn, self.namespace, self.schema = dsn, namespace, schema

    @contextmanager
    def connection(self):
        with psycopg.connect(self.dsn, row_factory=dict_row, connect_timeout=5) as c:
            c.execute(sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(self.schema)))
            c.execute("SET statement_timeout = '5s'")
            c.execute("SET lock_timeout = '5s'")
            yield c

    def initialize(self):
        """Operator-only migration, never exposed by HTTP or MCP."""
        with self.connection() as c:
            c.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            c.execute(Path(__file__).with_name("schema.sql").read_text())
            c.execute("INSERT INTO node_config VALUES (1,%s,1) ON CONFLICT DO NOTHING", (self.namespace,))
            if c.execute("SELECT namespace FROM node_config").fetchone()["namespace"] != self.namespace:
                raise Conflict("Store already belongs to another namespace")

    def provision(self, token: str, actor: str, operator: str, roles: list[str],
                  namespaces: list[str] | None = None, daily_write_limit: int = 100):
        """Explicit local operator configuration, not self-service or imported authority.

        Tokens are supplied in memory; only their hashes are persisted.
        """
        if not 24 <= len(token) <= 512 or not set(roles) <= {"contributor", "reviewer", "coordinator"}:
            raise ValueError("Invalid provisioning configuration")
        for identity in (actor, operator):
            Ref(namespace=self.namespace, kind="Actor", id=identity, version="0" * 64)
        with self.connection() as c:
            c.execute("INSERT INTO principals VALUES (%s,%s,%s,%s,%s,%s)",
                      (sha256(token.encode()).hexdigest(), actor, operator, Jsonb(roles),
                       Jsonb(namespaces or [self.namespace]), daily_write_limit))

    def _auth(self, c, token, role=None):
        if not token or not isinstance(token, str) or len(token) > 512:
            raise Unauthorized("Authenticated operator token required")
        p = c.execute("SELECT actor,operator,roles,namespaces,daily_write_limit FROM principals WHERE token_hash=%s",
                      (sha256(token.encode()).hexdigest(),)).fetchone()
        if p is None:
            raise Unauthorized("Unknown operator token")
        if role and role not in p["roles"]:
            raise Forbidden("Required role missing")
        return p

    def _read_principal(self, c, token):
        return self._auth(c, token) if token else None

    def _can_read(self, r, principal):
        return r["visibility"] == "public" or (principal and r["namespace"] in principal["namespaces"])

    def _raw(self, c, target, principal=None, current=False):
        t = Ref.model_validate(target).model_dump()
        row = c.execute("SELECT envelope FROM record_versions WHERE namespace=%s AND kind=%s AND record_id=%s AND version=%s",
                        (t["namespace"], t["kind"], t["id"], t["version"])).fetchone()
        if row is None or not self._can_read(row["envelope"], principal):
            raise Missing("Exact record version unavailable")
        if current:
            head = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s",
                             (t["namespace"], t["kind"], t["id"])).fetchone()
            if head is None or head["version"] != t["version"]:
                raise Conflict("Stale or forked target version")
        return row["envelope"]

    def _validate_refs(self, c, record, principal, current=True):
        for relation, target in references(record):
            referenced = self._raw(c, target, principal, current=current)
            # An action needs acceptance criteria, falsifiers, a next action and a stop bound.
            # A `recorded` problem has none of them, so there is nothing to execute or to stop.
            if record["kind"] == "Action" and relation == "targets" and referenced["kind"] == "Problem":
                if referenced["payload"].get("completeness") == "recorded":
                    raise Conflict("Target problem is recorded, not actionable; supply the four actionability fields first")

    def _write(self, token, key, request, role, operation):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", key):
            raise FrontierError("Bounded idempotency key required")
        fingerprint = digest(request)
        with self.connection() as c:
            # Lock first; checks, state change, event and response commit together.
            c.execute("SELECT singleton FROM node_config WHERE singleton=1 FOR UPDATE")
            p = self._auth(c, token, role)
            if self.namespace not in p["namespaces"]:
                raise Forbidden("Operator cannot write this namespace")
            prior = c.execute("SELECT request_hash,response FROM idempotency WHERE actor=%s AND key=%s", (p["actor"], key)).fetchone()
            if prior:
                if prior["request_hash"] != fingerprint:
                    raise Conflict("Idempotency key already used for a different request")
                return prior["response"]
            n = c.execute("SELECT count(*) AS n FROM write_receipts WHERE operator=%s AND witnessed_at > CURRENT_TIMESTAMP - INTERVAL '1 day'", (p["operator"],)).fetchone()["n"]
            if n >= p["daily_write_limit"]:
                raise Forbidden("Operator daily write quota exhausted")
            result = operation(c, p)
            c.execute("INSERT INTO write_receipts(actor,operator,witnessed_at) VALUES (%s,%s,CURRENT_TIMESTAMP)", (p["actor"], p["operator"]))
            c.execute("INSERT INTO idempotency VALUES (%s,%s,%s,%s,CURRENT_TIMESTAMP)", (p["actor"], key, fingerprint, Jsonb(result)))
            return result

    def _insert(self, c, record, p, status="proposed", set_head=True):
        c.execute("INSERT INTO record_versions VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                  (record["version"], record["namespace"], record["kind"], record["id"], record["issuer"], record["source_uri"],
                   record["visibility"], record["predecessor"], record["created_at"], Jsonb(record),
                   (record["id"] + " " + canonical(record["payload"])).lower()))
        c.execute("INSERT INTO local_states VALUES (%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
                  (record["version"], status, POLICY, p["actor"], p["operator"]))
        if set_head:
            c.execute("INSERT INTO heads VALUES (%s,%s,%s,%s) ON CONFLICT(namespace,kind,record_id) DO UPDATE SET version=EXCLUDED.version",
                      (record["namespace"], record["kind"], record["id"], record["version"]))
        for relation, target in references(record):
            c.execute("INSERT INTO typed_edges VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                      (record["version"], relation, target["namespace"], target["kind"], target["id"], target["version"]))
        if record["kind"] == "Action":
            c.execute("INSERT INTO action_state(version,state,updated_at) VALUES (%s,'proposed',CURRENT_TIMESTAMP)", (record["version"],))

    def _event(self, c, event_type, record, p, details=None):
        event = make_record(Draft(namespace=self.namespace, kind="Event", id=str(uuid4()), issuer=p["actor"],
                                 source_uri="urn:frontier:local-transaction", visibility=record["visibility"], payload={
                                     "event_type": event_type, "target": ref(record), "actor": p["actor"], "operator": p["operator"],
                                     "witnessed_at": now(), "details": details or {}}))
        self._insert(c, event, p)
        c.execute("INSERT INTO events(event_version,event_type,target_version,actor,operator,witnessed_at) VALUES (%s,%s,%s,%s,%s,%s)",
                  (event["version"], event_type, record["version"], p["actor"], p["operator"], event["payload"]["witnessed_at"]))

    def submit(self, token: str, key: str, draft: dict):
        d = Draft.model_validate(draft)
        if d.kind == "Event":
            raise Forbidden("Events are emitted only by transactions")

        def operation(c, p):
            if d.namespace != self.namespace or d.issuer != p["actor"]:
                raise Forbidden("Issuer and namespace must match authenticated actor and node")
            head = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s",
                             (d.namespace, d.kind, d.id)).fetchone()
            expected = head["version"] if head else None
            if d.predecessor != expected:
                raise Conflict("Stale predecessor; supply exact current version")
            if d.kind == "Action" and head:
                state = c.execute("SELECT state FROM action_state WHERE version=%s", (expected,)).fetchone()["state"]
                if state not in {"proposed", "ready", "cancelled", "failed", "expired"}:
                    raise Conflict("Cannot revise an action with active or completed execution")
            record = make_record(d)
            self._validate_refs(c, record, p)
            self._insert(c, record, p)
            self._event(c, "record_proposed", record, p)
            return {"record": record, "local_status": "proposed", "artifact_bytes_verified": False}
        return self._write(token, key, {"op": "submit", "draft": draft}, "contributor", operation)

    def get(self, target: dict, token: str | None = None):
        with self.connection() as c:
            p = self._read_principal(c, token)
            record = self._raw(c, target, p)
            state = c.execute("SELECT status,policy_version FROM local_states WHERE version=%s", (record["version"],)).fetchone()
            action = c.execute("SELECT state,lease_until FROM action_state WHERE version=%s", (record["version"],)).fetchone()
            head = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s",
                             (record["namespace"], record["kind"], record["id"])).fetchone()
            return {"record": record, "local_review": state, "is_head": bool(head and head["version"] == record["version"]),
                    "action": {"state": action["state"], "lease_until": action["lease_until"].isoformat() if action["lease_until"] else None} if action else None}

    def search(self, query="", kind=None, status=None, limit=20, after="", token=None):
        if len(query) > 200 or not 1 <= limit <= 50 or len(after) > 64 or (after and not re.fullmatch(r"[0-9a-f]{64}", after)):
            raise FrontierError("Invalid bounded search parameters")
        if kind and kind not in KINDS:
            raise FrontierError("Unknown kind")
        if status and status not in {"proposed", "imported_unreviewed", "accepted", "disputed", "rejected"}:
            raise FrontierError("Unknown review status")
        with self.connection() as c:
            p = self._read_principal(c, token)
            args = [after, Jsonb(p["namespaces"] if p else []), query.lower(), query.lower(), kind, kind, status, status, limit + 1]
            rows = c.execute("""SELECT v.envelope,s.status FROM record_versions v JOIN local_states s USING(version)
                JOIN heads h ON h.version=v.version
                WHERE v.version>%s AND (v.visibility='public' OR %s::jsonb ? v.namespace)
                AND (%s='' OR position(%s in v.search_text)>0)
                AND (%s::text IS NULL OR v.kind=%s) AND (%s::text IS NULL OR s.status=%s)
                ORDER BY v.version LIMIT %s""", args).fetchall()
            results = [{"ref": ref(r["envelope"]), "issuer": r["envelope"]["issuer"], "source_uri": r["envelope"]["source_uri"],
                        "title": r["envelope"]["payload"].get("title", r["envelope"]["id"]), "local_status": r["status"],
                        "why_matched": "all within filters" if not query else "literal text match: " + query} for r in rows[:limit]]
            return {"results": results, "next_cursor": results[-1]["ref"]["version"] if len(rows) > limit else None,
                    "search_kind": "bounded literal lexical retrieval; relevance is not truth"}

    def neighborhood(self, target, limit=20, token=None):
        if not 1 <= limit <= 50:
            raise FrontierError("Limit must be 1..50")
        with self.connection() as c:
            p = self._read_principal(c, token)
            record = self._raw(c, target, p)
            rows = c.execute("""SELECT e.*,v.envelope FROM typed_edges e
                JOIN record_versions v ON v.version=e.source_version
                WHERE (source_version=%s OR target_version=%s)
                  AND (v.visibility='public' OR %s::jsonb ? v.namespace)
                ORDER BY source_version,target_version LIMIT %s""",
                (record["version"], record["version"], Jsonb(p["namespaces"] if p else []), limit + 1)).fetchall()
            edges = []
            for row in rows[:limit]:
                dest = {"namespace": row["target_namespace"], "kind": row["target_kind"], "id": row["target_id"], "version": row["target_version"]}
                try:
                    self._raw(c, dest, p)
                except Missing:
                    continue
                edges.append({"source": ref(row["envelope"]), "relation": row["relation"], "target": dest})
            return {"edges": edges, "truncated": len(rows) > limit, "depth": 1,
                    "limit": "Typed one-hop relations, including disputed assessments; no implicit support inference."}

    def review(self, token, key, assessment: dict):
        a = Assessment.model_validate(assessment)
        if a.decision == "unreviewed":
            raise FrontierError("A review requires an explicit decision")

        def operation(c, p):
            target = self._raw(c, a.target.model_dump(), p, current=True)
            state = c.execute("SELECT submitter_operator FROM local_states WHERE version=%s", (target["version"],)).fetchone()
            if target["issuer"] == p["actor"] or state["submitter_operator"] == p["operator"]:
                raise Forbidden("Independent operator review required")
            if any(d.reviewer != p["actor"] for d in a.dimensions.values()):
                raise Forbidden("Dimension reviewer must match authenticated reviewer")
            if a.decision == "accepted":
                if any(d.status not in {"passed", "not_applicable"} for d in a.dimensions.values()):
                    raise Conflict("Unreviewed, failed or insufficient dimensions cannot be accepted")
                if any(a.dimensions[k].status != "passed" for k in ("target_fidelity", "applicability")):
                    raise Conflict("Acceptance requires target fidelity and applicability to pass")
            self._validate_refs(c, target, p)
            draft = Draft(namespace=self.namespace, kind="Assessment", id=str(uuid4()), issuer=p["actor"],
                          source_uri="urn:frontier:local-review", visibility=target["visibility"], payload=a.model_dump())
            review = make_record(draft)
            self._validate_refs(c, review, p)
            if target["kind"] == "Action":
                action = c.execute("SELECT state,lease_operator FROM action_state WHERE version=%s", (target["version"],)).fetchone()
                if action["state"] != "submitted" or action["lease_operator"] == p["operator"]:
                    raise Conflict("Only submitted work reviewed by a separate operator can be adjudicated")
                self._event(c, "action_reviewed", target, p, {"assessment": ref(review)})
                action_status = {"accepted": "accepted", "disputed": "disputed", "rejected": "failed"}[a.decision]
                c.execute("UPDATE action_state SET state=%s,updated_at=CURRENT_TIMESTAMP WHERE version=%s", (action_status, target["version"]))
                self._event(c, "action_" + action_status, target, p)
            self._insert(c, review, p)
            c.execute("INSERT INTO reviews VALUES (%s,%s,%s,%s,%s,%s,CURRENT_TIMESTAMP)",
                      (review["version"], target["version"], p["actor"], p["operator"], a.decision, POLICY))
            c.execute("UPDATE local_states SET status=%s,updated_at=CURRENT_TIMESTAMP WHERE version=%s", (a.decision, target["version"]))
            self._event(c, "review_recorded", target, p, {"assessment": ref(review)})
            self._event(c, "acceptance_changed", target, p, {"status": a.decision, "policy_version": POLICY})
            return {"assessment": review, "local_status": a.decision, "policy_version": POLICY}
        return self._write(token, key, {"op": "review", "assessment": assessment}, "reviewer", operation)

    def transition(self, token, key, target, state, lease_id=None):
        if state not in {"ready", "running", "submitted", "blocked", "cancelled", "failed"}:
            raise FrontierError("Unsupported transition; reviews control acceptance")

        def operation(c, p):
            record = self._raw(c, target, p, current=True)
            if record["kind"] != "Action" or record["namespace"] != self.namespace:
                raise Conflict("Only locally owned Action versions can execute")
            current = c.execute("SELECT * FROM action_state WHERE version=%s", (record["version"],)).fetchone()
            if state == "ready":
                if "coordinator" not in p["roles"] or current["state"] not in {"proposed", "blocked", "expired"}:
                    raise Forbidden("Coordinator readiness gate required")
                self._validate_refs(c, record, p)
            elif state in {"blocked", "cancelled", "failed"} and "coordinator" in p["roles"]:
                if current["state"] in {"accepted", "disputed", "failed", "cancelled"}:
                    raise Conflict("Terminal action cannot transition")
            else:
                if current["lease_actor"] != p["actor"] or lease_id != current["lease_id"]:
                    raise Forbidden("Lease owner and exact lease ID required")
                live = c.execute("SELECT %s::timestamptz > CURRENT_TIMESTAMP AS live", (current["lease_until"],)).fetchone()["live"]
                if not live:
                    raise Conflict("Lease expired")
                allowed = {"leased": {"running", "blocked", "failed", "cancelled"}, "running": {"submitted", "blocked", "failed", "cancelled"}}
                if state not in allowed.get(current["state"], set()):
                    raise Conflict("Invalid action lifecycle transition")
            c.execute("UPDATE action_state SET state=%s,updated_at=CURRENT_TIMESTAMP WHERE version=%s", (state, record["version"]))
            self._event(c, "action_" + state, record, p)
            return {"target": target, "state": state}
        return self._write(token, key, {"op": "transition", "target": target, "state": state, "lease_id": lease_id}, "contributor", operation)

    def lease(self, token, key, target, seconds=60):
        if not isinstance(seconds, int) or isinstance(seconds, bool) or not 1 <= seconds <= 600:
            raise FrontierError("Lease duration must be 1..600 seconds")

        def operation(c, p):
            record = self._raw(c, target, p, current=True)
            if record["kind"] != "Action" or record["namespace"] != self.namespace:
                raise Conflict("Only local Action versions can be leased")
            self._validate_refs(c, record, p)
            prior = c.execute("SELECT state,lease_until FROM action_state WHERE version=%s", (record["version"],)).fetchone()
            lease_id = str(uuid4())
            won = c.execute("""UPDATE action_state SET state='leased',lease_id=%s,lease_actor=%s,lease_operator=%s,
                lease_until=CURRENT_TIMESTAMP + %s * INTERVAL '1 second',updated_at=CURRENT_TIMESTAMP
                WHERE version=%s AND (state IN ('ready','expired') OR (state IN ('leased','running') AND lease_until<=CURRENT_TIMESTAMP))
                RETURNING lease_until""", (lease_id, p["actor"], p["operator"], seconds, record["version"])).fetchone()
            if not won:
                raise Conflict("Action unavailable or lease already held")
            if prior["state"] in {"leased", "running"}:
                self._event(c, "action_expired", record, p, {"expired_at": prior["lease_until"].isoformat()})
            self._event(c, "action_leased", record, p, {"lease_id": lease_id, "lease_until": won["lease_until"].isoformat()})
            return {"target": target, "state": "leased", "lease_id": lease_id, "lease_until": won["lease_until"].isoformat()}
        return self._write(token, key, {"op": "lease", "target": target, "seconds": seconds}, "contributor", operation)

    def export_bundle(self, targets, token=None):
        if not 1 <= len(targets) <= MAX_BUNDLE_RECORDS:
            raise FrontierError("Export requires 1..100 explicit versions; dependencies are not silently expanded")
        with self.connection() as c:
            p = self._read_principal(c, token)
            records = [self._raw(c, target, p) for target in targets]
            versions = [r["version"] for r in records]
            rows = c.execute("SELECT assessment_version,target_version,reviewer,operator,decision,policy_version,witnessed_at FROM reviews WHERE target_version=ANY(%s) ORDER BY assessment_version LIMIT 101", (versions,)).fetchall()
            claims = [{**r, "witnessed_at": r["witnessed_at"].isoformat()} for r in rows]
            if len(claims) > 100:
                raise FrontierError("Too many review receipts for one bundle")
            # Preserve complete dimensional reviews, bounded with the selected records.
            for review in rows:
                if review["assessment_version"] not in versions:
                    assessment = c.execute("SELECT envelope FROM record_versions WHERE version=%s", (review["assessment_version"],)).fetchone()["envelope"]
                    if self._can_read(assessment, p):
                        records.append(assessment)
                        versions.append(assessment["version"])
            if len(records) > MAX_BUNDLE_RECORDS:
                raise FrontierError("Selected records plus dimensional reviews exceed 100-record bundle limit")
            body = {"schema_version": "frontier-bundle-0.1", "exporting_node": self.namespace,
                    "records": records, "review_claims": claims, "policy_version": POLICY,
                    "trust": "Digest proves integrity only; reviews require receiving-node policy."}
            bundle = {**body, "bundle_sha256": digest(body)}
            if len(canonical(bundle).encode()) > MAX_BUNDLE_BYTES:
                raise FrontierError("Bundle exceeds byte limit")
            return bundle

    def import_bundle(self, token, key, bundle):
        if len(canonical(bundle).encode()) > MAX_BUNDLE_BYTES:
            raise FrontierError("Bundle exceeds byte limit")
        if set(bundle) != {"schema_version", "exporting_node", "records", "review_claims", "policy_version", "trust", "bundle_sha256"}:
            raise FrontierError("Unknown bundle fields")
        if bundle["schema_version"] != "frontier-bundle-0.1" or digest({k:v for k,v in bundle.items() if k != "bundle_sha256"}) != bundle["bundle_sha256"]:
            raise FrontierError("Bundle digest or version mismatch")
        if not 1 <= len(bundle["records"]) <= MAX_BUNDLE_RECORDS or len(bundle["review_claims"]) > 100:
            raise FrontierError("Bundle record/review limit exceeded")
        records = [Record.model_validate(r).model_dump() for r in bundle["records"]]

        def operation(c, p):
            inserted, forks = [], []
            for record in records:
                if c.execute("SELECT 1 FROM record_versions WHERE version=%s", (record["version"],)).fetchone():
                    continue
                head = c.execute("SELECT version FROM heads WHERE namespace=%s AND kind=%s AND record_id=%s",
                                 (record["namespace"], record["kind"], record["id"])).fetchone()
                self._insert(c, record, p, status="imported_unreviewed", set_head=head is None)
                self._event(c, "record_imported", record, p, {"bundle_sha256": bundle["bundle_sha256"], "issuer_authenticated": False})
                inserted.append(ref(record))
                if head:
                    fork = {"local_version": head["version"], "imported_version": record["version"]}
                    c.execute("INSERT INTO forks VALUES (%s,%s,%s,%s,%s)", (record["namespace"], record["kind"], record["id"], head["version"], record["version"]))
                    self._event(c, "fork_detected", record, p, fork)
                    forks.append(fork)
            for claim in bundle["review_claims"]:
                # Stored as an untrusted source assertion, never in local reviews/auth.
                c.execute("INSERT INTO imported_review_claims VALUES (%s,%s,%s,CURRENT_TIMESTAMP) ON CONFLICT DO NOTHING",
                          (digest({"node": bundle["exporting_node"], "claim": claim}), bundle["exporting_node"], Jsonb(claim)))
            return {"inserted": inserted, "forks": forks, "imported_reviews_are_local_authority": False}
        return self._write(token, key, {"op": "import", "bundle_sha256": bundle["bundle_sha256"]}, "coordinator", operation)

    def events(self, after=0, limit=20, token=None):
        if not isinstance(after, int) or after < 0 or not 1 <= limit <= 50:
            raise FrontierError("Invalid event cursor/limit")
        with self.connection() as c:
            p = self._read_principal(c, token)
            rows = c.execute("""SELECT e.sequence,v.envelope FROM events e JOIN record_versions v ON v.version=e.event_version
                WHERE e.sequence>%s AND (v.visibility='public' OR %s::jsonb ? v.namespace)
                ORDER BY e.sequence LIMIT %s""", (after, Jsonb(p["namespaces"] if p else []), limit + 1)).fetchall()
            return {"events": rows[:limit], "next_cursor": rows[limit-1]["sequence"] if len(rows) > limit else None}
