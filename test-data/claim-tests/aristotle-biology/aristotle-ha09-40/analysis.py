#!/usr/bin/env python3
"""aristotle-ha09-40: are robin/redstart and blackcap/garden warbler one species?

Rules are those in result.json. Run: python3 analysis.py
"""
import datetime as dt
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived"
PAIRS = [
    ("Erithacus rubecula", "Phoenicurus phoenicurus", "robin-redstart"),
    ("Sylvia atricapilla", "Sylvia borin", "blackcap-garden-warbler"),
]
BASES = [
    "HUMAN_OBSERVATION",
    "PRESERVED_SPECIMEN",
    "MACHINE_OBSERVATION",
    "MATERIAL_SAMPLE",
    "OCCURRENCE",
    "MATERIAL_CITATION",
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
        final = r.geturl()
    return raw, final


def match_species(name):
    url = "https://api.gbif.org/v1/species/match?" + urllib.parse.urlencode({"name": name, "kingdom": "Animalia"})
    raw, final = get(url)
    data = json.loads(raw)
    accepted = data.get("speciesKey") or data.get("acceptedUsageKey") or data.get("usageKey")
    return {
        "query": name,
        "url": url,
        "final_url": final,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "usageKey": data.get("usageKey"),
        "speciesKey": data.get("speciesKey"),
        "acceptedKey": accepted,
        "scientificName": data.get("species") or data.get("scientificName"),
        "rank": data.get("rank"),
        "status": data.get("status"),
        "matchType": data.get("matchType"),
        "synonym": data.get("synonym"),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def month_counts(taxon_key, region):
    params = [("taxonKey", str(taxon_key)), ("facet", "month"), ("facetLimit", "20"), ("limit", "0")]
    if region["kind"] == "country":
        params.append(("country", region["value"]))
    else:
        params.append(("continent", region["value"]))
    for b in BASES:
        params.append(("basisOfRecord", b))
    url = "https://api.gbif.org/v1/occurrence/search?" + urllib.parse.urlencode(params)
    raw, final = get(url)
    data = json.loads(raw)
    counts = {m: 0 for m in range(1, 13)}
    for facet in data.get("facets") or []:
        field = (facet.get("field") or "").upper()
        if field not in {"MONTH", "MONTHS"}:
            continue
        for c in facet.get("counts") or []:
            try:
                m = int(c.get("name"))
            except (TypeError, ValueError):
                continue
            if 1 <= m <= 12:
                counts[m] = int(c.get("count") or 0)
    return {
        "url": url,
        "final_url": final,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_count": int(data.get("count") or 0),
        "month_counts": counts,
        "month_tagged": sum(counts.values()),
    }


def floor_for(total):
    return max(5, 0.05 * total)


def joint_months(a, b):
    ta = a["month_tagged"]
    tb = b["month_tagged"]
    fa, fb = floor_for(ta), floor_for(tb)
    months = []
    for m in range(1, 13):
        if a["month_counts"][m] >= fa and b["month_counts"][m] >= fb:
            months.append(m)
    return months, fa, fb


def evaluate_pair(name_a, name_b, label):
    ma, mb = match_species(name_a), match_species(name_b)
    same = (
        ma["acceptedKey"] is not None
        and ma["acceptedKey"] == mb["acceptedKey"]
        and ma["matchType"] not in {None, "NONE"}
        and mb["matchType"] not in {None, "NONE"}
    )
    out = {"pair": label, "match_a": ma, "match_b": mb, "same_accepted_species": bool(same)}
    if ma["matchType"] in {None, "NONE"} or mb["matchType"] in {None, "NONE"} or not ma["acceptedKey"] or not mb["acceptedKey"]:
        out["pair_verdict"] = "untestable"
        out["reason"] = "species-match-failed"
        return out
    if same:
        out["pair_verdict"] = "supports"
        return out
    regions = [
        {"kind": "country", "value": "GR", "label": "Greece"},
        {"kind": "continent", "value": "EUROPE", "label": "Europe"},
    ]
    used = []
    for region in regions:
        occ_a = month_counts(ma["acceptedKey"], region)
        occ_b = month_counts(mb["acceptedKey"], region)
        block = {"region": region["label"], "a": occ_a, "b": occ_b}
        used.append(block)
        if occ_a["total_count"] < 30 or occ_b["total_count"] < 30:
            block["skipped"] = "under-30"
            continue
        months, fa, fb = joint_months(occ_a, occ_b)
        block["joint_months"] = months
        block["floor_a"] = fa
        block["floor_b"] = fb
        block["skipped"] = None
        out["regions"] = used
        out["region_used"] = region["label"]
        out["pair_verdict"] = "refutes" if months else "mixed"
        return out
    out["regions"] = used
    out["pair_verdict"] = "untestable"
    out["reason"] = "under-30-in-greece-and-europe"
    return out


def ncbi_taxid(name):
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({
        "db": "taxonomy", "term": f"{name}[SCIN]", "retmode": "json",
    })
    try:
        raw, _ = get(url)
        data = json.loads(raw)
        ids = (data.get("esearchresult") or {}).get("idlist") or []
        return {"name": name, "taxid": ids[0] if ids else None, "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    except Exception as exc:
        return {"name": name, "taxid": None, "error": str(exc)}


def main():
    result = json.loads(RESULT.read_text())
    DERIVED.mkdir(parents=True, exist_ok=True)
    pair_results = [evaluate_pair(*p) for p in PAIRS]
    ncbi = [ncbi_taxid(n) for pair in PAIRS for n in pair[:2]]
    verdicts = [p["pair_verdict"] for p in pair_results]
    if any(v == "refutes" for v in verdicts):
        verdict, reason, conf = "refutes", None, 0.85
    elif verdicts == ["supports", "supports"]:
        verdict, reason, conf = "supports", None, 0.8
    elif all(v == "untestable" for v in verdicts):
        verdict, reason, conf = "inconclusive", "data-unavailable", 0.3
    else:
        verdict, reason, conf = "mixed", None, 0.6

    def slim_occ(block):
        if not block:
            return None
        return {
            "region": block.get("region"),
            "skipped": block.get("skipped"),
            "joint_months": block.get("joint_months"),
            "floor_a": block.get("floor_a"),
            "floor_b": block.get("floor_b"),
            "total_a": (block.get("a") or {}).get("total_count"),
            "total_b": (block.get("b") or {}).get("total_count"),
            "months_a": (block.get("a") or {}).get("month_counts"),
            "months_b": (block.get("b") or {}).get("month_counts"),
        }

    summary_pairs = []
    files = []
    for p in pair_results:
        summary_pairs.append({
            "pair": p["pair"],
            "pair_verdict": p["pair_verdict"],
            "same_accepted_species": p["same_accepted_species"],
            "name_a": p["match_a"]["scientificName"],
            "key_a": p["match_a"]["acceptedKey"],
            "name_b": p["match_b"]["scientificName"],
            "key_b": p["match_b"]["acceptedKey"],
            "region_used": p.get("region_used"),
            "regions": [slim_occ(b) for b in p.get("regions") or []],
        })
        for m in (p["match_a"], p["match_b"]):
            files.append({
                "download_url": m["url"],
                "retrieved_at": m["retrieved_at"],
                "byte_size": m["byte_size"],
                "sha256": m["sha256"],
                "name": "species-match:" + m["query"],
            })
        for block in p.get("regions") or []:
            for side in ("a", "b"):
                occ = block[side]
                files.append({
                    "download_url": occ["url"],
                    "retrieved_at": occ["retrieved_at"],
                    "byte_size": occ["byte_size"],
                    "sha256": occ["sha256"],
                    "name": f"occurrences:{p['pair']}:{block['region']}:{side}",
                })

    n_joint = 0
    for p in summary_pairs:
        for reg in p["regions"]:
            if reg and reg.get("joint_months") and not reg.get("skipped"):
                n_joint += len(reg["joint_months"])
    measured = {
        "value": n_joint,
        "unit": "joint months across tested pairs in the region used",
        "n": len(pair_results),
        "extra": {"pairs": summary_pairs, "ncbi_taxonomy_check": ncbi},
    }
    result["status"] = "complete"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = conf
    result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    result["measured"] = measured
    result["method"] = (
        "Resolved each name on the GBIF backbone, then counted non-fossil occurrences by month in Greece, "
        "falling back to Europe when a species had fewer than 30 Greek records. A pair of different accepted "
        "species with a month in which both cleared max(5, 5% of month-tagged records) refutes that pair; "
        "the claim is refuted if either pair is."
    )
    result["datasets"] = [{
        "id": "gbif-backbone-and-occurrences",
        "name": "GBIF species backbone and occurrence index",
        "landing_url": "https://www.gbif.org/",
        "doi": None,
        "version": "API as retrieved on the run date",
        "license": None,
        "files": files,
        "role": "accepted species keys and monthly occurrence counts for the two named pairs",
    }]
    result["results_summary"] = [
        f"{p['pair']}: {p['pair_verdict']} ({p['name_a']} key {p['key_a']} vs {p['name_b']} key {p['key_b']}, region {p.get('region_used')})"
        for p in summary_pairs
    ]
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, summary_pairs)


if __name__ == "__main__":
    main()
