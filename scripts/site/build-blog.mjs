#!/usr/bin/env node
// Builds docs/blog.html, the written summary of the project, from scripts/site/templates/blog.template.html.
// Every number in the article is computed here from repo files: docs/claims.json (built by
// build-claim-graph.mjs), test-data/claim-tests/**/result.json, test-data/organisms/merged/taxa.json,
// docs/problems.json, test-data/agent-comparison/four-arm.json, mcp/usage/*.json and the Lean law
// registry via lib/lean-source.mjs. Edit the template, not the output.
//
//   node scripts/site/build-blog.mjs
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { withChrome } from './chrome.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const R = (...p) => path.join(ROOT, ...p);
const TEMPLATE = R('scripts', 'site', 'templates', 'blog.template.html');
// Posts live in docs/blog/, one HTML file each, listed from docs/blog/index.html.
const OUT = R('docs', 'blog', 'science-claw-2026.html');
const OUT_MD = R('docs', 'blog', 'science-claw-2026.md');

const { listLaws } = await import(R('lib', 'lean-source.mjs'));

const claimsDoc = JSON.parse(fs.readFileSync(R('docs', 'claims.json'), 'utf8'));
const claims = claimsDoc.claims;
const taxa = JSON.parse(fs.readFileSync(R('test-data', 'organisms', 'merged', 'taxa.json'), 'utf8'));
const problems = JSON.parse(fs.readFileSync(R('docs', 'problems.json'), 'utf8'));
const laws = listLaws().laws;

const n = (f) => claims.filter(f).length;
const verdict = (c) => (c.evidence && typeof c.evidence === 'object' ? c.evidence.verdict : c.evidence) || null;
const tested = claims.filter((c) => verdict(c));
const faith = (c) => c.data_test && c.data_test.faithfulness;
const faithed = tested.filter(faith);

// Pre-registered tests awaiting data: result.json files with status "preregistered".
const runs = [];
const walk = (d) => {
  for (const f of fs.readdirSync(d, { withFileTypes: true })) {
    if (f.isDirectory()) walk(path.join(d, f.name));
    else if (f.name === 'result.json') { try { runs.push(JSON.parse(fs.readFileSync(path.join(d, f.name), 'utf8'))); } catch {} }
  }
};
walk(R('test-data', 'claim-tests'));

const byThinker = new Map();
for (const c of claims) byThinker.set(c.thinker, (byThinker.get(c.thinker) || 0) + 1);
const thinkerCount = (t) => byThinker.get(t) ?? (() => { throw new Error(`no claims by ${t}`); })();

const counts = {
  CLAIMS: claims.length,
  THINKERS: byThinker.size,
  WORKS: new Set(claims.map((c) => c.work)).size,
  MATH: n((c) => c.math),
  THEOREMS: n((c) => c.theorem),
  LEAN: n((c) => c.theorem && c.proof === 'lean'),
  LIT: n((c) => c.theorem && c.proof === 'literature'),
  TESTED: tested.length,
  SUPPORTS: n((c) => verdict(c) === 'supports'),
  REFUTES: n((c) => verdict(c) === 'refutes'),
  MIXED: n((c) => verdict(c) === 'mixed'),
  INCONCLUSIVE: n((c) => verdict(c) === 'inconclusive'),
  BIO: tested.filter((c) => c.evidence_kind === 'biological').length,
  COMPUTATIONAL: tested.filter((c) => c.evidence_kind === 'computational').length,
  PENDING: runs.filter((r) => r.status === 'preregistered').length,
  FAITH_N: faithed.length,
  FAITH_NOTREP: faithed.filter((c) => faith(c).status === 'agreed' && faith(c).verdict === 'not-representative').length,
  FAITH_CONTESTED: faithed.filter((c) => faith(c).status === 'contested').length,
  LIVE: n((c) => c.registry === 'production' && !c.draft),
  TEST_REGISTRY: n((c) => c.registry === 'test'),
  UNTESTED: n((c) => c.verification === 'untested' && !verdict(c)),
  DARWIN: thinkerCount('Charles Darwin'),
  THOMPSON: thinkerCount("D'Arcy Wentworth Thompson"),
  WOLFRAM: thinkerCount('Stephen Wolfram'),
  LEVIN: thinkerCount('Michael Levin'),
  ARISTOTLE: thinkerCount('Aristotle'),
  TAXA: taxa.length,
  TAXA_DATA: taxa.filter((t) => Array.isArray(t.datasets) && t.datasets.length).length,
  DATASET_RECORDS: taxa.reduce((s, t) => s + (Array.isArray(t.datasets) ? t.datasets.length : 0), 0),
  MENTIONS: taxa.reduce((s, t) => s + (t.mention_count || 0), 0),
  PROBLEMS: problems.problems.length,
  LEAN_THOMPSON: n((c) => c.theorem && c.proof === 'lean' && c.thinker === "D'Arcy Wentworth Thompson"),
  LEAN_DARWIN: n((c) => c.theorem && c.proof === 'lean' && c.thinker === 'Charles Darwin'),
  LEAN_HYGRO: n((c) => c.theorem && c.proof === 'lean' && !['Charles Darwin', "D'Arcy Wentworth Thompson"].includes(c.thinker)),
  REG_LAWS: laws.length,
  REG_ACCEPTED: laws.filter((l) => l.status === 'accepted').length,
};
if (counts.TESTED !== counts.SUPPORTS + counts.REFUTES + counts.MIXED + counts.INCONCLUSIVE) throw new Error('unknown evidence verdict in docs/claims.json');
// Result-bar widths for the record panel, as percentages of tested claims.
const barVars = Object.fromEntries(['SUPPORTS', 'REFUTES', 'MIXED', 'INCONCLUSIVE'].map((k) => [`BAR_${k}`, (counts[k] / counts.TESTED * 100).toFixed(2)]));
if (counts.THEOREMS !== counts.LEAN + counts.LIT) throw new Error('unknown proof kind in docs/claims.json');

