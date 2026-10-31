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
const index = JSON.parse(readFileSync(join(ROOT, "inputs/pages.json"), "utf8"));
const pageSha = Object.fromEntries(index.pages.map(p => [p.page, p.sha256]));

const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const dirty = git("status --porcelain -- build inputs/pages.json extraction claims.json") !== "";

const EDITION = "http://www.wikidata.org/entity/Q60413467"; // 2002 Wolfram Media edition
const WORK = "http://www.wikidata.org/entity/Q2987018";     // A New Kind of Science (the work)
const WOLFRAM = "http://www.wikidata.org/entity/Q310798";
const ISBN = "urn:isbn:978-1-57955-008-0";
const ONLINE = "https://www.wolframscience.com/nks/";
const PERMISSIONS = "https://www.wolframscience.com/nks/piv--copyright/";
const AGENT = "https://w3id.org/delphi/resource/agent/delphisci-wolfram-nks-extractor";
const MODEL = "https://w3id.org/delphi/resource/model/claude-opus-5.5";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const blob = path => `https://github.com/fractastical/delphisci/blob/${commit}/books/wolfram-nks/${path}`;
const DOMAIN = "wolfram-nks-2002";
const RIGHTS = "Verbatim quotation from A New Kind of Science, © 2002 Stephen Wolfram, LLC, all rights reserved; quoted for scholarly purposes with citation, as the book's copyright notice permits.";

const CHAPTER_TITLES = {
  1: "The Foundations for a New Kind of Science", 2: "The Crucial Experiment", 3: "The World of Simple Programs",
  4: "Systems Based on Numbers", 5: "Two Dimensions and Beyond", 6: "Starting from Randomness",
  7: "Mechanisms in Programs and Nature", 8: "Implications for Everyday Systems", 9: "Fundamental Physics",
  10: "Processes of Perception and Analysis", 11: "The Notion of Computation", 12: "The Principle of Computational Equivalence",
};

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
  const claim = `<https://w3id.org/delphi/resource/claim/${c.id}>`;
  const pages = c.pageEnd === c.pageStart ? `p. ${c.pageStart}` : `pp. ${c.pageStart}–${c.pageEnd}`;
  const context = `Stephen Wolfram, A New Kind of Science (Champaign, IL: Wolfram Media, 2002), Chapter ${c.chapter}, “${CHAPTER_TITLES[c.chapter]}”; section “${c.section}” (from p. ${c.sectionStart}), ${pages}. Scope: ${c.scope}`;
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
  sub:assertion prov:wasDerivedFrom <${EDITION}> , sub:quote ;
    prov:wasAttributedTo <${AGENT}> ;
    prov:wasGeneratedBy sub:extraction .

  sub:quote a prov:Entity ;
    schema:text ${lit(c.quote)} ;
    prov:wasQuotedFrom <${EDITION}> ;
    prov:hadPrimarySource <${c.url}> ;
    schema:pagination ${lit(pages)} ;
    dct:rights ${lit(RIGHTS)} ;
    rdfs:seeAlso <${PERMISSIONS}> .

  <${c.url}> schema:isPartOf <${ONLINE}> ;
    schema:pagination ${lit(String(c.pageStart))} .
  sub:pageText a prov:Entity ;
    prov:wasDerivedFrom <${c.url}> ;
    rdfs:comment "Plain text of the cited page as extracted by the pipeline's fetch step (headings, paragraphs and figure captions, whitespace collapsed); the checksum is of this text, not of the HTML." ;
    spdx:checksum sub:pageTextChecksum .
  sub:pageTextChecksum spdx:algorithm spdx:checksumAlgorithm_sha256 ;
    spdx:checksumValue ${lit(pageSha[c.pageStart])} .

  <${EDITION}> dct:title "A New Kind of Science" ;
    dct:creator <${WOLFRAM}> ;
    dct:publisher "Wolfram Media" ;
    dct:date "2002"^^xsd:gYear ;
    dct:identifier <${ISBN}> ;
    schema:exampleOfWork <${WORK}> .
  <${ONLINE}> schema:about <${EDITION}> .

  sub:extraction a prov:Activity ;
    prov:used <${c.url}> , sub:pageText ;
    prov:wasAssociatedWith <${AGENT}> ;
    prov:qualifiedAssociation sub:extractionPlan .
  sub:extractionPlan prov:hadPlan <${blob("build/generate.mjs")}> , <${blob("extraction/INSTRUCTIONS.md")}> .

  <${AGENT}> a prov:SoftwareAgent ;
    rdfs:label "delphisci A New Kind of Science claim extractor" ;
    delphi:usesModel <${MODEL}> ;
    prov:actedOnBehalfOf <${OWNER}> .
  <${MODEL}> a delphi:LanguageModel ;
    rdfs:label "Claude Opus 5.5" .
}

sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator <${OWNER}> ;
    rdfs:label ${lit(`Wolfram 2002 claim: ${c.label}`)} ;
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
