"""Delphi claim -> Frontier Claim draft, preserving the ORIGINAL Delphi identifiers and versions.

Three kinds of Delphi claim reach this adapter, and the draft says which:
  literature  nanopub-backed, quotes a public source        (quote digest + locator + source hash)
  math        nanopub-backed, cites a paper, no quote        (citation / DOI only)
  catalog     in `delphi_graph` only: NO nanopub, registry null = unpublished draft (a citation string only)

What is preserved (all from the Delphi record itself, nothing invented):
  Draft.id                    the Delphi claim id             (`turing-ddi`, `darwin1859-ch02-04`, `levin-2024-anthrobots-08`)
  Draft.source_uri            the Delphi claim IRI, or for an unpublished catalog entry an explicit
                              `urn:frontier:import:delphi-claim-graph:<id>` label (no IRI is minted for it)
  Claim.source_record_version the claim's nanopub URI as Delphi reports it; null when Delphi has none
  prior_review.delphi_original registry (production | test | null), domain, nanopub path, record licence,
                              creator/created/extractor, every field with no Claim slot, and Delphi's own
                              verification / data-test / truth labels, carried as UPSTREAM ASSERTIONS

What is deliberately NOT done:
  * quote text is never kept: only sha256, length and locator. Third-party text whose rights the Delphi record
    does not state (Wolfram NKS states "all rights reserved"). `content_available` is always False, `license` None.
  * `Source.license` means source-content rights. Delphi's record licence (CC-BY-4.0, on the nanopub) is kept
    separately under `prior_review.delphi_original.record`.
  * Delphi's recorded source hash goes into `Source.content_sha256` only after this adapter re-fetched the source
    and the hash matched.
  * Delphi's labels (`lean`, `literature`, `refuted`, data-test verdicts, LLM truth scores) are upstream
    assertions. They are never local acceptance and never evidence.
  * `assumptions` / `limitations` stay empty: Delphi has no field for them.
"""
from __future__ import annotations

import re
import urllib.request
from collections import defaultdict

from .common import iso_utc, sha_bytes, sha_obj

ADAPTER_ID = "frontier_adapters.delphi_claim"
ADAPTER_VERSION = "0.2.0"
CLAIM_PREFIX = "https://w3id.org/delphi/resource/claim/"
CATALOG_URN = "urn:frontier:import:delphi-claim-graph:"

# full predicate IRI -> name, for the rows of a claim's nanopub graphs
P = {
    "https://schema.org/text": "quote_text",
    "http://www.w3.org/ns/prov#hadPrimarySource": "primary_source",
    "http://www.w3.org/ns/prov#wasQuotedFrom": "work",
    "http://spdx.org/rdf/terms#checksumValue": "sha256",
    "http://purl.org/dc/terms/license": "record_license",
    "http://purl.org/dc/terms/created": "created",
    "http://purl.org/dc/terms/creator": "creator",
    "http://purl.org/dc/terms/rights": "rights",
    "http://purl.org/dc/terms/publisher": "publisher",
    "https://schema.org/pagination": "pagination",
    "https://schema.org/bookEdition": "edition",
    "http://purl.org/dc/terms/identifier": "identifier",
    "http://www.w3.org/ns/prov#wasDerivedFrom": "derived_from",
    "http://www.w3.org/ns/prov#wasAssociatedWith": "extractor",
}
FIELD_P = {  # predicates of the claim itself (subject = claim IRI, assertion graph)
    "http://www.w3.org/2000/01/rdf-schema#label": "rdfs:label",
    "http://purl.org/dc/terms/description": "dct:description",
    "https://w3id.org/delphi/ontology/context": "delphi:context",
    "http://purl.org/dc/terms/type": "dct:type",
    "http://www.w3.org/2004/02/skos/core#notation": "skos:notation",
    "https://w3id.org/delphi/ontology/hypothesisType": "delphi:hypothesisType",
    "https://w3id.org/delphi/ontology/proposedTest": "delphi:proposedTest",
    "http://purl.org/dc/terms/source": "dct:source",
    "http://www.w3.org/2000/01/rdf-schema#seeAlso": "rdfs:seeAlso",
    "https://w3id.org/delphi/ontology/hasEvidence": "delphi:hasEvidence",
}
MULTI = {"rdfs:seeAlso", "delphi:hasEvidence"}
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
LANGUAGE_MODEL = "https://w3id.org/delphi/ontology/LanguageModel"
GRAPH_DROP = {"graph", "id", "title", "statement"}   # `graph` is a file:///app link that resolves nowhere outside Delphi


