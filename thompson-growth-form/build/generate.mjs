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

const { source, claims } = JSON.parse(readFileSync(join(ROOT, "claims.json"), "utf8"));

const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const dirty = git("status --porcelain -- build inputs extraction claims.json") !== "";

const EDITION = "https://www.gutenberg.org/ebooks/55264";      // 1917 first edition as digitised by Project Gutenberg
const WORK = "http://www.wikidata.org/entity/Q19902738";       // On Growth and Form (the work)
const THOMPSON = "http://www.wikidata.org/entity/Q739438";
const TEXT_FILE = "https://www.gutenberg.org/cache/epub/55264/pg55264.txt";
const AGENT = "https://w3id.org/delphi/resource/agent/delphisci-thompson-growth-form-extractor";
const MODEL = "https://w3id.org/delphi/resource/model/claude-opus-5.5";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const GENERATOR = `https://github.com/fractastical/delphisci/blob/${commit}/thompson-growth-form/build/generate.mjs`;
const DOMAIN = "thompson-growth-form-1917";

const CHAPTER_TITLES = {
  I: "Introductory", II: "On Magnitude", III: "The Rate of Growth", IV: "On the Internal Form and Structure of the Cell",
  V: "The Forms of Cells", VI: "A Note on Adsorption", VII: "The Forms of Tissues, or Cell-Aggregates",
  VIII: "The Forms of Tissues, or Cell-Aggregates (continued)", IX: "On Concretions, Spicules, and Spicular Skeletons",
  X: "A Parenthetic Note on Geodetics", XI: "The Logarithmic Spiral", XII: "The Spiral Shells of the Foraminifera",
  XIII: "The Shapes of Horns, and of Teeth or Tusks: with a Note on Torsion", XIV: "On Leaf-Arrangement, or Phyllotaxis",
  XV: "On the Shapes of Eggs, and of Certain Other Hollow Structures", XVI: "On Form and Mechanical Efficiency",
  XVII: "On the Theory of Transformations, or the Comparison of Related Forms", Epilogue: "Epilogue",
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
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix spdx: <http://spdx.org/rdf/terms#> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
@prefix delphir: <https://w3id.org/delphi/resource/> .
`;

function trig(c, created) {
  const claim = `<https://w3id.org/delphi/resource/claim/${c.id}>`;
  const chapter = c.chapter === "Epilogue" ? "the Epilogue" : `Chapter ${c.chapter}, “${CHAPTER_TITLES[c.chapter]}”`;
  const context = `D’Arcy Wentworth Thompson, On Growth and Form (1st ed., Cambridge: Cambridge University Press, 1917), ${chapter}; topic “${c.section}”. Scope: ${c.scope}`;
  // RFC 5147 text/plain fragment: line=a,b selects the lines after position a up to position b.
  const locator = `${TEXT_FILE}#line=${c.lineStart - 1},${c.lineEnd}`;
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
    dct:description ${lit(c.claim)} ;${c.notation ? `
    skos:notation ${lit(c.notation)} ;` : ""}
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
    prov:hadPrimarySource <${locator}> .

  <${locator}> schema:isPartOf <${TEXT_FILE}> .

  <${EDITION}> dct:title ${lit("On Growth and Form")} ;
    dct:creator <${THOMPSON}> ;
    dct:date "1917"^^xsd:gYear ;
    schema:publisher "Cambridge University Press" ;
    schema:bookEdition "1" ;
    schema:exampleOfWork <${WORK}> .

  <${TEXT_FILE}> schema:about <${EDITION}> ;
    spdx:checksum sub:sourceChecksum .
  sub:sourceChecksum spdx:algorithm spdx:checksumAlgorithm_sha256 ;
    spdx:checksumValue ${lit(source.sha256)} .

  sub:extraction a prov:Activity ;
    prov:used <${TEXT_FILE}> ;
    prov:wasAssociatedWith <${AGENT}> ;
    prov:qualifiedAssociation sub:extractionPlan .
  sub:extractionPlan prov:hadPlan <${GENERATOR}> .

  <${AGENT}> a prov:SoftwareAgent ;
    rdfs:label "delphisci On Growth and Form claim extractor" ;
    delphi:usesModel <${MODEL}> ;
    prov:actedOnBehalfOf <${OWNER}> .
  <${MODEL}> a delphi:LanguageModel ;
    rdfs:label "Claude Opus 5.5" .
}

sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator <${OWNER}> ;
    rdfs:label ${lit(`Thompson 1917 claim: ${c.label}`)} ;
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
