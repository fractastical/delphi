# Subagent: Scout Thompson datasets 04

- **Parent chat:** [do we need to go rhough and validate more of the claims ? we should have another](../2026-10-31_2254_do-we-need-to-go-rhough-and-validate-more-of-the-claims-we-s.md)
- **Started:** 2026-10-31 22:59 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 04:47 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Final status:** success
- **Transcript ID:** `28b96b67-bcd4-4b6c-a556-9cb15640dc60`

---

### 2026-10-31 22:59 — Turn 1 (User)

> You are a dataset scout in a swarm for the repo at /Users/jdietz/Documents/GitHub/dev/delphisci. First read test-data/dataset-scouting/INSTRUCTIONS.md in full and follow it exactly. Your slice is test-data/dataset-scouting/queue/levin-02.json (claims from Michael Levin papers on bioelectricity, regeneration, xenobots etc.; project 'levin-papers'). For each claim in the queue write test-data/dataset-scouting/levin-papers/<claim-id>/datasets.json (and optional REPORT.md), then run `node test-data/dataset-scouting/validate.mjs levin-papers/<claim-id>` and fix errors. Set scout.kind='cursor-subagent', scout.model to your model id, scout.run='levin-02'. Note: many claims report a specific experiment (e.g. planarian regeneration, Xenopus, xenobots); look for the paper's own deposited data (Dryad/Zenodo/Figshare/BioImage Archive/GEO/SRA), and general repositories holding comparable variables. If the only data is in a paper supplement or is not public, status is partial or gap and say so. Hard rules: only record URLs/DOIs/numbers you actually fetched, with the HTTP status; never invent anything; describe data, do not run the test or state what the data show; do not write outside your own claim directories; do not edit claim files, docs/, nanopubs or test-data/claim-tests/; do not download over 1 MB; do not git commit. Budget about 15 HTTP requests per claim; prefer API calls returning counts or field lists. Do all claims in the slice. Final response: one line per claim `<claim-id> <status> <best dataset or 'none'>`, plus a count of validation failures left (should be 0).

**Assistant:**

With 11 claims to verify, I'm budgeting roughly 15 requests per claim and planning to be efficient by sharing findings across claims where possible. I'll start by checking validate.mjs and an example, then move into searches covering anthrobots (PMC10811512, Zenodo/Dryad for Gumuskaya), planarian two-headed regeneration, Xenopus ectopic eye studies, and lobolab's planform work.

I'll also want to hit the Allen Brain Cell types API, BioModels for ion channel/gap junction models, ModelDB, IUPHAR, the BETSE GitHub repo, NCBI genome data for Schmidtea mediterranea, AnAge, and PlanMine — running these searches in parallel to save time.

I'll write a helper script to handle fetching multiple items at once.

That's strange, some command is failing approval. Heredocs might be the issue, so I'll try simpler commands instead.

I'll keep the commands simple and write a helper script at /tmp/l02/c.sh using the Write tool.

Maybe commands through ./c.sh aren't allowlisted and need approval that times out, while curl itself is allowlisted directly. I'll try running curl directly instead, chaining commands with && like the earlier successful attempt.

Since curl works directly, I'll write a small Python helper script to handle this and run it, falling back to curl piped through jq if the script needs extra approval steps.

Use urllib instead.

I should check the data availability statement and the supplement filenames.

I'm checking whether anthrobots-04 data and the day 0/day 7 spheroid claims are tied to a specific GEO or BioStudies record, looking at the supplementary files from the 2024/2025 papers to pin down the source.

That PMC file seems too small to be useful, and searching GEO for "Anthrobot" or "Gumuskaya" isn't turning up results. Given limited budget, I'll try one more search combining Gumuskaya with GEO accession terms before moving on.

GSE281379 looks promising - it's the anthrobots lifecycle transcriptome (day 0, day 10, etc.), potentially relevant to cilia genes though not exactly day 7. I should check the GEO landing page and get the sample count and titles.

I've got 22 good samples including day 0 and day 10 bots, progenitor, and ALI, though the GEO landing page hit a reCAPTCHA check despite returning a 200 status — I'll note that and rely on eutils evidence instead. Now I'm moving on to the planarian bundle, starting with Planform and Dryad searches.

These two planaria papers look relevant — one on non-senescence and stress in planarian species for the wisdom angle, another on intraindividual genetic diversity for the chaotic genomes angle. I should grab their DOIs, then check the Planform page for data download details.