// The worked example: thompson1917-ch07-04 (120-degree cell packing), from its result files.
const ch0704Dir = R('test-data', 'claim-tests', 'thompson-growth-form', 'thompson1917-ch07-04');
const ch0704 = JSON.parse(fs.readFileSync(path.join(ch0704Dir, 'result.json'), 'utf8'));
const cornealPix = ch0704.measured.extra.per_tissue['human-corneal-endothelium'];
const segBias = ch0704.revisions[0];
const eyeBank = JSON.parse(fs.readFileSync(path.join(ch0704Dir, 'eye-bank-hexagonality', 'derived', 'summary.json'), 'utf8'));
const eyeBankRun = JSON.parse(fs.readFileSync(path.join(ch0704Dir, 'eye-bank-hexagonality', 'result.json'), 'utf8'));
const pct = (x, d = 0) => (100 * x).toFixed(d);
const q5 = eyeBank.f6_by_cv_quintile;
const cornealVars = {
  CORNEA_JUNCTIONS: cornealPix.junctions_measured.toLocaleString('en-US'),
  CORNEA_NEAR_TWENTY: pct(cornealPix.frac_all_within_15deg),
  CORNEA_T: pct(cornealPix.frac_T_like),
  CORNEA_SD: cornealPix.angle_sd.toFixed(1),
  SEGBIAS_FROM: segBias.from.confidence.toFixed(2),
  SEGBIAS_TO: segBias.to.confidence.toFixed(2),
  SEGBIAS_AGENTS: segBias.prompted_by.map((p) => `<a href="${p.comment}">${esc(p.agent)}</a>`).join(', '),
  EYEBANK_IMAGES: eyeBank.descriptives.images_total.toLocaleString('en-US'),
  EYEBANK_CELLS: eyeBank.descriptives.rows.toLocaleString('en-US'),
  EYEBANK_RHO: eyeBank.image_level.rho_cv_f6.toFixed(2),
  EYEBANK_CI_LO: eyeBank.image_level.ci95[0].toFixed(2),
  EYEBANK_CI_HI: eyeBank.image_level.ci95[1].toFixed(2),
  EYEBANK_HEX_LOW_CV: pct(q5[0].f6_median, 1),
  EYEBANK_HEX_HIGH_CV: pct(q5[q5.length - 1].f6_median, 1),
  EYEBANK_SIDES: eyeBank.descriptives.mean_cell_sides_overall.toFixed(3),
  EYEBANK_LEWIS: eyeBank.secondary_lewis_within_image.median_rho_area_sides.toFixed(2),
  EYEBANK_DENSITY_RHO: eyeBank.secondary_density_f6_image.rho.toFixed(2),
  EYEBANK_VERDICT: esc(eyeBankRun.verdict),
  EYEBANK_PREREG_COMMIT: preregCommit(path.join(ch0704Dir, 'eye-bank-hexagonality', 'result.json')),
  CORNEA_CLAIM_VERDICT: esc(ch0704.verdict),
  CORNEA_CLAIM_CONF: ch0704.confidence.toFixed(2),
};

