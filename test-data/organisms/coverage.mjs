#!/usr/bin/env node
// Rank organisms by how completely the vendored datasets describe them.
//
//   node test-data/organisms/coverage.mjs          # writes test-data/organisms/merged/coverage.json + COVERAGE.md
//
// Reads test-data/organisms/merged/{taxa,datasets}.json (run merge.mjs first). Each dataset record is
// assigned to one data axis, from its explicit `category` field when present, else from its
// id / label / measurement_technique. A taxon's coverage is the set of axes it has at least
// one dataset on; the genome axis is graded by assembly level. Axes we care about but have
// no records for yet (bioelectric, barcode) are kept so the gap is visible per organism.
//
// This measures how complete *our records* are, not how reliable the datasets are; dataset
// reliability (source authority, integrity, completeness, independence, authenticity) is a
// separate assessment pass per BEST_PRACTICES.md. No dependencies (Node 20+).

import { readFileSync, writeFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const MERGED = join(ROOT, "merged");
const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));

// Axis id -> { label, weight, how to detect }. Order is the column order in the report.
export const AXES = [
  { id: "genome", label: "genome sequencing", weight: 3, graded: true,
    re: /genome|assembly|\bgca_|\bgcf_|refseq|genbank assembly/ },
  { id: "bioelectric", label: "bioelectric / electrophysiology", weight: 3,
    re: /bioelectric|electrophysiolog|\bephys\b|neuroelectro|channelpedia|modeldb|patch[- ]clamp|membrane potential|\bvmem\b|\beeg\b|\becg\b|\bekg\b|electrogenic|electroreception|ion channel|allen (cell types|brain)|physionet|dandi/ },
  { id: "barcode", label: "DNA barcodes", weight: 1, re: /\bbold\b|barcode|\bcoi\b|cytochrome oxidase/ },
  { id: "traits", label: "life-history / trait tables", weight: 2,
    re: /anage|pantheria|avonet|eltontraits|amniote|fishbase|life-history|life history|trait/ },
  { id: "morphology3d", label: "3D morphology", weight: 1, re: /morphosource|phenome10k|\bct scan|micro-?ct|3d (media|mesh|model)/ },
  { id: "phylogeny", label: "phylogeny / divergence", weight: 1, re: /timetree|open-tree|opentree|open tree of life|divergence/ },
  { id: "occurrence", label: "occurrence records", weight: 1, re: /gbif-occ|\bobis|occurrence/ },
  { id: "fossil", label: "fossil record", weight: 1, re: /pbdb|paleobiology|fossil/ },
  { id: "conservation", label: "conservation status", weight: 0.5, re: /iucn|red list/ },
  { id: "taxonomy", label: "taxonomic resolution", weight: 0.5,
    re: /backbone|taxonomy|taxon items|taxon match|tnrs|worms|aphia|wikidata|ncbi-tax/ },
];
const AXIS = Object.fromEntries(AXES.map((a) => [a.id, a]));
const MAX_SCORE = AXES.reduce((s, a) => s + a.weight, 0);

// Assembly level -> fraction of the genome axis weight.
const LEVEL_FRACTION = { complete: 1, chromosome: 1, scaffold: 2 / 3, contig: 1 / 3 };

// Known dataset-id prefixes, tried before the keyword scan (labels of occurrence records
// mention "GBIF Backbone", taxonomy records mention "genome", etc.).
const ID_PREFIX = [
  [/^(gbif|obis)-occ/, "occurrence"],
  [/^ncbi-genome/, "genome"],
  [/^(pbdb|paleobiology)/, "fossil"],
  [/^(gbif-backbone|ncbi-tax|open-?tree|opentree|wikidata|worms)/, "taxonomy"],
  [/^(anage|pantheria|avonet|eltontraits|amniote|fishbase)/, "traits"],
  [/^morphosource/, "morphology3d"],
  [/^timetree/, "phylogeny"],
  [/^iucn/, "conservation"],
  [/^bold/, "barcode"],
];