I need to map titles to DOIs, so I'm writing a small script to parse the Dryad search JSON results and extract that pairing.

I should also check the Non-senescent dataset's description, the Dugesia diversity data, and the Dryad entry on Xenopus eye bioelectrics, plus the Planform download page. Let me pull the dataset description for dryad.v15dv425h via the API.

Now HEAD planformDB for size, and search other planarian repositories (Zenodo, Figshare, DataCite).

Zenodo's total of 288097 looks unreliable given how its query handles OR semantics, so I'm noting that caveat. DataCite returned 4 hits for the planarian two-headed regeneration search, and I'm checking those titles now. For Figshare, the POST request returned an empty array—0 hits with a 200 status—so I'm recording that as zero results rather than an error.

I'm not finding anything relevant for tail eyes, so I should check Xenbase and BioStudies for Xenopus eye data, along with the Blackiston & Levin 2013 paper on ectopic eyes in Xenopus tadpoles enabling light-mediated learning, searching Europe PMC for data availability.

The key papers here are Blackiston & Levin's 2013 JEB study and Blackiston et al.'s 2017 npj Regenerative Medicine paper—I should check their data availability statements and supplements for relevant information, keeping in mind PMC pages sometimes trigger reCAPTCHA blocks.

I'm noting the ectopic eye papers have little supplementary data available—the 2013 paper has none and the 2017 paper only includes a single image file. I tried checking Xenbase's API but got rate-limited, so I'll note that and move on. Now I'm turning to planarian head-number claims, starting with Durant 2017's work on early bioelectric signals.

I want to check Europe PMC data availability for these studies and look into Planform's database too—the .edb file is only 744KB, under the 1MB threshold, so I could download and inspect it to see what format it's in and whether I can count "ectopic head" experiments without needing to run any actual tests.

I'm checking the schema for drug entries like gap junction blockers, experiment fields, result sets, and publication records, looking specifically for author names like Levin, Nogi, and Emmons-Bell.

I'm counting the 45 gap junction blocker experiments and cross-checking whether key studies like Emmons-Bell 2015 and Nogi & Levin 2005 are included, along with double-head and re-cutting manipulation experiments on Girardia and Dugesia dorotocephala.

The 282 experiments split evenly into 126 headless and 126 D. dorotocephala cases seems coincidental. I should double check whether publications like Emmons-Bell 2015 or Durant 2017 fall within the dataset's year range, so I'm going to verify the max publication year and look at titles from 2015 onward.

I'm noting that Planform covers Nogi & Levin 2005, Beane 2011, and Oviedo 2010, but seems to be missing Emmons-Bell 2015, Durant 2017, and the serial recut work—so it's only a partial match. I want to verify whether the Emmons-Bell 2015 paper is open access.

Searching Europe PMC for Emmons-Bell, Durant 2017, and the Levin "gap junctional blockade" paper, plus checking for any related Zenodo or Figshare supplementary datasets.

I should check the PMC4661923 supplementary materials and data availability section, though the two-headed planarian paper from Oviedo probably isn't needed. Rather than pulling the zip from the Europe PMC API directly, I'll look at the PMC page itself for supplement links.

I'm moving to glue-04, thinking through Allen Brain Cell Types patch-seq data alongside GEO and PRIDE, and sketching out the Allen Cell Types API query I'd need to pull specimen details.

I'm also checking DANDI Archive for the Gouwens 2020 Patch-seq dataset (possibly dandiset 000020), planning a GEO/eutils search for "Patch-seq," and considering PRIDE's project search API as a weaker fallback for counting patch-clamp related entries. Time to actually run these queries.

I'm looking at the Allen Cell Types dataset of 2333 cells with electrophysiology and specimen fields, checking whether it also includes transcriptomic markers alongside the ef__ and dendrite type tags, before moving on to check DANDI.

The heredoc approach didn't work, so I'll write the content to a file directly instead.

I'm noting that the Allen Cell Types transcriptomic data isn't paired per-cell in this API, but the Gouwens 2020 Patch-seq dataset (DANDI 000020) pairs ephys NWB files with transcriptomic data likely deposited separately in GEO.

DANDI 000020 looks good — CC-BY-4.0 and open, and GEO has 44 GSE entries matching Patch-seq. Now I want to check the assetsSummary for file count and size, so I'll look at the end of that JSON.

