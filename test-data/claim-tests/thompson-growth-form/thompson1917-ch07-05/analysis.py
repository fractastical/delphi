#!/usr/bin/env python3
"""thompson1917-ch07-05: polar furrow versus four-way junction at the four-cell stage.

Reads Pennerstorfer 2015 (DOI 10.18452/17282) and parses the pole-contact tables
(Tables 1, 5 and 8) for the 4-cell stage. Thresholds are those committed in
result.json before this PDF was downloaded.

Requires: pymupdf (layout-aware text). numpy is not needed.
Run from this directory: python3 analysis.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
PDF_NAME = "pennerstorfer.pdf"
PDF_URL = "https://edoc.hu-berlin.de/server/api/core/bitstreams/1911bb6c-b4d1-4b9b-89ec-2be03e16abfc/content"
EXPECTED_MD5 = "2c50a890f0cfcf61bd2fc134138ef8c7"
EXPECTED_SIZE = 57993948


def fetch() -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / PDF_NAME
    if not path.exists() or path.stat().st_size != EXPECTED_SIZE:
        req = urllib.request.Request(PDF_URL, headers={"User-Agent": "delphisci-claim-test"})
        path.write_bytes(urllib.request.urlopen(req, timeout=180).read())
    raw = path.read_bytes()
    return {
        "download_url": PDF_URL,
        "retrieved_at": dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
        "matches_registered_md5": hashlib.md5(raw).hexdigest() == EXPECTED_MD5,
        "matches_registered_size": len(raw) == EXPECTED_SIZE,
    }


def _num(token: str):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%?[a-z]?", token)
    if not m:
        return None
    return float(m.group(1)), token.endswith("%") or "%" in token


def parse_tables(path: Path) -> list[dict]:
    doc = pymupdf.open(path)
    samples = []
    for page in doc:
        plain = page.get_text("text")
        if "Pole blastomere contacts" not in plain:
            continue
        species = re.search(r"in (P\. [a-z]+) embryos", plain)
        species = species.group(1) if species else "unknown"
        words = page.get_text("words")
        # header row that names the six contact columns
        header_y = None
        for w in words:
            if w[4] == "Animal" and 180 < w[1] < 280:
                header_y = round(w[1])
                break
        if header_y is None:
            continue
        col_words = [w for w in words if abs(w[1] - header_y) < 3 and w[4] in {"Animal", "Vegetal", "Both"}]
        col_words.sort(key=lambda w: w[0])
        # Animal, Vegetal, Both, Animal, Vegetal, Both
        names = [
            "polar_animal", "polar_vegetal", "polar_both",
            "x_animal", "x_vegetal", "x_both",
        ]
        if len(col_words) < 6:
            continue
        centers = [w[0] for w in col_words[:6]]
        # Numbers sit a few points above their stage label, and the next stage's
        # numbers sit just above that next label. Keep tokens nearer to "4-cell"
        # than to any other stage label, and within 10 points of it.
        stage_ys = {w[4]: w[1] for w in words if w[4] in {"4-cell", "8-cell", "16-cell", "32-cell", "64-cell"}}
        y4 = stage_ys["4-cell"]
        def nearest_stage(y):
            return min(stage_ys, key=lambda name: abs(y - stage_ys[name]))
        block = [w for w in words if nearest_stage(w[1]) == "4-cell" and abs(w[1] - y4) <= 10]
        # cluster into rows
        ys = sorted({round(w[1], 1) for w in block})
        rows_y: list[list[float]] = []
        for y in ys:
            if not rows_y or y - rows_y[-1][-1] > 6:
                rows_y.append([y])
            else:
                rows_y[-1].append(y)
        parsed_rows = []
        for cluster in rows_y:
            lo, hi = min(cluster) - 0.6, max(cluster) + 0.6
            toks = [w for w in block if lo <= w[1] <= hi]
            n_val = None
            cols = {name: 0.0 for name in names}
            for w in toks:
                parsed = _num(w[4])
                if not parsed:
                    continue
                value, is_pct = parsed
                if not is_pct and 100 <= w[0] <= 140:
                    n_val = int(value)
                    continue
                if is_pct:
                    nearest = min(range(6), key=lambda i: abs(w[0] - centers[i]))
                    if abs(w[0] - centers[nearest]) < 45:
                        cols[names[nearest]] = value
            if n_val is None:
                continue
            parsed_rows.append({"n": n_val, **cols})
        for i, row in enumerate(parsed_rows):
            kind = "4d-recorded" if len(parsed_rows) == 2 and i == 0 else (
                "fixed" if len(parsed_rows) == 2 else "fixed-only"
            )
            samples.append({"species": species, "preparation": kind, **row})
    return samples


def counts_for(row: dict) -> dict:
    n = row["n"]
    polar_pct = row["polar_animal"] + row["polar_vegetal"] + row["polar_both"]
    x_pct = row["x_animal"] + row["x_vegetal"] + row["x_both"]
    # Polar columns that sum to about 100% partition the sample: every embryo
    # has a polar furrow, and an X column is a second contact at the other pole.
    partitions = 90 <= polar_pct <= 110
    if partitions:
        n_x = int(round(x_pct / 100 * n))
        n_x = min(n_x, n)
        n_polar_only = n - n_x
        n_opening = 0
        in_scope = n
    else:
        n_polar_only = int(round(polar_pct / 100 * n))
        n_x = int(round(x_pct / 100 * n))
        if n_polar_only + n_x > n:
            # keep the proportions but do not invent embryos
            scale = n / (n_polar_only + n_x)
            n_polar_only = int(round(n_polar_only * scale))
            n_x = n - n_polar_only
        n_opening = n - n_polar_only - n_x
        in_scope = n_polar_only + n_x
    return {
        "n_embryos": n,
        "polar_percent_sum": polar_pct,
        "x_percent_sum": x_pct,
        "polar_columns_partition_the_sample": partitions,
        "n_polar_only": n_polar_only,
        "n_x": n_x,
        "n_opening_excluded": n_opening,
        "n_in_scope": in_scope,
        "unrounded_n_polar": polar_pct / 100 * n,
        "unrounded_n_x": x_pct / 100 * n,
    }


def verdict(n_in: int, n_polar: int, n_x: int) -> tuple[str, str | None]:
    if n_in < 20:
        return "inconclusive", "underpowered"
    x_frac = n_x / n_in
    p_frac = n_polar / n_in
    if x_frac >= 0.25:
        return "refutes", None
    if p_frac >= 0.90 and x_frac <= 0.10:
        return "supports", None
    return "mixed", None


def main():
    info = fetch()
    samples = parse_tables(DATA / PDF_NAME)
    detailed = []
    for row in samples:
        c = counts_for(row)
        detailed.append({**row, **c})
    n_in = sum(d["n_in_scope"] for d in detailed)
    n_polar = sum(d["n_polar_only"] for d in detailed)
    n_x = sum(d["n_x"] for d in detailed)
    n_open = sum(d["n_opening_excluded"] for d in detailed)
    # species with n_in_scope >= 10
    by_sp: dict[str, dict] = {}
    for d in detailed:
        s = by_sp.setdefault(d["species"], {"n_in_scope": 0, "n_polar_only": 0, "n_x": 0})
        s["n_in_scope"] += d["n_in_scope"]
        s["n_polar_only"] += d["n_polar_only"]
        s["n_x"] += d["n_x"]
    # The pre-registered species split uses n >= 10, then the same fractions
    # (X >= 0.25 refutes; polar >= 0.90 and X <= 0.10 supports). The pooled
    # n >= 20 gate is not re-applied inside a species.
    species_calls = {}
    support_sp, refute_sp = [], []
    for sp, s in by_sp.items():
        if s["n_in_scope"] < 10:
            species_calls[sp] = "underpowered"
            continue
        xf = s["n_x"] / s["n_in_scope"]
        pf = s["n_polar_only"] / s["n_in_scope"]
        if xf >= 0.25:
            v = "refutes"
        elif pf >= 0.90 and xf <= 0.10:
            v = "supports"
        else:
            v = "mixed"
        species_calls[sp] = v
        if v == "supports":
            support_sp.append(sp)
        if v == "refutes":
            refute_sp.append(sp)
    pooled, reason = verdict(n_in, n_polar, n_x)
    if support_sp and refute_sp:
        pooled, reason = "mixed", None
    x_frac = (n_x / n_in) if n_in else None
    p_frac = (n_polar / n_in) if n_in else None
    measured = {
        "value": round(x_frac, 4) if x_frac is not None else None,
        "unit": "fraction of full-contact 4-cell embryos with an X-furrow",
        "n": n_in,
        "uncertainty": "counts are nearest integers of the table percentages times n; see extra.unrounded",
        "extra": {
            "n_polar_only": n_polar,
            "n_x": n_x,
            "n_opening_excluded": n_open,
            "polar_fraction": round(p_frac, 4) if p_frac is not None else None,
            "x_fraction": round(x_frac, 4) if x_frac is not None else None,
            "unrounded_n_x": round(sum(d["unrounded_n_x"] for d in detailed), 3),
            "unrounded_n_polar_contact": round(sum(
                d["unrounded_n_polar"] if not d["polar_columns_partition_the_sample"] else d["n_embryos"] - d["unrounded_n_x"]
                for d in detailed
            ), 3),
            "species_calls": species_calls,
            "samples": detailed,
            "file": info,
        },
    }
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = pooled
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    # confidence: live 4D rows have no X-furrows; the X count is from fixed embryos,
    # and the author says a small opening is hard to tell from an X-furrow.
    if pooled == "refutes":
        conf = 0.45
    elif pooled == "supports":
        conf = 0.55
    elif pooled == "mixed":
        conf = 0.5
    else:
        conf = 0.4
    result["confidence"] = conf
    result["measured"] = {k: measured[k] for k in ("value", "unit", "n", "uncertainty")}
    result["measured"]["extra"] = {
        "n_polar_only": n_polar,
        "n_x": n_x,
        "n_opening_excluded": n_open,
        "polar_fraction": measured["extra"]["polar_fraction"],
        "species_calls": species_calls,
        "unrounded_n_x": measured["extra"]["unrounded_n_x"],
    }
    result["datasets"] = [{
        "id": "pennerstorfer-2015-phoronida-cleavage-edoc-17282",
        "name": "Cleavage and cell fates in Phoronida (Pennerstorfer 2015), doctoral thesis",
        "landing_url": "https://doi.org/10.18452/17282",
        "doi": "10.18452/17282",
        "version": "PDF issued 2015-07-28, bitstream md5 2c50a890f0cfcf61bd2fc134138ef8c7",
        "license": "CC BY-NC-ND 3.0 DE",
        "files": [{
            "name": PDF_NAME,
            "download_url": PDF_URL,
            "retrieved_at": info["retrieved_at"],
            "byte_size": info["byte_size"],
            "sha256": info["sha256"],
            "md5": info["md5"],
        }],
        "role": "scored 4-cell polar furrows and X-furrows in three Phoronis species",
    }]
    result["method"] = (
        "Downloaded the thesis PDF, checked its size and md5 against the repository record, "
        "and read Tables 1, 5 and 8 (pole blastomere contacts) by word coordinates. "
        "For each 4-cell row, a percentage is the value in that column and a blank is zero. "
        "Nearest-integer counts are percent times n. Where the polar-furrow columns sum to about 100 percent, "
        "every embryo is in full contact and an X-furrow column counts an embryo that also meets at a point at the other pole. "
        "Where only one contact type is filled, the rest of the row are openings and are excluded. "
        "The pre-registered fractions are applied to the pooled full-contact embryos."
    )
    result["deviations"] = [{
        "date": "2026-11-01",
        "what": "How a percentage table becomes a count.",
        "why": (
            "The pre-registration asked for counts. The tables print percentages of n, rounded by the author, "
            "and an embryo can carry a polar furrow at one pole and an X-furrow at the other. "
            "Counts are the nearest integer of percent times n. That rule is not a change of the 0.90 or 0.25 thresholds."
        ),
    }]
    result["caveats"] = [
        "Openings, where the four cells do not touch, are outside the claim's full-contact scope and are not counted as crosses.",
        "X-furrows in these tables come from fixed embryos. The 4D-recorded rows of P. pallida and P. muelleri show polar furrows or openings and no X-furrow.",
        "The author notes that a very small opening is difficult to tell from an X-furrow, so some X calls may be openings.",
        "Percentages were already rounded in the thesis, so a count can be off by about one embryo. The unrounded X total is stored beside the rounded one.",
        "One phoronid genus is not every animal egg the claim names.",
        info["matches_registered_md5"] and "The PDF md5 matches the repository record." or "The PDF md5 did not match the repository record.",
    ]
    result["results_summary"] = [
        f"Full-contact 4-cell embryos n={n_in}: polar furrow only {n_polar}, X-furrow {n_x}, X fraction {x_frac:.3f}. Openings excluded: {n_open}.",
        f"Pooled verdict {pooled}. Species calls: {species_calls}.",
    ]
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": pooled, "reason": reason, "n_in": n_in, "n_polar": n_polar, "n_x": n_x, "x_frac": x_frac, "species": species_calls}, indent=2))


if __name__ == "__main__":
    main()
