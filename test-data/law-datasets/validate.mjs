#!/usr/bin/env node
// Validate law-dataset slice records against INSTRUCTIONS.md and REMEDIATION.md.
//
//   node test-data/law-datasets/validate.mjs                      # every record present
//   node test-data/law-datasets/validate.mjs log-spiral/fossils   # one slice
//   node test-data/law-datasets/validate.mjs --final              # also require 5 remediation rounds, distinct providers
//
// Exits 1 on any error. No dependencies (Node 20+).

import { existsSync, readFileSync, statSync } from "node:fs";
import { LAWS, slices, slicePath, VERDICTS, TYPES, RELEVANCE, ROUND_PROCESSES, provider, KINGDOMS } from "./lib.mjs";

const ISO = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z)?$/;
const URL_RE = /^https?:\/\//;
const SLUG = /^[a-z0-9]+([-.][a-z0-9]+)*$/;
const BANNED = ["assessment", "p_true", "truth", "stance", "supports", "refutes", "verdict", "measured", "pass_criterion", "conclusion"];
const BANNED_SRC = ["stance", "supports", "refutes", "p_true", "truth", "conclusion", "measured", "pass_criterion"];
// Placeholder text and identifiers that must never be published (BEST_PRACTICES.md section 2).
const PLACEHOLDER = /(example\.(org|com)|lorem ipsum|\bTODO\b|\bTBD\b|\bXXX\b|~~~ARTIFACT|placeholder|10\.1234\/|10\.0000\/)/i;

export const sourceStatus = rec => {
  const n = (rec.sources ?? []).filter(s => ["holds", "partial"].includes(s.verdict)).length;
  return n >= 15 ? "rich" : n >= 6 ? "moderate" : n >= 1 ? "sparse" : "none";
};

