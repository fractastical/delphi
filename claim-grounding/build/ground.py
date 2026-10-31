"""Ground the entities a Project Delphi claim is about, and draft its subject-matter nanopublication.

The script reads claims either from the nanopublication network (each claim IRI given on the
command line) or from the unsigned nanopublication files of a project in this repository
(--local, through the local store of the delphisci CLI, so `npm ci` must have run). Each claim's
label, description, context and quoted source text is grounded twice: by Gilda (the grounding
service behind INDRA), and by exact label or synonym lookups of its short phrases in GO, UBERON,
CL and NCBITaxon through EBI's Ontology Lookup Service. A match is kept when its vocabulary is
allowed and its score reaches the minimum, unless it is a gene or protein matched on a word not
written as a symbol, a top-level chemical class, or a term under an excluded branch (HPO clinical
modifiers and frequencies, the CHEBI role branch). A local claim's provenance cites the signed
copy of its nanopublication where the project has one. It then writes:

  candidates/<claim-id>.json          every match found, kept or dropped, with the reason
  nanopubs/unsigned/<claim-id>.trig   an unsigned draft made with the Project Delphi claim
                                      subject-matter template: <claim> schema:about <IRI>, one
                                      triple per kept entity, with provenance on what grounded it

Nothing is signed or published. Every draft is reviewed, by a person or a second model, before
it is.

    python3 claim-grounding/build/ground.py <claim-iri> [<claim-iri> ...]
    python3 claim-grounding/build/ground.py --local claim-sources/math-bio-claims
"""

import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SPARQL_ENDPOINT = "https://query.knowledgepixels.com/repo/full"
GILDA_ANNOTATE = "https://grounding.indra.bio/annotate"
GILDA_SERVICE = "https://grounding.indra.bio/"
OLS_API = "https://www.ebi.ac.uk/ols4/api"
OLS_SERVICE = "https://www.ebi.ac.uk/ols4/"
OLS_ONTOLOGIES = "go,uberon,cl,ncbitaxon"
OLS_WORKERS = 6
RETRIES = 4
TEMPLATE = "https://w3id.org/np/RAUScXW9qrWeA-x8TUsvmHkqJJsHTHke8ev4eus4e61qQ/templateVersion"
PUBINFO_TEMPLATES = [
    "https://w3id.org/np/RACJ58Gvyn91LqCKIO9zu1eijDQIeEff28iyDrJgjSJF8",
    "https://w3id.org/np/RAukAcWHRDlkqxk7H2XNSegc1WnHI569INvNr-xdptDGI",
]
AGENT = "https://w3id.org/delphi/resource/agent/delphisci-claim-entity-grounder"
AGENT_LABEL = "delphisci claim entity grounder (Gilda, OLS)"
OPERATOR_ORCID = "https://orcid.org/0000-0001-8492-0354"
OPERATOR_NAME = "Ashley Caselli"
MIN_SCORE = 0.7
OBO_PURL = "http://purl.obolibrary.org/obo/"
TERM_IRIS = {
    "HGNC": lambda identifier: f"https://identifiers.org/hgnc:{identifier}",
    "UP": lambda identifier: f"http://purl.uniprot.org/uniprot/{identifier}",
    "CHEBI": lambda identifier: OBO_PURL + identifier.replace(":", "_"),
    "GO": lambda identifier: OBO_PURL + identifier.replace(":", "_"),
    "UBERON": lambda identifier: OBO_PURL + identifier.replace(":", "_"),
    "CL": lambda identifier: OBO_PURL + identifier.replace(":", "_"),
    "HP": lambda identifier: OBO_PURL + identifier.replace(":", "_"),
    "NCBITAXON": lambda identifier: OBO_PURL + identifier.replace(":", "_").replace("NCBITAXON", "NCBITaxon"),
}
GENE_VOCABULARIES = {"HGNC", "UP"}
EXCLUDED_BRANCHES = {
    "HP": {"HP:0012823", "HP:0040279"},
    "CHEBI": {"CHEBI:50906"},
}
GENERIC_TERMS = {
    "CHEBI:24431", "CHEBI:23367", "CHEBI:59999", "CHEBI:60004", "CHEBI:33250",
    "CHEBI:24433", "CHEBI:24870", "CHEBI:36342", "CHEBI:60027",
}
OLS_SCORES = {"label": 1.0, "synonym": 0.9, "ambiguous synonym": 0.75}
STOPWORDS = set("""a an and are as at be been between but by can do does each either for from has have
how if in into is it its may more most must no not of on one or other our over per same such than that
the their them then there these they this those through to two under up upon was we were what when where
which while who will with within without would""".split())
USER_AGENT = "delphisci/claim-grounding (https://github.com/fractastical/delphi)"


