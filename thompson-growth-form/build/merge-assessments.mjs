// Validate the assessors' raw outputs, compute overall scores from the rubric weights,
// check that every proposed dataset URL resolves, and write assessment/assessments.json.
// Fails if any assessor's batch is missing a claim, has an out-of-range score, or an
// unknown verdict. Unresolvable dataset URLs are dropped and reported, not published.
//
//   node build/merge-assessments.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const A = join(ROOT, "assessment");
const rubric = JSON.parse(readFileSync(join(A, "rubric.json"), "utf8"));
const DIMS = rubric.dimensions.map(d => d.id);
const VERDICTS = new Set(Object.keys(rubric.verdicts));
const only = process.env.ASSESSORS?.split(",");
const ASSESSORS = JSON.parse(readFileSync(join(A, "assessors.json"), "utf8")).filter(a => !only || only.includes(a.id));
const { claims } = JSON.parse(readFileSync(join(ROOT, "claims.json"), "utf8"));
const claimIds = new Set(claims.map(c => c.id));
const batches = readdirSync(join(A, "inputs")).filter(f => /^batch-\d+\.json$/.test(f)).sort();

const errors = [];
const unit = x => typeof x === "number" && x >= 0 && x <= 1;
const rows = [];
for (const a of ASSESSORS) {
  for (const b of batches) {
    const input = JSON.parse(readFileSync(join(A, "inputs", b), "utf8")).map(c => c.id);
    const path = join(A, "raw", a.id, b);
    if (!existsSync(path)) { errors.push(`${a.id}/${b}: missing`); continue; }
    let out;
    try { out = JSON.parse(readFileSync(path, "utf8")); } catch (e) { errors.push(`${a.id}/${b}: ${e.message}`); continue; }
    const got = out.map(r => r.claim_id);
    if (got.join() !== input.join()) errors.push(`${a.id}/${b}: claim ids do not match the input batch in order`);
    for (const r of out) {
      const where = `${a.id}/${b} ${r.claim_id}`;
      if (!claimIds.has(r.claim_id)) { errors.push(`${where}: unknown claim`); continue; }
      for (const d of DIMS) if (!unit(r.scores?.[d])) errors.push(`${where}: score ${d}=${r.scores?.[d]}`);
      if (Object.keys(r.scores ?? {}).some(k => !DIMS.includes(k))) errors.push(`${where}: unknown score dimension`);
      if (!VERDICTS.has(r.verdict)) errors.push(`${where}: verdict ${r.verdict}`);
      if (!unit(r.confidence)) errors.push(`${where}: confidence ${r.confidence}`);
      for (const k of ["operationalization", "rationale"]) if (typeof r[k] !== "string" || !r[k].trim()) errors.push(`${where}: missing ${k}`);
      if (!Array.isArray(r.candidate_datasets) || r.candidate_datasets.length > 3) errors.push(`${where}: candidate_datasets`);
      if (!Array.isArray(r.obstacles)) errors.push(`${where}: obstacles`);
      const overall = DIMS.reduce((s, d, i) => s + rubric.dimensions[i].weight * (r.scores?.[d] ?? 0), 0);
      rows.push({ assessor: a.id, batch: b, claim_id: r.claim_id, ...r, overall: Math.round(overall * 1000) / 1000 });
    }
  }
}
if (errors.length) {
  console.error(errors.slice(0, 50).join("\n"));
  console.error(`\n${errors.length} error(s); assessments.json not written`);
  process.exit(1);
}

// URL checks: DOIs through the DOI handle API, everything else by fetching the page.
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36";
async function resolves(url) {
  try {
    const doi = url.match(/^https?:\/\/(?:dx\.)?doi\.org\/(10\.\d{4,9}\/\S+)$/i)?.[1];
    if (doi) {
      const r = await fetch(`https://doi.org/api/handles/${encodeURI(doi)}`, { signal: AbortSignal.timeout(20000) });
      return r.ok && (await r.json()).responseCode === 1 ? "ok" : `doi-not-found`;
    }
    if (!/^https?:\/\/[^\s]+$/.test(url)) return "not-a-url";
    let r = await fetch(url, { method: "HEAD", redirect: "follow", headers: { "User-Agent": UA }, signal: AbortSignal.timeout(20000) });
    if (!r.ok) r = await fetch(url, { redirect: "follow", headers: { "User-Agent": UA }, signal: AbortSignal.timeout(20000) });
    return r.ok ? "ok" : `http-${r.status}`;
  } catch (e) {
    return `error-${e.cause?.code ?? e.name}`;
  }
}
const urls = [...new Set(rows.flatMap(r => r.candidate_datasets.map(d => d.url)))];
const status = new Map();
for (let i = 0; i < urls.length; i += 12)
  await Promise.all(urls.slice(i, i + 12).map(async u => status.set(u, await resolves(u))));

const dropped = [];
for (const r of rows) {
  r.candidate_datasets = r.candidate_datasets.filter(d => {
    const s = status.get(d.url);
    if (s !== "ok") dropped.push({ assessor: r.assessor, claim_id: r.claim_id, name: d.name, url: d.url, status: s });
    return s === "ok";
  });
}
writeFileSync(join(A, "assessments.json"), JSON.stringify({ rubric: `${rubric.id}/${rubric.version}`, assessments: rows }, null, 2) + "\n");
writeFileSync(join(A, "dropped-datasets.json"), JSON.stringify(dropped, null, 2) + "\n");

const byAssessor = {};
for (const a of ASSESSORS) {
  const mine = rows.filter(r => r.assessor === a.id);
  const v = {};
  for (const r of mine) v[r.verdict] = (v[r.verdict] ?? 0) + 1;
  byAssessor[a.id] = { n: mine.length, verdicts: v, droppedUrls: dropped.filter(d => d.assessor === a.id).length };
}
console.log(`${rows.length} assessments; ${urls.length} distinct dataset URLs, ${dropped.length} dropped references`);
console.log(JSON.stringify(byAssessor, null, 1));