export function classify(d) {
  if (d.category && AXIS[d.category]) return d.category;
  for (const [re, axis] of ID_PREFIX) if (re.test(d.id)) return axis;
  const text = `${d.id} ${d.label ?? ""} ${d.measurement_technique ?? ""} ${d.role ?? ""}`.toLowerCase();
  // Fossil before occurrence: PBDB records are also "occurrence" records.
  const order = ["genome", "bioelectric", "barcode", "morphology3d", "phylogeny", "conservation", "traits", "fossil", "occurrence", "taxonomy"];
  for (const id of order) if (AXIS[id].re.test(text)) return id;
  return "other";
}

function assemblyLevel(d) {
  const text = `${d.label ?? ""} ${d.measurement_technique ?? ""} ${JSON.stringify(d.counts ?? [])}`;
  const m = text.match(/complete genome|\bcomplete\b|chromosome|scaffold|contig/i);
  if (!m) return null;
  const w = m[0].toLowerCase();
  return w.startsWith("complete") ? "complete" : w;
}
const LEVEL_RANK = { complete: 4, chromosome: 3, scaffold: 2, contig: 1 };
const count = (d, re) => (d.counts ?? []).find((c) => re.test(c.property_id))?.value ?? null;

export function coverageFor(taxon, byId) {
  const axes = Object.fromEntries(AXES.map((a) => [a.id, 0]));
  const genome = { level: null, n_assemblies: null, busco_complete_fraction: null, annotated: false, assemblies: [] };
  for (const id of taxon.datasets ?? []) {
    const d = byId.get(id);
    if (!d) continue;
    const axis = classify(d);
    if (axis === "other") continue;
    axes[axis] += 1;
    if (axis === "genome") {
      const level = assemblyLevel(d);
      if (level && (!genome.level || LEVEL_RANK[level] > LEVEL_RANK[genome.level])) genome.level = level;
      const n = count(d, /^n_assemblies/);
      if (n !== null) genome.n_assemblies = Math.max(genome.n_assemblies ?? 0, Number(n));
      const b = count(d, /busco_complete/);
      if (b !== null) genome.busco_complete_fraction = Math.max(genome.busco_complete_fraction ?? 0, Number(b));
      if (count(d, /n_genes_annotated/) !== null || /refseq/i.test(d.label ?? "")) genome.annotated = true;
      genome.assemblies.push(d.id);
    }
  }
  let score = 0;
  for (const a of AXES) {
    if (!axes[a.id]) continue;
    score += a.graded ? a.weight * (LEVEL_FRACTION[genome.level] ?? 1 / 3) : a.weight;
  }
  const missing = AXES.filter((a) => !axes[a.id]).map((a) => a.id);
  return { axes, genome, score: Math.round((score / MAX_SCORE) * 1000) / 10, missing };
}

export function buildCoverage(taxa, datasets) {
  const byId = new Map(datasets.map((d) => [d.id, d]));
  const rows = taxa.map((t) => ({
    key: t.key,
    slug: t.slug,
    accepted_name: t.accepted_name,
    rank: t.rank,
    class: t.lineage?.class ?? t.lineage?.phylum ?? null,
    projects: t.projects,
    mention_count: t.mention_count,
    n_datasets: (t.datasets ?? []).length,
    ...coverageFor(t, byId),
  }));
  rows.sort((a, b) => b.score - a.score || b.mention_count - a.mention_count || a.accepted_name.localeCompare(b.accepted_name));
  rows.forEach((r, i) => (r.position = i + 1));
  const datasetAxes = {};
  for (const d of datasets) datasetAxes[classify(d)] = (datasetAxes[classify(d)] ?? 0) + 1;
  return { rows, datasetAxes };
}

