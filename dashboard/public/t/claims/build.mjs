#!/usr/bin/env node
// Builds dashboard/public/t/claims/tests.json from every claim-tests/<project>/<id>/result.json plus the claim's
// label and assessor truth score from docs/claims.json. Every number on the claims sub-dashboard comes from this file.
//   node dashboard/public/t/claims/build.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../../..');
const graph = JSON.parse(fs.readFileSync(path.join(root, 'docs/claims.json'), 'utf8'));
const byId = Object.fromEntries(graph.claims.map(c => [c.id, c]));

const tests = [];
const ct = path.join(root, 'claim-tests');
for (const proj of fs.readdirSync(ct, { withFileTypes: true }).filter(d => d.isDirectory())) {
  for (const t of fs.readdirSync(path.join(ct, proj.name), { withFileTypes: true }).filter(d => d.isDirectory())) {
    const f = path.join(ct, proj.name, t.name, 'result.json');
    if (!fs.existsSync(f)) continue;
    const r = JSON.parse(fs.readFileSync(f, 'utf8'));
    const c = byId[r.claim_id] || null;
    const files = (r.datasets || []).flatMap(d => d.files || []);
    tests.push({
      claim_id: r.claim_id, project: proj.name, status: r.status, verdict: r.verdict || null, reason: r.reason || null,
      confidence: r.confidence ?? null,
      label: c ? c.label : r.claim_id, thinker: c ? c.thinker : null, year: c ? c.year : null, kind: c ? c.kind : null,
      graph_status: c ? c.status : null, truth: c ? c.truth : null, truthBy: c ? (c.truth_by || []) : [],
      hypothesis: r.hypothesis, pass: r.pass_criterion, fail: r.fail_criterion, interpretation: r.interpretation,
      method: r.method || null, measured: r.measured || null, caveats: r.caveats || [],
      datasets: (r.datasets || []).map(d => ({ id: d.id, name: d.name, url: d.landing_url, doi: d.doi, license: d.license, version: d.version,
        n_files: (d.files || []).length, bytes: (d.files || []).reduce((s, x) => s + (x.byte_size || 0), 0),
        files: (d.files || []).map(x => ({ url: x.download_url, bytes: x.byte_size ?? null, sha256: x.sha256 ?? null, retrieved_at: x.retrieved_at ?? null, obtained: x.obtained !== false && !!x.sha256 })) })),
      n_files_obtained: files.filter(x => x.sha256).length, bytes_obtained: files.reduce((s, x) => s + (x.sha256 ? (x.byte_size || 0) : 0), 0),
      agent: r.agent || null,
      dir: `claim-tests/${proj.name}/${t.name}/`
    });
  }
}
const count = (arr, f) => arr.reduce((m, x) => { const k = f(x); m[k] = (m[k] || 0) + 1; return m; }, {});
const out = {
  built: new Date().toISOString(), graphBuilt: graph.built, tests,
  stats: { total: tests.length, byVerdict: count(tests, t => t.verdict || t.status), byProject: count(tests, t => t.project),
    complete: tests.filter(t => t.status === 'complete').length,
    datasets: tests.reduce((s, t) => s + t.datasets.length, 0), files: tests.reduce((s, t) => s + t.n_files_obtained, 0),
    bytes: tests.reduce((s, t) => s + t.bytes_obtained, 0) }
};
fs.writeFileSync(path.join(here, 'tests.json'), JSON.stringify(out));
console.log(`claims sub-dashboard: ${out.stats.total} tests (${JSON.stringify(out.stats.byVerdict)}), ${out.stats.files} files, ${(out.stats.bytes / 1e6).toFixed(1)} MB`);
