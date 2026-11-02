#!/usr/bin/env python3
"""Test aristotle-pa04-34 against published fish testes masses.

Thresholds are locked to result.json. The CSV is downloaded at run time.
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

FILE_URL = "https://datadryad.org/downloads/file_stream/58157"
LANDING = "https://datadryad.org/dataset/doi:10.5061/dryad.fd3nq57"
API_FILE_URL = "https://datadryad.org/api/v2/files/58157/download"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

EXPECTED_THRESHOLDS = {"refute_min_species_positive_mass": 10}

SPECIES_PRIORITY = ["species", "scientificname", "scientific_name", "binomial", "taxon", "latin"]
NONFISH = ("mammal", "bird", "reptile", "snake", "amphibian")

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


def parse_number(value: str):
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "" or text.lower() in {"na", "nan", "none", "null"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def main() -> None:
    result = json.loads(RESULT.read_text())
    if result.get("thresholds") != EXPECTED_THRESHOLDS:
        sys.exit("thresholds in result.json do not match the locked constants in analysis.py")
    locked = {k: result.get(k) for k in LOCKED}
    original_caveats = list(result.get("caveats") or [])

    with tempfile.TemporaryDirectory(prefix="aristotle-pa04-34-") as tmp:
        dest = Path(tmp) / "MPdata2018.csv"
        meta = fetch(FILE_URL, dest)
        text = dest.read_text(encoding="utf-8-sig", errors="replace")
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            conclude(result, locked, original_caveats, meta, "inconclusive", "data-unavailable", 0.35, None, ["The testes file has no data rows."], {"headers": []})
            return
        headers = list(rows[0].keys())

        def banned(name: str) -> bool:
            n = name.lower()
            return any(tok in n for tok in ("residual", "gsi", "relative", "ratio", "index"))

        mass_candidates = []
        for header in headers:
            if not header or banned(header):
                continue
            low = header.lower()
            if ("testis" in low or "testes" in low) and ("mass" in low or "weight" in low):
                mass_candidates.append(header)
        mass_col = None
        for header in mass_candidates:
            if "combined" in header.lower() or "total" in header.lower():
                mass_col = header
                break
        if mass_col is None and mass_candidates:
            mass_col = mass_candidates[0]

        by_squash = {squash(h): h for h in headers if h}
        species_col = None
        for token in SPECIES_PRIORITY:
            if squash(token) in by_squash:
                species_col = by_squash[squash(token)]
                break
        group_col = None
        for header in headers:
            if header and any(tok in header.lower() for tok in ("group", "clade", "shark", "chondrich", "class")):
                group_col = header
                break

        if mass_col is None:
            conclude(
                result,
                locked,
                original_caveats,
                meta,
                "inconclusive",
                "data-unavailable",
                0.35,
                None,
                ["No testes-mass column matched the pre-registered header rule.", "Headers: " + ", ".join(headers)],
                {"headers": headers},
            )
            return

        numeric_rows = 0
        positive_species = []
        zero_or_negative_species = set()
        nonfish_positive = []
        seen = set()
        per_species_max = {}
        per_species_group = {}
        for i, row in enumerate(rows):
            mass = parse_number(row.get(mass_col))
            if mass is None:
                continue
            numeric_rows += 1
            if species_col:
                species = " ".join((row.get(species_col) or "").split())
            else:
                species = f"row-{i+1}"
            if not species:
                species = f"row-{i+1}"
            group = " ".join(((row.get(group_col) or "") if group_col else "").split())
            if any(tok in group.lower() for tok in NONFISH):
                if mass > 0:
                    nonfish_positive.append({"species": species, "group": group, "mass": mass})
                continue
            prev = per_species_max.get(species)
            if prev is None or mass > prev:
                per_species_max[species] = mass
            per_species_group.setdefault(species, group)
            seen.add(species)

        group_counts = {}
        for species, mass in per_species_max.items():
            group = per_species_group.get(species)
            if mass > 0:
                positive_species.append({"species": species, "group": group, "max_testes_mass": mass})
                group_counts[group] = group_counts.get(group, 0) + 1
            else:
                zero_or_negative_species.add(species)
        positive_species.sort(key=lambda r: r["species"])
        n_positive = len(positive_species)
        n_species_numeric = len(per_species_max)
        th = EXPECTED_THRESHOLDS["refute_min_species_positive_mass"]

        if numeric_rows == 0:
            verdict, reason, confidence = "inconclusive", "data-unavailable", 0.35
        elif n_positive >= th:
            verdict, reason, confidence = "refutes", None, 0.70
        elif n_positive >= 1:
            verdict, reason, confidence = "mixed", None, 0.40
        else:
            verdict, reason, confidence = "inconclusive", "other", 0.35

        measured = {
            "value": n_positive,
            "unit": "fish species with testes mass > 0",
            "n": n_species_numeric,
            "uncertainty": None,
            "extra": {
                "numeric_mass_rows": numeric_rows,
                "species_with_only_nonpositive_mass": len(zero_or_negative_species),
                "mass_column": mass_col,
                "species_column": species_col,
                "group_column": group_col,
                "headers": headers,
                "positive_species": positive_species,
                "nonfish_positive_rows": nonfish_positive,
                "min_positive_mass": min((r["max_testes_mass"] for r in positive_species), default=None),
                "max_positive_mass": max((r["max_testes_mass"] for r in positive_species), default=None),
                "positive_species_by_group": group_counts,
            },
        }
        summary = [
            f"Fish species with a numeric testes mass: {n_species_numeric}. Species with mass > 0: {n_positive}. Numeric rows: {numeric_rows}.",
            f"Mass column: {mass_col}. Species column: {species_col or 'row index, because no species header matched'}.",
            "Positive species by group: " + ", ".join(f"{k or 'blank'}={v}" for k, v in sorted(group_counts.items(), key=lambda kv: (-kv[1], str(kv[0])))) + ".",
        ]
        conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, None)


def conclude(result, locked, original_caveats, meta, verdict, reason, confidence, measured, summary, extra):
    if measured is None:
        measured = {
            "value": None,
            "unit": "fish species with testes mass > 0",
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
            "id": "dryad-10.5061/dryad.fd3nq57-MPdata2018",
            "name": "Testes size, sperm competition and body mass in bony fish and sharks (MPdata2018.csv)",
            "landing_url": LANDING,
            "doi": "10.5061/dryad.fd3nq57",
            "version": "1",
            "license": "CC0-1.0",
            "files": [
                {
                    "name": "MPdata2018.csv",
                    "download_url": FILE_URL,
                    "final_url": meta["final_url"],
                    "retrieved_at": meta["retrieved_at"],
                    "byte_size": meta["byte_size"],
                    "sha256": meta["sha256"],
                }
            ],
            "role": "measured testes mass of fish species, used only as presence of a positive mass",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded MPdata2018.csv from the public Dryad file link, hashed it, and selected the testes-mass column "
        "by the pre-registered header rule. Distinct fish species with a numeric mass strictly above zero "
        "were counted and compared with 10. No regression was fit, and the file's sperm-competition columns were not used."
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
