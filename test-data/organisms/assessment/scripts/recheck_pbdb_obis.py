#!/usr/bin/env python3
"""Re-check and score the Paleobiology Database (PBDB) and OBIS dataset records.

Batch: every record in test-data/organisms/merged/datasets.json whose id starts with
``pbdb-``, ``paleobiology-database-`` or ``obis-occurrence``.

For each record the script
  * re-fetches every recorded distribution URL (PBDB occs/list, taxa/single, taxa/list;
    OBIS /v3/occurrence?...&size=0, /v3/statistics) and re-reads the count it carries,
  * matches every entry of ``counts[]`` to a distribution (or to a derived lookup) and
    compares recorded vs observed (tolerance: relative <= 0.5 % or absolute <= 5),
  * resolves the queried taxon name or id in the same database (PBDB
    taxa/single?name= plus taxa/list?match_name= for homonyms; OBIS /v3/taxon/<id> and
    /v3/taxon/<name>) and compares it with the taxon the record lists (name, phylum,
    class), flagging homonyms, nomina dubia, synonyms and names not in the database,
  * recomputes SHA-256 of every re-fetched body and compares with the recorded value
    (PBDB bodies embed ``elapsed_time`` so they can never match; this is reported, not
    penalised),
  * re-resolves the record's ``identifier`` (classic PBDB pages answer 403 to scripts; the
    equivalent data-service URL is used as fallback evidence),
  * scores the five rubric dimensions, derives the verdict and writes
    test-data/organisms/assessment/records/pbdb-obis/batch-NN.json.

Requests are rate-limited to <= 3 per second and cached (gitignored) under
test-data/organisms/assessment/scripts/cache/ so the run can be repeated offline.

Usage:
    python3 test-data/organisms/assessment/scripts/recheck_pbdb_obis.py            # full run
    python3 test-data/organisms/assessment/scripts/recheck_pbdb_obis.py --ids pbdb-occurrences-mytilus-2026-10-31
    python3 test-data/organisms/assessment/scripts/recheck_pbdb_obis.py --limit 10 --no-write
    python3 test-data/organisms/assessment/scripts/recheck_pbdb_obis.py --refresh   # ignore cache
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse

import requests

HERE = Path(__file__).resolve().parent
ASSESSMENT = HERE.parent
REPO = ASSESSMENT.parents[2]

DATASETS = REPO / "test-data" / "organisms" / "merged" / "datasets.json"
TAXA = REPO / "test-data" / "organisms" / "merged" / "taxa.json"
SOURCES = {
    "paleobiology-database": ASSESSMENT / "sources" / "paleobiology-database.json",
    "obis": ASSESSMENT / "sources" / "obis.json",
}
OUT_DIR = ASSESSMENT / "records" / "pbdb-obis"
CACHE_DIR = HERE / "cache"

ID_PREFIXES = ("pbdb-", "paleobiology-database-", "obis-occurrence")
USER_AGENT = "delphi-dataset-reliability-assessor/0.1 (+https://github.com/fractastical/delphi)"
MIN_INTERVAL = 1.0 / 3.0  # <= 3 requests per second
TIMEOUT = 60
BATCH_SIZE = 50
MAX_FILE_BYTES = 1_000_000

REL_TOL = 0.005
ABS_TOL = 5

WEIGHTS = {
    "source-authority": 0.2,
    "integrity": 0.25,
    "completeness": 0.2,
    "independence": 0.15,
    "authenticity": 0.2,
}

# DOIs that appear in this batch's records but resolve to documents unrelated to the
# source (verified through doi.org / Crossref / DataCite on 2026-10-31).
BAD_DOIS = {
    "10.25607/OBP-1690": "resolves to a Government of Greenland white paper on seal management (AquaDocs handle 1834/44081), not to OBIS",
    "10.1007/s12549-015-0207-y": "resolves to Simpson et al. 2015, 'Enigmatic spheres from the Upper Triassic Lockatong Formation' (Palaeobiodiversity and Palaeoenvironments), not to a PBDB data paper",
    "10.1017/pab.2015.47": "resolves to Petsios & Bottjer 2016 (Paleobiology), not to Peters & McClennen 2016 (which is 10.1017/pab.2015.39)",
}

# Phylum names that GBIF/Wikidata lineages and PBDB/WoRMS use for the same group.
PHYLUM_ALIASES = {
    "radiozoa": {"radiolaria", "retaria"},
    "radiolaria": {"radiozoa", "retaria"},
    "foraminifera": {"retaria", "granuloreticulosa"},
    "retaria": {"foraminifera", "radiolaria", "radiozoa"},
    "cnidaria": {"coelenterata"},
    "coelenterata": {"cnidaria"},
    "chordata": {"vertebrata", "craniata"},
    "vertebrata": {"chordata"},
    "bryozoa": {"ectoprocta"},
    "ectoprocta": {"bryozoa"},
}

# Class names that differ only by classification scheme between GBIF/Wikidata and PBDB/WoRMS.
CLASS_ALIASES = {
    "actinopterygii": {"osteichthyes", "actinopteri", "teleostei"},
    "actinopteri": {"osteichthyes", "actinopterygii", "teleostei"},
    "teleostei": {"osteichthyes", "actinopterygii", "actinopteri"},
    "osteichthyes": {"actinopterygii", "actinopteri", "sarcopterygii", "teleostei"},
    "sarcopterygii": {"osteichthyes"},
    "elasmobranchii": {"chondrichthyes"},
    "chondrichthyes": {"elasmobranchii"},
    "reptilia": {"sauropsida"},
    "sauropsida": {"reptilia"},
    "aves": {"reptilia", "sauropsida"},
    "anthozoa": {"octocorallia", "hexacorallia"},
    "octocorallia": {"anthozoa"},
    "hexacorallia": {"anthozoa"},
}

PBDB_SHOW_CLASS = "class,size"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- HTTP

class Client:
    """Rate-limited, disk-cached GET client."""

    def __init__(self, cache_dir: Path, refresh: bool = False, min_interval: float = MIN_INTERVAL):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.min_interval = min_interval
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.n_network = 0
        self.n_cached = 0

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".json")

    def get(self, url: str) -> dict:
        path = self._cache_path(url)
        if not self.refresh and path.exists():
            try:
                cached = json.loads(path.read_text("utf-8"))
                if cached.get("url") == url and "status" in cached:
                    self.n_cached += 1
                    return cached
            except (OSError, ValueError):
                pass
        result = self._fetch(url)
        # Cache successful and definitive responses; retry network errors next run.
        if result.get("status") is not None:
            path.write_text(json.dumps(result), "utf-8")
        return result

    def _fetch(self, url: str) -> dict:
        attempts = 3
        delay = 2.0
        last_error = None
        for attempt in range(attempts):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.n_network += 1
            try:
                resp = self.session.get(url, timeout=TIMEOUT, allow_redirects=True)
            except requests.RequestException as exc:  # network problem
                last_error = f"{type(exc).__name__}: {exc}"
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < attempts - 1:
                last_error = f"HTTP {resp.status_code}"
                time.sleep(delay)
                delay *= 2
                continue
            body = resp.content
            return {
                "url": url,
                "final_url": resp.url,
                "status": resp.status_code,
                "content_type": resp.headers.get("Content-Type"),
                "byte_size": len(body),
                "sha256": sha256_hex(body),
                "body": body.decode("utf-8", errors="replace"),
                "fetched_at": now_iso(),
            }
        return {"url": url, "status": None, "error": last_error, "fetched_at": now_iso()}


# --------------------------------------------------------------------------- parsing

def dist_info(url: str) -> dict:
    """Classify a distribution URL and extract the taxon name / id it queries."""
    p = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(p.query, keep_blank_values=True).items()}
    info = {"url": url, "kind": None, "name": None, "id": None, "db": None}
    host = p.netloc.lower()
    if "paleobiodb.org" in host:
        info["db"] = "pbdb"
        if "/occs/list" in p.path:
            info["kind"] = "pbdb-occs-list"
        elif "/occs/diversity" in p.path:
            info["kind"] = "pbdb-occs-diversity"
        elif "/taxa/single" in p.path:
            info["kind"] = "pbdb-taxa-single"
        elif "/taxa/list" in p.path:
            info["kind"] = "pbdb-taxa-list"
        elif "/classic/" in p.path:
            info["kind"] = "pbdb-classic"
        else:
            info["kind"] = "pbdb-other"
        name = q.get("base_name") or q.get("name") or q.get("match_name") or q.get("taxon_name")
        if name:
            info["name"] = unquote_plus(name).strip()
        ident = q.get("base_id") or q.get("id") or q.get("taxon_id") or q.get("taxon_no")
        if ident:
            ids = [re.sub(r"^txn:", "", x) for x in ident.split(",") if x]
            info["id"] = ids[0] if len(ids) == 1 else None
            info["ids"] = ids
    elif "obis.org" in host:
        info["db"] = "obis"
        if p.path.rstrip("/").endswith("/occurrence"):
            info["kind"] = "obis-occurrence"
        elif p.path.rstrip("/").endswith("/statistics"):
            info["kind"] = "obis-statistics"
        elif "/taxon/" in p.path:
            info["kind"] = "obis-taxon"
            info["id"] = p.path.rstrip("/").rsplit("/", 1)[-1]
        else:
            info["kind"] = "obis-other"
        if q.get("taxonid"):
            info["id"] = q["taxonid"]
        if q.get("scientificname"):
            info["name"] = unquote_plus(q["scientificname"])
    return info


def parse_json(body: str | None):
    if body is None:
        return None
    try:
        return json.loads(body)
    except ValueError:
        return None


def observe(kind: str, resp: dict) -> dict:
    """Extract the countable quantities from a re-fetched response."""
    obs = {"status": resp.get("status"), "count": None, "ok": False}
    if resp.get("status") is None:
        obs["error"] = resp.get("error")
        return obs
    j = parse_json(resp.get("body"))
    if j is None:
        obs["error"] = "response is not JSON"
        return obs
    if kind == "pbdb-occs-list":
        obs["count"] = j.get("records_found")
        if j.get("warnings"):
            obs["warnings"] = j["warnings"]
        if j.get("errors"):
            obs["errors"] = j["errors"]
        obs["ok"] = obs["count"] is not None
    elif kind == "pbdb-occs-diversity":
        recs = j.get("records") or []
        obs["count"] = sum((r.get("sampled_in_bin") or r.get("dsb") or 0) for r in recs)
        obs["n_bins"] = len(recs)
        obs["ok"] = bool(recs)
    elif kind in ("pbdb-taxa-single", "pbdb-taxa-list"):
        recs = j.get("records") or []
        if j.get("errors"):
            obs["errors"] = j["errors"]
        if j.get("warnings"):
            obs["warnings"] = j["warnings"]
        obs["n_records"] = len(recs)
        if recs:
            r = recs[0]
            obs["count"] = r.get("noc")
            obs["taxon"] = pbdb_taxon_summary(r)
            obs["n_extinct"] = sum(1 for x in recs if str(x.get("ext")) == "0")
            obs["ok"] = True
        else:
            obs["ok"] = False
    elif kind == "obis-occurrence":
        obs["count"] = j.get("total")
        if j.get("error"):
            obs["error"] = j["error"]
        obs["ok"] = obs["count"] is not None and not j.get("error")
    elif kind == "obis-statistics":
        obs["count"] = j.get("records")
        obs["datasets"] = j.get("datasets")
        obs["species"] = j.get("species")
        if j.get("error"):
            obs["error"] = j["error"]
        obs["ok"] = obs["count"] is not None and not j.get("error")
    else:
        obs["ok"] = 200 <= (resp.get("status") or 0) < 300
    return obs


def pbdb_taxon_summary(r: dict) -> dict:
    return {
        "oid": r.get("oid"),
        "name": r.get("nam"),
        "rank": r.get("rnk"),
        "accepted_oid": r.get("acc"),
        "accepted_name": r.get("acn"),
        "taxonomic_difference": r.get("tdf"),
        "flags": r.get("flg"),
        "extant": r.get("ext"),
        "noc": r.get("noc"),
        "siz": r.get("siz"),
        "exs": r.get("exs"),
        "phylum": r.get("phl"),
        "class": r.get("cll"),
        "order": r.get("odl"),
        "family": r.get("fml"),
    }


# --------------------------------------------------------------------------- taxon resolution

class Resolver:
    def __init__(self, client: Client):
        self.client = client
        self._memo: dict[str, dict] = {}

    def pbdb_by_name(self, name: str) -> dict:
        key = f"pbdb-name:{name.lower()}"
        if key in self._memo:
            return self._memo[key]
        single_url = f"https://paleobiodb.org/data1.2/taxa/single.json?name={requests.utils.quote(name)}&show={PBDB_SHOW_CLASS}"
        single = self.client.get(single_url)
        obs = observe("pbdb-taxa-single", single)
        list_url = f"https://paleobiodb.org/data1.2/taxa/list.json?match_name={requests.utils.quote(name)}&show=class"
        lst = self.client.get(list_url)
        j = parse_json(lst.get("body")) or {}
        homonyms = {}
        for r in j.get("records") or []:
            if (r.get("nam") or "").lower() != name.lower():
                continue
            homonyms.setdefault(r.get("oid"), pbdb_taxon_summary(r))
        out = {
            "query": name,
            "lookup_url": single_url,
            "status": single.get("status"),
            "found": obs.get("ok", False),
            "taxon": obs.get("taxon"),
            "homonyms": list(homonyms.values()),
            "n_homonyms": len(homonyms),
            "warnings": obs.get("warnings"),
        }
        self._memo[key] = out
        return out

    def pbdb_by_id(self, txn: str) -> dict:
        key = f"pbdb-id:{txn}"
        if key in self._memo:
            return self._memo[key]
        url = f"https://paleobiodb.org/data1.2/taxa/single.json?id=txn:{txn}&show={PBDB_SHOW_CLASS}"
        resp = self.client.get(url)
        obs = observe("pbdb-taxa-single", resp)
        out = {
            "query": f"txn:{txn}",
            "lookup_url": url,
            "status": resp.get("status"),
            "found": obs.get("ok", False),
            "taxon": obs.get("taxon"),
            "homonyms": [],
            "n_homonyms": None,
        }
        self._memo[key] = out
        return out

    def obis_by_id(self, aphia: str) -> dict:
        key = f"obis-id:{aphia}"
        if key in self._memo:
            return self._memo[key]
        url = f"https://api.obis.org/v3/taxon/{aphia}"
        resp = self.client.get(url)
        j = parse_json(resp.get("body")) or {}
        res = (j.get("results") or [None])[0]
        out = {
            "query": aphia,
            "lookup_url": url,
            "status": resp.get("status"),
            "found": res is not None,
            "taxon": obis_taxon_summary(res) if res else None,
        }
        self._memo[key] = out
        return out

    def obis_by_name(self, name: str) -> dict:
        key = f"obis-name:{name.lower()}"
        if key in self._memo:
            return self._memo[key]
        url = f"https://api.obis.org/v3/taxon/{requests.utils.quote(name)}"
        resp = self.client.get(url)
        j = parse_json(resp.get("body")) or {}
        results = [obis_taxon_summary(r) for r in (j.get("results") or [])]
        out = {
            "query": name,
            "lookup_url": url,
            "status": resp.get("status"),
            "found": bool(results),
            "matches": results,
            "n_matches": len(results),
        }
        self._memo[key] = out
        return out


def obis_taxon_summary(r: dict) -> dict:
    return {
        "taxonID": r.get("taxonID"),
        "name": r.get("scientificName"),
        "rank": r.get("taxonRank"),
        "status": r.get("taxonomicStatus"),
        "accepted_id": r.get("acceptedNameUsageID"),
        "accepted_name": r.get("acceptedNameUsage"),
        "kingdom": r.get("kingdom"),
        "phylum": r.get("phylum"),
        "class": r.get("class"),
        "is_marine": r.get("is_marine"),
    }


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def expected_taxon(record: dict, info: dict, dist: dict, taxa: dict) -> dict | None:
    """Pick the record taxon that a distribution is about."""
    cands = [taxa[k] for k in record.get("taxa") or [] if k in taxa]
    slug = dist.get("taxon")
    if slug:
        for t in cands:
            if t.get("slug") == slug:
                return t
    name = (info.get("name") or "").lower()
    if name:
        for t in cands:
            if (t.get("accepted_name") or "").lower() == name:
                return t
        for t in cands:
            if slugify(name) == t.get("slug"):
                return t
        for t in cands:
            if any(n.lower() == name for n in t.get("names_as_written") or []):
                return t
    ident = info.get("id")
    if ident:
        for t in cands:
            ids = t.get("identifiers") or {}
            pb = str(ids.get("pbdb_taxon_id") or "").replace("txn:", "")
            if info["db"] == "pbdb" and pb == ident:
                return t
            if info["db"] == "obis" and str(ids.get("worms_aphia_id") or "") == ident:
                return t
    if len(cands) == 1:
        return cands[0]
    return None


def phyla_equal(a: str | None, b: str | None) -> bool | None:
    if not a or not b:
        return None
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    return b in PHYLUM_ALIASES.get(a, set()) or a in PHYLUM_ALIASES.get(b, set())


def classes_equal(a: str | None, b: str | None) -> bool | None:
    if not a or not b:
        return None
    a, b = a.lower(), b.lower()
    if a == b:
        return True
    return b in CLASS_ALIASES.get(a, set()) or a in CLASS_ALIASES.get(b, set())


HIGH_RANKS = {"kingdom", "subkingdom", "infrakingdom", "superphylum", "phylum", "subphylum", "infraphylum", "unranked", "clade", "informal group", "grade (paraphyletic)", "grade (obsolete)", "superclass"}


def clean_rank_value(v: str | None) -> str | None:
    """PBDB uses NO_PHYLUM_SPECIFIED etc. for unplaced taxa; treat those as unknown."""
    if not v or str(v).upper().startswith("NO_"):
        return None
    return v


def lineage_agreement(expected: dict, observed: dict) -> int:
    """Number of lineage levels (phylum, class, order) on which the two agree; -1 on conflict."""
    lineage = expected.get("lineage") or {}
    obs_name = (observed.get("name") or "").lower()
    score = 0
    for level in ("phylum", "class", "order"):
        e = lineage.get(level)
        o = clean_rank_value(observed.get(level))
        if not e or not o:
            continue
        if e.lower() == obs_name:
            # the taxon is itself the expected phylum/class/order
            score += 1
            continue
        if level == "phylum":
            same = phyla_equal(e, o)
        elif level == "class":
            same = classes_equal(e, o)
        else:
            same = e.lower() == o.lower()
        if same:
            score += 1
        else:
            return -1
    return score


def compare_taxon(expected: dict | None, observed: dict | None, homonyms: list[dict] | None = None) -> dict:
    """Compare the record's taxon with what the database returned for the query."""
    out = {"name_match": None, "lineage_match": None, "note": None}
    if not expected or not observed:
        return out
    exp_name = (expected.get("accepted_name") or "").lower()
    exp_rank = (expected.get("rank") or "").lower()
    lineage = expected.get("lineage") or {}
    exp_phylum = lineage.get("phylum")
    exp_class = lineage.get("class")
    obs_names = {(observed.get("name") or "").lower(), (observed.get("accepted_name") or "").lower()} - {""}
    out["name_match"] = exp_name in obs_names if exp_name else None
    obs_phylum = clean_rank_value(observed.get("phylum"))
    obs_class = clean_rank_value(observed.get("class"))
    if homonyms and len(homonyms) > 1:
        # The database picked one of several taxa with this name; check it is the one
        # whose lineage (phylum/class/order) fits the record's taxon best.
        scored = [(lineage_agreement(expected, h), h) for h in homonyms]
        best_score = max(s for s, _ in scored)
        chosen = next((s for s, h in scored if h.get("oid") == observed.get("oid")), None)
        if chosen is not None and chosen < 0 and best_score >= 1:
            best = next(h for s, h in scored if s == best_score)
            out["lineage_match"] = False
            out["note"] = (
                f"'{observed.get('name')}' is a homonym; the query resolved to {observed.get('oid')} "
                f"(phylum {obs_phylum}, class {obs_class}, order {clean_rank_value(observed.get('order'))}) but "
                f"{best.get('oid')} (phylum {clean_rank_value(best.get('phylum'))}, class {clean_rank_value(best.get('class'))}, "
                f"order {clean_rank_value(best.get('order'))}) fits the record's taxon {expected.get('accepted_name')} "
                f"(order {lineage.get('order')})"
            )
            out["wrong_homonym"] = {"resolved": observed.get("oid"), "better": best.get("oid"), "better_noc": best.get("noc")}
            return out
    if exp_name and (observed.get("name") or "").lower() == exp_name and (exp_rank in HIGH_RANKS or exp_phylum is None or exp_phylum.lower() == exp_name):
        out["lineage_match"] = True
    elif exp_phylum and obs_phylum:
        out["lineage_match"] = phyla_equal(exp_phylum, obs_phylum)
        if out["lineage_match"] is False and exp_name and (obs_phylum or "").lower() == exp_name:
            out["lineage_match"] = True
    elif exp_phylum and (observed.get("name") or "").lower() == exp_phylum.lower():
        out["lineage_match"] = True
    elif exp_class and obs_class:
        out["lineage_match"] = classes_equal(exp_class, obs_class)
    if out["lineage_match"] is False:
        out["note"] = (
            f"record taxon {expected.get('accepted_name')} (phylum {exp_phylum}, class {exp_class}) vs database taxon "
            f"{observed.get('name')} (phylum {obs_phylum}, class {obs_class})"
        )
    return out


