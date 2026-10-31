"""Relevance assessment of lexical vs vector vs hybrid discovery on ACTUAL public records, against frozen judged pairs.

    FRONTIER_SOURCE_DSN='host=... dbname=... user=...' python3 scripts/discovery_assess.py --judgments findings/discovery-judgments.json \\
        --namespace NS --out findings/discovery-assessment.json [--receipt findings/discovery-index-receipt.json]

Read-only on the source node: it SELECTs the public head records. It builds a PRIVATE temporary PostgreSQL cluster (own socket, deleted at the
end), copies those public rows into it, embeds them with the hosted embedding model through frontier.discovery, runs each judged query in the
three modes, and reports ranks and counts. The judgments are frozen before any run and are never edited by this script. Nothing is written to
the source node. Run inside the documented bounded systemd scope. No credential is printed or recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from frontier.discovery import Discovery, GeminiEmbedder, RECIPE  # noqa: E402
from frontier.store import Store  # noqa: E402

PG_BIN = os.environ.get("FRONTIER_PG_BIN", "/usr/lib/postgresql/16/bin")
MODES = ("lexical", "vector", "hybrid")


def start_cluster(tmp: Path) -> str:
    (tmp / "socket").mkdir()
    subprocess.run([f"{PG_BIN}/initdb", "-D", str(tmp / "data"), "--auth-local=trust", "--auth-host=reject", "--no-locale", "--encoding=UTF8"],
                   check=True, capture_output=True)
    subprocess.run([f"{PG_BIN}/pg_ctl", "-D", str(tmp / "data"), "-l", str(tmp / "pg.log"), "-o",
                    f"-k {tmp / 'socket'} -c listen_addresses='' -c max_connections=20 -c shared_buffers=64MB", "-w", "start"], check=True, capture_output=True)
    return f"host={tmp / 'socket'} dbname=postgres"


def stop_cluster(tmp: Path) -> None:
    subprocess.run([f"{PG_BIN}/pg_ctl", "-D", str(tmp / "data"), "-m", "immediate", "-w", "stop"], capture_output=True)


def copy_public_heads(source_dsn: str, store: Store) -> int:
    with psycopg.connect(source_dsn, row_factory=dict_row, connect_timeout=5) as src:
        rows = src.execute("""SELECT v.*, s.status, s.policy_version, s.submitter_actor, s.submitter_operator, s.updated_at AS s_updated FROM record_versions v
            JOIN heads h ON h.version = v.version JOIN local_states s ON s.version = v.version WHERE v.visibility = 'public' ORDER BY v.version""").fetchall()
    with store.connection() as c:
        for r in rows:
            c.execute("""INSERT INTO record_versions(version,namespace,kind,record_id,issuer,source_uri,visibility,predecessor,created_at,envelope,search_text)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", (r["version"], r["namespace"], r["kind"], r["record_id"], r["issuer"], r["source_uri"], r["visibility"],
                                                                 r["predecessor"], r["created_at"], Jsonb(r["envelope"]), r["search_text"]))
            c.execute("INSERT INTO local_states(version,status,policy_version,submitter_actor,submitter_operator,updated_at) VALUES (%s,%s,%s,%s,%s,%s)",
                      (r["version"], r["status"], r["policy_version"], r["submitter_actor"], r["submitter_operator"], r["s_updated"]))
            c.execute("INSERT INTO heads VALUES (%s,%s,%s,%s)", (r["namespace"], r["kind"], r["record_id"], r["version"]))
    return len(rows)


def rank_of(items: list[dict], target: dict) -> int | None:
    for i, it in enumerate(items, 1):
        if it["ref"]["version"] == target["version"]:
            return i
    return None


