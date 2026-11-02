#!/usr/bin/env python3
"""aristotle-ha06-12: common cuckoo lays in the nests of smaller birds.

Pre-registered rules are in result.json (committed before these files were read).
This script downloads the three planned datasets, scores clauses A–E, writes
derived/measured.json and derived/hosts.csv, and fills the result fields that
are not the pre-registered criteria.

Dependencies: pandas, openpyxl, pypdf.
  pip install pandas openpyxl pypdf
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
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = {"User-Agent": "delphisci-claim-test"}

STOKKE_ZIP = "https://datadryad.org/api/v2/versions/6072/download"
LOWTHER_PDF = "https://www.datocms-assets.com/44232/1749565809-host-list-ow-cuckoos-05jun2025.pdf"
AVONET_XLSX = "https://ndownloader.figshare.com/files/34480856"

PARASITE_GENERA = (
    "Clamator",
    "Pachycoccyx",
    "Cuculus",
    "Cercococcyx",
    "Cacomantis",
    "Chrysococcyx",
    "Surniculus",
    "Hierococcyx",
    "Eudynamys",
    "Scythrops",
)
BINOMIAL = re.compile(r"\b([A-Z][a-z]+)\s+([a-z]{3,})\b")
YEAR = re.compile(r"\b(1[7-9]\d{2}|20[0-2]\d)\b")
OTHER_PARASITE = re.compile(
    r"\b(" + "|".join(PARASITE_GENERA) + r")\s+([a-z]{3,})\b"
)


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


def binomial(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace("_", " ")
    text = re.sub(r"\(.*?\)", "", text)
    match = BINOMIAL.search(text)
    if not match:
        return None
    return f"{match.group(1)} {match.group(2)}"


def positive_hosts(df: pd.DataFrame, sci_col: str, count_col: str, source: str) -> tuple[set[str], int, int]:
    """Return (host binomials with count>0, n positive rows, n rows naming Cuculus canorus)."""
    hosts: set[str] = set()
    self_rows = 0
    positive_rows = 0
    for _, row in df.iterrows():
        name = binomial(row.get(sci_col))
        if name == "Cuculus canorus":
            self_rows += 1
        count = row.get(count_col)
        try:
            count_f = float(count)
        except (TypeError, ValueError):
            continue
        if pd.isna(count_f) or count_f <= 0:
            continue
        positive_rows += 1
        if name and name != "Cuculus canorus":
            hosts.add(name)
    return hosts, positive_rows, self_rows


def load_stokke(zip_path: Path) -> dict:
    raw = zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        members = {}
        for info in zf.infolist():
            blob = zf.read(info)
            members[Path(info.filename).name] = {
                "bytes": blob,
                "byte_size": len(blob),
                "sha256": sha256(blob),
            }
    tables = {
        "ESM1": pd.read_excel(io.BytesIO(members["Stokke_data_parasitism_rates_Dryad_ESM1.xlsx"]["bytes"])),
        "ESM2": pd.read_excel(io.BytesIO(members["Stokke_data_passerines_Dryad_ESM2.xlsx"]["bytes"])),
        "ESM3": pd.read_excel(io.BytesIO(members["Stokke_data_parasitism_UK_Dryad_ESM3.xlsx"]["bytes"])),
        "ESM4": pd.read_excel(io.BytesIO(members["Stokke_data_parasitism_Germany_Dryad_ESM4.xlsx"]["bytes"])),
    }
    return {"members": members, "tables": tables}


def score_laying(tables: dict) -> dict:
    specs = [
        ("ESM1", "Scientific.name", "par_nests"),
        ("ESM3", "Latin", "parasitism cases"),
        ("ESM4", "Latin", "parasitism cases"),
    ]
    hosts: set[str] = set()
    self_rows = 0
    positive_rows = {}
    per_source = {}
    for key, sci, count in specs:
        found, n_pos, n_self = positive_hosts(tables[key], sci, count, key)
        hosts |= found
        self_rows += n_self
        positive_rows[key] = n_pos
        per_source[key] = sorted(found)
    n = len(hosts)
    if self_rows >= 5 or n < 5:
        status = "fail"
    elif n >= 30:
        status = "pass"
    else:
        status = "underpowered"
    # Clause C and D: no per-nest egg count and no laying-behaviour column.
    columns = {key: list(tables[key].columns.astype(str)) for key in ("ESM1", "ESM3", "ESM4")}
    return {
        "status": status,
        "n_host_species": n,
        "self_host_rows": self_rows,
        "positive_rows": positive_rows,
        "hosts": sorted(hosts),
        "columns": columns,
        "clause_C": "unmeasured",
        "clause_D": "unmeasured",
        "clause_C_reason": "par_nests and parasitism cases count parasitized nests or cases, not cuckoo eggs inside one nest",
        "clause_D_reason": "no column records whether the laying female removed or ate a host egg",
    }


def avonet_masses(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="AVONET1_BirdLife", usecols=["Species1", "Mass", "Mass.Source", "Inference"])
    df["binomial"] = df["Species1"].map(binomial)
    df["Mass"] = pd.to_numeric(df["Mass"], errors="coerce")
    return df.dropna(subset=["binomial"]).drop_duplicates("binomial", keep="first")


def score_size(hosts: list[str], masses: pd.DataFrame, tables: dict) -> dict:
    cuckoo_rows = masses[masses["binomial"] == "Cuculus canorus"]
    if cuckoo_rows.empty or not (cuckoo_rows.iloc[0]["Mass"] > 0):
        return {"status": "unmeasured", "reason": "Cuculus canorus has no positive AVONET mass"}
    cuckoo_mass = float(cuckoo_rows.iloc[0]["Mass"])
    cuckoo_source = str(cuckoo_rows.iloc[0]["Mass.Source"])
    cuckoo_inference = str(cuckoo_rows.iloc[0]["Inference"])
    indexed = masses.set_index("binomial")["Mass"]
    rows = []
    for host in hosts:
        mass = indexed.get(host)
        mass_f = None if mass is None or (isinstance(mass, float) and pd.isna(mass)) else float(mass)
        lighter = None if mass_f is None or mass_f <= 0 else bool(mass_f < cuckoo_mass)
        rows.append({"host": host, "mass_g": mass_f, "lighter": lighter})
    scored = [r for r in rows if r["lighter"] is not None]
    n = len(scored)
    n_lighter = sum(1 for r in scored if r["lighter"])
    fraction = (n_lighter / n) if n else None
    if n < 20:
        status = "underpowered"
    elif fraction is not None and fraction >= 0.80:
        status = "pass"
    elif fraction is not None and fraction < 0.50:
        status = "fail"
    else:
        status = "intermediate"
    # Descriptive only: Stokke's own column is named "body size", not mass, so it is not the verdict mass.
    stokke_size = {}
    for key, sci, size_col in (
        ("ESM1", "Scientific.name", "body size"),
        ("ESM3", "Latin", "body size"),
        ("ESM4", "Latin", "body_size"),
    ):
        for _, row in tables[key].iterrows():
            name = binomial(row.get(sci))
            if name not in set(hosts):
                continue
            try:
                value = float(row.get(size_col))
            except (TypeError, ValueError):
                continue
            if pd.isna(value) or value <= 0:
                continue
            stokke_size[name] = value
    stokke_scored = {h: v for h, v in stokke_size.items() if h in {r["host"] for r in scored}}
    stokke_lighter = sum(1 for v in stokke_scored.values() if v < cuckoo_mass)
    return {
        "status": status,
        "cuckoo_mass_g": cuckoo_mass,
        "cuckoo_mass_source": cuckoo_source,
        "cuckoo_mass_inference": cuckoo_inference,
        "n_hosts_with_mass": n,
        "n_lighter": n_lighter,
        "fraction_lighter": fraction,
        "n_unmatched": len(hosts) - n,
        "rows": rows,
        "stokke_body_size_check_not_used_for_verdict": {
            "n": len(stokke_scored),
            "n_lighter_than_avonet_cuckoo": stokke_lighter,
            "fraction_lighter": (stokke_lighter / len(stokke_scored)) if stokke_scored else None,
            "note": "Stokke labels this column body size, not mass. The verdict uses AVONET Mass.",
        },
    }


def lowther_account(pdf_path: Path) -> dict:
    reader = PdfReader(str(pdf_path))
    lines: list[str] = []
    for page in reader.pages:
        lines.extend((page.extract_text() or "").splitlines())
    text = "\n".join(lines)
    marks_survive = ("&" in text) or ("%" in text)
    start = None
    for i, line in enumerate(lines):
        if "Cuculus canorus" in line and "," in line and YEAR.search(line) and BINOMIAL.search(line):
            match = BINOMIAL.search(line)
            # heading, not a subspecies mention buried in a sentence: the binomial is Cuculus canorus
            # and a common-name comma precedes it
            if match and f"{match.group(1)} {match.group(2)}" == "Cuculus canorus":
                start = i
                break
    if start is None:
        return {"status": "unmeasured", "reason": "no Cuculus canorus heading line", "marks_survive": marks_survive}
    end = len(lines)
    for i in range(start + 1, len(lines)):
        match = OTHER_PARASITE.search(lines[i])
        if not match or not YEAR.search(lines[i]):
            continue
        if match.group(1) == "Cuculus" and match.group(2) == "canorus":
            continue
        end = i
        break
    section = lines[start:end]
    reared = []
    hippolais = []
    for line in section:
        stripped = line.strip()
        if "Hippolais" in stripped or "hypolais" in stripped.lower():
            hippolais.append(stripped)
        if not (stripped.startswith("&") or stripped.startswith("%")):
            continue
        match = None
        for candidate in BINOMIAL.finditer(stripped):
            match = candidate  # scientific name follows the common name; keep the last binomial
        if not match:
            continue
        name = f"{match.group(1)} {match.group(2)}"
        if name == "Cuculus canorus":
            continue
        reared.append({"binomial": name, "line": stripped})
    # distinct
    seen = []
    used = set()
    for item in reared:
        if item["binomial"] in used:
            continue
        used.add(item["binomial"])
        seen.append(item)
    if not marks_survive:
        status = "unmeasured"
        reason = "rearing-mark characters did not survive text extraction"
    elif len(seen) >= 10:
        status = "pass"
        reason = None
    elif len(seen) == 0:
        status = "fail"
        reason = "account found and zero hosts carry a rearing prefix"
    else:
        # 1 to 9 is neither the pass threshold nor the fail threshold.
        # The pre-registered fail is zero. Fewer than 10 does not pass.
        # Treat 1–9 as unmeasured-for-support but not a fail: it cannot support,
        # and the decision map sends a non-pass non-fail E to mixed when A and B pass.
        status = "unmeasured"
        reason = f"{len(seen)} rearing-marked hosts, below the pass threshold of 10 and above the fail threshold of 0"
    return {
        "status": status,
        "reason": reason,
        "marks_survive": marks_survive,
        "start_line": lines[start],
        "end_line": lines[end] if end < len(lines) else None,
        "n_reared": len(seen),
        "reared": seen,
        "hippolais_lines": hippolais,
        "section_line_count": len(section),
    }


def hypolais_in_stokke(hosts: list[str], tables: dict) -> dict:
    names = []
    for key, sci, common in (
        ("ESM1", "Scientific.name", "Species"),
        ("ESM3", "Latin", "Species name"),
        ("ESM4", "Latin", "Species"),
    ):
        for _, row in tables[key].iterrows():
            sci_name = binomial(row.get(sci))
            label = str(row.get(common) or "")
            if sci_name and (sci_name.startswith("Hippolais ") or "hypolais" in label.lower() or "icterine" in label.lower()):
                names.append({"source": key, "binomial": sci_name, "common": label, "parasitized": sci_name in hosts})
    # unique parasitized
    parasitized = sorted({n["binomial"] for n in names if n["parasitized"]})
    return {"rows": names, "parasitized_binomials": parasitized}


def decide(a: str, b: str, c: str, d: str, e: str, stokke_downloaded: bool) -> tuple[str, str | None]:
    statuses = {"A": a, "B": b, "C": c, "D": d, "E": e}
    if any(v == "fail" for v in statuses.values()):
        return "refutes", None
    c_ok = c in ("pass", "unmeasured", "underpowered")
    d_ok = d in ("pass", "unmeasured", "underpowered")
    if a == "pass" and b == "pass" and e == "pass" and c_ok and d_ok and c != "intermediate" and d != "intermediate":
        return "supports", None
    if not stokke_downloaded or all(v == "unmeasured" for v in statuses.values()):
        return "inconclusive", "data-unavailable"
    if (a == "underpowered" or b == "underpowered") and b != "intermediate" and c != "intermediate":
        return "inconclusive", "underpowered"
    if b == "unmeasured" and e == "unmeasured":
        return "inconclusive", "other"
    return "mixed", None


def confidence_for(verdict: str, c: str, d: str) -> float:
    # Fixed before the measured fraction was used to choose a number: two clauses of the
    # compound claim have no column, so a pass cannot be read as confirmation of every clause.
    if verdict == "supports" and c == "unmeasured" and d == "unmeasured":
        return 0.58
    if verdict == "supports":
        return 0.74
    if verdict == "refutes":
        return 0.7
    if verdict == "mixed":
        return 0.46
    return 0.35


def main() -> None:
    DERIVED.mkdir(exist_ok=True)
    stokke_meta = fetch(STOKKE_ZIP, DATA / "stokke.zip")
    lowther_meta = fetch(LOWTHER_PDF, DATA / "lowther.pdf")
    avonet_meta = fetch(AVONET_XLSX, DATA / "AVONET_Supplementary_dataset_1.xlsx")
    loaded = load_stokke(DATA / "stokke.zip")
    laying = score_laying(loaded["tables"])
    masses = avonet_masses(DATA / "AVONET_Supplementary_dataset_1.xlsx")
    size = score_size(laying["hosts"], masses, loaded["tables"])
    rearing = lowther_account(DATA / "lowther.pdf")
    hypo = hypolais_in_stokke(laying["hosts"], loaded["tables"])

    verdict, reason = decide(
        laying["status"],
        size["status"],
        laying["clause_C"],
        laying["clause_D"],
        rearing["status"],
        stokke_downloaded=True,
    )
    conf = confidence_for(verdict, laying["clause_C"], laying["clause_D"])

    scored_rows = [r for r in size.get("rows", []) if r.get("lighter") is not None]
    masses_only = sorted((r["mass_g"] for r in scored_rows), reverse=True)
    heavier = sorted((r for r in scored_rows if r["lighter"] is False), key=lambda r: -r["mass_g"])
    count_totals = {h: {"ESM1_par_nests": 0, "ESM3_cases": 0, "ESM4_cases": 0} for h in (r["host"] for r in heavier)}
    for key, sci, col, bucket in (
        ("ESM1", "Scientific.name", "par_nests", "ESM1_par_nests"),
        ("ESM3", "Latin", "parasitism cases", "ESM3_cases"),
        ("ESM4", "Latin", "parasitism cases", "ESM4_cases"),
    ):
        for _, row in loaded["tables"][key].iterrows():
            name = binomial(row.get(sci))
            if name not in count_totals:
                continue
            try:
                value = float(row.get(col))
            except (TypeError, ValueError):
                continue
            if pd.notna(value) and value > 0:
                count_totals[name][bucket] += value
    for row in heavier:
        row["positive_counts"] = count_totals[row["host"]]
    median = None
    if masses_only:
        mid = len(masses_only) // 2
        median = masses_only[mid] if len(masses_only) % 2 == 1 else (masses_only[mid - 1] + masses_only[mid]) / 2

    hosts_df = pd.DataFrame(size.get("rows", []))
    reared_set = {item["binomial"] for item in rearing.get("reared", [])}
    if not hosts_df.empty:
        hosts_df["rearing_mark_in_lowther"] = hosts_df["host"].isin(reared_set)
        hosts_df.sort_values(["lighter", "mass_g"], ascending=[False, True]).to_csv(
            DERIVED / "hosts.csv", index=False
        )

    measured = {
        "value": None if size.get("fraction_lighter") is None else round(size["fraction_lighter"], 4),
        "unit": "fraction of parasitized host species with adult body mass below Cuculus canorus",
        "n": size.get("n_hosts_with_mass"),
        "uncertainty": None,
        "extra": {
            "cuckoo_mass_g": size.get("cuckoo_mass_g"),
            "cuckoo_mass_source": size.get("cuckoo_mass_source"),
            "cuckoo_mass_inference": size.get("cuckoo_mass_inference"),
            "n_parasitized_host_species": laying["n_host_species"],
            "n_lighter": size.get("n_lighter"),
            "n_unmatched_to_avonet": size.get("n_unmatched"),
            "median_host_mass_g": median,
            "heavier_hosts": heavier,
            "positive_rows": laying["positive_rows"],
            "self_host_rows": laying["self_host_rows"],
            "clause_A": laying["status"],
            "clause_B": size["status"],
            "clause_C": laying["clause_C"],
            "clause_D": laying["clause_D"],
            "clause_E": rearing["status"],
            "n_hosts_marked_reared": rearing.get("n_reared"),
            "reared_hosts": [item["binomial"] for item in rearing.get("reared", [])],
            "hippolais_parasitized_in_stokke": hypo["parasitized_binomials"],
            "hippolais_lines_in_lowther_account": rearing.get("hippolais_lines", []),
            "stokke_body_size_check_not_used_for_verdict": size.get("stokke_body_size_check_not_used_for_verdict"),
        },
    }
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["measured"] = measured
    result["verdict"] = verdict
    result["confidence"] = conf
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "stokke-2018-dryad-9r0n681",
            "name": "Data from: Characteristics determining host suitability for a generalist parasite",
            "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.9r0n681",
            "doi": "10.5061/dryad.9r0n681",
            "version": "1",
            "license": "CC0 1.0",
            "files": [
                {
                    "name": "doi_10.5061_dryad.9r0n681__v20190411.zip",
                    "download_url": STOKKE_ZIP,
                    "retrieved_at": stokke_meta["retrieved_at"],
                    "byte_size": stokke_meta["byte_size"],
                    "sha256": stokke_meta["sha256"],
                    "note": "Per-file Dryad links returned HTTP 401. The version zip is the public download. Members below are the files inside it.",
                },
                *[
                    {
                        "name": name,
                        "download_url": STOKKE_ZIP,
                        "retrieved_at": stokke_meta["retrieved_at"],
                        "byte_size": meta["byte_size"],
                        "sha256": meta["sha256"],
                    }
                    for name, meta in sorted(loaded["members"].items())
                ],
            ],
            "role": "population parasitism rates of Cuculus canorus and the host species they name",
        },
        {
            "id": "lowther-2025-ow-cuckoo-host-list",
            "name": "Host list of avian brood parasites — 2 — Cuculiformes, Old World cuckoos (Peter E. Lowther, Field Museum, version 05 Jun 2025)",
            "landing_url": LOWTHER_PDF,
            "doi": None,
            "version": "05 Jun 2025",
            "license": "not stated on the file; public working copy posted by the Field Museum author",
            "files": [
                {
                    "name": "host-list-ow-cuckoos-05jun2025.pdf",
                    "download_url": LOWTHER_PDF,
                    "retrieved_at": lowther_meta["retrieved_at"],
                    "byte_size": lowther_meta["byte_size"],
                    "sha256": lowther_meta["sha256"],
                }
            ],
            "role": "host species of Cuculus canorus, with the compiler's mark for hosts that have reared the parasite",
        },
        {
            "id": "avonet-tobias-2022-figshare-16586228",
            "name": "AVONET: morphological, ecological and geographical data for all birds",
            "landing_url": "https://doi.org/10.6084/m9.figshare.16586228.v7",
            "doi": "10.6084/m9.figshare.16586228.v7",
            "version": "v7",
            "license": "CC BY 4.0",
            "files": [
                {
                    "name": "AVONET Supplementary dataset 1.xlsx",
                    "download_url": AVONET_XLSX,
                    "retrieved_at": avonet_meta["retrieved_at"],
                    "byte_size": avonet_meta["byte_size"],
                    "sha256": avonet_meta["sha256"],
                }
            ],
            "role": "species-mean adult body mass in grams, sheet AVONET1_BirdLife, column Mass",
        },
    ]
    frac = measured["value"]
    result["method"] = (
        "Downloaded the Stokke Dryad version zip (per-file links returned HTTP 401), the Lowther host-list PDF, "
        "and AVONET Supplementary dataset 1. A host species counts as parasitized if ESM1 par_nests, ESM3 parasitism cases, "
        "or ESM4 parasitism cases is greater than zero. Adult body mass is the AVONET1_BirdLife Mass of that binomial. "
        "Rearing is a host binomial on a line prefixed with '&' or '%' inside the Cuculus canorus account, which runs from "
        "its heading to the next other brood-parasite heading that carries a year. Clauses C and D are unmeasured because "
        "those columns are not in the files. The verdict is the pre-registered map applied to the five clause statuses. "
        "Confidence is 0.58 on a support verdict when C and D are both unmeasured."
    )
    n_reared = rearing.get("n_reared")
    heavier_names = ", ".join(
        f"{r['host']} ({r['mass_g']:.1f} g; ESM1 parasitized nests {r['positive_counts']['ESM1_par_nests']:g}, "
        f"UK cases {r['positive_counts']['ESM3_cases']:g}, Germany cases {r['positive_counts']['ESM4_cases']:g})"
        for r in heavier[:8]
    ) or "none"
    hypo_txt = ", ".join(hypo["parasitized_binomials"]) or "none"
    result["results_summary"] = [
        f"Clause A {laying['status']}: {laying['n_host_species']} host species with a positive parasitism record; {laying['self_host_rows']} rows name Cuculus canorus as the host. Positive rows: {laying['positive_rows']}.",
        f"Clause B {size['status']}: {size.get('n_lighter')} of {size.get('n_hosts_with_mass')} matched hosts are lighter than Cuculus canorus at {size.get('cuckoo_mass_g')} g (fraction {frac}); {size.get('n_unmatched')} parasitized names did not match AVONET. Heavier hosts: {heavier_names}.",
        f"Clauses C and D unmeasured: {laying['clause_C_reason']}; {laying['clause_D_reason']}.",
        f"Clause E {rearing['status']}: {n_reared} host species in the Cuculus canorus account carry the file's successful-rearing prefix.",
        f"Scope check, not in the verdict: Hippolais species with a positive Stokke record: {hypo_txt}.",
    ]
    extra_caveat = (
        "Clauses C (usually one cuckoo egg) and D (the female devours the host's eggs) have no column in these files, "
        "so the support verdict does not speak for those two clauses. Clause A counts eggs recorded in other species' nests; "
        "a nest built by the cuckoo would not be in a parasitism compilation. Clause E counts host species the compiler marked "
        "as having reared a cuckoo, not the fraction of nests that fledged."
    )
    caveats = list(result.get("caveats") or [])
    if extra_caveat not in caveats:
        caveats.append(extra_caveat)
    result["caveats"] = caveats
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({
        "verdict": verdict,
        "reason": reason,
        "confidence": conf,
        "A": laying["status"],
        "B": size["status"],
        "fraction": frac,
        "n_mass": size.get("n_hosts_with_mass"),
        "n_hosts": laying["n_host_species"],
        "E": rearing["status"],
        "n_reared": n_reared,
        "cuckoo_g": size.get("cuckoo_mass_g"),
        "heavier": heavier_names,
        "hippolais": hypo_txt,
    }, indent=2))


if __name__ == "__main__":
    main()
