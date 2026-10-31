"""Ground the entities a Project Delphi claim is about, and draft its subject-matter nanopublication.

For each claim IRI given on the command line, the script reads the published claim from the
nanopublication network, sends its label, description and quoted source text to Gilda (the
grounding service behind INDRA), and keeps the matches from an allowed vocabulary at or above a
minimum score. It then writes:

  candidates/<claim-id>.json          every match Gilda returned, kept or dropped, with the reason
  nanopubs/unsigned/<claim-id>.trig   an unsigned draft made with the Project Delphi claim
                                      subject-matter template: <claim> schema:about <IRI>, one
                                      triple per kept entity, with provenance on what grounded it

Nothing is signed or published. Every draft is reviewed, by a person or a second model, before
it is.

    python3 claim-grounding/build/ground.py <claim-iri> [<claim-iri> ...]
"""

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
SPARQL_ENDPOINT = "https://query.knowledgepixels.com/repo/full"
GILDA_ANNOTATE = "https://grounding.indra.bio/annotate"
GILDA_SERVICE = "https://grounding.indra.bio/"
TEMPLATE = "https://w3id.org/np/RAUScXW9qrWeA-x8TUsvmHkqJJsHTHke8ev4eus4e61qQ/templateVersion"
PUBINFO_TEMPLATES = [
    "https://w3id.org/np/RACJ58Gvyn91LqCKIO9zu1eijDQIeEff28iyDrJgjSJF8",
    "https://w3id.org/np/RAukAcWHRDlkqxk7H2XNSegc1WnHI569INvNr-xdptDGI",
]
AGENT = "https://w3id.org/delphi/resource/agent/delphisci-claim-entity-grounder"
AGENT_LABEL = "delphisci claim entity grounder (Gilda)"
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
}
USER_AGENT = "delphisci/claim-grounding (https://github.com/fractastical/delphi)"


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
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read().decode()


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
select ?np ?label ?description ?quote where {{
  graph npa:graph {{
    ?np npx:introduces <{claim_iri}> ; np:hasAssertion ?a ; np:hasProvenance ?p ;
      npa:hasValidSignatureForPublicKeyHash ?pk .
    filter not exists {{ ?inv npx:invalidates ?np ; npa:hasValidSignatureForPublicKeyHash ?pk . }}
    filter not exists {{ ?sup npx:supersedes ?np ; npa:hasValidSignatureForPublicKeyHash ?pk . }}
  }}
  optional {{ graph ?a {{ <{claim_iri}> rdfs:label ?label }} }}
  optional {{ graph ?a {{ <{claim_iri}> dct:description ?description }} }}
  optional {{ graph ?p {{ ?q schema:text ?quote }} }}
}}""")
    if not rows:
        raise SystemExit(f"no valid, current nanopublication introduces {claim_iri}")
    first = rows[0]
    return {
        "iri": claim_iri,
        "nanopub": first["np"],
        "label": first.get("label", claim_iri.rsplit("/", 1)[-1]),
        "description": first.get("description", ""),
        "quotes": sorted({row["quote"] for row in rows if "quote" in row}),
    }


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


def judge(match):
    """Decide whether a Gilda match becomes a draft link, and why.

    :param match: one Gilda grounding of a mention
    :return: a pair (kept, reason)
    """
    db = match["term"]["db"]
    if db not in TERM_IRIS:
        return False, f"namespace {db} is not in the allowed vocabularies"
    if match["score"] < MIN_SCORE:
        return False, f"score {match['score']:.2f} is below {MIN_SCORE}"
    return True, "allowed vocabulary, score at or above the minimum"


def ground(claim):
    """Ground a claim's texts and judge every match.

    :param claim: the claim as returned by read_claim
    :return: one candidate per distinct grounded term, best match first per mention
    """
    texts = [("label", claim["label"]), ("description", claim["description"])]
    texts += [("quoted source", quote) for quote in claim["quotes"]]
    candidates = {}
    for field, text in texts:
        if not text:
            continue
        for annotation in annotate(text):
            if not annotation.get("matches"):
                continue
            match = annotation["matches"][0]
            term = match["term"]
            key = (term["db"], term["id"])
            kept, reason = judge(match)
            candidate = candidates.setdefault(key, {
                "db": term["db"], "id": term["id"], "name": term["entry_name"],
                "iri": term_iri(term["db"], term["id"]) if kept else None,
                "score": round(match["score"], 4), "kept": kept, "reason": reason, "mentions": []})
            candidate["mentions"].append({"field": field, "text": annotation["text"]})
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
    prov:wasGeneratedBy sub:grounding ;
    prov:wasDerivedFrom <{claim['nanopub']}> .

  <{AGENT}> a prov:SoftwareAgent ;
    rdfs:label {literal(AGENT_LABEL)} ;
    prov:actedOnBehalfOf <{OPERATOR_ORCID}> .

  sub:grounding a prov:Activity ;
    prov:wasAssociatedWith <{AGENT}> ;
    prov:used <{claim['nanopub']}>, <{GILDA_SERVICE}> ;
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


def main(claim_iris):
    """Ground each claim and write its candidates file and unsigned draft.

    :param claim_iris: the IRIs of the claims to ground
    """
    plan, pinned = plan_iri()
    if not pinned:
        print("note: script is not committed, so the drafts name an UNCOMMITTED plan; rebuild after committing")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (ROOT / "candidates").mkdir(exist_ok=True)
    (ROOT / "nanopubs" / "unsigned").mkdir(parents=True, exist_ok=True)
    for claim_iri in claim_iris:
        claim = read_claim(claim_iri)
        candidates = ground(claim)
        claim_id = claim_iri.rsplit("/", 1)[-1]
        record = {"claim": claim_iri, "nanopub": claim["nanopub"], "label": claim["label"],
                  "grounded_at": now, "service": GILDA_SERVICE, "min_score": MIN_SCORE,
                  "allowed_vocabularies": sorted(TERM_IRIS), "plan": plan,
                  "review": {"status": "pending", "reviewer": None, "decisions": {}},
                  "candidates": candidates}
        (ROOT / "candidates" / f"{claim_id}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        kept = [c for c in candidates if c["kept"]]
        if kept:
            (ROOT / "nanopubs" / "unsigned" / f"{claim_id}.trig").write_text(draft(claim, candidates, plan, now))
        print(f"{claim_id}: {len(kept)} kept of {len(candidates)} grounded"
              + ("" if kept else " (no draft: nothing to link)"))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1:])
