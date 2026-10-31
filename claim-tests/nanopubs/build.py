"""Build unsigned evidence-item nanopublication drafts from claim-tests/**/result.json.

One record per nanopub (AGENTS.md standing order): a delphi:EvidenceItem linked from the existing
claim IRI with delphi:hasEvidence, carrying the status, the dataset(s) with identifier, retrieval
time, byte size and SHA-256, the computed numbers, the repo files they came from, the
pre-registration commit, and what the result does not establish. Where a mixed verdict is split
across readings of the claim, one record per reading; where it is mixed inside one reading, one
record labelled "partially supported" with the supported and unsupported components as separate
statements (see DECISIONS.md).

Usage (from the repo root):
    python claim-tests/nanopubs/build.py              # writes unsigned/*.trig and manifest.json
    python claim-tests/nanopubs/build.py --check JAR  # also runs `java -jar JAR check` on each file

Nothing here signs or publishes anything. Every output file is an unsigned draft and says so.
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TESTS = os.path.join(ROOT, "claim-tests")
OUT = os.path.join(HERE, "unsigned")
REPO = "https://github.com/fractastical/delphisci"
# No human ORCID is written into these drafts (hub instruction 2026-10-31): the assertion and the nanopub are
# attributed to the software agent below; the human owner is added by the ORCID key holder at signing time. See DECISIONS.md.
TEMPLATE_CHECKED = "2026-10-31"
LICENSE_IRIS = {"CC0 1.0": "https://creativecommons.org/publicdomain/zero/1.0/", "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/"}
COUNT_IN_TEXT = re.compile(r"\b(\d{1,3}(?:,\d{3})+|\d+)\s+(species|specimens|genera|families|taxa|individuals|samples|images|sites|populations)\b", re.I)


def structured_counts(prefix, texts):
    """PropertyValue triples for counts that the record's own label/description/comment text states, one per unit,
    only where the unit has a single distinct number across the texts (so nothing is guessed)."""
    found = {}
    for t in texts:
        for num, unit in COUNT_IN_TEXT.findall(t or ""):
            found.setdefault(unit.lower(), set()).add(int(num.replace(",", "")))
    nodes, lines = [], []
    for unit, vals in sorted(found.items()):
        if len(vals) != 1:
            continue
        node = f"{prefix}N{unit}"
        nodes.append(node)
        lines.append(f"  {node} a schema:PropertyValue ; schema:propertyID \"n_{unit}\" ; schema:value {vals.pop()} ; schema:description \"Count of {unit} as stated in this record's text, taken from result.json.\" .")
    return nodes, lines
AGENT = "https://w3id.org/delphi/resource/agent/delphisci-claim-tests-runner"
MODEL = "https://w3id.org/delphi/resource/model/claude-fable-5.1"
# Project Delphi evidence item template (published version; the 2.0 source is project-delphi-ontology nanopubs/src/05).
TEMPLATE_EVIDENCE = "https://w3id.org/np/RAk4kcX4zA_touv8CeKku9tTUnbR5xiTLSLwFbrKSl3BE"
# Project Delphi provenance template v2 (sources: paper, commit, dataset, rubric).
TEMPLATE_PROV = "https://w3id.org/np/RAaYeFYF-Cz2bM5S1wPQsnvs5X6BBxsphL03UkbVZ1lcA"
# Pubinfo templates are not declared either (not verified clean; the record is hand-authored).

# Hand-written per record: the plain-language sentence (item 1), the status (item 2), the one-line
# evidence label, the statistical test the numbers rest on, where the p-value is (or None), the
# components of a partially supported result, and what the result does not establish (item 5).
# Every number in these strings is copied from result.json; `checks` lists tokens the generator
# verifies against the file and refuses to build if one is missing.
RECORDS = [
    dict(id="kimura-heterozygosity", project="math-bio-theorems", status="refuted",
         plain="Species with bigger populations should carry proportionally more genetic variation; across 160 animal species, variation does rise with population size, but about ten times too slowly.",
         label="Refuted: nucleotide diversity rises with census population size about ten times more slowly than the law predicts (log-log slope 0.107, 95% CI 0.078 to 0.137, not about 1)",
         test="Ordinary least squares of log10 nucleotide diversity on log10 census size across 160 non-bird metazoan species with a t-based 95% confidence interval on the slope; Spearman rank correlation reported alongside (rho 0.49, p 3.9e-11)",
         pvalue=None, checks=["0.107", "0.078", "0.137", "160"],
         dne="Does not test the within-model theorem H = theta/(1+theta), which is proved; it refutes the cross-species operationalization in which census size stands in for effective size and the per-site mutation rate is not included (Lewontin's paradox). Birds (13 species) were held out and not scored."),
    dict(id="maynardsmith-hitchhiking", project="math-bio-theorems", status="supported",
         plain="Stretches of a chromosome where genes are shuffled less often should carry less genetic variation; on human chromosome 22 they do.",
         label="Supported: nucleotide diversity rises with local recombination rate across 177 windows of 200 kb on human chromosome 22 (Spearman rho 0.62, p 6.8e-20)",
         test="Spearman rank correlation between per-window nucleotide diversity (1000 Genomes phase 3, all 26 populations) and HapMap phase II recombination rate in cM/Mb, 200 kb windows",
         pvalue=("uncertainty", r"p = ([0-9.]+e-?[0-9]+)"), checks=["0.616", "177", "6.8e-20"],
         dne="Does not isolate selective sweeps as the cause: background selection, gene density and mutation-rate variation produce the same positive correlation. One chromosome, all SNPs rather than neutral sites only, and diversity pooled over populations."),
    dict(id="fisher-infinitesimal", project="math-bio-theorems", status="supported",
         plain="If height comes from many genes of tiny effect, children's heights should scatter around their parents' average by the same amount whatever the parents' height, and siblings should resemble each other at least as much as parent and child; Galton's families fit this.",
         label="Supported: residual variance of child height is constant across mid-parent terciles (ratio 1.08, Levene p 0.96), residuals are near-Gaussian (skew -0.12, excess kurtosis 0.46), and the sibling correlation 0.39 is at least the parent-offspring correlation 0.35",
         test="Levene test for equality of residual variance across mid-parent terciles of 934 children in 205 Galton families; sibling intraclass correlation versus implied parent-offspring correlation",
         pvalue=("uncertainty", r"Levene p = ([0-9.]+)"), checks=["1.08", "0.956", "0.394", "0.351", "934", "205"],
         dne="An in-sample test on the classic data Fisher built the model to explain, not an out-of-sample test; shared family environment cannot be separated from dominance in the sibling excess; heights are Galton's rounded values."),
    dict(id="kimura-fixation-probability", project="math-bio-theorems", status="supported",
         plain="A gene variant with no advantage should end up taking over a population about as often as its starting share; in Buri's fly experiment, lines that started at 50% fixed it about half the time.",
         label="Supported: of the 58 Buri (1956) lines resolved by generation 19, 28 fixed bw75 and 30 lost it (0.48 against the neutral prediction 0.5, exact binomial p 0.90)",
         test="Exact two-sided binomial test of fixed versus lost lines against 0.5 among the 58 of 107 lines that had fixed or lost bw75 by the last recorded generation",
         pvalue=("uncertainty", r"p = ([0-9.]+)"), checks=["28", "30", "58", "107", "0.90"],
         dne="Only the neutral limit u(p) = p at p = 0.5 is tested; the selection-dependent formula is untested because the selection coefficient of bw75 is not independently known; 49 lines were still segregating and are censored; the data are a transcription of Buri's table."),
    dict(id="darwin1859-ch11-13", project="darwin-origin", status="supported",
         plain="Ice ages lasted a very long time and happened in both hemispheres at once; the deep-sea record and the Antarctic ice record agree on this.",
         label="Supported: 38% of the last 2.6 million years lies in cold, ice-rich states, 34 such intervals last at least 10 thousand years, the last glacial maximum is among the coldest, and Antarctic temperature tracks global ice volume (correlation 0.88 at a 2 kyr lag)",
         test="Fraction of the 0 to 2600 ka LR04 benthic d18O stack at or above 4.0 per mil; count of contiguous intervals of at least 10 kyr; Pearson correlation of EPICA Dome C temperature with negative LR04 d18O over 0 to 800 ka at lags of -6 to +6 kyr",
         pvalue=None, checks=["0.3798", "34", "4.88", "0.8758", "2"],
         dne="Shows many glacial cycles rather than Darwin's single long Glacial period; simultaneity is shown at orbital resolution for two records (a global benthic stack dominated by northern ice and one Antarctic site), not for the tropics, the ocean surface or millennial-scale bipolar anti-phasing."),
    dict(id="thompson1917-ch03-07", project="thompson-growth-form", status="supported",
         plain="As children grow, their weight rises roughly with the cube of their height; a US survey of 2 to 19 year olds gives an exponent of 2.7 to 2.9.",
         label="Supported: the log-log exponent of mean weight on mean height across ages 2 to 19 is 2.74 for males (95% CI 2.59 to 2.89) and 2.86 for females, inside the pre-registered 2.5 to 3.5 band; a pure cubic model explains 98 to 99% of the variance in mean weight",
         test="Ordinary least squares of log mean weight on log mean height over 18 one-year age bins per sex (NHANES 2013 to 2018, survey-weighted means) with a t-based 95% confidence interval; R-squared of the cubic model on the original scale",
         pvalue=None, checks=["2.742", "2.59", "2.89", "2.86", "0.9905", "0.979"],
         dne="The exponent is below 3 in both sexes and the male interval excludes 3, so the cube is an approximation, as Thompson's 'mainly (though not wholly)' allows; cross-sectional population means, not individual growth; 16 degrees of freedom per sex."),
    dict(id="thompson1917-ch16-13", project="thompson-growth-form", status="supported",
         plain="Mammals that returned to the sea lost the tall spines over the shoulders that land mammals have; seals and whales show no such peak.",
         label="Supported: the pinniped withers index is about 1.0 against 1.24 to 2.99 in 40 terrestrial carnivorans (one-sided Mann-Whitney p 0.0012), and all 74 cetacean species fall below the terrestrial minimum",
         test="Exact one-sided Mann-Whitney U test, pinnipeds (n = 2 species) below terrestrial carnivorans (n = 40), on the withers index (mean relative neural-spine height T1-T4 over T10-T13); cetacean withers index compared with the terrestrial distribution",
         pvalue=("uncertainty", r"WI p = ([0-9.]+)"), checks=["1.023", "1.238", "2.993", "0.0012", "74"],
         dne="Only two pinniped species are available; sirenians and the bird-pelvis half of the claim were not tested; the spines are reduced, not literally vanished; no phylogenetic comparative model was fitted; the two datasets use different spine-height protocols, so only the within-column ratio is compared."),
    dict(id="thompson1917-ch04-13", project="thompson-growth-form", status="refuted",
         plain="Thompson said most species have 6 to 16 chromosomes in their sex cells and very few have more than 16; among plants, a third of species have more than 16.",
         label="Refuted: 34.3% of 69,948 plant species have a haploid chromosome number above 16 against 1.7% below 6; 64.1% lie in 6 to 16",
         test="Proportions of species by haploid-number class from the Chromosome Counts Database (median count per species, gametophytic level confirmed on reference species); binomial standard error below 0.002; post-hoc sensitivity (lowest count per species, genus medians, angiosperms only) all give the same verdict",
         pvalue=None, checks=["0.3426", "69948", "0.0166", "0.6407"],
         dne="Plants only: the animal half of Thompson's 'plants and animals' is untested; the central range is roughly right (mode n = 9); the upper tail is driven by polyploidy, unknown in 1917; the CCDB is a compilation with uneven coverage."),
    dict(id="thompson1917-ch10-02", project="thompson-growth-form", status="refuted",
         plain="Thompson said the seam between the whorls of a Turritella shell follows the shortest path on a cone; real shells wind about two and a half times more than such a path could.",
         label="Refuted: observed whorl counts exceed the maximum number of turns a conical geodesic can make in all 34 Turritella specimens (median ratio 2.5, range 1.63 to 3.39)",
         test="Deterministic bound N_obs <= 1/(2 sin(alpha/2)) per specimen from apical angle and whorl number; no sampling test (every specimen exceeds the bound, also after subtracting two early whorls)",
         pvalue=None, checks=["2.5", "34", "1.63", "3.39"],
         dne="Refutes the identification of the suture with a geodesic of the enveloping right cone, not Thompson's geometric statement that a conical geodesic coils more closely toward the apex (which is true); Neogene fossil Turritella from Java, not the type species; apical angles are the source's gross measurements."),
    dict(id="thompson1917-ch11-06", project="thompson-growth-form", status="refuted",
         plain="Thompson said a shell grows by adding pieces that keep its overall shape the same; ammonoid shells change shape as they grow.",
         label="Refuted: at least one conch shape index changes by 50% or more over post-embryonic growth in 94% of 179 ammonoid series (177 species); only 1 series is gnomonic",
         test="Per-series monotonic trend (Spearman |rho| >= 0.7, p < 0.05) and percentage change over ontogeny in conch width index, umbilical width index and whorl expansion rate; classification allometric / intermediate / gnomonic by pre-registered thresholds",
         pvalue=None, checks=["0.939", "179", "177", "168", "10", "1"],
         dne="The refutation is carried almost entirely by the umbilical width index; the whorl expansion rate, which encodes the spiral angle, stays within 25% in 80% of series, so the spiral itself is close to logarithmic; without UWI the rule would give 'mixed'; ammonoids only, from a sample chosen for phased ontogenies; gastropods, bivalves, horns and tusks untested."),
    dict(id="darwin1859-ch09-03", project="darwin-origin", status="refuted", reading="numeric",
         plain="Darwin estimated that more than 300 million years had passed since the late Chalk; the modern timescale puts the end of the Chalk at 66 million years ago.",
         label="Refuted: the end of the Chalk (top of the Maastrichtian) is 66.0 Ma, 4.6 times younger than Darwin's 306.7 million years; the Weald-denudation and start-of-Late-Cretaceous readings (100.5 Ma, ratio 3.05) are refuted too",
         test="One-number comparison of ICS chronostratigraphic boundary ages (Macrostrat API, international ages; uncertainties about 0.2 Ma) with the pre-registered threshold of 225 Ma; no sampling test",
         pvalue=None, checks=["66", "306.66", "4.646", "225", "83.6", "72.2", "100.5", "3.05"],
         dne="Does not evaluate Darwin's erosion rate, only the duration he inferred from it; refutes the figure as stated in the first edition, which Darwin withdrew in the third; the qualitative reading that geological time is immense is a separate record (darwin1859-ch09-03--qualitative)."),
    dict(id="darwin1859-ch09-03", project="darwin-origin", status="inconclusive", reading="qualitative",
         plain="Darwin's underlying point was that geological time is immense, far longer than the physics of his day allowed; that reading was not put to a pre-registered test.",
         label="Not tested: the qualitative reading of darwin1859-ch09-03 (geological time is immense) had no pre-registered pass or fail criterion, so no verdict is recorded",
         test="None. The readings check (added after the numeric result, no number or threshold changed) notes that the modern timescale is consistent with this reading (the Mesozoic began about 252 Ma; the Earth is about 4.5 Gyr old), but the pre-registered test operationalized only the 300 million year figure",
         pvalue=None, checks=["252", "4.5"], no_measurement=True,
         dne="Establishes nothing on its own. It records that the numeric refutation (darwin1859-ch09-03--numeric) does not touch the qualitative reading, and that this reading would need its own pre-registered criterion before any verdict is given."),
    dict(id="fisher-sex-ratio", project="math-bio-theorems", status="partially supported",
         plain="Fisher argued that parents should produce about as many sons as daughters; across 146 countries from 1950 to 1979 about 105 boys were born per 100 girls, close to equal but consistently above it.",
         label="Partially supported: every one of 4222 country-years lies within 10% of equality (criterion B holds), but the median sex ratio at birth is 105.2 males per 100 females, outside the pre-registered 5% band (criterion A fails)",
         test="Median and band fractions of the UN World Population Prospects 2024 sex ratio at birth over country-years 1950 to 1979 with population at least 1 million; no inferential test",
         pvalue=None, checks=["105.2", "4222", "146", "0.4689"],
         supported="Criterion B: 100% of 4222 country-years from 146 countries lie within [90, 110] males per 100 females; no population departs widely from equal numbers at birth.",
         unsupported="Criterion A: the median is 105.2 (5th to 95th percentile 102.5 to 107.0) and lies outside [95, 105]; the male excess is systematic, the lowest country mean being 101.0, and only 47% of country-years fall within the 5% band.",
         dne="Tests numbers at birth, not parental investment, which is what Fisher's principle concerns; it cannot confirm the usual reconciliation (higher boy mortality before the end of parental care brings investment nearer equality) because child mortality by sex was not measured; humans only, equal-cost case only; UN estimates are smoothed and not independent across years."),
    dict(id="hamilton-senescence", project="math-bio-theorems", status="partially supported",
         plain="If natural selection weakens with age, death rates should rise with age in almost all wild animals; in matrix population models they rise in 20 of 35 species, a majority but not the great majority.",
         label="Partially supported: adult mortality rises with age in 20 of 35 non-bird species (57%), above the 50% refute line but below the 80% support line; mean Spearman rho 0.15, below the pre-registered 0.3",
         test="Per-species Spearman correlation between age-class index and adult mortality (1 - column sum of U) over mature classes of unmanipulated wild age-classified COMADRE matrices; fraction of species with rho > 0 and mean rho",
         pvalue=None, checks=["0.5714", "35", "0.1454", "20"],
         supported="A majority of species (20 of 35, 12 of them significant at p < 0.05) show adult mortality rising with age, the direction the claim predicts.",
         unsupported="13 of 35 species show falling adult mortality (6 significant) and 2 are flat; the mean rho of 0.15 is below the pre-registered 0.3; 'inevitable senescence in the great majority' is not seen in these matrices.",
         dne="Does not test the proved formula for the age-specific force of selection, only the biological corollary; published matrices truncate old ages with a plus group, which biases against the claim; 35 species dominated by well-studied mammals and fishes; birds (8 species) held out and not scored."),
    dict(id="thompson1917-ch03-10", project="thompson-growth-form", status="partially supported",
         plain="Fish keep growing throughout life, only ever approaching a maximum size; in 7 of 11 North Sea species the survey data agree, just short of the pre-set bar.",
         label="Partially supported: an asymptotic growth model is favoured in 7 of 11 North Sea species (0.636, pre-registered threshold two thirds) and 76% of late-age length increments are positive (threshold 75%)",
         test="AIC comparison of a von Bertalanffy fit against a quadratic-plateau (reached-maximum) fit to weighted mean length at age per species (ICES DATRAS NS-IBTS 2000 to 2024, 1111408 aged fish); sign of the last three increments per species",
         pvalue=None, checks=["0.6363", "11", "0.758", "7", "2", "33", "1111408"],
         supported="25 of 33 pooled late-age increments are positive (0.758, at or above the 0.75 threshold) and the median dAIC favouring the asymptotic model is 13.9.",
         unsupported="Only 7 of 11 species (0.636) favour the asymptotic model against the pre-registered two thirds; in whiting and lemon sole mean length at age declines over the oldest ages, which neither model predicts.",
         dne="Cross-sectional survey means mix cohorts and years; size-selective fishing mortality and ageing error can mimic growth cessation; the reached-maximum alternative had to be given one specific functional form; 11 North Sea teleosts, not cold-blooded animals in general; DATRAS is a live database."),
]

SKIPPED = {
    "hamilton-lmc": "inconclusive, data-unavailable (Dryad blocks scripted downloads): no evidence item; open task, not a record",
    "maynardsmith-war-of-attrition": "inconclusive, data-unavailable (Dryad blocks scripted downloads): no evidence item; open task, not a record",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def lit(s):
    s = str(s)
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\r", "").replace("\n", "\\n") + '"'


def commit_info(sha):
    date = git("log", "-1", "--format=%cI", sha)
    subject = git("log", "-1", "--format=%s", sha)
    on_origin = "origin/main" in git("branch", "-r", "--contains", sha)
    utc = dt.datetime.fromisoformat(date).astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dict(sha=sha, date=utc, subject=subject, on_origin=on_origin)


def history(relpath):
    shas = git("log", "--format=%H", "--reverse", "--", relpath).split("\n")
    return [commit_info(s) for s in shas if s]


def build(rec, now):
    tdir = os.path.join(TESTS, rec["project"], rec["id"])
    rel_result = f"claim-tests/{rec['project']}/{rec['id']}/result.json"
    rel_analysis = f"claim-tests/{rec['project']}/{rec['id']}/analysis.py"
    r = json.load(open(os.path.join(tdir, "result.json"), encoding="utf-8"))
    blob = json.dumps(r)
    for tok in rec["checks"]:
        if tok not in blob:
            raise SystemExit(f"{rec['id']}: '{tok}' from the hand-written text is not in result.json; refusing to build")
    hist = history(rel_result)
    prereg = hist[0]
    amendments = [h for h in hist[1:] if "amend" in h["subject"].lower()]
    latest = hist[-1]
    ahist = history(rel_analysis)
    analysis_latest = ahist[-1] if ahist else None
    retrievals = sorted(f["retrieved_at"] for d in r["datasets"] for f in d.get("files", []) if f.get("retrieved_at"))
    first_retrieval = retrievals[0] if retrievals else None
    delta = None
    if first_retrieval:
        t_ret = dt.datetime.fromisoformat(first_retrieval.replace("Z", "+00:00"))
        t_pre = dt.datetime.fromisoformat(prereg["date"].replace("Z", "+00:00"))
        delta = int((t_ret - t_pre).total_seconds())
        if delta <= 0:
            raise SystemExit(f"{rec['id']}: first retrieval {first_retrieval} is not after the pre-registration commit {prereg['date']}")
    suffix = f"--{rec['reading']}" if rec.get("reading") else ""
    name = rec["id"] + suffix
    claim_iri = r["claim_iri"]
    ev = f"https://w3id.org/delphi/resource/evidence/claim-test-{name}"
    m = r["measured"]
    ds_iris = [f"https://w3id.org/delphi/resource/dataset/{d['id']}" for d in r["datasets"]]
    L = []
    A = L.append
    A("@prefix this: <http://purl.org/nanopub/temp/np1/> .")
    A("@prefix sub: <http://purl.org/nanopub/temp/np1/> .")
    A("@prefix np: <http://www.nanopub.org/nschema#> .")
    A("@prefix npx: <http://purl.org/nanopub/x/> .")
    A("@prefix nt: <https://w3id.org/np/o/ntemplate/> .")
    A("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .")
    A("@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .")
    A("@prefix dct: <http://purl.org/dc/terms/> .")
    A("@prefix prov: <http://www.w3.org/ns/prov#> .")
    A("@prefix schema: <https://schema.org/> .")
    A("@prefix dcat: <http://www.w3.org/ns/dcat#> .")
    A("@prefix spdx: <http://spdx.org/rdf/terms#> .")
    A("@prefix owl: <http://www.w3.org/2002/07/owl#> .")
    A("@prefix delphi: <https://w3id.org/delphi/ontology/> .")
    A("")
    A("sub:Head {")
    A("  this: a np:Nanopublication ;")
    A("    np:hasAssertion sub:assertion ;")
    A("    np:hasProvenance sub:provenance ;")
    A("    np:hasPublicationInfo sub:pubinfo .")
    A("}")
    A("")
    A("sub:assertion {")
    A(f"  <{claim_iri}> delphi:hasEvidence <{ev}> .")
    A(f"  <{ev}> a delphi:EvidenceItem ;")
    A(f"    rdfs:label {lit(rec['label'])} ;")
    A(f"    dct:description {lit('Pre-registered test of the claim. Hypothesis as tested: ' + r['hypothesis'])} ;")
    A(f"    delphi:statisticalTest {lit(rec['test'])} ;")
    if rec.get("pvalue"):
        field, pat = rec["pvalue"]
        mm = re.search(pat, m[field])
        if not mm:
            raise SystemExit(f"{rec['id']}: p-value pattern not found in measured.{field}")
        A(f"    delphi:pValue \"{float(mm.group(1))!r}\"^^xsd:double ;")
    props = ["sub:plain", "sub:status", "sub:doesNotEstablish"]
    if not rec.get("no_measurement"):
        props += ["sub:measured", "sub:n", "sub:uncertainty", "sub:preregRule"]
    if rec.get("supported"):
        props += ["sub:supportedComponent", "sub:unsupportedComponent"]
    if rec.get("reading"):
        props.append("sub:reading")
    ev_texts = [rec["label"], "Pre-registered test of the claim. Hypothesis as tested: " + r["hypothesis"]] + list(r.get("caveats", []))
    cnodes, clines = structured_counts("sub:ev", ev_texts)
    A("    schema:additionalProperty " + ", ".join(props + cnodes) + " ;")
    for c in r.get("caveats", []):
        A(f"    rdfs:comment {lit(c)} ;")
    A("    prov:used " + ", ".join(f"<{d}>" for d in ds_iris) + " ;")
    A(f"    prov:wasDerivedFrom <{REPO}/blob/{latest['sha']}/{rel_result}> .")
    status_desc = "Outcome under the pre-registered decision rule. result.json verdict field: " + r["verdict"]
    if r.get("reason"):
        status_desc += " (reason: " + r["reason"] + ")"
    if rec.get("reading"):
        status_desc += "; this record covers the " + rec["reading"] + " reading of the claim only"
    A(f"  sub:plain a schema:PropertyValue ; schema:propertyID \"plain_language_statement\" ; schema:value {lit(rec['plain'])} ; schema:description \"The tested claim and its outcome in one sentence for a general reader.\" .")
    A(f"  sub:status a schema:PropertyValue ; schema:propertyID \"status\" ; schema:value {lit(rec['status'])} ; schema:description {lit(status_desc)} .")
    if not rec.get("no_measurement"):
        val = m["value"]
        vlit = f"\"{float(val)!r}\"^^xsd:double" if isinstance(val, (int, float)) else lit(val)
        A(f"  sub:measured a schema:PropertyValue ; schema:propertyID \"measured_value\" ; schema:value {vlit} ; schema:unitText {lit(m['unit'])} ; schema:description \"Observation: the primary pre-registered quantity, computed by analysis.py from the retrieved files; further computed quantities are in result.json measured.extra.\" .")
        A(f"  sub:n a schema:PropertyValue ; schema:propertyID \"sample\" ; schema:value {lit(m['n'])} ; schema:description \"Observation: what was analysed after the pre-registered filters.\" .")
        A(f"  sub:uncertainty a schema:PropertyValue ; schema:propertyID \"uncertainty\" ; schema:value {lit(m.get('uncertainty', 'not applicable'))} ; schema:description \"Observation: uncertainty or secondary statistics as reported in result.json.\" .")
        A(f"  sub:preregRule a schema:PropertyValue ; schema:propertyID \"pre_registered_rule\" ; schema:value {lit('PASS: ' + r['pass_criterion'] + ' FAIL: ' + r['fail_criterion'])} ; schema:description \"Assumption and decision rule fixed before the data were opened (see the pre-registration commit in the provenance graph); not an observation.\" .")
    L.extend(clines)
    A(f"  sub:doesNotEstablish a schema:PropertyValue ; schema:propertyID \"does_not_establish\" ; schema:value {lit(rec['dne'])} ; schema:description \"Interpretation: the limits of what this evidence shows.\" .")
    if rec.get("supported"):
        A(f"  sub:supportedComponent a schema:PropertyValue ; schema:propertyID \"supported_component\" ; schema:value {lit(rec['supported'])} ; schema:description \"The part of the pre-registered prediction that the data meet.\" .")
        A(f"  sub:unsupportedComponent a schema:PropertyValue ; schema:propertyID \"unsupported_component\" ; schema:value {lit(rec['unsupported'])} ; schema:description \"The part of the pre-registered prediction that the data do not meet.\" .")
    if rec.get("reading"):
        A(f"  sub:reading a schema:PropertyValue ; schema:propertyID \"reading_of_claim\" ; schema:value {lit(rec['reading'])} ; schema:description \"Which reading of the source claim this record evaluates; the other reading has its own record linked to the same claim.\" .")
    for di, d in enumerate(r["datasets"], 1):
        iri = ds_iris[di - 1]
        files = d.get("files", [])
        dnodes, dlines = structured_counts(f"sub:ds{di}", [d["name"], "Role in this test: " + d.get("role", "")])
        A(f"  sub:ds{di}Nfiles a schema:PropertyValue ; schema:propertyID \"n_files\" ; schema:value {len(files)} ; schema:description \"Files of this dataset that the test retrieved and checksummed (the distributions listed here).\" .")
        A(f"  sub:ds{di}Nbytes a schema:PropertyValue ; schema:propertyID \"byte_size_total\" ; schema:value {sum(int(f['byte_size']) for f in files)} ; schema:description \"Total byte size of the retrieved files.\" .")
        L.extend(dlines)
        A(f"  <{iri}> a dcat:Dataset ;")
        A(f"    rdfs:label {lit(d['name'])} ;")
        A("    schema:additionalProperty " + ", ".join([f"sub:ds{di}Nfiles", f"sub:ds{di}Nbytes"] + dnodes) + " ;")
        if d.get("doi"):
            A(f"    dct:identifier {lit(d['doi'])} ;")
            A(f"    owl:sameAs <https://doi.org/{d['doi']}> ;")
        else:
            A(f"    dct:identifier {lit(d.get('landing_url') or files[0]['download_url'])} ;")
        if d.get("landing_url"):
            A(f"    dcat:landingPage <{d['landing_url']}> ;")
        if d.get("version"):
            A(f"    dcat:version {lit(d['version'])} ;")
        lic = d.get("license", "")
        lic_iri = next((v for k, v in LICENSE_IRIS.items() if lic.startswith(k)), None)
        if lic_iri:
            A(f"    dct:license <{lic_iri}> ;")
        if lic:
            A(f"    dct:rights {lit(lic)} ;")
            if not lic_iri:
                A(f"    dct:license {lit(lic)} ;")
        if d.get("role"):
            A(f"    rdfs:comment {lit('Role in this test: ' + d['role'])} ;")
        A("    dcat:distribution " + ", ".join(f"sub:ds{di}f{fi}" for fi in range(1, len(files) + 1)) + " .")
        for fi, f in enumerate(files, 1):
            A(f"  sub:ds{di}f{fi} a dcat:Distribution, prov:Entity ;")
            if f.get("download_url"):
                A(f"    dcat:downloadURL <{f['download_url']}> ;")
            if f.get("member_of_tarball"):
                A(f"    dct:isPartOf sub:ds{di}f1 ; rdfs:comment {lit('Member of the retrieved archive: ' + f['member_of_tarball'])} ;")
            A(f"    dcat:byteSize \"{int(f['byte_size'])}\"^^xsd:nonNegativeInteger ;")
            if f.get("retrieved_at"):
                A(f"    prov:generatedAtTime \"{f['retrieved_at']}\"^^xsd:dateTime ;")
            flines = []
            if f.get("note"):
                A(f"    rdfs:comment {lit(f['note'])} ;")
                fnodes, flines = structured_counts(f"sub:ds{di}f{fi}", [f["note"]])
                if fnodes:
                    A("    schema:additionalProperty " + ", ".join(fnodes) + " ;")
            A(f"    spdx:checksum sub:ds{di}f{fi}sum .")
            L.extend(flines)
            A(f"  sub:ds{di}f{fi}sum a spdx:Checksum ; spdx:algorithm spdx:checksumAlgorithm_sha256 ; spdx:checksumValue \"{f['sha256']}\"^^xsd:hexBinary .")
    A("}")
    A("")
    A("sub:provenance {")
    derived = [f"<{REPO}/blob/{latest['sha']}/{rel_result}>", f"<{REPO}/commit/{prereg['sha']}>"] + [f"<{REPO}/commit/{a['sha']}>" for a in amendments]
    local_note = " This commit is local to the hackathon tree and not yet on GitHub; the URL resolves after the push."
    A(f"  sub:assertion prov:wasAttributedTo <{AGENT}> ;")
    A("    prov:wasDerivedFrom " + ", ".join(derived) + " ;")
    A("    prov:wasGeneratedBy sub:test .")
    A(f"  <{REPO}/blob/{latest['sha']}/{rel_result}> dct:title {lit(rel_result + ' at commit ' + latest['sha'][:7] + ' (' + latest['date'] + ')')} ;")
    A(f"    rdfs:comment {lit('Result file with verdict, measured values, dataset checksums and caveats.' + ('' if latest['on_origin'] else local_note))} .")
    pre_note = f"Pre-registration: pass and fail criteria with verdict null, committed {prereg['date']}"
    if first_retrieval:
        pre_note += f"; the first data file for this test was retrieved at {first_retrieval}, {delta} s later"
    pre_note += "." + ("" if prereg["on_origin"] else local_note)
    A(f"  <{REPO}/commit/{prereg['sha']}> a prov:Entity ; dct:title {lit(prereg['subject'])} ; dct:date \"{prereg['date']}\"^^xsd:dateTime ; rdfs:comment {lit(pre_note)} .")
    for a in amendments:
        A(f"  <{REPO}/commit/{a['sha']}> a prov:Entity ; dct:title {lit(a['subject'])} ; dct:date \"{a['date']}\"^^xsd:dateTime ; rdfs:comment {lit('Amendment to the pre-registration, committed before this test retrieved any data.' + ('' if a['on_origin'] else local_note))} .")
    used = [f"<{d}>" for d in ds_iris]
    if analysis_latest:
        used.append(f"<{REPO}/blob/{analysis_latest['sha']}/{rel_analysis}>")
    A(f"  sub:test a prov:Activity ; prov:wasAssociatedWith <{AGENT}> ; prov:used " + ", ".join(used) + " ; prov:qualifiedAssociation sub:plan .")
    A(f"  sub:plan a prov:Association ; prov:agent <{AGENT}> ; prov:hadPlan <{REPO}/blob/{prereg['sha']}/{rel_result}> .")
    A(f"  <{REPO}/blob/{prereg['sha']}/{rel_result}> rdfs:comment \"The pre-registered plan: result.json as first committed, before any download.\" .")
    agent_note = "Run: " + r["agent"].get("run", "") + "; model " + r["agent"].get("model", "") + "; " + r["agent"].get("date", "")
    A(f"  <{AGENT}> a prov:SoftwareAgent ; rdfs:label \"delphisci claim-tests runner (claims thread)\" ; rdfs:comment {lit(agent_note)} ; delphi:usesModel <{MODEL}> .")
    A(f"  <{MODEL}> a delphi:LanguageModel ; rdfs:label \"Claude Fable 5.1\" .")
    A("}")
    A("")
    A("sub:pubinfo {")
    A(f"  this: dct:created \"{now}\"^^xsd:dateTime ;")
    A(f"    dct:creator <{AGENT}> ;")
    A(f"    rdfs:label {lit('Evidence for ' + r['claim_id'] + ': ' + rec['status'])} ;")
    A("    dct:license <https://creativecommons.org/licenses/by/4.0/> ;")
    A("    npx:hasNanopubType delphi:EvidenceItem ;")
    A(f"    npx:introduces <{ev}> ;")
    A(f"    nt:wasCreatedFromProvenanceTemplate <{TEMPLATE_PROV}> ;")
    A(f"    rdfs:comment \"UNSIGNED DRAFT prepared {now[:10]} by the claims thread of the DELPHI team: not signed, not published to any registry. Intended for the nanopub TEST registry first; production publication needs the ORCID key owner's explicit approval. No human owner is named in this draft: dct:creator is the software agent, and the ORCID of the key holder is added only when that person approves and signs. Built by claim-tests/nanopubs/build.py from result.json.\" ;")
    A(f"    rdfs:comment \"No assertion template is declared. The template that would otherwise apply, the published Project Delphi evidence item template {TEMPLATE_EVIDENCE} (dct:created 2026-10-01), still carries the legacy https://w3id.org/probknow/ontology/ namespace (1 occurrence, checked {TEMPLATE_CHECKED} on the live network), and its required statements cannot be instantiated with Delphi ontology 2.0 terms, so this hand-authored record was not created from it and does not claim to be. The provenance template {TEMPLATE_PROV} is declared because it carries no legacy IRI (0 occurrences, same check). No pubinfo template is declared. See claim-tests/nanopubs/DECISIONS.md (2026-10-31).\" .")
    if rec["project"] == "darwin-origin":
        A("  this: delphi:domain <https://w3id.org/delphi/resource/domain/darwin-origin-1859> .")
        A("  <https://w3id.org/delphi/resource/domain/darwin-origin-1859> rdfs:label \"darwin-origin-1859\" .")
    A("}")
    text = "\n".join(L) + "\n"
    path = os.path.join(OUT, name + ".trig")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return dict(file=f"unsigned/{name}.trig", claim_id=r["claim_id"], claim_iri=claim_iri, evidence_iri=ev, status=rec["status"],
                reading=rec.get("reading"), verdict_in_result=r["verdict"], prereg_commit=prereg["sha"], prereg_date=prereg["date"],
                first_retrieval=first_retrieval, seconds_prereg_to_first_retrieval=delta, amendment_commits=[a["sha"] for a in amendments],
                result_commit=latest["sha"], signed=False, published=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="JAR", help="path to nanopub-*-jar-with-dependencies.jar; runs `check` on every output")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries = [build(rec, now) for rec in RECORDS]
    manifest = dict(built=now, generator="claim-tests/nanopubs/build.py", records=entries, skipped=SKIPPED, checked_with=None)
    if args.check:
        log = []
        for e in entries:
            p = os.path.join(HERE, e["file"])
            cp = subprocess.run(["java", "-jar", args.check, "check", "-v", p], capture_output=True, text=True)
            out = (cp.stdout + cp.stderr).strip()
            valid = "Valid (but not trusty)" in out and "RDF ERROR" not in out and "errors" not in out
            issues = [ln.strip()[2:] for ln in out.split("\n") if ln.strip().startswith("- ")]
            e["np_check"] = dict(valid=valid, exit_code=cp.returncode, issues=issues)
            log.append(f"## {e['file']} ({'VALID' if valid else 'NOT VALID'}, exit {cp.returncode})\n{out}\n")
        ver = subprocess.run(["java", "-jar", args.check], capture_output=True, text=True)
        manifest["checked_with"] = (ver.stdout + ver.stderr).strip().split("\n")[-1]
        with open(os.path.join(HERE, "check.log"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(log))
    with open(os.path.join(HERE, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"wrote {len(entries)} records to {OUT}")
    for e in entries:
        print(f"  {e['file']:52s} {e['status']:22s} np_check={e.get('np_check', {}).get('valid', 'not run')}")
    if args.check and not all(e["np_check"]["valid"] for e in entries):
        raise SystemExit("np check: at least one draft is not valid; see check.log")


if __name__ == "__main__":
    main()
