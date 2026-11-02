#!/usr/bin/env python3
"""Brain/body ratio and human sex difference for aristotle-pa02-17.

Criteria are the pre-registered result.json (commit before download). This script
fetches the Tsuboi workbooks, checks the registered MD5s, and fills measured,
verdict, and data_kind. The Burger Dryad file is attempted; a failed fetch is
recorded and does not change the thresholds.
"""
import csv
import datetime as dt
import hashlib
import json
import math
import urllib.request
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
UA = "delphisci-claim-test/1.0"

TSUBOI = [
    ("Tsuboi_etal_NEE_amphibian.xlsx", "https://ndownloader.figshare.com/files/12384062", 89709, "542544a1b13e50d197b7a7fbc609ab06"),
    ("Tsuboi_etal_NEE_bird.xlsx", "https://ndownloader.figshare.com/files/12384068", 1126942, "b3d6fd8e0f4395b11b691e99e7e14628"),
    ("Tsuboi_etal_NEE_mammal.xlsx", "https://ndownloader.figshare.com/files/12384065", 373510, "ad4c91be6e79e8d1c3ff03f5ab946ae6"),
    ("Tsuboi_etal_NEE_reptile.xlsx", "https://ndownloader.figshare.com/files/12384071", 56289, "cbc361b0a39de5af885544e9921d96fb"),
    ("Tsuboi_etal_NEE_shark_ray.xlsx", "https://ndownloader.figshare.com/files/12384074", 86236, "fa1aabc4e3f72383fdfa17a950b82aa4"),
    ("Tsuboi_etal_NEE_teleost.xlsx", "https://ndownloader.figshare.com/files/12384077", 310372, "b45ba45ea145674c65e7cc67d308e457"),
]
BURGER = ("BrainAllometry_Supplement_Data.csv", "https://datadryad.org/api/v2/files/94072/download", 203795, "3a68156bcdbc6531895c51fdaf2fb111")


