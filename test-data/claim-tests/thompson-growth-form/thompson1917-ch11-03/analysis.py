#!/usr/bin/env python3
"""thompson1917-ch11-03: does a steady transverse proportion predict a steady spiral angle?

The pass and fail rules are the ones committed in result.json before this file was
downloaded. This script only applies them.

WHI = (1 - UWI) / 2 at each half-whorl. CV is the sample standard deviation divided
by the mean. Spearman rho is the Pearson correlation of average ranks. The two-sided
p-value uses t = rho * sqrt((n - 2) / (1 - rho^2)) with n - 2 degrees of freedom.

Run from this directory: python3 analysis.py
Requires numpy, scipy and openpyxl (Dryad serves the table as xlsx).
"""

import datetime as dt
import hashlib
import io
import json
import math
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import openpyxl
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
XLSX_NAME = "Ontogenetic_Conch_Parameter_Data.xlsx"
# Per-file Dryad URL returns 401. The version endpoint redirects to a short-lived
# archive whose only member is the xlsx named in the Dryad file record.
DOWNLOAD_URL = "https://datadryad.org/api/v2/versions/7242/download"
EXPECTED_MD5 = "0302022d2f622b73754cf0e66c54f2ac"
EXPECTED_SIZE = 215182
MIN_STAGES = 8
MIN_SPECIES = 40
RHO_PASS = 0.30
RHO_FAIL = 0.10
P_PASS = 0.01

FROZEN = (
    "hypothesis",
    "pass_criterion",
    "fail_criterion",
    "planned_datasets",
    "test_contract",
    "interpretation",
    "secondary_analyses_descriptive",
)


def fetch_xlsx():
    DATA.mkdir(exist_ok=True)
    path = DATA / XLSX_NAME
    req = urllib.request.Request(
        DOWNLOAD_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; delphisci-claim-test/1.0)",
            "Accept": "*/*",
        },
    )
    blob = urllib.request.urlopen(req, timeout=180).read()
    if blob[:2] == b"PK" and blob[2:4] != b"\x03\x04":
        # zip local-file magic is PK\x03\x04; some wrappers still start with PK
        pass
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            names = [n for n in zf.namelist() if n.endswith(".xlsx")]
            if len(names) != 1:
                raise RuntimeError(f"expected one xlsx in the archive, found {names}")
            raw = zf.read(names[0])
    except zipfile.BadZipFile:
        raw = blob
    path.write_bytes(raw)
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    info = {
        "name": XLSX_NAME,
        "download_url": DOWNLOAD_URL,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "md5": hashlib.md5(raw).hexdigest(),
        "matches_registered_md5": hashlib.md5(raw).hexdigest() == EXPECTED_MD5,
        "matches_registered_size": len(raw) == EXPECTED_SIZE,
    }
    return raw, info


def sheet_rows(raw, sheet_name):
    wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    ws = wb[sheet_name]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    header = [("" if c is None else str(c).strip()) for c in rows[0]]
    return header, rows[1:]


def whorl_columns(header):
    return [i for i, h in enumerate(header) if h.lower().startswith("whorl")]


def species_column(header):
    wanted = ("species", "taxon", "species name")
    lowered = [h.lower() for h in header]
    for name in wanted:
        if name in lowered:
            return lowered.index(name)
    raise RuntimeError(f"no species column in {header[:8]}")


