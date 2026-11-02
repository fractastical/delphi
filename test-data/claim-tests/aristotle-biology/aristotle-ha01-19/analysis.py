#!/usr/bin/env python3
"""Count bony ribs on one side of the canonical human skeleton.

Pre-registered in result.json before these sources were queried for this test:
a per-side count of exactly 8 supports; agreement on any other count refutes;
disagreement is mixed. Grouping classes, costal cartilages and named variants
are not ordinals. A source counts only if it gives a contiguous series 1..N
or an explicit typical number on one side.

Run from this directory: python3 analysis.py
Writes data/ (gitignored), derived/measured.json, and fills result.json.
"""

import hashlib
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-ha01-19)"

ORDINALS = [
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
]
WORD_TO_N = {word: i + 1 for i, word in enumerate(ORDINALS)}
WORD_TO_N.update({str(i + 1): i + 1 for i in range(len(ORDINALS))})
# Gray states a cardinal ("twelve in number"), not the ordinal adjective used as an FMA label.
CARDINALS = [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen",
]
WORD_TO_N.update({word: i + 1 for i, word in enumerate(CARDINALS)})

GRAY_URL = "https://archive.org/download/anatomyofhumanbo1918gray/anatomyofhumanbo1918gray_djvu.txt"
FMA_ONTOLOGY_URL = "https://www.ebi.ac.uk/ols4/api/ontologies/fma"
FMA_SEARCH = "https://www.ebi.ac.uk/ols4/api/search?q={q}&ontology=fma&rows=200"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        raw = dest.read_bytes()
        retrieved = datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        final_url = url
    else:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            final_url = resp.geturl()
        dest.write_bytes(raw)
        retrieved = now()
    return {
        "download_url": final_url,
        "requested_url": url,
        "retrieved_at": retrieved,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "path": str(dest.relative_to(HERE)),
    }, raw


def exact_rib_label(label, word):
    """True for the rib bone itself, not a part, cartilage, groove or variant."""
    lab = re.sub(r"\s+", " ", label.strip().lower())
    if any(bad in lab for bad in ("cartilage", "cervical", "lumbar", "bifid", "supernumerary")):
        return False
    return lab in {f"{word} rib", f"left {word} rib", f"right {word} rib"}


def fma_counts():
    meta_info, meta_raw = fetch(FMA_ONTOLOGY_URL, DATA / "fma-ontology.json")
    meta = json.loads(meta_raw.decode("utf-8"))
    config = meta.get("config", {})
    version = config.get("version") or meta.get("version")
    queries = []
    present = []
    for word in ORDINALS:
        url = FMA_SEARCH.format(q=urllib.parse.quote(f"{word} rib"))
        info, raw = fetch(url, DATA / f"fma-search-{word}-rib.json")
        payload = json.loads(raw.decode("utf-8"))
        docs = payload.get("response", {}).get("docs", [])
        hits = []
        for doc in docs:
            label = doc.get("label") or ""
            if exact_rib_label(label, word):
                hits.append(
                    {
                        "label": label,
                        "iri": doc.get("iri"),
                        "short_form": doc.get("short_form"),
                    }
                )
        side = {
            "unspecified": any(h["label"].lower() == f"{word} rib" for h in hits),
            "left": any(h["label"].lower() == f"left {word} rib" for h in hits),
            "right": any(h["label"].lower() == f"right {word} rib" for h in hits),
        }
        entry = {
            "ordinal": WORD_TO_N[word],
            "word": word,
            "n_exact_bones": len(hits),
            "sides": side,
            "labels": [h["label"] for h in hits],
        }
        queries.append({**info, "num_found": payload.get("response", {}).get("numFound"), "kept": entry})
        if hits:
            present.append(entry)
    ordinals = sorted(e["ordinal"] for e in present)
    contiguous = []
    for n in ordinals:
        if n == len(contiguous) + 1:
            contiguous.append(n)
        else:
            break
    per_side = len(contiguous)
    # A gapped list is not a count (pre-registered). Trailing ordinals beyond the
    # first gap are recorded but do not extend N.
    admissible = per_side >= 1 and contiguous == list(range(1, per_side + 1))
    left_n = sum(1 for e in present if e["ordinal"] <= per_side and e["sides"]["left"])
    right_n = sum(1 for e in present if e["ordinal"] <= per_side and e["sides"]["right"])
    return {
        "file": meta_info,
        "version": version,
        "title": config.get("title"),
        "queries": [
            {
                "requested_url": q["requested_url"],
                "download_url": q["download_url"],
                "retrieved_at": q["retrieved_at"],
                "byte_size": q["byte_size"],
                "sha256": q["sha256"],
                "path": q["path"],
            }
            for q in queries
        ],
        "ordinals_with_a_bone_class": ordinals,
        "contiguous_from_one": contiguous,
        "per_side": per_side if admissible else None,
        "admissible": admissible,
        "left": left_n if admissible else None,
        "right": right_n if admissible else None,
        "bones": present,
    }


