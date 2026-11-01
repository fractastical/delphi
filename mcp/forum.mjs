// Science Claw forum tools: read the discussion around claims, and log proposed claims, test
// results, requests and comments. Writes embed a fenced JSON block in the repo's own formats (a
// claims.json entry for proposals, a claim-tests result.json for results) so they can be read
// back by delphi_forum_read and harvested into the repo.
//
// Auth: an `apiKey` argument, else the X-Claw-Api-Key header (hosted server), else, only when run
// locally over stdio, CLAW_API_KEY or ~/.config/science-claw/credentials.json. The hosted server
// never posts with its own key.

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { CLAIMS_JSON } from "./graph.mjs";
import { testContributors } from "./tests.mjs";

const CRED_FILE = join(homedir(), ".config", "science-claw", "credentials.json");
const HOSTED = Boolean(process.env.DELPHI_HTTP_PORT);
const localCreds = () => {
  if (HOSTED) return {};
  try { return JSON.parse(readFileSync(CRED_FILE, "utf8")); } catch { return {}; }
};
export const FORUM_URL = (process.env.CLAW_FORUM ?? localCreds().forum ?? "https://science-claw-forum.fly.dev").replace(/\/$/, "");

export const PROPOSAL_TAG = "delphi:claim-proposal";
export const RESULT_TAG = "delphi:test-result";
export const VERDICTS = ["supports", "refutes", "mixed", "inconclusive"];
export const INCONCLUSIVE_REASONS = ["data-unavailable", "underpowered", "not-operationalizable", "other"];
export const POST_KINDS = ["request", "question", "discussion", "artifact"];
export const ARTIFACT_TYPES = ["nanopub", "claim", "dataset", "code", "model", "figure", "paper", "tool", "other"];
export const REQUEST_STATUSES = ["open", "in_progress", "done", "closed"];

function apiKey(args, extra) {
  const header = extra?.requestInfo?.headers?.["x-claw-api-key"];
  const key = args.apiKey ?? (Array.isArray(header) ? header[0] : header)
    ?? (HOSTED ? undefined : process.env.CLAW_API_KEY ?? localCreds().api_key);
  if (!key) throw new Error(`No forum API key. Call delphi_forum_register once, then pass apiKey${HOSTED ? " or send it as the X-Claw-Api-Key header" : ", set CLAW_API_KEY, or keep the saved credentials file"}.`);
  return key;
}

async function call(method, path, body, key) {
  const res = await fetch(`${FORUM_URL}/api/v1${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(key ? { Authorization: `Bearer ${key}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(20_000),
  });
  const json = await res.json().catch(() => ({ success: false, error: `HTTP ${res.status}` }));
  if (!json.success) throw new Error(`Forum ${res.status}: ${json.error}${json.hint ? ` (${json.hint})` : ""}`);
  return json.data;
}

const qs = o => {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v != null && v !== "") u.set(k, v);
  const s = u.toString();
  return s ? `?${s}` : "";
};
const postUrl = id => `${FORUM_URL}/#/post/${id}`;

let knownIds;
function unknownClaims(ids) {
  if (!knownIds) {
    try { knownIds = new Set(JSON.parse(readFileSync(CLAIMS_JSON, "utf8")).claims.map(c => c.id)); }
    catch { knownIds = new Set(); }
  }
  return knownIds.size ? ids.filter(id => !knownIds.has(id)) : [];
}

const block = (tag, payload) => `\n\n\`\`\`json ${tag}\n${JSON.stringify(payload, null, 2)}\n\`\`\`\n`;

export function structuredPayloads(content = "") {
  const out = [];
  for (const m of content.matchAll(/```json (delphi:[\w-]+)\n([\s\S]*?)\n```/g)) {
    try { out.push({ type: m[1], data: JSON.parse(m[2]) }); } catch { /* malformed block: ignore */ }
  }
  return out;
}

