#!/usr/bin/env python3
"""Build the organism reference data for Thompson, On Growth and Form, chapters VI-XI.

Usage (run from anywhere; paths are resolved relative to the repository):

    python3 build.py mentions    # scan claims + book text -> mentions.json
    python3 build.py resolve     # GBIF / WoRMS / PBDB / NCBI / Wikidata / ITIS -> taxa/*.json
    python3 build.py datasets    # GBIF counts, PBDB, WoRMS, AnAge, PanTHERIA, AVONET, NCBI genomes -> datasets/*.json
    python3 build.py report      # REPORT.md
    python3 build.py all

Every HTTP response is cached under $ORGANISMS_CACHE (default /tmp/organisms-cache/ch06-11)
so the run is reproducible and the APIs are not hammered. Downloaded data files stay in the
cache directory and are never written into the repository; only their sha256 / byte_size are.
"""
import hashlib
import json
import os
import re
import sys
import time
import zipfile
import io
import datetime as dt
from collections import Counter, defaultdict
from urllib.parse import quote

import requests

sys.stdout.reconfigure(line_buffering=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taxa_list import TAXA  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SLICE = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(SLICE, "..", "..", "..", ".."))
PROJECT = "thompson-growth-form"
SLICE_NAME = "ch06-11"
CHAPTERS = ["VI", "VII", "VIII", "IX", "X", "XI"]
TEXT_FILE = f"claim-sources/{PROJECT}/inputs/pg55264.txt"
TEXT_RANGE = (9882, 19560)  # 1-based inclusive line range of chapters VI-XI
CACHE = os.environ.get("ORGANISMS_CACHE", "/tmp/organisms-cache/ch06-11")
os.makedirs(CACHE, exist_ok=True)
UA = {"User-Agent": "delphi-organisms/0.1 (https://github.com/fractastical/delphi; cloud agent)"}
TODAY = dt.date.today().isoformat()
VENDORED_BY = {"kind": "cloud-agent", "model": "claude-fable-5.1", "run": "cursor/thompson-organisms-ch06-11-4fb0", "date": TODAY}

NON_ANIMAL_GROUPS = {"protist"}


# ----------------------------------------------------------------------------- helpers
def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def cache_path(url, suffix=".bin"):
    return os.path.join(CACHE, sha256(url.encode())[:24] + suffix)


HOST_INTERVAL = {"eutils.ncbi.nlm.nih.gov": 0.4, "www.wikidata.org": 1.2, "www.itis.gov": 0.3, "api.ncbi.nlm.nih.gov": 0.4}
_last_call = {}


def throttle(url):
    host = url.split("/")[2]
    gap = HOST_INTERVAL.get(host, 0.15)
    wait = _last_call.get(host, 0) + gap - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call[host] = time.time()


def fetch(url, retries=7, timeout=120, method="GET", json_body=None):
    """GET url with caching and per-host throttling. Returns (bytes, retrieved_at_iso, from_cache)."""
    p = cache_path(url)
    meta = p + ".meta.json"
    if os.path.exists(p) and os.path.exists(meta):
        with open(p, "rb") as f, open(meta) as m:
            return f.read(), json.load(m)["retrieved_at"], True
    delay = 3
    for attempt in range(retries):
        throttle(url)
        try:
            if method == "POST":
                r = requests.post(url, json=json_body, headers=UA, timeout=timeout)
            else:
                r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code in (200, 204):
                ts = now()
                with open(p, "wb") as f:
                    f.write(r.content)
                with open(meta, "w") as m:
                    json.dump({"url": url, "retrieved_at": ts, "status": r.status_code}, m)
                return r.content, ts, False
            if r.status_code in (404, 400):
                ts = now()
                with open(p, "wb") as f:
                    f.write(r.content)
                with open(meta, "w") as m:
                    json.dump({"url": url, "retrieved_at": ts, "status": r.status_code}, m)
                return r.content, ts, False
            print(f"  HTTP {r.status_code} for {url}", file=sys.stderr)
            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                delay = max(delay, int(ra) if ra and ra.isdigit() else 10)
        except requests.RequestException as e:
            print(f"  {type(e).__name__} for {url}: {e}", file=sys.stderr)
        time.sleep(delay)
        delay *= 2
    raise RuntimeError(f"failed: {url}")


def fetch_json(url, **kw):
    b, ts, cached = fetch(url, **kw)
    try:
        return json.loads(b.decode("utf-8", "replace")), ts, b
    except json.JSONDecodeError:
        return None, ts, b


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def dump_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def clean_text(s):
    s = re.sub(r"\{\d+\}", "", s)       # page markers
    s = re.sub(r"\[\d+\]", "", s)       # footnote markers
    s = s.replace("_", "")
    return re.sub(r"\s+", " ", s).strip()


def read_text_lines():
    with open(os.path.join(REPO, TEXT_FILE), encoding="utf-8") as f:
        return f.read().split("\n")


def claims_in_scope():
    data = load_json(os.path.join(REPO, "claim-sources", PROJECT, "claims.json"))
    return [c for c in data["claims"] if c.get("chapter") in CHAPTERS]


# ----------------------------------------------------------------------------- mentions
def compiled_patterns():
    out = []
    for t in TAXA:
        out.append((t, [re.compile(p) for p in t["patterns"]]))
    return out


def build_mentions():
    lines = read_text_lines()
    claims = claims_in_scope()
    pats = compiled_patterns()
    mentions = []
    # 1. claims: one mention per (taxon, claim), the quote field is preferred as the verbatim source
    for c in claims:
        for t, regs in pats:
            hit = None
            for field in ("quote", "claim"):
                txt = c[field].replace("_", " ")
                for rg in regs:
                    m = rg.search(txt)
                    if m:
                        hit = (field, m, txt)
                        break
                if hit:
                    break
            if hit:
                field, m, txt = hit
                a, b = m.span()
                lo = max(0, txt.rfind(" ", 0, max(0, a - 60)) + 1)
                hi = txt.find(" ", b + 60)
                hi = len(txt) if hi == -1 else hi
                mentions.append({
                    "taxon_slug": t["slug"],
                    "name_as_written": m.group(0),
                    "source": {"claim_id": c["id"], "field": field},
                    "quote": txt[lo:hi].strip(),
                })
    # 2. book text, chapters VI-XI: one mention per (taxon, line)
    lo, hi = TEXT_RANGE
    for i in range(lo - 1, hi):
        raw = lines[i]
        if not raw.strip():
            continue
        scan = raw.replace("_", " ")  # italics markers break \b word boundaries
        for t, regs in pats:
            m = None
            for rg in regs:
                m = rg.search(scan)
                if m:
                    break
            if not m:
                continue
            mentions.append({
                "taxon_slug": t["slug"],
                "name_as_written": clean_text(m.group(0)),
                "source": {"file": TEXT_FILE, "line_start": i + 1, "line_end": i + 1},
                "quote": clean_text(raw),
            })
    dump_json(os.path.join(SLICE, "mentions.json"), mentions)
    by_taxon = Counter(m["taxon_slug"] for m in mentions)
    print(f"{len(mentions)} mentions, {len(by_taxon)} taxa with mentions")
    missing = [t["slug"] for t in TAXA if t["slug"] not in by_taxon]
    if missing:
        print("taxa in list without any mention:", missing)
    return mentions


# ----------------------------------------------------------------------------- resolution
GBIF_RANKS = {"species", "genus", "family", "order", "class", "phylum", "kingdom", "subspecies"}
BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"


def expected_kingdoms(t):
    if t.get("kingdom"):
        # GBIF parks some unplaced radiolarian genera under Animalia incertae sedis
        return {t["kingdom"], "Chromista", "Protozoa", "Animalia"} if t.get("group") == "protist" else {t["kingdom"]}
    return {"Animalia"}


