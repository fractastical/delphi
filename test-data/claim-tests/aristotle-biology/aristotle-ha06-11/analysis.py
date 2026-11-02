#!/usr/bin/env python3
"""aristotle-ha06-11: the cuckoo is not a hawk, and hawks prey on it.

Pre-registered: families of Cuculus canorus and Accipiter nisus must differ;
GloBI must return at least one Accipitridae preysOn/eats/kills Cuculus canorus;
and zero such records of Accipiter nisus on itself. Talons are not scored.

Run: python3 analysis.py
"""

import datetime as dt
import hashlib
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/1.0", "Accept": "application/json", "Content-Type": "application/json"}
PREDATION = {"preyson", "eats", "kills"}
TAXA = ("Cuculus canorus", "Accipiter nisus")
CUCKOO_URL = (
    "https://api.globalbioticinteractions.org/interaction"
    "?sourceTaxon=Accipitridae&targetTaxon=Cuculus%20canorus&interactionType=preysOn"
)
SELF_URL = (
    "https://api.globalbioticinteractions.org/interaction"
    "?sourceTaxon=Accipiter%20nisus&targetTaxon=Accipiter%20nisus&interactionType=preysOn"
)


def fetch(url, name, payload=None):
    DATA.mkdir(exist_ok=True)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read()
        final = resp.geturl()
    (DATA / name).write_bytes(raw)
    return {"download_url": url, "final_url": final, "retrieved_at": retrieved,
            "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "raw": raw}


def family_of(info):
    for node in info.get("lineage") or []:
        if node.get("rank") == "family":
            return node.get("name")
    return None


def order_of(info):
    for node in info.get("lineage") or []:
        if node.get("rank") == "order":
            return node.get("name")
    return None


def predation_rows(payload):
    columns = payload["columns"]
    name_i = columns.index("source_taxon_name")
    target_i = columns.index("target_taxon_name")
    type_i = columns.index("interaction_type")
    study_i = columns.index("study_title") if "study_title" in columns else None
    rows = []
    for row in payload["data"]:
        kind = (row[type_i] or "")
        if kind.lower() not in PREDATION:
            continue
        rows.append({
            "source": row[name_i],
            "interaction_type": kind,
            "target": row[target_i],
            "study_title": None if study_i is None else row[study_i],
        })
    return rows


def main():
    tnrs = fetch(
        "https://api.opentreeoflife.org/v3/tnrs/match_names",
        "tnrs-match-names.json",
        {"names": list(TAXA), "do_approximate_matching": False},
    )
    matched = json.loads(tnrs["raw"])
    ott = {}
    for result in matched["results"]:
        matches = result.get("matches") or []
        if not matches:
            continue
        taxon = matches[0]["taxon"]
        if taxon.get("name") == result.get("name") and taxon.get("rank") == "species":
            ott[result["name"]] = taxon["ott_id"]

    families = {}
    orders = {}
    infos = {}
    for name, ott_id in ott.items():
        got = fetch(
            "https://api.opentreeoflife.org/v3/taxonomy/taxon_info",
            f"taxon-info-{ott_id}.json",
            {"ott_id": ott_id, "include_lineage": True},
        )
        info = json.loads(got["raw"])
        infos[name] = got
        families[name] = family_of(info)
        orders[name] = order_of(info)

    cuckoo = fetch(CUCKOO_URL, "globi-accipitridae-cuculus.json")
    self_q = fetch(SELF_URL, "globi-accipiter-nisus-self.json")
    cuckoo_rows = predation_rows(json.loads(cuckoo["raw"]))
    self_rows = predation_rows(json.loads(self_q["raw"]))

    same_family = families.get("Cuculus canorus") and families.get("Cuculus canorus") == families.get("Accipiter nisus")
    families_known = all(families.get(n) for n in TAXA)
    if not families_known or cuckoo.get("byte_size") is None:
        verdict, reason = "inconclusive", "data-unavailable"
    elif same_family or len(cuckoo_rows) == 0:
        verdict, reason = "refutes", None
    elif len(self_rows) > 0:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "supports", None

    confidence = 0.6 if verdict == "mixed" else (0.75 if verdict in ("supports", "refutes") else 0.4)
    measured = {
        "value": len(cuckoo_rows),
        "unit": "GloBI predation records of Accipitridae on Cuculus canorus",
        "n": len(cuckoo_rows) + len(self_rows),
        "uncertainty": (
            f"families {families}; conspecific Accipiter nisus records {len(self_rows)}"
        ),
        "extra": {
            "families": families,
            "orders": orders,
            "ott_id": ott,
            "cuckoo_predation": cuckoo_rows,
            "conspecific_predation": self_rows,
            "same_family": bool(same_family),
        },
    }

    def file_of(got, label):
        return {"name": label, "download_url": got["download_url"], "final_url": got.get("final_url"),
                "retrieved_at": got["retrieved_at"], "byte_size": got["byte_size"], "sha256": got["sha256"]}

    datasets = [
        {"id": "opentree-taxonomy-v3", "name": "Open Tree of Life taxonomy",
         "landing_url": "https://tree.opentreeoflife.org/", "doi": None,
         "version": "ott3.7draft3", "license": "not stated in the API response",
         "files": [file_of(tnrs, "tnrs-match-names.json")] + [
             file_of(infos[n], f"taxon-info-{ott[n]}.json") for n in TAXA if n in infos
         ],
         "role": "family and order of Cuculus canorus and Accipiter nisus"},
        {"id": "globi-interactions", "name": "Global Biotic Interactions",
         "landing_url": "https://www.globalbioticinteractions.org/", "doi": None,
         "version": None, "license": "not stated in the API response",
         "files": [file_of(cuckoo, "accipitridae-on-cuculus.json"), file_of(self_q, "accipiter-nisus-on-itself.json")],
         "role": "predation records of hawks on the common cuckoo, and of the sparrowhawk on itself"},
    ]
    result = json.loads((HERE / "result.json").read_text())
    result.update({
        "status": "complete",
        "data_kind": "none" if reason == "data-unavailable" else "biological",
        "verdict": verdict,
        "confidence": confidence,
        "datasets": datasets,
        "measured": measured,
        "deviations": [],
        "method": (
            "Matched both species in the Open Tree taxonomy and read the first family and the first order "
            "in each lineage. Counted GloBI rows whose interaction type is preysOn, eats, or kills for "
            "Accipitridae on Cuculus canorus and for Accipiter nisus on itself. "
            f"Families: {families}. Cuckoo-predation rows: {len(cuckoo_rows)}. "
            f"Conspecific rows: {len(self_rows)}."
        ),
        "results_summary": [
            f"Open Tree families: {families}. Orders: {orders}.",
            f"Accipitridae on Cuculus canorus: {len(cuckoo_rows)} predation rows. "
            f"Accipiter nisus on Accipiter nisus: {len(self_rows)}.",
            f"Verdict {verdict}. Talon shape and pigeon resemblance were not scored.",
        ],
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict, "families": families, "orders": orders,
        "cuckoo_predation": cuckoo_rows, "conspecific_predation": self_rows,
    }, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "families": families, "orders": orders,
                      "cuckoo": len(cuckoo_rows), "self": len(self_rows)}, indent=2))


if __name__ == "__main__":
    main()
