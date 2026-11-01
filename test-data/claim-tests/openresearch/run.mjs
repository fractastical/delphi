#!/usr/bin/env node
// OpenResearch literature grounding for headline claim tests (issue #16; AGENTS.md role A2 requirement).
// Runs the official alphaXiv OpenResearch CLI (`orx discover <source> <query>`) for each claim, logs the exact
// command, the CLI version and the UTC time of every call, and stores the returned records verbatim in
// test-data/claim-tests/<project>/<dir>/openresearch.json. `orx discover` is a retrieval primitive with no run or
// experiment identifier of its own; what is recorded is the real command and its real output, nothing else.
// The `assessment` block of each file is written by hand afterwards from the returned records only.
//   node test-data/claim-tests/openresearch/run.mjs [--orx <path to orx>] [--only <claim_id>]
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '../../..');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const orx = arg('orx', path.join(os.homedir(), '.cargo', 'bin', 'orx'));
const only = arg('only');

export const QUERIES = {
  'kimura-heterozygosity': { dir: 'math-bio-theorems/kimura-heterozygosity', queries: [
    ['openalex', "Lewontin's paradox nucleotide diversity census population size across species"],
    ['pubmed', 'genetic diversity census population size correlation across animal species'],
  ] },
  'thompson1917-ch03-07': { dir: 'thompson-growth-form/thompson1917-ch03-07--delphi-claims', queries: [
    ['openalex', 'weight height power law exponent children growth allometry body mass'],
    ['pubmed', 'weight for height power exponent children allometric Benn index'],
    ['openalex', 'weight height relationship children power of height exponent Cole Benn index adiposity'],
  ] },
  'maynardsmith-hitchhiking': { dir: 'math-bio-theorems/maynardsmith-hitchhiking', queries: [
    ['openalex', 'correlation between nucleotide diversity and recombination rate human genome hitchhiking background selection'],
    ['pubmed', 'recombination rate nucleotide diversity correlation human genome linked selection'],
    ['openalex', 'levels of naturally occurring DNA polymorphism correlate with recombination rates Begun Aquadro'],
  ] },
  'darwin1859-ch09-03': { dir: 'darwin-origin/darwin1859-ch09-03--delphi-claims', queries: [
    ['openalex', 'Darwin denudation of the Weald 300 million years Phillips age of the Earth geological time'],
    ['openalex', 'Cretaceous Paleogene boundary age 66 Ma geochronology Maastrichtian'],
  ] },
  'thompson1917-ch04-13': { dir: 'thompson-growth-form/thompson1917-ch04-13--delphi-claims', queries: [
    ['openalex', 'distribution of chromosome numbers across plant species polyploidy haploid number'],
    ['pubmed', 'chromosome number distribution angiosperms polyploidy frequency'],
  ] },
  'darwin1859-ch11-13': { dir: 'darwin-origin/darwin1859-ch11-13--delphi-claims', queries: [
    ['openalex', 'Pleistocene glacial cycles benthic oxygen isotope stack Antarctic temperature interhemispheric synchrony'],
    ['pubmed', 'glacial cycles duration Pleistocene benthic d18O stack 5.3 million years'],
    ['openalex', 'Pliocene-Pleistocene stack of 57 globally distributed benthic d18O records Lisiecki Raymo'],
  ] },
};

import { pathToFileURL } from 'node:url';
const isMain = process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href;
const version = isMain ? spawnSync(orx, ['--no-telemetry', '--version'], { encoding: 'utf8' }).stdout.trim() : '';
for (const [claim_id, spec] of Object.entries(isMain ? QUERIES : {})) {
  if (only && claim_id !== only) continue;
  const outPath = path.join(root, 'test-data', 'claim-tests', spec.dir, 'openresearch.json');
  const prev = fs.existsSync(outPath) ? JSON.parse(fs.readFileSync(outPath, 'utf8')) : {};
  const runs = [];
  for (const [source, query] of spec.queries) {
    const args = ['--no-telemetry', 'discover', source, query, '--limit', '10'];
    const t = new Date().toISOString();
    const r = spawnSync(orx, args, { encoding: 'utf8', maxBuffer: 32 * 1024 * 1024, timeout: 180000 });
    let results = null, error = null;
    try { results = JSON.parse(r.stdout); } catch { error = (r.stderr || r.stdout || '').slice(0, 500) || 'no JSON output'; }
    runs.push({ command: `orx ${args.map(a => /\s/.test(a) ? JSON.stringify(a) : a).join(' ')}`, source, query, at: t, exit_code: r.status,
                n_results: results ? results.length : 0, error,
                results: (results || []).map(x => ({ source: x.source, id: x.id, title: x.title, publicationDate: x.publicationDate, citations: x.citations,
                                                     abstract: (x.abstract || '').slice(0, 1200) })) });
    process.stdout.write(`${claim_id} ${source}: ${results ? results.length + ' results' : 'ERROR ' + error}\n`);
  }
  const out = { claim_id, tool: 'OpenResearch CLI (alphaXiv) `orx discover`', cli_version: version, run_identifier: null,
                run_identifier_note: '`orx discover` is a stateless retrieval primitive; it issues no run or experiment id. The command, time and returned records are the record.',
                runs, assessment: prev.assessment || { status: 'pending', what_the_literature_says: null, already_answered_by_prior_work: null, citation: null, implication_for_this_test: null } };
  fs.writeFileSync(outPath, JSON.stringify(out, null, 1) + '\n');
}