// The commit that added a pre-registration file, as recorded by git (first commit touching the path).
function preregCommit(file) {
  const out = execFileSync('git', ['log', '--diff-filter=A', '--format=%h', '--', path.relative(ROOT, file)], { cwd: ROOT, encoding: 'utf8' }).trim();
  if (!out) throw new Error(`no commit adds ${file}; commit the pre-registration first`);
  return out.split('\n').pop();
}

// The measured four-arm comparison (test-data/agent-comparison/four-arm.json).
const fourArm = JSON.parse(fs.readFileSync(R('test-data', 'agent-comparison', 'four-arm.json'), 'utf8'));
const ARMS = ['single', 'isolated', 'centralized', 'decentralized'];
const e1 = fourArm.experiments[0].arms, e2 = fourArm.experiments[1].arms;
const swarmArms = ARMS.filter((a) => a !== 'single');
const minGain = Math.min(...fourArm.experiments.map((e) => Math.min(...swarmArms.map((a) => e.arms[a].primary.verified - e.arms.single.primary.verified))));
// The recorded cost sentence ("a fifth … to a tenth") lives in four-arm.json. Recomputing
// it from the cheapest arm rounded the ratio to 0 and printed "0th".
const costSentence = fourArm.what_this_does_not_show.find((s) => s.startsWith('The single agent costs'));
if (!costSentence) throw new Error('four-arm.json has no single-agent cost sentence');
const fourArmRows = ARMS.map((a) => `<tr><td>${a}</td><td>${e1[a].primary.verified} of 20</td><td>$${e1[a].primary.cost_usd_list.toFixed(2)}</td><td>${e2[a].primary.verified} of 20</td><td>$${e2[a].primary.cost_usd_list.toFixed(2)}</td></tr>`).join('');
const fourArmVars = {
  FOURARM_ROWS: fourArmRows,
  FOURARM_MIN_GAIN: minGain,
  FOURARM_COST: esc(costSentence.split(';')[0]),
  FOURARM_MODEL: esc(fourArm.source.model_all_arms),
  FOURARM_NOT: fourArm.what_this_does_not_show.map((s) => `<li>${esc(s)}</li>`).join(''),
};

// Hosted MCP server usage, from mcp/usage/<date>.json.
const usageFiles = fs.readdirSync(R('mcp', 'usage')).filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort();
const mcp = { calls: 0, sessions: 0, clients: new Set() };
for (const f of usageFiles) {
  const u = JSON.parse(fs.readFileSync(R('mcp', 'usage', f), 'utf8'));
  for (const t of Object.values(u.tools || {})) mcp.calls += (t.ok || 0) + (t.error || 0);
  for (const [name, c] of Object.entries(u.clients || {})) { mcp.sessions += c.sessions || 0; mcp.clients.add(name); }
}
const mcpVars = {
  MCP_CALLS: mcp.calls, MCP_SESSIONS: mcp.sessions, MCP_CLIENTS: mcp.clients.size,
  MCP_DAYS: usageFiles.length === 1 ? usageFiles[0].replace('.json', '') : `${usageFiles[0].replace('.json', '')} to ${usageFiles.at(-1).replace('.json', '')}`,
};

// Claim sources table, largest first; the small math-bio set is folded into one row.
const BOOKS = new Set(['Aristotle', 'Stephen Wolfram', 'Michael Levin', "D'Arcy Wentworth Thompson", 'Charles Darwin']);
const sourceRows = [...byThinker].filter(([t]) => BOOKS.has(t)).sort((a, b) => b[1] - a[1]).map(([t, k]) => {
  const mine = claims.filter((c) => c.thinker === t);
  const works = [...new Set(mine.map((c) => c.work))];
  const work = works.length === 1 ? works[0] : `${works.length} papers`;
  return `<tr><td>${esc(t)}</td><td>${esc(work)}</td><td class="num">${k}</td><td class="num">${mine.filter((c) => c.theorem).length}</td><td class="num">${mine.filter((c) => verdict(c)).length}</td></tr>`;
});
const rest = claims.filter((c) => !BOOKS.has(c.thinker));
sourceRows.push(`<tr><td>${new Set(rest.map((c) => c.thinker)).size} mathematical biologists and hygromorph-mechanics authors</td><td>${new Set(rest.map((c) => c.work)).size} papers</td><td class="num">${rest.length}</td><td class="num">${rest.filter((c) => c.theorem).length}</td><td class="num">${rest.filter((c) => verdict(c)).length}</td></tr>`);

