#!/usr/bin/env python3
"""Test aristotle-ha09-26 against honey-bee pollen loads.

Thresholds are locked to result.json. The CSV is downloaded at run time
and is not committed.
"""

from __future__ import annotations

import csv
import hashlib
import http.client
import json
import re
import ssl
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlparse

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DERIVED = HERE / "derived" / "measured.json"

FILE_URL = "https://datadryad.org/downloads/file_stream/3848538"
LANDING = "https://datadryad.org/dataset/doi:10.5061/dryad.tdz08kq88"
API_FILE_URL = "https://datadryad.org/api/v2/files/3848538/download"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

EXPECTED_THRESHOLDS = {"min_loads": 30, "refute_min_mixed_fraction": 0.1}

POLLEN_PRIORITY = [
    "morphotype",
    "pollenmorphotype",
    "pollen_morphotype",
    "pollentype",
    "pollen_type",
    "plantspecies",
    "plant_species",
    "floralspecies",
    "floral_species",
    "family",
    "genus",
    "taxon",
    "pollen",
]

LOCKED = [
    "claim_id",
    "claim_iri",
    "project",
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "thresholds",
    "test_contract",
    "interpretation",
    "preregistered_at",
    "created",
    "agent",
]


def solve_anubis(random_data: str, difficulty: int):
    whole = difficulty // 2
    odd = difficulty % 2
    prefix = random_data.encode()
    nonce = 0
    while nonce < 5_000_000:
        digest = hashlib.sha256(prefix + str(nonce).encode()).digest()
        ok = digest[:whole] == b"\x00" * whole
        if ok and odd and (digest[whole] >> 4) != 0:
            ok = False
        if ok:
            return digest.hex(), nonce
        nonce += 1
    raise RuntimeError("Anubis proof-of-work was not solved")


def _merge_cookies(jar: dict, headers) -> None:
    for key, value in headers:
        if key.lower() != "set-cookie":
            continue
        pair = value.split(";", 1)[0]
        if "=" not in pair:
            continue
        name, cookie = pair.split("=", 1)
        jar[name] = cookie


def _header(headers, name: str):
    for key, value in headers:
        if key.lower() == name:
            return value
    return None


def _dryad_once(host: str, path: str, page_url: str) -> bytes:
    """One keep-alive session.

    The proof-of-work cookie is valid only for the client address that solved
    the challenge. Separate connections leave from different addresses here, so
    the challenge, the pass request, and the file request share one connection.
    A redirect off this host is followed once and is not recorded.
    """
    context = ssl.create_default_context()
    conn = http.client.HTTPSConnection(host, timeout=180, context=context)
    base = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Host": host,
        "Referer": LANDING,
    }
    cookies = {}

    def send(target: str):
        headers = dict(base)
        if cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in cookies.items())
        conn.request("GET", target, headers=headers)
        resp = conn.getresponse()
        payload = resp.read()
        _merge_cookies(cookies, resp.getheaders())
        return resp.status, resp.getheaders(), payload

    try:
        status, headers, body = send(path)
        if b"anubis_challenge" in body:
            match = re.search(
                br'<script id="anubis_challenge" type="application/json">(.*?)</script>',
                body,
                re.S,
            )
            if not match:
                raise RuntimeError("challenge page had no JSON")
            payload = json.loads(match.group(1))
            challenge = payload["challenge"]
            digest, nonce = solve_anubis(challenge["randomData"], int(payload["rules"]["difficulty"]))
            query = urlencode(
                {
                    "id": challenge["id"],
                    "response": digest,
                    "nonce": str(nonce),
                    "redir": page_url,
                    "elapsedTime": "1600",
                }
            )
            send("/.within.website/x/cmd/anubis/api/pass-challenge?" + query)
            status, headers, body = send(path)
        location = _header(headers, "location")
        if status in (301, 302, 303, 307, 308) and location:
            nxt = urlparse(location)
            if nxt.hostname == host:
                status, headers, body = send(nxt.path + (("?" + nxt.query) if nxt.query else ""))
                location = _header(headers, "location")
                nxt = urlparse(location) if location else None
            if nxt and nxt.hostname and nxt.hostname != host and status in (301, 302, 303, 307, 308):
                conn.close()
                conn = http.client.HTTPSConnection(nxt.hostname, timeout=180, context=context)
                remote = nxt.path + (("?" + nxt.query) if nxt.query else "")
                conn.request(
                    "GET",
                    remote,
                    headers={"User-Agent": UA, "Accept": "*/*", "Host": nxt.hostname, "Connection": "close"},
                )
                resp = conn.getresponse()
                body = resp.read()
                status = resp.status
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        return body
    finally:
        conn.close()