def fetch(request, timeout):
    """Send a request and return the decoded body, retrying transient network failures.

    :param request: the request to send
    :param timeout: the timeout per attempt, in seconds
    :return: the response body as text
    :raises urllib.error.URLError: if every attempt fails
    """
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode()
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt == RETRIES - 1:
                raise
            time.sleep(2 ** attempt)


def post(url, data, content_type, accept):
    """Send a POST request and return the decoded body.

    :param url: the URL to post to
    :param data: the request body
    :param content_type: the Content-Type header
    :param accept: the Accept header
    :return: the response body as text
    """
    request = urllib.request.Request(url, data=data.encode(), method="POST", headers={
        "Content-Type": content_type, "Accept": accept, "User-Agent": USER_AGENT})
    return fetch(request, 120)


def sparql(query):
    """Run a SPARQL query against the network's full repository.

    :param query: the SPARQL query
    :return: the result rows, each a dict from variable name to value
    """
    body = post(SPARQL_ENDPOINT, urllib.parse.urlencode({"query": query}),
                "application/x-www-form-urlencoded", "application/sparql-results+json")
    return [{k: v["value"] for k, v in row.items()} for row in json.loads(body)["results"]["bindings"]]


def read_claim(claim_iri):
    """Read a published claim: its nanopublication, label, description and quoted source text.

    Only a nanopublication with a valid signature that is neither invalidated nor superseded by
    its own key counts.

    :param claim_iri: the claim's IRI
    :return: a dict with the claim's nanopublication, label and texts
    :raises SystemExit: if no such nanopublication introduces the claim
    """
    rows = sparql(f"""
prefix np: <http://www.nanopub.org/nschema#>
prefix npa: <http://purl.org/nanopub/admin/>
prefix npx: <http://purl.org/nanopub/x/>
prefix dct: <http://purl.org/dc/terms/>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix schema: <https://schema.org/>
prefix delphi: <https://w3id.org/delphi/ontology/>
select ?np ?label ?description ?context ?quote where {{
  graph npa:graph {{
    ?np npx:introduces <{claim_iri}> ; np:hasAssertion ?a ; np:hasProvenance ?p ;
      npa:hasValidSignatureForPublicKeyHash ?pk .
    filter not exists {{ ?inv npx:invalidates ?np ; npa:hasValidSignatureForPublicKeyHash ?pk . }}
    filter not exists {{ ?sup npx:supersedes ?np ; npa:hasValidSignatureForPublicKeyHash ?pk . }}
  }}
  optional {{ graph ?a {{ <{claim_iri}> rdfs:label ?label }} }}
  optional {{ graph ?a {{ <{claim_iri}> dct:description ?description }} }}
  optional {{ graph ?a {{ <{claim_iri}> delphi:context ?context }} }}
  optional {{ graph ?p {{ ?q schema:text ?quote }} }}
}}""")
    if not rows:
        raise SystemExit(f"no valid, current nanopublication introduces {claim_iri}")
    return claim_record(claim_iri, rows[0]["np"], "network", rows)


def claim_record(claim_iri, nanopub, nanopub_source, rows):
    """Collect a claim's texts from query rows into one record.

    :param claim_iri: the claim's IRI
    :param nanopub: the IRI of the nanopublication that introduces the claim, or None if it has none
    :param nanopub_source: where that nanopublication is: network, test registry or none
    :param rows: the query rows for the claim, with optional label, description, context and quote
    :return: a dict with the claim's nanopublication, label and texts
    """
    first = rows[0]
    return {
        "iri": claim_iri,
        "nanopub": nanopub,
        "nanopub_source": nanopub_source,
        "label": first.get("label", claim_iri.rsplit("/", 1)[-1]),
        "description": first.get("description", ""),
        "context": first.get("context", ""),
        "quotes": sorted({row["quote"] for row in rows if "quote" in row}),
    }


