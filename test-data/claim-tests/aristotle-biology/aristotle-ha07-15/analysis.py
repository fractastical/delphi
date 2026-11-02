#!/usr/bin/env python3
"""Live births by single year of father's age, England and Wales, 2000–2016.

Requires xlrd (BIFF .xls). Thresholds come from result.json.
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT = HERE / "result.json"
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test/aristotle-ha07-15"}


def fetch(url, dest):
    DATA.mkdir(parents=True, exist_ok=True)
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=120) as r:
            dest.write_bytes(r.read())
    raw = dest.read_bytes()
    return {
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
    }


def cell_text(value):
    if value is None or value == "":
        return ""
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value).strip()


def parse_age(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if float(value) == int(value) and 10 <= int(value) <= 110:
            return ("exact", int(value))
        return None
    text = cell_text(value).lower().replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    m = re.fullmatch(r"(\d{2})", text)
    if m and 10 <= int(m.group(1)) <= 110:
        return ("exact", int(m.group(1)))
    m = re.fullmatch(r"(\d{2})\s*(\+|and over|or over|and above|or above).*", text)
    if m:
        return ("bin", int(m.group(1)))
    m = re.fullmatch(r"(\d{2})\s*-\s*(\d{2})", text)
    if m:
        return ("range", int(m.group(1)), int(m.group(2)))
    return None


def numeric(value):
    if isinstance(value, bool) or value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if re.fullmatch(r"-?\d+(\.\d+)?", text):
        return float(text)
    return None


def sheet_matrix(sheet):
    rows = []
    for r in range(sheet.nrows):
        rows.append([sheet.cell_value(r, c) for c in range(sheet.ncols)])
    return rows


def find_anchors(matrix, father_re, age_re):
    anchors = []
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            text = cell_text(value)
            if father_re.search(text) and age_re.search(text):
                anchors.append((i, j, text))
    return anchors


def ages_down(matrix, anchor_row):
    """Return (start_row, age_col, list of (row, parsed age)) for the longest run below an anchor."""
    best = None
    for col in range(len(matrix[0]) if matrix else 0):
        run = []
        for r in range(anchor_row + 1, len(matrix)):
            parsed = parse_age(matrix[r][col])
            if parsed and parsed[0] in ("exact", "bin"):
                run.append((r, parsed))
            elif run and cell_text(matrix[r][col]) == "":
                continue
            elif run:
                break
        if len(run) >= 5 and (best is None or len(run) > len(best[2])):
            best = (run[0][0], col, run)
    return best


def sum_row_except(matrix, row, skip_col):
    total = 0.0
    seen = False
    for c, value in enumerate(matrix[row]):
        if c == skip_col:
            continue
        n = numeric(value)
        if n is not None and n >= 0:
            total += n
            seen = True
    return total if seen else None


def collect(matrix, anchors):
    tables = []
    for anchor_row, anchor_col, anchor_text in anchors:
        found = ages_down(matrix, anchor_row)
        if not found:
            continue
        _, age_col, run = found
        births = {}
        for row, parsed in run:
            total = sum_row_except(matrix, row, age_col)
            if total is None:
                continue
            births.setdefault(parsed, 0.0)
            births[parsed] += total
        tables.append({"anchor": anchor_text, "anchor_row": anchor_row, "n_ages": len(births), "births": births})
    return tables


def clause(births, age):
    exact = births.get(("exact", age))
    bin_total = births.get(("bin", age))
    if exact is not None:
        return {"kind": "exact", "births": exact, "holds": exact >= 1}
    if bin_total is not None:
        return {"kind": "bin", "births": bin_total, "holds": bin_total >= 1}
    return {"kind": "missing", "births": None, "holds": False}


def can_refute(births, age, rules):
    exact_ages = sorted(a for kind, a in births if kind == "exact")
    if not exact_ages:
        return False
    needed = list(range(rules["refute_age_min"], rules["refute_age_max"] + 1))
    if any(a not in exact_ages for a in needed):
        return False
    young = sum(births.get(("exact", a), 0.0) for a in range(rules["young_min"], rules["young_max"] + 1))
    older = sum(births.get(("exact", a), 0.0) for a in exact_ages if a >= age)
    return young > 0 and older == 0


def main():
    import xlrd
    result = json.loads(RESULT.read_text())
    rules = result["rules"]
    exp = result["expected_files"][0]
    meta = fetch(exp["download_url"], DATA / exp["name"])
    father_re = re.compile(rules["anchor_pattern"])
    age_re = re.compile(rules["age_pattern"])
    book = xlrd.open_workbook(DATA / exp["name"])
    candidates = []
    for sheet in book.sheets():
        matrix = sheet_matrix(sheet)
        anchors = find_anchors(matrix, father_re, age_re)
        # Sheet name can identify the table if cells say only "Age".
        if not anchors and father_re.search(sheet.name) and age_re.search(sheet.name):
            anchors = [(0, 0, sheet.name)]
        for table in collect(matrix, anchors):
            table["sheet"] = sheet.name
            candidates.append(table)
    candidates.sort(key=lambda t: t["n_ages"], reverse=True)
    chosen = candidates[0] if candidates else None
    layout = []
    for table in candidates[:8]:
        ages = []
        for parsed, total in sorted(table["births"].items(), key=lambda kv: (kv[0][0], kv[0][1])):
            ages.append({"kind": parsed[0], "age": parsed[1], "births": total})
        layout.append({"sheet": table["sheet"], "anchor": table["anchor"], "n_ages": table["n_ages"], "ages": ages})
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "layout.json").write_text(json.dumps(layout, indent=2) + "\n")
    if not chosen:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
        measured = {"value": None, "unit": "live births to fathers aged 70", "n": 0, "extra": {"tables": 0}}
        method = "No cell or sheet name matched both 'father' and 'age' with a run of at least five ages beneath it, so no birth counts were used."
        summary = ["No father-age table found.", f"Sheets: {[s.name for s in book.sheets()]}"]
    else:
        births = chosen["births"]
        c60 = clause(births, 60)
        c70 = clause(births, 70)
        refute60 = can_refute(births, 60, rules)
        refute70 = can_refute(births, 70, rules)
        hold60 = bool(c60["holds"])
        hold70 = bool(c70["holds"])
        if hold60 and hold70:
            verdict, reason, conf = "supports", None, rules["confidence_supports"]
        elif refute60 and refute70:
            verdict, reason, conf = "refutes", None, rules["confidence_refutes"]
        elif refute70 and hold60:
            verdict, reason, conf = "mixed", None, rules["confidence_mixed"]
        elif refute60 and not hold70:
            verdict, reason, conf = "refutes", None, rules["confidence_refutes"]
        else:
            verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
        measured = {
            "value": c70["births"],
            "unit": "live births on the father-age axis at 70 (exact year or bin starting at 70)",
            "n": chosen["n_ages"],
            "extra": {
                "sheet": chosen["sheet"],
                "anchor": chosen["anchor"],
                "age_60": c60,
                "age_70": c70,
                "refute_60": refute60,
                "refute_70": refute70,
                "n_candidate_tables": len(candidates),
            },
        }
        method = (
            f"Opened the ONS workbook with xlrd. Used the father-age table with the most age rows "
            f"(sheet {chosen['sheet']!r}, anchor {chosen['anchor']!r}), summed numeric cells on each age row "
            "across the other columns, and applied the preregistered 60 and 70 thresholds."
        )
        summary = [
            f"Sheet {chosen['sheet']}, anchor {chosen['anchor']}, age rows {chosen['n_ages']}.",
            f"Age 60: {c60}. Age 70: {c70}.",
            f"Verdict {verdict}.",
        ]
    result["status"] = "complete"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["data_kind"] = "biological" if verdict != "inconclusive" else "none"
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["measured"] = measured
    result["method"] = method
    result["results_summary"] = summary
    # Licence phrase from the landing page, if the page states one.
    license_name = None
    try:
        req = urllib.request.Request(exp["landing_url"], headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            html = r.read().decode("utf-8", "replace").lower()
        if "open government licence" in html:
            license_name = "Open Government Licence"
    except Exception:
        license_name = None
    result["datasets"] = [{
        "id": "ons-live-births-age-mother-father-2000-2016",
        "name": "Live births by age of mother and father, 2000 to 2016, England and Wales",
        "landing_url": exp["landing_url"],
        "doi": None,
        "version": "released 2018-02-13",
        "license": license_name,
        "files": [meta],
        "role": "registered live births by single year of parental age",
    }]
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(verdict, measured.get("extra"))


if __name__ == "__main__":
    main()
