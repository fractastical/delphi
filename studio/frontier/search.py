"""Indexed lexical and exact discovery over the Frontier store.

What this is: PostgreSQL full-text candidate retrieval (GIN index over the store's own ``search_text``, ``simple``
dictionary) PLUS a literal substring fallback, ranked by integer tiers, with bounded keyset pagination, structured
filters, a ``why_matched`` explanation, exact version pins, and explicit opposing/disputed references.

What this is not: not semantic search, not a hybrid, not a truth or quality score. There are no embeddings and none are
claimed; embeddings could later supply extra CANDIDATES but would not change the pins or the access rules here. Ranking
never reads review status or curation labels, so nothing is silently promoted: labels describe, they do not rank.

Reuses the Store's connection, principal lookup and visibility rule unchanged. No data is copied; only indexes are added
(search_schema.sql). Reads only; no writes, no network.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from psycopg.types.json import Jsonb

from .models import KINDS, canonical, ref
from .store import FrontierError, Store, _unlicensed_available_content

STATUSES = ("proposed", "imported_unreviewed", "accepted", "disputed", "rejected")
MAX_QUERY = 200
MAX_TERMS = 12
MAX_REFS_PER_RESULT = 10
SNIPPET_RADIUS = 80
SEARCH_KIND = ("PostgreSQL full-text (simple dictionary, GIN-indexed) plus literal substring fallback; lexical only, "
               "no embeddings, no hybrid; relevance is not truth")
_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_CURSOR = re.compile(r"^(?P<score>[0-9]{1,6})\.(?P<version>[0-9a-f]{64})\.(?P<pid>[0-9a-f]{8})$")

# Integer rank tiers. They only order candidates; they say nothing about correctness.
# The score is LEXICOGRAPHIC: the best single category a record satisfies (a MAX, never a sum), times 1000, plus a secondary
# full-text relevance bucket of at most 999. So a higher category always outranks a lower one however many lower categories
# a record also satisfies (a record matching source + title + literal text cannot outrank an exact version pin).
T_EXACT_VERSION, T_EXACT_ID, T_EXACT_SOURCE = 9000, 8000, 7000
T_TITLE_EQUALS, T_TITLE_CONTAINS, T_LITERAL, T_LEXICAL = 6000, 5000, 4000, 1000
T_SECONDARY_MAX = 999


def _as_tuple(value: str | Sequence[str] | None, allowed: Iterable[str], what: str) -> tuple[str, ...] | None:
    if value is None:
        return None
    items = (value,) if isinstance(value, str) else tuple(value)
    if not items or len(items) > len(tuple(allowed)) or len(set(items)) != len(items) or any(i not in allowed for i in items):
        raise FrontierError(f"Unknown or repeated {what}")
    return items


def _like_prefix(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _text_of(value: Any) -> str:
    return value.lower() if isinstance(value, str) else canonical(value).lower()


def source_view(payload: dict) -> dict | None:
    """The payload's own source assertion, kept separate from review status. None if the record type has no source."""
    src = payload.get("source")
    if not isinstance(src, dict):
        return None
    return {"uri": src.get("uri"), "locator": src.get("locator"), "source_version": src.get("source_version"),
            "content_available": bool(src.get("content_available")), "license": src.get("license"),
            "content_sha256_declared": bool(src.get("content_sha256")), "access": src.get("access")}


def source_fidelity(src: dict | None) -> str:
    """Three honest classes of source support, never merged into one 'sourced' flag."""
    if src is None:
        return "not_applicable"
    if not src["uri"] and not src["locator"]:
        return "no_source"
    if not src["locator"]:
        return "reference_only"
    return "locator_present"


_FIDELITY_TEXT = {
    "no_source": "no source recorded",
    "reference_only": "topic-level source reference only, no locator",
    "locator_present": "source locator recorded; whether it supports the text is not checked by search",
}
_STATUS_TEXT = {
    "proposed": "not independently reviewed",
    "imported_unreviewed": "imported and not reviewed by this node",
    "accepted": "accepted under this node's review policy; not a scientific endorsement",
    "disputed": "disputed by a recorded review",
    "rejected": "rejected by a recorded review",
}


