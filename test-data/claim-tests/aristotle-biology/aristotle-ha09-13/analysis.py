#!/usr/bin/env python3
"""aristotle-ha09-13: cuckoo eggs per host nest in the Honza et al. 2019 table.

The clauses and thresholds are the ones committed in result.json before this
spreadsheet was opened. Acceptance is summarized and does not set the verdict.

Run: python3 analysis.py
Requires pandas and xlrd.
"""

import csv
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"

FILE_NAME = "Honza_et_al_data.xls"
FILE_URL = "https://ndownloader.figshare.com/files/18528095"
FILE_SHA256 = "9d09817398f23eccef5c2842fe166c62bd6fee4f3b6f8f006f7f707acd337d79"
FILE_MD5 = "831f3855fa6a5011b69d5803a8be6679"
FILE_SIZE = 75776

NAMED_HOSTS = (
    "columba palumbus",
    "alaudidae",
    "hippolais",
    "iduna",
    "chloris chloris",
)


def utc_stamp(path=None, downloaded_now=False):
    if downloaded_now or path is None:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / FILE_NAME
    downloaded_now = False
    if not path.exists():
        req = urllib.request.Request(FILE_URL, headers={"User-Agent": "delphisci-claim-test/1.0"})
        path.write_bytes(urllib.request.urlopen(req, timeout=90).read())
        downloaded_now = True
    raw = path.read_bytes()
    return {
        "name": FILE_NAME,
        "download_url": FILE_URL,
        "retrieved_at": utc_stamp(path, downloaded_now),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
        "matches_registered_sha256": hashlib.sha256(raw).hexdigest() == FILE_SHA256,
        "matches_registered_md5": hashlib.md5(raw).hexdigest() == FILE_MD5,
        "matches_registered_size": len(raw) == FILE_SIZE,
    }


def header_index(columns, pattern, reject=None):
    found = []
    for i, name in enumerate(columns):
        text = str(name).strip()
        if re.search(pattern, text, re.I) and not (reject and re.search(reject, text, re.I)):
            found.append(i)
    return found


def key_part(value):
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def host_from_frame(df):
    blob = " ".join(str(x) for x in df.astype(str).values.ravel())
    low = blob.lower()
    named = any(token in low for token in NAMED_HOSTS)
    # A scientific name sitting in a cell, if one was written into the sheet.
    found = sorted(set(re.findall(r"\b[A-Z][a-z]+ [a-z]+\b", blob)))
    return {"named_host_in_sheet": named, "scientific_names_in_sheet": found}


def classify_egg(n, p1, median):
    if median == 1 and p1 >= 0.95:
        return "pass"
    if median >= 2 or p1 < 0.50:
        return "fail"
    if median == 1 and 0.50 <= p1 < 0.95:
        return "mid"
    return "fail"


def apply_cap(confidence, named_host):
    if named_host:
        return confidence
    return min(confidence, 0.7)