def local_sparql(query):
    """Run a SPARQL query against the repository's local store of unsigned nanopublications.

    The store is the one the delphisci MCP server and CLI use: every nanopubs/unsigned directory
    of a project under claim-sources/ or test-data/, each file loaded under its own base.

    :param query: the SPARQL query
    :return: the result rows, each a dict from variable name to value; nanopublications are file paths
    """
    result = subprocess.run(["node", str(REPO / "mcp" / "cli.mjs"), "sparql", query],
                            capture_output=True, text=True, cwd=REPO)
    if result.returncode != 0:
        raise SystemExit(f"local query failed (is `npm ci` done?): {result.stderr.strip()[-500:]}")
    return json.loads(result.stdout)


def signed_nanopub(unsigned_path):
    """Find the trusty IRI of the signed copy of an unsigned nanopublication, if there is one.

    The signed copy is the file of the same name in a sibling signed directory (signed-test for
    the test registry, signed for the live network).

    :param unsigned_path: the unsigned file's path, relative to the repository
    :return: a pair (IRI, where it is published), or (None, "none")
    """
    for directory, source in (("signed", "network"), ("signed-test", "test registry")):
        signed = REPO / unsigned_path.replace("/unsigned/", f"/{directory}/")
        if signed.is_file():
            for line in signed.read_text().splitlines()[:20]:
                if line.startswith("@prefix this:"):
                    return line.split("<", 1)[1].split(">", 1)[0], source
    return None, "none"


def read_local_claims(project):
    """Read the claims of a project from its unsigned nanopublication files.

    :param project: the project directory, relative to the repository, e.g. claim-sources/math-bio-claims
    :return: one claim record per claim the project's unsigned files introduce
    """
    rows = local_sparql(f"""
prefix np: <http://www.nanopub.org/nschema#>
prefix npx: <http://purl.org/nanopub/x/>
prefix dct: <http://purl.org/dc/terms/>
prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>
prefix schema: <https://schema.org/>
prefix delphi: <https://w3id.org/delphi/ontology/>
select ?np ?claim ?label ?description ?context ?quote where {{
  graph ?h {{ ?np np:hasAssertion ?a ; np:hasProvenance ?p }}
  graph ?i {{ ?np npx:introduces ?claim }}
  graph ?a {{ ?claim a delphi:Claim }}
  optional {{ graph ?a {{ ?claim rdfs:label ?label }} }}
  optional {{ graph ?a {{ ?claim dct:description ?description }} }}
  optional {{ graph ?a {{ ?claim delphi:context ?context }} }}
  optional {{ graph ?p {{ ?q schema:text ?quote }} }}
  filter(contains(str(?np), "{project.rstrip('/')}/nanopubs/unsigned/"))
}}""")
    by_claim = {}
    for row in rows:
        by_claim.setdefault(row["claim"], []).append(row)
    claims = []
    for claim_iri, claim_rows in sorted(by_claim.items()):
        nanopub, source = signed_nanopub(claim_rows[0]["np"])
        claims.append(claim_record(claim_iri, nanopub, source, claim_rows))
    return claims


def annotate(text):
    """Find and ground entity mentions in a text with Gilda.

    :param text: the text to annotate
    :return: Gilda's annotations, each with the matched text and its ranked groundings
    """
    return json.loads(post(GILDA_ANNOTATE, json.dumps({"text": text}), "application/json", "application/json"))


def term_iri(db, identifier):
    """Build the IRI of a grounded term: the vocabulary's own IRI where it has one.

    OBO vocabularies (GO, CHEBI, UBERON, CL, HP) get their OBO PURL, UniProt its own IRI, and HGNC,
    which publishes no IRIs of its own, an identifiers.org IRI.

    :param db: Gilda's namespace, e.g. GO
    :param identifier: Gilda's identifier within that namespace, e.g. GO:0060361
    :return: the IRI, e.g. http://purl.obolibrary.org/obo/GO_0060361
    """
    return TERM_IRIS[db](identifier)


