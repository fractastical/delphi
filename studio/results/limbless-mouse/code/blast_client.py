#!/usr/bin/env python3
"""Minimal, polite NCBI BLAST URL-API client.

Submits one search, polls until done, writes the raw JSON2 / text output.
Everything it returns is recorded verbatim so the retrieval can be re-run.
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://blast.ncbi.nlm.nih.gov/Blast.cgi"
UA = "zrs-comparative-analysis/1.0 (hackathon artifact; contact via MorphoSwarm)"


def _get(params, timeout=180):
    url = BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace"), url


def submit(query, database, entrez_query=None, program="blastn", task="discoMegablast",
           hitlist=20, evalue=1e-5):
    p = {
        "CMD": "Put",
        "PROGRAM": program,
        "DATABASE": database,
        "QUERY": query,
        "HITLIST_SIZE": hitlist,
        "EXPECT": evalue,
        "FORMAT_TYPE": "JSON2",
    }
    if task:
        p["MEGABLAST" if task == "megablast" else "BLAST_PROGRAMS"] = "on" if task == "megablast" else task
    if entrez_query:
        p["ENTREZ_QUERY"] = entrez_query
    st, body, url = _get(p)
    rid = rtoe = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith("RID = "):
            rid = line[6:].strip()
        if line.startswith("RTOE = "):
            rtoe = line[7:].strip()
    return rid, rtoe, st, body


def poll(rid, max_wait=900, interval=20):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        time.sleep(interval)
        st, body, _ = _get({"CMD": "Get", "RID": rid, "FORMAT_OBJECT": "SearchInfo"})
        if "Status=READY" in body:
            return "READY" if "ThereAreHits=yes" in body else "NO_HITS"
        if "Status=FAILED" in body or "Status=UNKNOWN" in body:
            return "FAILED"
        print(f"  ... {rid} waiting {int(time.time()-t0)}s", flush=True)
    return "TIMEOUT"


def fetch(rid, fmt="JSON2"):
    st, body, url = _get({"CMD": "Get", "RID": rid, "FORMAT_TYPE": fmt}, timeout=300)
    return st, body, url


if __name__ == "__main__":
    qfile, database, entrez, out = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    seq = open(qfile).read()
    entrez = None if entrez in ("-", "none") else entrez
    ts = datetime.now(timezone.utc).isoformat()
    rid, rtoe, st, body = submit(seq, database, entrez)
    print(f"submitted at {ts}: RID={rid} RTOE={rtoe} http={st} db={database} entrez={entrez}", flush=True)
    if not rid:
        print("NO RID. Response head:\n" + body[:2000])
        sys.exit(2)
    status = poll(rid)
    print("status:", status, flush=True)
    if status in ("READY", "NO_HITS"):
        st2, out_body, url2 = fetch(rid)
        with open(out, "w") as fh:
            fh.write(out_body)
        meta = {"rid": rid, "database": database, "entrez_query": entrez,
                "submitted_utc": ts, "status": status, "result_url": url2,
                "http_status": st2, "bytes": len(out_body)}
        with open(out + ".meta.json", "w") as fh:
            json.dump(meta, fh, indent=2)
        print(json.dumps(meta, indent=2))
    else:
        sys.exit(3)
