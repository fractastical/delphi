// Build one unsigned evidence nanopub per completed claim test (claim-tests/<project>/<id>/result.json).
//
// The assertion is a delphi:Assessment of type "claim-test/0.1.0" on the claim: hypothesis,
// pre-registered criteria, method, measured value, verdict, confidence, caveats, and one
// delphi:EvidenceItem per dataset used (with the SHA-256 of each file). If the result carries
// `revisions`, each is recorded as a prov:Activity that revised the assessment, with the
// reason, the null result it rests on, and the outside agents who prompted it as prov:Agents
// (dct:contributor). Written to claim-tests/nanopubs/unsigned/<id>.trig; signing and
// publishing are separate, deliberate steps (see BEST_PRACTICES.md).
//
//   node claim-tests/build-test-nanopubs.mjs [claim-id ...]
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, "..");
const OUT = join(HERE, "nanopubs", "unsigned");
const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const blob = path => `https://github.com/fractastical/delphisci/blob/${commit}/${path}`;

const R = "https://w3id.org/delphi/resource/";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const DOMAINS = { "darwin-origin": "darwin-origin-1859", "thompson-growth-form": "thompson-growth-form-1917", "wolfram-nks": "wolfram-nks-2002" };

const lit = s => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r")}"`;
const dbl = x => `"${Number(x)}"^^xsd:double`;
const iri = u => `<${String(u).trim().replace(/[ <>"{}|\\^`]/g, ch => encodeURIComponent(ch))}>`;
const slug = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
// The four test-contract fields (claim-tests/README.md), falling back to the pre-registration fields.
export const testContract = r => ({
  expected_observation: r.test_contract?.expected_observation ?? r.pass_criterion ?? "",
  disconfirming_observation: r.test_contract?.disconfirming_observation ?? r.fail_criterion ?? "",
  admissible_datasets: r.test_contract?.admissible_datasets ?? (r.planned_datasets?.length ? `Planned datasets: ${r.planned_datasets.join(", ")}` : ""),
  inference_method: r.test_contract?.inference_method ?? r.method ?? "",
  explicit: !!r.test_contract,
});

const PREFIXES = `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix foaf: <http://xmlns.com/foaf/0.1/> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
`;

function trig(project, id, r) {
  const claim = `${R}claim/${id}`;
  const A = `${R}assessment/${id}--claim-test`;
  const agent = `${R}agent/delphisci-claim-tester-${slug(r.agent?.model ?? "unknown")}`;
  const model = `${R}model/${slug(r.agent?.model ?? "unknown")}`;
  const path = `claim-tests/${project}/${id}/result.json`;
  const domain = `${R}domain/${DOMAINS[project] ?? project}`;
  const created = new Date().toISOString();
  const summary = r.measured ? `${r.measured.value} ${r.measured.unit}` : "";
  const tc = testContract(r);

  const evidence = (r.datasets ?? []).map((d, i) => {
    const e = `${R}evidence/${id}--claim-test--dataset-${i + 1}`;
    const files = (d.files ?? []).map(f => `    delphi:hasChecksum ${lit("sha256:" + f.sha256)} ;\n    prov:atLocation ${iri(f.download_url)} ;`).join("\n");
    return `  ${iri(e)} a delphi:EvidenceItem ;
    rdfs:label ${lit(`Dataset: ${d.name}`)} ;
    dct:description ${lit(d.role ?? "")} ;
${files}
    dct:license ${lit(d.license ?? "")} ;
    prov:wasDerivedFrom ${iri(d.landing_url)} .
`;
  });

  const revisions = (r.revisions ?? []).map((v, i) => {
    const act = `${R}activity/${id}--claim-test--revision-${i + 1}`;
    const people = (v.prompted_by ?? []).map((p, j) => {
      const who = `${R}agent/moltbook-${slug(p.agent)}`;
      return { who, trig: `  ${iri(who)} a prov:Agent ;
    foaf:name ${lit(p.agent)} ;
    rdfs:comment ${lit(p.contribution)} ;
    rdfs:seeAlso ${iri(p.comment)} .
` };
    });
    return {
      who: people.map(p => p.who),
      assertion: `  ${iri(act)} a prov:Activity ;
    rdfs:label ${lit(`Revision ${i + 1} of the ${id} claim test (${v.date})`)} ;
    dct:description ${lit(v.reason)} ;
    prov:startedAtTime "${v.date}"^^xsd:date ;
    prov:used ${iri(blob(v.null_result))} ;
    delphi:evidenceAgainst ${lit(`Before: ${v.from.summary} (confidence ${v.from.confidence}). After: ${v.to.summary} (confidence ${v.to.confidence}).`)} ;
    prov:wasInformedBy ${people.map(p => iri(p.who)).join(", ") || "()"} .
${people.map(p => p.trig).join("")}  ${iri(A)} prov:qualifiedRevision ${iri(act)} ;
    dct:contributor ${people.map(p => iri(p.who)).join(", ")} .
`,
    };
  });

  return `${PREFIXES}
sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}

sub:assertion {
  ${iri(A)} a delphi:Assessment ;
    rdfs:label ${lit(`Claim test of ${id}: ${r.verdict}, confidence ${r.confidence}`)} ;
    delphi:assessmentType "claim-test/0.1.0" ;
    delphi:hasVerdict ${lit(r.verdict)} ;
    delphi:hasConfidence ${dbl(r.confidence)} ;
    delphi:hypothesis ${lit(r.hypothesis ?? "")} ;
    delphi:passCriterion ${lit(r.pass_criterion ?? "")} ;
    delphi:failCriterion ${lit(r.fail_criterion ?? "")} ;
    delphi:expectedObservation ${lit(tc.expected_observation)} ;
    delphi:disconfirmingObservation ${lit(tc.disconfirming_observation)} ;
    delphi:admissibleDatasets ${lit(tc.admissible_datasets)} ;
    delphi:inferenceMethod ${lit(tc.inference_method)} ;
    delphi:preregistered ${r.preregistered ? "true" : "false"} ;
    dct:description ${lit(r.method ?? "")} ;
    rdfs:comment ${lit(`Measured: ${summary}${r.measured?.n != null ? ` (n = ${r.measured.n}${r.measured.uncertainty ? `, ${r.measured.uncertainty}` : ""})` : ""}. Interpretation: ${r.interpretation ?? ""}`)} ;
${(r.caveats ?? []).map(c => `    delphi:evidenceAgainst ${lit(c)} ;`).join("\n")}
    delphi:hasEvidence ${evidence.length ? (r.datasets.map((_, i) => iri(`${R}evidence/${id}--claim-test--dataset-${i + 1}`)).join(", ")) : "()"} ;
    prov:wasAttributedTo ${iri(agent)} ;
    rdfs:seeAlso ${iri(blob(path))} .
${evidence.join("")}${revisions.map(v => v.assertion).join("")}  ${iri(claim)} delphi:hasAssessment ${iri(A)} .
}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(agent)} ;
    prov:wasDerivedFrom ${iri(blob(path))}${r.revisions?.length ? `, ${iri(blob(r.revisions.at(-1).null_result))}` : ""} ;
    prov:wasGeneratedBy sub:test .
  sub:test a prov:Activity ;
    prov:wasAssociatedWith ${iri(agent)} ;
    prov:qualifiedAssociation sub:plan .
  sub:plan prov:hadPlan ${iri(blob("claim-tests/README.md"))} .
  ${iri(agent)} a prov:SoftwareAgent ;
    rdfs:label ${lit(`delphisci claim tester (${r.agent?.model ?? "unknown"}; ${r.agent?.run ?? ""})`)} ;
    delphi:usesModel ${iri(model)} ;
    prov:actedOnBehalfOf ${iri(OWNER)} .
  ${iri(model)} a delphi:LanguageModel ;
    dct:identifier ${lit(r.agent?.model ?? "unknown")} .
}

sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator ${iri(OWNER)} ;
    rdfs:label ${lit(`Claim test of ${id}: ${r.verdict}, confidence ${r.confidence}`)} ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType delphi:Assessment ;
    npx:introduces ${iri(A)} ;
    delphi:domain ${iri(domain)} .
}
`;
}

mkdirSync(OUT, { recursive: true });
const wanted = new Set(process.argv.slice(2));
let n = 0;
for (const project of readdirSync(HERE).filter(p => existsSync(join(HERE, p, "")) && !p.includes(".") && p !== "nanopubs")) {
  for (const id of readdirSync(join(HERE, project))) {
    if (wanted.size && !wanted.has(id)) continue;
    const f = join(HERE, project, id, "result.json");
    if (!existsSync(f)) continue;
    const r = JSON.parse(readFileSync(f, "utf8"));
    if (r.status !== "complete") continue;
    writeFileSync(join(OUT, `${id}.trig`), trig(project, id, r));
    n++;
  }
}
console.log(`wrote ${n} claim-test nanopubs to ${OUT} (commit ${commit.slice(0, 8)})`);
