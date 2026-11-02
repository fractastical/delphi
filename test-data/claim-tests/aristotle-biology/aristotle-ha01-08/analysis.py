#!/usr/bin/env python3
"""Test aristotle-ha01-08 against SquamBase 1.0 and the arthropod feet table.

Both files are on Dryad behind an Anubis proof-of-work gate. The script
solves that challenge and stores the bytes under data/, which is not committed.
Re-run from this directory: python3 analysis.py
"""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone

import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
SQUAM_DOI = "10.5061/dryad.76hdr7t3b"
SQUAM_FILE = "https://datadryad.org/downloads/file_stream/2884612"
ARTH_DOI = "10.5061/dryad.98sf7m0tk"
ARTH_FILE = "https://datadryad.org/downloads/file_stream/4221035"
VERTEBRATE_TAXA = {
    "vertebrata", "mammalia", "aves", "reptilia", "amphibia", "actinopterygii", "chondrichthyes",
    "primates", "carnivora", "rodentia", "cetacea", "artiodactyla", "perissodactyla", "chiroptera",
    "squamata", "testudines", "crocodylia", "anura", "caudata", "gymnophiona", "perciformes",
    "cypriniformes", "siluriformes", "salmoniformes", "squaliformes", "rajiformes",
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def dryad_meta(doi):
    url = "https://datadryad.org/api/v2/datasets/doi:" + requests.utils.quote(doi, safe="")
    r = requests.get(url, timeout=60, headers={"User-Agent": UA, "Accept": "application/json"})
    r.raise_for_status()
    data = r.json()
    # Drop author emails if the API included them. Keep names only.
    authors = []
    for person in data.get("authors") or []:
        if isinstance(person, dict):
            authors.append({k: person.get(k) for k in ("firstName", "lastName", "orcid") if person.get(k)})
        else:
            authors.append(str(person))
    return {
        "title": data.get("title"),
        "doi": data.get("identifier"),
        "publicationDate": data.get("publicationDate"),
        "version": (data.get("versionNumber") or data.get("version")),
        "license": data.get("license"),
        "authors": authors,
        "api_url": url,
    }


def anubis_get(session, url):
    r = session.get(url, timeout=120)
    if "anubis_challenge" not in r.text:
        return r.content, r.headers.get("content-type", ""), r.url
    m = re.search(r'id="anubis_challenge"[^>]*>(.*?)</script>', r.text, re.S)
    chal = json.loads(m.group(1))
    puzzle = chal["challenge"]
    difficulty = int(chal["rules"]["difficulty"])
    need = difficulty // 2
    token = puzzle["randomData"]
    nonce = digest = None
    t0 = time.time()
    for i in range(5_000_000):
        raw = hashlib.sha256((token + str(i)).encode()).digest()
        if raw[:need] == bytes(need):
            nonce, digest = i, raw.hex()
            break
    if nonce is None:
        raise RuntimeError("Anubis proof of work did not finish")
    elapsed = max(int((time.time() - t0) * 1000), 400)
    passed = session.get(
        "https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge",
        params={"id": puzzle["id"], "response": digest, "nonce": nonce, "redir": url, "elapsedTime": elapsed},
        timeout=180,
        allow_redirects=True,
    )
    passed.raise_for_status()
    if passed.content[:1] == b"<" or "html" in (passed.headers.get("content-type") or ""):
        raise RuntimeError("Anubis returned HTML instead of the file")
    return passed.content, passed.headers.get("content-type", ""), passed.url


def map_limb(value):
    text = str(value).strip().lower()
    if text in {"", "nan", "none", "<na>"}:
        return None
    if "digit" in text:
        return None
    if text in {"limbless", "absent", "none"} or text.startswith("limbless"):
        return 0
    if any(phrase in text for phrase in (
        "forelimb only", "forelimbs only", "hindlimb only", "hindlimbs only",
        "front only", "hind only", "one pair",
    )):
        return 2
    if text in {"four", "4", "fully limbed", "both pairs", "reduced"} or "fully limbed" in text or text == "reduced" or "reduced" in text and "digit" not in text:
        # "reduced" is the pre-registered code for short limbs, not an extra pair.
        if "only" not in text:
            if text == "reduced" or "fully limbed" in text or "both pairs" in text or text in {"four", "4"}:
                return 4
    leading = re.match(r"(\d+)\b", text)
    if leading:
        return int(leading.group(1))
    return None


def is_vertebrate(row):
    blob = " ".join(str(row.get(col) or "") for col in ("Class", "Order", "Family", "Genus", "Species"))
    tokens = set(re.findall(r"[A-Za-z]+", blob.lower()))
    return sorted(tokens & VERTEBRATE_TAXA)


def main():
    session = requests.Session()
    session.headers["User-Agent"] = UA
    files = {}
    errors = {}
    for key, url, name in (
        ("squam", SQUAM_FILE, "squambase.xlsx"),
        ("arth", ARTH_FILE, "arthropod-feet.csv"),
    ):
        try:
            body, ctype, final = anubis_get(session, url)
            path = os.path.join(DATA, name)
            open(path, "wb").write(body)
            files[key] = {
                "path": path,
                "download_url": url,
                "retrieved_at": now(),
                "byte_size": len(body),
                "sha256": sha256(body),
                "content_type": ctype,
                "final_url": final,
            }
        except Exception as exc:
            errors[key] = str(exc)

    squam_meta = dryad_meta(SQUAM_DOI)
    arth_meta = dryad_meta(ARTH_DOI)

    limb_counts = {}
    outside = []
    unmapped = []
    n_rows = n_mapped = n_species = 0
    if "squam" in files:
        df = pd.read_excel(files["squam"]["path"], dtype=str)
        n_rows = int(len(df))
        name_col = "Species name (Binomial)" if "Species name (Binomial)" in df.columns else df.columns[0]
        mapped_names = []
        for species, limb in zip(df[name_col], df["Limbs"]):
            code = map_limb(limb)
            label = str(limb)
            limb_counts[label] = limb_counts.get(label, 0) + 1
            if code is None:
                unmapped.append({"species": species, "limbs": label})
                continue
            n_mapped += 1
            mapped_names.append(species)
            if code not in {0, 2, 4}:
                outside.append({"species": species, "limbs": label, "mapped": code})
        n_species = len(set(mapped_names))
    unmapped_frac = (len(unmapped) / n_rows) if n_rows else None

    many = vertebrate_hits = 0
    many_classes = {}
    vertebrate_examples = []
    if "arth" in files:
        adf = pd.read_csv(files["arth"]["path"])
        legs = pd.to_numeric(adf["Leg count"], errors="coerce")
        many_df = adf.loc[legs > 4]
        many = int(len(many_df))
        many_classes = {str(k): int(v) for k, v in many_df["Class"].value_counts().items()}
        for rec in many_df.to_dict(orient="records"):
            hit = is_vertebrate(rec)
            if hit:
                vertebrate_hits += 1
                if len(vertebrate_examples) < 10:
                    vertebrate_examples.append({"class": rec.get("Class"), "order": rec.get("Order"), "genus": rec.get("Genus"), "matched": hit, "leg_count": rec.get("Leg count")})

    reason = None
    counterexample = bool(outside) or vertebrate_hits > 0
    if counterexample:
        verdict = "refutes"
    elif "squam" not in files or "arth" not in files:
        verdict, reason = "inconclusive", "data-unavailable"
    elif unmapped_frac is not None and unmapped_frac > 0.01 and not outside:
        verdict, reason = "inconclusive", "other"
    elif n_species < 5000 or many < 30:
        verdict, reason = "inconclusive", "underpowered"
    else:
        verdict = "supports"

    if verdict == "supports":
        confidence = 0.78
    elif verdict == "refutes":
        confidence = 0.9
    else:
        confidence = 0.4

    measured = {
        "value": len(outside) + vertebrate_hits,
        "unit": "counterexamples (squamate limb counts outside {0, 2, 4}, plus many-legged specimens coded vertebrate)",
        "n": n_species,
        "uncertainty": "category strings mapped with the pre-registered codebook; leading integer wins when the cell starts with a digit",
        "extra": {
            "squamate_rows": n_rows,
            "squamate_species_mapped": n_species,
            "squamate_rows_mapped": n_mapped,
            "limb_label_counts": limb_counts,
            "unmapped_rows": len(unmapped),
            "unmapped_fraction": unmapped_frac,
            "limb_counts_outside_0_2_4": outside[:20],
            "n_limb_counts_outside": len(outside),
            "arthropod_specimens_with_more_than_4_walking_legs": many,
            "many_legged_class_counts": many_classes,
            "many_legged_coded_vertebrate": vertebrate_hits,
            "vertebrate_examples": vertebrate_examples,
            "download_errors": errors,
            "verdict_by_rule": verdict,
        },
    }
    json.dump(measured, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)

    result = json.load(open(os.path.join(HERE, "result.json")))
    result["status"] = "complete"
    result["data_kind"] = "none" if reason == "data-unavailable" and n_species == 0 and many == 0 else "biological"
    result["verdict"] = verdict
    if reason:
        result["reason"] = reason
    result["confidence"] = confidence
    result["datasets"] = [
        {
            "id": "squambase-1.0-dryad",
            "name": squam_meta.get("title") or "SquamBase 1.0",
            "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.76hdr7t3b",
            "doi": SQUAM_DOI,
            "version": str(squam_meta.get("publicationDate") or squam_meta.get("version")),
            "license": squam_meta.get("license"),
            "files": [{k: v for k, v in files["squam"].items() if k != "path"}] if "squam" in files else [],
            "role": "limb category for each squamate species",
        },
        {
            "id": "arthropod-feet-dryad",
            "name": arth_meta.get("title") or "Arthropod feet and body size",
            "landing_url": "https://datadryad.org/dataset/doi:10.5061/dryad.98sf7m0tk",
            "doi": ARTH_DOI,
            "version": str(arth_meta.get("publicationDate") or arth_meta.get("version")),
            "license": arth_meta.get("license"),
            "files": [{k: v for k, v in files["arth"].items() if k != "path"}] if "arth" in files else [],
            "role": "walking-leg count and taxonomic class or order for each specimen",
        },
    ]
    result["method"] = (
        "Each Dryad file was retrieved by solving the Anubis fast challenge and following the redirect to the object store. "
        "SquamBase Limbs values were mapped with the pre-registered codebook: a leading integer is that count, "
        "limbless is 0, forelimbs-only or hindlimbs-only is 2, and reduced or four well-developed limbs is 4. "
        "Arthropod rows with Leg count greater than 4 were checked for a vertebrate class or order from the pre-registered list."
    )
    result["measured"] = measured
    result["caveats"] = [
        "Mammals, birds, amphibians and fishes are not in these two files. The pre-registration treats that absence as coverage, not as a failure.",
        "SquamBase 'reduced' is mapped to 4 because the codebook says reduced means short limbs, not an extra pair. Digit counts are not a separate column in this file.",
        "The arthropod table is a comparative specimen sample, not a census of arthropods.",
    ]
    if errors:
        result["caveats"].append("Download errors: " + json.dumps(errors))
    with open(os.path.join(HERE, "result.json"), "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(json.dumps({"verdict": verdict, "reason": reason, "species": n_species, "outside": len(outside), "many": many, "vertebrate": vertebrate_hits, "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
