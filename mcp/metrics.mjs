// Usage counters for the hosted server, exposed in Prometheus text format on a private port that
// Fly scrapes (fly.toml [metrics]). Counters live in memory, so they reset on deploy; Prometheus
// rate()/increase() handle that. No IPs are stored: unique visitors are counted as salted hashes,
// and the salt is replaced every UTC day.

import { createHash, randomBytes } from "node:crypto";

const BUCKETS = [0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10];
const MAX_CLIENTS = 50;

const toolCalls = new Map();    // "tool|status" -> count
const toolSeconds = new Map();  // tool -> { buckets[], sum, count }
const sessions = new Map();     // client -> count
const requests = new Map();     // method -> count
let rateLimited = 0;

let day = "";
let salt = "";
const visitors = new Set();

const inc = (map, key, by = 1) => map.set(key, (map.get(key) ?? 0) + by);

export function observeToolCall(tool, ok, seconds) {
  inc(toolCalls, `${tool}|${ok ? "ok" : "error"}`);
  const h = toolSeconds.get(tool) ?? toolSeconds.set(tool, { buckets: BUCKETS.map(() => 0), sum: 0, count: 0 }).get(tool);
  BUCKETS.forEach((b, i) => { if (seconds <= b) h.buckets[i]++; });
  h.sum += seconds;
  h.count++;
}

export function observeRequest(method) {
  inc(requests, method ?? "unknown");
}

export function observeSession(clientName) {
  const name = String(clientName ?? "unknown").toLowerCase().replace(/[^a-z0-9._ -]/g, "").slice(0, 40) || "unknown";
  inc(sessions, sessions.has(name) || sessions.size < MAX_CLIENTS ? name : "other");
}

export function observeRateLimited() {
  rateLimited++;
}

export function observeVisitor(ip) {
  const today = new Date().toISOString().slice(0, 10);
  if (today !== day) { day = today; salt = randomBytes(16).toString("hex"); visitors.clear(); }
  visitors.add(createHash("sha256").update(salt + ip).digest("hex").slice(0, 16));
}

const esc = v => String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"');

export function renderMetrics() {
  const out = [];
  const family = (name, type, help) => out.push(`# HELP ${name} ${help}`, `# TYPE ${name} ${type}`);

  family("delphi_mcp_tool_calls_total", "counter", "MCP tool calls by tool and outcome.");
  for (const [key, n] of toolCalls) {
    const [tool, status] = key.split("|");
    out.push(`delphi_mcp_tool_calls_total{tool="${esc(tool)}",status="${status}"} ${n}`);
  }

  family("delphi_mcp_tool_call_seconds", "histogram", "MCP tool call duration.");
  for (const [tool, h] of toolSeconds) {
    BUCKETS.forEach((b, i) => out.push(`delphi_mcp_tool_call_seconds_bucket{tool="${esc(tool)}",le="${b}"} ${h.buckets[i]}`));
    out.push(`delphi_mcp_tool_call_seconds_bucket{tool="${esc(tool)}",le="+Inf"} ${h.count}`,
      `delphi_mcp_tool_call_seconds_sum{tool="${esc(tool)}"} ${h.sum}`,
      `delphi_mcp_tool_call_seconds_count{tool="${esc(tool)}"} ${h.count}`);
  }

  family("delphi_mcp_sessions_total", "counter", "MCP initialize requests by client name (clientInfo.name).");
  for (const [client, n] of sessions) out.push(`delphi_mcp_sessions_total{client="${esc(client)}"} ${n}`);

  family("delphi_mcp_requests_total", "counter", "JSON-RPC requests to /mcp by method.");
  for (const [method, n] of requests) out.push(`delphi_mcp_requests_total{method="${esc(method)}"} ${n}`);

  family("delphi_mcp_rate_limited_total", "counter", "Requests rejected by the per-IP rate limit.");
  out.push(`delphi_mcp_rate_limited_total ${rateLimited}`);

  family("delphi_mcp_unique_visitors_today", "gauge", "Distinct client IPs since 00:00 UTC (hashed, not stored; resets on deploy).");
  out.push(`delphi_mcp_unique_visitors_today ${visitors.size}`);

  return out.join("\n") + "\n";
}
