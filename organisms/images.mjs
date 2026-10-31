#!/usr/bin/env node
// Vendor one representative image per merged taxon and collect the dates needed to draw a
// timeline for it.
//
//   node organisms/images.mjs            # fills organisms/images/thumbs/, writes manifest + timeline.json
//   node organisms/images.mjs --refresh  # re-query the APIs even for taxa already in the manifest
//
// Image source: the Wikidata item's P18 (image) claim, rendered as a Commons thumbnail no wider
// than THUMB_WIDTH px, with licence and attribution from the Commons extmetadata. Taxa without a
// P18 fall back to the first StillImage GBIF holds for the usage key. Thumbnails are small
// (tens of kB) and checksummed; licence and author are recorded so the attribution can travel
// with the image.
//
// Timeline source: Paleobiology Database `taxa/list?show=app` (first/last appearance in Ma and
// named intervals), GBIF species authorship (year of formal description), the `issued` year of
// our NCBI genome records, and the books the taxon is mentioned in (Darwin 1859, Thompson 1917).
//
// Outputs: organisms/images/manifest.json, organisms/merged/timeline.json. Rendering is done
// by organisms/timeline.py. No dependencies (Node 20+).

import { readFileSync, writeFileSync, mkdirSync, existsSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { join, dirname, extname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const MERGED = join(ROOT, "merged");
const IMAGES = join(ROOT, "images");
const THUMBS = join(IMAGES, "thumbs");
const MANIFEST = join(IMAGES, "manifest.json");
const TIMELINE = join(MERGED, "timeline.json");
const THUMB_WIDTH = 160;
const MAX_THUMB_BYTES = 400_000;
const UA = "delphisci-organisms/0.1 (https://github.com/fractastical/delphi; research use)";
const REFRESH = process.argv.includes("--refresh");
const BOOK_YEAR = { "darwin-origin": 1859, "thompson-growth-form": 1917 };

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const asArray = (x) => (Array.isArray(x) ? x : x.taxa ?? x.datasets ?? Object.values(x));
const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");
const chunk = (arr, n) => Array.from({ length: Math.ceil(arr.length / n) }, (_, i) => arr.slice(i * n, i * n + n));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const stripHtml = (s) => (s ?? "").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim() || null;

async function getJson(url, tries = 3) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": UA, Accept: "application/json" } });
      if (res.status === 429 || res.status >= 500) throw new Error(`HTTP ${res.status}`);
      if (!res.ok) return null;
      return await res.json();
    } catch (e) {
      if (i === tries - 1) { console.warn(`  ! ${url}: ${e.message}`); return null; }
      await sleep(1000 * (i + 1));
    }
  }
}
async function getBytes(url, tries = 5) {
  for (let i = 0; i < tries; i++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": UA } });
      if (res.status === 429 || res.status >= 500) throw new Error(`HTTP ${res.status}`);
      if (!res.ok) return null;
      return { buf: Buffer.from(await res.arrayBuffer()), type: res.headers.get("content-type") };
    } catch (e) {
      if (i === tries - 1) { console.warn(`  ! ${url}: ${e.message}`); return null; }
      await sleep(3000 * (i + 1));
    }
  }
}
// Commons thumbnails of animated GIFs / huge PNGs can exceed the 1 MB vendoring limit; ask for
// a narrower rendering (Commons accepts any width in the thumb path) before giving up.
async function getThumb(url) {
  let got = await getBytes(url);
  if (got && got.buf.length > MAX_THUMB_BYTES && /\/\d+px-/.test(url)) {
    got = await getBytes(url.replace(/\/\d+px-/, "/96px-"));
  }
  if (got && got.buf.length > MAX_THUMB_BYTES) return null;
  return got;
}
async function pool(items, n, fn) {
  const out = new Array(items.length);
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => {
    while (i < items.length) { const k = i++; out[k] = await fn(items[k], k); }
  }));
  return out;
}

// ---------------------------------------------------------------- images