// Taxa in our set with well-known electrophysiology literature or databases, so the
// bioelectric vendoring pass knows where to look first. Keys are accepted-name regexes.
const BIOELECTRIC_LEADS = [
  [/^Homo sapiens$/, "Allen Cell Types (human cortex patch-seq), PhysioNet (ECG/EEG), NeuroElectro"],
  [/^Mus musculus$/, "Allen Cell Types, NeuroElectro, DANDI/Neurodata Without Borders"],
  [/^Rattus/, "NeuroElectro (largest species share), ModelDB, DANDI"],
  [/^Loligo$|^Cephalopoda$|^Sepia$/, "Squid giant axon (Hodgkin–Huxley 1952 series), ModelDB HH models, cephalopod chromatophore ephys"],
  [/^Hydra$/, "Hydra nerve-net calcium imaging and pacemaker recordings (Dupre & Yuste 2017), Hydra single-cell atlas"],
  [/^Hirudo medicinalis$/, "Leech Retzius/sensory neuron recordings, ModelDB, NeuroElectro"],
  [/^Helix/, "Helix pomatia / aspersa giant neuron recordings, NeuroElectro gastropod entries"],
  [/^Apis mellifera$/, "Honeybee Kenyon cell and antennal lobe recordings, NeuroElectro"],
  [/^Anura$|^Salamandridae$/, "Xenopus/amphibian Vmem and embryonic bioelectric patterning (Levin lab datasets), NeuroElectro"],
  [/^Gallus gallus$/, "Chick embryo bioelectric and cardiac electrophysiology literature"],
  [/^Oryctolagus cuniculus$|^Felis catus$|^Canis|^Sus scrofa$|^Bos taurus$|^Ovis aries$/, "Cardiac electrophysiology (Purkinje, ventricular myocyte) datasets, PhysioNet animal records"],
  [/^Scyliorhinus/, "Elasmobranch electroreception (ampullae of Lorenzini) recordings"],
  [/^Anguilla$/, "Electroreception/electrosensory literature; compare Electrophorus for electrogenesis"],
  [/^Echinus$/, "Sea-urchin embryo membrane potential and ion-channel studies"],
  [/^Mytilus$|^Pecten$/, "Bivalve ciliary and adductor muscle electrophysiology"],
  [/^Tubularia$|^Hydractinia$/, "Hydrozoan pacemaker and epithelial conduction recordings"],
  [/^Homarus$/, "Lobster stomatogastric ganglion (STG) recordings, ModelDB STG models"],
  [/^Bombyx mori$/, "Silkmoth olfactory receptor neuron recordings"],
];