# --------------------------------------------------------------------------- count matching

AGG_COUNT_PROPS = {"n_rows_for_taxa", "n_taxa_matched", "n_taxa_covered", "n_taxa_resolved", "n_rows", "n_extinct"}
AGG_SUM_PROPS = {"n_occurrences_total", "n_fossil_occurrences_for_taxa"}


def classify_count(c: dict) -> str:
    pid = c.get("property_id") or ""
    desc = (c.get("description") or "").lower()
    if pid in AGG_COUNT_PROPS:
        return "agg-count"
    if pid in AGG_SUM_PROPS or "sum of" in desc:
        return "agg-sum"
    if pid == "n_subtaxa":
        return "siz"
    if pid == "n_extant_subtaxa":
        return "exs"
    if pid in ("n_taxon_occurrences_in_taxonomy_table", "n_occs_taxon_record") or "noc field" in desc or "'noc'" in desc or "n_occs field" in desc:
        return "noc"
    if pid == "n_records" or "datasets)" in desc and "obis" in desc:
        return "count"
    return "count"


def count_text(c: dict) -> str:
    pid = (c.get("property_id") or "").replace("_", " ").replace(":", " ")
    return f"{pid} {c.get('description') or ''}".lower()


def ids_in_text(text: str) -> set[str]:
    ids = set()
    for pat in (r"aphiaid\s*(\d+)", r"txn:(\d+)", r"taxonid=(\d+)", r"taxon_no=(\d+)", r"taxon id (\d+)"):
        ids.update(re.findall(pat, text))
    return ids


