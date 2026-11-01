#!/usr/bin/env node
// Merge a round's forecasts into rounds/<round>/aggregate.json, rebuild history.json and
// FORECASTS.md (latest numbers, moves since the previous round, by-method roll-up, and Brier
// scores for rounds whose 30-day horizon has passed).
//
//   node problems/forecasts/build/merge.mjs [<round>] [--today 2026-12-01]
//
// Invalid forecast files are reported and left out. No dependencies (Node 20+).
import { existsSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { FORECASTS, ROUNDS, addDays, listRounds, loadApproaches, loadProblems, loadRuns, median, r3, readJson } from "./lib.mjs";
import { validateFile } from "./validate.mjs";

const argv = process.argv.slice(2);
const todayArg = argv.indexOf("--today");
const today = todayArg >= 0 ? argv[todayArg + 1] : new Date().toISOString().slice(0, 10);
const roundArg = argv.find(a => /^r\d+-/.test(a));
const rounds = listRounds();
const target = roundArg ?? rounds.at(-1);
if (!target) { console.error("no rounds; run build/queue.mjs first"); process.exit(1); }

const problems = new Map(loadProblems().map(p => [p.id, p]));
const approaches = new Map(loadApproaches().map(a => [a.id, a]));
const stat = xs => ({ median: r3(median(xs)), min: r3(Math.min(...xs)), max: r3(Math.max(...xs)) });

function loadForecasts(round) {
  const dir = join(ROUNDS, round, "forecasts");
  const out = [], rejected = [];
  for (const file of existsSync(dir) ? readdirSync(dir).filter(f => f.endsWith(".json")).sort() : []) {
    const v = validateFile(round, file);
    if (v.errors.length) { rejected.push({ file, errors: v.errors }); continue; }
    out.push(readJson(join(dir, file)));
  }
  return { forecasts: out, rejected };
}

function aggregate(round) {
  const meta = readJson(join(ROUNDS, round, "ROUND.json"));
  const { forecasts, rejected } = loadForecasts(round);
  const byProblem = new Map();
  for (const f of forecasts) for (const p of f.problems) {
    if (!byProblem.has(p.problem)) byProblem.set(p.problem, []);
    byProblem.get(p.problem).push({ model: f.model, ...p });
  }
  const rows = [];
  for (const [pid, list] of byProblem) {
    const aps = new Map();
    for (const p of list) for (const a of p.approaches) { if (!aps.has(a.approach)) aps.set(a.approach, []); aps.get(a.approach).push({ model: p.model, ...a }); }
    rows.push({
      problem: pid, n: list.length, models: list.map(p => p.model).sort(),
      p_solved_30d: stat(list.map(p => p.p_solved_30d)), p_solved_365d: stat(list.map(p => p.p_solved_365d)),
      approaches: [...aps].map(([id, xs]) => ({
        approach: id, kind: approaches.get(id)?.kind ?? null, proposer: approaches.get(id)?.model ?? null, n: xs.length,
        p_complete: stat(xs.map(x => x.p_complete)), p_settle: stat(xs.map(x => x.p_settle)),
        p_success: stat(xs.map(x => x.p_complete * x.p_settle)),
      })).sort((a, b) => b.p_success.median - a.p_success.median),
    });
  }
  rows.sort((a, b) => b.p_solved_365d.median - a.p_solved_365d.median);
  return {
    round, date: meta.date, previous_round: meta.previous_round, blind: meta.blind, generated: new Date().toISOString(),
    forecasters: [...new Set(forecasts.map(f => f.model))].sort(), files: forecasts.length, rejected, problems: rows,
  };
}

const agg = aggregate(target);
writeFileSync(join(ROUNDS, target, "aggregate.json"), JSON.stringify(agg, null, 1) + "\n");

// History across rounds (re-aggregate any round that has no aggregate yet).
const history = rounds.map(r => r === target ? agg : readJson(join(ROUNDS, r, "aggregate.json"), null) ?? aggregate(r)).filter(a => a.files > 0).map(a => ({
  round: a.round, date: a.date, forecasters: a.forecasters,
  problems: Object.fromEntries(a.problems.map(p => [p.problem, { p30: p.p_solved_30d.median, p365: p.p_solved_365d.median, spread365: r3(p.p_solved_365d.max - p.p_solved_365d.min) }])),
  approaches: Object.fromEntries(a.problems.flatMap(p => p.approaches.map(x => [x.approach, { complete: x.p_complete.median, settle: x.p_settle.median }]))),
}));
writeFileSync(join(FORECASTS, "history.json"), JSON.stringify({ rounds: history }, null, 1) + "\n");

// Scoring: a round is scored once date + 30 days has passed. Outcomes come from runs.json only.
const runs = loadRuns();
const brier = (p, o) => (p - o) ** 2;
const scores = [];
for (const r of rounds) {
  const a = r === target ? agg : readJson(join(ROUNDS, r, "aggregate.json"), null);
  const dir = join(ROUNDS, r, "forecasts");
  if (!a || !a.files || addDays(a.date, 30) > today) continue;
  const deadline = addDays(a.date, 30);
  const inWindow = runs.filter(x => x.date >= a.date && x.date <= deadline);
  const per = new Map();
  for (const file of readdirSync(dir).filter(f => f.endsWith(".json"))) {
    if (validateFile(r, file).errors.length) continue;
    const f = readJson(join(dir, file));
    const s = per.get(f.model) ?? { model: f.model, round: r, complete: [], settle: [], solved30: [] };
    for (const p of f.problems) {
      const solved = inWindow.some(x => x.solves_problem && (x.problem === p.problem || approaches.get(x.approach)?.problem === p.problem)) ? 1 : 0;
      s.solved30.push(brier(p.p_solved_30d, solved));
      for (const ap of p.approaches) {
        const done = inWindow.filter(x => x.approach === ap.approach && x.outcome === "completed");
        s.complete.push(brier(ap.p_complete, done.length ? 1 : 0));
        const st = done.find(x => x.settled === true || x.settled === false);
        if (st) s.settle.push(brier(ap.p_settle, st.settled ? 1 : 0));
      }
    }
    per.set(f.model, s);
  }
  const mean = xs => xs.length ? r3(xs.reduce((s, x) => s + x, 0) / xs.length) : null;
  for (const s of per.values()) scores.push({ model: s.model, round: r, deadline, brier_complete: mean(s.complete), n_complete: s.complete.length, brier_settle: mean(s.settle), n_settle: s.settle.length, brier_solved_30d: mean(s.solved30), n_problems: s.solved30.length });
}
writeFileSync(join(FORECASTS, "scores.json"), JSON.stringify({ today, note: "Brier score, lower is better; 0.25 is a forecast of 0.5 everywhere. Outcomes come only from runs.json inside each round's 30-day window.", scores }, null, 1) + "\n");

// FORECASTS.md
const prevAgg = agg.previous_round ? readJson(join(ROUNDS, agg.previous_round, "aggregate.json"), null) : null;
const prevP = new Map((prevAgg?.problems ?? []).map(p => [p.problem, p]));
const pct = x => `${Math.round(x * 100)}%`;
const rng = s => `${pct(s.median)} (${pct(s.min)}–${pct(s.max)})`;
const arrow = (now, was) => was == null ? "" : (d => d === 0 ? "=" : (d > 0 ? "+" : "") + Math.round(d * 100))(now - was);
const L = [];
L.push("# Open-problem forecasts", "");
L.push(`Built by \`node problems/forecasts/build/merge.mjs\`; do not edit. Round **${agg.round}** (${agg.date}${agg.blind ? ", blind" : `, prior ${agg.previous_round}`}), ${agg.forecasters.length} forecasters (${agg.forecasters.join(", ")}), ${agg.files} slice files.`, "");
L.push("Probabilities are medians across forecasters with the range in brackets. \"Solved\" means the problem's acceptance criteria are met or a falsifier is hit definitively, by logged artifacts. Nothing counts unless run and logged (`runs.json`, Lean reports, `test-data/claim-tests/`). Definitions: [INSTRUCTIONS.md](INSTRUCTIONS.md).", "");
if (agg.rejected.length) L.push(`Rejected files (fix and re-merge): ${agg.rejected.map(r => `\`${r.file}\``).join(", ")}`, "");
L.push("## Problems", "", "| Problem | Tier | Solved in 30 days | Δ | Solved in 365 days | Δ | Best approach (success = complete × settle) |", "|---|---|---|---|---|---|---|");
for (const p of agg.problems) {
  const pr = prevP.get(p.problem), top = p.approaches[0], t = problems.get(p.problem)?.tier ?? "";
  L.push(`| ${p.problem} | ${t} | ${rng(p.p_solved_30d)} | ${arrow(p.p_solved_30d.median, pr?.p_solved_30d.median)} | ${rng(p.p_solved_365d)} | ${arrow(p.p_solved_365d.median, pr?.p_solved_365d.median)} | ${top ? `${top.kind}, ${pct(top.p_success.median)} (${top.proposer} #${top.approach.split("--").pop()})` : ""} |`);
}
L.push("");
const sum = k => agg.problems.reduce((s, p) => s + p[k].median, 0);
L.push(`Expected problems solved (sum of medians): **${sum("p_solved_30d").toFixed(1)}** of ${agg.problems.length} in 30 days, **${sum("p_solved_365d").toFixed(1)}** in 365 days.`, "");

const kinds = new Map();
for (const p of agg.problems) for (const a of p.approaches) { const k = a.kind ?? "unknown"; if (!kinds.has(k)) kinds.set(k, []); kinds.get(k).push(a); }
L.push("## By method", "", "Mean over approaches of each kind, using medians across forecasters.", "", "| Kind | Approaches | Complete in 30 days | Settle if complete | Success | Best problem for this kind |", "|---|---|---|---|---|---|");
for (const [k, xs] of [...kinds].sort((a, b) => b[1].length - a[1].length)) {
  const m = f => xs.reduce((s, x) => s + f(x), 0) / xs.length;
  const best = xs.reduce((b, x) => x.p_success.median > b.p_success.median ? x : b);
  L.push(`| ${k} | ${xs.length} | ${pct(m(x => x.p_complete.median))} | ${pct(m(x => x.p_settle.median))} | ${pct(m(x => x.p_success.median))} | ${best.approach.split("--")[0]} (${pct(best.p_success.median)}) |`);
}
L.push("");

const moves = agg.problems.map(p => ({ id: p.problem, d30: prevP.has(p.problem) ? p.p_solved_30d.median - prevP.get(p.problem).p_solved_30d.median : null, d365: prevP.has(p.problem) ? p.p_solved_365d.median - prevP.get(p.problem).p_solved_365d.median : null })).filter(m => m.d365 != null && (Math.abs(m.d30) >= 0.03 || Math.abs(m.d365) >= 0.03)).sort((a, b) => Math.abs(b.d365) - Math.abs(a.d365));
if (prevAgg) {
  L.push(`## Moves since ${agg.previous_round}`, "");
  if (!moves.length) L.push("No problem moved by 3 points or more.", "");
  else { L.push("| Problem | 30 days | 365 days |", "|---|---|---|"); for (const m of moves) L.push(`| ${m.id} | ${arrow(m.d30, 0)} | ${arrow(m.d365, 0)} |`); L.push(""); }
}

