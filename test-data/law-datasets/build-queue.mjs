#!/usr/bin/env node
// Build the scouting queue: one entry per law x kingdom slice, joined to the claim statements, the
// datasets the assessors already named and what the per-claim scouts already found.
//
//   node test-data/law-datasets/build-queue.mjs            # writes queue/<law>/<kingdom>.json
//
// Needs docs/claims.json. No dependencies (Node 20+).

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { LAWS, REPO, ROOT, modelFor, slices } from "./lib.mjs";

const claims = Object.fromEntries(JSON.parse(readFileSync(join(REPO, "docs/claims.json"), "utf8")).claims.map(c => [c.id, c]));
const projectOf = id => id.startsWith("thompson1917-") ? "thompson-growth-form" : id.startsWith("darwin1859-") ? "darwin-origin"
  : id.startsWith("wolfram2002-") ? "wolfram-nks" : id.startsWith("levin-") ? "levin-papers" : "math-bio-claims";

// Assessor-named datasets per claim.
const named = new Map();
for (const project of readdirSync(join(REPO, "claim-sources"))) {
  const raw = join(REPO, "claim-sources", project, "assessment/raw");
  if (!existsSync(raw)) continue;
  for (const assessor of readdirSync(raw)) {
    const dir = join(raw, assessor);
    let files = []; try { files = readdirSync(dir).filter(f => f.endsWith(".json")); } catch { continue; }
    for (const f of files) {
      let d; try { d = JSON.parse(readFileSync(join(dir, f), "utf8")); } catch { continue; }
      for (const a of Array.isArray(d) ? d : d?.assessments ?? []) {
        if (!a?.claim_id) continue;
        for (const ds of a.candidate_datasets ?? []) {
          const name = typeof ds === "string" ? ds : ds?.name; if (!name) continue;
          const m = named.get(a.claim_id) ?? named.set(a.claim_id, new Map()).get(a.claim_id);
          const e = m.get(name) ?? m.set(name, { name, url: ds?.url ?? null, suggested_by: [] }).get(name);
          if (!e.suggested_by.includes(assessor)) e.suggested_by.push(assessor);
        }
      }
    }
  }
}

const claimScouted = id => {
  const p = join(REPO, "test-data/dataset-scouting", projectOf(id), id, "datasets.json");
  if (!existsSync(p)) return null;
  try {
    const d = JSON.parse(readFileSync(p, "utf8"));
    return { status: d.status, datasets: (d.datasets ?? []).filter(x => ["holds", "partial"].includes(x.verdict)).map(x => ({ name: x.name, landing_url: x.landing_url, verdict: x.verdict })) };
  } catch { return null; }
};

let n = 0;
for (const { law, kingdom } of slices()) {
  const L = LAWS.laws.find(l => l.id === law);
  const entry = {
    law_id: law, kingdom, title: L.title,
    scout_model: modelFor(law, "scout"),
    look_for_in_this_kingdom: L.kingdoms[kingdom],
    variables_needed: L.variables,
    claims: L.claims.map(id => ({
      id, label: claims[id]?.label, statement: claims[id]?.statement, quote: claims[id]?.quote ?? null,
      assessor_named_datasets: [...(named.get(id)?.values() ?? [])].sort((a, b) => b.suggested_by.length - a.suggested_by.length),
      claim_scouting: claimScouted(id),
    })),
    other_kingdoms_hint: Object.fromEntries(Object.entries(L.kingdoms).filter(([k]) => k !== kingdom)),
    output: `test-data/law-datasets/records/${law}/${kingdom}.json`,
    instructions: "test-data/law-datasets/INSTRUCTIONS.md",
    organisms_datasets: "test-data/organisms/merged/datasets.json (provenanced dataset records keyed by taxon; reuse by id where it covers your variables)",
  };
  const dir = join(ROOT, "queue", law);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, `${kingdom}.json`), JSON.stringify(entry, null, 2) + "\n");
  n++;
}
console.log(`${n} queue entries written to test-data/law-datasets/queue/`);