def name_in_text(name: str, text: str) -> bool:
    n = name.lower()
    variants = {n, n.replace(" ", "-"), n.replace(" ", "_")}
    return any(re.search(r"(?<![a-z])" + re.escape(v) + r"(?![a-z])", text) for v in variants)


def within_tolerance(recorded, observed) -> tuple[bool | None, float | None]:
    if recorded is None or observed is None:
        return None, None
    try:
        rec = float(recorded)
        obs = float(observed)
    except (TypeError, ValueError):
        return None, None
    diff = abs(obs - rec)
    rel = diff / rec if rec else (0.0 if diff == 0 else None)
    ok = diff <= ABS_TOL or (rel is not None and rel <= REL_TOL)
    return ok, (round(rel, 6) if rel is not None else None)


def match_counts(record: dict, dists: list[dict], lookups: dict[int, dict]) -> list[dict]:
    """Match every counts[] entry to a distribution and compare values."""
    out = []
    single_taxon = len(record.get("taxa") or []) <= 1
    for c in record.get("counts") or []:
        ctype = classify_count(c)
        text = count_text(c)
        entry = {
            "property_id": c.get("property_id"),
            "recorded": c.get("value"),
            "observed": None,
            "relative_diff": None,
            "within_tolerance": None,
            "matched_to": None,
            "match_method": None,
            "kind": ctype,
        }
        # Aggregates over a merged record are restricted to the slice the count came from.
        scope = dists
        scope_note = ""
        if c.get("slice") and any(d.get("slice") for d in dists):
            scoped = [d for d in dists if d.get("slice") == c["slice"]]
            if scoped:
                scope = scoped
                scope_note = f" (restricted to the {len(scoped)} distributions of slice {c['slice']})"
        if ctype == "agg-count":
            desc = (c.get("description") or "").lower()
            if "extinct" in desc:
                vals = [d["observed"].get("n_extinct") for d in scope if d["info"]["kind"] in ("pbdb-taxa-list", "pbdb-taxa-single")]
                entry["observed"] = sum(v for v in vals if v is not None) if vals else None
                entry["match_method"] = "number of returned taxa with ext=0" + scope_note
            elif "at least one" in desc or "with an occurrence" in desc or "with fossil occurrences" in desc:
                entry["observed"] = sum(1 for d in scope if (d["observed"].get("count") or 0) > 0)
                entry["match_method"] = "number of distributions whose observed count > 0" + scope_note
            elif "taxon record" in desc or "returned" in desc or "resolved" in desc or "taxon_no" in desc:
                if any(d["info"]["kind"] == "pbdb-taxa-list" for d in scope):
                    entry["observed"] = sum(d["observed"].get("n_records") or 0 for d in scope if d["info"]["kind"] == "pbdb-taxa-list")
                    entry["match_method"] = "number of taxon records returned by taxa/list" + scope_note
                else:
                    entry["observed"] = sum(1 for d in scope if d["observed"].get("ok"))
                    entry["match_method"] = "number of distributions that resolved to a record" + scope_note
            else:
                entry["observed"] = sum(1 for d in scope if d["observed"].get("count") is not None)
                entry["match_method"] = "number of distributions with an observed count" + scope_note
        elif ctype == "agg-sum":
            desc = (c.get("description") or "")
            use_noc = "noc" in desc.lower()
            kinds = {"pbdb-taxa-single", "pbdb-taxa-list"} if use_noc else {"pbdb-occs-list", "obis-occurrence", "obis-statistics"}
            pool = [d for d in scope if d["info"]["kind"] in kinds]
            if not pool:
                pool = scope
            m = re.search(r"per taxon:\s*(.*)$", desc, flags=re.I)
            if m:
                names = {re.sub(r"[^a-z0-9]+", "-", x.split("=")[0].strip().lower()).strip("-") for x in m.group(1).split(",") if "=" in x}
                pool2 = [d for d in pool if d["info"].get("name") and slugify(d["info"]["name"]) in names]
                if pool2:
                    pool = pool2
                    entry["match_method"] = f"sum over the {len(pool)} per-taxon distributions named in the description"
            vals = [d["observed"].get("count") for d in pool]
            if vals and all(v is not None for v in vals):
                entry["observed"] = sum(vals)
                entry["match_method"] = entry["match_method"] or f"sum of observed counts over {len(pool)} distributions"
            else:
                entry["match_method"] = "sum not computable: some distributions returned no count"
        else:
            wanted_kinds = {
                "count": {"pbdb-occs-list", "obis-occurrence", "obis-statistics", "pbdb-occs-diversity"},
                "noc": {"pbdb-taxa-single", "pbdb-taxa-list"},
                "siz": {"pbdb-taxa-single", "pbdb-taxa-list"},
                "exs": {"pbdb-taxa-single", "pbdb-taxa-list"},
            }[ctype]
            ids = ids_in_text(text)
            cands = [d for d in dists if d["info"].get("id") and d["info"]["id"] in ids]
            method = "taxon id in count description" if cands else None
            if not cands:
                scored = []
                for d in dists:
                    names = {n for n in (d["info"].get("name"), d["info"].get("resolved_name")) if n}
                    hits = [len(n) for n in names if name_in_text(n, text)]
                    if hits:
                        scored.append((max(hits), d))
                if scored:
                    best = max(s for s, _ in scored)
                    cands = [d for s, d in scored if s == best]
                    method = "taxon name in count description"
            if not cands and c.get("slice"):
                cands = [d for d in dists if d.get("slice") == c["slice"]]
                method = "same slice" if cands else None
            if not cands and (single_taxon or len(dists) == 1):
                cands = list(dists)
                method = "single-taxon record"
            if not cands and ctype in ("noc", "siz", "exs"):
                # Taxon-record quantities with no name in the description: the record has a
                # single taxon record (or taxon lookups) to compare with, so use them all and
                # let the closest value win.
                cands = list(dists)
                method = "no name in description; all distributions considered"
            if len(cands) > 1 and c.get("slice"):
                same = [d for d in cands if d.get("slice") == c["slice"]]
                if same:
                    cands = same
            typed = [d for d in cands if d["info"]["kind"] in wanted_kinds]
            if typed:
                field = {"count": "count", "noc": "count", "siz": "siz", "exs": "exs"}[ctype]
                vals = []
                for d in typed:
                    if field == "count":
                        v = d["observed"].get("count")
                    else:
                        v = (d["observed"].get("taxon") or {}).get(field)
                    vals.append((d, v))
                vals_known = [(d, v) for d, v in vals if v is not None]
                if vals_known:
                    if len(vals_known) > 1 and c.get("value") is not None:
                        d, v = min(vals_known, key=lambda dv: abs(float(dv[1]) - float(c["value"])))
                        method = (method or "") + "; closest of several equivalent distributions"
                    else:
                        d, v = vals_known[0]
                    entry["observed"] = v
                    entry["matched_to"] = d["info"]["url"]
                    entry["match_method"] = method
                else:
                    entry["matched_to"] = typed[0]["info"]["url"]
                    entry["match_method"] = (method or "") + "; distribution returned no value"
            elif cands and ctype in ("noc", "siz", "exs"):
                # Derived: no taxa/single distribution in the record, so use the taxon
                # records fetched for the identifier / alternate identifiers and the
                # name lookups (record taxon and queried name); pick the closest.
                field = {"noc": "noc", "siz": "siz", "exs": "exs"}[ctype]
                options = []
                for d in cands:
                    for url, tx in lookups.get(d["idx"]) or []:
                        if tx and tx.get(field) is not None:
                            options.append((url, tx))
                if options:
                    if c.get("value") is not None and len(options) > 1:
                        url, tx = min(options, key=lambda o: abs(float(o[1][field]) - float(c["value"])))
                    else:
                        url, tx = options[0]
                    entry["observed"] = tx[field]
                    entry["matched_to"] = url
                    entry["match_method"] = (method or "") + f"; derived from taxon record {tx.get('oid')} {tx.get('name')} ({field})"
                else:
                    entry["match_method"] = (method or "") + "; no taxon record to derive from"
            elif cands and ctype == "count":
                d = cands[0]
                tx = d["observed"].get("taxon") or {}
                if tx.get("noc") is not None:
                    entry["observed"] = tx["noc"]
                    entry["matched_to"] = d["info"]["url"]
                    entry["match_method"] = (method or "") + "; compared with noc of the taxon record"
                else:
                    entry["match_method"] = (method or "") + "; no countable distribution"
            else:
                entry["match_method"] = "no distribution matched this count"
        ok, rel = within_tolerance(entry["recorded"], entry["observed"])
        entry["within_tolerance"] = ok
        entry["relative_diff"] = rel
        out.append(entry)
    return out


