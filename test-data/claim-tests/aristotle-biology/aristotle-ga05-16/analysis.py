#!/usr/bin/env python3
"""Albino or leucistic observations of ravens, sparrows, partridges and bears.

Counts come from the iNaturalist observations API. Thresholds are the ones
committed in result.json. A zero count does not refute the claim.
"""
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
API = "https://api.inaturalist.org/v1"
UA = "delphisci-claim-test (github.com/fractastical/delphi)"
PROJECTS = ("albino-leucistic-birds", "albino-leucistic-melanistic-animals")
WHITE = re.compile(r"\b(albino|albinism|albinistic|leucistic|leucism|leukistic|leukism)\b", re.I)
MELAN = re.compile(r"\b(melanism|melanistic|melanic)\b", re.I)
RAVEN_WORD = re.compile(r"\bRaven\b")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    return raw, json.loads(raw)


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def taxon_by_name(q, rank, exact):
    url = f"{API}/taxa?" + urllib.parse.urlencode({"q": q, "rank": rank, "per_page": 20})
    _, payload = get_json(url)
    time.sleep(0.7)
    for item in payload.get("results", []):
        if item.get("name") == exact and item.get("rank") == rank:
            return item
    return None


def blob(obs):
    parts = []
    if obs.get("description"):
        parts.append(obs["description"])
    for tag in obs.get("tags") or []:
        parts.append(str(tag))
    for ofv in obs.get("ofvs") or []:
        parts.append(str(ofv.get("name") or ""))
        parts.append(str(ofv.get("value") or ""))
    return "\n".join(parts)


def text_ok(obs, project):
    text = blob(obs)
    white = bool(WHITE.search(text))
    if MELAN.search(text) and not white:
        return False
    if white:
        return True
    return project == "albino-leucistic-birds"


def group_for(taxon, queried_as):
    name = taxon.get("name") or ""
    common = taxon.get("preferred_common_name") or ""
    rank = taxon.get("rank") or ""
    if rank not in {"species", "subspecies", "variety", "form"}:
        return None
    if queried_as == "ravens":
        if name == "Corvus corax" or RAVEN_WORD.search(common):
            return "ravens"
        return None
    if queried_as == "sparrows":
        return "sparrows" if name.startswith("Passer ") else None
    if queried_as == "partridges":
        genus = name.split(" ")[0]
        return "partridges" if genus in {"Alectoris", "Perdix"} else None
    if queried_as == "bears":
        if name.startswith("Ursus maritimus") or common.lower() == "polar bear":
            return None
        return "bears"
    return None


