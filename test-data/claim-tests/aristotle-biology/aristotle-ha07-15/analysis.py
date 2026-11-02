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
    """Father-axis labels only. A title that also names the mother is not the axis."""
    anchors = []
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            text = cell_text(value)
            if father_re.search(text) and age_re.search(text) and not re.search(r"(?i)mother", text):
                anchors.append((i, j, text))
    return anchors


def ages_across(matrix, anchor_row, anchor_col):
    """Longest age run on the header row at or just below an 'Age of father' label."""
    best = None
    for r in range(anchor_row, min(len(matrix), anchor_row + 4)):
        run = []
        started = False
        start_c = anchor_col if r == anchor_row else 0
        width = len(matrix[r])
        for c in range(start_c, width):
            parsed = parse_age(matrix[r][c])
            if parsed and parsed[0] in ("exact", "bin"):
                run.append((c, parsed))
                started = True
            elif not started:
                continue
            elif cell_text(matrix[r][c]) == "":
                continue
            else:
                break
        if len(run) >= 5 and (best is None or len(run) > len(best[1])):
            best = (r, run)
    return best


def sum_column(matrix, col, header_row):
    """Births down a father-age column, excluding the age header and any Total row."""
    total = 0.0
    seen = False
    for r, row in enumerate(matrix):
        if r <= header_row or col >= len(row):
            continue
        if cell_text(row[0]).lower() in ("total", "totals"):
            continue
        n = numeric(row[col])
        if n is not None and n >= 0:
            total += n
            seen = True
    return total if seen else None


def collect(matrix, anchors):
    tables = []
    for anchor_row, anchor_col, anchor_text in anchors:
        found = ages_across(matrix, anchor_row, anchor_col)
        if not found:
            continue
        header_row, run = found
        births = {}
        for col, parsed in run:
            total = sum_column(matrix, col, header_row)
            if total is None:
                continue
            births[parsed] = births.get(parsed, 0.0) + total
        tables.append({
            "anchor": anchor_text,
            "anchor_row": anchor_row,
            "header_row": header_row,
            "n_ages": len(births),
            "births": births,
        })
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
        for table in collect(matrix, anchors):
            table["sheet"] = sheet.name
            candidates.append(table)
    births = {}
    for table in candidates:
        for parsed, total in table["births"].items():
            births[parsed] = births.get(parsed, 0.0) + total
    layout = []
    for table in candidates:
        exacts = sorted(a for kind, a in table["births"] if kind == "exact")
        bins = sorted(a for kind, a in table["births"] if kind == "bin")
        layout.append({
            "sheet": table["sheet"],
            "anchor": table["anchor"],
            "n_ages": table["n_ages"],
            "exact_min": exacts[0] if exacts else None,
            "exact_max": exacts[-1] if exacts else None,
            "bin_lower_bounds": bins,
        })
    aggregated = [
        {"kind": parsed[0], "age": parsed[1], "births": total}
        for parsed, total in sorted(births.items(), key=lambda kv: (kv[0][0], kv[0][1]))
    ]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "layout.json").write_text(json.dumps({"sheets": layout, "aggregated": aggregated}, indent=2) + "\n")
    if not candidates:
        verdict, reason, conf = "inconclusive", "data-unavailable", rules["confidence_inconclusive"]
        measured = {"value": None, "unit": "live births to fathers aged 70", "n": 0, "extra": {"tables": 0}}
        method = (
            "No cell named the father's age without also naming the mother, and no horizontal "
            "age header of at least five ages sat under such a label, so no birth counts were used."
        )
        summary = ["No father-age axis found.", f"Sheets: {[s.name for s in book.sheets()]}"]
    else:
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
        exacts = sorted(a for kind, a in births if kind == "exact")
        bins = sorted(a for kind, a in births if kind == "bin")
        measured = {
            "value": c70["births"],
            "unit": "live births on the father-age axis at 70 (exact year or bin starting at 70)",
            "n": len(births),
            "extra": {
                "anchor": candidates[0]["anchor"],
                "n_year_sheets": len(candidates),
                "exact_min": exacts[0] if exacts else None,
                "exact_max": exacts[-1] if exacts else None,
                "bin_lower_bounds": bins,
                "age_60": c60,
                "age_70": c70,
                "refute_60": refute60,
                "refute_70": refute70,
            },
        }
        method = (
            "Opened the ONS workbook with xlrd. Each year sheet has a cell 'Age of father' and, on the "
            "next row, father's age across columns. Births were summed down each of those columns, "
            "excluding the Total row, then summed across the year sheets. A title that names both "
            "mother and father was not used as the axis. The preregistered thresholds were applied: "
            "an open bin counts only when its lower bound is 60 or 70."
        )
        summary = [
            f"Father-age axis on {len(candidates)} year sheets, anchor {candidates[0]['anchor']!r}.",
            f"Exact ages {exacts[0] if exacts else None}–{exacts[-1] if exacts else None}; open bins at {bins}.",
            f"Age 60: {c60}. Age 70: {c70}.",
            f"Verdict {verdict}.",
        ]
        if not hold60 and not hold70 and bins and (not exacts or exacts[-1] < 60):
            note = (
                f"The father-age header lists exact ages {exacts[0] if exacts else 'none'}–"
                f"{exacts[-1] if exacts else 'none'} and open bins whose lower bounds are {bins}. "
                "A bin counts for age 60 or 70 only when its lower bound is that age, so these bins were not used as those counts."
            )
            if note not in result.get("caveats", []):
                result.setdefault("caveats", []).append(note)
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
