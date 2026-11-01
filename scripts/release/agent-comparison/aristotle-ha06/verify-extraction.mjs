// Stage 2 of the single-agent chain: deterministic verification of an extraction draft.
// Locates every quote verbatim (whitespace-collapsed) on one line of ha.txt, inside Book VI, fills in
// id, section, line, work and book, and checks the label and quote limits from
// claim-sources/aristotle-biology/extraction/INSTRUCTIONS.md.
//
//   node verify-extraction.mjs <draft.json> <out-claims.json> [--book VI]
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const AR = join(HERE, "../../../../claim-sources/aristotle-biology");
const [draftPath, outPath] = process.argv.slice(2);
const ws = s => s.replace(/\s+/g, " ").trim();
const lines = readFileSync(join(AR, "inputs/ha.txt"), "utf8").split("\n");

// Book VI bounds
const start = lines.findIndex(l => l.trim() === "## Book VI");
const end = lines.findIndex((l, i) => i > start && /^## Book /.test(l));
const draft = JSON.parse(readFileSync(draftPath, "utf8"));
const kinds = new Set(["empirical-generalization", "mechanism", "historical-inference", "prediction", "conceptual"]);
const triage = new Set(["testable-with-existing-data", "testable-with-new-data", "partly-testable", "not-empirically-testable"]);

const errors = [];
const claims = draft.map((d, k) => {
  const id = `aristotle-ha06-${String(k + 1).padStart(2, "0")}`;
  const q = ws(d.quote);
  const hits = [];
  for (let i = start + 1; i < end; i++) if (ws(lines[i]).includes(q)) hits.push(i);
  if (hits.length !== 1) errors.push(`${id}: quote found on ${hits.length} lines (${hits.map(h => h + 1)}): ${q.slice(0, 60)}…`);
  const i = hits[0] ?? -1;
  let section = "";
  for (let j = i; j > start; j--) { const m = lines[j].match(/^### (Part \d+)/); if (m) { section = m[1]; break; } }
  if (q.split(" ").length > 70) errors.push(`${id}: quote ${q.split(" ").length} words`);
  if (d.label.length > 90) errors.push(`${id}: label ${d.label.length} chars`);
  if (/\.$/.test(d.label)) errors.push(`${id}: label ends with period`);
  if (!kinds.has(d.claim_kind)) errors.push(`${id}: bad claim_kind ${d.claim_kind}`);
  if (!triage.has(d.resolvability_triage)) errors.push(`${id}: bad triage`);
  return { id, work: "ha", book: "VI", section, label: d.label, claim: d.claim, quote: d.quote, line: i + 1,
    claim_kind: d.claim_kind, scope: d.scope, measurable_quantities: d.measurable_quantities,
    candidate_data: d.candidate_data, resolvability_triage: d.resolvability_triage };
});
const dup = new Set();
for (const c of claims) { if (dup.has(c.line + c.quote)) errors.push(`${c.id}: duplicate quote`); dup.add(c.line + c.quote); }

if (errors.length) { console.error(`${errors.length} problems:\n` + errors.join("\n")); process.exitCode = 1; }
else console.log(`ok: ${claims.length} claims, all quotes verbatim on a single line of Book VI`);
writeFileSync(outPath, JSON.stringify({ source: "aristotle-biology", claims }, null, 2) + "\n");
const byPart = {};
for (const c of claims) byPart[c.section] = (byPart[c.section] || 0) + 1;
console.log("per part:", JSON.stringify(byPart));
