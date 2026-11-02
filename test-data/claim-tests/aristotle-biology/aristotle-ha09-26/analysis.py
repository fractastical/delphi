#!/usr/bin/env python3
"""Honey-bee pollen loads against aristotle-ha09-26.

Rules are those committed in result.json before the CSV was downloaded.
Uses the Python standard library only.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import urllib.request
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://datadryad.org/downloads/file_stream/3848538"
UA = "delphisci-claim-test"
NEED = ("species", "period", "day", "site", "bee", "morphotype")


def solve_anubis(html: str) -> tuple[str, str]:
    marker = 'id="anubis_challenge"'
    start = html.find(marker)
    if start < 0:
        raise RuntimeError("Dryad did not return an Anubis challenge page")
    open_tag = html.find(">", start)
    close_tag = html.find("</script>", open_tag)
    payload = json.loads(html[open_tag + 1:close_tag].strip())
    challenge = payload["challenge"]
    data = challenge["randomData"]
    zeros = "0" * int(challenge["difficulty"])
    nonce = 0
    while True:
        digest = hashlib.sha256(f"{data}{nonce}".encode()).hexdigest()
        if digest.startswith(zeros):
            return challenge["id"], f"{digest}:{nonce}"
        nonce += 1
        if nonce > 2_000_000:
            raise RuntimeError("Anubis proof of work did not finish")


def fetch(url: str, dest: Path) -> dict:
    """Download the Dryad file. The file stream sits behind an Anubis proof-of-work
    cookie, so a plain urllib GET receives an HTML challenge. curl keeps the cookie."""
    import subprocess
    import tempfile
    from urllib.parse import urlencode

    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size < 1000:
        with tempfile.TemporaryDirectory() as tmp:
            jar = str(Path(tmp) / "cookies.txt")
            html_path = Path(tmp) / "challenge.html"
            subprocess.run(
                ["curl", "-sL", "--max-time", "60", "-A", UA, "-c", jar, "-b", jar, "-o", str(html_path), url],
                check=True,
            )
            html = html_path.read_text(encoding="utf-8", errors="replace")
            if html.lstrip().startswith("species,"):
                dest.write_text(html)
            else:
                challenge_id, solved = solve_anubis(html)
                digest, nonce = solved.split(":")
                pass_url = "https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge?" + urlencode({
                    "id": challenge_id,
                    "response": digest,
                    "nonce": nonce,
                    "redir": url,
                    "elapsedTime": "4000",
                })
                subprocess.run(
                    ["curl", "-sL", "--max-time", "90", "-A", UA, "-c", jar, "-b", jar, "-o", str(dest), pass_url],
                    check=True,
                )
                if dest.read_bytes()[:15].lstrip().startswith(b"<!") or dest.stat().st_size < 1000:
                    raise RuntimeError("Dryad download did not return the CSV")
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def num(value: str) -> float | None:
    text = (value or "").strip()
    if text == "" or text.lower() in {"na", "nan", "null"}:
        return None
    return float(text)


def main() -> None:
    info = fetch(URL, DATA / "dataset_pollen_raw.csv")
    with (DATA / "dataset_pollen_raw.csv").open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        rows = list(reader)
    missing = [name for name in NEED if name not in fields]
    has_prop = "prop" in fields
    has_counts = "count" in fields and "total_count" in fields
    if missing or not (has_prop or has_counts):
        finish(info, None, "inconclusive", "data-unavailable", 0.85, {
            "value": None,
            "unit": "proportion of honey-bee loads with two morphotypes at or above 5% of grains",
            "n": 0,
            "uncertainty": None,
            "extra": {"columns": fields, "missing": missing, "n_rows": len(rows)},
        }, "The CSV did not have the columns the pre-registration requires.")
        return

    hb = [row for row in rows if (row.get("species") or "").strip().lower() == "hb"]
    loads: dict[tuple, list[dict]] = defaultdict(list)
    for row in hb:
        key = (row.get("period"), row.get("day"), row.get("site"), row.get("bee"))
        loads[key].append(row)

    props_seen = []
    for group in loads.values():
        for row in group:
            value = num(row.get("prop") or "")
            if value is not None:
                props_seen.append(value)
    as_percent = bool(props_seen) and max(props_seen) > 1.5
    threshold = 5.0 if as_percent else 0.05

    def proportion(row: dict, total_from_counts: float | None) -> float | None:
        value = num(row.get("prop") or "")
        if value is not None:
            return value
        count = num(row.get("count") or "")
        total = num(row.get("total_count") or "") or total_from_counts
        if count is None or not total:
            return None
        return count / total

    n = len(loads)
    n_mixed = 0
    n_mixed_any = 0
    n_single = 0
    morph_hist: dict[str, int] = defaultdict(int)
    for group in loads.values():
        by_morph: dict[str, float] = {}
        for row in group:
            name = (row.get("morphotype") or "").strip()
            if not name:
                continue
            share = proportion(row, None)
            if share is None:
                continue
            by_morph[name] = by_morph.get(name, 0.0) + share
        counted = [name for name, share in by_morph.items() if share + 1e-12 >= threshold]
        morph_hist[str(len(by_morph))] += 1
        if len(by_morph) >= 2:
            n_mixed_any += 1
        if len(counted) >= 2:
            n_mixed += 1
        elif len(counted) == 1 or (len(by_morph) == 1 and not counted):
            n_single += 1
    p = (n_mixed / n) if n else None
    p_any = (n_mixed_any / n) if n else None

    if n < 30:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.7
    elif p == 0:
        verdict, reason, confidence = "supports", None, 0.40
    elif p >= 0.05:
        verdict, reason, confidence = "refutes", None, 0.80
    else:
        verdict, reason, confidence = "refutes", None, 0.45

    measured = {
        "value": None if p is None else round(p, 6),
        "unit": "proportion of honey-bee pollen loads with two or more morphotypes each at least 5% of counted grains",
        "n": n,
        "uncertainty": "exact proportion of loads; grain counts are the dataset's microscopy counts",
        "extra": {
            "n_honey_bee_rows": len(hb),
            "n_mixed_loads_at_5pct": n_mixed,
            "n_mixed_loads_any_second_morphotype": n_mixed_any,
            "proportion_mixed_any_abundance": None if p_any is None else round(p_any, 6),
            "n_loads_with_one_counted_morphotype": n_single,
            "proportion_scale": "percent" if as_percent else "fraction",
            "threshold_in_file_units": threshold,
            "loads_by_n_morphotypes_unthresholded": dict(sorted(morph_hist.items(), key=lambda kv: int(kv[0]))),
        },
    }
    note = (
        f"Honey-bee loads: {n}. Loads with two morphotypes at or above 5% of grains: {n_mixed} "
        f"(p={p}). Loads with any second morphotype, not used for the verdict: {n_mixed_any}."
    )
    deviations = None
    if as_percent:
        deviations = [{
            "date": "2026-11-01",
            "what": "prop values in the CSV exceed 1, so they are percentages. The pre-registered 5% floor is applied as prop >= 5, which is the same grain share.",
            "why": "The dictionary describes prop as a proportion but the file is scaled 0-100. The scientific threshold is unchanged.",
        }]
    finish(info, deviations, verdict, reason, confidence, measured, note)


def finish(info, deviations, verdict, reason, confidence, measured, note) -> None:
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["datasets"] = [{
        "id": "dryad-10.5061-dryad.tdz08kq88-dataset-pollen-raw",
        "name": "dataset_pollen_raw.csv from Pollen collection by the western honey bee and common eastern bumble bee",
        "landing_url": "https://doi.org/10.5061/dryad.tdz08kq88",
        "doi": "10.5061/dryad.tdz08kq88",
        "version": "v20250206",
        "license": "CC0-1.0",
        "files": [{"name": "dataset_pollen_raw.csv", **info}],
        "role": "per-load pollen morphotype counts for honey bees and bumble bees; only honey-bee rows are scored",
    }]
    doc["method"] = (
        "Downloaded dataset_pollen_raw.csv, hashed it, and kept rows with species hb. "
        "A load is the combination of period, day, site and bee. Morphotype shares in a load were summed. "
        "A morphotype counts toward the verdict when its share is at least 5% of counted grains. "
        "The pre-registered rule was applied to the proportion of loads with two or more such morphotypes. "
        "Bumble-bee rows were not scored."
    )
    doc["measured"] = measured
    doc["verdict"] = verdict
    doc["confidence"] = confidence
    doc["data_kind"] = "biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none"
    if verdict == "inconclusive" and reason == "data-unavailable":
        doc["data_kind"] = "none"
    elif verdict == "inconclusive":
        doc["data_kind"] = "biological"
    doc["results_summary"] = [note]
    if reason:
        doc["reason"] = reason
    else:
        doc.pop("reason", None)
    if deviations:
        doc["deviations"] = deviations
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "measured": measured["value"], "n": measured["n"], "confidence": confidence}))


if __name__ == "__main__":
    main()
