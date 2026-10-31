// Write blinded truth-assessment batches (truth/inputs/batch-NN.json) for every claim that has no
// truth score yet from every assessor. Assessors see the claim, never our proof status, testability
// scores or other assessors' outputs.
//
//   node truth/make-batches.mjs [--size 75]
import { writeFileSync, mkdirSync, readdirSync, readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { ROOT, loadClaims } from "../docs/load-claims.mjs";

const sizeArg = process.argv.indexOf("--size");
const SIZE = sizeArg > -1 ? +process.argv[sizeArg + 1] : 75;
const OUT = join(ROOT, "truth/inputs");
const RAW = join(ROOT, "truth/raw");

const scored = {};
for (const who of existsSync(RAW) ? readdirSync(RAW) : [])
  for (const f of readdirSync(join(RAW, who)).filter(f => f.endsWith(".json")))
    try { for (const r of JSON.parse(readFileSync(join(RAW, who, f), "utf8"))) (scored[r.key] ??= new Set()).add(who); } catch {}

const assumptions = ctx => (ctx || "").replace(/Formal status:[^]*$/, "").replace(/^Assumptions:\s*/, "").trim() || undefined;
const todo = loadClaims().filter(c => !scored[c.key] || scored[c.key].size < 2).map(c => ({
  key: c.key, thinker: c.thinker, year: c.year, work: c.work, label: c.label, statement: c.text,
  quote: c.quote || undefined, scope: c.scope || undefined, notation: c.notation || undefined, assumptions: assumptions(c.context),
}));

mkdirSync(OUT, { recursive: true });
const first = Math.max(0, ...readdirSync(OUT).map(f => +(f.match(/^batch-(\d+)\.json$/)?.[1] ?? 0))) + 1;
const n = Math.ceil(todo.length / SIZE);
const names = [];
for (let i = 0; i < n; i++) {
  names.push(`batch-${String(first + i).padStart(2, "0")}.json`);
  writeFileSync(join(OUT, names[i]), JSON.stringify(todo.slice(i * SIZE, (i + 1) * SIZE), null, 2) + "\n");
}
console.log(`${todo.length} claims to score in ${n} batches of up to ${SIZE}${n ? ` (truth/inputs/${names.join(", ")})` : ""}`);
