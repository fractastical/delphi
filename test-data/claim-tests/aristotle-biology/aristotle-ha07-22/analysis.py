#!/usr/bin/env python3
"""Lactational amenorrhea in the World Fertility Survey standard recode.

Recomputes the verdict locked in result.json. The Kenya dictionary was read
before that registration; this script is the first reader of the microdata.

Run from anywhere: python3 analysis.py
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
INDEX = "https://wfs.dhsprogram.com/"
UA = "delphisci-claim-test/aristotle-ha07-22"

# 96 is the standard-recode code for an open amenorrhea interval.
F122_OPEN = 96
DEVIATIONS = [
    {
        "what": "A fixed-width file is accepted when its byte size equals the dictionary record count times the logical record length plus 0, 1 or 2 separator bytes.",
        "why": "The Kenya content-length, read from the HTTP header before any field value, is 8618400 = 8100 * (1062 + 2). The logical record length does not divide the on-disk file because each record is followed by CR LF. Eligibility and the 0.60 / 0.50 thresholds are unchanged.",
    },
    {
        "what": "V206 = 0 is accepted when the variable label contains 'pregnant' or 'enceinte' and value 0 starts with No or Non and value 1 is Yes or Oui, rather than requiring the value label 'not pregnant'.",
        "why": "Re-reading the same Kenya dictionary showed that the words 'Not pregnant' are the value label of V205 (duration of the current pregnancy). V206 is labeled 'Currently pregnant', with 0 = No and 1 = Yes. The eligibility rule is the one named in the hypothesis: drop women who are currently pregnant. No microdata value had been read when this was noticed.",
    },
    {
        "what": "The closed amenorrhea codes are the integers from that survey's own F122 minimum through its maximum, not Kenya's maximum of 41. F117 may be labeled Yes or Oui. Code 96 must be labeled as still amenorrheic. Codes 88 and 99 must be the not-applicable and not-stated labels. Code 87, when present, is a missing-data label and is excluded. Pill and injection are recognized from the value label (Pill/Pilule, Injection) rather than only the English words; a code labeled 'not used' is not treated as an injection.",
        "why": "The figure 41 in the Kenya dictionary is the highest closed duration coded in Kenya, not a different meaning of the variable. Other standard-recode dictionaries use the same 96 = still amenorrheic code with a different ordinary maximum, and the French files label the sampling weight 'ponderation' rather than 'weight'. Requiring the maximum to equal 41 and the English word 'weight' kept only Kenya. The other dictionaries were compared before their microdata were read. The 0.60 and 0.50 thresholds are unchanged.",
    },
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, dest: Path | None = None) -> tuple[bytes, str]:
    if dest is not None and dest.exists() and dest.stat().st_size > 0:
        raw = dest.read_bytes()
        if raw[:1] not in (b"<", b"{"):
            retrieved = datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return raw, retrieved
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=180) as resp:
        raw = resp.read()
    retrieved = now()
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    return raw, retrieved


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def file_info(url: str, raw: bytes, retrieved: str) -> dict:
    return {
        "download_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": sha256(raw),
    }


def get_text(url: str) -> str:
    raw, _ = fetch(url)
    return raw.decode("utf-8", "replace")


def country_codes() -> list[str]:
    html = get_text(INDEX)
    codes = re.findall(r"index\.cfm\?ccode=([A-Za-z0-9]+)", html)
    seen = []
    for c in codes:
        c = c.lower()
        if c not in seen:
            seen.append(c)
    return seen


def country_page(code: str) -> tuple[str, str, list[str]]:
    url = f"https://wfs.dhsprogram.com/index.cfm?ccode={code}"
    html = get_text(url)
    html_clean = html_lib.unescape(html)
    html_clean = re.sub(r"<script[\s\S]*?</script>", " ", html_clean, flags=re.I)
    html_clean = re.sub(r"<style[\s\S]*?</style>", " ", html_clean, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html_clean)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    name = code
    m = re.search(r"WFS Data\s+((?:(?!WFS Data).)+?)\s+\(WFS\)", text)
    if m:
        name = m.group(1).strip()
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    dcts = []
    for h in hrefs:
        if h.lower().split("?")[0].endswith(".dct"):
            if h.startswith("http"):
                dcts.append(h)
            else:
                dcts.append("https://wfs.dhsprogram.com/" + h.lstrip("/"))
    return url, name, dcts


def parse_dictionary(text: str) -> dict:
    variables = {}
    order = []
    current = None
    meta = {"lrecl": None, "nrec": None, "country": None, "version": None}
    for line in text.splitlines():
        if line.startswith("%FILE"):
            meta["country"] = line[8:10].strip()
            meta["version"] = line[28:30].strip()
            try:
                meta["lrecl"] = int(line[36:40])
                meta["nrec"] = int(line[42:50])
            except ValueError:
                meta["lrecl"] = None
                meta["nrec"] = None
            continue
        if line[:1].isalpha():
            name = line[0:6].strip()
            def cell(a, b):
                s = line[a:b].strip()
                if not s:
                    return None
                try:
                    return int(s)
                except ValueError:
                    return None
            start = cell(9, 13)
            length = cell(14, 16)
            if not isinstance(start, int) or not isinstance(length, int):
                current = None
                continue
            var = {
                "name": name,
                "start": start,
                "length": length,
                "min": cell(16, 20),
                "max": cell(20, 24),
                "na": cell(25, 29),
                "special": cell(30, 34),
                "label": line[35:65].strip(),
                "backref": line[66:72].strip(),
                "values": {},
            }
            variables[name] = var
            order.append(name)
            current = var
            continue
        if current is not None and line[:1] == " ":
            code = line[35:39].strip()
            label = line[43:63].strip()
            if code:
                current["values"][code] = label
    return {"meta": meta, "variables": variables, "order": order}


def _low(values: dict, code: str) -> str:
    return values.get(code, "").lower()


def labels_ok(d: dict) -> tuple[bool, str]:
    """Dictionary gate. See DEVIATIONS for the Kenya-maximum and V206 label corrections."""
    v = d["variables"]
    need = ["F117", "F121", "F122", "V206", "V635", "V006", "V010"]
    for name in need:
        if name not in v:
            return False, f"missing {name}"
    f117 = v["F117"]["values"]
    yes = _low(f117, "1")
    no = _low(f117, "0")
    if not (yes.startswith("yes") or yes.startswith("oui")):
        return False, f"F117 1 label {f117.get('1')!r}"
    if not (no.startswith("no") or no.startswith("non")):
        return False, f"F117 0 label {f117.get('0')!r}"
    if v["F121"]["backref"] != "F117":
        return False, f"F121 backref {v['F121']['backref']!r}"
    f122 = v["F122"]
    if not isinstance(f122["min"], int) or not isinstance(f122["max"], int):
        return False, f"F122 range {f122['min']}..{f122['max']}"
    if not (0 <= f122["min"] <= f122["max"] < 96):
        return False, f"F122 range {f122['min']}..{f122['max']}"
    if "amenorr" not in _low(f122["values"], "96"):
        return False, f"F122 96 label {f122['values'].get('96')!r}"
    if "appli" not in _low(f122["values"], "88"):
        return False, f"F122 88 label {f122['values'].get('88')!r}"
    stated = _low(f122["values"], "99")
    if "stat" not in stated and "declar" not in stated:
        return False, f"F122 99 label {f122['values'].get('99')!r}"
    if "87" in f122["values"]:
        missing = _low(f122["values"], "87")
        if not any(fragment in missing for fragment in ("data", "information", "donn")):
            return False, f"F122 87 label {f122['values'].get('87')!r}"
    label206 = v["V206"]["label"].lower()
    if "pregnan" not in label206 and "enceinte" not in label206:
        return False, f"V206 label {v['V206']['label']!r}"
    v206 = v["V206"]["values"]
    if not (_low(v206, "0").startswith("no") or _low(v206, "0").startswith("non")):
        return False, f"V206 0 label {v206.get('0')!r}"
    if _low(v206, "1") not in {"yes", "oui"}:
        return False, f"V206 1 label {v206.get('1')!r}"
    v635 = v["V635"]["values"]
    pill = _low(v635, "1")
    if not (pill.startswith("pill") or pill.startswith("pilul")):
        return False, f"V635 1 label {v635.get('1')!r}"
    if "11" in v635:
        inj = _low(v635, "11")
        if inj.startswith("inject"):
            pass
        elif "not used" in inj or inj == "":
            pass
        else:
            return False, f"V635 11 label {v635.get('11')!r}"
    weight_label = v["V006"]["label"].lower()
    if "weight" not in weight_label and "ponderat" not in weight_label:
        return False, f"V006 is not a weight ({v['V006']['label']!r})"
    if d["meta"]["lrecl"] is None or d["meta"]["nrec"] is None:
        return False, "no %FILE length"
    return True, "ok"


def code_sets(d: dict) -> tuple[set[int], set[int], set[int]]:
    """Closed amenorrhea codes, codes that are known but ineligible, hormonal method codes."""
    f122 = d["variables"]["F122"]
    closed = set(range(f122["min"], f122["max"] + 1))
    known_other = {88, 99, 96}
    if "87" in f122["values"]:
        known_other.add(87)
    hormonal = set()
    for code, lab in d["variables"]["V635"]["values"].items():
        low = lab.lower().strip()
        if low.startswith("pill") or low.startswith("pilul") or low.startswith("inject"):
            hormonal.add(int(code))
    return closed, known_other, hormonal


def records(raw: bytes, lrecl: int, nrec: int) -> tuple[list[bytes], str | None]:
    """Split a fixed-width ASCII file into logical records.

    The dictionary length does not include the line separator. A file is
    accepted when its size is n * lrecl, n * (lrecl + 1) or n * (lrecl + 2).
    """
    for sep, label in ((0, "none"), (1, "lf"), (2, "crlf")):
        if nrec * (lrecl + sep) == len(raw):
            out = []
            step = lrecl + sep
            for i in range(nrec):
                rec = raw[i * step : i * step + lrecl]
                if len(rec) != lrecl:
                    return [], f"short record {i}"
                out.append(rec)
            return out, None
    return [], f"size {len(raw)} is not {nrec} records of {lrecl} plus a 0, 1 or 2 byte separator"


def field_int(rec: bytes, start: int, length: int):
    s = rec[start - 1 : start - 1 + length].decode("latin1").strip()
    if s == "":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def analyze_survey(recs: list[bytes], d: dict) -> dict:
    v = d["variables"]
    closed, known_other, hormonal = code_sets(d)
    known = closed | known_other
    ages = []
    outside = 0
    for rec in recs:
        age = field_int(rec, v["V010"]["start"], v["V010"]["length"])
        if age is None:
            continue
        ages.append(age)
        if age < 15 or age > 50:
            outside += 1
    age_rate = (outside / len(ages)) if ages else 1.0
    if age_rate > 0.01:
        return {"drop": f"age outside 15-50 in {outside}/{len(ages)} ({age_rate:.4f})"}

    filtered = []
    invalid = 0
    for rec in recs:
        f117 = field_int(rec, v["F117"]["start"], v["F117"]["length"])
        v206 = field_int(rec, v["V206"]["start"], v["V206"]["length"])
        v635 = field_int(rec, v["V635"]["start"], v["V635"]["length"])
        if f117 != 1 or v206 != 0 or v635 in hormonal:
            continue
        f122 = field_int(rec, v["F122"]["start"], v["F122"]["length"])
        if f122 not in known:
            invalid += 1
            continue
        filtered.append(rec)
    denom = len(filtered) + invalid
    if denom and invalid / denom > 0.05:
        return {"drop": f"invalid F122 {invalid}/{denom}"}

    eligible = []
    for rec in filtered:
        f122 = field_int(rec, v["F122"]["start"], v["F122"]["length"])
        if f122 in closed or f122 == F122_OPEN:
            eligible.append(rec)
    if not eligible:
        return {"drop": "no eligible women", "n_filtered": len(filtered), "invalid_f122": invalid}

    concord = 0
    weights = []
    amen = []
    full_w = []
    full_y = []
    for rec in eligible:
        f121 = field_int(rec, v["F121"]["start"], v["F121"]["length"])
        f122 = field_int(rec, v["F122"]["start"], v["F122"]["length"])
        y = 1 if f122 == F122_OPEN else 0
        expect = 1 if y == 1 else 0
        if f121 == expect:
            concord += 1
        w = field_int(rec, v["V006"]["start"], v["V006"]["length"])
        if w is None or w <= 0:
            continue
        weights.append(w / 1000.0)
        amen.append(y)
        if "F119" in v:
            f119 = field_int(rec, v["F119"]["start"], v["F119"]["length"])
            if f119 == 1:
                full_w.append(w / 1000.0)
                full_y.append(y)
    n = len(eligible)
    concordance = concord / n
    if concordance < 0.95:
        return {"drop": f"F121/F122 concordance {concordance:.4f} on {n}"}
    if not weights:
        return {"drop": "no positive weights"}
    wsum = sum(weights)
    p = sum(w * y for w, y in zip(weights, amen)) / wsum
    full_p = None
    if full_w:
        full_p = sum(w * y for w, y in zip(full_w, full_y)) / sum(full_w)
    return {
        "drop": None,
        "n": n,
        "n_weighted": len(weights),
        "p": p,
        "p_resumed": 1.0 - p,
        "concordance": concordance,
        "age_outside_rate": age_rate,
        "invalid_f122": invalid,
        "n_full_breastfeeding": len(full_w),
        "p_full_breastfeeding": full_p,
        "weight_sum_raw": wsum,
    }


def decide(pooled_p: float, pooled_resumed: float, n: int, surveys: list[dict]) -> tuple[str, str | None]:
    big = [s for s in surveys if s["n"] >= 100]
    disagree = (
        len(big) >= 3
        and any(s["p"] >= 0.60 for s in big)
        and any(s["p"] <= 0.50 for s in big)
    )
    if pooled_p <= 0.50:
        return "refutes", None
    if disagree or pooled_p < 0.60 or pooled_resumed < 0.05:
        return "mixed", None
    if pooled_p >= 0.60 and pooled_resumed >= 0.05 and n >= 200:
        return "supports", None
    return "inconclusive", "other"


def confidence_for(verdict: str, p: float | None, n: int, n_surveys: int) -> float:
    if verdict == "inconclusive":
        return 0.55
    if p is None:
        return 0.5
    base = 0.55 + 0.25 * min(n, 2000) / 2000 + 0.20 * min(abs(p - 0.5), 0.20) / 0.20
    if verdict == "mixed":
        base = min(base, 0.65)
    if n_surveys == 1:
        base = min(base, 0.70)
    return round(min(0.90, base), 2)


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    codes = country_codes()
    print(f"index surveys: {len(codes)} {codes}")
    included = []
    excluded = []
    datasets = []
    for code in codes:
        try:
            page, name, dcts = country_page(code)
        except Exception as exc:  # noqa: BLE001 — one dead country page should not stop the pool
            excluded.append({"ccode": code, "reason": f"page: {type(exc).__name__}: {exc}"})
            print(f"  {code} page failed")
            continue
        if not dcts:
            excluded.append({"ccode": code, "name": name, "reason": "no .dct link"})
            print(f"  {code} no dictionary")
            continue
        chosen = None
        dct_url = None
        dct_raw = None
        dct_when = None
        why = "no dictionary matched the Kenya labels"
        for url in dcts:
            dct_name = url.rstrip("/").split("/")[-1]
            dct_dest = DATA / code / dct_name
            try:
                raw, when = fetch(url, dct_dest)
            except Exception as exc:  # noqa: BLE001
                why = f"dct download {type(exc).__name__}: {exc}"
                continue
            if raw[:1] in (b"<", b"{"):
                why = "dct was not a dictionary"
                continue
            parsed = parse_dictionary(raw.decode("latin1", "replace"))
            ok, reason = labels_ok(parsed)
            if ok:
                chosen = parsed
                dct_url = url
                dct_raw = raw
                dct_when = when
                break
            why = reason
        if chosen is None:
            excluded.append({"ccode": code, "name": name, "reason": why, "dcts": dcts})
            print(f"  {code} excluded: {why}")
            continue
        dat_url = dct_url[:-4] + ".dat"
        dat_dest = DATA / code / (dct_url.rstrip("/").split("/")[-1][:-4] + ".dat")
        try:
            dat_raw, dat_when = fetch(dat_url, dat_dest)
        except Exception as exc:  # noqa: BLE001
            excluded.append({"ccode": code, "name": name, "reason": f"dat: {type(exc).__name__}: {exc}"})
            print(f"  {code} dat failed")
            continue
        if dat_raw[:1] in (b"<", b"{"):
            excluded.append({"ccode": code, "name": name, "reason": "dat payload was HTML or JSON"})
            print(f"  {code} dat not microdata")
            continue
        lrecl = chosen["meta"]["lrecl"]
        nrec = chosen["meta"]["nrec"]
        recs, err = records(dat_raw, lrecl, nrec)
        if err:
            excluded.append({"ccode": code, "name": name, "reason": err, "byte_size": len(dat_raw)})
            print(f"  {code} {err}")
            continue
        stats = analyze_survey(recs, chosen)
        dct_info = file_info(dct_url, dct_raw, dct_when)
        dat_info = file_info(dat_url, dat_raw, dat_when)
        entry = {
            "ccode": code,
            "name": name,
            "landing_url": page,
            "lrecl": lrecl,
            "nrec": nrec,
            "dictionary": dct_info,
            "data": dat_info,
            **{k: stats[k] for k in stats},
        }
        if stats.get("drop"):
            excluded.append(entry)
            print(f"  {code} drop: {stats['drop']}")
            continue
        included.append(entry)
        print(f"  {code} n={stats['n']} p={stats['p']:.4f} concord={stats['concordance']:.4f}")

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    if not included:
        reasons = [e.get("reason", "") for e in excluded]
        unreachable = all(
            r.startswith("page:") or r.startswith("dat:") or "download" in r or r == "no .dct link"
            for r in reasons
        ) if reasons else True
        result["status"] = "complete"
        result["verdict"] = "inconclusive"
        result["reason"] = "data-unavailable" if unreachable else "other"
        result["data_kind"] = "none"
        result["confidence"] = confidence_for("inconclusive", None, 0, 0)
        result["measured"] = {"value": None, "unit": "weighted proportion still amenorrheic", "n": 0, "extra": {"excluded": excluded}}
        result["method"] = "The public WFS index was read and every linked standard-recode dictionary was checked against the pre-registered labels. No survey both downloaded and passed the coding checks."
        result["datasets"] = []
        result["deviations"] = DEVIATIONS
        DERIVED.joinpath("measured.json").write_text(json.dumps({"included": included, "excluded": excluded}, indent=2))
        result_path.write_text(json.dumps(result, indent=2) + "\n")
        print("INCONCLUSIVE", result["reason"])
        return

    n = sum(s["n"] for s in included)
    # Weights were already applied inside each survey. Rescale each survey to its eligible n and pool.
    pooled_p = sum(s["p"] * s["n"] for s in included) / n
    pooled_resumed = 1.0 - pooled_p
    if n < 200:
        verdict, reason = "inconclusive", "underpowered"
    else:
        verdict, reason = decide(pooled_p, pooled_resumed, n, included)

    ps = [s["p"] for s in included]
    full_ns = [s for s in included if s.get("n_full_breastfeeding")]
    full_n = sum(s["n_full_breastfeeding"] for s in full_ns)
    full_p = (sum(s["p_full_breastfeeding"] * s["n_full_breastfeeding"] for s in full_ns) / full_n) if full_n else None

    datasets = []
    for s in included:
        datasets.append({
            "id": f"wfs-sr-{s['ccode']}",
            "name": f"World Fertility Survey standard recode, {s['name']}",
            "landing_url": s["landing_url"],
            "doi": None,
            "version": "WFS SR02 public-use",
            "license": "Public-use file. The Kenya release note, which the registration treated as the archive's stated condition, allows academic research with credit to the agency that conducted the survey.",
            "files": [
                {"name": "dictionary", **s["dictionary"]},
                {"name": "standard-recode", **s["data"]},
            ],
            "role": "individual records of current breastfeeding and amenorrhea in the open interval",
        })

    measured = {
        "value": pooled_p,
        "unit": "weighted proportion still amenorrheic (F122=96) among eligible currently breastfeeding women",
        "n": n,
        "uncertainty": f"survey proportions {min(ps):.4f} to {max(ps):.4f} across {len(included)} surveys",
        "extra": {
            "proportion_amenorrhea_ended": pooled_resumed,
            "n_surveys": len(included),
            "surveys": [
                {
                    "ccode": s["ccode"],
                    "name": s["name"],
                    "n": s["n"],
                    "n_weighted": s["n_weighted"],
                    "proportion_still_amenorrheic": s["p"],
                    "proportion_amenorrhea_ended": s["p_resumed"],
                    "concordance_f121_f122": s["concordance"],
                    "n_full_breastfeeding": s["n_full_breastfeeding"],
                    "proportion_still_amenorrheic_if_full_breastfeeding": s["p_full_breastfeeding"],
                    "data_sha256": s["data"]["sha256"],
                    "data_byte_size": s["data"]["byte_size"],
                }
                for s in included
            ],
            "full_breastfeeding_pooled_n": full_n,
            "full_breastfeeding_pooled_proportion_still_amenorrheic": full_p,
            "n_surveys_excluded": len(excluded),
        },
    }
    # JSON cannot store raw tuples; excluded entries may contain the same stats.
    def scrub(obj):
        if isinstance(obj, float):
            return obj
        return obj

    derived = {
        "pooled_proportion_still_amenorrheic": pooled_p,
        "pooled_proportion_amenorrhea_ended": pooled_resumed,
        "n": n,
        "verdict": verdict,
        "surveys": measured["extra"]["surveys"],
        "excluded": [
            {k: v for k, v in e.items() if k not in {"dictionary", "data"} or True}
            for e in excluded
        ],
    }
    # Keep excluded reasons, drop bulky repeated file hashes from the human table by retaining them: they are small.
    DERIVED.joinpath("measured.json").write_text(json.dumps(derived, indent=2) + "\n")
    DERIVED.joinpath("by-survey.csv").write_text(
        "ccode,name,n,proportion_still_amenorrheic,proportion_amenorrhea_ended,concordance,n_full,p_full,byte_size,sha256\n"
        + "".join(
            f"{s['ccode']},{s['name'].replace(',', ';')},{s['n']},{s['p']:.6f},{s['p_resumed']:.6f},{s['concordance']:.6f},{s['n_full_breastfeeding']},{'' if s['p_full_breastfeeding'] is None else f'{s['p_full_breastfeeding']:.6f}'},{s['data']['byte_size']},{s['data']['sha256']}\n"
            for s in included
        )
    )

    result["status"] = "complete"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["data_kind"] = "biological"
    result["confidence"] = confidence_for(verdict, pooled_p, n, len(included))
    result["measured"] = measured
    result["datasets"] = datasets
    result["method"] = (
        "Every country linked from the World Fertility Survey public index was opened. "
        "A survey entered the pool only when its original .dct used the same codes as Kenya: "
        "current breastfeeding (F117=1), not currently pregnant (V206=0), pill or injection excluded by value label, "
        "and amenorrhea in the open interval (F122=96 still amenorrheic; a closed duration is an integer from that dictionary's own minimum through its maximum). "
        "Design weights V006/1000 were applied inside each survey, rescaled to sum to that survey's eligible count, and pooled. "
        "The pre-registered thresholds were then applied. Full breastfeeding (F119=1) is reported and does not set the verdict. "
        f"Excluded surveys: {len(excluded)}."
    )
    result["deviations"] = DEVIATIONS
    lows = sorted(included, key=lambda s: s["p"])[:3]
    highs = sorted(included, key=lambda s: s["p"], reverse=True)[:3]
    result["results_summary"] = [
        f"Pooled weighted proportion still amenorrheic: {pooled_p:.4f} on {n} eligible women in {len(included)} surveys; proportion whose amenorrhea had ended: {pooled_resumed:.4f}.",
        "Lowest surveys: " + "; ".join(f"{s['name']} {s['p']:.3f} (n={s['n']})" for s in lows) + ".",
        "Highest surveys: " + "; ".join(f"{s['name']} {s['p']:.3f} (n={s['n']})" for s in highs) + ".",
        (
            f"Among women coded as fully breastfeeding, the pooled proportion still amenorrheic is {full_p:.4f} (n={full_n}). This split was pre-registered as descriptive."
            if full_p is not None
            else "No survey contributed a full-breastfeeding subset."
        ),
    ]
    result["caveats"] = list(result.get("caveats") or []) + [
        "Partial breastfeeding is coded as still breastfeeding. Women on the pill or an injection were removed; other contraceptives were kept.",
        "F122 values 0 through 41 are read as a closed amenorrhea interval because 96 is the dictionary's code for still amenorrheic. A closed interval means menstruation resumed during the open pregnancy interval, and the woman was still breastfeeding at interview.",
        f"{len(excluded)} linked surveys were not in the pool. Reasons are in derived/measured.json.",
    ]
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    print(f"VERDICT {verdict} p={pooled_p:.4f} n={n} surveys={len(included)}")


if __name__ == "__main__":
    main()
