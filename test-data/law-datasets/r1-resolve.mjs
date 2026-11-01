#!/usr/bin/env node
// Remediation round 1 (process: link-resolver, a script, no model). Re-fetches every URL and DOI in a
// slice, checks DOI metadata (title, year) against what the scout recorded, drops sources whose
// identifiers do not resolve or point at a different work, and appends a remediation entry.
//
//   node test-data/law-datasets/r1-resolve.mjs log-spiral/fossils [more slices]   |  --all
//
// No dependencies (Node 20+).

import { existsSync } from "node:fs";
import { http, now, readSlice, writeSlice, slices, slicePath } from "./lib.mjs";

const tokens = s => new Set(String(s ?? "").toLowerCase().normalize("NFKD").replace(/<[^>]+>/g, " ").replace(/[^a-z0-9 ]+/g, " ").split(/\s+/).filter(w => w.length > 3));
const jaccard = (a, b) => { const A = tokens(a), B = tokens(b); if (!A.size || !B.size) return 0; let i = 0; for (const w of A) if (B.has(w)) i++; return i / (A.size + B.size - i); };

async function csl(doi) {
  const r = await http(`https://doi.org/${encodeURI(doi)}`, { accept: "application/vnd.citationstyles.csl+json", readBody: true, timeout: 25000 });
  if (!r.ok) return { status: r.status, error: r.error };
  try {
    const j = JSON.parse(r.text);
    const title = Array.isArray(j.title) ? j.title[0] : j.title;
    const year = j.issued?.["date-parts"]?.[0]?.[0] ?? j.published?.["date-parts"]?.[0]?.[0] ?? null;
    return { status: r.status, title, year };
  } catch { return { status: r.status, error: "non-json response" }; }
}

async function checkUrl(url) {
  let r = await http(url, { method: "HEAD", timeout: 20000 });
  if (r.status == null || r.status === 405 || r.status === 403 || r.status === 400 || r.status >= 500) r = await http(url, { method: "GET", timeout: 25000 });
  return r;
}

async function pool(items, n, fn) {
  const out = []; let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k], k); } }));
  return out;
}

export async function resolveSlice(law, kingdom) {
  const rec = readSlice(law, kingdom);
  if (!rec) return null;
  rec.dropped ??= []; rec.remediation ??= [];
  const counts = { checked: rec.sources.length, kept: 0, fixed: 0, dropped: 0, flagged: 0 };
  const keep = [];
  const results = await pool(rec.sources, 6, async s => {
    const notes = [];
    let drop = null;
    const meta = s.doi ? await csl(s.doi) : null;
    const u = await checkUrl(s.url);
    const au = s.access_url && s.access_url !== s.url ? await checkUrl(s.access_url) : null;
    if (s.doi) {
      if (meta.status === 404 || meta.status === 410) drop = `doi ${s.doi} does not resolve (HTTP ${meta.status})`;
      else if (meta.title) {
        const j = jaccard(s.title, meta.title);
        s.doi_metadata = { title: meta.title, year: meta.year, title_similarity: Math.round(j * 100) / 100 };
        if (j < 0.25) drop = `doi ${s.doi} is "${meta.title}", not "${s.title}" (title similarity ${j.toFixed(2)})`;
        else if (j < 0.5) { (s.flags ??= []).push("title-differs-from-doi"); counts.flagged++; }
        if (!drop && meta.year && s.year && Math.abs(meta.year - s.year) > 1) { notes.push(`year ${s.year} -> ${meta.year} (from DOI metadata)`); s.year = meta.year; counts.fixed++; }
        if (!drop && meta.year && !s.year) { s.year = meta.year; counts.fixed++; notes.push(`year filled from DOI: ${meta.year}`); }
      }
    }
    const urlDead = u.status != null && [404, 410].includes(u.status);
    const urlDown = u.status == null;
    if (!drop && urlDead && s.doi && meta?.status && meta.status < 400) { s.url = `https://doi.org/${s.doi}`; notes.push(`url was HTTP ${u.status}; replaced by DOI link`); counts.fixed++; }
    else if (!drop && urlDead && !s.doi) drop = `url returns HTTP ${u.status} and there is no DOI`;
    if (!drop && au && [404, 410].includes(au.status)) { notes.push(`access_url returned HTTP ${au.status}; cleared`); s.access_url = null; counts.fixed++; (s.flags ??= []).push("access-url-dead"); }
    if (!drop && (urlDown || (u.status >= 400 && !urlDead)) && !(s.doi && meta?.status && meta.status < 400)) { s.verdict = "unreachable"; notes.push(`url not reachable (${u.status ?? u.error})`); }
    if (!drop) {
      s.checked = { at: now(), method: `r1 link-resolver: ${s.doi ? "doi.org CSL + " : ""}${u.status === 200 || u.status == null ? "GET/HEAD" : "HEAD/GET"} url`, http_status: u.status ?? null, ...(u.status == null ? { note: `no response: ${u.error}` } : {}), previous: s.checked };
      if (notes.length) s.r1_notes = notes;
    }
    return { s, drop };
  });
  for (const { s, drop } of results) {
    if (drop) { rec.dropped.push({ ...s, dropped_in_round: 1, dropped_reason: drop }); counts.dropped++; }
    else { keep.push(s); counts.kept++; }
  }
  rec.sources = keep;
  rec.remediation.push({ round: 1, process: "link-resolver", kind: "script", model: null, script: "test-data/law-datasets/r1-resolve.mjs", at: now(),
    summary: `Re-fetched ${counts.checked} sources; kept ${counts.kept}, dropped ${counts.dropped} (non-resolving or wrong-work identifiers), fixed ${counts.fixed}, flagged ${counts.flagged}.`, counts });
  writeSlice(law, kingdom, rec);
  return counts;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const list = args.includes("--all") ? slices().filter(s => existsSync(slicePath(s.law, s.kingdom))).map(s => [s.law, s.kingdom])
    : args.filter(a => !a.startsWith("--")).map(a => a.split("/"));
  for (const [law, kingdom] of list) {
    const c = await resolveSlice(law, kingdom);
    console.log(`${law}/${kingdom}`, c ? JSON.stringify(c) : "no record");
  }
}