The PRIDE keyword search isn't filtering well—searching "membrane potential" surfaced unrelated hits like milk-related projects rather than relevant data. I'll mark PRIDE as rejected since it only offers proteomics data, lacks voltage measurements, and returned unrelated top results.

For DANDI 000020, I'm noting it has 4435 files across 1040 subjects totaling 141.9 GB of NWB ephys data, but I haven't verified whether paired transcriptomic data exists in GEO—the companion Gouwens 2020 dataset remains unconfirmed. I'll run one quick GEO search for "Gouwens Patch-seq" to check before mentioning it as unverified.

I'll just cite the GSE count since the title didn't match cleanly in the search results. Now I'm checking other claims about tame-21 and boundary-26 against resources like BioModels, ModelDB, IUPHAR, and BETSE, starting with a BioModels search.

I'm getting a 400 error from BioModels, so I should inspect the error body and try the new search API endpoint instead. I also want to check the ModelDB listing to estimate how many model IDs it contains, and explore ModelDB's API for searching models by name.

I found only 2 matches for "gap junction" in BioModels. Now I'm checking ModelDB, which lists 1931 models, and trying to figure out the right API endpoint or search query to filter for gap junction models there.

The "gap junction" query matched Maleckar2008 and Verma2016, though I haven't verified if those models actually contain gap junctions—just that the search matched them. I'll skip digging deeper into ModelDB's API for now and just note what I've found so far.

For BETSE's GitHub repo, I noticed the license field returned an object rather than a simple string, so I should fetch the license details and SPDX identifier along with the repo's root contents to check example configs.

With BETSE confirmed, I'm checking other bioelectric model sources - IUPHAR needs an API key so I'll just check its landing page status, along with ModelDB and Allen Cell Types. For planaria genome data, I'll look at NCBI datasets, AnAge, PlanMine, and SRA next.

For Schmidtea mediterranea specifically, I'm planning searches against assembly and SRA databases via eutils, checking if AnAge even covers planaria species, and verifying the PlanMine landing page - I've already got the Dryad non-senescent and Dugesia diversity results.

SRA shows 6382 total runs with 149 WGS experiments, but the assembly query got rate limited so I'll retry that later. Meanwhile the AnAge dataset is small enough to download directly, so I'll grab it and search for Schmidtea or planarian entries in the taxa data.

I'm noting that the AnAge record for S. mediterranea has no max longevity listed with low data quality, while S. polychroa shows 3.6 years, and I'll avoid misreading the shifted column data. Next I want to pull the NCBI assembly summaries for the nine genomes to get their names, strain types, and assembly levels.

The naming pattern suggests schMedA2h1 refers to an asexual haplotype and schMedS3h1 to a sexual one, but I should only state that as an inference from the names themselves rather than something verified from the fetched source.

Beyond that, I need to check the PlanMine landing page, do HEAD requests for IUPHAR, ModelDB, and Allen landing pages, and retry Xenbase before writing things up.

Xenbase is now responding, so I check PlanMine's landing page title too, but decide not to dig into Xenbase's search API further since it's a curated resource and I've only fetched the landing page. Given the limited data I actually verified, I lean toward a partial verdict.

Curl succeeded with a 200 status using the -L flag, while Python's SSL handling is failing, so I'll just go with curl instead.

PlanMine's InterMine API checks out with version 26 and the organism list. I'm also verifying PRIDE versus GEO for glue-04 and its 2023 claim, then checking BioImage Archive and Dryad options for planarian bioelectric videos, noting BioStudies turned up nothing for levin-2023-agential-08, and now searching Zenodo.

Dryad gave two queries, DataCite zero hits, and BioStudies results seemed mostly unrelated though one might match. I'll quickly check Zenodo for tail eye data, run one request each for agential-08 and tame-03, and search BioStudies for planarian "voltage" along with a quoted Zenodo search for "Xenopus ectopic eye" and "planarian bioelectric."

Zenodo's total for ectopic eye searches is unclear and the hits seem unrelated, while BioStudies shows 736 planarian bioelectric hits that are mostly mirrored text articles rather than actual datasets. I'm now looking at a specific Zenodo entry on "planarian polarity editing" that appears to be an independent computational preprint rather than a data source.

Now I'm moving to write up the 11 claim files, settling on approximate timestamps around 2026-11-01T03:25Z and using "claude-sonnet-5.5" as the model id. For the first claim on AnthroBots, I'm working through the dataset details — the PMC landing page with its supplementary videos and PDF (data available only "upon reasonable request"), noting the fetch byte sizes, and cross-checking the BioStudies mirror of the same PMC article with its 8 files, figuring out how to represent the landing URL versus the API endpoint I actually used to retrieve it.

