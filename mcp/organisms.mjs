// Organisms: every animal taxon Darwin and Thompson mention, the datasets vendored for each, and
// the per-taxon dataset-coverage ranking. Reads test-data/organisms/merged/{taxa,datasets,mentions,coverage}.json;
// rebuild with `node test-data/organisms/merge.mjs && node test-data/organisms/coverage.mjs`.

import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { REPO } from "./lib.mjs";

const MERGED = join(REPO, "test-data/organisms/merged");
const FILES = ["taxa", "datasets", "mentions", "coverage"];

let cache = null;

function load() {
  const stamp = FILES.map(f => statSync(join(MERGED, `${f}.json`)).mtimeMs).join(":");
  if (cache?.stamp === stamp) return cache.data;
  const data = Object.fromEntries(FILES.map(f => [f, JSON.parse(readFileSync(join(MERGED, `${f}.json`), "utf8"))]));
  data.coverageByKey = new Map(data.coverage.taxa.map(r => [r.key, r]));
  data.taxaByKey = new Map(data.taxa.map(t => [t.key, t]));
  data.datasetsById = new Map(data.datasets.map(d => [d.id, d]));
  cache = { stamp, data };
  return data;
}

const has = (value, needle) => String(value ?? "").toLowerCase().includes(needle.toLowerCase());
const mean = xs => (xs.length ? +(xs.reduce((a, b) => a + b, 0) / xs.length).toFixed(1) : null);

export const AXIS_IDS = ["genome", "bioelectric", "barcode", "traits", "morphology3d", "phylogeny", "occurrence", "fossil", "conservation", "taxonomy"];

const SORTS = {
  score: (a, b) => b.score - a.score || b.mention_count - a.mention_count,
  "score-asc": (a, b) => a.score - b.score || b.mention_count - a.mention_count,
  mentions: (a, b) => b.mention_count - a.mention_count || b.score - a.score,
  datasets: (a, b) => b.n_datasets - a.n_datasets,
  name: (a, b) => a.accepted_name.localeCompare(b.accepted_name),
};
export const SORT_KEYS = Object.keys(SORTS);

const GROUPS = {
  class: r => r.class ?? "unknown",
  rank: r => r.rank,
  project: r => r.projects.join("+"),
  genomeLevel: r => r.genome.level ?? "none",
};
export const GROUP_KEYS = Object.keys(GROUPS);

const findTaxon = (data, id) => {
  const needle = String(id).toLowerCase();
  return data.taxa.find(t => t.key.toLowerCase() === needle || t.slug === needle || t.accepted_name.toLowerCase() === needle)
    ?? data.taxa.find(t => t.names_as_written.some(n => n.toLowerCase() === needle) || t.vernacular.some(n => n.toLowerCase() === needle));
};

export function browseOrganisms({
  text, taxonClass, rank, project, hasAxis = [], missingAxis = [], genomeLevel, minScore, maxScore, minMentions = 0,
  sort = "score", groupBy, limit = 20,
} = {}) {
  const { coverage } = load();
  for (const a of [...hasAxis, ...missingAxis]) if (!AXIS_IDS.includes(a)) throw new Error(`axis must be one of ${AXIS_IDS.join(", ")}`);
  const hits = coverage.taxa.filter(r =>
    (!text || has(r.accepted_name, text) || has(r.slug, text))
    && (!taxonClass || has(r.class, taxonClass))
    && (!rank || r.rank === rank)
    && (!project || r.projects.some(p => has(p, project)))
    && hasAxis.every(a => r.axes[a] > 0)
    && missingAxis.every(a => !r.axes[a])
    && (!genomeLevel || (genomeLevel === "none" ? !r.genome.level : r.genome.level === genomeLevel))
    && (minScore == null || r.score >= minScore)
    && (maxScore == null || r.score <= maxScore)
    && r.mention_count >= minMentions);

  const axisCounts = rows => Object.fromEntries(AXIS_IDS.map(a => [a, rows.filter(r => r.axes[a] > 0).length]));

  if (groupBy) {
    if (!GROUPS[groupBy]) throw new Error(`groupBy must be one of ${GROUP_KEYS.join(", ")}`);
    const groups = new Map();
    for (const r of hits) {
      const k = GROUPS[groupBy](r);
      (groups.get(k) ?? groups.set(k, []).get(k)).push(r);
    }
    return {
      generated: coverage.generated, matched: hits.length, groupBy,
      groups: [...groups].map(([group, rs]) => ({
        group, taxa: rs.length, meanScore: mean(rs.map(r => r.score)), mentions: rs.reduce((s, r) => s + r.mention_count, 0),
        axisCoverage: axisCounts(rs),
      })).sort((a, b) => b.taxa - a.taxa),
    };
  }

  if (!SORTS[sort]) throw new Error(`sort must be one of ${SORT_KEYS.join(", ")}`);
  return {
    generated: coverage.generated, axes: coverage.axes, maxScore: coverage.max_score, matched: hits.length,
    axisCoverage: axisCounts(hits),
    taxa: [...hits].sort(SORTS[sort]).slice(0, Math.min(Number(limit) || 20, 1000)).map(r => ({
      position: r.position, key: r.key, slug: r.slug, name: r.accepted_name, rank: r.rank, class: r.class,
      projects: r.projects, mentions: r.mention_count, datasets: r.n_datasets, score: r.score,
      axes: r.axes, genome: r.genome.level ? { level: r.genome.level, assemblies: r.genome.n_assemblies, busco: r.genome.busco_complete_fraction, annotated: r.genome.annotated } : null,
      missing: r.missing,
    })),
  };
}

export function getOrganism({ id, includeMentions = true } = {}) {
  if (!id) throw new Error("id is required (taxon key like gbif:2495414, slug, or accepted name)");
  const data = load();
  const t = findTaxon(data, id);
  if (!t) throw new Error(`No taxon matches "${id}"`);
  const cov = data.coverageByKey.get(t.key);
  const datasets = t.datasets.map(did => data.datasetsById.get(did)).filter(Boolean).map(d => ({
    id: d.id, label: d.label, identifier: d.identifier, doi: d.doi, license: d.license, issued: d.issued,
    measurement_technique: d.measurement_technique, role: d.role, counts: d.counts, distributions: d.distributions,
    integrity: d.integrity, n_taxa_covered: d.taxa.length,
  }));
  return {
    taxon: t,
    coverage: cov ? { position: cov.position, score: cov.score, axes: cov.axes, genome: cov.genome, missing: cov.missing } : null,
    datasets,
    mentions: includeMentions ? data.mentions.filter(m => m.taxon_key === t.key).map(({ taxon_slug, taxon_key, ...m }) => m) : undefined,
  };
}

export function organismsOverview() {
  const { taxa, datasets, mentions, coverage } = load();
  const species = coverage.taxa.filter(r => /species/.test(r.rank));
  return {
    generated: coverage.generated, taxa: taxa.length, speciesRank: species.length, datasets: datasets.length, mentions: mentions.length,
    axes: coverage.axes.map(a => ({
      ...a, datasets: coverage.dataset_axes?.[a.id] ?? 0,
      taxaCovered: coverage.taxa.filter(r => r.axes[a.id] > 0).length,
      speciesCovered: species.filter(r => r.axes[a.id] > 0).length,
    })),
    genomeLevels: coverage.taxa.reduce((m, r) => { const k = r.genome.level ?? "none"; m[k] = (m[k] ?? 0) + 1; return m; }, {}),
    meanScore: mean(coverage.taxa.map(r => r.score)), meanSpeciesScore: mean(species.map(r => r.score)),
  };
}
