"""Contextual discovery of artifact declarations, never a URL-fetch or execution service.

Artifacts stay attached to immutable Evidence versions. Identical bytes in two
contexts remain two uses, not two independently confirming measurements.
"""
import base64
from hashlib import sha256
import json
import re

from psycopg.types.json import Jsonb

from .models import ArtifactRef, canonical, ref
from .store import FrontierError, Store, _refuse_unlicensed, _unlicensed_available_content

ROLES = ("input", "output", "code", "environment", "protocol", "log", "certificate", "geometry")
EVIDENCE_KINDS = ("observed", "predicted", "simulated", "formal", "source_assessment")


class ArtifactIndex:
    def __init__(self, store: Store):
        self.store = store

    def search(self, query="", *, role=None, evidence_kind=None, limit=20, cursor="", token=None):
        if (not isinstance(query, str) or len(query) > 200 or "\x00" in query
                or type(limit) is not int or not 1 <= limit <= 50
                or role is not None and role not in ROLES
                or evidence_kind is not None and evidence_kind not in EVIDENCE_KINDS):
            raise FrontierError("Invalid bounded artifact search")
        if not isinstance(cursor, str) or len(cursor) > 512:
            raise FrontierError("Invalid artifact cursor")
        identity = sha256(canonical([query.lower(), role, evidence_kind]).encode()).hexdigest()[:16]
        after = ("", "", "")
        if cursor:
            try:
                cur = json.loads(base64.urlsafe_b64decode(cursor.encode()))
                if (not isinstance(cur, list) or len(cur) != 4 or cur[0] != identity
                        or not all(isinstance(s, str) and re.fullmatch(r"[a-f0-9]{64}", s) for s in cur[1:3])
                        or cur[3] not in ROLES):
                    raise ValueError
                after = tuple(cur[1:])
            except (ValueError, TypeError, UnicodeError):
                raise FrontierError("Invalid artifact cursor or changed filters") from None
        with self.store.connection() as c:
            principal = self.store._read_principal(c, token)
            namespaces = Jsonb(principal["namespaces"] if principal else [])
            rows = c.execute("""
                SELECT v.envelope, s.status, a.value AS artifact,
                       h.version IS NOT NULL AS is_head
                FROM record_versions v JOIN local_states s USING(version)
                LEFT JOIN heads h ON h.version=v.version
                CROSS JOIN LATERAL jsonb_array_elements(coalesce(v.envelope->'payload'->'artifacts', '[]'::jsonb)) a
                WHERE v.kind='Evidence' AND (v.visibility='public' OR %(ns)s::jsonb ? v.namespace)
                  AND (%(role)s::text IS NULL OR a.value->>'role'=%(role)s)
                  AND (%(kind)s::text IS NULL OR v.envelope #>> '{payload,evidence_kind}'=%(kind)s)
                  AND (%(q)s='' OR position(%(q)s in lower(a.value::text))>0
                       OR position(%(q)s in lower(v.envelope #>> '{payload,context}'))>0)
                  AND (a.value->>'sha256', v.version, a.value->>'role') > (%(sha)s,%(version)s,%(arole)s)
                ORDER BY a.value->>'sha256',v.version,a.value->>'role'
                LIMIT %(n)s
            """, {"ns": namespaces, "role": role, "kind": evidence_kind, "q": query.lower(),
                  "sha": after[0], "version": after[1], "arole": after[2], "n": limit + 1}).fetchall()
            items = []
            for row in rows[:limit]:
                _refuse_unlicensed(_unlicensed_available_content([row["envelope"]]), "index")
                env, artifact = row["envelope"], ArtifactRef.model_validate(row["artifact"]).model_dump()
                p = env["payload"]
                items.append({"artifact": artifact, "evidence": ref(env), "target": p["target"],
                              "produced_by": p.get("produced_by"), "evidence_kind": p["evidence_kind"],
                              "relation": p.get("relation", "unspecified"), "context": p["context"],
                              "assumptions": p["assumptions"], "limitations": p["limitations"],
                              "source_dependence": p["source_dependence"], "local_status": row["status"],
                              "is_head": row["is_head"], "artifact_bytes_verified": False,
                              "verification_note": "Declared metadata; follow the evidence and review receipts for checks. The index does not fetch bytes."})
            next_cursor = None
            if len(rows) > limit:
                last = items[-1]
                val = [identity, last["artifact"]["sha256"], last["evidence"]["version"], last["artifact"]["role"]]
                next_cursor = base64.urlsafe_b64encode(canonical(val).encode()).decode()
            return {"items": items, "next_cursor": next_cursor, "mode": "live", "namespace": self.store.namespace,
                    "search_kind": "literal artifact metadata and context search; no semantic ranking",
                    "count_scope": "artifact declarations per exact Evidence version, including history; not independent observations"}
