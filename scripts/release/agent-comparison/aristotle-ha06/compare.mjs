// Stage 5: compare the single-agent chain with the swarm on History of Animals Book VI.
//   node compare.mjs  ->  comparison.json (and a summary on stdout)
// Claims are matched by content (match.json), not by id: the two runs reuse the ids aristotle-ha06-NN
// for different claims.
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const AR = join(HERE, "../../../../claim-sources/aristotle-biology");
const J = p => JSON.parse(readFileSync(p, "utf8"));
const ws = s => s.replace(/\s+/g, " ").trim();
const mean = a => a.reduce((s, x) => s + x, 0) / a.length;
const sd = a => Math.sqrt(mean(a.map(x => (x - mean(a)) ** 2)));
const r3 = x => Math.round(x * 1000) / 1000;
const pearson = (x, y) => { const mx = mean(x), my = mean(y); let n = 0, dx = 0, dy = 0; x.forEach((v, i) => { n += (v - mx) * (y[i] - my); dx += (v - mx) ** 2; dy += (y[i] - my) ** 2; }); return n / Math.sqrt(dx * dy); };
const mae = (x, y) => mean(x.map((v, i) => Math.abs(v - y[i])));
const ORD = { "resolvable-now": 3, "partially-resolvable": 2, "needs-new-data": 1, "not-empirically-resolvable": 0 };

