#!/usr/bin/env python3
"""Test aristotle-ga03-10 against Salamon and Kent 2014.

The publisher PDF is a scan. Counts are read from Tesseract OCR of the
rendered pages. Re-run from this directory: python3 analysis.py
Requires pdftoppm and tesseract.
"""
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

PDF_URL = "https://docsdrive.com/pdfs/ansinet/ijps/2014/316-318.pdf"
DOI = "10.3923/ijps.2014.316.318"
LANDING = "https://doi.org/10.3923/ijps.2014.316.318"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def fetch(url):
    r = requests.get(url, timeout=120, headers={"User-Agent": "DelphiClaimTest/1.0"})
    r.raise_for_status()
    return r.content, r.headers.get("content-type", ""), r.url


def ocr_pdf(path):
    prefix = os.path.join(DATA, "page")
    subprocess.check_call(["pdftoppm", "-png", "-r", "200", path, prefix])
    pages = sorted(p for p in os.listdir(DATA) if p.startswith("page-") and p.endswith(".png"))
    chunks = []
    for p in pages:
        txt = subprocess.check_output(["tesseract", os.path.join(DATA, p), "stdout"], stderr=subprocess.DEVNULL)
        chunks.append(txt.decode("utf-8", "replace"))
    return "\n".join(chunks), pages


def load_result():
    with open(os.path.join(HERE, "result.json")) as f:
        return json.load(f)


