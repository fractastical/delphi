// Builds a plain, flat export of the claims for third-party import: docs/export/claims.csv,
// docs/export/claims.json and docs/export/README.md (field dictionary).
//
// Reads docs/claims.json (run build-claim-graph.mjs first so it is current) and keeps only what a
// reader outside the project needs. It deliberately drops internal fields (hash keys, assessor
// truth scores and testability, Lean module details, MorphoLib links, registry and draft flags,
// pre-registration contracts) and splits the overlapping `status` / `verification` / `evidence`
// fields into one summary `status` plus two clearly named columns, `proof` and `data_test`.
//
//   node scripts/site/build-export.mjs
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = join(ROOT, "docs/export");
const REPO_URL = "https://github.com/fractastical/delphi/blob/main";
const src = JSON.parse(readFileSync(join(ROOT, "docs/claims.json"), "utf8"));

// proof: how (and whether) a mathematical claim was proved.
const proof = c => c.verification === "lean" ? "lean"
  : c.verification === "literature" ? "literature"
  : c.verification === "partial" ? "partial"
  : c.verification === "refuted" ? "disproved" : "none";

// status: one value per claim, in order of strength. A claim with a proof and a data test is
// "proved"; its data test is still in `data_test`.
const status = c => c.theorem ? "proved"
  : c.verification === "partial" ? "partially_proved"
  : c.verification === "refuted" ? "disproved"
  : c.evidence ? "tested" : "untested";

const clean = s => (s ?? "").replace(/\s+/g, " ").trim();

const rows = src.claims.map(c => ({
  id: c.id,
  title: clean(c.label),
  statement: clean(c.statement),
  author: c.thinker,
  work: c.work,
  year: c.year,
  chapter: clean(c.chapter),
  quote: clean(c.quote),
  claim_type: c.kind,
  is_mathematical: !!c.math,
  status: status(c),
  proof: proof(c),
  data_test: c.evidence ?? "none",
  data_test_kind: c.evidence ? (c.evidence_kind ?? "none") : "none",
  data_test_url: c.data_test?.path ? `${REPO_URL}/${c.data_test.path}` : "",
  published: !!c.nanopub,
  nanopub_url: c.nanopub ?? "",
}));

const COLUMNS = Object.keys(rows[0]);
const csvCell = v => { const s = String(v); return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
const csv = [COLUMNS.join(","), ...rows.map(r => COLUMNS.map(k => csvCell(r[k])).join(","))].join("\r\n") + "\r\n";

const count = f => rows.filter(f).length;
const stat = Object.fromEntries(["proved", "partially_proved", "disproved", "tested", "untested"].map(s => [s, count(r => r.status === s)]));

mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, "claims.csv"), csv);
writeFileSync(join(OUT, "claims.json"), JSON.stringify({ built: src.built, count: rows.length, claims: rows }, null, 1) + "\n");

writeFileSync(join(OUT, "README.md"), `# Claims export

Flat, one-row-per-claim copy of the claim graph, built by \`node scripts/site/build-export.mjs\`
from [\`docs/claims.json\`](../claims.json). Do not edit by hand.

- [\`claims.csv\`](claims.csv): UTF-8, comma-separated, CRLF line ends, header row, quoted where needed.
- [\`claims.json\`](claims.json): the same rows as \`{ built, count, claims: [...] }\`.

${rows.length} claims: ${stat.proved} proved, ${stat.partially_proved} partially proved, ${stat.disproved} disproved,
${stat.tested} tested against data, ${stat.untested} untested.

## Fields

| field | values | meaning |
|---|---|---|
| \`id\` | text | Stable claim id, e.g. \`darwin1859-ch01-09\`. |
| \`title\` | text | One-line summary of the claim. |
| \`statement\` | text | The claim, stated in full. |
| \`author\` | text | Whose claim it is. |
| \`work\` | text | Book or paper the claim comes from. |
| \`year\` | number | Year of that work (negative = BCE). |
| \`chapter\` | text | Chapter or section, where there is one. |
| \`quote\` | text | Passage in the source the claim was extracted from. |
| \`claim_type\` | text | Kind of claim, e.g. \`empirical-generalization\`, \`mathematical-law\`. |
| \`is_mathematical\` | true / false | A formal mathematical statement that a proof could settle. |
| \`status\` | \`proved\`, \`partially_proved\`, \`disproved\`, \`tested\`, \`untested\` | Summary, strongest first. **\`untested\` means no proof and no data test yet, not that the claim is false.** |
| \`proof\` | \`lean\`, \`literature\`, \`partial\`, \`disproved\`, \`none\` | How a mathematical claim was proved: checked in Lean 4, or proved in the published literature. |
| \`data_test\` | \`supports\`, \`refutes\`, \`mixed\`, \`inconclusive\`, \`none\` | Result of testing the claim against public data. \`none\` = not tested. |
| \`data_test_kind\` | \`biological\`, \`physical\`, \`computational\`, \`none\` | What the data measured. Only \`biological\` shows a claim holds in organisms; \`computational\` shows it holds as mathematics. |
| \`data_test_url\` | URL | Full record of the test (hypothesis, data, method, caveats). Empty if untested. |
| \`published\` | true / false | Whether the claim is published as a nanopublication. |
| \`nanopub_url\` | URL | The nanopublication, when published. |

## What is left out

Internal and model-generated fields: hash keys, AI assessor truth and testability scores, Lean
module details, MorphoLib links, registry and draft flags, and pre-registration contracts. They are
still in [\`docs/claims.json\`](../claims.json) and available over the \`delphisci\` MCP server.
`);

console.log(`export: ${rows.length} claims -> docs/export/ (${Object.entries(stat).map(([k, v]) => `${v} ${k}`).join(", ")})`);
