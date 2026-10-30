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

const EDITION = "http://www.wikidata.org/entity/Q20968204"; // 1859 first edition (Gutenberg #1228)
const WORK = "http://www.wikidata.org/entity/Q20124";        // On the Origin of Species (the work)
const DARWIN = "http://www.wikidata.org/entity/Q1035";
const TEXT_FILE = "https://www.gutenberg.org/cache/epub/1228/pg1228.txt";
const AGENT = "https://w3id.org/delphi/resource/agent/delphisci-darwin-origin-extractor";
const MODEL = "https://w3id.org/delphi/resource/model/claude-opus-5.5";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const GENERATOR = `https://github.com/fractastical/delphisci/blob/${commit}/darwin-origin/build/generate.mjs`;
const DOMAIN = "darwin-origin-1859";

const CHAPTER_TITLES = {
  Introduction: "Introduction", I: "Variation under Domestication", II: "Variation under Nature",
  III: "Struggle for Existence", IV: "Natural Selection", V: "Laws of Variation", VI: "Difficulties on Theory",
  VII: "Instinct", VIII: "Hybridism", IX: "On the Imperfection of the Geological Record",
  X: "On the Geological Succession of Organic Beings", XI: "Geographical Distribution",
  XII: "Geographical Distribution, continued", XIII: "Mutual Affinities of Organic Beings: Morphology: Embryology: Rudimentary Organs",
  XIV: "Recapitulation and Conclusion",
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
  const chapter = c.chapter === "Introduction" ? "the Introduction" : `Chapter ${c.chapter}, “${CHAPTER_TITLES[c.chapter]}”`;
  const context = `Charles Darwin, On the Origin of Species (1st ed., London: John Murray, 1859), ${chapter}; section “${c.section}”. Scope: ${c.scope}`;
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
    prov:hadPrimarySource <${locator}> .

  <${locator}> schema:isPartOf <${TEXT_FILE}> .

  <${EDITION}> dct:title ${lit("On the Origin of Species by Means of Natural Selection, or the Preservation of Favoured Races in the Struggle for Life")} ;
    dct:creator <${DARWIN}> ;
    dct:date "1859"^^xsd:gYear ;
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
    rdfs:label "delphisci Origin of Species claim extractor" ;
    delphi:usesModel <${MODEL}> ;
    prov:actedOnBehalfOf <${OWNER}> .
  <${MODEL}> a delphi:LanguageModel ;
    rdfs:label "Claude Opus 5.5" .
}

sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator <${OWNER}> ;
    rdfs:label ${lit(`Darwin 1859 claim: ${c.label}`)} ;
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
