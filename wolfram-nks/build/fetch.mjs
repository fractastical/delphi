// Fetch the main text (pp. 1–846) of A New Kind of Science from wolframscience.com/nks
// into a local, git-ignored cache, and write inputs/pages.json with each page's URL and
// the SHA-256 of its extracted text. The book is © Stephen Wolfram, LLC (all rights
// reserved), so only the page index and hashes are committed, never the text itself.
//
//   node build/fetch.mjs            fetch missing pages, rebuild cache/nks.txt and pages.json
//   node build/fetch.mjs --verify   fail if any cached page differs from pages.json
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const CACHE = join(ROOT, "inputs/cache");
const BASE = "https://www.wolframscience.com";
const LAST_PAGE = 846;
const UA = "delphisci-nks-claim-extractor (+https://github.com/fractastical/delphisci)";
const verify = process.argv.includes("--verify");
const sha256 = s => createHash("sha256").update(s).digest("hex");

// Inline math uses <sup>/<sub> (e.g. 10<sup>-35</sup>); mark them so exponents and
// indices are not flattened into the base (10-35, ej).
const decode = s => s
  .replace(/<(sup|sub)>([\s\S]*?)<\/\1>/g, (_, tag, x) => {
    const inner = x.replace(/<[^>]+>/g, "").trim();
    return (tag === "sup" ? "^" : "_") + (/^[A-Za-z0-9]+$/.test(inner) ? inner : `(${inner})`);
  })
  .replace(/<img\b[^>]*\balt="([^"]*)"[^>]*>/g, "$1")
  .replace(/<[^>]+>/g, "")
  .replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
  .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
  .replace(/&nbsp;/g, " ").replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&amp;/g, "&")
  .replace(/\s+/g, " ").trim();

// Page text: chapter/section headings, body paragraphs and figure captions, in order.
function pageText(html, url) {
  const start = html.indexOf('<div class="text-content');
  if (start === -1) throw new Error(`${url}: no text-content block`);
  const end = html.indexOf('<div class="ribbon-wrapper stripe', start);
  const body = html.slice(start, end === -1 ? undefined : end);
  const out = [];
  for (const m of body.matchAll(/<(h1|h2|h3|p|figcaption)\b([^>]*)>([\s\S]*?)<\/\1>/g)) {
    const t = decode(m[3]);
    if (!t) continue;
    out.push(m[1] === "h1" ? `# ${t}` : m[1] === "h2" || m[1] === "h3" ? `## ${t}` : m[1] === "figcaption" ? `[Caption] ${t}` : t);
  }
  return out.join("\n");
}

async function get(url) {
  for (let attempt = 1; ; attempt++) {
    const r = await fetch(url, { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(30000) }).catch(e => e);
    if (r instanceof Response && r.ok) return r.text();
    if (r instanceof Response && r.status === 404) return null;
    if (attempt === 4) throw new Error(`${url}: ${r instanceof Response ? r.status : r.message}`);
    await new Promise(res => setTimeout(res, 2000 * attempt));
  }
}

// Section start pages from the table of contents; a page belongs to the latest section
// starting at or before it, which gives its canonical URL slug.
const toc = await get(`${BASE}/nks/`);
const sections = [...new Set([...toc.matchAll(/href="\/nks\/p(\d+)--([a-z0-9-]+)\/"/g)].map(m => `${m[1]}|${m[2]}`))]
  .map(s => { const [p, slug] = s.split("|"); return { page: +p, slug }; })
  .filter(s => s.page >= 1 && s.page <= LAST_PAGE)
  .sort((a, b) => a.page - b.page);
if (sections[0]?.page !== 1) throw new Error("table of contents did not yield a section starting on page 1");
// In TOC order each chapter link is followed by its first section's link.
const chapters = [];
for (const m of toc.matchAll(/href="\/nks\/(?:chap-(\d+)--([a-z0-9-]+)|p(\d+)--[a-z0-9-]+)\/"/g)) {
  if (m[1] && !chapters.some(c => c.n === +m[1])) chapters.push({ n: +m[1], slug: m[2] });
  else if (m[3] && chapters.at(-1) && chapters.at(-1).startPage === undefined) chapters.at(-1).startPage = +m[3];
}
if (chapters.length !== 12 || chapters.some((c, i) => c.n !== i + 1 || !c.startPage)) throw new Error(`unexpected chapter list ${JSON.stringify(chapters)}`);

mkdirSync(join(CACHE, "pages"), { recursive: true });
mkdirSync(join(CACHE, "html"), { recursive: true });
const pinned = existsSync(join(ROOT, "inputs/pages.json")) ? JSON.parse(readFileSync(join(ROOT, "inputs/pages.json"), "utf8")) : null;
const pages = [];
const todo = [];
for (let p = 1; p <= LAST_PAGE; p++) {
  const sec = sections.filter(s => s.page <= p).at(-1);
  pages.push({ page: p, url: `${BASE}/nks/p${p}--${sec.slug}/`, sectionSlug: sec.slug, sectionStart: sec.page });
  if (!existsSync(join(CACHE, "html", `p${p}.html`))) todo.push(pages.at(-1));
}
if (verify && todo.length) throw new Error(`${todo.length} pages missing from cache; run without --verify`);

let done = 0;
const worker = async () => {
  for (let pg; (pg = todo.shift()); ) {
    // Blank print pages (e.g. before a chapter opening) have no web page.
    writeFileSync(join(CACHE, "html", `p${pg.page}.html`), (await get(pg.url)) ?? "");
    if (++done % 50 === 0) console.log(`fetched ${done}`);
    await new Promise(res => setTimeout(res, 250));
  }
};
await Promise.all(Array.from({ length: 4 }, worker));

let full = "";
for (const pg of pages) {
  const html = readFileSync(join(CACHE, "html", `p${pg.page}.html`), "utf8");
  const text = html ? pageText(html, pg.url) + "\n" : "";
  if (!verify) writeFileSync(join(CACHE, "pages", `p${pg.page}.txt`), text);
  pg.sha256 = sha256(text);
  pg.words = text.split(/\s+/).filter(Boolean).length;
  if (!text) { pg.blank = true; delete pg.url; }
  full += `=== p${pg.page} ===\n${text}`;
}
if (pinned) {
  const bad = pages.filter((pg, i) => pinned.pages[i]?.sha256 !== pg.sha256 || pinned.pages[i]?.url !== pg.url);
  if (bad.length) {
    console.error(`pages differ from pinned inputs/pages.json: ${bad.map(b => b.page).slice(0, 20).join(", ")}${bad.length > 20 ? " …" : ""}`);
    if (verify) process.exit(1);
  }
}
if (verify) { console.log(`all ${pages.length} cached pages match inputs/pages.json`); process.exit(0); }
writeFileSync(join(CACHE, "nks.txt"), full);
writeFileSync(join(ROOT, "inputs/pages.json"), JSON.stringify({
  source: `${BASE}/nks/`, fetchedAt: new Date().toISOString(), textSha256: sha256(full),
  extraction: "headings, p.text paragraphs and figcaptions of div.text-content; sup/sub as ^/_, inline images as alt text; other tags stripped, whitespace collapsed",
  chapters, pages,
}, null, 1) + "\n");
console.log(`${pages.length} pages (blank: ${pages.filter(p => p.blank).map(p => p.page).join(", ") || "none"}), ${pages.reduce((s, p) => s + p.words, 0)} words; cache/nks.txt sha256 ${sha256(full)}`);
