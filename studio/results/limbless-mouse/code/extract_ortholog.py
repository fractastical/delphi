#!/usr/bin/env python3
"""Extract a ZRS-orthologous window from a BLAST HSP and fetch it from NCBI.

Given the best HSP of the mouse 1324 bp ZRS against a subject accession, project
the FULL query interval (1..query_len) onto subject coordinates by extending the
HSP ends by the unaligned query overhangs, then efetch that window.

Every retrieval records: accession, coordinates, strand, exact URL, HTTP status,
byte count, sha256 and a UTC timestamp.
"""
import hashlib
import json
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
UA = {"User-Agent": "zrs-comparative-analysis/1.0"}


def project(qlen, qf, qt, sf, st, strand):
    """Return (seq_start, seq_stop, efetch_strand) covering query 1..qlen."""
    if strand == "Plus":
        lo = sf - (qf - 1)
        hi = st + (qlen - qt)
        return max(1, lo), hi, 1
    # Minus: hit_from > hit_to; query runs antiparallel to subject
    hi = sf + (qf - 1)
    lo = st - (qlen - qt)
    return max(1, lo), hi, 2


def efetch_window(acc, start, stop, strand, retries=3):
    params = {"db": "nuccore", "id": acc, "rettype": "fasta", "retmode": "text",
              "seq_start": start, "seq_stop": stop, "strand": strand}
    url = EFETCH + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                status, raw = r.status, r.read()
            break
        except Exception as e:  # transient NCBI 429/500
            last = e
            time.sleep(3 * (attempt + 1))
    else:
        raise RuntimeError(f"efetch failed for {acc}: {last}")
    text = raw.decode("utf-8", "replace")
    header = text.splitlines()[0] if text.startswith(">") else ""
    seq = "".join(l.strip() for l in text.splitlines() if not l.startswith(">")).upper()
    return {
        "accession": acc, "url": url, "http_status": status,
        "bytes": len(raw), "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "coords": f"{acc}:{start}-{stop}", "seq_start": start, "seq_stop": stop,
        "efetch_strand": "plus" if strand == 1 else "minus",
        "defline": header, "length": len(seq),
        "sha256": hashlib.sha256(seq.encode()).hexdigest(), "sequence": seq,
    }


if __name__ == "__main__":
    spec = json.load(open(sys.argv[1]))
    out = {}
    for name, s in spec.items():
        lo, hi, strand = project(s["qlen"], s["qf"], s["qt"], s["sf"], s["st"], s["strand"])
        rec = efetch_window(s["acc"], lo, hi, strand)
        rec.update(species=s["species"], common_name=s["common"], assembly=s.get("assembly"),
                   blast_pid=s.get("pid"), blast_alen=s.get("alen"), blast_evalue=s.get("evalue"))
        out[name] = rec
        print(f"{name:14s} {rec['accession']:16s} {rec['coords']:34s} "
              f"{rec['efetch_strand']:5s} len={rec['length']:5d} http={rec['http_status']} "
              f"sha={rec['sha256'][:12]}")
        time.sleep(0.4)
    json.dump(out, open(sys.argv[2], "w"), indent=2)
    print("wrote", sys.argv[2])
