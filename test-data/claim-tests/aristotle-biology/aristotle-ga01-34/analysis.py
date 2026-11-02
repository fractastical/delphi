#!/usr/bin/env python3
"""aristotle-ga01-34: only fish eggs the milt reaches are fertilized.

Rules fixed in result.json before the numeric tables were opened.
Dependencies: pandas, openpyxl.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test"}

PACKAGES = [
    {
        "id": "dryad-crjdfn38v-zebrafish-fertilization",
        "name": "Female reproductive fluids attract more and better sperm in zebrafish",
        "doi": "10.5061/dryad.crjdfn38v",
        "version_id": "241008",
        "species": "Danio rerio",
        "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.crjdfn38v",
    },
    {
        "id": "dryad-6djh9w10z-round-goby",
        "name": "Sperm performance limits the reproduction of an invasive fish in novel salinities",
        "doi": "10.5061/dryad.6djh9w10z",
        "version_id": "106291",
        "species": "Neogobius melanostomus",
        "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.6djh9w10z",
    },
    {
        "id": "dryad-v933m-salmon-trout-fertilization",
        "name": "Cryptic choice of conspecific sperm controlled by ovarian fluid in salmon and trout",
        "doi": "10.5061/dryad.v933m",
        "version_id": "8842",
        "species": "Salmo salar / Salmo trutta",
        "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.v933m",
    },
]

NO_MILT_PHRASES = (
    "no sperm",
    "no milt",
    "without sperm",
    "without milt",
    "unexposed",
    "sperm-free",
    "sperm free",
    "zero sperm",
    "0 sperm",
    "seawater only",
    "water only",
    "unfertilized control",
    "no male",
    "males absent",
    "milt absent",
)
SPERM_AMOUNT = re.compile(
    r"(sperm|milt).*(conc|count|volume|number|dose|amount|density|cells|ul\b)|^(sperm|milt)$",
    re.I,
)
FERT_COL = re.compile(r"fert|embryo|hatch", re.I)
FROZEN = (
    "claim_id",
    "claim_iri",
    "project",
    "created",
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "agent",
)


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def fetch(url: str, dest: Path) -> dict:
    DATA.mkdir(exist_ok=True)
    retrieved = None
    if not dest.exists() or dest.stat().st_size < 100:
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


def license_for(doi: str) -> str | None:
    url = "https://datadryad.org/api/v2/datasets/doi%3A" + doi.replace("/", "%2F")
    req = urllib.request.Request(url, headers={**UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        payload = json.load(resp)
    raw = payload.get("license") or ""
    if "CC0" in raw:
        return "CC0 1.0"
    return raw or None


def read_csv_bytes(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8", errors="replace")
    first = text.splitlines()[0] if text.splitlines() else ""
    sep = ";" if first.count(";") > first.count(",") else ","
    return pd.read_csv(io.BytesIO(raw), sep=sep)


def read_table(raw: bytes, name: str) -> list[tuple[str, pd.DataFrame]]:
    lower = name.lower()
    if lower.endswith((".md", ".rtf", ".pdf", ".nex")):
        return []
    if lower.endswith(".csv"):
        return [(name, read_csv_bytes(raw))]
    if lower.endswith(".txt"):
        return [(name, pd.read_csv(io.BytesIO(raw), sep=None, engine="python"))]
    if lower.endswith(".xlsx"):
        book = pd.ExcelFile(io.BytesIO(raw))
        return [(f"{name}#{sheet}", pd.read_excel(book, sheet)) for sheet in book.sheet_names]
    return []


def cell_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip().lower()


def find_no_milt(df: pd.DataFrame) -> dict:
    reasons = []
    mask = pd.Series(False, index=df.index)
    amount_cols = [c for c in df.columns if SPERM_AMOUNT.search(str(c))]
    for col in amount_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        hit = numeric.eq(0)
        if hit.any():
            mask = mask | hit.fillna(False)
            reasons.append(f"numeric zero in {col}")
    for col in df.columns:
        texts = df[col].map(cell_text)
        hit = pd.Series(False, index=df.index)
        for phrase in NO_MILT_PHRASES:
            hit = hit | texts.str.contains(re.escape(phrase), na=False)
        if hit.any():
            mask = mask | hit
            reasons.append(f"label in {col}")
    fert_cols = [str(c) for c in df.columns if FERT_COL.search(str(c))]
    labels = {}
    for col in df.columns:
        if re.search(r"treat|group|label|type", str(col), re.I):
            values = sorted({cell_text(v) for v in df[col].tolist() if cell_text(v)})
            if 0 < len(values) <= 12:
                labels[str(col)] = values
    return {
        "n_rows": int(df.shape[0]),
        "columns": [str(c) for c in df.columns],
        "sperm_amount_columns": [str(c) for c in amount_cols],
        "fertilization_columns": fert_cols,
        "n_no_milt_rows": int(mask.sum()),
        "reasons": reasons,
        "labels": labels,
        "scoreable": bool(reasons) and bool(fert_cols),
    }


def scan_zip(path: Path) -> list[dict]:
    reports = []
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            raw = archive.read(info)
            for label, frame in read_table(raw, info.filename):
                found = find_no_milt(frame)
                found["table"] = label
                reports.append(found)
    return reports


def main() -> None:
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    frozen = {key: result[key] for key in FROZEN}
    analysis_caveats = [
        "No planned table contained a no-milt arm together with a fertilization column. Fertilization rates from rows that were all exposed to sperm were not turned into a verdict.",
        "Salmon and trout are oviparous external fertilizers, as are the zebrafish and the round goby. Tables for other animal groups were not in these packages.",
    ]
    original_caveats = [c for c in result.get("caveats", []) if c not in analysis_caveats]

    datasets = []
    scans = []
    download_failed = False
    for package in PACKAGES:
        url = f"https://datadryad.org/api/v2/versions/{package['version_id']}/download"
        dest = DATA / f"{package['version_id']}.zip"
        try:
            meta = fetch(url, dest)
            tables = scan_zip(dest)
            failed = False
        except Exception as exc:  # noqa: BLE001 — record the retrieval failure, do not invent a table
            meta = {"download_url": url, "retrieved_at": now_utc(), "byte_size": None, "sha256": None, "error": str(exc)}
            tables = []
            failed = True
            download_failed = True
        scoreable = [t for t in tables if t["scoreable"]]
        scans.append(
            {
                "id": package["id"],
                "species": package["species"],
                "download_failed": failed,
                "n_tables": len(tables),
                "n_scoreable_no_milt_tables": len(scoreable),
                "tables": [
                    {
                        "table": t["table"],
                        "n_rows": t["n_rows"],
                        "columns": t["columns"],
                        "sperm_amount_columns": t["sperm_amount_columns"],
                        "fertilization_columns": t["fertilization_columns"],
                        "n_no_milt_rows": t["n_no_milt_rows"],
                        "reasons": t["reasons"],
                        "labels": t["labels"],
                        "scoreable": t["scoreable"],
                    }
                    for t in tables
                ],
            }
        )
        try:
            license_name = license_for(package["doi"])
        except Exception:  # noqa: BLE001
            license_name = None
        datasets.append(
            {
                "id": package["id"],
                "name": package["name"],
                "landing_url": package["landing_url"],
                "doi": package["doi"],
                "version": package["version_id"],
                "license": license_name,
                "files": [{"name": dest.name, **{k: meta[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256") if k in meta}}],
                "role": f"candidate fertilization table for {package['species']}; scored only if a no-milt arm is present",
            }
        )

    n_scoreable = sum(item["n_scoreable_no_milt_tables"] for item in scans)
    n_no_milt_rows = sum(t["n_no_milt_rows"] for item in scans for t in item["tables"])
    n_packages = len(PACKAGES)
    if n_scoreable != 0:
        raise SystemExit(
            "A scoreable no-milt arm is present. Compute its fertilization proportion "
            "with the pre-registered 0.05 and 0.20 thresholds before writing a verdict."
        )
    verdict = "inconclusive"
    reason = "data-unavailable"
    confidence = 0.62
    zebra = next(item for item in scans if item["id"].startswith("dryad-crjdfn38v"))
    zebra_labels = {}
    for table in zebra["tables"]:
        if table["table"].endswith("fertilization.csv"):
            zebra_labels = table["labels"]
    summary = (
        f"None of the {n_packages} planned fish packages has a no-milt arm. "
        f"Tables were scanned for the pre-registered labels and for a sperm or milt amount of 0; "
        f"{n_no_milt_rows} rows matched. Fertilization rates from sperm-exposed rows were not scored. "
        f"Zebrafish fertilization labels: {zebra_labels}. "
        "The word control is not in the no-milt list, and the package README describes both of those labels as sperm subpopulations."
    )
    measured = {
        "value": int(n_scoreable),
        "unit": "planned packages with a scoreable no-milt arm",
        "n": int(n_packages),
        "uncertainty": None,
        "extra": {"n_no_milt_rows": int(n_no_milt_rows), "scans": scans},
    }

    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    result.update(
        {
            "status": "complete",
            "data_kind": "none" if reason == "data-unavailable" else "biological",
            "verdict": verdict,
            "reason": reason,
            "confidence": confidence,
            "measured": measured,
            "datasets": datasets,
            "method": (
                "Downloaded the three Dryad version zips named in the pre-registration. "
                "Every table was scanned for a numeric sperm or milt amount of 0, or for a treatment label in the pre-registered list, "
                "and for a fertilization column. "
                "A package counts only when both are in the same table. "
                "No fertilization rate from a sperm-exposed row was used as a verdict."
            ),
            "results_summary": [summary],
            "caveats": original_caveats + analysis_caveats,
            "deviations": [
                {
                    "field": "scoreable no-milt arm",
                    "change": "A numeric zero or a matching label counts only when that same table also has a fertilization column.",
                    "why": "The pass rule needs a fertilization proportion. A sperm-trait row with a count of 0 and no egg score is not an arm of eggs the milt did not reach. This does not change the 0.05, 0.20, or 0.50 thresholds.",
                }
            ],
        }
    )
    if download_failed and n_scoreable == 0:
        result["reason"] = "data-unavailable"
    for key, value in frozen.items():
        result[key] = value
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": result["verdict"], "reason": result.get("reason"), "summary": summary, "n_scoreable": n_scoreable}, indent=2))


if __name__ == "__main__":
    main()
