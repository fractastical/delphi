#!/usr/bin/env python3
"""Test aristotle-ga01-21 against the Human Protein Atlas consensus RNA file.

Re-run from this directory: python3 analysis.py
The zip is several MB and is not committed.
"""
import hashlib
import html
import io
import json
import os
import re
import time
import zipfile
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

HPA_URL = "https://www.proteinatlas.org/download/tsv/rna_tissue_consensus.tsv.zip"
LICENCE_URL = "https://www.proteinatlas.org/about/licence"
ENSEMBL = "https://rest.ensembl.org/lookup/symbol/homo_sapiens/{symbol}"
SEMEN = ["PRM1", "PRM2", "TNP1", "ODF1", "AKAP4", "SEMG1", "SEMG2", "KLK3"]
CONTROLS = ["ALB", "TTN", "INS", "GFAP"]
SEMEN_TISSUES = {"testis", "epididymis", "prostate", "seminal vesicle"}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch_ensembl(symbol):
    r = requests.get(ENSEMBL.format(symbol=symbol), headers={"Content-Type": "application/json", "User-Agent": "DelphiClaimTest/1.0"}, timeout=60)
    rec = {
        "symbol": symbol,
        "download_url": r.url,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": sha256(r.content),
        "status_code": r.status_code,
    }
    if r.status_code != 200:
        rec["id"] = None
        return rec
    body = r.json()
    rec["id"] = body.get("id")
    rec["display_name"] = body.get("display_name")
    return rec


def licence_text():
    try:
        r = requests.get(LICENCE_URL, timeout=60, headers={"User-Agent": "DelphiClaimTest/1.0"})
        r.raise_for_status()
        text = html.unescape(re.sub(r"<[^>]+>", " ", r.text))
        text = re.sub(r"\s+", " ", text)
        m = re.search(r"licensed under the (Creative Commons Attribution \d+\.\d+ International License)", text, re.I)
        return (m.group(1) if m else "not stated on the retrieved licence page"), r.url
    except requests.RequestException as exc:
        return f"licence page not retrieved: {exc}", LICENCE_URL


def pick_columns(df):
    cols = {c.lower(): c for c in df.columns}
    gene = cols.get("gene") or cols.get("ensembl") or df.columns[0]
    tissue = cols.get("tissue")
    ntpm = None
    for key in ("ntpm", "tpm", "nx"):
        if key in cols:
            ntpm = cols[key]
            break
    if ntpm is None:
        for c in df.columns:
            if "tpm" in c.lower():
                ntpm = c
                break
    symbol = cols.get("gene name") or cols.get("gene_name") or cols.get("symbol")
    return gene, tissue, ntpm, symbol


def peak(sub):
    totals = sub.groupby("tissue_key")["level"].max()
    top = float(totals.max())
    winners = sorted(totals[totals == top].index.tolist())
    outside = [t for t in winners if t not in SEMEN_TISSUES]
    semen_peak = len(winners) > 0 and not outside and all(t in SEMEN_TISSUES for t in winners)
    outside_peak = len(winners) == 1 and winners[0] not in SEMEN_TISSUES
    other = totals.drop(labels=[t for t in totals.index if t in SEMEN_TISSUES], errors="ignore")
    median = float(other.median()) if len(other) else None
    ratio = None
    if semen_peak and median is not None:
        ratio = float("inf") if median == 0 and top > 0 else (top / median if median else None)
    return {
        "max_ntpm": top,
        "max_tissues": winners,
        "semen_peak": semen_peak,
        "outside_peak": outside_peak,
        "tie_includes_outside": bool(outside) and len(winners) > 1,
        "median_outside": median,
        "ratio_to_median_outside": None if ratio is None else (None if ratio == float("inf") else round(ratio, 3)),
        "ratio_infinite": ratio == float("inf"),
        "tenfold": bool(semen_peak and ratio is not None and ratio >= 10),
    }


