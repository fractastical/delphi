// Build docs/claim-graph.html: every claim in the repo as a clickable graph, grouped by thinker or
// by decade, coloured by proof status, with assessor numbers on the edges and links to the live
// nanopubs.
//
//   node docs/build-claim-graph.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { ROOT, loadClaims } from "./load-claims.mjs";

const HERE = join(ROOT, "docs");
const claims = loadClaims();
const DATA = { claims, built: new Date().toISOString().slice(0, 16).replace("T", " ") };
const seal = readFileSync(join(ROOT, "assets/logo.svg"), "utf8").trim();
const html = readFileSync(join(HERE, "claim-graph.template.html"), "utf8")
  .replace("<!--__SEAL__-->", seal.replace(/\s(width|height)="\d+"/g, "").replace("<svg ", '<svg role="img" aria-label="DELPHI seal" '))
  .replace("/*__SEAL_URI__*/", encodeURIComponent(seal))
  .replace("/*__DATA__*/null", JSON.stringify(DATA).replace(/</g, "\\u003c"));
writeFileSync(join(HERE, "claim-graph.html"), html);
const count = f => claims.filter(f).length;
console.log(`docs/claim-graph.html: ${claims.length} claims (${count(c => c.registry === "production")} in production, ${count(c => c.registry === "test")} test only, ${count(c => !c.registry)} unpublished, ${count(c => c.draft)} drafts), ${(html.length / 1024).toFixed(0)} KB`);
