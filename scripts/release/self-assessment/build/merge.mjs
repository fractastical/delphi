// Validate raw/<assessor>.json against the rubric, compute weighted totals, and write
// assessments.json plus SUMMARY.md (per-criterion table, mean, spread, ranked fixes).
//
//   node scripts/release/self-assessment/build/merge.mjs
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const rubric = JSON.parse(readFileSync(join(HERE, "rubric.json"), "utf8"));
const assessors = Object.fromEntries(JSON.parse(readFileSync(join(HERE, "assessors.json"), "utf8")).map(a => [a.id, a]));
const pack = JSON.parse(readFileSync(join(HERE, "evidence/MANIFEST.json"), "utf8"));
const packSha = readFileSync(join(HERE, "evidence/PACK_SHA256"), "utf8").trim();
const RUBRIC = `${rubric.id}/${rubric.version}`;
const dims = rubric.dimensions;
const int10 = (v, what) => { if (!Number.isInteger(v) || v < 0 || v > 10) throw new Error(`${what}: ${v} is not an integer in 0..10`); return v; };

const out = [];
for (const f of readdirSync(join(HERE, "raw")).filter(f => f.endsWith(".json")).sort()) {
  const id = f.replace(/\.json$/, "");
  if (!assessors[id]) throw new Error(`raw/${f}: no such assessor in assessors.json`);
  const r = JSON.parse(readFileSync(join(HERE, "raw", f), "utf8"));
  if (r.assessor !== id) throw new Error(`raw/${f}: assessor field is ${r.assessor}`);
  if (r.rubric !== RUBRIC) throw new Error(`raw/${f}: rubric ${r.rubric} != ${RUBRIC}`);
  if (r.evidence_pack_sha256 !== packSha) throw new Error(`raw/${f}: pack sha ${r.evidence_pack_sha256} != ${packSha}`);
  if (r.commit !== pack.commit) throw new Error(`raw/${f}: commit ${r.commit} != ${pack.commit}`);
  for (const d of dims) { int10(r.scores[d.id], `${id} ${d.id}`); if (!r.justifications?.[d.id]) throw new Error(`${id}: no justification for ${d.id}`); }
  int10(r.bonus, `${id} bonus`);
  if (typeof r.confidence !== "number" || r.confidence < 0 || r.confidence > 1) throw new Error(`${id}: confidence`);
  const total = dims.reduce((s, d) => s + d.weight * r.scores[d.id] * 10, 0);
  const hvi = r.highest_value_improvement;
  if (hvi) {
    let gain = 0;
    for (const [k, v] of Object.entries(hvi.expected_score_deltas ?? {})) {
      const d = dims.find(x => x.id === k);
      if (!d) throw new Error(`${id}: highest_value_improvement names unknown criterion ${k}`);
      if (!Number.isInteger(v)) throw new Error(`${id}: delta for ${k} is not an integer`);
      if (r.scores[k] + v > 10 || r.scores[k] + v < 0) throw new Error(`${id}: ${k} ${r.scores[k]}${v >= 0 ? "+" : ""}${v} leaves 0..10`);
      gain += d.weight * v * 10;
    }
    hvi.computed_total_gain = Math.round(gain * 10) / 10;
    if (Math.abs(hvi.computed_total_gain - Number(hvi.expected_total_gain)) > 0.6) console.warn(`${id}: stated gain ${hvi.expected_total_gain} vs computed ${hvi.computed_total_gain}; using computed`);
  }
  out.push({ ...r, weighted_total: Math.round(total * 10) / 10, file: `raw/${f}` });
}
if (out.length < 2) throw new Error(`only ${out.length} assessor(s); need at least two providers`);
const providers = new Set(out.map(a => assessors[a.assessor].provider));
if (providers.size < 2) throw new Error("fewer than two providers");

