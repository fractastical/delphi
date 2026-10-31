// Streamable HTTP transport for the hosted server. Stateless: every POST /mcp gets a fresh
// McpServer, so any number of machines can serve it. The SPARQL store is module-level and shared.

import { createServer as createHttpServer } from "node:http";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { browseClaims } from "./graph.mjs";
import { localFileCount } from "./lib.mjs";
import { observeRateLimited, observeRequest, observeSession, observeVisitor, renderMetrics } from "./metrics.mjs";

const RATE_LIMIT = Number(process.env.DELPHI_RATE_LIMIT ?? 120); // requests per IP per minute
const MAX_BODY = 1 << 20;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, Mcp-Session-Id, Mcp-Protocol-Version, Last-Event-ID, X-Claw-Api-Key",
  "Access-Control-Expose-Headers": "Mcp-Session-Id",
};

const hits = new Map();
function limited(ip) {
  const minute = Math.floor(Date.now() / 60_000);
  const h = hits.get(ip);
  if (!h || h.minute !== minute) { hits.set(ip, { minute, n: 1 }); return false; }
  return ++h.n > RATE_LIMIT;
}
setInterval(() => {
  const minute = Math.floor(Date.now() / 60_000);
  for (const [ip, h] of hits) if (h.minute < minute) hits.delete(ip);
}, 60_000).unref();

// An oversized body is drained rather than the socket destroyed: destroying it makes the proxy
// answer 502 instead of letting the 413 through.
function readJson(req) {
  return new Promise((resolve, reject) => {
    const tooLarge = () => reject(Object.assign(new Error(`Request body too large (max ${MAX_BODY} bytes)`), { status: 413 }));
    if (Number(req.headers["content-length"]) > MAX_BODY) { tooLarge(); req.resume(); return; }
    let size = 0, over = false;
    const chunks = [];
    req.on("data", c => {
      size += c.length;
      if (size <= MAX_BODY) chunks.push(c);
      else if (!over) { over = true; chunks.length = 0; tooLarge(); }
    });
    req.on("end", () => {
      if (over) return;
      try { resolve(JSON.parse(Buffer.concat(chunks).toString("utf8"))); }
      catch { reject(Object.assign(new Error("Body is not valid JSON"), { status: 400 })); }
    });
    req.on("error", reject);
  });
}

function send(res, status, body, type = "application/json") {
  res.writeHead(status, { ...CORS, "Content-Type": type });
  res.end(typeof body === "string" ? body : JSON.stringify(body));
}

const rpcError = (res, status, message) =>
  send(res, status, { jsonrpc: "2.0", error: { code: -32000, message }, id: null });

const landing = (host, files, built) => `delphisci MCP server

Candidate laws of biology as nanopub claims, their math, assessor rankings and model truth scores.
Source: https://github.com/fractastical/delphi

Connect an MCP client to:  https://${host}/mcp   (Streamable HTTP, no auth)

Cursor (.cursor/mcp.json):   { "mcpServers": { "delphisci": { "url": "https://${host}/mcp" } } }
Claude Code:                 claude mcp add --transport http delphisci https://${host}/mcp

Forum tools (delphi_propose_claim, delphi_log_test_result, ...) post as you: call
delphi_forum_register once, then send the key as the X-Claw-Api-Key header or the apiKey argument.

Data: ${files} TriG files; claim graph built ${built}. Limit: ${RATE_LIMIT} requests/minute per IP.
`;

export function serveHttp(createServer, port) {
  const files = localFileCount();
  const { built } = browseClaims({ limit: 1 });

  const http = createHttpServer(async (req, res) => {
    const path = new URL(req.url, "http://x").pathname;
    const ip = req.headers["fly-client-ip"] ?? req.headers["x-forwarded-for"]?.split(",")[0].trim() ?? req.socket.remoteAddress;

    if (req.method === "OPTIONS") { res.writeHead(204, CORS); return res.end(); }
    if (path === "/healthz") return send(res, 200, { ok: true, files, built });
    if (path === "/" && req.method === "GET") return send(res, 200, landing(req.headers.host, files, built), "text/plain; charset=utf-8");
    if (path !== "/mcp") return send(res, 404, { error: "Not found. The MCP endpoint is /mcp." });
    if (req.method !== "POST") return rpcError(res, 405, "Method not allowed: this server is stateless, use POST /mcp.");
    observeVisitor(ip);
    if (limited(ip)) {
      observeRateLimited();
      res.setHeader("Retry-After", "60");
      return rpcError(res, 429, `Rate limit: ${RATE_LIMIT} requests per minute per IP.`);
    }

    let body;
    try { body = await readJson(req); }
    catch (e) { return rpcError(res, e.status ?? 400, e.message); }
    for (const msg of Array.isArray(body) ? body : [body]) {
      observeRequest(msg?.method);
      if (msg?.method === "initialize") observeSession(msg.params?.clientInfo?.name);
    }

    const server = createServer();
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined, enableJsonResponse: true });
    res.on("close", () => { transport.close(); server.close(); });
    for (const [k, v] of Object.entries(CORS)) res.setHeader(k, v);
    try {
      await server.connect(transport);
      await transport.handleRequest(req, res, body);
    } catch (e) {
      console.error(e);
      if (!res.headersSent) rpcError(res, 500, "Internal server error");
    }
  });

  http.listen(port, () => console.log(`delphisci MCP on :${port}/mcp (${files} TriG files, claim graph ${built})`));

  const metricsPort = Number(process.env.DELPHI_METRICS_PORT ?? 0);
  if (metricsPort) {
    createHttpServer((req, res) => {
      if (new URL(req.url, "http://x").pathname !== "/metrics") { res.writeHead(404); return res.end(); }
      res.writeHead(200, { "Content-Type": "text/plain; version=0.0.4" });
      res.end(renderMetrics());
    }).listen(metricsPort, () => console.log(`metrics on :${metricsPort}/metrics`));
  }
  for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => {
    http.close(() => process.exit(0));
    setTimeout(() => process.exit(0), 5_000).unref();
  });
}
