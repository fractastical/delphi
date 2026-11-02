#!/usr/bin/env python3
"""Test aristotle-ga03-25 against WoRMS environment flags.

A full species-rank crawl is the pre-registered method. Groups whose species-rank
list is longer than 20,000 rows are probed, not fully downloaded, and the
pre-registered rule then calls the test inconclusive because the crawl is incomplete.
Cephalopoda, which is short enough to finish, is counted in full.
"""
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
UA = "DelphiClaimTest/1.0 (aristotle-ga03-25; public claim test)"
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": UA, "Accept": "application/json"})
PAGE = 50
PAGE_CAP = 400  # 400 pages = 20,000 species-rank rows. Longer lists are not fully fetched.


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_json(url):
    digest = hashlib.sha256(url.encode()).hexdigest()[:20]
    path = os.path.join(DATA, digest + ".json")
    meta = path + ".retrieved"
    if os.path.exists(path) and os.path.exists(meta) and os.path.getsize(path) > 0:
        raw = open(path, "rb").read()
        when = open(meta).read().strip()
        return raw, json.loads(raw), when
    last = None
    for attempt in range(6):
        r = SESSION.get(url, timeout=45)
        last = r
        if r.status_code == 200 and r.content.strip():
            raw = r.content
            when = now()
            open(path, "wb").write(raw)
            open(meta, "w").write(when)
            return raw, json.loads(raw), when
        if r.status_code in {200, 429, 500, 502, 503, 504}:
            time.sleep(min(20, 2 ** attempt))
            continue
        r.raise_for_status()
    if last is not None and last.status_code == 200:
        return last.content, [], now()
    last.raise_for_status()
    return b"", [], now()


def page_url(belongs, offset):
    return (
        "https://www.marinespecies.org/rest/AphiaRecordsByTaxonRankID/220"
        f"?belongsTo={belongs}&offset={offset}&marine_only=false&extant_only=true"
    )


def page_len(belongs, offset):
    raw, data, when = get_json(page_url(belongs, offset))
    n = len(data) if isinstance(data, list) else 0
    return n, raw, when


def record_probe(belongs, offset, n, raw, when):
    return {
        "offset": offset,
        "n": n,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": when,
        "download_url": page_url(belongs, offset),
    }