def now_utc():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest, size, md5):
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = dest.read_bytes() if dest.exists() else b""
    if not raw or hashlib.md5(raw).hexdigest() != md5 or len(raw) != size:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
    got = hashlib.md5(raw).hexdigest()
    if got != md5 or len(raw) != size:
        raise RuntimeError(f"checksum/size mismatch for {dest.name}: md5 {got} size {len(raw)}")
    return {
        "name": dest.name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "md5": got,
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def read_xlsx(path):
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{NS}si"):
                shared.append("".join((t.text or "") for t in si.iter(f"{NS}t")))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        sheets = []
        for sh in wb.findall(f"{NS}sheets/{NS}sheet"):
            target = rid[sh.attrib[REL]]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            root = ET.fromstring(zf.read(target))
            table = []
            for row in root.findall(f".//{NS}sheetData/{NS}row"):
                vals = {}
                for cell in row.findall(f"{NS}c"):
                    ref = cell.attrib.get("r", "")
                    col = "".join(ch for ch in ref if ch.isalpha())
                    n = 0
                    for ch in col:
                        n = n * 26 + ord(ch.upper()) - 64
                    if n < 1 or n > 80:
                        continue
                    kind = cell.attrib.get("t")
                    v = cell.find(f"{NS}v")
                    if kind == "s" and v is not None and v.text:
                        val = shared[int(v.text)]
                    elif v is not None and v.text:
                        val = v.text
                    else:
                        val = ""
                    vals[n - 1] = val
                if not vals:
                    continue
                width = max(vals) + 1
                table.append([vals.get(i, "") for i in range(width)])
            sheets.append((sh.attrib["name"], table))
    return sheets


def num(text):
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    if not s or s.lower() in {"na", "nan", "null", "-"}:
        return None
    try:
        value = float(s)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def age_flag(text):
    compact = text.lower().replace("-", "").replace(" ", "")
    if any(bad in compact for bad in ("juvenile", "fetus", "foetus", "embryo", "neonat", "subadult", "young")):
        return False
    low = text.lower()
    if "adult" in low or "mature" in low:
        return True
    return None


def sex_of(text):
    t = text.strip().lower()
    if t in {"f", "female"} or t.startswith("female"):
        return "f"
    if t in {"m", "male"} or t.startswith("male"):
        return "m"
    return None


def resolve(idx, *names):
    folded = {name.lower(): name for name in idx}
    for name in names:
        hit = folded.get(name.lower())
        if hit is not None:
            return hit
    return None


def cell(row, idx, name):
    if name is None or idx[name] >= len(row):
        return ""
    return row[idx[name]]


def species_key(row, idx):
    genus = cell(row, idx, resolve(idx, "Genus")).strip()
    species = cell(row, idx, resolve(idx, "Species")).strip()
    if genus and species:
        return (genus + " " + species.split()[0]).lower()
    combined = resolve(idx, "Genus_Species", "Genus_species")
    parts = cell(row, idx, combined).strip().replace("_", " ").split()
    if len(parts) >= 2:
        return (parts[0] + " " + parts[1]).lower()
    return None


def column_index(header):
    return {name.strip(): i for i, name in enumerate(header)}


def welch_p(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size < 2 or b.size < 2:
        return None
    if np.std(a) == 0 and np.std(b) == 0:
        return 0.0 if a.mean() != b.mean() else 1.0
    return float(stats.ttest_ind(a, b, equal_var=False).pvalue)


def absorb_sheet(table, clade, species_rows, deviations):
    if not table:
        return False
    idx = column_index(table[0])
    brain_col = resolve(idx, "Brain mass (g)", "Brain weight (g)")
    body_col = resolve(idx, "Body mass (g)", "Body weight (g)")
    if brain_col is None or body_col is None:
        return False
    if "weight" in brain_col.lower() or "weight" in body_col.lower():
        deviations.append(
            f"{clade}: the gram columns are '{brain_col}' and '{body_col}'. "
            "They are read as mass in grams. Brain volume (mm3) is not converted. Thresholds are unchanged."
        )
    combined = resolve(idx, "Genus_Species", "Genus_species")
    if combined and combined != "Genus_Species":
        deviations.append(
            f"{clade}: the combined name column is '{combined}', read as genus and species. Thresholds are unchanged."
        )
    age_col = resolve(idx, "Age Class")
    sex_col = resolve(idx, "Sex")
    for row in table[1:]:
        key = species_key(row, idx)
        if not key:
            continue
        brain = num(cell(row, idx, brain_col))
        body = num(cell(row, idx, body_col))
        if brain is None or body is None or brain <= 0 or not (0.05 < body < 2e8):
            continue
        ratio = brain / body
        if ratio >= 0.5:
            continue
        age = cell(row, idx, age_col)
        sex = cell(row, idx, sex_col)
        species_rows.setdefault(key, []).append({
            "clade": clade,
            "ratio": ratio,
            "brain": brain,
            "body": body,
            "age": age_flag(age),
            "sex": sex_of(sex),
        })
    return True


def settle_caveats(existing, additions):
    stale = (
        "has not been downloaded",
        "have not been re-hashed",
        "No brain or body mass value has been read",
        "No maturity value has been read",
        "No Camelus number has been read",
        "No age has been read",
        "No species habitat value has been read",
        "No body mass or litter size has been read",
    )
    kept = []
    for item in list(existing) + list(additions):
        if any(mark in item for mark in stale):
            continue
        if item not in kept:
            kept.append(item)
    return kept


def species_median(rows):
    adults = [r for r in rows if r["age"] is True]
    use = adults if adults else rows
    return float(np.median([r["ratio"] for r in use])), len(use), bool(adults)


def main():
    deviations = []
    file_meta = []
    for name, url, size, md5 in TSUBOI:
        file_meta.append(fetch(url, DATA / name, size, md5))
    burger_meta = None
    burger_error = None
    try:
        burger_meta = fetch(BURGER[1], DATA / BURGER[0], BURGER[2], BURGER[3])
    except Exception as exc:
        burger_error = str(exc)
        deviations.append(
            "The Burger et al. Dryad CSV was not retrieved. "
            "https://datadryad.org/api/v2/files/94072/download returned HTTP 401 "
            "(Unauthorized, must have current bearer token), and the public file-stream "
            "URL is behind an Anubis challenge that this client did not pass. "
            "The pre-registered rule treats a checksum failure of a received file as "
            "data-unavailable. No file was received, so there is no checksum to compare. "
            "The vertebrate test uses the Tsuboi workbooks, which were the primary dataset. "
            "The mammal replication and the Burger sex-clause fallback were not run."
        )

    species_rows = {}
    for meta in file_meta:
        sheets = read_xlsx(DATA / meta["name"])
        clade = meta["name"].replace("Tsuboi_etal_NEE_", "").replace(".xlsx", "")
        absorbed = False
        for _name, table in sheets:
            if absorb_sheet(table, clade, species_rows, deviations):
                absorbed = True
                break
        if not absorbed:
            headers = [table[0] for _, table in sheets if table]
            raise RuntimeError(f"{clade} has no brain and body gram columns; headers={headers}")

    medians = {}
    for key, rows in species_rows.items():
        med, n_use, used_adult = species_median(rows)
        medians[key] = {"median_ratio": med, "n_rows": n_use, "adult_only": used_adult, "clade": rows[0]["clade"]}

    human_key = "homo sapiens"
    human = medians.get(human_key)
    others = {k: v for k, v in medians.items() if k != human_key}
    n_other = len(others)

    clause_a = None
    n_at_or_above = None
    top = sorted(others.values(), key=lambda r: r["median_ratio"], reverse=True)[:8]
    top_named = sorted(others.items(), key=lambda kv: kv[1]["median_ratio"], reverse=True)[:8]
    if human is None:
        reason = "data-unavailable"
    elif n_other < 100:
        reason = "underpowered"
    else:
        reason = None
        n_at_or_above = sum(1 for v in others.values() if v["median_ratio"] >= human["median_ratio"])
        clause_a = n_at_or_above == 0

    # sex clause on adult human brain mass
    human_rows = species_rows.get(human_key, [])
    adults = [r for r in human_rows if r["age"] is True]
    pool = adults if adults else human_rows
    males = [r["brain"] for r in pool if r["sex"] == "m"]
    females = [r["brain"] for r in pool if r["sex"] == "f"]
    clause_b = None
    sex_stats = {"n_male": len(males), "n_female": len(females), "adult_pool": bool(adults)}
    if len(males) >= 10 and len(females) >= 10:
        mean_m = float(np.mean(males))
        mean_f = float(np.mean(females))
        rel = (mean_m - mean_f) / mean_f if mean_f else None
        p = welch_p(males, females)
        sex_stats.update({"mean_male_g": mean_m, "mean_female_g": mean_f, "relative_excess": rel, "welch_p": p})
        clause_b = bool(mean_m > mean_f and rel is not None and rel >= 0.05 and p is not None and p < 0.05)
    else:
        sex_stats["note"] = "fewer than 10 adult rows of one sex; Burger fallback unavailable"

    if clause_a is None:
        verdict = "inconclusive"
    elif clause_a and clause_b is True:
        verdict = "supports"
    elif clause_a is False and clause_b is not True:
        verdict = "refutes"
    else:
        verdict = "mixed"

    # secondary: encephalization residual on species medians of log brain and log body,
    # using the same rows that entered each species median. Not used for the verdict.
    eq = {}
    if human is not None and n_other >= 100:
        log_body = []
        log_brain = []
        keys = []
        for key, rows in species_rows.items():
            adults_r = [r for r in rows if r["age"] is True]
            use = adults_r if adults_r else rows
            log_body.append(math.log10(float(np.median([r["body"] for r in use]))))
            log_brain.append(math.log10(float(np.median([r["brain"] for r in use]))))
            keys.append(key)
        x = np.asarray(log_body)
        y = np.asarray(log_brain)
        fit = stats.linregress(x, y)
        resid = y - (fit.intercept + fit.slope * x)
        order = np.argsort(-resid)
        rank = int(np.where(np.array(keys) == human_key)[0][0])
        human_rank = int(np.where(order == rank)[0][0]) + 1
        eq = {
            "ols_slope": float(fit.slope),
            "ols_intercept": float(fit.intercept),
            "human_residual": float(resid[rank]),
            "human_residual_rank": human_rank,
            "n_species": len(keys),
            "used_for_verdict": False,
        }

    if verdict == "inconclusive":
        confidence = 0.4
    elif verdict == "refutes" and n_at_or_above is not None and n_at_or_above >= 10:
        confidence = 0.85
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "supports":
        confidence = 0.75
    else:
        confidence = 0.6

    human_ratio = None if human is None else human["median_ratio"]
    measured = {
        "value": human_ratio,
        "unit": "species-median brain mass / body mass, Homo sapiens",
        "n": n_other + (0 if human is None else 1),
        "uncertainty": None if n_at_or_above is None else f"{n_at_or_above} non-human species have a median ratio greater than or equal to the human median",
        "extra": {
            "clause_a_human_strictly_largest": clause_a,
            "clause_b_men_larger": clause_b,
            "n_nonhuman_species": n_other,
            "n_at_or_above_human": n_at_or_above,
            "human": human,
            "highest_nonhuman": [{"species": k, **v} for k, v in top_named],
            "sex": sex_stats,
            "encephalization_residual_not_used_for_verdict": eq,
        },
    }
    summary = []
    if human_ratio is not None:
        summary.append(
            f"Homo sapiens median brain/body ratio is {human_ratio:.6g} "
            f"across {human['n_rows']} rows (adult-only={human['adult_only']}), "
            f"compared with {n_other} other vertebrate species."
        )
    if n_at_or_above is not None:
        summary.append(
            f"{n_at_or_above} non-human species have a median ratio at least as high as the human median. "
            f"Clause A (largest in proportion to size) {'passes' if clause_a else 'fails'}."
        )
    if clause_b is None:
        summary.append(
            f"Sex clause not measured: {sex_stats['n_male']} adult male and {sex_stats['n_female']} adult female human brain-mass rows."
        )
    else:
        summary.append(
            f"Adult human brain mass mean {sex_stats['mean_male_g']:.4g} g (male, n={sex_stats['n_male']}) "
            f"versus {sex_stats['mean_female_g']:.4g} g (female, n={sex_stats['n_female']}), "
            f"relative excess {sex_stats['relative_excess']:.4f}, Welch p={sex_stats['welch_p']:.4g}. "
            f"Clause B {'passes' if clause_b else 'fails'}."
        )
    if eq:
        summary.append(
            f"Secondary, not used for the verdict: log-log OLS slope of brain on body is {eq['ols_slope']:.4f}; "
            f"the human residual ranks {eq['human_residual_rank']} of {eq['n_species']}."
        )

    datasets = [{
        "id": "tsuboi-2018-figshare-6803276",
        "name": "Brain mass and body mass datasets for amphibians, birds, mammals, reptiles, sharks and rays, and teleosts (Tsuboi et al.)",
        "landing_url": "https://doi.org/10.6084/m9.figshare.6803276.v1",
        "doi": "10.6084/m9.figshare.6803276.v1",
        "version": "v1",
        "license": "CC0",
        "files": file_meta,
        "role": "brain mass, body mass, sex, and age class for vertebrate species",
    }]
    if burger_meta:
        datasets.append({
            "id": "burger-2019-dryad-2r62k7s",
            "name": "Data from: The allometry of brain size in mammals",
            "landing_url": "https://doi.org/10.5061/dryad.2r62k7s",
            "doi": "10.5061/dryad.2r62k7s",
            "version": "2019-05-08",
            "license": "CC0",
            "files": [burger_meta],
            "role": "mammal replication; not used because the download did not succeed" if burger_error else "mammal replication",
        })

    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["datasets"] = datasets
    result["method"] = (
        "Downloaded the six Tsuboi class workbooks and checked each MD5 and byte size against the registration. "
        "For each species the median brain-mass/body-mass ratio was taken on adult rows when any adult row existed, otherwise on all rows with brain mass > 0, body mass between 0.05 g and 2e8 g, and ratio < 0.5. "
        "Homo sapiens was compared with every other species. Adult male and female human brain masses were compared with a Welch t-test. "
        "An allometric residual was computed and stored and was not used for the verdict. The Burger CSV was not retrieved."
    )
    result["measured"] = measured
    result["verdict"] = verdict
    result["data_kind"] = "none" if verdict == "inconclusive" and reason == "data-unavailable" and human is None else "biological"
    result["confidence"] = confidence
    result["results_summary"] = summary
    if reason:
        result["reason"] = reason
    if deviations:
        result["deviations"] = deviations
    result["caveats"] = settle_caveats(result.get("caveats", []), [
        "Species medians give equal weight to a species with one row and a species with many rows.",
        "The ratio cut at 0.5 drops rows in which the recorded brain mass is at least half the body mass; those rows are treated as unit or entry errors.",
        "Age class 'Young adult' contains the word young and is excluded from the adult pool by the pre-registered rule. 'Sub-adult' is treated as subadult.",
        "Clause A uses the raw brain/body ratio. The allometric residual, which can rank Homo sapiens first, is stored and does not enter the verdict.",
    ])
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    payload = {"verdict": verdict, "reason": reason, "measured": measured, "sex": sex_stats, "encephalization": eq}
    (DERIVED / "measured.json").write_text(json.dumps(payload, indent=2) + "\n")
    print(verdict, reason, "human", human_ratio, "n_other", n_other, "at_or_above", n_at_or_above, "clause_b", clause_b)


if __name__ == "__main__":
    main()
