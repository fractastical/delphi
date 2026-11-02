#!/usr/bin/env python3
"""Dolphin skeleton preparations and live-birth wording.

Pre-registered: anatomy passes with at least 10 Delphinidae preparations that
name a bone or skeleton and none that call the skeleton cartilage or a fish-spine.
Viviparity passes if at least two Animal Diversity Web accounts, among
Tursiops truncatus, Delphinus delphis and Orcinus orca, say the species is
viviparous or gives birth to live young, and none says it lays eggs.
Both clauses must pass. Mammal taxonomy is not evidence.

The GBIF scan is the first 900 preserved-specimen records returned for family
Delphinidae (three pages of 300). That bound was not in the registration; it is
how a finite public response was read, and it is recorded as such.

Run: python3 analysis.py
"""

import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DERIVED = HERE / "derived"
UA = "delphisci-claim-test/1.0 (aristotle-pa02-25)"
FAMILY_KEY = 5314
PAGES = 3
PAGE_SIZE = 300
ACCOUNTS = [
    "Tursiops_truncatus",
    "Delphinus_delphis",
    "Orcinus_orca",
]
BONE = re.compile(r"\b(bones?|skeleton|skulls?|crani\w*|vertebrae?|mandibles?|osteolog\w*)\b", re.I)
CARTILAGE = re.compile(r"cartilag|fish[ -]?spine", re.I)
LIVE = re.compile(r"vivipar\w*|live birth|live young|gives birth|give birth", re.I)
EGG = re.compile(r"ovipar\w*|lays eggs|lay eggs|egg-laying", re.I)


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        raw = dest.read_bytes()
        final = url
    else:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read()
            final = resp.geturl()
        dest.write_bytes(raw)
    return {
        "download_url": final,
        "requested_url": url,
        "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }, raw


def html_text(raw):
    html = raw.decode("utf-8", errors="replace")
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def sentences_with(text, pattern):
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if pattern.search(part)]


