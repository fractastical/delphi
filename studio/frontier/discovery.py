"""Hybrid lexical + vector discovery over the public Frontier records and the declared metadata of their artifacts.

Real embeddings: a hosted embedding model (see GeminiEmbedder) embeds a fixed, versioned text recipe of every PUBLIC record version
and every declared artifact (metadata only; bytes are never fetched). Vectors live in PostgreSQL (pgvector) next to the records, pinned to
the immutable record version, the sha256 of the exact embedded text, the provider, model, dimensions and recipe. Private records are never
embedded. No credential appears in any output.

Search is hybrid by reciprocal-rank fusion (RRF) of two independent rankings: the existing lexical SearchIndex and pgvector cosine
similarity. Relevance here means retrieval similarity to the query. It is NOT truth, quality or epistemic confidence, and every result
says so. When vectors or the provider are unavailable the result is the lexical ranking, labelled, with `unavailable_reason`.

    Discovery(store, embedder).search(query, kind=None, limit=12, mode="hybrid") -> dict      (see `search` for the contract)
    FRONTIER_DSN=... python -m frontier.discovery index|status|search --namespace NS [--schema S]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import urllib.error
import urllib.request
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from hashlib import sha256
from math import sqrt
from pathlib import Path
from typing import Any, Iterable, Protocol, Sequence

from psycopg import sql
from psycopg.errors import InsufficientPrivilege, UndefinedFile, UndefinedTable, FeatureNotSupported

from .artifacts import ArtifactIndex
from .models import KINDS, canonical
from .search import SearchIndex
from .store import FrontierError, Store

RECIPE = "frontier-discovery-text-v1"
DIMENSIONS = 768
MAX_TEXT_CHARS = 6000
MAX_QUERY = 200
RRF_K = 60
CANDIDATES = 50
MODES = ("lexical", "vector", "hybrid")
RELEVANCE_NOTE = "Relevance ranks retrieval similarity to the query. It is not truth, quality or epistemic confidence; review status is shown separately."
DEFAULT_EXCLUDED_KIND = "Event"  # indexed, but operational log lines are left out of results unless kind='Event' is asked for


class Unavailable(Exception):
    """Vectors or the embedding provider cannot be used right now; carries a short, credential-free reason."""


# ----------------------------------------------------------------------------------------------------------------------
# The text recipe: what exactly is embedded. Deterministic, versioned, bounded, public fields only.
# ----------------------------------------------------------------------------------------------------------------------
_FIELDS: dict[str, tuple[str, ...]] = {
    "Problem": ("title", "question", "known_state", "problem_kind", "novelty_status", "data_access", "required_capabilities", "downstream_uses", "context_tags", "scales"),
    "Claim": ("title", "statement", "context", "assumptions", "limitations"),
    "Evidence": ("method", "context", "evidence_kind", "relation", "assumptions", "limitations", "uncertainty"),
    "Assessment": ("decision", "independence_rationale", "limitations"),
    "Action": ("title", "acceptance_criteria", "required_capabilities", "cost_stop_bounds"),
    "Actor": ("display_name", "capabilities"),
    "ResourceOffer": ("capability", "unit", "restrictions", "terms"),
    "Interest": ("signal", "explanation"),
    "Event": ("event_type",),
}


def _flat(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "; ".join(x for x in (_flat(v) for v in value) if x)
    if isinstance(value, dict):
        return "; ".join(f"{k}: {t}" for k, v in value.items() if (t := _flat(v)))
    return str(value)


def _bound(text: str) -> tuple[str, bool]:
    return (text, False) if len(text) <= MAX_TEXT_CHARS else (text[:MAX_TEXT_CHARS], True)


def record_doc(envelope: dict) -> dict:
    """Title and embedded text for one record version. Missing fields are skipped, never invented."""
    kind, p = envelope["kind"], envelope["payload"]
    title = _flat(p.get("title")) or _flat(p.get("display_name")) or envelope["id"]
    lines = [f"{kind}: {title}"]
    for f in _FIELDS.get(kind, ()):
        if f == "title":
            continue
        t = _flat(p.get(f))
        if t:
            lines.append(f"{f.replace('_', ' ')}: {t}")
    if kind == "Action" and isinstance(p.get("proposal"), dict):
        for f in ("method", "expected_information", "decision_context"):
            t = _flat(p["proposal"].get(f))
            if t:
                lines.append(f"{f.replace('_', ' ')}: {t}")
    if kind == "Event":
        tgt = p.get("target") or {}
        lines.append(f"about {tgt.get('kind', '')} {tgt.get('id', '')}")
    if len(lines) == 1:  # a kind without recipe fields: fall back to its string leaves, still bounded
        lines.append(_flat({k: v for k, v in p.items() if isinstance(v, (str, list))}))
    text, truncated = _bound("\n".join(lines))
    return {"title": title[:300], "text": text, "truncated": truncated}


def artifact_doc(envelope: dict, art: dict) -> dict:
    """Declared artifact metadata plus the context of the Evidence that declares it. The artifact bytes are never read."""
    p = envelope["payload"]
    title = _flat(art.get("title")) or art.get("sha256", "")[:12]
    lines = [f"Artifact ({art.get('role')}): {title}", f"media type: {art.get('media_type')}", f"availability: {art.get('availability')} (declared)",
             f"declared by Evidence {envelope['id']}: {_flat(p.get('context'))}", f"method: {_flat(p.get('method'))}"]
    text, truncated = _bound("\n".join(x for x in lines if x.split(": ", 1)[-1]))
    return {"title": title[:300], "text": text, "truncated": truncated}


def input_hash(text: str) -> str:
    return sha256(text.encode()).hexdigest()


# ----------------------------------------------------------------------------------------------------------------------
# Embedding providers
# ----------------------------------------------------------------------------------------------------------------------
class Embedder(Protocol):
    provider: str
    model: str
    dimensions: int

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


def _unit(v: Sequence[float]) -> list[float]:
    n = sqrt(sum(x * x for x in v))
    if n == 0:
        raise Unavailable("provider returned a zero vector")
    return [x / n for x in v]


class GeminiEmbedder:
    """Google Generative Language API embeddings (public hosted). The key is read in process from the environment variable GEMINI_API_KEY or
    from an env file (default ~/.config/morphoswarm/gemini.env, or FRONTIER_GEMINI_ENV_FILE), goes only into the x-goog-api-key header, and
    is never logged. Truncated (768 of 3072) outputs are not unit length, so every vector is L2-normalised here."""

    provider = "google-generative-language"

    def __init__(self, model: str = "gemini-embedding-001", dimensions: int = DIMENSIONS, timeout: float = 15.0, env_file: str | None = None):
        self.model, self.dimensions, self.timeout, self._env_file = model, dimensions, timeout, env_file
        self.requests = 0

    def _key(self) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            path = Path(self._env_file or os.environ.get("FRONTIER_GEMINI_ENV_FILE") or Path.home() / ".config/morphoswarm/gemini.env")
            try:
                for line in path.read_text().splitlines():
                    m = re.match(r"^GEMINI_API_KEY=(.*)$", line.strip())
                    if m:
                        key = m.group(1).strip().strip("\"'")
            except OSError:
                pass
        if not key:
            raise Unavailable("no embedding credential is configured for this process")
        return key

    def _post(self, method: str, body: dict) -> dict:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:{method}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "x-goog-api-key": self._key(), "User-Agent": "delphi-frontier-discovery/1"})
        self.requests += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise Unavailable(f"embedding provider answered HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise Unavailable("embedding provider unreachable or timed out") from None

    def _req(self, text: str, task: str) -> dict:
        return {"model": f"models/{self.model}", "content": {"parts": [{"text": text}]}, "taskType": task, "outputDimensionality": self.dimensions}

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        out = self._post("batchEmbedContents", {"requests": [self._req(t, "RETRIEVAL_DOCUMENT") for t in texts]})
        vecs = [e["values"] for e in out.get("embeddings", [])]
        if len(vecs) != len(texts) or any(len(v) != self.dimensions for v in vecs):
            raise Unavailable("embedding provider returned an unexpected shape")
        return [_unit(v) for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        out = self._post("embedContent", self._req(text, "RETRIEVAL_QUERY"))
        v = (out.get("embedding") or {}).get("values") or []
        if len(v) != self.dimensions:
            raise Unavailable("embedding provider returned an unexpected shape")
        return _unit(v)


def vec_literal(v: Sequence[float]) -> str:
    return "[" + ",".join(f"{x:.8g}" for x in v) + "]"


# ----------------------------------------------------------------------------------------------------------------------
# Discovery
# ----------------------------------------------------------------------------------------------------------------------
class Discovery:
    def __init__(self, store: Store, embedder: Embedder | None = None, *, query_timeout: float = 8.0, live_query_limit: int = 20, window_seconds: int = 60,
                 lru_size: int = 256):
        self.store, self.embedder = store, embedder
        self.lexical = SearchIndex(store)
        self.artifacts = ArtifactIndex(store)
        self.query_timeout, self.live_query_limit, self.window = query_timeout, live_query_limit, window_seconds
        self._lru: OrderedDict[str, list[float]] = OrderedDict()
        self._calls: list[float] = []
        self._lock = threading.Lock()
        self.lru_size = lru_size
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="discovery")

    # -- connections ---------------------------------------------------------------------------------------------
    def _conn(self):
        """A store connection whose search_path also includes the schema that holds the vector extension."""
        cm = self.store.connection()
        c = cm.__enter__()
        try:
            row = c.execute("SELECT e.extnamespace::regnamespace::text AS s FROM pg_extension e WHERE e.extname='vector'").fetchone()
            if row:
                c.execute(sql.SQL("SET search_path TO {}, {}, pg_catalog").format(sql.Identifier(self.store.schema), sql.SQL(row["s"])))
        except BaseException:
            cm.__exit__(*sys.exc_info())
            raise
        return c, cm

    def _with_conn(self, fn):
        c, cm = self._conn()
        try:
            return fn(c)
        finally:
            cm.__exit__(None, None, None)

    def initialize(self) -> None:
        """Operator-only and idempotent. Needs the pgvector extension: creating it requires a superuser, so if it is absent and this role cannot
        create it, an Unavailable error names exactly what to run."""
        def run(c):
            if not c.execute("SELECT 1 FROM pg_extension WHERE extname='vector'").fetchone():
                try:
                    c.execute("CREATE EXTENSION IF NOT EXISTS vector SCHEMA public")
                except (InsufficientPrivilege, FeatureNotSupported, UndefinedFile) as e:
                    raise Unavailable("the pgvector extension is not installed and this role cannot create it; a superuser must run: CREATE EXTENSION IF NOT EXISTS vector;") from e
                row = c.execute("SELECT e.extnamespace::regnamespace::text AS s FROM pg_extension e WHERE e.extname='vector'").fetchone()
                c.execute(sql.SQL("SET search_path TO {}, {}, pg_catalog").format(sql.Identifier(self.store.schema), sql.SQL(row["s"])))
            c.execute((Path(__file__).with_name("vector_schema.sql")).read_text())
        self._with_conn(run)

    # -- indexing --------------------------------------------------------------------------------------------------
    def _candidates(self, c, kinds: Iterable[str] | None, after: str, n: int) -> list[dict]:
        return c.execute("""SELECT v.version, v.namespace, v.kind, v.record_id, v.envelope FROM record_versions v JOIN heads h ON h.version=v.version
            WHERE v.visibility='public' AND v.version > %s AND (%s::text[] IS NULL OR v.kind = ANY(%s)) ORDER BY v.version LIMIT %s""",
                         (after, list(kinds) if kinds else None, list(kinds) if kinds else None, n)).fetchall()

    def plan(self, kinds: Iterable[str] | None = None) -> list[dict]:
        """Every document that SHOULD exist for the current public heads, with its exact text hash. Pure read."""
        docs: list[dict] = []

        def run(c):
            after = ""
            while True:
                rows = self._candidates(c, kinds, after, 500)
                if not rows:
                    return
                for r in rows:
                    env = r["envelope"]
                    d = record_doc(env)
                    docs.append({"doc_id": f"record:{r['version']}", "doc_type": "record", "version": r["version"], "namespace": r["namespace"], "kind": r["kind"],
                                 "record_id": r["record_id"], "artifact_sha256": None, "artifact_role": None, **d, "input_sha256": input_hash(d["text"])})
                    if r["kind"] == "Evidence":
                        for a in env["payload"].get("artifacts", []):
                            ad = artifact_doc(env, a)
                            docs.append({"doc_id": f"artifact:{r['version']}:{a['sha256']}:{a['role']}", "doc_type": "artifact", "version": r["version"],
                                         "namespace": r["namespace"], "kind": r["kind"], "record_id": r["record_id"], "artifact_sha256": a["sha256"],
                                         "artifact_role": a["role"], **ad, "input_sha256": input_hash(ad["text"])})
                after = rows[-1]["version"]
        self._with_conn(run)
        return docs

    def index(self, kinds: Iterable[str] | None = None, *, max_requests: int = 100, batch: int = 50, dry_run: bool = False, workers: int = 4) -> dict:
        """Embed every planned document whose (doc_id, input hash, model, dimensions, recipe) is not already stored. Resumable and idempotent.
        Bounded by max_requests provider calls. Failures are recorded per document; coverage is reported as measured."""
        if self.embedder is None:
            raise Unavailable("no embedder configured")
        run_id = uuid.uuid4().hex
        started = datetime.now(timezone.utc)
        planned = self.plan(kinds)

        def have(c):
            return {r["doc_id"]: r["input_sha256"] for r in c.execute(
                "SELECT doc_id, input_sha256 FROM discovery_documents WHERE model=%s AND dimensions=%s AND text_recipe=%s",
                (self.embedder.model, self.embedder.dimensions, RECIPE)).fetchall()}
        existing = self._with_conn(have)
        todo = [d for d in planned if existing.get(d["doc_id"]) != d["input_sha256"]]
        summary = {"run_id": run_id, "provider": self.embedder.provider, "model": self.embedder.model, "dimensions": self.embedder.dimensions, "text_recipe": RECIPE,
                   "planned": len(planned), "already_current": len(planned) - len(todo), "to_embed": len(todo), "requests": 0, "embedded": 0, "failed": 0,
                   "truncated_inputs": sum(1 for d in planned if d["truncated"]), "dry_run": dry_run}
        failures: list[dict] = []
        if dry_run:
            return self._finish(run_id, started, summary, planned, failures, write=False)
        chunks = [todo[i:i + batch] for i in range(0, len(todo), batch)]
        allowed, over = chunks[:max_requests], chunks[max_requests:]
        for chunk in over:  # beyond the request budget: reported, never silently dropped
            for d in chunk:
                failures.append({"doc_id": d["doc_id"], "error_class": "request_budget", "message": f"max_requests={max_requests} reached before this document"})
        requests = len(allowed)
        # The provider calls for different batches are independent: run up to `workers` at once. Database writes stay on this thread.
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            results = list(ex.map(self._embed_chunk, allowed))
        for chunk, (vecs, err) in zip(allowed, results):
            if err and len(chunk) > 1:  # isolate the bad document(s): bounded single-document retries share the same request budget
                vecs = []
                for d in chunk:
                    if requests >= max_requests:
                        failures.append({"doc_id": d["doc_id"], "error_class": "request_budget", "message": f"max_requests={max_requests} reached"})
                        vecs.append(None)
                        continue
                    v, e = self._embed_chunk([d])
                    requests += 1
                    vecs.append(v[0] if v else None)
                    if e:
                        failures.append({"doc_id": d["doc_id"], "error_class": e[0], "message": e[1]})
            elif err:
                failures.append({"doc_id": chunk[0]["doc_id"], "error_class": err[0], "message": err[1]})
                vecs = [None]
            self._store_vectors(chunk, vecs)
            summary["embedded"] += sum(1 for v in vecs if v is not None)
        summary["requests"] = requests
        summary["failed"] = len(failures)
        return self._finish(run_id, started, summary, planned, failures, write=True)

    def refresh(self, *, max_requests: int = 20, workers: int = 4, dry_run: bool = False) -> dict:
        """The recurring job: embed only records and artifacts that are new or changed since the last run, under a small request budget. An advisory
        lock makes overlapping runs harmless (the second one skips). Safe to run from a timer; a run with nothing new makes zero provider calls."""
        lock = int(sha256(b"frontier-discovery-refresh").hexdigest()[:8], 16) & 0x7FFFFFFF  # constant across processes

        def hold(c):
            return c.execute("SELECT pg_try_advisory_lock(%s) AS ok", (lock,)).fetchone()["ok"]
        c, cm = self._conn()
        try:
            if not hold(c):
                return {"skipped": "another refresh is running", "requests": 0}
            return self.index(max_requests=max_requests, workers=workers, dry_run=dry_run)
        finally:
            cm.__exit__(None, None, None)

    def _embed_chunk(self, chunk: list[dict]):
        delay = 1.0
        for attempt in range(3):
            try:
                return self.embedder.embed_documents([d["text"] for d in chunk]), None
            except Unavailable as e:
                msg = str(e)
                if "HTTP 429" in msg or "HTTP 5" in msg or "unreachable" in msg:
                    time.sleep(delay)
                    delay *= 2
                    continue
                return None, ("unavailable", msg[:200])
        return None, ("unavailable", msg[:200])

    def _store_vectors(self, chunk, vecs) -> None:
        def run(c):
            for d, v in zip(chunk, vecs):
                if v is None:
                    continue
                c.execute("""INSERT INTO discovery_documents(doc_id,doc_type,version,namespace,kind,record_id,artifact_sha256,artifact_role,title,input_text,input_sha256,
                    text_recipe,truncated,provider,model,dimensions,task_type,embedding) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)
                    ON CONFLICT (doc_id) DO UPDATE SET title=EXCLUDED.title,input_text=EXCLUDED.input_text,input_sha256=EXCLUDED.input_sha256,text_recipe=EXCLUDED.text_recipe,
                    truncated=EXCLUDED.truncated,provider=EXCLUDED.provider,model=EXCLUDED.model,dimensions=EXCLUDED.dimensions,task_type=EXCLUDED.task_type,
                    embedding=EXCLUDED.embedding,embedded_at=CURRENT_TIMESTAMP""",
                          (d["doc_id"], d["doc_type"], d["version"], d["namespace"], d["kind"], d["record_id"], d["artifact_sha256"], d["artifact_role"], d["title"],
                           d["text"], d["input_sha256"], RECIPE, d["truncated"], self.embedder.provider, self.embedder.model, self.embedder.dimensions,
                           "RETRIEVAL_DOCUMENT", vec_literal(v)))
        self._with_conn(run)

    def _finish(self, run_id, started, summary, planned, failures, write: bool) -> dict:
        by_kind: dict[str, dict] = {}

        def cover(c):
            have = {r["doc_id"] for r in c.execute("SELECT doc_id FROM discovery_documents WHERE model=%s AND dimensions=%s AND text_recipe=%s",
                                                   (self.embedder.model, self.embedder.dimensions, RECIPE)).fetchall()}
            return have
        have = self._with_conn(cover)
        for d in planned:
            k = by_kind.setdefault(f"{d['kind']}/{d['doc_type']}", {"planned": 0, "indexed": 0})
            k["planned"] += 1
            k["indexed"] += d["doc_id"] in have
        summary["coverage"] = {"by_kind": by_kind, "documents_planned": len(planned), "documents_indexed": sum(v["indexed"] for v in by_kind.values())}
        summary["manifest_sha256"] = sha256(canonical(sorted((d["doc_id"], d["input_sha256"]) for d in planned)).encode()).hexdigest()
        summary["failures"] = failures[:50]
        summary["failure_classes"] = {k: sum(1 for f in failures if f["error_class"] == k) for k in sorted({f["error_class"] for f in failures})}
        summary["started_at"], summary["finished_at"] = started.isoformat(), datetime.now(timezone.utc).isoformat()
        if write:
            def run(c):
                for f in failures:
                    c.execute("INSERT INTO discovery_failures(run_id,doc_id,error_class,message) VALUES (%s,%s,%s,%s)", (run_id, f["doc_id"], f["error_class"], f["message"]))
                c.execute("INSERT INTO discovery_runs(run_id,started_at,finished_at,provider,model,dimensions,text_recipe,requests,summary) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (run_id, started, datetime.now(timezone.utc), self.embedder.provider, self.embedder.model, self.embedder.dimensions, RECIPE,
                           summary["requests"], json.dumps(summary)))
            self._with_conn(run)
        return summary

    def index_info(self) -> dict:
        def run(c):
            if self.embedder is None:
                return {"model": None, "dimensions": None, "documents": 0, "updated_at": None}
            r = c.execute("SELECT count(*) AS n, max(embedded_at) AS u FROM discovery_documents WHERE model=%s AND dimensions=%s AND text_recipe=%s",
                          (self.embedder.model, self.embedder.dimensions, RECIPE)).fetchone()
            return {"model": self.embedder.model, "dimensions": self.embedder.dimensions, "documents": r["n"], "updated_at": r["u"].isoformat() if r["u"] else None,
                    "provider": self.embedder.provider, "text_recipe": RECIPE}
        try:
            return self._with_conn(run)
        except (UndefinedTable, Exception) as e:  # noqa: BLE001 - the index may not exist yet
            return {"model": getattr(self.embedder, "model", None), "dimensions": getattr(self.embedder, "dimensions", None), "documents": 0, "updated_at": None}

    # -- query embedding: cache, bounds, no unbounded calls ----------------------------------------------------------
    @staticmethod
    def _norm(q: str) -> str:
        return re.sub(r"\s+", " ", q.strip().lower())

    def _qhash(self, nq: str) -> str:
        e = self.embedder
        return sha256(canonical([nq, e.provider, e.model, e.dimensions, "RETRIEVAL_QUERY"]).encode()).hexdigest()

    def query_vector(self, query: str, cache_only: bool = False) -> list[float]:
        if self.embedder is None:
            raise Unavailable("no embedding provider is configured")
        nq = self._norm(query)
        h = self._qhash(nq)
        with self._lock:
            if h in self._lru:
                self._lru.move_to_end(h)
                return self._lru[h]

        def get(c):
            r = c.execute("UPDATE discovery_query_cache SET hits=hits+1 WHERE query_hash=%s RETURNING embedding::text AS e", (h,)).fetchone()
            return json.loads(r["e"]) if r else None
        try:
            cached = self._with_conn(get)
        except Exception:  # noqa: BLE001 - a missing cache table must not break search
            cached = None
        if cached is None:
            if cache_only:
                raise Unavailable("query not in the embedding cache (autocomplete never calls the provider)")
            now = time.monotonic()
            with self._lock:
                self._calls = [t for t in self._calls if now - t < self.window]
                if len(self._calls) >= self.live_query_limit:
                    raise Unavailable(f"query-embedding rate limit ({self.live_query_limit} per {self.window}s) reached")
                self._calls.append(now)
            result: dict = {}
            th = threading.Thread(target=lambda: result.update(v=self._safe_embed(nq)), daemon=True)
            th.start()
            th.join(self.query_timeout)
            if th.is_alive():
                raise Unavailable(f"query embedding exceeded the {self.query_timeout:g}s bound")
            if isinstance(result.get("v"), Unavailable):
                raise result["v"]
            cached = result["v"]

            def put(c):
                c.execute("INSERT INTO discovery_query_cache(query_hash,query_text,model,embedding) VALUES (%s,%s,%s,%s::vector) ON CONFLICT DO NOTHING",
                          (h, nq, self.embedder.model, vec_literal(cached)))
            try:
                self._with_conn(put)
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            self._lru[h] = cached
            while len(self._lru) > self.lru_size:
                self._lru.popitem(last=False)
        return cached

    def _safe_embed(self, nq: str):
        try:
            return self.embedder.embed_query(nq)
        except Unavailable as e:
            return e
        except Exception:  # noqa: BLE001
            return Unavailable("embedding provider failed")

    # -- search ------------------------------------------------------------------------------------------------------
    def search(self, query: str, kind: str | None = None, limit: int = 12, mode: str = "hybrid", cache_only: bool = False) -> dict:
        """Contract: {query, mode, items:[{type, ref:{namespace,kind,id,version}, artifact_sha256?, title, snippet, kind, local_status, score, score_kind,
        why_matched}], index:{model,dimensions,documents,updated_at}, relevance_note, unavailable_reason?}. `mode` in the result is the mode actually used."""
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY or "\x00" in query:
            raise FrontierError("query must be 1..200 characters")
        if kind is not None and kind not in KINDS:
            raise FrontierError("Unknown kind")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
            raise FrontierError("limit must be 1..50")
        if mode not in MODES:
            raise FrontierError("mode must be lexical, vector or hybrid")
        q = query.strip()
        reason = None
        vec_hits: list[dict] = []
        # The lexical ranking and the query embedding + vector search are independent: run them concurrently, so latency is the slower of the two.
        lex_future = self._pool.submit(self._lexical, q, kind) if mode in ("lexical", "hybrid") else None
        if mode in ("vector", "hybrid"):
            try:
                qv = self.query_vector(q, cache_only=cache_only)
                vec_hits = self._vector_hits(qv, kind)
                if not vec_hits and self.index_info()["documents"] == 0:
                    raise Unavailable("the vector index is empty; run: python -m frontier.discovery index")
            except Unavailable as e:
                reason = str(e)
            except Exception:  # noqa: BLE001 - e.g. the extension or tables are not installed
                reason = "vector index unavailable (pgvector extension or discovery tables not installed)"
        used = mode if reason is None else "lexical"
        lex_records, lex_artifacts = ([], [])
        if lex_future is not None:
            lex_records, lex_artifacts = lex_future.result()
        elif used == "lexical":  # requested vector mode that fell back
            lex_records, lex_artifacts = self._lexical(q, kind)
        items = self._fuse(used, lex_records, lex_artifacts, vec_hits, limit)
        out = {"query": q, "mode": used, "items": items, "index": self.index_info(), "relevance_note": RELEVANCE_NOTE}
        if reason:
            out["unavailable_reason"] = reason
            out["requested_mode"] = mode
        return out

    def _lexical(self, q: str, kind: str | None):
        kinds = [kind] if kind else [k for k in KINDS if k != DEFAULT_EXCLUDED_KIND]
        recs = self.lexical.search(q, kinds=kinds, limit=CANDIDATES)["results"]
        arts: list[dict] = []
        if kind in (None, "Evidence"):
            try:
                arts = self.artifacts.search(q, limit=CANDIDATES)["items"]
            except FrontierError:
                arts = []
        return recs, arts

    def _vector_hits(self, qv: list[float], kind: str | None) -> list[dict]:
        def run(c):
            return c.execute("""SELECT d.doc_id, d.doc_type, d.version, d.namespace, d.kind, d.record_id, d.artifact_sha256, d.artifact_role, d.title, d.input_text,
                       1 - (d.embedding <=> %s::vector) AS cosine, s.status
                FROM discovery_documents d JOIN heads h ON h.version = d.version JOIN record_versions v ON v.version = d.version JOIN local_states s ON s.version = d.version
                WHERE v.visibility = 'public' AND d.model = %s AND d.dimensions = %s AND d.text_recipe = %s
                  AND ((%s::text IS NULL AND d.kind <> %s) OR d.kind = %s)
                ORDER BY d.embedding <=> %s::vector, d.doc_id LIMIT %s""",
                             (vec_literal(qv), self.embedder.model, self.embedder.dimensions, RECIPE, kind, DEFAULT_EXCLUDED_KIND, kind, vec_literal(qv), CANDIDATES)).fetchall()
        return self._with_conn(run)

    @staticmethod
    def _snippet(text: str) -> str:
        t = re.sub(r"\s+", " ", text).strip()
        return t[:240] + ("…" if len(t) > 240 else "")

    def _fuse(self, used: str, lex_records: list[dict], lex_artifacts: list[dict], vec_hits: list[dict], limit: int) -> list[dict]:
        pool: dict[str, dict] = {}
        lex_rank: dict[str, int] = {}
        vec_rank: dict[str, int] = {}
        for i, r in enumerate(lex_records, 1):
            key = "record:" + r["ref"]["version"]
            lex_rank[key] = i
            pool[key] = {"type": "record", "ref": r["ref"], "title": r["title"], "snippet": r.get("snippet") or "", "kind": r["ref"]["kind"], "local_status": r["local_status"],
                         "lex_reasons": r["why_matched"]}
        for j, a in enumerate(lex_artifacts, len(lex_records) + 1):
            key = f"artifact:{a['evidence']['version']}:{a['artifact']['sha256']}:{a['artifact']['role']}"
            lex_rank[key] = j
            pool.setdefault(key, {"type": "artifact", "ref": a["evidence"], "artifact_sha256": a["artifact"]["sha256"], "title": a["artifact"]["title"],
                                  "snippet": self._snippet(a.get("context", "")), "kind": "Evidence", "local_status": a["local_status"],
                                  "lex_reasons": ["declared artifact metadata matched the query text"]})
        for i, d in enumerate(vec_hits, 1):
            key = d["doc_id"]
            vec_rank[key] = i
            ref = {"namespace": d["namespace"], "kind": d["kind"], "id": d["record_id"], "version": d["version"]}
            p = pool.setdefault(key, {"type": d["doc_type"], "ref": ref, "title": d["title"], "snippet": self._snippet(d["input_text"]), "kind": d["kind"],
                                      "local_status": d["status"], "lex_reasons": []})
            if d["doc_type"] == "artifact":
                p["artifact_sha256"] = d["artifact_sha256"]
            p["cosine"] = float(d["cosine"])
            if not p.get("snippet"):
                p["snippet"] = self._snippet(d["input_text"])
        scored = []
        for key, p in pool.items():
            if used == "hybrid":
                score = (1 / (RRF_K + lex_rank[key]) if key in lex_rank else 0.0) + (1 / (RRF_K + vec_rank[key]) if key in vec_rank else 0.0)
                kind_ = "rrf_k60_lexical_plus_vector"
            elif used == "vector":
                score, kind_ = p.get("cosine", 0.0), "cosine_similarity"
            else:
                score, kind_ = 1.0 / (RRF_K + lex_rank[key]), "lexical_rank_reciprocal"
            why = list(p["lex_reasons"])
            if key in lex_rank:
                why.append(f"lexical rank {lex_rank[key]}")
            if key in vec_rank:
                why.append(f"semantic: cosine {p['cosine']:.3f}, vector rank {vec_rank[key]}")
            if used == "vector" and key not in vec_rank:
                continue
            if used == "lexical" and key not in lex_rank:
                continue
            item = {k: v for k, v in p.items() if k not in ("lex_reasons", "cosine")}
            item.update(score=round(score, 6), score_kind=kind_, why_matched=why)
            scored.append((score, key, item))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [i for _, _, i in scored[:limit]]


# ----------------------------------------------------------------------------------------------------------------------
def search(store: Store, query: str, kind: str | None = None, limit: int = 12, mode: str = "hybrid", embedder: Embedder | None = None) -> dict:
    """Module-level convenience matching the requested contract: discovery.search(query, kind=None, limit=12, mode='hybrid')."""
    return Discovery(store, embedder).search(query, kind=kind, limit=limit, mode=mode)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Frontier hybrid discovery: index, status, search")
    ap.add_argument("command", choices=["init", "index", "refresh", "status", "search"])
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--schema", default="public")
    ap.add_argument("--kinds", nargs="*")
    ap.add_argument("--max-requests", type=int, default=None, help="provider-call budget (index: 100, refresh: 20)")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--workers", type=int, default=4, help="concurrent provider requests while indexing")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--receipt", help="write the JSON index receipt here (atomic)")
    ap.add_argument("--query")
    ap.add_argument("--mode", default="hybrid", choices=MODES)
    ap.add_argument("--kind")
    ap.add_argument("--limit", type=int, default=12)
    a = ap.parse_args(argv)
    store = Store(os.environ["FRONTIER_DSN"], a.namespace, a.schema)
    d = Discovery(store, GeminiEmbedder())
    try:
        if a.command == "init":
            d.initialize()
            print(json.dumps({"ok": True}))
        elif a.command == "status":
            print(json.dumps(d.index_info()))
        elif a.command == "search":
            print(json.dumps(d.search(a.query or "", kind=a.kind, limit=a.limit, mode=a.mode), indent=1))
        elif a.command == "refresh":
            d.initialize()
            r = d.refresh(max_requests=a.max_requests or 20, workers=a.workers, dry_run=a.dry_run)
            if a.receipt and "run_id" in r:
                with open(a.receipt, "a") as fh:
                    fh.write(json.dumps({k: r[k] for k in ("run_id", "started_at", "finished_at", "model", "dimensions", "planned", "already_current", "embedded", "failed", "requests")}) + "\n")
            print(json.dumps({k: r[k] for k in ("skipped", "run_id", "planned", "already_current", "to_embed", "requests", "embedded", "failed") if k in r}))
            return 2 if r.get("failed") else 0
        else:
            d.initialize()
            r = d.index(a.kinds, max_requests=a.max_requests or 100, batch=a.batch, dry_run=a.dry_run, workers=a.workers)
            if a.receipt:
                tmp = Path(a.receipt + ".tmp")
                tmp.write_text(json.dumps(r, indent=1, ensure_ascii=False) + "\n")
                os.replace(tmp, a.receipt)
            print(json.dumps({k: r[k] for k in ("run_id", "model", "dimensions", "planned", "already_current", "to_embed", "requests", "embedded", "failed", "coverage")}))
        return 0
    except Unavailable as e:
        print(json.dumps({"ok": False, "unavailable": str(e)}))
        return 3
    except FrontierError as e:
        print(json.dumps({"ok": False, "error": str(e)[:200]}))
        return 2
    except Exception as e:  # noqa: BLE001 - never print a traceback that could carry a connection string
        print(json.dumps({"ok": False, "error": type(e).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