def check_coverage_fields(record: dict, dists: list[dict]) -> dict | None:
    """Cross-check per-taxon occurrence counts stored in taxon_coverage / taxa_coverage."""
    cov = record.get("taxon_coverage") or record.get("taxa_coverage")
    if not isinstance(cov, dict):
        return None
    by_slug = {}
    for d in dists:
        slug = d.get("taxon") or (slugify(d["info"]["name"]) if d["info"].get("name") else None)
        if slug:
            by_slug.setdefault(slug, d)
    n = within = drifted = unmatched = 0
    worst = None
    for slug, val in cov.items():
        if isinstance(val, dict):
            val = val.get("n_occurrences") or val.get("noc")
        if not isinstance(val, (int, float)):
            continue
        d = by_slug.get(slug)
        if not d:
            unmatched += 1
            continue
        tx = d["observed"].get("taxon") or {}
        obs = tx.get("noc") if tx else d["observed"].get("count")
        if obs is None:
            unmatched += 1
            continue
        n += 1
        ok, rel = within_tolerance(val, obs)
        if ok:
            within += 1
        else:
            drifted += 1
            if worst is None or (rel or 0) > (worst.get("relative_diff") or 0):
                worst = {"taxon": slug, "recorded": val, "observed": obs, "relative_diff": rel}
    return {"n_compared": n, "n_within_tolerance": within, "n_drifted": drifted, "n_unmatched": unmatched, "worst": worst}


