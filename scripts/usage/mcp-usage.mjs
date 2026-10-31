#!/usr/bin/env node
// Daily usage of the hosted MCP server, saved to mcp/usage/<YYYY-MM-DD>.json. The server's counters
// (mcp/metrics.mjs) reset on every deploy and Fly's managed Prometheus only keeps them for a while,
// so this pulls the raw scraped samples for each UTC day and stores the totals in the repo.
//
//   npm run mcp:usage [-- 2026-10-31 ...] [-- --days 7]
//
// Defaults to today (partial until midnight UTC; rerunning overwrites). Needs the fly CLI logged in,
// or FLY_API_TOKEN. FLY_ORG defaults to "personal", FLY_APP to "delphisci-mcp".
import { mkdirSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const OUT = join(ROOT, "mcp/usage");
const APP = process.env.FLY_APP ?? "delphisci-mcp";
const ORG = process.env.FLY_ORG ?? "personal";
const DAY = 86400;

const fly = (...args) => execFileSync("fly", args, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
const token = process.env.FLY_API_TOKEN ?? fly("auth", "token").trim().split("\n").at(-1);
const iso = t => new Date(t * 1000).toISOString().slice(0, 19) + "Z";

const args = process.argv.slice(2);
const today = Math.floor(Date.now() / 1000 / DAY) * DAY;
let days = args.filter(a => /^\d{4}-\d{2}-\d{2}$/.test(a)).map(d => Date.parse(`${d}T00:00:00Z`) / 1000);
const n = args.includes("--days") ? Number(args[args.indexOf("--days") + 1]) : 0;
if (n) days = Array.from({ length: n }, (_, i) => today - (n - 1 - i) * DAY);
if (!days.length) days = [today];

// Deploys restart the process and reset every counter, even when the new value is not lower.
const releases = JSON.parse(fly("releases", "-a", APP, "--json"))
  .map(r => ({ version: r.Version ?? r.version, at: Date.parse(r.CreatedAt ?? r.createdAt) / 1000 }))
  .sort((a, b) => a.at - b.at);

async function samples(metric, end, seconds) {
  const url = `https://api.fly.io/prometheus/${ORG}/api/v1/query`;
  const body = new URLSearchParams({ query: `${metric}{app="${APP}"}[${seconds}s]`, time: String(end) });
  const res = await fetch(url, { method: "POST", headers: { Authorization: `FlyV1 ${token}` }, body });
  const j = await res.json();
  if (j.status !== "success") throw new Error(`${metric}: ${j.error ?? res.status}`);
  return j.data.result.map(s => ({ metric: s.metric, values: s.values.map(([t, v]) => [t, Number(v)]) }));
}

// Counter increments within the window as [timestamp, amount]. A series that first appears after the
// window starts counts from zero. Prometheus writes NaN staleness markers both for missed scrapes and
// when a deploy stops the process; only a drop in value or a release during the gap means the counter
// restarted. Fly records a release a few seconds before the old process stops, hence the margin.
function increments({ values }, start) {
  const out = [];
  let prev = values.length && values[0][0] - start > 60 ? 0 : null;
  let prevAt = start;
  let stale = false;
  for (const [t, v] of values) {
    if (Number.isNaN(v)) { stale = true; continue; }
    const restarted = prev !== null && (v < prev || (stale && releases.some(r => r.at > prevAt - 60 && r.at <= t)));
    const d = prev === null ? 0 : restarted ? v : v - prev;
    if (d > 0) out.push([t, d]);
    prev = v;
    prevAt = t;
    stale = false;
  }
  return out;
}

const add = (obj, key, by) => { obj[key] = (obj[key] ?? 0) + by; };
const hourOf = t => iso(Math.floor(t / 3600) * 3600).slice(11, 16);

async function day(start) {
  const end = Math.min(start + DAY, Math.floor(Date.now() / 1000));
  const span = end - start;
  const hourly = {};
  const bump = (t, key, by) => { hourly[hourOf(t)] ??= {}; add(hourly[hourOf(t)], key, by); };

  const tools = {};
  for (const s of await samples("delphi_mcp_tool_calls_total", end, span))
    for (const [t, d] of increments(s, start)) {
      tools[s.metric.tool] ??= { ok: 0, error: 0 };
      tools[s.metric.tool][s.metric.status] += d;
      bump(t, "toolCalls", d);
    }

  const clients = {};
  for (const s of await samples("delphi_mcp_sessions_total", end, span))
    for (const [t, d] of increments(s, start)) {
      const c = clients[s.metric.client] ??= { sessions: 0, first: iso(t), last: iso(t) };
      c.sessions += d;
      c.last = iso(t);
      bump(t, "sessions", d);
    }

  const methods = {};
  for (const s of await samples("delphi_mcp_requests_total", end, span))
    for (const [, d] of increments(s, start)) add(methods, s.metric.method, d);

  let rateLimited = 0;
  for (const s of await samples("delphi_mcp_rate_limited_total", end, span))
    for (const [t, d] of increments(s, start)) { rateLimited += d; bump(t, "rateLimited", d); }

  // The visitor gauge counts distinct hashed IPs since the process started (or since 00:00 UTC), so
  // only its peak per process is meaningful; visitors cannot be summed across processes.
  const bounds = [start, ...releases.map(r => r.at).filter(t => t > start && t < end), end];
  const visitorSamples = (await samples("delphi_mcp_unique_visitors_today", end, span))
    .flatMap(s => s.values).filter(([, v]) => !Number.isNaN(v));
  const peakVisitorsByProcess = bounds.slice(0, -1).map((from, i) => {
    const vs = visitorSamples.filter(([t]) => t >= from && t < bounds[i + 1]).map(([, v]) => v);
    return { from: iso(from), to: iso(bounds[i + 1]), peak: vs.length ? Math.max(...vs) : null };
  }).filter(p => p.peak !== null);
  for (const [t, v] of visitorSamples) {
    const h = hourly[hourOf(t)] ??= {};
    h.peakVisitors = Math.max(h.peakVisitors ?? 0, v);
  }

  const total = (o, f) => Object.values(o).reduce((a, b) => a + f(b), 0);
  return {
    date: iso(start).slice(0, 10),
    app: APP,
    source: `Fly managed Prometheus (org ${ORG}), raw scrape samples of delphi_mcp_* (mcp/metrics.mjs)`,
    generatedAt: iso(Math.floor(Date.now() / 1000)),
    window: { start: iso(start), end: iso(end), partial: end < start + DAY },
    note: "Times are scrape times (every 15 s), up to one interval after the request. Requests in the last seconds before a deploy are lost. methods['tools/call'] exceeds the tool totals by the calls rejected before reaching a tool (unknown name or invalid arguments). Visitors are distinct hashed IPs per process and cannot be summed.",
    releases: releases.filter(r => r.at >= start && r.at < end).map(r => ({ version: r.version, at: iso(r.at) })),
    totals: { toolCalls: total(tools, t => t.ok + t.error), sessions: total(clients, c => c.sessions), rateLimited, maxVisitorsInOneProcess: Math.max(0, ...peakVisitorsByProcess.map(p => p.peak)) },
    tools: Object.fromEntries(Object.entries(tools).sort((a, b) => (b[1].ok + b[1].error) - (a[1].ok + a[1].error))),
    clients: Object.fromEntries(Object.entries(clients).sort((a, b) => a[1].first.localeCompare(b[1].first))),
    methods,
    peakVisitorsByProcess,
    hourly: Object.entries(hourly).sort().map(([hour, v]) => ({ hour, ...v })),
  };
}

mkdirSync(OUT, { recursive: true });
for (const start of days) {
  const r = await day(start);
  const file = join(OUT, `${r.date}.json`);
  writeFileSync(file, JSON.stringify(r, null, 2) + "\n");
  const t = r.totals;
  console.log(`${relative(ROOT, file)}: ${t.toolCalls} tool calls, ${t.sessions} sessions (${Object.keys(r.clients).join(", ") || "none"}), ${t.rateLimited} rate-limited, peak ${t.maxVisitorsInOneProcess} visitors${r.window.partial ? " (partial day)" : ""}`);
}
