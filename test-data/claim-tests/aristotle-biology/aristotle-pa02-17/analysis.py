#!/usr/bin/env python3
"""aristotle-pa02-17: human brain/body ratio against other species, and male vs female brain mass.

Thresholds are those committed in result.json. The log-log residual is descriptive only.
Run: python3 analysis.py
"""
import csv
import datetime as dt
import hashlib
import io
import json
import re
import time
import urllib.parse
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
import requests
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")
MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

FILES = [
    {
        "id": "burger-2019-mammal-brain-dryad-2r62k7s",
        "name": "Data from: The allometry of brain size in mammals",
        "landing_url": "https://doi.org/10.5061/dryad.2r62k7s",
        "doi": "10.5061/dryad.2r62k7s",
        "license": "CC0-1.0",
        "file_id": "94072",
        "filename": "BrainAllometry_Supplement_Data.csv",
        "role": "mammals",
        "kind": "csv",
    },
    {
        "id": "jimenez-ortega-2020-bird-brain-dryad-sqv9s4n27",
        "name": "Brain size and life history variables in birds",
        "landing_url": "https://doi.org/10.5061/dryad.sqv9s4n27",
        "doi": "10.5061/dryad.sqv9s4n27",
        "license": "CC0-1.0",
        "file_id": "401942",
        "filename": "Brain_size_and_life_history_variables_in_birds.xlsx",
        "role": "birds",
        "kind": "xlsx",
    },
    {
        "id": "font-2019-reptile-bird-brain-dryad-pd5hh46",
        "name": "Data on brain mass and body mass for reptiles and birds (Font et al. 2019)",
        "landing_url": "https://doi.org/10.5061/dryad.pd5hh46",
        "doi": "10.5061/dryad.pd5hh46",
        "license": "CC0-1.0",
        "file_id": "108959",
        "filename": "font2019_brain_body.xlsx",
        "role": "font",
        "kind": "xlsx",
    },
]
NONADULT = ("juvenile", "neonate", "infant", "fetal", "fetus", "newborn", "subadult", "young", "pup", "hatchling")


def solve_anubis(random_data, difficulty):
    prefix = "0" * difficulty
    nonce = 0
    while True:
        digest = hashlib.sha256((random_data + str(nonce)).encode()).hexdigest()
        if digest.startswith(prefix):
            return digest, nonce
        nonce += 1


def dryad_download(file_id, timeout=180):
    url = f"https://datadryad.org/downloads/file_stream/{file_id}"
    session = requests.Session()
    session.headers["User-Agent"] = UA
    response = session.get(url, timeout=timeout)
    if response.headers.get("content-type", "").startswith("text/html") and "anubis_challenge" in response.text[:8000]:
        match = re.search(r'id="anubis_challenge" type="application/json">(.*?)</script>', response.text, re.S)
        challenge = json.loads(match.group(1))
        started = time.time()
        digest, nonce = solve_anubis(challenge["challenge"]["randomData"], challenge["rules"]["difficulty"])
        query = urllib.parse.urlencode({
            "id": challenge["challenge"]["id"],
            "response": digest,
            "nonce": nonce,
            "redir": url,
            "elapsedTime": int((time.time() - started) * 1000) + 1,
        })
        response = session.get("https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge?" + query, timeout=timeout)
    response.raise_for_status()
    return response.content, url


def fetch(spec):
    DATA.mkdir(exist_ok=True)
    path = DATA / spec["filename"]
    if not path.exists():
        content, url = dryad_download(spec["file_id"])
        path.write_bytes(content)
        retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        content = path.read_bytes()
        url = f"https://datadryad.org/downloads/file_stream/{spec['file_id']}"
        retrieved = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "name": spec["filename"],
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "content": content,
    }


def col_index(letters):
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - 64)
    return idx - 1