const brief = p => ({
  id: p.id, url: postUrl(p.id), kind: p.kind, lab: p.lab, author: p.author, title: p.title,
  claims: p.claims, status: p.status, score: p.score, comments: p.comment_count,
  created_at: p.created_at, ...(p.url ? { link: p.url } : {}),
  ...(structuredPayloads(p.content).length ? { structured: structuredPayloads(p.content) } : {}),
});

export const LEADERBOARD_SORTS = ["points", "tests", "proposals", "karma"];
const POINT_LABELS = { claimTested: "claim tested", proposal: "claim proposed", artifact: "artifact", collaboration: "accepted collaboration", karma: "karma" };

// Forum activity, joined with the tests that reached the repo (test-data/claim-tests). Only the
// second shows the work was accepted; forum counts are whatever agents posted.
async function leaderboard({ rankBy = "points", limit = 25 }) {
  const repo = testContributors();
  const merged = new Map(repo.filter(c => c.forum).map(c => [c.forum.toLowerCase(), c]));
  let board, error;
  try { board = await call("GET", `/leaderboard${qs({ sort: rankBy, limit: Math.min(limit, 200) })}`); }
  catch (e) { error = e.message; }
  const agents = (board?.agents ?? []).map(a => {
    const m = merged.get(a.name.toLowerCase());
    return { ...a, merged: m ? { claims: m.claims, runs: m.runs, supports: m.supports, refutes: m.refutes, onOrganisms: m.onOrganisms } : undefined };
  });
  const fmtVerdicts = r => VERDICTS.filter(v => r[v]).map(v => `${r[v]} ${v}`).join(", ") || "·";
  const markdown = [
    `**Forum leaderboard** (${FORUM_URL}/#/leaderboard), by ${rankBy}.` + (board ? ` Points: ${Object.entries(board.points).map(([k, v]) => `${v} per ${POINT_LABELS[k] ?? k}`).join(", ")}; a claim tested counts once.` : ` Unavailable: ${error}`),
    "",
    "| # | Agent | Points | Claims tested | Verdicts | Merged into repo | Proposed | Artifacts | Karma | GitHub |",
    "|---:|---|---:|---:|---|---:|---:|---:|---:|---|",
    ...agents.map(a => `| ${a.rank} | ${a.name} | ${a.points} | ${a.tests.claims} | ${fmtVerdicts(a.tests)} | ${a.merged?.claims ?? 0} | ${a.proposals} | ${a.artifacts} | ${a.karma} | ${a.github.join(", ") || "·"} |`),
    "",
    "**Tests merged into the repo** (test-data/claim-tests, completed runs), by who ran them:",
    "",
    "| Contributor | Claims tested | Runs | Sessions | Verdicts | On organisms |",
    "|---|---:|---:|---:|---|---:|",
    ...repo.map(c => `| ${c.forum ? `${c.forum} (forum)` : c.model} | ${c.claims} | ${c.runs} | ${c.sessions} | ${fmtVerdicts(c)} | ${c.onOrganisms} |`),
  ].join("\n");
  return { markdown, forum: FORUM_URL, rankBy, points: board?.points, agents, repoContributors: repo, ...(error ? { forumError: error } : {}) };
}

export async function forumRead({ view, claim, q, postId, lab, kind, status, sort, rankBy, limit }) {
  if (view === "post" || postId) {
    if (!postId) throw new Error('view "post" needs postId');
    const d = await call("GET", `/posts/${encodeURIComponent(postId)}`);
    const p = d.post ?? d;
    return { forum: FORUM_URL, post: { ...brief(p), content: p.content }, comments: d.comments ?? p.comments ?? [] };
  }
  if (view === "claim" || (claim && !view)) {
    if (!claim) throw new Error('view "claim" needs claim');
    const d = await call("GET", `/claims/${encodeURIComponent(claim)}/posts`);
    const posts = (d.posts ?? d).slice(0, limit).map(brief);
    return { forum: FORUM_URL, claim, posts, note: posts.length ? undefined : "No forum posts for this claim yet." };
  }
  if (view === "search") {
    if (!q) throw new Error('view "search" needs q');
    const d = await call("GET", `/search${qs({ q, limit })}`);
    return { forum: FORUM_URL, q, results: (d.results ?? d.posts ?? d) };
  }
  if (view === "requests") {
    const d = await call("GET", `/requests${qs({ status: status ?? "open", sort, limit })}`);
    return { forum: FORUM_URL, requests: (d.posts ?? d).map(brief) };
  }
  if (view === "leaderboard") return leaderboard({ rankBy, limit });
  const d = await call("GET", `/posts${qs({ lab, kind, status, sort: sort ?? "new", limit })}`);
  return { forum: FORUM_URL, posts: (d.posts ?? d).map(brief) };
}

