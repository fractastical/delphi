// Write blinded assessor input batches (assessment/inputs/batch-N.json) from claims.json.
// Assessors see the claim and its paper, never the extractor's triage, measurable quantities
// or candidate data.
//
//   node build/make-batches.mjs [--size 45]
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const sizeArg = process.argv.indexOf("--size");
const SIZE = sizeArg > -1 ? +process.argv[sizeArg + 1] : 45;
const { claims } = JSON.parse(readFileSync(join(ROOT, "claims.json"), "utf8"));
const papers = Object.fromEntries(JSON.parse(readFileSync(join(ROOT, "inputs/sources.json"), "utf8")).papers.map(p => [p.key, p]));

const rows = claims.map(c => ({
  id: c.id, label: c.label, claim: c.claim, quote: c.quote, paper: c.paper, paper_title: papers[c.paper].title,
  year: papers[c.paper].year, section: c.section, scope: c.scope, claim_kind: c.claim_kind,
}));
mkdirSync(join(ROOT, "assessment/inputs"), { recursive: true });
const n = Math.ceil(rows.length / SIZE);
for (let i = 0; i < n; i++)
  writeFileSync(join(ROOT, `assessment/inputs/batch-${i + 1}.json`), JSON.stringify(rows.slice(i * SIZE, (i + 1) * SIZE), null, 2) + "\n");
console.log(`${rows.length} claims in ${n} batches of up to ${SIZE}`);