def save_result(result):
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main():
    pdf, ctype, final_url = fetch(PDF_URL)
    pdf_path = os.path.join(DATA, "salamon-kent-2014.pdf")
    open(pdf_path, "wb").write(pdf)
    file_rec = {
        "download_url": PDF_URL,
        "retrieved_at": now(),
        "byte_size": len(pdf),
        "sha256": sha256(pdf),
        "content_type": ctype,
        "final_url": final_url,
    }
    text, pages = ocr_pdf(pdf_path)
    text = re.sub(r"\s+", " ", text)

    notes = []
    species = []

    blunt_m = re.search(r"(\d+)\s+blunt end first", text, re.I)
    total_m = re.search(r"total of\s+(\d+)\s+single yolked\s*\(SY\)\s+eggs", text, re.I)
    pct_m = re.search(r"(\d+\.\d+)\s*%\s+of (?:these |the )?SY goose eggs were laid pointed end first", text, re.I)
    if not pct_m:
        pct_m = re.search(r"(\d+\.\d+)\s*%\s+of the single yolked\s*\(SY\)\s+goose eggs were laid pointed end first", text, re.I)
    if blunt_m and total_m:
        blunt = int(blunt_m.group(1))
        total = int(total_m.group(1))
        pointed = total - blunt
        rec = {
            "species": "domestic goose",
            "pointed": pointed,
            "blunt": blunt,
            "n": total,
            "source_sentence": "SY goose eggs: blunt-end-first count and total",
        }
        if pct_m and total:
            printed = float(pct_m.group(1))
            computed = 100.0 * pointed / total
            rec["printed_pointed_percent"] = printed
            rec["computed_pointed_percent"] = round(computed, 2)
            rec["percent_matches_printed"] = abs(computed - printed) < 0.2
        species.append(rec)
    else:
        notes.append("Goose blunt count or total was not found in the OCR.")

    duck = re.search(
        r"(\d+)\s+of the\s+(\d+)\s*(?:\(\s*\d+\.\d+\s*%\s*\))?\s*random layings were observed as pointed end first",
        text,
        re.I,
    )
    if not duck:
        duck = re.search(r"(\d+)\s+of the\s+(\d+).{0,40}pointed end first", text, re.I)
    if duck:
        pointed = int(duck.group(1))
        total = int(duck.group(2))
        rec = {
            "species": "domestic duck",
            "pointed": pointed,
            "blunt": total - pointed,
            "n": total,
            "source_sentence": duck.group(0),
        }
        pct = re.search(r"(\d+\.\d+)\s*%", duck.group(0))
        if pct and total:
            printed = float(pct.group(1))
            computed = 100.0 * pointed / total
            rec["printed_pointed_percent"] = printed
            rec["computed_pointed_percent"] = round(computed, 2)
            rec["percent_matches_printed"] = abs(computed - printed) < 0.2
        species.append(rec)
    else:
        notes.append("Duck pointed-end-first count was not found in the OCR.")

    fowl_pointed = fowl_total = 0
    fowl_rows = []
    for m in re.finditer(r"(\d+\.?\d*)\s*%\s*\(\s*(\d+)\s*/\s*(\d+)\s*\)", text):
        window = text[max(0, m.start() - 80):m.end() + 80]
        if not re.search(r"pointed end first", window, re.I):
            continue
        num, den = int(m.group(2)), int(m.group(3))
        printed = float(m.group(1))
        fowl_rows.append({
            "printed_percent": printed,
            "pointed": num,
            "n": den,
            "computed_percent": round(100.0 * num / den, 2) if den else None,
            "percent_matches_printed": abs(100.0 * num / den - printed) < 0.3 if den else False,
        })
        if den >= 20:
            fowl_pointed += num
            fowl_total += den
    if fowl_total:
        species.append({
            "species": "domestic fowl",
            "pointed": fowl_pointed,
            "blunt": fowl_total - fowl_pointed,
            "n": fowl_total,
            "pooled_from": fowl_rows,
        })

    bradfield = re.search(r"(\d+)\s+of the\s+(\d+)\s+hens", text, re.I)
    excluded = []
    if bradfield:
        num, den = int(bradfield.group(1)), int(bradfield.group(2))
        # "9 of the 10 hens ... blunt end first"
        excluded.append({
            "species": "domestic fowl",
            "label": "Bradfield 1951 as printed in this paper",
            "blunt": num,
            "n": den,
            "counted_in_verdict": den >= 20,
        })

    eligible = []
    for sp in species:
        if sp["n"] < 20 or sp["pointed"] is None or sp["blunt"] is None:
            continue
        blunt_share = sp["blunt"] / sp["n"]
        pointed_share = sp["pointed"] / sp["n"]
        if blunt_share > 0.5:
            side = "blunt"
        elif pointed_share > 0.5:
            side = "pointed"
        else:
            side = "tie"
        sp["blunt_share"] = round(blunt_share, 4)
        sp["pointed_share"] = round(pointed_share, 4)
        sp["majority"] = side
        eligible.append(sp)

    reason = None
    if not eligible:
        verdict, reason = "inconclusive", "data-unavailable"
    elif all(sp["majority"] == "blunt" for sp in eligible):
        verdict = "supports"
    elif all(sp["majority"] == "pointed" for sp in eligible):
        verdict = "refutes"
    elif any(sp["majority"] == "blunt" for sp in eligible) and any(sp["majority"] == "pointed" for sp in eligible):
        verdict = "mixed"
    else:
        verdict, reason = "inconclusive", "other"
        notes.append("At least one eligible species has a blunt share of exactly 0.5, which is neither a pass nor the all-pointed fail.")

    checks = []
    for sp in species:
        if sp.get("percent_matches_printed") is True:
            checks.append(True)
        if sp.get("pooled_from"):
            checks.extend(row["percent_matches_printed"] for row in sp["pooled_from"])
    confidence = 0.86 if checks and all(checks) else 0.62

    measured = {
        "value": sum(1 for sp in eligible if sp["majority"] == "blunt"),
        "unit": "eligible species (n>=20) with blunt-end-first share strictly above 0.5",
        "n": len(eligible),
        "uncertainty": "counts read by OCR from a scanned PDF; percentages recomputed from the extracted numerators",
        "extra": {
            "species": species,
            "eligible": [{k: sp[k] for k in ("species", "pointed", "blunt", "n", "blunt_share", "pointed_share", "majority")} for sp in eligible],
            "excluded_below_n20": excluded,
            "double_yolked_both_counts_stated": False,
            "ocr_pages": pages,
            "verdict_by_rule": verdict,
        },
    }

    result = load_result()
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = confidence
    result["datasets"] = [{
        "id": "salamon-kent-2014-egg-orientation",
        "name": "Salamon and Kent 2014, Orientation of the egg at laying",
        "landing_url": LANDING,
        "doi": DOI,
        "version": "International Journal of Poultry Science 13(6):316-318",
        "license": "Copyright Asian Network for Scientific Information 2014, as printed on the PDF; no Creative Commons grant is printed on the file",
        "files": [file_rec],
        "role": "direct oviposition counts for geese and ducks, and cited hen fractions that print a numerator and a denominator",
    }]
    result["method"] = (
        "The publisher PDF was downloaded and rendered at 200 dpi with pdftoppm. "
        "Tesseract read each page. Domestic-goose blunt and total counts, the domestic-duck "
        "pointed-end-first fraction, and parenthetical hen fractions were taken from that text. "
        "Shares are blunt/(blunt+pointed). Fractions with n<20 are reported and do not enter the verdict. "
        "Hen series that each have n>=20 are pooled as domestic fowl. Double-yolked eggs have no paired counts in this paper."
    )
    result["measured"] = measured
    result["caveats"] = [
        "The PDF is a scan, so the counts depend on OCR. Each percentage cited beside a fraction was recomputed from the extracted numerator and denominator.",
        "Domestic fowl enters only through fractions this paper prints (Wood-Gush and Gilbert). Bradfield's 9 of 10 is below the pre-registered floor of 20 and is not in the verdict.",
        "The attachment-to-the-uterus clause is not measured. Double-yolked eggs are discussed in the paper without a pointed-versus-blunt count, so they do not set the verdict.",
    ] + notes
    save_result(result)
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    print(json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "eligible": measured["extra"]["eligible"]}, indent=2))


if __name__ == "__main__":
    main()
