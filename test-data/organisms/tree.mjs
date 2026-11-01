#!/usr/bin/env node
// Draw the organism inventory as a time-calibrated tree, with the claims that mention each
// taxon as colour-coded boxes beside it.
//
//   node test-data/organisms/tree.mjs             # reuse merged/tree.json if present, render images/tree.svg
//   node test-data/organisms/tree.mjs --refresh   # re-query Open Tree of Life
//
// Topology: Open Tree of Life. Every merged taxon's accepted name is matched with the TNRS
// (`/v3/tnrs/match_names`, exact matches only) and the matched OTT ids are sent to
// `/v3/tree_of_life/induced_subtree`, which returns the synthetic tree restricted to those taxa.
// A merged taxon that contains another merged taxon (an order and one of its species) comes
// back as an internal node, and is drawn there.
//
// Ages: the Paleobiology Database first appearance of each taxon from merged/timeline.json
// (collected by images.mjs). An internal node is placed at the oldest first appearance among
// its descendants, which is a lower bound on the clade's age, not a divergence-time estimate.
// Nodes with no PBDB record under them are drawn dashed at an arbitrary position.
//
// Claims: merged/taxa.json `mentioned_in` plus merged/mentions.json `source.claim_id`, coloured by
// docs/claims.json: theorem (Lean or literature proof), data verdict (supports / refutes / mixed /
// inconclusive), else untested. Each box links to docs/claim-graph.html?claim=<id>.
//
// Outputs: merged/tree.json (matches, Newick, per-taxon placement, retrieval time), images/tree.svg.
// No dependencies (Node 20+).

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = dirname(fileURLToPath(import.meta.url));
const REPO = join(ROOT, "..", "..");
const MERGED = join(ROOT, "merged");
const TREE_JSON = join(MERGED, "tree.json");
const SVG_OUT = join(ROOT, "images", "tree.svg");
const OTOL = "https://api.opentreeoflife.org/v3";
const UA = "delphisci-organisms/0.1 (https://github.com/fractastical/delphi; research use)";
const REFRESH = process.argv.includes("--refresh");
const CLAIM_URL = "https://fractastical.github.io/delphi/claim-graph.html?claim=";

const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const asArray = (x, k) => (Array.isArray(x) ? x : x[k] ?? Object.values(x));
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

// ---------------------------------------------------------------- inputs
const taxa = asArray(readJson(join(MERGED, "taxa.json")), "taxa");
const timeline = asArray(readJson(join(MERGED, "timeline.json")), "taxa");
const mentions = asArray(readJson(join(MERGED, "mentions.json")), "mentions");
const claims = asArray(readJson(join(REPO, "docs", "claims.json")), "claims");
const bySlug = new Map(taxa.map((t) => [t.slug, t]));
const fossilBySlug = new Map(timeline.map((t) => [t.slug, t.fossil ?? null]));
const claimById = new Map(claims.map((c) => [c.id, c]));

const claimsOf = new Map();
for (const t of taxa) for (const id of t.mentioned_in ?? []) (claimsOf.get(t.slug) ?? claimsOf.set(t.slug, new Set()).get(t.slug)).add(id);
for (const m of mentions) {
  const id = m.source?.claim_id;
  if (id && bySlug.has(m.taxon_slug)) (claimsOf.get(m.taxon_slug) ?? claimsOf.set(m.taxon_slug, new Set()).get(m.taxon_slug)).add(id);
}

// Claim colour classes, in the order boxes are drawn.
const CLASSES = [
  ["theorem", "Theorem (proof established)", "#1F4E79", "#1F4E79"],
  ["supports", "Data test: supports", "#2A9D8F", "#1F7A70"],
  ["mixed", "Data test: mixed", "#E9A23B", "#B87A1E"],
  ["inconclusive", "Data test: inconclusive", "#9FB3C8", "#6F8499"],
  ["refutes", "Data test: refutes", "#B22222", "#7F1818"],
  ["untested", "Claim, untested", "#FFFFFF", "#9A9A9A"],
];
const CLASS_RANK = Object.fromEntries(CLASSES.map(([k], i) => [k, i]));
function classify(c) {
  if (!c) return "untested";
  if (c.theorem) return "theorem";
  const v = c.data_test?.verdict ?? c.evidence;
  return typeof v === "string" && CLASS_RANK[v] !== undefined ? v : "untested";
}

