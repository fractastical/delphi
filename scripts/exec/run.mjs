#!/usr/bin/env node
// Re-runs the entries in scripts/exec/manifest.json and reports, per claim, whether the committed result
// still comes out: reproduced, drifted, failed, unverified (ran but printed nothing comparable)
// or skipped. Files a data test writes are restored afterwards unless --update is given.
//
// Usage: node scripts/exec/run.mjs [--kind lean|data] [--project P] [--claim ID ...] [--offline]
//                          [--update] [--jobs N] [--timeout S] [--rtol X] [--list]

import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { cpSync, existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(dirname(HERE));
const RUNS = join(HERE, "runs");
const LOGS = join(RUNS, "logs");
const STD_AXIOMS = new Set(["propext", "Classical.choice", "Quot.sound"]);
const WALL_CLOCK = /(^|[._])(seconds|secs|elapsed|runtime|duration|wall_?time|timing)s?($|[._[])/i;
// Sizes of fetched files change with upstream re-exports and HTTP metadata; they are provenance, not measurement.
const FETCH_METADATA = /(^|[._\]])(byte_size|bytes|size_bytes|content_length|n_bytes)$/i;
const PY_DEPS = ["numpy", "scipy", "pandas", "requests", "biopython", "pillow", "openpyxl", "pdfplumber"];

const args = process.argv.slice(2);
const opt = { claims: [], jobs: 1, rtol: 1e-6, atol: 1e-9 };
for (let i = 0; i < args.length; i++) {
  const a = args[i];
  if (a === "--kind") opt.kind = args[++i];
  else if (a === "--project") opt.project = args[++i];
  else if (a === "--claim") opt.claims.push(args[++i]);
  else if (a === "--offline") opt.offline = true;
  else if (a === "--update") opt.update = true;
  else if (a === "--list") opt.list = true;
  else if (a === "--jobs") opt.jobs = Number(args[++i]);
  else if (a === "--timeout") opt.timeout = Number(args[++i]);
  else if (a === "--rtol") opt.rtol = Number(args[++i]);
  else throw new Error(`unknown argument ${a}`);
}

const manifestPath = join(HERE, "manifest.json");
if (!existsSync(manifestPath)) throw new Error("scripts/exec/manifest.json missing; run node scripts/exec/build-manifest.mjs");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const selected = manifest.entries.filter(
  (e) =>
    (!opt.kind || e.kind === opt.kind) &&
    (!opt.project || e.project === opt.project) &&
    (!opt.claims.length || opt.claims.includes(e.claim_id)),
);

if (opt.list) {
  for (const e of selected)
    console.log(`${e.id.padEnd(34)} ${e.kind === "data" ? (e.runnable ? (e.network ? "net " : "local") : "none ") : "lean "} ${e.label ?? ""}`);
  process.exit(0);
}

const sha256 = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");
const readJsonMaybe = (p) => {
  try {
    return JSON.parse(readFileSync(p, "utf8"));
  } catch {
    return null;
  }
};
const hasUv = spawnSync("uv", ["--version"]).status === 0;

function exec(cmd, cwd, timeoutS) {
  return new Promise((resolve) => {
    const started = Date.now();
    const child = spawn(cmd[0], cmd.slice(1), { cwd, env: { ...process.env, PYTHONUNBUFFERED: "1", MPLBACKEND: "Agg" } });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, timeoutS * 1000);
    child.on("error", (e) => (err += String(e)));
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ code: timedOut ? null : code, timedOut, out, err, seconds: (Date.now() - started) / 1000 });
    });
  });
}

