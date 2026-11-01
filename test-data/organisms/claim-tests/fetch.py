#!/usr/bin/env python3
"""Build an organism slice for the species used by claim data tests.

    uv run --with pyarrow test-data/organisms/claim-tests/fetch.py lean-tested

Reads <slice>/species.json and, for every species, queries the public sources behind the
coverage axes in ../coverage.mjs: GBIF backbone and occurrences, Wikidata, NCBI Taxonomy and
Datasets (genome), WoRMS, OBIS, BOLD (barcodes), Paleobiology Database, Open Tree of Life,
IUCN status via GBIF, MorphoSource, DANDI (electrophysiology), FishBase / SeaLifeBase and AnAge.
Writes taxa/, datasets/, mentions.json, REPORT.md and PROFILES.md in the slice directory
following ../README.md, plus vendored per-species extracts under files/.

Responses are cached in ~/.cache/delphisci/organisms-claim-tests; --refresh re-queries.
Records only datasets that answered with data: a source with zero hits for a species is listed
in REPORT.md as a gap, never written as a dataset.
"""
import csv, datetime as dt, hashlib, io, json, os, re, sys, time, urllib.parse, urllib.request, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CACHE = os.path.expanduser("~/.cache/delphisci/organisms-claim-tests")
UA = "delphisci-organisms/0.2 (https://github.com/fractastical/delphi)"
TODAY = dt.date.today().isoformat()
REFRESH = "--refresh" in sys.argv
FB_VERSION = "v25.04"
VENDORED_BY = {"kind": "local-agent", "model": "claude-opus-5.5", "run": "cursor local session", "date": TODAY}


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def get(url, data=None, headers=None, timeout=90):
    """GET (or POST when data is given) with an on-disk cache. Returns body bytes and provenance."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha256((url + "\n" + (data or "")).encode()).hexdigest()
    body_path, meta_path = os.path.join(CACHE, key), os.path.join(CACHE, key + ".json")
    if not REFRESH and os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        meta["body"] = open(body_path, "rb").read()
        return meta
    h = {"User-Agent": UA, "Accept": "application/json"}
    h.update(headers or {})
    last = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, data=data.encode() if data else None, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body, status = r.read(), r.status
            break
        except urllib.error.HTTPError as e:
            body, status = e.read(), e.code
            if e.code < 500 and e.code != 429:
                break
            last = e
        except Exception as e:  # network errors: retry with backoff
            last, body, status = e, None, None
        time.sleep(2 ** attempt)
    if body is None:
        raise RuntimeError(f"{url}: {last}")
    meta = {"url": url, "status": status, "retrieved_at": now(), "byte_size": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}
    open(body_path, "wb").write(body)
    json.dump(meta, open(meta_path, "w"))
    meta["body"] = body
    return meta


def get_json(url, data=None, headers=None):
    r = get(url, data, headers)
    try:
        r["json"] = json.loads(r["body"])
    except Exception:
        r["json"] = None
    return r


def dist(r, media_type="application/json", **extra):
    d = {"download_url": r["url"], "media_type": media_type, "byte_size": r["byte_size"], "sha256": r["sha256"],
         "retrieved_at": r["retrieved_at"], "inspected": True,
         "note": "sha256 of the response body as retrieved"}
    d.update(extra)
    return d


def q(s):
    return urllib.parse.quote(s)


# ---------------------------------------------------------------- per-species sources

def gbif_match(name):
    r = get_json(f"https://api.gbif.org/v1/species/match?strict=true&name={q(name)}")
    return r, r["json"] or {}


def gbif_occurrences(key):
    r = get_json(f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&limit=0")
    rc = get_json(f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&hasCoordinate=true&hasGeospatialIssue=false&limit=0")
    return r, rc


def gbif_iucn(key):
    try:
        r = get_json(f"https://api.gbif.org/v1/species/{key}/iucnRedListCategory")
    except RuntimeError:
        return None
    return r if r["status"] == 200 and r["json"] and r["json"].get("category") else None


def wikidata(gbif_keys):
    vals = " ".join(f'"{k}"' for k in gbif_keys)
    query = ("SELECT ?item ?gbif ?ncbi ?itis ?worms ?iucnLabel WHERE { VALUES ?gbif { %s } ?item wdt:P846 ?gbif. "
             "OPTIONAL{?item wdt:P685 ?ncbi} OPTIONAL{?item wdt:P815 ?itis} OPTIONAL{?item wdt:P850 ?worms} "
             "OPTIONAL{?item wdt:P141 ?iucn} SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } }" % vals)
    r = get_json("https://query.wikidata.org/sparql?format=json&query=" + q(query),
                 headers={"Accept": "application/sparql-results+json"})
    out = {}
    for b in (r["json"] or {}).get("results", {}).get("bindings", []):
        g = b["gbif"]["value"]
        qid = b["item"]["value"].rsplit("/", 1)[1]
        cur = out.get(g)
        # Several items can carry the same GBIF id (e.g. a breed); keep the lowest QID.
        if cur and int(cur["qid"][1:]) < int(qid[1:]):
            continue
        out[g] = {"qid": qid, **{k: b[k]["value"] for k in ("ncbi", "itis", "worms", "iucnLabel") if k in b}}
    return r, out


def ncbi_taxonomy(name):
    r = get_json(f"https://api.ncbi.nlm.nih.gov/datasets/v2/taxonomy/taxon/{q(name)}/dataset_report")
    time.sleep(0.25)
    reps = (r["json"] or {}).get("reports") or []
    t = reps[0].get("taxonomy", {}) if reps else {}
    return r, t


LEVELS = {"Complete Genome": 4, "Chromosome": 3, "Scaffold": 2, "Contig": 1}


def ncbi_genome(taxid):
    r = get_json(f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report?filters.reference_only=true&page_size=1")
    time.sleep(0.25)
    reps = (r["json"] or {}).get("reports") or []
    if not reps:
        r = get_json(f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report?page_size=50")
        time.sleep(0.25)
        reps = (r["json"] or {}).get("reports") or []
        reps = [x for x in reps if x.get("organism", {}).get("tax_id") == taxid] or reps
        reps.sort(key=lambda x: (LEVELS.get(x.get("assembly_info", {}).get("assembly_level"), 0),
                                 x.get("assembly_stats", {}).get("contig_n50", 0)), reverse=True)
    return r, (reps[0] if reps else None)


def worms(name):
    r = get_json(f"https://www.marinespecies.org/rest/AphiaRecordsByName/{q(name)}?like=false&marine_only=false")
    recs = r["json"] if isinstance(r["json"], list) else []
    acc = [x for x in recs if x.get("status") == "accepted"] or recs
    return r, (acc[0] if acc else None)


def obis(aphia):
    return get_json(f"https://api.obis.org/v3/occurrence?taxonid={aphia}&size=0")


def bold(name):
    url = f"https://portal.boldsystems.org/api/summary?query=tax:species:{q(name)}&fields=specimens,bin_uri,marker_code,country/ocean"
    return get_json(url)


def pbdb(name):
    r = get_json(f"https://paleobiodb.org/data1.2/occs/list.json?base_name={q(name)}&rowcount&limit=0")
    return r, (r["json"] or {}).get("records_found", 0)


def morphosource(name):
    m = get_json(f"https://www.morphosource.org/api/media?q={q(name)}&per_page=1")
    p = get_json(f"https://www.morphosource.org/api/physical-objects?q={q(name)}&per_page=1")
    n = lambda r: ((r["json"] or {}).get("response", {}).get("pages", {}) or {}).get("total_count", 0)
    return m, n(m), p, n(p)


def dandi(name, taxid):
    """Dandisets whose asset summary lists this NCBI taxon and an electrophysiological approach."""
    hits, url = [], f"https://api.dandiarchive.org/api/dandisets/?search={q(name)}&page_size=100&empty=false"
    queries = []
    while url:
        r = get_json(url)
        queries.append(r)
        j = r["json"] or {}
        for d in j.get("results", []):
            ver = (d.get("most_recent_published_version") or d.get("draft_version") or {}).get("version", "draft")
            info = get_json(f"https://api.dandiarchive.org/api/dandisets/{d['identifier']}/versions/{ver}/info/")
            md = (info["json"] or {}).get("metadata", {})
            summ = md.get("assetsSummary", {}) or {}
            sp = [s.get("identifier", "") for s in summ.get("species", []) or []]
            approach = [a.get("name", "") for a in summ.get("approach", []) or []]
            if not any(s.endswith(f"NCBITaxon_{taxid}") for s in sp):
                continue
            if not any("electrophysiolog" in a.lower() for a in approach):
                continue
            hits.append({"identifier": d["identifier"], "version": ver, "name": md.get("name"), "info": info,
                         "approach": approach, "license": md.get("license"), "doi": md.get("doi"),
                         "citation": md.get("citation"), "techniques": [t.get("name") for t in summ.get("measurementTechnique", []) or []],
                         "n_files": summ.get("numberOfFiles"), "n_bytes": summ.get("numberOfBytes"),
                         "n_subjects": summ.get("numberOfSubjects"), "date": md.get("datePublished") or md.get("dateCreated")})
        url = j.get("next")
    return queries, hits


def opentree(names):
    r = get_json("https://api.opentreeoflife.org/v3/tnrs/match_names", data=json.dumps({"names": names, "do_approximate_matching": False}),
                 headers={"Content-Type": "application/json"})
    ott = {}
    for res in (r["json"] or {}).get("results", []):
        ms = [m for m in res.get("matches", []) if not m.get("is_synonym")] or res.get("matches", [])
        if ms:
            ott[res["name"]] = ms[0]["taxon"]["ott_id"]
    ids = sorted(set(ott.values()))
    tree, dropped = None, []
    for _ in range(4):
        t = get_json("https://api.opentreeoflife.org/v3/tree_of_life/induced_subtree",
                     data=json.dumps({"ott_ids": ids, "label_format": "name_and_id"}), headers={"Content-Type": "application/json"})
        if t["status"] == 200 and t["json"] and t["json"].get("newick"):
            tree = t
            break
        bad = [int(x) for x in re.findall(r"ott(\d+)", json.dumps(t["json"]))]
        bad = [b for b in bad if b in ids]
        if not bad:
            break
        dropped += bad
        ids = [i for i in ids if i not in bad]
    return r, ott, tree, dropped


# ---------------------------------------------------------------- FishBase / SeaLifeBase / AnAge

FB_TABLES = {
    "fb": ["species", "estimate", "poplw", "popgrowth", "popchar", "maturity", "fecundity", "spawning", "morphmet",
           "morphdat", "swimming", "speed", "brains", "oxygen", "diet", "ecology", "stocks"],
    "slb": ["species", "estimate", "poplw", "popgrowth", "popchar"],
}


TETRAPODS = {"Mammalia", "Aves", "Reptilia", "Amphibia", "Squamata", "Testudines", "Crocodylia"}


def lifebase_db(s, taxon):
    """FishBase for non-tetrapod chordates (the GBIF backbone gives ray-finned fish no class),
    SeaLifeBase for other species with a WoRMS AphiaID, unless species.json says otherwise."""
    if "lifebase" in s:
        return s["lifebase"]
    lin = taxon["lineage"]
    if lin.get("phylum") == "Chordata":
        return None if lin.get("class") in TETRAPODS else "fb"
    return "slb" if taxon["identifiers"].get("worms_aphia_id") else None


def lifebase(db, species_names):
    import pyarrow.parquet as pq
    base = f"https://huggingface.co/datasets/cboettig/fishbase/resolve/main/data/{db}/{FB_VERSION}/parquet"
    files, out = {}, {n: {"tables": {}} for n in species_names}
    sp = get(f"{base}/species.parquet")
    files["species"] = sp
    tbl = pq.read_table(io.BytesIO(sp["body"])).to_pylist()
    codes = {}
    for row in tbl:
        n = f"{row.get('Genus')} {row.get('Species')}"
        if n in out:
            codes[row["SpecCode"]] = n
    for name in FB_TABLES[db]:
        r = files.get(name) or get(f"{base}/{name}.parquet")
        files[name] = r
        try:
            rows = pq.read_table(io.BytesIO(r["body"])).to_pylist()
        except Exception:
            continue
        for row in rows:
            n = codes.get(row.get("SpecCode", row.get("Speccode")))
            if n:
                clean = {k: v for k, v in row.items() if v not in (None, "", 0) or k in ("a", "b")}
                for k, v in clean.items():
                    if isinstance(v, (dt.date, dt.datetime)):
                        clean[k] = v.isoformat()
                    elif isinstance(v, bytes):
                        clean[k] = v.decode("utf-8", "replace")
                out[n]["tables"].setdefault(name, []).append(clean)
    for c, n in codes.items():
        out[n]["SpecCode"] = c
    return base, files, out


def anage():
    r = get("https://genomics.senescence.info/species/dataset.zip")
    z = zipfile.ZipFile(io.BytesIO(r["body"]))
    text = z.read("anage_data.txt").decode("latin-1")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    return r, {f"{x['Genus']} {x['Species']}": {k: v for k, v in x.items() if v} for x in rows}, len(rows)


# ---------------------------------------------------------------- mentions

ALIASES = {
    "Homo sapiens": ["Homo sapiens", "human"],
    "Apis mellifera": ["Western honey bee", "Western honey", "honeybee", "honey bee", "hive-bee"],
    "Apis cerana": ["Eastern and Western honey bee", "Eastern"],
    "Bos taurus": ["Bos taurus", "ox"],
    "Ovis aries": ["Ovis aries", "sheep"],
    "Giraffa camelopardalis": ["Giraffa", "giraffe"],
    "Drosophila melanogaster": ["Drosophila melanogaster", "Drosophila"],
}


def strings(o, keys=True):
    if isinstance(o, dict):
        for k, v in o.items():
            if keys:
                yield k
            yield from strings(v, keys)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v, keys)
    elif isinstance(o, str):
        yield o


def find_mention(name, claim, claims_by_id):
    path = (claims_by_id.get(claim, {}).get("data_test") or {}).get("path")
    sources = []
    if path and os.path.exists(os.path.join(REPO, path)):
        sources.append(json.load(open(os.path.join(REPO, path))))
    sources.append({"statement": claims_by_id.get(claim, {}).get("statement", ""), "quote": claims_by_id.get(claim, {}).get("quote", "")})
    for term in ALIASES.get(name, [name]):
        pat = re.compile(r"\b" + re.escape(term) + r"\b", re.I)
        for src in sources:
            for s in strings(src, keys=False):
                m = pat.search(s)
                if m:
                    a, b = max(0, m.start() - 90), min(len(s), m.end() + 90)
                    a = s.rfind(" ", 0, a) + 1 if a else 0
                    b = s.find(" ", b) if b < len(s) and s.find(" ", b) > 0 else len(s)
                    return m.group(0), s[a:b].strip()
            for s in strings(src):
                if pat.search(s) and len(s) >= 10:
                    return pat.search(s).group(0), s
    return None, None


# ---------------------------------------------------------------- main

def main():
    slice_name = next((a for a in sys.argv[1:] if not a.startswith("--")), None)
    if not slice_name:
        sys.exit("usage: fetch.py <slice> [--refresh]")
    sdir = os.path.join(HERE, slice_name)
    cfg = json.load(open(os.path.join(sdir, "species.json")))
    tag = f"{slice_name}-{TODAY}"
    claims_by_id = {c["id"]: c for c in json.load(open(os.path.join(REPO, "docs", "claims.json")))["claims"]}
    for d in ("taxa", "datasets", "files"):
        os.makedirs(os.path.join(sdir, d), exist_ok=True)
    for f in os.listdir(os.path.join(sdir, "datasets")):
        os.remove(os.path.join(sdir, "datasets", f))
    for f in os.listdir(os.path.join(sdir, "taxa")):
        os.remove(os.path.join(sdir, "taxa", f))

    datasets, taxa, mentions, gaps, profiles = {}, {}, [], {}, {}

    def add_ds(rec):
        rec.setdefault("vendored_by", VENDORED_BY)
        rec.setdefault("integrity", {"identifier_resolves": True, "checksum_verified": True, "checked_at": now()})
        if rec["id"] in datasets:
            datasets[rec["id"]]["taxa"] = sorted(set(datasets[rec["id"]]["taxa"] + rec["taxa"]))
            datasets[rec["id"]].setdefault("counts", []).extend(rec.get("counts", []))
        else:
            datasets[rec["id"]] = rec
        return rec["id"]

    def gap(slug, axis, why):
        gaps.setdefault(slug, []).append(f"{axis}: {why}")

    spp = cfg["species"]
    s_by_name = {s["name"]: s for s in spp}
    print(f"{len(spp)} species")

    # GBIF backbone
    gbif_rs, matched = [], {}
    for s in spp:
        r, m = gbif_match(s["name"])
        gbif_rs.append(r)
        if not m.get("usageKey") or m.get("matchType") == "NONE":
            print(f"  GBIF: no match for {s['name']}")
            continue
        matched[s["name"]] = m
    wd_r, wd = wikidata([str(m["usageKey"]) for m in matched.values()])

    for s in spp:
        name = s["name"]
        m = matched.get(name)
        if not m:
            continue
        accepted = s.get("accepted_name") or m.get("canonicalName") or name
        slug = slugify(accepted)
        print(f"- {name} ({slug})")
        w = dict(wd.get(str(m["usageKey"]), {}))
        if s.get("wikidata_qid"):
            w = {"qid": s["wikidata_qid"], **{k: v for k, v in w.items() if k == "iucnLabel"}}
        tx_r, tx = ncbi_taxonomy(name)
        taxid = tx.get("tax_id") or (int(w["ncbi"]) if w.get("ncbi") else None)
        wr, wrec = worms(name) if s.get("marine", True) else (None, None)
        aphia = (wrec or {}).get("AphiaID") or (int(w["worms"]) if w.get("worms") else None)
        prof = {"accepted_name": accepted, "claims": s["claims"], "identifiers": {}, "genome": None, "counts": {}, "traits": {}}
        ids = {"gbif_usage_key": m["usageKey"], "ncbi_taxid": taxid, "wikidata_qid": w.get("qid"),
               "itis_tsn": int(w["itis"]) if w.get("itis", "").isdigit() else None, "worms_aphia_id": aphia}
        prof["identifiers"] = dict(ids)
        lineage = {k: m.get(k) for k in ("kingdom", "phylum", "class", "order", "family", "genus") if m.get(k)}
        t = {"slug": slug, "accepted_name": accepted, "rank": m.get("rank", "").lower(), "vernacular": [],
             "names_as_written": [], "identifiers": ids, "lineage": lineage, "mentioned_in": s["claims"], "datasets": [],
             "notes": f"Used by the data test of {', '.join(s['claims'])}; GBIF match {m.get('matchType')} ({m.get('scientificName')})."}
        taxa[name] = t

        # taxonomy (shared records)
        t["datasets"].append(add_ds({"id": f"gbif-backbone-matches-{tag}", "label": f"GBIF Backbone Taxonomy name matches for slice {slice_name}",
            "identifier": "https://doi.org/10.15468/39omei", "doi": "10.15468/39omei", "license": "CC BY 4.0",
            "bibliographic_citation": "GBIF Secretariat. GBIF Backbone Taxonomy. Checklist dataset https://doi.org/10.15468/39omei accessed via GBIF.org.",
            "distributions": [dist(r) for r in gbif_rs if name.replace(" ", "%20") in r["url"]],
            "category": "taxonomy", "taxa": [slug], "role": "accepted name, rank, lineage and GBIF usage key for the listed taxa",
            "measurement_technique": "GBIF species/match API, strict matching"}))
        if w.get("qid"):
            t["datasets"].append(add_ds({"id": f"wikidata-taxon-items-{tag}", "label": f"Wikidata taxon items (by GBIF taxon ID, P846) for slice {slice_name}",
                "identifier": "https://www.wikidata.org/", "license": "CC0 1.0", "distributions": [dist(wd_r, "application/sparql-results+json")],
                "category": "taxonomy", "taxa": [slug], "role": "Wikidata QID, NCBI (P685), ITIS (P815) and WoRMS (P850) cross-references, IUCN status (P141)",
                "measurement_technique": "Wikidata Query Service SPARQL"}))
        if tx:
            cnt = {c["type"].replace("COUNT_TYPE_", "").lower(): c["count"] for c in tx.get("counts", [])}
            prof["counts"].update({f"ncbi_{k}": v for k, v in cnt.items() if k in ("assembly", "gene", "protein_coding")})
            t["datasets"].append(add_ds({"id": f"ncbi-taxonomy-{tag}", "label": f"NCBI Taxonomy records for slice {slice_name}",
                "identifier": "https://www.ncbi.nlm.nih.gov/taxonomy", "license": "Public domain (NCBI)",
                "bibliographic_citation": "Schoch CL, et al. (2020) NCBI Taxonomy: a comprehensive update on curation, resources and tools. Database 2020:baaa062.",
                "is_referenced_by": "https://doi.org/10.1093/database/baaa062",
                "distributions": [dist(tx_r)], "category": "taxonomy", "taxa": [slug],
                "counts": [{"property_id": f"n_assemblies:{slug}", "value": cnt.get("assembly", 0), "description": f"genome assemblies in NCBI for {name}"},
                           {"property_id": f"n_genes:{slug}", "value": cnt.get("gene", 0), "description": f"NCBI Gene records for {name}"}],
                "role": "NCBI taxid and counts of assemblies and annotated genes", "measurement_technique": "NCBI Datasets v2 taxonomy dataset_report"}))
        if wrec:
            t["datasets"].append(add_ds({"id": f"worms-aphia-records-{tag}", "label": f"World Register of Marine Species (WoRMS) records for slice {slice_name}",
                "identifier": "https://www.marinespecies.org/", "doi": "10.14284/170", "license": "CC BY 4.0",
                "bibliographic_citation": "WoRMS Editorial Board (2026). World Register of Marine Species. https://doi.org/10.14284/170",
                "distributions": [dist(wr)], "category": "taxonomy", "taxa": [slug], "role": "AphiaID and accepted marine name",
                "measurement_technique": "WoRMS REST AphiaRecordsByName"}))

        # genome
        if taxid:
            gr, rep = ncbi_genome(taxid)
            if rep:
                acc = rep["accession"]
                ai, st = rep.get("assembly_info", {}), rep.get("assembly_stats", {})
                busco = (rep.get("annotation_info") or {}).get("busco", {})
                counts = [{"property_id": "total_sequence_length_bp", "value": int(st["total_sequence_length"]), "description": "total assembled sequence length (bp)"}] if st.get("total_sequence_length") else []
                for k, label in (("contig_n50", "contig N50 (bp)"), ("scaffold_n50", "scaffold N50 (bp)"), ("total_number_of_chromosomes", "assembled chromosomes")):
                    if st.get(k):
                        counts.append({"property_id": k.replace("total_number_of_chromosomes", "number_of_chromosomes") + ("_bp" if "n50" in k else ""), "value": int(st[k]), "description": label})
                if busco.get("complete") is not None:
                    counts.append({"property_id": "busco_complete_fraction", "value": round(float(busco["complete"]), 4), "description": f"BUSCO complete ({busco.get('busco_lineage')}, {busco.get('busco_ver')})"})
                genes = ((rep.get("annotation_info") or {}).get("stats") or {}).get("gene_counts", {}).get("total")
                if genes:
                    counts.append({"property_id": "n_genes_annotated", "value": int(genes), "description": "genes in the assembly's annotation"})
                prof["genome"] = {"accession": acc, "level": ai.get("assembly_level"), "name": ai.get("assembly_name"),
                                  "released": ai.get("release_date"), **{c["property_id"]: c["value"] for c in counts}}
                t["datasets"].append(add_ds({"id": "ncbi-genome-" + slugify(acc), "label": f"NCBI {'reference ' if rep.get('source_database') else ''}genome assembly {acc} ({ai.get('assembly_name')}) for {name}",
                    "identifier": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/", "license": "NCBI data are in the public domain (US Government work); see https://www.ncbi.nlm.nih.gov/home/about/policies/",
                    "creators": [ai["submitter"]] if ai.get("submitter") else [], "issued": ai.get("release_date"), "version": ai.get("assembly_name"),
                    "distributions": [dist(gr)], "counts": counts, "category": "genome",
                    "measurement_technique": f"Genome assembly; level {ai.get('assembly_level')}; BioProject {(ai.get('bioproject_accession') or '')}; organism tax_id {taxid}.",
                    "taxa": [slug], "role": f"reference genome assembly for {name}"}))
            else:
                gap(slug, "genome", "no assembly in NCBI Datasets")
        else:
            gap(slug, "genome", "no NCBI taxid")

        # occurrences
        oc, occ = gbif_occurrences(m["usageKey"])
        n_occ, n_geo = (oc["json"] or {}).get("count", 0), (occ["json"] or {}).get("count", 0)
        prof["counts"]["gbif_occurrences"], prof["counts"]["gbif_georeferenced"] = n_occ, n_geo
        t["datasets"].append(add_ds({"id": f"gbif-occurrences-{slug}-{tag}", "label": f"GBIF occurrence records for {name} (count query)",
            "identifier": f"https://www.gbif.org/occurrence/search?taxon_key={m['usageKey']}", "license": "Per-record CC0 / CC BY / CC BY-NC (GBIF)",
            "distributions": [dist(oc), dist(occ)], "category": "occurrence", "taxa": [slug],
            "counts": [{"property_id": "n_occurrences", "value": n_occ, "description": "all GBIF occurrences for the taxon key"},
                       {"property_id": "n_occurrences_georeferenced", "value": n_geo, "description": "with coordinates and no geospatial issue"}],
            "role": f"occurrence records for {name}", "measurement_technique": "GBIF occurrence search API, limit=0 count"}))
        if aphia:
            ob = obis(aphia)
            n_obis = (ob["json"] or {}).get("total", 0)
            prof["counts"]["obis_occurrences"] = n_obis
            if n_obis:
                t["datasets"].append(add_ds({"id": f"obis-occurrences-{slug}-{tag}", "label": f"OBIS occurrence records for {name} (AphiaID {aphia})",
                    "identifier": f"https://obis.org/taxon/{aphia}", "license": "Per-dataset CC0 / CC BY / CC BY-NC (OBIS)",
                    "distributions": [dist(ob)], "category": "occurrence", "taxa": [slug],
                    "counts": [{"property_id": "n_occurrences", "value": n_obis, "description": "OBIS occurrences for the AphiaID"}],
                    "role": f"marine occurrence records for {name}", "measurement_technique": "OBIS API v3 occurrence count"}))

        # barcodes
        br = bold(name)
        bj = (br["json"] or {})
        n_spec = (bj.get("counts") or {}).get("specimens", 0) if isinstance(bj.get("counts"), dict) else 0
        bins = bj.get("bin_uri") or {}
        markers = bj.get("marker_code") or {}
        countries = bj.get("country/ocean") or {}
        prof["counts"].update({"bold_specimens": n_spec, "bold_bins": len(bins), "bold_coi5p": markers.get("COI-5P", 0)})
        if n_spec:
            t["datasets"].append(add_ds({"id": f"bold-barcodes-{slug}-{TODAY}", "label": f"BOLD Systems barcode records for {name} (summary query)",
                "identifier": f"https://portal.boldsystems.org/result?query={q(name)}[tax]", "license": "CC BY 4.0 (BOLD public data)",
                "bibliographic_citation": "Ratnasingham S, Hebert PDN (2007) BOLD: The Barcode of Life Data System. Mol Ecol Notes 7:355-364.",
                "is_referenced_by": "https://doi.org/10.1111/j.1471-8286.2007.01678.x",
                "distributions": [dist(br)], "category": "barcode", "taxa": [slug],
                "counts": [{"property_id": "n_specimens", "value": n_spec, "description": "public BOLD specimen records"},
                           {"property_id": "n_bins", "value": len(bins), "description": "Barcode Index Numbers (BINs) the specimens fall in"},
                           {"property_id": "n_coi5p", "value": markers.get("COI-5P", 0), "description": "records with a COI-5P barcode sequence"},
                           {"property_id": "n_countries_oceans", "value": len(countries), "description": "distinct countries/oceans of collection"}],
                "role": f"DNA barcodes (COI) for {name}", "measurement_technique": "BOLD portal API summary"}))
        else:
            gap(slug, "barcode", "no public BOLD records")

        # fossils
        pr, n_fos = pbdb(name)
        prof["counts"]["pbdb_occurrences"] = n_fos
        if n_fos:
            t["datasets"].append(add_ds({"id": f"pbdb-occurrences-{slug}-{tag}", "label": f"Paleobiology Database fossil occurrences for {name}",
                "identifier": f"https://paleobiodb.org/classic/checkTaxonInfo?taxon_name={q(name)}", "license": "CC BY 4.0",
                "distributions": [dist(pr)], "category": "fossil", "taxa": [slug],
                "counts": [{"property_id": "n_occurrences", "value": n_fos, "description": "PBDB occurrences for the name and its subtaxa"}],
                "role": f"fossil occurrences of {name}", "measurement_technique": "PBDB data1.2 occs/list rowcount"}))
        else:
            gap(slug, "fossil", "no PBDB occurrences at species level")

        # conservation
        iu = gbif_iucn(m["usageKey"])
        if iu and iu["json"]["category"] == "NOT_EVALUATED":
            prof["traits"]["iucn"] = "NOT_EVALUATED"
            iu = None
            w = {k: v for k, v in w.items() if k != "iucnLabel" or v != "not evaluated"}
        if iu:
            prof["traits"]["iucn"] = iu["json"]["category"]
            t["datasets"].append(add_ds({"id": f"iucn-red-list-via-gbif-{tag}", "label": f"IUCN Red List categories via the GBIF IUCN checklist for slice {slice_name}",
                "identifier": "https://doi.org/10.15468/0qnb58", "doi": "10.15468/0qnb58", "license": "IUCN Red List terms of use",
                "distributions": [dist(iu)], "category": "conservation", "taxa": [slug],
                "counts": [], "role": "IUCN Red List category for the listed taxa", "measurement_technique": "GBIF species/{key}/iucnRedListCategory"}))
        elif w.get("iucnLabel"):
            prof["traits"]["iucn"] = w["iucnLabel"]
            t["datasets"].append(add_ds({"id": f"iucn-status-via-wikidata-{tag}", "label": f"IUCN conservation status (Wikidata P141) for slice {slice_name}",
                "identifier": "https://www.wikidata.org/wiki/Property:P141", "license": "CC0 1.0", "distributions": [dist(wd_r, "application/sparql-results+json")],
                "category": "conservation", "taxa": [slug], "role": "IUCN status as recorded on Wikidata", "measurement_technique": "Wikidata SPARQL P141"}))
        else:
            gap(slug, "conservation", "no IUCN category via GBIF or Wikidata")

        # 3D morphology
        mr, n_media, por, n_po = morphosource(name)
        prof["counts"]["morphosource_media"], prof["counts"]["morphosource_objects"] = n_media, n_po
        if n_media or n_po:
            t["datasets"].append(add_ds({"id": f"morphosource-{slug}-{tag}", "label": f"MorphoSource media and physical objects matching {name}",
                "identifier": f"https://www.morphosource.org/catalog/media?q={q(name)}", "license": "Per-media licences (MorphoSource)",
                "distributions": [dist(mr), dist(por)], "category": "morphology3d", "taxa": [slug],
                "counts": [{"property_id": "n_media", "value": n_media, "description": "public media matching the name (keyword search)"},
                           {"property_id": "n_physical_objects", "value": n_po, "description": "physical objects matching the name (keyword search)"}],
                "role": f"3D scans (CT, surface) of {name} specimens", "measurement_technique": "MorphoSource API keyword search"}))
        else:
            gap(slug, "morphology3d", "no MorphoSource hits for the name")

        # electrophysiology
        if taxid:
            dq, hits = dandi(name, taxid)
            prof["counts"]["dandi_ephys_dandisets"] = len(hits)
            for h in hits:
                info = h["info"]
                did = f"dandi-{h['identifier']}-{slugify(h['version'])}"
                add_ds({"id": did, "label": f"DANDI:{h['identifier']} {h['name']}",
                    "identifier": f"https://dandiarchive.org/dandiset/{h['identifier']}/{h['version']}",
                    **({"doi": h["doi"].replace("https://doi.org/", "")} if h.get("doi") else {}),
                    "bibliographic_citation": h.get("citation"), "license": ", ".join(h.get("license") or []), "issued": (h.get("date") or "")[:10] or None,
                    "version": h["version"], "distributions": [dist(info)], "category": "bioelectric", "taxa": [slug],
                    "counts": [c for c in ({"property_id": "n_files", "value": h["n_files"], "description": "assets"} if h.get("n_files") else None,
                                           {"property_id": "n_subjects", "value": h["n_subjects"], "description": "subjects"} if h.get("n_subjects") else None) if c],
                    "measurement_technique": "; ".join([*h["approach"], *h["techniques"]]),
                    "role": f"electrophysiology recordings from {name} (DANDI asset summary lists NCBITaxon_{taxid})"})
                t["datasets"].append(did)
            if not hits:
                gap(slug, "bioelectric", "no DANDI dandiset with an electrophysiological approach for this taxon")
        profiles[slug] = prof

        # mentions
        for c in s["claims"]:
            written, quote = find_mention(name, c, claims_by_id)
            if not quote:
                written, quote = name, f"{name} — used by the data test of {c}"
            if written not in t["names_as_written"]:
                t["names_as_written"].append(written)
            mentions.append({"taxon_slug": slug, "name_as_written": written,
                             "source": {"claim_id": c, "file": (claims_by_id.get(c, {}).get("data_test") or {}).get("path")}, "quote": quote})

    # Open Tree phylogeny (one induced subtree for the slice)
    names = [n for n in taxa]
    tnrs, ott, tree, dropped = opentree(names)
    if tree:
        newick = tree["json"]["newick"]
        open(os.path.join(sdir, "files", "opentree-induced-subtree.tre"), "w").write(newick + "\n")
        in_tree = [taxa[n]["slug"] for n in names if ott.get(n) and ott[n] not in dropped]
        for n in names:
            if ott.get(n):
                profiles[taxa[n]["slug"]]["identifiers"]["ott_id"] = ott[n]
        did = add_ds({"id": f"opentree-induced-subtree-{tag}", "label": f"Open Tree of Life synthetic tree, induced subtree for slice {slice_name}",
            "identifier": "https://tree.opentreeoflife.org/", "license": "CC0 1.0",
            "bibliographic_citation": "Open Tree of Life (2026). Synthetic tree via the v3 tree_of_life/induced_subtree API.",
            "is_referenced_by": "https://doi.org/10.1073/pnas.1423041112",
            "distributions": [dist(tnrs), dist(tree, note="sha256 of the response body; newick vendored as files/opentree-induced-subtree.tre")],
            "category": "phylogeny", "taxa": in_tree,
            "counts": [{"property_id": "n_tips", "value": len(in_tree), "description": "taxa placed in the induced subtree"}],
            "role": "phylogenetic placement of the listed taxa in the Open Tree synthesis", "measurement_technique": "Open Tree TNRS match_names + induced_subtree"})
        for n in names:
            if taxa[n]["slug"] in in_tree:
                taxa[n]["datasets"].append(did)
    for n in names:
        if taxa[n]["slug"] not in (datasets.get(f"opentree-induced-subtree-{tag}", {}).get("taxa") or []):
            gap(taxa[n]["slug"], "phylogeny", "not placed in the Open Tree induced subtree")

    # FishBase / SeaLifeBase
    for db, label, doi_cite in (("fb", "FishBase", "Froese R, Pauly D (eds) (2025) FishBase. World Wide Web electronic publication, www.fishbase.org, version 04/2025."),
                                ("slb", "SeaLifeBase", "Palomares MLD, Pauly D (eds) (2025) SeaLifeBase. World Wide Web electronic publication, www.sealifebase.org, version 04/2025.")):
        names_db = [s["name"] for s in spp if s["name"] in taxa and lifebase_db(s, taxa[s["name"]]) == db]
        if not names_db:
            continue
        base, files, out = lifebase(db, names_db)
        os.makedirs(os.path.join(sdir, "files", "lifebase"), exist_ok=True)
        covered, counts = [], []
        for n in names_db:
            slug = taxa[n]["slug"]
            o = out[n]
            if not o.get("SpecCode"):
                gap(slug, "traits", f"not found in {label} {FB_VERSION}")
                continue
            covered.append(slug)
            o.update({"source": label, "version": FB_VERSION, "accepted_name": n})
            path = os.path.join(sdir, "files", "lifebase", f"{slug}.json")
            json.dump(o, open(path, "w"), indent=1, ensure_ascii=False, default=str)
            tabs = o["tables"]
            sp = (tabs.get("species") or [{}])[0]
            est = (tabs.get("estimate") or [{}])[0]
            bs = sorted(float(x["b"]) for x in tabs.get("poplw", []) if x.get("b") not in (None, 0))
            tr = profiles[slug]["traits"]
            tr.update({k: v for k, v in {"max_length_cm": sp.get("Length"), "common_length_cm": sp.get("CommonLength"),
                       "max_weight_g": sp.get("Weight"), "max_age_yr": sp.get("LongevityWild"), "habitat": sp.get("DemersPelag"),
                       "lw_bayes_a": est.get("a"), "lw_bayes_b": est.get("b"), "trophic_level": est.get("Troph"),
                       "lw_studies": len(bs), "lw_b_median": round(bs[len(bs) // 2], 3) if bs else None,
                       "growth_studies": len(tabs.get("popgrowth", [])), "maturity_studies": len(tabs.get("maturity", [])),
                       "fecundity_studies": len(tabs.get("fecundity", []))}.items() if v not in (None, "")})
            for tname, rows in tabs.items():
                counts.append({"property_id": f"n_rows:{tname}:{slug}", "value": len(rows), "description": f"{tname} rows for {n}"})
            taxa[n]["datasets"].append(f"{slugify(label)}-{FB_VERSION.replace('.', '-')}-{slice_name}")
        if covered:
            add_ds({"id": f"{slugify(label)}-{FB_VERSION.replace('.', '-')}-{slice_name}", "label": f"{label} {FB_VERSION} tables (rfishbase parquet snapshot), rows for slice {slice_name}",
                "identifier": "https://www.fishbase.se/" if db == "fb" else "https://www.sealifebase.se/", "license": "CC BY-NC 4.0",
                "bibliographic_citation": doi_cite, "version": FB_VERSION,
                "distributions": [dist(r, "application/vnd.apache.parquet") for r in files.values()],
                "category": "traits", "taxa": covered, "counts": counts,
                "measurement_technique": "Literature-compiled length-weight, growth, maturity, fecundity, morphometric, physiological and ecological records; per-species extracts vendored under files/lifebase/",
                "role": "life-history, length-weight and morphometric records for the listed taxa"})

    # AnAge
    an_names = [s["name"] for s in spp if s["name"] in taxa and s.get("anage", True)]
    if an_names:
        ar, rows, n_rows = anage()
        covered = []
        for n in an_names:
            row = rows.get(n)
            slug = taxa[n]["slug"]
            if not row:
                if taxa[n]["lineage"].get("class") in TETRAPODS or s_by_name[n].get("anage"):
                    gap(slug, "traits", "no AnAge row")
                continue
            covered.append(slug)
            profiles[slug]["traits"]["anage"] = {k: row[k] for k in row if k not in ("HAGRID", "Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species", "References")}
            taxa[n]["datasets"].append("anage-build-15")
        if covered:
            add_ds({"id": "anage-build-15", "label": "AnAge: The Animal Ageing and Longevity Database, build 15",
                "identifier": "https://genomics.senescence.info/species/", "doi": "10.1093/nar/gkx1042", "license": "CC BY 3.0", "issued": "2017-11", "version": "build 15",
                "bibliographic_citation": "Tacutu R, et al. (2018) Human Ageing Genomic Resources: new and updated databases. Nucleic Acids Res 46(D1):D1083-D1090.",
                "distributions": [dist(ar, "application/zip", files=["anage_data.txt"])], "category": "traits", "taxa": covered,
                "counts": [{"property_id": "n_species", "value": n_rows, "description": "rows in anage_data.txt"},
                           {"property_id": "n_rows_for_taxa", "value": len(covered), "description": "rows matching the taxa listed below"}],
                "measurement_technique": "Literature-compiled life-history traits (maximum longevity, body mass, maturity, metabolism).",
                "role": "maximum longevity, adult body mass, maturity and metabolic rate for the listed taxa"})

    # write
    for n, t in taxa.items():
        t["datasets"] = sorted(set(t["datasets"]))
        json.dump(t, open(os.path.join(sdir, "taxa", f"{t['slug']}.json"), "w"), indent=2, ensure_ascii=False)
    for d in datasets.values():
        d["taxa"] = sorted(set(d["taxa"]))
        json.dump(d, open(os.path.join(sdir, "datasets", f"{d['id']}.json"), "w"), indent=2, ensure_ascii=False)
    json.dump(mentions, open(os.path.join(sdir, "mentions.json"), "w"), indent=2, ensure_ascii=False)
    os.makedirs(os.path.join(sdir, "files", "profiles"), exist_ok=True)
    for slug, p in profiles.items():
        p["gaps"] = gaps.get(slug, [])
        json.dump(p, open(os.path.join(sdir, "files", "profiles", f"{slug}.json"), "w"), indent=2, ensure_ascii=False, default=str)
    write_reports(sdir, slice_name, cfg, taxa, datasets, mentions, profiles, gaps)
    print(f"{len(taxa)} taxa, {len(datasets)} datasets, {len(mentions)} mentions")


def write_reports(sdir, slice_name, cfg, taxa, datasets, mentions, profiles, gaps):
    axes = ["taxonomy", "genome", "occurrence", "barcode", "fossil", "conservation", "morphology3d", "bioelectric", "phylogeny", "traits"]
    by_slug = {t["slug"]: t for t in taxa.values()}
    cat = {d["id"]: d.get("category") for d in datasets.values()}
    rows = []
    for slug, t in by_slug.items():
        have = {cat[d] for d in t["datasets"] if d in cat}
        rows.append((slug, t["accepted_name"], have))
    md = [f"# Organism slice `{cfg['slice']}`\n", cfg["description"] + "\n",
          f"Generated by `uv run --with pyarrow test-data/organisms/claim-tests/fetch.py {slice_name}` on {TODAY}. "
          f"{len(taxa)} taxa, {len(datasets)} dataset records, {len(mentions)} mentions (one per species and claim, quoted from the claim's `result.json` or statement).\n",
          "## Axes covered per taxon\n", "| taxon | " + " | ".join(axes) + " |", "|---|" + "---|" * len(axes)]
    for slug, name, have in sorted(rows, key=lambda r: r[1]):
        md.append(f"| {name} | " + " | ".join("●" if a in have else "·" for a in axes) + " |")
    md.append("\n| axis | taxa covered |\n|---|---|")
    for a in axes:
        md.append(f"| {a} | {sum(a in h for _, _, h in rows)} of {len(rows)} |")
    md.append("\n## Gaps (sources queried that returned nothing)\n")
    for slug in sorted(gaps):
        md.append(f"- **{by_slug[slug]['accepted_name']}**: " + "; ".join(gaps[slug]))
    md.append("\n## Non-animal taxa seen\n\nThe ch07-04 junction-angle test also used three plant tissues: *Physcomitrium patens* (moss leaf), "
              "*Festuca arundinacea* (leaf epidermis) and *Aloe vera* (leaf epidermis). Animals only in this tree, so no records were built.\n")
    md.append("## Notes\n\n- Counts are API query results on the retrieval date; each distribution records the exact URL and the sha256 of the response.\n"
              "- BOLD, MorphoSource and DANDI are searched by name. MorphoSource keyword search misses specimens catalogued under other names, so a gap there is not proof of absence. "
              "DANDI dandisets count only when their asset summary lists the taxon's NCBI id and an electrophysiological approach.\n"
              "- FishBase/SeaLifeBase rows for each species are vendored in `files/lifebase/<slug>.json` (every row of the tables listed in the dataset record). "
              "Per-species summaries of all sources are in `files/profiles/<slug>.json` and `PROFILES.md`.\n"
              "- No record carries an assessment; reliability scoring is a separate pass.\n")
    open(os.path.join(sdir, "REPORT.md"), "w").write("\n".join(md) + "\n")

    pm = [f"# Species profiles: `{cfg['slice']}`\n", f"Generated {TODAY} from `files/profiles/`. Genome = NCBI reference assembly; counts are records on the retrieval date.\n",
          "| taxon | claims | genome (level, contig N50, BUSCO) | NCBI genes | GBIF occ. | OBIS occ. | BOLD specimens / BINs | PBDB occ. | DANDI ephys | IUCN | key traits |",
          "|---|---|---|---:|---:|---:|---|---:|---:|---|---|"]
    for slug, p in sorted(profiles.items(), key=lambda kv: kv[1]["accepted_name"]):
        g, c, tr = p.get("genome") or {}, p["counts"], p["traits"]
        gs = f"{g.get('accession')} ({g.get('level')}, {g.get('contig_n50_bp', '?')}, {g.get('busco_complete_fraction', '?')})" if g else "·"
        keys = []
        if tr.get("max_length_cm"): keys.append(f"Lmax {tr['max_length_cm']} cm")
        if tr.get("lw_bayes_b"): keys.append(f"LW b {tr['lw_bayes_b']:.3f} (Bayes), median {tr.get('lw_b_median')} over {tr.get('lw_studies')} studies")
        if tr.get("growth_studies"): keys.append(f"{tr['growth_studies']} growth studies")
        an = tr.get("anage") or {}
        if an.get("Maximum longevity (yrs)"): keys.append(f"max longevity {an['Maximum longevity (yrs)']} yr")
        if an.get("Adult weight (g)"): keys.append(f"adult {an['Adult weight (g)']} g")
        pm.append(f"| {p['accepted_name']} | {', '.join(x.replace('thompson1917-', '') for x in p['claims'])} | {gs} | {c.get('ncbi_gene', '·')} | {c.get('gbif_occurrences', '·')} | "
                  f"{c.get('obis_occurrences', '·')} | {c.get('bold_specimens', 0)} / {c.get('bold_bins', 0)} | {c.get('pbdb_occurrences', 0)} | {c.get('dandi_ephys_dandisets', 0)} | "
                  f"{tr.get('iucn', '·')} | {'; '.join(keys) or '·'} |")
    open(os.path.join(sdir, "PROFILES.md"), "w").write("\n".join(pm) + "\n")


if __name__ == "__main__":
    main()
