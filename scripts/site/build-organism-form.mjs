// Build docs/test-organism.html, the public form for asking that a species or a designed
// organism be tested. The page embeds the names from test-data/organisms/merged/taxa.json so a
// visitor can see whether that name is already in the inventory. Sending the form opens a GitHub
// issue. It does not add a taxon, resolve identifiers, download data, or run a test.
//
//   node scripts/site/build-organism-form.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { withChrome } from "./chrome.mjs";
import { ROOT } from "./load-claims.mjs";

const taxa = JSON.parse(readFileSync(join(ROOT, "test-data/organisms/merged/taxa.json"), "utf8"));
const slim = taxa.map(t => {
  const vernacular = Array.isArray(t.vernacular) ? t.vernacular.filter(Boolean) : [];
  const written = Array.isArray(t.names_as_written) ? t.names_as_written.filter(Boolean) : [];
  const seen = new Set();
  const aka = [];
  for (const name of [...vernacular, ...written]) {
    const key = name.toLowerCase();
    if (seen.has(key) || key === String(t.accepted_name || "").toLowerCase()) continue;
    seen.add(key);
    aka.push(name);
  }
  return {
    slug: t.slug,
    name: t.accepted_name,
    rank: t.rank || "",
    cls: t.lineage && t.lineage.class || "",
    vernacular: vernacular[0] || "",
    aka: aka.slice(0, 12),
    gbif: t.identifiers && t.identifiers.gbif_usage_key != null ? t.identifiers.gbif_usage_key : null,
    ncbi: t.identifiers && t.identifiers.ncbi_taxid != null ? t.identifiers.ncbi_taxid : null,
    qid: t.identifiers && t.identifiers.wikidata_qid || "",
    mentions: t.mention_count ?? (Array.isArray(t.mentioned_in) ? t.mentioned_in.length : 0),
  };
});
if (!slim.some(t => t.slug === "columba-livia" && t.cls === "Aves")) {
  console.error("taxa.json no longer has Columba livia as an Aves record; the form's inventory check would be wrong");
  process.exit(1);
}

const built = new Date().toISOString().slice(0, 16).replace("T", " ");
const data = {
  built,
  count: slim.length,
  source: "test-data/organisms/merged/taxa.json",
  repo: "https://github.com/fractastical/delphi",
  taxa: slim,
};
const seal = readFileSync(join(ROOT, "assets/logo.svg"), "utf8").trim();
const html = withChrome(readFileSync(join(ROOT, "scripts/site/templates/test-organism.template.html"), "utf8"), "test-organism")
  .replace("/*__SEAL_URI__*/", encodeURIComponent(seal))
  .replace("/*__DATA__*/null", JSON.stringify(data).replace(/</g, "\\u003c"));
const out = join(ROOT, "docs/test-organism.html");
writeFileSync(out, html);
console.log(`docs/test-organism.html: ${(html.length / 1024).toFixed(0)} KB, ${slim.length} taxa, built ${built}`);
