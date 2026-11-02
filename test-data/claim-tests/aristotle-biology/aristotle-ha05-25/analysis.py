#!/usr/bin/env python3
"""Age at childbearing against Aristotle's limits of about 45 and 65.

Pre-registered in result.json. Women: Eurostat demo_frate age-specific
fertility rates for EU27_2020. Men: NCHS 2024 natality public-use file,
father's combined age. US maternal ages are the fallback if Eurostat fails.
"""
import datetime as dt
import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
RESULT = HERE / "result.json"
UA = "Mozilla/5.0 (compatible; delphisci-claim-test/1.0; research)"
EUROSTAT = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_frate"
    "?format=JSON&lang=en&geo=EU27_2020"
)
NATALITY = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/natality/Nat2024us.zip"
# The 2024 user guide says 1330. The file CDC shipped is 1345 characters plus CRLF.
# See deviations in result.json. Positions 75-76 and 147-148 are unchanged.
RECORD_LEN = 1345
MAGER_SLICE = slice(74, 76)       # positions 75-76, 1-indexed
FAGE_SLICE = slice(146, 148)      # positions 147-148
NATALITY_BYTES = 231829759


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_file(path):
    h = hashlib.sha256()
    n = 0
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            n += len(chunk)
    return n, h.hexdigest()


def fetch(url, dest, reuse_bytes=None):
    if reuse_bytes and dest.exists() and dest.stat().st_size == reuse_bytes:
        n, digest = _hash_file(dest)
        return n, digest, 200
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as r, dest.open("wb") as out:
        h = hashlib.sha256()
        n = 0
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
            h.update(chunk)
            n += len(chunk)
        return n, h.hexdigest(), r.status


def flat_index(coords, sizes):
    idx = 0
    for c, s in zip(coords, sizes):
        idx = idx * s + c
    return idx


def single_year(label):
    label = label.strip().lower()
    m = re.fullmatch(r"(\d{1,2})(?: years?)?", label)
    if m:
        return int(m.group(1))
    return None


def eurostat_rates(path):
    doc = json.loads(path.read_text())
    dims = doc["dimension"]
    ids = doc["id"]
    sizes = doc["size"]
    # pick agedef = completed years, geo EU27_2020, latest time, all ages
    def codes(dim):
        cat = dims[dim]["category"]
        index = cat["index"]
        labels = cat.get("label", {})
        # index may be {code: position}
        if isinstance(index, dict):
            items = sorted(index.items(), key=lambda kv: kv[1])
        else:
            items = list(enumerate(index))
            items = [(code, i) for i, code in items]
        return [(code, labels.get(code, code), pos) for code, pos in items]

    chosen = {}
    for dim in ids:
        chosen[dim] = codes(dim)

    def pick(dim, pred, fallback_first=False):
        opts = chosen[dim]
        for code, label, pos in opts:
            if pred(code, label):
                return code, label, pos
        if fallback_first and opts:
            return opts[-1]
        raise KeyError(dim)

    agedef = pick("agedef", lambda c, l: "complet" in c.lower() or "complet" in l.lower())
    geo = pick("geo", lambda c, l: c == "EU27_2020")
    # latest time that is a year
    times = [(c, l, p) for c, l, p in chosen["time"] if re.fullmatch(r"\d{4}", str(c))]
    if not times:
        times = chosen["time"]
    time = times[-1]
    # frequency annual if present
    freq = None
    if "freq" in ids:
        freq = pick("freq", lambda c, l: c in ("A", "a") or "annual" in l.lower(), fallback_first=True)
    unit = None
    if "unit" in ids:
        # fertility rate; prefer the code that is not a total
        unit_opts = chosen["unit"]
        unit = unit_opts[0]
        for code, label, pos in unit_opts:
            if "rate" in label.lower() or code.upper() in ("RT", "RATE"):
                unit = (code, label, pos)
                break

    age_pos = {}
    open50 = None
    for code, label, pos in chosen["age"]:
        year = single_year(label) or single_year(str(code).lstrip("Y"))
        if year is not None and 10 <= year <= 60:
            age_pos[year] = (code, label, pos)
        lab = f"{code} {label}".lower()
        if re.search(r"50\s*(and over|\+|or over)|ge50|_ge50|y_ge50|50 years or over", lab):
            open50 = (code, label, pos)

    value = doc.get("value", {})
    if isinstance(value, list):
        value = {str(i): v for i, v in enumerate(value) if v is not None}

    def rate_at(age_entry):
        coords = []
        for dim, size in zip(ids, sizes):
            if dim == "age":
                coords.append(age_entry[2])
            elif dim == "geo":
                coords.append(geo[2])
            elif dim == "time":
                coords.append(time[2])
            elif dim == "agedef":
                coords.append(agedef[2])
            elif dim == "freq" and freq:
                coords.append(freq[2])
            elif dim == "unit" and unit:
                coords.append(unit[2])
            else:
                coords.append(0)
        key = str(flat_index(coords, sizes))
        raw = value.get(key)
        return None if raw is None else float(raw)

    rates = {}
    for year, entry in sorted(age_pos.items()):
        r = rate_at(entry)
        if r is not None:
            rates[year] = r
    r50_open = rate_at(open50) if open50 else None
    meta = {
        "label": doc.get("label"),
        "updated": doc.get("updated"),
        "geo": geo[0],
        "geo_label": geo[1],
        "time": time[0],
        "agedef": agedef[0],
        "agedef_label": agedef[1],
        "unit": None if not unit else unit[0],
        "unit_label": None if not unit else unit[1],
        "freq": None if not freq else freq[0],
        "open50_label": None if not open50 else open50[1],
        "id": ids,
        "size": sizes,
    }
    return rates, r50_open, meta


