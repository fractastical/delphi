#!/usr/bin/env python3
"""Height gained by age five versus height gained after age five.

Pre-registered: R = (median at 5 years − median at birth) / (median at 19 years − median at 5 years).
Supports if R is in [0.35, 0.65] for both sexes. The WHO 0–5 tables are daily, so birth is day 0
and five years is the day nearest to 5 × 365.25, day 1826. Nineteen years is month 228 of the
WHO 2007 reference, the last age in that file.

Run: python3 analysis.py
"""

import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-ga01-23)"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
FILES = {
    "lhfa-boys-zscore-expanded-tables.xlsx": "https://cdn.who.int/media/docs/default-source/child-growth/child-growth-standards/indicators/length-height-for-age/expandable-tables/lhfa-boys-zscore-expanded-tables.xlsx",
    "lhfa-girls-zscore-expanded-tables.xlsx": "https://cdn.who.int/media/docs/default-source/child-growth/child-growth-standards/indicators/length-height-for-age/expandable-tables/lhfa-girls-zscore-expanded-tables.xlsx",
    "hfa-boys-z-who-2007-exp.xlsx": "https://cdn.who.int/media/docs/default-source/child-growth/growth-reference-5-19-years/height-for-age-(5-19-years)/hfa-boys-z-who-2007-exp.xlsx",
    "hfa-girls-z-who-2007-exp.xlsx": "https://cdn.who.int/media/docs/default-source/child-growth/growth-reference-5-19-years/height-for-age-(5-19-years)/hfa-girls-z-who-2007-exp.xlsx",
}
DAY_AT_FIVE = 1826  # nearest integer to 5 * 365.25 = 1826.25
MONTH_ADULT = 228
LOW, HIGH = 0.35, 0.65


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(name, url):
    DATA.mkdir(parents=True, exist_ok=True)
    dest = DATA / name
    if not dest.exists() or dest.stat().st_size == 0:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())
            final = resp.geturl()
    else:
        final = url
    raw = dest.read_bytes()
    return {
        "name": name,
        "download_url": final,
        "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def sheet_rows(raw):
    zf = zipfile.ZipFile(io.BytesIO(raw))
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
    table = []
    for row in root.findall(f"{NS}sheetData/{NS}row"):
        cells = {}
        for cell in row.findall(f"{NS}c"):
            ref = cell.get("r") or ""
            col = "".join(ch for ch in ref if ch.isalpha())
            vnode = cell.find(f"{NS}v")
            val = vnode.text if vnode is not None else ""
            if cell.get("t") == "s" and val.isdigit():
                val = shared[int(val)]
            cells[col] = val
        table.append(cells)
    header = table[0]
    col_by_name = {name: col for col, name in header.items()}
    age_col = col_by_name.get("Day") or col_by_name.get("Month")
    median_col = col_by_name.get("M")
    if age_col is None or median_col is None:
        raise SystemExit(f"Missing Day/Month or M in {header}")
    series = {}
    for cells in table[1:]:
        if age_col not in cells or median_col not in cells:
            continue
        series[int(float(cells[age_col]))] = float(cells[median_col])
    return series


def ratio(h0, h5, adult):
    gain_first = h5 - h0
    gain_rest = adult - h5
    gain_total = adult - h0
    return {
        "length_at_birth_cm": h0,
        "height_at_5_years_cm": h5,
        "height_at_19_years_cm": adult,
        "gain_birth_to_5_cm": gain_first,
        "gain_5_to_19_cm": gain_rest,
        "R_half_of_the_rest": gain_first / gain_rest,
        "R_half_of_total_postnatal_not_used": gain_first / gain_total,
        "inside_band": LOW <= (gain_first / gain_rest) <= HIGH,
    }


def main():
    infos = {}
    series = {}
    for name, url in FILES.items():
        info, raw = fetch(name, url)
        infos[name] = info
        series[name] = sheet_rows(raw)

    sexes = {}
    missing = []
    for sex, child_name, adult_name in (
        ("boys", "lhfa-boys-zscore-expanded-tables.xlsx", "hfa-boys-z-who-2007-exp.xlsx"),
        ("girls", "lhfa-girls-zscore-expanded-tables.xlsx", "hfa-girls-z-who-2007-exp.xlsx"),
    ):
        child = series[child_name]
        adult = series[adult_name]
        if 0 not in child or DAY_AT_FIVE not in child or MONTH_ADULT not in adult:
            missing.append(sex)
            continue
        sexes[sex] = ratio(child[0], child[DAY_AT_FIVE], adult[MONTH_ADULT])

    if missing or len(sexes) < 2:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.45
    else:
        inside = [sexes[s]["inside_band"] for s in ("boys", "girls")]
        if all(inside):
            verdict, reason, confidence = "supports", None, 0.75
        elif not any(inside):
            verdict, reason, confidence = "refutes", None, 0.75
        else:
            verdict, reason, confidence = "mixed", None, 0.5

    measured = {
        "value": None if "boys" not in sexes else round(sexes["boys"]["R_half_of_the_rest"], 4),
        "unit": "boys' ratio of height gained by age 5 to height gained from 5 to 19; girls are in extra",
        "n": 2 if len(sexes) == 2 else len(sexes),
        "uncertainty": None,
        "extra": {
            "day_used_for_age_five": DAY_AT_FIVE,
            "month_used_for_adult": MONTH_ADULT,
            "band": [LOW, HIGH],
            "sexes": {
                sex: {key: (round(val, 4) if isinstance(val, float) else val) for key, val in row.items()}
                for sex, row in sexes.items()
            },
            "missing_sexes": missing,
        },
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(
        json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n",
        encoding="utf-8",
    )
    result = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    result["status"] = "complete"
    result["data_kind"] = "biological" if sexes else "none"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "who-child-growth-standards-lhfa-0-5",
            "name": "WHO Child Growth Standards, length/height-for-age expanded z-score tables, birth to five years",
            "landing_url": "https://www.who.int/tools/child-growth-standards/standards/length-height-for-age",
            "doi": None,
            "version": "expanded z-score tables",
            "license": "WHO terms; free to use with acknowledgement",
            "files": [infos[name] for name in FILES if name.startswith("lhfa-")],
            "role": "median length at birth (day 0) and median height at day 1826",
        },
        {
            "id": "who-2007-height-for-age-5-19",
            "name": "WHO 2007 growth reference, height-for-age expanded z-score tables, 5–19 years",
            "landing_url": "https://www.who.int/tools/growth-reference-data-for-5to19-years/indicators/height-for-age",
            "doi": None,
            "version": "2007 expanded",
            "license": "WHO terms; free to use with acknowledgement",
            "files": [infos[name] for name in FILES if name.startswith("hfa-")],
            "role": "median height at month 228, used as adult height",
        },
    ]
    result["measured"] = measured
    result["method"] = (
        "The WHO length/height-for-age expanded tables give a daily median (column M). "
        "Birth is day 0. Age five is day 1826, the integer nearest to 5 × 365.25 days, "
        "because the table has no month column and the registered age was 60 months. "
        "Adult height is the median at month 228 in the WHO 2007 height-for-age tables, "
        "which run from month 61 to month 228. R is the gain from birth to day 1826 divided "
        "by the gain from day 1826 to month 228, for boys and for girls. The band [0.35, 0.65] "
        "was applied as registered. The share of total postnatal gain is stored and not used."
    )
    lines = []
    for sex, row in sexes.items():
        lines.append(
            f"{sex}: birth {row['length_at_birth_cm']:.2f} cm, age 5 {row['height_at_5_years_cm']:.2f} cm, "
            f"age 19 {row['height_at_19_years_cm']:.2f} cm, R {row['R_half_of_the_rest']:.3f}, "
            f"inside band {row['inside_band']}."
        )
    lines.append(f"Verdict {verdict}" + (f" ({reason})" if reason else "") + ".")
    result["results_summary"] = lines
    if sexes:
        unused = ", ".join(
            f"{sex} {row['R_half_of_total_postnatal_not_used']:.3f}" for sex, row in sexes.items()
        )
        note = (
            "The ratio that was not used for the verdict, gain by age five divided by all postnatal gain, "
            f"is {unused}. A reading on which the first five years are half of total growth would be scored "
            "against one half. The registered reading is gain by age five equals half the gain after age five, "
            "and that is the reading the verdict uses."
        )
        result.setdefault("caveats", [])
        if note not in result["caveats"]:
            result["caveats"].append(note)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "reason": reason, "sexes": measured["extra"]["sexes"]}, indent=2))


if __name__ == "__main__":
    main()