I'm also checking GSE281379 — 22 samples across day 0/day 10 bots, progenitor, and ALI conditions but missing day 7 and motility data — and dealing with the GEO landing page showing a reCAPTCHA interstitial, so I'm relying on eutils esummary as evidence while still recording the 200 status with a note. For the related 2025 paper (PMC12376695), I'm marking it as rejected or partial since it only states data is available upon reasonable request and isn't independently verified, while noting the key variables of interest: motility fractions, cilia imaging, and multiciliated cell counts at day 0 and day 7.

Then I'm moving to the next two claims, which share the same dataset structure referencing the Blackiston paper (PMC3587383).

Xenbase returned a 429 initially then 200, but no trial-level data confirmed, so I'll mark it as a gap. Next step is to contact the corresponding author for trial-level tables from the Blackiston & Levin 2013 and 2017 papers.

Checking levin-2022-tame-14 on head number/species shape: 1716 experiments, 119 publications spanning 2005–2018, 17 species; 282 experiments show "Double head" morphology, 126 "Headless," 45 involve octanol/heptanol/hexanol. It includes Nogi & Levin 2005 (innexin) and Beane 2011 (H,K-ATPase) titles, but doesn't list Emmons-Bell 2015 or Durant 2017 — the 2015 publications listed are Teashirt, Regional signals, yorkie, and β-catenin, with no Emmons-Bell entry. I need to be careful here since the claim counts "ectopic" queries.

The head count outcomes are encoded only as morphology frequencies, with no voltage maps or landmark shapes. For Emmons-Bell 2015 (PMC4661923), there's a supplement s001.pdf, but since it's a PDF rather than a structured data table, I'm leaning toward classifying papers like this as rejected rather than partial, though I'll still note them in the summary since they're primary sources. I'm also considering whether to create a dataset entry for PMC4661923 marked as a generic pubmed-central candidate with no suggesting source.

For PMC4988443, there's a supplementary zip whose contents I haven't inspected, so I'm weighing whether to list it as partial with a note about unknown contents, possibly checking its size with a HEAD request before deciding.

For the persistence-over-recuts candidates, I'm trying to verify whether Planform actually encodes serial cuts — I'd need to check manipulation records for multiple crop/remove actions, which isn't straightforward to confirm quickly.

That zip request actually returned an HTML interstitial page rather than real zip data, so I can't verify its contents. I'm also considering how the schema represents manipulations as a chain of actions, like successive crops or removals linked together, and whether I need to count cases where that chain depth reaches two or more after a given step.

Now I'm switching to writing the actual dataset files — planning a small Node script to generate the JSON entries rather than hand-writing all eleven, reusing shared objects across claims. I'm defining the first dataset entry for PlanformDB 2.5.0, including its landing page, download URL, DOI, and timestamps for when it was scouted and checked.

Since there's no formal SPDX license, I'll note it as custom permissive terms described on the landing page, and record the download as a ~744KB SQLite file I opened and queried directly. I'm now tallying the actual database contents — experiment counts, publication years, species, drugs, and specific morphology outcomes like double-head and headless phenotypes — to verify the dataset's claims per-variable.

For the Dryad entry, I've been using the API dataset endpoint as the landing reference since that's what I actually fetched, but I still haven't pulled species names or the files list — the abstract only mentions "two planaria species" without specifics, so I should do one more fetch to get the species and file details before finalizing this record.

I'm pulling together the search log entries across the various repositories—Dryad, Zenodo, DataCite, BioStudies, GEO—noting which searches had unclear hit counts so I can flag those appropriately in the generator.

Continuing down the list: planarian regeneration searches across Dryad, DataCite, Zenodo, Figshare, and BioStudies, then Xenopus eye/tadpole searches, and Europe PMC. I'm also recording the Figshare API's POST request format for its search endpoint, then compiling model repository results (BioModels, ModelDB, IUPHAR), Allen Institute and DANDI patch-seq data, and genome assembly/SRA counts.

Now I'm sketching out the dataset helper structure for wisdom-01 variables like ploidy, regeneration success, tumor incidence, and lifespan curves in asexual Schmidtea strains, logging the NCBI genome assembly evidence—nine Schmidtea mediterranea assemblies including four chromosome-level haplotype genomes with their accession numbers.