def get_json(url, params):
    """Send a GET request and return the decoded JSON body.

    :param url: the URL to get
    :param params: the query parameters
    :return: the decoded JSON
    """
    request = urllib.request.Request(f"{url}?{urllib.parse.urlencode(params)}",
                                     headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    return json.loads(fetch(request, 60))


@lru_cache(maxsize=None)
def ancestors(db, identifier):
    """Look up a term's ancestors in its ontology through OLS.

    :param db: the vocabulary, e.g. HP
    :param identifier: the term's identifier, e.g. HP:0031915
    :return: the identifiers of all its ancestors, as a frozenset
    """
    iri = term_iri(db, identifier)
    encoded = urllib.parse.quote(urllib.parse.quote(iri, safe=""), safe="")
    body = get_json(f"{OLS_API}/ontologies/{db.lower()}/terms/{encoded}/hierarchicalAncestors", {"size": 500})
    return frozenset(term["obo_id"] for term in body.get("_embedded", {}).get("terms", []) if term.get("obo_id"))


@lru_cache(maxsize=None)
def ols_lookup(phrase):
    """Find the terms whose label or synonym is exactly a phrase, in the OLS ontologies searched.

    :param phrase: the phrase, lower case
    :return: a tuple of (obo_id, label, matched field) for each distinct matching term
    """
    body = get_json(f"{OLS_API}/search", {"q": phrase, "ontology": OLS_ONTOLOGIES, "exact": "true",
                                          "queryFields": "label,synonym", "rows": 10})
    found = {}
    for doc in body["response"]["docs"]:
        obo_id = doc.get("obo_id")
        if not obo_id or ":" not in obo_id or obo_id in found:
            continue
        field = "label" if doc.get("label", "").lower() == phrase else "synonym"
        found[obo_id] = (obo_id, doc.get("label", ""), field)
    return tuple(found.values())


def phrases(text):
    """List the short phrases of a text worth looking up: one to three words, no stopword at either end.

    :param text: the text
    :return: the distinct phrases, lower case, each mapped to the form it first appears in
    """
    found = {}
    for clause in re.split(r"[.,;:()\[\]!?\"“”]", text):
        words = re.findall(r"[A-Za-z][A-Za-z-]*[A-Za-z]", clause)
        for size in (1, 2, 3):
            for start in range(len(words) - size + 1):
                original = words[start:start + size]
                gram = [w.lower() for w in original]
                if gram[0] in STOPWORDS or gram[-1] in STOPWORDS:
                    continue
                if size == 1 and len(gram[0]) < 5:
                    continue
                found.setdefault(" ".join(gram), " ".join(original))
    return found


def excluded(db, identifier):
    """Tell whether a term is too generic to say what a claim is about.

    :param db: the vocabulary
    :param identifier: the term's identifier
    :return: the reason it is excluded, or None
    """
    if identifier in GENERIC_TERMS:
        return f"{identifier} is a top-level class, too generic to say what a claim is about"
    branches = EXCLUDED_BRANCHES.get(db)
    if not branches:
        return None
    hit = branches & ({identifier} | ancestors(db, identifier))
    return f"{identifier} is under {', '.join(sorted(hit))}, an excluded branch" if hit else None


def judge(db, identifier, name, score, source, mention):
    """Decide whether one mention of a term makes it a draft link, and why.

    :param db: the vocabulary of the matched term
    :param identifier: the matched term's identifier
    :param name: the matched term's name
    :param score: the match score
    :param source: what found the match, e.g. gilda or ols-exact-synonym
    :param mention: the text that was matched, as written
    :return: a pair (kept, reason)
    """
    if db not in TERM_IRIS:
        return False, f"namespace {db} is not in the allowed vocabularies"
    if score < MIN_SCORE:
        return False, f"score {score:.2f} is below {MIN_SCORE}"
    if db in GENE_VOCABULARIES and mention != mention.upper():
        return False, f"'{mention}' is not written as a gene or protein symbol"
    if source == "ols-exact-ambiguous-synonym":
        return False, f"'{mention}' is a synonym of several terms"
    if source == "ols-exact-synonym" and mention[:1].isupper():
        return False, f"'{mention}' is capitalized, so more likely a name than the common name of {identifier}"
    if source == "ols-exact-synonym" and db != "NCBITAXON" and " " not in mention:
        return False, f"'{mention}' is a one-word synonym, accepted only as the common name of a taxon"
    if source == "ols-exact-label" and db == "NCBITAXON" and mention != name:
        return False, f"'{mention}' is not written as the scientific name {name}"
    reason = excluded(db, identifier)
    if reason:
        return False, reason
    return True, "allowed vocabulary, score at or above the minimum"


def add_candidate(candidates, db, identifier, name, score, source, field, mention):
    """Record a mention of a term; the term becomes a link if any of its mentions passes.

    :param candidates: the candidates so far, by (db, identifier)
    :param db: the vocabulary
    :param identifier: the term's identifier
    :param name: the term's name
    :param score: the match score
    :param source: what found the match, e.g. gilda or ols-exact-label
    :param field: the claim field the mention is in
    :param mention: the matched text
    """
    key = (db, identifier)
    candidate = candidates.setdefault(key, {"db": db, "id": identifier, "name": name, "iri": None,
                                            "score": round(score, 4), "source": source, "kept": False,
                                            "reason": None, "mentions": []})
    candidate["mentions"].append({"field": field, "text": mention})
    if candidate["kept"]:
        return
    kept, reason = judge(db, identifier, name, score, source, mention)
    if kept or candidate["reason"] is None:
        candidate.update({"score": round(score, 4), "source": source, "kept": kept, "reason": reason,
                          "iri": term_iri(db, identifier) if kept else None})


def ground(claim, pool):
    """Ground a claim's texts with Gilda and OLS exact lookups, and judge every match.

    :param claim: the claim as returned by read_claim or read_local_claims
    :param pool: the thread pool for OLS lookups
    :return: one candidate per distinct term, kept ones first, best score first
    """
    texts = [("label", claim["label"]), ("description", claim["description"]), ("context", claim["context"])]
    texts += [("quoted source", quote) for quote in claim["quotes"]]
    candidates = {}
    for field, text in texts:
        if not text:
            continue
        for annotation in annotate(text):
            if annotation.get("matches"):
                term = annotation["matches"][0]["term"]
                add_candidate(candidates, term["db"], term["id"], term["entry_name"],
                              annotation["matches"][0]["score"], "gilda", field, annotation["text"])
        grams = phrases(text)
        lowered = sorted(grams)
        for gram, terms in zip(lowered, pool.map(ols_lookup, lowered)):
            for obo_id, label, matched in terms:
                kind = "ambiguous synonym" if matched == "synonym" and len(terms) > 1 else matched
                prefix = obo_id.split(":", 1)[0].upper()
                add_candidate(candidates, prefix, obo_id, label, OLS_SCORES[kind],
                              f"ols-exact-{kind.replace(' ', '-')}", field, grams[gram])
    return sorted(candidates.values(), key=lambda c: (not c["kept"], -c["score"], c["db"], c["id"]))


def plan_iri():
    """Return the GitHub IRI of this script at the commit it runs from, or a marker if uncommitted.

    :return: the plan IRI and whether it is pinned to a clean commit
    """
    relative = Path(__file__).resolve().relative_to(REPO).as_posix()
    commit = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain", "--", relative],
                           capture_output=True, text=True).stdout.strip()
    pinned = bool(commit) and not dirty
    return f"https://github.com/fractastical/delphi/blob/{commit if pinned else 'UNCOMMITTED'}/{relative}", pinned


