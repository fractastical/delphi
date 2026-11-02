#!/usr/bin/env python3
"""aristotle-pa04-30: is the wryneck the only bird with two toes forward and two back?

The article text is fetched only after result.json was committed.
Assignments come from explicit sentences in that text. Species counts come
from the GBIF backbone.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test"
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
ARTICLE_URL = "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4083792/"
EPMC_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    "?query=DOI:10.1098/rspb.2014.0765&format=json&resultType=core"
)
GBIF_MATCH = "https://api.gbif.org/v1/species/match"
GBIF_SEARCH = "https://api.gbif.org/v1/species/search"
BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
TAXON = re.compile(r"\b([A-Z][a-z]+(?:idae|iformes)|[A-Z][a-z]{2,}\s+[a-z]{3,})\b")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, browser: bool = False) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": BROWSER_UA if browser else UA, "Accept": "*/*"},
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def save_download(name: str, url: str, raw: bytes, retrieved: str) -> dict:
    DATA.mkdir(exist_ok=True)
    path = DATA / name
    if not path.exists() or path.stat().st_size == 0:
        path.write_bytes(raw)
        stamp = retrieved
    else:
        raw = path.read_bytes()
        stamp = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    return {
        "download_url": url,
        "retrieved_at": stamp,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def article_text(html: str) -> str:
    start = html.find("pmc-article-section")
    if start < 0:
        start = 0
    body = html[start:]
    for marker in ("id=\"ref-list\"", "id='ref-list'", ">References<", ">REFERENCES<"):
        cut = body.find(marker)
        if cut > 0:
            body = body[:cut]
            break
    body = re.sub(r"<script[\s\S]*?</script>", " ", body, flags=re.I)
    body = re.sub(r"<style[\s\S]*?</style>", " ", body, flags=re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"&nbsp;|&#160;", " ", body)
    body = re.sub(r"&\w+;|&#\d+;", " ", body)
    body = re.sub(r"\s+", " ", body)
    return body


def names_in(span: str) -> list[str]:
    found = []
    for name in TAXON.findall(span or ""):
        if name not in found:
            found.append(name)
    return found


def assignments(text: str) -> dict:
    """Taxa the paper's own sentences place in a two-forward-two-back foot.

    Each frame is a wording that applies zygodactyl, semi-zygodactyl,
    facultative zygodactyl, or heterodactyl to the names that follow it.
    Pamprodactyl and anisodactyl clauses are not frames.
    """
    frames = []

    def add(label: str, span: str) -> None:
        if not span:
            return
        span = span.split("Finally")[0]
        span = re.split(r"\bpamprodactyl\b", span, maxsplit=1, flags=re.I)[0]
        names = names_in(span)
        if names:
            frames.append({"frame": label, "span": span.strip()[:500], "taxa": names})

    match = re.search(r"extant clades:\s*([^.]*)", text)
    add("extant clades", match.group(1) if match else "")
    match = re.search(r"originated at least three times in extant birds:\s*([^.]*)", text)
    add("three extant origins", match.group(1) if match else "")
    match = re.search(r"semi-zygodactyl.{0,160}?like\s+([^.]*)", text, re.I)
    add("semi-zygodactyl like", match.group(1) if match else "")
    match = re.search(r"heterodactyl\w*.{0,140}?evolved in\s+([^.]{0,160})", text, re.I)
    add("heterodactyl evolved in", match.group(1) if match else "")
    for match in re.finditer(
        r"(?<!semi-)zygodactyl birds like\s+([^.]{0,160})",
        text,
        re.I,
    ):
        add("zygodactyl birds like", match.group(1))
    for match in re.finditer(
        r"zygodactyl (?:bird|foot)[^()]{0,80}\(\s*([^)]+?)\s*\)",
        text,
        re.I,
    ):
        add("zygodactyl bird or foot", match.group(1))
    match = re.search(
        r"([A-Z][a-z]+\s+[a-z]+)\s*\)\s*may represent a fourth independent",
        text,
    )
    if match and re.search(r"zygodactyl", text[max(0, match.start() - 400):match.end() + 80], re.I):
        add("fourth independent origin", match.group(1))

    taxa = []
    for frame in frames:
        for name in frame["taxa"]:
            if name not in taxa:
                taxa.append(name)
    three_forward = bool(re.search(
        r"digits II, III and IV are oriented forwards, while digit I is oriented backwards",
        text,
    ))
    wryneck_named = bool(re.search(r"\bJynx\b|wryneck", text, re.I))
    return {
        "frames": frames,
        "taxa": taxa,
        "three_forward_described": three_forward,
        "wryneck_or_jynx_named": wryneck_named,
    }


def gbif_json(url: str) -> dict:
    raw = http_get(url)
    return json.loads(raw.decode("utf-8"))


def resolve_taxon(name: str) -> dict:
    query = urllib.parse.urlencode({"name": name, "kingdom": "Animalia"})
    match = gbif_json(f"{GBIF_MATCH}?{query}")
    usage = match.get("usageKey")
    rank = match.get("rank")
    status = match.get("status")
    scientific = match.get("scientificName") or match.get("canonicalName")
    match_type = match.get("matchType")
    class_name = match.get("class")
    accepted = status == "ACCEPTED" and match_type in {"EXACT", "EXACT_HOMO"} or (
        match_type == "EXACT"
    )
    # A fuzzy match to a different name is not this paper's taxon.
    canonical = (match.get("canonicalName") or "").split()
    query_parts = name.split()
    name_ok = (
        match_type == "EXACT"
        and scientific
        and (
            scientific.startswith(name)
            or (canonical and canonical[0] == query_parts[0] and (
                len(query_parts) == 1 or (len(canonical) > 1 and canonical[1] == query_parts[1])
            ))
        )
    )
    count = None
    search_url = None
    if usage and name_ok:
        params = {
            "datasetKey": BACKBONE,
            "higherTaxonKey": usage,
            "rank": "SPECIES",
            "status": "ACCEPTED",
            "limit": 0,
        }
        search_url = f"{GBIF_SEARCH}?{urllib.parse.urlencode(params)}"
        search = gbif_json(search_url)
        count = search.get("count")
    return {
        "query": name,
        "match_type": match_type,
        "scientific_name": scientific,
        "rank": rank,
        "status": status,
        "usage_key": usage,
        "class": class_name,
        "kingdom": match.get("kingdom"),
        "accepted_species_count": count,
        "name_ok": bool(name_ok),
        "search_url": search_url,
    }


def jynx_keys() -> dict:
    query = urllib.parse.urlencode({"name": "Jynx torquilla", "kingdom": "Animalia"})
    match = gbif_json(f"{GBIF_MATCH}?{query}")
    keys = {
        key: match.get(key)
        for key in (
            "usageKey", "speciesKey", "genusKey", "familyKey",
            "orderKey", "classKey", "phylumKey", "kingdomKey",
        )
    }
    return {
        "scientific_name": match.get("scientificName"),
        "match_type": match.get("matchType"),
        "genus": match.get("genus"),
        "family": match.get("family"),
        "order": match.get("order"),
        "class": match.get("class"),
        "keys": keys,
    }


def is_jynx_taxon(name: str, resolved: dict) -> bool:
    if name in {"Jynx", "Jynx torquilla"}:
        return True
    scientific = resolved.get("scientific_name") or ""
    if scientific.startswith("Jynx torquilla") or (
        resolved.get("rank") == "GENUS" and scientific.startswith("Jynx")
    ):
        return True
    return False


def main() -> None:
    retrieved = now_utc()
    epmc_raw = http_get(EPMC_URL)
    epmc = json.loads(epmc_raw.decode("utf-8"))
    hits = (epmc.get("resultList") or {}).get("result") or []
    hit = hits[0] if hits else {}
    pmcid = hit.get("pmcid")
    article_url = ARTICLE_URL
    if pmcid:
        article_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
    html = http_get(article_url, browser=True)
    if b"zygodactyl" not in html.lower():
        raise SystemExit("article text did not contain the toe term")
    epmc_meta = save_download("europepmc-botelho.json", EPMC_URL, epmc_raw, retrieved)
    article_meta = save_download("pmc4083792.html", article_url, html, retrieved)
    # save_download skips rewrite if the file exists; write the fresh bytes when new.
    if not (DATA / "pmc4083792.html").exists() or (DATA / "pmc4083792.html").stat().st_size == 0:
        (DATA / "pmc4083792.html").write_bytes(html)
    text = article_text(html.decode("utf-8", errors="replace"))
    parsed = assignments(text)
    if not parsed["taxa"] and not re.search(r"zygodactyl|heterodactyl", text, re.I):
        verdict_blocker = "not-operationalizable"
    elif not parsed["taxa"]:
        verdict_blocker = "not-operationalizable"
    else:
        verdict_blocker = None

    jynx = jynx_keys() if parsed["taxa"] else {}
    jynx_keyset = {v for v in (jynx.get("keys") or {}).values() if v}
    resolved = []
    refuting = []
    for name in parsed["taxa"]:
        rec = resolve_taxon(name)
        inside = bool(rec.get("usage_key") and rec["usage_key"] in jynx_keyset)
        count = rec.get("accepted_species_count")
        others = None if count is None else (count - 1 if inside else count)
        rec["jynx_torquilla_inside"] = inside
        rec["accepted_species_besides_wryneck"] = others
        rec["is_jynx"] = is_jynx_taxon(name, rec)
        resolved.append(rec)
        if (
            not rec["is_jynx"]
            and rec["name_ok"]
            and others is not None
            and others >= 1
            and (rec.get("class") in {None, "Aves"} or rec.get("kingdom") == "Animalia")
        ):
            # Drop a match that GBIF places outside birds.
            if rec.get("class") not in (None, "Aves"):
                continue
            refuting.append(rec)

    only_jynx = bool(parsed["taxa"]) and all(r["is_jynx"] for r in resolved if r["name_ok"])
    if verdict_blocker == "not-operationalizable":
        verdict, why = "inconclusive", "not-operationalizable"
    elif refuting:
        verdict, why = "refutes", None
    elif only_jynx and parsed["three_forward_described"] and parsed["wryneck_or_jynx_named"]:
        verdict, why = "supports", None
    elif parsed["taxa"] and not any(r["name_ok"] for r in resolved):
        verdict, why = "inconclusive", "data-unavailable"
    else:
        verdict, why = "inconclusive", "not-operationalizable"

    if verdict == "refutes" and len(refuting) >= 3:
        confidence = 0.72
    elif verdict == "refutes":
        confidence = 0.6
    elif verdict == "supports":
        confidence = 0.55
    else:
        confidence = 0.35

    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({
        "frames": parsed["frames"],
        "taxa": parsed["taxa"],
        "three_forward_described": parsed["three_forward_described"],
        "wryneck_or_jynx_named": parsed["wryneck_or_jynx_named"],
        "jynx_torquilla": jynx,
        "resolved": [
            {
                "query": r["query"],
                "scientific_name": r["scientific_name"],
                "rank": r["rank"],
                "class": r["class"],
                "accepted_species_count": r["accepted_species_count"],
                "accepted_species_besides_wryneck": r["accepted_species_besides_wryneck"],
                "jynx_torquilla_inside": r["jynx_torquilla_inside"],
                "is_jynx": r["is_jynx"],
                "name_ok": r["name_ok"],
            }
            for r in resolved
        ],
        "refuting_queries": [r["query"] for r in refuting],
    }, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological" if parsed["taxa"] else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if why:
        result["reason"] = why
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "botelho-2014-rspb-20140765",
            "name": hit.get("title") or "Botelho et al. 2014, Proc R Soc B",
            "landing_url": "https://doi.org/10.1098/rspb.2014.0765",
            "doi": "10.1098/rspb.2014.0765",
            "version": pmcid,
            "license": "The Europe PMC record marks an HTML full text as free; the publisher copy is also listed as subscription",
            "files": [
                {"name": "europepmc-botelho.json", **epmc_meta},
                {"name": "pmc4083792.html", **article_meta},
            ],
            "role": "open text that names bird taxa together with toe arrangements",
        },
        {
            "id": "gbif-backbone",
            "name": "GBIF backbone taxonomy species counts",
            "landing_url": "https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c",
            "doi": None,
            "version": BACKBONE,
            "license": "GBIF backbone, queried live",
            "files": [],
            "role": "accepted-species counts for each taxon the paper codes two-forward-two-back",
        },
    ]
    result["method"] = (
        "Fetched the Europe PMC record for doi:10.1098/rspb.2014.0765 and the "
        "open PMC HTML it points to. Taxa were taken only from sentences that "
        "apply zygodactyl, semi-zygodactyl, or heterodactyl to a following "
        "scientific name: the extant-clade list, the three-origins list, the "
        "semi-zygodactyl 'like' list, the heterodactyl 'evolved in' clause, "
        "'zygodactyl birds like', a zygodactyl bird or foot named in parentheses, "
        "and a binomial said to be a fourth independent origin. Pamprodactyl "
        "and anisodactyl clauses were not used. Each name was matched on GBIF "
        "and counted with species search, rank SPECIES, status ACCEPTED, limit 0. "
        "Jynx torquilla was subtracted when its GBIF key sits inside that taxon."
    )
    n_refuting_species = sum(
        r["accepted_species_besides_wryneck"] or 0 for r in refuting
    )
    result["measured"] = {
        "value": len(refuting),
        "unit": "named non-Jynx taxa with at least one other accepted species",
        "n": len(parsed["taxa"]),
        "uncertainty": None,
        "extra": {
            "taxa": parsed["taxa"],
            "refuting_taxa": [r["query"] for r in refuting],
            "accepted_species_besides_wryneck_by_taxon": {
                r["query"]: r["accepted_species_besides_wryneck"] for r in resolved
            },
            "sum_of_refuting_species_counts": n_refuting_species,
            "three_forward_described": parsed["three_forward_described"],
            "wryneck_or_jynx_named": parsed["wryneck_or_jynx_named"],
            "jynx_torquilla_order": jynx.get("order"),
            "jynx_torquilla_family": jynx.get("family"),
        },
    }
    bits = ", ".join(
        f"{r['query']} {r['accepted_species_besides_wryneck']}"
        for r in refuting
    ) or "none"
    result["results_summary"] = [
        f"The paper names {len(parsed['taxa'])} taxa in a two-forward-two-back frame. "
        f"Non-Jynx taxa with at least one other accepted species: {len(refuting)} ({bits}).",
        f"Jynx or wryneck named in the text: {parsed['wryneck_or_jynx_named']}. "
        f"GBIF places Jynx torquilla in {jynx.get('family')} , {jynx.get('order')}.",
        "Three forward and one back is described for the anisodactyl foot: "
        + str(parsed["three_forward_described"]) + ".",
    ]
    species_zero = [
        r["query"] for r in resolved
        if r.get("rank") == "SPECIES" and r.get("accepted_species_count") == 0 and not r["is_jynx"]
    ]
    note = (
        "After the run, the assignments are the paper's explicit lists, not a "
        "survey of skins. Facultative and heterodactyl feet are inside the "
        "pre-registered two-and-two rule. A taxon the paper discusses only as "
        "an ancestor, or as having lost the arrangement, is not in these frames. "
        "A species-rank GBIF search with higherTaxonKey returned 0 for "
        + (", ".join(species_zero) if species_zero else "no name")
        + ", so those names did not meet the pre-registered count of at least 1. "
        "The family and order counts are what the verdict uses."
    )
    caveats = [c for c in result.get("caveats") or [] if not c.startswith("After the run,")]
    caveats.append(note)
    result["caveats"] = caveats
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": why,
        "taxa": parsed["taxa"],
        "refuting": [r["query"] for r in refuting],
        "counts": {r["query"]: r["accepted_species_besides_wryneck"] for r in resolved},
        "jynx_named": parsed["wryneck_or_jynx_named"],
        "jynx_order": jynx.get("order"),
        "confidence": confidence,
    }, indent=2))


if __name__ == "__main__":
    main()
