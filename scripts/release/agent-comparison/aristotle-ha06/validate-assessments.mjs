// Stage 4 of the single-agent chain. Same checks as claim-sources/aristotle-biology/build/merge-assessments.mjs
// (ids in input order, scores in [0,1], known verdict, required text fields, at most 3 datasets, every
// dataset URL resolves, overall = rubric-weighted mean), plus a verdict-versus-score consistency check.
//
//   node validate-assessments.mjs <batch.json> <assessments.json> <out-validated.json> <out-dropped.json>
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const rubric = JSON.parse(readFileSync(join(HERE, "../../../../claim-sources/aristotle-biology/assessment/rubric.json"), "utf8"));
const [batchPath, inPath, outPath, droppedPath] = process.argv.slice(2);
const DIMS = rubric.dimensions.map(d => d.id);
const VERDICTS = new Set(Object.keys(rubric.verdicts));
const input = JSON.parse(readFileSync(batchPath, "utf8")).map(c => c.id);
const out = JSON.parse(readFileSync(inPath, "utf8"));
const errors = [], warnings = [];
const unit = x => typeof x === "number" && x >= 0 && x <= 1;
if (out.map(r => r.claim_id).join() !== input.join()) errors.push("claim ids do not match the input batch in order");
const rows = out.map(r => {
  for (const d of DIMS) if (!unit(r.scores?.[d])) errors.push(`${r.claim_id}: score ${d}=${r.scores?.[d]}`);
  if (Object.keys(r.scores ?? {}).some(k => !DIMS.includes(k))) errors.push(`${r.claim_id}: unknown dimension`);
  if (!VERDICTS.has(r.verdict)) errors.push(`${r.claim_id}: verdict ${r.verdict}`);
  if (!unit(r.confidence)) errors.push(`${r.claim_id}: confidence`);
  for (const k of ["operationalization", "rationale"]) if (typeof r[k] !== "string" || !r[k].trim()) errors.push(`${r.claim_id}: missing ${k}`);
  if (!Array.isArray(r.candidate_datasets) || r.candidate_datasets.length > 3) errors.push(`${r.claim_id}: candidate_datasets`);
  if (!Array.isArray(r.obstacles) || r.obstacles.length > 3) errors.push(`${r.claim_id}: obstacles`);
  const overall = Math.round(DIMS.reduce((s, d, i) => s + rubric.dimensions[i].weight * (r.scores[d] ?? 0), 0) * 1000) / 1000;
  const s = r.scores;
  // verdict bands used by the single-agent run (the swarm's merge step has no such check)
  if (r.verdict === "resolvable-now" && !(overall >= 0.7 && s.operationalizability >= 0.6 && s["data-existence"] >= 0.5)) warnings.push(`${r.claim_id}: resolvable-now with overall ${overall}`);
  if (r.verdict === "partially-resolvable" && !(overall >= 0.4 && overall < 0.7)) warnings.push(`${r.claim_id}: partially-resolvable with overall ${overall}`);
  if (r.verdict === "needs-new-data" && !(s["data-existence"] <= 0.3)) warnings.push(`${r.claim_id}: needs-new-data with data-existence ${s["data-existence"]}`);
  return { ...r, overall };
});
if (errors.length) { console.error(errors.join("\n")); process.exit(1); }

const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36";
async function resolves(url) {
  try {
    const doi = url.match(/^https?:\/\/(?:dx\.)?doi\.org\/(10\.\d{4,9}\/\S+)$/i)?.[1];
    if (doi) {
      const r = await fetch(`https://doi.org/api/handles/${encodeURI(doi)}`, { signal: AbortSignal.timeout(20000) });
      return r.ok && (await r.json()).responseCode === 1 ? "ok" : "doi-not-found";
    }
    if (!/^https?:\/\/[^\s]+$/.test(url)) return "not-a-url";
    let r = await fetch(url, { method: "HEAD", redirect: "follow", headers: { "User-Agent": UA }, signal: AbortSignal.timeout(20000) });
    if (!r.ok) r = await fetch(url, { redirect: "follow", headers: { "User-Agent": UA }, signal: AbortSignal.timeout(20000) });
    return r.ok ? "ok" : `http-${r.status}`;
  } catch (e) { return `error-${e.cause?.code ?? e.name}`; }
}
const urls = [...new Set(rows.flatMap(r => r.candidate_datasets.map(d => d.url)))];
const status = new Map();
for (let i = 0; i < urls.length; i += 12) await Promise.all(urls.slice(i, i + 12).map(async u => status.set(u, await resolves(u))));
const dropped = [];
const refs = rows.reduce((n, r) => n + r.candidate_datasets.length, 0);
for (const r of rows) r.candidate_datasets = r.candidate_datasets.filter(d => {
  const s = status.get(d.url);
  if (s !== "ok") dropped.push({ claim_id: r.claim_id, name: d.name, url: d.url, status: s });
  return s === "ok";
});
writeFileSync(outPath, JSON.stringify({ rubric: `${rubric.id}/${rubric.version}`, assessments: rows }, null, 2) + "\n");
writeFileSync(droppedPath, JSON.stringify(dropped, null, 2) + "\n");
const v = {};
for (const r of rows) v[r.verdict] = (v[r.verdict] ?? 0) + 1;
console.log(`${rows.length} assessments; ${urls.length} distinct URLs; ${dropped.length}/${refs} dataset references dropped`);
console.log("verdicts:", JSON.stringify(v));
if (warnings.length) console.log("verdict/score warnings:\n" + warnings.join("\n"));
for (const [u, s] of status) if (s !== "ok") console.log("URL", s, u);