// qid -> Commons file name. P18 of the item itself; when a taxon item has no P18 (common for
// taxon items whose common-name item carries the picture, e.g. Canis lupus familiaris vs "dog")
// fall back to the page image of its English Wikipedia article.
async function wikidataImages(qids) {
  const out = {};
  const enwiki = {};
  for (const batch of chunk(qids, 50)) {
    const url = `https://www.wikidata.org/w/api.php?action=wbgetentities&ids=${batch.join("|")}&props=claims|sitelinks&format=json`;
    const d = await getJson(url);
    for (const [qid, e] of Object.entries(d?.entities ?? {})) {
      const claims = e.claims?.P18 ?? [];
      const pick = claims.find((c) => c.rank === "preferred") ?? claims[0];
      const file = pick?.mainsnak?.datavalue?.value;
      if (file) out[qid] = file;
      else if (e.sitelinks?.enwiki?.title) enwiki[e.sitelinks.enwiki.title] = qid;
    }
  }
  const titles = Object.keys(enwiki);
  for (const batch of chunk(titles, 50)) {
    const url = `https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&piprop=name&redirects=1&format=json&titles=${encodeURIComponent(batch.join("|"))}`;
    const d = await getJson(url);
    const back = {};
    for (const r of d?.query?.normalized ?? []) back[r.to] = r.from;
    for (const r of d?.query?.redirects ?? []) back[r.to] = back[r.from] ?? r.from;
    for (const p of Object.values(d?.query?.pages ?? {})) {
      const qid = enwiki[back[p.title] ?? p.title];
      if (qid && p.pageimage) out[qid] = p.pageimage;
    }
  }
  return out;
}

async function commonsInfo(files) {
  const out = {};
  for (const batch of chunk(files, 50)) {
    const titles = batch.map((f) => "File:" + f).join("|");
    const url = "https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo&iiprop=url|extmetadata|size|mime" +
      `&iiurlwidth=${THUMB_WIDTH}&iiextmetadatafilter=License|LicenseShortName|LicenseUrl|Artist|Credit|ObjectName` +
      `&format=json&titles=${encodeURIComponent(titles)}`;
    const d = await getJson(url);
    const norm = Object.fromEntries((d?.query?.normalized ?? []).map((n) => [n.to, n.from]));
    for (const p of Object.values(d?.query?.pages ?? {})) {
      const ii = p.imageinfo?.[0];
      if (!ii) continue;
      const title = p.title;
      const key = (norm[title] ?? title).replace(/^File:/, "");
      const m = ii.extmetadata ?? {};
      out[key] = {
        commons_file: title,
        description_url: ii.descriptionurl,
        original_url: ii.url?.split("?")[0],
        thumb_url: ii.thumburl?.split("?")[0],
        mime: ii.mime,
        width: ii.width, height: ii.height,
        license: m.LicenseShortName?.value ?? m.License?.value ?? null,
        license_url: m.LicenseUrl?.value ?? null,
        author: stripHtml(m.Artist?.value),
        credit: stripHtml(m.Credit?.value),
      };
      // Also key by the normalised title so lookups with either spelling work.
      out[title.replace(/^File:/, "")] = out[key];
    }
  }
  return out;
}

async function gbifImage(key) {
  const d = await getJson(`https://api.gbif.org/v1/species/${key}/media?limit=20`);
  const r = (d?.results ?? []).find((x) => x.type === "StillImage" && x.identifier && /^https?:/.test(x.identifier));
  if (!r) return null;
  return {
    source: "gbif-media",
    description_url: r.references ?? `https://www.gbif.org/species/${key}`,
    original_url: r.identifier,
    thumb_url: r.identifier,
    license: r.license ?? null,
    author: r.creator ?? r.rightsHolder ?? null,
    credit: r.publisher ?? null,
  };
}

function thumbPath(slug, mime, url) {
  const byMime = { "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/webp": ".webp" };
  const ext = byMime[(mime ?? "").split(";")[0]] ?? (extname(new URL(url).pathname).toLowerCase() || ".jpg");
  return join(THUMBS, slug + ext);
}

// ---------------------------------------------------------------- timeline