def main():
    gbif_files = []
    preparations = []
    seen = set()
    for page in range(PAGES):
        offset = page * PAGE_SIZE
        url = (
            "https://api.gbif.org/v1/occurrence/search"
            f"?taxonKey={FAMILY_KEY}&basisOfRecord=PRESERVED_SPECIMEN&limit={PAGE_SIZE}&offset={offset}"
        )
        info, raw = fetch(url, DATA / f"gbif-page-{page}.json")
        gbif_files.append(info)
        payload = json.loads(raw.decode("utf-8"))
        for rec in payload.get("results", []):
            gid = rec.get("gbifID") or rec.get("key")
            if gid in seen:
                continue
            seen.add(gid)
            prep = rec.get("preparations")
            if not prep:
                continue
            preparations.append(
                {
                    "gbifID": gid,
                    "species": rec.get("species") or rec.get("scientificName"),
                    "preparations": prep,
                    "bone": bool(BONE.search(prep)),
                    "cartilage_or_fish_spine": bool(CARTILAGE.search(prep)),
                }
            )

    bone_rows = [row for row in preparations if row["bone"]]
    cartilage_rows = [row for row in preparations if row["cartilage_or_fish_spine"]]
    anatomy_tested = len(bone_rows) >= 10 or len(cartilage_rows) > 0
    anatomy_pass = len(bone_rows) >= 10 and len(cartilage_rows) == 0
    anatomy_fail = len(cartilage_rows) > 0

    accounts = []
    adw_files = []
    for slug in ACCOUNTS:
        url = f"https://animaldiversity.org/accounts/{slug}/"
        info, raw = fetch(url, DATA / f"{slug}.html")
        adw_files.append(info)
        text = html_text(raw)
        live_s = sentences_with(text, LIVE)
        egg_s = sentences_with(text, EGG)
        # Negated egg sentences ("do not lay eggs") are not a claim that they lay eggs.
        egg_positive = []
        for sentence in egg_s:
            if re.search(r"\b(not|never|no|unlike|rather than|instead of)\b", sentence, re.I):
                continue
            egg_positive.append(sentence)
        accounts.append(
            {
                "species": slug.replace("_", " "),
                "url": url,
                "live_sentences": live_s[:6],
                "egg_sentences": egg_positive[:6],
                "live": bool(live_s),
                "egg": bool(egg_positive),
            }
        )
    retrieved = [a for a in accounts if a["live"] or a["egg"] or True]
    # A page that was fetched counts as retrieved. The clause needs the words.
    n_live = sum(1 for a in accounts if a["live"] and not a["egg"])
    n_egg = sum(1 for a in accounts if a["egg"])
    viviparity_pass = n_live >= 2 and n_egg == 0
    viviparity_fail = n_egg > 0
    viviparity_tested = viviparity_pass or viviparity_fail or n_live > 0

    if anatomy_fail or viviparity_fail:
        verdict, reason, confidence = "refutes", None, 0.75
    elif anatomy_pass and viviparity_pass:
        verdict, reason, confidence = "supports", None, 0.75
    elif (anatomy_pass and not viviparity_tested) or (viviparity_pass and not anatomy_tested):
        verdict, reason, confidence = "mixed", None, 0.5
    elif anatomy_pass or viviparity_pass:
        # One clause passed and the other was tested but did not pass and did not fail:
        # too few bone records, or too few live-birth accounts.
        verdict, reason, confidence = "mixed", None, 0.5
    else:
        verdict, reason, confidence = "inconclusive", "data-unavailable", 0.45

    measured = {
        "value": len(bone_rows),
        "unit": "Delphinidae preserved specimens in the GBIF scan whose preparation names a bone or skeleton",
        "n": len(seen),
        "uncertainty": None,
        "extra": {
            "gbif_records_scanned": len(seen),
            "preparations_nonempty": len(preparations),
            "bone_preparations": len(bone_rows),
            "cartilage_or_fish_spine_preparations": len(cartilage_rows),
            "anatomy_pass": anatomy_pass,
            "viviparity_pass": viviparity_pass,
            "accounts_stating_live_birth": n_live,
            "accounts_stating_eggs": n_egg,
            "cartilage_examples": cartilage_rows[:15],
            "bone_examples": [
                {"gbifID": row["gbifID"], "species": row["species"], "preparations": row["preparations"]}
                for row in bone_rows[:15]
            ],
            "accounts": accounts,
        },
    }
    DERIVED.mkdir(parents=True, exist_ok=True)
    (DERIVED / "preparations.json").write_text(json.dumps(preparations, indent=2) + "\n", encoding="utf-8")
    (DERIVED / "measured.json").write_text(
        json.dumps({"verdict": verdict, "reason": reason, "confidence": confidence, "measured": measured}, indent=2) + "\n",
        encoding="utf-8",
    )
    result = json.loads((HERE / "result.json").read_text(encoding="utf-8"))
    result["status"] = "complete"
    result["data_kind"] = "biological"
    result["verdict"] = verdict
    result["confidence"] = confidence
    if reason:
        result["reason"] = reason
    elif "reason" in result:
        del result["reason"]
    result["datasets"] = [
        {
            "id": "gbif-delphinidae-preserved-specimens",
            "name": "GBIF occurrence search, preserved specimens of Delphinidae",
            "landing_url": "https://www.gbif.org/species/5314",
            "doi": None,
            "version": "GBIF occurrence API, familyKey 5314",
            "license": "record-level licenses vary; the API response is the source read here",
            "files": gbif_files,
            "role": "preparation text for dolphin specimens, scored for bone versus cartilage or fish-spine",
        },
        {
            "id": "adw-dolphin-accounts",
            "name": "Animal Diversity Web accounts for three dolphin species",
            "landing_url": "https://animaldiversity.org/",
            "doi": None,
            "version": "pages retrieved " + now()[:10],
            "license": "ADW content is available for educational use; see animaldiversity.org",
            "files": adw_files,
            "role": "wording of reproductive mode: viviparous or live birth, versus egg-laying",
        },
    ]
    result["measured"] = measured
    result["method"] = (
        f"The first {PAGES * PAGE_SIZE} preserved-specimen occurrences of Delphinidae "
        f"(GBIF familyKey {FAMILY_KEY}) were read in pages of {PAGE_SIZE}. "
        "A preparation counted as bone if it named bone, skeleton, skull, cranium, vertebra, mandible or an osteological element, "
        "and as cartilage or fish-spine if it contained those words. "
        "Empty preparation fields were ignored. Animal Diversity Web accounts for Tursiops truncatus, "
        "Delphinus delphis and Orcinus orca were read as text. A live-birth sentence matches viviparous, "
        "live birth, live young, or gives birth. An egg sentence matches oviparous, lays eggs, lay eggs or egg-laying, "
        "unless the sentence negates it. Both clauses had to pass."
    )
    result["results_summary"] = [
        f"GBIF scan: {len(seen)} preserved specimens, {len(preparations)} with preparation text, {len(bone_rows)} bone or skeleton, {len(cartilage_rows)} cartilage or fish-spine.",
        f"ADW: {n_live} accounts state live birth or viviparity, {n_egg} state egg-laying.",
        f"Anatomy pass {anatomy_pass}. Viviparity pass {viviparity_pass}. Verdict {verdict}.",
    ]
    note = (
        f"The GBIF count is the first {len(seen)} preserved records in the API's default order, not every dolphin specimen in GBIF."
    )
    result.setdefault("caveats", [])
    if note not in result["caveats"]:
        result["caveats"].append(note)
    (HERE / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "bone": len(bone_rows),
        "cartilage": len(cartilage_rows),
        "scanned": len(seen),
        "live": n_live,
        "egg": n_egg,
    }, indent=2))


if __name__ == "__main__":
    main()
