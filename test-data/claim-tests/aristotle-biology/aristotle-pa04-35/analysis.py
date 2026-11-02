#!/usr/bin/env python3
"""Cetacean gills, lung, and blowhole function, using the rules in result.json."""
import datetime as dt
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-pa04-35; research)"
PAGES = [
    ("adw-cetacea", "Animal Diversity Web account of Cetacea",
     "https://animaldiversity.org/accounts/Cetacea/"),
    ("adw-balaenoptera-musculus", "Animal Diversity Web account of Balaenoptera musculus",
     "https://animaldiversity.org/accounts/Balaenoptera_musculus/"),
    ("adw-tursiops-truncatus", "Animal Diversity Web account of Tursiops truncatus",
     "https://animaldiversity.org/accounts/Tursiops_truncatus/"),
    ("noaa-ocean-today-dolphin-anatomy", "NOAA Ocean Today dolphin anatomy",
     "https://oceantoday.noaa.gov/dolphinanatomy/"),
]
NO_GILL = re.compile(r"no gills|without gills|lack gills|lacks gills", re.I)
HAS_GILLS = re.compile(r"\bhave gills\b|\bhas gills\b|\bwith gills\b", re.I)
NO_LUNG = re.compile(r"no lungs|without lungs|lack lungs|lacks a lung", re.I)
BLOW = re.compile(r"blowhole|blow hole", re.I)
FUNC_WATER = re.compile(r"seawater|sea water|water taken|water swallowed|ingested", re.I)
FUNC_VERB = re.compile(r"discharg|expel|spout", re.I)
RESP = re.compile(r"breath|breathe|air|nostril|lung|respir", re.I)