// ---------------------------------------------------------------- Open Tree of Life
async function post(path, body) {
  for (let attempt = 0; attempt < 4; attempt++) {
    const r = await fetch(`${OTOL}/${path}`, {
      method: "POST", headers: { "content-type": "application/json", "user-agent": UA }, body: JSON.stringify(body),
    });
    const text = await r.text();
    let json = null;
    try { json = JSON.parse(text); } catch { /* fall through */ }
    if (r.ok && json) return json;
    // induced_subtree answers 400 with the list of unknown ids; the caller needs that.
    if (json && (json.unknown || json.broken)) return json;
    if (attempt === 3) throw new Error(`${path}: HTTP ${r.status} ${text.slice(0, 300)}`);
    await new Promise((res) => setTimeout(res, 1500 * (attempt + 1)));
  }
}

// Metazoan phyla in our lineages: matched in the TNRS "Animals" context so that homonyms in other
// kingdoms (Trigonia the bivalve vs Trigonia the plant) cannot win. Everything else uses "All life".
const ANIMAL_PHYLA = new Set(["Chordata", "Arthropoda", "Mollusca", "Cnidaria", "Echinodermata", "Porifera", "Brachiopoda", "Annelida",
  "Nemertea", "Platyhelminthes", "Ctenophora", "Bryozoa", "Nematoda", "Rotifera", "Hemichordata", "Tardigrada", "Onychophora", "Priapulida", "Chaetognatha", "Phoronida", "Sipuncula", "Echiura"]);

async function matchNames() {
  const matches = {};
  const unmatched = [];
  const groups = { Animals: taxa.filter((t) => ANIMAL_PHYLA.has(t.lineage?.phylum)), "All life": taxa.filter((t) => !ANIMAL_PHYLA.has(t.lineage?.phylum)) };
  for (const [context, list] of Object.entries(groups)) {
    for (let i = 0; i < list.length; i += 200) {
      const batch = list.slice(i, i + 200);
      const names = batch.map((t) => t.accepted_name);
      const res = await post("tnrs/match_names", { names, context_name: context, do_approximate_matching: false });
      for (const r of res.results ?? []) {
        const t = batch[names.indexOf(r.name)];
        const want = (t.rank ?? "").split(" ")[0];
        const ms = r.matches ?? [];
        // Prefer an accepted (non-synonym) match of the same rank; else any non-synonym; else the first.
        const m = ms.find((x) => !x.is_synonym && x.taxon.rank === want) ?? ms.find((x) => !x.is_synonym) ?? ms[0];
        if (m) matches[t.slug] = { ott_id: m.taxon.ott_id, ott_name: m.taxon.name, ott_unique_name: m.taxon.unique_name, ott_rank: m.taxon.rank, is_synonym: !!m.is_synonym, n_matches: ms.length, context };
      }
      for (const n of res.unmatched_names ?? []) unmatched.push(batch[names.indexOf(n)].slug);
      process.stderr.write(`tnrs ${context} ${Math.min(i + 200, list.length)}/${list.length}\n`);
    }
  }
  return { matches, unmatched };
}