I'm noting the esummary results seem incomplete, with only seven of nine record sets returned, likely because older assemblies lack certain fields, so I'll mark that dataset as partial. I'm also tallying SRA with 6,382 records including 149 WGS entries as partial access, and starting to note AnAge's coverage.

For AnAge, I'm verifying how columns map for different species entries—S. mediterranea has blank longevity data with low quality/tiny sample flags, while S. polychroa shows a max longevity of 3.6 years from a captivity source rated medium/acceptable. The local dataset.zip is 169,150 bytes with 4,646 data rows, so I'll call that partial too. Now I'm checking PlanMine's organism list to see whether Schmidtea mediterranea strains are represented there.

Looking at the PlanMine landing page more closely, it references both asexual "Smed" and sexual "Smes" assemblies, and the organism query returns species like Dugesia japonica, Dendrocoelum lacteum, and Macrostomum lignano alongside Schmidtea mediterranea S2F2. For the Dryad dataset v15dv425h, I found it covers Schmidtea mediterranea and Dugesia tahitiensis in a 19-week factorial design examining population viability and feeding stress, licensed CC0 at about 4.69MB—it has population-level performance data but seems to be missing explicit asexual/sexual strain breakdowns.

The c5f0ps6 dataset looks tangential—it's about Dugesia subtentaculata haplotype diversity for one nuclear and one mitochondrial gene, relevant to genetic mosaicism in fissiparous planarians but a different genus with limited loci, so I'd mark it partial at best. For tumor incidence I'm not finding any matching dataset, so that's a confirmed gap to note in obstacles.

Moving to glue-04, I need live resting voltage per cell paired with matched transcript counts from the same cells, plus optionally proteomic and cell history data. Checking the Allen Brain cell types API, it has 2333 specimen records with electrophysiology fields like resting voltage, but the specimen detail table's 54 fields don't appear to include transcript data.

For DANDI dataset 000020, I'm finding a Patch-seq mouse V1 dataset under CC-BY-4.0 with 4435 files, 1040 subjects, and 141.9 GB—likely partial since it has ephys NWB data but I haven't confirmed paired transcriptomes or sequence data within it, and it's adult neurons rather than developmental slow voltage changes. Searching GEO for Patch-seq studies with electrophysiology turns up some hits like GSE350772, which I've verified does contain genuine Patch-seq cells based on its sample titles. For PRIDE, proteomics-only searches return unrelated results like dental calculus studies, so I'm leaning toward rejecting it since it holds proteomes but no paired voltage data.

Now moving to the modeling-focused tasks (tame-21 and boundary-26), I'm looking for published conductance models with voltage-gated channels, gap junctions, and gating parameters that could be simulated. Searching BioModels for "gap junction" returns two matches—Maleckar2008_AtrialMyocyte and Verma2016—with BioModels ID BIOMD0000000834 corresponding to one of these, giving partial support for this variable category.

Checking ModelDB, I find 1931 model IDs are accessible through the API, with concept-based search returning results and the landing page reachable, indicating partial coverage. IUPHAR doesn't appear to be reachable at all.

Betse looks like a legitimate executable simulator for channel and gap junction networks, BSD-2-Clause licensed, recently pushed with a PyPI release and config file present, though multistability itself isn't actually tested. I'll mark the verdict as holding for "executable implementation exists."

Given the claim's framing of feedback loops implementing dynamical systems with multiple attractors, modeling tools should suffice, but since I haven't verified multistability in a published model, I'll keep BETSE's verdict as "partial." Tame-21 gets the same partial treatment, and I should check Zenodo and the BioModels mapping next.

I should write the generator script next, but first I need to check the rest of validate.mjs to understand the dataset requirements like checked.at, method, and evidence fields.

That's odd, the directory seems to have vanished. Earlier the relative path worked with no explicit working directory set, so maybe the cwd was different then—let me check if the absolute path actually exists now.

That's odd—test-data only shows claim-tests now, but earlier I saw dataset-scouting content there. Something's changed the working tree, maybe another agent or worktree. I should check git status and see if dataset-scouting exists elsewhere.

The working tree looks like it changed drastically — different state, missing claim-sources and scripts — likely from a branch switch or concurrent activity by another process. I should check git log, stash list, and whether dataset-scouting exists in HEAD without altering the git state myself.