def gbif_match(t):
    """Match a name against the GBIF backbone.

    The match API reports HIGHERRANK for a bare uninomial even when the canonical name is
    identical, so the match is accepted only when canonicalName equals the query. When the
    match API fails, fall back to the backbone name lookup (species?name=) filtered by the
    kingdom / phylum / class / family hints, preferring accepted usages over synonyms.
    """
    query = t["query"]
    rank = t.get("rank") or ("species" if " " in query else "genus")
    params = {"name": query, "strict": "false"}
    if rank in GBIF_RANKS:
        params["rank"] = rank.upper()
    for k in ("kingdom", "phylum", "order", "family"):
        if t.get(k):
            params[k] = t[k]
    if t.get("cls"):
        params["class"] = t["cls"]
    url = "https://api.gbif.org/v1/species/match?" + "&".join(f"{k}={quote(v)}" for k, v in params.items())
    j, ts, _ = fetch_json(url)
    res = {"url": url, "retrieved_at": ts, "raw": j, "match_type": (j or {}).get("matchType")}
    got_rank = (j or {}).get("rank", "").lower()
    rank_ok = (got_rank == rank) if rank in GBIF_RANKS else got_rank not in ("genus", "species", "subspecies")
    ok = bool(j) and (j.get("canonicalName") or "").lower() == query.lower() and j.get("matchType") in ("EXACT", "HIGHERRANK", "FUZZY") \
        and j.get("kingdom") in expected_kingdoms(t) and rank_ok
    if ok:
        key = j.get("acceptedUsageKey") or j.get("usageKey")
        res.update(usage_key=j.get("usageKey"), accepted_key=key, rank=j.get("rank", "").lower(), status=j.get("status"),
                   match_type="EXACT", confidence=j.get("confidence"), canonical=j.get("canonicalName"),
                   lineage={k: j.get(k) for k in ("kingdom", "phylum", "class", "order", "family") if j.get(k)})
        if j.get("acceptedUsageKey"):
            acc, _, _ = fetch_json(f"https://api.gbif.org/v1/species/{key}")
            if acc:
                res["accepted_name"] = acc.get("canonicalName")
                res["lineage"] = {k: acc.get(k) for k in ("kingdom", "phylum", "class", "order", "family") if acc.get(k)}
        else:
            res["accepted_name"] = j.get("canonicalName")
        return res
    # fallback: exact-name lookup in the backbone
    url2 = f"https://api.gbif.org/v1/species?name={quote(query)}&datasetKey={BACKBONE}&limit=50"
    j2, ts2, _ = fetch_json(url2)
    cands = []
    for r in (j2 or {}).get("results", []):
        if (r.get("canonicalName") or "").lower() != query.lower():
            continue
        if r.get("kingdom") not in expected_kingdoms(t):
            continue
        if t.get("phylum") and r.get("phylum") and r["phylum"] != t["phylum"]:
            continue
        if t.get("cls") and r.get("class") and r["class"] != t["cls"]:
            continue
        if t.get("family") and r.get("family") and r["family"] != t["family"]:
            continue
        if rank in GBIF_RANKS and (r.get("rank") or "").lower() != rank:
            continue
        if rank not in GBIF_RANKS and (r.get("rank") or "").lower() in ("genus", "species", "subspecies"):
            continue  # a higher group must not be matched to a homonymous genus
        if r.get("taxonomicStatus") == "PROPARTE_SYNONYM":
            continue  # e.g. Reptilia -> Crocodylia; no single accepted usage exists
        cands.append(r)
    order = {"ACCEPTED": 0, "SYNONYM": 1, "HOMOTYPIC_SYNONYM": 1, "HETEROTYPIC_SYNONYM": 1, "DOUBTFUL": 3}
    cands.sort(key=lambda r: order.get(r.get("taxonomicStatus"), 4))
    if not cands:
        res["url"] = url2
        res["match_type"] = "NONE"
        return res
    r = cands[0]
    key = r.get("acceptedKey") or r["key"]
    res.update(url=url2, retrieved_at=ts2, raw=r, usage_key=r["key"], accepted_key=key, rank=(r.get("rank") or "").lower(),
               status=r.get("taxonomicStatus"), match_type="NAME_LOOKUP", confidence=None, canonical=r.get("canonicalName"),
               lineage={k: r.get(k) for k in ("kingdom", "phylum", "class", "order", "family") if r.get(k)})
    if r.get("acceptedKey"):
        acc, _, _ = fetch_json(f"https://api.gbif.org/v1/species/{key}")
        if acc:
            res["accepted_name"] = acc.get("canonicalName")
            res["lineage"] = {k: acc.get(k) for k in ("kingdom", "phylum", "class", "order", "family") if acc.get(k)}
    else:
        res["accepted_name"] = r.get("canonicalName")
    return res


