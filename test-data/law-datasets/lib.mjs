// Shared helpers for test-data/law-datasets: laws, slices, providers, record IO. No dependencies (Node 20+).

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = dirname(fileURLToPath(import.meta.url));
export const REPO = resolve(ROOT, "../..");
export const LAWS = JSON.parse(readFileSync(join(ROOT, "laws.json"), "utf8"));
export const KINGDOMS = LAWS.kingdoms;
export const ROT = LAWS.providers.rotation;
export const VERDICTS = ["holds", "partial", "rejected", "unreachable", "not-found"];
export const TYPES = ["paper", "dataset", "database", "specimen-collection", "supplement"];
export const RELEVANCE = ["measures-quantity", "tests-law-directly", "raw-specimens", "context"];
export const ROUND_PROCESSES = {
  1: "link-resolver",
  2: "blind-relevance-audit",
  3: "taxon-and-age-resolver",
  4: "gap-filler",
  5: "final-adjudicator",
};

export const provider = m => {
  const s = String(m ?? "").toLowerCase();
  return /claude|opus|sonnet|fable/.test(s) ? "anthropic" : /gpt|codex/.test(s) ? "openai" : /gemini/.test(s) ? "google"
    : /grok/.test(s) ? "xai" : /composer/.test(s) ? "cursor" : /muse/.test(s) ? "muse" : s || "unknown";
};

export const lawIndex = id => LAWS.laws.findIndex(l => l.id === id);
export const modelFor = (lawId, role) => {
  const i = lawIndex(lawId);
  const off = { scout: 0, r2: 1, r4: 2, r5: 3 }[role];
  return ROT[(i + off) % ROT.length];
};

export const slices = () => LAWS.laws.flatMap(l => Object.keys(l.kingdoms).map(k => ({ law: l.id, kingdom: k })));
export const slicePath = (law, kingdom) => join(ROOT, "records", law, `${kingdom}.json`);
export const readSlice = (law, kingdom) => {
  const p = slicePath(law, kingdom);
  return existsSync(p) ? JSON.parse(readFileSync(p, "utf8")) : null;
};
export const writeSlice = (law, kingdom, rec) => {
  const p = slicePath(law, kingdom);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(rec, null, 2) + "\n");
};
export const now = () => new Date().toISOString().slice(0, 19) + "Z";
export const slug = s => String(s).toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// Polite fetch with timeout; returns { status, ok, text?, headers?, error? }.
export async function http(url, { method = "GET", timeout = 20000, accept, readBody = false, retries = 1 } = {}) {
  for (let t = 0; ; t++) {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeout);
    try {
      const r = await fetch(url, { method, redirect: "follow", signal: ctl.signal,
        headers: { "User-Agent": "delphisci-law-datasets/0.1", ...(accept ? { Accept: accept } : {}) } });
      const text = readBody ? (await r.text()).slice(0, 400_000) : null;
      if (!readBody) try { await r.body?.cancel(); } catch {}
      return { status: r.status, ok: r.ok, text, finalUrl: r.url, type: r.headers.get("content-type"), length: r.headers.get("content-length") };
    } catch (e) {
      if (t >= retries) return { status: null, ok: false, error: e.name === "AbortError" ? "timeout" : String(e.message ?? e) };
    } finally { clearTimeout(timer); }
  }
}
