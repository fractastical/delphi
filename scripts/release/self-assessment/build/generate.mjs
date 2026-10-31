// Build the rubric nanopub and one assessment nanopub per assessor from assessments.json.
// The thing assessed is the project snapshot (repository at the pinned commit plus the frozen
// evidence pack), not a claim; it is typed prov:Entity / schema:SoftwareSourceCode and linked
// with delphi:hasAssessment like a claim would be.
//
//   node scripts/release/self-assessment/build/generate.mjs
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(HERE, "../../..");
const rubric = JSON.parse(readFileSync(join(HERE, "rubric.json"), "utf8"));
const assessors = Object.fromEntries(JSON.parse(readFileSync(join(HERE, "assessors.json"), "utf8")).map(a => [a.id, a]));
const merged = JSON.parse(readFileSync(join(HERE, "assessments.json"), "utf8"));

const git = cmd => execSync(`git ${cmd}`, { cwd: REPO, encoding: "utf8" }).trim();
const headCommit = git("rev-parse HEAD");
const dirty = git("status --porcelain -- scripts/release/self-assessment") !== "";
const GH = "https://github.com/fractastical/delphi";
const blob = path => `${GH}/blob/${headCommit}/scripts/release/self-assessment/${path}`;
const SNAPSHOT = `${GH}/tree/${merged.commit}`;

const R = "https://w3id.org/delphi/resource/";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const RUBRIC_ID = `${rubric.id}-${rubric.version}`;
const RUBRIC = `${R}concept/${RUBRIC_ID}`;
const dimIri = d => `${R}concept/${RUBRIC_ID}-${d}`;
const BONUS = dimIri(rubric.bonus.id);
const BUILDER = `${R}agent/delphisci-self-assessment-builder`;
const BUILDER_MODEL = `${R}model/claude-fable-5.1`;
const DOMAIN = `${R}domain/delphisci-project`;

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
@prefix schema: <https://schema.org/> .
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
  ${iri(DOMAIN)} rdfs:label "delphisci project self-assessment" .
}
`;
const agentTriples = (agent, label, model, modelLabel, modelId) => `  ${iri(agent)} a prov:SoftwareAgent ;
    rdfs:label ${lit(label)} ;
    delphi:usesModel ${iri(model)} ;
    prov:actedOnBehalfOf ${iri(OWNER)} .
  ${iri(model)} a delphi:LanguageModel ;
    rdfs:label ${lit(modelLabel)}${modelId ? ` ;\n    dct:identifier ${lit(modelId)}` : ""} .
`;
const anchors = a => Object.entries(a).map(([k, v]) => `${k} = ${v}`).join("; ");

function rubricTrig(created) {
  const dims = rubric.dimensions.map(d => `  ${iri(dimIri(d.id))} a delphi:Concept, skos:Concept ;
    rdfs:label ${lit(`${d.label} (${rubric.id} ${rubric.version})`)} ;
    dct:description ${lit(`Weight ${d.weight}. ${d.question} Anchors (0-10): ${anchors(d.anchors)}.`)} ;
    skos:broader ${iri(RUBRIC)} .
`).join("");
  const bonus = `  ${iri(BONUS)} a delphi:Concept, skos:Concept ;
    rdfs:label ${lit(`${rubric.bonus.label} (${rubric.id} ${rubric.version})`)} ;
    dct:description ${lit(`Scored separately, up to ${rubric.bonus.max}, not part of the weighted total. ${rubric.bonus.question} Anchors (0-10): ${anchors(rubric.bonus.anchors)}.`)} ;
    skos:broader ${iri(RUBRIC)} .
`;
  return `${PREFIXES}
${head}
sub:assertion {
  ${iri(RUBRIC)} a delphi:Concept, skos:Concept ;
    rdfs:label ${lit(rubric.label)} ;
    dct:description ${lit(rubric.description)} ;
    dct:source ${iri(rubric.source)} ;
    rdfs:seeAlso ${iri(blob("rubric.json"))} ;
    skos:narrower ${[...rubric.dimensions.map(d => iri(dimIri(d.id))), iri(BONUS)].join(", ")} .
${dims}${bonus}}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(BUILDER)} , ${iri(OWNER)} ;
    prov:wasDerivedFrom ${iri(blob("rubric.json"))} , ${iri(rubric.source)} .
${agentTriples(BUILDER, "delphisci self-assessment pipeline builder", BUILDER_MODEL, "Claude Fable 5.1")}}

${pubinfo(created, `Rubric: ${rubric.label}`, "delphi:Concept", RUBRIC)}`;
}

function assessmentTrig(a, created) {
  const who = assessors[a.assessor];
  const snap = merged.commit.slice(0, 8);
  const base = `${R}assessment/delphisci-${snap}--${RUBRIC_ID}--${a.assessor}`;
  const agent = `${R}agent/delphisci-scienceclaw-rubric-assessor-${who.modelId}`;
  const model = `${R}model/${who.modelId}`;
  const label = `${who.modelLabel} on delphisci@${snap} (Science Claw rubric): ${a.weighted_total}/100, bonus ${a.bonus}/10`;
  const dimAssessments = rubric.dimensions.map(d => `  ${iri(`${base}--${d.id}`)} a delphi:LLMClaimAssessment ;
    rdfs:label ${lit(`${d.label} of delphisci@${snap} by ${who.modelLabel}: ${a.scores[d.id]}/10`)} ;
    dct:subject ${iri(dimIri(d.id))} ;
    delphi:assessmentType ${lit(`${rubric.id}/${rubric.version}/${d.id}`)} ;
    delphi:hasScore ${dbl(a.scores[d.id] / 10)} ;
    dct:description ${lit(a.justifications[d.id])} ;${(a.gaps?.[d.id] ?? []).length ? `\n    delphi:evidenceAgainst ${a.gaps[d.id].map(lit).join(", ")} ;` : ""}
    dct:isPartOf ${iri(base)} ;
    prov:wasAttributedTo ${iri(agent)} .
  ${iri(SNAPSHOT)} delphi:hasAssessment ${iri(`${base}--${d.id}`)} .