# --------------------------------------------------------------------------- identifier check

def check_identifier(record: dict, client: Client, resolver: Resolver) -> dict:
    ident = record.get("identifier")
    out = {"identifier": ident, "status": None, "resolves": None, "note": None}
    if not ident:
        out["note"] = "no identifier"
        return out
    info = dist_info(ident)
    resp = client.get(ident)
    out["status"] = resp.get("status")
    if info["kind"] == "pbdb-classic":
        txn = None
        m = re.search(r"taxon_no=(\d+)", ident)
        if m:
            txn = m.group(1)
            lk = resolver.pbdb_by_id(txn)
        else:
            m = re.search(r"taxon_name=([^&]+)", ident)
            lk = resolver.pbdb_by_name(unquote_plus(m.group(1))) if m else {}
        out["resolves"] = bool(lk.get("found"))
        out["fallback_url"] = lk.get("lookup_url")
        if resp.get("status") == 403:
            out["note"] = "classic PBDB page answers HTTP 403 to non-browser clients; existence verified through the data service"
        if lk.get("taxon"):
            out["resolves_to"] = lk["taxon"].get("name")
    elif info["kind"] == "obis-taxon" and info.get("id"):
        lk = resolver.obis_by_id(info["id"])
        out["resolves"] = bool(lk.get("found"))
        out["fallback_url"] = lk.get("lookup_url")
        out["note"] = "obis.org/taxon pages are a single-page app that returns 200 for any id; existence verified through api.obis.org/v3/taxon"
        if lk.get("taxon"):
            out["resolves_to"] = lk["taxon"].get("name")
    elif info["kind"] in ("pbdb-taxa-single", "pbdb-taxa-list"):
        obs = observe("pbdb-taxa-single", resp)
        out["resolves"] = bool(obs.get("ok"))
        if obs.get("taxon"):
            out["resolves_to"] = obs["taxon"].get("name")
    else:
        out["resolves"] = resp.get("status") is not None and 200 <= resp["status"] < 400
    return out


# --------------------------------------------------------------------------- scoring

def clamp(x: float) -> float:
    return max(0.0, min(1.0, round(x, 2)))


def weighted_overall(scores: dict) -> float:
    return round(sum(scores[k] * WEIGHTS[k] for k in WEIGHTS), 4)


def verdict_for(scores: dict, identifier_exists: bool) -> str:
    overall = weighted_overall(scores)
    integ, comp, auth = scores["integrity"], scores["completeness"], scores["authenticity"]
    if auth < 0.5 or not identifier_exists:
        return "reject"
    if overall >= 0.8 and integ >= 0.7 and auth >= 0.8:
        return "reliable"
    if integ < 0.5 or comp < 0.4:
        return "needs-repair"
    if overall >= 0.55:
        return "usable-with-caveats"
    return "needs-repair"


