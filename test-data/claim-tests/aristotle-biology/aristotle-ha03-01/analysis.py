#!/usr/bin/env python3
"""Test aristotle-ha03-01 against EBI BioSamples and NCBI BioSample.

Pre-registered panel and attribute rule are in result.json. This script
does not edit those fields.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
DERIVED = ROOT / "derived"
UA = "delphi-claim-test/aristotle-ha03-01 (research; contact none)"

PANEL = [
    ("Danio rerio", "fish"),
    ("Oryzias latipes", "fish"),
    ("Takifugu rubripes", "fish"),
    ("Gasterosteus aculeatus", "fish"),
    ("Oreochromis niloticus", "fish"),
    ("Salmo salar", "fish"),
    ("Gadus morhua", "fish"),
    ("Sparus aurata", "fish"),
    ("Scyliorhinus canicula", "fish"),
    ("Raja clavata", "fish"),
    ("Python bivittatus", "snake"),
    ("Thamnophis sirtalis", "snake"),
    ("Pantherophis guttatus", "snake"),
    ("Vipera berus", "snake"),
    ("Naja naja", "snake"),
    ("Crotalus viridis", "snake"),
    ("Ambystoma mexicanum", "axolotl"),
]

VALUE_RE = re.compile(r"\btest(?:is|es|icle|icles)\b", re.I)
NEG_RE = re.compile(r"\b(no|not|without|absent|lacking)\b", re.I)
ATTR_RE = re.compile(r"organism\s*part|organismpart|tissue|isolation[ _-]?source", re.I)
FROZEN = [
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "claim_id",
    "claim_iri",
    "project",
    "agent",
]


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept": "application/json"})
    return s


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def is_testis_value(text: str) -> bool:
    if text is None:
        return False
    t = str(text).strip()
    if not VALUE_RE.search(t):
        return False
    if NEG_RE.search(t):
        return False
    if len(t) > 60:
        return False
    return True


def local(tag: str) -> str:
    return tag.split("}")[-1] if tag else ""


class FetchLog:
    def __init__(self):
        self.entries = []
        self.total_bytes = 0
        self.digest = hashlib.sha256()

    def add(self, url: str, content: bytes, retrieved_at: str):
        digest = sha256(content)
        self.total_bytes += len(content)
        self.digest.update(digest.encode())
        self.entries.append(
            {
                "download_url": url,
                "retrieved_at": retrieved_at,
                "byte_size": len(content),
                "sha256": digest,
            }
        )


def get(sess, log, url, params=None, accept="application/json"):
    retrieved = now()
    r = sess.get(url, params=params, timeout=60, headers={"Accept": accept})
    log.add(r.url, r.content, retrieved)
    r.raise_for_status()
    return r


def clade_of(lineage: str, organism: str) -> str | None:
    text = lineage or ""
    name = (organism or "").lower()
    if "ambystoma mexicanum" in name or (
        "Ambystoma mexicanum" in text or ("Ambystoma" in text and "mexicanum" in name)
    ):
        return "axolotl"
    if "Serpentes" in text or "Ophidia" in text:
        return "snake"
    if "Actinopterygii" in text or "Actinopteri" in text or "Chondrichthyes" in text or "Elasmobranchii" in text:
        return "fish"
    return None


def ebi_characteristics(sample: dict):
    chars = sample.get("characteristics") or {}
    organism = ""
    taxid = None
    hits = []
    for key, values in chars.items():
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            text = item.get("text") or ""
            if key.lower() == "organism" and not organism:
                organism = text
                for term in item.get("ontologyTerms") or []:
                    m = re.search(r"NCBITaxon_(\d+)", term)
                    if m:
                        taxid = m.group(1)
            if ATTR_RE.search(key) and is_testis_value(text):
                hits.append({"attribute": key, "value": text})
    return organism, taxid, hits


def ebi_panel(sess, log, organism: str):
    filters = [
        f"attr:organism:{organism}",
        "attr:organism part:testis",
    ]
    # Two-filter requests, plus tissue and testes variants, each paired with the organism.
    queries = [
        [f"attr:organism:{organism}", "attr:organism part:testis"],
        [f"attr:organism:{organism}", "attr:organism part:testes"],
        [f"attr:organism:{organism}", "attr:tissue:testis"],
        [f"attr:organism:{organism}", "attr:tissue:testes"],
    ]
    found = []
    errors = []
    for filt in queries:
        params = [("size", "20"), ("page", "0")] + [("filter", f) for f in filt]
        url = "https://www.ebi.ac.uk/biosamples/samples"
        try:
            r = get(sess, log, url, params=params)
        except requests.RequestException as exc:
            errors.append(str(exc))
            continue
        try:
            payload = r.json()
        except ValueError:
            errors.append("non-json")
            continue
        for sample in (payload.get("_embedded") or {}).get("samples") or []:
            org, taxid, hits = ebi_characteristics(sample)
            if hits:
                found.append(
                    {
                        "source": "ebi-biosamples",
                        "accession": sample.get("accession"),
                        "organism": org or organism,
                        "taxid": taxid,
                        "attributes": hits,
                    }
                )
        if found:
            break
    return found, errors


def ebi_open(sess, log, pages=10):
    found = []
    errors = []
    url = "https://www.ebi.ac.uk/biosamples/samples"
    for page in range(pages):
        try:
            r = get(
                sess,
                log,
                url,
                params={"size": 100, "page": page, "filter": "attr:organism part:testis"},
            )
        except requests.RequestException as exc:
            errors.append(str(exc))
            break
        try:
            payload = r.json()
        except ValueError:
            errors.append("non-json")
            break
        samples = (payload.get("_embedded") or {}).get("samples") or []
        if not samples:
            break
        for sample in samples:
            org, taxid, hits = ebi_characteristics(sample)
            if hits and org:
                found.append(
                    {
                        "source": "ebi-biosamples-open",
                        "accession": sample.get("accession"),
                        "organism": org,
                        "taxid": taxid,
                        "attributes": hits,
                    }
                )
    return found, errors


def ncbi_taxonomy(sess, log, taxids):
    lineages = {}
    ids = [t for t in taxids if t]
    for i in range(0, len(ids), 40):
        chunk = ids[i : i + 40]
        time.sleep(0.4)
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        try:
            r = get(
                sess,
                log,
                url,
                params={"db": "taxonomy", "id": ",".join(chunk), "retmode": "xml"},
                accept="application/xml",
            )
        except requests.RequestException:
            continue
        try:
            root = ET.fromstring(r.content)
        except ET.ParseError:
            continue
        for taxon in root.iter():
            if local(taxon.tag) != "Taxon":
                continue
            tid = None
            lineage = ""
            name = ""
            for child in list(taxon):
                if local(child.tag) == "TaxId" and tid is None:
                    tid = (child.text or "").strip()
                elif local(child.tag) == "ScientificName" and not name:
                    name = child.text or ""
                elif local(child.tag) == "Lineage":
                    lineage = child.text or ""
            if tid:
                lineages[tid] = lineage
                if name:
                    lineages["name:" + name.lower()] = lineage
    return lineages


def ncbi_name_taxid(sess, log, organism: str):
    time.sleep(0.4)
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    try:
        r = get(
            sess,
            log,
            url,
            params={"db": "taxonomy", "term": f'"{organism}"[Scientific Name]', "retmode": "json", "retmax": 1},
        )
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    ids = (data.get("esearchresult") or {}).get("idlist") or []
    return ids[0] if ids else None


def ncbi_panel(sess, log, organism: str):
    time.sleep(0.4)
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    term = f'"{organism}"[Organism] AND testis'
    try:
        r = get(sess, log, url, params={"db": "biosample", "term": term, "retmode": "json", "retmax": 8})
        data = r.json()
    except (requests.RequestException, ValueError) as exc:
        return [], [str(exc)]
    result = data.get("esearchresult") or {}
    ids = result.get("idlist") or []
    if not ids:
        return [], []
    time.sleep(0.4)
    fetch = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    try:
        r = get(
            sess,
            log,
            fetch,
            params={"db": "biosample", "id": ",".join(ids), "rettype": "xml", "retmode": "xml"},
            accept="application/xml",
        )
    except requests.RequestException as exc:
        return [], [str(exc)]
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return [], ["biosample xml parse error"]
    found = []
    for biosample in root.iter():
        if local(biosample.tag) != "BioSample":
            continue
        accession = biosample.attrib.get("accession")
        organism_name = organism
        taxid = None
        hits = []
        for node in biosample.iter():
            if local(node.tag) == "Organism":
                organism_name = node.attrib.get("taxonomy_name") or organism_name
                taxid = node.attrib.get("taxonomy_id") or taxid
            if local(node.tag) == "Attribute":
                aname = node.attrib.get("attribute_name") or node.attrib.get("harmonized_name") or ""
                if ATTR_RE.search(aname) and is_testis_value(node.text or ""):
                    hits.append({"attribute": aname, "value": (node.text or "").strip()})
        if hits:
            found.append(
                {
                    "source": "ncbi-biosample",
                    "accession": accession,
                    "organism": organism_name,
                    "taxid": taxid,
                    "attributes": hits,
                }
            )
    return found, []


def finish(measured, verdict, confidence, reason, datasets, method, caveats):
    data = json.loads(RESULT.read_text())
    snapshot = {k: data[k] for k in FROZEN}
    data["status"] = "complete"
    data["data_kind"] = "biological" if datasets else "none"
    data["measured"] = measured
    data["verdict"] = verdict
    data["confidence"] = confidence
    if reason:
        data["reason"] = reason
    data["datasets"] = datasets
    data["method"] = method
    data["caveats"] = caveats
    for key, value in snapshot.items():
        if data[key] != value:
            raise SystemExit(f"frozen field changed: {key}")
    RESULT.write_text(json.dumps(data, indent=2) + "\n")


def main():
    DERIVED.mkdir(exist_ok=True)
    sess = session()
    log = FetchLog()
    retrieved = now()
    panel_hits = []
    panel_errors = []
    queried = []
    for organism, expected in PANEL:
        ebi_hits, ebi_err = ebi_panel(sess, log, organism)
        ncbi_hits, ncbi_err = ncbi_panel(sess, log, organism)
        panel_errors.extend(ebi_err + ncbi_err)
        queried.append(organism)
        for hit in ebi_hits + ncbi_hits:
            hit["expected"] = expected
            hit["query"] = organism
            panel_hits.append(hit)

    open_hits, open_err = ebi_open(sess, log, pages=10)
    panel_errors.extend(open_err)

    taxids = sorted({h["taxid"] for h in panel_hits + open_hits if h.get("taxid")})
    # Names from the open search that lack a taxid still need a lineage.
    need_names = sorted({h["organism"] for h in open_hits + panel_hits if h.get("organism") and not h.get("taxid")})
    for name in need_names[:80]:
        taxid = ncbi_name_taxid(sess, log, name)
        if taxid:
            for hit in open_hits + panel_hits:
                if hit.get("organism") == name and not hit.get("taxid"):
                    hit["taxid"] = taxid
            taxids.append(taxid)
    lineages = ncbi_taxonomy(sess, log, sorted(set(taxids)))

    def accept(hit):
        organism = hit.get("organism") or ""
        lineage = ""
        if hit.get("taxid"):
            lineage = lineages.get(str(hit["taxid"]), "")
        if not lineage:
            lineage = lineages.get("name:" + organism.lower(), "")
        kind = clade_of(lineage, organism)
        # Panel hits already queried a named species. If taxonomy lookup failed,
        # fall back to the expected panel clade only for exact panel-name matches.
        if kind is None and hit.get("query") and organism.lower() == hit["query"].lower():
            kind = hit.get("expected")
            lineage = lineage or "lineage-unresolved; panel name matched"
        if kind not in {"fish", "snake", "axolotl"}:
            return None
        if kind != hit.get("expected") and hit.get("expected") and organism.lower() == (hit.get("query") or "").lower():
            # A shark queried as fish must not be counted as a snake.
            if hit["expected"] != kind:
                return None
        hit = dict(hit)
        hit["clade"] = kind
        hit["lineage_excerpt"] = lineage[:300]
        return hit

    accepted = []
    for hit in panel_hits:
        kept = accept(hit)
        if kept:
            accepted.append(kept)
    # Open-search organisms are not limited to the panel.
    for hit in open_hits:
        hit = dict(hit)
        hit["expected"] = None
        kept = accept(hit)
        if kept:
            accepted.append(kept)

    by_species = {}
    for hit in accepted:
        key = (hit["clade"], hit["organism"])
        by_species.setdefault(key, {"n_samples_seen": 0, "example": hit})
        by_species[key]["n_samples_seen"] += 1

    species_rows = []
    for (clade, organism), info in sorted(by_species.items()):
        example = info["example"]
        species_rows.append(
            {
                "clade": clade,
                "organism": organism,
                "n_samples_seen": info["n_samples_seen"],
                "example_accession": example.get("accession"),
                "example_attribute": (example.get("attributes") or [{}])[0].get("value"),
                "source": example.get("source"),
            }
        )

    fish_species = [r for r in species_rows if r["clade"] == "fish"]
    snake_species = [r for r in species_rows if r["clade"] == "snake"]
    axolotl_species = [r for r in species_rows if r["clade"] == "axolotl"]
    n_species = len(species_rows)
    services_failed = len(log.entries) == 0

    if services_failed:
        verdict, reason = "inconclusive", "data-unavailable"
    elif n_species >= 1:
        verdict, reason = "refutes", None
    else:
        verdict, reason = "inconclusive", "other"

    if verdict == "refutes" and fish_species and snake_species:
        confidence = 0.74
    elif verdict == "refutes":
        confidence = 0.62
    else:
        confidence = 0.4

    (DERIVED / "species.csv").write_text(
        "clade,organism,n_samples_seen,example_accession,example_attribute,source\n"
        + "\n".join(
            ",".join(
                json.dumps(str(row[k] if row[k] is not None else ""))[1:-1].replace(",", " ")
                if False
                else '"' + str(row[k] if row[k] is not None else "").replace('"', "'") + '"'
                for k in [
                    "clade",
                    "organism",
                    "n_samples_seen",
                    "example_accession",
                    "example_attribute",
                    "source",
                ]
            )
            for row in species_rows
        )
        + ("\n" if species_rows else "")
    )
    measured = {
        "value": n_species,
        "unit": "species with a testis-labelled BioSample",
        "n": len(queried),
        "uncertainty": None,
        "extra": {
            "fish_species": len(fish_species),
            "snake_species": len(snake_species),
            "axolotl_species": len(axolotl_species),
            "species": species_rows,
            "panel_queried": len(queried),
            "query_errors": panel_errors[:12],
            "rule_based_verdict": verdict,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    file_entry = {
        "download_url": "https://www.ebi.ac.uk/biosamples/samples and https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        "retrieved_at": retrieved,
        "byte_size": log.total_bytes,
        "sha256": log.digest.hexdigest(),
        "note": f"SHA-256 of the concatenated per-response SHA-256 hex digests; {len(log.entries)} HTTP responses",
    }
    datasets = [
        {
            "id": "ebi-biosamples",
            "name": "EBI BioSamples",
            "landing_url": "https://www.ebi.ac.uk/biosamples/",
            "doi": None,
            "version": None,
            "license": "sample-level licenses vary; registry metadata accessed via the public API",
            "files": [file_entry],
            "role": "tissue or organism-part labels on biological samples",
        },
        {
            "id": "ncbi-biosample",
            "name": "NCBI BioSample",
            "landing_url": "https://www.ncbi.nlm.nih.gov/biosample/",
            "doi": None,
            "version": None,
            "license": "public domain US government work for NCBI records; submitter metadata varies",
            "files": [file_entry],
            "role": "BioSample attributes for the same testis query, with NCBI taxonomy lineages",
        },
    ]
    method = (
        f"Queried EBI BioSamples and NCBI BioSample for the {len(queried)} pre-registered organisms, "
        "keeping a sample only when a tissue, organism-part or isolation-source attribute matched testis, "
        "testes, testicle or testicles under the 60-character rule. Also paged 10 EBI result pages for "
        "organism part = testis. Lineages came from NCBI Taxonomy. One qualifying fish, snake or axolotl species refutes."
    )
    caveats = [
        "BioSamples record that a tissue was sampled. They do not survey species in which nobody looked for a testis, so a miss cannot support the claim.",
        "Aristotle's testicles can be read as external scrotal organs. This test uses the claim file's quantity, testes, which is the male gonad named in the sample registries.",
        "The open page cap can miss species that are not on the panel. Species that were found are still counterexamples.",
        "A testis cell line counts, because the culture was taken from that organ.",
    ]
    finish(measured, verdict, confidence, reason, datasets, method, caveats)
    print(json.dumps({"verdict": verdict, "reason": reason, "n_species": n_species, "fish": len(fish_species), "snake": len(snake_species)}, indent=2))


if __name__ == "__main__":
    main()