const wide = agg.problems.filter(p => p.n > 1).sort((a, b) => (b.p_solved_365d.max - b.p_solved_365d.min) - (a.p_solved_365d.max - a.p_solved_365d.min)).slice(0, 5);
if (wide.length) { L.push("## Largest disagreements (365-day range)", ""); for (const p of wide) L.push(`- ${p.problem}: ${pct(p.p_solved_365d.min)}–${pct(p.p_solved_365d.max)}`); L.push(""); }

L.push("## Calibration", "");
if (!scores.length) L.push("No round has passed its 30-day horizon yet, so nothing is scored. Once one has, Brier scores per forecaster appear here (outcomes come only from `runs.json`).", "");
else {
  L.push("Brier score (lower is better; 0.25 = always 0.5). `complete` is the 30-day completion forecast per approach, `settle` the conditional settle forecast, `solved 30d` the per-problem forecast.", "", "| Forecaster | Round | complete | settle | solved 30d |", "|---|---|---|---|---|");
  for (const s of scores) L.push(`| ${s.model} | ${s.round} | ${s.brier_complete} (n=${s.n_complete}) | ${s.brier_settle ?? "-"} (n=${s.n_settle}) | ${s.brier_solved_30d} (n=${s.n_problems}) |`);
  L.push("");
}
writeFileSync(join(FORECASTS, "FORECASTS.md"), L.join("\n") + "\n");
console.log(`${target}: ${agg.files} files from ${agg.forecasters.length} forecasters, ${agg.problems.length} problems aggregated, ${agg.rejected.length} rejected; history ${history.length} rounds; ${scores.length} scored rows -> problems/forecasts/FORECASTS.md`);
for (const r of agg.rejected) console.log(`  rejected ${r.file}: ${r.errors.slice(0, 3).join("; ")}`);
