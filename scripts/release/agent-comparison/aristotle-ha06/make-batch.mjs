// Stage 3a of the single-agent chain: blinded assessor batch from verified claims, with exactly the
// fields claim-sources/aristotle-biology/build/make-batches.mjs gives the swarm's assessors (no triage,
// measurable quantities or candidate data).
//   node make-batch.mjs <stage2-claims.json> <out-batch.json>
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const AR = join(dirname(fileURLToPath(import.meta.url)), "../../../../claim-sources/aristotle-biology");
const [inPath, outPath] = process.argv.slice(2);
const works = Object.fromEntries(JSON.parse(readFileSync(join(AR, "inputs/sources.json"), "utf8")).works.map(w => [w.key, w]));
const { claims } = JSON.parse(readFileSync(inPath, "utf8"));
const rows = claims.map(c => ({ id: c.id, label: c.label, claim: c.claim, quote: c.quote, work: c.work, work_title: works[c.work].title,
  book: c.book, translator: works[c.work].translator, section: c.section, scope: c.scope, claim_kind: c.claim_kind }));
writeFileSync(outPath, JSON.stringify(rows, null, 2) + "\n");
console.log(`${rows.length} claims -> ${outPath}`);
