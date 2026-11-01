// Shared helpers for the forecast swarm: load problems, approaches, claim states and run logs.
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const FORECASTS = resolve(dirname(fileURLToPath(import.meta.url)), "..");
export const PROBLEMS = resolve(FORECASTS, "..");
export const REPO = resolve(PROBLEMS, "..");
export const ROUNDS = join(FORECASTS, "rounds");
export const HORIZONS = { complete_days: 30, short_days: 30, long_days: 365 };

export const readJson = (p, fallback = undefined) => {
  if (!existsSync(p)) { if (fallback !== undefined) return fallback; throw new Error(`missing ${p}`); }
  return JSON.parse(readFileSync(p, "utf8"));
};

export const loadProblems = () => readJson(join(PROBLEMS, "problems.json")).problems;

// Approaches from approaches/*.json and approaches/pending/*.json (pending = proposed, not yet nanopubs).
export function loadApproaches() {
  const out = [];
  for (const [dir, pending] of [[join(PROBLEMS, "approaches"), false], [join(PROBLEMS, "approaches", "pending"), true]]) {
    if (!existsSync(dir)) continue;
    for (const f of readdirSync(dir).filter(f => f.endsWith(".json")).sort()) {
      const a = readJson(join(dir, f));
      for (const ap of a.approaches ?? []) out.push({ id: `${ap.problem}--${a.model}--${ap.n}`, model: a.model, pending, ...ap });
    }
  }
  const seen = new Set();
  return out.filter(a => !seen.has(a.id) && seen.add(a.id));
}

export const loadClaims = () => {
  const c = readJson(join(REPO, "docs", "claims.json"));
  return new Map((c.claims ?? c).map(x => [x.id, x]));
};

export const claimState = c => c && {
  id: c.id, label: c.label, status: c.status, proof: c.proof ?? null, theorem: !!c.theorem,
  evidence: c.evidence ?? null,
  data_test: c.data_test ? { verdict: c.data_test.verdict, confidence: c.data_test.confidence, data_kind: c.data_test.data_kind, preregistered: c.data_test.preregistered, path: c.data_test.path } : null,
};

// Run log: what the swarm has actually attempted. An approach counts only when run and logged here.
export const loadRuns = () => readJson(join(FORECASTS, "runs.json"), { runs: [] }).runs;

export const listRounds = () => existsSync(ROUNDS) ? readdirSync(ROUNDS).filter(d => /^r\d+-/.test(d)).sort((a, b) => parseInt(a.slice(1)) - parseInt(b.slice(1))) : [];

export const median = xs => { const s = [...xs].sort((a, b) => a - b); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : null; };
export const r3 = x => x == null ? null : Math.round(x * 1000) / 1000;
export const addDays = (iso, d) => new Date(Date.parse(iso) + d * 864e5).toISOString().slice(0, 10);
