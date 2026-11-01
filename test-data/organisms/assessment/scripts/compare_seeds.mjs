#!/usr/bin/env node
// Compares an outside assessor's batch output with the project's seed scores (seeds.json).
//
//   node test-data/organisms/assessment/scripts/compare_seeds.mjs <batch-id> <assessor>
//
// Reads records/<assessor>/<batch-id>.json. For each seed in the batch: every dimension within
// 0.15 of the project score = agree. Mid seeds set the trust condition for the batch; a known-bad
// seed where the assessor's score on the named dimension is above the project's by more than
// 0.15 is reported as 'lenient on <dimension>', which is a finding about the rubric anchor as much
// as about the assessor. Prints a report; exits 0 either way (the report is the output).
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const A = join(dirname(fileURLToPath(import.meta.url)), "..");
const [batchId, assessor] = process.argv.slice(2);
if (!batchId || !assessor) { console.error("usage: compare_seeds.mjs <batch-id> <assessor>"); process.exit(1); }
const TOL = 0.15;
const seeds = JSON.parse(readFileSync(join(A, "seeds.json"), "utf8")).seeds.filter(s => s.batches.includes(batchId));
const out = JSON.parse(readFileSync(join(A, "records", assessor, `${batchId}.json`), "utf8"));
const byId = new Map(out.map(r => [r.dataset_id, r]));
let trusted = true;
for (const s of seeds) {
  const r = byId.get(s.dataset_id);
  if (!r) { console.log(`${s.dataset_id}: MISSING from assessor output`); trusted = false; continue; }
  const diffs = Object.entries(s.project_scores).map(([d, v]) => [d, +(r.scores[d] - v).toFixed(2)]);
  const off = diffs.filter(([, x]) => Math.abs(x) > TOL);
  const line = diffs.map(([d, x]) => `${d} ${x >= 0 ? "+" : ""}${x}`).join(", ");
  if (s.kind === "mid") { if (off.length) trusted = false; console.log(`${s.dataset_id} [mid]: ${off.length ? "DISAGREE on " + off.map(([d]) => d).join(", ") : "agree"} (${line})`); }
  else {
    const x = r.scores[s.dimension] - s.project_scores[s.dimension];
    console.log(`${s.dataset_id} [known-bad: ${s.dimension}]: ${x > TOL ? `LENIENT on ${s.dimension} by +${x.toFixed(2)}` : "caught"} (${line})`);
  }
}
console.log(`\nbatch ${batchId}, assessor ${assessor}: ${out.length} records; trust condition (mid seeds within ${TOL}): ${trusted ? "met" : "NOT met"}`);
