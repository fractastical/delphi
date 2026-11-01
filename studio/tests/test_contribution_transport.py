"""Browser contribution transport: explicit credentials, no session authority."""
from pathlib import Path
import subprocess


def test_contribution_credentials_are_explicit_transient_and_never_redirected():
    root = Path(__file__).resolve().parents[1]
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
global.window = {DF: {}};
const failStorage = () => { throw Error('credential storage is forbidden'); };
global.localStorage = {getItem: failStorage, setItem: failStorage};
global.sessionStorage = {getItem: failStorage, setItem: failStorage};
vm.runInThisContext(fs.readFileSync('site/js/adapters.js', 'utf8'));
const api = window.DF.api;
api.state.mode = 'live'; api.state.publicAccess = true;
const marker = 'fixture-contributor-' + 'x'.repeat(40);
const principal = {actor: 'fixture-author', roles: ['contributor'], namespaces: ['fixture']};
const calls = [];
global.fetch = async (path, opts) => {
  calls.push({path, opts});
  return {ok:true, status:200, json:async()=> path.endsWith('identity') ? {principal} : {local_status:'proposed'}};
};
(async () => {
  await assert.rejects(api.identity(), /Connect a contributor/);
  await assert.rejects(api.propose({kind:'Annotation'}, 'draft-1'), /Connect a contributor/);
  assert.equal(calls.length, 0);
  assert.deepEqual(await api.connectContributor(marker), {principal});
  assert.equal(api.hasContributor(), true);
  assert.deepEqual(await api.propose({kind:'Annotation', issuer:principal.actor}, 'draft-1'), {local_status:'proposed'});
  assert.equal(calls[0].path, '/v1/read/identity');
  assert.equal(calls[0].opts.body, '{}');
  const write = calls[1];
  assert.equal(write.path, '/v1/proposals');
  assert.equal(write.opts.headers['Idempotency-Key'], 'draft-1');
  assert.equal(write.opts.headers.Authorization, 'Bearer ' + marker);
  assert.equal(write.opts.credentials, 'omit');
  assert.equal(write.opts.redirect, 'error');
  assert.equal(write.opts.cache, 'no-store');
  assert(!JSON.stringify(api.state).includes(marker));
  assert(!write.path.includes(marker) && !write.opts.body.includes(marker));
  assert.equal(JSON.parse(write.opts.body).draft.issuer, principal.actor);
  api.disconnectContributor();
  assert.equal(api.hasContributor(), false);
  await assert.rejects(api.identity(), /Connect a contributor/);
  let finish;
  global.fetch = () => new Promise(resolve => { finish = resolve; });
  const pending = api.connectContributor(marker);
  api.disconnectContributor();
  finish({ok:true, json:async()=>({principal})});
  await assert.rejects(pending, /cancelled/);
  assert.equal(api.hasContributor(), false);
  global.fetch = async () => ({ok:false, status:401, json:async()=>({secret:marker})});
  await assert.rejects(api.connectContributor(marker), {message:'Contributor request refused (HTTP 401).'});
  assert.equal(api.hasContributor(), false);
  await assert.rejects(api.propose({kind:'Claim'}, 'draft-2'), /Annotation/);
  await assert.rejects(api.propose({kind:'Annotation'}, ''), /idempotency/);
})().catch(e => {console.error(e); process.exitCode = 1;});
"""
    completed = subprocess.run(
        ["node", "-e", script], cwd=root, capture_output=True, text=True, timeout=20
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