def _rx(cid: str) -> str:
    """A claim id as a regex fragment inside a SPARQL string literal. Backslash escapes other than \\t \\b \\n \\r \\f \\" \\' \\\\
    are syntax errors there, so `re.escape` cannot be used; ids only need '.' neutralised and must not contain anything else."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", cid):
        raise ValueError(f"claim id {cid!r} has characters this query builder will not put in a SPARQL literal")
    return cid.replace(".", "[.]")


def claim_rows_query(claim_ids: list[str]) -> str:
    """SPARQL for the four nanopub graphs of the given claims. No '#' in any literal: the endpoint treats it as a
    comment start even inside quotes and then silently matches nothing. `assessments-unsigned/` graphs do not match."""
    alt = "|".join(_rx(c) for c in claim_ids)
    return ('SELECT ?g ?s ?p ?o WHERE { GRAPH ?g { ?s ?p ?o } '
            f'FILTER(REGEX(STR(?g),"/nanopubs/unsigned/({alt})[.]trig")) }} ORDER BY ?g ?s ?p ?o LIMIT 3000')


def domain_dir_of(nanopub_path: str | None) -> str | None:
    """The directory above `nanopubs/`: `darwin-origin` for `books/darwin-origin/nanopubs/...`, `math-bio-claims` for
    `math-bio-claims/nanopubs/...`, and the same for the layout seen from build 2026-10-31 20:10, `claim-sources/<dir>/nanopubs/...`.
    (Before that build this field was the FIRST path segment, so books read as `books`; records imported then keep that value.)"""
    m = re.search(r"(?:^|/)([^/]+)/nanopubs/", nanopub_path or "")
    return m.group(1) if m else None


def _claim_of_graph(g: str) -> str | None:
    m = re.search(r"/nanopubs/unsigned/([^/#]+)\.trig", g)
    return m.group(1) if m else None


def snapshot_from_rows(claim_id: str, rows: list[dict], graph_entry: dict, assessors: list[str] | None = None,
                       receipt: dict | None = None) -> tuple[dict, dict]:
    """Pure function: SPARQL rows of one claim's nanopub graphs + its `delphi_graph` entry -> (snapshot, transient).

    `snapshot` is JSON-safe and contains NO quote text; `transient` holds the quote for in-process verification only.
    Raises LookupError if the four graphs are not all present (a partial read would silently drop fields).
    """
    iri = CLAIM_PREFIX + claim_id
    mine = [r for r in rows if _claim_of_graph(r["g"]) == claim_id]
    graphs = {r["g"].rsplit("#", 1)[-1] for r in mine}
    missing = {"Head", "assertion", "provenance", "pubinfo"} - graphs
    if missing:
        raise LookupError(f"claim {claim_id!r}: nanopub graphs incomplete, missing {sorted(missing)}")
    # Provenance graphs now (build 2026-10-31 20:10) also describe the extracting LanguageModel, whose dct:identifier is a
    # model name; read as a source identifier it became the "isbn". Rows about those nodes are not source metadata.
    models = {r["s"] for r in mine if r["p"] == RDF_TYPE and r["o"] == LANGUAGE_MODEL}
    by = defaultdict(list)
    for r in mine:
        if r["s"] in models:
            continue
        name = P.get(r["p"])
        if name:
            by[name].append(r["o"])
    f = {}
    for r in mine:
        k = FIELD_P.get(r["p"])
        if k and r["s"] == iri and r["g"].endswith("#assertion"):
            f.setdefault(k, []).append(r["o"])
    fields = {k: (sorted(set(v)) if k in MULTI else v[0]) for k, v in f.items()}
    for k in ("rdfs:label", "dct:description", "delphi:context"):
        if not fields.get(k):
            raise LookupError(f"claim {claim_id!r}: record has no {k}")
    quote = (by.get("quote_text") or [None])[0]
    literature = quote is not None
    head = next((r["g"] for r in mine if r["g"].endswith("#Head")), "")
    nanopub_path = head.split("#")[0] or None
    snap = {
        "claim_id": claim_id, "claim_iri": iri, "retrieved_at": iso_utc(), "delphi_source": "local",
        "mcp_endpoint": "https://delphisci-mcp.fly.dev/mcp",
        "nanopub_path": nanopub_path, "nanopub_uri": graph_entry.get("nanopub"), "registry": graph_entry.get("registry"),
        "fields": fields,
        "record": {"license": (by.get("record_license") or [None])[0], "created": (by.get("created") or [None])[0],
                   "creator": [c for c in by.get("creator", []) if c.startswith("https://orcid.org/")][:1],
                   "extractor_agent": [e for e in by.get("extractor", []) if "extractor" in e][:1]},
        "kind": "literature" if literature else "math",
        "delphi_graph": {**{k: v for k, v in graph_entry.items() if k not in GRAPH_DROP},
                         "label": "upstream assertions by Delphi (verification, dataTest, status) and LLM-elicited scores "
                                  "(truth, testability): carried as labelled, NEVER local acceptance, NEVER evidence"},
        "assessments": {"count": len(assessors or []), "assessors": sorted(assessors or []),
                        "label": "dataset-resolvability ratings by LLM assessors: NOT evidence, NOT truth ratings"},
    }
    snap["domain_dir"] = domain_dir_of(nanopub_path)
    if literature:
        ps = by["primary_source"][0]
        base, _, frag = ps.partition("#")
        pag = [p for p in by.get("pagination", []) if p.lower().startswith("p")]
        snap["source"] = {
            "url": base, "locator": (frag or (pag[0] if pag else None)), "work": (by.get("work") or [None])[0],
            "recorded_sha256": (by.get("sha256") or [None])[0],
            "hash_scope": "whole_source_file" if "gutenberg.org" in base else "pipeline_extracted_page_text_not_reproducible",
            "edition": (by.get("edition") or [None])[0], "publisher": (by.get("publisher") or [None])[0],
            "isbn": (by.get("identifier") or [None])[0], "rights_statement": (by.get("rights") or [None])[0],
        }
        snap["quote"] = {"sha256": sha_bytes(quote.encode()), "chars": len(quote), "text_stored": False}
    else:
        d = (by.get("derived_from") or [None])[0]
        snap["source"] = {
            "url": d if d and d.startswith("https://doi.org/") else None,
            "unresolved_internal_iri": d if d and not d.startswith("https://doi.org/") else None,
            "locator": None, "recorded_sha256": None, "hash_scope": None, "citation": fields.get("dct:source"),
            "see_also_related_not_source": fields.get("rdfs:seeAlso") or [],
        }
        snap["quote"] = {"sha256": None, "chars": 0, "text_stored": False, "absent_in_record": True}
    if receipt:
        snap["receipt"] = receipt
    snap["snapshot_sha256"] = sha_obj({k: v for k, v in snap.items() if k not in ("retrieved_at", "snapshot_sha256", "receipt")})
    return snap, {"quote": quote}


def snapshot_from_catalog(entry: dict, receipt: dict | None = None) -> dict:
    """A claim present only in `delphi_graph` (no nanopub, registry null). Everything is the catalog's own text."""
    if entry.get("nanopub") or entry.get("registry"):
        raise ValueError(f"{entry.get('id')!r} has a nanopub/registry; build it from rows, not as a catalog-only entry")
    cid = entry["id"]
    chapter = entry.get("chapter") or ""
    snap = {
        "claim_id": cid, "claim_iri": None, "retrieved_at": iso_utc(), "delphi_source": "claim-graph",
        "mcp_endpoint": "https://delphisci-mcp.fly.dev/mcp", "nanopub_path": None, "nanopub_uri": None, "registry": None,
        "fields": {"rdfs:label": entry["title"], "dct:description": entry["statement"],
                   "delphi:context": ("Delphi catalog entry, unpublished (no nanopub, registry null). Source citation exactly as the "
                                      "catalog gives it: " + (chapter or "(none)")),
                   "dct:type": entry.get("kind")},
        "record": {"license": None, "created": None, "creator": [], "extractor_agent": []},
        "kind": "catalog", "domain_dir": None,
        "delphi_graph": {**{k: v for k, v in entry.items() if k not in GRAPH_DROP},
                         "label": "upstream assertions by Delphi and LLM-elicited scores: NEVER local acceptance, NEVER evidence"},
        "assessments": {"count": 0, "assessors": [], "label": "none retrieved for catalog-only entries"},
        "source": {"url": None, "locator": chapter.split(" › ", 1)[1] if " › " in chapter else None,
                   "citation": chapter or None, "work": entry.get("work"), "recorded_sha256": None, "hash_scope": None},
        "quote": {"sha256": None, "chars": 0, "text_stored": False, "absent_in_record": True},
    }
    if receipt:
        snap["receipt"] = receipt
    snap["snapshot_sha256"] = sha_obj({k: v for k, v in snap.items() if k not in ("retrieved_at", "snapshot_sha256", "receipt")})
    return snap