export function validateSlice(law, kingdom, { final = false } = {}) {
  const errors = [], warnings = [];
  const rel = `${law}/${kingdom}`;
  const L = LAWS.laws.find(l => l.id === law);
  if (!L || !L.kingdoms[kingdom]) return { rel, errors: [`${rel}: not a slice in laws.json`], warnings, record: null };
  const path = slicePath(law, kingdom);
  if (!existsSync(path)) return { rel, errors: [`${rel}: record missing`], warnings, record: null };
  if (statSync(path).size > 900_000) errors.push(`${rel}: record over 900 KB`);
  let d;
  try { d = JSON.parse(readFileSync(path, "utf8")); } catch (e) { return { rel, errors: [`${rel}: invalid JSON (${e.message})`], warnings, record: null }; }

  if (d.law_id !== law) errors.push(`${rel}: law_id "${d.law_id}" does not match`);
  if (d.kingdom !== kingdom) errors.push(`${rel}: kingdom "${d.kingdom}" does not match`);
  if (!ISO.test(d.scouted_at ?? "")) errors.push(`${rel}: scouted_at missing or not ISO 8601 UTC`);
  for (const k of ["kind", "model", "run"]) if (!d.scout?.[k]) errors.push(`${rel}: scout.${k} missing`);
  for (const k of BANNED) if (d[k] !== undefined) errors.push(`${rel}: top-level "${k}" must be absent (scouts describe sources, they do not test or score)`);
  if (!d.summary || d.summary.length < 40) errors.push(`${rel}: summary missing or too short`);
  if (!Array.isArray(d.search_log) || d.search_log.length < 3) errors.push(`${rel}: search_log needs at least 3 entries`);
  else d.search_log.forEach((s, i) => {
    if (!s.source || !URL_RE.test(s.url ?? "")) errors.push(`${rel}: search_log[${i}] needs source and a URL`);
    if (s.hits != null && typeof s.hits !== "number") errors.push(`${rel}: search_log[${i}].hits must be a number or null`);
  });
  if (!Array.isArray(d.sources)) { errors.push(`${rel}: sources must be an array`); return { rel, errors, warnings, record: d }; }
  if (!Array.isArray(d.dropped ?? [])) errors.push(`${rel}: dropped must be an array`);
  if (!Array.isArray(d.remediation ?? [])) errors.push(`${rel}: remediation must be an array`);

  const ids = new Set();
  d.sources.forEach((x, i) => {
    const at = `${rel}: sources[${i}]${x?.id ? ` (${x.id})` : ""}`;
    if (!x.id || !SLUG.test(x.id)) errors.push(`${at}.id missing or not a lowercase slug`);
    if (ids.has(x.id)) errors.push(`${at}.id duplicated`); ids.add(x.id);
    if (!x.title) errors.push(`${at}.title missing`);
    if (!TYPES.includes(x.type)) errors.push(`${at}.type "${x.type}" not one of ${TYPES.join(", ")}`);
    if (!URL_RE.test(x.url ?? "")) errors.push(`${at}.url missing or not http(s)`);
    if (x.access_url != null && !URL_RE.test(x.access_url)) errors.push(`${at}.access_url not http(s)`);
    if (x.doi != null && !/^10\.\d{4,9}\/\S+$/.test(x.doi)) errors.push(`${at}.doi "${x.doi}" is not a bare DOI`);
    if (x.year != null && !(Number.isInteger(x.year) && x.year > 1500 && x.year < 2100)) errors.push(`${at}.year not a plausible integer`);
    if (!VERDICTS.includes(x.verdict)) errors.push(`${at}.verdict "${x.verdict}" not one of ${VERDICTS.join(", ")}`);
    if (!RELEVANCE.includes(x.relevance)) errors.push(`${at}.relevance "${x.relevance}" not one of ${RELEVANCE.join(", ")}`);
    if (!Array.isArray(x.claims) || !x.claims.length) errors.push(`${at}.claims must name at least one claim of this law`);
    else for (const c of x.claims) if (!L.claims.includes(c)) errors.push(`${at}.claims has "${c}", not a claim of ${law}`);
    if (!Array.isArray(x.taxa)) errors.push(`${at}.taxa must be an array (may be empty)`);
    else x.taxa.forEach((t, j) => { if (!t.name) errors.push(`${at}.taxa[${j}].name missing`); });
    if (!Array.isArray(x.measurements) || !x.measurements.length) errors.push(`${at}.measurements must list the variables the source reports or holds`);
    const c = x.checked ?? {};
    if (!ISO.test(c.at ?? "")) errors.push(`${at}.checked.at missing or not ISO 8601 UTC`);
    if (!c.method) errors.push(`${at}.checked.method missing`);
    if (c.http_status == null) { if (!c.note) errors.push(`${at}.checked.http_status null without checked.note`); }
    else if (!Number.isInteger(c.http_status)) errors.push(`${at}.checked.http_status must be an integer`);
    if (x.verdict === "holds" && !x.evidence) errors.push(`${at}: verdict holds needs evidence (what the response showed)`);
    if (x.verdict === "holds" && c.http_status != null && c.http_status >= 400) errors.push(`${at}: verdict holds but http_status ${c.http_status}`);
    if (x.reported != null) {
      if (!x.reported.quote || !x.reported.locator) errors.push(`${at}.reported needs quote and locator`);
      else if (x.reported.quote.length > 400) errors.push(`${at}.reported.quote over 400 characters`);
    }
    if (kingdom === "fossils" && x.verdict !== "rejected" && x.verdict !== "not-found" && !x.geologic_age && x.type !== "paper")
      warnings.push(`${at}: fossil dataset without geologic_age`);
    for (const k of BANNED_SRC) if (x[k] !== undefined) errors.push(`${at}: "${k}" must be absent`);
    const flat = JSON.stringify(x);
    if (PLACEHOLDER.test(flat)) errors.push(`${at}: placeholder text or identifier (${flat.match(PLACEHOLDER)[0]})`);
  });
  if (d.sources.length < 6 && !d.gap_note) warnings.push(`${rel}: ${d.sources.length} sources and no gap_note explaining why`);

  if (final) {
    const rounds = d.remediation ?? [];
    for (let r = 1; r <= 5; r++) {
      const e = rounds.find(x => x.round === r);
      if (!e) { errors.push(`${rel}: remediation round ${r} (${ROUND_PROCESSES[r]}) missing`); continue; }
      if (e.process !== ROUND_PROCESSES[r]) errors.push(`${rel}: round ${r} process "${e.process}" should be ${ROUND_PROCESSES[r]}`);
      if (!ISO.test(e.at ?? "")) errors.push(`${rel}: round ${r} missing ISO time`);
      if (!e.summary) errors.push(`${rel}: round ${r} missing summary`);
      if (e.kind !== "script" && !e.model) errors.push(`${rel}: round ${r} is not a script but has no model`);
    }
    const llm = rounds.filter(x => x.kind !== "script");
    const providers = [provider(d.scout?.model), ...llm.map(x => provider(x.model))];
    if (new Set(providers).size !== providers.length) errors.push(`${rel}: scout and LLM rounds must use different providers (got ${providers.join(", ")})`);
  }
  return { rel, errors, warnings, record: d };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const final = args.includes("--final");
  const which = args.filter(a => !a.startsWith("--"));
  const list = which.length ? which.map(w => w.split("/")) : slices().filter(s => existsSync(slicePath(s.law, s.kingdom))).map(s => [s.law, s.kingdom]);
  let bad = 0, n = 0;
  for (const [law, kingdom] of list) {
    const r = validateSlice(law, kingdom, { final });
    n++;
    for (const e of r.errors) console.log("ERROR  ", e);
    for (const w of r.warnings) console.log("warning", w);
    if (r.errors.length) bad++;
  }
  console.log(`${n} record(s) checked, ${bad} with errors`);
  process.exit(bad ? 1 : 0);
}