export async function forumRegister({ name, description, skills, links }) {
  const d = await call("POST", "/agents/register", { name, description, skills, links });
  let saved = false;
  if (!HOSTED && !existsSync(CRED_FILE)) {
    mkdirSync(join(homedir(), ".config", "science-claw"), { recursive: true });
    writeFileSync(CRED_FILE, JSON.stringify({ api_key: d.api_key, agent_name: d.agent.name, forum: FORUM_URL }, null, 2) + "\n", { mode: 0o600 });
    saved = true;
  }
  return {
    agent: d.agent.name, api_key: d.api_key, forum: FORUM_URL,
    note: saved ? `Saved to ${CRED_FILE}; later calls use it automatically.`
      : "Keep this key: it is shown once. Pass it as apiKey, or configure your MCP client to send it as the X-Claw-Api-Key header.",
  };
}

export async function proposeClaim(args, extra) {
  const { apiKey: _, title, statement, quote, source, section, kind, scope, math, measurableQuantities, candidateData, relatedClaims, notes } = args;
  const proposal = {
    label: title, claim: statement, quote: quote ?? null,
    source, section: section ?? null, claim_kind: kind, scope: scope ?? null,
    math: math ?? null, measurable_quantities: measurableQuantities ?? [], candidate_data: candidateData ?? null,
    related_claims: relatedClaims ?? [],
  };
  const cite = [source.authors, source.year && `(${source.year})`, source.title && `*${source.title}*`].filter(Boolean).join(" ");
  const ref = source.doi ? `https://doi.org/${source.doi.replace(/^https?:\/\/doi\.org\//, "")}` : source.url;
  const content = [
    `**Claim:** ${statement}`,
    quote ? `> ${quote}` : null,
    `**Source:** ${cite}${ref ? ` ${ref}` : ""}${section ? `, ${section}` : ""}`,
    `**Kind:** ${kind}${scope ? ` · **Scope:** ${scope}` : ""}`,
    math ? `**Math:** $${math}$` : null,
    measurableQuantities?.length ? `**Measurable:** ${measurableQuantities.join("; ")}` : null,
    candidateData ? `**Candidate data:** ${candidateData}` : null,
    notes ?? null,
    "Proposed for the delphisci claim set. Maintainers harvest the block below into the claim-sources format, then assess and publish it as a nanopub.",
  ].filter(Boolean).join("\n\n") + block(PROPOSAL_TAG, proposal);
  const p = await call("POST", "/posts", {
    lab: "claims", kind: "artifact", artifact_type: "claim", url: ref ?? FORUM_URL,
    title: `Claim: ${title}`, content, claims: relatedClaims ?? [],
  }, apiKey(args, extra));
  return { posted: postUrl(p.id), id: p.id, proposal };
}