function main() {
  const taxa = readJson(join(MERGED, "taxa.json"));
  const datasets = readJson(join(MERGED, "datasets.json"));
  const { rows, datasetAxes } = buildCoverage(taxa, datasets);
  const today = new Date().toISOString().slice(0, 10);

  writeFileSync(join(MERGED, "coverage.json"), JSON.stringify({
    generated: today,
    axes: AXES.map(({ id, label, weight, graded }) => ({ id, label, weight, graded: !!graded })),
    max_score: MAX_SCORE,
    dataset_axes: datasetAxes,
    taxa: rows,
  }, null, 2) + "\n");

  const species = rows.filter((r) => /species/.test(r.rank));
  const covered = (set, id) => set.filter((r) => r.axes[id] > 0).length;
  const pct = (n, d) => (d ? `${Math.round((100 * n) / d)}%` : "–");
  const cell = (r, a) => {
    if (!r.axes[a.id]) return "·";
    if (a.id === "genome") return r.genome.level ? r.genome.level[0].toUpperCase() : "●";
    return "●";
  };
  const legend = AXES.map((a) => `${a.label} (w=${a.weight})`).join(", ");
  const header = `| # | taxon | class | mentions | score | ${AXES.map((a) => a.id).join(" | ")} |\n|---|---|---|---|---|${AXES.map(() => "---").join("|")}|\n`;
  const line = (r) => `| ${r.position} | ${r.accepted_name} | ${r.class ?? ""} | ${r.mention_count} | ${r.score} | ${AXES.map((a) => cell(r, a)).join(" | ")} |\n`;

  let md = `# Organisms: dataset coverage ranking\n\nGenerated by \`node test-data/organisms/coverage.mjs\` on ${today} from ${taxa.length} taxa and ${datasets.length} dataset records.\n\n`;
  md += `Score = weighted share of data axes with at least one vendored dataset (0–100). Axes and weights: ${legend}. `;
  md += `Genome is graded by best assembly level (C = chromosome/complete, S = scaffold, c = contig). `;
  md += `This ranks the completeness of our records per organism, not the reliability of the datasets.\n\n`;

  md += `## Coverage by axis\n\n| axis | dataset records | taxa covered (of ${rows.length}) | species-rank taxa covered (of ${species.length}) |\n|---|---|---|---|\n`;
  for (const a of AXES) md += `| ${a.label} | ${datasetAxes[a.id] ?? 0} | ${covered(rows, a.id)} (${pct(covered(rows, a.id), rows.length)}) | ${covered(species, a.id)} (${pct(covered(species, a.id), species.length)}) |\n`;
  if (datasetAxes.other) md += `| unclassified | ${datasetAxes.other} | | |\n`;

  const levels = {};
  for (const r of rows) if (r.axes.genome) levels[r.genome.level ?? "unknown"] = (levels[r.genome.level ?? "unknown"] ?? 0) + 1;
  md += `\n## Genome sequencing depth\n\n| best assembly level | taxa |\n|---|---|\n`;
  for (const k of ["complete", "chromosome", "scaffold", "contig", "unknown"]) if (levels[k]) md += `| ${k} | ${levels[k]} |\n`;
  const busco = rows.filter((r) => r.genome.busco_complete_fraction !== null);
  md += `\nTaxa with BUSCO completeness recorded: ${busco.length}; with annotation/RefSeq noted: ${rows.filter((r) => r.genome.annotated).length}.\n`;

  const hist = {};
  for (const r of species) { const b = Math.min(9, Math.floor(r.score / 10)) * 10; hist[b] = (hist[b] ?? 0) + 1; }
  md += `\n## Score distribution (species-rank taxa)\n\n| score band | taxa |\n|---|---|\n`;
  for (let b = 90; b >= 0; b -= 10) md += `| ${b}–${b + 9} | ${hist[b] ?? 0} |\n`;

  md += `\n## Most complete (species-rank, top 40)\n\n${header}`;
  for (const r of species.slice(0, 40)) md += line(r);

  md += `\n## Least complete (species-rank, bottom 40)\n\n${header}`;
  for (const r of species.slice(-40)) md += line(r);

  md += `\n## Most-mentioned taxa, any rank (top 40 by mentions)\n\n${header}`;
  for (const r of [...rows].sort((a, b) => b.mention_count - a.mention_count).slice(0, 40)) md += line(r);

  const chromNoTraits = species.filter((r) => r.genome.level && LEVEL_RANK[r.genome.level] >= 3 && !r.axes.traits);
  md += `\n## Chromosome-level genome but no trait table (${chromNoTraits.length})\n\n`;
  md += chromNoTraits.map((r) => `${r.accepted_name}`).join(", ") + "\n";
  const noGenome = species.filter((r) => !r.axes.genome && r.mention_count >= 3).sort((a, b) => b.mention_count - a.mention_count);
  md += `\n## Species mentioned ≥3 times with no genome assembly record (${noGenome.length})\n\n`;
  md += noGenome.map((r) => `${r.accepted_name} (${r.mention_count})`).join(", ") + "\n";

  const bio = rows.filter((r) => r.axes.bioelectric);
  md += `\n## Bioelectric / electrophysiology\n\n`;
  md += bio.length
    ? `Taxa with a bioelectric dataset: ${bio.map((r) => r.accepted_name).join(", ")}.\n`
    : `No taxon has a bioelectric or electrophysiology dataset yet; every organism scores 0 on this axis (weight ${AXIS.bioelectric.weight} of ${MAX_SCORE}).\n`;
  const leads = rows.filter((r) => BIOELECTRIC_LEADS.some(([re]) => re.test(r.accepted_name)));
  md += `\nTaxa in our set with known electrophysiology sources, as leads for the vendoring pass:\n\n| taxon | mentions | current score | where to look |\n|---|---|---|---|\n`;
  for (const r of leads.sort((a, b) => b.mention_count - a.mention_count)) {
    const lead = BIOELECTRIC_LEADS.find(([re]) => re.test(r.accepted_name))[1];
    md += `| ${r.accepted_name} | ${r.mention_count} | ${r.score} | ${lead} |\n`;
  }
  md += `\nDataset records for this axis should set \`"category": "bioelectric"\` explicitly; the keyword fallback in \`coverage.mjs\` is a safety net, not the convention.\n`;

  writeFileSync(join(MERGED, "COVERAGE.md"), md);
  console.log(`${rows.length} taxa ranked (${species.length} species-rank); axes: ${JSON.stringify(datasetAxes)} -> test-data/organisms/merged/{coverage.json,COVERAGE.md}`);
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
