// Build docs/claim-graph.html: every claim in the repo as a clickable graph, grouped by thinker or
// by decade, coloured by proof status, with assessor numbers on the edges and links to the live
// nanopubs.
//
//   node docs/build-claim-graph.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT, loadClaims } from "./load-claims.mjs";

const HERE = join(ROOT, "docs");
const claims = loadClaims();

// Truth scores from truth/raw/<assessor>/*.json, matched by content key.
const TRUTH = join(ROOT, "truth/raw");
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
const DATA = { claims, built: new Date().toISOString().slice(0, 16).replace("T", " ") };
const seal = readFileSync(join(ROOT, "assets/logo.svg"), "utf8").trim();
const html = readFileSync(join(HERE, "claim-graph.template.html"), "utf8")
  .replace("<!--__SEAL__-->", seal.replace(/\s(width|height)="\d+"/g, "").replace("<svg ", '<svg role="img" aria-label="DELPHI seal" '))
  .replace("/*__SEAL_URI__*/", encodeURIComponent(seal))
  .replace("/*__DATA__*/null", JSON.stringify(DATA).replace(/</g, "\\u003c"));
writeFileSync(join(HERE, "claim-graph.html"), html);
const count = f => claims.filter(f).length;
console.log(`docs/claim-graph.html: ${claims.length} claims (${count(c => c.registry === "production")} in production, ${count(c => c.registry === "test")} test only, ${count(c => !c.registry)} unpublished, ${count(c => c.draft)} drafts), ${(html.length / 1024).toFixed(0)} KB`);
