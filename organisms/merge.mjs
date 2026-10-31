#!/usr/bin/env node
// Merge all organism slices into one cross-project view keyed by taxon identifier.
//
//   node organisms/merge.mjs            # writes organisms/merged/{taxa,datasets,mentions}.json + SUMMARY.md
//
// Taxa from different slices are the same taxon when they share a GBIF usage key, else a
// Wikidata QID, else an NCBI taxid, else the slug. Shared-database dataset records that
// appear in several slices under the same id are merged by id (union of taxa, first
// metadata kept, differing distributions appended). No dependencies (Node 20+).

import { readdirSync, readFileSync, statSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const OUT = join(ROOT, "merged");

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const listJson = (d) => (existsSync(d) ? readdirSync(d).filter((f) => f.endsWith(".json")).sort() : []);
const uniq = (a) => [...new Set(a.filter((x) => x !== undefined && x !== null && x !== ""))];

function slices() {
  const out = [];
  for (const project of readdirSync(ROOT)) {
    const pd = join(ROOT, project);
    if (!statSync(pd).isDirectory() || project === "merged" || project === "node_modules") continue;
    for (const slice of readdirSync(pd)) {
      const sd = join(pd, slice);
      if (statSync(sd).isDirectory()) out.push({ project, slice, dir: sd });
    }
  }
  return out.sort((a, b) => `${a.project}/${a.slice}`.localeCompare(`${b.project}/${b.slice}`));
}

function taxonKey(t) {
  const i = t.identifiers ?? {};
  if (i.gbif_usage_key) return `gbif:${i.gbif_usage_key}`;
  if (i.wikidata_qid) return `wd:${i.wikidata_qid}`;
  if (i.ncbi_taxid) return `ncbi:${i.ncbi_taxid}`;
  return `slug:${t.slug}`;
}

const taxa = new Map(); // key -> merged taxon
const slugToKey = new Map(); // `${project}/${slice}/${slug}` -> key
const datasets = new Map(); // id -> merged dataset
const mentions = [];
const conflicts = [];
const perSlice = [];

for (const { project, slice, dir } of slices()) {
  const sliceTaxa = listJson(join(dir, "taxa")).map((f) => readJson(join(dir, "taxa", f)));
  const sliceDatasets = listJson(join(dir, "datasets")).map((f) => readJson(join(dir, "datasets", f)));
  const sliceMentions = existsSync(join(dir, "mentions.json")) ? readJson(join(dir, "mentions.json")) : [];
  perSlice.push({ project, slice, taxa: sliceTaxa.length, datasets: sliceDatasets.length, mentions: sliceMentions.length });

  for (const t of sliceTaxa) {
    const key = taxonKey(t);
    slugToKey.set(`${project}/${slice}/${t.slug}`, key);
    const ids = t.identifiers ?? {};
    let m = taxa.get(key);
    if (!m) {
      m = {
        key,
        slug: t.slug,
        accepted_name: t.accepted_name,
        rank: t.rank,
        vernacular: [],
        names_as_written: [],
        identifiers: {},
        lineage: t.lineage ?? {},
        projects: [],
        slices: [],
        mentioned_in: [],
        mention_count: 0,
        datasets: [],
        notes: [],
      };
      taxa.set(key, m);
    } else {
      if (m.accepted_name !== t.accepted_name)
        conflicts.push(`${key}: accepted_name "${m.accepted_name}" vs "${t.accepted_name}" (${project}/${slice}/${t.slug})`);
      if (m.rank !== t.rank) conflicts.push(`${key}: rank "${m.rank}" vs "${t.rank}" (${project}/${slice}/${t.slug})`);
    }
    for (const [k, v] of Object.entries(ids)) {
      if (v === null || v === undefined || v === "") continue;
      if (m.identifiers[k] !== undefined && m.identifiers[k] !== v)
        conflicts.push(`${key}: identifiers.${k} ${m.identifiers[k]} vs ${v} (${project}/${slice}/${t.slug})`);
      else m.identifiers[k] = v;
    }
    for (const [k, v] of Object.entries(t.lineage ?? {})) if (v && !m.lineage[k]) m.lineage[k] = v;
    m.vernacular = uniq([...m.vernacular, ...(t.vernacular ?? [])]);
    m.names_as_written = uniq([...m.names_as_written, ...(t.names_as_written ?? [])]);
    m.projects = uniq([...m.projects, project]);
    m.slices = uniq([...m.slices, `${project}/${slice}`]);
    m.mentioned_in = uniq([...m.mentioned_in, ...(t.mentioned_in ?? [])]);
    m.datasets = uniq([...m.datasets, ...(t.datasets ?? [])]);
    if (t.notes) m.notes.push(`${project}/${slice}: ${t.notes}`);
  }

  for (const d of sliceDatasets) {
    const taxaKeys = (d.taxa ?? []).map((s) => slugToKey.get(`${project}/${slice}/${s}`) ?? `slug:${s}`);
    let m = datasets.get(d.id);
    if (!m) {
      m = { ...d, taxa: uniq(taxaKeys), slices: [`${project}/${slice}`] };
      datasets.set(d.id, m);
    } else {
      m.taxa = uniq([...m.taxa, ...taxaKeys]);
      m.slices = uniq([...m.slices, `${project}/${slice}`]);
      for (const dist of d.distributions ?? []) {
        const same = (m.distributions ?? []).some((x) => x.download_url === dist.download_url && x.sha256 === dist.sha256);
        if (!same) (m.distributions ??= []).push({ ...dist, slice: `${project}/${slice}` });
      }
      for (const c of d.counts ?? []) {
        const same = (m.counts ?? []).some((x) => x.property_id === c.property_id && x.value === c.value);
        if (!same) {
          const clash = (m.counts ?? []).find((x) => x.property_id === c.property_id && x.value !== c.value && !x.slice);
          // Counts scoped to the slice's own taxa (n_rows_for_taxa, n_taxa_covered) differ by design.
          if (clash && /^n_/.test(c.property_id) && !/for_taxa|covered|listed/.test(c.property_id))
            conflicts.push(`dataset ${d.id}: ${c.property_id} ${clash.value} vs ${c.value} in ${project}/${slice} (check the queried key)`);
          (m.counts ??= []).push({ ...c, slice: `${project}/${slice}` });
        }
      }
      if (m.identifier !== d.identifier) m.alternate_identifiers = uniq([...(m.alternate_identifiers ?? []), d.identifier]);
    }
  }

  for (const x of sliceMentions) {
    mentions.push({ ...x, project, slice, taxon_key: slugToKey.get(`${project}/${slice}/${x.taxon_slug}`) ?? `slug:${x.taxon_slug}` });
  }
}

for (const m of taxa.values()) m.mention_count = mentions.filter((x) => x.taxon_key === m.key).length;
// Datasets referenced by a taxon but also covering it only via the dataset record.
for (const d of datasets.values()) for (const k of d.taxa) { const t = taxa.get(k); if (t && !t.datasets.includes(d.id)) t.datasets.push(d.id); }

const taxaOut = [...taxa.values()].sort((a, b) => a.accepted_name.localeCompare(b.accepted_name));
const datasetsOut = [...datasets.values()].sort((a, b) => a.id.localeCompare(b.id));

mkdirSync(OUT, { recursive: true });
writeFileSync(join(OUT, "taxa.json"), JSON.stringify(taxaOut, null, 2) + "\n");
writeFileSync(join(OUT, "datasets.json"), JSON.stringify(datasetsOut, null, 2) + "\n");
writeFileSync(join(OUT, "mentions.json"), JSON.stringify(mentions, null, 2) + "\n");

// Summary
const byAuthority = (k) => taxaOut.filter((t) => t.identifiers[k] !== undefined).length;
const byClass = {};
for (const t of taxaOut) byClass[t.lineage.class ?? t.lineage.phylum ?? "unknown"] = (byClass[t.lineage.class ?? t.lineage.phylum ?? "unknown"] ?? 0) + 1;
const source = (d) => (d.id.startsWith("gbif-") ? "GBIF occurrences" : d.id.startsWith("ncbi-genome") ? "NCBI genome assembly" : d.id.startsWith("pbdb") ? "Paleobiology Database" : d.label ?? d.id);
const bySource = {};
for (const d of datasetsOut) bySource[source(d)] = (bySource[source(d)] ?? 0) + 1;
const noDataset = taxaOut.filter((t) => t.datasets.length === 0);
const inBoth = taxaOut.filter((t) => t.projects.length > 1);

let md = `# Organisms: merged view\n\nGenerated by \`node organisms/merge.mjs\` on ${new Date().toISOString().slice(0, 10)}.\n\n`;
md += `| | count |\n|---|---|\n| slices merged | ${perSlice.length} |\n| mentions | ${mentions.length} |\n| distinct taxa | ${taxaOut.length} |\n| taxa in both Darwin and Thompson | ${inBoth.length} |\n| taxa with GBIF key | ${byAuthority("gbif_usage_key")} |\n| taxa with NCBI taxid | ${byAuthority("ncbi_taxid")} |\n| taxa with Wikidata QID | ${byAuthority("wikidata_qid")} |\n| taxa with WoRMS AphiaID | ${byAuthority("worms_aphia_id")} |\n| taxa with no dataset | ${noDataset.length} |\n| dataset records | ${datasetsOut.length} |\n| identifier conflicts | ${conflicts.length} |\n\n`;
md += `## Per slice\n\n| slice | mentions | taxa | datasets |\n|---|---|---|---|\n`;
for (const s of perSlice) md += `| ${s.project}/${s.slice} | ${s.mentions} | ${s.taxa} | ${s.datasets} |\n`;
md += `\n## Taxa by class\n\n| class | taxa |\n|---|---|\n`;
for (const [k, v] of Object.entries(byClass).sort((a, b) => b[1] - a[1])) md += `| ${k} | ${v} |\n`;
md += `\n## Datasets by source\n\n| source | records |\n|---|---|\n`;
for (const [k, v] of Object.entries(bySource).sort((a, b) => b[1] - a[1])) md += `| ${k} | ${v} |\n`;
md += `\n## Most-mentioned taxa\n\n| taxon | rank | mentions | projects | datasets |\n|---|---|---|---|---|\n`;
for (const t of [...taxaOut].sort((a, b) => b.mention_count - a.mention_count).slice(0, 40))
  md += `| ${t.accepted_name} | ${t.rank} | ${t.mention_count} | ${t.projects.join(", ")} | ${t.datasets.length} |\n`;
if (inBoth.length) {
  md += `\n## Taxa mentioned by both authors\n\n`;
  for (const t of inBoth) md += `- ${t.accepted_name} (${t.key})\n`;
}
if (noDataset.length) {
  md += `\n## Taxa with no dataset\n\n`;
  for (const t of noDataset) md += `- ${t.accepted_name} (${t.slices.join(", ")})\n`;
}
if (conflicts.length) {
  md += `\n## Identifier conflicts to resolve\n\n`;
  for (const c of conflicts) md += `- ${c}\n`;
}
writeFileSync(join(OUT, "SUMMARY.md"), md);

console.log(`${perSlice.length} slices, ${mentions.length} mentions, ${taxaOut.length} taxa, ${datasetsOut.length} datasets, ${conflicts.length} conflicts -> organisms/merged/`);
