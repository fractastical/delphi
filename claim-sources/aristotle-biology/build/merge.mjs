// Merge the extraction files into claims.json, assigning stable ids and locating every quote
// in its work's vendored text. Fails if a text does not match the SHA-256 pinned in
// inputs/sources.json, if any quote is not a verbatim substring of its work (after collapsing
// whitespace), or if the stated book disagrees with where the quote is. Book and part come from
// the text's own "## Book" and "### Part" headings.
//
//   node build/merge.mjs
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const { works } = JSON.parse(readFileSync(join(ROOT, "inputs/sources.json"), "utf8"));
const MAX_QUOTE_WORDS = 70;
const ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];

const KINDS = new Set(["empirical-generalization", "mechanism", "historical-inference", "prediction", "conceptual"]);
const TRIAGE = new Set(["testable-with-existing-data", "testable-with-new-data", "partly-testable", "not-empirically-testable"]);

// Per work: collapsed text, the 1-based line of each collapsed character, and the book and part
// in force at each line.
const text = {};
for (const w of works) {
  const raw = readFileSync(join(ROOT, "inputs", w.text_file));
  if (createHash("sha256").update(raw).digest("hex") !== w.text_sha256) throw new Error(`inputs/${w.text_file} does not match sources.json; run build/fetch.py`);
  const lines = raw.toString("utf8").split("\n");
  let flat = "", book = null, part = "";
  const lineOf = [], bookAt = [], partAt = [];
  for (let i = 0; i < lines.length; i++) {
    const b = lines[i].match(/^## Book ([IVX]+)$/), p = lines[i].match(/^### (.+)$/);
    if (b) { book = b[1]; part = ""; }
    if (p) part = p[1];
    bookAt[i + 1] = book;
    partAt[i + 1] = part;
    if (lines[i].startsWith("#")) continue;
    for (const tok of lines[i].split(/\s+/).filter(Boolean)) {
      if (flat.length) { flat += " "; lineOf.push(i + 1); }
      flat += tok;
      for (let k = 0; k < tok.length; k++) lineOf.push(i + 1);
    }
  }
  text[w.key] = { flat, lineOf, bookAt, partAt };
}
const order = works.map(w => w.key);
const collapse = s => s.split(/\s+/).filter(Boolean).join(" ");

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
    if (!text[r.work]) { errors.push(`${where}: unknown work ${r.work}`); continue; }
    if (!KINDS.has(r.claim_kind)) errors.push(`${where}: bad claim_kind ${r.claim_kind}`);
    if (!TRIAGE.has(r.resolvability_triage)) errors.push(`${where}: bad resolvability_triage ${r.resolvability_triage}`);
    for (const k of ["label", "claim", "quote", "scope", "candidate_data"])
      if (typeof r[k] !== "string" || !r[k].trim()) errors.push(`${where}: missing ${k}`);
    if (!Array.isArray(r.measurable_quantities)) errors.push(`${where}: measurable_quantities must be an array`);
    if (r.label?.length > 90) errors.push(`${where}: label longer than 90 characters`);

    const { flat, lineOf, bookAt, partAt } = text[r.work];
    const q = collapse(r.quote ?? "");
    if (q.split(" ").length > MAX_QUOTE_WORDS) errors.push(`${where}: quote longer than ${MAX_QUOTE_WORDS} words`);
    const hits = [];
    for (let at = flat.indexOf(q); at !== -1 && q; at = flat.indexOf(q, at + 1)) hits.push(at);
    if (!hits.length) { errors.push(`${where}: quote not found verbatim in ${r.work}`); continue; }
    // With repeated wording, take the occurrence nearest the extractor's line number.
    const at = hits.sort((a, b) => Math.abs(lineOf[a] - r.line) - Math.abs(lineOf[b] - r.line))[0];
    const lineStart = lineOf[at], lineEnd = lineOf[at + q.length - 1];
    if (Math.abs(lineStart - r.line) > 3) errors.push(`${where}: quote found at line ${lineStart}, not stated line ${r.line}`);
    const book = bookAt[lineStart], part = partAt[lineStart];
    if (r.book !== book) errors.push(`${where}: stated book ${r.book}, quote is in Book ${book}`);
    claims.push({ ...r, quote: q, line: undefined, book, section: part, lineStart, lineEnd, pos: at });
  }
}

for (const x of unusedExclusions) errors.push(`excluded.json: no claim matches ${x.replace("\t", " / ")}`);

// Stable ids: work order in sources.json, then book, then position in the text.
claims.sort((a, b) => order.indexOf(a.work) - order.indexOf(b.work) || a.pos - b.pos);
const seen = new Map();
for (const c of claims) {
  const wb = `${c.work}${String(ROMAN.indexOf(c.book) + 1).padStart(2, "0")}`;
  const n = (seen.get(wb) ?? 0) + 1;
  seen.set(wb, n);
  c.id = `aristotle-${wb}-${String(n).padStart(2, "0")}`;
}
const dupQuotes = claims.filter((c, i) => claims.findIndex(d => d.quote === c.quote) !== i);
for (const d of dupQuotes) errors.push(`${d.id}: same quote as another claim`);

if (errors.length) {
  console.error(errors.join("\n"));
  console.error(`\n${errors.length} error(s); claims.json not written`);
  process.exit(1);
}

const ordered = claims.map(({ id, work, book, section, label, claim, quote, lineStart, lineEnd, claim_kind, scope, measurable_quantities, candidate_data, resolvability_triage }) =>
  ({ id, work, book, section, label, claim, quote, lineStart, lineEnd, claim_kind, scope, measurable_quantities, candidate_data, resolvability_triage }));
const source = { index: "inputs/sources.json", works: works.map(({ key, title, translator, text_sha256 }) => ({ key, title, translator, text_sha256 })) };
writeFileSync(join(ROOT, "claims.json"), JSON.stringify({ source, claims: ordered }, null, 2) + "\n");

const tsv = [["id", "work", "book", "section", "label", "claim_kind", "resolvability_triage", "measurable_quantities", "candidate_data"].join("\t"),
  ...ordered.map(c => [c.id, c.work, c.book, c.section, c.label, c.claim_kind, c.resolvability_triage, c.measurable_quantities.join("; "), c.candidate_data].map(v => String(v).replace(/[\t\n]/g, " ")).join("\t"))];
writeFileSync(join(ROOT, "worklist.tsv"), tsv.join("\n") + "\n");

const per = {}, kinds = {};
for (const c of ordered) { per[`${c.work} ${c.book}`] = (per[`${c.work} ${c.book}`] ?? 0) + 1; kinds[c.claim_kind] = (kinds[c.claim_kind] ?? 0) + 1; }
console.log(`${ordered.length} claims from ${files.length} files`, per, kinds);
