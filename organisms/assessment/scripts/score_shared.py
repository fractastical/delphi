#!/usr/bin/env python3
"""Build records/shared/batch-01.json from recheck_shared_results.json + sources/*.json.

Source-authority, independence and authenticity are inherited from the source file unless
the per-record JUDGMENTS table overrides them (wrong DOI, untraceable ids, ...). Integrity and
completeness are per-record judgments informed by the recheck results; the script fills the
`checks` block from the recheck output, computes the weighted overall score and the verdict
from rubric.json, and refuses to write a record whose verdict is inconsistent with its scores
or whose integrity exceeds what the recheck supports.

Usage: python3 score_shared.py [--results PATH] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSESS = HERE.parent
RUBRIC = json.load(open(ASSESS / "rubric.json"))
WEIGHTS = {d["id"]: d["weight"] for d in RUBRIC["dimensions"]}

# --------------------------------------------------------------------------- per-record judgments
# source: sources/<id>.json; i = integrity; c = completeness; a = authenticity override (else
# inherited); conf = confidence; obs = obstacles; why = rationale.
J = {}


def j(ids, source, i, c, conf, why, a=None, obs=(), sa=None, ind=None):
    for x in ([ids] if isinstance(ids, str) else ids):
        J[x] = {"source": source, "i": i, "c": c, "a": a, "sa": sa, "ind": ind, "conf": conf,
                "obs": list(obs), "why": why}


ESA_403 = "Ecological Archives directory (identifier) answers HTTP 403 to scripts; the data file itself downloads."
NEOGALE = "Neogale vison is present in the file under its older name Neovison vison, so the recorded 1 row is not found under the current binomial."

j("amniote-life-history-database-2015", "amniote-life-history-database", 0.8, 0.8, 0.85,
  "CSV re-downloaded from esapubs matches the recorded SHA-256 and 21,322 rows; 59 of 59 per-taxon counts reproduced. "
  "The record's doi and is_referenced_by (10.1890/15-0846.1) are not registered (handle API code 100); the data paper is "
  "10.1890/15-0846R.1. Identifier directory is 403 to scripts. Licence text varies by slice and is not stated at the source.",
  a=0.6, obs=[ESA_403, "DOI 10.1890/15-0846.1 does not exist; correct DOI 10.1890/15-0846R.1."])
j("amniote-life-history-database-2015-08", "amniote-life-history-database", 0.85, 0.85, 0.9,
  "Checksum and row count (21,322) reproduced; 87 of 88 per-taxon counts match, the exception being a nomenclatural synonym. "
  "DOI 10.1890/15-0846R.1 is registered. Identifier directory blocked (403); licence recorded as 'not stated', which is accurate.",
  obs=[ESA_403, NEOGALE])
j("amniote-life-history-database-aug-2015", "amniote-life-history-database", 0.8, 0.85, 0.85,
  "Both distributions (esapubs CSV and figshare ECOL_96_269.zip, which contains the identical CSV) match their recorded SHA-256; "
  "21,322 rows and 40 of 40 per-taxon counts reproduced. The merged record's doi/is_referenced_by 10.1890/15-0846.1 is unregistered "
  "(the ch07-08 slice); the other four slices cite the correct 10.1890/15-0846R.1.",
  a=0.6, obs=[ESA_403, "DOI 10.1890/15-0846.1 does not exist; correct DOI 10.1890/15-0846R.1."])
j("amniote-life-history-db-2015", "amniote-life-history-database", 1.0, 0.85, 0.9,
  "Identifier is the registered DOI 10.1890/15-0846R.1; checksum matches; 21,322 rows and 67 of 67 per-taxon counts reproduced. "
  "Licence honestly recorded as not stated in the archive.")
j("amniote-life-history-db-2015-08", "amniote-life-history-database", 1.0, 0.85, 0.9,
  "Identifier DOI resolves; checksum matches; 21,322 rows, 36 columns and 71 of 71 per-taxon counts reproduced. The licence "
  "'CC0 1.0 (as stated in the data paper metadata)' is misattributed: CC0 is the label of the Wiley figshare deposit, the ESA "
  "archive states no licence.",
  obs=["Licence attribution: CC0 belongs to figshare article 3563457, not to the data paper metadata."])

j("anage-build-15", "anage", 1.0, 0.85, 0.9,
  "dataset.zip matches the recorded SHA-256; anage_data.txt has 4,645 rows (one slice recorded 4,646, within tolerance) while "
  "release.html states 4,671 entries, a discrepancy the records themselves note. 144 of 145 per-taxon counts reproduced (Neogale vison "
  "synonym). Eleven of twenty slices cite 10.1093/nar/gkx1042, a real HAGR paper but not the citation release.html requests (gks1155).",
  a=0.9, obs=[NEOGALE, "Site states 4,671 entries; file has 4,645 rows.", "Unversioned download URL; checksum will change at build 16."])
j("anage-build-15-2026-10-31", "anage", 1.0, 0.85, 0.9,
  "Same build-15 zip (checksum matches), 4,645 rows, 38 of 38 per-taxon counts reproduced, DOI gks1155 is the requested citation. "
  "Completeness deduction only for the 4,645 vs 4,671 entry-count discrepancy inherited from the source.",
  obs=["Site states 4,671 entries; file has 4,645 rows.", "Unversioned download URL; checksum will change at build 16."])

AV = "avonet"
j("avonet-2022", AV, 0.95, 0.9, 0.9,
  "The xlsx (figshare file 34480856) matches the recorded SHA-256 and figshare's md5; 11,009 AVONET1_BirdLife rows and 8 of 8 per-taxon "
  "counts reproduced. The second distribution (figshare API JSON) carries no checksum. One slice dates the record 2022-02 (paper) rather "
  "than 2022-12-05 (figshare v7).",
  obs=["figshare API metadata distribution has no recorded checksum."])
j("avonet-2022-figshare-v7", AV, 0.95, 0.9, 0.9,
  "Checksum of the xlsx matches; 11,009 rows and 28 of 28 per-taxon counts reproduced. The thompson ch01-02 slice recorded the same file "
  "without a checksum and with an empty counts list; the merged record inherits the complete metadata from the other slices.",
  obs=["One slice's distribution has no recorded checksum."])
j("avonet-2022-v7", AV, 1.0, 0.9, 0.9,
  "Checksum matches; 11,009 rows; 32 of 33 per-taxon counts reproduced. Corvus monedula is present in the BirdLife sheet as "
  "Coloeus monedula, which the vendor matched by synonym.",
  obs=["Corvus monedula appears as Coloeus monedula in the AVONET1_BirdLife sheet."])
j("avonet-figshare-16586228-v7", AV, 1.0, 0.85, 0.9,
  "Checksum matches; 11,009 rows and 37 columns reproduced. The ch07-08 slice counted shared strings in the workbook rather than rows, "
  "so its presence claims for Anser cygnoides and Corvus cornix are not row counts and could not be compared; the 2 countable taxa match.",
  obs=["ch07-08 slice recorded presence via xl/sharedStrings.xml rather than species rows."])
j("avonet-figshare-v7-2022", AV, 1.0, 0.85, 0.9,
  "Checksum matches; 11,009 AVONET1_BirdLife rows reproduced. The record stores only presence for its four species, no per-taxon counts "
  "to compare.")
j("avonet-v7", AV, 1.0, 0.95, 0.95,
  "Checksum matches; 11,009 rows and 47 of 47 per-taxon counts reproduced; version, licence (CC BY 4.0) and issued date (2022-12-05) "
  "agree with the figshare API.")

j("eltontraits-1-0", "eltontraits", 0.85, 0.7, 0.85,
  "All five distributions (esapubs and figshare copies of BirdFuncDat.txt and MamFuncDat.txt) match their SHA-256. The merged "
  "n_bird_species 10,011 is within tolerance of the true 9,993 species rows, but the ch03 slice's 10,205 and the ch06-10 n_rows 15,395 "
  "are line-count artefacts; 96 of 100 per-taxon counts reproduced (Aves 10,011 vs 9,993; Cetacea 84 not derivable, no order column; "
  "Neogale vison synonym).",
  obs=["Bird row counts in several slices are line counts (10,205/10,011) rather than species rows (9,993).",
       "MamFuncDat.txt has no order column; Cetacea count cannot be re-derived."])
j("eltontraits-1-0-2014", "eltontraits", 0.6, 0.55, 0.85,
  "All four distributions match their SHA-256, but the merged counts are wrong: n_bird_species 10,203 (and 10,205 in ch11-12) versus "
  "9,993 species rows in the file and in the data paper (2.1% off, beyond tolerance); n_mammal_species 5,403 in one slice versus 5,400. "
  "The ch11-14 slice got it right (9,993 + 5,400 = 15,393). The merged licence 'CC BY 4.0 (figshare deposit)' is wrong: figshare "
  "article 3559887 is CC0. 39 of 39 per-taxon counts reproduced.",
  obs=["Recorded bird species count 10,203 is a line count; the file has 9,993 species rows.",
       "Licence should read CC0 (figshare 3559887) / not stated (esapubs)."])

FBW = "fishbase"
FB_LIC = "Licence recorded as CC BY-NC 3.0; the FishBase footer links CC BY-NC 4.0."
FB_HTML = "FishBase summary pages are generated dynamically; byte checksums do not reproduce although the content (title, max length) is unchanged."
j("fishbase-2026-10", FBW, 0.5, 0.6, 0.8,
  "All ten species summary pages still resolve (HTTP 200) with the same titles and max-length values, but none of the ten recorded page "
  "checksums reproduces (dynamic HTML). is_referenced_by (…/manual/English/FishBaseThe_Database.htm) returns 404. Version is 'accessed "
  "2026-10-31' rather than the footer's '(06/2026)'; licence should be CC BY-NC 4.0.",
  a=0.8, obs=[FB_HTML, FB_LIC, "is_referenced_by URL returns HTTP 404."])
j("fishbase-length-weight-2026", FBW, 0.5, 0.35, 0.8,
  "The only distribution is the manual page for the LENGTH-WEIGHT table, which resolves, but no checksum, version, issued date or count "
  "was recorded and no data rows are vendored, so nothing beyond the URL could be verified.",
  a=0.85, obs=["No checksum, version, date or counts recorded; documentation pointer only.", FB_LIC])
for sp, rec_n, obs_n, integ in (("melanogrammus-aeglefinus", 43, 51, 0.5), ("mustelus-canis", 8, 8, 0.65),
                                ("pleuronectes-platessa", 14, 26, 0.5), ("salmo-trutta", 55, 57, 0.6)):
    name = sp.replace("-", " ").capitalize()
    drift = (f"PopGrowth study rows: recorded {rec_n}, re-parsed {obs_n}"
             + (" (within tolerance)" if abs(rec_n - obs_n) <= 5 else " (beyond tolerance; live table and/or different row heuristic)") + ".")
    j(f"fishbase-popgrowth-{sp}-2026-10-31", FBW, integ, 0.7, 0.75,
      f"The PopGrowthList page for {name} matches its recorded SHA-256 byte-for-byte; the species summary page does not (dynamic HTML). "
      f"{drift} is_referenced_by https://www.fishbase.org answers 403 to scripts (bot block, not a dead link). Licence should be CC BY-NC 4.0.",
      a=0.85, obs=[drift, FB_HTML, FB_LIC])
j("fishbase-scyliorhinus-canicula-2026-10-31", FBW, 0.5, 0.6, 0.8,
  "The species page resolves with the same title and max length (100.0 cm TL) but its recorded checksum does not reproduce (dynamic HTML). "
  "Only one page and no table counts were vendored; version is an access date.",
  a=0.85, obs=[FB_HTML, FB_LIC])

j("fishbase-v25-04", "fishbase-hf-parquet", 1.0, 0.9, 0.9,
  "species.parquet and families.parquet (Hugging Face cboettig/fishbase, data/fb/v25.04) match their SHA-256; 36,132 species and 664 "
  "family rows and 10 of 10 per-taxon counts reproduced. One slice records licence null; the HF card says cc-by-nc-4.0. The thompson "
  "slice's is_referenced_by manual URL returns 404 but the merged record keeps the HF URL.",
  obs=["Identifier is the FishBase website; the checksummed files are the Hugging Face parquet snapshot."])
j("fishbase-v25-04-species", "fishbase-hf-parquet", 1.0, 0.9, 0.9,
  "Both parquet files match their SHA-256; 36,132 species rows and 19 of 19 per-taxon counts reproduced; licence CC BY-NC 4.0 agrees "
  "with the HF dataset card.",
  obs=["Identifier is the FishBase website; the checksummed files are the Hugging Face parquet snapshot."])

j("iucn-red-list-taxon-ids-2026-10-31", "iucn-red-list", 0.35, 0.35, 0.5,
  "Every IUCN URL (homepage, 24 taxonredirect links) answered HTTP 403, so no identifier, id or count could be verified; the vendor "
  "also did not fetch them and took the ids from Wikidata property P627, so the ids trace to Wikidata rather than to IUCN. No "
  "checksums, no assessment version, licence by reference to terms that could not be read.",
  a=0.6, obs=["All IUCN endpoints return HTTP 403 to non-browser clients; nothing could be re-checked.",
              "Ids originate from Wikidata P627, not from an IUCN query.", "Assessment version not retrieved."])

MS = "morphosource"
MS_RL = "MorphoSource totals are live and the API rate-limits (429); re-queries were throttled to one request per 2 s."
j("morphosource-media-2026-10-31", MS, 1.0, 0.85, 0.9,
  "All 29 API responses re-downloaded byte-identical to their recorded SHA-256 and all 29 per-taxon media totals matched exactly. "
  "Licence is per-media (recorded as such) and the version is an access date.",
  obs=[MS_RL])
j("morphosource-media-ch12-epilogue-2026-10-31", MS, 0.95, 0.85, 0.85,
  "87 of 89 'reduced response' checksums reproduced using the vendor's documented reduction (response.pages + media_type/modality/"
  "publication_status facets, JSON sorted keys); the other two differ because a live count moved, yet all 89 per-taxon totals are within "
  "tolerance. The record's doi/is_referenced_by 10.1017/S1089332600002862 resolves to an unrelated 2014 article; the MorphoSource paper "
  "cited in bibliographic_citation is 10.1017/scs.2017.13.",
  a=0.6, obs=[MS_RL, "DOI 10.1017/S1089332600002862 is the wrong article; correct DOI 10.1017/scs.2017.13."])
j("morphosource-media-counts-2026-10-31", MS, 1.0, 0.85, 0.9,
  "All 28 API responses byte-identical to their recorded SHA-256; 28 of 28 per-taxon media counts matched.",
  obs=[MS_RL])
j("morphosource-physical-objects-2026-10-31", MS, 0.85, 0.85, 0.85,
  "All 13 responses byte-identical to their recorded SHA-256 at the time of caching, and 12 of 13 physical-object counts reproduced; "
  "'q=Pan troglodytes' rose from 7 to 24 (free-text search, live repository). DOI 10.1017/scs.2017.13 is correct.",
  obs=[MS_RL, "Pan troglodytes physical-object count drifted 7 -> 24 (free-text q= query)."])

OT = "open-tree-of-life"
j("open-tree-of-life-taxonomy-tnrs-2026-10-31", OT, 1.0, 0.9, 0.9,
  "The recorded POST body replayed against /v3/tnrs/match_names returned a byte-identical response (checksum match); 76 names queried, "
  "75 matched (Pachydermata unmatched) exactly as recorded; taxonomy/about reports ott3.7draft3.")
j("open-tree-of-life-tnrs-ott3-7-2026-10-31", OT, 0.5, 0.85, 0.8,
  "The distribution stores the placeholder '[<58 accepted names>]' instead of the JSON body, so the recorded checksum cannot be "
  "reproduced. Rebuilding the request from the record's 58 taxa reproduced the recorded 58 queried / 58 matched / 5 ambiguous, and "
  "taxonomy/about confirms ott3.7draft3, so the content is credible but not byte-verifiable.",
  obs=["Exact TNRS POST body not recorded; checksum not reproducible."])
j("opentree-tnrs-ch11-2026-10-31", OT, 1.0, 0.9, 0.9,
  "Recorded POST body replayed: byte-identical response; 194 queried / 178 matched reproduced, with the same 16 unmatched fossil and "
  "gastropod names.")
j("opentree-tnrs-ott3-7-2026-10-31", OT, 1.0, 0.85, 0.85,
  "Recorded POST body replayed: byte-identical response; 54 matched / 1 unmatched (Ungulata) reproduced. The record's doi field, "
  "10.1093/sysbio/syx068, resolves to an unrelated Systematic Biology paper; its is_referenced_by (10.3897/BDJ.5.e12581, Rees & Cranston "
  "2017) is the right reference.",
  a=0.6, obs=["doi field 10.1093/sysbio/syx068 is unrelated to Open Tree; the correct reference is 10.3897/BDJ.5.e12581."])

PT = "pantheria"
j("pantheria-1-0", PT, 1.0, 0.8, 0.9,
  "Identifier is the registered DOI 10.1890/08-1494.1; file checksum matches; 5,416 rows and 20 of 20 per-taxon counts reproduced. "
  "Licence recorded as null (the archive indeed states none).")
j("pantheria-1-0-wr05", PT, 0.85, 0.85, 0.9,
  "File checksum matches, 5,416 rows reproduced, 38 of 39 per-taxon counts match (Neogale vison synonym). Identifier directory is 403.",
  obs=[ESA_403, NEOGALE])
j("pantheria-1-0-wr05-2008", PT, 0.85, 0.9, 0.9,
  "File checksum matches; 5,416 rows, 55 columns and 21 of 21 per-taxon counts reproduced. Identifier directory is 403; licence text "
  "varies by slice but all variants correctly say no explicit licence.",
  obs=[ESA_403])
j("pantheria-1-0-wr05-aug2008", PT, 0.85, 0.8, 0.9,
  "File checksum matches; 5,416 rows and 42 of 43 per-taxon counts reproduced (Neogale vison synonym). Identifier directory is 403; "
  "merged licence is null.",
  obs=[ESA_403, NEOGALE])

j("timetree-5-pairwise-2026-10-31", "timetree", 1.0, 0.9, 0.9,
  "All five pairwise CSV responses re-downloaded byte-identical; precomputed ages (e.g. Rhea pennata vs Rhea americana 11.4406 Ma) and "
  "study counts reproduced exactly. Licence paraphrase 'Free for academic use' omits that /about forbids redistribution.",
  obs=["TimeTree terms: redistribution of data and its transformations not permitted; relevant for republication."])

WD = "wikidata"
j("wikidata-taxa-ch11-2026-10-31", WD, 1.0, 0.85, 0.85,
  "The SPARQL query re-ran byte-identical (checksum match) and returned the recorded 187 rows. is_referenced_by is the P225 property page, "
  "which is documentation rather than a citation.")
j("wikidata-taxon-items-2026-10-31", WD, 1.0, 0.9, 0.9,
  "All 112 wbgetentities responses byte-identical to their recorded SHA-256; 111 of 112 items carry a P225 equal to the project's accepted "
  "name (Q6495741 has 'Batomorphi' where the label says Batoidea).",
  obs=["Q6495741 P225 = Batomorphi, labelled Batoidea."])
j("wikidata-taxon-items-ch09-10-2026-10-31", WD, 0.95, 0.8, 0.85,
  "98 of 100 responses byte-identical (two items edited since vendoring); all 50 searched names still resolve to an item with P225, as "
  "recorded. The record has no is_referenced_by and counts entities over all search candidates.",
  obs=["Two entity responses changed through live edits."])

WR = "worms"
j("worms-aphia-records-2026-10-31", WR, 0.95, 0.9, 0.9,
  "168 of 168 recorded response checksums reproduced and all 186 queries re-ran with the recorded AphiaIDs, names and ranks; 18 "
  "distributions from the thompson ch08 slice carry no checksum.",
  obs=["18 AphiaRecordByAphiaID distributions recorded without a checksum."])
j("worms-aphia-records-ch06-11-2026-10-31", WR, 1.0, 0.9, 0.95,
  "124 of 124 responses byte-identical and every AphiaID/name/rank agrees with its description.")
j("worms-aphia-records-ch09-10-2026-10-31", WR, 0.95, 0.9, 0.9,
  "51 of 51 recorded checksums reproduced; the 10 unchecksummed distributions are name queries that WoRMS answers with HTTP 204 "
  "(name not held), as the slice documents.",
  obs=["10 name queries return 204 (not in WoRMS); nothing to checksum."])
j("worms-aphia-records-ch12-epilogue-2026-10-31", WR, 1.0, 0.9, 0.95,
  "72 of 72 responses byte-identical and every AphiaID/name/rank agrees with its description.")
j("worms-ch11-2026-10-31", WR, 0.8, 0.8, 0.85,
  "Only an example query was vendored, without a checksum, and the claimed 154 resolved taxa are not stored as AphiaIDs. Re-querying "
  "AphiaRecordsByName (marine_only=false) for all 154 taxa in the record returned at least one Aphia record for every name, reproducing "
  "the count.",
  obs=["No checksum recorded; AphiaIDs not vendored, only the count."])


# --------------------------------------------------------------------------- helpers

def overall(scores: dict) -> float:
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS), 4)


def verdict(scores: dict, identifier_exists: bool) -> str:
    o = overall(scores)
    integ, auth, comp = scores["integrity"], scores["authenticity"], scores["completeness"]
    if auth < 0.5 or not identifier_exists:
        return "reject"
    if o >= 0.8 and integ >= 0.7 and auth >= 0.8:
        return "reliable"
    if integ < 0.5 or comp < 0.4:
        return "needs-repair"
    if o >= 0.55 and auth >= 0.5:
        return "usable-with-caveats"
    return "needs-repair"


def pick_count(r: dict) -> dict | None:
    """One representative count comparison per record, with a `metric` naming what it is."""
    fc = r.get("file_count_rechecks") or []
    for pref in ("n_species", "n_rows", "n_species_avonet1_birdlife", "n_bird_species"):
        for e in fc:
            if e["property_id"] == pref and e.get("observed") is not None:
                return {"metric": f"{pref} (file rows)", **{k: e[k] for k in ("recorded", "observed", "relative_diff", "within_tolerance")}}
    api = r.get("api_rechecks") or {}
    if "count_rechecks" in api:
        for pref in ("n_names_matched", "n_taxa_matched", "n_names_queried"):
            if pref in api["count_rechecks"]:
                e = api["count_rechecks"][pref]
                return {"metric": f"{pref} (TNRS)", **{k: e.get(k) for k in ("recorded", "observed", "relative_diff", "within_tolerance")}}
    if "n_growth_studies" in api:
        e = api["n_growth_studies"]
        return {"metric": "n_growth_studies (PopGrowth rows)", **{k: e.get(k) for k in ("recorded", "observed", "relative_diff", "within_tolerance")}}
    if "taxa_resolution" in api:
        e = api["taxa_resolution"]
        return {"metric": "n_taxa_resolved (names with Aphia records)", **{k: e.get(k) for k in ("recorded", "observed", "relative_diff", "within_tolerance")}}
    if "sparql_rows" in api:
        e = api["sparql_rows"]
        return {"metric": "n_rows (SPARQL)", **{k: e.get(k) for k in ("recorded", "observed", "relative_diff", "within_tolerance")}}
    if "searched_names_resolved" in api:
        e = api["searched_names_resolved"]
        return {"metric": "n_taxa_resolved (searched names with P225)", **{k: e.get(k) for k in ("recorded", "observed", "relative_diff", "within_tolerance")}}
    if "p225_equals_accepted_name" in api:
        e = api["p225_equals_accepted_name"]
        n, ok = e["n_checked"], e["n_ok"]
        return {"metric": "entities whose P225 equals the label", "recorded": n, "observed": ok,
                "relative_diff": round((n - ok) / n, 6) if n else None, "within_tolerance": (n - ok) <= 5 or (n and (n - ok) / n <= 0.005)}
    if "n_compared" in api and "n_within_tolerance" in api:
        n, ok = api["n_compared"], api["n_within_tolerance"]
        return {"metric": "per-taxon API totals reproduced within tolerance", "recorded": n, "observed": ok,
                "relative_diff": round((n - ok) / n, 6) if n else None, "within_tolerance": n == ok}
    if "n_ok" in api:
        n, ok = api["n_queries_rerun"], api["n_ok"]
        return {"metric": "Aphia queries reproducing recorded id/name/rank", "recorded": n, "observed": ok,
                "relative_diff": round((n - ok) / n, 6) if n else None, "within_tolerance": n == ok}
    if "pairs" in api:
        n = len(api["pairs"])
        ok = sum(1 for p in api["pairs"] if p.get("age_check", {}).get("within_tolerance") and p.get("n_studies_check", {}).get("within_tolerance"))
        return {"metric": "pairwise ages and study counts reproduced", "recorded": n, "observed": ok,
                "relative_diff": round((n - ok) / n, 6) if n else None, "within_tolerance": n == ok}
    if "pages" in api:
        pages = api["pages"]
        n, ok = len(pages), sum(1 for p in pages if p.get("status") == 200)
        if n and r["dataset_id"].startswith("fishbase-2026") or n == 1 and "summary" in pages[0]["url"]:
            return {"metric": "species pages resolving (HTTP 200)", "recorded": n, "observed": ok,
                    "relative_diff": round((n - ok) / n, 6), "within_tolerance": n == ok}
    return None


def checksum_match(r: dict) -> bool | None:
    cs = r["checksum_summary"]
    if cs.get("n_with_recorded_sha256", 0) == 0:
        return None
    return cs["n_match"] == cs["n_with_recorded_sha256"]


def identifier_resolves(r: dict) -> bool:
    idr = r.get("identifier") or {}
    return bool(idr.get("resolves") or idr.get("registered"))


def taxon_resolution(r: dict) -> str | None:
    api = r.get("api_rechecks") or {}
    pages = api.get("pages") or []
    if r.get("n_taxa") == 1:
        for p in pages:
            if "summary" in p.get("url", "") and p.get("title"):
                return p["title"].split(",")[0]
    tr = r.get("taxa_rechecks") or {}
    if tr.get("n_compared"):
        return f"{tr['n_match']}/{tr['n_compared']} per-taxon row counts reproduced"
    if "n_ok" in api:
        return f"{api['n_ok']}/{api['n_queries_rerun']} Aphia records agree with their labels"
    if "n_within_tolerance" in api:
        return f"{api['n_within_tolerance']}/{api['n_compared']} per-taxon MorphoSource totals within tolerance"
    if "p225_equals_accepted_name" in api:
        e = api["p225_equals_accepted_name"]
        return f"{e['n_ok']}/{e['n_checked']} items' P225 equals the label"
    if "replay" in api:
        rp = api["replay"]
        return f"{rp.get('n_names_matched')}/{rp.get('n_names_queried')} names matched in OTT {api.get('taxonomy_about', {}).get('source')}"
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(HERE / "recheck_shared_results.json"))
    ap.add_argument("--out", default=str(ASSESS / "records" / "shared" / "batch-01.json"))
    args = ap.parse_args()
    results = json.load(open(args.results))
    sources = {p.stem: json.load(open(p)) for p in (ASSESS / "sources").glob("*.json")}

    out = []
    for r in results:
        did = r["dataset_id"]
        jd = J[did]
        src = sources[jd["source"]]
        scores = {
            "source-authority": jd["sa"] if jd["sa"] is not None else src["scores"]["source-authority"],
            "integrity": jd["i"],
            "completeness": jd["c"],
            "independence": jd["ind"] if jd["ind"] is not None else src["scores"]["independence"],
            "authenticity": jd["a"] if jd["a"] is not None else src["scores"]["authenticity"],
        }
        scores = {k: round(v, 2) for k, v in scores.items()}
        cs = r["checksum_summary"]
        cm = checksum_match(r)
        idr = identifier_resolves(r)
        # guard rails: the judgments may not be rosier than the script's observations
        blocked = cs.get("n_blocked", 0) or cs.get("n_not_reproducible", 0)
        if (blocked and cs.get("n_match", 0) == 0) and scores["integrity"] > 0.5:
            raise SystemExit(f"{did}: integrity {scores['integrity']} > 0.5 but checks were blocked/not reproducible")
        if cm is False and cs.get("n_mismatch", 0) and scores["integrity"] > 0.5:
            raise SystemExit(f"{did}: non-live checksum mismatch but integrity > 0.5")
        if not idr and scores["integrity"] > 0.85:
            raise SystemExit(f"{did}: identifier does not resolve but integrity > 0.85")
        # identifier "exists" (for reject rule) = resolves, or is blocked by 403 rather than 404/unregistered
        id_info = r.get("identifier") or {}
        identifier_exists = idr or id_info.get("status") in (401, 403, 429)
        v = verdict(scores, identifier_exists)
        notes = []
        if cs.get("n_mismatch_live"):
            notes.append(f"{cs['n_mismatch_live']} live-response checksum(s) differ")
        if cs.get("n_no_checksum"):
            notes.append(f"{cs['n_no_checksum']} distribution(s) without recorded checksum")
        if cs.get("n_blocked"):
            notes.append(f"{cs['n_blocked']} download(s) blocked (401/403/429)")
        if cs.get("n_not_reproducible"):
            notes.append(f"{cs['n_not_reproducible']} request(s) not reproducible (POST body not recorded)")
        doi = r.get("doi") or {}
        if doi and doi.get("registered") is False:
            notes.append(f"doi {doi['doi']} not registered")
        ref = r.get("is_referenced_by") or {}
        if ref and ref.get("resolves") is False:
            notes.append(f"is_referenced_by {ref.get('url')} -> HTTP {ref.get('status')}")
        out.append({
            "dataset_id": did,
            "source_id": jd["source"],
            "scores": scores,
            "verdict": v,
            "confidence": jd["conf"],
            "checks": {
                "checked_at": r["checked_at"],
                "identifier_resolves": idr,
                "checksum_match": cm,
                "checksums": {k: cs.get(k, 0) for k in ("n_distributions", "n_with_recorded_sha256", "n_match", "n_mismatch",
                                                         "n_mismatch_live", "n_blocked", "n_not_reproducible", "n_no_checksum")},
                "count_recheck": pick_count(r),
                "taxon_key_resolves_to": taxon_resolution(r),
                "notes": notes,
            },
            "obstacles": jd["obs"],
            "rationale": jd["why"],
        })
    missing = set(J) - {o["dataset_id"] for o in out}
    if missing:
        raise SystemExit(f"judgments without results: {sorted(missing)}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(out, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    from collections import Counter
    print(f"wrote {args.out}: {len(out)} records, {Path(args.out).stat().st_size} bytes")
    print(Counter(o["verdict"] for o in out))
    for o in out:
        print(f"  {o['verdict']:20s} {overall(o['scores']):.3f} {o['dataset_id']}")


if __name__ == "__main__":
    main()
