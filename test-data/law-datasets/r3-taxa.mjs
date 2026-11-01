#!/usr/bin/env node
// Remediation round 3 (process: taxon-and-age-resolver, a script, no model). Resolves every taxon in a
// slice against GBIF (and PBDB for fossils), records the identifiers, flags a kingdom that does not
// match the slice, and checks a fossil source's stated geologic age against the taxon's PBDB range.
// It flags; it never drops (round 5 adjudicates the flags).
//
//   node test-data/law-datasets/r3-taxa.mjs log-spiral/fossils [more slices]   |  --all
//
// No dependencies (Node 20+).

import { existsSync } from "node:fs";
import { http, now, readSlice, writeSlice, slices, slicePath } from "./lib.mjs";

const gbifCache = new Map(), pbdbCache = new Map();
const KINGDOM_OK = { plants: ["Plantae", "Chromista", "Fungi", "Protozoa"], animals: ["Animalia"], fossils: null };

async function gbif(name) {
  if (gbifCache.has(name)) return gbifCache.get(name);
  const r = await http(`https://api.gbif.org/v1/species/match?name=${encodeURIComponent(name)}&verbose=false`, { readBody: true });
  let v = null;
  if (r.ok) { try { const j = JSON.parse(r.text); v = j.usageKey ? { gbif_key: j.usageKey, canonical: j.canonicalName ?? j.scientificName, rank: j.rank, kingdom: j.kingdom ?? null, phylum: j.phylum ?? null, match: j.matchType, confidence: j.confidence } : { match: j.matchType ?? "NONE" }; } catch {} }
  gbifCache.set(name, v);
  return v;
}

async function pbdb(name) {
  if (pbdbCache.has(name)) return pbdbCache.get(name);
  const r = await http(`https://paleobiodb.org/data1.2/taxa/single.json?name=${encodeURIComponent(name)}&show=app`, { readBody: true });
  let v = null;
  if (r.ok) { try { const x = JSON.parse(r.text).records?.[0]; if (x) v = { pbdb_id: x.oid, rank: x.rnk, first_ma: x.fea ?? null, last_ma: x.lea ?? null, occurrences: x.noc ?? null }; } catch {} }
  pbdbCache.set(name, v);
  return v;
}

export async function resolveSlice(law, kingdom) {
  const rec = readSlice(law, kingdom);
  if (!rec) return null;
  rec.remediation ??= [];
  const counts = { taxa: 0, resolved: 0, unresolved: 0, kingdom_flags: 0, age_flags: 0, pbdb: 0 };
  for (const s of rec.sources) {
    for (const t of s.taxa ?? []) {
      if (!t.name || /^(various|multiple|many|n\/a|unspecified)/i.test(t.name)) continue;
      counts.taxa++;
      const g = await gbif(t.name);
      if (g?.gbif_key) {
        counts.resolved++;
        t.resolved = { ...g, resolved_by: "r3 GBIF species/match", at: now() };
        const ok = KINGDOM_OK[kingdom];
        if (ok && g.kingdom && !ok.includes(g.kingdom)) { (s.flags ??= []); if (!s.flags.includes("taxon-kingdom-mismatch")) s.flags.push("taxon-kingdom-mismatch"); t.resolved.flag = `GBIF kingdom ${g.kingdom} in a ${kingdom} slice`; counts.kingdom_flags++; }
      } else { counts.unresolved++; t.resolved = { match: g?.match ?? "NONE", resolved_by: "r3 GBIF species/match", at: now() }; }
      if (kingdom === "fossils") {
        const p = await pbdb(t.name);
        if (p) {
          counts.pbdb++;
          t.pbdb = { ...p, resolved_by: "r3 PBDB taxa/single", at: now() };
          const a = s.geologic_age;
          if (a && p.first_ma != null && p.last_ma != null && a.ma_min != null && a.ma_max != null) {
            const overlap = a.ma_max >= p.last_ma && a.ma_min <= p.first_ma;
            if (!overlap) { (s.flags ??= []); if (!s.flags.includes("age-outside-pbdb-range")) s.flags.push("age-outside-pbdb-range"); t.pbdb.flag = `source age ${a.ma_min}-${a.ma_max} Ma does not overlap PBDB range ${p.last_ma}-${p.first_ma} Ma`; counts.age_flags++; }
          }
        }
      }
    }
  }
  rec.remediation.push({ round: 3, process: "taxon-and-age-resolver", kind: "script", model: null, script: "test-data/law-datasets/r3-taxa.mjs", at: now(),
    summary: `Resolved ${counts.resolved} of ${counts.taxa} taxon mentions in GBIF${kingdom === "fossils" ? ` and ${counts.pbdb} in PBDB` : ""}; flagged ${counts.kingdom_flags} kingdom mismatches and ${counts.age_flags} age mismatches (round 5 adjudicates).`, counts });
  writeSlice(law, kingdom, rec);
  return counts;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const args = process.argv.slice(2);
  const list = args.includes("--all") ? slices().filter(s => existsSync(slicePath(s.law, s.kingdom))).map(s => [s.law, s.kingdom])
    : args.filter(a => !a.startsWith("--")).map(a => a.split("/"));
  for (const [law, kingdom] of list) {
    const c = await resolveSlice(law, kingdom);
    console.log(`${law}/${kingdom}`, c ? JSON.stringify(c) : "no record");
  }
}
