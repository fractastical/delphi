// Build docs/claim-graph.html: every claim in the repo as a clickable graph, grouped by thinker or
// by decade, coloured by proof status, with assessor numbers on the edges and links to the live
// nanopubs.
//
//   node scripts/site/build-claim-graph.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import { withChrome } from "./chrome.mjs";
import { ROOT, VERIFICATION, EVIDENCE, DATA_KINDS, loadClaims } from "./load-claims.mjs";

const HERE = join(ROOT, "docs");
const TEMPLATES = join(ROOT, "scripts/site/templates");
const claims = loadClaims();

// Truth scores from test-data/truth/raw/<assessor>/*.json, matched by content key.
const TRUTH = join(ROOT, "test-data/truth/raw");
const LABEL = { gpt: "GPT-5.6 Sol", grok: "Grok 4.7", gemini: "Gemini 4 Argon" };
const truth = {};
for (const who of existsSync(TRUTH) ? readdirSync(TRUTH) : []) {
  for (const f of readdirSync(join(TRUTH, who)).filter(f => f.endsWith(".json"))) {
    let rows; try { rows = JSON.parse(readFileSync(join(TRUTH, who, f), "utf8")); } catch { console.warn(`skipping unparsable ${who}/${f}`); continue; }
    for (const r of rows) if (typeof r.p_true === "number") (truth[r.key] ??= []).push({ who: LABEL[who] ?? who, p: r.p_true, rationale: r.rationale });
  }
}
for (const c of claims) {
  c.truthBy = truth[c.key] ?? [];
  c.truth = c.truthBy.length ? Math.round(1000 * c.truthBy.reduce((s, x) => s + x.p, 0) / c.truthBy.length) / 1000 : null;
}
// Snapshot of the MorphoEval simulation that tests or models the claim (scripts/site/morpholib-thumbs.py).
const THUMBS = existsSync(join(HERE, "thumbs/index.json")) ? JSON.parse(readFileSync(join(HERE, "thumbs/index.json"), "utf8")).thumbs : {};
for (const c of claims) {
  const m = [...c.morpholib].sort((a, b) => (a.relation === "tests" ? 0 : 1) - (b.relation === "tests" ? 0 : 1)).find(m => THUMBS[m.id]);
  c.thumb = m ? { src: THUMBS[m.id].file, morpholib: m.id, relation: m.relation, media: THUMBS[m.id].media, source: THUMBS[m.id].source, frame: THUMBS[m.id].frame + 1, frames: THUMBS[m.id].frames } : null;
}
const built = new Date().toISOString().slice(0, 16).replace("T", " ");
const count = f => claims.filter(f).length;
const DATA = { claims, built };
// docs/theorems.html lists exactly the claims with `theorem` set (see load-claims.mjs), from any
// project: a math claim that has reached proof, not a claim from claim-sources/math-bio-claims/.
const THEOREMS = { claims: claims.filter(c => c.theorem), total: claims.length, math: count(c => c.math), built };
const seal = readFileSync(join(ROOT, "assets/logo.svg"), "utf8").trim();
const inline = svg => svg.replace(/<svg[^>]*>/, t => t.replace(/\s(width|height)="\d+"/g, "")).replace("<svg ", '<svg role="img" aria-label="DELPHI seal" ');
for (const [page, data] of [["claim-graph", DATA], ["claims-query", DATA], ["theorems", THEOREMS]]) {
  const html = withChrome(readFileSync(join(TEMPLATES, `${page}.template.html`), "utf8"), page)
    .replace("<!--__SEAL__-->", inline(seal))
    .replace("<!--__SEAL_MONO__-->", inline(seal.replace(/#14213d/gi, "#000").replace(/#e5c07b/gi, "#fff")))
    .replace("/*__SEAL_URI__*/", encodeURIComponent(seal))
    .replace("/*__DATA__*/null", JSON.stringify(data).replace(/</g, "\\u003c"));
  writeFileSync(join(HERE, `${page}.html`), html);
  console.log(`docs/${page}.html: ${(html.length / 1024).toFixed(0)} KB`);
}

// Flat export for scripts: one row per claim with its scores.
const rows = claims.map(c => ({ id: c.id, key: c.key, label: c.label, statement: c.text, quote: c.quote || null, thinker: c.thinker, year: c.year,
  work: c.work, chapter: c.section || null, kind: c.kind, status: c.status, proof: c.proof ?? null, verification: c.verification,
  math: c.math, theorem: c.theorem, notation: c.notation || null, lean_theorems: c.lean?.theorems ?? null,
  formalization: c.formalization,
  evidence: c.evidence, evidence_kind: c.evidenceKind, data_test: c.dataTest ? { verdict: c.dataTest.verdict, confidence: c.dataTest.confidence, preregistered: c.dataTest.preregistered, data_kind: c.dataTest.dataKind, path: c.dataTest.path, test_contract: c.dataTest.testContract, revisions: c.dataTest.revisions, faithfulness: c.dataTest.faithfulness } : null,
  morpholib: c.morpholib.map(m => ({ id: m.id, relation: m.relation, note: m.note, label: m.label, organism: m.organism, verdict: m.verdict,
    score: m.score, thompson_verdict: m.thompsonVerdict, nanopub: m.nanopub, registry: m.registry, report: m.report })),
  thumbnail: c.thumb ? { file: `docs/${c.thumb.src}`, morpholib: c.thumb.morpholib, source: c.thumb.source } : null,
  testability: c.resolvability ?? null, truth: c.truth,
  truth_by: c.truthBy.map(x => ({ assessor: x.who, p_true: x.p })), assessor_confidence: c.confidence ?? null,
  nanopub: c.uri || null, registry: c.registry || null, draft: !!c.draft }));
writeFileSync(join(HERE, "claims.json"), JSON.stringify({ built: DATA.built, claims: rows }, null, 1) + "\n");
console.log(`${claims.length} claims (${count(c => c.registry === "production")} in production, ${count(c => c.registry === "test")} test only, ${count(c => !c.registry)} unpublished, ${count(c => c.draft)} drafts); docs/claims.json written`);
console.log(`verification: ${VERIFICATION.map(v => `${count(c => c.verification === v)} ${v}`).join(", ")}`);
console.log(`tested against data: ${count(c => c.evidence)} (${EVIDENCE.map(v => `${count(c => c.evidence === v)} ${v}`).join(", ")}); ${count(c => c.verification === "untested" && !c.evidence)} neither proved nor tested`);
console.log(`data kind of tests: ${DATA_KINDS.map(k => `${count(c => c.evidenceKind === k)} ${k}`).join(", ")}; math claims supported by biological data: ${count(c => c.math && c.evidenceKind === "biological" && c.evidence === "supports")} of ${count(c => c.math)}`);
console.log(`morpholib: ${count(c => c.morpholib.length)} claims linked to MorphoEval audits (${count(c => c.morpholib.some(m => m.relation === "tests"))} tested by one)`);
console.log(`${count(c => c.math)} math claims; ${count(c => c.theorem)} theorems (math and proved): ${count(c => c.theorem && c.proof === "lean")} machine-checked in Lean 4, ${count(c => c.theorem && c.proof === "literature")} proved in the literature`);

// Plain-text counts for readers without MCP: test-data/claim-tests/SUMMARY.md, and the block
// between the numbers markers in README.md. Both come from the same claims as docs/claims.json.
const TESTS = join(ROOT, "test-data/claim-tests");
const runs = [];
const walk = d => { for (const f of readdirSync(d, { withFileTypes: true })) {
  if (f.isDirectory()) walk(join(d, f.name));
  else if (f.name === "result.json") { try { runs.push(JSON.parse(readFileSync(join(d, f.name), "utf8"))); } catch {} }
} };
if (existsSync(TESTS)) walk(TESTS);
const pending = runs.filter(r => r.status === "preregistered");
const tested = claims.filter(c => c.evidence);
// A9 faithfulness gate (test-data/claim-tests/FAITHFULNESS.md): which tests an independent provider has checked
// for measuring what the claim asserts, and with what outcome.
const FAITH = ["faithful", "faithful-with-narrower-scope", "not-representative"];
const faithed = tested.filter(c => c.dataTest.faithfulness);
console.log(`faithfulness: ${faithed.length} of ${tested.length} tests checked (${FAITH.map(v => `${faithed.filter(c => c.dataTest.faithfulness.status === "agreed" && c.dataTest.faithfulness.verdict === v).length} ${v}`).join(", ")}, ${faithed.filter(c => c.dataTest.faithfulness.status === "contested").length} contested)`);
const byThinker = [...new Set(tested.map(c => c.thinker))];
const n = (cs, f) => cs.filter(f).length;
const cell = k => k || "·";
const gh = p => p.replace(/^test-data\/claim-tests\//, "");
const summary = [
  "# Claim tests: summary",
  "",
  `Generated by \`node scripts/site/build-claim-graph.mjs\` on ${built} UTC. Do not edit by hand.`,
  "",
  `**${tested.length} claims tested against data** (${EVIDENCE.map(v => `${n(tested, c => c.evidence === v)} ${v}`).join(", ")}), from ${runs.filter(r => r.status === "complete").length} completed test runs. ` +
    `${pending.length} more tests are pre-registered and awaiting data. ${n(tested, c => c.evidenceKind === "biological")} of the tested claims were tested on data measured on organisms; the rest on simulation, mathematics or physical data.`,
  "",
  "A claim with several runs counts once, using its top-level `result.json`. A data verdict is evidence, not proof: it never makes a claim a theorem.",
  "",
  `| Thinker | Tested | ${EVIDENCE.join(" | ")} | ${DATA_KINDS.join(" | ")} |`,
  `|---|---:|${"---:|".repeat(EVIDENCE.length + DATA_KINDS.length)}`,
  ...byThinker.map(t => { const cs = tested.filter(c => c.thinker === t);
    return `| ${t} | ${cs.length} | ${EVIDENCE.map(v => cell(n(cs, c => c.evidence === v))).join(" | ")} | ${DATA_KINDS.map(k => cell(n(cs, c => c.evidenceKind === k))).join(" | ")} |`; }),
  `| **All** | **${tested.length}** | ${EVIDENCE.map(v => n(tested, c => c.evidence === v)).join(" | ")} | ${DATA_KINDS.map(k => n(tested, c => c.evidenceKind === k)).join(" | ")} |`,
  "",
  "Same numbers by query: `node mcp/cli.mjs overview`, the `delphi_overview` MCP tool, or",
  "`jq '[.claims[] | select(.evidence)] | group_by(.evidence) | map({(.[0].evidence): length}) | add' docs/claims.json`.",
  "",
  `## Faithfulness gate (${faithed.length} of ${tested.length} tests checked)`,
  "",
  "Does the analysis measure what the claim asserts? Judged by an assessor from a provider other than the builder's, reading only the claim and the test directory ([FAITHFULNESS.md](FAITHFULNESS.md)). " +
    "A `not-representative` verdict means the number is about something else and the evidence does not count, whatever it said; every such verdict gets a blind second opinion, and the test is `contested` when the assessors disagree. The data verdict column is left as the test reported it.",
  "",
  `| Outcome | Tests |`,
  `|---|---:|`,
  ...FAITH.map(v => `| ${v} (agreed) | ${n(faithed, c => c.dataTest.faithfulness.status === "agreed" && c.dataTest.faithfulness.verdict === v)} |`),
  `| contested | ${n(faithed, c => c.dataTest.faithfulness.status === "contested")} |`,
  `| not yet checked | ${tested.length - faithed.length} |`,
  "",
  ...(faithed.some(c => c.dataTest.faithfulness.verdict === "not-representative" || c.dataTest.faithfulness.status === "contested") ? [
    "| Claim | Data verdict | Faithfulness | Assessors |",
    "|---|---|---|---|",
    ...faithed.filter(c => c.dataTest.faithfulness.verdict === "not-representative" || c.dataTest.faithfulness.status === "contested").sort((a, b) => a.id.localeCompare(b.id)).map(c =>
      `| [\`${c.id}\`](${gh(c.dataTest.path).replace(/result\.json$/, "")}) | ${c.evidence} | ${c.dataTest.faithfulness.status === "agreed" ? `**${c.dataTest.faithfulness.verdict}**` : "contested"} | ${c.dataTest.faithfulness.assessors.map(a => `${a.assessor}: ${a.verdict}`).join("; ")} |`),
    ""] : []),
  "## Every tested claim",
  "",
  "| Claim | Verdict | Confidence | Data | Faithfulness | Statement |",
  "|---|---|---:|---|---|---|",
  ...tested.sort((a, b) => a.id.localeCompare(b.id)).map(c =>
    `| [\`${c.id}\`](${gh(c.dataTest.path)}) | ${c.evidence} | ${c.dataTest.confidence ?? "·"} | ${c.evidenceKind ?? "·"} | ${c.dataTest.faithfulness ? (c.dataTest.faithfulness.status === "agreed" ? c.dataTest.faithfulness.verdict : "contested") : "·"} | ${c.label.replace(/\|/g, "\\|")} |`),
  "",
  `## Pre-registered, awaiting data (${pending.length})`,
  "",
  ...pending.map(r => `- \`${r.claim_id}\` (${r.project})`),
  "",
].join("\n");
writeFileSync(join(TESTS, "SUMMARY.md"), summary);

const README = join(ROOT, "README.md");
const START = "<!-- numbers:start -->", END = "<!-- numbers:end -->";
const readme = readFileSync(README, "utf8");
if (readme.includes(START) && readme.includes(END)) {
  const block = [START,
    `As of ${built} UTC (generated by \`node scripts/site/build-claim-graph.mjs\`):`,
    "",
    "| | count |",
    "|---|---:|",
    `| claims | ${claims.length} |`,
    `| live as nanopubs (production; the Darwin, Thompson, Wolfram and math-bio claims, signed and published on the hackathon's first night, Oct 30–31) | ${count(c => c.registry === "production")} |`,
    `| theorems (math claims with a proof) | ${count(c => c.theorem)} (${count(c => c.theorem && c.proof === "lean")} Lean-checked, ${count(c => c.theorem && c.proof === "literature")} literature) |`,
    `| claims tested against data | ${tested.length} (${EVIDENCE.map(v => `${n(tested, c => c.evidence === v)} ${v}`).join(", ")}) |`,
    `| of those, tested on organisms | ${n(tested, c => c.evidenceKind === "biological")} |`,
    `| tests pre-registered, awaiting data | ${pending.length} |`,
    `| tests through the faithfulness gate | ${faithed.length} of ${tested.length} (${n(faithed, c => c.dataTest.faithfulness.status === "agreed" && c.dataTest.faithfulness.verdict === "not-representative")} not representative, ${n(faithed, c => c.dataTest.faithfulness.status === "contested")} contested) |`,
    `| claims neither proved nor tested | ${count(c => c.verification === "untested" && !c.evidence)} |`,
    "",
    "Every tested claim with its verdict: [`test-data/claim-tests/SUMMARY.md`](test-data/claim-tests/SUMMARY.md). Per-claim fields: [`docs/claims.json`](docs/claims.json) (`evidence`, `data_test`, `theorem`). Over MCP: `delphi_claim_tests` (summary, one claim's full result, and untested claims ranked by testability).",
    END].join("\n");
  writeFileSync(README, readme.replace(new RegExp(`${START}[\\s\\S]*?${END}`), block));
  console.log("README.md numbers block updated");
}
console.log(`test-data/claim-tests/SUMMARY.md: ${tested.length} tested claims, ${pending.length} pre-registered`);
