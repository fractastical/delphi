// Builds one unsigned Project Delphi entity nanopub per claim in claims/key-claims.json,
// using the upstream builders (project-delphi-ontology/pipeline) so the triples match the
// ontology exactly. Output is unsigned TriG on the nanopub temp base; seal it with the
// project key (pipeline/seal.ts) before publishing to the test registry.
//
//   DELPHI_PIPELINE=/path/to/project-delphi-ontology/pipeline npx tsx build-nanopubs.mts

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const pipeline = process.env.DELPHI_PIPELINE;
if (!pipeline) throw new Error("Set DELPHI_PIPELINE to the project-delphi-ontology/pipeline directory");

const B = await import(pathToFileURL(resolve(pipeline, "probknow-builders.ts")).href);
const { triplesToTrig } = await import(pathToFileURL(resolve(pipeline, "seal.ts")).href);
const { DELPHI, DELPHIR, RDF, RDFS, DC, PROV, SYSTEM_ID } = B;
const SKOS = "http://www.w3.org/2004/02/skos/core#";
const DCTERMS_ID = `${DC}identifier`;

// The builders attribute everything to the upstream ProbKnow system agent. These nanopubs are
// signed by the operator's key, so the operator is the creator and the extraction is attributed
// to the software agent that did it.
const operator = process.env.NANOPUB_ORCID;
if (!operator) throw new Error("Set NANOPUB_ORCID to the ORCID IRI of the person whose key signs the batch");
const AGENT = `${DELPHIR}agent/cursor-claude-opus-5-5-extractor`;
const MODEL = `${DELPHIR}model/claude-opus-5-5`;
const held: Record<string, string> = JSON.parse(process.env.HOLD ?? "{}");

function reattribute(triples: { subject: string; predicate: string; object: string; graph: string }[]) {
  const provG = triples.find(t => t.graph.endsWith("/provenance"))!.graph;
  const out = triples.map(t =>
    t.object !== SYSTEM_ID ? t
    : t.graph === provG ? { ...t, object: AGENT }
    : { ...t, object: operator! });
  const lit = (s: string) => JSON.stringify(s);
  out.push(
    { subject: AGENT, predicate: `${RDF}type`, object: `${PROV}SoftwareAgent`, graph: provG },
    { subject: AGENT, predicate: `${RDFS}label`, object: lit("Cursor agent (Claude Opus 5.5) extracting key claims from source papers"), graph: provG },
    { subject: AGENT, predicate: `${DELPHI}usesModel`, object: MODEL, graph: provG },
    { subject: AGENT, predicate: `${PROV}actedOnBehalfOf`, object: operator!, graph: provG },
    { subject: MODEL, predicate: `${RDF}type`, object: `${DELPHI}LanguageModel`, graph: provG },
    { subject: MODEL, predicate: `${RDFS}label`, object: lit("Claude Opus 5.5"), graph: provG },
    { subject: MODEL, predicate: DCTERMS_ID, object: lit("claude-opus-5-5"), graph: provG },
  );
  return out;
}

interface Paper { title: string; doi: string | null; year: number }
interface Claim {
  id: string; thinker: string; label: string; statement: string; notation: string; context: string;
  kind: string; proposed_test: string; paper: Paper; see_also: string[];
}

const src = JSON.parse(readFileSync(join(here, "claims/key-claims.json"), "utf8"));
const outDir = join(here, "nanopubs/unsigned");
mkdirSync(outDir, { recursive: true });

const slug = (s: string) => s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
const surname = (thinker: string) => slug(thinker.split(/\s+/).at(-1)!);

// Published nanopubs are immutable: keep their manifest entries and unsigned files as they are.
const manifestPath = join(here, "nanopubs/manifest.json");
const previous = existsSync(manifestPath) ? JSON.parse(readFileSync(manifestPath, "utf8")) : { nanopubs: [] };
const published = new Map<string, Record<string, unknown>>(
  previous.nanopubs.filter((m: any) => m.trustyUri).map((m: any) => [m.claim, m]));

const manifest: Record<string, unknown>[] = [];
for (const c of src.claims as Claim[]) {
  const done = published.get(`${DELPHIR}claim/${c.id}`);
  if (done) {
    manifest.push(done);
    continue;
  }
  if (held[c.id]) {
    manifest.push({ claim: `${DELPHIR}claim/${c.id}`, thinker: c.thinker, held: held[c.id] });
    continue;
  }
  if (!c.paper?.title || !c.paper.year) throw new Error(`${c.id}: every claim needs its source paper`);
  const domain = c.id.startsWith("turing-") ? src.domains.turing : src.domains.default;
  const citation = `${c.thinker} (${c.paper.year}) ${c.paper.title}`;
  const built = B.buildEntityNanopub({
    iri: `${DELPHIR}claim/${c.id}`,
    // With no DOI the builder names the source delphir:paper/<id>, so key it by the work, not the claim.
    id: c.paper.doi ? c.id : `${surname(c.thinker)}-${c.paper.year}-${slug(c.paper.title)}`,
    type: `${DELPHI}Claim`,
    label: c.label,
    description: c.statement,
    statements: [
      { predicate: `${RDF}type`, object: `${DELPHI}TestableHypothesis` },
      { predicate: `${SKOS}notation`, object: c.notation },
      { predicate: `${DELPHI}context`, object: c.context },
      { predicate: `${DELPHI}proposedTest`, object: c.proposed_test },
      { predicate: `${DELPHI}hypothesisType`, object: c.kind },
      { predicate: `${DC}source`, object: citation },
      ...c.see_also.map(d => ({ predicate: `${RDFS}seeAlso`, object: `https://doi.org/${d}` })),
    ],
    domain,
    paper: c.paper,
  });
  const file = `${c.id}.trig`;
  writeFileSync(join(outDir, file), triplesToTrig(reattribute(built.triples), built.preUri));
  manifest.push({ file: `nanopubs/unsigned/${file}`, claim: `${DELPHIR}claim/${c.id}`, thinker: c.thinker, source: c.paper.doi ? `https://doi.org/${c.paper.doi}` : citation, domain, ontologyCommit: process.env.DELPHI_COMMIT ?? null, registry: null, trustyUri: null });
}
const status = manifest.every(m => m.trustyUri) ? "published to the test registry; not promoted to production"
  : manifest.some(m => m.trustyUri) ? "partly published to the test registry; not promoted to production"
  : "unsigned draft; not published";
writeFileSync(manifestPath, JSON.stringify({ status, nanopubs: manifest }, null, 2) + "\n");
const count = (k: string) => manifest.filter(m => m[k]).length;
console.log(`wrote ${manifest.filter(m => m.file && !m.trustyUri).length} unsigned nanopubs to ${outDir}; kept ${count("trustyUri")} published; held ${count("held")}`);