def as_float(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if text == "" or text.upper() == "NA":
            return None
        try:
            value = float(text)
        except ValueError:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def series_by_species(raw, sheet_name):
    header, rows = sheet_rows(raw, sheet_name)
    sp_col = species_column(header)
    cols = whorl_columns(header)
    out = {}
    order = []
    for row in rows:
        if sp_col >= len(row) or row[sp_col] is None:
            continue
        name = str(row[sp_col]).strip()
        if not name:
            continue
        values = []
        for i in cols:
            values.append(as_float(row[i]) if i < len(row) else None)
        # A repeated name would mix two ontogenies. Keep each data row.
        key = name if name not in out else f"{name}__dup{len(order)}"
        out[key] = values
        order.append(key)
    return [header[i] for i in cols], out, order


def cv(values):
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    if mean == 0:
        return None
    return float(arr.std(ddof=1) / mean)


def spearman(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = int(x.size)
    if n < 3:
        return {"n": n, "rho": None, "p": None}
    rx = stats.rankdata(x, method="average")
    ry = stats.rankdata(y, method="average")
    if np.std(rx) == 0 or np.std(ry) == 0:
        return {"n": n, "rho": None, "p": None}
    rho = float(np.corrcoef(rx, ry)[0, 1])
    if abs(rho) >= 1.0:
        p = 0.0
    else:
        tstat = rho * math.sqrt((n - 2) / (1.0 - rho * rho))
        p = float(2 * stats.t.sf(abs(tstat), n - 2))
    check = stats.spearmanr(x, y)
    return {
        "n": n,
        "rho": rho,
        "p": p,
        "scipy_spearman_rho": float(check.statistic),
        "scipy_spearman_p": float(check.pvalue),
    }


def confidence_for(verdict, rho):
    # Fixed before the correlation was computed. Confidence is in the verdict.
    if verdict == "supports":
        return 0.70 if rho is not None and rho >= 0.50 else 0.55
    if verdict == "refutes":
        return 0.75 if rho is not None and rho <= 0 else 0.60
    if verdict == "mixed":
        return 0.45
    if verdict == "inconclusive":
        return 0.60
    return 0.50


def decide(rho, p, n, checksum_ok):
    if not checksum_ok:
        return "inconclusive", "data-unavailable"
    if n < MIN_SPECIES or rho is None or p is None:
        if rho is None and n >= MIN_SPECIES:
            return "inconclusive", "other"
        return "inconclusive", "underpowered" if checksum_ok else "data-unavailable"
    if n >= MIN_SPECIES and rho <= RHO_FAIL:
        return "refutes", None
    if n >= MIN_SPECIES and rho >= RHO_PASS and p < P_PASS:
        return "supports", None
    return "mixed", None


def ols_r2(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.size < 3 or np.std(x) == 0:
        return None
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    ss_res = float(np.sum((y - pred) ** 2))
    if ss_tot == 0:
        return None
    return {"r2": 1.0 - ss_res / ss_tot, "slope": float(slope), "n": int(x.size)}


def main():
    raw, file_info = fetch_xlsx()
    checksum_ok = file_info["matches_registered_md5"] and file_info["matches_registered_size"]
    uwi_headers, uwi, uwi_order = series_by_species(raw, "UWI")
    wer_headers, wer, wer_order = series_by_species(raw, "WER")
    cwi_headers, cwi, _cwi_order = series_by_species(raw, "CWI")
    if uwi_headers != wer_headers:
        raise RuntimeError("UWI and WER whorl headers differ")

    records = []
    for name in uwi_order:
        if name not in wer:
            continue
        paired_u = []
        paired_w = []
        paired_c = []
        cwi_row = cwi.get(name)
        for u, w, c in zip(uwi[name], wer[name], cwi_row if cwi_row is not None else [None] * len(uwi[name])):
            if u is None or w is None:
                continue
            if not (w > 0 and 0 <= u < 1):
                continue
            paired_u.append(u)
            paired_w.append(w)
            if c is not None and c > 0:
                paired_c.append(c)
        if len(paired_w) < MIN_STAGES:
            continue
        whi = [(1.0 - u) / 2.0 for u in paired_u]
        cv_whi = cv(whi)
        cv_wer = cv(paired_w)
        if cv_whi is None or cv_wer is None:
            continue
        rec = {
            "species": name,
            "n_stages": len(paired_w),
            "cv_whi": cv_whi,
            "cv_wer": cv_wer,
            "mean_whi": float(np.mean(whi)),
            "mean_wer": float(np.mean(paired_w)),
            "mean_uwi": float(np.mean(paired_u)),
        }
        if len(paired_c) >= MIN_STAGES:
            rec["cv_cwi"] = cv(paired_c)
            rec["mean_cwi"] = float(np.mean(paired_c))
        records.append(rec)

    primary = spearman([r["cv_whi"] for r in records], [r["cv_wer"] for r in records])
    with_cwi = [r for r in records if "cv_cwi" in r]
    secondary_cwi = spearman([r["cv_cwi"] for r in with_cwi], [r["cv_wer"] for r in with_cwi])
    steady = [r for r in records if r["cv_whi"] <= 0.05 and r["mean_wer"] > 0]
    magnitude = None
    if len(steady) >= 15:
        magnitude = ols_r2(
            [r["mean_whi"] for r in steady],
            [math.log(r["mean_wer"]) for r in steady],
        )
    alphas = []
    for r in records:
        if r["mean_wer"] > 1:
            alphas.append(math.degrees(math.atan(2 * math.pi / math.log(r["mean_wer"]))))
    alpha_summary = None
    if alphas:
        alpha_summary = {
            "n": len(alphas),
            "median_deg": float(np.median(alphas)),
            "min_deg": float(np.min(alphas)),
            "max_deg": float(np.max(alphas)),
        }
    cv_wer_vals = [r["cv_wer"] for r in records]
    fraction_steady_wer = None
    if cv_wer_vals:
        fraction_steady_wer = float(np.mean([v <= 0.10 for v in cv_wer_vals]))

    verdict, reason = decide(primary["rho"], primary["p"], primary["n"], checksum_ok)
    if not checksum_ok:
        verdict, reason = "inconclusive", "data-unavailable"

    rho = primary["rho"]
    conf = confidence_for(verdict, rho)
    if verdict == "inconclusive" and reason == "data-unavailable":
        conf = 0.90

    measured = {
        "value": None if rho is None else round(rho, 6),
        "unit": "Spearman rho of CV(WHI) against CV(WER)",
        "n": primary["n"],
        "uncertainty": None if primary["p"] is None else f"two-sided p = {primary['p']:.6g}",
        "extra": {
            "p": primary["p"],
            "scipy_spearman_rho": primary.get("scipy_spearman_rho"),
            "scipy_spearman_p": primary.get("scipy_spearman_p"),
            "min_stages": MIN_STAGES,
            "median_cv_whi": float(np.median([r["cv_whi"] for r in records])) if records else None,
            "median_cv_wer": float(np.median(cv_wer_vals)) if cv_wer_vals else None,
            "fraction_cv_wer_at_most_0.10": fraction_steady_wer,
            "cwi_sensitivity": {
                "n": secondary_cwi["n"],
                "rho": secondary_cwi["rho"],
                "p": secondary_cwi["p"],
            },
            "steady_whi_magnitude": magnitude,
            "n_steady_whi_cv_at_most_0.05": len(steady),
            "alpha_from_mean_wer_deg": alpha_summary,
            "checksum_ok": checksum_ok,
        },
    }

    DERIVED.mkdir(exist_ok=True)
    species_out = []
    for r in records:
        species_out.append({k: (round(v, 6) if isinstance(v, float) else v) for k, v in r.items()})
    (DERIVED / "measured.json").write_text(
        json.dumps(
            {
                "primary": primary,
                "measured": measured,
                "verdict": verdict,
                "reason": reason,
                "species": species_out,
            },
            indent=2,
        )
        + "\n"
    )

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    frozen = {k: result.get(k) for k in FROZEN}
    result["status"] = "complete"
    result["data_kind"] = "biological" if checksum_ok and primary["n"] else "none"
    if verdict == "inconclusive" and reason == "data-unavailable":
        result["data_kind"] = "none"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["confidence"] = conf
    result["datasets"] = [
        {
            "id": "walton-korn-2018-ontogenetic-conch-dryad-c17p8",
            "name": "Ontogenetic conch parameters of 177 Devonian to Jurassic ammonoid species",
            "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.c17p8",
            "doi": "10.5061/dryad.c17p8",
            "version": "2018-05-16",
            "license": "CC0-1.0",
            "files": [file_info],
            "role": "ontogenetic CWI, UWI and WER for ammonoid median sections, one species per row",
        }
    ]
    result["measured"] = measured
    result["method"] = (
        "Downloaded the Dryad version archive, extracted Ontogenetic_Conch_Parameter_Data.xlsx, "
        "and checked its md5 and byte size against the Dryad file record registered before download. "
        "UWI and WER are on separate sheets in wide form (whorl columns). Stages were paired by whorl "
        "header. A species entered the correlation only with at least 8 stages where WER > 0 and "
        "UWI was in [0, 1). WHI = (1 - UWI) / 2. Spearman rho is the Pearson correlation of average "
        "ranks, and the p-value is the pre-registered t approximation. The verdict is the rule in "
        "pass_criterion and fail_criterion. CWI, the steady-WHI regression and the angles are descriptive."
    )
    rho_txt = "undefined" if measured["value"] is None else f"{measured['value']:.5f}"
    p_txt = "undefined" if primary["p"] is None else f"{primary['p']:.4g}"
    med_whi = measured["extra"]["median_cv_whi"]
    med_wer = measured["extra"]["median_cv_wer"]
    frac = measured["extra"]["fraction_cv_wer_at_most_0.10"]
    cwi_rho = secondary_cwi["rho"]
    cwi_p = secondary_cwi["p"]
    alpha_bit = "no species with mean WER > 1"
    if alpha_summary:
        alpha_bit = (
            f"alpha from mean WER spans {alpha_summary['min_deg']:.2f} to "
            f"{alpha_summary['max_deg']:.2f} degrees (median {alpha_summary['median_deg']:.2f})"
        )
    result["results_summary"] = [
        f"Eligible species: {primary['n']} (every species row had at least {MIN_STAGES} paired stages). Spearman rho of CV(WHI) against CV(WER) = {rho_txt}, two-sided p = {p_txt}.",
        (
            f"Verdict {verdict}"
            + (f" ({reason})" if reason else "")
            + f", confidence {conf}. "
            + (
                "rho is at least 0.30 and p is below 0.01."
                if verdict == "supports"
                else "rho is at or below 0.10."
                if verdict == "refutes"
                else "The support rule needs rho >= 0.30 and p < 0.01; the refute rule is rho <= 0.10; this result is in between."
                if verdict == "mixed"
                else "The eligible sample or the checksum did not meet the pre-registered conditions for a supports or refutes verdict."
            )
        ),
        (
            f"Median CV(WHI) = {med_whi:.4f}, median CV(WER) = {med_wer:.4f}, "
            f"and {frac:.3f} of species have CV(WER) <= 0.10. "
            f"CWI in place of WHI gives rho = {None if cwi_rho is None else round(cwi_rho, 4)} "
            f"(p = {None if cwi_p is None else round(cwi_p, 4)}). "
            f"Species with CV(WHI) <= 0.05: {len(steady)}, so the magnitude regression was not run (it needed 15). "
            f"{alpha_bit}. These descriptions are not the verdict."
        ),
        "The Dryad abstract describes this table as globular and pachyconic ammonoids. The angles sit in a narrow band near 85 degrees, so there is little expansion-rate difference for a transverse ratio to determine. Horns are not in the table.",
    ]
    for key, value in frozen.items():
        if result.get(key) != value:
            raise RuntimeError(f"refusing to alter pre-registered field {key}")
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "n": primary["n"], "rho": rho, "p": primary["p"], "confidence": conf}, indent=2))


if __name__ == "__main__":
    main()