def graph_entries(mcp, **filters) -> list[dict]:
    r = mcp.tool("delphi_graph", {**filters, "limit": 500})
    if r.get("matched") != len(r.get("claims", [])):
        raise LookupError(f"delphi_graph {filters}: matched {r.get('matched')} but returned {len(r.get('claims', []))}; narrow the filter")
    return r["claims"]


def assessor_query(claim_ids: list[str]) -> str:
    alt = "|".join(_rx(c) for c in claim_ids)
    return ('SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } '
            f'FILTER(REGEX(STR(?g),"/nanopubs/assessments-unsigned/({alt})--[a-z0-9.-]+[.]trig")) }} ORDER BY ?g LIMIT 1000')


def assessors_from(rows) -> dict[str, list[str]]:
    out = defaultdict(set)
    for r in rows or []:
        m = re.search(r"/assessments-unsigned/(.+?)--([a-z0-9.-]+)\.trig", r["g"])
        if m:
            out[m.group(1)].add(m.group(2))
    return {k: sorted(v) for k, v in out.items()}


def collect(mcp, claim_id: str) -> tuple[dict, dict]:
    """One claim, live: its nanopub rows, then its graph entry (looked up by the claim's own label, matched by id), then its
    assessment graphs. `delphi_graph(text=...)` filters on title/statement, not on id, so the label comes from the rows."""
    rows = mcp.sparql(claim_rows_query([claim_id]))
    if not rows:
        raise LookupError(f"no nanopub graphs found for Delphi claim {claim_id!r}")
    iri = CLAIM_PREFIX + claim_id
    label = next((r["o"] for r in rows if r["s"] == iri and r["p"] == "http://www.w3.org/2000/01/rdf-schema#label"
                  and r["g"].endswith("#assertion")), None)
    if label is None:
        raise LookupError(f"claim {claim_id!r}: no label in its assertion graph")
    ent = next((x for x in graph_entries(mcp, text=label) if x["id"] == claim_id), None)
    if ent is None:
        raise LookupError(f"delphi_graph did not return {claim_id!r} for its own label {label!r}")
    ass = mcp.sparql(assessor_query([claim_id]))
    return snapshot_from_rows(claim_id, rows, ent, assessors_from(ass).get(claim_id, []))