def assess_record(record: dict, taxa: dict, sources: dict, client: Client, resolver: Resolver) -> dict:
    is_obis = record["id"].startswith("obis-")
    source_id = "obis" if is_obis else "paleobiology-database"
    src = sources[source_id]
    checked_at = now_iso()
    obstacles: list[str] = []
    notes: list[str] = []

    # 1. Re-fetch distributions.
    dists = []
    for idx, d in enumerate(record.get("distributions") or []):
        info = dist_info(d["download_url"])
        resp = client.get(d["download_url"])
        obs = observe(info["kind"], resp)
        sha_match = None
        if d.get("sha256") and resp.get("sha256"):
            sha_match = d["sha256"].lower() == resp["sha256"]
        dists.append({
            "idx": idx,
            "info": info,
            "recorded": d,
            "resp": resp,
            "observed": obs,
            "sha_match": sha_match,
            "taxon": d.get("taxon"),
            "slice": d.get("slice"),
        })

    # 1b. Taxon records named as identifier / alternate identifiers (PBDB only).
    aux_taxa: list[tuple[str, dict]] = []
    if not is_obis:
        for url in [record.get("identifier")] + list(record.get("alternate_identifiers") or []):
            if not url:
                continue
            ainfo = dist_info(url)
            if ainfo["kind"] == "pbdb-taxa-single" and ainfo.get("id"):
                lk = resolver.pbdb_by_id(ainfo["id"])
                if lk.get("taxon"):
                    aux_taxa.append((lk["lookup_url"], lk["taxon"]))

    # 2. Resolve taxa per distribution.
    lookups: dict[int, list[tuple[str, dict]]] = {}
    taxon_checks = []
    for d in dists:
        info = d["info"]
        exp = expected_taxon(record, info, d["recorded"], taxa)
        lk = None
        observed_taxon = None
        record_taxon_lookup = None
        if info["db"] == "pbdb":
            if info.get("name"):
                lk = resolver.pbdb_by_name(info["name"])
            elif info.get("id"):
                lk = resolver.pbdb_by_id(info["id"])
            if lk:
                observed_taxon = lk.get("taxon")
            if observed_taxon is None and d["observed"].get("taxon") and len(info.get("ids") or []) <= 1:
                observed_taxon = d["observed"]["taxon"]
            derived = list(aux_taxa)
            if lk and lk.get("taxon"):
                derived.append((lk["lookup_url"], lk["taxon"]))
            if exp and exp.get("accepted_name") and info.get("name") and exp["accepted_name"].lower() != info["name"].lower():
                record_taxon_lookup = resolver.pbdb_by_name(exp["accepted_name"])
                if record_taxon_lookup.get("taxon"):
                    derived.append((record_taxon_lookup["lookup_url"], record_taxon_lookup["taxon"]))
            lookups[d["idx"]] = derived
        elif info["db"] == "obis" and info.get("id"):
            lk = resolver.obis_by_id(info["id"])
            observed_taxon = lk.get("taxon")
            if exp and exp.get("accepted_name"):
                by_name = resolver.obis_by_name(exp["accepted_name"])
                lk = dict(lk)
                lk["name_lookup"] = {
                    "query": exp["accepted_name"],
                    "n_matches": by_name.get("n_matches"),
                    "ids": [m.get("taxonID") for m in by_name.get("matches") or []],
                    "recorded_id_among_matches": any(str(m.get("taxonID")) == str(info["id"]) for m in by_name.get("matches") or []),
                }
        if observed_taxon and observed_taxon.get("name"):
            info["resolved_name"] = observed_taxon["name"]
        cmp = compare_taxon(exp, observed_taxon, (lk or {}).get("homonyms"))
        multi_id = info["kind"] == "pbdb-taxa-list" and len(info.get("ids") or []) > 1
        tc = {
            "distribution": info["url"],
            "queried": info.get("name") or (f"{len(info['ids'])} taxon ids" if multi_id else (f"txn:{info['id']}" if info["db"] == "pbdb" and info.get("id") else info.get("id"))),
            "expected_taxon": exp.get("accepted_name") if exp else None,
            "expected_key": exp.get("key") if exp else None,
            "found": (d["observed"].get("ok") if multi_id else (lk.get("found") if lk else None)),
            "resolved_name": observed_taxon.get("name") if observed_taxon else None,
            "resolved_id": (observed_taxon.get("oid") or observed_taxon.get("taxonID")) if observed_taxon else None,
            "resolved_phylum": observed_taxon.get("phylum") if observed_taxon else None,
            "name_match": cmp["name_match"],
            "lineage_match": cmp["lineage_match"],
        }
        if observed_taxon:
            if observed_taxon.get("taxonomic_difference"):
                tc["taxonomic_difference"] = observed_taxon["taxonomic_difference"]
                tc["accepted_name"] = observed_taxon.get("accepted_name")
            if observed_taxon.get("status") and observed_taxon.get("status") != "accepted":
                tc["taxonomic_status"] = observed_taxon["status"]
                tc["accepted_name"] = observed_taxon.get("accepted_name")
        if lk and lk.get("n_homonyms"):
            tc["n_homonyms_in_pbdb"] = lk["n_homonyms"]
            if lk["n_homonyms"] > 1:
                tc["homonyms"] = [
                    {"oid": h.get("oid"), "rank": h.get("rank"), "phylum": h.get("phylum"), "class": h.get("class"), "noc": h.get("noc")}
                    for h in lk["homonyms"]
                ]
        if lk and lk.get("name_lookup"):
            tc["obis_name_lookup"] = lk["name_lookup"]
        if cmp["note"]:
            tc["note"] = cmp["note"]
        if cmp.get("wrong_homonym"):
            tc["wrong_homonym"] = cmp["wrong_homonym"]
        if exp and info.get("name") and (exp.get("accepted_name") or "").lower() != info["name"].lower():
            tc["query_differs_from_taxon"] = True
            if record_taxon_lookup is not None:
                rt = record_taxon_lookup.get("taxon") or {}
                tc["record_taxon_in_pbdb"] = {
                    "query": record_taxon_lookup.get("query"),
                    "found": record_taxon_lookup.get("found"),
                    "oid": rt.get("oid"),
                    "taxonomic_difference": rt.get("taxonomic_difference"),
                    "accepted_name": rt.get("accepted_name"),
                    "noc": rt.get("noc"),
                }
        if d["observed"].get("warnings"):
            tc["warnings"] = d["observed"]["warnings"]
        taxon_checks.append(tc)

    # 3. Count comparisons.
    count_rechecks = match_counts(record, dists, lookups)
    coverage = check_coverage_fields(record, dists)

    # 4. Identifier.
    ident = check_identifier(record, client, resolver)

    # ---- Derived facts
    n_dist = len(dists)
    n_fetched = sum(1 for d in dists if d["resp"].get("status") is not None)
    n_http_ok = sum(1 for d in dists if d["resp"].get("status") == 200)
    n_counted = sum(1 for d in dists if d["observed"].get("count") is not None)
    comparable = [c for c in count_rechecks if c["within_tolerance"] is not None]
    n_within = sum(1 for c in comparable if c["within_tolerance"])
    drifted = [c for c in comparable if not c["within_tolerance"]]
    unmatched = [c for c in count_rechecks if c["within_tolerance"] is None]
    material = [c for c in drifted if (c["relative_diff"] is None or c["relative_diff"] > 0.10) or (c["observed"] == 0 and (c["recorded"] or 0) > 0)]
    worst_rel = max((c["relative_diff"] or 0) for c in drifted) if drifted else 0.0

    sha_pairs = [d for d in dists if d["sha_match"] is not None]
    sha_ok = sum(1 for d in sha_pairs if d["sha_match"])
    pbdb = source_id == "paleobiology-database"
    checksum_match: bool | None
    if not sha_pairs:
        checksum_match = None
    elif pbdb:
        checksum_match = None
        obstacles.append("PBDB JSON responses embed an elapsed_time field, so the recorded SHA-256 values cannot be reproduced; counts were compared instead.")
    else:
        checksum_match = sha_ok == len(sha_pairs)
    unexplained_sha = []
    if not pbdb:
        for d in dists:
            if d["sha_match"] is False:
                rec_count = None
                for c in count_rechecks:
                    if c.get("matched_to") == d["info"]["url"]:
                        rec_count = c
                        break
                if rec_count and rec_count["observed"] == rec_count["recorded"]:
                    unexplained_sha.append(d["info"]["url"])
    size_consistent = None
    if pbdb and dists:
        diffs = [abs((d["recorded"].get("byte_size") or 0) - (d["resp"].get("byte_size") or 0)) for d in dists if d["recorded"].get("byte_size") and d["resp"].get("byte_size")]
        if diffs:
            size_consistent = all(x <= 12 for x in diffs)

    lineage_mismatch = [t for t in taxon_checks if t["lineage_match"] is False]
    # Severity: the queried name resolves to an organism with a different name (the record's
    # taxon is simply not what was counted) is worse than a same-name homonym picked by the
    # database; and one bad name among many distributions is less damaging than the only one.
    mismatch_other_name = [t for t in lineage_mismatch if t.get("name_match") is False]
    mismatch_minor = bool(lineage_mismatch) and len(lineage_mismatch) <= max(1, 0.1 * n_dist) and n_dist >= 10
    not_found = [t for t in taxon_checks if t["found"] is False]
    name_warn = [t for t in taxon_checks if t.get("warnings")]
    invalid = [t for t in taxon_checks if t.get("taxonomic_difference") and any(k in t["taxonomic_difference"] for k in ("nomen", "invalid", "misspelling"))]
    synonyms = [t for t in taxon_checks if t.get("taxonomic_difference") and t not in invalid]
    unaccepted_obis = [t for t in taxon_checks if t.get("taxonomic_status")]
    homonymous = [t for t in taxon_checks if (t.get("n_homonyms_in_pbdb") or 0) > 1]
    query_differs = [t for t in taxon_checks if t.get("query_differs_from_taxon") and t["lineage_match"] is not False]
    zero_counts = [d for d in dists if d["observed"].get("count") == 0 and d["info"]["kind"] in ("pbdb-occs-list", "obis-occurrence", "obis-statistics")]

    bad_dois = []
    for field in ("doi", "is_referenced_by"):
        v = record.get(field)
        if not v:
            continue
        for doi, why in BAD_DOIS.items():
            if doi.lower() in str(v).lower():
                bad_dois.append({"field": field, "value": v, "problem": why})

    # ---- Scores
    scores = {
        "source-authority": src["scores"]["source-authority"],
        "independence": src["scores"]["independence"],
        "authenticity": src["scores"]["authenticity"],
    }

    # Integrity
    if n_fetched == 0:
        integrity = 0.3
        obstacles.append("No distribution could be fetched (network failure); integrity capped at 0.5 per the spec.")
    elif not comparable:
        integrity = 0.5
        obstacles.append("No recorded count could be matched to a re-queried value; integrity capped at 0.5.")
    else:
        frac_ok = n_within / len(comparable)
        if not drifted:
            integrity = 1.0
        elif material:
            integrity = round(0.4 * frac_ok, 2)
        else:
            integrity = round(0.5 + 0.45 * frac_ok, 2)
    if unexplained_sha:
        integrity = min(integrity, 0.5)
        obstacles.append(f"{len(unexplained_sha)} OBIS response(s) changed checksum although the count is unchanged; see checks.")
    if ident["resolves"] is False and ident["status"] not in (403,):
        integrity = min(integrity, 0.2)
    integrity = clamp(integrity)

    # Completeness
    completeness = 1.0
    for f in ("license", "creators", "bibliographic_citation", "measurement_technique", "role"):
        if not record.get(f):
            completeness -= 0.15
            notes.append(f"field {f} missing")
    if not record.get("counts"):
        completeness -= 0.4
    if not record.get("taxa"):
        completeness -= 0.2
    version = str(record.get("version") or "")
    cite = str(record.get("bibliographic_citation") or "")
    if not re.search(r"data\s*(service)?\s*1\.2|api|v3|data1\.2", version + " " + cite, flags=re.I):
        completeness -= 0.1
        notes.append("version is a date only; the API version is not stated")
    if unmatched:
        frac = len(unmatched) / len(count_rechecks)
        completeness -= 0.3 if frac > 0.5 else 0.15
        notes.append(f"{len(unmatched)} of {len(count_rechecks)} counts could not be matched to a distribution for cross-checking")
    if any(not d["recorded"].get("sha256") for d in dists):
        completeness -= 0.1
        notes.append("some distributions have no sha256/byte_size")
    if lineage_mismatch:
        if mismatch_minor:
            completeness = min(completeness, 0.6)
        elif mismatch_other_name:
            completeness = min(completeness, 0.3)
        else:
            completeness = min(completeness, 0.35)
    if query_differs:
        label = (record.get("label") or "").lower()
        mentioned = all(name_in_text(t["queried"], label) for t in query_differs if t.get("queried"))
        completeness -= 0.1 if mentioned else 0.3
        notes.append("the queried name differs from the record's taxon" + (" (stated in the label)" if mentioned else " and the label does not say so"))
    if n_dist:
        frac_zero = len(zero_counts) / max(1, sum(1 for d in dists if d["info"]["kind"] in ("pbdb-occs-list", "obis-occurrence", "obis-statistics")) or 1)
        if frac_zero > 0:
            completeness -= 0.3 * frac_zero
            notes.append(f"{len(zero_counts)} count query(ies) return 0: the taxon is not present in the database")
        frac_nf = (len(not_found) + len(name_warn)) / n_dist
        if frac_nf > 0:
            completeness -= 0.3 * frac_nf
    if invalid:
        completeness -= 0.1
    completeness = clamp(completeness)

    # Authenticity
    authenticity = scores["authenticity"]
    if bad_dois:
        authenticity = min(authenticity, 0.5)
    if lineage_mismatch:
        authenticity = min(authenticity, 0.5 if (mismatch_other_name and not mismatch_minor) else 0.7)
    if ident["status"] == 404 or (ident["resolves"] is False and ident["status"] not in (403, None)):
        authenticity = min(authenticity, 0.0)
    if material and len(material) == len(comparable) and comparable:
        authenticity = min(authenticity, 0.6)
    authenticity = clamp(authenticity)

    scores["integrity"] = integrity
    scores["completeness"] = completeness
    scores["authenticity"] = authenticity
    identifier_exists = ident["resolves"] is not False or ident["status"] == 403 or any(d["observed"].get("ok") for d in dists)
    verdict = verdict_for(scores, identifier_exists)

    confidence = 0.9
    if unmatched:
        confidence -= 0.1
    if n_fetched < n_dist:
        confidence -= 0.2
    if any(t["lineage_match"] is None for t in taxon_checks):
        confidence -= 0.05
    confidence = clamp(confidence)

    # ---- Obstacles
    db_label = "OBIS" if is_obis else "PBDB"
    obstacles.append(f"{db_label} counts are live and drift as records are added or re-identified; no snapshot identifier exists for a count query.")
    if ident.get("note"):
        obstacles.append(ident["note"] + ".")
    for b in bad_dois:
        obstacles.append(f"{b['field']} {b['value']} {b['problem']}.")
    for t in lineage_mismatch:
        if t.get("wrong_homonym"):
            obstacles.append(f"Wrong homonym: {t['note']}; the recorded count is therefore for a different organism.")
        else:
            obstacles.append(f"Homonym/mismatch: '{t['queried']}' resolves in {db_label} to {t['resolved_name']} ({t['resolved_id']}, phylum {t['resolved_phylum']}), not to the record's taxon {t['expected_taxon']} ({t['note']}).")
    for t in homonymous:
        if t not in lineage_mismatch:
            msg = f"'{t['queried']}' is a homonym in PBDB ({t['n_homonyms_in_pbdb']} taxa share the name); the query resolved to {t['resolved_id']} (phylum {t['resolved_phylum']}), consistent with the record's taxon."
            # A base_name occurrence query matching several taxa counts all of them.
            d = next((x for x in dists if x["info"]["url"] == t["distribution"]), None)
            if d and d["info"]["kind"] == "pbdb-occs-list" and d["observed"].get("count") is not None:
                nocs = [h.get("noc") for h in t.get("homonyms") or []]
                if all(isinstance(n, int) for n in nocs) and len(nocs) > 1 and d["observed"]["count"] == sum(nocs):
                    msg += f" The base_name count ({d['observed']['count']}) equals the sum of the homonyms' occurrence counts ({' + '.join(str(n) for n in nocs)}), i.e. it includes every taxon with this name."
            obstacles.append(msg)
    for t in lineage_mismatch:
        if t.get("name_match") is True and not t.get("wrong_homonym"):
            obstacles.append(f"The record's taxon key {t.get('expected_key')} is a different organism with the same name as the {db_label} taxon actually counted; the dataset describes the {db_label} taxon, so the taxon link (not the count) needs repair.")
    for t in invalid + synonyms:
        obstacles.append(f"'{t['queried']}' is '{t['taxonomic_difference']}' {t.get('accepted_name') or ''} in PBDB; base_name counts are those of the accepted taxon.".replace("  ", " "))
    for t in taxon_checks:
        rt = t.get("record_taxon_in_pbdb")
        if rt and rt.get("taxonomic_difference"):
            obstacles.append(f"The record's taxon {rt['query']} is '{rt['taxonomic_difference']}' {rt.get('accepted_name') or ''} in PBDB ({rt.get('oid')}, noc {rt.get('noc')}); the counts are for {t['queried']}.".replace("  ", " "))
        elif rt and rt.get("found") is False:
            obstacles.append(f"The record's taxon {rt['query']} has no PBDB taxon record; the counts are for {t['queried']}.")
    for t in unaccepted_obis:
        obstacles.append(f"AphiaID {t['queried']} has WoRMS status '{t['taxonomic_status']}' (accepted: {t.get('accepted_name')}).")
    for t in not_found + name_warn:
        obstacles.append(f"'{t['queried']}' is not in the {db_label} taxonomy (query returns no taxon record).")
    if material:
        obstacles.append(f"{len(material)} count(s) disagree materially with the live value (worst relative difference {worst_rel:.3f}).")
    elif drifted:
        obstacles.append(f"{len(drifted)} of {len(comparable)} counts drifted beyond tolerance (worst relative difference {worst_rel:.4f}), consistent with new records indexed since 2026-10-31.")
    # de-duplicate while keeping order
    seen = set()
    obstacles = [o for o in obstacles if not (o in seen or seen.add(o))]

    # ---- Rationale
    kinds = sorted({d["info"]["kind"] for d in dists})
    parts = []
    parts.append(
        f"Re-fetched {n_fetched} of {n_dist} recorded {db_label} distribution(s) ({', '.join(kinds)}) on {checked_at[:10]}; "
        f"{n_within} of {len(comparable)} recorded counts match the live value within tolerance"
        + (f", {len(drifted)} drifted (worst relative difference {worst_rel:.4f})" if drifted else "")
        + (f", {len(unmatched)} could not be cross-checked" if unmatched else "")
        + "."
    )
    if taxon_checks:
        resolved = [t for t in taxon_checks if t["found"]]
        consistent = [t for t in resolved if t["lineage_match"] is True or (t["name_match"] is True and t["lineage_match"] is None)]
        s = f"{len(resolved)} of {len(taxon_checks)} queried name(s)/id(s) resolve in {db_label}"
        if consistent:
            s += f", {len(consistent)} verifiably to the record's taxon (name or phylum/class agree)"
        if lineage_mismatch:
            s += f"; {len(lineage_mismatch)} resolve to a different organism ({'; '.join(t['queried'] + ' -> ' + str(t['resolved_name']) for t in lineage_mismatch)})"
        if homonymous and not lineage_mismatch:
            s += f"; {len(homonymous)} name(s) are PBDB homonyms but the resolved taxon is the right one"
        if not_found or name_warn:
            s += f"; {len(not_found) + len(name_warn)} name(s) are absent from the {db_label} taxonomy"
        parts.append(s + ".")
    if pbdb:
        parts.append("PBDB checksums are unreproducible by construction (elapsed_time in every response)" + (", but recorded byte sizes are consistent with the live responses" if size_consistent else "") + ".")
    elif sha_pairs:
        parts.append(f"{sha_ok} of {len(sha_pairs)} recorded SHA-256 values match the re-fetched OBIS bodies" + ("; every mismatch coincides with a changed count" if sha_ok < len(sha_pairs) and not unexplained_sha else "") + ".")
    if ident["resolves"]:
        parts.append(f"The identifier resolves" + (f" (via {ident.get('fallback_url')})" if ident.get("fallback_url") else "") + ".")
    elif ident["resolves"] is False:
        parts.append(f"The identifier does not resolve (HTTP {ident['status']}).")
    if bad_dois:
        parts.append("The record cites a DOI that resolves to an unrelated document, so authenticity is capped at 0.5.")
    if zero_counts:
        parts.append(f"{len(zero_counts)} query(ies) return 0 records, so the taxon is not actually present in the database.")
    parts.append(f"Source authority, independence and authenticity are inherited from sources/{source_id}.json" + (" with the per-record caps noted." if (bad_dois or lineage_mismatch) else "."))
    rationale = " ".join(parts)

    count_summary = None
    if len(count_rechecks) == 1:
        c = count_rechecks[0]
        count_summary = {"recorded": c["recorded"], "observed": c["observed"], "relative_diff": c["relative_diff"], "within_tolerance": c["within_tolerance"]}

    checks = {
        "checked_at": checked_at,
        "identifier_resolves": ident["resolves"],
        "identifier_http_status": ident["status"],
        "identifier_fallback_url": ident.get("fallback_url"),
        "checksum_match": checksum_match,
        "checksums_compared": len(sha_pairs),
        "checksums_matching": sha_ok if sha_pairs else None,
        "byte_sizes_consistent": size_consistent,
        "distributions_total": n_dist,
        "distributions_fetched": n_fetched,
        "distributions_http_200": n_http_ok,
        "distributions_with_count": n_counted,
        "count_recheck": count_summary if count_summary else {
            "n_counts": len(count_rechecks),
            "n_compared": len(comparable),
            "n_within_tolerance": n_within,
            "n_drifted": len(drifted),
            "n_material": len(material),
            "n_unmatched": len(unmatched),
            "worst_relative_diff": round(worst_rel, 6) if drifted else 0.0,
        },
        "count_rechecks": count_rechecks,
        "taxon_key_resolves_to": (taxon_checks[0]["resolved_name"] if len(taxon_checks) == 1 else None),
        "taxon_checks": taxon_checks,
        "coverage_field_check": coverage,
        "bad_dois": bad_dois or None,
        "distributions": [
            {
                "url": d["info"]["url"],
                "http_status": d["resp"].get("status"),
                "observed_count": d["observed"].get("count"),
                "sha256_match": d["sha_match"],
                "observed_byte_size": d["resp"].get("byte_size"),
                "recorded_byte_size": d["recorded"].get("byte_size"),
            }
            for d in dists
        ],
    }

    return {
        "dataset_id": record["id"],
        "source_id": source_id,
        "scores": {k: scores[k] for k in ("source-authority", "integrity", "completeness", "independence", "authenticity")},
        "overall": round(weighted_overall(scores), 3),
        "verdict": verdict,
        "confidence": confidence,
        "checks": checks,
        "obstacles": obstacles,
        "rationale": rationale,
        "assessor": {"kind": "cloud-agent", "script": "test-data/organisms/assessment/scripts/recheck_pbdb_obis.py", "rubric": "dataset-reliability/0.1.0"},
    }


