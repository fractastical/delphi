#!/usr/bin/env python3
"""Re-check and score the GBIF-API dataset records of test-data/organisms/merged/datasets.json.

Batch: every record whose id starts with `gbif-occurrences-`, `gbif-occurrence-`,
`gbif-backbone-` or `iucn-red-list-via-gbif-`.

For each record the script
  * re-fetches every recorded distribution URL on api.gbif.org (count, search?limit=0,
    species/match, species/{key}, species/{key}/iucnRedListCategory) and recomputes the
    SHA-256 of the body (raw, and for JSON bodies a few canonical serialisations, because
    some vendors hashed a re-serialised cache rather than the wire bytes);
  * compares the observed occurrence count with every recorded `counts[].value`
    (tolerance: relative <= 0.5 % or absolute <= 5), constructing the documented
    `occurrence/count?taxonKey=K[&hasCoordinate=true&hasGeospatialIssue=false]` query when
    the record stored a count without a matching distribution;
  * resolves every taxon key (identifier, `taxa`, count descriptions) through
    `species/{key}` and checks canonicalName / acceptedKey against the record label, the
    dataset-id slug and the `taxa` slugs, flagging non-accepted usages, keys with zero
    descendants above species rank, and zero counts for higher taxa;
  * verifies DOIs through the doi.org handle API (www.gbif.org returns 403 to scripts);
  * scores the five rubric dimensions (test-data/organisms/assessment/rubric.json) and writes
    test-data/organisms/assessment/records/gbif/batch-NN.json (< 1 MB each).

Requests are rate-limited to <= 5/s and cached under scripts/cache/ (gitignored), so a
re-run is cheap; pass --refresh to ignore the cache.

Usage:  python3 test-data/organisms/assessment/scripts/recheck_gbif.py [--refresh] [--limit N] [--report]
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import re
import sys
import threading
import time
from collections import Counter, OrderedDict
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
MERGED = REPO / "test-data" / "organisms" / "merged" / "datasets.json"
TAXA = REPO / "test-data" / "organisms" / "merged" / "taxa.json"
RUBRIC = HERE.parent / "rubric.json"
OUT_DIR = HERE.parent / "records" / "gbif"
CACHE_DIR = HERE / "cache"
RAW_OUT = CACHE_DIR / "recheck-raw.json"

BATCH_PREFIXES = ("gbif-occurrences-", "gbif-occurrence-", "gbif-backbone-", "iucn-red-list-via-gbif-")
API = "https://api.gbif.org/v1"
USER_AGENT = "delphi-dataset-assessor/0.1 (test-data/organisms/assessment/scripts/recheck_gbif.py; +https://github.com/fractastical/delphi)"
MAX_RPS = 5.0
TIMEOUT = 40
MAX_FILE_BYTES = 900_000
MAX_PER_FILE = 300
SPECIES_RANKS = {"SPECIES", "SUBSPECIES", "VARIETY", "FORM", "SUBVARIETY", "SUBFORM"}

SOURCE_SCORES = {
    "gbif-occurrence-api": {"source-authority": 0.9, "independence": 0.85, "authenticity": 1.0},
    "gbif-backbone-taxonomy": {"source-authority": 0.95, "independence": 0.8, "authenticity": 1.0},
    "iucn-red-list-via-gbif": {"source-authority": 0.9, "independence": 0.95, "authenticity": 1.0},
}
IUCN_ORDER = ["NE", "DD", "LC", "NT", "VU", "EN", "CR", "EW", "EX"]


# ----------------------------------------------------------------------------- fetching

class RateLimiter:
    def __init__(self, rps: float):
        self.interval = 1.0 / rps
        self.lock = threading.Lock()
        self.next_at = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            if now < self.next_at:
                time.sleep(self.next_at - now)
                now = time.monotonic()
            self.next_at = max(now, self.next_at) + self.interval


class Fetcher:
    """GET with on-disk cache (exact bytes), rate limit and retries."""

    def __init__(self, refresh: bool = False):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.limiter = RateLimiter(MAX_RPS)
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.session.headers["Accept"] = "application/json, text/plain, */*"
        self.stats = Counter()
        self.lock = threading.Lock()

    @staticmethod
    def _path(url: str, method: str) -> Path:
        h = hashlib.sha1(f"{method} {url}".encode()).hexdigest()
        return CACHE_DIR / f"{h}.json"

    def get(self, url: str, method: str = "GET") -> dict:
        p = self._path(url, method)
        if not self.refresh and p.exists():
            with p.open() as fh:
                entry = json.load(fh)
            with self.lock:
                self.stats["cache_hits"] += 1
            return entry
        entry = None
        for attempt in range(4):
            self.limiter.wait()
            try:
                if method == "HEAD":
                    r = self.session.head(url, timeout=TIMEOUT, allow_redirects=True)
                else:
                    r = self.session.get(url, timeout=TIMEOUT)
                body = r.content if method == "GET" else b""
                entry = {
                    "url": url,
                    "method": method,
                    "status": r.status_code,
                    "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "content_type": r.headers.get("Content-Type"),
                    "content_length": r.headers.get("Content-Length"),
                    "body_b64": base64.b64encode(body).decode("ascii"),
                }
                if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                break
            except requests.RequestException as exc:  # network error: retry, then record
                entry = {"url": url, "method": method, "status": None, "error": str(exc)[:300],
                         "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                         "body_b64": ""}
                time.sleep(2.0 * (attempt + 1))
        with self.lock:
            self.stats["requests"] += 1
        if entry.get("status") is not None:  # do not cache pure network failures
            tmp = p.with_suffix(".tmp")
            with tmp.open("w") as fh:
                json.dump(entry, fh)
            os.replace(tmp, p)
        return entry

    def prefetch(self, urls, workers: int = 4):
        urls = [u for u in OrderedDict.fromkeys(urls) if u]
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(self.get, urls))


def body_bytes(entry: dict) -> bytes:
    return base64.b64decode(entry.get("body_b64", "")) if entry else b""


def body_json(entry: dict):
    try:
        return json.loads(body_bytes(entry).decode("utf-8"))
    except Exception:
        return None


# ----------------------------------------------------------------------------- helpers

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def checksum_variants(raw: bytes) -> dict:
    """SHA-256 of the wire bytes plus common re-serialisations of a JSON body."""
    out = {"raw": sha256_hex(raw)}
    try:
        obj = json.loads(raw.decode("utf-8"))
    except Exception:
        return out
    for name, kw in (
        ("json_sorted", dict(sort_keys=True)),
        ("json_sorted_compact", dict(sort_keys=True, separators=(",", ":"))),
        ("json_sorted_indent2", dict(sort_keys=True, indent=2)),
        ("json_default", {}),
        ("json_indent2", dict(indent=2)),
        ("json_sorted_ascii_false", dict(sort_keys=True, ensure_ascii=False)),
        ("json_sorted_indent2_ascii_false", dict(sort_keys=True, indent=2, ensure_ascii=False)),
    ):
        s = json.dumps(obj, **kw)
        out[name] = sha256_hex(s.encode("utf-8"))
        out[name + "_nl"] = sha256_hex((s + "\n").encode("utf-8"))
    return out


def norm_name(s: str | None) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("-", " ")).strip()


def slugify(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def within_tol(recorded, observed) -> tuple[bool | None, float | None]:
    if recorded is None or observed is None:
        return None, None
    diff = abs(observed - recorded)
    rel = diff / max(abs(recorded), 1)
    return (diff <= 5 or rel <= 0.005), round(rel, 6)


def keys_in_text(s: str | None) -> list[int]:
    if not s:
        return []
    found = re.findall(r"(?:taxonKey|usageKey|usage key|usage|key)\s*=?\s*(\d{2,})", s)
    return [int(k) for k in found]


def query_key_and_flags(url: str) -> tuple[int | None, bool, dict]:
    q = parse_qs(urlparse(url).query)
    key = q.get("taxonKey", [None])[0]
    georef = q.get("hasCoordinate", [""])[0] == "true" and q.get("hasGeospatialIssue", [""])[0] == "false"
    extra = {k: v for k, v in q.items() if k not in ("taxonKey", "limit", "hasCoordinate", "hasGeospatialIssue")}
    try:
        key = int(key) if key is not None else None
    except ValueError:
        key = None
    return key, georef, extra


def count_url(key: int, georef: bool) -> str:
    u = f"{API}/occurrence/count?taxonKey={key}"
    return u + "&hasCoordinate=true&hasGeospatialIssue=false" if georef else u


def parse_count(entry: dict, url: str):
    if not entry or entry.get("status") != 200:
        return None
    raw = body_bytes(entry)
    if "/occurrence/count" in url:
        try:
            return int(raw.decode().strip())
        except ValueError:
            return None
    obj = body_json(entry)
    if isinstance(obj, dict) and isinstance(obj.get("count"), int):
        return obj["count"]
    return None


def identifier_keys(identifier: str) -> list[int]:
    keys: list[int] = []
    m = re.search(r"taxon_key=([\d,]+)", identifier)
    if m:
        keys += [int(k) for k in m.group(1).split(",") if k]
    m = re.search(r"taxonKey=(\d+)", identifier)
    if m:
        keys.append(int(m.group(1)))
    m = re.search(r"/species/(\d+)", identifier)
    if m:
        keys.append(int(m.group(1)))
    return list(OrderedDict.fromkeys(keys))


def label_name(label: str) -> str | None:
    m = re.search(r"GBIF occurrence (?:count|records) for (.+?) \((?:GBIF )?(?:backbone )?(?:taxonKey|usageKey|count)", label)
    if m:
        return m.group(1).strip()
    m = re.search(r"GBIF occurrence (?:count|records) for (.+?)(?:,| \(|$)", label)
    return m.group(1).strip() if m else None


def id_slug(dataset_id: str) -> str:
    s = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", dataset_id)
    for p in ("gbif-occurrence-count-", "gbif-occurrences-", "gbif-occurrence-"):
        if s.startswith(p):
            return s[len(p):]
    return s


def name_matches(canonical: str | None, text: str | None) -> bool:
    """True when `text` is the canonical name, optionally followed by authorship."""
    if not canonical or not text:
        return False
    c, t = norm_name(canonical), norm_name(text)
    if c == t:
        return True
    if t.startswith(c + " "):
        rest = text.strip()[len(canonical):].strip()
        # what follows must look like authorship: "Linnaeus, 1758", "(Goldfuss, 1826)", "d'Orbigny, 1849", "de Blainville, 1830"
        return bool(rest) and (rest[0].isupper() or rest[0] in "(" or re.match(r"(d'|de |da |van |von |du |le |la )", rest) is not None)
    return False


def same_epithet_variant(canonical: str | None, text: str | None) -> bool:
    """'Canis familiaris' vs 'Canis lupus familiaris', 'Anancus arvernensis' vs 'Mastodon arvernensis':
    same terminal epithet, so the same nominal concept under another combination or rank."""
    if not canonical or not text:
        return False
    c, t = norm_name(canonical).split(), norm_name(text).split()
    if len(c) < 2 or len(t) < 2:
        return False
    return c[-1] == t[-1]


def fmt_dt() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- taxon lookup

class TaxonIndex:
    def __init__(self, fetcher: Fetcher, taxa_json: list[dict]):
        self.f = fetcher
        self.by_key = {}
        for t in taxa_json:
            self.by_key[t["key"]] = t
            gk = (t.get("identifiers") or {}).get("gbif_usage_key")
            if gk is not None:
                self.by_key.setdefault(f"gbif:{gk}", t)

    def project_taxon(self, key: str) -> dict | None:
        return self.by_key.get(key)

    def species(self, key: int) -> dict:
        url = f"{API}/species/{key}"
        e = self.f.get(url)
        info = {"key": key, "http_status": e.get("status"), "resolves": e.get("status") == 200}
        obj = body_json(e) if e.get("status") == 200 else None
        if isinstance(obj, dict):
            for k in ("scientificName", "canonicalName", "rank", "taxonomicStatus", "acceptedKey", "accepted",
                      "numDescendants", "kingdom", "parentKey", "parent", "synonym", "nubKey", "datasetKey"):
                if k in obj:
                    info[k] = obj[k]
            info["lineage_keys"] = [obj.get(k) for k in ("kingdomKey", "phylumKey", "classKey", "orderKey",
                                                        "familyKey", "genusKey", "speciesKey") if obj.get(k)]
            info["is_backbone"] = obj.get("datasetKey") == "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
        return info


# ----------------------------------------------------------------------------- scoring

def load_rubric():
    with RUBRIC.open() as fh:
        rub = json.load(fh)
    return {d["id"]: d["weight"] for d in rub["dimensions"]}


WEIGHTS = load_rubric()


def clamp(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 2)


def overall(scores: dict) -> float:
    return round(sum(scores[k] * w for k, w in WEIGHTS.items()), 4)


def verdict_for(scores: dict, identifier_exists: bool) -> str:
    o = overall(scores)
    if scores["authenticity"] < 0.5 or not identifier_exists:
        return "reject"
    if scores["integrity"] < 0.5 or scores["completeness"] < 0.4:
        return "needs-repair"
    if o >= 0.8 and scores["integrity"] >= 0.7 and scores["authenticity"] >= 0.8:
        return "reliable"
    if o >= 0.55:
        return "usable-with-caveats"
    return "needs-repair"


# ----------------------------------------------------------------------------- occurrence records

def check_occurrence(rec: dict, f: Fetcher, tx: TaxonIndex) -> dict:
    checks: dict = {"checked_at": fmt_dt()}
    flags: list[str] = []
    obstacles: list[str] = []
    ident = rec.get("identifier") or ""
    id_keys = identifier_keys(ident)
    taxa_gbif = [int(t.split(":")[1]) for t in rec.get("taxa", []) if t.startswith("gbif:")]
    taxa_other = [t for t in rec.get("taxa", []) if not t.startswith("gbif:")]

    # --- distributions: re-fetch, checksum, parse counts
    observed_queries: dict[tuple[int, bool], dict] = {}
    checksums = []
    for d in rec.get("distributions", []):
        url = d.get("download_url")
        if not url or "api.gbif.org" not in url:
            checksums.append({"url": url, "recorded": d.get("sha256"), "observed": None, "match": None,
                              "note": "not an api.gbif.org URL; not re-fetched"})
            continue
        e = f.get(url)
        raw = body_bytes(e) if e.get("status") == 200 else b""
        variants = checksum_variants(raw) if raw else {}
        rec_sha = d.get("sha256")
        match = None
        matched_as = None
        if rec_sha and variants:
            for name, h in variants.items():
                if h == rec_sha:
                    match, matched_as = True, name
                    break
            else:
                match = False
        checksums.append({"url": url, "http_status": e.get("status"), "recorded": rec_sha,
                          "observed": variants.get("raw"), "match": match, "matched_as": matched_as})
        if "/occurrence/" in url:
            key, georef, extra = query_key_and_flags(url)
            cnt = parse_count(e, url)
            if key is not None and not extra:
                observed_queries.setdefault((key, georef), {"url": url, "count": cnt, "http_status": e.get("status")})
            elif key is not None:
                observed_queries.setdefault((key, georef, json.dumps(extra, sort_keys=True)),
                                            {"url": url, "count": cnt, "http_status": e.get("status"), "extra": extra})
    checks["checksums"] = checksums
    comparable = [c for c in checksums if c["match"] is not None]
    checks["checksum_match"] = (all(c["match"] for c in comparable) if comparable else None)

    # --- counts
    count_keys_from_desc = []
    for c in rec.get("counts", []):
        count_keys_from_desc += keys_in_text(c.get("description"))
    primary_key = id_keys[0] if id_keys else (taxa_gbif[0] if taxa_gbif else (count_keys_from_desc[0] if count_keys_from_desc else None))
    component_keys = id_keys if len(id_keys) > 1 else [k for k in OrderedDict.fromkeys(count_keys_from_desc)]
    rechecks = []
    for c in rec.get("counts", []):
        pid = c.get("property_id")
        recorded = c.get("value")
        desc_keys = keys_in_text(c.get("description"))
        georef = pid == "n_occurrences_georeferenced" or "coordinates" in (c.get("description") or "").lower()
        item = {"property_id": pid, "recorded": recorded, "description": (c.get("description") or "")[:160]}
        if pid == "n_occurrences_total" or (not desc_keys and len(id_keys) > 1 and "sum" in (c.get("description") or "").lower()):
            keys = [k for k in component_keys if k] or id_keys
            parts = []
            total = 0
            ok = True
            for k in keys:
                q = observed_queries.get((k, False))
                if q is None:
                    e = f.get(count_url(k, False))
                    q = {"url": count_url(k, False), "count": parse_count(e, count_url(k, False)), "http_status": e.get("status"), "constructed": True}
                    observed_queries[(k, False)] = q
                parts.append({"key": k, "observed": q["count"]})
                if q["count"] is None:
                    ok = False
                else:
                    total += q["count"]
            item.update({"keys": keys, "parts": parts, "observed": total if ok else None, "kind": "sum"})
        else:
            key = desc_keys[0] if desc_keys else primary_key
            q = observed_queries.get((key, georef)) if key is not None else None
            if q is None and key is not None:
                e = f.get(count_url(key, georef))
                q = {"url": count_url(key, georef), "count": parse_count(e, count_url(key, georef)), "http_status": e.get("status"), "constructed": True}
                observed_queries[(key, georef)] = q
            item.update({"key": key, "georeferenced": georef, "observed": q["count"] if q else None,
                         "query": q["url"] if q else None, "query_constructed": bool(q and q.get("constructed"))})
        ok, rel = within_tol(recorded, item.get("observed"))
        item["relative_diff"] = rel
        item["within_tolerance"] = ok
        if item.get("observed") is not None and recorded is not None:
            item["absolute_diff"] = item["observed"] - recorded
        rechecks.append(item)
    checks["count_rechecks"] = rechecks
    worst = None
    for it in rechecks:
        if it["within_tolerance"] is None:
            worst = it if worst is None else worst
            continue
        if worst is None or worst["within_tolerance"] is None or (not it["within_tolerance"] and (it["relative_diff"] or 0) > (worst["relative_diff"] or 0)):
            worst = it
        elif worst["within_tolerance"] and not it["within_tolerance"]:
            worst = it
    checks["count_recheck"] = ({k: worst.get(k) for k in ("property_id", "key", "recorded", "observed", "relative_diff", "within_tolerance")} if worst else None)

    # --- taxon keys
    all_keys = list(OrderedDict.fromkeys([k for k in id_keys + taxa_gbif + [it.get("key") for it in rechecks if it.get("key")]
                                          + [k for it in rechecks for k in it.get("keys", [])] if k]))
    key_info = {k: tx.species(k) for k in all_keys}
    for k, info in list(key_info.items()):
        ak = info.get("acceptedKey")
        if ak and ak not in key_info:
            key_info[ak] = tx.species(ak)
    checks["taxon_keys"] = [{kk: v for kk, v in key_info[k].items() if kk != "lineage_keys"} for k in all_keys]

    lname = label_name(rec.get("label") or "")
    slug = id_slug(rec["id"])
    checks["label_name"] = lname
    checks["id_slug"] = slug

    primary_info = key_info.get(primary_key) if primary_key else None
    checks["taxon_key_resolves_to"] = primary_info.get("canonicalName") if primary_info and primary_info.get("resolves") else None
    # composite: the group has no backbone usage and the record sums or lists component keys
    composite = bool(taxa_other) or len(id_keys) > 1 or any(it.get("kind") == "sum" for it in rechecks)
    checks["composite_record"] = composite
    if primary_key is None:
        flags.append("no_taxon_key_found")
    elif not primary_info.get("resolves"):
        flags.append(f"primary_key_{primary_key}_does_not_resolve_http_{primary_info.get('http_status')}")
    else:
        canon = primary_info.get("canonicalName")
        acc_name = None
        if primary_info.get("acceptedKey") and key_info.get(primary_info["acceptedKey"], {}).get("resolves"):
            acc_name = key_info[primary_info["acceptedKey"]].get("canonicalName")
        # synonyms mentioned in the record (count descriptions / taxa) whose accepted key is the primary key
        syn_names = [i.get("canonicalName") for k, i in key_info.items() if i.get("acceptedKey") == primary_key and i.get("resolves")]
        proj = tx.project_taxon(f"gbif:{primary_key}")
        proj_names = [proj.get("accepted_name"), proj.get("slug").replace("-", " ")] if proj else []
        label_ok = None
        if lname:
            label_ok = name_matches(canon, lname) or name_matches(acc_name, lname) or any(name_matches(p, lname) for p in proj_names)
            if not label_ok and any(name_matches(sn, lname) for sn in syn_names):
                label_ok = True
                flags.append(f"label_is_a_synonym_resolved_to_accepted_key_{primary_key}_({canon})")
            elif not label_ok and same_epithet_variant(canon, lname):
                label_ok = True
                flags.append(f"label_name_variant_of_key_{primary_key}_({lname}_vs_{canon})")
        slug_ok = slug in {slugify(canon), slugify(acc_name)} or (proj is not None and proj.get("slug") == slug) or any(slugify(sn) == slug for sn in syn_names)
        if not slug_ok and same_epithet_variant(canon, slug.replace("-", " ")):
            slug_ok = True
        if composite:
            # the label names the group (e.g. Reptilia, Xenarthra); the keys are its components
            comp_names = [key_info.get(k, {}).get("canonicalName") for k in (component_keys or id_keys)]
            checks["component_keys_resolve_to"] = comp_names
            group = tx.project_taxon(taxa_other[0]) if taxa_other else None
            group_name = group.get("accepted_name") if group else None
            flags.append("composite_group_without_backbone_usage:" + (lname or slug) + "=" + "+".join(str(n) for n in comp_names))
            if not (label_ok or slug_ok):
                label_ok = None  # not applicable: the label names the group, not a key
                if group_name and lname and not (name_matches(group_name, lname) or norm_name(group_name) == norm_name(lname)):
                    flags.append(f"label_{lname}_differs_from_project_group_{group_name}")
            if len(id_keys) == 1 and taxa_other and comp_names and lname and not name_matches(comp_names[0], lname):
                flags.append(f"single_proxy_key_{primary_key}_({comp_names[0]})_stands_for_{lname}")
        checks["label_matches_key"] = label_ok
        checks["id_slug_matches_key"] = slug_ok
        if label_ok is False and not slug_ok:
            flags.append(f"label_and_slug_disagree_with_key_{primary_key}_({canon})")
        elif label_ok is False:
            flags.append(f"label_name_differs_from_key_{primary_key}_({canon})")
        elif not slug_ok and not composite:
            flags.append(f"id_slug_differs_from_key_{primary_key}_({canon})")
        if primary_info.get("taxonomicStatus") not in (None, "ACCEPTED"):
            flags.append(f"primary_key_status_{primary_info.get('taxonomicStatus')}")
        if primary_info.get("rank") not in SPECIES_RANKS and primary_info.get("numDescendants") == 0:
            if primary_info.get("rank") == "GENUS":
                flags.append("primary_key_genus_without_species_in_backbone")
            else:
                flags.append(f"primary_key_orphaned_higher_rank_{primary_info.get('rank')}_with_zero_descendants")
        if not primary_info.get("is_backbone", True):
            flags.append("primary_key_not_in_backbone_dataset")

    # keys per count: non-accepted or orphaned
    vendor_noted_zero = "0 because" in json.dumps(rec.get("notes") or "") or "zero" in json.dumps(rec.get("notes") or "").lower()
    for it in rechecks:
        for k in ([it.get("key")] if it.get("key") else it.get("keys", [])):
            info = key_info.get(k, {})
            if not info.get("resolves"):
                flags.append(f"count_key_{k}_does_not_resolve")
                continue
            if (it.get("observed") == 0 or it.get("recorded") == 0) and it.get("kind") != "sum" and not it.get("georeferenced"):
                if info.get("rank") in SPECIES_RANKS or info.get("rank") == "GENUS":
                    flags.append(f"zero_count_for_{str(info.get('rank')).lower()}_key_{k}_({info.get('canonicalName')})")
                else:
                    flags.append(f"zero_count_for_higher_taxon_key_{k}_({info.get('canonicalName')},{info.get('rank')},{info.get('numDescendants')}_descendants)"
                                 + ("_noted_by_vendor" if vendor_noted_zero else ""))
            if info.get("taxonomicStatus") not in (None, "ACCEPTED") and k != primary_key:
                flags.append(f"count_key_{k}_status_{info.get('taxonomicStatus')}")

    # taxa slugs vs queried keys
    queried = set(k for k in id_keys) | set(it.get("key") for it in rechecks if it.get("key")) | set(k for it in rechecks for k in it.get("keys", []))
    taxa_checks = []
    for k in taxa_gbif:
        info = key_info.get(k, {})
        rel = "queried" if k in queried else None
        if rel is None:
            for qk in queried:
                qi = key_info.get(qk, {})
                if qi.get("acceptedKey") == k:
                    rel = f"accepted_key_of_queried_synonym_{qk}"
                    break
                if info.get("acceptedKey") == qk:
                    rel = f"synonym_of_queried_key_{qk}"
                    break
                if k in (qi.get("lineage_keys") or []):
                    rel = f"ancestor_of_queried_key_{qk}"
                    break
                if qk in (info.get("lineage_keys") or []):
                    rel = f"descendant_of_queried_key_{qk}"
                    break
        proj = tx.project_taxon(f"gbif:{k}")
        entry = {"taxon": f"gbif:{k}", "resolves_to": info.get("canonicalName"), "rank": info.get("rank"),
                 "status": info.get("taxonomicStatus"), "relation_to_queried_key": rel or "unrelated",
                 "project_slug": proj.get("slug") if proj else None, "project_accepted_name": proj.get("accepted_name") if proj else None}
        if proj and info.get("resolves") and not (name_matches(info.get("canonicalName"), proj.get("accepted_name"))
                                                  or name_matches(proj.get("accepted_name"), info.get("canonicalName"))):
            entry["project_name_vs_gbif"] = "differs"
            flags.append(f"taxa_slug_{proj.get('slug')}_names_{proj.get('accepted_name')}_but_key_{k}_is_{info.get('canonicalName')}")
        if rel is None:
            flags.append(f"taxa_key_{k}_({info.get('canonicalName')})_unrelated_to_queried_keys_{sorted(queried)}")
        taxa_checks.append(entry)
    for t in taxa_other:
        proj = tx.project_taxon(t)
        taxa_checks.append({"taxon": t, "resolves_to": None, "relation_to_queried_key": "not a GBIF key",
                            "project_slug": proj.get("slug") if proj else None,
                            "project_accepted_name": proj.get("accepted_name") if proj else None})
        flags.append(f"taxa_slug_{t}_is_not_a_gbif_key_(group_has_no_backbone_usage;_components_{id_keys})")
    checks["taxa_slugs"] = taxa_checks

    # identifier resolution
    if "api.gbif.org" in ident:
        e = f.get(ident)
        checks["identifier_http_status"] = e.get("status")
        checks["identifier_resolves"] = e.get("status") == 200
        checks["identifier_checked_via"] = ident
    elif primary_key is not None:
        via = count_url(primary_key, False) if "/occurrence/" in ident else f"{API}/species/{primary_key}"
        e = f.get(via)
        checks["identifier_http_status"] = e.get("status")
        checks["identifier_resolves"] = e.get("status") == 200 and (primary_info or {}).get("resolves", True)
        checks["identifier_checked_via"] = via
        obstacles.append("www.gbif.org landing pages return HTTP 403 to automated clients; the identifier was verified through the equivalent api.gbif.org query.")
    else:
        checks["identifier_resolves"] = None

    # --- scoring
    src = SOURCE_SCORES["gbif-occurrence-api"]
    s = dict(src)
    rechecked = [it for it in rechecks if it["within_tolerance"] is not None]
    unreproducible = [it for it in rechecks if it["within_tolerance"] is None]
    beyond = [it for it in rechecks if it["within_tolerance"] is False]
    worst_rel = max((it["relative_diff"] or 0) for it in beyond) if beyond else 0.0
    if not checks.get("identifier_resolves"):
        integrity = 0.0
    elif not rechecked:
        integrity = 0.4
    elif not beyond:
        integrity = 1.0
    elif worst_rel <= 0.02:
        integrity = 0.7
    elif worst_rel <= 0.10:
        integrity = 0.55
    elif worst_rel <= 0.5:
        integrity = 0.4
    else:
        integrity = 0.2
    if unreproducible and rechecked and integrity > 0.5:
        integrity = 0.5
    # a count on a key that does not resolve cannot be an integrity pass
    if any(fl.startswith("count_key_") and "does_not_resolve" in fl for fl in flags):
        integrity = min(integrity, 0.3)

    completeness = 1.0
    missing = [k for k in ("license", "creators", "issued", "version", "bibliographic_citation", "measurement_technique") if not rec.get(k)]
    if missing:
        completeness -= 0.2 * len(missing)
    if not rec.get("is_referenced_by") and not rec.get("doi"):
        completeness -= 0.1
    if any(not d.get("sha256") for d in rec.get("distributions", [])):
        completeness -= 0.1
    has = lambda prefix: any(fl.startswith(prefix) for fl in flags)  # noqa: E731
    if has("label_and_slug_disagree"):
        completeness -= 0.4
    elif has("label_name_differs"):
        completeness -= 0.15
    elif has("id_slug_differs"):
        completeness -= 0.05  # the id carries the project's name-as-written; the label and key agree
    if has("label_name_variant_of_key") or has("label_is_a_synonym"):
        completeness -= 0.1  # same nominal concept under another combination; should be stated in the record
    if any(fl.startswith("primary_key_status_") and not fl.endswith("DOUBTFUL") for fl in flags):
        completeness -= 0.15  # synonym key: GBIF indexes occurrences to the accepted usage, so the count under-reports
    elif has("primary_key_status_DOUBTFUL"):
        completeness -= 0.05  # provisionally accepted usage (typical for fossil genera); the count is still meaningful
    if has("zero_count_for_higher_taxon"):
        completeness -= 0.3 if any("noted_by_vendor" in fl for fl in flags) else 0.4
    elif has("zero_count_for_"):
        completeness -= 0.15  # a genuine zero for an obscure genus/species: reproducible but uninformative
    if has("primary_key_orphaned_higher_rank"):
        completeness -= 0.3  # a family-or-higher node with no descendants: the count cannot cover the group
    elif has("primary_key_genus_without_species"):
        completeness -= 0.05
    if any(fl.startswith("taxa_key_") and "unrelated" in fl for fl in flags):
        completeness -= 0.25
    if any(fl.startswith("taxa_slug_") and "_but_key_" in fl for fl in flags):
        completeness -= 0.2
    if has("composite_group_without_backbone_usage"):
        completeness -= 0.1  # the group itself has no backbone usage; the record is a documented sum of components
    if has("single_proxy_key"):
        completeness -= 0.15  # one component (e.g. a family) stands in for the whole group named in the label
    if has("label_") and any("differs_from_project_group" in fl for fl in flags):
        completeness -= 0.2
    if unreproducible:
        completeness -= 0.2

    authenticity = src["authenticity"]
    authority = src["source-authority"]
    if any("does_not_resolve" in fl for fl in flags):
        authenticity = 0.0 if (primary_info and not primary_info.get("resolves")) else 0.4
        authority = 0.5
    elif has("label_and_slug_disagree"):
        authenticity = 0.4  # the key is a different taxon from the one named
        authority = authority - 0.2
    elif has("zero_count_for_higher_taxon") or has("primary_key_orphaned_higher_rank"):
        # real response, but a number that does not measure the taxon named: recorded as if meaningful
        authenticity = 0.7 if any("noted_by_vendor" in fl for fl in flags) else 0.6
        authority = authority - 0.1
    elif rechecks and all(it["within_tolerance"] is None for it in rechecks):
        authenticity = 0.5
    elif beyond and worst_rel > 0.5:
        authenticity = 0.7
    s.update({"integrity": clamp(integrity), "completeness": clamp(completeness),
              "authenticity": clamp(authenticity), "source-authority": clamp(authority)})

    confidence = 0.9
    if checks.get("checksum_match") is False:
        confidence -= 0.05
    if unreproducible:
        confidence -= 0.2
    if any(f_.get("http_status") not in (200, 404) for f_ in checks["taxon_keys"]):
        confidence -= 0.2
    if taxa_other:
        confidence -= 0.1

    if beyond:
        obstacles.append("GBIF counts are live and drift as records are indexed or removed; the recorded value could not be reproduced within tolerance.")
    else:
        obstacles.append("GBIF counts are live and drift as records are indexed; the comparison holds only for the check date.")
    if checks.get("checksum_match") is False:
        obstacles.append("Checksum of the API body no longer matches: the count/search response is volatile (bare integer or JSON with live count), so this is expected and integrity is scored on the count itself.")
    if any(c.get("matched_as") and c["matched_as"] != "raw" for c in checksums):
        obstacles.append("The recorded checksum was computed on a re-serialised JSON cache rather than the wire bytes; it matched after re-serialisation.")
    if has("zero_count_for_higher_taxon"):
        obstacles.append("The occurrence index returns 0 for this key although the backbone lists descendants under it: GBIF does not attach occurrences to this node (superfamily and some class keys are not part of the occurrence classification), so the count says nothing about the taxon.")
    if has("primary_key_orphaned_higher_rank"):
        obstacles.append("The key is a family-or-higher usage with no descendants in the frozen backbone; occurrences are attached to it only by direct name match, so the count covers a fraction of the group named.")
    if has("composite_group_without_backbone_usage"):
        obstacles.append("The group named has no accepted usage in the GBIF backbone; the record sums counts over component keys, each verified separately.")

    return finish(rec, "gbif-occurrence-api", s, confidence, checks, flags, obstacles, occurrence_rationale(rec, checks, flags, s))


def occurrence_rationale(rec, checks, flags, s) -> str:
    rc = checks.get("count_rechecks") or []
    n_ok = sum(1 for it in rc if it["within_tolerance"])
    n_tot = len(rc)
    parts = []
    ck = checks.get("taxon_key_resolves_to")
    parts.append(f"Re-queried {n_tot} recorded count(s) against api.gbif.org on {checks['checked_at'][:10]}: {n_ok} of {n_tot} within tolerance"
                 + (f" (worst relative difference {checks['count_recheck']['relative_diff']})." if checks.get("count_recheck") and checks["count_recheck"].get("relative_diff") is not None else "."))
    if ck and checks.get("composite_record"):
        comps = checks.get("component_keys_resolve_to") or []
        parts.append(f"The group named ({checks.get('label_name') or checks.get('id_slug')}) has no backbone usage; the record is built from component key(s) resolving to {', '.join(str(c) for c in comps)}, each re-queried separately.")
    elif ck:
        lm, sm = checks.get("label_matches_key"), checks.get("id_slug_matches_key")
        if lm in (True, None) and sm:
            tail = "consistent with the record label and id."
        elif lm in (True, None):
            tail = f"consistent with the record label; the dataset id ({checks.get('id_slug')}) carries the project's name-as-written instead."
        elif sm:
            tail = f"consistent with the dataset id but not with the label text ({checks.get('label_name')})."
        else:
            tail = f"which does not match the record label ({checks.get('label_name')}) or id ({checks.get('id_slug')})."
        parts.append(f"Primary taxon key resolves to {ck} in the GBIF backbone, {tail}")
    else:
        parts.append("The primary taxon key did not resolve through species/{key}.")
    cm = checks.get("checksum_match")
    parts.append("Recorded checksums reproduce exactly." if cm else ("Recorded checksums no longer reproduce, as expected for a live count body; integrity is scored on the count." if cm is False else "No checksum could be compared."))
    if flags:
        parts.append("Flags: " + "; ".join(flags[:4]) + ("." if len(flags) <= 4 else f" (+{len(flags) - 4} more)."))
    parts.append("Source authority, independence and authenticity inherit from the gbif-occurrence-api source score"
                 + ("." if s["authenticity"] == SOURCE_SCORES["gbif-occurrence-api"]["authenticity"] and s["source-authority"] == SOURCE_SCORES["gbif-occurrence-api"]["source-authority"] else ", lowered because the record itself shows a problem."))
    return " ".join(parts)


# ----------------------------------------------------------------------------- backbone records

def doi_check(f: Fetcher, doi: str) -> dict:
    e = f.get(f"https://doi.org/api/handles/{doi}")
    obj = body_json(e) if e.get("status") == 200 else None
    url = None
    if isinstance(obj, dict):
        for v in obj.get("values", []):
            if v.get("type") == "URL":
                url = (v.get("data") or {}).get("value")
    return {"doi": doi, "handle_api_status": e.get("status"), "response_code": obj.get("responseCode") if isinstance(obj, dict) else None, "url": url}


def check_backbone(rec: dict, f: Fetcher, tx: TaxonIndex) -> dict:
    checks: dict = {"checked_at": fmt_dt()}
    flags: list[str] = []
    obstacles: list[str] = []
    doi = rec.get("doi") or "10.15468/39omei"
    checks["doi_check"] = doi_check(f, doi)
    ds = f.get(f"{API}/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c")
    dsj = body_json(ds) or {}
    checks["dataset_api"] = {"http_status": ds.get("status"), "title": dsj.get("title"), "doi": dsj.get("doi"), "license": dsj.get("license"), "pubDate": (dsj.get("pubDate") or "")[:10]}
    checks["identifier_resolves"] = checks["doi_check"]["response_code"] == 1 and ds.get("status") == 200
    checks["identifier_checked_via"] = "doi.org handle API + api.gbif.org/v1/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c (landing page returns 403 to scripts)"
    obstacles.append("www.gbif.org dataset landing page returns HTTP 403 to automated clients; identifier verified through the DOI handle API and the registry API.")

    taxa_keys = [int(t.split(":")[1]) for t in rec.get("taxa", []) if t.startswith("gbif:")]
    taxa_set = set(taxa_keys)
    checksums = []
    match_usage_keys = []
    exact_keys = set()
    bad_fallbacks = []
    n_match = n_match_key = n_higherrank = n_in_taxa = 0
    for d in rec.get("distributions", []):
        url = d.get("download_url") or ""
        if url.endswith(".zip"):
            e = f.get(url, method="HEAD")
            checksums.append({"url": url, "http_status": e.get("status"), "recorded": d.get("sha256"), "observed": None, "match": None,
                              "content_length": e.get("content_length"), "note": "HEAD only; archive not downloaded (not inspected by the vendor either)"})
            continue
        if "api.gbif.org" not in url and "doi.org" not in url:
            checksums.append({"url": url, "recorded": d.get("sha256"), "observed": None, "match": None, "note": "not re-fetched"})
            continue
        e = f.get(url)
        raw = body_bytes(e) if e.get("status") == 200 else b""
        variants = checksum_variants(raw) if raw else {}
        rec_sha = d.get("sha256")
        match, matched_as = None, None
        if rec_sha and variants:
            for name, h in variants.items():
                if h == rec_sha:
                    match, matched_as = True, name
                    break
            else:
                match = False
        item = {"url": url, "http_status": e.get("status"), "recorded": rec_sha, "observed": variants.get("raw"), "match": match, "matched_as": matched_as}
        if "/species/match" in url:
            n_match += 1
            obj = body_json(e) or {}
            uk = obj.get("usageKey")
            item.update({"usageKey": uk, "matchType": obj.get("matchType"), "status": obj.get("status"), "rank": obj.get("rank"), "scientificName": obj.get("scientificName")})
            queried_name = parse_qs(urlparse(url).query).get("name", [""])[0]
            if uk:
                n_match_key += 1
                match_usage_keys.append(uk)
                if uk in taxa_set:
                    n_in_taxa += 1
            if obj.get("matchType") == "HIGHERRANK":
                n_higherrank += 1
                same_name = norm_name(obj.get("canonicalName")) == norm_name(queried_name)
                item["note"] = "higher-rank fallback" + ("" if same_name else f" (queried {queried_name!r})")
                if uk and uk in taxa_set and not same_name:
                    bad_fallbacks.append({"queried": queried_name, "usageKey": uk, "returned": obj.get("scientificName")})
                elif uk and same_name:
                    exact_keys.add(uk)
            elif uk and obj.get("matchType") == "EXACT":
                exact_keys.add(uk)
        checksums.append(item)
    # a fallback key is only a defect if it is in `taxa` without any exact match that also produced it
    bad_fallbacks = [b for b in bad_fallbacks if b["usageKey"] not in exact_keys]
    checks["checksums"] = checksums
    comparable = [c for c in checksums if c["match"] is not None]
    checks["checksum_match"] = all(c["match"] for c in comparable) if comparable else None
    checks["checksum_summary"] = {"comparable": len(comparable), "matching": sum(1 for c in comparable if c["match"])}
    distinct_keys = len(set(match_usage_keys))
    checks["match_queries"] = {"total": n_match, "with_usage_key": n_match_key, "higher_rank_fallbacks": n_higherrank,
                               "fallbacks_listed_in_taxa_under_another_name": bad_fallbacks,
                               "distinct_usage_keys": distinct_keys, "usage_keys_listed_in_taxa": n_in_taxa}

    # resolve every taxa key
    infos = [tx.species(k) for k in taxa_keys]
    resolving = [i for i in infos if i.get("resolves")]
    non_acc = [i for i in resolving if i.get("taxonomicStatus") != "ACCEPTED"]
    orphans = [i for i in resolving if i.get("rank") not in SPECIES_RANKS and i.get("numDescendants") == 0]
    checks["taxa_keys"] = {"listed": len(taxa_keys), "resolving": len(resolving),
                           "non_accepted": [{"key": i["key"], "name": i.get("canonicalName"), "status": i.get("taxonomicStatus")} for i in non_acc],
                           "higher_rank_zero_descendants": [{"key": i["key"], "name": i.get("canonicalName"), "rank": i.get("rank")} for i in orphans],
                           "not_resolving": [i["key"] for i in infos if not i.get("resolves")]}
    checks["taxon_key_resolves_to"] = f"{len(resolving)}/{len(taxa_keys)} listed keys resolve in the backbone"
    if checks["taxa_keys"]["not_resolving"]:
        flags.append(f"taxa_keys_not_resolving_{checks['taxa_keys']['not_resolving']}")
    if non_acc:
        flags.append(f"{len(non_acc)}_taxa_keys_not_accepted")
    if orphans:
        flags.append(f"{len(orphans)}_higher_rank_keys_with_zero_descendants")
    if bad_fallbacks:
        flags.append(f"{len(bad_fallbacks)}_higher_rank_fallback_keys_listed_in_taxa:" + ",".join(f"{b['queried']}->{b['usageKey']}" for b in bad_fallbacks))

    # counts: compare with what the distributions show
    rechecks = []
    multi_slice = len(rec.get("slices", [])) > 1
    candidates = {"taxa_listed": len(taxa_keys), "match_queries": n_match, "match_queries_with_key": n_match_key, "distinct_usage_keys": distinct_keys}
    for c in rec.get("counts", []):
        pid, recorded = c.get("property_id"), c.get("value")
        item = {"property_id": pid, "recorded": recorded, "description": (c.get("description") or "")[:160], "slice": c.get("slice")}
        if pid in ("n_taxa_matched", "n_taxa_resolved", "n_rows_for_taxa") and multi_slice and (c.get("slice") or len(rec.get("counts", [])) > 1):
            item.update({"observed": None, "within_tolerance": None, "relative_diff": None,
                         "note": f"per-slice count merged into a {len(rec['slices'])}-slice record; the union of distributions ({n_match} match queries, {distinct_keys} distinct usage keys, {len(taxa_keys)} taxa listed) cannot be attributed to one slice"})
        elif pid in ("n_taxa_matched", "n_taxa_resolved", "n_rows_for_taxa"):
            best = None
            for name, v in candidates.items():
                ok, rel = within_tol(recorded, v)
                if ok and (best is None or abs(v - recorded) < abs(best[1] - recorded)):
                    best = (name, v)
            if best:
                item.update({"observed": best[1], "observed_as": best[0], "within_tolerance": True})
                _, item["relative_diff"] = within_tol(recorded, best[1])
            else:
                item.update({"observed": distinct_keys, "observed_as": "distinct_usage_keys", "within_tolerance": False})
                _, item["relative_diff"] = within_tol(recorded, distinct_keys)
                if c.get("slice") and len(rec.get("slices", [])) > 1:
                    item["note"] = "per-slice count merged into a multi-slice record; the distributions of other slices dilute the comparison"
        else:
            item.update({"observed": None, "within_tolerance": None, "relative_diff": None, "note": "count of a kind that cannot be re-derived from the API (unmatched taxa, components)"})
        rechecks.append(item)
    checks["count_rechecks"] = rechecks
    checks["count_recheck"] = next(({k: it.get(k) for k in ("property_id", "recorded", "observed", "relative_diff", "within_tolerance")} for it in rechecks if it["within_tolerance"] is False),
                                   next(({k: it.get(k) for k in ("property_id", "recorded", "observed", "relative_diff", "within_tolerance")} for it in rechecks if it["within_tolerance"]), None))

    src = SOURCE_SCORES["gbif-backbone-taxonomy"]
    s = dict(src)
    frac = (checks["checksum_summary"]["matching"] / len(comparable)) if comparable else None
    if not checks["identifier_resolves"]:
        integrity = 0.0
    elif frac == 1.0:
        integrity = 1.0
    elif frac is not None and frac >= 0.9:
        integrity = 0.85
        obstacles.append("A few species/{key} or species/match bodies no longer reproduce byte-for-byte although the usage keys are unchanged; the backbone is frozen but the API serialisation of a usage record is not.")
    elif frac is not None and frac >= 0.5:
        integrity = 0.7
    elif frac is not None:
        integrity = 0.5
    else:
        integrity = 0.5
        obstacles.append("No distribution carries a checksum that could be re-verified (the backbone archive was not inspected by the vendor and is only HEAD-checked here).")
    cnt_bad = [it for it in rechecks if it["within_tolerance"] is False]
    if cnt_bad and integrity > 0.7:
        integrity = 0.7
    completeness = 1.0
    if not rec.get("license") or not rec.get("version") or not rec.get("creators"):
        completeness -= 0.2
    if checks["taxa_keys"]["not_resolving"]:
        completeness -= 0.3
    synonyms = [i for i in non_acc if i.get("taxonomicStatus") != "DOUBTFUL"]
    if synonyms:
        completeness -= min(0.2, 0.05 * len(synonyms))
    if orphans:
        completeness -= min(0.2, 0.03 * len(orphans))
    if bad_fallbacks:
        completeness -= min(0.3, 0.1 * len(bad_fallbacks))
    if cnt_bad:
        completeness -= 0.15
    if any(it["within_tolerance"] is None for it in rechecks):
        completeness -= 0.05
    if n_match_key and n_in_taxa < n_match_key:
        completeness -= 0.05  # some matched usage keys are not listed in `taxa` (rejected fallbacks or components)
    if any(not d.get("sha256") for d in rec.get("distributions", []) if not (d.get("download_url") or "").endswith(".zip")):
        completeness -= 0.1
    authenticity = src["authenticity"] if not checks["taxa_keys"]["not_resolving"] else 0.6
    s.update({"integrity": clamp(integrity), "completeness": clamp(completeness), "authenticity": clamp(authenticity)})
    confidence = 0.85 if comparable else 0.6
    if len(rec.get("slices", [])) > 1:
        confidence -= 0.1
        obstacles.append("Merged from several slices; per-slice counts were compared against the union of distributions.")
    rationale = (f"DOI {doi} verified through the handle API (responseCode {checks['doi_check']['response_code']}) and the registry record (licence {checks['dataset_api']['license']}, pubDate {checks['dataset_api']['pubDate']}). "
                 f"Re-fetched {sum(1 for c in checksums if c.get('http_status') == 200)} api.gbif.org distributions, {len(comparable)} of which carry a checksum; {checks['checksum_summary']['matching']} reproduce. {n_match} species/match queries returned {distinct_keys} distinct usage keys, {n_in_taxa} of which are listed in `taxa`, with {n_higherrank} HIGHERRANK matches of which {len(bad_fallbacks)} are fallbacks to another name that were nevertheless listed. "
                 f"{len(resolving)} of {len(taxa_keys)} listed keys resolve ({len(synonyms)} synonyms, {len(non_acc) - len(synonyms)} doubtful, {len(orphans)} higher-rank keys with zero descendants). "
                 + ("Flags: " + "; ".join(flags) + ". " if flags else "")
                 + "Source authority, independence and authenticity inherit from the gbif-backbone-taxonomy source score.")
    return finish(rec, "gbif-backbone-taxonomy", s, confidence, checks, flags, obstacles, rationale)


# ----------------------------------------------------------------------------- IUCN record

def check_iucn(rec: dict, f: Fetcher, tx: TaxonIndex) -> dict:
    checks: dict = {"checked_at": fmt_dt()}
    flags: list[str] = []
    obstacles: list[str] = []
    doi = rec.get("doi") or "10.15468/0qnb58"
    checks["doi_check"] = doi_check(f, doi)
    ds = f.get(f"{API}/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3")
    dsj = body_json(ds) or {}
    checks["dataset_api"] = {"http_status": ds.get("status"), "title": dsj.get("title"), "doi": dsj.get("doi"), "license": dsj.get("license"), "pubDate": (dsj.get("pubDate") or "")[:10], "citation": (dsj.get("citation") or {}).get("text")}
    checks["identifier_resolves"] = checks["doi_check"]["response_code"] == 1 and ds.get("status") == 200
    checks["identifier_checked_via"] = "doi.org handle API + api.gbif.org/v1/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3"
    obstacles.append("www.gbif.org and iucnredlist.org return HTTP 403 to automated clients; identifier verified through the DOI handle API and the registry API.")
    if dsj.get("license") and "by-nc" not in dsj["license"] and "BY-NC" in (rec.get("license") or ""):
        flags.append(f"record_license_says_CC_BY-NC_but_registry_says_{dsj['license']}")

    checksums, categories = [], {}
    for d in rec.get("distributions", []):
        url = d.get("download_url") or ""
        e = f.get(url) if "api.gbif.org" in url else None
        if e is None:
            checksums.append({"url": url, "recorded": d.get("sha256"), "observed": None, "match": None, "note": "not re-fetched"})
            continue
        raw = body_bytes(e) if e.get("status") == 200 else b""
        variants = checksum_variants(raw) if raw else {}
        rec_sha = d.get("sha256")
        match, matched_as = None, None
        if rec_sha and variants:
            for name, h in variants.items():
                if h == rec_sha:
                    match, matched_as = True, name
                    break
            else:
                match = False
        obj = body_json(e) or {}
        m = re.search(r"/species/(\d+)/iucnRedListCategory", url)
        item = {"url": url, "http_status": e.get("status"), "recorded": rec_sha, "observed": variants.get("raw"), "match": match, "matched_as": matched_as,
                "code": obj.get("code"), "category": obj.get("category"), "iucnTaxonID": obj.get("iucnTaxonID"), "scientificName": obj.get("scientificName")}
        if m:
            categories[int(m.group(1))] = item
        checksums.append(item)
    checks["checksums"] = checksums
    comparable = [c for c in checksums if c["match"] is not None]
    checks["checksum_match"] = all(c["match"] for c in comparable) if comparable else None

    # match counts (per-species category codes) to the fetched categories by name slug
    rechecks = []
    by_slug = {}
    for k, it in categories.items():
        proj = tx.project_taxon(f"gbif:{k}")
        if proj:
            by_slug[proj["slug"]] = (k, it)
        if it.get("scientificName"):
            by_slug.setdefault(slugify(" ".join(it["scientificName"].split()[:2])), (k, it))
    for c in rec.get("counts", []):
        pid, recorded, desc = c.get("property_id"), c.get("value"), c.get("description") or ""
        item = {"property_id": pid, "recorded": recorded, "description": desc[:160]}
        if pid == "iucn_category_code":
            slug = desc.split(":")[0].strip()
            code_m = re.search(r"\((LC|NT|VU|EN|CR|EW|EX|DD|NE)\)", desc)
            id_m = re.search(r"IUCN taxon id (\d+)", desc)
            hit = by_slug.get(slug)
            if hit:
                k, it = hit
                obs_code = it.get("code")
                obs_val = IUCN_ORDER.index(obs_code) if obs_code in IUCN_ORDER else None
                item.update({"key": k, "observed_code": obs_code, "recorded_code": code_m.group(1) if code_m else None, "observed": obs_val,
                             "iucn_taxon_id_recorded": id_m.group(1) if id_m else None, "iucn_taxon_id_observed": it.get("iucnTaxonID")})
                item["within_tolerance"] = (obs_val == recorded) and (not code_m or code_m.group(1) == obs_code) and (not id_m or id_m.group(1) == str(it.get("iucnTaxonID")))
                item["relative_diff"] = 0.0 if item["within_tolerance"] else None
            else:
                item.update({"observed": None, "within_tolerance": None, "note": "no distribution for this taxon slug"})
        else:
            # summary counts: recompute from the per-species items
            codes = [it.get("code") for it in categories.values()]
            if pid == "n_taxa_with_category":
                obs = sum(1 for cd in codes if cd and cd != "NE")
            elif pid.startswith("n_taxa_") and pid[7:].upper() in IUCN_ORDER:
                obs = sum(1 for cd in codes if cd == pid[7:].upper())
            else:
                obs = None
            ok, rel = within_tol(recorded, obs)
            item.update({"observed": obs, "within_tolerance": ok, "relative_diff": rel,
                         "note": "recomputed over the distributions actually listed; the record merges slices so this may not equal the slice-level count"})
        rechecks.append(item)
    checks["count_rechecks"] = rechecks
    bad = [it for it in rechecks if it["within_tolerance"] is False]
    checks["count_recheck"] = {k: (bad[0] if bad else rechecks[0]).get(k) for k in ("property_id", "recorded", "observed", "relative_diff", "within_tolerance")} if rechecks else None
    per_species = [it for it in rechecks if it["property_id"] == "iucn_category_code"]
    checks["taxon_key_resolves_to"] = f"{sum(1 for it in per_species if it['within_tolerance'])}/{len(per_species)} per-species categories reproduce"

    src = SOURCE_SCORES["iucn-red-list-via-gbif"]
    s = dict(src)
    n_ok = sum(1 for it in per_species if it["within_tolerance"])
    if not checks["identifier_resolves"]:
        integrity = 0.0
    elif per_species and n_ok == len(per_species):
        integrity = 1.0 if checks["checksum_match"] else 0.9
    elif per_species and n_ok >= 0.9 * len(per_species):
        integrity = 0.7
    else:
        integrity = 0.5
    completeness = 1.0
    if flags:
        completeness -= 0.1
    summary_bad = [it for it in rechecks if it["property_id"] != "iucn_category_code" and it["within_tolerance"] is False]
    if summary_bad:
        completeness -= 0.1
    if any(it["within_tolerance"] is None for it in per_species):
        completeness -= 0.1
    s.update({"integrity": clamp(integrity), "completeness": clamp(completeness)})
    rationale = (f"DOI {doi} verified through the handle API; registry record '{checks['dataset_api']['title']}' (licence {checks['dataset_api']['license']}, pubDate {checks['dataset_api']['pubDate']}). "
                 f"Re-fetched {len(categories)} species/{{key}}/iucnRedListCategory responses: {n_ok} of {len(per_species)} recorded category codes and IUCN taxon ids reproduce; {sum(1 for c in comparable if c['match'])} of {len(comparable)} checksums match. "
                 + ("Flags: " + "; ".join(flags) + ". " if flags else "")
                 + "Source authority, independence and authenticity inherit from the iucn-red-list-via-gbif source score.")
    return finish(rec, "iucn-red-list-via-gbif", s, 0.85, checks, flags, obstacles, rationale)


# ----------------------------------------------------------------------------- assemble

def finish(rec, source_id, scores, confidence, checks, flags, obstacles, rationale) -> dict:
    scores = {k: clamp(scores[k]) for k in ("source-authority", "integrity", "completeness", "independence", "authenticity")}
    ident_exists = bool(checks.get("identifier_resolves"))
    out = OrderedDict()
    out["dataset_id"] = rec["id"]
    out["source_id"] = source_id
    out["scores"] = scores
    out["overall"] = round(overall(scores), 3)
    out["verdict"] = verdict_for(scores, ident_exists)
    out["confidence"] = clamp(confidence)
    out["checks"] = checks
    out["flags"] = flags
    out["obstacles"] = obstacles
    out["rationale"] = rationale
    out["assessor"] = {"kind": "cloud-agent", "model": "claude-fable-5.1", "script": "test-data/organisms/assessment/scripts/recheck_gbif.py", "rubric": "dataset-reliability/0.1.0"}
    return out


def write_batches(results: list[dict]) -> list[Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("batch-*.json"):
        old.unlink()
    files, current, size = [], [], 2
    n = 1

    def flush():
        nonlocal current, size, n
        if not current:
            return
        p = OUT_DIR / f"batch-{n:02d}.json"
        with p.open("w") as fh:
            json.dump(current, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        files.append(p)
        n += 1
        current, size = [], 2

    for r in results:
        s = len(json.dumps(r, indent=1, ensure_ascii=False).encode("utf-8")) + 2
        if current and (size + s > MAX_FILE_BYTES or len(current) >= MAX_PER_FILE):
            flush()
        current.append(r)
        size += s
    flush()
    return files


def report(results: list[dict], fetcher: Fetcher | None = None) -> str:
    lines = []
    v = Counter(r["verdict"] for r in results)
    lines.append(f"records: {len(results)}  verdicts: " + ", ".join(f"{k}={v[k]}" for k in ("reliable", "usable-with-caveats", "needs-repair", "reject")))
    drift = []
    for r in results:
        for it in r["checks"].get("count_rechecks", []):
            if it.get("within_tolerance") is False and it.get("observed") is not None and r["source_id"] == "gbif-occurrence-api":
                drift.append((it.get("relative_diff") or 0, r["dataset_id"], it.get("property_id"), it.get("key") or it.get("keys"), it.get("recorded"), it.get("observed")))
    drift.sort(reverse=True)
    lines.append(f"count comparisons outside tolerance: {len(drift)} (in {len(set(d[1] for d in drift))} records)")
    for d in drift[:10]:
        lines.append(f"  rel={d[0]:.4f} {d[1]} {d[2]} key={d[3]} recorded={d[4]} observed={d[5]}")
    unres = [(r["dataset_id"], k["key"], k.get("http_status")) for r in results for k in r["checks"].get("taxon_keys", []) if not k.get("resolves")]
    lines.append(f"keys that failed to resolve: {len(unres)}")
    for u in unres:
        lines.append(f"  {u}")
    def section(title, pred):
        items = [(r["dataset_id"], fl) for r in results for fl in r["flags"] if pred(fl)]
        lines.append(f"{title}: {len(items)}")
        for d_id, fl in items:
            lines.append(f"  {d_id}: {fl}")

    section("records whose label/id disagree with the key", lambda fl: fl.startswith("label_and_slug_disagree") or fl.startswith("label_name_differs") or fl.startswith("id_slug_differs"))
    section("label is a name variant / synonym of the key (same concept)", lambda fl: fl.startswith("label_name_variant") or fl.startswith("label_is_a_synonym"))
    section("composite or proxy records (group has no backbone usage)", lambda fl: fl.startswith("composite_group") or fl.startswith("single_proxy_key"))
    section("orphaned higher-rank keys (family or above, zero descendants)", lambda fl: fl.startswith("primary_key_orphaned_higher_rank"))
    section("zero counts for higher taxa", lambda fl: fl.startswith("zero_count_for_higher_taxon"))
    section("zero counts for genera/species", lambda fl: fl.startswith("zero_count_for_") and not fl.startswith("zero_count_for_higher"))
    section("primary key not ACCEPTED", lambda fl: fl.startswith("primary_key_status"))
    section("genus keys without species in the backbone", lambda fl: fl.startswith("primary_key_genus_without"))
    section("taxa-slug disagreements", lambda fl: fl.startswith("taxa_"))
    section("backbone-record flags", lambda fl: fl[0].isdigit())
    cs = Counter(("match" if r["checks"].get("checksum_match") else ("mismatch" if r["checks"].get("checksum_match") is False else "n/a")) for r in results)
    lines.append(f"checksum status: {dict(cs)}")
    if fetcher:
        lines.append(f"http: {dict(fetcher.stats)}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="ignore the on-disk cache")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N records (debugging)")
    ap.add_argument("--only", default=None, help="substring filter on dataset id (debugging)")
    ap.add_argument("--report", action="store_true", help="print the summary report after writing")
    ap.add_argument("--no-write", action="store_true", help="do not write batch files")
    args = ap.parse_args(argv)

    with MERGED.open() as fh:
        all_records = json.load(fh)
    with TAXA.open() as fh:
        taxa_json = json.load(fh)
    batch = [r for r in all_records if r["id"].startswith(BATCH_PREFIXES)]
    if args.only:
        batch = [r for r in batch if args.only in r["id"]]
    if args.limit:
        batch = batch[: args.limit]
    print(f"{len(batch)} records in batch", file=sys.stderr)

    f = Fetcher(refresh=args.refresh)
    tx = TaxonIndex(f, taxa_json)

    # one probe of the public site so the 403 is observed, not assumed
    probe = f.get("https://www.gbif.org/occurrence/search?taxon_key=2222298")
    print(f"www.gbif.org probe: HTTP {probe.get('status')}", file=sys.stderr)

    # round 1: everything we can list from the records
    urls = []
    for r in batch:
        for d in r.get("distributions", []):
            u = d.get("download_url") or ""
            if "api.gbif.org" in u and not u.endswith(".zip"):
                urls.append(u)
        if "api.gbif.org" in (r.get("identifier") or ""):
            urls.append(r["identifier"])
        keys = identifier_keys(r.get("identifier") or "") + [int(t.split(":")[1]) for t in r.get("taxa", []) if t.startswith("gbif:")]
        for c in r.get("counts", []):
            keys += keys_in_text(c.get("description"))
        for k in OrderedDict.fromkeys(keys):
            urls.append(f"{API}/species/{k}")
            if r["id"].startswith(("gbif-occurrences-", "gbif-occurrence-")):
                urls.append(count_url(k, False))
    print(f"prefetching {len(set(urls))} URLs", file=sys.stderr)
    t0 = time.time()
    f.prefetch(urls)
    print(f"prefetch done in {time.time() - t0:.0f}s: {dict(f.stats)}", file=sys.stderr)

    results = []
    for i, r in enumerate(batch, 1):
        if r["id"].startswith("gbif-backbone-"):
            res = check_backbone(r, f, tx)
        elif r["id"].startswith("iucn-red-list-via-gbif-"):
            res = check_iucn(r, f, tx)
        else:
            res = check_occurrence(r, f, tx)
        results.append(res)
        if i % 100 == 0:
            print(f"  {i}/{len(batch)} checked ({dict(f.stats)})", file=sys.stderr)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with RAW_OUT.open("w") as fh:
        json.dump(results, fh, indent=1)
    if not args.no_write:
        files = write_batches(results)
        for p in files:
            print(f"wrote {p.relative_to(REPO)} ({p.stat().st_size / 1024:.0f} KB)", file=sys.stderr)
    if args.report:
        print(report(results, f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
