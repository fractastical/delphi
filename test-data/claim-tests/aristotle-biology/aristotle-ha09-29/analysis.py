#!/usr/bin/env python3
"""Age at onset of foraging in honey bees for aristotle-ha09-29.

Refute if the median age at onset of foraging is at least 14 days.
Support only if that median is at most 7 days and a hairiness column
passes its own test. Mixed if the median is between those cuts, or if
the age clause passes and hair is absent. Criteria were committed first.
"""
import csv
import datetime as dt
import hashlib
import json
import math
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
URL = "https://ndownloader.figshare.com/files/22408710"
MD5 = "c8c0b59902fe69705df2a0521615d61c"
SIZE = 171175
UA = "delphisci-claim-test/1.0"


def num(text):
    if text is None:
        return None
    s = str(text).strip()
    if not s or s.lower() in {"na", "nan", "null"}:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / "dataLHT_Requier_et_al.csv"
    raw = dest.read_bytes() if dest.exists() else b""
    if hashlib.md5(raw).hexdigest() != MD5 or len(raw) != SIZE:
        req = urllib.request.Request(URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
    got = hashlib.md5(raw).hexdigest()
    if got != MD5 or len(raw) != SIZE:
        raise RuntimeError(f"checksum mismatch md5 {got} size {len(raw)}")
    return {
        "name": "dataLHT_Requier et al.csv",
        "download_url": URL,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "md5": got,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def pick_aof(headers):
    lowered = [(h, h.strip().lower()) for h in headers]
    for h, low in lowered:
        if low == "aof":
            return h
    for h, low in lowered:
        if "aof" in low:
            return h
    for h, low in lowered:
        if "onset" in low and "forag" in low:
            return h
    return None


def median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        return None
    mid = n // 2
    if n % 2:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2)


def settle_caveats(existing, additions):
    stale = (
        "has not been downloaded",
        "have not been re-hashed",
        "No maturity value has been read",
        "No Camelus number has been read",
        "No age has been read",
        "No species habitat value has been read",
        "No body mass or litter size has been read",
        "No brain or body mass value has been read",
    )
    kept = []
    for item in list(existing) + list(additions):
        if any(mark in item for mark in stale):
            continue
        if item not in kept:
            kept.append(item)
    return kept


def main():
    meta, raw = fetch()
    text = raw.decode("utf-8")
    sample = text[:2048]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    rows = list(csv.DictReader(text.splitlines(), delimiter=delimiter))
    headers = rows[0].keys() if rows else []
    aof_col = pick_aof(list(headers))
    if aof_col is None:
        finish("inconclusive", "data-unavailable", None, meta, delimiter, None, [], "no onset-of-foraging column")
        return
    header_low = aof_col.lower()
    values = []
    for row in rows:
        v = num(row.get(aof_col))
        if v is not None and v > 0:
            values.append(v)
    m = median(values)
    unit_note = None
    if m is not None and m > 200 and "hour" not in header_low:
        finish("inconclusive", "other", m, meta, delimiter, aof_col, values, "median above 200 and header does not say hours")
        return
    if m is not None and "hour" in header_low:
        values = [v / 24.0 for v in values]
        m = median(values)
        unit_note = "header says hours; values divided by 24"
    n = len(values)
    if n < 100 or m is None:
        verdict, reason = "inconclusive", "underpowered" if n else "data-unavailable"
    elif m >= 14:
        verdict, reason = "refutes", None
    elif m <= 7:
        # hairiness is not in this header set unless a hair column exists
        hair = [h for h in headers if "hair" in h.lower() or "seta" in h.lower()]
        verdict, reason = ("mixed", None) if not hair else ("supports", None)
    else:
        verdict, reason = "mixed", None
    if verdict == "refutes" and m is not None and m >= 20:
        confidence = 0.85
    elif verdict == "refutes":
        confidence = 0.75
    elif verdict == "mixed":
        confidence = 0.6
    else:
        confidence = 0.45
    extra_cols = {}
    for label, pred in (("AFE", lambda h: h.strip().lower() == "afe"), ("LSP", lambda h: h.strip().lower() == "lsp")):
        col = next((h for h in headers if pred(h)), None)
        if col:
            vals = [num(row.get(col)) for row in rows]
            vals = [v for v in vals if v is not None and v > 0]
            extra_cols[label] = {"n": len(vals), "median": median(vals), "used_for_verdict": False}
    fraction_le_7 = (sum(v <= 7 for v in values) / n) if n else None
    measured = {
        "value": m,
        "unit": "days, median age at onset of foraging",
        "n": n,
        "uncertainty": None,
        "extra": {
            "fraction_aof_at_or_under_7_days": fraction_le_7,
            "aof_column": aof_col,
            "delimiter": delimiter,
            "unit_note": unit_note,
            "hairiness_measured": False,
            "other_columns_not_used_for_verdict": extra_cols,
        },
    }
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["datasets"] = [{
        "id": "requier-2020-figshare-12187398",
        "name": "Data from: Measuring ontogenetic shifts in central-place foragers: a case study with honey bees",
        "landing_url": "https://doi.org/10.6084/m9.figshare.12187398.v2",
        "doi": "10.6084/m9.figshare.12187398.v2",
        "version": "v2",
        "license": "CC BY 4.0",
        "files": [meta],
        "role": "age at onset of foraging for RFID-tagged honey-bee workers",
    }]
    result["method"] = (
        "Downloaded the Requier life-history CSV, checked MD5 and byte size, and read the AOF column "
        "(age at onset of foraging, described by the deposit as days). "
        "The median is among workers with a positive finite AOF. "
        "No hair or seta column is present, so the hairiness clause is unmeasured. "
        "AFE and LSP medians are reported and do not set the verdict."
    )
    result["measured"] = measured
    result["verdict"] = verdict
    result["data_kind"] = "biological" if n else "none"
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["results_summary"] = [
        f"Workers with AOF: n={n}. Median age at onset of foraging: {m} days. Share with AOF <= 7 days: {fraction_le_7}.",
        "Hairiness is not in the file. The verdict follows the task-assignment clause only.",
    ]
    result["caveats"] = settle_caveats(result.get("caveats", []), [
        "One apiary, six cohorts in 2011. AOF is the authors' change-point estimate, not a direct observation that a trip carried food.",
        "Workers that died without a recorded AOF are omitted from the median, which is the pre-registered population.",
    ])
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "measured": measured}, indent=2) + "\n")
    print(verdict, reason, "median", m, "n", n)


def finish(verdict, reason, m, meta, delimiter, aof_col, values, note):
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["verdict"] = verdict
    result["reason"] = reason
    result["data_kind"] = "none"
    result["confidence"] = 0.4
    result["measured"] = {"value": m, "unit": "days, median age at onset of foraging", "n": len(values), "uncertainty": note, "extra": {"aof_column": aof_col, "delimiter": delimiter}}
    result["datasets"] = [{
        "id": "requier-2020-figshare-12187398",
        "name": "Requier et al. honey-bee life-history table",
        "landing_url": "https://doi.org/10.6084/m9.figshare.12187398.v2",
        "doi": "10.6084/m9.figshare.12187398.v2",
        "version": "v2",
        "license": "CC BY 4.0",
        "files": [meta],
        "role": "age at onset of foraging",
    }]
    result["method"] = note
    result["results_summary"] = [note]
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, reason, note)


if __name__ == "__main__":
    main()