# --------------------------------------------------------------------------- main

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_batches(results: list[dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("batch-*.json"):
        old.unlink()
    paths = []
    batch: list[dict] = []
    n = 1

    def flush():
        nonlocal batch, n
        if not batch:
            return
        p = out_dir / f"batch-{n:02d}.json"
        p.write_text(json.dumps(batch, indent=1, ensure_ascii=False) + "\n", "utf-8")
        paths.append(p)
        n += 1
        batch = []

    for r in results:
        batch.append(r)
        size = len(json.dumps(batch, indent=1, ensure_ascii=False))
        if len(batch) >= BATCH_SIZE or size > MAX_FILE_BYTES * 0.8:
            flush()
    flush()
    for p in paths:
        if p.stat().st_size > MAX_FILE_BYTES:
            raise SystemExit(f"{p} exceeds 1 MB; lower BATCH_SIZE")
    return paths


def summarise(results: list[dict]) -> dict:
    verdicts: dict[str, int] = {}
    for r in results:
        verdicts[r["verdict"]] = verdicts.get(r["verdict"], 0) + 1
    drift = []
    for r in results:
        for c in r["checks"]["count_rechecks"]:
            if c["within_tolerance"] is False:
                drift.append({"dataset_id": r["dataset_id"], "property_id": c["property_id"], "recorded": c["recorded"], "observed": c["observed"], "relative_diff": c["relative_diff"]})
    drift.sort(key=lambda x: -(x["relative_diff"] if x["relative_diff"] is not None else 9e9))
    homonyms = []
    for r in results:
        for t in r["checks"]["taxon_checks"]:
            if t.get("lineage_match") is False or (t.get("n_homonyms_in_pbdb") or 0) > 1 or t.get("taxonomic_difference") or t.get("taxonomic_status") or t.get("found") is False or t.get("warnings"):
                homonyms.append({"dataset_id": r["dataset_id"], "queried": t["queried"], "expected": t["expected_taxon"], "resolved": t["resolved_name"], "resolved_id": t["resolved_id"], "phylum": t["resolved_phylum"], "lineage_match": t["lineage_match"], "n_homonyms": t.get("n_homonyms_in_pbdb"), "tdf": t.get("taxonomic_difference"), "status": t.get("taxonomic_status"), "found": t.get("found")})
    unmatched = [(r["dataset_id"], c["property_id"]) for r in results for c in r["checks"]["count_rechecks"] if c["within_tolerance"] is None]
    return {
        "n_records": len(results),
        "verdicts": verdicts,
        "n_drifted_counts": len(drift),
        "worst_drift": drift[:25],
        "taxon_issues": homonyms,
        "unmatched_counts": unmatched,
        "bad_dois": [(r["dataset_id"], b["value"]) for r in results for b in (r["checks"].get("bad_dois") or [])],
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datasets", type=Path, default=DATASETS)
    ap.add_argument("--taxa", type=Path, default=TAXA)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--cache", type=Path, default=CACHE_DIR)
    ap.add_argument("--ids", nargs="*", help="only these dataset ids")
    ap.add_argument("--limit", type=int, help="only the first N records of the batch")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-fetch everything")
    ap.add_argument("--no-write", action="store_true", help="do not write batch files; print results")
    ap.add_argument("--summary", type=Path, help="write the run summary JSON here (default: <cache>/summary.json)")
    args = ap.parse_args(argv)

    records = [r for r in load_json(args.datasets) if r["id"].startswith(ID_PREFIXES)]
    if args.ids:
        wanted = set(args.ids)
        records = [r for r in records if r["id"] in wanted]
    if args.limit:
        records = records[: args.limit]
    taxa = {t["key"]: t for t in load_json(args.taxa)}
    sources = {k: load_json(p) for k, p in SOURCES.items()}

    client = Client(args.cache, refresh=args.refresh)
    resolver = Resolver(client)
    results = []
    t0 = time.monotonic()
    for i, rec in enumerate(records, 1):
        res = assess_record(rec, taxa, sources, client, resolver)
        results.append(res)
        cr = res["checks"]["count_recheck"]
        brief = f"{cr.get('recorded')}->{cr.get('observed')}" if "recorded" in cr else f"{cr['n_within_tolerance']}/{cr['n_compared']} ok"
        print(f"[{i}/{len(records)}] {rec['id']}: {res['verdict']} overall={res['overall']} integ={res['scores']['integrity']} comp={res['scores']['completeness']} auth={res['scores']['authenticity']} counts {brief}", flush=True)

    summary = summarise(results)
    summary["network_requests"] = client.n_network
    summary["cached_responses"] = client.n_cached
    summary["elapsed_s"] = round(time.monotonic() - t0, 1)
    if args.no_write:
        preview = args.cache / "preview.json"
        preview.write_text(json.dumps(results, indent=1, ensure_ascii=False), "utf-8")
        print(f"preview written to {preview}")
    else:
        paths = write_batches(results, args.out)
        print(f"wrote {len(paths)} batch file(s) to {args.out}")
    spath = args.summary or (args.cache / "summary.json")
    spath.write_text(json.dumps(summary, indent=1, ensure_ascii=False), "utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k not in ("worst_drift", "taxon_issues", "unmatched_counts")}, indent=1))
    print(f"summary written to {spath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