def literal(text):
    """Serialize a string as a Turtle literal.

    :param text: the string
    :return: the quoted, escaped literal
    """
    return json.dumps(text, ensure_ascii=False)


def draft(claim, candidates, plan, now):
    """Write the unsigned subject-matter nanopublication for a claim.

    :param claim: the claim as returned by read_claim
    :param candidates: the judged candidates; only kept ones become links
    :param plan: the IRI of the script that grounded the claim
    :param now: the creation time, ISO 8601 in UTC
    :return: the TriG text
    """
    kept = [c for c in candidates if c["kept"]]
    about = "".join(f"\n    schema:about <{c['iri']}> ;" for c in kept).rstrip(" ;") + " ."
    labels = "".join(f"\n  <{c['iri']}> rdfs:label {literal(c['name'])} ." for c in kept)
    claim_id = claim["iri"].rsplit("/", 1)[-1]
    claim_nanopub = claim["nanopub"]
    derived = f" ;\n    prov:wasDerivedFrom <{claim_nanopub}> ." if claim_nanopub else " ."
    services = f"<{GILDA_SERVICE}>, <{OLS_SERVICE}>"
    used = f"<{claim_nanopub}>, {services}" if claim_nanopub else services
    return f"""@prefix this: <http://purl.org/nanopub/temp/claim-subject-matter/> .
@prefix sub: <http://purl.org/nanopub/temp/claim-subject-matter/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix nt: <https://w3id.org/np/o/ntemplate/> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix schema: <https://schema.org/> .

sub:Head {{
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}}

sub:assertion {{
  <{claim['iri']}>{about}
{labels}
}}

sub:provenance {{
  sub:assertion prov:wasAttributedTo <{AGENT}> ;
    prov:wasGeneratedBy sub:grounding{derived}

  <{AGENT}> a prov:SoftwareAgent ;
    rdfs:label {literal(AGENT_LABEL)} ;
    prov:actedOnBehalfOf <{OPERATOR_ORCID}> .

  sub:grounding a prov:Activity ;
    prov:wasAssociatedWith <{AGENT}> ;
    prov:used {used} ;
    prov:startedAtTime "{now}"^^xsd:dateTime ;
    prov:qualifiedAssociation sub:groundingPlan .

  sub:groundingPlan prov:hadPlan <{plan}> .
}}

sub:pubinfo {{
  <{OPERATOR_ORCID}> foaf:name {literal(OPERATOR_NAME)} .

  this: dct:created "{now}"^^xsd:dateTime ;
    dct:creator <{OPERATOR_ORCID}> ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    rdfs:label {literal("Subject matter of " + claim_id)} ;
    npx:hasNanopubType schema:about ;
    nt:wasCreatedFromTemplate <{TEMPLATE}> ;
    nt:wasCreatedFromPubinfoTemplate {", ".join(f"<{t}>" for t in PUBINFO_TEMPLATES)} .
}}
"""