`).join("");
  const bonus = `  ${iri(`${base}--${rubric.bonus.id}`)} a delphi:LLMClaimAssessment ;
    rdfs:label ${lit(`${rubric.bonus.label} of delphisci@${snap} by ${who.modelLabel}: ${a.bonus}/10`)} ;
    dct:subject ${iri(BONUS)} ;
    delphi:assessmentType ${lit(`${rubric.id}/${rubric.version}/${rubric.bonus.id}`)} ;
    delphi:hasScore ${dbl(a.bonus / 10)} ;
    dct:description ${lit(a.justifications[rubric.bonus.id] ?? "")} ;${(a.gaps?.[rubric.bonus.id] ?? []).length ? `\n    delphi:evidenceAgainst ${a.gaps[rubric.bonus.id].map(lit).join(", ")} ;` : ""}
    dct:isPartOf ${iri(base)} ;
    prov:wasAttributedTo ${iri(agent)} .
  ${iri(SNAPSHOT)} delphi:hasAssessment ${iri(`${base}--${rubric.bonus.id}`)} .
`;
  const fixes = (a.top_three_fixes ?? []).map((f, i) => `${i + 1}. ${f}`).join(" ");
  return `${PREFIXES}
${head}
sub:assertion {
  ${iri(SNAPSHOT)} a prov:Entity, schema:SoftwareSourceCode ;
    rdfs:label ${lit(`delphisci (fractastical/delphi) at commit ${merged.commit}`)} ;
    schema:codeRepository ${iri(GH)} ;
    dct:description ${lit(`Project snapshot assessed through the frozen evidence pack (sha256 ${merged.evidence_pack_sha256}), captured ${merged.capturedAt}.`)} ;
    delphi:hasAssessment ${iri(base)} .
  ${iri(base)} a delphi:LLMClaimAssessment ;
    rdfs:label ${lit(label)} ;
    dct:subject ${iri(RUBRIC)} ;
    delphi:assessmentType ${lit(`${rubric.id}/${rubric.version}`)} ;
    delphi:hasScore ${dbl(a.weighted_total / 100)} ;
    delphi:hasConfidence ${dbl(a.confidence)} ;
    dct:description ${lit(a.summary)} ;
    rdfs:comment ${lit(`Weighted total ${a.weighted_total}/100 (weights ${rubric.dimensions.map(d => `${d.id} ${d.weight}`).join(", ")}); collaboration bonus ${a.bonus}/10 scored separately. Comparison multi- vs single-agent found: ${a.comparison_found?.found ? "yes" : "no"}. ${a.comparison_found?.note ?? ""} Top fixes: ${fixes}`)} ;
    prov:wasAttributedTo ${iri(agent)} .
${dimAssessments}${bonus}${agentTriples(agent, who.agentLabel, model, who.modelLabel, who.modelId)}}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(agent)} ;
    prov:wasDerivedFrom ${iri(blob(a.file))} , ${iri(blob("evidence/MANIFEST.json"))} , ${iri(RUBRIC)} ;
    prov:wasGeneratedBy sub:assessment .
  sub:assessment a prov:Activity ;
    rdfs:comment "Blind assessment: the assessor saw only the rubric and the frozen evidence pack, not the builders' view or other assessors' output. The builder's model provider (Anthropic) did not assess." ;
    prov:used ${iri(SNAPSHOT)} ;
    prov:wasAssociatedWith ${iri(agent)} ;
    prov:qualifiedAssociation sub:assessmentPlan .
  sub:assessmentPlan prov:hadPlan ${iri(blob("INSTRUCTIONS.md"))} .
}

${pubinfo(created, label, "delphi:LLMClaimAssessment", base)}`;
}

const created = new Date().toISOString();
for (const d of ["nanopubs/rubric-unsigned", "nanopubs/assessments-unsigned"]) { rmSync(join(HERE, d), { recursive: true, force: true }); mkdirSync(join(HERE, d), { recursive: true }); }
writeFileSync(join(HERE, "nanopubs/rubric-unsigned", `${RUBRIC_ID}.trig`), rubricTrig(created));
for (const a of merged.assessments) writeFileSync(join(HERE, "nanopubs/assessments-unsigned", `delphisci-${merged.commit.slice(0, 8)}--${a.assessor}.trig`), assessmentTrig(a, created));
console.log(`wrote rubric + ${merged.assessments.length} assessment nanopubs (generator commit ${headCommit}${dirty ? ", self-assessment tree DIRTY: blob links will not resolve until committed" : ""})`);