async function inducedSubtree(ottIds) {
  let ids = [...new Set(ottIds)];
  const dropped = {};
  for (let round = 0; round < 12; round++) {
    const res = await post("tree_of_life/induced_subtree", { ott_ids: ids, label_format: "name_and_id" });
    if (res.newick) return { newick: res.newick, ids_in_tree: ids, dropped, broken: res.broken ?? {} };
    const bad = Object.keys(res.unknown ?? {}).map((k) => +k.replace(/^ott/, ""));
    if (!bad.length) throw new Error(`induced_subtree: ${res.message ?? JSON.stringify(res).slice(0, 300)}`);
    for (const b of bad) dropped[b] = res.unknown[`ott${b}`];
    ids = ids.filter((x) => !bad.includes(x));
    process.stderr.write(`induced_subtree: dropped ${bad.length} ids not in the synthetic tree, retrying with ${ids.length}\n`);
  }
  throw new Error("induced_subtree: too many retries");
}

// ---------------------------------------------------------------- Newick
function parseNewick(s) {
  let i = 0;
  const node = () => ({ children: [], label: "" });
  function readLabel() {
    let out = "";
    if (s[i] === "'") {
      i++;
      while (i < s.length) {
        if (s[i] === "'" && s[i + 1] === "'") { out += "'"; i += 2; continue; }
        if (s[i] === "'") { i++; break; }
        out += s[i++];
      }
    } else {
      while (i < s.length && !",():;".includes(s[i])) out += s[i++];
    }
    if (s[i] === ":") { i++; while (i < s.length && !",();".includes(s[i])) i++; }
    return out;
  }
  function readNode() {
    const n = node();
    if (s[i] === "(") {
      i++;
      for (;;) {
        n.children.push(readNode());
        if (s[i] === ",") { i++; continue; }
        if (s[i] === ")") { i++; break; }
        throw new Error(`newick parse error at ${i}`);
      }
    }
    n.label = readLabel().replace(/_/g, " ").trim();
    const mrca = n.label.match(/^mrcaott\d+ott\d+$/);
    const m = mrca ? null : n.label.match(/\bott(\d+)$/);
    n.ott_id = m ? +m[1] : null;
    // Node id as OTOL names it: "ott123" for a taxon node, "mrcaott1ott2" for an unnamed node.
    n.node_id = mrca ? n.label : m ? `ott${m[1]}` : null;
    n.name = m ? n.label.slice(0, m.index).trim() : n.label;
    return n;
  }
  const root = readNode();
  return root;
}

// Drop nodes with one child and nothing attached (the ancestor chain from the root of life).
function collapseUnary(n) {
  n.children = n.children.map(collapseUnary);
  while (n.children.length === 1 && !(n.slugs?.length)) {
    const c = n.children[0];
    if (c.slugs?.length) return c;
    n = c;
  }
  return n;
}

// ---------------------------------------------------------------- build
async function loadTree() {
  if (!REFRESH && existsSync(TREE_JSON)) {
    const t = readJson(TREE_JSON);
    if (t.newick) return t;
  }
  const { matches, unmatched } = await matchNames();
  const ottToSlugs = {};
  for (const [slug, m] of Object.entries(matches)) (ottToSlugs[m.ott_id] ??= []).push(slug);
  const sub = await inducedSubtree(Object.keys(ottToSlugs).map(Number));
  const out = {
    source: "Open Tree of Life v3 API (tnrs/match_names, tree_of_life/induced_subtree), synthetic tree",
    retrieved: new Date().toISOString(),
    taxa_total: taxa.length,
    matched: Object.keys(matches).length,
    unmatched,
    not_in_synthetic_tree: sub.dropped,
    broken: sub.broken,
    matches,
    newick: sub.newick,
  };
  writeFileSync(TREE_JSON, JSON.stringify(out, null, 1) + "\n");
  return out;
}

const PERIODS = [
  ["Cambrian", 538.8, 485.4, "#7FA056"], ["Ordovician", 485.4, 443.8, "#009270"],
  ["Silurian", 443.8, 419.2, "#B3E1B6"], ["Devonian", 419.2, 358.9, "#CB8C37"],
  ["Carboniferous", 358.9, 298.9, "#67A599"], ["Permian", 298.9, 251.9, "#F04028"],
  ["Triassic", 251.9, 201.4, "#812B92"], ["Jurassic", 201.4, 145.0, "#34B2C9"],
  ["Cretaceous", 145.0, 66.0, "#7FC64E"], ["Paleogene", 66.0, 23.03, "#FD9A52"],
  ["Neogene", 23.03, 2.58, "#FFE619"], ["Quaternary", 2.58, 0.0, "#F9F97F"],
];
const GEO_MAX = 560;

