#!/usr/bin/env python3
"""aristotle-ha08-29: crabs, crawfish and lobsters moult repeatedly.

Rules fixed in result.json before these workbooks were opened.
Dependencies: pandas, openpyxl.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test"}

SNOW_URL = "https://ndownloader.figshare.com/files/6504888"
CRAY_ZIP = "https://datadryad.org/api/v2/versions/353121/download"
LOBSTER_URL = "https://zenodo.org/api/records/6588031/files/ALMQ_2004_2015_27.5.csv/content"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(exist_ok=True)
    retrieved = None
    if not dest.exists() or dest.stat().st_size < 1000:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=180) as resp:
            dest.write_bytes(resp.read())
        retrieved = now_utc()
    raw = dest.read_bytes()
    mtime = dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc)
    return {
        "download_url": url,
        "retrieved_at": retrieved or mtime.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": sha256(raw),
    }


def ratio(lengths: pd.Series) -> float | None:
    positive = lengths[lengths > 0]
    if positive.empty:
        return None
    return float(positive.max() / positive.min())


def score_crab(path: Path) -> dict:
    xl = pd.ExcelFile(path)
    per_sheet = {}
    overall = 0
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet)
        instar = pd.to_numeric(df["Instar"], errors="coerce")
        per_sheet[sheet] = {
            "n_rows": int(instar.notna().sum()),
            "min_instar": None if instar.dropna().empty else int(instar.min()),
            "max_instar": None if instar.dropna().empty else int(instar.max()),
        }
        if per_sheet[sheet]["max_instar"] is not None:
            overall = max(overall, per_sheet[sheet]["max_instar"])
    if overall <= 0:
        status = "unmeasured"
    elif overall == 1:
        status = "fail"
    elif overall >= 3:
        status = "pass"
    else:
        status = "intermediate"
    return {"status": status, "max_instar": overall, "sheets": per_sheet}


def score_crayfish(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    length = pd.to_numeric(df["Carapace Length (mm)"], errors="coerce")
    hard = df["Carapace Hardness (EHS)"].astype(str)
    measured = length.dropna()
    measured = measured[measured > 0]
    median = float(measured.median())
    soft_mask = hard.str.contains(r"EHS\s*0", case=False, na=False)
    soft = length[soft_mask].dropna()
    soft = soft[soft > 0]
    n_soft = int(soft.shape[0])
    n_below = int((soft < median).sum())
    n_above = int((soft > median).sum())
    size_ratio = ratio(soft)
    if n_soft < 5:
        status = "underpowered"
    elif size_ratio is not None and size_ratio < 1.10 and n_soft >= 10:
        status = "fail"
    elif size_ratio is not None and size_ratio >= 1.5 and n_below >= 5 and n_above >= 5:
        status = "pass"
    elif size_ratio is not None and 1.10 <= size_ratio < 1.5:
        status = "intermediate"
    else:
        status = "intermediate"
    return {
        "status": status,
        "n_animals": int(measured.shape[0]),
        "median_carapace_mm": median,
        "n_soft": n_soft,
        "n_soft_below_median": n_below,
        "n_soft_above_median": n_above,
        "soft_min_mm": None if soft.empty else float(soft.min()),
        "soft_max_mm": None if soft.empty else float(soft.max()),
        "soft_max_over_min": size_ratio,
        "hardness_counts": hard.value_counts(dropna=False).to_dict(),
    }


def score_lobster(path: Path) -> dict:
    df = pd.read_csv(path)
    # Deviation, recorded in result.json: Shellhardness 1 is Soft in the data paper's code table.
    length = pd.to_numeric(df["Size"], errors="coerce")
    hardness = pd.to_numeric(df["Shellhardness"], errors="coerce")
    measured = length.dropna()
    measured = measured[measured > 0]
    median = float(measured.median())
    soft = length[hardness == 1].dropna()
    soft = soft[soft > 0]
    n_soft = int(soft.shape[0])
    n_below = int((soft < median).sum())
    n_above = int((soft > median).sum())
    size_ratio = ratio(soft)
    q01 = float(soft.quantile(0.01)) if n_soft else None
    q99 = float(soft.quantile(0.99)) if n_soft else None
    if n_soft < 30:
        status = "underpowered"
    elif size_ratio is not None and size_ratio < 1.10:
        status = "fail"
    elif size_ratio is not None and size_ratio >= 1.5 and n_below >= 5 and n_above >= 5:
        status = "pass"
    elif size_ratio is not None and 1.10 <= size_ratio < 1.5:
        status = "intermediate"
    else:
        status = "intermediate"
    return {
        "status": status,
        "n_animals": int(measured.shape[0]),
        "median_size_mm": median,
        "n_soft": n_soft,
        "n_soft_below_median": n_below,
        "n_soft_above_median": n_above,
        "soft_min_mm": None if soft.empty else float(soft.min()),
        "soft_max_mm": None if soft.empty else float(soft.max()),
        "soft_max_over_min": size_ratio,
        "soft_p01_mm": q01,
        "soft_p99_mm": q99,
        "soft_p01_p99_ratio": None if not q01 else float(q99 / q01),
        "shellhardness_counts": {str(k): int(v) for k, v in hardness.value_counts(dropna=False).to_dict().items()},
        "code": "Shellhardness == 1, the data paper's label for Soft",
    }


def decide(crab: str, cray: str, lobster: str) -> tuple[str, str | None]:
    statuses = (crab, cray, lobster)
    if any(s == "fail" for s in statuses):
        return "refutes", None
    if all(s == "pass" for s in statuses):
        return "supports", None
    if any(s == "underpowered" for s in statuses) and not any(s in ("unmeasured", "intermediate") for s in statuses):
        return "inconclusive", "underpowered"
    if all(s == "unmeasured" for s in statuses):
        return "inconclusive", "other"
    return "mixed", None


def confidence_for(verdict: str) -> float:
    if verdict == "supports":
        return 0.8
    if verdict == "refutes":
        return 0.7
    if verdict == "mixed":
        return 0.5
    return 0.35


def main() -> None:
    DERIVED.mkdir(exist_ok=True)
    snow_meta = fetch(SNOW_URL, DATA / "snow_crab.xlsx")
    cray_meta = fetch(CRAY_ZIP, DATA / "cambarus.zip")
    lobster_meta = fetch(LOBSTER_URL, DATA / "homarus.csv")
    with zipfile.ZipFile(DATA / "cambarus.zip") as zf:
        csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
        csv_bytes = zf.read(csv_name)
        readme_name = next(n for n in zf.namelist() if n.lower().endswith(".md"))
        readme_bytes = zf.read(readme_name)
    csv_path = DATA / Path(csv_name).name
    csv_path.write_bytes(csv_bytes)
    crab = score_crab(DATA / "snow_crab.xlsx")
    cray = score_crayfish(csv_path)
    lobster = score_lobster(DATA / "homarus.csv")
    verdict, reason = decide(crab["status"], cray["status"], lobster["status"])
    conf = confidence_for(verdict)

    summary = {
        "crab": {k: v for k, v in crab.items()},
        "crawfish": cray,
        "lobster": {k: v for k, v in lobster.items() if k != "shellhardness_counts"},
        "lobster_shellhardness_counts": lobster["shellhardness_counts"],
    }
    (DERIVED / "measured.json").write_text(json.dumps(summary, indent=2) + "\n")

    def r4(value):
        return None if value is None else round(float(value), 4)

    measured = {
        "value": crab["max_instar"],
        "unit": "maximum snow-crab instar index (a value of 3 or more means at least two molts)",
        "n": crab["sheets"][max(crab["sheets"], key=lambda s: crab["sheets"][s]["max_instar"] or 0)]["n_rows"],
        "uncertainty": None,
        "extra": {
            "crab_status": crab["status"],
            "crab_max_instar": crab["max_instar"],
            "crab_sheets": crab["sheets"],
            "crawfish_status": cray["status"],
            "crawfish_n_soft": cray["n_soft"],
            "crawfish_soft_max_over_min": r4(cray["soft_max_over_min"]),
            "crawfish_soft_mm": [cray["soft_min_mm"], cray["soft_max_mm"]],
            "crawfish_soft_below_above_median": [cray["n_soft_below_median"], cray["n_soft_above_median"]],
            "crawfish_median_mm": r4(cray["median_carapace_mm"]),
            "lobster_status": lobster["status"],
            "lobster_n_soft": lobster["n_soft"],
            "lobster_soft_max_over_min": r4(lobster["soft_max_over_min"]),
            "lobster_soft_mm": [lobster["soft_min_mm"], lobster["soft_max_mm"]],
            "lobster_soft_below_above_median": [lobster["n_soft_below_median"], lobster["n_soft_above_median"]],
            "lobster_median_mm": r4(lobster["median_size_mm"]),
            "lobster_soft_p01_p99_mm": [r4(lobster["soft_p01_mm"]), r4(lobster["soft_p99_mm"])],
            "lobster_soft_p01_p99_ratio": r4(lobster["soft_p01_p99_ratio"]),
        },
    }

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = conf
    result["measured"] = measured
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["deviations"] = [
        {
            "field": "lobster recently-molted code",
            "change": "Shellhardness equal to 1 is counted as soft.",
            "why": "The pre-registered rule matched the words soft, paper or EHS 0. This sheet stores hardness as integers. The data paper's own code table labels 1 as Soft, 2 as Medium and 3 as Hard. Moultstage_group 1 was not used: that code pools postmoult with intermoult.",
        }
    ]
    result["datasets"] = [
        {
            "id": "figshare-4037664-snow-crab-growth",
            "name": "Growth data of snow crab (Chionoecetes opilio)",
            "landing_url": "https://doi.org/10.6084/m9.figshare.4037664.v1",
            "doi": "10.6084/m9.figshare.4037664.v1",
            "version": "v1",
            "license": "CC BY 4.0",
            "files": [{
                "name": "snow_crab.xlsx",
                "download_url": SNOW_URL,
                "retrieved_at": snow_meta["retrieved_at"],
                "byte_size": snow_meta["byte_size"],
                "sha256": snow_meta["sha256"],
            }],
            "role": "carapace width of snow crab at successive instars",
        },
        {
            "id": "dryad-qjq2bvqqq-cambarus-sinking-creek",
            "name": "A survey of Cambarus crayfish and their symbiotic branchiobdellidans, Sinking Creek, Newport, VA, USA 2017-2018",
            "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.qjq2bvqqq",
            "doi": "10.5061/dryad.qjq2bvqqq",
            "version": "1",
            "license": "CC0 1.0",
            "files": [
                {
                    "name": "cambarus.zip",
                    "download_url": CRAY_ZIP,
                    "retrieved_at": cray_meta["retrieved_at"],
                    "byte_size": cray_meta["byte_size"],
                    "sha256": cray_meta["sha256"],
                },
                {
                    "name": Path(csv_name).name,
                    "download_url": CRAY_ZIP,
                    "retrieved_at": cray_meta["retrieved_at"],
                    "byte_size": len(csv_bytes),
                    "sha256": sha256(csv_bytes),
                },
                {
                    "name": Path(readme_name).name,
                    "download_url": CRAY_ZIP,
                    "retrieved_at": cray_meta["retrieved_at"],
                    "byte_size": len(readme_bytes),
                    "sha256": sha256(readme_bytes),
                },
            ],
            "role": "carapace length and carapace hardness of Cambarus appalachiensis; EHS 0/1 is the soft exoskeleton",
        },
        {
            "id": "zenodo-6588031-homarus-moult",
            "name": "Fisheries dataset on moulting patterns and shell quality of American lobsters Homarus americanus in Atlantic Canada",
            "landing_url": "https://doi.org/10.5281/zenodo.6588031",
            "doi": "10.5281/zenodo.6588031",
            "version": "1",
            "license": "CC BY 4.0",
            "files": [{
                "name": "ALMQ_2004_2015_27.5.csv",
                "download_url": LOBSTER_URL,
                "retrieved_at": lobster_meta["retrieved_at"],
                "byte_size": lobster_meta["byte_size"],
                "sha256": lobster_meta["sha256"],
            }],
            "role": "carapace size and shell hardness of Homarus americanus; hardness 1 is soft",
        },
    ]
    result["method"] = (
        "Downloaded the snow-crab workbook, the Cambarus Dryad zip and the Homarus Zenodo CSV. "
        "The crab clause uses the maximum Instar across sheets. The crawfish clause uses rows whose "
        "Carapace Hardness (EHS) matches EHS 0, compared with the median carapace length of every measured animal. "
        "The lobster clause uses Shellhardness 1, the code the data paper labels Soft, compared with the median of the Size column. "
        "The verdict is the pre-registered map of the three clause statuses."
    )
    result["results_summary"] = [
        f"Crab {crab['status']}: maximum instar {crab['max_instar']} (sheets: " +
        ", ".join(f"{k} max {v['max_instar']}" for k, v in crab["sheets"].items()) + ").",
        f"Crawfish {cray['status']}: {cray['n_soft']} soft animals, carapace {cray['soft_min_mm']}–{cray['soft_max_mm']} mm "
        f"(max/min {r4(cray['soft_max_over_min'])}), {cray['n_soft_below_median']} below and {cray['n_soft_above_median']} above the median {r4(cray['median_carapace_mm'])} mm.",
        f"Lobster {lobster['status']}: {lobster['n_soft']} soft-shelled animals, size {lobster['soft_min_mm']}–{lobster['soft_max_mm']} mm "
        f"(max/min {r4(lobster['soft_max_over_min'])}), {lobster['n_soft_below_median']} below and {lobster['n_soft_above_median']} above the median {r4(lobster['median_size_mm'])} mm. "
        f"The 1st to 99th percentiles are {r4(lobster['soft_p01_mm'])}–{r4(lobster['soft_p99_mm'])} mm (ratio {r4(lobster['soft_p01_p99_ratio'])}); that percentile ratio is descriptive and is not the verdict ratio.",
    ]
    caveat = (
        "Soft shells are a cross-section, not repeated observations of one animal. "
        "The snow-crab instars are a compiled growth schedule: each step is a molt the schedule says the animal passes through. "
        "Crawfish here is a freshwater Cambarus, which is what the English word names; Aristotle's marine crawfish is often read as a spiny lobster."
    )
    caveats = list(result.get("caveats") or [])
    if caveat not in caveats:
        caveats.append(caveat)
    result["caveats"] = caveats
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "confidence": conf,
        "crab": crab["status"],
        "max_instar": crab["max_instar"],
        "cray": cray["status"],
        "cray_ratio": r4(cray["soft_max_over_min"]),
        "cray_n": cray["n_soft"],
        "lobster": lobster["status"],
        "lobster_ratio": r4(lobster["soft_max_over_min"]),
        "lobster_n": lobster["n_soft"],
    }, indent=2))


if __name__ == "__main__":
    main()