function scriptCmd(script, cwd) {
  if (script.endsWith(".mjs")) return ["node", script];
  if (!hasUv) return ["python3", script];
  const text = readFileSync(join(cwd, script), "utf8");
  if (/^# \/\/\/ script/m.test(text)) return ["uv", "run", "--quiet", "--script", script];
  return ["uv", "run", "--quiet", "--no-project", ...PY_DEPS.flatMap((d) => ["--with", d]), "python", script];
}

// ---- comparison of numeric outputs -------------------------------------------------------

function leaves(x, path = "", out = new Map()) {
  if (typeof x === "number" || typeof x === "boolean") out.set(path, x);
  else if (Array.isArray(x)) x.forEach((v, i) => leaves(v, `${path}[${i}]`, out));
  else if (x && typeof x === "object") for (const [k, v] of Object.entries(x)) leaves(v, path ? `${path}.${k}` : k, out);
  return out;
}

function compare(before, after, ignore) {
  const a = leaves(before);
  const b = leaves(after);
  const mismatches = [];
  let compared = 0;
  for (const [k, v] of a) {
    if (!b.has(k) || WALL_CLOCK.test(k) || FETCH_METADATA.test(k) || ignore?.test(k)) continue;
    compared++;
    const w = b.get(k);
    const same = typeof v === "number" && typeof w === "number" ? Math.abs(v - w) <= opt.atol + opt.rtol * Math.abs(v) : v === w;
    if (!same) mismatches.push({ path: k, committed: v, now: w });
  }
  return { compared, mismatches };
}

function lastJson(text) {
  const lines = text.split("\n");
  const starts = [];
  const ends = [];
  lines.forEach((l, i) => {
    if (/^[{[]/.test(l)) starts.push(i);
    if (/^[}\]]\s*$/.test(l) || /^[{[].*[}\]]\s*$/.test(l)) ends.push(i);
  });
  for (const s of starts)
    for (const e of [...ends].reverse()) {
      if (e < s) break;
      try {
        return JSON.parse(lines.slice(s, e + 1).join("\n"));
      } catch {}
    }
  return null;
}

function findVerdict(x) {
  if (!x || typeof x !== "object") return null;
  for (const k of ["verdict", "verdict_by_rule", "verdict_by_prereg_rule"])
    if (typeof x[k] === "string" && /^(supports|refutes|mixed|inconclusive)$/.test(x[k])) return x[k];
  for (const v of Object.values(x)) {
    const found = findVerdict(v);
    if (found) return found;
  }
  return null;
}

// ---- data tests --------------------------------------------------------------------------

async function runData(e) {
  if (!e.runnable) return { status: "skipped", reason: e.why_not };
  if (opt.offline && e.network) return { status: "skipped", reason: "needs network (--offline)" };

  const dir = join(ROOT, e.dir);
  const resultPath = join(dir, "result.json");
  const measuredPath = join(dir, "derived", "measured.json");
  const committed = readJsonMaybe(resultPath);
  const committedMeasured = readJsonMaybe(measuredPath);
  const scriptChanged = e.steps.some((s) => s.cwd === e.dir && /^analysis\./.test(s.script)) && e.script_sha256 && sha256(join(dir, e.steps.at(-1).script)) !== e.script_sha256;

  const backup = mkdtempSync(join(tmpdir(), "delphi-exec-"));
  const saved = [];
  for (const [i, w] of e.writes.entries()) {
    const p = join(ROOT, w);
    if (existsSync(p)) {
      cpSync(p, join(backup, String(i)), { recursive: true });
      saved.push([p, join(backup, String(i))]);
    }
  }

  const started = Date.now();
  let stdout = "";
  let log = "";
  let failure = null;
  for (const step of e.steps) {
    const cwd = join(ROOT, step.cwd);
    const cmd = scriptCmd(step.script, cwd);
    const r = await exec(cmd, cwd, opt.timeout ?? e.timeout_s);
    stdout = r.out;
    log += `$ (cd ${step.cwd} && ${cmd.join(" ")})  [${r.seconds.toFixed(1)} s, exit ${r.code}]\n${r.out}\n--- stderr ---\n${r.err}\n`;
    if (r.timedOut || r.code !== 0) {
      failure = r.timedOut ? `timeout after ${opt.timeout ?? e.timeout_s} s` : `exit ${r.code}: ${r.err.trim().split("\n").at(-1) ?? ""}`;
      break;
    }
  }
  const seconds = (Date.now() - started) / 1000;
  const logPath = join(LOGS, `${e.id.replace(/[:/]/g, "_")}.log`);
  writeFileSync(logPath, log);

  const out = { seconds, log: logPath.slice(ROOT.length + 1), ...(scriptChanged ? { script_changed_since_manifest: true } : {}) };
  if (failure) {
    restore(saved, backup);
    return { status: "failed", reason: failure, ...out };
  }

  const rewritten = (p) => existsSync(p) && statSync(p).mtimeMs >= started;
  const fresh = rewritten(resultPath) ? readJsonMaybe(resultPath) : null;
  const printed = lastJson(stdout);
  const ignore = e.ignore ? new RegExp(e.ignore) : null;

  const checks = [];
  const add = (source, before, after) => {
    if (before == null || after == null) return;
    const c = compare(before, after, ignore);
    if (c.compared) checks.push({ source, ...c });
  };
  if (fresh) add("result.json", committed?.measured, fresh.measured);
  const derivedDir = join(dir, "derived");
  const derivedBackup = saved.find(([p]) => p === derivedDir)?.[1];
  const freshDerived = existsSync(derivedDir) ? readdirSync(derivedDir).filter((f) => f.endsWith(".json") && rewritten(join(derivedDir, f))) : [];
  for (const f of freshDerived) {
    const before = derivedBackup && existsSync(join(derivedBackup, f)) ? readJsonMaybe(join(derivedBackup, f)) : f === "measured.json" ? committed?.measured : null;
    add(`derived/${f}`, before, readJsonMaybe(join(derivedDir, f)));
  }
  if (printed) {
    const p = printed.measured ?? printed;
    const options = [committed?.measured, committed?.measured?.extra, committedMeasured?.measured ?? committedMeasured].filter(Boolean);
    const best = options.map((o) => compare(o, p, ignore)).sort((x, y) => y.compared - x.compared)[0];
    if (best?.compared) checks.push({ source: "stdout", ...best });
  }

  const nowVerdict = fresh?.verdict || findVerdict(rewritten(measuredPath) ? readJsonMaybe(measuredPath) : null) || findVerdict(printed);
  const expectedVerdict = e.script_verdict ?? committed?.verdict;
  const verdictChanged = nowVerdict && expectedVerdict && nowVerdict !== expectedVerdict;

  if (opt.update) {
    rmSync(backup, { recursive: true, force: true });
  } else restore(saved, backup);

  const compared = checks.reduce((s, c) => s + c.compared, 0);
  const mismatches = checks.flatMap((c) => c.mismatches.map((m) => ({ source: c.source, ...m })));
  const status = verdictChanged || mismatches.length ? "drifted" : compared ? "reproduced" : "unverified";
  return {
    status,
    verdict: { committed: committed?.verdict ?? null, now: nowVerdict ?? null, ...(e.script_verdict ? { script_expected: e.script_verdict } : {}) },
    compared,
    sources: checks.map((c) => c.source),
    ...(mismatches.length ? { mismatches: mismatches.slice(0, 10), mismatch_count: mismatches.length } : {}),
    ...(status === "unverified" ? { reason: "script ran but wrote no result.json, derived/measured.json or JSON on stdout to compare" } : {}),
    ...out,
  };
}

function restore(saved, backup) {
  for (const [p, b] of saved) {
    rmSync(p, { recursive: true, force: true });
    cpSync(b, p, { recursive: true });
  }
  rmSync(backup, { recursive: true, force: true });
}

// ---- Lean --------------------------------------------------------------------------------

async function runLeanModule(entries) {
  const { cwd, source, module } = entries[0];
  const src = readFileSync(join(ROOT, source), "utf8");
  const srcLines = src.split("\n").length;
  const theorems = [...new Set(entries.flatMap((e) => e.theorems))];
  const forbidden = [...src.replace(/--.*$/gm, "").replace(/\/-[\s\S]*?-\//g, "").matchAll(/\b(sorry|admit|native_decide|axiom|unsafe|opaque)\b/g)].map((m) => m[1]);

  const dir = mkdtempSync(join(tmpdir(), "delphi-lean-"));
  const file = join(dir, `${module.split(".").at(-1)}.lean`);
  writeFileSync(file, `${src}\n${theorems.map((t) => `#print axioms ${t}`).join("\n")}\n`);
  const r = await exec(["lake", "env", "lean", file], join(ROOT, cwd), opt.timeout ?? 1800);
  rmSync(dir, { recursive: true, force: true });
  const text = `${r.out}\n${r.err}`;
  const logPath = join(LOGS, `lean_${module}.log`);
  writeFileSync(logPath, text);

  const errors = [...text.matchAll(/:(\d+):\d+: error: ([^\n]*)/g)].map((m) => ({ line: Number(m[1]), msg: m[2] }));
  const sorryWarning = /declaration uses 'sorry'/.test(text);
  const axioms = new Map();
  for (const m of text.matchAll(/'([^']+)' depends on axioms: \[([^\]]*)\]/g)) axioms.set(m[1], m[2].split(",").map((s) => s.trim()).filter(Boolean));
  for (const m of text.matchAll(/'([^']+)' does not depend on any axioms/g)) axioms.set(m[1], []);
  const sourceErrors = errors.filter((x) => x.line <= srcLines);
  const printErrors = new Map(errors.filter((x) => x.line > srcLines).map((x) => [theorems[x.line - srcLines - 1], x.msg]));

  const common = { seconds: r.seconds, log: logPath.slice(ROOT.length + 1) };
  return entries.map((e) => {
    const changed = e.source_sha256 && sha256(join(ROOT, e.source)) !== e.source_sha256 ? { source_changed_since_manifest: true } : {};
    if (r.timedOut) return { status: "failed", reason: "timeout", ...common, ...changed };
    if (sourceErrors.length) return { status: "failed", reason: `module does not compile: ${sourceErrors[0].msg}`, error_count: sourceErrors.length, ...common, ...changed };
    if (sorryWarning || forbidden.length) return { status: "failed", reason: `module uses ${forbidden[0] ?? "sorry"}`, ...common, ...changed };
    const problems = [];
    const per = {};
    for (const t of e.theorems) {
      if (printErrors.has(t)) problems.push(`${t}: ${printErrors.get(t)}`);
      else if (!axioms.has(t)) problems.push(`${t}: no axiom report`);
      else {
        per[t] = axioms.get(t);
        const extra = per[t].filter((a) => !STD_AXIOMS.has(a));
        if (extra.length) problems.push(`${t}: non-standard axioms ${extra.join(", ")}`);
      }
    }
    if (!e.theorems.length) problems.push("report lists no theorems");
    return problems.length
      ? { status: "failed", reason: problems.join("; "), axioms: per, ...common, ...changed }
      : { status: "reproduced", axioms: per, ...common, ...changed };
  });
}

// ---- main --------------------------------------------------------------------------------

mkdirSync(LOGS, { recursive: true });
const results = new Map();
const report = (e, r) => {
  results.set(e.id, r);
  const detail = r.reason ?? (r.mismatches ? `${r.mismatch_count} numbers differ, e.g. ${r.mismatches[0].path}: ${r.mismatches[0].committed} -> ${r.mismatches[0].now}` : r.verdict ? `verdict ${r.verdict.committed}${r.verdict.script_expected ? ` (script rule: ${r.verdict.now})` : r.verdict.now && r.verdict.now !== r.verdict.committed ? ` -> ${r.verdict.now}` : ""}, ${r.compared} numbers checked` : "");
  console.log(`${r.status.padEnd(10)} ${e.id.padEnd(34)} ${r.seconds != null ? `${r.seconds.toFixed(0).padStart(4)} s ` : "       "}${detail}`);
};

const lean = selected.filter((e) => e.kind === "lean");
const byModule = Map.groupBy(lean, (e) => e.source);
for (const group of byModule.values()) {
  console.log(`checking ${group[0].module} (${group.length} claims)...`);
  const rs = await runLeanModule(group);
  group.forEach((e, i) => report(e, rs[i]));
}

const data = selected.filter((e) => e.kind === "data");
const queue = [...data];
const sharedWrites = new Set();
await Promise.all(
  Array.from({ length: Math.max(1, opt.jobs) }, async () => {
    while (queue.length) {
      const i = queue.findIndex((e) => !e.writes.some((w) => sharedWrites.has(w)));
      if (i < 0) {
        await new Promise((r) => setTimeout(r, 500));
        continue;
      }
      const [e] = queue.splice(i, 1);
      e.writes.forEach((w) => sharedWrites.add(w));
      report(e, await runData(e));
      e.writes.forEach((w) => sharedWrites.delete(w));
    }
  }),
);

const ordered = selected.map((e) => ({ id: e.id, claim_id: e.claim_id, kind: e.kind, ...results.get(e.id) }));
const tally = Object.groupBy(ordered, (r) => r.status);
const summary = Object.fromEntries(Object.entries(tally).map(([k, v]) => [k, v.length]));
const run = {
  ran_at: new Date().toISOString(),
  manifest_built: manifest.built,
  options: { ...opt, claims: opt.claims.length ? opt.claims : undefined },
  summary,
  results: ordered,
};
const stamp = run.ran_at.replace(/[:.]/g, "-");
writeFileSync(join(RUNS, `${stamp}.json`), JSON.stringify(run, null, 2) + "\n");
writeFileSync(join(RUNS, "latest.json"), JSON.stringify(run, null, 2) + "\n");
console.log(`\n${JSON.stringify(summary)}  ->  scripts/exec/runs/${stamp}.json`);
process.exit(tally.failed?.length || tally.drifted?.length ? 1 : 0);