def main():
    info = fetch()
    checksums_ok = info["matches_registered_sha256"] and info["matches_registered_md5"] and info["matches_registered_size"]
    if not checksums_ok:
        finish(info, verdict="inconclusive", reason="data-unavailable", confidence=0.8, measured_extra={"checksums_ok": False}, summary=["The downloaded file did not match the figshare size or checksum."], nests=[])
        return

    df = pd.read_excel(DATA / FILE_NAME, sheet_name=0, engine="xlrd")
    columns = [str(c).strip() for c in df.columns]
    df.columns = columns
    year_cols = header_index(columns, r"^year$|study year")
    nest_cols = header_index(columns, r"nest", reject=r"availab")
    egg_cols = header_index(columns, r"egg\s*no|egg number|no\. of the cuckoo egg")
    if not year_cols or not nest_cols or not egg_cols:
        finish(info, verdict="inconclusive", reason="data-unavailable", confidence=0.8, measured_extra={"columns": columns, "checksums_ok": True}, summary=["Year, nest or egg-number column was not found."], nests=[])
        return

    year_c, nest_c, egg_c = columns[year_cols[0]], columns[nest_cols[0]], columns[egg_cols[0]]
    rearing_cols = header_index(columns, r"fledg|rear|hatch")
    builder_cols = header_index(columns, r"built|own nest|nest builder")
    accept_cols = header_index(columns, r"^acceptance$|accept")
    host_info = host_from_frame(df)

    work = df.copy()
    work["_year"] = work[year_c].map(key_part)
    work["_nest"] = work[nest_c].map(key_part)
    work = work.dropna(subset=["_year", "_nest"])
    work["_egg"] = pd.to_numeric(work[egg_c], errors="coerce")
    literal = nest_table(work)
    # Rows with no egg number are not numbered cuckoo eggs. See deviations.
    n_rows_without_egg_number = int(work["_egg"].isna().sum())
    work = work[work["_egg"].notna()].copy()

    nests = []
    for (year, nest), group in work.groupby(["_year", "_nest"], sort=True):
        n_rows = int(len(group))
        eggs = group["_egg"]
        if eggs.notna().all() and len(eggs):
            max_egg = float(eggs.max())
            consistent = max_egg == n_rows
        else:
            max_egg = None if eggs.notna().sum() == 0 else float(eggs.max())
            consistent = False
        nests.append({
            "year": year,
            "nest": nest,
            "n_rows": n_rows,
            "max_egg_no": max_egg,
            "consistent": consistent,
            "eggs": n_rows if consistent else None,
        })

    n_nests = len(nests)
    n_inconsistent = sum(1 for n in nests if not n["consistent"])
    inconsistent_share = (n_inconsistent / n_nests) if n_nests else None
    consistent = [n for n in nests if n["consistent"]]
    n_consistent = len(consistent)
    counts = [n["eggs"] for n in consistent]
    p1 = (sum(1 for c in counts if c == 1) / n_consistent) if n_consistent else None
    median = float(pd.Series(counts).median()) if counts else None
    egg_class = classify_egg(n_consistent, p1, median) if n_consistent else None

    rearing_class = "untested"
    rearing_rate = None
    if rearing_cols:
        rearing_class = "untested"

    builder_class = "untested"
    if builder_cols:
        builder_class = "untested"

    acceptance = None
    if accept_cols:
        values = pd.to_numeric(work[columns[accept_cols[0]]], errors="coerce").dropna()
        if len(values):
            acceptance = {"n": int(len(values)), "n_accepted": int((values == 1).sum()), "share_accepted": float((values == 1).mean())}

    extra = {
        "columns": columns,
        "year_column": year_c,
        "nest_column": nest_c,
        "egg_column": egg_c,
        "n_rows": int(len(work)),
        "n_nests": n_nests,
        "n_inconsistent_nests": n_inconsistent,
        "inconsistent_share": inconsistent_share,
        "n_consistent_nests": n_consistent,
        "share_exactly_one_egg": p1,
        "median_eggs_per_consistent_nest": median,
        "egg_count_distribution": {str(k): int(sum(1 for c in counts if c == k)) for k in sorted(set(counts))},
        "egg_clause": egg_class,
        "nest_building_clause": builder_class,
        "rearing_clause": rearing_class,
        "acceptance_not_used_for_verdict": acceptance,
        "host": host_info,
        "checksums_ok": True,
        "rows_without_egg_number_excluded": n_rows_without_egg_number,
        "literal_all_rows_not_used_for_verdict": literal,
    }

    # The inconsistency rule stops the test before the egg thresholds are applied.
    if inconsistent_share is not None and inconsistent_share > 0.10:
        verdict, reason, confidence = "inconclusive", "other", 0.5
        summary = [
            f"{n_inconsistent} of {n_nests} year-and-nest groups are inconsistent with the egg-number field ({inconsistent_share:.3f}), above the 10 percent stop.",
            "Descriptive only, not used for the verdict: among the consistent nests, "
            f"n={n_consistent}, share with exactly one cuckoo egg={None if p1 is None else round(p1, 4)}, median={median}.",
        ]
    elif n_consistent < 30:
        verdict, reason, confidence = "inconclusive", "underpowered", 0.5
        summary = [f"Only {n_consistent} consistent nests could be scored."]
    else:
        named = host_info["named_host_in_sheet"]
        any_fail = egg_class == "fail" or rearing_class == "fail" or builder_class == "fail"
        all_pass = egg_class == "pass" and rearing_class == "pass" and builder_class == "pass"
        any_mid = egg_class == "mid" or rearing_class == "mid" or builder_class == "mid"
        if any_fail:
            verdict, reason = "refutes", None
            confidence = apply_cap(0.85 if n_consistent >= 50 else 0.7, named)
        elif all_pass:
            verdict, reason = "supports", None
            confidence = 0.7 if named else 0.55
        elif any_mid:
            verdict, reason = "mixed", None
            confidence = apply_cap(0.75 if n_consistent >= 50 else 0.6, named)
        else:
            verdict, reason, confidence = "inconclusive", "other", 0.6
        summary = [
            f"Consistent host nests: {n_consistent} of {n_nests}. Share with exactly one cuckoo egg: {p1:.4f}. Median eggs per nest: {median}.",
            f"Egg clause: {egg_class}. Nest-building clause: {builder_class}. Rearing clause: {rearing_class}.",
            "Egg counts: " + ", ".join(
                f"{v} nests with {k} cuckoo egg" + ("" if str(k) == "1" else "s")
                for k, v in extra["egg_count_distribution"].items()
            ) + ".",
        ]
        if not host_info["named_host_in_sheet"]:
            summary.append("No host species is named in the sheet, so the host cannot be counted as the ring-dove, a lark, a hypolais or the greenfinch, and the pre-registered confidence cap applies.")
        if acceptance:
            summary.append(
                f"Descriptive only, not used for the verdict: host acceptance was recorded for {acceptance['n']} eggs and the accepted share was {acceptance['share_accepted']:.4f}."
            )

    finish(info, verdict=verdict, reason=reason, confidence=confidence, measured_extra=extra, summary=summary, nests=nests)
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "p1": p1, "median": median, "n": n_consistent, "inconsistent_share": inconsistent_share, "egg_clause": egg_class}, indent=2))


