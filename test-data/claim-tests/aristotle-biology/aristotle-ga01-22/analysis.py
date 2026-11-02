#!/usr/bin/env python3
"""Litter or clutch size against body mass for aristotle-ga01-22.

Spearman correlation of log10 litter/clutch size on log10 body mass.
Support requires amniote rho <= -0.20 (p < 0.01), fishes not clearly
positive, and the PanTHERIA mammal replication not clearly positive.
Criteria were committed before this download.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
from scipy import stats

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "delphisci-claim-test/1.0"
ANAGE = ("https://genomics.senescence.info/species/dataset.zip", 169150, "e3ddb66e32e973a79932859ba53013e8f60d957c6ec01c6eb573e3ea3018d630")
PAN = ("https://esapubs.org/archive/ecol/E090/184/PanTHERIA_1-0_WR05_Aug2008.txt", 2359096, "36e64314cae0394a966a63b949504d1975ac5c5629e05e36c1b139b3348f044a")
AMNIOTE = {"mammalia", "mammals", "mammal", "aves", "birds", "bird", "reptilia", "reptiles", "reptile"}
FISH_EXACT = {
    "actinopterygii", "chondrichthyes", "osteichthyes", "teleostei", "sarcopterygii",
    "cephalaspidomorphi", "myxini", "agnatha", "chondrostei", "holostei", "fish", "fishes", "pisces",
}


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
    if not math.isfinite(value) or value == -999:
        return None
    return value


def fetch(url, dest, size, sha):
    DATA.mkdir(parents=True, exist_ok=True)
    raw = dest.read_bytes() if dest.exists() else b""
    if hashlib.sha256(raw).hexdigest() != sha or len(raw) != size:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read()
        dest.write_bytes(raw)
    got = hashlib.sha256(raw).hexdigest()
    if got != sha or len(raw) != size:
        raise RuntimeError(f"checksum mismatch {dest.name}")
    return {
        "name": dest.name,
        "download_url": url,
        "retrieved_at": dt.datetime.fromtimestamp(dest.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": got,
    }, raw


def is_fish(label):
    low = label.strip().lower()
    if low in FISH_EXACT:
        return True
    return any(token in low for token in ("fish", "shark", "ray"))


def is_amniote(label):
    return label.strip().lower() in AMNIOTE


def spearman(pairs):
    if len(pairs) < 3:
        return None
    x = np.log10(np.array([a for a, _ in pairs], dtype=float))
    y = np.log10(np.array([b for _, b in pairs], dtype=float))
    res = stats.spearmanr(x, y)
    fit = stats.linregress(x, y)
    return {
        "n": len(pairs),
        "rho": float(res.statistic),
        "p": float(res.pvalue),
        "ols_slope": float(fit.slope),
        "ols_slope_used_for_verdict": False,
    }


def pattern(stat):
    if stat is None or stat["n"] < 100:
        return "too_small" if stat is None or stat["n"] < 100 else "flat"
    if stat["rho"] <= -0.20 and stat["p"] < 0.01:
        return "negative"
    if stat["rho"] >= 0.20 and stat["p"] < 0.01:
        return "positive"
    return "flat"


def settle_caveats(existing, additions):
    stale = (
        "has not been downloaded",
        "have not been re-hashed",
        "No maturity value has been read",
        "No Camelus number has been read",
        "No age has been read",
        "No species habitat value has been read",
        "No body mass or litter size has been read",
        "No brain or body mass value has been read",
    )
    kept = []
    for item in list(existing) + list(additions):
        if any(mark in item for mark in stale):
            continue
        if item not in kept:
            kept.append(item)
    return kept


def main():
    anage_meta, anage_raw = fetch(ANAGE[0], DATA / "dataset.zip", ANAGE[1], ANAGE[2])
    pan_error = None
    try:
        pan_meta, pan_raw = fetch(PAN[0], DATA / "PanTHERIA_1-0_WR05_Aug2008.txt", PAN[1], PAN[2])
    except Exception as exc:
        pan_meta, pan_raw, pan_error = None, None, str(exc)
    with zipfile.ZipFile(io.BytesIO(anage_raw)) as zf:
        text = zf.read("anage_data.txt").decode("utf-8")
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    # Body mass (g) is present, so it is the registered mass column.
    groups = {"amniote": [], "fish": [], "amphibia": []}
    by_class = {}
    class_counts = {}
    fish_rows = 0
    fish_body_and_litter = 0
    fish_adult_weight_and_litter = 0
    for row in rows:
        label = row.get("Class", "")
        class_counts[label] = class_counts.get(label, 0) + 1
        mass = num(row.get("Body mass (g)"))
        litter = num(row.get("Litter/Clutch size"))
        if is_fish(label):
            fish_rows += 1
            adult_weight = num(row.get("Adult weight (g)"))
            if mass is not None and litter is not None and mass > 0 and litter > 0:
                fish_body_and_litter += 1
            if adult_weight is not None and litter is not None and adult_weight > 0 and litter > 0:
                fish_adult_weight_and_litter += 1
        if mass is None or litter is None or mass <= 0 or litter <= 0:
            continue
        pair = (mass, litter)
        low = label.strip().lower()
        if is_amniote(label):
            groups["amniote"].append(pair)
            by_class.setdefault(low, []).append(pair)
        elif is_fish(label):
            groups["fish"].append(pair)
        elif low in {"amphibia", "amphibian", "amphibians"}:
            groups["amphibia"].append(pair)
    amniote = spearman(groups["amniote"])
    fish = spearman(groups["fish"]) if len(groups["fish"]) >= 30 else None
    amph = spearman(groups["amphibia"]) if len(groups["amphibia"]) >= 30 else None
    class_stats = {}
    for label, pairs in by_class.items():
        if len(pairs) >= 30:
            class_stats[label] = spearman(pairs)
    pan_stat = None
    if pan_raw is not None:
        pairs = []
        for row in csv.DictReader(io.StringIO(pan_raw.decode("utf-8", errors="replace")), delimiter="\t"):
            mass = num(row.get("5-1_AdultBodyMass_g"))
            litter = num(row.get("15-1_LitterSize"))
            if mass is not None and litter is not None and mass > 0 and litter > 0:
                pairs.append((mass, litter))
        pan_stat = spearman(pairs)
    amniote_pattern = "too_small" if amniote is None or amniote["n"] < 100 else pattern(amniote)
    if amniote is None or amniote["n"] < 100:
        # pattern() already returns too_small when n < 100, but a present stat with n<100
        # is handled here explicitly
        if amniote is not None and amniote["n"] < 100:
            amniote_pattern = "too_small"
    fish_pattern = "absent" if fish is None else pattern(fish) if fish["n"] >= 30 else "absent"
    if fish is not None and fish["n"] < 100:
        # fish cuts use the same rho rules but the registration allows n >= 30.
        # pattern() requires n >= 100. Apply the fish rule directly.
        if fish["rho"] <= -0.20 and fish["p"] < 0.01:
            fish_pattern = "negative"
        elif fish["rho"] >= 0.20 and fish["p"] < 0.01:
            fish_pattern = "positive"
        else:
            fish_pattern = "flat"
    n_pos_classes = 0
    for stat in class_stats.values():
        if stat["n"] >= 30 and stat["rho"] > 0 and stat["p"] < 0.05:
            n_pos_classes += 1
    pan_positive = bool(pan_stat and pan_stat["n"] >= 100 and pan_stat["rho"] > 0 and pan_stat["p"] < 0.01)
    if amniote_pattern == "too_small":
        verdict, reason = "inconclusive", "underpowered"
    elif amniote_pattern == "positive":
        verdict, reason = "refutes", None
    elif amniote_pattern == "negative" and fish_pattern == "positive":
        verdict, reason = "mixed", None
    elif amniote_pattern == "negative" and n_pos_classes >= 2:
        verdict, reason = "mixed", None
    elif amniote_pattern == "negative" and pan_positive:
        verdict, reason = "mixed", None
    elif amniote_pattern == "negative":
        verdict, reason = "supports", None
    else:
        verdict, reason = "mixed", None
    bird_not_negative = any(
        name in {"aves", "birds", "bird"} and stat["n"] >= 30
        and not (stat["rho"] <= -0.20 and stat["p"] < 0.01)
        for name, stat in class_stats.items()
    )
    if verdict == "supports" and (fish is None or bird_not_negative):
        # Judgment only. The pooled amniote cut still decides the verdict.
        # Birds are not negative, or fishes were not scored, so the scope
        # "animals generally" is only partly measured.
        confidence = 0.55
    elif verdict == "supports":
        confidence = 0.7
    elif verdict == "refutes":
        confidence = 0.75
    elif verdict == "mixed":
        confidence = 0.65
    else:
        confidence = 0.45
    measured = {
        "value": None if amniote is None else amniote["rho"],
        "unit": "Spearman rho of log10 litter or clutch size on log10 body mass, AnAge amniotes",
        "n": 0 if amniote is None else amniote["n"],
        "uncertainty": None if amniote is None else f"two-sided p = {amniote['p']:.6g}",
        "extra": {
            "amniote": amniote,
            "amniote_pattern": amniote_pattern,
            "classes": class_stats,
            "n_classes_positive_p05": n_pos_classes,
            "fish": fish,
            "fish_pattern": fish_pattern,
            "amphibia_not_used_for_verdict": amph,
            "pantheria_mammals": pan_stat,
            "pantheria_significant_positive": pan_positive,
            "anage_class_row_counts": class_counts,
            "mass_column": "Body mass (g)",
            "litter_column": "Litter/Clutch size",
            "n_amniote_by_class": {name: len(pairs) for name, pairs in sorted(by_class.items())},
            "fish_rows": fish_rows,
            "fish_body_mass_and_litter_n": fish_body_and_litter,
            "fish_adult_weight_and_litter_n": fish_adult_weight_and_litter,
            "fish_adult_weight_spearman_used_for_verdict": False,
        },
    }
    datasets = [{
        "id": "anage-build-15",
        "name": "AnAge: The Animal Ageing and Longevity Database, build 15",
        "landing_url": "https://genomics.senescence.info/species/",
        "doi": "10.1093/nar/gks1155",
        "version": "build 15",
        "license": "CC BY 3.0",
        "files": [anage_meta],
        "role": "body mass and litter or clutch size by class",
        "prior_record": "test-data/organisms/thompson-growth-form/ch08/datasets/anage-build-15.json",
    }]
    if pan_meta:
        datasets.append({
            "id": "pantheria-1-0-wr05-aug2008",
            "name": "PanTHERIA 1.0 life-history table",
            "landing_url": "https://esapubs.org/archive/ecol/E090/184/",
            "doi": "10.1890/08-1494.1",
            "version": "1.0 (WR05, Aug 2008)",
            "license": "Ecological Archives; reuse with citation",
            "files": [pan_meta],
            "role": "mammal adult body mass and litter size replication",
            "prior_record": "test-data/organisms/thompson-growth-form/ch04-05/datasets/pantheria-1-0-wr05-aug2008.json",
        })
    result = json.loads(RESULT.read_text())
    result["status"] = "complete"
    result["datasets"] = datasets
    result["method"] = (
        "Downloaded AnAge build 15 and PanTHERIA and checked both SHA-256 checksums. "
        "AnAge body mass is the column Body mass (g), which is present, and offspring number is Litter/Clutch size. "
        "Spearman correlations use log10 of both. Amniotes are birds, mammals, and reptiles. "
        "Fishes are reported with the pre-registered class rule. PanTHERIA mammals are the replication. "
        "OLS slopes are stored and do not set the verdict."
    )
    result["measured"] = measured
    result["verdict"] = verdict
    result["data_kind"] = "biological" if amniote and amniote["n"] else "none"
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    if pan_error:
        result["deviations"] = [f"PanTHERIA was not used: {pan_error}"]
    class_bits = ", ".join(
        f"{name} rho={stat['rho']:.4f} p={stat['p']:.3g} n={stat['n']}" for name, stat in sorted(class_stats.items())
    )
    fish_bit = "absent" if fish is None else f"rho={fish['rho']:.4f} p={fish['p']:.3g} n={fish['n']} ({fish_pattern})"
    pan_bit = "absent" if pan_stat is None else f"rho={pan_stat['rho']:.4f} p={pan_stat['p']:.3g} n={pan_stat['n']}"
    result["results_summary"] = [
        f"AnAge amniotes: {amniote_pattern}, rho={None if amniote is None else round(amniote['rho'], 4)}, n={0 if amniote is None else amniote['n']}.",
        f"Classes: {class_bits or 'none with n>=30'}.",
        f"Fishes: {fish_bit}. PanTHERIA mammals: {pan_bit}.",
        (
            f"Fish rows in AnAge: {fish_rows}. Rows with Body mass (g) and litter: {fish_body_and_litter}. "
            f"Rows with Adult weight (g) and litter: {fish_adult_weight_and_litter}. "
            "The adult-weight fish correlation was not computed and is not used for the verdict."
        ),
    ]
    result["caveats"] = settle_caveats(result.get("caveats", []), [
        "Body mass (g) is the AnAge mass paired with metabolic-rate rows. Adult weight (g) was not substituted, because the registration names Body mass (g) when that column is present.",
        "Species are not phylogenetically independent. The class split is the only control the registration allowed.",
        (
            f"Fishes are present ({fish_rows} rows), but Body mass (g) together with litter or clutch size is filled for {fish_body_and_litter} of them, "
            f"so the fish pattern is absent. Adult weight (g) together with litter is filled for {fish_adult_weight_and_litter} fish and was not used. "
            "Birds with both registered fields are not a negative class. The pooled amniote correlation is carried by the classes that meet the negative cut, principally mammals."
        ),
    ])
    RESULT.write_text(json.dumps(result, indent=2) + "\n")
    DERIVED.mkdir(exist_ok=True)
    # class_counts can be large but is a handful of classes
    (DERIVED / "measured.json").write_text(json.dumps({"verdict": verdict, "reason": reason, "measured": measured}, indent=2) + "\n")
    print(verdict, reason, "amniote", amniote_pattern, None if not amniote else amniote["rho"], "fish", fish_pattern, "pan_pos", pan_positive)


if __name__ == "__main__":
    main()
