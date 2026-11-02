#!/usr/bin/env python3
"""aristotle-ga02-05: internal viviparity only in animals that breathe air.

Uses FishBase snapshot v26.06 (the pre-registered backup) when the Dryad mode
file cannot be fetched. Placental coding follows method_preregistered, with the
negation fix recorded in deviations. Does not edit the pass or fail text.

Run: python3 analysis.py
Needs pyarrow (pip install pyarrow).
"""
import datetime as dt
import hashlib
import json
import re
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
FB = "https://data.source.coop/cboettig/fishbase/fb/v26.06/parquet/"
DRYAD_PAGE = "https://datadryad.org/dataset/doi:10.5061/dryad.80gb5mm12"
DRYAD_LINKSET = DRYAD_PAGE + "/linkset.json"
UA = "delphisci-claim-test/aristotle-ga02-05"
AIR_CODES = {"Facultative", "FacultativeGenus", "FacultativeObligate", "Obligate", "ObligateGenus"}
WATER_CODES = {"Water", "WaterAssumed"}


def fetch(url, name):
    DATA.mkdir(exist_ok=True)
    path = DATA / name
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    raw = urllib.request.urlopen(req, timeout=180).read()
    path.write_bytes(raw)
    return {
        "name": name,
        "download_url": url,
        "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, path


def try_dryad():
    """Return (csv_bytes, meta) or (None, error string). Does not solve bot challenges."""
    try:
        req = urllib.request.Request(DRYAD_LINKSET, headers={"User-Agent": UA})
        raw = urllib.request.urlopen(req, timeout=40).read()
        linkset = json.loads(raw)
    except Exception as exc:
        return None, "linkset: %s" % exc
    hrefs = []
    for item in linkset.get("linkset", [{}])[0].get("item", []):
        if item.get("type") == "text/csv":
            hrefs.append(item["href"])
    # Prefer the file whose first line is the mode table. Read only a small prefix.
    for href in hrefs:
        try:
            req = urllib.request.Request(href, headers={"User-Agent": UA, "Range": "bytes=0-400"})
            with urllib.request.urlopen(req, timeout=40) as resp:
                head = resp.read(400)
        except Exception as exc:
            return None, "csv %s: %s" % (href, exc)
        if b"mode" in head.lower() and b"species" in head.lower() and b"<html" not in head[:200].lower():
            req = urllib.request.Request(href, headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=90).read()
            if raw[:20].lower().startswith(b"<!doctype") or b"anubis" in raw[:500].lower():
                return None, "dryad file_stream returned a bot-check page, not a csv"
            return raw, href
        if b"<html" in head[:300].lower() or b"anubis" in head[:300].lower() or b"validating" in head[:300].lower():
            return None, "dryad file_stream returned a bot-check page, not a csv"
    return None, "no mode csv among %d csv links" % len(hrefs)


def placental_text(text):
    """Positive placenta mention. Negations are removed so 'aplacental' and 'without a placenta' do not count."""
    t = text or ""
    t = re.sub(r"without (?:a |an )?(?:yolk[- ]sac )?placentas?", " ", t, flags=re.I)
    t = re.sub(r"\bno placenta\b", " ", t, flags=re.I)
    t = re.sub(r"aplacental", " ", t, flags=re.I)
    return re.search(r"placenta", t, flags=re.I) is not None


def main():
    dryad_bytes, dryad_info = try_dryad()
    used_dryad = isinstance(dryad_bytes, (bytes, bytearray))
    files = []
    species_meta, species_path = fetch(FB + "species.parquet", "species.parquet")
    files.append(species_meta)
    ref_meta, ref_path = fetch(FB + "airbreathingref.parquet", "airbreathingref.parquet")
    files.append(ref_meta)
    if used_dryad:
        DATA.mkdir(exist_ok=True)
        (DATA / "shark_modepruned_E.csv").write_bytes(dryad_bytes)
        files.append({
            "name": "shark_modepruned_E.csv",
            "download_url": dryad_info,
            "retrieved_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(dryad_bytes),
            "sha256": hashlib.sha256(dryad_bytes).hexdigest(),
        })
        source = "dryad"
    else:
        rep_meta, rep_path = fetch(FB + "reproduc.parquet", "reproduc.parquet")
        files.append(rep_meta)
        source = "fishbase-reproduc-backup"

    import pyarrow.parquet as pq  # local name for the closure below
    species = pq.read_table(species_path, columns=["SpecCode", "Genus", "Species", "AirBreathing"]).to_pandas()
    ref = pq.read_table(ref_path).to_pandas()
    labels = {str(r.AirBreathingCode): str(r.AirBreathing) for _, r in ref.iterrows()}

    if source == "dryad":
        import csv
        import io
        rows = list(csv.DictReader(io.StringIO(dryad_bytes.decode("utf-8", "replace"))))
        # column names as published
        mode_key = "mode" if rows and "mode" in rows[0] else None
        species_key = "species" if rows and "species" in rows[0] else None
        if not mode_key or not species_key:
            raise SystemExit("dryad columns %s" % (list(rows[0]) if rows else None))
        name_to_spec = {}
        for rec in species.itertuples(index=False):
            if rec.Genus and rec.Species:
                name_to_spec["%s %s" % (rec.Genus, rec.Species)] = rec
        placental = []
        for row in rows:
            if row[mode_key].strip() != "Placental_viviparity":
                continue
            sp = name_to_spec.get(row[species_key].strip())
            placental.append({
                "binomial": row[species_key].strip(),
                "air": None if sp is None else (None if sp.AirBreathing is None or str(sp.AirBreathing) == "nan" else str(sp.AirBreathing)),
                "snippet": "Placental_viviparity",
            })
    else:
        rep = pq.read_table(rep_path, columns=["SpecCode", "RepGuild2", "AddInfos"]).to_pandas()
        guild = rep["RepGuild2"].fillna("").str.contains("internal live bearer", case=False)
        live = rep[guild]
        by_spec = {}
        for rec in live.itertuples(index=False):
            text = "" if rec.AddInfos is None else str(rec.AddInfos)
            slot = by_spec.setdefault(int(rec.SpecCode), {"texts": []})
            slot["texts"].append(text)
        spec_lookup = {int(r.SpecCode): r for r in species.itertuples(index=False)}
        placental = []
        for spec, slot in by_spec.items():
            if not any(placental_text(t) for t in slot["texts"]):
                continue
            sp = spec_lookup.get(spec)
            air = None
            binomial = "SpecCode %s" % spec
            if sp is not None and sp.Genus and sp.Species:
                binomial = "%s %s" % (sp.Genus, sp.Species)
                if sp.AirBreathing is not None and str(sp.AirBreathing) != "nan":
                    air = str(sp.AirBreathing)
            hit = next(t for t in slot["texts"] if placental_text(t))
            placental.append({"binomial": binomial, "air": air, "snippet": re.sub(r"\s+", " ", hit)[:180]})

    def klass(code):
        if code is None:
            return "unmatched"
        if code in AIR_CODES:
            return "air"
        if code in WATER_CODES:
            return "not_air"
        return "unmatched"

    for row in placental:
        row["class"] = klass(row["air"])
        row["air_label"] = labels.get(row["air"], row["air"])
    n = len(placental)
    n_air = sum(r["class"] == "air" for r in placental)
    n_not = sum(r["class"] == "not_air" for r in placental)
    n_un = sum(r["class"] == "unmatched" for r in placental)
    n_assumed = sum(r["air"] == "WaterAssumed" for r in placental)
    n_water = sum(r["air"] == "Water" for r in placental)
    genera = sorted({r["binomial"].split()[0] for r in placental if r["binomial"] and not r["binomial"].startswith("SpecCode")})
    matched = n_air + n_not
    match_rate = (matched / n) if n else 0.0

    if n_not >= 1:
        verdict = "refutes"
        reason = None
        confidence = 0.80 if n_not >= 5 else 0.65
    elif n >= 15 and match_rate >= 0.90 and n_not == 0 and n_air == matched:
        verdict = "supports"
        reason = None
        confidence = 0.40
    elif n < 15 or (n_not == 0 and match_rate < 0.5):
        verdict = "inconclusive"
        reason = "underpowered"
        confidence = 0.35
    else:
        verdict = "inconclusive"
        reason = "underpowered"
        confidence = 0.35

    examples = [r["binomial"] for r in placental if r["class"] == "not_air"][:8]
    measured = {
        "value": n_not,
        "unit": "placentally viviparous species coded not air-breathing",
        "n": n,
        "uncertainty": None,
        "extra": {
            "source": source,
            "placental_species": n,
            "matched_respiration": matched,
            "match_rate": round(match_rate, 4),
            "air_breathing": n_air,
            "not_air_breathing": n_not,
            "of_which_water_assumed": n_assumed,
            "of_which_water_explicit": n_water,
            "unmatched": n_un,
            "example_non_air_binomials": examples,
            "genera": genera,
            "n_genera": len(genera),
            "dryad_error": None if used_dryad else dryad_info,
        },
    }
    DERIVED.mkdir(exist_ok=True)
    lines = ["binomial,air_code,air_label,class,snippet"]
    for r in sorted(placental, key=lambda x: x["binomial"]):
        snip = r["snippet"].replace('"', "'").replace("\n", " ")
        lines.append('"%s",%s,"%s",%s,"%s"' % (r["binomial"], r["air"] or "", (r["air_label"] or "").replace('"', "'"), r["class"], snip))
    (DERIVED / "placental_species.csv").write_text("\n".join(lines) + "\n")
    (DERIVED / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")

    result = json.loads((HERE / "result.json").read_text())
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result["deviations"] = [{
        "what": "The backup pattern /placenta/i also matches the negation 'aplacental' and the phrase 'without a placenta'.",
        "why": "Those phrases deny a placenta. Rows are placental only after those negations are removed. Thresholds are unchanged. Yolk-only rows are still excluded from the test class.",
    }, {
        "what": "FishBase stores air-breathing as the codes in airbreathingref, not the words yes/no.",
        "why": "Codes whose label contains 'air-breathing' (Facultative, FacultativeGenus, FacultativeObligate, Obligate, ObligateGenus) count as air-breathing, including facultative, as pre-registered. Codes whose label is water-breathing (Water, WaterAssumed) count as not air-breathing. WaterAssumed is FishBase's explicit 'only water-breathing (assumed)' category.",
    }]
    result["datasets"] = [{
        "id": "fishbase-v26.06-species-and-respiration",
        "name": "FishBase species table snapshot v26.06, air-breathing field, via the rfishbase source.coop release",
        "landing_url": "https://www.fishbase.se/",
        "doi": None,
        "version": "v26.06",
        "license": None,
        "files": [species_meta, ref_meta],
        "role": "air-breathing code for each species, with the seven-row code list",
    }]
    if source != "dryad":
        result["datasets"].append({
            "id": "fishbase-v26.06-reproduc-backup",
            "name": "FishBase reproduc table snapshot v26.06",
            "landing_url": "https://www.fishbase.org/manual/english/FishBaseThe_REPRODUCTION_Table.htm",
            "doi": None,
            "version": "v26.06",
            "license": None,
            "files": [rep_meta],
            "role": "internal live bearers whose notes state a placenta, used because the Dryad mode file could not be downloaded",
        })
    result["measured"] = measured
    result["method"] = (
        "Tried the Dryad mode file (%s). " % ("downloaded" if used_dryad else "not downloaded: %s" % dryad_info)
        + "Classified internal live bearers as placental only when the note still says placenta after removing 'aplacental' and 'without a placenta'. "
        + "Joined to FishBase species.AirBreathing. One matched non-air-breathing placental species refutes the universal. Yolk-only live birth was not used as a counterexample."
    )
    result["results_summary"] = [
        "Placental species: %d. Air-breathing %d, not air-breathing %d (Water %d, WaterAssumed %d), unmatched %d." % (n, n_air, n_not, n_water, n_assumed, n_un),
        "Match rate %.3f. Examples not air-breathing: %s." % (match_rate, ", ".join(examples) if examples else "none"),
        "Source of the reproductive class: %s." % source,
    ]
    caveats = [c for c in (result.get("caveats") or []) if not str(c).startswith("Analysis: ")]
    caveats.append(
        "Analysis: All %d species whose notes still say placenta are coded 'only water-breathing (assumed)' (WaterAssumed), FishBase's default water-breathing category, rather than from a species-by-species respiration paper. The code is the database's statement that they are not air-breathers. It is not a new measurement of gill ventilation. Genera in the set: %s."
        % (n_assumed, ", ".join(genera))
    )
    caveats.append("Analysis: The test class is the FishBase internal-live-bearer notes that still contain the word placenta after the negation filter. It does not re-survey mammals, and it does not add yolk-only live birth. A single non-air-breathing placental fish refutes the universal. Species whose notes never use the word placenta are outside this backup pattern.")
    if not used_dryad:
        caveats.append("Analysis: The Dryad file shark_modepruned_E.csv was not used. The download URL returns an interstitial bot check rather than the CSV. The pre-registered FishBase reproduc backup was used instead.")
    result["caveats"] = caveats
    (HERE / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"verdict": verdict, "confidence": confidence, "n": n, "not_air": n_not, "air": n_air, "assumed": n_assumed, "source": source}, indent=2))


if __name__ == "__main__":
    main()
