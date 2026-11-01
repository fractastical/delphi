#!/usr/bin/env node
// Builds the "Delphi — Lean for Biology" project overview deck, written to two identical files:
// docs/deck/index.html (GitHub Pages, https://delphibio.org/deck/) and assets/deck/overview-deck.html
// (beside the other decks in the repo), from
// scripts/site/templates/overview-deck.template.html. Every number in the deck is computed here
// from repo files: docs/claims.json (built by build-claim-graph.mjs), test-data/organisms/merged/
// taxa.json, the Lean law registry via lib/lean-source.mjs, and the frontier node's usage record
// (swarm/frontier/built.json) for slide 4's stack. Edit the template, not the output.
// Each output also gets an overview-deck.pdf beside it (one page per slide, via the template's print
// CSS), rendered with headless Chrome; set CHROME_PATH if it is not found, or pass --no-pdf to skip.
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const R = (...p) => path.join(ROOT, ...p);
const TEMPLATE = R('scripts', 'site', 'templates', 'overview-deck.template.html');
// `--draft [dir]` writes index.html and overview-deck.pdf to a scratch directory (default /tmp/delphi-deck-draft)
// and leaves docs/deck/ and assets/deck/ untouched, so a change can be reviewed before it reaches the live deck.
const draftIdx = process.argv.indexOf('--draft');
const OUTS = draftIdx >= 0
  ? [path.resolve(process.argv[draftIdx + 1] && !process.argv[draftIdx + 1].startsWith('--') ? process.argv[draftIdx + 1] : '/tmp/delphi-deck-draft', 'index.html')]
  : [R('docs', 'deck', 'index.html'), R('assets', 'deck', 'overview-deck.html')];

const { listLaws } = await import(R('lib', 'lean-source.mjs'));

const claimsDoc = JSON.parse(fs.readFileSync(R('docs', 'claims.json'), 'utf8'));
const claims = claimsDoc.claims;
const taxa = JSON.parse(fs.readFileSync(R('test-data', 'organisms', 'merged', 'taxa.json'), 'utf8'));
const laws = listLaws().laws;

const n = (f) => claims.filter(f).length;
const verdict = (c) => (c.evidence && typeof c.evidence === 'object' ? c.evidence.verdict : c.evidence) || null;

const counts = {
  CLAIMS: claims.length,
  MATH: n((c) => c.math),
  THEOREMS: n((c) => c.theorem),
  LEAN: n((c) => c.theorem && c.proof === 'lean'),
  LIT: n((c) => c.theorem && c.proof === 'literature'),
  TESTED: n((c) => verdict(c)),
  SUPPORTS: n((c) => verdict(c) === 'supports'),
  REFUTES: n((c) => verdict(c) === 'refutes'),
  MIXED: n((c) => verdict(c) === 'mixed'),
  INCONCLUSIVE: n((c) => verdict(c) === 'inconclusive'),
  LIVE: n((c) => c.registry === 'production' && !c.draft),
  WORKS: new Set(claims.map((c) => c.work)).size,
  TAXA: taxa.length,
  TAXA_DATA: taxa.filter((t) => Array.isArray(t.datasets) && t.datasets.length).length,
  REG_LAWS: laws.length,
  REG_ACCEPTED: laws.filter((l) => l.status === 'accepted').length,
};
if (counts.TESTED !== counts.SUPPORTS + counts.REFUTES + counts.MIXED + counts.INCONCLUSIVE) {
  throw new Error('unknown evidence verdict in docs/claims.json');
}

// Claim sources for the rotating graph: one bucket per thinker, largest first.
const byThinker = new Map();
for (const c of claims) byThinker.set(c.thinker, (byThinker.get(c.thinker) || 0) + 1);
const sources = [...byThinker].map(([thinker, count]) => ({ thinker, count })).sort((a, b) => b.count - a.count);
const universe = { total: counts.CLAIMS, math: counts.MATH, proved: counts.THEOREMS, sources, built: claimsDoc.built || null };

