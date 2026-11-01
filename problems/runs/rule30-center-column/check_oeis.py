#!/usr/bin/env python3
"""Compare the packed center column with OEIS A051023.

Fetches (does not recall) the A051023 b-file (n=0..100000) and the 'data' field of the OEIS
JSON record, checks both against the packed column file given on the command line and prints
the SHA-256 of what was fetched.  Fetches are cached in $WORK (default /tmp/rule30-work).
"""
import hashlib, json, os, sys, urllib.request

WORK = os.environ.get("WORK", "/tmp/rule30-work")
os.makedirs(WORK, exist_ok=True)


def fetch(url, name):
    p = os.path.join(WORK, name)
    if not os.path.exists(p):
        req = urllib.request.Request(url, headers={"User-Agent": "delphisci-rule30-run"})
        open(p, "wb").write(urllib.request.urlopen(req, timeout=60).read())
    return open(p, "rb").read()


def main(packed):
    col = open(packed, "rb").read()
    def bit(t): return (col[t >> 3] >> (7 - (t & 7))) & 1
    bf = fetch("https://oeis.org/A051023/b051023.txt", "b051023.txt")
    rows = [l.split() for l in bf.decode().splitlines() if l.strip() and not l.startswith("#")]
    assert [int(r[0]) for r in rows] == list(range(len(rows)))
    assert len(rows) <= 8 * len(col), "column shorter than the b-file"
    bad = [int(n) for n, v in rows if bit(int(n)) != int(v)]
    assert bad == [], "b-file mismatch at %s" % bad[:5]
    js = json.loads(fetch("https://oeis.org/search?q=id:A051023&fmt=json", "a051023.json"))
    rec = js["results"][0] if isinstance(js, dict) else js[0]
    data = [int(x) for x in rec["data"].split(",")]
    assert all(bit(i) == v for i, v in enumerate(data)), "data field mismatch"
    print("OEIS A051023 b-file: %d terms match; data field: %d terms (%s...) match; b-file sha256 %s"
          % (len(rows), len(data), ",".join(map(str, data[:18])), hashlib.sha256(bf).hexdigest()))


if __name__ == "__main__":
    main(sys.argv[1])