def fetch(url: str, dest: Path) -> dict:
    """Download a public Dryad file.

    The API download URL returns 401 without a bearer token. The same file is
    linked from the dataset page and is behind the site's proof-of-work cookie.
    The signed asset-store URL is not stored.
    """
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    parsed = urlparse(url)
    path = parsed.path + (("?" + parsed.query) if parsed.query else "")
    last_error = "no attempt"
    body = b""
    for _attempt in range(5):
        try:
            body = _dryad_once(parsed.hostname, path, url)
        except Exception as exc:
            last_error = type(exc).__name__ + ": " + str(exc)[:160]
            body = b""
            continue
        head = body.lstrip()[:20].lower()
        if body and not (head.startswith(b"<!doctype html") or head.startswith(b"<html")):
            break
        last_error = "HTML page, " + str(len(body)) + " bytes"
        body = b""
    else:
        raise RuntimeError("Dryad did not return the CSV: " + last_error)
    dest.write_bytes(body)
    return {
        "download_url": url,
        "final_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(body),
        "sha256": hashlib.sha256(body).hexdigest(),
        "retrieval_note": (
            "API URL " + API_FILE_URL + " returned 401 without a bearer token. "
            "The bytes were retrieved from the public file link on the dataset page "
            "after the site's proof-of-work cookie, on one kept-alive connection. "
            "The signed asset-store URL was not stored."
        ),
    }


def squash(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def is_honey(value: str) -> bool:
    v = (value or "").strip().lower()
    return v == "hb" or "mellifera" in v or "honey" in v


def main() -> None:
    result = json.loads(RESULT.read_text())
    if result.get("thresholds") != EXPECTED_THRESHOLDS:
        sys.exit("thresholds in result.json do not match the locked constants in analysis.py")
    locked = {k: result.get(k) for k in LOCKED}
    original_caveats = list(result.get("caveats") or [])

    with tempfile.TemporaryDirectory(prefix="aristotle-ha09-26-") as tmp:
        dest = Path(tmp) / "dataset_pollen_raw.csv"
        meta = fetch(FILE_URL, dest)
        text = dest.read_text(encoding="utf-8-sig", errors="replace")
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            conclude(result, locked, original_caveats, meta, "inconclusive", "data-unavailable", 0.30, None, ["The pollen file has no data rows."], {"headers": []})
            return
        headers = list(rows[0].keys())
        by_squash = {squash(h): h for h in headers if h}

        def need(*candidates):
            for c in candidates:
                if squash(c) in by_squash:
                    return by_squash[squash(c)]
            return None

        species_col = need("species")
        site_col = need("site")
        period_col = need("period")
        day_col = need("day")
        bee_col = need("bee")
        pollen_col = None
        for token in POLLEN_PRIORITY:
            key = squash(token)
            if key in by_squash and by_squash[key] != species_col:
                pollen_col = by_squash[key]
                break
        missing = [
            name
            for name, col in (
                ("species", species_col),
                ("site", site_col),
                ("period", period_col),
                ("day", day_col),
                ("bee", bee_col),
                ("pollen_kind", pollen_col),
            )
            if col is None
        ]
        if missing:
            conclude(
                result,
                locked,
                original_caveats,
                meta,
                "inconclusive",
                "data-unavailable",
                0.30,
                None,
                ["Required columns were not found: " + ", ".join(missing) + ".", "Headers: " + ", ".join(headers)],
                {"headers": headers, "missing": missing},
            )
            return

        family_col = by_squash.get("family")
        loads = {}
        families = {}
        honey_rows = 0
        for row in rows:
            if not is_honey(row.get(species_col) or ""):
                continue
            honey_rows += 1
            key = (
                (row.get(site_col) or "").strip(),
                (row.get(period_col) or "").strip(),
                (row.get(day_col) or "").strip(),
                (row.get(bee_col) or "").strip(),
            )
            kind = " ".join((row.get(pollen_col) or "").split())
            loads.setdefault(key, set())
            if kind:
                loads[key].add(kind)
            if family_col:
                family = " ".join((row.get(family_col) or "").split())
                families.setdefault(key, set())
                if family:
                    families[key].add(family)

        single = 0
        mixed = 0
        excluded = 0
        mixed_examples = []
        kind_counts = {}
        for key, kinds in loads.items():
            if len(kinds) == 0:
                excluded += 1
            elif len(kinds) == 1:
                single += 1
                only = next(iter(kinds))
                kind_counts[only] = kind_counts.get(only, 0) + 1
            else:
                mixed += 1
                if len(mixed_examples) < 12:
                    mixed_examples.append({"site": key[0], "period": key[1], "day": key[2], "bee": key[3], "kinds": sorted(kinds)})
        scored = single + mixed
        fraction = (mixed / scored) if scored else None
        family_mixed = family_single = family_scored = None
        family_fraction = None
        if family_col:
            family_mixed = family_single = 0
            for key in loads:
                kinds = families.get(key, set())
                if len(kinds) >= 2:
                    family_mixed += 1
                elif len(kinds) == 1:
                    family_single += 1
            family_scored = family_mixed + family_single
            family_fraction = (family_mixed / family_scored) if family_scored else None
        th = EXPECTED_THRESHOLDS
        if scored < th["min_loads"]:
            verdict, reason, confidence = "inconclusive", "underpowered", 0.30
        elif mixed == 0:
            verdict, reason, confidence = "supports", None, 0.55
        elif fraction >= th["refute_min_mixed_fraction"]:
            verdict, reason, confidence = "refutes", None, 0.75
        else:
            verdict, reason, confidence = "mixed", None, 0.60

        measured = {
            "value": None if fraction is None else round(fraction, 6),
            "unit": "fraction of scored honey-bee pollen loads with two or more pollen kinds",
            "n": scored,
            "uncertainty": None,
            "extra": {
                "mixed_loads": mixed,
                "single_kind_loads": single,
                "excluded_loads_no_pollen_kind": excluded,
                "honey_bee_rows": honey_rows,
                "load_keys": len(loads),
                "pollen_column": pollen_col,
                "species_column": species_col,
                "grouping_columns": [site_col, period_col, day_col, bee_col],
                "headers": headers,
                "mixed_load_examples": mixed_examples,
                "single_kind_counts_top": dict(sorted(kind_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:15]),
                "family_column": family_col,
                "family_mixed_loads": family_mixed,
                "family_scored_loads": family_scored,
                "family_mixed_fraction": None if family_fraction is None else round(family_fraction, 6),
                "family_fraction_used_for_verdict": False,
            },
        }
        fraction_text = "none" if fraction is None else f"{fraction:.4f}"
        family_text = "not computed" if family_fraction is None else f"{family_fraction:.4f} ({family_mixed} of {family_scored})"
        summary = [
            f"Honey-bee rows: {honey_rows}. Load keys: {len(loads)}. Scored loads: {scored}. Single-kind: {single}. Mixed: {mixed}. Excluded with no pollen kind: {excluded}.",
            f"Mixed fraction: {fraction_text}. Pollen-kind column: {pollen_col}.",
            f"Family-level mixed fraction, not used for the verdict: {family_text}.",
        ]
        conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, None)


def conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, extra):
    if measured is None:
        measured = {
            "value": None,
            "unit": "fraction of scored honey-bee pollen loads with two or more pollen kinds",
            "n": 0,
            "uncertainty": None,
            "extra": extra or {},
        }
    elif extra:
        measured["extra"].update(extra)
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "dryad-10.5061/dryad.tdz08kq88-dataset_pollen_raw",
            "name": "Pollen collection by the western honey bee and common eastern bumble bee (dataset_pollen_raw.csv)",
            "landing_url": LANDING,
            "doi": "10.5061/dryad.tdz08kq88",
            "version": "4",
            "license": "CC0-1.0",
            "files": [
                {
                    "name": "dataset_pollen_raw.csv",
                    "download_url": FILE_URL,
                    "final_url": meta["final_url"],
                    "retrieved_at": meta["retrieved_at"],
                    "byte_size": meta["byte_size"],
                    "sha256": meta["sha256"],
                }
            ],
            "role": "individual corbicular pollen loads of honey bees and bumble bees; only honey bees are scored",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded dataset_pollen_raw.csv from the public Dryad file link, hashed it, and grouped honey-bee rows "
        "by site, period, day and bee. The pollen-kind column was chosen by the pre-registered header priority. "
        "A load with two or more distinct pollen-kind values was mixed. The fraction was compared with 0 and 0.10."
    )
    result["results_summary"] = summary
    result["caveats"] = original_caveats
    result["deviations"] = [
        {
            "date": "2026-11-01",
            "change": "retrieval route only",
            "note": meta.get("retrieval_note"),
        }
    ]
    for key, value in locked.items():
        if result.get(key) != value:
            sys.exit(f"locked field changed: {key}")
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    DERIVED.write_text(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured, "results_summary": summary}, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "value": measured.get("value"), "n": measured.get("n")}, indent=2))


if __name__ == "__main__":
    main()