const built = claimsDoc.built ? new Date(claimsDoc.built.replace(' ', 'T') + 'Z') : new Date();
const DATE_LONG = built.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
const BUILT_UTC = claimsDoc.built || built.toISOString().slice(0, 16).replace('T', ' ');

const fmt = (v) => (typeof v === 'number' ? v.toLocaleString('en-US') : v);
const vars = {
  ...Object.fromEntries(Object.entries({ ...counts, ...mcpVars, ...barVars }).map(([k, v]) => [k, fmt(v)])),
  ...fourArmVars,
  ...cornealVars,
  SOURCE_ROWS: sourceRows.join(''),
  DATE_LONG, BUILT_UTC,
};

let html = fs.readFileSync(TEMPLATE, 'utf8').replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => {
  if (!(k in vars)) throw new Error(`template placeholder without a value: ${k}`);
  return vars[k];
});
const markdown = articleToMarkdown(html);
// The shared header and footer link to the atlas pages relative to docs/; this page is one level down.
html = withChrome(html, 'blog').replace(/(href|src)="(?!(?:https?:)?\/\/|#|\.\.?\/|mailto:|data:)/g, '$1="../');
fs.mkdirSync(path.dirname(OUT), { recursive: true });
const card = R('assets', 'delphi-where-it-stands.png');
if (!fs.existsSync(card)) throw new Error('missing assets/delphi-where-it-stands.png; run python3 scripts/site/build-summary-video.py');
fs.copyFileSync(card, R('docs', 'blog', 'delphi-where-it-stands.png'));
// Hero art: the segmented Drosophila compound eye (assets/deck/cell-geometry-thumb.jpg, a centre crop of
// claim-sources/cell-geometry/results/drosophila-compound-eye/overlay.png).
const eye = R('assets', 'deck', 'cell-geometry-thumb.jpg');
if (!fs.existsSync(eye)) throw new Error('missing assets/deck/cell-geometry-thumb.jpg');
fs.copyFileSync(eye, R('docs', 'blog', 'compound-eye.jpg'));
// The validation harness refusing the project's own winged zebrafish, screen-captured from the dashboard's
// /validate page for the product report (https://delphi-mission-control.ashenoy000.workers.dev/docs).
const gate = R('assets', 'validate-gate.jpg');
if (!fs.existsSync(gate)) throw new Error('missing assets/validate-gate.jpg');
fs.copyFileSync(gate, R('docs', 'blog', 'validate-gate.jpg'));
// Design Studio screenshots, captured from the live runtime for the studio demo video.
const CAPTURES = R('studio', 'artifacts', 'demo-video-science', 'sources', 'captures');
for (const [src, dst] of [['01-hero-3d-mesh.png', 'studio-flying-fish.png'], ['03-engineering-recorded-runs.png', 'studio-engineering-runs.png']]) {
  if (!fs.existsSync(path.join(CAPTURES, src))) throw new Error(`missing studio capture ${path.relative(ROOT, path.join(CAPTURES, src))}`);
  fs.copyFileSync(path.join(CAPTURES, src), R('docs', 'blog', dst));
}
fs.writeFileSync(OUT, html);
fs.writeFileSync(OUT_MD, markdown);
console.log(`wrote ${path.relative(ROOT, OUT)} (${(html.length / 1024).toFixed(0)} KB)`);
console.log(`wrote ${path.relative(ROOT, OUT_MD)} (${(markdown.length / 1024).toFixed(0)} KB)`);
console.table(counts);

function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

function decode(s) {
  return String(s)
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ');
}

function inline(t) {
  let s = String(t);
  s = s.replace(/<a href="([^"]+)">([\s\S]*?)<\/a>/g, (_, h, x) => `[${inline(x)}](${h})`);
  s = s.replace(/<code>([\s\S]*?)<\/code>/g, (_, x) => `\`${decode(x)}\``);
  s = s.replace(/<\/?(?:b|strong)>/g, '**');
  s = s.replace(/<\/?(?:i|em)>/g, '*');
  s = s.replace(/<br\s*\/?>/g, ' ');
  s = s.replace(/<[^>]+>/g, '');
  return decode(s).replace(/\s+/g, ' ').trim();
}

