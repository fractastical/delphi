#!/usr/bin/env node
// Open a forecast round: snapshot the evidence, diff it against the previous round, attach the
// previous round's aggregate as the prior, and cut the problems into slices for forecasters.
//
//   node problems/forecasts/build/queue.mjs [--per-slice 9] [--date 2026-11-01]
//
// Writes problems/forecasts/rounds/r<N>-<date>/{ROUND.json,snapshot.json,queue/slice-NN.json}.
// Needs docs/claims.json (node scripts/site/build-claim-graph.mjs). No dependencies (Node 20+).
import { execSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { HORIZONS, REPO, ROUNDS, claimState, listRounds, loadApproaches, loadClaims, loadProblems, loadRuns, readJson } from "./lib.mjs";

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) => a.startsWith("--") ? [a.slice(2), all[i + 1]] : []).filter(x => x.length));
const perSlice = Number(args["per-slice"] ?? 9);
const date = args.date ?? new Date().toISOString().slice(0, 10);

const rounds = listRounds();
const n = rounds.length + 1;
const id = `r${n}-${date}`;
const prev = rounds.at(-1);
const prevSnap = prev ? readJson(join(ROUNDS, prev, "snapshot.json")) : null;
const prevAgg = prev ? readJson(join(ROUNDS, prev, "aggregate.json"), null) : null;

const claims = loadClaims();
const approaches = loadApproaches();
const runs = loadRuns();
const problems = loadProblems();

const git = cmd => { try { return execSync(cmd, { cwd: REPO, encoding: "utf8" }).trim(); } catch { return null; } };

const snapshot = {
  round: id, date, commit: git("git rev-parse HEAD"), dirty: !!git("git status --porcelain -- problems claim-sources test-data docs/claims.json"),
  problems: Object.fromEntries(problems.map(p => [p.id, {
    claims: p.related_claims.map(c => claimState(claims.get(c))).filter(Boolean),
    runs: runs.filter(r => r.problem === p.id || approaches.find(a => a.id === r.approach)?.problem === p.id),
    approaches: approaches.filter(a => a.problem === p.id).map(a => a.id),
  }])),
};

// What changed since the previous round, per problem.
const changes = {};
for (const p of problems) {
  const now = snapshot.problems[p.id], was = prevSnap?.problems?.[p.id];
  if (!was) { changes[p.id] = prevSnap ? ["new problem since last round"] : []; continue; }
  const out = [];
  const wasClaim = new Map(was.claims.map(c => [c.id, c]));
  for (const c of now.claims) {
    const w = wasClaim.get(c.id);
    if (!w) { out.push(`claim ${c.id} added`); continue; }
    for (const k of ["status", "proof", "theorem", "evidence"]) if (JSON.stringify(w[k]) !== JSON.stringify(c[k])) out.push(`claim ${c.id}: ${k} ${JSON.stringify(w[k])} -> ${JSON.stringify(c[k])}`);
    if (JSON.stringify(w.data_test) !== JSON.stringify(c.data_test)) out.push(`claim ${c.id}: data_test ${w.data_test?.verdict ?? "none"} -> ${c.data_test?.verdict ?? "none"}`);
  }
  const wasRuns = new Set(was.runs.map(r => JSON.stringify(r)));
  for (const r of now.runs) if (!wasRuns.has(JSON.stringify(r))) out.push(`run logged: ${r.approach} ${r.outcome}${r.settled === true ? " (settled)" : r.settled === false ? " (did not settle)" : ""}: ${r.note ?? ""}`.trim());
  const wasAp = new Set(was.approaches);
  for (const a of now.approaches) if (!wasAp.has(a)) out.push(`approach added: ${a}`);
  changes[p.id] = out;
}

const priorOf = pid => prevAgg?.problems?.find(p => p.problem === pid) ?? null;
const slim = p => {
  const pr = priorOf(p.id);
  return {
    id: p.id, title: p.title, field: p.field, tier: p.tier, question: p.question, known_state: p.known_state,
    acceptance_criteria: p.acceptance_criteria, falsifiers: p.falsifiers, required_capabilities: p.required_capabilities, data_access: p.data_access,
    related_claims: snapshot.problems[p.id].claims,
    runs_logged: snapshot.problems[p.id].runs,
    changes_since_last_round: changes[p.id],
    prior: pr && { p_solved_30d: pr.p_solved_30d.median, p_solved_365d: pr.p_solved_365d.median, forecasters: pr.n },
    approaches: approaches.filter(a => a.problem === p.id).map(a => {
      const pa = pr?.approaches?.find(x => x.approach === a.id);
      return {
        id: a.id, proposer: a.model, title: a.title, kind: a.kind, method: a.method, steps: a.steps, decisive_result: a.decisive_result,
        failure_signature: a.failure_signature, tools: a.tools, proposer_difficulty: a.difficulty, missing: a.missing ?? null,
        prior: pa && { p_complete: pa.p_complete.median, p_settle: pa.p_settle.median },
      };
    }),
  };
};

const dir = join(ROUNDS, id);
mkdirSync(join(dir, "queue"), { recursive: true });
mkdirSync(join(dir, "forecasts"), { recursive: true });
const slices = [];
for (let i = 0; i < problems.length; i += perSlice) slices.push(problems.slice(i, i + perSlice));
const sliceIds = slices.map((s, i) => `slice-${String(i + 1).padStart(2, "0")}`);
slices.forEach((s, i) => writeFileSync(join(dir, "queue", `${sliceIds[i]}.json`), JSON.stringify({
  round: id, slice: sliceIds[i], date, horizons: HORIZONS, blind: !prev, previous_round: prev ?? null, problems: s.map(slim),
}, null, 1) + "\n"));
writeFileSync(join(dir, "snapshot.json"), JSON.stringify(snapshot, null, 1) + "\n");
writeFileSync(join(dir, "ROUND.json"), JSON.stringify({
  round: id, n, date, opened: new Date().toISOString(), previous_round: prev ?? null, blind: !prev, commit: snapshot.commit, slices: sliceIds,
  problems: problems.length, approaches: approaches.length, horizons: HORIZONS,
}, null, 1) + "\n");
console.log(`${id}: ${problems.length} problems, ${approaches.length} approaches, ${sliceIds.length} slices; ${prev ? `prior = ${prev}` : "blind (no prior round)"}`);
console.log(`changed problems since ${prev ?? "start"}: ${Object.values(changes).filter(c => c.length).length}`);
