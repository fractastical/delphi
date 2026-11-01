#!/usr/bin/env node
// Validate scouting records against INSTRUCTIONS.md.
//
//   node test-data/dataset-scouting/validate.mjs                                   # everything
//   node test-data/dataset-scouting/validate.mjs thompson-growth-form/thompson1917-ch02-06
//
// Exits 1 on any error. No dependencies (Node 20+).

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = dirname(fileURLToPath(import.meta.url));
export const STATUSES = ["data-ready", "partial", "gap", "not-empirically-resolvable"];
export const DS_VERDICTS = ["holds", "partial", "rejected", "unreachable", "not-found"];
const SKIP = new Set(["queue", "merged", "node_modules"]);
const ISO = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z)?$/;
const URL_RE = /^https?:\/\//;
const SLUG = /^[a-z0-9]+([-.][a-z0-9]+)*$/;

export function listRecords(arg) {
  if (arg) return [join(ROOT, arg)];
  const out = [];
  for (const project of readdirSync(ROOT)) {
    const pd = join(ROOT, project);
    if (SKIP.has(project) || !statSync(pd).isDirectory()) continue;
    for (const claim of readdirSync(pd)) {
      const cd = join(pd, claim);
      if (statSync(cd).isDirectory()) out.push(cd);
    }
  }
  return out.sort();
}

export function validateRecord(dir) {
  const errors = [], warnings = [];
  const rel = dir.slice(ROOT.length + 1);
  const [project, claimId] = rel.split("/");
  const path = join(dir, "datasets.json");
  if (!existsSync(path)) return { rel, errors: [`${rel}: datasets.json missing`], warnings, record: null };
  if (statSync(path).size > 200_000) errors.push(`${rel}: datasets.json over 200 KB`);
  let d;
  try { d = JSON.parse(readFileSync(path, "utf8")); } catch (e) { return { rel, errors: [`${rel}: invalid JSON (${e.message})`], warnings, record: null }; }
  for (const f of readdirSync(dir)) if (!["datasets.json", "REPORT.md"].includes(f)) errors.push(`${rel}: unexpected file ${f}`);

  if (d.claim_id !== claimId) errors.push(`${rel}: claim_id "${d.claim_id}" does not match directory`);
  if (d.project !== project) errors.push(`${rel}: project "${d.project}" does not match directory`);
  if (!ISO.test(d.scouted_at ?? "")) errors.push(`${rel}: scouted_at missing or not ISO 8601 UTC`);
  for (const k of ["kind", "model", "run"]) if (!d.scout?.[k]) errors.push(`${rel}: scout.${k} missing`);
  if (!Array.isArray(d.variables_needed) || d.variables_needed.length === 0) errors.push(`${rel}: variables_needed must be a non-empty array`);
  if (!STATUSES.includes(d.status)) errors.push(`${rel}: status "${d.status}" not one of ${STATUSES.join(", ")}`);
  if (!d.summary || d.summary.length < 20) errors.push(`${rel}: summary missing or too short`);
  for (const k of ["assessment", "p_true", "truth", "verdict", "measured", "pass_criterion"])
    if (d[k] !== undefined) errors.push(`${rel}: top-level "${k}" must be absent (scouts describe data, they do not test or score)`);
  if (!Array.isArray(d.search_log) || d.search_log.length === 0) errors.push(`${rel}: search_log must have at least one entry`);
  else d.search_log.forEach((s, i) => {
    if (!s.source || !s.url || !URL_RE.test(s.url)) errors.push(`${rel}: search_log[${i}] needs source and a URL`);
    if (s.hits != null && typeof s.hits !== "number") errors.push(`${rel}: search_log[${i}].hits must be a number or null`);
  });

  if (!Array.isArray(d.datasets)) errors.push(`${rel}: datasets must be an array`);
  else {
    const ids = new Set();
    d.datasets.forEach((x, i) => {
      const at = `${rel}: datasets[${i}]`;
      if (!x.id || !SLUG.test(x.id)) errors.push(`${at}.id missing or not a lowercase slug`);
      if (ids.has(x.id)) errors.push(`${at}.id "${x.id}" duplicated`); ids.add(x.id);
      if (!x.name) errors.push(`${at}.name missing`);
      if (!URL_RE.test(x.landing_url ?? "")) errors.push(`${at}.landing_url missing or not http(s)`);
      if (x.access_url != null && !/^(https?|ftp|s3):\/\//.test(x.access_url)) errors.push(`${at}.access_url not http(s), ftp or s3`);
      if (x.doi != null && !/^10\.\d{4,9}\/\S+$/.test(x.doi)) errors.push(`${at}.doi "${x.doi}" is not a bare DOI`);
      if (!Array.isArray(x.suggested_by)) errors.push(`${at}.suggested_by must be an array (empty if the scout found it)`);
      if (!DS_VERDICTS.includes(x.verdict)) errors.push(`${at}.verdict "${x.verdict}" not one of ${DS_VERDICTS.join(", ")}`);
      const c = x.checked ?? {};
      if (!ISO.test(c.at ?? "")) errors.push(`${at}.checked.at missing or not ISO 8601 UTC`);
      if (!c.method) errors.push(`${at}.checked.method missing`);
      if (c.http_status == null) { if (!c.note) errors.push(`${at}.checked.http_status null without checked.note`); }
      else if (!Number.isInteger(c.http_status)) errors.push(`${at}.checked.http_status must be an integer`);
      if (x.verdict === "holds" && !(Array.isArray(x.variables_present) && x.variables_present.length)) errors.push(`${at}: verdict holds needs variables_present`);
      if (x.verdict === "holds" && !x.evidence) errors.push(`${at}: verdict holds needs evidence (what the response showed)`);
      if (["holds", "partial"].includes(x.verdict) && c.http_status != null && c.http_status >= 400) warnings.push(`${at}: verdict ${x.verdict} with HTTP ${c.http_status}`);
      for (const k of ["assessment", "p_true", "score"]) if (x[k] !== undefined) errors.push(`${at}.${k} must be absent`);
    });
    const holds = d.datasets.filter(x => x.verdict === "holds").length;
    if (d.status === "data-ready" && holds === 0) errors.push(`${rel}: status data-ready needs at least one dataset with verdict holds`);
    if (d.status === "gap" && holds > 0) warnings.push(`${rel}: status gap but a dataset holds`);
  }
  return { rel, errors, warnings, record: d };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const dirs = listRecords(process.argv[2]);
  if (!dirs.length) { console.log("No scouting records yet."); process.exit(0); }
  let failed = false, n = 0;
  for (const dir of dirs) {
    const r = validateRecord(dir);
    n++;
    if (r.errors.length || r.warnings.length || process.argv[2]) {
      console.log(`${r.rel}: ${r.record?.status ?? "-"}, ${r.record?.datasets?.length ?? 0} datasets, ${r.errors.length} errors, ${r.warnings.length} warnings`);
      for (const e of r.errors) console.log(`  ERROR ${e}`);
      for (const w of r.warnings) console.log(`  warn  ${w}`);
    }
    if (r.errors.length) failed = true;
  }
  console.log(`${n} records checked${failed ? ", errors found" : ", all valid"}`);
  process.exit(failed ? 1 : 0);
}