function tableToMd(table) {
  const rows = [...table.matchAll(/<tr>([\s\S]*?)<\/tr>/g)].map((m) =>
    [...m[1].matchAll(/<t[hd][^>]*>([\s\S]*?)<\/t[hd]>/g)].map((c) => inline(c[1]).replace(/\|/g, '\\|')));
  if (!rows.length) return '';
  const head = rows[0];
  const body = rows.slice(1).map((r) => {
    while (r.length < head.length) r.push('');
    return r;
  });
  return `\n| ${head.join(' | ')} |\n| ${head.map(() => '---').join(' | ')} |\n${body.map((r) => `| ${r.join(' | ')} |`).join('\n')}\n`;
}

// The article, as Markdown, with site links absolute so the file can be pasted elsewhere.
function articleToMarkdown(page) {
  let s = page.match(/<div class="essay">([\s\S]*)<\/article>/)[1];
  s = s.replace(/<div class="byline">([\s\S]*?)<\/div>/, (_, t) => `\n${[...t.matchAll(/<span[^>]*>([\s\S]*?)<\/span>/g)].map((m) => inline(m[1])).filter((x) => x && x !== 'Read time').join(' · ')}\n`);
  s = s.replace(/<aside class="rail"[\s\S]*?<\/aside>/, '');
  s = s.replace(/<span class="section-no">[\s\S]*?<\/span>\n?/g, '');
  s = s.replace(/<div class="record-panel"[\s\S]*?<\/div>\n<\/div>\n/, '');
  s = s.replace(/<div class="intro-band"><div class="eyebrow">([\s\S]*?)<\/div><p>([\s\S]*?)<\/p><\/div>/g, (_, e, t) => `\n**${inline(e)}.** ${inline(t)}\n`);
  s = s.replace(/<div class="eyebrow[^"]*">([\s\S]*?)<\/div>/g, (_, t) => `\n${inline(t)}\n`);
  s = s.replace(/<figure[^>]*><img src="([^"]+)" alt="([^"]*)"[^>]*><figcaption>([\s\S]*?)<\/figcaption><\/figure>/g,
    (_, src, alt, cap) => `\n![${inline(alt)}](${src})\n\n*${inline(cap)}*\n`);
  s = s.replace(/<h1>([\s\S]*?)<\/h1>/g, (_, t) => `\n# ${inline(t)}\n`);
  s = s.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/g, (_, t) => `\n## ${inline(t)}\n`);
  s = s.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/g, (_, t) => `\n### ${inline(t)}\n`);
  s = s.replace(/<div class="proof-grid">([\s\S]*?)<\/div>\n<\/div>/g, (_, t) => [...t.matchAll(/<div class="small-title">([\s\S]*?)<\/div><p>([\s\S]*?)<\/p>/g)].map((m) => `\n**${inline(m[1])}.** ${inline(m[2])}\n`).join(''));
  s = s.replace(/<blockquote class="pullquote">([\s\S]*?)<\/blockquote>/g, (_, t) => `\n> ${inline(t)}\n`);
  s = s.replace(/<table[\s\S]*?<\/table>/g, tableToMd);
  s = s.replace(/<ul>([\s\S]*?)<\/ul>/g, (_, t) => `\n${[...t.matchAll(/<li>([\s\S]*?)<\/li>/g)].map((m) => `- ${inline(m[1])}`).join('\n')}\n`);
  s = s.replace(/<pre>([\s\S]*?)<\/pre>/g, (_, t) => `\n\`\`\`\n${decode(t).trim()}\n\`\`\`\n`);
  s = s.replace(/<p(?: class="[^"]*")?>([\s\S]*?)<\/p>/g, (_, t) => `\n${inline(t)}\n`);
  s = s.replace(/<[^>]+>/g, '');
  s = decode(s).replace(/\n{3,}/g, '\n\n').trim() + '\n';
  s = s.replace(/\]\((?!https?:|#)([^)]+)\)/g, (_, p) => {
    // The standing card is copied beside this file; other links go to the site.
    if (/\.(png|gif|jpe?g)$/i.test(p)) return `](${p.replace(/^\.\.\/blog\//, '')})`;
    return `](https://delphibio.org/${p.replace(/^\.\.\//, '')})`;
  });
  return s;
}
