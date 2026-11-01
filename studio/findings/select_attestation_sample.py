"""Fix the 15-item attestation sample BEFORE any source is fetched.

Rule (declared here, applied mechanically, no human choice of items):
  key(item) = sha256("frontier-attestation-sample-v1|<slug>|<attestation index>|<register sha256>")
  3 attestations with stance "settled"  -> lowest keys, distinct problems and distinct sources
  1 attestation with a url (no pmcid)   -> lowest key (the Wolfram rule 30 page)
  11 attestations with stance "open" and a pmcid -> lowest keys, distinct problems and distinct sources, not already chosen
Output: findings/attestation-sample-15.json. This is a demonstration sample, not a random sample of the 250 and not a verification of them.
"""
import json
import sys
from hashlib import sha256
from pathlib import Path

import yaml

REGISTER = Path(sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/git/morphoswarm/data/problems/register.yaml")
OUT = Path(__file__).with_name("attestation-sample-15.json")
reg_sha = sha256(REGISTER.read_bytes()).hexdigest()
problems = yaml.safe_load(REGISTER.read_text())["problems"]
items = []
for p in problems:
    for i, a in enumerate(p["attestations"]):
        src = a.get("pmcid") or a.get("url")
        items.append({"slug": p["slug"], "index": i, "source": src, "stance": a["stance"], "kind": a["kind"], "pmcid": a.get("pmcid"),
                      "url": a.get("url"), "locator": a["locator"], "quote": a["quote"], "question": p["statement"],
                      "key": sha256(f"frontier-attestation-sample-v1|{p['slug']}|{i}|{reg_sha}".encode()).hexdigest()})
items.sort(key=lambda x: x["key"])
chosen, used_p, used_s = [], set(), set()


def take(pred, n, stratum):
    got = 0
    for x in items:
        if got == n:
            break
        if pred(x) and x["slug"] not in used_p and x["source"] not in used_s:
            chosen.append({**x, "stratum": stratum}); used_p.add(x["slug"]); used_s.add(x["source"]); got += 1
    assert got == n, (stratum, got)


take(lambda x: x["stance"] == "settled", 3, "settled")
take(lambda x: x["url"] and not x["pmcid"], 1, "url_wolfram")
take(lambda x: x["stance"] == "open" and x["pmcid"], 11, "open_pmcid")
doc = {"rule": __doc__.strip(), "register_sha256": reg_sha, "n": len(chosen),
       "by_stratum": {k: sum(1 for c in chosen if c["stratum"] == k) for k in ("settled", "url_wolfram", "open_pmcid")},
       "by_kind": {k: sum(1 for c in chosen if c["kind"] == k) for k in sorted({c["kind"] for c in chosen})},
       "items": chosen}
OUT.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
print(OUT, doc["n"], doc["by_stratum"], doc["by_kind"])
for c in chosen:
    print(c["stratum"], c["slug"], c["index"], c["source"], c["stance"], c["kind"])
