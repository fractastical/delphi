#!/usr/bin/env node
// Validate forecast files for a round against INSTRUCTIONS.md and the round's queue slices.
//
//   node problems/forecasts/build/validate.mjs [<round>] [<file-substring>]
//
// Exits 1 on any error. No dependencies (Node 20+).
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { ROUNDS, listRounds, readJson } from "./lib.mjs";

const prob = x => typeof x === "number" && Number.isFinite(x) && x >= 0 && x <= 1;

export function validateFile(round, file) {
  const errors = [], warnings = [];
  const dir = join(ROUNDS, round);
  let f;
  try { f = readJson(join(dir, "forecasts", file)); } catch (e) { return { file, errors: [`unreadable JSON: ${e.message}`], warnings }; }
  const m = file.match(/^(.+)--(slice-\d+)\.json$/);
  if (!m) return { file, errors: ["file name must be <model-slug>--<slice>.json"], warnings };
  const [, model, slice] = m;
  if (f.round !== round) errors.push(`round is ${f.round}, expected ${round}`);
  if (f.slice !== slice) errors.push(`slice is ${f.slice}, expected ${slice}`);
  if (f.model !== model) errors.push(`model is ${f.model}, expected ${model}`);
  if (!f.provider) errors.push("provider missing");
  if (!f.generated || Number.isNaN(Date.parse(f.generated))) errors.push("generated must be an ISO timestamp");
  const q = readJson(join(dir, "queue", `${slice}.json`));
  const want = new Map(q.problems.map(p => [p.id, p]));
  const seen = new Set();
  for (const p of f.problems ?? []) {
    const w = want.get(p.problem);
    if (!w) { errors.push(`unknown problem ${p.problem}`); continue; }
    if (seen.has(p.problem)) errors.push(`${p.problem} appears twice`);
    seen.add(p.problem);
    for (const k of ["p_solved_30d", "p_solved_365d"]) if (!prob(p[k])) errors.push(`${p.problem}.${k} must be a number in [0,1]`);
    if (prob(p.p_solved_30d) && prob(p.p_solved_365d) && p.p_solved_30d > p.p_solved_365d) errors.push(`${p.problem}: p_solved_30d > p_solved_365d`);
    if (typeof p.rationale !== "string" || p.rationale.trim().length < 40) errors.push(`${p.problem}: rationale missing or too short`);
    if (!q.blind && w.prior && prob(p.p_solved_30d) && (Math.abs(p.p_solved_30d - w.prior.p_solved_30d) > 0.1 || Math.abs(p.p_solved_365d - w.prior.p_solved_365d) > 0.1) && !p.change_reason)
      errors.push(`${p.problem}: moved more than 0.10 from the prior without change_reason`);
    const wantA = new Map(w.approaches.map(a => [a.id, a]));
    const seenA = new Set();
    let best = 0;
    for (const a of p.approaches ?? []) {
      if (!wantA.has(a.approach)) { errors.push(`${p.problem}: unknown approach ${a.approach}`); continue; }
      if (seenA.has(a.approach)) errors.push(`${a.approach} appears twice`);
      seenA.add(a.approach);
      for (const k of ["p_complete", "p_settle"]) if (!prob(a[k])) errors.push(`${a.approach}.${k} must be a number in [0,1]`);
      if (typeof a.note !== "string" || a.note.trim().length < 10) errors.push(`${a.approach}: note missing`);
      if (prob(a.p_complete) && prob(a.p_settle)) best = Math.max(best, a.p_complete * a.p_settle);
    }
    for (const id of wantA.keys()) if (!seenA.has(id)) errors.push(`${p.problem}: approach ${id} missing`);
    if (prob(p.p_solved_30d) && p.p_solved_30d + 0.02 < best) warnings.push(`${p.problem}: p_solved_30d ${p.p_solved_30d} below best approach p_complete*p_settle ${best.toFixed(2)}`);
  }
  for (const id of want.keys()) if (!seen.has(id)) errors.push(`problem ${id} missing`);
  return { file, errors, warnings };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const round = process.argv[2] && /^r\d+-/.test(process.argv[2]) ? process.argv[2] : listRounds().at(-1);
  const sub = process.argv.find((a, i) => i > 1 && !/^r\d+-/.test(a));
  const dir = join(ROUNDS, round, "forecasts");
  const files = (existsSync(dir) ? readdirSync(dir).filter(f => f.endsWith(".json")) : []).filter(f => !sub || f.includes(sub)).sort();
  let bad = 0;
  for (const file of files) {
    const { errors, warnings } = validateFile(round, file);
    if (errors.length) bad++;
    console.log(`${errors.length ? "FAIL" : "ok  "} ${file}${warnings.length ? ` (${warnings.length} warnings)` : ""}`);
    for (const e of errors) console.log(`   error: ${e}`);
    for (const w of warnings) console.log(`   warn:  ${w}`);
  }
  console.log(`${round}: ${files.length} files, ${bad} with errors`);
  process.exit(bad ? 1 : 0);
}