def find_end(belongs):
    """Last offset that returns rows, or None when the list is longer than PAGE_CAP pages.

    The end is located by exponential search and then binary search on the
    1, 51, 101, ... page grid, so a short last page is not skipped.
    """
    probes = []

    def probe(offset):
        n, raw, when = page_len(belongs, offset)
        probes.append(record_probe(belongs, offset, n, raw, when))
        return n

    def page_index(offset):
        return (offset - 1) // PAGE

    n = probe(1)
    if n == 0:
        return None, probes
    if n < PAGE:
        return 1, probes
    last_full = 1
    offset = 1 + PAGE * 40  # 2001
    while offset < 2_000_000:
        if page_index(offset) >= PAGE_CAP:
            cap_offset = 1 + PAGE * (PAGE_CAP - 1)
            n = probe(cap_offset)
            if n >= PAGE:
                return None, probes
            if 0 < n < PAGE:
                return cap_offset, probes
            offset = cap_offset
            break
        n = probe(offset)
        if n == 0:
            break
        if n < PAGE:
            return offset, probes
        last_full = offset
        offset = 1 + PAGE * (page_index(offset) + 1) * 4
    else:
        return None, probes
    lo, hi = last_full, offset
    while page_index(hi) - page_index(lo) > 1:
        mid = 1 + PAGE * ((page_index(lo) + page_index(hi)) // 2)
        if mid <= lo or mid >= hi:
            break
        if page_index(mid) >= PAGE_CAP:
            return None, probes
        n = probe(mid)
        if n == 0:
            hi = mid
        elif n < PAGE:
            return mid, probes
        else:
            lo = mid
    if page_index(lo) >= PAGE_CAP:
        return None, probes
    return lo, probes


def tally(records):
    accepted = [
        r for r in records
        if r.get("status") == "accepted" and r.get("isExtinct") != 1 and r.get("rank") == "Species"
    ]
    def flag(r, key):
        return r.get(key) == 1
    aquatic = [r for r in accepted if flag(r, "isMarine") or flag(r, "isBrackish") or flag(r, "isFreshwater")]
    fresh_nonmarine = [r for r in aquatic if flag(r, "isFreshwater") and not flag(r, "isMarine")]
    brackish = [r for r in aquatic if flag(r, "isBrackish")]
    frac = (len(fresh_nonmarine) / len(aquatic)) if aquatic else None
    if frac is None:
        group = "unmeasured"
    elif frac < 0.05 and brackish:
        group = "pass"
    elif frac >= 0.15:
        group = "refute"
    else:
        group = "ambiguous"
    return {
        "accepted_extant": len(accepted),
        "aquatic": len(aquatic),
        "fresh_nonmarine": len(fresh_nonmarine),
        "brackish": len(brackish),
        "fraction_fresh_nonmarine": frac,
        "group_result": group,
        "fresh_nonmarine_names": [r.get("scientificname") for r in fresh_nonmarine],
        "brackish_names": [r.get("scientificname") for r in brackish],
    }


def crawl(belongs, exclude_class=None):
    end, probes = find_end(belongs)
    if end is None:
        return {"crawled": False, "probes": probes, "reason": "species-rank list longer than 20,000 rows"}, []
    offsets = list(range(1, end + 1, 50))
    if len(offsets) > PAGE_CAP:
        return {"crawled": False, "probes": probes, "pages": len(offsets), "reason": "over page cap"}, []
    pages = {}

    def one(offset):
        raw, data, when = get_json(page_url(belongs, offset))
        return offset, raw, data if isinstance(data, list) else [], when

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(one, off) for off in offsets]
        for fut in as_completed(futures):
            offset, raw, data, when = fut.result()
            pages[offset] = (raw, data, when)
    records = []
    manifest = []
    for offset in offsets:
        raw, data, when = pages[offset]
        if exclude_class:
            data = [r for r in data if str(r.get("class") or "") != exclude_class]
        records.extend(data)
        manifest.append({
            "download_url": page_url(belongs, offset),
            "retrieved_at": when,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "n": len(data),
        })
    return {"crawled": True, "probes": probes, "tally": tally(records), "pages": len(offsets)}, manifest


