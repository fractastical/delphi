#!/usr/bin/env python3
"""aristotle-ha09-29: honey-bee age at onset of foraging, and hairiness if present.

Thresholds are those committed in result.json. Run: python3 analysis.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import statistics
from pathlib import Path

import requests
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
URL = "https://ndownloader.figshare.com/files/22408710"
UA = "delphisci-claim-test/aristotle-ha09-29"


def norm(header):
    return re.sub(r"[^a-z0-9]+", "", header.lower())


def num(value):
    """Parse a cell. Commas are decimal marks unless they are thousands separators."""
    if value is None:
        return None
    s = str(value).strip().replace(" ", "")
    if s == "" or s.lower() in {"na", "nan", "null", ".", "-"}:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", s):
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def find_aof(headers):
    for h in headers:
        n = norm(h)
        if n == "aof" or n.startswith("aof") or "onsetofforaging" in n or "ageatonsetofforaging" in n:
            return h
        if "forag" in n and any(k in n for k in ("age", "onset", "day")):
            return h
    return None


def find_life(headers):
    for h in headers:
        n = norm(h)
        # LSP is the lifespan abbreviation in the Requier file (see deviations).
        if n == "lsp" or "lifespan" in n or n in {"longevity", "agelast", "agelastdays"} or "agelast" in n:
            return h
    return None


def find_hair(headers):
    for h in headers:
        n = norm(h)
        if "hair" in n or "pile" in n:
            return h
    return None


def find_age(headers, aof_name):
    for h in headers:
        if h == aof_name:
            continue
        n = norm(h)
        if n in {"age", "agedays", "workerage", "beage"} or n.startswith("age") and "forag" not in n and "exit" not in n:
            return h
    return None


def fetch():
    DATA.mkdir(exist_ok=True)
    path = DATA / "dataLHT_Requier_et_al.csv"
    if not path.exists():
        r = requests.get(URL, headers={"User-Agent": UA}, timeout=120)
        r.raise_for_status()
        path.write_bytes(r.content)
        retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    raw = path.read_bytes()
    return raw, retrieved


def read_table(raw):
    text = raw.decode("utf-8-sig")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return list(reader), reader.fieldnames or []


def main():
    raw, retrieved = fetch()
    rows, headers = read_table(raw)
    result = json.loads((HERE / "result.json").read_text())
    result["datasets"] = [{
        "id": "requier-2020-honeybee-lht-figshare-12187398",
        "name": "Data from: Measuring ontogenetic shifts in central-place foragers: a case study with honey bees",
        "landing_url": "https://doi.org/10.6084/m9.figshare.12187398.v2",
        "doi": "10.6084/m9.figshare.12187398.v2",
        "version": "v2",
        "license": "CC BY 4.0",
        "files": [{
            "name": "dataLHT_Requier et al.csv",
            "download_url": URL,
            "retrieved_at": retrieved,
            "byte_size": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }],
        "role": "age at onset of foraging and lifespan of individually monitored honey-bee workers",
    }]
    aof_col = find_aof(headers)
    life_col = find_life(headers)
    hair_col = find_hair(headers)
    age_col = find_age(headers, aof_col) if aof_col else None

    def finish(verdict, reason, measured, summary):
        result.update(status="complete", verdict=verdict, data_kind="biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none",
                      confidence={"supports": 0.70, "refutes": 0.70, "mixed": 0.55}.get(verdict, 0.40))
        if verdict == "inconclusive" and reason == "data-unavailable":
            result["data_kind"] = "none"
        else:
            result["data_kind"] = "biological"
        if reason and verdict == "inconclusive":
            result["reason"] = reason
        else:
            result.pop("reason", None)
        result["measured"] = measured
        result["method"] = (
            "Downloaded the Requier figshare life-history CSV. Decimal commas were parsed as "
            "decimal marks. The lifespan column is named LSP and is the lifespan variable named "
            "in the figshare description, so the primary rule is the median of AOF/LSP with "
            "cutoffs 0.35 and 0.50. Hairiness is scored only when a hairiness column and a "
            "separate worker-age column are both present. Thresholds were not changed."
        )
        result["deviations"] = [{
            "date": "2026-11-02",
            "thresholds_unchanged": True,
            "reason": (
                "Two parser fixes after the file header was read, before the verdict was kept. "
                "The CSV uses semicolon separators and decimal commas. A first execution stripped "
                "commas, so 47,5 became 475 and the median AOF was the fabricated value 46 days; "
                "that execution was discarded and is not the recorded measurement. The lifespan "
                "column is headed LSP, an abbreviation the original header list did not contain. "
                "LSP is mapped to lifespan so the pre-registered primary statistic, median "
                "AOF/lifespan, is the one that sets the verdict. The 0.35 and 0.50 cutoffs are unchanged."
            ),
        }]
        result["results_summary"] = summary
        DERIVED.mkdir(exist_ok=True)
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(verdict, reason, summary[0] if summary else "")

    if not aof_col:
        finish("inconclusive", "data-unavailable", {
            "value": None, "unit": "median AOF/lifespan", "n": 0, "uncertainty": None,
            "extra": {"headers": headers},
        }, [f"No age-at-foraging column in headers: {headers}."])
        return

    task = {"column_aof": aof_col, "column_lifespan": life_col}
    ratios, aofs = [], []
    if life_col:
        for row in rows:
            aof = num(row.get(aof_col))
            life = num(row.get(life_col))
            if aof is None or life is None or aof <= 0 or life <= 0 or aof > life:
                continue
            aofs.append(aof)
            ratios.append(aof / life)
        n = len(ratios)
        task["n"] = n
        task["used_lifespan"] = True
        if n >= 1:
            med = float(statistics.median(ratios))
            task["median_aof_over_lifespan"] = med
            task["median_aof_days"] = float(statistics.median(aofs))
            task["median_lifespan_days"] = float(statistics.median([a / r for a, r in zip(aofs, ratios)]))
        if n < 100:
            task["state"] = "unknown"
            task["unknown_reason"] = "underpowered"
        elif med <= 0.35:
            task["state"] = "hold"
        elif med >= 0.50:
            task["state"] = "fail"
        else:
            task["state"] = "mixed"
    else:
        for row in rows:
            aof = num(row.get(aof_col))
            if aof is None or aof <= 0:
                continue
            aofs.append(aof)
        n = len(aofs)
        task["n"] = n
        task["used_lifespan"] = False
        if n >= 1:
            med = float(statistics.median(aofs))
            task["median_aof_days"] = med
        if n < 100:
            task["state"] = "unknown"
            task["unknown_reason"] = "underpowered"
        elif med <= 7:
            task["state"] = "hold"
        elif med >= 14:
            task["state"] = "fail"
        else:
            task["state"] = "mixed"

    hair = {"column": hair_col, "age_column": age_col, "state": "absent"}
    if hair_col and age_col:
        ages, hairs = [], []
        for row in rows:
            a = num(row.get(age_col))
            h = num(row.get(hair_col))
            if a is None or h is None:
                continue
            ages.append(a)
            hairs.append(h)
        hair["n"] = len(ages)
        if len(ages) >= 100:
            rho, p = stats.spearmanr(ages, hairs)
            hair["spearman_rho"] = float(rho)
            hair["spearman_p"] = float(p)
            if rho >= 0.20 and p < 0.05:
                hair["state"] = "hold"
            elif rho <= -0.20 and p < 0.05:
                hair["state"] = "fail"
            else:
                hair["state"] = "mixed"
        else:
            hair["state"] = "unknown"
            hair["unknown_reason"] = "underpowered"

    scored = []
    if task["state"] in {"hold", "fail", "mixed"}:
        scored.append(task["state"])
    if hair["state"] in {"hold", "fail", "mixed"}:
        scored.append(hair["state"])
    states = set(scored)
    if not scored:
        reason = task.get("unknown_reason") or "data-unavailable"
        if reason not in {"underpowered", "data-unavailable"}:
            reason = "underpowered"
        verdict = "inconclusive"
    elif "fail" in states and "hold" in states:
        verdict, reason = "mixed", None
    elif "fail" in states:
        verdict, reason = "refutes", None
    elif states == {"hold"} and len(scored) == 2:
        verdict, reason = "supports", None
    elif states == {"hold"}:
        verdict, reason = "inconclusive", "other"
    else:
        # Task between the cutoffs, with hair absent, holding, or also between the cutoffs.
        verdict, reason = "mixed", None

    value = task.get("median_aof_over_lifespan", task.get("median_aof_days"))
    unit = "median of AOF/lifespan" if task.get("used_lifespan") else "median AOF in days"
    finish(verdict, reason, {
        "value": value,
        "unit": unit,
        "n": task.get("n", 0),
        "uncertainty": None,
        "extra": {"task": task, "hair": hair, "headers": headers},
    }, [
        f"Task state {task.get('state')} on n={task.get('n')} using lifespan={task.get('used_lifespan')}; median ratio={task.get('median_aof_over_lifespan')}; median AOF days={task.get('median_aof_days')}.",
        f"Hair state {hair.get('state')}.",
        f"Verdict {verdict}.",
    ])


if __name__ == "__main__":
    main()
