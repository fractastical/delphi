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
const works = Object.fromEntries(JSON.parse(readFileSync(join(ROOT, "inputs/sources.json"), "utf8")).works.map(w => [w.key, w]));

const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const dirty = git("status --porcelain -- build inputs extraction claims.json") !== "";

const ARISTOTLE = "http://www.wikidata.org/entity/Q868";
const AGENT = "https://w3id.org/delphi/resource/agent/delphisci-aristotle-biology-extractor";
const MODEL = "https://w3id.org/delphi/resource/model/claude-opus-5.5";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const GENERATOR = `https://github.com/fractastical/delphisci/blob/${commit}/claim-sources/aristotle-biology/build/generate.mjs`;
const TEXT_BASE = `https://raw.githubusercontent.com/fractastical/delphisci/${commit}/claim-sources/aristotle-biology/inputs/`;
const DOMAIN = "aristotle-biology";

const WORK_TITLES = { ha: "History of Animals", pa: "Parts of Animals", ga: "Generation of Animals" };

const lit = s => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r")}"`;
const PREFIXES = `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix spdx: <http://spdx.org/rdf/terms#> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
@prefix delphir: <https://w3id.org/delphi/resource/> .
`;

function trig(c, created) {
  const w = works[c.work];
  const claim = `<https://w3id.org/delphi/resource/claim/${c.id}>`;
  // The Oxford translation is identified by the page we took it from; the work is the Wikidata item.
  const edition = w.landing_url;
  const textFile = `${TEXT_BASE}${w.text_file}`;
  const where = `Book ${c.book}${c.section ? `, ${c.section}` : ""}`;
  const context = `Aristotle, ${w.title} (${w.latin}), ${where}; translated by ${w.translator}, ${w.edition}. Scope: ${c.scope}`;
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
  sub:assertion prov:wasDerivedFrom <${edition}> , sub:quote ;
    prov:wasAttributedTo <${AGENT}> ;
    prov:wasGeneratedBy sub:extraction .

  sub:quote a prov:Entity ;
    schema:text ${lit(c.quote)} ;
    prov:wasQuotedFrom <${edition}> ;
    prov:hadPrimarySource <${locator}> .

  <${locator}> schema:isPartOf <${textFile}> .

  <${edition}> a schema:Book ;
    dct:title ${lit(`${w.title}, translated by ${w.translator}`)} ;
    dct:creator <${ARISTOTLE}> ;
    schema:translator ${lit(w.translator)} ;
    dct:bibliographicCitation ${lit(`Aristotle. ${w.title} (${w.latin}). Translated by ${w.translator}. ${w.edition}.`)} ;
    dct:date "${w.translation_year}"^^xsd:gYear ;
    schema:translationOfWork <${w.wikidata}> .

  <${textFile}> schema:about <${edition}> ;
    prov:wasDerivedFrom ${w.files.map(f => `<${f.download_url}>`).join(" , ")} ;
    spdx:checksum sub:sourceChecksum .
  sub:sourceChecksum spdx:algorithm spdx:checksumAlgorithm_sha256 ;
    spdx:checksumValue ${lit(w.text_sha256)} .

  sub:extraction a prov:Activity ;
    prov:used <${textFile}> ;
    prov:wasAssociatedWith <${AGENT}> ;
    prov:qualifiedAssociation sub:extractionPlan .
  sub:extractionPlan prov:hadPlan <${GENERATOR}> .

  <${AGENT}> a prov:SoftwareAgent ;
    rdfs:label "delphisci Aristotle biology claim extractor" ;
    delphi:usesModel <${MODEL}> ;
    prov:actedOnBehalfOf <${OWNER}> .
  <${MODEL}> a delphi:LanguageModel ;
    rdfs:label "Claude Opus 5.5" .
}

sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator <${OWNER}> ;
    rdfs:label ${lit(`Aristotle, ${WORK_TITLES[c.work]} ${c.book}: ${c.label}`)} ;
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