async function pbdbRanges(names) {
  const out = {};
  for (const batch of chunk(names, 25)) {
    const url = `https://paleobiodb.org/data1.2/taxa/list.json?name=${encodeURIComponent(batch.join(","))}&show=app&vocab=pbdb`;
    const d = await getJson(url);
    for (const r of d?.records ?? []) {
      const rec = {
        pbdb_taxon_no: Number(r.taxon_no), pbdb_name: r.taxon_name, pbdb_rank: r.taxon_rank,
        is_extant: r.is_extant ?? null, n_occs: r.n_occs ?? 0,
        firstapp_max_ma: r.firstapp_max_ma ?? null, firstapp_min_ma: r.firstapp_min_ma ?? null,
        lastapp_max_ma: r.lastapp_max_ma ?? null, lastapp_min_ma: r.lastapp_min_ma ?? null,
        early_interval: r.early_interval ?? null, late_interval: r.late_interval ?? null,
      };
      for (const n of new Set([r.taxon_name, r.accepted_name])) if (n) (out[n.toLowerCase()] ??= []).push(rec);
    }
    await sleep(150);
  }
  return out;
}

function authorshipYear(s) {
  const m = (s ?? "").match(/\b(1[5-9]\d\d|20[0-2]\d)\b/);
  return m ? Number(m[1]) : null;
}

// ---------------------------------------------------------------- main