// Source texts, grouped by thinker with claim counts (computed), plus the formal libraries used.
const yearOf = (y) => (y < 0 ? `c. ${-y} BC` : String(y));
// "Ronald A. Fisher" -> "Fisher", "John Maynard Smith" -> "Maynard Smith", "X & Y" -> X's surname.
const surname = (t) => esc(t.split(/\s*(?:&|\band\b)\s*/)[0].trim().split(' ').slice(1).filter((w) => !/^[A-Z]\.$/.test(w)).join(' '));
const TOP = 5;
const textItems = sources.slice(0, TOP).map(({ thinker, count }) => {
  const ys = claims.filter((c) => c.thinker === thinker).map((c) => c.year).filter((y) => Number.isFinite(y));
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const span = lo === hi ? yearOf(lo) : `${yearOf(lo)}–${yearOf(hi)}`;
  return `<li><b>${surname(thinker) || esc(thinker)}</b> (${span}): ${count} claims</li>`;
});
const restSources = sources.slice(TOP);
const rest = restSources.reduce((a, s) => a + s.count, 0);
if (rest) {
  const named = restSources.slice(0, 3).map((s) => surname(s.thinker)).join(', ');
  textItems.push(`<li>${restSources.length} more mathematical biologists (${named}, …): ${rest} claims</li>`);
}
textItems.push('<li><b>Lean 4 + Mathlib</b> for the machine-checked proofs</li>');

// The remaining three lists are facts taken from README.md, COLLABORATIONS.md, docs/PORTAL.md and
// sponsors/*.md. They are names, not counts; keep them in step with those files.
const people = [
  '<li><b>Joel Dietz</b>, <b>Amit Shenoy</b>, <b>Kavita Koolkarni</b> (portal), <b>Kris Ganjam</b> (delphi-evolve, delphi-frontier)</li>',
  '<li><b>Knowledge Pixels</b>: nanopublications, the Delphi ontology, the <code>nanopub</code> and <code>delphi</code> skills</li>',
  '<li><b>Science Claw Hack @ MIT</b> and the SentiLab, ScienceClaw and Moltbook agents whose objections changed our tests</li>',
  '<li>Assessors from Anthropic, OpenAI, Google and a self-hosted Qwen3-32B; assessor is never builder</li>',
];
const code = [
  '<li><b>fractastical/delphi</b>: claims, assessments, Lean proofs, claim tests, the <code>delphisci</code> MCP server</li>',
  '<li><b>morpholib</b>, <b>delphi-portal</b>, <b>delphi-evolve</b>, <b>delphi-frontier</b></li>',
  '<li><b>Cellpose</b> (CPSAM v2) for segmentation; <b>INDRA CoGEx</b> for molecular statements</li>',
  '<li>nanopub-registry, Nanodash, Nanopub Query</li>',
];
const data = [
  `<li><b>GBIF, NCBI, Wikidata, WoRMS, PBDB</b>: identifiers and datasets for ${counts.TAXA.toLocaleString('en-US')} taxa; <b>Europe PMC</b> for the Levin papers</li>`,
  '<li><b>NVIDIA</b> Brev L40S serving the Qwen3-32B assessor</li>',
  '<li><b>Nebius</b> Scientific AI Platform: Cellpose and ESMFold2 operations</li>',
  '<li><b>OpenResearch</b> (alphaXiv <code>orx</code>) for literature grounding; <b>Formlabs</b> SLA prints</li>',
];