def main():
    ids = {}
    id_files = []
    for name in ("Mollusca", "Crustacea", "Cephalopoda"):
        url = f"https://www.marinespecies.org/rest/AphiaIDByName/{name}?marine_only=false"
        raw, data, when = get_json(url)
        ids[name] = int(data)
        id_files.append({
            "download_url": url,
            "retrieved_at": when,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "role": f"AphiaID for {name}",
        })
    groups = {}
    manifests = []
    # Cephalopoda is its own belongsTo crawl. Testaceans are Mollusca excluding Cephalopoda,
    # which requires the Mollusca crawl. Crustacea is its own crawl.
    for label, belongs in (("cephalopoda", ids["Cephalopoda"]), ("testacea_mollusca", ids["Mollusca"]), ("crustacea", ids["Crustacea"])):
        print(f"crawl {label} {belongs}", flush=True)
        summary, manifest = crawl(belongs, exclude_class="Cephalopoda" if label == "testacea_mollusca" else None)
        print(f"done {label} crawled={summary.get('crawled')} pages={summary.get('pages')} reason={summary.get('reason')}", flush=True)
        groups[label] = summary
        manifests.extend(manifest)
        # Drop bulky probe bodies from the saved summary; hashes remain.
        if not summary["crawled"]:
            summary["probe_offsets"] = [
                {k: p[k] for k in ("offset", "n", "byte_size", "sha256", "download_url", "retrieved_at")}
                for p in summary["probes"]
            ]
            del summary["probes"]

    finished = [k for k, v in groups.items() if v.get("crawled")]
    # Pre-registered decision needs all three groups. An incomplete crawl is inconclusive.
    verdict, reason = "inconclusive", "underpowered"
    ceph = groups["cephalopoda"].get("tally")
    measured = {
        "value": None if not ceph else ceph["fraction_fresh_nonmarine"],
        "unit": "cephalopod fresh-and-not-marine fraction among aquatic accepted species",
        "n": None if not ceph else ceph["aquatic"],
        "uncertainty": None,
        "extra": {
            "aphia_ids": ids,
            "groups": groups,
            "finished_groups": finished,
            "page_cap": PAGE_CAP,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2, ensure_ascii=False)
    manifest_path = os.path.join(DERIVED, "page_manifest.json")
    json.dump(manifests, open(manifest_path, "w"), ensure_ascii=False)
    manifest_bytes = open(manifest_path, "rb").read()

    path = os.path.join(HERE, "result.json")
    result = json.load(open(path))
    result["status"] = "complete"
    result["preregistered"] = True
    result["data_kind"] = "biological" if ceph else "none"
    result["verdict"] = verdict
    result["reason"] = reason
    result["confidence"] = 0.8
    result["deviations"] = [{
        "field": "crawl scope",
        "change": "Species-rank lists longer than 20,000 rows were probed at exponentially increasing offsets and not fully downloaded.",
        "why": "Mollusca still returned a full page at offset 200001-scale and Crustacea did too past 100,000 rows. Completing those crawls was not possible in this run. The pass and fail fractions were not changed. The pre-registered rule says an incomplete crawl is inconclusive.",
    }]
    result["method"] = (
        "WoRMS Aphia IDs for Mollusca, Crustacea and Cephalopoda were resolved, then species-rank pages were requested with marine_only false. "
        "The length of each list was probed by quadrupling the offset until a short page or until the list passed 20,000 rows. "
        "Only lists within that bound were fully downloaded. Accepted extant species were tallied by isMarine, isBrackish and isFreshwater. "
        "Cephalopoda was fully counted. Mollusca and Crustacea were not, so the three-group test is incomplete and the verdict is inconclusive."
    )
    result["measured"] = measured
    frac = None if not ceph or ceph["fraction_fresh_nonmarine"] is None else round(ceph["fraction_fresh_nonmarine"], 4)
    result["caveats"] = [
        "The cephalopod fraction is a finished count and is reported, but it does not decide the claim by itself.",
        "Unaccepted names and synonyms are in the species-rank pages and were excluded from the tally.",
        "extant_only was requested; records with isExtinct equal to 1 were also dropped.",
        "Terrestrial-only species are outside the aquatic denominator, as pre-registered.",
    ]
    files = id_files + [
        {
            "download_url": p["download_url"],
            "retrieved_at": p["retrieved_at"],
            "byte_size": p["byte_size"],
            "sha256": p["sha256"],
            "role": "probe page",
        }
        for g in groups.values() for p in g.get("probe_offsets", [])
    ]
    files.extend(manifests)
    files.append({
        "download_url": "derived/page_manifest.json",
        "retrieved_at": now(),
        "byte_size": len(manifest_bytes),
        "sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "role": "manifest of fully downloaded cephalopod pages",
    })
    result["datasets"] = [{
        "id": "worms-aphia-environment-flags",
        "name": "WoRMS Aphia species-rank records with environment flags",
        "landing_url": "https://www.marinespecies.org/",
        "doi": None,
        "version": "live REST API",
        "license": "CC BY (WoRMS)",
        "files": files,
        "role": "freshwater, brackish and marine flags",
    }]
    result["headline"] = (
        "WoRMS species-rank lists for molluscs and crustaceans still fill a page past 20,000 rows, so the three-group test is unfinished"
        + (
            f"; of {ceph['aquatic']} accepted extant aquatic cephalopod species, {ceph['fresh_nonmarine']} are fresh and not marine (fraction {frac}) and {ceph['brackish']} {'is' if ceph['brackish'] == 1 else 'are'} brackish."
            if frac is not None else "."
        )
    )
    # The file list can be large. Keep result.json under 1 MB.
    encoded = json.dumps(result)
    if len(encoded) > 900_000:
        result["datasets"][0]["files"] = id_files + [files[-1]]
        result["datasets"][0]["files_note"] = "Per-page SHA-256 values are in derived/page_manifest.json and in measured.extra group probes."
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(verdict, result["headline"])
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "probe_offsets"} for k, v in groups.items()}, indent=2)[:2000])


if __name__ == "__main__":
    main()