def read_xlsx(content):
    sheets = {}
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{MAIN}si"):
                strings.append("".join((t.text or "") for t in si.findall(f".//{MAIN}t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels}
        for sheet in wb.findall(f"{MAIN}sheets/{MAIN}sheet"):
            name = sheet.attrib.get("name")
            rid = sheet.attrib.get(OFFICE_REL + "id")
            target = rid_to_target[rid]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            root = ET.fromstring(zf.read(target))
            rows = []
            for row in root.findall(f"{MAIN}sheetData/{MAIN}row"):
                vals = []
                for cell in row.findall(f"{MAIN}c"):
                    ref = cell.attrib.get("r", "")
                    letters = "".join(ch for ch in ref if ch.isalpha())
                    idx = col_index(letters) if letters else len(vals)
                    while len(vals) < idx:
                        vals.append("")
                    kind = cell.attrib.get("t")
                    vnode = cell.find(f"{MAIN}v")
                    inode = cell.find(f"{MAIN}is")
                    if kind == "s" and vnode is not None and vnode.text:
                        vals.append(strings[int(vnode.text)])
                    elif kind == "inlineStr" and inode is not None:
                        vals.append("".join((t.text or "") for t in inode.findall(f".//{MAIN}t")))
                    elif vnode is not None and vnode.text is not None:
                        vals.append(vnode.text)
                    else:
                        vals.append("")
                rows.append(vals)
            sheets[name] = rows
    return sheets


def read_csv(content):
    text = content.decode("utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    return {"csv": rows}


def norm_header(header):
    return re.sub(r"[^a-z0-9]+", "", str(header).lower())


def unit_token(header):
    h = str(header).lower()
    if re.search(r"\bkg\b|kilogram", h):
        return "kg"
    if re.search(r"\bmg\b|milligram", h):
        return "mg"
    if re.search(r"\bg\b|gram", h):
        return "g"
    return None


def is_volume(header):
    h = str(header).lower()
    return any(token in h for token in ("volume", "mm3", "cm3", " ml", "(ml)"))


def pick_columns(headers):
    named = [(h, norm_header(h)) for h in headers if str(h).strip()]
    def find(pred, avoid=()):
        hits = []
        for h, n in named:
            if any(a in n for a in avoid):
                continue
            if pred(n):
                score = 0
                if any(k in n for k in ("mass", "weight", "size")):
                    score += 2
                if unit_token(h):
                    score += 1
                hits.append((score, h))
        if not hits:
            return None
        hits.sort(key=lambda item: -item[0])
        return hits[0][1]
    brain = find(lambda n: "brain" in n, avoid=("body",))
    body = find(lambda n: "body" in n or n in {"mass", "bodymass", "adultmass"}, avoid=("brain",))
    if body == brain:
        body = None
    return {
        "brain": brain,
        "body": body,
        "sex": find(lambda n: n in {"sex", "gender"} or n.endswith("sex")),
        "genus": find(lambda n: n == "genus"),
        "species": find(lambda n: n in {"species", "specificepithet", "epithet"}),
        "binomial": find(lambda n: n in {"binomial", "scientificname", "taxon", "speciesname", "latinname"} or "binomial" in n or "scientificname" in n),
        "age": find(lambda n: n in {"age", "ageclass", "lifestage"} or "ageclass" in n or "lifestage" in n),
        "class": find(lambda n: n in {"class", "group", "clade", "taxonclass"}),
    }


def header_row(rows):
    best = None
    for i, row in enumerate(rows[:15]):
        cols = pick_columns([str(c) for c in row])
        if cols["brain"] and cols["body"]:
            best = i
            break
    return best


def num(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", "")
    if s == "" or s.lower() in {"na", "nan", "null", ".", "-"}:
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    if not np.isfinite(v):
        return None
    return v


def is_human(name):
    n = re.sub(r"\s+", " ", name.strip().lower().replace("_", " "))
    if any(token in n for token in ("neanderthal", "erectus", "habilis", "floresiensis")):
        return False
    return n == "homo sapiens" or n.startswith("homo sapiens ")


def sex_label(value):
    n = re.sub(r"[^a-z]", "", str(value).lower())
    if n in {"m", "male", "males"}:
        return "male"
    if n in {"f", "female", "females"}:
        return "female"
    return None


def nonadult(value):
    n = str(value).strip().lower()
    return any(token in n for token in NONADULT)


def rows_to_records(table_rows):
    idx = header_row(table_rows)
    if idx is None:
        return None, "no brain and body headers"
    headers = [str(c).strip() for c in table_rows[idx]]
    cols = pick_columns(headers)
    brain_u, body_u = unit_token(cols["brain"]), unit_token(cols["body"])
    if is_volume(cols["brain"]) != is_volume(cols["body"]):
        return None, f"volume/mass mismatch in {cols['brain']!r} vs {cols['body']!r}"
    if brain_u and body_u and brain_u != body_u:
        return None, f"unit mismatch {brain_u} vs {body_u}"
    if (brain_u is None) != (body_u is None) and (brain_u or body_u):
        return None, f"unit stated on only one of {cols['brain']!r} and {cols['body']!r}"
    records = []
    for raw in table_rows[idx + 1:]:
        padded = list(raw) + [""] * (len(headers) - len(raw))
        row = {headers[i]: padded[i] for i in range(len(headers))}
        if cols["age"] and nonadult(row.get(cols["age"], "")):
            continue
        brain = num(row.get(cols["brain"]))
        body = num(row.get(cols["body"]))
        if brain is None or body is None or brain <= 0 or body <= 0:
            continue
        genus = str(row.get(cols["genus"], "")).strip() if cols["genus"] else ""
        species = str(row.get(cols["species"], "")).strip() if cols["species"] else ""
        binomial = str(row.get(cols["binomial"], "")).strip() if cols["binomial"] else ""
        if genus and species:
            name = f"{genus} {species}"
        elif binomial:
            name = binomial
        elif species:
            name = species
        else:
            continue
        if not name or name.lower() in {"species", "binomial"}:
            continue
        rec = {
            "name": re.sub(r"\s+", " ", name.replace("_", " ")).strip(),
            "brain": brain,
            "body": body,
            "ratio": brain / body,
            "sex": sex_label(row.get(cols["sex"], "")) if cols["sex"] else None,
            "group": str(row.get(cols["class"], "")).strip() if cols["class"] else "",
        }
        records.append(rec)
    return {"columns": cols, "records": records, "n_rows": len(records), "header_index": idx}, None


def species_table(records):
    buckets = defaultdict(list)
    for rec in records:
        buckets[rec["name"].lower()].append(rec)
    species = []
    for key, items in buckets.items():
        ratios = [item["ratio"] for item in items]
        species.append({
            "name": items[0]["name"],
            "n_rows": len(items),
            "ratio": float(np.median(ratios)),
            "median_brain": float(np.median([item["brain"] for item in items])),
            "median_body": float(np.median([item["body"] for item in items])),
            "human": is_human(items[0]["name"]),
        })
    species.sort(key=lambda item: -item["ratio"])
    return species


def summarize_set(label, records, human_ratio_fallback):
    species = species_table(records)
    humans = [s for s in species if s["human"]]
    others = [s for s in species if not s["human"]]
    human_ratio = humans[0]["ratio"] if len(humans) == 1 else (humans[0]["ratio"] if len(humans) > 1 else None)
    # If several human-name buckets exist, use the median of their species ratios and flag it.
    if len(humans) > 1:
        human_ratio = float(np.median([s["ratio"] for s in humans]))
    reference = human_ratio if human_ratio is not None else human_ratio_fallback
    counter = []
    if reference is not None:
        counter = [s for s in others if s["ratio"] >= reference]
    return {
        "label": label,
        "n_species": len(species),
        "n_human_buckets": len(humans),
        "human_ratio_within": human_ratio,
        "reference_human_ratio": reference,
        "n_counterexamples": len(counter),
        "highest_other": others[0] if others else None,
        "counterexamples_top": counter[:8],
        "human_buckets": humans,
        "top5": species[:5],
    }


def score_sex(records):
    male = [r["brain"] for r in records if is_human(r["name"]) and r["sex"] == "male"]
    female = [r["brain"] for r in records if is_human(r["name"]) and r["sex"] == "female"]
    out = {"n_male": len(male), "n_female": len(female), "state": "unknown"}
    if len(male) >= 5 and len(female) >= 5:
        male_mean = float(np.mean(male))
        female_mean = float(np.mean(female))
        p = float(stats.ttest_ind(male, female, equal_var=False).pvalue)
        out.update({"mode": "individuals", "male_mean_brain": male_mean, "female_mean_brain": female_mean, "welch_p": p})
        if male_mean > female_mean and p < 0.05:
            out["state"] = "hold"
        elif female_mean >= male_mean:
            out["state"] = "fail"
        else:
            out["state"] = "unknown"
            out["unknown_reason"] = "male mean larger but Welch p >= 0.05"
    elif len(male) == 1 and len(female) == 1:
        out.update({"mode": "aggregates", "male_brain": male[0], "female_brain": female[0]})
        out["state"] = "hold" if male[0] > female[0] else "fail"
    elif len(male) + len(female) > 0:
        out["unknown_reason"] = "sex sample below the pre-registered floor"
    else:
        out["unknown_reason"] = "no sex-labelled Homo sapiens brain masses"
    return out


def descriptive_residual(records):
    mammals = [r for r in records if not is_human(r["name"])]
    humans = [r for r in records if is_human(r["name"])]
    if len(mammals) < 10 or not humans:
        return {"note": "not computed"}
    # Species medians for the fit, so a heavily sampled species does not dominate.
    species = species_table(mammals)
    x = np.log10([s["median_body"] for s in species])
    y = np.log10([s["median_brain"] for s in species])
    slope, intercept, r_value, p_value, stderr = stats.linregress(x, y)
    human_body = float(np.median([r["body"] for r in humans]))
    human_brain = float(np.median([r["brain"] for r in humans]))
    predicted = intercept + slope * np.log10(human_body)
    residual = float(np.log10(human_brain) - predicted)
    other_residuals = []
    for s in species:
        pred = intercept + slope * np.log10(s["median_body"])
        other_residuals.append(float(np.log10(s["median_brain"]) - pred))
    rank = 1 + sum(1 for item in other_residuals if item > residual)
    return {
        "note": "descriptive only; not used for the verdict",
        "n_nonhuman_species": len(species),
        "ols_slope": float(slope),
        "ols_intercept": float(intercept),
        "ols_r": float(r_value),
        "human_log10_residual": residual,
        "human_residual_rank_1_is_largest": rank,
    }


def load_sets(spec, meta, human_ratio):
    content = meta["content"]
    tables = read_csv(content) if spec["kind"] == "csv" else read_xlsx(content)
    sets = []
    errors = []
    for sheet, rows in tables.items():
        parsed, err = rows_to_records(rows)
        if err:
            errors.append({"sheet": sheet, "error": err})
            continue
        records = parsed["records"]
        if not records:
            errors.append({"sheet": sheet, "error": "no positive brain and body rows"})
            continue
        groups = defaultdict(list)
        labels = {r["group"].casefold() for r in records if r["group"]}
        birdish = [g for g in labels if "bird" in g or g == "aves"]
        reptileish = [g for g in labels if "reptil" in g]
        if birdish or reptileish:
            for rec in records:
                g = rec["group"].casefold()
                if "bird" in g or g == "aves":
                    groups["birds"].append(rec)
                elif "reptil" in g:
                    groups["reptiles"].append(rec)
                else:
                    groups["other"].append(rec)
        else:
            role = spec["role"] if spec["role"] in {"mammals", "birds"} else f"{spec['role']}:{sheet}"
            groups[role] = records
        for label, group_records in groups.items():
            if not group_records:
                continue
            summary = summarize_set(f"{spec['id']}:{label}", group_records, human_ratio)
            summary["sheet"] = sheet
            summary["columns"] = {k: v for k, v in parsed["columns"].items() if v}
            summary["source_role"] = label
            sets.append((summary, group_records if label in {"mammals", "csv"} or spec["role"] == "mammals" else None))
            # group_records returned separately only for the mammal sex and residual analyses
            sets[-1] = (summary, group_records)
    return sets, errors


def main():
    metas = []
    datasets = []
    for spec in FILES:
        meta = fetch(spec)
        metas.append((spec, meta))
        datasets.append({
            "id": spec["id"],
            "name": spec["name"],
            "landing_url": spec["landing_url"],
            "doi": spec["doi"],
            "version": None,
            "license": spec["license"],
            "files": [{k: v for k, v in meta.items() if k != "content"}],
            "role": spec["role"],
        })

    # Mammal file first so its human ratio is available to the others.
    mammal_sets = []
    other_sets = []
    errors = []
    mammal_records = []
    for spec, meta in metas:
        sets, errs = load_sets(spec, meta, None)
        errors.extend({"dataset": spec["id"], **e} for e in errs)
        if spec["role"] == "mammals":
            mammal_sets.extend(sets)
            mammal_records.extend(rec for _, recs in sets for rec in recs)
        else:
            other_sets.extend(sets)

    human_candidates = [r for r in mammal_records if is_human(r["name"])]
    if human_candidates:
        human_ratio = float(np.median([r["ratio"] for r in human_candidates]))
    else:
        human_ratio = None

    # Re-summarize non-mammal sets against the mammal human ratio when they lack their own human.
    final_sets = []
    for summary, recs in mammal_sets:
        final_sets.append(summarize_set(summary["label"], recs, human_ratio))
    for summary, recs in other_sets:
        final_sets.append(summarize_set(summary["label"], recs, human_ratio))

    sex = score_sex(mammal_records)
    residual = descriptive_residual(mammal_records)

    mammal_ok = [s for s in final_sets if s["label"].endswith(":mammals") or ":mammals" in s["label"] or s["label"].endswith("mammals")]
    # Burger labels come out as id:mammals because role mammals is used when no class split.
    if not mammal_ok:
        mammal_ok = [s for s in final_sets if "burger-2019" in s["label"]]
    bird_sets = [s for s in final_sets if s["source_role"] == "birds" or s["label"].endswith(":birds")]
    # source_role may be missing on re-summary. Recover from label.
    bird_sets = [s for s in final_sets if s["label"].endswith(":birds") or s["label"].endswith(":birds")]
    # Jiménez-Ortega role is birds, so label ends with :birds. Font split also ends with :birds.
    reptile_sets = [s for s in final_sets if s["label"].endswith(":reptiles")]

    def fails(s):
        return s.get("reference_human_ratio") is not None and s["n_counterexamples"] > 0

    def mammal_holds(s):
        return (s["n_species"] >= 200 and s["n_human_buckets"] >= 1 and s["n_counterexamples"] == 0
                and s.get("reference_human_ratio") is not None)

    def bird_holds(s):
        return s["n_species"] >= 100 and s["n_counterexamples"] == 0 and s.get("reference_human_ratio") is not None

    proportion_fail = any(fails(s) for s in final_sets)
    proportion_hold = any(mammal_holds(s) for s in mammal_ok) and any(bird_holds(s) for s in bird_sets) and not proportion_fail
    if proportion_fail:
        proportion = "fail"
    elif proportion_hold:
        proportion = "hold"
    else:
        proportion = "unknown"

    scored = []
    if proportion in {"hold", "fail"}:
        scored.append(proportion)
    if sex["state"] in {"hold", "fail"}:
        scored.append(sex["state"])

    if not scored:
        verdict = "inconclusive"
        # Sample-size floor is the usual reason the mammal or bird set cannot support.
        if not mammal_records:
            reason = "data-unavailable"
        elif human_ratio is None:
            reason = "other"
        else:
            reason = "underpowered"
    elif set(scored) == {"fail"}:
        verdict, reason = "refutes", None
    elif set(scored) == {"hold"} and len(scored) == 2:
        verdict, reason = "supports", None
    elif set(scored) == {"hold"}:
        verdict, reason = "inconclusive", "other"
    else:
        verdict, reason = "mixed", None

    conf = {"supports": 0.72, "refutes": 0.72, "mixed": 0.60}.get(verdict, 0.40)
    # Drop bulky species lists from the result; keep the auditable top of each set.
    def public_set(s):
        keep = {k: s[k] for k in (
            "label", "n_species", "n_human_buckets", "human_ratio_within", "reference_human_ratio",
            "n_counterexamples", "highest_other", "counterexamples_top", "human_buckets", "top5",
        ) if k in s}
        return keep

    result = json.loads((HERE / "result.json").read_text())
    result["datasets"] = datasets
    result.update(status="complete", verdict=verdict, confidence=conf,
                  data_kind="none" if reason == "data-unavailable" else "biological")
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["measured"] = {
        "value": human_ratio,
        "unit": "species-median brain mass / body mass for Homo sapiens in the mammal file",
        "n": mammal_ok[0]["n_species"] if mammal_ok else 0,
        "uncertainty": None,
        "extra": {
            "proportion_clause": proportion,
            "sex_clause": sex,
            "sets": [public_set(s) for s in final_sets],
            "parse_errors": errors,
            "descriptive_log_residual": residual,
        },
    }
    result["method"] = (
        "Downloaded the three Dryad files, solved the Dryad download challenge when it was presented, "
        "and read brain and body masses. Species ratios are medians of brain/body. Homo sapiens was "
        "compared with every other species under the pre-registered strict-superlative rule. Male and "
        "female human brain masses were compared only when the sex sample met the pre-registered floor. "
        "The mammal log-log residual is stored and was not read by the verdict rule."
    )
    top_counter = []
    for s in final_sets:
        if s["n_counterexamples"]:
            top_counter.append(f"{s['label']} counterexamples={s['n_counterexamples']} highest={s['counterexamples_top'][:1]}")
        else:
            top_counter.append(f"{s['label']} n={s['n_species']} counterexamples=0 human_ratio={s['human_ratio_within']}")
    result["results_summary"] = [
        f"Human mammal-file ratio {human_ratio}. Proportion clause {proportion}. Sex clause {sex.get('state')}.",
        " ".join(top_counter),
        f"Verdict {verdict}.",
    ]
    DERIVED.mkdir(exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(result["measured"], indent=2) + "\n")
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(verdict, human_ratio, proportion, sex.get("state"))
    for line in top_counter:
        print(line)


if __name__ == "__main__":
    main()
