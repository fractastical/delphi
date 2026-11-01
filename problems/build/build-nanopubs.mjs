// Build unsigned nanopubs for the problem graph:
//
//   problems/nanopubs/unsigned/problem--<id>.trig                 one per problem in problems.json
//   problems/nanopubs/unsigned/approach--<problem>--<model>--<n>.trig  one per approach in approaches/*.json
//   problems/nanopubs/unsigned/run--<approach>--<date>.trig            one per entry in forecasts/runs.json
//
// A problem is delphir:problem/<id>, typed delphi:Concept (the ontology's reusable entity that
// claims and plans refer to) and schema:Question. It links to the repo claims it bears on with
// skos:related and to the literature with rdfs:seeAlso. An approach is delphir:approach/<...>,
// typed prov:Plan and delphi:TestableHypothesis (the hypothesis that this plan would settle the
// problem, with delphi:proposedTest the decisive result), and names its problem with dct:subject.
// A run is delphir:run/<...>, a prov:Activity whose prov:hadPlan is the approach, with the outcome
// as schema:actionStatus and the artifact (and the claim-test assessment, if any) as prov:generated.
// Links listed in dropped-links.json (resolve-links.mjs) are left out. Signing and publishing are
// separate steps (publish.mjs; BEST_PRACTICES.md sections 2-4).
//
//   node problems/build/build-nanopubs.mjs
import { readFileSync, writeFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { linkOf } from "./links.mjs";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = join(HERE, "..");
const OUT = join(HERE, "nanopubs", "unsigned");
const git = cmd => execSync(`git ${cmd}`, { cwd: ROOT, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const blob = path => `https://github.com/fractastical/delphi/blob/${commit}/${path}`;

const R = "https://w3id.org/delphi/resource/";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const DOMAIN = `${R}domain/open-problems`;
// The problems were curated by the top-level Cursor agent that wrote problems.json.
const CURATOR = { agent: `${R}agent/cursor-claude-fable-5-1-problem-curator`, model: `${R}model/claude-fable-5-1`, modelId: "claude-fable-5-1", label: "Cursor agent (Claude Fable 5.1) curating open problems from the claim graph and the literature" };

const lit = s => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r")}"`;
const iri = u => `<${String(u).trim().replace(/[ <>"{}|\\^`[\]]/g, ch => encodeURIComponent(ch))}>`;
const slug = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const isUrl = u => typeof u === "string" && /^https?:\/\/[^\s<>"{}|\\^`]+$/.test(u.trim());

const dropped = existsSync(join(HERE, "dropped-links.json")) ? JSON.parse(readFileSync(join(HERE, "dropped-links.json"), "utf8")) : { checked: {}, dropped: [] };
const resolved = url => dropped.checked[url]?.ok === true;
const title = url => dropped.checked[url]?.title ?? null;
const unresolvedLog = [];
// Only links the resolver has seen and accepted go into a nanopub (BEST_PRACTICES.md section 2).
function keepLink(url, where) {
  if (!url || !isUrl(url)) return false;
  if (resolved(url)) return true;
  unresolvedLog.push({ url, where, reason: dropped.checked[url] ? (dropped.checked[url].error ?? `status ${dropped.checked[url].status}`) : "not checked; run resolve-links.mjs" });
  return false;
}

const problems = JSON.parse(readFileSync(join(HERE, "problems.json"), "utf8"));
const problemIds = new Set(problems.problems.map(p => p.id));
const claimsJson = JSON.parse(readFileSync(join(ROOT, "docs/claims.json"), "utf8"));
const knownClaims = new Set((claimsJson.claims ?? claimsJson).map(c => c.id));
for (const dir of readdirSync(join(ROOT, "claim-sources"))) {
  const u = join(ROOT, "claim-sources", dir, "nanopubs", "unsigned");
  if (existsSync(u)) for (const f of readdirSync(u)) if (f.endsWith(".trig")) knownClaims.add(f.replace(/\.trig$/, ""));
}

const PREFIXES = `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix schema: <https://schema.org/> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
`;

const head = `
sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}
`;

function agentBlock(a) {
  return `  ${iri(a.agent)} a prov:SoftwareAgent ;
    rdfs:label ${lit(a.label)} ;
    delphi:usesModel ${iri(a.model)} ;
    prov:actedOnBehalfOf ${iri(OWNER)} .
  ${iri(a.model)} a delphi:LanguageModel ;
    rdfs:label ${lit(a.modelLabel ?? a.modelId)} ;
    dct:identifier ${lit(a.modelId)} .`;
}

function pubinfo(label, type, subject) {
  return `
sub:pubinfo {
  this: dct:created "${new Date().toISOString()}"^^xsd:dateTime ;
    dct:creator ${iri(OWNER)} ;
    rdfs:label ${lit(label)} ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType ${type} ;
    npx:introduces ${iri(subject)} ;
    delphi:domain ${iri(DOMAIN)} .
  ${iri(DOMAIN)} rdfs:label "open-problems" .
}
`;
}

// References become rdfs:seeAlso with the Crossref title (when known) and the proposer's note.
function refTriples(refs, where) {
  const out = [];
  for (const r of refs ?? []) {
    const url = linkOf(r);
    if (!keepLink(url, where)) continue;
    out.push(`    rdfs:seeAlso ${iri(url)} ;`);
    const t = title(url);
    out.push({ after: `  ${iri(url)} ${t ? `dct:title ${lit(t)} ;\n    ` : ""}dct:bibliographicCitation ${lit(r.note ?? t ?? url)} .` });
  }
  return out;
}
// The upstream linter requires every "<number> <species|genera|...>" in a label, description or
// comment to have a structured count (schema:additionalProperty) on the subject. Approaches state
// planned sample sizes in prose, so mirror each one as a structured count. Two different numbers
// for the same unit (two datasets of 40 and 45 images) become two counts with the same propertyID.
const COUNT_IN_TEXT = /(~|≈|\bc\.\s*|\babout\s+|\bapprox(?:\.|imately)?\s+|\bon the order of\s+)?\b(\d{1,3}(?:,\d{3})+|\d+)\s+(species|specimens|genera|families|taxa|individuals|samples|images|sites|populations)\b/gi;
function structuredCounts(subject, texts, where) {
  const counts = new Map();
  for (const text of texts) for (const m of String(text ?? "").matchAll(COUNT_IN_TEXT)) {
    const [, approx, num, unit] = m;
    if (approx) throw new Error(`${where}: approximate count "${m[0].trim()}" cannot be a structured value; state the number exactly or drop it`);
    const id = `n_${unit.toLowerCase()}`, value = Number(num.replace(/,/g, ""));
    if (!counts.has(id)) counts.set(id, new Set());
    counts.get(id).add(value);
  }
  const inlineParts = [], afterParts = [];
  for (const [id, values] of counts) for (const value of values) {
    const node = `${subject}#${values.size > 1 ? `${id}-${value}` : id}`;
    inlineParts.push(`    schema:additionalProperty ${iri(node)} ;`);
    afterParts.push(`  ${iri(node)} a schema:PropertyValue ;\n    schema:propertyID ${lit(id)} ;\n    schema:value ${value} ;\n    schema:description ${lit(`${id.slice(2)} named in the text (a sample size as stated there, not a measurement made here)`)} .`);
  }
  return { inline: inlineParts.join("\n"), after: afterParts.join("\n") };
}
const inline = parts => parts.filter(p => typeof p === "string").join("\n");
const after = parts => parts.filter(p => typeof p !== "string").map(p => p.after).join("\n");

function problemTrig(p) {
  const P = `${R}problem/${p.id}`;
  const related = (p.related_claims ?? []).filter(c => { if (knownClaims.has(c)) return true; unresolvedLog.push({ url: c, where: `problem ${p.id}`, reason: "no such claim in the repo" }); return false; });
  const refs = refTriples(p.references, `problem ${p.id}`);
  const counts = structuredCounts(P, [p.title, p.question], `problem ${p.id}`);
  return `${PREFIXES}${head}
sub:assertion {
  ${iri(P)} a delphi:Concept, schema:Question ;
    rdfs:label ${lit(p.title)} ;
    dct:description ${lit(p.question)} ;
${counts.inline}
    skos:historyNote ${lit(`Known state: ${p.known_state}`)} ;
    dct:subject ${lit(p.field)} ;
    delphi:hypothesisType ${lit(`open-problem/tier-${p.tier}`)} ;
${(p.acceptance_criteria ?? []).map(c => `    skos:scopeNote ${lit(`Resolved when: ${c}`)} ;`).join("\n")}
${(p.falsifiers ?? []).map(c => `    skos:scopeNote ${lit(`Refuted if: ${c}`)} ;`).join("\n")}
    skos:note ${lit(`Data access: ${p.data_access}`)} ;
${(p.required_capabilities ?? []).map(c => `    skos:note ${lit(`Requires: ${c}`)} ;`).join("\n")}
${(p.scales ?? []).map(s => `    skos:note ${lit(`Scale: ${s}`)} ;`).join("\n")}
${p.frontier_problem ? `    skos:note ${lit(`Also recorded as a Delphi Frontier Problem: ${p.frontier_problem}`)} ;\n` : ""}${related.map(c => `    skos:related ${iri(`${R}claim/${c}`)} ;`).join("\n")}
${inline(refs)}
    rdfs:isDefinedBy ${iri(blob("problems/problems.json"))} .
${counts.after}
${after(refs)}
}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(CURATOR.agent)} ;
    prov:wasDerivedFrom ${iri(blob("problems/problems.json"))} ;
    prov:wasGeneratedBy sub:curation .
  sub:curation a prov:Activity ;
    rdfs:label "Curating open problems that the delphisci agent swarm could attack, from the claim graph (docs/claims.json), its test candidates and the literature" ;
    prov:wasAssociatedWith ${iri(CURATOR.agent)} ;
    prov:used ${iri(blob("docs/claims.json"))} .
${agentBlock({ ...CURATOR, modelLabel: "Claude Fable 5.1" })}
}
${pubinfo(`Open problem: ${p.title}`, "delphi:Concept", P)}`;
}

function approachTrig(a, ap) {
  const id = `${ap.problem}--${a.model}--${ap.n}`;
  const A = `${R}approach/${id}`;
  const P = `${R}problem/${ap.problem}`;
  const agent = { agent: `${R}agent/delphisci-approach-proposer-${slug(a.model)}`, model: `${R}model/${slug(a.model)}`, modelId: a.model, modelLabel: a.model_label ?? a.model, label: `delphisci approach proposer (${a.model_label ?? a.model}, ${a.provider}), working blind from problems.json` };
  const where = `approach ${id}`;
  const refs = refTriples(ap.references, where);
  const datasets = [];
  for (const d of ap.datasets ?? []) {
    const url = d.url ? String(d.url).trim() : null;
    if (!keepLink(url, `${where} dataset`)) { if (d.name) datasets.push(`    skos:note ${lit(`Dataset (no resolvable link): ${d.name}${d.note ? `. ${d.note}` : ""}`)} ;`); continue; }
    datasets.push(`    rdfs:seeAlso ${iri(url)} ;`);
    datasets.push({ after: `  ${iri(url)} dct:title ${lit(d.name ?? url)} ;\n    dct:description ${lit(d.note ?? "")} .` });
  }
  const related = problems.problems.find(p => p.id === ap.problem)?.related_claims?.filter(c => knownClaims.has(c)) ?? [];
  const counts = structuredCounts(A, [ap.title, ap.method], where);
  return `${PREFIXES}${head}
sub:assertion {
  ${iri(A)} a prov:Plan, delphi:TestableHypothesis ;
    rdfs:label ${lit(ap.title)} ;
    dct:subject ${iri(P)} ;
    dct:description ${lit(ap.method)} ;
${counts.inline}
    delphi:proposedTest ${lit(ap.decisive_result)} ;
    delphi:context ${lit(`Fails if: ${ap.failure_signature}`)} ;
    delphi:hypothesisType ${lit(`approach/${ap.kind}`)} ;
    skos:note ${lit(`Steps: ${(ap.steps ?? []).map((s, i) => `${i + 1}. ${s}`).join(" ")}`)} ;
    skos:note ${lit(`Difficulty (proposer's estimate of completion within about a month of agent time): ${ap.difficulty}`)} ;
${ap.missing ? `    skos:note ${lit(`Missing: ${ap.missing}`)} ;\n` : ""}${(ap.tools ?? []).map(t => `    skos:note ${lit(`Tool: ${t}`)} ;`).join("\n")}
${related.map(c => `    skos:related ${iri(`${R}claim/${c}`)} ;`).join("\n")}
${inline(datasets)}
${inline(refs)}
    rdfs:isDefinedBy ${iri(blob(`problems/approaches/${a.model}.json`))} .
  ${iri(P)} a delphi:Concept, schema:Question ;
    rdfs:label ${lit(problems.problems.find(p => p.id === ap.problem)?.title ?? ap.problem)} .
${counts.after}
${after(datasets)}
${after(refs)}
}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(agent.agent)} ;
    prov:wasDerivedFrom ${iri(blob(`problems/approaches/${a.model}.json`))}, ${iri(blob("problems/problems.json"))} ;
    prov:wasGeneratedBy sub:proposal .
  sub:proposal a prov:Activity ;
    rdfs:label ${lit(`Proposing approaches to ${ap.problem}, blind to other proposers, following problems/approaches/INSTRUCTIONS.md`)} ;
    prov:wasAssociatedWith ${iri(agent.agent)} ;
    prov:qualifiedAssociation sub:plan .
  sub:plan prov:hadPlan ${iri(blob("problems/approaches/INSTRUCTIONS.md"))} .
${agentBlock(agent)}
}
${pubinfo(`Approach to ${ap.problem}: ${ap.title}`, "prov:Plan", A)}`;
}

// A run is what the swarm actually did against an approach (forecasts/runs.json, append only):
// delphir:run/<approach>--<date>[-<k>], a prov:Activity whose plan was the approach, on the
// problem, generating the logged artifact. The outcome is schema:actionStatus (completed,
// partial, abandoned, in-progress); `settled` and `solves_problem` are structured
// schema:PropertyValue booleans so they can be queried without parsing prose. When the run
// produced a claim test, prov:generated names that test's assessment IRI as
// test-data/claim-tests/build-test-nanopubs.mjs mints it (<claim>--claim-test[--<run>]).
const STATUS = { completed: "schema:CompletedActionStatus", partial: "schema:ActiveActionStatus", "in-progress": "schema:ActiveActionStatus", abandoned: "schema:FailedActionStatus" };
const runsPath = join(HERE, "forecasts", "runs.json");
const runs = existsSync(runsPath) ? JSON.parse(readFileSync(runsPath, "utf8")).runs ?? [] : [];
const approachMeta = new Map();
for (const f of readdirSync(join(HERE, "approaches")).filter(f => f.endsWith(".json"))) {
  const a = JSON.parse(readFileSync(join(HERE, "approaches", f), "utf8"));
  for (const ap of a.approaches ?? []) approachMeta.set(`${ap.problem}--${a.model}--${ap.n}`, { ...ap, model: a.model, model_label: a.model_label, provider: a.provider });
}
function runId(r, k) {
  const base = `${r.approach ?? `${r.problem}--unplanned`}--${r.date}`;
  return k ? `${base}-${k}` : base;
}
function testAssessmentIri(testPath) {
  const m = /^test-data\/claim-tests\/[^/]+\/([^/]+)\/(?:([^/]+)\/)?result\.json$/.exec(testPath ?? "");
  if (!m) return null;
  return `${R}assessment/${m[1]}--claim-test${m[2] ? `--${m[2]}` : ""}`;
}
function runTrig(r, id) {
  const RUN = `${R}run/${id}`;
  const ap = r.approach ? approachMeta.get(r.approach) : null;
  if (r.approach && !ap) throw new Error(`runs.json: unknown approach ${r.approach}`);
  const problemId = r.problem ?? ap?.problem;
  const problem = problems.problems.find(p => p.id === problemId);
  if (!problem) throw new Error(`runs.json: run ${id} names unknown problem ${problemId}`);
  if (!STATUS[r.outcome]) throw new Error(`runs.json: run ${id} has outcome ${r.outcome}; expected ${Object.keys(STATUS).join(", ")}`);
  if (!r.artifact) throw new Error(`runs.json: run ${id} has no artifact`);
  const P = `${R}problem/${problemId}`;
  const A = r.approach ? `${R}approach/${r.approach}` : null;
  const claims = (r.claims ?? []).filter(c => { if (knownClaims.has(c)) return true; unresolvedLog.push({ url: c, where: `run ${id}`, reason: "no such claim in the repo" }); return false; });
  const assessment = r.test ? testAssessmentIri(r.test) : null;
  if (r.test && !assessment) throw new Error(`runs.json: run ${id} has a test path that is not test-data/claim-tests/<project>/<claim>[/<run>]/result.json`);
  const generated = [iri(blob(r.artifact)), assessment && iri(assessment)].filter(Boolean);
  const modelSlug = r.agent ? slug(r.agent) : null;
  const agent = modelSlug
    ? { agent: `${R}agent/delphisci-approach-runner-${modelSlug}`, model: `${R}model/${modelSlug}`, modelId: r.agent, modelLabel: r.agent, label: `delphisci approach runner (${r.agent}), executing a proposed approach and logging the result` }
    : { agent: `${R}agent/delphisci-approach-runner`, label: "delphisci approach runner (model not recorded in the run report)" };
  const flag = (key, value, description) => value == null ? "" : `  ${iri(`${RUN}#${key}`)} a schema:PropertyValue ;\n    schema:propertyID ${lit(key)} ;\n    schema:value ${value ? "true" : "false"} ;\n    schema:description ${lit(description)} .`;
  const label = `Run of ${r.approach ? `approach ${r.approach}` : `an unplanned test on ${problemId}`} (${r.date}): ${r.outcome}${r.settled === true ? ", settled its target" : r.settled === false ? ", did not settle its target" : ""}`;
  const counts = structuredCounts(RUN, [label, r.note], `run ${id}`);
  return `${PREFIXES}${head}
sub:assertion {
  ${iri(RUN)} a prov:Activity ;
    rdfs:label ${lit(label)} ;
    dct:description ${lit(r.note ?? "")} ;
${counts.inline}
    dct:subject ${iri(P)} ;
${A ? `    prov:qualifiedAssociation ${iri(`${RUN}#plan`)} ;\n` : ""}    prov:startedAtTime "${r.date}"^^xsd:date ;
${r.outcome === "completed" || r.outcome === "abandoned" ? `    prov:endedAtTime "${r.date}"^^xsd:date ;\n` : ""}    schema:actionStatus ${STATUS[r.outcome]} ;
    schema:additionalProperty ${iri(`${RUN}#settled`)}, ${iri(`${RUN}#solves_problem`)} ;
${claims.map(c => `    skos:related ${iri(`${R}claim/${c}`)} ;`).join("\n")}
${r.report ? `    rdfs:seeAlso ${iri(blob(r.report))} ;\n` : ""}    prov:generated ${generated.join(", ")} ;
    rdfs:isDefinedBy ${iri(blob("problems/forecasts/runs.json"))} .
${A ? `  ${iri(`${RUN}#plan`)} a prov:Association ;\n    prov:hadPlan ${iri(A)} .\n  ${iri(A)} a prov:Plan ;\n    rdfs:label ${lit(ap.title)} .\n` : ""}  ${iri(P)} a delphi:Concept, schema:Question ;
    rdfs:label ${lit(problem.title)} .
${flag("settled", r.settled ?? false, r.settled == null ? "Whether the run settled the piece of the problem its approach names: unknown, the run did not complete" : "Whether the run settled the piece of the problem its approach names (forecasts/INSTRUCTIONS.md)")}
${flag("solves_problem", !!r.solves_problem, "Whether the logged artifacts meet the problem's acceptance criteria or hit one of its falsifiers definitively")}
${assessment ? `  ${iri(assessment)} a delphi:Assessment ;\n    rdfs:label ${lit(`Claim test produced by this run (${r.test})`)} .` : ""}
${counts.after}
}

sub:provenance {
  sub:assertion prov:wasAttributedTo ${iri(agent.agent)} ;
    prov:wasDerivedFrom ${iri(blob("problems/forecasts/runs.json"))}${r.report ? `, ${iri(blob(r.report))}` : ""} ;
    prov:wasGeneratedBy sub:logging .
  sub:logging a prov:Activity ;
    rdfs:label ${lit(`Logging what the swarm ran against ${r.approach ?? problemId} in problems/forecasts/runs.json, following problems/forecasts/INSTRUCTIONS.md`)} ;
    prov:wasAssociatedWith ${iri(agent.agent)} ;
    prov:qualifiedAssociation sub:plan .
  sub:plan prov:hadPlan ${iri(blob("problems/forecasts/INSTRUCTIONS.md"))} .
${agent.model ? agentBlock(agent) : `  ${iri(agent.agent)} a prov:SoftwareAgent ;\n    rdfs:label ${lit(agent.label)} ;\n    prov:actedOnBehalfOf ${iri(OWNER)} .`}
}
${pubinfo(label, "prov:Activity", RUN)}`;
}

mkdirSync(OUT, { recursive: true });
const manifestPath = join(HERE, "nanopubs", "manifest.json");
const previous = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, "utf8")) : { nanopubs: [] };
// Publication state comes from nanopubs/manifest.jsonl, which scripts/release/publish.mjs appends to
// (one line per file and registry). A file that reached a registry is never regenerated here.
const jsonl = join(HERE, "nanopubs", "manifest.jsonl");
const publications = existsSync(jsonl) ? readFileSync(jsonl, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l)) : [];
const published = new Map();
for (const m of previous.nanopubs) if (m.trustyUri) published.set(m.file, m);
for (const m of publications) {
  const file = `nanopubs/${m.file}`;
  const prev = published.get(file) ?? previous.nanopubs.find(x => x.file === file) ?? { file };
  published.set(file, { ...prev, trustyUri: m.trustyUri, registry: m.registry === "production" ? "production" : (prev.registry === "production" ? "production" : m.registry), publishedAt: m.publishedAt, generatorCommit: m.generatorCommit ?? prev.generatorCommit });
}
const manifest = [];
let nP = 0, nA = 0, nR = 0, kept = 0;

for (const p of problems.problems) {
  const file = `nanopubs/unsigned/problem--${p.id}.trig`;
  if (published.has(file)) { manifest.push(published.get(file)); kept++; continue; }
  writeFileSync(join(HERE, file), problemTrig(p));
  manifest.push({ file, kind: "problem", subject: `${R}problem/${p.id}`, problem: p.id, tier: p.tier, field: p.field, generatorCommit: commit, registry: null, trustyUri: null });
  nP++;
}
const apDir = join(HERE, "approaches");
for (const f of readdirSync(apDir).filter(f => f.endsWith(".json")).sort()) {
  const a = JSON.parse(readFileSync(join(apDir, f), "utf8"));
  if (!a.model || !a.provider) throw new Error(`${f}: needs model and provider`);
  if (`${a.model}.json` !== f) throw new Error(`${f}: file must be named after its model slug (${a.model})`);
  for (const ap of a.approaches ?? []) {
    if (!problemIds.has(ap.problem)) throw new Error(`${f}: approach for unknown problem ${ap.problem}`);
    for (const k of ["n", "title", "kind", "method", "decisive_result", "failure_signature", "difficulty"]) if (ap[k] == null || ap[k] === "") throw new Error(`${f}: ${ap.problem} n=${ap.n} lacks ${k}`);
    const file = `nanopubs/unsigned/approach--${ap.problem}--${a.model}--${ap.n}.trig`;
    if (published.has(file)) { manifest.push(published.get(file)); kept++; continue; }
    writeFileSync(join(HERE, file), approachTrig(a, ap));
    manifest.push({ file, kind: "approach", subject: `${R}approach/${ap.problem}--${a.model}--${ap.n}`, problem: ap.problem, model: a.model, provider: a.provider, approachKind: ap.kind, difficulty: ap.difficulty, generatorCommit: commit, registry: null, trustyUri: null });
    nA++;
  }
}
const seenRun = new Map();
for (const r of runs) {
  const base = runId(r);
  const k = seenRun.get(base) ?? 0;
  seenRun.set(base, k + 1);
  const id = runId(r, k);
  const file = `nanopubs/unsigned/run--${id}.trig`;
  if (published.has(file)) { manifest.push(published.get(file)); kept++; continue; }
  writeFileSync(join(HERE, file), runTrig(r, id));
  manifest.push({ file, kind: "run", subject: `${R}run/${id}`, problem: r.problem ?? approachMeta.get(r.approach)?.problem, approach: r.approach, date: r.date, outcome: r.outcome, settled: r.settled ?? null, solvesProblem: !!r.solves_problem, artifact: r.artifact, generatorCommit: commit, registry: null, trustyUri: null });
  nR++;
}
const status = manifest.every(m => m.registry === "production") ? "published to production"
  : manifest.every(m => m.trustyUri) ? "published to the test registry; not promoted to production"
  : manifest.some(m => m.trustyUri) ? "partly published to the test registry; not promoted to production"
  : "unsigned draft; not published";
writeFileSync(manifestPath, JSON.stringify({ status, nanopubs: manifest }, null, 2) + "\n");
writeFileSync(join(HERE, "nanopubs", "omitted-links.json"), JSON.stringify({ generated: new Date().toISOString(), note: "Links and claim ids named in the sources but left out of the nanopubs, with the reason.", omitted: unresolvedLog }, null, 2) + "\n");
console.log(`wrote ${nP} problem, ${nA} approach and ${nR} run nanopubs to ${OUT} (commit ${commit.slice(0, 8)}); kept ${kept} already published; omitted ${unresolvedLog.length} links (nanopubs/omitted-links.json)`);