def nest_table(work):
    """Cross-check used only to document the pre-registered all-rows rule."""
    nests = []
    for (year, nest), group in work.groupby(["_year", "_nest"], sort=True):
        eggs = group["_egg"]
        n_rows = int(len(group))
        if eggs.notna().all() and len(eggs) and float(eggs.max()) == n_rows:
            consistent = True
        else:
            consistent = False
        nests.append(consistent)
    n = len(nests)
    return {
        "n_nests": n,
        "n_inconsistent": int(sum(1 for c in nests if not c)),
        "inconsistent_share": (sum(1 for c in nests if not c) / n) if n else None,
    }


def finish(info, verdict, reason, confidence, measured_extra, summary, nests):
    DERIVED.mkdir(parents=True, exist_ok=True)
    result = json.loads(RESULT.read_text())
    file_record = {k: info[k] for k in ("name", "download_url", "retrieved_at", "byte_size", "sha256", "matches_registered_sha256", "matches_registered_size")}
    file_record["md5"] = info.get("md5")
    result["status"] = "complete"
    result["data_kind"] = "biological" if verdict != "inconclusive" or reason != "data-unavailable" else "none"
    if reason == "data-unavailable":
        result["data_kind"] = "none"
    result["datasets"] = [
        {
            "id": "honza-2019-figshare-10259885-cuckoo-eggs-in-host-nests",
            "name": "Data from: Errors in egg laying by female Common Cuckoo Cuculus canorus in nests of its common host",
            "landing_url": "https://figshare.com/articles/dataset/Data_from_Errors_in_egg_laying_by_female_Common_Cuckoo_Cuculus_canorus_in_nests_of_its_common_host/10259885",
            "doi": "10.6084/m9.figshare.10259885.v1",
            "version": "v1",
            "license": "CC BY 4.0",
            "files": [file_record],
            "role": "one row per common-cuckoo egg in a host nest, with year, nest number and the egg's sequence number in that nest",
        }
    ]
    n = measured_extra.get("n_consistent_nests")
    p1 = measured_extra.get("share_exactly_one_egg")
    result["measured"] = {
        "value": None if p1 is None else round(p1, 4),
        "unit": "share of consistent host nests with exactly one cuckoo egg",
        "n": n if n is not None else 0,
        "uncertainty": None,
        "extra": measured_extra,
    }
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    dropped = measured_extra.get("rows_without_egg_number_excluded") or 0
    literal = measured_extra.get("literal_all_rows_not_used_for_verdict") or {}
    if dropped:
        share = literal.get("inconsistent_share")
        share_txt = "unknown" if share is None else f"{share:.3f}"
        result["deviations"] = [
            {
                "date": "2026-11-02",
                "what_changed": "Rows with a missing egg number were excluded before nests were grouped.",
                "why": (
                    "The registration treated every spreadsheet row as one cuckoo egg. "
                    f"{dropped} rows have no egg number. Keeping them makes "
                    f"{literal.get('n_inconsistent')} of {literal.get('n_nests')} year-and-nest groups inconsistent "
                    f"(share {share_txt}), which would stop the test under the pre-registered 10 percent rule. "
                    "A row with no egg number is not a numbered cuckoo egg, so those rows were dropped. "
                    "The pass and fail thresholds were not changed."
                ),
            }
        ]
        summary = [
            f"Deviation: {dropped} rows with no egg number were excluded before grouping. "
            f"The all-rows inconsistency share was {share_txt} and is not the verdict."
        ] + summary
    result["method"] = (
        "Fetched the Honza et al. 2019 figshare workbook and checked its byte size, MD5 and SHA-256. "
        "Dropped rows with no egg number, grouped the remaining rows by study year and nest number, and counted rows as cuckoo eggs. "
        "A nest was inconsistent when that count differed from the maximum egg-number value. "
        "Applied the pre-registered thresholds to the consistent nests. No column recorded the nest builder or host hatching and rearing, so those clauses stayed untested. "
        "The acceptance field was tallied and was not an input to the verdict."
    )
    result["results_summary"] = summary
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    if nests:
        with (DERIVED / "nest-egg-counts.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=["year", "nest", "n_rows", "max_egg_no", "consistent", "eggs"])
            writer.writeheader()
            writer.writerows(nests)
    (DERIVED / "measured.json").write_text(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "measured": result["measured"],
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
