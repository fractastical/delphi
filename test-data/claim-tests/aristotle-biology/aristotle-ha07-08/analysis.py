#!/usr/bin/env python3
"""Test aristotle-ha07-08 against ONS live births by gestational week and sex."""

from __future__ import annotations

import hashlib
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
DERIVED = ROOT / "derived"
UA = "delphi-claim-test/aristotle-ha07-08 (research)"
WORKBOOKS = [
    (
        "ons-birth-characteristics-england-wales-2022",
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/datasets/birthcharacteristicsinenglandandwales/2022/birthcharacteristics2022.xlsx",
    ),
    (
        "ons-birth-characteristics-england-wales-2021",
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/datasets/birthcharacteristicsinenglandandwales/2021/correctionsbirthcharacteristics2021workbook6.xlsx",
    ),
    (
        "ons-birth-characteristics-england-wales-2020",
        "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/datasets/birthcharacteristicsinenglandandwales/2020/birthcharacteristics2020correction.xlsx",
    ),
]
FROZEN = [
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "claim_id",
    "claim_iri",
    "project",
    "agent",
]


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def finish(payload):
    data = json.loads(RESULT.read_text())
    snapshot = {k: data[k] for k in FROZEN}
    data.update(payload)
    for key, value in snapshot.items():
        if data[key] != value:
            raise SystemExit(f"frozen field changed: {key}")
    RESULT.write_text(json.dumps(data, indent=2) + "\n")


