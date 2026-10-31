#!/usr/bin/env python3
"""Re-check and score the NCBI records in organisms/merged/datasets.json.

Batch: every record whose id starts with ``ncbi-genome-`` (one GCA_/GCF_ assembly),
``ncbi-genomes-`` (genome count for a higher taxon) or ``ncbi-taxonomy-`` (E-utilities
taxid lookups). For each record the script

* parses the accession and/or NCBI taxid from the identifier, distributions and counts;
* re-queries NCBI Datasets v2 (``genome/accession/<acc>/dataset_report``,
  ``genome/taxon/<taxid>/dataset_report``, ``taxonomy/taxon/<taxid>``) and, when Datasets
  returns nothing for an accession, E-utilities ``esearch``/``esummary`` with ``db=assembly``
  to tell "superseded" from "does not exist";
* confirms the accession exists and is current, whether it is the reference assembly for
  the organism and for the taxon the record was built for, that the organism is the record's
  taxon (or nested in it), and that assembly level, total length, N50s, chromosome count,
  release date and gene counts match what NCBI reports now;
* re-queries every recorded taxon count and compares it with tolerance
  (relative <= 0.5 % or absolute <= 5);
* re-downloads every small distribution that carries a SHA-256 and recomputes it;
* scores the five rubric dimensions and writes ``records/ncbi/batch-NN.json``.

Requests are rate-limited to 3/s (10/s with ``NCBI_API_KEY`` set) and cached under
``scripts/cache/`` (gitignored) so a re-run is cheap and reproducible.

Usage:  python3 organisms/assessment/scripts/recheck_ncbi.py [--limit N] [--ids ID ...]
        [--batch-size 100] [--refresh]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

HERE = Path(__file__).resolve().parent
ASSESSMENT = HERE.parent
REPO = ASSESSMENT.parent.parent
MERGED = REPO / "organisms" / "merged"
CACHE = HERE / "cache"
OUT_DIR = ASSESSMENT / "records" / "ncbi"
RUBRIC = json.loads((ASSESSMENT / "rubric.json").read_text())
SOURCES = {
    "ncbi-assembly": json.loads((ASSESSMENT / "sources" / "ncbi-assembly.json").read_text()),
    "ncbi-taxonomy": json.loads((ASSESSMENT / "sources" / "ncbi-taxonomy.json").read_text()),
}

DATASETS = "https://api.ncbi.nlm.nih.gov/datasets/v2"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY")
MIN_INTERVAL = 0.105 if API_KEY else 0.34  # 10/s with a key, 3/s without
MAX_CHECKSUM_BYTES = 5_000_000
REL_TOL = 0.005
ABS_TOL = 5
USER_AGENT = "delphi-organisms-assessment/0.1 (recheck_ncbi.py)"

ACC_RE = re.compile(r"(GC[AF]_\d{9}\.\d+)")
TAXON_URL_RE = re.compile(r"/genome/taxon/(\d+)/dataset_report")
LEVELS = {"complete genome": "Complete Genome", "chromosome": "Chromosome", "scaffold": "Scaffold", "contig": "Contig"}

# record count property -> (observed field path, kind)
STAT_PROPS = {
    "total_sequence_length_bp": ("assembly_stats.total_sequence_length", "int"),
    "total_sequence_length": ("assembly_stats.total_sequence_length", "int"),
    "genome_total_sequence_length_bp": ("assembly_stats.total_sequence_length", "int"),
    "contig_n50_bp": ("assembly_stats.contig_n50", "int"),
    "contig_n50": ("assembly_stats.contig_n50", "int"),
    "scaffold_n50_bp": ("assembly_stats.scaffold_n50", "int"),
    "scaffold_n50": ("assembly_stats.scaffold_n50", "int"),
    "n_chromosomes": ("assembly_stats.total_number_of_chromosomes", "int"),
    "number_of_chromosomes": ("assembly_stats.total_number_of_chromosomes", "int"),
    "n_contigs": ("assembly_stats.number_of_contigs", "int"),
    "number_of_contigs": ("assembly_stats.number_of_contigs", "int"),
    "n_scaffolds": ("assembly_stats.number_of_scaffolds", "int"),
    "number_of_scaffolds": ("assembly_stats.number_of_scaffolds", "int"),
    "gc_percent": ("assembly_stats.gc_percent", "float"),
    "n_genes_annotated": ("annotation_info.stats.gene_counts.total", "int"),
    "busco_complete_fraction": ("annotation_info.busco.complete", "float"),
    "ncbi_taxid": ("organism.tax_id", "exact"),
}
TAXON_COUNT_PROPS = {
    "n_assemblies_for_taxon": "all",
    "n_assemblies": "all",
    "n_reference_genomes": "reference",
    "n_reference_assemblies": "reference",
    "n_reference_assemblies_for_taxon": "reference",
    "n_assemblies_matching_query": "query",
    "n_assemblies_reported": "query",
}
UNCHECKABLE_PROPS = {"n_rows_for_taxa", "n_taxa_matched", "n_taxa_resolved", "n_taxa_unresolved", "n_taxa_queried"}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def getpath(obj: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(obj, dict) or part not in obj:
            return None
        obj = obj[part]
    return obj


def within_tolerance(recorded: float, observed: float) -> tuple[float | None, bool]:
    if recorded is None or observed is None:
        return None, False
    diff = abs(float(recorded) - float(observed))
    rel = diff / abs(float(observed)) if observed else (0.0 if diff == 0 else None)
    ok = diff <= ABS_TOL or (rel is not None and rel <= REL_TOL)
    return (round(rel, 6) if rel is not None else None), ok


class Fetcher:
    """Rate-limited, disk-cached HTTP GET. Caches bodies by URL so a re-run is offline."""

    def __init__(self, cache_dir: Path, refresh: bool = False):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh = refresh
        self.last = 0.0
        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.requests_made = 0
        self.refreshed: set[str] = set()

    def _key(self, url: str) -> Path:
        return self.cache_dir / hashlib.sha1(url.encode()).hexdigest()

    def _ncbi_url(self, url: str) -> str:
        if API_KEY and ("ncbi.nlm.nih.gov" in url) and "api_key=" not in url:
            return url + ("&" if "?" in url else "?") + "api_key=" + API_KEY
        return url

    def get(self, url: str, max_bytes: int | None = None) -> dict:
        key = self._key(url)
        meta_path = key.with_suffix(".json")
        if meta_path.exists() and not (self.refresh and url not in self.refreshed):
            meta = json.loads(meta_path.read_text())
            if meta.get("body_file"):
                meta["body"] = (self.cache_dir / meta["body_file"]).read_bytes()
            return meta
        for attempt in range(5):
            wait = self.last + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.last = time.monotonic()
            self.requests_made += 1
            try:
                resp = self.session.get(self._ncbi_url(url), timeout=60, stream=True)
                if resp.status_code == 429 or resp.status_code >= 500:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                body = b""
                for chunk in resp.iter_content(65536):
                    body += chunk
                    if max_bytes is not None and len(body) > max_bytes:
                        break
                meta = {
                    "url": url,
                    "status": resp.status_code,
                    "final_url": resp.url.replace(API_KEY, "[KEY]") if API_KEY else resp.url,
                    "fetched_at": now_iso(),
                    "content_length_header": resp.headers.get("Content-Length"),
                    "truncated": bool(max_bytes is not None and len(body) > max_bytes),
                }
                break
            except requests.RequestException as exc:
                meta = {"url": url, "status": None, "error": str(exc), "fetched_at": now_iso(), "truncated": False}
                body = b""
                time.sleep(1.5 * (attempt + 1))
        meta["byte_size"] = len(body)
        meta["sha256"] = sha256_bytes(body) if body else None
        body_file = key.name + ".bin"
        (self.cache_dir / body_file).write_bytes(body)
        meta["body_file"] = body_file
        meta_path.write_text(json.dumps(meta))
        self.refreshed.add(url)
        meta["body"] = body
        return meta

    def get_json(self, url: str) -> tuple[dict, Any]:
        meta = self.get(url)
        data = None
        if meta.get("status") == 200 and meta.get("body"):
            try:
                data = json.loads(meta["body"])
            except json.JSONDecodeError:
                data = None
        return meta, data


# --------------------------------------------------------------------------- NCBI lookups

class NCBI:
    def __init__(self, fetcher: Fetcher):
        self.f = fetcher
        self._tax_cache: dict[int, dict | None] = {}

    def accession_report(self, acc: str) -> tuple[dict, dict | None]:
        meta, data = self.f.get_json(f"{DATASETS}/genome/accession/{acc}/dataset_report")
        reports = (data or {}).get("reports") or []
        return meta, (reports[0] if reports else None)

    def eutils_assembly(self, acc: str) -> dict | None:
        """Entrez Assembly summary for an accession, or None when Entrez has never heard of it."""
        _, es = self.f.get_json(f"{EUTILS}/esearch.fcgi?db=assembly&term={acc}&retmode=json")
        ids = ((es or {}).get("esearchresult") or {}).get("idlist") or []
        if not ids:
            return None
        _, summ = self.f.get_json(f"{EUTILS}/esummary.fcgi?db=assembly&id={ids[0]}&retmode=json")
        res = (summ or {}).get("result") or {}
        doc = res.get(ids[0])
        return doc if isinstance(doc, dict) else None

    def taxon_report(self, taxid: int, reference_only: bool, page_size: int = 200, max_pages: int = 10) -> tuple[int | None, list[dict]]:
        base = f"{DATASETS}/genome/taxon/{taxid}/dataset_report?"
        if reference_only:
            base += "filters.reference_only=true&"
        base += f"page_size={page_size}"
        total, reports, token = None, [], None
        for _ in range(max_pages):
            url = base + (f"&page_token={token}" if token else "")
            _, data = self.f.get_json(url)
            if data is None:
                break
            total = data.get("total_count", 0 if not data.get("reports") else total)
            reports.extend(data.get("reports") or [])
            token = data.get("next_page_token")
            if not token:
                break
        return total, reports

    def taxon_count_for_url(self, url: str) -> tuple[dict, int | None]:
        """total_count of an arbitrary recorded taxon dataset_report URL (also used for checksums)."""
        meta, data = self.f.get_json(url)
        if data is None:
            return meta, None
        if "total_count" in data:
            return meta, data["total_count"]
        return meta, (0 if data == {} or not data.get("reports") else len(data.get("reports")))

    def taxonomy(self, taxid: int) -> dict | None:
        if taxid in self._tax_cache:
            return self._tax_cache[taxid]
        _, data = self.f.get_json(f"{DATASETS}/taxonomy/taxon/{taxid}")
        node = None
        for n in (data or {}).get("taxonomy_nodes") or []:
            if "taxonomy" in n:
                node = n["taxonomy"]
                break
        self._tax_cache[taxid] = node
        return node


# --------------------------------------------------------------------------- record parsing

def parse_record(rec: dict, taxa: dict[str, dict]) -> dict:
    p: dict[str, Any] = {}
    rid = rec["id"]
    p["kind"] = "genome" if rid.startswith("ncbi-genome-") else "genomes" if rid.startswith("ncbi-genomes-") else "taxonomy"
    m = ACC_RE.search(rec.get("identifier", "")) or ACC_RE.search(rid.upper().replace("-", "_", 2))
    if p["kind"] == "genome":
        # id slug is like ncbi-genome-gca-000001405-29 -> GCA_000001405.29
        mm = re.match(r"ncbi-genome-(gc[af])-(\d{9})-(\d+)$", rid)
        p["accession"] = (m.group(1) if m else None) or (f"{mm.group(1).upper()}_{mm.group(2)}.{mm.group(3)}" if mm else None)
    else:
        p["accession"] = None
    taxon_urls = []
    for d in rec.get("distributions", []):
        u = d.get("download_url", "")
        tm = TAXON_URL_RE.search(u)
        if tm:
            q = parse_qs(urlparse(u).query)
            taxon_urls.append({
                "url": u,
                "taxid": int(tm.group(1)),
                "reference_only": q.get("filters.reference_only", ["false"])[0] == "true",
                "other_filters": sorted(k for k in q if k.startswith("filters.") and k != "filters.reference_only"),
            })
    p["taxon_urls"] = taxon_urls
    ident_tax = re.search(r"/datasets/taxonomy/(\d+)/?", rec.get("identifier", ""))
    p["identifier_taxid"] = int(ident_tax.group(1)) if ident_tax else None
    recorded_org_taxid = None
    for src in (rec.get("extra") or {}, rec.get("assembly") or {}, rec):
        for k in ("tax_id", "organism_taxid", "ncbi_taxid"):
            v = src.get(k)
            if isinstance(v, int):
                recorded_org_taxid = v
    for c in rec.get("counts", []):
        if c.get("property_id") == "ncbi_taxid":
            recorded_org_taxid = c.get("value")
    p["recorded_organism_taxid"] = recorded_org_taxid
    p["taxa"] = []
    for key in rec.get("taxa", []):
        t = taxa.get(key)
        if t:
            p["taxa"].append({"key": key, "name": t.get("accepted_name"), "rank": t.get("rank"), "ncbi_taxid": (t.get("identifiers") or {}).get("ncbi_taxid")})
    taxids = {u["taxid"] for u in taxon_urls}
    if p["identifier_taxid"]:
        taxids.add(p["identifier_taxid"])
    taxids |= {t["ncbi_taxid"] for t in p["taxa"] if t.get("ncbi_taxid")}
    p["record_taxids"] = sorted(taxids)
    # recorded assembly level
    level = None
    for src in (rec.get("extra") or {}, rec.get("assembly") or {}, rec):
        if isinstance(src.get("assembly_level"), str):
            level = src["assembly_level"]
    if not level:
        text = " ".join(str(rec.get(k, "")) for k in ("measurement_technique", "label", "role", "bibliographic_citation"))
        lm = re.search(r"\b(Complete Genome|Chromosome|Scaffold|Contig)\b", text)
        level = lm.group(1) if lm else None
    p["recorded_level"] = level
    p["recorded_release_date"] = (rec.get("extra") or {}).get("release_date") or (rec.get("assembly") or {}).get("release_date") or rec.get("issued")
    text = (rec.get("label", "") + " " + rec.get("measurement_technique", "") + " " + str(rec.get("extra", {}).get("refseq_category", "")) + " " + str(rec.get("assembly", {}).get("refseq_category", ""))).lower()
    p["reference_claimed"] = "reference" in text
    bp = re.search(r"\b(PRJ[DEN][A-Z]\d+)\b", str(rec.get("is_referenced_by") or "")) or re.search(r"\b(PRJ[DEN][A-Z]\d+)\b", rec.get("bibliographic_citation", ""))
    p["recorded_bioproject"] = bp.group(1) if bp else None
    return p


# --------------------------------------------------------------------------- checks

def check_checksums(rec: dict, ncbi: NCBI, obstacles: list[str]) -> tuple[list[dict], bool | None]:
    seen = {}
    for d in rec.get("distributions", []):
        if d.get("sha256") and d["download_url"] not in seen:
            seen[d["download_url"]] = d
    results = []
    for url, d in seen.items():
        if (d.get("byte_size") or 0) > MAX_CHECKSUM_BYTES or url.endswith((".zip", ".tar.gz")):
            results.append({"url": url, "recorded_sha256": d["sha256"], "observed_sha256": None, "match": None, "note": "not re-downloaded (large or assembled-on-demand archive)"})
            continue
        meta = ncbi.f.get(url, max_bytes=MAX_CHECKSUM_BYTES)
        if meta.get("status") != 200:
            results.append({"url": url, "recorded_sha256": d["sha256"], "observed_sha256": None, "match": None, "http_status": meta.get("status"), "note": meta.get("error") or "download failed"})
            obstacles.append(f"could not re-download {url} (HTTP {meta.get('status')})")
            continue
        results.append({
            "url": url,
            "recorded_sha256": d["sha256"],
            "observed_sha256": meta["sha256"],
            "recorded_byte_size": d.get("byte_size"),
            "observed_byte_size": meta["byte_size"],
            "match": meta["sha256"] == d["sha256"],
            "live_api_response": "api.ncbi.nlm.nih.gov" in url or "eutils" in url,
        })
    if not results or all(r["match"] is None for r in results):
        return results, None
    return results, all(r["match"] is True for r in results if r["match"] is not None)


def recheck_genome(rec: dict, p: dict, ncbi: NCBI) -> dict:
    """Checks for one GCA_/GCF_ record. Returns the checks dict plus derived flags."""
    acc = p["accession"]
    obstacles: list[str] = []
    checks: dict[str, Any] = {"checked_at": now_iso(), "accession": acc}
    flags: dict[str, Any] = {"exists": None, "status": None, "organism_match": None, "stats_ok": True, "counts_ok": True,
                             "level_match": None, "date_match": None, "ref_for_taxon": None, "ref_for_organism": None, "unverified": []}
    meta, report = ncbi.accession_report(acc)
    if meta.get("status") != 200:
        obstacles.append(f"Datasets accession endpoint returned HTTP {meta.get('status')}")
    entrez = None
    if report is None:
        entrez = ncbi.eutils_assembly(acc)
        if entrez is None:
            flags["exists"] = False
            flags["status"] = "does-not-exist"
            checks.update({"identifier_resolves": False, "accession_status": "does-not-exist", "datasets_report": "empty", "entrez_assembly": "no record"})
            return {"checks": checks, "flags": flags, "obstacles": obstacles}
        flags["exists"] = True
        props = entrez.get("propertylist") or []
        latest = entrez.get("latestaccession") or None
        flags["status"] = "superseded" if ("replaced" in props or (latest and latest != acc)) else ("suppressed" if "suppressed" in " ".join(props) else "not-in-datasets")
        checks.update({
            "identifier_resolves": True,
            "accession_status": flags["status"],
            "datasets_report": "empty",
            "entrez_assembly": {"assembly_status": entrez.get("assemblystatus"), "latest_accession": latest, "organism": entrez.get("organism"), "tax_id": entrez.get("taxid"), "properties": props},
            "current_accession": latest or acc,
        })
        obs_level = entrez.get("assemblystatus")
        obs_name = (entrez.get("organism") or "").split(" (")[0]
        obs_taxid = int(entrez["taxid"]) if str(entrez.get("taxid", "")).isdigit() else None
        obs_date = (entrez.get("asmreleasedate_genbank") or "")[:10].replace("/", "-") or None
        stats = {}
        paired = (entrez.get("synonym") or {}).get("genbank" if acc.startswith("GCF") else "refseq")
        refseq_cat = entrez.get("refseq_category")
    else:
        flags["exists"] = True
        info = report.get("assembly_info") or {}
        status = info.get("assembly_status") or "current"
        cur = report.get("current_accession") or acc
        if status != "current":
            flags["status"] = status
        elif cur != acc:
            flags["status"] = "superseded"
        else:
            flags["status"] = "current"
        obs_level = info.get("assembly_level")
        obs_name = (report.get("organism") or {}).get("organism_name")
        obs_taxid = (report.get("organism") or {}).get("tax_id")
        obs_date = info.get("release_date")
        stats = report
        paired = report.get("paired_accession")
        refseq_cat = info.get("refseq_category")
        checks.update({
            "identifier_resolves": True,
            "accession_status": flags["status"],
            "current_accession": cur,
            "paired_accession": paired,
            "source_database": report.get("source_database"),
            "refseq_category": refseq_cat,
            "assembly_name": info.get("assembly_name"),
            "bioproject": info.get("bioproject_accession"),
            "submitter": info.get("submitter"),
        })
    checks["organism_observed"] = {"tax_id": obs_taxid, "organism_name": obs_name}

    # organism vs the record's taxa (exact taxid or nested under it)
    lineage = []
    obs_node = ncbi.taxonomy(obs_taxid) if obs_taxid else None
    if obs_node:
        lineage = [obs_taxid] + list(obs_node.get("lineage") or [])
    elif obs_taxid:
        obstacles.append(f"could not fetch NCBI lineage for organism taxid {obs_taxid}")
    taxon_matches = []
    for t in p["taxa"]:
        tid = t.get("ncbi_taxid")
        node = ncbi.taxonomy(tid) if tid else None
        taxon_matches.append({
            "taxon_key": t["key"],
            "taxon_name": t["name"],
            "taxon_ncbi_taxid": tid,
            "ncbi_name_for_taxid": node.get("organism_name") if node else None,
            "organism_is_or_nested_in_taxon": (tid in lineage) if (tid and lineage) else None,
        })
    rec_taxids = set(p["record_taxids"])
    if p["recorded_organism_taxid"]:
        rec_taxids.add(p["recorded_organism_taxid"])
    if lineage:
        flags["organism_match"] = any(tid in lineage for tid in rec_taxids)
    checks["taxon_key_resolves_to"] = "; ".join(f"{t['taxon_name']} -> NCBI {t['ncbi_name_for_taxid']}" for t in taxon_matches if t["ncbi_name_for_taxid"]) or None
    checks["taxon_checks"] = taxon_matches
    checks["organism_matches_record_taxon"] = flags["organism_match"]
    if p["recorded_organism_taxid"] and obs_taxid:
        checks["recorded_organism_taxid_match"] = p["recorded_organism_taxid"] == obs_taxid

    # assembly level / release date
    if p["recorded_level"] and obs_level:
        flags["level_match"] = LEVELS.get(p["recorded_level"].lower(), p["recorded_level"]) == obs_level
    checks["assembly_level"] = {"recorded": p["recorded_level"], "observed": obs_level, "match": flags["level_match"]}
    if p["recorded_release_date"] and obs_date:
        flags["date_match"] = p["recorded_release_date"][:10] == obs_date[:10]
    checks["release_date"] = {"recorded": p["recorded_release_date"], "observed": obs_date, "match": flags["date_match"]}
    obs_bp = checks.get("bioproject")
    flags["bioproject_match"] = (p["recorded_bioproject"] == obs_bp) if (p["recorded_bioproject"] and obs_bp) else None
    checks["bioproject_check"] = {"recorded": p["recorded_bioproject"], "observed": obs_bp, "match": flags["bioproject_match"]}
    ver = str(rec.get("version") or "")
    asm_name = checks.get("assembly_name") or (entrez or {}).get("assemblyname")
    flags["version_consistent"] = None
    if ver and (asm_name or acc):
        flags["version_consistent"] = (acc in ver) or bool(asm_name and asm_name.lower() in ver.lower())
    checks["version_check"] = {"recorded": ver or None, "assembly_name": asm_name, "consistent": flags["version_consistent"]}

    # reference status for the organism and for the record's taxon
    ref_check: dict[str, Any] = {"refseq_category_of_accession": refseq_cat}
    if obs_taxid:
        total, reps = ncbi.taxon_report(obs_taxid, reference_only=True, page_size=20, max_pages=1)
        accs = [(r.get("accession"), r.get("paired_accession")) for r in reps]
        flags["ref_for_organism"] = any(acc in pair for pair in accs) if total is not None else None
        ref_check["organism_taxid"] = obs_taxid
        ref_check["organism_reference_assemblies"] = [a for a, _ in accs][:5]
        ref_check["is_reference_for_organism"] = flags["ref_for_organism"]
    ref_taxids = sorted({u["taxid"] for u in p["taxon_urls"] if u["reference_only"]} or {t["ncbi_taxid"] for t in p["taxa"] if t.get("ncbi_taxid")})
    ref_check["record_taxids"] = ref_taxids
    for_taxon = None
    for tid in ref_taxids:
        if tid == obs_taxid and flags["ref_for_organism"] is not None:
            for_taxon = flags["ref_for_organism"] if for_taxon is None else (for_taxon or flags["ref_for_organism"])
            continue
        total, reps = ncbi.taxon_report(tid, reference_only=True, page_size=200, max_pages=10)
        if total is None:
            continue
        found = any(acc in (r.get("accession"), r.get("paired_accession")) for r in reps)
        complete = len(reps) >= total
        ref_check[f"reference_set_taxid_{tid}"] = {"total_count": total, "accession_in_set": found, "set_fully_scanned": complete}
        if found:
            for_taxon = True
        elif complete and for_taxon is None:
            for_taxon = False
    flags["ref_for_taxon"] = for_taxon
    ref_check["is_reference_for_record_taxon"] = for_taxon
    ref_check["reference_claimed_by_record"] = p["reference_claimed"]
    checks["reference_status"] = ref_check

    # recorded statistics and taxon counts
    stats_recheck = []
    count_recheck = None
    url_counts: dict[str, int | None] = {}
    for u in p["taxon_urls"]:
        _, c = ncbi.taxon_count_for_url(u["url"])
        url_counts[u["url"]] = c
    for c in rec.get("counts", []):
        pid = c.get("property_id")
        rv = c.get("value")
        entry: dict[str, Any] = {"property_id": pid, "recorded": rv, "slice": c.get("slice")}
        if pid in STAT_PROPS:
            path, kind = STAT_PROPS[pid]
            ov = getpath(stats, path) if stats else None
            if ov is None and entrez and pid == "ncbi_taxid":
                ov = obs_taxid
            if ov is None and rv is None:
                entry.update({"observed": None, "within_tolerance": None, "note": "recorded as null and NCBI reports no value either"})
            elif ov is None:
                entry.update({"observed": None, "within_tolerance": None, "note": "field not in current NCBI report"})
                flags["unverified"].append(pid)
            else:
                try:
                    ovn = float(ov)
                except (TypeError, ValueError):
                    ovn = None
                if kind == "exact":
                    entry.update({"observed": ov, "within_tolerance": rv == ov})
                elif kind == "float":
                    rel, ok = within_tolerance(rv, ovn)
                    ok = ok or (rv is not None and ovn is not None and abs(float(rv) - ovn) <= 0.05)
                    entry.update({"observed": ovn, "relative_diff": rel, "within_tolerance": ok})
                else:
                    rel, ok = within_tolerance(rv, ovn)
                    entry.update({"observed": int(ovn) if ovn is not None else None, "relative_diff": rel, "within_tolerance": ok})
                if entry["within_tolerance"] is False:
                    if pid in ("n_genes_annotated", "busco_complete_fraction"):
                        entry["note"] = "annotation-release dependent; drift expected"
                        flags["unverified"].append(pid)
                    else:
                        flags["stats_ok"] = False
            stats_recheck.append(entry)
        elif pid in TAXON_COUNT_PROPS:
            want = TAXON_COUNT_PROPS[pid]
            cands = [u for u in p["taxon_urls"] if (want == "query") or (u["reference_only"] == (want == "reference"))]
            desc = (c.get("description") or "").lower()
            if want == "query" and len({u["reference_only"] for u in cands}) > 1:
                cands = [u for u in cands if u["reference_only"] == ("reference" in desc)]
            observed = None
            url_used = None
            for u in cands:
                if url_counts.get(u["url"]) is not None:
                    observed, url_used = url_counts[u["url"]], u["url"]
                    break
            if observed is None and not cands and p["record_taxids"]:
                # no recorded query URL: re-query the taxon directly
                tid = p["taxa"][0]["ncbi_taxid"] if p["taxa"] and p["taxa"][0].get("ncbi_taxid") else p["record_taxids"][0]
                total, _ = ncbi.taxon_report(tid, reference_only=(want == "reference"), page_size=1, max_pages=1)
                observed, url_used = total, f"taxon {tid} reference_only={want == 'reference'}"
            rel, ok = within_tolerance(rv, observed) if observed is not None else (None, None)
            entry.update({"observed": observed, "relative_diff": rel, "within_tolerance": ok, "query": url_used})
            if observed is None:
                flags["unverified"].append(pid)
            elif not ok:
                flags["counts_ok"] = False
            if count_recheck is None:
                count_recheck = entry
            else:
                stats_recheck.append(entry)
        elif pid in UNCHECKABLE_PROPS:
            entry.update({"observed": None, "within_tolerance": None, "note": "describes the record itself; not re-checkable against NCBI"})
            stats_recheck.append(entry)
        else:
            entry.update({"observed": None, "within_tolerance": None, "note": "no re-check implemented"})
            flags["unverified"].append(pid)
            stats_recheck.append(entry)
    checks["count_recheck"] = count_recheck
    checks["stats_recheck"] = stats_recheck

    cs, cs_all = check_checksums(rec, ncbi, obstacles)
    checks["checksum_match"] = cs_all
    checks["checksums"] = cs
    return {"checks": checks, "flags": flags, "obstacles": obstacles}


def recheck_genomes(rec: dict, p: dict, ncbi: NCBI) -> dict:
    obstacles: list[str] = []
    checks: dict[str, Any] = {"checked_at": now_iso()}
    flags: dict[str, Any] = {"exists": None, "organism_match": None, "counts_ok": True, "unverified": []}
    tid = p["identifier_taxid"] or (p["taxon_urls"][0]["taxid"] if p["taxon_urls"] else None)
    node = ncbi.taxonomy(tid) if tid else None
    flags["exists"] = bool(node)
    checks["identifier_resolves"] = bool(node)
    checks["taxid"] = tid
    checks["taxon_key_resolves_to"] = node.get("organism_name") if node else None
    checks["ncbi_rank"] = node.get("rank") if node else None
    # does the record's taxon (via taxa.json) agree with the taxid queried?
    tm = []
    for t in p["taxa"]:
        tm.append({"taxon_key": t["key"], "taxon_name": t["name"], "taxon_ncbi_taxid": t.get("ncbi_taxid"), "same_taxid_as_query": t.get("ncbi_taxid") == tid})
    checks["taxon_checks"] = tm
    flags["taxon_relation"] = None
    if tm:
        if any(x["same_taxid_as_query"] for x in tm):
            flags["organism_match"] = True
            flags["taxon_relation"] = "same"
        elif node:
            lin = set(node.get("lineage") or [])
            if any(x["taxon_ncbi_taxid"] in lin for x in tm):
                flags["organism_match"] = True
                flags["taxon_relation"] = "queried taxon is nested in the record's taxon"
            else:
                for x in tm:
                    tnode = ncbi.taxonomy(x["taxon_ncbi_taxid"]) if x.get("taxon_ncbi_taxid") else None
                    if tnode and tid in set(tnode.get("lineage") or []):
                        flags["organism_match"] = True
                        flags["taxon_relation"] = "queried taxon is an ancestor of the record's taxon (count covers a broader group)"
                        break
                else:
                    flags["organism_match"] = False
                    flags["taxon_relation"] = "unrelated"
    checks["organism_matches_record_taxon"] = flags["organism_match"]
    checks["taxon_relation"] = flags["taxon_relation"]
    url_counts = {}
    for u in p["taxon_urls"]:
        _, c = ncbi.taxon_count_for_url(u["url"])
        url_counts[u["url"]] = c
    count_recheck = None
    others = []
    for c in rec.get("counts", []):
        pid = c.get("property_id")
        want = TAXON_COUNT_PROPS.get(pid, "query")
        cands = [u for u in p["taxon_urls"] if want == "query" or u["reference_only"] == (want == "reference")]
        observed, used = None, None
        for u in cands:
            if url_counts.get(u["url"]) is not None:
                observed, used = url_counts[u["url"]], u["url"]
                break
        if observed is None and tid:
            total, _ = ncbi.taxon_report(tid, reference_only=(want != "all"), page_size=1, max_pages=1)
            observed, used = total, f"taxon {tid} reference_only={want != 'all'}"
        rel, ok = within_tolerance(c.get("value"), observed) if observed is not None else (None, None)
        entry = {"property_id": pid, "recorded": c.get("value"), "observed": observed, "relative_diff": rel, "within_tolerance": ok, "query": used}
        if observed is None:
            flags["unverified"].append(pid)
            obstacles.append(f"could not re-query count {pid}")
        elif not ok:
            flags["counts_ok"] = False
        if count_recheck is None:
            count_recheck = entry
        else:
            others.append(entry)
    checks["count_recheck"] = count_recheck
    checks["stats_recheck"] = others
    first = re.search(r"first listed: (GC[AF]_\d{9}\.\d+)", rec.get("role", ""))
    if first and tid:
        _, reps = ncbi.taxon_report(tid, reference_only=True, page_size=1, max_pages=1)
        checks["first_listed_reference"] = {"recorded": first.group(1), "observed": reps[0].get("accession") if reps else None, "match": bool(reps) and reps[0].get("accession") == first.group(1)}
    cs, cs_all = check_checksums(rec, ncbi, obstacles)
    checks["checksum_match"] = cs_all
    checks["checksums"] = cs
    return {"checks": checks, "flags": flags, "obstacles": obstacles}


def recheck_taxonomy(rec: dict, p: dict, ncbi: NCBI) -> dict:
    obstacles: list[str] = []
    checks: dict[str, Any] = {"checked_at": now_iso()}
    flags: dict[str, Any] = {"exists": True, "lookups_ok": True, "unverified": []}
    home = ncbi.f.get(rec["identifier"])
    checks["identifier_resolves"] = home.get("status") == 200
    checks["identifier_final_url"] = home.get("final_url")
    flags["exists"] = checks["identifier_resolves"]
    lookups = []
    n_ok = n_bad = n_unchecked = 0
    for d in rec.get("distributions", []):
        url = d["download_url"]
        if "esearch.fcgi" in url:
            meta, data = ncbi.f.get_json(url)
            ids = ((data or {}).get("esearchresult") or {}).get("idlist") if data else None
            expected = re.search(r"->\s*taxid\s*(\d+)", d.get("description") or "")
            entry = {"url": url, "http_status": meta.get("status"), "idlist": ids}
            if ids is None:
                entry["ok"] = None
                n_unchecked += 1
            elif expected:
                entry["expected_taxid"] = int(expected.group(1))
                entry["ok"] = str(expected.group(1)) in ids
                if entry["ok"] and len(ids) > 1:
                    entry["note"] = "query also matches other uids; recorded taxid is among them"
            else:
                entry["ok"] = len(ids) >= 1
                if len(ids) > 1:
                    entry["note"] = "ambiguous: more than one uid"
            if entry["ok"] is True:
                n_ok += 1
            elif entry["ok"] is False:
                n_bad += 1
            lookups.append(entry)
        elif "esummary.fcgi" in url:
            meta, data = ncbi.f.get_json(url)
            res = (data or {}).get("result") or {}
            uids = res.get("uids") or []
            statuses = {u: (res.get(u) or {}).get("status") for u in uids}
            entry = {"url": url, "http_status": meta.get("status"), "n_uids": len(uids), "statuses": {k: v for k, v in statuses.items() if v != "active"}}
            if not uids:
                entry["ok"] = None if meta.get("status") != 200 else False
                if entry["ok"] is None:
                    n_unchecked += 1
                else:
                    n_bad += 1
            else:
                entry["ok"] = all(v == "active" for v in statuses.values())
                n_ok += 1 if entry["ok"] else 0
                n_bad += 0 if entry["ok"] else 1
            lookups.append(entry)
        else:
            lookups.append({"url": url, "ok": None, "note": "not re-fetched (bulk dump or unrecorded checksum)"})
            n_unchecked += 1
    checks["lookups"] = {"n_ok": n_ok, "n_failed": n_bad, "n_unchecked": n_unchecked, "detail": lookups}
    flags["lookups_ok"] = n_bad == 0 and n_ok > 0
    # how many distinct taxids do the recorded lookups actually evidence, vs the record's own count?
    evidenced: set[str] = set()
    for d, l in zip(rec.get("distributions", []), lookups):
        if "esearch.fcgi" in d["download_url"]:
            if l.get("expected_taxid"):
                evidenced.add(str(l["expected_taxid"]))
            elif l.get("idlist") and len(l["idlist"]) == 1:
                evidenced.add(l["idlist"][0])
        elif "esummary.fcgi" in d["download_url"]:
            evidenced |= set(parse_qs(urlparse(d["download_url"]).query).get("id", [""])[0].split(","))
    evidenced.discard("")
    checks["count_recheck"] = None
    stats = []
    for c in rec.get("counts", []):
        pid = c.get("property_id")
        entry = {"property_id": pid, "recorded": c.get("value"), "slice": c.get("slice")}
        if pid in ("n_taxa_resolved", "n_taxa_matched") and c.get("value") is not None:
            entry.update({"observed": len(evidenced), "within_tolerance": len(evidenced) >= c["value"] * 0.9,
                          "note": "observed = distinct taxids evidenced by the recorded E-utilities lookups"})
            if checks["count_recheck"] is None:
                checks["count_recheck"] = entry
                continue
        else:
            entry.update({"observed": None, "within_tolerance": None, "note": "describes the record's own taxon list; not re-checkable against NCBI"})
        stats.append(entry)
    checks["stats_recheck"] = stats
    flags["taxa_evidenced"] = len(evidenced)
    cs, cs_all = check_checksums(rec, ncbi, obstacles)
    checks["checksum_match"] = cs_all
    checks["checksums"] = cs
    return {"checks": checks, "flags": flags, "obstacles": obstacles}


# --------------------------------------------------------------------------- scoring

def r2(x: float) -> float:
    return round(max(0.0, min(1.0, x)) + 1e-9, 2)


def overall(scores: dict) -> float:
    return sum(scores[d["id"]] * d["weight"] for d in RUBRIC["dimensions"])


def verdict(scores: dict, exists: bool) -> str:
    o = overall(scores)
    a, i, c = scores["authenticity"], scores["integrity"], scores["completeness"]
    if a < 0.5 or not exists:
        return "reject"
    if i < 0.5 or c < 0.4:
        return "needs-repair"
    if o >= 0.8 and i >= 0.7 and a >= 0.8:
        return "reliable"
    if o >= 0.55 and a >= 0.5:
        return "usable-with-caveats"
    return "needs-repair"


def metadata_completeness(rec: dict) -> tuple[float, list[str]]:
    pen, notes = 0.0, []
    if not rec.get("license"):
        pen += 0.1
        notes.append("license missing")
    if not rec.get("version"):
        pen += 0.1
        notes.append("version missing")
    if not rec.get("creators"):
        pen += 0.1
        notes.append("creators missing")
    if not rec.get("is_referenced_by") and not rec.get("doi"):
        pen += 0.1
        notes.append("no is_referenced_by or doi")
    if not rec.get("counts"):
        pen += 0.1
        notes.append("no counts")
    if not rec.get("bibliographic_citation"):
        pen += 0.1
        notes.append("no citation")
    return pen, notes


def score_genome(rec: dict, p: dict, res: dict) -> dict:
    src = SOURCES["ncbi-assembly"]["scores"]
    f, checks, obstacles = res["flags"], res["checks"], list(res["obstacles"])
    scores = {"source-authority": src["source-authority"], "independence": src["independence"], "authenticity": src["authenticity"]}
    notes = []
    if not f["exists"]:
        scores.update({"integrity": 0.0, "completeness": 0.0, "authenticity": 0.0})
        rationale = (f"Accession {p['accession']} is returned neither by NCBI Datasets v2 nor by Entrez Assembly, so the identifier does not exist; "
                     "the record is rejected. Source-level scores for NCBI Assembly are not inherited because the record does not trace to the source.")
        return finish(rec, p, scores, checks, obstacles, rationale, confidence=0.95)

    integrity = 1.0
    if f["status"] == "superseded":
        integrity = 0.6
        notes.append(f"accession superseded by {checks.get('current_accession')}")
    elif f["status"] == "suppressed":
        integrity = 0.5
        notes.append("assembly is suppressed at NCBI")
    elif f["status"] not in ("current", None):
        integrity = 0.6
        notes.append(f"assembly status is '{f['status']}'")
    if not f["stats_ok"]:
        integrity = min(integrity, 0.3)
        notes.append("a recorded assembly statistic disagrees with NCBI's current value")
    if not f["counts_ok"]:
        integrity = min(integrity, 0.5)
        notes.append("a recorded taxon count drifted beyond tolerance")
    cs = checks.get("checksum_match")
    if cs is False:
        live_only = all(c.get("live_api_response") for c in checks["checksums"] if c.get("match") is False)
        if live_only and f["stats_ok"] and f["counts_ok"]:
            integrity = min(integrity, 0.9)
            notes.append("SHA-256 of the live API JSON changed, but the content re-checked matches")
        else:
            integrity = min(integrity, 0.5)
            notes.append("SHA-256 mismatch on a re-downloaded distribution")
    if obstacles:
        integrity = min(integrity, 0.5)

    completeness = 1.0
    pen, mnotes = metadata_completeness(rec)
    completeness -= pen
    notes += mnotes
    if f["level_match"] is False:
        completeness -= 0.15
        notes.append(f"recorded assembly level {checks['assembly_level']['recorded']} vs NCBI {checks['assembly_level']['observed']}")
    if f["date_match"] is False:
        completeness -= 0.1
        notes.append(f"recorded date {checks['release_date']['recorded']} vs NCBI release date {checks['release_date']['observed']}")
    if p["recorded_level"] is None:
        completeness -= 0.05
        notes.append("assembly level not stated in the record")
    if f.get("bioproject_match") is False:
        completeness -= 0.1
        notes.append(f"recorded BioProject {checks['bioproject_check']['recorded']} vs NCBI {checks['bioproject_check']['observed']}")
    if f.get("version_consistent") is False:
        completeness -= 0.05
        notes.append(f"version '{checks['version_check']['recorded']}' is neither the accession nor NCBI's assembly name '{checks['version_check']['assembly_name']}'")
    if f["unverified"]:
        completeness -= 0.05
    authenticity = scores["authenticity"]
    if f["organism_match"] is False:
        authenticity = 0.5
        completeness -= 0.4
        notes.append(f"organism {checks['organism_observed']['organism_name']} (taxid {checks['organism_observed']['tax_id']}) is not the record's taxon nor nested in it")
    elif f["organism_match"] is None:
        completeness -= 0.1
        obstacles.append("organism-taxon relationship could not be verified (lineage lookup failed)")
    if p["reference_claimed"] and f["ref_for_taxon"] is False:
        completeness -= 0.15
        notes.append("record presents the assembly as the reference, but it is no longer in the reference set for the record's taxon")
    if p["reference_claimed"] and f["ref_for_taxon"] is None and f["ref_for_organism"] is False:
        completeness -= 0.1
        notes.append("assembly is not the current reference for its organism")
    scores["integrity"] = r2(integrity)
    scores["completeness"] = r2(completeness)
    scores["authenticity"] = r2(authenticity)

    confidence = 0.9
    if obstacles:
        confidence -= 0.2
    if f["organism_match"] is None:
        confidence -= 0.1
    n_stats = sum(1 for s in checks.get("stats_recheck", []) if s.get("within_tolerance") is True) + (1 if (checks.get("count_recheck") or {}).get("within_tolerance") else 0)
    org = checks["organism_observed"]
    ref = checks["reference_status"]
    rationale = (
        f"Accession {p['accession']} re-resolved via NCBI Datasets v2 ({checks['accession_status']}"
        + (f", RefSeq category '{ref.get('refseq_category_of_accession')}'" if ref.get("refseq_category_of_accession") else "")
        + f"); organism {org['organism_name']} (taxid {org['tax_id']})"
        + (" is the record's taxon or nested in it." if f["organism_match"] else " does not match the record's taxon." if f["organism_match"] is False else "; relationship to the record's taxon unverified.")
        + (f" It is the current reference assembly for {'its organism' if f['ref_for_organism'] else ''}{' and ' if f['ref_for_organism'] and f['ref_for_taxon'] else ''}{'the record taxon' if f['ref_for_taxon'] else ''}." if (f["ref_for_organism"] or f["ref_for_taxon"]) else " It is not in the current reference set for its organism." if f["ref_for_organism"] is False else "")
        + f" {n_stats} recorded statistic(s)/count(s) re-checked within tolerance"
        + ("; assembly level and release date agree with NCBI." if f["level_match"] and f["date_match"] else ".")
        + (" Checksums of the recorded API responses " + ("match." if cs else "differ (live JSON)." if cs is False else "were not re-checkable."))
        + (" Issues: " + "; ".join(notes) + "." if notes else "")
    )
    return finish(rec, p, scores, checks, obstacles, rationale, confidence)


def score_genomes(rec: dict, p: dict, res: dict) -> dict:
    src = SOURCES["ncbi-assembly"]["scores"]
    f, checks, obstacles = res["flags"], res["checks"], list(res["obstacles"])
    scores = {"source-authority": src["source-authority"], "independence": src["independence"], "authenticity": src["authenticity"]}
    notes = []
    if not f["exists"]:
        scores.update({"integrity": 0.0, "completeness": 0.0, "authenticity": 0.0})
        return finish(rec, p, scores, checks, obstacles, f"NCBI taxid {checks.get('taxid')} does not resolve in NCBI Taxonomy; identifier does not exist.", 0.9)
    integrity = 1.0
    cr = checks.get("count_recheck") or {}
    if not f["counts_ok"]:
        integrity = 0.5
        notes.append(f"count drifted beyond tolerance ({cr.get('recorded')} recorded vs {cr.get('observed')} now)")
    if checks.get("checksum_match") is False:
        if f["counts_ok"]:
            integrity = min(integrity, 0.9)
            notes.append("SHA-256 of the live API JSON changed, but the count matches")
        else:
            integrity = min(integrity, 0.5)
    if obstacles or f["unverified"]:
        integrity = min(integrity, 0.5)
    completeness = 1.0
    pen, mnotes = metadata_completeness(rec)
    completeness -= pen
    notes += mnotes
    authenticity = scores["authenticity"]
    if f["organism_match"] is False:
        authenticity = 0.5
        completeness -= 0.4
        notes.append("queried taxid is unrelated to the record's taxon")
    elif f.get("taxon_relation", "same") != "same":
        completeness -= 0.3 if "ancestor" in f["taxon_relation"] else 0.15
        tn = ", ".join(str(x["taxon_name"]) for x in checks["taxon_checks"])
        notes.append(f"{f['taxon_relation']}: record counts genomes under {checks['taxon_key_resolves_to']} but is linked to taxon {tn}")
    fl = checks.get("first_listed_reference")
    if fl and fl.get("match") is False:
        completeness -= 0.05
        notes.append(f"first listed reference changed from {fl['recorded']} to {fl['observed']}")
    scores["integrity"] = r2(integrity)
    scores["completeness"] = r2(completeness)
    scores["authenticity"] = r2(authenticity)
    confidence = 0.9 - (0.2 if obstacles else 0.0)
    rationale = (
        f"NCBI taxid {checks['taxid']} resolves to {checks['taxon_key_resolves_to']} ({checks.get('ncbi_rank')}), "
        + ("which is the record's taxon. " if f.get("taxon_relation") == "same" else f"a broader group than the record's linked taxon ({f['taxon_relation']}). " if f["organism_match"] and f.get("taxon_relation") else "which is not the record's taxon. " if f["organism_match"] is False else "relationship to the record's taxon unverified. ")
        + f"The recorded count of {cr.get('recorded')} ({cr.get('property_id')}) re-queried as {cr.get('observed')} "
        + ("(within tolerance). " if cr.get("within_tolerance") else "(outside tolerance). " if cr.get("within_tolerance") is False else "(not re-checkable). ")
        + ("Checksum of the recorded API response matches. " if checks.get("checksum_match") else "Checksum of the live API response differs. " if checks.get("checksum_match") is False else "")
        + "Source scores inherited from the NCBI Assembly source assessment."
        + (" Issues: " + "; ".join(notes) + "." if notes else "")
    )
    return finish(rec, p, scores, checks, obstacles, rationale, confidence)


def score_taxonomy(rec: dict, p: dict, res: dict) -> dict:
    src = SOURCES["ncbi-taxonomy"]["scores"]
    f, checks, obstacles = res["flags"], res["checks"], list(res["obstacles"])
    scores = {"source-authority": src["source-authority"], "independence": src["independence"], "authenticity": src["authenticity"]}
    lk = checks["lookups"]
    notes = []
    integrity = 1.0
    if not f["exists"]:
        integrity = 0.0
    if lk["n_failed"]:
        integrity = min(integrity, 0.5 if lk["n_failed"] <= 2 else 0.3)
        notes.append(f"{lk['n_failed']} recorded lookup(s) no longer return the recorded taxid")
    if lk["n_ok"] == 0:
        integrity = min(integrity, 0.5)
        obstacles.append("no recorded lookup could be reproduced")
    if checks.get("checksum_match") is False:
        n_mis = sum(1 for c in checks["checksums"] if c.get("match") is False)
        if lk["n_failed"] == 0:
            integrity = min(integrity, 0.9)
            notes.append(f"{n_mis} live E-utilities response(s) changed bytes while returning the same taxids")
        else:
            integrity = min(integrity, 0.5)
    if lk["n_unchecked"] and lk["n_unchecked"] > lk["n_ok"]:
        integrity = min(integrity, 0.5)
    completeness = 1.0
    pen, mnotes = metadata_completeness(rec)
    completeness -= pen
    notes += mnotes
    if lk["n_unchecked"]:
        completeness -= 0.05
    cr = checks.get("count_recheck")
    if cr and cr.get("within_tolerance") is False:
        completeness -= 0.4 if cr["observed"] < 0.1 * cr["recorded"] else 0.3
        notes.append(f"record counts {cr['recorded']} taxa ({cr['property_id']}) but its distributions evidence only {cr['observed']} taxid(s); the count is not cross-checkable")
    ambiguous = sum(1 for d in lk["detail"] if "ambiguous" in str(d.get("note", "")))
    if ambiguous:
        completeness -= 0.1
        notes.append(f"{ambiguous} unfielded esearch term(s) match more than one taxid")
    scores["integrity"] = r2(integrity)
    scores["completeness"] = r2(completeness)
    confidence = 0.85 - (0.2 if obstacles else 0.0)
    rationale = (
        f"Identifier {rec['identifier']} resolves (final URL {checks.get('identifier_final_url')}). Of {len(lk['detail'])} recorded E-utilities lookups, "
        f"{lk['n_ok']} reproduce the recorded taxid(s) today, {lk['n_failed']} fail and {lk['n_unchecked']} could not be re-fetched or carry no checksum. "
        + ("All recorded SHA-256 values match. " if checks.get("checksum_match") else "Some response bytes differ from the recorded SHA-256 (live service). " if checks.get("checksum_match") is False else "")
        + f"The recorded lookups evidence {f.get('taxa_evidenced', 0)} distinct taxid(s); the record's own taxon counts cannot otherwise be cross-checked against NCBI. Source scores inherited from the NCBI Taxonomy source assessment."
        + (" Issues: " + "; ".join(notes) + "." if notes else "")
    )
    return finish(rec, p, scores, checks, obstacles, rationale, confidence)


def finish(rec: dict, p: dict, scores: dict, checks: dict, obstacles: list[str], rationale: str, confidence: float) -> dict:
    scores = {k: r2(v) for k, v in scores.items()}
    ordered = {d["id"]: scores[d["id"]] for d in RUBRIC["dimensions"]}
    exists = checks.get("identifier_resolves") is not False
    std_obstacles = []
    if p["kind"] in ("genome", "genomes"):
        if any(c.get("live_api_response") for c in checks.get("checksums", [])):
            std_obstacles.append("recorded distributions are live NCBI Datasets API responses; their bytes and taxon counts change as assemblies are added or metadata is edited.")
        if p["kind"] == "genome" and p["reference_claimed"]:
            std_obstacles.append("'reference genome' is a live NCBI designation that can move to a newer assembly.")
    else:
        std_obstacles.append("E-utilities responses are live; taxids are stable but names and node merges change over time.")
    return {
        "dataset_id": rec["id"],
        "source_id": "ncbi-taxonomy" if p["kind"] == "taxonomy" else "ncbi-assembly",
        "scores": ordered,
        "overall": round(overall(ordered), 3),
        "verdict": verdict(ordered, exists),
        "confidence": round(confidence, 2),
        "checks": checks,
        "obstacles": obstacles + std_obstacles,
        "rationale": rationale,
    }


# --------------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--ids", nargs="*", default=None)
    ap.add_argument("--batch-size", type=int, default=100)
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-fetch everything")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--no-write", action="store_true")
    args = ap.parse_args()

    records = json.loads((MERGED / "datasets.json").read_text())
    taxa = {t["key"]: t for t in json.loads((MERGED / "taxa.json").read_text())}
    batch = [r for r in records if r["id"].startswith(("ncbi-genome-", "ncbi-genomes-", "ncbi-taxonomy-"))]
    if args.ids:
        batch = [r for r in batch if r["id"] in set(args.ids)]
    if args.limit:
        batch = batch[: args.limit]
    fetcher = Fetcher(CACHE, refresh=args.refresh)
    ncbi = NCBI(fetcher)
    out = []
    t0 = time.time()
    for i, rec in enumerate(batch, 1):
        p = parse_record(rec, taxa)
        try:
            if p["kind"] == "genome":
                res = recheck_genome(rec, p, ncbi)
                scored = score_genome(rec, p, res)
            elif p["kind"] == "genomes":
                res = recheck_genomes(rec, p, ncbi)
                scored = score_genomes(rec, p, res)
            else:
                res = recheck_taxonomy(rec, p, ncbi)
                scored = score_taxonomy(rec, p, res)
        except Exception as exc:  # keep going; record the failure honestly
            scored = finish(rec, p, {"source-authority": SOURCES["ncbi-assembly"]["scores"]["source-authority"], "integrity": 0.5, "completeness": 0.5,
                                     "independence": SOURCES["ncbi-assembly"]["scores"]["independence"], "authenticity": SOURCES["ncbi-assembly"]["scores"]["authenticity"]},
                            {"checked_at": now_iso(), "identifier_resolves": None, "checksum_match": None, "count_recheck": None, "error": f"{type(exc).__name__}: {exc}"},
                            [f"re-check script failed: {type(exc).__name__}: {exc}"],
                            "The re-check could not run for this record; integrity and completeness capped at 0.5 pending a re-run.", 0.3)
        out.append(scored)
        print(f"[{i}/{len(batch)}] {rec['id']}: {scored['verdict']} {scored['scores']}  (requests={fetcher.requests_made}, {time.time()-t0:.0f}s)", file=sys.stderr)

    if args.no_write:
        print(json.dumps(out, indent=1))
        return 0
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("batch-*.json"):
        old.unlink()
    for n, start in enumerate(range(0, len(out), args.batch_size), 1):
        path = out_dir / f"batch-{n:02d}.json"
        path.write_text(json.dumps(out[start:start + args.batch_size], indent=1, ensure_ascii=False) + "\n")
        size = path.stat().st_size
        print(f"wrote {path} ({len(out[start:start + args.batch_size])} records, {size/1024:.0f} KB)", file=sys.stderr)
        if size > 1_000_000:
            print(f"WARNING {path} exceeds 1 MB; re-run with a smaller --batch-size", file=sys.stderr)
    from collections import Counter
    print("verdicts:", dict(Counter(o["verdict"] for o in out)), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