def main():
    r = requests.get(HPA_URL, timeout=180, headers={"User-Agent": "DelphiClaimTest/1.0"})
    r.raise_for_status()
    open(os.path.join(DATA, "rna_tissue_consensus.tsv.zip"), "wb").write(r.content)
    file_rec = {
        "download_url": HPA_URL,
        "retrieved_at": now(),
        "byte_size": len(r.content),
        "sha256": sha256(r.content),
        "content_type": r.headers.get("content-type", ""),
        "final_url": r.url,
    }
    licence, licence_url = licence_text()
    reason = None
    if not r.content.startswith(b"PK"):
        verdict, reason = "inconclusive", "data-unavailable"
        measured = {"value": None, "unit": "semen genes", "n": 0, "uncertainty": "download was not a zip", "extra": {}}
        lookups = []
    else:
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            name = zf.namelist()[0]
            df = pd.read_csv(zf.open(name), sep="\t")
        gene_col, tissue_col, ntpm_col, symbol_col = pick_columns(df)
        lookups = []
        for symbol in SEMEN + CONTROLS:
            lookups.append(fetch_ensembl(symbol))
            time.sleep(0.2)
        id_by_symbol = {rec["symbol"]: rec.get("id") for rec in lookups}
        df = df.copy()
        df["gene_id"] = df[gene_col].astype(str)
        df["tissue_key"] = df[tissue_col].astype(str).str.strip().str.lower()
        df["level"] = pd.to_numeric(df[ntpm_col], errors="coerce")
        if symbol_col:
            df["symbol_in_file"] = df[symbol_col].astype(str).str.upper()
        rows = []
        for symbol in SEMEN + CONTROLS:
            ensembl_id = id_by_symbol.get(symbol)
            sub = df[df["gene_id"] == ensembl_id] if ensembl_id else df.iloc[0:0]
            if sub.empty and symbol_col:
                sub = df[df["symbol_in_file"] == symbol]
            if sub.empty:
                rows.append({"symbol": symbol, "ensembl_id": ensembl_id, "found": False, "role": "semen" if symbol in SEMEN else "control"})
                continue
            info = peak(sub.dropna(subset=["level"]))
            info.update({"symbol": symbol, "ensembl_id": ensembl_id, "found": True, "n_tissues": int(sub["tissue_key"].nunique()), "role": "semen" if symbol in SEMEN else "control"})
            rows.append(info)
        semen_found = [row for row in rows if row["role"] == "semen" and row["found"]]
        controls_found = [row for row in rows if row["role"] == "control" and row["found"]]
        tenfold = [row["symbol"] for row in semen_found if row.get("tenfold")]
        outside = [row["symbol"] for row in semen_found if row.get("outside_peak") or row.get("tie_includes_outside")]
        control_peak = [row["symbol"] for row in controls_found if row.get("semen_peak")]
        if len(semen_found) < 5 or len(control_peak) >= 2:
            verdict, reason = "inconclusive", "other"
        elif len(tenfold) >= 6 and len(control_peak) < 2:
            verdict = "supports"
        elif len(outside) >= 3:
            verdict = "refutes"
        else:
            verdict = "mixed"
        measured = {
            "value": len(tenfold),
            "unit": "semen genes whose maximum nTPM is in testis, epididymis, prostate or seminal vesicle and at least 10 times the median of the other tissues",
            "n": len(semen_found),
            "uncertainty": "maximum per tissue; a tie that includes a tissue outside the four is not a semen peak",
            "extra": {
                "genes": rows,
                "semen_tenfold": tenfold,
                "semen_max_outside_or_tie": outside,
                "controls_peaking_in_semen_tissues": control_peak,
                "columns": {"gene": gene_col, "tissue": tissue_col, "level": ntpm_col, "symbol": symbol_col},
                "zip_member": name,
                "verdict_by_rule": verdict,
            },
        }

    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "none" if reason == "data-unavailable" else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = 0.8 if verdict == "supports" else 0.55
    result["datasets"] = [
        {
            "id": "hpa-rna-tissue-consensus",
            "name": "Human Protein Atlas consensus RNA by tissue",
            "landing_url": "https://www.proteinatlas.org/humanproteome/tissue/data",
            "doi": None,
            "version": "rna_tissue_consensus.tsv.zip as served on the retrieval date",
            "license": licence,
            "files": [file_rec],
            "role": "nTPM by gene and normal tissue",
        },
        {
            "id": "ensembl-symbol-lookup",
            "name": "Ensembl REST symbol lookup, homo_sapiens",
            "landing_url": "https://rest.ensembl.org/",
            "doi": None,
            "version": "lookup/symbol/homo_sapiens",
            "license": "not retrieved; the responses are the public symbol-lookup JSON",
            "files": [{k: rec[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")} for rec in lookups],
            "role": "map the pre-registered symbols to Ensembl gene ids",
        },
    ]
    result["method"] = (
        "The consensus zip was opened and the nTPM column was read. "
        "Each pre-registered symbol was resolved through Ensembl and matched to that gene id. "
        "The tissue of maximum nTPM was taken. A tie that includes a tissue outside testis, epididymis, prostate and seminal vesicle is not a semen peak. "
        "The tenfold test compares that maximum with the median nTPM of tissues outside those four. No gene was added after the file was opened."
    )
    result["measured"] = measured
    result["caveats"] = [
        "The file is human. It stands in for animals that emit semen, which is the pre-registered limit.",
        "Where the median nTPM outside the four semen tissues is 0, a positive semen-tissue maximum meets the tenfold rule because it is greater than ten times zero.",
        "The markers are sperm and seminal-plasma genes, not a sample of every transcript in semen.",
        "A peak in the four organs does not show that no nutrient in semen ever passed through another organ. That reading was set aside before the test.",
    ]
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "tenfold": measured.get("extra", {}).get("semen_tenfold"), "outside": measured.get("extra", {}).get("semen_max_outside_or_tie"), "controls": measured.get("extra", {}).get("controls_peaking_in_semen_tissues")}, indent=2))


if __name__ == "__main__":
    main()
