// Every claim in the repo in one shape: Darwin and the math-bio key claims from their verified
// files, Thompson and Wolfram from their extraction drafts until a verified claims.json exists.
// `key` hashes the label and statement, so it survives a draft being given its final id.
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
export const MATH_KINDS = new Set(["mathematical-law", "mathematical", "model-theorem"]);
export const VERIFICATION = ["refuted", "untested", "partial", "literature", "lean"];
export const EVIDENCE = ["supports", "mixed", "refutes", "inconclusive"];
// What a test's data measured (test-data/claim-tests/README.md). Only `biological` shows that a
// claim holds in organisms; `computational` shows it holds in simulation or mathematics.
export const DATA_KINDS = ["biological", "physical", "computational", "none"];
const UNTESTED_NOTE = "Extracted from the text; not yet tested against data.";
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
  const ASSESSOR_LABEL = Object.fromEntries(readJson(join(ROOT, "claim-sources/darwin-origin/assessment/assessors.json")).map(a => [a.id, a.modelLabel]));
  const claims = [];

  // "Theorem" is a proof status, not a project. A claim is `proved` only when its mathematical
  // content has been established: either machine-checked in Lean 4 (a `formalized` entry in some
  // <project>/lean/reports/*.json, which per lean/INSTRUCTIONS.md means the module compiled with no
  // sorry and only the standard axioms) or recorded as proved in the literature (the formal status
  // in claim-sources/math-bio-claims/claims/key-claims.json). Everything else is `untested`, however it is
  // phrased in the source. Lean reports are keyed by claim id across every project.
  const lean = {}, leanDeclined = {};
  const projects = readdirSync(join(ROOT, "claim-sources")).map(d => `claim-sources/${d}`);
  for (const dir of projects.filter(d => existsSync(join(ROOT, d, "lean/reports")))) {
    for (const f of ls(join(ROOT, dir, "lean/reports"), /\.json$/)) {
      const module = `${dir}/lean/${readJson(join(ROOT, dir, "lean/reports", f)).find(r => r.lean_declaration)?.lean_declaration.split(".")[0] ?? "Lean"}/${f.replace(/\.json$/, ".lean")}`;
      for (const r of readJson(join(ROOT, dir, "lean/reports", f))) {
        if (r.status === "not-formalized" && r.reason) leanDeclined[r.claim_id] = r.reason;
        if (r.status !== "formalized" || !r.lean_theorems?.length) continue;
        lean[r.claim_id] = { module, declaration: r.lean_declaration, theorems: r.lean_theorems, assumptions: r.assumptions ?? "", scopeNote: r.scope_note ?? "", notation: r.notation ?? null };
      }
    }
  }

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

  function addBook({ dir, thinker, work, year, idPrefix, chapterOf, titles, perClaim = () => ({}) }) {
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
      const l = lean[c.id] ?? null;
      claims.push({
        id: c.id, label: c.label, text: c.claim, quote: c.quote, kind: c.claim_kind, scope: c.scope, notation: c.notation ?? l?.notation ?? null,
        thinker, year, work, section: ch === "Introduction" ? "Introduction" : `Ch. ${ch}${titles[ch] ? `: ${titles[ch]}` : ""}`,
        locator: c.lineStart ? `lines ${c.lineStart}–${c.lineEnd}` : c.line ? `line ${c.line}` : c.pageStart ? `p. ${c.pageStart}` : c.page ? `p. ${c.page}` : "",
        status: l ? "proved" : "untested", proof: l ? "lean" : null,
        statusNote: l ? `Mathematical core machine-checked in Lean 4 (${l.module}: ${l.theorems.join(", ")}). ${l.scopeNote}`.trim()
          : leanDeclined[c.id] ? `Lean formalization attempted and declined: ${leanDeclined[c.id]}` : UNTESTED_NOTE,
        lean: l,
        draft, assess: a, resolvability: mean(a.map(x => x.overall).filter(v => v != null)), confidence: mean(a.map(x => x.confidence).filter(v => v != null)),
        uri, registry,
        ...perClaim(c),
      });
    }
  }

  addBook({ dir: "claim-sources/darwin-origin", thinker: "Charles Darwin", work: "On the Origin of Species", year: 1859, idPrefix: "darwin1859",
    chapterOf: c => c.chapter, titles: chapterTitles(join(ROOT, "claim-sources/darwin-origin/build/generate.mjs")) });

  const thompsonTitles = chapterTitles(join(ROOT, "claim-sources/thompson-growth-form/build/generate.mjs"));
  addBook({ dir: "claim-sources/thompson-growth-form", thinker: "D'Arcy Wentworth Thompson", work: "On Growth and Form", year: 1917, idPrefix: "thompson1917",
    chapterOf: c => c.chapter,
    // generate.mjs is still a copy of Darwin's until the Thompson build is adapted; ignore its titles then.
    titles: /Variation under Domestication/.test(Object.values(thompsonTitles).join()) ? {} : thompsonTitles });

  const nksIndex = existsSync(join(ROOT, "claim-sources/wolfram-nks/inputs/pages.json")) ? readJson(join(ROOT, "claim-sources/wolfram-nks/inputs/pages.json")) : { chapters: [] };
  addBook({ dir: "claim-sources/wolfram-nks", thinker: "Stephen Wolfram", work: "A New Kind of Science", year: 2002, idPrefix: "wolfram2002",
    chapterOf: c => c.chapter ?? nksIndex.chapters.filter(x => x.startPage <= (c.pageStart ?? c.page)).at(-1)?.n ?? "?",
    titles: chapterTitles(join(ROOT, "claim-sources/wolfram-nks/build/generate.mjs")) });

  // Levin's papers: one project, many works, so work, year and section come from each claim's paper.
  const LEVIN = "claim-sources/levin-papers";
  const levinPapers = existsSync(join(ROOT, LEVIN, "inputs/sources.json")) ? readJson(join(ROOT, LEVIN, "inputs/sources.json")).papers : [];
  const levinWork = Object.fromEntries(levinPapers.map(p => [p.key, p]));
  addBook({ dir: LEVIN, thinker: "Michael Levin", idPrefix: "levin", chapterOf: () => "", titles: {},
    perClaim: c => {
      const p = levinWork[c.paper];
      return p ? { work: p.title, year: p.year, doi: p.doi, section: `${p.authors.split(",")[0]} ${p.year}, ${p.title}${c.section ? ` › ${c.section}` : ""}` } : {};
    } });

  // Aristotle: three works in one project; the year is the conventional dating (c. 350 BCE) as a negative number.
  const ARISTOTLE = "claim-sources/aristotle-biology";
  const aristotleWorks = existsSync(join(ROOT, ARISTOTLE, "inputs/sources.json")) ? readJson(join(ROOT, ARISTOTLE, "inputs/sources.json")).works : [];
  const aristotleWork = Object.fromEntries(aristotleWorks.map(w => [w.key, w]));
  addBook({ dir: ARISTOTLE, thinker: "Aristotle", year: -350, idPrefix: "aristotle", chapterOf: () => "", titles: {},
    perClaim: c => {
      const w = aristotleWork[c.work];
      return w ? { work: w.title, section: `${w.title}, Book ${c.book}${c.section ? `, ${c.section}` : ""}` } : {};
    } });

  // Key-claim projects (claim-sources/<project>/claims/key-claims.json: math-bio-claims,
  // plant-hygromorph-mechanics): formal status as recorded in each claim's context. Being in such a
  // project does not make a claim a theorem; only a recorded proof (or a Lean report) does.
  const formalStatus = c => {
    const fs = (c.context.match(/Formal status:\s*([^]*)$/) || [, ""])[1].toLowerCase();
    if (/refuted as stated|largely abandoned/.test(fs)) return "refuted";
    if (/not a mathematical|framework rather than/.test(fs) || c.kind !== "model-theorem") return "untested";
    if (/^partial|not in general|is open|conjectur/.test(fs)) return "partial";
    return "proved";
  };
  const keyClaimProjects = projects.filter(d => existsSync(join(ROOT, d, "claims/key-claims.json")));
  for (const dir of keyClaimProjects) for (const c of readJson(join(ROOT, dir, "claims/key-claims.json")).claims) {
    const manifestFile = join(ROOT, dir, "nanopubs/manifest.json");
    const m = existsSync(manifestFile) ? readJson(manifestFile).nanopubs.find(n => n.claim.endsWith(`/${c.id}`)) : null;
    const fsText = (c.context.match(/Formal status:\s*([^]*)$/) || [, ""])[1];
    const l = lean[c.id] ?? null, status = l ? "proved" : formalStatus(c);
    claims.push({
      id: c.id, label: c.label, text: c.statement, notation: c.notation, context: c.context, test: c.proposed_test, kind: c.kind,
      thinker: c.thinker, year: c.paper.year, work: c.paper.title, section: `${c.paper.title} (${c.paper.year})`,
      doi: c.paper.doi, seeAlso: c.see_also ?? [], status, proof: l ? "lean" : status === "proved" ? "literature" : null, lean: l,
      statusNote: fsText ? `Formal status recorded in ${dir}/claims/key-claims.json: ${fsText}` : "",
      draft: false, assess: [], resolvability: null, confidence: null,
      uri: m?.trustyUri ?? null, registry: m?.productionRegistry ? "production" : m?.trustyUri ? "test" : null,
    });
  }
  // `verification` refines `status` by how a proof was established, strongest last:
  // refuted < untested < partial < literature < lean. Assessor truth scores are opinions, not
  // verification, so they never raise it. A claim is `math` when it has a formal statement
  // (notation or a Lean formalization) or is a mathematical kind of claim, and a `theorem` only
  // when it is both math and proved.
  // `evidence` is the second axis: the verdict of a test against data in test-data/claim-tests/<project>/<id>/
  // result.json. It never changes `verification` or `theorem` (a proof is not evidence that
  // organisms satisfy the assumptions, and a data test is not a proof). test-data/claim-tests/README.md
  // requires pre-registration, so a test counts as pre-registered unless it says otherwise.
  const tests = {}, unkinded = [];
  const TESTS = join(ROOT, "test-data/claim-tests");
  // A claim's folder may hold its result at the top or in one subfolder per test run; the top-level one wins.
  const isDir = p => statSync(p).isDirectory();
  for (const p of ls(TESTS, /^[a-z]/).filter(p => isDir(join(TESTS, p)))) for (const id of ls(join(TESTS, p), /^[^.]/)) {
    const dir = join(TESTS, p, id);
    if (!isDir(dir)) continue;
    for (const rel of [".", ...ls(dir, /^[^.]/).filter(d => existsSync(join(dir, d, "result.json")))]) {
      const f = join(dir, rel, "result.json");
      if (!existsSync(f)) continue;
      const r = readJson(f);
      if (r.status !== "complete" || !EVIDENCE.includes(r.verdict) || tests[r.claim_id]) continue;
      if (!DATA_KINDS.includes(r.data_kind)) { unkinded.push(join("test-data/claim-tests", p, id, rel, "result.json")); continue; }
      tests[r.claim_id] = { verdict: r.verdict, confidence: r.confidence ?? null, preregistered: r.preregistered !== false, dataKind: r.data_kind,
        path: join("test-data/claim-tests", p, id, rel, "result.json"), hypothesis: r.hypothesis ?? "", datasets: (r.datasets || []).map(d => d.name),
        // The four test-contract fields (test-data/claim-tests/README.md); `explicit` is false when derived from the pre-registration fields.
        testContract: { expected_observation: r.test_contract?.expected_observation ?? r.pass_criterion ?? "",
          disconfirming_observation: r.test_contract?.disconfirming_observation ?? r.fail_criterion ?? "",
          admissible_datasets: r.test_contract?.admissible_datasets ?? (r.planned_datasets?.length ? `Planned datasets: ${r.planned_datasets.join(", ")}` : ""),
          inference_method: r.test_contract?.inference_method ?? r.method ?? "", explicit: !!r.test_contract },
        revisions: (r.revisions || []).map(v => ({ date: v.date, from: v.from, to: v.to, prompted_by: (v.prompted_by || []).map(x => x.agent) })),
        // A9 faithfulness (test-data/claim-tests/FAITHFULNESS.md): does the analysis measure what the claim asserts?
        // faithfulness.json is the first assessor, faithfulness.<assessor>.json a blind second opinion. `agreed` when
        // every assessor gave the same verdict; `contested` otherwise. A not-representative verdict never changes
        // `evidence` here; it is a published finding about the test.
        faithfulness: (() => {
          const files = ls(join(dir, rel), /^faithfulness(\.[a-z0-9-]+)?\.json$/).sort((a, b) => (a === "faithfulness.json" ? -1 : b === "faithfulness.json" ? 1 : a.localeCompare(b)));
          if (!files.length) return null;
          const by = files.map(f => { const a = readJson(join(dir, rel, f)); return { assessor: a.assessor?.model ?? f, verdict: a.verdict, confidence: a.confidence ?? null, file: join("test-data/claim-tests", p, id, rel, f) }; });
          const verdicts = new Set(by.map(a => a.verdict));
          return { verdict: by[0].verdict, assessors: by, status: verdicts.size === 1 ? "agreed" : "contested" };
        })() };
    }
  }
  if (unkinded.length) throw new Error(`Complete claim tests without data_kind (${DATA_KINDS.join(" | ")}):\n  ${unkinded.join("\n  ")}`);
  // MorphoEval audits in github.com/fractastical/morpholib that bear on a claim (test-data/morpholib/README.md).
  // `tests` = the audit measured the claim's own assertion on specimens; `models` = it simulates the
  // claim's mechanism. Their `verdict` grades the simulation, not the claim; `thompsonVerdict` is the
  // verdict on Thompson's claim itself. Like truth scores, neither changes `evidence`.
  const MORPHO = join(ROOT, "test-data/morpholib/links.json");
  const morpho = {};
  if (existsSync(MORPHO)) {
    const { claims: audits, links } = readJson(MORPHO);
    const byId = Object.fromEntries(audits.map(a => [a.id, a]));
    const ids = new Set(claims.map(c => c.id));
    const stale = links.filter(l => !ids.has(l.claim) || !byId[l.morpholib]).map(l => `${l.claim} <- ${l.morpholib}`);
    if (stale.length) throw new Error(`test-data/morpholib/links.json links unknown claims:\n  ${stale.join("\n  ")}`);
    for (const l of links) {
      const a = byId[l.morpholib];
      (morpho[l.claim] ??= []).push({ id: a.id, relation: l.relation, note: l.note, label: a.label, organism: a.organism,
        verdict: a.verdict, score: a.score, thompsonVerdict: a.thompson?.verdict ?? null, nanopub: a.nanopub, registry: a.registry, report: a.report });
    }
  }
  for (const c of claims) {
    c.morpholib = morpho[c.id] ?? [];
    c.key = claimKey(c);
    c.verification = c.status === "proved" ? c.proof : c.status;
    c.math = !!(c.notation || c.lean || MATH_KINDS.has(c.kind));
    c.theorem = c.math && c.status === "proved";
    c.dataTest = tests[c.id] ?? null;
    c.evidence = c.dataTest?.verdict ?? null;
    c.evidenceKind = c.dataTest?.dataKind ?? null;
    if (c.dataTest && c.statusNote === UNTESTED_NOTE) c.statusNote = "Extracted from the text; not proved.";
  }
  return claims;
}