def page_observations(project, taxon_id):
    page = 1
    found = []
    total = None
    while page <= 25:
        query = urllib.parse.urlencode({
            "project_id": project,
            "taxon_id": taxon_id,
            "quality_grade": "research",
            "captive": "false",
            "per_page": 200,
            "page": page,
            "order_by": "id",
            "order": "asc",
        })
        url = f"{API}/observations?{query}&has[]=photos"
        raw, payload = get_json(url)
        time.sleep(0.7)
        if total is None:
            total = payload.get("total_results")
        results = payload.get("results") or []
        found.append((url, raw, results))
        if len(results) < 200:
            break
        page += 1
    return total, found


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    retrieved = now()
    targets = {
        "ravens": taxon_by_name("Corvus", "genus", "Corvus"),
        "sparrows": taxon_by_name("Passer", "genus", "Passer"),
        "partridges_alectoris": taxon_by_name("Alectoris", "genus", "Alectoris"),
        "partridges_perdix": taxon_by_name("Perdix", "genus", "Perdix"),
        "bears": taxon_by_name("Ursidae", "family", "Ursidae"),
    }
    missing = [k for k, v in targets.items() if not v]
    if missing:
        result = json.loads(RESULT.read_text())
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable"
        result["confidence"] = 0.3
        result["data_kind"] = "none"
        result["measured"] = {"value": None, "unit": "qualifying observations", "n": 0, "uncertainty": None, "extra": {"missing_taxa": missing}}
        RESULT.write_text(json.dumps(result, indent=2) + "\n")
        print("missing taxa", missing)
        return
    queries = [
        ("ravens", "ravens", targets["ravens"]["id"]),
        ("sparrows", "sparrows", targets["sparrows"]["id"]),
        ("partridges", "partridges", targets["partridges_alectoris"]["id"]),
        ("partridges", "partridges", targets["partridges_perdix"]["id"]),
        ("bears", "bears", targets["bears"]["id"]),
    ]
    # Birds project will not contain bears; still query it. Animals project may contain all groups.
    groups = {name: {} for name in ("ravens", "sparrows", "partridges", "bears")}
    request_log = []
    api_failed = False
    for project in PROJECTS:
        for group_name, queried_as, taxon_id in queries:
            if project == "albino-leucistic-birds" and group_name == "bears":
                continue
            try:
                total, pages = page_observations(project, taxon_id)
            except Exception as exc:  # network or HTTP error
                api_failed = True
                request_log.append({"project": project, "group": group_name, "taxon_id": taxon_id, "error": str(exc)})
                continue
            kept = 0
            for url, raw, results in pages:
                request_log.append({
                    "project": project,
                    "group": group_name,
                    "taxon_id": taxon_id,
                    "url": url,
                    "byte_size": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "n_results": len(results),
                    "total_results": total,
                })
                for obs in results:
                    if obs.get("quality_grade") != "research":
                        continue
                    if not obs.get("photos"):
                        continue
                    if obs.get("captive") is True:
                        continue
                    if not text_ok(obs, project):
                        continue
                    taxon = obs.get("taxon") or {}
                    assigned = group_for(taxon, queried_as)
                    if assigned != group_name:
                        continue
                    groups[group_name][obs["id"]] = {
                        "id": obs["id"],
                        "uri": f"https://www.inaturalist.org/observations/{obs['id']}",
                        "taxon": taxon.get("name"),
                        "common": taxon.get("preferred_common_name"),
                        "project": project,
                        "license": (obs.get("license_code") or obs.get("license")),
                    }
                    kept += 1
            request_log.append({"project": project, "group": group_name, "taxon_id": taxon_id, "kept": kept, "api_total_results": total})
    counts = {name: len(obs) for name, obs in groups.items()}
    positive = [name for name, n in counts.items() if n >= 1]
    if api_failed and not any(counts.values()):
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.3
    elif len(positive) == 4:
        verdict, reason = "supports", None
        confidence = 0.70 if all(n >= 3 for n in counts.values()) else 0.55
    elif len(positive) >= 1:
        verdict, reason, confidence = "mixed", None, 0.45
    else:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.3
    samples = {name: list(obs.values())[:12] for name, obs in groups.items()}
    measured = {
        "value": len(positive),
        "unit": "groups with at least one qualifying observation (ravens, sparrows, partridges, bears)",
        "n": sum(counts.values()),
        "uncertainty": None,
        "extra": {
            "counts": counts,
            "samples": samples,
            "taxon_ids": {k: v["id"] for k, v in targets.items()},
            "api_failed": api_failed,
        },
    }
    # Persist request hashes without the observation bodies.
    hash_rows = [row for row in request_log if "sha256" in row]
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if any(counts.values()) or hash_rows else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["datasets"] = [
        {
            "id": "inaturalist-project-albino-leucistic-birds",
            "name": "iNaturalist project Albino & Leucistic birds",
            "landing_url": "https://www.inaturalist.org/projects/albino-leucistic-birds",
            "doi": None,
            "version": "API v1 observations, retrieved " + retrieved,
            "license": "Per-observation licences returned by the API; project membership is user-contributed",
            "files": [
                {"name": f"observations-{i}.json", "download_url": row["url"], "retrieved_at": retrieved, "byte_size": row["byte_size"], "sha256": row["sha256"]}
                for i, row in enumerate(hash_rows) if "albino-leucistic-birds" in row["url"]
            ],
            "role": "research-grade photographed observations in a project limited to albino and leucistic birds",
        },
        {
            "id": "inaturalist-project-albino-leucistic-melanistic-animals",
            "name": "iNaturalist project Albino, Leucistic & Melanistic Animals",
            "landing_url": "https://www.inaturalist.org/projects/albino-leucistic-melanistic-animals",
            "doi": None,
            "version": "API v1 observations, retrieved " + retrieved,
            "license": "Per-observation licences returned by the API; project membership is user-contributed",
            "files": [
                {"name": f"observations-{i}.json", "download_url": row["url"], "retrieved_at": retrieved, "byte_size": row["byte_size"], "sha256": row["sha256"]}
                for i, row in enumerate(hash_rows) if "albino-leucistic-melanistic-animals" in row["url"]
            ],
            "role": "research-grade photographed observations; melanistic-only text is excluded and a white-aberration word is required",
        },
    ]
    result["method"] = (
        "Resolved Corvus, Passer, Alectoris, Perdix and Ursidae on the iNaturalist taxa API, then paged "
        "research-grade, non-captive observations with photos in the two projects. Ravens are species or "
        "subspecies whose name is Corvus corax or whose preferred common name contains the word Raven. "
        "Sparrows are species in genus Passer. Partridges are Alectoris and Perdix. Bears are Ursidae "
        "except Ursus maritimus. The birds project qualifies without a further keyword. The animals project "
        "qualifies only when the description, a tag or an observation field matches albino or leucistic wording, "
        "and melanistic-only text is dropped. Observation ids were deduplicated within each group. "
        "The pre-registered rule has no refutation from a zero count."
    )
    result["measured"] = measured
    result["results_summary"] = [
        "Qualifying observations: " + ", ".join(f"{k}={v}" for k, v in counts.items()) + ".",
        f"Groups positive: {len(positive)} of 4. Verdict {verdict}" + (f" ({reason})" if reason else "") + ".",
    ]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.joinpath("measured.json").write_text(json.dumps({"counts": counts, "samples": samples, "requests": request_log}, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "counts": counts}, indent=2))


if __name__ == "__main__":
    main()
