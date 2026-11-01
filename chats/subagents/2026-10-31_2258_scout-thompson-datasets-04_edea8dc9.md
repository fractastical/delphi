# Subagent: Scout Thompson datasets 04

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-10-31 22:58 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 03:12 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `edea8dc9-4005-44d7-b59a-8006c2895789`

---

### 2026-10-31 22:58 — Turn 1 (User)

> You are a dataset scout in a swarm for the repo at /Users/jdietz/Documents/GitHub/dev/delphisci. First read test-data/dataset-scouting/INSTRUCTIONS.md in full and follow it exactly. Your slice is test-data/dataset-scouting/queue/darwin-05.json (10 claims from Darwin's Origin of Species; project 'darwin-origin'). For each claim in the queue write test-data/dataset-scouting/darwin-origin/<claim-id>/datasets.json (and optional REPORT.md), then run `node test-data/dataset-scouting/validate.mjs darwin-origin/<claim-id>` and fix errors. Set scout.kind='cursor-subagent', scout.model to your model id, scout.run='darwin-05'. Hard rules: only record URLs/DOIs/numbers you actually fetched, with the HTTP status; never invent anything; describe data, do not run the test or state what the data show; do not write outside your own claim directories; do not edit claim files, docs/, nanopubs or test-data/claim-tests/; do not download over 1 MB; do not git commit. Budget about 15 HTTP requests per claim; prefer API calls returning counts or field lists. Reuse test-data/organisms/merged/datasets.json where it covers the variables (cite id in reuses_organism_dataset). Do all claims in the slice. Final response: one line per claim `<claim-id> <status> <best dataset or 'none'>`, plus a count of validation failures left (should be 0).

**Assistant:**

With 10 claims and many datasets to verify, I'm planning to write a Python script to batch-check URLs and query APIs efficiently, keeping it outside the repo in /tmp, rather than making individual requests one by one.

I'm planning to build a small logging script in /tmp that fetches URLs with a timeout, caps the read size, and records status, size, and a snippet for each request. I'll first batch-check the roughly 40 unique landing page URLs, then move on to running searches per claim.

That got rejected since the parent turn ended, so I should retry, maybe running it in the background this time.

I notice /tmp/scout already has other files from different scouts, so there's a collision risk if they share the same directory. I should use a unique directory name instead, like /tmp/scout-darwin05.

The shell tool keeps failing, possibly from concurrency with many agents running at once — I'll retry and check.

The heredoc commands got rejected, so maybe that's the problem. I'll switch to using the Write tool for files instead.

Maybe the requests library isn't available here, so I'll switch to urllib instead.

I've recorded the landing statuses: NCBI GEO is blocked by a recaptcha, Open Tree timed out, Morphobank returned 403, GBIF/POWO are blocked by Cloudflare on web (though their APIs may still work), and MorphoSource has anti-bot protection. Given these blocks, I should shift to doing claim-by-claim searches via APIs instead, so I'm checking the organisms adapters for available endpoints.

To save effort, I'm writing a reusable helper function that takes a URL and field path, then prints a compact summary — total hit counts and titles — so I can batch through claims efficiently without pulling full records each time.

For the intermediates claim, I need morphological character matrices spanning extant and fossil taxa, fossil occurrence and age data, and phylogenetic trees. I'm planning to check PBDB for occurrence counts, search MorphoBank/Zenodo/Dryad for matrix data, and try the Open Tree API for phylogenies.

It seems heredoc creation is causing failures, so I should use the Write tool instead for scripts.

I'll use the shell's timestamp for scouted_at despite the odd clock reading. I need to be careful to only cite sources I've actually seen, like the Zenodo record for the Darwin wasps morphological data matrix.

I should verify a few more records: the Zenodo files for 13913229, the Dryad API for the primates dataset, and confirm the PBDB Equidae and Open Tree API numbers (noting the landing page returns 503 but the API works with ~2.4 million tips). Then I'll move to claim 2, which covers within-genus phylogenies and species distances for large genera, checking Open Tree taxon info, BOLD systems stats, and BirdTree data availability, batching these queries together to limit the number of turns.

For claim 2, I also want NCBI counts (esearch for Carex organism and taxonomy counts), plus a check of Dryad, Zenodo, and Open Tree documentation for genus-level phylogeny references. I'll look at BirdTree and TimeTree landing pages for content snippets confirming tree data availability, and check TRY's redirect behavior too.

I should also check Open Tree of Life for a subtree confirming the genus Carex, which means first resolving the OTT id via tnrs match_names, then querying node_info. I'll also try the BOLD systems API and GBIF API for additional specimen data, though I'm not fully certain of the correct endpoints.

For claim 3, the Drosophila dataset from Coyne & Orr is on Dryad (g5g43), so I need to pull the dataset's files via the Dryad API using the DOI and version endpoints. I should also check Mouse Phenome Database for sperm count measures, try GEO's eutils esearch for "hybrid sterility testis" since recaptcha blocks direct access, and search Dryad for terms like "hybrid sterility F1 pollen fertility interspecific cross."

I realize importing c2 directly would re-run its code since there's no main guard, so instead I should avoid that import entirely and move the shared title into a utility module that both files can reference safely.

I want the Dryad g5g43 dataset's file list, so I'll follow its version link to get the files endpoint. The Zenodo entry on postmating-prezygotic evolution looks like another Drosophila study, not relevant here, so I'll skip it and just fetch the Dryad file list.

I should grab the file ids and fetch the CSV itself since it's small enough, rather than just the header.

The Dryad API requires a token, but the public file stream URL for direct download should work without authentication—I'll give that a shot.

I only have file metadata confirming raw data exists, not actual column content, so I need to flag that as unverified. The verdict is partial and limited to Drosophila—the abstract lumps inviability and sterility together as one dichotomized measure, so I can't confirm the claim separates those stages.

For claim 4, I'm thinking through how to pull high-latitude Pliocene fossil counts from the PBDB API using interval and latitude filters with a rowcount flag, then cross-check against GBIF occurrence searches filtered by continent and genus, GenBank counts via eutils, and possibly POWO or TimeTree for divergence times, though TimeTree likely lacks a stable API and POWO may block requests.

The Pliocene query with latmin=60 pulled 171 records against a total of 109,350 for that interval. I'm now checking PBDB's genus-level occurrence data for claim 5, looking at fields like abundance, geographic coordinates, and time ranges.

I should also check other counts: PBDB Mammalia occurrences for the Miocene, Neotoma's dataset and site counts via their API, GBIF occurrence totals, and Open Tree clade sizes. I'll also search Dryad and Zenodo for relevant datasets on species survivorship and fossil geographic ranges, and confirm PBDB's taxa list can return first/last appearance data alongside coordinates.

I should cite Dryad 10.5061/dryad.8330, so I'll fetch its API details for the landing URL before moving to the next claim about PBDB.

Now for claim 6, I'm checking PBDB taxonomy hierarchy, GenBank, Open Tree's API stats (2,385,875 tips, 1,931 source studies), and trying Catalogue of Life's checklistbank API, though the endpoint structure isn't clear yet. MorphoBank returned a 403, and my Dryad search for geometric morphometric data wasn't relevant, so I'm trying different search terms around treeness and phylogenetic signal, and will also try TreeBASE's phylows search endpoint as another option.

For claim 7, I need details on sPlotOpen, which redirects to an idiv page — checking plot counts and whether it includes CWM height data. TRY appears to require a request rather than offering an open API, and I'm also verifying the WorldClim download URL for the bioclimatic variables zip file.

I'm uncertain about BIEN's API endpoint, so I'll likely just check its landing page rather than hunt for an unclear API path. I'm planning to search Dryad for Hargreaves-style transplant studies on range limits and abiotic/biotic poleward-upper elevational gradients, plus Zenodo for plant height/elevation/latitude/species richness datasets, and possibly check GBIF for richness counts — so the plan is sPlotOpen page text, a WorldClim HEAD request, two Dryad searches, one DataCite search, and a Zenodo search.

The sPlotOpen HTML page isn't informative enough, so I'll try the DataCite DOI API for its metadata, or pull details from the associated Sabatini et al. 2021 GEB paper via Crossref to get dataset counts.

I need to confirm whether sPlotOpen's CWM_CWV table actually includes plant height among its TRY-derived trait means, along with the header table's lat/lon/elevation fields.

For claim 8, I'm weighing several germplasm database APIs -- Genesys PGR, GRIN-Global, TRY, and possibly Dryad/Zenodo searches for cultivar trait variation studies -- to find usable endpoints for crop descriptor data.

The Genesys API returned a 401 on stats, and the sPlotOpen DataCite metadata lacks a description, so I'll mark it as partial/unverified. To verify its contents I could check the Sabatini 2021 paper via Crossref, which might require citing an additional DOI—I'll handle that in the next batch. Moving on to claim 9.

For meristic trait data I'm weighing FishBase's API (possibly defunct), vendored organism datasets with vertebral counts and floral traits, Dryad and Zenodo searches for intraspecific trait variation, VertNet's API for vertebrae-related records, and GIFT's trait metadata endpoint—MorphoSource is blocked by a bot challenge. I'll start by checking the vendored organism datasets first.

It worked earlier using a relative path from the repo's working directory, so I'll check the directory listing again.

Wait, the test-data directory just disappeared -- maybe another process or agent is running git operations like checkout or stash concurrently. I should check git status and list the directory contents to figure out what's going on.

The repo state looks changed - claim-sources and test-data directories seem to have vanished entirely, like the working tree got reset to a different commit. That's concerning, especially with mention of diverging 3 and 486 commits, so I should check git log, git status more thoroughly, and see if those files exist in another worktree.

It looks like the repo is mid-restructure, with things being moved into `engine/` and `site/`. The files I'm looking for were likely relocated into `engine/`, so I should search there for the test data.

I notice the repo has been restructured under engine/, so the darwin-05.json queue file I was looking for isn't where I expected. I need to check engine/test-data/dataset-scouting/queue and see if the darwin-origin directories exist there instead, since my task calls for writing to test-data/dataset-scouting/darwin-origin/<claim-id>/.

I notice the repo got restructured into an engine/ directory, so my task path now points to engine/test-data/... instead. I should write my files there and check darwin-origin for my ids to make sure none of my claims are already present.

I'm saving this under the darwin-origin test data path and will note it in my final answer, with a quick check later that the darwin-05 engine queue has matching ids. Next I'll continue scouting claims 9 and 10, follow up on sPlotOpen, check the organisms dataset file, and update the org.py path accordingly.

I'm uncertain whether fishbase-v25-04 actually covers vertebral count data, so I'll leave that citation unconfirmed and skip it for now. Moving on to claims 9 and 10, I need to check sources like the FishBase API, VertNet API, GIFT API, and Dryad.

Rather than trying to pull the full FishBase species parquet (too heavy for a range read), the simplest approach is just fetching the FishBase summary page for Gadus morhua and scanning for the "Vertebrae" field directly in the morphology section.

The VertNet API attempt fails with a cert issue, so I'll mark it as unreachable while the landing page itself returns 200. Moving to claim 10, GloNAF's landing page works fine, so I'll check accessing its data through Python.

Then I'm checking GRIIS via its GBIF-hosted checklist, querying the GBIF dataset search API for GRIIS entries like the New Zealand checklist, and also considering GISD's landing page and the IUCN Red List API which likely needs a token. I'll also try GBIF occurrence searches filtering by establishmentMeans to get introduced versus native species counts for New Zealand.

I should pull details on the Zenodo GloNAF record (files, license, size), check the GRIIS New Zealand checklist count via GBIF's dataset and species search APIs, and also gather the sPlotOpen Crossref abstract and the Dryad chapter 9 entry.

The abstract got cut off before confirming the trait data details, so I should fetch more of it to verify species composition and community-weighted mean traits are included, and also check the GloNAF regional data file.

I'm noting that the abstract mentions 18 traits from TRY CWM but I haven't individually confirmed plant height among them, so I'll flag that uncertainty. Now I have enough to write the ten datasets.json files, planning to generate them with a small Python script that builds each claim as a dict and writes out the files using timestamps from the log.

For ch09-01, I'm working through the variables needed (morphological matrices, fossil occurrences, phylogeny) and recording per-dataset results: Morphobank returns a 403 error on both endpoints I checked, so it's unreachable and I'll suggest other tools investigate it further, while I continue checking the paleobiology database.

Paleobiodb returns 200 with occurrence data including fossil ages, but lacks character matrices or ancestral reconstruction, so it's only a partial match. Open Tree of Life's landing page is flaky (timeout then 503) but its API works and returns millions of tips and thousands of source trees — useful for living-species branching but still no morphological data, so also partial. I'm also noting a Zenodo record on Darwin wasps I found via the API that I still need to verify.

Checking the dryad.4g42q primates record, landing page returns 200 with CC0 license and a compiled phylogenetic matrix for primates—partial match. I note the Dryad.8120 Lissamphibia fossil-terminal-taxa record only appeared in a Zenodo title search, so I'll flag it rather than verify directly, and I'm tracking search log inconsistencies like the Zenodo hit count looking like API noise and missing total counts from DataCite.

Moving to status: this is partial since clade-wide data isn't fully confirmed, and I need to note that MorphoBank is inaccessible via scripted access (403 error) and no dataset contains true ancestor information. Now I'm compiling exact queried URLs with their encodings for the search log, then moving to the next variable set covering species-level phylogenies, genus size, and pairwise distances between congeners, starting with the Open Tree of Life API results.

For BOLD Systems, I only got a 200 response on the landing page without testing the actual API, so I can't verify any claims about pairwise distance matrices or DNA barcode data — I should mark this as partial with an empty variables_present list rather than overclaiming what wasn't actually verified by a real query.

For BirdTree, same issue — I only confirmed the homepage loads but haven't verified the actual page content about avian trees, so that needs more checking before I can call it complete. Meanwhile for NCBI GenBank, I actually did get solid numbers: Carex count of 73,246 from nuccore and 1,701 species under the Carex taxonomy, which gives me something concrete to work with there.

Looking at timetree, the landing page confirms 5,072 studies and 208,740 species, with the downloads page also loading fine — still partial since I haven't dug into whether this actually supports genus-wide tree imbalance analysis. For Try-Plant-Trait, I found a substantial dataset — 22,860,407 trait records across 306,701 taxa — but this is raw trait data, not a prepared distance matrix within a genus, and I'm not sure if access requires a request, so I shouldn't claim otherwise. My searches on Dryad turned up nothing (zero hits) and DataCite gave 95 hits but none seem clearly relevant to genus-wide tree imbalance work. Overall this leaves me with a partial picture across these sources.

Phylogenies clearly exist, but there's no pre-compiled dataset of genus trees sitting ready — I'd need to assemble one myself, likely by pulling from Open Tree of Life's synthetic tree via their API. I'm thinking I should run a couple more checks on BOLD and BirdTree, and also use Open Tree's node_info endpoint to get something like the number of tips in Carex as supporting evidence — but I need the ott_id from the TNRS lookup first, which got cut off earlier, so I'll rerun that and follow up with node_info.

The Carex node has 5,519 tips but is flagged as not monophyletic, so I'll note that caveat with the MRCA node's tip count. Now I'm writing a script to generate the JSON output files using the observed timing data.

Moving to the third claim about speciation genetics in Drosophila, I'm checking the Dryad datasets for cross-failure and hybrid sterility data. The main dataset returns a 200 but downloads fail with 401/403 errors so I can't verify columns directly, though the abstract shows inviability and sterility are dichotomized together rather than separately, making it a partial match; meanwhile the generic Dryad repository portal entries look like they should be rejected since they're not actual datasets, just the platform itself.

For the mouse phenome database I'm uncertain - the landing page loads but I have no confirmation it covers interspecific F1 hybrids, so rather than falsely asserting rejection I'm marking it partial with unverified variables. I'm now checking GEO, where the landing page hit a CAPTCHA wall but an eutils search for hybrid sterility testis studies returned 27 results.

Beyond those, I'm noting some additional plant datasets found via search - a Dryad entry on costly hybridization in Boechera rock cress, and Zenodo records on Mimulus postzygotic barriers and pre/postzygotic asymmetry - though I haven't fetched full details on any of these yet and should verify at least one through the Dryad API.

Moving to chapters 11-12, the variables involve dated phylogenies of North America-Europe sister lineages, ancestral ranges, and Pliocene fossil occurrences at high latitudes. I'm checking PBDB data for Pliocene fossils above 60°N latitude, finding totals split across longitude bands that suggest high-latitude Pliocene circumpolar fossil occurrences do exist, supporting that variable.

Since the claim also needs divergence time data which PBDB doesn't provide, I mark this one as partial. GenBank shows Carex sequences exist (73,246 records) but without dating info, again partial. GBIF occurrence data confirms modern Carex distributions in both Europe and North America (millions of records each), which fully supports the modern distribution variable.

POWO is unreachable due to Cloudflare blocking both landing page and API. TimeTree shows a large phylogenetic database (5,072 studies, 208,740 species) with working downloads, but only partially supports the claim since it covers one variable at a time.

I'm also checking several Dryad datasets on Beringian and disjunct plant clades—dogwood phylogenomics, Ranunculus glacialis biogeography, Quercus, and others—and plan to verify one or two of these through the Dryad API before moving to the next set of variables involving fossil occurrences, geographic ranges, abundance, and clade survival data.

For the paleobiology database, I'm finding good coverage: over 21,000 Mammalia species with first/last appearance fields, 9,031 genera, and tens of thousands of Miocene occurrence records with coordinates and abundance data where available. The dataset supports taxon durations, occurrences, and geographic range variables well, though true ancestry/descendant relationships aren't directly present—genus-level survivorship would need to be derived from the appearance fields instead, which I think still counts as a partial match for the claim.

Since true species-level ancestor-descendant data isn't available, I'll scope the variable as genus-level persistence proxy instead. I'll mark PBDB as "holds" for that restricted genus-level scope, but keep overall status "partial" since it doesn't cover the literal species-level claim.

Checking Neotoma, GBIF, and Open Tree against the claim's scope — most come back partial since they're taxon-specific or focused on modern analogues, while Open Tree's clade sizes look more promising. For ch13-01, I'm noting the character matrix and taxonomic hierarchy needs, with Paleobiology Database giving partial family/genus counts and GenBank returning landing-page data with counts for taxa like Equus.

Catalogue of Life gives a working ChecklistBank dataset with a solid hierarchical taxonomy, but since it's a classification rather than independent character data, it's circular for testing tree independence — so still partial. MorphoBank is unreachable (403), but I found promising leads in Zenodo's darwin wasp matrix and a Dryad primate matrix.

For TreeBASE, the landing page works but contents are unverified, so I'll log it as partial without fully relying on it. Moving to chapter 3-6 variables on species richness and climate: TRY gives a huge trait database but doesn't confirm plant height individually or site-level richness, so partial; WorldClim's bioclimatic data file is confirmed reachable (just under 50MB) and covers climate, so also partial.

Checking BIEN, its landing page loads but I can't verify deeper content, so I'm marking it partial with a "landing only" note. Dryad's search returns zero results for the Hargreaves transplant datasets, so I'm rejecting that source. GBIF's web landing hits a Cloudflare block but the API itself returns a live occurrence count near 3.9 billion records, giving partial support for richness but nothing on plant stature. sPlotOpen's DOI resolves to an iDiv page flagged as not the latest version, and the Crossref abstract describes over 95,000 vegetation plots with elevation and community-weighted trait data.

I'm weighing whether sPlotOpen counts as partial given it has species richness derivable from its matrices, elevation, latitude, and CWM traits, but lacks individual plant height verification, climate variables, and any intraspecific stunting data since it only reports community-weighted means — so I'll call it partial, though probably the strongest source so far. I also found a Zenodo/Dryad entry on krummholz winter damage that's worth including as another partial lead, and a VegVault dataset on DataCite linking sPlot and TRY traits that I should check further.

Shifting to the cultivar trait variables, I checked Genesys and found the landing page and API root return 200 but the stats endpoint returns 401, so it's partial since passport and characterization data exist but full API access needs authentication. For GRIN-Global, the generic landing page is just the software project site and should be rejected, but the USDA npgsweb GRIN-Global search page itself returns 200 and looks like the real accessions database — I haven't confirmed descriptor data there yet, so that's still partial too.

For the next variable on serial structure variance, I found Zenodo datasets on wheat and Noug domestication that each cover a single crop, so status there is partial rather than a clear gap. Moving to within-species variance in serial structure counts, I'm checking Dryad, which is just a portal and gets rejected, with searches for vertebral counts in snakes turning up nothing and stamen counts returning one hit on Penstemon nectary size.

FishBase works though, showing Gadus morhua's page with a vertebrae range of 51-55 along with dorsal soft ray counts—useful per-species ranges but not individual-level samples, so partial. GIFT's API gives no results without a query, MorphoBank returns a 403, and MorphoSource throws up a bot-detection wall, leaving all three unverified or unreachable.

Vertnet's main site loads but its API hits an SSL certificate mismatch, so that's partial too. I'm finding some promising Zenodo records with meristic count tables for vertebrae, including one on snake vertebral morphology, though I'd need to fetch the actual record to confirm the data format rather than just the title.

FishBase gives ranges rather than variance, so marking that species-level data as partial with a gap for individual measurements, and plant data as a gap too. Moving to the introduced-vs-native species chapter, I'm checking GBIF occurrence counts for New Zealand, but filtering by establishmentMeans for INTRODUCED or NATIVE is returning zero results despite millions of total occurrences, which looks like the field isn't being populated as expected.

I'll note this as "returned count 0 with these filters" without over-interpreting, marking it partial. For GRIIS, I'm finding New Zealand's checklist with over two thousand species records under CC BY 4.0 license, alongside eighteen total GRIIS country checklists, which covers introduced species lists though impact data isn't verified yet.

For GloNAF, the Zenodo snapshot shows over 16,000 taxa across more than 1,300 regions including islands, with hundreds of source references under CC BY 4.0 — solid for plant distribution but limited to flora only, and I still need to verify the claimed donor/recipient region data since GloNAF's structure may not directly support that framing.

Checking GISD and IUCN next: GISD's landing and search pages respond fine but impact records remain unverified, while IUCN's API returns a 404 without an authentication token even though the main site loads — so I'll mark these partial pending token access. I also found a couple of relevant island biodiversity datasets through DataCite and Zenodo searches, including a global island richness study and a Pacific introduced flora dataset, though I haven't confirmed their relevance yet.

Now I'm planning a batch of Dryad and Zenodo API checks across several dataset identifiers to pull title, license, storage size, and a truncated abstract for each, skipping file-level details for now.

I'm now planning out the generator script that will build the test dataset entries, organizing them by source directory, and working through the landing timestamps for each API call across the batch to keep everything consistent.

I should double check the model identifier string before running, and also verify the license parameter mapping in the dataset helper function to make sure the variants I passed are handled correctly.

Going through the remaining evidence entries one by one—sPlotOpen's redirect notice, Neotoma's sample record, CoL's unconfirmed fossil taxa, GBIF's PBDB Pliocene count, the Drosophila landing page fetch, Zenodo's API URL, and Genesys's BrAPI listing—they all check out against what's actually documented on each page.

For the FishBase gap case, I'm reconsidering whether "gap" is the right label since partial per-species ranges do exist and could support a crude spread measure—leaning toward marking it "partial" instead and adjusting the summary accordingly. The reuses_organism_dataset fields are null across the board, and the BirdTree/timetree entries look fine too.

I need to fix the pacifLora id casing, and the other content checks look fine as-is. Let me correct that and rerun, then double check there aren't any stray files left over.

All 10 claims in slice darwin-05 are scouted and written, and all 10 pass `validate.mjs`. I did not write any `REPORT.md` files.

The repo was restructured while I worked, and `test-data/` now lives under `engine/test-data/`. I wrote the records to `engine/test-data/dataset-scouting/darwin-origin/<claim-id>/datasets.json`.

- darwin1859-ch09-01 partial Zenodo 10.5281/zenodo.13913229 (extant+fossil Darwin-wasp matrix, one family)
- darwin1859-ch02-12 partial Open Tree of Life API (with NCBI and BOLD counts)
- darwin1859-ch08-01 partial Dryad 10.5061/dryad.g5g43 (Drosophila pairwise isolation data)
- darwin1859-ch11-12 partial PBDB Pliocene occurrences (plus GBIF API)
- darwin1859-ch14-11 partial PBDB (first/last appearances, coordinates, abundance fields)
- darwin1859-ch13-01 partial PBDB taxonomic hierarchy (plus Open Tree)
- darwin1859-ch03-06 partial sPlotOpen 10.25829/idiv.3474-40-3292 (plus WorldClim 2.1)
- darwin1859-ch01-12 partial Genesys PGR (passport-level only; descriptor data not confirmed)
- darwin1859-ch05-11 partial FishBase species pages (per-species min–max ranges, not individual counts)
- darwin1859-ch06-14 partial GloNAF v2.02, Zenodo 10.5281/zenodo.17105725 (plants only)

No claim got a dataset that fully covers its variables, so every status is `partial`. Several sites could not be inspected by script:
- **Blocked or challenged:** MorphoBank and POWO returned 403, and MorphoSource served an anti-bot page.
- **Landing page only:** TRY, GRIN-Global, BIEN, VertNet and GISD were not queried further.
- **Unverified columns:** Dryad file downloads returned 401/403, so the Drosophila column names are unchecked.

Validation failures left: 0.

_Tools used: Read ×2, Shell ×39, StrReplace ×2, UpdateCurrentStep ×2, Write ×24_