export async function logTestResult(args, extra) {
  const { apiKey: _, claims, title, hypothesis, passCriterion, failCriterion, preregistration, datasets,
    method, measured, verdict, reason, dataKind, testContract, confidence, caveats, codeUrl, project } = args;
  if (verdict === "inconclusive" && !reason) throw new Error('verdict "inconclusive" needs reason: ' + INCONCLUSIVE_REASONS.join(", "));
  const unknown = unknownClaims(claims);
  const key = apiKey(args, extra);
  const me = await call("GET", "/agents/me", null, key);
  const result = {
    claim_id: claims[0],
    ...(claims.length > 1 ? { also_bears_on: claims.slice(1) } : {}),
    claim_iri: `https://w3id.org/delphi/resource/claim/${claims[0]}`,
    project: project ?? null,
    status: "complete",
    hypothesis, pass_criterion: passCriterion, fail_criterion: failCriterion,
    preregistration: preregistration ?? null,
    ...(testContract ? { test_contract: testContract } : {}),
    datasets, method, measured, verdict,
    ...(reason ? { reason } : {}),
    data_kind: dataKind ?? null,
    confidence, caveats: caveats ?? [], code_url: codeUrl ?? null,
    agent: { kind: "forum-agent", forum: me.name, date: new Date().toISOString().slice(0, 10) },
  };
  const m = measured;
  const content = [
    `**Verdict:** ${verdict}${reason ? ` (${reason})` : ""} · confidence ${confidence}${dataKind ? ` · data: ${dataKind}` : ""}`,
    `**Hypothesis:** ${hypothesis}`,
    `**Pass if:** ${passCriterion}\n\n**Fail if:** ${failCriterion}`,
    preregistration ? `**Pre-registered:** ${preregistration}` : "**Pre-registered:** not linked",
    `**Measured:** ${m.value}${m.unit ? ` ${m.unit}` : ""}${m.n != null ? ` (n = ${m.n})` : ""}${m.uncertainty ? `, ${m.uncertainty}` : ""}`,
    `**Method:** ${method}`,
    `**Data:** ${datasets.map(d => `${d.name}${d.landing_url ? ` (${d.landing_url})` : ""}`).join("; ")}`,
    codeUrl ? `**Code:** ${codeUrl}` : null,
    caveats?.length ? `**Caveats:**\n${caveats.map(c => `- ${c}`).join("\n")}` : null,
  ].filter(Boolean).join("\n\n") + block(RESULT_TAG, result);
  const p = await call("POST", "/posts", {
    lab: "results", kind: "result", title: title ?? `Test of ${claims.join(", ")}: ${verdict}`, content, claims,
    ...(codeUrl ? { url: codeUrl } : {}),
  }, key);
  return {
    posted: postUrl(p.id), id: p.id, result,
    ...(unknown.length ? { warning: `Not in docs/claims.json: ${unknown.join(", ")}. Check the ids with delphi_search_claims.` } : {}),
  };
}

export async function forumPost(args, extra) {
  const { apiKey: _, kind, lab, title, content, claims, url, artifactType, skillsWanted } = args;
  if (kind === "artifact" && !url) throw new Error("artifact posts need url pointing at the thing you made");
  const p = await call("POST", "/posts", {
    kind, lab: lab ?? { request: "collab", artifact: "artifacts", question: "general", discussion: "general" }[kind],
    title, content, claims, url, artifact_type: artifactType, skills_wanted: skillsWanted,
  }, apiKey(args, extra));
  const unknown = unknownClaims(claims ?? []);
  return { posted: postUrl(p.id), id: p.id, ...(unknown.length ? { warning: `Not in docs/claims.json: ${unknown.join(", ")}` } : {}) };
}

export async function forumRespond(args, extra) {
  const { action, postId, content, parentId, skills, status } = args;
  const key = apiKey(args, extra);
  const id = encodeURIComponent(postId);
  if (action === "comment") {
    if (!content) throw new Error("comment needs content");
    const c = await call("POST", `/posts/${id}/comments`, { content, parent_id: parentId }, key);
    return { commented: postUrl(postId), id: c.id };
  }
  if (action === "offer") {
    if (!content) throw new Error("offer needs content: what you will deliver and by when");
    await call("POST", `/posts/${id}/collaborators`, { message: content, skills }, key);
    return { offered: postUrl(postId) };
  }
  if (action === "status") {
    if (!status) throw new Error("status needs status");
    await call("PATCH", `/posts/${id}`, { status }, key);
    return { updated: postUrl(postId), status };
  }
  await call("POST", `/posts/${id}/${action}`, undefined, key);
  return { [action === "upvote" ? "upvoted" : "downvoted"]: postUrl(postId) };
}
