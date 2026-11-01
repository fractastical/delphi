// Three single-agent arms (Claude Sonnet 5.5, Claude Opus 5.5, GPT 5.6 Sol) and the swarm, on Book VI.
//   node compare-arms.mjs  ->  comparison-arms.json
// Claims are matched automatically and deterministically: same source paragraph, then greedy one-to-one
// on the sum of quote and claim word-set Jaccard similarity (threshold below). The matcher is checked
// against the hand matching in match.json (Sonnet arm vs swarm).
import { readFileSync, writeFileSync } from "node:fs";
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
const THRESH = +(process.env.THRESH ?? 0.45); // quoteJ + claimJ; run THRESH=0.35 node compare-arms.mjs for a sensitivity check

const lines = readFileSync(join(AR, "inputs/ha.txt"), "utf8").split("\n");
const start = lines.findIndex(l => l.trim() === "## Book VI");
const end = lines.findIndex((l, i) => i > start && /^## Book /.test(l));
const paras = []; for (let i = start + 1; i < end; i++) if (lines[i].trim() && !lines[i].startsWith("#")) paras.push(i + 1);
const partOf = ln => { for (let j = ln - 1; j > start; j--) { const m = lines[j].match(/^### Part (\d+)/); if (m) return +m[1]; } return 0; };
const group = p => p <= 9 ? "birds" : p <= 17 ? "fishes+marine" : "land";
const STOP = new Set("the a an of and to in is are it its that this by for with as at on be or from not but they their which has have had".split(" "));
const toks = s => new Set(ws(s).toLowerCase().replace(/[^a-z0-9' -]/g, " ").split(/\s+/).filter(w => w && !STOP.has(w)));
const jac = (a, b) => { let i = 0; for (const x of a) if (b.has(x)) i++; return i / (a.size + b.size - i || 1); };

// ---------- runs
const swarmClaims = J(join(AR, "claims.json")).claims.filter(c => c.work === "ha" && c.book === "VI").map(c => ({ ...c, line: c.lineStart }));
const swarmAssess = J(join(AR, "assessment/assessments.json")).assessments.filter(a => /^aristotle-ha06-/.test(a.claim_id));
const sBy = {}; for (const a of swarmAssess) (sBy[a.claim_id] ??= {})[a.assessor] = a;
const arm = (dir, name) => ({ name, claims: J(join(dir, "stage2-claims.json")).claims, assess: Object.fromEntries(J(join(dir, "stage4-validated.json")).assessments.map(a => [a.claim_id, a])),
  dropped: J(join(dir, "stage4-dropped.json")), raw: J(join(dir, "stage3-assessments.json")) });
const runs = {
  swarm: { name: "swarm", claims: swarmClaims },
  sonnet: arm(join(HERE, "single-agent"), "Claude Sonnet 5.5 (single)"),
  opus: arm(join(HERE, "arms/claude-opus-5-5"), "Claude Opus 5.5 (single)"),
  gpt: arm(join(HERE, "arms/gpt-5.6-sol"), "GPT 5.6 Sol (single)"),
};
// uniform per-claim score view: {overall, verdict}; the swarm has two assessors, kept separately
const view = (run, id) => run === runs.swarm
  ? { overall: mean(["gpt", "grok"].map(a => sBy[id][a].overall)), verdicts: ["gpt", "grok"].map(a => sBy[id][a].verdict), assessors: ["gpt", "grok"].map(a => sBy[id][a].overall) }
  : { overall: run.assess[id].overall, verdicts: [run.assess[id].verdict], assessors: [run.assess[id].overall] };

// ---------- matching
function matchRuns(A, B) {
  const cand = [];
  for (const a of A.claims) for (const b of B.claims) {
    if (a.line !== b.line && !(a.lineEnd && b.lineEnd && a.lineStart <= b.line && b.line <= a.lineEnd)) continue;
    const s = jac(toks(a.quote), toks(b.quote)) + jac(toks(a.claim), toks(b.claim));
    if (s >= THRESH) cand.push({ a: a.id, b: b.id, s });
  }
  cand.sort((x, y) => y.s - x.s);
  const ua = new Set(), ub = new Set(), out = [];
  for (const c of cand) if (!ua.has(c.a) && !ub.has(c.b)) { ua.add(c.a); ub.add(c.b); out.push(c); }
  return out;
}
// matcher validation against hand matching (swarm id vs sonnet id)
const hand = J(join(HERE, "match.json")).pairs.map(p => [`aristotle-ha06-${String(p.swarm).padStart(2, "0")}`, `aristotle-ha06-${String(p.single).padStart(2, "0")}`]);
const auto = matchRuns(runs.swarm, runs.sonnet);
const autoSet = new Set(auto.map(m => m.a + "|" + m.b)), handSet = new Set(hand.map(h => h.join("|")));
const matcherCheck = { hand: hand.length, auto: auto.length, both: [...handSet].filter(x => autoSet.has(x)).length,
  handOnly: [...handSet].filter(x => !autoSet.has(x)), autoOnly: [...autoSet].filter(x => !handSet.has(x)) };

// ---------- per-run extraction stats
function stats(run) {
  const cs = run.claims, g = {}; cs.forEach(c => { const k = group(partOf(c.line)); g[k] = (g[k] || 0) + 1; });
  const tri = {}; cs.forEach(c => tri[c.resolvability_triage] = (tri[c.resolvability_triage] || 0) + 1);
  return { claims: cs.length, verbatim: cs.filter(c => ws(lines[c.line - 1] ?? "").includes(ws(c.quote))).length,
    paragraphsWithClaim: new Set(cs.map(c => c.line)).size, byGroup: g, numeric: cs.filter(c => /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|hundred)\b/i.test(c.claim)).length, byTriage: tri };
}
const extraction = Object.fromEntries(Object.entries(runs).map(([k, r]) => [k, stats(r)]));
extraction.swarm = (() => { // claims.json lacks `line` for the extractor's own value; recompute from lineStart
  const cs = swarmClaims, g = {}; cs.forEach(c => { const k = group(partOf(c.line)); g[k] = (g[k] || 0) + 1; });
  const tri = {}; cs.forEach(c => tri[c.resolvability_triage] = (tri[c.resolvability_triage] || 0) + 1);
  return { claims: cs.length, verbatim: cs.filter(c => ws(lines[c.line - 1] ?? "").includes(ws(c.quote))).length, paragraphsWithClaim: new Set(cs.map(c => c.line)).size, byGroup: g,
    numeric: cs.filter(c => /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|sixty|hundred)\b/i.test(c.claim)).length, byTriage: tri };
})();

// ---------- pairwise comparison of runs
function pair(ka, kb) {
  const A = runs[ka], B = runs[kb], m = matchRuns(A, B);
  const va = m.map(x => view(A, x.a)), vb = m.map(x => view(B, x.b));
  const oa = va.map(v => v.overall), ob = vb.map(v => v.overall);
  let exact = 0, within1 = 0, n = 0;
  m.forEach((_, i) => { for (const x of va[i].verdicts) for (const y of vb[i].verdicts) { n++; if (x === y) exact++; if (Math.abs(ORD[x] - ORD[y]) <= 1) within1++; } });
  return { a: ka, b: kb, matched: m.length, ofA: A.claims.length, ofB: B.claims.length, jaccard: r3(m.length / (A.claims.length + B.claims.length - m.length)),
    r: r3(pearson(oa, ob)), mae: r3(mae(oa, ob)), bias: r3(mean(oa) - mean(ob)), verdictExact: r3(exact / n), verdictWithinOne: r3(within1 / n), matchedPairs: m.map(x => [x.a, x.b, r3(x.s)]) };
}
const keys = Object.keys(runs);
const pairs = []; for (let i = 0; i < keys.length; i++) for (let j = i + 1; j < keys.length; j++) pairs.push(pair(keys[i], keys[j]));

// ---------- score distributions per assessor/run
const dist = a => { const o = {}; a.forEach(x => o[x] = (o[x] || 0) + 1); return o; };
const spread = {
  swarm_gpt: sd0(swarmAssess.filter(a => a.assessor === "gpt")), swarm_grok: sd0(swarmAssess.filter(a => a.assessor === "grok")),
  sonnet: sd0(Object.values(runs.sonnet.assess)), opus: sd0(Object.values(runs.opus.assess)), gpt: sd0(Object.values(runs.gpt.assess)),
};
function sd0(rows) { return { n: rows.length, mean: r3(mean(rows.map(r => r.overall))), sd: r3(sd(rows.map(r => r.overall))), verdicts: dist(rows.map(r => r.verdict)), meanConfidence: r3(mean(rows.map(r => r.confidence))) }; }

// claims several runs agree on: reached by 2+ single arms and swarm
const dsRefs = Object.fromEntries(["sonnet", "opus", "gpt"].map(k => [k, { references: runs[k].raw.reduce((n, r) => n + r.candidate_datasets.length, 0), perClaim: r3(runs[k].raw.reduce((n, r) => n + r.candidate_datasets.length, 0) / runs[k].raw.length),
  claimsWithNone: runs[k].raw.filter(r => !r.candidate_datasets.length).length, dropped: runs[k].dropped.length, droppedStatus: dist(runs[k].dropped.map(d => d.status)) }]));

// which claims are reached by every single arm / by the swarm
const idsMatched = (ka, kb) => new Map(matchRuns(runs[ka], runs[kb]).map(x => [x.a, x.b]));
const sw2 = { sonnet: idsMatched("swarm", "sonnet"), opus: idsMatched("swarm", "opus"), gpt: idsMatched("swarm", "gpt") };
const coverageBySwarmClaim = runs.swarm.claims.map(c => ({ id: c.id, label: c.label, sonnet: sw2.sonnet.has(c.id), opus: sw2.opus.has(c.id), gpt: sw2.gpt.has(c.id) }));
const reachedBySwarmCount = { "all 3 single arms": 0, "2": 0, "1": 0, "none": 0 };
for (const c of coverageBySwarmClaim) { const n = +c.sonnet + +c.opus + +c.gpt; reachedBySwarmCount[n === 3 ? "all 3 single arms" : n === 0 ? "none" : String(n)]++; }
const swarmOnlyAll = coverageBySwarmClaim.filter(c => !c.sonnet && !c.opus && !c.gpt).map(c => c.label);

const out = { threshold: THRESH, matcherCheck, extraction, spread, datasetReferences: dsRefs, pairs: pairs.map(({ matchedPairs, ...p }) => p), reachedBySwarmCount, swarmClaimsNoSingleArmReached: swarmOnlyAll };
writeFileSync(join(HERE, "comparison-arms.json"), JSON.stringify({ ...out, pairDetail: pairs.map(p => ({ a: p.a, b: p.b, matchedPairs: p.matchedPairs })), coverageBySwarmClaim }, null, 2) + "\n");
console.log(JSON.stringify(out, null, 1));