def gray_count(text):
    """Typical number: the first 'N in number on either side' (or 'each side') in the rib chapter.

    The Internet Archive djvu text doubles spaces and breaks lines. Matching is done on
    whitespace-collapsed text so those artefacts are not part of the count.
    """
    flat = re.sub(r"\s+", " ", text)
    low = flat.lower()
    start = low.find("the ribs are elastic arches")
    if start < 0:
        start = low.find("4b. the ribs")
    end = low.find("the costal cartilages", start + 20) if start >= 0 else -1
    if start < 0:
        window = flat
        chapter_found = False
    else:
        window = flat[start : end if end > start else start + 2500]
        chapter_found = True
    number_re = re.compile(
        r"\b(" + "|".join(CARDINALS + ORDINALS) + r"|\d{1,2})\b(?:\s+\w+){0,4}?\s+in\s+number\s+on\s+(?:either|each)\s+side",
        re.I,
    )
    matches = []
    for m in number_re.finditer(window):
        token = m.group(1).lower()
        if token.isdigit():
            value = int(token)
        else:
            value = WORD_TO_N.get(token)
        sentence_start = window.rfind(".", 0, m.start())
        sentence_end = window.find(".", m.end())
        sentence = window[sentence_start + 1 : sentence_end + 1].strip()
        sentence = re.sub(r"\s+", " ", sentence)
        matches.append({"value": value, "sentence": sentence})
    typical = matches[0]["value"] if matches and matches[0]["value"] else None
    return {
        "chapter_found": chapter_found,
        "window_chars": len(window),
        "matches": matches,
        "per_side": typical,
        "admissible": typical is not None,
        "excerpt": re.sub(r"\s+", " ", window[:1500]).strip(),
    }


def decide(fma, gray):
    sources = []
    if fma["admissible"]:
        sources.append(("fma", fma["per_side"]))
    if gray["admissible"]:
        sources.append(("gray1918", gray["per_side"]))
    if not sources:
        return "inconclusive", "data-unavailable", None, 0.3
    counts = {name: n for name, n in sources}
    values = list(counts.values())
    if len(set(values)) == 1 and values[0] == 8:
        return "supports", None, 8, 0.9 if len(values) > 1 else 0.7
    if len(set(values)) == 1 and values[0] != 8:
        return "refutes", None, values[0], 0.9 if len(values) > 1 else 0.7
    return "mixed", None, None, 0.45


