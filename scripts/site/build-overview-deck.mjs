#!/usr/bin/env node
// Builds assets/deck/overview-deck.html (the "Delphi — Lean for Biology" project overview deck) from
// scripts/site/templates/overview-deck.template.html. Every number in the deck is computed here
// from repo files: docs/claims.json (built by build-claim-graph.mjs), test-data/organisms/merged/
// taxa.json and the Lean law registry via lib/lean-source.mjs. Edit the template, not the output.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const R = (...p) => path.join(ROOT, ...p);
const TEMPLATE = R('scripts', 'site', 'templates', 'overview-deck.template.html');
const OUT = R('assets', 'deck', 'overview-deck.html');

const { listLaws } = await import(R('lib', 'lean-source.mjs'));

const claimsDoc = JSON.parse(fs.readFileSync(R('docs', 'claims.json'), 'utf8'));
const claims = claimsDoc.claims;
const taxa = JSON.parse(fs.readFileSync(R('test-data', 'organisms', 'merged', 'taxa.json'), 'utf8'));
const laws = listLaws().laws;

const n = (f) => claims.filter(f).length;
const verdict = (c) => (c.evidence && typeof c.evidence === 'object' ? c.evidence.verdict : c.evidence) || null;

const counts = {
  CLAIMS: claims.length,
  MATH: n((c) => c.math),
  THEOREMS: n((c) => c.theorem),
  LEAN: n((c) => c.theorem && c.proof === 'lean'),
  LIT: n((c) => c.theorem && c.proof === 'literature'),
  TESTED: n((c) => verdict(c)),
  SUPPORTS: n((c) => verdict(c) === 'supports'),
  REFUTES: n((c) => verdict(c) === 'refutes'),
  MIXED: n((c) => verdict(c) === 'mixed'),
  INCONCLUSIVE: n((c) => verdict(c) === 'inconclusive'),
  LIVE: n((c) => c.registry === 'production' && !c.draft),
  WORKS: new Set(claims.map((c) => c.work)).size,
  TAXA: taxa.length,
  TAXA_DATA: taxa.filter((t) => Array.isArray(t.datasets) && t.datasets.length).length,
  REG_LAWS: laws.length,
  REG_ACCEPTED: laws.filter((l) => l.status === 'accepted').length,
};
if (counts.TESTED !== counts.SUPPORTS + counts.REFUTES + counts.MIXED + counts.INCONCLUSIVE) {
  throw new Error('unknown evidence verdict in docs/claims.json');
}

// Claim sources for the rotating graph: one bucket per thinker, largest first.
const byThinker = new Map();
for (const c of claims) byThinker.set(c.thinker, (byThinker.get(c.thinker) || 0) + 1);
const sources = [...byThinker].map(([thinker, count]) => ({ thinker, count })).sort((a, b) => b.count - a.count);
const universe = { total: counts.CLAIMS, math: counts.MATH, proved: counts.THEOREMS, sources, built: claimsDoc.built || null };

// Source texts, grouped by thinker with claim counts (computed), plus the formal libraries used.
const yearOf = (y) => (y < 0 ? `c. ${-y} BC` : String(y));
// "Ronald A. Fisher" -> "Fisher", "John Maynard Smith" -> "Maynard Smith", "X & Y" -> X's surname.
const surname = (t) => esc(t.split(/\s*(?:&|\band\b)\s*/)[0].trim().split(' ').slice(1).filter((w) => !/^[A-Z]\.$/.test(w)).join(' '));
const TOP = 5;
const textItems = sources.slice(0, TOP).map(({ thinker, count }) => {
  const ys = claims.filter((c) => c.thinker === thinker).map((c) => c.year).filter((y) => Number.isFinite(y));
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const span = lo === hi ? yearOf(lo) : `${yearOf(lo)}–${yearOf(hi)}`;
  return `<li><b>${surname(thinker) || esc(thinker)}</b> (${span}): ${count} claims</li>`;
});
const restSources = sources.slice(TOP);
const rest = restSources.reduce((a, s) => a + s.count, 0);
if (rest) {
  const named = restSources.slice(0, 3).map((s) => surname(s.thinker)).join(', ');
  textItems.push(`<li>${restSources.length} more mathematical biologists (${named}, …): ${rest} claims</li>`);
}
textItems.push('<li><b>Lean 4 + Mathlib</b> for the machine-checked proofs</li>');

// The remaining three lists are facts taken from README.md, COLLABORATIONS.md, docs/PORTAL.md and
// sponsors/*.md. They are names, not counts; keep them in step with those files.
const people = [
  '<li><b>Joel Dietz</b>, <b>Amit Shenoy</b>, <b>Kavita Koolkarni</b> (portal), <b>Kris Ganjam</b> (delphi-evolve, delphi-frontier)</li>',
  '<li><b>Knowledge Pixels</b>: nanopublications, the Delphi ontology, the <code>nanopub</code> and <code>delphi</code> skills</li>',
  '<li><b>Science Claw Hack @ MIT</b> and the SentiLab, ScienceClaw and Moltbook agents whose objections changed our tests</li>',
  '<li>Assessors from Anthropic, OpenAI, Google and a self-hosted Qwen3-32B; assessor is never builder</li>',
];
const code = [
  '<li><b>fractastical/delphi</b>: claims, assessments, Lean proofs, claim tests, the <code>delphisci</code> MCP server</li>',
  '<li><b>morpholib</b>, <b>delphi-portal</b>, <b>delphi-evolve</b>, <b>delphi-frontier</b></li>',
  '<li><b>Cellpose</b> (CPSAM v2) for segmentation; <b>INDRA CoGEx</b> for molecular statements</li>',
  '<li>nanopub-registry, Nanodash, Nanopub Query</li>',
];
const data = [
  `<li><b>GBIF, NCBI, Wikidata, WoRMS, PBDB</b>: identifiers and datasets for ${counts.TAXA.toLocaleString('en-US')} taxa; <b>Europe PMC</b> for the Levin papers</li>`,
  '<li><b>NVIDIA</b> Brev L40S serving the Qwen3-32B assessor</li>',
  '<li><b>Nebius</b> Scientific AI Platform: Cellpose and ESMFold2 operations</li>',
  '<li><b>OpenResearch</b> (alphaXiv <code>orx</code>) for literature grounding; <b>Formlabs</b> SLA prints</li>',
];

const built = claimsDoc.built ? new Date(claimsDoc.built) : new Date();
const DATE_SHORT = built.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const DATE_LONG = built.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

const fmt = (v) => (typeof v === 'number' ? v.toLocaleString('en-US') : v);
const vars = {
  ...Object.fromEntries(Object.entries(counts).map(([k, v]) => [k, fmt(v)])),
  DATE_SHORT, DATE_LONG,
  UNIVERSE_JSON: JSON.stringify(universe),
  PEOPLE: people.join(''), CODE: code.join(''), TEXTS: textItems.join(''), DATA: data.join(''),
};

let html = fs.readFileSync(TEMPLATE, 'utf8');
html = html.replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => {
  if (!(k in vars)) throw new Error(`template placeholder without a value: ${k}`);
  return vars[k];
});
fs.writeFileSync(OUT, html);
console.log(`wrote ${path.relative(ROOT, OUT)} (${(html.length / 1024).toFixed(0)} KB)`);
console.table(counts);

function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
