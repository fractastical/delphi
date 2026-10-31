// Build unsigned nanopubs (TriG, temp base) for the cell-geometry claim tests: one dcat:Dataset
// nanopub per tissue image used, and one delphi:EvidenceItem nanopub per tested claim.
// Signing replaces the temp base with the trusty URI (build/publish.mjs).
//
//   node build/generate.mjs [--out nanopubs/unsigned]
import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { execSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(ROOT, "..");
const outArg = process.argv.indexOf("--out");
const OUT = join(ROOT, outArg > -1 ? process.argv[outArg + 1] : "nanopubs/unsigned");

const TESTS = {
  "thompson1917-ch07-04": "claim-tests/thompson-growth-form/thompson1917-ch07-04/result.json",
  "thompson1917-ch07-08": "claim-tests/thompson-growth-form/thompson1917-ch07-08/cellpose-multi-tissue/result.json",
  "thompson1917-ch07-10": "claim-tests/thompson-growth-form/thompson1917-ch07-10/result.json",
};

const git = cmd => execSync(`git ${cmd}`, { cwd: REPO, encoding: "utf8" }).trim();
const commit = git("rev-parse HEAD");
const inputs = ["cell-geometry/build", "cell-geometry/inputs/sources.json", "cell-geometry/results", "cell-geometry/analyze.py",
  "cell-geometry/segment.py", ...Object.values(TESTS)];
const dirty = git(`status --porcelain -- ${inputs.join(" ")}`) !== "";

const sources = JSON.parse(readFileSync(join(ROOT, "inputs/sources.json"), "utf8"));
const summary = JSON.parse(readFileSync(join(ROOT, "results/summary.json"), "utf8"));
const used = Object.keys(summary.images).filter(id => summary.images[id].sufficient === true);
const cellpose = Object.fromEntries(used.map(id => [id, JSON.parse(readFileSync(join(ROOT, "results", id, "cellpose.json"), "utf8"))]));
const control = summary.controls["random-voronoi"];

const BLOB = path => `https://github.com/fractastical/delphisci/blob/${commit}/${path}`;
const AGENT = "https://w3id.org/delphi/resource/agent/delphisci-cell-geometry";
const MODEL = "https://w3id.org/delphi/resource/model/claude-opus-5.5";
const OWNER = "https://orcid.org/0009-0007-4948-9192";
const NEBIUS = "https://w3id.org/delphi/resource/agent/nebius-scientific-ai-cellpose";
const DOMAIN = "thompson-growth-form-1917";
const datasetIri = id => `https://w3id.org/delphi/resource/dataset/wikimedia-commons-${id}`;

const lit = s => `"${String(s).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r")}"`;
const num = v => Number.isInteger(v) ? `"${v}"^^xsd:integer` : `"${v}"^^xsd:double`;
const licenseIri = url => url.replace(/\/?$/, "/");
const PREFIXES = `@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix schema: <https://schema.org/> .
@prefix spdx: <http://spdx.org/rdf/terms#> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .
@prefix delphir: <https://w3id.org/delphi/resource/> .
`;

const HEAD = `sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}
`;

const AGENT_TRIPLES = `  <${AGENT}> a prov:SoftwareAgent ;
    rdfs:label "delphisci cell-geometry claim tester" ;
    delphi:usesModel <${MODEL}> ;
    prov:actedOnBehalfOf <${OWNER}> .
  <${MODEL}> a delphi:LanguageModel ;
    rdfs:label "Claude Opus 5.5" .`;

const pubinfo = (created, label, type, introduces) => `sub:pubinfo {
  this: dct:created "${created}"^^xsd:dateTime ;
    dct:creator <${OWNER}> ;
    rdfs:label ${lit(label)} ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType ${type} ;
    npx:introduces <${introduces}> ;
    delphi:domain <https://w3id.org/delphi/resource/domain/${DOMAIN}> .
  <https://w3id.org/delphi/resource/domain/${DOMAIN}> rdfs:label "${DOMAIN}" .
}
`;

// A schema:PropertyValue node: [propertyID, value, description, unit?, about?].
const property = (node, [id, value, description, unit, about]) => `  ${node} a schema:PropertyValue ;
    schema:propertyID ${lit(id)} ;
    schema:value ${typeof value === "number" ? num(value) : lit(value)} ;${unit ? `
    schema:unitText ${lit(unit)} ;` : ""}${about ? `
    schema:about <${about}> ;` : ""}
    schema:description ${lit(description)} .`;

function datasetTrig(id, created) {
  const m = sources[id], ds = datasetIri(id);
  const title = m.commons_file.replace(/^File:/, "");
  const counts = [
    ["n_images", 1, "image files in this dataset"],
    ["width_px", m.size[0], "width in pixels of the downloaded file", "px"],
    ["height_px", m.size[1], "height in pixels of the downloaded file", "px"],
  ];
  return `${PREFIXES}
${HEAD}
sub:assertion {
  <${ds}> a dcat:Dataset ;
    rdfs:label ${lit(`Wikimedia Commons image: ${title} (${m.species}, ${m.tissue})`)} ;
    dct:identifier ${lit(m.commons_file)} ;
    dct:bibliographicCitation ${lit(`${m.creator}. ${title}. Wikimedia Commons, ${m.license}. ${m.source_page}`)} ;
    dct:description ${lit(m.description)} ;
    dct:creator ${lit(m.creator)} ;
    dct:license <${licenseIri(m.license_url)}> ;
    dcat:landingPage <${m.source_page}> ;
    dcat:version ${lit(`Commons rendition retrieved ${m.retrieved_at}`)} ;
    schema:measurementTechnique ${lit(m.measurement_technique)} ;
    schema:about ${lit(`${m.species} (${m.kingdom}), ${m.tissue}`)} ;
    dcat:distribution sub:file ;
${counts.map((_, i) => `    schema:additionalProperty sub:count${i}`).join(" ;\n")} .
  sub:file a dcat:Distribution ;
    dcat:downloadURL <${m.download_url}> ;
    dcat:byteSize "${m.download_bytes}"^^xsd:integer ;
    dcat:mediaType <https://www.iana.org/assignments/media-types/image/jpeg> ;
    spdx:checksum sub:fileChecksum .
  sub:fileChecksum spdx:algorithm spdx:checksumAlgorithm_sha256 ;
    spdx:checksumValue ${lit(m.download_sha256)} .
${counts.map((c, i) => property(`sub:count${i}`, c)).join("\n")}
}

sub:provenance {
  sub:assertion prov:wasAttributedTo <${AGENT}> ;
    prov:wasDerivedFrom <${m.source_page}> ;
    prov:wasGeneratedBy sub:retrieval .
  sub:retrieval a prov:Activity ;
    prov:endedAtTime "${m.retrieved_at}"^^xsd:dateTime ;
    prov:wasAssociatedWith <${AGENT}> ;
    prov:qualifiedAssociation sub:retrievalPlan .
  sub:retrievalPlan prov:hadPlan <${BLOB("cell-geometry/fetch_inputs.py")}> .
${AGENT_TRIPLES}
}

${pubinfo(created, `Dataset: Wikimedia Commons image ${title}`, "dcat:Dataset", ds)}`;
}

// Per-claim measurements, each about one tissue's dataset.
const METRICS = {
  "thompson1917-ch07-04": [
    ["junction_angle_sd", "angle_sd", "standard deviation of the angles between cell walls at three-cell junctions", "degree"],
    ["frac_T_like_junctions", "frac_T_like", "fraction of measured junctions whose largest angle is at least 160 degrees"],
    ["frac_fourfold_junctions", "fourfold_or_more_fraction", "fraction of junction clusters where four or more cells meet"],
    ["n_junctions_measured", "junctions_measured", "three-cell junctions whose angles were measured"],
  ],
  "thompson1917-ch07-08": [
    ["area_cv", "area_cv", "coefficient of variation of interior cell areas"],
    ["frac_hexagons", "frac_hexagons", "fraction of interior cells with exactly six neighbours"],
    ["n_interior_cells", "interior_cells", "cells fully surrounded by other segmented cells"],
  ],
  "thompson1917-ch07-10": [
    ["mean_neighbours", "mean_neighbours", "mean number of neighbours of interior cells"],
    ["neighbour_variance_mu2", "neighbour_variance_mu2", "variance of the neighbour number of interior cells"],
    ["n_interior_cells", "interior_cells", "cells fully surrounded by other segmented cells"],
  ],
};

function evidenceTrig(claimId, created) {
  const r = JSON.parse(readFileSync(join(REPO, TESTS[claimId]), "utf8"));
  const ev = `https://w3id.org/delphi/resource/evidence/cell-geometry-${claimId}`;
  const claim = r.claim_iri;
  const species = new Set(used.map(id => sources[id].species));
  const props = [
    ["verdict", r.verdict, `verdict under the criterion stated in the description, exploratory (not pre-registered); tester's confidence ${r.confidence}`],
    ["n_images", used.length, "tissue images analysed, one per tissue"],
    ["n_species", species.size, "species the analysed tissues come from"],
    ["n_cells_segmented", used.reduce((s, id) => s + summary.images[id].cells, 0), "cells segmented by Cellpose across the analysed images"],
    ...used.flatMap(id => METRICS[claimId].map(([pid, key, desc, unit]) =>
      [pid, summary.images[id][key], `${desc}, ${sources[id].species} ${sources[id].tissue}`, unit, datasetIri(id)])),
    ...METRICS[claimId].filter(([, key]) => typeof control[key] === "number").map(([pid, key, desc, unit]) =>
      [`${pid}_random_voronoi_control`, control[key], `${desc}, synthetic random Voronoi tiling of ${control.cells} cells (calibration control)`, unit]),
  ];
  const description = [
    `Exploratory test of ${claimId}: ${r.hypothesis}`,
    `Result: ${r.measured.value} (${r.measured.unit}; n = ${r.measured.n}; ${r.measured.uncertainty}).`,
    `Criterion: ${r.pass_criterion}`,
    `Interpretation: ${r.interpretation}`,
  ].join("\n\n");
  const pValue = typeof r.measured.uncertainty === "string" && /^p = /.test(r.measured.uncertainty)
    ? Number(r.measured.uncertainty.slice(4)) : null;
  const imageActivities = used.map((id, i) => {
    const c = cellpose[id];
    return `  sub:segmentation${i} a prov:Activity ;
    rdfs:label ${lit(`Cellpose segmentation of ${id}, Nebius operation ${c.operation_id}`)} ;
    dct:identifier ${lit(c.operation_id)} ;
    prov:used <${datasetIri(id)}> ;
    prov:wasAssociatedWith <${NEBIUS}> ;
    prov:startedAtTime "${c.timings.posted_at}"^^xsd:dateTime ;
    prov:endedAtTime "${c.timings.completed_at}"^^xsd:dateTime ;
    schema:description ${lit(`input PNG sha256 ${c.input_sha256} (crop ${JSON.stringify(sources[id].crop)} of the downloaded file); mask sha256 ${c.mask_sha256}; ${c.object_count} objects; diameter hint ${c.diameter ?? "auto"}`)} .`;
  });
  return `${PREFIXES}
${HEAD}
sub:assertion {
  <${claim}> delphi:hasEvidence <${ev}> .
  <${ev}> a delphi:EvidenceItem ;
    rdfs:label ${lit(`Exploratory cell-geometry test of ${claimId} on ${used.length} images: ${r.verdict}`)} ;
    dct:description ${lit(description)} ;
    schema:value ${num(r.measured.value)} ;
    schema:unitText ${lit(r.measured.unit)} ;${pValue != null ? `
    delphi:pValue "${pValue}"^^xsd:double ;
    delphi:statisticalTest ${lit(`Spearman rank correlation across ${r.measured.n} tissues, two-sided`)} ;` : ""}
    rdfs:comment ${lit(r.caveats.join("\n"))} ;
    rdfs:seeAlso <${BLOB(TESTS[claimId])}> ;
${used.map(id => `    prov:used <${datasetIri(id)}>`).join(" ;\n")} ;
${props.map((_, i) => `    schema:additionalProperty sub:value${i}`).join(" ;\n")} .
${props.map((p, i) => property(`sub:value${i}`, p)).join("\n")}
}

sub:provenance {
  sub:assertion prov:wasAttributedTo <${AGENT}> ;
    prov:wasGeneratedBy sub:analysis .
  sub:analysis a prov:Activity ;
    rdfs:label "Junction-angle and neighbour-number measurement on Cellpose masks" ;
    prov:wasAssociatedWith <${AGENT}> ;
    prov:qualifiedAssociation sub:analysisPlan ;
${used.map((_, i) => `    prov:wasInformedBy sub:segmentation${i}`).join(" ;\n")} .
  sub:analysisPlan prov:hadPlan <${BLOB("cell-geometry/analyze.py")}> .
${imageActivities.join("\n")}
  <${NEBIUS}> a prov:SoftwareAgent ;
    rdfs:label "Cellpose CPSAM v2 on the Nebius Scientific AI Platform (segment_cells_native)" ;
    schema:softwareVersion ${lit(`cellpose ${cellpose[used[0]].cellpose_version}, model ${cellpose[used[0]].model_id} sha256 ${cellpose[used[0]].model_sha256}`)} ;
    prov:actedOnBehalfOf <${AGENT}> ;
    prov:qualifiedAssociation sub:segmentPlan .
  sub:segmentPlan prov:hadPlan <${BLOB("cell-geometry/segment.py")}> .
${AGENT_TRIPLES}
}

${pubinfo(created, `Evidence item: exploratory cell-geometry test of Thompson 1917 claim ${claimId}`, "delphi:EvidenceItem", ev)}`;
}

for (const id of used) {
  const c = cellpose[id];
  if (c.input_sha256 !== sources[id].prepared_png_sha256) throw new Error(`${id}: Cellpose input is not the prepared PNG`);
}
if (new Set(used.map(id => cellpose[id].model_sha256)).size !== 1) throw new Error("images were segmented with different models");

rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
const created = new Date().toISOString();
for (const id of used) writeFileSync(join(OUT, `dataset-wikimedia-commons-${id}.trig`), datasetTrig(id, created));
for (const claimId of Object.keys(TESTS)) writeFileSync(join(OUT, `evidence-cell-geometry-${claimId}.trig`), evidenceTrig(claimId, created));
console.log(`wrote ${used.length + Object.keys(TESTS).length} nanopubs to ${OUT} (generator commit ${commit}${dirty ? ", working tree DIRTY: drafts only, do not sign" : ""})`);
