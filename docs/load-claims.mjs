// Every claim in the repo in one shape: Darwin and the math-bio key claims from their verified
// files, Thompson and Wolfram from their extraction drafts until a verified claims.json exists.
// `key` hashes the label and statement, so it survives a draft being given its final id.
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
export const claimKey = c => createHash("sha256").update(`${c.label}\n${c.text}`.replace(/\s+/g, " ").trim()).digest("hex").slice(0, 16);

export function loadClaims() {
  const readJson = p => JSON.parse(readFileSync(p, "utf8"));
  const ls = (p, re) => (existsSync(p) ? readdirSync(p).filter(f => re.test(f)).sort() : []);
  const jsonl = p => (existsSync(p) ? readFileSync(p, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l)) : []);
  const mean = xs => (xs.length ? Math.round((1000 * xs.reduce((a, b) => a + b, 0)) / xs.length) / 1000 : null);
  const chapterTitles = file => {
    const m = existsSync(file) && readFileSync(file, "utf8").match(/const CHAPTER_TITLES = (\{[\s\S]*?\});/);
    return m ? Function(`return (${m[1]})`)() : {};
  };
  const ASSESSOR_LABEL = Object.fromEntries(readJson(join(ROOT, "darwin-origin/assessment/assessors.json")).map(a => [a.id, a.modelLabel]));
  const claims = [];

  // Publication status from a book project's manifest.jsonl (Darwin, Thompson, Wolfram share publish.mjs).
  const bookLinks = dir => {
    const m = jsonl(join(ROOT, dir, "nanopubs/manifest.jsonl"));
    return id => {
      const prod = m.find(x => x.id === id && x.registry === "production");
      const test = m.find(x => x.id === id && x.registry === "test");
      return prod ? { uri: prod.trustyUri, registry: "production" } : test ? { uri: test.trustyUri, registry: "test" } : { uri: null, registry: null };
    };
  };

  // Per-claim assessor numbers from a book project's merged assessments, falling back to raw batches.
  const bookAssessments = dir => {
    const merged = join(ROOT, dir, "assessment/assessments.json");
    let rows = existsSync(merged) ? readJson(merged).assessments : [];
    if (!rows.length) {
      const raw = join(ROOT, dir, "assessment/raw");
      for (const who of ls(raw, /^[a-z]/)) for (const f of ls(join(raw, who), /\.json$/)) {
        try { rows.push(...readJson(join(raw, who, f)).map(r => ({ assessor: who, ...r }))); } catch {}
      }
    }
    const by = {};
    for (const r of rows) (by[r.claim_id] ??= []).push({
      who: ASSESSOR_LABEL[r.assessor] ?? r.assessor, verdict: r.verdict, overall: r.overall ?? null, confidence: r.confidence ?? null,
      operationalization: r.operationalization, datasets: (r.candidate_datasets || []).map(d => ({ name: d.name, url: d.url })),
    });
    return id => by[id] ?? [];
  };

  function addBook({ dir, thinker, work, year, idPrefix, chapterOf, titles }) {
    const verified = join(ROOT, dir, "claims.json");
    const link = bookLinks(dir), assess = bookAssessments(dir);
    let rows, draft = false;
    if (existsSync(verified)) rows = readJson(verified).claims;
    else {
      draft = true;
      rows = ls(join(ROOT, dir, "extraction"), /^[A-Z]-.*\.json$/).flatMap(f => {
        try { return readJson(join(ROOT, dir, "extraction", f)).map((c, i) => ({ ...c, id: `${idPrefix}-draft-${f.replace(/\.json$/, "")}-${i + 1}` })); }
        catch { return []; }
      });
    }
    for (const c of rows) {
      const ch = String(chapterOf(c));
      const a = assess(c.id);
      const { uri, registry } = link(c.id);
      claims.push({
        id: c.id, label: c.label, text: c.claim, quote: c.quote, kind: c.claim_kind, scope: c.scope,
        thinker, year, work, section: ch === "Introduction" ? "Introduction" : `Ch. ${ch}${titles[ch] ? `: ${titles[ch]}` : ""}`,
        locator: c.lineStart ? `lines ${c.lineStart}–${c.lineEnd}` : c.line ? `line ${c.line}` : c.pageStart ? `p. ${c.pageStart}` : c.page ? `p. ${c.page}` : "",
        status: "untested", statusNote: "Extracted from the text; not yet tested against data.",
        draft, assess: a, resolvability: mean(a.map(x => x.overall).filter(v => v != null)), confidence: mean(a.map(x => x.confidence).filter(v => v != null)),
        uri, registry,
      });
    }
  }

  addBook({ dir: "darwin-origin", thinker: "Charles Darwin", work: "On the Origin of Species", year: 1859, idPrefix: "darwin1859",
    chapterOf: c => c.chapter, titles: chapterTitles(join(ROOT, "darwin-origin/build/generate.mjs")) });

  const thompsonTitles = chapterTitles(join(ROOT, "thompson-growth-form/build/generate.mjs"));
  addBook({ dir: "thompson-growth-form", thinker: "D'Arcy Wentworth Thompson", work: "On Growth and Form", year: 1917, idPrefix: "thompson1917",
    chapterOf: c => c.chapter,
    // generate.mjs is still a copy of Darwin's until the Thompson build is adapted; ignore its titles then.
    titles: /Variation under Domestication/.test(Object.values(thompsonTitles).join()) ? {} : thompsonTitles });

  const nksIndex = existsSync(join(ROOT, "wolfram-nks/inputs/pages.json")) ? readJson(join(ROOT, "wolfram-nks/inputs/pages.json")) : { chapters: [] };
  addBook({ dir: "wolfram-nks", thinker: "Stephen Wolfram", work: "A New Kind of Science", year: 2002, idPrefix: "wolfram2002",
    chapterOf: c => c.chapter ?? nksIndex.chapters.filter(x => x.startPage <= (c.pageStart ?? c.page)).at(-1)?.n ?? "?",
    titles: chapterTitles(join(ROOT, "wolfram-nks/build/generate.mjs")) });

  // Mathematical-biology key claims: formal status as recorded in key-claims.json.
  const MATH = join(ROOT, "math-bio-theorems");
  const keyClaims = readJson(join(MATH, "claims/key-claims.json")).claims;
  const mathManifest = readJson(join(MATH, "nanopubs/manifest.json")).nanopubs;
  const formalStatus = c => {
    const fs = (c.context.match(/Formal status:\s*([^]*)$/) || [, ""])[1].toLowerCase();
    if (/refuted as stated|largely abandoned/.test(fs)) return "refuted";
    if (/not a mathematical|framework rather than/.test(fs) || c.kind !== "model-theorem") return "untested";
    if (/not in general|is open|conjectur/.test(fs)) return "partial";
    return "proved";
  };
  for (const c of keyClaims) {
    const m = mathManifest.find(n => n.claim.endsWith(`/${c.id}`));
    const fsText = (c.context.match(/Formal status:\s*([^]*)$/) || [, ""])[1];
    claims.push({
      id: c.id, label: c.label, text: c.statement, notation: c.notation, context: c.context, test: c.proposed_test, kind: c.kind,
      thinker: c.thinker, year: c.paper.year, work: c.paper.title, section: `${c.paper.title} (${c.paper.year})`,
      doi: c.paper.doi, status: formalStatus(c), statusNote: fsText ? `Formal status recorded in key-claims.json: ${fsText}` : "",
      draft: false, assess: [], resolvability: null, confidence: null,
      uri: m?.trustyUri ?? null, registry: m?.productionRegistry ? "production" : m?.trustyUri ? "test" : null,
    });
  }
  for (const c of claims) c.key = claimKey(c);
  return claims;
}