def main():
    fma = fma_counts()
    gray_info, gray_raw = fetch(GRAY_URL, DATA / "gray-1918-djvu.txt")
    gray = gray_count(gray_raw.decode("utf-8", errors="replace"))
    verdict, reason, value, confidence = decide(fma, gray)

    measured = {
        "value": value if value is not None else fma.get("per_side"),
        "unit": "bony ribs on one side of the canonical human trunk",
        "n": int(fma["admissible"]) + int(gray["admissible"]),
        "uncertainty": None,
        "extra": {
            "fma_per_side": fma["per_side"],
            "fma_left": fma["left"],
            "fma_right": fma["right"],
            "fma_contiguous_ordinals": fma["contiguous_from_one"],
            "fma_version": fma["version"],
            "gray_per_side": gray["per_side"],
            "gray_matches": gray["matches"],
            "sources_agree": (
                fma["admissible"]
                and gray["admissible"]
                and fma["per_side"] == gray["per_side"]
            ),
        },
    }
    # value must be the agreed count when there is one; do not invent a blend.
    if verdict == "mixed":
        measured["value"] = None
        measured["extra"]["fma_per_side"] = fma["per_side"]
        measured["extra"]["gray_per_side"] = gray["per_side"]

    out = {
        "measured": measured,
        "verdict": verdict,
        "reason": reason,
        "confidence": confidence,
        "fma_bones": fma["bones"],
        "gray_excerpt": gray["excerpt"],
        "gray_chapter_found": gray["chapter_found"],
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "measured.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")

    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    fma_files = [
        {
            "name": "fma-ontology.json",
            "download_url": fma["file"]["download_url"],
            "retrieved_at": fma["file"]["retrieved_at"],
            "byte_size": fma["file"]["byte_size"],
            "sha256": fma["file"]["sha256"],
        }
    ]
    # One checksum record per ordinal query would blow the result file; record the
    # manifest of query files in derived and the ontology metadata file here, plus
    # a combined hash of the ordinal responses in order.
    ordinal_bytes = b"".join((DATA / f"fma-search-{w}-rib.json").read_bytes() for w in ORDINALS)
    fma_files.append(
        {
            "name": "fma-search-ordinal-ribs.json (14 OLS responses, concatenated in ordinal order for the checksum)",
            "download_url": "https://www.ebi.ac.uk/ols4/api/search?ontology=fma",
            "retrieved_at": fma["queries"][-1]["retrieved_at"],
            "byte_size": len(ordinal_bytes),
            "sha256": hashlib.sha256(ordinal_bytes).hexdigest(),
        }
    )
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    result["datasets"] = [
        {
            "id": "fma-ols-human-ribs",
            "name": "Foundational Model of Anatomy, queried through the EMBL-EBI Ontology Lookup Service",
            "landing_url": "https://www.ebi.ac.uk/ols4/ontologies/fma",
            "doi": None,
            "version": fma["version"],
            "license": "CC BY 3.0",
            "files": fma_files,
            "role": "canonical human skeletal partonomy: one class per rib bone, including left and right",
        },
        {
            "id": "gray-1918-osteology-ribs",
            "name": "Henry Gray, Anatomy of the Human Body, 20th edition (1918), Internet Archive plain text",
            "landing_url": "https://archive.org/details/anatomyofhumanbo1918gray",
            "doi": None,
            "version": "1918",
            "license": "public domain",
            "files": [
                {
                    "name": "anatomyofhumanbo1918gray_djvu.txt",
                    "download_url": gray_info["download_url"],
                    "retrieved_at": gray_info["retrieved_at"],
                    "byte_size": gray_info["byte_size"],
                    "sha256": gray_info["sha256"],
                }
            ],
            "role": "public-domain statement of how many ribs the human trunk has on either side",
        },
    ]
    result["method"] = (
        "For each ordinal from first through fourteenth, the Ontology Lookup Service was queried "
        "for that phrase plus 'rib' in FMA. A hit counted only when the label was exactly "
        "'{ordinal} rib', 'Left {ordinal} rib' or 'Right {ordinal} rib', excluding cartilages and "
        "cervical, lumbar, bifid or supernumerary variants. The per-side count is the length of the "
        "contiguous run that starts at the first rib. Gray 1918 was fetched from the Internet Archive "
        "and the first sentence of the form 'N in number on either side' in the ribs chapter was read "
        "as the typical count. The pre-registered rule was then applied: agreement on 8 supports, "
        "agreement on any other integer refutes, disagreement is mixed."
    )
    result["measured"] = measured
    variant_caveat = (
        "Gray 1918 gives twelve as the typical number and then says that number may be increased "
        "by a cervical or lumbar rib or diminished to eleven. Those variants are not the typical "
        "count, and eight is not among them. Neither source is a sample of living people, so the "
        "test does not estimate how often a person has a rib count other than the canonical one."
    )
    result.setdefault("caveats", [])
    if variant_caveat not in result["caveats"]:
        result["caveats"].append(variant_caveat)
    result["results_summary"] = [
        f"FMA {fma['version']}: contiguous bony rib ordinals {fma['contiguous_from_one']}, per side {fma['per_side']}, left classes in that run {fma['left']}, right classes {fma['right']}.",
        f"Gray 1918: typical number on either side {gray['per_side']}. Matches: {gray['matches']}.",
        f"Verdict {verdict} under the pre-registered rule (support only if every admissible source says 8).",
    ]
    # Per-query provenance is part of the measurement record. Keep it out of the
    # narrative and in the derived file, which the checksum above covers.
    (DERIVED / "fma-query-manifest.json").write_text(
        json.dumps(fma["queries"], indent=2) + "\n", encoding="utf-8"
    )
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"verdict": verdict, "reason": reason, "measured": measured, "confidence": confidence}, indent=2))


if __name__ == "__main__":
    main()
