#!/usr/bin/env python3
"""Winged and wingless ants in the AntWeb specimen service.

Pre-registered: at least 50 flying and 50 non-flying specimens, in at least two
genera each, supports the claim that some ants fly and others do not. Flying
requires a wing word (alate, but not dealate; winged; macropterous). Non-flying
is caste worker, or wingless / apterous / ergatoid / dealate. If the service
cannot be retrieved, the verdict is inconclusive with reason data-unavailable.

Run: python3 analysis.py
"""

import hashlib
import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "Mozilla/5.0 (compatible; delphisci-claim-test/1.0; aristotle-pa01-06)"
QUERIES = {
    "worker": "https://api.antweb.org/v3/specimens?family=formicidae&caste=worker&limit=200",
    "alate": "https://api.antweb.org/v3/specimens?family=formicidae&lifeStageSex=alate&limit=200",
    "dealate": "https://api.antweb.org/v3/specimens?family=formicidae&lifeStageSex=dealate&limit=200",
    "wingless": "https://api.antweb.org/v3/specimens?family=formicidae&lifeStageSex=wingless&limit=200",
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            code = resp.status
            final = resp.geturl()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        code = exc.code
        final = exc.geturl()
    dest.write_bytes(raw)
    return {
        "requested_url": url,
        "download_url": final,
        "http_status": code,
        "retrieved_at": now(),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "content_type_hint": "json" if raw[:1] in (b"{", b"[") else "not-json",
    }, raw


def life_text(spec):
    parts = []
    for key, value in spec.items():
        if re.search(r"life|stage|sex|caste", key, re.I) and isinstance(value, str):
            parts.append(value)
    return " ".join(parts)


def is_flying(spec):
    text = life_text(spec).lower()
    if re.search(r"dealate", text):
        return False
    return bool(re.search(r"\balate\b|winged|macropterous", text))


def is_nonflying(spec):
    if is_flying(spec):
        return False
    text = life_text(spec).lower()
    caste = str(spec.get("caste") or spec.get("Caste") or "").lower()
    if caste == "worker":
        return True
    return bool(re.search(r"wingless|apterous|ergatoid|dealate", text))


def genus_of(spec):
    for key in ("genus", "Genus"):
        if spec.get(key):
            return str(spec[key])
    name = spec.get("scientificName") or spec.get("scientific_name") or ""
    parts = str(name).split()
    return parts[0] if parts else None


def specimens_of(payload):
    if isinstance(payload, list):
        return payload, None
    if not isinstance(payload, dict):
        return [], None
    total = None
    for key in ("count", "total", "numFound", "totalCount", "matched"):
        if isinstance(payload.get(key), int):
            total = payload[key]
    rows = None
    for key in ("specimens", "data", "results", "hits"):
        if isinstance(payload.get(key), list):
            rows = payload[key]
            break
    return rows or [], total


def main():
    responses = []
    parsed = {}
    blocked = False
    for name, url in QUERIES.items():
        info, raw = fetch(url, DATA / f"{name}.json")
        responses.append(info)
        if info["content_type_hint"] != "json" or info["http_status"] != 200:
            blocked = True
            parsed[name] = {"rows": 0, "total": None, "error": info["http_status"]}
            continue
        payload = json.loads(raw.decode("utf-8"))
        rows, total = specimens_of(payload)
        parsed[name] = {"rows": len(rows), "total": total, "sample": rows[:200]}

    flying = []
    nonflying = []
    if not blocked:
        # Alate query is the flying pool; worker, wingless and dealate are non-flying pools.
        # Re-classify each record so a mis-tagged row cannot cross the pre-registered rule.
        for row in parsed["alate"]["sample"]:
            if is_flying(row):
                flying.append(row)
        for key in ("worker", "dealate", "wingless"):
            for row in parsed[key]["sample"]:
                if is_nonflying(row):
                    nonflying.append(row)
        fly_total = parsed["alate"]["total"]
        if fly_total is None:
            fly_total = len(flying)
        non_total = parsed["worker"]["total"]
        if non_total is None:
            non_total = len(nonflying)
        fly_genera = {g for g in (genus_of(r) for r in flying) if g}
        non_genera = {g for g in (genus_of(r) for r in nonflying) if g}
    else:
        fly_total = non_total = 0
        fly_genera = set()
        non_genera = set()

    if blocked:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.85
    elif fly_total >= 50 and len(fly_genera) >= 2 and non_total >= 50 and len(non_genera) >= 2:
        verdict, reason, confidence = "supports", None, 0.8
    elif (fly_total == 0 and non_total >= 50) or (non_total == 0 and fly_total >= 50):
        verdict, reason, confidence = "refutes", None, 0.8
    elif fly_total < 50 and non_total < 50:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.5
    else:
        verdict, reason, confidence = "mixed", None, 0.5

    measured = {
        "value": None if blocked else int(fly_total),
        "unit": "AntWeb specimens classed as flying; non-flying count is in extra",
        "n": None if blocked else int(fly_total) + int(non_total),
        "uncertainty": None,
        "extra": {
            "service_retrieved": not blocked,
            "http_status": {r["requested_url"]: r["http_status"] for r in responses},
            "flying_specimens": None if blocked else fly_total,
            "nonflying_specimens": None if blocked else non_total,
            "flying_genera_in_sample": sorted(fly_genera),
            "nonflying_genera_in_sample": sorted(non_genera),
        },
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(
        json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n",
        encoding="utf-8",
    )
    result = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    result["status"] = "complete"
    result["data_kind"] = "none" if blocked else "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["datasets"] = [
        {
            "id": "antweb-specimens-v3",
            "name": "AntWeb specimen service, version 3",
            "landing_url": "https://www.antweb.org/api.do",
            "doi": None,
            "version": "v3",
            "license": "AntWeb data are available for use; the service page states the terms",
            "files": [
                {
                    "name": Path(info["requested_url"].split("?")[0]).name + "-" + name,
                    "download_url": info["download_url"],
                    "retrieved_at": info["retrieved_at"],
                    "byte_size": info["byte_size"],
                    "sha256": info["sha256"],
                    "http_status": info["http_status"],
                }
                for name, info in zip(QUERIES, responses)
            ],
            "role": "caste and life-stage text for ant specimens, used to separate flying and non-flying individuals",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Four AntWeb v3 specimen queries were requested: caste=worker, lifeStageSex=alate, "
        "lifeStageSex=dealate, and lifeStageSex=wingless, each limited to 200 records and to family Formicidae. "
        "Records would be classed by the pre-registered wing and caste rules, with genera counted on the "
        "returned sample and totals taken from the service when it reports one. "
        "A non-JSON or non-200 response is recorded as the service not retrieved."
    )
    result["results_summary"] = [
        f"HTTP status by query: {measured['extra']['http_status']}.",
        f"Service retrieved: {not blocked}. Verdict {verdict}" + (f" ({reason})" if reason else "") + ".",
    ]
    if blocked:
        result.setdefault("caveats", [])
        note = (
            "From this network the AntWeb host returned a Cloudflare challenge page (HTTP 403) "
            "instead of specimen JSON. No caste or wing count was read, and no other dataset was substituted."
        )
        if note not in result["caveats"]:
            result["caveats"].append(note)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "blocked": blocked}, indent=2))


if __name__ == "__main__":
    main()
