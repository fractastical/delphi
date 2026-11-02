#!/usr/bin/env python3
"""Test aristotle-ga04-22: human females develop longer in the womb and sooner after birth."""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

NATALITY_URL = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/natality/Nat2023us.zip"
PUBERTY_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC6378593/fullTextXML"
MX_URL = "https://raw.githubusercontent.com/open-numbers/ddf--unpop--world_population_prospects/master/life_table/ddf--datapoints--mx--by--world--time--sex--age_group_broad.csv"
EX_URL = "https://raw.githubusercontent.com/open-numbers/ddf--unpop--world_population_prospects/master/life_table/ddf--datapoints--ex--by--world--time--sex--age_group_broad.csv"


def fetch(url, name):
    path = os.path.join(DATA, name)
    meta = path + ".retrieved"
    if not (os.path.exists(path) and os.path.exists(meta)):
        r = requests.get(url, timeout=300)
        r.raise_for_status()
        open(path, "wb").write(r.content)
        open(meta, "w").write(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    content = open(path, "rb").read()
    return path, {
        "download_url": url,
        "retrieved_at": open(meta).read().strip(),
        "byte_size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def median_from_hist(hist):
    total = sum(hist.values())
    if total == 0:
        return None, 0
    need = total / 2
    running = 0
    weeks = sorted(hist)
    for w in weeks:
        running += hist[w]
        if running >= need:
            # Even-count median is the mean of the two central ranks when the
            # cumulative crosses an integer boundary exactly between two values.
            if total % 2 == 0 and running - hist[w] == need:
                # previous week is the lower central rank
                prev = max(x for x in weeks if x < w)
                return (prev + w) / 2, total
            return float(w), total
    return float(weeks[-1]), total


def gestation(path):
    hist_oe = {"M": {}, "F": {}}
    hist_comb = {"M": {}, "F": {}}
    lines = 0
    used = 0
    proc = subprocess.Popen(["unzip", "-p", path], stdout=subprocess.PIPE)
    assert proc.stdout is not None
    for line in proc.stdout:
        lines += 1
        if len(line) < 510:
            continue
        sex = line[474:475]
        if sex not in (b"M", b"F"):
            continue
        key = sex.decode()
        oe = line[498:500]
        comb = line[489:491]
        try:
            w = int(oe)
        except ValueError:
            w = None
        if w is not None and 17 <= w <= 47:
            hist_oe[key][w] = hist_oe[key].get(w, 0) + 1
            used += 1
        try:
            c = int(comb)
        except ValueError:
            c = None
        if c is not None and 17 <= c <= 47:
            hist_comb[key][c] = hist_comb[key].get(c, 0) + 1
    proc.wait()
    med_f, n_f = median_from_hist(hist_oe["F"])
    med_m, n_m = median_from_hist(hist_oe["M"])
    comb_f, _ = median_from_hist(hist_comb["F"])
    comb_m, _ = median_from_hist(hist_comb["M"])
    return {
        "lines": lines,
        "oe_records": used,
        "female_median_oe_weeks": med_f,
        "male_median_oe_weeks": med_m,
        "female_n": n_f,
        "male_n": n_m,
        "female_median_combined_weeks": comb_f,
        "male_median_combined_weeks": comb_m,
        "female_longer": None if med_f is None or med_m is None else bool(med_f > med_m),
    }


def puberty(path):
    root = ET.fromstring(open(path, "rb").read())
    text = re.sub(r"\s+", " ", " ".join(root.itertext()))
    voice = re.search(
        r"voice break occurred at\s+([0-9]+(?:\.[0-9]+)?)\s+\(95%\s*CI\s*([0-9.]+),\s*([0-9.]+)\)",
        text, re.I)
    menarche = re.search(
        r"age at menarche occurred at\s+([0-9]+(?:\.[0-9]+)?)\s+\(95%\s*CI\s*([0-9.]+),\s*([0-9.]+)\)",
        text, re.I)
    doi = re.search(r"10\.\d{4,}/[A-Za-z0-9._()/-]+", text)
    out = {"doi": doi.group(0).rstrip(").,") if doi else None}
    if voice:
        out["voice_break_mean"] = float(voice.group(1))
        out["voice_break_ci"] = [float(voice.group(2)), float(voice.group(3))]
    if menarche:
        out["menarche_mean"] = float(menarche.group(1))
        out["menarche_ci"] = [float(menarche.group(2)), float(menarche.group(3))]
    if "menarche_mean" in out and "voice_break_mean" in out:
        out["female_earlier"] = bool(out["menarche_mean"] < out["voice_break_mean"])
    else:
        out["female_earlier"] = None
    return out


def age_start(label):
    label = str(label)
    if label == "0":
        return 0
    if label == "100plus":
        return 100
    m = re.fullmatch(r"(\d+)_(\d+)", label)
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if b - a > 4:
        return None
    return a


def life_table(path):
    df = pd.read_csv(path)
    value_col = [c for c in df.columns if c not in ("world", "time", "sex", "age_group_broad")][-1]
    df["age_start"] = df["age_group_broad"].map(age_start)
    df = df[df["age_start"].notna() & (df["time"] == 2023) & (df["sex"].isin([1, 2]))].copy()
    df["mx"] = pd.to_numeric(df[value_col], errors="coerce")
    adult = df[(df.age_start >= 15) & (df.age_start <= 49)]
    scale = "per_thousand" if float(adult["mx"].median()) > 1 else "per_year"
    threshold = 20.0 if scale == "per_thousand" else 0.02

    def side(sex):
        sub = df[df.sex == sex].sort_values("age_start")
        prime_pool = sub[(sub.age_start >= 15) & (sub.age_start <= 50)]
        prime_row = prime_pool.loc[prime_pool["mx"].idxmin()]
        old = sub[(sub.age_start >= 50) & (sub.mx >= threshold)].sort_values("age_start")
        old_age = None if old.empty else int(old.iloc[0]["age_start"])
        return {
            "prime_age_start": int(prime_row["age_start"]),
            "prime_mx": float(prime_row["mx"]),
            "old_age_start": old_age,
            "schedule": {str(int(a)): round(float(m), 6) for a, m in zip(sub.age_start, sub.mx)},
        }

    male = side(1)
    female = side(2)
    return {
        "value_column": value_col,
        "scale": scale,
        "threshold": threshold,
        "male": {k: v for k, v in male.items() if k != "schedule"},
        "female": {k: v for k, v in female.items() if k != "schedule"},
        "male_schedule": male["schedule"],
        "female_schedule": female["schedule"],
        "female_prime_earlier": female["prime_age_start"] < male["prime_age_start"],
        "female_old_age_earlier": (
            None if female["old_age_start"] is None or male["old_age_start"] is None
            else female["old_age_start"] < male["old_age_start"]
        ),
    }


def main():
    pub_path, pub_file = fetch(PUBERTY_URL, "PMC6378593.fulltext.xml")
    mx_path, mx_file = fetch(MX_URL, "wpp-mx-world-sex-age.csv")
    ex_path, ex_file = fetch(EX_URL, "wpp-ex-world-sex-age.csv")
    nat_path, nat_file = fetch(NATALITY_URL, "Nat2023us.zip")

    pub = puberty(pub_path)
    life = life_table(mx_path)
    ex = pd.read_csv(ex_path)
    ex_col = [c for c in ex.columns if c not in ("world", "time", "sex", "age_group_broad")][-1]
    ex["age_start"] = ex["age_group_broad"].map(age_start)
    e0 = {}
    for sex, name in ((1, "male"), (2, "female")):
        row = ex[(ex.time == 2023) & (ex.sex == sex) & (ex.age_start == 0)]
        e0[name] = None if row.empty else float(row.iloc[0][ex_col])
    gest = gestation(nat_path)
    json.dump({"puberty": pub, "life": {k: v for k, v in life.items() if "schedule" not in k}, "e0": e0, "gestation": gest},
              open(os.path.join(DERIVED, "clauses.json"), "w"), indent=2)
    pd.DataFrame({
        "age_start": list(life["female_schedule"]),
        "female_mx": list(life["female_schedule"].values()),
        "male_mx": [life["male_schedule"].get(a) for a in life["female_schedule"]],
    }).to_csv(os.path.join(DERIVED, "world-2023-mx.csv"), index=False)

    clauses = {
        "prenatal_female_longer_gestation": gest["female_longer"],
        "puberty_menarche_before_voice_break": pub.get("female_earlier"),
        "prime_female_younger": life["female_prime_earlier"],
        "old_age_female_younger": life["female_old_age_earlier"],
    }
    known = {k: v for k, v in clauses.items() if v is not None}
    holds = [v for v in known.values() if v]
    fails = [v for v in known.values() if v is False]
    underpowered = gest["female_n"] < 1000 or gest["male_n"] < 1000
    if underpowered and not fails:
        verdict, reason = "inconclusive", "underpowered"
    elif len(known) == 4 and all(known.values()):
        verdict, reason = "supports", None
    elif len(known) == 4 and not any(known.values()):
        verdict, reason = "refutes", None
    elif holds and fails:
        verdict, reason = "mixed", None
    elif fails and len(known) < 4:
        verdict, reason = "mixed", None
    else:
        verdict, reason = "inconclusive", "data-unavailable"
    confidence = 0.8 if verdict == "mixed" else 0.85 if verdict in ("supports", "refutes") else 0.4

    measured = {
        "value": gest["female_median_oe_weeks"],
        "unit": "female median obstetric estimate of gestation, weeks, US natality 2023",
        "n": gest["female_n"] + gest["male_n"],
        "uncertainty": "medians of integer weeks; a tie is not 'longer'",
        "extra": {
            "clauses": clauses,
            "gestation": gest,
            "puberty": pub,
            "life_table": {k: v for k, v in life.items() if "schedule" not in k},
            "e0_2023": e0,
        },
    }
    if "--write-result" in sys.argv:
        result = json.load(open(os.path.join(HERE, "result.json")))
        result["status"] = "complete"
        result["data_kind"] = "biological"
        result["verdict"] = verdict
        if reason:
            result["reason"] = reason
        result["confidence"] = confidence
        result["measured"] = measured
        result["datasets"] = [
            {
                "id": "cdc-nvss-natality-2023",
                "name": "NCHS 2023 natality public-use file",
                "landing_url": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/natality/Nat2023us.zip",
                "doi": None,
                "version": "Nat2023PublicUS.c20240509.r20240724",
                "license": "US government public data",
                "role": "sex and obstetric gestational age of live births",
                "files": [nat_file],
            },
            {
                "id": "pmc6378593-puberty-timing",
                "name": "Brix et al. population puberty timing, Europe PMC full text",
                "landing_url": "https://europepmc.org/article/PMC/PMC6378593",
                "doi": pub.get("doi"),
                "version": "PMC6378593",
                "license": "CC BY",
                "role": "mean age at menarche and at voice break",
                "files": [pub_file],
            },
            {
                "id": "un-wpp2024-mx5-world-2023",
                "name": "UN WPP central death rates by sex and abridged age, world, open-numbers mirror",
                "landing_url": "https://github.com/open-numbers/ddf--unpop--world_population_prospects",
                "doi": None,
                "version": "open-numbers master, medium variant, year 2023",
                "license": "CC BY 3.0 IGO (UN WPP)",
                "role": "age of lowest adult mortality and onset of a 2 percent death rate",
                "files": [mx_file, ex_file],
            },
        ]
        result["method"] = (
            "Gestation is the obstetric estimate in bytes 499-500 of the 2023 natality file (1-indexed positions 499-500), "
            f"sex in byte 475. Female median {gest['female_median_oe_weeks']} weeks (n={gest['female_n']}), "
            f"male median {gest['male_median_oe_weeks']} weeks (n={gest['male_n']}). "
            "Puberty means are parsed from the results sentence of PMC6378593. "
            f"Menarche {pub.get('menarche_mean')} years, voice break {pub.get('voice_break_mean')} years. "
            "Prime and old age use the open-numbers world life table for 2023. "
            f"Rates are treated as {life['scale']} because the median adult mx is "
            f"{'above' if life['scale']=='per_thousand' else 'at or below'} 1; the old-age threshold used is {life['threshold']}. "
            f"Female prime age-group start {life['female']['prime_age_start']}, male {life['male']['prime_age_start']}. "
            f"Female old-age onset {life['female']['old_age_start']}, male {life['male']['old_age_start']}."
        )
        result["deviations"] = [
            {
                "field": "life-table source",
                "change": "The UN Population Data Portal data endpoint returned HTTP 401 Bearer. Central death rates mx were read from the open-numbers GitHub mirror of the WPP medium-variant life table, world, year 2023, sex codes 1 and 2. The comparisons are the ones that were pre-registered.",
                "why": "The named API refused unauthenticated data requests. The mirror is the same WPP table.",
            },
            {
                "field": "mx units",
                "change": f"The file's adult rates are on the scale '{life['scale']}'. The pre-registered 0.02 per year is applied as {life['threshold']} in the file's units.",
                "why": "The concept file does not state the multiplier. The scale rule was fixed as: median adult mx > 1 means per thousand.",
            },
            {
                "field": "gestational-age field",
                "change": "The verdict uses OEGest_Comb, bytes 499-500, the obstetric estimate the user guide says replaced the menstrual estimate. Combined gestation, bytes 490-491, is reported and does not set the verdict.",
                "why": "The natality user guide documents two week-count fields. The obstetric estimate is the one NCHS describes as the current measure.",
            },
        ]
        result["caveats"] = [
            "Gestation is one US year, including the territories that share this public-use file (about 22 thousand of 3.63 million records). The median is over the whole file.",
            "Menarche and voice break are one Danish cohort's means. The reported intervals overlap, and the clause still follows the point estimates, as pre-registered.",
            "Prime of life is the five-year age group of lowest mortality between 15 and 50, not a measured peak of strength or fertility.",
            "Old age is the first age group at or after 50 whose central death rate reaches the threshold. It is not menopause and not the age of the oldest person.",
            "Life expectancy at birth is stored as extra and does not set the verdict.",
            "A search snippet had already shown the puberty point estimates. The rule remained 'earlier means a smaller age', with no minimum gap.",
        ]
        json.dump(result, open(os.path.join(HERE, "result.json"), "w"), indent=2)
        open(os.path.join(HERE, "result.json"), "a").write("\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "clauses": clauses, "e0": e0, "scale": life["scale"]}, default=str))


if __name__ == "__main__":
    main()