def cell(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def parse_week(label: str):
    s = label.strip().lower().replace("–", "-")
    s = re.sub(r"\.0$", "", s)
    s = s.replace("completed weeks", "weeks")
    match = re.match(r"^(\d{2})\s*(weeks?)?$", s)
    if match:
        week = int(match.group(1))
        if 17 <= week <= 47:
            return week, False
    match = re.match(r"^(\d{2})\s*(weeks?)?\s*(\+|and over|or more|or over|and above).*$", s)
    if match:
        week = int(match.group(1))
        if 17 <= week <= 47:
            return week, True
    return None


def sex_of(header: str):
    h = header.lower()
    if any(word in h for word in ("stillbirth", "death", "neonatal", "infant mortality")):
        return None
    if "female" in h and "male" not in h.replace("female", ""):
        return "female"
    if re.search(r"\bmales?\b", h) and "female" not in h:
        return "male"
    return None


def score_sheet(sheet_name: str, frame: pd.DataFrame):
    name = sheet_name.lower()
    if any(word in name for word in ("content", "note", "definition", "metadata")):
        return None
    values = frame.fillna("").astype(str)
    candidates = []
    limit = min(len(values), 80)
    width = min(values.shape[1], 40)
    for r in range(limit):
        headers = [cell(values.iat[r, c]) for c in range(width)]
        joined = " ".join(headers).lower()
        if "female" not in joined or not re.search(r"\bmales?\b", joined):
            continue
        # Pull a second header line above or below so "live births" can sit next to "male".
        extra = ""
        if r > 0:
            extra += " " + " ".join(cell(values.iat[r - 1, c]) for c in range(width))
        if r + 1 < len(values):
            extra += " " + " ".join(cell(values.iat[r + 1, c]) for c in range(width))
        sexes = []
        for c, header in enumerate(headers):
            combined = header + " " + extra
            kind = sex_of(combined)
            if kind:
                sexes.append((c, kind, header))
        if not any(kind == "male" for _, kind, _ in sexes) or not any(kind == "female" for _, kind, _ in sexes):
            continue
        week_rows = []
        for rr in range(r + 1, len(values)):
            label = cell(values.iat[rr, 0]) or cell(values.iat[rr, 1])
            parsed = parse_week(label)
            if parsed:
                week_rows.append((rr, label, parsed[0], parsed[1]))
        single = [row for row in week_rows if not row[3]]
        if len(single) < 8:
            continue
        live_bonus = 0
        blob = (sheet_name + " " + joined + " " + extra).lower()
        if "live birth" in blob or "livebirth" in blob:
            live_bonus += 5
        if "stillbirth" in blob or "death" in blob:
            live_bonus -= 8
        candidates.append(
            {
                "sheet": sheet_name,
                "header_row": r,
                "sexes": sexes,
                "week_rows": week_rows,
                "n_single": len(single),
                "score": len(single) + live_bonus,
                "blob": blob[:300],
            }
        )
    if not candidates:
        return None
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[0]


def counts_for(values, candidate):
    male_cols = [c for c, kind, _ in candidate["sexes"] if kind == "male"]
    female_cols = [c for c, kind, _ in candidate["sexes"] if kind == "female"]
    # If several male columns exist, keep those whose own header looks like a count of births
    # and drop overlapping breakdowns when one header contains "all" or "total" or "live".
    def prefer(cols, kind):
        headers = [(c, next(h for cc, k, h in candidate["sexes"] if cc == c)) for c in cols]
        live = [c for c, h in headers if "live" in h.lower()]
        total = [c for c, h in headers if re.search(r"(?i)\b(all|total)\b", h)]
        if live:
            return live
        if total:
            return total
        return cols

    male_cols = prefer(male_cols, "male")
    female_cols = prefer(female_cols, "female")

    def number(text):
        s = text.replace(",", "").replace(" ", "")
        if s in {"", "-", ".", "..", ":", "u", "z"}:
            return 0
        if not re.match(r"^-?\d+(\.\d+)?$", s):
            return None
        return float(s)

    rows = []
    for rr, label, week, open_ended in candidate["week_rows"]:
        def total(cols):
            acc = 0.0
            for c in cols:
                if c >= values.shape[1]:
                    return None
                val = number(cell(values.iat[rr, c]))
                if val is None:
                    return None
                acc += val
            return acc

        male = total(male_cols)
        female = total(female_cols)
        if male is None or female is None:
            continue
        rows.append({"label": label, "week": week, "open_ended": open_ended, "male": male, "female": female})
    return rows


def summarise(rows):
    single = [row for row in rows if not row["open_ended"]]
    def mean_and_n(key):
        n = sum(row[key] for row in single)
        if n <= 0:
            return None, 0, None
        mean = sum(row["week"] * row[key] for row in single) / n
        var = sum(row[key] * (row["week"] - mean) ** 2 for row in single) / n
        return mean, n, var ** 0.5

    male_mean, male_n, male_sd = mean_and_n("male")
    female_mean, female_n, female_sd = mean_and_n("female")

    def late(key):
        late_n = 0.0
        all_n = 0.0
        for row in rows:
            if row["open_ended"] and row["week"] < 40:
                continue
            if row["week"] >= 40 or (row["open_ended"] and row["week"] >= 40):
                late_n += row[key]
            if not row["open_ended"] or row["week"] >= 40:
                all_n += row[key]
        # Denominator: single weeks plus open bins at or above 40. Open bins below 40 are excluded
        # because they mix weeks on both sides of the cut.
        if all_n <= 0:
            return None
        return late_n / all_n

    return {
        "male_mean": male_mean,
        "female_mean": female_mean,
        "male_n": male_n,
        "female_n": female_n,
        "male_sd": male_sd,
        "female_sd": female_sd,
        "male_prop_ge40": late("male"),
        "female_prop_ge40": late("female"),
        "rows": rows,
    }


def sheet_signals(frame: pd.DataFrame):
    """Whether a sheet shows single-week labels, and whether it shows male and female labels."""
    values = frame.fillna("").astype(str)
    limit = min(len(values), 45)
    width = min(values.shape[1], 12)
    has_week = False
    has_male = False
    has_female = False
    for r in range(limit):
        for c in range(width):
            text = cell(values.iat[r, c])
            if not text:
                continue
            if "week" in text.lower() and parse_week(text):
                has_week = True
            if sex_of(text) == "male":
                has_male = True
            if sex_of(text) == "female":
                has_female = True
    return has_week, has_male and has_female


def main():
    DERIVED.mkdir(exist_ok=True)
    sess = requests.Session()
    sess.headers["User-Agent"] = UA
    failures = []
    retrieved_files = []
    scans = []
    for dataset_id, url in WORKBOOKS:
        try:
            response = sess.get(url, timeout=120)
            response.raise_for_status()
        except requests.RequestException as exc:
            failures.append(f"{dataset_id}: {exc}")
            continue
        content = response.content
        retrieved = now()
        file_record = {
            "dataset_id": dataset_id,
            "download_url": response.url,
            "retrieved_at": retrieved,
            "byte_size": len(content),
            "sha256": sha256(content),
        }
        retrieved_files.append(file_record)
        try:
            book = pd.read_excel(io.BytesIO(content), sheet_name=None, header=None, engine="openpyxl")
        except Exception as exc:
            failures.append(f"{dataset_id} parse: {exc}")
            continue
        best = None
        scan = []
        week_sheets = []
        sex_sheets = []
        for sheet, frame in book.items():
            lowered = sheet.lower()
            if any(word in lowered for word in ("content", "note", "cover", "definition")):
                continue
            has_week, has_sex = sheet_signals(frame)
            if has_week and not has_sex:
                week_sheets.append(sheet)
            if has_sex and not has_week:
                sex_sheets.append(sheet)
            candidate = score_sheet(sheet, frame)
            if candidate:
                scan.append({"sheet": sheet, "n_single": candidate["n_single"], "score": candidate["score"]})
                if best is None or candidate["score"] > best["score"]:
                    best = candidate
        scans.append(
            {
                "dataset": dataset_id,
                "byte_size": len(content),
                "sha256": file_record["sha256"],
                "candidates": scan,
                "sheets_with_single_weeks_and_no_sex": week_sheets,
                "sheets_with_sex_and_no_single_weeks": sex_sheets,
            }
        )
        (DERIVED / "scan.json").write_text(json.dumps(scans, indent=2) + "\n")
        if best is None:
            failures.append(f"{dataset_id}: no single-week sex table")
            continue
        values = book[best["sheet"]].fillna("").astype(str)
        summary = summarise(counts_for(values, best))
        if summary["male_mean"] is None or summary["female_n"] < 1:
            failures.append(f"{dataset_id}: counts unreadable in {best['sheet']}")
            continue

        male_mean = summary["male_mean"]
        female_mean = summary["female_mean"]
        male_prop = summary["male_prop_ge40"]
        female_prop = summary["female_prop_ge40"]
        male_n = summary["male_n"]
        female_n = summary["female_n"]
        if male_n < 10000 or female_n < 10000:
            verdict, reason = "inconclusive", "underpowered"
        elif female_mean > male_mean and female_prop > male_prop:
            verdict, reason = "supports", None
        elif female_mean < male_mean and female_prop < male_prop:
            verdict, reason = "refutes", None
        else:
            verdict, reason = "mixed", None

        if verdict in {"supports", "refutes"} and min(male_n, female_n) >= 100000:
            confidence = 0.82
        elif verdict in {"supports", "refutes"}:
            confidence = 0.74
        elif verdict == "mixed":
            confidence = 0.7
        else:
            confidence = 0.4

        table = pd.DataFrame(summary["rows"])
        table.to_csv(DERIVED / "weeks.csv", index=False)
        measured = {
            "value": female_mean - male_mean,
            "unit": "weeks, female mean completed week minus male mean",
            "n": int(male_n + female_n),
            "uncertainty": None,
            "extra": {
                "dataset_id": dataset_id,
                "sheet": best["sheet"],
                "male_mean_weeks": male_mean,
                "female_mean_weeks": female_mean,
                "male_sd_weeks": summary["male_sd"],
                "female_sd_weeks": summary["female_sd"],
                "male_n": male_n,
                "female_n": female_n,
                "male_proportion_ge_40_weeks": male_prop,
                "female_proportion_ge_40_weeks": female_prop,
                "proportion_difference_female_minus_male": (female_prop - male_prop) if female_prop is not None else None,
                "earlier_workbooks_skipped": failures,
                "rule_based_verdict": verdict,
            },
        }
        (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
        finish(
            {
                "status": "complete",
                "data_kind": "biological",
                "verdict": verdict,
                "confidence": confidence,
                **({"reason": reason} if reason else {}),
                "measured": measured,
                "datasets": [
                    {
                        "id": dataset_id,
                        "name": "ONS birth characteristics in England and Wales",
                        "landing_url": "https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/datasets/birthcharacteristicsinenglandandwales",
                        "doi": None,
                        "version": dataset_id[-4:],
                        "license": "Open Government Licence, if stated on the ONS download; the workbook itself was the file read",
                        "files": [
                            {
                                "download_url": response.url,
                                "retrieved_at": retrieved,
                                "byte_size": len(content),
                                "sha256": sha256(content),
                            }
                        ],
                        "role": "live births by completed gestational week and sex",
                    }
                ],
                "method": (
                    f"Downloaded the {dataset_id[-4:]} ONS birth-characteristics workbook and selected sheet {best['sheet']!r}, "
                    f"the candidate with the most single completed-week rows and separate male and female counts "
                    f"(score {best['score']}). Means are birth-weighted averages of those weeks. "
                    "The late proportion uses weeks 40 and above, including an open bin that starts at 40 or later."
                ),
                "caveats": [
                    "Completed week of birth is a proxy for time to delivery, not a direct clock of when each organ finishes.",
                    "Ten months is mapped to 40 completed weeks, the lunar-month term, before the table was read.",
                    "Births inside one week are all given that week number, so both sexes share the same rounding.",
                    "The workbook is England and Wales, not the ancient Mediterranean population Aristotle was describing.",
                    "Columns marked stillbirth, death or neonatal were excluded by the pre-registered rule.",
                ],
            }
        )
        print(json.dumps({"verdict": verdict, "sheet": best["sheet"], "diff": female_mean - male_mean, "female_n": female_n, "male_n": male_n}, indent=2))
        return

    caveats = [
        "No sex-by-single-week live-birth table was found, so no mean week and no proportion at 40 or more weeks were computed."
    ]
    for scan in scans:
        weeks = scan["sheets_with_single_weeks_and_no_sex"]
        sexes = scan["sheets_with_sex_and_no_single_weeks"]
        if weeks and sexes:
            caveats.append(
                f"{scan['dataset']}: single-week labels without a male and female pair on "
                + ", ".join(weeks[:8])
                + "; male and female labels without single-week rows on "
                + ", ".join(sexes[:8])
                + "."
            )
    if not retrieved_files:
        caveats.append("None of the three workbook URLs returned a file.")
    finish(
        {
            "status": "complete",
            "data_kind": "none",
            "verdict": "inconclusive",
            "reason": "data-unavailable" if not any("no single-week" in item for item in failures) else "not-operationalizable",
            "confidence": 0.35,
            "measured": {
                "value": None,
                "unit": "weeks, female mean completed week minus male mean",
                "n": 0,
                "uncertainty": None,
                "extra": {
                    "failures": failures,
                    "workbooks": [
                        {
                            "dataset_id": item["dataset_id"],
                            "byte_size": item["byte_size"],
                            "sha256": item["sha256"],
                        }
                        for item in retrieved_files
                    ],
                    "sheet_signals": [
                        {
                            "dataset": scan["dataset"],
                            "sheets_with_single_weeks_and_no_sex": scan["sheets_with_single_weeks_and_no_sex"],
                            "sheets_with_sex_and_no_single_weeks": scan["sheets_with_sex_and_no_single_weeks"],
                        }
                        for scan in scans
                    ],
                    "rule_based_verdict": "inconclusive",
                },
            },
            "datasets": [
                {
                    "id": item["dataset_id"],
                    "name": "ONS birth characteristics in England and Wales",
                    "landing_url": "https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/datasets/birthcharacteristicsinenglandandwales",
                    "doi": None,
                    "version": item["dataset_id"][-4:],
                    "license": "not parsed from the workbook",
                    "files": [
                        {
                            "download_url": item["download_url"],
                            "retrieved_at": item["retrieved_at"],
                            "byte_size": item["byte_size"],
                            "sha256": item["sha256"],
                        }
                    ],
                    "role": "searched for a live-birth table of single completed weeks by sex",
                }
                for item in retrieved_files
            ],
            "method": (
                f"Downloaded {len(retrieved_files)} of the three pre-registered ONS birth-characteristics workbooks "
                "and scanned each sheet for a header row with male and female live births and at least eight single-week rows. "
                "No sheet met that rule, so the sex difference was not calculated."
            ),
            "caveats": caveats,
        }
    )
    print(json.dumps(failures, indent=2))


if __name__ == "__main__":
    main()