def metrics(ranks: list[int | None]) -> dict:
    n = len(ranks)
    at = lambda k: sum(1 for r in ranks if r is not None and r <= k)  # noqa: E731
    return {"n": n, "success_at_1": at(1), "success_at_5": at(5), "success_at_10": at(10), "found_in_top_50": sum(1 for r in ranks if r is not None),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 4) if n else None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judgments", required=True)
    ap.add_argument("--namespace", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--receipt")
    ap.add_argument("--max-requests", type=int, default=120)
    a = ap.parse_args(argv)
    judg_bytes = Path(a.judgments).read_bytes()
    judg = json.loads(judg_bytes)
    source = os.environ["FRONTIER_SOURCE_DSN"]
    tmp = Path(tempfile.mkdtemp(prefix="frontier-assess."))
    tmp.chmod(0o700)
    try:
        dsn = start_cluster(tmp)
        store = Store(dsn, a.namespace, "public")
        store.initialize()
        copied = copy_public_heads(source, store)
        emb = GeminiEmbedder()
        d = Discovery(store, emb, live_query_limit=1000)
        d.initialize()
        t0 = time.time()
        receipt = d.index(max_requests=a.max_requests)
        receipt["index_seconds"] = round(time.time() - t0, 1)
        receipt["source_public_heads_copied"] = copied
        receipt["environment"] = "private temporary PostgreSQL 16 cluster with pgvector, deleted after the run; the source node was only read"
        if a.receipt:
            Path(a.receipt).write_text(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
        per_query, by_mode = [], {m: [] for m in MODES}
        for pair in judg["pairs"]:
            target = pair["relevant"][0]
            row = {"qid": pair["qid"], "style": pair["style"], "query": pair["query"], "target": target["id"], "ranks": {}, "mode_used": {}}
            for m in MODES:
                res = d.search(pair["query"], limit=50, mode=m)
                r = rank_of(res["items"], target)
                row["ranks"][m] = r
                row["mode_used"][m] = res["mode"]
                by_mode[m].append((pair["style"], r))
            per_query.append(row)
        summary = {m: {"all": metrics([r for _, r in v]), **{s: metrics([r for st, r in v if st == s]) for s in ("paraphrase", "keyword")}} for m, v in by_mode.items()}
        paired = {}
        for other in ("lexical", "vector"):
            w = l = t = 0
            for row in per_query:
                h, o = row["ranks"]["hybrid"] or 10 ** 6, row["ranks"][other] or 10 ** 6
                if h < o:
                    w += 1
                elif h > o:
                    l += 1
                else:
                    t += 1
            paired[f"hybrid_vs_{other}"] = {"hybrid_better_rank": w, "hybrid_worse_rank": l, "same_rank_or_both_absent": t}
        out = {"what": "Relevance assessment on actual public records against frozen judged pairs; lower-bound, single-judge, known-item.",
               "judgments_file": a.judgments, "judgments_sha256": sha256(judg_bytes).hexdigest(), "pairs": len(judg["pairs"]),
               "embedding": {"provider": emb.provider, "model": emb.model, "dimensions": emb.dimensions, "text_recipe": RECIPE},
               "index": {k: receipt[k] for k in ("planned", "embedded", "failed", "requests", "coverage", "manifest_sha256", "truncated_inputs")},
               "metrics_by_mode": summary, "paired_hybrid_comparisons": paired, "per_query": per_query,
               "mode_fallbacks": sorted({(r["qid"], m, u) for r in per_query for m, u in r["mode_used"].items() if u != m}),
               "metric_notes": "success_at_k = number of queries whose judged record appears in the top k; mrr = mean reciprocal rank (0 when absent from the top 50). Rankings use limit 50. No tuning was done on these pairs; weights are RRF k=60 as shipped.",
               "ran_at": datetime.now(timezone.utc).isoformat()}
        Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
        print(json.dumps({"index": out["index"]["coverage"]["documents_indexed"], "planned": out["index"]["coverage"]["documents_planned"], "failed": out["index"]["failed"],
                          "metrics": {m: summary[m]["all"] for m in MODES}}))
        return 0
    finally:
        stop_cluster(tmp)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