async function main() {
  mkdirSync(THUMBS, { recursive: true });
  const taxa = asArray(readJson(join(MERGED, "taxa.json")));
  const datasets = asArray(readJson(join(MERGED, "datasets.json")));
  const prev = existsSync(MANIFEST) && !REFRESH ? Object.fromEntries(readJson(MANIFEST).images.map((i) => [i.slug, i])) : {};
  const prevTl = existsSync(TIMELINE) && !REFRESH ? Object.fromEntries(readJson(TIMELINE).taxa.map((i) => [i.slug, i])) : {};
  const now = new Date().toISOString();

  // --- images
  const need = taxa.filter((t) => !prev[t.slug]?.thumb_path || !existsSync(join(ROOT, "..", prev[t.slug].thumb_path)));
  console.log(`images: ${taxa.length} taxa, ${need.length} to fetch`);
  const qids = [...new Set(need.map((t) => t.identifiers?.wikidata_qid).filter(Boolean))];
  const p18 = await wikidataImages(qids);
  console.log(`  wikidata P18 found for ${Object.keys(p18).length}/${qids.length} items`);
  const info = await commonsInfo([...new Set(Object.values(p18))]);
  console.log(`  commons imageinfo for ${Object.keys(info).length} files`);

  const images = { ...prev };
  let nCommons = 0, nGbif = 0, nNone = 0;
  await pool(need, 3, async (t) => {
    const qid = t.identifiers?.wikidata_qid;
    let meta = null;
    if (qid && p18[qid] && info[p18[qid]]) meta = { source: "wikimedia-commons", wikidata_qid: qid, ...info[p18[qid]] };
    if (!meta && t.identifiers?.gbif_usage_key) meta = await gbifImage(t.identifiers.gbif_usage_key);
    if (!meta) { nNone++; images[t.slug] = { slug: t.slug, key: t.key, accepted_name: t.accepted_name, source: null, retrieved_at: now }; return; }
    const got = await getThumb(meta.thumb_url);
    if (!got || !/^image\//.test(got.type ?? "")) { nNone++; images[t.slug] = { slug: t.slug, key: t.key, accepted_name: t.accepted_name, source: null, note: `thumbnail fetch failed: ${meta.thumb_url}`, retrieved_at: now }; return; }
    const path = thumbPath(t.slug, got.type, meta.thumb_url);
    writeFileSync(path, got.buf);
    meta.source === "wikimedia-commons" ? nCommons++ : nGbif++;
    images[t.slug] = {
      slug: t.slug, key: t.key, accepted_name: t.accepted_name,
      ...meta,
      thumb_path: "organisms/images/thumbs/" + path.split("/").pop(),
      thumb_width: THUMB_WIDTH, byte_size: got.buf.length, sha256: sha256(got.buf), retrieved_at: now,
    };
  });
  console.log(`  fetched: ${nCommons} from Commons, ${nGbif} from GBIF media, ${nNone} without image`);

  const imgList = taxa.map((t) => images[t.slug]).filter(Boolean);
  writeFileSync(MANIFEST, JSON.stringify({
    generated: now, thumb_width: THUMB_WIDTH,
    note: "One representative image per merged taxon. Source is the Wikidata P18 image rendered as a Commons thumbnail, else the first GBIF StillImage. Licence and author are as reported by the source; check them before reuse beyond this repo.",
    n_taxa: taxa.length, n_with_image: imgList.filter((i) => i.thumb_path).length,
    images: imgList,
  }, null, 1) + "\n");

  // --- timeline
  const needTl = taxa.filter((t) => !prevTl[t.slug]);
  console.log(`timeline: ${needTl.length} taxa to query`);
  const ranges = await pbdbRanges([...new Set(needTl.map((t) => t.accepted_name))]);
  console.log(`  pbdb records for ${Object.keys(ranges).length} names`);
  const gbifYears = {};
  await pool(needTl.filter((t) => t.identifiers?.gbif_usage_key), 8, async (t) => {
    const d = await getJson(`https://api.gbif.org/v1/species/${t.identifiers.gbif_usage_key}`);
    if (d) gbifYears[t.slug] = { authorship: d.authorship ?? null, year: authorshipYear(d.authorship), published_in: d.publishedIn ?? null };
  });
  console.log(`  gbif authorship for ${Object.keys(gbifYears).length} taxa`);

  const dsById = Object.fromEntries(datasets.map((d) => [d.id, d]));
  const tl = taxa.map((t) => {
    if (prevTl[t.slug]) return prevTl[t.slug];
    const genomes = t.datasets.map((id) => dsById[id]).filter((d) => d && /^ncbi-genome/.test(d.id) && d.issued)
      .map((d) => ({ dataset: d.id, year: Number(d.issued.slice(0, 4)), level: (d.label.match(/complete|chromosome|scaffold|contig/i) || [null])[0]?.toLowerCase() ?? null }))
      .sort((a, b) => a.year - b.year);
    // Homonyms (e.g. Echinus the genus vs. an order) come back as several records: prefer the
    // one whose rank matches ours, else the one with the most occurrences.
    const cands = ranges[t.accepted_name.toLowerCase()] ?? [];
    const norm = (r) => (r ?? "").replace(/\s*\(.*\)$/, "").toLowerCase();
    const f = cands.find((r) => norm(r.pbdb_rank) === norm(t.rank)) ?? cands.sort((a, b) => b.n_occs - a.n_occs)[0] ?? null;
    return {
      slug: t.slug, key: t.key, accepted_name: t.accepted_name, rank: t.rank, class: t.lineage?.class ?? null,
      vernacular: t.vernacular?.[0] ?? null, mention_count: t.mention_count,
      described: gbifYears[t.slug] ?? null,
      mentioned: t.projects.map((p) => ({ project: p, year: BOOK_YEAR[p] })).filter((m) => m.year),
      genomes,
      fossil: f,
      has_iucn: t.datasets.some((id) => /^iucn/.test(id)),
    };
  });
  writeFileSync(TIMELINE, JSON.stringify({
    generated: now,
    note: "Per-taxon dates for the timeline figures: formal description year (GBIF authorship), book mentions, NCBI assembly release years (from our dataset records), and the Paleobiology Database first/last appearance range (taxa/list show=app, base taxon only, not subtaxa). PBDB ranges for genus- and higher-rank taxa span all their fossil species.",
    sources: {
      pbdb: "https://paleobiodb.org/data1.2/taxa/list.json?name=<accepted names, comma-separated>&show=app&vocab=pbdb",
      gbif: "https://api.gbif.org/v1/species/<gbif_usage_key> (authorship field)",
    },
    n_taxa: tl.length, n_with_fossil_range: tl.filter((x) => x.fossil?.firstapp_max_ma != null).length,
    n_with_description_year: tl.filter((x) => x.described?.year).length,
    taxa: tl,
  }, null, 1) + "\n");
  const total = imgList.filter((i) => i.thumb_path).reduce((s, i) => s + i.byte_size, 0);
  console.log(`done: ${imgList.filter((i) => i.thumb_path).length} thumbnails (${(total / 1e6).toFixed(1)} MB), ${tl.filter((x) => x.fossil?.firstapp_max_ma != null).length} fossil ranges, ${tl.filter((x) => x.described?.year).length} description years`);
}

main().catch((e) => { console.error(e); process.exit(1); });
