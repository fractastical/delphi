// Merge the per-chapter extraction files into claims.json, assigning stable ids and
// locating every quote in the vendored source text. Fails if any quote is not a
// verbatim substring of the text (after collapsing whitespace).
//
//   node build/merge.mjs
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SOURCE = join(ROOT, "inputs/pg1228.txt");
const SOURCE_SHA256 = "362142cb7c6f90850477520cfe2a62fe423ae92ea8eb6d9cd8b30ddb39de60b9";

const CHAPTERS = ["Introduction", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV"];
const KINDS = new Set(["empirical-generalization", "mechanism", "historical-inference", "prediction", "conceptual"]);
const TRIAGE = new Set(["testable-with-existing-data", "testable-with-new-data", "partly-testable", "not-empirically-testable"]);

const raw = readFileSync(SOURCE);
const sha = createHash("sha256").update(raw).digest("hex");
if (sha !== SOURCE_SHA256) throw new Error(`source SHA-256 ${sha} does not match pinned ${SOURCE_SHA256}`);

// Collapsed text plus, for each collapsed character, the 1-based source line it came from.
const lines = raw.toString("utf8").split("\n");
let flat = "";
const lineOf = [];
for (let i = 0; i < lines.length; i++) {
  for (const tok of lines[i].split(/\s+/).filter(Boolean)) {
    if (flat.length) { flat += " "; lineOf.push(i + 1); }
    flat += tok;
    for (let k = 0; k < tok.length; k++) lineOf.push(i + 1);
  }
}
const collapse = s => s.split(/\s+/).filter(Boolean).join(" ");

const files = readdirSync(join(ROOT, "extraction")).filter(f => /^[A-G]-.*\.json$/.test(f)).sort();
const excluded = JSON.parse(readFileSync(join(ROOT, "extraction/excluded.json"), "utf8"));
const errors = [];
const claims = [];
const unusedExclusions = new Set(excluded.map(x => `${x.file}\t${x.label}`));
for (const f of files) {
  const rows = JSON.parse(readFileSync(join(ROOT, "extraction", f), "utf8"));
  for (const [i, r] of rows.entries()) {
    if (unusedExclusions.delete(`${f}\t${r.label}`)) continue;
    const where = `${f}[${i}] ${JSON.stringify(r.label)}`;
    if (!CHAPTERS.includes(r.chapter)) errors.push(`${where}: bad chapter ${r.chapter}`);
    if (!KINDS.has(r.claim_kind)) errors.push(`${where}: bad claim_kind ${r.claim_kind}`);
    if (!TRIAGE.has(r.resolvability_triage)) errors.push(`${where}: bad resolvability_triage ${r.resolvability_triage}`);
    for (const k of ["section", "label", "claim", "quote", "scope", "candidate_data"])
      if (typeof r[k] !== "string" || !r[k].trim()) errors.push(`${where}: missing ${k}`);
    if (!Array.isArray(r.measurable_quantities)) errors.push(`${where}: measurable_quantities must be an array`);
    if (r.label?.length > 90) errors.push(`${where}: label longer than 90 characters`);

    const q = collapse(r.quote ?? "");
    const hits = [];
    for (let at = flat.indexOf(q); at !== -1 && q; at = flat.indexOf(q, at + 1)) hits.push(at);
    if (!hits.length) { errors.push(`${where}: quote not found verbatim in source`); continue; }
    // With repeated wording, take the occurrence nearest the extractor's line number.
    const at = hits.sort((a, b) => Math.abs(lineOf[a] - r.line) - Math.abs(lineOf[b] - r.line))[0];
    const lineStart = lineOf[at], lineEnd = lineOf[at + q.length - 1];
    if (Math.abs(lineStart - r.line) > 40) errors.push(`${where}: quote found at line ${lineStart}, far from stated line ${r.line}`);
    claims.push({ ...r, quote: q, line: undefined, lineStart, lineEnd });
  }
}

for (const x of unusedExclusions) errors.push(`excluded.json: no claim matches ${x.replace("\t", " / ")}`);

// Stable ids: chapter order, then position in the text.
claims.sort((a, b) => CHAPTERS.indexOf(a.chapter) - CHAPTERS.indexOf(b.chapter) || a.lineStart - b.lineStart);
const seen = new Map();
for (const c of claims) {
  const n = (seen.get(c.chapter) ?? 0) + 1;
  seen.set(c.chapter, n);
  const ch = c.chapter === "Introduction" ? "intro" : `ch${String(CHAPTERS.indexOf(c.chapter)).padStart(2, "0")}`;
  c.id = `darwin1859-${ch}-${String(n).padStart(2, "0")}`;
}
const dupQuotes = claims.filter((c, i) => claims.findIndex(d => d.quote === c.quote) !== i);
for (const d of dupQuotes) errors.push(`${d.id}: same quote as another claim`);

if (errors.length) {
  console.error(errors.join("\n"));
  console.error(`\n${errors.length} error(s); claims.json not written`);
  process.exit(1);
}

const ordered = claims.map(({ id, chapter, section, label, claim, quote, lineStart, lineEnd, claim_kind, scope, measurable_quantities, candidate_data, resolvability_triage }) =>
  ({ id, chapter, section, label, claim, quote, lineStart, lineEnd, claim_kind, scope, measurable_quantities, candidate_data, resolvability_triage }));
writeFileSync(join(ROOT, "claims.json"), JSON.stringify({ source: { file: "inputs/pg1228.txt", sha256: SOURCE_SHA256 }, claims: ordered }, null, 2) + "\n");

const tsv = [["id", "chapter", "section", "label", "claim_kind", "resolvability_triage", "measurable_quantities", "candidate_data"].join("\t"),
  ...ordered.map(c => [c.id, c.chapter, c.section, c.label, c.claim_kind, c.resolvability_triage, c.measurable_quantities.join("; "), c.candidate_data].map(v => String(v).replace(/[\t\n]/g, " ")).join("\t"))];
writeFileSync(join(ROOT, "worklist.tsv"), tsv.join("\n") + "\n");

const per = {};
for (const c of ordered) per[c.chapter] = (per[c.chapter] ?? 0) + 1;
console.log(`${ordered.length} claims from ${files.length} files`, per);
