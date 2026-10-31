// Build docs/claim-graph.html: every claim in the repo as a clickable graph, grouped by thinker or
// by decade, coloured by proof status, with assessor numbers on the edges and links to the live
// nanopubs.
//
//   node scripts/site/build-claim-graph.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT, VERIFICATION, EVIDENCE, loadClaims } from "./load-claims.mjs";

const HERE = join(ROOT, "docs");
const claims = loadClaims();

// Truth scores from test-data/truth/raw/<assessor>/*.json, matched by content key.
const TRUTH = join(ROOT, "test-data/truth/raw");
const LABEL = { gpt: "GPT-5.6 Sol", grok: "Grok 4.7", gemini: "Gemini 4 Argon" };
const truth = {};
for (const who of existsSync(TRUTH) ? readdirSync(TRUTH) : []) {
  for (const f of readdirSync(join(TRUTH, who)).filter(f => f.endsWith(".json"))) {
    let rows; try { rows = JSON.parse(readFileSync(join(TRUTH, who, f), "utf8")); } catch { console.warn(`skipping unparsable ${who}/${f}`); continue; }
    for (const r of rows) if (typeof r.p_true === "number") (truth[r.key] ??= []).push({ who: LABEL[who] ?? who, p: r.p_true, rationale: r.rationale });
  }
}
for (const c of claims) {
  c.truthBy = truth[c.key] ?? [];
  c.truth = c.truthBy.length ? Math.round(1000 * c.truthBy.reduce((s, x) => s + x.p, 0) / c.truthBy.length) / 1000 : null;
}
const built = new Date().toISOString().slice(0, 16).replace("T", " ");
const count = f => claims.filter(f).length;
const DATA = { claims, built };
// docs/theorems.html lists exactly the claims with `theorem` set (see load-claims.mjs), from any
// project: a math claim that has reached proof, not a claim from claim-sources/math-bio-claims/.
const THEOREMS = { claims: claims.filter(c => c.theorem), total: claims.length, math: count(c => c.math), built };
const seal = readFileSync(join(ROOT, "assets/logo.svg"), "utf8").trim();
const inline = svg => svg.replace(/<svg[^>]*>/, t => t.replace(/\s(width|height)="\d+"/g, "")).replace("<svg ", '<svg role="img" aria-label="DELPHI seal" ');
for (const [page, data] of [["claim-graph", DATA], ["claims-query", DATA], ["theorems", THEOREMS]]) {
  const html = readFileSync(join(HERE, `${page}.template.html`), "utf8")
    .replace("<!--__SEAL__-->", inline(seal))
    .replace("<!--__SEAL_MONO__-->", inline(seal.replace(/#14213d/gi, "#000").replace(/#e5c07b/gi, "#fff")))
    .replace("/*__SEAL_URI__*/", encodeURIComponent(seal))
    .replace("/*__DATA__*/null", JSON.stringify(data).replace(/</g, "\\u003c"));
  writeFileSync(join(HERE, `${page}.html`), html);
  console.log(`docs/${page}.html: ${(html.length / 1024).toFixed(0)} KB`);
}

// Flat export for scripts: one row per claim with its scores.
const rows = claims.map(c => ({ id: c.id, key: c.key, label: c.label, statement: c.text, quote: c.quote || null, thinker: c.thinker, year: c.year,
  work: c.work, chapter: c.section || null, kind: c.kind, status: c.status, proof: c.proof ?? null, verification: c.verification,
  math: c.math, theorem: c.theorem, notation: c.notation || null, lean_theorems: c.lean?.theorems ?? null,
  evidence: c.evidence, data_test: c.dataTest ? { verdict: c.dataTest.verdict, confidence: c.dataTest.confidence, preregistered: c.dataTest.preregistered, path: c.dataTest.path, test_contract: c.dataTest.testContract, revisions: c.dataTest.revisions } : null,
  testability: c.resolvability ?? null, truth: c.truth,
  truth_by: c.truthBy.map(x => ({ assessor: x.who, p_true: x.p })), assessor_confidence: c.confidence ?? null,
  nanopub: c.uri || null, registry: c.registry || null, draft: !!c.draft }));
writeFileSync(join(HERE, "claims.json"), JSON.stringify({ built: DATA.built, claims: rows }, null, 1) + "\n");
console.log(`${claims.length} claims (${count(c => c.registry === "production")} in production, ${count(c => c.registry === "test")} test only, ${count(c => !c.registry)} unpublished, ${count(c => c.draft)} drafts); docs/claims.json written`);
console.log(`verification: ${VERIFICATION.map(v => `${count(c => c.verification === v)} ${v}`).join(", ")}`);
console.log(`tested against data: ${count(c => c.evidence)} (${EVIDENCE.map(v => `${count(c => c.evidence === v)} ${v}`).join(", ")}); ${count(c => c.verification === "untested" && !c.evidence)} neither proved nor tested`);
console.log(`${count(c => c.math)} math claims; ${count(c => c.theorem)} theorems (math and proved): ${count(c => c.theorem && c.proof === "lean")} machine-checked in Lean 4, ${count(c => c.theorem && c.proof === "literature")} proved in the literature`);