def main(claims):
    """Ground each claim and write its candidates file and unsigned draft.

    :param claims: the claims to ground, as returned by read_claim or read_local_claims
    """
    plan, pinned = plan_iri()
    if not pinned:
        print("note: script is not committed, so the drafts name an UNCOMMITTED plan; rebuild after committing")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (ROOT / "candidates").mkdir(exist_ok=True)
    (ROOT / "nanopubs" / "unsigned").mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=OLS_WORKERS) as pool:
        for claim in claims:
            claim_iri = claim["iri"]
            candidates = ground(claim, pool)
            claim_id = claim_iri.rsplit("/", 1)[-1]
            record = {"claim": claim_iri, "nanopub": claim["nanopub"], "nanopub_source": claim["nanopub_source"],
                      "label": claim["label"], "grounded_at": now,
                      "services": [GILDA_SERVICE, OLS_SERVICE], "ols_ontologies": OLS_ONTOLOGIES.split(","),
                      "min_score": MIN_SCORE, "allowed_vocabularies": sorted(TERM_IRIS),
                      "excluded_branches": {db: sorted(ids) for db, ids in EXCLUDED_BRANCHES.items()},
                      "generic_terms": sorted(GENERIC_TERMS), "plan": plan,
                      "review": {"status": "pending", "reviewer": None, "decisions": {}},
                      "candidates": candidates}
            (ROOT / "candidates" / f"{claim_id}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
            draft_path = ROOT / "nanopubs" / "unsigned" / f"{claim_id}.trig"
            kept = [c for c in candidates if c["kept"]]
            if kept:
                draft_path.write_text(draft(claim, candidates, plan, now))
            elif draft_path.exists():
                draft_path.unlink()
            print(f"{claim_id}: {len(kept)} kept of {len(candidates)} grounded"
                  + ("" if kept else " (no draft: nothing to link)"))


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if not arguments:
        raise SystemExit(__doc__)
    if arguments[0] == "--local":
        if len(arguments) != 2:
            raise SystemExit(__doc__)
        main(read_local_claims(arguments[1]))
    else:
        main([read_claim(claim_iri) for claim_iri in arguments])