def curation_labels(envelope: dict, status: str) -> dict:
    """Labels that DESCRIBE a record's source and review state. They never raise a rank, change a status or promote anything."""
    payload = envelope["payload"]
    src = source_view(payload)
    labels = []
    fidelity = source_fidelity(src)
    if fidelity in _FIDELITY_TEXT:
        labels.append(_FIDELITY_TEXT[fidelity])
    if src is not None:
        if src["content_available"]:
            labels.append("content held" + (f" under licence {src['license']}" if src["license"] else " with NO stated licence"))
        elif src["content_sha256_declared"]:
            labels.append("digest declared; content bytes not held")
        else:
            labels.append("no content digest declared")
    labels.append(_STATUS_TEXT[status])
    if envelope["kind"] == "Problem":
        if payload.get("completeness") == "recorded":
            labels.append("recorded problem, not actionable: lacks acceptance criteria, falsifiers, next action or stop bounds")
        else:
            labels.append("declares the four actionability fields; the declaration itself is not verified")
        labels.append("problem kind: " + str(payload.get("problem_kind")))
    if envelope["kind"] == "Evidence":
        labels.append("evidence kind: " + str(payload.get("evidence_kind")) + " (a direction for or against is not inferred)")
    return {"source_fidelity": fidelity, "labels": labels, "promoted": False,
            "note": "Labels describe; ranking never uses status or labels."}


def _terms(query: str) -> list[str]:
    return re.findall(r"\w+", query.lower(), flags=re.UNICODE)[:MAX_TERMS]


def explain_match(envelope: dict, query: str, raw_query: str, exact_version: str | None) -> tuple[list[str], list[str], str | None]:
    """Why a record matched, computed from its own text. Explanatory only: ranking is computed in PostgreSQL."""
    if not query:
        return ["no query: every record within the filters"], [], None
    reasons, fields, snippet_source = [], [], None
    if exact_version and envelope["version"] == exact_version:
        reasons.append("exact version pin")
    if envelope["id"] == raw_query:
        reasons.append("exact record id")
    if envelope["source_uri"].lower() == query:
        reasons.append("exact source URI")
    title = str(envelope["payload"].get("title", "")).lower()
    if title and title == query:
        reasons.append("title equals the query")
    elif title and query in title:
        reasons.append("title contains the literal query")
    terms = _terms(query)
    for key, value in envelope["payload"].items():
        text = _text_of(value)
        if query in text:
            fields.append(key)
            reasons.append(f"literal text match in payload.{key}")
            snippet_source = snippet_source or (key, text, text.index(query), len(query))
        elif terms and all(t in text for t in terms):
            fields.append(key)
            reasons.append(f"all query terms found in payload.{key}: " + ", ".join(terms))
            first = min(text.index(t) for t in terms)
            snippet_source = snippet_source or (key, text, first, len(terms[0]))
        if len(fields) >= 5:
            break
    if envelope["id"].lower().find(query) >= 0 and "exact record id" not in reasons:
        reasons.append("record id contains the literal query")
    if not reasons:
        reasons.append("matched the full-text index on terms: " + (", ".join(terms) or query))
    snippet = None
    if snippet_source and not _unlicensed_available_content([envelope]):
        _, text, at, n = snippet_source
        lo, hi = max(0, at - SNIPPET_RADIUS), min(len(text), at + n + SNIPPET_RADIUS)
        snippet = ("…" if lo else "") + text[lo:hi] + ("…" if hi < len(text) else "")
    return reasons, fields, snippet