const PHYLUM_COLOUR = {
  Chordata: "#1F4E79", Arthropoda: "#8B5A2B", Mollusca: "#6A3D9A", Cnidaria: "#D1495B",
  Echinodermata: "#C77D00", Porifera: "#5B8C5A", Brachiopoda: "#7A6F9B", Annelida: "#A0522D", Foraminifera: "#3E8E7E",
};
const OTHER_COLOUR = "#666666";

async function main() {
  const tree = await loadTree();
  let root = parseNewick(tree.newick);
  // A taxon that is not monophyletic in the synthetic tree ("broken") is attached to the node OTOL
  // maps it to, which is usually an unnamed MRCA node.
  const slugsByNode = {};
  for (const [slug, m] of Object.entries(tree.matches)) {
    const own = `ott${m.ott_id}`;
    const node = tree.broken[own] ?? own;
    (slugsByNode[node] ??= []).push(slug);
  }
  (function attach(n) { n.slugs = n.node_id ? slugsByNode[n.node_id] ?? [] : []; n.children.forEach(attach); })(root);
  root = collapseUnary(root);

  // Compute ages bottom-up.
  const placed = new Set();
  let nTips = 0;
  function annotate(n, depth = 0) {
    n.depth = depth;
    for (const s of n.slugs) placed.add(s);
    n.is_tip = n.children.length === 0;
    if (n.is_tip) nTips++;
    let first = null, last = null, extant = null;
    for (const s of n.slugs) {
      const f = fossilBySlug.get(s);
      if (f?.firstapp_max_ma != null) first = Math.max(first ?? -1, f.firstapp_max_ma);
      if (f?.lastapp_min_ma != null) last = last == null ? f.lastapp_min_ma : Math.min(last, f.lastapp_min_ma);
      if (f?.is_extant) extant = extant || f.is_extant === "extant";
    }
    n.own_first = first;
    n.last = extant === false && last != null ? last : 0;
    n.extinct = extant === false;
    let age = first;
    for (const c of n.children) { annotate(c, depth + 1); if (c.age != null) age = Math.max(age ?? -1, c.age); }
    n.age = age;
    n.dated = age != null;
  }
  annotate(root);

  // Top-down: undated nodes get a visual position under their parent.
  function place(n, parentAge) {
    if (!n.dated) n.age = n.is_tip ? (parentAge ?? GEO_MAX) * 0.6 : (parentAge ?? GEO_MAX) * 0.8;
    for (const c of n.children) place(c, n.age);
  }
  place(root, null);

  // Layout: tips in traversal order, sorted so older lineages come first within each node.
  const ROW = 13, TOP = 150, LEFT = 60, TREE_W = 760, LABEL_W = 230, BOX = 9, BOX_GAP = 2, MAX_BOXES = 20;
  const BOX_W = 120, MARGIN_R = 20;
  const WIDTH = LEFT + TREE_W + 10 + LABEL_W + BOX_W + MARGIN_R;
  const x = (age) => LEFT + (TREE_W * (GEO_MAX - Math.min(age, GEO_MAX))) / GEO_MAX;
  let row = 0;
  function layout(n) {
    if (n.is_tip) { n.y = TOP + row * ROW; row++; return; }
    n.children.sort((a, b) => (b.age ?? 0) - (a.age ?? 0));
    for (const c of n.children) layout(c);
    n.y = (n.children[0].y + n.children[n.children.length - 1].y) / 2;
  }
  layout(root);
  const HEIGHT = TOP + row * ROW + 60;

  // ---------------------------------------------------------------- SVG
  const out = [];
  out.push(`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}" font-family="Helvetica, Arial, sans-serif" font-size="9">`);
  out.push(`<rect width="100%" height="100%" fill="#ffffff"/>`);
  out.push(`<style>a:hover rect{stroke:#000;stroke-width:1.5} .tip:hover{font-weight:bold}</style>`);

  // Period bands.
  for (const [name, a, b, col] of PERIODS) {
    const x0 = x(a), x1 = x(b);
    out.push(`<rect x="${x0.toFixed(1)}" y="${TOP - 24}" width="${(x1 - x0).toFixed(1)}" height="${HEIGHT - TOP + 24 - 40}" fill="${col}" opacity="0.10"/>`);
    out.push(`<rect x="${x0.toFixed(1)}" y="${TOP - 24}" width="${(x1 - x0).toFixed(1)}" height="10" fill="${col}"/>`);
    if (x1 - x0 > 22) out.push(`<text x="${((x0 + x1) / 2).toFixed(1)}" y="${TOP - 27}" text-anchor="middle" font-size="8" fill="#333">${name.slice(0, x1 - x0 > 60 ? 20 : 3)}</text>`);
  }
  out.push(`<rect x="${LEFT}" y="${TOP - 24}" width="${x(538.8) - LEFT}" height="10" fill="#F74370"/>`);
  for (const ma of [500, 400, 300, 200, 100, 0]) {
    out.push(`<line x1="${x(ma)}" y1="${TOP - 14}" x2="${x(ma)}" y2="${HEIGHT - 40}" stroke="#000" stroke-opacity="0.08"/>`);
    out.push(`<text x="${x(ma)}" y="${HEIGHT - 28}" text-anchor="middle" font-size="9" fill="#333">${ma} Ma</text>`);
  }

  // Title and legend.
  out.push(`<text x="${LEFT}" y="28" font-size="18" font-weight="bold" fill="#111">The organisms Darwin and Thompson wrote about, on the tree of life, with the claims that mention them</text>`);
  const nDated = (function count(n) { return (n.is_tip && n.own_first != null ? 1 : 0) + n.children.reduce((s, c) => s + count(c), 0); })(root);
  out.push(`<text x="${LEFT}" y="46" font-size="10" fill="#444">Topology: Open Tree of Life synthetic tree, induced subtree over ${tree.matched} of ${tree.taxa_total} merged taxa (${Object.keys(tree.not_in_synthetic_tree).length} matched names are not in the synthetic tree; ${tree.unmatched.length} names unmatched). Retrieved ${tree.retrieved.slice(0, 10)}.</text>`);
  out.push(`<text x="${LEFT}" y="60" font-size="10" fill="#444">Horizontal position: Paleobiology Database first appearance of the taxon (${nDated} tips). An internal node sits at the oldest first appearance beneath it, a lower bound on clade age, not a divergence time. Dashed: no PBDB range, position arbitrary.</text>`);
  out.push(`<text x="${LEFT}" y="74" font-size="10" fill="#444">Boxes: one per claim that mentions the taxon, coloured by what the repo knows about it. Hover for the claim, click to open it in the claim graph.</text>`);
  let lx = LEFT;
  for (const [, label, fill, stroke] of CLASSES) {
    out.push(`<rect x="${lx}" y="88" width="${BOX}" height="${BOX}" fill="${fill}" stroke="${stroke}" stroke-width="0.8"/>`);
    out.push(`<text x="${lx + BOX + 4}" y="96" font-size="9" fill="#333">${label}</text>`);
    lx += BOX + 8 + label.length * 5.2 + 12;
  }
  out.push(`<line x1="${LEFT}" y1="112" x2="${LEFT + 40}" y2="112" stroke="#3A3A3A" stroke-width="3"/><text x="${LEFT + 46}" y="115" font-size="9" fill="#333">fossil range (first to last appearance)</text>`);
  out.push(`<line x1="${LEFT + 240}" y1="112" x2="${LEFT + 280}" y2="112" stroke="#3A3A3A" stroke-width="1" stroke-dasharray="3 2"/><text x="${LEFT + 286}" y="115" font-size="9" fill="#333">no PBDB range for this lineage</text>`);
  out.push(`<text x="${LEFT + 470}" y="115" font-size="9" fill="#B22222">✕ extinct (last appearance)</text>`);
  let px = LEFT + 620;
  for (const [ph, col] of Object.entries(PHYLUM_COLOUR)) { out.push(`<text x="${px}" y="115" font-size="9" fill="${col}">${ph}</text>`); px += ph.length * 5.2 + 10; }

  // Branches.
  const labelX = LEFT + TREE_W + 10;
  const boxX = labelX + LABEL_W;
  function draw(n) {
    for (const c of n.children) {
      const dashed = !c.dated;
      const stroke = dashed ? `stroke="#9A9A9A" stroke-dasharray="3 2"` : `stroke="#3A3A3A"`;
      const xc = x(c.age);
      out.push(`<path d="M${x(n.age).toFixed(1)} ${n.y.toFixed(1)} V${c.y.toFixed(1)} H${xc.toFixed(1)}" fill="none" ${stroke} stroke-width="${dashed ? 0.8 : 1}"/>`);
      draw(c);
    }
    if (n.is_tip) {
      // Range bar from first appearance to last (0 if extant).
      const x0 = x(n.age), x1 = x(n.last);
      if (n.dated && n.own_first != null) out.push(`<line x1="${x0.toFixed(1)}" y1="${n.y.toFixed(1)}" x2="${x1.toFixed(1)}" y2="${n.y.toFixed(1)}" stroke="#3A3A3A" stroke-width="3" stroke-linecap="butt"/>`);
      if (n.extinct) out.push(`<text x="${x1.toFixed(1)}" y="${(n.y + 3.5).toFixed(1)}" text-anchor="middle" font-size="9" fill="#B22222">✕</text>`);
      out.push(`<line x1="${x1.toFixed(1)}" y1="${n.y.toFixed(1)}" x2="${labelX - 3}" y2="${n.y.toFixed(1)}" stroke="#000" stroke-opacity="0.12" stroke-dasharray="1 2"/>`);
    }
    if (n.slugs.length) label(n);
  }
  function label(n) {
    const yText = n.y + 3.2;
    const names = n.slugs.map((s) => bySlug.get(s));
    const t = names[0];
    const phylum = t.lineage?.phylum;
    const col = PHYLUM_COLOUR[phylum] ?? OTHER_COLOUR;
    const vern = (t.vernacular ?? [])[0];
    const ids = [...new Set(n.slugs.flatMap((s) => [...(claimsOf.get(s) ?? [])]))]
      .map((id) => ({ id, c: claimById.get(id), k: classify(claimById.get(id)) }))
      .sort((a, b) => CLASS_RANK[a.k] - CLASS_RANK[b.k] || a.id.localeCompare(b.id));
    const text = `${names.map((q) => q.accepted_name).join(" / ")}${vern ? ` · ${vern}` : ""}`;
    // Tips label in the aligned column; internal nodes label to the left of the node, above the branch,
    // so that clades near the present do not run into the tip labels.
    const tx = n.is_tip ? labelX : x(n.age) - 4;
    const anchor = n.is_tip ? "start" : "end";
    const maxChars = n.is_tip ? 44 : 30;
    const shown = text.length > maxChars ? text.slice(0, maxChars - 1) + "…" : text;
    const broken = n.slugs.filter((s) => tree.broken[`ott${tree.matches[s].ott_id}`]).map((s) => bySlug.get(s).accepted_name);
    const title = `${text} (${t.rank}; ${n.own_first != null ? `PBDB first appearance ${n.own_first} Ma` : "no PBDB range"}; ${ids.length} claim${ids.length === 1 ? "" : "s"}${broken.length ? `; not monophyletic in the synthetic tree, drawn at its MRCA: ${broken.join(", ")}` : ""})`;
    const style = n.is_tip ? `fill="${col}"` : `fill="${col}" font-style="italic" font-size="8"`;
    const yInt = n.is_tip ? yText : n.y - 2;
    out.push(`<text class="tip" x="${tx.toFixed(1)}" y="${yInt.toFixed(1)}" text-anchor="${anchor}" ${style}><title>${esc(title)}</title>${esc(shown)}</text>`);
    // Boxes: for tips in the box column; for internal nodes to the left of the label, growing leftwards.
    const lim = n.is_tip ? MAX_BOXES : 8;
    const nBoxes = Math.min(ids.length, lim);
    let bx = n.is_tip ? boxX : tx - shown.length * 4.1 - 6 - nBoxes * (BOX + BOX_GAP) - (ids.length > lim ? 16 : 0);
    const by = n.is_tip ? n.y - BOX / 2 : n.y - 2 - BOX;
    ids.slice(0, lim).forEach(({ id, c, k }) => {
      const [, lab, fill, stroke] = CLASSES[CLASS_RANK[k]];
      const tt = `${id}: ${c?.label ?? ""} — ${lab}${c?.thinker ? ` (${c.thinker}${c.year ? ` ${c.year}` : ""})` : ""}`;
      out.push(`<a xlink:href="${CLAIM_URL}${encodeURIComponent(id)}" target="_blank"><rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${BOX}" height="${BOX}" fill="${fill}" stroke="${stroke}" stroke-width="0.8" rx="1"><title>${esc(tt)}</title></rect></a>`);
      bx += BOX + BOX_GAP;
    });
    if (ids.length > lim) out.push(`<text x="${(bx + 2).toFixed(1)}" y="${(by + BOX - 1).toFixed(1)}" font-size="8" fill="#555">+${ids.length - lim}</text>`);
  }
  draw(root);

  // Footer.
  const tested = new Set(), all = new Set();
  for (const s of placed) for (const id of claimsOf.get(s) ?? []) { all.add(id); if (classify(claimById.get(id)) !== "untested") tested.add(id); }
  out.push(`<text x="${LEFT}" y="${HEIGHT - 10}" font-size="9" fill="#555">${placed.size} taxa placed, ${row} tips. ${all.size} distinct claims mention a placed taxon; ${tested.size} of them have a proof or a data verdict. Sources: Open Tree of Life (CC0), Paleobiology Database (CC BY), repo files test-data/organisms/merged/{taxa,timeline,mentions}.json and docs/claims.json. Built by test-data/organisms/tree.mjs.</text>`);
  out.push(`</svg>`);
  writeFileSync(SVG_OUT, out.join("\n") + "\n");

  // Per-taxon placement back into tree.json for other consumers.
  const placement = {};
  (function walk(n) { for (const s of n.slugs) placement[s] = { ott_id: tree.matches[s].ott_id, node_id: n.node_id, broken: !!tree.broken[`ott${tree.matches[s].ott_id}`], is_tip: n.is_tip, age_ma: n.dated ? n.age : null, own_first_ma: n.own_first, extinct: n.extinct, depth: n.depth, claims: [...(claimsOf.get(s) ?? [])] }; n.children.forEach(walk); })(root);
  tree.placement = placement;
  tree.summary = { taxa_total: taxa.length, matched: tree.matched, placed: placed.size, tips: row, dated_tips: nDated, claims_linked: all.size, claims_with_verdict_or_proof: tested.size, unmatched: tree.unmatched.length, not_in_synthetic_tree: Object.keys(tree.not_in_synthetic_tree).length };
  writeFileSync(TREE_JSON, JSON.stringify(tree, null, 1) + "\n");
  console.log(JSON.stringify(tree.summary, null, 1));
  console.log(`wrote ${SVG_OUT} (${WIDTH}x${HEIGHT})`);
}

main().catch((e) => { console.error(e); process.exit(1); });
