#!/usr/bin/env python3
"""Download go-basic.obo, the GOA human GAF and the HGNC protein-coding gene list into data/
(git-ignored), then query INDRA CoGEx (public MCP endpoint, execute_cypher) for each HGNC
gene's number of distinct INDRA statements and write data/indra_degree.tsv.
data/manifest.json records URL, retrieval time, byte size and SHA-256 of every file;
checksums.json (committed) is a copy of it.

Usage: python3 fetch.py
"""
import csv
import hashlib
import json
import os
import shutil
import time

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = {
    "go-basic.obo": "https://purl.obolibrary.org/obo/go/go-basic.obo",
    "goa_human.gaf.gz": "https://current.geneontology.org/annotations/goa_human.gaf.gz",
    "hgnc_protein_coding.tsv": "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/locus_types/gene_with_protein_product.txt",
}
INDRA_MCP = "https://discovery.indra.bio/mcp"
INDRA_QUERY = (
    "UNWIND $ids AS gid MATCH (a:BioEntity {id: gid}) "
    "OPTIONAL MATCH (a)-[r:indra_rel]-() "
    "RETURN gid AS id, count(DISTINCT r.stmt_hash) AS degree"
)
BATCH = 250


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def cypher(query, params):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "execute_cypher", "arguments": {"params": {
            "query": query, "parameters": params, "max_results": 10000, "limit": 10000,
            "timeout_ms": 120000, "validate_first": False}}}}
    for attempt in range(5):
        try:
            r = requests.post(INDRA_MCP, json=body, timeout=300,
                              headers={"Accept": "application/json, text/event-stream"})
            r.raise_for_status()
            res = r.json()["result"]
            payload = json.loads(res["content"][0]["text"])
            if res.get("isError") or "results" not in payload:
                raise RuntimeError(str(payload)[:500])
            return payload["results"]
        except Exception as e:  # noqa: BLE001
            print(f"  retry {attempt + 1}: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("INDRA query failed after retries")


def fetch_indra(manifest):
    out = os.path.join(DATA, "indra_degree.tsv")
    if not os.path.exists(out):
        with open(os.path.join(DATA, "hgnc_protein_coding.tsv")) as f:
            ids = [row["hgnc_id"].replace("HGNC:", "hgnc:") for row in csv.DictReader(f, delimiter="\t")
                   if row["status"] == "Approved"]
        started = now()
        rows = {}
        for i in range(0, len(ids), BATCH):
            for rec in cypher(INDRA_QUERY, {"ids": ids[i:i + BATCH]}):
                rows[rec["id"]] = rec["degree"]
            print(f"  INDRA {min(i + BATCH, len(ids))}/{len(ids)}")
        with open(out, "w") as f:
            f.write("hgnc_id\tindra_statements\n")
            for gid in ids:
                f.write(f"{gid}\t{rows.get(gid, '')}\n")
        manifest["indra_degree.tsv"] = {
            "download_url": INDRA_MCP, "query": INDRA_QUERY, "tool": "execute_cypher",
            "retrieved_at": started, "note": "empty degree = HGNC id not present as a BioEntity node"}
    manifest["indra_degree.tsv"].update(byte_size=os.path.getsize(out), sha256=sha256(out))


def main():
    os.makedirs(DATA, exist_ok=True)
    manifest_path = os.path.join(DATA, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {}
    for name, url in FILES.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            retrieved = now()
            with requests.get(url, stream=True, timeout=600,
                              headers={"User-Agent": "delphisci-claim-tests"}) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
                manifest[name] = {"download_url": url, "resolved_url": r.url, "retrieved_at": retrieved}
        manifest[name].update(byte_size=os.path.getsize(path), sha256=sha256(path))
    fetch_indra(manifest)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=1)
    shutil.copy(manifest_path, os.path.join(HERE, "checksums.json"))
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