class SearchIndex:
    """``SearchIndex(store).search(...)``: lexical and exact discovery with the Store's own authorisation and visibility."""

    def __init__(self, store: Store):
        self.store = store

    def initialize(self) -> None:
        """Operator-only and idempotent: adds indexes over the existing tables. Run after Store.initialize()."""
        with self.store.connection() as c:
            c.execute(Path(__file__).with_name("search_schema.sql").read_text())

    def search(self, query: str = "", *, kinds: str | Sequence[str] | None = None, status: str | Sequence[str] | None = None,
               source: str | None = None, scope: str | None = None, context: str | None = None,
               include_history: bool = False, limit: int = 20, cursor: str = "", token: str | None = None) -> dict:
        if not isinstance(query, str) or len(query) > MAX_QUERY or "\x00" in query:
            raise FrontierError("Invalid bounded search parameters")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise FrontierError("Invalid bounded search parameters")
        kinds_t = _as_tuple(kinds, KINDS, "kind")
        status_t = _as_tuple(status, STATUSES, "review status")
        if source is not None and (not isinstance(source, str) or not 3 <= len(source) <= 200 or "\x00" in source):
            raise FrontierError("source must be 3..200 characters (a URI prefix)")
        if context is not None and (not isinstance(context, str) or not 1 <= len(context) <= 200 or "\x00" in context):
            raise FrontierError("context must be 1..200 characters")
        if scope is not None and scope not in ("public", "private") and not _IDENT.fullmatch(str(scope)):
            raise FrontierError("scope must be 'public', 'private' or a namespace identifier")
        if not isinstance(include_history, bool):
            raise FrontierError("include_history must be a boolean")
        m = None
        if cursor:
            m = _CURSOR.fullmatch(cursor) if isinstance(cursor, str) else None
            if m is None:
                raise FrontierError("Invalid cursor")
        raw = query.strip()
        q = raw.lower()
        exact_version = q if _HEX64.fullmatch(q) else None
        params_id = sha256(canonical({"q": q, "raw": raw, "k": kinds_t, "s": status_t, "src": (source or "").lower(), "sc": scope,
                                      "c": (context or "").lower(), "h": include_history}).encode()).hexdigest()[:8]
        if m and m["pid"] != params_id:
            raise FrontierError("Cursor belongs to a different query or filter set")
        with self.store.connection() as c:
            principal = self.store._read_principal(c, token)
            namespaces = principal["namespaces"] if principal else []
            args = {
                "q": q, "raw": raw, "exact_version": exact_version, "namespaces": Jsonb(namespaces),
                "heads_only": not include_history, "kinds": list(kinds_t) if kinds_t else None,
                "statuses": list(status_t) if status_t else None,
                "source_like": _like_prefix(source.lower()) if source else None,
                "scope": scope, "context": context.lower() if context else None,
                "c_score": int(m["score"]) if m else None, "c_version": m["version"] if m else None, "n": limit + 1,
            }
            rows = c.execute("""
                WITH tsq AS (SELECT websearch_to_tsquery('simple', %(q)s) AS q),
                cand AS (
                  SELECT v.version, v.envelope, s.status, (h.version IS NOT NULL) AS is_head,
                         ( GREATEST(
                              CASE WHEN %(exact_version)s::text IS NOT NULL AND v.version = %(exact_version)s THEN 9000 ELSE 0 END,
                              CASE WHEN %(raw)s <> '' AND v.record_id = %(raw)s THEN 8000 ELSE 0 END,
                              CASE WHEN %(q)s <> '' AND lower(v.source_uri) = %(q)s THEN 7000 ELSE 0 END,
                              CASE WHEN %(q)s <> '' AND lower(v.envelope #>> '{payload,title}') = %(q)s THEN 6000
                                   WHEN %(q)s <> '' AND position(%(q)s in lower(coalesce(v.envelope #>> '{payload,title}', ''))) > 0 THEN 5000
                                   ELSE 0 END,
                              CASE WHEN %(q)s <> '' AND position(%(q)s in v.search_text) > 0 THEN 4000 ELSE 0 END,
                              CASE WHEN %(q)s <> '' THEN 1000 ELSE 0 END )
                         + CASE WHEN %(q)s <> '' THEN LEAST(999, floor(1000 * ts_rank_cd(to_tsvector('simple', v.search_text), tsq.q, 1))::int)
                                ELSE 0 END ) AS score
                  FROM record_versions v
                  JOIN local_states s ON s.version = v.version
                  LEFT JOIN heads h ON h.version = v.version
                  CROSS JOIN tsq
                  WHERE (v.visibility = 'public' OR %(namespaces)s::jsonb ? v.namespace)
                    AND (NOT %(heads_only)s OR h.version IS NOT NULL OR (%(exact_version)s::text IS NOT NULL AND v.version = %(exact_version)s))
                    AND (%(kinds)s::text[] IS NULL OR v.kind = ANY(%(kinds)s))
                    AND (%(statuses)s::text[] IS NULL OR s.status = ANY(%(statuses)s))
                    AND (%(source_like)s::text IS NULL
                         OR lower(v.source_uri) LIKE %(source_like)s
                         OR lower(coalesce(v.envelope #>> '{payload,source,uri}', '')) LIKE %(source_like)s)
                    AND (%(scope)s::text IS NULL
                         OR (%(scope)s = 'public' AND v.visibility = 'public')
                         OR (%(scope)s = 'private' AND v.visibility = 'private')
                         OR (%(scope)s NOT IN ('public', 'private') AND v.namespace = %(scope)s))
                    AND (%(context)s::text IS NULL
                         OR position(%(context)s in lower(coalesce(v.envelope #>> '{payload,context}', ''))) > 0)
                    AND ( %(q)s = ''
                          OR v.version = %(exact_version)s
                          OR v.record_id = %(raw)s
                          OR lower(v.source_uri) = %(q)s
                          OR to_tsvector('simple', v.search_text) @@ tsq.q
                          OR position(%(q)s in v.search_text) > 0 )
                )
                SELECT version, envelope, status, is_head, score FROM cand
                WHERE (%(c_score)s::int IS NULL OR score < %(c_score)s OR (score = %(c_score)s AND version > %(c_version)s))
                ORDER BY score DESC, version ASC
                LIMIT %(n)s""", args).fetchall()
            page = rows[:limit]
            related = self._related(c, principal, [r["version"] for r in page])
            results = []
            for r in page:
                env = r["envelope"]
                reasons, fields, snippet = explain_match(env, q, raw, exact_version)
                src = source_view(env["payload"])
                rel = related[r["version"]]
                withheld = bool(_unlicensed_available_content([env]))
                results.append({
                    "ref": ref(env), "is_head": r["is_head"], "title": env["payload"].get("title", env["id"]),
                    "issuer": env["issuer"], "source_uri": env["source_uri"], "visibility": env["visibility"],
                    "local_status": r["status"], "score": r["score"],
                    "why_matched": reasons, "matched_fields": fields,
                    "snippet": None if withheld else snippet,
                    "snippet_withheld": "content asserted available with no stated licence" if withheld else None,
                    "source": src, "curation": curation_labels(env, r["status"]),
                    "disputes": {"local_status": r["status"], "disputing_reviews": rel["disputing_reviews"], "cited_evidence": rel["cited_evidence"],
                                 "diverging_versions": rel["diverging_versions"],
                                 "truncated": any(rel["truncation"][k] for k in ("disputing_reviews", "cited_evidence", "diverging_versions"))},
                    "evidence_references": rel["evidence_references"],
                    "reference_truncation": rel["truncation"],
                    "references_complete": not any(rel["truncation"].values()),
                })
            more = len(rows) > limit
            last = page[-1] if page else None
            return {"results": results,
                    "next_cursor": f"{last['score']}.{last['version']}.{params_id}" if more and last else None,
                    "search_kind": SEARCH_KIND, "ordering": "score descending, then version ascending (stable keyset cursor)",
                    "limit": limit, "heads_only": not include_history}

    def _related(self, c, principal, versions: list[str]) -> dict:
        """Explicit relations only: recorded disputing/rejecting reviews, the evidence those reviews cite, diverging imported
        versions, and Evidence records that target a result. Nothing is inferred from text or from the absence of a dispute.

        Every list is bounded PER RESULT (window functions; MAX_REFS_PER_RESULT + 1 rows fetched per result) so a crowded result
        can never starve another result of its references, and an omission is reported rather than silent: ``truncation[list]`` is
        true when more visible references exist than are returned, or when an upstream list that feeds it was itself cut.
        References the caller may not see are simply absent, with no flag (a flag would reveal that they exist)."""
        cap = MAX_REFS_PER_RESULT
        names = ("disputing_reviews", "cited_evidence", "diverging_versions", "evidence_references")
        out: dict = {v: {**{n: [] for n in names}, "truncation": {n: False for n in names}} for v in versions}
        if not versions:
            return out
        ns = Jsonb(principal["namespaces"] if principal else [])

        def add(version: str, name: str, item: dict):
            if len(out[version][name]) >= cap:
                out[version]["truncation"][name] = True
            else:
                out[version][name].append(item)

        reviews = c.execute("""SELECT target_version, assessment_version, decision, envelope FROM (
              SELECT r.target_version, r.assessment_version, r.decision, a.envelope,
                     row_number() OVER (PARTITION BY r.target_version ORDER BY r.assessment_version) AS rn
              FROM reviews r JOIN record_versions a ON a.version = r.assessment_version
              WHERE r.target_version = ANY(%s) AND r.decision IN ('disputed','rejected')
                AND (a.visibility = 'public' OR %s::jsonb ? a.namespace)) x
            WHERE rn <= %s ORDER BY target_version, assessment_version""", (versions, ns, cap + 1)).fetchall()
        by_assessment: dict[str, list[str]] = {}
        for r in reviews:
            before = len(out[r["target_version"]]["disputing_reviews"])
            add(r["target_version"], "disputing_reviews",
                {"assessment": ref(r["envelope"]), "decision": r["decision"],
                 "note": "recorded review receipt; an uploaded Assessment without a receipt is not counted"})
            if len(out[r["target_version"]]["disputing_reviews"]) > before:
                by_assessment.setdefault(r["assessment_version"], []).append(r["target_version"])
        for v in versions:  # the evidence cited by reviews that were cut off is incomplete too
            if out[v]["truncation"]["disputing_reviews"]:
                out[v]["truncation"]["cited_evidence"] = True
        if by_assessment:
            cited = c.execute("""SELECT source_version, envelope FROM (
                  SELECT e.source_version, ev.envelope, row_number() OVER (PARTITION BY e.source_version ORDER BY e.target_version) AS rn
                  FROM typed_edges e JOIN record_versions ev ON ev.version = e.target_version
                  WHERE e.source_version = ANY(%s) AND e.relation = 'review_evidence'
                    AND (ev.visibility = 'public' OR %s::jsonb ? ev.namespace)) x
                WHERE rn <= %s ORDER BY source_version, rn""", (list(by_assessment), ns, cap + 1)).fetchall()
            seen: dict[str, int] = {}
            for e in cited:
                seen[e["source_version"]] = seen.get(e["source_version"], 0) + 1
                for target in by_assessment[e["source_version"]]:
                    if seen[e["source_version"]] > cap:  # this one review cites more than the cap
                        out[target]["truncation"]["cited_evidence"] = True
                    else:
                        add(target, "cited_evidence",
                            {"evidence": ref(e["envelope"]), "cited_by_assessment": e["source_version"],
                             "evidence_kind": e["envelope"]["payload"].get("evidence_kind"),
                             "note": "cited by the disputing review; its direction is the review's, not inferred here"})
        forks = c.execute("""SELECT mine, other_env FROM (
              SELECT f.local_version AS mine, iv.envelope AS other_env,
                     row_number() OVER (PARTITION BY f.local_version ORDER BY f.imported_version) AS rn
              FROM forks f JOIN record_versions iv ON iv.version = f.imported_version
              WHERE f.local_version = ANY(%(v)s) AND (iv.visibility = 'public' OR %(ns)s::jsonb ? iv.namespace)
              UNION ALL
              SELECT f.imported_version, lv.envelope,
                     row_number() OVER (PARTITION BY f.imported_version ORDER BY f.local_version)
              FROM forks f JOIN record_versions lv ON lv.version = f.local_version
              WHERE f.imported_version = ANY(%(v)s) AND (lv.visibility = 'public' OR %(ns)s::jsonb ? lv.namespace)) x
            WHERE rn <= %(cap)s ORDER BY mine""", {"v": versions, "ns": ns, "cap": cap + 1}).fetchall()
        for f in forks:
            add(f["mine"], "diverging_versions", {"version": ref(f["other_env"]), "note": "a different version of the same record id is held as a fork"})
        evidence = c.execute("""SELECT target_version, envelope FROM (
              SELECT e.target_version, ev.envelope, row_number() OVER (PARTITION BY e.target_version ORDER BY e.source_version) AS rn
              FROM typed_edges e JOIN record_versions ev ON ev.version = e.source_version
              WHERE e.target_version = ANY(%s) AND e.relation = 'targets' AND ev.kind = 'Evidence'
                AND (ev.visibility = 'public' OR %s::jsonb ? ev.namespace)) x
            WHERE rn <= %s ORDER BY target_version, rn""", (versions, ns, cap + 1)).fetchall()
        for e in evidence:
            add(e["target_version"], "evidence_references",
                {"evidence": ref(e["envelope"]), "evidence_kind": e["envelope"]["payload"].get("evidence_kind"),
                 "source_fidelity": source_fidelity(source_view(e["envelope"]["payload"])),
                 "note": "targets this version; whether it supports or opposes is not inferred"})
        return out
