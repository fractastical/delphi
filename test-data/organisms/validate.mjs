#!/usr/bin/env node
// Validate organism slices against the conventions in test-data/organisms/README.md.
//
//   node test-data/organisms/validate.mjs                      # all slices
//   node test-data/organisms/validate.mjs darwin-origin/ch01-02 # one slice
//
// Exits 1 if any slice has errors. No dependencies (Node 20+).

import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const MAX_FILE_BYTES = 1_000_000;
const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const SHA256 = /^[0-9a-f]{64}$/;
const ISO = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2})?Z)?$/;

function readJson(path, errors) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (e) {
    errors.push(`${path}: invalid JSON (${e.message})`);
    return null;
  }
}

function listJson(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => f.endsWith(".json")).sort();
}

function validateSlice(sliceDir) {
  const errors = [];
  const warnings = [];
  const rel = (p) => p.slice(ROOT.length + 1);

  // Size limit on everything in the slice.
  const walk = (d) => {
    for (const f of readdirSync(d)) {
      const p = join(d, f);
      const st = statSync(p);
      if (st.isDirectory()) walk(p);
      else if (st.size > MAX_FILE_BYTES) errors.push(`${rel(p)}: ${st.size} bytes exceeds 1 MB limit`);
    }
  };
  walk(sliceDir);

  if (!existsSync(join(sliceDir, "REPORT.md"))) errors.push(`${rel(sliceDir)}: REPORT.md missing`);

  // taxa
  const taxa = new Map();
  for (const f of listJson(join(sliceDir, "taxa"))) {
    const p = join(sliceDir, "taxa", f);
    const t = readJson(p, errors);
    if (!t) continue;
    const slug = basename(f, ".json");
    if (t.slug !== slug) errors.push(`${rel(p)}: slug "${t.slug}" does not match filename`);
    if (!SLUG.test(slug)) errors.push(`${rel(p)}: slug is not a lowercase hyphen slug`);
    for (const k of ["accepted_name", "rank", "identifiers", "lineage", "mentioned_in", "datasets"])
      if (t[k] === undefined) errors.push(`${rel(p)}: missing "${k}"`);
    const ids = t.identifiers ?? {};
    const hasId = ["gbif_usage_key", "ncbi_taxid", "wikidata_qid", "itis_tsn", "worms_aphia_id"].some(
      (k) => ids[k] !== null && ids[k] !== undefined && ids[k] !== ""
    );
    if (!hasId) errors.push(`${rel(p)}: no authority identifier resolved`);
    if (ids.wikidata_qid && !/^Q\d+$/.test(ids.wikidata_qid)) errors.push(`${rel(p)}: wikidata_qid must look like Q123`);
    if (ids.gbif_usage_key !== null && ids.gbif_usage_key !== undefined && !Number.isInteger(ids.gbif_usage_key))
      errors.push(`${rel(p)}: gbif_usage_key must be an integer`);
    if (!Array.isArray(t.names_as_written) || t.names_as_written.length === 0)
      errors.push(`${rel(p)}: names_as_written must be a non-empty array`);
    if (!Array.isArray(t.mentioned_in) || t.mentioned_in.length === 0)
      warnings.push(`${rel(p)}: mentioned_in is empty`);
    if (t.assessment !== undefined) errors.push(`${rel(p)}: "assessment" must be absent (vendoring agents do not score)`);
    taxa.set(slug, t);
  }

  // datasets
  const datasets = new Map();
  for (const f of listJson(join(sliceDir, "datasets"))) {
    const p = join(sliceDir, "datasets", f);
    const d = readJson(p, errors);
    if (!d) continue;
    const id = basename(f, ".json");
    if (d.id !== id) errors.push(`${rel(p)}: id "${d.id}" does not match filename`);
    if (!SLUG.test(id)) errors.push(`${rel(p)}: id is not a lowercase hyphen slug`);
    for (const k of ["label", "identifier", "distributions", "taxa", "role", "vendored_by"])
      if (d[k] === undefined) errors.push(`${rel(p)}: missing "${k}"`);
    if (d.identifier && !/^https?:\/\//.test(d.identifier)) errors.push(`${rel(p)}: identifier must be an http(s) URL or DOI URL`);
    if (d.doi && !/^10\.\d{4,9}\/\S+$/.test(d.doi)) errors.push(`${rel(p)}: doi "${d.doi}" is not a bare DOI like 10.1093/...`);
    if (d.assessment !== undefined) errors.push(`${rel(p)}: "assessment" must be absent (vendoring agents do not score)`);
    if (!Array.isArray(d.distributions) || d.distributions.length === 0) {
      errors.push(`${rel(p)}: at least one distribution required`);
    } else {
      d.distributions.forEach((x, i) => {
        if (!x.download_url || !/^https?:\/\//.test(x.download_url)) errors.push(`${rel(p)}: distributions[${i}].download_url missing or not a URL`);
        if (!x.retrieved_at || !ISO.test(x.retrieved_at)) errors.push(`${rel(p)}: distributions[${i}].retrieved_at missing or not ISO 8601 UTC`);
        if (x.inspected) {
          if (!Number.isInteger(x.byte_size) || x.byte_size <= 0) errors.push(`${rel(p)}: distributions[${i}].byte_size required when inspected`);
          if (!x.sha256 || !SHA256.test(x.sha256)) errors.push(`${rel(p)}: distributions[${i}].sha256 must be 64 hex chars when inspected`);
        }
      });
    }
    if (Array.isArray(d.counts))
      d.counts.forEach((c, i) => {
        if (!c.property_id || typeof c.value !== "number") errors.push(`${rel(p)}: counts[${i}] needs property_id and numeric value`);
      });
    if (Array.isArray(d.taxa)) {
      if (d.taxa.length === 0) errors.push(`${rel(p)}: taxa is empty`);
      for (const s of d.taxa) if (!taxa.has(s)) errors.push(`${rel(p)}: taxa references unknown slug "${s}"`);
    }
    const vb = d.vendored_by ?? {};
    if (!vb.kind || !vb.model || !vb.date) errors.push(`${rel(p)}: vendored_by needs kind, model, date`);
    if (!d.integrity || typeof d.integrity.identifier_resolves !== "boolean")
      warnings.push(`${rel(p)}: integrity.identifier_resolves not recorded`);
    datasets.set(id, d);
  }

  // taxon -> dataset back-references
  for (const [slug, t] of taxa) {
    for (const ds of t.datasets ?? []) if (!datasets.has(ds)) errors.push(`taxa/${slug}.json: datasets references unknown id "${ds}"`);
    const covering = [...datasets.values()].filter((d) => (d.taxa ?? []).includes(slug)).map((d) => d.id);
    for (const ds of covering) if (!(t.datasets ?? []).includes(ds)) warnings.push(`taxa/${slug}.json: not listing dataset "${ds}" that covers it`);
    if (covering.length === 0 && (t.datasets ?? []).length === 0) warnings.push(`taxa/${slug}.json: no dataset`);
  }

  // mentions
  const mp = join(sliceDir, "mentions.json");
  let nMentions = 0;
  if (!existsSync(mp)) errors.push(`${rel(mp)}: missing`);
  else {
    const m = readJson(mp, errors);
    if (m && !Array.isArray(m)) errors.push(`${rel(mp)}: must be an array`);
    else if (m) {
      nMentions = m.length;
      m.forEach((x, i) => {
        if (!x.taxon_slug || !taxa.has(x.taxon_slug)) errors.push(`${rel(mp)}[${i}]: taxon_slug "${x.taxon_slug}" has no taxa file`);
        if (!x.name_as_written) errors.push(`${rel(mp)}[${i}]: name_as_written missing`);
        if (!x.quote || x.quote.length < 10) errors.push(`${rel(mp)}[${i}]: quote missing or too short`);
        const s = x.source ?? {};
        const ok = typeof s.claim_id === "string" || (typeof s.file === "string" && Number.isInteger(s.line_start) && Number.isInteger(s.line_end));
        if (!ok) errors.push(`${rel(mp)}[${i}]: source needs claim_id or file+line_start+line_end`);
      });
      const mentioned = new Set(m.map((x) => x.taxon_slug));
      for (const slug of taxa.keys()) if (!mentioned.has(slug)) warnings.push(`taxa/${slug}.json: no entry in mentions.json`);
    }
  }

  return { slice: rel(sliceDir), nMentions, nTaxa: taxa.size, nDatasets: datasets.size, errors, warnings };
}

function findSlices(arg) {
  if (arg) return [join(ROOT, arg)];
  const out = [];
  for (const project of readdirSync(ROOT)) {
    const pd = join(ROOT, project);
    if (!statSync(pd).isDirectory() || project === "node_modules") continue;
    for (const slice of readdirSync(pd)) {
      const sd = join(pd, slice);
      if (statSync(sd).isDirectory() && slice !== "merged") out.push(sd);
    }
  }
  return out.sort();
}

const slices = findSlices(process.argv[2]);
if (slices.length === 0) {
  console.log("No slices found under test-data/organisms/<project>/<slice>/");
  process.exit(0);
}
let failed = false;
for (const s of slices) {
  const r = validateSlice(s);
  console.log(`${r.slice}: ${r.nMentions} mentions, ${r.nTaxa} taxa, ${r.nDatasets} datasets, ${r.errors.length} errors, ${r.warnings.length} warnings`);
  for (const e of r.errors) console.log(`  ERROR ${e}`);
  for (const w of r.warnings) console.log(`  warn  ${w}`);
  if (r.errors.length) failed = true;
}
process.exit(failed ? 1 : 0);