const mean = xs => xs.reduce((a, b) => a + b, 0) / xs.length;
const fmt = x => (Math.round(x * 10) / 10).toString();
const stats = {};
for (const d of dims) { const xs = out.map(a => a.scores[d.id]); stats[d.id] = { mean: mean(xs), min: Math.min(...xs), max: Math.max(...xs) }; }
const bonusXs = out.map(a => a.bonus), totXs = out.map(a => a.weighted_total);
stats.bonus = { mean: mean(bonusXs), min: Math.min(...bonusXs), max: Math.max(...bonusXs) };
stats.weighted_total = { mean: mean(totXs), min: Math.min(...totXs), max: Math.max(...totXs) };

writeFileSync(join(HERE, "assessments.json"), JSON.stringify({
  rubric: RUBRIC, commit: pack.commit, evidence_pack_sha256: packSha, capturedAt: pack.capturedAt,
  mergedAt: new Date().toISOString(), stats, assessments: out,
}, null, 2) + "\n");

const head = ["Criterion", "Weight", ...out.map(a => assessors[a.assessor].modelLabel), "Mean", "Spread"];
const rows = dims.map(d => [d.label, `${d.weight * 100}%`, ...out.map(a => a.scores[d.id]), fmt(stats[d.id].mean), `${stats[d.id].min}–${stats[d.id].max}`]);
rows.push(["**Weighted total (0–100)**", "100%", ...out.map(a => `**${fmt(a.weighted_total)}**`), `**${fmt(stats.weighted_total.mean)}**`, `${fmt(stats.weighted_total.min)}–${fmt(stats.weighted_total.max)}`]);
rows.push(["Collaboration bonus (0–10, separate)", "+10", ...out.map(a => a.bonus), fmt(stats.bonus.mean), `${stats.bonus.min}–${stats.bonus.max}`]);
const table = [head, head.map(() => "---"), ...rows].map(r => `| ${r.join(" | ")} |`).join("\n");

