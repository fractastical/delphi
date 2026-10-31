// Build one unsigned claim nanopub (TriG, temp base) per entry in claims.json.
// Signing replaces the temp base with the trusty URI (nanopub-js or `np sign`).
//
//   node build/generate.mjs [--out nanopubs/unsigned]
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const outArg = process.argv.indexOf("--out");
const OUT = join(ROOT, outArg > -1 ? process.argv[outArg + 1] : "nanopubs/unsigned");

const { claims } = JSON.parse(readFileSync(join(ROOT, "claims.json"), "utf8"));
const papers = Object.fromEntries(JSON.parse(readFileSync(join(ROOT, "inputs/sources.json"), "utf8")).papers.map(p => [p.key, p]));

const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const dirty = git("status --porcelain -- build inputs extraction claims.json") !== "";

const LEVIN = "http://www.wikidata.org/entity/Q39444955";
const AGENT = "https://w3id.org/delphi/resource/agent/delphisci-levin-papers-extractor";
const MODEL = "https://w3id.org/delphi/resource/model/claude-opus-5.5";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const GENERATOR = `https://github.com/fractastical/delphisci/blob/${commit}/books/levin-papers/build/generate.mjs`;
const TEXT_BASE = `https://raw.githubusercontent.com/fractastical/delphisci/${commit}/books/levin-papers/inputs/`;
const DOMAIN = "levin-papers";

const lit = s => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r")}"`;
const PREFIXES = `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix spdx: <http://spdx.org/rdf/terms#> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
@prefix delphir: <https://w3id.org/delphi/resource/> .
`;

function trig(c, created) {
  const p = papers[c.paper];
  const claim = `<https://w3id.org/delphi/resource/claim/${c.id}>`;
  const article = `https://doi.org/${p.doi}`;
  const textFile = `${TEXT_BASE}${p.text_file}`;
  const context = `${p.authors}, “${p.title}”, ${p.journal} (${p.year}), doi:${p.doi}; section “${c.section}”. Scope: ${c.scope}`;
  // RFC 5147 text/plain fragment: line=a,b selects the lines after position a up to position b.
  const locator = `${textFile}#line=${c.lineStart - 1},${c.lineEnd}`;
  return `${PREFIXES}
sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}

sub:assertion {
  ${claim} a delphi:Claim ;
    rdfs:label ${lit(c.label)} ;
    dct:description ${lit(c.claim)} ;
    delphi:context ${lit(context)} ;
    dct:type ${lit(c.claim_kind)} .
}

sub:provenance {
  sub:assertion prov:wasDerivedFrom <${article}> , sub:quote ;
    prov:wasAttributedTo <${AGENT}> ;
    prov:wasGeneratedBy sub:extraction .

  sub:quote a prov:Entity ;
    schema:text ${lit(c.quote)} ;
    prov:wasQuotedFrom <${article}> ;
    prov:hadPrimarySource <${locator}> .

  <${locator}> schema:isPartOf <${textFile}> .

  <${article}> a schema:ScholarlyArticle ;
    dct:title ${lit(p.title)} ;
    dct:creator <${LEVIN}> ;
    dct:bibliographicCitation ${lit(`${p.authors}. ${p.title}. ${p.journal} (${p.year}). doi:${p.doi}`)} ;
    dct:date "${p.year}"^^xsd:gYear ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    schema:sameAs <${p.landing_url}> .

  <${textFile}> schema:about <${article}> ;
    prov:wasDerivedFrom <${p.xml.download_url}> ;
    spdx:checksum sub:sourceChecksum .
  sub:sourceChecksum spdx:algorithm spdx:checksumAlgorithm_sha256 ;
    spdx:checksumValue ${lit(p.text_sha256)} .

  sub:extraction a prov:Activity ;
    prov:used <${textFile}> ;
    prov:wasAssociatedWith <${AGENT}> ;
    prov:qualifiedAssociation sub:extractionPlan .
  sub:extractionPlan prov:hadPlan <${GENERATOR}> .

  <${AGENT}> a prov:SoftwareAgent ;
    rdfs:label "delphisci Levin papers claim extractor" ;
    delphi:usesModel <${MODEL}> ;
    prov:actedOnBehalfOf <${OWNER}> .
  <${MODEL}> a delphi:LanguageModel ;
    rdfs:label "Claude Opus 5.5" .
}

sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator <${OWNER}> ;
    rdfs:label ${lit(`Levin ${p.year} claim: ${c.label}`)} ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType delphi:Claim ;
    npx:introduces ${claim} ;
    delphi:domain <https://w3id.org/delphi/resource/domain/${DOMAIN}> .
  <https://w3id.org/delphi/resource/domain/${DOMAIN}> rdfs:label "${DOMAIN}" .
}
`;
}

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
const created = new Date().toISOString();
for (const c of claims) writeFileSync(join(OUT, `${c.id}.trig`), trig(c, created));
console.log(`wrote ${claims.length} nanopubs to ${OUT} (generator commit ${commit}${dirty ? ", working tree DIRTY: drafts only, do not sign" : ""})`);
