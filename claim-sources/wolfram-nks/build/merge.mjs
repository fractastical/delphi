// Merge the per-range extraction files into claims.json, assigning stable ids and
// locating every quote in the cached page text. Fails if any quote is not a verbatim
// substring of the text (after collapsing whitespace) or exceeds the quotation limit.
// Chapter and section come from the page index, not from the extractors.
//
//   node build/merge.mjs
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const index = JSON.parse(readFileSync(join(ROOT, "inputs/pages.json"), "utf8"));
const MAX_QUOTE_WORDS = 60;

const KINDS = new Set(["computational-observation", "mathematical", "model-of-nature", "physical-hypothesis", "general-principle", "prediction", "conceptual"]);
const TRIAGE = new Set(["testable-with-existing-data", "testable-with-new-data", "partly-testable", "not-empirically-testable"]);

// Collapsed text of all pages (markers and heading/caption prefixes removed) plus, for
// each collapsed character, the printed page it came from. Section titles are the first
// heading on each section's start page.
let flat = "";
const pageOf = [];
const sectionTitle = {};
for (const pg of index.pages) {
  const text = readFileSync(join(ROOT, "inputs/cache/pages", `p${pg.page}.txt`), "utf8");
  if (createHash("sha256").update(text).digest("hex") !== pg.sha256) throw new Error(`cached p${pg.page} does not match inputs/pages.json; run build/fetch.mjs`);
  const lines = text.split("\n");
  // Chapter openings carry the chapter title as h1 and the section as h2; elsewhere a
  // section heading may be marked up as h1 (p. 840).
  if (pg.page === pg.sectionStart) sectionTitle[pg.sectionSlug] = (lines.find(l => l.startsWith("## ")) ?? lines.find(l => l.startsWith("# ")))?.replace(/^#+ /, "");
  for (const line of lines) {
    for (const tok of line.replace(/^(#+ |\[Caption\] )/, "").split(/\s+/).filter(Boolean)) {
      if (flat.length) { flat += " "; pageOf.push(pg.page); }
      flat += tok;
      for (let k = 0; k < tok.length; k++) pageOf.push(pg.page);
    }
  }
}
const collapse = s => s.split(/\s+/).filter(Boolean).join(" ");
const chapterOf = p => index.chapters.filter(c => c.startPage <= p).at(-1);
const pageInfo = Object.fromEntries(index.pages.map(p => [p.page, p]));

const files = readdirSync(join(ROOT, "extraction")).filter(f => /^[A-Z]-.*\.json$/.test(f)).sort();
const excluded = JSON.parse(readFileSync(join(ROOT, "extraction/excluded.json"), "utf8"));
const errors = [];
const claims = [];
const unusedExclusions = new Set(excluded.map(x => `${x.file}\t${x.label}`));
for (const f of files) {
  const rows = JSON.parse(readFileSync(join(ROOT, "extraction", f), "utf8"));
  for (const [i, r] of rows.entries()) {
    if (unusedExclusions.delete(`${f}\t${r.label}`)) continue;
    const where = `${f}[${i}] ${JSON.stringify(r.label)}`;
    if (!KINDS.has(r.claim_kind)) errors.push(`${where}: bad claim_kind ${r.claim_kind}`);
    if (!TRIAGE.has(r.resolvability_triage)) errors.push(`${where}: bad resolvability_triage ${r.resolvability_triage}`);
    for (const k of ["label", "claim", "quote", "scope", "candidate_data"])
      if (typeof r[k] !== "string" || !r[k].trim()) errors.push(`${where}: missing ${k}`);
    if (!Array.isArray(r.measurable_quantities)) errors.push(`${where}: measurable_quantities must be an array`);
    if (r.label?.length > 90) errors.push(`${where}: label longer than 90 characters`);
    if (!Number.isInteger(r.page)) errors.push(`${where}: page must be an integer`);

    const q = collapse(r.quote ?? "");
    if (q.split(" ").length > MAX_QUOTE_WORDS) errors.push(`${where}: quote longer than ${MAX_QUOTE_WORDS} words`);
    const hits = [];
    for (let at = flat.indexOf(q); at !== -1 && q; at = flat.indexOf(q, at + 1)) hits.push(at);
    if (!hits.length) { errors.push(`${where}: quote not found verbatim in source`); continue; }
    // With repeated wording, take the occurrence nearest the extractor's page.
    const at = hits.sort((a, b) => Math.abs(pageOf[a] - r.page) - Math.abs(pageOf[b] - r.page))[0];
    const pageStart = pageOf[at], pageEnd = pageOf[at + q.length - 1];
    if (Math.abs(pageStart - r.page) > 2) errors.push(`${where}: quote found on p${pageStart}, not stated p${r.page}`);
    const ch = chapterOf(pageStart);
    const sec = pageInfo[pageStart];
    claims.push({ ...r, quote: q, page: undefined, pageStart, pageEnd, chapter: ch.n, section: sectionTitle[sec.sectionSlug], sectionStart: sec.sectionStart, url: sec.url });
  }
}

for (const x of unusedExclusions) errors.push(`excluded.json: no claim matches ${x.replace("\t", " / ")}`);

// Stable ids: position in the text.
claims.sort((a, b) => a.pageStart - b.pageStart || flat.indexOf(a.quote) - flat.indexOf(b.quote));
const seen = new Map();
for (const c of claims) {
  const n = (seen.get(c.chapter) ?? 0) + 1;
  seen.set(c.chapter, n);
  c.id = `wolfram2002-ch${String(c.chapter).padStart(2, "0")}-${String(n).padStart(2, "0")}`;
}
const dupQuotes = claims.filter((c, i) => claims.findIndex(d => d.quote === c.quote) !== i);
for (const d of dupQuotes) errors.push(`${d.id}: same quote as another claim`);
for (const c of claims) if (!c.section) errors.push(`${c.id}: no section title for page ${c.pageStart}`);

if (errors.length) {
  console.error(errors.join("\n"));
  console.error(`\n${errors.length} error(s); claims.json not written`);
  process.exit(1);
}

const ordered = claims.map(({ id, chapter, section, sectionStart, label, claim, quote, pageStart, pageEnd, url, claim_kind, scope, measurable_quantities, candidate_data, resolvability_triage }) =>
  ({ id, chapter, section, sectionStart, label, claim, quote, pageStart, pageEnd, url, claim_kind, scope, measurable_quantities, candidate_data, resolvability_triage }));
writeFileSync(join(ROOT, "claims.json"), JSON.stringify({ source: { index: "inputs/pages.json", textSha256: index.textSha256 }, claims: ordered }, null, 2) + "\n");

const tsv = [["id", "chapter", "section", "page", "label", "claim_kind", "resolvability_triage", "measurable_quantities", "candidate_data"].join("\t"),
  ...ordered.map(c => [c.id, c.chapter, c.section, c.pageStart, c.label, c.claim_kind, c.resolvability_triage, c.measurable_quantities.join("; "), c.candidate_data].map(v => String(v).replace(/[\t\n]/g, " ")).join("\t"))];
writeFileSync(join(ROOT, "worklist.tsv"), tsv.join("\n") + "\n");

const per = {}, kinds = {};
for (const c of ordered) { per[c.chapter] = (per[c.chapter] ?? 0) + 1; kinds[c.claim_kind] = (kinds[c.claim_kind] ?? 0) + 1; }
console.log(`${ordered.length} claims from ${files.length} files`, per, kinds);