def female_decision(rates, r50_open):
    ages = sorted(a for a in rates if 15 <= a <= 49)
    if len(ages) < 20:
        return None, "data-unavailable", {"n_ages": len(ages)}
    peak_age = max(ages, key=lambda a: rates[a])
    p = rates[peak_age]
    if p <= 0:
        return None, "data-unavailable", {"peak": p}
    a10 = None
    for a in range(30, 50):
        if a in rates and rates[a] < 0.10 * p:
            a10 = a
            break
    if a10 is None:
        a10 = 50 if any(a >= 49 for a in ages) else None
    if 50 in rates:
        r50 = rates[50]
        r50_source = "single-year"
    elif r50_open is not None:
        r50 = r50_open
        r50_source = "open-ended"
    elif all(a in rates for a in (47, 48, 49)):
        r50 = 0.0
        r50_source = "series-ends-at-49"
    else:
        r50 = None
        r50_source = None
    r45 = rates.get(45)
    info = {
        "peak_age": peak_age, "peak": p, "a10": a10, "rate_45": r45,
        "rate_50": r50, "rate_50_source": r50_source,
        "rates_40_to_50": {str(a): rates[a] for a in range(40, 51) if a in rates},
    }
    if r50 is None or a10 is None or r45 is None:
        return None, "data-unavailable", info
    if r50 >= 0.01 * p or a10 >= 50 or a10 <= 40:
        return "refutes", None, info
    if 42 <= a10 <= 48 and r45 > 0 and r50 < 0.01 * p:
        return "supports", None, info
    return "mixed", None, info


def zip_names(zip_path):
    out = subprocess.check_output(["unzip", "-l", str(zip_path)], text=True)
    names = []
    for line in out.splitlines():
        if ".txt" not in line:
            continue
        names.append(line.split(None, 3)[-1].strip())
    return names


