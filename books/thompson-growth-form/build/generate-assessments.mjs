// Build the rubric nanopub and one assessment nanopub per (claim, assessor) from
// assessment/assessments.json. Each assessment nanopub holds the overall rubric
// assessment, one assessment per rubric dimension, and the candidate datasets as
// evidence items, all linked to the claim with delphi:hasAssessment.
//
//   node build/generate-assessments.mjs
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const A = join(ROOT, "assessment");
const rubric = JSON.parse(readFileSync(join(A, "rubric.json"), "utf8"));
const assessors = Object.fromEntries(JSON.parse(readFileSync(join(A, "assessors.json"), "utf8")).map(a => [a.id, a]));
const { assessments } = JSON.parse(readFileSync(join(A, "assessments.json"), "utf8"));
const claims = Object.fromEntries(JSON.parse(readFileSync(join(ROOT, "claims.json"), "utf8")).claims.map(c => [c.id, c]));

const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const dirty = git("status --porcelain -- build assessment claims.json") !== "";
const blob = path => `https://github.com/fractastical/delphisci/blob/${commit}/books/thompson-growth-form/${path}`;

const R = "https://w3id.org/delphi/resource/";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const RUBRIC_ID = `${rubric.id}-${rubric.version}`;
const RUBRIC = `${R}concept/${RUBRIC_ID}`;
const dimIri = d => `${R}concept/${RUBRIC_ID}-${d}`;
const BUILDER = `${R}agent/delphisci-thompson-growth-form-builder`;
const BUILDER_MODEL = `${R}model/claude-opus-5.5`;
const DOMAIN = `${R}domain/thompson-growth-form-1917`;

const lit = s => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r")}"`;
const dbl = x => `"${Number(x)}"^^xsd:double`;
const iri = u => `<${u}>`;
const PREFIXES = `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
`;
const head = `sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}
`;
const pubinfo = (created, label, type, introduces) => `sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator ${iri(OWNER)} ;
    rdfs:label ${lit(label)} ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType ${type} ;
    npx:introduces ${iri(introduces)} ;
    delphi:domain ${iri(DOMAIN)} .
  ${iri(DOMAIN)} rdfs:label "thompson-growth-form-1917" .
}
`;
const agentTriples = (agent, label, model, modelLabel, modelId) => `  ${iri(agent)} a prov:SoftwareAgent ;
    rdfs:label ${lit(label)} ;
    delphi:usesModel ${iri(model)} ;
    prov:actedOnBehalfOf ${iri(OWNER)} .
  ${iri(model)} a delphi:LanguageModel ;
    rdfs:label ${lit(modelLabel)}${modelId ? ` ;\n    dct:identifier ${lit(modelId)}` : ""} .
`;

function rubricTrig(created) {
  const dims = rubric.dimensions.map(d => `  ${iri(dimIri(d.id))} a delphi:Concept, skos:Concept ;
    rdfs:label ${lit(`${d.label} (${rubric.id} ${rubric.version})`)} ;
    dct:description ${lit(`Weight ${d.weight}. ${d.question} Anchors: ${Object.entries(d.anchors).map(([k, v]) => `${k} = ${v}`).join("; ")}.`)} ;
    skos:broader ${iri(RUBRIC)} .
`).join("");
  return `${PREFIXES}
${head}
sub:assertion {
  ${iri(RUBRIC)} a delphi:Concept, skos:Concept ;
    rdfs:label ${lit(rubric.label)} ;
    dct:description ${lit(`${rubric.description} Verdicts: ${Object.entries(rubric.verdicts).map(([k, v]) => `${k} = ${v}`).join("; ")}.`)} ;
    rdfs:seeAlso ${iri(blob("assessment/rubric.json"))} ;
    skos:narrower ${rubric.dimensions.map(d => iri(dimIri(d.id))).join(", ")} .
${dims}}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(BUILDER)} , ${iri(OWNER)} ;
    prov:wasDerivedFrom ${iri(blob("assessment/rubric.json"))} .
${agentTriples(BUILDER, "delphisci On Growth and Form pipeline builder", BUILDER_MODEL, "Claude Opus 5.5")}}