It looks like something else has concurrently restructured the working tree — files like claim-sources and scripts are gone, and even untracked queue files have vanished, while HEAD still points to dataset-scouting. This seems like a destructive concurrent change, so I shouldn't run git restore; I need to figure out a safe place to write my results instead.

Given the flux, the safest approach is to pull a read-only copy of validate.mjs from git history into /tmp for validation, build my outputs in a temporary scratch directory, and only once validated copy them into the proper repo claim path — rather than risk writing directly into a repo that might get wiped again. I still need to check whether validate.mjs and queue/levin-02.json actually exist in HEAD via git ls-tree.

The working tree seems mid-change, so I'll avoid touching it directly. Instead I'll write outputs to a temp directory, validate them using a copy of the validation script pulled from git history, then once confirmed, copy the results into the actual repo path.

I need to make sure the DOI is written bare, then move on to writing the generator script. For timestamps, I'm picking a consistent value around 2026-11-01T04:40:00Z based on the file modification times to use across checks.

Rather than fabricate precise timing for when each source was actually scouted versus checked, I'll just use the generation time uniformly for both the scouted_at and checked-at fields -- the slight imprecision is acceptable and not worth over-engineering.

I'm double-checking the PMC open-access flag and the pmcEmmons suggestion sources for glue-14 and tame-15, confirming which cases were actually flagged by the scout versus GPT.

Next I'll verify the repo directory still exists before running the generator and validation step.

The timestamp looks a bit off from before, but I'll go with it. I notice the test-data/dataset-scouting directory isn't in the working tree, so I need to create the proper subdirectories under test-data/dataset-scouting/levin-papers/ for each id and place my files there, though this will leave out validate.mjs and the queue files.

Since the validator isn't available in the working tree, I'll use the git HEAD copy instead, and copy the needed files over.

I notice the git index has staged deletions from someone else's restructure, not mine — HEAD already contains other levin-papers slices, and my 11 files are placed separately. Let me check whether any of my ids already exist in HEAD to rule out conflicts.

All 11 claims in `levin-02` have a `datasets.json`, and all 11 pass `validate.mjs` (0 failures left). Validation ran against a copy of the validator from git `HEAD`, because the working-tree copy had disappeared. Mid-session, `test-data/dataset-scouting/` (including `validate.mjs`, `INSTRUCTIONS.md` and the queue file) and `claim-sources/` vanished from the repo working tree. Staged deletions I didn't make also appeared in `git status`. I didn't touch git and only created my 11 claim directories under `test-data/dataset-scouting/levin-papers/`.

- levin-2024-anthrobots-04 partial GSE281379 (Anthrobot life-cycle RNA-seq, day 0 and day 10; the paper's own data are "on request", only 7 example videos are public)
- levin-2023-agential-08 gap none
- levin-2022-tame-03 gap none
- levin-2022-tame-14 partial PlanformDB 2.5.0 (open SQLite, 1,716 experiments)
- levin-2022-tame-15 gap none
- levin-2023-glue-09 gap none
- levin-2023-glue-14 gap none
- levin-2023-glue-04 partial DANDI:000020 (mouse visual-cortex Patch-seq, CC-BY-4.0; Allen API gives ephys features for 2,333 cells)
- levin-2022-tame-21 partial BETSE (BSD-2-Clause) plus BioModels
- levin-2019-boundary-26 partial BETSE
- levin-2025-wisdom-01 partial NCBI Assembly (9 S. mediterranea assemblies) plus Dryad `10.5061/dryad.v15dv425h`

Validation failures left: 0.

- **Records:** I wrote only `datasets.json`, with no `REPORT.md`. Every URL, status code and count in them comes from a response I fetched.
- **Fetch problems:** GEO's landing page returned a reCAPTCHA page, so GSE281379 details come from E-utilities. The PMC4988443 supplementary zip returned an HTML interstitial, so its contents are unverified. IUPHAR's API needs a key (401). Xenbase returned 429 on first try, then 200.
- **Timestamps:** `scouted_at` and `checked.at` are the generation time (2026-11-01T09:46:54Z), not each individual fetch time.
- **PlanformDB:** counts come from the 744 KB database I downloaded (282 experiments with a "Double head…" outcome, 45 involving gap-junction blockers). I did not check whether it records untreated re-cutting of drug-induced lineages, so the three persistence claims are marked `gap`.
- **Models:** for the model claims (`tame-21`, `boundary-26`) I did not verify that any published model shows multistability.

_Tools used: Read ×3, Shell ×66, UpdateCurrentStep ×2, Write ×7_