let md = `# Self-assessment on the Science Claw judging rubric\n\n`;
md += `Rubric \`${RUBRIC}\` ([rubric.json](rubric.json), weights from [scienceclawhack.ai](https://scienceclawhack.ai/)). Snapshot: commit \`${pack.commit.slice(0, 8)}\`, evidence pack \`${packSha.slice(0, 12)}…\` captured ${pack.capturedAt} ([evidence/MANIFEST.json](evidence/MANIFEST.json)). `;
md += `${out.length} blind assessors from ${providers.size} providers (${[...providers].join(", ")}); the builder's provider (Anthropic) did not score. Scores are 0–10 per criterion; the pipeline computes the weighted total. Generated by \`build/merge.mjs\`.\n\n${table}\n\n`;
md += `Each criterion is scored 0–10 whatever its weight; the weight only matters in the total. The same scores as points of the 100 available (score × weight × 10):\n\n`;
const phead = ["Criterion", "Max points", ...out.map(a => assessors[a.assessor].modelLabel), "Mean"];
const prows = dims.map(d => [d.label, d.weight * 100, ...out.map(a => fmt(a.scores[d.id] * d.weight * 10)), fmt(stats[d.id].mean * d.weight * 10)]);
prows.push(["**Total**", 100, ...out.map(a => `**${fmt(a.weighted_total)}**`), `**${fmt(stats.weighted_total.mean)}**`]);
md += [phead, phead.map(() => "---"), ...prows].map(r => `| ${r.join(" | ")} |`).join("\n") + "\n\n";
md += `Assessor confidence in own scoring: ${out.map(a => `${assessors[a.assessor].modelLabel} ${a.confidence}`).join(", ")}.\n\n`;
if (out.some(a => a.highest_value_improvement)) {
  md += `## The one improvement each assessor would make first\n\n`;
  md += `Each assessor was asked for the single change with the largest expected gain in the weighted total per hour of effort, achievable before the deadline, with deltas on its own scores. Gains are recomputed from the deltas and the weights.\n\n`;
  md += `| Assessor | Improvement | Deltas (0–10 scale) | Gain on /100 | Bonus | Effort |\n|---|---|---|---:|---:|---|\n`;
  for (const a of out) {
    const h = a.highest_value_improvement; if (!h) continue;
    const deltas = Object.entries(h.expected_score_deltas ?? {}).map(([k, v]) => `${dims.find(d => d.id === k)?.label ?? k} ${v >= 0 ? "+" : ""}${v}`).join(", ");
    md += `| ${assessors[a.assessor].modelLabel} | **${h.title}** | ${deltas} | +${fmt(h.computed_total_gain)} → ${fmt(a.weighted_total + h.computed_total_gain)} | ${h.bonus_delta ? `+${h.bonus_delta}` : "0"} | ${h.effort} |\n`;
  }
  md += "\n";
  for (const a of out) {
    const h = a.highest_value_improvement; if (!h) continue;
    md += `**${assessors[a.assessor].modelLabel}: ${h.title}.** ${h.what}\n\n*Why this one:* ${h.why_this_one}\n\n*Proof it happened:* ${h.evidence_that_would_prove_it}\n\n`;
  }
}
const MANIFEST = join(HERE, "nanopubs/manifest.jsonl");
if (existsSync(MANIFEST)) {
  const pubs = readFileSync(MANIFEST, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l));
  const byId = {};
  for (const p of pubs) (byId[p.id] ??= {})[p.registry] = p.trustyUri;
  md += `## Nanopubs\n\n| Nanopub | Test registry | Production |\n|---|---|---|\n`;
  for (const [id, regs] of Object.entries(byId)) md += `| \`${id}\` | ${regs.test ? `[${regs.test.slice(-45, -35)}…](${regs.test})` : "—"} | ${regs.production ? `[${regs.production.slice(-45, -35)}…](${regs.production})` : "not promoted"} |\n`;
  md += `\nPublished by \`build/publish.mjs\`; full record in [nanopubs/manifest.jsonl](nanopubs/manifest.jsonl).\n\n`;
}
md += `## Did anyone find a multi-agent vs single-agent comparison?\n\n`;
for (const a of out) md += `- **${assessors[a.assessor].modelLabel}**: ${a.comparison_found?.found ? "yes" : "no"}${a.comparison_found?.where ? ` (${a.comparison_found.where})` : ""}. ${a.comparison_found?.note ?? ""}\n`;
md += `\n## Summaries\n\n`;
for (const a of out) md += `**${assessors[a.assessor].modelLabel}** (${fmt(a.weighted_total)} + ${a.bonus}): ${a.summary}\n\n`;
md += `## Top fixes, as ranked by each assessor\n\n`;
for (const a of out) { md += `**${assessors[a.assessor].modelLabel}**\n\n`; (a.top_three_fixes ?? []).forEach((x, i) => md += `${i + 1}. ${x}\n`); md += "\n"; }
md += `## Per-criterion justifications and gaps\n\n`;
for (const d of [...dims, { id: "collaboration-bonus", label: rubric.bonus.label }]) {
  md += `### ${d.label}\n\n`;
  for (const a of out) {
    const score = d.id === "collaboration-bonus" ? a.bonus : a.scores[d.id];
    md += `**${assessors[a.assessor].modelLabel}: ${score}.** ${a.justifications[d.id] ?? ""}\n\n`;
    const gaps = a.gaps?.[d.id] ?? [];
    if (gaps.length) md += gaps.map(g => `- ${g}`).join("\n") + "\n\n";
  }
}
md += `## Missing evidence reported\n\n`;
for (const a of out) md += `- **${assessors[a.assessor].modelLabel}**: ${(a.missing_evidence ?? []).join("; ") || "none"}\n`;
writeFileSync(join(HERE, "SUMMARY.md"), md);
console.log(`merged ${out.length} assessors; weighted total mean ${fmt(stats.weighted_total.mean)} (${fmt(stats.weighted_total.min)}–${fmt(stats.weighted_total.max)}), bonus mean ${fmt(stats.bonus.mean)}`);
