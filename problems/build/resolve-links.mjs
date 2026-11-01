// Resolve every DOI and URL named in problems.json and approaches/*.json against the live web,
// as BEST_PRACTICES.md section 2 requires ("model-proposed identifiers are checked mechanically").
// Writes problems/dropped-links.json: the links that did not resolve, with the HTTP status or
// error, so the nanopub builder leaves them out. The raw problem and approach files are never
// edited. A link that answers 2xx or 3xx resolves; anything else (404, 403 from a bot wall,
// timeout) is dropped, even if the site is real.
//
//   node problems/build/resolve-links.mjs [--only problems|approaches]
import { readFileSync, writeFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(HERE, "dropped-links.json");
const only = process.argv.includes("--only") ? process.argv[process.argv.indexOf("--only") + 1] : null;

import { linkOf } from "./links.mjs";

const links = new Map(); // url -> [where]
const linkNotes = new Map(); // url -> [note text written by the proposer]
const note = (url, where, text) => {
  if (!url) return;
  if (!links.has(url)) { links.set(url, []); linkNotes.set(url, []); }
  links.get(url).push(where);
  if (text) linkNotes.get(url).push(text);
};

if (only !== "approaches") {
  const problems = JSON.parse(readFileSync(join(HERE, "problems.json"), "utf8")).problems;
  for (const p of problems) for (const r of p.references ?? []) note(linkOf(r), `problem ${p.id}`, r.note);
}
if (only !== "problems") {
  const dir = join(HERE, "approaches");
  for (const f of readdirSync(dir).filter(f => f.endsWith(".json"))) {
    const a = JSON.parse(readFileSync(join(dir, f), "utf8"));
    for (const ap of a.approaches ?? []) {
      for (const r of ap.references ?? []) note(linkOf(r), `approach ${ap.problem}--${a.model}--${ap.n}`, r.note);
      for (const d of ap.datasets ?? []) note(d.url ? String(d.url).trim() : null, `approach ${ap.problem}--${a.model}--${ap.n} dataset`, `${d.name ?? ""} ${d.note ?? ""}`);
    }
  }
}

const UA = "delphisci-link-check/0.1 (+https://github.com/fractastical/delphi; mailto:joel@fractastical.com)";
const get = async (url, accept = "application/json") => {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 20000);
  try { return await fetch(url, { redirect: "follow", signal: ctl.signal, headers: { "user-agent": UA, accept } }); }
  finally { clearTimeout(t); }
};
// A DOI is an identifier, not a web page: publishers' bot walls answer 403 to the redirected
// request even for real papers. Resolve it through the Handle system, which says whether the DOI
// is registered, and fetch its Crossref metadata so the title can be compared with the note.
async function probeDoi(doi) {
  try {
    const h = await get(`https://doi.org/api/handles/${encodeURIComponent(doi).replace(/%2F/g, "/")}`);
    if (h.status === 404) return { ok: false, status: 404, error: "DOI not registered" };
    if (!h.ok) return { ok: false, status: h.status, error: "handle API" };
    const hj = await h.json();
    if (hj.responseCode !== 1) return { ok: false, status: 404, error: `handle responseCode ${hj.responseCode}` };
    const target = hj.values?.find(v => v.type === "URL")?.data?.value ?? null;
    let c = await get(`https://api.crossref.org/works/${encodeURIComponent(doi)}`);
    for (let retry = 0; c.status === 429 && retry < 4; retry++) {
      await new Promise(r => setTimeout(r, 1500 * (retry + 1)));
      c = await get(`https://api.crossref.org/works/${encodeURIComponent(doi)}`);
    }
    if (c.ok) {
      const m = (await c.json()).message;
      return { ok: true, status: h.status, final: target, title: m.title?.[0] ?? null, year: m.issued?.["date-parts"]?.[0]?.[0] ?? null, container: m["container-title"]?.[0] ?? null };
    }
    return { ok: true, status: h.status, final: target, title: null, note: `crossref ${c.status}` };
  } catch (e) {
    return { ok: false, error: String(e.cause?.code ?? e.message) };
  }
}
async function probe(url) {
  const doi = url.match(/^https:\/\/doi\.org\/(.+)$/)?.[1];
  if (doi) return probeDoi(doi);
  for (const method of ["HEAD", "GET"]) {
    try {
      const ctl = new AbortController();
      const t = setTimeout(() => ctl.abort(), 20000);
      const res = await fetch(url, { method, redirect: "follow", signal: ctl.signal, headers: { "user-agent": UA, accept: "*/*" } });
      clearTimeout(t);
      if (res.ok) return { ok: true, status: res.status, final: res.url };
      if (method === "GET") return { ok: false, status: res.status, final: res.url };
    } catch (e) {
      if (method === "GET") return { ok: false, error: String(e.cause?.code ?? e.message) };
    }
  }
  return { ok: false, error: "unreachable" };
}

// A registered DOI can still be the wrong paper. Compare the Crossref title with the words of the
// note the proposer wrote: if they share no significant word, the DOI is dropped as a mismatch.
const STOP = new Set("the a an of in on and or for to with by from at as is are its their et al vs versus".split(" "));
const words = s => new Set(String(s ?? "").toLowerCase().normalize("NFKD").replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(w => w.length > 3 && !STOP.has(w)));
const titleAgrees = (title, notes) => {
  if (!title) return true; // Crossref had no title; the Handle check stands alone
  const t = words(title);
  return notes.some(n => [...words(n)].filter(w => t.has(w)).length >= 2);
};

const previous = existsSync(OUT) ? JSON.parse(readFileSync(OUT, "utf8")) : { checked: {}, dropped: [] };
const checked = { ...(previous.checked ?? {}) };
const urls = [...links.keys()];
let i = 0;
async function worker() {
  while (i < urls.length) {
    const url = urls[i++];
    const r = await probe(url);
    const notes = linkNotes.get(url) ?? [];
    if (r.ok && !titleAgrees(r.title, notes)) Object.assign(r, { ok: false, error: `title mismatch: Crossref says "${r.title}"` });
    checked[url] = { ...r, checkedAt: new Date().toISOString(), where: links.get(url), notes };
    if (!r.ok) console.error(`DROP ${url} ${r.status ?? ""} ${r.error ?? ""} (${links.get(url).join("; ")})`);
  }
}
await Promise.all(Array.from({ length: 3 }, worker));

const dropped = Object.entries(checked).filter(([, v]) => !v.ok).map(([url, v]) => ({ url, status: v.status ?? null, error: v.error ?? null, where: v.where }));
writeFileSync(OUT, JSON.stringify({ generated: new Date().toISOString(), note: "Links that did not resolve when checked; the nanopub builder omits them. Raw files are unchanged.", checked, dropped }, null, 2) + "\n");
console.log(`${urls.length} links checked, ${dropped.length} dropped -> ${OUT}`);