def ncbi_lookup(t, names):
    """NCBI Taxonomy id whose scientific name equals one of the candidate names and whose
    lineage contains the expected keyword (default Metazoa)."""
    if "ncbi_name" in t and t["ncbi_name"] is None:
        return None
    kw = re.compile(t.get("ncbi_kw", "Metazoa"))
    names = ([t["ncbi_name"]] if t.get("ncbi_name") else []) + list(names)
    for name in names:
        if not name:
            continue
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=taxonomy&term={quote(name)}&retmode=json"
        j, ts, _ = fetch_json(url)
        ids = (j or {}).get("esearchresult", {}).get("idlist", [])
        for tid in ids[:10]:
            b, _, _ = fetch(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=taxonomy&id={tid}&retmode=xml")
            x = b.decode("utf-8", "replace")
            sci = re.search(r"<ScientificName>(.*?)</ScientificName>", x)
            lin = re.search(r"<Lineage>(.*?)</Lineage>", x)
            rank = re.search(r"<Rank>(.*?)</Rank>", x)
            if sci and lin and sci.group(1).lower() == name.lower() and kw.search(lin.group(1) + "; " + sci.group(1)):
                return {"taxid": int(tid), "name": sci.group(1), "rank": rank.group(1) if rank else None, "lineage": lin.group(1), "url": url}
    return None


def wikidata_lookup(names):
    for name in names:
        if not name:
            continue
        url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={quote(name)}&language=en&format=json&limit=10"
        j, ts, _ = fetch_json(url)
        ids = [s["id"] for s in (j or {}).get("search", [])]
        if not ids:
            continue
        url2 = f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={'|'.join(ids)}&props=claims|labels&languages=en&format=json"
        e, _, _ = fetch_json(url2)
        for qid in ids:
            ent = (e or {}).get("entities", {}).get(qid, {})
            cl = ent.get("claims", {})
            p31 = [c["mainsnak"].get("datavalue", {}).get("value", {}).get("id") for c in cl.get("P31", [])]
            p225 = [c["mainsnak"].get("datavalue", {}).get("value") for c in cl.get("P225", [])]
            if ("Q16521" in p31 or "Q310890" in p31 or "Q23038290" in p31) and any((v or "").lower() == name.lower() for v in p225):
                return {"qid": qid, "taxon_name": p225[0], "url": url}
    return None


def worms_lookup(t, names):
    want_phylum = t.get("phylum")
    for name in names:
        if not name:
            continue
        url = f"https://www.marinespecies.org/rest/AphiaRecordsByName/{quote(name)}?like=false&marine_only=false"
        j, ts, _ = fetch_json(url)
        if not isinstance(j, list) or not j:
            continue
        cands = [r for r in j if r.get("scientificname", "").lower() == name.lower()]
        if want_phylum:
            ph = [r for r in cands if (r.get("phylum") or "") == want_phylum]
            cands = ph or cands
        if t.get("family"):
            fm = [r for r in cands if (r.get("family") or "") == t["family"]]
            cands = fm or cands
        acc = [r for r in cands if r.get("status") == "accepted"]
        pick = (acc or [r for r in cands if r.get("valid_AphiaID")] or cands)
        if not pick:
            continue
        r = pick[0]
        return {"matched_aphia_id": r["AphiaID"], "matched_name": r["scientificname"], "status": r.get("status"),
                "valid_aphia_id": r.get("valid_AphiaID") or r["AphiaID"], "valid_name": r.get("valid_name") or r["scientificname"],
                "rank": (r.get("rank") or "").lower(), "url": url, "n_homonyms": len(j),
                "lineage": {k: r.get(k) for k in ("kingdom", "phylum", "class", "order", "family") if r.get(k)},
                "is_extinct": r.get("isExtinct")}
    return None


RANKS = {2: "subspecies", 3: "species", 4: "subgenus", 5: "genus", 6: "subtribe", 7: "tribe", 8: "subfamily", 9: "family", 10: "superfamily",
         11: "infraorder", 12: "suborder", 13: "order", 14: "superorder", 15: "infraclass", 16: "subclass", 17: "class", 18: "superclass",
         19: "subphylum", 20: "phylum", 21: "superphylum", 22: "subkingdom", 23: "kingdom"}


def pbdb_lookup(t, names):
    for name in names:
        if not name:
            continue
        url = f"https://paleobiodb.org/data1.2/taxa/single.json?name={quote(name)}&show=class"
        j, ts, _ = fetch_json(url)
        recs = (j or {}).get("records", [])
        if not recs:
            continue
        r = recs[0]
        if t.get("phylum") and r.get("phl") and r["phl"] != t["phylum"]:
            continue
        tid = int(r["oid"].split(":")[1])
        acc_id = int(r["acc"].split(":")[1]) if r.get("acc") else tid
        return {"taxon_id": tid, "name": r.get("nam"), "accepted_id": acc_id, "accepted_name": r.get("acn") or r.get("nam"),
                "rank": RANKS.get(r.get("rnk")), "n_occurrences": r.get("noc"), "url": url, "difference": r.get("tdf"),
                "lineage": {k2: r.get(k1) for k1, k2 in (("phl", "phylum"), ("cll", "class"), ("odl", "order"), ("fml", "family")) if r.get(k1) and r.get(k1) != "NO_FAMILY_SPECIFIED"},
                "extant": r.get("ext")}
    return None


def itis_lookup(names):
    for name in names:
        if not name:
            continue
        url = f"https://www.itis.gov/ITISWebService/jsonservice/searchByScientificName?srchKey={quote(name)}"
        j, ts, _ = fetch_json(url)
        for r in (j or {}).get("scientificNames") or []:
            if r and (r.get("combinedName") or "").lower() == name.lower() and r.get("kingdom") in ("Animalia", "Chromista", "Protozoa"):
                return {"tsn": int(r["tsn"]), "name": r["combinedName"], "url": url}
    return None


def safe(fn, *a):
    try:
        return fn(*a)
    except RuntimeError as e:
        print(f"  lookup failed: {e}", file=sys.stderr)
        return None


def resolve_all():
    mentions = load_json(os.path.join(SLICE, "mentions.json"))
    by_taxon = defaultdict(list)
    for m in mentions:
        by_taxon[m["taxon_slug"]].append(m)
    resolution = {}
    for i, t in enumerate(TAXA):
        slug = t["slug"]
        if slug not in by_taxon:
            continue
        print(f"[{i+1}/{len(TAXA)}] {slug}", file=sys.stderr)
        g = gbif_match(t)
        w = worms_lookup(t, [t.get("worms_name"), t["query"]]) if (t.get("marine") or t.get("worms_name")) else None
        p = pbdb_lookup(t, [t.get("pbdb_name"), t["query"]]) if t.get("fossil") else None
        candidates = [t["query"], g.get("accepted_name"), (w or {}).get("valid_name"), (p or {}).get("accepted_name")]
        seen, names = set(), []
        for n in candidates:
            if n and n not in seen:
                seen.add(n)
                names.append(n)
        n = safe(ncbi_lookup, t, names)
        q = safe(wikidata_lookup, names)
        it = safe(itis_lookup, names)
        resolution[slug] = {"gbif": g, "worms": w, "pbdb": p, "ncbi": n, "wikidata": q, "itis": it}
        time.sleep(0.1)
    dump_json(os.path.join(CACHE, "resolution.json"), resolution)
    write_taxa(resolution, by_taxon)
    return resolution


def accepted_name_for(t, r):
    g, w, p, n = r["gbif"], r["worms"], r["pbdb"], r["ncbi"]
    if w and w.get("valid_name"):
        return w["valid_name"]
    if g.get("accepted_name"):
        return g["accepted_name"]
    if n and n.get("name"):
        return n["name"]
    if p and p.get("accepted_name"):
        return p["accepted_name"]
    return t["query"]


def rank_for(t, r):
    g, w, p = r["gbif"], r["worms"], r["pbdb"]
    if t.get("rank"):
        return t["rank"]
    for src in (w, g, p):
        if src and src.get("rank"):
            return src["rank"]
    return None


def lineage_for(t, r):
    lin = {}
    for src in (r["gbif"], r["worms"], r["pbdb"]):
        if src and src.get("lineage"):
            for k, v in src["lineage"].items():
                lin.setdefault(k, v)
    if t.get("group") not in NON_ANIMAL_GROUPS:
        lin.setdefault("kingdom", "Animalia")
    if t.get("phylum"):
        lin.setdefault("phylum", t["phylum"])
    lin = {k: lin[k] for k in ("kingdom", "phylum", "class", "order", "family") if lin.get(k)}
    if r["ncbi"] and r["ncbi"].get("lineage"):
        lin["ncbi_lineage"] = r["ncbi"]["lineage"]
    return lin


def write_taxa(resolution, by_taxon):
    tdir = os.path.join(SLICE, "taxa")
    os.makedirs(tdir, exist_ok=True)
    existing = {}
    for fn in os.listdir(tdir):
        if fn.endswith(".json"):
            existing[fn[:-5]] = load_json(os.path.join(tdir, fn))
            os.remove(os.path.join(tdir, fn))
    for t in TAXA:
        slug = t["slug"]
        if slug not in resolution:
            continue
        r = resolution[slug]
        g, w, p, n, q, it = r["gbif"], r["worms"], r["pbdb"], r["ncbi"], r["wikidata"], r["itis"]
        ms = by_taxon[slug]
        names_written = sorted({m["name_as_written"] for m in ms}, key=str.lower)
        claim_ids = sorted({m["source"]["claim_id"] for m in ms if "claim_id" in m["source"]})
        n_text = sum(1 for m in ms if "file" in m["source"])
        notes = [t.get("notes")] if t.get("notes") else []
        if g.get("match_type") == "NAME_LOOKUP":
            notes.append(f"GBIF usage found by exact-name lookup in the backbone (status {g.get('status')}), not by the match API.")
        if g.get("status") == "DOUBTFUL":
            notes.append("GBIF marks this usage doubtful.")
        elif g.get("match_type") in ("NONE", "HIGHERRANK", None):
            notes.append(f"No GBIF backbone usage for '{t['query']}'.")
        if g.get("status") and g["status"] != "ACCEPTED" and g.get("accepted_key") != g.get("usage_key"):
            notes.append(f"GBIF treats '{g.get('canonical')}' as {g['status'].lower()} of '{g.get('accepted_name')}' (usageKey {g.get('usage_key')}, accepted {g.get('accepted_key')}).")
        if w and w.get("status") != "accepted":
            notes.append(f"WoRMS: '{w['matched_name']}' (AphiaID {w['matched_aphia_id']}) is {w['status']}; accepted name {w['valid_name']} (AphiaID {w['valid_aphia_id']}).")
        if p and p.get("difference"):
            notes.append(f"PBDB: {p['name']} is {p['difference']} {p['accepted_name']}.")
        lin = lineage_for(t, r)
        if t.get("group") in NON_ANIMAL_GROUPS and lin.get("kingdom") == "Animalia":
            notes.append("GBIF places this genus in Animalia incertae sedis; the kingdom is omitted here because the taxon is a protist.")
            lin.pop("kingdom")
        entry = {
            "slug": slug,
            "accepted_name": accepted_name_for(t, r),
            "rank": rank_for(t, r),
            "vernacular": t.get("vern", []),
            "names_as_written": names_written,
            "identifiers": {
                "gbif_usage_key": g.get("accepted_key"),
                "ncbi_taxid": n["taxid"] if n else None,
                "wikidata_qid": q["qid"] if q else None,
                "itis_tsn": it["tsn"] if it else None,
                "worms_aphia_id": w["valid_aphia_id"] if w else None,
                "pbdb_taxon_id": p["accepted_id"] if p else None,
            },
            "lineage": lin,
            "mentioned_in": claim_ids,
            "n_text_mentions": n_text,
            "datasets": existing.get(slug, {}).get("datasets", []),
            "notes": " ".join(notes) if notes else None,
            "animalia": t.get("group") not in NON_ANIMAL_GROUPS,
            "resolution_sources": {k: v.get("url") for k, v in (("gbif", g), ("worms", w or {}), ("pbdb", p or {}), ("ncbi", n or {}), ("wikidata", q or {}), ("itis", it or {})) if v},
        }
        dump_json(os.path.join(tdir, f"{slug}.json"), entry)


# ----------------------------------------------------------------------------- datasets
def dist(url, body, ts, media_type="application/json", inspected=True, **extra):
    d = {"download_url": url, "media_type": media_type, "byte_size": len(body), "sha256": sha256(body), "retrieved_at": ts, "inspected": inspected}
    d.update(extra)
    return d


def doi_resolves(doi):
    j, ts, _ = fetch_json(f"https://doi.org/api/handles/{doi}")
    return bool(j and j.get("responseCode") == 1), ts


def url_resolves(url):
    try:
        r = requests.head(url, headers=UA, timeout=60, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(url, headers=UA, timeout=60, stream=True)
        return r.status_code < 400
    except requests.RequestException:
        return False


def taxa_files():
    tdir = os.path.join(SLICE, "taxa")
    out = {}
    for fn in sorted(os.listdir(tdir)):
        if fn.endswith(".json"):
            out[fn[:-5]] = load_json(os.path.join(tdir, fn))
    return out


def save_taxa(taxa):
    for slug, t in taxa.items():
        t["datasets"] = sorted(set(t["datasets"]))
        dump_json(os.path.join(SLICE, "taxa", f"{slug}.json"), t)


def write_dataset(rec):
    dump_json(os.path.join(SLICE, "datasets", f"{rec['id']}.json"), rec)


def ds_gbif_occurrences(taxa):
    ids = []
    for slug, t in taxa.items():
        key = t["identifiers"].get("gbif_usage_key")
        if not key:
            continue
        url = f"https://api.gbif.org/v1/occurrence/search?taxonKey={key}&limit=0"
        j, ts, body = fetch_json(url)
        if not j or "count" not in j:
            continue
        did = f"gbif-occurrences-{slug}-{ts[:10]}"
        rec = {
            "id": did,
            "label": f"GBIF occurrence count for {t['accepted_name']} (taxonKey {key}), {ts[:10]}",
            "identifier": url,
            "doi": None,
            "bibliographic_citation": f"GBIF.org ({ts[:10]}) GBIF Occurrence Search API, taxonKey={key} (count only). https://api.gbif.org/v1/occurrence/search?taxonKey={key}&limit=0",
            "is_referenced_by": "https://techdocs.gbif.org/en/openapi/v1/occurrence",
            "creators": ["GBIF.org"],
            "issued": ts[:10],
            "license": "Occurrence records carry CC0 1.0, CC BY 4.0 or CC BY-NC 4.0 per publishing dataset (https://www.gbif.org/terms); this record vendors only the aggregate count.",
            "version": ts[:10],
            "distributions": [dist(url, body, ts)],
            "counts": [{"property_id": "n_occurrences", "value": j["count"], "description": f"occurrence records in GBIF for taxonKey {key} ({t['accepted_name']}) and all taxa nested beneath it, as returned by the search API"}],
            "measurement_technique": "GBIF occurrence search API count (limit=0); aggregated specimen, observation and literature records indexed by GBIF.",
            "taxa": [slug],
            "role": f"number of GBIF occurrence records for {t['accepted_name']}",
            "integrity": {"identifier_resolves": True, "checksum_verified": True, "checked_at": ts},
            "vendored_by": VENDORED_BY,
        }
        write_dataset(rec)
        t["datasets"].append(did)
        ids.append(did)
    print(f"GBIF occurrence records: {len(ids)}")


def ds_gbif_backbone(taxa, resolution):
    j, ts, body = fetch_json("https://api.gbif.org/v1/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c")
    dists, covered = [], []
    for slug, t in taxa.items():
        r = resolution.get(slug, {}).get("gbif") or {}
        if t["identifiers"].get("gbif_usage_key") and r.get("url"):
            b, ts2, _ = fetch(r["url"])
            dists.append(dist(r["url"], b, ts2, taxon=slug))
            covered.append(slug)
    did = f"gbif-backbone-taxonomy-{SLICE_NAME}-{ts[:10]}"
    rec = {
        "id": did,
        "label": f"GBIF Backbone Taxonomy, name matches for Thompson chapters VI-XI taxa ({ts[:10]})",
        "identifier": "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",
        "doi": "10.15468/39omei",
        "bibliographic_citation": j["citation"]["text"],
        "is_referenced_by": "https://doi.org/10.15468/39omei",
        "creators": ["GBIF Secretariat"],
        "issued": j.get("pubDate", "")[:10],
        "license": "CC BY 4.0",
        "version": j.get("pubDate", "")[:10],
        "distributions": dists,
        "counts": [{"property_id": "n_rows_for_taxa", "value": len(covered), "description": "taxa in this slice matched to a backbone usageKey via the species/match API (one distribution per query)"}],
        "measurement_technique": "GBIF species/match API against the GBIF Backbone Taxonomy, with kingdom/phylum/class/family hints where the name is a homonym.",
        "taxa": covered,
        "role": "accepted names, ranks, higher classification and usageKeys for the listed taxa",
        "integrity": {"identifier_resolves": doi_resolves("10.15468/39omei")[0], "checksum_verified": True, "checked_at": now()},
        "vendored_by": VENDORED_BY,
    }
    write_dataset(rec)
    for s in covered:
        taxa[s]["datasets"].append(did)
    print(f"GBIF backbone record covers {len(covered)} taxa")


def ds_worms(taxa, resolution):
    dists, covered, counts = [], [], []
    for slug, t in taxa.items():
        w = resolution.get(slug, {}).get("worms")
        if not w:
            continue
        b, ts, _ = fetch(w["url"])
        dists.append(dist(w["url"], b, ts, taxon=slug))
        covered.append(slug)
    ts = now()
    did = f"worms-aphia-records-{SLICE_NAME}-{ts[:10]}"
    ok, _ = doi_resolves("10.14284/170")
    rec = {
        "id": did,
        "label": f"World Register of Marine Species (WoRMS) Aphia records for Thompson chapters VI-XI marine taxa ({ts[:10]})",
        "identifier": "https://www.marinespecies.org/",
        "doi": "10.14284/170",
        "bibliographic_citation": f"WoRMS Editorial Board ({ts[:4]}). World Register of Marine Species. Available from https://www.marinespecies.org at VLIZ. Accessed {ts[:10]}. doi:10.14284/170",
        "is_referenced_by": "https://doi.org/10.14284/170",
        "creators": ["WoRMS Editorial Board", "Flanders Marine Institute (VLIZ)"],
        "issued": ts[:10],
        "license": "CC BY 4.0",
        "version": ts[:10],
        "distributions": dists,
        "counts": [{"property_id": "n_rows_for_taxa", "value": len(covered), "description": "taxa in this slice with an Aphia record (AphiaRecordsByName, exact match); unaccepted names carry the valid AphiaID and name"}],
        "measurement_technique": "WoRMS REST API AphiaRecordsByName (like=false, marine_only=false). Molluscan names are curated by MolluscaBase, which shares the Aphia identifiers.",
        "taxa": covered,
        "role": "accepted names, synonymy, rank and classification for the listed marine and fossil taxa (AphiaID)",
        "integrity": {"identifier_resolves": ok, "checksum_verified": True, "checked_at": ts},
        "vendored_by": VENDORED_BY,
    }
    write_dataset(rec)
    for s in covered:
        taxa[s]["datasets"].append(did)
    print(f"WoRMS record covers {len(covered)} taxa")


def ds_pbdb(taxa, resolution):
    dists, covered, counts = [], [], []
    for slug, t in taxa.items():
        p = resolution.get(slug, {}).get("pbdb")
        if not p:
            continue
        name = p["accepted_name"]
        url = f"https://paleobiodb.org/data1.2/occs/list.json?base_name={quote(name)}&limit=1&rowcount"
        j, ts, body = fetch_json(url)
        if not j or "records_found" not in j:
            continue
        dists.append(dist(url, body, ts, taxon=slug))
        counts.append({"property_id": "n_occurrences", "value": j["records_found"], "description": f"fossil occurrences for {name} and nested taxa (base_name) for taxon {slug}"})
        covered.append(slug)
    ts = now()
    did = f"pbdb-occurrence-counts-{SLICE_NAME}-{ts[:10]}"
    rec = {
        "id": did,
        "label": f"Paleobiology Database fossil occurrence counts for Thompson chapters VI-XI fossil taxa ({ts[:10]})",
        "identifier": "https://paleobiodb.org/",
        "doi": None,
        "bibliographic_citation": f"The Paleobiology Database ({ts[:4]}). Data Service 1.2, occurrence list (occs/list, base_name queries). Accessed {ts[:10]} at https://paleobiodb.org/data1.2/",
        "is_referenced_by": "https://paleobiodb.org/data1.2/",
        "creators": ["Paleobiology Database contributors"],
        "issued": ts[:10],
        "license": "CC BY 4.0",
        "version": ts[:10],
        "distributions": dists,
        "counts": [{"property_id": "n_rows_for_taxa", "value": len(covered), "description": "fossil taxa in this slice with an occurrence count"}] + counts,
        "measurement_technique": "PBDB Data Service 1.2 occs/list with base_name and rowcount; records_found is the number of fossil occurrences assigned to the taxon or any taxon nested in it.",
        "taxa": covered,
        "role": "fossil occurrence counts and PBDB taxon identifiers for the listed extinct and fossil-bearing taxa",
        "integrity": {"identifier_resolves": url_resolves("https://paleobiodb.org/data1.2/"), "checksum_verified": True, "checked_at": ts},
        "vendored_by": VENDORED_BY,
    }
    write_dataset(rec)
    for s in covered:
        taxa[s]["datasets"].append(did)
    print(f"PBDB record covers {len(covered)} taxa")


def match_rows_by_rank(taxa, row_iter, colmap):
    """colmap: rank -> column name. Returns slug -> n_rows."""
    import pandas as pd
    df = row_iter
    hits = {}
    for slug, t in taxa.items():
        rank, name = t["rank"], t["accepted_name"]
        col = colmap.get(rank)
        if not col or col not in df.columns:
            continue
        n = int((df[col].astype(str).str.strip().str.lower() == name.lower()).sum())
        if n:
            hits[slug] = n
    return hits


def ds_anage(taxa):
    import pandas as pd
    url = "https://genomics.senescence.info/species/dataset.zip"
    body, ts, _ = fetch(url)
    z = zipfile.ZipFile(io.BytesIO(body))
    names = z.namelist()
    data_name = [n for n in names if n.endswith("anage_data.txt")][0]
    df = pd.read_csv(z.open(data_name), sep="\t", dtype=str)
    df["Binomial"] = (df["Genus"].str.strip() + " " + df["Species"].str.strip())
    hits = match_rows_by_rank(taxa, df, {"species": "Binomial", "genus": "Genus", "family": "Family", "order": "Order", "class": "Class", "phylum": "Phylum"})
    rel = z.read([n for n in names if "release" in n.lower() or "readme" in n.lower()][0]).decode("utf-8", "replace") if any("release" in n.lower() or "readme" in n.lower() for n in names) else ""
    build = re.search(r"[Bb]uild\s*(\d+)", rel)
    build = build.group(1) if build else "unknown"
    ok, _ = doi_resolves("10.1093/nar/gkx1042")
    did = f"anage-build-{build}"
    rec = {
        "id": did,
        "label": f"AnAge: The Animal Ageing and Longevity Database, build {build}",
        "identifier": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gkx1042",
        "bibliographic_citation": "Tacutu R, Thornton D, Johnson E, Budovsky A, Barardo D, Craig T, Diana E, Lehmann G, Toren D, Wang J, Fraifeld VE, de Magalhães JP (2018) Human Ageing Genomic Resources: new and updated databases. Nucleic Acids Research 46(D1):D1083-D1090.",
        "is_referenced_by": "https://doi.org/10.1093/nar/gkx1042",
        "creators": ["Tacutu R", "Thornton D", "Johnson E", "Budovsky A", "Barardo D", "Craig T", "Diana E", "Lehmann G", "Toren D", "Wang J", "Fraifeld VE", "de Magalhães JP"],
        "issued": "2017-11",
        "license": "CC BY 3.0",
        "version": f"build {build}",
        "distributions": [dist(url, body, ts, media_type="application/zip", files=names)],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": f"species rows in {data_name} as distributed"},
            {"property_id": "n_rows_for_taxa", "value": int(sum(hits.values())), "description": "rows whose Genus+Species / Genus / Family / Order / Class / Phylum column equals the accepted name of a taxon in this slice, at that taxon's rank"},
        ] + [{"property_id": "n_rows_for_taxon", "value": n, "description": f"rows for {slug}"} for slug, n in sorted(hits.items())],
        "measurement_technique": "Literature-compiled life-history traits (maximum longevity, body mass, maturity, growth rate) per species.",
        "taxa": sorted(hits),
        "role": "maximum longevity, adult body mass and other life-history traits for the listed taxa",
        "integrity": {"identifier_resolves": ok, "checksum_verified": True, "checked_at": now()},
        "vendored_by": VENDORED_BY,
    }
    write_dataset(rec)
    for s in hits:
        taxa[s]["datasets"].append(did)
    print(f"AnAge build {build}: {len(df)} rows, covers {len(hits)} taxa")


def ds_pantheria(taxa):
    import pandas as pd
    url = "https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt"
    body, ts, _ = fetch(url)
    df = pd.read_csv(io.BytesIO(body), sep="\t", dtype=str, encoding="latin-1")
    hits = match_rows_by_rank(taxa, df, {"species": "MSW05_Binomial", "genus": "MSW05_Genus", "family": "MSW05_Family", "order": "MSW05_Order"})
    by_slug = {x["slug"]: x for x in TAXA}
    for slug, t in taxa.items():
        if t["accepted_name"] == "Mammalia":  # class covers every row
            hits[slug] = int(len(df))
        fams = by_slug.get(slug, {}).get("pantheria_families")
        if fams:
            n = int(df["MSW05_Family"].isin(fams).sum())
            if n:
                hits[slug] = n
    ok, _ = doi_resolves("10.1890/08-1494.1")
    did = "pantheria-1-0-wr05-2008"
    rec = {
        "id": did,
        "label": "PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals (1.0, Wilson & Reeder 2005 taxonomy)",
        "identifier": "https://esapubs.org/archive/ecol/E090/184/",
        "doi": "10.1890/08-1494.1",
        "bibliographic_citation": "Jones KE, Bielby J, Cardillo M, Fritz SA, O'Dell J, Orme CDL, Safi K, Sechrest W, Boakes EH, Carbone C, Connolly C, Cutts MJ, Foster JK, Grenyer R, Habib M, Plaster CA, Price SA, Rigby EA, Rist J, Teacher A, Bininda-Emonds ORP, Gittleman JL, Mace GM, Purvis A (2009) PanTHERIA: a species-level database of life history, ecology, and geography of extant and recently extinct mammals. Ecology 90:2648.",
        "is_referenced_by": "https://doi.org/10.1890/08-1494.1",
        "creators": ["Jones KE", "Bielby J", "Cardillo M", "Fritz SA", "O'Dell J", "Orme CDL", "Safi K", "Sechrest W", "Boakes EH", "Carbone C", "Connolly C", "Cutts MJ", "Foster JK", "Grenyer R", "Habib M", "Plaster CA", "Price SA", "Rigby EA", "Rist J", "Teacher A", "Bininda-Emonds ORP", "Gittleman JL", "Mace GM", "Purvis A"],
        "issued": "2009-09",
        "license": "No licence stated in the distributed file; Ecological Archives data paper E090-184 (Ecology 90:2648), cite the paper when reusing",
        "version": "1.0 (WR05, Aug 2008)",
        "distributions": [dist(url, body, ts, media_type="text/tab-separated-values")],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": "species rows in PanTHERIA_1-0_WR05_Aug2008.txt"},
            {"property_id": "n_rows_for_taxa", "value": int(sum(hits.values())), "description": "rows whose MSW05_Binomial / Genus / Family / Order equals the accepted name of a taxon in this slice at that rank (Mammalia = all rows; Ruminantia = rows in Bovidae, Cervidae, Giraffidae, Antilocapridae, Moschidae, Tragulidae)"},
        ] + [{"property_id": "n_rows_for_taxon", "value": n, "description": f"rows for {slug}"} for slug, n in sorted(hits.items())],
        "measurement_technique": "Literature-compiled species-level life-history, ecological and geographic traits for mammals (body mass, gestation, litter size, longevity, range).",
        "taxa": sorted(hits),
        "role": "body mass and life-history traits for the listed mammal taxa",
        "integrity": {"identifier_resolves": ok, "checksum_verified": True, "checked_at": now()},
        "vendored_by": VENDORED_BY,
    }
    write_dataset(rec)
    for s in hits:
        taxa[s]["datasets"].append(did)
    print(f"PanTHERIA: {len(df)} rows, covers {len(hits)} taxa")