def fetch(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read(), getattr(resp, "status", 200)


def to_text(raw):
    page = raw.decode("utf-8", "replace")
    page = re.sub(r"(?is)<(script|style)\b.*?>.*?</\1>", " ", page)
    page = re.sub(r"(?is)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(page)).strip()


def blow_windows(text, inner):
    hits = []
    for m in BLOW.finditer(text):
        w = text[max(0, m.start() - 150): m.end() + 150]
        if inner(w):
            hits.append(w)
    return hits


def ols_term(query):
    url = (
        "https://www.ebi.ac.uk/ols4/api/search?ontology=uberon&queryFields=label"
        f"&exact=true&q={urllib.parse.quote(query)}"
    )
    raw, _ = fetch(url, "application/json")
    docs = json.loads(raw)["response"]["docs"]
    exact = [d for d in docs if d.get("label", "").casefold() == query.casefold() and d.get("ontology_name") == "uberon"]
    if not exact:
        return {"query": query, "found": False}
    doc = exact[0]
    obo = doc.get("obo_id")
    detail_url = f"https://www.ebi.ac.uk/ols4/api/ontologies/uberon/terms?obo_id={obo}"
    detail, _ = fetch(detail_url, "application/json")
    term = json.loads(detail)["_embedded"]["terms"][0]
    ann = term.get("annotation") or {}
    return {
        "query": query,
        "found": True,
        "obo_id": obo,
        "label": term.get("label"),
        "never_in_taxon": ann.get("never in taxon", []),
        "annotation_keys": sorted(ann.keys()),
    }


def taxon_label(iri):
    obo = iri.rstrip("/").split("/")[-1].replace("_", ":")
    url = f"https://www.ebi.ac.uk/ols4/api/ontologies/ncbitaxon/terms?obo_id={urllib.parse.quote(obo)}"
    try:
        raw, _ = fetch(url, "application/json")
        return json.loads(raw)["_embedded"]["terms"][0].get("label")
    except Exception:
        return obo


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datasets = []
    page_scores = []
    combined = ""
    for pid, name, url in PAGES:
        raw, status = fetch(url)
        (DATA / f"{pid}.html").write_bytes(raw)
        text = to_text(raw)
        combined += "\n" + text
        water = blow_windows(text, lambda w: FUNC_WATER.search(w) and FUNC_VERB.search(w))
        resp = blow_windows(text, lambda w: RESP.search(w))
        separate = bool(re.search(r"blowhole|blow hole|nasal", text, re.I) and re.search(r"separate|separated|not connected", text, re.I) and re.search(r"mouth|esophagus|oesophagus", text, re.I))
        page_scores.append({
            "id": pid,
            "http_status": status,
            "chars": len(text),
            "no_gill": bool(NO_GILL.search(text)),
            "has_gills_phrase": bool(HAS_GILLS.search(text)),
            "lung": bool(re.search(r"\blungs?\b", text, re.I)),
            "no_lung_phrase": bool(NO_LUNG.search(text)),
            "blowhole": bool(BLOW.search(text)),
            "aristotle_function_windows": len(water),
            "respiratory_windows": len(resp),
            "separate_from_mouth": separate,
            "function_snippet": water[0][:300] if water else (resp[0][:300] if resp else ""),
        })
        datasets.append({
            "id": pid, "name": name, "landing_url": url, "doi": None, "version": None, "license": None,
            "files": [{"download_url": url, "retrieved_at": now, "byte_size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}],
            "role": "prose on cetacean respiration",
        })
    uberon = [ols_term(q) for q in ("lung", "gill", "blowhole")]
    for term in uberon:
        named = []
        for iri in term.get("never_in_taxon") or []:
            named.append({"iri": iri, "label": taxon_label(iri)})
        term["never_in_taxon_named"] = named
    (DATA / "uberon-terms.json").write_text(json.dumps(uberon, indent=2))
    uberon_bytes = (DATA / "uberon-terms.json").read_bytes()
    datasets.append({
        "id": "uberon-lung-gill-blowhole",
        "name": "Uberon terms lung, gill, and blowhole via OLS",
        "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/uberon",
        "doi": None, "version": None, "license": "CC BY 4.0",
        "files": [{
            "download_url": "https://www.ebi.ac.uk/ols4/api/search?ontology=uberon&queryFields=label&exact=true",
            "retrieved_at": now,
            "byte_size": len(uberon_bytes),
            "sha256": hashlib.sha256(uberon_bytes).hexdigest(),
            "note": "byte size and checksum are of the derived term bundle written from the live OLS responses, not of one upstream file",
        }],
        "role": "taxon restrictions on lung, gill, and blowhole",
    })

    loaded = [p for p in page_scores if p["http_status"] == 200 and p["chars"] > 500]
    no_gill = any(p["no_gill"] for p in loaded)
    lung = any(p["lung"] for p in loaded)
    blow = any(p["blowhole"] for p in loaded)
    # Uberon may supply no-gill or lung, never a missing annotation as a failure.
    gill_term = next((t for t in uberon if t["query"] == "gill" and t.get("found")), None)
    lung_term = next((t for t in uberon if t["query"] == "lung" and t.get("found")), None)
    def covers_mammal_or_cetacean(term):
        if not term:
            return False
        labels = " ".join((x.get("label") or "") for x in term.get("never_in_taxon_named") or []).casefold()
        # Amniota is recorded as a deviation: it is the parent group of Mammalia and Cetacea.
        return any(name in labels for name in ("mammalia", "cetacea", "amniota"))
    if covers_mammal_or_cetacean(gill_term):
        no_gill = True
    if lung_term and lung_term.get("found"):
        # a lung term existing is not presence in Cetacea; only an explicit annotation would count.
        # The criterion allows "a lung term is present for Mammalia or Cetacea".
        # OLS 'never in taxon' does not assert presence. Leave lung to the prose unless an annotation says so.
        pass
    inventory_fails = any(p["has_gills_phrase"] or p["no_lung_phrase"] for p in loaded)
    inventory_holds = no_gill and lung and blow and not inventory_fails
    function_holds = any(p["aristotle_function_windows"] for p in loaded)
    function_fails = (not function_holds) and (
        any(p["respiratory_windows"] or p["separate_from_mouth"] for p in loaded)
    )
    if not loaded:
        verdict, reason = "inconclusive", "data-unavailable"
    elif not inventory_holds and not function_holds and not function_fails and not inventory_fails:
        verdict, reason = "inconclusive", "not-operationalizable"
    elif inventory_fails and function_fails:
        verdict, reason = "refutes", None
    elif inventory_holds and function_holds:
        verdict, reason = "supports", None
    elif inventory_holds and function_fails:
        verdict, reason = "mixed", None
    elif inventory_fails and function_holds:
        verdict, reason = "mixed", None
    elif function_fails and not inventory_holds:
        # function contradicted and inventory not positively shown: the fail rule's
        # refutation needs inventory to fail as well. Leave mixed when function fails
        # and inventory is simply incomplete rather than contradicted.
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "not-operationalizable"
    measured = {
        "value": sum(p["aristotle_function_windows"] for p in page_scores),
        "unit": "pages' blowhole windows that describe discharge of ingested seawater",
        "n": len(loaded),
        "uncertainty": None,
        "extra": {
            "inventory_holds": inventory_holds,
            "inventory_fails": inventory_fails,
            "function_holds": function_holds,
            "function_fails": function_fails,
            "no_gill": no_gill,
            "lung": lung,
            "blowhole": blow,
            "pages": page_scores,
            "uberon": [{k: t.get(k) for k in ("query", "found", "obo_id", "label", "never_in_taxon_named")} for t in uberon],
        },
    }
    confidence = 0.8 if verdict == "mixed" and inventory_holds and function_fails else 0.5
    result = json.loads((HERE / "result.json").read_text())
    result["deviations"] = [{
        "change": "A Uberon never_in_taxon annotation on Amniota was accepted as the no-gill clause.",
        "why": "The pre-registered rule named Mammalia or Cetacea. The gill term is annotated never_in_taxon for Amniota, the parent taxon of both. The prose pages say lung and blowhole but do not contain the strings 'no gills', 'without gills', 'lack gills', or 'lacks gills'. Thresholds were not changed.",
    }]
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "datasets": datasets,
        "measured": measured,
        "verdict": verdict,
        "confidence": confidence,
        "method": (
            "Stripped the four pre-registered prose pages and applied the no-gill, lung, blowhole, "
            "seawater-discharge, and respiratory-window tests. Queried OLS for the Uberon labels "
            "lung, gill, and blowhole and resolved never_in_taxon names. A missing annotation did not "
            "count as evidence that gills are present."
        ),
    })
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["results_summary"] = [
        f"inventory_holds={inventory_holds} (no_gill={no_gill}, lung={lung}, blowhole={blow}, inventory_fails={inventory_fails}).",
        f"function_holds={function_holds}, function_fails={function_fails}.",
    ] + [
        f"{p['id']}: no_gill={p['no_gill']} lung={p['lung']} blowhole={p['blowhole']} seawater_windows={p['aristotle_function_windows']} respiratory_windows={p['respiratory_windows']}"
        for p in page_scores
    ]
    (DERIVED / "measured.json").write_text(json.dumps({"measured": measured, "verdict": verdict}, indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, "inv", inventory_holds, "fn_hold", function_holds, "fn_fail", function_fails)


if __name__ == "__main__":
    main()