${pubinfo(created, `Rubric: ${rubric.label}`, "delphi:Concept", RUBRIC)}`;
}

function assessmentTrig(a, created) {
  const who = assessors[a.assessor];
  const claim = `${R}claim/${a.claim_id}`;
  const base = `${R}assessment/${a.claim_id}--${a.assessor}`;
  const agent = `${R}agent/delphisci-resolvability-assessor-${who.modelId}`;
  const model = `${R}model/${who.modelId}`;
  const ev = a.candidate_datasets.map((d, i) => ({ ...d, iri: `${R}evidence/${a.claim_id}--${a.assessor}--dataset-${i + 1}` }));
  const label = `${who.modelLabel} on ${a.claim_id}: ${a.verdict}, resolvability ${a.overall.toFixed(2)}`;
  const dimAssessments = rubric.dimensions.map(d => `  ${iri(`${base}--${d.id}`)} a delphi:LLMClaimAssessment ;
    rdfs:label ${lit(`${d.label} of ${a.claim_id} by ${who.modelLabel}: ${a.scores[d.id]}`)} ;
    dct:subject ${iri(dimIri(d.id))} ;
    delphi:assessmentType ${lit(`${rubric.id}/${rubric.version}/${d.id}`)} ;
    delphi:hasScore ${dbl(a.scores[d.id])} ;
    dct:isPartOf ${iri(base)} ;
    prov:wasAttributedTo ${iri(agent)} .
  ${iri(claim)} delphi:hasAssessment ${iri(`${base}--${d.id}`)} .
`).join("");
  const evidence = ev.map(d => `  ${iri(d.iri)} a delphi:EvidenceItem ;
    rdfs:label ${lit(`Candidate dataset: ${d.name}`)} ;
    dct:description ${lit(d.role)} ;
    prov:wasDerivedFrom ${iri(d.url)} .
`).join("");
  return `${PREFIXES}
${head}
sub:assertion {
  ${iri(claim)} delphi:hasAssessment ${iri(base)} .
  ${iri(base)} a delphi:LLMClaimAssessment ;
    rdfs:label ${lit(label)} ;
    dct:subject ${iri(RUBRIC)} ;
    delphi:assessmentType ${lit(`${rubric.id}/${rubric.version}`)} ;
    delphi:hasScore ${dbl(a.overall)} ;
    delphi:hasVerdict ${lit(a.verdict)} ;
    delphi:hasConfidence ${dbl(a.confidence)} ;
    dct:description ${lit(a.rationale)} ;
    rdfs:comment ${lit(`Proposed test with existing data: ${a.operationalization}`)} ;
    prov:wasAttributedTo ${iri(agent)}${a.obstacles.length ? ` ;\n    delphi:evidenceAgainst ${a.obstacles.map(lit).join(", ")}` : ""}${ev.length ? ` ;\n    delphi:hasEvidence ${ev.map(d => iri(d.iri)).join(", ")}` : ""} .
${dimAssessments}${evidence}${agentTriples(agent, who.agentLabel, model, who.modelLabel, who.modelId)}}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(agent)} ;
    prov:wasDerivedFrom ${iri(blob(`assessment/raw/${a.assessor}/${a.batch}`))} , ${iri(RUBRIC)} ;
    prov:wasGeneratedBy sub:assessment .
  sub:assessment a prov:Activity ;
    prov:wasAssociatedWith ${iri(agent)} ;
    prov:qualifiedAssociation sub:assessmentPlan .
  sub:assessmentPlan prov:hadPlan ${iri(blob("assessment/INSTRUCTIONS.md"))} .
}

${pubinfo(created, label, "delphi:LLMClaimAssessment", base)}`;
}

const created = new Date().toISOString();
const rubricDir = join(ROOT, "nanopubs/rubric-unsigned");
const outDir = join(ROOT, "nanopubs/assessments-unsigned");
for (const d of [rubricDir, outDir]) { rmSync(d, { recursive: true, force: true }); mkdirSync(d, { recursive: true }); }
writeFileSync(join(rubricDir, `${RUBRIC_ID}.trig`), rubricTrig(created));
for (const a of assessments) {
  if (!claims[a.claim_id]) throw new Error(`unknown claim ${a.claim_id}`);
  writeFileSync(join(outDir, `${a.claim_id}--${a.assessor}.trig`), assessmentTrig(a, created));
}
console.log(`wrote rubric and ${assessments.length} assessment nanopubs (generator commit ${commit}${dirty ? ", working tree DIRTY: drafts only, do not sign" : ""})`);
