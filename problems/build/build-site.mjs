// Build the problem graph for the site: docs/problems.json (problems, their approaches, the claims
// each bears on with their current status, and nanopub URIs from the manifest) and docs/problems.html
// from docs/problems.template.html, following scripts/site/build-claim-graph.mjs conventions.
//
//   node problems/build/build-site.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { linkOf } from "./links.mjs";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const ROOT = join(HERE, "..");
const DOCS = join(ROOT, "docs");

const problems = JSON.parse(readFileSync(join(HERE, "problems.json"), "utf8"));
const manifest = existsSync(join(HERE, "nanopubs/manifest.json")) ? JSON.parse(readFileSync(join(HERE, "nanopubs/manifest.json"), "utf8")) : { nanopubs: [] };
const links = existsSync(join(HERE, "dropped-links.json")) ? JSON.parse(readFileSync(join(HERE, "dropped-links.json"), "utf8")).checked : {};
const claimsJson = JSON.parse(readFileSync(join(DOCS, "claims.json"), "utf8"));
const claims = new Map((claimsJson.claims ?? claimsJson).map(c => [c.id, c]));

const np = subject => {
  const m = manifest.nanopubs.find(m => m.subject === subject);
  if (!m?.trustyUri) return null;
  return { uri: m.trustyUri, registry: m.productionRegistry ?? m.registry, publishedAt: m.productionPublishedAt ?? m.publishedAt };
};
const ref = r => {
  const url = linkOf(r);
  const c = url ? links[url] : null;
  if (!url || !c?.ok) return null;
  return { url, title: c.title ?? null, year: c.year ?? null, note: r.note ?? null };
};

const approachesByProblem = new Map();
const apDir = join(HERE, "approaches");
for (const f of readdirSync(apDir).filter(f => f.endsWith(".json")).sort()) {
  const a = JSON.parse(readFileSync(join(apDir, f), "utf8"));
  for (const ap of a.approaches ?? []) {
    const id = `${ap.problem}--${a.model}--${ap.n}`;
    const list = approachesByProblem.get(ap.problem) ?? [];
    list.push({
      id, model: a.model, model_label: a.model_label ?? a.model, provider: a.provider, n: ap.n, title: ap.title, kind: ap.kind, method: ap.method,
      steps: ap.steps ?? [], decisive_result: ap.decisive_result, failure_signature: ap.failure_signature, tools: ap.tools ?? [],
      datasets: (ap.datasets ?? []).map(d => ({ name: d.name ?? null, url: d.url && links[String(d.url).trim()]?.ok ? String(d.url).trim() : null, note: d.note ?? null })),
      references: (ap.references ?? []).map(r => ref(r) ?? { url: null, note: r.note ?? null }),
      difficulty: ap.difficulty, missing: ap.missing ?? null,
      nanopub: np(`https://w3id.org/delphi/resource/approach/${id}`),
    });
    approachesByProblem.set(ap.problem, list);
  }
}

const data = {
  built: new Date().toISOString().slice(0, 16).replace("T", " "),
  version: problems.version,
  tiers: problems.tiers,
  registry: manifest.status?.startsWith("published to production") ? "production" : manifest.nanopubs.some(m => m.trustyUri) ? "test registry" : null,
  problems: problems.problems.map(p => ({
    id: p.id, title: p.title, field: p.field, tier: p.tier, question: p.question, known_state: p.known_state,
    acceptance_criteria: p.acceptance_criteria ?? [], falsifiers: p.falsifiers ?? [], required_capabilities: p.required_capabilities ?? [],
    data_access: p.data_access, scales: p.scales ?? [], frontier_problem: p.frontier_problem ?? null,
    related_claims: (p.related_claims ?? []).map(id => { const c = claims.get(id); return { id, label: c?.label ?? c?.title ?? null, thinker: c?.thinker ?? null, status: c?.status ?? null, evidence: c?.evidence ?? null, theorem: c?.theorem ?? false }; }),
    references: (p.references ?? []).map(ref).filter(Boolean),
    nanopub: np(`https://w3id.org/delphi/resource/problem/${p.id}`),
    approaches: (approachesByProblem.get(p.id) ?? []).sort((a, b) => a.model.localeCompare(b.model) || a.n - b.n),
  })),
};
writeFileSync(join(DOCS, "problems.json"), JSON.stringify(data, null, 1) + "\n");

const seal = readFileSync(join(ROOT, "assets/logo.svg"), "utf8").trim();
const inline = svg => svg.replace(/<svg[^>]*>/, t => t.replace(/\s(width|height)="\d+"/g, "")).replace("<svg ", '<svg role="img" aria-label="DELPHI seal" ');
const html = readFileSync(join(DOCS, "problems.template.html"), "utf8")
  .replace("<!--__SEAL__-->", inline(seal))
  .replace("/*__SEAL_URI__*/", encodeURIComponent(seal))
  .replace("/*__DATA__*/null", JSON.stringify(data).replace(/</g, "\\u003c"));
writeFileSync(join(DOCS, "problems.html"), html);
const nA = data.problems.reduce((s, p) => s + p.approaches.length, 0);
console.log(`docs/problems.json and docs/problems.html: ${data.problems.length} problems, ${nA} approaches from ${new Set([...approachesByProblem.values()].flat().map(a => a.model)).size} models, ${data.problems.filter(p => p.nanopub).length + data.problems.reduce((s, p) => s + p.approaches.filter(a => a.nanopub).length, 0)} nanopubs published`);