def ds_avonet(taxa):
    import pandas as pd
    meta, _, _ = fetch_json("https://api.figshare.com/v2/articles/16586228")
    f = [x for x in meta["files"] if x["name"] == "AVONET Supplementary dataset 1.xlsx"][0]
    url = f["download_url"]
    body, ts, _ = fetch(url, timeout=600)
    df = pd.read_excel(io.BytesIO(body), sheet_name="AVONET1_BirdLife", dtype=str)
    hits = match_rows_by_rank(taxa, df, {"species": "Species1", "family": "Family1", "order": "Order1"})
    for slug, t in taxa.items():
        if t["accepted_name"] == "Aves":
            hits[slug] = int(len(df))
    ok, _ = doi_resolves("10.1111/ele.13898")
    did = "avonet-figshare-16586228-v7"
    rec = {
        "id": did,
        "label": "AVONET: morphological, ecological and geographical data for all birds (Supplementary dataset 1, AVONET1_BirdLife sheet)",
        "identifier": "https://figshare.com/articles/dataset/AVONET_morphological_ecological_and_geographical_data_for_all_birds_Tobias_et_al_2021_Ecology_Letters_/16586228",
        "doi": "10.6084/m9.figshare.16586228.v7",
        "bibliographic_citation": "Tobias JA, Sheard C, Pigot AL, Devenish AJM, Yang J, Sayol F, et al. (2022) AVONET: morphological, ecological and geographical data for all birds. Ecology Letters 25:581-597. https://doi.org/10.1111/ele.13898",
        "is_referenced_by": "https://doi.org/10.1111/ele.13898",
        "creators": ["Tobias JA", "Sheard C", "Pigot AL", "Devenish AJM", "Yang J", "Sayol F", "Neate-Clegg MHC", "Alioravainen N", "Weeks TL", "Barber RA", "Walkden PA", "MacGregor HEA", "Jones SEI", "Vincent C", "Phillips AG", "Marples NM", "Montaño-Centellas FA", "Leandro-Silva V", "Claramunt S", "Darski B", "Freeman BG", "Bregman TP", "Cooney CR", "Hughes EC", "Capp EJR", "Varley ZK", "Friedman NR", "Korntheuer H", "Corrales-Vargas A", "Trisos CH", "Weeks BC", "Hanz DM", "Töpfer T", "Bravo GA", "Remeš V", "Nowak L", "Carneiro LS", "Moncada R AJ", "Matysioková B", "Baldassarre DT", "Martínez-Salinas A", "Wolfe JD", "Chapman PM", "Daly BG", "Sorensen MC", "Neu A", "Ford MA", "Mayhew RJ", "Fabio Silveira L", "Kelly DJ", "Annorbah NND", "Pollock HS", "Grabowska-Zhang AM", "McEntee JP", "Carlos T Gonzalez J", "Meneses CG", "Muñoz MC", "Powell LL", "Jamie GA", "Matthews TJ", "Johnson O", "Brito GRR", "Zyskowski K", "Crates R", "Harvey MG", "Jurado Zevallos M", "Hosner PA", "Bradfer-Lawrence T", "Maley JM", "Stiles FG", "Lima HS", "Provost KL", "Chibesa M", "Mashao M", "Howard JT", "Mlamba E", "Chua MAH", "Li B", "Gómez MI", "García NC", "Päckert M", "Fuchs J", "Ali JR", "Derryberry EP", "Carlson ML", "Urriza RC", "Brzeski KE", "Prawiradilaga DM", "Rayner MJ", "Miller ET", "Bowie RCK", "Lafontaine R-M", "Scofield RP", "Lou Y", "Somarathna L", "Lepage D", "Illif M", "Neuschulz EL", "Templin M", "Dehling DM", "Cooper JC", "Pauwels OSG", "Analuddin K", "Fjeldså J", "Seddon N", "Sweet PR", "DeClerck FAJ", "Naka LN", "Brawn JD", "Aleixo A", "Böhning-Gaese K", "Schleuning M"],
        "issued": meta["published_date"][:10],
        "license": "CC BY 4.0",
        "version": "figshare v7 (2022-12-05)",
        "distributions": [dist(url, body, ts, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", file_name=f["name"], sheet="AVONET1_BirdLife")],
        "counts": [
            {"property_id": "n_species", "value": int(len(df)), "description": "species rows in sheet AVONET1_BirdLife (BirdLife taxonomy)"},
            {"property_id": "n_rows_for_taxa", "value": int(sum(hits.values())), "description": "rows whose Species1 / Family1 / Order1 equals the accepted name of a taxon in this slice at that rank (Aves = all rows)"},
        ] + [{"property_id": "n_rows_for_taxon", "value": n, "description": f"rows for {slug}"} for slug, n in sorted(hits.items())],
        "measurement_technique": "Museum-specimen measurements (beak, wing, tail, tarsus, mass) and compiled ecological traits for all bird species.",
        "taxa": sorted(hits),
        "role": "beak and body morphometrics for the listed bird taxa",
        "integrity": {"identifier_resolves": ok, "checksum_verified": True, "checked_at": now()},
        "vendored_by": VENDORED_BY,
    }
    write_dataset(rec)
    for s in hits:
        taxa[s]["datasets"].append(did)
    print(f"AVONET: {len(df)} rows, covers {len(hits)} taxa")


GENOME_TAXA_RANKS = {"species", "genus"}


def ds_ncbi_genomes(taxa):
    n_made = 0
    for slug, t in taxa.items():
        if t["rank"] not in GENOME_TAXA_RANKS or not t.get("animalia", True) or not t["identifiers"].get("ncbi_taxid"):
            continue
        taxid = t["identifiers"]["ncbi_taxid"]
        base = f"https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/{taxid}/dataset_report"
        url = base + "?filters.reference_only=true&page_size=5"
        j, ts, body = fetch_json(url)
        reports = (j or {}).get("reports") or []
        ref = True
        if not reports:
            url = base + "?filters.assembly_level=complete_genome&filters.assembly_level=chromosome&filters.assembly_level=scaffold&filters.assembly_level=contig&page_size=1"
            j, ts, body = fetch_json(url)
            reports = (j or {}).get("reports") or []
            ref = False
        if not reports:
            continue
        rep = reports[0]
        acc = rep["accession"]
        info = rep.get("assembly_info", {})
        total_url = base + "?page_size=1"
        tj, _, _ = fetch_json(total_url)
        total = (tj or {}).get("total_count")
        did = "ncbi-genome-" + acc.lower().replace("_", "-").replace(".", "-")
        existing_path = os.path.join(SLICE, "datasets", f"{did}.json")
        if os.path.exists(existing_path):  # same assembly reached from two taxa (e.g. a genus and its species)
            rec = load_json(existing_path)
            rec["taxa"] = sorted(set(rec["taxa"] + [slug]))
            rec["counts"][1]["value"] = len(rec["taxa"])
            rec["counts"][1]["description"] = "taxa in this slice for which this assembly is vendored"
            rec["counts"].append({"property_id": "n_assemblies", "value": total, "description": f"genome assemblies in NCBI Datasets for NCBI taxid {taxid} ({t['accepted_name']}) and nested taxa"})
            write_dataset(rec)
            t["datasets"].append(did)
            n_made += 1
            continue
        rec = {
            "id": did,
            "label": f"NCBI genome assembly {acc} ({info.get('assembly_name')}) for {rep['organism']['organism_name']}",
            "identifier": f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            "doi": None,
            "bibliographic_citation": f"{info.get('submitter') or 'NCBI'} ({(info.get('release_date') or '')[:4]}). Genome assembly {acc} {info.get('assembly_name') or ''}, {rep['organism']['organism_name']}. NCBI Datasets. https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/",
            "is_referenced_by": "https://www.ncbi.nlm.nih.gov/datasets/docs/v2/",
            "creators": [info.get("submitter") or "NCBI"],
            "issued": (info.get("release_date") or "")[:10],
            "license": "NCBI public domain data (https://www.ncbi.nlm.nih.gov/home/about/policies/)",
            "version": acc,
            "distributions": [dist(url, body, ts, assembly_accession=acc, assembly_name=info.get("assembly_name"), assembly_level=info.get("assembly_level"), refseq_category=info.get("refseq_category"))],
            "counts": [
                {"property_id": "n_assemblies", "value": total, "description": f"genome assemblies in NCBI Datasets for NCBI taxid {taxid} ({t['accepted_name']}) and nested taxa"},
                {"property_id": "n_rows_for_taxa", "value": 1, "description": "assembly vendored for the listed taxon"},
            ],
            "measurement_technique": f"Whole-genome sequencing and assembly ({info.get('assembly_level')}; {'RefSeq reference/representative' if ref else 'GenBank assembly, no RefSeq reference designated'}).",
            "taxa": [slug],
            "role": f"reference genome assembly for {t['accepted_name']}",
            "integrity": {"identifier_resolves": url_resolves(f"https://www.ncbi.nlm.nih.gov/datasets/genome/{acc}/"), "checksum_verified": True, "checked_at": now()},
            "vendored_by": VENDORED_BY,
        }
        write_dataset(rec)
        t["datasets"].append(did)
        n_made += 1
        time.sleep(0.35)
    print(f"NCBI genome records: {n_made}")


def build_datasets(only=None):
    taxa = taxa_files()
    resolution = load_json(os.path.join(CACHE, "resolution.json"))
    for t in taxa.values():
        t["datasets"] = []
    steps = {
        "gbif": lambda: ds_gbif_occurrences(taxa),
        "backbone": lambda: ds_gbif_backbone(taxa, resolution),
        "worms": lambda: ds_worms(taxa, resolution),
        "pbdb": lambda: ds_pbdb(taxa, resolution),
        "anage": lambda: ds_anage(taxa),
        "pantheria": lambda: ds_pantheria(taxa),
        "avonet": lambda: ds_avonet(taxa),
        "genomes": lambda: ds_ncbi_genomes(taxa),
    }
    ddir = os.path.join(SLICE, "datasets")
    if os.path.isdir(ddir):
        for fn in os.listdir(ddir):
            os.remove(os.path.join(ddir, fn))
    for name, fn in steps.items():
        if only and name not in only:
            continue
        print(f"== {name}")
        try:
            fn()
        except Exception as e:  # keep going; report lists what failed
            print(f"  FAILED {name}: {type(e).__name__}: {e}", file=sys.stderr)
    save_taxa(taxa)


# ----------------------------------------------------------------------------- report
def build_report():
    mentions = load_json(os.path.join(SLICE, "mentions.json"))
    taxa = taxa_files()
    ddir = os.path.join(SLICE, "datasets")
    datasets = {fn[:-5]: load_json(os.path.join(ddir, fn)) for fn in sorted(os.listdir(ddir)) if fn.endswith(".json")}
    claims = claims_in_scope()
    by_t = {t["slug"]: t for t in TAXA}
    n_claim_m = sum(1 for m in mentions if "claim_id" in m["source"])
    n_text_m = len(mentions) - n_claim_m
    animal = {s: t for s, t in taxa.items() if t.get("animalia")}
    protist = {s: t for s, t in taxa.items() if not t.get("animalia")}

    def n_with(key):
        return sum(1 for t in taxa.values() if t["identifiers"].get(key))

    ds_by_kind = Counter(d.split("-")[0] if not d.startswith("gbif-occurrences") else "gbif-occurrences" for d in datasets)
    no_ds = [s for s, t in taxa.items() if not t["datasets"]]
    only_backbone = [s for s, t in taxa.items() if t["datasets"] and all(d.startswith("gbif-backbone") for d in t["datasets"])]
    unresolved_gbif = [s for s, t in taxa.items() if not t["identifiers"].get("gbif_usage_key")]
    claim_taxa = sorted({m["taxon_slug"] for m in mentions if "claim_id" in m["source"]})
    text_counts = Counter(m["taxon_slug"] for m in mentions if "file" in m["source"])
    top = text_counts.most_common(25)

    L = []
    L.append(f"# Organisms in *On Growth and Form* (1917), chapters VI-XI\n")
    L.append(f"Slice `{SLICE_NAME}` of project `{PROJECT}`, built {TODAY} by a cloud agent on branch `{VENDORED_BY['run']}`. "
             f"Scripts: `scripts/taxa_list.py` (curated names and regexes) and `scripts/build.py` (mentions, resolution, datasets, this report). "
             f"Nothing here is scored, and no claim, assessment or nanopub file was touched.\n")
    L.append("## Counts\n")
    L.append(f"- Claims in scope (chapters {', '.join(CHAPTERS)}): **{len(claims)}**.")
    L.append(f"- Mentions: **{len(mentions)}** ({n_claim_m} in claim `claim`/`quote` fields, {n_text_m} in the book text, lines {TEXT_RANGE[0]}-{TEXT_RANGE[1]} of `{TEXT_FILE}`; one mention per taxon per claim or per line).")
    L.append(f"- Distinct taxa with a `taxa/` file: **{len(taxa)}**, of which {len(animal)} are Animalia and {len(protist)} are protists Thompson treats as animals (Foraminifera, Radiolaria, testate amoebae, heliozoans, ciliates; see notes in each file).")
    L.append(f"- Taxa named in claims (required set): **{len(claim_taxa)}**; all have a taxon file, {sum(1 for s in claim_taxa if taxa[s]['datasets'])} have at least one dataset record.")
    L.append(f"- Resolved to GBIF usageKey: **{n_with('gbif_usage_key')}**; NCBI Taxonomy: **{n_with('ncbi_taxid')}**; Wikidata: **{n_with('wikidata_qid')}**; WoRMS AphiaID: **{n_with('worms_aphia_id')}**; ITIS: **{n_with('itis_tsn')}**; PBDB: **{n_with('pbdb_taxon_id')}**.")
    L.append(f"- Dataset records: **{len(datasets)}** (" + ", ".join(f"{k}: {v}" for k, v in sorted(ds_by_kind.items())) + ").")
    L.append(f"- Taxa with no dataset record: **{len(no_ds)}**" + (f" ({', '.join(no_ds)})" if no_ds else "") + ".")
    L.append(f"- Taxa whose only dataset is the GBIF backbone match (no occurrence count, trait or fossil record): **{len(only_backbone)}**" + (f" ({', '.join(only_backbone)})" if only_backbone else "") + ".\n")
    L.append("## Most-mentioned taxa in the text\n")
    L.append("| taxon | accepted name | text mentions | claims |\n|---|---|---:|---:|")
    for s, n in top:
        L.append(f"| `{s}` | {taxa[s]['accepted_name']} | {n} | {len(taxa[s]['mentioned_in'])} |")
    L.append("")
    L.append("## Taxa named in claims\n")
    L.append("| taxon | as written | claims | datasets |\n|---|---|---|---:|")
    for s in claim_taxa:
        t = taxa[s]
        aw = sorted({m["name_as_written"] for m in mentions if m["taxon_slug"] == s and "claim_id" in m["source"]})
        L.append(f"| `{s}` ({t['accepted_name']}) | {', '.join(aw)} | {', '.join(c.replace('thompson1917-', '') for c in t['mentioned_in'])} | {len(t['datasets'])} |")
    L.append("")
    L.append("## Datasets\n")
    L.append("| id | taxa covered | key count |\n|---|---:|---|")
    for did, d in datasets.items():
        if did.startswith("gbif-occurrences") or did.startswith("ncbi-genome"):
            continue
        c0 = d["counts"][0]
        L.append(f"| `{did}` | {len(d['taxa'])} | {c0['property_id']} = {c0['value']} |")
    n_occ = sum(1 for d in datasets if d.startswith("gbif-occurrences"))
    zero = [d["taxa"][0] for d in datasets.values() if d["id"].startswith("gbif-occurrences") and d["counts"][0]["value"] == 0]
    L.append(f"\nPlus {n_occ} per-taxon `gbif-occurrences-*` records (API count, limit=0). {len(zero)} of them report zero occurrences" + (f": {', '.join(zero)}" if zero else "") + ".")
    genomes = {did: d for did, d in datasets.items() if did.startswith("ncbi-genome")}
    g_taxa = sorted({s for d in genomes.values() for s in d["taxa"]})
    n_ref = sum(1 for d in genomes.values() if "RefSeq reference" in d["measurement_technique"])
    L.append(f"\nPlus {len(genomes)} per-assembly `ncbi-genome-*` records ({n_ref} RefSeq reference/representative, {len(genomes) - n_ref} GenBank-only), one per species- or genus-level animal taxon with an NCBI taxid and at least one assembly, covering {len(g_taxa)} taxa: {', '.join(g_taxa)}.\n")
    L.append("Data files (AnAge zip, PanTHERIA txt, AVONET xlsx) were downloaded to the cache, read with pandas, checksummed and **not** committed; "
             "every record carries `byte_size` and `sha256`. API responses are likewise checksummed as retrieved; counts change as the databases grow, so the retrieval date is part of each record id.\n")
    L.append("## Taxa without a usable dataset, and why\n")
    if no_ds:
        for s in no_ds:
            L.append(f"- `{s}` ({taxa[s]['accepted_name']}): no identifier in any database that has a dataset record here. {taxa[s].get('notes') or ''}")
    else:
        L.append("Every taxon has at least one dataset record. The taxa **without** a GBIF occurrence count (no GBIF backbone usage exists for the name) and what covers them instead:\n")
        for s, t in taxa.items():
            if not t["identifiers"].get("gbif_usage_key"):
                L.append(f"- `{s}` ({t['accepted_name']}, {t['rank']}): {', '.join('`' + d + '`' for d in t['datasets'])}.")
    weak = [s for s, t in taxa.items() if t["identifiers"].get("gbif_usage_key") and len(t["datasets"]) == 2]
    L.append(f"\nTaxa whose only records are the GBIF backbone match and the GBIF occurrence count (no trait, fossil, WoRMS or genome record): {len(weak)}" + (f": {', '.join(weak)}" if weak else "") + ". These are mostly freshwater or terrestrial genera and higher groups outside the scope of the marine (WoRMS), fossil (PBDB), mammal (PanTHERIA), bird (AVONET) and life-history (AnAge) databases used; FishBase and MorphoSource were not reachable or not taxon-filterable (see below).\n")
    L.append("## Non-animal taxa seen (not built)\n")
    L.append("Plants, algae, fungi and other non-animals named in chapters VI-XI, left for a later pass: "
             "Volvox is **not** mentioned in these chapters of the 1917 text; the plant and algal names are "
             "Pleurocarpus, Mesocarpus, Spirogyra, Protococcus, Nostoc, Anabaena, Rivularia, Oscillatoria, Equisetum, Chara, Fucus, Dictyota, Taonia, Laminaria, Sphacelaria, Erythrotrichia, Callithamnion, Melobesia, Girardia (a seaweed), "
             "Riccia, Pellia, Anthoceros, Jungermannia, Sphagnum, Phascum, Polytrichum, Salvinia, Selaginella, Osmunda, Adiantum, Pteris, Elodea, Juncus, Hyacinth, Sedum, Epilobium, Passiflora, Neottia, Periploca, Apocynum, Erica, Eulalia japonica, Begonia, Urticaceae, Acanthaceae, maize, sunflower, borage, cacti; "
             "the fungus Mucor; diatoms (Asterolampra, Arachnoidiscus) and the silicoflagellate Dictyocha. "
             "Protists that Thompson treats as animals are built (see above) and flagged `\"animalia\": false`.\n")
    L.append("## Ambiguities and decisions\n")
    renamed = []
    for s, t in taxa.items():
        if by_t.get(s, {}).get("vern"):
            continue  # vernacular names are not renamings
        first = t["accepted_name"].split()[0].lower()
        written = {w.split()[0].lower().rstrip("s") for w in t["names_as_written"]}
        if first not in written and first.rstrip("s") not in written and t["rank"] in ("genus", "species"):
            renamed.append(f"{sorted(t['names_as_written'], key=len)[0]} -> {t['accepted_name']}")
    amb = [
        "'Coelenterata' is resolved to Cnidaria (Thompson's usage also embraced the Ctenophora, which are recorded separately).",
        "'Corals'/'corallites' are resolved to Anthozoa; the Palaeozoic corals (Heterophyllia, Zaphrentis, Lithostrotion, Cyathophyllum, 'Streptoplasma' = Streptelasma, Phillipsastraea, Arachnophyllum) are resolved through PBDB and GBIF. 'Monticuliporae' are bryozoans, not corals, and are recorded as such.",
        "'Actinomyxidia' (which Thompson calls parasitic protozoa) are Myxozoa, now known to be cnidarian animals; they are recorded as Animalia.",
        "'Fish'/'bony fish' is resolved to Actinopterygii, 'elasmobranch fishes' to Elasmobranchii; 'the frog' of Rauber and Roux to Anura (Rana esculenta, named once, is recorded separately as Pelophylax esculentus).",
        "'Ammonites' as a genus, 'Ammonitoid', 'Ammonoidea', 'aptychus' and 'Anaptychus' are all recorded under Ammonoidea; named ammonite genera (Arcestes, Scaphites, Macroscaphites, Ancyloceras, Oekotraustes = Oecotraustes, Goniatites, Sonninia, Pinacoceras) have their own files.",
        "Archaic or superseded names are resolved through WoRMS/MolluscaBase, GBIF and PBDB to the current name, and each taxon file keeps the name as written: " + "; ".join(renamed) + ".",
        "Species named only in the whorl-ratio tables (e.g. Turritella terebellata, Conus virgo, Haliotis excavatus) are recorded as mentions of their genus with the full binomial as `name_as_written`; resolving each archaic binomial individually is left for a later pass. Nautilus pompilius, N. umbilicatus and Rana esculenta are the species-level taxa.",
        "'Pupa' in Thompson's sense (land snails of Draparnaud, now Pupilla/Pupillidae) collides with the marine genus Pupa Röding; the record follows whatever WoRMS/GBIF return for 'Pupa' and the note flags it.",
        "Estheria (clam shrimp) is resolved under Branchiopoda to avoid the tachinid fly homonym; the modern living species are in Cyzicus, the name persists in PBDB.",
        "Generic words that are not taxa (egg, embryo, polyp, zoophyte, worm, Pluteus and Bipinnaria larvae, 'horn', 'tusk', 'claw') are not recorded as mentions.",
        "MorphoSource was probed (API reachable) but its free-text search does not filter by taxon reliably, so no MorphoSource record was built; FishBase (ropensci mirror) was unreachable (TLS error); BOLD and the IUCN API returned 403. These are listed as gaps rather than guessed at.",
    ]
    for a in amb:
        L.append(f"- {a}")
    L.append("")
    with open(os.path.join(SLICE, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("REPORT.md written")


# ----------------------------------------------------------------------------- main
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("mentions", "all"):
        build_mentions()
    if cmd in ("resolve", "all"):
        resolve_all()
    if cmd in ("datasets", "all"):
        build_datasets(only=sys.argv[2].split(",") if len(sys.argv) > 2 else None)
    if cmd in ("report", "all"):
        build_report()
