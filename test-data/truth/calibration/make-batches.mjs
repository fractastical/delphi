// Write the two calibration batches for the claims in historical-verdicts.json:
//   inputs/blind.json       statement only, no thinker, work, date or quote
//   inputs/attributed.json  the fields the main truth pipeline shows (test-data/truth/make-batches.mjs)
// Both use the claim's content key and the same shuffled order, so the only difference between the
// conditions is whether the assessor knows the claim is Aristotle's.
//
//   node test-data/truth/calibration/make-batches.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { ROOT, claimKey } from "../../../scripts/site/load-claims.mjs";

const HERE = join(ROOT, "test-data/truth/calibration");
const SRC = join(ROOT, "claim-sources/aristotle-biology");
const read = p => JSON.parse(readFileSync(p, "utf8"));

const verdicts = read(join(HERE, "historical-verdicts.json")).claims;
const claims = Object.fromEntries(read(join(SRC, "claims.json")).claims.map(c => [c.id, c]));
const works = Object.fromEntries(read(join(SRC, "inputs/sources.json")).works.map(w => [w.key, w]));

const missing = verdicts.filter(v => !claims[v.id]).map(v => v.id);
if (missing.length) throw new Error(`not in claims.json: ${missing.join(", ")}`);
const dup = verdicts.map(v => v.id).filter((id, i, a) => a.indexOf(id) !== i);
if (dup.length) throw new Error(`duplicate ids: ${dup.join(", ")}`);

// Deterministic shuffle (mulberry32) so reruns produce identical batches.
let seed = 0x5eed;
const rand = () => { seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t ^= t + Math.imul(t ^ (t >>> 7), 61 | t); return ((t ^ (t >>> 14)) >>> 0) / 2 ** 32; };
const order = verdicts.map(v => v.id);
for (let i = order.length - 1; i > 0; i--) { const j = Math.floor(rand() * (i + 1)); [order[i], order[j]] = [order[j], order[i]]; }

const byId = Object.fromEntries(verdicts.map(v => [v.id, v]));
const blind = [], attributed = [];
for (const id of order) {
  const c = claims[id], v = byId[id], key = claimKey({ label: c.label, text: c.claim });
  const statement = v.blind_statement ?? c.claim;
  if (/aristot/i.test(statement)) throw new Error(`${id}: blind statement names Aristotle; add blind_statement`);
  blind.push({ key, statement });
  attributed.push({ key, thinker: "Aristotle", year: -350, work: works[c.work]?.title ?? c.work, label: c.label, statement: c.claim,
    quote: c.quote || undefined, scope: c.scope || undefined });
}

mkdirSync(join(HERE, "inputs"), { recursive: true });
for (const [name, rows] of [["blind", blind], ["attributed", attributed]])
  writeFileSync(join(HERE, "inputs", `${name}.json`), JSON.stringify(rows, null, 2) + "\n");
const g = verdicts.reduce((m, v) => ({ ...m, [v.group]: (m[v.group] ?? 0) + 1 }), {});
console.log(`${verdicts.length} claims (${Object.entries(g).map(([k, n]) => `${n} ${k}`).join(", ")}) -> test-data/truth/calibration/inputs/{blind,attributed}.json`);
