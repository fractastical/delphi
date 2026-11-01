#!/usr/bin/env node
// Builds a dataset-reliability batch for an outside assessor (README.md, "Calibration seeds").
//
//   node test-data/organisms/assessment/scripts/make_batch.mjs <batch-id> [--size 25] [--seed 1]
//
// Picks unscored records from test-data/organisms/merged/datasets.json, spread across sources,
// and mixes in calibration seeds: records the project has already scored (seeds.json), unmarked,
// in random positions. Two kinds of seed: `known-bad` (a record we are confident sits at the
// bottom of one dimension, e.g. a re-query of a count already vendored under another record, on
// independence) and `mid` (an ordinary scored record). Agreement on the mid seeds within 0.15 is
// the trust condition for the batch; both scorers sliding the same way on the known-bad seeds
// localizes a broken dimension rather than an ambiguous one.
// Writes batches/<batch-id>.json: the full records, in input order, nothing marked.
import { readFileSync, writeFileSync, readdirSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const A = join(HERE, "..");
const ROOT = join(A, "../../..");
const args = process.argv.slice(2);
const batchId = args.find(a => !a.startsWith("--"));
if (!batchId) { console.error("usage: make_batch.mjs <batch-id> [--size N] [--seed N]"); process.exit(1); }
const opt = (k, d) => { const i = args.indexOf(`--${k}`); return i >= 0 ? Number(args[i + 1]) : d; };
const SIZE = opt("size", 25), SEED = opt("seed", 1);

const recs = JSON.parse(readFileSync(join(ROOT, "test-data/organisms/merged/datasets.json"), "utf8"));
const byId = new Map(recs.map(r => [r.id, r]));
const scored = new Set();
for (const who of readdirSync(join(A, "records"))) for (const f of readdirSync(join(A, "records", who)))
  if (f.endsWith(".json")) for (const s of JSON.parse(readFileSync(join(A, "records", who, f), "utf8"))) scored.add(s.dataset_id);
const seeds = JSON.parse(readFileSync(join(A, "seeds.json"), "utf8"));
const batchSeeds = seeds.seeds.filter(s => s.batches.includes(batchId));
if (!batchSeeds.length) throw new Error(`seeds.json names no seeds for batch ${batchId}`);
for (const s of batchSeeds) if (!byId.has(s.dataset_id)) throw new Error(`seed ${s.dataset_id} is not in merged/datasets.json`);

// Deterministic shuffle (mulberry32) so the batch can be regenerated.
let t = SEED >>> 0;
const rand = () => { t += 0x6D2B79F5; let x = Math.imul(t ^ (t >>> 15), 1 | t); x ^= x + Math.imul(x ^ (x >>> 7), 61 | x); return ((x ^ (x >>> 14)) >>> 0) / 4294967296; };
const shuffle = xs => { for (let i = xs.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [xs[i], xs[j]] = [xs[j], xs[i]]; } return xs; };

// Candidates: unscored, not a seed, and not another re-query variant (those are what the seeds are for).
const seedIds = new Set(batchSeeds.map(s => s.dataset_id));
const prefix = id => id.match(/^([a-z]+)/)[1]; // source database: gbif, pbdb, obis, bold, ncbi, dandi, morphosource, ...
const pool = recs.filter(r => !scored.has(r.id) && !seedIds.has(r.id) && !/-(lean-tested|validated)-\d{4}/.test(r.id));
// Round-robin across source prefixes so one source does not fill the batch.
const groups = new Map();
for (const r of shuffle([...pool])) (groups.get(prefix(r.id)) ?? groups.set(prefix(r.id), []).get(prefix(r.id))).push(r);
const order = shuffle([...groups.keys()]);
const picked = [];
while (picked.length < SIZE - batchSeeds.length && order.some(k => groups.get(k).length))
  for (const k of order) { const r = groups.get(k).shift(); if (r && picked.length < SIZE - batchSeeds.length) picked.push(r); }
const batch = shuffle([...picked, ...batchSeeds.map(s => byId.get(s.dataset_id))]);

mkdirSync(join(A, "batches"), { recursive: true });
const out = join(A, "batches", `${batchId}.json`);
writeFileSync(out, JSON.stringify({
  batch_id: batchId, built: new Date().toISOString().slice(0, 19) + "Z", rubric: "test-data/organisms/assessment/rubric.json",
  instructions: "test-data/organisms/assessment/README.md (sections 'Two levels of scoring', 'Output: records/<assessor>/<batch>.json', 'Rules'). Score every record on all five dimensions; write records/<your-name>/" + batchId + ".json in input order. Some records in this batch have already been scored by the project; they are not marked.",
  records: batch,
}, null, 2) + "\n");
console.log(`${out}: ${batch.length} records (${batchSeeds.length} seeds, ${picked.length} unscored) from ${new Set(batch.map(r => prefix(r.id))).size} sources`);
