#!/usr/bin/env python3
"""Age at natural menopause in NHANES 2017-2018, and Eurostat births at ages 48 and 49.

Decision rule: result.json pass_criterion, committed before these files were downloaded.
Y_GE50 and NHANES age at last live birth are reported only and do not set the verdict.
"""
import datetime as dt
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
FILES = {
    "RHQ_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RHQ_J.xpt",
    "DEMO_J.xpt": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
}
EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_fagec"
LOCKED = {
    "hypothesis", "pass_criterion", "fail_criterion", "planned_datasets", "test_contract",
    "claim_id", "claim_iri", "project", "preregistered_at", "interpretation",
}


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    last = None
    if not dest.exists() or dest.stat().st_size == 0:
        for i in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "delphisci-claim-test"})
                with urllib.request.urlopen(req, timeout=180) as resp:
                    dest.write_bytes(resp.read())
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(2 * (i + 1))
        else:
            raise last
    raw = dest.read_bytes()
    return {
        "name": dest.name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def numeric(series):
    if getattr(series.dtype, "kind", "") == "O" or str(series.dtype) == "object":
        series = series.apply(lambda x: x.decode() if isinstance(x, (bytes, bytearray)) else x)
    return pd.to_numeric(series, errors="coerce")


def weighted_median(ages, weights):
    order = sorted(range(len(ages)), key=lambda i: ages[i])
    total = sum(weights[i] for i in order)
    if total <= 0:
        return None
    running = 0.0
    half = 0.5 * total
    for i in order:
        running += weights[i]
        if running >= half:
            return float(ages[i])
    return float(ages[order[-1]])


def meno_far(value):
    return value <= 35 or value >= 45


def meno_near(value):
    return 38 <= value <= 42


def eurostat_births():
    query = urllib.parse.urlencode([
        ("format", "JSON"),
        ("lang", "en"),
        ("age", "Y48"),
        ("age", "Y49"),
        ("age", "Y_GE50"),
    ])
    url = EUROSTAT + "?" + query
    info, raw = fetch(url, DATA / "demo_fagec.json")
    payload = json.loads(raw.decode("utf-8"))
    dims = payload["id"]
    sizes = payload["size"]
    categories = []
    for dim in dims:
        index = payload["dimension"][dim]["category"]["index"]
        inv = [None] * len(index)
        for code, pos in index.items():
            inv[int(pos)] = code
        categories.append(inv)
    age_i = dims.index("age")
    geo_i = dims.index("geo")
    labels = []
    for dim in dims:
        labels.append(payload["dimension"][dim]["category"].get("label") or {})
    marital_i = None
    for i, dim in enumerate(dims):
        codes = set(categories[i])
        if codes & {"MAR", "NMAR", "TOTAL", "LBIRTH"} or "marital" in dim.lower() or "wstatus" in dim.lower():
            marital_i = i
    total_codes = set()
    if marital_i is not None:
        for code, label in labels[marital_i].items():
            if "total" in str(label).lower() or str(code).upper() == "TOTAL":
                total_codes.add(code)
    use_total = bool(total_codes)
    births_48_49 = 0.0
    births_ge50 = 0.0
    cells_48_49 = 0
    suspicious = False
    for key, val in (payload.get("value") or {}).items():
        if val is None:
            continue
        idx = int(key)
        coords = []
        for size in reversed(sizes):
            coords.append(idx % size)
            idx //= size
        coords = list(reversed(coords))
        age = categories[age_i][coords[age_i]]
        geo = str(categories[geo_i][coords[geo_i]])
        if len(geo) != 2 or "_" in geo:
            continue
        if marital_i is not None:
            marital = categories[marital_i][coords[marital_i]]
            if use_total and marital not in total_codes:
                continue
            if not use_total and str(marital).upper() == "TOTAL":
                continue
        value = float(val)
        if value > 1e7:
            suspicious = True
        if age in {"Y48", "Y49"}:
            births_48_49 += value
            if value > 0:
                cells_48_49 += 1
        elif age == "Y_GE50":
            births_ge50 += value
    return {
        "file": info,
        "births_y48_plus_y49": births_48_49,
        "positive_cells_y48_y49": cells_48_49,
        "births_y_ge50_not_used": births_ge50,
        "suspicious_cell": suspicious,
        "dimensions": dims,
        "marital_dimension": None if marital_i is None else dims[marital_i],
        "used_total_codes": sorted(total_codes),
        "used_marital_total": use_total,
    }


def write_result(fields):
    doc = json.loads(RESULT.read_text())
    for key in fields:
        if key in LOCKED:
            raise SystemExit("refusing to edit locked field " + key)
    doc.update(fields)
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")


def nhanes_datasets(files):
    return [
        {
            "id": "nhanes-2017-2018-rhq-j",
            "name": "NHANES 2017-2018 Reproductive Health (RHQ_J)",
            "landing_url": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/RHQ_J.htm",
            "doi": None,
            "version": "2017-2018",
            "license": "U.S. government public-use file (National Center for Health Statistics)",
            "files": [f for f in files if f["name"] == "RHQ_J.xpt"],
            "role": "age at last menstrual period among women who gave menopause as the reason periods had stopped",
        },
        {
            "id": "nhanes-2017-2018-demo-j",
            "name": "NHANES 2017-2018 Demographics (DEMO_J)",
            "landing_url": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.htm",
            "doi": None,
            "version": "2017-2018",
            "license": "U.S. government public-use file (National Center for Health Statistics)",
            "files": [f for f in files if f["name"] == "DEMO_J.xpt"],
            "role": "interview weight WTINT2YR",
        },
    ]


def main():
    DERIVED.mkdir(parents=True, exist_ok=True)
    try:
        files = []
        for name, url in FILES.items():
            info, _ = fetch(url, DATA / name)
            files.append(info)
        rhq = pd.read_sas(DATA / "RHQ_J.xpt", format="xport")
        demo = pd.read_sas(DATA / "DEMO_J.xpt", format="xport")
    except Exception as exc:  # noqa: BLE001
        measured = {"value": None, "unit": "years (weighted median age at natural menopause)", "n": 0, "uncertainty": None, "extra": {"error": str(exc)}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.3, "data_kind": "none", "measured": measured,
            "method": "An NHANES file could not be downloaded or read.",
            "results_summary": [str(exc)],
        })
        print("nhanes failed", exc)
        return
    needed = {"RHQ060", "RHD043", "SEQN"}
    if not needed <= set(rhq.columns) or "WTINT2YR" not in demo.columns:
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.35, "data_kind": "none",
            "measured": {"value": None, "unit": "years (weighted median age at natural menopause)", "n": 0, "uncertainty": None, "extra": {"columns_present": sorted(needed & set(rhq.columns))}},
            "datasets": nhanes_datasets(files),
            "method": "A pre-registered NHANES column was absent.",
            "results_summary": ["Required column missing."],
        })
        return
    rhq = rhq.copy()
    demo = demo.copy()
    rhq["SEQN"] = numeric(rhq["SEQN"]).astype("int64")
    demo["SEQN"] = numeric(demo["SEQN"]).astype("int64")
    demo["WTINT2YR"] = numeric(demo["WTINT2YR"])
    merged = rhq.merge(demo[["SEQN", "WTINT2YR"]], on="SEQN", how="left")
    reason_code = numeric(merged["RHD043"])
    age = numeric(merged["RHQ060"])
    natural = reason_code == 7
    if merged.loc[natural, "WTINT2YR"].notna().sum() == 0:
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "data-unavailable",
            "confidence": 0.35, "data_kind": "none",
            "measured": {"value": None, "unit": "years", "n": 0, "uncertainty": None, "extra": {}},
            "datasets": nhanes_datasets(files),
            "method": "The interview weight did not join to women coded as menopause.",
            "results_summary": ["WTINT2YR join failed."],
        })
        return
    natural_age = age.loc[natural]
    n_nat = int(natural_age.notna().sum())
    n_19 = int((natural_age == 19).sum())
    n_60 = int((natural_age == 60).sum())
    if n_nat and (n_19 / n_nat > 0.05 or n_60 / n_nat > 0.05):
        measured = {"value": None, "unit": "years (weighted median age at natural menopause)", "n": n_nat, "uncertainty": None, "extra": {"share_code_19": n_19 / n_nat, "share_code_60": n_60 / n_nat}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "other", "confidence": 0.4,
            "data_kind": "biological", "measured": measured, "datasets": nhanes_datasets(files),
            "method": "A top or bottom code exceeded the pre-registered 5 percent gate.",
            "results_summary": [f"Code 19 share {n_19 / n_nat:.4f}; code 60 share {n_60 / n_nat:.4f}."],
        })
        return
    exact = natural & (age >= 20) & (age <= 59) & (merged["WTINT2YR"] > 0)
    ages = age.loc[exact].astype(float).tolist()
    weights = merged.loc[exact, "WTINT2YR"].astype(float).tolist()
    if len(ages) < 100:
        measured = {"value": None, "unit": "years (weighted median age at natural menopause)", "n": len(ages), "uncertainty": None, "extra": {}}
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        write_result({
            "status": "complete", "verdict": "inconclusive", "reason": "underpowered", "confidence": 0.4,
            "data_kind": "biological", "measured": measured, "datasets": nhanes_datasets(files),
            "method": "Fewer than 100 exact menopause ages remained.",
            "results_summary": [f"Exact ages: {len(ages)}."],
        })
        return
    w_med = weighted_median(ages, weights)
    u_med = weighted_median(ages, [1.0] * len(ages))
    tail = sum(1 for a in ages if 48 <= a <= 52)
    tail_ok = tail >= 10 and tail <= 0.5 * len(ages)
    both_near = meno_near(w_med) and meno_near(u_med)
    both_far = meno_far(w_med) and meno_far(u_med)
    euro = None
    euro_error = None
    try:
        euro = eurostat_births()
    except Exception as exc:  # noqa: BLE001
        euro_error = str(exc)
    births_ok = bool(euro) and not euro["suspicious_cell"] and euro["births_y48_plus_y49"] >= 1
    if both_far:
        verdict, confidence, reason = "refutes", 0.75, None
    elif both_near and tail_ok and births_ok:
        verdict, confidence, reason = "supports", 0.50, None
    else:
        verdict, confidence, reason = "mixed", 0.55, None
    measured = {
        "value": w_med,
        "unit": "years (weighted median age at natural menopause, RHQ060 among RHD043=7)",
        "n": len(ages),
        "uncertainty": None,
        "extra": {
            "weighted_median_years": w_med,
            "unweighted_median_years": u_med,
            "both_near": both_near,
            "both_far": both_far,
            "n_age_48_to_52": tail,
            "tail_condition": tail_ok,
            "maximum_exact_age": max(ages),
            "minimum_exact_age": min(ages),
            "eurostat": None if euro is None else {k: v for k, v in euro.items() if k != "file"},
            "eurostat_error": euro_error,
            "beyond_age_50_births_scored": False,
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    ds = nhanes_datasets(files)
    if euro and euro.get("file"):
        ds.append({
            "id": "eurostat-demo-fagec",
            "name": "Eurostat live births by mother's age and legal marital status (demo_fagec)",
            "landing_url": "https://ec.europa.eu/eurostat/databrowser/view/demo_fagec/default/table",
            "doi": None,
            "version": "dissemination API at retrieval",
            "license": "Eurostat copyright; reuse under the Eurostat reuse policy",
            "files": [euro["file"]],
            "role": "live births at mother's ages 48 and 49; the Y_GE50 bin is stored and not scored",
        })
    summary = [
        f"Weighted median {w_med} years; unweighted median {u_med} years; n={len(ages)}; ages 48-52: {tail}.",
        f"Eurostat births at 48 plus 49: {None if euro is None else euro['births_y48_plus_y49']}. Y_GE50 sum (not scored): {None if euro is None else euro['births_y_ge50_not_used']}.",
        "Births after the fiftieth birthday were not scored.",
    ]
    if euro_error:
        summary.append("Eurostat request failed: " + euro_error)
    fields = {
        "status": "complete", "verdict": verdict, "confidence": confidence, "data_kind": "biological",
        "measured": measured, "datasets": ds,
        "method": "Restricted RHQ_J to RHD043=7, kept exact RHQ060 ages 20-59, and computed weighted and unweighted medians with WTINT2YR. Separately summed Eurostat demo_fagec live births at ages Y48 and Y49 for two-letter geographies. Y_GE50 was not used in the verdict.",
        "results_summary": summary,
    }
    if reason:
        fields["reason"] = reason
    doc = json.loads(RESULT.read_text())
    if euro_error:
        doc["caveats"] = list(doc.get("caveats") or []) + ["Eurostat demo_fagec could not be read: " + euro_error]
    note = (
        "Deviation, 2026-11-02: the first run of this script summed every indic_de category. "
        "The pre-registered rule is to use the total category when one is present. In demo_fagec that total is coded LBIRTH "
        "('Live births - total'), not TOTAL. This run keeps only categories whose label contains 'total'. "
        "The menopause medians, which decide a refute, do not use this sum."
    )
    deviations = list(doc.get("deviations") or [])
    if not any("LBIRTH" in str(item) for item in deviations):
        deviations.append({"date": "2026-11-02", "text": note})
    doc["deviations"] = deviations
    fr_note = "Eurostat two-letter geography codes include both FR and FX, so France can contribute twice to the birth sum. The support rule uses only whether that sum is at least 1."
    caveats = list(doc.get("caveats") or [])
    if fr_note not in caveats:
        caveats.append(fr_note)
    doc["caveats"] = caveats
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    write_result(fields)
    print(verdict, w_med, u_med, tail, None if euro is None else euro["births_y48_plus_y49"])


if __name__ == "__main__":
    main()
