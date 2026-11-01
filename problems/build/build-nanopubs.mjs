// Build unsigned nanopubs for the problem graph:
//
//   problems/nanopubs/unsigned/problem--<id>.trig                 one per problem in problems.json
//   problems/nanopubs/unsigned/approach--<problem>--<model>--<n>.trig  one per approach in approaches/*.json
//
// A problem is delphir:problem/<id>, typed delphi:Concept (the ontology's reusable entity that
// claims and plans refer to) and schema:Question. It links to the repo claims it bears on with
// skos:related and to the literature with rdfs:seeAlso. An approach is delphir:approach/<...>,
// typed prov:Plan and delphi:TestableHypothesis (the hypothesis that this plan would settle the
// problem, with delphi:proposedTest the decisive result), and names its problem with dct:subject.
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
// for the same unit in one nanopub cannot be mirrored unambiguously and stop the build.
const COUNT_IN_TEXT = /(~|≈|\bc\.\s*|\babout\s+|\bapprox(?:\.|imately)?\s+|\bon the order of\s+)?\b(\d{1,3}(?:,\d{3})+|\d+)\s+(species|specimens|genera|families|taxa|individuals|samples|images|sites|populations)\b/gi;
function structuredCounts(subject, texts, where) {
  const counts = new Map();
  for (const text of texts) for (const m of String(text ?? "").matchAll(COUNT_IN_TEXT)) {
    const [, approx, num, unit] = m;
    if (approx) throw new Error(`${where}: approximate count "${m[0].trim()}" cannot be a structured value; state the number exactly or drop it`);
    const id = `n_${unit.toLowerCase()}`, value = Number(num.replace(/,/g, ""));
    if (counts.has(id) && counts.get(id) !== value) throw new Error(`${where}: two different counts of ${unit} (${counts.get(id)} and ${value}); make the text unambiguous`);
    counts.set(id, value);
  }
  const inlineParts = [], afterParts = [];
  for (const [id, value] of counts) {
    const node = `${subject}#${id}`;
    inlineParts.push(`    schema:additionalProperty ${iri(node)} ;`);
    afterParts.push(`  ${iri(node)} a schema:PropertyValue ;\n    schema:propertyID ${lit(id)} ;\n    schema:value ${value} ;\n    schema:description ${lit(`${id.slice(2)} the approach proposes to use, as stated in its description (a planned sample size, not a measurement)`)} .`);
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

mkdirSync(OUT, { recursive: true });
const manifestPath = join(HERE, "nanopubs", "manifest.json");
const previous = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, "utf8")) : { nanopubs: [] };
const published = new Map(previous.nanopubs.filter(m => m.trustyUri).map(m => [m.file, m]));
const manifest = [];
let nP = 0, nA = 0, kept = 0;

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
const status = manifest.every(m => m.trustyUri) ? "published to the test registry; not promoted to production"
  : manifest.some(m => m.trustyUri) ? "partly published to the test registry; not promoted to production"
  : "unsigned draft; not published";
writeFileSync(manifestPath, JSON.stringify({ status, nanopubs: manifest }, null, 2) + "\n");
writeFileSync(join(HERE, "nanopubs", "omitted-links.json"), JSON.stringify({ generated: new Date().toISOString(), note: "Links and claim ids named in the sources but left out of the nanopubs, with the reason.", omitted: unresolvedLog }, null, 2) + "\n");
console.log(`wrote ${nP} problem and ${nA} approach nanopubs to ${OUT} (commit ${commit.slice(0, 8)}); kept ${kept} already published; omitted ${unresolvedLog.length} links (nanopubs/omitted-links.json)`);
