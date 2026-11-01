#!/usr/bin/env node
// Builds the blinded A9 faithfulness inputs for selected claim tests: the claim text from
// docs/claims.json plus, from the test directory, the hypothesis, the pre-registered criteria, the
// dataset descriptions, the method text and the analysis.py source. Nothing about the result (measured
// values, verdict, confidence, caveats, interpretation) is included: the assessor judges the model, not
// the outcome, and the builder's reasoning is withheld (AGENTS.md, role A9).
//   node claim-tests/assessment/build-inputs.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../..');
const raw = JSON.parse(fs.readFileSync(path.join(root, 'docs/claims.json'), 'utf8'));
const claims = Array.isArray(raw) ? raw : (raw.claims || Object.values(raw));

// Headline tests to assess (project, directory). The directory can differ from the claim id when a
// collaborator's attempt already occupies <claim-id>/.
export const TESTS = [
  ['thompson-growth-form', 'thompson1917-ch03-07--delphi-claims'],
  ['math-bio-theorems', 'kimura-heterozygosity'],
  ['math-bio-theorems', 'maynardsmith-hitchhiking'],
  ['darwin-origin', 'darwin1859-ch09-03--delphi-claims'],
  ['thompson-growth-form', 'thompson1917-ch04-13--delphi-claims'],
  ['darwin-origin', 'darwin1859-ch11-13--delphi-claims'],
  ['math-bio-theorems', 'fisher-sex-ratio'],
];

const inputs = TESTS.map(([project, dir]) => {
  const tdir = path.join(root, 'claim-tests', project, dir);
  const r = JSON.parse(fs.readFileSync(path.join(tdir, 'result.json'), 'utf8'));
  const c = claims.find(k => k.id === r.claim_id) || {};
  const datasets = (r.datasets || []).map(d => `- ${d.name}${d.version ? ` (version: ${d.version})` : ''}${d.doi ? ` doi:${d.doi}` : ''}${d.license ? `; licence: ${d.license}` : ''}. ${d.role ? 'Role: ' + d.role : ''} Files: ${(d.files || []).map(f => (f.download_url || f.member_of_tarball || '?').split('/').pop()).join(', ')}`).join('\n');
  return {
    claim_id: r.claim_id, project, dir,
    label: c.label || r.claim_id, statement: c.statement || '', quote: c.quote || '', thinker: c.thinker || '', work: c.work || '',
    year: c.year || '', chapter: c.chapter || '', kind: c.kind || '',
    hypothesis: r.hypothesis, pass_criterion: r.pass_criterion, fail_criterion: r.fail_criterion,
    datasets, method: r.method || '',
    analysis_source: fs.readFileSync(path.join(tdir, 'analysis.py'), 'utf8').replace(/\r\n/g, '\n'),
  };
});
fs.writeFileSync(path.join(here, 'inputs.json'), JSON.stringify(inputs, null, 1));
const tpl = fs.readFileSync(path.join(here, 'prompt.md'), 'utf8');
fs.mkdirSync(path.join(here, 'prompts'), { recursive: true });
for (const r of inputs) fs.writeFileSync(path.join(here, 'prompts', r.claim_id + '.md'), tpl.replace(/\{\{(\w+)\}\}/g, (_, k) => String(r[k] ?? '')));
console.log(`inputs.json: ${inputs.length} tests; prompts/ written`);