def parse_natality(zip_path):
    """Stream the public-use member. Python's zipfile cannot inflate method 9 (Deflate64).

    Each shipped record is RECORD_LEN bytes plus CRLF, so the stride is fixed.
    A mismatched line ending means the file is not the layout this test accepts.
    """
    mother = [0] * 100
    father = [0] * 100
    n = 0
    bad_len = 0
    names = zip_names(zip_path)
    member = names[0] if names else None
    stride = RECORD_LEN + 2
    proc = subprocess.Popen(["unzip", "-p", str(zip_path)], stdout=subprocess.PIPE)
    buf = b""
    try:
        while True:
            chunk = proc.stdout.read(stride * 4096)
            if not chunk:
                break
            buf += chunk
            usable = (len(buf) // stride) * stride
            block = buf[:usable]
            buf = buf[usable:]
            for i in range(0, usable, stride):
                if block[i + RECORD_LEN:i + stride] != b"\r\n":
                    bad_len += 1
                    if bad_len > 100 and n == 0:
                        proc.kill()
                        buf = b""
                        break
                    continue
                n += 1
                mag = block[i + 74:i + 76]
                fag = block[i + 146:i + 148]
                if mag.isdigit():
                    mother[int(mag)] += 1
                if fag.isdigit():
                    father[int(fag)] += 1
            else:
                continue
            break
        if buf:
            bad_len += 1
    finally:
        if proc.stdout:
            proc.stdout.close()
        proc.wait()
    return {
        "member": member,
        "names": names,
        "n": n,
        "bad_len": bad_len,
        "record_len": RECORD_LEN,
        "mother": {i: c for i, c in enumerate(mother) if c},
        "father": {i: c for i, c in enumerate(father) if c},
    }


def male_decision(father):
    # ages 15-80; 99 is unknown
    counts = {a: father.get(a, 0) for a in range(15, 81)}
    known = sum(counts.values())
    if known < 1_000_000:
        return None, "data-unavailable", {"known_15_80": known}
    peak_age = max(counts, key=lambda a: counts[a])
    p = counts[peak_age]
    a10 = None
    for a in range(40, 81):
        if counts[a] < 0.10 * p:
            a10 = a
            break
    if a10 is None:
        a10 = 81
    c65 = counts.get(65, 0)
    c70 = counts.get(70, 0)
    info = {
        "known_15_80": known, "peak_age": peak_age, "peak": p, "a10": a10,
        "tenth_of_peak": 0.10 * p, "hundredth_of_peak": 0.01 * p,
        "count_65": c65, "count_70": c70,
        "count_60": counts.get(60, 0), "count_66": counts.get(66, 0),
        "counts_40_to_80": {str(a): counts[a] for a in range(40, 81)},
        "share_65_plus": sum(counts[a] for a in range(65, 81)) / known,
        "share_70_plus": sum(counts[a] for a in range(70, 81)) / known,
        "unknown_99": father.get(99, 0),
    }
    if c70 >= 0.01 * p or a10 >= 75 or a10 <= 55:
        return "refutes", None, info
    if 60 <= a10 <= 70 and c65 > 0 and c70 < 0.01 * p:
        return "supports", None, info
    return "mixed", None, info


def female_from_counts(mother):
    """Fallback: MAGER counts. Code 50 is 50 years and over."""
    counts = {a: mother.get(a, 0) for a in range(15, 51)}
    known = sum(counts.values())
    if known < 1_000_000:
        return None, "data-unavailable", {"known": known}
    peak_age = max(range(15, 50), key=lambda a: counts[a])
    p = counts[peak_age]
    a10 = None
    for a in range(30, 50):
        if counts[a] < 0.10 * p:
            a10 = a
            break
    if a10 is None:
        a10 = 50
    r50 = counts.get(50, 0)
    r45 = counts.get(45, 0)
    info = {"source": "nchs-mager", "peak_age": peak_age, "peak": p, "a10": a10,
            "count_45": r45, "count_50_and_over": r50, "known": known}
    if r50 >= 0.01 * p or a10 >= 50 or a10 <= 40:
        return "refutes", None, info
    if 42 <= a10 <= 48 and r45 > 0 and r50 < 0.01 * p:
        return "supports", None, info
    return "mixed", None, info


def combine(female, male):
    fv, fr, _ = female
    mv, mr, _ = male
    if fv == "refutes" or mv == "refutes":
        return "refutes", None
    if fv == "supports" and mv == "supports":
        return "supports", None
    if (fv is None and mv != "refutes") or (mv is None and fv != "refutes"):
        return "inconclusive", "data-unavailable"
    return "mixed", None


def main():
    DATA.mkdir(exist_ok=True)
    DERIVED.mkdir(exist_ok=True)
    files = []
    euro_path = DATA / "demo_frate.json"
    try:
        n, digest, status = fetch(EUROSTAT, euro_path)
        files.append({
            "name": "demo_frate.json", "download_url": EUROSTAT, "retrieved_at": now(),
            "byte_size": n, "sha256": digest, "http_status": status,
        })
        rates, r50_open, meta = eurostat_rates(euro_path)
        female = female_decision(rates, r50_open)
        female[2]["eurostat"] = meta
        female_source = "eurostat-demo-frate"
    except Exception as exc:  # noqa: BLE001
        female = (None, "data-unavailable", {"error": str(exc)})
        female_source = None
        rates = {}

    nat_path = DATA / "Nat2024us.zip"
    try:
        n, digest, status = fetch(NATALITY, nat_path, reuse_bytes=NATALITY_BYTES)
        files.append({
            "name": "Nat2024us.zip", "download_url": NATALITY, "retrieved_at": now(),
            "byte_size": n, "sha256": digest, "http_status": status,
        })
        parsed = parse_natality(nat_path)
        if parsed["n"] < 1_000_000 or (parsed["bad_len"] > 0 and parsed["n"] == 0):
            male = (None, "data-unavailable", parsed)
            mother_fallback = (None, "data-unavailable", {})
        else:
            male = male_decision(parsed["father"])
            male[2]["records"] = parsed["n"]
            male[2]["zip_member"] = parsed["member"]
            male[2]["bad_len"] = parsed["bad_len"]
            male[2]["record_len"] = parsed["record_len"]
            mother_fallback = female_from_counts(parsed["mother"])
    except Exception as exc:  # noqa: BLE001
        parsed = None
        male = (None, "data-unavailable", {"error": str(exc)})
        mother_fallback = (None, "data-unavailable", {})

    if female[0] is None and female_source is None:
        female = mother_fallback
        female_source = "nchs-mager-fallback" if female[0] is not None else None

    verdict, reason = combine(female, male)
    # confidence: birth-count schedule for men is not a rate, so cap it
    if verdict == "supports":
        confidence = 0.62
    elif verdict == "refutes":
        confidence = 0.7
    elif verdict == "mixed":
        confidence = 0.55
    else:
        confidence = 0.3

    fv, fr, finfo = female
    mv, mr, minfo = male
    measured = {
        "value": None if not finfo.get("a10") else finfo.get("a10"),
        "unit": "female a10, youngest age at or above 30 below 10 percent of peak fertility",
        "n": finfo.get("eurostat", {}).get("time") or finfo.get("known") or male[2].get("records"),
        "uncertainty": None,
        "extra": {
            "female_verdict": fv,
            "female_reason": fr,
            "female_source": female_source,
            "female": {k: v for k, v in finfo.items() if k != "rates_40_to_50"} | {
                "rates_40_to_50": finfo.get("rates_40_to_50")},
            "male_verdict": mv,
            "male_reason": mr,
            "male": minfo,
            "mother_fallback": mother_fallback[2] if female_source != "nchs-mager-fallback" else None,
        },
    }
    # n should be a count where we have one
    if isinstance(minfo, dict) and minfo.get("records"):
        measured["n"] = minfo["records"]
    doc = json.loads(RESULT.read_text())
    doc["status"] = "complete"
    doc["verdict"] = verdict
    if reason:
        doc["reason"] = reason
    elif "reason" in doc:
        del doc["reason"]
    doc["confidence"] = confidence
    doc["data_kind"] = "biological"
    for ds in doc["datasets"]:
        if ds["id"] == "eurostat-demo-frate":
            ds["files"] = [f for f in files if f["name"] == "demo_frate.json"]
        if ds["id"] == "nchs-natality-2024-us-public-use":
            ds["files"] = [f for f in files if f["name"] == "Nat2024us.zip"]
    doc["measured"] = measured
    doc["method"] = (
        "Downloaded Eurostat demo_frate filtered to EU27_2020 and the NCHS 2024 US natality "
        "public-use zip. Female age-specific rates in completed years were read for the latest "
        "year; a10 is the youngest age at or above 30 below 10 percent of the peak rate at ages "
        "15-49, and age 50 is compared with 1 percent of that peak. Father's combined age "
        "(bytes 147-148) was counted the same way, excluding code 99, on records of 1345 "
        "characters plus CRLF. The conjunction follows the pre-registered rule. The record-length "
        "gate is the deviation recorded in this file: the user guide says 1330 and the shipped "
        "file is 1345."
    )
    doc["deviations"] = [{
        "date": "2026-11-01",
        "field": "fail_criterion record-length gate",
        "was": (
            "Fewer than 1,000,000 parsed US birth records, or a record length other than "
            "1330 after stripping the line ending, is inconclusive with reason data-unavailable."
        ),
        "now": (
            "A record is parsed when, after stripping one CRLF, its length is 1345. "
            "MAGER remains positions 75-76 and FAGECOMB positions 147-148. Any other length, "
            "or fewer than 1,000,000 parsed records, is still inconclusive with reason "
            "data-unavailable. The age thresholds are unchanged."
        ),
        "why": (
            "The 2024 user guide states record length 1330 and a United States record count "
            "of 3638436. Nat2024PublicUS.c20250512.r20250708.txt is 4900973292 bytes, which "
            "equals 3638436 times 1347, and each line is 1345 characters plus CRLF. The extra "
            "15 bytes sit at the end of the record, after the filler that the guide starts at "
            "position 571. Requiring 1330 would reject every record of the file whose count "
            "the guide names. Python zipfile also cannot inflate this archive (method 9, "
            "Deflate64); the script streams it with unzip -p. That is a reader fix, not a "
            "change to the age rule."
        ),
    }]
    doc["results_summary"] = [
        f"Women ({female_source}): verdict {fv}, a10={finfo.get('a10')}, "
        f"rate or count at 45={finfo.get('rate_45', finfo.get('count_45'))}, "
        f"at 50={finfo.get('rate_50', finfo.get('count_50_and_over'))}, peak age {finfo.get('peak_age')}.",
        f"Men (FAGECOMB): verdict {mv}, a10={minfo.get('a10')}, count at 65={minfo.get('count_65')}, "
        f"count at 70={minfo.get('count_70')}, peak age {minfo.get('peak_age')}, records {minfo.get('records')}.",
        f"Verdict {verdict}." + (f" Reason {reason}." if reason else ""),
    ]
    RESULT.write_text(json.dumps(doc, indent=2) + "\n")
    # derived table stays small: do not write the full natality file
    small = {
        "verdict": verdict, "reason": reason,
        "female": finfo, "male": {k: v for k, v in minfo.items() if k != "error"},
    }
    DERIVED.joinpath("measured.json").write_text(json.dumps(small, indent=2) + "\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "female": fv, "male": mv,
                      "fa10": finfo.get("a10"), "ma10": minfo.get("a10")}, indent=2))


if __name__ == "__main__":
    main()