_NORM = lambda s: re.sub(r"[^a-z0-9]+", " ", re.sub(r"\[\d+\]|\{\d+\}|_", "", s.replace("’", "'")).lower()).strip()


def verify_source(snap: dict, transient: dict, fetch=None) -> dict:
    """Re-fetch a Project Gutenberg source and check hash + quote-at-locator. Skips (says so) otherwise."""
    s = snap["source"]
    if snap["kind"] != "literature" or "gutenberg.org" not in (s.get("url") or ""):
        return {"performed": False, "reason": "no re-fetchable, rights-clear source (math, catalog or non-Gutenberg)"}
    raw = (fetch or (lambda u: urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "frontier-adapters/0.2 (read-only check)"}), timeout=60).read()))(s["url"])
    m = re.fullmatch(r"line=(\d+),(\d+)", s["locator"] or "")
    out = {"performed": True, "fetched_at": iso_utc(), "sha256_fetched": sha_bytes(raw),
           "sha256_match": sha_bytes(raw) == s["recorded_sha256"], "quote_at_locator": "no_locator"}
    if m and transient.get("quote"):
        lines = raw.decode("utf-8", "replace").splitlines()
        a, b = int(m.group(1)), int(m.group(2))
        win = " ".join(lines[a:b])
        q = transient["quote"]
        norm_ws = lambda x: re.sub(r"\s+", " ", x.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()
        out["quote_at_locator"] = ("exact" if norm_ws(q) in norm_ws(win)
                                   else "after_markup_strip" if _NORM(q) in _NORM(win) else "not_found")
    return out


def rights_for(snap: dict) -> dict:
    s = snap["source"]
    return {
        "delphi_record_license": snap["record"]["license"],
        "delphi_record_license_applies_to": "the Delphi nanopub only, NOT to the quoted source text",
        "source_text_rights": s.get("rights_statement") or "not stated in the Delphi record",
        "quote_text_included_in_output": False,
        "redistribution": "digest and locator only; no source bytes or quote text",
        "adapter_does_not_assert": "public-domain status; a reviewer must supply it with a citation before any quote is stored",
    }


def to_claim_draft(snap: dict, *, namespace: str = "node-a", issuer: str = "importer",
                   verification: dict | None = None, visibility: str = "public", origin: str = "unknown") -> dict:
    f, s = snap["fields"], snap["source"]
    ver = verification or {"performed": False, "reason": "not requested"}
    verified_hash = s.get("recorded_sha256") if ver.get("performed") and ver.get("sha256_match") else None
    catalog = snap["kind"] == "catalog"
    if catalog:
        access = ("A citation string from the Delphi claim graph only. Delphi has no nanopub for this claim (registry null: an "
                  "unpublished draft) and records no URI, quote or hash. The cited source was not retrieved or checked here.")
    elif snap["kind"] == "literature":
        access = ("Public web source named by the Delphi record. This adapter did not store the source bytes or the "
                  "quote text (" + rights_for(snap)["source_text_rights"] + "). "
                  + ("Hash re-verified against the fetched source." if verified_hash else
                     "The recorded hash was NOT re-verified here, so it is not carried as content_sha256."))
    else:
        access = ("A bibliographic citation from the Delphi record" + (" with a resolvable DOI" if s.get("url") else
                  "; the record's source IRI is a Delphi-internal identifier that does not resolve")
                  + ". No locator, quote or hash exist in the record; the claim is not span-anchored to its source.")
    absent = ["access", "assumptions", "limitations", "source_version"]
    if snap["kind"] == "math":
        absent += ["locator", "quote", "content_sha256"]
    if catalog:
        absent += ["nanopub", "claim_iri", "quote", "content_sha256", "source_uri"]
    original = {
        "claim_iri": snap["claim_iri"], "claim_id": snap["claim_id"], "nanopub_uri": snap["nanopub_uri"],
        "registry": snap["registry"], "nanopub_path": snap["nanopub_path"], "domain_dir": snap["domain_dir"],
        "publication_state": ("unpublished_catalog_entry" if catalog else
                              "delphi_test_registry: test/unreviewed, kept separate from production" if snap["registry"] == "test"
                              else "delphi_local_unsigned_nanopub: in Delphi's repository, on no registry" if not snap["registry"]
                              else "delphi_production_registry"),
        "record": snap["record"], "kind": snap["kind"],
        "unmapped_fields": {k: f[k] for k in ("dct:type", "skos:notation", "delphi:hypothesisType", "delphi:proposedTest",
                                              "dct:source", "rdfs:seeAlso", "delphi:hasEvidence") if f.get(k)},
        "source_detail": {k: v for k, v in s.items() if k not in ("url", "locator")},
        "quote": snap["quote"],
        "recorded_sha256_unverified": None if verified_hash else s.get("recorded_sha256"),
        "permission": rights_for(snap), "absent_in_record": absent,
        "delphi_graph": snap["delphi_graph"], "assessments": snap["assessments"],
    }
    payload = {
        "title": f["rdfs:label"], "statement": f["dct:description"], "context": f["delphi:context"],
        "assumptions": [], "limitations": [],
        "source": {"uri": s.get("url"), "locator": s.get("locator"), "source_version": None,
                   "content_sha256": verified_hash, "content_available": False, "access": access, "license": None},
        "source_record_version": snap["nanopub_uri"],
        "prior_review": {"delphi_original": original, "source_verification": ver,
                         "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION, "snapshot_sha256": snap["snapshot_sha256"],
                                     "retrieved_at": snap["retrieved_at"], "receipt": snap.get("receipt")}},
    }
    # `origin` (frontier-core 1b329cc): omitted when unknown, which is what omission means. This adapter never sets
    # `source_statement`: it cannot check that a pipeline-written statement says what its source says.
    if origin != "unknown":
        if origin == "source_statement":
            raise ValueError("this adapter does not assert source_statement; a reviewer who read the source must")
        payload["origin"] = origin
    return {"namespace": namespace, "kind": "Claim", "id": snap["claim_id"], "issuer": issuer,
            "source_uri": snap["claim_iri"] or (CATALOG_URN + snap["claim_id"]), "visibility": visibility, "predecessor": None,
            "payload": payload}