// ---- Swarm: hand-kept snapshot table in chats/SWARM_COORDINATION.md, plus the transcribed chats.
const swarmMd = fs.readFileSync(R('chats', 'SWARM_COORDINATION.md'), 'utf8');
const snapshotHead = swarmMd.match(/^### Snapshot: (.+)$/m);
const snapRow = (label) => {
  const m = swarmMd.match(new RegExp(`^\\| ${label}[^|]*\\| *([\\d,]+)`, 'm'));
  if (!m) throw new Error(`SWARM_COORDINATION.md: no snapshot row starting "${label}"`);
  return Number(m[1].replace(/,/g, ''));
};
const swarm = {
  SWARM_CHATS: snapRow('Local Cursor chats'),
  SWARM_SUBAGENTS: snapRow('Subagents launched'),
  SWARM_CLOUD: snapRow('Cloud agents launched'),
  SWARM_SNAPSHOT: snapshotHead ? snapshotHead[1].replace(/\s*\(.*\)$/, '') : 'undated',
  CHATS_LOGGED: fs.readdirSync(R('chats')).filter((f) => /^\d{4}-\d{2}-\d{2}_.*\.md$/.test(f)).length,
};

// ---- Four-arm comparison: measured, from test-data/agent-comparison/four-arm.json.
const fourArm = JSON.parse(fs.readFileSync(R('test-data', 'agent-comparison', 'four-arm.json'), 'utf8'));
const ARMS = ['single', 'isolated', 'centralized', 'decentralized'];
const fourArmSvg = (() => {
  const W = 640, H = 170, left = 92, top = 18, rowH = 34, barMax = W - left - 150;
  const exps = fourArm.experiments;
  let out = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" role="img" aria-label="Verified datasets out of 20 per arm, two experiments">`;
  out += `<text x="${left}" y="11" font-size="9" fill="#7B8798" font-family="monospace">0</text><text x="${left + barMax}" y="11" font-size="9" fill="#7B8798" font-family="monospace" text-anchor="end">20 of 20</text>`;
  ARMS.forEach((arm, i) => {
    const y = top + i * rowH;
    out += `<text x="${left - 8}" y="${y + 20}" font-size="12" fill="#142033" text-anchor="end" font-weight="600">${arm}</text>`;
    exps.forEach((e, k) => {
      const p = e.arms[arm].primary;
      const v = p.verified, w = Math.round((v / 20) * barMax), yy = y + k * 13;
      const fill = k === 0 ? '#2457D6' : '#B23A5A';
      out += `<rect x="${left}" y="${yy}" width="${w}" height="10" rx="2" fill="${fill}" opacity="${arm === 'single' ? 0.55 : 0.9}"/>`;
      out += `<text x="${left + w + 5}" y="${yy + 9}" font-size="10" fill="#4B5A70" font-family="monospace">${v}${p.fabricated_identifiers_all_attempts ? ` (${p.fabricated_identifiers_all_attempts} fabricated id)` : ''} · $${p.cost_usd_list.toFixed(2)}</text>`;
    });
  });
  out += `<text x="${left}" y="${H - 4}" font-size="9.5" fill="#7B8798">blue: exp 1, web tools allowed · rose: exp 2, landing page must be fetched · ${fourArm.source.model_all_arms} in every arm · labels: verified · cost</text></svg>`;
  return out;
})();
const notShow = fourArm.what_this_does_not_show;
const fourArmVars = {
  FOURARM_SVG: fourArmSvg,
  FOURARM_SHOWS: esc(fourArm.what_this_shows),
  FOURARM_NOT: esc(notShow[0]),
  FOURARM_NOT_ALL: esc(notShow.join(' ')),
  FOURARM_TAKEAWAY: (() => {
    const e1 = fourArm.experiments[0].arms, e2 = fourArm.experiments[1].arms;
    const best = (e) => ARMS.filter((a) => a !== 'single' && e[a].primary.fabricated_identifiers_all_attempts === 0).sort((a, b) => e[b].primary.verified - e[a].primary.verified)[0];
    const b1 = best(e1), b2 = best(e2);
    return `Best clean swarm arm: ${e1[b1].primary.verified} and ${e2[b2].primary.verified} of 20 against the single agent’s ${e1.single.primary.verified} and ${e2.single.primary.verified}, at ${(e1[b1].primary.cost_usd_list / e1.single.primary.cost_usd_list).toFixed(1)}× and ${(e2[b2].primary.cost_usd_list / e2.single.primary.cost_usd_list).toFixed(1)}× the cost; the swarm shapes are indistinguishable at n = 20.`;
  })(),
};

// ---- Collaborations: the two tables in COLLABORATIONS.md.
const collabMd = fs.readFileSync(R('COLLABORATIONS.md'), 'utf8');
const mdTable = (heading) => {
  const start = collabMd.indexOf(heading);
  if (start < 0) throw new Error(`COLLABORATIONS.md: heading not found: ${heading}`);
  const block = collabMd.slice(start).split(/\n(?=## )/)[0];
  const rows = block.split('\n').filter((l) => l.startsWith('|')).slice(2);
  return rows.map((l) => l.slice(1, -1).split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, '|')));
};
const plain = (t) => t.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1').replace(/`([^`]+)`/g, '$1').replace(/\*+/g, '');
const teams = mdTable('## People and teams');
const agents = mdTable('## Agent networks').filter((r) => !/^Nothing to change/i.test(r[3]));
const agentChange = (r) => {
  // "What they contributed" is the readable half; cut at the first ';' and cap the length.
  let t = plain(r[2]).split(';')[0].trim();
  if (t.length > 95) t = t.slice(0, 92).replace(/\s+\S*$/, '') + '…';
  return t;
};
const teamShort = (r) => {
  let who = plain(r[1]).replace(/\s*\(.*$/, '').trim();
  let what = plain(r[3]).split(/\.\s/)[0].trim();
  if (what.length > 110) what = what.slice(0, 107).replace(/\s+\S*$/, '') + '…';
  return `<li><b>${esc(who)}</b> (${esc(plain(r[2]).split(/[;,(]/)[0].trim())}): ${esc(what)} <i>${esc(plain(r[4]).split(/[;,.(]/)[0].trim())}</i></li>`;
};
const collab = {
  COLLAB_TEAMS_N: teams.length,
  COLLAB_AGENTS_N: agents.length,
  COLLAB_AGENTS: agents.map((r) => `<li><b>${esc(plain(r[0]))}</b>: ${esc(agentChange(r))}</li>`).join(''),
  COLLAB_TEAMS: teamRows(5),
  COLLAB_TEAMS_SHORT: teamRows(3),
};
// Done and Active contacts first, one row per counterpart.
function teamRows(n) {
  const rank = (r) => (/^Done/.test(plain(r[4])) ? 0 : /^Active/.test(plain(r[4])) ? 1 : /^Contact$/.test(plain(r[4]).trim()) ? 3 : 2);
  const seen = new Set();
  return teams.slice().sort((a, b) => rank(a) - rank(b)).filter((r) => {
    const who = plain(r[1]).replace(/\s*\(.*$/, '').trim().split(' ')[0];
    if (seen.has(who)) return false; seen.add(who); return true;
  }).slice(0, n).map(teamShort).join('');
}

// ---- Hosted MCP server usage, from mcp/usage/<date>.json.
const usageFiles = fs.readdirSync(R('mcp', 'usage')).filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f)).sort();
const usage = usageFiles.map((f) => JSON.parse(fs.readFileSync(R('mcp', 'usage', f), 'utf8')));
const mcp = { calls: 0, sessions: 0, clients: new Set() };
for (const u of usage) {
  for (const t of Object.values(u.tools || {})) mcp.calls += (t.ok || 0) + (t.error || 0);
  for (const [name, c] of Object.entries(u.clients || {})) { mcp.sessions += c.sessions || 0; mcp.clients.add(name); }
}
const mcpVars = {
  MCP_CALLS: mcp.calls, MCP_SESSIONS: mcp.sessions, MCP_CLIENTS: mcp.clients.size,
  MCP_DAYS: usageFiles.length === 1 ? usageFiles[0].replace('.json', '') : `${usageFiles[0].replace('.json', '')} to ${usageFiles.at(-1).replace('.json', '')}`,
};

// ---- Stack: the frontier node's own usage record, swarm/frontier/built.json (quoted, not re-verified).
const frontier = JSON.parse(fs.readFileSync(R('swarm', 'frontier', 'built.json'), 'utf8')).timeline;
const jobs = frontier.usage.jobs;
const tel = frontier.rows.filter((r) => r.kind === 'GPU telemetry').map((r) => Number(r.outcome.match(/mean ([\d.]+)%/)[1]));
const live = frontier.rows.filter((r) => r.kind === 'live check');
const ledger = frontier.audits.models.data;
const entries = ledger.entries;
const embed = entries.find((e) => e.kind === 'embedding_service');
const STATUS = {
  completed: 'completed', succeeded: 'completed', completed_pilot: 'pilot only',
  provider_completed_science_runner_failed: 'runner failed', completed_with_declared_checks_passing: 'checks passed',
  failed: 'failed', completed_after_output_repair: 'completed after repair',
  completed_computation_scientific_predicates_failed: 'targets failed', completed_with_mixed_predicate_results: 'mixed targets',
  completed_for_final_video_revision: 'completed',
};
const provider = (p) => p.replace(/^Nebius serverless (\S+) job harness$/, 'Nebius $1').replace(/^Nebius Scientific AI MCP$/, 'Nebius Scientific AI')
  .replace(/^Google Generative Language API$/, 'Google').replace(/^local CPU execution.*$/, 'local CPU');
const nameOf = (e) => (e.model_or_tool || e.model || e.models.map((m) => m.model).join(', ')).split(';')[0].replace(/ generic edited (.+) example$/, ' ($1)');
const groups = new Map();
for (const e of entries) {
  const k = nameOf(e);
  if (!groups.has(k)) groups.set(k, { provider: provider(e.provider), statuses: [] });
  groups.get(k).statuses.push(STATUS[e.status] || e.status.replace(/_/g, ' '));
}
const tally = (s) => Object.entries(s.reduce((a, x) => ((a[x] = (a[x] || 0) + 1), a), {})).map(([x, c]) => (s.length > 1 ? `${c} ${x}` : x)).join(', ');
const stack = {
  STACK_JOBS: jobs.length,
  STACK_GPU: jobs.filter((j) => j.kind === 'GPU').length,
  STACK_CPU: jobs.filter((j) => j.kind === 'CPU').length,
  STACK_COMPLETED: jobs.filter((j) => j.state === 'COMPLETED').length,
  STACK_TEL_N: tel.length,
  STACK_TEL_RANGE: `${Math.round(Math.min(...tel))}–${Math.round(Math.max(...tel))}%`,
  STACK_EMBED: embed.usage.documents.toLocaleString('en-US'),
  STACK_LIVE: `${live.filter((r) => r.ok).length} of ${live.length}`,
  STACK_RECORDS: entries.length,
  STACK_MODELS: [...groups].map(([k, g]) => `<li><span><b>${esc(k)}</b> · ${esc(g.provider)}</span><span>${esc(tally(g.statuses))}</span></li>`).join(''),
  STACK_BIONEMO: esc(ledger.bionemo_nim.statement),
  STACK_OBSERVED: esc(frontier.observed_at.utc.slice(0, 16).replace('T', ' ') + ' UTC'),
};

// ---- One worker's run through the stack: Thompson's cell-packing claims, segmented with Cellpose on Nebius.
// Counts come from claim-sources/cell-geometry/results/*/cellpose.json (one receipt per Nebius operation) and
// summary.json; verdicts from the three result.json files that claim_tests.py wrote.
const CG = R('claim-sources', 'cell-geometry', 'results');
const cgSummary = JSON.parse(fs.readFileSync(path.join(CG, 'summary.json'), 'utf8'));
const cgOps = fs.readdirSync(CG).filter((d) => fs.existsSync(path.join(CG, d, 'cellpose.json')))
  .map((d) => JSON.parse(fs.readFileSync(path.join(CG, d, 'cellpose.json'), 'utf8')));
const cgUsable = Object.values(cgSummary.images).filter((i) => i.sufficient);
const cgTests = [
  ['thompson1917-ch07-04', 'walls meet at 120°', (r) => `${r.measured.value} of ${r.measured.n} tissues beat the control`],
  ['thompson1917-ch07-08', 'regular only with equal cells', (r) => `ρ = ${r.measured.value}, ${r.measured.uncertainty}, n = ${r.measured.n}`],
  ['thompson1917-ch07-10', 'hexagonal on average', (r) => `${r.measured.value} of ${r.measured.n} tissues mean six`],
].map(([id, label, measure]) => {
  const dir = R('test-data', 'claim-tests', 'thompson-growth-form', id);
  const multi = path.join(dir, 'cellpose-multi-tissue', 'result.json');
  const r = JSON.parse(fs.readFileSync(fs.existsSync(multi) ? multi : path.join(dir, 'result.json'), 'utf8'));
  if (!/Cellpose/.test(r.method) || !/Nebius/.test(r.method)) throw new Error(`${id}: expected the Cellpose-on-Nebius test`);
  if (r.preregistered) throw new Error(`${id}: the panel describes it as exploratory; update the label`);
  return { id, label, verdict: r.verdict, measure: measure(r) };
});
const cgThumb = R('assets', 'deck', 'cell-geometry-thumb.jpg'); // centre crop of results/drosophila-compound-eye/overlay.png
const cellGeometry = {
  CG_THUMB: `data:image/jpeg;base64,${fs.readFileSync(cgThumb).toString('base64')}`,
  CG_OPS: cgOps.length,
  CG_CELLS: cgOps.reduce((a, o) => a + o.object_count, 0),
  CG_SECONDS: (cgOps.reduce((a, o) => a + o.timings.duration_s, 0) / cgOps.length).toFixed(1),
  CG_MODEL: `${cgOps[0].model_id.split('/').pop()}, Cellpose ${cgOps[0].cellpose_version}`,
  CG_TISSUES: cgUsable.length,
  CG_INTERIOR: cgUsable.reduce((a, i) => a + i.interior_cells, 0),
  CG_SPECIES: new Set(JSON.parse(fs.readFileSync(R('test-data', 'claim-tests', 'thompson-growth-form', 'thompson1917-ch07-08', 'cellpose-multi-tissue', 'result.json'), 'utf8')).datasets.map((d) => d.role.split(',')[0])).size,
  CG_TESTS: cgTests.map((t) => `<li title="${t.id}"><span><b>${esc(t.label)}</b></span><span><span class="verdict ${t.verdict}">${esc(t.verdict)}</span>, ${esc(t.measure)}</span></li>`).join(''),
};

// ---- Sponsor logos for slide 4, as published on the Science Claw Hack site: assets/partners/partners.json.
const partnerDoc = JSON.parse(fs.readFileSync(R('assets', 'partners', 'partners.json'), 'utf8'));
const logo = (p) => {
  const bytes = fs.readFileSync(R('assets', 'partners', p.file));
  const mime = p.file.endsWith('.svg') ? 'image/svg+xml' : 'image/png';
  const style = `height:${p.height}px${p.filter ? `;filter:${p.filter}` : ''}`;
  return `<img src="data:${mime};base64,${bytes.toString('base64')}" alt="${esc(p.name)}" style="${style}">`;
};
const PARTNER_EVENT = `${logo(partnerDoc.event)}<span>${esc(partnerDoc.event.name)} sponsors we used</span>`;
const PARTNER_LOGOS = partnerDoc.partners.map((p) => `<span class="partner" title="${esc(p.name)}: ${esc(p.role)}">${logo(p)}</span>`).join('');

const built = claimsDoc.built ? new Date(claimsDoc.built) : new Date();
const DATE_SHORT = built.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const DATE_LONG = built.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

const fmt = (v) => (typeof v === 'number' ? v.toLocaleString('en-US') : v);
const vars = {
  ...Object.fromEntries(Object.entries({ ...counts, ...swarm, ...collab, ...mcpVars, ...stack, ...cellGeometry }).map(([k, v]) => [k, fmt(v)])),
  ...fourArmVars,
  DATE_SHORT, DATE_LONG, PARTNER_EVENT, PARTNER_LOGOS,
  UNIVERSE_JSON: JSON.stringify(universe),
  PEOPLE: people.join(''), CODE: code.join(''), TEXTS: textItems.join(''), DATA: data.join(''),
};

let html = fs.readFileSync(TEMPLATE, 'utf8');
html = html.replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => {
  if (!(k in vars)) throw new Error(`template placeholder without a value: ${k}`);
  return vars[k];
});
for (const id of ['deck-data', 'universe-data']) {
  const m = html.match(new RegExp(`id="${id}">([\\s\\S]*?)</script>`));
  JSON.parse(m[1]); // throws if a substituted value broke the embedded JSON
}
for (const out of OUTS) {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, html);
  console.log(`wrote ${path.relative(ROOT, out)} (${(html.length / 1024).toFixed(0)} KB)`);
}
console.table(counts);

if (!process.argv.includes('--no-pdf')) {
  const chrome = [
    process.env.CHROME_PATH,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    ...['google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'].map((b) => {
      try { return execFileSync('which', [b], { encoding: 'utf8' }).trim(); } catch { return null; }
    }),
  ].find((p) => p && fs.existsSync(p));
  if (!chrome) {
    console.warn('no Chrome found (set CHROME_PATH): overview-deck.pdf not rebuilt and may be stale');
  } else {
    const pdf = path.join(path.dirname(OUTS[0]), 'overview-deck.pdf');
    execFileSync(chrome, ['--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--virtual-time-budget=8000',
      `--print-to-pdf=${pdf}`, pathToFileURL(OUTS[0]).href], { stdio: 'ignore' });
    for (const out of OUTS.slice(1)) fs.copyFileSync(pdf, path.join(path.dirname(out), 'overview-deck.pdf'));
    for (const out of OUTS) console.log(`wrote ${path.relative(ROOT, path.join(path.dirname(out), 'overview-deck.pdf'))} (${(fs.statSync(pdf).size / 1024).toFixed(0)} KB)`);
  }
}

// Also escapes quotes and backslashes so a value can sit inside the deck-data JSON block.
function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/\\/g, '&#92;'); }