const lines = readFileSync(join(AR, "inputs/ha.txt"), "utf8").split("\n");
const start = lines.findIndex(l => l.trim() === "## Book VI");
const end = lines.findIndex((l, i) => i > start && /^## Book /.test(l));
const bookParas = []; for (let i = start + 1; i < end; i++) if (lines[i].trim() && !lines[i].startsWith("#")) bookParas.push(i + 1);
const partOf = ln => { for (let j = ln - 1; j > start; j--) { const m = lines[j].match(/^### Part (\d+)/); if (m) return +m[1]; } return 0; };
const group = p => p <= 9 ? "birds (Parts 1-9)" : p <= 17 ? "fishes and marine mammals (Parts 10-17)" : "land viviparous animals (Parts 18-37)";

// ---------- load both runs
const swarm = J(join(AR, "claims.json")).claims.filter(c => c.work === "ha" && c.book === "VI");
const single = J(join(HERE, "single-agent/stage2-claims.json")).claims;
const sAssess = J(join(AR, "assessment/assessments.json")).assessments.filter(a => /^aristotle-ha06-/.test(a.claim_id));
const mine = J(join(HERE, "single-agent/stage4-validated.json")).assessments;
const myRaw = J(join(HERE, "single-agent/stage3-assessments.json"));
const match = J(join(HERE, "match.json")).pairs;
const byId = a => Object.fromEntries(a.map(x => [x.id ?? x.claim_id, x]));
const swarmC = byId(swarm), singleC = byId(single);
const id = (n) => `aristotle-ha06-${String(n).padStart(2, "0")}`;

// ---------- extraction
function extractionStats(cs, name) {
  const verbatim = cs.filter(c => ws(lines[c.line - 1] ?? "").includes(ws(c.quote))).length;
  const paras = new Set(cs.map(c => c.line));
  const g = {}; cs.forEach(c => { const k = group(partOf(c.line)); g[k] = (g[k] || 0) + 1; });
  const kind = {}; cs.forEach(c => kind[c.claim_kind] = (kind[c.claim_kind] || 0) + 1);
  const tri = {}; cs.forEach(c => tri[c.resolvability_triage] = (tri[c.resolvability_triage] || 0) + 1);
  const quoted = new Set(); cs.forEach(c => quoted.add(c.line));
  const words = cs.map(c => ws(c.claim).split(" ").length);
  return { run: name, claims: cs.length, quotesVerbatimOnStatedLine: verbatim, distinctParagraphs: paras.size,
    paragraphsInBook: bookParas.length, paragraphCoverage: r3(paras.size / bookParas.length),
    byGroup: g, byKind: kind, byTriage: tri, meanClaimWords: r3(mean(words)),
    withNumericContent: cs.filter(c => /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|hundred)\b/i.test(c.claim)).length };
}
const swarmExtraction = J(join(AR, "extraction/D-ha-06.json")); // has the extractor's own `line`; claims.json keeps lineStart/lineEnd
if (!swarm.every((c, i) => c.label === swarmExtraction[i].label)) throw new Error("claims.json and D-ha-06.json disagree");
const extraction = { swarm: extractionStats(swarmExtraction, "swarm (1 extractor agent for Book VI)"), single: extractionStats(single, "single agent chain") };
const matchedSwarm = new Set(match.map(p => p.swarm)), matchedSingle = new Set(match.map(p => p.single));
const strict = match.filter(p => p.match === "same").length;
const overlap = {
  pairs: match.length, same: strict, partial: match.length - strict,
  swarmOnly: swarm.filter((_, i) => !matchedSwarm.has(i + 1)).map(c => `${c.id}: ${c.label}`),
  singleOnly: single.filter((_, i) => !matchedSingle.has(i + 1)).map(c => `${c.id}: ${c.label}`),
  jaccardAny: r3(match.length / (swarm.length + single.length - match.length)),
  jaccardSame: r3(strict / (swarm.length + single.length - strict)),
};

// ---------- assessment
const swarmBy = {}; for (const a of sAssess) (swarmBy[a.claim_id] ??= {})[a.assessor] = a;
const mineBy = byId(mine);
const assessors = ["gpt", "grok"]; // the swarm's merged assessments.json holds only these two: Gemini finished batch 1 only
const rows = match.map(p => {
  const sw = swarmBy[id(p.swarm)], me = mineBy[id(p.single)];
  return { swarm: id(p.swarm), single: id(p.single), match: p.match, swarmLabel: swarmC[id(p.swarm)].label, singleLabel: singleC[id(p.single)].label,
    mine: me.overall, mineVerdict: me.verdict, gpt: sw.gpt.overall, grok: sw.grok.overall,
    swarmMean: r3(mean(assessors.map(a => sw[a].overall))), gptV: sw.gpt.verdict, grokV: sw.grok.verdict };
});
const col = k => rows.map(r => r[k]);
function sectionStats(rs, label) {
  const m = rs.map(r => r.mine), s = rs.map(r => r.swarmMean);
  const per = Object.fromEntries(assessors.map(a => [a, { r: r3(pearson(m, rs.map(r => r[a]))), mae: r3(mae(m, rs.map(r => r[a]))),
    verdictExact: r3(rs.filter(r => ORD[r.mineVerdict] === ORD[r[a + "V"]]).length / rs.length) }]));
  // baseline on the same claims: each swarm assessor against the mean of the other two
  const base = Object.fromEntries(assessors.map(a => { const others = assessors.filter(o => o !== a);
    const o = rs.map(r => mean(others.map(x => r[x])));
    return [a, { r: r3(pearson(rs.map(r => r[a]), o)), mae: r3(mae(rs.map(r => r[a]), o)) }]; }));
  const meanOther = rs.map(r => mean(assessors.map(a => r[a])));
  return { label, n: rs.length, mineVsSwarmMean: { r: r3(pearson(m, s)), mae: r3(mae(m, s)), bias: r3(mean(m) - mean(s)) },
    mineVsEachAssessor: per, swarmAssessorVsOtherTwo: base,
    meanOverall: { mine: r3(mean(rs.map(r => r.mine))), gpt: r3(mean(rs.map(r => r.gpt))), grok: r3(mean(rs.map(r => r.grok))) },
    verdictMineEqualsBothAssessors: r3(rs.filter(r => assessors.every(a => r.mineVerdict === r[a + "V"])).length / rs.length),
    verdictAssessorsEqualEachOther: r3(rs.filter(r => r.gptV === r.grokV).length / rs.length),
    verdictMineWithinOneOfEachAssessor: r3(mean(rs.flatMap(r => assessors.map(a => Math.abs(ORD[r.mineVerdict] - ORD[r[a + "V"]]) <= 1 ? 1 : 0)))) };
}
const assessment = { matched: sectionStats(rows, "all matched pairs"), sameOnly: sectionStats(rows.filter(r => r.match === "same"), "same-proposition pairs only") };

// whole-run distributions
const dist = (a, f) => { const o = {}; a.forEach(x => o[f(x)] = (o[f(x)] || 0) + 1); return o; };
const swarmAll = Object.fromEntries(assessors.map(a => [a, sAssess.filter(x => x.assessor === a)]));
const spread = {
  mine: { n: mine.length, mean: r3(mean(mine.map(x => x.overall))), sd: r3(sd(mine.map(x => x.overall))), verdicts: dist(mine, x => x.verdict), meanConfidence: r3(mean(mine.map(x => x.confidence))) },
  ...Object.fromEntries(assessors.map(a => [a, { n: swarmAll[a].length, mean: r3(mean(swarmAll[a].map(x => x.overall))), sd: r3(sd(swarmAll[a].map(x => x.overall))),
    verdicts: dist(swarmAll[a], x => x.verdict), meanConfidence: r3(mean(swarmAll[a].map(x => x.confidence))) }])),
};
// inter-assessor agreement within the swarm on all 42 claims
const sw42 = Object.keys(swarmBy).sort();
const pairAgree = [["gpt", "grok"]].map(([a, b]) => ({ pair: `${a}-${b}`,
  r: r3(pearson(sw42.map(i => swarmBy[i][a].overall), sw42.map(i => swarmBy[i][b].overall))),
  mae: r3(mae(sw42.map(i => swarmBy[i][a].overall), sw42.map(i => swarmBy[i][b].overall))),
  verdictExact: r3(sw42.filter(i => swarmBy[i][a].verdict === swarmBy[i][b].verdict).length / sw42.length) }));

// dataset references and URL resolution
const swarmDropped = existsSync(join(AR, "assessment/dropped-datasets.json")) ? J(join(AR, "assessment/dropped-datasets.json")) : [];
const swarmDroppedHa06 = swarmDropped.filter(d => /^aristotle-ha06-/.test(d.claim_id));
const myDropped = J(join(HERE, "single-agent/stage4-dropped.json"));
const refs = {
  single: { references: myRaw.reduce((n, r) => n + r.candidate_datasets.length, 0), dropped: myDropped.length,
    droppedByHost: dist(myDropped, d => new URL(d.url).host), droppedStatus: dist(myDropped, d => d.status) },
  swarm: Object.fromEntries(assessors.map(a => [a, { references: swarmAll[a].length ? null : 0, dropped: swarmDroppedHa06.filter(d => d.assessor === a).length,
    droppedByHost: dist(swarmDroppedHa06.filter(d => d.assessor === a), d => new URL(d.url).host),
    droppedByStatus: dist(swarmDroppedHa06.filter(d => d.assessor === a), d => d.status.replace(/^error-.*/, "network-timeout/error")) }])),
};
const emptyDatasets = { single: myRaw.filter(r => r.candidate_datasets.length === 0).length, swarmRawRefs: null };
const swarmRawRefs = {};
for (const a of assessors) {
  let n = 0, empty = 0, tot = 0;
  for (let b = 1; b <= 8; b++) { const p = join(AR, `assessment/raw/${a}/batch-${b}.json`); if (!existsSync(p)) continue;
    for (const r of J(p)) if (/^aristotle-ha06-/.test(r.claim_id)) { tot++; n += r.candidate_datasets.length; if (!r.candidate_datasets.length) empty++; } }
  swarmRawRefs[a] = { claims: tot, references: n, claimsWithNoDataset: empty };
  refs.swarm[a].references = n;
}
emptyDatasets.swarmRawRefs = swarmRawRefs;

const out = { extraction, overlap, assessment, spread, interAssessorAgreementSwarm: pairAgree, datasetReferences: refs, emptyDatasets, pairs: rows };
writeFileSync(join(HERE, "comparison.json"), JSON.stringify(out, null, 2) + "\n");
console.log(JSON.stringify({ extraction, overlap: { ...overlap, swarmOnly: overlap.swarmOnly.length, singleOnly: overlap.singleOnly.length }, assessment, spread, interAssessorAgreementSwarm: pairAgree, datasetReferences: refs, emptyDatasets }, null, 1));
